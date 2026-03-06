"""
institution/tests/test_sidebar_access.py
Tests for sidebar menu access control based on user role and institution context.

Key middleware behaviour (institution/middleware.py):
- SUPERADMIN without session['active_institution_id'] → redirected to institution-selector
- SUPERADMIN with session['active_institution_id'] set → institution resolved, no redirect
- URLs under /institution/ are EXEMPT from the redirect — always render
- Session key: 'active_institution_id' (integer PK of Institution)
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


@STATIC_OVERRIDE
class SidebarAccessControlTest(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_sidebar', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771991001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(
            name='Test Hospital', slug='test-hospital-sb',
            subscription_status=SubscriptionStatus.ACTIVE,
            is_active=True, created_by=self.superadmin,
        )
        self.admin_user = User.objects.create_user(
            username='admin_sidebar', password='Testpass1!',
            first_name='Test', last_name='Admin',
            position='Administrator', mobile_primary='0771991002',
            user_type=UserType.ADMIN, institution=self.inst,
        )
        self.regular_user = User.objects.create_user(
            username='user_sidebar', password='Testpass1!',
            first_name='Test', last_name='User',
            position='Medical Officer', mobile_primary='0771991003',
            user_type=UserType.USER, institution=self.inst,
        )
        # /institution/ URLs are EXEMPT from middleware redirect — use selector for SUPERADMIN
        # tests where no institution is in session (avoids 302 with empty body)
        self.exempt_url = reverse('institution:institution-selector')
        self.home_url = reverse('home')

    def test_patient_items_hidden_for_superadmin_without_institution(self):
        """AC 1: SUPERADMIN with no active institution sees no patient-level menu items.
        Uses institution-selector URL (EXEMPT from redirect) to get a rendered sidebar."""
        client = Client()
        client.force_login(self.superadmin)
        # Do NOT set session['active_institution_id'] — no institution context
        response = client.get(self.exempt_url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn(reverse('add-patient'), content)
        self.assertNotIn(reverse('search-start'), content)
        self.assertNotIn(reverse('manage-patients'), content)
        self.assertNotIn(reverse('problem-analysis'), content)
        self.assertNotIn(reverse('assessment-manager'), content)
        self.assertNotIn(reverse('video:manager'), content)

    def test_patient_items_visible_for_superadmin_with_institution(self):
        """AC 2: SUPERADMIN with active institution set in session sees patient menu items."""
        client = Client()
        client.force_login(self.superadmin)
        # Set institution context via the session key used by InstitutionContextMiddleware
        session = client.session
        session['active_institution_id'] = self.inst.pk
        session.save()
        response = client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(reverse('add-patient'), content)
        self.assertIn(reverse('search-start'), content)
        self.assertIn(reverse('manage-patients'), content)
        self.assertIn(reverse('problem-analysis'), content)
        self.assertIn(reverse('assessment-manager'), content)
        self.assertIn(reverse('video:manager'), content)

    def test_patient_items_visible_for_user(self):
        """AC 3: Regular USER always sees all patient-level menu items."""
        client = Client()
        client.force_login(self.regular_user)
        response = client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(reverse('add-patient'), content)
        self.assertIn(reverse('search-start'), content)
        self.assertIn(reverse('manage-patients'), content)

    def test_patient_items_visible_for_admin(self):
        """AC 4: ADMIN always sees all patient-level menu items."""
        client = Client()
        client.force_login(self.admin_user)
        response = client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(reverse('add-patient'), content)
        self.assertIn(reverse('manage-patients'), content)
