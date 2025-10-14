import os
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import format_html
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.validators import validate_video_file, validate_recording_date
from ndas.custom_codes.custom_methods import calculate_age_string, extract_video_metadata, simple_video_duration_estimate
        
from ndas.custom_codes.choice import PROCESSING_STATUS

class Video(TimeStampedModel, UserTrackingMixin):

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

    resolution = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Video Resolution"),
        help_text=_("Video resolution (e.g., 1920x1080)"),
    )
    
    class Meta:
        verbose_name = _("Video")
        verbose_name_plural = _("Videos")
        ordering = ["-recorded_on", "-created_at"]  # Secondary sort by creation time
        
        # Composite indexes for common queries
        indexes = [
            models.Index(fields=['patient', '-recorded_on']),
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
        return reverse('video:detail', kwargs={'pk': self.pk})
    
    def clean(self):
        """Custom model validation."""
        super().clean()

        # Validate recording date is not in future - only if patient is already assigned
        # Use patient_id instead of patient to avoid RelatedObjectDoesNotExist error
        if self.recorded_on and self.patient_id:
            try:
                # Access patient only if we have a patient_id
                from patients.models import Patient
                patient = Patient.objects.get(pk=self.patient_id)

                if hasattr(patient, 'dob_tob') and patient.dob_tob:
                    if self.recorded_on.date() < patient.dob_tob.date():
                        raise ValidationError({
                            'recorded_on': _('Recording date cannot be before patient birth date.')
                        })
            except Patient.DoesNotExist:
                # Patient doesn't exist, skip validation
                pass
            except (AttributeError, ValueError):
                # Patient not fully loaded yet, skip this validation
                # It will be validated later when patient is assigned
                pass
    
    def save(self, *args, **kwargs):
        # Auto-populate file size if not set
        if self.video_file and not self.file_size_bytes:
            try:
                self.file_size_bytes = self.video_file.size
            except (ValueError, OSError):
                pass

        # Extract video metadata if video file is present and duration not set
        if self.video_file and not self.duration_seconds:
            try:
                # Get the file path - handle both uploaded files and existing files
                if hasattr(self.video_file, 'path'):
                    file_path = self.video_file.path
                elif hasattr(self.video_file, 'temporary_file_path'):
                    file_path = self.video_file.temporary_file_path()
                else:
                    # For uploaded files that haven't been saved yet
                    import tempfile
                    import os

                    # Create a temporary file to extract metadata
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as temp_file:
                        for chunk in self.video_file.chunks():
                            temp_file.write(chunk)
                        temp_file.flush()
                        file_path = temp_file.name

                    try:
                        metadata = extract_video_metadata(file_path)
                        if metadata:
                            if metadata.get('duration_seconds'):
                                self.duration_seconds = metadata['duration_seconds']
                            if metadata.get('resolution') and not self.resolution:
                                self.resolution = metadata['resolution']
                    finally:
                        # Clean up temporary file
                        try:
                            os.unlink(file_path)
                        except:
                            pass
                    file_path = None  # Skip the normal metadata extraction

                if file_path:
                    metadata = extract_video_metadata(file_path)
                    if metadata:
                        if metadata.get('duration_seconds'):
                            self.duration_seconds = metadata['duration_seconds']
                        if metadata.get('resolution') and not self.resolution:
                            self.resolution = metadata['resolution']
                    else:
                        # Try simple estimation as last resort
                        estimation = simple_video_duration_estimate(file_path)
                        if estimation and estimation.get('duration_seconds'):
                            self.duration_seconds = estimation['duration_seconds']

            except Exception as e:
                # Log the error but don't prevent saving
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to extract video metadata for {self.title}: {str(e)}")

                # Try simple estimation as absolute fallback
                try:
                    if hasattr(self.video_file, 'path'):
                        estimation = simple_video_duration_estimate(self.video_file.path)
                        if estimation and estimation.get('duration_seconds'):
                            self.duration_seconds = estimation['duration_seconds']
                except:
                    pass  # If estimation also fails, just continue without duration

        # Validate before saving
        self.clean()
        super().save(*args, **kwargs)

    @property
    def age_on_recording(self):
        if not hasattr(self.patient, 'dob_tob') or not self.recorded_on:
            return None
            
        return calculate_age_string(
            self.patient.dob_tob.date(), 
            self.recorded_on.date(),
            "medical"
        )
    
    # Cached properties to avoid repeated database hits
    def is_new_file(self):
        """Check if this video has been used in any assessments."""
        from patients.models import GMAssessment
        return not GMAssessment.objects.filter(video_file=self).exists()
    
    def is_bookmarked(self):
        """Check if this video is bookmarked by any user."""
        from patients.models import Bookmark
        return Bookmark.objects.filter(
            bookmark_type="Video",
            object_id=self.pk
        ).exists()

    def get_bookmark(self):
        """Get the bookmark object if it exists."""
        from patients.models import Bookmark
        return Bookmark.objects.filter(
            bookmark_type="Video",
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

    def get_resolution_display(self):
        return self.resolution or "Unknown"
    
    def video_count(self):
        return Video.objects.filter(patient=self.patient).count() or "Unknown"
    
    def age_string_recorded(self):
        """Get formatted age string for how long ago the video was recorded."""
        if not self.recorded_on:
            return "Unknown"
        
        return calculate_age_string(
            self.recorded_on.date(),
            timezone.now().date(),
            "simple"
        )
    
    def age_string_uploaded(self):
        """Get formatted age string for how long ago the video was uploaded."""
        if not self.created_at:
            return "Unknown"
        
        return calculate_age_string(
            self.created_at.date(),
            timezone.now().date(),
            "simple"
        )
