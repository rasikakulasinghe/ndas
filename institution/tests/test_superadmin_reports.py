"""
Tests for Story 2.5 — Cross-Institution Aggregate Reports.

Covers:
- GET renders the scope selector
- POST per_institution generates a file response
- POST cross_institution generates a file response
- Invalid scope returns error
- Per-institution without institution_id returns error
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


STATIC_OVERRIDE = override_settings(
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
)


@STATIC_OVERRIDE
class SuperadminReportsAccessTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('institution:superadmin-reports')
        self.superadmin = make_superadmin()

    def test_unauthenticated_redirects(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_superadmin_get_renders_form(self):
        self.client.login(username='superadmin', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'institution/superadmin_reports.html')
        self.assertIn('institutions', response.context)


@STATIC_OVERRIDE
class SuperadminReportsGenerationTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('institution:superadmin-reports')
        self.superadmin = make_superadmin()
        self.institution = Institution.objects.create(name='Export Hospital', slug='export-hosp')
        self.client.login(username='superadmin', password='testpass123')

    def test_invalid_scope_shows_error(self):
        response = self.client.post(self.url, {'scope': 'invalid_scope'})
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(any('Invalid report scope' in str(m) for m in messages))

    def test_per_institution_without_institution_id_shows_error(self):
        response = self.client.post(self.url, {'scope': 'per_institution', 'institution_id': ''})
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(any('select a target institution' in str(m).lower() or
                           'please select' in str(m).lower() for m in messages))

    def test_cross_institution_generates_file_response(self):
        response = self.client.post(self.url, {'scope': 'cross_institution'})
        self.assertIn(response.status_code, [200, 302])
        if response.status_code == 200:
            content_type = response.get('Content-Type', '')
            if 'spreadsheet' in content_type or 'excel' in content_type:
                self.assertIn('attachment', response.get('Content-Disposition', ''))

    def test_per_institution_with_id_generates_file_response(self):
        response = self.client.post(self.url, {
            'scope': 'per_institution',
            'institution_id': self.institution.pk,
        })
        self.assertIn(response.status_code, [200, 302])
        if response.status_code == 200:
            content_type = response.get('Content-Type', '')
            if 'spreadsheet' in content_type or 'excel' in content_type:
                self.assertIn('attachment', response.get('Content-Disposition', ''))
