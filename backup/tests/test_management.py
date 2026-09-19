"""
backup/tests/test_management.py — Story 1.1 (added during review)

Exercises `run_backup` itself, not just `services.create_export` in
isolation: the pending -> running -> completed/failed transitions, that the
initial 'running' save is guarded, and that a failed export removes only the
partial .zip (never the whole archive_dir, which also holds run_backup.log).
"""
import zipfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from backup.models import BackupJob
from backup.services import get_archive_dir, get_archive_path
from institution.models import Institution
from ndas.custom_codes.choice import BackupJobStatus, BackupJobType

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
