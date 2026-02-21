# Story 2.7: Fix Unhandled `.objects.get()` Producing 500 Errors

Status: done

## Story

As a security-conscious developer,
I want views that look up objects by PK to use `get_object_or_404()` instead of raw `.objects.get()`,
so that invalid IDs return a clean 404 instead of an unhandled `ObjectDoesNotExist` exception (500).

## Acceptance Criteria

1. `attachment_delete_confirm` no longer exists in the codebase — confirmed removed (no code change needed here).
2. `bookmark_view` updated: `Bookmark.objects.get(id=pk)` replaced with `get_object_or_404(Bookmark, id=pk)`.
3. Requesting `/bookmarks/view/99999/` returns 404, not 500.
4. The deprecation docstring on `bookmark_view` (if any) remains in place.
5. `help_article`'s existing `try/except Help.DoesNotExist` is left as-is — no 500 is currently produced there.

## Tasks / Subtasks

- [x] Task 1: Verify `attachment_delete_confirm` is gone (AC: #1)
  - [x] `grep -n "attachment_delete_confirm" patients/views.py patients/urls.py` — confirm zero results
  - [x] No code change needed
- [x] Task 2: Fix `bookmark_view` (AC: #2, #3) — `patients/views.py:1616`
  - [x] Change `Bookmark.objects.get(id=pk)` → `get_object_or_404(Bookmark, id=pk)`
  - [x] `get_object_or_404` already imported at top of `patients/views.py`
- [x] Task 3: Verify (AC: #3, #5)
  - [x] `python manage.py test patients` — 3 story-related tests pass; 20 pre-existing failures unchanged

## Dev Notes

### Why the Original Target No Longer Exists

The audit (SEC-07) identified `attachment_delete_confirm` at `patients/views.py:2211`. That view has since been removed from both `patients/views.py` and `patients/urls.py` as part of the delete system refactoring (the unified delete modal replaced it). Verification:

```bash
grep -n "attachment_delete_confirm" patients/views.py patients/urls.py
# Returns nothing — view and URL are gone
```

The URL `/attachment/delete-confirm/99999/` already returns 404 (unregistered route).

### Active Vulnerability: `bookmark_view` at Line 1617

`bookmark_view` has the identical problem SEC-07 described:

```python
# patients/views.py:1616–1619 — CURRENT (broken)
@login_required(login_url="user-login")
def bookmark_view(request, pk):
    bookmark = Bookmark.objects.get(id=pk)   # ← unhandled ObjectDoesNotExist → 500
    return render(request, "bookmark/view.html", {"bookmark": bookmark})
```

With `Story 2.3` changing the URL parameter to `<int:pk>`, non-integer paths will return 404 at routing. But integer IDs that don't exist in the DB still reach the view and trigger the unhandled exception. Fix:

```python
# CORRECT — after fix
@login_required(login_url="user-login")
def bookmark_view(request, pk):
    bookmark = get_object_or_404(Bookmark, id=pk)   # ← returns 404 for missing objects
    return render(request, "bookmark/view.html", {"bookmark": bookmark})
```

**One word change:** `Bookmark.objects.get` → `get_object_or_404(Bookmark,`

### `get_object_or_404` Already Imported

`patients/views.py:34` (approx): `from django.shortcuts import render, redirect, get_object_or_404`

Confirm with: `grep -n "get_object_or_404" patients/views.py | head -3`

No new imports needed.

### `help_article` at Line 1430 — Not a 500 Risk

```python
# patients/views.py:1430–1435
def help_article(request, pk):
    try:
        article = Help.objects.get(id=pk)   # ← caught by except below
    except Help.DoesNotExist:
        messages.error(request, "Help article not found.")
        return redirect("help-home")
```

`Help.DoesNotExist` is explicitly caught — no 500. This pattern is not ideal (Story 4.2 will replace with `get_object_or_404`) but it does not produce 500 errors. Leave it alone in this story.

### No URL Changes Needed

`bookmark_view` is already registered in `patients/urls.py:40`:
```python
path("bookmarks/view/<str:pk>/", views.bookmark_view, name='bookmark-view'),
```
(After Story 2.3, this will be `<int:pk>`.)

### No Migration Required

One-line view change. No model, URL pattern, or template changes.

### Project Structure Notes

- File changed: `patients/views.py:1618` — single word change
- No imports, no templates, no URLs changed

### References

- [Source: _bmad-output/planning-artifacts/epic-2-security.md#Story-2.7]
- [Source: docs/code-audit-adversarial-review.md#SEC-07]
- [Source: patients/views.py:1616–1619 — bookmark_view with unhandled .objects.get()]
- [Source: patients/views.py:1430–1435 — help_article with caught DoesNotExist]
- [Source: patients/urls.py:40 — bookmark-view URL registration]
- [Source: CLAUDE.md#View Pattern — "ALWAYS use get_object_or_404"]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1 complete: Confirmed `attachment_delete_confirm` absent from `patients/views.py` and `patients/urls.py` (0 grep results). View was already removed as part of the unified delete modal refactoring. AC #1 satisfied.
- Task 2 complete: Changed `Bookmark.objects.get(id=pk)` to `get_object_or_404(Bookmark, id=pk)` in `bookmark_view` (`patients/views.py:1616`). `get_object_or_404` already imported. Invalid PK now returns 404 instead of 500. AC #2 and #3 satisfied.
- Task 3 complete: 3 regression tests pass; 20 pre-existing failures (test_validators ImportError, DashboardTestCase/PatientManagerTestCase staticfiles errors) are unchanged. AC #3 and #5 satisfied.

### File List

patients/views.py

## Change Log

- 2026-02-20: Implemented Story 2.7 — changed `Bookmark.objects.get(id=pk)` to `get_object_or_404(Bookmark, id=pk)` in `bookmark_view` in `patients/views.py`. Invalid bookmark IDs now return 404 instead of an unhandled 500. `attachment_delete_confirm` was already removed from the codebase prior to this story.
