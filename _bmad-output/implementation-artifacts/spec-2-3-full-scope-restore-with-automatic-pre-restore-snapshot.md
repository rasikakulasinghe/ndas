---
title: 'Story 2.3: Full-scope restore with automatic pre-restore snapshot'
type: 'feature'
created: '2026-09-21'
status: 'in-progress'
review_loop_iteration: 0
context: []
baseline_commit: 'ae5848e'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A confirmed archive (Story 2.2) is only a recorded decision. Nothing applies it, so there is still no way to recover data from an archive, and nothing protects the current data if a restore goes wrong.

**Approach:** A super admin starts the restore of a confirmed, full-scope upload. A detached `run_restore` process first takes a full-scope, undated snapshot of the current data for the same institutions (a `pre_restore_snapshot` job, using the existing export), then replaces those institutions' rows for the ten restorable models with the archive's rows, original primary keys preserved, all in **one database transaction**, and only after it commits copies the archive's media files into place. A job-level lock keeps a second restore or backup of an overlapping scope out while it runs, and the restore gets Story 1.5's progress polling and finish notification. Referral models are not touched.

## Boundaries & Constraints

**Always:**
- Same access rules as Stories 2.1/2.2: `UserType.SUPERADMIN` only, ownership 404 for another user's upload, POST-only and CSRF-protected start, rate limit `5/m`, denials logged to `django.security.restore`.
- Only a `confirmed` upload can be started. Starting is a separate explicit action from confirming (2.2's confirm stays record-only). Start refuses, changing nothing, if: the upload is not `confirmed`; the digest recomputed from the current preview no longer equals `confirmed_snapshot['digest']`; any snapshot institution is gone from this system; the archive is date-scoped; the lock finds an overlapping pending/running job; or the disk check (snapshot estimate + archive size, with the existing 1.2x safety margin and 500 MB floor) fails. A refused start leaves the upload `confirmed` and retryable.
- **Job lock (AC c).** The overlap rule now living inline in `backup_create` (a `system` job overlaps everything; otherwise institution-id sets must intersect; checked over all pending/running jobs of any type, under `transaction.atomic()` + `select_for_update()`, with the job created inside the same atomic block) is extracted into one shared helper and used by `backup_create` and the restore start. A running restore therefore blocks an overlapping backup and restore, and a running backup blocks an overlapping restore start. `backup_create`'s behaviour and messages are unchanged. The pre-restore snapshot job is created by `run_restore` **without** the lock (it is covered by the restore job's lock).
- Start creates, in one atomic block with the lock check: the `restore` `BackupJob` (`pending`, scope shape = the upload's scope type and institutions resolved on this system, `triggered_by`, `trigger_institution` chosen exactly as `backup_create` does, `restore_upload` = the upload) and flips the upload to `applying`. The process is then launched through `_launch_detached_command` (which stays in `backup/views.py`). If launch fails, the job is marked `failed` and the upload goes back to `confirmed`.
- **`run_restore <job_id>`** (detached, mirrors `run_backup`: every save uses `update_fields`, terminal status + progress in one save, notification after) does, in order, and any failure before step 5 changes no domain data:
  1. Marks the job `running`; refuses (fails the job) unless the upload is `applying` with a version-1 `confirmed_snapshot`.
  2. **Re-checks the confirmation**: re-hashes the whole staged archive against `archive_sha256` (Story 2.1's deferred precondition; the archive may be 50 GiB, so this is streamed), and rebuilds the preview facts and requires the digest to equal `confirmed_snapshot['digest']`. Any mismatch fails the job.
  3. **Snapshot (AC a):** creates a `BackupJob(job_type=pre_restore_snapshot)` with the same scope shape/institutions, no date filter, `triggered_by`/`trigger_institution` copied, runs it in-process through `create_export` (its own status, progress and `archive_checksum`, exactly as `run_backup` would set them), and links it as the restore job's `pre_restore_snapshot`. If the snapshot fails, the restore job fails and touches nothing. The snapshot archive must exist on disk before step 5.
  4. **Preflight (read-only):** streams `db_export.json` once and rejects the restore, with a specific message, if: a model key is unknown, or model keys are not in the fixed order; a record's pk repeats within its model; a `Patient.institution` value is not the id of one of the target institutions matched by the manifest slugs (cross-server archives whose institution ids differ are not restorable yet — see Design Notes); an archive pk already exists in the model **outside** the rows about to be deleted (a patient that was moved to another institution since); a `Patient` identifier (`bht`, `nnc_no`, `ptc_no`, `pc_no`, `pin`) belongs to an existing patient outside the deleted rows; or a many-to-many reference (`indecation_for_gma`, `diagnosis`) names a reference row missing here. Referral keys are skipped, never read into memory.
  5. **Apply (AC b):** ONE `transaction.atomic()` for all ten models, in this fixed order: delete in reverse (`ProblemAction`; `Problem`, `GeneralPaediatricAssessment`, `CDICRecord`, `DevelopmentalAssessment`, `HINEAssessment`, `GMAssessment`, `Attachment`, `Video`; `Patient`), selecting the rows with the export's own scoping (`_model_export_plan`, no date), then load in forward order (`Patient` first … `ProblemAction` last) through `serializers.deserialize('python', …)` + `.save()` in batches, streaming the JSON, original pks kept. Deleting uses `QuerySet._raw_delete` (no cascade, no signals, no `django_cleanup` file deletion) plus explicit removal of the deleted patients' and assessments' many-to-many through rows. After the load, in the same transaction: `ReferralSent.patient` set to `NULL` and `institution.PatientMoveLog` rows removed for patients that no longer exist (what their cascade/SET_NULL would have done, and nothing else); every user foreign key (`added_by`, `last_edit_by`, `performed_by`, `discharged_authorized_by`, …) whose user does not exist here is set to `NULL`; `connection.check_constraints()` is called so a dangling reference fails inside the transaction (rolling everything back) rather than at commit; and on PostgreSQL each restored model's sequence is reset (`connection.ops.sequence_reset_sql`). Referral models and `Bookmark` are never read or changed.
  6. **Media, after commit only:** for each restored `Video.video_file` and `Attachment.attachment`, extracts `media/<name>` from the archive to `MEDIA_ROOT/<name>` (path confined to `MEDIA_ROOT`, written to a temp file, SHA-256 compared with the manifest, then `os.replace`d). A missing member or failed file does not undo the database: the job completes with a warning listing each file, like Story 1.1's skipped media. Files of deleted rows that the archive does not contain are left on disk, never deleted.
  7. Terminal save: `completed` (100%) or `failed`; on completion the upload becomes `applied` and its staged archive is deleted (best-effort); on **failure the upload returns to `confirmed`** (the transaction made the data unchanged) so the user can retry or cancel. The restore job's `error_message` says what failed and names the snapshot job.
- **Progress and notification (AC d):** the restore job's `progress_pct` is monotonic, mapped over the steps above (re-hash, snapshot, preflight, apply, media). The upload status page/fragment shows the restore job's status and progress while the upload is `applying` and its outcome afterwards, and keeps HTMX polling only while `applying`. On finish `notify_job_finished` creates a notification for the triggering user: new types `RESTORE_COMPLETED` / `RESTORE_FAILED`, restore wording, linking to the upload's status page. Snapshot jobs never notify.
- The `pre_restore_snapshot` is exempt from retention pruning (AC a): there is no pruning yet (Epic 3), so this story only fixes the contract — a snapshot job is identifiable by `job_type` and referenced by `restore_job.pre_restore_snapshot`, and a test asserts the contract Epic 3 must honour. The snapshot appears in the backup history labelled as a pre-restore snapshot.
- A `confirmed`/`applying` upload keeps blocking a new upload by the same user (`applying` joins `confirmed` in the 2.2 refusal); `applying` cannot be cancelled; `applied` counts as finished (`FINISHED_STATUSES`).

**Ask First:** None — referrals left untouched, missing institutions blocking, unverified archives via checkbox and the 50 GiB limit are decided. The single-transaction departure from the planning docs' per-model transactions and the separate "Start restore" step are flagged in Design Notes for approval at this checkpoint.

**Never:**
- No partial restore: if the transaction fails, nothing changes. No per-model commits.
- No use of `.delete()`/cascade for restored models, and no deletion of media files.
- No creation of institutions, users or reference rows; no restore of referral models, `PatientMoveLog` content, or `Bookmark`.
- No date-scoped restore (Stories 2.4/2.5). No restore audit-trail records (Story 2.6). No retention/pruning (Epic 3).
- No change to `django-cleanup`, other apps' models, or Story 2.1/2.2 behaviour beyond the status transitions named above. No maintenance mode (AD-16: accepted risk).
- Nothing loads the whole archive or a whole model in memory; nothing is read twice except the deliberate re-hash.

## I/O & Edge-Case Matrix

| Scenario | Behaviour |
|----------|-----------|
| Happy path, single institution | Snapshot completes; ten models replaced; media copied; job `completed`; upload `applied`; staged archive gone; notification "Restore completed" |
| Restore start while an overlapping job is pending/running | Refused with a message; upload stays `confirmed`; no job row |
| Backup start while a restore is running for that scope | Refused by the same lock; unchanged message |
| Disk too small | Start refused with a message; upload stays `confirmed` |
| Staged archive changed/truncated since confirm | Step 2 fails the job; no snapshot, no data change; upload back to `confirmed` |
| Snapshot fails | Restore job fails with the reason; data untouched |
| Preflight finds a foreign-institution patient, identifier or pk collision, or a missing reference row | Job fails before step 5 with the specific reason; data untouched |
| Error part-way through apply (bad record, constraint) | Transaction rolls back; data exactly as before; job `failed` naming the snapshot |
| Archive lacks a patient that exists now | That patient and its children are removed; `ReferralSent.patient` for it becomes null; its `PatientMoveLog` rows are removed |
| Archive user id not present here | That user reference becomes null; restore proceeds |
| Media member missing/unwritable | Database restored; job `completed` with a warning listing the files |
| Files present at restored paths | Untouched by delete (no `django_cleanup` removal); overwritten by the archive's copy |
| Process killed mid-apply | Transaction never commits, data unchanged; job left `running` (recorded as deferred: no stale-job recovery yet) |
| Cancel while `applying` | Refused |

</frozen-after-approval>

## Code Map

- `backup/models.py:11` (`BackupJob`) -- add `restore_upload` (nullable FK to `RestoreUpload`, `SET_NULL`, `related_name='restore_jobs'`) and `pre_restore_snapshot` (nullable self-FK, `SET_NULL`, `related_name='restores_using_snapshot'`); `RestoreUpload` (`:171`) needs no new columns. `ndas/custom_codes/choice.py:271` (`RestoreUploadStatus`) -- add `APPLYING`, `APPLIED`; `:220` (`NotificationType`) -- add `RESTORE_COMPLETED`, `RESTORE_FAILED`. Migrations: `backup/0013_...` and the resulting `referral` choices migration (as Story 1.5 did for `BACKUP_*`), generated with `venv/Scripts/python.exe manage.py makemigrations --no-input` and reviewed (only these apps).
- New `backup/job_lock.py` -- the extracted overlap check + guarded create (`create_job_unless_overlapping(...)` returning the job or `None`), plus `resolved_institution_ids(job)` moved from `backup/views.py:201` (keep a name in `views.py` if tests import it). Used by `backup_create` (`views.py:365-410`) and the new start view.
- `backup/views.py:213` (`_launch_detached_command`) -- stays here; new `restore_start` view beside `restore_confirm` (`:726`), same gate/ownership/`handle_view_errors` pattern; `_restore_status_context` (`:628`) gains the restore job; `restore_upload` (`:522`) refusal now covers `applying`.
- New `backup/restore_apply.py` -- the service layer: `start_restore(...)`, `verify_confirmed(upload)`, the streaming reader (`iter_export_records`, incremental `json.JSONDecoder.raw_decode`, no new dependency), `preflight(...)`, `apply_restore(...)`, `restore_media(...)`, and the snapshot helper. Reuses `_model_export_plan`, `EXPORT_MODEL_KEYS`, `REFERRAL_MODEL_KEYS`, `build_preview` for the digest, `create_export`, `has_sufficient_disk_space`. Keeps `restore_preview.py` for the 2.2 gate.
- New `backup/management/commands/run_restore.py` -- thin driver copied from `run_backup.py`'s structure (running → steps → one terminal save → notify), calling `restore_apply`.
- `backup/notifications.py:31,52` -- `_build_content`/`notify_job_finished` become job-type-aware; restore link is `reverse('backup:restore-status', args=[upload.pk])`; snapshot jobs are skipped.
- `backup/restore_validation.py:91` (`FINISHED_STATUSES`) -- add `applied`. `backup/restore_preview.py:68` (`CANCELLABLE_STATUSES`) -- unchanged (excludes `applying`/`applied`).
- `backup/urls.py` -- `restore/<int:pk>/start/`.
- Templates: `restore_status_partial.html` (poll while `applying`; "Start restore" button on the confirmed panel; restore job progress/outcome), `restore_status.html`, backup history list (label the job type).
- Reference facts (from the research pass, verified against the code): inbound FKs to the ten models are non-null CASCADE inside the set, except `referral.ReferralSent.patient` (`SET_NULL`) and `institution.PatientMoveLog.patient` (`CASCADE`); `Patient.institution` is `PROTECT`; `Patient.bht/nnc_no/ptc_no/pc_no/pin` are each globally unique; `DeserializedObject.save()` uses `save_base(raw=True)`, bypassing the models' custom `save()` and preserving `created_at`/`updated_at`; `django_cleanup` removes files after commit for `.delete()`/cascade but not for `_raw_delete`; SQLite handles explicit-pk sequences itself, PostgreSQL does not.
- Tests: `backup/tests/restore_helpers.py` (`build_archive`, `IsolatedBaseDirMixin`) for archives; new `test_restore_apply.py`, `test_restore_command.py` additions, `test_job_lock.py`, and additions to `test_views.py`, `test_restore_views.py`, `test_notifications.py`.

## Tasks & Acceptance

**Execution:**
- [ ] Models, choices, migrations (`backup`, `referral`); `job_lock.py` extraction with `backup_create` refactored onto it and its existing tests unchanged and green.
- [ ] `restore_apply.py` + `run_restore` command: re-hash/digest re-check, snapshot, streaming reader, preflight, atomic delete-and-load, post-load reference fixes, constraint check, PostgreSQL sequence reset, media extraction, terminal states.
- [ ] `restore_start` view + URL + template changes (start button, polling, restore progress/outcome, job-type label) + upload-refusal and status transitions + notification changes.
- [ ] Tests (below), the full backup suite, migration check, encoding scan.

**Acceptance Criteria:**
- Given a confirmed, full-scope upload, when the super admin starts it and `run_restore` runs, then a `pre_restore_snapshot` job for the same scope completes first, is linked from the restore job, and holds the pre-restore data; then the ten models' rows in that scope equal the archive's rows with original pks, `created_at`/`updated_at` preserved, and rows outside the scope are untouched.
- Given a patient that exists now but not in the archive, when restored, then that patient and its children are gone, its `ReferralSent.patient` is null, and no other referral row changed.
- Given any failure before step 5, or during it, then the domain data is exactly as before and the upload is `confirmed` again.
- Given a running restore for a scope, then a backup or restore start for an overlapping scope is refused and one for a disjoint scope is accepted; and the reverse.
- Given a restore job, then its status/progress are pollable on the upload page and a `RESTORE_COMPLETED`/`RESTORE_FAILED` notification reaches the triggering user.
- Given restored files at existing paths, then they remain (no `django_cleanup` deletion) and hold the archive's bytes.

## Spec Change Log

_None yet — pre-review._

## Design Notes

- **One transaction, not per-model (deviation from ARCHITECTURE-SPINE AD-3).** Deleting `Patient` cascades to every other restored table, so per-model commits could leave an empty or half-restored database. A single transaction keeps "all or nothing"; the pre-restore snapshot remains the manual recovery path for a restore that succeeded but was wrong. Cost: on SQLite the write lock is held for the whole apply, so other writers wait (AD-16 already accepts no maintenance mode); PostgreSQL only locks touched rows. **Needs your approval at the checkpoint.**
- **Separate "Start restore" step.** Story 2.2's tests and copy fix confirm as record-only ("not applied yet"); a distinct start keeps that intact and gives a natural retry when the lock or disk check refuses. Alternative: have confirm launch the job (rejected: changes shipped 2.2 behaviour).
- **`_raw_delete` and explicit fix-ups** are used because `.delete()` would cascade into `PatientMoveLog`, null `ReferralSent.patient` for patients that are then restored anyway, and schedule `django_cleanup` to delete the files the restore is about to reuse. It is a private Django API, so a test pins its no-cascade/no-file-deletion behaviour.
- **Institution mapping is by pk equality.** The manifest carries slugs; the records carry institution pks. This story only restores when every `Patient.institution` in the archive is one of the target institutions matched by slug (correct for restoring onto the same system, the intended use). A cross-server archive whose ids differ is rejected in preflight with a clear message; a same-id-different-institution coincidence cannot be detected (known limitation, recorded in `deferred-work.md`; the snapshot is the backstop).
- **Records deleted by scope, not by archive pks:** using the export's own scoping guarantees the delete set is exactly the set a same-scope backup would have exported.
- **Deferred to the ledger (append after implementation):** stale `running` restore job / stuck `applying` upload recovery (Story 1.1's jobs have the same gap); leftover media files of deleted rows; retention pruning must exclude `pre_restore_snapshot` (Epic 3); cross-server institution-id mapping; SQLite write-lock duration for large restores.

## Verification

**Commands:**
- `venv/Scripts/python.exe manage.py makemigrations --check --dry-run` -- expected: no changes after the new migrations.
- `venv/Scripts/python.exe manage.py test backup --noinput` -- expected: all pass (run in the background; ~12-16 min; one run at a time).
- An encoding scan (every edited `.py`/`.html` is valid UTF-8, no stray CR) after each implementation round.

**Manual checks (if no CLI):**
- Restore a real archive on a scratch database, open the status page during the run, and confirm data, media and the notification. Not doable by the agent; the test client covers everything else.
