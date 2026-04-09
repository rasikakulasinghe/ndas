import os
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import logging
from .models import Video
from ndas.custom_codes.choice import QUALITY_CHOICES
from ndas.custom_codes.sanitization import (
    sanitize_html,
    sanitize_plain_text,
    sanitize_filename,
)

logger = logging.getLogger(__name__)


class VideoForm(forms.ModelForm):
    
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter a descriptive title for the video (e.g., BHT-20240827-Assessment)',
            'autocomplete': 'off'
        }),
        help_text='Descriptive title for the video (max 200 characters)'
    )
    
    recorded_on = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        help_text='Date and time when the video was recorded',
        initial=timezone.now
    )
    
    description = forms.CharField(
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Optional: Add detailed description, assessment notes, or observations about this video...'
        }),
        help_text='Optional description (max 2000 characters)'
    )

    video_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'custom-file-input',
            'accept': 'video/mp4,video/avi,video/mov,video/wmv,video/mkv,video/webm'
        }),
        help_text='Upload video file (supported formats: MP4, AVI, MOV, MKV, WEBM - max 2 GB)',
        required=False  # Will be set to True in __init__ for new videos
    )

    class Meta:
        model = Video
        fields = ['title', 'video_file', 'recorded_on', 'description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default recorded_on to now if not editing existing record
        if not self.instance.pk:
            self.fields['recorded_on'].initial = timezone.now()
            # Require video file for new uploads
            self.fields['video_file'].required = True
        else:
            # Video file is optional when editing (only required if replacing)
            self.fields['video_file'].required = False

    def clean_video_file(self):
        video_file = self.cleaned_data.get('video_file')

        # Only validate if a new file is being uploaded (UploadedFile instance).
        # When editing without a new file, FileField.clean() returns False (required=False),
        # which save_form_data converts to "" — skip validation in that case.
        if video_file and isinstance(video_file, UploadedFile):
            # Sanitize the filename to prevent directory traversal and other attacks
            if hasattr(video_file, 'name'):
                video_file.name = sanitize_filename(video_file.name)

            # Check file size using centralized settings limit
            limits = getattr(settings, 'FILE_UPLOAD_LIMITS', {})
            max_size = limits.get('VIDEO_MAX_SIZE', 2 * 1024 * 1024 * 1024)
            max_size_mb = max_size // (1024 * 1024)
            if video_file.size > max_size:
                raise ValidationError(
                    _(f'Video file is too large. Maximum size allowed is {max_size_mb} MB.')
                )

            # Check file extension — must match settings.ALLOWED_FILE_EXTENSIONS['VIDEO']
            allowed_ext_dict = getattr(settings, 'ALLOWED_FILE_EXTENSIONS', {})
            allowed_extensions = allowed_ext_dict.get('VIDEO', ['.mp4', '.mov', '.avi', '.mkv', '.webm'])
            _, file_extension = os.path.splitext(video_file.name.lower())

            if file_extension not in allowed_extensions:
                raise ValidationError(
                    _('Unsupported file format. Allowed formats: MP4, AVI, MOV, WMV, MKV, WEBM')
                )

            # MIME type validation - verify file content matches video format
            try:
                import magic

                # Read first 2048 bytes for MIME detection
                video_file.seek(0)
                file_header = video_file.read(2048)
                video_file.seek(0)  # Reset file pointer

                # Detect MIME type from file content
                mime = magic.Magic(mime=True)
                detected_mime = mime.from_buffer(file_header)

                # Define allowed MIME types
                allowed_mimes = [
                    'video/mp4',
                    'video/x-m4v',           # MP4 variant
                    'video/quicktime',        # .mov
                    'video/x-msvideo',        # .avi
                    'video/avi',              # .avi variant
                    'video/x-matroska',       # .mkv
                    'video/webm',             # .webm
                    'video/x-ms-wmv',         # .wmv
                    'video/x-ms-asf',         # .wmv variant
                ]

                if detected_mime not in allowed_mimes:
                    logger.warning(
                        f"Video upload rejected - Invalid MIME type: {detected_mime} "
                        f"for file: {video_file.name}"
                    )
                    raise ValidationError(
                        _(f'Invalid video file. Detected file type: {detected_mime}. '
                          f'Please upload a valid video file (MP4, AVI, MOV, WMV, MKV, WEBM).')
                    )

                logger.info(
                    f"Video file validated - MIME type: {detected_mime}, "
                    f"Filename: {video_file.name}, Size: {video_file.size} bytes"
                )

            except ImportError:
                logger.error("python-magic library not installed. MIME type validation skipped.")
                # Continue without MIME validation if library not available
            except Exception as e:
                logger.error(f"Error during MIME type validation: {str(e)}")
                raise ValidationError(
                    _('Unable to validate video file. Please ensure you are uploading a valid video file.')
                )

        return video_file

    def clean_recorded_on(self):
        recorded_on = self.cleaned_data.get('recorded_on')
        
        if recorded_on:
            # Check if recorded date is not in the future
            if recorded_on > timezone.now():
                raise ValidationError(
                    _('Recording date cannot be in the future.')
                )
                
            # Check if recorded date is not too far in the past (10 years)
            ten_years_ago = timezone.now() - timezone.timedelta(days=3650)
            if recorded_on < ten_years_ago:
                raise ValidationError(
                    _('Recording date cannot be more than 10 years ago.')
                )
                
        return recorded_on

    def clean_title(self):
        title = self.cleaned_data.get('title')

        if title:
            # Sanitize to prevent XSS
            title = sanitize_plain_text(title, max_length=200)

            # Clean up the title
            title = title.strip()

            # Check for minimum length
            if len(title) < 3:
                raise ValidationError(
                    _('Title must be at least 3 characters long.')
                )

        return title

    def clean_description(self):
        """Sanitize video description"""
        description = self.cleaned_data.get('description')
        if description:
            # Sanitize HTML to prevent XSS while allowing safe formatting
            description = sanitize_html(description, strip=True)
        return description

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set processing status to pending if new video
        if not instance.pk:
            instance.processing_status = 'pending'
            
        if commit:
            instance.save()
            
        return instance