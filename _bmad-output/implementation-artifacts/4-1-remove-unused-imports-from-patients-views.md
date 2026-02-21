# Story 4.1: Remove Unused Imports from `patients/views.py`

Status: done

## Story

As a developer maintaining the NDAS codebase,
I want unused imports removed from `patients/views.py`,
so that the import block is clean, load time is reduced, and security-risk imports (`csrf_exempt`, `subprocess`) do not suggest functionality that does not exist.

## Acceptance Criteria

1. `pytz` removed from `import pytz, os, logging, subprocess, tempfile` (line 64) — verify no `pytz.` usage in views.py first.
2. `subprocess` removed from the same import line — verify no `subprocess.` usage in views.py.
3. `tempfile` removed from the same import line — verify no `tempfile.` usage in views.py.
4. `from django.views.decorators.csrf import csrf_exempt` (line 62) removed — confirm no `@csrf_exempt` usage in views.py.
5. `from django.core.files import File` (line 70) removed — confirm no `File(` usage in views.py.
6. `from django.core.files.storage import FileSystemStorage` (line 71) removed — confirm no `FileSystemStorage` usage in views.py.
7. `from datetime import datetime` (line 61) audited — if `datetime.strptime(...)` calls at lines 1817, 1828, 1936, 1947 already have matching local `from datetime import datetime` imports inside their function bodies, remove the module-level import at line 61; otherwise leave it.
8. No `NameError` or `ImportError` after removal — dev server starts cleanly.
9. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Verify and remove `pytz`, `subprocess`, `tempfile` from line 63 (AC: #1, #2, #3)
  - [x] Confirmed zero usages of `pytz.`, `subprocess.`, `tempfile.` in views.py.
  - [x] Rewrote line as `import os, logging` (removed 3 unused names). AC #1–3 satisfied.
- [x] Task 2: Remove `csrf_exempt` import (AC: #4)
  - [x] `csrf_exempt` was already removed by Story 2.2 — skipped. AC #4 already satisfied.
- [x] Task 3: Remove `File` and `FileSystemStorage` imports (AC: #5, #6)
  - [x] Confirmed zero usages of `File(` and `FileSystemStorage` in views.py.
  - [x] Removed both import lines. AC #5 and #6 satisfied.
- [x] Task 4: Audit `from datetime import datetime` (AC: #7)
  - [x] Confirmed all 4 `datetime.strptime()` call sites (lines 1685, 1696, 1804, 1815) have local `from datetime import datetime` imports immediately above them.
  - [x] Removed module-level `from datetime import datetime` at line 61. AC #7 satisfied.
- [x] Task 5: Verify (AC: #8, #9)
  - [x] System check clean. 7 regression tests pass. AC #8 and #9 satisfied.

## Dev Notes

### Current Imports — `patients/views.py:61–71`

```python
from datetime import datetime                                    # line 61 — audit for usage
from django.views.decorators.csrf import csrf_exempt            # line 62 — unused, remove
from django.views.decorators.http import require_http_methods, require_GET, require_POST
import pytz, os, logging, subprocess, tempfile                  # line 64 — pytz/subprocess/tempfile unused
from django.http import JsonResponse
from django.utils.timezone import localtime, now
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, Count, Exists, OuterRef
from django.core.files import File                              # line 70 — unused, remove
from django.core.files.storage import FileSystemStorage         # line 71 — unused, remove
```

### `datetime` Usage Detail

`datetime.strptime()` is called inside function bodies at lines ~1817, 1828, 1936, 1947. All 4 call sites also have a **local** `from datetime import datetime` import at the top of their respective function bodies. The module-level import at line 61 is therefore redundant — the local imports keep working after line 61 is removed.

### `csrf_exempt` Overlap with Story 2.2

Story 2.2 (`2-2-remove-unused-csrf-exempt-imports`) also removes the `csrf_exempt` import. Implement only once — whichever story runs first handles it; the other skips this step.

### What to Keep on Line 64

After removing `pytz`, `subprocess`, `tempfile`, line 64 becomes:
```python
import os, logging
```
`os` — used for file path operations. `logging` — used for the module-level logger at line 75.

### No Migration Required

Import-only changes. No models, views logic, templates, or URLs changed.

### Project Structure Notes

- File changed: `patients/views.py` — lines 61–71 only
- No other files changed

### References

- [Source: _bmad-output/planning-artifacts/epic-4-code-quality.md#Story-4.1]
- [Source: docs/code-audit-adversarial-review.md#BP-05, #SEC-02]
- [Source: patients/views.py:61–71 — import block]
- [Source: patients/views.py:1817,1828,1936,1947 — datetime local imports inside functions]
- [Source: CLAUDE.md#Quick Reference]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- All tasks complete: Removed `from datetime import datetime` (module-level, covered by 4 local imports), `pytz`, `subprocess`, `tempfile` (from combined import line), `from django.core.files import File`, and `from django.core.files.storage import FileSystemStorage`. `csrf_exempt` was already removed by Story 2.2. `import os, logging` retained. System check clean. 7 regression tests pass. AC #1–9 satisfied.

### File List

patients/views.py

## Change Log

- 2026-02-20: Implemented Story 4.1 — removed unused imports from `patients/views.py`: `datetime` (module-level; function bodies have local imports), `pytz`, `subprocess`, `tempfile`, `File`, `FileSystemStorage`. `csrf_exempt` already removed by Story 2.2.
