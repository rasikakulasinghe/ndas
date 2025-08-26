from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import logging
from .models import Video
from ndas.custom_codes.choice import QUALITY_CHOICES

logger = logging.getLogger(__name__)


class VideoForm(forms.ModelForm):
    """Enhanced form for creating and editing video records with full model support"""
    
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter a descriptive title for the video',
            'id': 'file_title'
        }),
        help_text='Descriptive title for the video (max 200 characters)'
    )
    
    original_video = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'custom-file-input',
            'accept': 'video/mp4,video/mov,video/avi,video/mkv,video/webm',
            'id': 'file-upload-input'
        }),
        help_text='Select the video file to upload (Max: 2GB)'
    )
    
    recorded_on = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
            'id': 'id_recorded_on'
        }),
        help_text='Date and time when the video was recorded',
        initial=timezone.now
    )
    
    description = forms.CharField(
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Detailed description of the video content, assessment notes, etc.',
            'id': 'description'
        }),
        help_text='Optional description (max 2000 characters)'
    )
    
    tags = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'assessment, movement, follow-up',
            'id': 'tags'
        }),
        help_text='Comma-separated tags for easy searching'
    )
    
    target_quality = forms.ChoiceField(
        choices=QUALITY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'target_quality'
        }),
        initial='medium',
        help_text='Desired compression quality for web playback'
    )
    
    access_level = forms.ChoiceField(
        choices=[
            ('restricted', 'Restricted'),
            ('internal', 'Internal Staff'),
            ('public', 'Public')
        ],
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'access_level'
        }),
        initial='restricted',
        help_text='Who can access this video'
    )
    
    is_sensitive = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'is_sensitive'
        }),
        help_text='Contains sensitive medical content'
    )
    
    class Meta:
        model = Video
        fields = [
            'title',
            'original_video',
            'recorded_on',
            'description',
            'tags',
            'target_quality',
            'access_level',
            'is_sensitive'
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
        """Enhanced video file validation"""
        video_file = self.cleaned_data.get('original_video')
        
        # Skip validation if no file provided and this is an edit form
        if not video_file and self.instance and self.instance.pk:
            return video_file
            
        if video_file:
            # Check file size (max 2GB for uploads)
            max_size = 2 * 1024 * 1024 * 1024  # 2GB in bytes
            if video_file.size > max_size:
                raise ValidationError(_('Video file size cannot exceed 2GB.'))
            
            # Check file extension
            allowed_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
            file_extension = video_file.name.lower().split('.')[-1]
            if f'.{file_extension}' not in allowed_extensions:
                raise ValidationError(_(
                    f'File type .{file_extension} is not supported. '
                    f'Allowed types: {", ".join(allowed_extensions)}'
                ))
            
            # Basic content type validation
            if not video_file.content_type or not video_file.content_type.startswith('video/'):
                logger.warning(f"File {video_file.name} has content type: {video_file.content_type}")
                # Don't fail validation, just log warning as some browsers don't set correct MIME types
        
        return video_file
    
    def clean_tags(self):
        """Clean and validate tags"""
        tags = self.cleaned_data.get('tags', '')
        if tags:
            # Clean up tags: remove extra spaces, convert to lowercase
            tag_list = [tag.strip().lower() for tag in tags.split(',') if tag.strip()]
            # Limit to 20 tags maximum
            if len(tag_list) > 20:
                raise ValidationError(_('Maximum 20 tags allowed.'))
            # Rejoin cleaned tags
            return ', '.join(tag_list)
        return tags
    
    def clean_description(self):
        """Clean description field"""
        description = self.cleaned_data.get('description', '')
        if description:
            description = description.strip()
            if len(description) > 2000:
                raise ValidationError(_('Description cannot exceed 2000 characters.'))
        return description

    def save(self, commit=True):
        """Override save to handle additional processing"""
        instance = super().save(commit=False)
        
        # Set file size if video file is present
        if self.cleaned_data.get('original_video'):
            instance.file_size = self.cleaned_data['original_video'].size
            
            # Extract file format from extension
            filename = self.cleaned_data['original_video'].name
            extension = filename.lower().split('.')[-1]
            format_mapping = {
                'mp4': 'MP4',
                'avi': 'AVI', 
                'mov': 'MOV',
                'mkv': 'MKV',
                'webm': 'WEBM',
                'wmv': 'WMV',
                'flv': 'FLV'
            }
            instance.format = format_mapping.get(extension, 'OTHER')
        
        if commit:
            instance.save()
            # Trigger processing for large files
            if instance.file_size and instance.file_size > 25 * 1024 * 1024:  # 25MB
                instance.start_video_processing()
        
        return instance
