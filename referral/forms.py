"""
referral/forms.py

Referral system forms.
"""
from django import forms
from institution.models import Institution
from users.models import CustomUser
from ndas.custom_codes.choice import UserType


class ReferralInitiateForm(forms.Form):
    to_institution = forms.ModelChoiceField(
        queryset=Institution.objects.filter(is_active=True),
        label='Receiving Institution',
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label='— Select institution —',
    )
    to_clinician = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),  # Populated dynamically via HTMX
        label='Receiving Clinician',
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'clinician-select'}),
        empty_label='— Select clinician —',
    )
    initial_message = forms.CharField(
        label='Referral Message',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
    )

    def __init__(self, *args, sending_institution=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sending_institution = sending_institution

        # Exclude sending institution from choices (AC #5)
        if sending_institution:
            self.fields['to_institution'].queryset = (
                Institution.objects.filter(is_active=True)
                .exclude(pk=sending_institution.pk)
            )

        # If to_institution is in submitted data, populate to_clinician queryset
        if 'to_institution' in self.data:
            try:
                to_inst_id = int(self.data.get('to_institution'))
                self.fields['to_clinician'].queryset = CustomUser.objects.filter(
                    institution_id=to_inst_id,
                    is_active=True,
                    user_type=UserType.USER,
                )
            except (ValueError, TypeError):
                pass

    def clean(self):
        cleaned_data = super().clean()
        to_institution = cleaned_data.get('to_institution')
        to_clinician = cleaned_data.get('to_clinician')

        # AC #5: Self-institution referrals not permitted
        if to_institution and self.sending_institution:
            if to_institution.pk == self.sending_institution.pk:
                raise forms.ValidationError(
                    "You cannot refer to a clinician at your own institution. "
                    "Cross-institution referrals only."
                )

        # Ensure clinician belongs to selected to_institution
        if to_institution and to_clinician:
            if to_clinician.institution_id != to_institution.pk:
                raise forms.ValidationError(
                    "The selected clinician does not belong to the selected institution."
                )
        return cleaned_data


class ReferralReplyForm(forms.Form):
    body = forms.CharField(
        label='Clinical Opinion',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter your clinical opinion...',
        }),
        min_length=10,
    )

    def clean_body(self):
        from ndas.custom_codes.validators import sanitize_text_input
        body = self.cleaned_data.get('body', '')
        return sanitize_text_input(body)
