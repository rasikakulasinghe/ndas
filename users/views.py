from django.shortcuts import render
from users.models import CustomUser, UserActivityLog, UserSession
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth import views as auth_views
from ndas.custom_codes.custom_methods import getCurrentDateTime, getFullDeviceDetails
from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, Http404
from django.views.decorators.http import require_POST, require_http_methods, require_GET
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import date
from django_ratelimit.decorators import ratelimit
from django_ratelimit.core import is_ratelimited
from django_ratelimit.exceptions import Ratelimited
from .forms import CustomUserRegistrationForm, UserPasswordChange, CustomUserEditForm, SubscriptionForm
from .models import DeveloperContacts, Subscription
from .utils import (
    log_user_activity,
    create_or_update_user_session,
    log_logout_activity,
    send_email_verification,
    check_email_verification_required,
    get_user_activity_summary,
    get_enhanced_device_details
)
import json
import logging
import os
from django.urls import reverse

logger = logging.getLogger(__name__)

# Create your views here.
# F6 FIX: Use block=False on both decorators so both counters are always incremented
# before any blocking decision. With block=True the outer decorator raises immediately,
# leaving the inner counter un-incremented — an attacker exploiting the outer limit can
# bypass the inner counter indefinitely.
@ratelimit(key='post:username', rate='5/m', method='POST', block=False)
@ratelimit(key='ip', rate='3/m', method='POST', block=False)
def loginPage(request):
    if getattr(request, 'limited', False):
        raise Ratelimited()
    logged_user = request.user

    # Fetch developer contact information for modal
    developer, _ = DeveloperContacts.objects.get_or_create(pk=1)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember')
        
        # Basic validation
        if not username:
            messages.error(request, 'Username is required.')
            return render(request, 'users/login.html', {'logged_user': logged_user, 'developer': developer})

        if not password:
            messages.error(request, 'Password is required.')
            return render(request, 'users/login.html', {'logged_user': logged_user, 'developer': developer})

        # SECURITY FIX: Always call authenticate() to prevent timing attacks
        # Do NOT check if username exists first - this allows username enumeration
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Check if email verification is required
            if check_email_verification_required(user):
                messages.warning(request, 'Please verify your email address before logging in.')
                return render(request, 'users/login.html', {
                    'logged_user': logged_user,
                    'developer': developer,
                    'show_resend_verification': True,
                    'unverified_user_email': user.email
                })

            # CRITICAL: Check subscription status BEFORE allowing login
            # Skip for superusers only (staff are subject to subscription)
            if not user.is_superuser:
                try:
                    # Get the global subscription
                    subscription = Subscription.get_global_subscription()
                    # Update status to ensure it's current
                    subscription.update_status()

                    # SECURITY FIX: Block login ONLY if fully expired (past grace period)
                    # Allow login during grace period with warnings
                    if subscription.is_expired:
                        messages.error(
                            request,
                            f'The system subscription expired on {subscription.expiration_date} and grace period ended on {subscription.grace_period_end_date}. '
                            'Please contact support to renew the subscription before logging in.'
                        )
                        # Log the failed login attempt due to expired subscription
                        try:
                            log_user_activity(
                                request,
                                None,
                                UserActivityLog.LOGIN_FAILED,
                                attempted_username=username,
                                failed_reason="Global subscription fully expired (past grace period)"
                            )
                        except Exception:
                            pass
                        return render(request, 'users/login.html', {'logged_user': logged_user, 'developer': developer})

                    # SECURITY: Show warning during grace period (after expiration but before full expiry)
                    if subscription.is_grace_period:
                        days_until_lockout = (subscription.grace_period_end_date - date.today()).days
                        messages.warning(
                            request,
                            f'URGENT: The system subscription expired on {subscription.expiration_date}. '
                            f'You have {days_until_lockout} days remaining in the grace period. '
                            'Please contact support to renew the subscription.'
                        )

                except Exception as e:
                    # If subscription check fails, deny login (fail closed for security)
                    logger.error(f"Global subscription check failed for user {username}: {e}")
                    messages.error(
                        request,
                        'Unable to verify subscription status. Please contact support.'
                    )
                    return render(request, 'users/login.html', {'logged_user': logged_user, 'developer': developer})

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
                logger.error(f"Error updating last_login_device for {user.username}: {e}")

            # Log activity with enhanced tracking
            try:
                log_user_activity(request, user, UserActivityLog.LOGIN_SUCCESS)
            except Exception as e:
                # Log error but don't break login process
                logger.error(f"Error logging user activity for {user.username}: {e}")

            # Create/update session tracking
            try:
                create_or_update_user_session(request, user)
            except Exception as e:
                # Log error but don't break login process
                logger.error(f"Error creating user session for {user.username}: {e}")

            messages.success(request, 'You have successfully logged in!')
            return redirect('home')
        else:
            # SECURITY FIX: Authentication failed - use generic message to prevent username enumeration
            # Same message whether username doesn't exist or password is wrong
            try:
                log_user_activity(
                    request,
                    None,
                    UserActivityLog.LOGIN_FAILED,
                    attempted_username=username,
                    failed_reason="Invalid credentials"  # Generic reason - no details
                )
            except Exception as e:
                # Log error but don't break the flow
                logger.error(f"Error logging failed login attempt: {e}")

            # Generic error message - same for all authentication failures
            messages.error(request, 'Invalid username or password. Please try again.')
            return render(request, 'users/login.html', {'logged_user': logged_user, 'developer': developer})
    else:
        if request.user.is_authenticated:
            return redirect('home')
        else:
            return render(request, 'users/login.html', {'logged_user': logged_user, 'developer': developer})

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
    if request.user.is_superuser:
        custom_user = get_object_or_404(CustomUser, id=pk)
    else:
        custom_user = get_object_or_404(CustomUser, id=pk, institution=request.institution)
    loged_user = request.user
    return render(request, 'users/user_view.html', {'custom_user': custom_user, 'user' : loged_user})

@login_required(login_url='user-login')
def userViewByUsername(request, username):
    if request.user.is_superuser:
        custom_user = get_object_or_404(CustomUser, username=username)
    else:
        custom_user = get_object_or_404(CustomUser, username=username, institution=request.institution)
    return render(request, 'users/user_view.html', {'custom_user': custom_user,})

@login_required(login_url='user-login')
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
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
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
def userChangePassword(request):
    custom_user = request.user
    form = UserPasswordChange(custom_user, request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            # Django invalidates the session auth hash whenever the password
            # changes; without this, the user is silently logged out on their
            # very next request.
            update_session_auth_hash(request, form.user)
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
    developer, _ = DeveloperContacts.objects.get_or_create(pk=1)

    try:
        var = getFullDeviceDetails(request)
    except Exception as e:
        var = "Device details unavailable"
        logger.error(f"Error getting device details: {e}")
    
    return render(request, 'users/contact-developer.html', {'logged_user': logged_user, 'developer': developer, 'var': var})


# Email Verification Views
@require_GET
@ratelimit(key='ip', rate='10/m', block=True)
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
        
    except (CustomUser.DoesNotExist, CustomUser.MultipleObjectsReturned):
        messages.error(request, 'Invalid verification link.')
        return redirect('user-login')


@require_POST
@ratelimit(key='ip', rate='3/h', method='POST', block=True)
@ratelimit(key='post:email', rate='3/h', method='POST', block=True)
def resend_verification_email(request):
    """
    Resend email verification to user.

    Rate limited to:
    - 3 requests per hour per IP address
    - 3 requests per hour per email address
    """
    email = request.POST.get('email')
    
    if not email:
        messages.error(request, 'Email address is required.')
        return redirect('user-login')
    
    try:
        user = CustomUser.objects.get(email=email)
        
        if user.is_email_verified:
            # Use neutral message — do not reveal whether account exists or is already verified
            messages.success(request, 'If an account with this email exists and is unverified, a link has been sent.')
            return redirect('user-login')

        # Check if we can send another verification email (rate limiting)
        if user.email_verification_sent_at:
            time_since_last_sent = timezone.now() - user.email_verification_sent_at
            if time_since_last_sent.total_seconds() < 300:  # 5 minutes
                messages.warning(request, 'Please wait a few minutes before requesting another verification email.')
                return redirect('user-login')

        # Send verification email (log failures for ops visibility; user always sees neutral message)
        if not send_email_verification(user, request):
            logger.error(f"Failed to send verification email to user id={user.id}")
        messages.success(request, 'If an account with this email exists and is unverified, a link has been sent.')

        return redirect('user-login')

    except (CustomUser.DoesNotExist, CustomUser.MultipleObjectsReturned):
        # Use neutral message — do not reveal whether account exists or if duplicates exist
        messages.success(request, 'If an account with this email exists and is unverified, a link has been sent.')
        return redirect('user-login')


@method_decorator(ratelimit(key='ip', rate='3/h', method='POST', block=True), name='post')
class RateLimitedPasswordResetView(auth_views.PasswordResetView):
    """
    Password reset view with rate limiting.

    Rate limited to:
    - 3 requests per hour per IP address (class-level decorator)
    - 5 requests per hour per email address (post() override)

    This prevents abuse of the password reset functionality and protects against:
    - Email enumeration attacks
    - Password reset email spam
    - Resource exhaustion
    """

    def post(self, request, *args, **kwargs):
        email = request.POST.get('email', '').lower().strip()
        if email:
            # F7 FIX: Prefix key with view-specific namespace to prevent cache key collisions
            # with other rate limiters that might use 'email:...' keys.
            # F8 FIX: Empty email falls through here (not rate-limited per-email, which is
            # correct — the class-level IP decorator still protects against empty-email flooding).
            limited = is_ratelimited(
                request,
                fn=self.post,
                key=f'pwreset_email:{email}',
                rate='5/h',
                method='POST',
                increment=True,
            )
            if limited:
                # Neutral message — same as success to prevent timing/enumeration attacks
                messages.info(
                    request,
                    'If an account with this email exists, a reset link has been sent.'
                )
                return redirect(request.path)
        return super().post(request, *args, **kwargs)


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
    activities = UserActivityLog.objects.select_related('user').filter(user=user).order_by('-login_timestamp')[:50]
    
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
    user_session = get_object_or_404(UserSession, id=session_id, user=request.user)
    user_session.deactivate()
    messages.success(request, 'Session terminated successfully.')
    
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
@require_http_methods(["POST"])
def get_user_activity_api(request):
    """
    API endpoint to get user activity data for charts/widgets.
    Requires CSRF token for security.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    user = request.user
    days = int(request.POST.get('days', 30))
    
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
        login_status=UserActivityLog.LOGIN_SUCCESS,
        login_timestamp__gte=yesterday
    ).count()
    
    # Get recent activities (last 10)
    recent_activities = UserActivityLog.objects.select_related('user').order_by('-login_timestamp')[:10]
    
    # Get recently added users (last 5) - optimized to only fetch needed fields
    recent_users = CustomUser.objects.only('id', 'username', 'position', 'is_active', 'date_joined').order_by('-date_joined')[:5]
    
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
    _inst = getattr(request, 'institution', None)
    if request.user.is_superuser:
        users = CustomUser.objects.all().order_by('-date_joined')
    elif _inst is not None:
        users = CustomUser.objects.filter(institution=_inst).order_by('-date_joined')
    else:
        # Non-superuser with no institution assigned — return nothing rather than leak data
        users = CustomUser.objects.none()
    
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
                    failed_reason=f"Admin action: Created user: {user.username}"
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
    if request.user.is_superuser:
        user = get_object_or_404(CustomUser, pk=pk)
    else:
        user = get_object_or_404(CustomUser, pk=pk, institution=request.institution)
    
    if request.method == 'POST':
        form = AdminUserEditForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            try:
                original_data = {
                    'is_active': user.is_active,
                    'is_staff': user.is_staff,
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
                
                # Log admin action
                change_description = f"Updated user: {user.username}"
                if changes:
                    change_description += f" - {', '.join(changes)}"
                
                log_user_activity(
                    request,
                    request.user,
                    UserActivityLog.LOGIN_SUCCESS,
                    failed_reason=change_description
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
@require_http_methods(["DELETE"])
def admin_user_delete(request, pk):
    """
    Unified user deletion endpoint with password verification (soft delete)
    Part of refactor-delete-confirmation change

    Accepts: DELETE method with JSON payload {password: str}
    Returns: JSON {success: bool, message: str, redirect_url: str}
    """
    try:
        # 1. Retrieve user
        if request.user.is_superuser:
            user = get_object_or_404(CustomUser, pk=pk)
        else:
            user = get_object_or_404(CustomUser, pk=pk, institution=request.institution)

        # 2. Check self-deletion
        if user == request.user:
            logger.warning(
                f"Self-deletion attempt blocked: user={request.user.username}"
            )
            return JsonResponse({
                "success": False,
                "error": "Self-deletion not allowed",
                "message": "You cannot delete your own account."
            }, status=403)

        # 3. Verify password
        try:
            data = json.loads(request.body)
            password = data.get('password', '')
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "error": "Invalid request",
                "message": "Invalid request format."
            }, status=400)

        if not password:
            return JsonResponse({
                "success": False,
                "error": "Password required",
                "message": "Password is required to confirm deletion."
            }, status=400)

        if not request.user.check_password(password):
            logger.warning(
                f"Invalid password for user deletion: admin={request.user.username}, "
                f"target_user={user.username}"
            )
            return JsonResponse({
                "success": False,
                "error": "Invalid password",
                "message": "Incorrect password. Please try again."
            }, status=401)

        # 4. Perform soft delete (deactivation)
        user.is_active = False
        user.save()

        # 5. Audit log
        log_user_activity(
            request,
            request.user,
            UserActivityLog.ADMIN_ACTION,
            failed_reason=f"Admin action: Deleted (deactivated) user: {user.username}"
        )

        logger.info(
            f"User deletion successful: admin={request.user.username}, "
            f"deactivated_user={user.username}, id={pk}"
        )

        # 7. Return success
        return JsonResponse({
            "success": True,
            "message": f"User '{user.username}' has been deactivated successfully.",
            "redirect_url": reverse('admin-user-list')
        })

    except Http404:
        return JsonResponse({
            "success": False,
            "error": "Not found",
            "message": "User not found."
        }, status=404)
    except Exception as e:
        logger.error(
            f"User deletion error: admin={request.user.username}, "
            f"target_user_id={pk}, error={str(e)}"
        )
        return JsonResponse({
            "success": False,
            "error": "Server error",
            "message": "An unexpected error occurred. Please try again."
        }, status=500)


@admin_required
@require_POST
def admin_user_toggle_status(request, pk):
    """Admin view to toggle user active status."""
    if request.user.is_superuser:
        user = get_object_or_404(CustomUser, pk=pk)
    else:
        user = get_object_or_404(CustomUser, pk=pk, institution=request.institution)
    
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
            UserActivityLog.ADMIN_ACTION,
            failed_reason=f"Admin action: User {status}: {user.username}"
        )
        
        messages.success(request, f'User "{user.username}" has been {status}.')
    except Exception as e:
        messages.error(request, f'Error updating user status: {str(e)}')
    
    return redirect('admin-user-list')


@admin_required
def admin_user_activity(request, pk):
    """Admin view to see specific user's activity."""
    if request.user.is_superuser:
        user = get_object_or_404(CustomUser, pk=pk)
    else:
        user = get_object_or_404(CustomUser, pk=pk, institution=request.institution)
    activities = UserActivityLog.objects.select_related('user').filter(user=user).order_by('-login_timestamp')
    
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
    if request.user.is_superuser:
        activities = UserActivityLog.objects.select_related('user').all().order_by('-login_timestamp')
    else:
        activities = UserActivityLog.objects.select_related('user').filter(
            user__institution=request.institution
        ).order_by('-login_timestamp')

    paginator = Paginator(activities, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'total_activities': paginator.count,
    }

    return render(request, 'users/admin/activity_logs.html', context)


@login_required(login_url="user-login")
def subscription_detail(request):
    """
    Display global subscription details.
    Shows subscription information including remaining days, status, and expiration date.

    SECURITY: Requires login - for active/grace period users only.
    """
    try:
        # Get the global subscription
        subscription = Subscription.get_global_subscription()
        subscription.update_status()

        context = {
            'subscription': subscription,
            'remaining_days': subscription.remaining_days,
            'is_grace_period': subscription.is_grace_period,
            'expiration_date': subscription.expiration_date,
            'grace_period_end_date': subscription.grace_period_end_date,
        }

        return render(request, 'users/subscription_detail.html', context)

    except Exception as e:
        messages.error(request, 'Unable to retrieve subscription information.')
        return redirect('home')


def subscription_info(request):
    """
    Display subscription expired/information page.
    Shows clear messaging about expired subscription and contact information.

    SECURITY: No @login_required - users are logged out before reaching here.
    This page is accessible to show expired subscription details.
    """
    try:
        # Get the global subscription
        subscription = None
        try:
            subscription = Subscription.get_global_subscription()
            subscription.update_status()
        except Exception:
            pass

        # Fetch developer contact information
        developer = DeveloperContacts.objects.first()
        if developer is None:
            developer = DeveloperContacts.objects.create()

        context = {
            'subscription': subscription,
            'expiration_date': subscription.expiration_date if subscription else None,
            'grace_period_end_date': subscription.grace_period_end_date if subscription else None,
            'developer': developer,
        }

        return render(request, 'users/subscription_expired.html', context)

    except Exception as e:
        # Log error but still show page with minimal info
        logger.error(f"Error in subscription_info view: {e}", exc_info=True)

        # Fetch developer contact information
        developer = DeveloperContacts.objects.first()
        if developer is None:
            developer = DeveloperContacts.objects.create()

        messages.error(request, 'Unable to retrieve complete subscription information.')

        context = {
            'subscription': None,
            'expiration_date': None,
            'grace_period_end_date': None,
            'developer': developer,
        }

        return render(request, 'users/subscription_expired.html', context)


@login_required(login_url="user-login")
def subscription_update(request):
    """
    Update the global subscription that applies to all non-superuser users.

    SECURITY: Restricted to superusers only.
    PURPOSE: Allows superusers to modify the single global subscription.
    """
    # Check if user is superuser
    if not request.user.is_superuser:
        messages.error(request, 'Access denied. Only superusers can update subscriptions.')
        return redirect('home')

    # Get or create the global subscription
    subscription = Subscription.get_global_subscription()

    if request.method == 'POST':
        form = SubscriptionForm(request.POST, instance=subscription)
        if form.is_valid():
            try:
                # Update the global subscription
                subscription = form.save()
                subscription.update_status()

                messages.success(request, 'Global subscription updated successfully. Changes apply to all non-superuser users.')
                return redirect('admin-user-list')

            except Exception as e:
                messages.error(request, f'Error updating subscription: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SubscriptionForm(instance=subscription)

    context = {
        'form': form,
        'subscription': subscription,
    }

    return render(request, 'users/subscription_update.html', context)
