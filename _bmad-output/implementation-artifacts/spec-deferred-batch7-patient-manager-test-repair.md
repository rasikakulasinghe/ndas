---
title: 'Deferred-Work Batch 7: PatientManagerTestCase Repair'
type: 'bugfix'
created: '2026-11-13'
status: 'done'
baseline_commit: 'b5e2f8702e0e04674440561349e2fed148bb9cb3'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `patients/tests/test_views.py::PatientManagerTestCase` (13 of a fresh, verified 31 project-wide pre-existing failures/errors) predates a refactor of `patient_manager()` and has drifted on four independent axes: (1) it asserts template `patients/patient/manager.html`, the view now renders `patients/manager.html`; (2) it reads the patient list from context key `pts`, the view now provides it as `patients_page_obj`; (3) it checks `filter_label` text against wording the view no longer produces for `new` and `dx_normal` (and expects a `dx_abnormal` filter_type/label pair that was never implemented); (4) it checks for Django-ListView-style `is_paginated`/`page_obj` context keys the view never sets (pagination is driven entirely off `patients_page_obj`'s own attributes). Three of its 13 test methods (`dx_abnormal`, `dx_pending`, `high_risk` filters) assert behavior for filter types that `git log -S` confirms never existed in `patients/views.py` or `patients/urls.py` at any commit -- not a regression, dead-on-arrival test scaffolding.

**Approach:** Rewrite the class to assert what `patient_manager()` actually does today: correct template, correct context key, correct label text, correct pagination assertions (via `patients_page_obj` itself). Delete the three methods testing never-implemented filter types. No production code changes.

## Boundaries & Constraints

**Always:** Every assertion changed must be verified against the live `patient_manager()` view and `patients/manager.html` before being written, not guessed. Keep every fixture and every still-meaningful assertion (patient counts, `assertIn`/`assertNotIn` membership checks) -- only the stale template/context-key/label/pagination-key expectations change.

**Ask First:** None -- this is a test-only repair with no production code change, so nothing here is user-facing or security-relevant. Deleting the three dead-filter-type tests is a judgment call already made and documented (git-history-verified, not a regression) rather than deferred to a question, since leaving them permanently red or inventing production routes to satisfy them are both worse outcomes.

**Never:** No change to `patients/views.py`'s `patient_manager()`, `FILTER_MAP`, or `FILTER_LABELS` -- the three missing filter types (`dx_abnormal`, `dx_pending`, `high_risk`) are confirmed via `git log -S` to never have existed in version control; reintroducing them as new functionality is a product decision, not a test-repair task, and is tracked separately in `deferred-work.md`. No change to any other failing test outside this one class (Dashboard, institution, problemlist, referral, test_security, the GMA tiebreaker, `tests/test_integration.py` are all separate, independently-scoped issues -- tracked, not touched here).

## I/O & Edge-Case Matrix

<!-- No meaningful I/O scenarios: this is a test-file correction with no behavior to characterize beyond "the test now asserts the view's real, unchanged behavior." -->

</frozen-after-approval>

## Code Map

- `patients/tests/test_views.py:27-332` `PatientManagerTestCase` -- full rewrite of assertions, fixtures unchanged:
  - `:165` `assertTemplateUsed(response, 'patients/patient/manager.html')` -> `'patients/manager.html'`.
  - All `response.context['pts']` reads (`:168,181,197,212,225,238,249,260,272,284,300,313`) -> `response.context['patients_page_obj']`.
  - `:189` `'New Patients (No Assessment)'` -> `'New Patients'` (current `FILTER_LABELS['new']`).
  - `test_patient_manager_dx_normal_filter` -- no label assertion in this method to fix, but `:322` in `test_patient_manager_filter_type_context`'s `test_cases` list: `('dx_normal', 'Diagnosed Normal')` -> `('dx_normal', 'Normal Diagnosis')` (current `FILTER_LABELS['dx_normal']`).
  - `:323` `('dx_abnormal', 'Diagnosed Abnormal')` -- remove this tuple from `test_cases`; `dx_abnormal` is not a key in `FILTER_MAP`/`FILTER_LABELS`.
  - `test_patient_manager_dx_abnormal_filter` (`:219-230`), `test_patient_manager_dx_pending_filter` (`:232-241`), `test_patient_manager_high_risk_filter` (`:243-252`) -- delete all three methods (and, if now otherwise unused, the `self.patient_dx_pending`/`self.patient_high_risk` fixtures they alone exercised -- check `test_patient_manager_pagination`'s count-of-15 assertion still needs all 15 fixture patients present, so do not remove the fixtures themselves, only the three test methods).
  - `test_patient_manager_pagination` (`:289-301`) -- replace the `assertIn('is_paginated', response.context)` / `assertIn('page_obj', response.context)` checks (keys the view never sets) with assertions against `patients_page_obj` itself (e.g. `response.context['patients_page_obj'].paginator.count == 15`, and `.has_other_pages()` is true given `Paginator(..., 10)` over 15 patients).
- `_bmad-output/implementation-artifacts/deferred-work.md` -- add a `RESOLVED by:` line to the `spec-fix-bookmark-edit-idor-and-patientlist-bug.md` entry (summary starting "patients/tests/test_views.py's entire PatientManagerTestCase class"); add a `PARTIALLY RESOLVED by:` line to the "45 pre-existing test failures" entry (summary starting "45 pre-existing test failures/errors") noting only the `PatientManagerTestCase` portion (item 3's first half) is fixed here, and recording the fresh, full current failure count (31, not 45) for whoever picks up the rest.

## Tasks & Acceptance

**Execution:**
- [x] Rewrite `PatientManagerTestCase` per the Code Map above. (`test_patient_manager_diagnosed_filter` and `test_patient_manager_dx_normal_filter` needed assertion-content fixes beyond the Code Map's literal context-key/label substitutions -- verified live that `patient_dx_normal`/`patient_dx_abnormal` carry no real diagnosis/video fixtures, so their original assertIn-based assertions could never pass without a fixture change this spec's Boundaries forbid; both methods were rewritten to assert the real, verified behavior instead, with explanatory docstrings. Fixtures themselves were not touched.)
- [x] Run `patients` app tests and confirm all `PatientManagerTestCase` methods pass (11 remaining methods after the 3 deletions, not 10 as estimated -- 14 original methods minus 3 deleted = 11; all 11 pass).
- [x] `deferred-work.md` -- add the two annotations described above (RESOLVED on the spec-fix-bookmark-edit-idor-and-patientlist-bug entry; PARTIALLY RESOLVED on the "45 pre-existing test failures" entry, with a freshly-verified current count of 15, not 31 -- see annotation for detail).
- [x] Review hardening (blind-hunter + verification-gap, both independently confirmed): fixed a factual error in two docstrings/the ledger annotation (`patient_dx_pending`'s GMAssessment does carry a `diagnosis_conclusion` -- the model's own default, `'NORMAL'` -- it does not carry "no" value as originally worded); added exact-count assertions to `test_patient_manager_new_filter` (14) and `test_patient_manager_dx_normal_filter` (1), closing a coverage gap where only membership, not count, was checked; added a comment at the `patient_high_risk` fixture explaining why it now exists only for the pagination count. Logged a new deferred-work entry for a real, pre-existing (not introduced here) gap: `discharged`/`hine`/`da_normal`/`da_abnormal` have zero test coverage anywhere in this file.

**Acceptance Criteria:**
- Given `patients`'s test suite, when run after this change, then every `PatientManagerTestCase` method passes.
- Given the same suite, when run, then no other test file is touched and no other previously-passing test starts failing.
- Given the ledger, when read, then it accurately states that only the `PatientManagerTestCase` portion of the "45 pre-existing failures" entry is resolved, and gives the current (31) total for the rest.

## Design Notes

Why delete rather than "fix" `test_patient_manager_dx_abnormal_filter`/`dx_pending`/`high_risk`: `git log --oneline -S"patient_manager_high_risk" -- patients/views.py` and the equivalent for `urls.py` return zero commits. `ndas/custom_codes/ndas_enums.py`'s `PtStatus` has no `DX_ABNORMAL` (generic, cross-assessment), `DX_PENDING`, or `HIGH_RISK` member -- only `DX_GMA_NORMAL`/`DX_GMA_ABNORMAL`, `DX_DA_NORMAL`/`DX_DA_ABNORMAL`, `DX_HINE`, `DX_NORMAL`, `DIAGNOSED`, `NEW`, `DISCHARGED`, `ALL`. No template anywhere links to `filter_type=dx_abnormal`, `high_risk`, or `dx_pending`. These three tests assert behavior for routes that were never built, not behavior that regressed -- `FILTER_MAP.get(filter_type, PtStatus.ALL)` silently treats all three as `'all'` today, which is what currently makes them fail (they asserted a filtered subset, got all 15 patients back) rather than erroring outright.

## Verification

**Commands:**
- `venv/Scripts/python.exe manage.py test patients.tests.test_views.PatientManagerTestCase` (with `SECURE_SSL_REDIRECT=False`) -- expected: all pass.
- `venv/Scripts/python.exe manage.py test patients` (same env) -- expected: no new failures introduced elsewhere in the app.

## Suggested Review Order

**The four drifted axes, each at their clearest example**

- Template path: the view's real render target.
  [`views.py:272`](../../patients/views.py#L272)

- Context key: `patients_page_obj`, not `pts` -- the view's own context dict.
  [`views.py:265`](../../patients/views.py#L265)

- The test that needed the paginator's unsliced queryset, not the page slice, since 'new' matches 14/15 patients.
  [`test_views.py:185`](../../patients/tests/test_views.py#L185)

- Pagination reasserted against `patients_page_obj` itself -- the view never sets `is_paginated`/`page_obj`.
  [`test_views.py:288`](../../patients/tests/test_views.py#L288)

**Fixture-reality rewrites (not just key renames)**

- `diagnosed` filter verified to return zero patients against this fixture set -- corrected to match, not guessed.
  [`test_views.py:200`](../../patients/tests/test_views.py#L200)

- `dx_normal`'s one real match, and why `patient_dx_normal` itself doesn't qualify despite its name.
  [`test_views.py:224`](../../patients/tests/test_views.py#L224)

**Dead filter types -- deleted, not fixed**

- The three deleted methods' replacement: nothing, by design -- `FILTER_MAP` has no `dx_abnormal`/`dx_pending`/`high_risk` key; see Design Notes for the `git log -S` proof.
  [`views.py:218`](../../patients/views.py#L218)

- The orphaned fixture's new comment explaining why it's kept anyway.
  [`test_views.py:126`](../../patients/tests/test_views.py#L126)

**Ledger**

- The corrected, itemized "15" baseline replacing two stale prior counts (45, then this spec's own "31").
  [`deferred-work.md:21`](deferred-work.md#L21)
