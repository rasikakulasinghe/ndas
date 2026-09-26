"""
backup/tests/test_restore_import.py -- Story 2.5

The date-scoped (additive) restore: `backup/restore_import.py` driven through
the real `manage.py run_restore` pipeline. Archives are real exports of real
domain objects; the source patients are then deleted (so validation classifies
them as the import-set) and the archive is re-staged as a date-scoped one.
"""
import gc
import hashlib
import json
import os
import shutil
import sqlite3
import zipfile
from pathlib import Path
from unittest import mock

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.serializers.base import DeserializationError, DeserializedObject
from django.db import DataError, IntegrityError, InterfaceError, OperationalError, connection
from django.template.loader import render_to_string
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from backup import restore_apply, restore_import, restore_validation
from backup.models import BackupJob, RestoreUpload
from backup.restore_apply import RESTORE_MODEL_KEYS, ExportFormatError, RestoreError
from backup.restore_import import ImportFailure
from backup.restore_validation import get_upload_dir, get_upload_path
from backup.tests.restore_helpers import build_archive
from backup.tests.test_restore_apply import EXPORT_KEYS_ORDER, RestoreApplyTestBase, _to_millis
from institution.models import Institution
from ndas.custom_codes.choice import (
    BackupJobStatus,
    BackupJobType,
    NotificationType,
    RestoreUploadStatus,
    UserType,
)
from patients.models import (
    Attachment, CDICRecord, DiagnosisList, GeneralPaediatricAssessment, GMAssessment, HINEAssessment, IndicationsForGMA,
    Patient,
)
from problemlist.models import Problem, ProblemAction
from referral.models import Notification, ReferralSent
from video.models import Video

SECURITY_LOGGER = 'django.security.restore'
DATE_FILTER = {'applied': True, 'start': '2026-01-01', 'end': None}
GPA_TEXT = dict(
    current_problems='cp', physical_examination='pe', investigation_summary='is',
    prescribed_medications='pm', next_plan='np',
)


class ImportTestBase(RestoreApplyTestBase):
    def setUp(self):
        super().setUp()
        self.diagnosis = DiagnosisList.objects.create(abr='ABN', title='Abnormal', description='d')
        self.indication = IndicationsForGMA.objects.create(title='Prematurity IM', level='High')

    # ---- builders ----

    def make_full_patient(self, name, bht, video_content=b'video-of-%s', **kwargs):
        patient = self.make_patient(self.inst, baby_name=name, bht=bht, **kwargs)
        patient.indecation_for_gma.add(self.indication)
        video = self.make_video(
            patient, name=f'{bht}.mp4',
            content=(video_content % name.encode()) if b'%s' in video_content else video_content,
        )
        gm = GMAssessment.objects.create(
            patient=patient, video_file=video, date_of_assessment=timezone.now(),
            diagnosis_conclusion='ABNORMAL', added_by=self.user,
        )
        gm.diagnosis.add(self.diagnosis)
        self.make_attachment(patient, name=f'{bht}.txt', content=b'attachment-of-' + name.encode())
        HINEAssessment.objects.create(
            patient=patient, date_of_assessment=timezone.now(), score=50, assessment_done_by='Dr H',
            added_by=self.user,
        )
        patient.developmental_assessments.create(
            date_of_assessment=timezone.now(), assessment_done_by='Dr D', added_by=self.user,
        )
        CDICRecord.objects.create(patient=patient, assessment_date=timezone.now().date(), added_by=self.user)
        GeneralPaediatricAssessment.objects.create(
            patient=patient, assessment_date=timezone.now(), healthcare_provider='Dr G',
            added_by=self.user, discharged_authorized_by=self.user, **GPA_TEXT,
        )
        self.make_problem(patient)
        return patient

    def delete_patients(self, *patients):
        Patient._base_manager.filter(pk__in=[p.pk for p in patients]).delete()

    def wipe_media(self):
        gc.collect()  # release file handles left open by the fixtures (Windows cannot delete open files)
        shutil.rmtree(self.media_root)

    def dated_upload(self, db_export, media, filename='dated.zip'):
        """`(archive_path, confirmed upload)` for `db_export` re-staged as a
        date-scoped archive of `self.inst`, validated against the DB as it is now."""
        path = self.rebuild_archive(db_export, media, manifest_overrides={
            'institutions': [self.inst.slug], 'date_filter': DATE_FILTER,
        }, filename=filename)
        return path, self.stage_and_confirm(path, allow_unverified=True, filename=filename)

    def run_import(self, upload):
        job = self.run_restore_command(self.start(upload))
        upload.refresh_from_db()
        return job

    def media_files(self):
        root = Path(settings.MEDIA_ROOT)
        return sorted(str(p.relative_to(root)).replace('\\', '/') for p in root.rglob('*') if p.is_file())


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class HappyPathTest(ImportTestBase):
    def test_imports_patients_with_fresh_keys_remapped_references_and_media(self):
        alpha = self.make_full_patient('Alpha', 'IMP-1')
        beta = self.make_full_patient('Beta', 'IMP-2')
        alpha.refresh_from_db()
        old_pks = {alpha.pk, beta.pk}
        old_video_pks = set(Video.objects.values_list('pk', flat=True))
        old_video_names = {v.video_file.name: v.video_file.read() for v in Video.objects.all()}
        db_export, media, _manifest = self.export_json(self.inst)
        self.delete_patients(alpha, beta)
        self.wipe_media()
        path, upload = self.dated_upload(db_export, media)
        self.assertEqual(len(upload.confirmed_snapshot['date_scope_match']['import']), 2)

        job = self.run_import(upload)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        self.assertEqual(job.progress_pct, 100)
        self.assertEqual(job.error_message, '')
        self.assertEqual(job.restore_result, {
            'mode': 'date_scoped', 'imported': 2, 'failed': [], 'skipped': 0, 'excluded': 0, 'media_warnings': [],
        })
        snapshot = job.pre_restore_snapshot
        self.assertEqual(snapshot.job_type, BackupJobType.PRE_RESTORE_SNAPSHOT)
        self.assertEqual(snapshot.status, BackupJobStatus.COMPLETED)
        self.assertEqual(upload.status, RestoreUploadStatus.APPLIED)
        self.assertFalse(get_upload_path(upload).exists())
        self.assertFalse((get_upload_dir(upload) / f'import-spool-{job.id}').exists())

        new = Patient._base_manager.get(bht='IMP-1')
        self.assertNotIn(new.pk, old_pks)
        self.assertEqual(new.institution_id, self.inst.id)
        self.assertEqual(new.baby_name, 'Alpha')
        self.assertEqual(_to_millis(new.created_at), _to_millis(alpha.created_at))
        self.assertEqual(_to_millis(new.updated_at), _to_millis(alpha.updated_at))
        self.assertEqual(new.added_by_id, self.user.id)
        self.assertEqual(list(new.indecation_for_gma.all()), [self.indication])
        self.assertEqual(Patient._base_manager.filter(institution=self.inst).count(), 2)

        video = Video.objects.get(patient=new)
        self.assertNotIn(video.pk, old_video_pks)
        gm = GMAssessment.objects.get(patient=new)
        self.assertEqual(gm.video_file_id, video.pk)
        self.assertEqual(list(gm.diagnosis.all()), [self.diagnosis])
        for model in (HINEAssessment, CDICRecord, GeneralPaediatricAssessment):
            self.assertEqual(model.objects.filter(patient=new).count(), 1, model)
        self.assertEqual(new.developmental_assessments.count(), 1)
        self.assertEqual(Attachment.objects.filter(patient=new).count(), 1)
        problem = Problem.objects.get(patient=new)
        self.assertEqual(ProblemAction.objects.get(problem=problem).action, 'Reviewed')
        gpa = GeneralPaediatricAssessment.objects.get(patient=new)
        self.assertEqual(gpa.discharged_authorized_by_id, self.user.id)

        # Media copied after commit, under the original names, with their bytes.
        self.assertIn(video.video_file.name, old_video_names)
        self.assertEqual((self.media_root / video.video_file.name).read_bytes(), old_video_names[video.video_file.name])

        notification = Notification.objects.get(notification_type=NotificationType.RESTORE_COMPLETED)
        self.assertEqual(notification.title, 'Restore completed')
        self.assertIn('Imported 2, skipped 0, excluded 0, failed 0', notification.body)
        self.assertEqual(notification.link, reverse('backup:restore-status', args=[upload.id]))

    def test_progress_is_monotonic_capped_and_advances_through_the_import(self):
        a = self.make_full_patient('Alpha', 'PG-1')
        b = self.make_full_patient('Beta', 'PG-2')
        db_export, media, _ = self.export_json(self.inst)
        self.delete_patients(a, b)
        _path, upload = self.dated_upload(db_export, media)
        job = self.start(upload)
        seen = []
        restore_import.execute_import(job, progress_callback=seen.append)
        self.assertEqual(seen, sorted(set(seen)))
        self.assertLessEqual(max(seen), 99)
        self.assertGreater(seen[-1], 60)
        self.assertIn(20, seen)
        self.assertIn(50, seen)

    def test_status_page_shows_the_counts_after_applied(self):
        from backup.views import _restore_status_context
        a = self.make_full_patient('Alpha', 'ST-1')
        db_export, media, _ = self.export_json(self.inst)
        self.delete_patients(a)
        _path, upload = self.dated_upload(db_export, media)
        self.run_import(upload)
        html = render_to_string('backup/restore_status_partial.html', _restore_status_context(upload))
        self.assertIn('Imported: 1', html)
        self.assertIn('Skipped: 0', html)
        self.assertIn('Excluded: 0', html)
        self.assertIn('Failed: 0', html)


# ---------------------------------------------------------------------------
# Skip-set, excluded, referral records are never applied
# ---------------------------------------------------------------------------

class PartitionTest(ImportTestBase):
    def test_skip_excluded_and_referral_records_are_never_applied_or_extracted(self):
        keeper = self.make_full_patient('Keeper', 'SK-1')
        new_one = self.make_full_patient('Newcomer', 'NW-1')
        e1 = self.make_patient(self.inst, baby_name='E1', bht='EX-1')
        e2 = self.make_patient(self.inst, baby_name='E2', nnc_no='EX-NNC')
        conflicted = self.make_full_patient('Conflicted', 'CF-1')
        self.make_referral(self.inst, new_one)
        keeper.refresh_from_db()
        keeper_updated = keeper.updated_at
        referral_count = ReferralSent.objects.count()

        db_export, media, _ = self.export_json(self.inst)
        # The conflicted archive patient matches two different existing patients.
        for record in db_export['patients.patient']:
            if record['pk'] == conflicted.pk:
                record['fields']['bht'] = 'EX-1'
                record['fields']['nnc_no'] = 'EX-NNC'
        db_export['patients.patient'] = [r for r in db_export['patients.patient'] if r['pk'] not in (e1.pk, e2.pk)]
        keeper_video = Video.objects.get(patient=keeper)
        keeper_name = keeper_video.video_file.name
        new_files = sorted([
            Video.objects.get(patient=new_one).video_file.name,
            Attachment.objects.get(patient=new_one).attachment.name,
        ])
        media = {**media, f'media/{keeper_name}': b'ARCHIVE-COPY-MUST-NOT-BE-EXTRACTED'}

        self.delete_patients(new_one, conflicted)
        self.wipe_media()
        (self.media_root / keeper_name).parent.mkdir(parents=True, exist_ok=True)
        (self.media_root / keeper_name).write_bytes(b'KEEPER-ORIGINAL')
        keeper_before = b'KEEPER-ORIGINAL'

        _path, upload = self.dated_upload(db_export, media)
        match = upload.confirmed_snapshot['date_scope_match']
        self.assertEqual([e['archive_pk'] for e in match['import']], [new_one.pk])
        self.assertEqual([e['archive_pk'] for e in match['skip']], [keeper.pk])
        self.assertEqual([e['archive_pk'] for e in match['excluded']], [conflicted.pk])

        job = self.run_import(upload)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        self.assertEqual(job.restore_result['imported'], 1)
        self.assertEqual(job.restore_result['skipped'], 1)
        self.assertEqual(job.restore_result['excluded'], 1)
        # Skip-set patient: same row, untouched, and its file is not overwritten or re-extracted.
        keeper.refresh_from_db()
        self.assertEqual(keeper.updated_at, keeper_updated)
        self.assertEqual(Patient._base_manager.filter(bht='SK-1').count(), 1)
        self.assertEqual((self.media_root / keeper_name).read_bytes(), keeper_before)
        # Excluded patient: nothing imported, no media written.
        self.assertFalse(Patient._base_manager.filter(baby_name='Conflicted').exists())
        self.assertFalse([n for n in self.media_files() if 'CF-1' in n])
        # The media folder holds exactly the skip patient's own file plus the two
        # files of the import-set patient (the conflicted patient's and the skip
        # patient's archive copies were never extracted).
        self.assertEqual(self.media_files(), sorted([keeper_name] + new_files))
        # Import-set patient arrived; nothing else did.
        self.assertEqual(Patient._base_manager.filter(baby_name='Newcomer').count(), 1)
        self.assertEqual(Patient._base_manager.filter(institution=self.inst).count(), 4)  # keeper, e1, e2, new
        # No referral rows were created.
        self.assertEqual(ReferralSent.objects.count(), referral_count)

    def test_spooling_writes_only_the_import_sets_records(self):
        keeper = self.make_full_patient('Keeper', 'SP-1')
        new_one = self.make_full_patient('Newcomer', 'SP-2')
        db_export, media, _ = self.export_json(self.inst)
        self.delete_patients(new_one)
        _path, upload = self.dated_upload(db_export, media)
        job = self.start(upload)
        captured = []
        original = restore_import._Spool.add_many

        def _capture(spool, rows):
            captured.extend(rows)
            return original(spool, rows)

        with mock.patch.object(restore_import._Spool, 'add_many', _capture), \
                mock.patch.object(restore_import, 'iter_export_records', wraps=restore_import.iter_export_records) as it:
            restore_import.execute_import(job)
        it.assert_called_once()
        self.assertTrue(captured)
        self.assertEqual({owner for owner, _key, _src, _body in captured}, {new_one.pk})
        keys = {key for _owner, key, _src, _body in captured}
        self.assertNotIn('referral.referralsent', keys)

        # Every one of the skip patient's records (children, problem actions
        # through their problem) exists in the archive and none was spooled.
        keeper_problems = {
            r['pk'] for r in db_export['problemlist.problem'] if r['fields']['patient'] == keeper.pk
        }
        keeper_records = {
            (key, r['pk']) for key in EXPORT_KEYS_ORDER for r in db_export.get(key, [])
            if (key == 'patients.patient' and r['pk'] == keeper.pk)
            or (key == 'problemlist.problemaction' and r['fields'].get('problem') in keeper_problems)
            or (key not in ('patients.patient', 'problemlist.problemaction') and r['fields'].get('patient') == keeper.pk)
        }
        self.assertGreaterEqual(len(keeper_records), 9)
        spooled = {(key, src) for _owner, key, src, _body in captured}
        self.assertFalse(spooled & keeper_records)
        # The spooled body is the record itself, for the same (key, pk).
        for _owner, key, src, body in captured:
            record = json.loads(body)
            self.assertEqual((record['model'], record['pk']), (key, src))

    def test_the_same_record_twice_in_the_import_set_is_refused_while_spooling(self):
        record = self.patient_record(7, self.inst.id)
        problem = {'model': 'problemlist.problem', 'pk': 5, 'fields': {'patient': 7}}
        cases = {
            'patient': self.skeleton(**{'patients.patient': [record, dict(record)]}),
            'problem': self.skeleton(**{'patients.patient': [record], 'problemlist.problem': [problem, dict(problem)]}),
        }
        for label, db_export in cases.items():
            with self.subTest(label):
                upload = self.preflight_upload(db_export, filename=f'dup-{label}.zip')
                spool = restore_import._Spool(str(self.tmp / f'spool-{label}'))
                self.addCleanup(spool.close)
                with self.assertRaises(ExportFormatError) as cm:
                    restore_import._spool_import_set(upload, {7}, spool)
                self.assertIn('more than once', cm.exception.message)

    def test_distinct_records_spool_fine_and_a_duplicate_outside_the_import_set_is_not_looked_at(self):
        db_export = self.skeleton(**{
            'patients.patient': [self.patient_record(7, self.inst.id), self.patient_record(8, self.inst.id)],
            'problemlist.problem': [
                {'model': 'problemlist.problem', 'pk': 5, 'fields': {'patient': 7}},
                {'model': 'problemlist.problem', 'pk': 6, 'fields': {'patient': 7}},
            ],
            'problemlist.problemaction': [
                {'model': 'problemlist.problemaction', 'pk': 1, 'fields': {'problem': 5}},
                {'model': 'problemlist.problemaction', 'pk': 2, 'fields': {'problem': 6}},
            ],
        })
        upload = self.preflight_upload(db_export, filename='distinct.zip')
        spool = restore_import._Spool(str(self.tmp / 'spool-distinct'))
        self.addCleanup(spool.close)
        self.assertEqual(restore_import._spool_import_set(upload, {7}, spool), 5)
        self.assertEqual([key for key, _r in spool.records_for(7)], [
            'patients.patient', 'problemlist.problem', 'problemlist.problem',
            'problemlist.problemaction', 'problemlist.problemaction',
        ])
        self.assertEqual(spool.records_for(8), [])

    def test_empty_import_set_completes_with_nothing_imported(self):
        self.make_full_patient('Keeper', 'EM-1')
        db_export, media, _ = self.export_json(self.inst)
        _path, upload = self.dated_upload(db_export, media)
        self.assertEqual(upload.confirmed_snapshot['date_scope_match']['import'], [])
        before = Patient._base_manager.count()

        with mock.patch.object(restore_import, 'iter_export_records') as stream:
            job = self.run_import(upload)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        self.assertEqual(job.restore_result, {
            'mode': 'date_scoped', 'imported': 0, 'failed': [], 'skipped': 1, 'excluded': 0, 'media_warnings': [],
        })
        self.assertIn('Nothing was imported', job.error_message)
        self.assertIn('skipped or excluded', job.error_message)
        self.assertEqual(upload.status, RestoreUploadStatus.APPLIED)
        self.assertEqual(Patient._base_manager.count(), before)
        # Nothing will change, so no pre-restore snapshot is taken and the archive is not read.
        self.assertIsNone(job.pre_restore_snapshot_id)
        self.assertFalse(BackupJob.objects.filter(job_type=BackupJobType.PRE_RESTORE_SNAPSHOT).exists())
        stream.assert_not_called()
        self.assertFalse(get_upload_path(upload).exists())

    def test_a_problem_action_of_a_skip_set_patient_is_dropped_not_imported(self):
        keeper = self.make_full_patient('Keeper', 'PA-1')
        new_one = self.make_full_patient('Newcomer', 'PA-2')
        db_export, media, _ = self.export_json(self.inst)
        self.assertEqual(len(db_export['problemlist.problemaction']), 2)
        self.delete_patients(new_one)
        self.wipe_media()
        _path, upload = self.dated_upload(db_export, media)
        self.assertEqual([e['archive_pk'] for e in upload.confirmed_snapshot['date_scope_match']['skip']], [keeper.pk])

        job = self.run_import(upload)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        self.assertEqual(job.restore_result['imported'], 1)
        # The keeper's problem/action is unchanged (not duplicated); the new patient got its own.
        self.assertEqual(ProblemAction.objects.count(), 2)
        self.assertEqual(Problem.objects.count(), 2)
        self.assertEqual(ProblemAction.objects.filter(problem__patient=keeper).count(), 1)
        new = Patient._base_manager.get(bht='PA-2')
        self.assertEqual(ProblemAction.objects.filter(problem__patient=new).count(), 1)


# ---------------------------------------------------------------------------
# Per-patient failures
# ---------------------------------------------------------------------------

class PartialFailureTest(ImportTestBase):
    def two_patient_upload(self):
        a = self.make_full_patient('Alpha', 'PF-A')
        b = self.make_full_patient('Beta', 'PF-B')
        db_export, media, _ = self.export_json(self.inst)
        self.delete_patients(a, b)
        self.wipe_media()
        path, upload = self.dated_upload(db_export, media)
        return a, b, path, upload

    def test_one_failing_patient_rolls_back_alone_and_the_run_completes_with_a_warning(self):
        a, b, _path, upload = self.two_patient_upload()
        # Created after validation: B's identifier now collides.
        collider = self.make_patient(self.inst2, baby_name='Collider', bht='PF-B')

        job = self.run_import(upload)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        self.assertEqual(job.restore_result['imported'], 1)
        self.assertEqual(job.restore_result['failed'], [{
            'archive_pk': b.pk, 'identifiers': {'bht': 'PF-B'}, 'reason': restore_import.REASON_CONSTRAINT,
        }])
        self.assertIn(f'archive patient {b.pk} (bht: PF-B)', job.error_message)
        self.assertEqual(upload.status, RestoreUploadStatus.APPLIED)
        self.assertTrue(Patient._base_manager.filter(bht='PF-A', institution=self.inst).exists())
        # B's patient and children rolled back; the pre-existing patient is untouched.
        self.assertEqual(Patient._base_manager.filter(bht='PF-B').count(), 1)
        collider.refresh_from_db()
        self.assertEqual(collider.baby_name, 'Collider')
        self.assertEqual(Video.objects.count(), 1)
        self.assertEqual(Problem.objects.count(), 1)
        self.assertEqual(len([n for n in self.media_files() if 'PF-A' in n and n.endswith('.mp4')]), 1)
        self.assertFalse(any('PF-B' in n for n in self.media_files()))
        notification = Notification.objects.get(notification_type=NotificationType.RESTORE_COMPLETED)
        self.assertEqual(notification.title, 'Restore completed with warnings')
        self.assertIn('failed 1', notification.body)

    def test_status_page_lists_the_failed_patients(self):
        from backup.views import _restore_status_context
        _a, b, _path, upload = self.two_patient_upload()
        self.make_patient(self.inst2, baby_name='Collider', bht='PF-B')
        self.run_import(upload)
        html = render_to_string('backup/restore_status_partial.html', _restore_status_context(upload))
        self.assertIn('Imported: 1', html)
        self.assertIn('Failed: 1', html)
        self.assertIn(f'Archive patient {b.pk}', html)
        self.assertIn('bht: PF-B', html)
        self.assertIn('Restore applied with warnings', html)

    def test_a_collision_gets_the_mapped_reason_and_no_database_text_or_value_in_it(self):
        _a, b, _path, upload = self.two_patient_upload()
        self.make_patient(self.inst2, baby_name='Collider', bht='PF-B')

        with self.assertLogs(SECURITY_LOGGER, level='INFO') as logs:
            job = self.run_import(upload)

        reason = job.restore_result['failed'][0]['reason']
        self.assertEqual(reason, restore_import.REASON_CONSTRAINT)
        self.assertNotIn('PF-B', reason)
        # The raw database message never reaches the record, the job message or the notification ...
        shown = json.dumps(job.restore_result) + job.error_message + Notification.objects.get(
            notification_type=NotificationType.RESTORE_COMPLETED).body
        for raw in ('IntegrityError', 'UNIQUE', 'patients_patient', 'Traceback'):
            self.assertNotIn(raw, shown)
        # ... the identifier value appears only as the patient's identification, not inside a reason.
        self.assertEqual(job.restore_result['failed'][0]['identifiers'], {'bht': 'PF-B'})
        # The full text stays in the server log, together with the run summary.
        text = "\n".join(logs.output)
        self.assertIn(f'archive patient {b.pk} failed and was rolled back', text)
        self.assertIn('IntegrityError', text)
        self.assertIn(
            f'Restore import summary: upload={upload.id} job={job.id} imported=1 failed=1 skipped=0 excluded=0 '
            'media_warnings=0 aborted=False', text,
        )

    def test_import_patient_maps_data_errors_and_lets_environment_errors_propagate(self):
        ctx = restore_import._ImportContext(self.inst)
        record = ('patients.patient', {'model': 'patients.patient', 'pk': 1, 'fields': {'baby_name': 'Secret Name'}})
        cases = {
            ValueError('Secret Name is bad'): restore_import.REASON_INVALID,
            TypeError('Secret Name'): restore_import.REASON_INVALID,
            KeyError('Secret Name'): restore_import.REASON_INVALID,
            ObjectDoesNotExist('Secret Name'): restore_import.REASON_INVALID,
            ValidationError('Secret Name'): restore_import.REASON_INVALID,
            DeserializationError('Secret Name'): restore_import.REASON_INVALID,
            DataError('Secret Name too long'): restore_import.REASON_INVALID,
            IntegrityError('Secret Name duplicated'): restore_import.REASON_CONSTRAINT,
        }
        for error, reason in cases.items():
            with self.subTest(type(error).__name__):
                with mock.patch.object(restore_import.serializers, 'deserialize', side_effect=error):
                    with self.assertRaises(ImportFailure) as cm:
                        restore_import._import_patient(1, [record], ctx)
                self.assertEqual(cm.exception.reason, reason)
                self.assertNotIn('Secret', cm.exception.reason)
                self.assertIn('Secret Name', cm.exception.detail)  # server log only
        for error in (OperationalError('down'), InterfaceError('closed'), OSError('disk'), MemoryError()):
            with self.subTest(type(error).__name__):
                with mock.patch.object(restore_import.serializers, 'deserialize', side_effect=error):
                    with self.assertRaises(type(error)):
                        restore_import._import_patient(1, [record], ctx)

    def test_the_connection_level_constraint_check_failing_for_one_patient_fails_only_that_patient(self):
        _a, _b, _path, upload = self.two_patient_upload()
        first, second = [e['archive_pk'] for e in upload.confirmed_snapshot['date_scope_match']['import']]
        bht = {a_.pk: a_.bht for a_ in (_a, _b)}
        real_check = connection.check_constraints
        calls = []

        def check(table_names=None):
            calls.append(table_names)
            if len(calls) == 2:  # patient B's transaction only
                raise IntegrityError('dangling reference in Secret')
            return real_check(table_names=table_names)

        with mock.patch.object(restore_import, 'connection', mock.Mock(check_constraints=check)):
            job = self.run_import(upload)

        self.assertEqual(len(calls), 2)
        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        self.assertEqual(job.restore_result['imported'], 1)
        self.assertEqual([f['archive_pk'] for f in job.restore_result['failed']], [second])
        self.assertEqual(job.restore_result['failed'][0]['reason'], restore_import.REASON_CONSTRAINT)
        # The second patient and everything of it rolled back; the first is complete.
        self.assertFalse(Patient._base_manager.filter(bht=bht[second]).exists())
        self.assertTrue(Patient._base_manager.filter(bht=bht[first]).exists())
        self.assertEqual(Video.objects.count(), 1)
        self.assertEqual(GMAssessment.objects.count(), 1)
        self.assertEqual(Attachment.objects.count(), 1)
        self.assertEqual(Problem.objects.count(), 1)
        self.assertEqual(ProblemAction.objects.count(), 1)

    def test_every_attempted_patient_failing_fails_the_job_and_returns_the_upload_to_confirmed(self):
        a = self.make_full_patient('Alpha', 'AF-A')
        db_export, media, _ = self.export_json(self.inst)
        self.delete_patients(a)
        self.wipe_media()
        _path, upload = self.dated_upload(db_export, media)
        self.make_patient(self.inst2, baby_name='Collider', bht='AF-A')
        count = Patient._base_manager.count()

        job = self.run_import(upload)

        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertIn('None of the 1 patient(s) could be imported', job.error_message)
        self.assertIn(f'archive patient {a.pk}', job.error_message)
        self.assertIsNone(job.restore_result)
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        self.assertTrue(get_upload_path(upload).exists())
        self.assertEqual(Patient._base_manager.count(), count)
        self.assertEqual(self.media_files(), [])
        self.assertTrue(Notification.objects.filter(notification_type=NotificationType.RESTORE_FAILED).exists())

    def test_gm_assessment_whose_video_is_not_in_the_patients_map_fails_that_patient(self):
        a = self.make_full_patient('Alpha', 'GM-A')
        b = self.make_full_patient('Beta', 'GM-B')
        db_export, media, _ = self.export_json(self.inst)
        b_video = Video.objects.get(patient=b).pk
        for record in db_export['patients.gmassessment']:
            if record['fields']['patient'] == a.pk:
                record['fields']['video_file'] = b_video
        self.delete_patients(a, b)
        self.wipe_media()
        _path, upload = self.dated_upload(db_export, media)

        job = self.run_import(upload)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        self.assertEqual([f['archive_pk'] for f in job.restore_result['failed']], [a.pk])
        self.assertIn('video that is not this patient', job.restore_result['failed'][0]['reason'])
        self.assertFalse(Patient._base_manager.filter(bht='GM-A').exists())
        self.assertTrue(Patient._base_manager.filter(bht='GM-B').exists())

    def test_missing_m2m_reference_row_fails_that_patient(self):
        a = self.make_full_patient('Alpha', 'M2-A')
        b = self.make_full_patient('Beta', 'M2-B')
        db_export, media, _ = self.export_json(self.inst)
        for record in db_export['patients.patient']:
            if record['pk'] == a.pk:
                record['fields']['indecation_for_gma'] = [999999]
        self.delete_patients(a, b)
        self.wipe_media()
        _path, upload = self.dated_upload(db_export, media)

        job = self.run_import(upload)

        self.assertEqual([f['archive_pk'] for f in job.restore_result['failed']], [a.pk])
        self.assertIn('IndicationsForGMA 999999', job.restore_result['failed'][0]['reason'])
        self.assertFalse(Patient._base_manager.filter(bht='M2-A').exists())
        self.assertTrue(Patient._base_manager.filter(bht='M2-B').exists())

    def test_retry_by_re_upload_reclassifies_imported_patients_as_skip_set(self):
        a, b, path, upload = self.two_patient_upload()
        collider = self.make_patient(self.inst2, baby_name='Collider', bht='PF-B')
        job = self.run_import(upload)
        self.assertEqual(job.restore_result['imported'], 1)
        collider.delete()

        retry = self.stage_and_confirm(path, allow_unverified=True, filename='retry.zip')
        match = retry.confirmed_snapshot['date_scope_match']
        self.assertEqual([e['archive_pk'] for e in match['skip']], [a.pk])
        self.assertEqual([e['archive_pk'] for e in match['import']], [b.pk])

        job2 = self.run_import(retry)

        self.assertEqual(job2.status, BackupJobStatus.COMPLETED, job2.error_message)
        self.assertEqual(job2.restore_result['imported'], 1)
        self.assertEqual(job2.restore_result['skipped'], 1)
        self.assertEqual(Patient._base_manager.filter(bht='PF-A').count(), 1)
        self.assertEqual(Patient._base_manager.filter(bht='PF-B', institution=self.inst).count(), 1)


# ---------------------------------------------------------------------------
# Unexpected (non-data) errors: once a patient has committed the upload never
# goes back to `confirmed`
# ---------------------------------------------------------------------------

class UnexpectedErrorTest(ImportTestBase):
    def three_patient_upload(self):
        patients = [self.make_full_patient(name, f'UE-{name[0]}') for name in ('Alpha', 'Beta', 'Gamma')]
        db_export, media, _ = self.export_json(self.inst)
        self.delete_patients(*patients)
        self.wipe_media()
        _path, upload = self.dated_upload(db_export, media)
        # The archive's own import order decides which patient is "first".
        self.order = [
            e['identifiers']['bht'] for e in upload.confirmed_snapshot['date_scope_match']['import']
        ]
        self.assertEqual(sorted(self.order), ['UE-A', 'UE-B', 'UE-G'])
        return upload

    def name_of(self, position):
        return {'UE-A': 'Alpha', 'UE-B': 'Beta', 'UE-G': 'Gamma'}[self.order[position]]

    def records_for_failing_on(self, call_number, error):
        real = restore_import._Spool.records_for
        calls = []

        def records_for(spool, patient_pk):
            calls.append(patient_pk)
            if len(calls) == call_number:
                raise error
            return real(spool, patient_pk)

        return records_for

    def assert_aborted_after_the_first_commit(self, job, upload, error_name):
        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        self.assertEqual(upload.status, RestoreUploadStatus.APPLIED)  # NOT confirmed: the partition is stale
        result = job.restore_result
        self.assertEqual(result['imported'], 1)
        self.assertIs(result['aborted'], True)
        self.assertEqual(result['not_attempted'], 2)
        self.assertEqual(result['failed'], [{
            'archive_pk': None, 'identifiers': {},
            'reason': f'the import stopped early: {error_name}; 2 patient(s) were not imported',
        }])
        self.assertIn('The import stopped early', job.error_message)
        self.assertFalse(get_upload_path(upload).exists())
        # Only the first patient (and its media) is there.
        first = self.order[0]
        self.assertTrue(Patient._base_manager.filter(bht=first, institution=self.inst).exists())
        self.assertFalse(Patient._base_manager.filter(bht__in=self.order[1:]).exists())
        self.assertEqual(Video.objects.count(), 1)
        self.assertEqual(len([n for n in self.media_files() if first in n]), 2)
        self.assertEqual(len(self.media_files()), 2)
        notification = Notification.objects.get(notification_type=NotificationType.RESTORE_COMPLETED)
        self.assertEqual(notification.title, 'Restore completed with warnings')
        self.assertIn('Imported 1, skipped 0, excluded 0, failed 0.', notification.body)
        self.assertIn('stopped early: 2 patient(s)', notification.body)
        # The same upload can never be started again.
        outcome = restore_apply.start_restore(upload, self.user, self.inst)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.code, restore_apply.NOT_CONFIRMED)

    def assert_failed_and_confirmed_with_nothing_changed(self, job, upload):
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        self.assertIsNone(job.restore_result)
        self.assertFalse(Patient._base_manager.filter(bht__startswith='UE-').exists())
        self.assertEqual(self.media_files(), [])
        self.assertTrue(get_upload_path(upload).exists())
        self.assertFalse((get_upload_dir(upload) / f'import-spool-{job.id}').exists())
        self.assertTrue(Notification.objects.filter(notification_type=NotificationType.RESTORE_FAILED).exists())

    def test_an_unexpected_error_after_the_first_commit_completes_with_warnings_and_applies(self):
        upload = self.three_patient_upload()
        error = RuntimeError('spool exploded on Secret Name')
        with mock.patch.object(restore_import._Spool, 'records_for', self.records_for_failing_on(2, error)):
            job = self.run_import(upload)
        self.assert_aborted_after_the_first_commit(job, upload, 'RuntimeError')
        shown = json.dumps(job.restore_result) + job.error_message
        self.assertNotIn('exploded', shown)
        self.assertNotIn('Secret', shown)

    def test_the_same_error_before_any_commit_fails_the_job_and_returns_the_upload_to_confirmed(self):
        upload = self.three_patient_upload()
        error = RuntimeError('spool exploded on Secret Name')
        with mock.patch.object(restore_import._Spool, 'records_for', self.records_for_failing_on(1, error)):
            job = self.run_import(upload)
        self.assert_failed_and_confirmed_with_nothing_changed(job, upload)
        self.assertIn('could not run (RuntimeError)', job.error_message)
        self.assertNotIn('exploded', job.error_message)
        # Nothing committed, so the same confirmed upload can be started again.
        self.assertTrue(restore_apply.start_restore(upload, self.user, self.inst).ok)

    def test_an_operational_error_aborts_the_run_instead_of_failing_every_remaining_patient(self):
        upload = self.three_patient_upload()
        real_save = DeserializedObject.save

        def save(deserialized, *args, **kwargs):
            if getattr(deserialized.object, 'baby_name', None) == self.name_of(1):
                raise OperationalError('database is locked')
            return real_save(deserialized, *args, **kwargs)

        with mock.patch.object(DeserializedObject, 'save', save):
            job = self.run_import(upload)

        self.assert_aborted_after_the_first_commit(job, upload, 'OperationalError')
        # One abort entry, not one failure per remaining patient.
        self.assertEqual(len(job.restore_result['failed']), 1)

    def test_an_operational_error_on_the_first_patient_fails_the_job_and_changes_nothing(self):
        upload = self.three_patient_upload()
        real_save = DeserializedObject.save

        def save(deserialized, *args, **kwargs):
            if getattr(deserialized.object, 'baby_name', None) == self.name_of(0):
                raise OperationalError('database is locked')
            return real_save(deserialized, *args, **kwargs)

        with mock.patch.object(DeserializedObject, 'save', save):
            job = self.run_import(upload)

        self.assert_failed_and_confirmed_with_nothing_changed(job, upload)
        self.assertIn('could not run (OperationalError)', job.error_message)

    def test_a_spool_that_cannot_be_created_fails_the_job_and_leaves_nothing_behind(self):
        upload = self.three_patient_upload()
        with mock.patch.object(restore_import.sqlite3, 'connect', side_effect=sqlite3.OperationalError('no spool')):
            job = self.run_import(upload)
        self.assert_failed_and_confirmed_with_nothing_changed(job, upload)
        self.assertIn('could not run (OperationalError)', job.error_message)

    def test_a_spool_that_fails_while_being_built_closes_its_connection_and_removes_its_directory(self):
        directory = self.tmp / 'half-built-spool'
        conn = mock.MagicMock()
        conn.execute.side_effect = sqlite3.OperationalError('disk full')
        with mock.patch.object(restore_import.sqlite3, 'connect', return_value=conn):
            with self.assertRaises(sqlite3.OperationalError):
                restore_import._Spool(str(directory))
        conn.close.assert_called_once_with()
        self.assertFalse(directory.exists())


# ---------------------------------------------------------------------------
# Foreign keys: users
# ---------------------------------------------------------------------------

class UserReferenceTest(ImportTestBase):
    def test_missing_users_become_null_and_present_users_are_kept_never_the_restoring_admin(self):
        gone = make_user('gone_user', '0770000699')
        kept = make_user('kept_user', '0770000698')
        patient = self.make_patient(self.inst, baby_name='Users', bht='US-1', added_by=gone)
        Patient._base_manager.filter(pk=patient.pk).update(last_edit_by=kept)
        problem = Problem.objects.create(patient=patient, name='Asthma', added_by=gone)
        ProblemAction.objects.create(problem=problem, action='Seen', added_by=kept, performed_by=gone)
        GeneralPaediatricAssessment.objects.create(
            patient=patient, assessment_date=timezone.now(), healthcare_provider='Dr U',
            added_by=kept, discharged_authorized_by=gone, **GPA_TEXT,
        )
        db_export, media, _ = self.export_json(self.inst)
        self.delete_patients(patient)
        gone.delete()
        _path, upload = self.dated_upload(db_export, media)

        job = self.run_import(upload)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        self.assertEqual(job.restore_result['imported'], 1)
        new = Patient._base_manager.get(bht='US-1')
        self.assertIsNone(new.added_by_id)
        self.assertEqual(new.last_edit_by_id, kept.id)
        action = ProblemAction.objects.get(problem__patient=new)
        self.assertIsNone(action.performed_by_id)
        self.assertEqual(action.added_by_id, kept.id)
        self.assertIsNone(GeneralPaediatricAssessment.objects.get(patient=new).discharged_authorized_by_id)
        self.assertNotIn(self.user.id, {new.added_by_id, new.last_edit_by_id, action.performed_by_id})


def make_user(username, mobile):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.create_user(
        username=username, password='x', position='Administrator', mobile_primary=mobile,
        user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
    )


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------

class MediaTest(ImportTestBase):
    def test_an_existing_file_is_never_overwritten_and_the_row_is_repointed(self):
        a = self.make_full_patient('Alpha', 'MD-1')
        db_export, media, _ = self.export_json(self.inst)
        name = Video.objects.get(patient=a).video_file.name
        attachment_name = Attachment.objects.get(patient=a).attachment.name
        self.delete_patients(a)
        self.wipe_media()
        (self.media_root / name).parent.mkdir(parents=True, exist_ok=True)
        (self.media_root / name).write_bytes(b'EXISTING-PATIENTS-FILE')
        _path, upload = self.dated_upload(db_export, media)

        job = self.run_import(upload)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        self.assertEqual((self.media_root / name).read_bytes(), b'EXISTING-PATIENTS-FILE')
        new = Patient._base_manager.get(bht='MD-1')
        video = Video.objects.get(patient=new)
        self.assertNotEqual(video.video_file.name, name)
        self.assertEqual((self.media_root / video.video_file.name).read_bytes(), media[f'media/{name}'])
        self.assertTrue(video.video_file.name.endswith('.mp4'))
        self.assertEqual(job.restore_result['media_warnings'], [])
        # Only the two archive files plus the pre-existing one; no temp leftovers.
        self.assertFalse([n for n in self.media_files() if n.endswith('.tmp')])
        self.assertIn(attachment_name, self.media_files())

    def test_a_missing_media_member_leaves_the_patient_imported_with_a_warning(self):
        a = self.make_full_patient('Alpha', 'MM-1')
        db_export, media, _ = self.export_json(self.inst)
        video_name = Video.objects.get(patient=a).video_file.name
        media = {k: v for k, v in media.items() if k != f'media/{video_name}'}
        self.delete_patients(a)
        self.wipe_media()
        _path, upload = self.dated_upload(db_export, media)

        job = self.run_import(upload)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        self.assertEqual(job.restore_result['imported'], 1)
        self.assertEqual(job.restore_result['failed'], [])
        self.assertTrue(any('missing from the archive' in w for w in job.restore_result['media_warnings']))
        self.assertIn('media warning', job.error_message)
        self.assertEqual(upload.status, RestoreUploadStatus.APPLIED)
        self.assertTrue(Patient._base_manager.filter(bht='MM-1').exists())

    def test_place_media_reports_a_checksum_mismatch_and_leaves_no_temp_file(self):
        path = self.archive_path('mm.zip')
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('media/a.txt', b'bytes')
        with zipfile.ZipFile(path) as zf:
            warning = restore_import._place_media(
                zf, {'media/a.txt': 'ab' * 32}, 'patients.attachment', 'attachment', 1, 'a.txt',
            )
        self.assertIn('checksum mismatch', warning)
        self.assertEqual(self.media_files(), [])

    def test_place_media_refuses_a_path_outside_the_media_folder(self):
        # The manifest carries the REAL checksum, so only the path guard can refuse it.
        path = self.archive_path('esc.zip')
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('media/../evil.txt', b'bytes')
        with zipfile.ZipFile(path) as zf:
            warning = restore_import._place_media(
                zf, {'media/../evil.txt': hashlib.sha256(b'bytes').hexdigest()},
                'patients.attachment', 'attachment', 1, '../evil.txt',
            )
        self.assertIn('outside the media folder', warning)
        self.assertEqual(list(self.base_dir.rglob('evil.txt')), [])
        self.assertEqual(self.media_files(), [])

    # ---- helpers for the row-level media tests ----

    def attachment_row(self, bht, content=b'row-original'):
        """A real Attachment row whose file already exists on disk (so it
        stands for another patient's file at its archived path)."""
        patient = self.make_patient(self.inst, baby_name=bht, bht=bht)
        attachment = self.make_attachment(patient, name=f'{bht}.txt', content=content)
        name = attachment.attachment.name
        del attachment
        gc.collect()  # release the fixture's file handle (Windows cannot unlink an open file)
        return Attachment.objects.get(patient=patient), name

    def archive_with(self, name, content, checksum=None):
        path = self.archive_path('member.zip')
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr(f'media/{name}', content)
        checksums = {f'media/{name}': checksum or hashlib.sha256(content).hexdigest()}
        return path, checksums

    def place(self, path, checksums, attachment, name):
        with zipfile.ZipFile(path) as zf:
            return restore_import._place_media(
                zf, checksums, 'patients.attachment', 'attachment', attachment.pk, name,
            )

    def row_file(self, attachment):
        return Attachment.objects.get(pk=attachment.pk).attachment.name

    def test_a_lost_race_for_the_name_writes_a_fresh_name_and_never_overwrites(self):
        attachment, name = self.attachment_row('RC-1')
        (self.media_root / name).unlink()
        path, checksums = self.archive_with(name, b'ARCHIVE-BYTES')
        real_link = os.link
        raced = []

        def racing_link(src, dst, *args, **kwargs):
            if not raced:  # another writer takes the name between our check and our placement
                raced.append(dst)
                Path(dst).write_bytes(b'RACE-WINNER')
                raise FileExistsError(dst)
            return real_link(src, dst, *args, **kwargs)

        with mock.patch.object(restore_import.os, 'link', racing_link):
            warning = self.place(path, checksums, attachment, name)

        self.assertIsNone(warning)
        self.assertEqual(len(raced), 1)
        self.assertEqual((self.media_root / name).read_bytes(), b'RACE-WINNER')
        fresh = self.row_file(attachment)
        self.assertNotEqual(fresh, name)
        self.assertEqual((self.media_root / fresh).read_bytes(), b'ARCHIVE-BYTES')
        self.assertFalse([n for n in self.media_files() if n.endswith('.tmp')])

    def test_placement_falls_back_to_a_look_up_when_hard_links_are_unsupported(self):
        attachment, name = self.attachment_row('FB-1')
        foreign = self.media_root / name
        path, checksums = self.archive_with(name, b'ARCHIVE-BYTES')
        with mock.patch.object(restore_import.os, 'link', side_effect=OSError('links unsupported')):
            warning = self.place(path, checksums, attachment, name)  # a file exists: fresh name
            self.assertIsNone(warning)
            self.assertEqual(foreign.read_bytes(), b'row-original')
            fresh = self.row_file(attachment)
            self.assertNotEqual(fresh, name)
            self.assertEqual((self.media_root / fresh).read_bytes(), b'ARCHIVE-BYTES')
            foreign.unlink()
            (self.media_root / fresh).unlink()
            warning = self.place(path, checksums, attachment, name)  # nothing there: the archived name
            self.assertIsNone(warning)
            self.assertEqual(foreign.read_bytes(), b'ARCHIVE-BYTES')
        self.assertFalse([n for n in self.media_files() if n.endswith('.tmp')])

    def test_a_failed_copy_onto_an_existing_foreign_file_clears_the_rows_file_and_leaves_that_file_alone(self):
        for label, member_bytes, checksum, expected in (
            ('checksum', b'ARCHIVE-BYTES', 'ab' * 32, 'checksum mismatch'),
            ('missing', None, None, 'missing from the archive'),
        ):
            with self.subTest(label):
                attachment, name = self.attachment_row(f'FC-{label}')
                foreign = self.media_root / name
                if member_bytes is None:
                    path = self.archive_path('empty.zip')
                    with zipfile.ZipFile(path, 'w') as zf:
                        zf.writestr('media/other.txt', b'x')
                    checksums = {}
                else:
                    path, checksums = self.archive_with(name, member_bytes, checksum=checksum)

                warning = self.place(path, checksums, attachment, name)

                self.assertIn(expected, warning)
                self.assertIn('the archived file name is already used by another file, so this row has no file', warning)
                self.assertEqual(self.row_file(attachment), '')
                self.assertEqual(foreign.read_bytes(), b'row-original')
                self.assertFalse([n for n in self.media_files() if n.endswith('.tmp')])

    def test_a_failed_copy_with_nothing_at_the_archived_path_keeps_the_archived_name(self):
        attachment, name = self.attachment_row('FK-1')
        (self.media_root / name).unlink()
        path, checksums = self.archive_with(name, b'ARCHIVE-BYTES', checksum='cd' * 32)
        warning = self.place(path, checksums, attachment, name)
        self.assertIn('checksum mismatch', warning)
        self.assertNotIn('no file', warning)
        self.assertEqual(self.row_file(attachment), name)  # dangles exactly as in the source
        self.assertFalse((self.media_root / name).exists())

    def test_a_write_error_onto_an_existing_foreign_file_also_clears_the_row(self):
        attachment, name = self.attachment_row('WE-1')
        path, checksums = self.archive_with(name, b'ARCHIVE-BYTES')
        with mock.patch.object(restore_import.os, 'link', side_effect=PermissionError('read-only')):
            with mock.patch.object(restore_import.os, 'replace', side_effect=PermissionError('read-only')):
                warning = self.place(path, checksums, attachment, name)
        self.assertIn('could not be written', warning)
        self.assertNotIn('read-only', warning)   # no exception text in what the user sees
        self.assertIn('so this row has no file', warning)
        self.assertEqual(self.row_file(attachment), '')
        self.assertEqual((self.media_root / name).read_bytes(), b'row-original')

    def test_a_row_that_cannot_be_repointed_leaves_no_orphan_file(self):
        attachment, name = self.attachment_row('RP-1')
        path, checksums = self.archive_with(name, b'ARCHIVE-BYTES')
        with mock.patch.object(Attachment._base_manager.__class__, 'filter', side_effect=RuntimeError('db gone')):
            warning = self.place(path, checksums, attachment, name)
        self.assertIn('could not be recorded (RuntimeError)', warning)
        self.assertEqual(self.media_files(), [name])   # only the foreign file: no fresh-named orphan

    def test_media_warning_reaches_the_notification_and_the_job_message(self):
        a = self.make_full_patient('Alpha', 'MW-1')
        db_export, media, _ = self.export_json(self.inst)
        video_name = Video.objects.get(patient=a).video_file.name
        media = {k: v for k, v in media.items() if k != f'media/{video_name}'}
        self.delete_patients(a)
        self.wipe_media()
        _path, upload = self.dated_upload(db_export, media)
        job = self.run_import(upload)
        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        notification = Notification.objects.get(notification_type=NotificationType.RESTORE_COMPLETED)
        self.assertEqual(notification.title, 'Restore completed with warnings')
        self.assertEqual(notification.body, 'Imported 1, skipped 0, excluded 0, failed 0. 1 media warning(s).')
        self.assertIn('1 media warning(s)', job.error_message)

    def test_snapshot_skipped_media_is_a_media_warning_everywhere(self):
        a = self.make_full_patient('Alpha', 'SS-1')
        db_export, media, _ = self.export_json(self.inst)
        self.delete_patients(a)
        self.wipe_media()
        _path, upload = self.dated_upload(db_export, media)
        real_export = restore_apply.create_export

        def create_export(snapshot_job, progress_callback=None):
            archive_path, _skipped, checksum = real_export(snapshot_job, progress_callback=progress_callback)
            return archive_path, ['gone.mp4: file missing on disk'], checksum

        with mock.patch('backup.restore_apply.create_export', create_export):
            job = self.run_import(upload)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        self.assertEqual(job.restore_result['imported'], 1)
        warnings = job.restore_result['media_warnings']
        self.assertEqual(len(warnings), 1)
        self.assertIn(f'the pre-restore snapshot (job {job.pre_restore_snapshot_id}) skipped 1 media file(s)', warnings[0])
        self.assertIn('1 media warning(s)', job.error_message)
        self.assertIn('skipped 1 media file(s)', job.error_message)
        notification = Notification.objects.get(notification_type=NotificationType.RESTORE_COMPLETED)
        self.assertEqual(notification.title, 'Restore completed with warnings')
        self.assertIn('1 media warning(s)', notification.body)
        self.assertEqual(upload.status, RestoreUploadStatus.APPLIED)


# ---------------------------------------------------------------------------
# Failures before any patient is touched
# ---------------------------------------------------------------------------

class PreImportFailureTest(ImportTestBase):
    def confirmed(self):
        a = self.make_full_patient('Alpha', 'PI-1')
        db_export, media, _ = self.export_json(self.inst)
        self.delete_patients(a)
        self.wipe_media()
        _path, upload = self.dated_upload(db_export, media)
        return db_export, media, upload

    def assert_untouched_and_confirmed(self, job, upload):
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        self.assertFalse(Patient._base_manager.filter(bht='PI-1').exists())
        self.assertEqual(self.media_files(), [])

    def test_institution_id_differing_from_the_snapshot_fails_before_any_patient(self):
        _e, _m, upload = self.confirmed()
        job = self.start(upload)
        Institution.objects.filter(pk=self.inst.pk).update(slug='moved-away')
        Institution.objects.create(name='Impostor', slug=self.inst.slug, created_by=self.user)
        job = self.run_restore_command(job)
        upload.refresh_from_db()
        self.assert_untouched_and_confirmed(job, upload)
        self.assertIn('its id changed', job.error_message)
        self.assertEqual(BackupJob.objects.filter(job_type=BackupJobType.PRE_RESTORE_SNAPSHOT).count(), 0)

    def test_resolve_target_refuses_a_missing_institution_and_an_id_mismatch(self):
        _e, _m, upload = self.confirmed()
        job = self.start(upload)
        match = dict(upload.confirmed_snapshot['date_scope_match'])
        self.assertEqual(restore_import._resolve_target(job, match), self.inst)
        with self.assertRaises(RestoreError):
            restore_import._resolve_target(job, {**match, 'target_institution_id': self.inst.id + 1000})
        with self.assertRaises(RestoreError):
            restore_import._resolve_target(job, {**match, 'institution_slug': 'no-such-slug'})

    def test_partition_is_read_only_from_the_confirmed_snapshot(self):
        _e, _m, upload = self.confirmed()
        # Changing the stored match_summary after confirmation must not matter:
        # the import reads confirmed_snapshot['date_scope_match'] alone.
        RestoreUpload.objects.filter(pk=upload.pk).update(match_summary={'skip': [], 'import': [], 'excluded': []})
        upload.refresh_from_db()
        _match, import_pks = restore_import._read_partition(upload)
        self.assertEqual(len(import_pks), 1)
        broken = dict(upload.confirmed_snapshot)
        broken['date_scope_match'] = {'skip': [], 'import': [{'archive_pk': 'x'}], 'excluded': []}
        upload.confirmed_snapshot = broken
        with self.assertRaises(RestoreError):
            restore_import._read_partition(upload)

    def test_a_malformed_partition_is_refused(self):
        _e, _m, upload = self.confirmed()
        good = upload.confirmed_snapshot['date_scope_match']
        pk = good['import'][0]['archive_pk']
        other = {'archive_pk': pk + 1000, 'identifiers': {}}
        cases = {
            'import and skip': {**good, 'skip': [{'archive_pk': pk, 'matched_fields': [], 'identifiers': {}}]},
            'import and excluded': {**good, 'excluded': [{'archive_pk': pk, 'reason': 'ambiguous-conflict'}]},
            'not a record (import)': {**good, 'import': [*good['import'], 'x']},
            'not a record (skip)': {**good, 'skip': [other, 5]},
            'not a record (excluded)': {**good, 'excluded': [None]},
            'duplicate import': {**good, 'import': [*good['import'], dict(good['import'][0])]},
        }
        for label, match in cases.items():
            with self.subTest(label):
                upload.confirmed_snapshot = {**upload.confirmed_snapshot, 'date_scope_match': match}
                with self.assertRaises(RestoreError):
                    restore_import._read_partition(upload)
        # The unmodified partition is fine, and skip/excluded entries may hold other patients.
        upload.confirmed_snapshot = {
            **upload.confirmed_snapshot, 'date_scope_match': {**good, 'skip': [other], 'excluded': [{'archive_pk': pk + 2000}]},
        }
        self.assertEqual(restore_import._read_partition(upload)[1], [pk])

    def test_identifiers_come_from_the_confirmed_import_entries_and_only_the_known_names(self):
        match = {'import': [
            {'archive_pk': 1, 'identifiers': {'bht': 'B-1', 'pin': 'P-1', 'items': 'x', 'ptc_no': None}},
            {'archive_pk': 2, 'identifiers': 'not a dict'},
            {'archive_pk': 3},
        ]}
        self.assertEqual(restore_import._identifiers_by_pk(match), {1: {'bht': 'B-1', 'pin': 'P-1'}, 2: {}, 3: {}})

    def test_digest_or_archive_change_since_confirm_fails_at_the_rehash_before_any_snapshot(self):
        _e, _m, upload = self.confirmed()
        job = self.start(upload)
        get_upload_path(upload).write_bytes(get_upload_path(upload).read_bytes() + b'\x00')
        job = self.run_restore_command(job)
        upload.refresh_from_db()
        self.assert_untouched_and_confirmed(job, upload)
        self.assertEqual(BackupJob.objects.filter(job_type=BackupJobType.PRE_RESTORE_SNAPSHOT).count(), 0)

    def test_snapshot_failure_fails_the_job_and_imports_nothing(self):
        _e, _m, upload = self.confirmed()
        job = self.start(upload)
        with mock.patch('backup.restore_apply.create_export', side_effect=RuntimeError('disk exploded')):
            job = self.run_restore_command(job)
        upload.refresh_from_db()
        self.assert_untouched_and_confirmed(job, upload)
        self.assertIn('disk exploded', job.error_message)
        self.assertIsNotNone(job.pre_restore_snapshot_id)

    def test_a_malformed_export_fails_after_the_snapshot_and_before_any_patient(self):
        db_export, media, _upload = self.confirmed()
        db_export = {**db_export, 'some.bogus_model': []}
        _path, upload = self.dated_upload(db_export, media, filename='bogus.zip')
        job = self.run_import(upload)
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertIn('unknown model key', job.error_message)
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        self.assertFalse(Patient._base_manager.filter(bht='PI-1').exists())
        self.assertFalse((get_upload_dir(upload) / f'import-spool-{job.id}').exists())

    def test_the_snapshot_is_taken_before_the_first_patient_is_imported(self):
        _e, _m, upload = self.confirmed()
        job = self.start(upload)
        order = []
        real_snapshot = restore_apply.take_snapshot
        real_import = restore_import._import_patient

        def _snapshot(*args, **kwargs):
            order.append('snapshot')
            return real_snapshot(*args, **kwargs)

        def _patient(*args, **kwargs):
            order.append('patient')
            return real_import(*args, **kwargs)

        with mock.patch('backup.restore_apply.take_snapshot', _snapshot), \
                mock.patch.object(restore_import, '_import_patient', _patient):
            restore_import.execute_import(job)
        self.assertEqual(order, ['snapshot', 'patient'])

    def test_import_patient_failure_reason_is_an_import_failure(self):
        ctx = restore_import._ImportContext(self.inst)
        with self.assertRaises(ImportFailure):
            restore_import._import_patient(1, [], ctx)


# ---------------------------------------------------------------------------
# Every foreign key of a restorable model is one the import remaps or nulls
# ---------------------------------------------------------------------------

class ForeignKeyGuardTest(TestCase):
    """`_import_patient` remaps `patient`, `problem`, `video_file`, sets
    `institution` and nulls missing users. A new foreign key on a restorable
    model that it does not handle would import with a dangling or wrong
    reference: this test fails until `_import_patient` (and this list) handle it."""

    HANDLED = {'patient': Patient, 'problem': Problem, 'video_file': Video, 'institution': Institution}

    def test_every_foreign_key_of_every_restorable_model_is_handled_by_the_import(self):
        user_model = get_user_model()
        checked = 0
        for key in RESTORE_MODEL_KEYS:
            model = apps.get_model(key)
            for f in model._meta.concrete_fields:
                if not (f.many_to_one or f.one_to_one):
                    continue
                checked += 1
                with self.subTest(f'{key}.{f.name}'):
                    handled = f.related_model is user_model or self.HANDLED.get(f.name) is f.related_model
                    self.assertTrue(
                        handled,
                        f"{key}.{f.name} -> {f.related_model.__name__} is not remapped or nulled by "
                        "restore_import._import_patient: extend it before restoring this model.",
                    )
        self.assertGreater(checked, 10)


# ---------------------------------------------------------------------------
# The start view launches the date-scoped run
# ---------------------------------------------------------------------------

@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class StartViewTest(ImportTestBase):
    def test_a_confirmed_date_scoped_upload_with_a_usable_match_starts_and_launches_run_restore(self):
        a = self.make_full_patient('Alpha', 'SV-1')
        db_export, media, _ = self.export_json(self.inst)
        self.delete_patients(a)
        self.wipe_media()
        _path, upload = self.dated_upload(db_export, media)
        client = Client()
        client.force_login(self.user)
        session = client.session
        session['active_institution_id'] = self.inst.id
        session.save()

        with mock.patch('backup.views.subprocess.Popen') as popen:
            response = client.post(reverse('backup:restore-start', args=[upload.id]))

        self.assertRedirects(response, reverse('backup:restore-status', args=[upload.id]), fetch_redirect_response=False)
        job = BackupJob.objects.get(job_type=BackupJobType.RESTORE)
        self.assertEqual(job.status, BackupJobStatus.PENDING)
        self.assertEqual(job.restore_upload_id, upload.id)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.APPLYING)
        popen.assert_called_once()
        args = popen.call_args[0][0]
        self.assertIn('run_restore', args)
        self.assertIn(str(job.id), args)
        # Nothing was imported by the view itself; the launched command does that.
        self.assertFalse(Patient._base_manager.filter(bht='SV-1').exists())
        job = self.run_restore_command(job)
        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        self.assertEqual(job.restore_result['imported'], 1)
        self.assertTrue(Patient._base_manager.filter(bht='SV-1').exists())


# ---------------------------------------------------------------------------
# Status page wording
# ---------------------------------------------------------------------------

class StatusPageTest(ImportTestBase):
    def render(self, status, progress=0, date_scoped=True, snapshot=False, job_status=BackupJobStatus.RUNNING,
               result=None, error_message=''):
        from backup.views import _restore_status_context
        confirmed = {'snapshot_version': 1, 'digest': 'a' * 64}
        if date_scoped:
            confirmed['date_filter'] = DATE_FILTER
        upload = RestoreUpload.objects.create(
            uploaded_by=self.user, original_filename='a.zip', status=status, confirmed_at=timezone.now(),
            confirmed_by=self.user, confirmed_snapshot=confirmed,
        )
        job = BackupJob.objects.create(
            job_type=BackupJobType.RESTORE, status=job_status, scope=self.inst, trigger_institution=self.inst,
            triggered_by=self.user, restore_upload=upload, progress_pct=progress, restore_result=result,
            error_message=error_message,
        )
        if snapshot:
            job.pre_restore_snapshot = BackupJob.objects.create(
                job_type=BackupJobType.PRE_RESTORE_SNAPSHOT, status=BackupJobStatus.RUNNING, scope=self.inst,
            )
            job.save()
        return render_to_string('backup/restore_status_partial.html', _restore_status_context(upload))

    def test_date_scoped_progress_wording_follows_the_steps(self):
        applying = RestoreUploadStatus.APPLYING
        steps = (
            (5, False, 'Re-checking the archive.'),
            (20, False, 'Taking a snapshot of the current data before changing anything.'),
            (35, True, 'Taking a snapshot of the current data (job '),
            (49, False, 'Taking a snapshot of the current data'),
            (50, True, "Reading the archive's new patients."),
            (59, False, "Reading the archive's new patients."),
            (60, True, "Importing the archive's new patients one at a time"),
            (95, True, "Importing the archive's new patients one at a time"),
        )
        for progress, snapshot, text in steps:
            with self.subTest(progress=progress, snapshot=snapshot):
                html = self.render(applying, progress, snapshot=snapshot)
                self.assertIn(text, html)
                self.assertNotIn('Applying the archive', html)
                self.assertNotIn('Checking the archive against this system', html)

    def test_full_scope_progress_wording_is_unchanged(self):
        applying = RestoreUploadStatus.APPLYING
        self.assertIn('Re-checking the archive.', self.render(applying, 10, date_scoped=False))
        self.assertIn('Taking a snapshot', self.render(applying, 30, date_scoped=False, snapshot=True))
        self.assertIn('Checking the archive against this system.', self.render(applying, 55, date_scoped=False))
        self.assertIn('Applying the archive.', self.render(applying, 70, date_scoped=False))
        self.assertIn('Copying the archive', self.render(applying, 95, date_scoped=False))

    def test_a_partial_restore_result_renders_with_zero_counts(self):
        html = self.render(
            RestoreUploadStatus.APPLIED, job_status=BackupJobStatus.COMPLETED, result={'mode': 'date_scoped'},
        )
        for text in ('Imported: 0', 'Skipped: 0', 'Excluded: 0', 'Failed: 0'):
            self.assertIn(text, html)

    def test_an_early_stop_is_shown_and_not_counted_as_a_failed_patient(self):
        result = {
            'mode': 'date_scoped', 'imported': 1, 'skipped': 0, 'excluded': 0, 'media_warnings': [],
            'aborted': True, 'not_attempted': 2,
            'failed': [{
                'archive_pk': None, 'identifiers': {},
                'reason': 'the import stopped early: RuntimeError; 2 patient(s) were not imported',
            }],
        }
        html = self.render(
            RestoreUploadStatus.APPLIED, job_status=BackupJobStatus.COMPLETED, result=result,
            error_message='Restore completed with warnings: ...',
        )
        self.assertIn('Imported: 1', html)
        self.assertIn('Failed: 0', html)
        self.assertIn('stopped early because of an unexpected error: 2 patient(s) were not imported', html)
        self.assertIn('the import stopped early: RuntimeError', html)
        self.assertNotIn('Archive patient None', html)
