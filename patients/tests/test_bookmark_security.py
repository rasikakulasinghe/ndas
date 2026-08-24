"""
patients/tests/test_bookmark_security.py

Regression tests for the bookmark_manager_user IDOR fix.
Part of spec-fix-auth-permission-bypasses.

Ensures a user cannot view another user's private bookmark list, while
still allowing the owning user and superusers to view it.
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

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
