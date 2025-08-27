from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import logging
from .models import Video
from ndas.custom_codes.choice import QUALITY_CHOICES

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
        help_text='Upload video file (supported formats: MP4, AVI, MOV, WMV, MKV, WEBM - max 500MB)',
        required=True
    )

    class Meta:
        model = Video
        fields = ['title', 'video_file', 'recorded_on', 'description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default recorded_on to now if not editing existing record
        if not self.instance.pk:
            self.fields['recorded_on'].initial = timezone.now()

    def clean_video_file(self):
        video_file = self.cleaned_data.get('video_file')
        
        if video_file:
            # Check file size (max 500MB)
            max_size = 500 * 1024 * 1024  # 500MB in bytes
            if video_file.size > max_size:
                raise ValidationError(
                    _('Video file is too large. Maximum size allowed is 500MB.')
                )
            
            # Check file extension
            allowed_extensions = ['.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm']
            file_extension = video_file.name.lower().split('.')[-1]
            
            if f'.{file_extension}' not in allowed_extensions:
                raise ValidationError(
                    _('Unsupported file format. Allowed formats: MP4, AVI, MOV, WMV, MKV, WEBM')
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
            # Clean up the title
            title = title.strip()
            
            # Check for minimum length
            if len(title) < 3:
                raise ValidationError(
                    _('Title must be at least 3 characters long.')
                )
                
        return title

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set processing status to pending if new video
        if not instance.pk:
            instance.processing_status = 'pending'
            
        if commit:
            instance.save()
            
        return instance