import os
from datetime import timedelta
from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import format_html
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.validators import validate_video_file, validate_recording_date
        
from ndas.custom_codes.choice import PROCESSING_STATUS

class Video(TimeStampedModel, UserTrackingMixin):
    """
    Video model for storing patient video records with comprehensive metadata.
    
    This model stores video files associated with patients, including metadata
    such as duration, file size, and processing status. It includes methods
    for calculating patient age at recording time and checking file status.
    """

    video_file = models.FileField(
        upload_to="videos/%Y/%m/",  # Better organization by month
        verbose_name=_("Video File"),
        help_text=_("Upload the video file here"),
        validators=[validate_video_file],
        db_index=True,
    )

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
        db_index=True,  # Index for faster search
    )

    # Patient relationship
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="videos",  # Shorter, more intuitive name
        verbose_name=_("Patient"),
        help_text=_("Patient associated with this video"),
        db_index=True,
    )

    recorded_on = models.DateTimeField(
        verbose_name=_("Recorded On"),
        help_text=_("Date and time when the video was recorded"),
        validators=[validate_recording_date],
        db_index=True,  # Index for filtering/sorting
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Detailed description of the video content"),
    )
    
    # Video metadata fields
    duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Duration (seconds)"),
        help_text=_("Video duration in seconds"),
        validators=[MaxValueValidator(14400)],  # 4 hours max
    )
    
    file_size_bytes = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name=_("File Size (bytes)"),
        help_text=_("File size in bytes"),
    )
    

    
    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS,
        default='pending',
        verbose_name=_("Processing Status"),
        help_text=_("Current processing status of the video"),
        db_index=True,
    )
    
    # Quality/resolution metadata
    width = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Width"),
        help_text=_("Video width in pixels"),
    )
    
    height = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Height"),
        help_text=_("Video height in pixels"),
    )
    
    # Medical assessment flags
    is_assessment_ready = models.BooleanField(
        default=False,
        verbose_name=_("Assessment Ready"),
        help_text=_("Whether this video is ready for medical assessment"),
        db_index=True,
    )

    class Meta:
        verbose_name = _("Video")
        verbose_name_plural = _("Videos")
        ordering = ["-recorded_on", "-created_at"]  # Secondary sort by creation time
        
        # Composite indexes for common queries
        indexes = [
            models.Index(fields=['patient', '-recorded_on']),
            models.Index(fields=['processing_status', '-created_at']),
            models.Index(fields=['is_assessment_ready', '-recorded_on']),
        ]
        
        # Ensure no duplicate videos for same patient at same time
        constraints = [
            models.UniqueConstraint(
                fields=['patient', 'recorded_on', 'title'],
                name='unique_video_per_patient_time_title'
            ),
        ]

    def __str__(self):
        return f"{self.title} - {self.patient} ({self.recorded_on:%Y-%m-%d})"
    
    def get_absolute_url(self):
        """Get the canonical URL for this video."""
        # Assuming you have a video detail view
        return reverse('video:detail', kwargs={'pk': self.pk})
    
    def clean(self):
        """Custom model validation."""
        super().clean()
        
        # Validate recording date is not in future
        if self.recorded_on and hasattr(self.patient, 'dob_tob'):
            if self.recorded_on.date() < self.patient.dob_tob.date():
                raise ValidationError({
                    'recorded_on': _('Recording date cannot be before patient birth date.')
                })
    
    def save(self, *args, **kwargs):
        """Override save to populate metadata if missing."""
        # Auto-populate file size if not set
        if self.video_file and not self.file_size_bytes:
            try:
                self.file_size_bytes = self.video_file.size
            except (ValueError, OSError):
                pass
        
        # Validate before saving
        self.clean()
        super().save(*args, **kwargs)

    @property
    def age_on_recording(self):
        """Calculate patient's age at the time of recording."""
        if not hasattr(self.patient, 'dob_tob') or not self.recorded_on:
            return None
            
        return self._calculate_age_string(
            self.patient.dob_tob.date(), 
            self.recorded_on.date()
        )
    
    def _calculate_age_string(self, birth_date, recording_date):
        """Calculate age string in human-readable format."""
        if recording_date < birth_date:
            return "Invalid: Recording before birth"
            
        delta = recording_date - birth_date
        total_days = delta.days
        
        if total_days == 0:
            return "Same day as birth"
        elif total_days < 7:
            return f"{total_days} day{'s' if total_days != 1 else ''}"
        elif total_days < 30:
            weeks, days = divmod(total_days, 7)
            if days == 0:
                return f"{weeks} week{'s' if weeks != 1 else ''}"
            return f"{weeks} week{'s' if weeks != 1 else ''} and {days} day{'s' if days != 1 else ''}"
        elif total_days < 365:
            months, remaining_days = divmod(total_days, 30)
            weeks, days = divmod(remaining_days, 7)
            if weeks == 0 and days == 0:
                return f"{months} month{'s' if months != 1 else ''}"
            elif days == 0:
                return f"{months} month{'s' if months != 1 else ''} and {weeks} week{'s' if weeks != 1 else ''}"
            return f"{months} month{'s' if months != 1 else ''} and {days} day{'s' if days != 1 else ''}"
        else:
            years, remaining_days = divmod(total_days, 365)
            months, days = divmod(remaining_days, 30)
            if months == 0 and days == 0:
                return f"{years} year{'s' if years != 1 else ''}"
            elif days == 0:
                return f"{years} year{'s' if years != 1 else ''} and {months} month{'s' if months != 1 else ''}"
            return f"{years} year{'s' if years != 1 else ''} and {months} month{'s' if months != 1 else ''}"
    
    # Cached properties to avoid repeated database hits
    def is_new_file(self):
        """Check if this video has been used in any assessments."""
        from patients.models import GMAssessment
        return not GMAssessment.objects.filter(video_file=self).exists()
    
    def is_bookmarked(self):
        """Check if this video is bookmarked by any user."""
        from patients.models import Bookmark
        return Bookmark.objects.filter(
            bookmark_type="File", 
            object_id=self.pk
        ).exists()
    
    def get_bookmark(self):
        """Get the bookmark object if it exists."""
        from patients.models import Bookmark
        return Bookmark.objects.filter(
            bookmark_type="File", 
            object_id=self.pk
        ).first()
    
    # Utility methods
    @property
    def file_extension(self):
        """Get the file extension."""
        if self.video_file:
            return os.path.splitext(self.video_file.name)[1].lower()
        return ''
    
    @property
    def file_size_mb(self):
        """Get file size in MB."""
        if self.file_size_bytes:
            return round(self.file_size_bytes / (1024 * 1024), 2)
        return 0
    
    @property
    def duration_formatted(self):
        """Get formatted duration string (HH:MM:SS)."""
        if not self.duration_seconds:
            return "--:--:--"
        
        hours, remainder = divmod(self.duration_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    @property
    def resolution(self):
        """Get resolution string."""
        if self.width and self.height:
            return f"{self.width}×{self.height}"
        return "Unknown"
    
    def can_be_processed(self):
        """Check if video can be processed."""
        return (
            self.video_file and 
            self.processing_status in ['pending', 'failed']
        )
    
    def mark_processing_started(self):
        """Mark video as being processed."""
        self.processing_status = 'processing'
        self.save(update_fields=['processing_status', 'updated_at'])
    
    def mark_processing_completed(self, duration=None, width=None, height=None):
        """Mark video processing as completed with metadata."""
        self.processing_status = 'completed'
        self.is_assessment_ready = True
        
        if duration:
            self.duration_seconds = duration
        if width:
            self.width = width
        if height:
            self.height = height
            
        self.save(update_fields=[
            'processing_status', 'is_assessment_ready', 
            'duration_seconds', 'width', 'height', 'updated_at'
        ])
    
    def mark_processing_failed(self):
        """Mark video processing as failed."""
        self.processing_status = 'failed'
        self.is_assessment_ready = False
        self.save(update_fields=['processing_status', 'is_assessment_ready', 'updated_at'])
