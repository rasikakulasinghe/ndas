"""
Tests for Story 2.2 — SUPERADMIN Institution Context Switching.

Covers:
- POST-only enforcement
- Session update on successful switch
- Invalid institution_id rejected
- Non-SUPERADMIN cannot switch
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
class ContextSwitchingTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.superadmin = make_superadmin()
        self.institution = Institution.objects.create(name='City Hospital', slug='city-hospital')
        self.switch_url = reverse('institution:institution-switch', args=[self.institution.pk])

    def test_get_not_allowed(self):
        """Context switch endpoint is POST-only."""
        self.client.login(username='superadmin', password='testpass123')
        response = self.client.get(self.switch_url)
        self.assertEqual(response.status_code, 405)

    def test_superadmin_switch_sets_session(self):
        """Successful switch stores institution ID in session."""
        self.client.login(username='superadmin', password='testpass123')
        response = self.client.post(self.switch_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get('active_institution_id'), self.institution.pk)

    def test_switch_redirects_to_patient_list(self):
        """After switch, redirects to manage-patients."""
        self.client.login(username='superadmin', password='testpass123')
        response = self.client.post(self.switch_url)
        self.assertRedirects(response, reverse('manage-patients'), fetch_redirect_response=False)

    def test_switch_to_inactive_institution_denied(self):
        """Inactive institution is not accessible — get_object_or_404 applies."""
        inactive = Institution.objects.create(
            name='Closed Hospital', slug='closed-hospital', is_active=False
        )
        url = reverse('institution:institution-switch', args=[inactive.pk])
        self.client.login(username='superadmin', password='testpass123')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302,
            "Switching to inactive institution should redirect (handle_view_errors wraps 404)")
        # Critical: session must NOT be updated to an inactive institution
        self.assertNotEqual(
            self.client.session.get('active_institution_id'), inactive.pk,
            "Session must not be set to an inactive institution"
        )

    def test_non_superadmin_cannot_switch(self):
        """Non-SUPERADMIN users are redirected without setting session."""
        admin = make_admin(institution=self.institution)
        self.client.login(username='admin', password='testpass123')
        response = self.client.post(self.switch_url)
        self.assertEqual(response.status_code, 302,
            "ADMIN should be redirected (not granted switch access)")
        self.assertIsNone(
            self.client.session.get('active_institution_id'),
            "ADMIN must not be able to set active_institution_id"
        )

    def test_switch_to_nonexistent_institution_denied(self):
        """Non-existent institution_id is denied — session not updated."""
        url = reverse('institution:institution-switch', args=[99999])
        self.client.login(username='superadmin', password='testpass123')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302,
            "Non-existent institution should redirect (handle_view_errors wraps 404)")
        self.assertIsNone(
            self.client.session.get('active_institution_id'),
            "Session must not be set for a non-existent institution"
        )


STATIC_OVERRIDE = override_settings(
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
    MULTI_INSTITUTION_ENABLED=True,
)


@STATIC_OVERRIDE
class SuperadminOverlayTest(TestCase):
    """AC #2: Overlay renders for SUPERADMIN with active context; hidden for ADMIN/USER (AC #4)."""

    def setUp(self):
        self.institution = Institution.objects.create(
            name='Test Hospital', slug='test-hospital'
        )
        self.superadmin = make_superadmin()
        self.admin = make_admin(institution=self.institution)

    def test_overlay_visible_for_superadmin_with_active_context(self):
        """AC #2: SUPERADMIN sees overlay banner after switching to an institution."""
        self.client.login(username='superadmin', password='testpass123')
        # Switch context via POST
        self.client.post(reverse('institution:institution-switch', args=[self.institution.pk]))
        # Load any authenticated page
        response = self.client.get(reverse('manage-patients'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'superadmin-context-banner',
            msg_prefix="Overlay banner div must appear for SUPERADMIN with active context (AC #2)")
        self.assertContains(response, 'Test Hospital',
            msg_prefix="Active institution name must appear in overlay banner")

    def test_overlay_hidden_for_superadmin_without_context(self):
        """Overlay not shown when SUPERADMIN has no active institution."""
        self.client.login(username='superadmin', password='testpass123')
        # Selector page — no active_institution_id in session
        response = self.client.get(reverse('institution:institution-selector'))
        self.assertNotContains(response, 'superadmin-context-banner',
            msg_prefix="Overlay must not render on selector (no active context)")

    def test_overlay_hidden_for_admin(self):
        """AC #4: ADMIN user never sees the superadmin overlay banner."""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('manage-patients'))
        self.assertNotContains(response, 'superadmin-context-banner',
            msg_prefix="ADMIN must never see the superadmin overlay banner (AC #4)")

    def test_overlay_shows_switch_dropdown(self):
        """AC #2: Switch dropdown is present in overlay with institution list."""
        self.client.login(username='superadmin', password='testpass123')
        self.client.post(reverse('institution:institution-switch', args=[self.institution.pk]))
        response = self.client.get(reverse('manage-patients'))
        self.assertContains(response, 'superadmin-switch-select',
            msg_prefix="Switch select element must appear in overlay")
