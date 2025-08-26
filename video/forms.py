from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import Video
from ndas.custom_codes.choice import QUALITY_CHOICES


class VideoForm(forms.ModelForm):
    """Form for creating and editing video records"""
    
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter a descriptive title for the video'
        }),
        help_text='Descriptive title for the video (max 200 characters)'
    )
    
    original_video = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control-file',
            'accept': 'video/*'
        }),
        help_text='Select the video file to upload'
    )
    
    recorded_on = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        help_text='Date and time when the video was recorded',
        initial=timezone.now
    )
    
    target_quality = forms.ChoiceField(
        choices=QUALITY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        initial='medium',
        help_text='Desired compression quality for web playback'
    )
    
    class Meta:
        model = Video
        fields = [
            'title',
            'original_video',
            'recorded_on',
            'target_quality'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If this is an edit form (instance exists), make video file optional
        if self.instance and self.instance.pk:
            self.fields['original_video'].required = False
            self.fields['original_video'].help_text = 'Leave empty to keep current video file'
    
    def clean_title(self):
        """Validate video title"""
        title = self.cleaned_data.get('title')
        if title:
            # Additional validation can be added here
            title = title.strip()
            if len(title) < 3:
                raise ValidationError(_('Title must be at least 3 characters long.'))
        return title
    
    def clean_recorded_on(self):
        """Validate recording date"""
        recorded_on = self.cleaned_data.get('recorded_on')
        if recorded_on:
            # Don't allow future dates
            if recorded_on > timezone.now():
                raise ValidationError(_('Recording date cannot be in the future.'))
            
            # Don't allow dates too far in the past (more than 5 years)
            five_years_ago = timezone.now() - timezone.timedelta(days=5*365)
            if recorded_on < five_years_ago:
                raise ValidationError(_('Recording date cannot be more than 5 years ago.'))
        
        return recorded_on
    
    def clean_original_video(self):
        """Validate video file"""
        video_file = self.cleaned_data.get('original_video')
        
        # Skip validation if no file provided and this is an edit form
        if not video_file and self.instance and self.instance.pk:
            return video_file
            
        if video_file:
            # Check file size (max 500MB)
            max_size = 500 * 1024 * 1024  # 500MB in bytes
            if video_file.size > max_size:
                raise ValidationError(_('Video file size cannot exceed 500MB.'))
            
            # Check file extension
            allowed_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
            file_extension = video_file.name.lower().split('.')[-1]
            if f'.{file_extension}' not in allowed_extensions:
                raise ValidationError(_(
                    f'File type .{file_extension} is not supported. '
                    f'Allowed types: {", ".join(allowed_extensions)}'
                ))
        
        return video_file
