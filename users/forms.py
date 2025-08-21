from django import forms
from ndas.custom_codes.choice import POSSITION
from users.models import CustomUser
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, PasswordChangeForm

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
        Validate that username is unique (excluding current user).
        """
        username = self.cleaned_data.get('username')
        if username:
            # Check if another user already has this username
            existing_user = CustomUser.objects.filter(username=username).exclude(pk=self.instance.pk)
            if existing_user.exists():
                raise forms.ValidationError("A user with this username already exists.")
        return username


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
            'is_active', 'is_staff', 'is_superuser', 'additional_notes'
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
            'is_superuser': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
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
            'is_active', 'is_staff', 'is_superuser', 'is_email_verified',
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
            'is_superuser': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
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
