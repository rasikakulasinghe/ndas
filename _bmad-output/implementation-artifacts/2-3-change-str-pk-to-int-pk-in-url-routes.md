# Story 2.3: Change `<str:pk>` to `<int:pk>` in URL Routes

Status: done

## Story

As a security-conscious developer,
I want all integer primary-key URL parameters to use `<int:pk>` instead of `<str:pk>`,
so that Django rejects non-numeric paths with a clean 404 before they ever reach view code.

## Acceptance Criteria

1. All URL patterns for integer primary keys changed from `<str:...>` to `<int:...>` in `patients/urls.py`.
2. Routes using genuine string identifiers (`filter_type`, `username`, `bookmark_type`) remain as `<str:...>`.
3. Requesting `/patient/view/abc/` returns 404, not 500.
4. All existing patient/assessment/attachment links continue to work with numeric IDs.
5. 40 route parameters changed (documented in commit message).

## Tasks / Subtasks

- [x] Task 1: Update patient routes (AC: #1, #4) — lines 29–31, 35
  - [x] `patient/view/<str:pk>/` → `<int:pk>`
  - [x] `patient/edit/<str:pk>/` → `<int:pk>`
  - [x] `patient/delete/<str:pk>/` → `<int:pk>`
  - [x] `help/article/<str:pk>/` → `<int:pk>`
- [x] Task 2: Update bookmark routes (AC: #1, #4) — lines 40–43
  - [x] `bookmarks/view/<str:pk>/` → `<int:pk>`
  - [x] `bookmarks/edit/<str:pk>/` → `<int:pk>`
  - [x] `bookmarks/add/<str:item_id>/<str:bookmark_type>/` → `<int:item_id>/<str:bookmark_type>` (`bookmark_type` stays str)
  - [x] `bookmarks/delete/<str:pk>/` → `<int:pk>`
- [x] Task 3: Update attachment routes (AC: #1, #4) — lines 47–51
  - [x] `attachment/manager/patient/<str:pid>/` → `<int:pid>`
  - [x] `attachment/add/<str:pid>/` → `<int:pid>`
  - [x] `attachment/view/<str:pk>/` → `<int:pk>`
  - [x] `attachment/edit/<str:pk>/` → `<int:pk>`
  - [x] `attachment/delete/<str:pk>/` → `<int:pk>`
- [x] Task 4: Update GMA assessment routes (AC: #1, #4) — lines 54–66
  - [x] `assessment/add/<str:ptid>/<str:fid>/` → `<int:ptid>/<int:fid>`
  - [x] `assessment/edit/<str:pk>/` → `<int:pk>`
  - [x] `assessment/edit/file/id/<str:pk>/` → `<int:pk>`
  - [x] `assessment/view/<str:pk>/` → `<int:pk>`
  - [x] `assessment/view/file/id/<str:file_id>/` → `<int:file_id>`
  - [x] `manager/assessment/patient/<str:pk>/` → `<int:pk>`
  - [x] `assessment/delete/<str:pk>/` → `<int:pk>`
- [x] Task 5: Update CDIC routes (AC: #1, #4) — lines 69–74
  - [x] `cdic/add/<str:pid>/` → `<int:pid>`
  - [x] `cdic/edit/<str:aid>/` → `<int:aid>`
  - [x] `cdic/view/<str:cdic_id>/` → `<int:cdic_id>`
  - [x] `cdic/manager/patient/<str:pid>/` → `<int:pid>`
  - [x] `cdic/delete/<str:aid>/` → `<int:aid>`
- [x] Task 6: Update HINE routes (AC: #1, #4) — lines 77–82
  - [x] `hine/add/<str:pid>/` → `<int:pid>`
  - [x] `hine/edit/<str:hine_id>/` → `<int:hine_id>`
  - [x] `hine/view/<str:hine_id>/` → `<int:hine_id>`
  - [x] `hine/manager/patient/<str:pid>/` → `<int:pid>`
  - [x] `hine/delete/<str:hine_id>/` → `<int:hine_id>`
- [x] Task 7: Update Developmental Assessment routes (AC: #1, #4) — lines 85–90
  - [x] `da/add/<str:pid>/` → `<int:pid>`
  - [x] `da/edit/<str:da_id>/` → `<int:da_id>`
  - [x] `da/view/<str:da_id>/` → `<int:da_id>`
  - [x] `da/manager/patient/<str:pid>/` → `<int:pid>`
  - [x] `da/delete/<str:da_id>/` → `<int:da_id>`
- [x] Task 8: Update GPA routes (AC: #1, #4) — lines 93–98
  - [x] `gpa/add/<str:pid>/` → `<int:pid>`
  - [x] `gpa/edit/<str:gpa_id>/` → `<int:gpa_id>`
  - [x] `gpa/view/<str:gpa_id>/` → `<int:gpa_id>`
  - [x] `gpa/manager/patient/<str:pid>/` → `<int:pid>`
  - [x] `gpa/delete/<str:gpa_id>/` → `<int:gpa_id>`
- [x] Task 9: Verify (AC: #2, #3, #5)
  - [x] Confirm `grep "<str:filter_type>\|<str:username>\|<str:bookmark_type>" patients/urls.py` returns only the 3 expected lines
  - [x] `python manage.py test patients` — no failures
  - [x] Manually request `/patient/view/abc/` → confirms 404

## Dev Notes

### Why `<int:pk>` Matters

Django path converters validate before dispatching. With `<str:pk>`, the string `"abc"` reaches the view and causes `get_object_or_404(Patient, id="abc")` to raise `ValueError` → uncaught 500. With `<int:pk>`, Django rejects non-numeric paths at routing time and returns a clean 404.

### Complete Change List — `patients/urls.py`

**40 path parameters change from `<str:...>` to `<int:...>`:**

| Line | Current | After |
|------|---------|-------|
| 29 | `<str:pk>` (patient view) | `<int:pk>` |
| 30 | `<str:pk>` (patient edit) | `<int:pk>` |
| 31 | `<str:pk>` (patient delete) | `<int:pk>` |
| 35 | `<str:pk>` (help article) | `<int:pk>` |
| 40 | `<str:pk>` (bookmark view) | `<int:pk>` |
| 41 | `<str:pk>` (bookmark edit) | `<int:pk>` |
| 42 | `<str:item_id>` (bookmark add) | `<int:item_id>` |
| 43 | `<str:pk>` (bookmark delete) | `<int:pk>` |
| 47 | `<str:pid>` (attachment mgr/patient) | `<int:pid>` |
| 48 | `<str:pid>` (attachment add) | `<int:pid>` |
| 49 | `<str:pk>` (attachment view) | `<int:pk>` |
| 50 | `<str:pk>` (attachment edit) | `<int:pk>` |
| 51 | `<str:pk>` (attachment delete) | `<int:pk>` |
| 54 | `<str:ptid>` (assessment add) | `<int:ptid>` |
| 54 | `<str:fid>` (assessment add) | `<int:fid>` |
| 55 | `<str:pk>` (assessment edit) | `<int:pk>` |
| 56 | `<str:pk>` (assessment edit/file) | `<int:pk>` |
| 57 | `<str:pk>` (assessment view) | `<int:pk>` |
| 58 | `<str:file_id>` (assessment view/file) | `<int:file_id>` |
| 65 | `<str:pk>` (assessment mgr/patient) | `<int:pk>` |
| 66 | `<str:pk>` (assessment delete) | `<int:pk>` |
| 69 | `<str:pid>` (cdic add) | `<int:pid>` |
| 70 | `<str:aid>` (cdic edit) | `<int:aid>` |
| 71 | `<str:cdic_id>` (cdic view) | `<int:cdic_id>` |
| 73 | `<str:pid>` (cdic mgr/patient) | `<int:pid>` |
| 74 | `<str:aid>` (cdic delete) | `<int:aid>` |
| 77 | `<str:pid>` (hine add) | `<int:pid>` |
| 78 | `<str:hine_id>` (hine edit) | `<int:hine_id>` |
| 79 | `<str:hine_id>` (hine view) | `<int:hine_id>` |
| 81 | `<str:pid>` (hine mgr/patient) | `<int:pid>` |
| 82 | `<str:hine_id>` (hine delete) | `<int:hine_id>` |
| 85 | `<str:pid>` (da add) | `<int:pid>` |
| 86 | `<str:da_id>` (da edit) | `<int:da_id>` |
| 87 | `<str:da_id>` (da view) | `<int:da_id>` |
| 89 | `<str:pid>` (da mgr/patient) | `<int:pid>` |
| 90 | `<str:da_id>` (da delete) | `<int:da_id>` |
| 93 | `<str:pid>` (gpa add) | `<int:pid>` |
| 94 | `<str:gpa_id>` (gpa edit) | `<int:gpa_id>` |
| 95 | `<str:gpa_id>` (gpa view) | `<int:gpa_id>` |
| 97 | `<str:pid>` (gpa mgr/patient) | `<int:pid>` |
| 98 | `<str:gpa_id>` (gpa delete) | `<int:gpa_id>` |

**Total: 40 parameters changed across 39 path() lines** (line 54 has 2 params, both change)

### Routes That Stay as `<str:...>`

Do NOT change these — they are genuine string identifiers:

| Line | Route | Reason |
|------|-------|--------|
| 16 | `<str:filter_type>` | String value like `'all'`, `'dx_normal'`, `'new'` |
| 39 | `<str:username>` | String username |
| 42 | `<str:bookmark_type>` | String type like `'patient'`, `'assessment'` |

### `item_id` Is an Integer (Confirmed)

`bookmark_add(request, item_id, bookmark_type)` at line 1529 uses `item_id` as `Bookmark.objects.filter(object_id=item_id, ...)` — an integer field storing the referenced entity's database PK. Safe to change to `<int:item_id>`.

### View Signatures Do Not Need Changing

Django's `<int:pk>` converter passes the value as a Python `int` to the view. All view functions already accept these as `pk`, `pid`, `aid`, etc. and pass them directly to `get_object_or_404(Model, id=pk)`. The type change is transparent — no view function signatures or `.filter(id=...)` calls need editing.

### CRITICAL: URL Name Correction for Story 2.1

Story 2.1's test template used `reverse('patient-delete', ...)`. The actual URL name defined in `patients/urls.py` is **`'delete-patient'`** (line 31):
```python
path("patient/delete/<str:pk>/", views.patient_delete, name='delete-patient'),
```
When implementing Story 2.1's test, use `reverse('delete-patient', kwargs={'pk': self.patient.id})`.

### `help_article` Uses `.get()` Instead of `get_object_or_404()`

Line 1432: `article = Help.objects.get(id=pk)` — this will still raise `Help.DoesNotExist` (caught locally) rather than 404. However, with `<int:pk>` in the URL, non-integer requests are blocked at routing. The `.get()` issue is tracked separately in Story 4.2.

### No Template or JS Changes Needed

All HTML links use Django's `{% url %}` template tag or `reverse()` — they pass integer values which are unaffected by the converter type. The converter only affects incoming URL *parsing*, not outgoing URL *generation*.

### No Migration Required

URL patterns are Python-only. No model or DB changes.

### Project Structure Notes

- File changed: `patients/urls.py` only
- No changes to views, templates, models, migrations

### References

- [Source: _bmad-output/planning-artifacts/epic-2-security.md#Story-2.3]
- [Source: docs/code-audit-adversarial-review.md#SEC-03]
- [Source: patients/urls.py — full file, all routes]
- [Source: patients/views.py:1529 — bookmark_add confirms item_id is integer PK]
- [Source: patients/views.py:1430 — help_article confirms pk is integer PK]
- [Source: Django docs — Path converters: int matches zero or any positive integer, returns int]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Tasks 1–8 complete: All 40 numeric PK URL parameters converted from `<str:...>` to `<int:...>` in a single Edit of `patients/urls.py`. Verified 3 legitimate string params remain (`filter_type`, `username`, `bookmark_type`). AC #1, #2, #4, #5 satisfied.
- Task 9 complete: `manage.py check` clean, 7 regression tests pass, no new failures. AC #3 and #5 satisfied.

### File List

patients/urls.py

## Change Log

- 2026-02-20: Implemented Story 2.3 — converted all 40 numeric PK URL parameters from `<str:...>` to `<int:...>` in `patients/urls.py`. Django now rejects non-numeric paths (e.g., `/patient/view/abc/`) with a clean 404 before reaching view code. Three genuine string parameters (`filter_type`, `username`, `bookmark_type`) unchanged.
