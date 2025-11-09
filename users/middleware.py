"""
Middleware for tracking user activity and managing sessions.
"""

from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.shortcuts import redirect
from django.urls import reverse
from users.utils import (
    log_user_activity, 
    create_or_update_user_session,
    log_logout_activity
)
from users.models import UserActivityLog, UserSession
from django.utils import timezone


class UserActivityMiddleware(MiddlewareMixin):
    """
    Middleware to track user activity and update session information.
    """
    
    def process_request(self, request):
        """
        Process incoming requests to update session activity.
        """
        # Update session activity for authenticated users
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                session_key = request.session.session_key
                if session_key:
                    UserSession.objects.filter(
                        user=request.user,
                        session_key=session_key,
                        is_active=True
                    ).update(last_activity=timezone.now())
            except Exception:
                # Fail silently to avoid breaking the application
                pass
        
        return None


class SubscriptionCheckMiddleware(MiddlewareMixin):
    """
    Middleware to check user subscription status and enforce access control.
    Redirects expired users to subscription information page.
    """
    
    # URLs exempt from subscription check
    EXEMPT_URLS = [
        '/users/login/',
        '/users/logout/',
        '/users/subscription/info/',
        '/static/',
        '/media/',
        '/admin/',  # Admin users should be able to access admin panel
    ]
    
    def process_request(self, request):
        """
        Check subscription status for authenticated users.
        """
        # Skip check for unauthenticated users
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None
        
        # Skip check for exempt URLs
        if any(request.path.startswith(url) for url in self.EXEMPT_URLS):
            return None
        
        # Skip check for superusers and staff
        if request.user.is_superuser or request.user.is_staff:
            return None
        
        try:
            # Get user's subscription
            subscription = request.user.subscription
            
            # Update subscription status
            subscription.update_status()
            
            # Check if subscription is expired (beyond grace period)
            if subscription.is_expired:
                # Redirect to subscription info page
                return redirect(reverse('subscription-info'))
            
        except Exception:
            # Fail silently to avoid breaking the application
            # If no subscription exists or any error occurs, allow access
            pass
        
        return None


# @receiver(user_logged_in)
# def log_user_login(sender, request, user, **kwargs):
#     """
#     Signal handler for successful user login.
#     """
#     try:
#         # Log the login activity
#         log_user_activity(request, user, UserActivityLog.LOGIN_SUCCESS)
#         
#         # Create or update user session
#         create_or_update_user_session(request, user)
#         
#     except Exception as e:
#         # Log the error but don't break the login process
#         import logging
#         logger = logging.getLogger(__name__)
#         logger.error(f"Error logging user activity for {user.username}: {e}")


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """
    Signal handler for user logout.
    """
    try:
        if user:
            log_logout_activity(request, user)
    except Exception as e:
        # Log the error but don't break the logout process
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error logging logout activity for {user.username if user else 'unknown'}: {e}")
