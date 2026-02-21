# Story 2.6: Fix Login Rate Limit to Prevent Username Enumeration

Status: done

## Story

As a security-conscious developer,
I want the login view's rate limiting to be keyed on IP address instead of username,
so that an attacker cannot enumerate valid usernames by observing which username-specific buckets trigger a 429.

## Acceptance Criteria

1. Rate limit key changed from `post:username` to `ip` on the login view (`users/views.py:33`).
2. Rate is `3/m` (unchanged) or stricter.
3. Both valid and invalid usernames receive the same 429 response when the IP limit is hit — no differential behavior.
4. Username enumeration via differential 429 responses is no longer possible.

## Tasks / Subtasks

- [x] Task 1: Change rate limit key on `loginPage` (AC: #1, #2) — `users/views.py:33`
  - [x] Change `key='post:username'` to `key='ip'` on line 33
  - [x] Keep `rate='3/m'`, `method='POST'`, `block=True` unchanged
- [x] Task 2: Verify (AC: #3, #4)
  - [x] `python manage.py test users` — no failures
  - [x] Confirm login still works for valid credentials after change

## Dev Notes

### Current State — `users/views.py:32–34`

```python
@ratelimit(key='ip', rate='5/m', method='POST', block=True)          # line 32
@ratelimit(key='post:username', rate='3/m', method='POST', block=True)  # line 33  ← CHANGE THIS
def loginPage(request):
```

### Required State After Fix

```python
@ratelimit(key='ip', rate='5/m', method='POST', block=True)    # line 32 (unchanged)
@ratelimit(key='ip', rate='3/m', method='POST', block=True)    # line 33 (key changed)
def loginPage(request):
```

**One-word change: `post:username` → `ip` on line 33. Nothing else changes.**

### Why `post:username` Enables Enumeration

With `key='post:username'`, each username gets its own rate limit bucket. An attacker can submit one POST per unique username indefinitely:

```
POST username=alice  password=wrong  → 200 (1/3 for alice bucket)
POST username=bob    password=wrong  → 200 (1/3 for bob bucket)
POST username=carol  password=wrong  → 200 (1/3 for carol bucket)
... repeat for 10,000 usernames, never hitting any bucket's limit
```

With `key='ip'`, all login attempts from an IP share one bucket:

```
POST username=alice  → 200 (1/3 for this IP)
POST username=bob    → 200 (2/3 for this IP)
POST username=carol  → 429 (3/3 exhausted — blocked regardless of username)
```

Now every username gets the same 429 response from the same IP after 3 total attempts.

### After the Fix: Two IP Limiters on the Same View

The view will have two IP-based limiters:
- `key='ip', rate='5/m'` (line 32 — unchanged)
- `key='ip', rate='3/m'` (line 33 — fixed)

Both check the same IP independently. The stricter one (`3/m`) always fires first, making the `5/m` limiter redundant. This is harmless — Django ratelimit short-circuits on first `Ratelimited` exception. You can leave both in place; they do not conflict.

### No Import Changes Needed

`ratelimit` is already imported in `users/views.py:17`: `from django_ratelimit.decorators import ratelimit`

### Existing Security Context in the Login View

The view already has several enumeration-prevention measures (worth knowing — do not disturb):
- Line 59–60: Comment notes always calling `authenticate()` instead of checking username existence first
- Line 61: `user = authenticate(request, username=username, password=password)` — constant-time regardless of username validity
- Same error message for wrong username vs wrong password (`'Invalid username or password. Please try again.'` at line 189)

The rate limit fix completes the anti-enumeration picture: responses are now identical *and* rate limiting doesn't create differential 429 buckets.

### No Migration Required

Single decorator key change. No model, URL, or template changes.

### Project Structure Notes

- File changed: `users/views.py` only — one word changed on line 33
- No imports to add or remove

### References

- [Source: _bmad-output/planning-artifacts/epic-2-security.md#Story-2.6]
- [Source: docs/code-audit-adversarial-review.md#SEC-06]
- [Source: users/views.py:32–34 — loginPage decorator stack]
- [Source: users/views.py:59–61 — existing timing-attack prevention context]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1 complete: Changed `key='post:username'` to `key='ip'` on `users/views.py:32`. `rate='3/m'`, `method='POST'`, `block=True` unchanged. Both rate limiters now key on IP; no username-differential 429 buckets possible. AC #1–4 satisfied.
- Task 2 complete: System check clean, regression tests pass. AC #3 and #4 satisfied.

### File List

users/views.py

## Change Log

- 2026-02-20: Implemented Story 2.6 — changed login rate limit key from `post:username` to `ip` in `users/views.py`. All login attempts from an IP now share one bucket, preventing username enumeration via differential 429 responses.
- 2026-02-20: Code review fix — removed redundant `@ratelimit(key='ip', rate='5/m', ...)` decorator. After the Story 2.6 change, both decorators used `key='ip'`; the `5/m` limiter was a dead constraint since the `3/m` one is always stricter. Only `@ratelimit(key='ip', rate='3/m', method='POST', block=True)` remains.
