# Story 3.2: Fix Unbounded Bookmark Queryset in Dashboard

Status: done

## Story

As a system administrator,
I want the dashboard to retrieve only the current user's bookmark count efficiently,
so that the dashboard does not hold a full-table queryset object in memory on every request.

## Acceptance Criteria

1. `Bookmark.objects.all()` at `patients/views.py:128` replaced with `Bookmark.objects.filter(owner=request.user).count()`.
2. Context key changed from `"bookmark"` (queryset) to `"bookmark_count"` (integer).
3. Template `templates/patients/index.html:99` updated: `{{ bookmark.count }}` → `{{ bookmark_count }}`.
4. Dashboard bookmark count displays correctly (shows current user's bookmark count).
5. No full-table `Bookmark` queryset exists anywhere in the dashboard code path after the fix.
6. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Replace queryset with count integer (AC: #1, #2, #5)
  - [x] `patients/views.py:127` — changed `bookmark = Bookmark.objects.all()` → `bookmark_count = Bookmark.objects.filter(owner=request.user).count()`
- [x] Task 2: Update context dict (AC: #2)
  - [x] `patients/views.py:188` — changed `"bookmark": bookmark` → `"bookmark_count": bookmark_count`
- [x] Task 3: Update template (AC: #3, #4)
  - [x] `templates/patients/index.html:99` — changed `{{bookmark.count}}` → `{{bookmark_count}}`
- [x] Task 4: Verify (AC: #5, #6)
  - [x] Confirmed `{{bookmark.count}}` is the only usage of the `bookmark` context variable in the template — no other references.
  - [x] 6 tests pass; no new failures. AC #5 and #6 satisfied.

## Dev Notes

### Current State

**`patients/views.py:127–129`**
```python
# Efficient counting for misc items
bookmark = Bookmark.objects.all()    # ← UNBOUNDED: holds reference to full-table queryset
attachments_count = Attachment.objects.count()
```

**`patients/views.py:189–191`** (context dict)
```python
"bookmark": bookmark,
```

**`templates/patients/index.html:99`**
```html
<div class="col"><a href="{% url 'bookmark-manager' %}" style="color:white;">{{bookmark.count}}</a></div>
```

### Required State After Fix

**`patients/views.py:127–129`**
```python
# Efficient counting for misc items
bookmark_count = Bookmark.objects.filter(owner=request.user).count()    # ← integer, user-scoped
attachments_count = Attachment.objects.count()
```

**`patients/views.py:189–191`** (context dict)
```python
"bookmark_count": bookmark_count,
```

**`templates/patients/index.html:99`**
```html
<div class="col"><a href="{% url 'bookmark-manager' %}" style="color:white;">{{bookmark_count}}</a></div>
```

### Why the Current Code Is a Risk (Even Though It Appears to Work)

Django querysets are **lazy** — `Bookmark.objects.all()` does not immediately execute SQL or load records. `{{ bookmark.count }}` in the template triggers a single efficient `SELECT COUNT(*)` SQL query. So the dashboard does NOT currently load all bookmarks into memory.

**However, the unbounded queryset is still a defect because:**
1. Any template addition of `{% for b in bookmark %}` would instantly cause a full-table scan loading all records
2. Passing a queryset instead of an integer for a count-only use is semantically wrong
3. It shows all users' bookmarks rather than the current user's bookmarks (unintended scope)

The fix converts the queryset to a scalar integer, eliminating the risk entirely and narrowing the scope to the current user.

### Important: Bookmark Has NO `patient` ForeignKey

The Epic 3 planning doc suggests `select_related('patient')` — **this is incorrect**. The Bookmark model uses a **generic object reference** pattern:

```python
# patients/models.py — Bookmark model
object_id = models.PositiveIntegerField(...)    # ID of any bookmarked object
bookmark_type = models.CharField(...)           # 'Patient', 'Video', 'GMA', etc.
owner = models.ForeignKey("users.CustomUser", ...)  # The user who owns the bookmark
```

There is **no `patient` FK field** on Bookmark. The `select_related('patient')` hint in the epic planning doc is wrong. The fix uses `.count()` — no `select_related` is needed at all.

### `request.user` Is Guaranteed Available

The `dashboard` view has `@login_required(login_url="user-login")` — `request.user` is always an authenticated `CustomUser` instance when the view body executes. Safe to use in the filter directly.

### Behavioral Change: Total Count → User Count

The current code shows the **total bookmark count** (all users). After the fix, it shows the **current user's bookmark count**. This is the intended behavior per the audit finding: the dashboard should be personalized, not show system-wide totals for user-specific resources like bookmarks.

### Context Key Name Alignment

The context key changes from `"bookmark"` to `"bookmark_count"` to match the naming convention used for other count values in the same dict (`attachments_count`, `users_total_count`, `videos_total_count`, etc.).

### No Other Template References to `bookmark`

Confirmed: `{{ bookmark.count }}` at line 99 is the only usage of the `bookmark` context variable in `templates/patients/index.html`. No other dashboard template partial uses it. Safe to rename.

### No Migration Required

Three-file change: one view line, one context dict line, one template line. No model changes, no new imports needed.

### Project Structure Notes

- `patients/views.py:128` — replace queryset with `.count()` call
- `patients/views.py:190` — rename context key from `"bookmark"` to `"bookmark_count"`
- `templates/patients/index.html:99` — update template variable reference
- No new imports needed — `Bookmark` already imported in `patients/views.py`

### References

- [Source: _bmad-output/planning-artifacts/epic-3-performance.md#Story-3.2]
- [Source: docs/code-audit-adversarial-review.md#PERF-02]
- [Source: patients/views.py:127–199 — dashboard view, bookmark queryset and context]
- [Source: templates/patients/index.html:91–101 — dashboard bookmark count display]
- [Source: patients/models.py — Bookmark model (no patient FK; uses object_id + bookmark_type generic pattern)]
- [Source: CLAUDE.md#View Pattern]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1 complete: Replaced `Bookmark.objects.all()` with `Bookmark.objects.filter(owner=request.user).count()` — now returns an integer scoped to the current user. AC #1, #2, #5 satisfied.
- Task 2 complete: Context key renamed from `"bookmark"` to `"bookmark_count"`. AC #2 satisfied.
- Task 3 complete: Template updated from `{{bookmark.count}}` to `{{bookmark_count}}`. AC #3 and #4 satisfied.
- Task 4 complete: No other template references to `bookmark` context variable. 6 regression tests pass. AC #5 and #6 satisfied.

### File List

patients/views.py
templates/patients/index.html

## Change Log

- 2026-02-20: Implemented Story 3.2 — replaced `Bookmark.objects.all()` queryset with `Bookmark.objects.filter(owner=request.user).count()` integer in dashboard view. Context key renamed `"bookmark"` → `"bookmark_count"`. Template updated accordingly. Dashboard now shows current user's bookmark count instead of system-wide total.
