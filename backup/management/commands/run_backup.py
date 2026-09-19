"""
Story 1.1 — run_backup management command.

Invoked exclusively by `backup/views.py` as a detached OS subprocess:

    manage.py run_backup <job_id>

Drives a `BackupJob` through running -> completed|failed and calls
`backup.services.create_export` to do the actual work. No other app or view
should call this command or `backup.services` directly.
"""
import logging

from django.core.management.base import BaseCommand, CommandError

from backup.models import BackupJob
from backup.services import create_export, get_archive_path
from ndas.custom_codes.choice import BackupJobStatus

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run a queued BackupJob: streams the institution-scoped export to a zip archive."

    def add_arguments(self, parser):
        parser.add_argument('job_id', type=int, help='Primary key of the BackupJob to run.')

    def handle(self, *args, **options):
        job_id = options['job_id']

        try:
            job = BackupJob.objects.get(pk=job_id)
        except BackupJob.DoesNotExist:
            raise CommandError(f"BackupJob {job_id} does not exist.")

        try:
            job.status = BackupJobStatus.RUNNING
            job.progress_pct = 0
            job.save(update_fields=['status', 'progress_pct', 'updated_at'])
        except Exception as e:
            # A failure here (e.g. a transient DB hiccup) must not leave the
            # job stuck at 'pending' forever with no explanation.
            logger.exception("BackupJob %s: failed to transition to running.", job.id)
            try:
                job.status = BackupJobStatus.FAILED
                job.error_message = f"Failed to start backup job: {e}"
                job.save(update_fields=['status', 'error_message', 'updated_at'])
            except Exception:
                logger.exception("BackupJob %s: also failed to record the failure.", job.id)
            self.stdout.write(self.style.ERROR(f"BackupJob {job.id}: failed to start - {e}"))
            return

        self.stdout.write(f"BackupJob {job.id}: running (scope_id={job.scope_id})")

        def _on_progress(pct):
            try:
                job.progress_pct = min(max(pct, 0), 99)
                job.save(update_fields=['progress_pct', 'updated_at'])
            except Exception:
                logger.exception("BackupJob %s: failed to persist progress update.", job.id)

        try:
            archive_path, skipped_media, archive_checksum = create_export(job, progress_callback=_on_progress)
        except Exception as e:
            logger.exception("BackupJob %s failed during export.", job.id)
            # Remove only the partial .zip, never the whole archive_dir --
            # that directory also holds this very process's run_backup.log
            # (still open via redirected stdout/stderr), which Windows
            # cannot delete while the handle is open.
            get_archive_path(job).unlink(missing_ok=True)
            job.status = BackupJobStatus.FAILED
            job.progress_pct = 0
            job.error_message = f"Backup export failed: {e}"
            job.save(update_fields=['status', 'progress_pct', 'error_message', 'updated_at'])
            self.stdout.write(self.style.ERROR(f"BackupJob {job.id}: failed - {e}"))
            return

        # Terminal success state written as one save (status + progress_pct together).
        # A non-empty skipped_media list still completes the job (human-approved
        # policy) but the admin must see exactly what was skipped.
        job.status = BackupJobStatus.COMPLETED
        job.progress_pct = 100
        job.archive_checksum = archive_checksum
        job.error_message = (
            "Completed with {} media file(s) skipped: {}".format(
                len(skipped_media), "; ".join(skipped_media)
            )
            if skipped_media else ""
        )
        job.save(update_fields=['status', 'progress_pct', 'archive_checksum', 'error_message', 'updated_at'])
        if skipped_media:
            self.stdout.write(self.style.WARNING(
                f"BackupJob {job.id}: completed with {len(skipped_media)} media file(s) skipped -> {archive_path}"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f"BackupJob {job.id}: completed -> {archive_path}"))
