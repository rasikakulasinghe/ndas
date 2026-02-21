# Story 3.4: Eliminate N+1 Query Properties in Patient Manager List

Status: done

## Story

As a clinical user browsing the patient list,
I want the patient manager page to load quickly regardless of how many patients are shown,
so that per-patient status badges (bookmarked, discharged, screening result) do not generate one database query per patient per badge.

## Acceptance Criteria

1. `getPatientList()` in `ndas/custom_codes/custom_methods.py` adds 5 `Exists()` annotations to the base queryset before the filter branches, so all returned querysets automatically include them.
2. The 5 annotations are: `has_videos_ann`, `is_discharged_ann`, `is_bookmarked_ann`, `is_gma_abnormal_ann`, `is_hine_abnormal_ann`.
3. `templates/patients/manager.html` updated to use the annotated fields instead of the 4 `@property` calls (`isBookmarked`, `isNewPatient`, `isDischarged`, `isScreeningPositive`).
4. `@property` methods on the `Patient` model remain **unchanged** — they are still needed for single-object views (patient detail, edit, etc.).
5. Patient list page renders correctly with the same status badges as before.
6. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Update imports in `getPatientList()` (AC: #1)
  - [x] Changed local import from `from patients.models import Patient` to `from patients.models import Patient, CDICRecord, Bookmark, GMAssessment, HINEAssessment`. AC #1 satisfied.
- [x] Task 2: Add 5 annotations to `getPatientList()` base queryset (AC: #1, #2)
  - [x] Added `.annotate(has_videos_ann, is_discharged_ann, is_bookmarked_ann, is_gma_abnormal_ann, is_hine_abnormal_ann)` block to `var_ptl` before filter branches.
  - [x] Note: `is_diagnosis_normal` in story notes is a `@property`, not a DB field — used `diagnosis_conclusion='ABNORMAL'` to match existing filter logic.
  - [x] Removed `has_videos` variable; `PtStatus.NEW` now uses `.filter(has_videos_ann=False)`.
  - [x] `PtStatus.DX_NORMAL` branch updated to use `.filter(has_videos_ann=True)`. AC #1 and #2 satisfied.
- [x] Task 3: Update `templates/patients/manager.html` (AC: #3)
  - [x] Lines 260, 285: `isBookmarked` → `is_bookmarked_ann` (2 occurrences).
  - [x] Lines 264, 289: `isNewPatient` → `not has_videos_ann` (2 occurrences).
  - [x] Lines 268, 293: `isDischarged` → `is_discharged_ann` (2 occurrences).
  - [x] Lines 309, 348: `isScreeningPositive` → `is_gma_abnormal_ann or is_hine_abnormal_ann` (2 occurrences). AC #3 satisfied.
- [x] Task 4: Verify (AC: #4, #5, #6)
  - [x] `@property` methods on `Patient` model confirmed untouched. AC #4 satisfied.
  - [x] System check clean. 6 regression tests pass. AC #5 and #6 satisfied.

## Dev Notes

### Current State — `ndas/custom_codes/custom_methods.py:529–597`

```python
def getPatientList(pts_type):
    from patients.models import Patient       # ← only Patient imported

    var_ptl = Patient.objects.select_related(
        'added_by', 'last_edit_by'
    ).prefetch_related(
        'indecation_for_gma', 'videos', 'gm_assessments',
        'hine_assessments', 'developmental_assessments', 'cdic_records'
    )

    from video.models import Video
    has_videos = Video.objects.filter(patient=OuterRef('pk'))   # ← local variable

    if pts_type == PtStatus.ALL:
        return var_ptl
    elif pts_type == PtStatus.NEW:
        return var_ptl.annotate(has_videos=Exists(has_videos)).filter(has_videos=False)  # ← annotates locally
    ...
    elif pts_type == PtStatus.DX_NORMAL:
        return var_ptl.exclude(...).annotate(has_videos=Exists(has_videos)).filter(has_videos=True).distinct()
    ...
```

### Required State After Fix — `getPatientList()` Only Changed Section

```python
def getPatientList(pts_type):
    # CHANGED: import all needed models
    from patients.models import Patient, CDICRecord, Bookmark, GMAssessment, HINEAssessment

    var_ptl = Patient.objects.select_related(
        'added_by', 'last_edit_by'
    ).prefetch_related(
        'indecation_for_gma', 'videos', 'gm_assessments',
        'hine_assessments', 'developmental_assessments', 'cdic_records'
    )

    from video.models import Video

    # NEW: Add all N+1 annotations to base queryset before filter branches
    # These are available on every Patient object returned by this function
    var_ptl = var_ptl.annotate(
        has_videos_ann=Exists(Video.objects.filter(patient=OuterRef('pk'))),
        is_discharged_ann=Exists(CDICRecord.objects.filter(patient=OuterRef('pk'), is_discharged=True)),
        is_bookmarked_ann=Exists(Bookmark.objects.filter(bookmark_type='Patient', object_id=OuterRef('pk'))),
        is_gma_abnormal_ann=Exists(GMAssessment.objects.filter(patient=OuterRef('pk'), is_diagnosis_normal=False)),
        is_hine_abnormal_ann=Exists(HINEAssessment.objects.filter(patient=OuterRef('pk'), score__lt=73)),
    )

    if pts_type == PtStatus.ALL:
        return var_ptl
    elif pts_type == PtStatus.NEW:
        # CHANGED: uses has_videos_ann annotation (already on var_ptl)
        return var_ptl.filter(has_videos_ann=False)
    elif pts_type == PtStatus.DISCHARGED:
        return var_ptl.filter(cdic_records__is_discharged=True).distinct()
    elif pts_type == PtStatus.DIAGNOSED:
        return var_ptl.filter(...).distinct()
    elif pts_type == PtStatus.DX_NORMAL:
        # CHANGED: uses has_videos_ann annotation (already on var_ptl)
        return var_ptl.exclude(...).filter(has_videos_ann=True).distinct()
    ...
```

### `Exists` and `OuterRef` Are Already Imported

```python
# ndas/custom_codes/custom_methods.py:3 (EXISTING — do NOT change)
from django.db.models import Count, Q, Exists, OuterRef
```

`Exists` and `OuterRef` are already available. Do NOT add duplicate imports.

### Template Changes — `templates/patients/manager.html`

**Lines 260 and 285 (both identical, desktop + mobile):**
```django
{# BEFORE #}
{% if Patient.isBookmarked %}

{# AFTER #}
{% if Patient.is_bookmarked_ann %}
```

**Lines 264 and 289 (both identical):**
```django
{# BEFORE #}
{% elif Patient.isNewPatient %}

{# AFTER #}
{% elif not Patient.has_videos_ann %}
```

**Lines 268 and 293 (both identical):**
```django
{# BEFORE #}
{% elif Patient.isDischarged %}

{# AFTER #}
{% elif Patient.is_discharged_ann %}
```

**Lines 309 and 348 (both identical):**
```django
{# BEFORE #}
{% if Patient.isScreeningPositive %}

{# AFTER #}
{% if Patient.is_gma_abnormal_ann or Patient.is_hine_abnormal_ann %}
```

### Why `@property` Methods Must Stay Unchanged

The `@property` methods on `Patient` (`isDischarged`, `isBookmarked`, `isScreeningPositive`, `isNewPatient`) are used in **single-object contexts** outside the list view:
- `patient_view` — renders `templates/patients/view.html` with a single patient object
- Direct Python code that instantiates a Patient and checks `patient.isDischarged`
- Admin views, tests, shell usage

These single-object contexts do NOT use `getPatientList()` and therefore do NOT have the annotations. Removing or changing the `@property` methods would break them. Leave all `@property` definitions at `patients/models.py:363–484` exactly as-is.

### Behavioral Note: `isScreeningPositive` Simplification

The original `isScreeningPositive` property checks only the **latest** GMA/HINE record. The annotation-based approach (`is_gma_abnormal_ann`, `is_hine_abnormal_ann`) checks if **any** GMA/HINE is abnormal.

This is a slight behavioral change:
- If a patient had an ABNORMAL GMA, then a NORMAL GMA later, the property returns False (latest is normal)
- The annotation returns True (any is abnormal)

However, note that `getPatientList(PtStatus.DIAGNOSED)` already uses `filter(gmassessment__diagnosis_conclusion='ABNORMAL')` which checks ANY abnormal, not just the latest. The annotation approach is consistent with the existing list filter logic. Document this in the commit message.

### Behavioral Note: `isDischarged` Simplification

The original `isDischarged` property checks the **latest** CDICRecord's `is_discharged` status. A patient with `is_discharged=True` followed by a new `is_discharged=False` (re-admission) would return `False` from the property.

`is_discharged_ann = Exists(CDICRecord.objects.filter(patient=OuterRef('pk'), is_discharged=True))` returns `True` if ANY CDICRecord has `is_discharged=True`. This means a re-admitted patient would still show "DISCHARGED".

This is consistent with `getPatientList(PtStatus.DISCHARGED)` which uses `filter(cdic_records__is_discharged=True)`. Leave as-is — fixing the precise "latest record" logic with a Subquery is more complex and can be a follow-up improvement.

### No New Imports Needed Anywhere

- `Exists`, `OuterRef` — already at `custom_methods.py:3`
- All model classes added to the local import inside `getPatientList()`
- No changes to `patients/views.py` imports (the function signature is unchanged)

### No Migration Required

Changes only to a utility function and a template. No model changes.

### Project Structure Notes

- `ndas/custom_codes/custom_methods.py` — `getPatientList()` function body only (lines ~529–597)
- `templates/patients/manager.html` — 8 template tag changes (4 properties × 2 occurrences each)
- `patients/models.py` — **no changes**
- `patients/views.py` — **no changes**

### References

- [Source: _bmad-output/planning-artifacts/epic-3-performance.md#Story-3.4]
- [Source: docs/code-audit-adversarial-review.md#PERF-04]
- [Source: ndas/custom_codes/custom_methods.py:529–598 — getPatientList() function]
- [Source: ndas/custom_codes/custom_methods.py:3 — existing Exists/OuterRef imports]
- [Source: patients/models.py:363–484 — @property methods (isDischarged, isScreeningPositive, isBookmarked, isNewPatient)]
- [Source: templates/patients/manager.html:255–360 — template loop with property accesses]
- [Source: CLAUDE.md#View Pattern — "use select_related()/prefetch_related() for related objects"]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1 complete: Updated `getPatientList()` local import to include `CDICRecord, Bookmark, GMAssessment, HINEAssessment`. AC #1 satisfied.
- Task 2 complete: Added 5 `Exists()` annotations to base queryset. Note: story notes used `is_diagnosis_normal=False` (a `@property`, not a DB field) — corrected to `diagnosis_conclusion='ABNORMAL'` matching existing filter logic. `has_videos` variable removed; `PtStatus.NEW` and `PtStatus.DX_NORMAL` branches updated. AC #1 and #2 satisfied.
- Task 3 complete: All 8 template property references replaced with annotation names in `manager.html`. AC #3 satisfied.
- Task 4 complete: `@property` methods in `patients/models.py` confirmed untouched. System check clean. 6 regression tests pass. AC #4–6 satisfied.

### File List

ndas/custom_codes/custom_methods.py
templates/patients/manager.html

## Change Log

- 2026-02-20: Implemented Story 3.4 — added 5 `Exists()` annotations (`has_videos_ann`, `is_discharged_ann`, `is_bookmarked_ann`, `is_gma_abnormal_ann`, `is_hine_abnormal_ann`) to `getPatientList()` base queryset in `custom_methods.py`. Updated `manager.html` to use these annotations instead of N+1-generating `@property` method calls. `@property` methods on Patient model unchanged.
