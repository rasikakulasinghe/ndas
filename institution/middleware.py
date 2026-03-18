"""
Institution context middleware — Phase 2 replacement for SubscriptionCheckMiddleware.
Position 13 in MIDDLEWARE stack (replaces users.middleware.SubscriptionCheckMiddleware).
"""
import logging
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponseRedirect

logger = logging.getLogger(__name__)

# URLs that bypass institution context resolution entirely
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
    '/admin/',
    '/institution/',  # Institution management URLs don't need a pre-existing context
]


class InstitutionContextMiddleware(MiddlewareMixin):
    """
    Phase 2 institution context middleware (position 13).
    Replaces users.middleware.SubscriptionCheckMiddleware.

    MULTI_INSTITUTION_ENABLED=False: behaves identically to old SubscriptionCheckMiddleware.
    MULTI_INSTITUTION_ENABLED=True: resolves request.institution from user or session.
    """

    def process_request(self, request):
        if not getattr(settings, 'MULTI_INSTITUTION_ENABLED', False):
            return self._phase1_subscription_check(request)

        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        if any(request.path.startswith(url) for url in EXEMPT_URLS):
            return None

        return self._resolve_institution_context(request)

    # ─── Phase 2: Institution Context Resolution ───────────────────────────────

    def _resolve_institution_context(self, request):
        from ndas.custom_codes.choice import UserType
        from institution.models import Institution

        user_type = getattr(request.user, 'user_type', UserType.USER)

        if user_type == UserType.SUPERADMIN:
            return self._resolve_superadmin_context(request, Institution)
        else:
            return self._resolve_user_context(request)

    def _resolve_superadmin_context(self, request, Institution):
        active_id = request.session.get('active_institution_id')
        if active_id:
            # Per-request cache: avoid repeated DB hits within a single request cycle.
            # F1 FIX: Compare cached pk against session id — middleware can be called multiple
            # times per request, and the session could have changed between calls.
            cached = getattr(request, '_institution_cache', None)
            if cached is not None and cached.pk == active_id:
                request.institution = cached
                return None
            try:
                request.institution = Institution.objects.get(pk=active_id, is_active=True)
                request._institution_cache = request.institution
            except Institution.DoesNotExist:
                request.session.pop('active_institution_id', None)
                return redirect(reverse('institution:institution-selector'))
            except Institution.MultipleObjectsReturned:
                # PK collision is a data-integrity error — log it before redirecting
                logger.error(
                    "Data integrity error: multiple Institution rows with pk=%s. "
                    "Clearing session context for user=%s.",
                    active_id,
                    getattr(request.user, 'username', '?'),
                )
                request.session.pop('active_institution_id', None)
                return redirect(reverse('institution:institution-selector'))
        else:
            return redirect(reverse('institution:institution-selector'))
        return None

    def _resolve_user_context(self, request):
        institution = getattr(request.user, 'institution', None)
        if institution is None:
            # Transitional state: institution not yet assigned (pre-Story-1.6 data migration).
            # Permit access so existing users are not locked out during migration.
            request.institution = None
            return None
        request.institution = institution
        return self._check_subscription(request)

    def _check_subscription(self, request):
        """Enforce per-institution subscription for ADMIN/USER (Phase 2 mode)."""
        if request.institution is None:
            return None

        from ndas.custom_codes.choice import SubscriptionStatus

        sub_status = request.institution.subscription_status

        if sub_status == SubscriptionStatus.EXPIRED:
            from django.contrib.auth import logout as auth_logout
            logger.warning(
                f"Blocked EXPIRED institution access: user={request.user.username}, "
                f"institution={request.institution.slug}"
            )
            request.session['expired_username'] = request.user.username
            auth_logout(request)
            messages.error(
                request,
                'Your institution subscription has expired. Please contact your administrator.'
            )
            return redirect(reverse('subscription-info'))

        if sub_status == SubscriptionStatus.GRACE:
            if request.method != 'GET' and not request.path.startswith('/referral/'):
                # Block writes during grace period (FR48).
                # /referral/ URLs are exempt — active referrals continue to completion.
                messages.warning(
                    request,
                    'Your institution is in a grace period. Only read access is permitted. '
                    'Active referrals continue normally. Contact your administrator to renew.'
                )
                referer = request.META.get('HTTP_REFERER', '/')
                return HttpResponseRedirect(referer)

        return None

    # ─── Phase 1: Legacy Subscription Check (MULTI_INSTITUTION_ENABLED=False) ──

    def _phase1_subscription_check(self, request):
        """
        Mirrors the old SubscriptionCheckMiddleware exactly.
        Active when MULTI_INSTITUTION_ENABLED=False (default during Phase 2 development).
        Preserves all Phase 1 behaviour unchanged.
        """
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        exempt_urls = [
            '/users/login/', '/users/logout/', '/users/subscription/info/',
            '/users/reset_password/', '/users/reset_password_sent/',
            '/users/reset/', '/users/reset_password_complete/',
            '/static/', '/media/', '/admin/',
        ]
        if any(request.path.startswith(url) for url in exempt_urls):
            return None

        if request.user.is_superuser:
            return None

        try:
            from users.models import Subscription
            from django.core.cache import cache
            subscription = Subscription.get_global_subscription()

            update_cache_key = f'subscription_last_update_{subscription.pk}'
            if cache.add(update_cache_key, True, 60):
                subscription.update_status()

            if subscription.is_expired:
                logger.warning(
                    f"Blocked access for user {request.user.username} - global subscription expired."
                )
                request.session['expired_username'] = request.user.username
                from django.contrib.auth import logout as auth_logout
                auth_logout(request)
                messages.error(
                    request,
                    f'Your subscription expired on {subscription.expiration_date} and grace period '
                    f'ended on {subscription.grace_period_end_date}. Please contact support.'
                )
                return redirect(reverse('subscription-info'))

            if subscription.is_grace_period:
                from datetime import date
                days_until_lockout = (subscription.grace_period_end_date - date.today()).days
                session_key = f'grace_warning_shown_{subscription.pk}'
                if not request.session.get(session_key, False):
                    messages.warning(
                        request,
                        f'URGENT: Your subscription expired. You have {days_until_lockout} days '
                        'before account lockout. Please contact support immediately.'
                    )
                    request.session[session_key] = True

        except Exception as e:
            logger.error(
                f"Subscription check error for {request.user.username}: {type(e).__name__}: {e}",
                exc_info=True
            )
            request.session['expired_username'] = request.user.username
            from django.contrib.auth import logout as auth_logout
            auth_logout(request)
            messages.error(request, 'Unable to verify subscription status. Please contact support.')
            return redirect(reverse('subscription-info'))

        return None
