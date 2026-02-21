# Story 4.2: Replace Raw `.objects.get()` Calls with `get_object_or_404()`

Status: done

## Story

As a developer maintaining the NDAS codebase,
I want raw `.objects.get()` calls replaced with `get_object_or_404()` where appropriate,
so that requests for non-existent records return a proper 404 response instead of an unhandled 500 error.

## Acceptance Criteria

1. `GMAssessment.objects.get(video_file=pk)` at line 1071 (`assessment_edit_by_fileid`) replaced with `get_object_or_404(GMAssessment, video_file=pk)`.
2. `Bookmark.objects.get(id=pk)` at line 1618 (`bookmark_view`) replaced with `get_object_or_404(Bookmark, id=pk)`.
3. `CustomUser.objects.get(username=username)` at line 1726 (`bookmark_manager_user`) replaced with `get_object_or_404(CustomUser, username=username)`.
4. `Help.objects.get(id=pk)` at line 1432 (`help_article`) — already in a try/except for `Help.DoesNotExist` — replaced with `get_object_or_404(Help, id=pk)` and the try/except removed.
5. `HINEAssessment.objects.get(pk=hine_id)` at line 2762 (`hine_assessment_edit`) — already in a try/except — replaced with `get_object_or_404(HINEAssessment, pk=hine_id)` and the try/except structure reviewed.
6. The 3 search-view `.objects.get()` calls (lines 709, 726, 743) for patient lookup (BHT, PIN, NNC) **remain as try/except** — they show a search-specific "not found" UI, not a 404 page. These are correct as-is.
7. Any additional `.objects.get()` calls found during implementation (lines 2211, 3025 per audit) are audited and fixed with the same approach.
8. Accessing a non-existent record via direct URL returns 404, not 500.
9. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Fix line 1080 — `assessment_edit_by_fileid` (AC: #1)
  - [x] `patients/views.py:1080` — `GMAssessment.objects.get(video_file=pk)` → `get_object_or_404(GMAssessment, video_file=pk)`. AC #1 satisfied.
- [x] Task 2: Fix line 1618 — `bookmark_view` (AC: #2)
  - [x] Already fixed by Story 2-7 — skipped. AC #2 already satisfied.
- [x] Task 3: Fix line 1591 — `bookmark_manager_user` (AC: #3)
  - [x] `patients/views.py:1591` — `CustomUser.objects.get(username=username)` → `get_object_or_404(CustomUser, username=username)`. AC #3 satisfied.
- [x] Task 4: Fix line 1295 — `help_article` (AC: #4)
  - [x] `patients/views.py:1295–1299` — replaced try/except block with `article = get_object_or_404(Help, id=pk)` and removed the except clause. AC #4 satisfied.
- [x] Task 5: Fix line 2627 — `hine_assessment_edit` (AC: #5)
  - [x] `patients/views.py:2626–2631` — replaced try/except with `shr = get_object_or_404(HINEAssessment, pk=hine_id)` + `sp = shr.patient`, removed DoesNotExist except clause. AC #5 satisfied.
- [x] Task 6: Audit additional occurrences (AC: #7)
  - [x] Grepped `patients/views.py` for `\.objects\.get(` — found 7 total. 4 fixed above, 3 are search-view BHT/PIN/NNC lookups (lines 718, 735, 752) — left unchanged per AC #6. No additional occurrences at lines ~2211 or ~3025. AC #7 satisfied.
- [x] Task 7: Leave search-view get() calls unchanged (AC: #6)
  - [x] Confirmed lines 718, 735, 752 (Patient BHT/PIN/NNC lookup) remain as try/except with existing not-found UI. AC #6 satisfied.
- [x] Task 8: Verify (AC: #8, #9)
  - [x] System check clean. No new test failures introduced — all 20 errors pre-existing (staticfiles manifest, import error in test_validators, mock delete tests). AC #8 and #9 satisfied.

## Dev Notes

### Current Dangerous Bare `.objects.get()` Calls (No try/except)

```python
# Line 1071 — assessment_edit_by_fileid — bare, unprotected
assmnt = GMAssessment.objects.get(video_file=pk)

# Line 1618 — bookmark_view — bare, unprotected
bookmark = Bookmark.objects.get(id=pk)

# Line 1726 — bookmark_manager_user — bare, unprotected
user = CustomUser.objects.get(username=username)
```

Any of these raise an unhandled `ObjectDoesNotExist` on a bad URL, producing a 500 error in production.

### Current Guarded Calls (Already in try/except)

```python
# Lines 709, 726, 743 — search_results — KEEP AS try/except
try:
    patient = Patient.objects.get(bht=search_text)
    ...
except Patient.DoesNotExist:
    messages.warning(request, f"No patient found with BHT: {search_text}")
    return render(request, "patients/search_notfound.html", ...)

# Line 1432 — help_article — can convert to get_object_or_404
try:
    article = Help.objects.get(id=pk)
except Help.DoesNotExist:
    messages.error(request, "Help article not found.")
    ...

# Line 2762 — hine_assessment_edit — can convert to get_object_or_404
try:
    shr = HINEAssessment.objects.get(pk=hine_id)
    sp = shr.patient
except HINEAssessment.DoesNotExist:
    ...
```

### Why Search Views Stay as try/except

The patient search views (`search_results`) use `.objects.get()` inside a try/except that specifically renders a "not found" search result template. Using `get_object_or_404()` would instead render Django's generic 404 page, which breaks the intended UX (search-specific "no patient found" message). These are correct as-is.

### `get_object_or_404` Already Imported

```python
# patients/views.py:1 — already present
from django.shortcuts import redirect, render, get_object_or_404
```

No new imports needed.

### No Migration Required

View function changes only. No models, templates, URLs, or migrations changed.

### Project Structure Notes

- File changed: `patients/views.py` — lines 1071, 1432–1434, 1618, 1726, 2760–2770, and any others found in Task 6
- No other files changed

### References

- [Source: _bmad-output/planning-artifacts/epic-4-code-quality.md#Story-4.2]
- [Source: docs/code-audit-adversarial-review.md#BP-01]
- [Source: patients/views.py:1071,1432,1618,1726,2762 — raw .objects.get() calls]
- [Source: patients/views.py:709,726,743 — search-flow try/except (leave unchanged)]
- [Source: CLAUDE.md#View Pattern — "Use get_object_or_404() not .objects.get()"]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Tasks 1–8 complete: Fixed 4 bare/guarded `.objects.get()` calls in `patients/views.py`. `assessment_edit_by_fileid` (line 1080) and `bookmark_manager_user` (line 1591) were bare unprotected calls — replaced with `get_object_or_404()`. `help_article` (line 1295) and `hine_assessment_edit` (line 2627) had try/except — replaced with `get_object_or_404()` and except clauses removed. `bookmark_view` already fixed by Story 2-7 — skipped. 3 search-view `.objects.get()` calls (Patient BHT/PIN/NNC, lines 718/735/752) correctly left as try/except per AC #6. Full audit confirmed no other occurrences. System check clean. No new test failures. AC #1–9 satisfied.

### File List

patients/views.py

## Change Log

- 2026-02-20: Implemented Story 4.2 — replaced raw `.objects.get()` calls with `get_object_or_404()` in `patients/views.py`. Fixed 4 call sites: `assessment_edit_by_fileid` (bare), `bookmark_manager_user` (bare), `help_article` (try/except converted), `hine_assessment_edit` (try/except converted). Search-view BHT/PIN/NNC lookups left unchanged. `bookmark_view` already fixed by Story 2-7.
