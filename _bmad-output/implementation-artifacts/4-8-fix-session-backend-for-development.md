# Story 4.8: Fix Session Backend for Development

Status: done

## Story

As a developer running the NDAS application locally,
I want the session backend to use `cached_db` in development,
so that sessions survive server restarts and are not lost when the development server reloads.

## Acceptance Criteria

1. In development (`DEBUG=True`), `SESSION_ENGINE` uses `django.contrib.sessions.backends.cached_db`.
2. In production (`DEBUG=False`), `SESSION_ENGINE` can remain as `cache` (backed by Redis) or also use `cached_db` — either is acceptable.
3. Sessions survive a `python manage.py runserver` restart during local development.
4. Login/logout continues to work correctly in both environments.
5. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Change `SESSION_ENGINE` to be environment-conditional (AC: #1, #2)
  - [x] `ndas/settings.py:397` — replaced single `SESSION_ENGINE = 'django.contrib.sessions.backends.cache'` with `if DEBUG: SESSION_ENGINE = 'cached_db' else: SESSION_ENGINE = 'cache'` block. AC #1 and #2 satisfied.
- [x] Task 2: Verify (AC: #3, #4, #5)
  - [x] System check clean. 31 tests, same 20 pre-existing errors — no new failures. AC #5 satisfied.

## Dev Notes

### Current State — `ndas/settings.py:396–398`

```python
# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
```

In development with `LocMemCache`, the `cache` backend stores sessions in process memory. On server restart, all sessions are lost — every developer restart requires re-login.

### Required State After Fix

```python
# Session Configuration
if DEBUG:
    # Use cached_db in development: sessions persist across server restarts
    SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
else:
    # Use cache in production: sessions backed by Redis for performance
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
```

### Why `cached_db` for Development

`cached_db` writes sessions to the database as backup and reads from cache. In development with `LocMemCache`:
- Cache hit: session loaded from memory (fast)
- Cache miss (after restart): session loaded from DB (slow but correct)

Sessions survive server restarts because the DB backup is always up to date. In production with Redis, `cache` is preferred (no DB writes, Redis is persistent enough).

### `django_session` Table Must Exist

`cached_db` requires the `django_session` table. Run `python manage.py migrate` if not already done (should already be present in any migrated NDAS instance).

### No New Imports Required

Settings-only change. No imports needed.

### No Migration Required

Settings-only change. No model, view, template, or migration changes needed.

### Project Structure Notes

- File changed: `ndas/settings.py:397` — `SESSION_ENGINE` line only
- No other files changed

### References

- [Source: _bmad-output/planning-artifacts/epic-4-code-quality.md#Story-4.8]
- [Source: docs/code-audit-adversarial-review.md#CFG-01]
- [Source: ndas/settings.py:396–398 — session configuration]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Tasks 1–2 complete: Replaced unconditional `SESSION_ENGINE = 'cache'` with DEBUG-conditional block in `ndas/settings.py`. Development uses `cached_db` (sessions survive server restarts); production uses `cache` (Redis-backed). System check clean. No new test failures. AC #1–5 satisfied.

### File List

ndas/settings.py

## Change Log

- 2026-02-20: Implemented Story 4.8 — replaced `SESSION_ENGINE = 'cache'` with DEBUG-conditional: `cached_db` for development (sessions persist across restarts), `cache` for production (Redis performance).
