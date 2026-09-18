from django.core.validators import MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.choice import BackupJobType, BackupJobStatus


class BackupJob(TimeStampedModel, UserTrackingMixin):
    """
    Tracks a single backup (or, in Epic 2, restore/pre-restore-snapshot) job.

    Story 1.1 only creates `job_type=backup` rows and drives them through
    pending -> running -> completed|failed. `restore` / `pre_restore_snapshot`
    values are reserved for Epic 2.

    `triggered_by` is set explicitly by the trigger view (mirrors the manual
    `added_by=request.user` pattern used elsewhere) rather than relying on
    UserActivityMiddleware, because the job is later mutated by a detached
    subprocess with no authenticated request in flight.
    """

    job_type = models.CharField(
        max_length=25,
        choices=BackupJobType.choices,
        default=BackupJobType.BACKUP,
        db_index=True,
        verbose_name=_("Job Type"),
        help_text=_("Kind of job this record tracks."),
    )

    status = models.CharField(
        max_length=10,
        choices=BackupJobStatus.choices,
        default=BackupJobStatus.PENDING,
        db_index=True,
        verbose_name=_("Status"),
        help_text=_("Current lifecycle state of the job."),
    )

    progress_pct = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(100)],
        verbose_name=_("Progress %"),
        help_text=_("Approximate completion percentage (0-100)."),
    )

    error_message = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Error Message"),
        help_text=_("Populated when status=failed."),
    )

    triggered_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backup_jobs_triggered",
        verbose_name=_("Triggered By"),
        help_text=_("User who triggered this job (set explicitly, not via middleware)."),
    )

    scope = models.ForeignKey(
        "institution.Institution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backup_jobs",
        verbose_name=_("Scope"),
        help_text=_("Institution this job is scoped to. Null = system-wide (Epic 1.2)."),
    )

    class Meta:
        verbose_name = _("Backup Job")
        verbose_name_plural = _("Backup Jobs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["scope", "status"], name="backup_scope_status_idx"),
        ]

    def __str__(self):
        return f"BackupJob[{self.pk}] {self.job_type}/{self.status}"
