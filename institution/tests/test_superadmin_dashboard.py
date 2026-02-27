"""
Tests for Story 2.4 — Cross-Institution Aggregate Analytics Dashboard.

Covers:
- Only SUPERADMIN can access (AC: #1, #3)
- POST rejected (read-only view)
- Correct aggregate context variables (AC: #1)
- Recent events ordered newest-first (AC: #2)
- All institutions shown regardless of active session context (AC: #3)
- Zero-activity institutions render without error (AC: #4)
- Assessment count dicts always have all keys (AC: #4)
- Referral counts stubbed at zero until Story 4.1
"""
from datetime import timedelta

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

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
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
    RATELIMIT_ENABLE=False,
    MULTI_INSTITUTION_ENABLED=True,
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
        """H2 fix: ADMIN must receive a redirect — 200 would mean a security bypass."""
        make_admin(institution=self.institution)
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302,
            "ADMIN must be redirected from the superadmin analytics dashboard (not 200)")

    def test_post_returns_405(self):
        """Dashboard is read-only — POST must be rejected."""
        self.client.login(username='superadmin', password='testpass123')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 405,
            "POST to read-only dashboard must return 405 Method Not Allowed")


@STATIC_OVERRIDE
class SuperadminDashboardContentTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('institution:superadmin-dashboard')
        self.superadmin = make_superadmin()
        self.inst_a = Institution.objects.create(
            name='Alpha Hospital', slug='alpha',
            subscription_status=SubscriptionStatus.ACTIVE,
        )
        self.inst_b = Institution.objects.create(
            name='Beta Clinic', slug='beta',
            subscription_status=SubscriptionStatus.GRACE,
        )
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
        self.assertGreaterEqual(response.context['total_institutions'], 2)

    def test_uses_correct_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'institution/superadmin_dashboard.html')


@STATIC_OVERRIDE
class SuperadminDashboardRecentEventsTest(TestCase):
    """AC #2: Recent events appear in reverse chronological order."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('institution:superadmin-dashboard')
        self.superadmin = make_superadmin()
        self.client.login(username='superadmin', password='testpass123')

        now = timezone.now()
        self.inst_old = Institution.objects.create(name='Old Hospital', slug='old-hosp')
        # Force created_at to be older by updating via queryset (bypasses auto_now_add)
        Institution.objects.filter(pk=self.inst_old.pk).update(
            created_at=now - timedelta(days=10)
        )
        self.inst_new = Institution.objects.create(name='New Clinic', slug='new-clinic')
        Institution.objects.filter(pk=self.inst_new.pk).update(
            created_at=now - timedelta(days=1)
        )

    def test_recent_institutions_in_context(self):
        """AC #2: recent_institutions context variable is present."""
        response = self.client.get(self.url)
        self.assertIn('recent_institutions', response.context)

    def test_recent_institutions_ordered_newest_first(self):
        """AC #2: Events appear newest first (reverse chronological)."""
        response = self.client.get(self.url)
        recent = list(response.context['recent_institutions'])
        for i in range(len(recent) - 1):
            self.assertGreaterEqual(
                recent[i].created_at, recent[i + 1].created_at,
                "Recent institutions must be ordered newest-first"
            )


@STATIC_OVERRIDE
class SuperadminDashboardCrossInstitutionTest(TestCase):
    """AC #3: Dashboard reads ALL institutions regardless of active session context."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('institution:superadmin-dashboard')
        self.superadmin = make_superadmin()
        self.inst_a = Institution.objects.create(name='Alpha Hospital', slug='alpha-hosp')
        self.inst_b = Institution.objects.create(name='Beta Clinic', slug='beta-clinic')
        self.client.login(username='superadmin', password='testpass123')

    def test_all_institutions_shown_regardless_of_active_context(self):
        """AC #3: Setting active_institution_id in session must not filter dashboard results."""
        session = self.client.session
        session['active_institution_id'] = self.inst_a.pk
        session.save()

        response = self.client.get(self.url)
        names = [d['institution'].name for d in response.context['institution_data']]
        self.assertIn('Alpha Hospital', names,
            "Active institution must appear on the dashboard")
        self.assertIn('Beta Clinic', names,
            "Non-active institution must also appear — dashboard is an unscoped aggregate view")

    def test_institution_data_count_matches_all_institutions(self):
        """AC #3: institution_data length equals total institution count — no scoping."""
        response = self.client.get(self.url)
        total_in_db = Institution.objects.count()
        self.assertEqual(
            len(response.context['institution_data']), total_in_db,
            "AC #3: Dashboard must show all institutions without institution-scoped filtering"
        )


@STATIC_OVERRIDE
class SuperadminDashboardZeroStateTest(TestCase):
    """AC #4: Zero values render gracefully — no exceptions raised."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('institution:superadmin-dashboard')
        self.superadmin = make_superadmin()
        self.inst_a = Institution.objects.create(name='Alpha Hospital', slug='alpha-zero')
        self.client.login(username='superadmin', password='testpass123')

    def test_zero_activity_institution_renders_without_error(self):
        """AC #4: Institution with no patients, no assessments renders status 200."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200,
            "AC #4: Dashboard must load without error for zero-activity institutions")

    def test_assessment_counts_have_all_keys_as_integers(self):
        """AC #4: assessment_counts dict always has all 6 keys with integer values."""
        response = self.client.get(self.url)
        for item in response.context['institution_data']:
            counts = item['assessment_counts']
            for key in ['gma', 'hine', 'cdic', 'gpa', 'da', 'total']:
                self.assertIn(key, counts,
                    f"assessment_counts must have '{key}' key even for zero-activity institutions")
                self.assertIsInstance(counts[key], int,
                    f"assessment_counts['{key}'] must be int, not None or missing")

    def test_referral_stubs_return_zeros(self):
        """Referral counts are stubbed at 0 until Story 4.1 adds ReferralSent/ReferralReceived."""
        response = self.client.get(self.url)
        for item in response.context['institution_data']:
            r = item['referral_counts']
            for key in ['sent', 'received', 'pending', 'closed']:
                self.assertEqual(r[key], 0,
                    f"referral_counts['{key}'] must be 0 (stub until Story 4.1)")

    def test_empty_institution_list_renders_without_error(self):
        """AC #4: If no institutions exist the empty state renders without raising exceptions."""
        Institution.objects.all().delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200,
            "Dashboard must render without error when no institutions exist")
