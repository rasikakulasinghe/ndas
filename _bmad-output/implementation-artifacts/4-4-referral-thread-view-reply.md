# Story 4.4: Referral Thread View & Reply

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **clinician**,
I want to view a full referral thread with the frozen patient snapshot and all consultation messages, and reply with my clinical opinion,
So that the consultation is fully documented with clinician identity, institution badge, and timestamp on every entry.

## Acceptance Criteria

1. **Given** a clinician opens a referral thread
   **When** the thread panel loads
   **Then** a fixed patient header card is displayed at the top with the patient's name and key identifiers (BHT, NNC)

2. **Given** the thread panel renders the frozen snapshot section
   **When** it is displayed
   **Then** it appears as a collapsible `<details>` panel — collapsed by default, expandable on click — showing the full patient data captured at referral time

3. **Given** the thread has existing messages
   **When** they are rendered
   **Then** each entry alternates visually and shows: clinician name, institution badge, timestamp, and message body

4. **Given** a clinician writes a reply and submits the reply form
   **When** the submission is processed
   **Then** a `ReferralMessage` record is created with `message_type=OPINION` linked to the referral via UUID
   **And** the `ReferralSent` status updates to `REPLIED`
   **And** the new message entry appears in the thread immediately

5. **Given** a clinician attempts to reply to a `CLOSED` referral
   **When** the reply form is submitted
   **Then** the system rejects the reply — no messages can be added to a closed referral thread

## Tasks / Subtasks

- [ ] Task 1: Extend `referral_thread_panel` view in `referral/views.py` (AC: #1, #2, #3)
  - [ ] Patient header: extract from `snapshot_data['demographics']` (BHT, NNC, baby_name)
  - [ ] Full message list: `ReferralMessage.objects.filter(referral_uuid=referral_uuid).order_by('created_at')`
  - [ ] Reply form: include `ReferralReplyForm` in context if thread is not CLOSED
  - [ ] See exact view extension in Dev Notes

- [ ] Task 2: Add `referral_reply` view to `referral/views.py` (AC: #4, #5)
  - [ ] POST only, `@login_required`, `@ratelimit(rate='10/m')`
  - [ ] Creates `ReferralMessage` with `message_type=OPINION`
  - [ ] Updates `ReferralSent.status` to `REPLIED` if sender is current user's institution
  - [ ] Updates `ReferralReceived.status` to `REPLIED` at both institutions
  - [ ] Rejects POST if status is CLOSED (AC #5)
  - [ ] Returns HTMX-compatible response (re-render thread panel or redirect)
  - [ ] See exact view code in Dev Notes

- [ ] Task 3: Create `ReferralReplyForm` in `referral/forms.py` (AC: #4)
  - [ ] Single field: `body` (Textarea, required)
  - [ ] Validated with `sanitize_text_input()` to prevent XSS
  - [ ] See exact form code in Dev Notes

- [ ] Task 4: Add `referral-reply` URL to `referral/urls.py` (AC: #4)
  - [ ] `path('thread/<uuid:referral_uuid>/reply/', views.referral_reply, name='referral-reply')`

- [ ] Task 5: Update `templates/referral/thread_panel.html` with full thread content (AC: #1, #2, #3, #4, #5)
  - [ ] Patient header card (compact summary)
  - [ ] Frozen snapshot as `<details>` collapsible panel
  - [ ] Message list with alternating visual styling, institution badge, clinician name, timestamp
  - [ ] Reply form (hidden when CLOSED)
  - [ ] See exact template in Dev Notes

- [ ] Task 6: Write tests in `referral/tests/test_thread.py` (AC: #1–#5)
  - [ ] See exact test code in Dev Notes

## Dev Notes

### Story 4.4 Position

Story 4.4 = **Step 10** (thread detail + reply):
```
    ├── Story 4.3: inbox            ← done
    ├── Story 4.4: thread/reply     ← THIS STORY
    ├── Story 4.5: lifecycle/closure
    └── Story 4.6: patient referrals tab
```

**FR Coverage:** FR62 (thread view + frozen snapshot), FR64 (status update to REPLIED).

---

### Task 1: Extend `referral_thread_panel` View

The view from Story 4.3 is extended here with full content. Replace the stub return with:

```python
@login_required(login_url="user-login")
@require_GET
@handle_view_errors(redirect_url='referral:referral-inbox', error_message='Failed to load thread.')
def referral_thread_panel(request, referral_uuid):
    """
    HTMX partial: full referral thread with frozen snapshot + reply form (FR62).
    Extended from Story 4.3 stub.
    """
    from referral.models import ReferralSent, ReferralReceived, ReferralMessage
    from referral.forms import ReferralReplyForm

    sent     = ReferralSent.objects.filter(referral_uuid=referral_uuid, institution=request.institution).first()
    received = ReferralReceived.objects.filter(referral_uuid=referral_uuid, institution=request.institution).first()

    if not sent and not received:
        from django.http import HttpResponse
        return HttpResponse('<p class="text-center text-danger p-3">Thread not found.</p>', status=404)

    # Mark received as read on open
    if received and not received.is_read and received.to_clinician == request.user:
        received.is_read = True
        received.save(update_fields=['is_read', 'updated_at'])

    messages_qs = ReferralMessage.objects.filter(
        referral_uuid=referral_uuid
    ).select_related('sender', 'sender_institution').order_by('created_at')

    current_record = sent or received
    status = current_record.status
    snapshot_data = current_record.snapshot_data
    is_closed = status == 'CLOSED'
    is_sender = sent is not None

    # Patient header from snapshot (AC #1)
    demographics = snapshot_data.get('demographics', {})
    patient_header = {
        'baby_name': demographics.get('baby_name', 'Unknown'),
        'bht':       demographics.get('bht', '—'),
        'nnc_no':    demographics.get('nnc_no', '—'),
    }

    reply_form = None if is_closed else ReferralReplyForm()

    return render(request, 'referral/thread_panel.html', {
        'referral_uuid':  referral_uuid,
        'sent':           sent,
        'received':       received,
        'messages':       messages_qs,
        'status':         status,
        'snapshot_data':  snapshot_data,
        'patient_header': patient_header,
        'is_sender':      is_sender,
        'is_closed':      is_closed,
        'reply_form':     reply_form,
    })
```

---

### Task 2: `referral_reply` View

```python
@login_required(login_url="user-login")
@require_http_methods(["POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='referral:referral-inbox', error_message='Failed to submit reply.')
def referral_reply(request, referral_uuid):
    """
    Submit a clinical opinion reply to a referral thread (FR62, FR64).

    Creates ReferralMessage, updates status to REPLIED on both ReferralSent + ReferralReceived.
    Rejects if thread is CLOSED (AC #5).
    """
    from referral.models import ReferralSent, ReferralReceived, ReferralMessage
    from referral.forms import ReferralReplyForm
    from ndas.custom_codes.choice import ReferralStatus

    # Find the referral records visible to this institution
    sent     = ReferralSent.objects.filter(referral_uuid=referral_uuid, institution=request.institution).first()
    received = ReferralReceived.objects.filter(referral_uuid=referral_uuid, institution=request.institution).first()

    if not sent and not received:
        from django.http import HttpResponse
        return HttpResponse('<p class="text-danger p-3">Referral not found.</p>', status=404)

    current_record = sent or received

    # AC #5: Reject reply to CLOSED thread
    if current_record.status == ReferralStatus.CLOSED:
        from django.http import HttpResponse
        return HttpResponse(
            '<div class="alert alert-danger m-2">This referral is closed. No further replies are permitted.</div>',
            status=403,
        )

    form = ReferralReplyForm(request.POST)
    if form.is_valid():
        body = form.cleaned_data['body']

        # Create the message
        msg = ReferralMessage.objects.create(
            referral_uuid=referral_uuid,
            sender=request.user,
            sender_institution=request.institution,
            body=body,
            message_type=ReferralMessage.OPINION,
            added_by=request.user,
            last_edit_by=request.user,
        )

        # Update status to REPLIED on own record
        if sent:
            sent.status = ReferralStatus.REPLIED
            sent.save(update_fields=['status', 'updated_at'])
        if received:
            received.status = ReferralStatus.REPLIED
            received.save(update_fields=['status', 'updated_at'])

        # Also update the counterpart's status if we can find it
        # (The counterpart record is at the other institution — use uuid to find it)
        ReferralSent.objects.filter(referral_uuid=referral_uuid).update(status=ReferralStatus.REPLIED)
        ReferralReceived.objects.filter(referral_uuid=referral_uuid).update(status=ReferralStatus.REPLIED)

        logger.info(
            "Clinician '%s' replied to referral %s",
            request.user.username, referral_uuid,
        )

        # Return the updated thread panel as HTMX response
        return referral_thread_panel(request, referral_uuid)

    # Form invalid — re-render with errors
    return referral_thread_panel(request, referral_uuid)
```

**Note:** `ReferralSent.objects.filter(referral_uuid=referral_uuid).update(...)` without
institution scoping is intentional here — we want to update status at BOTH institutions.
This is an INTENTIONAL cross-institution write (not a data leak). Document this in code comments.

---

### Task 3: `ReferralReplyForm`

Add to `referral/forms.py`:

```python
from ndas.custom_codes.validators import sanitize_text_input


class ReferralReplyForm(forms.Form):
    body = forms.CharField(
        label='Clinical Opinion',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter your clinical opinion...',
        }),
        min_length=10,
    )

    def clean_body(self):
        body = self.cleaned_data.get('body', '')
        return sanitize_text_input(body)
```

---

### Task 5: `templates/referral/thread_panel.html` — Full Template

```django
{# referral/thread_panel.html — Full thread view (Story 4.4) #}
<div class="card card-outline">

  {# ── Patient Header (AC #1) ──────────────────────────────────────── #}
  <div class="card-header bg-light">
    <h3 class="card-title">
      <i class="fas fa-user-injured mr-2"></i>
      {{ patient_header.baby_name }}
      <small class="text-muted ml-2">BHT: {{ patient_header.bht }} | NNC: {{ patient_header.nnc_no }}</small>
    </h3>
    <div class="card-tools">
      {% if status == 'PENDING' %}
        <span class="badge badge-warning">Pending</span>
      {% elif status == 'REPLIED' %}
        <span class="badge badge-primary">Replied</span>
      {% elif status == 'CLOSED' %}
        <span class="badge badge-secondary">Closed</span>
      {% endif %}
      {% if is_sender and not is_closed %}
        <a href="{% url 'referral:referral-close' referral_uuid %}"
           class="btn btn-xs btn-danger ml-2"
           hx-post="{% url 'referral:referral-close' referral_uuid %}"
           hx-target="#thread-panel-container"
           hx-swap="innerHTML"
           hx-confirm="Close this referral? This cannot be undone.">
          Close Referral
        </a>
      {% endif %}
    </div>
  </div>

  <div class="card-body">

    {# ── Frozen Snapshot (AC #2) — collapsible <details> ───────────── #}
    <details class="mb-3">
      <summary class="font-weight-bold text-info" style="cursor:pointer;">
        <i class="fas fa-history mr-1"></i>
        Patient Snapshot at Referral Time
        <small class="text-muted font-weight-normal">({{ snapshot_data.captured_at|default:"unknown" }})</small>
      </summary>
      <div class="card card-secondary card-outline mt-2">
        <div class="card-body p-2">
          {% with demo=snapshot_data.demographics peri=snapshot_data.perinatal %}
          {% if demo %}
          <div class="row">
            <div class="col-sm-6">
              <table class="table table-sm table-borderless mb-0">
                <tr><th class="text-muted" style="width:40%">Name</th><td>{{ demo.baby_name }}</td></tr>
                <tr><th class="text-muted">BHT</th><td>{{ demo.bht|default:"—" }}</td></tr>
                <tr><th class="text-muted">NNC No.</th><td>{{ demo.nnc_no|default:"—" }}</td></tr>
                <tr><th class="text-muted">DOB</th><td>{{ demo.dob_tob|default:"—" }}</td></tr>
                <tr><th class="text-muted">Gender</th><td>{{ demo.gender|default:"—" }}</td></tr>
              </table>
            </div>
            <div class="col-sm-6">
              <table class="table table-sm table-borderless mb-0">
                <tr><th class="text-muted" style="width:50%">Birth Weight</th><td>{{ peri.birth_weight|default:"—" }}g</td></tr>
                <tr><th class="text-muted">POG</th><td>{{ peri.pog_wks|default:"—" }}w {{ peri.pog_days|default:0 }}d</td></tr>
                <tr><th class="text-muted">APGAR 1/5</th><td>{{ peri.apgar_1|default:"—" }} / {{ peri.apgar_5|default:"—" }}</td></tr>
              </table>
            </div>
          </div>
          {% endif %}
          {% with assessments=snapshot_data.assessments %}
          {% if assessments %}
          <hr class="mt-1 mb-1">
          <small class="text-muted">
            Assessments: GMA: {{ assessments.gma|length }},
            HINE: {{ assessments.hine|length }},
            DA: {{ assessments.da|length }},
            CDIC: {{ assessments.cdic|length }},
            GPA: {{ assessments.gpa|length }}
          </small>
          {% endif %}
          {% endwith %}
          {% endwith %}
        </div>
      </div>
    </details>

    {# ── Message Thread (AC #3) ───────────────────────────────────── #}
    <div class="direct-chat-messages" style="height:auto; max-height:400px; overflow-y:auto;" id="message-thread">
      {% if messages %}
      {% for msg in messages %}
      <div class="direct-chat-msg {% if msg.sender == request.user %}right{% endif %} mb-3">
        <div class="direct-chat-infos clearfix">
          <span class="direct-chat-name {% if msg.sender == request.user %}float-right{% endif %}">
            {{ msg.sender.get_full_name|default:msg.sender.username }}
          </span>
          <span class="badge badge-light border {% if msg.sender == request.user %}float-right mr-2{% endif %}">
            {{ msg.sender_institution.name|default:"Unknown" }}
          </span>
          <span class="direct-chat-timestamp {% if msg.sender == request.user %}float-left{% else %}float-right{% endif %}">
            {{ msg.created_at|date:"d M Y, H:i" }}
          </span>
        </div>
        <div class="direct-chat-text {% if msg.sender == request.user %}bg-primary text-white{% else %}bg-light{% endif %}">
          {{ msg.body }}
        </div>
      </div>
      {% endfor %}
      {% else %}
      <p class="text-muted text-center">No messages yet.</p>
      {% endif %}
    </div>

    {# ── Reply Form (AC #4, #5) ───────────────────────────────────── #}
    {% if not is_closed and reply_form %}
    <div class="mt-3" id="reply-form-section">
      <form hx-post="{% url 'referral:referral-reply' referral_uuid %}"
            hx-target="#thread-panel-container"
            hx-swap="innerHTML">
        {% csrf_token %}
        <div class="form-group">
          <label class="font-weight-bold">Your Reply</label>
          {{ reply_form.body }}
          {% if reply_form.body.errors %}
          <div class="text-danger small">{{ reply_form.body.errors }}</div>
          {% endif %}
        </div>
        <div class="d-flex justify-content-end">
          <button type="submit" class="btn btn-primary btn-sm">
            <i class="fas fa-reply mr-1"></i>Send Reply
          </button>
        </div>
      </form>
    </div>
    {% elif is_closed %}
    <div class="alert alert-secondary mt-3 mb-0">
      <i class="fas fa-lock mr-1"></i>This referral is closed. No further replies can be added.
    </div>
    {% endif %}

  </div>
</div>
```

---

### Task 6: `referral/tests/test_thread.py`

```python
"""
referral/tests/test_thread.py
Tests for Referral Thread View & Reply (Story 4.4 — FR62, FR64).
"""
import uuid
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, ReferralStatus
from referral.models import ReferralSent, ReferralReceived, ReferralMessage

User = get_user_model()


class ThreadTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_thread', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771111001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='Thread Alpha', slug='thread-alpha',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Thread Beta', slug='thread-beta',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.clin_a = User.objects.create_user(
            username='clin_a_thread', password='Testpass1!',
            first_name='Thread', last_name='Alpha',
            position='Medical Officer', mobile_primary='0771111002',
            user_type=UserType.USER, institution=self.inst_a,
        )
        self.clin_b = User.objects.create_user(
            username='clin_b_thread', password='Testpass1!',
            first_name='Thread', last_name='Beta',
            position='Consultant', mobile_primary='0771111003',
            user_type=UserType.USER, institution=self.inst_b,
        )
        from patients.models import Patient
        self.patient = Patient.objects.create(
            institution=self.inst_a, baby_name='Thread Patient',
            mother_name='Test Mother', added_by=self.clin_a, last_edit_by=self.clin_a,
        )
        self.shared_uuid = uuid.uuid4()
        self.snapshot = {
            'schema_version': 1,
            'captured_at': '2026-02-24T10:00:00',
            'demographics': {'baby_name': 'Thread Patient', 'bht': 'BHT001', 'nnc_no': 'NNC001'},
        }
        self.sent = ReferralSent.objects.create(
            from_institution=self.inst_a, to_institution=self.inst_b,
            institution=self.inst_a, patient=self.patient,
            from_clinician=self.clin_a, to_clinician=self.clin_b,
            referral_uuid=self.shared_uuid, initial_message='Test referral.',
            snapshot_data=self.snapshot, added_by=self.clin_a, last_edit_by=self.clin_a,
        )
        self.received = ReferralReceived.objects.create(
            to_institution=self.inst_b, from_institution=self.inst_a,
            institution=self.inst_b, patient_name='Thread Patient',
            from_clinician_name='Thread Alpha', to_clinician=self.clin_b,
            referral_uuid=self.shared_uuid, initial_message='Test referral.',
            snapshot_data=self.snapshot, added_by=self.clin_a, last_edit_by=self.clin_a,
        )


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class ThreadViewTest(ThreadTestBase):
    def test_thread_panel_shows_patient_header(self):
        """AC #1: Patient name and BHT must appear in thread panel."""
        client = Client()
        client.force_login(self.clin_a)
        url = reverse('referral:referral-thread-panel', args=[self.shared_uuid])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['patient_header']['baby_name'], 'Thread Patient')
        self.assertEqual(response.context['patient_header']['bht'], 'BHT001')

    def test_thread_panel_has_snapshot_data(self):
        """AC #2: Snapshot data available in context for <details> panel."""
        client = Client()
        client.force_login(self.clin_a)
        url = reverse('referral:referral-thread-panel', args=[self.shared_uuid])
        response = client.get(url)
        self.assertIn('snapshot_data', response.context)
        self.assertEqual(response.context['snapshot_data']['schema_version'], 1)


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class ReferralReplyTest(ThreadTestBase):
    def test_reply_creates_message(self):
        """AC #4: Reply creates a ReferralMessage with OPINION type."""
        client = Client()
        client.force_login(self.clin_b)
        url = reverse('referral:referral-reply', args=[self.shared_uuid])
        response = client.post(url, {'body': 'My clinical opinion on this patient.'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ReferralMessage.objects.filter(referral_uuid=self.shared_uuid).count(), 1)
        msg = ReferralMessage.objects.first()
        self.assertEqual(msg.message_type, ReferralMessage.OPINION)

    def test_reply_updates_status_to_replied(self):
        """AC #4: Replying updates status to REPLIED."""
        client = Client()
        client.force_login(self.clin_b)
        url = reverse('referral:referral-reply', args=[self.shared_uuid])
        client.post(url, {'body': 'Clinical opinion — patient is improving.'})
        self.sent.refresh_from_db()
        self.received.refresh_from_db()
        self.assertEqual(self.sent.status, ReferralStatus.REPLIED)
        self.assertEqual(self.received.status, ReferralStatus.REPLIED)

    def test_reply_to_closed_thread_rejected(self):
        """AC #5: Reply to CLOSED referral must be rejected (403)."""
        self.sent.status = ReferralStatus.CLOSED
        self.sent.save()
        self.received.status = ReferralStatus.CLOSED
        self.received.save()

        client = Client()
        client.force_login(self.clin_b)
        url = reverse('referral:referral-reply', args=[self.shared_uuid])
        response = client.post(url, {'body': 'Attempt to reply after close.'})
        self.assertEqual(response.status_code, 403, "AC #5: Reply to CLOSED thread must return 403")
        self.assertEqual(ReferralMessage.objects.count(), 0, "AC #5: No message must be created for closed thread reply")
```

---

### Project Structure Notes

**Files MODIFIED in this story:**
- `referral/views.py` — extend `referral_thread_panel` + add `referral_reply`
- `referral/forms.py` — add `ReferralReplyForm`
- `referral/urls.py` — add `referral-reply` path
- `templates/referral/thread_panel.html` — replace stub with full content

**Files CREATED in this story:**
- `referral/tests/test_thread.py` — 6+ tests

---

### References

- FR62: Thread view — fixed header, frozen snapshot, alternating messages with clinician/institution/timestamp [Source: `_bmad-output/planning-artifacts/epics.md#Story 4.4`]
- FR64: Referral status transitions: PENDING → REPLIED → CLOSED [Source: `_bmad-output/planning-artifacts/epics.md#FR64`]
- Architecture: Frozen snapshot as collapsible `<details>` panel [Source: `_bmad-output/planning-artifacts/epics.md#Templates & Frontend`]
- Project context: `sanitize_text_input()` for free-text field validation [Source: `_bmad-output/project-context.md#Input Sanitization`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
