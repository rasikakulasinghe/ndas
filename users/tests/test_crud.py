"""
CRUD operation tests for the users app.

Covers: User view (detail), user edit, admin user add/edit/delete.

Lives under users/tests/ (not a top-level users/tests.py) because a
top-level tests.py collides with this tests/ package and breaks
`manage.py test` discovery for the whole project. Do not reintroduce
a top-level users/tests.py.
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


@STATIC_OVERRIDE
class AdminUserListInstitutionFilterTest(UserTestBase):
    """admin_user_list's institution filter/column is superuser-only."""

    def setUp(self):
        super().setUp()
        from institution.models import Institution
        self.inst_a = Institution.objects.create(name='Inst Alpha', slug='inst-alpha')
        self.inst_b = Institution.objects.create(name='Inst Beta', slug='inst-beta')
        self.user_a = User.objects.create_user(
            username='user_a', password=self.PASSWORD, email='user_a@test.com',
            institution=self.inst_a,
        )
        self.user_b = User.objects.create_user(
            username='user_b', password=self.PASSWORD, email='user_b@test.com',
            institution=self.inst_b,
        )

    def test_superuser_can_filter_by_institution(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('admin-user-list'), {'institution': self.inst_a.pk})
        self.assertEqual(response.status_code, 200)
        page_users = list(response.context['page_obj'])
        self.assertIn(self.user_a, page_users)
        self.assertNotIn(self.user_b, page_users)

    def test_superuser_no_filter_sees_all_institutions(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('admin-user-list'))
        page_users = list(response.context['page_obj'])
        self.assertIn(self.user_a, page_users)
        self.assertIn(self.user_b, page_users)
        self.assertContains(response, 'Institution')

    def test_institution_filter_field_hidden_for_non_superuser_staff(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('admin-user-list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('institution', response.context['form'].fields)

    def test_institution_query_param_ignored_for_non_superuser_staff(self):
        # staff_user has no institution assigned, so admin_user_list scopes
        # them to CustomUser.objects.none(); passing ?institution must not
        # error and must not leak cross-institution users.
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('admin-user-list'), {'institution': self.inst_a.pk})
        self.assertEqual(response.status_code, 200)
        page_users = list(response.context['page_obj'])
        self.assertNotIn(self.user_a, page_users)
        self.assertNotIn(self.user_b, page_users)


# ---------------------------------------------------------------------------
# 4. Admin User Add/Edit — institution field, scoped by role
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class AdminUserAddEditInstitutionScopingTest(UserTestBase):
    """
    Institution field on admin_user_add/admin_user_edit is superuser-only
    (mirrors UserSearchForm/admin_user_list): non-superuser staff admins
    never see or control it, and the view force-assigns their own
    institution on create.
    """

    def setUp(self):
        super().setUp()
        from django.conf import settings
        from institution.models import Institution

        self.Institution = Institution
        # The default institution is seeded by a data migration
        # (institution.0002_default_institution_data) at DEFAULT_INSTITUTION_SLUG
        # — fetch it rather than creating a duplicate (unique slug).
        self.default_institution, _ = Institution.objects.get_or_create(
            slug=settings.DEFAULT_INSTITUTION_SLUG,
            defaults={'name': 'Default Institution'},
        )
        self.other_institution = Institution.objects.create(
            name='Other Institution',
            slug='other-institution',
        )

        # Non-superuser staff admin scoped to the default institution.
        self.staff_admin = User.objects.create_user(
            username='staff_admin',
            password=self.PASSWORD,
            email='staff_admin@test.com',
            is_staff=True,
            institution=self.default_institution,
            mobile_primary='0771234561',
        )

    def _valid_add_post_data(self, **overrides):
        data = {
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@test.com',
            'position': 'Medical Officer',
            'mobile_primary': '0771234567',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'is_active': 'on',
        }
        data.update(overrides)
        return data

    def _valid_edit_post_data(self, user, **overrides):
        data = {
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'position': 'Medical Officer',
            'mobile_primary': user.mobile_primary or '0771234562',
            'is_active': 'on',
        }
        data.update(overrides)
        return data

    # --- Superuser: Add ---

    def test_superuser_get_add_form_initial_is_default_institution(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('admin-user-add'))
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('institution', form.fields)
        self.assertEqual(form.fields['institution'].initial, self.default_institution)

    def test_superuser_add_form_lists_only_active_institutions(self):
        inactive = self.Institution.objects.create(
            name='Inactive Institution', slug='inactive-institution', is_active=False
        )
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('admin-user-add'))
        qs = response.context['form'].fields['institution'].queryset
        self.assertIn(self.default_institution, qs)
        self.assertIn(self.other_institution, qs)
        self.assertNotIn(inactive, qs)

    def test_superuser_add_sets_chosen_institution(self):
        self.client.force_login(self.superuser)
        data = self._valid_add_post_data(
            username='su_added', email='su_added@test.com',
            institution=self.other_institution.pk,
        )
        response = self.client.post(reverse('admin-user-add'), data)
        self.assertEqual(response.status_code, 302, msg=getattr(response, 'context', None))
        user = User.objects.get(username='su_added')
        self.assertEqual(user.institution, self.other_institution)

    def test_superuser_add_can_clear_institution(self):
        self.client.force_login(self.superuser)
        data = self._valid_add_post_data(
            username='su_added_none', email='su_added_none@test.com', institution='',
        )
        response = self.client.post(reverse('admin-user-add'), data)
        self.assertEqual(response.status_code, 302, msg=getattr(response, 'context', None))
        user = User.objects.get(username='su_added_none')
        self.assertIsNone(user.institution)

    # --- Non-superuser staff admin: Add ---

    def test_staff_admin_add_form_has_no_institution_field(self):
        self.client.force_login(self.staff_admin)
        response = self.client.get(reverse('admin-user-add'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('institution', response.context['form'].fields)

    @override_settings(MULTI_INSTITUTION_ENABLED=True)
    def test_staff_admin_add_forces_own_institution(self):
        self.client.force_login(self.staff_admin)
        data = self._valid_add_post_data(username='staff_added', email='staff_added@test.com')
        response = self.client.post(reverse('admin-user-add'), data)
        self.assertEqual(response.status_code, 302, msg=getattr(response, 'context', None))
        user = User.objects.get(username='staff_added')
        self.assertEqual(user.institution, self.default_institution)

    def test_staff_admin_add_ignores_forged_institution(self):
        self.client.force_login(self.staff_admin)
        data = self._valid_add_post_data(
            username='staff_added_forged', email='staff_added_forged@test.com',
            institution=self.other_institution.pk,
        )
        response = self.client.post(reverse('admin-user-add'), data)
        self.assertEqual(response.status_code, 302, msg=getattr(response, 'context', None))
        user = User.objects.get(username='staff_added_forged')
        self.assertEqual(user.institution, self.default_institution)

    @override_settings(MULTI_INSTITUTION_ENABLED=True)
    def test_staff_admin_with_no_institution_blocked_under_phase2(self):
        # UserTestBase.staff_user has no institution assigned.
        self.client.force_login(self.staff_user)
        data = self._valid_add_post_data(username='blocked_user', email='blocked_user@test.com')
        response = self.client.post(reverse('admin-user-add'), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='blocked_user').exists())
        msgs = [str(m) for m in response.context['messages']]
        self.assertTrue(any('institution' in m.lower() for m in msgs), msg=msgs)

    @override_settings(MULTI_INSTITUTION_ENABLED=False)
    def test_staff_admin_add_under_phase1_creates_with_none_institution(self):
        # UserTestBase.staff_user has no institution assigned; under Phase 1
        # request.institution is never resolved for anyone, so this must not
        # be blocked and must match pre-spec behavior (institution=None).
        self.client.force_login(self.staff_user)
        data = self._valid_add_post_data(username='phase1_user', email='phase1_user@test.com')
        response = self.client.post(reverse('admin-user-add'), data)
        self.assertEqual(response.status_code, 302, msg=getattr(response, 'context', None))
        user = User.objects.get(username='phase1_user')
        self.assertIsNone(user.institution)

    # --- Superuser: Edit ---

    def test_superuser_edit_updates_institution(self):
        target = User.objects.create_user(
            username='edit_target', password=self.PASSWORD, email='edit_target@test.com',
            institution=self.default_institution, mobile_primary='0771234562',
        )
        self.client.force_login(self.superuser)
        url = reverse('admin-user-edit', kwargs={'pk': target.pk})
        data = self._valid_edit_post_data(target, institution=self.other_institution.pk)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302, msg=getattr(response, 'context', None))
        target.refresh_from_db()
        self.assertEqual(target.institution, self.other_institution)

    def test_edit_form_includes_and_preselects_deactivated_current_institution(self):
        deactivated = self.Institution.objects.create(
            name='Deactivated Institution', slug='deactivated-institution', is_active=False,
        )
        target = User.objects.create_user(
            username='deact_target', password=self.PASSWORD, email='deact_target@test.com',
            institution=deactivated, mobile_primary='0771234563',
        )
        self.client.force_login(self.superuser)
        url = reverse('admin-user-edit', kwargs={'pk': target.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn(deactivated, form.fields['institution'].queryset)
        self.assertEqual(form.initial.get('institution'), deactivated.pk)

    def test_edit_post_without_changing_institution_preserves_deactivated(self):
        """A full submit that re-sends the pre-selected (deactivated)
        institution — simulating a browser posting an untouched <select> —
        must not fall back to the alphabetically-first active institution."""
        deactivated = self.Institution.objects.create(
            name='Deactivated Institution 2', slug='deactivated-institution-2', is_active=False,
        )
        target = User.objects.create_user(
            username='deact_target2', password=self.PASSWORD, email='deact_target2@test.com',
            institution=deactivated, mobile_primary='0771234566',
        )
        self.client.force_login(self.superuser)
        url = reverse('admin-user-edit', kwargs={'pk': target.pk})
        data = self._valid_edit_post_data(
            target, first_name='Changed', institution=deactivated.pk,
        )
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302, msg=getattr(response, 'context', None))
        target.refresh_from_db()
        self.assertEqual(target.institution, deactivated)
        self.assertEqual(target.first_name, 'Changed')

    def test_superuser_edit_can_clear_active_institution(self):
        target = User.objects.create_user(
            username='clear_target', password=self.PASSWORD, email='clear_target@test.com',
            institution=self.default_institution, mobile_primary='0771234567',
        )
        self.client.force_login(self.superuser)
        url = reverse('admin-user-edit', kwargs={'pk': target.pk})
        data = self._valid_edit_post_data(target, institution='')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302, msg=getattr(response, 'context', None))
        target.refresh_from_db()
        self.assertIsNone(target.institution)

    # --- Non-superuser staff admin: Edit ---

    def test_staff_admin_edit_form_has_no_institution_field(self):
        target = User.objects.create_user(
            username='edit_target2', password=self.PASSWORD, email='edit_target2@test.com',
            institution=self.default_institution, mobile_primary='0771234564',
        )
        self.client.force_login(self.staff_admin)
        url = reverse('admin-user-edit', kwargs={'pk': target.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('institution', response.context['form'].fields)

    def test_staff_admin_edit_institution_unchanged_even_with_forged_field(self):
        target = User.objects.create_user(
            username='edit_target3', password=self.PASSWORD, email='edit_target3@test.com',
            institution=self.default_institution, mobile_primary='0771234565',
        )
        self.client.force_login(self.staff_admin)
        url = reverse('admin-user-edit', kwargs={'pk': target.pk})
        data = self._valid_edit_post_data(target, institution=self.other_institution.pk)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302, msg=getattr(response, 'context', None))
        target.refresh_from_db()
        self.assertEqual(target.institution, self.default_institution)
