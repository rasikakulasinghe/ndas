"""
referral/tests/test_thread.py
Tests for Referral Thread View & Reply (Story 4.4 — FR62, FR64).
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


class ThreadTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_thread', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771111001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='Thread Alpha', slug='thread-alpha',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Thread Beta', slug='thread-beta',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.clin_a = User.objects.create_user(
            username='clin_a_thread', password='Testpass1!',
            first_name='Thread', last_name='Alpha',
            position='Medical Officer', mobile_primary='0771111002',
            user_type=UserType.USER, institution=self.inst_a,
        )
        self.clin_b = User.objects.create_user(
            username='clin_b_thread', password='Testpass1!',
            first_name='Thread', last_name='Beta',
            position='Consultant', mobile_primary='0771111003',
            user_type=UserType.USER, institution=self.inst_b,
        )
        # Non-participant colleague at inst_a — same institution as clin_a but not
        # assigned to this referral. Used to verify institution membership alone
        # is not sufficient to access the thread.
        self.clin_a_colleague = User.objects.create_user(
            username='clin_a_colleague_thread', password='Testpass1!',
            first_name='Colleague', last_name='Alpha',
            position='Medical Officer', mobile_primary='0771111004',
            user_type=UserType.USER, institution=self.inst_a,
        )
        # Institution ADMIN at inst_b (the receiving side) — not a participant
        # clinician, but should still be granted access per _is_thread_participant.
        self.admin_b = User.objects.create_user(
            username='admin_b_thread', password='Testpass1!',
            first_name='Admin', last_name='Beta',
            position='Administrator', mobile_primary='0771111005',
            user_type=UserType.ADMIN, institution=self.inst_b,
        )
        self.shared_uuid = uuid.uuid4()
        self.snapshot = {
            'schema_version': 1,
            'captured_at': '2026-02-24T10:00:00',
            'demographics': {'baby_name': 'Thread Patient', 'bht': 'BHT001', 'nnc_no': 'NNC001'},
            'perinatal': {},
        }
        self.sent = ReferralSent.objects.create(
            from_institution=self.inst_a, to_institution=self.inst_b,
            institution=self.inst_a, patient=None,
            from_clinician=self.clin_a, to_clinician=self.clin_b,
            referral_uuid=self.shared_uuid, initial_message='Test referral.',
            snapshot_data=self.snapshot,
            added_by=self.clin_a, last_edit_by=self.clin_a,
        )
        self.received = ReferralReceived.objects.create(
            to_institution=self.inst_b, from_institution=self.inst_a,
            institution=self.inst_b, patient_name='Thread Patient',
            from_clinician_name='Thread Alpha', to_clinician=self.clin_b,
            referral_uuid=self.shared_uuid, initial_message='Test referral.',
            snapshot_data=self.snapshot,
            added_by=self.clin_a, last_edit_by=self.clin_a,
        )


@STATIC_OVERRIDE
class ThreadViewTest(ThreadTestBase):
    def test_thread_panel_shows_patient_header(self):
        """AC #1: Patient name and BHT must appear in thread panel context."""
        client = Client()
        client.force_login(self.clin_a)
        url = reverse('referral:referral-thread-panel', args=[self.shared_uuid])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['patient_header']['baby_name'], 'Thread Patient')
        self.assertEqual(response.context['patient_header']['bht'], 'BHT001')

    def test_thread_panel_has_snapshot_data(self):
        """AC #2: Snapshot data available in context for collapsible <details> panel."""
        client = Client()
        client.force_login(self.clin_a)
        url = reverse('referral:referral-thread-panel', args=[self.shared_uuid])
        response = client.get(url)
        self.assertIn('snapshot_data', response.context)
        self.assertEqual(response.context['snapshot_data']['schema_version'], 1)

    def test_thread_panel_reply_form_present_for_open_thread(self):
        """Reply form is provided in context for non-closed threads."""
        client = Client()
        client.force_login(self.clin_a)
        url = reverse('referral:referral-thread-panel', args=[self.shared_uuid])
        response = client.get(url)
        self.assertIsNotNone(response.context['reply_form'])

    def test_thread_panel_reply_form_absent_for_closed_thread(self):
        """Reply form is NOT provided when thread is CLOSED."""
        self.sent.status = ReferralStatus.CLOSED
        self.sent.save()
        client = Client()
        client.force_login(self.clin_a)
        url = reverse('referral:referral-thread-panel', args=[self.shared_uuid])
        response = client.get(url)
        self.assertIsNone(response.context['reply_form'])

    def test_non_participant_colleague_cannot_view_thread(self):
        """A same-institution colleague who is not from_clinician/to_clinician is denied (404)."""
        client = Client()
        client.force_login(self.clin_a_colleague)
        url = reverse('referral:referral-thread-panel', args=[self.shared_uuid])
        response = client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_institution_admin_can_view_thread(self):
        """An ADMIN at either institution (not just the assigned clinician) is granted access."""
        client = Client()
        client.force_login(self.admin_b)
        url = reverse('referral:referral-thread-panel', args=[self.shared_uuid])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)


@STATIC_OVERRIDE
class ReferralReplyTest(ThreadTestBase):
    def test_reply_creates_message(self):
        """AC #4: Reply creates a ReferralMessage with OPINION type."""
        client = Client()
        client.force_login(self.clin_b)
        url = reverse('referral:referral-reply', args=[self.shared_uuid])
        response = client.post(url, {'body': 'My clinical opinion on this patient case.'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ReferralMessage.objects.filter(referral_uuid=self.shared_uuid).count(), 1,
        )
        msg = ReferralMessage.objects.first()
        self.assertEqual(msg.message_type, ReferralMessage.OPINION)

    def test_reply_updates_status_to_replied(self):
        """AC #4: Replying updates status to REPLIED on both records."""
        client = Client()
        client.force_login(self.clin_b)
        url = reverse('referral:referral-reply', args=[self.shared_uuid])
        client.post(url, {'body': 'Clinical opinion — patient is improving significantly.'})
        self.sent.refresh_from_db()
        self.received.refresh_from_db()
        self.assertEqual(self.sent.status, ReferralStatus.REPLIED)
        self.assertEqual(self.received.status, ReferralStatus.REPLIED)

    def test_reply_to_closed_thread_rejected(self):
        """AC #5: Reply to CLOSED referral must be rejected (403)."""
        self.sent.status = ReferralStatus.CLOSED
        self.sent.save(update_fields=['status', 'updated_at'])
        self.received.status = ReferralStatus.CLOSED
        self.received.save(update_fields=['status', 'updated_at'])

        client = Client()
        client.force_login(self.clin_b)
        url = reverse('referral:referral-reply', args=[self.shared_uuid])
        response = client.post(url, {'body': 'Attempt to reply after close.'})
        self.assertEqual(response.status_code, 403, "AC #5: Reply to CLOSED thread must return 403")
        self.assertEqual(
            ReferralMessage.objects.count(), 0,
            "AC #5: No message must be created for closed thread reply",
        )

    def test_empty_body_reply_does_not_create_message(self):
        """M2: Empty body must not create a ReferralMessage (form validation rejects it)."""
        client = Client()
        client.force_login(self.clin_b)
        url = reverse('referral:referral-reply', args=[self.shared_uuid])
        client.post(url, {'body': ''})
        self.assertEqual(
            ReferralMessage.objects.count(), 0,
            "M2: Empty body must not create a ReferralMessage",
        )

    def test_non_participant_colleague_cannot_reply(self):
        """A same-institution colleague who is not from_clinician/to_clinician cannot reply (404)."""
        client = Client()
        client.force_login(self.clin_a_colleague)
        url = reverse('referral:referral-reply', args=[self.shared_uuid])
        response = client.post(url, {'body': 'I am not a participant on this referral.'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            ReferralMessage.objects.count(), 0,
            "Non-participant reply must not create a ReferralMessage",
        )

    def test_reply_updates_timestamp(self):
        """H1: Status transition via .update() must stamp updated_at."""
        from django.utils import timezone
        import datetime

        before = timezone.now() - datetime.timedelta(seconds=5)
        client = Client()
        client.force_login(self.clin_b)
        url = reverse('referral:referral-reply', args=[self.shared_uuid])
        client.post(url, {'body': 'Timestamp verification reply message.'})
        self.sent.refresh_from_db()
        self.assertGreater(
            self.sent.updated_at, before,
            "H1: updated_at must be refreshed after status change via queryset .update()",
        )
