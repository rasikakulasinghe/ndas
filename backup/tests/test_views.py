"""
backup/tests/test_views.py — Story 1.1

Covers the trigger-view half of the I/O matrix: permission gate, happy
path (job created + subprocess launched + response returns immediately),
concurrency lock, disk-space refusal, and subprocess-launch failure.

Rate limiting itself is `django_ratelimit`'s existing, separately-tested
behavior (see tests/test_security.py) — here we only need the endpoint to
be reachable with RATELIMIT_ENABLE=False, consistent with the rest of the
suite's convention.
"""
import shutil
import threading
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from backup.models import BackupJob
from backup.services import get_archive_dir
from institution.models import Institution
from ndas.custom_codes.choice import BackupJobStatus, UserType

User = get_user_model()

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

STATIC_OVERRIDE = override_settings(
    MULTI_INSTITUTION_ENABLED=True,
    RATELIMIT_ENABLE=False,
    STORAGES=TEST_STORAGES,
)

SUFFICIENT_DISK = (True, 0, 0, 10 ** 12)


@STATIC_OVERRIDE
class BackupTriggerViewTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_bk', password='Testpass1!', position='Administrator',
            mobile_primary='0770000010', user_type=UserType.SUPERADMIN,
            is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(
            name='Backup Hosp', slug='backup-hosp', created_by=self.superadmin,
        )
        self.admin = User.objects.create_user(
            username='admin_bk', password='Testpass1!', position='Administrator',
            mobile_primary='0770000011', user_type=UserType.ADMIN, institution=self.inst,
        )
        self.other_inst = Institution.objects.create(
            name='Other Hosp', slug='other-hosp', created_by=self.superadmin,
        )
        self.user = User.objects.create_user(
            username='user_bk', password='Testpass1!', position='Medical Officer',
            mobile_primary='0770000012', user_type=UserType.USER, institution=self.inst,
        )
        self.url = reverse('backup:backup-create')

    def tearDown(self):
        # The view creates BASE_DIR/backups/<job_id>/ (for the run_backup.log
        # file) as a real filesystem side effect even though Popen is mocked
        # in these tests -- clean it up so test runs don't litter the repo.
        for job in BackupJob.objects.all():
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)


class BackupTriggerAccessTest(BackupTriggerViewTestBase):
    def test_unauthenticated_redirected_to_login(self):
        response = Client().get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_non_admin_user_redirected_home_and_creates_no_job(self):
        client = Client()
        client.force_login(self.user)
        response = client.post(self.url)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertEqual(BackupJob.objects.count(), 0)

    def test_non_admin_user_get_also_redirected_home(self):
        # The permission gate runs before the GET/POST branch -- a non-admin
        # must be denied the trigger form itself, not just blocked from
        # submitting it (only the POST path had a test before review).
        client = Client()
        client.force_login(self.user)
        response = client.get(self.url)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_admin_can_view_trigger_form(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_superadmin_with_no_institution_context_denied_gracefully(self):
        # A superadmin with no active_institution_id in session never reaches
        # backup_create's own "no institution context" guard at all --
        # institution.middleware.InstitutionContextMiddleware already
        # redirects them to the institution selector first. Confirms the
        # request is denied gracefully (no raise, no job created) rather
        # than testing backup_create's own redirect('home') branch, which
        # is unreachable for superadmins via this codepath.
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.url)
        self.assertRedirects(
            response, reverse('institution:institution-selector'), fetch_redirect_response=False
        )
        self.assertEqual(BackupJob.objects.count(), 0)


class BackupTriggerHappyPathTest(BackupTriggerViewTestBase):
    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_post_creates_pending_job_and_launches_subprocess(self, mock_disk, mock_popen):
        client = Client()
        client.force_login(self.admin)
        response = client.post(self.url)

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        job = BackupJob.objects.get()
        self.assertEqual(job.status, BackupJobStatus.PENDING)
        self.assertEqual(job.triggered_by, self.admin)
        self.assertEqual(job.scope, self.inst)
        mock_popen.assert_called_once()

        # The command line handed to the subprocess names run_backup + this job's id.
        args = mock_popen.call_args[0][0]
        self.assertIn('run_backup', args)
        self.assertIn(str(job.id), args)

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_response_returns_immediately_without_running_export_inline(self, mock_disk, mock_popen):
        # Popen is mocked (never actually spawns/exports); the view still
        # completing with a normal redirect demonstrates the export never
        # runs synchronously inside the request.
        client = Client()
        client.force_login(self.admin)
        response = client.post(self.url)
        self.assertEqual(response.status_code, 302)


class BackupTriggerConcurrencyTest(BackupTriggerViewTestBase):
    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_second_trigger_refused_while_one_pending_no_new_row(self, mock_disk, mock_popen):
        BackupJob.objects.create(scope=self.inst, status=BackupJobStatus.PENDING, triggered_by=self.admin)

        client = Client()
        client.force_login(self.admin)
        client.post(self.url)

        self.assertEqual(BackupJob.objects.count(), 1)
        mock_popen.assert_not_called()

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_pending_job_in_other_institution_does_not_block(self, mock_disk, mock_popen):
        BackupJob.objects.create(scope=self.other_inst, status=BackupJobStatus.PENDING, triggered_by=self.admin)

        client = Client()
        client.force_login(self.admin)
        client.post(self.url)

        self.assertEqual(BackupJob.objects.filter(scope=self.inst).count(), 1)
        mock_popen.assert_called_once()


class BackupTriggerAtomicRaceTest(TransactionTestCase):
    """
    Real-thread concurrency test (TransactionTestCase does real commits,
    unlike TestCase's savepoint-per-test) -- the naive exists()-then-create()
    pattern this replaces let two near-simultaneous requests both pass the
    lock check before either row committed (flagged independently by three
    review passes). Best-effort: SQLite's own database-level write lock is
    what actually serializes the two threads here.
    """
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_bk_race', password='Testpass1!', position='Administrator',
            mobile_primary='0770000030', user_type=UserType.SUPERADMIN,
            is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(
            name='Race Hosp', slug='race-hosp', created_by=self.superadmin,
        )
        self.admin = User.objects.create_user(
            username='admin_bk_race', password='Testpass1!', position='Administrator',
            mobile_primary='0770000031', user_type=UserType.ADMIN, institution=self.inst,
        )
        self.url = reverse('backup:backup-create')

    def tearDown(self):
        for job in BackupJob.objects.all():
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)

    @override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False, STORAGES=TEST_STORAGES)
    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_two_simultaneous_triggers_create_exactly_one_job(self, mock_disk, mock_popen):
        barrier = threading.Barrier(2)

        def fire():
            try:
                client = Client()
                client.force_login(self.admin)
                barrier.wait(timeout=5)
                client.post(self.url)
            finally:
                # Each thread opens its own DB connection that Django never
                # auto-closes outside a real request/response cycle -- on
                # Windows, a lingering handle keeps the file-based test DB
                # locked and teardown_databases() fails to delete it.
                from django.db import connections
                connections.close_all()

        threads = [threading.Thread(target=fire) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(BackupJob.objects.filter(scope=self.inst).count(), 1)


class BackupTriggerDiskSpaceTest(BackupTriggerViewTestBase):
    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch(
        'backup.views.has_sufficient_disk_space',
        return_value=(False, 10 ** 12, 10 ** 12, 10),
    )
    def test_insufficient_disk_creates_failed_job_without_launching_subprocess(self, mock_disk, mock_popen):
        client = Client()
        client.force_login(self.admin)
        client.post(self.url)

        job = BackupJob.objects.get()
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertTrue(job.error_message)
        mock_popen.assert_not_called()


class BackupTriggerLaunchFailureTest(BackupTriggerViewTestBase):
    @mock.patch('backup.views.subprocess.Popen', side_effect=OSError('boom'))
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_popen_failure_marks_job_failed_with_launch_error(self, mock_disk, mock_popen):
        client = Client()
        client.force_login(self.admin)
        client.post(self.url)

        job = BackupJob.objects.get()
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertIn('boom', job.error_message)


@override_settings(
    MULTI_INSTITUTION_ENABLED=True,
    RATELIMIT_ENABLE=True,
    STORAGES=TEST_STORAGES,
)
class BackupTriggerRateLimitTest(TestCase):
    """
    Live rate-limit test (RATELIMIT_ENABLE=True, unlike every other test in
    this module, which disables it) -- the I/O matrix's 'rate limit
    exceeded' row needs an actual request rejected, not just decorator
    presence or a disabled-limiter smoke test.
    """
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # isolate this test's rate-limit counter from any other test's

        self.superadmin = User.objects.create_user(
            username='sa_bk_rl', password='Testpass1!', position='Administrator',
            mobile_primary='0770000020', user_type=UserType.SUPERADMIN,
            is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(
            name='Rate Limit Hosp', slug='rate-limit-hosp', created_by=self.superadmin,
        )
        self.admin = User.objects.create_user(
            username='admin_bk_rl', password='Testpass1!', position='Administrator',
            mobile_primary='0770000021', user_type=UserType.ADMIN, institution=self.inst,
        )
        self.url = reverse('backup:backup-create')

    def tearDown(self):
        for job in BackupJob.objects.all():
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_eleventh_request_in_a_minute_is_rejected(self, mock_disk, mock_popen):
        # NOTE: `settings.RATELIMIT_VIEW` (-> a friendly 429 page) is dead
        # configuration project-wide: it's only ever consulted by
        # `django_ratelimit.middleware.RatelimitMiddleware`, which isn't
        # registered in `MIDDLEWARE`. So `Ratelimited` (a `PermissionDenied`
        # subclass) falls through to Django's generic 403 handler instead --
        # true for every `@ratelimit`-decorated view in this codebase, not
        # something specific to backup_create. The throttling itself (the
        # 11th request being denied) works correctly either way; only the
        # error page shown is generic instead of the intended one. Asserting
        # 403 here documents the actual, current, codebase-wide behavior --
        # flagged to the user as a pre-existing gap, not fixed in this story.
        client = Client()
        client.force_login(self.admin)

        for _ in range(10):
            response = client.post(self.url)
            self.assertNotEqual(response.status_code, 403)

        response = client.post(self.url)
        self.assertEqual(response.status_code, 403)
