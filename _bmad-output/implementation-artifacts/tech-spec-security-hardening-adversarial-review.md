---
title: 'NDAS Security & Performance Hardening — Adversarial Review Fixes'
slug: 'security-hardening-adversarial-review'
created: '2026-05-16'
status: 'completed'
stepsCompleted: [1, 2, 3, 4, 5]
tech_stack: ['Django 4.2.16', 'Python 3.x', 'django-ratelimit 4.1.0', 'django-csp 3.8']
files_to_modify: ['reports/views.py', 'users/views.py', 'video/views.py', 'ndas/settings.py', 'ndas/custom_codes/custom_methods.py']
code_patterns: ['institution_scope()', 'admin_required decorator', '@ratelimit decorator stack order', '_counts() aggregation helper', 'has_delete_permission()']
test_patterns: ['PatientTestBase mixin', 'force_login', '@override_settings STATIC_OVERRIDE', 'django.test.TestCase']
---

# Tech-Spec: NDAS Security & Performance Hardening — Adversarial Review Fixes

**Created:** 2026-05-16

## Overview

### Problem Statement

12 security vulnerabilities and performance issues identified in an adversarial review (`ad.md`) remain unpatched in the NDAS codebase. The issues span IDOR on medical PDF downloads (a direct data breach vector), cross-institution data leakage in user/activity-log views, missing rate limits on password-change and user-edit endpoints, a CSP configuration that is inert in DEBUG mode, a silent institution-scope expansion footgun, a file-handle leak under load, an unbounded full-table load in a stats function, staff lateral access to any peer's video records, an unauthenticated report file download path, and a redundant database COUNT on every admin page load.

### Solution

Apply targeted, surgical fixes to each of the 12 identified issues across `reports/views.py`, `users/views.py`, `video/views.py`, `ndas/settings.py`, and `ndas/custom_codes/custom_methods.py`. No new abstractions, no model changes, no migrations required. Every fix is the minimal change needed to close the vulnerability at its identified location.

### Scope

**In Scope:**
- Fix #1: Add institution scoping to all 5 assessment PDF download views (`reports/views.py`)
- Fix #3: Add same-institution permission check to `userViewByUsername` (and `userView` by PK) (`users/views.py`)
- Fix #4: Filter `admin_activity_logs` by institution for non-superusers (`users/views.py`)
- Fix #6: Add `@ratelimit` to `userEdit` and `userChangePassword` (`users/views.py`)
- Fix #7: Remove `'unsafe-inline'` and `'unsafe-eval'` from `CSP_SCRIPT_SRC` in DEBUG block (`ndas/settings.py`)
- Fix #8: Add guard in `institution_scope()` — raise `PermissionDenied` + log when a non-superuser has `institution=None` (`ndas/custom_codes/custom_methods.py`)
- Fix #10: Replace raw `open()` with context manager / path-passing in all 5 PDF download views + `download_report` (`reports/views.py`)
- Fix #11: Replace `Bookmark.objects.all()` with aggregation query in `get_userStats()` (`ndas/custom_codes/custom_methods.py`)
- Fix #12: Tighten `video_edit` and `video_delete_confirm` — staff may only modify their own uploads; superusers retain full access (`video/views.py`)
- Fix #13: Addressed implicitly by Fix #3 (enumeration vector broken)
- Fix #14: Add session+cache keyed ownership check to `download_report` (`reports/views.py`)
- Fix #15: Replace `activities.count()` with `paginator.count` in `admin_activity_logs` (`users/views.py`)

**Out of Scope:**
- Fix #2: `bookmark_manager_user` user exposure (excluded by user)
- Fix #5: `help_article` institution scoping (excluded by user)
- Fix #9: Dashboard DB query caching (excluded by user)
- Any new features, refactors, or abstractions beyond the minimal fix per issue
- Model changes or database migrations
- Frontend / template changes

## Context for Development

### Codebase Patterns

**Institution scoping:**
- `institution_scope(request, field='patient__institution')` from `ndas/custom_codes/custom_methods.py` returns ORM filter kwargs dict; spread as `**institution_scope(request)` into `get_object_or_404()`.
- Default field `'patient__institution'` applies to all 5 assessment models — they all have a `patient` FK whose model has an `institution` FK.
- When `inst is None` (Phase 1 / superuser), currently returns `{}` (no scope). Fix #8 changes this to raise for non-superusers.

**`admin_required` decorator** (`users/decorators.py:7`):
- Permits `is_staff OR is_superuser`. Inside decorated views, use `request.user.is_superuser` to distinguish the two.
- `superuser_required` (same file) permits `is_superuser` only.

**Decorator stack order** (mandatory per project rules):
1. `@login_required(login_url="user-login")`
2. `@require_http_methods(["GET", "POST"])` / `@require_GET` / `@require_POST`
3. `@ratelimit(key='user_or_ip', rate='10/m')` for create/edit; `'5/m'` for delete
4. `@handle_view_errors(...)` (where applicable)
- `userEdit` (line 216) and `userChangePassword` (line 270) currently have only `@login_required`. Both need `@require_http_methods` AND `@ratelimit` added.

**`_counts()` aggregation helper** (`custom_methods.py:68`):
```python
def _counts(qs, field='added_by_id'):
    return {row[field]: row['count'] for row in qs.values(field).annotate(count=Count('id'))}
```
Accepts a queryset and returns a `{pk: count}` dict via SQL aggregation — does NOT load objects into memory. Fix #11 replaces the else branch with an explicit `{...: ... for row in Bookmark.objects.values('owner_id').annotate(count=Count('id'))}` to bypass `_counts()` for the global case, avoiding double-annotation risk.

**FileResponse and file handles:**
- `FileResponse(open(file_path, 'rb'), ...)` leaks if construction or header assignment raises before return.
- Safe pattern: open in `try`, close in `except`, let FileResponse take ownership on success:
  ```python
  f = open(file_path, 'rb')
  try:
      response = FileResponse(f, content_type=...)
      response['Content-Disposition'] = ...
      return response
  except Exception:
      f.close()
      raise
  ```
- 6 sites affected: `download_gm_assessment_pdf`, `download_hine_assessment_pdf`, `download_da_assessment_pdf`, `download_cdic_assessment_pdf`, `download_gpa_assessment_pdf`, `download_report`.

**Report generation flow (for fix #14):**
- `report_builder` (line 33) → generates file → `file_id = os.path.basename(file_path)` (line 164) → `redirect('reports:download', file_id=file_id)` (line 175).
- Cache key set immediately after `file_id` is assigned: `cache.set(f"report_owner_{file_id}_{request.session.session_key}", request.user.pk, 24*3600)`.
- `download_report` (line 292) checks: `owner_pk = cache.get(f"report_owner_{file_id}_{request.session.session_key}")`. If `None` (key absent = different session or attacker) → `raise PermissionDenied`. If mismatch → `raise PermissionDenied`.
- `reports/views.py` currently does NOT import `cache` — add `from django.core.cache import cache`.
- Trade-off: downloading a report after session refresh (browser-close-reopen) will be denied. Since reports expire in 24h and the redirect is immediate, this is acceptable.

**`has_delete_permission()` (`delete_helpers.py:16`):**
- For staff: returns `True` only if `entity.added_by == user` — already enforces own-record-only for `video_delete`.
- `video_edit` and `video_delete_confirm` do their own inline check (`if not request.user.is_staff`) that incorrectly bypasses ownership for all staff. These two views need the check changed to `if not request.user.is_superuser`.

**`paginator.count`:**
- Django's `Paginator` computes `.count` internally on first use. At line 858, `activities.count()` re-issues a full `COUNT(*)` query. Replace with `paginator.count`.

**Test structure:**
- Tests exist only in `patients/tests/` — no existing tests in `reports/`, `users/`, or `video/`.
- Test base class pattern: `PatientTestBase(TestCase)` with `superuser`, `staff_user`, `other_staff`.
- Key fixtures: `self.client.force_login(user)`, `@override_settings(STORAGES=STATIC_OVERRIDE)`, `@ratelimit` must be disabled in tests via `RATELIMIT_ENABLE=False` override.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `reports/views.py` | PDF downloads + report builder + download_report (fixes #1, #10, #14) |
| `users/views.py` | User profile, admin logs, password change (fixes #3, #4, #6, #15) |
| `users/decorators.py` | `admin_required` definition — check for `is_staff OR is_superuser` |
| `video/views.py` | `video_edit` (line 155), `video_delete_confirm` (line 472), `video_delete` (line 507) — fix #12 |
| `ndas/settings.py` | DEBUG `CSP_SCRIPT_SRC` block (fix #7) |
| `ndas/custom_codes/custom_methods.py` | `institution_scope()` (line 23), `get_userStats()` (line 63) — fixes #8, #11 |
| `ndas/custom_codes/delete_helpers.py` | `has_delete_permission()` — reference only, already correct for delete |
| `patients/tests/test_patient_crud.py` | Test pattern reference for new tests |

### Technical Decisions

- **Fix #3 — scope model:** Same-institution only. Non-superusers: `get_object_or_404(CustomUser, username=username, institution=request.institution)`. Superusers: pass through (no filter added). Applies to both `userViewByUsername` (line 211) and `userView` by PK (line 205).
- **Fix #8 — guard placement:** Inside `institution_scope()` itself. When `inst is None` and `not request.user.is_superuser`: `logger.warning(...)` + `raise PermissionDenied(...)`. Superusers retain `{}` return (full access by design).
- **Fix #12 — video permissions:** `video_edit` and `video_delete_confirm` — change `if not request.user.is_staff` to `if not request.user.is_superuser`. `video_delete` already uses `has_delete_permission()` which is already correct.
- **Fix #14 — ownership store:** Session-keyed cache (Option B). Key: `f"report_owner_{file_id}_{request.session.session_key}"`. Set in `report_builder` at line 164+, check in `download_report` before serving.

## Implementation Plan

### Tasks

Tasks are ordered dependency-first: utility functions before the views that use them, same-file changes batched together.

---

- [x] **Task 1: Fix `institution_scope()` None guard for non-superusers (Fix #8)**
  - File: `ndas/custom_codes/custom_methods.py`
  - Action: After resolving `inst = getattr(request, 'institution', None)`, add a guard: if `inst is None` and `not request.user.is_superuser`, call `logger.warning(...)` then `raise PermissionDenied("Institution context required.")`. Superusers continue to receive `{}` (full access by design).
  - Exact replacement in `institution_scope()` (line 31):
    ```python
    inst = getattr(request, 'institution', None)
    if inst is None and not request.user.is_superuser:
        logger.warning(
            "institution_scope: non-superuser %s has no institution context — denying to prevent silent cross-institution exposure.",
            request.user.username,
        )
        raise PermissionDenied("Institution context required.")
    return {field: inst} if inst is not None else {}
    ```
  - Notes: `PermissionDenied` is already imported in `custom_methods.py` (check; add `from django.core.exceptions import PermissionDenied` if missing). This must be the first task — it protects all subsequent views that call `institution_scope()`.

---

- [x] **Task 2: Fix `get_userStats()` bookmark aggregation (Fix #11)**
  - File: `ndas/custom_codes/custom_methods.py`
  - Action: Replace the bookmark_counts line (line 79–82) with an explicit branch that avoids passing `Bookmark.objects.all()` to `_counts()` (which would re-annotate an already-annotatable queryset). Use direct aggregation for the global case:
    ```python
    if institution:
        bookmark_counts = _counts(
            Bookmark.objects.filter(owner__institution=institution),
            field='owner_id',
        )
    else:
        bookmark_counts = {
            row['owner_id']: row['count']
            for row in Bookmark.objects.values('owner_id').annotate(count=Count('id'))
        }
    ```
  - Notes: `Count` is already imported at the top of `custom_methods.py`. This is safe for the superuser (`institution=None`) case — the aggregation query never loads Bookmark objects into Python memory.

---

- [x] **Task 3: Fix DEBUG CSP to re-enable script-src protection (Fix #7)**
  - File: `ndas/settings.py`
  - Action: In the `if DEBUG:` block (line 294), remove `"'unsafe-inline'"` and `"'unsafe-eval'"` from `CSP_SCRIPT_SRC`. The nonce mechanism (`CSP_INCLUDE_NONCE_IN = ['script-src']`, line 288) already handles inline scripts that have a nonce — `'unsafe-inline'` is not needed alongside nonces for scripts.
  - Replace line 294:
    ```python
    # Before
    CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdn.jsdelivr.net", ...)
    # After
    CSP_SCRIPT_SRC = ("'self'", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com", "https://unpkg.com", "https://vjs.zencdn.net")
    ```
  - Notes: No change to production CSP (already correct). The nonce injected by `CSPMiddleware` into `{{ request.csp_nonce }}` will still allow inline scripts that have the nonce attribute. Any inline script in templates/JS that does NOT use `nonce="{{ request.csp_nonce }}"` will be blocked — this is intentional.

---

- [x] **Task 4: Add institution scoping + safe file handles to the 5 assessment PDF download views (Fixes #1 + #10)**
  - File: `reports/views.py`
  - Action part A — Add import at top of file:
    ```python
    from ndas.custom_codes.custom_methods import institution_scope
    ```
  - Action part B — For each of the 5 views (`download_gm_assessment_pdf`, `download_hine_assessment_pdf`, `download_da_assessment_pdf`, `download_cdic_assessment_pdf`, `download_gpa_assessment_pdf`):
    1. Add `**institution_scope(request)` to `get_object_or_404`:
       ```python
       # Before
       assessment = get_object_or_404(GMAssessment, id=assessment_id)
       # After
       assessment = get_object_or_404(GMAssessment, id=assessment_id, **institution_scope(request))
       ```
       (Substitute the correct model class for each view.)
    2. Wrap the `open()` call with a try/except to prevent handle leaks:
       ```python
       # Before
       response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
       response['Content-Disposition'] = f'attachment; filename="{filename}"'
       return response
       # After
       f = open(file_path, 'rb')
       try:
           response = FileResponse(f, content_type='application/pdf')
           response['Content-Disposition'] = f'attachment; filename="{filename}"'
           return response
       except Exception:
           f.close()
           raise
       ```
  - Notes: `institution_scope()` default field is `'patient__institution'` — all 5 assessment models have a `patient` FK with an `institution` FK, so the default applies. The field path `'patient__institution'` is in `_ALLOWED_SCOPE_FIELDS`. Do NOT change the generator calls or filename logic.

---

- [x] **Task 5: Fix `download_report` file handle + add report ownership check; add cache.set in `report_builder` (Fixes #10 + #14)**
  - File: `reports/views.py`
  - Action part A — Add `cache` import at top of file (alongside existing imports):
    ```python
    from django.core.cache import cache
    ```
  - Action part B — In `report_builder` (line ~164), immediately after `file_id = os.path.basename(file_path)`, add:
    ```python
    cache.set(
        f"report_owner_{file_id}_{request.session.session_key}",
        request.user.pk,
        timeout=24 * 3600,
    )
    ```
  - Action part C — In `download_report` (line ~292), after `get_validated_report_path(file_id)` and before the `os.path.exists` check, add ownership verification:
    ```python
    owner_pk = cache.get(f"report_owner_{file_id}_{request.session.session_key}")
    if owner_pk is None or owner_pk != request.user.pk:
        raise PermissionDenied("You are not authorized to download this report.")
    ```
  - Action part D — Apply the same try/except file-handle pattern (from Task 4) to the `open()` call in `download_report` (line ~320).
  - Notes: `PermissionDenied` is already imported in `reports/views.py` (line 15). The ownership check uses `None` as the sentinel for "no record found" (different session or attacker), blocking access in that case. Superusers are NOT exempt — the report was still generated in a specific session.

---

- [x] **Task 6: Add institution scope to `userView` and `userViewByUsername` (Fix #3)**
  - File: `users/views.py`
  - Action — Replace both views:
    ```python
    # userView (line 204–208)
    @login_required(login_url='user-login')
    def userView(request, pk):
        if request.user.is_superuser:
            custom_user = get_object_or_404(CustomUser, id=pk)
        else:
            custom_user = get_object_or_404(CustomUser, id=pk, institution=request.institution)
        loged_user = request.user
        return render(request, 'users/user_view.html', {'custom_user': custom_user, 'user': loged_user})

    # userViewByUsername (line 210–213)
    @login_required(login_url='user-login')
    def userViewByUsername(request, username):
        if request.user.is_superuser:
            custom_user = get_object_or_404(CustomUser, username=username)
        else:
            custom_user = get_object_or_404(CustomUser, username=username, institution=request.institution)
        return render(request, 'users/user_view.html', {'custom_user': custom_user})
    ```
  - Notes: `request.institution` is set by `InstitutionContextMiddleware` — always present for authenticated views. Superusers bypass scoping (consistent with the rest of the system). A non-superuser attempting to view a user from another institution now gets a 404 (same as any other scoped `get_object_or_404`).

---

- [x] **Task 7: Scope `admin_activity_logs` by institution + fix double COUNT (Fixes #4 + #15)**
  - File: `users/views.py`
  - Action — Replace the view body (lines 847–861):
    ```python
    @admin_required
    def admin_activity_logs(request):
        """Admin view to see all system activity logs."""
        if request.user.is_superuser:
            activities = UserActivityLog.objects.select_related('user').all().order_by('-login_timestamp')
        else:
            activities = UserActivityLog.objects.select_related('user').filter(
                user__institution=request.institution
            ).order_by('-login_timestamp')

        paginator = Paginator(activities, 100)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'total_activities': paginator.count,
        }
        return render(request, 'users/admin/activity_logs.html', context)
    ```
  - Notes: `paginator.count` (Fix #15) replaces `activities.count()` — Paginator already ran `COUNT(*)` internally; this reuses the cached value. `user__institution` follows the FK chain `UserActivityLog.user → CustomUser.institution`.

---

- [x] **Task 8: Add rate limiting to `userEdit` and `userChangePassword` (Fix #6)**
  - File: `users/views.py`
  - Action — Add `@require_http_methods` and `@ratelimit` decorators to both views in the mandatory project order:
    ```python
    # userEdit (currently line 215–216)
    @login_required(login_url='user-login')
    @require_http_methods(["GET", "POST"])
    @ratelimit(key='user_or_ip', rate='10/m')
    def userEdit(request, pk):

    # userChangePassword (currently line 269–270)
    @login_required(login_url='user-login')
    @require_http_methods(["GET", "POST"])
    @ratelimit(key='user_or_ip', rate='10/m')
    def userChangePassword(request):
    ```
  - Notes: Verify `require_http_methods` and `ratelimit` are already imported at the top of `users/views.py` (they are used elsewhere in the file — login view has `@ratelimit` at lines 42–43). If `require_http_methods` is not imported, add `from django.views.decorators.http import require_http_methods`. `user_or_ip` is the correct key for authenticated + public safety.

---

- [x] **Task 9: Remove `is_staff` bypass from video edit and delete confirm (Fix #12)**
  - File: `video/views.py`
  - Action — In both `video_edit` (line 160) and `video_delete_confirm` (line 478), change the permission guard:
    ```python
    # Before (both views)
    if not request.user.is_staff and video.added_by != request.user:
    # After (both views)
    if not request.user.is_superuser and video.added_by != request.user:
    ```
  - Notes: This enforces that staff users can only edit/delete their own uploaded videos. `video_delete` (the DELETE endpoint, line 507) already uses `has_delete_permission()` which correctly restricts staff to own records — no change needed there. The error messages and redirect targets remain unchanged.

---

### Acceptance Criteria

- [ ] **AC 1 (Fix #1 — IDOR):** Given a staff user at Institution A is authenticated, when they request `download_gm_assessment_pdf` with an `assessment_id` that belongs to a patient at Institution B, then the response is HTTP 404.

- [ ] **AC 2 (Fix #1 — IDOR happy path):** Given a staff user at Institution A is authenticated, when they request `download_gm_assessment_pdf` with an `assessment_id` that belongs to a patient at Institution A, then the response is HTTP 200 with a PDF attachment.

- [ ] **AC 3 (Fix #3 — cross-institution profile):** Given a staff user at Institution A is authenticated, when they request `userViewByUsername` with a username belonging to a user at Institution B, then the response is HTTP 404.

- [ ] **AC 4 (Fix #3 — same institution):** Given a staff user at Institution A is authenticated, when they request `userViewByUsername` with a username belonging to a user at Institution A, then the response is HTTP 200 with the profile rendered.

- [ ] **AC 5 (Fix #3 — superuser bypass):** Given a superuser is authenticated, when they request `userViewByUsername` with any username regardless of institution, then the response is HTTP 200.

- [ ] **AC 6 (Fix #4 — activity log scoping):** Given a staff user at Institution A is authenticated, when they access `admin_activity_logs`, then the returned activity records contain only entries for users whose `institution` is Institution A.

- [ ] **AC 7 (Fix #4 — superuser sees all):** Given a superuser is authenticated, when they access `admin_activity_logs`, then activity records for all institutions are returned.

- [ ] **AC 8 (Fix #6 — rate limit):** Given a logged-in user sends more than 10 POST requests per minute to `userEdit` or `userChangePassword`, then subsequent requests within that window return HTTP 429.

- [ ] **AC 9 (Fix #7 — CSP script-src):** Given `DEBUG=True`, when a page response is inspected, then the `Content-Security-Policy` header's `script-src` directive does NOT contain `'unsafe-inline'` or `'unsafe-eval'`.

- [ ] **AC 10 (Fix #8 — None institution guard):** Given a staff user whose `institution` is `None` (missing context) makes any request that triggers `institution_scope()`, then the response is HTTP 403 and a warning is logged.

- [ ] **AC 11 (Fix #11 — bookmark aggregation):** Given `get_userStats(institution=None)` is called (superuser context), then no `Bookmark` model instances are loaded into Python memory — the result is produced by a single SQL aggregate query.

- [ ] **AC 12 (Fix #12 — video staff lateral access):** Given a staff user at Institution A is authenticated, when they attempt to edit a video uploaded by a different staff user at Institution A, then the response is HTTP 302 redirect with a permission-denied message.

- [ ] **AC 13 (Fix #12 — video own record):** Given a staff user is authenticated, when they attempt to edit a video they themselves uploaded, then they are permitted (HTTP 200 or valid form).

- [ ] **AC 14 (Fix #12 — superuser override):** Given a superuser is authenticated, when they attempt to edit any video regardless of `added_by`, then they are permitted.

- [ ] **AC 15 (Fix #14 — report ownership):** Given User A generates a report (receiving `file_id`), when User B (in a different session) attempts to download that same `file_id`, then the response is HTTP 403.

- [ ] **AC 16 (Fix #14 — own report):** Given a user generates a report in their current session, when they immediately download it (same session), then the response is HTTP 200 with the file.

- [ ] **AC 17 (Fix #15 — double COUNT):** Given `admin_activity_logs` is rendered, then only one `COUNT(*)` SQL query is issued for the total count (verified via Django's `connection.queries` in tests or Django Debug Toolbar in dev).

## Additional Context

### Dependencies

- No new packages. All fixes use: `django.core.cache` (already in stack), `django.core.exceptions.PermissionDenied` (already imported in relevant files), `django_ratelimit` (already installed).
- `from django.core.cache import cache` must be added to `reports/views.py`.
- `from ndas.custom_codes.custom_methods import institution_scope` must be added to `reports/views.py`.
- Verify `from django.views.decorators.http import require_http_methods` is present in `users/views.py` (likely already imported — check before adding).

### Testing Strategy

**No existing tests** for `reports/`, `users/`, or `video/` apps. New tests should be written alongside each fix, following the `PatientTestBase` pattern from `patients/tests/test_patient_crud.py`.

For each new test module:
- Class setup: `superuser`, `staff_user` (with `institution`), `other_staff` (different institution or no institution)
- Always use `self.client.force_login(user)` — never `client.login(username=..., password=...)`
- Always decorate test classes with `@override_settings(STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})` (`STATIC_OVERRIDE` pattern)
- Disable rate limiting: `@override_settings(RATELIMIT_ENABLE=False)` on test classes that hit rate-limited views
- Test files to create:
  - `reports/tests/test_security.py` — ACs 1, 2, 15, 16
  - `users/tests/test_security.py` — ACs 3–8, 17
  - `video/tests/test_security.py` — ACs 12–14

**Manual smoke tests (pre-deploy):**
1. Log in as staff at Institution A → attempt to download a PDF for a patient at Institution B → expect 404
2. Log in as staff → navigate to another staff user's username URL → expect 404 (if different institution)
3. Log in as staff → access admin activity logs → verify no entries from other institutions appear
4. Generate a report → copy the download URL → open in incognito (different session) → expect 403
5. Open browser dev tools → check `Content-Security-Policy` header → confirm no `unsafe-inline` in `script-src` in dev
6. Log in as staff → attempt to edit a video uploaded by a colleague → expect permission-denied redirect

### Notes

- **Fix #13 (enumeration chain)** is fully addressed as a side-effect of Fix #3 — no separate task.
- **Fix #7 caution:** After removing `'unsafe-inline'` from DEBUG `CSP_SCRIPT_SRC`, any inline `<script>` tag in templates that does NOT use `nonce="{{ request.csp_nonce }}"` will be blocked by the browser in dev. Run the app locally after this change and check the browser console for CSP violation reports — this may surface pre-existing template issues.
- **Fix #8 scope:** The guard in `institution_scope()` covers all 37 call sites at once. In Phase 1 (before `MULTI_INSTITUTION_ENABLED=True`), `request.institution` is typically `None` for all users, which would make ALL staff requests raise `PermissionDenied`. **Verify that Phase 1 compatibility is maintained** — if `InstitutionContextMiddleware` always provides a non-None institution for staff in the current deployment, this is safe. If `institution` is still `None` in Phase 1 for all users, this guard must be gated on `MULTI_INSTITUTION_ENABLED`.
- **Fix #14 trade-off:** A user who closes their browser (session expires) and returns to `report_history` to re-download a report from the same day will receive HTTP 403. This is the intended security trade-off with session-keyed caching.
- **Fix #14 scope gap:** The `delete_report` endpoint (line 252) is not covered by ownership checking — it can delete any report file by UUID. This is a residual risk but is out of scope for this spec.

## Review Notes

- Adversarial review completed: 11 findings, 2 fixed, 9 skipped (noise or out of scope)
- Resolution approach: auto-fix
- **F7 (fixed):** `report_builder` now calls `request.session.create()` before accessing `session_key` so the cache key is never `None` for brand-new sessions.
- **F1 (fixed):** `institution_scope` guard narrowed to only deny when `user.institution_id` is set but `request.institution` is missing (middleware misconfiguration). Phase 1 and transitional users with `institution=None` pass through cleanly.
- Skipped (out of scope): F3 (userEdit no institution scope), F4 (admin user views unscoped), F5 (delete_report no ownership check), F6 (report_history shows all files).
- Skipped (noise): F2 (video_view read-only asymmetry by design), F8 (CSP nonce operative via django-csp), F9 (ORM paths verified correct), F10 (test logic correct), F11 (allowlist design observation).
