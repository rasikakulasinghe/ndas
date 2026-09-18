"""
Backup trigger view — Story 1.1.

The ONLY entry point into `backup/services.py`'s export logic: permission
check -> concurrency-lock check -> disk-space check -> create `BackupJob` ->
launch a detached subprocess running `manage.py run_backup <job_id>` ->
redirect immediately. The export itself never runs synchronously in this
request.
"""
import logging
import os
import subprocess
import sys

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from ndas.custom_codes.choice import UserType, BackupJobType, BackupJobStatus
from ndas.custom_codes.error_handlers import handle_view_errors
from backup.models import BackupJob
from backup.services import has_sufficient_disk_space

logger = logging.getLogger(__name__)


def _get_admin_institution(request):
    """Mirror institution/views.py's `_get_admin_institution` helper."""
    return getattr(request, 'institution', None) or getattr(request.user, 'institution', None)


@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='backup:backup-create', error_message='Failed to trigger backup.')
def backup_create(request):
    """
    Institutional admin (or super admin acting within an institution context):
    trigger a full-scope backup of their institution's data.

    GET  -> render the trigger form + recent job list.
    POST -> run the checks and launch the backup subprocess.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type not in (UserType.ADMIN, UserType.SUPERADMIN):
        messages.error(request, "You don't have permission to trigger a backup.")
        return redirect('home')

    institution = _get_admin_institution(request)
    if institution is None:
        messages.error(request, "No institution context found for this account.")
        return redirect('home')

    if request.method == 'GET':
        recent_jobs = BackupJob.objects.filter(scope=institution).order_by('-created_at')[:10]
        return render(request, 'backup/create.html', {
            'institution': institution,
            'recent_jobs': recent_jobs,
        })

    # ─── POST: trigger the job ──────────────────────────────────────────────

    # Disk-capacity pre-check: refuse before creating any row, but record the
    # refused attempt as a failed BackupJob for visibility/audit. Guarded so
    # an OSError probing disk usage fails the request cleanly rather than
    # propagating as an unhandled exception.
    try:
        sufficient, estimated, required, free = has_sufficient_disk_space(institution)
    except OSError:
        logger.exception(
            "Backup trigger: disk-space check raised for institution=%s", institution.slug
        )
        messages.error(
            request,
            "Could not verify available disk space. Please try again or contact support."
        )
        return redirect('backup:backup-create')

    if not sufficient:
        BackupJob.objects.create(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.FAILED,
            scope=institution,
            triggered_by=request.user,
            error_message=(
                f"Insufficient disk space to safely complete this backup: "
                f"{free} bytes free, {required} bytes required (estimated export size {estimated} bytes)."
            ),
        )
        logger.error(
            "Backup trigger refused for institution=%s: insufficient disk space "
            "(free=%s, required=%s, estimated=%s).",
            institution.slug, free, required, estimated,
        )
        messages.error(
            request,
            "Not enough free disk space to safely run this backup. "
            "Please contact your system administrator."
        )
        return redirect('backup:backup-create')

    # Concurrency lock + job creation as ONE atomic unit: a naive
    # exists()-then-create() lets two near-simultaneous requests both pass
    # the check before either row commits, launching two subprocesses for
    # the same institution. select_for_update() gives real row-level
    # protection on Postgres; on SQLite (no row-level locking support) the
    # surrounding transaction still serializes concurrent writers via
    # SQLite's own database-level write lock.
    with transaction.atomic():
        already_running = BackupJob.objects.select_for_update().filter(
            scope=institution, status__in=[BackupJobStatus.PENDING, BackupJobStatus.RUNNING]
        ).exists()
        job = None
        if not already_running:
            job = BackupJob.objects.create(
                job_type=BackupJobType.BACKUP,
                status=BackupJobStatus.PENDING,
                scope=institution,
                triggered_by=request.user,
            )

    if job is None:
        messages.error(
            request,
            "A backup for your institution is already pending or running. "
            "Please wait for it to finish before starting another."
        )
        return redirect('backup:backup-create')

    manage_py = str(settings.BASE_DIR / "manage.py")
    archive_dir = settings.BASE_DIR / "backups" / str(job.id)
    log_path = archive_dir / "run_backup.log"

    popen_kwargs = {"cwd": str(settings.BASE_DIR)}
    if os.name == 'nt':
        # Detached process group on Windows — survives this worker's lifecycle.
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        # Detached session on POSIX — survives this worker's lifecycle.
        popen_kwargs["start_new_session"] = True

    # mkdir + Popen share one guarded block: a failure at EITHER point (not
    # just Popen) must mark the job failed rather than leaving it stuck
    # pending with no explanation.
    try:
        archive_dir.mkdir(parents=True, exist_ok=True)
        with open(log_path, "ab") as log_file:
            subprocess.Popen(
                [sys.executable, manage_py, "run_backup", str(job.id)],
                stdout=log_file,
                stderr=log_file,
                stdin=subprocess.DEVNULL,
                **popen_kwargs,
            )
    except OSError as e:
        logger.exception("Failed to launch run_backup subprocess for job=%s", job.id)
        job.status = BackupJobStatus.FAILED
        job.error_message = f"Failed to launch backup process: {e}"
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        messages.error(request, "Failed to start the backup process. Please try again.")
        return redirect('backup:backup-create')

    logger.info(
        "User '%s' triggered BackupJob %s for institution '%s'",
        request.user.username, job.id, institution.slug,
    )
    messages.success(
        request,
        "Backup started. This may take a while for large institutions — "
        "check back here for status."
    )
    return redirect('backup:backup-create')
