"""
Story 1.5 -- in-app notification when a BackupJob reaches a terminal state.

Called from `backup/management/commands/run_backup.py` and (Story 2.3)
`run_restore.py`, after the terminal `BackupJob` save. Creates a
`referral.Notification` (the record the navbar bell lists) for the user who
triggered the job. A restore's notification links to its upload's status page;
the pre-restore snapshot job a restore takes never notifies (its restore does).

Strictly best-effort: `notify_job_finished` never raises, so a notification
problem can never change the job's terminal state or make the command fail.
"""
import logging

from django.urls import reverse

from ndas.custom_codes.choice import BackupJobStatus, BackupJobType, NotificationType

logger = logging.getLogger(__name__)

# Notification.body is a TextField, but the bell panel truncates it at 80
# characters anyway -- keep the stored summary short.
_BODY_SUMMARY_MAX = 200


def _summarize(text, limit=_BODY_SUMMARY_MAX):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _build_restore_content(job):
    """Return (notification_type, title, body) for a terminal restore `job`."""
    if job.status == BackupJobStatus.COMPLETED:
        if job.error_message:
            return (
                NotificationType.RESTORE_COMPLETED,
                "Restore completed with warnings",
                _summarize(job.error_message),
            )
        return (
            NotificationType.RESTORE_COMPLETED,
            "Restore completed",
            "The archive was restored successfully.",
        )
    return (
        NotificationType.RESTORE_FAILED,
        "Restore failed",
        _summarize(job.error_message) or "The restore job failed.",
    )


def _build_content(job):
    """Return (notification_type, title, body) for a terminal `job`."""
    if job.job_type == BackupJobType.RESTORE:
        return _build_restore_content(job)
    if job.status == BackupJobStatus.COMPLETED:
        if job.error_message:
            return (
                NotificationType.BACKUP_COMPLETED,
                "Backup completed with warnings",
                _summarize(job.error_message),
            )
        return (
            NotificationType.BACKUP_COMPLETED,
            "Backup completed",
            "Your backup finished successfully and is ready.",
        )
    return (
        NotificationType.BACKUP_FAILED,
        "Backup failed",
        _summarize(job.error_message) or "The backup job failed.",
    )


def _link_for(job):
    """Where the notification points: a restore's upload status page (its
    outcome and progress live there), the backup page for everything else."""
    if job.job_type == BackupJobType.RESTORE and job.restore_upload_id:
        return reverse('backup:restore-status', args=[job.restore_upload_id])
    if job.job_type == BackupJobType.RESTORE:
        return reverse('backup:restore-upload')
    return reverse('backup:backup-create')


def notify_job_finished(job):
    """
    Notify `job.triggered_by` that `job` finished (completed or failed).
    A `pre_restore_snapshot` job never notifies.

    Delivery institution is `job.trigger_institution`, falling back to
    `job.scope` for jobs that predate that field. Skipped (log line only)
    when there is no recipient or no resolvable institution. Any exception
    is logged and swallowed.
    """
    try:
        if job.job_type == BackupJobType.PRE_RESTORE_SNAPSHOT:
            return

        recipient = job.triggered_by
        if recipient is None:
            logger.info("BackupJob %s: no triggering user; skipping notification.", job.id)
            return

        institution = job.trigger_institution or job.scope
        if institution is None:
            logger.info("BackupJob %s: no delivery institution; skipping notification.", job.id)
            return

        from referral.models import Notification

        notification_type, title, body = _build_content(job)
        Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            body=body,
            link=_link_for(job),
            institution=institution,
            added_by=recipient,
            last_edit_by=recipient,
        )
        logger.info(
            "%s notification -> %s (BackupJob %s)", notification_type, recipient.username, job.id,
        )
    except Exception:
        logger.exception("BackupJob %s: failed to create completion notification.", getattr(job, 'id', None))
