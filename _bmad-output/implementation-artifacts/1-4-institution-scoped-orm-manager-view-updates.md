# Story 1.4: Institution-Scoped ORM Manager & View Updates

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **clinician**,
I want all patient, video, assessment, and report queries to automatically filter to my institution,
So that cross-institution data is never returned regardless of the access path used.

## Acceptance Criteria

1. **Given** `InstitutionScopedManager` is defined in `institution/managers.py` with `for_institution(institution)` and `all_institutions()` methods
   **When** `Patient.objects.for_institution(request.institution)` is called
   **Then** only patients belonging to that institution are returned; zero patients from other institutions appear

2. **Given** `InstitutionScopedManager` is set as the `objects` manager on `Patient` and all other models with an `institution` FK
   **When** a clinician from Institution A accesses the patient list, patient detail, video list, or any assessment view
   **Then** no Institution B records appear in any response

3. **Given** a clinician from Institution A requests a patient detail using a `patient_id` that belongs to Institution B
   **When** the view executes `get_object_or_404(Patient.objects.for_institution(request.institution), id=pk)`
   **Then** a 404 response is returned — not a 403, not the Institution B patient record

4. **Given** all `patients/`, `video/`, `reports/`, and `problemlist/` views have been updated to call `.for_institution(request.institution)` on every Patient queryset
   **When** a SUPERADMIN calls `Patient.objects.all_institutions()` in an aggregate view
   **Then** records from all institutions are returned

## Tasks / Subtasks

- [ ] Task 1: Create `institution/managers.py` — InstitutionScopedManager (AC: #1, #4)
  - [ ] `for_institution(institution)`: if institution is None → return `get_queryset()` (Phase 1 safe); else → `filter(institution=institution)`
  - [ ] `all_institutions()`: return `get_queryset()` unfiltered (SUPERADMIN aggregate use only)
  - [ ] See exact code in Dev Notes

- [ ] Task 2: Add `institution` FK + `InstitutionScopedManager` to `patients/models.py` Patient (AC: #1, #2)
  - [ ] Add `institution` FK: `ForeignKey('institution.Institution', on_delete=PROTECT, null=True, blank=True, db_index=True, related_name='patients')`
  - [ ] Add `objects = InstitutionScopedManager()` below the FK field
  - [ ] Update imports in `patients/models.py`: add `InstitutionScopedManager`
  - [ ] See exact spec in Dev Notes

- [ ] Task 3: Create `patients/migrations/0008_add_institution_fk.py` (AC: #1, #2)
  - [ ] `python manage.py makemigrations patients`
  - [ ] Confirm migration depends on `("institution", "0001_initial")`
  - [ ] FK is `null=True` — no data default needed (Story 1.6 populates the data)

- [ ] Task 4: Update `patients/views.py` — Patient queryset changes (AC: #2, #3)
  - [ ] Change ALL `get_object_or_404(Patient, ...)` calls → use institution-scoped manager (15 occurrences — see Dev Notes for exact lines)
  - [ ] Change ALL `Patient.objects.filter(...)` / `Patient.objects.count()` / `Patient.objects.get(...)` → institution-scoped (see Dev Notes)
  - [ ] Dashboard aggregate counts for child models (GMAssessment, Video, etc.) → scope via `patient__in` (see Dev Notes)
  - [ ] Use `getattr(request, 'institution', None)` not `request.institution` directly — Phase 1 safe

- [ ] Task 5: Update `video/views.py` — Video queryset changes (AC: #2)
  - [ ] All `Video.objects.select_related(...)` → filter `patient__in=Patient.objects.for_institution(...)` (see Dev Notes)
  - [ ] Any `get_object_or_404(Patient, ...)` calls → institution-scoped

- [ ] Task 6: Update `problemlist/views.py` — Problem queryset changes (AC: #2)
  - [ ] `Patient.objects.all()` at line 493 → `Patient.objects.for_institution(...)` (see Dev Notes)
  - [ ] `Problem.objects...all()` at lines 471, 542 → filter via `patient__in=institution_patients`

- [ ] Task 7: Update `reports/views.py` — Report queryset changes (AC: #2)
  - [ ] Any Patient-level queries → scoped (see Dev Notes for what was found)

- [ ] Task 8: Write `institution/tests/test_isolation.py` — First isolation test pass (AC: #1, #2, #3)
  - [ ] Create two institutions with separate patients
  - [ ] Test: clinician from Institution A cannot see Institution B patients
  - [ ] Test: direct URL attack (`/patients/{institution_b_patient_id}/view/`) → 404
  - [ ] Test: `all_institutions()` returns all records (SUPERADMIN aggregate)
  - [ ] Full isolation test suite is Story 1.7 — this is a first pass

- [ ] Task 9: Run all tests (AC: all)
  - [ ] `python manage.py test institution`
  - [ ] `python manage.py test patients`
  - [ ] `python manage.py test` — full suite; no regressions

## Dev Notes

### Dependencies

- Story 1.1: `institution.models.Institution` must exist (Patient FK references it)
- Story 1.2: `CustomUser.institution` must exist (needed for manager context)
- Story 1.3: `InstitutionContextMiddleware` must be in place (sets `request.institution`)

**Note:** `request.institution` may be `None` during Stories 1.1–1.7 development while `MULTI_INSTITUTION_ENABLED=False`. All view code uses `getattr(request, 'institution', None)` as the safe getter. The `InstitutionScopedManager.for_institution(None)` returns all records → Phase 1 compatible.

### `institution/managers.py` — Complete Spec

```python
"""
InstitutionScopedManager: provides institution-filtered querysets for all
models with an institution FK. The single point of truth for data isolation.
"""
from django.db import models


class InstitutionScopedManager(models.Manager):
    """
    Custom manager that scopes querysets to a single institution.

    Usage:
        # In any institution-scoped view:
        patients = Patient.objects.for_institution(request.institution)

        # In SUPERADMIN aggregate views only:
        all_patients = Patient.objects.all_institutions()

    NEVER use .all() or inline .filter(institution=...) in institution-scoped views.
    """

    def for_institution(self, institution):
        """
        Return queryset filtered to the given institution.
        If institution is None (Phase 1 / transitional state), returns all records.
        """
        if institution is None:
            # Phase 1 safe: no institution context active → unfiltered (backward compatible)
            return self.get_queryset()
        return self.get_queryset().filter(institution=institution)

    def all_institutions(self):
        """
        Return unfiltered queryset — for SUPERADMIN aggregate use ONLY.
        Never call this from a regular institution-scoped view.
        """
        return self.get_queryset()
```

### `patients/models.py` — Patient Model Changes

Add `institution` FK and manager import. These two additions go in the `Patient` class. Find the class definition (line ~47) and add after the existing fields:

**Import addition** at the top of `patients/models.py`:
```python
from institution.managers import InstitutionScopedManager
```

**Fields to add to `Patient` class** (add after the last existing field, before class `Meta` or `def` methods):
```python
# Phase 2: Multi-institution support
institution = models.ForeignKey(
    'institution.Institution',
    on_delete=models.PROTECT,
    null=True,
    blank=True,
    db_index=True,
    related_name='patients',
    help_text="Institution this patient belongs to. Set by Story 1.6 data migration for existing patients.",
    verbose_name="Institution",
)
objects = InstitutionScopedManager()
```

**`on_delete=PROTECT` rationale**: An institution deletion would be catastrophic for patient data. PROTECT prevents this at the DB level.

**`null=True` rationale**: Required for transitional state — existing patients get `institution=default_institution` in Story 1.6. Until then, FK is null.

**Migration dependency** in the auto-generated `0008_add_institution_fk.py`:
```python
dependencies = [
    ("patients", "0007_alter_diagnosislist_abr_alter_diagnosislist_title_and_more"),
    ("institution", "0001_initial"),  # Must be explicit
]
```

### Standard View Pattern — The Three Transformations

Every institution-scoped view needs ONE of these three transformations:

**Transformation 1 — `get_object_or_404` (HIGHEST PRIORITY — prevents cross-institution access):**
```python
# OLD (insecure — returns patient from any institution):
patient = get_object_or_404(Patient, id=pk)
patient = get_object_or_404(Patient, pk=pid)

# NEW (institution-scoped — returns 404 for wrong institution):
patient = get_object_or_404(
    Patient.objects.for_institution(getattr(request, 'institution', None)),
    id=pk
)
patient = get_object_or_404(
    Patient.objects.for_institution(getattr(request, 'institution', None)),
    pk=pid
)
```

**Transformation 2 — Filter/Count/Annotate queries:**
```python
# OLD:
patients = Patient.objects.filter(status='active')
count = Patient.objects.count()

# NEW:
_inst = getattr(request, 'institution', None)
patients = Patient.objects.for_institution(_inst).filter(status='active')
count = Patient.objects.for_institution(_inst).count()
```

**Transformation 3 — Child model queries (no institution FK — scope via Patient):**
```python
# OLD:
gma_count = GMAssessment.objects.count()
videos = Video.objects.select_related('patient').filter(patient=some_patient)

# NEW (scope via patient__in):
_inst = getattr(request, 'institution', None)
_patients_qs = Patient.objects.for_institution(_inst)
gma_count = GMAssessment.objects.filter(patient__in=_patients_qs).count()
# For single-patient child queries, they're already scoped IF the patient was fetched with for_institution()
```

**NEVER write:**
```python
Patient.objects.all()                              # leaks cross-institution data
Patient.objects.filter(institution=request.institution)  # bypasses manager
```

### `patients/views.py` — Specific Changes Required

#### 1. Helper variable for institution (add once per view function, reuse)
```python
_inst = getattr(request, 'institution', None)
```

#### 2. Dashboard view (line ~76) — All aggregate counts
Approximately lines 103–160 need the following changes:

```python
# All these Patient.objects calls (lines 103-137):
# OLD → NEW pattern:
patients_total_count = Patient.objects.for_institution(_inst).count()
patients_discharged_count = Patient.objects.for_institution(_inst).filter(
    pt_status=PtStatus.DISCHARGED
).count()

# For child model aggregates, define institution_patients once:
_patients_qs = Patient.objects.for_institution(_inst)
all_gm_assessments_count = GMAssessment.objects.filter(patient__in=_patients_qs).count()
all_hine_assessments_count = HINEAssessment.objects.filter(patient__in=_patients_qs).count()
all_da_assessments_count = DevelopmentalAssessment.objects.filter(patient__in=_patients_qs).count()
all_cdic_records_count = CDICRecord.objects.filter(patient__in=_patients_qs).count()
attachments_count = Attachment.objects.filter(patient__in=_patients_qs).count()
videos_total_count = Video.objects.filter(patient__in=_patients_qs).count()

# Line 132-137 (annotate query):
patients_new_count = Patient.objects.for_institution(_inst).annotate(...).count()
Patients_new_list_10 = Patient.objects.for_institution(_inst).annotate(...).order_by(...)[:10]

# Line 149-153 (new videos):
new_videos_count = Video.objects.filter(patient__in=_patients_qs).annotate(...).count()
new_videos = Video.objects.filter(patient__in=_patients_qs).annotate(...)
```

#### 3. Patient detail view (line ~372) — `get_object_or_404`
```python
# Line 372:
selected_patient = get_object_or_404(
    Patient.objects.for_institution(getattr(request, 'institution', None)), id=pk
)
```

#### 4. All remaining `get_object_or_404(Patient, ...)` calls
Apply Transformation 1 to every occurrence (lines 509, 604, 628, 866, 1241, 1732, 1858, 2157, 2355, 2556, 2746, 2931, 3139, 3361, 3504 — approximately 15 occurrences).

#### 5. Patient search (lines ~714, 731, 748, 765, 804)
```python
# Lines 714, 731, 748 — Patient.objects.get() in search:
# OLD:
patient = Patient.objects.get(bht=search_text)
# NEW:
patient = Patient.objects.for_institution(_inst).get(bht=search_text)
# (DoesNotExist exception handling is already in place — no change needed to except blocks)

# Lines 765, 804 — Patient.objects.filter() list queries:
# OLD:
patients = Patient.objects.filter(Q(...) | Q(...))
# NEW:
patients = Patient.objects.for_institution(_inst).filter(Q(...) | Q(...))
```

#### 6. Line 325 — duplicate check
```python
# OLD:
if bht and Patient.objects.filter(bht=bht).exists():
# NEW:
if bht and Patient.objects.for_institution(_inst).filter(bht=bht).exists():
```

#### 7. Lines 376–430 (patient detail child objects)
These queries (`Video.objects.select_related(...)`, `Attachment.objects.select_related(...)`, `GMAssessment.objects.select_related(...)`, etc.) are ALREADY scoped because they use `filter(patient=selected_patient)` (or are inside a function call with a patient arg). Since `selected_patient` is fetched with `for_institution()` in step 3, these child queries are transitively institution-scoped. **No change needed** for these lines IF the parent `get_object_or_404` is updated.

### `video/views.py` — Specific Changes Required

Video objects do NOT have a direct institution FK — they're scoped via the Patient FK.

#### 1. Video list queries (lines ~249, 266, 271, 311, 330, 364, 366, 407)
```python
# Pattern: add patient__in=Patient.objects.for_institution(_inst) to filter
_inst = getattr(request, 'institution', None)
_patients_qs = Patient.objects.for_institution(_inst)

# OLD:
Video.objects.select_related("patient", "added_by", "last_edit_by").filter(patient=...)
# NEW (for all-patient video lists):
Video.objects.select_related("patient", "added_by", "last_edit_by").filter(
    patient__in=_patients_qs
)

# For videos attached to a specific patient fetched with for_institution(), no change needed
```

#### 2. Any `get_object_or_404(Patient, ...)` calls in video views
Apply Transformation 1.

### `problemlist/views.py` — Specific Changes Required

#### 1. Line 493 — Patient.objects.all() for problem export/list
```python
# OLD (line 493):
patients = Patient.objects.all().values('pk', 'baby_name', 'bht', 'mother_name')
# NEW:
_inst = getattr(request, 'institution', None)
patients = Patient.objects.for_institution(_inst).values('pk', 'baby_name', 'bht', 'mother_name')
```

#### 2. Lines 471, 542 — Problem.objects...all() for problem lists
```python
# OLD:
problems = Problem.objects.select_related('patient', 'added_by').all()
# NEW:
_inst = getattr(request, 'institution', None)
_patients_qs = Patient.objects.for_institution(_inst)
problems = Problem.objects.select_related('patient', 'added_by').filter(
    patient__in=_patients_qs
)
```

#### 3. Line 43 — Problem query by patient (already scoped via patient param)
```python
# Line 43: problems = Problem.objects.filter(patient=patient).annotate(...)
# This is ALREADY scoped IF the patient variable was fetched with for_institution()
# Check the calling function — if it uses get_object_or_404(Patient, ...) apply Transformation 1
```

### `reports/views.py` — Notes

No direct `Patient.objects.` calls were found in the grep scan. Reports views likely use helper functions in `reports/utils/`. Check if any helper function in `reports/utils/pdf_generator.py` or `reports/utils/excel_generator.py` queries Patient directly and apply `for_institution()` there as needed.

**Minimal reports view check:**
```bash
grep -n "Patient\.objects\.\|\.objects\.all\(\)\|\.objects\.filter\(" reports/views.py
grep -n "Patient\.objects\.\|\.objects\.all\(\)" reports/utils/pdf_generator.py
grep -n "Patient\.objects\.\|\.objects\.all\(\)" reports/utils/excel_generator.py
```

### `patients/models.py` Import Pattern

After adding `institution` FK, `patients/models.py` will import `InstitutionScopedManager`:

```python
from institution.managers import InstitutionScopedManager
```

This creates an import from `institution/` → `patients/` direction. This is intentional and consistent with the architecture:
```
institution/  ←  patients/  (patients depends on institution, not vice versa)
```

**Do NOT** import anything from `patients/` inside `institution/managers.py` (would create circular import).

### Test Code Pattern for `institution/tests/test_isolation.py`

```python
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from institution.models import Institution
from patients.models import Patient
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class InstitutionPatientIsolationTest(TestCase):
    """First-pass isolation tests. Story 1.7 extends this to full coverage."""

    def setUp(self):
        self.institution_a = Institution.objects.create(
            name='Hospital A', slug='hospital-a',
            subscription_status=SubscriptionStatus.ACTIVE,
        )
        self.institution_b = Institution.objects.create(
            name='Hospital B', slug='hospital-b',
            subscription_status=SubscriptionStatus.ACTIVE,
        )
        self.clinician_a = User.objects.create_user(
            username='clinician_a', password='testpass123',
            first_name='A', last_name='Clinician',
            position='Medical Officer', mobile_primary='0771234001',
            user_type=UserType.USER, institution=self.institution_a,
        )
        self.patient_a = Patient.objects.create(
            baby_name='Patient A', institution=self.institution_a,
        )
        self.patient_b = Patient.objects.create(
            baby_name='Patient B', institution=self.institution_b,
        )

    def test_for_institution_returns_only_institution_patients(self):
        """AC #1: for_institution() filters correctly."""
        patients = Patient.objects.for_institution(self.institution_a)
        self.assertIn(self.patient_a, patients)
        self.assertNotIn(self.patient_b, patients)

    def test_for_institution_none_returns_all(self):
        """for_institution(None) returns all — Phase 1 compatible."""
        patients = Patient.objects.for_institution(None)
        self.assertIn(self.patient_a, patients)
        self.assertIn(self.patient_b, patients)

    def test_all_institutions_returns_all(self):
        """AC #4: all_institutions() returns records from all institutions."""
        patients = Patient.objects.all_institutions()
        self.assertEqual(patients.count(), 2)

    def test_cross_institution_patient_detail_returns_404(self):
        """AC #3: Cross-institution URL attack returns 404."""
        self.client.force_login(self.clinician_a)
        # patient_b belongs to institution_b; clinician_a is in institution_a
        url = f'/patients/{self.patient_b.pk}/view/'
        response = self.client.get(url)
        # Should return 404, not 200 or 403
        self.assertEqual(response.status_code, 404)

    def test_patient_list_shows_only_own_institution(self):
        """AC #2: Patient list view returns only institution A patients for clinician A."""
        self.client.force_login(self.clinician_a)
        response = self.client.get('/')  # dashboard or patient list
        # patient_b should not appear
        if hasattr(response, 'context') and response.context:
            patients_in_context = response.context.get('Patients_new_list_10', [])
            patient_ids = [p.pk for p in patients_in_context]
            self.assertNotIn(self.patient_b.pk, patient_ids)
```

### Project Structure Notes

**Files to CREATE in this story:**
- `institution/managers.py`
- `institution/tests/test_isolation.py` (first-pass — Story 1.7 extends it)
- `patients/migrations/0008_add_institution_fk.py` (generated)

**Files to MODIFY in this story:**
- `patients/models.py` — add `institution` FK + `InstitutionScopedManager` + import
- `patients/views.py` — ~15+ queryset locations (see detailed list above)
- `video/views.py` — Video list query scoping via `patient__in`
- `problemlist/views.py` — lines 43, 471, 493, 542
- `reports/views.py` — check and update any Patient queries found

**Files NOT touched in this story:**
- `institution/middleware.py` — already done (Story 1.3)
- `patients/migrations/0001–0007` — do not modify existing migrations
- `video/models.py`, `problemlist/models.py` — these models have no institution FK (scoped through Patient)
- Assessment model files — scoped through Patient FK, no direct institution FK needed in this story
- `institution/managers.py` will be IMPORTED by `referral/models.py` in Story 4.1 (ReferralSent, ReferralReceived also use InstitutionScopedManager)

### References

- Architecture: InstitutionScopedManager canonical usage and anti-patterns [Source: `_bmad-output/planning-artifacts/architecture.md#Format Patterns`]
- Architecture: All enforcement guidelines [Source: `_bmad-output/planning-artifacts/architecture.md#Enforcement Guidelines`]
- Architecture: App dependency rules (institution/ ← patients/) [Source: `_bmad-output/planning-artifacts/architecture.md#Architectural Boundaries`]
- Architecture: 13-step sequence — Step 4 [Source: `_bmad-output/planning-artifacts/architecture.md#Decision Impact Analysis`]
- Epics: Story 1.4 ACs [Source: `_bmad-output/planning-artifacts/epics.md#Story 1.4`]
- Existing queryset patterns: `patients/views.py` lines 103–160 (dashboard), 372/509/604/628/866/1241/1732/1858/2157/2355/2556/2746/2931/3139/3361/3504 (get_object_or_404)
- Existing queryset patterns: `video/views.py` lines 249, 266, 271, 311, 330, 364, 366, 407
- Existing queryset patterns: `problemlist/views.py` lines 43, 471, 493, 542
- Latest patients migration: `0007_alter_diagnosislist_abr_alter_diagnosislist_title_and_more.py`

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
