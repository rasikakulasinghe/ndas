from django import forms
from ndas.custom_codes.choice import POSSITION, SUBSCRIPTION_TYPE_CHOICES, SUBSCRIPTION_STATUS_CHOICES
from users.models import CustomUser, Subscription
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, PasswordChangeForm
from datetime import date, timedelta
from ndas.custom_codes.sanitization import (
    sanitize_html,
    sanitize_plain_text,
)

class CustomUserRegistrationForm(forms.ModelForm):
    profile_picture = forms.ImageField(required=False, label='Your Profile Picture: ')
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={
            'class': "form-control",
            'type': 'password',
            'name': 'password',
            'placeholder': 'Password',
            'id': "password1",
        }))
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput(attrs={
            'class': "form-control",
            'type': 'password',
            'name': 'password',
            'placeholder': 'Confirm Password',
            'id': "password2",
        }))
    position = forms.ChoiceField(choices=POSSITION, widget=forms.Select(attrs={'class': 'form-control'}))
    
    class Meta:
        model = CustomUser
        fields = [
            'username', 'position', 'first_name', 'last_name', 'email', 'password1', 'password2',
            'profile_picture', 'mobile_primary', 'mobile_secondary', 
            'landline_primary', 'landline_secondary', 'home_address', 'station_address',
            'additional_notes',
        ]
        
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'mobile_primary': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1234567890'}),
            'mobile_secondary': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1234567890'}),
            'landline_primary': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1234567890'}),
            'landline_secondary': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1234567890'}),
            'home_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'station_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'additional_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def clean_username(self):
        """Sanitize username"""
        username = self.cleaned_data.get("username")
        if username:
            username = sanitize_plain_text(username, max_length=150)
        return username

    def clean_first_name(self):
        """Sanitize first name"""
        first_name = self.cleaned_data.get("first_name")
        if first_name:
            first_name = sanitize_plain_text(first_name, max_length=150)
        return first_name

    def clean_last_name(self):
        """Sanitize last name"""
        last_name = self.cleaned_data.get("last_name")
        if last_name:
            last_name = sanitize_plain_text(last_name, max_length=150)
        return last_name

    def clean_home_address(self):
        """Sanitize home address"""
        home_address = self.cleaned_data.get("home_address")
        if home_address:
            home_address = sanitize_plain_text(home_address)
        return home_address

    def clean_station_address(self):
        """Sanitize station address"""
        station_address = self.cleaned_data.get("station_address")
        if station_address:
            station_address = sanitize_plain_text(station_address)
        return station_address

    def clean_additional_notes(self):
        """Sanitize additional notes"""
        additional_notes = self.cleaned_data.get("additional_notes")
        if additional_notes:
            additional_notes = sanitize_plain_text(additional_notes)
        return additional_notes

    def clean_profile_picture(self):
        """Validate profile picture upload"""
        import os
        from PIL import Image

        profile_picture = self.cleaned_data.get('profile_picture')

        # Only validate if a new file is being uploaded
        # When editing without uploading a new file, this will skip validation
        if profile_picture and hasattr(profile_picture, 'read'):
            # Validate file size (5MB max)
            max_size = 5 * 1024 * 1024  # 5MB in bytes
            if profile_picture.size > max_size:
                raise forms.ValidationError(
                    f'Profile picture file size is {profile_picture.size / (1024 * 1024):.2f}MB. '
                    f'Maximum allowed size is 5MB.'
                )

            # Validate file extension
            allowed_extensions = ['.jpg', '.jpeg', '.png']
            ext = os.path.splitext(profile_picture.name)[1].lower()
            if ext not in allowed_extensions:
                raise forms.ValidationError(
                    f'Unsupported file extension: {ext}. '
                    f'Allowed extensions: JPG, JPEG, PNG'
                )

            # Validate actual image content using PIL
            try:
                image = Image.open(profile_picture)
                image.verify()  # Verify it's actually an image

                # Re-open for dimension check (verify() closes the file)
                profile_picture.seek(0)
                image = Image.open(profile_picture)
                width, height = image.size

                # Validate dimensions (4000x4000 max)
                max_dimension = 4000
                if width > max_dimension or height > max_dimension:
                    raise forms.ValidationError(
                        f'Image dimensions ({width}x{height}) exceed maximum allowed size of {max_dimension}x{max_dimension} pixels.'
                    )

                # Reset file pointer for subsequent processing
                profile_picture.seek(0)

            except (IOError, SyntaxError) as e:
                raise forms.ValidationError(
                    'Invalid image file. Please upload a valid JPG, JPEG, or PNG image.'
                )

        return profile_picture

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class CustomUserEditForm(forms.ModelForm):
    """
    Form for editing user profiles without password fields.
    Password changes should be handled separately.
    """
    profile_picture = forms.ImageField(
        required=False, 
        label='Profile Picture',
        help_text='Supported formats: JPG, JPEG, PNG. Max size: 5MB'
    )
    position = forms.ChoiceField(
        choices=POSSITION, 
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = CustomUser
        fields = [
            'username', 'position', 'first_name', 'last_name', 'email',
            'profile_picture', 'mobile_primary', 'mobile_secondary', 
            'landline_primary', 'landline_secondary', 'home_address', 'station_address',
            'additional_notes',
        ]
        
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': 'readonly',  # Username should not be editable
            }),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'required': True}),
            'mobile_primary': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '+1234567890',
                'required': True
            }),
            'mobile_secondary': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '+1234567890'
            }),
            'landline_primary': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '+1234567890'
            }),
            'landline_secondary': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '+1234567890'
            }),
            'home_address': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': 'Enter your home address'
            }),
            'station_address': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': 'Enter your work station address'
            }),
            'additional_notes': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': 'Any additional notes or information'
            }),
        }
        
        labels = {
            'mobile_primary': 'Primary Mobile *',
            'mobile_secondary': 'Secondary Mobile',
            'landline_primary': 'Primary Landline',
            'landline_secondary': 'Secondary Landline',
            'home_address': 'Home Address',
            'station_address': 'Station Address',
            'additional_notes': 'Additional Notes',
        }

    def clean_email(self):
        """
        Validate that email is unique (excluding current user).
        """
        email = self.cleaned_data.get('email')
        if email:
            # Check if another user already has this email
            existing_user = CustomUser.objects.filter(email=email).exclude(pk=self.instance.pk)
            if existing_user.exists():
                raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_username(self):
        """
        Validate that username is unique (excluding current user) and sanitize.
        """
        username = self.cleaned_data.get('username')
        if username:
            # Sanitize username
            username = sanitize_plain_text(username, max_length=150)

            # Check if another user already has this username
            existing_user = CustomUser.objects.filter(username=username).exclude(pk=self.instance.pk)
            if existing_user.exists():
                raise forms.ValidationError("A user with this username already exists.")
        return username

    def clean_first_name(self):
        """Sanitize first name"""
        first_name = self.cleaned_data.get("first_name")
        if first_name:
            first_name = sanitize_plain_text(first_name, max_length=150)
        return first_name

    def clean_last_name(self):
        """Sanitize last name"""
        last_name = self.cleaned_data.get("last_name")
        if last_name:
            last_name = sanitize_plain_text(last_name, max_length=150)
        return last_name

    def clean_home_address(self):
        """Sanitize home address"""
        home_address = self.cleaned_data.get("home_address")
        if home_address:
            home_address = sanitize_plain_text(home_address)
        return home_address

    def clean_station_address(self):
        """Sanitize station address"""
        station_address = self.cleaned_data.get("station_address")
        if station_address:
            station_address = sanitize_plain_text(station_address)
        return station_address

    def clean_additional_notes(self):
        """Sanitize additional notes"""
        additional_notes = self.cleaned_data.get("additional_notes")
        if additional_notes:
            additional_notes = sanitize_plain_text(additional_notes)
        return additional_notes

    def clean_profile_picture(self):
        """Validate profile picture upload"""
        import os
        from PIL import Image

        profile_picture = self.cleaned_data.get('profile_picture')

        # Only validate if a new file is being uploaded
        # When editing without uploading a new file, this will skip validation
        if profile_picture and hasattr(profile_picture, 'read'):
            # Validate file size (5MB max)
            max_size = 5 * 1024 * 1024  # 5MB in bytes
            if profile_picture.size > max_size:
                raise forms.ValidationError(
                    f'Profile picture file size is {profile_picture.size / (1024 * 1024):.2f}MB. '
                    f'Maximum allowed size is 5MB.'
                )

            # Validate file extension
            allowed_extensions = ['.jpg', '.jpeg', '.png']
            ext = os.path.splitext(profile_picture.name)[1].lower()
            if ext not in allowed_extensions:
                raise forms.ValidationError(
                    f'Unsupported file extension: {ext}. '
                    f'Allowed extensions: JPG, JPEG, PNG'
                )

            # Validate actual image content using PIL
            try:
                image = Image.open(profile_picture)
                image.verify()  # Verify it's actually an image

                # Re-open for dimension check (verify() closes the file)
                profile_picture.seek(0)
                image = Image.open(profile_picture)
                width, height = image.size

                # Validate dimensions (4000x4000 max)
                max_dimension = 4000
                if width > max_dimension or height > max_dimension:
                    raise forms.ValidationError(
                        f'Image dimensions ({width}x{height}) exceed maximum allowed size of {max_dimension}x{max_dimension} pixels.'
                    )

                # Reset file pointer for subsequent processing
                profile_picture.seek(0)

            except (IOError, SyntaxError) as e:
                raise forms.ValidationError(
                    'Invalid image file. Please upload a valid JPG, JPEG, or PNG image.'
                )

        return profile_picture


class UserPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super(UserPasswordResetForm, self).__init__(*args, **kwargs)

    email = forms.EmailField(label='', widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Your email address here...',
        'type': 'email',
        'name': 'email'
        }))

class UserPasswordResetConfirmForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super(UserPasswordResetConfirmForm, self).__init__(*args, **kwargs)

    new_password1 = forms.CharField(label='', widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'New password',
        'type': 'password',
        }))
    
    new_password2 = forms.CharField(label='', widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Re enter password',
        'type': 'password',
        }))

class UserPasswordChange(PasswordChangeForm):
    
    def __init__(self, *args, **kwargs):
        super(UserPasswordChange, self).__init__(*args, **kwargs)

    old_password = forms.CharField(label='', widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Your current password here',
        'type': 'password',
        }))
    
    new_password1 = forms.CharField(label='', widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Your new password here',
        'type': 'password',
        }))
    
    new_password2 = forms.CharField(label='', widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Re enter your new password here',
        'type': 'password',
        }))
    
    class Meta:
        model = CustomUser
        fields = ['new_password1', 'new_password2']


class AdminUserCreationForm(forms.ModelForm):
    """Admin form for creating new users with all fields."""
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Password must be at least 8 characters long."
    )
    password2 = forms.CharField(
        label='Password confirmation',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Enter the same password as before, for verification."
    )
    
    class Meta:
        model = CustomUser
        fields = [
            'username', 'first_name', 'last_name', 'email', 'position',
            'mobile_primary', 'mobile_secondary', 'landline_primary', 'landline_secondary',
            'home_address', 'station_address', 'profile_picture',
            'is_active', 'is_staff', 'additional_notes'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'position': forms.Select(attrs={'class': 'form-control'}),
            'mobile_primary': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile_secondary': forms.TextInput(attrs={'class': 'form-control'}),
            'landline_primary': forms.TextInput(attrs={'class': 'form-control'}),
            'landline_secondary': forms.TextInput(attrs={'class': 'form-control'}),
            'home_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'station_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'additional_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2
    
    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")
        if password1 and len(password1) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long")
        return password1
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class AdminUserEditForm(forms.ModelForm):
    """Admin form for editing existing users."""

    class Meta:
        model = CustomUser
        fields = [
            'username', 'first_name', 'last_name', 'email', 'position',
            'mobile_primary', 'mobile_secondary', 'landline_primary', 'landline_secondary',
            'home_address', 'station_address', 'profile_picture',
            'is_active', 'is_staff', 'is_email_verified',
            'additional_notes'
        ]
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': 'readonly'
            }),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'position': forms.Select(attrs={'class': 'form-control'}),
            'mobile_primary': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile_secondary': forms.TextInput(attrs={'class': 'form-control'}),
            'landline_primary': forms.TextInput(attrs={'class': 'form-control'}),
            'landline_secondary': forms.TextInput(attrs={'class': 'form-control'}),
            'home_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'station_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'additional_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_email_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class UserSearchForm(forms.Form):
    """Form for searching and filtering users."""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by username, name, or email...'
        })
    )
    position = forms.ChoiceField(
        required=False,
        choices=[('', 'All Positions')] + list(POSSITION),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_active = forms.ChoiceField(
        required=False,
        choices=[('', 'All Status'), ('true', 'Active'), ('false', 'Inactive')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_staff = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types'), ('true', 'Staff'), ('false', 'Regular Users')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class SubscriptionForm(forms.ModelForm):
    """
    Form for updating the global subscription.
    This form is used to modify the single subscription that applies to all non-superuser users.
    Includes validation for reasonable date ranges and positive numeric values.
    """

    class Meta:
        model = Subscription
        fields = [
            'subscription_type',
            'start_date',
            'duration_days',
            'billing_amount',
            'grace_period_days',
            'status',
            'notes',
        ]

        widgets = {
            'subscription_type': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'duration_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
            }),
            'billing_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
            }),
            'grace_period_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
            }),
        }
    
    def clean_duration_days(self):
        """Validate that duration_days is positive."""
        duration_days = self.cleaned_data.get('duration_days')
        if duration_days is not None and duration_days <= 0:
            raise forms.ValidationError('Duration must be greater than 0 days.')
        return duration_days
    
    def clean_billing_amount(self):
        """Validate that billing_amount is non-negative."""
        billing_amount = self.cleaned_data.get('billing_amount')
        if billing_amount is not None and billing_amount < 0:
            raise forms.ValidationError('Billing amount cannot be negative.')
        return billing_amount
    
    def clean_grace_period_days(self):
        """Validate that grace_period_days is non-negative."""
        grace_period_days = self.cleaned_data.get('grace_period_days')
        if grace_period_days is not None and grace_period_days < 0:
            raise forms.ValidationError('Grace period cannot be negative.')
        return grace_period_days
    
    def clean_start_date(self):
        """Validate that start_date is within a reasonable range."""
        start_date = self.cleaned_data.get('start_date')
        if start_date:
            # Check if start_date is not too far in the past (more than 10 years)
            ten_years_ago = date.today() - timedelta(days=365 * 10)
            if start_date < ten_years_ago:
                raise forms.ValidationError('Start date cannot be more than 10 years in the past.')
            
            # Check if start_date is not too far in the future (more than 1 year)
            one_year_from_now = date.today() + timedelta(days=365)
            if start_date > one_year_from_now:
                raise forms.ValidationError('Start date cannot be more than 1 year in the future.')
        
        return start_date
