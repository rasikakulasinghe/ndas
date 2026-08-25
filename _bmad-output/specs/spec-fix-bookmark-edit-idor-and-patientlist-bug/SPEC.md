---
id: SPEC-fix-bookmark-edit-idor-and-patientlist-bug
companions: []
sources: []
---

> **Canonical contract.** This SPEC is the complete, preservation-validated contract for what to build, test, and validate. Source documents (deferred-work.md, codebase-review-2026-08-23.md) are for traceability only.

# Fix bookmark_edit write-access IDOR and getPatientList invalid related-name bug

## Why

Two live, unresolved bugs surfaced during prior fixation work (deferred-work.md, triaged 2026-08-25) and are the two highest-priority items left unaddressed: a pain to fix before the next user hits it, in both cases. `bookmark_edit` (patients/views.py:1691-1714) has no ownership check at all, letting any authenticated user overwrite another user's bookmark by guessing a pk — a write-access IDOR, strictly worse than the view-only `bookmark_manager_user` IDOR already closed in `spec-fix-auth-permission-bypasses`. `getPatientList` (ndas/custom_codes/custom_methods.py:563-644) references an invalid Django related-name in three branches (DIAGNOSED, DX_GMA_ABNORMAL, DX_GMA_NORMAL), which is live-reachable from the patient manager's filter UI and 500s on any authenticated user's request today.

## Capabilities

- **CAP-1**
  - **intent:** Only a Bookmark's owner or a superuser can view or submit `patients/views.py:bookmark_edit` (GET/POST `/bookmarks/edit/<pk>/`).
  - **success:** An authenticated non-owner, non-superuser GET or POST to `bookmark-edit/<pk>/` for a bookmark they do not own returns `HttpResponseForbidden` (403) before the form renders or any save occurs, mirroring the existing `bookmark_manager_user` guard pattern (username/superuser check + `logger.warning` on block, patients/views.py:1673-1679). Owner and superuser requests are unaffected — identical 200/redirect flow to today. A regression test covers both the blocked non-owner case and the unaffected owner/superuser case.

- **CAP-2**
  - **intent:** `getPatientList`'s DIAGNOSED, DX_GMA_ABNORMAL, and DX_GMA_NORMAL branches (custom_methods.py:621, 632, 634) query GMAssessment through its correct related_name (`gm_assessments`, per `patients/models.py:866`) instead of the invalid `gmassessment`.
  - **success:** GET requests to `patient-manager` with `filter_type=diagnosed`, `filter_type=gma_abnormal`, or `filter_type=gma_normal` (routed via patients/views.py:220-248) return 200 with a patient list correctly scoped by `gm_assessments__diagnosis_conclusion`, instead of the Django `FieldError` (500) they raise today. A regression test exercises all three branches, mirroring the existing `test_patient_manager_diagnosed_filter`-style pattern used for the sibling DX_NORMAL fix in `spec-fix-medical-data-correctness`.

## Constraints

- CAP-1 must not change `bookmark_edit`'s URL, template (`bookmark/edit.html`), or the success-path behavior for legitimate owners/superusers — add only the ownership guard.
- CAP-1 must not add `@require_http_methods` or `@ratelimit` to `bookmark_edit` or `bookmark_manager_user` — that gap is a separate, already-identified deferred-work item and stays out of scope here.
- CAP-2 must not touch the DX_NORMAL branch (custom_methods.py:623-631) — already fixed and marked `status: done` in `spec-fix-medical-data-correctness`.
- CAP-2 must not redesign `getPatientList`'s classification scheme — only correct the three invalid field references, exactly matching the working `gm_assessments__diagnosis_conclusion` pattern already proven correct at custom_methods.py:628.

## Non-goals

- HINE 3-bucket UI gap (score 60-73), `get_latest_hine/gma_assessment` tiebreaker, virus-scan stub, Excel-export Celery task institution leak, `InstitutionScopedManager` missing safe helper, and the ~180-item mechanical findings batch (deferred-work.md group 5) — all remain separate deferred-work entries for future specs.
- Adding rate-limiting or HTTP-method restrictions to any bookmark view.

## Success signal

An authenticated user who is not a bookmark's owner (and not a superuser) can no longer view or edit that bookmark via `/bookmarks/edit/<pk>/` — they get a 403 instead of the form. Any authenticated user filtering the patient manager by diagnosed/GMA-abnormal/GMA-normal gets a correctly filtered patient list instead of a server error. Both are demonstrable via the regression tests named in CAP-1 and CAP-2's success criteria.

## Assumptions

- CAP-1's ownership model mirrors `bookmark_manager_user` exactly: owner (`request.user == selected_bm.owner`) or `is_superuser` may proceed. No institution-scoping is needed — `Bookmark` has no institution field, and the existing sibling view uses only owner/superuser.
