"""
Regression tests for the 2026-11-16 QA bug report fix batch
(see `_bmad-output/implementation-artifacts/spec-qa-bug-report-fixes.md`).

Covers: H1 (superuser/user_type sync — model save() + migration backfill),
H2 (admin_required accepts Phase 2 ADMIN/SUPERADMIN + admin_dashboard
institution scoping), M2 (AdminUserCreationForm password policy).

Lives under users/tests/ (not a top-level users/tests.py) because a
top-level tests.py collides with this tests/ package and breaks
`manage.py test` discovery for the whole project.
"""

import importlib

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from institution.models import Institution
from ndas.custom_codes.choice import UserType
from users.forms import AdminUserCreationForm

User = get_user_model()

STATIC_OVERRIDE = override_settings(
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
)


# ---------------------------------------------------------------------------
# H1 — CustomUser.save() syncs user_type to SUPERADMIN for every superuser
# ---------------------------------------------------------------------------

class SuperuserUserTypeSyncTest(TestCase):
    def test_create_superuser_defaults_to_superadmin_user_type(self):
        user = User.objects.create_superuser(
            username='newsuper', password='Pass123456!', email='newsuper@test.com',
            position='Medical Officer', mobile_primary='0771111111',
        )
        self.assertEqual(user.user_type, UserType.SUPERADMIN)

    def test_promoting_a_user_to_superuser_syncs_user_type_on_save(self):
        user = User.objects.create_user(
            username='latersuper', password='Pass123456!', email='latersuper@test.com',
        )
        self.assertEqual(user.user_type, UserType.USER)

        user.is_superuser = True
        user.save()

        user.refresh_from_db()
        self.assertEqual(user.user_type, UserType.SUPERADMIN)

    def test_migration_0011_backfills_existing_superuser_rows(self):
        """Simulates a superuser row created before the save() override existed
        (migration 0009's one-time backfill already ran, but this row was
        created via `createsuperuser` afterwards) — exactly what migration
        0011 backfills for accounts that predate this fix."""
        user = User.objects.create_user(
            username='legacysuper', password='Pass123456!', email='legacysuper@test.com',
            is_superuser=True,
        )
        # Bypass CustomUser.save()'s auto-sync via a bulk update, to reproduce
        # a pre-existing row the new save() override never touched.
        User.objects.filter(pk=user.pk).update(user_type=UserType.USER)
        user.refresh_from_db()
        self.assertEqual(user.user_type, UserType.USER)

        migration = importlib.import_module('users.migrations.0011_sync_superuser_user_type')
        migration.sync_superuser_user_type(django_apps, None)

        user.refresh_from_db()
        self.assertEqual(user.user_type, UserType.SUPERADMIN)


# ---------------------------------------------------------------------------
# H2 — admin_required accepts Phase 2 user_type, admin_dashboard is scoped
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class AdminRequiredPhase2AccessTest(TestCase):
    def test_institution_admin_can_reach_admin_dashboard(self):
        """A user_type=ADMIN account with no is_staff/is_superuser flags
        (the sidebar already shows them the link) must not be redirected
        away by admin_required."""
        inst = Institution.objects.create(name='Inst QA1', slug='inst-qa1')
        admin = User.objects.create_user(
            username='inst_admin_qa1', password='Pass123456!', email='inst_admin_qa1@test.com',
            user_type=UserType.ADMIN, institution=inst,
            position='Medical Officer', mobile_primary='0772222222',
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('admin-dashboard'))

        self.assertEqual(response.status_code, 200)

    def test_plain_user_is_still_blocked_from_admin_dashboard(self):
        """Opening admin_required to Phase 2 ADMIN/SUPERADMIN must not also
        open it to a plain USER."""
        plain = User.objects.create_user(
            username='plain_qa1', password='Pass123456!', email='plain_qa1@test.com',
        )
        self.client.force_login(plain)

        response = self.client.get(reverse('admin-dashboard'))

        self.assertEqual(response.status_code, 302)

    def test_admin_dashboard_scopes_total_users_to_own_institution(self):
        """Regression guard: opening admin_dashboard to non-staff Institution
        Admins must not leak other institutions' user counts."""
        inst_a = Institution.objects.create(name='Inst QA2', slug='inst-qa2')
        inst_b = Institution.objects.create(name='Inst QA3', slug='inst-qa3')
        admin_a = User.objects.create_user(
            username='admin_qa2', password='Pass123456!', email='admin_qa2@test.com',
            user_type=UserType.ADMIN, institution=inst_a,
            position='Medical Officer', mobile_primary='0773333333',
        )
        User.objects.create_user(
            username='other_inst_user_qa3', password='Pass123456!', email='other_inst_qa3@test.com',
            institution=inst_b, position='Medical Officer', mobile_primary='0774444444',
        )
        self.client.force_login(admin_a)

        response = self.client.get(reverse('admin-dashboard'))

        self.assertEqual(response.status_code, 200)
        # Only admin_a themself belongs to inst_a; inst_b's user must not be counted.
        self.assertEqual(response.context['total_users'], 1)


# ---------------------------------------------------------------------------
# M2 — AdminUserCreationForm enforces the project's real password policy
# ---------------------------------------------------------------------------

class AdminUserCreationFormPasswordPolicyTest(TestCase):
    def _form_data(self, **overrides):
        data = {
            'username': 'pwpolicyuser',
            'first_name': 'Pw', 'last_name': 'Policy',
            'email': 'pwpolicy@test.com',
            'position': 'Medical Officer',
            'mobile_primary': '0775555555',
            'is_active': 'on',
        }
        data.update(overrides)
        return data

    def test_rejects_password_shorter_than_12_characters(self):
        """Matches /institution/clinicians/add/'s policy (M2) instead of the
        old hardcoded 8-character check."""
        form = AdminUserCreationForm(data=self._form_data(
            password1='Xk7!qLm9zRt',  # 11 chars
            password2='Xk7!qLm9zRt',
        ))

        self.assertFalse(form.is_valid())
        self.assertIn('password1', form.errors)
        self.assertTrue(
            any('12 characters' in msg for msg in form.errors['password1']),
            msg=form.errors['password1'],
        )

    def test_accepts_password_meeting_the_12_character_policy(self):
        form = AdminUserCreationForm(data=self._form_data(
            password1='Xk7!qLm9zRtW',  # 12 chars
            password2='Xk7!qLm9zRtW',
        ))

        self.assertTrue(form.is_valid(), msg=form.errors)
