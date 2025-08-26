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
)
from ndas.custom_codes.choice import (
    MODE_OF_DELIVERY,
    GENDER,
    POG_DAYS,
    POG_WKS,
    APGAR,
    DX_CONCLUTION,
)


class PatientForm(forms.ModelForm):
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
            "problems",
            "indecation_for_gma",
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
                    "class": "big-checkbox",
                    "id": "id_resuscitated",
                    "onchange": "toggleresuscitated()",
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
                    "min": "300",
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
            "problems": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": "3",
                    "placeholder": "Current medical problems or concerns",
                }
            ),
            "indecation_for_gma": forms.CheckboxSelectMultiple(attrs={"class": ""}),
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
        """Validate BHT number"""
        bht = self.cleaned_data.get("bht")
        if bht:
            # Check if BHT already exists (excluding current instance during edit)
            queryset = Patient.objects.filter(bht=bht)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise ValidationError(
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
        """Validate NNC number"""
        nnc_no = self.cleaned_data.get("nnc_no")
        if nnc_no:
            # Check uniqueness
            queryset = Patient.objects.filter(nnc_no=nnc_no)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise ValidationError(
                    _("A patient with this NNC number already exists.")
                )

        return nnc_no

    def clean_pin(self):
        """Validate PIN number"""
        pin = self.cleaned_data.get("pin")
        if pin:
            # Check uniqueness
            queryset = Patient.objects.filter(pin=pin)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise ValidationError(_("A patient with this PIN already exists."))

        return pin

    def clean_baby_name(self):
        """Validate baby name"""
        baby_name = self.cleaned_data.get("baby_name")
        if baby_name:
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
        """Validate mother name"""
        mother_name = self.cleaned_data.get("mother_name")
        if mother_name:
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
        """Validate date and time of birth"""
        dob_tob = self.cleaned_data.get("dob_tob")
        if dob_tob:
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
            if birth_weight < 300 or birth_weight > 8000:
                raise ValidationError(_("Birth weight must be between 300g and 8000g."))

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

        return cleaned_data


class GMAssessmentForm(forms.ModelForm):

    diagnosis_conclusion = forms.ChoiceField(
        choices=DX_CONCLUTION, widget=forms.Select(attrs={"class": "form-control"})
    )

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
                    "onchange": "toggleis_assessment_completed()",
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


class CDICRecordForm(forms.ModelForm):
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
                    "onchange": "toggleis_discharged_fromCDIC()",
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


class HINEAssessmentForm(forms.ModelForm):
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


class DevelopmentalAssessmentForm(forms.ModelForm):
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
