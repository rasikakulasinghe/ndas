# Story 1.6: Default Institution Data Migration

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **platform operator**,
I want all existing patient, user, and file data migrated atomically to a default institution,
So that the existing single-institution deployment becomes the first institution in the multi-institution network with zero data loss.

## Acceptance Criteria

1. **Given** Django data migration `institution/migrations/0002_default_institution_data.py` is applied
   **When** the migration runs
   **Then** a `default_institution` record is created atomically with the existing `Subscription` singleton's values copied to its subscription fields

2. **Given** the migration completes successfully
   **When** all `Patient` records are queried
   **Then** every patient has `institution=default_institution` — zero null `institution` FKs exist

3. **Given** the migration completes successfully
   **When** all `Video` and `Attachment` file paths are checked
   **Then** every file reference is updated to `/{default_institution_slug}/videos/` or `/{default_institution_slug}/attachments/`

4. **Given** all `CustomUser` records (non-SUPERADMIN) are checked after migration
   **When** the user queryset is reviewed
   **Then** every non-SUPERADMIN user has `institution=default_institution` with no nulls

5. **Given** `MULTI_INSTITUTION_ENABLED=False` after the migration has been applied
   **When** the system processes requests
   **Then** behaviour is identical to the pre-Phase-2 single-institution deployment

## Tasks / Subtasks

- [ ] Task 1: Add `DEFAULT_INSTITUTION_NAME` and `DEFAULT_INSTITUTION_SLUG` to `ndas/settings.py` (AC: #1)
  - [ ] Add `DEFAULT_INSTITUTION_NAME = config('DEFAULT_INSTITUTION_NAME', default='Default Institution')`
  - [ ] Add `DEFAULT_INSTITUTION_SLUG = config('DEFAULT_INSTITUTION_SLUG', default='default')`
  - [ ] Place after `MULTI_INSTITUTION_ENABLED` setting (end of settings.py)
  - [ ] Operator should set these in `.env` to match their clinic name before running migration

- [ ] Task 2: Create `institution/migrations/0002_default_institution_data.py` (AC: #1, #2, #3, #4)
  - [ ] Write `RunPython` data migration with the complete `migrate_to_default_institution` function
  - [ ] Step A: Resolve default institution name/slug from settings
  - [ ] Step B: Map Subscription singleton status → SubscriptionStatus (see mapping in Dev Notes)
  - [ ] Step C: Create Institution record with values from Subscription singleton
  - [ ] Step D: Assign `institution=default_institution` to all Patient records (bulk_update)
  - [ ] Step E: Assign `institution=default_institution` to all non-SUPERADMIN CustomUser records
  - [ ] Step F: Update Video and Attachment file path references in DB (see Dev Notes)
  - [ ] Step G: Move physical media files on disk (resilient — log warnings on failure, don't fail migration)
  - [ ] Wrap entire function body in `transaction.atomic()`
  - [ ] See exact migration code in Dev Notes

- [ ] Task 3: Write reverse migration (AC: #1)
  - [ ] Provide `reverse_migration` function in the `RunPython` second argument
  - [ ] Reverse: delete the `default_institution` record (it has PROTECT FK from patients/users — check for this)
  - [ ] **NOTE:** Physical file moves cannot be automatically reversed. Document this clearly in code comment.

- [ ] Task 4: Verify migration dependencies (AC: all)
  - [ ] Migration must depend on `('institution', '0001_initial')`
  - [ ] Migration must depend on `('patients', '0008_add_institution_fk')` — Patient.institution FK
  - [ ] Migration must depend on `('patients', '0009_alter_attachment_attachment')` — Attachment path callable
  - [ ] Migration must depend on `('video', '0007_alter_video_video_file')` — Video path callable
  - [ ] Migration must depend on `('users', '0009_add_user_type_institution')` — User.institution FK
  - [ ] See exact dependencies list in Dev Notes

- [ ] Task 5: Write tests for Story 1.6 (AC: all)
  - [ ] Add tests to `institution/tests/` — see test code in Dev Notes
  - [ ] Test: Institution record exists after migration (use `call_command('migrate')` or load fixtures)
  - [ ] Test: All existing Patient records have `institution` set (non-null)
  - [ ] Test: All existing non-SUPERADMIN users have `institution` set
  - [ ] Test: Video.video_file.name starts with `{default_slug}/videos/` after migration
  - [ ] Test: Attachment.attachment.name starts with `{default_slug}/attachments/` after migration

- [ ] Task 6: Run migration and verify (AC: all)
  - [ ] `python manage.py migrate` — apply all pending migrations in order
  - [ ] `python manage.py shell` — verify: `Institution.objects.count() == 1`
  - [ ] Verify: `Patient.objects.filter(institution=None).count() == 0`
  - [ ] Verify: `CustomUser.objects.filter(institution=None, user_type__in=['USER','ADMIN']).count() == 0`
  - [ ] Verify: `Video.objects.filter(video_file__startswith='videos/').count() == 0`
  - [ ] Verify: `Attachment.objects.filter(attachment__startswith='attachments/').count() == 0`
  - [ ] `python manage.py test institution` — full suite
  - [ ] `python manage.py test` — no regressions

## Dev Notes

### Dependencies: Stories 1.1–1.5 Must All Be Complete First

This migration is the capstone of Epic 1. It MUST run after:
- Story 1.1: `institution/migrations/0001_initial.py` (Institution model exists)
- Story 1.2: `users/migrations/0009_add_user_type_institution.py` (User.user_type + User.institution FK)
- Story 1.4: `patients/migrations/0008_add_institution_fk.py` (Patient.institution FK)
- Story 1.5: `patients/migrations/0009_alter_attachment_attachment.py` + `video/migrations/0007_alter_video_video_file.py` (path callables)

**Before starting:** `python manage.py showmigrations` must show `[X]` for all above.

### `Subscription` Singleton → `Institution` Field Mapping

The `Subscription` model (users/models.py line 564) uses lowercase old-style `SUBSCRIPTION_STATUS_CHOICES`:
- `'active'` → `SubscriptionStatus.ACTIVE` (`'ACTIVE'`)
- `'expired'` → `SubscriptionStatus.EXPIRED` (`'EXPIRED'`)
- `'grace_period'` → `SubscriptionStatus.GRACE` (`'GRACE'`)
- Any other value → `SubscriptionStatus.ACTIVE` (safe default)

Field mapping from `Subscription` to `Institution`:

| Subscription field | Institution field | Notes |
|-------------------|-------------------|-------|
| `start_date` | `subscription_start` | Direct copy |
| computed `expiration_date + timedelta(grace_period_days)` | `grace_period_end` | `start_date + duration_days + grace_period_days` |
| `status` (lowercase) | `subscription_status` (uppercase) | See mapping above |
| (always True for live system) | `is_active = True` | |

**Not mapped:** `subscription_type`, `billing_amount`, `notes`, `duration_days`, `grace_period_days` — the new Institution model does not track these.

### `DEFAULT_INSTITUTION_NAME` and `DEFAULT_INSTITUTION_SLUG` Settings

Add to `ndas/settings.py` (after `MULTI_INSTITUTION_ENABLED`, end of file):

```python
# Default Institution Configuration for Story 1.6 data migration
# Set these in .env before running 'python manage.py migrate' for the first time
DEFAULT_INSTITUTION_NAME = config('DEFAULT_INSTITUTION_NAME', default='Default Institution')
DEFAULT_INSTITUTION_SLUG = config('DEFAULT_INSTITUTION_SLUG', default='default')
```

**Instructions for operator:** Before running the migration in production, set:
```ini
# .env
DEFAULT_INSTITUTION_NAME=Lady Ridgeway Hospital
DEFAULT_INSTITUTION_SLUG=lady-ridgeway
```

If not configured, slug will be `'default'` and name `'Default Institution'`. These can be changed later via admin (name only — slug is immutable after creation).

### `institution/migrations/0002_default_institution_data.py` — Complete Spec

```python
# institution/migrations/0002_default_institution_data.py

import os
import shutil
import logging
from datetime import timedelta, date
from django.db import migrations
from django.conf import settings

logger = logging.getLogger(__name__)


# Status mapping: old Subscription.status (lowercase) → new SubscriptionStatus (uppercase)
_SUBSCRIPTION_STATUS_MAP = {
    'active': 'ACTIVE',
    'expired': 'EXPIRED',
    'grace_period': 'GRACE',
}


def migrate_to_default_institution(apps, schema_editor):
    """
    Atomic data migration: create default_institution from existing Subscription singleton,
    then assign all existing Patients, Users, and file records to it.

    Physical media files are moved to the institution-partitioned directory structure.
    File move failures are logged as warnings but do NOT abort the migration.
    """
    from django.db import transaction

    Institution = apps.get_model('institution', 'Institution')
    Subscription = apps.get_model('users', 'Subscription')
    Patient = apps.get_model('patients', 'Patient')
    CustomUser = apps.get_model('users', 'CustomUser')
    Video = apps.get_model('video', 'Video')
    Attachment = apps.get_model('patients', 'Attachment')

    with transaction.atomic():
        # ── Step A: Resolve default institution config ───────────────────────
        default_name = getattr(settings, 'DEFAULT_INSTITUTION_NAME', 'Default Institution')
        default_slug = getattr(settings, 'DEFAULT_INSTITUTION_SLUG', 'default')

        # ── Step B: Read Subscription singleton ──────────────────────────────
        sub = Subscription.objects.filter(pk=1).first()

        # Map subscription fields
        if sub:
            old_status = sub.status  # 'active', 'expired', 'grace_period'
            new_status = _SUBSCRIPTION_STATUS_MAP.get(old_status, 'ACTIVE')
            subscription_start = sub.start_date
            # grace_period_end = expiration_date + grace_period_days
            expiration = sub.start_date + timedelta(days=sub.duration_days)
            grace_period_end = expiration + timedelta(days=sub.grace_period_days)
        else:
            # No subscription record exists — use safe defaults
            new_status = 'ACTIVE'
            subscription_start = date.today()
            grace_period_end = None

        # ── Step C: Create the default institution ────────────────────────────
        default_institution = Institution.objects.create(
            name=default_name,
            slug=default_slug,
            subscription_status=new_status,
            subscription_start=subscription_start,
            grace_period_end=grace_period_end,
            is_active=True,
        )

        # ── Step D: Assign all Patients to default_institution ────────────────
        patient_count = Patient.objects.filter(institution__isnull=True).update(
            institution=default_institution
        )
        logger.info(f"[Migration 0002] Assigned {patient_count} patients to {default_slug}")

        # ── Step E: Assign all non-SUPERADMIN Users to default_institution ────
        user_count = CustomUser.objects.filter(
            institution__isnull=True,
        ).exclude(
            user_type='SUPERADMIN'
        ).update(institution=default_institution)
        logger.info(f"[Migration 0002] Assigned {user_count} users to {default_slug}")

        # ── Step F: Update Video file path references in DB ───────────────────
        _migrate_video_paths(Video, default_slug)

        # ── Step G: Update Attachment file path references in DB ──────────────
        _migrate_attachment_paths(Attachment, default_slug)

    # ── Step H: Move physical files on disk (OUTSIDE transaction) ────────────
    # File system operations cannot be rolled back — run after DB commit
    media_root = str(settings.MEDIA_ROOT)
    _move_physical_video_files(Video, default_slug, media_root)
    _move_physical_attachment_files(Attachment, default_slug, media_root)


def _migrate_video_paths(Video, default_slug):
    """
    Update Video.video_file DB field to use institution-partitioned path.

    Old path pattern: 'videos/{year}/{month}/{filename}'
    New path pattern: '{default_slug}/videos/{year}/{month}/{filename}'

    If old path does NOT start with 'videos/', prefix with '{slug}/videos/' as fallback.
    Already-migrated paths (starting with '{slug}/') are left unchanged (idempotent).
    """
    updated = 0
    for video in Video.objects.all().only('pk', 'video_file'):
        old_name = video.video_file.name if video.video_file else ''
        if not old_name or old_name.startswith(f'{default_slug}/'):
            continue  # Already migrated or empty

        if old_name.startswith('videos/'):
            # Replace 'videos/' prefix with '{slug}/videos/'
            new_name = f"{default_slug}/videos/{old_name[len('videos/'):]}"
        else:
            # Unknown prefix: just put under {slug}/videos/
            new_name = f"{default_slug}/videos/{os.path.basename(old_name)}"

        Video.objects.filter(pk=video.pk).update(video_file=new_name)
        updated += 1
    logger.info(f"[Migration 0002] Updated {updated} video file paths to {default_slug}/videos/")


def _migrate_attachment_paths(Attachment, default_slug):
    """
    Update Attachment.attachment DB field to use institution-partitioned path.

    Old path pattern: 'attachments/{filename}'
    New path pattern: '{default_slug}/attachments/{filename}'

    Already-migrated paths are left unchanged (idempotent).
    """
    updated = 0
    for att in Attachment.objects.all().only('pk', 'attachment'):
        old_name = att.attachment.name if att.attachment else ''
        if not old_name or old_name.startswith(f'{default_slug}/'):
            continue  # Already migrated or empty

        if old_name.startswith('attachments/'):
            new_name = f"{default_slug}/attachments/{old_name[len('attachments/'):]}"
        else:
            new_name = f"{default_slug}/attachments/{os.path.basename(old_name)}"

        Attachment.objects.filter(pk=att.pk).update(attachment=new_name)
        updated += 1
    logger.info(f"[Migration 0002] Updated {updated} attachment file paths to {default_slug}/attachments/")


def _move_physical_video_files(Video, default_slug, media_root):
    """
    Move physical video files from old paths to institution-partitioned paths on disk.

    Resilient: failures are logged as warnings, not raised — migration has already committed.
    """
    moved, skipped, failed = 0, 0, 0
    for video in Video.objects.all().only('pk', 'video_file'):
        new_name = video.video_file.name if video.video_file else ''
        if not new_name:
            continue

        # Derive old name: reverse the path migration
        # New: '{slug}/videos/...' → Old: 'videos/...'
        if new_name.startswith(f'{default_slug}/videos/'):
            old_relative = 'videos/' + new_name[len(f'{default_slug}/videos/'):]
        else:
            skipped += 1
            continue

        old_path = os.path.join(media_root, old_relative)
        new_path = os.path.join(media_root, new_name)

        if not os.path.exists(old_path):
            skipped += 1
            continue  # File not on this server (may be prod with separate storage)

        if os.path.exists(new_path):
            skipped += 1
            continue  # Already moved

        try:
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.move(old_path, new_path)
            moved += 1
        except OSError as e:
            logger.warning(f"[Migration 0002] Could not move video file {old_path} → {new_path}: {e}")
            failed += 1

    logger.info(f"[Migration 0002] Video files: moved={moved}, skipped={skipped}, failed={failed}")
    if failed > 0:
        logger.warning(
            f"[Migration 0002] {failed} video file(s) could not be moved. "
            f"DB references are correct; run 'python manage.py fix_media_paths' manually to relocate files."
        )


def _move_physical_attachment_files(Attachment, default_slug, media_root):
    """
    Move physical attachment files from old paths to institution-partitioned paths on disk.
    """
    moved, skipped, failed = 0, 0, 0
    for att in Attachment.objects.all().only('pk', 'attachment'):
        new_name = att.attachment.name if att.attachment else ''
        if not new_name:
            continue

        if new_name.startswith(f'{default_slug}/attachments/'):
            old_relative = 'attachments/' + new_name[len(f'{default_slug}/attachments/'):]
        else:
            skipped += 1
            continue

        old_path = os.path.join(media_root, old_relative)
        new_path = os.path.join(media_root, new_name)

        if not os.path.exists(old_path):
            skipped += 1
            continue

        if os.path.exists(new_path):
            skipped += 1
            continue

        try:
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.move(old_path, new_path)
            moved += 1
        except OSError as e:
            logger.warning(f"[Migration 0002] Could not move attachment {old_path} → {new_path}: {e}")
            failed += 1

    logger.info(f"[Migration 0002] Attachment files: moved={moved}, skipped={skipped}, failed={failed}")
    if failed > 0:
        logger.warning(
            f"[Migration 0002] {failed} attachment file(s) could not be moved. "
            f"DB references are correct; files can be relocated manually."
        )


def reverse_migration(apps, schema_editor):
    """
    Reverse this migration — deletes the default_institution record.

    IMPORTANT: Physical file moves CANNOT be reversed automatically.
    Reversing will attempt to delete the Institution record. This will fail with
    a django.db.models.ProtectedError if any Patient or CustomUser still FK-references it.
    Run only in a clean test environment.
    """
    from django.conf import settings
    Institution = apps.get_model('institution', 'Institution')
    default_slug = getattr(settings, 'DEFAULT_INSTITUTION_SLUG', 'default')
    Institution.objects.filter(slug=default_slug).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('institution', '0001_initial'),
        ('patients', '0008_add_institution_fk'),
        ('patients', '0009_alter_attachment_attachment'),
        ('video', '0007_alter_video_video_file'),
        ('users', '0009_add_user_type_institution'),
    ]

    operations = [
        migrations.RunPython(
            migrate_to_default_institution,
            reverse_code=reverse_migration,
        ),
    ]
```

### Critical Warning: Transaction vs File I/O

The migration splits work into two phases:
1. **DB operations inside `transaction.atomic()`**: Institution creation, Patient bulk_update, User bulk_update, Video/Attachment file path name updates
2. **Physical file moves OUTSIDE transaction**: `_move_physical_video_files` and `_move_physical_attachment_files` run AFTER the transaction commits

**Why?** File system operations cannot be rolled back. If the transaction rolls back after files were moved, the DB references would point to new paths but files are gone from old paths. Running file moves after DB commit ensures: if file moves fail, DB is already correct (pointing to new paths) and operator can fix file locations manually.

**Result of partial file move failure:** DB has correct new path; old file still at old disk location. Django's `FileField.url` and `FileField.path` will point to non-existent files — but this is recoverable. DB integrity is preserved.

### Migration Dependencies — Exact List

```python
dependencies = [
    ('institution', '0001_initial'),              # Institution model must exist
    ('patients', '0008_add_institution_fk'),       # Patient.institution FK (Story 1.4)
    ('patients', '0009_alter_attachment_attachment'),  # Attachment upload_to (Story 1.5)
    ('video', '0007_alter_video_video_file'),      # Video upload_to (Story 1.5)
    ('users', '0009_add_user_type_institution'),   # User.user_type + User.institution (Story 1.2)
]
```

**Note:** The exact migration file numbers may differ if `makemigrations` generates different names. Verify each dependency number by running `python manage.py showmigrations` before writing the dependency list.

### `is_superuser` vs `user_type` for SUPERADMIN Exclusion

In Step E (excluding SUPERADMIN from institution assignment), the code uses `.exclude(user_type='SUPERADMIN')`. This requires Story 1.2's migration to have already run (sets `user_type='SUPERADMIN'` for all `is_superuser=True` users).

**Fallback**: If for any reason `user_type` was not set by Story 1.2's migration (recovery scenario), also add:
```python
.exclude(is_superuser=True)
```
Making the full exclusion: `.filter(institution__isnull=True).exclude(user_type='SUPERADMIN').exclude(is_superuser=True)`.

### Subscription Singleton — Read Pattern in Migration

Using `apps.get_model()` returns the historical version of the model. `Subscription.get_global_subscription()` is a class method on the real model — NOT available via `apps.get_model()`. Use `filter(pk=1).first()` instead:

```python
# CORRECT:
sub = Subscription.objects.filter(pk=1).first()

# WRONG — class method not available on historical model:
sub = Subscription.get_global_subscription()
```

### File Path Edge Cases

The file path migration handles these cases:
- **Empty file field**: `video_file.name == ''` or `None` → skip
- **Already migrated path**: starts with `'{slug}/'` → skip (idempotent)
- **Unknown prefix** (not `videos/` or `attachments/`): use `os.path.basename()` as fallback — logs warning
- **File not on disk**: DB update still happens, file move skipped (may be different server / object storage)
- **Destination already exists**: skip move (file already there from previous partial run)

### Test Code Pattern

Add `institution/tests/test_data_migration.py`:

```python
from django.test import TestCase, override_settings
from django.core.management import call_command
from institution.models import Institution
from patients.models import Patient
from django.contrib.auth import get_user_model

User = get_user_model()


@override_settings(
    DEFAULT_INSTITUTION_NAME='Test Hospital',
    DEFAULT_INSTITUTION_SLUG='test-hospital',
)
class DefaultInstitutionMigrationTest(TestCase):
    """
    Tests for Story 1.6 post-migration state.
    These are STATE tests, not migration execution tests.
    Run AFTER the migration has been applied.
    """

    def test_default_institution_exists(self):
        """AC #1: At least one Institution record exists after migration."""
        self.assertGreaterEqual(Institution.objects.count(), 1)

    def test_no_patients_without_institution(self):
        """AC #2: All Patient records have an institution assigned."""
        null_count = Patient.objects.filter(institution__isnull=True).count()
        self.assertEqual(null_count, 0,
            f"{null_count} patients still have null institution FK after migration")

    def test_no_non_superadmin_users_without_institution(self):
        """AC #4: All non-SUPERADMIN users have institution assigned."""
        from ndas.custom_codes.choice import UserType
        null_count = User.objects.filter(
            institution__isnull=True
        ).exclude(user_type=UserType.SUPERADMIN).count()
        self.assertEqual(null_count, 0,
            f"{null_count} non-SUPERADMIN users still have null institution FK")

    def test_superadmin_users_remain_institution_null(self):
        """SUPERADMIN users should retain institution=None."""
        from ndas.custom_codes.choice import UserType
        null_count = User.objects.filter(
            user_type=UserType.SUPERADMIN,
            institution__isnull=True
        ).count()
        # All SADMINs should have null institution; none should have been assigned
        total_superadmins = User.objects.filter(user_type=UserType.SUPERADMIN).count()
        self.assertEqual(null_count, total_superadmins)


class PathCallableTest(TestCase):
    """Unit tests for path migration logic (not dependent on migration execution)."""

    def test_video_path_strip_and_prepend(self):
        """videos/ prefix is replaced by {slug}/videos/"""
        from institution.migrations._0002_default_institution_data import _migrate_video_paths
        # This test validates the path logic, not the DB — can only be run if we expose the helper
        # See Dev Notes for how to test path logic directly via validators.py test
        pass

    def test_no_video_paths_with_old_prefix(self):
        """AC #3: No Video records have old 'videos/' path prefix after migration."""
        from video.models import Video
        old_path_count = Video.objects.filter(video_file__startswith='videos/').count()
        self.assertEqual(old_path_count, 0)

    def test_no_attachment_paths_with_old_prefix(self):
        """AC #3: No Attachment records have old 'attachments/' path prefix after migration."""
        from patients.models import Attachment
        old_path_count = Attachment.objects.filter(attachment__startswith='attachments/').count()
        self.assertEqual(old_path_count, 0)
```

### `institution/migrations/` — File Naming

The migration is named `0002_default_institution_data.py`. It is a **hand-written** migration (not generated by `makemigrations`). Create it directly with the code from above.

The `institution/migrations/0001_initial.py` was generated by Story 1.1's `makemigrations institution`. Story 1.6 manually creates `0002_default_institution_data.py`.

### Deployment Checklist for Operators

Before running `python manage.py migrate` in a production environment:

1. **Back up the database**: `pg_dump ndas > ndas_backup_$(date +%Y%m%d).sql`
2. **Set `.env` variables**:
   ```ini
   DEFAULT_INSTITUTION_NAME=<Your Clinic Name>
   DEFAULT_INSTITUTION_SLUG=<your-clinic-slug>
   ```
3. **Verify media files exist**: `ls media/videos/ && ls media/attachments/`
4. **Run migration**: `python manage.py migrate institution 0002`
5. **Verify no nulls**: Run verification queries from Task 6
6. **Keep `MULTI_INSTITUTION_ENABLED=False`** until Story 1.7 isolation tests pass

### Project Structure Notes

**Files to CREATE in this story:**
- `institution/migrations/0002_default_institution_data.py` (hand-written, not generated)

**Files to MODIFY in this story:**
- `ndas/settings.py` — add `DEFAULT_INSTITUTION_NAME` and `DEFAULT_INSTITUTION_SLUG`

**Files NOT touched in this story:**
- `users/models.py` — `Subscription` model remains. It is READ by this migration (Subscription values → Institution) but not deleted. Full Subscription retirement is a future task (Phase 3) — the model is not removed until all references are cleaned up
- `users/middleware.py` — `SubscriptionCheckMiddleware` was already replaced in Story 1.3 with `InstitutionContextMiddleware`
- Any existing migrations — do not modify
- Any view files — no view changes in this story

**IMPORTANT: Do NOT delete `Subscription` model or `SubscriptionCheckMiddleware` in this story.** The `Subscription` model still has DB records and its table still exists. The class should remain until a dedicated clean-up story in Phase 3. The model is simply deprecated — no longer driving middleware behavior (Story 1.3 replaced it) but the class and table must remain to avoid migration graph breakage.

### References

- Architecture: Data Migration section [Source: `_bmad-output/planning-artifacts/architecture.md#Data Architecture`]
- Architecture: 13-step sequence — Step 6 [Source: `_bmad-output/planning-artifacts/architecture.md#Decision Impact Analysis`]
- Architecture: MULTI_INSTITUTION_ENABLED until staging validation [Source: `_bmad-output/planning-artifacts/architecture.md#Infrastructure & Deployment`]
- Architecture: institution migrations directory [Source: `_bmad-output/planning-artifacts/architecture.md#Project Structure`]
- Epics: Story 1.6 ACs [Source: `_bmad-output/planning-artifacts/epics.md#Story 1.6`]
- Subscription model fields: subscription_type, start_date, duration_days, billing_amount, status, grace_period_days [Source: `users/models.py:564-618`]
- Subscription.status choices (lowercase: 'active'/'expired'/'grace_period') [Source: `users/models.py:599-606`]
- Subscription.get_global_subscription() uses pk=1 singleton [Source: `users/models.py:819-836`]
- Institution.subscription_status uses SubscriptionStatus (uppercase: 'ACTIVE'/'GRACE'/'EXPIRED') [Source: `_bmad-output/planning-artifacts/architecture.md#Data Architecture`]
- Video.video_file current upload path `videos/%Y/%m/` [Source: `video/models.py:82`]
- Attachment.attachment current upload callable `get_attachment_path_file_name` → `attachments/{filename}` [Source: `ndas/custom_codes/custom_methods.py:213-254`]
- Story 1.2: user_type=SUPERADMIN set for is_superuser=True users [Source: `_bmad-output/implementation-artifacts/1-2-user-institution-binding-role-extension.md`]
- Story 1.4: Patient.institution FK (null=True transitional) [Source: `_bmad-output/implementation-artifacts/1-4-institution-scoped-orm-manager-view-updates.md`]
- Story 1.5: new upload_to callables + 'pending' fallback slug [Source: `_bmad-output/implementation-artifacts/1-5-institution-aware-file-storage.md`]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
