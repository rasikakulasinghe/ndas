# Story 4.7: Clean Up Dead Settings in `ndas/settings.py`

Status: done

## Story

As a developer maintaining the NDAS codebase,
I want dead and ineffective settings removed from `ndas/settings.py`,
so that the settings file reflects the actual runtime configuration and does not mislead future developers.

## Acceptance Criteria

1. `DATABASE_ENGINE_OPTIONS` dict (~lines 416–421) removed — it is MySQL-specific and never referenced by `DATABASES`.
2. Module-level `CONN_MAX_AGE = 300` (~line 447) removed — this is inside `if not DEBUG:` block but at module scope, not inside `DATABASES['default']`. The correct setting at line 112 (`DATABASES['default']['CONN_MAX_AGE'] = 300` inside `if not DEBUG:`) is preserved.
3. `COMPRESS_ENABLED` and `COMPRESS_OFFLINE` (~lines 439–440) removed — `django-compressor` is not installed.
4. `SECURE_BROWSER_XSS_FILTER = True` removed from both locations (~line 267 and ~line 444) — deprecated since Django 4.0, removed in 5.0, has no effect.
5. `MEDIA_URL_EXPIRY = 3600` and `SECURE_FILE_UPLOADS = True` (~lines 428–429) removed — these are not valid Django settings and have no effect.
6. `SILENCED_SYSTEM_CHECKS` (~line 432) — add an inline comment explaining why W019 is silenced, or remove it if the suppression is not justified for this deployment.
7. Application starts cleanly after settings cleanup.
8. `python manage.py check --deploy` runs without unexpected new warnings.
9. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Remove `DATABASE_ENGINE_OPTIONS` (AC: #1)
  - [x] Removed `# Database Query Optimization` comment and `DATABASE_ENGINE_OPTIONS = {...}` block (5 lines). AC #1 satisfied.
- [x] Task 2: Remove module-level duplicate `CONN_MAX_AGE` (AC: #2)
  - [x] Removed `# Database optimizations` comment and `CONN_MAX_AGE = 300` from inside `if not DEBUG:` block. `DATABASES['default']['CONN_MAX_AGE'] = 300` at line 112 confirmed preserved. Grep confirms only 1 occurrence remains (correct one). AC #2 satisfied.
- [x] Task 3: Remove `COMPRESS_ENABLED` and `COMPRESS_OFFLINE` (AC: #3)
  - [x] Removed `# Enable compression` comment, `COMPRESS_ENABLED`, and `COMPRESS_OFFLINE` lines from `if not DEBUG:` block. AC #3 satisfied.
- [x] Task 4: Remove both `SECURE_BROWSER_XSS_FILTER` occurrences (AC: #4)
  - [x] Removed `SECURE_BROWSER_XSS_FILTER = True` from `# Security Headers Configuration` block (~line 267) and from `# Security enhancements` block inside `if not DEBUG:` (~line 444). AC #4 satisfied.
- [x] Task 5: Remove `MEDIA_URL_EXPIRY` and `SECURE_FILE_UPLOADS` (AC: #5)
  - [x] Removed `# Media Files Security` comment, `MEDIA_URL_EXPIRY = 3600`, and `SECURE_FILE_UPLOADS = True`. AC #5 satisfied.
- [x] Task 6: Document `SILENCED_SYSTEM_CHECKS` (AC: #6)
  - [x] Expanded comment from `# Only if using HTTPS proxy` to `# Silenced when nginx/load balancer terminates SSL and SECURE_PROXY_SSL_HEADER is set in .env`. Setting retained as it is conditionally applied only when proxy SSL header is configured. AC #6 satisfied.
- [x] Task 7: Verify (AC: #7, #8, #9)
  - [x] System check clean (only pre-existing ckeditor.W001 warning). Grep confirms all dead settings removed and correct `CONN_MAX_AGE` preserved. 31 tests, same 20 pre-existing errors — no new failures. AC #7, #8, #9 satisfied.

## Dev Notes

### Dead Settings Summary

| Setting | Location | Why Dead |
|---|---|---|
| `DATABASE_ENGINE_OPTIONS` | ~lines 416–421 | MySQL-specific dict; SQLite/Postgres `DATABASES` config never references it |
| `CONN_MAX_AGE = 300` (module-level) | ~line 447 | Django reads `CONN_MAX_AGE` from `DATABASES['default']`, not module scope. The correct one is at line 112. |
| `COMPRESS_ENABLED` | ~line 439 | `django-compressor` not in `INSTALLED_APPS` or `requirements.txt` |
| `COMPRESS_OFFLINE` | ~line 440 | Same reason as `COMPRESS_ENABLED` |
| `SECURE_BROWSER_XSS_FILTER` | ~lines 267, 444 | Deprecated in Django 4.0, removed in 5.0; setting is parsed but ignored |
| `MEDIA_URL_EXPIRY` | ~line 428 | Not a Django setting; no Django mechanism reads this |
| `SECURE_FILE_UPLOADS` | ~line 429 | Not a Django setting; no Django mechanism reads this |

### The Correct `CONN_MAX_AGE` Location

```python
# ndas/settings.py:111–112 — KEEP THIS (correct location inside DATABASES config)
if not DEBUG:
    DATABASES['default']['CONN_MAX_AGE'] = 300
```

The duplicate at ~line 447 (`CONN_MAX_AGE = 300` at module scope) has no effect — Django only reads `CONN_MAX_AGE` from the `DATABASES` dict.

### `SILENCED_SYSTEM_CHECKS` Context

```python
# Current state
SILENCED_SYSTEM_CHECKS = [
    'security.W019',  # Only if using HTTPS proxy
] if config('SECURE_PROXY_SSL_HEADER', default=False, cast=bool) else []
```

`W019` warns about missing `SECURE_PROXY_SSL_HEADER`. If the deployment uses an SSL proxy (nginx terminates HTTPS, Django runs plain HTTP behind it), and `SECURE_PROXY_SSL_HEADER` is set in `.env`, this silencing is justified. The comment should be expanded to make this explicit.

### No Migration Required

Settings-only cleanup. No models, views, templates, or migrations changed.

### Project Structure Notes

- File changed: `ndas/settings.py` only
- No other files changed

### References

- [Source: _bmad-output/planning-artifacts/epic-4-code-quality.md#Story-4.7]
- [Source: docs/code-audit-adversarial-review.md#DEAD-01, #DEAD-02, #DEAD-03, #DEAD-04, #DEAD-07, #DEAD-08]
- [Source: ndas/settings.py:110–113 — correct CONN_MAX_AGE in DATABASES (keep)]
- [Source: ndas/settings.py:267,416–447 — dead settings (remove)]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Tasks 1–7 complete: Removed 7 dead settings from `ndas/settings.py`. `DATABASE_ENGINE_OPTIONS` block (MySQL-specific, never referenced) removed. Module-level `CONN_MAX_AGE = 300` duplicate removed; correct `DATABASES['default']['CONN_MAX_AGE'] = 300` at line 112 preserved. `COMPRESS_ENABLED` and `COMPRESS_OFFLINE` removed (django-compressor not installed). Both `SECURE_BROWSER_XSS_FILTER = True` occurrences removed (deprecated Django 4.0, no-op in 5.0). `MEDIA_URL_EXPIRY` and `SECURE_FILE_UPLOADS` removed (not valid Django settings). `SILENCED_SYSTEM_CHECKS` comment expanded to explain W019 suppression context. System check clean. No new test failures. AC #1–9 satisfied.

### File List

ndas/settings.py

## Change Log

- 2026-02-20: Implemented Story 4.7 — removed 7 dead settings from `ndas/settings.py`: `DATABASE_ENGINE_OPTIONS`, duplicate module-level `CONN_MAX_AGE`, `COMPRESS_ENABLED`, `COMPRESS_OFFLINE`, both `SECURE_BROWSER_XSS_FILTER` occurrences, `MEDIA_URL_EXPIRY`, `SECURE_FILE_UPLOADS`. Expanded `SILENCED_SYSTEM_CHECKS` W019 comment. Correct `DATABASES['default']['CONN_MAX_AGE']` preserved.
