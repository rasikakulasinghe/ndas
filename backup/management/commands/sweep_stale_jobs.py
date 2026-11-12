"""
Deferred-work ledger triage -- stale backup/restore job sweep.

`run_backup`/`run_restore` (this app's other management commands) are each
invoked as a detached subprocess that writes its own terminal state. If that
process dies (killed, OOM, server restart) before reaching it, the
`BackupJob` row is left `pending`/`running` forever: nothing else in the
codebase ever revisits it. That single gap blocks the Story 1.2 overlap lock
for the job's scope indefinitely, and for a `restore` job also leaves its
`RestoreUpload` stuck `applying` with no audit record of what happened.

This command recovers both: any `BackupJob` whose `updated_at` has not
advanced for `STALE_JOB_AFTER` while `pending`/`running` is marked `failed`
(freeing the lock); a stale `restore` job's upload is returned to
`confirmed` (the transaction never committed, so the data is unchanged -- it
can be retried or cancelled) and gets a best-effort `restore_audit` record,
mirroring `run_restore.Command._fail`. A second, defensive pass catches any
`RestoreUpload` left `applying` with the same staleness gate but no
`pending`/`running` job at all (e.g. its job row was since deleted) -- Epic
3's manual delete must never remove a `restore` job (see deferred-work.md),
but nothing enforces that yet, so the same grace period is applied here too
rather than reverting the instant the job row disappears.

`updated_at` is a safe heartbeat: both subprocesses save it on every
progress-percent change (see `run_backup.py`/`run_restore.py`), so a live
job keeps it fresh. `STALE_JOB_AFTER` happens to equal Story 2.1's own
`RestoreUpload` validating-staleness constant (`restore_preview.
STALE_VALIDATING_AFTER`) but is deliberately its own independent value, not
an alias -- the two thresholds solve unrelated problems and must be free to
diverge. Accepts the same known risk that constant already carries: a
genuinely slow final stage with no progress callback could be swept before
it finishes (the error message below says so explicitly, since this
command's own verdict can be wrong).

Each job is re-fetched under `select_for_update()` inside its own
transaction before being flipped, re-checking it is still stale right then
(mirrors `backup/job_lock.py`'s overlap-lock pattern) -- this is a no-op on
SQLite (this project's primary target), relying on SQLite's own
database-level write lock to serialize instead, same as job_lock.py; on
PostgreSQL it is a real row lock. Either way two overlapping sweep runs (a
slow tick overlapping the next) cannot both flip the same job and double
the notification/audit it produces.

Meant to be run periodically from cron (see DEPLOYMENT.md "Configure Cron
Jobs"), e.g.:

    */15 * * * * cd <app root> && <venv>/bin/python manage.py sweep_stale_jobs

Never invoked by application code or from a request -- an ops/cron concern,
like `clearsessions`.
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from backup import restore_apply, restore_audit, restore_validation
from backup.models import BackupJob, RestoreUpload
from backup.notifications import notify_job_finished
from ndas.custom_codes.choice import BackupJobStatus, BackupJobType, RestoreUploadStatus

logger = logging.getLogger(__name__)
security_logger = restore_validation.security_logger

STALE_JOB_AFTER = timedelta(minutes=30)
ACTIVE_STATUSES = (BackupJobStatus.PENDING, BackupJobStatus.RUNNING)


class Command(BaseCommand):
    help = (
        "Fail BackupJob rows stuck pending/running with no progress for over "
        "30 minutes (their subprocess died); return any stuck restore's "
        "upload to 'confirmed'. Run periodically from cron, never from "
        "application code."
    )

    def _claim_and_fail(self, job_id, cutoff, message):
        """Re-fetch and lock `job_id`, re-check it is still pending/running
        and stale right now, and flip it to failed -- all inside ONE
        transaction, so the lock is held across the check AND the write.
        (Splitting the SELECT and the save into separate transactions would
        release the lock in between, letting two concurrent sweeps both pass
        the check before either commits its flip.) Returns the saved job, or
        None if a concurrent sweep already handled it or it is no longer
        stale."""
        with transaction.atomic():
            job = (
                BackupJob.objects.select_for_update()
                .select_related('restore_upload')
                .filter(pk=job_id, status__in=ACTIVE_STATUSES, updated_at__lt=cutoff)
                .first()
            )
            if job is None:
                return None

            job.status = BackupJobStatus.FAILED
            job.error_message = message
            job.progress_pct = 0
            update_fields = ['status', 'error_message', 'progress_pct', 'updated_at']

            if job.job_type == BackupJobType.RESTORE:
                date_scoped = job.restore_upload is not None and restore_apply.is_date_scoped(
                    job.restore_upload.confirmed_snapshot
                )
                audit = restore_audit.record_and_log(
                    job, outcome=restore_audit.OUTCOME_FAILED, error=message,
                    date_scoped=date_scoped, started_at=job.created_at,
                )
                if audit is not None:
                    update_fields.append('restore_audit')

            try:
                job.save(update_fields=update_fields)
            except Exception:
                logger.exception("BackupJob %s: stale-job sweep could not save the failure.", job.id)
                return None
            return job

    def handle(self, *args, **options):
        minutes = int(STALE_JOB_AFTER.total_seconds() // 60)
        cutoff = timezone.now() - STALE_JOB_AFTER
        message = (
            f"This job stalled (no progress for over {minutes} minutes) and was "
            "marked failed by the stale-job sweep. Its process most likely died "
            "(killed, OOM, server restart) -- or, rarely, it is still running a "
            "genuinely slow final stage with no progress update; if so, it can "
            "be safely re-run."
        )

        candidate_ids = list(
            BackupJob.objects.filter(status__in=ACTIVE_STATUSES, updated_at__lt=cutoff)
            .values_list('id', flat=True)
        )
        handled_count = 0
        for job_id in candidate_ids:
            job = self._claim_and_fail(job_id, cutoff, message)
            if job is None:
                continue  # no longer stale, already claimed by a concurrent sweep, or save failed

            if job.job_type == BackupJobType.RESTORE and job.restore_upload is not None:
                restore_apply.revert_upload_to_confirmed(job.restore_upload)

            notify_job_finished(job)
            security_logger.warning(
                "Stale-job sweep: BackupJob %s (type=%s, scope_type=%s) marked failed "
                "after %s minutes with no progress.",
                job.id, job.job_type, job.scope_type, minutes,
            )
            self.stdout.write(self.style.WARNING(f"BackupJob {job.id}: marked failed (stale)."))
            handled_count += 1

        # Defensive second pass: an `applying` upload with no pending/running
        # job at all (e.g. its job row was deleted) is just as stuck, but the
        # loop above never reaches it. The same staleness gate on the upload's
        # own `updated_at` avoids reverting one whose job row vanished only
        # moments ago, while its subprocess may still be finishing the apply.
        orphaned_uploads = list(
            RestoreUpload.objects.filter(status=RestoreUploadStatus.APPLYING, updated_at__lt=cutoff)
            .exclude(restore_jobs__status__in=ACTIVE_STATUSES)
        )
        for upload in orphaned_uploads:
            restore_apply.revert_upload_to_confirmed(upload)
            self.stdout.write(
                self.style.WARNING(f"RestoreUpload {upload.id}: reverted to 'confirmed' (no active job).")
            )

        if not handled_count and not orphaned_uploads:
            self.stdout.write("No stale jobs found.")
