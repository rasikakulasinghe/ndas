---
title: 'Deferred-Work Batch 5b: Backup Download Integrity, Log Throttle & Doc Fix'
type: 'bugfix'
created: '2026-11-12'
status: 'done'
baseline_commit: '086838cbfe1814a557a8edec8bb238534820c7b4'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Three small, verified-still-open `deferred-work.md` entries in the backup app. (1) `_backup_download_body` streams a `completed` archive after only an `os.fstat` check; `BackupJob.archive_checksum` (already computed at export time) is never re-verified, so a corrupted archive downloads as if healthy. (2) `restore_audit.log_unknown_upload` logs one warning per request with no throttle, so every HTMX poll of `restore_status_fragment` (and 5 sibling views) for a foreign/unknown upload id floods `security.log`. (3) CLAUDE.md's "24 CRUD operations protected" figure is stale — the verified current count is 100 `@ratelimit` decorator lines across 8 apps.

**Approach:** Hash the archive against `archive_checksum` before streaming, refusing cleanly on mismatch; add a short-TTL cache dedup to `log_unknown_upload`; correct the CLAUDE.md count. Annotate the three ledger entries as resolved.

## Boundaries & Constraints

**Always:** Skip the checksum comparison entirely when `job.archive_checksum` is blank (legacy/partial rows) -- stream unchanged in that case. The throttle is logging-only: the 404 response itself must still happen on every request, deduped or not. Match `reports/views.py`'s existing `cache.get`/`cache.set` key-naming style (`f"prefix_{id}_{extra}"`) for the new cache key.

**Ask First:** None -- both code changes are additive refusal/dedup paths that don't alter any existing success path.

**Never:** No new models, fields or migrations. No change to `_backup_download_body`'s existing `open()`/`os.fstat()` missing-archive handling. No change to which of the six `_own_upload_or_404` call sites can trigger the warning -- the dedup lives inside `log_unknown_upload` itself, not at each call site.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Downloaded archive bytes don't match `archive_checksum` | admin requests a completed job's download | download refused, redirected to history with a user-facing message; no bytes streamed | `backup_security_logger.warning`, no `FileResponse` built |
| Archive row has no stored checksum (legacy) | `job.archive_checksum == ''` | checksum step skipped entirely, download streams as today | N/A |
| Archive re-read raises `OSError` mid-hash (file vanished after the initial `fstat`) | rare race between open and hash | handle closed, same "no longer available" refusal path as the existing missing-archive case | no partial stream |
| Same unknown/foreign upload id polled repeatedly within 60s | HTMX hits `restore_status_fragment` every few seconds | one `security_logger.warning` line per 60s window per user+upload, not one per request | still 404 every time |

</frozen-after-approval>

## Code Map

- `backup/views.py:657-671` `_backup_download_body` -- after the existing `open()`/`os.fstat()` check, when `job.archive_checksum` is non-blank: stream-hash the already-open `archive_file` in `COPY_CHUNK_SIZE` chunks (same pattern as `backup/services.py:513-517`; needs `import hashlib` and `COPY_CHUNK_SIZE` added to the existing `from backup.services import ...` line), `seek(0)` after hashing, compare hex digest to `job.archive_checksum`. On mismatch, or an `OSError` while re-reading: close the handle, `backup_security_logger.warning(...)`, `messages.error(request, "This backup's archive file appears to be corrupted and cannot be downloaded.")`, redirect to `backup:backup-history` -- never construct the `FileResponse`.
- `backup/restore_audit.py:228-240` `log_unknown_upload` -- add `from django.core.cache import cache`; guard the existing body behind `if not cache.add(f"restore-unknown-upload-log:{getattr(request.user, 'pk', None)}:{pk}", True, timeout=60): return`.
- `CLAUDE.md:140` -- replace `"24 CRUD operations protected (10/min create/edit, 5/min delete)"` with the verified current figure (100 `@ratelimit` decorator lines across patients/backup/reports/users/video/referral/problemlist/institution).
- `backup/tests/test_download_views.py` -- add a checksum-mismatch case (download refused, no stream) and a blank-checksum pass-through case for `_backup_download_body`.
- A restore-audit or view test (e.g. `backup/tests/test_restore_views.py`) -- add a case asserting a second poll of the same unknown/foreign upload id within the throttle window produces no second `security.log` line.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- annotate: the entry starting "`_backup_download_body` streams a `completed` archive with no integrity/checksum check" and the entry starting "CLAUDE.md's Security Architecture section states" (both source_spec `spec-3-2-download-a-completed-backup.md`) with `RESOLVED by:` lines; append a second resolution line to the entry starting "A restore job killed mid-run gets no audit" for its still-open "per-poll throttling" half, leaving the existing `PARTIALLY RESOLVED by:` line untouched.

## Tasks & Acceptance

**Execution:**
- [x] `backup/views.py` -- add checksum verification to `_backup_download_body`.
- [x] `backup/restore_audit.py` -- add the cache-based dedup to `log_unknown_upload`.
- [x] `CLAUDE.md` -- correct the rate-limiting count.
- [x] Add the two new download-integrity test cases and the dedup test case.
- [x] `deferred-work.md` -- annotate the three entries (two full, one partial-closing) as resolved.
- [x] Review hardening (blind-hunter + edge-case-hunter + verification-gap, all independently confirmed): guard `log_unknown_upload`'s `cache.add()` against a cache-backend exception (was previously unguarded, unlike the DB-existence check beside it); reword CLAUDE.md's rate-limiting bullet (the old phrasing's trailing "(10/min create/edit, 5/min delete)" no longer described all 100 lines) and bump its "Last Updated" date; add a CLAUDE.md bullet naming the new download-integrity control; add the missing success-path test (`test_matching_archive_checksum_streams_the_full_correct_bytes` -- the one case that would catch a `seek(0)` regression and that no existing test reached); add `test_oserror_during_hash_closes_handle_and_refuses_as_missing`; strengthen the mismatch test to a same-length bit-flip; add `cache.clear()` to `UnknownUploadLoggingTest.setUp` against cross-test throttle-key leakage (LocMemCache is process-global).

**Acceptance Criteria:**
- Given a `completed` `BackupJob` whose archive on disk no longer matches `archive_checksum`, when an admin requests `backup:backup-download`, then no file bytes are streamed and the admin is redirected to the history page with an error message.
- Given a `completed` `BackupJob` created before `archive_checksum` existed (blank), when downloaded, then it streams exactly as it does today.
- Given two requests for the same unknown/foreign upload id from the same user within 60 seconds, when both hit any of the six `_own_upload_or_404` call sites, then `security.log` gets at most one matching warning line.

## Design Notes

The checksum check deliberately re-reads the whole archive once per download (accepted cost, not fixed here): `backup_download` is a low-frequency, admin-only action, and silently serving a corrupted institutional backup is worse than the added latency.

The throttle key intentionally ignores `view_name`: a user hammering any mix of the six `_own_upload_or_404`-guarded views with the same bad `pk` should still only log once per window, not once per view.

## Verification

**Commands:**
- `venv/Scripts/python.exe manage.py test backup` (with `SECURE_SSL_REDIRECT=False` for the run) -- expected: all pass, including the three new cases.

## Suggested Review Order

**Download integrity check**

- The checksum re-verification itself: hash, `seek(0)`, compare, refuse on mismatch or read failure.
  [`views.py:679`](../../backup/views.py#L679)

- The success path a regression here would silently break (no existing test reached it).
  [`test_download_views.py:231`](../../backup/tests/test_download_views.py#L231)

- Corrupted archive refused -- strengthened to a same-length bit-flip so only the hash comparison can catch it.
  [`test_download_views.py:354`](../../backup/tests/test_download_views.py#L354)

- Mid-hash read failure reuses the existing missing-archive refusal path, per the frozen I/O matrix.
  [`test_download_views.py:379`](../../backup/tests/test_download_views.py#L379)

**Log throttle**

- The dedup guard itself, now exception-safe after review (a cache-backend failure must not turn a 404 into a 500).
  [`restore_audit.py:239`](../../backup/restore_audit.py#L239)

- Second poll within the window logs nothing; the 404 itself is unaffected.
  [`test_restore_audit.py:672`](../../backup/tests/test_restore_audit.py#L672)

- `cache.clear()` added here against cross-test leakage, since LocMemCache is process-global.
  [`test_restore_audit.py:558`](../../backup/tests/test_restore_audit.py#L558)

**Documentation**

- Corrected count, reworded to not misdescribe every rate, plus the new integrity-check bullet.
  [`CLAUDE.md:140`](../../CLAUDE.md#L140)
