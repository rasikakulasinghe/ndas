"""
Utility functions for user management, email verification, and activity tracking.
"""

import requests
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import UserActivityLog, UserSession
from ndas.custom_codes.custom_methods import get_ip_address
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


def get_enhanced_device_details(request):
    """
    Get enhanced device details from request with improved parsing.
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    ip_address = get_ip_address(request)
    
    # Parse user agent using django-user-agents
    ua = request.user_agent
    
    device_info = {
        'ip_address': ip_address,
        'user_agent': user_agent,
        'browser_name': ua.browser.family if ua.browser else 'Unknown',
        'browser_version': ua.browser.version_string if ua.browser else 'Unknown',
        'operating_system': ua.os.family if ua.os else 'Unknown',
        'device_type': _get_device_type(ua),
        'device_brand': ua.device.brand if ua.device and ua.device.brand else 'Unknown',
        'device_model': ua.device.model if ua.device and ua.device.model else 'Unknown',
        'is_mobile': ua.is_mobile,
        'is_tablet': ua.is_tablet,
        'is_touch_capable': ua.is_touch_capable,
        'is_pc': ua.is_pc,
        'is_bot': ua.is_bot,
    }
    
    # Add geolocation if available
    location_info = get_geolocation_from_ip(ip_address)
    device_info.update(location_info)
    
    return device_info


def _get_device_type(ua):
    """
    Determine device type from user agent.
    """
    if ua.is_mobile:
        return 'Mobile'
    elif ua.is_tablet:
        return 'Tablet'
    elif ua.is_pc:
        return 'Desktop'
    elif ua.is_bot:
        return 'Bot'
    else:
        return 'Unknown'


def get_geolocation_from_ip(ip_address):
    """
    Get geolocation information from IP address.
    This is a basic implementation - for production, consider using a proper service.
    """
    location_info = {
        'country': '',
        'city': '',
        'latitude': None,
        'longitude': None,
    }
    
    # Skip private/local IP addresses
    if _is_private_ip(ip_address):
        return location_info
    
    try:
        # Using a free geolocation service (consider using a paid service for production)
        response = requests.get(
            f'http://ip-api.com/json/{ip_address}',
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                location_info.update({
                    'country': data.get('country', ''),
                    'city': data.get('city', ''),
                    'latitude': data.get('lat'),
                    'longitude': data.get('lon'),
                })
    except Exception as e:
        logger.warning(f"Failed to get geolocation for IP {ip_address}: {e}")
    
    return location_info


def _is_private_ip(ip_address):
    """
    Check if IP address is private/local.
    """
    private_ranges = [
        '127.',  # localhost
        '10.',   # private class A
        '172.',  # private class B (simplified check)
        '192.168.',  # private class C
        '::1',   # IPv6 localhost
    ]
    
    return any(ip_address.startswith(prefix) for prefix in private_ranges)


def log_user_activity(request, user=None, login_status=UserActivityLog.LOGIN_SUCCESS, 
                     attempted_username='', failed_reason=''):
    """
    Log user activity with enhanced device and security information.
    """
    device_info = get_enhanced_device_details(request)
    
    # Create activity log
    activity_log = UserActivityLog.objects.create(
        user=user,
        login_status=login_status,
        attempted_username=attempted_username or (user.username if user else ''),
        ip_address=device_info['ip_address'],
        user_agent=device_info['user_agent'],
        browser_name=device_info['browser_name'],
        browser_version=device_info['browser_version'],
        operating_system=device_info['operating_system'],
        device_type=device_info['device_type'],
        device_brand=device_info['device_brand'],
        device_model=device_info['device_model'],
        is_mobile=device_info['is_mobile'],
        is_tablet=device_info['is_tablet'],
        is_touch_capable=device_info['is_touch_capable'],
        is_pc=device_info['is_pc'],
        is_bot=device_info['is_bot'],
        country=device_info['country'],
        city=device_info['city'],
        latitude=device_info['latitude'],
        longitude=device_info['longitude'],
        session_key=request.session.session_key or '',
        failed_login_reason=failed_reason,
        data_retention_date=timezone.now() + timezone.timedelta(days=90),  # GDPR compliance
    )
    
    # Check for suspicious activity
    if activity_log.is_suspicious_activity():
        username = attempted_username or (user.username if user else 'Unknown')
        logger.warning(f"Suspicious activity detected for user {username}")
    
    return activity_log


def create_or_update_user_session(request, user):
    """
    Create or update user session tracking.
    """
    device_info = get_enhanced_device_details(request)
    device_summary = f"{device_info['browser_name']} on {device_info['operating_system']} ({device_info['device_type']})"
    
    session, created = UserSession.objects.update_or_create(
        session_key=request.session.session_key or '',
        defaults={
            'user': user,
            'ip_address': device_info['ip_address'],
            'user_agent': device_info['user_agent'],
            'device_summary': device_summary,
            'is_active': True,
        }
    )
    
    return session


def log_logout_activity(request, user):
    """
    Log logout activity and update session duration.
    """
    # Log logout activity
    log_user_activity(request, user, UserActivityLog.LOGOUT)
    
    # Update the most recent login activity with logout timestamp
    try:
        last_login = UserActivityLog.objects.filter(
            user=user,
            login_status=UserActivityLog.LOGIN_SUCCESS,
            session_key=request.session.session_key or ''
        ).latest('login_timestamp')
        
        last_login.logout_timestamp = timezone.now()
        last_login.calculate_session_duration()
        last_login.save(update_fields=['logout_timestamp', 'session_duration'])
        
    except UserActivityLog.DoesNotExist:
        logger.warning(f"No login record found for logout of user {user.username}")
    
    # Deactivate user session
    try:
        session_key = request.session.session_key or ''
        if session_key:
            user_session = UserSession.objects.get(session_key=session_key)
            user_session.deactivate()
    except UserSession.DoesNotExist:
        logger.warning(f"No session record found for user {user.username}")


def send_email_verification(user, request):
    """
    Send email verification to user.
    """
    # Generate verification token
    token = user.generate_email_verification_token()
    
    # Build verification URL
    verification_url = request.build_absolute_uri(
        f'/users/verify-email/{token}/'
    )
    
    # Email context
    context = {
        'user': user,
        'verification_url': verification_url,
        'site_name': 'NDAS System',
        'expiry_hours': 24,
    }
    
    # Render email template
    html_message = render_to_string('users/emails/verify_email.html', context)
    plain_message = strip_tags(html_message)
    
    # Send email
    try:
        send_mail(
            subject='Verify Your Email Address - NDAS System',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email to {user.email}: {e}")
        return False


def send_login_alert_email(user, device_info):
    """
    Send email alert for new device login.
    """
    context = {
        'user': user,
        'device_info': device_info,
        'login_time': timezone.now(),
        'site_name': 'NDAS System',
    }
    
    html_message = render_to_string('users/emails/login_alert.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject='New Device Login Alert - NDAS System',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send login alert email to {user.email}: {e}")
        return False


def check_email_verification_required(user):
    """
    Check if email verification is required for user.
    """
    # Skip verification for superusers and staff (optional)
    if user.is_superuser or user.is_staff:
        return False
    
    return not user.is_email_verified


def get_user_activity_summary(user, days=30):
    """
    Get user activity summary for the last N days.
    """
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days)
    
    activities = UserActivityLog.objects.filter(
        user=user,
        login_timestamp__gte=cutoff_date
    )
    
    summary = {
        'total_logins': activities.filter(login_status=UserActivityLog.LOGIN_SUCCESS).count(),
        'failed_attempts': activities.filter(login_status=UserActivityLog.LOGIN_FAILED).count(),
        'unique_ips': activities.values('ip_address').distinct().count(),
        'unique_devices': activities.values('device_type', 'browser_name', 'operating_system').distinct().count(),
        'last_login': activities.filter(login_status=UserActivityLog.LOGIN_SUCCESS).first(),
        'recent_activities': activities[:10],
    }
    
    return summary


def cleanup_user_data():
    """
    Cleanup old user data for privacy compliance.
    """
    # Cleanup old activity logs (older than 90 days)
    deleted_logs = UserActivityLog.cleanup_old_records(days=90)
    
    # Cleanup expired sessions
    deleted_sessions = UserSession.cleanup_expired_sessions()
    
    logger.info(f"Cleaned up {deleted_logs[0]} activity logs and {deleted_sessions[0]} sessions")
    
    return {
        'deleted_logs': deleted_logs[0],
        'deleted_sessions': deleted_sessions[0],
    }
