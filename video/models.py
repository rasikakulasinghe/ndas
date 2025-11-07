import os
import logging
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

logger = logging.getLogger(__name__)


class VideoQuerySet(models.QuerySet):
    """Custom queryset for Video model with performance optimizations"""

    def with_assessment_status(self):
        """Annotate videos with assessment status to avoid N+1 queries"""
        from patients.models import GMAssessment
        return self.annotate(
            is_assessed=models.Exists(
                GMAssessment.objects.filter(video_file=models.OuterRef('pk'))
            )
        )

    def with_bookmark_status(self, user):
        """Annotate videos with bookmark status for specific user"""
        from patients.models import Bookmark
        return self.annotate(
            user_bookmarked=models.Exists(
                Bookmark.objects.filter(
                    bookmark_type="Video",
                    object_id=models.OuterRef('pk'),
                    added_by=user
                )
            )
        )

    def new_videos_only(self):
        """Return only videos not used in assessments"""
        from patients.models import GMAssessment
        assessed_video_ids = GMAssessment.objects.values_list('video_file_id', flat=True)
        return self.exclude(id__in=assessed_video_ids)

    def assessed_videos_only(self):
        """Return only videos used in assessments"""
        from patients.models import GMAssessment
        assessed_video_ids = GMAssessment.objects.values_list('video_file_id', flat=True)
        return self.filter(id__in=assessed_video_ids)


class VideoManager(models.Manager):
    """Custom manager for Video model"""

    def get_queryset(self):
        return VideoQuerySet(self.model, using=self._db)

    def with_assessment_status(self):
        return self.get_queryset().with_assessment_status()

    def with_bookmark_status(self, user):
        return self.get_queryset().with_bookmark_status(user)

    def new_videos_only(self):
        return self.get_queryset().new_videos_only()

    def assessed_videos_only(self):
        return self.get_queryset().assessed_videos_only()


class Video(TimeStampedModel, UserTrackingMixin):

    objects = VideoManager()

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

        # FIX 3.2: Enhanced indexes for common queries
        indexes = [
            models.Index(fields=['patient', '-recorded_on']),
            models.Index(fields=['processing_status'], name='video_processing_status_idx'),
            models.Index(fields=['patient', 'processing_status'], name='video_patient_status_idx'),
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
        # FIX 1.3: Validate patient exists before any processing
        if self.patient_id and not getattr(self, '_patient_validated', False):
            try:
                from patients.models import Patient
                Patient.objects.get(pk=self.patient_id)
                self._patient_validated = True
            except Patient.DoesNotExist:
                raise ValidationError({'patient': _('Selected patient does not exist.')})

        # FIX 1.4: Auto-populate file size if not set
        if self.video_file and not self.file_size_bytes:
            try:
                self.file_size_bytes = self.video_file.size
            except (ValueError, OSError) as e:
                logger.warning(
                    f"Failed to get file size for video {self.title}: {e}",
                    extra={'video_title': self.title}
                )

        # FIX 1.2 & 3.4: Extract video metadata with better exception handling and logging
        if self.video_file and not self.duration_seconds:
            try:
                file_path = self._get_video_file_path()

                if file_path:
                    metadata = extract_video_metadata(file_path)
                    if metadata:
                        self._apply_video_metadata(metadata)
                        logger.info(
                            f"Video metadata extracted successfully",
                            extra={
                                'video_title': self.title,
                                'duration': self.duration_seconds,
                                'resolution': self.resolution,
                                'file_size': self.file_size_bytes
                            }
                        )
                    else:
                        # Try simple estimation as fallback
                        self._try_estimate_metadata(file_path)

            except (IOError, OSError) as e:
                logger.warning(
                    f"I/O error during video metadata extraction for {self.title}: {e}",
                    extra={'video_title': self.title, 'error_type': 'IOError'}
                )
                self._try_fallback_estimation()

            except (AttributeError, ValueError, TypeError) as e:
                logger.warning(
                    f"Data error during video metadata extraction for {self.title}: {e}",
                    extra={'video_title': self.title, 'error_type': type(e).__name__}
                )
                self._try_fallback_estimation()

            except Exception as e:
                logger.error(
                    f"Unexpected error during video metadata extraction",
                    extra={
                        'video_title': self.title,
                        'error': str(e),
                        'error_type': type(e).__name__
                    },
                    exc_info=True
                )
                self._try_fallback_estimation()

        # Validate before saving
        self.clean()
        super().save(*args, **kwargs)

    def _get_video_file_path(self):
        """Helper method to get video file path for metadata extraction"""
        if hasattr(self.video_file, 'path'):
            return self.video_file.path
        elif hasattr(self.video_file, 'temporary_file_path'):
            return self.video_file.temporary_file_path()
        else:
            # For uploaded files that haven't been saved yet
            return self._create_temp_file_for_metadata()

    def _create_temp_file_for_metadata(self):
        """Create temporary file for metadata extraction from uploaded file"""
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as temp_file:
            for chunk in self.video_file.chunks():
                temp_file.write(chunk)
            temp_file.flush()
            file_path = temp_file.name

        try:
            metadata = extract_video_metadata(file_path)
            if metadata:
                self._apply_video_metadata(metadata)
        finally:
            # Clean up temporary file
            try:
                os.unlink(file_path)
            except (OSError, IOError, PermissionError) as e:
                logger.warning(f"Failed to delete temporary file {file_path}: {e}")

        return None  # Skip normal metadata extraction

    def _apply_video_metadata(self, metadata):
        """Apply extracted metadata to video instance"""
        if metadata.get('duration_seconds'):
            self.duration_seconds = metadata['duration_seconds']
        if metadata.get('resolution') and not self.resolution:
            self.resolution = metadata['resolution']

    def _try_estimate_metadata(self, file_path):
        """Try simple estimation as fallback"""
        try:
            estimation = simple_video_duration_estimate(file_path)
            if estimation and estimation.get('duration_seconds'):
                self.duration_seconds = estimation['duration_seconds']
                logger.info(
                    f"Video duration estimated for {self.title}",
                    extra={'video_title': self.title, 'duration': self.duration_seconds}
                )
        except (IOError, OSError, ValueError) as e:
            logger.warning(f"Failed to estimate video duration for {self.title}: {e}")

    def _try_fallback_estimation(self):
        """Try estimation as absolute fallback"""
        try:
            if hasattr(self.video_file, 'path'):
                self._try_estimate_metadata(self.video_file.path)
        except Exception as e:
            logger.debug(f"Fallback estimation also failed for {self.title}: {e}")
            # Continue without duration - not critical for saving

    @property
    def age_on_recording(self):
        if not hasattr(self.patient, 'dob_tob') or not self.recorded_on:
            return None
            
        return calculate_age_string(
            self.patient.dob_tob.date(), 
            self.recorded_on.date(),
            "medical"
        )
    
    # FIX 1.1: Removed N+1 query methods - use annotations from VideoQuerySet instead
    # Use Video.objects.with_assessment_status() and check 'is_assessed' annotation
    # Use Video.objects.with_bookmark_status(user) and check 'user_bookmarked' annotation
    # These methods caused N+1 queries when iterating over video lists

    def get_bookmark_for_user(self, user):
        """
        Get the bookmark object for specific user if it exists.
        Note: This still performs a query, but it's explicit and only used
        in detail views, not list views.
        """
        from patients.models import Bookmark
        try:
            return Bookmark.objects.select_related("added_by").get(
                bookmark_type="Video",
                object_id=self.pk,
                added_by=user
            )
        except Bookmark.DoesNotExist:
            return None
    
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

    # FIX 1.4: Removed video_count() method - causes N+1 queries
    # Use patient.videos.count() or annotate Patient queryset with Count('videos')
    # in Patient model manager for better performance

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
