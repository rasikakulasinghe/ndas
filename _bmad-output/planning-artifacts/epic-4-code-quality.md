# Epic 4: Code Quality, Best Practices & Configuration Cleanup

**Priority:** Medium — fix this sprint
**Source:** Code Audit Adversarial Review (2026-02-20)
**Scope:** `patients/views.py`, `patients/models.py`, `users/models.py`, `ndas/settings.py`, `ndas/custom_codes/custom_methods.py`

Clean up dead code, fix best practice violations, and resolve configuration issues. These changes carry low risk but improve long-term maintainability and correctness.

---

## Story 4.1: Remove Unused Imports from `patients/views.py`

**Audit Finding:** BP-05, SEC-02 (partial)
**File:** `patients/views.py`
**Severity:** Low

### Description

The following imports are unused in `patients/views.py` and should be removed:
- `import pytz` (line ~64) — no `timezone.activate()` calls
- `import subprocess` (line ~64) — only used in `custom_methods.py`
- `import tempfile` (line ~64) — not used in views
- `from django.core.files.storage import FileSystemStorage` (line ~71) — unused
- `from django.core.files import File` (line ~70) — unused
- `from django.views.decorators.csrf import csrf_exempt` (line ~62) — unused

### Acceptance Criteria

- [ ] All 6 listed unused imports removed from `patients/views.py`
- [ ] No `NameError` or `ImportError` occurs after removal (verify by running the dev server)
- [ ] Grep confirms none of the removed names are referenced elsewhere in the file
- [ ] `isort` or import order is maintained after removal

---

## Story 4.2: Replace Raw `.objects.get()` Calls with `get_object_or_404()`

**Audit Finding:** BP-01
**File:** `patients/views.py` — 10 occurrences
**Severity:** Medium

### Description

Ten views use raw `.objects.get()` which raises an unhandled `ObjectDoesNotExist` (500 error) for missing records. Per CLAUDE.md: always use `get_object_or_404()`.

Locations to fix:
- `patients/views.py:709` — `Patient.objects.get(bht=search_text)`
- `patients/views.py:726` — `Patient.objects.get(pin=search_text)`
- `patients/views.py:743` — `Patient.objects.get(nnc_no=search_text)`
- `patients/views.py:1071` — `GMAssessment.objects.get(video_file=pk)`
- `patients/views.py:1444` — `Help.objects.get(id=pk)`
- `patients/views.py:1630` — `Bookmark.objects.get(id=pk)`
- `patients/views.py:1738` — `CustomUser.objects.get(username=username)`
- `patients/views.py:2211` — `Attachment.objects.get(id=pk)` (also covered in SEC-07)
- `patients/views.py:2801` — `HINEAssessment.objects.get(pk=hine_id)`
- `patients/views.py:3025` — `HINEAssessment.objects.get(id=hine_id)`

**Note:** For search views (`Patient.objects.get(bht=...)` etc.), if no result found the current code likely redirects or shows an error message — replicate that behavior using `try/except ObjectDoesNotExist` or `filter().first()` with a None check, as `get_object_or_404()` may not be appropriate for search (which should show "not found" UI, not a 404 page).

### Acceptance Criteria

- [ ] All 10 raw `.objects.get()` calls audited and replaced with either `get_object_or_404()` or explicit `filter().first()` with None check (for search result flows)
- [ ] Requesting a non-existent record via URL returns 404, not 500
- [ ] Search for a non-existent BHT/PIN/NNC shows the existing "not found" UI message (not a 404 page)
- [ ] All views continue to function correctly for existing records

---

## Story 4.3: Add Missing HTTP Method Decorators to Views

**Audit Finding:** BP-06, BP-08, SEC-04 (partial)
**File:** `patients/views.py`
**Severity:** Medium

### Description

Several views are missing `@require_http_methods` or `@require_GET` decorators per CLAUDE.md patterns:
- `search_results` — manually checks `request.method != "POST"` instead of using `@require_POST`
- `assessment_edit_by_fileid` — missing all security decorators except `@login_required`
- `assessment_manager` — should be `@require_GET` (read-only list view)

### Acceptance Criteria

- [ ] `@require_http_methods(["POST"])` added to `search_results` and manual method check removed
- [ ] `@require_http_methods(["GET", "POST"])` added to `assessment_edit_by_fileid`
- [ ] `@handle_view_errors` decorator added to `assessment_edit_by_fileid`
- [ ] `@require_GET` added to `assessment_manager` (if it is GET-only)
- [ ] Decorator order follows CLAUDE.md: `@login_required` → `@require_*` → `@ratelimit`
- [ ] All affected views respond correctly to valid requests
- [ ] Invalid HTTP methods return 405 Method Not Allowed

---

## Story 4.4: Fix Logger Usage — Remove In-Function Logger Overrides

**Audit Finding:** BP-03
**File:** `patients/views.py`
**Severity:** Low

### Description

The module-level logger (`logger = logging.getLogger("django")`) is overridden inside function bodies (`logger = logging.getLogger(__name__)`). These are different loggers with different configurations. Logs from assessment operations go to the wrong logger.

### Acceptance Criteria

- [ ] All in-function `logger = logging.getLogger(...)` assignments removed
- [ ] All functions use the module-level `logger` variable
- [ ] Log messages from assessment views now appear in the `django` logger output
- [ ] No existing log calls are broken (check for `logger.info`, `logger.error`, `logger.exception` patterns)

---

## Story 4.5: Remove Redundant Imports Inside Function Bodies

**Audit Finding:** BP-04
**File:** `patients/views.py:863–865`
**Severity:** Low

### Description

`assessment_add()` re-imports `JsonResponse`, `ValidationError`, and `logging` inside the function body, all of which are already imported at module level. These are wasteful and misleading.

### Acceptance Criteria

- [ ] In-function `from django.http import JsonResponse` import removed from `assessment_add`
- [ ] In-function `from django.core.exceptions import ValidationError` import removed from `assessment_add`
- [ ] In-function `import logging` import removed from `assessment_add`
- [ ] Function continues to use `JsonResponse`, `ValidationError`, and `logging` correctly from module-level imports
- [ ] Check all other view functions for the same pattern and fix any additional occurrences found

---

## Story 4.6: Fix `EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS` Setting Not Used in Model

**Audit Finding:** CFG-03
**File:** `ndas/settings.py:189` and `users/models.py`
**Severity:** Medium

### Description

`settings.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS` is defined and configurable via `.env`, but `users/models.py` hardcodes `timedelta(hours=24)` instead of reading the setting. Changing the env variable has no effect.

### Acceptance Criteria

- [ ] `users/models.py` updated to use `from django.conf import settings` and `timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS)` instead of hardcoded `24`
- [ ] Setting `EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS=48` in `.env` now results in a 48-hour expiry window
- [ ] Default behavior (24 hours) unchanged when the env variable is not set

---

## Story 4.7: Clean Up Dead Settings in `ndas/settings.py`

**Audit Findings:** DEAD-01, DEAD-02, DEAD-03, DEAD-04, DEAD-07, DEAD-08
**File:** `ndas/settings.py`
**Severity:** Low–Medium

### Description

Multiple dead or ineffective settings exist in `ndas/settings.py`:

- `DATABASE_ENGINE_OPTIONS` (DEAD-01) — MySQL-specific dict never referenced by `DATABASES` setting
- Duplicate module-level `CONN_MAX_AGE = 300` (DEAD-02) — Django reads this from `DATABASES['default']`, not module scope
- `COMPRESS_ENABLED` / `COMPRESS_OFFLINE` (DEAD-03) — `django-compressor` not installed or in `INSTALLED_APPS`
- `SECURE_BROWSER_XSS_FILTER = True` (DEAD-04) — deprecated since Django 4.0, removed in 5.0
- `MEDIA_URL_EXPIRY = 3600` and `SECURE_FILE_UPLOADS = True` (DEAD-07) — not Django settings, no effect
- `SILENCED_SYSTEM_CHECKS` for `security.W019` (DEAD-08) — suppresses deploy check without documented justification

### Acceptance Criteria

- [ ] `DATABASE_ENGINE_OPTIONS` dict removed
- [ ] Module-level `CONN_MAX_AGE = 300` (the redundant one at line ~447) removed — the `DATABASES['default']['CONN_MAX_AGE'] = 300` inside `if not DEBUG:` block preserved
- [ ] `COMPRESS_ENABLED` and `COMPRESS_OFFLINE` settings removed
- [ ] `SECURE_BROWSER_XSS_FILTER` removed
- [ ] `MEDIA_URL_EXPIRY` and `SECURE_FILE_UPLOADS` removed
- [ ] `SILENCED_SYSTEM_CHECKS` either removed (if W019 suppression is unjustified) or given an inline comment explaining why it is silenced
- [ ] `python manage.py check --deploy` runs cleanly (or any remaining warnings are expected and documented)
- [ ] Application starts and runs correctly after settings cleanup

---

## Story 4.8: Fix Session Backend for Development Environment

**Audit Finding:** CFG-01
**File:** `ndas/settings.py:397`
**Severity:** Low

### Description

`SESSION_ENGINE = 'django.contrib.sessions.backends.cache'` uses in-process `LocMemCache` in development, causing sessions to be wiped on every server restart and not shared between gunicorn workers. Should use `cached_db` backend for development safety.

### Acceptance Criteria

- [ ] In development (`DEBUG=True`), session engine uses `django.contrib.sessions.backends.cached_db`
- [ ] In production (`DEBUG=False` with Redis), session engine remains as `cache` (or `cached_db` is also acceptable)
- [ ] Sessions survive a server restart during development
- [ ] Login/logout continues to work correctly

---

## Story 4.9: Fix Race Condition in Middleware Cache Throttle

**Audit Finding:** CFG-02
**File:** `users/middleware.py:36–49`, `users/middleware.py:106–113`
**Severity:** Low

### Description

The middleware uses a non-atomic `cache.get()` → `cache.set()` pattern. Two concurrent requests from the same user can both see `last_update is None` before either sets the cache, causing duplicate DB writes. Use `cache.add()` which is atomic.

### Acceptance Criteria

- [ ] `cache.get()` + `cache.set()` pattern replaced with `cache.add()` for the session activity update throttle
- [ ] Pattern: `if cache.add(cache_key, True, 60): # perform the DB update`
- [ ] Both throttle locations in `users/middleware.py` updated (lines ~36–49 and ~106–113)
- [ ] Session activity tracking continues to function correctly under normal load
