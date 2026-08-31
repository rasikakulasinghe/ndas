---
title: 'Fix users institution-scoping gap and missing update_session_auth_hash'
type: 'bugfix'
created: '2026-08-31'
status: 'done'
review_loop_iteration: 0
context: []
route: 'one-shot'
---

# Fix users institution-scoping gap and session-hash bug

## Intent

**Problem:** Two unrelated bugs in `users/views.py` from the 2026-08-25 whole-app bmad-review: (1) four sibling admin views (`admin_user_edit`, `admin_user_delete`, `admin_user_toggle_status`, `admin_user_activity`) used `get_object_or_404(CustomUser, pk=pk)` with no institution filter, unlike `userView`/`userViewByUsername`/`admin_user_list`/`admin_activity_logs` — a non-superuser staff account could edit/deactivate/delete/inspect-activity of a user at a completely different institution; (2) `userChangePassword` never called `update_session_auth_hash` after `form.save()`, so a user changing their own password was silently logged out on the very next request.

**Approach:** Extracted the existing `userView`/`userViewByUsername` institution-scoping pattern into a shared `get_institution_scoped_user_or_404()` helper and applied it to all six pk/username-lookup views, so the exact IDOR class can't be reintroduced by a future view forgetting to copy the inline pattern. Added `update_session_auth_hash(request, form.user)` right after `form.save()` in `userChangePassword`.

## Suggested Review Order

1. [users/views.py](../../users/views.py) — `get_institution_scoped_user_or_404()` (new helper) and its six call sites (`userView`, `userViewByUsername`, `admin_user_edit`, `admin_user_delete`, `admin_user_toggle_status`, `admin_user_activity`)
2. [users/views.py](../../users/views.py) — `userChangePassword`'s `update_session_auth_hash` call
3. [users/tests/test_security.py](../../users/tests/test_security.py) — `AdminUserCrudInstitutionScopingTest` (full cross/same-institution/superuser matrix for all four views) and `ChangePasswordSessionTest`
4. [_bmad-output/implementation-artifacts/deferred-work.md](deferred-work.md) — follow-ups logged from blind-hunter review

## Code Map

- `users/views.py` -- `get_institution_scoped_user_or_404()` (new) -- single source of truth for the pk/username institution-scoping pattern
- `users/views.py` -- `userView`, `userViewByUsername`, `admin_user_edit`, `admin_user_delete`, `admin_user_toggle_status`, `admin_user_activity` -- all now call the shared helper
- `users/views.py` -- `userChangePassword` -- `update_session_auth_hash(request, form.user)` added after `form.save()`

## Tasks & Acceptance

**Execution:**
- [x] `users/views.py` -- add `get_institution_scoped_user_or_404(request, **lookup)` -- consolidates the scoping pattern, treats a missing `request.institution` attribute (Phase 1 / `MULTI_INSTITUTION_ENABLED=False`) as `None` instead of raising `AttributeError`
- [x] `users/views.py` -- apply the helper to `userView`, `userViewByUsername`, `admin_user_edit`, `admin_user_delete`, `admin_user_toggle_status`, `admin_user_activity` -- close the IDOR on the four previously-unscoped views, deduplicate the two already-scoped ones
- [x] `users/views.py` -- add `update_session_auth_hash(request, form.user)` to `userChangePassword` -- fix the silent-logout bug
- [x] `users/tests/test_security.py` -- add `AdminUserCrudInstitutionScopingTest` (cross-institution 404, same-institution 200/302, superuser-bypass 200/302, for all four views; GET+POST for edit) and `ChangePasswordSessionTest` (success + failure paths) -- verify both fixes
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- log out-of-scope follow-ups (is_superuser vs. UserType.SUPERADMIN divergence risk; the narrower "two different not-yet-onboarded institutions" edge case, deliberately not fixed after it was found to break intentional, tested behavior)

**Acceptance Criteria:**
- Given a non-superuser staff user at institution A, when they GET or POST `admin_user_edit`/`admin_user_delete`/`admin_user_toggle_status`/`admin_user_activity` for a pk belonging to institution B, then all four return 404 and make no state change (verified).
- Given the same staff user acting on a user at their own institution, then all four succeed (200/302 as appropriate) (verified); a superuser succeeds regardless of institution (verified).
- Given a user who successfully changes their own password via `userChangePassword`, when they make an immediately-following authenticated request, then it succeeds (200), not a login redirect (verified). A rejected password-change attempt (wrong old password) leaves the session and password unchanged (verified).

## Verification

**Commands:**
- `python manage.py test users -v 1` -- expected: `OK` (39/39, verified)
- `python manage.py test users institution -v 1` -- expected: only the 2 pre-existing failures already logged in `deferred-work.md` (`institution.tests.test_clinician_management`, `institution.tests.test_models`), none new (verified: 226 tests, 2 pre-existing failures, 0 new)
