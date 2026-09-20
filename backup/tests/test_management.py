"""
backup/tests/test_management.py — Story 1.1 (added during review)

Exercises `run_backup` itself, not just `services.create_export` in
isolation: the pending -> running -> completed/failed transitions, that the
initial 'running' save is guarded, and that a failed export removes only the
partial .zip (never the whole archive_dir, which also holds run_backup.log).
"""
import contextlib
import zipfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from backup.models import BackupJob
from backup.services import get_archive_dir, get_archive_path
from institution.models import Institution
from ndas.custom_codes.choice import BackupJobStatus, BackupJobType, NotificationType
from referral.models import Notification

User = get_user_model()

STORAGE_OVERRIDE = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)


@STORAGE_OVERRIDE
class RunBackupCommandTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='mgmt_sa1', password='x', position='Administrator', mobile_primary='0770000201',
        )
        self.inst = Institution.objects.create(name='Mgmt Hosp', slug='mgmt-hosp', created_by=self.user)
        self.job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.PENDING,
            scope=self.inst,
            triggered_by=self.user,
            trigger_institution=self.inst,
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(get_archive_dir(self.job), ignore_errors=True)

    def test_successful_run_transitions_pending_to_completed(self):
        call_command('run_backup', str(self.job.id))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, BackupJobStatus.COMPLETED)
        self.assertEqual(self.job.progress_pct, 100)
        self.assertEqual(self.job.error_message, "")
        self.assertTrue(Path(get_archive_path(self.job)).exists())

    def test_archive_checksum_persisted_on_successful_completion(self):
        # Story 1.3: run_backup must unpack create_export's 3rd return value
        # and persist it onto BackupJob.archive_checksum in the same final
        # save that sets status=completed.
        call_command('run_backup', str(self.job.id))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, BackupJobStatus.COMPLETED)
        self.assertEqual(len(self.job.archive_checksum), 64)

    def test_completed_with_skipped_media_reflected_in_error_message(self):
        with mock.patch(
            'backup.management.commands.run_backup.create_export',
            return_value=(get_archive_path(self.job), ["a.mp4: file missing on disk"], "a" * 64),
        ):
            get_archive_dir(self.job).mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(get_archive_path(self.job), 'w'):
                pass
            call_command('run_backup', str(self.job.id))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, BackupJobStatus.COMPLETED)
        self.assertIn('a.mp4', self.job.error_message)
        self.assertEqual(self.job.archive_checksum, "a" * 64)

    def test_export_exception_marks_job_failed_and_removes_only_the_zip(self):
        archive_dir = get_archive_dir(self.job)
        archive_dir.mkdir(parents=True, exist_ok=True)
        zip_path = get_archive_path(self.job)
        zip_path.write_bytes(b'partial-zip-bytes')
        log_path = archive_dir / 'run_backup.log'
        log_path.write_text('some log output')

        with mock.patch(
            'backup.management.commands.run_backup.create_export',
            side_effect=RuntimeError('boom'),
        ):
            call_command('run_backup', str(self.job.id))

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, BackupJobStatus.FAILED)
        self.assertIn('boom', self.job.error_message)
        self.assertFalse(zip_path.exists(), "the partial .zip should be removed on failure")
        self.assertTrue(log_path.exists(), "the log file must survive failure cleanup")
        self.assertEqual(
            self.job.archive_checksum, "",
            "archive_checksum must stay at the model default when create_export raises",
        )

    def test_nonexistent_job_raises_command_error(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('run_backup', '999999')

    def test_running_save_failure_does_not_crash_the_command(self):
        original_save = BackupJob.save
        call_state = {'count': 0}

        def flaky_save(self, *args, **kwargs):
            call_state['count'] += 1
            if call_state['count'] == 1:
                raise RuntimeError('transient db error')
            return original_save(self, *args, **kwargs)

        with mock.patch.object(BackupJob, 'save', flaky_save):
            call_command('run_backup', str(self.job.id))

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, BackupJobStatus.FAILED)
        self.assertIn('transient db error', self.job.error_message)

    # --- Story 1.5: terminal-state notifications ---

    def test_clean_completion_notifies_triggering_user(self):
        call_command('run_backup', str(self.job.id))
        notif = Notification.objects.get()
        self.assertEqual(notif.notification_type, NotificationType.BACKUP_COMPLETED)
        self.assertEqual(notif.recipient, self.user)
        self.assertEqual(notif.institution, self.inst)
        self.assertNotIn('warnings', notif.title)

    def test_completion_with_skipped_media_notifies_with_warnings(self):
        with mock.patch(
            'backup.management.commands.run_backup.create_export',
            return_value=(get_archive_path(self.job), ["a.mp4: file missing on disk"], "a" * 64),
        ):
            call_command('run_backup', str(self.job.id))
        notif = Notification.objects.get()
        self.assertEqual(notif.notification_type, NotificationType.BACKUP_COMPLETED)
        self.assertIn('warnings', notif.title)

    def test_export_failure_notifies_backup_failed(self):
        with mock.patch(
            'backup.management.commands.run_backup.create_export', side_effect=RuntimeError('boom'),
        ):
            call_command('run_backup', str(self.job.id))
        notif = Notification.objects.get()
        self.assertEqual(notif.notification_type, NotificationType.BACKUP_FAILED)
        self.assertIn('boom', notif.body)

    def _fail_when_marking_running(self):
        """A `BackupJob.save` replacement that raises only on the save that
        marks the job RUNNING (the "failed to start" trigger), not on the
        ordinal of the call."""
        original_save = BackupJob.save

        def flaky_save(instance, *args, **kwargs):
            if instance.status == BackupJobStatus.RUNNING:
                raise RuntimeError('transient db error')
            return original_save(instance, *args, **kwargs)

        return mock.patch.object(BackupJob, 'save', flaky_save)

    def _db_state_when_notified(self, *extra_patches):
        """Run `run_backup` with `notify_job_finished` replaced by a spy that
        re-reads the row from the DB at call time; return what it saw."""
        seen = {}

        def spy(job):
            fresh = BackupJob.objects.get(pk=job.pk)
            seen.update(status=fresh.status, progress=fresh.progress_pct)

        with mock.patch('backup.management.commands.run_backup.notify_job_finished', side_effect=spy):
            with contextlib.ExitStack() as stack:
                for patcher in extra_patches:
                    stack.enter_context(patcher)
                call_command('run_backup', str(self.job.id))
        return seen

    def test_failed_to_start_notifies_backup_failed(self):
        with self._fail_when_marking_running():
            call_command('run_backup', str(self.job.id))
        notif = Notification.objects.get()
        self.assertEqual(notif.notification_type, NotificationType.BACKUP_FAILED)
        self.assertIn('transient db error', notif.body)

    def test_notification_created_only_after_terminal_save_on_success(self):
        seen = self._db_state_when_notified()
        self.assertEqual(seen, {'status': BackupJobStatus.COMPLETED, 'progress': 100})

    def test_notification_created_only_after_terminal_save_on_export_failure(self):
        seen = self._db_state_when_notified(
            mock.patch('backup.management.commands.run_backup.create_export', side_effect=RuntimeError('boom')),
        )
        # status + progress_pct are written together in the one terminal save
        self.assertEqual(seen, {'status': BackupJobStatus.FAILED, 'progress': 0})

    def test_notification_created_only_after_terminal_save_on_failed_to_start(self):
        seen = self._db_state_when_notified(self._fail_when_marking_running())
        self.assertEqual(seen['status'], BackupJobStatus.FAILED)

    def test_notification_failure_does_not_change_job_outcome(self):
        with mock.patch.object(Notification.objects, 'create', side_effect=RuntimeError('nope')):
            call_command('run_backup', str(self.job.id))  # must not raise
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, BackupJobStatus.COMPLETED)
        self.assertEqual(self.job.progress_pct, 100)
        self.assertEqual(Notification.objects.count(), 0)

    def test_job_without_triggering_user_completes_without_notification(self):
        self.job.triggered_by = None
        self.job.save(update_fields=['triggered_by'])
        call_command('run_backup', str(self.job.id))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, BackupJobStatus.COMPLETED)
        self.assertEqual(Notification.objects.count(), 0)
