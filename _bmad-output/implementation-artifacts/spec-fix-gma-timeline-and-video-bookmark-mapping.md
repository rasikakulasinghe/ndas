---
title: 'Fix GMA timeline event drop and Video-bookmark wrong-app mapping'
type: 'bugfix'
created: '2026-09-01'
status: 'done'
review_loop_iteration: 0
context: []
route: 'one-shot'
---

# Fix GMA timeline drop and Video-bookmark mapping

## Intent

**Problem:** Two unrelated silent-data-loss bugs from the 2026-08-25 whole-app bmad-review: (1) `get_patient_timeline_events`'s GM Assessment event block referenced `gma.observation`, a field that doesn't exist on `GMAssessment` — the `AttributeError` was silently swallowed by a broad `except`, dropping every GM Assessment event from every patient's timeline; (2) `Bookmark`'s `model_mapping` mapped `bookmark_type='Video'` to the wrong Django app (`patients` instead of `video`), so `apps.get_model` raised `LookupError` for Video bookmarks specifically.

**Approach:** Fixed both narrow bugs. While writing a regression test for (2), discovered a broader sibling bug in the same method: the deliberately-raised `ValidationError` for a genuinely-missing bookmarked object was itself being swallowed by the same broad `except Exception` meant only for model-lookup failures — for every `bookmark_type`, not just Video. Fixed that too, which then surfaced two downstream robustness gaps in `patients/views.py` (`bookmark_add`, `bookmark_edit`) that had never had to handle a real validation failure before, since it never actually fired.

## Suggested Review Order

1. [patients/timeline_utils.py](../../patients/timeline_utils.py) — `gma.diagnosis_other` fix, empty-string-not-fallback-sentence for the JS ternary
2. [static/js/patient-timeline.js](../../static/js/patient-timeline.js) — `notes` key / "Additional Diagnosis:" label to match
3. [patients/models.py](../../patients/models.py) — `Bookmark.MODEL_MAPPING` (shared constant), `_validate_bookmarked_object`'s restructure (ValidationError now propagates), new `bookmarked_object_exists` property
4. [patients/views.py](../../patients/views.py) — `bookmark_add`'s `ValidationError` handling, `bookmark_edit`'s upfront orphan check (avoids a Django ModelForm crash — see Design Notes)
5. [patients/tests/test_timeline_utils.py](../../patients/tests/test_timeline_utils.py) (new), [patients/tests/test_models.py](../../patients/tests/test_models.py), [patients/tests/test_bookmark_security.py](../../patients/tests/test_bookmark_security.py), [ndas/tests/test_delete_helpers.py](../../ndas/tests/test_delete_helpers.py) — regression tests, incl. an existing fixture that only "passed" because validation was broken
6. [_bmad-output/implementation-artifacts/deferred-work.md](deferred-work.md) — 2 pre-existing entries marked resolved, 2 new follow-ups logged

## Code Map

- `patients/timeline_utils.py:199-205` -- GMA event `preview_data` -- field fix + empty-string fallback
- `static/js/patient-timeline.js:236-239` -- GMA preview template -- key/label match
- `patients/models.py` -- `Bookmark.MODEL_MAPPING`, `_validate_bookmarked_object`, `_get_bookmarked_object`, `bookmarked_object_exists` (new) -- core fix
- `patients/views.py` -- `bookmark_add`, `bookmark_edit` -- downstream robustness fixes required once validation actually fires

## Tasks & Acceptance

**Execution:**
- [x] `patients/timeline_utils.py` -- use `gma.diagnosis_other`, empty string (not a sentence) when absent -- fix the crash without breaking the JS preview's conditional row
- [x] `static/js/patient-timeline.js` -- rename `observation`→`notes` key, relabel "Additional Diagnosis:" -- match the field's actual meaning
- [x] `patients/models.py` -- fix `'Video': ("video", "Video")` in both mapping dicts, factor into `Bookmark.MODEL_MAPPING` -- close the LookupError and prevent the two dicts drifting again
- [x] `patients/models.py` -- restructure `_validate_bookmarked_object` so the deliberate `ValidationError` propagates instead of being caught by the lookup-failure `except` -- close the broader swallowed-validation bug
- [x] `patients/models.py` -- add `bookmarked_object_exists` (cheap `.exists()` check) -- avoid an unnecessary full-object fetch in `bookmark_edit`'s pre-check
- [x] `patients/views.py::bookmark_add` -- add a dedicated `except ValidationError` branch -- stop leaking a raw error-dict repr to users
- [x] `patients/views.py::bookmark_edit` -- check `bookmarked_object_exists` before calling `bm_form_data.is_valid()` -- avoid a Django-internal `ValueError` crash (see Design Notes) and a broken redirect target
- [x] `ndas/tests/test_delete_helpers.py` -- update a fixture that only "passed" because validation was broken (`bookmark_type='Video', object_id=1` with no real Video row) -- use a real Patient instead
- [x] Regression tests across `patients/tests/test_timeline_utils.py` (new), `test_models.py`, `test_bookmark_security.py` -- verify both original bugs, the broader swallowed-validation bug (non-Video type), and the two downstream view fixes (incl. GET and a Video-type orphan case)
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- mark 2 pre-existing entries RESOLVED, log 2 new out-of-scope follow-ups (a pre-existing `bookmark_view` design flaw discovered along the way; test-fixture duplication)

**Acceptance Criteria:**
- Given a patient with a GM Assessment, when their timeline is built, then a `'gma'` event appears with `notes` set to `diagnosis_other` (or `''` if absent) (verified).
- Given a `Bookmark(bookmark_type='Video', object_id=<real video pk>)`, when saved, then it succeeds and `bookmarked_object`/`bookmarked_object_title` resolve to that Video (verified); a bogus `object_id` for **any** bookmark_type now raises `ValidationError` (verified for both `Video` and `Patient`).
- Given a bookmark whose target was deleted, when its owner opens `bookmark_edit` (GET or POST), then they're redirected to their bookmark list with a clean message, not a 500 (verified for `Patient`- and `Video`-type bookmarks).

## Design Notes

The `bookmark_edit` crash was two layers deep: `BookmarkForm.Meta.fields = ['title', 'description']` excludes `object_id`, so when the model's `full_clean()` (run inside Django's `ModelForm._post_clean()`, itself called from `is_valid()`) raises a `ValidationError` keyed on `object_id`, Django's `_update_errors` can't map that key onto a declared form field and raises `ValueError` from deep inside `django/forms/forms.py` — before any code in `bookmark_edit` gets a chance to catch it. A `try/except ValidationError` around `.save()` alone (my first attempt) doesn't help, because the crash happens earlier, inside `is_valid()` itself. The fix instead checks existence upfront, before the form is ever validated.

## Verification

**Commands:**
- `python manage.py test patients.tests.test_timeline_utils patients.tests.test_models patients.tests.test_bookmark_security ndas.tests.test_delete_helpers -v 1` -- expected: `OK` (25/25, verified)
- `python manage.py test patients ndas -v 1` -- expected: only the same ~18 pre-existing `PatientManagerTestCase`/`DashboardTestCase` failures already logged in `deferred-work.md`, none new (verified: 158 tests, 18 pre-existing failures, 0 new)
