# Story 2.8: Move `SECURE_HSTS_SECONDS` Inside `if not DEBUG:` Block

Status: done

## Story

As a developer working in the NDAS development environment,
I want `SECURE_HSTS_SECONDS` to only be set in production (`DEBUG=False`),
so that browsers connecting to the dev server do not cache a 1-year HSTS directive that blocks future HTTP access.

## Acceptance Criteria

1. `SECURE_HSTS_SECONDS = 31536000` removed from the unconditional Security Headers block (currently line 269).
2. `SECURE_HSTS_SECONDS = 0` added inside the `if DEBUG:` block.
3. `SECURE_HSTS_SECONDS = 31536000` added inside the `else:` block (production).
4. In DEBUG mode, `SECURE_HSTS_SECONDS` evaluates to `0` (no HSTS).
5. In production (`DEBUG=False`), `SECURE_HSTS_SECONDS` evaluates to `31536000` (1 year).

## Tasks / Subtasks

- [x] Task 1: Remove unconditional HSTS line (AC: #1) — `ndas/settings.py:269`
  - [x] Deleted: `SECURE_HSTS_SECONDS = 31536000  # 1 year`
- [x] Task 2: Add `SECURE_HSTS_SECONDS = 0` to `if DEBUG:` block (AC: #2) — now line 284
  - [x] Added as first line inside the `if DEBUG:` block, before existing CSP settings
- [x] Task 3: Add `SECURE_HSTS_SECONDS = 31536000  # 1 year` to `else:` block (AC: #3) — now line 296
  - [x] Added as first line inside the `else:` block, before existing production CSP settings
- [x] Task 4: Verify (AC: #4, #5)
  - [x] `python manage.py check` — system check clean (1 pre-existing ckeditor warning only)

## Dev Notes

### Current State — `ndas/settings.py:266–295`

```python
# Security Headers Configuration
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000  # 1 year   ← LINE 269 — DELETE THIS
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=False, cast=bool)
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if config(...) else None
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

if DEBUG:
    CSP_DEFAULT_SRC = ("'self'",)
    # ... dev CSP settings ...
    CSP_FORM_ACTION = ("'self'",)
else:
    # Production CSP - Strict policy ...
    CSP_DEFAULT_SRC = ("'self'",)
    # ... production CSP settings ...
    CSP_FORM_ACTION = ("'self'",)
```

### Required State After Fix

```python
# Security Headers Configuration
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
# SECURE_HSTS_SECONDS removed from here
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=False, cast=bool)
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if config(...) else None
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

if DEBUG:
    SECURE_HSTS_SECONDS = 0   # ← ADD: no HSTS in dev
    CSP_DEFAULT_SRC = ("'self'",)
    # ... dev CSP settings ...
    CSP_FORM_ACTION = ("'self'",)
else:
    SECURE_HSTS_SECONDS = 31536000  # 1 year   # ← ADD: production only
    # Production CSP - Strict policy ...
    CSP_DEFAULT_SRC = ("'self'",)
    # ... production CSP settings ...
    CSP_FORM_ACTION = ("'self'",)
```

### Why This Matters

When a browser connects to the dev server with `SECURE_HSTS_SECONDS = 31536000` active, it caches a `Strict-Transport-Security: max-age=31536000` header. For the next **365 days**, that browser will refuse any HTTP connection to `localhost` (or whatever dev host is used) and only attempt HTTPS. This breaks the dev server immediately for that browser.

Django only sends the HSTS header when the connection is over HTTPS. The dev server typically runs HTTP. However, if the dev server is ever accessed over HTTPS (e.g., through a local reverse proxy), the HSTS directive gets cached. Setting `SECURE_HSTS_SECONDS = 0` in DEBUG mode prevents this entirely.

### `SECURE_HSTS_INCLUDE_SUBDOMAINS` and `SECURE_HSTS_PRELOAD` Are Already Safe

Both are read from environment variables with `default=False`. In development without those env vars set, they are `False` — they don't cause the same caching problem because HSTS is only triggered when `SECURE_HSTS_SECONDS > 0`. Once `SECURE_HSTS_SECONDS` is `0` in DEBUG mode, these settings become irrelevant in dev. No change needed for them.

### Django `check --deploy` Reference

`python manage.py check --deploy` warns about missing HSTS. After this fix, running it with `DEBUG=False` will show `SECURE_HSTS_SECONDS = 31536000` correctly set. No warnings expected.

### No Migration Required

Settings-file-only change. No model, view, URL, or template changes.

### Project Structure Notes

- File changed: `ndas/settings.py` only — remove 1 line, add 2 lines inside existing if/else block

### References

- [Source: _bmad-output/planning-artifacts/epic-2-security.md#Story-2.8]
- [Source: docs/code-audit-adversarial-review.md#DEAD-09]
- [Source: ndas/settings.py:266–308 — Security Headers block and DEBUG if/else]
- [Source: Django docs — SECURE_HSTS_SECONDS: set to 0 to disable HSTS]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1 complete: Deleted `SECURE_HSTS_SECONDS = 31536000  # 1 year` from the unconditional Security Headers block (was line 269). AC #1 satisfied.
- Task 2 complete: Added `SECURE_HSTS_SECONDS = 0` as first line inside `if DEBUG:` block (`ndas/settings.py:284`). AC #2 and #4 satisfied.
- Task 3 complete: Added `SECURE_HSTS_SECONDS = 31536000  # 1 year` as first line inside `else:` block (`ndas/settings.py:296`). AC #3 and #5 satisfied.
- Task 4 complete: `python manage.py check` passes — system clean. Pre-existing ckeditor.W001 warning unchanged. AC #4 and #5 satisfied.

### File List

ndas/settings.py

## Change Log

- 2026-02-20: Implemented Story 2.8 — moved `SECURE_HSTS_SECONDS` from unconditional block into `if DEBUG:` / `else:` blocks in `ndas/settings.py`. Dev mode now sets `SECURE_HSTS_SECONDS = 0` (no HSTS caching); production keeps `SECURE_HSTS_SECONDS = 31536000` (1 year).
