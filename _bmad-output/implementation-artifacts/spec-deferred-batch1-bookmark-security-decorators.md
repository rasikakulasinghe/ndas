---
title: 'Deferred-Work Batch 1: Bookmark/Security Decorators & Institution Guard Helper'
type: 'bugfix'
created: '2026-11-11'
status: 'done'
review_loop_iteration: 0
context: []
route: 'one-shot'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Four confirmed-still-open items from the restored `deferred-work.md` ledger: `bookmark_manager_user` and `bookmark_edit` lack the rate-limit/method decorators every other CRUD view in `patients/views.py` has; `InstitutionScopedManager` has no safe helper for call sites that must treat `institution=None` as "nothing" rather than "everything," so the guard is duplicated ad hoc in `referral/views.py`; and `Bookmark.get_bookmarked_object_url()` is dead, broken code with zero callers.

**Approach:** Mirror the existing, proven decorator patterns exactly (`bookmark_manager`'s rate limit for the GET-list view, `patient_edit`'s full stack for the GET+POST edit view); add `InstitutionScopedManager.for_institution_or_none()` and convert the 3 ad hoc call sites to use it; delete the dead method. Backfill `RESOLVED by:` on the four ledger entries this closes, and append new `defer` entries for pre-existing issues a review surfaced but which this narrow batch doesn't fix.

</frozen-after-approval>

## Suggested Review Order

1. [institution/managers.py](../../institution/managers.py) — new `for_institution_or_none()` helper + docstring.
2. [referral/views.py](../../referral/views.py) — 3 call sites converted to the new helper.
3. [patients/views.py](../../patients/views.py) — decorators added to `bookmark_manager_user` and `bookmark_edit`.
4. [patients/models.py](../../patients/models.py) — dead `get_bookmarked_object_url()` removed.
5. [institution/tests/test_isolation.py](../../institution/tests/test_isolation.py), [referral/tests/test_inbox.py](../../referral/tests/test_inbox.py) — new regression tests.
6. [_bmad-output/implementation-artifacts/deferred-work.md](deferred-work.md) — RESOLVED annotations + new defer entries.

