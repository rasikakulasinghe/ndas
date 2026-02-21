# Story 1.2: Fix Birth Weight Validation Range Inconsistency

Status: done

## Story

As a clinician entering patient data,
I want the birth weight validation to consistently reject values below 300g,
so that entering a premature infant's weight of 250g produces a clear form error instead of a confusing 500 server error.

## Acceptance Criteria

1. Birth weight lower bound in `patients/views.py` changed from `200` to `300` — `birth_weight < 300` at line 320.
2. The error message in the view reads "Birth weight must be between 300g and 8000g".
3. The standalone `validate_birth_weight()` function in `ndas/custom_codes/validators.py` also updated: lower bound `200` → `300`, error message updated to "300g".
4. Entering 250g in the patient add form returns a user-friendly validation error message (no 500 error).
5. Entering 300g is accepted normally.
6. Entering 200g is rejected with a clear error message.
7. `python manage.py test patients` — no new failures introduced.

## Tasks / Subtasks

- [x] Task 1: Fix view-level validation in `patient_add` (AC: #1, #2, #4, #5, #6)
  - [x] `patients/views.py:320` — change `birth_weight < 200` → `birth_weight < 300`
  - [x] `patients/views.py:322` — change error message from `"Birth weight must be between 200g and 8000g"` → `"Birth weight must be between 300g and 8000g"`
- [x] Task 2: Fix standalone `validate_birth_weight` function (AC: #3)
  - [x] `ndas/custom_codes/validators.py:386` — change `if value < 200` → `if value < 300`
  - [x] `ndas/custom_codes/validators.py:387` — change error message from `"Birth weight must be between 200g and 8000g"` → `"Birth weight must be between 300g and 8000g"`
- [x] Task 3: Write test (AC: #4, #5, #6)
  - [x] Add `BirthWeightViewValidationTest` class to `patients/tests/test_views.py`
  - [x] Test: POST to `add-patient` with `birth_weight=250` → form error, no redirect
  - [x] Test: POST to `add-patient` with `birth_weight=200` → form error
  - [x] Test: POST to `add-patient` with `birth_weight=300` → accepted (redirects to view-patient)
  - [x] `python manage.py test patients` — all new tests pass

## Dev Notes

### Current State — `patients/views.py:318–323`

```python
# Validate birth weight
birth_weight = cleaned_data.get("birth_weight")
if birth_weight and (birth_weight < 200 or birth_weight > 8000):   # ← WRONG: 200 should be 300
    data_form.add_error(
        "birth_weight", "Birth weight must be between 200g and 8000g"  # ← WRONG message
    )
```

### Required State After Fix — `patients/views.py:318–323`

```python
# Validate birth weight
birth_weight = cleaned_data.get("birth_weight")
if birth_weight and (birth_weight < 300 or birth_weight > 8000):   # ← FIXED: 300g minimum
    data_form.add_error(
        "birth_weight", "Birth weight must be between 300g and 8000g"  # ← FIXED message
    )
```

### Current State — `ndas/custom_codes/validators.py:385–387`

```python
def validate_birth_weight(value):
    if value < 200 or value > 8000:                                   # ← WRONG: 200 should be 300
        return False, (f"Birth weight must be between 200g and 8000g")  # ← WRONG message
```

### Required State After Fix — `ndas/custom_codes/validators.py:385–387`

```python
def validate_birth_weight(value):
    if value < 300 or value > 8000:                                   # ← FIXED: 300g minimum
        return False, (f"Birth weight must be between 300g and 8000g")  # ← FIXED message
```

### IMPORTANT: `validate_birth_weight` Is a Non-Functional Django Validator

`validate_birth_weight` returns a `(bool, str)` tuple instead of raising `ValidationError`. Django field validators work by raising `ValidationError` on invalid input; a return value is ignored. This means:

- The model field `validators=[validate_birth_weight]` on `Patient.birth_weight` is **currently a no-op** — it never enforces anything at the Django level.
- The view-level check (`patient_add`) is the **only actual enforcement** path.
- `patient_edit` relies entirely on the (broken) model validator and therefore accepts ANY birth weight value currently.

**Do NOT fix the tuple-return bug in this story** — that is a code quality defect covered by Epic 4 (Story 4.x). Only update the `200` → `300` threshold in the existing function.

This story's Task 2 updates the threshold value only, so when the validator IS eventually fixed to raise `ValidationError`, it will enforce the correct 300g boundary.

### `patient_edit` Is Out of Scope

`patient_edit` (~line 620) does not have an explicit birth weight validation block — it relies on `data_form_modified.is_valid()`. Because `validate_birth_weight` is currently broken (tuple return), edit currently accepts any birth weight. This broader issue is not part of BUG-02's scope. Do not add validation to `patient_edit` in this story.

### `test_validators.py` ImportError — Do NOT Touch

`patients/tests/test_validators.py` imports `validate_birth_weight_for_gestational_age` and `BIRTH_WEIGHT_RANGES_BY_POG`, which do **not** exist in `validators.py`. This is a pre-existing failure from a planned but unimplemented feature. The ImportError was present before this story and is unrelated to BUG-02. **Do not add these functions** — that is out of scope.

### Writing the Test

For the test, submitting to `patient_add` via POST requires:
- A logged-in user (`is_staff=True`)
- All required fields (see list below)
- `birth_weight=250` to test rejection, `birth_weight=300` to test acceptance

The `patient_add` URL name is `add-patient` — confirm with:
```bash
grep -n "patient_add\|add-patient" patients/urls.py
```

Required Patient form fields for a valid POST (from Story 1.1 learnings):
```python
{
    'bht': 'BHT-TEST-001',
    'baby_name': 'Test Baby',
    'mother_name': 'Test Mother',
    'dob_tob': '2025-01-01 12:00:00',
    'gender': 'Male',   # Must be 'Male' or 'Female', NOT 'M'/'F'
    'pog_wks': 38,
    'pog_days': 0,
    'birth_weight': 300,  # Set this to 250/200/300 in different test cases
    'ofc': 33,
    'mo_delivery': 'Normal vaginal delivery (NVD)',  # Full string, not abbreviation
    'tp_mobile': '0711234500',
}
```

Use `@override_settings(STORAGES={"default": {...}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})` on the test class to bypass whitenoise staticfiles manifest errors.

The `patient_add` view uses a dead `if not request.user.is_authenticated:` check (Story 2.5 will remove it) but has NO `@ratelimit` decorator and no `@require_http_methods` — so the test can POST without any special setup beyond login.

### URL Confirmation

```
patients/urls.py:XX — path("patient/add/", views.patient_add, name='add-patient')
```
Confirm exact URL with grep before writing tests.

### No Migration Required

Two one-line changes in two files (`views.py` and `validators.py`). No model changes, no new imports, no migrations.

### CLAUDE.md Reference

> **Validation Ranges:**
> - Birth weight: 300g-8000g (basic), POG-specific (enhanced)

This is the authoritative source. The fix aligns both the view and the standalone validator with this documented range.

### Model Field Help Text Note

`Patient.birth_weight` has `help_text=_("Weight of the baby at birth in grams (300-8000g)")` — this already correctly says 300g and does not need to change.

### Project Structure Notes

- `patients/views.py:320` — one-line change in `patient_add`
- `ndas/custom_codes/validators.py:386` — one-line change in `validate_birth_weight`
- `patients/tests/test_views.py` — new test class added
- No migrations, no URL changes, no template changes

### References

- [Source: _bmad-output/planning-artifacts/epic-1-critical-bugs.md#Story-1.2]
- [Source: docs/code-audit-adversarial-review.md#BUG-02]
- [Source: patients/views.py:284–370 — patient_add view with birth weight validation at line 320]
- [Source: ndas/custom_codes/validators.py:385–387 — validate_birth_weight function]
- [Source: patients/models.py:189–193 — birth_weight field with validators and help_text]
- [Source: CLAUDE.md#Validation Ranges — "Birth weight: 300g-8000g (basic)"]
- [Source: _bmad-output/implementation-artifacts/1-1-fix-method-reference-bug-in-patient-view.md — test infrastructure patterns]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Django 4.2 `assertFormError` API: requires form object (not string context key). Use `response.context['form']` instead of old `(response, 'form_name', ...)` signature.
- `PatientForm` defines APGAR fields as required `ChoiceField` — `apgar_1`, `apgar_5`, `apgar_10` must be included in test POST data for form to be valid.
- Context key is `'form'` (not `'data_form'`) in `patient_add` template render.

### Completion Notes List

- Task 1 complete: `patients/views.py` line 320 changed `birth_weight < 200` → `birth_weight < 300`; line 322 error message updated to "300g". AC #1 and #2 satisfied.
- Task 2 complete: `ndas/custom_codes/validators.py` line 386 changed `value < 200` → `value < 300`; line 387 message updated to "300g". AC #3 satisfied. Note: validator still returns tuple (not raise ValidationError) — that is Epic 4 scope; only threshold updated per story scope.
- Task 3 complete: `BirthWeightViewValidationTest` class added to `patients/tests/test_views.py` with 3 tests (250g rejected, 200g rejected, 300g accepted). All pass. AC #4, #5, #6 satisfied.
- Full suite run: 3 new tests pass; no new failures introduced. Pre-existing failures (test_validators ImportError, DashboardTestCase staticfiles) unchanged and pre-date this story.

### File List

patients/views.py
ndas/custom_codes/validators.py
patients/tests/test_views.py

## Change Log

- 2026-02-20: Implemented Story 1.2 — changed birth weight lower bound from 200g to 300g in `patients/views.py` (view-level validation) and `ndas/custom_codes/validators.py` (standalone validator); added `BirthWeightViewValidationTest` with 3 passing tests covering 250g rejection, 200g rejection, and 300g acceptance.
- 2026-02-20: Code review fix — `validate_birth_weight()` was returning `(False, msg)` tuple instead of raising `ValidationError`. Fixed to `raise ValidationError(...)`. Model-level validation is now fully functional for all write paths.
