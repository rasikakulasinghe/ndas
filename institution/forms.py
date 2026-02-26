"""
institution/forms.py

Form for Story 2.3 — Atomic Institution Onboarding.
Validates both institution fields and the first admin account fields
before the view creates both records inside a single transaction.
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from institution.models import Institution
from ndas.custom_codes.choice import Position
from ndas.custom_codes.validators import sanitize_text_input

User = get_user_model()


class InstitutionOnboardingForm(forms.Form):
    # ── Institution fields ─────────────────────────────────────────────────
    institution_name = forms.CharField(
        max_length=255,
        label="Institution Name",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. City General Hospital',
            'id': 'id_institution_name',
        }),
    )
    institution_slug = forms.SlugField(
        max_length=100,
        label="Slug (URL identifier)",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. city-general',
            'id': 'id_institution_slug',
        }),
        help_text="Lowercase, hyphens only. Auto-populated from name. Immutable after creation.",
    )

    # ── First admin account fields ─────────────────────────────────────────
    admin_first_name = forms.CharField(
        max_length=150,
        label="Admin First Name",
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    admin_last_name = forms.CharField(
        max_length=150,
        label="Admin Last Name",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    admin_username = forms.CharField(
        max_length=150,
        label="Admin Username",
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    admin_email = forms.EmailField(
        label="Admin Email",
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )
    admin_mobile = forms.CharField(
        max_length=20,
        label="Admin Mobile",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+94 77 xxx xxxx'}),
    )
    admin_position = forms.ChoiceField(
        choices=Position.choices,
        label="Admin Position",
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    admin_password = forms.CharField(
        label="Admin Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=8,
    )
    admin_password_confirm = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    # ── Field-level validation ─────────────────────────────────────────────

    def clean_institution_name(self):
        name = sanitize_text_input(self.cleaned_data['institution_name'])
        if Institution.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("An institution with this name already exists.")
        return name

    def clean_admin_first_name(self):
        return sanitize_text_input(self.cleaned_data['admin_first_name'])

    def clean_institution_slug(self):
        slug = self.cleaned_data['institution_slug'].lower()
        if Institution.objects.filter(slug=slug).exists():
            raise forms.ValidationError(
                "This slug is already taken. Choose a unique identifier."
            )
        return slug

    def clean_admin_username(self):
        username = self.cleaned_data['admin_username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_admin_email(self):
        email = self.cleaned_data['admin_email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already registered.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('admin_password')
        confirm = cleaned_data.get('admin_password_confirm')
        if password and confirm and password != confirm:
            self.add_error('admin_password_confirm', "Passwords do not match.")
            return cleaned_data
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                self.add_error('admin_password', e)
        return cleaned_data
