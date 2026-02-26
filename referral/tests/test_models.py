"""
referral/tests/test_models.py
Tests for Referral App Data Models (Story 4.1).
"""
import uuid
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, ReferralStatus
from referral.models import ReferralSent, ReferralReceived, ReferralMessage

User = get_user_model()


class ReferralModelsTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_ref', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771441001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='Referral Alpha', slug='ref-alpha',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Referral Beta', slug='ref-beta',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.clinician_a = User.objects.create_user(
            username='clin_a_ref', password='Testpass1!',
            first_name='Clin', last_name='A',
            position='Medical Officer', mobile_primary='0771441002',
            user_type=UserType.USER, institution=self.inst_a,
        )
        self.clinician_b = User.objects.create_user(
            username='clin_b_ref', password='Testpass1!',
            first_name='Clin', last_name='B',
            position='Medical Officer', mobile_primary='0771441003',
            user_type=UserType.USER, institution=self.inst_b,
        )


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ReferralStatusChoicesTest(ReferralModelsTestBase):
    def test_referral_status_choices_exist(self):
        """AC #1: ReferralStatus choices PENDING/REPLIED/CLOSED must exist."""
        self.assertEqual(ReferralStatus.PENDING, 'PENDING')
        self.assertEqual(ReferralStatus.REPLIED, 'REPLIED')
        self.assertEqual(ReferralStatus.CLOSED, 'CLOSED')


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ReferralUUIDCouplingTest(ReferralModelsTestBase):
    def _make_referral_pair(self):
        """Helper: create a matched ReferralSent + ReferralReceived pair."""
        shared_uuid = uuid.uuid4()
        snapshot = {'schema_version': 1, 'patient_name': 'Referral Patient'}
        sent = ReferralSent.objects.create(
            from_institution=self.inst_a,
            to_institution=self.inst_b,
            patient=None,  # patient FK is nullable
            from_clinician=self.clinician_a,
            to_clinician=self.clinician_b,
            referral_uuid=shared_uuid,
            initial_message='Please assess this patient.',
            snapshot_data=snapshot,
            institution=self.inst_a,
        )
        received = ReferralReceived.objects.create(
            to_institution=self.inst_b,
            from_institution=self.inst_a,
            patient_name='Referral Patient',
            from_clinician_name='Clin A',
            to_clinician=self.clinician_b,
            referral_uuid=shared_uuid,  # AC #2: copied, not regenerated
            initial_message='Please assess this patient.',
            snapshot_data=snapshot,
            institution=self.inst_b,
        )
        return sent, received

    def test_referral_uuid_is_shared(self):
        """AC #2: ReferralReceived must copy the same UUID from ReferralSent."""
        sent, received = self._make_referral_pair()
        self.assertEqual(sent.referral_uuid, received.referral_uuid,
            "AC #2: ReferralSent and ReferralReceived must share the same referral_uuid")

    def test_both_default_to_pending(self):
        """AC #2: Both records must default to status=PENDING."""
        sent, received = self._make_referral_pair()
        self.assertEqual(sent.status, ReferralStatus.PENDING)
        self.assertEqual(received.status, ReferralStatus.PENDING)

    def test_received_survives_sent_deletion(self):
        """AC #3: ReferralReceived remains accessible when ReferralSent is deleted."""
        sent, received = self._make_referral_pair()
        shared_uuid = sent.referral_uuid
        received_pk = received.pk

        sent.delete()  # Simulate institution A being suspended / ReferralSent deleted

        try:
            survivor = ReferralReceived.objects.get(pk=received_pk)
            self.assertEqual(survivor.referral_uuid, shared_uuid,
                "AC #3: ReferralReceived must remain intact after ReferralSent deletion")
        except ReferralReceived.DoesNotExist:
            self.fail("AC #3: ReferralReceived must survive deletion of ReferralSent")

    def test_institution_scoped_manager_filters_correctly(self):
        """AC #4: InstitutionScopedManager returns only own-institution records."""
        sent, received = self._make_referral_pair()
        inst_a_sent = ReferralSent.objects.for_institution(self.inst_a)
        self.assertIn(sent, inst_a_sent)
        inst_b_received = ReferralReceived.objects.for_institution(self.inst_b)
        self.assertIn(received, inst_b_received)


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ReferralMessageTest(ReferralModelsTestBase):
    def test_message_links_via_uuid(self):
        """AC #1: ReferralMessage links to referral by UUID."""
        shared_uuid = uuid.uuid4()
        msg = ReferralMessage.objects.create(
            referral_uuid=shared_uuid,
            sender=self.clinician_b,
            sender_institution=self.inst_b,
            body='Clinical opinion: Patient appears stable.',
            message_type=ReferralMessage.OPINION,
            added_by=self.clinician_b,
            last_edit_by=self.clinician_b,
        )
        self.assertEqual(msg.referral_uuid, shared_uuid)
        self.assertEqual(msg.message_type, ReferralMessage.OPINION)
