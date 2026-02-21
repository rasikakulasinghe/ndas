# Story 4.6: Fix `EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS` Setting Not Used in Model

Status: done

## Story

As a system administrator,
I want the email verification token expiry to be controlled by the `EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS` environment variable,
so that I can extend or shorten the expiry window via `.env` without modifying source code.

## Acceptance Criteria

1. `users/models.py:153` — `timedelta(hours=24)` replaced with `timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS)`.
2. `from django.conf import settings` added to `users/models.py` imports (if not already present).
3. Setting `EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS=48` in `.env` results in a 48-hour expiry.
4. Default behavior (24 hours) unchanged when `EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS` is not set in `.env` (the setting in `ndas/settings.py:189` defaults to `24`).
5. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Check if `from django.conf import settings` already in `users/models.py` (AC: #2)
  - [x] Grep confirmed absent. Added `from django.conf import settings` to imports in `users/models.py`. AC #2 satisfied.
- [x] Task 2: Replace hardcoded `timedelta(hours=24)` (AC: #1)
  - [x] `users/models.py:153` — replaced `timedelta(hours=24)` with `timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS)`. Updated docstring to remove hardcoded "(24 hours)". AC #1 satisfied.
- [x] Task 3: Verify (AC: #3, #4, #5)
  - [x] `ndas/settings.py:189` confirmed: `EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS = config('EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS', default=24, cast=int)`. AC #3 and #4 satisfied.
  - [x] 31 tests, same 20 pre-existing errors — no new failures. AC #5 satisfied.

## Dev Notes

### Current State — `users/models.py:149–154`

```python
def is_email_verification_token_valid(self):
    """Check if the email verification token is still valid (24 hours)."""
    if not self.email_verification_sent_at:
        return False
    expiry_time = self.email_verification_sent_at + timedelta(hours=24)  # ← hardcoded
    return timezone.now() < expiry_time
```

### Required State After Fix

```python
def is_email_verification_token_valid(self):
    """Check if the email verification token is still valid."""
    if not self.email_verification_sent_at:
        return False
    expiry_time = self.email_verification_sent_at + timedelta(
        hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS
    )
    return timezone.now() < expiry_time
```

### Settings Configuration — Already Correct

```python
# ndas/settings.py:189 — already reads from .env with correct default
EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS = config(
    'EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS', default=24, cast=int
)
```

The setting infrastructure is already in place. Only the model is missing the reference.

### `timedelta` Already Imported in `users/models.py`

```python
# users/models.py — confirm timedelta is already imported
from datetime import timedelta
```

(Verify — but it is used on line 153, so it must be imported.)

### No Migration Required

Change to a model method body only — no model field changes. No migrations, templates, or URLs changed.

### Project Structure Notes

- File changed: `users/models.py` — line 153 only; possibly add `from django.conf import settings` to imports
- No other files changed

### References

- [Source: _bmad-output/planning-artifacts/epic-4-code-quality.md#Story-4.6]
- [Source: docs/code-audit-adversarial-review.md#CFG-03]
- [Source: users/models.py:148–155 — is_email_verification_token_valid method]
- [Source: ndas/settings.py:189 — EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS setting definition]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Tasks 1–3 complete: Added `from django.conf import settings` to `users/models.py` imports (was absent). Replaced `timedelta(hours=24)` with `timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS)` in `is_email_verification_token_valid`. Setting confirmed at `ndas/settings.py:189` with `default=24`. System check clean. No new test failures. AC #1–5 satisfied.

### File List

users/models.py

## Change Log

- 2026-02-20: Implemented Story 4.6 — added `from django.conf import settings` to `users/models.py` and replaced `timedelta(hours=24)` with `timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS)` in `is_email_verification_token_valid`. Token expiry is now configurable via `EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS` env var (default 24).
