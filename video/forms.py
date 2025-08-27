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
            'placeholder': 'Enter a descriptive title for the video',
            'id': 'file_title'
        }),
        help_text='Descriptive title for the video (max 200 characters)'
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