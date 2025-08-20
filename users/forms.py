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
