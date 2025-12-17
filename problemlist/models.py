from django.db import models
from django.conf import settings
from django.utils import timezone
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.choice import PROBLEM_STATUS, SEVERITY_CHOICES


class Problem(TimeStampedModel, UserTrackingMixin):
    """
    Patient problem tracking model for medical issues, conditions, and ongoing clinical concerns.

    Inherits TimeStampedModel (created_at, updated_at) and UserTrackingMixin (added_by, last_edit_by).
    User tracking is automatically handled by UserActivityMiddleware.
    """
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='problem_list',
        help_text="Patient associated with this problem"
    )
    name = models.CharField(
        max_length=255,
        help_text="Short clinical name (e.g., Bronchial Asthma)",
        db_index=True
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed clinical description"
    )
    date_of_onset = models.DateField(
        null=True,
        blank=True,
        help_text="Date when problem first started"
    )
    date_identified = models.DateField(
        default=timezone.now,
        help_text="Date problem was first documented",
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=PROBLEM_STATUS.choices,
        default=PROBLEM_STATUS.ACTIVE,
        db_index=True,
        help_text="Current status of the problem"
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES.choices,
        null=True,
        blank=True,
        help_text="Severity level of the problem"
    )
    date_resolved = models.DateField(
        null=True,
        blank=True,
        help_text="Date when problem was resolved (auto-populated when status changes to resolved)"
    )
    action_taken = models.TextField(
        blank=True,
        help_text="Summary of treatments, investigations, and referrals"
    )
    outcome = models.TextField(
        blank=True,
        help_text="Response to treatment / current outcome"
    )
    comments = models.TextField(
        blank=True,
        help_text="Additional clinical notes (optional)"
    )

    class Meta:
        ordering = ['-date_identified']
        verbose_name = "Patient Problem"
        verbose_name_plural = "Patient Problems"
        indexes = [
            models.Index(fields=['patient', 'status']),
        ]

    def __str__(self):
        return f"{self.patient.baby_name} - {self.name[:50]}"

    def get_status_badge_class(self):
        """Return Bootstrap badge class based on problem status"""
        badge_classes = {
            'active': 'warning',
            'chronic': 'info',
            'resolved': 'success',
            'inactive': 'secondary',
        }
        return badge_classes.get(self.status, 'secondary')

    def get_severity_badge_class(self):
        """Return Bootstrap badge class based on severity"""
        badge_classes = {
            'mild': 'success',
            'moderate': 'warning',
            'severe': 'danger',
            'life_threatening': 'dark',
        }
        return badge_classes.get(self.severity, 'secondary')


class ProblemAction(models.Model):
    """
    Audit log for actions performed on patient problems.

    Separate from the Problem.action_taken summary field, this model provides
    timestamped action tracking for clinical audit trail.
    """
    problem = models.ForeignKey(
        Problem,
        on_delete=models.CASCADE,
        related_name='actions',
        help_text="Problem this action relates to"
    )
    action = models.TextField(
        help_text="Description of action taken"
    )
    date = models.DateTimeField(
        default=timezone.now,
        help_text="When this action was performed"
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        help_text="User who performed this action"
    )

    class Meta:
        ordering = ['-date']
        verbose_name = "Problem Action"
        verbose_name_plural = "Problem Actions"

    def __str__(self):
        return f"{self.problem.name} - {self.action[:50]} ({self.date.strftime('%Y-%m-%d %H:%M')})"
