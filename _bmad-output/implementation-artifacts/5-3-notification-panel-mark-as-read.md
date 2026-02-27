# Story 5.3: Notification Panel & Mark as Read

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **clinician**,
I want to open a notification panel showing all my recent alerts with links to the relevant referral threads, and mark them as read,
So that I can action notifications directly and keep my unread count accurate.

## Acceptance Criteria

1. **Given** the clinician clicks the navbar bell icon
   **When** the dropdown opens
   **Then** a list of recent notifications is loaded via HTMX into `#notification-panel-container`
   **And** each notification shows: type label, title, body, timestamp, and a clickable link to the referral thread

2. **Given** the notification list renders
   **When** both unread and read notifications are present
   **Then** unread notifications are visually distinguished with a highlighted background or bold title

3. **Given** the clinician clicks a notification link (HTMX `GET` to `notification_mark_read`)
   **When** the navigation occurs
   **Then** the notification's `is_read` is set to `True`
   **And** the response redirects to the notification's `link` URL (the referral thread)
   **And** the bell count decrements by 1 on the next poll

4. **Given** the clinician clicks "Mark all read"
   **When** the HTMX `POST` to `notification_mark_all_read` completes
   **Then** all `Notification` records where `recipient=request.user` and `institution=request.institution` have `is_read=True`
   **And** the panel re-renders showing all notifications as read

5. **Given** the notification panel queries notifications
   **When** the query runs
   **Then** only notifications where `recipient=request.user` and `institution=request.institution` are returned
   **And** results are ordered by `created_at` descending (most recent first)
   **And** the list is limited to the 20 most recent notifications (pagination not required)

## Tasks / Subtasks

- [x] Task 1: Add `notification_panel` view to `referral/views.py` (AC: #1, #2, #5)
  - [x] `@login_required`, `@require_GET`
  - [x] Queries `Notification.objects.filter(recipient=request.user, institution=request.institution).order_by('-created_at')[:20]`
  - [x] Returns `render(request, 'referral/notification_panel.html', {'notifications': notifications})`
  - [x] See exact view code in Dev Notes

- [x] Task 2: Add `notification_mark_read` view to `referral/views.py` (AC: #3)
  - [x] `@login_required`, `@require_GET`
  - [x] `get_object_or_404(Notification, id=pk, recipient=request.user, institution=request.institution)`
  - [x] Sets `is_read=True`, saves, then redirects to `notification.link` (or inbox if link is empty)
  - [x] See exact view code in Dev Notes

- [x] Task 3: Add `notification_mark_all_read` view to `referral/views.py` (AC: #4)
  - [x] `@login_required`, `@require_http_methods(["POST"])`
  - [x] Bulk update: `Notification.objects.filter(recipient=request.user, institution=request.institution).update(is_read=True)`
  - [x] Returns re-rendered `notification_panel` response (HTMX target: `#notification-panel-container`)
  - [x] See exact view code in Dev Notes

- [x] Task 4: Add 3 URLs to `referral/urls.py` (AC: #1, #3, #4)
  - [x] `path('notifications/panel/', views.notification_panel, name='notification-panel')`
  - [x] `path('notifications/<int:pk>/read/', views.notification_mark_read, name='notification-mark-read')`
  - [x] `path('notifications/mark-all-read/', views.notification_mark_all_read, name='notification-mark-all-read')`

- [x] Task 5: Create `templates/referral/notification_panel.html` (AC: #1, #2, #4)
  - [x] AdminLTE dropdown list style: `<div class="dropdown-item">` per notification
  - [x] Unread items: `bg-light` or bold title class
  - [x] "Mark all read" button at footer — HTMX POST to `notification-mark-all-read`
  - [x] Empty state when no notifications
  - [x] See exact template in Dev Notes

- [x] Task 6: Update `templates/src/navbar.html` panel container to load via HTMX on click (AC: #1)
  - [x] The `#notification-panel-container` div (added in Story 5.2) should load the panel on bell click
  - [x] `hx-get="{% url 'referral:notification-panel' %}"` on `#notification-panel-container`
  - [x] `hx-trigger="show.bs.dropdown from:closest .nav-item once"` — loads panel on first bell open
  - [x] See exact template diff in Dev Notes

- [x] Task 7: Write tests in `referral/tests/test_notification_panel.py` (AC: #1–#5)
  - [x] See exact test code in Dev Notes

## Dev Notes

### Story 5.3 Position

Story 5.3 = **Step 14** (final story — notification panel + mark as read):
```
    ├── Story 5.2: notification bell + real-time count  ← done
    └── Story 5.3: notification panel + mark as read  ← THIS STORY (FINAL)
```

**FR Coverage:** FR38 (notification panel with unread/read state), FR70 (mark-as-read action per notification and bulk).

---

### Task 1: `notification_panel` View

Add to `referral/views.py`:

```python
@login_required(login_url="user-login")
@require_GET
def notification_panel(request):
    """
    HTMX endpoint: returns rendered notification panel for dropdown (FR38, FR70).

    Limited to 20 most recent notifications for the current user+institution.
    Loaded into #notification-panel-container on bell click.
    """
    from referral.models import Notification
    notifications = Notification.objects.filter(
        recipient=request.user,
        institution=request.institution,
    ).order_by('-created_at')[:20]
    return render(request, 'referral/notification_panel.html', {
        'notifications': notifications,
    })
```

---

### Task 2: `notification_mark_read` View

Add to `referral/views.py`:

```python
@login_required(login_url="user-login")
@require_GET
def notification_mark_read(request, pk):
    """
    Mark a single notification as read and redirect to its target link (FR70).

    Scoped to recipient=request.user and institution=request.institution to
    prevent cross-user reads.
    """
    from referral.models import Notification
    notif = get_object_or_404(
        Notification,
        id=pk,
        recipient=request.user,
        institution=request.institution,
    )
    if not notif.is_read:
        notif.is_read = True
        notif.last_edit_by = request.user
        notif.save(update_fields=['is_read', 'last_edit_by', 'updated_at'])

    # Redirect to the notification's target link or inbox fallback
    target = notif.link if notif.link else reverse('referral:referral-inbox')
    return redirect(target)
```

---

### Task 3: `notification_mark_all_read` View

Add to `referral/views.py`:

```python
@login_required(login_url="user-login")
@require_http_methods(["POST"])
def notification_mark_all_read(request):
    """
    Mark all notifications for current user+institution as read (FR70).

    Returns re-rendered panel for HTMX swap into #notification-panel-container.
    """
    from referral.models import Notification
    Notification.objects.filter(
        recipient=request.user,
        institution=request.institution,
        is_read=False,
    ).update(is_read=True)

    # Re-render panel showing all-read state
    notifications = Notification.objects.filter(
        recipient=request.user,
        institution=request.institution,
    ).order_by('-created_at')[:20]
    return render(request, 'referral/notification_panel.html', {
        'notifications': notifications,
    })
```

---

### Task 4: URLs in `referral/urls.py`

Add to `urlpatterns`:

```python
path('notifications/panel/', views.notification_panel, name='notification-panel'),
path('notifications/<int:pk>/read/', views.notification_mark_read, name='notification-mark-read'),
path('notifications/mark-all-read/', views.notification_mark_all_read, name='notification-mark-all-read'),
```

---

### Task 5: `templates/referral/notification_panel.html`

Create `templates/referral/notification_panel.html`:

```html
{% load humanize %}
{% if notifications %}
  <span class="dropdown-item dropdown-header">
    Recent Notifications
  </span>
  <div class="dropdown-divider"></div>

  {% for notif in notifications %}
  <a href="{% url 'referral:notification-mark-read' notif.pk %}"
     class="dropdown-item {% if not notif.is_read %}bg-light{% endif %}">
    <div class="media">
      <div class="media-body">
        <p class="mb-0 {% if not notif.is_read %}font-weight-bold{% endif %}">
          {{ notif.title }}
        </p>
        {% if notif.body %}
        <p class="text-muted text-sm mb-0">{{ notif.body|truncatechars:80 }}</p>
        {% endif %}
        <p class="text-muted text-xs mb-0">{{ notif.created_at|naturaltime }}</p>
      </div>
    </div>
  </a>
  {% if not forloop.last %}
  <div class="dropdown-divider"></div>
  {% endif %}
  {% endfor %}

  <div class="dropdown-divider"></div>
  <form method="post"
        action="{% url 'referral:notification-mark-all-read' %}"
        hx-post="{% url 'referral:notification-mark-all-read' %}"
        hx-target="#notification-panel-container"
        hx-swap="innerHTML">
    {% csrf_token %}
    <button type="submit" class="dropdown-item text-center text-sm">
      <i class="fas fa-check-double mr-1"></i> Mark all as read
    </button>
  </form>

{% else %}
  <span class="dropdown-item text-muted text-sm py-2">
    <i class="far fa-bell-slash mr-1"></i> No notifications
  </span>
{% endif %}
```

---

### Task 6: Update Navbar Panel Container (diff on `templates/src/navbar.html`)

The `#notification-panel-container` div that was added in Story 5.2 needs HTMX wiring
to load the panel when the bell dropdown is opened.

Replace the inner container from Story 5.2:
```html
    <div id="notification-panel-container">
      <span class="dropdown-item text-muted text-sm">Loading notifications…</span>
    </div>
```

With:
```html
    <div id="notification-panel-container"
         hx-get="{% url 'referral:notification-panel' %}"
         hx-trigger="show.bs.dropdown from:closest .nav-item once"
         hx-swap="innerHTML">
      <span class="dropdown-item text-muted text-sm">Loading notifications…</span>
    </div>
```

**Explanation of `hx-trigger="show.bs.dropdown from:closest .nav-item once"`:**
- `show.bs.dropdown` — Bootstrap 4 event fired when a dropdown is opened
- `from:closest .nav-item` — listens on the parent `<li class="nav-item dropdown">`
- `once` — loads only once per page (prevents reload on every open); Story 5.2's `every 60s` polling on the count badge handles freshness

If the Bootstrap 4 event doesn't fire reliably, an alternative is:
```html
hx-trigger="click from:closest .nav-link once"
```

---

### Task 7: `referral/tests/test_notification_panel.py`

```python
"""
referral/tests/test_notification_panel.py
Tests for notification panel and mark-as-read views (Story 5.3 — FR38, FR70).
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, NotificationType
from referral.models import Notification

User = get_user_model()


class NotificationPanelBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_np', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771000030',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(
            name='Panel Inst', slug='panel-inst',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.user = User.objects.create_user(
            username='panel_user', password='Testpass1!',
            first_name='Panel', last_name='User',
            position='Medical Officer', mobile_primary='0771000031',
            user_type=UserType.USER, institution=self.inst,
        )
        self.other_user = User.objects.create_user(
            username='other_user_np', password='Testpass1!',
            first_name='Other', last_name='User',
            position='Consultant', mobile_primary='0771000032',
            user_type=UserType.USER, institution=self.inst,
        )

    def _make_notification(self, user=None, is_read=False, title='Test Notification'):
        user = user or self.user
        return Notification.objects.create(
            recipient=user,
            notification_type=NotificationType.REFERRAL_RECEIVED,
            title=title,
            body='Test notification body.',
            link='/referral/inbox/',
            is_read=is_read,
            institution=self.inst,
            added_by=user,
            last_edit_by=user,
        )


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class NotificationPanelViewTest(NotificationPanelBase):
    def test_panel_returns_200(self):
        """AC #1: notification-panel endpoint returns 200."""
        self._make_notification()
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('referral:notification-panel'))
        self.assertEqual(response.status_code, 200)

    def test_panel_shows_notification_title(self):
        """AC #1: Panel renders notification title."""
        self._make_notification(title='Referral Notification Title')
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('referral:notification-panel'))
        self.assertContains(response, 'Referral Notification Title')

    def test_panel_excludes_other_users_notifications(self):
        """AC #5: Only own notifications are returned."""
        self._make_notification(user=self.other_user, title='Other User Notification')
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('referral:notification-panel'))
        self.assertNotContains(response, 'Other User Notification',
            'AC #5: Other user notifications must not appear in panel')

    def test_panel_shows_empty_state_when_no_notifications(self):
        """AC #1: Panel renders empty state when no notifications."""
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('referral:notification-panel'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No notifications')


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class NotificationMarkReadTest(NotificationPanelBase):
    def test_mark_read_sets_is_read_true(self):
        """AC #3: Clicking notification marks it as read."""
        notif = self._make_notification(is_read=False)
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('referral:notification-mark-read', args=[notif.pk]))
        # Should redirect to notification's link
        self.assertEqual(response.status_code, 302)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read, 'AC #3: Notification must be marked as read after clicking')

    def test_mark_read_prevents_cross_user_access(self):
        """AC #5: Cannot mark another user's notification as read."""
        other_notif = self._make_notification(user=self.other_user)
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('referral:notification-mark-read', args=[other_notif.pk]))
        self.assertEqual(response.status_code, 404,
            'AC #5: Cross-user notification access must return 404')

    def test_mark_read_redirects_to_notification_link(self):
        """AC #3: After marking read, redirects to notification's link."""
        notif = self._make_notification()
        notif.link = '/referral/inbox/'
        notif.save()
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('referral:notification-mark-read', args=[notif.pk]))
        self.assertRedirects(response, '/referral/inbox/', fetch_redirect_response=False)


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class NotificationMarkAllReadTest(NotificationPanelBase):
    def test_mark_all_read_sets_all_is_read_true(self):
        """AC #4: Mark all read sets is_read=True on all user's unread notifications."""
        self._make_notification(is_read=False, title='Notif 1')
        self._make_notification(is_read=False, title='Notif 2')
        self._make_notification(is_read=True, title='Already Read')

        client = Client()
        client.force_login(self.user)
        response = client.post(reverse('referral:notification-mark-all-read'))
        self.assertEqual(response.status_code, 200)

        unread_count = Notification.objects.filter(
            recipient=self.user, institution=self.inst, is_read=False,
        ).count()
        self.assertEqual(unread_count, 0,
            'AC #4: All notifications must be marked as read after mark-all-read')

    def test_mark_all_read_does_not_affect_other_users(self):
        """AC #5: Mark-all-read only affects own notifications."""
        other_notif = self._make_notification(user=self.other_user, is_read=False)

        client = Client()
        client.force_login(self.user)
        client.post(reverse('referral:notification-mark-all-read'))

        other_notif.refresh_from_db()
        self.assertFalse(other_notif.is_read,
            'AC #5: Other users notifications must not be affected by mark-all-read')
```

---

### Project Structure Notes

**Files MODIFIED in this story:**
- `referral/views.py` — add `notification_panel`, `notification_mark_read`, `notification_mark_all_read`
- `referral/urls.py` — add 3 notification URLs
- `templates/src/navbar.html` — add HTMX load trigger to `#notification-panel-container`

**Files CREATED in this story:**
- `templates/referral/notification_panel.html` — dropdown panel template
- `referral/tests/test_notification_panel.py` — 7 tests

---

### References

- FR38: In-app notification panel visible at all times in navbar [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.2`]
- FR70: Mark notifications as read (individual and bulk) [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.3`]
- NFR23: Notification delivery ≤120 seconds [Source: `_bmad-output/planning-artifacts/architecture.md#NFR23`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Added 3 views to referral/views.py: notification_panel (GET, latest 20), notification_mark_read (GET → redirect), notification_mark_all_read (POST → re-rendered panel).
- Added `from django.urls import reverse` import to views.py for the inbox fallback redirect.
- Added 3 URLs to referral/urls.py (notification-panel, notification-mark-read, notification-mark-all-read).
- Created templates/referral/notification_panel.html with per-notification links, unread highlighting (bg-light + font-weight-bold), "Mark all as read" HTMX form, and empty state.
- Replaced `{% load humanize %}` with standard `|date:"d M Y H:i"` filter (django.contrib.humanize not installed in this project).
- Updated templates/src/navbar.html panel container with hx-get + hx-trigger="show.bs.dropdown from:closest .nav-item once" HTMX attributes. Both 5.2 and 5.3 navbar changes combined in single edit.
- Created referral/tests/test_notification_panel.py with 9 tests (all pass).
- Fixed test assertNotContains calls: message must use msg_prefix= keyword arg (3rd positional arg is status_code, not message).
- Added STATIC_OVERRIDE to panel tests to avoid ManifestStaticFilesStorage recursion on 404 pages.
- All 52 referral tests pass.

**Code Review Fixes (2026-02-27):**
- [M4] Added `@ratelimit(key='user_or_ip', rate='10/m')` to `notification_mark_read` and `notification_mark_all_read` — both modify database state and require rate limiting per project standards.

### File List

- referral/views.py (MODIFIED — added notification_panel, notification_mark_read, notification_mark_all_read views + `from django.urls import reverse`; MODIFIED in review: rate limits on write endpoints)
- referral/urls.py (MODIFIED — added 3 notification URLs)
- templates/referral/notification_panel.html (CREATED)
- templates/src/navbar.html (MODIFIED — panel container HTMX wiring)
- referral/tests/test_notification_panel.py (CREATED)
