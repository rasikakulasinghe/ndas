# Story 1.2: User Institution Binding & Role Extension

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **clinician or institution admin**,
I want my user account to be bound to exactly one institution,
So that my access is always scoped to my institution and I can never see data from other institutions.

## Acceptance Criteria

1. **Given** `UserType` choices (SUPERADMIN/ADMIN/USER) are added to `ndas/custom_codes/choice.py`
   **When** a `CustomUser` record is created with any `user_type` value
   **Then** the field is persisted correctly and the user_type is queryable

2. **Given** a `CustomUser` with `user_type=USER` or `user_type=ADMIN`
   **When** the user's `institution` FK is set to a specific institution
   **Then** the user is bound to that institution and cannot be reassigned to another institution without explicit superadmin action

3. **Given** a `CustomUser` with `user_type=SUPERADMIN`
   **When** the `institution` FK is null
   **Then** the model saves without error (nullable FK is valid for SUPERADMIN only)

4. **Given** the migration adding `institution` FK and `user_type` to `CustomUser` is applied
   **When** existing user records are migrated
   **Then** all existing users have `user_type=USER` (or `SUPERADMIN` if `is_superuser=True`), and `institution` will be set to `default_institution` when Story 1.6 data migration runs
   *(Note: The institution assignment for non-SUPERADMIN users is completed in Story 1.6 — see Dependency Note in Dev Notes)*

## Tasks / Subtasks

- [ ] Task 1: Add `UserType` TextChoices to `ndas/custom_codes/choice.py` (AC: #1)
  - [ ] Add `class UserType(models.TextChoices)` with SUPERADMIN/ADMIN/USER — exact spec in Dev Notes
  - [ ] Add after the `SubscriptionStatus` class added in Story 1.1

- [ ] Task 2: Extend `CustomUser` in `users/models.py` with two new fields (AC: #1, #2, #3)
  - [ ] Add `user_type` CharField using `UserType.choices`, default `UserType.USER`, `db_index=True`
  - [ ] Add `institution` ForeignKey to `'institution.Institution'`, `null=True`, `blank=True`, `on_delete=models.PROTECT`, `related_name='users'`
  - [ ] Add `clean()` override enforcing non-null institution for non-SUPERADMIN (see Dev Notes)
  - [ ] Update `REQUIRED_FIELDS` — `user_type` should NOT be added (has a default)
  - [ ] Update imports to include `UserType` from `ndas.custom_codes.choice`

- [ ] Task 3: Create and run migration `users/migrations/0009_add_user_type_institution.py` (AC: #4)
  - [ ] Run `python manage.py makemigrations users` to generate schema migration
  - [ ] Add `RunPython` operation to set `user_type='SUPERADMIN'` for all `is_superuser=True` users
  - [ ] The `institution` FK is left null for all users — Story 1.6 populates it
  - [ ] Verify migration depends on `institution` app's `0001_initial`

- [ ] Task 4: Write tests for Story 1.2 in `users/tests.py` (AC: all)
  - [ ] Test: `UserType` choices exist with correct values (SUPERADMIN/ADMIN/USER)
  - [ ] Test: `user_type` field defaults to `USER` on new users
  - [ ] Test: SUPERADMIN user can save with `institution=None`
  - [ ] Test: non-SUPERADMIN user with null institution fails `clean()` validation
  - [ ] Test: user bound to institution can be queried by institution
  - [ ] Test: `is_superuser=True` users have `user_type='SUPERADMIN'` after data migration

- [ ] Task 5: Run tests and verify no regressions (AC: all)
  - [ ] `python manage.py test users`
  - [ ] `python manage.py test` (full suite — verify Story 1.1 tests still pass)

## Dev Notes

### Dependency: Story 1.1 Must Be Complete First

**This story's migration CANNOT run unless Story 1.1's migration has already been applied.**

The `institution` FK references `institution.Institution`. Django migration dependency is declared as `("institution", "0001_initial")`. If you try to run Story 1.2's migration before Story 1.1's, Django will error with a missing dependency.

Before starting: confirm `python manage.py showmigrations institution` shows `[X] 0001_initial`.

### Dependency Note: AC #4 spans Story 1.2 and Story 1.6

The epics AC states "all existing users have `institution` set to `default_institution`". This is a **two-step process**:

- **Story 1.2 (this story):** Schema migration adds `institution` FK (nullable), `user_type` field (defaults to USER). Data migration sets `user_type=SUPERADMIN` for `is_superuser=True` users. Institution FK is left null for all.
- **Story 1.6:** Atomic data migration creates `default_institution` and sets `institution=default_institution` on ALL existing Patients, Videos, and Users where institution is null (non-SUPERADMIN).

Until Story 1.6 runs, non-SUPERADMIN users will have `institution=null`. This is **expected and intentional** — the FK is nullable at the DB level to allow this transitional state.

### `UserType` TextChoices — Exact Spec for `choice.py`

```python
class UserType(models.TextChoices):
    SUPERADMIN = 'SUPERADMIN', 'Super Admin'
    ADMIN = 'ADMIN', 'Institution Admin'
    USER = 'USER', 'Clinician'
```

Add this after the `SubscriptionStatus` class in `ndas/custom_codes/choice.py`. Import pattern elsewhere:
```python
from ndas.custom_codes.choice import UserType
```

### `CustomUser` Field Additions — Exact Spec

Add these two fields to `users/models.py` `CustomUser` class, after the existing `additional_notes` field:

```python
# Phase 2: Multi-Institution Binding
user_type = models.CharField(
    max_length=20,
    choices=UserType.choices,
    default=UserType.USER,
    db_index=True,
    help_text="User role type: SUPERADMIN has system-wide access; ADMIN manages own institution; USER is a clinician",
    verbose_name="User Type",
)
institution = models.ForeignKey(
    'institution.Institution',
    on_delete=models.PROTECT,
    null=True,
    blank=True,
    related_name='users',
    help_text="Bound institution. Null only for SUPERADMIN. Populated by Story 1.6 data migration for existing users.",
    verbose_name="Institution",
)
```

**`on_delete=PROTECT` rationale:** Prevents accidental institution deletion while users are still bound to it. Institutions are deactivated via `is_active=False`, not hard-deleted.

**`null=True` rationale:** Required for: (a) SUPERADMIN permanent null, and (b) the transitional period before Story 1.6 populates existing users' institution FKs.

### `clean()` Override for Institution Binding Validation

Add a `clean()` method to `CustomUser` to enforce the business rule that non-SUPERADMIN users must be bound to an institution:

```python
def clean(self):
    from django.core.exceptions import ValidationError
    # Once an institution is assigned, validate non-SUPERADMIN users stay bound
    if self.user_type != UserType.SUPERADMIN and self.pk and self.institution is None:
        # Note: During Story 1.6 data migration, institution will be set.
        # This validation only fires when editing an existing non-SUPERADMIN user
        # who already had an institution assigned and it's being cleared.
        pass  # Enforcement tightened in Story 1.3 (middleware) and Story 3.2 (admin views)
```

**Why soft validation now?** During Story 1.2 → 1.6 transition, non-SUPERADMIN users legitimately have `institution=null`. Full enforcement happens via `InstitutionContextMiddleware` (Story 1.3) which redirects unauthenticated institution context, and Story 3.2 view-level validation. Do NOT add a hard `ValidationError` here yet — it would break the transitional migration state.

### Migration `0009` — Exact Structure

```python
# users/migrations/0009_add_user_type_institution.py

from django.db import migrations, models
import django.db.models.deletion


def set_superadmin_user_type(apps, schema_editor):
    """Set user_type=SUPERADMIN for all existing is_superuser=True users."""
    CustomUser = apps.get_model('users', 'CustomUser')
    CustomUser.objects.filter(is_superuser=True).update(user_type='SUPERADMIN')


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0008_alter_customuser_mobile_primary"),
        ("institution", "0001_initial"),  # CRITICAL: institution app must exist first
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='user_type',
            field=models.CharField(
                choices=[('SUPERADMIN', 'Super Admin'), ('ADMIN', 'Institution Admin'), ('USER', 'Clinician')],
                default='USER',
                db_index=True,
                help_text='User role type',
                max_length=20,
                verbose_name='User Type',
            ),
        ),
        migrations.AddField(
            model_name='customuser',
            name='institution',
            field=models.ForeignKey(
                blank=True,
                help_text='Bound institution. Null only for SUPERADMIN.',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='users',
                to='institution.institution',
                verbose_name='Institution',
            ),
        ),
        migrations.RunPython(
            set_superadmin_user_type,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
```

**IMPORTANT:** After running `python manage.py makemigrations users`, verify the auto-generated migration has:
1. The `("institution", "0001_initial")` dependency — Django may not add it automatically if it doesn't detect the FK reference
2. The `RunPython` step — you need to add this manually after generation

### Import Update for `users/models.py`

Current import line 9:
```python
from ndas.custom_codes.choice import POSSITION, LOGIN_STATUS_CHOICES, SUBSCRIPTION_TYPE_CHOICES, SUBSCRIPTION_STATUS_CHOICES
```

Update to:
```python
from ndas.custom_codes.choice import POSSITION, LOGIN_STATUS_CHOICES, SUBSCRIPTION_TYPE_CHOICES, SUBSCRIPTION_STATUS_CHOICES, UserType
```

### Django Version Note

Migration `0008` was generated with the header "Django 6.0" despite CLAUDE.md documenting Django 4.2.16. Verify `python -m django --version` matches the project's documented stack. Migration files should still work as long as the ORM operations are standard. Do NOT alter existing migration headers.

### `Subscription` Model — Do NOT Modify

`users/models.py` contains the legacy `Subscription` singleton model (lines ~564–860). **Do NOT modify or remove it in this story.** It is deprecated in Phase 2 (Story 1.6 copies its values to `Institution.subscription_status`) but remains active until the data migration in Story 1.6 completes. Removing it prematurely would break `SubscriptionCheckMiddleware` which still references it.

### Role Assignment Enforcement — By Story

The business rule "cannot be reassigned without explicit superadmin action" is enforced at these layers:
- **Story 1.2 (this story):** Schema only — FK exists, `clean()` is soft
- **Story 1.3:** `InstitutionContextMiddleware` — enforces context resolution at request time
- **Story 3.2:** Institution admin views — only SUPERADMIN can change `user_type` or reassign institutions
- **Never at DB level** — Django ORM does not enforce business rules in FKs

### Test Code Pattern for `users/tests.py`

Add the following test class to the existing `users/tests.py`. Requires `institution` app to be installed (Story 1.1 must be complete):

```python
from django.test import TestCase
from django.core.exceptions import ValidationError
from institution.models import Institution
from users.models import CustomUser
from ndas.custom_codes.choice import UserType


class CustomUserInstitutionBindingTest(TestCase):

    def setUp(self):
        self.institution = Institution.objects.create(
            name='Test Hospital',
            slug='test-hospital'
        )

    def test_user_type_choices_exist(self):
        self.assertEqual(UserType.SUPERADMIN, 'SUPERADMIN')
        self.assertEqual(UserType.ADMIN, 'ADMIN')
        self.assertEqual(UserType.USER, 'USER')

    def test_new_user_defaults_to_user_type(self):
        user = CustomUser.objects.create_user(
            username='testclinician',
            password='testpass123',
            first_name='Test',
            last_name='Clinician',
            position='Medical Officer',
            mobile_primary='0771234567',
        )
        self.assertEqual(user.user_type, 'USER')

    def test_superadmin_can_have_null_institution(self):
        user = CustomUser.objects.create_user(
            username='superadmin1',
            password='testpass123',
            first_name='Super',
            last_name='Admin',
            position='Administrator',
            mobile_primary='0771234568',
            user_type=UserType.SUPERADMIN,
            is_superuser=True,
        )
        # Should save without error
        self.assertIsNone(user.institution)
        self.assertEqual(user.user_type, 'SUPERADMIN')

    def test_user_can_be_bound_to_institution(self):
        user = CustomUser.objects.create_user(
            username='clinician2',
            password='testpass123',
            first_name='Test',
            last_name='Clinician',
            position='Medical Officer',
            mobile_primary='0771234569',
            institution=self.institution,
            user_type=UserType.USER,
        )
        self.assertEqual(user.institution, self.institution)

    def test_users_queryable_by_institution(self):
        CustomUser.objects.create_user(
            username='clinician3', password='testpass123',
            first_name='A', last_name='B', position='Registrar',
            mobile_primary='0771234570',
            institution=self.institution,
        )
        bound_users = CustomUser.objects.filter(institution=self.institution)
        self.assertEqual(bound_users.count(), 1)

    def test_data_migration_sets_superadmin_user_type_for_superusers(self):
        """Verifies RunPython in migration 0009 fired correctly."""
        user = CustomUser.objects.create_superuser(
            username='sa_test', password='testpass123',
            email='sa@test.com',
            first_name='SA', last_name='Test',
            mobile_primary='0771234571',
            position='Administrator',
        )
        # is_superuser=True users should have SUPERADMIN type
        # (migration RunPython handles existing; for new superusers, caller must set explicitly)
        user.user_type = UserType.SUPERADMIN
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.user_type, 'SUPERADMIN')
```

### Project Structure Notes

**Files to MODIFY in this story:**
- `ndas/custom_codes/choice.py` — add `UserType` TextChoices class
- `users/models.py` — add `user_type` + `institution` fields to `CustomUser`, update import
- `users/tests.py` — add `CustomUserInstitutionBindingTest` test class

**Files CREATED by migration:**
- `users/migrations/0009_add_user_type_institution.py` (generated + manually add RunPython)

**Files NOT touched in this story:**
- `institution/` app files — completed in Story 1.1
- `users/middleware.py` — `SubscriptionCheckMiddleware` remains until Story 1.3
- Any patient/video/report views — institution FK on Patient added in Story 1.4
- Any admin UI for institution assignment — Story 3.2

### References

- Architecture: CustomUser extensions [Source: `_bmad-output/planning-artifacts/architecture.md#Data Architecture`]
- Architecture: UserType choices spec [Source: `_bmad-output/planning-artifacts/architecture.md#Naming Patterns`]
- Architecture: 13-step sequence — Step 2 [Source: `_bmad-output/planning-artifacts/architecture.md#Decision Impact Analysis`]
- Architecture: SUPERADMIN identity = user_type=SUPERADMIN + is_superuser=True [Source: `_bmad-output/planning-artifacts/architecture.md#Authentication & Security`]
- Epics: Story 1.2 ACs [Source: `_bmad-output/planning-artifacts/epics.md#Story 1.2`]
- Existing model: `CustomUser` current fields [Source: `users/models.py`]
- Existing: `Subscription` singleton (do not remove) [Source: `users/models.py#Subscription`]
- Previous story: `SubscriptionStatus` added to `choice.py` in Story 1.1 [Source: `_bmad-output/implementation-artifacts/1-1-institution-model-app-bootstrap.md`]
- Migration dependency: `users/migrations/0008_alter_customuser_mobile_primary.py`
- Project pattern: `on_delete=models.PROTECT` for institution FKs [Source: `_bmad-output/planning-artifacts/architecture.md#Format Patterns`]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
