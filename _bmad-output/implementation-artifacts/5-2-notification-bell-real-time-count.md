# Story 5.2: Notification Bell & Real-Time Count

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **clinician**,
I want an unread notification count displayed in the navbar that refreshes automatically,
So that I can see pending referral activity within 120 seconds of it occurring without leaving my current page.

## Acceptance Criteria

1. **Given** the navbar bell icon is wired up in `templates/src/navbar.html`
   **When** any authenticated page renders
   **Then** the bell icon displays the current unread notification count in a badge (`#notification-bell-count`)
   **And** the bell is only rendered for authenticated users with `request.institution` set

2. **Given** the bell icon uses HTMX polling on `#notification-bell-count`
   **When** 60 seconds elapse after page load
   **Then** `hx-get="{% url 'referral:notification-count' %}"` fires automatically
   **And** `#notification-bell-count` is updated with the latest unread count

3. **Given** a new `Notification` record is created (by Story 5.1 signals)
   **When** up to 120 seconds elapse
   **Then** the navbar bell count increments to reflect the new notification — satisfying NFR23

4. **Given** the `notification_count` view at `/referral/notifications/count/`
   **When** the request is processed
   **Then** it returns only the unread count for `request.user` scoped to `request.institution`
   **And** it returns an empty fragment (zero count hidden) when count is zero

5. **Given** the clinician has zero unread notifications
   **When** the bell renders
   **Then** the badge is not shown (count hidden) — no error is raised and no "0" badge appears

## Tasks / Subtasks

- [x] Task 1: Add `notification_count` view to `referral/views.py` (AC: #4, #5)
  - [x] `@login_required`, `@require_GET`
  - [x] Queries `Notification.objects.filter(recipient=request.user, institution=request.institution, is_read=False).count()`
  - [x] Returns `render(request, 'referral/notification_count_badge.html', {'count': count})`
  - [x] See exact view code in Dev Notes

- [x] Task 2: Add `notification-count` URL to `referral/urls.py` (AC: #4)
  - [x] `path('notifications/count/', views.notification_count, name='notification-count')`

- [x] Task 3: Create `templates/referral/notification_count_badge.html` partial (AC: #4, #5)
  - [x] Renders badge only when count > 0
  - [x] See exact template in Dev Notes

- [x] Task 4: Activate the navbar bell in `templates/src/navbar.html` (AC: #1, #2, #3)
  - [x] The bell icon block at lines 113–139 is currently commented out
  - [x] Uncomment and wire up with HTMX polling attributes
  - [x] Bell only shown for authenticated users with institution context
  - [x] See exact template fragment in Dev Notes

- [x] Task 5: Write tests in `referral/tests/test_notification_bell.py` (AC: #1–#5)
  - [x] See exact test code in Dev Notes

## Dev Notes

### Story 5.2 Position

Story 5.2 = **Step 13** (notification bell + HTMX polling):
```
    ├── Story 5.1: notification model + signals  ← done
    ├── Story 5.2: notification bell + real-time count  ← THIS STORY
    └── Story 5.3: notification panel + mark as read
```

**FR Coverage:** FR38 (notification bell in navbar), NFR23 (≤120s delivery = 60s poll interval).

---

### Task 1: `notification_count` View

Add to `referral/views.py`:

```python
@login_required(login_url="user-login")
@require_GET
def notification_count(request):
    """
    HTMX endpoint: returns unread notification count badge fragment (FR38, NFR23).

    Polled every 60 seconds by the navbar bell (hx-trigger="every 60s").
    Returns an empty fragment (no badge) when count is zero.
    """
    from referral.models import Notification
    count = Notification.objects.filter(
        recipient=request.user,
        institution=request.institution,
        is_read=False,
    ).count()
    return render(request, 'referral/notification_count_badge.html', {'count': count})
```

---

### Task 2: URL in `referral/urls.py`

Add to `urlpatterns`:

```python
path('notifications/count/', views.notification_count, name='notification-count'),
```

---

### Task 3: `templates/referral/notification_count_badge.html`

Create `templates/referral/notification_count_badge.html`:

```html
{% if count > 0 %}
<span class="badge badge-warning navbar-badge">{{ count }}</span>
{% endif %}
```

This partial is the **entire** HTMX swap target — only renders the badge element itself.
When count is zero, the swap replaces the previous badge with nothing (empty fragment).

---

### Task 4: Navbar Bell in `templates/src/navbar.html`

The commented-out bell block (currently at lines ~113–139) should be replaced with the
following. The existing commented-out block must be removed entirely and replaced with
this wired-up version:

```html
{# Notification Bell — only for institution-scoped users (FR38) #}
{% if request.user.is_authenticated and request.institution %}
<li class="nav-item dropdown">
  <a class="nav-link" data-toggle="dropdown" href="#" aria-label="Notifications">
    <i class="far fa-bell"></i>
    {# HTMX polling: fires every 60s, satisfies NFR23 (≤120s delivery) #}
    <span id="notification-bell-count"
          hx-get="{% url 'referral:notification-count' %}"
          hx-trigger="load, every 60s"
          hx-swap="innerHTML">
      {# Initial count loaded on page load via hx-trigger="load" #}
    </span>
  </a>
  {# Panel loaded in Story 5.3 #}
  <div class="dropdown-menu dropdown-menu-lg dropdown-menu-right"
       style="min-width: 280px;">
    <div id="notification-panel-container">
      <span class="dropdown-item text-muted text-sm">Loading notifications…</span>
    </div>
  </div>
</li>
{% endif %}
```

**Key attributes:**
- `hx-trigger="load, every 60s"` — fires immediately on page load (populates initial count) and every 60 seconds thereafter
- `hx-swap="innerHTML"` — replaces the badge span's inner HTML only
- `hx-get="{% url 'referral:notification-count' %}"` — calls the view from Task 1
- Wrapped in `{% if request.user.is_authenticated and request.institution %}` — SUPERADMIN without institution context does not see the bell

---

### Task 5: `referral/tests/test_notification_bell.py`

```python
"""
referral/tests/test_notification_bell.py
Tests for notification bell endpoint and HTMX count view (Story 5.2 — FR38, NFR23).
"""
import uuid
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, NotificationType
from referral.models import Notification

User = get_user_model()


class NotificationBellBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_bell', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771000020',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(
            name='Bell Inst', slug='bell-inst',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.user = User.objects.create_user(
            username='bell_user', password='Testpass1!',
            first_name='Bell', last_name='User',
            position='Medical Officer', mobile_primary='0771000021',
            user_type=UserType.USER, institution=self.inst,
        )


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class NotificationCountViewTest(NotificationBellBase):
    def test_count_returns_200_for_authenticated_user(self):
        """AC #4: notification-count endpoint returns 200."""
        client = Client()
        client.force_login(self.user)
        url = reverse('referral:notification-count')
        response = client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_count_zero_returns_empty_fragment(self):
        """AC #5: Zero unread notifications returns empty (no badge element)."""
        client = Client()
        client.force_login(self.user)
        url = reverse('referral:notification-count')
        response = client.get(url)
        self.assertNotIn(b'badge', response.content,
            'AC #5: Zero count must not render a badge')

    def test_count_returns_badge_when_unread_notifications_exist(self):
        """AC #1: Badge rendered when unread notifications exist."""
        Notification.objects.create(
            recipient=self.user,
            notification_type=NotificationType.REFERRAL_RECEIVED,
            title='Test notification',
            body='Test body',
            link='/referral/thread/test/',
            is_read=False,
            institution=self.inst,
            added_by=self.user,
            last_edit_by=self.user,
        )
        client = Client()
        client.force_login(self.user)
        url = reverse('referral:notification-count')
        response = client.get(url)
        self.assertIn(b'1', response.content,
            'AC #1: Count badge must show 1 unread notification')

    def test_count_excludes_read_notifications(self):
        """AC #4: Read notifications are not counted."""
        Notification.objects.create(
            recipient=self.user,
            notification_type=NotificationType.REFERRAL_RECEIVED,
            title='Read notification',
            is_read=True,  # Already read
            institution=self.inst,
            added_by=self.user,
            last_edit_by=self.user,
        )
        client = Client()
        client.force_login(self.user)
        url = reverse('referral:notification-count')
        response = client.get(url)
        self.assertNotIn(b'badge', response.content,
            'AC #4: Read notifications must not appear in unread count')

    def test_count_requires_authentication(self):
        """AC #1: Unauthenticated request redirects to login."""
        client = Client()
        url = reverse('referral:notification-count')
        response = client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response['Location'])
```

---

### Project Structure Notes

**Files MODIFIED in this story:**
- `referral/views.py` — add `notification_count` view
- `referral/urls.py` — add `notification-count` URL
- `templates/src/navbar.html` — activate and wire bell with HTMX polling

**Files CREATED in this story:**
- `templates/referral/notification_count_badge.html` — HTMX swap target fragment
- `referral/tests/test_notification_bell.py` — 5 tests

---

### References

- FR38: In-app notification panel visible at all times in navbar [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.2`]
- NFR23: Notification delivery ≤120 seconds — satisfied by 60s poll interval [Source: `_bmad-output/planning-artifacts/architecture.md#NFR23`]
- Architecture: HTMX polling for notifications [Source: `_bmad-output/planning-artifacts/architecture.md#NotificationPolling`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Added notification_count view to referral/views.py (HTMX polling endpoint, returns badge fragment).
- Added notification-count URL to referral/urls.py.
- Created templates/referral/notification_count_badge.html (badge only when count > 0).
- Replaced commented-out navbar notifications block with HTMX-wired bell (hx-trigger="load, every 60s") in templates/src/navbar.html. Combined with Story 5.3 panel container wiring in one step.
- Created referral/tests/test_notification_bell.py with 5 tests (all pass).
- All 52 referral tests pass.

**Code Review Fixes (2026-02-27):**
- [M3] Added `@ratelimit(key='user_or_ip', rate='60/m')` to `notification_count` view — protects polling endpoint from abuse per project rate-limit standards.
- [M5] Added `if not request.institution: return HttpResponse('')` guard to `notification_count` — prevents silent incorrect behavior for SUPERADMIN or users without institution context.

### File List

- referral/views.py (MODIFIED — added notification_count view; MODIFIED in review: rate limit + None guard)
- referral/urls.py (MODIFIED — added notification-count URL)
- templates/referral/notification_count_badge.html (CREATED)
- templates/src/navbar.html (MODIFIED — HTMX bell activated)
- referral/tests/test_notification_bell.py (CREATED)
