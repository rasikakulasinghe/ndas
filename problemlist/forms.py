from django import forms
from django.utils import timezone
from problemlist.models import Problem, ProblemAction


class ProblemForm(forms.ModelForm):
    """
    Form for creating and editing patient problems.

    Includes validation for dates and auto-population of date_resolved
    based on status changes.
    """
    class Meta:
        model = Problem
        fields = [
            "name",
            "description",
            "date_of_onset",
            "date_identified",
            "status",
            "severity",
            "date_resolved",
            "action_taken",
            "outcome",
            "comments",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g., Bronchial Asthma",
                "required": True,
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Detailed clinical description of the problem"
            }),
            "date_of_onset": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date"
            }),
            "date_identified": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date"
            }),
            "status": forms.Select(attrs={
                "class": "form-control"
            }),
            "severity": forms.Select(attrs={
                "class": "form-control"
            }),
            "date_resolved": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date"
            }),
            "action_taken": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Treatment, investigations, referrals, etc."
            }),
            "outcome": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Response to treatment / current outcome"
            }),
            "comments": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Additional clinical notes (optional)"
            }),
        }

    def clean(self):
        """
        Custom validation for problem form.

        - Auto-populates date_resolved when status is 'resolved'
        - Clears date_resolved if status is not 'resolved'
        - Validates date_of_onset is not in the future
        - Validates date_identified is not in the future
        """
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        date_resolved = cleaned_data.get('date_resolved')
        date_of_onset = cleaned_data.get('date_of_onset')
        date_identified = cleaned_data.get('date_identified')

        # Auto-populate date_resolved if status is 'resolved' and date_resolved is empty
        if status == 'resolved' and not date_resolved:
            cleaned_data['date_resolved'] = timezone.now().date()

        # Clear date_resolved if status is not 'resolved'
        if status != 'resolved':
            cleaned_data['date_resolved'] = None

        # Validate date_of_onset is not in the future
        if date_of_onset and date_of_onset > timezone.now().date():
            raise forms.ValidationError({
                'date_of_onset': 'Date of onset cannot be in the future.'
            })

        # Validate date_identified is not in the future
        if date_identified and date_identified > timezone.now().date():
            raise forms.ValidationError({
                'date_identified': 'Date identified cannot be in the future.'
            })

        # Validate date_resolved is not in the future
        if date_resolved and date_resolved > timezone.now().date():
            raise forms.ValidationError({
                'date_resolved': 'Date resolved cannot be in the future.'
            })

        return cleaned_data


class ProblemActionForm(forms.ModelForm):
    """
    Form for adding action log entries to a problem.

    Used for the audit trail of actions taken on a problem.
    """
    class Meta:
        model = ProblemAction
        fields = ["action"]
        widgets = {
            "action": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Describe the action taken",
                "required": True,
            }),
        }
