"""
backup/tests/test_views.py — Story 1.1, extended by Story 1.4 for the
optional date-range filter.

Covers the trigger-view half of the I/O matrix: permission gate, happy
path (job created + subprocess launched + response returns immediately),
concurrency lock, disk-space refusal, subprocess-launch failure, and (Story
1.4) the date-range filter -- available to every triggering user, refused
before any row is created when invalid, and never part of the overlap lock.

Rate limiting itself is `django_ratelimit`'s existing, separately-tested
behavior (see tests/test_security.py) — here we only need the endpoint to
be reachable with RATELIMIT_ENABLE=False, consistent with the rest of the
suite's convention.
"""
import shutil
import threading
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from backup.models import BackupJob
from backup.services import get_archive_dir
from institution.models import Institution
from ndas.custom_codes.choice import BackupJobScopeType, BackupJobStatus, UserType

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

    def test_admin_get_context_is_not_superadmin_but_has_scope_form_for_dates(self):
        # A non-superadmin ADMIN never gets the Story 1.2 scope-mode
        # selector (mode/institutions) -- confirmed separately below by
        # `test_admin_get_response_does_not_contain_scope_mode_radios`. But
        # Story 1.4's date-range fields live on this same `BackupScopeForm`
        # and are never privilege-gated, so `scope_form` itself is no
        # longer None for a non-superadmin (pre-1.4 behavior) -- the
        # template needs it to render/re-populate the date inputs for
        # every user.
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        self.assertFalse(response.context['is_superadmin'])
        self.assertIsNotNone(response.context['scope_form'])

    def test_admin_get_response_does_not_contain_scope_mode_radios(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        self.assertNotContains(response, 'id="ndas_scope_system"')
        self.assertNotContains(response, 'id="ndas_scope_multi"')
        self.assertNotContains(response, 'id="ndas_scope_single"')

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


@STATIC_OVERRIDE
class BackupScopeViewTestBase(TestCase):
    """
    Story 1.2 -- super-admin system-wide / explicit multi-institution scope
    selection, non-superadmin scope-elevation coercion, and the overlap lock.
    """

    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_scope1', password='Testpass1!', position='Administrator',
            mobile_primary='0770000040', user_type=UserType.SUPERADMIN,
            is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='Scope Hosp A', slug='scope-hosp-a', created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Scope Hosp B', slug='scope-hosp-b', created_by=self.superadmin,
        )
        self.inst_c = Institution.objects.create(
            name='Scope Hosp C', slug='scope-hosp-c', created_by=self.superadmin,
        )
        self.admin = User.objects.create_user(
            username='admin_scope1', password='Testpass1!', position='Administrator',
            mobile_primary='0770000041', user_type=UserType.ADMIN, institution=self.inst_a,
        )
        self.url = reverse('backup:backup-create')

    def _superadmin_client(self, active_institution):
        client = Client()
        client.force_login(self.superadmin)
        session = client.session
        session['active_institution_id'] = active_institution.id
        session.save()
        return client

    def tearDown(self):
        for job in BackupJob.objects.all():
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)


class BackupScopeSuperadminTriggerTest(BackupScopeViewTestBase):
    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_superadmin_system_wide_trigger_creates_system_job(self, mock_disk, mock_popen):
        client = self._superadmin_client(self.inst_a)
        response = client.post(self.url, {'mode': 'system'})

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        job = BackupJob.objects.get()
        self.assertEqual(job.scope_type, BackupJobScopeType.SYSTEM)
        self.assertIsNone(job.scope)
        self.assertEqual(job.scopes.count(), 0)
        mock_popen.assert_called_once()

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_superadmin_multi_trigger_creates_multi_job_with_selected_institutions(self, mock_disk, mock_popen):
        client = self._superadmin_client(self.inst_a)
        response = client.post(self.url, {
            'mode': 'multi',
            'institutions': [self.inst_a.id, self.inst_b.id],
        })

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        job = BackupJob.objects.get()
        self.assertEqual(job.scope_type, BackupJobScopeType.MULTI)
        self.assertIsNone(job.scope)
        self.assertSetEqual(
            set(job.scopes.values_list('id', flat=True)), {self.inst_a.id, self.inst_b.id}
        )
        mock_popen.assert_called_once()

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_superadmin_explicit_single_mode_scopes_to_own_institution(self, mock_disk, mock_popen):
        client = self._superadmin_client(self.inst_a)
        response = client.post(self.url, {'mode': 'single'})

        job = BackupJob.objects.get()
        self.assertEqual(job.scope_type, BackupJobScopeType.SINGLE)
        self.assertEqual(job.scope, self.inst_a)

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_superadmin_multi_with_empty_selection_rerenders_form_with_errors(self, mock_disk, mock_popen):
        # Refused before any row is created -- and, unlike a redirect, the
        # bound invalid scope_form is re-rendered (status 200) so the
        # template's error block is reachable and the user's picks (mode)
        # are preserved instead of lost.
        client = self._superadmin_client(self.inst_a)
        response = client.post(self.url, {'mode': 'multi', 'institutions': []})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['scope_form'].errors)
        self.assertContains(response, 'Select at least one institution')
        self.assertEqual(BackupJob.objects.count(), 0)
        mock_popen.assert_not_called()

    def test_superadmin_get_response_contains_scope_mode_radios(self):
        client = self._superadmin_client(self.inst_a)
        response = client.get(self.url)
        self.assertContains(response, 'id="ndas_scope_single"')
        self.assertContains(response, 'id="ndas_scope_multi"')
        self.assertContains(response, 'id="ndas_scope_system"')

    def test_superadmin_recent_jobs_listing_includes_own_multi_and_system_jobs(self):
        # scope=None for both -- filtering the GET listing on `scope=institution`
        # alone would hide these; the view must also match on `triggered_by`.
        system_job = BackupJob.objects.create(
            scope_type=BackupJobScopeType.SYSTEM, status=BackupJobStatus.COMPLETED,
            triggered_by=self.superadmin,
        )
        multi_job = BackupJob.objects.create(
            scope_type=BackupJobScopeType.MULTI, status=BackupJobStatus.COMPLETED,
            triggered_by=self.superadmin,
        )
        multi_job.scopes.set([self.inst_a, self.inst_b])

        client = self._superadmin_client(self.inst_a)
        response = client.get(self.url)

        self.assertEqual(response.status_code, 200)
        recent_ids = {job.id for job in response.context['recent_jobs']}
        self.assertIn(system_job.id, recent_ids)
        self.assertIn(multi_job.id, recent_ids)


class BackupScopeCoercionTest(BackupScopeViewTestBase):
    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_admin_crafted_system_scope_coerced_to_single_own_institution(self, mock_disk, mock_popen):
        # ADMIN (non-superadmin) crafts a POST claiming system-wide scope --
        # the trigger view must never trust it: coerced server-side to
        # single + the requester's own institution, no 403 (I/O matrix:
        # "Non-superadmin sends elevated scope").
        client = Client()
        client.force_login(self.admin)
        response = client.post(self.url, {
            'mode': 'system',
            'institutions': [self.inst_b.id, self.inst_c.id],
        })

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        job = BackupJob.objects.get()
        self.assertEqual(job.scope_type, BackupJobScopeType.SINGLE)
        self.assertEqual(job.scope, self.inst_a)
        self.assertEqual(job.scopes.count(), 0)

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_admin_crafted_multi_with_empty_institutions_never_refused(self, mock_disk, mock_popen):
        # Regression guard (Story 1.4): `BackupScopeForm` is now built and
        # validated for every submitter, including non-superadmins, because
        # start_date/end_date must be validated for everyone. But mode=multi
        # with no institutions selected trips `clean()`'s "Select at least
        # one institution" non-field ValidationError -- for a superadmin
        # that's a real refusal (see BackupScopeSuperadminTriggerTest), but
        # for a non-superadmin mode/institutions are inert content that gets
        # coerced away a few lines later regardless, so this must NOT
        # refuse the request. Mirrors
        # test_admin_crafted_system_scope_coerced_to_single_own_institution
        # above, but for the one payload shape that previously broke.
        client = Client()
        client.force_login(self.admin)
        response = client.post(self.url, {'mode': 'multi', 'institutions': []})

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        job = BackupJob.objects.get()
        self.assertEqual(job.scope_type, BackupJobScopeType.SINGLE)
        self.assertEqual(job.scope, self.inst_a)
        self.assertEqual(job.scopes.count(), 0)
        mock_popen.assert_called_once()


class BackupScopeOverlapLockTest(BackupScopeViewTestBase):
    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_system_wide_pending_blocks_any_new_single_trigger(self, mock_disk, mock_popen):
        BackupJob.objects.create(
            scope_type=BackupJobScopeType.SYSTEM, status=BackupJobStatus.PENDING,
            triggered_by=self.superadmin,
        )
        client = Client()
        client.force_login(self.admin)
        client.post(self.url)

        self.assertEqual(BackupJob.objects.filter(scope_type=BackupJobScopeType.SINGLE).count(), 0)
        mock_popen.assert_not_called()

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_new_system_wide_trigger_blocked_by_any_existing_pending_job(self, mock_disk, mock_popen):
        # system-wide overlaps every institution -- even one unrelated
        # single-institution pending job must block it.
        BackupJob.objects.create(
            scope_type=BackupJobScopeType.SINGLE, scope=self.inst_c, status=BackupJobStatus.PENDING,
            triggered_by=self.admin,
        )
        client = self._superadmin_client(self.inst_a)
        client.post(self.url, {'mode': 'system'})

        self.assertEqual(BackupJob.objects.filter(scope_type=BackupJobScopeType.SYSTEM).count(), 0)
        mock_popen.assert_not_called()

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_overlapping_multi_vs_multi_refused(self, mock_disk, mock_popen):
        pending = BackupJob.objects.create(
            scope_type=BackupJobScopeType.MULTI, status=BackupJobStatus.PENDING,
            triggered_by=self.superadmin,
        )
        pending.scopes.set([self.inst_a, self.inst_b])

        client = self._superadmin_client(self.inst_a)
        client.post(self.url, {'mode': 'multi', 'institutions': [self.inst_b.id, self.inst_c.id]})

        self.assertEqual(BackupJob.objects.filter(scope_type=BackupJobScopeType.MULTI).count(), 1)
        mock_popen.assert_not_called()

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_non_overlapping_multi_vs_multi_both_proceed(self, mock_disk, mock_popen):
        pending = BackupJob.objects.create(
            scope_type=BackupJobScopeType.MULTI, status=BackupJobStatus.PENDING,
            triggered_by=self.superadmin,
        )
        pending.scopes.set([self.inst_a])

        inst_d = Institution.objects.create(
            name='Scope Hosp D', slug='scope-hosp-d', created_by=self.superadmin,
        )

        client = self._superadmin_client(self.inst_a)
        client.post(self.url, {'mode': 'multi', 'institutions': [self.inst_b.id, inst_d.id]})

        self.assertEqual(BackupJob.objects.filter(scope_type=BackupJobScopeType.MULTI).count(), 2)
        mock_popen.assert_called_once()


class BackupScopeDiskCheckArgsTest(BackupScopeViewTestBase):
    """
    Every other POST test mocks `has_sufficient_disk_space` with a fixed
    return value and never checks what arguments it was called with -- a
    regression in `backup_create`'s `disk_check_scope` ternary (None /
    the institutions list / a single institution for system/multi/single)
    would ship silently. Assert the argument shape explicitly.
    """
    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_multi_post_calls_disk_check_with_full_institution_list(self, mock_disk, mock_popen):
        client = self._superadmin_client(self.inst_a)
        client.post(self.url, {
            'mode': 'multi',
            'institutions': [self.inst_a.id, self.inst_b.id],
        })

        mock_disk.assert_called_once()
        args, kwargs = mock_disk.call_args
        scope_arg = args[0] if args else kwargs.get('institution_or_institutions')
        self.assertIsInstance(scope_arg, list)
        self.assertSetEqual({inst.id for inst in scope_arg}, {self.inst_a.id, self.inst_b.id})
        self.assertFalse(kwargs.get('system_wide', False))

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_system_post_calls_disk_check_with_none_and_system_wide_true(self, mock_disk, mock_popen):
        client = self._superadmin_client(self.inst_a)
        client.post(self.url, {'mode': 'system'})

        mock_disk.assert_called_once()
        args, kwargs = mock_disk.call_args
        scope_arg = args[0] if args else kwargs.get('institution_or_institutions')
        self.assertIsNone(scope_arg)
        self.assertTrue(kwargs.get('system_wide'))

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_single_post_calls_disk_check_with_one_institution(self, mock_disk, mock_popen):
        client = self._superadmin_client(self.inst_a)
        client.post(self.url, {'mode': 'single'})

        mock_disk.assert_called_once()
        args, kwargs = mock_disk.call_args
        scope_arg = args[0] if args else kwargs.get('institution_or_institutions')
        self.assertEqual(scope_arg, self.inst_a)
        self.assertFalse(kwargs.get('system_wide', False))


class BackupScopeInsufficientDiskTest(BackupScopeViewTestBase):
    """
    The insufficient-disk failure path (which still creates a FAILED
    BackupJob for audit purposes) was only tested for the non-superadmin
    single-scope coercion case -- cover `multi` and `system` too.
    """
    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch(
        'backup.views.has_sufficient_disk_space',
        return_value=(False, 10 ** 12, 10 ** 12, 10),
    )
    def test_multi_insufficient_disk_creates_failed_job_with_scopes_populated(self, mock_disk, mock_popen):
        client = self._superadmin_client(self.inst_a)
        client.post(self.url, {
            'mode': 'multi',
            'institutions': [self.inst_a.id, self.inst_b.id],
        })

        job = BackupJob.objects.get()
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertEqual(job.scope_type, BackupJobScopeType.MULTI)
        self.assertIsNone(job.scope)
        self.assertSetEqual(
            set(job.scopes.values_list('id', flat=True)), {self.inst_a.id, self.inst_b.id}
        )
        mock_popen.assert_not_called()

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch(
        'backup.views.has_sufficient_disk_space',
        return_value=(False, 10 ** 12, 10 ** 12, 10),
    )
    def test_system_insufficient_disk_creates_failed_job_with_no_scopes(self, mock_disk, mock_popen):
        client = self._superadmin_client(self.inst_a)
        client.post(self.url, {'mode': 'system'})

        job = BackupJob.objects.get()
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertEqual(job.scope_type, BackupJobScopeType.SYSTEM)
        self.assertIsNone(job.scope)
        self.assertEqual(job.scopes.count(), 0)
        mock_popen.assert_not_called()


@STATIC_OVERRIDE
class BackupDateFilterViewTest(BackupTriggerViewTestBase):
    """
    Story 1.4 -- the date-range filter is available to any user who can
    trigger a backup (never superadmin-gated, unlike Story 1.2's scope-mode
    selection), refused before any row is created when `end_date <
    start_date`, and never participates in the overlap/concurrency lock.
    """

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_non_admin_superadmin_date_range_persisted_on_job(self, mock_disk, mock_popen):
        # Non-superadmin ADMIN, no mode/institutions submitted at all --
        # date filtering must work identically to a superadmin's submission.
        client = Client()
        client.force_login(self.admin)
        response = client.post(self.url, {'start_date': '2024-01-01', 'end_date': '2024-01-31'})

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        job = BackupJob.objects.get()
        self.assertEqual(job.scope_type, BackupJobScopeType.SINGLE)
        self.assertEqual(job.scope, self.inst)
        self.assertEqual(str(job.date_filter_start), '2024-01-01')
        self.assertEqual(str(job.date_filter_end), '2024-01-31')
        mock_popen.assert_called_once()

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_open_ended_start_only_persisted(self, mock_disk, mock_popen):
        client = Client()
        client.force_login(self.admin)
        client.post(self.url, {'start_date': '2024-05-01'})

        job = BackupJob.objects.get()
        self.assertEqual(str(job.date_filter_start), '2024-05-01')
        self.assertIsNone(job.date_filter_end)

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_no_dates_submitted_leaves_job_fields_null(self, mock_disk, mock_popen):
        # Omitting both dates must reproduce Stories 1.1-1.3's exact
        # behavior -- both fields stay null.
        client = Client()
        client.force_login(self.admin)
        client.post(self.url)

        job = BackupJob.objects.get()
        self.assertIsNone(job.date_filter_start)
        self.assertIsNone(job.date_filter_end)

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_end_before_start_refused_before_any_job_row_created(self, mock_disk, mock_popen):
        client = Client()
        client.force_login(self.admin)
        response = client.post(self.url, {'start_date': '2024-06-15', 'end_date': '2024-06-01'})

        # Bound-form re-render (status 200), not a redirect -- the user's
        # picks must not be lost.
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['scope_form'].errors)
        self.assertContains(response, 'End date cannot be before start date')
        self.assertEqual(BackupJob.objects.count(), 0)
        mock_popen.assert_not_called()

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_end_before_start_preserves_submitted_values_on_rerender(self, mock_disk, mock_popen):
        client = Client()
        client.force_login(self.admin)
        response = client.post(self.url, {'start_date': '2024-06-15', 'end_date': '2024-06-01'})

        self.assertContains(response, '2024-06-15')
        self.assertContains(response, '2024-06-01')

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_disk_check_called_with_resolved_date_bounds(self, mock_disk, mock_popen):
        client = Client()
        client.force_login(self.admin)
        client.post(self.url, {'start_date': '2024-01-01', 'end_date': '2024-01-31'})

        mock_disk.assert_called_once()
        _args, kwargs = mock_disk.call_args
        self.assertEqual(str(kwargs.get('date_start')), '2024-01-01')
        self.assertEqual(str(kwargs.get('date_end')), '2024-01-31')


@STATIC_OVERRIDE
class BackupDateFilterOverlapLockTest(BackupScopeViewTestBase):
    """
    Story 1.4 -- the date filter never participates in Story 1.2's overlap
    lock: two date-filtered jobs for the same/overlapping institutions still
    conflict regardless of their date ranges (institution-scope overlap is
    the only thing that matters).
    """

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_non_overlapping_date_ranges_same_institution_still_conflict(self, mock_disk, mock_popen):
        BackupJob.objects.create(
            scope=self.inst_a, status=BackupJobStatus.PENDING, triggered_by=self.admin,
            date_filter_start=date(2020, 1, 1), date_filter_end=date(2020, 1, 31),
        )

        client = Client()
        client.force_login(self.admin)
        client.post(self.url, {'start_date': '2024-01-01', 'end_date': '2024-01-31'})

        # Same institution, wildly different (non-overlapping) date ranges --
        # still refused. The overlap lock is institution-only.
        self.assertEqual(BackupJob.objects.filter(scope=self.inst_a).count(), 1)
        mock_popen.assert_not_called()

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_superadmin_multi_scope_combined_with_date_filter_persists_both(self, mock_disk, mock_popen):
        # Story 1.2's scope selection (superadmin-only) and Story 1.4's date
        # filter (never privilege-gated) are independent and compose freely.
        client = self._superadmin_client(self.inst_a)
        response = client.post(self.url, {
            'mode': 'multi',
            'institutions': [self.inst_a.id, self.inst_b.id],
            'start_date': '2024-03-01',
            'end_date': '2024-03-31',
        })

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        job = BackupJob.objects.get()
        self.assertEqual(job.scope_type, BackupJobScopeType.MULTI)
        self.assertSetEqual(
            set(job.scopes.values_list('id', flat=True)), {self.inst_a.id, self.inst_b.id}
        )
        self.assertEqual(str(job.date_filter_start), '2024-03-01')
        self.assertEqual(str(job.date_filter_end), '2024-03-31')


class BackupTriggerInstitutionTest(BackupScopeViewTestBase):
    """Story 1.5: `trigger_institution` is persisted on every job the view creates."""

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_admin_job_records_trigger_institution(self, mock_disk, mock_popen):
        client = Client()
        client.force_login(self.admin)
        client.post(self.url)
        self.assertEqual(BackupJob.objects.get().trigger_institution, self.inst_a)

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.views.has_sufficient_disk_space', return_value=SUFFICIENT_DISK)
    def test_superadmin_system_job_records_active_institution(self, mock_disk, mock_popen):
        client = self._superadmin_client(self.inst_b)
        client.post(self.url, {'mode': 'system'})
        job = BackupJob.objects.get()
        self.assertIsNone(job.scope)
        self.assertEqual(job.trigger_institution, self.inst_b)

    @mock.patch('backup.views.has_sufficient_disk_space', return_value=(False, 10, 20, 1))
    def test_insufficient_disk_failed_row_records_trigger_institution(self, mock_disk):
        client = Client()
        client.force_login(self.admin)
        client.post(self.url)
        job = BackupJob.objects.get()
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertEqual(job.trigger_institution, self.inst_a)


class BackupStatusViewTest(BackupScopeViewTestBase):
    """Story 1.5: the HTMX-polled `backup:backup-status` fragment."""

    def setUp(self):
        super().setUp()
        self.status_url = reverse('backup:backup-status')
        self.plain_user = User.objects.create_user(
            username='user_status1', password='Testpass1!', position='Medical Officer',
            mobile_primary='0770000042', user_type=UserType.USER, institution=self.inst_a,
        )

    def _job(self, status, institution=None, progress=0, **kwargs):
        return BackupJob.objects.create(
            job_type='backup', status=status, scope=institution or self.inst_a,
            trigger_institution=institution or self.inst_a, triggered_by=self.admin,
            progress_pct=progress, **kwargs,
        )

    def _get(self, user=None):
        client = Client()
        client.force_login(user or self.admin)
        return client.get(self.status_url)

    def test_active_job_renders_polling_trigger_and_progress(self):
        self._job(BackupJobStatus.RUNNING, progress=42)
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-trigger="every 5s"')
        self.assertContains(response, 'hx-swap="outerHTML"')
        self.assertContains(response, 'hx-get="%s"' % self.status_url)
        self.assertContains(response, 'width: 42%')

    def test_pending_job_also_polls(self):
        self._job(BackupJobStatus.PENDING)
        self.assertContains(self._get(), 'hx-trigger="every 5s"')

    def test_no_active_jobs_renders_no_polling_trigger(self):
        self._job(BackupJobStatus.COMPLETED, progress=100)
        self._job(BackupJobStatus.FAILED, error_message='Backup export failed: boom')
        response = self._get()
        self.assertNotContains(response, 'hx-trigger')
        self.assertNotContains(response, 'hx-get')

    def test_empty_state_renders_no_polling_trigger(self):
        response = self._get()
        self.assertContains(response, 'No backup jobs yet.')
        self.assertNotContains(response, 'hx-trigger')

    def test_running_job_at_99_shows_finalizing_label(self):
        self._job(BackupJobStatus.RUNNING, progress=99)
        self.assertContains(self._get(), 'Finalizing (verifying archive)')

    def test_running_job_below_99_has_no_finalizing_label(self):
        self._job(BackupJobStatus.RUNNING, progress=98)
        self.assertNotContains(self._get(), 'Finalizing')

    def test_completed_with_error_message_renders_as_warning(self):
        self._job(BackupJobStatus.COMPLETED, progress=100,
                  error_message='Completed with 1 media file(s) skipped: a.mp4')
        response = self._get()
        self.assertContains(response, 'badge-warning')
        self.assertContains(response, 'bg-warning')
        self.assertContains(response, 'text-dark')
        self.assertNotContains(response, 'text-danger')

    def test_failed_job_renders_error(self):
        self._job(BackupJobStatus.FAILED, error_message='Backup export failed: boom')
        response = self._get()
        self.assertContains(response, 'badge-danger')
        self.assertContains(response, 'text-danger')
        self.assertContains(response, 'Backup export failed: boom')

    def test_non_admin_gets_empty_403_with_no_job_data(self):
        self._job(BackupJobStatus.RUNNING, progress=10)
        response = self._get(self.plain_user)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b'')

    def test_unauthenticated_gets_204_with_hx_redirect_to_login(self):
        # Not a 302: htmx would follow it and swap the whole login page into
        # the card. HX-Redirect makes htmx navigate the full page instead.
        response = Client().get(self.status_url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response['HX-Redirect'], reverse('user-login'))
        self.assertEqual(response.content, b'')

    def test_post_to_status_endpoint_is_405(self):
        client = Client()
        client.force_login(self.admin)
        self.assertEqual(client.post(self.status_url).status_code, 405)

    def test_admin_without_any_institution_gets_empty_403(self):
        # A superadmin with no active institution is redirected by middleware
        # before the view runs, so exercise the view's own `institution is
        # None` branch directly.
        from django.test import RequestFactory
        from backup.views import backup_status

        no_inst_admin = User.objects.create_user(
            username='admin_noinst', password='Testpass1!', position='Administrator',
            mobile_primary='0770000043', user_type=UserType.ADMIN, institution=None,
        )
        request = RequestFactory().get(self.status_url)
        request.user = no_inst_admin
        response = backup_status(request)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b'')

    def test_invalid_post_rerender_still_lists_jobs_and_polls(self):
        job = self._job(BackupJobStatus.RUNNING, progress=37)
        client = Client()
        client.force_login(self.admin)
        response = client.post(self.url, {'start_date': '2024-06-15', 'end_date': '2024-06-01'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BackupJob.objects.count(), 1)  # refused: no new job row
        self.assertContains(response, 'id="backup-status"')
        self.assertContains(response, 'hx-trigger="every 5s"')
        self.assertContains(response, 'width: %d%%' % job.progress_pct)

    def test_other_institutions_jobs_never_appear_for_an_admin(self):
        self._job(BackupJobStatus.RUNNING, institution=self.inst_b, progress=77,
                  error_message='inst-b-secret')
        response = self._get()
        self.assertNotContains(response, 'inst-b-secret')
        self.assertNotContains(response, 'hx-trigger')
        self.assertContains(response, 'No backup jobs yet.')

    def test_superadmin_sees_own_system_wide_job(self):
        BackupJob.objects.create(
            job_type='backup', status=BackupJobStatus.RUNNING, scope=None,
            scope_type=BackupJobScopeType.SYSTEM, trigger_institution=self.inst_a,
            triggered_by=self.superadmin, progress_pct=30,
        )
        client = self._superadmin_client(self.inst_a)
        response = client.get(self.status_url)
        self.assertContains(response, 'width: 30%')
        self.assertContains(response, 'hx-trigger="every 5s"')

    def test_create_page_embeds_the_partial(self):
        self._job(BackupJobStatus.RUNNING, progress=5)
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        self.assertContains(response, 'id="backup-status"')
        self.assertContains(response, 'hx-trigger="every 5s"')


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=True, STORAGES=TEST_STORAGES)
class BackupStatusRateLimitTest(TestCase):
    """The status endpoint has its own 30/m limit (polled far more than 10/m)."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.superadmin = User.objects.create_user(
            username='sa_status_rl', password='Testpass1!', position='Administrator',
            mobile_primary='0770000050', user_type=UserType.SUPERADMIN,
            is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(name='Status RL Hosp', slug='status-rl-hosp', created_by=self.superadmin)
        self.admin = User.objects.create_user(
            username='admin_status_rl', password='Testpass1!', position='Administrator',
            mobile_primary='0770000051', user_type=UserType.ADMIN, institution=self.inst,
        )

    def test_thirty_polls_allowed_thirty_first_rejected(self):
        client = Client()
        client.force_login(self.admin)
        url = reverse('backup:backup-status')
        for _ in range(30):
            self.assertEqual(client.get(url).status_code, 200)
        self.assertEqual(client.get(url).status_code, 403)
