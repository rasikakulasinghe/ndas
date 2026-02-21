# Story 4.9: Fix Race Condition in Middleware Cache Throttle

Status: done

## Story

As a system administrator,
I want the session activity and subscription status throttle in middleware to be race-condition-free,
so that concurrent requests from the same user do not cause duplicate database writes.

## Acceptance Criteria

1. `cache.get()` + `if last_update is None: cache.set(...)` pattern replaced with `cache.add()` at `users/middleware.py:36–49` (session activity throttle).
2. Same replacement at `users/middleware.py:106–113` (subscription status throttle).
3. Session activity tracking and subscription status checking continue to function correctly under normal load.
4. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Fix session activity throttle (AC: #1)
  - [x] `users/middleware.py` — replaced `cache.get(cache_key)` + `if last_update is None: ... cache.set(cache_key, timezone.now(), 60)` with `if cache.add(cache_key, True, 60):`. Removed now-redundant `cache.set()` call. AC #1 satisfied.
- [x] Task 2: Fix subscription status throttle (AC: #2)
  - [x] `users/middleware.py` — replaced `cache.get(update_cache_key)` + `if last_update is None: ... cache.set(update_cache_key, True, 60)` with `if cache.add(update_cache_key, True, 60):`. Removed now-redundant `cache.set()` call. AC #2 satisfied.
- [x] Task 3: Verify (AC: #3, #4)
  - [x] System check clean. 31 tests, same 20 pre-existing errors — no new failures. AC #3 and #4 satisfied.

## Dev Notes

### Why `cache.get()` + `cache.set()` Is a Race Condition

The current pattern:
```python
last_update = cache.get(cache_key)
if last_update is None:
    # perform DB write
    cache.set(cache_key, timezone.now(), 60)
```

Two concurrent requests from the same user/session can both execute `cache.get()` and both see `last_update is None` before either sets the cache. Both then proceed to the `if` body and issue duplicate DB writes.

`cache.add(key, value, timeout)` is **atomic** — it only sets the key if it does not already exist, in a single cache operation. If two requests race, only one wins the `cache.add()` and executes the DB write. The other sees `False` returned from `cache.add()` and skips the write.

### Current State — Session Activity Throttle (`users/middleware.py:36–49`)

```python
from django.core.cache import cache
cache_key = f"user_session_update_{request.user.id}_{session_key}"
last_update = cache.get(cache_key)          # ← get

if last_update is None:
    # Update session activity
    UserSession.objects.filter(...).update(last_activity=timezone.now())
    cache.set(cache_key, timezone.now(), 60) # ← set
```

### Required State After Fix — Session Activity Throttle

```python
from django.core.cache import cache
cache_key = f"user_session_update_{request.user.id}_{session_key}"
if cache.add(cache_key, True, 60):          # ← atomic add: only succeeds once per 60s
    # Update session activity
    UserSession.objects.filter(...).update(last_activity=timezone.now())
# No cache.set() needed — cache.add() already set the key
```

### Current State — Subscription Status Throttle (`users/middleware.py:106–113`)

```python
update_cache_key = f'subscription_last_update_{subscription.pk}'
last_update = cache.get(update_cache_key)   # ← get

if last_update is None:
    subscription.update_status()
    cache.set(update_cache_key, True, 60)   # ← set
```

### Required State After Fix — Subscription Status Throttle

```python
update_cache_key = f'subscription_last_update_{subscription.pk}'
if cache.add(update_cache_key, True, 60):   # ← atomic add
    subscription.update_status()
# No cache.set() needed
```

### `cache.add()` Semantics

- Returns `True` if the key was set (key did not exist before)
- Returns `False` if the key already existed (another request got there first)
- Atomicity guarantee: both the existence check and the set happen as one operation in the cache backend (LocMemCache, Redis, Memcached all support this)

### With `LocMemCache` in Development

`LocMemCache.add()` uses a lock internally, so it is safe even in development. The fix works correctly regardless of cache backend.

### No New Imports Required

`cache` is already imported locally inside the middleware method (`from django.core.cache import cache`).

### No Migration Required

Middleware logic change only. No models, views, templates, or migrations changed.

### Project Structure Notes

- File changed: `users/middleware.py` — lines ~36–49 and ~106–113
- No other files changed

### References

- [Source: _bmad-output/planning-artifacts/epic-4-code-quality.md#Story-4.9]
- [Source: docs/code-audit-adversarial-review.md#CFG-02]
- [Source: users/middleware.py:34–52 — session activity cache throttle]
- [Source: users/middleware.py:104–115 — subscription status cache throttle]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Tasks 1–3 complete: Replaced both `cache.get()` + `if None: cache.set()` race-prone patterns in `users/middleware.py` with atomic `cache.add()`. Session activity throttle (line ~38) and subscription status throttle (line ~107) both updated. No `cache.set()` needed after `cache.add()` — the add itself sets the key. System check clean. No new test failures. AC #1–4 satisfied.

### File List

users/middleware.py

## Change Log

- 2026-02-20: Implemented Story 4.9 — replaced race-prone `cache.get()` + `cache.set()` patterns with atomic `cache.add()` in `users/middleware.py` for both the session activity throttle and subscription status throttle.
