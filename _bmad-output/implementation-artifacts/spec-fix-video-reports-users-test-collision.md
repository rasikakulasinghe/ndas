---
title: 'Fix video/reports/users test-collection collision'
type: 'bugfix'
created: '2026-08-31'
status: 'done'
review_loop_iteration: 0
context: []
route: 'one-shot'
---

# Fix video/reports/users test-collection collision

## Intent

**Problem:** `video/tests.py`, `reports/tests.py`, and `users/tests.py` each collided with a sibling `tests/` package (`video/tests/`, `reports/tests/`, `users/tests/`) in the same app, causing Python's `unittest` loader to raise `ImportError` and crash `python manage.py test` before any test executes — for the whole project, not just those apps.

**Approach:** Deleted `reports/tests.py` (an empty Django boilerplate stub with nothing to preserve). Moved `video/tests.py` and `users/tests.py` into their respective `tests/` packages as `test_crud.py`, fixing one stale assertion in the moved video test (`test_other_staff_can_edit_video` asserted 200 for a non-owner staff user, contradicting `video_edit`'s actual `is_superuser`-based permission check and the already-passing `video/tests/test_security.py`).

## Suggested Review Order

1. [reports/tests.py](../../reports/tests.py) — deleted (empty stub, collided with `reports/tests/`)
2. [video/tests/test_crud.py](../../video/tests/test_crud.py) — moved from `video/tests.py`; stale assertion fixed, one new edge-case test added
3. [users/tests/test_crud.py](../../users/tests/test_crud.py) — moved from `users/tests.py`, no content changes
4. [CLAUDE.md](../../CLAUDE.md) — added a `Never` rule against reintroducing this collision
5. [_bmad-output/implementation-artifacts/deferred-work.md](deferred-work.md) — logged 45 pre-existing test failures newly surfaced by this fix, plus follow-ups raised by review

## Code Map

- `reports/tests.py` -- deleted; empty stub colliding with `reports/tests/`
- `video/tests.py` -- moved to `video/tests/test_crud.py`; collided with `video/tests/`
- `video/tests/test_crud.py` -- CRUD test suite for the video app; one stale assertion corrected, one new test added
- `video/tests/test_security.py` -- unaffected; already-passing sibling test confirming the corrected permission behavior
- `users/tests.py` -- moved to `users/tests/test_crud.py`; collided with `users/tests/`
- `users/tests/test_crud.py` -- CRUD test suite for the users app; pure move, no content changes
- `video/views.py:155-160` -- `video_edit`'s permission check (`not is_superuser and added_by != user`), the ground truth the corrected test now matches
- `CLAUDE.md` -- added a `Never` rule against reintroducing a top-level `tests.py` alongside an existing `tests/` package

## Tasks & Acceptance

**Execution:**
- [x] `reports/tests.py` -- delete -- empty stub colliding with `reports/tests/`, nothing to preserve
- [x] `video/tests.py` -- move to `video/tests/test_crud.py` -- resolve collision with `video/tests/`
- [x] `video/tests/test_crud.py` -- fix `test_other_staff_can_edit_video` to `test_other_staff_cannot_edit_video` asserting 302 -- matches actual `video_edit` permission check and sibling `test_security.py`
- [x] `video/tests/test_crud.py` -- add `test_non_owner_non_staff_cannot_edit_video` -- close coverage gap on the corrected permission check (blind-hunter finding)
- [x] `video/tests/test_crud.py` -- align `test_other_staff_can_view_video`'s comment with the corrected test's style -- consistency (blind-hunter finding)
- [x] `video/tests/test_crud.py`, `users/tests/test_crud.py` -- add module docstring note on why the file lives under `tests/` -- prevent recollision (blind-hunter finding)
- [x] `users/tests.py` -- move to `users/tests/test_crud.py` -- resolve collision with `users/tests/`
- [x] `CLAUDE.md` -- add `Never` rule against top-level `tests.py` colliding with a `tests/` package -- prevent regression (blind-hunter finding)
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- log 45 pre-existing failures/errors surfaced by this fix, plus reports-CRUD-coverage-gap and video-fixture-noise blind-hunter findings -- out of scope here, tracked for follow-up

**Acceptance Criteria:**
- Given the fixed repo, when `python manage.py test video reports users` runs, then it collects and runs 59 tests with `OK` (verified; re-verified 53 tests `OK` after blind-hunter patches, reports run separately since it has no CRUD suite to add tests to).
- Given the fixed repo, when bare `python manage.py test` runs, then it collects and executes all 482 tests to completion (verified) instead of crashing at import time (as it did before this fix) — the run still reports 45 pre-existing failures/errors unrelated to this fix, none in `video/`, `reports/`, or `users/` (all logged to `deferred-work.md`).
- Given `video/tests/test_crud.py::VideoEditViewTest`, when a non-owner, non-superuser staff user or a non-owner, non-staff user requests `video:edit`, then both get HTTP 302 (verified), matching `video/tests/test_security.py::test_staff_cannot_edit_peer_video`.

## Verification

**Commands:**
- `python manage.py test video reports users -v 1` -- expected: `OK`, no `ImportError` at collection (59 tests before blind-hunter patches; 53 after, reports counted separately)
- `python manage.py test -v 1` -- expected: collects and runs all 482 tests to completion (45 pre-existing failures/errors remain, none in video/reports/users; tracked in `deferred-work.md`)
