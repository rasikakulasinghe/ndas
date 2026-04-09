# NDAS Code Review — Adversarial Analysis
**Date:** 2026-04-09  
**Reviewer:** BMad Code Review (Adversarial Mode)  
**Scope:** All modified source files + full-suite test execution  
**Test Result:** 99 tests run — **20 ERRORS, 79 passing**

---

## Executive Summary

The recent changes introduce Http404 explicit handling across delete endpoints, an OSError guard in `validate_video_file`, an `isinstance(UploadedFile)` guard in `VideoForm`, and comprehensive CRUD test suites for all three apps. The changes are directionally correct but introduce and expose several bugs ranging from test-breaking import failures to a silent privacy leak in the bookmark filter. Three issues will cause real-world failures in production. Fix all HIGH items before merging.

---

## 🔴 CRITICAL — Test-Breaking Failures

### CR-1: Missing function `validate_birth_weight_for_gestational_age` in validators.py

**File:** `ndas/custom_codes/validators.py`  
**Severity:** CRITICAL  
**Evidence:** Test run output:
```
ImportError: cannot import name 'validate_birth_weight_for_gestational_age'
from 'ndas.custom_codes.validators'
```
**Impact:** `patients/tests/test_validators.py` fails to import entirely — **entire test module skipped**. This function was referenced in existing tests but never existed (or was removed), creating a silent gap in validator coverage.  
**Fix:** Either add the function to `validators.py` or update `test_validators.py` to remove the import if the function is intentionally absent.

---

### CR-2: `GMAssessment.video_file` is non-null — breaks 19 existing tests

**File:** `patients/tests/test_views.py` (existing file, not part of this diff)  
**Severity:** CRITICAL  
**Evidence:** Test run output (repeated 19 times):
```
django.core.exceptions.ValidationError: {'video_file': ['This field cannot be null.']}
```
**Impact:** The `GMAssessment` model now enforces `video_file` as non-null, but all existing `DashboardTestCase` and `PatientManagerTestCase` setUp methods create `GMAssessment` records without a `video_file`. Every test in these two classes fails. The GMAssessment model or its migration changed without updating the test fixtures.  
**Fix:** In `patients/tests/test_views.py`, update every `GMAssessment.objects.create(...)` call to include a valid `video_file` fixture, OR add `null=True, blank=True` back to the model field if it was changed inadvertently.

---

## 🔴 HIGH — Production Bugs

### H-1: `.wmv` extension allowed by VideoForm but rejected by model validator

**Files:**  
- `video/forms.py:93` — `allowed_extensions = ['.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm']`  
- `ndas/custom_codes/validators.py:415` — `valid_extensions = allowed_extensions_dict.get("VIDEO", [".mp4", ".mov", ".avi", ".mkv", ".webm"])`

**Severity:** HIGH  
**Impact:** A user uploads a `.wmv` video. The form validates it successfully (form passes). Django then calls the model-level `validate_video_file` which uses `settings.ALLOWED_FILE_EXTENSIONS['VIDEO']`. If settings does not include `.wmv` (the default fallback list doesn't), the model validator raises `ValidationError`. The user gets an unintelligible error after the file has already been transferred. **Inconsistency causes failed uploads with no clear user feedback.**

**Fix options (choose one):**
1. Add `.wmv` to `settings.ALLOWED_FILE_EXTENSIONS['VIDEO']`
2. Remove `.wmv` from `VideoForm.allowed_extensions` at `video/forms.py:93`

Verify settings:
```python
# ndas/settings.py — ensure these match:
ALLOWED_FILE_EXTENSIONS = {
    'VIDEO': ['.mp4', '.mov', '.avi', '.mkv', '.webm'],  # add .wmv if desired
    ...
}
```

---

### H-2: `VideoForm` max size is 500 MB — model validator allows 2 GB

**File:** `video/forms.py:86-89`  
```python
max_size = 500 * 1024 * 1024  # 500MB in bytes
if video_file.size > max_size:
    raise ValidationError(_('Video file is too large. Maximum size allowed is 500MB.'))
```
**Severity:** HIGH  
**Impact:** `settings.FILE_UPLOAD_LIMITS['VIDEO_MAX_SIZE']` is 2 GB. The model validator (`validate_video_file`) uses this setting. But the form hard-codes 500 MB. A 600 MB video — which is within the documented system limit — fails at form validation with a misleading error. The form help text also says "max 500MB" contradicting the system's actual 2 GB limit.

**Fix:** Replace the hardcoded size with the settings value:
```python
from django.conf import settings
limits = getattr(settings, 'FILE_UPLOAD_LIMITS', {})
max_size = limits.get('VIDEO_MAX_SIZE', 500 * 1024 * 1024)
```
Update the help text and ValidationError message to match.

---

### H-3: Bookmark filter in `video_manager` leaks other users' bookmarks

**File:** `video/views.py:314-319`  
```python
if bookmarked_filter:
    from patients.models import Bookmark
    bookmarked_video_ids = Bookmark.objects.filter(
        bookmark_type="Video"
    ).values_list('object_id', flat=True)
    queryset = queryset.filter(id__in=bookmarked_video_ids)
```
**Severity:** HIGH  
**Impact:** The bookmark filter shows every video that ANY user has bookmarked, not just the current user's bookmarks. A user activating "Show Bookmarked" sees videos bookmarked by colleagues — a privacy violation in a multi-user medical system. This is especially serious given NDAS handles patient data.

**Fix:** Add `added_by=request.user` filter:
```python
bookmarked_video_ids = Bookmark.objects.filter(
    bookmark_type="Video",
    added_by=request.user
).values_list('object_id', flat=True)
```

---

### H-4: `admin_user_delete` uses `LOGIN_SUCCESS` for deletion audit log

**File:** `users/views.py:757-762`  
```python
log_user_activity(
    request,
    request.user,
    UserActivityLog.LOGIN_SUCCESS,  # ← wrong type
    failed_reason=f"Admin action: Deleted (deactivated) user: {user.username}"
)
```
**Severity:** HIGH  
**Impact:** Every user deactivation is recorded in the audit trail as a **successful login event**. Any security audit or compliance review will show inflated login counts and miss actual deletion events. `admin_user_toggle_status` at `users/views.py:812` has the same bug. The `UserActivityLog` model only defines `LOGIN_SUCCESS`, `LOGIN_FAILED`, and `LOGOUT` — there is no admin action type.

**Fix (two-step):**

1. Add an admin action constant to `UserActivityLog` model:
```python
# users/models.py
ADMIN_ACTION = 'admin'

LOGIN_STATUS_CHOICES = [
    (LOGIN_SUCCESS, 'Success'),
    (LOGIN_FAILED, 'Failed'),
    (LOGOUT, 'Logout'),
    (ADMIN_ACTION, 'Admin Action'),  # add this
]
```
2. Update both `admin_user_delete` and `admin_user_toggle_status` to use `UserActivityLog.ADMIN_ACTION`.
3. Run `makemigrations users`.

---

## 🟡 MEDIUM — Code Quality & Correctness

### M-1: Double ValidationError in `video_add`/`video_edit` for recording date

**File:** `video/views.py:46-49, 73-75` (video_add), `video/views.py:172-175, 192-194` (video_edit)  
```python
# In video_add:
form.add_error('recorded_on', 'Recording date cannot be before patient birth date.')
raise ValidationError('Recording date cannot be before patient birth date.')
# ...caught by:
except ValidationError as e:
    form.add_error(None, str(e))  # adds SAME message as a non-field error too
```
**Impact:** When recording date < patient DOB, the same error message appears twice — once on the `recorded_on` field and once as a general form error. This confuses users and clutters the UI.

**Fix:** Either add the field error then return without raising, or raise and let the except block handle it — not both:
```python
# Option A: add field error only, don't raise
form.add_error('recorded_on', 'Recording date cannot be before patient birth date.')
# Fall through to re-render form — no raise needed
```
Remove the `raise ValidationError(...)` line that follows.

---

### M-2: Dead `Video.DoesNotExist` catch in `video_delete_confirm`

**File:** `video/views.py:495-501`  
```python
except Video.DoesNotExist:
    messages.error(request, "Video not found.")
    return redirect("video:manager")
```
**Impact:** `get_object_or_404` never raises `Video.DoesNotExist` — it always raises `Http404`. This catch block is unreachable dead code. It misleads readers into thinking it handles a real case, and gives false security about error coverage. The actual Http404 is caught by the outer `@handle_view_errors` decorator.

**Fix:** Remove the dead `except Video.DoesNotExist` block entirely.

---

### M-3: `import logging as _logging` inside function body

**File:** `ndas/custom_codes/validators.py:432-434`  
```python
except OSError:
    import logging as _logging
    _logging.getLogger(__name__).warning(...)
```
**Impact:** The `_logging` alias suggests intentional obfuscation or a one-off import, but it's just logging. Python caches module imports so there's no performance benefit to lazy importing here. The `_` prefix implies it's a private/internal import, which is misleading. The module already imports at the top level for other purposes.

**Fix:** Add `import logging` at the top of `validators.py` alongside the existing imports:
```python
import os, math, mimetypes, re, html, logging
logger = logging.getLogger(__name__)
```
Then in the except block:
```python
except OSError:
    logger.warning(
        "validate_video_file: could not read size for %r — skipping size check", value.name
    )
    return
```

---

### M-4: `VideoForm.clean_video_file` uses fragile extension parsing

**File:** `video/forms.py:94`  
```python
file_extension = video_file.name.lower().split('.')[-1]
if f'.{file_extension}' not in allowed_extensions:
```
**Impact:** `split('.')[-1]` is fragile:
- File with no extension: `"videofile"` → `split('.')` returns `["videofile"]`, `[-1]` = `"videofile"`, check becomes `.videofile not in allowed_extensions` — wrong but won't crash
- File like `"archive.tar.mp4"` → returns `mp4` (correct but accidental)
- Inconsistent with the rest of the codebase which uses `os.path.splitext()`

**Fix:** Use `os.path.splitext` consistently:
```python
import os
_, file_extension = os.path.splitext(video_file.name.lower())
if file_extension not in allowed_extensions:
```

---

### M-5: `admin_user_delete` has step numbering gap (3 → 5, step 4 missing)

**File:** `users/views.py:708-754`  
Comments show steps `# 1.`, `# 2.`, `# 3.`, then jump to `# 5.`. Step 4 (likely a previous business rules check that was removed) was deleted but the numbering wasn't updated.

**Fix:** Renumber to 1–5 sequentially, or remove comment numbering and use descriptive comments instead.

---

## 🟢 LOW — Performance & Polish

### L-1: `video_manager_by_patient` runs redundant `for_institution` query

**File:** `video/views.py:411-420`  
```python
patient = get_object_or_404(Patient.objects.for_institution(...), id=patient_id)
# ... then:
_inst = getattr(request, 'institution', None)
_patients_qs = Patient.objects.for_institution(_inst)  # redundant
queryset = Video.objects.filter(patient__in=_patients_qs, patient_id=patient_id)
```
The `patient__in=_patients_qs` subquery is redundant when `patient_id=patient_id` already uniquely identifies the record, and institution scoping was already enforced by `get_object_or_404`.

**Fix:**
```python
queryset = Video.objects.select_related("patient", "added_by", "last_edit_by").filter(
    patient=patient
).order_by("-recorded_on", "-created_at")
```

---

### L-2: `video_manager` status filter re-evaluates `GMAssessment` queryset on every filter

**File:** `video/views.py:268-277`  
```python
if status_filter == "new":
    from patients.models import GMAssessment
    used_video_ids = GMAssessment.objects.values_list('video_file_id', flat=True)
    queryset = queryset.exclude(id__in=used_video_ids)
elif status_filter == "assessed":
    from patients.models import GMAssessment
    used_video_ids = GMAssessment.objects.values_list('video_file_id', flat=True)
    queryset = queryset.filter(id__in=used_video_ids)
```
Two separate branches both run `GMAssessment.objects.values_list(...)`. Minor inefficiency — only one branch can run per request, so duplication is code smell, not a real double-query. However, both branches import inside the if block, which is non-standard.

**Fix:** Move the import to module level and keep the query DRY:
```python
from patients.models import GMAssessment  # at module top
# ...
if status_filter in ("new", "assessed"):
    used_video_ids = GMAssessment.objects.values_list('video_file_id', flat=True)
    if status_filter == "new":
        queryset = queryset.exclude(id__in=used_video_ids)
    else:
        queryset = queryset.filter(id__in=used_video_ids)
```

---

### L-3: `validate_video_file` comment says "size validation applies to new uploads only" — but it's also called on model saves of existing records

**File:** `ndas/custom_codes/validators.py:426-428`  
The comment states the OSError guard is for "test environments" and "new uploads only." But `validate_video_file` is a model-level field validator — it runs on every `full_clean()` call, including edits to existing records. The comment could mislead future developers into thinking the validator only fires on uploads, causing them to skip the guard for other scenarios.

**Fix:** Update the comment to be precise:
```python
# Use try/except because stored FieldFiles may not be physically accessible on disk
# (e.g., different servers, test fixtures with dummy paths). Size validation is only
# meaningful for new uploads — for existing records, the size check is skipped safely.
```

---

## Test Infrastructure Issues

### TI-1: `patients/tests/test_views.py` — naive datetime warning in test fixtures

**File:** `patients/tests/test_views.py:100` (pre-existing)  
```
RuntimeWarning: DateTimeField Patient.dob_tob received a naive datetime
(2025-11-10 00:00:00) while time zone support is active.
```
Test creates a `Patient` with a naive datetime while `USE_TZ=True`. This won't cause a test failure but creates database-layer warnings on every test run, polluting CI output.

**Fix:** Use `timezone.make_aware(datetime(...))` or `timezone.now() - timedelta(...)` for all test datetime fixtures.

---

### TI-2: `video/tests.py` — "Failed to get file size" logged 16 times per test run

The `Video` model's `file_size_mb` property (or similar) tries to access the physical file for the test fixture (`videos/test_video_001.mp4`) which doesn't exist on disk. This logs `[WinError 2]` for every video test. Not a failure, but noisy and indicates the test setup doesn't fully isolate from the filesystem.

The `validate_video_file` change in this PR correctly handles OSError in the model validator. However, the file size property elsewhere in the model still reaches the disk. Consider using `SimpleUploadedFile` in test setUp to create an actual in-memory file, or mock `video.file_size_mb`.

---

## Findings Summary

| ID  | Severity | File | Description |
|-----|----------|------|-------------|
| CR-1 | 🔴 CRITICAL | `patients/tests/test_validators.py` | Missing `validate_birth_weight_for_gestational_age` import — test module fails |
| CR-2 | 🔴 CRITICAL | `patients/tests/test_views.py` | GMAssessment.video_file non-null breaks 19 existing tests |
| H-1  | 🔴 HIGH | `video/forms.py:93`, `validators.py:415` | .wmv allowed in form, rejected by model validator |
| H-2  | 🔴 HIGH | `video/forms.py:86` | Form max size 500 MB vs system max 2 GB |
| H-3  | 🔴 HIGH | `video/views.py:314-319` | Bookmark filter shows ALL users' bookmarks (privacy bug) |
| H-4  | 🔴 HIGH | `users/views.py:757-762` | Deletion logged as LOGIN_SUCCESS in audit trail |
| M-1  | 🟡 MEDIUM | `video/views.py:48-75` | Double ValidationError for recording date |
| M-2  | 🟡 MEDIUM | `video/views.py:495-501` | Dead `Video.DoesNotExist` catch (unreachable code) |
| M-3  | 🟡 MEDIUM | `validators.py:432-433` | `import logging as _logging` inside function body |
| M-4  | 🟡 MEDIUM | `video/forms.py:94` | Fragile extension parsing with `split('.')` |
| M-5  | 🟡 MEDIUM | `users/views.py` | Step numbering gap in `admin_user_delete` (3→5) |
| L-1  | 🟢 LOW | `video/views.py:411-420` | Redundant `for_institution` query in `video_manager_by_patient` |
| L-2  | 🟢 LOW | `video/views.py:268-277` | Duplicated imports inside status filter branches |
| L-3  | 🟢 LOW | `validators.py:426-428` | Misleading comment about when validator runs |
| TI-1 | ℹ️ INFO | `patients/tests/test_views.py` | Naive datetime in test fixtures |
| TI-2 | ℹ️ INFO | `video/tests.py` | 16x "[WinError 2]" log noise per test run |

---

## Recommended Fix Order

1. **CR-1** — Add or remove `validate_birth_weight_for_gestational_age` (5 min)
2. **CR-2** — Fix GMAssessment test fixtures to include video_file (15 min)
3. **H-3** — Add `added_by=request.user` to bookmark filter (2 min, one-liner)
4. **H-2** — Replace 500MB hardcode with settings value in VideoForm (5 min)
5. **H-1** — Align .wmv between form and settings (2 min)
6. **H-4** — Add ADMIN_ACTION to UserActivityLog and update callers (20 min + migration)
7. **M-1** — Remove duplicate `raise ValidationError` in video add/edit (5 min)
8. **M-2** — Delete dead except block in `video_delete_confirm` (1 min)
9. **M-3** — Move logging import to module top in validators.py (2 min)
10. **M-4** — Replace split('.') with os.path.splitext in VideoForm (2 min)
