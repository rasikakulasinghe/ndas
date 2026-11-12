---
title: 'Deferred-Work Batch 5a: Backup/Restore Error-Message Sanitization'
type: 'bugfix'
created: '2026-11-12'
status: 'done'
baseline_commit: 'e56306a92733ef122f967a934ad96b172ba6b820'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A verified-still-open `deferred-work.md` entry: ~13 call sites across `run_backup.py`, `run_restore.py`, `restore_apply.py`, `validate_restore_upload.py` and `views.py` interpolate raw exception text (can carry filesystem paths or DB driver messages) into `BackupJob.error_message`/`RestoreUpload.error_message`. `status.html` and (since batch 4) `manager.html` render that field verbatim to institutional admins, and `notify_job_finished` echoes it into notification bodies.

**Approach:** Replace each raw-exception interpolation with the `type(e).__name__` pattern already used elsewhere in this same code (e.g. `run_backup.py`'s interrupt branch, `run_restore.py`'s `audit_message`); every `logger.exception`/`logger.warning` call keeps its full detail unchanged. Annotate the ledger entry as resolved.

## Boundaries & Constraints

**Always:** Every `logger.*` call keeps its full exception detail — only the admin-/user-visible `error_message` (and anything built from it, like notification bodies) changes. Keep `run_restore._fail`'s `audit_message` architecture working; after this change it may become textually identical to the job message at the two sites that pass one — dropping the now-redundant explicit kwarg is optional cleanup, not required. Keep each fixed-phrase prefix in `validate_restore_upload.py` (e.g. "could not be recorded", "failed unexpectedly") and only replace the trailing raw-exception interpolation. Update every test that currently asserts raw exception text (`'boom'`, `'kaboom'`, `'transient db error'`, `'db gone'`) in an `error_message` or notification body produced by a changed site, to assert the exception's type name instead. Tests asserting a fixed-phrase prefix only (e.g. `'could not be recorded'`, `'Allow unverified origin'`) are unaffected and must keep passing unchanged.

**Ask First:** None — mechanical text-content change; no control-flow, status, or notification-trigger changes.

**Never:** No new models, fields or migrations. No change to `sweep_stale_jobs.py` (its `error_message` is already a fixed template with no raw exception text — verified, not in scope). No change to `run_restore`'s missing `KeyboardInterrupt`/`SystemExit` handling (tracked separately; needs its own design). No change to `abort_start`'s own passthrough behavior (it stores whatever message it's given — the fix is at its *callers* in `views.py`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Backup export raises `RuntimeError('boom')` | `create_export` fails mid-run | `job.error_message` contains `RuntimeError`, never `'boom'`; notification body matches | full exception still in `run_backup.log` via `logger.exception` |
| Restore's "could not start" / "unexpected error" branches raise `OperationalError(...)` | DB hiccup during `run_restore.handle` | `job.error_message` contains `OperationalError`, never the driver's raw message | audit record already used this pattern -- unaffected |
| `validate_restore_upload`'s terminal save itself fails | `RestoreUpload.save` raises after validation finished | `error_message` keeps "...could not be recorded" prefix, exception type instead of raw text | fallback save path unchanged |
| `_launch_detached_command` raises `OSError` (e.g. permission denied) | subprocess launch fails for backup/validate/restore | `error_message` contains `OSError` (or its subclass name), never the raw path/errno text | flash message to the user unchanged |

</frozen-after-approval>

## Code Map

- `backup/management/commands/run_backup.py:62,93` -- the "failed to start" branch and the `_record_failure(...)` call in `handle`; replace `{e}` with `{type(e).__name__}`.
- `backup/management/commands/run_restore.py:109-113,144-148` -- `handle`'s two `_fail(...)` calls ("could not start"/"unexpected error"); drop `_clip(e, 200)` from the job-facing message in favor of `type(e).__name__` (already used in the adjacent `audit_message`).
- `backup/restore_apply.py:505-508` `verify_confirmed`'s `RestoreError` on an unreadable staged archive, `:580` `take_snapshot`'s `snapshot.error_message`, `:582-587` `take_snapshot`'s `RestoreError` on export failure, `:980` `apply_restore`'s `RestoreError` on a rolled-back apply failure, `:1040` `_restore_one_media`'s per-file write-failure warning, `:1079` `restore_media`'s outer "stopped early" warning (both flow into `job.error_message` via `run_restore.py`'s `format_media_warnings`) -- same `{e}`/`_clip(e, ...)` → `type(e).__name__` replacement. (The last three were missed in the initial pass and added during review after blind-hunter and verification-gap both independently found the same gap.)
- `backup/management/commands/validate_restore_upload.py:55` `_save_terminal` fallback, `:117` the unexpected-exception branch in `handle` -- keep each fixed-phrase prefix, replace only the trailing `_clip(..., 200)` interpolation with the exception's type name.
- `backup/views.py:445` (`backup_create`), `:1068,1073` (`_mark_upload_failed` calls in the restore-upload view), `:1295` (`abort_start(...)` call in the restore-start view) -- four `OSError`/`Exception` launch/store-failure sites; same replacement.
- Test updates: `backup/tests/test_management.py` (assertions on `job.error_message`/`notif.body` currently checking `'boom'`, `'transient db error'` → the exception's type name, e.g. `test_export_failure_notifies_backup_failed`, `test_failed_to_start_notifies_backup_failed`, `test_export_failure_whose_zip_cleanup_fails_is_still_recorded_and_notified`); `backup/tests/test_restore_command.py::test_failure_at_63_percent_ends_failed_with_progress_zero` (`'kaboom'` → `'RuntimeError'`) and `::test_unexpected_exception_becomes_failed_and_deletes_file` (same).
- `_bmad-output/implementation-artifacts/deferred-work.md` -- annotate the entry starting "`BackupJob.error_message` stores raw exception text" with a `RESOLVED by:` line.

## Tasks & Acceptance

**Execution:**
- [x] `backup/management/commands/run_backup.py` -- sanitize the two raw-exception `error_message` sites.
- [x] `backup/management/commands/run_restore.py` -- sanitize the two `_fail(...)` call sites.
- [x] `backup/restore_apply.py` -- sanitize `verify_confirmed`, `take_snapshot`, `apply_restore`, `_restore_one_media` and `restore_media`'s six sites (three found in review: `apply_restore:980`, `_restore_one_media:1040`, `restore_media:1079`).
- [x] `backup/management/commands/validate_restore_upload.py` -- sanitize the two sites, keeping their fixed-phrase prefixes.
- [x] `backup/views.py` -- sanitize the four launch/store-failure sites.
- [x] Update the affected tests listed in the Code Map (plus `test_restore_import.py`, `test_views.py`, `test_restore_views.py`, and `test_restore_apply.py`, surfaced by the full-suite run; strengthened `test_restore_command.py::test_terminal_save_failure_falls_back_to_failed` and `test_restore_audit.py::test_could_not_start_the_job_is_a_failed_audit_without_raw_exception_text` with explicit raw-text-absence/type-name-presence assertions on `error_message` during the Matrix Test Audit).
- [x] `deferred-work.md` -- annotate the entry as resolved.

**Acceptance Criteria:**
- Given any of the 13 sanitized sites raising an exception whose message contains a filesystem path or DB driver text, when the terminal state is saved, then `error_message` (and any notification body built from it) contains only the exception's type name, never the raw message.
- Given `backup`'s full test suite, when run after this change, then every test passes, including the updated assertions.

## Design Notes

The sanitization pattern has existing precedent in this codebase: `run_backup.py:107`'s interrupt branch and `run_restore.py`'s `audit_message` computations already use `type(e).__name__` instead of raw exception text. This spec extends that existing convention to the remaining sites that still leak raw text into the *admin-visible* field, rather than inventing a new scheme.

## Verification

**Commands:**
- `venv/Scripts/python.exe manage.py test backup` (with `SECURE_SSL_REDIRECT=False` for the run) -- expected: all pass, including the updated assertions.

**Manual checks (if no CLI):**
- Grep the five changed files for `{e}` / `_clip(e,` interpolations feeding `error_message` -- none should remain outside the logger calls and the already-safe interrupt/`audit_message` sites.

## Suggested Review Order

**The sanitization pattern itself**

- Simplest example of the fix: a raw exception swapped for its type name, logger untouched below it.
  [`run_backup.py:93`](../../backup/management/commands/run_backup.py#L93)

- The existing safe precedent this batch generalizes -- already used `type(e).__name__` before this change.
  [`run_backup.py:107`](../../backup/management/commands/run_backup.py#L107)

**Restore command's two failure branches**

- "Could not start": job message now matches the `audit_message` computed right below it.
  [`run_restore.py:109`](../../backup/management/commands/run_restore.py#L109)

- "Unexpected error": dropped the date-scoped/non-date-scoped branch -- now unconditionally safe.
  [`run_restore.py:145`](../../backup/management/commands/run_restore.py#L145)

**The three sites review found missing from the initial pass**

- `apply_restore`'s rolled-back-failure message now matches its own `audit_message` exactly.
  [`restore_apply.py:980`](../../backup/restore_apply.py#L980)

- Per-file media write failure -- this warning reaches `job.error_message` via `format_media_warnings`.
  [`restore_apply.py:1040`](../../backup/restore_apply.py#L1040)

- Outer "stopped early" warning -- same downstream path, same fix.
  [`restore_apply.py:1079`](../../backup/restore_apply.py#L1079)

**Fixed-phrase prefixes kept intact**

- Prefix text ("could not be recorded") preserved; only the trailing raw exception replaced.
  [`validate_restore_upload.py:56`](../../backup/management/commands/validate_restore_upload.py#L56)

- Same prefix-preserving pattern for the unexpected-exception branch.
  [`validate_restore_upload.py:119`](../../backup/management/commands/validate_restore_upload.py#L119)

**Launch/store-failure sites in the view layer**

- Backup launch failure -- the admin-visible field no longer echoes the raw `OSError`.
  [`views.py:445`](../../backup/views.py#L445)

- Restore-upload view's two `_mark_upload_failed` call sites, same treatment.
  [`views.py:1069`](../../backup/views.py#L1069)

- Restore-start view's `abort_start` call, same treatment.
  [`views.py:1299`](../../backup/views.py#L1299)

**Regression tests proving the leak is gone**

- Exact-match + explicit raw-text-absence check on the audit path (strongest assertion in the batch).
  [`test_restore_audit.py:430`](../../backup/tests/test_restore_audit.py#L430)

- New coverage for the two review-found media-warning sites.
  [`test_restore_apply.py:885`](../../backup/tests/test_restore_apply.py#L885)

- `assertIn(type name)` + `assertNotIn(raw text)` pairs across the backup command tests.
  [`test_management.py:100`](../../backup/tests/test_management.py#L100)
