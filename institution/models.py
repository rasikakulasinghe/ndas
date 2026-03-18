from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.choice import SubscriptionStatus
from ndas.custom_codes.validators import get_institution_logo_path


class Institution(TimeStampedModel, UserTrackingMixin):
    name = models.CharField(max_length=255, unique=True, db_index=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    short_name = models.CharField(max_length=10, blank=True, default='')
    logo = models.ImageField(
        upload_to=get_institution_logo_path,  # Story 3.3: institution-aware logo path (FR58)
        null=True, blank=True,
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE
    )
    subscription_start = models.DateField(null=True, blank=True)
    grace_period_end = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='institutions_created',
        help_text="SUPERADMIN who onboarded this institution"
    )

    def save(self, *args, **kwargs):
        if self.pk:
            original = Institution.objects.get(pk=self.pk)
            if original.slug != self.slug:
                raise ValidationError("Institution slug is immutable and cannot be changed after creation.")
        super().save(*args, **kwargs)

    def clean(self):
        if self.pk:
            try:
                original = Institution.objects.get(pk=self.pk)
                if original.slug != self.slug:
                    raise ValidationError({'slug': 'Institution slug is immutable and cannot be changed after creation.'})
            except Institution.DoesNotExist:
                pass

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class PatientMoveLog(TimeStampedModel, UserTrackingMixin):
    """Audit trail for SUPERADMIN patient-move operations (Story 2.6 / FR55)."""

    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='move_logs',
        db_index=True,
    )
    from_institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        related_name='moves_out',
        db_index=True,
    )
    to_institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        related_name='moves_in',
        db_index=True,
    )
    moved_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='patient_moves_executed',
    )
    notes = models.TextField(blank=True)

    def __str__(self):
        from_name = self.from_institution.name if self.from_institution else '?'
        to_name = self.to_institution.name if self.to_institution else '?'
        return f"Patient {self.patient_id} moved: {from_name} → {to_name}"

    class Meta:
        ordering = ['-created_at']


class InstitutionSwitchLog(TimeStampedModel, UserTrackingMixin):
    """
    Persistent audit trail for SUPERADMIN institution context switches.

    Inherits TimeStampedModel (created_at, updated_at) and UserTrackingMixin
    (added_by, last_edit_by) per mandatory model pattern in CLAUDE.md.
    `user` is the explicit actor field; `added_by` is auto-populated by
    UserActivityMiddleware and should match.

    `previous_institution_id` is intentionally an IntegerField (not a FK) so that
    the audit record survives institution deletion — SET_NULL would destroy the
    historical reference.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='institution_switch_logs'
    )
    institution = models.ForeignKey(
        'Institution', on_delete=models.SET_NULL,
        null=True, related_name='switch_logs'
    )
    # Intentional IntegerField (not FK): preserves the ID even if institution is deleted.
    previous_institution_id = models.IntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'created_at'])]

    def __str__(self):
        return f"{self.user} → Institution {self.institution_id} at {self.created_at}"
