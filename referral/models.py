"""
referral/models.py

Cross-institution referral data models.

Key architecture decisions:
- ReferralSent and ReferralReceived are INDEPENDENT records linked by referral_uuid.
- Neither record has a FK to the other — this ensures both survive if the other's
  institution is suspended or deleted (FR66 + NFR22).
- snapshot_data is captured once at referral submission and is IMMUTABLE thereafter (FR61).
- Notification model added in Story 5.1.
"""
import uuid
import logging

from django.conf import settings
from django.db import models

from institution.managers import InstitutionScopedManager
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.choice import ReferralStatus, NotificationType

logger = logging.getLogger(__name__)


class ReferralSent(TimeStampedModel, UserTrackingMixin):
    """
    Referral record owned by the SENDING institution.

    Created atomically with ReferralReceived (transaction.atomic in Story 4.2 view).
    FR60, FR61, FR66.
    """
    # The institution that SENT this referral
    from_institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_sent',
        db_index=True,
    )
    # The institution receiving this referral
    to_institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_received_at',
        db_index=True,
    )
    # The patient being referred (scoped to from_institution)
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_sent',
        db_index=True,
    )
    # The clinician who sent the referral
    from_clinician = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_sent_by',
        db_index=True,
    )
    # The clinician at the receiving institution who is the referral target
    to_clinician = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_received_by',
        db_index=True,
    )

    # UUID shared with ReferralReceived — links the two records without a direct FK
    referral_uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Shared with ReferralReceived. Generated once at creation; never regenerated."
    )

    status = models.CharField(
        max_length=20,
        choices=ReferralStatus.choices,
        default=ReferralStatus.PENDING,
        db_index=True,
    )
    initial_message = models.TextField(
        help_text="The referral message from the sending clinician."
    )
    # Frozen snapshot of patient record at referral time — immutable after creation (FR61)
    snapshot_data = models.JSONField(
        default=dict,
        help_text="Frozen patient record snapshot at referral submission time. Do not modify after creation."
    )
    outcome = models.TextField(
        blank=True,
        help_text="Clinical outcome note, added at closure."
    )

    # institution FK for InstitutionScopedManager scoping (= from_institution, set at creation)
    institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_owned_sent',
        db_index=True,
        help_text="Owning institution for scoping. Same as from_institution."
    )

    objects = InstitutionScopedManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['referral_uuid']),
            models.Index(fields=['from_institution', 'status']),
            models.Index(fields=['to_institution', 'status']),
        ]

    def __str__(self):
        return f"ReferralSent[{self.referral_uuid}] {self.status}"


class ReferralReceived(TimeStampedModel, UserTrackingMixin):
    """
    Referral record owned by the RECEIVING institution.

    Created atomically with ReferralSent (transaction.atomic in Story 4.2 view).
    Has NO FK to ReferralSent — fully self-contained (FR66).
    Links to ReferralSent only via referral_uuid for cross-institution lookup.
    FR41, FR62, FR63, FR66.
    """
    # The institution that RECEIVED this referral
    to_institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_received',
        db_index=True,
    )
    from_institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_sent_from',
        db_index=True,
    )
    patient_name = models.CharField(
        max_length=200,
        help_text="Denormalized patient name from snapshot, for display without patient FK lookup."
    )
    from_clinician_name = models.CharField(
        max_length=200,
        help_text="Denormalized sending clinician name."
    )
    to_clinician = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_received_as_clinician',
        db_index=True,
    )

    # COPIED from ReferralSent.referral_uuid — same UUID, never regenerated (AC #2)
    referral_uuid = models.UUIDField(
        db_index=True,
        editable=False,
        help_text="Copied from ReferralSent.referral_uuid. Never regenerated."
    )

    status = models.CharField(
        max_length=20,
        choices=ReferralStatus.choices,
        default=ReferralStatus.PENDING,
        db_index=True,
    )
    initial_message = models.TextField(
        help_text="Copy of the referral message from the sending clinician."
    )
    # Own copy of snapshot — self-contained even if ReferralSent is deleted (FR66)
    snapshot_data = models.JSONField(
        default=dict,
        help_text="Own copy of patient snapshot. Self-contained regardless of ReferralSent state."
    )
    outcome = models.TextField(
        blank=True,
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True once the receiving clinician has opened the referral thread."
    )

    # institution FK for InstitutionScopedManager scoping (= to_institution, set at creation)
    institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_owned_received',
        db_index=True,
        help_text="Owning institution for scoping. Same as to_institution."
    )

    objects = InstitutionScopedManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['referral_uuid']),
            models.Index(fields=['to_institution', 'status']),
        ]

    def __str__(self):
        return f"ReferralReceived[{self.referral_uuid}] {self.status}"


class ReferralMessage(TimeStampedModel, UserTrackingMixin):
    """
    A consultation message in a referral thread.

    Linked to the referral via referral_uuid (no direct FK to ReferralSent/Received —
    allows messages to be retrieved from either institution's side).
    FR62, FR64.
    """
    OPINION = 'OPINION'
    MESSAGE_TYPE_CHOICES = [
        (OPINION, 'Clinical Opinion'),
    ]

    # Links to both ReferralSent and ReferralReceived via UUID
    referral_uuid = models.UUIDField(
        db_index=True,
        help_text="Shared referral_uuid — links to both ReferralSent and ReferralReceived."
    )
    sender = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referral_messages_sent',
        db_index=True,
    )
    sender_institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referral_messages',
        db_index=True,
        help_text="Institution of the sender at the time of the message (for display badge)."
    )
    body = models.TextField()
    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPE_CHOICES,
        default=OPINION,
    )

    class Meta:
        ordering = ['created_at']  # Chronological in thread view

    def __str__(self):
        return f"ReferralMessage[{self.referral_uuid}] by {self.sender_id}"


class Notification(TimeStampedModel, UserTrackingMixin):
    """
    In-app notification for referral lifecycle events (FR38, FR67–FR69).

    Scoped to recipient's institution via InstitutionScopedManager.
    Created exclusively by referral/signals.py — never directly by views (AC #5).
    """
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_notifications',
        db_index=True,
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        db_index=True,
    )
    title   = models.CharField(max_length=200)
    body    = models.TextField(blank=True)
    link    = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.CASCADE,
        related_name='notifications',
    )

    objects = InstitutionScopedManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.notification_type} → {self.recipient.username} ({self.created_at:%Y-%m-%d})'
