from django import forms
from patients.models import Patient, GMAssessment, Bookmark, Attachment, Video, CDICRecord, HINEAssessment, DevelopmentalAssessment
from ndas.custom_codes.choice import MODE_OF_DELIVERY, GENDER, POG_DAYS, POG_WKS, APGAR, DX_CONCLUTION


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

    diagnosis_conclution = forms.ChoiceField(
        choices=DX_CONCLUTION, widget=forms.Select(attrs={"class": "form-control"})
    )

    class Meta:
        model = GMAssessment
        fields = [
            'date_of_assessment', 'diagnosis', 'diagnosis_other', 'diagnosis_conclution',
            'managment_plan', 'next_assessment_date', 'parant_informed',
        ]

        widgets = {
            "date_of_assessment": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"},),

            "is_assessment_completed": forms.CheckboxInput(attrs={"class": "big-checkbox", 'id': 'is_assessment_completed', 'onchange': 'toggleis_assessment_completed()'}),

            "diagnosis": forms.CheckboxSelectMultiple(attrs={"class": ""}),

            "diagnosis_other": forms.Textarea(attrs={"class": "form-control", "rows": "3"}),

            "managment_plan": forms.Textarea(attrs={"class": "form-control", "rows": "3"}),

            "next_assessment_date": forms.DateInput(attrs={"type": "date", "class": "form-control"},),

            "parant_informed": forms.CheckboxInput(attrs={"class": "big-checkbox"}),

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
    class Meta:
        model = Video
        fields = [
            'caption', 'video', 'recorded_on', 'description', 'recorded_on', 'recorded_on'
        ]

        widgets = {
            "caption": forms.TextInput(attrs={"class": "form-control", "placeholder": "Video title", 'id': 'file_title'}),
            "recorded_on": forms.DateInput(attrs={"type": "date", "class": "form-control", 'id': 'id_recorded_on'}),
            'video': forms.ClearableFileInput(attrs={'class': 'form-control-file', 'id': 'file-upload-input'}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": "Video Description", 'id': 'descreption'}),
        }


class CDICRecordForm(forms.ModelForm):
    class Meta:
        model = CDICRecord
        fields = [
            'assessment_date', 'assessment', 'assessment_done_by', 'today_interventions', 'next_appoinment_date',
            'next_appoinment_plan', 'is_discharged', 'dischaged_date', 'dishcharged_by', 'discharge_plan'
        ]

        widgets = {
            "assessment_date": forms.DateInput(attrs={"type": "date", "class": "form-control", 'id': 'assessment_date'}),
            "assessment": forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": "Type your current assessment of the patient", 'id': 'assessment'}),
            "assessment_done_by": forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": "Type name and possiton of the officer who assess the patient...", }),
            "is_assessment_completed": forms.CheckboxInput(attrs={"class": "big-checkbox", 'id': 'is_assessment_completed', 'onchange': 'toggleis_CDIC_assessment_completed()'}),
            'today_interventions': forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": "Mention the interventions underwent tody...", 'id': 'today_interventions'}),
            "next_appoinment_date": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control", 'id': 'next_appoinment_date'}),
            'next_appoinment_plan': forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": "Mention plan at next visit...", 'id': 'next_appoinment_plan'}),
            "is_discharged": forms.CheckboxInput(attrs={"class": "big-checkbox", 'id': 'is_discharged', 'onchange': 'toggleis_discharged_fromCDIC()'}),
            "dishcharged_by": forms.Textarea(attrs={"class": "form-control", "placeholder": "Mention officers name and possition who responsible to discharge the patient...", "rows": "3"}),
            "dischaged_date": forms.DateInput(attrs={"type": "date", "class": "form-control", 'id': 'dischaged_date'}),
            'discharge_plan': forms.Textarea(attrs={"class": "form-control", "rows": "3", "placeholder": "Disharge plan including refferals", 'id': 'discharge_plan'}),
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
