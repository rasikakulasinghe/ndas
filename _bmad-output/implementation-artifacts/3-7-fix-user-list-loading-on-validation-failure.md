# Story 3.7: Fix User List Loading on Validation Failure in `search_results`

Status: done

## Story

As a system administrator,
I want the search view to load the user dropdown list only once per request,
so that validation error paths do not each issue a redundant full-table scan of the `CustomUser` table.

## Acceptance Criteria

1. `CustomUser.objects.all()` called exactly once in `search_results` (`patients/views.py`), immediately after the POST method guard (around line 684).
2. All 6 existing inline `username_list = CustomUser.objects.all()` definitions (lines 689, 697, 702, 836, 845, 855) removed — replaced by the single hoisted assignment.
3. All 6 `return render(request, ..., {"username_list": username_list})` calls remain unchanged and continue to use the hoisted variable.
4. The search page renders correctly and the user dropdown populates on all validation error paths.
5. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Hoist `username_list` to top of view body (AC: #1)
  - [x] Added `username_list = CustomUser.objects.all()` after `pagn = ""` (line 684), before the first validation check. AC #1 satisfied.
- [x] Task 2: Remove 6 inline redefinitions (AC: #2)
  - [x] Removed all 6 `username_list = CustomUser.objects.all()` inline redefinitions at the 6 validation error paths. AC #2 satisfied.
- [x] Task 3: Verify (AC: #3, #4, #5)
  - [x] All `return render(...)` calls continue to reference the hoisted `username_list`. AC #3 and #4 satisfied.
  - [x] System check clean. 6 regression tests pass. AC #5 satisfied.

## Dev Notes

### Current State — `patients/views.py:668–856`

`CustomUser.objects.all()` is called **6 separate times** — once per early-return validation path:

| Line | Trigger path |
|---|---|
| 689 | `combo_record_type` is empty |
| 697 | `combo_pt_param_type` is empty (patient search branch) |
| 702 | `search_text` is empty (patient search branch) |
| 836 | Patient param validation failed (`else` of param type checks) |
| 845 | `combo_user_username` is empty (user search branch) |
| 855 | `combo_record_type` is unrecognised (`else` of record type checks) |

All 6 paths return `render(request, "patients/search.html", {"username_list": username_list})`, meaning every validation failure triggers a full `SELECT * FROM users_customuser` query.

### Required State After Fix — Changed Section

**Add after `pagn = ""`  (line ~684), before the first `if not combo_record_type:` check:**

```python
    # Load user list once — reused across all validation error return paths
    username_list = CustomUser.objects.all()
```

**Then delete the 6 inline `username_list = CustomUser.objects.all()` lines at lines 689, 697, 702, 836, 845, and 855.** The 6 `return render(...)` lines are untouched.

### Example — Before vs After (first validation path)

**Before (lines 687–690):**
```python
    if not combo_record_type:
        messages.error(request, "Please select a record type.")
        username_list = CustomUser.objects.all()   # ← redundant
        return render(request, "patients\search.html", {"username_list": username_list})
```

**After:**
```python
    if not combo_record_type:
        messages.error(request, "Please select a record type.")
        return render(request, "patients\search.html", {"username_list": username_list})
```

Same pattern for all 6 paths.

### Performance Impact

The fix eliminates 5 out of 6 `SELECT * FROM users_customuser` queries per request that hits a validation error. The one remaining query (the hoisted assignment) only executes if the request method is POST — the early `if request.method != "POST": return redirect(...)` guard at line 675 prevents it from running on GET requests.

### `search_start` View Is Out of Scope

`search_start` at `patients/views.py:663` also calls `CustomUser.objects.all()`. This is a separate view function and is not part of this story.

### No New Imports Required

`CustomUser` is already imported in `patients/views.py`.

### No Migration Required

Single-location refactor within one view function. No models, templates, URLs, or migrations changed.

### Project Structure Notes

- File changed: `patients/views.py` — add one line (~684), delete 6 lines (689, 697, 702, 836, 845, 855)
- No other files changed

### References

- [Source: _bmad-output/planning-artifacts/epic-3-performance.md#Story-3.7]
- [Source: docs/code-audit-adversarial-review.md#PERF-07]
- [Source: patients/views.py:668–856 — search_results function]
- [Source: CLAUDE.md#View Pattern]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1 complete: Added hoisted `username_list = CustomUser.objects.all()` after `pagn = ""` in `search_results` (`patients/views.py:684`). AC #1 satisfied.
- Task 2 complete: Removed all 6 inline `username_list = CustomUser.objects.all()` redefinitions from validation error paths. `search_start`'s assignment at line 660 correctly left untouched (out of scope). AC #2 satisfied.
- Task 3 complete: All render calls still use the hoisted variable. System check clean. 6 regression tests pass. AC #3–5 satisfied.

### File List

patients/views.py

## Change Log

- 2026-02-20: Implemented Story 3.7 — hoisted `username_list = CustomUser.objects.all()` to a single assignment in `search_results` in `patients/views.py`. Removed 6 inline redefinitions at validation error return paths. Reduces redundant full-table user queries from 6 to 1 per POST request that fails validation.
