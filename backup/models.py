from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.choice import (
    BackupJobType, BackupJobStatus, BackupJobScopeType,
    RestoreUploadStatus, RestoreAuthenticity, RestoreRejectionCode,
)


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

    trigger_institution = models.ForeignKey(
        "institution.Institution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backup_jobs_triggered_from",
        verbose_name=_("Trigger Institution"),
        help_text=_(
            "Story 1.5: the institution context the job was triggered from. Used as "
            "the delivery institution for the completion notification (a super "
            "admin's multi/system job has scope=null). Null on jobs that predate "
            "this field, which are never backfilled."
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

    date_filter_start = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Date Filter Start"),
        help_text=_(
            "Story 1.4: optional inclusive lower bound (on Patient.created_at's "
            "date) this job's export was narrowed to. Null when no date filter "
            "was applied -- including every Story 1.1-1.3 job, which predates "
            "this field and is never backfilled."
        ),
    )

    date_filter_end = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Date Filter End"),
        help_text=_(
            "Story 1.4: optional inclusive upper bound (on Patient.created_at's "
            "date) this job's export was narrowed to. Null when no date filter "
            "was applied."
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


class RestoreUpload(TimeStampedModel, UserTrackingMixin):
    """
    Story 2.1: one uploaded restore archive and the result of validating it.

    The archive is staged at BASE_DIR/restore_uploads/<id>/upload.zip and
    validated by the detached `manage.py validate_restore_upload <id>`
    command, which is the only writer of `status`/`progress_pct`/result
    fields after launch. Nothing about an upload touches any domain data.
    """

    uploaded_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="restore_uploads",
        verbose_name=_("Uploaded By"),
    )
    original_filename = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Original Filename"))
    size_bytes = models.PositiveBigIntegerField(default=0, verbose_name=_("Size (bytes)"))
    archive_sha256 = models.CharField(
        max_length=64, blank=True, default="", db_index=True,
        verbose_name=_("Archive SHA-256"),
        help_text=_("SHA-256 of the uploaded file, computed while it was streamed to disk."),
    )
    allow_unverified = models.BooleanField(
        default=False,
        verbose_name=_("Allow Unverified Origin"),
        help_text=_("Accept an archive whose originating backup job is unknown on this system."),
    )
    status = models.CharField(
        max_length=10,
        choices=RestoreUploadStatus.choices,
        default=RestoreUploadStatus.VALIDATING,
        db_index=True,
        verbose_name=_("Status"),
    )
    progress_pct = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(100)],
        verbose_name=_("Progress %"),
    )
    error_code = models.CharField(
        max_length=40,
        choices=RestoreRejectionCode.choices,
        blank=True,
        default="",
        verbose_name=_("Error Code"),
    )
    error_message = models.TextField(blank=True, default="", verbose_name=_("Error Message"))
    authenticity = models.CharField(
        max_length=10,
        choices=RestoreAuthenticity.choices,
        blank=True,
        default="",
        verbose_name=_("Authenticity"),
    )
    source_job_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Source Job ID"),
        help_text=_("`source_job_id` from the archive's manifest."),
    )
    manifest_summary = models.JSONField(
        null=True, blank=True, verbose_name=_("Manifest Summary"),
        help_text=_("Summary of the validated archive's manifest; set only when status=validated."),
    )

    class Meta:
        verbose_name = _("Restore Upload")
        verbose_name_plural = _("Restore Uploads")
        ordering = ["-created_at"]
        constraints = [
            # At most one `validating` upload per user, enforced by the DB so
            # two concurrent POSTs can't both pass the view's friendly check.
            models.UniqueConstraint(
                fields=["uploaded_by"],
                condition=Q(status="validating"),
                name="restore_one_validating_per_user",
            ),
        ]

    def __str__(self):
        return f"RestoreUpload[{self.pk}] {self.status}"
