"""
backup/tests/test_services.py — Story 1.1, extended by Story 1.4 for the
optional date-range filter.

Covers the export-service half of the I/O matrix: the fixed 13-model plan
and its ordering, institution scoping (no cross-institution leakage), every
model key present even when empty, the media layout inside the archive, the
disk-space pre-check, and (Story 1.4) narrowing `Patient` + its 9
patient-linked models by `created_at`'s date while referral models stay
full-scope.
"""
import json
import shutil
import zipfile
from datetime import date, datetime, time
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from backup.models import BackupJob
from backup.services import (
    _compute_schema_version,
    _model_export_plan,
    create_export,
    estimate_export_size_bytes,
    get_archive_dir,
    has_sufficient_disk_space,
)
from institution.models import Institution
from ndas.custom_codes.choice import BackupJobScopeType, BackupJobStatus, BackupJobType
from patients.models import Attachment, Patient
from problemlist.models import Problem, ProblemAction
from referral.models import ReferralSent
from video.models import Video

User = get_user_model()


def _set_created_at_date(model, pk, d):
    """
    Force a specific `created_at` date on an already-created row, bypassing
    `auto_now_add` (which only fires on INSERT via `.save()`, never on
    `.update()`) -- the same bypass-via-`.update()` pattern already used
    below (`EstimateExportSizeAttachmentZeroTest`) for `file_size`. Noon is
    used (not midnight) so the stored UTC-converted instant never crosses
    into a neighboring day regardless of `TIME_ZONE`.
    """
    dt = timezone.make_aware(datetime.combine(d, time(12, 0)))
    model.objects.filter(pk=pk).update(created_at=dt)

EXPECTED_KEYS_IN_ORDER = [
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
]

STORAGE_OVERRIDE = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)


def make_patient(institution, user, baby_name='Baby One', bht='BHT-001'):
    return Patient.objects.create(
        bht=bht,
        baby_name=baby_name,
        mother_name='Test Mother',
        dob_tob=timezone.now(),
        gender='Male',
        pog_wks=38,
        pog_days=2,
        birth_weight=3000,
        ofc=33,
        mo_delivery='Normal vaginal delivery (NVD)',
        tp_mobile='0711234567',
        institution=institution,
        added_by=user,
    )


@STORAGE_OVERRIDE
class ModelExportPlanTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa1', password='x', position='Administrator', mobile_primary='0770000101',
        )
        self.inst = Institution.objects.create(name='Plan Hosp', slug='plan-hosp', created_by=self.user)

    def test_plan_has_13_models_in_spec_order(self):
        plan = _model_export_plan(self.inst)
        keys = [k for k, _ in plan]
        self.assertEqual(keys, EXPECTED_KEYS_IN_ORDER)

    def test_notification_and_bookmark_excluded(self):
        plan = _model_export_plan(self.inst)
        keys = [k for k, _ in plan]
        self.assertNotIn('referral.notification', keys)
        self.assertNotIn('patients.bookmark', keys)


@STORAGE_OVERRIDE
class CreateExportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa2', password='x', position='Administrator', mobile_primary='0770000102',
        )
        self.inst_a = Institution.objects.create(name='Export Hosp A', slug='export-hosp-a', created_by=self.user)
        self.inst_b = Institution.objects.create(name='Export Hosp B', slug='export-hosp-b', created_by=self.user)

        self.patient_a = make_patient(self.inst_a, self.user, 'Baby A', 'BHT-A-1')
        self.patient_b = make_patient(self.inst_b, self.user, 'Baby B', 'BHT-B-1')

        self.video_a = Video.objects.create(
            patient=self.patient_a,
            title='VidA',
            recorded_on=timezone.now(),
            video_file=SimpleUploadedFile('a.mp4', b'video-a-bytes', content_type='video/mp4'),
            added_by=self.user,
        )
        self.attachment_a = Attachment.objects.create(
            patient=self.patient_a,
            title='AttA',
            attachment_type='document',
            attachment=SimpleUploadedFile('a.txt', b'attachment-a-bytes'),
            added_by=self.user,
        )
        self.problem_a = Problem.objects.create(patient=self.patient_a, name='Asthma', added_by=self.user)
        ProblemAction.objects.create(problem=self.problem_a, action='Reviewed', added_by=self.user)

        self.job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.PENDING,
            scope=self.inst_a,
            triggered_by=self.user,
        )

    def tearDown(self):
        shutil.rmtree(get_archive_dir(self.job), ignore_errors=True)

    def _export(self):
        path, skipped, checksum = create_export(self.job)
        return path

    def _export_with_skipped(self):
        path, skipped, checksum = create_export(self.job)
        return path, skipped

    def _read_db_export(self, path):
        with zipfile.ZipFile(path) as zf:
            return json.loads(zf.read('db_export.json'))

    def _read_manifest(self, path):
        with zipfile.ZipFile(path) as zf:
            return json.loads(zf.read('manifest.json'))

    def test_all_13_keys_present_even_when_empty(self):
        data = self._read_db_export(self._export())
        self.assertEqual(len(data), 13)
        for key in EXPECTED_KEYS_IN_ORDER:
            self.assertIn(key, data)
        # No GMAssessment/HINE/etc seeded for this institution -> present but empty.
        self.assertEqual(data['patients.gmassessment'], [])
        self.assertEqual(data['patients.hineassessment'], [])

    def test_scoped_to_triggering_institution_only(self):
        data = self._read_db_export(self._export())
        patient_pks = [rec['pk'] for rec in data['patients.patient']]
        self.assertIn(self.patient_a.pk, patient_pks)
        self.assertNotIn(self.patient_b.pk, patient_pks)
        self.assertEqual(len(data['patients.patient']), 1)

    def test_related_records_included(self):
        data = self._read_db_export(self._export())
        self.assertEqual(len(data['video.video']), 1)
        self.assertEqual(len(data['patients.attachment']), 1)
        self.assertEqual(len(data['problemlist.problem']), 1)
        self.assertEqual(len(data['problemlist.problemaction']), 1)

    def test_media_copied_with_existing_institution_slug_layout(self):
        path = self._export()
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        self.assertTrue(
            any(n.startswith(f'media/{self.inst_a.slug}/videos/') for n in names), names
        )
        self.assertTrue(
            any(n.startswith(f'media/{self.inst_a.slug}/attachments/') for n in names), names
        )
        # No institution B media leaked into institution A's archive.
        self.assertFalse(any(self.inst_b.slug in n for n in names), names)

    def test_archive_stored_under_backups_dir_not_media_or_static_root(self):
        path = self._export()
        self.assertTrue(str(path).startswith(str(settings.BASE_DIR / 'backups')))
        self.assertNotIn(str(settings.MEDIA_ROOT), str(path))

    def test_progress_callback_reaches_100_range(self):
        seen = []
        create_export(self.job, progress_callback=seen.append)
        self.assertTrue(seen)
        self.assertEqual(max(seen), 100)

    def test_missing_media_file_reported_not_silently_dropped(self):
        # video_a's underlying file is deleted from disk before export runs --
        # the export must still complete, but must report exactly what it skipped
        # (human-approved policy: complete with a warning, not a silent success).
        self.video_a.video_file.delete(save=False)
        path, skipped = self._export_with_skipped()
        self.assertTrue(skipped, "expected the missing video file to be reported as skipped")
        self.assertTrue(any('a.mp4' in s or 'missing' in s for s in skipped), skipped)
        # The archive itself still completes -- everything else still got exported.
        data = self._read_db_export(path)
        self.assertEqual(len(data['video.video']), 1)
        # manifest.json: record_counts still counts the DB row, but checksums
        # has no entry for the skipped (never-written) media file. (Note:
        # storage may rename a colliding filename on write, so match on
        # directory/extension rather than the exact original filename.)
        manifest = self._read_manifest(path)
        self.assertEqual(manifest['record_counts']['video.video'], 1)
        self.assertFalse(
            any(name.startswith('media/') and name.endswith('.mp4') for name in manifest['checksums']),
            manifest['checksums'],
        )
        # The attachment (not deleted) is still a real checksum entry.
        self.assertTrue(
            any(name.startswith('media/') and name.endswith('.txt') for name in manifest['checksums']),
            manifest['checksums'],
        )

    def test_no_skipped_media_when_everything_present(self):
        path, skipped = self._export_with_skipped()
        self.assertEqual(skipped, [])

    def test_duplicate_media_arcname_does_not_silently_overwrite_checksum(self):
        # Two exported media files that resolve to the same "media/<name>"
        # archive member (e.g. a shared/reused underlying file) must not
        # let the second checksum silently overwrite the first in the
        # manifest -- the second occurrence is flagged in skipped_media
        # instead. self.video_a and self.attachment_a give create_export
        # exactly 2 media sources, so this mock's 2-item side_effect lines
        # up with the 2 real calls to `_copy_media_file`.
        with mock.patch('backup.services._copy_media_file') as copy_mock:
            copy_mock.side_effect = [
                (None, 'a' * 64, 'media/shared.mp4'),
                (None, 'b' * 64, 'media/shared.mp4'),
            ]
            path, skipped, checksum = create_export(self.job)
        manifest = self._read_manifest(path)
        self.assertEqual(manifest['checksums']['media/shared.mp4'], 'a' * 64)
        self.assertTrue(
            any('duplicate archive member' in s for s in skipped), skipped,
        )

    def test_scope_none_raises_instead_of_silently_exporting_nothing(self):
        # Story 1.1 never creates a job with scope=None itself; reaching this
        # state means the institution was deleted after job creation (SET_NULL).
        # create_export must fail loudly, not silently scope-less-query.
        self.job.scope = None
        self.job.save(update_fields=['scope'])
        with self.assertRaises(ValueError):
            create_export(self.job)


@STORAGE_OVERRIDE
class ManifestTest(TestCase):
    """
    Story 1.3 -- `manifest.json` is written as a third zip member covering
    schema version, scope, per-model record counts, per-file checksums, and
    generation metadata; `BackupJob.archive_checksum` is the whole-archive
    SHA-256, computed after the zip is closed.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa8', password='x', position='Administrator', mobile_primary='0770000108',
        )
        self.inst_a = Institution.objects.create(name='Manifest Hosp A', slug='manifest-hosp-a', created_by=self.user)
        self.inst_b = Institution.objects.create(name='Manifest Hosp B', slug='manifest-hosp-b', created_by=self.user)
        self.patient_a = make_patient(self.inst_a, self.user, 'Baby ManA', 'BHT-MAN-A')

        self.video_a = Video.objects.create(
            patient=self.patient_a,
            title='VidManA',
            recorded_on=timezone.now(),
            video_file=SimpleUploadedFile('mana.mp4', b'video-mana-bytes', content_type='video/mp4'),
            added_by=self.user,
        )

        self.job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.PENDING,
            scope=self.inst_a,
            triggered_by=self.user,
        )

    def tearDown(self):
        shutil.rmtree(get_archive_dir(self.job), ignore_errors=True)

    def _read_manifest(self, path):
        with zipfile.ZipFile(path) as zf:
            return json.loads(zf.read('manifest.json'))

    def test_manifest_present_with_all_fields_single_scope(self):
        path, skipped, checksum = create_export(self.job)
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        self.assertIn('manifest.json', names)

        manifest = self._read_manifest(path)
        self.assertEqual(manifest['source_job_id'], self.job.id)
        self.assertEqual(manifest['manifest_version'], 1)
        self.assertEqual(manifest['checksum_algorithm'], 'sha256')
        self.assertEqual(manifest['scope_type'], BackupJobScopeType.SINGLE)
        self.assertEqual(manifest['institutions'], [self.inst_a.slug])
        self.assertEqual(manifest['generated_by'], self.user.username)
        self.assertEqual(
            manifest['date_filter'], {"applied": False, "start": None, "end": None},
        )
        self.assertTrue(manifest['generated_at'])
        self.assertEqual(len(manifest['schema_version']), 64)

        for key in EXPECTED_KEYS_IN_ORDER:
            self.assertIn(key, manifest['record_counts'])
        self.assertEqual(manifest['record_counts']['patients.patient'], 1)
        self.assertEqual(manifest['record_counts']['video.video'], 1)
        self.assertEqual(manifest['record_counts']['patients.gmassessment'], 0)

        self.assertIn('db_export.json', manifest['checksums'])
        # Match on directory/extension, not the exact filename -- storage
        # renames a colliding filename on write.
        self.assertTrue(
            any(name.startswith('media/') and name.endswith('.mp4') for name in manifest['checksums']),
            manifest['checksums'],
        )

    def test_manifest_institutions_multi_scope(self):
        job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.PENDING,
            scope_type=BackupJobScopeType.MULTI,
            triggered_by=self.user,
        )
        job.scopes.set([self.inst_a, self.inst_b])
        try:
            path, skipped, checksum = create_export(job)
            manifest = self._read_manifest(path)
            self.assertEqual(manifest['scope_type'], BackupJobScopeType.MULTI)
            self.assertEqual(
                sorted(manifest['institutions']), sorted([self.inst_a.slug, self.inst_b.slug]),
            )
        finally:
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)

    def test_manifest_institutions_system_scope_includes_every_institution(self):
        job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.PENDING,
            scope_type=BackupJobScopeType.SYSTEM,
            triggered_by=self.user,
        )
        try:
            path, skipped, checksum = create_export(job)
            manifest = self._read_manifest(path)
            self.assertEqual(manifest['scope_type'], BackupJobScopeType.SYSTEM)
            # "every institution slug at generation time" -- including any
            # seeded/pre-existing institution (e.g. the data-migration
            # default), not just the two created in this test's setUp.
            expected = sorted(Institution.objects.values_list('slug', flat=True))
            self.assertEqual(sorted(manifest['institutions']), expected)
            self.assertIn(self.inst_a.slug, manifest['institutions'])
            self.assertIn(self.inst_b.slug, manifest['institutions'])
        finally:
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)

    def test_empty_scope_manifest_all_counts_zero_and_only_db_export_checksum(self):
        empty_inst = Institution.objects.create(
            name='Empty Hosp', slug='empty-hosp', created_by=self.user,
        )
        job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.PENDING,
            scope=empty_inst,
            triggered_by=self.user,
        )
        try:
            path, skipped, checksum = create_export(job)
            manifest = self._read_manifest(path)
            for key in EXPECTED_KEYS_IN_ORDER:
                self.assertEqual(manifest['record_counts'][key], 0)
            self.assertEqual(list(manifest['checksums'].keys()), ['db_export.json'])
        finally:
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)

    def test_archive_checksum_matches_independently_hashed_zip(self):
        import hashlib
        path, skipped, checksum = create_export(self.job)
        self.assertEqual(len(checksum), 64)
        hasher = hashlib.sha256()
        with open(path, 'rb') as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
        self.assertEqual(checksum, hasher.hexdigest())

    def test_generated_by_empty_when_triggered_by_is_none(self):
        # triggered_by is on_delete=SET_NULL, null=True -- the triggering
        # user can be deleted between job creation and export running. That
        # must not crash manifest generation; generated_by degrades to "".
        job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.PENDING,
            scope=self.inst_a,
            triggered_by=None,
        )
        try:
            path, skipped, checksum = create_export(job)
            manifest = self._read_manifest(path)
            self.assertEqual(manifest['generated_by'], "")
        finally:
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)

    def test_schema_version_reproducible_across_two_calls(self):
        first = _compute_schema_version()
        second = _compute_schema_version()
        self.assertEqual(first, second)

    def test_schema_version_reproducible_across_two_exports(self):
        job2 = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.PENDING,
            scope=self.inst_a,
            triggered_by=self.user,
        )
        try:
            path1, _skipped1, _checksum1 = create_export(self.job)
            path2, _skipped2, _checksum2 = create_export(job2)
            manifest1 = self._read_manifest(path1)
            manifest2 = self._read_manifest(path2)
            self.assertEqual(manifest1['schema_version'], manifest2['schema_version'])
        finally:
            shutil.rmtree(get_archive_dir(job2), ignore_errors=True)


@STORAGE_OVERRIDE
class DiskSpaceCheckTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa3', password='x', position='Administrator', mobile_primary='0770000103',
        )
        self.inst = Institution.objects.create(name='Disk Hosp', slug='disk-hosp', created_by=self.user)

    def test_sufficient_when_plenty_of_free_space(self):
        with mock.patch('backup.services.shutil.disk_usage') as disk_usage:
            disk_usage.return_value = mock.Mock(free=10 * 1024 ** 4)  # 10TB free
            sufficient, estimated, required, free = has_sufficient_disk_space(self.inst)
        self.assertTrue(sufficient)
        self.assertEqual(free, 10 * 1024 ** 4)

    def test_insufficient_when_free_space_below_margin(self):
        with mock.patch('backup.services.shutil.disk_usage') as disk_usage:
            disk_usage.return_value = mock.Mock(free=1024)  # 1KB free
            sufficient, estimated, required, free = has_sufficient_disk_space(self.inst)
        self.assertFalse(sufficient)


@STORAGE_OVERRIDE
class EstimateExportSizeAttachmentZeroTest(TestCase):
    """A recorded file_size of exactly 0 must be trusted, not treated as unset."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa4', password='x', position='Administrator', mobile_primary='0770000104',
        )
        self.inst = Institution.objects.create(name='Zero Hosp', slug='zero-hosp', created_by=self.user)
        self.patient = make_patient(self.inst, self.user, 'Baby Zero', 'BHT-Z-1')
        self.attachment = Attachment.objects.create(
            patient=self.patient,
            title='ZeroAtt',
            attachment_type='document',
            attachment=SimpleUploadedFile('zero.txt', b'not-actually-empty'),
            added_by=self.user,
        )
        # Force file_size to a recorded 0 via .update() -- bypasses the
        # model's save() override that would recompute it from the real file.
        Attachment.objects.filter(pk=self.attachment.pk).update(file_size=0)

    def test_recorded_zero_is_trusted_not_recomputed_from_disk(self):
        # If the old `file_size or _safe_file_size(...)` bug were still
        # present, a falsy stored 0 would fall through to this live
        # filesystem read instead -- assert that never happens.
        with mock.patch('backup.services._safe_file_size') as safe_size:
            safe_size.return_value = 999_999
            total = estimate_export_size_bytes(self.inst)
        safe_size.assert_not_called()
        self.assertEqual(total, 0)


@STORAGE_OVERRIDE
class ModelExportPlanScopeTest(TestCase):
    """
    Story 1.2 -- `_model_export_plan`'s multi/system-wide scope shapes still
    produce the same fixed, ordered 13-key plan as the single-institution
    shape (Story 1.1, unmodified above).
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa5', password='x', position='Administrator', mobile_primary='0770000105',
        )
        self.inst_a = Institution.objects.create(name='Scope Hosp A', slug='scope-hosp-a', created_by=self.user)
        self.inst_b = Institution.objects.create(name='Scope Hosp B', slug='scope-hosp-b', created_by=self.user)

    def test_system_wide_plan_has_same_13_keys_in_order(self):
        plan = _model_export_plan(system_wide=True)
        keys = [k for k, _ in plan]
        self.assertEqual(keys, EXPECTED_KEYS_IN_ORDER)

    def test_multi_plan_has_same_13_keys_in_order(self):
        plan = _model_export_plan([self.inst_a, self.inst_b])
        keys = [k for k, _ in plan]
        self.assertEqual(keys, EXPECTED_KEYS_IN_ORDER)

    def test_no_scope_info_raises_clear_value_error_not_typeerror(self):
        # Calling with the bare defaults (institution_or_institutions=None,
        # system_wide=False) used to fall through to the "multi" branch and
        # do list(None), raising a confusing TypeError. Must raise a clear
        # ValueError instead.
        with self.assertRaises(ValueError):
            _model_export_plan()
        with self.assertRaises(ValueError):
            estimate_export_size_bytes()
        with self.assertRaises(ValueError):
            has_sufficient_disk_space()


@STORAGE_OVERRIDE
class SystemWideExportTest(TestCase):
    """Story 1.2 -- a system-wide job's export must include every institution's data."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa6', password='x', position='Administrator', mobile_primary='0770000106',
        )
        self.inst_a = Institution.objects.create(name='System Hosp A', slug='system-hosp-a', created_by=self.user)
        self.inst_b = Institution.objects.create(name='System Hosp B', slug='system-hosp-b', created_by=self.user)
        self.patient_a = make_patient(self.inst_a, self.user, 'Baby SysA', 'BHT-SYS-A')
        self.patient_b = make_patient(self.inst_b, self.user, 'Baby SysB', 'BHT-SYS-B')

        self.job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.PENDING,
            scope_type=BackupJobScopeType.SYSTEM,
            triggered_by=self.user,
        )

    def tearDown(self):
        shutil.rmtree(get_archive_dir(self.job), ignore_errors=True)

    def test_system_wide_export_includes_every_institution(self):
        path, skipped, checksum = create_export(self.job)
        with zipfile.ZipFile(path) as zf:
            data = json.loads(zf.read('db_export.json'))
        patient_pks = [rec['pk'] for rec in data['patients.patient']]
        self.assertIn(self.patient_a.pk, patient_pks)
        self.assertIn(self.patient_b.pk, patient_pks)
        self.assertEqual(len(patient_pks), 2)

    def test_system_wide_export_includes_inactive_institution(self):
        # Intentional, documented asymmetry: `multi` mode's institution-
        # *selection* list (BackupScopeForm) only offers active
        # institutions, but a `system`-wide export is a complete snapshot
        # and must NOT filter on Institution.is_active -- an inactive
        # institution's data still belongs in a full system export.
        self.inst_b.is_active = False
        self.inst_b.save(update_fields=['is_active'])

        path, skipped, checksum = create_export(self.job)
        with zipfile.ZipFile(path) as zf:
            data = json.loads(zf.read('db_export.json'))
        patient_pks = [rec['pk'] for rec in data['patients.patient']]
        self.assertIn(self.patient_b.pk, patient_pks, "inactive institution's data was wrongly excluded")
        self.assertEqual(len(patient_pks), 2)


@STORAGE_OVERRIDE
class MultiInstitutionExportTest(TestCase):
    """Story 1.2 -- a multi-institution job's export must include only the selected set."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa7', password='x', position='Administrator', mobile_primary='0770000107',
        )
        self.inst_a = Institution.objects.create(name='Multi Hosp A', slug='multi-hosp-a', created_by=self.user)
        self.inst_b = Institution.objects.create(name='Multi Hosp B', slug='multi-hosp-b', created_by=self.user)
        self.inst_c = Institution.objects.create(name='Multi Hosp C', slug='multi-hosp-c', created_by=self.user)
        self.patient_a = make_patient(self.inst_a, self.user, 'Baby MultiA', 'BHT-MUL-A')
        self.patient_b = make_patient(self.inst_b, self.user, 'Baby MultiB', 'BHT-MUL-B')
        self.patient_c = make_patient(self.inst_c, self.user, 'Baby MultiC', 'BHT-MUL-C')

        self.job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.PENDING,
            scope_type=BackupJobScopeType.MULTI,
            triggered_by=self.user,
        )
        self.job.scopes.set([self.inst_a, self.inst_b])

    def tearDown(self):
        shutil.rmtree(get_archive_dir(self.job), ignore_errors=True)

    def test_multi_export_includes_only_selected_institutions_no_leakage(self):
        path, skipped, checksum = create_export(self.job)
        with zipfile.ZipFile(path) as zf:
            data = json.loads(zf.read('db_export.json'))
        patient_pks = [rec['pk'] for rec in data['patients.patient']]
        self.assertIn(self.patient_a.pk, patient_pks)
        self.assertIn(self.patient_b.pk, patient_pks)
        self.assertNotIn(self.patient_c.pk, patient_pks)
        self.assertEqual(len(patient_pks), 2)

    def test_multi_scope_type_with_empty_scopes_raises(self):
        # Guards against `scopes` being emptied after job creation (the
        # trigger view/form never creates a multi job with an empty set) --
        # create_export must fail loudly rather than silently exporting
        # nothing (mirrors 1.1's scope=None guard for the single case).
        self.job.scopes.clear()
        with self.assertRaises(ValueError):
            create_export(self.job)


@STORAGE_OVERRIDE
class DateFilterModelExportPlanTest(TestCase):
    """
    Story 1.4 -- `_model_export_plan`'s optional `date_start`/`date_end`
    narrows `Patient` (and, via `patient_qs`, its 9 patient-linked models)
    to `created_at`'s date falling in `[date_start, date_end]`; referral
    models are never date-narrowed, always full institution-scope.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa9', password='x', position='Administrator', mobile_primary='0770000109',
        )
        self.inst = Institution.objects.create(name='DateFilter Hosp', slug='datefilter-hosp', created_by=self.user)

        self.patient_before = make_patient(self.inst, self.user, 'Baby Before', 'BHT-DF-BEFORE')
        self.patient_start = make_patient(self.inst, self.user, 'Baby Start', 'BHT-DF-START')
        self.patient_mid = make_patient(self.inst, self.user, 'Baby Mid', 'BHT-DF-MID')
        self.patient_end = make_patient(self.inst, self.user, 'Baby End', 'BHT-DF-END')
        self.patient_after = make_patient(self.inst, self.user, 'Baby After', 'BHT-DF-AFTER')

        _set_created_at_date(Patient, self.patient_before.pk, date(2020, 6, 1))
        _set_created_at_date(Patient, self.patient_start.pk, date(2020, 6, 10))
        _set_created_at_date(Patient, self.patient_mid.pk, date(2020, 6, 15))
        _set_created_at_date(Patient, self.patient_end.pk, date(2020, 6, 20))
        _set_created_at_date(Patient, self.patient_after.pk, date(2020, 6, 30))

        # A video attached to the excluded (out-of-range) patient_before --
        # narrowing must exclude it too via patient_qs, not just Patient itself.
        self.video_before = Video.objects.create(
            patient=self.patient_before, title='VidBefore', recorded_on=timezone.now(),
            video_file=SimpleUploadedFile('before.mp4', b'x'), added_by=self.user,
        )
        self.video_mid = Video.objects.create(
            patient=self.patient_mid, title='VidMid', recorded_on=timezone.now(),
            video_file=SimpleUploadedFile('mid.mp4', b'x'), added_by=self.user,
        )

        # A referral tied to the out-of-range patient_before -- must still
        # be exported in full regardless of the date filter (spec: referral
        # models never date-narrowed). `to_clinician`/`from_clinician` are
        # set (not left null) because ReferralSent's post_save signal
        # (referral/signals.py: notify_referral_received) creates a
        # Notification with recipient=instance.to_clinician -- a null
        # recipient trips a NOT NULL constraint inside the signal, which
        # poisons this test's atomic transaction even though the signal
        # itself swallows the exception.
        self.referral_sent = ReferralSent.objects.create(
            from_institution=self.inst, to_institution=self.inst, institution=self.inst,
            patient=self.patient_before, initial_message='Referral msg',
            from_clinician=self.user, to_clinician=self.user, added_by=self.user,
        )

    def _plan_dict(self, **kwargs):
        return dict(_model_export_plan(self.inst, **kwargs))

    def _patient_pks(self, plan, key='patients.patient'):
        return set(plan[key].values_list('pk', flat=True))

    def test_no_date_filter_includes_every_patient(self):
        # Both bounds omitted -- byte-for-byte the same as pre-1.4 behavior.
        plan = self._plan_dict()
        self.assertEqual(
            self._patient_pks(plan),
            {self.patient_before.pk, self.patient_start.pk, self.patient_mid.pk,
             self.patient_end.pk, self.patient_after.pk},
        )

    def test_full_range_inclusive_both_bounds(self):
        plan = self._plan_dict(date_start=date(2020, 6, 10), date_end=date(2020, 6, 20))
        self.assertEqual(
            self._patient_pks(plan),
            {self.patient_start.pk, self.patient_mid.pk, self.patient_end.pk},
        )

    def test_open_ended_start_only(self):
        plan = self._plan_dict(date_start=date(2020, 6, 10), date_end=None)
        self.assertEqual(
            self._patient_pks(plan),
            {self.patient_start.pk, self.patient_mid.pk, self.patient_end.pk, self.patient_after.pk},
        )

    def test_open_ended_end_only(self):
        plan = self._plan_dict(date_start=None, date_end=date(2020, 6, 20))
        self.assertEqual(
            self._patient_pks(plan),
            {self.patient_before.pk, self.patient_start.pk, self.patient_mid.pk, self.patient_end.pk},
        )

    def test_patient_linked_model_narrowed_via_shared_patient_qs(self):
        # video_before's patient falls outside the range -- must be excluded
        # even though Video itself carries no `created_at` date filter of
        # its own; it's narrowed relative to the already date-scoped
        # `patient_qs` (spec: "applied to Patient.created_at's date").
        plan = self._plan_dict(date_start=date(2020, 6, 10), date_end=date(2020, 6, 20))
        video_pks = set(plan['video.video'].values_list('pk', flat=True))
        self.assertEqual(video_pks, {self.video_mid.pk})
        self.assertNotIn(self.video_before.pk, video_pks)

    def test_referral_models_unaffected_by_date_filter(self):
        # A date range that excludes patient_before (the referral's own
        # patient) must NOT exclude the referral itself -- referral models
        # stay full institution-scope in every scope/date combination.
        plan = self._plan_dict(date_start=date(2020, 6, 10), date_end=date(2020, 6, 20))
        referral_pks = set(plan['referral.referralsent'].values_list('pk', flat=True))
        self.assertIn(self.referral_sent.pk, referral_pks)

    def test_no_date_filter_referral_plan_unchanged(self):
        # Sanity check: referral querysets are identical with/without a date
        # filter -- they're built from institution scope alone.
        with_filter = self._plan_dict(date_start=date(2020, 6, 10), date_end=date(2020, 6, 20))
        without_filter = self._plan_dict()
        self.assertEqual(
            set(with_filter['referral.referralsent'].values_list('pk', flat=True)),
            set(without_filter['referral.referralsent'].values_list('pk', flat=True)),
        )


@STORAGE_OVERRIDE
class DateFilterWithMultiAndSystemScopeTest(TestCase):
    """
    Story 1.4 -- the date filter must compose correctly with Story 1.2's
    `multi` and `system` scope shapes, not just `single`. Both scope shapes
    resolve `patient_qs` once (institution scope, then optional date
    narrowing) and the 9 patient-linked models follow it via
    `patient__in=patient_qs`, so scope and date must narrow *together*.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa12', password='x', position='Administrator', mobile_primary='0770000112',
        )
        self.inst_a = Institution.objects.create(name='DF Multi A', slug='df-multi-a', created_by=self.user)
        self.inst_b = Institution.objects.create(name='DF Multi B', slug='df-multi-b', created_by=self.user)
        self.inst_c = Institution.objects.create(name='DF Multi C', slug='df-multi-c', created_by=self.user)

        # In-range and out-of-range patient for each institution.
        self.a_in = make_patient(self.inst_a, self.user, 'A In', 'BHT-DFM-A-IN')
        self.a_out = make_patient(self.inst_a, self.user, 'A Out', 'BHT-DFM-A-OUT')
        self.b_in = make_patient(self.inst_b, self.user, 'B In', 'BHT-DFM-B-IN')
        self.b_out = make_patient(self.inst_b, self.user, 'B Out', 'BHT-DFM-B-OUT')
        self.c_in = make_patient(self.inst_c, self.user, 'C In', 'BHT-DFM-C-IN')
        for patient, when in (
            (self.a_in, date(2022, 3, 10)), (self.a_out, date(2022, 5, 10)),
            (self.b_in, date(2022, 3, 12)), (self.b_out, date(2022, 5, 12)),
            (self.c_in, date(2022, 3, 14)),
        ):
            _set_created_at_date(Patient, patient.pk, when)

        self.video_a_in = Video.objects.create(
            patient=self.a_in, title='VidAIn', recorded_on=timezone.now(),
            video_file=SimpleUploadedFile('df_a_in.mp4', b'0123456789'), added_by=self.user,
        )
        self.video_a_out = Video.objects.create(
            patient=self.a_out, title='VidAOut', recorded_on=timezone.now(),
            video_file=SimpleUploadedFile('df_a_out.mp4', b'0123456789ABCDEFGHIJ'), added_by=self.user,
        )
        self.video_c_in = Video.objects.create(
            patient=self.c_in, title='VidCIn', recorded_on=timezone.now(),
            video_file=SimpleUploadedFile('df_c_in.mp4', b'0123456789'), added_by=self.user,
        )

        self.march = dict(date_start=date(2022, 3, 1), date_end=date(2022, 3, 31))

    def _pks(self, plan, key):
        return set(plan[key].values_list('pk', flat=True))

    def test_multi_scope_with_date_range_narrows_by_both(self):
        plan = dict(_model_export_plan([self.inst_a, self.inst_b], **self.march))
        # Only the in-range patients of the two selected institutions:
        # not the out-of-range ones, and not institution C's in-range one.
        self.assertEqual(self._pks(plan, 'patients.patient'), {self.a_in.pk, self.b_in.pk})
        self.assertEqual(self._pks(plan, 'video.video'), {self.video_a_in.pk})

    def test_system_scope_with_date_range_narrows_across_every_institution(self):
        plan = dict(_model_export_plan(system_wide=True, **self.march))
        self.assertEqual(
            self._pks(plan, 'patients.patient'), {self.a_in.pk, self.b_in.pk, self.c_in.pk},
        )
        self.assertEqual(
            self._pks(plan, 'video.video'), {self.video_a_in.pk, self.video_c_in.pk},
        )

    def test_multi_scope_without_date_filter_unchanged(self):
        # Regression guard: no date bounds => Story 1.2's multi behavior.
        plan = dict(_model_export_plan([self.inst_a, self.inst_b]))
        self.assertEqual(
            self._pks(plan, 'patients.patient'),
            {self.a_in.pk, self.a_out.pk, self.b_in.pk, self.b_out.pk},
        )

    def test_multi_scope_estimate_excludes_out_of_range_media(self):
        full = estimate_export_size_bytes([self.inst_a, self.inst_b])
        narrowed = estimate_export_size_bytes([self.inst_a, self.inst_b], **self.march)
        self.assertGreater(full, narrowed)
        self.assertGreater(narrowed, 0)

    def test_system_scope_estimate_excludes_out_of_range_media(self):
        full = estimate_export_size_bytes(system_wide=True)
        narrowed = estimate_export_size_bytes(system_wide=True, **self.march)
        self.assertGreater(full, narrowed)
        self.assertGreater(narrowed, 0)


@STORAGE_OVERRIDE
class DateFilterEstimateSizeTest(TestCase):
    """
    Story 1.4 -- `estimate_export_size_bytes`/`has_sufficient_disk_space`
    resolve the same institution+date `patient_qs` as `_model_export_plan`,
    so a date-filtered job's disk-space estimate excludes media belonging to
    patients the filter would exclude.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa10', password='x', position='Administrator', mobile_primary='0770000110',
        )
        self.inst = Institution.objects.create(name='Estimate Hosp', slug='estimate-hosp', created_by=self.user)
        self.patient_in = make_patient(self.inst, self.user, 'Baby In', 'BHT-EST-IN')
        self.patient_out = make_patient(self.inst, self.user, 'Baby Out', 'BHT-EST-OUT')
        _set_created_at_date(Patient, self.patient_in.pk, date(2021, 1, 15))
        _set_created_at_date(Patient, self.patient_out.pk, date(2021, 2, 15))

        Video.objects.create(
            patient=self.patient_in, title='VidIn', recorded_on=timezone.now(),
            video_file=SimpleUploadedFile('in.mp4', b'0123456789'), added_by=self.user,
        )
        Video.objects.create(
            patient=self.patient_out, title='VidOut', recorded_on=timezone.now(),
            video_file=SimpleUploadedFile('out.mp4', b'0123456789ABCDEFGHIJ'), added_by=self.user,
        )

    def test_estimate_excludes_media_outside_date_range(self):
        full = estimate_export_size_bytes(self.inst)
        narrowed = estimate_export_size_bytes(
            self.inst, date_start=date(2021, 1, 1), date_end=date(2021, 1, 31),
        )
        self.assertGreater(full, narrowed)
        self.assertGreater(narrowed, 0)

    def test_disk_check_uses_date_narrowed_estimate(self):
        with mock.patch('backup.services.shutil.disk_usage') as disk_usage:
            disk_usage.return_value = mock.Mock(free=10 * 1024 ** 4)
            _sufficient, estimated_full, _req, _free = has_sufficient_disk_space(self.inst)
            _sufficient2, estimated_narrowed, _req2, _free2 = has_sufficient_disk_space(
                self.inst, date_start=date(2021, 1, 1), date_end=date(2021, 1, 31),
            )
        self.assertGreater(estimated_full, estimated_narrowed)


@STORAGE_OVERRIDE
class ManifestDateFilterTest(TestCase):
    """
    Story 1.4 -- `manifest.json`'s `date_filter` key reflects the real
    applied `BackupJob.date_filter_start`/`date_filter_end` values instead
    of Story 1.3's constant "unapplied" stub.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa11', password='x', position='Administrator', mobile_primary='0770000111',
        )
        self.inst = Institution.objects.create(name='ManifestDF Hosp', slug='manifestdf-hosp', created_by=self.user)
        self.patient = make_patient(self.inst, self.user, 'Baby MF', 'BHT-MF-1')
        _set_created_at_date(Patient, self.patient.pk, date(2022, 3, 10))

    def _read_manifest(self, path):
        with zipfile.ZipFile(path) as zf:
            return json.loads(zf.read('manifest.json'))

    def _make_job(self, date_filter_start=None, date_filter_end=None):
        return BackupJob.objects.create(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.PENDING,
            scope=self.inst,
            triggered_by=self.user,
            date_filter_start=date_filter_start,
            date_filter_end=date_filter_end,
        )

    def test_full_range_reflected_in_manifest(self):
        job = self._make_job(date(2022, 3, 1), date(2022, 3, 31))
        try:
            path, _skipped, _checksum = create_export(job)
            manifest = self._read_manifest(path)
            self.assertEqual(
                manifest['date_filter'],
                {"applied": True, "start": "2022-03-01", "end": "2022-03-31"},
            )
        finally:
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)

    def test_open_ended_start_only_reflected_in_manifest(self):
        job = self._make_job(date_filter_start=date(2022, 3, 1), date_filter_end=None)
        try:
            path, _skipped, _checksum = create_export(job)
            manifest = self._read_manifest(path)
            self.assertEqual(
                manifest['date_filter'],
                {"applied": True, "start": "2022-03-01", "end": None},
            )
        finally:
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)

    def test_open_ended_end_only_reflected_in_manifest(self):
        job = self._make_job(date_filter_start=None, date_filter_end=date(2022, 3, 31))
        try:
            path, _skipped, _checksum = create_export(job)
            manifest = self._read_manifest(path)
            self.assertEqual(
                manifest['date_filter'],
                {"applied": True, "start": None, "end": "2022-03-31"},
            )
        finally:
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)

    def test_no_filter_still_produces_unapplied_stub_shape(self):
        # No date_filter_start/end set on the job (defaults to null/null,
        # same as every pre-1.4 job) -- byte-for-byte the same shape as
        # Story 1.3's stub.
        job = self._make_job()
        try:
            path, _skipped, _checksum = create_export(job)
            manifest = self._read_manifest(path)
            self.assertEqual(
                manifest['date_filter'], {"applied": False, "start": None, "end": None},
            )
        finally:
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)
