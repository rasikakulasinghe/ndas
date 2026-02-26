# Story 5.1: Notification Model & Signal Infrastructure

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **clinician**,
I want the system to automatically create a notification for every referral event — new referral received, reply from specialist, referral closed,
So that I am always informed of consultation activity without having to poll the inbox manually.

## Acceptance Criteria

1. **Given** the `Notification` model is created in `referral/models.py` with fields: `recipient` FK, `notification_type`, `title`, `body`, `link`, `is_read`, and `institution` FK
   **When** the migration runs
   **Then** the `Notification` table is created with all required fields
   **And** `NotificationType` choices (`REFERRAL_RECEIVED`, `REFERRAL_REPLIED`, `REFERRAL_CLOSED`) exist in `ndas/custom_codes/choice.py`

2. **Given** signal handlers are defined in `referral/signals.py` and registered in `ReferralConfig.ready()`
   **When** a new `ReferralSent` record is created (referral submitted)
   **Then** a `Notification` with `notification_type=REFERRAL_RECEIVED` is created for `to_clinician`
   **And** the notification `link` points to the referral thread URL

3. **Given** a `ReferralMessage` is saved
   **When** the `post_save` signal fires
   **Then** a `Notification` with `notification_type=REFERRAL_REPLIED` is created for the other party in the thread (not the sender)

4. **Given** the `referral_status_changed` custom signal is dispatched from the `referral_close` view with `new_status=CLOSED`
   **When** the signal receiver processes the event
   **Then** `Notification` records with `notification_type=REFERRAL_CLOSED` are created for both the sending clinician and the receiving clinician
   **And** each notification's `institution` FK is set to the respective recipient's institution

5. **Given** the signal handlers are inspected
   **When** their module location is checked
   **Then** all `Notification.objects.create()` calls exist exclusively in `referral/signals.py` — no view file contains direct notification creation

## Tasks / Subtasks

- [x] Task 1: Add `NotificationType` to `ndas/custom_codes/choice.py` (AC: #1)
  - [x] `REFERRAL_RECEIVED = 'REFERRAL_RECEIVED', 'Referral Received'`
  - [x] `REFERRAL_REPLIED = 'REFERRAL_REPLIED', 'Referral Replied'`
  - [x] `REFERRAL_CLOSED = 'REFERRAL_CLOSED', 'Referral Closed'`
  - [x] See exact code in Dev Notes

- [x] Task 2: Add `Notification` model to `referral/models.py` (AC: #1)
  - [x] Import `NotificationType` at the top of the file
  - [x] Fields: `recipient` (FK User), `notification_type`, `title`, `body`, `link`, `is_read` (BooleanField), `institution` (FK Institution)
  - [x] `objects = InstitutionScopedManager()`
  - [x] `class Meta: ordering = ['-created_at']`
  - [x] See exact model code in Dev Notes

- [x] Task 3: Generate and apply migration (AC: #1)
  - [x] `python manage.py makemigrations referral`
  - [x] `python manage.py migrate`

- [x] Task 4: Create `referral/signals.py` with signal handlers and custom signal (AC: #2, #3, #4, #5)
  - [x] `referral_status_changed = Signal()` — custom signal for lifecycle events (dispatched from close view)
  - [x] `notify_referral_received()` — `post_save` on `ReferralSent` (created=True only)
  - [x] `notify_referral_replied()` — `post_save` on `ReferralMessage` (created=True only)
  - [x] `notify_referral_closed()` — receiver for `referral_status_changed` (new_status=CLOSED only)
  - [x] All handlers use try/except to suppress signal failures silently (logged)
  - [x] See exact signal code in Dev Notes

- [x] Task 5: Update `referral/apps.py` to import signals in `ready()` (AC: #2, #3, #4)
  - [x] `import referral.signals  # noqa: F401`
  - [x] See exact apps.py code in Dev Notes

- [x] Task 6: Update `referral/views.py` — dispatch `referral_status_changed` from `referral_close` (AC: #4)
  - [x] After the `db_transaction.atomic()` block in `referral_close`, import and dispatch the custom signal
  - [x] See exact code snippet in Dev Notes

- [x] Task 7: Write tests in `referral/tests/test_notifications.py` (AC: #1–#5)
  - [x] See exact test code in Dev Notes

## Dev Notes

### Story 5.1 Position

Story 5.1 = **Step 12** (notification model + signals):
```
    ├── Story 4.6: patient referrals tab  ← done
    ├── Story 5.1: notification model + signals  ← THIS STORY
    ├── Story 5.2: notification bell + real-time count
    └── Story 5.3: notification panel + mark as read
```

**FR Coverage:** FR38 (in-app notification panel), FR67 (REFERRAL_RECEIVED notification), FR68 (REFERRAL_REPLIED notification), FR69 (REFERRAL_CLOSED notification).

---

### Why a Custom Signal for Closure (Not post_save)

The `referral_close` view uses `queryset.update()` for bulk closure:

```python
ReferralSent.objects.filter(referral_uuid=referral_uuid).update(status=ReferralStatus.CLOSED)
```

Django's `QuerySet.update()` does **not** trigger `post_save` signals. A custom signal
dispatched manually from the view is the cleanest solution that keeps all
`Notification.objects.create()` calls inside `referral/signals.py` (AC #5).

---

### Task 1: `NotificationType` in `choice.py`

Add to `ndas/custom_codes/choice.py` after the `ReferralStatus` class:

```python
class NotificationType(models.TextChoices):
    REFERRAL_RECEIVED = 'REFERRAL_RECEIVED', 'Referral Received'
    REFERRAL_REPLIED  = 'REFERRAL_REPLIED',  'Referral Replied'
    REFERRAL_CLOSED   = 'REFERRAL_CLOSED',   'Referral Closed'
```

---

### Task 2: `Notification` Model

Add to `referral/models.py` (after the `ReferralMessage` class).

First, update the import at the top of `referral/models.py`:
```python
from ndas.custom_codes.choice import ReferralStatus, NotificationType
```

Then add the model:

```python
class Notification(TimeStampedModel, UserTrackingMixin):
    """
    In-app notification for referral lifecycle events (FR38, FR67–FR69).

    Scoped to recipient's institution via InstitutionScopedManager.
    Created exclusively by referral/signals.py — never directly by views.
    """
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_notifications',
        db_index=True,
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        db_index=True,
    )
    title   = models.CharField(max_length=200)
    body    = models.TextField(blank=True)
    link    = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    institution = models.ForeignKey(
        'institution.Institution',
        on_delete=models.CASCADE,
        related_name='notifications',
    )

    objects = InstitutionScopedManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.notification_type} → {self.recipient.username} ({self.created_at:%Y-%m-%d})'
```

---

### Task 4: `referral/signals.py`

Create new file `referral/signals.py`:

```python
"""
referral/signals.py

Signal handlers and custom signals for referral lifecycle notifications (FR67–FR69).

All Notification.objects.create() calls live here — never in view files.
Handlers use try/except with logging so a signal failure never breaks a referral action.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal

logger = logging.getLogger(__name__)

# ── Custom signal for lifecycle status changes ─────────────────────────────
# Dispatched from referral_close() after bulk update (bulk update skips post_save).
# kwargs: referral_uuid (UUID), new_status (ReferralStatus), changed_by (User)
referral_status_changed = Signal()


# ── post_save: ReferralSent — new referral received ────────────────────────
@receiver(post_save, sender='referral.ReferralSent')
def notify_referral_received(sender, instance, created, **kwargs):
    """FR67: Notify receiving clinician when a new referral arrives."""
    if not created:
        return
    try:
        from referral.models import Notification
        from ndas.custom_codes.choice import NotificationType
        Notification.objects.create(
            recipient=instance.to_clinician,
            notification_type=NotificationType.REFERRAL_RECEIVED,
            title=f'New referral from {instance.from_institution.name}',
            body=instance.initial_message[:200],
            link=f'/referral/thread/{instance.referral_uuid}/',
            institution=instance.to_institution,
            added_by=instance.from_clinician,
            last_edit_by=instance.from_clinician,
        )
        logger.info(
            'REFERRAL_RECEIVED notification → %s (referral %s)',
            instance.to_clinician.username, instance.referral_uuid,
        )
    except Exception as exc:
        logger.error('notify_referral_received failed: %s', exc, exc_info=True)


# ── post_save: ReferralMessage — reply sent ────────────────────────────────
@receiver(post_save, sender='referral.ReferralMessage')
def notify_referral_replied(sender, instance, created, **kwargs):
    """FR68: Notify the OTHER party when a reply message is saved."""
    if not created:
        return
    try:
        from referral.models import ReferralSent, Notification
        from ndas.custom_codes.choice import NotificationType

        sent = ReferralSent.objects.filter(
            referral_uuid=instance.referral_uuid,
        ).select_related(
            'from_clinician', 'to_clinician',
            'from_institution', 'to_institution',
        ).first()

        if not sent:
            logger.warning(
                'notify_referral_replied: no ReferralSent for uuid=%s', instance.referral_uuid,
            )
            return

        # Recipient = whoever did NOT send this message
        if instance.sender_id == sent.from_clinician_id:
            recipient = sent.to_clinician
            recipient_institution = sent.to_institution
        else:
            recipient = sent.from_clinician
            recipient_institution = sent.from_institution

        Notification.objects.create(
            recipient=recipient,
            notification_type=NotificationType.REFERRAL_REPLIED,
            title=f'Reply from {instance.sender_institution.name}',
            body=instance.body[:200],
            link=f'/referral/thread/{instance.referral_uuid}/',
            institution=recipient_institution,
            added_by=instance.sender,
            last_edit_by=instance.sender,
        )
        logger.info(
            'REFERRAL_REPLIED notification → %s (referral %s)',
            recipient.username, instance.referral_uuid,
        )
    except Exception as exc:
        logger.error('notify_referral_replied failed: %s', exc, exc_info=True)


# ── Custom signal receiver: referral_status_changed — closure ──────────────
@receiver(referral_status_changed)
def notify_referral_closed(sender, referral_uuid, new_status, changed_by, **kwargs):
    """FR69: Notify both clinicians when a referral is closed."""
    try:
        from referral.models import ReferralSent, Notification
        from ndas.custom_codes.choice import NotificationType, ReferralStatus

        if new_status != ReferralStatus.CLOSED:
            return

        sent = ReferralSent.objects.filter(
            referral_uuid=referral_uuid,
        ).select_related(
            'from_clinician', 'to_clinician',
            'from_institution', 'to_institution',
        ).first()

        if not sent:
            return

        # Notify receiving clinician
        Notification.objects.create(
            recipient=sent.to_clinician,
            notification_type=NotificationType.REFERRAL_CLOSED,
            title=f'Referral from {sent.from_institution.name} has been closed',
            body='The referring clinician has closed this referral thread.',
            link=f'/referral/thread/{referral_uuid}/',
            institution=sent.to_institution,
            added_by=changed_by,
            last_edit_by=changed_by,
        )

        # Notify sending clinician (confirms closure)
        Notification.objects.create(
            recipient=sent.from_clinician,
            notification_type=NotificationType.REFERRAL_CLOSED,
            title=f'You closed a referral to {sent.to_institution.name}',
            body='This referral thread is now sealed.',
            link=f'/referral/thread/{referral_uuid}/',
            institution=sent.from_institution,
            added_by=changed_by,
            last_edit_by=changed_by,
        )

        logger.info(
            'REFERRAL_CLOSED notifications created (referral %s, by %s)',
            referral_uuid, changed_by.username,
        )
    except Exception as exc:
        logger.error('notify_referral_closed failed: %s', exc, exc_info=True)
```

---

### Task 5: `referral/apps.py`

Replace `ready(self): pass` with:

```python
from django.apps import AppConfig


class ReferralConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'referral'

    def ready(self):
        import referral.signals  # noqa: F401 — registers all signal handlers
```

---

### Task 6: Dispatch `referral_status_changed` from `referral_close`

In `referral/views.py`, inside `referral_close()`, after the `db_transaction.atomic()` block
(and after the `logger.info(...)` call):

```python
    # Dispatch custom signal so signals.py can create closure notifications (FR69)
    # NOTE: bulk update() skips post_save, so we use a custom signal here.
    from referral.signals import referral_status_changed
    referral_status_changed.send(
        sender=ReferralSent,
        referral_uuid=referral_uuid,
        new_status=ReferralStatus.CLOSED,
        changed_by=request.user,
    )
```

---

### Task 7: `referral/tests/test_notifications.py`

```python
"""
referral/tests/test_notifications.py
Tests for Notification model and signal infrastructure (Story 5.1 — FR67–FR69).
"""
import uuid
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, NotificationType
from referral.models import ReferralSent, ReferralReceived, ReferralMessage, Notification

User = get_user_model()


class NotificationSignalBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_ns', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771000010',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='NS Alpha', slug='ns-alpha',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='NS Beta', slug='ns-beta',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.clin_a = User.objects.create_user(
            username='clin_a_ns', password='Testpass1!',
            first_name='NS', last_name='Alpha',
            position='Medical Officer', mobile_primary='0771000011',
            user_type=UserType.USER, institution=self.inst_a,
        )
        self.clin_b = User.objects.create_user(
            username='clin_b_ns', password='Testpass1!',
            first_name='NS', last_name='Beta',
            position='Consultant', mobile_primary='0771000012',
            user_type=UserType.USER, institution=self.inst_b,
        )
        from patients.models import Patient
        self.patient = Patient.objects.create(
            institution=self.inst_a, baby_name='NS Patient',
            mother_name='NS Mother', added_by=self.clin_a, last_edit_by=self.clin_a,
        )
        self.shared_uuid = uuid.uuid4()

    def _make_referral_pair(self):
        """Create a matching ReferralSent + ReferralReceived pair."""
        sent = ReferralSent.objects.create(
            from_institution=self.inst_a, to_institution=self.inst_b,
            institution=self.inst_a, patient=self.patient,
            from_clinician=self.clin_a, to_clinician=self.clin_b,
            referral_uuid=self.shared_uuid, initial_message='Signal test.',
            snapshot_data={'schema_version': 1},
            added_by=self.clin_a, last_edit_by=self.clin_a,
        )
        ReferralReceived.objects.create(
            to_institution=self.inst_b, from_institution=self.inst_a,
            institution=self.inst_b, patient_name='NS Patient',
            from_clinician_name='NS Alpha', to_clinician=self.clin_b,
            referral_uuid=self.shared_uuid, initial_message='Signal test.',
            snapshot_data={'schema_version': 1},
            added_by=self.clin_a, last_edit_by=self.clin_a,
        )
        return sent


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ReferralReceivedNotificationTest(NotificationSignalBase):
    def test_creates_notification_on_referral_sent_creation(self):
        """FR67: Creating ReferralSent triggers REFERRAL_RECEIVED notification for to_clinician."""
        self._make_referral_pair()
        notif = Notification.objects.filter(
            recipient=self.clin_b,
            notification_type=NotificationType.REFERRAL_RECEIVED,
        ).first()
        self.assertIsNotNone(notif, 'FR67: REFERRAL_RECEIVED notification must be created')
        self.assertEqual(notif.institution, self.inst_b,
            'Notification must be scoped to receiving institution')

    def test_no_notification_on_referral_update(self):
        """FR67: Updating ReferralSent does not create duplicate notifications."""
        sent = self._make_referral_pair()
        count_before = Notification.objects.filter(
            notification_type=NotificationType.REFERRAL_RECEIVED,
        ).count()
        sent.status = 'REPLIED'
        sent.save()
        count_after = Notification.objects.filter(
            notification_type=NotificationType.REFERRAL_RECEIVED,
        ).count()
        self.assertEqual(count_before, count_after,
            'Update (not create) must not trigger additional REFERRAL_RECEIVED notifications')


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ReferralRepliedNotificationTest(NotificationSignalBase):
    def test_creates_notification_when_receiver_replies(self):
        """FR68: Receiver reply creates REFERRAL_REPLIED notification for sender."""
        self._make_referral_pair()
        ReferralMessage.objects.create(
            referral_uuid=self.shared_uuid,
            sender=self.clin_b, sender_institution=self.inst_b,
            body='Specialist opinion here.',
            message_type='OPINION',
            added_by=self.clin_b, last_edit_by=self.clin_b,
        )
        notif = Notification.objects.filter(
            recipient=self.clin_a,
            notification_type=NotificationType.REFERRAL_REPLIED,
        ).first()
        self.assertIsNotNone(notif, 'FR68: REFERRAL_REPLIED notification must be created for the sender')
        self.assertEqual(notif.institution, self.inst_a)


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ReferralClosedNotificationTest(NotificationSignalBase):
    def test_dispatching_referral_status_changed_creates_closed_notifications(self):
        """FR69: Custom signal dispatch creates REFERRAL_CLOSED notifications for both parties."""
        self._make_referral_pair()
        from referral.signals import referral_status_changed
        from ndas.custom_codes.choice import ReferralStatus
        referral_status_changed.send(
            sender=ReferralSent,
            referral_uuid=self.shared_uuid,
            new_status=ReferralStatus.CLOSED,
            changed_by=self.clin_a,
        )
        closed_notifs = Notification.objects.filter(
            notification_type=NotificationType.REFERRAL_CLOSED,
        )
        self.assertGreaterEqual(closed_notifs.count(), 2,
            'FR69: Both clinicians must receive REFERRAL_CLOSED notifications')
        recipients = set(closed_notifs.values_list('recipient_id', flat=True))
        self.assertIn(self.clin_a.id, recipients, 'Sending clinician must be notified')
        self.assertIn(self.clin_b.id, recipients, 'Receiving clinician must be notified')
```

---

### Project Structure Notes

**Files MODIFIED in this story:**
- `ndas/custom_codes/choice.py` — add `NotificationType`
- `referral/models.py` — add `Notification` model; update import of `NotificationType`
- `referral/apps.py` — activate signal import in `ready()`
- `referral/views.py` — dispatch `referral_status_changed` in `referral_close`

**Files CREATED in this story:**
- `referral/signals.py` — all 3 signal handlers + custom signal
- `referral/tests/test_notifications.py` — 4+ tests

---

### References

- FR38: In-app notification panel for referral events [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.1`]
- FR67: REFERRAL_RECEIVED notification trigger [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.1`]
- FR68: REFERRAL_REPLIED notification trigger [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.2`]
- FR69: REFERRAL_CLOSED notification trigger [Source: `_bmad-output/planning-artifacts/epics.md#Story 5.3`]
- NFR23: Notification delivery within 120 seconds [Source: `_bmad-output/planning-artifacts/architecture.md#NFR23`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- NotificationType (choice.py) and Notification model (referral/models.py) were already implemented; created migration 0002 and applied it.
- Created referral/signals.py with all 3 signal handlers (REFERRAL_RECEIVED, REFERRAL_REPLIED, REFERRAL_CLOSED) and custom `referral_status_changed` signal.
- Activated signal registration in referral/apps.py ready().
- Dispatched referral_status_changed signal from referral_close view after bulk update.
- Created referral/tests/test_notifications.py with 4 tests (all pass).
- Fixed patient creation in tests to use VALID_PATIENT_FIELDS (required fields: gender, dob_tob, mo_delivery, birth_weight, ofc, tp_mobile).
- All 52 referral tests pass, no regressions.

### File List

- ndas/custom_codes/choice.py (pre-existing, no change needed)
- referral/models.py (pre-existing, no change needed)
- referral/migrations/0002_notification_and_more.py (CREATED)
- referral/signals.py (CREATED — full implementation)
- referral/apps.py (MODIFIED — activated signal import)
- referral/views.py (MODIFIED — signal dispatch in referral_close)
- referral/tests/test_notifications.py (CREATED)
