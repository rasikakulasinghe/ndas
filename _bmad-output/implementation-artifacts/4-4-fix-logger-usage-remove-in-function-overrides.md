# Story 4.4: Fix Logger Usage — Remove In-Function Logger Overrides

Status: done

## Story

As a developer maintaining the NDAS codebase,
I want all view functions to use the module-level logger,
so that log messages from all views appear under the consistent `django` logger rather than the per-function `patients.views` logger.

## Acceptance Criteria

1. All 4 in-function `logger = logging.getLogger(...)` assignments removed from `patients/views.py` (lines ~867, ~968, ~1008, ~2081).
2. The `import logging` inside a function body (line ~2080) also removed — `logging` is already imported at module level (line 64).
3. All view functions use the module-level `logger = logging.getLogger("django")` variable (line 75).
4. No existing `logger.info(...)`, `logger.error(...)`, `logger.exception(...)` calls are broken.
5. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Remove in-function logger at line 870 (`assessment_add`) (AC: #1, #3)
  - [x] Removed `logger = logging.getLogger(__name__)` and blank line at line 869–870. Left `import logging` at line 868 for Story 4.5. AC #1 and #3 satisfied.
- [x] Task 2: Remove in-function logger at line 971 (`assessment_view`) (AC: #1, #3)
  - [x] Removed blank + `logger = logging.getLogger(__name__)` at lines 970–971. Left `import logging` at line 969 for Story 4.5. AC #1 and #3 satisfied.
- [x] Task 3: Remove in-function logger at line 1011 (`assessment_view_by_fileid`) (AC: #1, #3)
  - [x] Removed blank + `logger = logging.getLogger(__name__)` at lines 1010–1011. Left `import logging` at line 1009 for Story 4.5. AC #1 and #3 satisfied.
- [x] Task 4: Remove `import logging` + in-function logger in attachment view (formerly ~2080, now line 1938–1939) (AC: #1, #2, #3)
  - [x] Deleted 2-line block: `import logging` + `logger = logging.getLogger(__name__)` inside `except Exception as e:` block. `logger.error(...)` call now uses module-level logger. AC #1, #2, #3 satisfied.
- [x] Task 5: Verify (AC: #4, #5)
  - [x] Grep confirms only `logger = logging.getLogger("django")` at line 71 remains. System check clean. 31 tests, same 20 pre-existing errors — no new failures. AC #4 and #5 satisfied.

## Dev Notes

### Module-Level Logger — Preserved Unchanged

```python
# patients/views.py:74–75 — KEEP UNCHANGED
# Configure logger for patient operations
logger = logging.getLogger("django")
```

All view functions should use this `logger` variable directly.

### In-Function Overrides to Remove

| Line | Location | Override |
|---|---|---|
| ~867 | `assessment_add` | `logger = logging.getLogger(__name__)` |
| ~968 | Unknown view (read to identify) | `logger = logging.getLogger(__name__)` |
| ~1008 | Unknown view (read to identify) | `logger = logging.getLogger(__name__)` |
| ~2080–2081 | Attachment view | `import logging` + `logger = logging.getLogger(__name__)` |

### Why In-Function Overrides Are Harmful

`logging.getLogger("django")` (module level) and `logging.getLogger(__name__)` (which resolves to `logging.getLogger("patients.views")`) are **different loggers** with potentially different handlers, log levels, and formatters. Log messages from functions with the override go to the wrong output destination — they may be filtered, formatted differently, or not appear in the expected log file/sink.

### Note on `assessment_add` (Interaction with Story 4.5)

`assessment_add` has a 3-line in-function import block at lines 863–865:
```python
from django.http import JsonResponse
from django.core.exceptions import ValidationError
import logging
```
Followed immediately by:
```python
logger = logging.getLogger(__name__)
```

Story 4.4 removes the `logger = ...` line (and the `import logging` from this block is also a redundant import to remove — see Story 4.5). Both stories touch the same block. If implemented separately:
- Story 4.4: removes `logger = logging.getLogger(__name__)` at line 867
- Story 4.5: removes `import logging` at line 865 (and other redundant imports)

Either order is safe. The dev can clean all 4 lines at once if both stories are implemented in the same pass.

### No Migration Required

Log configuration changes only. No models, templates, URLs, or migrations changed.

### Project Structure Notes

- File changed: `patients/views.py` — delete `logger = logging.getLogger(__name__)` at lines ~867, ~968, ~1008, and `import logging` + override at lines ~2080–2081
- No other files changed

### References

- [Source: _bmad-output/planning-artifacts/epic-4-code-quality.md#Story-4.4]
- [Source: docs/code-audit-adversarial-review.md#BP-03]
- [Source: patients/views.py:74–75 — module-level logger (keep)]
- [Source: patients/views.py:867,968,1008,2080–2081 — in-function logger overrides (remove)]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Tasks 1–5 complete: Removed 4 in-function `logger = logging.getLogger(__name__)` overrides from `patients/views.py`. `assessment_add` (line 870), `assessment_view` (line 971), `assessment_view_by_fileid` (line 1011) — logger assignment + blank line removed; `import logging` left for Story 4.5. Attachment view except block (line 1938–1939) — both `import logging` and logger assignment removed. All `logger.*` calls now use module-level `logger = logging.getLogger("django")` at line 71. System check clean. No new test failures. AC #1–5 satisfied.

### File List

patients/views.py

## Change Log

- 2026-02-20: Implemented Story 4.4 — removed 4 in-function `logger = logging.getLogger(__name__)` overrides from `patients/views.py` (`assessment_add`, `assessment_view`, `assessment_view_by_fileid`, attachment except block). All view functions now use the module-level `logger = logging.getLogger("django")`.
