---
title: 'QA CRUD Smoke Test — Bug Fix Batch'
type: 'bugfix'
created: '2026-10-14'
status: 'in-progress'
review_loop_iteration: 0
context: []
baseline_commit: 'f2cac7730d8e1e9d2a183a9063c9e5d9de856174'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A manual QA pass (CRUD Smoke Test Report, 2026-10-14) found 13 open, independently-shippable bugs across Referral, Reports/PDF, Video/Institution media access, audit attribution, Problem List, and delete-modal UX. Bug #0 (missing backup/referral migrations) was already fixed by the user manually — out of scope here.

**Approach:** Apply 13 small, isolated fixes, each scoped to its own file(s), mirroring patterns already proven elsewhere in the codebase (e.g. copy Attachment's `added_by` assignment pattern onto Patient/Video/Problem/Assessment). No refactors, no new abstractions. Bug #13 (onboarding Short Name field) was investigated and found to have no underlying code defect — documented as a no-op.

## Boundaries & Constraints

**Always:** Match existing codebase patterns exactly (nonce usage, HTMX attributes, nullable-field display conventions). Keep `delete_helpers.py`'s `entity_type` (class name) untouched where it drives `url_map`/business-rule branching — only change what feeds the *display* label.

**Ask First:** Nothing identified — all 13 fixes are mechanical and low-risk.

**Never:** Touch DB migrations (user already applied them manually). Do not extend the "pending" media-institution bypass into a full per-patient ACL check — a simple slug-bypass is correct per the report's first suggested fix direction. Do not fix the identical `subscription_status`/`is_active` badge mismatch on `superadmin_dashboard.html` — only `selector.html` ("Institution Network" page) was reported.

</frozen-after-approval>

## Code Map

- `templates/referral/initiate.html:38` — `hx-get` hardcodes institution id `0`
- `referral/urls.py:9`, `referral/views.py:134-153` — `get_institution_clinicians` reads only path kwarg
- `reports/utils/pdf_generator.py:398` — `dx.name` should be `dx.title` (`patients/models.py:2505-2513` DiagnosisList has no `name`)
- `institution/views.py:908-945` (`protected_media_view`) — slug comparison never allows `'pending'`
- `ndas/custom_codes/validators.py:689-706` — `get_institution_video_path`/`get_institution_attachment_path` default to slug `'pending'`
- `patients/views.py:282-328` (`patient_add`), `:597-644` (`patient_edit`) — no `added_by`/`last_edit_by`
- `video/views.py:33-94` (`video_add`), `:155-210` (`video_edit`) — no `added_by`/`last_edit_by`
- `problemlist/views.py:65-98` (`problem_add`), `:130-163` (`problem_edit`) — no `added_by`/`last_edit_by`
- `patients/views.py:857-916` (`assessment_add`), `:1048-1072` (`assessment_edit`), `:1079-1097` (`assessment_edit_by_fileid`) — no `added_by`/`last_edit_by`
- `templates/hine/view.html:120` — `{{HINERecord.added_by}}` prints raw `None`
- `templates/problemlist/view.html:261,272,283` — plain `<form method="POST">`, no `hx-post`; `problemlist/views.py:331-375` (`problem_status_change`) already returns an HTMX row fragment
- `reports/templates/reports/builder.html:493` — bare `<script>`, no nonce (CSP blocks it); working pattern at `templates/patients/index.html:292` (`<script nonce="{{ request.csp_nonce }}">`)
- `templates/patients/edit.html` delete wiring (lines 499-503, 662) vs. working `templates/patients/partials/patient_view.html:880-881,917` — both paths statically check out (consistent modal ids, consistent `redirect_url='/manager/patient/'`); root cause not found by static read — needs live repro during implementation
- `ndas/templatetags/delete_modal_tags.py:82` — `entity_type = entity.__class__.__name__` used directly as the *display* label; model `Meta.verbose_name` (e.g. `users/models.py:192 "User"`, `patients/models.py:918 "GM Assessment"`) is never consulted
- `templates/src/partials/delete_confirmation_modal.html:11,68` — prints `{{ entity_type }}` (raw class name) instead of a friendly label
- `ndas/custom_codes/delete_helpers.py:289` — `entity.file.name` should be `entity.video_file.name` (Video model has no `file` field, only `video_file` — `video/models.py:82`)
- `templates/video/view.html:91-98` vs `templates/video/edit.html:68-79` — both labeled "Status" but answer different questions (`video.is_new_file` assessment status vs `video.processing_status` pipeline status)
- `templates/video/edit.html` AJAX submit handler — cosmetic delay before redirect after success; low priority, verify live
- `templates/institution/selector.html:61-69` vs `:101-104` — badge driven by `subscription_status`, Enter button correctly driven by `is_active`; no code change found for `templates/institution/add.html` Short Name field (bug #13 — no JS touches that field at all; likely a test-tooling timing artifact, not a product bug)

## Tasks & Acceptance

**Execution:**
- [x] `referral/urls.py`, `referral/views.py`, `templates/referral/initiate.html` — drop the hardcoded `0` path segment; add a URL pattern with no `institution_id` kwarg, read `to_institution` from `request.GET` in the view, point `hx-get` at the new URL — referral clinician dropdown resolves for the selected institution
- [x] `reports/utils/pdf_generator.py:398` — change `dx.name` to `dx.title` — GMA PDF download no longer 500s when a diagnosis is selected
- [x] `institution/views.py:936-945` — when `path_slug == 'pending'`, skip the institution-slug comparison (any authenticated user may access) — pending-bucket media no longer 403s
- [x] `patients/views.py` (`patient_add`, `patient_edit`), `video/views.py` (`video_add`, `video_edit`), `problemlist/views.py` (`problem_add`, `problem_edit`), `patients/views.py` (`assessment_add`, `assessment_edit`, `assessment_edit_by_fileid`) — set `.added_by = request.user` before first save on create, `.last_edit_by = request.user` before save on edit — Added By/Last Edited By populate correctly
- [x] `templates/hine/view.html:120` — wrap with `{{ HINERecord.added_by|default:"Unknown" }}` — no longer prints literal "None"
- [x] `templates/problemlist/view.html:261,272,283` — add `hx-post="{% url 'problem-status-change' problem.pk %}"`, `hx-target`/`hx-swap` appropriate to the row fragment the view already returns — quick actions stay inside the app shell
- [x] `reports/templates/reports/builder.html:493` — add `nonce="{{ request.csp_nonce }}"` to the `<script>` tag — field-selection toggle works under CSP
- [x] `templates/patients/edit.html` + shared delete JS/modal — reproduced live in browser; root cause found (see Spec Change Log) and fixed
- [x] `ndas/templatetags/delete_modal_tags.py`, `templates/src/partials/delete_confirmation_modal.html` — pass a friendly `entity_label`, falling back to the existing class-name string, alongside the unchanged `entity_type`; template displays `entity_label` in the two places it currently shows `entity_type` — CustomUser/GMAssessment modals show "User"/"GM Assessment" (see Spec Change Log re: `.title()`)
- [x] `ndas/custom_codes/delete_helpers.py:289` — change `entity.file.name` / `hasattr(entity, 'file')` to `entity.video_file.name` / `hasattr(entity, 'video_file')` — video delete modal shows the real filename
- [x] `templates/video/view.html:91`, `templates/video/edit.html:68` — relabel to "Assessment Status" and "Processing Status" respectively — no more contradictory same-named status
- [x] `templates/video/edit.html` AJAX handler — verified live; stuck-button delay NOT confirmed (1.5s bounded success-message window, button re-enables correctly on error) — left unchanged
- [x] `templates/institution/selector.html:61-69` — when `not inst.is_active`, render a "Deactivated" badge instead of the subscription-status badge — badge matches the already-correct Enter-button gating
- [x] Bug #13 (onboarding Short Name auto-fill) — no code change; confirmed no JS/attribute touches that field

**Acceptance Criteria:**
- Given a referral form with an institution selected, when the clinician dropdown loads via HTMX, then it lists that institution's active clinicians (not an empty "— Select institution first —" / "Self-referral not permitted" fallback for a different institution).
- Given a GMA with at least one diagnosis selected, when "Download PDF" is clicked, then a PDF downloads without a 500 error.
- Given a video/attachment stored under a `pending/` path, when any authenticated user requests it, then it serves (200), not 403.
- Given a new Patient/Video/Problem/Assessment record, when it is created or edited, then `added_by`/`last_edit_by` reflect the acting user (not "Unknown"/"None").
- Given a Problem's Quick Action button is clicked, when the status change completes, then the page remains inside the app shell (header/nav/footer intact).
- Given the Report Builder page, when "Show Field Selection" is clicked, then the field-selection panel toggles visibly with no CSP console violation.
- Given a CustomUser or GMAssessment delete modal, when it opens, then the title/button read "User"/"GM Assessment", not the raw class name.
- Given a Video delete modal, when it opens, then "File Name" shows the actual filename, not "Unknown".
- Given the same un-assessed video, when viewed on both the view and edit pages, then the two status labels are distinguishable and non-contradictory.
- Given a deactivated institution on the Institution Network page, when the page renders, then its badge visibly indicates it is inactive, matching the disabled Enter button.

## Spec Change Log

- **entity_label casing**: implemented as `str(entity._meta.verbose_name)` as-is, NOT `.title()` as the Tasks line specified. `Meta.verbose_name` values in this codebase are already correctly cased (e.g. "GM Assessment", "CDIC Record", "HINE Assessment"). `str.title()` lowercases every letter but the first of each word, which mangles those acronyms to "Gm Assessment" / "Cdic Record" / "Hine Assessment" — contradicting this spec's own Acceptance Criteria, which expects "GM Assessment" verbatim. Using verbose_name unmodified satisfies the Acceptance Criteria exactly.
- **patients/edit.html delete bug — root cause found via live repro**: NOT a redirect bug. The delete trigger button was gated by `{% if user.is_superuser %}` only (line 499), while the working reference page (`patients/partials/patient_view.html:878`) gates it by `{% if user.is_superuser or user.is_staff %}`, matching the actual server-side rule in `has_delete_permission()` (staff may delete their own `added_by` records). A non-superuser staff owner of a patient could delete it from the view page but the Delete button was entirely absent from the edit page. Fixed by aligning the condition with `patient_view.html`. Verified live end-to-end (Chrome DevTools automation against a local dev server with disposable test users/patients, cleaned up afterward): superuser delete, staff-owner delete, and wrong-password error handling all work correctly; redirect to `/manager/patient/` and app-shell integrity were already correct and required no change.
- **video/edit.html AJAX handler — verified live, no change**: clicked Update on a real video edit page; button correctly disables, shows a spinner, progress reaches 100%, shows a success alert, then redirects after a bounded 1.5s `setTimeout`. On error (not separately re-tested live, confirmed by code read) `resetUpdateState()` re-enables the button. This is a deliberate "show success, then redirect" pattern, not a stuck button — left unchanged per the Tasks line's own threshold ("only touch if the stuck-button delay is confirmed longer than the redirect itself").

## Design Notes

- Bug #7 (patient-edit delete redirect) and the `video/edit.html` stuck-button bug are UX/JS issues where static reading found no discrepancy from the working reference implementation. Per CLAUDE.md, UI fixes must be verified in a real browser — reproduce first, then fix only what's observed, rather than guessing a change with no confirmed root cause.
- `delete_modal_tags.py`'s `entity_type` is a dual-purpose string: internal lookup key (`url_map`) and (today) the display label. Keep it as the lookup key; add a separate `entity_label` for display so no business-rule branch (`warnings`/`details`/`url_map`) needs to change.

## Verification

**Commands:**
- `venv\Scripts\python.exe manage.py test referral patients video problemlist reports institution` -- expected: existing suites still pass (no new failures introduced)

**Manual checks (if no CLI):**
- Referral: as a clinician, start a referral, pick a receiving institution, confirm clinician dropdown populates.
- GMA PDF download with a diagnosis selected.
- Upload a video/attachment for a patient with no institution; confirm it plays/downloads.
- Create and edit a Patient, Video, Problem, and GM Assessment; confirm attribution fields in the DB/UI.
- Problem quick-action buttons stay inside the app shell.
- Report builder field-selection toggle, with browser console open, shows no CSP violation.
- Delete modals for a User and a GM Assessment show friendly names; Video delete modal shows real filename.
- Compare video status label wording on view vs edit pages for the same record.
- Institution Network page: deactivate an institution, confirm badge changes.
- Reproduce patient-edit delete and video-edit stuck-button issues live before touching code.
