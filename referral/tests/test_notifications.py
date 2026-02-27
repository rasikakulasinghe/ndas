"""
referral/tests/test_notifications.py
Tests for Notification model and signal infrastructure (Story 5.1 — FR67–FR69).
"""
import uuid
import datetime
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, NotificationType
from referral.models import ReferralSent, ReferralReceived, ReferralMessage, Notification

User = get_user_model()

# Valid patient fields — Patient.save() calls full_clean() which validates required fields
VALID_PATIENT_FIELDS = {
    'baby_name': 'NS Patient',
    'mother_name': 'NS Mother',
    'gender': 'Male',
    'dob_tob': datetime.datetime(2023, 1, 15, 8, 30, tzinfo=datetime.timezone.utc),
    'mo_delivery': 'Normal vaginal delivery (NVD)',
    'birth_weight': 3000,
    'ofc': 33,
    'tp_mobile': '0771000013',
}


class NotificationSignalBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_ns', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771000010',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='NS Alpha', slug='ns-alpha',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='NS Beta', slug='ns-beta',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.clin_a = User.objects.create_user(
            username='clin_a_ns', password='Testpass1!',
            first_name='NS', last_name='Alpha',
            position='Medical Officer', mobile_primary='0771000011',
            user_type=UserType.USER, institution=self.inst_a,
        )
        self.clin_b = User.objects.create_user(
            username='clin_b_ns', password='Testpass1!',
            first_name='NS', last_name='Beta',
            position='Consultant', mobile_primary='0771000012',
            user_type=UserType.USER, institution=self.inst_b,
        )
        from patients.models import Patient
        self.patient = Patient.objects.create(
            institution=self.inst_a,
            added_by=self.clin_a, last_edit_by=self.clin_a,
            **VALID_PATIENT_FIELDS,
        )
        self.shared_uuid = uuid.uuid4()

    def _make_referral_pair(self):
        """Create a matching ReferralSent + ReferralReceived pair."""
        sent = ReferralSent.objects.create(
            from_institution=self.inst_a, to_institution=self.inst_b,
            institution=self.inst_a, patient=self.patient,
            from_clinician=self.clin_a, to_clinician=self.clin_b,
            referral_uuid=self.shared_uuid, initial_message='Signal test.',
            snapshot_data={'schema_version': 1},
            added_by=self.clin_a, last_edit_by=self.clin_a,
        )
        ReferralReceived.objects.create(
            to_institution=self.inst_b, from_institution=self.inst_a,
            institution=self.inst_b, patient_name='NS Patient',
            from_clinician_name='NS Alpha', to_clinician=self.clin_b,
            referral_uuid=self.shared_uuid, initial_message='Signal test.',
            snapshot_data={'schema_version': 1},
            added_by=self.clin_a, last_edit_by=self.clin_a,
        )
        return sent


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ReferralReceivedNotificationTest(NotificationSignalBase):
    def test_creates_notification_on_referral_sent_creation(self):
        """FR67: Creating ReferralSent triggers REFERRAL_RECEIVED notification for to_clinician."""
        self._make_referral_pair()
        notif = Notification.objects.filter(
            recipient=self.clin_b,
            notification_type=NotificationType.REFERRAL_RECEIVED,
        ).first()
        self.assertIsNotNone(notif, 'FR67: REFERRAL_RECEIVED notification must be created')
        self.assertEqual(notif.institution, self.inst_b,
            'Notification must be scoped to receiving institution')

    def test_no_notification_on_referral_update(self):
        """FR67: Updating ReferralSent does not create duplicate notifications."""
        sent = self._make_referral_pair()
        count_before = Notification.objects.filter(
            notification_type=NotificationType.REFERRAL_RECEIVED,
        ).count()
        sent.status = 'REPLIED'
        sent.save()
        count_after = Notification.objects.filter(
            notification_type=NotificationType.REFERRAL_RECEIVED,
        ).count()
        self.assertEqual(count_before, count_after,
            'Update (not create) must not trigger additional REFERRAL_RECEIVED notifications')


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ReferralRepliedNotificationTest(NotificationSignalBase):
    def test_creates_notification_when_receiver_replies(self):
        """FR68: Receiver reply creates REFERRAL_REPLIED notification for sender."""
        self._make_referral_pair()
        ReferralMessage.objects.create(
            referral_uuid=self.shared_uuid,
            sender=self.clin_b, sender_institution=self.inst_b,
            body='Specialist opinion here.',
            message_type='OPINION',
            added_by=self.clin_b, last_edit_by=self.clin_b,
        )
        notif = Notification.objects.filter(
            recipient=self.clin_a,
            notification_type=NotificationType.REFERRAL_REPLIED,
        ).first()
        self.assertIsNotNone(notif, 'FR68: REFERRAL_REPLIED notification must be created for the sender')
        self.assertEqual(notif.institution, self.inst_a)

    def test_creates_notification_when_sender_replies(self):
        """FR68: Sender reply creates REFERRAL_REPLIED notification for receiver (symmetric path)."""
        self._make_referral_pair()
        ReferralMessage.objects.create(
            referral_uuid=self.shared_uuid,
            sender=self.clin_a, sender_institution=self.inst_a,
            body='Follow-up from referring clinician.',
            message_type='OPINION',
            added_by=self.clin_a, last_edit_by=self.clin_a,
        )
        notif = Notification.objects.filter(
            recipient=self.clin_b,
            notification_type=NotificationType.REFERRAL_REPLIED,
        ).first()
        self.assertIsNotNone(notif,
            'FR68: REFERRAL_REPLIED notification must be created for receiver when sender replies')
        self.assertEqual(notif.institution, self.inst_b)


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ReferralClosedNotificationTest(NotificationSignalBase):
    def test_dispatching_referral_status_changed_creates_closed_notifications(self):
        """FR69: Custom signal dispatch creates REFERRAL_CLOSED notifications for both parties."""
        self._make_referral_pair()
        from referral.signals import referral_status_changed
        from ndas.custom_codes.choice import ReferralStatus
        referral_status_changed.send(
            sender=ReferralSent,
            referral_uuid=self.shared_uuid,
            new_status=ReferralStatus.CLOSED,
            changed_by=self.clin_a,
        )
        closed_notifs = Notification.objects.filter(
            notification_type=NotificationType.REFERRAL_CLOSED,
        )
        self.assertGreaterEqual(closed_notifs.count(), 2,
            'FR69: Both clinicians must receive REFERRAL_CLOSED notifications')
        recipients = set(closed_notifs.values_list('recipient_id', flat=True))
        self.assertIn(self.clin_a.id, recipients, 'Sending clinician must be notified')
        self.assertIn(self.clin_b.id, recipients, 'Receiving clinician must be notified')
