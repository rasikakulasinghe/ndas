# Story 2.4: Add Rate Limiting to Missing Mutating Endpoints

Status: done

## Story

As a security-conscious developer,
I want all mutating POST endpoints to have rate limiting,
so that brute-force and abuse attacks on forms and search are blocked.

## Acceptance Criteria

1. `@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)` added to `assessment_add`.
2. `@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)` added to `assessment_edit`.
3. `@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)` added to `assessment_edit_by_fileid`.
4. `@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)` added to `search_results`.
5. `@ratelimit(key='user_or_ip', rate='10/m', block=True)` added to `bookmark_manager`.
6. `@require_GET` added to `assessment_manager`.
7. Decorator order for each view: `@login_required` first, then `@require_GET`/`@require_http_methods` (if any), then `@ratelimit` — per CLAUDE.md standard.
8. No new imports needed — both `ratelimit` (line 34) and `require_GET` (line 63) are already imported in `patients/views.py`.

## Tasks / Subtasks

- [x] Task 1: Add `@ratelimit` to `assessment_add` (AC: #1, #7) — ~line 859
  - [x] Insert `@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)` between `@login_required` and `def assessment_add`
- [x] Task 2: Add `@ratelimit` to `assessment_edit` (AC: #2, #7) — ~line 1043
  - [x] Insert `@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)` between `@login_required` and `def assessment_edit`
- [x] Task 3: Add `@ratelimit` to `assessment_edit_by_fileid` (AC: #3, #7) — ~line 1069
  - [x] Insert `@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)` between `@login_required` and `def assessment_edit_by_fileid`
- [x] Task 4: Add `@ratelimit` to `search_results` (AC: #4, #7) — ~line 668
  - [x] Insert `@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)` between `@login_required` and `def search_results`
- [x] Task 5: Add `@ratelimit` to `bookmark_manager` (AC: #5, #7) — ~line 1443
  - [x] Insert `@ratelimit(key='user_or_ip', rate='10/m', block=True)` between `@login_required` and `def bookmark_manager`
- [x] Task 6: Add `@require_GET` to `assessment_manager` (AC: #6, #7) — ~line 1195
  - [x] Insert `@require_GET` between `@login_required` and `def assessment_manager`
- [x] Task 7: Verify (AC: #7, #8)
  - [x] `python manage.py test patients` — no failures
  - [x] Confirm no new imports added (both decorators already present)

## Dev Notes

### Current State — All 6 Views Have Only `@login_required`

```python
# assessment_add (~line 859) — CURRENT
@login_required(login_url="user-login")
def assessment_add(request, ptid, fid):

# assessment_edit (~line 1043) — CURRENT
@login_required(login_url="user-login")
def assessment_edit(request, pk):

# assessment_edit_by_fileid (~line 1069) — CURRENT
@login_required(login_url="user-login")
def assessment_edit_by_fileid(request, pk):

# search_results (~line 668) — CURRENT
@login_required(login_url="user-login")
def search_results(request):

# bookmark_manager (~line 1443) — CURRENT
@login_required(login_url="user-login")
def bookmark_manager(request):

# assessment_manager (~line 1195) — CURRENT
@login_required(login_url="user-login")
def assessment_manager(request):
```

### Required State After This Story

```python
# assessment_add
@login_required(login_url="user-login")
@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)
def assessment_add(request, ptid, fid):

# assessment_edit
@login_required(login_url="user-login")
@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)
def assessment_edit(request, pk):

# assessment_edit_by_fileid
@login_required(login_url="user-login")
@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)
def assessment_edit_by_fileid(request, pk):

# search_results
@login_required(login_url="user-login")
@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)
def search_results(request):

# bookmark_manager
@login_required(login_url="user-login")
@ratelimit(key='user_or_ip', rate='10/m', block=True)
def bookmark_manager(request):

# assessment_manager
@login_required(login_url="user-login")
@require_GET
def assessment_manager(request):
```

### Why `bookmark_manager` Gets No `method='POST'`

`bookmark_manager` handles both GET (list) and POST (HTMX updates/delete). The ratelimit without `method=` applies to all methods — safer for a manager view that accepts multiple HTTP methods.

### Decorator Execution Order in Django (Critical Understanding)

Django decorators apply bottom-up (innermost first). The stack order determines precedence:

```
@login_required     ← evaluated FIRST (outer) — redirects if not authenticated
@ratelimit          ← evaluated SECOND (inner) — rate limits after auth check
def view():
```

This is intentional: `@login_required` redirects unauthenticated users before they consume rate limit quota. `@ratelimit` then applies to authenticated (or recently-authed-session) users only.

**Story 4.3 note:** When Story 4.3 adds `@require_http_methods(["GET", "POST"])`, it goes between `@login_required` and `@ratelimit`:
```python
@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])   # Story 4.3 will add this
@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)  # this story
def assessment_add(request, ptid, fid):
```
This matches the CLAUDE.md pattern exactly.

### `block=True` Behaviour

With `block=True`, exceeding the rate limit raises `django_ratelimit.exceptions.Ratelimited`, which Django's default error handler converts to a 403 response. Without it, the view would have to check `if request.limited:` manually. Always use `block=True` per project standards.

### No New Imports Needed

- `ratelimit` already imported: `patients/views.py:34` — `from django_ratelimit.decorators import ratelimit`
- `require_GET` already imported: `patients/views.py:63` — `from django.views.decorators.http import require_http_methods, require_GET, require_POST`

### Existing Delete Views Have Inconsistent Decorator Order

Several existing delete views (e.g., `patient_delete`) have `@ratelimit` *before* `@login_required`, which is the reverse of CLAUDE.md. **Do NOT "fix" this in this story** — this story only adds decorators to the 6 views listed in the AC. The existing delete view ordering is a separate concern.

### No Migration Required

Decorator-only change. No model, URL, or template changes.

### Project Structure Notes

- File changed: `patients/views.py` only — 6 decorator insertions
- No imports added, no template changes, no URL changes

### References

- [Source: _bmad-output/planning-artifacts/epic-2-security.md#Story-2.4]
- [Source: docs/code-audit-adversarial-review.md#SEC-04]
- [Source: patients/views.py:34 — ratelimit import]
- [Source: patients/views.py:63 — require_GET import]
- [Source: patients/views.py:859 — assessment_add current decorators]
- [Source: patients/views.py:1043 — assessment_edit current decorators]
- [Source: patients/views.py:1069 — assessment_edit_by_fileid current decorators]
- [Source: patients/views.py:668 — search_results current decorators]
- [Source: patients/views.py:1443 — bookmark_manager current decorators]
- [Source: patients/views.py:1195 — assessment_manager current decorators]
- [Source: CLAUDE.md#View Pattern — decorator order standard]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Tasks 1–6 complete: Added `@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)` to `search_results`, `assessment_add`, `assessment_edit`, `assessment_edit_by_fileid`; `@ratelimit(key='user_or_ip', rate='10/m', block=True)` to `bookmark_manager`; `@require_GET` to `assessment_manager`. All placed after `@login_required` per CLAUDE.md decorator order. No new imports added. AC #1–7 satisfied.
- Task 7 complete: `manage.py check` clean, 7 regression tests pass. AC #8 satisfied.

### File List

patients/views.py

## Change Log

- 2026-02-20: Implemented Story 2.4 — added rate limiting (`@ratelimit`) to `search_results`, `assessment_add`, `assessment_edit`, `assessment_edit_by_fileid`, `bookmark_manager`; added `@require_GET` to `assessment_manager` in `patients/views.py`. No new imports, no regressions.
