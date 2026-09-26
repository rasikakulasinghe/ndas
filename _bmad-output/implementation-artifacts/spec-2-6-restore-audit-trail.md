---
title: 'Story 2.6: Restore audit trail'
type: 'feature'
created: '2026-09-26'
status: 'in-review'
review_loop_iteration: 0
context: []
baseline_commit: '2dc57b67f5cf05fe0555b0d2fb7fd596cc747d9e'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A finished restore leaves no single answer to "who restored what, when, and how much". A full-scope restore stores no result at all, a date-scoped one stores counts but not who ran it, and the security log's completion line (date-scoped only) has no actor. Failed restores and two denial paths (another user's or an unknown upload) leave no audit line.

**Approach:** Every restore job that ran ends with one self-contained, PHI-free audit record on its `BackupJob` (new nullable `restore_audit` JSON, migration `0016`) and one matching line in `logs/security.log`; every remaining denied or failed path logs to `logs/security.log` through one helper. No new page, no new model, no change to what a restore does.

## Boundaries & Constraints

**Always:**
- **Record content** (written in the same terminal save as status, for `completed` and `failed`): `version: 1`; `actor: {id, username, user_type}` (embedded, so it survives user deletion); `upload_id`; `archive: {filename, sha256, source_job_id}`; `scope: {mode: 'full'|'date_scoped', scope_type, institutions: [{id, slug, name}], date_filter: {start, end}}` (system scope takes the manifest's slugs); `outcome: 'completed'|'completed_with_warnings'|'failed'`; `started_at`, `finished_at` (UTC ISO); `snapshot_job_id`; `counts`; `error` (failed only).
- **Counts.** Date-scoped: `imported`, `skipped`, `excluded`, `failed`, `media_warnings` (numbers), plus `patients`: `[[archive_pk, new_pk], ...]` for every committed patient (integers only). Full-scope: records loaded per model, `referral_links_cleared`, `move_logs_removed`, `media_warnings`. A failed job carries whatever counts exist (zeros otherwise).
- **PHI-free.** No patient name, identifier, note or archive record content anywhere in the record or the log line; `error` is the job's already-clipped, PHI-free failure text. The record is assembled in one place, `backup/restore_audit.py`, and its log line is written by the same call.
- **One security-log line** per finished restore job, `django.security.restore` logger, INFO for `completed`, WARNING for `completed_with_warnings`/`failed`: actor, upload, job, mode, scope slugs, outcome, counts, snapshot. It is written even if the job's own save fails.
- **Denied paths.** A super admin naming an upload that is not theirs or does not exist still gets 404, and now also a `Restore access denied (unknown or foreign upload)` warning with user, view and upload id, from every restore view that looks up an upload. Existing denial and refusal logs (non-super-admin, upload/confirm/start refusals, archive rejection) are unchanged in behaviour.
- The audit is best-effort: a failure while building or saving it is logged and never changes the restore's outcome, its status, its notification or the upload's state.
- Story 2.5's `restore_result`, the status page, notifications and `_log_summary` are unchanged.

**Ask First:** None -- the fields, the archive-pk to new-pk map for date-scoped runs (resolving the Story 2.5 ledger item), no review page and no new model are this spec's own calls, flagged in Design Notes.

**Never:**
- No page, view, URL, admin registration or model for reviewing the audit (Epic 3 history owns lists); no separate audit table.
- No audit of backup creation, download, delete or prune (Epics 1 and 3); no change to restore behaviour, matching or the import/full-scope engines beyond returning the counts and pk map they already hold.
- No PHI in logs; no raw exception text in the record or line for a date-scoped run; no stale-job recovery (deferred); no new dependency.

## I/O & Edge-Case Matrix

| Scenario | Behaviour |
|----------|-----------|
| Full-scope restore completes | `restore_audit` outcome `completed` with scope/institutions, per-model counts, `referral_links_cleared`, `move_logs_removed`, snapshot id; INFO line |
| Date-scoped completes clean | outcome `completed`, imported/skipped/excluded counts, `patients` map; INFO line |
| Date-scoped with failed patients, media warnings or an early stop | outcome `completed_with_warnings`; WARNING line |
| Restore fails (any stage after start) | outcome `failed`, `error`, counts so far, snapshot id if taken; WARNING line; upload/notification behave as today |
| Empty import-set | outcome `completed`, `imported: 0`, empty `patients` |
| Acting user or an institution later deleted | The record still shows the embedded username and institution slug and name |
| Audit build or save raises | Logged; restore outcome and notification unchanged |
| Super admin opens another user's or an unknown upload | 404 plus one `unknown or foreign upload` warning |
| Non-super-admin at any restore URL, or an upload/confirm/start refusal, or a checksum/schema rejection | Logged to `security.log` as today (regression-tested) |

</frozen-after-approval>

## Code Map

- New `backup/restore_audit.py` -- `build_audit(job, *, outcome, error='')`, `record_and_log(job, ...)`, `log_unknown_upload(request, view_name, pk)`; reuse `restore_validation.security_logger` and `restore_validation._clip`.
- `backup/management/commands/run_restore.py:39` (`_fail`) and `:111-134` (terminal success) -- both terminal saves gain `restore_audit` in `update_fields`; `started_at` captured at `:72`. `date_scoped` already computed at `:92`.
- `backup/restore_apply.py:144` (`RestoreResult`) and `:1063` (`execute_restore`) -- add `referral_links_cleared`, `move_logs_removed` (already returned by `apply_restore` as `nulled`, `removed`) and per-model loaded counts; `scope_args` `:191` resolves the job's institutions; `snapshot` id via `job.pre_restore_snapshot_id`.
- `backup/restore_import.py` -- `_Outcome` and `ImportResult`/`summary` at `:745-800` (`imported`, `failed`, `skipped`, `excluded`, `media_warnings`, `aborted`); expose each committed patient's `(archive_pk, new_pk)` from `_import_patient`'s per-patient id map (built today and discarded); `_log_summary` stays.
- `backup/models.py:11` (`BackupJob`) -- nullable `restore_audit` `JSONField`; migration `0016_backupjob_restore_audit` (CRLF by repo convention).
- `backup/views.py:622-835` -- the five `get_object_or_404(RestoreUpload, pk=pk, uploaded_by=request.user)` lookups (`restore_status`, `_fragment`, `_preview`, `_confirm`, `_start`, `_cancel`); wrap them so a miss logs then re-raises `Http404`. `_deny_restore` at `:442` is the existing helper pattern.
- Tests: new `backup/tests/test_restore_audit.py`; extend `test_restore_command.py`, `test_restore_import.py`, `test_restore_views.py`. `backup/tests/restore_helpers.py` has the real-archive pipeline builders.
- Facts (verified): `PatientMoveLog`/`InstitutionSwitchLog` are model-only audit records with no review page (precedent for no UI); `BackupJob.triggered_by`, `scope` and `scopes` are `SET_NULL`; `security_file` only writes when `DEBUG` is off, so tests assert via `assertLogs('django.security.restore')`.

## Tasks & Acceptance

**Execution:**
- [ ] `backup/models.py`, migration `0016` -- add `restore_audit`; `makemigrations --check` clean.
- [ ] `backup/restore_audit.py` -- build the record and the log line in one place; best-effort wrapper; the unknown-upload log helper.
- [ ] `backup/restore_apply.py`, `backup/restore_import.py` -- return the counts, `referral_links_cleared`, `move_logs_removed` and the committed-patient pk map; no behaviour change.
- [ ] `backup/management/commands/run_restore.py` -- write and log the audit in both terminal saves.
- [ ] `backup/views.py` -- log foreign/unknown upload lookups in the restore views.
- [ ] Tests for every matrix row (record shape, PHI-free assertion against seeded identifiers, deleted actor/institution, audit failure is harmless, regression of each existing denial log), migrations check, full `backup` suite (background).

**Acceptance Criteria:**
- Given a completed restore (either scope), when its job is reviewed, then `restore_audit` shows the acting super admin, timestamps, scope (mode, institutions, date range) and, for a date-scoped run, patients skipped/imported/excluded.
- Given a denied attempt (institutional admin, foreign upload) or a checksum/schema rejection, when it happens, then it is logged to `logs/security.log` through the `django.security.restore` logger.
- Given a failed restore, when reviewed, then it shows the failure outcome with the actor and scope, without changing the failure handling of Stories 2.3 and 2.5.

## Spec Change Log

## Design Notes

- **Separate `restore_audit` field, not a widened `restore_result`.** `restore_result` drives the status panel and notification (date-scoped only, null elsewhere); reusing it would show result panels for failed or full-scope jobs. The audit needs its own stable, versioned shape and embeds the actor and institution names so it outlives `SET_NULL`. **Needs approval at the checkpoint.**
- **No review page.** Epic 3.1 builds history lists; the existing audit models (`PatientMoveLog`, `InstitutionSwitchLog`) also have no UI. Review is by reading the job row. **Needs approval at the checkpoint.**
- **`patients` map** lets an auditor trace a new patient row to its archive record (integers only, one pair per committed patient); full-scope keeps original keys, so it needs none. This resolves the Story 2.5 ledger item.
- **Cross-story constraint (record in the ledger):** Epic 3's manual delete and retention pruning must never remove `restore` jobs, or the audit goes with them.
- **Deferred to the ledger (append after implementation):** a review page or admin list for restore audits; `restore_audit` for jobs killed mid-run (no stale-job recovery yet); the `security_file` handler is skipped when `DEBUG` is on, so denials are not written to the file in development.

## Verification

**Commands:**
- `venv/Scripts/python.exe manage.py makemigrations --check --dry-run backup` -- no changes after `0016`.
- `venv/Scripts/python.exe manage.py test backup --noinput` (background; one run at a time) -- all pass.
