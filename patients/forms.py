from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import re
from patients.models import (
    Patient,
    GMAssessment,
    Bookmark,
    Attachment,
    CDICRecord,
    HINEAssessment,
    DevelopmentalAssessment,
    GeneralPaediatricAssessment,
)
from ndas.custom_codes.choice import (
    MODE_OF_DELIVERY,
    GENDER,
    POG_DAYS,
    POG_WKS,
    APGAR,
    DX_CONCLUTION,
)
from ndas.custom_codes.sanitization import (
    sanitize_html,
    sanitize_plain_text,
    sanitize_filename,
)


# FIX 2.1: Reusable validation mixin to eliminate code duplication
class UniqueFieldValidationMixin:
    """
    Mixin for validating unique fields in forms.
    Eliminates duplicate validation code across multiple forms.
    """

    def validate_unique_field(self, field_name, value, error_message):
        """
        Validate that a field value is unique in the database.

        Args:
            field_name: Name of the field to check
            value: Value to validate
            error_message: Error message to display if not unique

        Returns:
            The cleaned value

        Raises:
            ValidationError: If value is not unique
        """
        if not value:
            return value

        queryset = self.Meta.model.objects.filter(**{field_name: value})

        # Exclude current instance when editing
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise ValidationError(error_message)

        return value


# FIX 2.2: Timezone-aware datetime mixin
class TimezoneDateTimeMixin:
    """
    Mixin for handling timezone-aware datetime fields in forms.
    Automatically converts naive datetimes to timezone-aware.
    """

    def clean_datetime_field(self, field_name):
        """
        Clean and make timezone-aware a datetime field.

        Args:
            field_name: Name of the datetime field

        Returns:
            Timezone-aware datetime value
        """
        value = self.cleaned_data.get(field_name)

        if value and timezone.is_naive(value):
            value = timezone.make_aware(value)

        return value


class PatientForm(UniqueFieldValidationMixin, forms.ModelForm):
    gender = forms.ChoiceField(
        choices=GENDER, widget=forms.Select(attrs={"class": "form-control"})
    )
    mo_delivery = forms.ChoiceField(
        choices=MODE_OF_DELIVERY, widget=forms.Select(attrs={"class": "form-control"})
    )
    pog_wks = forms.ChoiceField(
        choices=POG_WKS,
        widget=forms.Select(attrs={"class": "form-control"}),
        initial="40",
    )
    pog_days = forms.ChoiceField(
        choices=POG_DAYS,
        widget=forms.Select(attrs={"class": "form-control"}),
        initial="0",
    )

    apgar_1 = forms.ChoiceField(
        choices=APGAR,
        widget=forms.Select(attrs={"class": "form-control"}),
        initial="10",
    )
    apgar_5 = forms.ChoiceField(
        choices=APGAR,
        widget=forms.Select(attrs={"class": "form-control"}),
        initial="10",
    )
    apgar_10 = forms.ChoiceField(
        choices=APGAR,
        widget=forms.Select(attrs={"class": "form-control"}),
        initial="10",
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
            "indecation_for_gma",
            "indecation_for_gma_other",
            "antenatal_hx",
            "intranatal_hx",
            "postnatal_hx",
            "other_relavent_details",
        ]

        widgets = {
            "bht": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example : 123456",
                    "required": True,
                    "maxlength": "20",
                }
            ),
            "nnc_no": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example : NNC/123/2023",
                    "maxlength": "20",
                }
            ),
            "ptc_no": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example : PTC/123/2023",
                    "maxlength": "20",
                }
            ),
            "pc_no": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example : PC/123/2023",
                    "maxlength": "20",
                }
            ),
            "pin": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example : 0751245852",
                    "maxlength": "20",
                }
            ),
            "disk_no": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example : 123",
                    "maxlength": "20",
                }
            ),
            "baby_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Name of the baby",
                    "required": True,
                    "maxlength": "100",
                }
            ),
            "mother_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Name of the mother",
                    "required": True,
                    "maxlength": "100",
                }
            ),
            "dob_tob": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": "form-control",
                    "required": True,
                },
            ),
            "resuscitated": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
            "resustn_note": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Detailed notes about resuscitation procedures if applicable",
                }
            ),
            "birth_weight": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "In grams (g), Ex : 2500",
                    "min": "200",
                    "max": "8000",
                    "required": True,
                }
            ),
            "length": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "In centimeters (Cm) Ex : 48",
                    "min": "20",
                    "max": "70",
                }
            ),
            "ofc": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "In centimeters (Cm) Ex : 32",
                    "min": "20",
                    "max": "50",
                    "required": True,
                }
            ),
            "address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Complete residential address",
                }
            ),
            "tp_mobile": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Primary mobile number (e.g., +94712345678)",
                    "pattern": r"^\+?1?\d{9,15}$",
                    "title": "Phone number must be entered in format: '+999999999'. Up to 15 digits allowed.",
                    "required": True,
                }
            ),
            "tp_lan": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Landline number (optional)",
                    "pattern": r"^\+?1?\d{9,15}$",
                    "title": "Phone number must be entered in format: '+999999999'. Up to 15 digits allowed.",
                }
            ),
            "moh_area": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Medical Officer of Health area",
                    "maxlength": "255",
                }
            ),
            "phm_area": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Public Health Midwife area",
                    "maxlength": "255",
                }
            ),
            "indecation_for_gma": forms.CheckboxSelectMultiple(attrs={"class": ""}),
            "indecation_for_gma_other": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Please specify other indication details",
                }
            ),
            "antenatal_hx": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Medical history during pregnancy",
                }
            ),
            "intranatal_hx": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Medical events during labor and delivery",
                }
            ),
            "postnatal_hx": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Medical events and care after birth",
                }
            ),
            "other_relavent_details": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Any other relevant medical information",
                }
            ),
        }

    def clean_bht(self):
        """Validate BHT number - FIX 2.1: Using validation mixin"""
        bht = self.cleaned_data.get("bht")
        if bht:
            # Validate uniqueness using mixin
            bht = self.validate_unique_field(
                'bht',
                bht,
                _("A patient with this BHT number already exists.")
            )

            # Additional BHT format validation
            if not re.match(r"^[A-Za-z0-9\-/]+$", bht):
                raise ValidationError(
                    _(
                        "BHT number can only contain letters, numbers, hyphens, and forward slashes."
                    )
                )

        return bht

    def clean_nnc_no(self):
        """Validate NNC number - FIX 2.1: Using validation mixin"""
        nnc_no = self.cleaned_data.get("nnc_no")
        if nnc_no:
            # Validate uniqueness using mixin
            nnc_no = self.validate_unique_field(
                'nnc_no',
                nnc_no,
                _("A patient with this NNC number already exists.")
            )

        return nnc_no

    def clean_pin(self):
        """Validate PIN number - FIX 2.1: Using validation mixin"""
        pin = self.cleaned_data.get("pin")
        if pin:
            # Validate uniqueness using mixin
            pin = self.validate_unique_field(
                'pin',
                pin,
                _("A patient with this PIN already exists.")
            )

        return pin

    def clean_baby_name(self):
        """Validate and sanitize baby name"""
        baby_name = self.cleaned_data.get("baby_name")
        if baby_name:
            # Sanitize input to prevent XSS
            baby_name = sanitize_plain_text(baby_name)

            # Remove extra whitespace and validate
            baby_name = " ".join(baby_name.split())
            if len(baby_name.strip()) < 2:
                raise ValidationError(
                    _("Baby name must be at least 2 characters long.")
                )

            # Check for valid characters (letters, spaces, hyphens, apostrophes)
            if not re.match(r"^[A-Za-z\s\-'\.]+$", baby_name):
                raise ValidationError(
                    _(
                        "Baby name can only contain letters, spaces, hyphens, apostrophes, and periods."
                    )
                )

        return baby_name

    def clean_mother_name(self):
        """Validate and sanitize mother name"""
        mother_name = self.cleaned_data.get("mother_name")
        if mother_name:
            # Sanitize input to prevent XSS
            mother_name = sanitize_plain_text(mother_name)

            # Remove extra whitespace and validate
            mother_name = " ".join(mother_name.split())
            if len(mother_name.strip()) < 2:
                raise ValidationError(
                    _("Mother name must be at least 2 characters long.")
                )

            # Check for valid characters
            if not re.match(r"^[A-Za-z\s\-'\.]+$", mother_name):
                raise ValidationError(
                    _(
                        "Mother name can only contain letters, spaces, hyphens, apostrophes, and periods."
                    )
                )

        return mother_name

    def clean_dob_tob(self):
        """Validate date and time of birth - FIX 2.2: Simplified timezone handling"""
        dob_tob = self.cleaned_data.get("dob_tob")
        if dob_tob:
            # Make datetime timezone-aware if it's naive (should be handled by Django settings)
            if timezone.is_naive(dob_tob):
                dob_tob = timezone.make_aware(dob_tob)

            # Check if date is not in the future
            if dob_tob > timezone.now():
                raise ValidationError(_("Date of birth cannot be in the future."))

            # Check if date is not too far in the past (reasonable limit: 10 years)
            ten_years_ago = timezone.now() - timezone.timedelta(days=365 * 10)
            if dob_tob < ten_years_ago:
                raise ValidationError(
                    _("Date of birth cannot be more than 10 years ago.")
                )

        return dob_tob

    def clean_birth_weight(self):
        """Validate birth weight"""
        birth_weight = self.cleaned_data.get("birth_weight")
        if birth_weight is not None:
            if birth_weight < 200 or birth_weight > 8000:
                raise ValidationError(_("Birth weight must be between 200g and 8000g."))

        return birth_weight

    def clean_length(self):
        """Validate length"""
        length = self.cleaned_data.get("length")
        if length is not None:
            if length < 20 or length > 70:
                raise ValidationError(_("Length must be between 20cm and 70cm."))

        return length

    def clean_ofc(self):
        """Validate OFC (Occipital Frontal Circumference)"""
        ofc = self.cleaned_data.get("ofc")
        if ofc is not None:
            if ofc < 20 or ofc > 50:
                raise ValidationError(_("OFC must be between 20cm and 50cm."))

        return ofc

    def clean_tp_mobile(self):
        """Validate mobile phone number"""
        tp_mobile = self.cleaned_data.get("tp_mobile")
        if tp_mobile:
            # Remove spaces and special characters for validation
            phone_digits = re.sub(r"[^\d+]", "", tp_mobile)

            # Validate format
            if not re.match(r"^\+?1?\d{9,15}$", phone_digits):
                raise ValidationError(
                    _(
                        "Phone number must be entered in format: '+999999999'. Up to 15 digits allowed."
                    )
                )

        return tp_mobile

    def clean_tp_lan(self):
        """Validate landline phone number"""
        tp_lan = self.cleaned_data.get("tp_lan")
        if tp_lan:
            # Remove spaces and special characters for validation
            phone_digits = re.sub(r"[^\d+]", "", tp_lan)

            # Validate format
            if not re.match(r"^\+?1?\d{9,15}$", phone_digits):
                raise ValidationError(
                    _(
                        "Phone number must be entered in format: '+999999999'. Up to 15 digits allowed."
                    )
                )

        return tp_lan

    def clean_resustn_note(self):
        """Sanitize resuscitation notes (allows safe HTML)"""
        resustn_note = self.cleaned_data.get("resustn_note")
        if resustn_note:
            # Sanitize HTML to prevent XSS while allowing safe formatting
            resustn_note = sanitize_html(resustn_note, strip=True)
        return resustn_note

    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()

        # Validate APGAR score progression (1min <= 5min <= 10min is not always true, but check for reasonable values)
        apgar_1 = cleaned_data.get("apgar_1")
        apgar_5 = cleaned_data.get("apgar_5")
        apgar_10 = cleaned_data.get("apgar_10")

        if all([apgar_1 is not None, apgar_5 is not None, apgar_10 is not None]):
            # Convert string values to integers for comparison
            try:
                apgar_scores = [
                    int(score)
                    for score in [apgar_1, apgar_5, apgar_10]
                    if score is not None and score != ""
                ]
                if any(score < 0 or score > 10 for score in apgar_scores):
                    raise ValidationError(
                        _("All APGAR scores must be between 0 and 10.")
                    )
            except (ValueError, TypeError):
                raise ValidationError(
                    _("All APGAR scores must be valid numbers between 0 and 10.")
                )

        # Validate POG (Period of Gestation)
        pog_wks = cleaned_data.get("pog_wks")
        pog_days = cleaned_data.get("pog_days")

        if pog_wks is not None and pog_wks != "":
            try:
                pog_wks_int = int(pog_wks)
                if pog_wks_int < 20 or pog_wks_int > 44:
                    raise ValidationError(
                        {
                            "pog_wks": _(
                                "Period of gestation must be between 20-44 weeks."
                            )
                        }
                    )
            except (ValueError, TypeError):
                raise ValidationError(
                    {"pog_wks": _("Period of gestation weeks must be a valid number.")}
                )

        if pog_days is not None and pog_days != "":
            try:
                pog_days_int = int(pog_days)
                if pog_days_int < 0 or pog_days_int > 6:
                    raise ValidationError(
                        {"pog_days": _("Period of gestation days must be between 0-6.")}
                    )
            except (ValueError, TypeError):
                raise ValidationError(
                    {"pog_days": _("Period of gestation days must be a valid number.")}
                )

        # Validate resuscitation note is provided if resuscitated is checked
        resuscitated = cleaned_data.get("resuscitated")
        resustn_note = cleaned_data.get("resustn_note")

        if resuscitated and not resustn_note:
            raise ValidationError(
                {
                    "resustn_note": _(
                        "Resuscitation note is required when baby was resuscitated."
                    )
                }
            )

        # Validate GMA other indication details if "Other" is selected
        indecation_for_gma = cleaned_data.get("indecation_for_gma")
        indecation_for_gma_other = cleaned_data.get("indecation_for_gma_other")

        if indecation_for_gma:
            # Check if "Other" indication (ID 27) is selected
            other_indication_ids = [indication.id for indication in indecation_for_gma if indication.id == 27]
            if other_indication_ids and not indecation_for_gma_other:
                raise ValidationError(
                    {
                        "indecation_for_gma_other": _(
                            "Please provide details when 'Other' GMA indication is selected."
                        )
                    }
                )

        return cleaned_data


class GMAssessmentForm(TimezoneDateTimeMixin, forms.ModelForm):

    diagnosis_conclusion = forms.ChoiceField(
        choices=DX_CONCLUTION, widget=forms.Select(attrs={"class": "form-control"})
    )

    def clean_date_of_assessment(self):
        """Validate and make timezone-aware the assessment date - FIX 2.2"""
        return self.clean_datetime_field("date_of_assessment")

    class Meta:
        model = GMAssessment
        fields = [
            "date_of_assessment",
            "diagnosis",
            "diagnosis_other",
            "diagnosis_conclusion",
            "management_plan",
            "next_assessment_date",
            "parent_informed",
        ]

        widgets = {
            "date_of_assessment": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"},
            ),
            "is_assessment_completed": forms.CheckboxInput(
                attrs={
                    "class": "big-checkbox",
                    "id": "is_assessment_completed",
                }
            ),
            "diagnosis": forms.CheckboxSelectMultiple(attrs={"class": ""}),
            "diagnosis_other": forms.Textarea(
                attrs={"class": "form-control", "rows": "3"}
            ),
            "management_plan": forms.Textarea(
                attrs={"class": "form-control", "rows": "3"}
            ),
            "next_assessment_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"},
            ),
            "parent_informed": forms.CheckboxInput(attrs={"class": "big-checkbox"}),
            # "other_details": forms.Textarea(attrs={"class": "form-control", "rows": "3"}),
            # "is_discharged": forms.CheckboxInput(attrs={"class": "big-checkbox", 'id': 'is_discharged', 'onchange': 'toggleis_discharged()'}),
            # "discharg_on": forms.DateInput(attrs={"type": "date", "class": "form-control"},),
            # "discharg_plan": forms.Textarea(attrs={"class": "form-control", "rows": "3"}),
        }


class BookmarkForm(forms.ModelForm):
    class Meta:
        model = Bookmark
        fields = ["title", "description"]

        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Bookmark title"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Bookmark Description",
                }
            ),
        }


class AttachmentkForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        """Make attachment field optional when editing existing records"""
        super().__init__(*args, **kwargs)
        # When editing (instance exists), make file upload optional
        if self.instance and self.instance.pk:
            self.fields['attachment'].required = False

    class Meta:
        model = Attachment
        fields = ["title", "attachment", "description"]

        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Attachment title",
                    "id": "title_id",
                }
            ),
            "attachment": forms.ClearableFileInput(
                attrs={"class": "form-control-file", "id": "attachment_file_id"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Attachment Description",
                    "id": "discription_id",
                }
            ),
        }

    def clean_title(self):
        """Sanitize attachment title"""
        title = self.cleaned_data.get("title")
        if title:
            # Sanitize to prevent XSS
            title = sanitize_plain_text(title, max_length=200)
        return title

    def clean_description(self):
        """Sanitize attachment description"""
        description = self.cleaned_data.get("description")
        if description:
            # Sanitize HTML to prevent XSS while allowing safe formatting
            description = sanitize_html(description, strip=True)
        return description

    def clean_attachment(self):
        """Sanitize uploaded filename and preserve existing file during edits"""
        attachment = self.cleaned_data.get("attachment")
        # Only sanitize if a new file is being uploaded
        # When editing without uploading a new file, this will return the existing file reference
        if attachment and hasattr(attachment, 'read'):
            # Sanitize the filename to prevent directory traversal and other attacks
            if hasattr(attachment, 'name'):
                attachment.name = sanitize_filename(attachment.name)
        elif not attachment and self.instance and self.instance.pk:
            # Preserve existing file when editing and no new file is provided
            return self.instance.attachment
        return attachment


class CDICRecordForm(TimezoneDateTimeMixin, forms.ModelForm):

    def clean_next_appointment_date(self):
        """Validate and make timezone-aware the next appointment date - FIX 2.2"""
        return self.clean_datetime_field("next_appointment_date")
    
    class Meta:
        model = CDICRecord
        fields = [
            "assessment_date",
            "assessment",
            "assessment_done_by",
            "today_interventions",
            "next_appointment_date",
            "next_appointment_plan",
            "is_discharged",
            "discharge_date",
            "discharged_by",
            "discharge_plan",
        ]

        widgets = {
            "assessment_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control", "id": "assessment_date"}
            ),
            "assessment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Type your current assessment of the patient",
                    "id": "assessment",
                }
            ),
            "assessment_done_by": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Name and position of the assessing officer",
                    "id": "assessment_done_by",
                }
            ),
            "today_interventions": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Mention the interventions undertaken today...",
                    "id": "today_interventions",
                }
            ),
            "next_appointment_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": "form-control",
                    "id": "next_appointment_date",
                }
            ),
            "next_appointment_plan": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Mention plan for next visit...",
                    "id": "next_appointment_plan",
                }
            ),
            "is_discharged": forms.CheckboxInput(
                attrs={
                    "class": "big-checkbox",
                    "id": "is_discharged",
                }
            ),
            "discharged_by": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Name and position of officer authorizing discharge",
                    "id": "discharged_by",
                }
            ),
            "discharge_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control", "id": "discharge_date"}
            ),
            "discharge_plan": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Discharge plan including referrals",
                    "id": "discharge_plan",
                }
            ),
        }


class HINEAssessmentForm(TimezoneDateTimeMixin, forms.ModelForm):

    def __init__(self, *args, **kwargs):
        """Initialize form with optional patient instance for validation"""
        self.patient = kwargs.pop('patient', None)
        super().__init__(*args, **kwargs)

    def clean_date_of_assessment(self):
        """Validate and make timezone-aware the assessment date - FIX 2.2"""
        date_of_assessment = self.clean_datetime_field("date_of_assessment")

        # Validate against patient's birth date if patient is provided
        if date_of_assessment and self.patient and self.patient.dob_tob:
            if date_of_assessment < self.patient.dob_tob:
                raise forms.ValidationError(
                    _("Assessment date cannot be before patient birth date.")
                )

        return date_of_assessment
    
    class Meta:
        model = HINEAssessment
        fields = ["date_of_assessment", "score", "assessment_done_by", "comment"]

        widgets = {
            "date_of_assessment": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": "form-control",
                    "id": "assessment_date",
                }
            ),
            "score": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "HINE Score",
                    "id": "score",
                }
            ),
            "assessment_done_by": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Type name and possiton of the officer who calculate the score...",
                }
            ),
            "comment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Any other relevent infomations related to this assessment...",
                    "id": "today_interventions",
                }
            ),
        }


class DevelopmentalAssessmentForm(TimezoneDateTimeMixin, forms.ModelForm):

    def __init__(self, *args, **kwargs):
        """Initialize form with optional patient instance for validation"""
        self.patient = kwargs.pop('patient', None)
        super().__init__(*args, **kwargs)

    def clean_date_of_assessment(self):
        """Validate and make timezone-aware the assessment date - FIX 2.2"""
        date_of_assessment = self.clean_datetime_field("date_of_assessment")

        # Validate against patient's birth date if patient is provided
        if date_of_assessment and self.patient and self.patient.dob_tob:
            if date_of_assessment < self.patient.dob_tob:
                raise forms.ValidationError(
                    _("Assessment date cannot be before patient birth date.")
                )

        return date_of_assessment
    
    class Meta:
        model = DevelopmentalAssessment
        fields = [
            "date_of_assessment",
            "gm_age_from",
            "gm_age_to",
            "gm_details",
            "fmv_age_from",
            "fmv_age_to",
            "fmv_details",
            "hsl_age_from",
            "hsl_age_to",
            "hsl_details",
            "seb_age_from",
            "seb_age_to",
            "seb_details",
            "assessment_done_by",
            "comment",
        ]

        widgets = {
            "date_of_assessment": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": "form-control",
                    "id": "assessment_date",
                }
            ),
            "gm_details": forms.Textarea(
                attrs={"class": "form-control", "rows": "3", "placeholder": ""}
            ),
            "gm_age_from": forms.NumberInput(attrs={"class": "form-control"}),
            "gm_age_to": forms.NumberInput(attrs={"class": "form-control"}),
            "fmv_details": forms.Textarea(
                attrs={"class": "form-control", "rows": "3", "placeholder": ""}
            ),
            "fmv_age_from": forms.NumberInput(attrs={"class": "form-control"}),
            "fmv_age_to": forms.NumberInput(attrs={"class": "form-control"}),
            "hsl_details": forms.Textarea(
                attrs={"class": "form-control", "rows": "3", "placeholder": ""}
            ),
            "hsl_age_from": forms.NumberInput(attrs={"class": "form-control"}),
            "hsl_age_to": forms.NumberInput(attrs={"class": "form-control"}),
            "seb_details": forms.Textarea(
                attrs={"class": "form-control", "rows": "3", "placeholder": ""}
            ),
            "seb_age_from": forms.NumberInput(attrs={"class": "form-control"}),
            "seb_age_to": forms.NumberInput(attrs={"class": "form-control"}),
            "assessment_done_by": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Type name and possiton of the officer who calculate the score...",
                }
            ),
            "comment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Any other relevent infomations related to this assessment...",
                    "id": "today_interventions",
                }
            ),
        }


class GeneralPaediatricAssessmentForm(TimezoneDateTimeMixin, forms.ModelForm):
    """
    Form for General Paediatric Assessment (GPA) records with comprehensive
    validation and Bootstrap styling.
    """

    def clean_next_assessment_date(self):
        """Validate and make timezone-aware the next assessment date - FIX 2.2"""
        return self.clean_datetime_field("next_assessment_date")

    def clean(self):
        """Form-level validation for discharge fields consistency"""
        cleaned_data = super().clean()
        is_discharged = cleaned_data.get("is_discharged")
        discharged_authorized_by = cleaned_data.get("discharged_authorized_by")
        discharge_plan = cleaned_data.get("discharge_plan")

        # If patient is marked as discharged, ensure discharge authorizer is provided
        if is_discharged and not discharged_authorized_by:
            raise ValidationError(
                {
                    "discharged_authorized_by": _(
                        "Discharge authorizer is required when patient is marked as discharged"
                    )
                }
            )

        return cleaned_data

    class Meta:
        model = GeneralPaediatricAssessment
        fields = [
            "assessment_date",
            "healthcare_provider",
            "current_problems",
            "physical_examination",
            "investigation_summary",
            "prescribed_medications",
            "next_plan",
            "next_assessment_date",
            "is_discharged",
            "discharged_authorized_by",
            "discharge_plan",
        ]

        widgets = {
            "assessment_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": "form-control",
                    "id": "assessment_date",
                    "required": True,
                }
            ),
            "healthcare_provider": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Name and designation of healthcare provider",
                    "id": "healthcare_provider",
                    "required": True,
                    "maxlength": "200",
                }
            ),
            "current_problems": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "4",
                    "placeholder": "Document current medical problems and presenting complaints...",
                    "id": "current_problems",
                    "required": True,
                }
            ),
            "physical_examination": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "4",
                    "placeholder": "Detail physical examination findings including vital signs, system examination...",
                    "id": "physical_examination",
                    "required": True,
                }
            ),
            "investigation_summary": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "4",
                    "placeholder": "Summarize investigations performed (blood tests, imaging, etc.) and results...",
                    "id": "investigation_summary",
                    "required": True,
                }
            ),
            "prescribed_medications": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "4",
                    "placeholder": "List prescribed medications with dosages, frequency, and duration...",
                    "id": "prescribed_medications",
                    "required": True,
                }
            ),
            "next_plan": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "4",
                    "placeholder": "Outline next steps, goals, planned interventions, and follow-up care...",
                    "id": "next_plan",
                    "required": True,
                }
            ),
            "next_assessment_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": "form-control",
                    "id": "next_assessment_date",
                }
            ),
            "is_discharged": forms.CheckboxInput(
                attrs={
                    "class": "big-checkbox",
                    "id": "is_discharged",
                }
            ),
            "discharged_authorized_by": forms.Select(
                attrs={
                    "class": "form-control",
                    "id": "discharged_authorized_by",
                }
            ),
            "discharge_plan": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "4",
                    "placeholder": "Discharge planning, follow-up instructions, and referrals...",
                    "id": "discharge_plan",
                }
            ),
        }
