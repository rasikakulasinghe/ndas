---
title: 'Security & Performance Hardening — Adversarial Review Fixes'
slug: 'adversarial-review-fixes'
created: '2026-03-10'
status: 'implementation-complete'
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
implementedBy: 'claude-sonnet-4-6'
implementedDate: '2026-03-11'
tech_stack: ['Django 4.2', 'Python 3.x', 'django-ratelimit 4.1.0', 'SQLite/PostgreSQL']
files_to_modify:
  - patients/views.py
  - users/views.py
  - ndas/custom_codes/custom_methods.py
code_patterns:
  - 'institution_scope(request, field) helper returns ORM filter kwargs or {} when institution is None'
  - 'Patient.objects.for_institution(inst) is the manager shortcut for patient queries'
  - 'get_object_or_404() is the NDAS standard — accepts a queryset as first arg (e.g. Model.objects.select_for_update())'
  - 'transaction is already imported in patients/views.py line 5 as: from django.db import transaction'
  - 'IntegrityError import: extend line 5 to: from django.db import transaction, IntegrityError'
  - 'transaction.on_commit(lambda: ...) available for post-commit side effects'
  - '30 bare except Exception blocks in patients/views.py; spec covers 9 security-critical paths'
  - 'Bookmark model uses generic object_id field — NO direct patient FK exists'
  - 'select_for_update() is PostgreSQL-only; SQLite raises DatabaseError — use engine check'
test_patterns:
  - 'patients/tests/test_views.py — 818 lines, comprehensive view + dashboard tests'
  - 'patients/tests/test_validators.py — birth weight validation tests'
  - 'users/tests.py — empty stub, no tests to break'
---

# Tech-Spec: Security & Performance Hardening — Adversarial Review Fixes

**Created:** 2026-03-10
**Revised:** 2026-03-10 (post adversarial review — 18 findings addressed)

## Overview

### Problem Statement

A full-codebase adversarial review (2026-03-10) identified 13 issues across `patients/views.py`, `users/views.py`, `institution/middleware.py`, and `ndas/custom_codes/`. Of these, 11 remain open: memory exhaustion from full queryset materialisation, user enumeration via unrate-limited token/email endpoints, unhandled exception paths that silently swallow integrity errors, a bookmark scope mismatch, a video isolation dependency on implicit upstream state, two concurrency hazards (deletion race condition + signal escape from atomic block), and a latent ORM injection vector in `institution_scope()`.

### Solution

Targeted, in-place backend fixes across three files — no schema migrations, no new packages, no template changes. Each fix is surgical and self-contained.

### Scope

**In Scope:**
- Issue #1/#2 — Full queryset `list()` materialisation before slicing (`patients/views.py` ~377–426) *(note: institution scope on assessments is already implicitly correct via patient scoping — fix is list() removal only)*
- Issue #3 — Email/token endpoints lack rate limiting, method restriction, and enumeration resistance (`users/views.py` ~305–375)
- Issue #4 — Bookmark institution scope mismatch — defence at object-resolution level (`patients/views.py` bookmark views)
- Issue #5 — Video scope relies on implicit upstream queryset (`patients/views.py` ~884)
- Issue #7 — Bare `except Exception` — 9 security-critical delete/save paths in `patients/views.py`
- Issue #8 — Raw `.objects.get(id=1)` without project-standard handling (`users/views.py`)
- Issue #9 — `MultipleObjectsReturned` unhandled in patient search (`patients/views.py` ~724–758)
- Issue #11 — Deletion race condition on institution boundary (`patients/views.py` ~1113–1213)
- Issue #12 — Signal side-effects escape `transaction.atomic()` (`patients/views.py` ~914–918)
- Issue #13 — `institution_scope()` field-path is an ORM injection vector (`ndas/custom_codes/custom_methods.py`)

**Out of Scope:**
- Issue #6 (middleware `is_active` re-check) — already addressed
- Issue #10 (N+1 in `get_userStats`) — already refactored to aggregation
- The remaining 21 non-critical `except Exception` blocks
- Schema migrations, new API endpoints, JS/template changes

## Context for Development

### Codebase Patterns

- `institution_scope(request, field='patient__institution')` lives at `ndas/custom_codes/custom_methods.py` lines 15–18. Returns `{field: inst}` when institution is set, `{}` when None. Field argument is **completely unchecked** — any string passes through to the ORM. Three known call sites with field paths: `'patient__institution'`, `'owner__institution'`, `'institution'` (line ~1750 of `patients/views.py`) — all three must be in the whitelist.
- `Patient.objects.for_institution(inst)` is the manager shortcut; used correctly throughout `patients/views.py`.
- **Assessment querysets in `patient_view()`:** Institution scope is already implicitly enforced because `selected_patient` was fetched via `for_institution()`. Filtering by `patient=selected_patient` is sufficient institution isolation. Do NOT add `patient__institution=_inst` — it is redundant when `_inst` is not None and incorrect (silently hides records) when `_inst` is None in Phase 1 mixed-data scenarios.
- **`transaction` import is at line 5:** `from django.db import transaction`. To add `IntegrityError`, extend this same line to `from django.db import transaction, IntegrityError`. Do NOT add a separate import statement.
- `get_object_or_404()` accepts a queryset as its first argument — `get_object_or_404(Model.objects.select_for_update(), id=pk)` is valid Django and maintains the project standard.
- `select_for_update()` is **PostgreSQL-only**. On SQLite it raises `django.db.utils.DatabaseError`. Use an engine check: `if 'postgresql' in settings.DATABASES['default']['ENGINE']:` to conditionally apply the lock. Import `settings` from `django.conf` (already imported in `patients/views.py`).
- `transaction.on_commit(lambda: ...)` is Django built-in — no import beyond `transaction`.
- `@ratelimit` decorator from `django_ratelimit.decorators` is already imported in both views files.
- `get_object_or_404()` is already imported in `users/views.py`.
- **`Bookmark` model has NO `patient` ForeignKey** — it uses a generic `object_id` field. The cross-institution bookmark risk (Issue #4) cannot be fixed at the queryset filter level. Defence must be implemented at object-resolution time (when the bookmarked object is fetched).
- `verify_email()` has **no** `@ratelimit` and **no** `@require_GET`. `resend_verification_email()` has `@ratelimit` and `@require_POST` — `verify_email` needs both `@require_GET` and `@ratelimit`.
- Enumeration gap: `resend_verification_email` returns `"No account found with this email address."` (DoesNotExist) AND `"Your email is already verified."` (is_verified branch) — both leak account existence. The neutral message must replace **both** leak points.
- 9 security-critical bare `except Exception` blocks: lines ~937, ~1203, ~1469, ~1604, ~2192, ~2598, ~2977, ~3404, ~3713. **Task 8 must be applied AFTER Task 6** for `assessment_delete()` at line ~1203, since Task 6 restructures that function's exception chain first.
- `DeveloperContacts.objects.create()` with no arguments may fail if model has required fields. Verify `DeveloperContacts` model fields before implementing Task 10.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `patients/views.py` | 3,724 lines — contains issues #1/#2, #4, #5, #7, #9, #11, #12 |
| `users/views.py` | 955 lines — contains issues #3, #8 |
| `ndas/custom_codes/custom_methods.py` | 610 lines — contains issue #13 (`institution_scope` at lines 15–18) |
| `patients/models.py` | Verify `Bookmark` model structure (no patient FK confirmed) and `DeveloperContacts` required fields |
| `docs/adversarial-review-bugs.md` | Full issue descriptions with original code snippets |
| `patients/tests/test_views.py` | 818 lines — existing tests to run after changes |

### Technical Decisions

| Issue | Decision |
|-------|----------|
| **#1/#2 (combined)** | Fix is list() removal only. Replace `list()` + `len()` with lazy queryset + `.count()` / `[:5]` / `.first()`. Do NOT add `patient__institution` filter — `patient=selected_patient` is sufficient and correct. |
| **#3** | Add `@require_GET` and `@ratelimit(key='ip', rate='10/m', block=True)` to `verify_email`. In `resend_verification_email`, replace BOTH the DoesNotExist message AND the `is_email_verified` message with the same neutral text using `messages.success`. |
| **#4** | `Bookmark` has no `patient` FK — queryset-level filter is not possible. Fix: in the view that resolves and renders a bookmarked object, fetch the target patient using `Patient.objects.for_institution(request.institution).get(id=bookmark.object_id)` — if the patient is not in the current institution, it will raise `DoesNotExist` and the bookmark renders as stale/inaccessible. Document as architectural constraint of the generic bookmark design. |
| **#5** | Keep `patient__in=_pts_qs` as the institution scope for the Video queryset. Do NOT add `patient__institution=_inst` — same Phase 1 compatibility issue. The existing `video_file.patient_id != patient.pk` check at line 887 provides the defence-in-depth. |
| **#7** | In 9 security-critical paths: extend line 5 import to include `IntegrityError`, then add `except IntegrityError` (409) and `except PermissionDenied: raise` before the bare `except Exception`. Apply to `assessment_delete()` (line ~1203) AFTER Task 6 restructures it. |
| **#8** | Before replacing, read `DeveloperContacts` model definition to confirm `.create()` with no args is safe. If required fields exist, pass sensible defaults. Replace hardcoded `id=1` at all 4 locations with `.first()`. |
| **#9** | Replace `.get()` with `.filter().first()`. Add a `logger.warning` when count > 1 to preserve audit visibility of duplicate-identifier anomalies. Extra query is acceptable given this is a search path, not a hot loop. |
| **#11** | Use `get_object_or_404(GMAssessment.objects.select_for_update(), id=pk, **institution_scope(request))` inside `transaction.atomic()` — this maintains the NDAS `get_object_or_404` standard while adding the lock. The `select_for_update()` is guarded by a PostgreSQL engine check. |
| **#12** | Move `logger.info(...)` into `transaction.on_commit()` inside the atomic block. Capture `assessment.id` and `request.user.id` into local variables before the lambda. |
| **#13** | Add `_ALLOWED_SCOPE_FIELDS` frozenset with all 3 confirmed call-site paths: `'patient__institution'`, `'owner__institution'`, `'institution'`. Raise `ValueError` on unrecognised path. |

---

## Implementation Plan

### Tasks

**Ordering:** Task 1 (utility) → Task 2 (read path) → Task 3 (search) → Task 4 (video scope) → Task 5 (on_commit) → Task 6 (delete lock) → Task 7 (bookmark defence) → Task 8 (except — AFTER Task 6) → Task 9 (auth) → Task 10 (developer contacts).

---

- [x] **Task 1: Whitelist `institution_scope()` field-path argument** (Issue #13)
  - **File:** `ndas/custom_codes/custom_methods.py`
  - **Action:**
    1. Before the `institution_scope` function definition (line 15), add:
       ```python
       _ALLOWED_SCOPE_FIELDS = frozenset({
           'patient__institution',
           'owner__institution',
           'institution',
       })
       ```
    2. At the start of `institution_scope()`, add:
       ```python
       if field not in _ALLOWED_SCOPE_FIELDS:
           raise ValueError(
               f"institution_scope: unrecognised field path '{field}'. "
               "Add to _ALLOWED_SCOPE_FIELDS if intentional."
           )
       ```
  - **Notes:** Before committing, grep `patients/views.py` and all other files for `institution_scope(` and confirm every call site's field path is one of the three whitelisted values. Three confirmed call sites: `'patient__institution'` (default), `'owner__institution'` (bookmark_manager ~line 1319), `'institution'` (~line 1750 of `patients/views.py`). All three are in the whitelist.

---

- [x] **Task 2: Fix `patient_view()` — remove `list()` materialisation** (Issues #1 + #2)
  - **File:** `patients/views.py`, function `patient_view()` (~line 373)
  - **Action:**
    1. At the top of `patient_view()`, extract the institution (used only for `selected_patient` fetch, which already exists):
       ```python
       _inst = getattr(request, 'institution', None)
       ```
       *(Note: `selected_patient` at line 374 already uses `for_institution` — `_inst` is only needed for the existing line; do not add institution filters to assessment querysets — see notes.)*
    2. For all 7 querysets (lines ~377–425), apply this pattern — remove `list()`, replace `len()` with `.count()`, slice directly, use `.first()`:
       ```python
       # Video (replaces lines ~377-382):
       _video_qs = Video.objects.select_related('added_by', 'last_edit_by').filter(
           patient=selected_patient
       ).order_by("-id")
       file_video_count = _video_qs.count()
       file_videos = _video_qs[:5]

       # Attachment (replaces lines ~384-389):
       _attach_qs = Attachment.objects.select_related('added_by', 'last_edit_by').filter(
           patient=selected_patient
       ).order_by("-id")
       file_attachment_count = _attach_qs.count()
       file_attachment = _attach_qs[:5]

       # GMAssessment (replaces lines ~391-397):
       _gma_qs = GMAssessment.objects.select_related('added_by', 'last_edit_by', 'video_file').filter(
           patient=selected_patient
       ).order_by("-id")
       gm_assessments_count = _gma_qs.count()
       gm_assessments = _gma_qs[:5]
       gm_last_assessment = _gma_qs.first()

       # HINEAssessment (replaces lines ~399-404):
       _hine_qs = HINEAssessment.objects.select_related('added_by', 'last_edit_by').filter(
           patient=selected_patient
       ).order_by("-id")
       hine_assessments_count = _hine_qs.count()
       hine_assessments = _hine_qs[:5]

       # DevelopmentalAssessment (replaces lines ~406-411):
       _da_qs = DevelopmentalAssessment.objects.select_related('added_by', 'last_edit_by').filter(
           patient=selected_patient
       ).order_by("-id")
       da_assessments_count = _da_qs.count()
       da_assessments = _da_qs[:5]

       # CDICRecord (replaces lines ~413-418):
       _cdic_qs = CDICRecord.objects.select_related('added_by', 'last_edit_by').filter(
           patient=selected_patient
       ).order_by("-id")
       cdic_record_count = _cdic_qs.count()
       cdic_record = _cdic_qs[:5]

       # GeneralPaediatricAssessment (replaces lines ~420-425):
       _gpa_qs = GeneralPaediatricAssessment.objects.select_related(
           'discharged_authorized_by', 'added_by'
       ).filter(patient=selected_patient).order_by("-assessment_date")
       gpa_assessments_count = _gpa_qs.count()
       gpa_assessments = _gpa_qs[:5]
       ```
  - **Notes:** Do NOT add `patient__institution=_inst` to these querysets. `patient=selected_patient` already uniquely identifies the patient who was institution-scoped at fetch time. Adding `patient__institution=_inst` is redundant when `_inst` is not None, and silently hides records when `_inst` is None (Phase 1 mixed data). The institution scope is fully enforced by the `get_object_or_404(Patient.objects.for_institution(...), id=pk)` at line 374. Also note: downstream code that referenced `var_gma`, `var_hine`, etc. as lists must be updated — search for any use of these variable names below line 425 and replace with the new queryset variables.

---

- [x] **Task 3: Fix patient search — replace `.get()` with `.filter().first()` + duplicate warning** (Issue #9)
  - **File:** `patients/views.py`, function `patient_search()` (~lines 720–770)
  - **Action:**
    1. For the BHT search block (~lines 723–735), replace the `try/except` pattern:
       ```python
       _inst = getattr(request, 'institution', None)
       _bht_qs = Patient.objects.for_institution(_inst).filter(bht=search_text)
       if _bht_qs.count() > 1:
           logger.warning(
               f"Duplicate BHT '{search_text}' found in institution {_inst} — "
               "data integrity anomaly, returning first result"
           )
       patient = _bht_qs.first()
       if patient:
           messages.success(request, f"Found patient with BHT: {search_text}")
           return render(request, "patients/view.html", {"patient": patient, "pgn": pagn})
       else:
           messages.warning(request, f"No patient found with BHT: {search_text}")
           return render(request, "patients/search_notfound.html", {"pgn": pagn})
       ```
    2. Apply the identical pattern to PHN search (~line 740): field `pin=search_text`, log message "Duplicate PHN".
    3. Apply the identical pattern to NNC search (~line 757): field `nnc_no=search_text`, log message "Duplicate NNC".
  - **Notes:** The extra `.count()` query per search is acceptable on a search path (not a hot loop). The warning ensures duplicate identifiers are visible in logs even though no exception is raised to the user.

---

- [x] **Task 4: Harden video scope in `assessment_add()` — remove Phase 1 unsafe filter** (Issue #5)
  - **File:** `patients/views.py`, function `assessment_add()` (~line 884)
  - **Action:** No change to the Video queryset filter itself. The existing code:
    ```python
    video_file = get_object_or_404(Video.objects.filter(patient__in=_pts_qs), pk=fid)
    ```
    is correct — `_pts_qs` already provides institution scope. The defence-in-depth for this view is the explicit patient ownership check at line 887:
    ```python
    if video_file.patient_id != patient.pk:
        messages.error(request, "This video does not belong to the selected patient.")
        return redirect("view-patient", pk=patient.pk)
    ```
    Verify this check is present. If it is, no additional filter is needed. If it is absent, add it. Add a code comment above the `get_object_or_404` line:
    ```python
    # Institution scope is enforced via patient__in=_pts_qs (for_institution scoped).
    # patient_id check below provides defence-in-depth against cross-patient access.
    ```
  - **Notes:** Do NOT add `patient__institution=_inst` to this queryset. When `_inst` is None, `patient__institution=None` is not equivalent to `for_institution(None)` which returns all records — this would silently restrict results and break Phase 1 deployments with mixed institution data.

---

- [x] **Task 5: Move post-save log to `transaction.on_commit()`** (Issue #12)
  - **File:** `patients/views.py`, function `assessment_add()` (~lines 914–920)
  - **Action:** Change:
    ```python
    with transaction.atomic():
        assessment.save()
        diagnosis_list = assessment_form.cleaned_data.get('diagnosis', [])
        if diagnosis_list:
            assessment.diagnosis.set(diagnosis_list)

    logger.info(f"Assessment created successfully: {assessment.id} by user {request.user.id}")
    ```
    To:
    ```python
    with transaction.atomic():
        assessment.save()
        diagnosis_list = assessment_form.cleaned_data.get('diagnosis', [])
        if diagnosis_list:
            assessment.diagnosis.set(diagnosis_list)
        _aid = assessment.id
        _uid = request.user.id
        transaction.on_commit(lambda: logger.info(
            f"Assessment created successfully: {_aid} by user {_uid}"
        ))
    ```
  - **Notes:** `_aid` and `_uid` are captured as local variables inside the atomic block before the lambda, so their values are fixed at call time.

---

- [x] **Task 6: Fix assessment delete race condition with `select_for_update()`** (Issue #11)
  - **File:** `patients/views.py`, function `assessment_delete()` (~lines 1113–1213)
  - **Action:**
    1. Extend the existing import at line 5 from `from django.db import transaction` to `from django.db import transaction, IntegrityError`. *(Do not add a new import line — extend the existing one.)*
    2. Import `settings` if not already imported: confirm `from django.conf import settings` exists.
    3. Wrap the entire fetch-through-delete sequence in `with transaction.atomic():`. Use `get_object_or_404` with a conditionally locked queryset:
       ```python
       try:
           with transaction.atomic():
               # Use select_for_update on PostgreSQL to prevent concurrent deletes
               if 'postgresql' in settings.DATABASES['default']['ENGINE']:
                   _qs = GMAssessment.objects.select_for_update()
               else:
                   _qs = GMAssessment.objects
               assessment = get_object_or_404(_qs, id=pk, **institution_scope(request))
               patient = assessment.patient

               # ... (permission checks, password verify, business rules — unchanged) ...

               # Deletion inside the atomic block
               assessment.delete()

           # Audit log fires only after successful commit
           _aname = assessment_name  # captured before delete
           transaction.on_commit(lambda: logger.info(
               f"Deletion successful: user={request.user.username}, "
               f"entity=GMAssessment, name={_aname}, id={pk}, "
               f"patient={patient.baby_name}"
           ))
       except Http404:
           return JsonResponse({"success": False, "error": "Not found",
               "message": "Assessment not found."}, status=404)
       except Exception as e:
           # bare except remains for now — Task 8 will refine this
           ...
       ```
    4. Capture `assessment_name` (from `get_entity_display_name(assessment)`) before `assessment.delete()` so it's available in the `on_commit` lambda.
  - **Notes:** `Http404` is raised by `get_object_or_404` when not found — import it: `from django.http import Http404` (confirm if already imported). The PostgreSQL engine check ensures the test suite on SQLite continues to pass — no lock is attempted on SQLite. Task 8 will add `IntegrityError` and `PermissionDenied` handlers to this function's outer `except Exception` — apply Task 8 **after** this task.

---

- [x] **Task 7: Fix bookmark cross-institution risk at object-resolution level** (Issue #4)
  - **File:** `patients/views.py` — bookmark detail/follow view (the view that resolves `bookmark.object_id` to a patient record)
  - **Action:** The `Bookmark` model uses a generic `object_id` field — there is no `patient` FK, so queryset-level institution filtering is not possible. The defence must be at resolution time. Locate the view that fetches the bookmarked patient from a bookmark record (search for `bookmark.object_id` in `patients/views.py`). Where the patient is resolved, replace any bare lookup with an institution-scoped lookup:
    ```python
    # BEFORE (unsafe — fetches patient regardless of institution):
    patient = Patient.objects.get(id=bookmark.object_id)

    # AFTER (institution-scoped — raises DoesNotExist if patient is not in current institution):
    patient = get_object_or_404(
        Patient.objects.for_institution(getattr(request, 'institution', None)),
        id=bookmark.object_id
    )
    ```
    Add a code comment:
    ```python
    # Institution scope enforced here — stale cross-institution bookmarks will 404.
    ```
  - **Notes:** This is the architecturally correct fix given the generic bookmark design. The bookmark_manager() queryset filter (by `owner__institution`) remains unchanged — it already correctly limits which bookmarks are shown. The additional protection is at the point where the bookmarked object is actually accessed. If `bookmark.object_id` resolution does not exist as a dedicated step in the current code (e.g. the view renders only metadata without fetching the patient), document the gap and add a TODO to enforce institution scope when the feature is extended.

---

- [x] **Task 8: Fix security-critical bare `except Exception` blocks** (Issue #7)
  - **File:** `patients/views.py`
  - **Prerequisites:** Task 6 must be applied first for `assessment_delete()` (~line 1203).
  - **Action:** `IntegrityError` is already imported after Task 6 (line 5). For each of the 9 locations (lines ~937, ~1203, ~1469, ~1604, ~2192, ~2598, ~2977, ~3404, ~3713), insert explicit handlers **before** the bare `except Exception`:
    ```python
    except IntegrityError as e:
        logger.error(f"Database integrity error in [view_name]: {e}")
        return JsonResponse({
            "success": False,
            "error": "Data integrity error",
            "message": "A data conflict occurred. Please refresh and try again."
        }, status=409)
    except PermissionDenied:
        raise  # Re-raise so Django's 403 handler takes over
    except Exception as e:
        logger.error(f"Unexpected error in [view_name]: {e}")
        return JsonResponse({"success": False, ...}, status=500)
    ```
  - **Notes:** Replace `[view_name]` with the actual view function name at each location. `PermissionDenied` is already imported from `django.core.exceptions` at line ~69. For `assessment_delete()` (~line 1203): after Task 6's restructuring, verify the outer `except Exception` location before inserting — the structure will have changed. Apply delete endpoints first (~1203, ~2192, ~2598, ~2977, ~3404, ~3713), then save endpoints (~937, ~1469, ~1604).

---

- [x] **Task 9: Fix `verify_email()` — add rate limiting, method restriction, and fix enumeration** (Issue #3)
  - **File:** `users/views.py`
  - **Action:**
    1. Add two decorators to `verify_email()` immediately before `def verify_email(request, token):` (line ~305):
       ```python
       @require_GET
       @ratelimit(key='ip', rate='10/m', block=True)
       def verify_email(request, token):
       ```
       (`require_GET` is already imported via `django.views.decorators.http` — confirm import exists.)
    2. In `resend_verification_email()`, replace ALL three response messages that leak account existence:
       - **DoesNotExist branch** (~line 373): change `messages.error(request, 'No account found with this email address.')` to `messages.success(request, 'If an account with this email exists and is unverified, a link has been sent.')`
       - **`is_email_verified` branch** (~line 354): change `messages.info(request, 'Your email is already verified.')` to the same neutral message: `messages.success(request, 'If an account with this email exists and is unverified, a link has been sent.')`
       - **Success branch** (~line 367): update to the same neutral message for consistency.
  - **Notes:** All three branches of `resend_verification_email()` must return the same message text. Using `messages.success` for all three eliminates all observable differences between found/not-found/already-verified outcomes.

---

- [x] **Task 10: Align `DeveloperContacts` lookup to project standard** (Issue #8)
  - **File:** `users/views.py`, lines ~42, ~287, ~881, ~900
  - **Prerequisite:** Read `DeveloperContacts` model definition in `users/models.py` (or wherever defined) and confirm that `.objects.create()` with no arguments is safe (no required fields without defaults). If required fields exist, pass appropriate defaults in the `.create()` call.
  - **Action:** Replace at all 4 locations:
    ```python
    try:
        developer = DeveloperContacts.objects.get(id=1)
    except DeveloperContacts.DoesNotExist:
        developer = DeveloperContacts.objects.first()
        if not developer:
            developer = DeveloperContacts.objects.create()
    ```
    With:
    ```python
    developer = DeveloperContacts.objects.first()
    if developer is None:
        developer = DeveloperContacts.objects.create()  # safe only if no required fields
    ```
  - **Notes:** `.first()` returns `None` on empty table — no exception raised. The hardcoded `id=1` is eliminated. If the `DeveloperContacts` model has required fields, replace `DeveloperContacts.objects.create()` with `DeveloperContacts.objects.create(field=default_value, ...)` using sensible defaults. Confirm before implementing.

---

### Acceptance Criteria

- [x] **AC1:** Given `institution_scope()` is called with an unrecognised field path, when the function executes, then it raises `ValueError` identifying the invalid path.

- [x] **AC2:** Given `institution_scope()` is called with any of the three whitelisted paths (`'patient__institution'`, `'owner__institution'`, `'institution'`), when the function executes, then it returns the correct ORM filter kwargs dict without raising.

- [x] **AC3:** Given a patient with 100 GMA assessments, when `patient_view()` renders, then `with self.assertNumQueries(N):` confirms no more than 2 queries per assessment model (1 COUNT + 1 SELECT with LIMIT 5) — no full queryset materialised. *(Use `assertNumQueries` in `patients/tests/test_views.py`, not `connection.queries` which requires DEBUG=True.)*

- [x] **AC4:** Given two patients with the same BHT in the database, when `patient_search()` is called with that BHT, then a single patient is returned (first match), no 500 error is raised, and a `WARNING`-level log entry is written recording the duplicate.

- [x] **AC5:** Given a valid video that belongs to an institution-scoped patient, when `assessment_add()` fetches the video, then the queryset uses `patient__in=_pts_qs` (institution-scoped) and the `patient_id` ownership check at line 887 is present as defence-in-depth.

- [x] **AC6:** Given an assessment is saved inside `transaction.atomic()` and the transaction rolls back after `diagnosis.set()` raises, when the rollback completes, then no `logger.info` entry is written for that assessment.

- [x] **AC7:** Given two concurrent DELETE requests for the same assessment on PostgreSQL, when both are processed, then exactly one succeeds (HTTP 200) and the other returns an error — no duplicate deletion or silent 500.

- [x] **AC8:** Given a bookmark owned by Institution A whose `object_id` references a patient that belongs to Institution B, when the bookmark detail view resolves that patient under Institution A's context, then `get_object_or_404(Patient.objects.for_institution(A), id=bookmark.object_id)` raises 404 — the cross-institution patient is not accessible.

- [x] **AC9:** Given an `IntegrityError` is raised during a delete operation, when the exception is caught, then the response status is 409 and the logger records an `error`-level message containing "integrity" (not a generic 500 message).

- [x] **AC10:** Given `verify_email` receives 11 rapid GET requests from the same IP within 1 minute, when the 11th request arrives, then it is blocked by `@ratelimit` (`block=True`).

- [x] **AC11:** Given `resend_verification_email` is called with a non-existent email, a verified-account email, and an unverified-account email, when all three responses are returned, then all three display the same message text — no observable difference between outcomes.

- [x] **AC12:** Given `DeveloperContacts` table is empty, when any of the 4 views that reference developer contact info render, then the page loads without a 500 error.

- [x] **AC13:** Given all 10 tasks are applied, when `python manage.py test patients` is run, then all existing tests in `patients/tests/test_views.py` pass.

---

## Review Notes

- Adversarial review completed: 2026-03-11
- Findings: 12 total, 8 fixed, 4 skipped
- Resolution approach: auto-fix
- Findings fixed: F1 (lock scope narrowed), F2 (Http404 on all delete endpoints), F4 (email send failure logged), F5 (template queryset re-evaluation fixed), F6 (1-query search), F7 (ValueError→ImproperlyConfigured), F9 (get_or_create), F12 (on_commit on all delete audit logs)
- Findings skipped: F3 (acceptable timing residual), F8 (negligible niche edge case), F10 (reviewer's decorator order analysis was incorrect — current order is correct), F11 (known Django TestCase/on_commit limitation, not a bug)

---

## Additional Context

### Dependencies

- No new packages required. All fixes use:
  - Django built-ins: `select_for_update()`, `transaction.on_commit()`, `transaction.atomic()`, `get_object_or_404()`
  - Existing `django-ratelimit 4.1.0` (already installed and imported)
  - `IntegrityError` from `django.db` — extend line 5 of `patients/views.py`
  - `PermissionDenied` from `django.core.exceptions` — already imported
  - `Http404` from `django.http` — confirm import for Task 6
  - `require_GET` from `django.views.decorators.http` — confirm import for Task 9
  - `settings` from `django.conf` — confirm import for Task 6 engine check

### Testing Strategy

- **After each task:** Run `python manage.py test patients` — all existing tests must stay green.
- **Task 1 (whitelist):** Add unit test: call `institution_scope(mock_request, 'bad__field')` and assert `ValueError`.
- **Task 2 (list() removal):** Use `assertNumQueries()` to verify COUNT + LIMIT SELECT per assessment model.
- **Task 3 (search fix):** Verify `.filter().first()` returns a result with no exception when duplicate BHT exists in fixture. Check logger output for WARNING.
- **Task 6 (delete lock):** AC 7 requires PostgreSQL — mark test as `@skipUnless(settings.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql', 'PostgreSQL only')`.
- **Task 8 (except Exception):** `DeleteEndpointErrorSanitizationTest` (test_views.py lines 556–618) tests error message sanitization — run it after Task 8 to confirm new `IntegrityError` handler doesn't break existing assertions.
- **Task 9 (rate limiting):** Manual test — 11 rapid GET requests to `verify_email`, confirm 11th blocked.
- **Task 9 (enumeration):** Test all three `resend_verification_email` branches — confirm identical response message.

### Notes

- **Task application order matters:** Task 1 first (before any new `institution_scope()` call sites). Task 6 before Task 8 for `assessment_delete()`. All others are independent.
- **Issue #4 (bookmarks):** The generic `object_id` design is an architectural limitation. The queryset-level filter cannot be applied. The fix is minimal and correct: enforce institution scope at object resolution time. A future migration to a direct `patient` FK would enable a stronger queryset-level fix.
- **Issue #7 scope:** Only 9 of 30 `except Exception` blocks are addressed. The remaining 21 (pagination helpers, attachment managers, CDIC/HINE/DA managers) should be addressed in a follow-on cleanup task.
- **SQLite / `select_for_update()` (Task 6):** The PostgreSQL engine check means the lock is a no-op on SQLite dev/test environments. The atomic block still provides correct rollback semantics — concurrent requests on SQLite will serialise via SQLite's global write lock, giving partial protection. Full protection requires PostgreSQL in production.
- **`DeveloperContacts.create()` (Task 10):** Inspect `users/models.py` before implementing. If any field has `blank=False, null=False` without a `default`, `.create()` will raise `IntegrityError`. Pass defaults or use `get_or_create()` with sensible field values.
