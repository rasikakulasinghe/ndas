"""
backup/tests/test_sweep_stale_jobs.py -- deferred-work ledger triage

Exercises `manage.py sweep_stale_jobs`: a `BackupJob` stuck pending/running
with no progress for over the stale threshold is marked failed (freeing the
Story 1.2 overlap lock); a stale `restore` job also returns its upload to
'confirmed' and gets a best-effort restore_audit; an `applying` upload with
no active job at all, itself stale, is caught by the defensive second pass.
A job (or upload) updated recently is left alone, and two concurrent runs
over the same stale job cannot both flip it.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from backup.job_lock import create_job_unless_overlapping
from backup.management.commands.sweep_stale_jobs import STALE_JOB_AFTER, Command
from backup.models import BackupJob, RestoreUpload
from institution.models import Institution
from ndas.custom_codes.choice import (
    BackupJobScopeType, BackupJobStatus, BackupJobType, NotificationType, RestoreUploadStatus,
)
from referral.models import Notification

User = get_user_model()


class SweepStaleJobsTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='sweep_sa', password='x', position='Administrator', mobile_primary='0770000701',
        )
        self.inst = Institution.objects.create(name='Sweep Hosp', slug='sweep-hosp', created_by=self.user)

    def make_job(self, **kwargs):
        defaults = dict(
            job_type=BackupJobType.BACKUP, status=BackupJobStatus.RUNNING,
            scope_type=BackupJobScopeType.SINGLE, scope=self.inst,
            trigger_institution=self.inst, triggered_by=self.user,
        )
        defaults.update(kwargs)
        return BackupJob.objects.create(**defaults)

    def backdate(self, obj, age=None):
        """Push `obj.updated_at` back past the stale threshold, bypassing
        auto_now (a plain .save() would just overwrite it with now)."""
        age = age or (STALE_JOB_AFTER * 2)
        type(obj).objects.filter(pk=obj.pk).update(updated_at=timezone.now() - age)
        obj.refresh_from_db()


class StaleBackupJobTest(SweepStaleJobsTestBase):
    def test_stale_pending_job_marked_failed(self):
        job = self.make_job(status=BackupJobStatus.PENDING)
        self.backdate(job)

        call_command('sweep_stale_jobs')

        job.refresh_from_db()
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertIn('stalled', job.error_message)
        self.assertEqual(job.progress_pct, 0)

    def test_stale_running_job_notifies_backup_failed(self):
        job = self.make_job(status=BackupJobStatus.RUNNING)
        self.backdate(job)

        call_command('sweep_stale_jobs')

        notif = Notification.objects.get()
        self.assertEqual(notif.notification_type, NotificationType.BACKUP_FAILED)

    def test_stale_job_logs_a_security_warning(self):
        job = self.make_job(status=BackupJobStatus.RUNNING)
        self.backdate(job)

        with self.assertLogs('django.security.restore', level='WARNING') as cm:
            call_command('sweep_stale_jobs')

        self.assertTrue(any(f'BackupJob {job.id}' in line for line in cm.output))

    def test_fresh_job_is_left_alone(self):
        job = self.make_job(status=BackupJobStatus.RUNNING)
        # updated_at defaults to now -- well within the stale threshold.

        call_command('sweep_stale_jobs')

        job.refresh_from_db()
        self.assertEqual(job.status, BackupJobStatus.RUNNING)
        self.assertEqual(Notification.objects.count(), 0)

    def test_stale_job_frees_the_overlap_lock(self):
        """Ledger regression (#45): a stuck job must stop blocking Story
        1.2's overlap lock for its scope once swept."""
        job = self.make_job(status=BackupJobStatus.RUNNING)
        self.backdate(job)
        self.assertIsNone(
            create_job_unless_overlapping(
                BackupJobScopeType.SINGLE, [self.inst],
                job_type=BackupJobType.BACKUP, status=BackupJobStatus.PENDING, triggered_by=self.user,
            ),
            "the stale job should still block until it is swept",
        )

        call_command('sweep_stale_jobs')

        new_job = create_job_unless_overlapping(
            BackupJobScopeType.SINGLE, [self.inst],
            job_type=BackupJobType.BACKUP, status=BackupJobStatus.PENDING, triggered_by=self.user,
        )
        self.assertIsNotNone(new_job, "the lock must be free once the stale job is marked failed")

    def test_stale_pre_restore_snapshot_marked_failed_without_notification(self):
        job = self.make_job(job_type=BackupJobType.PRE_RESTORE_SNAPSHOT, status=BackupJobStatus.RUNNING)
        self.backdate(job)

        call_command('sweep_stale_jobs')

        job.refresh_from_db()
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertIsNone(job.restore_audit)
        self.assertEqual(Notification.objects.count(), 0)

    def test_multiple_stale_jobs_are_all_swept_in_one_run(self):
        job_a = self.make_job(status=BackupJobStatus.RUNNING)
        job_b = self.make_job(status=BackupJobStatus.PENDING)
        self.backdate(job_a)
        self.backdate(job_b)

        call_command('sweep_stale_jobs')

        job_a.refresh_from_db()
        job_b.refresh_from_db()
        self.assertEqual(job_a.status, BackupJobStatus.FAILED)
        self.assertEqual(job_b.status, BackupJobStatus.FAILED)
        self.assertEqual(Notification.objects.count(), 2)

    def test_running_twice_is_idempotent(self):
        job = self.make_job(status=BackupJobStatus.RUNNING)
        self.backdate(job)

        call_command('sweep_stale_jobs')
        call_command('sweep_stale_jobs')  # second run must be a true no-op

        job.refresh_from_db()
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertEqual(Notification.objects.count(), 1, "the second run must not re-notify an already-failed job")

    def test_save_failure_leaves_job_untouched_and_does_not_crash(self):
        job = self.make_job(status=BackupJobStatus.RUNNING)
        self.backdate(job)

        with mock.patch.object(BackupJob, 'save', side_effect=RuntimeError('db gone')):
            call_command('sweep_stale_jobs')  # must not raise

        job.refresh_from_db()
        self.assertEqual(job.status, BackupJobStatus.RUNNING, "an unsaved flip must not be reported as handled")
        self.assertEqual(Notification.objects.count(), 0)

    def test_concurrent_claim_only_flips_the_job_once(self):
        """Two sweeps racing the same stale job: the second claim must see
        it already gone (no longer pending/running) and skip it, rather than
        both flipping it and double-notifying."""
        job = self.make_job(status=BackupJobStatus.RUNNING)
        self.backdate(job)
        message = "stalled"

        first = Command()._claim_and_fail(job.id, timezone.now(), message)
        second = Command()._claim_and_fail(job.id, timezone.now(), message)

        self.assertIsNotNone(first)
        self.assertIsNone(second, "a job already flipped to failed must not be claimed again")
        self.assertEqual(Notification.objects.count(), 0)  # _claim_and_fail alone never notifies


class StaleRestoreJobTest(SweepStaleJobsTestBase):
    def make_upload(self, **kwargs):
        defaults = dict(
            uploaded_by=self.user, status=RestoreUploadStatus.APPLYING,
            confirmed_at=timezone.now(), confirmed_snapshot={'snapshot_version': 1, 'digest': 'a' * 64},
        )
        defaults.update(kwargs)
        return RestoreUpload.objects.create(**defaults)

    def test_stale_restore_job_reverts_upload_and_writes_audit(self):
        upload = self.make_upload()
        job = self.make_job(job_type=BackupJobType.RESTORE, status=BackupJobStatus.RUNNING, restore_upload=upload)
        self.backdate(job)

        call_command('sweep_stale_jobs')

        job.refresh_from_db()
        upload.refresh_from_db()
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertIsNotNone(job.restore_audit)
        self.assertEqual(job.restore_audit['outcome'], 'failed')
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)

    def test_stale_restore_job_without_upload_still_fails_cleanly(self):
        job = self.make_job(job_type=BackupJobType.RESTORE, status=BackupJobStatus.RUNNING, restore_upload=None)
        self.backdate(job)

        call_command('sweep_stale_jobs')  # must not raise

        job.refresh_from_db()
        self.assertEqual(job.status, BackupJobStatus.FAILED)

    def test_orphaned_applying_upload_with_no_job_is_reverted_once_stale(self):
        """Defensive second pass: an upload stuck 'applying' whose job row no
        longer exists (e.g. deleted) is just as stuck as one with a live
        stale job, but the main loop never reaches it."""
        upload = self.make_upload()
        self.backdate(upload)

        call_command('sweep_stale_jobs')

        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.CONFIRMED)

    def test_orphaned_applying_upload_not_yet_stale_is_left_alone(self):
        """The grace period on the orphan pass: a job row vanishing moments
        ago must not immediately revert an upload whose subprocess may still
        be finishing the apply (see the delete_helpers gap in deferred-work.md)."""
        upload = self.make_upload()
        # upload.updated_at defaults to now -- not stale, and no job row exists.

        call_command('sweep_stale_jobs')

        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.APPLYING)

    def test_applying_upload_with_a_fresh_job_is_left_alone(self):
        upload = self.make_upload()
        self.make_job(job_type=BackupJobType.RESTORE, status=BackupJobStatus.RUNNING, restore_upload=upload)
        # job.updated_at defaults to now -- not stale.

        call_command('sweep_stale_jobs')

        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.APPLYING)


class NoStaleJobsTest(SweepStaleJobsTestBase):
    def test_no_stale_jobs_does_not_crash(self):
        call_command('sweep_stale_jobs')  # must not raise with nothing to sweep
