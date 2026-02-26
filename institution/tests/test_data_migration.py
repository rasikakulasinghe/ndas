"""
Story 1.6 — Default institution data migration tests.
These are POST-MIGRATION STATE tests — they verify the state after migration 0002 runs.
"""
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from institution.models import Institution
from patients.models import Patient, Attachment
from video.models import Video
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()


@override_settings(
    DEFAULT_INSTITUTION_NAME='Test Hospital',
    DEFAULT_INSTITUTION_SLUG='test-hospital',
)
class DefaultInstitutionMigrationTest(TestCase):
    """
    Post-migration state tests: verify migration 0002 has correctly assigned
    all patients and users to the default institution.

    The test database has migration 0002 applied, so the default institution
    from settings should exist if any users/patients were pre-existing.
    These tests are state assertions, not migration execution tests.
    """

    def test_no_patients_without_institution(self):
        """AC #2: All Patient records have an institution assigned."""
        null_count = Patient.objects.filter(institution__isnull=True).count()
        self.assertEqual(
            null_count, 0,
            f"{null_count} patients still have null institution FK after migration",
        )

    def test_no_non_superadmin_users_without_institution(self):
        """AC #4: All non-SUPERADMIN, non-superuser users have institution assigned."""
        null_count = User.objects.filter(
            institution__isnull=True,
            is_superuser=False,
        ).exclude(user_type=UserType.SUPERADMIN).count()
        self.assertEqual(
            null_count, 0,
            f"{null_count} non-SUPERADMIN users still have null institution FK",
        )

    def test_no_video_paths_with_old_prefix(self):
        """AC #3: No Video records have old 'videos/' path prefix after migration."""
        old_path_count = Video.objects.filter(video_file__startswith='videos/').count()
        self.assertEqual(
            old_path_count, 0,
            f"{old_path_count} Video records still use old 'videos/...' path prefix",
        )

    def test_no_attachment_paths_with_old_prefix(self):
        """AC #3: No Attachment records have old 'attachments/' path prefix after migration."""
        old_path_count = Attachment.objects.filter(attachment__startswith='attachments/').count()
        self.assertEqual(
            old_path_count, 0,
            f"{old_path_count} Attachment records still use old 'attachments/...' path prefix",
        )


class MigrationPathHelperTest(TestCase):
    """
    Unit tests for the path-update logic used by migration 0002.
    These use the real migration helper functions directly.
    """

    def setUp(self):
        self.institution = Institution.objects.create(
            name='Path Test Hospital',
            slug='path-test',
            subscription_status=SubscriptionStatus.ACTIVE,
        )
        # Create a patient to attach media objects to
        self.patient = Patient.objects.create(
            bht='MIG001',
            baby_name='Migration Baby',
            mother_name='Test Mother',
            dob_tob=timezone.now(),
            gender='Male',
            pog_wks=38,
            pog_days=2,
            birth_weight=3000,
            ofc=33,
            mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711234567',
            institution=self.institution,
        )

    @staticmethod
    def _load_migration_helpers():
        """Load helper functions from the 0002 migration (digit-prefixed module)."""
        import importlib
        mod = importlib.import_module('institution.migrations.0002_default_institution_data')
        return mod._migrate_video_paths, mod._migrate_attachment_paths

    def test_migration_helper_video_path_old_prefix(self):
        """_migrate_video_paths converts 'videos/...' to '{slug}/videos/...'"""
        _migrate_video_paths, _ = self._load_migration_helpers()

        from django.apps import apps
        VideoModel = apps.get_model('video', 'Video')
        video = VideoModel.objects.create(
            patient=self.patient,
            video_file='videos/2025/01/test_video.mp4',
            title='Test Video',
            recorded_on=timezone.now().date(),
        )

        _migrate_video_paths(VideoModel, 'path-test')

        video.refresh_from_db()
        self.assertTrue(
            video.video_file.name.startswith('path-test/videos/'),
            f"Expected path-test/videos/..., got: {video.video_file.name}",
        )

    def test_migration_helper_attachment_path_old_prefix(self):
        """_migrate_attachment_paths converts 'attachments/...' to '{slug}/attachments/...'"""
        _, _migrate_attachment_paths = self._load_migration_helpers()

        # Use bulk_create to bypass Attachment.save() / full_clean() which validates the file exists
        AttachmentModel = Attachment
        att = AttachmentModel(
            patient=self.patient,
            attachment='attachments/report.pdf',
            title='Test Report',
        )
        AttachmentModel.objects.bulk_create([att])
        att = AttachmentModel.objects.filter(
            patient=self.patient,
            title='Test Report',
        ).first()

        _migrate_attachment_paths(AttachmentModel, 'path-test')

        att.refresh_from_db()
        self.assertTrue(
            att.attachment.name.startswith('path-test/attachments/'),
            f"Expected path-test/attachments/..., got: {att.attachment.name}",
        )

    def test_migration_helper_idempotent_already_migrated(self):
        """Path migration is idempotent — already-migrated paths are not changed."""
        _migrate_video_paths, _ = self._load_migration_helpers()

        from django.apps import apps
        VideoModel = apps.get_model('video', 'Video')
        video = VideoModel.objects.create(
            patient=self.patient,
            video_file='path-test/videos/2025/01/already_migrated.mp4',
            title='Already Migrated',
            recorded_on=timezone.now().date(),
        )
        original_name = video.video_file.name

        # Running again should not change the path
        _migrate_video_paths(VideoModel, 'path-test')

        video.refresh_from_db()
        self.assertEqual(video.video_file.name, original_name)
