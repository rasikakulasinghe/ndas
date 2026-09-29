"""
Backup trigger view — Story 1.1, extended by Story 1.2 for super-admin
system-wide / explicit multi-institution scope selection, and by Story 1.4
for an optional date-range filter available to every triggering user.

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
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
from django_ratelimit.decorators import ratelimit

from ndas.custom_codes.choice import (
    UserType, BackupJobType, BackupJobStatus, BackupJobScopeType, RestoreUploadStatus,
)
from ndas.custom_codes.error_handlers import handle_view_errors
from ndas.custom_codes.validators import sanitize_filename
from backup import restore_apply, restore_audit
from backup import restore_preview as preview_service
from backup import restore_validation
from backup.forms import BackupScopeForm, RestoreConfirmForm, RestoreUploadForm
from backup.job_lock import create_job_unless_overlapping
from backup.models import BackupJob, RestoreUpload
from backup.services import get_archive_path, has_sufficient_disk_space
from institution.models import Institution

logger = logging.getLogger(__name__)
# Story 2.1: denials and archive rejections log under `django.security` so
# they reach security.log.
security_logger = restore_validation.security_logger


def _get_admin_institution(request):
    """Mirror institution/views.py's `_get_admin_institution` helper."""
    return getattr(request, 'institution', None) or getattr(request.user, 'institution', None)


@dataclass
class ResolvedScope:
    """
    Story 1.2's original 5-element `_resolve_scope_from_request` return
    tuple (scope_type, institutions, system_wide, error_message, scope_form)
    was already getting unwieldy; Story 1.4 adds two more fields (the
    resolved date filter), so it's a dataclass instead of growing the tuple
    further.

      - `institutions` is always a list of Institution instances (one
        element for `single`, one-or-more for `multi`, empty for `system`).
      - `date_start`/`date_end` are the validated, optional date-range bound
        -- resolved (and available) for every submitter, superadmin or not
        (Story 1.4: never privilege-gated, unlike `scope_type`/`institutions`).
      - On a validation failure (e.g. `multi` with no institutions selected,
        or `end_date < start_date`), `scope_type` is None and
        `error_message` is set; the caller must refuse before creating any
        BackupJob row. `scope_form` is the bound, invalid form so the caller
        can re-render the trigger page with field errors and the user's
        picks preserved, instead of redirecting and losing them.
    """
    scope_type: Optional[str]
    institutions: Optional[List]
    system_wide: bool
    error_message: Optional[str]
    scope_form: BackupScopeForm
    date_start: Optional[date] = None
    date_end: Optional[date] = None


def _resolve_scope_from_request(request, is_superadmin, own_institution):
    """
    Resolve this POST's backup scope + date filter (Story 1.2 + Story 1.4).

    Named `_resolve_scope_from_request` (not `_resolve_scope`) to avoid
    confusion with the unrelated `backup.services._resolve_scope`, which
    normalizes an already-decided scope into a queryset-filter descriptor
    rather than reading one out of an HTTP request.

    `BackupScopeForm` is now built and validated for *every* submitter, not
    just superadmins -- `start_date`/`end_date` are never privilege-gated,
    so their validation (including the "end before start" refusal) must run
    regardless of `is_superadmin`. But `mode`/`institutions` *content* (and
    any error `clean()` raises because of it, e.g. an empty multi-selection)
    must stay completely inert for a non-superadmin, exactly as Story 1.2
    established (I/O matrix: "Non-superadmin sends elevated scope") -- so a
    non-superadmin's request must NEVER be refused because of what `mode`/
    `institutions` contain, only because `start_date`/`end_date` are
    genuinely invalid. This is why `form.errors` is inspected field-by-field
    below rather than relying on a single `form.is_valid()` check: a bare
    `is_valid()` gate would let a crafted/stale `mode=multi` with no
    `institutions` (content that's discarded a few lines later anyway)
    wrongly refuse a legitimate non-superadmin request before the
    coercion branch is even reached -- exactly the regression this
    structure avoids. Field-level `cleaned_data` entries are still
    populated even when the form's own `clean()` raises a non-field error
    (Django runs per-field cleaning before `clean()`), so `start_date`/
    `end_date` are safely readable from `cleaned_data` in that case too.

    Returns a `ResolvedScope`.
    """
    form = BackupScopeForm(request.POST)
    form.is_valid()  # populates form.errors / form.cleaned_data either way

    # A field-level error on start_date/end_date itself (an unparsable
    # date, or `clean()`'s "end before start" refusal -- attached to
    # `end_date` specifically) is a genuine problem for EVERY submitter,
    # superadmin or not.
    if form.errors.get('start_date') or form.errors.get('end_date'):
        error_message = "; ".join(
            msg for field in ('start_date', 'end_date') for msg in form.errors.get(field, [])
        ) or "Invalid date range."
        return ResolvedScope(None, None, False, error_message, form)

    date_start = form.cleaned_data.get('start_date')
    date_end = form.cleaned_data.get('end_date')

    if not is_superadmin:
        # mode/institutions content -- and any error clean() raised solely
        # because of it -- is never trusted for a non-superadmin, so it can
        # never refuse their request either. Coerced to single + own
        # institution regardless of what was submitted.
        return ResolvedScope(
            BackupJobScopeType.SINGLE, [own_institution], False, None, form, date_start, date_end,
        )

    # Superadmin: remaining errors (invalid `mode` choice, or `clean()`'s
    # empty-multi-selection refusal) DO matter.
    if not form.is_valid():
        error_message = "; ".join(
            msg for errors in form.errors.values() for msg in errors
        ) or "Invalid backup scope selection."
        return ResolvedScope(None, None, False, error_message, form)

    mode = form.cleaned_data['mode']
    if mode == BackupJobScopeType.SYSTEM:
        return ResolvedScope(BackupJobScopeType.SYSTEM, [], True, None, form, date_start, date_end)
    if mode == BackupJobScopeType.MULTI:
        return ResolvedScope(
            BackupJobScopeType.MULTI, list(form.cleaned_data['institutions']), False, None, form,
            date_start, date_end,
        )
    return ResolvedScope(BackupJobScopeType.SINGLE, [own_institution], False, None, form, date_start, date_end)


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


def _history_jobs_for(institution, is_superadmin):
    """
    Story 3.1: the full, correctly-scoped backup history -- every visible
    `backup`/`pre_restore_snapshot` job, newest first, unpaginated (the
    caller paginates). Deliberately separate from `_recent_jobs_for` above
    (read as precedent only, per Code Map -- not reused): that helper's
    10-row cap and `scope=institution OR triggered_by=user` superadmin
    shortcut under-scopes a multi-institution job for an institutional admin
    and over-restricts a superadmin to only their own triggered jobs.

    `job_type` never includes `restore` for either branch below -- a
    `restore` job has no archive of its own to list (Boundary: covered by
    Story 2.6's audit trail instead).

    Superadmin: every matching job, system-wide, completely unfiltered by
    scope -- `job_type` in {backup, pre_restore_snapshot}, including every
    `pre_restore_snapshot` row (AD-14).

    Institutional admin: `job_type` restricted to `backup` only (a
    `pre_restore_snapshot` row is never shown -- AD-14: super-admin-only,
    regardless of scope match, so that job_type is excluded outright for
    this branch rather than merely left unmatched by the scope filter
    below) -- and only jobs whose scope covers `institution`:
    scope_type=single with scope=institution, OR scope_type=multi with
    institution in scopes, OR scope_type=system (covers every institution).
    """
    scopes_ordered = Prefetch('scopes', queryset=Institution.objects.order_by('name'))

    if is_superadmin:
        qs = BackupJob.objects.filter(
            job_type__in=(BackupJobType.BACKUP, BackupJobType.PRE_RESTORE_SNAPSHOT)
        )
    else:
        qs = BackupJob.objects.filter(job_type=BackupJobType.BACKUP).filter(
            Q(scope_type=BackupJobScopeType.SINGLE, scope=institution)
            | Q(scope_type=BackupJobScopeType.MULTI, scopes=institution)
            | Q(scope_type=BackupJobScopeType.SYSTEM)
        ).distinct()

    return qs.select_related('triggered_by', 'scope').prefetch_related(scopes_ordered).order_by('-created_at', '-id')


def _status_context(request, institution, is_superadmin):
    """Context for the `backup/status.html` partial (Story 1.5): the visible
    jobs (evaluated once, so the template and `has_active_jobs` agree) plus
    whether any is still pending/running -- which decides whether the
    fragment keeps polling itself."""
    jobs = list(_recent_jobs_for(request, institution, is_superadmin))
    active = (BackupJobStatus.PENDING, BackupJobStatus.RUNNING)
    return {
        'recent_jobs': jobs,
        'has_active_jobs': any(job.status in active for job in jobs),
    }


def _launch_detached_command(command_name, object_id, work_dir, log_name):
    """
    Launch `manage.py <command_name> <object_id>` as a detached process
    (Story 1.1's launch rules, shared with Story 2.1's restore validation):
    its own process group/session so it survives this worker's lifecycle,
    stdout/stderr appended to `work_dir/log_name`, no stdin.

    Kept in this module, calling `subprocess.Popen` through it, so tests can
    keep patching `backup.views.subprocess.Popen`. Raises `OSError` if the
    directory can't be created or the process can't be started -- the caller
    owns marking its own row failed.
    """
    manage_py = str(settings.BASE_DIR / "manage.py")
    log_path = work_dir / log_name

    popen_kwargs = {"cwd": str(settings.BASE_DIR)}
    if os.name == 'nt':
        # Detached process group on Windows — survives this worker's lifecycle.
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        # Detached session on POSIX — survives this worker's lifecycle.
        popen_kwargs["start_new_session"] = True

    work_dir.mkdir(parents=True, exist_ok=True)
    with open(log_path, "ab") as log_file:
        subprocess.Popen(
            [sys.executable, manage_py, command_name, str(object_id)],
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.DEVNULL,
            **popen_kwargs,
        )


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
            **_status_context(request, institution, is_superadmin),
            'is_superadmin': is_superadmin,
            # Story 1.4: unlike Story 1.2's mode/institutions selector (still
            # superadmin-only in the template), the date-range fields on
            # this same form must be available to every triggering user --
            # so `scope_form` is no longer None for a non-superadmin.
            'scope_form': BackupScopeForm(),
        })

    # ─── POST: trigger the job ──────────────────────────────────────────────

    resolved = _resolve_scope_from_request(request, is_superadmin, institution)
    if resolved.scope_type is None:
        # Invalid scope/date-range selection (e.g. superadmin's `multi` with
        # no institutions chosen, or anyone's `end_date < start_date`) --
        # refused before any row is created (I/O matrix: "Superadmin:
        # multi-select, empty" / "Invalid range"). Re-render the form
        # (status 200, not a redirect) with the bound, invalid `scope_form`
        # so the template's error block actually displays and the user's
        # picks are preserved instead of lost on redirect.
        messages.error(request, resolved.error_message)
        return render(request, 'backup/create.html', {
            'institution': institution,
            **_status_context(request, institution, is_superadmin),
            'is_superadmin': is_superadmin,
            'scope_form': resolved.scope_form,
        }, status=200)

    scope_type = resolved.scope_type
    scope_institutions = resolved.institutions
    system_wide = resolved.system_wide
    date_start = resolved.date_start
    date_end = resolved.date_end

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
            disk_check_scope, system_wide=system_wide, date_start=date_start, date_end=date_end,
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
            trigger_institution=institution,
            triggered_by=request.user,
            date_filter_start=date_start,
            date_filter_end=date_end,
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

    # Concurrency lock + job creation as ONE atomic unit, shared with the
    # restore start (`backup/job_lock.py`): refuses when an overlapping job of
    # any type is pending or running.
    job = create_job_unless_overlapping(
        scope_type, scope_institutions,
        job_type=BackupJobType.BACKUP,
        status=BackupJobStatus.PENDING,
        trigger_institution=institution,
        triggered_by=request.user,
        date_filter_start=date_start,
        date_filter_end=date_end,
    )

    if job is None:
        messages.error(
            request,
            "A backup overlapping this scope is already pending or running. "
            "Please wait for it to finish before starting another."
        )
        return redirect('backup:backup-create')

    # mkdir + Popen share one guarded block: a failure at EITHER point (not
    # just Popen) must mark the job failed rather than leaving it stuck
    # pending with no explanation.
    try:
        _launch_detached_command(
            "run_backup", job.id, settings.BASE_DIR / "backups" / str(job.id), "run_backup.log",
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


@require_GET
@ratelimit(key='user_or_ip', rate='30/m')
def backup_status(request):
    """
    Story 1.5: HTMX-polled fragment -- the "Recent Backup Jobs" table.

    Same ADMIN/SUPERADMIN gate and job visibility as `backup_create`
    (`_recent_jobs_for`), but a failed gate returns an empty 403 instead of
    a redirect: the response is swapped into a page fragment. Polled every 5s
    while any listed job is pending/running, so it has its own, higher
    rate limit than the project default.
    """
    if not request.user.is_authenticated:
        # `@login_required` would 302 to the login page, which htmx follows
        # and swaps -- whole page and all -- into the card. HX-Redirect makes
        # htmx do a full-page navigation to the login page instead.
        return HttpResponse(status=204, headers={'HX-Redirect': reverse('user-login')})

    user_type = getattr(request.user, 'user_type', None)
    if user_type not in (UserType.ADMIN, UserType.SUPERADMIN):
        return HttpResponseForbidden()

    institution = _get_admin_institution(request)
    if institution is None:
        return HttpResponseForbidden()

    return render(
        request, 'backup/status.html',
        _status_context(request, institution, user_type == UserType.SUPERADMIN),
    )


@login_required(login_url="user-login")
@require_GET
@ratelimit(key='user_or_ip', rate='30/m')
@handle_view_errors(redirect_url='home', error_message='Failed to load backup history.')
def backup_history(request):
    """
    Story 3.1: the dedicated, paginated backup-history page -- every
    `backup`/`pre_restore_snapshot` job visible to this admin (see
    `_history_jobs_for`), 25 per page, newest first. A separate page from
    Story 1.5's "Recent Backup Jobs" widget (`backup_status`/
    `_recent_jobs_for`), which this view does not touch: that fragment stays
    the trigger page's own capped, actively-polled glance.

    Same ADMIN/SUPERADMIN gate as `backup_create` -- a non-admin (or an
    admin with no resolved institution context) is redirected home, no data
    rendered.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type not in (UserType.ADMIN, UserType.SUPERADMIN):
        messages.error(request, "You don't have permission to view backup history.")
        return redirect('home')

    institution = _get_admin_institution(request)
    if institution is None:
        messages.error(request, "No institution context found for this account.")
        return redirect('home')

    is_superadmin = user_type == UserType.SUPERADMIN
    jobs = _history_jobs_for(institution, is_superadmin)

    paginator = Paginator(jobs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Size-from-disk (Boundary: no `size_bytes` field on BackupJob -- read
    # once per completed row, at render time, from the archive that
    # `run_backup` writes to `get_archive_path`). Set as a plain attribute on
    # each row object (not a separate id-keyed dict) so the template can read
    # `job.archive_size_bytes` directly instead of needing a dynamic-key
    # dict lookup, which the Django template language doesn't support.
    for job in page_obj:
        if job.status == BackupJobStatus.COMPLETED:
            try:
                job.archive_size_bytes = os.path.getsize(get_archive_path(job))
            except OSError:
                # Archive pruned/missing since the list was last loaded (I/O
                # matrix: 'Job completed, archive file missing from disk' --
                # the row shows "unavailable" instead of a size).
                job.archive_size_bytes = None
        else:
            job.archive_size_bytes = None

    return render(request, 'backup/manager.html', {
        'institution': institution,
        'is_superadmin': is_superadmin,
        'page_obj': page_obj,
    })


def _backup_download_filename(job):
    """Server-constructed download filename -- built from the job's own id,
    type and created date only, never from user input (Design Notes: no
    scope-name/institution-slug, unlike the Excel export's institution-slug
    naming -- there is no scope-label helper for BackupJob and building one
    is unrelated surface area for this story)."""
    kind = 'pre_restore_snapshot' if job.job_type == BackupJobType.PRE_RESTORE_SNAPSHOT else 'backup'
    return f"ndas_{kind}_{job.id}_{job.created_at:%Y%m%d}.zip"


def _log_backup_download_refused(request, pk):
    """A download was refused because the job id is unknown, not completed, or
    out of this admin's scope -- the response is a plain 404 either way (AD-7:
    no hint which). Mirrors `restore_audit.log_unknown_upload`'s
    audit-without-leaking pattern: `exists` is recorded server-side only (in
    the log, never in the response) so an unknown pk can be told from another
    admin's job when this line is read later.

    Review patch (P4): the existence check itself can fail (e.g. a DB error)
    independently of whether the job exists -- that failure is logged as
    `exists=unknown` rather than silently folded into `exists=False`, so an
    operator reading the log later can tell "no such job" from "couldn't
    check"."""
    try:
        exists = BackupJob.objects.filter(pk=pk).exists()
    except Exception:
        logger.exception("Backup download refusal: could not check whether job=%s exists.", pk)
        exists = 'unknown'
    security_logger.warning(
        "Backup download refused (unknown, not completed, or out of scope): user=%s job=%s exists=%s",
        getattr(request.user, 'username', '?'), pk, exists,
    )


@login_required(login_url="user-login")
@require_GET
@ratelimit(key='user_or_ip', rate='30/m')
def backup_download(request, pk):
    """
    Story 3.2: stream a completed backup's `.zip` archive to an admin whose
    scope covers it -- exactly Story 3.1's `_history_jobs_for` scoping,
    filtered to `status=completed`.

    Deliberately undecorated by `handle_view_errors` at this level (mirrors
    the restore views' own-upload-lookup pattern, e.g. `restore_status`/
    `_own_upload_or_404`): `get_object_or_404` raises a plain `Http404` for a
    wrong-status/out-of-scope/unknown pk, and `handle_view_errors`'s generic
    `except Exception` clause would otherwise catch that `Http404` and turn
    it into a redirect -- exactly the information leak AD-7's one-shot 404
    is meant to avoid. The vanished-archive case is different (the row
    itself confirms the backup is real and completed) and gets its own
    friendly refusal below, per Design Notes.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type not in (UserType.ADMIN, UserType.SUPERADMIN):
        security_logger.warning(
            "Backup download denied (not an admin): user=%s user_type=%s job=%s",
            request.user.username, user_type, pk,
        )
        messages.error(request, "You don't have permission to download backups.")
        return redirect('home')

    institution = _get_admin_institution(request)
    if institution is None:
        security_logger.warning(
            "Backup download denied (no institution context): user=%s job=%s",
            request.user.username, pk,
        )
        messages.error(request, "No institution context found for this account.")
        return redirect('home')

    is_superadmin = user_type == UserType.SUPERADMIN
    try:
        job = get_object_or_404(
            _history_jobs_for(institution, is_superadmin), pk=pk, status=BackupJobStatus.COMPLETED,
        )
    except Http404:
        _log_backup_download_refused(request, pk)
        raise

    return _backup_download_body(request, job)


@handle_view_errors(redirect_url='backup:backup-history', error_message='Failed to download the backup.')
def _backup_download_body(request, job):
    """Open and stream the archive, or refuse cleanly if it has vanished from
    disk. `open()`/`os.fstat()` are wrapped together so a missing or
    unreadable archive is caught before any bytes reach the client -- never a
    raw exception, never a partial/corrupt stream. Nothing on disk is
    modified.

    Review patch (P1): `archive_file` is tracked outside the `try` so that if
    `open()` succeeds but the subsequent `os.fstat()` raises (rare, but
    possible -- e.g. the file vanishes between the two calls), the already-open
    handle is explicitly closed before refusing, instead of leaking the fd."""
    archive_path = get_archive_path(job)
    archive_file = None
    try:
        archive_file = open(archive_path, 'rb')
        archive_size = os.fstat(archive_file.fileno()).st_size
    except OSError:
        if archive_file is not None:
            archive_file.close()
        security_logger.warning(
            "Backup download refused (archive missing from disk): user=%s job=%s",
            request.user.username, job.id,
        )
        messages.error(request, "This backup's archive file is no longer available.")
        return redirect('backup:backup-history')

    filename = _backup_download_filename(job)
    security_logger.info(
        "Backup download: user=%s job=%s size=%s filename=%s",
        request.user.username, job.id, archive_size, filename,
    )
    response = FileResponse(archive_file, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    # Review patch (P3): a full institution backup archive must never be
    # cached by an intermediary or the browser.
    response['Cache-Control'] = 'no-store, private'
    return response

# ─── Story 2.1: restore archive upload + validation ─────────────────────────


def _is_superadmin(user):
    return getattr(user, 'user_type', None) == UserType.SUPERADMIN


def _deny_restore(request, view_name):
    """Log a non-super-admin's attempt at a restore URL to security.log."""
    security_logger.warning(
        "Restore access denied: user=%s user_type=%s view=%s path=%s",
        getattr(request.user, 'username', '?'), getattr(request.user, 'user_type', None),
        view_name, request.path,
    )


def _own_upload_or_404(request, view_name, pk):
    """The requesting super admin's own upload, else a 404 -- and, for the
    audit trail (Story 2.6), a security-log line saying the upload was unknown
    or someone else's."""
    try:
        return get_object_or_404(RestoreUpload, pk=pk, uploaded_by=request.user)
    except Http404:
        restore_audit.log_unknown_upload(request, view_name, pk)
        raise


def _latest_upload_for(user):
    return RestoreUpload.objects.filter(uploaded_by=user).order_by('-created_at', '-id').first()


@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='backup:restore-upload', error_message='Failed to process the restore upload.')
def restore_upload(request):
    """
    Super admin only: upload a backup archive, stage it to non-public
    storage, and launch the detached validation command. Nothing is applied
    to any data (that is Stories 2.2/2.3).

    GET  -> the upload form (+ a link to this user's latest upload, if any).
    POST -> form checks (nothing staged and no row on failure) -> one
            validating upload per user check + row creation -> replace
            earlier finished uploads -> stage (hashing as it streams) ->
            launch -> redirect to the status page.
    """
    if not _is_superadmin(request.user):
        _deny_restore(request, 'restore_upload')
        messages.error(request, "You don't have permission to restore data.")
        return redirect('home')

    def _render_form(form):
        return render(request, 'backup/restore.html', {
            'form': form,
            'max_size_bytes': settings.FILE_UPLOAD_LIMITS['RESTORE_ARCHIVE_MAX_SIZE'],
            'latest_upload': _latest_upload_for(request.user),
        })

    if request.method == 'GET':
        return _render_form(RestoreUploadForm())

    # Story 2.2: a confirmed archive is awaiting a restore and is never
    # replaced or deleted by a new upload -- only by an explicit cancel.
    # Story 2.3: neither is one whose restore is being applied right now.
    if RestoreUpload.objects.filter(uploaded_by=request.user, status=RestoreUploadStatus.APPLYING).exists():
        security_logger.info(
            "Restore upload refused (a restore is being applied): user=%s", request.user.username,
        )
        messages.error(
            request,
            "A restore is being applied right now. Wait for it to finish before uploading another archive."
        )
        return redirect('backup:restore-upload')
    if RestoreUpload.objects.filter(uploaded_by=request.user, status=RestoreUploadStatus.CONFIRMED).exists():
        security_logger.info(
            "Restore upload refused (a confirmed upload exists): user=%s", request.user.username,
        )
        messages.error(
            request,
            "You have a confirmed restore archive that has not been applied. "
            "Cancel it first before uploading another archive."
        )
        return redirect('backup:restore-upload')

    form = RestoreUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        security_logger.warning(
            "Restore upload refused: user=%s errors=%s", request.user.username, form.errors.as_json(),
        )
        return _render_form(form)

    uploaded = form.cleaned_data['archive']

    # One `validating` upload per super admin. The friendly pre-check gives a
    # clean message; the partial unique constraint on the model is what makes
    # it hold under concurrency (select_for_update locks nothing when no row
    # exists, and is a no-op on SQLite) -- an IntegrityError here means a
    # concurrent request won the race.
    upload = None
    try:
        with transaction.atomic():
            busy = RestoreUpload.objects.filter(
                uploaded_by=request.user, status=RestoreUploadStatus.VALIDATING,
            ).exists()
            if not busy:
                upload = RestoreUpload.objects.create(
                    uploaded_by=request.user,
                    original_filename=sanitize_filename(uploaded.name, max_length=255),
                    size_bytes=uploaded.size,
                    allow_unverified=form.cleaned_data['allow_unverified'],
                    status=RestoreUploadStatus.VALIDATING,
                )
    except IntegrityError:
        upload = None
    if upload is None:
        messages.error(
            request,
            "You already have an upload being validated. Please wait for its result "
            "before uploading another archive."
        )
        return redirect('backup:restore-upload')

    # From here on the row is `validating` with no process yet: anything that
    # raises before the launch must mark it failed (and remove its files), or
    # the one-validating-upload rule would lock this user out.
    try:
        size, sha256 = restore_validation.stage_upload(upload, uploaded)
        upload.size_bytes = size
        upload.archive_sha256 = sha256
        upload.save(update_fields=['size_bytes', 'archive_sha256', 'updated_at'])

        # Only now that the new archive is safely staged is it safe to
        # replace the user's earlier finished uploads.
        restore_validation.delete_finished_uploads(request.user, keep_id=upload.id)

        try:
            _launch_detached_command(
                "validate_restore_upload", upload.id,
                restore_validation.get_upload_dir(upload), "validate_restore_upload.log",
            )
        except OSError as e:
            logger.exception("Failed to launch validate_restore_upload subprocess for upload=%s", upload.id)
            _mark_upload_failed(upload, f"Failed to launch the validation process: {e}", keep_dir=True)
            messages.error(request, "Failed to start validating the archive. Please try again.")
            return redirect('backup:restore-status', pk=upload.id)
    except Exception as e:
        logger.exception("Restore upload %s: failed before the validation process was launched.", upload.id)
        _mark_upload_failed(upload, f"Failed to store or start validating the uploaded file: {e}")
        messages.error(request, "Failed to store the uploaded file. Please try again.")
        return redirect('backup:restore-upload')

    logger.info(
        "Super admin '%s' uploaded restore archive %r as RestoreUpload %s (%s bytes)",
        request.user.username, upload.original_filename, upload.id, size,
    )
    messages.success(request, "Archive uploaded. Validation is running in the background.")
    return redirect('backup:restore-status', pk=upload.id)


def _mark_upload_failed(upload, message, keep_dir=False):
    """Record a pre-launch failure on the row and remove its staged files.
    `keep_dir` removes only the archive (the launch log stays for diagnosis)."""
    try:
        if keep_dir:
            restore_validation.delete_staged_archive(upload)
        else:
            restore_validation.delete_upload_files(upload)
    except OSError:
        logger.exception("Could not remove staged files for failed RestoreUpload %s.", upload.id)
    try:
        upload.status = RestoreUploadStatus.FAILED
        upload.error_message = message
        upload.save(update_fields=['status', 'error_message', 'updated_at'])
    except Exception:
        logger.exception("Could not mark RestoreUpload %s as failed.", upload.id)


def _restore_status_context(upload):
    """Template context for the status page/fragment. The record counts are
    handed over as a sorted list of pairs: iterating an untrusted dict with
    `{% for k, v in d.items %}` would resolve a crafted "items" key first."""
    summary = upload.manifest_summary or {}
    counts = summary.get('record_counts') or {}
    return {
        'upload': upload,
        'record_counts': sorted(counts.items()) if isinstance(counts, dict) else [],
        'can_cancel': preview_service.can_cancel(upload),
        'confirmed_snapshot': upload.confirmed_snapshot if isinstance(upload.confirmed_snapshot, dict) else {},
        # Story 2.3: the latest restore job for this upload (status/progress
        # while `applying`, its outcome afterwards, a failed attempt's reason
        # once the upload is back to `confirmed`).
        'restore_job': (
            upload.restore_jobs.select_related('pre_restore_snapshot').order_by('-created_at', '-id').first()
        ),
    }


@login_required(login_url="user-login")
@require_GET
@ratelimit(key='user_or_ip', rate='30/m')
def restore_status(request, pk):
    """Super admin only: the status page for one of their own uploads."""
    if not _is_superadmin(request.user):
        _deny_restore(request, 'restore_status')
        messages.error(request, "You don't have permission to restore data.")
        return redirect('home')

    upload = _own_upload_or_404(request, 'restore_status', pk)
    return render(request, 'backup/restore_status.html', _restore_status_context(upload))


@require_GET
@ratelimit(key='user_or_ip', rate='30/m')
def restore_status_fragment(request, pk):
    """
    HTMX-polled fragment for `restore_status` (Story 1.5's pattern): same
    gates, but a denial is an empty 403 and an anonymous poll is a 204 +
    HX-Redirect to login, since the response is swapped into the page.
    """
    if not request.user.is_authenticated:
        return HttpResponse(status=204, headers={'HX-Redirect': reverse('user-login')})

    if not _is_superadmin(request.user):
        _deny_restore(request, 'restore_status_fragment')
        return HttpResponseForbidden()

    upload = _own_upload_or_404(request, 'restore_status_fragment', pk)
    return render(request, 'backup/restore_status_partial.html', _restore_status_context(upload))


# --- Story 2.2: restore preview, confirmation and cancel ---------------------
#
# Each view does the gate and the ownership lookup itself (so a foreign or
# unknown upload stays a 404: `handle_view_errors` would turn Http404 into a
# redirect) and hands the rest to a `handle_view_errors`-wrapped body.


def _redirect_to_status(upload):
    return redirect('backup:restore-status', pk=upload.id)


def _render_preview(request, upload, form=None):
    preview = preview_service.build_preview(upload)
    return render(request, 'backup/restore_preview.html', {
        'upload': upload,
        'preview': preview,
        'form': form or RestoreConfirmForm(),
        'can_cancel': preview_service.can_cancel(upload),
    })


@login_required(login_url="user-login")
@require_GET
@ratelimit(key='user_or_ip', rate='30/m')
def restore_preview(request, pk):
    """
    Super admin only: the read-only preview of one of their own validated
    uploads -- what the archive holds against what this system holds now. A
    GET writes no row and touches no file; it is built from the validated
    manifest summary plus live counts, never by opening the zip.
    """
    if not _is_superadmin(request.user):
        _deny_restore(request, 'restore_preview')
        messages.error(request, "You don't have permission to restore data.")
        return redirect('home')

    upload = _own_upload_or_404(request, 'restore_preview', pk)
    return _restore_preview_body(request, upload)


@handle_view_errors(redirect_url='backup:restore-upload', error_message='Failed to load the restore preview.')
def _restore_preview_body(request, upload):
    if upload.status != RestoreUploadStatus.VALIDATED:
        messages.warning(request, "Only a validated archive can be previewed.")
        return _redirect_to_status(upload)
    return _render_preview(request, upload)


@login_required(login_url="user-login")
@require_http_methods(["POST"])
@ratelimit(key='user_or_ip', rate='10/m')
def restore_confirm(request, pk):
    """
    Super admin only: confirm a validated upload's preview. Needs the
    acknowledgement checkbox and the preview's digest; records a snapshot of
    what was previewed and marks the upload `confirmed`. Nothing is applied.
    """
    if not _is_superadmin(request.user):
        _deny_restore(request, 'restore_confirm')
        messages.error(request, "You don't have permission to restore data.")
        return redirect('home')

    upload = _own_upload_or_404(request, 'restore_confirm', pk)
    return _restore_confirm_body(request, upload)


@handle_view_errors(redirect_url='backup:restore-upload', error_message='Failed to confirm the restore.')
def _restore_confirm_body(request, upload):
    if upload.status != RestoreUploadStatus.VALIDATED:
        security_logger.warning(
            "Restore confirm refused (status=%s): user=%s upload=%s", upload.status, request.user.username, upload.id,
        )
        messages.error(request, "This upload is not awaiting confirmation.")
        return _redirect_to_status(upload)

    form = RestoreConfirmForm(request.POST)
    if not form.is_valid():
        security_logger.warning(
            "Restore confirm refused (form): user=%s upload=%s errors=%r",
            request.user.username, upload.id, form.errors.as_json(),
        )
        return _render_preview(request, upload, form=form)

    outcome = preview_service.confirm_upload(
        upload.id, request.user, form.cleaned_data['digest'], form.cleaned_data['acknowledge'],
    )
    if outcome.ok:
        messages.success(
            request,
            "Restore confirmed. It has NOT been applied yet: nothing in the system was changed.",
        )
        return _redirect_to_status(upload)

    messages.error(request, outcome.message)
    if outcome.code == preview_service.NOT_VALIDATED:
        return _redirect_to_status(upload)
    return redirect('backup:restore-preview', pk=upload.id)


@login_required(login_url="user-login")
@require_http_methods(["POST"])
@ratelimit(key='user_or_ip', rate='5/m')
def restore_start(request, pk):
    """
    Super admin only: start applying one of their own confirmed uploads
    (Story 2.3). Creates the `restore` job under the job lock, flips the upload
    to `applying` and launches the detached `run_restore` process; the status
    page then shows its progress. Confirming (Story 2.2) stays record-only.
    """
    if not _is_superadmin(request.user):
        _deny_restore(request, 'restore_start')
        messages.error(request, "You don't have permission to restore data.")
        return redirect('home')

    upload = _own_upload_or_404(request, 'restore_start', pk)
    return _restore_start_body(request, upload)


@handle_view_errors(redirect_url='backup:restore-upload', error_message='Failed to start the restore.')
def _restore_start_body(request, upload):
    institution = _get_admin_institution(request)
    if institution is None:
        messages.error(request, "No institution context found for this account.")
        return redirect('home')

    outcome = restore_apply.start_restore(upload, request.user, institution)
    if not outcome.ok:
        messages.error(request, outcome.message)
        return _redirect_to_status(upload)

    job = outcome.job
    # The log goes in the upload's directory: the restore job has no directory
    # of its own (its snapshot job gets one under backups/).
    try:
        _launch_detached_command(
            "run_restore", job.id, restore_validation.get_upload_dir(upload), "run_restore.log",
        )
    except OSError as e:
        logger.exception("Failed to launch run_restore subprocess for job=%s", job.id)
        restore_apply.abort_start(job, upload, f"Failed to launch restore process: {e}")
        messages.error(request, "Failed to start the restore process. The upload is confirmed again; please try again.")
        return _redirect_to_status(upload)

    logger.info("Super admin '%s' started restore job %s for RestoreUpload %s", request.user.username, job.id, upload.id)
    messages.success(
        request,
        "Restore started. It first takes a snapshot of the current data, then applies the archive; "
        "this page shows its progress."
    )
    return _redirect_to_status(upload)


@login_required(login_url="user-login")
@require_http_methods(["POST"])
@ratelimit(key='user_or_ip', rate='10/m')
def restore_cancel(request, pk):
    """
    Super admin only: discard one of their own uploads -- its staged files and
    its row. Allowed for a validated, confirmed, rejected or failed upload,
    and for a validating one only when it is stale.
    """
    if not _is_superadmin(request.user):
        _deny_restore(request, 'restore_cancel')
        messages.error(request, "You don't have permission to restore data.")
        return redirect('home')

    upload = _own_upload_or_404(request, 'restore_cancel', pk)
    return _restore_cancel_body(request, upload)


@handle_view_errors(redirect_url='backup:restore-upload', error_message='Failed to cancel the restore upload.')
def _restore_cancel_body(request, upload):
    outcome = preview_service.cancel_upload(upload.id, request.user)
    if outcome.ok:
        messages.success(request, "The restore upload was cancelled and its staged archive removed.")
        return redirect('backup:restore-upload')

    if outcome.code == preview_service.GONE:
        # e.g. a double click: the first cancel already removed it.
        messages.info(request, "That upload was already cancelled.")
        return redirect('backup:restore-upload')

    messages.error(request, outcome.message)
    return _redirect_to_status(upload)
