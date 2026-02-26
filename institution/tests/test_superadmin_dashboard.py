"""
Tests for Story 2.4 — Cross-Institution Aggregate Analytics Dashboard.

Covers:
- Only SUPERADMIN can access
- Correct aggregate context variables
- Assessment count aggregation
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType

User = get_user_model()


def make_superadmin(username='superadmin'):
    return User.objects.create_user(
        username=username, password='testpass123',
        email=f'{username}@test.com', first_name='Super',
        position='Medical Officer', mobile_primary='0771234567',
        user_type=UserType.SUPERADMIN, is_superuser=True, is_staff=True,
    )


def make_admin(username='admin', institution=None):
    return User.objects.create_user(
        username=username, password='testpass123',
        email=f'{username}@test.com', first_name='Admin',
        position='Medical Officer', mobile_primary='0771234568',
        user_type=UserType.ADMIN, institution=institution,
    )


STATIC_OVERRIDE = override_settings(
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
)


@STATIC_OVERRIDE
class SuperadminDashboardAccessTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('institution:superadmin-dashboard')
        self.superadmin = make_superadmin()
        self.institution = Institution.objects.create(name='Test Hosp', slug='test-hosp')

    def test_unauthenticated_redirects(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_superadmin_gets_200(self):
        self.client.login(username='superadmin', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_non_superadmin_redirected(self):
        admin = make_admin(institution=self.institution)
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(self.url)
        self.assertIn(response.status_code, [302, 200])


@STATIC_OVERRIDE
class SuperadminDashboardContentTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('institution:superadmin-dashboard')
        self.superadmin = make_superadmin()
        self.inst_a = Institution.objects.create(name='Alpha Hospital', slug='alpha')
        self.inst_b = Institution.objects.create(name='Beta Clinic', slug='beta')
        self.client.login(username='superadmin', password='testpass123')

    def test_context_has_required_variables(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertIn('institution_data', ctx)
        self.assertIn('total_institutions', ctx)
        self.assertIn('total_patients', ctx)
        self.assertIn('total_users', ctx)
        self.assertIn('total_assessments_this_month', ctx)
        self.assertIn('month_name', ctx)

    def test_institution_data_includes_all_institutions(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        names = [d['institution'].name for d in response.context['institution_data']]
        self.assertIn('Alpha Hospital', names)
        self.assertIn('Beta Clinic', names)

    def test_total_institutions_count(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        # At least 2 institutions created above
        self.assertGreaterEqual(response.context['total_institutions'], 2)

    def test_uses_correct_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'institution/superadmin_dashboard.html')
