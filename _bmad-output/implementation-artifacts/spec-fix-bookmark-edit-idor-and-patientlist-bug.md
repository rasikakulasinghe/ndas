---
title: 'Fix bookmark_edit write-access IDOR and getPatientList invalid related-name bug'
type: 'bugfix'
created: '2026-08-25'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'cd6626946e80656aabbd5ba7670c157eb7340ece'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `bookmark_edit` (patients/views.py:1691-1714) has no ownership check, so any authenticated user can view and overwrite another user's bookmark by guessing/incrementing `pk` (write-access IDOR). Separately, `getPatientList`'s DIAGNOSED, DX_GMA_ABNORMAL, and DX_GMA_NORMAL branches (ndas/custom_codes/custom_methods.py:621,632,634) reference the invalid related-name `gmassessment` instead of `gm_assessments`, causing a live Django `FieldError` (500) whenever the patient manager's `diagnosed`/`gma_abnormal`/`gma_normal` filters are used — reachable today via `patients/views.py:220-248`.

**Approach:** Add an owner-or-superuser guard to `bookmark_edit`, mirroring the existing `bookmark_manager_user` pattern at patients/views.py:1673-1679 (username/superuser check + `HttpResponseForbidden` + `logger.warning`). Fix the three invalid `gmassessment__` field references to `gm_assessments__`, matching the already-correct pattern at custom_methods.py:628.

## Boundaries & Constraints

**Always:**
- Mirror `bookmark_manager_user`'s exact permission model for CAP-1: allow when `request.user == selected_bm.owner` or `request.user.is_superuser`; block (403) otherwise, with a `logger.warning` on block.
- Use the exact working field path `gm_assessments__diagnosis_conclusion` (proven correct at custom_methods.py:628) for all three CAP-2 fixes — no alternate query construction.

**Ask First:** None — both fixes are mechanical and scoped.

**Never:**
- Do not change `bookmark_edit`'s URL, template (`bookmark/edit.html`), or success-path behavior for owners/superusers.
- Do not add `@require_http_methods` or `@ratelimit` to `bookmark_edit` or `bookmark_manager_user` (separate deferred-work item).
- Do not touch the DX_NORMAL branch (custom_methods.py:623-631) — already fixed, `status: done` in spec-fix-medical-data-correctness.
- Do not redesign `getPatientList`'s classification scheme.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Non-owner edits bookmark | Authenticated non-owner, non-superuser GETs/POSTs `/bookmarks/edit/<pk>/` for another user's bookmark | 403 Forbidden, no form rendered, no save | N/A |
| Owner edits own bookmark | Owner GETs/POSTs their own bookmark | 200 / redirect to `bookmark-view`, unchanged from today | N/A |
| Superuser edits any bookmark | Superuser GETs/POSTs any bookmark | 200 / redirect, unchanged from today | N/A |
| Patient manager `diagnosed` filter | GET `manage-patients-filtered` with `filter_type=diagnosed`, patients have `GMAssessment(diagnosis_conclusion='ABNORMAL'/'NORMAL')` | 200, correctly filtered patient list (no `FieldError`) | N/A |
| Patient manager `gma_abnormal`/`gma_normal` filters | Same as above with `filter_type=gma_abnormal` / `gma_normal` | 200, list scoped to matching `diagnosis_conclusion` | N/A |

</frozen-after-approval>

## Code Map

- `patients/views.py:1691-1714` -- `bookmark_edit` -- add ownership guard; mirror pattern at `bookmark_manager_user`, lines 1672-1687.
- `ndas/custom_codes/custom_methods.py:621,632,634` -- `getPatientList` -- fix invalid `gmassessment__diagnosis_conclusion` to `gm_assessments__diagnosis_conclusion`; line 628 is the proven-correct reference (read-only).
- `patients/models.py:866` -- confirms `GMAssessment.patient` FK `related_name="gm_assessments"`.
- `patients/tests/test_bookmark_security.py` -- add `BookmarkEditSecurityTest`, following existing `STATIC_OVERRIDE`/`force_login` conventions.
- `patients/tests/test_views.py:26-158` -- `PatientManagerTestCase` fixture conventions (read-only reference, do not modify). `test_patient_manager_diagnosed_filter` (line 191) currently errors on this FieldError and separately has under-fixtured dx_normal/dx_abnormal patients (no real `GMAssessment` rows) -- both out of scope; log to deferred-work.md instead.

## Tasks & Acceptance

**Execution:**
- [x] `patients/views.py` -- in `bookmark_edit`, after fetching `selected_bm`, add `if request.user != selected_bm.owner and not request.user.is_superuser: logger.warning(...); return HttpResponseForbidden()` -- closes the write-access IDOR.
- [x] `ndas/custom_codes/custom_methods.py` -- change `gmassessment__diagnosis_conclusion` to `gm_assessments__diagnosis_conclusion` at lines 621 (DIAGNOSED), 632 (DX_GMA_ABNORMAL), 634 (DX_GMA_NORMAL) -- closes the FieldError.
- [x] `patients/tests/test_bookmark_security.py` -- add `BookmarkEditSecurityTest`: non-owner GET/POST → 403; owner GET/POST → 200/redirect unchanged; superuser GET/POST on another user's bookmark → 200/redirect unchanged.
- [x] `patients/tests/test_views.py` -- add a new self-contained test method/class exercising `filter_type=diagnosed`, `gma_abnormal`, `gma_normal` against patients with real `GMAssessment(diagnosis_conclusion=...)` fixtures (own Video/GMAssessment setup, independent of `PatientManagerTestCase`'s existing under-fixtured patients) -- proves no `FieldError` and correct membership.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- append one entry noting `test_patient_manager_diagnosed_filter`'s dx_normal/dx_abnormal fixtures lack real `GMAssessment` rows, so once this spec's FieldError fix lands, that pre-existing test will fail on its assertions instead of erroring on FieldError -- needs its own fixture fix, out of scope here.

**Acceptance Criteria:**
- Given a non-owner, non-superuser authenticated user, when they GET or POST `/bookmarks/edit/<pk>/` for a bookmark they don't own, then they receive 403 and no data is changed.
- Given the bookmark's owner or a superuser, when they GET or POST `/bookmarks/edit/<pk>/`, then behavior is identical to pre-fix (200 render or redirect to `bookmark-view`).
- Given patients with real `GMAssessment` records, when `patient_manager` is requested with `filter_type=diagnosed`, `gma_abnormal`, or `gma_normal`, then the response is 200 with a correctly filtered patient list, not a 500/FieldError.

## Spec Change Log

## Verification

**Commands:**
- `python manage.py test patients.tests.test_bookmark_security` -- expected: all pass, including new `BookmarkEditSecurityTest`.
- `python manage.py test patients.tests.test_views` -- expected: all pass except the pre-existing, separately-tracked `test_patient_manager_diagnosed_filter` fixture gap (noted above, not introduced by this spec).

## Suggested Review Order

**Bookmark write-access IDOR fix**

- Entry point: adds the owner-or-superuser guard, mirroring `bookmark_manager_user`'s pattern.
  [`views.py:1697`](../../patients/views.py#L1697)

**getPatientList invalid related-name fix**

- Three branches corrected from the invalid `gmassessment__` to the real related_name `gm_assessments__`.
  [`custom_methods.py:622`](../../ndas/custom_codes/custom_methods.py#L622)
  [`custom_methods.py:633`](../../ndas/custom_codes/custom_methods.py#L633)
  [`custom_methods.py:635`](../../ndas/custom_codes/custom_methods.py#L635)

**Tests and follow-up tracking**

- Regression coverage for the IDOR guard: non-owner blocked, owner/superuser unaffected.
  [`test_bookmark_security.py:79`](../../patients/tests/test_bookmark_security.py#L79)

- Self-contained regression coverage for the three fixed filter branches, independent of the pre-existing `PatientManagerTestCase` fixture gap.
  [`test_views.py:856`](../../patients/tests/test_views.py#L856)

- Three incidental pre-existing issues logged for later attention (not caused by this spec): `PatientManagerTestCase`'s context-key/fixture mismatch, the `Video` model-mapping bug in `Bookmark._validate_bookmarked_object`, and `bookmark_edit`'s missing rate-limiting.
  [`deferred-work.md:49`](deferred-work.md#L49)

