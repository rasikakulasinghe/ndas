"""
backup/tests/test_restore_validation.py -- Story 2.1

Each of the five validation stages and every rejection code, against hand-built
corrupt/malicious archives, plus a happy path over an archive produced by the
real `create_export`.
"""
import json
import stat
import struct
import zipfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from backup import restore_validation
from backup.export_stream import ExportFormatError
from backup.models import BackupJob
from backup.restore_validation import RestoreRejection, validate_restore_archive
from backup.services import create_export
from backup.tests.restore_helpers import (
    DB_EXPORT_BYTES,
    SOURCE_JOB_ID,
    IsolatedBaseDirMixin,
    build_archive,
    build_manifest,
    current_schema_version,
    corrupt_member_data,
    flag_first_member_encrypted,
    sha256_file,
)
from institution.models import Institution
from ndas.custom_codes.choice import (
    BackupJobStatus,
    BackupJobType,
    RestoreAuthenticity,
    RestoreRejectionCode as Code,
)
from patients.models import Patient

User = get_user_model()

STORAGE_OVERRIDE = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)


@STORAGE_OVERRIDE
class RestoreValidationBase(IsolatedBaseDirMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='rv_sa', password='x', position='Administrator', mobile_primary='0770000301',
        )
        self.inst = Institution.objects.create(name='Test Hosp', slug='test-hosp', created_by=self.user)

    def make_origin_job(self, checksum, pk=SOURCE_JOB_ID, job_type=BackupJobType.BACKUP):
        return BackupJob.objects.create(
            pk=pk, job_type=job_type, status=BackupJobStatus.COMPLETED, scope=self.inst,
            triggered_by=self.user, archive_checksum=checksum,
        )

    def validate(self, path, allow_unverified=False, progress_callback=None, sha=None):
        return validate_restore_archive(
            path, sha or sha256_file(path), allow_unverified=allow_unverified,
            progress_callback=progress_callback,
        )

    def assertRejected(self, path, code, allow_unverified=False, sha=None):
        with self.assertRaises(RestoreRejection) as ctx:
            self.validate(path, allow_unverified=allow_unverified, sha=sha)
        self.assertEqual(ctx.exception.code, str(code))
        return ctx.exception


class ZipSafetyTest(RestoreValidationBase):
    def test_not_a_zip(self):
        path = self.archive_path()
        path.write_bytes(b"this is definitely not a zip file" * 10)
        self.assertRejected(path, Code.NOT_A_ZIP)

    def test_truncated_zip(self):
        path = self.archive_path()
        build_archive(path)
        path.write_bytes(path.read_bytes()[:-30])
        self.assertRejected(path, Code.NOT_A_ZIP)

    def test_encrypted_member(self):
        path = self.archive_path()
        build_archive(path)
        flag_first_member_encrypted(path)
        self.assertRejected(path, Code.ENCRYPTED_MEMBER)

    def test_duplicate_member_names(self):
        path = self.archive_path()
        build_archive(path, extra_members=[("db_export.json", b"{}")])
        exc = self.assertRejected(path, Code.DUPLICATE_MEMBER)
        self.assertIn("db_export.json", exc.message)

    def test_parent_directory_member(self):
        path = self.archive_path()
        build_archive(path, extra_members=[("media/../../evil.txt", b"x")])
        self.assertRejected(path, Code.UNSAFE_MEMBER_PATH)

    def test_leading_dotdot_member(self):
        path = self.archive_path()
        build_archive(path, extra_members=[("../evil.txt", b"x")])
        self.assertRejected(path, Code.UNSAFE_MEMBER_PATH)

    def test_absolute_member(self):
        path = self.archive_path()
        build_archive(path, extra_members=[("/etc/passwd", b"x")])
        self.assertRejected(path, Code.UNSAFE_MEMBER_PATH)

    def test_drive_letter_member(self):
        path = self.archive_path()
        build_archive(path, extra_members=[("C:/Windows/evil.dll", b"x")])
        self.assertRejected(path, Code.UNSAFE_MEMBER_PATH)

    def test_backslash_member(self):
        # On Windows zipfile itself rewrites backslashes to '/', turning this
        # into a '..' traversal; on POSIX the backslash is caught directly.
        path = self.archive_path()
        build_archive(path, extra_members=[("media\\..\\evil.txt", b"x")])
        self.assertRejected(path, Code.UNSAFE_MEMBER_PATH)

    def test_symlink_member(self):
        path = self.archive_path()
        link = zipfile.ZipInfo("media/link")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        build_archive(path, extra_members=[(link, b"/etc/passwd")])
        self.assertRejected(path, Code.SYMLINK_MEMBER)

    def test_unexpected_member(self):
        path = self.archive_path()
        build_archive(path, extra_members=[("evil.txt", b"x")])
        exc = self.assertRejected(path, Code.UNEXPECTED_MEMBER)
        self.assertIn("evil.txt", exc.message)

    def test_directory_member_is_unexpected(self):
        path = self.archive_path()
        build_archive(path, extra_members=[("media/sub/", b"")])
        self.assertRejected(path, Code.UNEXPECTED_MEMBER)

    def test_implausible_expansion_ratio(self):
        path = self.archive_path()
        # 1 MB of zeros deflates to ~1 KB; drop the threshold so the test
        # doesn't depend on deflate's exact ratio.
        build_archive(path, media={"media/x/zeros.bin": b"\0" * (1024 * 1024)})
        with mock.patch.object(restore_validation, 'MAX_EXPANSION_RATIO', 10):
            self.assertRejected(path, Code.EXCESSIVE_EXPANSION)

    def test_total_declared_size_above_four_times_upload_limit(self):
        path = self.archive_path()
        build_archive(path, media={"media/x/big.bin": bytes(range(256)) * 4})  # 1 KiB, ratio ~1
        limits = {**settings.FILE_UPLOAD_LIMITS, 'RESTORE_ARCHIVE_MAX_SIZE': 100}  # 4x = 400 bytes
        with override_settings(FILE_UPLOAD_LIMITS=limits):
            exc = self.assertRejected(path, Code.EXCESSIVE_EXPANSION)
        self.assertIn("in total", exc.message)


class ManifestTest(RestoreValidationBase):
    def test_manifest_missing(self):
        path = self.archive_path()
        build_archive(path, manifest=False)
        self.assertRejected(path, Code.MANIFEST_MISSING)

    def test_manifest_not_json(self):
        path = self.archive_path()
        build_archive(path, manifest=b"{not json")
        self.assertRejected(path, Code.MANIFEST_INVALID)

    def test_manifest_not_utf8(self):
        path = self.archive_path()
        build_archive(path, manifest=b"\xff\xfe\x00")
        self.assertRejected(path, Code.MANIFEST_INVALID)

    def test_manifest_not_an_object(self):
        path = self.archive_path()
        build_archive(path, manifest=b"[1, 2, 3]")
        self.assertRejected(path, Code.MANIFEST_INVALID)

    def test_each_required_field_missing(self):
        for field in build_manifest({}):
            with self.subTest(field=field):
                path = self.archive_path(f"missing_{field}.zip")
                manifest = build_manifest({"db_export.json": b"{}"})
                del manifest[field]
                build_archive(path, manifest=manifest)
                exc = self.assertRejected(path, Code.MANIFEST_INVALID)
                self.assertIn(field, exc.message)

    def test_mistyped_fields(self):
        bad_values = {
            'source_job_id': "42",
            'manifest_version': "1",
            'schema_version': 123,
            'checksum_algorithm': None,
            'scope_type': 5,
            'institutions': "test-hosp",
            'record_counts': ["patients.patient"],
            'checksums': {"db_export.json": 12},
            'generated_at': 1,
            'generated_by': None,
            'date_filter': {"applied": "no", "start": None, "end": None},
        }
        for field, value in bad_values.items():
            with self.subTest(field=field):
                path = self.archive_path(f"typed_{field}.zip")
                build_archive(path, manifest_overrides={field: value})
                exc = self.assertRejected(path, Code.MANIFEST_INVALID)
                self.assertIn(field, exc.message)

    def test_boolean_is_not_an_integer(self):
        path = self.archive_path()
        build_archive(path, manifest_overrides={'manifest_version': True})
        self.assertRejected(path, Code.MANIFEST_INVALID)

    def test_source_job_id_out_of_range(self):
        path = self.archive_path()
        build_archive(path, manifest_overrides={'source_job_id': 2 ** 40})
        self.assertRejected(path, Code.MANIFEST_INVALID)

    def test_unsupported_manifest_version(self):
        path = self.archive_path()
        build_archive(path, manifest_overrides={'manifest_version': 2})
        exc = self.assertRejected(path, Code.MANIFEST_UNSUPPORTED)
        self.assertIn("2", exc.message)

    def test_unsupported_checksum_algorithm(self):
        path = self.archive_path()
        build_archive(path, manifest_overrides={'checksum_algorithm': 'md5'})
        exc = self.assertRejected(path, Code.MANIFEST_UNSUPPORTED)
        self.assertIn("md5", exc.message)

    def test_db_export_missing(self):
        path = self.archive_path()
        build_archive(path, db_export=False)
        self.assertRejected(path, Code.DB_EXPORT_MISSING)


class SchemaTest(RestoreValidationBase):
    def test_schema_mismatch_names_both_values(self):
        path = self.archive_path()
        build_archive(path, manifest_overrides={'schema_version': 'a' * 64})
        exc = self.assertRejected(path, Code.SCHEMA_MISMATCH)
        self.assertIn('a' * 64, exc.message)
        self.assertIn(current_schema_version(), exc.message)

    def test_schema_is_checked_before_origin(self):
        # Origin is also unverifiable here (no job, box unticked); schema wins.
        path = self.archive_path()
        build_archive(path, manifest_overrides={'schema_version': 'b' * 64})
        self.assertRejected(path, Code.SCHEMA_MISMATCH)

    def test_zip_safety_is_checked_before_manifest(self):
        path = self.archive_path()
        build_archive(path, manifest=False, extra_members=[("evil.txt", b"x")])
        self.assertRejected(path, Code.UNEXPECTED_MEMBER)


class OriginAuthenticityTest(RestoreValidationBase):
    def make_archive(self):
        path = self.archive_path()
        build_archive(path)
        return path

    def test_matching_checksum_is_verified(self):
        path = self.make_archive()
        self.make_origin_job(sha256_file(path))
        result = self.validate(path)
        self.assertEqual(result.authenticity, RestoreAuthenticity.VERIFIED)

    def test_matching_checksum_is_verified_even_with_box_ticked(self):
        path = self.make_archive()
        self.make_origin_job(sha256_file(path))
        self.assertEqual(self.validate(path, allow_unverified=True).authenticity, RestoreAuthenticity.VERIFIED)

    def test_checksum_differs_is_rejected_even_with_box_ticked(self):
        path = self.make_archive()
        self.make_origin_job('0' * 64)
        exc = self.assertRejected(path, Code.ARCHIVE_CHECKSUM_MISMATCH, allow_unverified=True)
        self.assertIn(str(SOURCE_JOB_ID), exc.message)
        self.assertIn(sha256_file(path), exc.message)

    def test_no_job_and_box_unticked_is_not_verifiable(self):
        path = self.make_archive()
        exc = self.assertRejected(path, Code.ORIGIN_NOT_VERIFIABLE)
        self.assertIn("Allow unverified origin", exc.message)

    def test_no_job_and_box_ticked_is_unverified(self):
        path = self.make_archive()
        result = self.validate(path, allow_unverified=True)
        self.assertEqual(result.authenticity, RestoreAuthenticity.UNVERIFIED)

    def test_job_without_checksum_is_treated_as_unknown(self):
        path = self.make_archive()
        self.make_origin_job('')
        self.assertRejected(path, Code.ORIGIN_NOT_VERIFIABLE)
        self.assertEqual(self.validate(path, allow_unverified=True).authenticity, RestoreAuthenticity.UNVERIFIED)

    def test_non_backup_job_with_that_id_is_ignored(self):
        path = self.make_archive()
        self.make_origin_job('0' * 64, job_type=BackupJobType.RESTORE)
        self.assertRejected(path, Code.ORIGIN_NOT_VERIFIABLE)


class PerFileChecksumTest(RestoreValidationBase):
    MEDIA = {"media/test-hosp/videos/a.mp4": b"video-bytes" * 100, "media/test-hosp/attachments/b.pdf": b"pdf"}

    def test_valid_archive_passes_and_reports_progress(self):
        path = self.archive_path()
        build_archive(path, media=self.MEDIA)
        seen = []
        result = self.validate(path, allow_unverified=True, progress_callback=seen.append)
        self.assertEqual(result.authenticity, RestoreAuthenticity.UNVERIFIED)
        self.assertTrue(seen)
        self.assertEqual(seen, sorted(seen))
        self.assertTrue(all(0 <= pct <= 99 for pct in seen))

    def test_listed_member_absent_from_archive(self):
        path = self.archive_path()
        manifest = build_manifest({"db_export.json": DB_EXPORT_BYTES})
        manifest['checksums']["media/test-hosp/videos/gone.mp4"] = '0' * 64
        build_archive(path, manifest=manifest)
        exc = self.assertRejected(path, Code.FILE_MISSING, allow_unverified=True)
        self.assertIn("media/test-hosp/videos/gone.mp4", exc.message)

    def test_member_not_listed_in_manifest(self):
        path = self.archive_path()
        manifest = build_manifest({"db_export.json": DB_EXPORT_BYTES, **self.MEDIA})
        build_archive(
            path, media=self.MEDIA, manifest=manifest,
            extra_members=[("media/test-hosp/videos/sneaky.mp4", b"x")],
        )
        exc = self.assertRejected(path, Code.FILE_NOT_LISTED, allow_unverified=True)
        self.assertIn("media/test-hosp/videos/sneaky.mp4", exc.message)

    def test_media_checksum_mismatch_names_the_member(self):
        path = self.archive_path()
        members = {"db_export.json": DB_EXPORT_BYTES, **self.MEDIA}
        manifest = build_manifest(members)
        manifest['checksums']["media/test-hosp/videos/a.mp4"] = 'f' * 64
        build_archive(path, media=self.MEDIA, manifest=manifest)
        exc = self.assertRejected(path, Code.FILE_CHECKSUM_MISMATCH, allow_unverified=True)
        self.assertIn("media/test-hosp/videos/a.mp4", exc.message)

    def test_db_export_checksum_mismatch(self):
        path = self.archive_path()
        manifest = build_manifest({"db_export.json": b"whatever"})
        build_archive(path, manifest=manifest)
        exc = self.assertRejected(path, Code.FILE_CHECKSUM_MISMATCH, allow_unverified=True)
        self.assertIn("db_export.json", exc.message)

    def test_corrupt_member_bytes_are_a_checksum_failure(self):
        path = self.archive_path()
        payload = b"A" * 500
        build_archive(path, media={"media/test-hosp/videos/a.mp4": payload}, compression=zipfile.ZIP_STORED)
        data = bytearray(path.read_bytes())
        i = data.index(payload)
        data[i + 10] ^= 0xFF  # flip a payload byte; the stored CRC no longer matches
        path.write_bytes(bytes(data))
        exc = self.assertRejected(path, Code.FILE_CHECKSUM_MISMATCH, allow_unverified=True)
        self.assertIn("media/test-hosp/videos/a.mp4", exc.message)


class RealExportArchiveTest(RestoreValidationBase):
    """The happy path over an archive produced by the real exporter."""

    def make_real_archive(self):
        job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP, status=BackupJobStatus.RUNNING, scope=self.inst,
            triggered_by=self.user, trigger_institution=self.inst,
        )
        archive_path, _skipped, checksum = create_export(job)
        job.status = BackupJobStatus.COMPLETED
        job.archive_checksum = checksum
        job.save()
        return job, Path(archive_path), checksum

    def test_real_archive_validates_as_verified(self):
        job, path, checksum = self.make_real_archive()
        seen = []
        result = self.validate(path, progress_callback=seen.append)
        self.assertEqual(result.authenticity, RestoreAuthenticity.VERIFIED)
        summary = result.summary
        self.assertEqual(summary['source_job_id'], job.id)
        self.assertEqual(summary['manifest_version'], 1)
        self.assertEqual(summary['schema_version'], current_schema_version())
        self.assertEqual(summary['scope_type'], 'single')
        self.assertEqual(summary['institutions'], ['test-hosp'])
        self.assertIn('patients.patient', summary['record_counts'])
        self.assertEqual(summary['date_filter'], {'applied': False, 'start': None, 'end': None})
        self.assertEqual(summary['generated_by'], self.user.username)
        self.assertTrue(summary['generated_at'])
        self.assertEqual(sha256_file(path), checksum)

    def test_tampered_real_archive_fails_the_archive_checksum(self):
        job, path, _checksum = self.make_real_archive()
        # Re-write the archive with a modified db_export.json member.
        tampered = self.archive_path("tampered.zip")
        with zipfile.ZipFile(path) as src, zipfile.ZipFile(tampered, "w", zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename == "db_export.json":
                    data = data.replace(b"[]", b"[ ]", 1)
                dst.writestr(info.filename, data)
        exc = self.assertRejected(tampered, Code.ARCHIVE_CHECKSUM_MISMATCH)
        self.assertIn(str(job.id), exc.message)

    def test_tampered_real_archive_fails_per_file_check_when_origin_unverified(self):
        _job, path, _checksum = self.make_real_archive()
        tampered = self.archive_path("tampered.zip")
        with zipfile.ZipFile(path) as src, zipfile.ZipFile(tampered, "w", zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename == "db_export.json":
                    data = data.replace(b"[]", b"[ ]", 1)
                dst.writestr(info.filename, data)
        BackupJob.objects.all().delete()
        exc = self.assertRejected(tampered, Code.FILE_CHECKSUM_MISMATCH, allow_unverified=True)
        self.assertIn("db_export.json", exc.message)


class HardenedPathTest(RestoreValidationBase):
    """Path-safety additions: control chars, ':', trailing dot/space, reserved
    device names, over-long names, case-insensitive duplicates."""

    def assertUnsafe(self, name):
        path = self.archive_path()
        build_archive(path, extra_members=[(name, b"x")])
        return self.assertRejected(path, Code.UNSAFE_MEMBER_PATH)

    def test_control_characters_rejected_and_never_reach_the_message(self):
        for name in ("media/a\nb.mp4", "media/a\rb.mp4", "media/a\x1bb.mp4", "media/a\x7fb.mp4"):
            with self.subTest(name=repr(name)):
                exc = self.assertUnsafe(name)
                self.assertNotIn("\n", exc.message)
                self.assertNotIn("\r", exc.message)
                self.assertNotIn("\x1b", exc.message)
                self.assertNotIn("\x7f", exc.message)

    def test_colon_alternate_data_stream_rejected(self):
        self.assertUnsafe("media/x/a.mp4:hidden")

    def test_trailing_dot_or_space_rejected(self):
        self.assertUnsafe("media/x/a.mp4.")
        self.assertUnsafe("media/x./a.mp4")
        self.assertUnsafe("media/x/a.mp4 ")

    def test_reserved_windows_device_names_rejected(self):
        for name in ("media/CON", "media/x/nul.txt", "media/x/Aux.mp4", "media/COM1", "media/x/lpt9.pdf"):
            with self.subTest(name=name):
                self.assertUnsafe(name)

    def test_ordinary_names_containing_reserved_words_are_fine(self):
        path = self.archive_path()
        build_archive(path, media={"media/x/console.mp4": b"a", "media/x/comx.pdf": b"b"})
        self.assertEqual(self.validate(path, allow_unverified=True).authenticity, RestoreAuthenticity.UNVERIFIED)

    def test_overlong_name_rejected_and_clipped(self):
        exc = self.assertUnsafe("media/" + "a" * 5000)
        self.assertLess(len(exc.message), 400)

    def test_duplicate_detection_is_case_insensitive(self):
        path = self.archive_path()
        build_archive(path, media={"media/x/A.mp4": b"1", "media/x/a.mp4": b"2"})
        exc = self.assertRejected(path, Code.DUPLICATE_MEMBER)
        self.assertIn("case-insensitively", exc.message)


class ZipBombGuardTest(RestoreValidationBase):
    def test_member_count_cap(self):
        path = self.archive_path()
        build_archive(path, media={f"media/x/{i}.bin": b"a" for i in range(5)})
        with mock.patch.object(restore_validation, 'MAX_MEMBERS', 3):
            exc = self.assertRejected(path, Code.EXCESSIVE_EXPANSION)
        self.assertIn("members", exc.message)

    def test_members_claiming_more_compressed_bytes_than_the_file_holds(self):
        path = self.archive_path()
        build_archive(path, media={"media/x/a.bin": bytes(range(256)) * 400})
        # An archive whose member table claims more compressed data than the
        # file contains has overlapping entries.
        with mock.patch('backup.restore_validation.os.path.getsize', return_value=10), \
                mock.patch.object(restore_validation, 'COMPRESSED_SIZE_SLACK', 0):
            exc = self.assertRejected(path, Code.EXCESSIVE_EXPANSION)
        self.assertIn("overlap", exc.message)

    def test_total_declared_size_capped_by_ratio_times_actual_file_size(self):
        path = self.archive_path()
        # ~200 KB declared, compresses ~200:1 so no per-member trip; with the
        # "actual" archive size pinned at 100 bytes, 1000 * 100 < 200 KB.
        build_archive(path, media={"media/x/a.bin": bytes(range(256)) * 800})
        with mock.patch('backup.restore_validation.os.path.getsize', return_value=100):
            exc = self.assertRejected(path, Code.EXCESSIVE_EXPANSION)
        self.assertIn("in total", exc.message)


class MalformedZipTest(RestoreValidationBase):
    def test_zipfile_parse_errors_are_not_a_zip_not_failed(self):
        path = self.archive_path()
        build_archive(path)
        for exc_type in (ValueError, OverflowError, NotImplementedError, struct.error):
            with self.subTest(exc=exc_type.__name__):
                with mock.patch('backup.restore_validation.zipfile.ZipFile', side_effect=exc_type('bad')):
                    self.assertRejected(path, Code.NOT_A_ZIP)


class HardenedManifestTest(RestoreValidationBase):
    def assertManifestInvalid(self, **overrides):
        path = self.archive_path()
        build_archive(path, manifest_overrides=overrides)
        return self.assertRejected(path, Code.MANIFEST_INVALID)

    def test_corrupt_manifest_crc_is_manifest_invalid(self):
        path = self.archive_path()
        build_archive(path, compression=zipfile.ZIP_STORED)
        corrupt_member_data(path, "manifest.json", fill=b"X")
        exc = self.assertRejected(path, Code.MANIFEST_INVALID)
        self.assertIn("manifest.json", exc.message)

    def test_truncated_deflate_manifest_is_manifest_invalid(self):
        path = self.archive_path()
        build_archive(path)
        corrupt_member_data(path, "manifest.json")
        self.assertRejected(path, Code.MANIFEST_INVALID)

    def test_oversized_manifest_is_manifest_invalid(self):
        path = self.archive_path()
        build_archive(path)
        with mock.patch.object(restore_validation, 'MANIFEST_MAX_BYTES', 10):
            exc = self.assertRejected(path, Code.MANIFEST_INVALID)
        self.assertIn("large", exc.message)

    def test_schema_version_must_be_64_lowercase_hex(self):
        for value in ('z' * 64, 'A' * 64, 'a' * 63, 'a' * 65, ''):
            with self.subTest(value=value):
                self.assertManifestInvalid(schema_version=value)

    def test_checksum_values_must_be_sha256_hex(self):
        for value in ('nothex', 'g' * 64, '0' * 63):
            with self.subTest(value=value):
                self.assertManifestInvalid(checksums={"db_export.json": value})

    def test_checksum_keys_are_length_bounded(self):
        exc = self.assertManifestInvalid(checksums={"media/" + "a" * 2000: '0' * 64})
        self.assertLess(len(exc.message), 400)

    def test_short_text_fields_are_length_bounded(self):
        for field in ('generated_by', 'generated_at', 'scope_type'):
            with self.subTest(field=field):
                self.assertManifestInvalid(**{field: 'x' * 256})

    def test_institutions_are_bounded(self):
        self.assertManifestInvalid(institutions=['a'] * 1001)
        self.assertManifestInvalid(institutions=['a' * 256])

    def test_date_filter_values_are_bounded(self):
        self.assertManifestInvalid(date_filter={'applied': True, 'start': 'x' * 65, 'end': None})

    def test_record_counts_bounds(self):
        self.assertManifestInvalid(record_counts={f'app.model{i}': 1 for i in range(101)})
        self.assertManifestInvalid(record_counts={'patients.patient': -1})
        self.assertManifestInvalid(record_counts={'patients.patient': True})

    def test_record_counts_keys_must_be_model_labels(self):
        for key in ('items', 'Patients.Patient', 'a b.c', 'app.', '.model', 'a.b.c', 'x' * 200 + '.y'):
            with self.subTest(key=key[:30]):
                self.assertManifestInvalid(record_counts={key: 1})

    def test_hostile_manifest_text_is_clipped_and_cleaned_in_messages(self):
        key = "bad\nkey" + "A" * 5000
        exc = self.assertManifestInvalid(record_counts={key: 1})
        self.assertLess(len(exc.message), 400)
        self.assertNotIn("\n", exc.message)

    def test_hostile_checksum_key_in_file_missing_message_is_clipped(self):
        path = self.archive_path()
        name = "media/" + "z" * 900 + "\nINJECTED"
        manifest = build_manifest({"db_export.json": DB_EXPORT_BYTES})
        manifest['checksums'][name] = '0' * 64
        build_archive(path, manifest=manifest)
        exc = self.assertRejected(path, Code.FILE_MISSING, allow_unverified=True)
        self.assertLess(len(exc.message), 400)
        self.assertNotIn("\n", exc.message)

    def test_valid_manifest_with_boundary_values_passes(self):
        path = self.archive_path()
        build_archive(path, manifest_overrides={
            'institutions': ['i' * 255] * 1000,
            'generated_by': 'u' * 255,
            'record_counts': {f'app.model{i}': i for i in range(100)},
            'date_filter': {'applied': True, 'start': '2026-01-01', 'end': None},
        })
        self.assertEqual(self.validate(path, allow_unverified=True).authenticity, RestoreAuthenticity.UNVERIFIED)

    def test_summary_normalises_date_filter(self):
        path = self.archive_path()
        build_archive(path, manifest_overrides={'date_filter': {'applied': False}})
        summary = self.validate(path, allow_unverified=True).summary
        self.assertEqual(summary['date_filter'], {'applied': False, 'start': None, 'end': None})


class OriginJobStatusTest(RestoreValidationBase):
    def test_matching_checksum_on_a_job_that_is_not_completed_is_not_verifiable(self):
        path = self.archive_path()
        build_archive(path)
        job = self.make_origin_job(sha256_file(path))
        for status in (BackupJobStatus.PENDING, BackupJobStatus.RUNNING, BackupJobStatus.FAILED):
            with self.subTest(status=status):
                BackupJob.objects.filter(pk=job.pk).update(status=status)
                self.assertRejected(path, Code.ORIGIN_NOT_VERIFIABLE)


# ---------------------------------------------------------------------------
# Stage 6 -- date-scoped match (Story 2.4)
# ---------------------------------------------------------------------------

def _patient_records(entries):
    """`entries`: [(pk, fields_dict), ...] -> the db_export.json bytes for a
    `patients.patient`-only export (plus an empty `video.video` array, so the
    shape matches a real export)."""
    return json.dumps({
        "patients.patient": [
            {"model": "patients.patient", "pk": pk, "fields": fields} for pk, fields in entries
        ],
        "video.video": [],
    }).encode("utf-8")


class DateScopeMatchTest(RestoreValidationBase):
    def make_patient(self, **overrides):
        fields = dict(
            baby_name='Existing', mother_name='Mother', dob_tob=timezone.now(), gender='Male',
            pog_wks=38, pog_days=2, birth_weight=3000, ofc=33, mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711234567', institution=self.inst, added_by=self.user,
        )
        fields.update(overrides)
        return Patient.objects.create(**fields)

    def build(self, entries, date_filter=None, **manifest_overrides):
        path = self.archive_path()
        overrides = {
            'date_filter': date_filter or {'applied': True, 'start': '2026-01-01', 'end': '2026-02-01'},
        }
        overrides.update(manifest_overrides)
        build_archive(path, db_export=_patient_records(entries), manifest_overrides=overrides)
        return path

    def result_for(self, entries, date_filter=None, **manifest_overrides):
        path = self.build(entries, date_filter=date_filter, **manifest_overrides)
        return self.validate(path, allow_unverified=True)

    def test_matches_existing_patient_by_bht_and_skips(self):
        existing = self.make_patient(bht='BHT-1')
        result = self.result_for([(1, {'bht': 'BHT-1'})])
        self.assertEqual(result.match_summary['institution_slug'], 'test-hosp')
        self.assertEqual(result.match_summary['target_institution_id'], self.inst.id)
        self.assertEqual(result.match_summary['skip'], [
            {
                'archive_pk': 1, 'matched_fields': ['bht'], 'identifiers': {'bht': 'BHT-1'},
                'existing_patient_ids': [existing.id],
            },
        ])
        self.assertEqual(result.match_summary['import'], [])
        self.assertEqual(result.match_summary['excluded'], [])

    def test_no_identifiers_set_always_imports(self):
        result = self.result_for([(1, {})])
        self.assertEqual(
            result.match_summary['import'], [{'archive_pk': 1, 'matched_fields': [], 'identifiers': {}}],
        )
        self.assertEqual(result.match_summary['skip'], [])
        self.assertEqual(result.match_summary['excluded'], [])

    def test_no_matching_existing_patient_imports(self):
        self.make_patient(bht='SOMEONE-ELSE')
        result = self.result_for([(1, {'bht': 'NEW-1'})])
        self.assertEqual(
            result.match_summary['import'],
            [{'archive_pk': 1, 'matched_fields': [], 'identifiers': {'bht': 'NEW-1'}}],
        )

    def test_archived_patient_matching_two_distinct_existing_patients_is_excluded(self):
        p1 = self.make_patient(bht='BHT-1')
        p2 = self.make_patient(pin='PIN-1')
        result = self.result_for([(1, {'bht': 'BHT-1', 'pin': 'PIN-1'})])
        excluded = result.match_summary['excluded']
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]['archive_pk'], 1)
        self.assertEqual(excluded[0]['reason'], 'ambiguous-conflict')
        self.assertEqual(sorted(excluded[0]['matched_fields']), ['bht', 'pin'])
        self.assertEqual(sorted(excluded[0]['existing_patient_ids']), sorted([p1.id, p2.id]))
        self.assertEqual(result.match_summary['skip'], [])
        self.assertEqual(result.match_summary['import'], [])

    def test_two_archived_patients_matching_the_same_existing_patient_are_both_excluded(self):
        existing = self.make_patient(bht='BHT-1', pin='PIN-1')
        result = self.result_for([(1, {'bht': 'BHT-1'}), (2, {'pin': 'PIN-1'})])
        excluded = {e['archive_pk']: e for e in result.match_summary['excluded']}
        self.assertEqual(set(excluded), {1, 2})
        for entry in excluded.values():
            self.assertEqual(entry['reason'], 'ambiguous-conflict')
            self.assertEqual(entry['existing_patient_ids'], [existing.id])
        self.assertEqual(result.match_summary['skip'], [])
        self.assertEqual(result.match_summary['import'], [])

    def test_three_archived_patients_matching_the_same_existing_patient_are_all_excluded(self):
        existing = self.make_patient(bht='BHT-1', pin='PIN-1', nnc_no='NNC-1')
        result = self.result_for([(1, {'bht': 'BHT-1'}), (2, {'pin': 'PIN-1'}), (3, {'nnc_no': 'NNC-1'})])
        excluded = {e['archive_pk']: e for e in result.match_summary['excluded']}
        self.assertEqual(set(excluded), {1, 2, 3})
        for entry in excluded.values():
            self.assertEqual(entry['existing_patient_ids'], [existing.id])

    def test_missing_institution_excludes_everyone_with_no_matching_attempted(self):
        result = self.result_for([(1, {'bht': 'BHT-1'}), (2, {})], institutions=['ghost-hosp'])
        self.assertIsNone(result.match_summary['target_institution_id'])
        self.assertEqual(result.match_summary['institution_slug'], 'ghost-hosp')
        excluded = {e['archive_pk']: e for e in result.match_summary['excluded']}
        self.assertEqual(set(excluded), {1, 2})
        for entry in excluded.values():
            self.assertEqual(entry['reason'], 'missing-institution')
            self.assertEqual(entry['matched_fields'], [])
            self.assertEqual(entry['existing_patient_ids'], [])
        self.assertEqual(excluded[1]['identifiers'], {'bht': 'BHT-1'})
        self.assertEqual(excluded[2]['identifiers'], {})
        self.assertEqual(result.match_summary['skip'], [])
        self.assertEqual(result.match_summary['import'], [])

    def test_ambiguous_institutions_list_is_treated_as_unresolvable(self):
        # scope_type=single but the manifest names two slugs: cannot be
        # resolved to one institution, so every patient is excluded.
        result = self.result_for([(1, {'bht': 'BHT-1'})], institutions=['test-hosp', 'other-hosp'])
        self.assertIsNone(result.match_summary['target_institution_id'])
        self.assertIsNone(result.match_summary['institution_slug'])
        self.assertEqual(result.match_summary['excluded'][0]['reason'], 'missing-institution')

    def test_multi_scope_gets_no_match_summary(self):
        result = self.result_for(
            [(1, {'bht': 'BHT-1'})], scope_type='multi', institutions=['test-hosp', 'other-hosp'],
        )
        self.assertIsNone(result.match_summary)

    def test_system_scope_gets_no_match_summary(self):
        result = self.result_for([(1, {'bht': 'BHT-1'})], scope_type='system', institutions=[])
        self.assertIsNone(result.match_summary)

    def test_non_date_scoped_archive_gets_no_match_summary(self):
        result = self.result_for(
            [(1, {'bht': 'BHT-1'})], date_filter={'applied': False, 'start': None, 'end': None},
        )
        self.assertIsNone(result.match_summary)

    def test_full_scope_archive_never_runs_stage_6(self):
        path = self.archive_path()
        build_archive(path)  # default: no date filter
        result = self.validate(path, allow_unverified=True)
        self.assertIsNone(result.match_summary)

    def test_only_matched_fields_count_not_the_whole_record(self):
        # bht matches, but nnc_no differs from any existing patient's -- only
        # 'bht' should be named as a matched field.
        existing = self.make_patient(bht='BHT-1', nnc_no='NNC-EXISTING')
        result = self.result_for([(1, {'bht': 'BHT-1', 'nnc_no': 'NNC-ARCHIVE'})])
        self.assertEqual(result.match_summary['skip'], [
            {
                'archive_pk': 1, 'matched_fields': ['bht'],
                'identifiers': {'bht': 'BHT-1', 'nnc_no': 'NNC-ARCHIVE'},
                'existing_patient_ids': [existing.id],
            },
        ])

    def test_malformed_patient_record_raises_export_format_error(self):
        path = self.archive_path()
        db_export = json.dumps({
            "patients.patient": [{"model": "patients.patient", "fields": {}}],  # no pk
            "video.video": [],
        }).encode("utf-8")
        build_archive(path, db_export=db_export, manifest_overrides={
            'date_filter': {'applied': True, 'start': '2026-01-01', 'end': None},
        })
        with self.assertRaises(ExportFormatError):
            self.validate(path, allow_unverified=True)

    # -- system-wide matching (identifiers are globally unique) -------------

    def test_identifier_held_by_a_patient_in_another_institution_is_a_skip(self):
        other = Institution.objects.create(name='Other Hosp', slug='other-hosp', created_by=self.user)
        existing = self.make_patient(bht='BHT-1', institution=other)
        result = self.result_for([(1, {'bht': 'BHT-1'})])
        self.assertEqual(result.match_summary['import'], [])
        self.assertEqual(result.match_summary['excluded'], [])
        self.assertEqual(result.match_summary['skip'], [
            {
                'archive_pk': 1, 'matched_fields': ['bht'], 'identifiers': {'bht': 'BHT-1'},
                'existing_patient_ids': [existing.id],
            },
        ])

    def test_identifier_held_by_a_patient_with_no_institution_is_a_skip(self):
        existing = self.make_patient(pin='PIN-9', institution=None)
        result = self.result_for([(1, {'pin': 'PIN-9'})])
        self.assertEqual(result.match_summary['import'], [])
        self.assertEqual([e['existing_patient_ids'] for e in result.match_summary['skip']], [[existing.id]])

    def test_matches_across_institutions_are_still_ambiguous_together(self):
        other = Institution.objects.create(name='Other Hosp', slug='other-hosp', created_by=self.user)
        p1 = self.make_patient(bht='BHT-1')
        p2 = self.make_patient(pin='PIN-1', institution=other)
        result = self.result_for([(1, {'bht': 'BHT-1', 'pin': 'PIN-1'})])
        excluded = result.match_summary['excluded']
        self.assertEqual([e['reason'] for e in excluded], ['ambiguous-conflict'])
        self.assertEqual(sorted(excluded[0]['existing_patient_ids']), sorted([p1.id, p2.id]))
        self.assertEqual(excluded[0]['identifiers'], {'bht': 'BHT-1', 'pin': 'PIN-1'})

    # -- duplicates inside the archive --------------------------------------

    def test_duplicate_archive_pk_is_refused(self):
        path = self.build([(1, {'bht': 'A'}), (1, {'bht': 'B'})])
        with self.assertRaises(ExportFormatError) as ctx:
            self.validate(path, allow_unverified=True)
        self.assertIn('Patient 1 appears more than once in db_export.json', ctx.exception.message)

    def test_patient_key_listed_twice_is_refused(self):
        record = '{"model": "patients.patient", "pk": %d, "fields": {}}'
        raw = ('{"patients.patient": [%s], "patients.patient": [%s]}' % (record % 1, record % 2)).encode('utf-8')
        path = self.archive_path()
        build_archive(path, db_export=raw, manifest_overrides={
            'date_filter': {'applied': True, 'start': '2026-01-01', 'end': None},
        })
        with self.assertRaises(ExportFormatError) as ctx:
            self.validate(path, allow_unverified=True)
        self.assertIn("lists 'patients.patient' more than once", ctx.exception.message)

    def test_same_identifier_value_on_two_archived_patients_is_refused(self):
        path = self.build([(1, {'bht': 'BHT-1'}), (2, {'bht': 'BHT-1'})])
        with self.assertRaises(ExportFormatError) as ctx:
            self.validate(path, allow_unverified=True)
        self.assertIn("The patient identifier bht 'BHT-1' appears on more than one patient", ctx.exception.message)

    def test_same_value_in_two_different_identifier_fields_is_not_a_duplicate(self):
        result = self.result_for([(1, {'bht': 'X-1'}), (2, {'nnc_no': 'X-1'})])
        self.assertEqual([e['archive_pk'] for e in result.match_summary['import']], [1, 2])

    def test_empty_identifiers_repeated_are_not_duplicates(self):
        result = self.result_for([(1, {'bht': '', 'pin': None}), (2, {'bht': '', 'pin': None})])
        self.assertEqual([e['archive_pk'] for e in result.match_summary['import']], [1, 2])

    # -- chunked lookups -----------------------------------------------------

    def test_chunked_lookups_give_the_same_partition_as_unchunked(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        e1 = self.make_patient(bht='B1', pin='P1')
        e2 = self.make_patient(bht='B2')
        e3 = self.make_patient(bht='B3', nnc_no='N3')
        self.make_patient(bht='B4')
        entries = [
            (1, {'bht': 'B1'}),                  # skip e1
            (2, {'bht': 'B2', 'nnc_no': 'N2'}),  # skip e2
            (3, {'bht': 'B3'}),                  # skip e3 ...
            (4, {'nnc_no': 'N3'}),               # ... shared with 3 -> both excluded
            (5, {'bht': 'B5'}),                  # import
            (6, {'bht': 'B6', 'pin': 'P6'}),     # import
            (7, {}),                             # import
            (8, {'bht': 'B4', 'pin': 'P1'}),     # matches two existing -> excluded
        ]
        path = self.build(entries)

        with CaptureQueriesContext(connection) as unchunked_queries:
            unchunked = self.validate(path, allow_unverified=True).match_summary
        with mock.patch.object(restore_validation, 'IDENTIFIER_LOOKUP_CHUNK_SIZE', 2):
            with CaptureQueriesContext(connection) as chunked_queries:
                chunked = self.validate(path, allow_unverified=True).match_summary

        self.assertEqual(chunked, unchunked)
        self.assertEqual([e['archive_pk'] for e in unchunked['skip']], [1, 2])
        self.assertEqual([e['archive_pk'] for e in unchunked['excluded']], [3, 4, 8])
        self.assertEqual([e['archive_pk'] for e in unchunked['import']], [5, 6, 7])
        self.assertEqual(unchunked['skip'][0]['existing_patient_ids'], [e1.id])
        self.assertEqual(unchunked['skip'][1]['existing_patient_ids'], [e2.id])
        self.assertEqual(unchunked['excluded'][0]['existing_patient_ids'], [e3.id])
        # ... and the tiny chunk size really did split the lookups.
        self.assertGreater(len(chunked_queries), len(unchunked_queries))

    # -- the date-scoped gate matches the preview's ------------------------------

    def test_a_date_bound_without_applied_still_runs_stage_6(self):
        existing = self.make_patient(bht='BHT-1')
        for date_filter in (
            {'applied': False, 'start': '2026-01-01', 'end': None},
            {'applied': False, 'start': None, 'end': '2026-02-01'},
        ):
            with self.subTest(date_filter=date_filter):
                result = self.result_for([(1, {'bht': 'BHT-1'})], date_filter=date_filter)
                self.assertIsNotNone(result.match_summary)
                self.assertEqual(result.match_summary['skip'][0]['existing_patient_ids'], [existing.id])

    def test_is_date_scoped_normalisation(self):
        is_date_scoped = restore_validation._is_date_scoped
        self.assertTrue(is_date_scoped({'applied': True}))
        self.assertTrue(is_date_scoped({'applied': False, 'start': '2026-01-01'}))
        self.assertTrue(is_date_scoped({'applied': False, 'end': '2026-01-01'}))
        self.assertFalse(is_date_scoped({'applied': False, 'start': None, 'end': None}))
        self.assertFalse(is_date_scoped(None))

    # -- identifier typing -----------------------------------------------------

    def test_non_text_identifier_value_is_refused(self):
        for bad in (12345, 0, True, ['A'], {'a': 1}):
            with self.subTest(bad=bad):
                path = self.build([(1, {'bht': bad})])
                with self.assertRaises(ExportFormatError) as ctx:
                    self.validate(path, allow_unverified=True)
                self.assertIn('bht value that is not text', ctx.exception.message)

    def test_null_and_empty_identifiers_are_simply_unpopulated(self):
        result = self.result_for([(1, {'bht': None, 'nnc_no': '', 'pin': 'P-1'})])
        self.assertEqual(result.match_summary['import'][0]['identifiers'], {'pin': 'P-1'})

    # -- _extract_patient_identity failure branches ---------------------------

    def test_extract_patient_identity_failure_branches(self):
        fields = ('bht', 'nnc_no', 'ptc_no', 'pc_no', 'pin')
        good = {'model': 'patients.patient', 'pk': 7, 'fields': {'bht': 'X'}}
        self.assertEqual(restore_validation._extract_patient_identity(good, fields), (7, {'bht': 'X'}))
        cases = {
            'non-dict record': ['not', 'a', 'dict'],
            'bool pk': {**good, 'pk': True},
            'string pk': {**good, 'pk': '7'},
            'missing pk': {k: v for k, v in good.items() if k != 'pk'},
            'wrong model label': {**good, 'model': 'patients.attachment'},
            'missing model label': {k: v for k, v in good.items() if k != 'model'},
            'missing fields': {k: v for k, v in good.items() if k != 'fields'},
            'non-dict fields': {**good, 'fields': ['bht']},
        }
        for label, record in cases.items():
            with self.subTest(label):
                with self.assertRaises(ExportFormatError):
                    restore_validation._extract_patient_identity(record, fields)

    # -- no patients.patient key at all -----------------------------------------

    def test_export_without_a_patients_key_gives_an_empty_partition(self):
        path = self.archive_path()
        build_archive(
            path, db_export=json.dumps({"video.video": []}).encode('utf-8'),
            manifest_overrides={'date_filter': {'applied': True, 'start': '2026-01-01', 'end': None}},
        )
        result = self.validate(path, allow_unverified=True)
        self.assertEqual(
            {k: result.match_summary[k] for k in ('skip', 'import', 'excluded')},
            {'skip': [], 'import': [], 'excluded': []},
        )
        self.assertEqual(result.match_summary['institution_slug'], 'test-hosp')
