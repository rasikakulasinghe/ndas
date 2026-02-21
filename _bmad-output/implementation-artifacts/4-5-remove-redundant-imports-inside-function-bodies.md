# Story 4.5: Remove Redundant Imports Inside Function Bodies

Status: done

## Story

As a developer maintaining the NDAS codebase,
I want redundant imports inside function bodies removed,
so that the code is clean, import intent is clear, and Python does not re-execute the import machinery on every function call.

## Acceptance Criteria

1. `from django.http import JsonResponse` inside `assessment_add` (line ~863) removed — `JsonResponse` is already imported at module level (line 65).
2. `from django.core.exceptions import ValidationError` inside `assessment_add` (line ~864) removed — `ValidationError` is already imported at module level (via `from django.core.exceptions import ObjectDoesNotExist`... wait — verify `ValidationError` is at module level).
3. `import logging` inside `assessment_add` (line ~865) removed — `logging` is already imported at module level (line 64).
4. `from datetime import datetime` inside function bodies at lines ~1817, ~1828, ~1936, ~1947 evaluated — if the module-level `from datetime import datetime` (line 61) is removed by Story 4.1, these local imports become the canonical ones and should remain; if Story 4.1 is NOT implemented, these local imports are redundant to the module-level one and may be removed.
5. All other function-body import patterns (`import logging` at line ~2080) removed (see also Story 4.4 for the `logger = ...` companion line).
6. No `NameError` after removal — all names continue to resolve from module-level imports.
7. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Verify `ValidationError` module-level import status (AC: #2)
  - [x] Grepped: only `ObjectDoesNotExist` was at module level. Added `ValidationError` to module-level import: `from django.core.exceptions import ObjectDoesNotExist, ValidationError`. AC #2 satisfied.
- [x] Task 2: Remove 3 in-function imports from `assessment_add` (AC: #1, #2, #3)
  - [x] Removed `from django.http import JsonResponse`, `from django.core.exceptions import ValidationError`, `import logging` from `assessment_add` function body. `logger = ...` was already removed by Story 4.4. AC #1, #2, #3 satisfied.
- [x] Task 3: Remove `import logging` from `assessment_view` and `assessment_view_by_fileid` (AC: #5)
  - [x] Story 4.4 already removed `import logging` + `logger = ...` from the attachment view except block. Removed remaining `import logging` from `assessment_view` and `assessment_view_by_fileid`. AC #5 satisfied.
- [x] Task 4: Evaluate `from datetime import datetime` local imports (AC: #4)
  - [x] Story 4.1 already removed the module-level `from datetime import datetime`. Local imports at the 4 call sites are now the canonical source — left unchanged. AC #4 satisfied.
- [x] Task 5: Verify (AC: #6, #7)
  - [x] Grep confirms zero indented `import logging`, zero in-function `JsonResponse`/`ValidationError` imports. System check clean. 31 tests, same 20 pre-existing errors — no new failures. AC #6 and #7 satisfied.

## Dev Notes

### Current State — `assessment_add` Lines 860–867

```python
@login_required(login_url="user-login")
def assessment_add(request, ptid, fid):
    """Enhanced assessment creation with proper validation and error handling"""
    from django.http import JsonResponse           # ← redundant (line 65 already imports this)
    from django.core.exceptions import ValidationError  # ← redundant if at module level
    import logging                                 # ← redundant (line 64 already imports this)

    logger = logging.getLogger(__name__)           # ← removed by Story 4.4
```

### Module-Level Imports That Make the In-Function Ones Redundant

```python
# patients/views.py:64 — already present
import pytz, os, logging, subprocess, tempfile

# patients/views.py:65 — already present
from django.http import JsonResponse

# patients/views.py:68 — already present (ObjectDoesNotExist)
from django.core.exceptions import ObjectDoesNotExist
```

**Verify:** `ValidationError` may not be at module level (only `ObjectDoesNotExist` is confirmed). If `ValidationError` is missing from module-level imports, add it to line 68:
```python
from django.core.exceptions import ObjectDoesNotExist, ValidationError
```

### Interaction with Story 4.1 and Story 4.4

- Story 4.1 removes `import pytz, subprocess, tempfile` from line 64 — after that edit, `import logging` on line 64 remains intact (`import os, logging`). The in-function `import logging` at line ~865 is therefore still redundant after Story 4.1.
- Story 4.4 removes `logger = logging.getLogger(__name__)` — that story handles the logger assignment. Story 4.5 removes the `import logging` line above it.
- Both stories touch the same 4-line block in `assessment_add`. If implemented together, clean all 4 lines at once.

### No Migration Required

Import-only changes. No models, view logic, templates, or migrations changed.

### Project Structure Notes

- File changed: `patients/views.py` — delete lines ~863–865, line ~2080, potentially add `ValidationError` to line 68
- No other files changed

### References

- [Source: _bmad-output/planning-artifacts/epic-4-code-quality.md#Story-4.5]
- [Source: docs/code-audit-adversarial-review.md#BP-04]
- [Source: patients/views.py:860–868 — assessment_add redundant imports]
- [Source: patients/views.py:2080–2082 — attachment function redundant import]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Tasks 1–5 complete: Added `ValidationError` to module-level `from django.core.exceptions import` line (it was absent). Removed 3 in-function imports from `assessment_add` (`JsonResponse`, `ValidationError`, `logging`). Removed `import logging` from `assessment_view` and `assessment_view_by_fileid` function bodies (Story 4.4 had already removed the `logger = ...` companions). `from datetime import datetime` local imports left as canonical (module-level removed by Story 4.1). System check clean. No new test failures. AC #1–7 satisfied.

### File List

patients/views.py

## Change Log

- 2026-02-20: Implemented Story 4.5 — removed redundant in-function imports from `patients/views.py`. Added `ValidationError` to module-level exceptions import. Removed `from django.http import JsonResponse`, `from django.core.exceptions import ValidationError`, `import logging` from `assessment_add`; `import logging` from `assessment_view` and `assessment_view_by_fileid`. Story 4.1 `datetime` locals left as canonical.
