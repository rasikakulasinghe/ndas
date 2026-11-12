---
title: 'Deferred-Work Batch 4: Backup App Quick Fixes'
type: 'bugfix'
created: '2026-11-12'
status: 'done'
baseline_commit: '406dc2788ea1f7c9766a58c1bffe626b7405ab8e'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nine small, verified-open `deferred-work.md` entries in the backup app: inconsistent/unguarded failure paths in `run_backup`/`run_restore`, `backup_delete` logging under the restore logger, over-broad `except Exception` in the two refusal-log helpers, a history page that hides failure reasons and has no sidebar entry, a delete modal missing archive size and the snapshot rollback warning, no N+1 guard test on the history page, and a timing-flaky rate-limit test.

**Approach:** Fix each in place with the smallest change that matches the existing patterns in the same file, add a regression test per behavior change, and annotate each ledger entry as resolved.

## Boundaries & Constraints

**Always:** Match the surrounding file's existing patterns (decorator stacks, log message style, Bootstrap 4.6/AdminLTE 3.2 classes). Keep the AD-7 plain-404 behavior for unknown/out-of-scope pks. Keep the `django.security` logger family so lines still reach `security_file`. Run tests with the venv Python, one run at a time, with `SECURE_SSL_REDIRECT=False` overridden for the run.

**Ask First:** Any change to the decorator order on `backup_delete` / `patient_delete`; any change to who may see or delete a job.

**Never:** No new models, fields or migrations. No change to `sweep_stale_jobs`. No re-checksumming of archives. No touching `.env`. Don't change `_recent_jobs_for` or `status.html`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Restore fails | `run_restore._fail` called on a job at 63% | job `failed`, `progress_pct=0` | existing `_save_terminal` |
| Export fails, failure save also fails | `create_export` raises, then `job.save` raises | logged via `logger.exception`, no notification, command returns without raising | swallowed + logged |
| Export interrupted | `KeyboardInterrupt`/`SystemExit` during `create_export` | partial zip removed, job saved `failed` (best effort), then the exception is re-raised | save guarded |
| Refusal-log existence check hits a DB error | `exists()` raises `DatabaseError` | logged `exists=unknown`, client still gets 404 | only `DatabaseError` caught |
| Failed job on history page | `status=failed`, `error_message` set | message shown under the status badge | N/A |
| Completed-with-warnings job | `completed` + `error_message` | warnings text shown | N/A |

</frozen-after-approval>

## Code Map

- `backup/management/commands/run_restore.py:56` -- `_fail`; add `job.progress_pct = 0` and `'progress_pct'` to `update_fields` (mirrors `run_backup.py:77`).
- `backup/management/commands/run_backup.py:66-82` -- failed-export branch; its `job.save` + `notify_job_finished` are unguarded. Copy the guarded pattern from the start-failure branch at lines 42-53 (save in try, notify in `else`).
- `backup/views.py:571-595` `_log_backup_download_refused`, `:716-729` `_log_backup_delete_refused` -- narrow `except Exception` to `except DatabaseError` (`django.db`).
- `backup/views.py:733-900` `backup_delete` -- every `security_logger.*` call → `download_security_logger` (the `django.security.backup` logger, defined near the top of the file). Consider renaming it to `backup_security_logger`, since it now covers both download and delete; update its comment and `backup/tests/test_download_views.py`'s `SECURITY_LOGGER` constant to match.
- `backup/templates/backup/manager.html:57-66` -- Status cell; render `job.error_message` (small, `text-danger` for failed, `text-dark` for warnings) under the badge, like `status.html:60-61`.
- `templates/src/main_sidebar_menu.html:262-272` -- Backup nav item; add a sibling "Backup History" item (`backup:backup-history`, `fas fa-history`, same visibility gate, `active` on `backup-history`).
- `ndas/custom_codes/delete_helpers.py:254-261` warnings, `:323-347` details (BackupJob branches) -- add `details['Size']` from `getattr(entity, 'archive_size_bytes', None)` via `filesizeformat` (`'unavailable'` if None and completed; omit otherwise); for `pre_restore_snapshot` append warning "Deleting this snapshot permanently removes the ability to roll back to the pre-restore state". `backup_history` already sets `archive_size_bytes` on each row (`backup/views.py:534-543`).
- `backup/tests/test_history_views.py` -- add a query-count test: history page with 2 vs 10 jobs (single + multi scope, mixed users) issues the same number of queries.
- `backup/tests/test_delete_views.py:428-447` `BackupDeleteRateLimitTest` -- patch `django_ratelimit.core._get_window` to a fixed future timestamp so all 6 requests land in one window.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- annotate the 9 entries (summaries starting: "`run_backup.py`'s failure path resets", "`backup/management/commands/run_backup.py`'s failed-export path", "`backup_delete`'s log lines", "The new `_log_backup_delete_refused`", "The history page shows only a status badge", "The only path to `backup:backup-history`", "No query-count regression test", "The delete-confirmation modal for a BackupJob", "`backup/tests/test_delete_views.py::BackupDeleteRateLimitTest`") with `RESOLVED by:` lines.

## Tasks & Acceptance

**Execution:**
- [x] `backup/management/commands/run_restore.py` -- reset `progress_pct` in `_fail` -- consistent failed-bar rendering.
- [x] `backup/management/commands/run_backup.py` -- guard the failed-export save; handle `KeyboardInterrupt`/`SystemExit` (clean partial zip, best-effort failed save, re-raise) -- no job left `running` by a recordable failure.
- [x] `backup/views.py` -- move delete logging to the `django.security.backup` logger; narrow both refusal helpers to `DatabaseError`.
- [x] `backup/templates/backup/manager.html` -- show `error_message`.
- [x] `templates/src/main_sidebar_menu.html` -- add Backup History nav item.
- [x] `ndas/custom_codes/delete_helpers.py` -- Size detail + snapshot rollback warning.
- [x] Tests: `backup/tests/test_management.py` (run_backup rows) and `backup/tests/test_restore_command.py` (`_fail` progress reset) for the matrix rows; `test_history_views.py` (error text + query count); `test_delete_views.py` (logger name, rate-limit determinism); `ndas/tests/test_delete_helpers.py` (Size + warning).
- [x] `deferred-work.md` -- annotate the 9 entries.

**Acceptance Criteria:**
- Given an ADMIN on any page, when the sidebar renders, then a "Backup History" link to `/backup/history/` is visible exactly where "Backup" is.
- Given a successful or refused backup delete, when it is logged, then the record's logger is `django.security.backup`, not `django.security.restore`.
- Given `BackupDeleteRateLimitTest` run 10 times in a row, then it passes every time.

## Design Notes

L406 asked to "re-raise or 500 on a genuine lookup failure". Narrowing to `DatabaseError` is the chosen reading: the primary `get_object_or_404` already ran successfully and decided 404, so a DB error inside the follow-up audit `exists()` is transient and shouldn't turn a 404 into a 500. Programming errors (anything other than `DatabaseError`) now surface instead of being hidden as `exists=unknown`.

## Verification

**Commands:**
- `venv/Scripts/python.exe manage.py test backup ndas.tests.test_delete_helpers` (with `SECURE_SSL_REDIRECT=False`) -- expected: all pass.

## Suggested Review Order

**Failure paths in the background commands**

- Guarded failed-save helper; a failed save leaves recovery to `sweep_stale_jobs`.
  [`run_backup.py:30`](../../backup/management/commands/run_backup.py#L30)

- Partial-zip cleanup is guarded so it can't skip recording the failure.
  [`run_backup.py:89`](../../backup/management/commands/run_backup.py#L89)

- Interrupts clean up, record failed best-effort, then re-raise.
  [`run_backup.py:97`](../../backup/management/commands/run_backup.py#L97)

- Failed restore now resets the bar to 0%, like a failed backup.
  [`run_restore.py:65`](../../backup/management/commands/run_restore.py#L65)

**Security logging**

- One `django.security.backup` logger now covers download and delete.
  [`views.py:64`](../../backup/views.py#L64)

- Refusal audit swallows only `DatabaseError`; other errors surface.
  [`views.py:717`](../../backup/views.py#L717)

**History page and delete dialog**

- Failure/warning text under the status badge, truncated to 300 chars.
  [`manager.html:69`](../../backup/templates/backup/manager.html#L69)

- Size line only when the page measured it; rollback warning only for completed snapshots.
  [`delete_helpers.py:357`](../../ndas/custom_codes/delete_helpers.py#L357)

- New sidebar entry under the same role gate as Backup.
  [`main_sidebar_menu.html:280`](../../templates/src/main_sidebar_menu.html#L280)

**Tests**

- Same query count for 2 and 10 rows guards against N+1 regressions.
  [`test_history_views.py:414`](../../backup/tests/test_history_views.py#L414)

- Frozen ratelimit window makes the 6th-delete test deterministic.
  [`test_delete_views.py:476`](../../backup/tests/test_delete_views.py#L476)

- Delete-dialog Size line and snapshot warning cases.
  [`test_delete_helpers.py:108`](../../ndas/tests/test_delete_helpers.py#L108)

- Restore failure at 63% ends at 0%.
  [`test_restore_command.py:438`](../../backup/tests/test_restore_command.py#L438)
