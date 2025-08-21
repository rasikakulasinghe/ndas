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
from django.core.paginator import Paginator
from django.db.models import Q
from .forms import CustomUserRegistrationForm, UserPasswordChange, CustomUserEditForm
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
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember')
        
        # Basic validation
        if not username:
            messages.error(request, 'Username is required.')
            return render(request, 'users/login.html', {'logged_user': logged_user})
        
        if not password:
            messages.error(request, 'Password is required.')
            return render(request, 'users/login.html', {'logged_user': logged_user})
        
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
                
                # Handle remember me functionality
                if remember_me:
                    # Set session to expire in 30 days if remember me is checked
                    request.session.set_expiry(30 * 24 * 60 * 60)  # 30 days in seconds
                else:
                    # Set session to expire when browser closes (default behavior)
                    request.session.set_expiry(0)
                
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
    """
    Edit user profile with enhanced security and validation.
    """
    # Get the user to be edited
    selected_user = get_object_or_404(CustomUser, id=pk)
    
    # Security check: Users can only edit their own profile unless they're staff
    if not request.user.is_staff and request.user.pk != selected_user.pk:
        messages.error(request, 'You do not have permission to edit this user.')
        return redirect('user-view', pk=request.user.pk)
    
    if request.method == 'POST':
        user_form = CustomUserEditForm(
            request.POST, 
            request.FILES, 
            instance=selected_user
        )
        
        if user_form.is_valid():
            try:
                # Save the form which will handle all field updates
                updated_user = user_form.save()
                
                messages.success(request, 'User profile updated successfully!')
                
                # Redirect to user view page instead of rendering template
                return redirect('user-view', pk=updated_user.pk)
                
            except Exception as e:
                messages.error(request, f'Error updating profile: {str(e)}')
                # Re-display the form with errors
                return render(request, 'users/user_edit.html', {
                    'form': user_form,
                    'selected_user': selected_user
                })
        else:
            # Form is invalid, show errors
            messages.error(request, 'Please correct the errors below.')
            return render(request, 'users/user_edit.html', {
                'form': user_form,
                'selected_user': selected_user
            })
    
    else:
        # GET request - show the form
        user_form = CustomUserEditForm(instance=selected_user)
        return render(request, 'users/user_edit.html', {
            'form': user_form,
            'selected_user': selected_user
        })

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
    try:
        developer = DeveloperContacts.objects.get(id=1)
    except DeveloperContacts.DoesNotExist:
        # Use the first available developer contact or create a default
        developer = DeveloperContacts.objects.first()
        if not developer:
            # Create a default developer contact if none exists
            developer = DeveloperContacts.objects.create()
    
    try:
        var = getFullDeviceDetails(request)
    except Exception as e:
        var = "Device details unavailable"
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting device details: {e}")
    
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


# Admin User Management Views
from .decorators import admin_required, superuser_required
from .forms import AdminUserCreationForm, AdminUserEditForm, UserSearchForm
from datetime import datetime, timedelta


@admin_required
def admin_dashboard(request):
    """Admin dashboard with user statistics and quick actions."""
    from django.utils import timezone
    
    # Get user statistics
    total_users = CustomUser.objects.count()
    active_users = CustomUser.objects.filter(is_active=True).count()
    staff_users = CustomUser.objects.filter(is_staff=True).count()
    
    # Get recent logins (last 24 hours)
    yesterday = timezone.now() - timedelta(days=1)
    recent_logins = UserActivityLog.objects.filter(
        activity_type=UserActivityLog.LOGIN_SUCCESS,
        login_timestamp__gte=yesterday
    ).count()
    
    # Get recent activities (last 10)
    recent_activities = UserActivityLog.objects.select_related('user').order_by('-login_timestamp')[:10]
    
    # Get recently added users (last 5)
    recent_users = CustomUser.objects.order_by('-date_joined')[:5]
    
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'staff_users': staff_users,
        'recent_logins': recent_logins,
        'recent_activities': recent_activities,
        'recent_users': recent_users,
    }
    
    return render(request, 'users/admin/admin_dashboard.html', context)


@admin_required
def admin_user_list(request):
    """Admin view to list all users with search and filtering."""
    form = UserSearchForm(request.GET)
    users = CustomUser.objects.all().order_by('-date_joined')
    
    # Apply filters
    if form.is_valid():
        search = form.cleaned_data.get('search')
        position = form.cleaned_data.get('position')
        is_active = form.cleaned_data.get('is_active')
        is_staff = form.cleaned_data.get('is_staff')
        
        if search:
            users = users.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )
        
        if position:
            users = users.filter(position=position)
        
        if is_active == 'true':
            users = users.filter(is_active=True)
        elif is_active == 'false':
            users = users.filter(is_active=False)
        
        if is_staff == 'true':
            users = users.filter(is_staff=True)
        elif is_staff == 'false':
            users = users.filter(is_staff=False)
    
    # Pagination
    paginator = Paginator(users, 25)  # Show 25 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'total_users': users.count(),
    }
    
    return render(request, 'users/admin/user_list.html', context)


@admin_required
def admin_user_add(request):
    """Admin view to add new users."""
    if request.method == 'POST':
        form = AdminUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                user = form.save()
                
                # Log admin action
                log_user_activity(
                    request, 
                    request.user, 
                    UserActivityLog.LOGIN_SUCCESS,
                    attempted_username=f"Created user: {user.username}"
                )
                
                messages.success(request, f'User "{user.username}" created successfully!')
                return redirect('admin-user-list')
            except Exception as e:
                messages.error(request, f'Error creating user: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AdminUserCreationForm()
    
    return render(request, 'users/admin/user_add.html', {'form': form})


@admin_required
def admin_user_edit(request, pk):
    """Admin view to edit existing users."""
    user = get_object_or_404(CustomUser, pk=pk)
    
    if request.method == 'POST':
        form = AdminUserEditForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            try:
                original_data = {
                    'is_active': user.is_active,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser,
                }
                
                updated_user = form.save()
                
                # Check for important changes and log them
                changes = []
                if original_data['is_active'] != updated_user.is_active:
                    status = "activated" if updated_user.is_active else "deactivated"
                    changes.append(f"User {status}")
                
                if original_data['is_staff'] != updated_user.is_staff:
                    status = "granted" if updated_user.is_staff else "removed"
                    changes.append(f"Staff access {status}")
                
                if original_data['is_superuser'] != updated_user.is_superuser:
                    status = "granted" if updated_user.is_superuser else "removed"
                    changes.append(f"Superuser access {status}")
                
                # Log admin action
                change_description = f"Updated user: {user.username}"
                if changes:
                    change_description += f" - {', '.join(changes)}"
                
                log_user_activity(
                    request,
                    request.user,
                    UserActivityLog.LOGIN_SUCCESS,
                    attempted_username=change_description
                )
                
                messages.success(request, f'User "{updated_user.username}" updated successfully!')
                return redirect('admin-user-list')
            except Exception as e:
                messages.error(request, f'Error updating user: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AdminUserEditForm(instance=user)
    
    return render(request, 'users/admin/user_edit.html', {
        'form': form,
        'user_obj': user
    })


@admin_required
@require_POST
def admin_user_delete(request, pk):
    """Admin view to delete users (soft delete by deactivating)."""
    user = get_object_or_404(CustomUser, pk=pk)
    
    # Prevent self-deletion
    if user == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('admin-user-list')
    
    # Prevent deletion of superusers by non-superusers
    if user.is_superuser and not request.user.is_superuser:
        messages.error(request, 'You cannot delete superuser accounts.')
        return redirect('admin-user-list')
    
    try:
        # Soft delete by deactivating
        user.is_active = False
        user.save()
        
        # Log admin action
        log_user_activity(
            request,
            request.user,
            UserActivityLog.LOGIN_SUCCESS,
            attempted_username=f"Deleted user: {user.username}"
        )
        
        messages.success(request, f'User "{user.username}" has been deactivated.')
    except Exception as e:
        messages.error(request, f'Error deleting user: {str(e)}')
    
    return redirect('admin-user-list')


@admin_required
@require_POST
def admin_user_toggle_status(request, pk):
    """Admin view to toggle user active status."""
    user = get_object_or_404(CustomUser, pk=pk)
    
    # Prevent self-deactivation
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('admin-user-list')
    
    try:
        user.is_active = not user.is_active
        user.save()
        
        status = "activated" if user.is_active else "deactivated"
        
        # Log admin action
        log_user_activity(
            request,
            request.user,
            UserActivityLog.LOGIN_SUCCESS,
            attempted_username=f"User {status}: {user.username}"
        )
        
        messages.success(request, f'User "{user.username}" has been {status}.')
    except Exception as e:
        messages.error(request, f'Error updating user status: {str(e)}')
    
    return redirect('admin-user-list')


@admin_required
def admin_user_activity(request, pk):
    """Admin view to see specific user's activity."""
    user = get_object_or_404(CustomUser, pk=pk)
    activities = UserActivityLog.objects.filter(user=user).order_by('-login_timestamp')
    
    # Pagination
    paginator = Paginator(activities, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'user_obj': user,
        'page_obj': page_obj,
        'total_activities': activities.count(),
    }
    
    return render(request, 'users/admin/user_activity.html', context)


@admin_required
def admin_activity_logs(request):
    """Admin view to see all system activity logs."""
    activities = UserActivityLog.objects.all().order_by('-login_timestamp')
    
    # Pagination
    paginator = Paginator(activities, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_activities': activities.count(),
    }
    
    return render(request, 'users/admin/activity_logs.html', context)
