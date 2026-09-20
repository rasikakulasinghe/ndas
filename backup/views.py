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
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
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
                trigger_institution=institution,
                triggered_by=request.user,
                date_filter_start=date_start,
                date_filter_end=date_end,
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
