"""
Tests for Story 2.1 — Institution Selector Screen.

Covers:
- Access control: only SUPERADMIN sees the selector
- Content: institution cards with metrics
- Session: active_institution_id is cleared on selector load
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()


def make_superadmin(username='superadmin'):
    return User.objects.create_user(
        username=username,
        password='testpass123',
        email=f'{username}@test.com',
        first_name='Super',
        position='Medical Officer',
        mobile_primary='0771234567',
        user_type=UserType.SUPERADMIN,
        is_superuser=True,
        is_staff=True,
    )


def make_admin(username='admin', institution=None):
    return User.objects.create_user(
        username=username,
        password='testpass123',
        email=f'{username}@test.com',
        first_name='Admin',
        position='Medical Officer',
        mobile_primary='0771234568',
        user_type=UserType.ADMIN,
        institution=institution,
    )


def make_institution(name='Test Hospital', slug='test-hospital'):
    return Institution.objects.create(name=name, slug=slug)


STATIC_OVERRIDE = override_settings(
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
)


@STATIC_OVERRIDE
class SelectorAccessTest(TestCase):
    """FR50: Only SUPERADMIN can access the institution selector."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('institution:institution-selector')
        self.superadmin = make_superadmin()
        self.institution = make_institution()
        self.admin = make_admin(institution=self.institution)

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f'/users/login/?next={self.url}', fetch_redirect_response=False)

    def test_superadmin_gets_200(self):
        self.client.login(username='superadmin', password='testpass123')
        # Bypass middleware by setting institution on session
        session = self.client.session
        session['active_institution_id'] = None
        session.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_non_superadmin_is_redirected(self):
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302,
            "ADMIN user must be redirected away from the institution selector (AC #3)")

    def test_selector_clears_active_institution_session(self):
        self.client.login(username='superadmin', password='testpass123')
        session = self.client.session
        session['active_institution_id'] = self.institution.pk
        session.save()
        self.client.get(self.url)
        session = self.client.session
        self.assertNotIn('active_institution_id', session)


@STATIC_OVERRIDE
class SelectorContentTest(TestCase):
    """Institution cards display correct aggregate data."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('institution:institution-selector')
        self.superadmin = make_superadmin()
        self.inst_a = make_institution('Hospital A', 'hospital-a')
        self.inst_b = make_institution('Hospital B', 'hospital-b')
        self.client.login(username='superadmin', password='testpass123')

    def test_selector_lists_all_institutions(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('institutions', response.context)
        institution_names = [i.name for i in response.context['institutions']]
        self.assertIn('Hospital A', institution_names)
        self.assertIn('Hospital B', institution_names)

    def test_selector_uses_correct_template(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'institution/selector.html')

    def test_institutions_have_annotated_counts(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for inst in response.context['institutions']:
            self.assertTrue(hasattr(inst, 'patient_count'))
            self.assertTrue(hasattr(inst, 'user_count'))


@STATIC_OVERRIDE
class SelectorSubscriptionBadgeTest(TestCase):
    """AC #2: EXPIRED institution card is visually distinct from ACTIVE/GRACE."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('institution:institution-selector')
        self.superadmin = make_superadmin()
        self.client.login(username='superadmin', password='testpass123')

    def test_active_institution_shows_badge_success(self):
        """AC #1: ACTIVE institution renders badge-success."""
        make_institution('Active Hosp', 'active-hosp')
        # patch subscription_status directly — make_institution uses default (ACTIVE)
        from institution.models import Institution
        Institution.objects.filter(slug='active-hosp').update(subscription_status='ACTIVE')
        response = self.client.get(self.url)
        self.assertContains(response, 'badge-success')

    def test_expired_institution_shows_badge_danger(self):
        """AC #2: EXPIRED institution card renders badge-danger — visually distinct."""
        from institution.models import Institution
        expired = Institution.objects.create(
            name='Expired Hosp', slug='expired-hosp', subscription_status='EXPIRED'
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # Both institution name and badge-danger must appear together on the page
        self.assertIn('Expired Hosp', content,
            "Expired institution must appear on selector")
        self.assertIn('badge-danger', content,
            "EXPIRED institution must show badge-danger (AC #2)")

    def test_grace_institution_shows_badge_warning(self):
        """AC #1: GRACE institution renders badge-warning."""
        from institution.models import Institution
        Institution.objects.create(
            name='Grace Hosp', slug='grace-hosp', subscription_status='GRACE'
        )
        response = self.client.get(self.url)
        self.assertContains(response, 'badge-warning')
