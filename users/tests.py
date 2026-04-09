"""
CRUD operation tests for the users app.

Covers: User view (detail), user edit, admin user add/edit/delete.
"""

import json
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

STATIC_OVERRIDE = override_settings(
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared setUp base
# ---------------------------------------------------------------------------

class UserTestBase(TestCase):
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
        self.regular_user = User.objects.create_user(
            username='regular',
            password=self.PASSWORD,
            email='regular@test.com',
        )


# ---------------------------------------------------------------------------
# 1. User Detail View
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class UserDetailViewTest(UserTestBase):
    """Test user detail (view) operation."""

    def test_view_own_profile_returns_200(self):
        self.client.force_login(self.staff_user)
        url = reverse('user-view', kwargs={'pk': self.staff_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view_other_user_profile_returns_200(self):
        self.client.force_login(self.staff_user)
        url = reverse('user-view', kwargs={'pk': self.regular_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view_nonexistent_user_returns_404(self):
        self.client.force_login(self.staff_user)
        url = reverse('user-view', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_view_by_username_returns_200(self):
        self.client.force_login(self.staff_user)
        url = reverse('user-view-by-username', kwargs={'username': self.regular_user.username})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view_redirects_unauthenticated(self):
        url = reverse('user-view', kwargs={'pk': self.staff_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


# ---------------------------------------------------------------------------
# 2. User Edit View
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class UserEditViewTest(UserTestBase):
    """Test user edit operation."""

    def test_edit_own_profile_get_returns_200(self):
        self.client.force_login(self.staff_user)
        url = reverse('user-edit', kwargs={'pk': self.staff_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_staff_can_edit_other_user(self):
        """Staff users can edit any user profile."""
        self.client.force_login(self.staff_user)
        url = reverse('user-edit', kwargs={'pk': self.regular_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_regular_user_cannot_edit_other_user(self):
        """Regular users cannot edit another user's profile."""
        self.client.force_login(self.regular_user)
        url = reverse('user-edit', kwargs={'pk': self.staff_user.pk})
        response = self.client.get(url)
        # userEdit always redirects (never 403)
        self.assertEqual(response.status_code, 302)

    def test_edit_redirects_unauthenticated(self):
        url = reverse('user-edit', kwargs={'pk': self.staff_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


# ---------------------------------------------------------------------------
# 3. Admin User Management (Add, Edit, Delete)
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class AdminUserManagementTest(UserTestBase):
    """Test admin user management CRUD (superuser only)."""

    def test_admin_user_list_returns_200_for_superuser(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('admin-user-list'))
        self.assertEqual(response.status_code, 200)

    def test_admin_user_list_denied_for_non_admin(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse('admin-user-list'))
        self.assertEqual(response.status_code, 302)

    def test_admin_user_add_get_returns_200(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('admin-user-add'))
        self.assertEqual(response.status_code, 200)

    def test_admin_user_edit_get_returns_200(self):
        self.client.force_login(self.superuser)
        url = reverse('admin-user-edit', kwargs={'pk': self.regular_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_admin_user_delete_deactivates_user(self):
        """admin_user_delete is a soft delete — sets is_active=False."""
        self.client.force_login(self.superuser)
        target = User.objects.create_user(
            username='to_delete',
            password='TempPass123!',
            email='delete@test.com',
        )
        url = reverse('admin-user-delete', kwargs={'pk': target.pk})
        # admin_user_delete requires DELETE method with JSON password payload
        response = self.client.delete(
            url,
            data=json.dumps({'password': self.PASSWORD}),
            content_type='application/json',
        )
        data = json.loads(response.content)
        self.assertTrue(data.get('success'), msg=data)
        target.refresh_from_db()
        self.assertFalse(target.is_active)

    def test_admin_user_edit_redirects_unauthenticated(self):
        url = reverse('admin-user-edit', kwargs={'pk': self.regular_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_admin_user_delete_redirects_unauthenticated(self):
        url = reverse('admin-user-delete', kwargs={'pk': self.regular_user.pk})
        response = self.client.delete(
            url,
            data=json.dumps({'password': self.PASSWORD}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_admin_user_delete_nonexistent_returns_404(self):
        # get_object_or_404 raises Http404 which is now explicitly caught
        # inside admin_user_delete and returned as 404 JSON.
        self.client.force_login(self.superuser)
        url = reverse('admin-user-delete', kwargs={'pk': 99999})
        response = self.client.delete(
            url,
            data=json.dumps({'password': self.PASSWORD}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertFalse(data.get('success'))
        self.assertEqual(data.get('error'), 'Not found')
