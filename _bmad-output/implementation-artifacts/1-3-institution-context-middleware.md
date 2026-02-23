# Story 1.3: Institution Context Middleware

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **clinician**,
I want every request I make to automatically resolve to my institution's context,
So that all views return only my institution's data without requiring per-view configuration.

## Acceptance Criteria

1. **Given** `InstitutionContextMiddleware` is at position 13 in `MIDDLEWARE`, replacing `SubscriptionCheckMiddleware`
   **When** an ADMIN or USER makes any authenticated request
   **Then** `request.institution` is set to `request.user.institution` before the view function executes

2. **Given** a SUPERADMIN has `session['active_institution_id']` set
   **When** the SUPERADMIN makes any request
   **Then** `request.institution` is set to the institution identified by the session value

3. **Given** a SUPERADMIN has no `active_institution_id` in session
   **When** the SUPERADMIN accesses any institution-scoped view
   **Then** the middleware redirects to the institution selector screen

4. **Given** an institution's `subscription_status` is GRACE
   **When** a user makes a GET request
   **Then** the request proceeds (read-only access granted)
   **And** when the same user makes a POST request that is not part of an active referral thread, the middleware blocks the request with a 403 and warning message

5. **Given** an institution's `subscription_status` is EXPIRED
   **When** any ADMIN or USER attempts to authenticate
   **Then** login is blocked and a subscription-expired message is shown

6. **Given** the `institution_context` context processor is registered in `settings.py`
   **When** any authenticated template is rendered
   **Then** `active_institution`, `user_type`, and `is_superadmin` are available as template context variables
   **And** `{{ request.user.institution }}` is never used directly in templates — only `{{ active_institution }}` from the context processor

## Tasks / Subtasks

- [ ] Task 1: Create `institution/middleware.py` — InstitutionContextMiddleware (AC: #1–#5)
  - [ ] Class uses `MiddlewareMixin` (project-standard pattern — see `security_middleware.py`)
  - [ ] When `MULTI_INSTITUTION_ENABLED=False`: delegate to Phase 1 `_phase1_subscription_check()` (mirrors old SubscriptionCheckMiddleware)
  - [ ] When `MULTI_INSTITUTION_ENABLED=True`: resolve institution context for ADMIN/USER from `request.user.institution`
  - [ ] When `MULTI_INSTITUTION_ENABLED=True`: resolve context for SUPERADMIN from `session['active_institution_id']`
  - [ ] When SUPERADMIN has no session context: redirect to `institution-selector`
  - [ ] GRACE enforcement: GET allowed; POST (non-referral) → `HttpResponseRedirect(referer)` + warning message
  - [ ] EXPIRED enforcement: logout user → redirect to `subscription-info` (same as Phase 1 behavior)
  - [ ] See exact code spec in Dev Notes

- [ ] Task 2: Create `institution/context_processors.py` — institution_context (AC: #6)
  - [ ] Guard anonymous requests: `if not request.user.is_authenticated: return {}`
  - [ ] Inject: `active_institution` (from `request.institution`), `user_type`, `is_superadmin`
  - [ ] See exact spec in Dev Notes

- [ ] Task 3: Create minimal `institution/urls.py` and stub `institution/views.py` (AC: #3)
  - [ ] `institution/urls.py`: one URL — `path('', views.institution_selector, name='institution-selector')` at `institution/`
  - [ ] `institution/views.py`: stub `institution_selector` view — `@login_required` + redirect to `patient-manager`
  - [ ] Full selector implementation is **Story 2.1** — this stub just makes the URL resolvable

- [ ] Task 4: Update `ndas/settings.py` — middleware and context processor registration (AC: #1, #6)
  - [ ] In `MIDDLEWARE`: replace `'users.middleware.SubscriptionCheckMiddleware'` with `'institution.middleware.InstitutionContextMiddleware'`
  - [ ] In `TEMPLATES[0]['OPTIONS']['context_processors']`: add `'institution.context_processors.institution_context'`
  - [ ] Do NOT move any other middleware entries — order is critical

- [ ] Task 5: Update `ndas/urls.py` — register institution URL namespace (AC: #3)
  - [ ] Add `path("institution/", include("institution.urls"))` to `urlpatterns`
  - [ ] Place it BEFORE `path("", include("patients.urls"))` — the catch-all root must come last
  - [ ] See Dev Notes for exact placement

- [ ] Task 6: Write `institution/tests/test_middleware.py` (AC: all)
  - [ ] Test: ADMIN/USER request sets `request.institution` from user FK
  - [ ] Test: SUPERADMIN with session sets `request.institution` from session
  - [ ] Test: SUPERADMIN without session redirects to `institution-selector`
  - [ ] Test: GRACE institution → GET allowed; POST blocked with 302 redirect
  - [ ] Test: EXPIRED institution → user logged out, redirected to `subscription-info`
  - [ ] Test: Context processor injects `active_institution`, `user_type`, `is_superadmin`
  - [ ] Test: Context processor returns `{}` for anonymous requests

- [ ] Task 7: Run tests and verify no regressions (AC: all)
  - [ ] `python manage.py test institution.tests.test_middleware`
  - [ ] `python manage.py test institution`
  - [ ] `python manage.py test` — full suite; confirm Phase 1 behavior unchanged with `MULTI_INSTITUTION_ENABLED=False`

## Dev Notes

### Dependencies: Stories 1.1 + 1.2 Must Be Complete

- Story 1.1: `institution.models.Institution` must exist (middleware imports it)
- Story 1.2: `request.user.institution` and `request.user.user_type` must exist on `CustomUser`

### Critical: `MULTI_INSTITUTION_ENABLED` Flag Behaviour

**All Phase 2 middleware logic is guarded by this flag.** The flag is `False` by default (set in Story 1.1). When `False`, `InstitutionContextMiddleware` internally mirrors the old `SubscriptionCheckMiddleware` exactly, preserving Phase 1 behaviour.

This means during Stories 1.3–1.6 development, `MULTI_INSTITUTION_ENABLED=False`, so all Phase 2 code paths are dormant. The flag is only set to `True` in Story 1.7 after isolation tests pass on staging.

**Phase 2 context resolution (MULTI_INSTITUTION_ENABLED=True only):**
- ADMIN/USER → `request.institution = request.user.institution`
- SUPERADMIN → `request.institution = Institution.objects.get(pk=session['active_institution_id'])`
- SUPERADMIN with no session → redirect to `institution-selector`

### `institution/middleware.py` — Complete Spec

```python
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
            try:
                request.institution = Institution.objects.get(pk=active_id, is_active=True)
            except Institution.DoesNotExist:
                # Clear stale session value and send to selector
                request.session.pop('active_institution_id', None)
                return redirect(reverse('institution-selector'))
        else:
            return redirect(reverse('institution-selector'))
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
```

### `institution/context_processors.py` — Complete Spec

```python
from ndas.custom_codes.choice import UserType


def institution_context(request):
    """
    Injects institution context into every template context.

    Provides:
      active_institution  — Institution object (or None for unresolved SUPERADMIN)
      user_type           — UserType string ('SUPERADMIN', 'ADMIN', 'USER')
      is_superadmin       — bool shorthand for user_type == SUPERADMIN

    Template usage (CORRECT):
      {{ active_institution.name }}
      {{ active_institution.logo.url }}
      {% if is_superadmin %}...{% endif %}
      {% if user_type == 'ADMIN' %}...{% endif %}

    NEVER use in templates:
      {{ request.user.institution.name }}  ← breaks SUPERADMIN context switching
      {% if request.user.is_superuser %}   ← use is_superadmin instead
    """
    if not request.user.is_authenticated:
        return {}

    active_institution = getattr(request, 'institution', None)
    user_type = getattr(request.user, 'user_type', UserType.USER)
    is_superadmin = (user_type == UserType.SUPERADMIN)

    return {
        'active_institution': active_institution,
        'user_type': user_type,
        'is_superadmin': is_superadmin,
    }
```

### `institution/urls.py` — Minimal Stub for Story 1.3

```python
from django.urls import path
from . import views

app_name = 'institution'

urlpatterns = [
    path('', views.institution_selector, name='institution-selector'),
    # Story 2.1 adds: institution card grid, add form, context switching
    # Story 2.2 adds: superadmin dashboard, overlay switch
    # Story 3.x adds: admin dashboard, user management, branding
]
```

### `institution/views.py` — Stub for Story 1.3

```python
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


@login_required(login_url='user-login')
def institution_selector(request):
    """
    Institution selector screen (STUB — full implementation in Story 2.1).
    Redirects to patient manager until Story 2.1 builds the full selector UI.
    """
    return redirect('patient-manager')
```

**Story 2.1** replaces this stub with the full card-grid selector implementation.

### `ndas/settings.py` — MIDDLEWARE Change

**Line 51** currently reads:
```python
'users.middleware.SubscriptionCheckMiddleware',
```

Change to:
```python
'institution.middleware.InstitutionContextMiddleware',
```

The full MIDDLEWARE list after the change:
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',           # 1
    'whitenoise.middleware.WhiteNoiseMiddleware',              # 2
    'csp.middleware.CSPMiddleware',                            # 3
    'ndas.custom_codes.security_middleware.AdditionalSecurityHeadersMiddleware',  # 4
    'django.contrib.sessions.middleware.SessionMiddleware',    # 5
    'django.middleware.common.CommonMiddleware',               # 6
    'django.middleware.csrf.CsrfViewMiddleware',               # 7
    'django.contrib.auth.middleware.AuthenticationMiddleware', # 8
    'users.middleware.UserActivityMiddleware',                 # 9
    'django.contrib.messages.middleware.MessageMiddleware',    # 10
    'django.middleware.clickjacking.XFrameOptionsMiddleware',  # 11
    'django_user_agents.middleware.UserAgentMiddleware',       # 12
    'institution.middleware.InstitutionContextMiddleware',     # 13 ← REPLACED
]
# production appends SecurityHeadersValidationMiddleware (14)
```

**Do NOT move any other entry.** Middleware order is security-critical in this project.

### `ndas/settings.py` — TEMPLATES Context Processor Addition

Current `context_processors` list (lines ~66–71):
```python
'context_processors': [
    'django.template.context_processors.debug',
    'django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
],
```

Add at the end:
```python
'context_processors': [
    'django.template.context_processors.debug',
    'django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
    'institution.context_processors.institution_context',  # ← ADD
],
```

### `ndas/urls.py` — Institution URL Include

Add the institution include BEFORE the patients root include (`path("", ...)`):

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("users/", include("users.urls")),
    path("reports/", include("reports.urls")),
    path("problems/", include("problemlist.urls")),
    path("institution/", include("institution.urls")),   # ← ADD (before root catch-all)
    path("", include("patients.urls")),                  # root catch-all — must stay last
    path("djrichtextfield/", include("djrichtextfield.urls")),
    path("video/", include("video.urls")),
    path("debug/bootstrap/", views.debug_bootstrap, name="debug-bootstrap"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

**Why before patients**: `path("", ...)` is a root catch-all. If institution/ is added after it, Django would still match institution URLs correctly because Django tests patterns in order and `institution/` is a more specific prefix. But placing it before is explicit and conventional.

### GRACE Period POST Blocking — Detail

**`_check_subscription` GRACE branch logic:**
- Method is `GET` → allow, return `None`
- Method is `POST` AND path starts with `/referral/` → allow (FR48: active referrals exempt)
- Method is `POST` AND any other path → add warning `messages.warning`, redirect to `HTTP_REFERER`

**Why redirect to `HTTP_REFERER`**: The POST (e.g. submitting a form) is blocked. Redirecting to the referring page keeps the user on the form with the warning message visible. This is a better UX than a hard 403 page.

**Story 4 enhancement**: When the referral app is built, the GRACE exemption check can be made more precise (checking for an active referral UUID). For now, all `/referral/` paths are exempt, which is safe.

### `subscription-info` URL Dependency

Both the Phase 1 fallback and the EXPIRED branch reference `reverse('subscription-info')`. This URL name must exist in `users.urls` — it was present in the original `SubscriptionCheckMiddleware` and is part of Phase 1 (Story 1.1 didn't modify users.urls). If this URL doesn't resolve, Django will raise `NoReverseMatch` on first expired user access. Verify by running `python manage.py shell -c "from django.urls import reverse; print(reverse('subscription-info'))"`.

### Test Code Pattern

```python
# institution/tests/test_middleware.py
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class InstitutionContextMiddlewareTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.institution = Institution.objects.create(
            name='Test Hospital',
            slug='test-hospital',
            subscription_status=SubscriptionStatus.ACTIVE,
        )
        self.institution_grace = Institution.objects.create(
            name='Grace Hospital',
            slug='grace-hospital',
            subscription_status=SubscriptionStatus.GRACE,
        )
        self.institution_expired = Institution.objects.create(
            name='Expired Hospital',
            slug='expired-hospital',
            subscription_status=SubscriptionStatus.EXPIRED,
        )

    def _make_clinician(self, username, institution=None):
        return User.objects.create_user(
            username=username, password='testpass123',
            first_name='Test', last_name='User',
            position='Medical Officer', mobile_primary='0771234567',
            user_type=UserType.USER,
            institution=institution,
        )

    def test_admin_user_request_sets_institution(self):
        """AC #1: ADMIN/USER request sets request.institution from user FK."""
        user = self._make_clinician('clinician1', self.institution)
        response = self.client.get('/patients/', **{'HTTP_HOST': 'testserver'})
        # NOTE: Full middleware test requires client login; use RequestFactory for unit tests.
        # Integration test verifiable via response context:
        self.client.force_login(user)
        response = self.client.get('/')
        # request.institution set by middleware before view executes
        # Test via context processor: active_institution should be in context
        self.assertEqual(response.context.get('active_institution'), self.institution)

    def test_grace_institution_get_allowed(self):
        """AC #4: GRACE + GET request is allowed."""
        user = self._make_clinician('clinician2', self.institution_grace)
        self.client.force_login(user)
        response = self.client.get('/')
        # Should not redirect to subscription-info
        self.assertNotEqual(response.status_code, 302)

    def test_context_processor_anonymous_returns_empty(self):
        """AC #6: Anonymous requests get empty context."""
        from institution.context_processors import institution_context
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        factory = RequestFactory()
        request = factory.get('/')
        request.user = AnonymousUser()
        result = institution_context(request)
        self.assertEqual(result, {})

    def test_context_processor_injects_variables(self):
        """AC #6: Authenticated requests get active_institution, user_type, is_superadmin."""
        from institution.context_processors import institution_context
        factory = RequestFactory()
        request = factory.get('/')
        user = self._make_clinician('clinician3', self.institution)
        request.user = user
        request.institution = self.institution
        result = institution_context(request)
        self.assertIn('active_institution', result)
        self.assertIn('user_type', result)
        self.assertIn('is_superadmin', result)
        self.assertEqual(result['active_institution'], self.institution)
        self.assertFalse(result['is_superadmin'])
```

### Project Structure Notes

**Files to CREATE in this story:**
- `institution/middleware.py`
- `institution/context_processors.py`
- `institution/urls.py` (minimal stub)
- `institution/views.py` (stub institution_selector view)
- `institution/tests/test_middleware.py`

**Files to MODIFY in this story:**
- `ndas/settings.py` — replace SubscriptionCheckMiddleware; add context processor
- `ndas/urls.py` — add `path("institution/", include("institution.urls"))`

**Files NOT touched in this story:**
- `users/middleware.py` — `SubscriptionCheckMiddleware` stays in users/middleware.py (but is no longer in MIDDLEWARE list); `UserActivityMiddleware` remains unchanged at position 9
- `users/models.py` — `Subscription` model still referenced by Phase 1 fallback in this middleware
- `institution/models.py` — Institution model unchanged
- `users/models.py` CustomUser — unchanged (was modified in Story 1.2)
- `src/base.html` — `{% superadmin_overlay %}` tag added in Story 2.2; `{{ active_institution }}` usage in base.html added in Story 3.3

### References

- Architecture: Middleware stack and position 13 replacement [Source: `_bmad-output/planning-artifacts/architecture.md#Architectural Boundaries`]
- Architecture: InstitutionContextMiddleware context resolution logic [Source: `_bmad-output/planning-artifacts/architecture.md#Data Architecture`]
- Architecture: institution_context context processor with anonymous guard [Source: `_bmad-output/planning-artifacts/architecture.md#Coherence Validation`]
- Architecture: Feature flag gating [Source: `_bmad-output/planning-artifacts/architecture.md#Infrastructure & Deployment`]
- Architecture: GRACE exemption for active referrals [Source: `_bmad-output/planning-artifacts/architecture.md#Authentication & Security`]
- Epics: Story 1.3 ACs [Source: `_bmad-output/planning-artifacts/epics.md#Story 1.3`]
- Existing middleware pattern: `MiddlewareMixin` [Source: `ndas/custom_codes/security_middleware.py`]
- Existing `SubscriptionCheckMiddleware` (Phase 1 logic to mirror) [Source: `users/middleware.py`]
- Current MIDDLEWARE list in settings [Source: `ndas/settings.py` lines 38–56]
- Current TEMPLATES context_processors [Source: `ndas/settings.py` lines 66–71]
- Current `ndas/urls.py` — patients root catch-all ordering [Source: `ndas/urls.py`]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
