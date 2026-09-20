"""
backup/tests/test_restore_command.py -- Story 2.1

`manage.py validate_restore_upload`: drives a RestoreUpload from `validating`
to `validated | rejected | failed`, deletes the staged file on any
non-validated outcome, reports progress, and writes each terminal state in
one save.
"""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError
from django.test import TestCase, override_settings

from backup.models import BackupJob, RestoreUpload
from backup.restore_validation import get_upload_dir, get_upload_path
from backup.tests.restore_helpers import (
    SOURCE_JOB_ID,
    IsolatedBaseDirMixin,
    build_archive,
    sha256_file,
)
from institution.models import Institution
from ndas.custom_codes.choice import (
    BackupJobStatus,
    BackupJobType,
    RestoreAuthenticity,
    RestoreRejectionCode,
    RestoreUploadStatus,
)

User = get_user_model()

STORAGE_OVERRIDE = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)


@STORAGE_OVERRIDE
class ValidateRestoreUploadCommandTest(IsolatedBaseDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='cmd_sa', password='x', position='Administrator', mobile_primary='0770000501',
        )
        self.inst = Institution.objects.create(name='Cmd Hosp', slug='cmd-hosp', created_by=self.user)

    def stage(self, allow_unverified=False, **archive_kwargs):
        upload = RestoreUpload.objects.create(
            uploaded_by=self.user, original_filename='b.zip', allow_unverified=allow_unverified,
            status=RestoreUploadStatus.VALIDATING,
        )
        get_upload_dir(upload).mkdir(parents=True, exist_ok=True)
        path = get_upload_path(upload)
        build_archive(path, **archive_kwargs)
        upload.archive_sha256 = sha256_file(path)
        upload.size_bytes = path.stat().st_size
        upload.save()
        return upload

    def make_origin_job(self, checksum):
        return BackupJob.objects.create(
            pk=SOURCE_JOB_ID, job_type=BackupJobType.BACKUP, status=BackupJobStatus.COMPLETED,
            scope=self.inst, triggered_by=self.user, archive_checksum=checksum,
        )

    def test_valid_archive_becomes_validated_and_verified(self):
        upload = self.stage()
        self.make_origin_job(upload.archive_sha256)
        call_command('validate_restore_upload', str(upload.id))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)
        self.assertEqual(upload.progress_pct, 100)
        self.assertEqual(upload.authenticity, RestoreAuthenticity.VERIFIED)
        self.assertEqual(upload.source_job_id, SOURCE_JOB_ID)
        self.assertEqual(upload.error_code, '')
        self.assertEqual(upload.error_message, '')
        self.assertEqual(upload.manifest_summary['institutions'], ['test-hosp'])
        self.assertEqual(
            set(upload.manifest_summary),
            {'source_job_id', 'manifest_version', 'schema_version', 'scope_type', 'institutions',
             'record_counts', 'date_filter', 'generated_at', 'generated_by'},
        )
        # A validated upload keeps its staged file for the later restore stories.
        self.assertTrue(get_upload_path(upload).exists())

    def test_unknown_origin_with_box_ticked_is_validated_unverified(self):
        upload = self.stage(allow_unverified=True)
        call_command('validate_restore_upload', str(upload.id))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)
        self.assertEqual(upload.authenticity, RestoreAuthenticity.UNVERIFIED)

    def test_unknown_origin_with_box_unticked_is_rejected_and_file_deleted(self):
        upload = self.stage()
        with self.assertLogs('django.security.restore', level='WARNING') as logs:
            call_command('validate_restore_upload', str(upload.id))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.REJECTED)
        self.assertEqual(upload.error_code, RestoreRejectionCode.ORIGIN_NOT_VERIFIABLE)
        self.assertIn('Allow unverified origin', upload.error_message)
        self.assertEqual(upload.authenticity, '')
        self.assertIsNone(upload.manifest_summary)
        self.assertFalse(get_upload_path(upload).exists())
        self.assertTrue(any('origin_not_verifiable' in line for line in logs.output))

    def test_schema_mismatch_is_rejected_with_both_values(self):
        upload = self.stage(manifest_overrides={'schema_version': 'c' * 64})
        call_command('validate_restore_upload', str(upload.id))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.REJECTED)
        self.assertEqual(upload.error_code, RestoreRejectionCode.SCHEMA_MISMATCH)
        self.assertIn('c' * 64, upload.error_message)
        self.assertFalse(get_upload_path(upload).exists())

    def test_zip_safety_rejection_deletes_staged_file(self):
        upload = self.stage(extra_members=[('../evil.txt', b'x')])
        call_command('validate_restore_upload', str(upload.id))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.REJECTED)
        self.assertEqual(upload.error_code, RestoreRejectionCode.UNSAFE_MEMBER_PATH)
        self.assertFalse(get_upload_path(upload).exists())

    def test_per_file_mismatch_names_the_member(self):
        upload = self.stage(
            allow_unverified=True, media={'media/cmd-hosp/videos/a.mp4': b'abc'},
            manifest_overrides={'checksums': {'db_export.json': '0' * 64, 'media/cmd-hosp/videos/a.mp4': '1' * 64}},
        )
        call_command('validate_restore_upload', str(upload.id))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.REJECTED)
        self.assertEqual(upload.error_code, RestoreRejectionCode.FILE_CHECKSUM_MISMATCH)
        self.assertIn('db_export.json', upload.error_message)

    def test_unexpected_exception_becomes_failed_and_deletes_file(self):
        upload = self.stage()
        with mock.patch(
            'backup.management.commands.validate_restore_upload.validate_restore_archive',
            side_effect=RuntimeError('kaboom'),
        ):
            call_command('validate_restore_upload', str(upload.id))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.FAILED)
        self.assertIn('kaboom', upload.error_message)
        self.assertFalse(get_upload_path(upload).exists())

    def test_missing_staged_file_becomes_failed(self):
        upload = self.stage()
        get_upload_path(upload).unlink()
        call_command('validate_restore_upload', str(upload.id))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.FAILED)

    def test_progress_is_persisted_during_validation(self):
        upload = self.stage()
        seen = []

        def fake_validate(path, sha, allow_unverified=False, progress_callback=None):
            progress_callback(42)
            seen.append(RestoreUpload.objects.get(pk=upload.pk).progress_pct)
            raise RuntimeError('stop here')

        with mock.patch(
            'backup.management.commands.validate_restore_upload.validate_restore_archive',
            side_effect=fake_validate,
        ):
            call_command('validate_restore_upload', str(upload.id))
        self.assertEqual(seen, [42])
        upload.refresh_from_db()
        self.assertEqual(upload.progress_pct, 0)  # terminal save resets it with the failed status

    def test_unknown_upload_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command('validate_restore_upload', '999999')

    def test_non_validating_upload_is_left_alone(self):
        upload = self.stage()
        upload.status = RestoreUploadStatus.VALIDATED
        upload.save()
        call_command('validate_restore_upload', str(upload.id))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)
        self.assertTrue(get_upload_path(upload).exists())

    def test_staged_file_deletion_failure_does_not_change_the_outcome(self):
        upload = self.stage()
        with mock.patch(
            'backup.management.commands.validate_restore_upload.delete_staged_archive',
            side_effect=PermissionError('locked by antivirus'),
        ):
            call_command('validate_restore_upload', str(upload.id))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.REJECTED)
        self.assertEqual(upload.error_code, RestoreRejectionCode.ORIGIN_NOT_VERIFIABLE)

    def test_staged_file_deletion_failure_on_unexpected_error_still_records_failed(self):
        upload = self.stage()
        with mock.patch(
            'backup.management.commands.validate_restore_upload.validate_restore_archive',
            side_effect=RuntimeError('kaboom'),
        ), mock.patch(
            'backup.management.commands.validate_restore_upload.delete_staged_archive',
            side_effect=PermissionError('locked'),
        ):
            call_command('validate_restore_upload', str(upload.id))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.FAILED)

    def _save_failing_on_terminal_validated_state(self):
        original_save = RestoreUpload.save

        def flaky_save(instance, *args, **kwargs):
            if 'manifest_summary' in (kwargs.get('update_fields') or ()):
                raise OperationalError('database is locked')
            return original_save(instance, *args, **kwargs)

        return mock.patch.object(RestoreUpload, 'save', autospec=True, side_effect=flaky_save)

    def test_terminal_save_failure_falls_back_to_failed(self):
        upload = self.stage(allow_unverified=True)
        with self._save_failing_on_terminal_validated_state():
            call_command('validate_restore_upload', str(upload.id))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.FAILED)
        self.assertIn('could not be recorded', upload.error_message)
        self.assertFalse(get_upload_path(upload).exists())

    def test_unverified_acceptance_is_logged_as_a_warning(self):
        upload = self.stage(allow_unverified=True)
        with self.assertLogs('django.security.restore', level='WARNING') as logs:
            call_command('validate_restore_upload', str(upload.id))
        line = "\n".join(logs.output)
        self.assertIn('Unverified-origin', line)
        self.assertIn(f'upload={upload.id}', line)
        self.assertIn(self.user.username, line)
        self.assertIn('b.zip', line)

    def test_verified_acceptance_is_not_warned_about(self):
        upload = self.stage()
        self.make_origin_job(upload.archive_sha256)
        with self.assertNoLogs('django.security.restore', level='WARNING'):
            call_command('validate_restore_upload', str(upload.id))

    def test_command_never_touches_domain_data_or_extracts_anything(self):
        from patients.models import Attachment, Patient
        from video.models import Video

        db_export = json.dumps({
            "patients.patient": [
                {"model": "patients.patient", "pk": 1, "fields": {"baby_name": "Should Not Appear"}},
            ],
            "video.video": [{"model": "video.video", "pk": 1, "fields": {"video_file": "cmd-hosp/videos/a.mp4"}}],
        }).encode("utf-8")
        media = {
            "media/cmd-hosp/videos/a.mp4": b"video-bytes" * 50,
            "media/cmd-hosp/attachments/b.pdf": b"pdf-bytes",
        }

        def domain_counts():
            return (
                Patient.objects.all_institutions().count(), Video.objects.count(),
                Attachment.objects.count(), Institution.objects.count(), BackupJob.objects.count(),
                User.objects.count(),
            )

        before = domain_counts()
        upload = self.stage(allow_unverified=True, db_export=db_export, media=media)
        call_command('validate_restore_upload', str(upload.id))
        upload.refresh_from_db()
        self.assertEqual(upload.status, RestoreUploadStatus.VALIDATED)
        self.assertEqual(domain_counts(), before)

        # Nothing was extracted: the only file anywhere under the isolated
        # base dir is the staged archive (there is no media/, no extra dirs).
        files = sorted(
            str(p.relative_to(self.base_dir)).replace("\\", "/")
            for p in self.base_dir.rglob("*") if p.is_file()
        )
        self.assertEqual(files, [f"restore_uploads/{upload.id}/upload.zip"])
        self.assertFalse(self.media_root.exists())
        self.assertFalse(self.static_root.exists())
