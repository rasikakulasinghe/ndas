from django import forms
from patients.models import Patient, GMAssessment, Bookmark, Attachment, Video, CDICRecord, HINEAssessment, DevelopmentalAssessment
from ndas.custom_codes.choice import MODE_OF_DELIVERY, GENDER, POG_DAYS, POG_WKS, APGAR, DX_CONCLUTION
import re


class PatientForm(forms.ModelForm):
    gender = forms.ChoiceField(
        choices=GENDER, widget=forms.Select(attrs={"class": "form-control"})
    )
    mo_delivery = forms.ChoiceField(
        choices=MODE_OF_DELIVERY, widget=forms.Select(
            attrs={"class": "form-control"})
    )
    pog_wks = forms.ChoiceField(
        choices=POG_WKS, widget=forms.Select(attrs={"class": "form-control"}), initial='40'
    )
    pog_days = forms.ChoiceField(
        choices=POG_DAYS, widget=forms.Select(attrs={"class": "form-control"}), initial='0'
    )

    apgar_1 = forms.ChoiceField(
        choices=APGAR, widget=forms.Select(attrs={"class": "form-control"}), initial='10'
    )
    apgar_5 = forms.ChoiceField(
        choices=APGAR, widget=forms.Select(attrs={"class": "form-control"}), initial='10'
    )
    apgar_10 = forms.ChoiceField(
        choices=APGAR, widget=forms.Select(attrs={"class": "form-control"}), initial='10'
    )

    class Meta:
        model = Patient
        fields = [
            "bht",
            "nnc_no",
            "ptc_no",
            "pc_no",
            "pin",
            "disk_no",
            "baby_name",
            "mother_name",
            "gender",
            "dob_tob",
            "pog_wks",
            "pog_days",
            "mo_delivery",
            "apgar_1",
            "apgar_5",
            "apgar_10",
            "resuscitated",
            "resustn_note",
            "birth_weight",
            "length",
            "ofc",
            "address",
            "tp_mobile",
            "tp_lan",
            "moh_area",
            "phm_area",
            "problems",
            "indecation_for_gma",
            "antenatal_hx",
            "intranatal_hx",
            "postnatal_hx",
            "other_relavent_details",
        ]

        widgets = {
            "bht": forms.TextInput(
                attrs={"class": "form-control",
                       "placeholder": "Example : 123456"}
            ),
            "nnc_no": forms.TextInput(
                attrs={"class": "form-control",
                       "placeholder": "Example : NNC/123/2023"}
            ),
            "ptc_no": forms.TextInput(
                attrs={"class": "form-control",
                       "placeholder": "Example : PTC/123/2023"}
            ),
            "pc_no": forms.TextInput(
                attrs={"class": "form-control",
                       "placeholder": "Example : PC/123/2023"}
            ),
            "pin": forms.TextInput(
                attrs={"class": "form-control",
                       "placeholder": "Example : 0751245852"}
            ),
            "disk_no": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Example : 123"}
            ),
            "baby_name": forms.TextInput(
                attrs={"class": "form-control",
                       "placeholder": "Name of the baby"}
            ),
            "mother_name": forms.TextInput(
                attrs={"class": "form-control",
                       "placeholder": "Name of the mother"}
            ),
            "dob_tob": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"},
            ),
            "resuscitated": forms.CheckboxInput(attrs={"class": "big-checkbox", 'id': 'id_resuscitated', 'onchange': 'toggleresuscitated()'}),

            "resustn_note": forms.Textarea(attrs={"class": "form-control", "rows": "3"}),

            "birth_weight": forms.TextInput(
                attrs={"class": "form-control",
                       "placeholder": "In grams (g), Ex : 2500"}
            ),
            "length": forms.TextInput(
                attrs={"class": "form-control",
                       "placeholder": "In centimeters (Cm) Ex : 48"}
            ),
            "ofc": forms.TextInput(
                attrs={"class": "form-control",
                       "placeholder": "In centimeters (Cm) Ex : 32"}
            ),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": "3"}),
            "tp_mobile": forms.TextInput(attrs={"class": "form-control"}),
            "tp_lan": forms.TextInput(attrs={"class": "form-control"}),
            "moh_area": forms.TextInput(attrs={"class": "form-control"}),
            "phm_area": forms.TextInput(attrs={"class": "form-control"}),
            "problems": forms.Textarea(attrs={"class": "form-control", "rows": "3"}),
            "indecation_for_gma": forms.CheckboxSelectMultiple(attrs={"class": ""}),
            "antenatal_hx": forms.Textarea(
                attrs={"class": "form-control", "rows": "3"}
            ),
            "intranatal_hx": forms.Textarea(
                attrs={"class": "form-control", "rows": "3"}
            ),
            "postnatal_hx": forms.Textarea(
                attrs={"class": "form-control", "rows": "3"}
            ),
            "other_relavent_details": forms.Textarea(
                attrs={"class": "form-control", "rows": "3"}
            ),
        }


class GMAssessmentForm(forms.ModelForm):

    diagnosis_conclusion = forms.ChoiceField(
        choices=DX_CONCLUTION, widget=forms.Select(attrs={"class": "form-control"})
    )

    class Meta:
        model = GMAssessment
        fields = [
            'date_of_assessment', 'diagnosis', 'diagnosis_other', 'diagnosis_conclusion',
            'management_plan', 'next_assessment_date', 'parent_informed',
        ]

        widgets = {
            "date_of_assessment": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"},),

            "is_assessment_completed": forms.CheckboxInput(attrs={"class": "big-checkbox", 'id': 'is_assessment_completed', 'onchange': 'toggleis_assessment_completed()'}),

            "diagnosis": forms.CheckboxSelectMultiple(attrs={"class": ""}),

            "diagnosis_other": forms.Textarea(attrs={"class": "form-control", "rows": "3"}),

            "management_plan": forms.Textarea(attrs={"class": "form-control", "rows": "3"}),

            "next_assessment_date": forms.DateInput(attrs={"type": "date", "class": "form-control"},),

            "parent_informed": forms.CheckboxInput(attrs={"class": "big-checkbox"}),

            # "other_details": forms.Textarea(attrs={"class": "form-control", "rows": "3"}),

            # "is_discharged": forms.CheckboxInput(attrs={"class": "big-checkbox", 'id': 'is_discharged', 'onchange': 'toggleis_discharged()'}),

            # "discharg_on": forms.DateInput(attrs={"type": "date", "class": "form-control"},),

            # "discharg_plan": forms.Textarea(attrs={"class": "form-control", "rows": "3"}),
        }


class BookmarkForm(forms.ModelForm):
    class Meta:
        model = Bookmark
        fields = [
            'title', 'description'
        ]

        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control",
                       "placeholder": "Bookmark title"}
            ),

            "description": forms.Textarea(attrs={"class": "form-control", "rows": "3",
                                                 "placeholder": "Bookmark Description"}),

        }


class AttachmentkForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = [
            'title', 'attachment', 'description'
        ]

        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Attachment title", 'id': 'title_id'}),
            'attachment': forms.ClearableFileInput(attrs={'class': 'form-control-file', 'id': 'attachment_file_id'}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": "Attachment Description", 'id': 'discription_id'}),
        }


class VideoForm(forms.ModelForm):
    """Enhanced VideoForm with comprehensive validation and new fields"""
    
    class Meta:
        model = Video
        fields = [
            'title', 'original_video', 'recorded_on', 'description', 
            'tags', 'target_quality', 'is_sensitive', 'access_level'
        ]

        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control", 
                "placeholder": "Video title (e.g., BHT123_Assessment_20250821)", 
                'id': 'file_title',
                'maxlength': '200'
            }),
            "recorded_on": forms.DateTimeInput(attrs={
                "type": "datetime-local", 
                "class": "form-control", 
                'id': 'id_recorded_on'
            }),
            'original_video': forms.ClearableFileInput(attrs={
                'class': 'form-control-file', 
                'id': 'file-upload-input',
                'accept': 'video/mp4,video/mov,video/avi,video/mkv,video/webm'
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control", 
                "rows": "4", 
                "placeholder": "Detailed description of the video content, assessment notes, etc.", 
                'id': 'description',
                'maxlength': '2000'
            }),
            "tags": forms.TextInput(attrs={
                "class": "form-control", 
                "placeholder": "Enter tags separated by commas (e.g., assessment, movement, follow-up)", 
                'id': 'tags',
                'maxlength': '500'
            }),
            "target_quality": forms.Select(attrs={
                "class": "form-control", 
                'id': 'target_quality'
            }),
            "is_sensitive": forms.CheckboxInput(attrs={
                "class": "form-check-input", 
                'id': 'is_sensitive'
            }),
            "access_level": forms.Select(attrs={
                "class": "form-control", 
                'id': 'access_level'
            }),
        }
        
        labels = {
            'title': 'Video Title',
            'original_video': 'Video File',
            'recorded_on': 'Recorded Date & Time',
            'description': 'Description',
            'tags': 'Tags',
            'target_quality': 'Compression Quality',
            'is_sensitive': 'Contains Sensitive Content',
            'access_level': 'Access Level',
        }
        
        help_texts = {
            'title': 'Provide a descriptive title (max 200 characters)',
            'original_video': 'Upload video file. Supported formats: MP4, MOV, AVI, MKV, WebM. Max size: 2GB',
            'recorded_on': 'When was this video recorded?',
            'description': 'Detailed description of the video content (max 2000 characters)',
            'tags': 'Comma-separated tags for easy searching and categorization',
            'target_quality': 'Choose compression quality for web playback',
            'is_sensitive': 'Check if video contains sensitive medical content',
            'access_level': 'Who can access this video',
        }

    def clean_title(self):
        """Validate title field"""
        title = self.cleaned_data.get('title')
        if not title:
            raise forms.ValidationError("Title is required.")
        
        # Check for inappropriate characters
        import re
        if not re.match(r'^[a-zA-Z0-9\s\-_\.]+$', title):
            raise forms.ValidationError(
                "Title can only contain letters, numbers, spaces, hyphens, underscores, and dots."
            )
        
        return title.strip()

    def clean_original_video(self):
        """Enhanced video file validation"""
        video = self.cleaned_data.get('original_video')
        if not video:
            return video
        
        # Import validation functions
        from ndas.custom_codes.validators import validate_video_file_upload
        
        is_valid, error_message = validate_video_file_upload(video)
        if not is_valid:
            raise forms.ValidationError(error_message)
        
        return video

    def clean_recorded_on(self):
        """Validate recording date"""
        recorded_on = self.cleaned_data.get('recorded_on')
        if not recorded_on:
            raise forms.ValidationError("Recording date and time is required.")
        
        from django.utils import timezone
        
        # Cannot be in the future
        if recorded_on > timezone.now():
            raise forms.ValidationError("Recording date cannot be in the future.")
        
        # Cannot be more than 10 years ago
        ten_years_ago = timezone.now() - timezone.timedelta(days=365 * 10)
        if recorded_on < ten_years_ago:
            raise forms.ValidationError("Recording date cannot be more than 10 years ago.")
        
        return recorded_on

    def clean_tags(self):
        """Validate and clean tags"""
        tags = self.cleaned_data.get('tags', '')
        if not tags:
            return ''
        
        # Split, clean, and rejoin tags
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        
        # Limit number of tags
        if len(tag_list) > 20:
            raise forms.ValidationError("Maximum 20 tags allowed.")
        
        # Validate individual tags
        for tag in tag_list:
            if len(tag) > 50:
                raise forms.ValidationError(f"Tag '{tag}' is too long. Maximum 50 characters per tag.")
            if not re.match(r'^[a-zA-Z0-9\s\-_]+$', tag):
                raise forms.ValidationError(f"Tag '{tag}' contains invalid characters.")
        
        return ', '.join(tag_list)

    def clean(self):
        """Form-level validation"""
        cleaned_data = super().clean()
        
        # Additional cross-field validation can be added here
        return cleaned_data


# Legacy VideoForm for backward compatibility  
class VideoFormLegacy(forms.ModelForm):
    """Legacy form for backward compatibility"""
    class Meta:
        model = Video
        fields = [
            'title', 'original_video', 'recorded_on', 'description'
        ]

        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Video title", 'id': 'file_title'}),
            "recorded_on": forms.DateInput(attrs={"type": "date", "class": "form-control", 'id': 'id_recorded_on'}),
            'original_video': forms.ClearableFileInput(attrs={'class': 'form-control-file', 'id': 'file-upload-input'}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": "Video Description", 'id': 'description'}),
        }
        
    # Map new field names to legacy names for compatibility
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Alias new fields to legacy names in the form
        if self.instance.pk:
            # Map title to caption for display
            self.fields['title'].initial = getattr(self.instance, 'title', getattr(self.instance, 'caption', ''))
            # Map original_video to video for display  
            self.fields['original_video'].initial = getattr(self.instance, 'original_video', getattr(self.instance, 'video', None))


class CDICRecordForm(forms.ModelForm):
    class Meta:
        model = CDICRecord
        fields = [
            'assessment_date', 'assessment', 'assessment_done_by', 'today_interventions', 'next_appointment_date',
            'next_appointment_plan', 'is_discharged', 'discharge_date', 'discharged_by', 'discharge_plan'
        ]

        widgets = {
            "assessment_date": forms.DateInput(attrs={"type": "date", "class": "form-control", 'id': 'assessment_date'}),
            "assessment": forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": "Type your current assessment of the patient", 'id': 'assessment'}),
            "assessment_done_by": forms.TextInput(attrs={"class": "form-control", "placeholder": "Name and position of the assessing officer", 'id': 'assessment_done_by'}),
            'today_interventions': forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": "Mention the interventions undertaken today...", 'id': 'today_interventions'}),
            "next_appointment_date": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control", 'id': 'next_appointment_date'}),
            'next_appointment_plan': forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": "Mention plan for next visit...", 'id': 'next_appointment_plan'}),
            "is_discharged": forms.CheckboxInput(attrs={"class": "big-checkbox", 'id': 'is_discharged', 'onchange': 'toggleis_discharged_fromCDIC()'}),
            "discharged_by": forms.TextInput(attrs={"class": "form-control", "placeholder": "Name and position of officer authorizing discharge", 'id': 'discharged_by'}),
            "discharge_date": forms.DateInput(attrs={"type": "date", "class": "form-control", 'id': 'discharge_date'}),
            'discharge_plan': forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": "Discharge plan including referrals", 'id': 'discharge_plan'}),
        }


class HINEAssessmentForm(forms.ModelForm):
    class Meta:
        model = HINEAssessment
        fields = ['date_of_assessment', 'score',
                  'assessment_done_by', 'comment']

        widgets = {
            "date_of_assessment": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control", 'id': 'assessment_date'}),
            "score": forms.NumberInput(attrs={"class": "form-control", "placeholder": "HINE Score", 'id': 'score'}),
            "assessment_done_by": forms.TextInput(attrs={"class": "form-control", "placeholder": "Type name and possiton of the officer who calculate the score...", }),
            'comment': forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": "Any other relevent infomations related to this assessment...", 'id': 'today_interventions'}),
        }


class DevelopmentalAssessmentForm(forms.ModelForm):
    class Meta:
        model = DevelopmentalAssessment
        fields = ['date_of_assessment', 'gm_age_from', 'gm_age_to', 'gm_details', 'fmv_age_from', 'fmv_age_to', 'fmv_details',
                  'hsl_age_from', 'hsl_age_to', 'hsl_details', 'seb_age_from', 'seb_age_to', 'seb_details', 'assessment_done_by', 'comment']

        widgets = {
            "date_of_assessment": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control", 'id': 'assessment_date'}),

            "gm_details": forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": ""}),
            "gm_age_from": forms.NumberInput(attrs={"class": "form-control"}),
            "gm_age_to": forms.NumberInput(attrs={"class": "form-control"}),

            "fmv_details": forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": ""}),
            "fmv_age_from": forms.NumberInput(attrs={"class": "form-control"}),
            "fmv_age_to": forms.NumberInput(attrs={"class": "form-control"}),

            "hsl_details": forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": ""}),
            "hsl_age_from": forms.NumberInput(attrs={"class": "form-control"}),
            "hsl_age_to": forms.NumberInput(attrs={"class": "form-control"}),

            "seb_details": forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": ""}),
            "seb_age_from": forms.NumberInput(attrs={"class": "form-control"}),
            "seb_age_to": forms.NumberInput(attrs={"class": "form-control"}),

            "assessment_done_by": forms.TextInput(attrs={"class": "form-control", "placeholder": "Type name and possiton of the officer who calculate the score...", }),
            "comment": forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": "Any other relevent infomations related to this assessment...", 'id': 'today_interventions'}),
        }
