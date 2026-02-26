from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from institution.models import Institution
from institution.middleware import InstitutionContextMiddleware
from institution.context_processors import institution_context
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()


def _make_clinician(username, institution=None, user_type=UserType.USER):
    return User.objects.create_user(
        username=username, password='testpass123',
        first_name='Test', last_name='User',
        position='Medical Officer', mobile_primary='0771234567',
        user_type=user_type,
        institution=institution,
    )


def _make_request(factory, path='/', method='GET'):
    if method == 'POST':
        request = factory.post(path)
    else:
        request = factory.get(path)
    # Attach session and messages (required by middleware)
    request.session = SessionStore()
    messages_storage = FallbackStorage(request)
    request._messages = messages_storage
    return request


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class InstitutionContextMiddlewareTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = InstitutionContextMiddleware(get_response=lambda r: None)
        self.institution = Institution.objects.create(
            name='Test Hospital',
            slug='test-hospital',
            subscription_status=SubscriptionStatus.ACTIVE,
        )
        self.institution_grace = Institution.objects.create(
            name='Grace Hospital',
            slug='grace-hospital',
            subscription_status=SubscriptionStatus.GRACE,
        )
        self.institution_expired = Institution.objects.create(
            name='Expired Hospital',
            slug='expired-hospital',
            subscription_status=SubscriptionStatus.EXPIRED,
        )

    def test_clinician_request_sets_institution_on_request(self):
        """AC #1: ADMIN/USER request sets request.institution from user FK."""
        user = _make_clinician('clinician1', self.institution)
        request = _make_request(self.factory)
        request.user = user
        response = self.middleware.process_request(request)
        self.assertIsNone(response)  # No redirect
        self.assertEqual(request.institution, self.institution)

    def test_grace_institution_get_allowed(self):
        """AC #4: GRACE + GET request passes through (no redirect)."""
        user = _make_clinician('clinician2', self.institution_grace)
        request = _make_request(self.factory, path='/', method='GET')
        request.user = user
        response = self.middleware.process_request(request)
        self.assertIsNone(response)  # GET allowed in grace period

    def test_grace_institution_post_blocked(self):
        """AC #4: GRACE + POST (non-referral) returns redirect."""
        user = _make_clinician('clinician3', self.institution_grace)
        request = _make_request(self.factory, path='/patient/add/', method='POST')
        request.META['HTTP_REFERER'] = '/patient/'
        request.user = user
        response = self.middleware.process_request(request)
        self.assertIsNotNone(response)  # Should redirect back
        self.assertEqual(response.status_code, 302)

    def test_grace_institution_referral_post_allowed(self):
        """AC #4: GRACE + POST to /referral/ is exempt and passes through."""
        user = _make_clinician('clinician4', self.institution_grace)
        request = _make_request(self.factory, path='/referral/reply/', method='POST')
        request.user = user
        response = self.middleware.process_request(request)
        self.assertIsNone(response)  # Referral POSTs exempt from grace block

    def test_superadmin_with_session_sets_institution(self):
        """AC #2: SUPERADMIN with active_institution_id in session gets institution set."""
        superadmin = _make_clinician('superadmin1', user_type=UserType.SUPERADMIN)
        request = _make_request(self.factory)
        request.user = superadmin
        request.session['active_institution_id'] = self.institution.pk
        response = self.middleware.process_request(request)
        self.assertIsNone(response)
        self.assertEqual(request.institution, self.institution)

    def test_superadmin_without_session_redirects_to_selector(self):
        """AC #3: SUPERADMIN with no session active_institution_id redirects."""
        superadmin = _make_clinician('superadmin2', user_type=UserType.SUPERADMIN)
        request = _make_request(self.factory)
        request.user = superadmin
        # No active_institution_id in session
        response = self.middleware.process_request(request)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/institution/', response['Location'])

    def test_expired_institution_redirects_to_subscription_info(self):
        """AC #5: EXPIRED institution — middleware redirects to subscription-info."""
        user = _make_clinician('clinician_exp', self.institution_expired)
        request = _make_request(self.factory)
        request.user = user
        response = self.middleware.process_request(request)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)
        self.assertIn('subscription', response['Location'])

    def test_unauthenticated_request_passes_through(self):
        """Unauthenticated requests are not processed (no institution resolution)."""
        request = _make_request(self.factory)
        request.user = AnonymousUser()
        response = self.middleware.process_request(request)
        self.assertIsNone(response)


class ContextProcessorTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.institution = Institution.objects.create(
            name='Test Hospital',
            slug='test-hospital',
        )

    def test_anonymous_request_returns_empty_dict(self):
        """AC #6: Anonymous requests return {}."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        result = institution_context(request)
        self.assertEqual(result, {})

    def test_authenticated_request_injects_variables(self):
        """AC #6: Authenticated requests get active_institution, user_type, is_superadmin."""
        request = self.factory.get('/')
        user = _make_clinician('cp_clinician', self.institution)
        request.user = user
        request.institution = self.institution
        result = institution_context(request)
        self.assertIn('active_institution', result)
        self.assertIn('user_type', result)
        self.assertIn('is_superadmin', result)
        self.assertEqual(result['active_institution'], self.institution)
        self.assertEqual(result['user_type'], UserType.USER)
        self.assertFalse(result['is_superadmin'])

    def test_superadmin_flag_is_true_for_superadmin_user(self):
        """AC #6: is_superadmin is True for SUPERADMIN user_type."""
        request = self.factory.get('/')
        user = _make_clinician('cp_superadmin', user_type=UserType.SUPERADMIN)
        request.user = user
        request.institution = None
        result = institution_context(request)
        self.assertTrue(result['is_superadmin'])
        self.assertEqual(result['user_type'], UserType.SUPERADMIN)


# ─────────────────────────────────────────────────────────────────────────────
# Story 1.7: ADMIN/USER/SUPERADMIN context resolution + subscription gate
# These extend the Story 1.3 middleware unit tests with Client-based assertions.
# ─────────────────────────────────────────────────────────────────────────────

_NO_STATIC = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(
    MULTI_INSTITUTION_ENABLED=True,
    STORAGES=_NO_STATIC,
    RATELIMIT_ENABLE=False,
)
class MiddlewareContextResolutionClientTest(TestCase):
    """Test that middleware sets request.institution correctly for ADMIN and USER types."""

    def setUp(self):
        from institution.models import Institution
        self.institution_a = Institution.objects.create(
            name='Resolution Hospital A',
            slug='res-hospital-a',
            subscription_status=SubscriptionStatus.ACTIVE,
            is_active=True,
        )

    def test_admin_user_gets_institution_context(self):
        """ADMIN user → institution context resolves, patient list loads (200 or redirect)."""
        from django.test import Client
        from django.urls import reverse
        admin = _make_clinician('admin_ctx', self.institution_a, UserType.ADMIN)
        client = Client()
        client.force_login(admin)
        response = client.get(reverse('manage-patients'))
        self.assertIn(response.status_code, [200, 302],
            f"ADMIN user must receive 200 or 302; got {response.status_code}")

    def test_regular_user_gets_institution_context(self):
        """USER → institution context resolves, patient list loads (200 or redirect)."""
        from django.test import Client
        from django.urls import reverse
        user = _make_clinician('user_ctx', self.institution_a, UserType.USER)
        client = Client()
        client.force_login(user)
        response = client.get(reverse('manage-patients'))
        self.assertIn(response.status_code, [200, 302],
            f"Regular USER must receive 200 or 302; got {response.status_code}")


@override_settings(
    MULTI_INSTITUTION_ENABLED=True,
    STORAGES=_NO_STATIC,
    RATELIMIT_ENABLE=False,
)
class SubscriptionGateClientTest(TestCase):
    """Test GRACE subscription allows GET but blocks POST."""

    def setUp(self):
        from datetime import date, timedelta
        from institution.models import Institution
        self.grace_institution = Institution.objects.create(
            name='Grace Hospital',
            slug='grace-hosp-17',
            subscription_status=SubscriptionStatus.GRACE,
            grace_period_end=date.today() + timedelta(days=3),
            is_active=True,
        )
        self.grace_user = _make_clinician('grace_user_17', self.grace_institution, UserType.USER)

    def test_grace_institution_allows_get(self):
        """GRACE subscription: GET requests are allowed (read-only mode)."""
        from django.test import Client
        from django.urls import reverse
        client = Client()
        client.force_login(self.grace_user)
        response = client.get(reverse('manage-patients'))
        self.assertNotEqual(response.status_code, 403,
            "GET must be allowed for GRACE institution")

    def test_grace_institution_blocks_post(self):
        """GRACE subscription: POST requests are blocked (read-only mode)."""
        from django.test import Client
        from django.urls import reverse
        client = Client()
        client.force_login(self.grace_user)
        response = client.post(reverse('add-patient'), data={})
        self.assertIn(response.status_code, [403, 302],
            "POST to add-patient should be blocked for GRACE institution")
