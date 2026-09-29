"""
backup/tests/test_download_views.py — Story 3.2: download a completed
backup's archive (`backup:backup-download` / `views.backup_download`).

Covers every row of the spec's I/O & Edge-Case Matrix: happy path for an
institutional admin and a super admin, a `pre_restore_snapshot` download by
a super admin (and its 404 for an institutional admin), non-`completed`
statuses 404, an out-of-scope job 404, an unknown pk / a `restore` job-type
404, a missing archive on disk (friendly refusal, no exception), the
non-admin and no-institution-context redirects, both `security.log` lines
(`assertLogs`), the rate limit, and that two downloads of the same archive
are each served independently without touching the file on disk.
"""
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
class BackupDownloadViewTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_dl', password='Testpass1!', position='Administrator',
            mobile_primary='0770000060', user_type=UserType.SUPERADMIN,
            is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='Download Hosp A', slug='download-hosp-a', created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Download Hosp B', slug='download-hosp-b', created_by=self.superadmin,
        )
        self.admin_a = User.objects.create_user(
            username='admin_dl_a', password='Testpass1!', position='Administrator',
            mobile_primary='0770000061', user_type=UserType.ADMIN, institution=self.inst_a,
        )
        self.user_a = User.objects.create_user(
            username='user_dl_a', password='Testpass1!', position='Medical Officer',
            mobile_primary='0770000062', user_type=UserType.USER, institution=self.inst_a,
        )
        # Transitional state (Story 3.1's own boundary): an admin with no
        # resolved institution context, mirroring pre-1.6 data.
        self.admin_no_inst = User.objects.create_user(
            username='admin_dl_none', password='Testpass1!', position='Administrator',
            mobile_primary='0770000063', user_type=UserType.ADMIN, institution=None,
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

    def _download_url(self, job_or_pk):
        pk = job_or_pk.pk if hasattr(job_or_pk, 'pk') else job_or_pk
        return reverse('backup:backup-download', args=[pk])

    def _get_and_close(self, client, url):
        """A completed download is a `FileResponse` wrapping an open file
        handle. Django's test client (`ClientHandler.__call__`) only releases
        it -- via `response.close()`, called through a disconnect/reconnect
        dance around the `request_finished` signal so the test's own DB
        connection is left alone -- once `streaming_content` is fully
        consumed. An un-drained 200 response leaves the archive file locked
        on Windows, so a later test's `shutil.rmtree` in `tearDown` silently
        no-ops (`ignore_errors=True`) and can leak a stale archive into a
        later test that reuses the same job id after its transaction rolls
        back. Every 200 response in these tests is fetched through this
        helper so the file is always fully drained (and released) before
        this test ends; the drained bytes are stashed at
        `response.download_content` for tests that need to check them."""
        response = client.get(url)
        if response.streaming:
            response.download_content = b''.join(response.streaming_content)
        return response

    def tearDown(self):
        for job in BackupJob.objects.all():
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)


class BackupDownloadAccessTest(BackupDownloadViewTestBase):
    def test_unauthenticated_redirected_to_login(self):
        job = self._make_job_with_archive()
        response = Client().get(self._download_url(job))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_non_admin_user_redirected_home_no_data_leaked_and_logged(self):
        job = self._make_job_with_archive()
        client = self._admin_client(self.user_a)
        with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            response = client.get(self._download_url(job))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertEqual(response.content, b'')
        self.assertTrue(any(self.user_a.username in line for line in logs.output))

    def test_admin_with_no_institution_context_redirected_home_and_logged(self):
        job = self._make_job_with_archive()
        client = self._admin_client(self.admin_no_inst)
        with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            response = client.get(self._download_url(job))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertTrue(any(self.admin_no_inst.username in line for line in logs.output))

    def test_post_is_405(self):
        """Review patch (P6): `@require_GET` rejects any other method."""
        job = self._make_job_with_archive()
        client = self._admin_client()
        response = client.post(self._download_url(job))
        self.assertEqual(response.status_code, 405)


class BackupDownloadHappyPathTest(BackupDownloadViewTestBase):
    def test_admin_downloads_completed_backup_within_scope(self):
        payload = b'archive-bytes-within-scope'
        job = self._make_job_with_archive(content=payload)
        client = self._admin_client()
        with self.assertLogs(SECURITY_LOGGER, level='INFO') as logs:
            response = self._get_and_close(client, self._download_url(job))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn(f'{job.id}', response['Content-Disposition'])
        self.assertEqual(response.download_content, payload)
        self.assertTrue(any(self.admin_a.username in line and str(job.id) in line for line in logs.output))
        # Review patch (P3): never cacheable -- this is a full backup archive.
        self.assertIn('no-store', response['Cache-Control'])
        # Review patch (P7): Content-Length must match the archive's actual
        # byte size, not just the streamed bytes.
        self.assertEqual(response['Content-Length'], str(len(payload)))
        self.assertEqual(int(response['Content-Length']), get_archive_path(job).stat().st_size)

    def test_superadmin_downloads_completed_backup(self):
        job = self._make_job_with_archive(
            scope_type=BackupJobScopeType.SINGLE, scope=self.inst_b, triggered_by=self.superadmin,
        )
        client = self._superadmin_client(self.inst_a)
        response = self._get_and_close(client, self._download_url(job))
        self.assertEqual(response.status_code, 200)

    def test_superadmin_downloads_pre_restore_snapshot(self):
        job = self._make_job_with_archive(
            job_type=BackupJobType.PRE_RESTORE_SNAPSHOT,
            scope_type=BackupJobScopeType.SINGLE, scope=self.inst_a, triggered_by=self.superadmin,
        )
        client = self._superadmin_client(self.inst_a)
        response = self._get_and_close(client, self._download_url(job))
        self.assertEqual(response.status_code, 200)
        self.assertIn('pre_restore_snapshot', response['Content-Disposition'])

    def test_two_downloads_of_the_same_archive_each_served_independently(self):
        payload = b'downloaded-twice'
        job = self._make_job_with_archive(content=payload)
        client = self._admin_client()

        first = self._get_and_close(client, self._download_url(job))
        self.assertEqual(first.download_content, payload)

        second = self._get_and_close(client, self._download_url(job))
        self.assertEqual(second.download_content, payload)

        # Never modified or moved by a download.
        self.assertEqual(get_archive_path(job).read_bytes(), payload)


class BackupDownloadRefusalTest(BackupDownloadViewTestBase):
    def test_pending_running_failed_statuses_are_404(self):
        client = self._admin_client()
        for status in (BackupJobStatus.PENDING, BackupJobStatus.RUNNING, BackupJobStatus.FAILED):
            with self.subTest(status=status):
                job = self._make_job(status=status)
                with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
                    response = client.get(self._download_url(job))
                self.assertEqual(response.status_code, 404)

    def test_out_of_scope_job_is_404_for_institutional_admin(self):
        job = self._make_job_with_archive(scope=self.inst_b, triggered_by=self.superadmin)
        client = self._admin_client()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = client.get(self._download_url(job))
        self.assertEqual(response.status_code, 404)

    def test_multi_scope_excluding_own_institution_is_404_for_institutional_admin(self):
        inst_c = Institution.objects.create(
            name='Download Hosp C', slug='download-hosp-c', created_by=self.superadmin,
        )
        job = self._make_job_with_archive(scope_type=BackupJobScopeType.MULTI, scope=None, triggered_by=self.superadmin)
        job.scopes.set([self.inst_b, inst_c])
        client = self._admin_client()
        response = client.get(self._download_url(job))
        self.assertEqual(response.status_code, 404)

    def test_pre_restore_snapshot_is_404_for_institutional_admin_even_in_own_scope(self):
        job = self._make_job_with_archive(
            job_type=BackupJobType.PRE_RESTORE_SNAPSHOT,
            scope_type=BackupJobScopeType.SINGLE, scope=self.inst_a,
        )
        client = self._admin_client()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = client.get(self._download_url(job))
        self.assertEqual(response.status_code, 404)

    def test_restore_job_type_is_404(self):
        job = self._make_job(job_type=BackupJobType.RESTORE, status=BackupJobStatus.COMPLETED)
        client = self._admin_client()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = client.get(self._download_url(job))
        self.assertEqual(response.status_code, 404)

        sa_client = self._superadmin_client(self.inst_a)
        response = sa_client.get(self._download_url(job))
        self.assertEqual(response.status_code, 404)

    def test_unknown_pk_is_404_and_logged(self):
        client = self._admin_client()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            response = client.get(self._download_url(999999))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(any('exists=False' in line for line in logs.output))

    def test_existence_check_failure_logs_exists_unknown_not_false(self):
        """Review patch (P4): a genuine failure while checking whether the job
        exists must not be silently folded into `exists=False` (which reads
        as a clean "no such job") -- it is logged as `exists=unknown`.

        Only `_log_backup_download_refused`'s own `.filter(pk=...)` call (no
        other kwargs) is made to fail -- `_history_jobs_for`'s unrelated
        `.filter(job_type=..., ...)` calls, used for the real scoped lookup
        earlier in the same request, must keep working normally."""
        client = self._admin_client()
        real_filter = BackupJob.objects.filter

        def flaky_filter(*args, **kwargs):
            if kwargs == {'pk': 999999}:
                raise Exception('db exploded')
            return real_filter(*args, **kwargs)

        with mock.patch('backup.views.BackupJob.objects.filter', side_effect=flaky_filter), \
                self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            response = client.get(self._download_url(999999))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(any('exists=unknown' in line for line in logs.output))
        self.assertFalse(any('exists=False' in line for line in logs.output))

    def test_missing_archive_on_disk_is_friendly_refusal_not_exception(self):
        job = self._make_job()  # completed, but no archive file ever written
        client = self._admin_client()
        with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
            response = client.get(self._download_url(job))
        self.assertRedirects(response, reverse('backup:backup-history'), fetch_redirect_response=False)
        self.assertTrue(any(str(job.id) in line for line in logs.output))

        response = client.get(response['Location'])
        self.assertContains(response, 'no longer available')

    def test_fstat_failure_after_successful_open_closes_the_handle(self):
        """Review patch (P1): `open()` can succeed and the subsequent
        `os.fstat()` can still raise (e.g. the file vanishes between the two
        calls) -- the already-open handle must be closed, not leaked, before
        the friendly refusal."""
        job = self._make_job_with_archive()
        client = self._admin_client()

        opened_files = []
        real_open = open

        def spy_open(*args, **kwargs):
            handle = real_open(*args, **kwargs)
            opened_files.append(handle)
            return handle

        with mock.patch('backup.views.open', side_effect=spy_open, create=True), \
                mock.patch('backup.views.os.fstat', side_effect=OSError('fstat boom')), \
                self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = client.get(self._download_url(job))

        self.assertRedirects(response, reverse('backup:backup-history'), fetch_redirect_response=False)
        self.assertEqual(len(opened_files), 1)
        self.assertTrue(
            opened_files[0].closed,
            "the archive file handle must be closed, not leaked, when os.fstat() fails after open()",
        )


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=True, STORAGES=TEST_STORAGES)
class BackupDownloadRateLimitTest(BackupDownloadViewTestBase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        super().setUp()

    def test_thirty_first_download_in_a_minute_is_rejected(self):
        job = self._make_job_with_archive()
        client = self._admin_client()
        url = self._download_url(job)
        for i in range(30):
            self.assertEqual(self._get_and_close(client, url).status_code, 200, f"request {i + 1}")
        self.assertEqual(client.get(url).status_code, 403)
