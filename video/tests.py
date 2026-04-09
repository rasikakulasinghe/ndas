"""
CRUD operation tests for the video app.

Covers: Video manager (list), add (GET), view (detail), edit, delete.
Note: Actual file upload tests are skipped because validate_video_file
      requires real MIME type inspection. The focus here is on view
      access control, GET rendering, and DELETE mechanics.
"""

import json
from datetime import timedelta
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from patients.models import Patient
from video.models import Video

User = get_user_model()

STATIC_OVERRIDE = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)


# ---------------------------------------------------------------------------
# Shared setUp base
# ---------------------------------------------------------------------------

class VideoTestBase(TestCase):
    """Shared setup for all video CRUD tests."""

    PASSWORD = 'SecurePass123!'

    def setUp(self):
        self.client = Client()

        self.superuser = User.objects.create_superuser(
            username='admin',
            password=self.PASSWORD,
            email='admin@test.com',
        )
        self.staff_user = User.objects.create_user(
            username='staff',
            password=self.PASSWORD,
            email='staff@test.com',
            is_staff=True,
        )
        self.other_staff = User.objects.create_user(
            username='other_staff',
            password='OtherPass123!',
            email='other@test.com',
            is_staff=True,
        )

        self.patient = Patient.objects.create(
            bht='BHT-VID-001',
            baby_name='Video Baby',
            mother_name='Video Mother',
            gender='Male',
            dob_tob=timezone.now() - timedelta(days=30),
            mo_delivery='Normal vaginal delivery (NVD)',
            pog_wks=38,
            pog_days=0,
            birth_weight=3000,
            ofc=34,
            tp_mobile='0771234567',
            added_by=self.staff_user,
        )

        # Create a Video record directly (bypass file validation for unit tests)
        self.video = Video(
            title='Test Video 001',
            patient=self.patient,
            recorded_on=timezone.now() - timedelta(days=1),
            added_by=self.staff_user,
        )
        self.video.video_file.name = 'videos/test_video_001.mp4'
        self.video.save()


# ---------------------------------------------------------------------------
# 1. Video List (manager)
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class VideoManagerViewTest(VideoTestBase):
    """Test video manager (list) view."""

    def test_manager_returns_200_for_staff(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('video:manager'))
        self.assertEqual(response.status_code, 200)

    def test_manager_redirects_unauthenticated(self):
        response = self.client.get(reverse('video:manager'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_manager_by_patient_returns_200(self):
        self.client.force_login(self.staff_user)
        url = reverse('video:manager-by-patient', kwargs={'patient_id': self.patient.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# 2. Video Add (GET only — POST requires real file)
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class VideoAddViewTest(VideoTestBase):
    """Test video add view."""

    def test_add_get_returns_200(self):
        self.client.force_login(self.staff_user)
        url = reverse('video:add', kwargs={'patient_id': self.patient.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_add_get_with_invalid_patient_redirects(self):
        # @handle_view_errors catches Http404 and redirects rather than propagating 404
        self.client.force_login(self.staff_user)
        url = reverse('video:add', kwargs={'patient_id': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_add_redirects_unauthenticated(self):
        url = reverse('video:add', kwargs={'patient_id': self.patient.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


# ---------------------------------------------------------------------------
# 3. Video Detail View
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class VideoDetailViewTest(VideoTestBase):
    """Test video detail (view) operation."""

    def test_view_returns_200_for_owner(self):
        self.client.force_login(self.staff_user)
        url = reverse('video:view', kwargs={'video_id': self.video.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view_returns_200_for_superuser(self):
        self.client.force_login(self.superuser)
        url = reverse('video:view', kwargs={'video_id': self.video.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view_nonexistent_video_returns_404(self):
        self.client.force_login(self.staff_user)
        url = reverse('video:view', kwargs={'video_id': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_view_redirects_unauthenticated(self):
        url = reverse('video:view', kwargs={'video_id': self.video.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_other_staff_can_view_video(self):
        """All staff users can view any video (permission: not is_staff AND not owner)."""
        self.client.force_login(self.other_staff)
        url = reverse('video:view', kwargs={'video_id': self.video.pk})
        response = self.client.get(url)
        # Staff permission check: only non-staff non-owners are blocked
        self.assertEqual(response.status_code, 200)

    def test_non_owner_non_staff_cannot_view_video(self):
        """Non-staff user who did not upload the video is blocked."""
        non_owner = User.objects.create_user(
            username='non_owner',
            password=self.PASSWORD,
            email='nonowner@test.com',
        )
        self.client.force_login(non_owner)
        url = reverse('video:view', kwargs={'video_id': self.video.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('patient', response.url)


# ---------------------------------------------------------------------------
# 4. Video Edit View
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class VideoEditViewTest(VideoTestBase):
    """Test video edit operation."""

    def test_edit_get_returns_200_for_owner(self):
        self.client.force_login(self.staff_user)
        url = reverse('video:edit', kwargs={'video_id': self.video.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_edit_get_for_superuser_returns_200(self):
        self.client.force_login(self.superuser)
        url = reverse('video:edit', kwargs={'video_id': self.video.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_other_staff_can_edit_video(self):
        """All staff users can edit any video (permission: not is_staff AND not owner)."""
        self.client.force_login(self.other_staff)
        url = reverse('video:edit', kwargs={'video_id': self.video.pk})
        response = self.client.get(url)
        # Staff bypass the permission check (only non-staff non-owners are blocked)
        self.assertEqual(response.status_code, 200)

    def test_edit_post_redirects(self):
        # Video edit POST without a file clears the FileField (FileInput behaviour),
        # which causes the view to redirect (either to view on success, or to manager
        # via @handle_view_errors). Either way a redirect is expected.
        self.client.force_login(self.staff_user)
        url = reverse('video:edit', kwargs={'video_id': self.video.pk})
        response = self.client.post(url, {
            'title': 'Updated Title 001',
            'recorded_on': (timezone.now() - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S'),
        })
        self.assertEqual(response.status_code, 302)
        self.video.refresh_from_db()
        self.assertEqual(self.video.title, 'Updated Title 001')
        self.assertTrue(self.video.video_file.name)  # file reference preserved

    def test_edit_nonexistent_video_redirects(self):
        # @handle_view_errors catches Http404 and redirects rather than propagating 404
        self.client.force_login(self.staff_user)
        url = reverse('video:edit', kwargs={'video_id': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_edit_redirects_unauthenticated(self):
        url = reverse('video:edit', kwargs={'video_id': self.video.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


# ---------------------------------------------------------------------------
# 5. Video Delete View
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class VideoDeleteViewTest(VideoTestBase):
    """Test video delete operation (DELETE + JSON password)."""

    def _delete_request(self, video_id, password, user):
        self.client.force_login(user)
        url = reverse('video:delete', kwargs={'video_id': video_id})
        return self.client.delete(
            url,
            data=json.dumps({'password': password}),
            content_type='application/json',
        )

    def test_superuser_can_delete_video(self):
        response = self._delete_request(self.video.pk, self.PASSWORD, self.superuser)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'), msg=data)
        self.assertFalse(Video.objects.filter(pk=self.video.pk).exists())

    def test_owner_can_delete_own_video(self):
        response = self._delete_request(self.video.pk, self.PASSWORD, self.staff_user)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'), msg=data)
        self.assertFalse(Video.objects.filter(pk=self.video.pk).exists())

    def test_non_owner_cannot_delete(self):
        response = self._delete_request(self.video.pk, 'OtherPass123!', self.other_staff)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Video.objects.filter(pk=self.video.pk).exists())

    def test_wrong_password_is_rejected(self):
        self.client.force_login(self.superuser)
        url = reverse('video:delete', kwargs={'video_id': self.video.pk})
        response = self.client.delete(
            url,
            data=json.dumps({'password': 'WrongPassword!'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)
        self.assertTrue(Video.objects.filter(pk=self.video.pk).exists())

    def test_missing_password_returns_400(self):
        self.client.force_login(self.superuser)
        url = reverse('video:delete', kwargs={'video_id': self.video.pk})
        response = self.client.delete(
            url,
            data=json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_nonexistent_video_returns_error(self):
        # get_object_or_404 raises Http404 which is now explicitly caught
        # inside video_delete and returned as 404 JSON.
        self.client.force_login(self.superuser)
        url = reverse('video:delete', kwargs={'video_id': 99999})
        response = self.client.delete(
            url,
            data=json.dumps({'password': self.PASSWORD}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertFalse(data.get('success'))

    def test_delete_requires_authentication(self):
        url = reverse('video:delete', kwargs={'video_id': self.video.pk})
        response = self.client.delete(
            url,
            data=json.dumps({'password': self.PASSWORD}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)
