"""
referral/tests/test_inbox.py
Tests for Referral Inbox (Story 4.3 — FR63).
"""
import uuid
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus
from referral.models import ReferralSent, ReferralReceived

User = get_user_model()

STATIC_OVERRIDE = override_settings(
    MULTI_INSTITUTION_ENABLED=True,
    RATELIMIT_ENABLE=False,
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)


class InboxTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_inbox', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771221001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='Inbox Alpha', slug='inbox-alpha',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Inbox Beta', slug='inbox-beta',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.clinician_a = User.objects.create_user(
            username='clin_a_inbox', password='Testpass1!',
            first_name='Alpha', last_name='Clinician',
            position='Medical Officer', mobile_primary='0771221002',
            user_type=UserType.USER, institution=self.inst_a,
        )
        self.clinician_b = User.objects.create_user(
            username='clin_b_inbox', password='Testpass1!',
            first_name='Beta', last_name='Clinician',
            position='Medical Officer', mobile_primary='0771221003',
            user_type=UserType.USER, institution=self.inst_b,
        )
        self.inbox_url = reverse('referral:referral-inbox')

    def _create_referral_pair(self):
        """Create a matched ReferralSent + ReferralReceived pair for testing."""
        shared_uuid = uuid.uuid4()
        sent = ReferralSent.objects.create(
            from_institution=self.inst_a, to_institution=self.inst_b,
            institution=self.inst_a, patient=None,
            from_clinician=self.clinician_a, to_clinician=self.clinician_b,
            referral_uuid=shared_uuid, initial_message='Test referral.',
            snapshot_data={'schema_version': 1, 'demographics': {'baby_name': 'Inbox Test Patient'}},
            added_by=self.clinician_a, last_edit_by=self.clinician_a,
        )
        received = ReferralReceived.objects.create(
            to_institution=self.inst_b, from_institution=self.inst_a,
            institution=self.inst_b, patient_name='Inbox Test Patient',
            from_clinician_name='Alpha Clinician', to_clinician=self.clinician_b,
            referral_uuid=shared_uuid, initial_message='Test referral.',
            snapshot_data={'schema_version': 1}, is_read=False,
            added_by=self.clinician_a, last_edit_by=self.clinician_a,
        )
        return sent, received


@STATIC_OVERRIDE
class InboxAccessTest(InboxTestBase):
    def test_authenticated_user_can_access_inbox(self):
        """AC #1: Authenticated clinician can access the inbox (200 OK)."""
        client = Client()
        client.force_login(self.clinician_a)
        response = client.get(self.inbox_url)
        self.assertEqual(response.status_code, 200)


@STATIC_OVERRIDE
class InboxEmptyStateTest(InboxTestBase):
    def test_empty_state_no_exception(self):
        """AC #5: Inbox loads without errors when no referrals exist."""
        client = Client()
        client.force_login(self.clinician_a)
        response = client.get(self.inbox_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['thread_count'], 0)


@STATIC_OVERRIDE
class InboxThreadListTest(InboxTestBase):
    def test_sent_referral_appears_in_thread_list(self):
        """AC #2: Sent referral appears with direction='sent' in clinician A's inbox."""
        self._create_referral_pair()
        client = Client()
        client.force_login(self.clinician_a)
        response = client.get(self.inbox_url)
        self.assertEqual(response.context['thread_count'], 1)
        thread = response.context['threads'][0]
        self.assertEqual(thread['direction'], 'sent')

    def test_received_referral_appears_in_thread_list(self):
        """AC #2: Received referral appears with direction='received' in clinician B's inbox."""
        self._create_referral_pair()
        client = Client()
        client.force_login(self.clinician_b)
        response = client.get(self.inbox_url)
        self.assertEqual(response.context['thread_count'], 1)
        thread = response.context['threads'][0]
        self.assertEqual(thread['direction'], 'received')

    def test_unread_indicator_on_received_thread(self):
        """AC #4: is_unread=True for unread received referral."""
        self._create_referral_pair()
        client = Client()
        client.force_login(self.clinician_b)
        response = client.get(self.inbox_url)
        thread = response.context['threads'][0]
        self.assertTrue(thread['is_unread'], "AC #4: Unread received referral must show is_unread=True")

    def test_sent_thread_is_never_unread(self):
        """Sent items have no unread state (is_unread=False)."""
        self._create_referral_pair()
        client = Client()
        client.force_login(self.clinician_a)
        response = client.get(self.inbox_url)
        thread = response.context['threads'][0]
        self.assertFalse(thread['is_unread'], "Sent referral must never show is_unread=True")


@STATIC_OVERRIDE
class InboxThreadPanelTest(InboxTestBase):
    def test_thread_panel_loads_via_get(self):
        """AC #3: Thread panel HTMX endpoint returns 200 for the sending clinician."""
        sent, received = self._create_referral_pair()
        client = Client()
        client.force_login(self.clinician_a)
        url = reverse('referral:referral-thread-panel', args=[sent.referral_uuid])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_thread_panel_marks_received_as_read(self):
        """AC #3: Opening thread panel marks ReferralReceived.is_read=True for recipient."""
        sent, received = self._create_referral_pair()
        self.assertFalse(received.is_read, "Precondition: must be unread before opening")
        client = Client()
        client.force_login(self.clinician_b)
        url = reverse('referral:referral-thread-panel', args=[received.referral_uuid])
        client.get(url)
        received.refresh_from_db()
        self.assertTrue(received.is_read, "AC #3: Opening thread panel must mark received as is_read=True")
