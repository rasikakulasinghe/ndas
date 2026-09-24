"""
backup/tests/test_restore_apply.py -- Story 2.3

`backup/restore_apply.py` and `manage.py run_restore`: starting a restore
(every refusal reason and the successful path), the re-verification/snapshot/
preflight/apply/media steps, the single-transaction rollback guarantee, the
`_raw_delete` no-cascade contract, media handling, and the terminal states
(notification, upload status, staged-archive cleanup) driven through the real
command.

Two archive-building strategies are used, chosen per scenario:

  * Real domain objects + `create_export` (`export_archive`) -- for
    integration-level tests (happy path, patient removal, media) where the
    archive's records must be genuinely save()-able (every required field
    present, exactly as Django's own export would produce). The resulting
    `db_export.json` is sometimes re-opened and mutated (`export_json` /
    `rebuild_archive`) to engineer a specific edge case without hand-writing
    a full valid Patient record.
  * Hand-built minimal records (`skeleton`, `patient_record`) -- for
    preflight-only tests, which never reach `.save()` and so only need the
    handful of fields preflight itself inspects (pk, model, institution,
    identifiers, m2m lists).
"""
import json
import shutil
import struct
import zipfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone

from backup import restore_apply, restore_preview, restore_validation
from backup.models import BackupJob, RestoreUpload
from backup.restore_apply import ExportFormatError, RestoreError
from backup.restore_validation import get_upload_dir, get_upload_path
from backup.services import create_export
from backup.tests.restore_helpers import IsolatedBaseDirMixin, build_archive, sha256_file
from institution.models import Institution, PatientMoveLog
from ndas.custom_codes.choice import (
    BackupJobScopeType,
    BackupJobStatus,
    BackupJobType,
    NotificationType,
    RestoreAuthenticity,
    RestoreUploadStatus,
    UserType,
)
from patients.models import Attachment, IndicationsForGMA, Patient
from problemlist.models import Problem, ProblemAction
from referral.models import Notification, ReferralSent
from video.models import Video

User = get_user_model()

STORAGE_OVERRIDE = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)

def _to_millis(dt):
    """`DjangoJSONEncoder` truncates a datetime's fractional seconds to
    milliseconds when serializing (matches JS `Date.toISOString()`), so a
    value that round-tripped through the export/restore JSON never has its
    original microseconds back -- compare at millisecond precision."""
    return dt.replace(microsecond=(dt.microsecond // 1000) * 1000)


def _inflate_declared_media_size(path, arcname, new_size):
    """Patch `arcname`'s DECLARED uncompressed size, in both its local file
    header and its central directory record, to `new_size` -- the actual
    stored bytes and CRC are left untouched. `ZipFile.writestr` always
    recomputes `file_size` from what was actually written (there is no
    supported way to hand it a mismatched size), so an oversized declared
    size can only be engineered by editing the raw header bytes afterwards
    -- the same low-level approach `restore_helpers.corrupt_member_data`
    uses to corrupt a member's payload, applied to the size field instead."""
    data = bytearray(Path(path).read_bytes())
    with zipfile.ZipFile(path) as zf:
        info = zf.getinfo(arcname)
    # Local file header: uncompressed size is a 4-byte field at offset +22.
    struct.pack_into('<I', data, info.header_offset + 22, new_size)
    # Central directory record: scan for the entry naming `arcname` and
    # patch its uncompressed size field at offset +24.
    target = arcname.encode('utf-8')
    idx = 0
    while True:
        idx = data.index(b'PK\x01\x02', idx)
        name_len, extra_len, comment_len = struct.unpack_from('<HHH', data, idx + 28)
        name_start = idx + 46
        if bytes(data[name_start:name_start + name_len]) == target:
            struct.pack_into('<I', data, idx + 24, new_size)
            break
        idx = name_start + name_len + extra_len + comment_len
    Path(path).write_bytes(bytes(data))


EXPORT_KEYS_ORDER = (
    'patients.patient',
    'referral.referralsent',
    'referral.referralreceived',
    'referral.referralmessage',
    'video.video',
    'patients.attachment',
    'patients.gmassessment',
    'patients.hineassessment',
    'patients.developmentalassessment',
    'patients.cdicrecord',
    'patients.generalpaediatricassessment',
    'problemlist.problem',
    'problemlist.problemaction',
)


@STORAGE_OVERRIDE
class RestoreApplyTestBase(IsolatedBaseDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='ra_sa', password='x', position='Administrator',
            mobile_primary='0770000601', user_type=UserType.SUPERADMIN,
            is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(name='RA Hosp', slug='ra-hosp', created_by=self.user)
        self.inst2 = Institution.objects.create(name='RA Hosp 2', slug='ra-hosp-2', created_by=self.user)

    # ---- domain object builders (minimal fields proven to satisfy every
    # validator/constraint -- mirrors backup/tests/test_services.py) ----

    def make_patient(self, institution, baby_name='Baby', bht=None, **kwargs):
        defaults = dict(
            baby_name=baby_name, mother_name='Mother', bht=bht, institution=institution,
            gender='Male', dob_tob=timezone.now(), pog_wks=38, pog_days=0, birth_weight=3000, ofc=33,
            mo_delivery='Normal vaginal delivery (NVD)', tp_mobile='0771234567', added_by=self.user,
        )
        defaults.update(kwargs)
        return Patient.objects.create(**defaults)

    def make_video(self, patient, name='a.mp4', content=b'video-bytes'):
        return Video.objects.create(
            patient=patient, title='Vid', recorded_on=timezone.now(),
            video_file=SimpleUploadedFile(name, content, content_type='video/mp4'), added_by=self.user,
        )

    def make_attachment(self, patient, name='a.txt', content=b'attachment-bytes'):
        return Attachment.objects.create(
            patient=patient, title='Att', attachment_type='document',
            attachment=SimpleUploadedFile(name, content), added_by=self.user,
        )

    def make_problem(self, patient):
        problem = Problem.objects.create(patient=patient, name='Asthma', added_by=self.user)
        ProblemAction.objects.create(problem=problem, action='Reviewed', added_by=self.user)
        return problem

    def make_referral(self, institution, patient):
        return ReferralSent.objects.create(
            from_institution=institution, to_institution=institution, institution=institution,
            patient=patient, initial_message='Referral msg', from_clinician=self.user,
            to_clinician=self.user, added_by=self.user,
        )

    def make_move_log(self, patient, institution):
        return PatientMoveLog.objects.create(
            patient=patient, from_institution=institution, to_institution=self.inst2, moved_by=self.user,
        )

    # ---- real export / stage / confirm pipeline ----

    def export_archive(self, institution, job_type=BackupJobType.BACKUP,
                        scope_type=BackupJobScopeType.SINGLE, institutions=None):
        """Run a real `create_export` for `institution` and mark the export
        job completed with its own checksum (so it verifies as origin).
        Returns (job, archive_path, checksum)."""
        job = BackupJob.objects.create(
            job_type=job_type, status=BackupJobStatus.PENDING, scope_type=scope_type,
            scope=institution if scope_type == BackupJobScopeType.SINGLE else None,
            trigger_institution=institution, triggered_by=self.user,
        )
        if scope_type == BackupJobScopeType.MULTI:
            job.scopes.set(institutions or [institution])
        archive_path, _skipped, checksum = create_export(job)
        job.status = BackupJobStatus.COMPLETED
        job.progress_pct = 100
        job.archive_checksum = checksum
        job.save()
        return job, archive_path, checksum

    def export_json(self, institution, **kwargs):
        """(db_export dict, media {name: bytes}, manifest dict) of a fresh
        real export -- for tests that mutate a genuine record set."""
        _job, archive_path, _checksum = self.export_archive(institution, **kwargs)
        with zipfile.ZipFile(archive_path) as zf:
            db_export = json.loads(zf.read('db_export.json'))
            manifest = json.loads(zf.read('manifest.json'))
            media = {n: zf.read(n) for n in zf.namelist() if n.startswith('media/')}
        return db_export, media, manifest

    def rebuild_archive(self, db_export, media, manifest_overrides=None, filename='rebuilt.zip'):
        path = self.archive_path(filename)
        build_archive(
            path, media=media,
            db_export=json.dumps(db_export).encode('utf-8'),
            manifest_overrides=manifest_overrides or {},
        )
        return path

    def stage_and_confirm(self, archive_path, allow_unverified=False, filename='staged.zip'):
        """Stage `archive_path` as a fresh RestoreUpload, validate it for
        real, then confirm it -- returns the `confirmed` upload."""
        sha = sha256_file(archive_path)
        upload = RestoreUpload.objects.create(
            uploaded_by=self.user, original_filename=filename, status=RestoreUploadStatus.VALIDATING,
        )
        get_upload_dir(upload).mkdir(parents=True, exist_ok=True)
        shutil.copy(archive_path, get_upload_path(upload))
        result = restore_validation.validate_restore_archive(
            get_upload_path(upload), sha, allow_unverified=allow_unverified,
        )
        upload.archive_sha256 = sha
        upload.size_bytes = get_upload_path(upload).stat().st_size
        upload.status = RestoreUploadStatus.VALIDATED
        upload.authenticity = result.authenticity
        upload.source_job_id = result.summary.get('source_job_id')
        upload.manifest_summary = result.summary
        upload.save()
        preview = restore_preview.build_preview(upload)
        assert not preview['blocked'], preview['block_reasons']
        outcome = restore_preview.confirm_upload(upload.id, self.user, preview['digest'], True)
        assert outcome.ok, outcome.message
        upload.refresh_from_db()
        return upload

    def build_and_confirm(self, institution, **export_kwargs):
        _job, archive_path, _checksum = self.export_archive(institution, **export_kwargs)
        return self.stage_and_confirm(archive_path)

    def start(self, upload, institution=None):
        outcome = restore_apply.start_restore(upload, self.user, institution or self.inst)
        assert outcome.ok, outcome.message
        return outcome.job

    def run_restore_command(self, job):
        call_command('run_restore', str(job.id))
        job.refresh_from_db()
        return job

    # ---- minimal hand-built archives (preflight-only; never `.save()`d) ----

    def skeleton(self, **overrides):
        data = {key: [] for key in EXPORT_KEYS_ORDER}
        data.update(overrides)
        return data

    def patient_record(self, pk, institution_id=None, **fields):
        f = {'baby_name': 'X', 'mother_name': 'Y'}
        if institution_id is not None:
            f['institution'] = institution_id
        f.update(fields)
        return {'model': 'patients.patient', 'pk': pk, 'fields': f}

    def preflight_upload(self, db_export, filename='pf.zip'):
        path = self.archive_path(filename)
        build_archive(path, db_export=json.dumps(db_export).encode('utf-8'), manifest=False)
        upload = RestoreUpload.objects.create(uploaded_by=self.user, status=RestoreUploadStatus.APPLYING)
        get_upload_dir(upload).mkdir(parents=True, exist_ok=True)
        shutil.copy(path, get_upload_path(upload))
        return upload

    def make_job(self, institution=None, scope_type=BackupJobScopeType.SINGLE, institutions=None, **kwargs):
        defaults = dict(
            job_type=BackupJobType.RESTORE, status=BackupJobStatus.RUNNING, scope_type=scope_type,
            scope=institution if scope_type == BackupJobScopeType.SINGLE else None,
            trigger_institution=institution, triggered_by=self.user,
        )
        defaults.update(kwargs)
        job = BackupJob.objects.create(**defaults)
        if scope_type == BackupJobScopeType.MULTI:
            job.scopes.set(institutions or [institution])
        return job


# ---------------------------------------------------------------------------
# start_restore: every refusal reason, and the successful path
# ---------------------------------------------------------------------------

class StartRestoreTest(RestoreApplyTestBase):
    def test_not_confirmed_is_refused(self):
        upload = RestoreUpload.objects.create(uploaded_by=self.user, status=RestoreUploadStatus.VALIDATED)
        outcome = restore_apply.start_restore(upload, self.user, self.inst)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_apply.NOT_CONFIRMED)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)
        self.assertEqual(BackupJob.objects.count(), 0)

    def test_bad_snapshot_version_is_refused(self):
        upload = self.build_and_confirm(self.inst)
        RestoreUpload.objects.filter(pk=upload.pk).update(
            confirmed_snapshot={**upload.confirmed_snapshot, 'snapshot_version': 99},
        )
        upload.refresh_from_db()
        outcome = restore_apply.start_restore(upload, self.user, self.inst)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_apply.BAD_SNAPSHOT)

    def test_institution_missing_is_refused(self):
        upload = self.build_and_confirm(self.inst)
        self.inst.delete()
        outcome = restore_apply.start_restore(upload, self.user, self.inst2)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_apply.INSTITUTION_MISSING)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)

    def test_date_scoped_archive_is_refused(self):
        upload = self.build_and_confirm(self.inst)
        summary = {**upload.manifest_summary, 'date_filter': {'applied': True, 'start': '2026-01-01', 'end': None}}
        snapshot = restore_preview._snapshot({**restore_preview.build_preview(upload), 'facts': {
            **restore_preview.build_preview(upload)['facts'], 'date_filter': summary['date_filter'],
        }})
        RestoreUpload.objects.filter(pk=upload.pk).update(manifest_summary=summary, confirmed_snapshot={
            **upload.confirmed_snapshot, 'date_filter': summary['date_filter'],
        })
        upload.refresh_from_db()
        # digest now legitimately differs from what start_restore recomputes
        # (date_filter changed) -- but date-scoped must be refused BEFORE the
        # digest check runs, so DATE_SCOPED, not DIGEST_CHANGED, is reported.
        outcome = restore_apply.start_restore(upload, self.user, self.inst)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_apply.DATE_SCOPED)

    def test_digest_changed_is_refused(self):
        upload = self.build_and_confirm(self.inst)
        RestoreUpload.objects.filter(pk=upload.pk).update(
            confirmed_snapshot={**upload.confirmed_snapshot, 'digest': 'f' * 64},
        )
        upload.refresh_from_db()
        outcome = restore_apply.start_restore(upload, self.user, self.inst)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_apply.DIGEST_CHANGED)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)

    def test_missing_staged_archive_is_refused(self):
        upload = self.build_and_confirm(self.inst)
        get_upload_path(upload).unlink()
        outcome = restore_apply.start_restore(upload, self.user, self.inst)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_apply.ARCHIVE_PROBLEM)

    @mock.patch('backup.restore_apply.has_sufficient_restore_disk', return_value=(False, 1, 2, 3))
    def test_disk_too_small_is_refused(self, _mock):
        upload = self.build_and_confirm(self.inst)
        outcome = restore_apply.start_restore(upload, self.user, self.inst)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_apply.DISK_TOO_SMALL)
        self.assertEqual(BackupJob.objects.count(), 1)  # only the origin export job

    @mock.patch('backup.restore_apply.has_sufficient_restore_disk', side_effect=OSError('boom'))
    def test_disk_check_failure_is_refused(self, _mock):
        upload = self.build_and_confirm(self.inst)
        outcome = restore_apply.start_restore(upload, self.user, self.inst)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_apply.DISK_UNKNOWN)

    def test_overlapping_job_refuses_start_and_leaves_upload_confirmed(self):
        upload = self.build_and_confirm(self.inst)
        BackupJob.objects.create(
            job_type=BackupJobType.BACKUP, status=BackupJobStatus.RUNNING,
            scope_type=BackupJobScopeType.SINGLE, scope=self.inst, triggered_by=self.user,
        )
        outcome = restore_apply.start_restore(upload, self.user, self.inst)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_apply.LOCK_CONFLICT)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)

    def test_disjoint_scope_job_does_not_block_start(self):
        upload = self.build_and_confirm(self.inst)
        BackupJob.objects.create(
            job_type=BackupJobType.BACKUP, status=BackupJobStatus.RUNNING,
            scope_type=BackupJobScopeType.SINGLE, scope=self.inst2, triggered_by=self.user,
        )
        outcome = restore_apply.start_restore(upload, self.user, self.inst)
        self.assertTrue(outcome.ok, outcome.message)

    def test_success_creates_restore_job_and_flips_upload_to_applying(self):
        upload = self.build_and_confirm(self.inst)
        job = self.start(upload)
        self.assertEqual(job.job_type, BackupJobType.RESTORE)
        self.assertEqual(job.status, BackupJobStatus.PENDING)
        self.assertEqual(job.restore_upload_id, upload.id)
        self.assertEqual(job.scope, self.inst)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.APPLYING)

    def test_abort_start_fails_job_and_reverts_upload(self):
        upload = self.build_and_confirm(self.inst)
        job = self.start(upload)
        restore_apply.abort_start(job, upload, "Failed to launch restore process: boom")
        job.refresh_from_db()
        upload.refresh_from_db()
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertIn('boom', job.error_message)
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)


# ---------------------------------------------------------------------------
# revert_upload_to_confirmed: the fallback branch when the upload cannot
# legitimately go back to `confirmed`
# ---------------------------------------------------------------------------

class RevertUploadToConfirmedFallbackTest(RestoreApplyTestBase):
    def test_falls_back_to_failed_with_a_message_and_deletes_the_staged_file(self):
        # An `applying` upload whose confirmed_at/confirmed_snapshot are
        # missing (should not happen once `check_upload_ready` has run, but
        # `revert_upload_to_confirmed` must still not silently leave a bare
        # 'failed' row with no explanation and a staged file the
        # restore_status_partial.html 'failed' branch claims is gone).
        upload = RestoreUpload.objects.create(uploaded_by=self.user, status=RestoreUploadStatus.APPLYING)
        get_upload_dir(upload).mkdir(parents=True, exist_ok=True)
        get_upload_path(upload).write_bytes(b'staged-bytes')
        self.assertTrue(get_upload_path(upload).exists())

        restore_apply.revert_upload_to_confirmed(upload)

        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.FAILED)
        self.assertTrue(upload.error_message, "a meaningful error_message must be recorded")
        self.assertFalse(get_upload_path(upload).exists())

    def test_falls_back_to_failed_when_confirmed_snapshot_is_not_a_dict(self):
        upload = RestoreUpload.objects.create(
            uploaded_by=self.user, status=RestoreUploadStatus.APPLYING,
            confirmed_at=timezone.now(), confirmed_snapshot=None,
        )
        get_upload_dir(upload).mkdir(parents=True, exist_ok=True)
        get_upload_path(upload).write_bytes(b'staged-bytes')

        restore_apply.revert_upload_to_confirmed(upload)

        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.FAILED)
        self.assertTrue(upload.error_message)
        self.assertFalse(get_upload_path(upload).exists())

    def test_legitimate_case_still_returns_to_confirmed(self):
        # Unchanged behaviour: a real confirmation record goes back to
        # 'confirmed', with no error_message and the staged file untouched.
        upload = RestoreUpload.objects.create(
            uploaded_by=self.user, status=RestoreUploadStatus.APPLYING,
            confirmed_at=timezone.now(), confirmed_snapshot={'snapshot_version': 1, 'digest': 'a' * 64},
        )
        get_upload_dir(upload).mkdir(parents=True, exist_ok=True)
        get_upload_path(upload).write_bytes(b'staged-bytes')

        restore_apply.revert_upload_to_confirmed(upload)

        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        self.assertTrue(get_upload_path(upload).exists())


# ---------------------------------------------------------------------------
# Preflight (read-only) -- every rejection reason
# ---------------------------------------------------------------------------

class PreflightTest(RestoreApplyTestBase):
    def test_unknown_model_key_is_rejected(self):
        upload = self.preflight_upload(self.skeleton(**{'some.bogus_model': []}))
        job = self.make_job(self.inst)
        with self.assertRaises(ExportFormatError) as cm:
            restore_apply.preflight(upload, job)
        self.assertIn('unknown model key', str(cm.exception))

    def test_out_of_order_model_keys_is_rejected(self):
        data = {}
        keys = list(EXPORT_KEYS_ORDER)
        keys[0], keys[4] = keys[4], keys[0]  # swap video.video before patients.patient
        for key in keys:
            data[key] = []
        upload = self.preflight_upload(data)
        job = self.make_job(self.inst)
        with self.assertRaises(ExportFormatError) as cm:
            restore_apply.preflight(upload, job)
        self.assertIn('out of order', str(cm.exception))

    def test_duplicate_pk_within_a_model_is_rejected(self):
        upload = self.preflight_upload(self.skeleton(**{
            'patients.patient': [
                self.patient_record(1, self.inst.id),
                self.patient_record(1, self.inst.id),
            ],
        }))
        job = self.make_job(self.inst)
        with self.assertRaises(ExportFormatError) as cm:
            restore_apply.preflight(upload, job)
        self.assertIn('more than once', str(cm.exception))

    def test_foreign_institution_patient_is_rejected(self):
        upload = self.preflight_upload(self.skeleton(**{
            'patients.patient': [self.patient_record(1, self.inst2.id)],
        }))
        job = self.make_job(self.inst)
        with self.assertRaises(ExportFormatError) as cm:
            restore_apply.preflight(upload, job)
        self.assertIn('not one of the institutions', str(cm.exception))

    def test_malformed_record_shape_is_rejected(self):
        upload = self.preflight_upload(self.skeleton(**{'patients.patient': ["not-a-dict"]}))
        job = self.make_job(self.inst)
        with self.assertRaises(ExportFormatError) as cm:
            restore_apply.preflight(upload, job)
        self.assertIn('is not an object', str(cm.exception))

    def test_non_integer_pk_is_rejected(self):
        upload = self.preflight_upload(self.skeleton(**{
            'patients.patient': [{'model': 'patients.patient', 'pk': 'abc', 'fields': {}}],
        }))
        job = self.make_job(self.inst)
        with self.assertRaises(ExportFormatError) as cm:
            restore_apply.preflight(upload, job)
        self.assertIn('integer primary key', str(cm.exception))

    def test_pk_already_exists_outside_scope_is_rejected(self):
        outsider = self.make_patient(self.inst2, bht='OUT-1')
        upload = self.preflight_upload(self.skeleton(**{
            'patients.patient': [self.patient_record(outsider.pk, self.inst.id)],
        }))
        job = self.make_job(self.inst)
        with self.assertRaises(ExportFormatError) as cm:
            restore_apply.preflight(upload, job)
        self.assertIn('outside the scope being restored', str(cm.exception))

    def test_pk_that_exists_inside_scope_is_allowed(self):
        # The exact scenario the delete-then-load is designed for: the pk
        # already exists, but only inside the scope about to be deleted.
        existing = self.make_patient(self.inst, bht='IN-1')
        upload = self.preflight_upload(self.skeleton(**{
            'patients.patient': [self.patient_record(existing.pk, self.inst.id)],
        }))
        job = self.make_job(self.inst)
        result = restore_apply.preflight(upload, job)
        self.assertEqual(result.counts['patients.patient'], 1)

    def test_patient_identifier_collision_outside_scope_is_rejected(self):
        self.make_patient(self.inst2, bht='DUP-1')
        upload = self.preflight_upload(self.skeleton(**{
            # A pk far outside the auto-increment range in use, so this
            # doesn't also (accidentally) trip the pk-collision check.
            'patients.patient': [self.patient_record(555001, self.inst.id, bht='DUP-1')],
        }))
        job = self.make_job(self.inst)
        with self.assertRaises(ExportFormatError) as cm:
            restore_apply.preflight(upload, job)
        self.assertIn('DUP-1', str(cm.exception))

    def test_duplicate_identifier_within_the_archive_itself_is_rejected(self):
        upload = self.preflight_upload(self.skeleton(**{
            'patients.patient': [
                self.patient_record(1, self.inst.id, bht='DUP-2'),
                self.patient_record(2, self.inst.id, bht='DUP-2'),
            ],
        }))
        job = self.make_job(self.inst)
        with self.assertRaises(ExportFormatError) as cm:
            restore_apply.preflight(upload, job)
        self.assertIn('more than one patient', str(cm.exception))

    def test_missing_m2m_reference_is_rejected(self):
        upload = self.preflight_upload(self.skeleton(**{
            'patients.patient': [self.patient_record(1, self.inst.id, indecation_for_gma=[999999])],
        }))
        job = self.make_job(self.inst)
        with self.assertRaises(ExportFormatError) as cm:
            restore_apply.preflight(upload, job)
        self.assertIn('999999', str(cm.exception))

    def test_existing_m2m_reference_passes(self):
        indication = IndicationsForGMA.objects.create(title='Prematurity RA', level='High')
        upload = self.preflight_upload(self.skeleton(**{
            'patients.patient': [self.patient_record(1, self.inst.id, indecation_for_gma=[indication.id])],
        }))
        job = self.make_job(self.inst)
        result = restore_apply.preflight(upload, job)
        self.assertEqual(result.total, 1)

    def test_null_institution_allowed_only_for_system_scope(self):
        single_job = self.make_job(self.inst)
        upload = self.preflight_upload(self.skeleton(**{
            'patients.patient': [self.patient_record(1, None)],
        }))
        with self.assertRaises(ExportFormatError):
            restore_apply.preflight(upload, single_job)

        system_job = self.make_job(scope_type=BackupJobScopeType.SYSTEM, status=BackupJobStatus.RUNNING)
        upload2 = self.preflight_upload(self.skeleton(**{
            'patients.patient': [self.patient_record(1, None)],
        }))
        RestoreUpload.objects.filter(pk=upload2.pk).update(manifest_summary={'institutions': [self.inst.slug]})
        upload2.refresh_from_db()
        result = restore_apply.preflight(upload2, system_job)
        self.assertEqual(result.total, 1)

    def test_referral_keys_are_never_loaded_into_memory_or_checked(self):
        # Garbage referral records (missing fields entirely) must not
        # trip anything -- they're skipped by the reader before any
        # shape/field check runs.
        upload = self.preflight_upload(self.skeleton(**{
            'referral.referralsent': [{'not': 'even a real record'}, 12345],
        }))
        job = self.make_job(self.inst)
        result = restore_apply.preflight(upload, job)
        self.assertEqual(result.total, 0)


# ---------------------------------------------------------------------------
# apply_restore: rollback guarantee, user/referral fix-ups, m2m replacement
# ---------------------------------------------------------------------------

class ApplyRestoreTest(RestoreApplyTestBase):
    def _upload_and_job(self, db_export, media=None):
        path = self.rebuild_archive(db_export, media or {})
        upload = RestoreUpload.objects.create(uploaded_by=self.user, status=RestoreUploadStatus.APPLYING)
        get_upload_dir(upload).mkdir(parents=True, exist_ok=True)
        shutil.copy(path, get_upload_path(upload))
        job = self.make_job(self.inst)
        RestoreUpload.objects.filter(pk=upload.pk).update()
        return upload, job

    def test_rollback_on_bad_record_leaves_data_unchanged(self):
        patient = self.make_patient(self.inst, baby_name='Original', bht='ROL-1')
        original_updated_at = patient.updated_at
        db_export, media, _manifest = self.export_json(self.inst)
        # Corrupt the record after Patient (video.video) with a field that
        # cannot be assigned -- the whole transaction must roll back.
        db_export['video.video'] = [{'model': 'video.video', 'pk': 999, 'fields': {'not_a_real_field': 1}}]
        upload, job = self._upload_and_job(db_export, media)

        with self.assertRaises(RestoreError):
            restore_apply.apply_restore(upload, job)

        patient.refresh_from_db()
        self.assertEqual(patient.baby_name, 'Original')
        self.assertEqual(patient.updated_at, original_updated_at)

    def test_missing_user_fk_is_nulled_and_restore_proceeds(self):
        patient = self.make_patient(self.inst, baby_name='HasUser', bht='USR-1')
        db_export, media, _manifest = self.export_json(self.inst)
        rec = next(r for r in db_export['patients.patient'] if r['pk'] == patient.pk)
        rec['fields']['added_by'] = 999999  # does not exist on this system
        upload, job = self._upload_and_job(db_export, media)

        restore_apply.apply_restore(upload, job)

        restored = Patient.objects.all_institutions().get(pk=patient.pk)
        self.assertIsNone(restored.added_by_id)

    def test_patient_absent_from_archive_is_removed_and_referral_nulled_movelog_removed(self):
        keep = self.make_patient(self.inst, baby_name='Keep', bht='KEEP-1')
        gone = self.make_patient(self.inst, baby_name='Gone', bht='GONE-1')
        referral = self.make_referral(self.inst, gone)
        untouched_referral = self.make_referral(self.inst, keep)
        move_log = self.make_move_log(gone, self.inst)

        # Archive taken while only `keep` existed (gone was added after).
        db_export, media, _manifest = self.export_json(self.inst)
        db_export['patients.patient'] = [r for r in db_export['patients.patient'] if r['pk'] == keep.pk]
        upload, job = self._upload_and_job(db_export, media)

        restore_apply.apply_restore(upload, job)

        self.assertFalse(Patient.objects.all_institutions().filter(pk=gone.pk).exists())
        self.assertTrue(Patient.objects.all_institutions().filter(pk=keep.pk).exists())
        referral.refresh_from_db()
        self.assertIsNone(referral.patient_id)
        untouched_referral.refresh_from_db()
        self.assertEqual(untouched_referral.patient_id, keep.pk)
        self.assertFalse(PatientMoveLog.objects.filter(pk=move_log.pk).exists())

    def test_m2m_through_rows_are_replaced_not_merged(self):
        indication_old = IndicationsForGMA.objects.create(title='Old Indication', level='Low')
        indication_new = IndicationsForGMA.objects.create(title='New Indication', level='Low')
        patient = self.make_patient(self.inst, baby_name='M2M', bht='M2M-1')
        patient.indecation_for_gma.set([indication_old])

        db_export, media, _manifest = self.export_json(self.inst)  # archive has indication_old

        # Mutate the CURRENT (not archived) m2m state.
        patient.indecation_for_gma.set([indication_new])
        self.assertEqual(set(patient.indecation_for_gma.values_list('pk', flat=True)), {indication_new.pk})

        upload, job = self._upload_and_job(db_export, media)
        restore_apply.apply_restore(upload, job)

        restored = Patient.objects.all_institutions().get(pk=patient.pk)
        self.assertEqual(set(restored.indecation_for_gma.values_list('pk', flat=True)), {indication_old.pk})

    def test_raw_delete_does_not_cascade_or_touch_files_or_fire_signals(self):
        """Pins the private-API contract `apply_restore` depends on: deleting
        the scope's rows with `_raw_delete` must NOT cascade into
        PatientMoveLog, NOT null ReferralSent.patient via Django's own
        on_delete machinery (that is done explicitly, separately), and NOT
        delete the file on disk (django_cleanup's post_delete signal never
        fires for a raw delete)."""
        patient = self.make_patient(self.inst, baby_name='RawDel', bht='RAW-1')
        video = self.make_video(patient)
        file_path = Path(video.video_file.path)
        self.assertTrue(file_path.exists())
        referral = self.make_referral(self.inst, patient)
        move_log = self.make_move_log(patient, self.inst)

        plan = restore_apply._restore_plan(self.make_job(self.inst))
        try:
            restore_apply._delete_scope(plan)

            self.assertFalse(Patient.objects.all_institutions().filter(pk=patient.pk).exists())
            self.assertFalse(Video.objects.filter(pk=video.pk).exists())
            # Neither cascade/SET_NULL fix-up ran (that's `_fix_references`'s
            # job, called separately, later, inside `apply_restore`) ...
            referral.refresh_from_db()
            self.assertEqual(referral.patient_id, patient.pk)
            self.assertTrue(PatientMoveLog.objects.filter(pk=move_log.pk).exists())
            # ... and the file was never touched.
            self.assertTrue(file_path.exists())
        finally:
            # `_raw_delete` deliberately leaves a dangling FK (that's the
            # point of this test) -- SQLite's deferred FK check at the test
            # transaction's teardown would otherwise fail on it, so clean up
            # exactly as `_fix_references` would before the test ends.
            ReferralSent.objects.filter(pk=referral.pk).update(patient=None)
            PatientMoveLog.objects.filter(pk=move_log.pk).delete()


# ---------------------------------------------------------------------------
# _reset_sequences: PostgreSQL-only behaviour, mocked (the dev/test DB is
# SQLite, where `sequence_reset_sql` returns nothing -- see module docstring
# of this test file's item 7 for why this is mocked rather than integration-
# tested against a real backend).
# ---------------------------------------------------------------------------

class ResetSequencesTest(RestoreApplyTestBase):
    def test_reset_sequences_executes_the_backends_statements_for_every_restored_model(self):
        fake_statements = [f"-- reset statement {i}" for i in range(3)]
        mock_cm = mock.MagicMock()
        mock_cursor_obj = mock.MagicMock()
        mock_cm.__enter__.return_value = mock_cursor_obj
        mock_cm.__exit__.return_value = False

        with mock.patch.object(connection, 'vendor', 'postgresql'), \
             mock.patch.object(connection.ops, 'sequence_reset_sql', return_value=fake_statements) as mocked_sql, \
             mock.patch.object(connection, 'cursor', return_value=mock_cm):
            restore_apply._reset_sequences()

        mocked_sql.assert_called_once()
        called_models = mocked_sql.call_args[0][1]
        self.assertEqual(
            {f"{m._meta.app_label}.{m._meta.model_name}" for m in called_models},
            set(restore_apply.RESTORE_MODEL_KEYS),
        )
        self.assertEqual(
            [call_args.args[0] for call_args in mock_cursor_obj.execute.call_args_list],
            fake_statements,
        )

    def test_reset_sequences_is_a_no_op_when_the_backend_has_nothing_to_reset(self):
        # SQLite's real behaviour: `sequence_reset_sql` returns an empty
        # list, so no cursor is even opened.
        with mock.patch.object(connection.ops, 'sequence_reset_sql', return_value=[]), \
             mock.patch.object(connection, 'cursor') as mocked_cursor:
            restore_apply._reset_sequences()
        mocked_cursor.assert_not_called()


# ---------------------------------------------------------------------------
# Media: restored, missing member warning, existing files overwritten,
# path traversal blocked
# ---------------------------------------------------------------------------

class RestoreMediaTest(RestoreApplyTestBase):
    def test_media_is_restored_from_the_archive(self):
        patient = self.make_patient(self.inst, baby_name='Media', bht='MED-1')
        video = self.make_video(patient, name='keep.mp4', content=b'ARCHIVED-BYTES')
        db_export, media, _manifest = self.export_json(self.inst)
        video_path = Path(video.video_file.path)
        video_path.write_bytes(b'MUTATED-LOCALLY')  # simulate on-disk drift

        upload = RestoreUpload.objects.create(uploaded_by=self.user, status=RestoreUploadStatus.APPLYING)
        get_upload_dir(upload).mkdir(parents=True, exist_ok=True)
        shutil.copy(self.rebuild_archive(db_export, media), get_upload_path(upload))
        job = self.make_job(self.inst)

        warnings = restore_apply.restore_media(upload, job)
        self.assertEqual(warnings, [])
        self.assertEqual(video_path.read_bytes(), b'ARCHIVED-BYTES')

    def test_missing_media_member_produces_a_warning_not_a_failure(self):
        patient = self.make_patient(self.inst, baby_name='MissingMedia', bht='MED-2')
        self.make_video(patient, name='ghost.mp4', content=b'x')
        db_export, media, _manifest = self.export_json(self.inst)
        media = {}  # drop every media member -- the DB record still names one

        upload = RestoreUpload.objects.create(uploaded_by=self.user, status=RestoreUploadStatus.APPLYING)
        get_upload_dir(upload).mkdir(parents=True, exist_ok=True)
        shutil.copy(self.rebuild_archive(db_export, media), get_upload_path(upload))
        job = self.make_job(self.inst)

        warnings = restore_apply.restore_media(upload, job)
        self.assertEqual(len(warnings), 1)
        self.assertIn('missing from the archive', warnings[0])

    def test_oversized_declared_media_size_is_rejected_before_any_write(self):
        patient = self.make_patient(self.inst, baby_name='Oversized', bht='MED-4')
        video = self.make_video(patient, name='huge.mp4', content=b'small-actual-bytes')
        db_export, media, _manifest = self.export_json(self.inst)
        video_path = Path(video.video_file.path)
        original_bytes = video_path.read_bytes()

        archive_path = self.rebuild_archive(db_export, media)
        media_name = next(n for n in media if n.startswith('media/'))
        # The declared (uncompressed) size is patched far above the per-file
        # ceiling; the actual stored bytes stay tiny -- the check must reject
        # based on the zip entry's declared size alone, before opening or
        # reading the member at all.
        _inflate_declared_media_size(archive_path, media_name, restore_apply.MEDIA_MEMBER_SIZE_CEILING + 1)

        upload = RestoreUpload.objects.create(uploaded_by=self.user, status=RestoreUploadStatus.APPLYING)
        get_upload_dir(upload).mkdir(parents=True, exist_ok=True)
        shutil.copy(archive_path, get_upload_path(upload))
        job = self.make_job(self.inst)

        warnings = restore_apply.restore_media(upload, job)

        self.assertEqual(len(warnings), 1)
        self.assertIn('exceeds', warnings[0])
        # Never opened/written to: the file on disk is exactly as it was.
        self.assertEqual(video_path.read_bytes(), original_bytes)

    def test_path_traversal_in_recorded_filename_is_blocked(self):
        patient = self.make_patient(self.inst, baby_name='Traversal', bht='MED-3')
        video = self.make_video(patient, name='safe.mp4', content=b'x')
        db_export, _media, _manifest = self.export_json(self.inst)
        rec = next(r for r in db_export['video.video'] if r['pk'] == video.pk)
        rec['fields']['video_file'] = '../../evil.mp4'
        # The archive must actually contain a member at that traversal path
        # for `zf.getinfo()` to find it and reach the `safe_join` check --
        # otherwise it is merely "missing", never dangerous.
        media = {'media/../../evil.mp4': b'evil-bytes'}

        upload = RestoreUpload.objects.create(uploaded_by=self.user, status=RestoreUploadStatus.APPLYING)
        get_upload_dir(upload).mkdir(parents=True, exist_ok=True)
        shutil.copy(self.rebuild_archive(db_export, media), get_upload_path(upload))
        job = self.make_job(self.inst)

        # `restore_media` reads the *restored* DB row's file field, not the
        # archive JSON directly -- apply first so the malicious path is what
        # actually ends up on the row.
        restore_apply.apply_restore(upload, job)
        warnings = restore_apply.restore_media(upload, job)
        self.assertEqual(len(warnings), 1)
        self.assertIn('outside the media folder', warnings[0])


# ---------------------------------------------------------------------------
# verify_confirmed (step 2)
# ---------------------------------------------------------------------------

class VerifyConfirmedTest(RestoreApplyTestBase):
    def test_matching_archive_passes(self):
        upload = self.build_and_confirm(self.inst)
        restore_apply.verify_confirmed(upload)  # must not raise

    def test_truncated_staged_archive_fails_the_rehash(self):
        upload = self.build_and_confirm(self.inst)
        path = get_upload_path(upload)
        data = path.read_bytes()
        path.write_bytes(data[: len(data) // 2])
        with self.assertRaises(RestoreError) as cm:
            restore_apply.verify_confirmed(upload)
        self.assertIn('no longer matches', str(cm.exception))

    def test_digest_mismatch_at_reverify_time_is_caught(self):
        upload = self.build_and_confirm(self.inst)
        RestoreUpload.objects.filter(pk=upload.pk).update(
            confirmed_snapshot={**upload.confirmed_snapshot, 'digest': 'a' * 64},
        )
        upload.refresh_from_db()
        with self.assertRaises(RestoreError) as cm:
            restore_apply.verify_confirmed(upload)
        self.assertIn('no longer matches what was confirmed', str(cm.exception))


# ---------------------------------------------------------------------------
# Progress: monotonic, capped
# ---------------------------------------------------------------------------

class ProgressTest(TestCase):
    def test_progress_never_goes_backwards_and_calls_back_only_on_change(self):
        seen = []
        progress = restore_apply.Progress(seen.append)
        progress.report(10)
        progress.report(5)  # ignored: would go backwards
        progress.report(10)  # ignored: no change
        progress.report(50)
        self.assertEqual(seen, [10, 50])

    def test_progress_is_capped_at_99(self):
        seen = []
        progress = restore_apply.Progress(seen.append)
        progress.report(150)
        self.assertEqual(seen, [99])

    def test_span_maps_a_fraction_into_a_sub_range(self):
        seen = []
        progress = restore_apply.Progress(seen.append)
        step = progress.span(20, 50)
        step(0.0)
        step(0.5)
        step(1.0)
        self.assertEqual(seen, [20, 35, 50])


# ---------------------------------------------------------------------------
# Full pipeline via `manage.py run_restore` -- AC-level integration tests
# ---------------------------------------------------------------------------

class RunRestoreHappyPathTest(RestoreApplyTestBase):
    def test_happy_path_preserves_pks_and_timestamps_snapshots_first_and_notifies(self):
        patient = self.make_patient(self.inst, baby_name='Original Name', bht='HP-1')
        video = self.make_video(patient)
        self.make_attachment(patient)
        self.make_problem(patient)
        original_patient_pk = patient.pk
        original_video_pk = video.pk
        # Re-fetch: the export (and later restore) round-trips through the
        # DB's own datetime precision, which is not necessarily identical to
        # the in-memory value `timezone.now()` produced at `.create()` time.
        patient.refresh_from_db()
        original_created_at = patient.created_at
        original_updated_at = patient.updated_at

        other_patient = self.make_patient(self.inst2, baby_name='Other Institution', bht='HP-OTHER')
        other_patient.refresh_from_db()
        other_updated_at = other_patient.updated_at

        upload = self.build_and_confirm(self.inst)

        # Mutate current data after the archive was taken.
        Patient.objects.filter(pk=patient.pk).update(baby_name='Mutated Name')
        video.delete()

        job = self.start(upload)
        job = self.run_restore_command(job)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED)
        self.assertEqual(job.progress_pct, 100)

        snapshot = job.pre_restore_snapshot
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.job_type, BackupJobType.PRE_RESTORE_SNAPSHOT)
        self.assertEqual(snapshot.status, BackupJobStatus.COMPLETED)

        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.APPLIED)
        self.assertFalse(get_upload_path(upload).exists())

        restored = Patient.objects.get(pk=original_patient_pk)
        self.assertEqual(restored.baby_name, 'Original Name')
        self.assertEqual(restored.pk, original_patient_pk)
        # `DjangoJSONEncoder` truncates datetimes to millisecond precision
        # (matches JS `Date.toISOString()`), so the export format itself
        # only round-trips to the millisecond, not the microsecond.
        self.assertEqual(_to_millis(restored.created_at), _to_millis(original_created_at))
        self.assertEqual(_to_millis(restored.updated_at), _to_millis(original_updated_at))
        self.assertTrue(Video.objects.filter(pk=original_video_pk).exists())

        # Untouched: a different institution's data.
        other_patient.refresh_from_db()
        self.assertEqual(other_patient.baby_name, 'Other Institution')
        self.assertEqual(other_patient.updated_at, other_updated_at)

        notif = Notification.objects.get(notification_type=NotificationType.RESTORE_COMPLETED)
        self.assertEqual(notif.recipient, self.user)
        from django.urls import reverse
        self.assertEqual(notif.link, reverse('backup:restore-status', args=[upload.id]))

    def test_snapshot_failure_aborts_before_touching_data(self):
        patient = self.make_patient(self.inst, baby_name='Untouched', bht='SF-1')
        upload = self.build_and_confirm(self.inst)
        job = self.start(upload)

        with mock.patch('backup.restore_apply.create_export', side_effect=RuntimeError('disk exploded')):
            job = self.run_restore_command(job)

        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertIn('disk exploded', job.error_message)
        snapshot = BackupJob.objects.get(job_type=BackupJobType.PRE_RESTORE_SNAPSHOT)
        self.assertEqual(snapshot.status, BackupJobStatus.FAILED)
        self.assertEqual(job.pre_restore_snapshot_id, snapshot.id)
        patient.refresh_from_db()
        self.assertEqual(patient.baby_name, 'Untouched')
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)

    def test_rehash_mismatch_fails_before_any_snapshot(self):
        patient = self.make_patient(self.inst, baby_name='Untouched2', bht='RH-1')
        upload = self.build_and_confirm(self.inst)
        job = self.start(upload)
        data = get_upload_path(upload).read_bytes()
        get_upload_path(upload).write_bytes(data + b'\x00')

        job = self.run_restore_command(job)

        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertEqual(BackupJob.objects.filter(job_type=BackupJobType.PRE_RESTORE_SNAPSHOT).count(), 0)
        patient.refresh_from_db()
        self.assertEqual(patient.baby_name, 'Untouched2')
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)

    def test_apply_failure_rolls_back_and_names_the_snapshot_in_error(self):
        patient = self.make_patient(self.inst, baby_name='RollbackMe', bht='RB-1')
        upload = self.build_and_confirm(self.inst)
        job = self.start(upload)

        with mock.patch('backup.restore_apply.apply_restore', side_effect=RestoreError('kaboom mid apply')):
            job = self.run_restore_command(job)

        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertIn('kaboom mid apply', job.error_message)
        self.assertIsNotNone(job.pre_restore_snapshot_id)
        self.assertIn(str(job.pre_restore_snapshot_id), job.error_message)
        patient.refresh_from_db()
        self.assertEqual(patient.baby_name, 'RollbackMe')
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)

    def test_pending_job_run_twice_is_a_no_op_the_second_time(self):
        upload = self.build_and_confirm(self.inst)
        job = self.start(upload)
        self.run_restore_command(job)
        completed_progress = job.progress_pct
        call_command('run_restore', str(job.id))  # already completed -- must not re-run
        job.refresh_from_db()
        self.assertEqual(job.progress_pct, completed_progress)

    def test_unknown_job_id_raises_command_error(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('run_restore', '999999')


# ---------------------------------------------------------------------------
# Pruning-exemption contract (Epic 3 must honour this)
# ---------------------------------------------------------------------------

class PruningExemptionContractTest(RestoreApplyTestBase):
    def test_pre_restore_snapshot_is_identifiable_and_linked_from_its_restore_job(self):
        upload = self.build_and_confirm(self.inst)
        job = self.start(upload)
        job = self.run_restore_command(job)

        snapshot = job.pre_restore_snapshot
        self.assertEqual(snapshot.job_type, BackupJobType.PRE_RESTORE_SNAPSHOT)
        # Epic 3's pruning must be able to find every snapshot still in use
        # by asking each restore job, not by inferring it from job_type alone.
        self.assertIn(job, snapshot.restores_using_snapshot.all())


# ---------------------------------------------------------------------------
# Applying blocks cancel (the reverse -- applying blocks a new upload -- is
# a view-level test in test_restore_views.py)
# ---------------------------------------------------------------------------

class ApplyingCannotBeCancelledTest(RestoreApplyTestBase):
    def test_can_cancel_is_false_while_applying(self):
        upload = self.build_and_confirm(self.inst)
        self.start(upload)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.APPLYING)
        self.assertFalse(restore_preview.can_cancel(upload))

    def test_applied_upload_also_cannot_be_cancelled(self):
        upload = self.build_and_confirm(self.inst)
        job = self.start(upload)
        self.run_restore_command(job)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.APPLIED)
        self.assertFalse(restore_preview.can_cancel(upload))


# ---------------------------------------------------------------------------
# run_restore / apply_restore with an ExportFormatError (Story 2.4 review)
# ---------------------------------------------------------------------------

class RunRestoreExportFormatErrorTest(RestoreApplyTestBase):
    def confirmed_upload_with_export(self, db_export, filename='bad.zip'):
        """A genuinely validated + confirmed upload whose `db_export.json` is
        `db_export` (validation only hashes it, so a preflight-level defect
        survives to the run)."""
        path = self.archive_path(filename)
        build_archive(
            path, db_export=json.dumps(db_export).encode('utf-8'),
            manifest_overrides={'institutions': [self.inst.slug]},
        )
        return self.stage_and_confirm(path, allow_unverified=True, filename=filename)

    def assert_failed_with(self, job, upload, expected_text, patient=None, baby_name=None):
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertIn(expected_text, job.error_message)
        self.assertNotIn('unexpected error', job.error_message)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        if patient is not None:
            patient.refresh_from_db()
            self.assertEqual(patient.baby_name, baby_name)

    def test_unknown_model_key_fails_the_job_with_the_specific_message(self):
        patient = self.make_patient(self.inst, baby_name='Untouched', bht='EF-1')
        upload = self.confirmed_upload_with_export(self.skeleton(**{'some.bogus_model': []}))
        job = self.run_restore_command(self.start(upload))
        self.assert_failed_with(job, upload, 'unknown model key', patient, 'Untouched')

    def test_duplicate_pk_fails_the_job_with_the_specific_message(self):
        patient = self.make_patient(self.inst, baby_name='Untouched', bht='EF-2')
        upload = self.confirmed_upload_with_export(self.skeleton(**{
            'patients.patient': [self.patient_record(1, self.inst.id), self.patient_record(1, self.inst.id)],
        }))
        job = self.run_restore_command(self.start(upload))
        self.assert_failed_with(job, upload, 'Patient 1 appears more than once in db_export.json', patient, 'Untouched')

    def test_export_format_error_during_apply_fails_the_job_with_its_message(self):
        patient = self.make_patient(self.inst, baby_name='Untouched', bht='EF-3')
        upload = self.build_and_confirm(self.inst)
        job = self.start(upload)
        with mock.patch(
            'backup.restore_apply.apply_restore', side_effect=ExportFormatError('a record was refused at load time'),
        ):
            job = self.run_restore_command(job)
        self.assert_failed_with(job, upload, 'a record was refused at load time', patient, 'Untouched')

    def test_apply_restore_reraises_an_export_format_error_unwrapped(self):
        upload = self.build_and_confirm(self.inst)
        job = self.make_job(self.inst)
        with mock.patch(
            'backup.restore_apply._load_records', side_effect=ExportFormatError('record refused'),
        ):
            with self.assertRaises(ExportFormatError) as cm:
                restore_apply.apply_restore(upload, job)
        self.assertEqual(cm.exception.message, 'record refused')


# ---------------------------------------------------------------------------
# A date-scoped upload WITH a match_summary is still not appliable (Story 2.4)
# ---------------------------------------------------------------------------

class DateScopedWithMatchSummaryStillRefusedTest(RestoreApplyTestBase):
    def confirmed_date_scoped_upload(self):
        self.make_patient(self.inst, baby_name='Dated', bht='DS-1')
        db_export, media, _manifest = self.export_json(self.inst)
        path = self.rebuild_archive(db_export, media, manifest_overrides={
            'institutions': [self.inst.slug],
            'date_filter': {'applied': True, 'start': '2026-01-01', 'end': None},
        }, filename='dated.zip')
        sha = sha256_file(path)
        upload = RestoreUpload.objects.create(
            uploaded_by=self.user, original_filename='dated.zip', status=RestoreUploadStatus.VALIDATING,
        )
        get_upload_dir(upload).mkdir(parents=True, exist_ok=True)
        shutil.copy(path, get_upload_path(upload))
        result = restore_validation.validate_restore_archive(get_upload_path(upload), sha, allow_unverified=True)
        self.assertIsNotNone(result.match_summary)
        upload.archive_sha256 = sha
        upload.size_bytes = get_upload_path(upload).stat().st_size
        upload.status = RestoreUploadStatus.VALIDATED
        upload.authenticity = result.authenticity
        upload.source_job_id = result.summary.get('source_job_id')
        upload.manifest_summary = result.summary
        upload.match_summary = result.match_summary
        upload.save()

        preview = restore_preview.build_preview(upload)
        self.assertFalse(preview['blocked'], preview['block_reasons'])
        self.assertIsNotNone(preview['date_scope_match'])
        outcome = restore_preview.confirm_upload(upload.id, self.user, preview['digest'], True)
        self.assertTrue(outcome.ok, outcome.message)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        self.assertIsNotNone(upload.confirmed_snapshot['date_scope_match'])
        return upload

    def test_start_restore_still_refuses_a_confirmed_date_scoped_upload(self):
        upload = self.confirmed_date_scoped_upload()
        outcome = restore_apply.start_restore(upload, self.user, self.inst)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_apply.DATE_SCOPED)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        self.assertEqual(BackupJob.objects.filter(job_type=BackupJobType.RESTORE).count(), 0)

    def test_verify_confirmed_still_refuses_a_confirmed_date_scoped_upload(self):
        upload = self.confirmed_date_scoped_upload()
        with self.assertRaises(RestoreError) as cm:
            restore_apply.verify_confirmed(upload)
        self.assertIn('date-scoped', str(cm.exception))
