"""
Middleware for tracking user activity and managing sessions.
"""

from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
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
