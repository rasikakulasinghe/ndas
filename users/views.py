from django.shortcuts import render
from users.models import CustomUser
from django.contrib.auth import authenticate, login, logout
from ndas.custom_codes.custom_methods import getCurrentDateTime, getFullDeviceDetails
from django.contrib import messages
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from .forms import CustomUserRegistrationForm, UserPasswordChange
from .models import DevoloperContacts
from pathlib import os

# Create your views here.
def loginPage(request):
    loged_user = request.user
    if request.method == 'POST':
        user = CustomUser()
        username = request.POST['username']
        if CustomUser.objects.filter(username=username).exists():
            password = request.POST['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                user.last_login_device = getFullDeviceDetails(request)
                user.save(update_fields=["last_login_device"]) 
                
                messages.success(request, 'Your succusfully logedin!')
                return redirect('home')
            else:
                messages.error(request, 'Wrong password, You are not autherized to login...')
                return render(request, 'users/login.html', {'loged_user' : loged_user})
        else:
            messages.error(request, 'Wrong username, You are not autherized to login...')
            return render(request, 'users/login.html', {'loged_user' : loged_user})
    else:
        if request.user.is_authenticated:
            return redirect('home')
        else:
            return render(request, 'users/login.html', {'loged_user' : loged_user})

def logoutPage(request):
    logout(request)
    messages.success(request, 'Your loged out !')
    return redirect('user-login')

@login_required(login_url='user-login')
def userView(request, pk):
    custom_user = CustomUser.objects.get(id=pk)
    loged_user = request.user
    return render(request, 'users/user_view.html', {'custom_user': custom_user, 'user' : loged_user})

@login_required(login_url='user-login')
def userViewByUsername(request, username):
    custom_user = CustomUser.objects.get(username=username)
    return render(request, 'users/user_view.html', {'custom_user': custom_user,})

@login_required(login_url='user-login')
def userEdit(request, pk):
    selected_user = CustomUser.objects.get(id=pk)
    user_form = CustomUserRegistrationForm(instance=selected_user)
    
    if request.method == 'POST':
        user_form_modified = CustomUserRegistrationForm(request.POST, request.FILES, instance=selected_user)
        selected_user.possition = user_form_modified.data.get("possition")
        selected_user.tp_mobile_1 = user_form_modified.data.get("tp_mobile_1")
        selected_user.tp_mobile_2 = user_form_modified.data.get("tp_mobile_2")
        selected_user.tp_lan_1 = user_form_modified.data.get("tp_lan_1")
        selected_user.tp_lan_2 = user_form_modified.data.get("tp_lan_2")
        selected_user.address_home = user_form_modified.data.get("address_home")
        selected_user.address_station = user_form_modified.data.get("address_station")
        selected_user.other = user_form_modified.data.get("other")
        
        image_prop = request.FILES['profile_pic']
        
        try:
            selected_user.profile_pic = image_prop
        except Exception as e:
            messages.warning(request, e)
            
        selected_user.username = user_form_modified.data.get("username")
        selected_user.first_name = user_form_modified.data.get("first_name")
        selected_user.last_name = user_form_modified.data.get("last_name")
        selected_user.email = user_form_modified.data.get("email")
        # selected_user.is_active = True if user_form_modified.data.get("is_active") == 'on' else False
        
        selected_user.save(update_fields=['possition', 'tp_mobile_1', 'tp_mobile_2', 'tp_lan_1','tp_lan_2', 'address_home', 'address_station', 'other', 'profile_pic', 'username', 'first_name', 'last_name', 'email',])
        
        updated_user = CustomUser.objects.get(id=pk)
        
        messages.success( request, 'User details update succusfully...')
        
        return render(request, 'users/user_view.html', {'user': updated_user})
    else:
        return render(request, 'users/user_edit.html', {'form' : user_form})

# change the password
@login_required(login_url='user-login')
def userChangePassword(request):
    custom_user = request.user
    form = UserPasswordChange(custom_user, request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Your password has been changed")
            return render(request, 'users/user_view.html', {'custom_user': custom_user})
        else:
            messages.error(request, form.error_messages)
            # for error in form.error_messages:
            #     if form.error_messages:
            #         messages.error(request, form.error_messages[error])
            return render(request, 'users/user_change_password.html', {'custom_user': custom_user, 'form' : form})
    else:
        return render(request, 'users/user_change_password.html', {'custom_user': custom_user, 'form' : form})

# Go to the developer contact page
def developerContacts(request):
    loged_user = request.user
    developer = DevoloperContacts.objects.get(id=1)
    var = getFullDeviceDetails(request)
    return render(request, 'users/contact-developer.html', {'loged_user': loged_user, 'developer': developer, 'var' : var})

