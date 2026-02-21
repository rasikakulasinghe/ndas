# Epic 2: Security Hardening

**Priority:** High — fix this week
**Source:** Code Audit Adversarial Review (2026-02-20)
**Scope:** `patients/views.py`, `patients/urls.py`, `users/views.py`, `ndas/settings.py`

Resolve all confirmed security vulnerabilities. None require schema changes.

---

## Story 2.1: Sanitize Exception Details in Delete Endpoint Responses

**Audit Finding:** SEC-01
**File:** `patients/views.py:588–594`, `patients/views.py:1195–1204` and similar
**Severity:** Critical

### Description

Every delete endpoint returns raw `str(e)` in the JSON error response, leaking database schema details, file paths, and internal model structure to the browser. Affected views: `patient_delete`, `assessment_delete`, `bookmark_delete`, `attachment_delete`, `cdic_assessment_delete`, `hine_assessment_delete`, `da_assessment_delete`, `gpa_delete`.

### Acceptance Criteria

- [ ] All delete endpoint except handlers return a generic message: `"An unexpected error occurred. Please try again."`
- [ ] Full exception details are logged server-side using the module logger (`logger.exception(...)`)
- [ ] `str(e)` is NOT included in any JSON response body
- [ ] All 8 affected delete views are updated
- [ ] Test: triggering a deliberate delete error returns generic message, not stack trace or DB details

---

## Story 2.2: Remove Unused `csrf_exempt` Imports

**Audit Finding:** SEC-02
**Files:** `patients/views.py:62`, `users/views.py:11`, `video/views.py:13`
**Severity:** Medium

### Description

`csrf_exempt` is imported but not applied to any view in `patients/views.py`. Its presence is dead import noise and a latent risk: a developer may assume CSRF exemption is already applied to a view and accidentally disable CSRF protection.

### Acceptance Criteria

- [ ] `csrf_exempt` import removed from `patients/views.py` if not used
- [ ] `csrf_exempt` import removed from `users/views.py` if not used
- [ ] `csrf_exempt` import removed from `video/views.py` if not used
- [ ] Grep confirms `csrf_exempt` is not applied to any view in these files (only remove imports where the decorator is genuinely unused)
- [ ] All views continue to enforce CSRF protection normally

---

## Story 2.3: Change `<str:pk>` to `<int:pk>` in URL Routes

**Audit Finding:** SEC-03
**File:** `patients/urls.py`
**Severity:** Medium

### Description

All patient/assessment/attachment routes use `<str:pk>` instead of `<int:pk>`. Arbitrary strings (including path traversal fragments and SQL fragments) reach the view before Django validates them. A non-numeric `pk` causes `get_object_or_404()` to raise a `ValueError` (500 error) instead of a clean 404.

### Acceptance Criteria

- [ ] All URL patterns for integer primary keys changed from `<str:pk>` to `<int:pk>`
- [ ] Routes for named string identifiers (e.g., BHT, NNC) remain as `<str:...>` — only change pk/id routes
- [ ] Requesting `/patient/view/abc/` returns 404, not 500
- [ ] All existing patient/assessment/attachment links continue to work with numeric IDs
- [ ] Count of changed routes documented in commit message

---

## Story 2.4: Add Rate Limiting to Missing Mutating Endpoints

**Audit Finding:** SEC-04
**File:** `patients/views.py`
**Severity:** Medium

### Description

Several POST/mutating views are missing `@ratelimit` decorator per CLAUDE.md standards. Missing on: `assessment_add`, `assessment_edit`, `assessment_edit_by_fileid`, `search_results`, `bookmark_manager`.

### Acceptance Criteria

- [ ] `@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)` added to `assessment_add`
- [ ] `@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)` added to `assessment_edit`
- [ ] `@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)` added to `assessment_edit_by_fileid`
- [ ] `@ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True)` added to `search_results`
- [ ] `@ratelimit(key='user_or_ip', rate='10/m', block=True)` added to `bookmark_manager`
- [ ] `@require_GET` added to `assessment_manager` (GET-only view)
- [ ] Decorator order follows CLAUDE.md: `@login_required`, then `@require_http_methods`, then `@ratelimit`

---

## Story 2.5: Remove Dead Authentication Check in `patient_add`

**Audit Finding:** SEC-05
**File:** `patients/views.py:283–289`
**Severity:** Low–Medium

### Description

`patient_add` has an `if not request.user.is_authenticated:` block inside the function body that is unreachable dead code — `@login_required` already redirected unauthenticated users before the function body executes. This misleads code readers.

### Acceptance Criteria

- [ ] The unreachable `if not request.user.is_authenticated:` block removed from `patient_add`
- [ ] The function still requires login via `@login_required` decorator
- [ ] No other views have the same redundant inner auth check pattern

---

## Story 2.6: Fix Login Rate Limit to Prevent Username Enumeration

**Audit Finding:** SEC-06
**File:** `users/views.py:32–33`
**Severity:** Medium

### Description

Rate limiting by `post:username` allows an attacker to enumerate valid usernames: after 3 failed attempts, only the rate-limited username gets a 429. Should rate limit by IP first to prevent enumeration.

### Acceptance Criteria

- [ ] Rate limit key changed from `post:username` to `ip` for the login view
- [ ] Rate still `3/m` (or stricter)
- [ ] Both valid and invalid usernames receive the same 429 response when the IP limit is hit
- [ ] Username enumeration via differential 429 responses is no longer possible

---

## Story 2.7: Fix `attachment_delete_confirm` to Use `get_object_or_404`

**Audit Finding:** SEC-07
**File:** `patients/views.py:2211`
**Severity:** Medium

### Description

The deprecated `attachment_delete_confirm` view uses raw `.objects.get(id=pk)` which raises an unhandled `ObjectDoesNotExist` (500 error) for invalid IDs. Even deprecated views must not produce 500s.

### Acceptance Criteria

- [ ] `Attachment.objects.get(id=pk)` replaced with `get_object_or_404(Attachment, id=pk)`
- [ ] Requesting `/attachment/delete-confirm/99999/` returns 404, not 500
- [ ] The deprecation docstring remains in place

---

## Story 2.8: Move `SECURE_HSTS_SECONDS` Inside `if not DEBUG:` Block

**Audit Finding:** DEAD-09
**File:** `ndas/settings.py:269`
**Severity:** Low

### Description

`SECURE_HSTS_SECONDS = 31536000` is set unconditionally (outside any DEBUG conditional). Browsers that connect to the dev server cache the HSTS directive for 1 year. Should only apply in production.

### Acceptance Criteria

- [ ] `SECURE_HSTS_SECONDS` moved inside the `if not DEBUG:` block in `ndas/settings.py`
- [ ] In DEBUG mode, `SECURE_HSTS_SECONDS` is not set (or set to `0`)
- [ ] Production settings (`DEBUG=False`) continue to set HSTS to 31536000

---

## Story 2.9: Restrict Patient Data in `patient_delete_confirm` Context

**Audit Finding:** SEC-09
**File:** `patients/views.py:599–611`
**Severity:** Low

### Description

`patient_delete_confirm` passes the full `patient` object to the template even when the user lacks delete permission (`hide=True`). If the template has a rendering bug, patient data is exposed. Should only pass patient data when permission is confirmed.

### Acceptance Criteria

- [ ] When user is not superuser, only minimal data (patient ID, patient name) passed to template context, not full patient object
- [ ] The `hide=True` flag still present for template rendering decisions
- [ ] Superuser path unchanged — full patient object still passed
- [ ] Template continues to render correctly for both permission levels
