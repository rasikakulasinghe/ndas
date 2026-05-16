"""
Security tests for video app.

Covers: AC 12-14 (Fix #12 staff lateral access to video edit).
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from institution.models import Institution
from patients.models import Patient
from video.models import Video

User = get_user_model()

STATIC_OVERRIDE = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
    MULTI_INSTITUTION_ENABLED=True,
    RATELIMIT_ENABLE=False,
)


class VideoSecurityBase(TestCase):
    """Shared setup for video permission tests."""

    def setUp(self):
        self.client = Client()
        self.inst_a = Institution.objects.create(name='Video Inst A', slug='vid-inst-a')

        self.superuser = User.objects.create_superuser(
            username='super', password='SuperPass123!', email='super@test.com',
            mobile_primary='0700000001',
        )
        self.staff_owner = User.objects.create_user(
            username='staff_owner', password='StaffPass123!', email='owner@test.com',
            is_staff=True, institution=self.inst_a, mobile_primary='0700000002',
        )
        self.staff_other = User.objects.create_user(
            username='staff_other', password='StaffPass123!', email='other@test.com',
            is_staff=True, institution=self.inst_a, mobile_primary='0700000003',
        )

        self.patient = Patient.objects.create(
            bht='BHT-VID-001',
            baby_name='Video Baby',
            mother_name='Video Mother',
            gender='Male',
            dob_tob=timezone.now() - timezone.timedelta(days=30),
            mo_delivery='Normal vaginal delivery (NVD)',
            pog_wks=38,
            pog_days=0,
            birth_weight=3000,
            ofc=34,
            tp_mobile='0771234567',
            institution=self.inst_a,
            added_by=self.staff_owner,
        )
        # Use bulk_create to bypass Video.save() which calls video_file.size on real storage
        self.video = Video.objects.bulk_create([Video(
            patient=self.patient,
            title='TestVideo',
            video_file='videos/test_video.mp4',
            recorded_on=timezone.now(),
            added_by=self.staff_owner,
        )])[0]


@STATIC_OVERRIDE
class VideoEditPermissionTest(VideoSecurityBase):
    """AC 12-14: Staff lateral access prevention on video_edit."""

    def test_staff_cannot_edit_peer_video(self):
        """AC 12: Staff from same institution cannot edit a video uploaded by a colleague."""
        self.client.force_login(self.staff_other)
        url = reverse('video:edit', kwargs={'video_id': self.video.id})
        response = self.client.get(url)
        # Expect redirect with permission-denied message (302)
        self.assertEqual(response.status_code, 302)

    def test_staff_can_edit_own_video(self):
        """AC 13: Staff can edit a video they uploaded themselves."""
        self.client.force_login(self.staff_owner)
        url = reverse('video:edit', kwargs={'video_id': self.video.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_edit_any_video(self):
        """AC 14: Superuser can edit any video regardless of added_by."""
        self.client.force_login(self.superuser)
        url = reverse('video:edit', kwargs={'video_id': self.video.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
