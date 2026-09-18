"""
backup/tests/test_services.py — Story 1.1

Covers the export-service half of the I/O matrix: the fixed 13-model plan
and its ordering, institution scoping (no cross-institution leakage), every
model key present even when empty, the media layout inside the archive, and
the disk-space pre-check.
"""
import json
import shutil
import zipfile
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from backup.models import BackupJob
from backup.services import (
    _model_export_plan,
    create_export,
    estimate_export_size_bytes,
    get_archive_dir,
    has_sufficient_disk_space,
)
from institution.models import Institution
from ndas.custom_codes.choice import BackupJobStatus, BackupJobType
from patients.models import Attachment, Patient
from problemlist.models import Problem, ProblemAction
from video.models import Video

User = get_user_model()

EXPECTED_KEYS_IN_ORDER = [
    'patients.patient',
    'referral.referralsent',
    'referral.referralreceived',
    'referral.referralmessage',
    'video.video',
    'patients.attachment',
    'patients.gmassessment',
    'patients.hineassessment',
    'patients.developmentalassessment',
    'patients.cdicrecord',
    'patients.generalpaediatricassessment',
    'problemlist.problem',
    'problemlist.problemaction',
]

STORAGE_OVERRIDE = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)


def make_patient(institution, user, baby_name='Baby One', bht='BHT-001'):
    return Patient.objects.create(
        bht=bht,
        baby_name=baby_name,
        mother_name='Test Mother',
        dob_tob=timezone.now(),
        gender='Male',
        pog_wks=38,
        pog_days=2,
        birth_weight=3000,
        ofc=33,
        mo_delivery='Normal vaginal delivery (NVD)',
        tp_mobile='0711234567',
        institution=institution,
        added_by=user,
    )


@STORAGE_OVERRIDE
class ModelExportPlanTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa1', password='x', position='Administrator', mobile_primary='0770000101',
        )
        self.inst = Institution.objects.create(name='Plan Hosp', slug='plan-hosp', created_by=self.user)

    def test_plan_has_13_models_in_spec_order(self):
        plan = _model_export_plan(self.inst)
        keys = [k for k, _ in plan]
        self.assertEqual(keys, EXPECTED_KEYS_IN_ORDER)

    def test_notification_and_bookmark_excluded(self):
        plan = _model_export_plan(self.inst)
        keys = [k for k, _ in plan]
        self.assertNotIn('referral.notification', keys)
        self.assertNotIn('patients.bookmark', keys)


@STORAGE_OVERRIDE
class CreateExportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa2', password='x', position='Administrator', mobile_primary='0770000102',
        )
        self.inst_a = Institution.objects.create(name='Export Hosp A', slug='export-hosp-a', created_by=self.user)
        self.inst_b = Institution.objects.create(name='Export Hosp B', slug='export-hosp-b', created_by=self.user)

        self.patient_a = make_patient(self.inst_a, self.user, 'Baby A', 'BHT-A-1')
        self.patient_b = make_patient(self.inst_b, self.user, 'Baby B', 'BHT-B-1')

        self.video_a = Video.objects.create(
            patient=self.patient_a,
            title='VidA',
            recorded_on=timezone.now(),
            video_file=SimpleUploadedFile('a.mp4', b'video-a-bytes', content_type='video/mp4'),
            added_by=self.user,
        )
        self.attachment_a = Attachment.objects.create(
            patient=self.patient_a,
            title='AttA',
            attachment_type='document',
            attachment=SimpleUploadedFile('a.txt', b'attachment-a-bytes'),
            added_by=self.user,
        )
        self.problem_a = Problem.objects.create(patient=self.patient_a, name='Asthma', added_by=self.user)
        ProblemAction.objects.create(problem=self.problem_a, action='Reviewed', added_by=self.user)

        self.job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.PENDING,
            scope=self.inst_a,
            triggered_by=self.user,
        )

    def tearDown(self):
        shutil.rmtree(get_archive_dir(self.job), ignore_errors=True)

    def _export(self):
        path, skipped = create_export(self.job)
        return path

    def _export_with_skipped(self):
        return create_export(self.job)

    def _read_db_export(self, path):
        with zipfile.ZipFile(path) as zf:
            return json.loads(zf.read('db_export.json'))

    def test_all_13_keys_present_even_when_empty(self):
        data = self._read_db_export(self._export())
        self.assertEqual(len(data), 13)
        for key in EXPECTED_KEYS_IN_ORDER:
            self.assertIn(key, data)
        # No GMAssessment/HINE/etc seeded for this institution -> present but empty.
        self.assertEqual(data['patients.gmassessment'], [])
        self.assertEqual(data['patients.hineassessment'], [])

    def test_scoped_to_triggering_institution_only(self):
        data = self._read_db_export(self._export())
        patient_pks = [rec['pk'] for rec in data['patients.patient']]
        self.assertIn(self.patient_a.pk, patient_pks)
        self.assertNotIn(self.patient_b.pk, patient_pks)
        self.assertEqual(len(data['patients.patient']), 1)

    def test_related_records_included(self):
        data = self._read_db_export(self._export())
        self.assertEqual(len(data['video.video']), 1)
        self.assertEqual(len(data['patients.attachment']), 1)
        self.assertEqual(len(data['problemlist.problem']), 1)
        self.assertEqual(len(data['problemlist.problemaction']), 1)

    def test_media_copied_with_existing_institution_slug_layout(self):
        path = self._export()
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        self.assertTrue(
            any(n.startswith(f'media/{self.inst_a.slug}/videos/') for n in names), names
        )
        self.assertTrue(
            any(n.startswith(f'media/{self.inst_a.slug}/attachments/') for n in names), names
        )
        # No institution B media leaked into institution A's archive.
        self.assertFalse(any(self.inst_b.slug in n for n in names), names)

    def test_archive_stored_under_backups_dir_not_media_or_static_root(self):
        path = self._export()
        self.assertTrue(str(path).startswith(str(settings.BASE_DIR / 'backups')))
        self.assertNotIn(str(settings.MEDIA_ROOT), str(path))

    def test_progress_callback_reaches_100_range(self):
        seen = []
        create_export(self.job, progress_callback=seen.append)
        self.assertTrue(seen)
        self.assertEqual(max(seen), 100)

    def test_missing_media_file_reported_not_silently_dropped(self):
        # video_a's underlying file is deleted from disk before export runs --
        # the export must still complete, but must report exactly what it skipped
        # (human-approved policy: complete with a warning, not a silent success).
        self.video_a.video_file.delete(save=False)
        path, skipped = self._export_with_skipped()
        self.assertTrue(skipped, "expected the missing video file to be reported as skipped")
        self.assertTrue(any('a.mp4' in s or 'missing' in s for s in skipped), skipped)
        # The archive itself still completes -- everything else still got exported.
        data = self._read_db_export(path)
        self.assertEqual(len(data['video.video']), 1)

    def test_no_skipped_media_when_everything_present(self):
        path, skipped = self._export_with_skipped()
        self.assertEqual(skipped, [])

    def test_scope_none_raises_instead_of_silently_exporting_nothing(self):
        # Story 1.1 never creates a job with scope=None itself; reaching this
        # state means the institution was deleted after job creation (SET_NULL).
        # create_export must fail loudly, not silently scope-less-query.
        self.job.scope = None
        self.job.save(update_fields=['scope'])
        with self.assertRaises(ValueError):
            create_export(self.job)


@STORAGE_OVERRIDE
class DiskSpaceCheckTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa3', password='x', position='Administrator', mobile_primary='0770000103',
        )
        self.inst = Institution.objects.create(name='Disk Hosp', slug='disk-hosp', created_by=self.user)

    def test_sufficient_when_plenty_of_free_space(self):
        with mock.patch('backup.services.shutil.disk_usage') as disk_usage:
            disk_usage.return_value = mock.Mock(free=10 * 1024 ** 4)  # 10TB free
            sufficient, estimated, required, free = has_sufficient_disk_space(self.inst)
        self.assertTrue(sufficient)
        self.assertEqual(free, 10 * 1024 ** 4)

    def test_insufficient_when_free_space_below_margin(self):
        with mock.patch('backup.services.shutil.disk_usage') as disk_usage:
            disk_usage.return_value = mock.Mock(free=1024)  # 1KB free
            sufficient, estimated, required, free = has_sufficient_disk_space(self.inst)
        self.assertFalse(sufficient)


@STORAGE_OVERRIDE
class EstimateExportSizeAttachmentZeroTest(TestCase):
    """A recorded file_size of exactly 0 must be trusted, not treated as unset."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_sa4', password='x', position='Administrator', mobile_primary='0770000104',
        )
        self.inst = Institution.objects.create(name='Zero Hosp', slug='zero-hosp', created_by=self.user)
        self.patient = make_patient(self.inst, self.user, 'Baby Zero', 'BHT-Z-1')
        self.attachment = Attachment.objects.create(
            patient=self.patient,
            title='ZeroAtt',
            attachment_type='document',
            attachment=SimpleUploadedFile('zero.txt', b'not-actually-empty'),
            added_by=self.user,
        )
        # Force file_size to a recorded 0 via .update() -- bypasses the
        # model's save() override that would recompute it from the real file.
        Attachment.objects.filter(pk=self.attachment.pk).update(file_size=0)

    def test_recorded_zero_is_trusted_not_recomputed_from_disk(self):
        # If the old `file_size or _safe_file_size(...)` bug were still
        # present, a falsy stored 0 would fall through to this live
        # filesystem read instead -- assert that never happens.
        with mock.patch('backup.services._safe_file_size') as safe_size:
            safe_size.return_value = 999_999
            total = estimate_export_size_bytes(self.inst)
        safe_size.assert_not_called()
        self.assertEqual(total, 0)
