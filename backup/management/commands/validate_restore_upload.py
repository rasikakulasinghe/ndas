"""
Story 2.1 -- validate_restore_upload management command.

Invoked exclusively by `backup/views.py` as a detached OS subprocess:

    manage.py validate_restore_upload <upload_id>

Drives a `RestoreUpload` from `validating` to `validated | rejected | failed`
by running `backup.restore_validation.validate_restore_archive` against the
staged archive. It is the only writer of the row's status after launch, and
it writes each terminal state (status, progress, result fields) in a single
save. On any outcome other than `validated` the staged archive is deleted;
a failure to delete it (e.g. an antivirus lock) is logged but never changes
the outcome. If the terminal save itself fails, one best-effort fallback save
marks the row `failed` so it is never left stuck at `validating`.
Nothing is applied to any domain data.
"""
import logging

from django.core.management.base import BaseCommand, CommandError

from backup.models import RestoreUpload
from backup.restore_validation import (
    RestoreRejection,
    _clip,
    delete_staged_archive,
    get_upload_path,
    security_logger,
    validate_restore_archive,
)
from ndas.custom_codes.choice import RestoreAuthenticity, RestoreUploadStatus

logger = logging.getLogger(__name__)


def _safe_delete_staged_archive(upload):
    try:
        delete_staged_archive(upload)
    except OSError:
        logger.exception("RestoreUpload %s: could not delete the staged archive.", upload.id)


def _save_terminal(upload, update_fields):
    """One terminal save; if it fails, a best-effort fallback save to `failed`."""
    try:
        upload.save(update_fields=update_fields)
        return
    except Exception as e:
        logger.exception("RestoreUpload %s: failed to record its terminal state.", upload.id)
        failure = e
    _safe_delete_staged_archive(upload)
    try:
        upload.status = RestoreUploadStatus.FAILED
        upload.progress_pct = 0
        upload.error_message = f"Validation finished but its result could not be recorded: {_clip(failure, 200)}"
        upload.save(update_fields=['status', 'progress_pct', 'error_message', 'updated_at'])
    except Exception:
        logger.exception("RestoreUpload %s: fallback save to 'failed' also failed.", upload.id)


class Command(BaseCommand):
    help = "Validate a staged restore archive upload (zip safety, manifest, schema, origin, checksums)."

    def add_arguments(self, parser):
        parser.add_argument('upload_id', type=int, help='Primary key of the RestoreUpload to validate.')

    def handle(self, *args, **options):
        upload_id = options['upload_id']

        try:
            upload = RestoreUpload.objects.get(pk=upload_id)
        except RestoreUpload.DoesNotExist:
            raise CommandError(f"RestoreUpload {upload_id} does not exist.")

        if upload.status != RestoreUploadStatus.VALIDATING:
            self.stdout.write(self.style.WARNING(
                f"RestoreUpload {upload.id}: status is '{upload.status}', not 'validating' - nothing to do."
            ))
            return

        self.stdout.write(f"RestoreUpload {upload.id}: validating {_clip(upload.original_filename)!r}")

        def _on_progress(pct):
            try:
                upload.progress_pct = min(max(pct, 0), 99)
                upload.save(update_fields=['progress_pct', 'updated_at'])
            except Exception:
                logger.exception("RestoreUpload %s: failed to persist progress update.", upload.id)

        try:
            result = validate_restore_archive(
                get_upload_path(upload),
                upload.archive_sha256,
                allow_unverified=upload.allow_unverified,
                progress_callback=_on_progress,
            )
        except RestoreRejection as rejection:
            security_logger.warning(
                "Restore archive rejected: upload=%s user=%s code=%s message=%s",
                upload.id, upload.uploaded_by_id, rejection.code, rejection.message,
            )
            _safe_delete_staged_archive(upload)
            upload.status = RestoreUploadStatus.REJECTED
            upload.progress_pct = 0
            upload.error_code = rejection.code
            upload.error_message = rejection.message
            _save_terminal(upload, ['status', 'progress_pct', 'error_code', 'error_message', 'updated_at'])
            self.stdout.write(self.style.ERROR(
                f"RestoreUpload {upload.id}: rejected ({rejection.code}) - {rejection.message}"
            ))
            return
        except Exception as e:
            logger.exception("RestoreUpload %s failed during validation.", upload.id)
            _safe_delete_staged_archive(upload)
            upload.status = RestoreUploadStatus.FAILED
            upload.progress_pct = 0
            upload.error_message = f"Validation failed unexpectedly: {_clip(e, 200)}"
            _save_terminal(upload, ['status', 'progress_pct', 'error_message', 'updated_at'])
            self.stdout.write(self.style.ERROR(f"RestoreUpload {upload.id}: failed - {e}"))
            return

        if result.authenticity == RestoreAuthenticity.UNVERIFIED:
            security_logger.warning(
                "Unverified-origin restore archive accepted: upload=%s user=%s filename=%s size=%s",
                upload.id, getattr(upload.uploaded_by, 'username', None), _clip(upload.original_filename),
                upload.size_bytes,
            )

        upload.status = RestoreUploadStatus.VALIDATED
        upload.progress_pct = 100
        upload.authenticity = result.authenticity
        upload.source_job_id = result.summary['source_job_id']
        upload.manifest_summary = result.summary
        upload.match_summary = result.match_summary
        _save_terminal(upload, [
            'status', 'progress_pct', 'authenticity', 'source_job_id', 'manifest_summary', 'match_summary',
            'updated_at',
        ])
        self.stdout.write(self.style.SUCCESS(
            f"RestoreUpload {upload.id}: validated (authenticity={result.authenticity})"
        ))
