---
title: 'Story 1.4: Date/date-range-scoped export'
type: 'feature'
created: '2026-09-19'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '1320c1ce3416e1019e8d2cf354703746bc520cca'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Every backup so far exports every patient in scope, full stop — there's no way to narrow a large institution's backup to just the patients created in a given window (e.g. "just this year's intake").

**Approach:** Add an optional start/end date filter (on `Patient.created_at`) to the trigger form, available to any user who can trigger a backup (not privilege-gated like Story 1.2's scope selection); narrow `Patient` and every patient-linked model relative to the filtered patient set, while `referral` models stay full-scope; populate `manifest.json`'s previously-stubbed `date_filter` field with the real applied values.

## Boundaries & Constraints

**Always:**
- Date-range filtering is available to **any** user who can trigger a backup (`ADMIN` and `SUPERADMIN` alike) — unlike Story 1.2's scope-mode selection, it is never superadmin-gated.
- `BackupScopeForm` gains `start_date`/`end_date` (`forms.DateField(required=False)`), validated for **every** submission, including non-superadmin ones. `_resolve_scope_from_request`'s current early-return for non-superadmins (which today skips form instantiation entirely) must be restructured so the form is still built and validated for the date fields even when `mode`/`institutions` are ignored/coerced exactly as Story 1.2 already established (regression: every existing Story 1.2 scope-coercion test must keep passing unmodified).
- `end_date < start_date` is refused before any `BackupJob` row is created — re-render the bound form with the error (mirrors Story 1.2's empty-multi-selection refusal pattern), never redirect-and-lose the user's picks.
- Only `Patient` and its patient-linked models (`Video`, `Attachment`, `GMAssessment`, `HINEAssessment`, `DevelopmentalAssessment`, `CDICRecord`, `GeneralPaediatricAssessment`, `Problem`, `ProblemAction`) are narrowed by the filter, applied to `Patient.created_at`'s date. `ReferralSent`/`ReferralReceived`/`ReferralMessage` are never narrowed by date — always full institution-scope (epic-1-context.md). `Bookmark` remains entirely excluded from export (unchanged, pre-existing, not this story's concern).
- Every date-narrowed model is filtered relative to the already institution-*and*-date-scoped `patient_qs` (`patient__in=patient_qs` / `problem__patient__in=patient_qs` for `ProblemAction`) rather than re-deriving institution filters per model — this replaces `_model_export_plan`'s current per-model institution-filter duplication for these 9 models with one shared `patient_qs`, which is *also* how the date filter reaches them. `estimate_export_size_bytes` needs the same `patient_qs` resolution (institution + optional date) to keep its disk-space estimate accurate under a date filter.
- `BackupJob` gains `date_filter_start`/`date_filter_end` (`DateField(null=True, blank=True)`) so a completed job's actual applied filter is recorded. `create_export`'s previously-stubbed `manifest.json` `date_filter` key (`{"applied": false, "start": null, "end": null}`, Story 1.3) is now populated with the real values whenever either bound is set.
- Omitting both dates exports the full scope, byte-for-byte identical to Stories 1.1-1.3's existing behavior — every existing `backup` test must keep passing unmodified.
- The date filter never participates in Story 1.2's overlap/concurrency lock — only institution-scope overlap matters (unchanged); two date-filtered jobs for the same/overlapping institutions still conflict regardless of their date ranges.

**Ask First:** None — fully decided from epic-1-context.md plus this spec's two additive, non-contradictory choices: open-ended one-sided ranges are allowed, and the filter is available to every triggering user, not just superadmins.

**Never:**
- No UI or manifest change to `referral` models' date participation — they stay full-scope always, in every scope/date combination.
- No retroactive backfill of `date_filter_start`/`date_filter_end` on Stories 1.1-1.3's already-completed jobs (both fields stay `null`, correctly meaning "no filter was applied").
- No change to the overlap-lock's institution-only conflict semantics (Story 1.2).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| No date filter | POST with neither `start_date` nor `end_date` | Full scope, byte-for-byte unchanged from Stories 1.1-1.3 | N/A |
| Full range | `start_date=D1`, `end_date=D2` | Only patients with `created_at` date in `[D1, D2]` (plus their full related records) exported; referral models stay full-scope | N/A |
| Open-ended, start only | `start_date=D1`, no end | Patients created on/after `D1` | N/A |
| Open-ended, end only | `end_date=D2`, no start | Patients created on/before `D2` | N/A |
| Invalid range | `end_date` before `start_date` | Refused before any row is created; bound form re-rendered with the error | Validation error shown, no `BackupJob` row |
| Non-superadmin uses the filter | `ADMIN` POSTs `start_date`/`end_date` (no `mode`/`institutions`) | Works identically to a superadmin's submission — never privilege-gated | N/A |
| Manifest reflects the filter | A date-filtered job completes | `manifest.json`'s `date_filter` = `{"applied": true, "start": "<D1>", "end": "<D2>"}` (or one side `null` for an open-ended range) | N/A |

</frozen-after-approval>

## Code Map

- `backup/services.py:85-190` (`_model_export_plan`) -- currently three institution-scoping branches each independently re-derive every patient-linked model's filter. Story 1.4 collapses the 9 patient-linked models' filters into `patient__in=patient_qs` (computed once per branch, then optionally date-narrowed), leaving only `Patient`/`ReferralSent`/`ReferralReceived`/`ReferralMessage` inside the three-way branch.
- `backup/services.py:200-232` (`estimate_export_size_bytes`) -- currently duplicates a small institution-filter for `Video`/`Attachment` directly; needs the same `patient_qs` (institution + optional date) resolution as `_model_export_plan` to stay accurate. Consider a small shared private helper (e.g. `_resolve_patient_qs(institution_or_institutions, system_wide, date_range)`) used by both, since the institution+date logic would otherwise be duplicated in two places -- a small, currently-justified exception to this codebase's usual explicit-branches-over-abstraction preference (see Story 1.2's own `_resolve_scope`/`_model_export_plan` precedent for the branch style to preserve elsewhere).
- `backup/services.py:306-460ish` (`create_export`) -- reads `job.scope_type`/`scope`/`scopes` today; needs to also read `job.date_filter_start`/`date_filter_end`, pass them into `_model_export_plan`/`has_sufficient_disk_space`, and populate the manifest's `date_filter` key with the real values instead of the Story 1.3 constant stub.
- `backup/models.py:9-123` (`BackupJob`) -- add `date_filter_start`/`date_filter_end` alongside `scope_type`/`scope`/`scopes`/`archive_checksum`.
- `backup/forms.py:18-53` (`BackupScopeForm`) -- add `start_date`/`end_date` `DateField(required=False)`; extend `clean()` to refuse `end_date < start_date` (same pattern as the existing empty-multi-selection refusal).
- `backup/views.py:39-79` (`_resolve_scope_from_request`) -- currently early-returns for non-superadmins *before* instantiating `BackupScopeForm` at all (line 63-64); must be restructured so the form (and its date-field validation) runs for every submission, while `mode`/`institutions` stay coerced/ignored for non-superadmins exactly as today. The current 5-element return tuple is already getting unwieldy -- consider a small dataclass/namedtuple for the resolved-scope-plus-dates result rather than growing the tuple further.
- `backup/views.py:127-315ish` (`backup_create`) -- the disk-check (`disk_check_scope`) and job-creation calls need the resolved date filter threaded through; on success, persist `date_filter_start`/`date_filter_end` onto the created `BackupJob`.
- `backup/templates/backup/create.html:35-81` -- the `{% if is_superadmin %}`-gated block currently wraps the whole scope-mode UI; the new date-range fields must render **outside** that gate (visible to every user), while `mode`/`institutions` stay inside it.

## Tasks & Acceptance

**Execution:**
- [x] `backup/models.py` -- add `BackupJob.date_filter_start`/`date_filter_end` (`DateField(null=True, blank=True)`)
- [x] `backup/migrations/0007_...`, `0008_...` -- generated via `makemigrations backup`
- [x] `backup/forms.py` -- `BackupScopeForm` gains `start_date`/`end_date`; `clean()` refuses `end_date < start_date`
- [x] `backup/services.py` -- `_model_export_plan` refactored: `patient_qs` resolved once per institution-scope branch (via shared `_resolve_patient_qs`), then optionally date-narrowed, then reused via `patient__in=patient_qs` for all 9 patient-linked models; `ReferralSent`/`ReferralReceived`/`ReferralMessage` untouched by date filtering
- [x] `backup/services.py` -- `estimate_export_size_bytes`/`has_sufficient_disk_space` extended with the same institution+date `patient_qs` resolution for accurate size estimates
- [x] `backup/services.py` -- `create_export` reads `job.date_filter_start`/`date_filter_end`, threads them through, and populates `manifest.json`'s `date_filter` key with the real applied values
- [x] `backup/views.py` -- `_resolve_scope_from_request` restructured (now returns a `ResolvedScope` dataclass) so `BackupScopeForm` (and its date-field validation) runs for every submitter, not just superadmins; `backup_create` persists the resolved dates onto the created `BackupJob`
- [x] `backup/templates/backup/create.html` -- date-range fields rendered outside the `is_superadmin` gate
- [x] `backup/tests/test_services.py` -- new cases: full-range/open-ended-start/open-ended-end filtering correctness, referral models unaffected by date filter, no-filter behavior byte-for-byte matches pre-1.4 tests, `manifest.json`'s `date_filter` reflects the real applied values
- [x] `backup/tests/test_views.py` -- new cases: non-superadmin can use the date filter, `end_date < start_date` refused with re-rendered form, overlap-lock ignores date ranges (two date-filtered jobs for the same institution still conflict); one existing test renamed/extended (`scope_form` is no longer `None` for a non-superadmin GET, since Story 1.4's date fields need a form instance for every user)

**Acceptance Criteria:**
- Given a backup triggered with a start/end date range, when the archive is inspected, then only patients created within that range (and their full related records) appear, and referral records are still full-scope.
- Given a backup triggered with no date filter, when compared against Story 1.1-1.3's existing behavior, then the export is identical.
- Given an `ADMIN` (non-superadmin) submits a date range, when the job runs, then the filter is applied exactly as it would be for a superadmin.
- Given `end_date` before `start_date`, when submitted, then the request is refused before any `BackupJob` row is created.
- Given a completed date-filtered job, when `manifest.json` is inspected, then `date_filter.applied` is `true` with the real start/end values.

## Spec Change Log

- **Verification pass (2026-09-20) — three-layer review (blind-hunter, edge-case-hunter, verification-gap); no spec-level ambiguity, all findings patched:**
  - **Regression (confirmed independently by all three reviewers, fixed):** `_resolve_scope_from_request` first cut ran `form.is_valid()` for every submitter *before* the non-superadmin coercion branch, so a non-superadmin POST carrying `mode=multi` with no `institutions` was refused outright by `clean()`'s empty-multi-selection rule -- violating this spec's own boundary that `mode`/`institutions` stay inert for non-superadmins. Now only `start_date`/`end_date` errors can refuse a non-superadmin; `mode`/`institutions` content (and errors caused solely by it) is ignored. Regression test added (non-superadmin POSTs `mode=multi`, `institutions=[]` -> job still created as `single`).
  - Field-level form errors (e.g. an unparsable date) render inline again; `end_date < start_date` is attached to the `end_date` field via `add_error`.
  - `date_filter_start`/`date_filter_end` gained `db_index=True` (CLAUDE.md convention; migration `0008`).
  - Help text now states the range bounds `Patient.created_at` only, not each related record's own date.
  - Added service-level tests for the date filter composed with `multi` and `system` scope (plan and size estimate), previously covered only at the view layer.
  - Rejected as noise/by-design: hardcoded template English (the existing template never used `{% trans %}`), no future-date bound (an out-of-range filter only yields an empty export), DB `CheckConstraint` on the range (project validates business rules in Python; form is the only creation path), midnight/timezone boundary testing (deferred).
  - Full suite: 94/94 pass.

## Design Notes

`_model_export_plan`'s simplified shape (illustrative):

```python
mode, value = _resolve_scope(institution_or_institutions, system_wide)
if mode == "system":
    patient_qs = Patient.objects.all_institutions()
    referral_sent_qs = ReferralSent.objects.all_institutions()
    # ... (referral_received_qs, referral_message_qs unchanged)
elif mode == "single":
    patient_qs = Patient.objects.for_institution(value)
    # ... (referral querysets unchanged)
else:
    patient_qs = Patient.objects.filter(institution__in=value)
    # ... (referral querysets unchanged)

if date_start:
    patient_qs = patient_qs.filter(created_at__date__gte=date_start)
if date_end:
    patient_qs = patient_qs.filter(created_at__date__lte=date_end)

video_qs = Video.objects.filter(patient__in=patient_qs)
attachment_qs = Attachment.objects.filter(patient__in=patient_qs)
# ... (gm_qs, hine_qs, dev_qs, cdic_qs, gpa_qs, problem_qs all the same pattern)
problem_action_qs = ProblemAction.objects.filter(problem__patient__in=patient_qs)
```

## Verification

**Commands:**
- `python manage.py test backup` -- expected: all existing tests (unmodified) plus new date-filter tests pass
- `python manage.py makemigrations --check backup` -- expected: no missing migrations

**Manual checks (if no CLI):**
- Trigger a date-filtered backup as a seeded admin, unzip, and confirm `db_export.json`'s patient records fall within the requested range while `manifest.json`'s `date_filter` reflects it accurately.

## Suggested Review Order

**Date narrowing (the core of this story)**

- One shared helper resolves institution scope, then optionally narrows by `Patient.created_at`'s date -- start here.
  [`services.py:85`](../../backup/services.py#L85)
- The 9 patient-linked models now follow `patient_qs`; referral models deliberately stay institution-only.
  [`services.py:124`](../../backup/services.py#L124)
- Disk-space estimate uses the same resolution so it stays accurate under a filter.
  [`services.py:233`](../../backup/services.py#L233)
- Job's stored filter feeds the plan, and the Story 1.3 manifest stub becomes the real applied values.
  [`services.py:341`](../../backup/services.py#L341)

**Who may use it, and the regression fixed in review**

- Dates are never privilege-gated; `mode`/`institutions` errors must never refuse a non-superadmin -- the subtle part to review.
  [`views.py:73`](../../backup/views.py#L73)
- Resolved scope+dates travel as a dataclass instead of an ever-growing tuple.
  [`views.py:44`](../../backup/views.py#L44)
- Dates persisted on the created job.
  [`views.py:337`](../../backup/views.py#L337)

**Form, model, UI**

- `end_date < start_date` refused on the `end_date` field.
  [`forms.py:81`](../../backup/forms.py#L81)
- New nullable, indexed date fields recording what each job applied.
  [`models.py:115`](../../backup/models.py#L115)
- Date inputs render outside the superadmin gate, so every user sees them.
  [`create.html:48`](../../backup/templates/backup/create.html#L48)

**Tests**

- Service-level filtering incl. multi/system composition, then view-level access, refusal, overlap-lock and the regression case.
  [`test_services.py`](../../backup/tests/test_services.py#L1)
  [`test_views.py`](../../backup/tests/test_views.py#L1)
