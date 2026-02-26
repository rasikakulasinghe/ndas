"""
institution/tests/test_feature_flag.py

Feature flag behaviour validation.
Tests InstitutionContextMiddleware with both flag states.
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()

_NO_STATIC = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


class FeatureFlagMiddlewareTest(TestCase):
    """Verify flag-gated middleware behaviour."""

    def setUp(self):
        self.institution = Institution.objects.create(
            name='Test Hospital',
            slug='test-hospital',
            subscription_status=SubscriptionStatus.ACTIVE,
            is_active=True,
        )
        self.user = User.objects.create_user(
            username='testclinician_ff',
            password='Testpass1!',
            first_name='Test',
            last_name='User',
            position='Medical Officer',
            mobile_primary='0771110099',
            user_type=UserType.USER,
            institution=self.institution,
        )
        self.client = Client()
        self.client.force_login(self.user)

    @override_settings(
        MULTI_INSTITUTION_ENABLED=True,
        STORAGES=_NO_STATIC,
        RATELIMIT_ENABLE=False,
    )
    def test_flag_true_middleware_runs_cleanly(self):
        """With flag True, middleware runs and a page loads without 500."""
        response = self.client.get(reverse('manage-patients'))
        self.assertIn(response.status_code, [200, 302])
        self.assertNotEqual(response.status_code, 500)

    @override_settings(
        MULTI_INSTITUTION_ENABLED=False,
        STORAGES=_NO_STATIC,
        RATELIMIT_ENABLE=False,
    )
    def test_flag_false_middleware_does_not_crash(self):
        """With flag False, the system behaves as pre-Phase-2 — page loads normally."""
        response = self.client.get(reverse('manage-patients'), follow=True)
        self.assertIn(response.status_code, [200, 302],
            f"Expected 200 or 302 with flag off; got {response.status_code}")

    @override_settings(
        MULTI_INSTITUTION_ENABLED=True,
        STORAGES=_NO_STATIC,
        RATELIMIT_ENABLE=False,
    )
    def test_superadmin_without_session_context_redirected_to_selector(self):
        """SUPERADMIN with no active_institution_id in session → redirect to institution selector."""
        superadmin = User.objects.create_user(
            username='superadmin_test_ff',
            password='Testpass1!',
            first_name='Super',
            last_name='Admin',
            position='Administrator',
            mobile_primary='0771110098',
            user_type=UserType.SUPERADMIN,
            is_superuser=True,
        )
        sa_client = Client()
        sa_client.force_login(superadmin)
        # No session['active_institution_id'] set → should redirect to institution selector
        response = sa_client.get(reverse('manage-patients'))
        self.assertEqual(response.status_code, 302,
            "SUPERADMIN without institution context should be redirected to institution selector")
        self.assertIn('institution', response['Location'],
            "Redirect should go to the institution selector screen")

    @override_settings(
        MULTI_INSTITUTION_ENABLED=True,
        STORAGES=_NO_STATIC,
        RATELIMIT_ENABLE=False,
    )
    def test_superadmin_with_session_context_accesses_patient_list(self):
        """SUPERADMIN with active_institution_id in session → patient list loads."""
        superadmin = User.objects.create_user(
            username='superadmin_test_ff2',
            password='Testpass1!',
            first_name='Super',
            last_name='Admin',
            position='Administrator',
            mobile_primary='0771110097',
            user_type=UserType.SUPERADMIN,
            is_superuser=True,
        )
        sa_client = Client()
        sa_client.force_login(superadmin)
        # Set active institution in session
        session = sa_client.session
        session['active_institution_id'] = self.institution.pk
        session.save()
        response = sa_client.get(reverse('manage-patients'))
        # Should load (200) or redirect for some other reason, but NOT to institution-selector
        self.assertIn(response.status_code, [200, 302],
            f"Expected 200 or 302 for SUPERADMIN with session context; got {response.status_code}")
        if response.status_code == 302:
            self.assertNotIn('institution/selector', response.get('Location', ''),
                "SUPERADMIN with session context should NOT be redirected to institution selector")
