"""
backup/tests/test_restore_views.py -- Story 2.1

The upload/status views: super-admin-only gates (and their security-log
entries), form-level rejections that stage nothing and create no row, the
one-validating-upload rule, replace-on-new-upload, launch/staging failure,
`404` for someone else's upload, the self-terminating polling trigger, and the
sidebar entries.
"""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, OperationalError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from backup import restore_validation
from backup.models import BackupJob, RestoreUpload
from backup.restore_validation import get_restore_uploads_root, get_upload_dir, get_upload_path
from backup.tests.restore_helpers import IsolatedBaseDirMixin, sha256_bytes, zip_bytes
from institution.models import Institution
from ndas.custom_codes.choice import RestoreAuthenticity, RestoreRejectionCode, RestoreUploadStatus, UserType

User = get_user_model()

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

SECURITY_LOGGER = 'django.security.restore'


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False, STORAGES=TEST_STORAGES)
class RestoreViewTestBase(IsolatedBaseDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.superadmin = User.objects.create_user(
            username='sa_rs', password='Testpass1!', position='Administrator',
            mobile_primary='0770000401', user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.other_superadmin = User.objects.create_user(
            username='sa_rs2', password='Testpass1!', position='Administrator',
            mobile_primary='0770000402', user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(name='Restore Hosp', slug='restore-hosp', created_by=self.superadmin)
        self.admin = User.objects.create_user(
            username='admin_rs', password='Testpass1!', position='Administrator',
            mobile_primary='0770000403', user_type=UserType.ADMIN, institution=self.inst,
        )
        self.user = User.objects.create_user(
            username='user_rs', password='Testpass1!', position='Medical Officer',
            mobile_primary='0770000404', user_type=UserType.USER, institution=self.inst,
        )
        self.url = reverse('backup:restore-upload')

    def client_for(self, user, active_institution=True):
        client = Client()
        client.force_login(user)
        if user.user_type == UserType.SUPERADMIN and active_institution:
            session = client.session
            session['active_institution_id'] = self.inst.id
            session.save()
        return client

    def make_upload(self, user=None, status=RestoreUploadStatus.VALIDATING, staged=True, **kwargs):
        upload = RestoreUpload.objects.create(
            uploaded_by=user or self.superadmin, original_filename='b.zip', status=status, **kwargs,
        )
        if staged:
            get_upload_dir(upload).mkdir(parents=True, exist_ok=True)
            get_upload_path(upload).write_bytes(b"staged")
        return upload

    def post_archive(self, client, content=None, name='backup.zip', **data):
        content = content if content is not None else zip_bytes()
        return client.post(self.url, {
            'archive': SimpleUploadedFile(name, content, content_type='application/zip'),
            **data,
        })

    def assertNothingStaged(self):
        root = get_restore_uploads_root()
        self.assertFalse(root.exists() and any(root.iterdir()), "bytes were staged")

    def assertNoRowNoBytes(self):
        self.assertEqual(RestoreUpload.objects.count(), 0)
        self.assertNothingStaged()


class RestoreAccessTest(RestoreViewTestBase):
    def test_anonymous_redirected_to_login(self):
        for url in (self.url, reverse('backup:restore-status', args=[1])):
            response = Client().get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn('login', response['Location'])

    def test_anonymous_fragment_poll_gets_204_with_hx_redirect(self):
        response = Client().get(reverse('backup:restore-status-fragment', args=[1]))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response['HX-Redirect'], reverse('user-login'))

    @mock.patch('backup.views.subprocess.Popen')
    def test_non_superadmins_denied_on_upload_get_and_post(self, mock_popen):
        for user in (self.admin, self.user):
            with self.subTest(user=user.username):
                client = self.client_for(user)
                with self.assertLogs(SECURITY_LOGGER, level='WARNING') as logs:
                    response = client.get(self.url)
                self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
                self.assertTrue(any(user.username in line for line in logs.output))

                with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
                    response = self.post_archive(client)
                self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
                self.assertNoRowNoBytes()
        mock_popen.assert_not_called()

    def test_non_superadmin_denied_on_status_page_even_for_an_existing_upload(self):
        upload = self.make_upload()
        client = self.client_for(self.admin)
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = client.get(reverse('backup:restore-status', args=[upload.id]))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_non_superadmin_fragment_is_empty_403(self):
        upload = self.make_upload()
        client = self.client_for(self.admin)
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            response = client.get(reverse('backup:restore-status-fragment', args=[upload.id]))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b'')

    def test_superadmin_without_active_institution_goes_to_selector(self):
        client = self.client_for(self.superadmin, active_institution=False)
        response = client.get(self.url)
        self.assertRedirects(response, reverse('institution:institution-selector'), fetch_redirect_response=False)
        self.assertNoRowNoBytes()

    def test_superadmin_sees_upload_form_with_size_limit(self):
        response = self.client_for(self.superadmin).get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Maximum upload size')
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'Allow unverified origin')

    def test_get_shows_link_to_latest_upload(self):
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATED)
        response = self.client_for(self.superadmin).get(self.url)
        self.assertContains(response, reverse('backup:restore-status', args=[upload.id]))


class RestoreFormRejectionTest(RestoreViewTestBase):
    def assertRejectedInRequest(self, response, needle):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, needle)
        self.assertNoRowNoBytes()

    @mock.patch('backup.views.subprocess.Popen')
    def test_wrong_extension(self, mock_popen):
        client = self.client_for(self.superadmin)
        for name in ('backup.tar.gz', 'backup.exe', 'backup', 'backup.zip.txt'):
            with self.subTest(name=name):
                response = self.post_archive(client, name=name)
                self.assertRejectedInRequest(response, 'Only .zip')
        mock_popen.assert_not_called()

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.forms.detect_file_mime', return_value='application/x-dosexec')
    def test_wrong_content_type(self, mock_mime, mock_popen):
        response = self.post_archive(self.client_for(self.superadmin), content=b'MZ' + b'\0' * 100)
        self.assertRejectedInRequest(response, 'not a zip archive')
        mock_popen.assert_not_called()

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.forms.detect_file_mime', return_value=None)
    def test_undetectable_content_falls_through(self, mock_mime, mock_popen):
        response = self.post_archive(self.client_for(self.superadmin))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RestoreUpload.objects.count(), 1)

    @mock.patch('backup.views.subprocess.Popen')
    def test_too_large(self, mock_popen):
        limits = {**settings.FILE_UPLOAD_LIMITS, 'RESTORE_ARCHIVE_MAX_SIZE': 10}
        with override_settings(FILE_UPLOAD_LIMITS=limits):
            response = self.post_archive(self.client_for(self.superadmin), content=zip_bytes())
        self.assertRejectedInRequest(response, 'too large')
        mock_popen.assert_not_called()

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.forms.restore_validation.has_sufficient_restore_space', return_value=(False, 10 ** 9, 5))
    def test_not_enough_disk(self, mock_space, mock_popen):
        response = self.post_archive(self.client_for(self.superadmin))
        self.assertRejectedInRequest(response, 'Not enough free disk space')
        mock_popen.assert_not_called()

    @mock.patch('backup.views.subprocess.Popen')
    @mock.patch('backup.forms.restore_validation.has_sufficient_restore_space', side_effect=OSError('boom'))
    def test_disk_probe_failure_is_a_form_error(self, mock_space, mock_popen):
        response = self.post_archive(self.client_for(self.superadmin))
        self.assertRejectedInRequest(response, 'Could not verify available disk space')

    def test_missing_file(self):
        response = self.client_for(self.superadmin).post(self.url, {})
        self.assertEqual(response.status_code, 200)
        self.assertNoRowNoBytes()

    def test_form_rejection_is_logged_to_security_log(self):
        with self.assertLogs(SECURITY_LOGGER, level='WARNING'):
            self.post_archive(self.client_for(self.superadmin), name='backup.exe')

    def test_disk_check_requires_upload_plus_margin(self):
        with mock.patch('backup.restore_validation.shutil.disk_usage') as usage:
            usage.return_value = mock.Mock(free=1000 + restore_validation.DISK_SAFETY_MINIMUM_BYTES)
            self.assertTrue(restore_validation.has_sufficient_restore_space(1000)[0])
            self.assertFalse(restore_validation.has_sufficient_restore_space(1001)[0])


class RestoreUploadHappyPathTest(RestoreViewTestBase):
    @mock.patch('backup.views.subprocess.Popen')
    def test_upload_stages_hashes_and_launches_validation(self, mock_popen):
        content = zip_bytes()
        client = self.client_for(self.superadmin)
        response = self.post_archive(client, content=content, allow_unverified='on')

        upload = RestoreUpload.objects.get()
        self.assertRedirects(
            response, reverse('backup:restore-status', args=[upload.id]), fetch_redirect_response=False,
        )
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATING)
        self.assertEqual(upload.uploaded_by, self.superadmin)
        self.assertEqual(upload.original_filename, 'backup.zip')
        self.assertEqual(upload.size_bytes, len(content))
        self.assertEqual(upload.archive_sha256, sha256_bytes(content))
        self.assertTrue(upload.allow_unverified)

        staged = get_upload_path(upload)
        self.assertEqual(staged, self.base_dir / 'restore_uploads' / str(upload.id) / 'upload.zip')
        self.assertEqual(staged.read_bytes(), content)

        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertIn('validate_restore_upload', args)
        self.assertIn(str(upload.id), args)
        self.assertTrue((get_upload_dir(upload) / 'validate_restore_upload.log').exists())

    @mock.patch('backup.views.subprocess.Popen')
    def test_box_unticked_is_recorded(self, mock_popen):
        self.post_archive(self.client_for(self.superadmin))
        self.assertFalse(RestoreUpload.objects.get().allow_unverified)

    @mock.patch('backup.views.subprocess.Popen')
    def test_filename_is_sanitized(self, mock_popen):
        self.post_archive(self.client_for(self.superadmin), name='../../evil name.zip')
        upload = RestoreUpload.objects.get()
        self.assertNotIn('..', upload.original_filename)
        self.assertNotIn('/', upload.original_filename)


class RestoreConcurrencyAndReplacementTest(RestoreViewTestBase):
    @mock.patch('backup.views.subprocess.Popen')
    def test_second_upload_refused_while_one_is_validating(self, mock_popen):
        self.make_upload(status=RestoreUploadStatus.VALIDATING)
        response = self.post_archive(self.client_for(self.superadmin))
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.assertEqual(RestoreUpload.objects.count(), 1)
        mock_popen.assert_not_called()
        root = get_restore_uploads_root()
        self.assertEqual(len(list(root.iterdir())), 1)  # only the pre-existing upload's dir

    @mock.patch('backup.views.subprocess.Popen')
    def test_another_super_admins_validating_upload_does_not_block(self, mock_popen):
        self.make_upload(user=self.other_superadmin, status=RestoreUploadStatus.VALIDATING)
        response = self.post_archive(self.client_for(self.superadmin))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RestoreUpload.objects.filter(uploaded_by=self.superadmin).count(), 1)

    @mock.patch('backup.views.subprocess.Popen')
    def test_new_upload_replaces_earlier_finished_uploads(self, mock_popen):
        finished = [
            self.make_upload(status=status)
            for status in (RestoreUploadStatus.VALIDATED, RestoreUploadStatus.REJECTED, RestoreUploadStatus.FAILED)
        ]
        theirs = self.make_upload(user=self.other_superadmin, status=RestoreUploadStatus.VALIDATED)
        old_dirs = [get_upload_dir(u) for u in finished]

        self.post_archive(self.client_for(self.superadmin))

        for upload, old_dir in zip(finished, old_dirs):
            self.assertFalse(RestoreUpload.objects.filter(pk=upload.pk).exists())
            self.assertFalse(old_dir.exists())
        self.assertTrue(RestoreUpload.objects.filter(pk=theirs.pk).exists())
        self.assertTrue(get_upload_path(theirs).exists())
        new = RestoreUpload.objects.get(uploaded_by=self.superadmin)
        self.assertEqual(new.status, RestoreUploadStatus.VALIDATING)
        self.assertTrue(get_upload_path(new).exists())


class RestoreFailureTest(RestoreViewTestBase):
    @mock.patch('backup.views.subprocess.Popen', side_effect=OSError('cannot spawn'))
    def test_popen_failure_marks_failed_and_deletes_staged_file(self, mock_popen):
        response = self.post_archive(self.client_for(self.superadmin))
        upload = RestoreUpload.objects.get()
        self.assertRedirects(
            response, reverse('backup:restore-status', args=[upload.id]), fetch_redirect_response=False,
        )
        self.assertEqual(upload.status, RestoreUploadStatus.FAILED)
        self.assertIn('cannot spawn', upload.error_message)
        self.assertFalse(get_upload_path(upload).exists())

    @mock.patch('backup.views.subprocess.Popen')
    def test_staging_failure_marks_failed_and_cleans_up(self, mock_popen):
        with mock.patch('backup.views.restore_validation.stage_upload', side_effect=OSError('disk gone')):
            response = self.post_archive(self.client_for(self.superadmin))
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        upload = RestoreUpload.objects.get()
        self.assertEqual(upload.status, RestoreUploadStatus.FAILED)
        self.assertIn('disk gone', upload.error_message)
        self.assertNothingStaged()
        mock_popen.assert_not_called()

    @mock.patch('backup.views.subprocess.Popen')
    def test_failed_upload_does_not_block_the_next_one(self, mock_popen):
        with mock.patch('backup.views.restore_validation.stage_upload', side_effect=OSError('x')):
            self.post_archive(self.client_for(self.superadmin))
        response = self.post_archive(self.client_for(self.superadmin))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RestoreUpload.objects.count(), 1)  # the failed one was replaced


class RestoreStatusViewTest(RestoreViewTestBase):
    def test_other_super_admin_gets_404_on_page_and_fragment(self):
        upload = self.make_upload()
        client = self.client_for(self.other_superadmin)
        self.assertEqual(client.get(reverse('backup:restore-status', args=[upload.id])).status_code, 404)
        self.assertEqual(client.get(reverse('backup:restore-status-fragment', args=[upload.id])).status_code, 404)

    def test_unknown_upload_is_404(self):
        client = self.client_for(self.superadmin)
        self.assertEqual(client.get(reverse('backup:restore-status', args=[99999])).status_code, 404)

    def test_validating_fragment_polls_itself(self):
        upload = self.make_upload(progress_pct=40)
        client = self.client_for(self.superadmin)
        fragment_url = reverse('backup:restore-status-fragment', args=[upload.id])

        page = client.get(reverse('backup:restore-status', args=[upload.id]))
        self.assertContains(page, 'hx-trigger="every 5s"')
        self.assertContains(page, fragment_url)

        fragment = client.get(fragment_url)
        self.assertContains(fragment, 'hx-trigger="every 5s"')
        self.assertContains(fragment, 'aria-valuenow="40"')

    def test_finished_fragment_stops_polling(self):
        client = self.client_for(self.superadmin)
        for status in (RestoreUploadStatus.VALIDATED, RestoreUploadStatus.REJECTED, RestoreUploadStatus.FAILED):
            with self.subTest(status=status):
                upload = self.make_upload(status=status, staged=False)
                fragment_url = reverse('backup:restore-status-fragment', args=[upload.id])
                for url in (
                    reverse('backup:restore-status-fragment', args=[upload.id]),
                    reverse('backup:restore-status', args=[upload.id]),
                ):
                    response = client.get(url)
                    self.assertEqual(response.status_code, 200)
                    # (the page's base layout has its own unrelated hx-trigger)
                    self.assertNotContains(response, f'hx-get="{fragment_url}"')
                    self.assertNotContains(response, 'hx-trigger="every 5s"')

    def test_rejected_upload_shows_specific_error(self):
        upload = self.make_upload(
            status=RestoreUploadStatus.REJECTED, staged=False,
            error_code=RestoreRejectionCode.SCHEMA_MISMATCH,
            error_message='Schema version mismatch: archive aaa but this database is bbb.',
        )
        response = self.client_for(self.superadmin).get(reverse('backup:restore-status', args=[upload.id]))
        self.assertContains(response, 'Archive rejected')
        self.assertContains(response, 'Schema version mismatch: archive aaa but this database is bbb.')
        self.assertContains(response, 'schema_mismatch')

    def test_validated_upload_shows_manifest_summary(self):
        summary = {
            'source_job_id': 77, 'manifest_version': 1, 'schema_version': 'f' * 64, 'scope_type': 'multi',
            'institutions': ['alpha', 'beta'], 'record_counts': {'patients.patient': 12},
            'date_filter': {'applied': True, 'start': '2026-01-01', 'end': None},
            'generated_at': '2026-09-20T10:00:00+00:00', 'generated_by': 'someone',
        }
        upload = self.make_upload(
            status=RestoreUploadStatus.VALIDATED, staged=True, progress_pct=100,
            authenticity=RestoreAuthenticity.VERIFIED, source_job_id=77, manifest_summary=summary,
        )
        response = self.client_for(self.superadmin).get(reverse('backup:restore-status', args=[upload.id]))
        self.assertContains(response, 'Archive validated')
        self.assertContains(response, 'verified against backup job 77')
        self.assertContains(response, 'alpha, beta')
        self.assertContains(response, 'patients.patient')
        self.assertContains(response, '2026-01-01')

    def test_unverified_origin_is_flagged(self):
        upload = self.make_upload(
            status=RestoreUploadStatus.VALIDATED, staged=True, progress_pct=100,
            authenticity=RestoreAuthenticity.UNVERIFIED, source_job_id=5,
            manifest_summary={
                'source_job_id': 5, 'manifest_version': 1, 'schema_version': 'x', 'scope_type': 'single',
                'institutions': [], 'record_counts': {}, 'date_filter': {'applied': False, 'start': None, 'end': None},
                'generated_at': 't', 'generated_by': '',
            },
        )
        response = self.client_for(self.superadmin).get(reverse('backup:restore-status', args=[upload.id]))
        self.assertContains(response, 'unverified')

    def test_untrusted_manifest_text_is_escaped(self):
        upload = self.make_upload(
            status=RestoreUploadStatus.REJECTED, staged=False,
            error_code='file_missing', error_message="<script>alert('x')</script>",
        )
        response = self.client_for(self.superadmin).get(reverse('backup:restore-status', args=[upload.id]))
        self.assertNotContains(response, "<script>alert('x')</script>")


class RestoreSidebarTest(RestoreViewTestBase):
    BACKUP_URL = '/backup/'

    def _home(self, client):
        response = client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        return response

    def test_superadmin_with_active_institution_sees_backup_and_restore(self):
        response = self._home(self.client_for(self.superadmin))
        self.assertContains(response, f'href="{reverse("backup:backup-create")}"')
        self.assertContains(response, f'href="{reverse("backup:restore-upload")}"')

    def test_institution_admin_sees_backup_but_not_restore(self):
        response = self._home(self.client_for(self.admin))
        self.assertContains(response, f'href="{reverse("backup:backup-create")}"')
        self.assertNotContains(response, f'href="{reverse("backup:restore-upload")}"')

    def test_clinician_sees_neither(self):
        response = self._home(self.client_for(self.user))
        self.assertNotContains(response, f'href="{reverse("backup:backup-create")}"')
        self.assertNotContains(response, f'href="{reverse("backup:restore-upload")}"')

    def test_superadmin_without_active_institution_sees_neither(self):
        client = self.client_for(self.superadmin, active_institution=False)
        response = client.get(reverse('institution:institution-selector'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'href="{reverse("backup:backup-create")}"')
        self.assertNotContains(response, f'href="{reverse("backup:restore-upload")}"')


class RestoreConstraintAndRaceTest(RestoreViewTestBase):
    def test_db_rejects_a_second_validating_upload_for_one_user(self):
        RestoreUpload.objects.create(uploaded_by=self.superadmin, status=RestoreUploadStatus.VALIDATING)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RestoreUpload.objects.create(uploaded_by=self.superadmin, status=RestoreUploadStatus.VALIDATING)

    def test_constraint_only_covers_validating_rows_of_the_same_user(self):
        RestoreUpload.objects.create(uploaded_by=self.superadmin, status=RestoreUploadStatus.VALIDATING)
        RestoreUpload.objects.create(uploaded_by=self.other_superadmin, status=RestoreUploadStatus.VALIDATING)
        for status in (RestoreUploadStatus.VALIDATED, RestoreUploadStatus.REJECTED, RestoreUploadStatus.FAILED):
            RestoreUpload.objects.create(uploaded_by=self.superadmin, status=status)
        self.assertEqual(RestoreUpload.objects.count(), 5)

    @mock.patch('backup.views.subprocess.Popen')
    def test_lost_race_is_reported_as_busy(self, mock_popen):
        # Simulate two concurrent POSTs: the friendly pre-check passes for
        # this request (it ran before the other one committed) but the DB
        # constraint catches it.
        self.make_upload(status=RestoreUploadStatus.VALIDATING)
        with mock.patch('backup.views.RestoreUpload.objects.filter') as fake_filter:
            fake_filter.return_value.exists.return_value = False
            response = self.post_archive(self.client_for(self.superadmin))
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.assertEqual(RestoreUpload.objects.count(), 1)
        mock_popen.assert_not_called()
        self.assertEqual(len(list(get_restore_uploads_root().iterdir())), 1)

    @mock.patch('backup.views.subprocess.Popen')
    def test_lost_race_shows_the_busy_message(self, mock_popen):
        self.make_upload(status=RestoreUploadStatus.VALIDATING)
        client = self.client_for(self.superadmin)
        with mock.patch('backup.views.RestoreUpload.objects.filter') as fake_filter:
            fake_filter.return_value.exists.return_value = False
            self.post_archive(client)
        response = client.get(self.url)
        self.assertContains(response, 'already have an upload being validated')


class RestorePreLaunchFailureTest(RestoreViewTestBase):
    @mock.patch('backup.views.subprocess.Popen')
    def test_any_exception_between_create_and_launch_marks_failed_and_cleans_up(self, mock_popen):
        with mock.patch.object(restore_validation, 'delete_finished_uploads', side_effect=RuntimeError('boom')):
            response = self.post_archive(self.client_for(self.superadmin))
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        upload = RestoreUpload.objects.get()
        self.assertEqual(upload.status, RestoreUploadStatus.FAILED)
        self.assertIn('boom', upload.error_message)
        self.assertFalse(get_upload_dir(upload).exists())
        mock_popen.assert_not_called()

    @mock.patch('backup.views.subprocess.Popen')
    def test_row_save_failure_after_staging_also_marks_failed(self, mock_popen):
        original_save = RestoreUpload.save

        def flaky_save(instance, *args, **kwargs):
            if 'archive_sha256' in (kwargs.get('update_fields') or ()):
                raise OperationalError('database is locked')
            return original_save(instance, *args, **kwargs)

        with mock.patch.object(RestoreUpload, 'save', autospec=True, side_effect=flaky_save):
            response = self.post_archive(self.client_for(self.superadmin))
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        upload = RestoreUpload.objects.get()
        self.assertEqual(upload.status, RestoreUploadStatus.FAILED)
        self.assertNothingStaged()

    @mock.patch('backup.views.subprocess.Popen')
    def test_user_is_not_locked_out_after_a_pre_launch_failure(self, mock_popen):
        with mock.patch.object(restore_validation, 'delete_finished_uploads', side_effect=RuntimeError('boom')):
            self.post_archive(self.client_for(self.superadmin))
        response = self.post_archive(self.client_for(self.superadmin))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RestoreUpload.objects.get().status, RestoreUploadStatus.VALIDATING)


class RestoreReplacementSafetyTest(RestoreViewTestBase):
    @mock.patch('backup.views.subprocess.Popen')
    def test_failed_reupload_leaves_the_earlier_validated_upload_intact(self, mock_popen):
        earlier = self.make_upload(status=RestoreUploadStatus.VALIDATED)
        with mock.patch.object(restore_validation, 'stage_upload', side_effect=OSError('disk gone')):
            self.post_archive(self.client_for(self.superadmin))
        self.assertTrue(RestoreUpload.objects.filter(pk=earlier.pk, status=RestoreUploadStatus.VALIDATED).exists())
        self.assertTrue(get_upload_path(earlier).exists())

    @mock.patch('backup.views.subprocess.Popen', side_effect=OSError('cannot spawn'))
    def test_failed_launch_still_replaces_only_after_staging_succeeded(self, mock_popen):
        earlier = self.make_upload(status=RestoreUploadStatus.VALIDATED)
        self.post_archive(self.client_for(self.superadmin))
        # staging succeeded, so the earlier upload was replaced; the new row is failed
        self.assertFalse(RestoreUpload.objects.filter(pk=earlier.pk).exists())
        self.assertEqual(RestoreUpload.objects.get().status, RestoreUploadStatus.FAILED)

    @mock.patch('backup.views.subprocess.Popen')
    def test_row_is_kept_when_its_files_cannot_be_removed_and_retried_next_time(self, mock_popen):
        stuck = self.make_upload(status=RestoreUploadStatus.VALIDATED)
        client = self.client_for(self.superadmin)
        content = zip_bytes()  # built before rmtree is patched (the helper uses it)

        with mock.patch('backup.restore_validation.shutil.rmtree', side_effect=PermissionError('locked')):
            with self.assertLogs('backup.restore_validation', level='WARNING') as logs:
                response = self.post_archive(client, content=content)
        self.assertEqual(response.status_code, 302)  # the new upload still proceeds
        self.assertTrue(RestoreUpload.objects.filter(pk=stuck.pk).exists())
        self.assertTrue(get_upload_path(stuck).exists())
        self.assertTrue(any(str(stuck.id) in line for line in logs.output))

        # The new upload finishes; the next upload retries the cleanup.
        new = RestoreUpload.objects.exclude(pk=stuck.pk).get()
        RestoreUpload.objects.filter(pk=new.pk).update(status=RestoreUploadStatus.VALIDATED)
        self.post_archive(client)
        self.assertFalse(RestoreUpload.objects.filter(pk=stuck.pk).exists())
        self.assertFalse(get_upload_dir(stuck).exists())

    def test_delete_finished_uploads_treats_an_already_missing_dir_as_removed(self):
        gone = self.make_upload(status=RestoreUploadStatus.REJECTED, staged=False)
        restore_validation.delete_finished_uploads(self.superadmin)
        self.assertFalse(RestoreUpload.objects.filter(pk=gone.pk).exists())


class RestoreStagingIsolationTest(RestoreViewTestBase):
    @mock.patch('backup.views.subprocess.Popen')
    def test_staged_path_is_outside_media_and_static_roots(self, mock_popen):
        self.post_archive(self.client_for(self.superadmin))
        staged = get_upload_path(RestoreUpload.objects.get())
        self.assertTrue(staged.exists())
        self.assertTrue(staged.is_relative_to(self.base_dir))
        self.assertEqual(Path(settings.MEDIA_ROOT), self.media_root)
        self.assertEqual(Path(settings.STATIC_ROOT), self.static_root)
        self.assertFalse(staged.is_relative_to(self.media_root))
        self.assertFalse(staged.is_relative_to(self.static_root))
        self.assertFalse(self.media_root.exists())


class RestoreStatusRenderingHardeningTest(RestoreViewTestBase):
    def summary(self, **overrides):
        base = {
            'source_job_id': 5, 'manifest_version': 1, 'schema_version': 'f' * 64, 'scope_type': 'single',
            'institutions': ['alpha'], 'record_counts': {'patients.patient': 3},
            'date_filter': {'applied': False, 'start': None, 'end': None},
            'generated_at': '2026-09-20T10:00:00+00:00', 'generated_by': 'someone',
        }
        base.update(overrides)
        return base

    def validated(self, authenticity=RestoreAuthenticity.VERIFIED, **overrides):
        return self.make_upload(
            status=RestoreUploadStatus.VALIDATED, progress_pct=100, authenticity=authenticity,
            source_job_id=5, manifest_summary=self.summary(**overrides),
        )

    def get_page(self, upload, fragment=False):
        name = 'backup:restore-status-fragment' if fragment else 'backup:restore-status'
        return self.client_for(self.superadmin).get(reverse(name, args=[upload.id]))

    def test_record_counts_with_an_items_key_does_not_crash_page_or_fragment(self):
        upload = self.validated(record_counts={'items': 1, 'values': 2, 'keys': 3})
        for fragment in (False, True):
            with self.subTest(fragment=fragment):
                response = self.get_page(upload, fragment=fragment)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'items')

    def test_legit_summary_renders_sorted_record_counts(self):
        upload = self.validated(record_counts={'video.video': 2, 'patients.patient': 7})
        response = self.get_page(upload)
        content = response.content.decode()
        self.assertLess(content.index('patients.patient'), content.index('video.video'))
        self.assertEqual(response.context['record_counts'], [('patients.patient', 7), ('video.video', 2)])

    def test_manifest_summary_values_are_html_escaped(self):
        upload = self.validated(
            institutions=['<b>evil</b>'], generated_by='<script>alert(1)</script>',
            scope_type='<img src=x>', generated_at='<i>t</i>',
            record_counts={'<u>x</u>': 1},
            date_filter={'applied': True, 'start': '<s>a</s>', 'end': None},
        )
        for fragment in (False, True):
            with self.subTest(fragment=fragment):
                response = self.get_page(upload, fragment=fragment)
                for raw in ('<b>evil</b>', '<script>alert(1)</script>', '<img src=x>', '<i>t</i>',
                            '<u>x</u>', '<s>a</s>'):
                    self.assertNotContains(response, raw)
                self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
                self.assertContains(response, '&lt;b&gt;evil&lt;/b&gt;')

    def test_unverified_warning_wording_appears_only_for_unverified(self):
        unverified = self.get_page(self.validated(authenticity=RestoreAuthenticity.UNVERIFIED))
        self.assertContains(unverified, 'Origin unverified')
        self.assertContains(unverified, 'not deliberate tampering')
        self.assertContains(unverified, 'claimed by the archive')
        self.assertNotContains(unverified, 'integrity confirmed')
        self.assertNotContains(unverified, 'Integrity and schema compatibility were confirmed')

        RestoreUpload.objects.all().delete()
        verified = self.get_page(self.validated(authenticity=RestoreAuthenticity.VERIFIED))
        self.assertContains(verified, 'origin was verified')
        self.assertNotContains(verified, 'Origin unverified')
        self.assertNotContains(verified, 'tampering')
        self.assertNotContains(verified, 'claimed by the archive')


class RestoreErrorCodeChoicesTest(TestCase):
    def test_error_code_field_uses_the_rejection_code_choices(self):
        from ndas.custom_codes.choice import RestoreRejectionCode
        field = RestoreUpload._meta.get_field('error_code')
        self.assertEqual(list(field.choices), list(RestoreRejectionCode.choices))
        self.assertTrue(field.blank)


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=True, STORAGES=TEST_STORAGES)
class RestoreRateLimitTest(RestoreViewTestBase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        super().setUp()

    def test_eleventh_upload_post_in_a_minute_is_rejected(self):
        client = self.client_for(self.superadmin)
        for i in range(10):
            # Empty POSTs fail form validation (200) but still count.
            self.assertEqual(client.post(self.url, {}).status_code, 200, f"request {i + 1}")
        self.assertEqual(client.post(self.url, {}).status_code, 403)

    def test_thirty_first_fragment_poll_is_rejected(self):
        upload = self.make_upload()
        client = self.client_for(self.superadmin)
        url = reverse('backup:restore-status-fragment', args=[upload.id])
        for i in range(30):
            self.assertEqual(client.get(url).status_code, 200, f"poll {i + 1}")
        self.assertEqual(client.get(url).status_code, 403)

    def test_thirty_first_status_page_view_is_rejected(self):
        upload = self.make_upload()
        client = self.client_for(self.superadmin)
        url = reverse('backup:restore-status', args=[upload.id])
        for i in range(30):
            self.assertEqual(client.get(url).status_code, 200, f"view {i + 1}")
        self.assertEqual(client.get(url).status_code, 403)

    # Story 2.2: preview 30/m, confirm and cancel 10/m.
    def _validated_upload(self):
        return self.make_upload(
            status=RestoreUploadStatus.VALIDATED, size_bytes=6, archive_sha256='a' * 64,
            authenticity=RestoreAuthenticity.VERIFIED, source_job_id=5,
            manifest_summary={
                'source_job_id': 5, 'manifest_version': 1, 'schema_version': 'f' * 64, 'scope_type': 'single',
                'institutions': [self.inst.slug], 'record_counts': {},
                'date_filter': {'applied': False, 'start': None, 'end': None},
                'generated_at': 't', 'generated_by': 'x',
            },
        )

    def test_thirty_first_preview_view_is_rejected(self):
        upload = self._validated_upload()
        client = self.client_for(self.superadmin)
        url = reverse('backup:restore-preview', args=[upload.id])
        for i in range(30):
            self.assertEqual(client.get(url).status_code, 200, f"preview {i + 1}")
        self.assertEqual(client.get(url).status_code, 403)

    def test_eleventh_confirm_post_is_rejected(self):
        upload = self._validated_upload()
        client = self.client_for(self.superadmin)
        url = reverse('backup:restore-confirm', args=[upload.id])
        for i in range(10):
            # No digest/acknowledgement: refused by the form (200) but still counted.
            self.assertEqual(client.post(url, {}).status_code, 200, f"confirm {i + 1}")
        self.assertEqual(client.post(url, {}).status_code, 403)

    def test_eleventh_cancel_post_is_rejected(self):
        upload = self.make_upload(status=RestoreUploadStatus.VALIDATING)  # fresh: cancel is refused (302), still counted
        client = self.client_for(self.superadmin)
        url = reverse('backup:restore-cancel', args=[upload.id])
        for i in range(10):
            self.assertEqual(client.post(url).status_code, 302, f"cancel {i + 1}")
        self.assertEqual(client.post(url).status_code, 403)


class DetachedLaunchKwargsTest(RestoreViewTestBase):
    """The shared `_launch_detached_command` helper: its Popen keyword
    arguments for both commands and both OS branches."""

    WIN_FLAGS = (0x00000200, 0x00000008)  # CREATE_NEW_PROCESS_GROUP, DETACHED_PROCESS

    def launch_restore(self, os_name):
        with mock.patch('backup.views.subprocess.Popen') as popen, \
                mock.patch('backup.views.os', SimpleNamespace(name=os_name)), \
                mock.patch.object(subprocess, 'CREATE_NEW_PROCESS_GROUP', self.WIN_FLAGS[0], create=True), \
                mock.patch.object(subprocess, 'DETACHED_PROCESS', self.WIN_FLAGS[1], create=True):
            self.post_archive(self.client_for(self.superadmin))
        popen.assert_called_once()
        return popen.call_args, RestoreUpload.objects.get()

    def launch_backup(self, os_name):
        with mock.patch('backup.views.subprocess.Popen') as popen, \
                mock.patch('backup.views.has_sufficient_disk_space', return_value=(True, 0, 0, 10 ** 12)), \
                mock.patch('backup.views.os', SimpleNamespace(name=os_name)), \
                mock.patch.object(subprocess, 'CREATE_NEW_PROCESS_GROUP', self.WIN_FLAGS[0], create=True), \
                mock.patch.object(subprocess, 'DETACHED_PROCESS', self.WIN_FLAGS[1], create=True):
            self.client_for(self.admin).post(reverse('backup:backup-create'))
        popen.assert_called_once()
        return popen.call_args, BackupJob.objects.get()

    def assertCommon(self, call, command, object_id, log_name):
        args, kwargs = call
        self.assertEqual(args[0], [sys.executable, str(settings.BASE_DIR / 'manage.py'), command, str(object_id)])
        self.assertIs(kwargs['stdin'], subprocess.DEVNULL)
        self.assertEqual(kwargs['cwd'], str(settings.BASE_DIR))
        self.assertIs(kwargs['stdout'], kwargs['stderr'])
        self.assertEqual(Path(kwargs['stdout'].name).name, log_name)
        self.assertTrue(Path(kwargs['stdout'].name).exists())

    def assertPosix(self, kwargs):
        self.assertIs(kwargs['start_new_session'], True)
        self.assertNotIn('creationflags', kwargs)

    def assertWindows(self, kwargs):
        self.assertNotIn('start_new_session', kwargs)
        self.assertTrue(kwargs['creationflags'] & self.WIN_FLAGS[0])
        self.assertTrue(kwargs['creationflags'] & self.WIN_FLAGS[1])

    def test_restore_validation_launch_posix(self):
        call, upload = self.launch_restore('posix')
        self.assertCommon(call, 'validate_restore_upload', upload.id, 'validate_restore_upload.log')
        self.assertPosix(call.kwargs)

    def test_restore_validation_launch_windows(self):
        call, upload = self.launch_restore('nt')
        self.assertCommon(call, 'validate_restore_upload', upload.id, 'validate_restore_upload.log')
        self.assertWindows(call.kwargs)

    def test_backup_launch_posix(self):
        call, job = self.launch_backup('posix')
        self.assertCommon(call, 'run_backup', job.id, 'run_backup.log')
        self.assertPosix(call.kwargs)

    def test_backup_launch_windows(self):
        call, job = self.launch_backup('nt')
        self.assertCommon(call, 'run_backup', job.id, 'run_backup.log')
        self.assertWindows(call.kwargs)
