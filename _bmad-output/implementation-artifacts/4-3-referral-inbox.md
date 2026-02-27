# Story 4.3: Referral Inbox

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **clinician**,
I want a unified inbox showing all my sent and received referral threads with their status,
So that I can track the status of every consultation at a glance and open any thread instantly.

## Acceptance Criteria

1. **Given** the clinician navigates to `/referral/inbox/`
   **When** the page loads
   **Then** a split-panel layout is displayed: thread list on the left (patient thumbnail, referring/receiving institution, date, status badge, unread indicator) and an empty thread panel on the right

2. **Given** the clinician has both sent and received referrals
   **When** the inbox renders
   **Then** both outgoing and incoming referrals appear in the thread list, each with a direction indicator (Sent / Received)

3. **Given** the clinician clicks a thread item in the left panel
   **When** the click is processed
   **Then** the referral thread is loaded into the right panel via `hx-get` HTMX partial — no full page reload occurs

4. **Given** a referral thread has an unread reply
   **When** it appears in the thread list
   **Then** an unread indicator (bold text or dot badge) is visible on that thread item

5. **Given** the clinician has no referrals yet
   **When** the inbox loads
   **Then** an empty state message is displayed in both panels without errors

## Tasks / Subtasks

- [ ] Task 1: Add `referral_inbox` view to `referral/views.py` (AC: #1, #2, #4, #5)
  - [ ] `@login_required`, `@require_GET`, `@handle_view_errors`
  - [ ] Queries: `ReferralSent.objects.for_institution(request.institution).filter(from_clinician=request.user)` + `ReferralReceived.objects.for_institution(request.institution).filter(to_clinician=request.user)`
  - [ ] Combine and sort by created_at descending
  - [ ] Annotate direction: 'sent' or 'received'
  - [ ] Unread indicator: `ReferralReceived.is_read == False`
  - [ ] See exact view code in Dev Notes

- [ ] Task 2: Add `referral_thread_panel` HTMX partial view to `referral/views.py` (AC: #3)
  - [ ] GET `/referral/thread/<uuid>/` — returns rendered thread panel partial
  - [ ] On GET: mark ReferralReceived as read (`is_read=True`) if the current user is `to_clinician`
  - [ ] See exact view code in Dev Notes (thread detail content covered more fully in Story 4.4)

- [ ] Task 3: Add inbox and thread panel URLs to `referral/urls.py` (AC: #1, #3)
  - [ ] `path('inbox/', views.referral_inbox, name='referral-inbox')`
  - [ ] `path('thread/<uuid:referral_uuid>/', views.referral_thread_panel, name='referral-thread-panel')`

- [ ] Task 4: Create `templates/referral/inbox.html` (AC: #1, #2, #4, #5)
  - [ ] Extend `src/base.html`; title "Referral Inbox"
  - [ ] AdminLTE split panel: left col-4 (thread list), right col-8 (thread panel placeholder)
  - [ ] Each thread item: direction badge, patient name, institutions, date, status badge, unread dot
  - [ ] hx-get on thread item → loads thread panel into `#thread-panel-container`
  - [ ] Empty state: shown when no threads exist
  - [ ] See exact template in Dev Notes

- [ ] Task 5: Create `templates/referral/thread_panel.html` (AC: #3)
  - [ ] Stub template for this story — full thread content added in Story 4.4
  - [ ] Must render without errors; placeholder "Thread loaded" message
  - [ ] See exact template in Dev Notes

- [ ] Task 6: Add "Referral Inbox" link to sidebar `templates/src/main_sidebar_menu.html` (AC: #1)
  - [ ] Under a new "Referrals" section or within existing navigation
  - [ ] Conditional: shown only when `MULTI_INSTITUTION_ENABLED` or always (for forward compatibility)
  - [ ] See exact placement in Dev Notes

- [ ] Task 7: Write tests in `referral/tests/test_inbox.py` (AC: #1–#5)
  - [ ] See exact test code in Dev Notes

## Dev Notes

### Story 4.3 Position in the 13-Step Sequence

Story 4.3 = **Step 10** (Referral inbox):

```
10. Referral inbox + thread UI:
    ├── Story 4.1: data models        ← done
    ├── Story 4.2: initiation         ← done
    ├── Story 4.3: inbox              ← THIS STORY
    ├── Story 4.4: thread view/reply
    ├── Story 4.5: lifecycle/closure
    └── Story 4.6: patient referrals tab
```

**Prerequisites:** Stories 4.1 + 4.2 done.

**FR Coverage:** FR63 (unified inbox — thread list + split panel), FR64 (status badge).

---

### Task 1: `referral_inbox` View

Add to `referral/views.py`:

```python
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_http_methods
from django_ratelimit.decorators import ratelimit
from ndas.custom_codes.error_handlers import handle_view_errors


@login_required(login_url="user-login")
@require_GET
@handle_view_errors(redirect_url='home', error_message='Failed to load referral inbox.')
def referral_inbox(request):
    """
    Unified referral inbox — shows sent and received referral threads (FR63).

    Split panel: thread list left, thread detail right (HTMX-loaded).
    """
    from referral.models import ReferralSent, ReferralReceived

    # Sent referrals: from this clinician at this institution
    sent_referrals = (
        ReferralSent.objects
        .for_institution(request.institution)
        .filter(from_clinician=request.user)
        .select_related('to_institution', 'to_clinician', 'patient')
        .order_by('-created_at')
    )

    # Received referrals: to this clinician at this institution
    received_referrals = (
        ReferralReceived.objects
        .for_institution(request.institution)
        .filter(to_clinician=request.user)
        .select_related('from_institution', 'to_clinician')
        .order_by('-created_at')
    )

    # Build unified thread list with direction annotation
    threads = []
    for ref in sent_referrals:
        threads.append({
            'direction':    'sent',
            'referral_uuid': ref.referral_uuid,
            'status':       ref.status,
            'patient_name': ref.patient.baby_name if ref.patient else ref.snapshot_data.get('demographics', {}).get('baby_name', 'Unknown'),
            'other_institution': ref.to_institution,
            'other_clinician':   ref.to_clinician,
            'created_at':   ref.created_at,
            'is_unread':    False,  # Sent items don't have unread state
            'obj':          ref,
        })
    for ref in received_referrals:
        threads.append({
            'direction':    'received',
            'referral_uuid': ref.referral_uuid,
            'status':       ref.status,
            'patient_name': ref.patient_name,
            'other_institution': ref.from_institution,
            'other_clinician':   ref.from_clinician_name,
            'created_at':   ref.created_at,
            'is_unread':    not ref.is_read,  # AC #4: unread indicator
            'obj':          ref,
        })

    # Sort combined list by created_at descending
    threads.sort(key=lambda t: t['created_at'], reverse=True)

    return render(request, 'referral/inbox.html', {
        'threads': threads,
        'thread_count': len(threads),
    })
```

---

### Task 2: `referral_thread_panel` HTMX Partial View

Add to `referral/views.py`:

```python
@login_required(login_url="user-login")
@require_GET
@handle_view_errors(redirect_url='referral:referral-inbox', error_message='Failed to load referral thread.')
def referral_thread_panel(request, referral_uuid):
    """
    HTMX partial: load referral thread into the right panel (FR62).

    AC #3: Called via hx-get from thread list item. Returns thread_panel.html partial.
    Marks ReferralReceived as read on first open.
    Story 4.4 extends this view with full thread content, frozen snapshot, and reply form.
    """
    from referral.models import ReferralSent, ReferralReceived, ReferralMessage

    # Try to find as sent (current user is sender)
    sent = ReferralSent.objects.filter(
        referral_uuid=referral_uuid,
        institution=request.institution,
    ).first()

    # Try to find as received (current user is receiver)
    received = ReferralReceived.objects.filter(
        referral_uuid=referral_uuid,
        institution=request.institution,
    ).first()

    if not sent and not received:
        from django.http import HttpResponse
        return HttpResponse('<p class="text-center text-danger">Referral not found or not accessible.</p>', status=404)

    # Mark as read if received and not yet read
    if received and not received.is_read and received.to_clinician == request.user:
        received.is_read = True
        received.save(update_fields=['is_read', 'updated_at'])

    # Load messages for this thread
    messages_qs = ReferralMessage.objects.filter(
        referral_uuid=referral_uuid
    ).select_related('sender', 'sender_institution').order_by('created_at')

    # Determine current status from the record we own
    current_record = sent or received
    status = current_record.status
    snapshot_data = current_record.snapshot_data

    is_sender = sent is not None
    is_closed = status == 'CLOSED'

    return render(request, 'referral/thread_panel.html', {
        'referral_uuid':  referral_uuid,
        'sent':           sent,
        'received':       received,
        'messages':       messages_qs,
        'status':         status,
        'snapshot_data':  snapshot_data,
        'is_sender':      is_sender,
        'is_closed':      is_closed,
    })
```

---

### Task 4: `templates/referral/inbox.html`

```django
{% extends 'src/base.html' %}
{% load static %}
{% block title %}Referral Inbox — NDAS{% endblock %}

{% block content_header %}
<div class="row mb-0">
  <div class="col-sm-6">
    <h1 class="m-0">Referral Inbox</h1>
    <small class="text-muted">{{ thread_count }} thread{{ thread_count|pluralize }}</small>
  </div>
  <div class="col-sm-6">
    <ol class="breadcrumb float-sm-right">
      <li class="breadcrumb-item active">Referral Inbox</li>
    </ol>
  </div>
</div>
{% endblock content_header %}

{% block main_content %}
<div class="container-fluid">
  <div class="row">

    {# ── Left Panel: Thread List ──────────────────────────────────────── #}
    <div class="col-lg-4 col-md-5">
      <div class="card card-primary card-outline">
        <div class="card-header">
          <h3 class="card-title">Threads</h3>
        </div>
        <div class="card-body p-0">
          {% if threads %}
          <ul class="list-unstyled mb-0">
            {% for thread in threads %}
            <li class="p-2 border-bottom {% if thread.is_unread %}bg-light{% endif %}"
                style="cursor:pointer;"
                hx-get="{% url 'referral:referral-thread-panel' thread.referral_uuid %}"
                hx-target="#thread-panel-container"
                hx-swap="innerHTML">
              <div class="d-flex justify-content-between align-items-start">
                <div class="flex-grow-1 mr-2">
                  {% if thread.is_unread %}
                  <span class="badge badge-primary badge-dot mr-1" title="Unread">●</span>
                  {% endif %}
                  <strong {% if thread.is_unread %}class="font-weight-bold"{% endif %}>
                    {{ thread.patient_name }}
                  </strong>
                  <div>
                    {% if thread.direction == 'sent' %}
                      <span class="badge badge-info badge-sm">Sent</span>
                      <small class="text-muted">→ {{ thread.other_institution.name|truncatechars:20 }}</small>
                    {% else %}
                      <span class="badge badge-success badge-sm">Received</span>
                      <small class="text-muted">← {{ thread.other_institution.name|truncatechars:20 }}</small>
                    {% endif %}
                  </div>
                  <small class="text-muted">{{ thread.created_at|date:"d M Y" }}</small>
                </div>
                <div class="text-right">
                  {% if thread.status == 'PENDING' %}
                    <span class="badge badge-warning">Pending</span>
                  {% elif thread.status == 'REPLIED' %}
                    <span class="badge badge-primary">Replied</span>
                  {% elif thread.status == 'CLOSED' %}
                    <span class="badge badge-secondary">Closed</span>
                  {% endif %}
                </div>
              </div>
            </li>
            {% endfor %}
          </ul>
          {% else %}
          {# AC #5: Empty state #}
          <div class="text-center text-muted p-4">
            <i class="fas fa-inbox fa-3x mb-2 d-block"></i>
            No referral threads yet.
          </div>
          {% endif %}
        </div>
      </div>
    </div>

    {# ── Right Panel: Thread Detail ────────────────────────────────────── #}
    <div class="col-lg-8 col-md-7">
      <div id="thread-panel-container">
        <div class="card card-outline">
          <div class="card-body text-center text-muted p-5">
            <i class="fas fa-comments fa-3x mb-2 d-block"></i>
            <p>Select a thread to view the consultation.</p>
          </div>
        </div>
      </div>
    </div>

  </div>
</div>
{% endblock %}
```

---

### Task 5: `templates/referral/thread_panel.html` (Stub — Full Content in Story 4.4)

```django
{# referral/thread_panel.html — Stub for Story 4.3. Extended in Story 4.4. #}
<div class="card card-outline">
  <div class="card-header">
    <h3 class="card-title">
      {% if sent %}
        Referral to {{ sent.to_institution.name }}
      {% elif received %}
        Referral from {{ received.from_institution.name }}
      {% endif %}
      — <span class="badge
          {% if status == 'PENDING' %}badge-warning
          {% elif status == 'REPLIED' %}badge-primary
          {% elif status == 'CLOSED' %}badge-secondary
          {% endif %}">
        {{ status }}
      </span>
    </h3>
  </div>
  <div class="card-body">
    {# Story 4.4 will add: patient header, frozen snapshot <details>, messages, reply form #}
    <p class="text-muted">Thread loaded. Full thread view implemented in Story 4.4.</p>
    <p><strong>Referral UUID:</strong> <code>{{ referral_uuid }}</code></p>
  </div>
</div>
```

---

### Task 6: Sidebar Menu Entry

In `templates/src/main_sidebar_menu.html`, add a new "Referrals" nav section before "Reports":

```django
{# Referrals — shown to all authenticated users #}
<li class="nav-header">REFERRALS</li>
<li class="nav-item {% if request.resolver_match.url_name == 'referral-inbox' %}active{% endif %}">
  <a href="{% url 'referral:referral-inbox' %}" class="nav-link">
    <i class="nav-icon fas fa-share-square"></i>
    <p>
      Referral Inbox
      {# Story 5.2 will add: unread count badge here via HTMX #}
    </p>
  </a>
</li>
```

---

### Task 7: `referral/tests/test_inbox.py`

```python
"""
referral/tests/test_inbox.py
Tests for Referral Inbox (Story 4.3 — FR63).
"""
import uuid
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, ReferralStatus
from referral.models import ReferralSent, ReferralReceived

User = get_user_model()


class InboxTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_inbox', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771221001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='Inbox Alpha', slug='inbox-alpha',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Inbox Beta', slug='inbox-beta',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.clinician_a = User.objects.create_user(
            username='clin_a_inbox', password='Testpass1!',
            first_name='Alpha', last_name='Clinician',
            position='Medical Officer', mobile_primary='0771221002',
            user_type=UserType.USER, institution=self.inst_a,
        )
        self.clinician_b = User.objects.create_user(
            username='clin_b_inbox', password='Testpass1!',
            first_name='Beta', last_name='Clinician',
            position='Medical Officer', mobile_primary='0771221003',
            user_type=UserType.USER, institution=self.inst_b,
        )
        from patients.models import Patient
        self.patient = Patient.objects.create(
            institution=self.inst_a,
            baby_name='Inbox Test Patient', mother_name='Test Mother',
            added_by=self.clinician_a, last_edit_by=self.clinician_a,
        )
        self.inbox_url = reverse('referral:referral-inbox')

    def _create_referral_pair(self):
        shared_uuid = uuid.uuid4()
        sent = ReferralSent.objects.create(
            from_institution=self.inst_a, to_institution=self.inst_b,
            institution=self.inst_a, patient=self.patient,
            from_clinician=self.clinician_a, to_clinician=self.clinician_b,
            referral_uuid=shared_uuid, initial_message='Test',
            snapshot_data={'schema_version': 1}, added_by=self.clinician_a, last_edit_by=self.clinician_a,
        )
        received = ReferralReceived.objects.create(
            to_institution=self.inst_b, from_institution=self.inst_a,
            institution=self.inst_b, patient_name='Inbox Test Patient',
            from_clinician_name='Alpha Clinician', to_clinician=self.clinician_b,
            referral_uuid=shared_uuid, initial_message='Test',
            snapshot_data={'schema_version': 1}, is_read=False,
            added_by=self.clinician_a, last_edit_by=self.clinician_a,
        )
        return sent, received


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class InboxAccessTest(InboxTestBase):
    def test_authenticated_user_can_access_inbox(self):
        client = Client()
        client.force_login(self.clinician_a)
        response = client.get(self.inbox_url)
        self.assertEqual(response.status_code, 200)


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class InboxEmptyStateTest(InboxTestBase):
    def test_empty_state_no_exception(self):
        """AC #5: Inbox loads without errors when no referrals exist."""
        client = Client()
        client.force_login(self.clinician_a)
        response = client.get(self.inbox_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['thread_count'], 0)


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class InboxThreadListTest(InboxTestBase):
    def test_sent_referral_appears_in_thread_list(self):
        """AC #2: Sent referral appears in clinician A's inbox."""
        self._create_referral_pair()
        client = Client()
        client.force_login(self.clinician_a)
        response = client.get(self.inbox_url)
        self.assertEqual(response.context['thread_count'], 1)
        thread = response.context['threads'][0]
        self.assertEqual(thread['direction'], 'sent')

    def test_received_referral_appears_in_thread_list(self):
        """AC #2: Received referral appears in clinician B's inbox."""
        self._create_referral_pair()
        client = Client()
        client.force_login(self.clinician_b)
        response = client.get(self.inbox_url)
        self.assertEqual(response.context['thread_count'], 1)
        thread = response.context['threads'][0]
        self.assertEqual(thread['direction'], 'received')

    def test_unread_indicator_on_received_thread(self):
        """AC #4: is_unread=True for unread received referral."""
        self._create_referral_pair()
        client = Client()
        client.force_login(self.clinician_b)
        response = client.get(self.inbox_url)
        thread = response.context['threads'][0]
        self.assertTrue(thread['is_unread'], "AC #4: Unread received referral must show is_unread=True")


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class InboxThreadPanelTest(InboxTestBase):
    def test_thread_panel_loads_via_get(self):
        """AC #3: Thread panel endpoint returns 200."""
        sent, received = self._create_referral_pair()
        client = Client()
        client.force_login(self.clinician_a)
        url = reverse('referral:referral-thread-panel', args=[sent.referral_uuid])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_thread_panel_marks_received_as_read(self):
        """AC #3: Opening thread panel marks ReferralReceived as is_read=True."""
        sent, received = self._create_referral_pair()
        self.assertFalse(received.is_read, "Precondition: must be unread")
        client = Client()
        client.force_login(self.clinician_b)
        url = reverse('referral:referral-thread-panel', args=[received.referral_uuid])
        client.get(url)
        received.refresh_from_db()
        self.assertTrue(received.is_read, "AC #3: Opening thread panel must mark received as is_read=True")
```

---

### Project Structure Notes

**Files CREATED in this story:**
- `templates/referral/inbox.html` — split-panel inbox template
- `templates/referral/thread_panel.html` — stub thread panel (extended in Story 4.4)
- `referral/tests/test_inbox.py` — 7+ tests

**Files MODIFIED in this story:**
- `referral/views.py` — add `referral_inbox` + `referral_thread_panel` views
- `referral/urls.py` — add `referral-inbox` + `referral-thread-panel` paths
- `templates/src/main_sidebar_menu.html` — add Referrals section with Inbox link

**Files NOT touched:**
- `referral/models.py` — no schema changes
- `templates/patients/view.html` — New Referral button added in Story 4.2

---

### References

- FR63: Unified referral inbox — thread list with split panel [Source: `_bmad-output/planning-artifacts/epics.md#Story 4.3`]
- FR64: Status badge (PENDING/REPLIED/CLOSED) visible in thread list [Source: `_bmad-output/planning-artifacts/epics.md#FR64`]
- Architecture: Referral inbox uses AdminLTE card split-panel, HTMX-loaded thread [Source: `_bmad-output/planning-artifacts/epics.md#Templates & Frontend`]
- Architecture: HTMX — no full-page JS framework; HTMX hx-get for partial updates [Source: `_bmad-output/project-context.md#Technology Stack`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

Story 4.3 implemented the unified referral inbox with sent/received thread list, HTMX thread panel, and unread indicators.

### Senior Developer Review

| # | Severity | Finding | Fix Applied |
|---|----------|---------|-------------|
| 1 | MEDIUM | No unauthenticated access test for inbox | Added `test_unauthenticated_redirected_to_login` |

**Verdict:** PASS — 7 tests (was 6), no functional bugs. Status: done.

### File List
