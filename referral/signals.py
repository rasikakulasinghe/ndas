"""
referral/signals.py

Signal handlers and custom signals for referral lifecycle notifications (FR67–FR69).

All Notification.objects.create() calls live here — never in view files.
Handlers use try/except with logging so a signal failure never breaks a referral action.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal

logger = logging.getLogger(__name__)

# ── Custom signal for lifecycle status changes ─────────────────────────────
# Dispatched from referral_close() after bulk update (bulk update skips post_save).
# kwargs: referral_uuid (UUID), new_status (ReferralStatus), changed_by (User)
referral_status_changed = Signal()


# ── post_save: ReferralSent — new referral received ────────────────────────
@receiver(post_save, sender='referral.ReferralSent')
def notify_referral_received(sender, instance, created, **kwargs):
    """FR67: Notify receiving clinician when a new referral arrives."""
    if not created:
        return
    try:
        from referral.models import Notification
        from ndas.custom_codes.choice import NotificationType
        Notification.objects.create(
            recipient=instance.to_clinician,
            notification_type=NotificationType.REFERRAL_RECEIVED,
            title=f'New referral from {instance.from_institution.name}',
            body=instance.initial_message[:200],
            link=f'/referral/thread/{instance.referral_uuid}/',
            institution=instance.to_institution,
            added_by=instance.from_clinician,
            last_edit_by=instance.from_clinician,
        )
        logger.info(
            'REFERRAL_RECEIVED notification → %s (referral %s)',
            instance.to_clinician.username, instance.referral_uuid,
        )
    except Exception as exc:
        logger.error('notify_referral_received failed: %s', exc, exc_info=True)


# ── post_save: ReferralMessage — reply sent ────────────────────────────────
@receiver(post_save, sender='referral.ReferralMessage')
def notify_referral_replied(sender, instance, created, **kwargs):
    """FR68: Notify the OTHER party when a reply message is saved."""
    if not created:
        return
    try:
        from referral.models import ReferralSent, Notification
        from ndas.custom_codes.choice import NotificationType

        sent = ReferralSent.objects.filter(
            referral_uuid=instance.referral_uuid,
        ).select_related(
            'from_clinician', 'to_clinician',
            'from_institution', 'to_institution',
        ).first()

        if not sent:
            logger.warning(
                'notify_referral_replied: no ReferralSent for uuid=%s', instance.referral_uuid,
            )
            return

        # Recipient = whoever did NOT send this message
        if instance.sender_id == sent.from_clinician_id:
            recipient = sent.to_clinician
            recipient_institution = sent.to_institution
        else:
            recipient = sent.from_clinician
            recipient_institution = sent.from_institution

        Notification.objects.create(
            recipient=recipient,
            notification_type=NotificationType.REFERRAL_REPLIED,
            title=f'Reply from {instance.sender_institution.name}',
            body=instance.body[:200],
            link=f'/referral/thread/{instance.referral_uuid}/',
            institution=recipient_institution,
            added_by=instance.sender,
            last_edit_by=instance.sender,
        )
        logger.info(
            'REFERRAL_REPLIED notification → %s (referral %s)',
            recipient.username, instance.referral_uuid,
        )
    except Exception as exc:
        logger.error('notify_referral_replied failed: %s', exc, exc_info=True)


# ── Custom signal receiver: referral_status_changed — closure ──────────────
@receiver(referral_status_changed)
def notify_referral_closed(sender, referral_uuid, new_status, changed_by, **kwargs):
    """FR69: Notify both clinicians when a referral is closed."""
    try:
        from referral.models import ReferralSent, Notification
        from ndas.custom_codes.choice import NotificationType, ReferralStatus

        if new_status != ReferralStatus.CLOSED:
            return

        sent = ReferralSent.objects.filter(
            referral_uuid=referral_uuid,
        ).select_related(
            'from_clinician', 'to_clinician',
            'from_institution', 'to_institution',
        ).first()

        if not sent:
            return

        # Notify receiving clinician
        Notification.objects.create(
            recipient=sent.to_clinician,
            notification_type=NotificationType.REFERRAL_CLOSED,
            title=f'Referral from {sent.from_institution.name} has been closed',
            body='The referring clinician has closed this referral thread.',
            link=f'/referral/thread/{referral_uuid}/',
            institution=sent.to_institution,
            added_by=changed_by,
            last_edit_by=changed_by,
        )

        # Notify sending clinician (confirms closure)
        Notification.objects.create(
            recipient=sent.from_clinician,
            notification_type=NotificationType.REFERRAL_CLOSED,
            title=f'You closed a referral to {sent.to_institution.name}',
            body='This referral thread is now sealed.',
            link=f'/referral/thread/{referral_uuid}/',
            institution=sent.from_institution,
            added_by=changed_by,
            last_edit_by=changed_by,
        )

        logger.info(
            'REFERRAL_CLOSED notifications created (referral %s, by %s)',
            referral_uuid, changed_by.username,
        )
    except Exception as exc:
        logger.error('notify_referral_closed failed: %s', exc, exc_info=True)
