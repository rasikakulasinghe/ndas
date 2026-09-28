"""
backup/tests/test_history_views.py — Story 3.1: the dedicated, paginated
backup-history page (`backup:backup-history` / `views.backup_history`).

Covers every row of the spec's I/O & Edge-Case Matrix: institutional-admin
single/multi/system scoping, another institution's job excluded,
`pre_restore_snapshot` excluded for an institutional admin but included for
a superadmin, `restore` job-type excluded for everyone, pending/running
(live status, no size, visibly not downloadable), failed (no size),
completed with the archive present (size read from disk) and missing
("unavailable"), a deleted `triggered_by` ("System"), the empty state,
pagination (25/page, newest first), and the non-admin redirect.
"""
import re
import shutil
from datetime import datetime, time, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.template.defaultfilters import filesizeformat
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

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


def _set_created_at(pk, dt):
    """Force a specific `created_at` on an already-created BackupJob,
    bypassing `auto_now_add` (which only fires on INSERT via `.save()`,
    never on `.update()`) -- same bypass pattern as
    `backup/tests/test_services.py`'s `_set_created_at_date`."""
    BackupJob.objects.filter(pk=pk).update(created_at=dt)


@STATIC_OVERRIDE
class BackupHistoryViewTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_hist', password='Testpass1!', position='Administrator',
            mobile_primary='0770000050', user_type=UserType.SUPERADMIN,
            is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='History Hosp A', slug='history-hosp-a', created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='History Hosp B', slug='history-hosp-b', created_by=self.superadmin,
        )
        self.admin_a = User.objects.create_user(
            username='admin_hist_a', password='Testpass1!', position='Administrator',
            mobile_primary='0770000051', user_type=UserType.ADMIN, institution=self.inst_a,
        )
        self.user_a = User.objects.create_user(
            username='user_hist_a', password='Testpass1!', position='Medical Officer',
            mobile_primary='0770000052', user_type=UserType.USER, institution=self.inst_a,
        )
        self.url = reverse('backup:backup-history')

    def _admin_client(self):
        client = Client()
        client.force_login(self.admin_a)
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

    def tearDown(self):
        for job in BackupJob.objects.all():
            shutil.rmtree(get_archive_dir(job), ignore_errors=True)


class BackupHistoryAccessTest(BackupHistoryViewTestBase):
    def test_unauthenticated_redirected_to_login(self):
        response = Client().get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_non_admin_user_redirected_home_no_data_leaked(self):
        job = self._make_job()
        client = Client()
        client.force_login(self.user_a)
        response = client.get(self.url)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        # A bare redirect response has an empty body and renders no
        # template -- confirms the view actually returned early via
        # `redirect('home')` rather than rendering `backup/manager.html`
        # (with real content, just happening not to include 'page_obj') and
        # then also, separately, setting a redirect status/header.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.content, b'')

    def test_admin_can_view_history_page(self):
        client = self._admin_client()
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['is_superadmin'])

    def test_superadmin_with_no_institution_context_redirected_to_selector(self):
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.url)
        self.assertRedirects(
            response, reverse('institution:institution-selector'), fetch_redirect_response=False
        )


class BackupHistoryScopingTest(BackupHistoryViewTestBase):
    def test_institutional_admin_sees_single_scope_backup_of_own_institution(self):
        job = self._make_job(scope_type=BackupJobScopeType.SINGLE, scope=self.inst_a)
        client = self._admin_client()
        response = client.get(self.url)
        self.assertIn(job, list(response.context['page_obj']))

    def test_institutional_admin_sees_multi_scope_backup_including_own_institution(self):
        job = self._make_job(scope_type=BackupJobScopeType.MULTI, scope=None, triggered_by=self.superadmin)
        job.scopes.set([self.inst_a, self.inst_b])
        client = self._admin_client()
        response = client.get(self.url)
        self.assertIn(job, list(response.context['page_obj']))

    def test_institutional_admin_sees_system_wide_backup(self):
        job = self._make_job(scope_type=BackupJobScopeType.SYSTEM, scope=None, triggered_by=self.superadmin)
        client = self._admin_client()
        response = client.get(self.url)
        self.assertIn(job, list(response.context['page_obj']))

    def test_institutional_admin_does_not_see_another_institutions_single_scope_backup(self):
        job = self._make_job(scope_type=BackupJobScopeType.SINGLE, scope=self.inst_b, triggered_by=self.superadmin)
        client = self._admin_client()
        response = client.get(self.url)
        self.assertNotIn(job, list(response.context['page_obj']))

    def test_institutional_admin_does_not_see_multi_scope_backup_excluding_own_institution(self):
        inst_c = Institution.objects.create(
            name='History Hosp C', slug='history-hosp-c', created_by=self.superadmin,
        )
        job = self._make_job(scope_type=BackupJobScopeType.MULTI, scope=None, triggered_by=self.superadmin)
        job.scopes.set([self.inst_b, inst_c])
        client = self._admin_client()
        response = client.get(self.url)
        self.assertNotIn(job, list(response.context['page_obj']))

    def test_institutional_admin_never_sees_pre_restore_snapshot_even_in_own_scope(self):
        job = self._make_job(
            job_type=BackupJobType.PRE_RESTORE_SNAPSHOT,
            scope_type=BackupJobScopeType.SINGLE, scope=self.inst_a,
        )
        client = self._admin_client()
        response = client.get(self.url)
        self.assertNotIn(job, list(response.context['page_obj']))

    def test_no_one_sees_restore_job_type(self):
        restore_job = self._make_job(job_type=BackupJobType.RESTORE, scope_type=BackupJobScopeType.SINGLE, scope=self.inst_a)
        admin_response = self._admin_client().get(self.url)
        self.assertNotIn(restore_job, list(admin_response.context['page_obj']))

        sa_response = self._superadmin_client(self.inst_a).get(self.url)
        self.assertNotIn(restore_job, list(sa_response.context['page_obj']))

    def test_superadmin_sees_every_backup_and_pre_restore_snapshot_job_system_wide(self):
        job_a = self._make_job(scope_type=BackupJobScopeType.SINGLE, scope=self.inst_a)
        job_b = self._make_job(scope_type=BackupJobScopeType.SINGLE, scope=self.inst_b, triggered_by=self.superadmin)
        snapshot = self._make_job(
            job_type=BackupJobType.PRE_RESTORE_SNAPSHOT,
            scope_type=BackupJobScopeType.SINGLE, scope=self.inst_b, triggered_by=self.superadmin,
        )
        client = self._superadmin_client(self.inst_a)
        response = client.get(self.url)
        page_jobs = list(response.context['page_obj'])
        self.assertIn(job_a, page_jobs)
        self.assertIn(job_b, page_jobs)
        self.assertIn(snapshot, page_jobs)
        self.assertTrue(response.context['is_superadmin'])


class BackupHistoryColumnsTest(BackupHistoryViewTestBase):
    def test_pending_job_shows_live_status_no_size_not_downloadable(self):
        job = self._make_job(status=BackupJobStatus.PENDING, progress_pct=42)
        client = self._admin_client()
        response = client.get(self.url)
        job = list(response.context['page_obj'])[0]
        self.assertEqual(job.archive_size_bytes, None)
        self.assertContains(response, 'Not downloadable')
        self.assertContains(response, '42%')

    def test_running_job_shows_live_status_no_size_not_downloadable(self):
        self._make_job(status=BackupJobStatus.RUNNING, progress_pct=77)
        client = self._admin_client()
        response = client.get(self.url)
        job = list(response.context['page_obj'])[0]
        self.assertEqual(job.archive_size_bytes, None)
        self.assertContains(response, 'Not downloadable')

    def test_failed_job_shown_with_status_no_size(self):
        self._make_job(status=BackupJobStatus.FAILED, error_message='Disk full')
        client = self._admin_client()
        response = client.get(self.url)
        job = list(response.context['page_obj'])[0]
        self.assertEqual(job.status, BackupJobStatus.FAILED)
        self.assertIsNone(job.archive_size_bytes)

    def test_completed_job_size_read_from_disk(self):
        job = self._make_job(status=BackupJobStatus.COMPLETED)
        archive_path = get_archive_path(job)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        payload = b'x' * 1234
        archive_path.write_bytes(payload)

        client = self._admin_client()
        response = client.get(self.url)
        rendered_job = list(response.context['page_obj'])[0]
        self.assertEqual(rendered_job.archive_size_bytes, len(payload))
        # `filesizeformat` renders with a non-breaking space (e.g. "1.2\xa0KB")
        # -- compare against the filter's own output rather than a literal
        # regular-space string.
        self.assertContains(response, filesizeformat(len(payload)))

    def test_completed_job_missing_archive_shows_unavailable(self):
        self._make_job(status=BackupJobStatus.COMPLETED)  # no archive written to disk
        client = self._admin_client()
        response = client.get(self.url)
        job = list(response.context['page_obj'])[0]
        self.assertIsNone(job.archive_size_bytes)
        self.assertContains(response, 'unavailable')

    def test_deleted_triggered_by_shows_system(self):
        self._make_job(triggered_by=None)
        client = self._admin_client()
        response = client.get(self.url)
        self.assertContains(response, '>System<')

    def test_empty_state_shows_no_backup_jobs_yet(self):
        client = self._admin_client()
        response = client.get(self.url)
        self.assertContains(response, 'No backup jobs yet.')


class BackupHistoryPaginationTest(BackupHistoryViewTestBase):
    def test_pagination_25_per_page_newest_first(self):
        base = timezone.make_aware(datetime.combine(timezone.now().date(), time(8, 0)))
        jobs = []
        for i in range(30):
            job = self._make_job()
            jobs.append(job)
            _set_created_at(job.pk, base + timedelta(minutes=i))
        # Newest (highest offset) first.
        expected_order = list(reversed(jobs))

        client = self._admin_client()
        page1 = client.get(self.url)
        self.assertEqual(len(page1.context['page_obj']), 25)
        self.assertEqual(list(page1.context['page_obj']), expected_order[:25])

        page2 = client.get(self.url, {'page': 2})
        self.assertEqual(len(page2.context['page_obj']), 5)
        self.assertEqual(list(page2.context['page_obj']), expected_order[25:])

    def test_pagination_window_never_silently_drops_a_page(self):
        """
        Review patch pass (P1): the page-number window (current +/- 2) and
        its two ellipsis markers must be symmetric -- every page position is
        either a rendered link/active page, the collapsed endpoint (1 or the
        last page), or explicitly covered by a "..." marker. Before the fix,
        the left ellipsis trigger (`number|add:'-4'`) didn't match the left
        edge of the window (`number|add:'-3'`, mirroring the right side's
        `number|add:'3'`), so that one page silently rendered no link and no
        "..." at all (e.g. current page 9 of 10 rendered "1 ... 7 8 9 10",
        dropping page 6 with no marker).

        Walks the rendered pagination nav for two current pages (one with a
        gap on both sides, one with a gap on the left only) and asserts the
        extracted sequence of page-link tokens never has two consecutive
        numeric tokens more than 1 apart without an "..." token between them.
        """
        # 230 jobs -> ceil(230/25) == 10 pages -- enough room for a real gap
        # on both sides of a middle page.
        base = timezone.make_aware(datetime.combine(timezone.now().date(), time(6, 0)))
        for i in range(230):
            job = self._make_job()
            _set_created_at(job.pk, base + timedelta(minutes=i))

        client = self._admin_client()

        for current_page in (5, 9):
            with self.subTest(current_page=current_page):
                response = client.get(self.url, {'page': current_page})
                num_pages = response.context['page_obj'].paginator.num_pages
                self.assertEqual(num_pages, 10)

                html = response.content.decode('utf-8')
                nav_match = re.search(
                    r'<nav aria-label="Backup history pagination">.*?</nav>', html, re.DOTALL,
                )
                self.assertIsNotNone(nav_match, "Pagination nav not found in rendered HTML")
                nav_html = nav_match.group(0)

                tokens = re.findall(
                    r'class="page-link px-2[^"]*"[^>]*>\s*(\d+|&hellip;)\s*<', nav_html,
                )
                self.assertTrue(tokens, "No pagination page-number tokens found")

                numeric_tokens = [int(t) for t in tokens if t != '&hellip;']
                self.assertEqual(numeric_tokens[0], 1, "First rendered page must be page 1")
                self.assertEqual(
                    numeric_tokens[-1], num_pages, "Last rendered page must be the final page"
                )

                prev = None
                for tok in tokens:
                    if tok == '&hellip;':
                        prev = None  # gap explicitly marked -- reset adjacency check
                        continue
                    n = int(tok)
                    if prev is not None:
                        self.assertLessEqual(
                            n - prev, 1,
                            f"Page(s) between rendered pages {prev} and {n} were silently "
                            f"dropped with no '...' marker (viewing page {current_page})."
                        )
                    prev = n
