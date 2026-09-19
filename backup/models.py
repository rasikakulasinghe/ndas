from django.core.validators import MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.choice import BackupJobType, BackupJobStatus, BackupJobScopeType


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
        help_text=_(
            "Single institution this job is scoped to when scope_type=single. "
            "Null when scope_type=multi (see `scopes` instead) or scope_type=system "
            "(unfiltered, system-wide)."
        ),
    )

    scope_type = models.CharField(
        max_length=10,
        choices=BackupJobScopeType.choices,
        default=BackupJobScopeType.SINGLE,
        db_index=True,
        verbose_name=_("Scope Type"),
        help_text=_(
            "Story 1.2: whether this job covers a single institution (`scope`), an "
            "explicit multi-institution subset (`scopes`), or the whole system "
            "(both empty)."
        ),
    )

    scopes = models.ManyToManyField(
        "institution.Institution",
        blank=True,
        related_name="backup_jobs_multi",
        verbose_name=_("Scopes"),
        help_text=_(
            "Explicit institution subset for scope_type=multi. Unused (empty) for "
            "single/system jobs."
        ),
    )

    archive_checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        verbose_name=_("Archive Checksum"),
        help_text=_(
            "Story 1.3: whole-archive SHA-256, computed by hashing the finished "
            ".zip file on disk after it is closed. Empty until the job completes."
        ),
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
