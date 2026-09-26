"""
backup/tests/test_restore_audit.py -- Story 2.6

The restore audit trail: one PHI-free `BackupJob.restore_audit` record and one
`django.security.restore` line per finished restore job (both scopes, failures
included), best-effort behaviour, and the unknown/foreign-upload denial line
from every restore view.
"""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from backup import restore_audit
from backup.models import BackupJob, RestoreUpload
from backup.restore_apply import RESTORE_MODEL_KEYS
from backup.tests.restore_helpers import IsolatedBaseDirMixin
from backup.tests.test_restore_apply import STORAGE_OVERRIDE
from backup.tests.test_restore_import import ImportTestBase
from institution.models import Institution
from ndas.custom_codes.choice import (
    BackupJobScopeType,
    BackupJobStatus,
    BackupJobType,
    NotificationType,
    RestoreUploadStatus,
    UserType,
)
from patients.models import Patient
from referral.models import Notification

User = get_user_model()
SECURITY_LOGGER = 'django.security.restore'


class AuditAssertions:
    def assertPhiFree(self, audit, logs, *secrets):
        text = json.dumps(audit) + "\n".join(logs.output if logs is not None else [])
        for secret in secrets:
            self.assertNotIn(secret, text)

    def assertCommonShape(self, job, audit, upload, outcome):
        self.assertEqual(audit['version'], 1)
        self.assertEqual(audit['actor'], {
            'id': self.user.id, 'username': self.user.username, 'user_type': UserType.SUPERADMIN,
        })
        self.assertEqual(audit['upload_id'], upload.id)
        self.assertEqual(audit['archive']['sha256'], upload.archive_sha256)
        self.assertEqual(audit['archive']['filename'], upload.original_filename)
        self.assertEqual(audit['archive']['source_job_id'], upload.source_job_id)
        self.assertEqual(audit['outcome'], outcome)
        self.assertLessEqual(audit['started_at'], audit['finished_at'])
        self.assertEqual(audit['snapshot_job_id'], job.pre_restore_snapshot_id)
        self.assertEqual(
            audit['scope']['institutions'], [{'id': self.inst.id, 'slug': 'ra-hosp', 'name': 'RA Hosp'}],
        )


class FullScopeAuditTest(AuditAssertions, ImportTestBase):
    def test_completed_full_scope_restore_records_scope_counts_and_snapshot(self):
        patient = self.make_patient(self.inst, baby_name='Secret Baby Zed', bht='PHI-123')
        self.make_video(patient)
        upload = self.build_and_confirm(self.inst)
        # A patient created after the archive: the restore removes it, orphaning
        # its referral link and move log.
        late = self.make_patient(self.inst, baby_name='Late Baby Qux', bht='PHI-LATE')
        self.make_referral(self.inst, late)
        self.make_move_log(late, self.inst)

        job = self.start(upload)
        with self.assertLogs(SECURITY_LOGGER, level='INFO') as logs:
            job = self.run_restore_command(job)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        audit = job.restore_audit
        self.assertCommonShape(job, audit, upload, 'completed')
        self.assertEqual(audit['scope']['mode'], 'full')
        self.assertEqual(audit['scope']['scope_type'], BackupJobScopeType.SINGLE)
        self.assertEqual(audit['scope']['date_filter'], {'start': None, 'end': None})
        counts = audit['counts']
        self.assertEqual(set(counts['records']), set(RESTORE_MODEL_KEYS))
        self.assertEqual(counts['records']['patients.patient'], 1)
        self.assertEqual(counts['records']['video.video'], 1)
        self.assertEqual(counts['referral_links_cleared'], 1)
        self.assertEqual(counts['move_logs_removed'], 1)
        self.assertEqual(counts['media_warnings'], 0)
        self.assertNotIn('error', audit)
        self.assertIsNotNone(audit['snapshot_job_id'])

        lines = [line for line in logs.output if 'Restore finished' in line]
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith('INFO:'))
        for part in ('actor=ra_sa', f'upload={upload.id}', f'job={job.id}', 'mode=full', 'scope=ra-hosp',
                     'outcome=completed', f'snapshot={audit["snapshot_job_id"]}'):
            self.assertIn(part, lines[0])
        self.assertPhiFree(audit, logs, 'Secret Baby Zed', 'PHI-123', 'Late Baby Qux', 'PHI-LATE')

        # The status panel, notification and result are unchanged by the audit.
        self.assertIsNone(job.restore_result)
        self.assertTrue(Notification.objects.filter(notification_type=NotificationType.RESTORE_COMPLETED).exists())

    def test_failed_restore_records_failure_with_actor_scope_snapshot_and_zero_counts(self):
        self.make_patient(self.inst, baby_name='Untouched Baby', bht='FAIL-1')
        upload = self.build_and_confirm(self.inst)
        job = self.start(upload)

        with mock.patch('backup.restore_apply.create_export', side_effect=RuntimeError('disk exploded')):
            with self.assertLogs(SECURITY_LOGGER, level='INFO') as logs:
                job = self.run_restore_command(job)

        self.assertEqual(job.status, BackupJobStatus.FAILED)
        audit = job.restore_audit
        self.assertCommonShape(job, audit, upload, 'failed')
        self.assertIn('pre-restore snapshot', audit['error'])
        self.assertNotIn('disk exploded', audit['error'])   # value-free variant
        self.assertIsNotNone(audit['snapshot_job_id'])      # the failed snapshot job is still named
        self.assertEqual(audit['counts']['records_loaded'], 0)
        self.assertEqual(audit['counts']['move_logs_removed'], 0)
        line = [entry for entry in logs.output if 'Restore finished' in entry]
        self.assertEqual(len(line), 1)
        self.assertTrue(line[0].startswith('WARNING:'))
        self.assertIn('outcome=failed', line[0])
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        self.assertTrue(Notification.objects.filter(notification_type=NotificationType.RESTORE_FAILED).exists())

    def test_failure_text_that_quotes_a_patient_identifier_is_kept_out_of_the_audit(self):
        patient = self.make_patient(self.inst, baby_name='Quoted Baby', bht='CLASH-BHT-1')
        upload = self.build_and_confirm(self.inst)
        Patient._base_manager.filter(pk=patient.pk).delete()
        self.make_patient(self.inst2, baby_name='Outsider', bht='CLASH-BHT-1')
        job = self.start(upload)

        with self.assertLogs(SECURITY_LOGGER, level='INFO') as logs:
            job = self.run_restore_command(job)

        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertIn('CLASH-BHT-1', job.error_message)   # existing behaviour, unchanged
        audit = job.restore_audit
        self.assertEqual(audit['outcome'], 'failed')
        self.assertIn('already belongs to a patient', audit['error'])
        self.assertPhiFree(audit, logs, 'CLASH-BHT-1', 'Quoted Baby')

    def test_media_warnings_make_a_full_scope_run_completed_with_warnings(self):
        patient = self.make_patient(self.inst, baby_name='Media Baby', bht='MW-1')
        self.make_video(patient)
        upload = self.build_and_confirm(self.inst)
        job = self.start(upload)
        with mock.patch('backup.restore_apply.restore_media', return_value=['a.mp4: missing from the archive']):
            with self.assertLogs(SECURITY_LOGGER, level='INFO') as logs:
                job = self.run_restore_command(job)
        self.assertEqual(job.status, BackupJobStatus.COMPLETED)
        self.assertEqual(job.restore_audit['outcome'], 'completed_with_warnings')
        self.assertEqual(job.restore_audit['counts']['media_warnings'], 1)
        line = [entry for entry in logs.output if 'Restore finished' in entry]
        self.assertTrue(line[0].startswith('WARNING:'))


class DateScopedAuditTest(AuditAssertions, ImportTestBase):
    def two_patient_upload(self):
        a = self.make_full_patient('Zelda Quixote', 'DS-A')
        b = self.make_full_patient('Yorick Pemberton', 'DS-B')
        db_export, media, _ = self.export_json(self.inst)
        self.delete_patients(a, b)
        self.wipe_media()
        _path, upload = self.dated_upload(db_export, media)
        return a, b, upload

    def test_clean_date_scoped_run_records_counts_and_the_archive_to_new_pk_map(self):
        a, b, upload = self.two_patient_upload()
        job = self.start(upload)
        with self.assertLogs(SECURITY_LOGGER, level='INFO') as logs:
            job = self.run_restore_command(job)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED, job.error_message)
        audit = job.restore_audit
        self.assertCommonShape(job, audit, upload, 'completed')
        self.assertEqual(audit['scope']['mode'], 'date_scoped')
        self.assertEqual(audit['scope']['date_filter'], {'start': '2026-01-01', 'end': None})
        new_a = Patient._base_manager.get(bht='DS-A').pk
        new_b = Patient._base_manager.get(bht='DS-B').pk
        self.assertEqual(audit['counts'], {
            'imported': 2, 'skipped': 0, 'excluded': 0, 'failed': 0, 'media_warnings': 0,
            'patients': audit['counts']['patients'],
        })
        self.assertCountEqual(audit['counts']['patients'], [[a.pk, new_a], [b.pk, new_b]])
        for pair in audit['counts']['patients']:
            self.assertTrue(all(isinstance(pk, int) for pk in pair))
        line = [entry for entry in logs.output if 'Restore finished' in entry]
        self.assertEqual(len(line), 1)
        self.assertTrue(line[0].startswith('INFO:'))
        self.assertIn('mode=date_scoped', line[0])
        self.assertPhiFree(audit, logs, 'Zelda Quixote', 'Yorick Pemberton', 'DS-A', 'DS-B')
        # Story 2.5's record is unchanged.
        self.assertEqual(job.restore_result['imported'], 2)

    def test_a_failed_patient_makes_it_completed_with_warnings_and_lists_only_committed_patients(self):
        a, b, upload = self.two_patient_upload()
        self.make_patient(self.inst2, baby_name='Collider', bht='DS-B')
        job = self.start(upload)
        with self.assertLogs(SECURITY_LOGGER, level='INFO') as logs:
            job = self.run_restore_command(job)

        self.assertEqual(job.status, BackupJobStatus.COMPLETED)
        audit = job.restore_audit
        self.assertEqual(audit['outcome'], 'completed_with_warnings')
        self.assertEqual(audit['counts']['imported'], 1)
        self.assertEqual(audit['counts']['failed'], 1)
        self.assertEqual([pair[0] for pair in audit['counts']['patients']], [a.pk])
        line = [entry for entry in logs.output if 'Restore finished' in entry]
        self.assertTrue(line[0].startswith('WARNING:'))
        self.assertPhiFree(audit, logs, 'DS-B', 'DS-A', 'Yorick Pemberton', 'Zelda Quixote')
        self.assertNotIn('reason', json.dumps(audit))

    def test_an_early_stop_is_completed_with_warnings_and_not_counted_as_a_failed_patient(self):
        a, b, upload = self.two_patient_upload()
        job = self.start(upload)
        from django.core.serializers.base import DeserializedObject
        from django.db import OperationalError
        real_save = DeserializedObject.save
        names = {a.pk: 'Zelda Quixote', b.pk: 'Yorick Pemberton'}
        second = upload.confirmed_snapshot['date_scope_match']['import'][1]['archive_pk']

        def save(deserialized, *args, **kwargs):
            if getattr(deserialized.object, 'baby_name', None) == names[second]:
                raise OperationalError('database is locked')
            return real_save(deserialized, *args, **kwargs)

        with mock.patch.object(DeserializedObject, 'save', save):
            job = self.run_restore_command(job)
        audit = job.restore_audit
        self.assertEqual(job.status, BackupJobStatus.COMPLETED)
        self.assertEqual(audit['outcome'], 'completed_with_warnings')
        self.assertEqual(audit['counts']['imported'], 1)
        self.assertEqual(audit['counts']['failed'], 0)

    def test_every_patient_failing_is_a_failed_audit_without_identifiers(self):
        a = self.make_full_patient('Zelda Quixote', 'AF-A')
        db_export, media, _ = self.export_json(self.inst)
        self.delete_patients(a)
        self.wipe_media()
        _path, upload = self.dated_upload(db_export, media)
        self.make_patient(self.inst2, baby_name='Collider', bht='AF-A')
        job = self.start(upload)
        with self.assertLogs(SECURITY_LOGGER, level='INFO') as logs:
            job = self.run_restore_command(job)

        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertIn('AF-A', job.error_message)   # the job message is unchanged
        audit = job.restore_audit
        self.assertEqual(audit['outcome'], 'failed')
        self.assertEqual(audit['scope']['mode'], 'date_scoped')
        self.assertIn('None of the 1 patient(s) could be imported', audit['error'])
        self.assertEqual(audit['counts']['imported'], 0)
        self.assertEqual(audit['counts']['patients'], [])
        self.assertPhiFree(audit, logs, 'AF-A', 'Zelda Quixote')

    def test_unexpected_error_in_a_date_scoped_run_never_carries_exception_text(self):
        self.two_patient_upload()
        upload = RestoreUpload.objects.get()
        job = self.start(upload)
        with mock.patch('backup.restore_import._read_partition', side_effect=RuntimeError('Zelda Quixote leaked')):
            with self.assertLogs(SECURITY_LOGGER, level='INFO') as logs:
                with self.assertLogs('backup.management.commands.run_restore', level='ERROR'):
                    job = self.run_restore_command(job)
        audit = job.restore_audit
        self.assertEqual(audit['outcome'], 'failed')
        self.assertIn('RuntimeError', audit['error'])
        self.assertPhiFree(audit, logs, 'Zelda Quixote')

    def test_empty_import_set_is_completed_with_zero_imported(self):
        self.make_full_patient('Keeper Person', 'EM-1')
        db_export, media, _ = self.export_json(self.inst)
        _path, upload = self.dated_upload(db_export, media)
        job = self.start(upload)
        job = self.run_restore_command(job)
        audit = job.restore_audit
        self.assertEqual(audit['outcome'], 'completed')
        self.assertEqual(audit['counts'], {
            'imported': 0, 'skipped': 1, 'excluded': 0, 'failed': 0, 'media_warnings': 0, 'patients': [],
        })
        self.assertIsNone(audit['snapshot_job_id'])


class AuditRobustnessTest(AuditAssertions, ImportTestBase):
    def completed_full_job(self):
        self.make_patient(self.inst, baby_name='Robust Baby', bht='RB-1')
        upload = self.build_and_confirm(self.inst)
        return upload, self.start(upload)

    def test_the_record_outlives_a_deleted_actor_and_institution(self):
        upload, job = self.completed_full_job()
        job = self.run_restore_command(job)
        BackupJob.objects.filter(pk=job.pk).update(triggered_by=None, scope=None)
        job.refresh_from_db()
        self.assertIsNone(job.triggered_by)
        self.assertIsNone(job.scope)
        self.assertEqual(job.restore_audit['actor']['username'], 'ra_sa')
        self.assertEqual(job.restore_audit['scope']['institutions'][0]['name'], 'RA Hosp')
        self.assertEqual(job.restore_audit['scope']['institutions'][0]['slug'], 'ra-hosp')

    def test_a_failure_building_the_audit_leaves_the_restore_untouched(self):
        upload, job = self.completed_full_job()
        with mock.patch.object(restore_audit, 'build_audit', side_effect=RuntimeError('boom')):
            with self.assertLogs('backup.restore_audit', level='ERROR'):
                job = self.run_restore_command(job)
        self.assertEqual(job.status, BackupJobStatus.COMPLETED)
        self.assertIsNone(job.restore_audit)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.APPLIED)
        self.assertTrue(Notification.objects.filter(notification_type=NotificationType.RESTORE_COMPLETED).exists())

    def test_a_failure_writing_the_log_line_still_saves_the_record(self):
        upload, job = self.completed_full_job()
        with mock.patch.object(restore_audit, '_log_line', side_effect=RuntimeError('log down')):
            with self.assertLogs('backup.restore_audit', level='ERROR'):
                job = self.run_restore_command(job)
        self.assertEqual(job.status, BackupJobStatus.COMPLETED)
        self.assertEqual(job.restore_audit['outcome'], 'completed')

    def test_a_failure_building_the_audit_of_a_failed_restore_keeps_the_failure_handling(self):
        upload, job = self.completed_full_job()
        with mock.patch('backup.restore_apply.create_export', side_effect=RuntimeError('disk')):
            with mock.patch.object(restore_audit, 'build_audit', side_effect=RuntimeError('boom')):
                with self.assertLogs('backup.restore_audit', level='ERROR'):
                    job = self.run_restore_command(job)
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertIsNone(job.restore_audit)
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)
        self.assertTrue(Notification.objects.filter(notification_type=NotificationType.RESTORE_FAILED).exists())

    def test_the_line_is_written_even_when_the_jobs_terminal_save_fails(self):
        upload, job = self.completed_full_job()
        real_save = BackupJob.save

        def save(instance, *args, **kwargs):
            if 'restore_audit' in (kwargs.get('update_fields') or ()):
                raise RuntimeError('save failed')
            return real_save(instance, *args, **kwargs)

        with mock.patch.object(BackupJob, 'save', save):
            with self.assertLogs(SECURITY_LOGGER, level='INFO') as logs:
                with self.assertLogs('backup.management.commands.run_restore', level='ERROR'):
                    self.run_restore_command(job)
        self.assertTrue(any('Restore finished' in line and 'outcome=completed' in line for line in logs.output))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.APPLIED)


class BuildAuditUnitTest(AuditAssertions, ImportTestBase):
    def test_multi_scope_lists_every_institution(self):
        job = self.make_job(scope_type=BackupJobScopeType.MULTI, institutions=[self.inst, self.inst2])
        audit = restore_audit.build_audit(job, outcome='completed')
        self.assertEqual(
            sorted(i['slug'] for i in audit['scope']['institutions']), ['ra-hosp', 'ra-hosp-2'],
        )
        self.assertEqual(audit['scope']['scope_type'], 'multi')

    def test_system_scope_takes_the_manifests_slugs(self):
        upload = RestoreUpload.objects.create(
            uploaded_by=self.user, status=RestoreUploadStatus.APPLYING,
            manifest_summary={'institutions': ['ra-hosp', 'gone-hosp']},
        )
        job = self.make_job(scope_type=BackupJobScopeType.SYSTEM, restore_upload=upload)
        audit = restore_audit.build_audit(job, outcome='completed')
        self.assertEqual(audit['scope']['institutions'], [
            {'id': self.inst.id, 'slug': 'ra-hosp', 'name': 'RA Hosp'},
            {'id': None, 'slug': 'gone-hosp', 'name': ''},
        ])

    def test_a_job_without_actor_or_upload_still_builds(self):
        job = self.make_job(self.inst, triggered_by=None)
        audit = restore_audit.build_audit(job, outcome='failed', error='x\ny')
        self.assertEqual(audit['actor'], {'id': None, 'username': '', 'user_type': ''})
        self.assertIsNone(audit['upload_id'])
        self.assertEqual(audit['archive'], {'filename': '', 'sha256': '', 'source_job_id': None})
        self.assertNotIn('\n', audit['error'])
        json.dumps(audit)


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
@STORAGE_OVERRIDE
class UnknownUploadLoggingTest(IsolatedBaseDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.sa = User.objects.create_user(
            username='sa_au', password='x', position='Administrator', mobile_primary='0770000701',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.other = User.objects.create_user(
            username='sa_au2', password='x', position='Administrator', mobile_primary='0770000702',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.admin_user = User.objects.create_user(
            username='ad_au', password='x', position='Administrator', mobile_primary='0770000703',
            user_type=UserType.ADMIN, institution=None,
        )
        self.inst = Institution.objects.create(name='AU Hosp', slug='au-hosp', created_by=self.sa)
        self.foreign = RestoreUpload.objects.create(
            uploaded_by=self.other, original_filename='f.zip', status=RestoreUploadStatus.VALIDATED,
        )

    def client_for(self, user):
        client = Client()
        client.force_login(user)
        session = client.session
        session['active_institution_id'] = self.inst.id
        session.save()
        return client

    VIEWS = (
        ('restore-status', 'get', 'restore_status'),
        ('restore-status-fragment', 'get', 'restore_status_fragment'),
        ('restore-preview', 'get', 'restore_preview'),
        ('restore-confirm', 'post', 'restore_confirm'),
        ('restore-start', 'post', 'restore_start'),
        ('restore-cancel', 'post', 'restore_cancel'),
    )

    def test_foreign_and_unknown_uploads_are_404_with_one_warning_each(self):
        client = self.client_for(self.sa)
        for url_name, method, view_name in self.VIEWS:
            for pk in (self.foreign.pk, 999999):
                with self.subTest(view=view_name, pk=pk):
                    with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
                        response = getattr(client, method)(reverse(f'backup:{url_name}', args=[pk]))
                    self.assertEqual(response.status_code, 404)
                    lines = [line for line in logs.output if 'unknown or foreign upload' in line]
                    self.assertEqual(len(lines), 1)
                    for part in ('Restore access denied', 'user=sa_au', f'view={view_name}', f'upload={pk}'):
                        self.assertIn(part, lines[0])
        self.foreign.refresh_from_db()
        self.assertEqual(self.foreign.status, RestoreUploadStatus.VALIDATED)

    def test_own_upload_writes_no_denial_line(self):
        own = RestoreUpload.objects.create(
            uploaded_by=self.sa, original_filename='o.zip', status=RestoreUploadStatus.FAILED,
        )
        client = self.client_for(self.sa)
        with self.assertNoLogs(SECURITY_LOGGER, level='WARNING'):
            response = client.get(reverse('backup:restore-status', args=[own.pk]))
        self.assertEqual(response.status_code, 200)

    def test_non_super_admin_denial_is_still_logged_at_every_restore_url(self):
        client = self.client_for(self.admin_user)
        for url_name, method, view_name in self.VIEWS:
            with self.subTest(view=view_name):
                with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
                    getattr(client, method)(reverse(f'backup:{url_name}', args=[self.foreign.pk]))
                self.assertTrue(any(
                    'Restore access denied: user=ad_au' in line and f'view={view_name}' in line
                    for line in logs.output
                ))
                self.assertFalse(any('unknown or foreign upload' in line for line in logs.output))
