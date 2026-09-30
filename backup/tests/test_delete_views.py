"""
backup/tests/test_delete_views.py — Story 3.3: delete an individual backup
(`backup:backup-delete` / `views.backup_delete`).

Covers every row of the spec's I/O & Edge-Case Matrix: institutional-admin
and super-admin happy paths (including a `pre_restore_snapshot`), an
out-of-scope job 404, wrong password, `pending`/`running` refusal,
`restore`-type-job refusal, snapshot-in-use refusal (including the
TOCTOU-fix race window), a missing archive on disk still succeeding, a
genuine archive-removal `OSError` returning 500 and keeping the row, a
double-delete race, the non-admin/no-institution-context denial, a
non-dict JSON body, `manager.html`'s delete-affordance visibility, both
log outcomes, and the rate limit.
"""
import json
import shutil
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from backup.models import BackupJob
from backup.services import get_archive_dir, get_archive_path
from institution.models import Institution
from ndas.custom_codes.choice import (
    BackupJobScopeType, BackupJobStatus, BackupJobType, UserType,
)

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

SECURITY_LOGGER = 'django.security.restore'


@STATIC_OVERRIDE
class BackupDeleteViewTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_del', password='Testpass1!', position='Administrator',
            mobile_primary='0770000070', user_type=UserType.SUPERADMIN,
            is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='Delete Hosp A', slug='delete-hosp-a', created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Delete Hosp B', slug='delete-hosp-b', created_by=self.superadmin,
        )
        self.admin_a = User.objects.create_user(
            username='admin_del_a', password='Testpass1!', position='Administrator',
            mobile_primary='0770000071', user_type=UserType.ADMIN, institution=self.inst_a,
        )
        self.user_a = User.objects.create_user(
            username='user_del_a', password='Testpass1!', position='Medical Officer',
            mobile_primary='0770000072', user_type=UserType.USER, institution=self.inst_a,
        )
        self.admin_no_inst = User.objects.create_user(
            username='admin_del_none', password='Testpass1!', position='Administrator',
            mobile_primary='0770000073', user_type=UserType.ADMIN, institution=None,
        )

    def _admin_client(self, user=None):
        client = Client()
        client.force_login(user or self.admin_a)
        return client

    def _superadmin_client(self, active_institution):
        client = Client()
        client.force_login(self.superadmin)
        session = client.session
        session['active_institution_id'] = active_institution.id
        session.save()
        return client

    def _make_job(self, **overrides):
        fields = dict(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.COMPLETED,
            scope_type=BackupJobScopeType.SINGLE,
            scope=self.inst_a,
            trigger_institution=self.inst_a,
            triggered_by=self.admin_a,
        )
        fields.update(overrides)
        return BackupJob.objects.create(**fields)

    def _make_job_with_archive(self, content=b'zip-bytes', **overrides):
        job = self._make_job(**overrides)
        archive_path = get_archive_path(job)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_bytes(content)
        return job

    def _delete_url(self, job_or_pk):
        pk = job_or_pk.pk if hasattr(job_or_pk, 'pk') else job_or_pk
        return reverse('backup:backup-delete', args=[pk])

    def _delete(self, client, job_or_pk, password='Testpass1!', body=None):
        if body is None:
            body = {'password': password}
        return client.delete(
            self._delete_url(job_or_pk),
            data=json.dumps(body),
            content_type='application/json',
        )

    def tearDown(self):
        for job in BackupJob.objects.all():
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)


class BackupDeleteAccessTest(BackupDeleteViewTestBase):
    def test_non_admin_denied_json_403_and_logged(self):
        job = self._make_job_with_archive()
        client = self._admin_client(self.user_a)
        with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            response = self._delete(client, job, password='Testpass1!')
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertTrue(any(self.user_a.username in line for line in logs.output))
        self.assertTrue(BackupJob.objects.filter(pk=job.pk).exists())

    def test_admin_with_no_institution_context_denied_json_403_and_logged(self):
        job = self._make_job_with_archive()
        client = self._admin_client(self.admin_no_inst)
        with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            response = self._delete(client, job)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()['success'])
        self.assertTrue(any(self.admin_no_inst.username in line for line in logs.output))

    def test_get_method_not_allowed(self):
        job = self._make_job_with_archive()
        client = self._admin_client()
        response = client.get(self._delete_url(job))
        self.assertEqual(response.status_code, 405)

    def test_unauthenticated_redirected_to_login(self):
        job = self._make_job_with_archive()
        response = self._delete(Client(), job)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])


class BackupDeleteHappyPathTest(BackupDeleteViewTestBase):
    def test_institutional_admin_deletes_own_completed_backup(self):
        job = self._make_job_with_archive()
        archive_dir = get_archive_dir(job)
        self.assertTrue(archive_dir.exists())
        client = self._admin_client()
        with self.assertLogs(SECURITY_LOGGER, level='INFO') as logs:
            response = self._delete(client, job)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['redirect_url'], reverse('backup:backup-history'))
        self.assertFalse(BackupJob.objects.filter(pk=job.pk).exists())
        self.assertFalse(archive_dir.exists())
        self.assertTrue(any(self.admin_a.username in line and str(job.id) in line for line in logs.output))

    def test_institutional_admin_deletes_failed_backup(self):
        job = self._make_job_with_archive(status=BackupJobStatus.FAILED)
        client = self._admin_client()
        response = self._delete(client, job)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BackupJob.objects.filter(pk=job.pk).exists())

    def test_superadmin_deletes_any_institutions_backup(self):
        job = self._make_job_with_archive(scope=self.inst_b, triggered_by=self.superadmin)
        client = self._superadmin_client(self.inst_a)
        response = self._delete(client, job)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BackupJob.objects.filter(pk=job.pk).exists())

    def test_superadmin_deletes_pre_restore_snapshot_not_in_use(self):
        job = self._make_job_with_archive(
            job_type=BackupJobType.PRE_RESTORE_SNAPSHOT,
            scope=self.inst_a, triggered_by=self.superadmin,
        )
        client = self._superadmin_client(self.inst_a)
        response = self._delete(client, job)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BackupJob.objects.filter(pk=job.pk).exists())

    def test_missing_archive_on_disk_still_succeeds(self):
        job = self._make_job()  # completed, but no archive ever written
        client = self._admin_client()
        response = self._delete(client, job)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BackupJob.objects.filter(pk=job.pk).exists())


class BackupDeleteRefusalTest(BackupDeleteViewTestBase):
    def test_wrong_password_refused_401_nothing_deleted_and_logged(self):
        job = self._make_job_with_archive()
        client = self._admin_client()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            response = self._delete(client, job, password='WrongPass!')
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()['success'])
        self.assertTrue(BackupJob.objects.filter(pk=job.pk).exists())
        self.assertTrue(any(self.admin_a.username in line for line in logs.output))

    def test_missing_password_is_400(self):
        job = self._make_job_with_archive()
        client = self._admin_client()
        response = self._delete(client, job, body={})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(BackupJob.objects.filter(pk=job.pk).exists())

    def test_non_dict_json_body_is_400_not_500(self):
        """Patch fix: a valid-JSON-but-non-dict body (e.g. a bare list or
        number) must return 400, not raise AttributeError."""
        job = self._make_job_with_archive()
        client = self._admin_client()
        for body in ([1, 2, 3], 42, "just a string", None):
            with self.subTest(body=body):
                response = client.delete(
                    self._delete_url(job), data=json.dumps(body), content_type='application/json',
                )
                self.assertEqual(response.status_code, 400)
        self.assertTrue(BackupJob.objects.filter(pk=job.pk).exists())

    def test_invalid_json_body_is_400(self):
        job = self._make_job_with_archive()
        client = self._admin_client()
        response = client.delete(self._delete_url(job), data='not-json', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_pending_and_running_jobs_refused_400(self):
        client = self._admin_client()
        for status in (BackupJobStatus.PENDING, BackupJobStatus.RUNNING):
            with self.subTest(status=status):
                job = self._make_job(status=status)
                with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
                    response = self._delete(client, job)
                self.assertEqual(response.status_code, 400)
                self.assertTrue(BackupJob.objects.filter(pk=job.pk).exists())

    def test_restore_type_job_refused_400_even_when_completed(self):
        """Job-type scope: a restore-type job, even completed/failed, is
        refused (Story 2.6's audit trail) -- distinct from a plain 404."""
        job = self._make_job(
            job_type=BackupJobType.RESTORE, status=BackupJobStatus.COMPLETED,
            scope=self.inst_a, trigger_institution=self.inst_a,
        )
        client = self._admin_client()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            response = self._delete(client, job)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(BackupJob.objects.filter(pk=job.pk).exists())
        self.assertTrue(any('restore' in line.lower() for line in logs.output))

        sa_client = self._superadmin_client(self.inst_a)
        response = sa_client.delete(
            self._delete_url(job), data=json.dumps({'password': 'Testpass1!'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_snapshot_in_use_refused_400(self):
        snapshot = self._make_job_with_archive(
            job_type=BackupJobType.PRE_RESTORE_SNAPSHOT, scope=self.inst_a, triggered_by=self.superadmin,
        )
        BackupJob.objects.create(
            job_type=BackupJobType.RESTORE, status=BackupJobStatus.RUNNING,
            scope_type=BackupJobScopeType.SINGLE, scope=self.inst_a,
            trigger_institution=self.inst_a, triggered_by=self.superadmin,
            pre_restore_snapshot=snapshot,
        )
        client = self._superadmin_client(self.inst_a)
        with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            response = self._delete(client, snapshot)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(BackupJob.objects.filter(pk=snapshot.pk).exists())
        self.assertTrue(any('snapshot' in line.lower() for line in logs.output))

    def test_snapshot_becomes_deletable_once_restore_finishes(self):
        snapshot = self._make_job_with_archive(
            job_type=BackupJobType.PRE_RESTORE_SNAPSHOT, scope=self.inst_a, triggered_by=self.superadmin,
        )
        BackupJob.objects.create(
            job_type=BackupJobType.RESTORE, status=BackupJobStatus.COMPLETED,
            scope_type=BackupJobScopeType.SINGLE, scope=self.inst_a,
            trigger_institution=self.inst_a, triggered_by=self.superadmin,
            pre_restore_snapshot=snapshot,
        )
        client = self._superadmin_client(self.inst_a)
        response = self._delete(client, snapshot)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BackupJob.objects.filter(pk=snapshot.pk).exists())

    def test_snapshot_in_use_guard_sees_a_restore_attached_after_the_row_was_first_fetched(self):
        """Race-fix (TOCTOU): the in-use check must re-query live state
        immediately before the delete, not rely on anything computed earlier
        in the request (e.g. when the history page was last rendered).
        Simulated here by fetching/rendering the snapshot's row first (as a
        user browsing the history page would), *then* attaching a new
        pending restore to it, and only *then* attempting the delete -- the
        guard must still catch it."""
        snapshot = self._make_job_with_archive(
            job_type=BackupJobType.PRE_RESTORE_SNAPSHOT, scope=self.inst_a, triggered_by=self.superadmin,
        )
        client = self._superadmin_client(self.inst_a)

        # Equivalent of the user having loaded the history page (no restore
        # using this snapshot yet -- it would show as deletable at this
        # point).
        self.assertFalse(
            BackupJob.objects.filter(
                pre_restore_snapshot=snapshot, status__in=(BackupJobStatus.PENDING, BackupJobStatus.RUNNING),
            ).exists()
        )

        # A restore now attaches to the snapshot between that page load and
        # the delete click.
        BackupJob.objects.create(
            job_type=BackupJobType.RESTORE, status=BackupJobStatus.PENDING,
            scope_type=BackupJobScopeType.SINGLE, scope=self.inst_a,
            trigger_institution=self.inst_a, triggered_by=self.superadmin,
            pre_restore_snapshot=snapshot,
        )

        response = self._delete(client, snapshot)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(BackupJob.objects.filter(pk=snapshot.pk).exists())

    def test_institutional_admin_cannot_delete_snapshot_scoped_to_own_institution(self):
        """AD-14 regression guard: a `pre_restore_snapshot` row is
        super-admin-only regardless of scope, even when it is completed,
        scoped to the institutional admin's own institution, and not
        backing any active restore. Must be refused (403), row must still
        exist -- an institutional admin must never be able to delete a
        snapshot."""
        snapshot = self._make_job_with_archive(
            job_type=BackupJobType.PRE_RESTORE_SNAPSHOT,
            scope=self.inst_a, triggered_by=self.superadmin,
        )
        client = self._admin_client()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            response = self._delete(client, snapshot)
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertTrue(BackupJob.objects.filter(pk=snapshot.pk).exists())
        self.assertTrue(any(self.admin_a.username in line for line in logs.output))

    def test_archive_removal_failure_returns_500_and_keeps_row(self):
        job = self._make_job_with_archive()
        client = self._admin_client()
        with mock.patch('backup.views.shutil.rmtree', side_effect=OSError('disk fault')), \
                self.assertLogs(SECURITY_LOGGER, level='ERROR'):
            response = self._delete(client, job)
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.json()['success'])
        self.assertTrue(BackupJob.objects.filter(pk=job.pk).exists())

    def test_out_of_scope_job_is_404_for_institutional_admin(self):
        job = self._make_job_with_archive(scope=self.inst_b, triggered_by=self.superadmin)
        client = self._admin_client()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            response = self._delete(client, job)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['success'])
        self.assertTrue(BackupJob.objects.filter(pk=job.pk).exists())
        self.assertTrue(any('exists=True' in line for line in logs.output))

    def test_unknown_pk_is_404_and_logged(self):
        client = self._admin_client()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            response = self._delete(client, 999999)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(any('exists=False' in line for line in logs.output))

    def test_double_delete_race_second_request_sees_404(self):
        job = self._make_job_with_archive()
        client = self._admin_client()
        first = self._delete(client, job)
        self.assertEqual(first.status_code, 200)
        second = self._delete(client, job)
        self.assertEqual(second.status_code, 404)
        self.assertFalse(second.json()['success'])


class BackupDeleteManagerTemplateTest(BackupDeleteViewTestBase):
    def test_completed_non_restore_row_shows_delete_affordance(self):
        self._make_job_with_archive(status=BackupJobStatus.COMPLETED)
        client = self._admin_client()
        response = client.get(reverse('backup:backup-history'))
        self.assertContains(response, 'delete-trigger-btn')

    def test_failed_non_restore_row_shows_delete_affordance(self):
        self._make_job(status=BackupJobStatus.FAILED)
        client = self._admin_client()
        response = client.get(reverse('backup:backup-history'))
        self.assertContains(response, 'delete-trigger-btn')

    def test_pending_and_running_rows_have_no_delete_affordance(self):
        client = self._admin_client()
        for status in (BackupJobStatus.PENDING, BackupJobStatus.RUNNING):
            with self.subTest(status=status):
                BackupJob.objects.all().delete()
                self._make_job(status=status)
                response = client.get(reverse('backup:backup-history'))
                self.assertNotContains(response, 'delete-trigger-btn')

    def test_restore_type_rows_never_listed_so_never_show_delete_affordance(self):
        """`_history_jobs_for` never lists a restore-type row at all, so it
        can never show a delete affordance either."""
        self._make_job(job_type=BackupJobType.RESTORE, status=BackupJobStatus.COMPLETED)
        client = self._admin_client()
        response = client.get(reverse('backup:backup-history'))
        self.assertNotContains(response, 'delete-trigger-btn')


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=True, STORAGES=TEST_STORAGES)
class BackupDeleteRateLimitTest(BackupDeleteViewTestBase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        super().setUp()

    def test_sixth_delete_in_a_minute_is_rejected(self):
        """A rate-limit breach raises `Ratelimited` (a `PermissionDenied`
        subclass); `handle_view_errors`'s own `except PermissionDenied`
        branch (not this view's code) turns that into a redirect to 'home'
        -- the same accepted behavior `patient_delete` already relies on
        (Code Map patch note), not a JSON refusal."""
        client = self._admin_client()
        jobs = [self._make_job_with_archive() for _ in range(6)]
        for i, job in enumerate(jobs[:5]):
            response = self._delete(client, job)
            self.assertEqual(response.status_code, 200, f"request {i + 1}")
        response = self._delete(client, jobs[5])
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertTrue(BackupJob.objects.filter(pk=jobs[5].pk).exists())
