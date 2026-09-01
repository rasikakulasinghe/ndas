"""
patients/tests/test_bookmark_security.py

Regression tests for the bookmark_manager_user IDOR fix.
Part of spec-fix-auth-permission-bypasses.

Ensures a user cannot view another user's private bookmark list, while
still allowing the owning user and superusers to view it.

Also includes BookmarkEditSecurityTest, a regression test for the
bookmark_edit write-access IDOR fix. Part of
spec-fix-bookmark-edit-idor-and-patientlist-bug.
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from django.utils import timezone

from patients.models import Bookmark, Patient
from video.models import Video

User = get_user_model()

STATIC_OVERRIDE = override_settings(
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)


@STATIC_OVERRIDE
class BookmarkManagerUserSecurityTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username='bm_owner',
            password='Testpass1!',
            email='owner@example.com',
            is_staff=True,
        )
        self.other_user = User.objects.create_user(
            username='bm_other',
            password='Testpass1!',
            email='other@example.com',
            is_staff=True,
        )
        self.superuser = User.objects.create_user(
            username='bm_super',
            password='Testpass1!',
            email='super@example.com',
            is_staff=True,
            is_superuser=True,
        )

    def test_own_username_succeeds(self):
        """Given a user requesting their own bookmark list, expect 200."""
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('bookmark-manager-user', kwargs={'username': self.owner.username})
        )
        self.assertEqual(response.status_code, 200)

    def test_other_username_is_forbidden(self):
        """Given a non-superuser requesting another user's list, expect 403 (IDOR fix)."""
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse('bookmark-manager-user', kwargs={'username': self.owner.username})
        )
        self.assertEqual(response.status_code, 403)

    def test_superuser_succeeds_for_any_username(self):
        """Given a superuser requesting any user's list, expect 200 (unchanged)."""
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse('bookmark-manager-user', kwargs={'username': self.owner.username})
        )
        self.assertEqual(response.status_code, 200)


@STATIC_OVERRIDE
class BookmarkEditSecurityTest(TestCase):
    """
    Regression tests for the bookmark_edit write-access IDOR fix.

    Previously, bookmark_edit had no ownership check, so any authenticated
    user could view and overwrite another user's bookmark by guessing/
    incrementing pk. This mirrors bookmark_manager_user's permission model:
    allow when request.user == selected_bm.owner or request.user.is_superuser;
    block (403) otherwise.
    """

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username='be_owner',
            password='Testpass1!',
            email='be_owner@example.com',
            is_staff=True,
        )
        self.other_user = User.objects.create_user(
            username='be_other',
            password='Testpass1!',
            email='be_other@example.com',
            is_staff=True,
        )
        self.superuser = User.objects.create_user(
            username='be_super',
            password='Testpass1!',
            email='be_super@example.com',
            is_staff=True,
            is_superuser=True,
        )
        # Using a real Patient (rather than Video) keeps this fixture's bookmark
        # existence-check exercised regardless of which bookmark_type is chosen —
        # see test_models.py::BookmarkVideoMappingTest for Video-specific coverage.
        self.patient = Patient.objects.create(
            bht='BE-BHT-001',
            baby_name='Bookmark Test Baby',
            mother_name='Bookmark Test Mother',
            dob_tob=timezone.now(),
            gender='Male',
            pog_wks=38,
            pog_days=0,
            birth_weight=3000,
            ofc=33,
            mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711234599',
            added_by=self.owner,
        )
        self.bookmark = Bookmark.objects.create(
            title='Owner Bookmark',
            bookmark_type='Patient',
            object_id=self.patient.pk,
            owner=self.owner,
            added_by=self.owner,
        )

    def _edit_url(self):
        return reverse('bookmark-edit', kwargs={'pk': self.bookmark.pk})

    def test_non_owner_get_is_forbidden(self):
        """Given a non-owner, non-superuser, GET returns 403 and no form is rendered."""
        self.client.force_login(self.other_user)
        response = self.client.get(self._edit_url())
        self.assertEqual(response.status_code, 403)

    def test_non_owner_post_is_forbidden(self):
        """Given a non-owner, non-superuser, POST returns 403 and no data is changed."""
        self.client.force_login(self.other_user)
        response = self.client.post(
            self._edit_url(),
            {'title': 'Hijacked Title', 'description': 'Hijacked'},
        )
        self.assertEqual(response.status_code, 403)
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'Owner Bookmark')

    def test_owner_get_succeeds(self):
        """Given the bookmark's owner, GET behaves unchanged (200)."""
        self.client.force_login(self.owner)
        response = self.client.get(self._edit_url())
        self.assertEqual(response.status_code, 200)

    def test_owner_post_succeeds(self):
        """Given the bookmark's owner, POST behaves unchanged (redirect to bookmark-view)."""
        self.client.force_login(self.owner)
        response = self.client.post(
            self._edit_url(),
            {'title': 'Updated Title', 'description': 'Updated'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('bookmark-view', kwargs={'pk': self.bookmark.pk}))
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'Updated Title')

    def test_superuser_get_succeeds_for_others_bookmark(self):
        """Given a superuser editing another user's bookmark, GET behaves unchanged (200)."""
        self.client.force_login(self.superuser)
        response = self.client.get(self._edit_url())
        self.assertEqual(response.status_code, 200)

    def test_superuser_post_succeeds_for_others_bookmark(self):
        """Given a superuser editing another user's bookmark, POST behaves unchanged (redirect)."""
        self.client.force_login(self.superuser)
        response = self.client.post(
            self._edit_url(),
            {'title': 'Superuser Update', 'description': 'Updated by superuser'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('bookmark-view', kwargs={'pk': self.bookmark.pk}))
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'Superuser Update')

    def test_editing_orphaned_bookmark_post_does_not_500(self):
        """
        Regression: Bookmark.save() now genuinely validates that object_id
        still exists (see spec-fix-gma-timeline-and-video-bookmark-mapping).
        Editing a bookmark whose target was since deleted must show a clean
        error, not raise an uncaught ValidationError/ValueError.
        """
        self.patient.delete()

        self.client.force_login(self.owner)
        response = self.client.post(
            self._edit_url(),
            {'title': 'Attempted Update', 'description': 'Updated'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('bookmark-manager-user', kwargs={'username': self.owner.username}),
        )
        self.bookmark.refresh_from_db()
        self.assertNotEqual(self.bookmark.title, 'Attempted Update')

    def test_editing_orphaned_bookmark_get_redirects(self):
        """GET must also redirect, not render an edit form for a dead reference."""
        self.patient.delete()

        self.client.force_login(self.owner)
        response = self.client.get(self._edit_url())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('bookmark-manager-user', kwargs={'username': self.owner.username}),
        )

    def test_editing_orphaned_video_bookmark_does_not_500(self):
        """Same orphan check for a Video-type bookmark — the type whose model_mapping was wrong."""
        video = Video.objects.create(
            patient=self.patient,
            title='Orphan Test Video',
            recorded_on=timezone.now(),
            added_by=self.owner,
        )
        video_bookmark = Bookmark.objects.create(
            title='Video Bookmark',
            bookmark_type='Video',
            object_id=video.pk,
            owner=self.owner,
            added_by=self.owner,
        )
        video.delete()

        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('bookmark-edit', kwargs={'pk': video_bookmark.pk}),
            {'title': 'Attempted Update', 'description': 'Updated'},
        )
        self.assertEqual(response.status_code, 302)
        video_bookmark.refresh_from_db()
        self.assertNotEqual(video_bookmark.title, 'Attempted Update')
