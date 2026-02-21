# Story 2.1: Sanitize Exception Details in Delete Endpoint Responses

Status: done

## Story

As a security-conscious developer,
I want all delete endpoint error responses to return a generic message instead of raw exception details,
so that database schema, file paths, and internal model structure are never leaked to the browser.

## Acceptance Criteria

1. All 8 delete endpoint `except Exception` handlers return `"An unexpected error occurred. Please try again."` as the JSON `"message"` value — no `str(e)` anywhere in the response body.
2. Full exception details are logged server-side using `logger.exception(...)` (not `logger.error`).
3. `str(e)` is NOT included in any JSON response body from any delete view.
4. All 8 affected delete views are updated: `patient_delete`, `assessment_delete`, `bookmark_delete`, `attachment_delete`, `cdic_assessment_delete`, `hine_assessment_delete`, `da_assessment_delete`, `gpa_delete`.
5. Test: triggering a deliberate delete error returns the generic message, not stack trace or DB details.

## Tasks / Subtasks

- [x] Task 1: Fix `patient_delete` except block (AC: #1, #2, #3)
  - [x] `patients/views.py` ~line 585: change `logger.error(...)` → `logger.exception(...)`, remove `error={str(e)}` from log message
  - [x] Change JSON `"message"` from `f"An error occurred during deletion: {str(e)}"` → `"An unexpected error occurred. Please try again."`
- [x] Task 2: Fix `assessment_delete` except block (AC: #1, #2, #3)
  - [x] `patients/views.py` ~line 1183: same two-line fix as Task 1
- [x] Task 3: Fix `bookmark_delete` except block (AC: #1, #2, #3)
  - [x] `patients/views.py` ~line 1712: same two-line fix
- [x] Task 4: Fix `attachment_delete` except block (AC: #1, #2, #3)
  - [x] `patients/views.py` ~line 2297: same two-line fix
- [x] Task 5: Fix `cdic_assessment_delete` except block (AC: #1, #2, #3)
  - [x] `patients/views.py` ~line 2697: same two-line fix
- [x] Task 6: Fix `hine_assessment_delete` except block (AC: #1, #2, #3)
  - [x] `patients/views.py` ~line 3077: same two-line fix
- [x] Task 7: Fix `da_assessment_delete` except block (AC: #1, #2, #3)
  - [x] `patients/views.py` ~line 3498: same two-line fix
- [x] Task 8: Fix `gpa_delete` except block (AC: #1, #2, #3)
  - [x] `patients/views.py` ~line 3807: same two-line fix
- [x] Task 9: Write test (AC: #5)
  - [x] Add test class to `patients/tests/test_views.py` that mocks `Patient.delete()` to raise an exception
  - [x] Assert response JSON `"message"` == `"An unexpected error occurred. Please try again."`
  - [x] Assert `str(e)` value is NOT in response content

## Dev Notes

### The Bug Pattern — Identical in All 8 Delete Views

Every delete endpoint's `except Exception as e:` block has two problems:

```python
# CURRENT (INSECURE) — leaks exception to browser
except Exception as e:
    logger.error(
        f"Deletion error: user={request.user.username}, "
        f"entity=Patient, id={pk}, error={str(e)}"   # ← redundant with logger.exception
    )
    return JsonResponse({
        "success": False,
        "error": "Server error",
        "message": f"An error occurred during deletion: {str(e)}"  # ← LEAKS str(e)
    }, status=500)
```

```python
# CORRECT — generic browser message, full detail in server logs only
except Exception as e:
    logger.exception(                          # ← captures full traceback automatically
        f"Deletion error: user={request.user.username}, "
        f"entity=Patient, id={pk}"             # ← removed error={str(e)} (now redundant)
    )
    return JsonResponse({
        "success": False,
        "error": "Server error",
        "message": "An unexpected error occurred. Please try again."  # ← generic, safe
    }, status=500)
```

**Two changes per view:**
1. `logger.error(...)` → `logger.exception(...)` and remove `error={str(e)}` from log message string
2. `f"An error occurred during deletion: {str(e)}"` → `"An unexpected error occurred. Please try again."`

### Exact Locations in `patients/views.py`

| View | Function | Except block starts |
|------|----------|---------------------|
| `patient_delete` | line 488 | ~line 585 |
| `assessment_delete` | line 1093 | ~line 1183 |
| `bookmark_delete` | line 1624 | ~line 1712 |
| `attachment_delete` | line 2200 | ~line 2297 |
| `cdic_assessment_delete` | line 2607 | ~line 2697 |
| `hine_assessment_delete` | line 2987 | ~line 3077 |
| `da_assessment_delete` | line 3408 | ~line 3498 |
| `gpa_delete` | line 3717 | ~line 3807 |

Use grep to confirm: `grep -n "An error occurred during deletion" patients/views.py` — should find exactly 8 matches before the fix, 0 after.

### Why `logger.exception` vs `logger.error`

`logger.exception(msg)` automatically calls `logger.error(msg, exc_info=True)` — it logs the full Python traceback, exception type, and `str(e)` to the server log. This satisfies the AC requirement for full server-side logging without any manual `str(e)` extraction.

After the fix, the server log will contain the full stack trace; the browser response will only receive the generic string.

### Module Logger Already Present

The `logger` is already defined at module level in `patients/views.py` (near top):

```python
import logging
logger = logging.getLogger(__name__)
```

No new imports needed.

### No Other Files Need Changing

This is a pure `patients/views.py` change. 8 tiny two-line edits. No templates, no models, no URLs, no migrations.

### Testing Approach

Use `unittest.mock.patch` to make `Patient.delete()` raise a predictable exception during a DELETE request, then assert the JSON response contains only the generic message.

```python
# patients/tests/test_views.py
import json
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from patients.models import Patient

User = get_user_model()

@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class DeleteEndpointErrorSanitizationTest(TestCase):
    """AC#1, #3, #5 — delete error responses must not leak str(e)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testdeleter',
            password='testpass123',
            email='deleter@example.com',
            is_staff=True,
            is_superuser=True   # superuser to pass permission checks
        )
        self.client.force_login(self.user)
        self.patient = Patient.objects.create(
            bht='BHTDEL001',
            baby_name='Delete Test Baby',
            mother_name='Delete Test Mother',
            dob_tob=timezone.now(),
            gender='Male',
            pog_wks=38,
            pog_days=0,
            birth_weight=3000,
            ofc=33,
            mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711111111',
            added_by=self.user,
        )

    def test_patient_delete_error_returns_generic_message(self):
        """patient_delete 500 must return generic message, not str(e)."""
        secret_detail = "DB_schema_leak_XYZ"
        url = reverse('patient-delete', kwargs={'pk': self.patient.id})
        payload = json.dumps({'password': 'testpass123'})

        with patch.object(Patient, 'delete', side_effect=Exception(secret_detail)):
            response = self.client.delete(
                url,
                data=payload,
                content_type='application/json'
            )

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(data['message'], "An unexpected error occurred. Please try again.")
        self.assertNotIn(secret_detail, response.content.decode())
        self.assertNotIn(secret_detail, data.get('message', ''))
        self.assertNotIn(secret_detail, data.get('error', ''))
```

**Key testing notes from Story 1.1:**
- Always use `@override_settings(STORAGES=...)` decorator to bypass whitenoise staticfiles manifest errors
- Patient model required fields: `bht`, `baby_name`, `mother_name`, `dob_tob`, `gender` ('Male'/'Female' not 'M'/'F'), `pog_wks`, `pog_days`, `birth_weight`, `ofc`, `mo_delivery` (full string like `'Normal vaginal delivery (NVD)'`), `tp_mobile`, `added_by`
- Use `force_login(user)` not `login(username, password)` in tests
- Need `is_superuser=True` to pass `has_delete_permission()` in delete views
- The test user password must match what you pass in the JSON payload

### URL Name Reference

The `patient-delete` URL name must be confirmed in `patients/urls.py`. Check with:
```bash
grep -n "patient.delete\|patient_delete" patients/urls.py
```

### Decorator Order Note

The existing delete views have mixed decorator ordering (some have `@ratelimit` before `@login_required`, some don't have `@ratelimit` at all). **Do NOT change decorators** in this story — that is Story 2.4's job. Only fix the `except` blocks.

### Existing `error_handlers.py` — Do NOT Use Here

`ndas/custom_codes/error_handlers.py` has `handle_view_errors` and `log_and_suppress` decorators. These are for HTML-rendering views that redirect on error. The delete views return `JsonResponse`, so they manage their own `try/except` blocks — do not refactor to use `handle_view_errors` in this story.

### Project Structure Notes

- Only file changed: `patients/views.py`
- Test file updated: `patients/tests/test_views.py`
- No migrations, no new imports, no template changes

### References

- [Source: _bmad-output/planning-artifacts/epic-2-security.md#Story-2.1]
- [Source: docs/code-audit-adversarial-review.md#SEC-01]
- [Source: patients/views.py:585–594 — patient_delete except block]
- [Source: patients/views.py:1183–1192 — assessment_delete except block]
- [Source: patients/views.py:1712–1721 — bookmark_delete except block]
- [Source: patients/views.py:2297–2306 — attachment_delete except block]
- [Source: patients/views.py:2697–2706 — cdic_assessment_delete except block]
- [Source: patients/views.py:3077–3086 — hine_assessment_delete except block]
- [Source: patients/views.py:3498–3507 — da_assessment_delete except block]
- [Source: patients/views.py:3807–3816 — gpa_delete except block]
- [Source: ndas/custom_codes/error_handlers.py — existing error handling (HTML views only)]
- [Source: _bmad-output/implementation-artifacts/1-1-fix-method-reference-bug-in-patient-view.md — test infrastructure patterns]
- [Source: CLAUDE.md#View Pattern]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — all tasks applied cleanly.

### Completion Notes List

- URL name for patient delete is `delete-patient` (not `patient-delete`) per `patients/urls.py:31`
- `logger.exception()` captures traceback automatically — `str(e)` removed from both log message string and JSON response body
- Pre-existing test failures (`test_validators` ImportError, `DashboardTestCase` staticfiles manifest) are unrelated to this story
- All 8 delete views updated; 2 new passing tests added to `patients/tests/test_views.py`

### File List

- `patients/views.py` — 8 except blocks updated (Tasks 1–8)
- `patients/tests/test_views.py` — `DeleteEndpointErrorSanitizationTest` class added (Task 9)
