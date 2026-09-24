---
title: 'Story 2.4: Date-scoped (partial) restore -- match and preview'
type: 'feature'
created: '2026-09-23'
status: 'done'
review_loop_iteration: 1
context: []
baseline_commit: '1095850bca0fc54961327b9df0b3f54baf036b71'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A date-scoped archive is currently blocked at the preview stage ("its match/skip/import preview is Story 2.4, so confirming one is not offered yet"). Nothing computes which archived patients already exist here, so nobody can trust what a date-scoped restore would actually do.

**Approach:** For a date-scoped, single-institution archive, validation (Story 2.1's `validate_restore_upload`) gains a sixth stage that streams the archive's `patients.patient` records once, matches each against this system's patients, and stores a final skip/import/excluded partition on the upload -- computed once, never re-derived, so it stays exactly what gets shown and confirmed. The preview (Story 2.2) renders that stored partition (still no zip I/O in the request) and, once it exists, the "date-scoped: not offered yet" block is lifted for confirmation. Applying the import itself stays blocked (Story 2.5); Story 2.3's `start_restore`/`verify_confirmed` refusal for `date_filter.applied` is untouched.

## Boundaries & Constraints

**Always:**
- Only a **single-institution** date-scoped archive (`scope_type == 'single'`) gets a computed match. A multi- or system-scoped date-scoped archive's `institutions` manifest field is a flat slug list with no per-record slug mapping in `db_export.json` (each `patients.patient` record carries only a raw source-system institution pk), so there is no reliable way to resolve which slug a given record belongs to. These are left validated with no `match_summary`, and the preview block reason becomes "date-scoped restore is only supported for a single-institution archive yet" instead of today's generic wording. (Full-scope multi/system restore is unaffected -- Story 2.3 already handles that scope shape differently, by pk equality across the whole scope, not per record.)
- **Stage 6 (`_compute_date_scope_match`), single-institution + `date_filter.applied` only**, runs after the existing five stages succeed, inside the same `validate_restore_upload` command/transaction-free flow, writing progress the same way. It: resolves the archive's one institution slug to a target `Institution` (missing -> every patient excluded, reason `missing-institution`, no further matching attempted); then streams `patients.patient` from `db_export.json` (the shared reader Story 2.3 built, extracted so both modules use one implementation, never two); for each record, checks the five identifier fields (`bht`, `nnc_no`, `ptc_no`, `pc_no`, `pin`) against `Patient.objects.all_institutions()` (every existing patient on this system: the five identifiers are globally unique, so a match in ANY institution is an existing patient) using plain equality lookups per populated field: any populated-field match -> **skip**; no populated field has a match -> **import**; a patient with none of the five fields set -> always **import** (accepted residual duplicate risk, matches the AC). If the *same* archived patient's populated fields match more than one distinct existing patient, or a later archived patient's match lands on an existing patient a prior archived patient already matched -> both/all the conflicting archived patient(s) are **excluded**, reason `ambiguous-conflict`, with which identifier(s) and which existing patient pk(s) caused it. Every archived patient in the file gets exactly one final outcome; none are silently dropped.
- Stores `RestoreUpload.match_summary` (new nullable `JSONField`, set only alongside `manifest_summary` in the terminal `validated` save, same single save, same `update_fields` discipline as the rest of Story 2.1): `{institution_slug, target_institution_id, skip: [...], import: [...], excluded: [...]}`, each list entry `{archive_pk, matched_fields: [...], reason (excluded only), existing_patient_ids (excluded/skip only)}`. No PHI beyond identifiers already present in the archive and already visible to this super admin on this system.
- `build_preview()` (Story 2.2, `backup/restore_preview.py`) reads `upload.match_summary` only -- no new zip I/O in the request, per Story 2.2's frozen "never re-opening the zip in the request" rule. When `date_filter['applied']` and `match_summary` is present: render skip/import/excluded counts and, per the existing per-model table's spirit, a compact per-set list (patient identifier value(s) that matched, or the exclusion reason); include a stable hash of `match_summary` in `facts` (and therefore the digest), exactly like every other archive-derived fact, so a corrupted/changed `match_summary` invalidates confirmation the same way a changed manifest would. Drop the current unconditional date-scoped block reason; add it back, unchanged in spirit, only when `match_summary` is absent for a date-scoped archive (multi/system scope, or validated before this story shipped).
- Confirmation (`confirm_upload`) already blocks a `validated`-only upload and re-digests; no change to its mechanics. The `confirmed_snapshot` therefore carries the locked-in partition byte-for-byte -- Story 2.5's apply step must read it from there, never recompute matching, matching the AC's "this partition is final ... including during the apply step".
- `RestoreUpload.match_summary` migration (`backup/0014_...`), reviewed like every prior migration in this epic (`--no-input`, only `backup` touched, no stray Django-6.0 header content beyond what Story 2.3's migrations already show, which is a pre-existing tracked issue).

**Ask First:** None -- the identifier-match rule, ambiguous-conflict handling, and "no identifiers set -> import" are fixed by the epic's ACs. The single-institution-only scope for this story, and computing the match inside `validate_restore_upload` rather than a new subprocess, are this spec's own calls, flagged in Design Notes.

**Never:**
- No import/apply of any patient row, media file, or related record (Story 2.5). No change to Story 2.3's full-scope path, its `start_restore`/`verify_confirmed` date-scoped refusal, or its per-model restore order.
- No re-matching at preview-render time, at confirm time, or during apply -- the stored `match_summary` is the single source of truth once computed.
- No match computation for a multi- or system-scoped date-scoped archive in this story.
- No new dependency, no `loaddata`, no change to the archive/manifest format.

## I/O & Edge-Case Matrix

| Scenario | Behaviour |
|----------|-----------|
| Single-institution date-scoped archive, institution exists here | Stage 6 runs; every patient gets skip/import/excluded; preview shows it; confirmation is offered |
| Single-institution date-scoped archive, institution missing here | Every patient excluded (`missing-institution`); `match_summary` still stored (so the preview can show why); confirmation still blocked by the existing missing-institution block reason |
| Multi- or system-scoped date-scoped archive | No `match_summary`; preview shows the new "single-institution only" block reason; confirmation blocked |
| Archived patient has none of the five identifiers | Always **import** |
| Archived patient matches two distinct existing patients | **Excluded**, `ambiguous-conflict`, both existing pks named |
| Two archived patients both match the same existing patient | Both **excluded**, `ambiguous-conflict` |
| Archive validated before this story shipped (no `match_summary`, date-scoped) | Preview treats it exactly like the multi/system case -- blocked, not crashed |
| Stage 6 throws (malformed record, DB error) | Whole validation fails (`failed`, same as any other unexpected validation error today); upload never reaches `validated` |
| Full-scope archive | Untouched; Stage 6 never runs |

</frozen-after-approval>

## Code Map

- `backup/restore_validation.py:562` (`validate_restore_archive`) -- add the conditional Stage 6 call after `_verify_file_checksums`, only when `manifest['date_filter'].get('applied')` and `manifest['scope_type'] == 'single'`; return the extra `match_summary` alongside `ValidationResult`'s existing `summary`.
- `backup/management/commands/validate_restore_upload.py:130` (terminal `validated` save) -- add `match_summary` to the fields set and to `update_fields`.
- New shared module `backup/export_stream.py` (or similar) -- move `START`, `ExportFormatError`, `ExportReader`, `iter_export_records` out of `backup/restore_apply.py` (currently private to it) so `restore_validation.py`'s new stage and `restore_apply.py` both import one implementation; `restore_apply.py`'s existing imports/call sites change to the new location, no behaviour change.
- `backup/models.py:171` (`RestoreUpload`) -- add `match_summary` (`JSONField`, `null=True, blank=True`), migration `0014_...`.
- `backup/restore_preview.py:154` (`build_preview`) -- read `upload.match_summary`; extend `facts`/digest and the returned dict with the date-scoped match rendering; change the date-scoped block-reason branch (currently unconditional at the date-scoped check) to the two-way split above.
- `backup/templates/backup/restore_preview.html` -- add the skip/import/excluded section, shown only when `date_filter.applied` and `match_summary` is present.
- Story 2.3's `RESTORE_MODEL_KEYS`, `PATIENT_IDENTIFIER_FIELDS` in `backup/restore_apply.py` -- reuse `PATIENT_IDENTIFIER_FIELDS` directly (same five fields, same order) rather than redefining it.
- `Patient.objects.all_institutions()` (`patients/models.py:141`, `PatientManager`) -- the queryset to match against (amended at the review checkpoint, see Spec Change Log: identifiers are globally unique, so matching is system-wide, not per institution).

## Tasks & Acceptance

**Execution:**
- [x] Extract the shared archive-record reader into `backup/export_stream.py`; repoint `restore_apply.py`; full `backup` suite still green before adding anything new (a pure refactor checkpoint).
- [x] `RestoreUpload.match_summary` model field + migration.
- [x] Stage 6 matching logic in `restore_validation.py` + wiring in `validate_restore_upload.py`.
- [x] `build_preview()` changes (facts/digest, block reasons, returned rendering data) + `restore_preview.html`.
- [x] Tests, migrations check, full suite (background).

**Acceptance Criteria:** exactly the epic's four Given/When/Then blocks for Story 2.4 (institution resolution by slug before identity matching; five-field populated-match -> skip, no match -> import, no fields set -> import; multi-match or shared-match -> excluded/ambiguous-conflict; preview shows the final, immutable skip/import/excluded partition).

## Spec Change Log

- **Review checkpoint 1 (2026-09-24) -- triggering finding (intent_gap, blind-hunter/edge-case-hunter):** matching only against `for_institution(target)` misses a patient whose bht/nnc_no/ptc_no/pc_no/pin belongs to a patient in ANOTHER institution (all five are globally unique on `Patient`); that archived patient would be classified import and then fail on the unique constraint in Story 2.5. **Amended (human decision, asked at this checkpoint):** the match is against every patient on the system (`all_institutions()`); any populated-identifier match, in any institution, places the archived patient in the skip set. Only the frozen matching sentence and the Code Map bullet changed. **Deviation from the loopback procedure, stated openly:** the code was NOT reverted and re-derived; the amendment is a one-line change to an otherwise verified implementation (513/513 tests), so it is applied as a patch alongside the other review patches below. **KEEP:** the extracted `backup/export_stream.py`, the two-pass conflict resolution (self-conflict and shared-match), the stored-once/immutable `match_summary`, the digest hash of `match_summary`, and the single-institution-only scope.
- **Verification pass (2026-09-24) -- three-layer review (blind-hunter, edge-case-hunter, verification-gap) over the uncommitted implementation, then a patch pass; one intent_gap, resolved with the human, and the rest patched, deferred or rejected:**
  - **Real bugs / gaps, fixed:** matching used `for_institution(target)`, but all five identifiers are globally unique, so an archived patient whose identifier belongs to a patient in another institution (or with no institution) would have been classified import and then failed on the unique constraint in Story 2.5 (the intent_gap above; now system-wide). Stage 6 accepted a repeated archive pk, a repeated `patients.patient` key, and one identifier on two archived patients (now `ExportFormatError`, mirroring `restore_apply.preflight`); it sent every identifier value in a single `__in` (now chunked at 500); it gated on `applied` alone while the preview treats `applied OR start OR end` as date-scoped, so a start-only archive was blocked forever (same normalisation now); it ignored a non-text identifier such as an integer bht (now `ExportFormatError`). The preview lifted its block for any dict, including an empty or partial one, a wrong-institution one, or a stray one on a multi/system archive (now requires `applied`, single scope, exactly one manifest slug, all three lists and a matching slug); a single-scope archive naming two slugs would have been confirmable with everyone excluded as "missing-institution" (now blocked with its own reason).
  - **Spec requirement missed by the implementation, fixed:** the preview promised the matched identifier values but showed only field names and pks; every entry now carries `identifiers` and the preview lists import entries too. The preview also printed raw reason codes and a "Story 2.5" project reference to end users, and had no bound on row count (readable text, no story reference, 200 rows per list with an "and N more" row).
  - **Verification gaps closed:** nothing tested that `validate_restore_upload` actually persists `match_summary` (dropping it from `update_fields` would have shipped a permanently blocked feature with a green suite); nothing tested `ExportFormatError` through `run_restore` / `apply_restore` after it stopped being a `RestoreError`; nothing tested that `start_restore` / `verify_confirmed` still refuse a date-scoped upload that now has a `match_summary` (the main regression risk of lifting the preview block); the identity-validation branches and a missing `patients.patient` key were untested. All added (`backup` suite 513 -> 543).
  - **Wording:** a single-scope archive with no usable match now says it was validated before date-scoped matching existed and must be cancelled and uploaded again, instead of "not available yet".
  - **Rejected, with reasons:** requiring the archived record's own institution to match (the spec deliberately ignores the raw source pk and overrides the institution from the resolved slug at import); checking archived patients against the date range (the exporter guarantees it); restoring `ExportFormatError`'s `RestoreError` base class (the two catch sites are explicit and now tested); the duplicate `iter_export_records` wrapper (documented, differing defaults are deliberate); the confirm/apply-time staleness of the partition (accepted by this spec's Design Notes); `.pyc` files and the Django 6.0 migration header (pre-existing repo-wide, unrelated).
  - **Deferred (recorded in deferred-work.md):** multi-/system-scoped matching needs a manifest pk-to-slug institution map; Stage 6 reports no progress and re-reads `db_export.json`; the full partition is stored, copied into `confirmed_snapshot` and re-hashed per render, so it is unbounded; Stage 6 depends lazily on the apply and preview layers (a neutral shared module would remove that); identifier matching is exact-string only; no maximum partition age or re-check between validation and confirm.
  - **Process notes:** the three review agents hit a session rate limit once and were rerun unchanged; one of my independent full-suite runs was killed by Claude Code for low system memory and was rerun on request. All results are from the project venv (Django 6.0).
  - Full suite (venv): `backup` 543/543 pass (independently re-run); `makemigrations --check --dry-run backup` clean.

## Design Notes

- **Single-institution scope for this story** is a narrowing beyond what the epic's prose implies (it doesn't call out multi/system as out of scope). It's necessary because the shipped manifest format has no per-record slug map -- only a flat `institutions` slug list -- so a multi-institution archive's per-record institution can't be resolved to a slug without guessing. Extending the manifest schema to carry a real pk->slug map is possible future work (recorded in `deferred-work.md`) but touches the already-shipped export format from Epic 1, so it's out of this story.
- **Where the match runs:** inside `validate_restore_upload` rather than a new subprocess/trigger, because Story 2.2's preview must never open the zip in the request, and validation is already the one async step every upload goes through before a preview is ever offered -- reusing it needs no new job type, lock, or UI action.
- **Immutability over live re-matching:** the partition is computed once and never recomputed (not at preview render, not at confirm, not at apply) -- deliberately accepting that a patient created or edited on the target between validation and apply won't be reflected. This mirrors Story 2.2's `confirmed_snapshot` and Story 2.3's "read once, trust the stored fact" pattern, and is what the epic's "final ... including during the apply step" line asks for.

## Verification

**Commands:**
- `venv/Scripts/python.exe manage.py makemigrations --check --dry-run` -- only `backup` changes.
- `venv/Scripts/python.exe manage.py test backup --noinput` (background; one run at a time).

**Manual checks (if no CLI):** none beyond the Django test client; not exercised in a browser.
