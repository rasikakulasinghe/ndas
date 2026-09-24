"""
backup/tests/test_restore_import.py -- Story 2.5

The date-scoped (additive) restore: `backup/restore_import.py` driven through
the real `manage.py run_restore` pipeline. Archives are real exports of real
domain objects; the source patients are then deleted (so validation classifies
them as the import-set) and the archive is re-staged as a date-scoped one.
"""
import gc
import json
import shutil
import zipfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from backup import restore_apply, restore_import, restore_validation
from backup.models import BackupJob, RestoreUpload
from backup.restore_apply import RestoreError
from backup.restore_import import ImportFailure
from backup.restore_validation import get_upload_dir, get_upload_path
from backup.tests.restore_helpers import build_archive
from backup.tests.test_restore_apply import RestoreApplyTestBase, _to_millis
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
        # Only the skip patient's own file and the import-set patient's files exist.
        self.assertEqual(
            sorted(n for n in self.media_files() if 'SK-1' in n or 'NW-1' in n),
            sorted([keeper_name] + [n for n in self.media_files() if 'NW-1' in n]),
        )
        self.assertFalse([n for n in self.media_files() if 'SK-1' in n and n != keeper_name])
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
        self.assertEqual({owner for owner, _key, _body in captured}, {new_one.pk})
        keys = {key for _owner, key, _body in captured}
        self.assertNotIn('referral.referralsent', keys)
        for _owner, _key, body in captured:
            self.assertNotEqual(json.loads(body)['pk'], keeper.pk if _key == 'patients.patient' else None)

    def test_empty_import_set_completes_with_nothing_imported(self):
        self.make_full_patient('Keeper', 'EM-1')
        db_export, media, _ = self.export_json(self.inst)
        _path, upload = self.dated_upload(db_export, media)
        self.assertEqual(upload.confirmed_snapshot['date_scope_match']['import'], [])
        before = Patient._base_manager.count()

        job = self.run_import(upload)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        self.assertEqual(job.restore_result['imported'], 0)
        self.assertEqual(job.restore_result['skipped'], 1)
        self.assertEqual(upload.status, RestoreUploadStatus.APPLIED)
        self.assertEqual(Patient._base_manager.count(), before)


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
        self.assertEqual([f['archive_pk'] for f in job.restore_result['failed']], [b.pk])
        self.assertIn('IntegrityError', job.restore_result['failed'][0]['reason'])
        self.assertIn(f'archive patient {b.pk}', job.error_message)
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
        self.assertIn('Restore applied with warnings', html)

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
        path = self.archive_path('esc.zip')
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('media/../evil.txt', b'bytes')
        with zipfile.ZipFile(path) as zf:
            warning = restore_import._place_media(
                zf, {'media/../evil.txt': 'ab' * 32}, 'patients.attachment', 'attachment', 1, '../evil.txt',
            )
        self.assertIsNotNone(warning)
        self.assertFalse((self.base_dir / 'evil.txt').exists())


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
