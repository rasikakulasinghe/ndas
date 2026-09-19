"""
Backup trigger view — Story 1.1, extended by Story 1.2 for super-admin
system-wide / explicit multi-institution scope selection.

The ONLY entry point into `backup/services.py`'s export logic: permission
check -> scope resolution -> concurrency/overlap-lock check -> disk-space
check -> create `BackupJob` -> launch a detached subprocess running
`manage.py run_backup <job_id>` -> redirect immediately. The export itself
never runs synchronously in this request.
"""
import logging
import os
import subprocess
import sys

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from ndas.custom_codes.choice import UserType, BackupJobType, BackupJobStatus, BackupJobScopeType
from ndas.custom_codes.error_handlers import handle_view_errors
from backup.forms import BackupScopeForm
from backup.models import BackupJob
from backup.services import has_sufficient_disk_space

logger = logging.getLogger(__name__)


def _get_admin_institution(request):
    """Mirror institution/views.py's `_get_admin_institution` helper."""
    return getattr(request, 'institution', None) or getattr(request.user, 'institution', None)


def _resolve_scope_from_request(request, is_superadmin, own_institution):
    """
    Resolve this POST's backup scope (Story 1.2).

    Named `_resolve_scope_from_request` (not `_resolve_scope`) to avoid
    confusion with the unrelated `backup.services._resolve_scope`, which
    normalizes an already-decided scope into a queryset-filter descriptor
    rather than reading one out of an HTTP request.

    Returns (scope_type, institutions, system_wide, error_message, scope_form):
      - `institutions` is always a list of Institution instances (one
        element for `single`, one-or-more for `multi`, empty for `system`).
      - A non-superadmin's POST body is never trusted for scope_type/
        institution selection -- coerced server-side to `single` + the
        requester's own institution regardless of what was submitted (I/O
        matrix: "Non-superadmin sends elevated scope"); `scope_form` is None
        in this path since a non-superadmin never renders/uses one.
      - On a validation failure (e.g. `multi` with no institutions
        selected), scope_type is None and `error_message` is set; the
        caller must refuse before creating any BackupJob row. `scope_form`
        is the bound, invalid form so the caller can re-render the trigger
        page with field errors and the user's picks preserved, instead of
        redirecting and losing them.
    """
    if not is_superadmin:
        return BackupJobScopeType.SINGLE, [own_institution], False, None, None

    form = BackupScopeForm(request.POST)
    if not form.is_valid():
        error_message = "; ".join(
            msg for errors in form.errors.values() for msg in errors
        ) or "Invalid backup scope selection."
        return None, None, False, error_message, form

    mode = form.cleaned_data['mode']
    if mode == BackupJobScopeType.SYSTEM:
        return BackupJobScopeType.SYSTEM, [], True, None, form
    if mode == BackupJobScopeType.MULTI:
        return BackupJobScopeType.MULTI, list(form.cleaned_data['institutions']), False, None, form
    return BackupJobScopeType.SINGLE, [own_institution], False, None, form


def _scope_log_description(scope_type, scope_institutions, system_wide):
    """
    Human-readable description of a resolved scope for log messages.

    Replaces the old hardcoded "for institution=%s" (the requester's own/
    session institution) which was misleading for `multi`/`system` scopes
    that span other institutions or everything.
    """
    if system_wide:
        return "system-wide (all institutions)"
    if scope_type == BackupJobScopeType.MULTI:
        slugs = ", ".join(inst.slug for inst in scope_institutions)
        return f"multi institutions=[{slugs}]"
    return f"institution={scope_institutions[0].slug}"


def _recent_jobs_for(request, institution, is_superadmin):
    """Shared GET/re-render query: the last 10 jobs relevant to this user."""
    if is_superadmin:
        # A superadmin's own multi/system jobs have scope=None -- filtering
        # on `scope=institution` alone would hide them, so also include
        # anything this user triggered (I/O matrix / boundary: the GET
        # listing "must also surface multi/system jobs a superadmin
        # triggered" -- "it cannot key off scope alone").
        return BackupJob.objects.filter(
            Q(scope=institution) | Q(triggered_by=request.user)
        ).order_by('-created_at').distinct()[:10]
    return BackupJob.objects.filter(scope=institution).order_by('-created_at')[:10]


def _resolved_institution_ids(job):
    """The set of institution ids `job`'s data covers -- empty for a
    system-wide job (its overlap with every other job is handled by the
    caller checking `scope_type == SYSTEM` directly, not via this set).
    Iterates the prefetched `.scopes.all()` cache rather than
    `.values_list()` (which would bypass `prefetch_related` and re-hit the
    DB per job)."""
    if job.scope_type == BackupJobScopeType.MULTI:
        return {inst.id for inst in job.scopes.all()}
    return {job.scope_id} if job.scope_id else set()


@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='backup:backup-create', error_message='Failed to trigger backup.')
def backup_create(request):
    """
    Institutional admin: trigger a full-scope backup of their institution's
    data. Super admin: also choose the scope explicitly -- their own
    institution only, an explicit multi-institution subset, or the entire
    system (Story 1.2's `BackupScopeForm`).

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

    is_superadmin = user_type == UserType.SUPERADMIN

    if request.method == 'GET':
        return render(request, 'backup/create.html', {
            'institution': institution,
            'recent_jobs': _recent_jobs_for(request, institution, is_superadmin),
            'is_superadmin': is_superadmin,
            'scope_form': BackupScopeForm() if is_superadmin else None,
        })

    # ─── POST: trigger the job ──────────────────────────────────────────────

    scope_type, scope_institutions, system_wide, scope_error, scope_form = _resolve_scope_from_request(
        request, is_superadmin, institution
    )
    if scope_type is None:
        # Superadmin submitted an invalid scope selection (e.g. `multi` with
        # no institutions chosen) -- refused before any row is created (I/O
        # matrix: "Superadmin: multi-select, empty"). Re-render the form
        # (status 200, not a redirect) with the bound, invalid `scope_form`
        # so the template's error block actually displays and the user's
        # mode/institution picks are preserved instead of lost on redirect.
        messages.error(request, scope_error)
        return render(request, 'backup/create.html', {
            'institution': institution,
            'recent_jobs': _recent_jobs_for(request, institution, is_superadmin),
            'is_superadmin': is_superadmin,
            'scope_form': scope_form,
        }, status=200)

    # Disk-capacity pre-check: refuse before creating any row, but record the
    # refused attempt as a failed BackupJob for visibility/audit. Guarded so
    # an OSError probing disk usage fails the request cleanly rather than
    # propagating as an unhandled exception.
    disk_check_scope = (
        None if system_wide
        else scope_institutions if scope_type == BackupJobScopeType.MULTI
        else scope_institutions[0]
    )
    try:
        sufficient, estimated, required, free = has_sufficient_disk_space(
            disk_check_scope, system_wide=system_wide
        )
    except OSError:
        logger.exception(
            "Backup trigger: disk-space check raised for scope=%s",
            _scope_log_description(scope_type, scope_institutions, system_wide),
        )
        messages.error(
            request,
            "Could not verify available disk space. Please try again or contact support."
        )
        return redirect('backup:backup-create')

    if not sufficient:
        failed_job = BackupJob.objects.create(
            job_type=BackupJobType.BACKUP,
            status=BackupJobStatus.FAILED,
            scope_type=scope_type,
            scope=scope_institutions[0] if scope_type == BackupJobScopeType.SINGLE else None,
            triggered_by=request.user,
            error_message=(
                f"Insufficient disk space to safely complete this backup: "
                f"{free} bytes free, {required} bytes required (estimated export size {estimated} bytes)."
            ),
        )
        if scope_type == BackupJobScopeType.MULTI:
            failed_job.scopes.set(scope_institutions)
        logger.error(
            "Backup trigger refused for scope=%s: insufficient disk space "
            "(free=%s, required=%s, estimated=%s).",
            _scope_log_description(scope_type, scope_institutions, system_wide), free, required, estimated,
        )
        messages.error(
            request,
            "Not enough free disk space to safely run this backup. "
            "Please contact your system administrator."
        )
        return redirect('backup:backup-create')

    # Concurrency lock + job creation as ONE atomic unit: a naive
    # exists()-then-create() lets two near-simultaneous requests both pass
    # the check before either row commits, launching two subprocesses whose
    # institution sets overlap. select_for_update() gives real row-level
    # protection on Postgres; on SQLite (no row-level locking support) the
    # surrounding transaction still serializes concurrent writers via
    # SQLite's own database-level write lock.
    #
    # Overlap rule (Story 1.2): a `system`-scoped job (new or existing)
    # overlaps every other job; otherwise two jobs overlap iff their
    # resolved institution-id sets intersect.
    resolved_ids = {inst.id for inst in scope_institutions}
    with transaction.atomic():
        existing_jobs = list(
            BackupJob.objects.select_for_update()
            .filter(status__in=[BackupJobStatus.PENDING, BackupJobStatus.RUNNING])
            .prefetch_related('scopes')
        )
        conflict = any(
            system_wide
            or existing.scope_type == BackupJobScopeType.SYSTEM
            or (_resolved_institution_ids(existing) & resolved_ids)
            for existing in existing_jobs
        )
        job = None
        if not conflict:
            job = BackupJob.objects.create(
                job_type=BackupJobType.BACKUP,
                status=BackupJobStatus.PENDING,
                scope_type=scope_type,
                scope=scope_institutions[0] if scope_type == BackupJobScopeType.SINGLE else None,
                triggered_by=request.user,
            )
            if scope_type == BackupJobScopeType.MULTI:
                job.scopes.set(scope_institutions)

    if job is None:
        messages.error(
            request,
            "A backup overlapping this scope is already pending or running. "
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
