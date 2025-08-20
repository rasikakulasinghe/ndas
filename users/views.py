from django.shortcuts import render
from users.models import CustomUser, UserActivityLog, UserSession
from django.contrib.auth import authenticate, login, logout
from ndas.custom_codes.custom_methods import getCurrentDateTime, getFullDeviceDetails
from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .forms import CustomUserRegistrationForm, UserPasswordChange
from .models import DeveloperContacts
from .utils import (
    log_user_activity, 
    create_or_update_user_session, 
    log_logout_activity,
    send_email_verification,
    check_email_verification_required,
    get_user_activity_summary,
    get_enhanced_device_details
)
import os

# Create your views here.
def loginPage(request):
    logged_user = request.user
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        
        if CustomUser.objects.filter(username=username).exists():
            user = authenticate(request, username=username, password=password)
            if user is not None:
                # Check if email verification is required
                if check_email_verification_required(user):
                    messages.warning(request, 'Please verify your email address before logging in.')
                    return render(request, 'users/login.html', {
                        'logged_user': logged_user,
                        'show_resend_verification': True,
                        'unverified_user_email': user.email
                    })
                
                # Successful login
                login(request, user)
                
                # Ensure session is created/saved before logging
                if not request.session.session_key:
                    request.session.save()
                
                # Update device information (keep existing functionality)
                try:
                    device_details = getFullDeviceDetails(request)
                    user.last_login_device = device_details
                    user.save(update_fields=["last_login_device"])
                except Exception as e:
                    # Log error but don't break login process
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error updating last_login_device for {user.username}: {e}")
                
                # Log activity with enhanced tracking
                try:
                    log_user_activity(request, user, UserActivityLog.LOGIN_SUCCESS)
                except Exception as e:
                    # Log error but don't break login process
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error logging user activity for {user.username}: {e}")
                
                # Create/update session tracking
                try:
                    create_or_update_user_session(request, user)
                except Exception as e:
                    # Log error but don't break login process
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error creating user session for {user.username}: {e}")
                
                messages.success(request, 'You have successfully logged in!')
                return redirect('home')
            else:
                # Failed login
                try:
                    log_user_activity(
                        request, 
                        None, 
                        UserActivityLog.LOGIN_FAILED, 
                        attempted_username=username,
                        failed_reason="Invalid password"
                    )
                except Exception as e:
                    # Log error but don't break the flow
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error logging failed login attempt: {e}")
                
                messages.error(request, 'Wrong password. You are not authorized to login.')
                return render(request, 'users/login.html', {'logged_user': logged_user})
        else:
            # User doesn't exist
            try:
                log_user_activity(
                    request, 
                    None, 
                    UserActivityLog.LOGIN_FAILED, 
                    attempted_username=username,
                    failed_reason="Username not found"
                )
            except Exception as e:
                # Log error but don't break the flow
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error logging failed login attempt: {e}")
            
            messages.error(request, 'Wrong username. You are not authorized to login.')
            return render(request, 'users/login.html', {'logged_user': logged_user})
    else:
        if request.user.is_authenticated:
            return redirect('home')
        else:
            return render(request, 'users/login.html', {'logged_user': logged_user})

def logoutPage(request):
    user = request.user
    if user.is_authenticated:
        # Log logout activity
        log_logout_activity(request, user)
    
    logout(request)
    messages.success(request, 'You have been logged out successfully!')
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
        selected_user.position = user_form_modified.data.get("position")
        selected_user.mobile_primary = user_form_modified.data.get("mobile_primary")
        selected_user.mobile_secondary = user_form_modified.data.get("mobile_secondary")
        selected_user.landline_primary = user_form_modified.data.get("landline_primary")
        selected_user.landline_secondary = user_form_modified.data.get("landline_secondary")
        selected_user.home_address = user_form_modified.data.get("home_address")
        selected_user.station_address = user_form_modified.data.get("station_address")
        selected_user.additional_notes = user_form_modified.data.get("additional_notes")
        
        if 'profile_picture' in request.FILES:
            image_prop = request.FILES['profile_picture']
            try:
                selected_user.profile_picture = image_prop
            except Exception as e:
                messages.warning(request, str(e))
        
        selected_user.username = user_form_modified.data.get("username")
        selected_user.first_name = user_form_modified.data.get("first_name")
        selected_user.last_name = user_form_modified.data.get("last_name")
        selected_user.email = user_form_modified.data.get("email")
        
        selected_user.save(update_fields=[
            'position', 'mobile_primary', 'mobile_secondary', 'landline_primary', 
            'landline_secondary', 'home_address', 'station_address', 'additional_notes', 
            'profile_picture', 'username', 'first_name', 'last_name', 'email'
        ])
        
        updated_user = CustomUser.objects.get(id=pk)
        
        messages.success(request, 'User details updated successfully...')
        
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
    logged_user = request.user
    developer = DeveloperContacts.objects.get(id=1)
    var = getFullDeviceDetails(request)
    return render(request, 'users/contact-developer.html', {'logged_user': logged_user, 'developer': developer, 'var': var})


# Email Verification Views
def verify_email(request, token):
    """
    Verify user's email address using the verification token.
    """
    try:
        user = CustomUser.objects.get(email_verification_token=token)
        
        if user.is_email_verified:
            messages.info(request, 'Your email is already verified.')
            return redirect('user-login')
        
        if not user.is_email_verification_token_valid():
            messages.error(request, 'Email verification link has expired. Please request a new one.')
            return render(request, 'users/verification_expired.html', {'user_email': user.email})
        
        # Verify the email
        user.verify_email()
        messages.success(request, 'Your email has been successfully verified! You can now log in.')
        
        # Log the verification activity
        log_user_activity(request, user, UserActivityLog.LOGIN_SUCCESS, failed_reason="Email verified")
        
        return redirect('user-login')
        
    except CustomUser.DoesNotExist:
        messages.error(request, 'Invalid verification link.')
        return redirect('user-login')


@require_POST
def resend_verification_email(request):
    """
    Resend email verification to user.
    """
    email = request.POST.get('email')
    
    if not email:
        messages.error(request, 'Email address is required.')
        return redirect('user-login')
    
    try:
        user = CustomUser.objects.get(email=email)
        
        if user.is_email_verified:
            messages.info(request, 'Your email is already verified.')
            return redirect('user-login')
        
        # Check if we can send another verification email (rate limiting)
        if user.email_verification_sent_at:
            time_since_last_sent = timezone.now() - user.email_verification_sent_at
            if time_since_last_sent.total_seconds() < 300:  # 5 minutes
                messages.warning(request, 'Please wait a few minutes before requesting another verification email.')
                return redirect('user-login')
        
        # Send verification email
        if send_email_verification(user, request):
            messages.success(request, 'Verification email has been sent. Please check your inbox.')
        else:
            messages.error(request, 'Failed to send verification email. Please try again later.')
        
        return redirect('user-login')
        
    except CustomUser.DoesNotExist:
        messages.error(request, 'No account found with this email address.')
        return redirect('user-login')


@login_required(login_url='user-login')
def user_activity(request):
    """
    Display user's activity history.
    """
    user = request.user
    
    # Get activity summary
    activity_summary = get_user_activity_summary(user, days=30)
    
    # Get recent activities with pagination
    page = request.GET.get('page', 1)
    activities = UserActivityLog.objects.filter(user=user).order_by('-login_timestamp')[:50]
    
    # Get active sessions
    active_sessions = user.active_sessions.filter(is_active=True).order_by('-last_activity')
    
    context = {
        'user': user,
        'activity_summary': activity_summary,
        'activities': activities,
        'active_sessions': active_sessions,
    }
    
    return render(request, 'users/user_activity.html', context)


@login_required(login_url='user-login')
@require_POST
def terminate_session(request, session_id):
    """
    Terminate a specific user session.
    """
    try:
        user_session = UserSession.objects.get(id=session_id, user=request.user)
        user_session.deactivate()
        messages.success(request, 'Session terminated successfully.')
    except UserSession.DoesNotExist:
        messages.error(request, 'Session not found.')
    
    return redirect('user-activity')


@login_required(login_url='user-login')
@require_POST
def terminate_all_sessions(request):
    """
    Terminate all user sessions except the current one.
    """
    current_session_key = request.session.session_key
    
    # Deactivate all other sessions
    other_sessions = UserSession.objects.filter(
        user=request.user,
        is_active=True
    ).exclude(session_key=current_session_key)
    
    count = other_sessions.count()
    other_sessions.update(is_active=False)
    
    messages.success(request, f'Terminated {count} session(s) successfully.')
    return redirect('user-activity')


def send_verification_email_view(request):
    """
    Show form to send verification email.
    """
    if request.method == 'POST':
        return resend_verification_email(request)
    
    return render(request, 'users/send_verification.html')


# API Views for AJAX requests
@csrf_exempt
def get_user_activity_api(request):
    """
    API endpoint to get user activity data for charts/widgets.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    user = request.user
    days = int(request.GET.get('days', 30))
    
    activity_summary = get_user_activity_summary(user, days)
    
    # Prepare data for JSON serialization
    response_data = {
        'total_logins': activity_summary['total_logins'],
        'failed_attempts': activity_summary['failed_attempts'],
        'unique_ips': activity_summary['unique_ips'],
        'unique_devices': activity_summary['unique_devices'],
        'last_login': {
            'timestamp': activity_summary['last_login'].login_timestamp.isoformat() if activity_summary['last_login'] else None,
            'ip_address': activity_summary['last_login'].ip_address if activity_summary['last_login'] else None,
            'device_type': activity_summary['last_login'].device_type if activity_summary['last_login'] else None,
        } if activity_summary['last_login'] else None,
    }
    
    return JsonResponse(response_data)

