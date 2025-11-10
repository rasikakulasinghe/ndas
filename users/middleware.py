"""
Middleware for tracking user activity and managing sessions.
"""

from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
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
    
    SECURITY: This middleware enforces subscription restrictions STRICTLY.
    """
    
    # URLs exempt from subscription check
    EXEMPT_URLS = [
        '/users/login/',
        '/users/logout/',
        '/users/subscription/info/',
        '/users/reset_password/',
        '/users/reset_password_sent/',
        '/users/reset/',
        '/users/reset_password_complete/',
        '/static/',
        '/media/',
        '/admin/',  # Admin users should be able to access admin panel
    ]
    
    def process_request(self, request):
        """
        Check subscription status for authenticated users.
        
        CRITICAL: This enforces subscription expiration strictly.
        """
        # Skip check for unauthenticated users
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None
        
        # Skip check for exempt URLs
        if any(request.path.startswith(url) for url in self.EXEMPT_URLS):
            return None
        
        # Skip check ONLY for superusers (as per requirements)
        # Staff users are subject to subscription like regular users
        if request.user.is_superuser:
            return None
        
        try:
            # Get the global subscription that applies to all non-superuser users
            # SECURITY: Use global subscription, not per-user subscriptions
            from users.models import Subscription
            subscription = Subscription.get_global_subscription()

            # PERFORMANCE: Only update status once per minute (avoid updating on every request)
            from django.core.cache import cache
            update_cache_key = f'subscription_last_update_{subscription.pk}'
            last_update = cache.get(update_cache_key)

            if last_update is None:
                # Update subscription status (uses date calculations)
                subscription.update_status()
                # Cache that we updated (prevent updates for 60 seconds)
                cache.set(update_cache_key, True, 60)

            # CRITICAL CHECK: Block access ONLY if fully expired (past grace period)
            # SECURITY: Allow access during grace period with warnings, block after grace period ends
            if subscription.is_expired:
                # Log the blocked access attempt
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Blocked access for user {request.user.username} with fully expired subscription. "
                    f"Expiration: {subscription.expiration_date}, Grace period ended: {subscription.grace_period_end_date}, Status: {subscription.status}"
                )

                # SECURITY: Store username in session before logout for display on expired page
                username = request.user.username
                request.session['expired_username'] = username

                # SECURITY: Force logout BEFORE redirect to prevent inconsistent state
                from django.contrib.auth import logout
                logout(request)

                # Add message after logout
                messages.error(
                    request,
                    f'Your subscription expired on {subscription.expiration_date} and grace period ended on {subscription.grace_period_end_date}. '
                    'Please contact support to renew your subscription.'
                )

                # Redirect to subscription info page (no login required)
                return redirect(reverse('subscription-info'))

            # SECURITY: Show warning banner during grace period (after expiration but before full expiry)
            # This warning appears on every page request during grace period
            if subscription.is_grace_period:
                from datetime import date
                days_until_lockout = (subscription.grace_period_end_date - date.today()).days

                # Only show warning once per session to avoid spam (check session flag)
                session_key = f'grace_warning_shown_{subscription.pk}'
                if not request.session.get(session_key, False):
                    messages.warning(
                        request,
                        f'URGENT: Your subscription expired on {subscription.expiration_date}. '
                        f'You have {days_until_lockout} days remaining before account lockout. '
                        'Please contact support immediately to renew your subscription.'
                    )
                    # Mark that we've shown the warning in this session
                    request.session[session_key] = True
        
        except Exception as e:
            # SECURITY: Log unexpected errors and deny access (fail closed)
            # This should rarely happen since get_global_subscription() always creates if missing
            import logging
            logger = logging.getLogger(__name__)
            logger.error(
                f"Unexpected subscription check error for user {request.user.username}: {type(e).__name__}: {str(e)}",
                exc_info=True
            )

            # Store username before logout
            username = request.user.username
            request.session['expired_username'] = username

            # In production, fail closed (deny access on errors)
            from django.contrib.auth import logout
            logout(request)

            messages.error(
                request,
                'Unable to verify subscription status. Please contact support.'
            )
            return redirect(reverse('subscription-info'))
        
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
