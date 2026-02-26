"""
institution/forms.py

Forms for institution management views.
Story 2.3 — Atomic Institution Onboarding.
Story 3.2 — Clinician Account Management.
"""
from django import forms
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from institution.models import Institution
from ndas.custom_codes.choice import Position, UserType
from ndas.custom_codes.validators import sanitize_text_input, image_extension_validation

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


class InstitutionClinicianForm(forms.ModelForm):
    """
    Form for institution admins to create new USER-type clinician accounts (Story 3.2 — FR57).

    Enforces user_type=USER — institution admins cannot create ADMIN or SUPERADMIN accounts.
    """
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        min_length=8,
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'position', 'mobile_primary']
        widgets = {
            'first_name':     forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':      forms.TextInput(attrs={'class': 'form-control'}),
            'username':       forms.TextInput(attrs={'class': 'form-control'}),
            'email':          forms.EmailInput(attrs={'class': 'form-control'}),
            'position':       forms.Select(attrs={'class': 'form-control'}),
            'mobile_primary': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1', '')
        p2 = self.cleaned_data.get('password2', '')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return p2

    def save(self, institution, commit=True):
        """
        Create and return a new USER-type clinician bound to the given institution.
        user_type is always forced to USER — never settable by form data (AC #3).
        """
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.user_type = UserType.USER  # AC #3: ALWAYS forced — never from form input
        user.institution = institution
        user.is_active = True
        if commit:
            user.save()
        return user


class InstitutionSettingsForm(forms.ModelForm):
    """
    Form for institution admin to update logo and display name (Story 3.3 — FR58).
    Slug is NOT editable (immutable after creation).
    """
    class Meta:
        model = Institution
        fields = ['name', 'logo']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo and hasattr(logo, 'size'):
            max_size = getattr(django_settings, 'FILE_UPLOAD_LIMITS', {}).get(
                'IMAGE_MAX_SIZE', 10 * 1024 * 1024
            )
            if logo.size > max_size:
                raise forms.ValidationError(
                    f"Logo file size must not exceed {max_size // (1024 * 1024)}MB."
                )
            try:
                image_extension_validation(logo)
            except Exception as e:
                raise forms.ValidationError(str(e))
        return logo
