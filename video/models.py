from django.db import models
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.validators import validate_video_file, validate_recording_date
from ndas.custom_codes.custom_methods import (
    get_video_path_file_name,
    get_compressed_video_path,
    get_video_thumbnail_path,
)
from ndas.custom_codes.choice import VIDEO_FORMATS, PROCESSING_STATUS, QUALITY_CHOICES
import json


class Video(TimeStampedModel, UserTrackingMixin):

    title = models.CharField(
        max_length=200,
        verbose_name=_("Video Title"),
        help_text=_("Descriptive title for the video (max 200 characters)"),
        validators=[
            RegexValidator(
                regex=r"^[a-zA-Z0-9\s\-_\.]+$",
                message=_(
                    "Title can only contain letters, numbers, spaces, hyphens, underscores, and dots."
                ),
            )
        ],
    )

    # Patient relationship
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="videos",
        verbose_name=_("Patient"),
        help_text=_("Patient associated with this video"),
    )

    # File fields
    original_video = models.FileField(
        upload_to=get_video_path_file_name,
        verbose_name=_("Original Video File"),
        help_text=_("Original uploaded video file"),
        validators=[validate_video_file],
    )

    compressed_video = models.FileField(
        upload_to=get_compressed_video_path,
        blank=True,
        null=True,
        verbose_name=_("Compressed Video"),
        help_text=_("Compressed version of the video for web playback"),
    )

    thumbnail = models.ImageField(
        upload_to=get_video_thumbnail_path,
        blank=True,
        null=True,
        verbose_name=_("Video Thumbnail"),
        help_text=_("Auto-generated thumbnail from video"),
    )

    recorded_on = models.DateTimeField(
        verbose_name=_("Recorded On"),
        help_text=_("Date and time when the video was recorded"),
        validators=[validate_recording_date],
    )

    # Processing status
    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS,
        default="pending",
        verbose_name=_("Processing Status"),
        help_text=_("Current processing status of the video"),
    )

    target_quality = models.CharField(
        max_length=20,
        choices=QUALITY_CHOICES,
        default="medium",
        verbose_name=_("Target Quality"),
        help_text=_("Desired compression quality"),
    )

    processing_started_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Processing Started"),
        help_text=_("When video processing began"),
    )

    processing_completed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Processing Completed"),
        help_text=_("When video processing completed"),
    )

    processing_error = models.TextField(
        blank=True,
        verbose_name=_("Processing Error"),
        help_text=_("Error message if processing failed"),
    )

    # Celery task tracking
    task_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Celery Task ID"),
        help_text=_("Celery task ID for video processing"),
    )

    retry_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Retry Count"),
        help_text=_("Number of processing retries"),
    )

    # Video metadata
    duration_seconds = models.FloatField(
        blank=True,
        null=True,
        verbose_name=_("Duration (seconds)"),
        help_text=_("Video duration in seconds"),
    )

    original_resolution = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("Original Resolution"),
        help_text=_("Original video resolution (e.g., 1920x1080)"),
    )

    original_codec = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Original Codec"),
        help_text=_("Original video codec"),
    )

    original_bitrate = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Original Bitrate"),
        help_text=_("Original video bitrate in kbps"),
    )

    file_size = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("File Size"),
        help_text=_("File size in bytes"),
    )

    format = models.CharField(
        max_length=10,
        choices=VIDEO_FORMATS,
        blank=True,
        verbose_name=_("Video Format"),
        help_text=_("Video file format"),
    )

    # Processing metrics
    processing_time_seconds = models.FloatField(
        blank=True,
        null=True,
        verbose_name=_("Processing Time"),
        help_text=_("Time taken to process video in seconds"),
    )

    compression_ratio = models.FloatField(
        blank=True,
        null=True,
        verbose_name=_("Compression Ratio"),
        help_text=_("Compression ratio achieved"),
    )

    progress_percentage = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Progress Percentage"),
        help_text=_("Processing progress percentage"),
    )

    # Processing configuration
    target_resolution = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("Target Resolution"),
        help_text=_("Target resolution for processing"),
    )

    target_bitrate = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Target Bitrate"),
        help_text=_("Target bitrate in kbps"),
    )

    processing_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Processing Metadata"),
        help_text=_("Additional processing metadata and logs"),
    )

    # Content fields
    description = models.TextField(
        blank=True,
        max_length=2000,
        verbose_name=_("Description"),
        help_text=_("Detailed description of the video content"),
    )

    class Meta:
        verbose_name = _("Video")
        verbose_name_plural = _("Videos")
        ordering = ["-created_at", "-recorded_on"]

    def __str__(self):
        return f"{self.title} - {self.patient.baby_name}"

    def save(self, *args, **kwargs):
        """Override save to handle metadata extraction and processing"""
        is_new = self.pk is None

        # Set file size if not already set
        if self.original_video and not self.file_size:
            self.file_size = self.original_video.size

        # Extract format from filename if not set
        if self.original_video and not self.format:
            import os

            ext = os.path.splitext(self.original_video.name)[1].lower().lstrip(".")
            if ext in dict(VIDEO_FORMATS):
                self.format = ext

        # Set processing status
        if is_new and self.original_video:
            self.processing_status = "pending"

        super().save(*args, **kwargs)

        # Trigger background processing for new videos
        if is_new and self.original_video:
            self.start_video_processing()

    def start_video_processing(self):
        """Start background video processing with Celery"""
        from django.utils import timezone
        from .tasks import process_video_task

        self.processing_status = "processing"
        self.processing_started_at = timezone.now()
        self.progress_percentage = 0
        self.save(
            update_fields=[
                "processing_status",
                "processing_started_at",
                "progress_percentage",
            ]
        )

        # Start Celery task
        task = process_video_task.delay(self.id)
        self.task_id = task.id
        self.save(update_fields=["task_id"])

    @property
    def file_size_mb(self):
        """Get file size in megabytes"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0

    @property
    def playback_url(self):
        """Get the best URL for video playback"""
        if self.compressed_video:
            return self.compressed_video.url
        return self.original_video.url if self.original_video else None

    @property
    def thumbnail_url(self):
        """Get thumbnail URL with fallback"""
        if self.thumbnail:
            return self.thumbnail.url
        return "/static/images/video-placeholder.jpg"

    @property
    def is_new_file(self):
        """Check if video has associated assessments"""
        return not hasattr(self, "gmassessment")

    @property
    def age_on_recording(self):
        """Get patient age when video was recorded"""
        if self.recorded_on and self.patient.dob:
            age_days = (self.recorded_on.date() - self.patient.dob).days
            return f"{age_days} days"
        return "Unknown"

    def get_task_status(self):
        """Get current Celery task status"""
        if not self.task_id:
            return None

        from celery import current_app

        result = current_app.AsyncResult(self.task_id)
        return {
            "status": result.status,
            "info": result.info if result.info else {},
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else False,
            "failed": result.failed() if result.ready() else False,
        }

    def cancel_processing(self):
        """Cancel video processing task"""
        if self.task_id:
            from celery import current_app

            current_app.control.revoke(self.task_id, terminate=True)
            self.processing_status = "failed"
            self.processing_error = "Processing cancelled by user"
            self.save(update_fields=["processing_status", "processing_error"])

    def update_processing_progress(self, percentage, metadata=None):
        """Update processing progress"""
        self.progress_percentage = min(100, max(0, percentage))
        if metadata:
            current_metadata = self.processing_metadata or {}
            current_metadata.update(metadata)
            self.processing_metadata = current_metadata
        self.save(update_fields=["progress_percentage", "processing_metadata"])

    def set_processing_complete(
        self, success=True, error_message=None, processing_time=None
    ):
        """Mark processing as complete"""
        from django.utils import timezone

        self.processing_completed_at = timezone.now()
        self.processing_status = "completed" if success else "failed"
        self.progress_percentage = 100 if success else self.progress_percentage

        if error_message:
            self.processing_error = error_message

        if processing_time:
            self.processing_time_seconds = processing_time

        if self.processing_started_at and self.processing_completed_at:
            total_time = (
                self.processing_completed_at - self.processing_started_at
            ).total_seconds()
            if not processing_time:
                self.processing_time_seconds = total_time

        self.save(
            update_fields=[
                "processing_completed_at",
                "processing_status",
                "progress_percentage",
                "processing_error",
                "processing_time_seconds",
            ]
        )

    @property
    def processing_duration_formatted(self):
        """Get formatted processing duration"""
        if self.processing_time_seconds:
            minutes, seconds = divmod(int(self.processing_time_seconds), 60)
            hours, minutes = divmod(minutes, 60)
            if hours:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return "Unknown"

    @property
    def video_duration_formatted(self):
        """Get formatted video duration"""
        if self.duration_seconds:
            minutes, seconds = divmod(int(self.duration_seconds), 60)
            hours, minutes = divmod(minutes, 60)
            if hours:
                return f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes}:{seconds:02d}"
        return "Unknown"

    # Legacy properties for backward compatibility
    @property
    def caption(self):
        """Legacy property mapping to title"""
        return self.title

    @property
    def video(self):
        """Legacy property mapping to original_video"""
        return self.original_video

    @property
    def getAgeOnRecord(self):
        """Legacy property for age calculation"""
        return self.age_on_recording
