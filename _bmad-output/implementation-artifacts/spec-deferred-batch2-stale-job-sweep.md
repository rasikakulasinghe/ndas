---
title: 'Deferred-Work Batch 2: Stale Backup/Restore Job Sweep'
type: 'bugfix'
created: '2026-11-12'
status: 'done'
review_loop_iteration: 0
context: []
route: 'one-shot'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Five confirmed-still-open `deferred-work.md` entries, all tracing to one root cause: `run_backup`/`run_restore` each write their own terminal state from a detached subprocess, but if that process dies first (killed, OOM, server restart), the `BackupJob` row is left `pending`/`running` forever — blocking the Story 1.2 overlap lock for its scope — and a stale `restore` job's `RestoreUpload` is left stuck `applying` with no `restore_audit` of what happened.

**Approach:** A new `manage.py sweep_stale_jobs` command, meant to run periodically from cron (documented in DEPLOYMENT.md), that fails any job whose `updated_at` heartbeat has gone stale for 30 minutes, returns a stale restore's upload to `confirmed`, and writes a best-effort `restore_audit`. A `select_for_update()` double-check guards against two overlapping sweep ticks double-processing the same job; a defensive second pass (with its own staleness grace period) catches an orphaned `applying` upload whose job row no longer exists at all.

</frozen-after-approval>

## Suggested Review Order

1. [backup/management/commands/sweep_stale_jobs.py](../../backup/management/commands/sweep_stale_jobs.py) — the sweep command itself.
2. [backup/tests/test_sweep_stale_jobs.py](../../backup/tests/test_sweep_stale_jobs.py) — 16 regression tests (staleness, locking, idempotency, orphan grace period, notifications, audit).
3. [DEPLOYMENT.md](../../DEPLOYMENT.md) — cron entry (section 1.8) and its documentation (section 1.8.1).
4. [_bmad-output/implementation-artifacts/deferred-work.md](deferred-work.md) — 5 entries closed, 3 new defer entries appended.

