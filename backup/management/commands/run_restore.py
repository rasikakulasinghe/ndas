"""
Story 2.3 -- run_restore management command.

Invoked exclusively by `backup/views.py` as a detached OS subprocess:

    manage.py run_restore <job_id>

Drives a `restore` `BackupJob` through running -> completed|failed by calling
`backup.restore_apply.execute_restore` (re-verify the staged archive, take the
pre-restore snapshot, preflight, apply in one transaction, restore media). It
is the only writer of the job's status after launch and writes its terminal
state (status + progress) in a single save, then notifies. The job's upload
becomes `applied` on completion; on any failure it returns to `confirmed`
(the transaction made the data unchanged) so the restore can be retried or
cancelled.
"""
import logging

from django.core.management.base import BaseCommand, CommandError

from backup import restore_apply
from backup.models import BackupJob
from backup.notifications import notify_job_finished
from backup.restore_validation import _clip
from ndas.custom_codes.choice import BackupJobStatus, BackupJobType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run a queued restore job: snapshot the current data, then apply the confirmed archive."

    def add_arguments(self, parser):
        parser.add_argument('job_id', type=int, help='Primary key of the restore BackupJob to run.')

    def _fail(self, job, message):
        """Terminal failure: one save, the upload back to `confirmed`, then notify."""
        snapshot_note = (
            f" The pre-restore snapshot is job {job.pre_restore_snapshot_id}."
            if job.pre_restore_snapshot_id else ""
        )
        job.status = BackupJobStatus.FAILED
        job.error_message = f"Restore failed: {message}{snapshot_note}"
        try:
            job.save(update_fields=['status', 'error_message', 'updated_at'])
        except Exception:
            logger.exception("BackupJob %s: failed to record its failure.", job.id)
        upload = job.restore_upload
        if upload is not None:
            restore_apply.revert_upload_to_confirmed(upload)
        notify_job_finished(job)
        self.stdout.write(self.style.ERROR(f"BackupJob {job.id}: failed - {message}"))

    def handle(self, *args, **options):
        job_id = options['job_id']

        try:
            job = BackupJob.objects.select_related('restore_upload').get(pk=job_id, job_type=BackupJobType.RESTORE)
        except BackupJob.DoesNotExist:
            raise CommandError(f"Restore job {job_id} does not exist.")

        if job.status != BackupJobStatus.PENDING:
            self.stdout.write(self.style.WARNING(
                f"BackupJob {job.id}: status is '{job.status}', not 'pending' - nothing to do."
            ))
            return

        try:
            job.status = BackupJobStatus.RUNNING
            job.progress_pct = 0
            job.save(update_fields=['status', 'progress_pct', 'updated_at'])
        except Exception as e:
            # A failure here must not leave the job stuck at 'pending' (and the
            # upload stuck at 'applying') with no explanation.
            logger.exception("BackupJob %s: failed to transition to running.", job.id)
            self._fail(job, f"could not start the restore job ({_clip(e, 200)})")
            return

        self.stdout.write(f"BackupJob {job.id}: restoring upload {job.restore_upload_id} (scope={job.scope_type})")

        def _on_progress(pct):
            try:
                job.progress_pct = min(max(pct, 0), 99)
                job.save(update_fields=['progress_pct', 'updated_at'])
            except Exception:
                logger.exception("BackupJob %s: failed to persist progress update.", job.id)

        try:
            result = restore_apply.execute_restore(job, progress_callback=_on_progress)
        except (restore_apply.RestoreError, restore_apply.ExportFormatError) as e:
            logger.warning("BackupJob %s: restore refused or failed: %s", job.id, e.message)
            self._fail(job, e.message)
            return
        except Exception as e:
            logger.exception("BackupJob %s failed during the restore.", job.id)
            self._fail(job, f"unexpected error ({_clip(e, 200)})")
            return

        # Terminal success state written as one save (status + progress_pct together).
        job.status = BackupJobStatus.COMPLETED
        job.progress_pct = 100
        job.error_message = restore_apply.format_media_warnings(result.warnings) if result.warnings else ""
        try:
            job.save(update_fields=['status', 'progress_pct', 'error_message', 'updated_at'])
        except Exception:
            logger.exception("BackupJob %s: restore committed but its terminal state could not be saved.", job.id)
        if job.restore_upload is not None:
            restore_apply.mark_applied(job.restore_upload)
        notify_job_finished(job)
        if result.warnings:
            self.stdout.write(self.style.WARNING(
                f"BackupJob {job.id}: restored with {len(result.warnings)} warning(s)"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f"BackupJob {job.id}: restore completed"))
