# Story 1.1: Institution Model & App Bootstrap

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **platform operator**,
I want the system to have an Institution entity with a name, immutable slug, and subscription status,
So that multiple distinct clinical institutions can exist as data-isolated tenants within a single deployment.

## Acceptance Criteria

1. **Given** the `institution/` Django app is created and registered in `INSTALLED_APPS`
   **When** a new Institution is saved with name, slug, and subscription_status
   **Then** the record is persisted with `TimeStampedModel` fields (created_at, updated_at) and `UserTrackingMixin` fields (added_by, last_edit_by)
   **And** `SubscriptionStatus` choices (ACTIVE/GRACE/EXPIRED) exist in `ndas/custom_codes/choice.py`

2. **Given** an Institution has been saved with a slug value
   **When** an attempt is made to change the slug and save again
   **Then** the `save()` override raises a `ValidationError` blocking the change, and the slug remains unchanged

3. **Given** `MULTI_INSTITUTION_ENABLED=False` in `settings.py`
   **When** any request is processed by the application
   **Then** the system behaves identically to the pre-Phase-2 single-institution deployment with no new behaviour active

## Tasks / Subtasks

- [ ] Task 1: Add `SubscriptionStatus` TextChoices to `ndas/custom_codes/choice.py` (AC: #1)
  - [ ] Add after existing `SUBSCRIPTION_STATUS_CHOICES` — both coexist (different naming convention)
  - [ ] Keys: `ACTIVE = 'ACTIVE'`, `GRACE = 'GRACE'`, `EXPIRED = 'EXPIRED'`

- [ ] Task 2: Create the `institution/` app directory structure (AC: #1)
  - [ ] Create `institution/` directory with all files listed in Project Structure Notes
  - [ ] **CRITICAL:** App name is `institution` (singular) — see Critical Warnings below
  - [ ] Do NOT use `python manage.py startapp` alone — it creates the wrong structure (missing `tests/` subdirectory)

- [ ] Task 3: Write `institution/apps.py` (AC: #1)
  - [ ] `InstitutionConfig(AppConfig)` with `name = 'institution'`, `default_auto_field = 'django.db.models.BigAutoField'`
  - [ ] `ready()` method present but empty for now (signals will be imported in later stories)

- [ ] Task 4: Write `institution/models.py` — Institution model (AC: #1, #2)
  - [ ] Inherit `TimeStampedModel, UserTrackingMixin` (CLAUDE.md mandatory pattern)
  - [ ] Fields: `name`, `slug`, `logo`, `subscription_status`, `subscription_start`, `grace_period_end`, `is_active`, `created_by` — see Dev Notes for exact spec
  - [ ] `save()` override: raise `ValidationError` if slug is being changed on an existing record
  - [ ] `clean()` method also guards slug immutability
  - [ ] `__str__` returns institution name

- [ ] Task 5: Add `MULTI_INSTITUTION_ENABLED` to `ndas/settings.py` (AC: #3)
  - [ ] Add `MULTI_INSTITUTION_ENABLED = config('MULTI_INSTITUTION_ENABLED', default=False, cast=bool)` after existing settings
  - [ ] Default must be `False` — system safe with no `.env` entry

- [ ] Task 6: Register institution app in `ndas/settings.py` `INSTALLED_APPS` (AC: #1)
  - [ ] Add `'institution.apps.InstitutionConfig'` — placement: before `'users.apps.UsersConfig'` and all existing clinical apps (other apps will later get FKs to Institution)

- [ ] Task 7: Create initial migration (AC: #1)
  - [ ] Run `python manage.py makemigrations institution`
  - [ ] Verify migration creates all Institution table fields correctly

- [ ] Task 8: Write `institution/tests/__init__.py` and `institution/tests/test_models.py` (AC: #1, #2, #3)
  - [ ] Test: Institution saves with correct TimeStampedModel + UserTrackingMixin fields
  - [ ] Test: SubscriptionStatus choices exist and are correct (ACTIVE/GRACE/EXPIRED)
  - [ ] Test: slug immutability — changing slug on existing record raises `ValidationError`
  - [ ] Test: slug immutability — creating new Institution with a slug works fine
  - [ ] Test: `MULTI_INSTITUTION_ENABLED=False` is the default setting value

- [ ] Task 9: Run tests and confirm all pass (AC: all)
  - [ ] `python manage.py test institution`
  - [ ] Confirm no regressions: `python manage.py test` (full suite)

## Dev Notes

### 🚨 CRITICAL WARNINGS — Read Before Writing Any Code

**1. APP NAME IS `institution` (SINGULAR), NOT `institutions` (PLURAL)**

Commit `008f51a` created a scaffold as `institutions/` (plural). Those files were subsequently deleted (visible as `D institutions/*` in git status). The architecture document is unambiguous: the app directory is `institution/` (singular). Using the plural name would break all FK references (e.g., `'institution.Institution'`), URL namespaces, and import paths throughout Phase 2.

**2. `SubscriptionStatus` IS A NEW TextChoices CLASS — NOT A REPLACEMENT**

`ndas/custom_codes/choice.py` already contains `SUBSCRIPTION_STATUS_CHOICES = [('active', ...), ('expired', ...), ('grace_period', ...)]` (line 186). This is used by the legacy `Subscription` model in `users/`. Do NOT modify or delete it. Add the NEW `SubscriptionStatus` TextChoices class alongside it with uppercase keys (`ACTIVE`/`GRACE`/`EXPIRED`) as specified in the architecture.

**3. BOTH `TimeStampedModel` AND `UserTrackingMixin` ARE REQUIRED**

The epics Story 1.1 AC explicitly tests for UserTrackingMixin fields (added_by, last_edit_by). The architecture also lists a separate `created_by` FK (for the SUPERADMIN who onboards the institution). Include both base classes. The `created_by` field is a distinct explicit FK from `UserTrackingMixin.added_by` — `added_by` is auto-populated by `UserActivityMiddleware`, while `created_by` is set programmatically during the atomic onboarding flow in Story 2.3.

### Institution Model — Exact Field Specification

```python
from django.db import models
from django.core.exceptions import ValidationError
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.choice import SubscriptionStatus


class Institution(TimeStampedModel, UserTrackingMixin):
    name = models.CharField(max_length=255, unique=True, db_index=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    logo = models.ImageField(
        upload_to='institution_logos/',  # temporary path; Story 1.5 adds institution-aware paths
        null=True, blank=True
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE
    )
    subscription_start = models.DateField(null=True, blank=True)
    grace_period_end = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='institutions_created',
        help_text="SUPERADMIN who onboarded this institution"
    )

    def save(self, *args, **kwargs):
        if self.pk:
            original = Institution.objects.get(pk=self.pk)
            if original.slug != self.slug:
                raise ValidationError("Institution slug is immutable and cannot be changed after creation.")
        super().save(*args, **kwargs)

    def clean(self):
        if self.pk:
            try:
                original = Institution.objects.get(pk=self.pk)
                if original.slug != self.slug:
                    raise ValidationError({'slug': 'Institution slug is immutable and cannot be changed after creation.'})
            except Institution.DoesNotExist:
                pass

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
```

**Important:** The `logo` `upload_to` path is a temporary placeholder for Story 1.1. It will be updated in Story 1.5 (institution-aware file storage) to `MEDIA_ROOT/{institution_slug}/logo/`.

### `SubscriptionStatus` TextChoices — Exact Spec for `choice.py`

```python
class SubscriptionStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    GRACE = 'GRACE', 'Grace Period'
    EXPIRED = 'EXPIRED', 'Expired'
```

Add this AFTER the existing `SUBSCRIPTION_STATUS_CHOICES` tuple at line ~186 of `ndas/custom_codes/choice.py`. The old tuple is NOT removed.

### `MULTI_INSTITUTION_ENABLED` — Settings Placement

```python
# Multi-Institution Feature Flag (Phase 2)
# Set to True in settings ONLY after staging isolation tests pass (Story 1.7)
MULTI_INSTITUTION_ENABLED = config('MULTI_INSTITUTION_ENABLED', default=False, cast=bool)
```

Add at the end of `ndas/settings.py` (after existing settings). The `decouple.config` is already imported at line 4. No new import needed.

### `INSTALLED_APPS` Ordering — Critical

The `institution` app provides the `Institution` model. Other apps (`patients`, `video`, `reports`, `problemlist`, `users`) will receive FKs to `Institution` in later stories. Django resolves FK references via string `'institution.Institution'`, so install order matters for migrations. Place `institution.apps.InstitutionConfig` before all clinical apps:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    # ... django apps ...
    'ndas',
    'institution.apps.InstitutionConfig',   # ← ADD HERE (before clinical apps)
    'users.apps.UsersConfig',
    'patients.apps.PatientsConfig',
    'video.apps.VideoConfig',
    'reports.apps.ReportsConfig',
    'problemlist.apps.ProblemlistConfig',
    # ... other apps ...
]
```

### App Directory Structure for This Story

Only the files needed for Story 1.1. Other files (`context_processors.py`, `managers.py`, `middleware.py`, `templatetags/`, `urls.py`, `views.py`) are created in later stories.

```
institution/
├── __init__.py            (empty)
├── apps.py                (InstitutionConfig)
├── migrations/
│   ├── __init__.py        (empty)
│   └── 0001_initial.py    (generated by makemigrations)
├── models.py              (Institution model)
└── tests/
    ├── __init__.py        (empty)
    └── test_models.py     (model tests)
```

### `institution/apps.py` — Exact Spec

```python
from django.apps import AppConfig


class InstitutionConfig(AppConfig):
    name = 'institution'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'Institution Management'

    def ready(self):
        pass  # Signal imports will be added in Story 1.3 / Epic 5
```

### Testing Approach

Use `TestCase` from `django.test`. No factories or fixtures needed for Story 1.1 — create test objects directly.

```python
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.conf import settings
from institution.models import Institution
from ndas.custom_codes.choice import SubscriptionStatus


class InstitutionModelTest(TestCase):

    def test_institution_saves_with_timestampedmodel_fields(self):
        inst = Institution.objects.create(name='Test Hospital', slug='test-hospital')
        self.assertIsNotNone(inst.created_at)
        self.assertIsNotNone(inst.updated_at)

    def test_institution_saves_with_usertracking_fields(self):
        inst = Institution.objects.create(name='Test Hospital', slug='test-hospital')
        # added_by and last_edit_by are auto-populated by middleware; here they are null
        self.assertIsNone(inst.added_by)   # acceptable in tests — middleware not active
        self.assertIsNone(inst.last_edit_by)

    def test_subscription_status_choices_exist(self):
        self.assertEqual(SubscriptionStatus.ACTIVE, 'ACTIVE')
        self.assertEqual(SubscriptionStatus.GRACE, 'GRACE')
        self.assertEqual(SubscriptionStatus.EXPIRED, 'EXPIRED')

    def test_slug_immutable_on_update(self):
        inst = Institution.objects.create(name='Test Hospital', slug='test-hospital')
        inst.slug = 'different-slug'
        with self.assertRaises(ValidationError):
            inst.save()

    def test_slug_unchanged_on_update_is_allowed(self):
        inst = Institution.objects.create(name='Test Hospital', slug='test-hospital')
        inst.name = 'Test Hospital Updated'
        inst.save()  # Should not raise — slug unchanged
        inst.refresh_from_db()
        self.assertEqual(inst.slug, 'test-hospital')

    def test_new_institution_creation_with_slug_works(self):
        inst = Institution.objects.create(name='New Hospital', slug='new-hospital')
        self.assertEqual(inst.slug, 'new-hospital')

    def test_multi_institution_enabled_is_false_by_default(self):
        self.assertFalse(settings.MULTI_INSTITUTION_ENABLED)

    def test_institution_str(self):
        inst = Institution.objects.create(name='Test Hospital', slug='test-hospital')
        self.assertEqual(str(inst), 'Test Hospital')
```

### Project Structure Notes

**Files to CREATE in this story:**
- `institution/__init__.py`
- `institution/apps.py`
- `institution/migrations/__init__.py`
- `institution/migrations/0001_initial.py` (generated)
- `institution/models.py`
- `institution/tests/__init__.py`
- `institution/tests/test_models.py`

**Files to MODIFY in this story:**
- `ndas/custom_codes/choice.py` — add `SubscriptionStatus` TextChoices class
- `ndas/settings.py` — add `institution.apps.InstitutionConfig` to `INSTALLED_APPS`, add `MULTI_INSTITUTION_ENABLED`

**Files NOT touched in this story (created in later stories):**
- `institution/context_processors.py` → Story 1.3
- `institution/managers.py` → Story 1.4
- `institution/middleware.py` → Story 1.3
- `institution/templatetags/` → Story 2.2
- `institution/urls.py` → Story 2.1
- `institution/views.py` → Story 2.1
- `institution/tests/test_isolation.py` → Story 1.7
- `institution/tests/test_middleware.py` → Story 1.3
- `patients/models.py` (institution FK) → Story 1.4
- `users/models.py` (user_type + institution FK) → Story 1.2
- `ndas/urls.py` (include institution.urls) → Story 2.1

### References

- Architecture: Institution model fields and app structure [Source: `_bmad-output/planning-artifacts/architecture.md#Data Architecture`]
- Architecture: Institution app directory structure [Source: `_bmad-output/planning-artifacts/architecture.md#Structure Patterns`]
- Architecture: INSTALLED_APPS ordering and InstitutionConfig [Source: `_bmad-output/planning-artifacts/architecture.md#Project Structure & Boundaries`]
- Architecture: 13-step implementation sequence — Step 1 [Source: `_bmad-output/planning-artifacts/architecture.md#Decision Impact Analysis`]
- Epics: Story 1.1 ACs [Source: `_bmad-output/planning-artifacts/epics.md#Story 1.1`]
- Project pattern: TimeStampedModel + UserTrackingMixin mandatory base [Source: `CLAUDE.md#Architecture Patterns`]
- Project pattern: All choices go to `ndas/custom_codes/choice.py` [Source: `CLAUDE.md#Key Rules`]
- Project pattern: decouple.config for settings [Source: `ndas/settings.py`]
- Existing choice.py: `SUBSCRIPTION_STATUS_CHOICES` at line ~186 — do NOT remove [Source: `ndas/custom_codes/choice.py`]
- Prior naming error: `institutions/` (plural) created in commit `008f51a`, already deleted [Source: `git show 008f51a`]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
