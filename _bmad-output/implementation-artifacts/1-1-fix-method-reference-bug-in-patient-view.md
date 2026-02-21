# Story 1.1: Fix Method Reference Bug in Patient View

Status: done

## Story

As a clinician,
I want the patient detail page to correctly retrieve the last GMA assessment object,
so that any template or future code using `gm_last_assessment` renders real assessment data, not a method string.

## Acceptance Criteria

1. `var_gma.last` at `patients/views.py:399` is changed to `var_gma.last()` so it stores the assessment object (or `None`), not a bound method reference.
2. Developer confirms whether `.last()` (oldest, since queryset is ordered `-id`) or `.first()` (most recent) is clinically correct — documents choice in commit message.
3. No other `.last` or `.first` without parentheses exist anywhere in `patients/views.py`.
4. `gm_last_assessment` in context is `None` (not a `<bound method>` string) when the patient has no GMA assessments.
5. Dev server starts without error after the change.

## Tasks / Subtasks

- [x] Task 1: Fix the method reference (AC: #1, #2)
  - [x] Open `patients/views.py`, go to line 399
  - [x] Change `gm_last_assessment = var_gma.last` → `gm_last_assessment = var_gma.first()`
  - [x] **Verify ordering intent:** `var_gma` is ordered by `-id` (descending). On this queryset:
    - `.first()` → most recent assessment (highest ID) ← clinically correct for "latest"
    - `.last()` → oldest assessment (lowest ID)
  - [x] Used `.first()` — "last assessment" means "most recent" (highest ID on -id ordered queryset)
- [x] Task 2: Scan for the same bug pattern (AC: #3)
  - [x] Ran grep for `\.last[^_(e]` and `\.first[^_(e]` — no other occurrences in patients/views.py
- [x] Task 3: Write test (AC: #4)
  - [x] Added `PatientViewContextTest` class in `patients/tests/test_views.py`
  - [x] Test: `test_gm_last_assessment_is_not_callable_when_no_assessments` — patient with no GMA → `None`, not callable
  - [x] RED phase confirmed: test failed with `AssertionError: True is not false : gm_last_assessment must not be callable. Got: <class 'method'>`
  - [x] GREEN phase confirmed: test passes after fix

## Dev Notes

### Exact Location

```
File: patients/views.py
Function: patient_view (line 380)
Bug line: 399
```

```python
# CURRENT (BUG) — stores bound method, not result
gm_last_assessment = var_gma.last        # line 399

# CORRECT — calls the method
gm_last_assessment = var_gma.last()      # or .first() — see ordering note below
```

### Critical: Queryset Ordering Impacts `.last()` vs `.first()`

```python
# Line 396 — queryset is ordered DESCENDING by id
var_gma = GMAssessment.objects.select_related(...).filter(patient=selected_patient).order_by("-id")

# On a descending queryset:
# .first()  → highest ID  → most recently created assessment
# .last()   → lowest ID   → oldest assessment
```

**Clinically, "last assessment" almost certainly means most recent.** If so, the correct fix is:
```python
gm_last_assessment = var_gma.first()   # most recent on -id ordered queryset
```
However, if the variable is meant to represent the first-ever (baseline) assessment, `.last()` is correct. Check with Rasika if uncertain.

### Current Template Usage

`gm_last_assessment` is passed to `templates/patients/view.html` in context (line 461) but the template does **not currently use it** (confirmed by grep). The bug has no visible symptom in the UI today, but must be fixed before the template is extended to display this data.

### No Migration Required

This is a pure Python change. No model changes, no migrations.

### Django `.last()` Behaviour Reference

- `QuerySet.last()` — returns the last object matching the queryset, using the current ordering. Returns `None` if no records match. Never raises an exception.
- `QuerySet.last` (no parens) — returns the **bound method object** itself. When rendered in a template, produces `<bound method QuerySet.last of <QuerySet [...]>>`.
- [Source: Django 4.2 docs — QuerySet.last()](https://docs.djangoproject.com/en/4.2/ref/models/querysets/#last)

### Project Structure Notes

- File to edit: `patients/views.py` (line 399) — single line change
- Template: `templates/patients/view.html` — no changes needed
- No imports needed — `QuerySet.last()` is a built-in Django method

### Testing Approach

```python
# patients/tests/test_views.py (or existing test file)
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from patients.models import Patient, GMAssessment

class PatientViewContextTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(username='testuser', password='pass')
        self.client.force_login(self.user)
        self.patient = Patient.objects.create(baby_name='Test Baby', ...)

    def test_gm_last_assessment_is_not_callable(self):
        """gm_last_assessment must be an object or None, never a method"""
        response = self.client.get(f'/patient/view/{self.patient.id}/')
        self.assertEqual(response.status_code, 200)
        gm_last = response.context['gm_last_assessment']
        self.assertNotCallable(gm_last)   # must not be a bound method

    def test_gm_last_assessment_none_when_no_assessments(self):
        """Patient with no GMA assessments → gm_last_assessment is None"""
        response = self.client.get(f'/patient/view/{self.patient.id}/')
        self.assertIsNone(response.context['gm_last_assessment'])
```

Use `assertFalse(callable(response.context['gm_last_assessment']))` if `assertNotCallable` is unavailable.

**Rate-limited view note:** `patient_view` uses `@require_GET` but no `@ratelimit`. No need to mock ratelimit for this test.

### References

- [Source: docs/code-audit-adversarial-review.md#BUG-01]
- [Source: patients/views.py:380–480 — patient_view function]
- [Source: _bmad-output/project-context.md#Framework-Specific Rules]
- [Source: CLAUDE.md#View Pattern]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- RED phase: `AssertionError: True is not false : gm_last_assessment must not be callable. Got: <class 'method'>` — confirmed bug exists
- GREEN phase: `Ran 1 test in 0.629s OK` — fix confirmed
- Pre-existing test failures (unrelated): `test_validators` ImportError for non-existent `validate_birth_weight_for_gestational_age`; `DashboardTestCase` staticfiles manifest error (whitenoise requires collectstatic in non-test settings)

### Completion Notes List

- Used `.first()` not `.last()`: queryset is ordered `-id` (descending), so `.first()` = highest ID = most recently created assessment. Clinically "last assessment" = most recent.
- Also fixed pre-existing test infrastructure issues in `patients/tests/test_views.py`: corrected `Video` import (was in `patients.models`, actually in `video.models`), corrected invalid Patient field values (`gender='Male'` not `'M'`, full delivery strings, added required `ofc`/`tp_mobile` fields, removed non-existent `dx_conclution` field).
- Added `@override_settings(STORAGES={...})` to `PatientViewContextTest` to bypass whitenoise staticfiles manifest requirement in tests.

### File List

- `patients/views.py` — line 399: `var_gma.last` → `var_gma.first()`
- `patients/tests/test_views.py` — fixed pre-existing import/field errors; added `PatientViewContextTest` class
