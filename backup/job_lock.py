"""
Job-level lock shared by every job that reads or replaces an institution's
data -- Story 1.2's overlap rule, extracted from `backup_create` by Story 2.3
so a backup and a restore are held to the same rule.

`create_job_unless_overlapping()` is the only place a *triggering* view may
create a `BackupJob`: it checks every pending/running job of any type and
creates the new one inside the same atomic block. (The pre-restore snapshot
job that `run_restore` creates is deliberately not routed through here: it is
covered by its restore job's lock.)
"""
from django.db import transaction

from backup.models import BackupJob
from ndas.custom_codes.choice import BackupJobScopeType, BackupJobStatus

ACTIVE_STATUSES = (BackupJobStatus.PENDING, BackupJobStatus.RUNNING)


def resolved_institution_ids(job):
    """The set of institution ids `job`'s data covers -- empty for a
    system-wide job (its overlap with every other job is handled by the
    caller checking `scope_type == SYSTEM` directly, not via this set).
    Iterates the prefetched `.scopes.all()` cache rather than
    `.values_list()` (which would bypass `prefetch_related` and re-hit the
    DB per job)."""
    if job.scope_type == BackupJobScopeType.MULTI:
        return {inst.id for inst in job.scopes.all()}
    return {job.scope_id} if job.scope_id else set()


def create_job_unless_overlapping(scope_type, institutions, **job_fields):
    """
    Concurrency lock + job creation as ONE atomic unit: a naive
    exists()-then-create() lets two near-simultaneous requests both pass
    the check before either row commits, launching two subprocesses whose
    institution sets overlap. select_for_update() gives real row-level
    protection on Postgres; on SQLite (no row-level locking support) the
    surrounding transaction still serializes concurrent writers via
    SQLite's own database-level write lock.

    Overlap rule (Story 1.2): a `system`-scoped job (new or existing)
    overlaps every other job; otherwise two jobs overlap iff their
    resolved institution-id sets intersect. Every pending/running job counts,
    whatever its type.

    `institutions` is the list of Institution instances the new job covers
    (empty for `system`). `job_fields` are passed to `BackupJob.objects.create`
    (job_type, status, triggered_by, ...). Returns the new job, or `None` when
    an overlapping job is pending or running (nothing is created then). The
    caller may wrap this in a larger `transaction.atomic()` block.
    """
    system_wide = scope_type == BackupJobScopeType.SYSTEM
    resolved_ids = {inst.id for inst in institutions}
    with transaction.atomic():
        existing_jobs = list(
            BackupJob.objects.select_for_update()
            .filter(status__in=ACTIVE_STATUSES)
            .prefetch_related('scopes')
        )
        conflict = any(
            system_wide
            or existing.scope_type == BackupJobScopeType.SYSTEM
            or (resolved_institution_ids(existing) & resolved_ids)
            for existing in existing_jobs
        )
        if conflict:
            return None
        job = BackupJob.objects.create(
            scope_type=scope_type,
            scope=institutions[0] if scope_type == BackupJobScopeType.SINGLE else None,
            **job_fields,
        )
        if scope_type == BackupJobScopeType.MULTI:
            job.scopes.set(institutions)
        return job
