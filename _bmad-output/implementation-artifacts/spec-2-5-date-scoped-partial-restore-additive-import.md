---
title: 'Story 2.5: Date-scoped (partial) restore -- additive import'
type: 'feature'
created: '2026-09-24'
status: 'in-progress'
review_loop_iteration: 0
context: []
baseline_commit: '17e5d0f8647dee333b775ab6b79c42efcb5f83d1'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A confirmed date-scoped archive (Story 2.4) still cannot be applied: `start_restore` and `verify_confirmed` refuse `date_filter.applied`. Nothing turns the locked-in skip/import/excluded partition into data, so a super admin cannot recover the patients a date-scoped archive holds.

**Approach:** The existing restore job (Story 2.3: start, lock, `run_restore`, snapshot, progress, notification) gains a date-scoped branch. It takes the same pre-restore snapshot of the target institution, then imports **only the confirmed import-set**, one patient per database transaction, every row with a fresh primary key and every foreign key remapped, and copies a patient's media only after that patient's transaction commits. Skip-set and excluded patients are never read into the database or extracted. Existing data is never updated, merged or deleted. A retry is a re-upload: the already-imported patients then match and become skip-set (Story 2.4).

## Boundaries & Constraints

**Always:**
- **Start.** `start_restore` and `verify_confirmed` stop refusing a date-scoped upload when `preview['date_scope_match']` is present (Story 2.4's usable-match rule) and the confirmed digest still matches; otherwise the `DATE_SCOPED` refusal stays, with wording that says why. Every other start rule of Story 2.3 is unchanged (super admin, `confirmed`, institutions exist, staged file intact, disk check, overlap lock, `applying` flip). The job's scope is the archive's one institution; `run_restore` chooses the branch solely from the confirmed snapshot's `date_filter.applied`.
- **`run_restore` date-scoped steps**, any failure before step 4 changing no domain data: (1) upload ready and version-1 snapshot; (2) re-hash the whole staged archive against `archive_sha256` and require the rebuilt preview digest to equal the confirmed one; (3) the same full-scope, undated pre-restore snapshot of the target institution as Story 2.3 (`take_snapshot`, unchanged), linked as `pre_restore_snapshot`; (4) import.
- **The partition is read from `confirmed_snapshot['date_scope_match']` and nothing else.** No re-matching, no re-derivation, no recomputation from the database or the archive. The target institution is re-resolved by its slug and its id must equal the snapshot's `target_institution_id`, otherwise the job fails before any patient is touched.
- **Import (AC 1, 3, 4).** Stream `db_export.json` (`backup/export_stream.py`) and route each record to its patient using the record's own `patient` (or, for `ProblemAction`, its `problem`, via the problem-to-patient map seen earlier in the stream); records of skip-set, excluded, unknown and referral patients are dropped and never applied. Nothing may load the whole archive or a whole model into memory: group the import-set's records by patient in a bounded way (for example a temporary spool under the job's directory, removed at the end). Then, for each import-set patient in archive order, **one `transaction.atomic()`**: insert the `Patient`, then its `Video`, `Attachment`, `GMAssessment`, `HINEAssessment`, `DevelopmentalAssessment`, `CDICRecord`, `GeneralPaediatricAssessment`, `Problem`, `ProblemAction` rows, each with a **fresh primary key** (`pk=None` through `serializers.deserialize('python', ...)`, so custom `save()` overrides are bypassed and `created_at`/`updated_at` preserved). Failure in one patient rolls back only that patient; patients already committed stay.
- **Foreign keys (AC 2).** `patient` and `problem` references go through this patient's source-pk to new-pk maps; `GMAssessment.video_file` goes through the Video map (a reference the map cannot resolve fails that patient); `Patient.institution` is set to the resolved target institution; `added_by`, `last_edit_by`, `performed_by`, `discharged_authorized_by` are kept when a user with that pk exists here and set to `NULL` otherwise, never to the restoring admin; many-to-many values (`diagnosis`, `indecation_for_gma`) are kept as shared reference data and a missing reference row fails that patient. `connection.check_constraints()` runs inside each patient's transaction so a dangling reference fails that patient, not the commit. A patient whose identifier now collides with an existing patient (created since validation) fails on the unique constraint like any other per-patient failure.
- **Media (AC 4).** After a patient's transaction commits, copy that patient's `Video.video_file` and `Attachment.attachment` files from `media/<name>` (path confined to `MEDIA_ROOT`, temp file, SHA-256 equal to the manifest, `os.replace`), and only those; never the whole `media/` folder. **An existing file at the target path is never overwritten** (existing patients are never touched): the file is written under a fresh available name and the new row's file field is updated to it. A missing member or failed copy leaves the patient imported and adds a warning.
- **Outcome states.** At least one patient committed: the job is `completed`, with a warning message when any patient failed or any media warning exists; the upload becomes `applied` and its staged archive is deleted (a retry is a re-upload, which re-classifies the imported patients as skip-set). No patient committed and at least one failed: `RestoreError`, job `failed`, upload back to `confirmed`, data unchanged. An import-set that is empty completes with nothing imported.
- **Result record.** A new nullable `BackupJob.restore_result` JSON (migration `0015`) is written in the terminal save for date-scoped restores: `{mode: 'date_scoped', imported, failed: [{archive_pk, reason}], skipped, excluded, media_warnings}`; counts for skipped/excluded come from the confirmed partition. The upload status page shows these counts and the failed patients after `applied`; the notification wording says "Restore completed" (or "with warnings") and includes the counts. The failed list shown is capped like media warnings; `restore_result` keeps the full list.
- Progress is monotonic 0..99 over re-hash, snapshot, spooling and import (advancing by patients done); the existing polling and notification mechanisms are reused unchanged. The lock, snapshot, `applying`/`applied` transitions, cancel refusal and log channel (`django.security.restore`) behave as in Story 2.3.

**Ask First:** None -- the partition, per-patient transactions, fresh keys, FK remap rules and retry-by-re-upload are fixed by the epic. The partial-failure states, never-overwrite media rule, `restore_result` field and the spool are this spec's own calls, flagged in Design Notes.

**Never:**
- No update, merge, overwrite or delete of any existing patient, row or media file; no application of skip-set or excluded patients; no referral or `Bookmark` rows; no institution or user creation.
- No re-matching or recomputation of the partition at any point; no whole-archive or whole-model load in memory; no `loaddata`; no new dependency.
- No change to Story 2.3's full-scope restore path or Story 2.4's matching. No audit-trail records (Story 2.6). No stale-job recovery (deferred since Story 1.1).

## I/O & Edge-Case Matrix

| Scenario | Behaviour |
|----------|-----------|
| Happy path: import-set of N patients with children and media | N patients committed each in its own transaction, fresh pks, FKs remapped, media copied after each commit; job `completed`; upload `applied`; snapshot linked first |
| Skip-set or excluded patient | No row, no media touched or extracted |
| One patient fails (bad reference, identifier now collides) | That patient rolls back; others continue; job `completed` with a warning naming it |
| Every attempted patient fails | Job `failed`, upload back to `confirmed`, data unchanged |
| Empty import-set | Job `completed`, nothing imported, upload `applied` |
| Source user pk missing here | User reference set to `NULL` |
| `GMAssessment.video_file` whose Video is not in this patient's map | That patient fails |
| Media path already exists on disk | Existing file untouched; archive copy written under a fresh name; new row points at it |
| Media member missing or checksum mismatch | Patient stays imported; warning listed |
| Institution gone, or its id differs from the snapshot's | Fails before any patient is touched; upload back to `confirmed` |
| Digest or archive hash changed since confirm | Fails at step 2; nothing changes |
| Snapshot fails | Job fails; nothing imported |
| Retry: same archive uploaded again after a partial run | New validation matches the imported patients as skip-set; only the rest are import-set |
| Process killed mid-import | Committed patients stay; job left `running` (stale-job recovery still deferred); re-upload re-classifies |
| Full-scope archive | Story 2.3 path, unchanged |

</frozen-after-approval>

## Code Map

- `backup/restore_apply.py:254` (`start_restore`) and `:458` (`verify_confirmed`) -- the two `date_filter.applied` refusals to relax when `preview['date_scope_match']` is present; `:497` (`take_snapshot`), `:1035` (`execute_restore`, the branch point: keep it for full scope), `:942` (`_restore_one_media`) and `:991` (`restore_media`) are the reuse points; `:756` (`_UserResolver`) already resolves user FKs and nulls missing users.
- New `backup/restore_import.py` -- `execute_import(job, progress_callback)`: confirmed-partition read, institution re-resolution, bounded grouping/spool of the import-set's records, the per-patient transaction (`_import_patient`), FK remap maps, post-commit per-patient media, result summary. Reuse `backup/export_stream.py` (`iter_export_records`, `START`, `ExportFormatError`), `restore_apply` helpers, and `PATIENT_KEY`/`RESTORE_MODEL_KEYS`/`MEDIA_FIELDS`.
- `backup/management/commands/run_restore.py:60-115` -- branch to `execute_import` when the confirmed snapshot's `date_filter.applied`; write `restore_result` in the terminal save; the `except RestoreError`/`ExportFormatError` path already routes to `_fail`, which reverts the upload to `confirmed`.
- `backup/models.py:11` (`BackupJob`) -- add nullable `restore_result` `JSONField`, migration `0015_...`.
- `backup/notifications.py` and `backup/templates/backup/restore_status_partial.html` -- counts in the completion notification body; imported/skipped/excluded/failed panel after `applied` (guard for a missing `restore_result`).
- `backup/restore_preview.py:154` (`build_preview`, `_snapshot`) -- `date_scope_match` already carried into `confirmed_snapshot` by Story 2.4; read only, not changed.
- Tests: `backup/tests/test_restore_apply.py` has the real-archive `run_restore` pipeline patterns; **`DateScopedWithMatchSummaryStillRefusedTest` (Story 2.4) asserts the refusal this story removes and is superseded** -- rewrite it to assert the new behaviour (a usable match starts; an unusable one still refuses). New `backup/tests/test_restore_import.py`.
- Facts (verified): every child model points at `patient` (`Video`, `Attachment`, `GMAssessment`, `HINEAssessment`, `DevelopmentalAssessment`, `CDICRecord`, `GeneralPaediatricAssessment`, `Problem`); `GMAssessment.video_file` is a OneToOne to `Video`; `ProblemAction.problem` points at `Problem`; the five patient identifiers are globally unique; `DeserializedObject.save()` uses `save_base(raw=True)`.

## Tasks & Acceptance

**Execution:**
- [ ] Model field + migration (`restore_result`); relax the two date-scoped refusals; branch in `run_restore`.
- [ ] `restore_import.py`: partition read and institution check, bounded grouping, per-patient transaction with FK remap and constraint check, post-commit media with the never-overwrite rule, result summary, outcome states.
- [ ] Notification and status-page changes; rewrite the superseded 2.4 refusal test.
- [ ] Tests for every matrix row, migrations check, full `backup` suite (background).

**Acceptance Criteria:** the epic's five Given/When/Then blocks for Story 2.5 (per-patient transaction with fresh keys and partial-failure isolation; FK remap, institution and user handling; skip-set and excluded untouched; media only after commit and only for imported patients; retry re-classifies imported patients as skip-set).

## Spec Change Log

_None yet — pre-review._

## Design Notes

- **Partial failure ends `applied`, not `confirmed`.** Once one patient has committed, the stored partition is stale (that patient would be imported again), so the same confirmed upload must never run twice; the epic's retry path is a re-upload. When nothing committed, the data is unchanged and the upload returns to `confirmed` as in Story 2.3. **Needs approval at the checkpoint.**
- **Never overwrite media.** An imported row's file name comes from the source system and can equal an existing patient's file path; overwriting it would damage an existing patient, which the epic forbids. The imported row is repointed to a fresh available name instead. **Needs approval at the checkpoint.**
- **`restore_result`** is the durable per-run record the status page needs (the message field is capped) and Story 2.6's audit trail will read; only date-scoped runs fill it.
- **Grouping without loading everything:** children reach their patient by the record's own foreign key, and Django JSON is one object keyed by model, so the import-set's records are regrouped by patient in a bounded spool; the choice of spool is the implementer's, the memory bound is not.
- **Deferred to the ledger (append after implementation):** stale `running` restore job recovery; media files of a partially failed patient that were already copied; per-patient progress granularity; conflict between an imported patient's media name and a later upload.

## Verification

**Commands:**
- `venv/Scripts/python.exe manage.py makemigrations --check --dry-run backup` -- no changes after `0015`.
- `venv/Scripts/python.exe manage.py test backup --noinput` (background; one run at a time).

**Manual checks (if no CLI):** none beyond the Django test client; not exercised in a browser.
