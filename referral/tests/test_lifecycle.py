"""
referral/tests/test_lifecycle.py
Tests for Referral Lifecycle & Closure (Story 4.5 — FR64, FR48).
"""
import uuid
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, ReferralStatus
from referral.models import ReferralSent, ReferralReceived, ReferralMessage

User = get_user_model()

STATIC_OVERRIDE = override_settings(
    MULTI_INSTITUTION_ENABLED=True,
    RATELIMIT_ENABLE=False,
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)


class LifecycleTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_lc', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771000011',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='LC Alpha', slug='lc-alpha',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='LC Beta', slug='lc-beta',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.clin_a = User.objects.create_user(
            username='clin_a_lc', password='Testpass1!',
            first_name='LC', last_name='Alpha',
            position='Medical Officer', mobile_primary='0771000012',
            user_type=UserType.USER, institution=self.inst_a,
        )
        self.clin_b = User.objects.create_user(
            username='clin_b_lc', password='Testpass1!',
            first_name='LC', last_name='Beta',
            position='Consultant', mobile_primary='0771000013',
            user_type=UserType.USER, institution=self.inst_b,
        )
        self.shared_uuid = uuid.uuid4()
        self.snapshot = {'schema_version': 1, 'demographics': {'baby_name': 'LC Patient'}, 'perinatal': {}}
        self.sent = ReferralSent.objects.create(
            from_institution=self.inst_a, to_institution=self.inst_b,
            institution=self.inst_a, patient=None,
            from_clinician=self.clin_a, to_clinician=self.clin_b,
            referral_uuid=self.shared_uuid, initial_message='Test.',
            snapshot_data=self.snapshot,
            added_by=self.clin_a, last_edit_by=self.clin_a,
        )
        self.received = ReferralReceived.objects.create(
            to_institution=self.inst_b, from_institution=self.inst_a,
            institution=self.inst_b, patient_name='LC Patient',
            from_clinician_name='LC Alpha', to_clinician=self.clin_b,
            referral_uuid=self.shared_uuid, initial_message='Test.',
            snapshot_data=self.snapshot,
            added_by=self.clin_a, last_edit_by=self.clin_a,
        )


@STATIC_OVERRIDE
class ClosureTest(LifecycleTestBase):
    def test_close_referral_sets_closed_on_both_records(self):
        """AC #1: Closing sets CLOSED status on both ReferralSent and ReferralReceived."""
        client = Client()
        client.force_login(self.clin_a)
        url = reverse('referral:referral-close', args=[self.shared_uuid])
        response = client.post(url)
        self.assertEqual(response.status_code, 200)
        self.sent.refresh_from_db()
        self.received.refresh_from_db()
        self.assertEqual(self.sent.status, ReferralStatus.CLOSED, "AC #1: ReferralSent must be CLOSED")
        self.assertEqual(self.received.status, ReferralStatus.CLOSED, "AC #1: ReferralReceived must be CLOSED")

    def test_non_sender_cannot_close(self):
        """AC #1: Receiving clinician cannot close the referral."""
        client = Client()
        client.force_login(self.clin_b)
        url = reverse('referral:referral-close', args=[self.shared_uuid])
        response = client.post(url)
        self.assertEqual(response.status_code, 403, "Receiving clinician must not be able to close")
        self.sent.refresh_from_db()
        self.assertNotEqual(self.sent.status, ReferralStatus.CLOSED)

    def test_reply_blocked_after_closure(self):
        """AC #2: No replies can be added after closure."""
        self.sent.status = ReferralStatus.CLOSED
        self.sent.save(update_fields=['status', 'updated_at'])
        self.received.status = ReferralStatus.CLOSED
        self.received.save(update_fields=['status', 'updated_at'])

        client = Client()
        client.force_login(self.clin_b)
        reply_url = reverse('referral:referral-reply', args=[self.shared_uuid])
        response = client.post(reply_url, {'body': 'Post-closure reply attempt.'})
        self.assertEqual(response.status_code, 403, "AC #2: Reply to CLOSED thread must return 403")
        self.assertEqual(ReferralMessage.objects.count(), 0)

    def test_close_thread_shows_closed_badge_in_panel(self):
        """AC #2 + AC #3: Thread panel shows CLOSED status and hides reply form."""
        client = Client()
        client.force_login(self.clin_a)
        close_url = reverse('referral:referral-close', args=[self.shared_uuid])
        response = client.post(close_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_closed'])
        self.assertIsNone(response.context['reply_form'])
        self.assertEqual(response.context['status'], ReferralStatus.CLOSED)


@STATIC_OVERRIDE
class GraceSubscriptionExemptionTest(LifecycleTestBase):
    def test_close_updates_timestamp(self):
        """H1: Closure via queryset .update() must stamp updated_at on both records."""
        from django.utils import timezone
        import datetime

        before = timezone.now() - datetime.timedelta(seconds=5)
        client = Client()
        client.force_login(self.clin_a)
        url = reverse('referral:referral-close', args=[self.shared_uuid])
        client.post(url)
        self.sent.refresh_from_db()
        self.received.refresh_from_db()
        self.assertGreater(self.sent.updated_at, before,
            "H1: ReferralSent.updated_at must be stamped on closure")
        self.assertGreater(self.received.updated_at, before,
            "H1: ReferralReceived.updated_at must be stamped on closure")

    def test_grace_institution_can_close_active_referral(self):
        """AC #4: GRACE subscription does not block referral closure (FR48 exemption)."""
        self.inst_a.subscription_status = SubscriptionStatus.GRACE
        self.inst_a.save()

        client = Client()
        client.force_login(self.clin_a)
        url = reverse('referral:referral-close', args=[self.shared_uuid])
        response = client.post(url)
        self.assertNotEqual(
            response.status_code, 403,
            "AC #4: GRACE subscription must not block active referral closure",
        )
        self.sent.refresh_from_db()
        self.assertEqual(self.sent.status, ReferralStatus.CLOSED)
