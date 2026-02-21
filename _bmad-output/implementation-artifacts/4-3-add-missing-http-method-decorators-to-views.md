# Story 4.3: Add Missing HTTP Method Decorators to Views

Status: done

## Story

As a developer maintaining the NDAS codebase,
I want all views to declare their accepted HTTP methods via decorators,
so that wrong-method requests return 405 automatically rather than proceeding to view logic.

## Acceptance Criteria

1. `search_results` view (`patients/views.py:668`): `@require_POST` decorator added; the manual `if request.method != "POST":` guard at line 675 removed.
2. `assessment_edit_by_fileid` view (`patients/views.py:1069`): `@require_http_methods(["GET", "POST"])` and `@handle_view_errors` decorators added.
3. `assessment_manager` (`patients/views.py:1195`): `@require_GET` added if Story 3.5 has NOT already implemented it; skip this step if Story 3.5 is implemented first (it adds `@require_GET` to the unified view).
4. Decorator order for all modified views follows CLAUDE.md: `@handle_view_errors` → `@login_required` → `@require_*` → `@ratelimit`.
5. Sending a wrong HTTP method to any modified view returns 405 Method Not Allowed.
6. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Add `@require_POST` to `search_results`, remove manual method check (AC: #1)
  - [x] Added `@require_POST` between `@login_required` and `@ratelimit` at `patients/views.py:677`. Removed 4-line manual method check (`if request.method != "POST": ...`). No dangling else blocks — remaining code is sequential validation. AC #1 satisfied.
- [x] Task 2: Add decorators to `assessment_edit_by_fileid` (AC: #2)
  - [x] Added `@handle_view_errors(redirect_url='assessment-manager', error_message='Error editing assessment by file')` above `@login_required` at line 1073. Added `@require_http_methods(["GET", "POST"])` between `@login_required` and `@ratelimit` at line 1075. Decorator order: `@handle_view_errors` → `@login_required` → `@require_http_methods` → `@ratelimit`. AC #2 satisfied.
- [x] Task 3: Check `assessment_manager` status (AC: #3)
  - [x] Story 3.5 already implemented — `@require_GET` present at line 1205 on the unified `assessment_manager` view. Skipped. AC #3 satisfied.
- [x] Task 4: Verify decorator order for all modified views (AC: #4)
  - [x] `search_results`: `@login_required` → `@require_POST` → `@ratelimit`. `assessment_edit_by_fileid`: `@handle_view_errors` → `@login_required` → `@require_http_methods` → `@ratelimit`. Both match CLAUDE.md order. AC #4 satisfied.
- [x] Task 5: Verify (AC: #5, #6)
  - [x] System check clean. 31 tests, same 20 pre-existing errors — no new failures. AC #5 and #6 satisfied.

## Dev Notes

### Current State — `search_results` (lines 668–677)

```python
@login_required(login_url="user-login")
def search_results(request):
    """..."""
    # Early validation for POST method
    if request.method != "POST":                                    # ← manual guard, remove this
        messages.warning(request, "Please use the search form.")
        return redirect("search-start")
    ...
```

**After fix:**
```python
@login_required(login_url="user-login")
@require_POST                                                       # ← added decorator
def search_results(request):
    """..."""
    # Remove the manual method check — @require_POST handles it
    ...
```

`@require_POST` is already imported: `from django.views.decorators.http import require_http_methods, require_GET, require_POST`.

### Current State — `assessment_edit_by_fileid` (lines 1069–1071)

```python
@login_required(login_url="user-login")
def assessment_edit_by_fileid(request, pk):
    assmnt = GMAssessment.objects.get(video_file=pk)   # ← also bare .objects.get(), see Story 4.2
```

**After fix:**
```python
@handle_view_errors(redirect_url='assessment-manager', error_message='Error editing assessment by file')
@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
def assessment_edit_by_fileid(request, pk):
```

### Dependency on Story 3.5

If Story 3.5 (unify assessment manager views) is implemented **before** this story, `assessment_manager` is already decorated with `@require_GET`. Task 3 should be skipped to avoid a no-op edit.

If Story 3.5 is **not yet** implemented, add `@require_GET` to `assessment_manager` at line ~1195.

### `handle_view_errors` Already Imported

```python
# patients/views.py:59 — already present
from ndas.custom_codes.error_handlers import handle_view_errors
```

### `require_POST` Already Imported

```python
# patients/views.py:63 — already present
from django.views.decorators.http import require_http_methods, require_GET, require_POST
```

### No Migration Required

Decorator additions only. No models, templates, URLs, or migrations changed.

### Project Structure Notes

- File changed: `patients/views.py` — decorator lines for 2–3 view functions, plus removal of 3-line manual method check
- No other files changed

### References

- [Source: _bmad-output/planning-artifacts/epic-4-code-quality.md#Story-4.3]
- [Source: docs/code-audit-adversarial-review.md#BP-06, #BP-08, #SEC-04]
- [Source: patients/views.py:668–677 — search_results manual method guard]
- [Source: patients/views.py:1069–1071 — assessment_edit_by_fileid missing decorators]
- [Source: CLAUDE.md#View Pattern — decorator order]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Tasks 1–5 complete: Added `@require_POST` to `search_results` and removed manual 4-line method guard. Added `@handle_view_errors` + `@require_http_methods(["GET", "POST"])` to `assessment_edit_by_fileid`. `assessment_manager` already has `@require_GET` from Story 3.5 — skipped. Decorator order matches CLAUDE.md for all modified views. System check clean. No new test failures. AC #1–6 satisfied.

### File List

patients/views.py

## Change Log

- 2026-02-20: Implemented Story 4.3 — added missing HTTP method decorators to `patients/views.py`. Added `@require_POST` to `search_results` and removed redundant manual `if request.method != "POST"` guard. Added `@handle_view_errors` + `@require_http_methods(["GET", "POST"])` to `assessment_edit_by_fileid`. `assessment_manager` `@require_GET` already present from Story 3.5.
