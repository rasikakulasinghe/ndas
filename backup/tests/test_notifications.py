"""
backup/tests/test_notifications.py -- Story 1.5

`backup.notifications.notify_job_finished`: recipient/institution resolution,
per-outcome content, best-effort behaviour, skips, and that the result
actually reaches the navbar bell / mark-read redirect.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from backup.models import BackupJob, RestoreUpload
from backup.notifications import notify_job_finished
from institution.models import Institution
from ndas.custom_codes.choice import (
    BackupJobScopeType, BackupJobStatus, BackupJobType, NotificationType, UserType,
)
from referral.models import Notification

User = get_user_model()


class NotifyJobFinishedTest(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_notif', password='Testpass1!', position='Administrator',
            mobile_primary='0770000301', user_type=UserType.SUPERADMIN,
            is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(name='Notif Hosp', slug='notif-hosp', created_by=self.superadmin)
        self.inst2 = Institution.objects.create(name='Notif Hosp 2', slug='notif-hosp-2', created_by=self.superadmin)
        self.admin = User.objects.create_user(
            username='admin_notif', password='Testpass1!', position='Administrator',
            mobile_primary='0770000302', user_type=UserType.ADMIN, institution=self.inst,
        )

    def _job(self, **kwargs):
        defaults = dict(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.COMPLETED,
            scope=self.inst,
            trigger_institution=self.inst,
            triggered_by=self.admin,
        )
        defaults.update(kwargs)
        return BackupJob.objects.create(**defaults)

    def test_clean_completion_creates_backup_completed_notification(self):
        job = self._job()
        notify_job_finished(job)
        notif = Notification.objects.get()
        self.assertEqual(notif.notification_type, NotificationType.BACKUP_COMPLETED)
        self.assertEqual(notif.recipient, self.admin)
        self.assertEqual(notif.institution, self.inst)
        self.assertFalse(notif.is_read)
        self.assertEqual(notif.link, reverse('backup:backup-create'))
        self.assertEqual(notif.title, "Backup completed")
        self.assertEqual(notif.added_by, self.admin)

    def test_completion_with_skipped_media_is_still_completed_type_but_mentions_warnings(self):
        job = self._job(error_message="Completed with 1 media file(s) skipped: a.mp4: file missing on disk")
        notify_job_finished(job)
        notif = Notification.objects.get()
        self.assertEqual(notif.notification_type, NotificationType.BACKUP_COMPLETED)
        self.assertIn('warnings', notif.title)
        self.assertIn('a.mp4', notif.body)

    def test_failure_creates_backup_failed_notification_with_error_summary(self):
        job = self._job(status=BackupJobStatus.FAILED, error_message="Backup export failed: boom")
        notify_job_finished(job)
        notif = Notification.objects.get()
        self.assertEqual(notif.notification_type, NotificationType.BACKUP_FAILED)
        self.assertIn('boom', notif.body)

    def test_long_error_message_is_truncated_in_body(self):
        job = self._job(status=BackupJobStatus.FAILED, error_message="x" * 5000)
        notify_job_finished(job)
        self.assertLessEqual(len(Notification.objects.get().body), 200)

    def test_delivered_to_trigger_institution_for_superadmin_system_wide_job(self):
        job = self._job(
            scope=None, scope_type=BackupJobScopeType.SYSTEM,
            triggered_by=self.superadmin, trigger_institution=self.inst2,
        )
        notify_job_finished(job)
        notif = Notification.objects.get()
        self.assertEqual(notif.institution, self.inst2)
        self.assertEqual(notif.recipient, self.superadmin)

    def test_falls_back_to_scope_when_trigger_institution_missing(self):
        job = self._job(trigger_institution=None)
        notify_job_finished(job)
        self.assertEqual(Notification.objects.get().institution, self.inst)

    def test_no_recipient_creates_nothing(self):
        job = self._job(triggered_by=None)
        notify_job_finished(job)
        self.assertEqual(Notification.objects.count(), 0)

    def test_no_institution_creates_nothing(self):
        job = self._job(scope=None, trigger_institution=None, scope_type=BackupJobScopeType.SYSTEM)
        notify_job_finished(job)
        self.assertEqual(Notification.objects.count(), 0)

    def test_creation_failure_is_swallowed_and_logged(self):
        job = self._job()
        with mock.patch.object(Notification.objects, 'create', side_effect=RuntimeError('db down')):
            with self.assertLogs('backup.notifications', level='ERROR'):
                notify_job_finished(job)  # must not raise
        job.refresh_from_db()
        self.assertEqual(job.status, BackupJobStatus.COMPLETED)


class NotifyRestoreJobFinishedTest(TestCase):
    """Story 2.3: a `restore` job's finish notification uses the
    RESTORE_COMPLETED/RESTORE_FAILED types, restore wording, and links to the
    upload's status page (not the backup page); a `pre_restore_snapshot` job
    never notifies at all."""

    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_notif_r', password='Testpass1!', position='Administrator',
            mobile_primary='0770000321', user_type=UserType.SUPERADMIN,
            is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(name='Notif R Hosp', slug='notif-r-hosp', created_by=self.superadmin)
        self.upload = RestoreUpload.objects.create(uploaded_by=self.superadmin, original_filename='a.zip')

    def _job(self, **kwargs):
        defaults = dict(
            job_type=BackupJobType.RESTORE,
            status=BackupJobStatus.COMPLETED,
            scope=self.inst,
            trigger_institution=self.inst,
            triggered_by=self.superadmin,
            restore_upload=self.upload,
        )
        defaults.update(kwargs)
        return BackupJob.objects.create(**defaults)

    def test_completed_restore_creates_restore_completed_notification_linked_to_status_page(self):
        job = self._job()
        notify_job_finished(job)
        notif = Notification.objects.get()
        self.assertEqual(notif.notification_type, NotificationType.RESTORE_COMPLETED)
        self.assertEqual(notif.title, "Restore completed")
        self.assertEqual(notif.recipient, self.superadmin)
        self.assertEqual(notif.link, reverse('backup:restore-status', args=[self.upload.id]))

    def test_completed_with_warnings_mentions_them(self):
        job = self._job(error_message="Restored with 1 warning(s): a.mp4: missing from the archive")
        notify_job_finished(job)
        notif = Notification.objects.get()
        self.assertEqual(notif.notification_type, NotificationType.RESTORE_COMPLETED)
        self.assertIn('warnings', notif.title)
        self.assertIn('a.mp4', notif.body)

    def test_failed_restore_creates_restore_failed_notification_with_reason(self):
        job = self._job(status=BackupJobStatus.FAILED, error_message="Restore failed: kaboom")
        notify_job_finished(job)
        notif = Notification.objects.get()
        self.assertEqual(notif.notification_type, NotificationType.RESTORE_FAILED)
        self.assertEqual(notif.title, "Restore failed")
        self.assertIn('kaboom', notif.body)
        self.assertEqual(notif.link, reverse('backup:restore-status', args=[self.upload.id]))

    def test_pre_restore_snapshot_job_never_notifies(self):
        snapshot = BackupJob.objects.create(
            job_type=BackupJobType.PRE_RESTORE_SNAPSHOT, status=BackupJobStatus.COMPLETED,
            scope=self.inst, trigger_institution=self.inst, triggered_by=self.superadmin,
        )
        notify_job_finished(snapshot)
        self.assertEqual(Notification.objects.count(), 0)

    def test_failed_pre_restore_snapshot_also_never_notifies(self):
        snapshot = BackupJob.objects.create(
            job_type=BackupJobType.PRE_RESTORE_SNAPSHOT, status=BackupJobStatus.FAILED,
            error_message="disk full", scope=self.inst, trigger_institution=self.inst,
            triggered_by=self.superadmin,
        )
        notify_job_finished(snapshot)
        self.assertEqual(Notification.objects.count(), 0)

    def test_restore_job_with_no_upload_links_to_restore_upload_page(self):
        # Defensive fallback: a restore job should always carry
        # `restore_upload`, but the link helper must not crash if it doesn't.
        job = self._job(restore_upload=None)
        notify_job_finished(job)
        notif = Notification.objects.get()
        self.assertEqual(notif.link, reverse('backup:restore-upload'))

    # ---- Story 2.5: date-scoped runs report their counts ----

    def _date_scoped(self, **overrides):
        result = {
            'mode': 'date_scoped', 'imported': 2, 'failed': [], 'skipped': 1, 'excluded': 0, 'media_warnings': [],
        }
        result.update(overrides)
        return self._job(restore_result=result)

    def test_clean_date_scoped_completion_reports_the_counts(self):
        notify_job_finished(self._date_scoped())
        notif = Notification.objects.get()
        self.assertEqual(notif.title, "Restore completed")
        self.assertEqual(notif.body, "Imported 2, skipped 1, excluded 0, failed 0.")

    def test_date_scoped_media_warnings_make_it_a_warning_and_are_counted_in_the_body(self):
        notify_job_finished(self._date_scoped(media_warnings=['archive patient 1: a.mp4: missing from the archive', 'x']))
        notif = Notification.objects.get()
        self.assertEqual(notif.notification_type, NotificationType.RESTORE_COMPLETED)
        self.assertEqual(notif.title, "Restore completed with warnings")
        self.assertEqual(notif.body, "Imported 2, skipped 1, excluded 0, failed 0. 2 media warning(s).")

    def test_date_scoped_failed_patients_and_media_warnings_are_both_counted(self):
        failed = [{'archive_pk': 4, 'identifiers': {'bht': 'B-4'}, 'reason': 'x'}]
        notify_job_finished(self._date_scoped(failed=failed, media_warnings=['w']))
        notif = Notification.objects.get()
        self.assertEqual(notif.title, "Restore completed with warnings")
        self.assertEqual(notif.body, "Imported 2, skipped 1, excluded 0, failed 1. 1 media warning(s).")

    def test_an_early_stop_is_a_warning_and_is_not_counted_as_a_failed_patient(self):
        abort = {'archive_pk': None, 'identifiers': {}, 'reason': 'the import stopped early: RuntimeError; 3 patient(s) were not imported'}
        notify_job_finished(self._date_scoped(imported=1, failed=[abort], aborted=True, not_attempted=3))
        notif = Notification.objects.get()
        self.assertEqual(notif.title, "Restore completed with warnings")
        self.assertEqual(
            notif.body, "Imported 1, skipped 1, excluded 0, failed 0. The import stopped early: 3 patient(s) were not imported.",
        )

    def test_ordinary_backup_notification_is_unaffected_by_the_restore_changes(self):
        job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP, status=BackupJobStatus.COMPLETED,
            scope=self.inst, trigger_institution=self.inst, triggered_by=self.superadmin,
        )
        notify_job_finished(job)
        notif = Notification.objects.get()
        self.assertEqual(notif.notification_type, NotificationType.BACKUP_COMPLETED)
        self.assertEqual(notif.link, reverse('backup:backup-create'))


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class NotificationReachesBellTest(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_bell_bk', password='Testpass1!', position='Administrator',
            mobile_primary='0770000311', user_type=UserType.SUPERADMIN,
            is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(name='Bell Bk Hosp', slug='bell-bk-hosp', created_by=self.superadmin)
        self.admin = User.objects.create_user(
            username='admin_bell_bk', password='Testpass1!', position='Administrator',
            mobile_primary='0770000312', user_type=UserType.ADMIN, institution=self.inst,
        )
        self.job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP, status=BackupJobStatus.COMPLETED,
            scope=self.inst, trigger_institution=self.inst, triggered_by=self.admin,
        )

    def test_bell_count_reflects_notification(self):
        notify_job_finished(self.job)
        client = Client()
        client.force_login(self.admin)
        response = client.get(reverse('referral:notification-count'))
        self.assertContains(response, 'navbar-badge')

    def test_panel_lists_notification_and_mark_read_redirects_to_backup_page(self):
        notify_job_finished(self.job)
        notif = Notification.objects.get()
        client = Client()
        client.force_login(self.admin)
        panel = client.get(reverse('referral:notification-panel'))
        self.assertContains(panel, 'Backup completed')
        response = client.post(reverse('referral:notification-mark-read', args=[notif.pk]))
        self.assertRedirects(response, reverse('backup:backup-create'), fetch_redirect_response=False)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_superadmin_sees_system_wide_notification_while_trigger_institution_is_active(self):
        job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP, status=BackupJobStatus.COMPLETED,
            scope=None, scope_type=BackupJobScopeType.SYSTEM,
            trigger_institution=self.inst, triggered_by=self.superadmin,
        )
        notify_job_finished(job)
        client = Client()
        client.force_login(self.superadmin)
        session = client.session
        session['active_institution_id'] = self.inst.id
        session.save()
        response = client.get(reverse('referral:notification-count'))
        self.assertContains(response, 'navbar-badge')
