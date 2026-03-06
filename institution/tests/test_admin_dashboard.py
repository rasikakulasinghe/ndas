"""
institution/tests/test_admin_dashboard.py
Tests for Institution Admin Dashboard (Story 3.1 — FR42, FR56).
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()

STATIC_OVERRIDE = override_settings(
    MULTI_INSTITUTION_ENABLED=True,
    RATELIMIT_ENABLE=False,
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)


class AdminDashboardTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_dash', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771881001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(
            name='Test Hospital', slug='test-hospital',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.admin = User.objects.create_user(
            username='admin_dash', password='Testpass1!',
            first_name='Test', last_name='Admin',
            position='Administrator', mobile_primary='0771881002',
            user_type=UserType.ADMIN, institution=self.inst,
        )
        self.user = User.objects.create_user(
            username='user_dash', password='Testpass1!',
            first_name='Test', last_name='User',
            position='Medical Officer', mobile_primary='0771881003',
            user_type=UserType.USER, institution=self.inst,
        )
        self.url = reverse('institution:institution-admin-dashboard')


@STATIC_OVERRIDE
class AdminDashboardAccessTest(AdminDashboardTestBase):
    def test_admin_can_access_dashboard(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_user_redirected_to_home(self):
        client = Client()
        client.force_login(self.user)
        response = client.get(self.url)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_superadmin_redirected_to_superadmin_dashboard(self):
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.url)
        self.assertRedirects(
            response,
            reverse('institution:superadmin-dashboard'),
            fetch_redirect_response=False,
            msg_prefix="AC #4: SUPERADMIN must be redirected to the superadmin dashboard",
        )

    def test_unauthenticated_redirected_to_login(self):
        client = Client()
        response = client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_admin_dashboard_shows_institution_banner_card(self):
        """AC 7: Institution admin dashboard renders bg-info banner card with institution name."""
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.inst.name)
        self.assertContains(response, 'card bg-info mb-3')


@STATIC_OVERRIDE
class AdminDashboardEmptyStateTest(AdminDashboardTestBase):
    def test_empty_state_no_exceptions(self):
        """AC #3: Empty institution loads dashboard without errors."""
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_total_patients_zero(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        self.assertEqual(response.context['total_patients'], 0)

    def test_assessment_counts_zero(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        counts = response.context['assessment_counts']
        for key in ('gma', 'hine', 'cdic', 'gpa', 'da', 'total'):
            self.assertEqual(counts[key], 0, f"AC #3: {key} must be 0 for empty institution")

    def test_referral_stats_zero(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        stats = response.context['referral_stats']
        for key in ('sent', 'received', 'pending', 'closed'):
            self.assertEqual(stats[key], 0, f"AC #3: referral {key} must be 0 (stub)")

    def test_total_users_count(self):
        """AC #1: Team activity quadrant shows user count."""
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        # The admin user itself is in the institution, so at least 1
        self.assertGreaterEqual(response.context['total_users'], 1)

    def test_context_contains_institution(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        self.assertEqual(response.context['institution'], self.inst)
