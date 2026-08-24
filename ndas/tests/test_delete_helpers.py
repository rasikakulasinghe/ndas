"""
ndas/tests/test_delete_helpers.py

Regression tests for the has_delete_permission() Bookmark ownership fix.
Part of spec-fix-auth-permission-bypasses.

Previously, ANY staff user could delete ANY Bookmark regardless of ownership.
The fix scopes staff deletion of bookmarks to entity.owner == user, matching
the documented "staff delete own records" rule.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from ndas.custom_codes.delete_helpers import has_delete_permission
from patients.models import Bookmark

User = get_user_model()


class HasDeletePermissionBookmarkTest(TestCase):
    def setUp(self):
        self.owner_staff = User.objects.create_user(
            username='dh_owner',
            password='Testpass1!',
            email='dh_owner@example.com',
            is_staff=True,
        )
        self.other_staff = User.objects.create_user(
            username='dh_other',
            password='Testpass1!',
            email='dh_other@example.com',
            is_staff=True,
        )
        self.superuser = User.objects.create_user(
            username='dh_super',
            password='Testpass1!',
            email='dh_super@example.com',
            is_staff=True,
            is_superuser=True,
        )
        self.bookmark = Bookmark.objects.create(
            title='Test Bookmark',
            bookmark_type='Video',
            object_id=1,
            owner=self.owner_staff,
            added_by=self.owner_staff,
        )
        # added_by != owner (e.g. an admin created it on another user's behalf) —
        # regression case for the generic added_by branch leaking Bookmark
        # delete rights when it ran before the owner-specific check.
        self.bookmark_added_by_other = Bookmark.objects.create(
            title='Added By Other',
            bookmark_type='Video',
            object_id=2,
            owner=self.owner_staff,
            added_by=self.other_staff,
        )

    def test_staff_deletes_own_bookmark_succeeds(self):
        """Given a staff user who owns the bookmark, expect permission granted."""
        self.assertTrue(has_delete_permission(self.owner_staff, self.bookmark))

    def test_staff_deletes_others_bookmark_fails(self):
        """Given a staff user who does NOT own the bookmark, expect permission denied (the fix)."""
        self.assertFalse(has_delete_permission(self.other_staff, self.bookmark))

    def test_superuser_deletes_any_bookmark_succeeds(self):
        """Given a superuser, expect permission granted regardless of ownership (unchanged)."""
        self.assertTrue(has_delete_permission(self.superuser, self.bookmark))

    def test_staff_added_by_but_not_owner_cannot_delete(self):
        """
        Regression: a staff user who is added_by on a bookmark they don't own
        must be denied — the owner check must run before (not after) the
        generic added_by branch, or this would incorrectly return True.
        """
        self.assertFalse(has_delete_permission(self.other_staff, self.bookmark_added_by_other))

    def test_owner_can_delete_even_when_added_by_someone_else(self):
        """The true owner can always delete, regardless of who added_by is."""
        self.assertTrue(has_delete_permission(self.owner_staff, self.bookmark_added_by_other))
