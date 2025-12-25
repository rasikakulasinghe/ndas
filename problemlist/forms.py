from django import forms
from django.utils import timezone
from problemlist.models import Problem, ProblemAction
from ndas.custom_codes.validators import sanitize_text_input


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

    def clean_name(self):
        """Sanitize problem name to prevent XSS attacks"""
        name = self.cleaned_data.get('name')
        return sanitize_text_input(name)

    def clean_description(self):
        """Sanitize description to prevent XSS attacks"""
        description = self.cleaned_data.get('description')
        return sanitize_text_input(description)

    def clean_action_taken(self):
        """Sanitize action_taken to prevent XSS attacks"""
        action_taken = self.cleaned_data.get('action_taken')
        return sanitize_text_input(action_taken)

    def clean_outcome(self):
        """Sanitize outcome to prevent XSS attacks"""
        outcome = self.cleaned_data.get('outcome')
        return sanitize_text_input(outcome)

    def clean_comments(self):
        """Sanitize comments to prevent XSS attacks"""
        comments = self.cleaned_data.get('comments')
        return sanitize_text_input(comments)

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

    def clean_action(self):
        """Sanitize action to prevent XSS attacks"""
        action = self.cleaned_data.get('action')
        return sanitize_text_input(action)
