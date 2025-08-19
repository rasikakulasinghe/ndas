from django import forms
from ndas.custom_codes.choice import POSSITION
from users.models import CustomUser
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, PasswordChangeForm

class CustomUserRegistrationForm(forms.ModelForm):
    profile_pic = forms.ImageField(required=False, label='Your Profile Picture : ')
    password1 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput(attrs={
            'class': "form-control",
            'type': 'password',
            'name': 'password',
            'placeholder': 'Password',
            'id' : "password1",
        }))
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput(attrs={
            'class': "form-control",
            'type': 'password',
            'name': 'password',
            'placeholder': 'Password',
            'id' : "password2",
        }))
    possition = forms.ChoiceField(choices=POSSITION, widget = forms.Select(attrs = {'class': 'form-control'}))
    
    class Meta:
        model = CustomUser
        fields = [
            'username', 'possition', 'first_name', 'last_name', 'email', 'password1',  'password2',
            'profile_pic', 'tp_mobile_1', 'tp_lan_1', 'tp_mobile_2', 'tp_lan_2', 'address_home', 'address_station',
            'date_joined', 'groups', 'user_permissions', 'other',
        ]
        
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'profile_pic': forms.TextInput(attrs={'class': 'form-control'}),
            'tp_mobile_1': forms.TextInput(attrs={'class': 'form-control'}),
            'tp_mobile_2': forms.TextInput(attrs={'class': 'form-control'}),
            'tp_lan_1': forms.TextInput(attrs={'class': 'form-control'}),
            'tp_lan_2': forms.TextInput(attrs={'class': 'form-control'}),
            'address_home': forms.Textarea(attrs={'class': 'form-control'}),
            'address_station': forms.Textarea(attrs={'class': 'form-control'}),
            'other': forms.Textarea(attrs={'class': 'form-control'}),
            'date_joined': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'},),
         }

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
