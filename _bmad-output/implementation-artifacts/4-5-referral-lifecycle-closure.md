# Story 4.5: Referral Lifecycle & Closure

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **clinician**,
I want to close a referral once the consultation is complete,
So that the thread is sealed with a permanent record and the CLOSED status is visible at a glance on all referral views.

## Acceptance Criteria

1. **Given** a referral is in `PENDING` or `REPLIED` status
   **When** the sending clinician clicks "Close Referral" and confirms
   **Then** both `ReferralSent.status` and `ReferralReceived.status` are set to `CLOSED`

2. **Given** a referral is `CLOSED`
   **When** it appears in the inbox thread list
   **Then** a CLOSED status badge is visible on the thread item
   **And** the reply input is hidden — no further messages can be added to the thread

3. **Given** a referral progresses through `PENDING → REPLIED → CLOSED`
   **When** each status transition occurs
   **Then** the status badge updates correctly on all referral list views (inbox and patient referrals tab)

4. **Given** an institution's subscription status is `GRACE`
   **When** a clinician attempts to reply or close an active referral thread via POST
   **Then** the action is permitted — active referrals are explicitly exempt from the read-only subscription restriction

## Tasks / Subtasks

- [ ] Task 1: Add `referral_close` view to `referral/views.py` (AC: #1, #4)
  - [ ] POST only, `@login_required`, `@ratelimit(rate='5/m')`
  - [ ] Only the SENDING clinician (`from_clinician`) or their institution ADMIN can close
  - [ ] Updates `ReferralSent.status = CLOSED` and `ReferralReceived.status = CLOSED` via bulk update
  - [ ] GRACE subscription exemption: the close action bypasses subscription read-only check
  - [ ] Returns HTMX-compatible re-render of thread panel
  - [ ] See exact view code in Dev Notes

- [ ] Task 2: Add `referral-close` URL to `referral/urls.py` (AC: #1)
  - [ ] `path('thread/<uuid:referral_uuid>/close/', views.referral_close, name='referral-close')`

- [ ] Task 3: Ensure `InstitutionContextMiddleware` exempts referral close/reply from GRACE read-only block (AC: #4)
  - [ ] In Story 1.3's `InstitutionContextMiddleware`, verify that POST requests to `/referral/thread/*/reply/` and `/referral/thread/*/close/` are exempt from the GRACE subscription read-only block
  - [ ] See exact middleware exemption pattern in Dev Notes

- [ ] Task 4: Write tests in `referral/tests/test_lifecycle.py` (AC: #1–#4)
  - [ ] See exact test code in Dev Notes

## Dev Notes

### Story 4.5 Position

Story 4.5 = **Step 10** (referral lifecycle closure):
```
    ├── Story 4.4: thread view + reply  ← done
    ├── Story 4.5: lifecycle + closure  ← THIS STORY
    └── Story 4.6: patient referrals tab
```

**FR Coverage:** FR64 (PENDING → REPLIED → CLOSED lifecycle), FR48 (GRACE exemption for active referrals).

---

### Task 1: `referral_close` View

Add to `referral/views.py`:

```python
@login_required(login_url="user-login")
@require_http_methods(["POST"])
@ratelimit(key='user_or_ip', rate='5/m')
@handle_view_errors(redirect_url='referral:referral-inbox', error_message='Failed to close referral.')
def referral_close(request, referral_uuid):
    """
    Close a referral thread (FR64).

    Sets CLOSED status on both ReferralSent and ReferralReceived via referral_uuid.
    Only the sending clinician can close (checked via from_institution match).
    GRACE subscription exemption: active referrals can be closed regardless of subscription status.

    Returns: re-rendered thread panel (HTMX) or redirect.
    """
    from referral.models import ReferralSent, ReferralReceived
    from ndas.custom_codes.choice import ReferralStatus

    # Find the ReferralSent record — only sender institution can close
    sent = ReferralSent.objects.filter(
        referral_uuid=referral_uuid,
        institution=request.institution,
    ).first()

    if not sent:
        from django.http import HttpResponse
        return HttpResponse(
            '<div class="alert alert-danger m-2">Only the sending institution can close a referral.</div>',
            status=403,
        )

    # Check permission: only from_clinician (or ADMIN of from_institution) can close
    user_type = getattr(request.user, 'user_type', None)
    from ndas.custom_codes.choice import UserType
    is_from_clinician = (sent.from_clinician == request.user)
    is_inst_admin = (user_type == UserType.ADMIN and request.user.institution == request.institution)

    if not is_from_clinician and not is_inst_admin:
        from django.http import HttpResponse
        return HttpResponse(
            '<div class="alert alert-danger m-2">Only the referring clinician or institution admin can close this referral.</div>',
            status=403,
        )

    # Reject if already closed
    if sent.status == ReferralStatus.CLOSED:
        from django.http import HttpResponse
        return HttpResponse(
            '<div class="alert alert-secondary m-2">This referral is already closed.</div>',
        )

    # ── Close both records atomically ─────────────────────────────────
    from django.db import transaction as db_transaction
    with db_transaction.atomic():
        # Update all records with this UUID (both institutions' copies)
        # INTENTIONAL cross-institution write — closure must be reflected on both sides
        ReferralSent.objects.filter(referral_uuid=referral_uuid).update(status=ReferralStatus.CLOSED)
        ReferralReceived.objects.filter(referral_uuid=referral_uuid).update(status=ReferralStatus.CLOSED)

    logger.info(
        "Clinician '%s' (inst: %s) closed referral %s",
        request.user.username, request.institution.name, referral_uuid,
    )

    # Return re-rendered thread panel (HTMX target: #thread-panel-container)
    # Need to reload the sent/received objects with updated status
    return referral_thread_panel(request, referral_uuid)
```

---

### Task 3: `InstitutionContextMiddleware` GRACE Exemption

In the `InstitutionContextMiddleware` (Story 1.3's `institution/middleware.py`), the GRACE logic
blocks all POST requests. Active referral actions must be exempted.

Find the GRACE check in the middleware and add an exemption list:

```python
# In InstitutionContextMiddleware.process_request() or __call__():

REFERRAL_EXEMPT_PATHS = [
    '/referral/thread/',  # reply and close endpoints
]

def is_referral_exempt(path):
    """Return True if this path is an active referral action (GRACE-exempt)."""
    return any(path.startswith(prefix) for prefix in REFERRAL_EXEMPT_PATHS)

# In the GRACE subscription check:
if institution.subscription_status == SubscriptionStatus.GRACE:
    if request.method == 'POST':
        if not is_referral_exempt(request.path):
            # Block non-referral POSTs
            return HttpResponseForbidden("Read-only access: subscription in grace period.")
        # Referral actions are allowed even in GRACE — fall through
```

**Location:** This change is in `institution/middleware.py` (created in Story 1.3).
The exact pattern depends on Story 1.3's implementation. The key is to check
`request.path.startswith('/referral/thread/')` before blocking GRACE POST requests.

---

### Task 4: `referral/tests/test_lifecycle.py`

```python
"""
referral/tests/test_lifecycle.py
Tests for Referral Lifecycle & Closure (Story 4.5 — FR64, FR48).
"""
import uuid
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, ReferralStatus
from referral.models import ReferralSent, ReferralReceived, ReferralMessage

User = get_user_model()


class LifecycleTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_lc', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771000001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='LC Alpha', slug='lc-alpha',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='LC Beta', slug='lc-beta',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.clin_a = User.objects.create_user(
            username='clin_a_lc', password='Testpass1!',
            first_name='LC', last_name='Alpha',
            position='Medical Officer', mobile_primary='0771000002',
            user_type=UserType.USER, institution=self.inst_a,
        )
        self.clin_b = User.objects.create_user(
            username='clin_b_lc', password='Testpass1!',
            first_name='LC', last_name='Beta',
            position='Consultant', mobile_primary='0771000003',
            user_type=UserType.USER, institution=self.inst_b,
        )
        from patients.models import Patient
        self.patient = Patient.objects.create(
            institution=self.inst_a, baby_name='LC Patient',
            mother_name='Test Mother', added_by=self.clin_a, last_edit_by=self.clin_a,
        )
        self.shared_uuid = uuid.uuid4()
        self.sent = ReferralSent.objects.create(
            from_institution=self.inst_a, to_institution=self.inst_b,
            institution=self.inst_a, patient=self.patient,
            from_clinician=self.clin_a, to_clinician=self.clin_b,
            referral_uuid=self.shared_uuid, initial_message='Test.',
            snapshot_data={'schema_version': 1}, added_by=self.clin_a, last_edit_by=self.clin_a,
        )
        self.received = ReferralReceived.objects.create(
            to_institution=self.inst_b, from_institution=self.inst_a,
            institution=self.inst_b, patient_name='LC Patient',
            from_clinician_name='LC Alpha', to_clinician=self.clin_b,
            referral_uuid=self.shared_uuid, initial_message='Test.',
            snapshot_data={'schema_version': 1}, added_by=self.clin_a, last_edit_by=self.clin_a,
        )


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class ClosureTest(LifecycleTestBase):
    def test_close_referral_sets_closed_on_both_records(self):
        """AC #1: Closing sets CLOSED status on both ReferralSent and ReferralReceived."""
        client = Client()
        client.force_login(self.clin_a)
        url = reverse('referral:referral-close', args=[self.shared_uuid])
        response = client.post(url)
        self.assertEqual(response.status_code, 200)
        self.sent.refresh_from_db()
        self.received.refresh_from_db()
        self.assertEqual(self.sent.status, ReferralStatus.CLOSED, "AC #1: ReferralSent must be CLOSED")
        self.assertEqual(self.received.status, ReferralStatus.CLOSED, "AC #1: ReferralReceived must be CLOSED")

    def test_non_sender_cannot_close(self):
        """AC #1: Receiving clinician cannot close the referral."""
        client = Client()
        client.force_login(self.clin_b)  # Receiver, not sender
        url = reverse('referral:referral-close', args=[self.shared_uuid])
        response = client.post(url)
        self.assertEqual(response.status_code, 403, "Receiving clinician must not be able to close")
        self.sent.refresh_from_db()
        self.assertNotEqual(self.sent.status, ReferralStatus.CLOSED)

    def test_reply_blocked_after_closure(self):
        """AC #2: No replies can be added after closure."""
        self.sent.status = ReferralStatus.CLOSED
        self.sent.save()
        self.received.status = ReferralStatus.CLOSED
        self.received.save()

        client = Client()
        client.force_login(self.clin_b)
        reply_url = reverse('referral:referral-reply', args=[self.shared_uuid])
        response = client.post(reply_url, {'body': 'Post-closure reply attempt.'})
        self.assertEqual(response.status_code, 403, "AC #2: Reply to CLOSED thread must return 403")
        self.assertEqual(ReferralMessage.objects.count(), 0)


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class GraceSubscriptionExemptionTest(LifecycleTestBase):
    def test_grace_institution_can_close_active_referral(self):
        """AC #4: GRACE subscription does not block referral closure."""
        # Set inst_a to GRACE
        self.inst_a.subscription_status = SubscriptionStatus.GRACE
        self.inst_a.save()

        client = Client()
        client.force_login(self.clin_a)
        url = reverse('referral:referral-close', args=[self.shared_uuid])
        response = client.post(url)

        # Should succeed (not 403 subscription block)
        self.assertNotEqual(response.status_code, 403,
            "AC #4: GRACE subscription must not block active referral closure")
```

---

### Project Structure Notes

**Files MODIFIED in this story:**
- `referral/views.py` — add `referral_close` view
- `referral/urls.py` — add `referral-close` path
- `institution/middleware.py` (Story 1.3) — add GRACE exemption for referral paths

**Files CREATED in this story:**
- `referral/tests/test_lifecycle.py` — 5+ tests

---

### References

- FR64: Lifecycle PENDING → REPLIED → CLOSED [Source: `_bmad-output/planning-artifacts/epics.md#Story 4.5`]
- FR48: GRACE subscription exemption — active referrals continue to completion [Source: `_bmad-output/planning-artifacts/epics.md#FR48`]
- Architecture: InstitutionContextMiddleware enforces subscription — grace=read-only, active referrals exempt [Source: `_bmad-output/planning-artifacts/epics.md#Middleware`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
