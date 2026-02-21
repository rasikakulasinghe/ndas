# Story 2.2: Remove Unused `csrf_exempt` Imports

Status: done

## Story

As a developer maintaining the NDAS codebase,
I want to remove unused `csrf_exempt` imports from all three view files,
so that future developers cannot accidentally assume CSRF exemption is already active and bypass CSRF protection.

## Acceptance Criteria

1. `from django.views.decorators.csrf import csrf_exempt` removed from `patients/views.py` (line 62).
2. `from django.views.decorators.csrf import csrf_exempt` removed from `users/views.py` (line 11).
3. `from django.views.decorators.csrf import csrf_exempt` removed from `video/views.py` (line 13).
4. After removal, `grep -rn "csrf_exempt" patients/views.py users/views.py video/views.py` returns zero results.
5. All existing views in these three files continue to enforce CSRF protection normally — no functional change.
6. Dev server starts without ImportError after the removals.

## Tasks / Subtasks

- [x] Task 1: Remove import from `patients/views.py` (AC: #1, #4)
  - [x] Delete line 62: `from django.views.decorators.csrf import csrf_exempt`
  - [x] Confirm no `@csrf_exempt` or `csrf_exempt(` usage anywhere else in the file
- [x] Task 2: Remove import from `users/views.py` (AC: #2, #4)
  - [x] Delete line 11: `from django.views.decorators.csrf import csrf_exempt`
  - [x] Confirm no `@csrf_exempt` or `csrf_exempt(` usage anywhere else in the file
- [x] Task 3: Remove import from `video/views.py` (AC: #3, #4)
  - [x] Delete line 13: `from django.views.decorators.csrf import csrf_exempt`
  - [x] Confirm no `@csrf_exempt` or `csrf_exempt(` usage anywhere else in the file
- [x] Task 4: Verify and run tests (AC: #5, #6)
  - [x] `python manage.py test patients users video` — no failures from this change
  - [x] `python manage.py runserver` — confirm startup without ImportError

## Dev Notes

### Why These Imports Are Safe to Remove

`csrf_exempt` is imported but **never applied** in any of the three files. Confirmed by grep:

```
grep -n "@csrf_exempt\|csrf_exempt(" patients/views.py users/views.py video/views.py
# Returns nothing — decorator is never used
```

**Historical context (temp_documents/security_audit_summary.md):** `@csrf_exempt` was previously applied to `get_user_activity_api` in `users/views.py:580` but was removed during a past security remediation. The import line was left behind accidentally. The same pattern appears in the other two files.

### Exact Lines to Delete

| File | Line to delete |
|------|----------------|
| `patients/views.py:62` | `from django.views.decorators.csrf import csrf_exempt` |
| `users/views.py:11` | `from django.views.decorators.csrf import csrf_exempt` |
| `video/views.py:13` | `from django.views.decorators.csrf import csrf_exempt` |

### Import Context — Nothing Else on These Lines

Each line is a standalone import — removing it does not affect adjacent imports:

```python
# patients/views.py lines 60-64 (remove line 62 only)
from patients.timeline_utils import get_patient_timeline_events
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt      # ← DELETE THIS LINE
from django.views.decorators.http import require_http_methods, require_GET, require_POST
import pytz, os, logging, subprocess, tempfile

# users/views.py lines 9-13 (remove line 11 only)
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt      # ← DELETE THIS LINE
from django.utils import timezone
from django.utils.decorators import method_decorator

# video/views.py lines 11-15 (remove line 13 only)
from django.http import JsonResponse, HttpResponseForbidden, Http404
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt      # ← DELETE THIS LINE
from django.views.decorators.http import require_http_methods
from django.utils import timezone
```

### CSRF Protection Is Not Affected

Removing an unused import has zero runtime effect. Django's `CsrfViewMiddleware` (position 7 in the middleware stack per CLAUDE.md) enforces CSRF on all views automatically. The `csrf_exempt` decorator is only needed when you deliberately want to bypass it — which no view here should do.

### No Test Required

This is a dead-code removal with no behavior change. The existing test suite (`python manage.py test patients users video`) serves as the regression guard. If any view accidentally depended on the import (impossible for a decorator import), the tests would catch it.

### No Migration Required

No model changes. Pure Python import cleanup.

### Project Structure Notes

- Files changed: `patients/views.py`, `users/views.py`, `video/views.py` — one line deleted from each
- No templates, no models, no URL changes

### References

- [Source: _bmad-output/planning-artifacts/epic-2-security.md#Story-2.2]
- [Source: docs/code-audit-adversarial-review.md#SEC-02]
- [Source: patients/views.py:62 — unused csrf_exempt import]
- [Source: users/views.py:11 — unused csrf_exempt import]
- [Source: video/views.py:13 — unused csrf_exempt import]
- [Source: temp_documents/security_audit_summary.md — historical context for users/views.py removal]
- [Source: CLAUDE.md#Security Architecture — middleware stack, CsrfViewMiddleware at position 7]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Tasks 1-3 complete: Deleted unused `from django.views.decorators.csrf import csrf_exempt` from `patients/views.py`, `users/views.py`, and `video/views.py`. Grep confirmed zero remaining occurrences in all three files. No `@csrf_exempt` usage existed anywhere — import was dead code. AC #1–4 satisfied.
- Task 4 complete: 7 passing tests confirmed no regressions. Zero behavior change (CSRF middleware still active via middleware stack). AC #5 and #6 satisfied.

### File List

patients/views.py
users/views.py
video/views.py

## Change Log

- 2026-02-20: Implemented Story 2.2 — removed unused `csrf_exempt` import from `patients/views.py`, `users/views.py`, and `video/views.py`. Dead-code cleanup, no functional change, no regressions.
