# Story 4.1: Referral App & Data Models

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **clinician**,
I want the system to have the data structures needed to record cross-institution referrals independently at both institutions,
So that each institution's consultation record is self-contained and survives the other institution being suspended or deleted.

## Acceptance Criteria

1. **Given** the `referral/` Django app is created and registered in `INSTALLED_APPS`
   **When** the initial migration runs
   **Then** `ReferralSent`, `ReferralReceived`, and `ReferralMessage` tables are created with all specified fields
   **And** `ReferralStatus` choices (PENDING/REPLIED/CLOSED) exist in `ndas/custom_codes/choice.py`

2. **Given** a `ReferralSent` record is created with a new `referral_uuid` (UUID4)
   **When** `ReferralReceived` is created for the same referral
   **Then** `ReferralReceived` copies the same `referral_uuid` — no new UUID is generated
   **And** both records default to `status=PENDING`

3. **Given** `ReferralSent` is deleted or Institution A is suspended
   **When** Institution B queries `ReferralReceived` by `referral_uuid`
   **Then** the `ReferralReceived` record remains intact and fully accessible — the two records are independently self-contained

4. **Given** all new referral models are inspected
   **When** their base classes are checked
   **Then** all inherit `TimeStampedModel` and `UserTrackingMixin`, and all institution-FK models use `InstitutionScopedManager`

## Tasks / Subtasks

- [ ] Task 1: Add `ReferralStatus` choices to `ndas/custom_codes/choice.py` (AC: #1)
  - [ ] `class ReferralStatus(models.TextChoices): PENDING = 'PENDING', REPLIED = 'REPLIED', CLOSED = 'CLOSED'`
  - [ ] See exact code in Dev Notes

- [ ] Task 2: Create the `referral/` Django app (AC: #1)
  - [ ] Run `python manage.py startapp referral` from project root
  - [ ] Create `referral/models.py`, `referral/views.py`, `referral/urls.py`, `referral/apps.py`, `referral/forms.py`, `referral/signals.py`, `referral/utils.py`
  - [ ] Create `referral/migrations/__init__.py` (migrations directory)
  - [ ] Create `referral/tests/__init__.py` (tests directory)
  - [ ] See full directory structure in Dev Notes

- [ ] Task 3: Add `ReferralConfig` to `referral/apps.py` (AC: #1, #4)
  - [ ] `name = 'referral'`, `verbose_name = 'Referral System'`
  - [ ] `ready()` method stub: `# Signals registered in Story 5.1: import referral.signals`
  - [ ] See exact code in Dev Notes

- [ ] Task 4: Define `ReferralSent`, `ReferralReceived`, `ReferralMessage` models in `referral/models.py` (AC: #1, #2, #3, #4)
  - [ ] All three inherit `TimeStampedModel, UserTrackingMixin`
  - [ ] `ReferralSent` + `ReferralReceived` use `InstitutionScopedManager` as `objects`
  - [ ] `referral_uuid = models.UUIDField(default=uuid.uuid4, db_index=True)` on `ReferralSent`; copied (not regenerated) on `ReferralReceived`
  - [ ] `snapshot_data = models.JSONField(default=dict)` on both `ReferralSent` and `ReferralReceived`
  - [ ] See exact model code in Dev Notes

- [ ] Task 5: Register `referral.apps.ReferralConfig` in `ndas/settings.py` `INSTALLED_APPS` (AC: #1)
  - [ ] Add `'referral.apps.ReferralConfig',` after `'institution.apps.InstitutionConfig'`
  - [ ] See exact settings change in Dev Notes

- [ ] Task 6: Create `referral/urls.py` with stub URL patterns (AC: #1)
  - [ ] Empty urlpatterns list with `app_name = 'referral'`
  - [ ] Include in `ndas/urls.py` with prefix `referral/`
  - [ ] See exact URL config in Dev Notes

- [ ] Task 7: Run initial migration (AC: #1)
  - [ ] `python manage.py makemigrations referral`
  - [ ] `python manage.py migrate`

- [ ] Task 8: Write tests in `referral/tests/test_models.py` (AC: #1–#4)
  - [ ] See exact test code in Dev Notes

## Dev Notes

### Story 4.1 Position in the 13-Step Sequence

Story 4.1 = **Step 7** (referral app — data models foundation):

```
7.  referral app — Referral + Notification models:
    ├── Story 4.1: ReferralSent, ReferralReceived, ReferralMessage  ← THIS STORY
    ├── Story 4.2–4.6: referral views and inbox
    └── Story 5.1: Notification model (added to referral/models.py)
```

**Prerequisites:**
- Story 1.1 done (`institution/` app, `Institution` model)
- Story 1.2 done (`CustomUser.institution` FK + `user_type` field)
- Story 1.4 done (`InstitutionScopedManager` in `institution/managers.py`)

**FR Coverage:** FR66 — Dual institution referral records via UUID (self-contained, independent records).

---

### Task 1: `ReferralStatus` in `ndas/custom_codes/choice.py`

Add after `SubscriptionStatus`:

```python
class ReferralStatus(models.TextChoices):
    """
    Referral lifecycle status — FR64.
    PENDING → REPLIED → CLOSED (one-way progression).
    """
    PENDING = 'PENDING', 'Pending'
    REPLIED = 'REPLIED', 'Replied'
    CLOSED  = 'CLOSED',  'Closed'
```

**Import:** `from django.db import models` is already present at the top of `choice.py`.

---

### Task 2: `referral/` App Directory Structure

```
referral/
├── __init__.py
├── apps.py
├── models.py
├── views.py            (empty initially; views added in Stories 4.2–4.6)
├── urls.py             (stub with empty urlpatterns; Story 4.3 adds inbox URL)
├── forms.py            (empty initially; forms added in Stories 4.2–4.3)
├── signals.py          (empty initially; Story 5.1 adds signal handlers)
├── utils.py            (empty initially; Story 4.2 adds build_patient_snapshot)
├── admin.py            (register models for Django admin)
├── migrations/
│   ├── __init__.py
│   └── (generated by makemigrations)
└── tests/
    ├── __init__.py
    └── test_models.py  (Story 4.1 tests)
```

**Create each file as listed.** `views.py`, `forms.py`, `signals.py`, `utils.py` can be empty
(just docstring headers) at this stage.

---

### Task 3: `referral/apps.py` — Full Code

```python
from django.apps import AppConfig


class ReferralConfig(AppConfig):
    name = 'referral'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'Referral System'

    def ready(self):
        # Story 5.1: Signal registration
        # import referral.signals  # Uncomment when Story 5.1 is implemented
        pass
```

---

### Task 4: `referral/models.py` — Full Model Code

```python
"""
referral/models.py

Cross-institution referral data models.

Key architecture decisions:
- ReferralSent and ReferralReceived are INDEPENDENT records linked by referral_uuid.
- Neither record has a FK to the other — this ensures both survive if the other's
  institution is suspended or deleted (FR66 + NFR22).
- snapshot_data is captured once at referral submission and is IMMUTABLE thereafter (FR61).
- Notification model added in Story 5.1.
"""
import uuid
import logging

from django.db import models

from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.choice import ReferralStatus

logger = logging.getLogger(__name__)


class ReferralSent(TimeStampedModel, UserTrackingMixin):
    """
    Referral record owned by the SENDING institution.

    Created atomically with ReferralReceived (transaction.atomic in Story 4.2 view).
    FR60, FR61, FR66.
    """
    from institution.managers import InstitutionScopedManager  # Story 1.4

    # The institution that SENT this referral
    from_institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_sent',
        db_index=True,
    )
    # The institution receiving this referral
    to_institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_received_at',
        db_index=True,
    )
    # The patient being referred (scoped to from_institution)
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_sent',
        db_index=True,
    )
    # The clinician who sent the referral
    from_clinician = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_sent_by',
        db_index=True,
    )
    # The clinician at the receiving institution who is the referral target
    to_clinician = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_received_by',
        db_index=True,
    )

    # UUID shared with ReferralReceived — links the two records without a direct FK
    referral_uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Shared with ReferralReceived. Generated once at creation; never regenerated."
    )

    status = models.CharField(
        max_length=20,
        choices=ReferralStatus.choices,
        default=ReferralStatus.PENDING,
        db_index=True,
    )
    initial_message = models.TextField(
        help_text="The referral message from the sending clinician."
    )
    # Frozen snapshot of patient record at referral time — immutable after creation (FR61)
    snapshot_data = models.JSONField(
        default=dict,
        help_text="Frozen patient record snapshot at referral submission time. Do not modify after creation."
    )
    outcome = models.TextField(
        blank=True,
        help_text="Clinical outcome note, added at closure."
    )

    # institution FK for InstitutionScopedManager scoping
    institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_owned_sent',
        db_index=True,
        help_text="Owning institution for scoping. Same as from_institution."
    )

    objects = InstitutionScopedManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['referral_uuid']),
            models.Index(fields=['from_institution', 'status']),
            models.Index(fields=['to_institution', 'status']),
        ]

    def __str__(self):
        return f"ReferralSent[{self.referral_uuid}] {self.status}"


class ReferralReceived(TimeStampedModel, UserTrackingMixin):
    """
    Referral record owned by the RECEIVING institution.

    Created atomically with ReferralSent (transaction.atomic in Story 4.2 view).
    Has NO FK to ReferralSent — fully self-contained (FR66).
    Links to ReferralSent only via referral_uuid for cross-institution lookup.
    FR41, FR62, FR63, FR66.
    """
    from institution.managers import InstitutionScopedManager  # Story 1.4

    # The institution that RECEIVED this referral
    to_institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_received',
        db_index=True,
    )
    from_institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_sent_from',
        db_index=True,
    )
    patient_name = models.CharField(
        max_length=200,
        help_text="Denormalized patient name from snapshot, for display without patient FK lookup."
    )
    from_clinician_name = models.CharField(
        max_length=200,
        help_text="Denormalized sending clinician name."
    )
    to_clinician = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_received_as_clinician',
        db_index=True,
    )

    # COPIED from ReferralSent.referral_uuid — same UUID, never regenerated (AC #2)
    referral_uuid = models.UUIDField(
        db_index=True,
        editable=False,
        help_text="Copied from ReferralSent.referral_uuid. Never regenerated."
    )

    status = models.CharField(
        max_length=20,
        choices=ReferralStatus.choices,
        default=ReferralStatus.PENDING,
        db_index=True,
    )
    initial_message = models.TextField(
        help_text="Copy of the referral message from the sending clinician."
    )
    # Own copy of snapshot — self-contained even if ReferralSent is deleted (FR66)
    snapshot_data = models.JSONField(
        default=dict,
        help_text="Own copy of patient snapshot. Self-contained regardless of ReferralSent state."
    )
    outcome = models.TextField(
        blank=True,
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True once the receiving clinician has opened the referral thread."
    )

    # institution FK for InstitutionScopedManager scoping
    institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referrals_owned_received',
        db_index=True,
        help_text="Owning institution for scoping. Same as to_institution."
    )

    objects = InstitutionScopedManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['referral_uuid']),
            models.Index(fields=['to_institution', 'status']),
        ]

    def __str__(self):
        return f"ReferralReceived[{self.referral_uuid}] {self.status}"


class ReferralMessage(TimeStampedModel, UserTrackingMixin):
    """
    A consultation message in a referral thread.

    Linked to the referral via referral_uuid (no direct FK to ReferralSent/Received —
    allows messages to be retrieved from either institution's side).
    FR62, FR64.
    """
    OPINION = 'OPINION'
    MESSAGE_TYPE_CHOICES = [
        (OPINION, 'Clinical Opinion'),
    ]

    # Links to both ReferralSent and ReferralReceived via UUID
    referral_uuid = models.UUIDField(
        db_index=True,
        help_text="Shared referral_uuid — links to both ReferralSent and ReferralReceived."
    )
    sender = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referral_messages_sent',
        db_index=True,
    )
    sender_institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.SET_NULL,
        null=True,
        related_name='referral_messages',
        db_index=True,
        help_text="Institution of the sender at the time of the message (for display badge)."
    )
    body = models.TextField()
    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPE_CHOICES,
        default=OPINION,
    )

    class Meta:
        ordering = ['created_at']  # Chronological in thread view

    def __str__(self):
        return f"ReferralMessage[{self.referral_uuid}] by {self.sender_id}"
```

**Note on `institution` FK for scoping:** `ReferralSent` and `ReferralReceived` have an `institution` FK
(separate from `from_institution` / `to_institution`) that is used by `InstitutionScopedManager`.
`ReferralSent.institution = from_institution` (set at creation).
`ReferralReceived.institution = to_institution` (set at creation).

**Import of `InstitutionScopedManager` inside class body:** Python class bodies do not execute
import statements lazily. Move the import to the module-level or use a string reference:

```python
# At top of referral/models.py — safe because institution/ is a dependency:
from institution.managers import InstitutionScopedManager
```

Then in each model class:
```python
objects = InstitutionScopedManager()
```

**App dependency direction:** `referral/` imports from `institution/` (one-way). `institution/`
must NOT import from `referral/` (circular dependency prevention).

---

### Task 5: `ndas/settings.py` — INSTALLED_APPS Update

In `ndas/settings.py`, add after `institution.apps.InstitutionConfig`:

```python
INSTALLED_APPS = [
    ...
    'institution.apps.InstitutionConfig',
    'referral.apps.ReferralConfig',   # ← ADD THIS
    'users.apps.UsersConfig',
    ...
]
```

---

### Task 6: `referral/urls.py` and `ndas/urls.py` Inclusion

**`referral/urls.py`:**
```python
from django.urls import path
from referral import views

app_name = 'referral'

urlpatterns = [
    # Story 4.3: Referral Inbox
    # path('inbox/', views.referral_inbox, name='referral-inbox'),

    # Story 4.3: Thread Panel (HTMX partial)
    # path('thread/<uuid:referral_uuid>/', views.referral_thread_panel, name='referral-thread-panel'),

    # Story 4.4: Reply
    # path('thread/<uuid:referral_uuid>/reply/', views.referral_reply, name='referral-reply'),

    # Story 4.5: Close
    # path('thread/<uuid:referral_uuid>/close/', views.referral_close, name='referral-close'),

    # Story 5.2: Notification count (HTMX polling)
    # path('notifications/count/', views.notification_count, name='notification-count'),

    # Story 5.3: Notification panel
    # path('notifications/panel/', views.notification_panel, name='notification-panel'),
    # path('notifications/<int:notification_id>/read/', views.notification_mark_read, name='notification-mark-read'),
    # path('notifications/mark-all-read/', views.notification_mark_all_read, name='notification-mark-all-read'),
]
```

**`ndas/urls.py` — add referral include:**

Find the urlpatterns list in `ndas/urls.py` and add:
```python
from django.urls import path, include

urlpatterns = [
    ...
    # Story 4.1: Referral system
    path('referral/', include('referral.urls')),
    ...
]
```

Check existing `ndas/urls.py` for the exact location to insert.

---

### Task 7: `referral/admin.py`

Register models for Django admin (useful for development inspection):

```python
from django.contrib import admin
from referral.models import ReferralSent, ReferralReceived, ReferralMessage

@admin.register(ReferralSent)
class ReferralSentAdmin(admin.ModelAdmin):
    list_display = ['referral_uuid', 'from_institution', 'to_institution', 'status', 'created_at']
    list_filter = ['status', 'from_institution']
    readonly_fields = ['referral_uuid']

@admin.register(ReferralReceived)
class ReferralReceivedAdmin(admin.ModelAdmin):
    list_display = ['referral_uuid', 'from_institution', 'to_institution', 'status', 'created_at']
    list_filter = ['status', 'to_institution']
    readonly_fields = ['referral_uuid']

@admin.register(ReferralMessage)
class ReferralMessageAdmin(admin.ModelAdmin):
    list_display = ['referral_uuid', 'sender', 'message_type', 'created_at']
    readonly_fields = ['referral_uuid']
```

---

### Task 8: `referral/tests/test_models.py`

```python
"""
referral/tests/test_models.py
Tests for Referral App Data Models (Story 4.1).
"""
import uuid
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, ReferralStatus
from referral.models import ReferralSent, ReferralReceived, ReferralMessage

User = get_user_model()


class ReferralModelsTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_ref', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771441001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='Referral Alpha', slug='ref-alpha',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Referral Beta', slug='ref-beta',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.clinician_a = User.objects.create_user(
            username='clin_a_ref', password='Testpass1!',
            first_name='Clin', last_name='A',
            position='Medical Officer', mobile_primary='0771441002',
            user_type=UserType.USER, institution=self.inst_a,
        )
        self.clinician_b = User.objects.create_user(
            username='clin_b_ref', password='Testpass1!',
            first_name='Clin', last_name='B',
            position='Medical Officer', mobile_primary='0771441003',
            user_type=UserType.USER, institution=self.inst_b,
        )
        from patients.models import Patient
        self.patient = Patient.objects.create(
            institution=self.inst_a,
            baby_name='Referral Patient', mother_name='Test Mother',
            added_by=self.clinician_a, last_edit_by=self.clinician_a,
        )


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ReferralStatusChoicesTest(ReferralModelsTestBase):
    def test_referral_status_choices_exist(self):
        """AC #1: ReferralStatus choices PENDING/REPLIED/CLOSED must exist."""
        self.assertEqual(ReferralStatus.PENDING, 'PENDING')
        self.assertEqual(ReferralStatus.REPLIED, 'REPLIED')
        self.assertEqual(ReferralStatus.CLOSED, 'CLOSED')


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ReferralUUIDCouplingTest(ReferralModelsTestBase):
    def _make_referral_pair(self):
        """Helper: create a matched ReferralSent + ReferralReceived pair."""
        shared_uuid = uuid.uuid4()
        snapshot = {'schema_version': 1, 'patient_name': 'Referral Patient'}
        sent = ReferralSent.objects.create(
            from_institution=self.inst_a,
            to_institution=self.inst_b,
            patient=self.patient,
            from_clinician=self.clinician_a,
            to_clinician=self.clinician_b,
            referral_uuid=shared_uuid,
            initial_message='Please assess this patient.',
            snapshot_data=snapshot,
            institution=self.inst_a,
        )
        received = ReferralReceived.objects.create(
            to_institution=self.inst_b,
            from_institution=self.inst_a,
            patient_name='Referral Patient',
            from_clinician_name='Clin A',
            to_clinician=self.clinician_b,
            referral_uuid=shared_uuid,  # AC #2: copied, not regenerated
            initial_message='Please assess this patient.',
            snapshot_data=snapshot,
            institution=self.inst_b,
        )
        return sent, received

    def test_referral_uuid_is_shared(self):
        """AC #2: ReferralReceived must copy the same UUID from ReferralSent."""
        sent, received = self._make_referral_pair()
        self.assertEqual(sent.referral_uuid, received.referral_uuid,
            "AC #2: ReferralSent and ReferralReceived must share the same referral_uuid")

    def test_both_default_to_pending(self):
        """AC #2: Both records must default to status=PENDING."""
        sent, received = self._make_referral_pair()
        self.assertEqual(sent.status, ReferralStatus.PENDING)
        self.assertEqual(received.status, ReferralStatus.PENDING)

    def test_received_survives_sent_deletion(self):
        """AC #3: ReferralReceived remains accessible when ReferralSent is deleted."""
        sent, received = self._make_referral_pair()
        shared_uuid = sent.referral_uuid
        received_pk = received.pk

        sent.delete()  # Simulate institution A being suspended / ReferralSent deleted

        # ReferralReceived must still be accessible
        try:
            survivor = ReferralReceived.objects.get(pk=received_pk)
            self.assertEqual(survivor.referral_uuid, shared_uuid,
                "AC #3: ReferralReceived must remain intact after ReferralSent deletion")
        except ReferralReceived.DoesNotExist:
            self.fail("AC #3: ReferralReceived must survive deletion of ReferralSent")

    def test_institution_scoped_manager_filters_correctly(self):
        """AC #4: InstitutionScopedManager returns only own-institution records."""
        sent, received = self._make_referral_pair()
        # ReferralSent owned by inst_a
        inst_a_sent = ReferralSent.objects.for_institution(self.inst_a)
        self.assertIn(sent, inst_a_sent)
        # ReferralReceived owned by inst_b
        inst_b_received = ReferralReceived.objects.for_institution(self.inst_b)
        self.assertIn(received, inst_b_received)


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ReferralMessageTest(ReferralModelsTestBase):
    def test_message_links_via_uuid(self):
        """AC #1: ReferralMessage links to referral by UUID."""
        shared_uuid = uuid.uuid4()
        msg = ReferralMessage.objects.create(
            referral_uuid=shared_uuid,
            sender=self.clinician_b,
            sender_institution=self.inst_b,
            body='Clinical opinion: Patient appears stable.',
            message_type=ReferralMessage.OPINION,
            added_by=self.clinician_b,
            last_edit_by=self.clinician_b,
        )
        self.assertEqual(msg.referral_uuid, shared_uuid)
        self.assertEqual(msg.message_type, ReferralMessage.OPINION)
```

---

### Project Structure Notes

**Files CREATED in this story:**
- `referral/__init__.py`
- `referral/apps.py`
- `referral/models.py` — `ReferralSent`, `ReferralReceived`, `ReferralMessage`
- `referral/views.py` (empty stub)
- `referral/urls.py` (commented-out stubs)
- `referral/forms.py` (empty stub)
- `referral/signals.py` (empty stub)
- `referral/utils.py` (empty stub)
- `referral/admin.py`
- `referral/migrations/__init__.py`
- `referral/migrations/0001_initial.py` (generated by makemigrations)
- `referral/tests/__init__.py`
- `referral/tests/test_models.py`

**Files MODIFIED in this story:**
- `ndas/custom_codes/choice.py` — add `ReferralStatus` class
- `ndas/settings.py` — add `referral.apps.ReferralConfig` to `INSTALLED_APPS`
- `ndas/urls.py` — add `path('referral/', include('referral.urls'))`

---

### Key Architecture Notes

1. **No FK between ReferralSent and ReferralReceived** — this is intentional per FR66. The two records are linked ONLY by `referral_uuid`. This ensures each institution's record is fully self-contained.

2. **`institution` FK on ReferralSent and ReferralReceived** — this is for `InstitutionScopedManager` scoping. `ReferralSent.institution = from_institution`, `ReferralReceived.institution = to_institution`. Set this at creation time.

3. **`snapshot_data` is immutable after creation** — never update it. This is enforced by convention (no update code) rather than DB constraint. Views must not allow editing snapshot_data.

4. **`ReferralMessage.referral_uuid` has no FK** — messages are linked via UUID, so both institutions can query all messages in a thread without cross-institution access to each other's `ReferralSent`/`ReferralReceived` records.

5. **`ReferralConfig.ready()` is a stub** — signals are registered in Story 5.1.

---

### References

- FR60–FR66: Referral system requirements [Source: `_bmad-output/planning-artifacts/epics.md#Epic 4`]
- FR66: Dual institution records via UUID [Source: `_bmad-output/planning-artifacts/epics.md#FR66`]
- Architecture: ReferralSent/ReferralReceived fields [Source: `_bmad-output/planning-artifacts/epics.md#Data Models`]
- Architecture: `referral_uuid` generated once at ReferralSent creation; ReferralReceived copies it [Source: `_bmad-output/planning-artifacts/epics.md#Referral Atomicity`]
- Architecture: All new models inherit TimeStampedModel + UserTrackingMixin [Source: `_bmad-output/project-context.md#Model Pattern`]
- Architecture: `InstitutionScopedManager` from Story 1.4 [Source: `_bmad-output/implementation-artifacts/1-4-institution-scoped-orm-manager-view-updates.md`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
