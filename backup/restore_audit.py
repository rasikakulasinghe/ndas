"""
Restore audit trail -- Story 2.6.

Every restore job that ran ends with ONE self-contained, PHI-free audit record
on its `BackupJob.restore_audit` and ONE matching line in `logs/security.log`
(the `django.security.restore` logger). Both are produced here, by
`record_and_log`, so the record and the line can never disagree.

The record embeds the acting user and the institutions by value (id, username,
slug, name) so it still reads correctly after either is deleted (the job's own
foreign keys are `SET_NULL`). It never holds a patient name, identifier, note or
archive record content: counts and integer primary keys only, and an `error`
that is the job's already-clipped failure text (or, when that text quotes data,
its value-free `audit_message`).

The audit is best-effort: a failure while building or logging it is logged and
never changes the restore's outcome, status, notification or the upload.

Also here: `log_unknown_upload`, the warning a restore view writes when a super
admin names an upload that is not theirs or does not exist (still a 404).
"""
import json
import logging
from datetime import datetime, timezone

from django.apps import apps

from backup import restore_validation
from backup.restore_apply import RESTORE_MODEL_KEYS
from ndas.custom_codes.choice import BackupJobScopeType

security_logger = restore_validation.security_logger   # 'django.security.restore'
logger = logging.getLogger(__name__)
_clip = restore_validation._clip

AUDIT_VERSION = 1
MODE_FULL = 'full'
MODE_DATE_SCOPED = 'date_scoped'
OUTCOME_COMPLETED = 'completed'
OUTCOME_WARNINGS = 'completed_with_warnings'
OUTCOME_FAILED = 'failed'

ERROR_MAX = 1000
FILENAME_MAX = 255


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _iso(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _int_or_none(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _actor(job):
    user = job.triggered_by
    if user is None:
        return {'id': None, 'username': '', 'user_type': ''}
    return {
        'id': user.pk,
        'username': _clip(user.username, 150),
        'user_type': _clip(getattr(user, 'user_type', '') or '', 50),
    }


def _institution(inst):
    return {'id': inst.pk, 'slug': _clip(inst.slug, 100), 'name': _clip(inst.name, 255)}


def _scope_institutions(job, upload):
    """The institutions the job covered, by value. A system-scoped job names
    none of its own: it takes the archive manifest's slugs (resolved to id and
    name where they still exist here)."""
    if job.scope_type == BackupJobScopeType.SYSTEM:
        manifest = (upload.manifest_summary if upload is not None else None) or {}
        slugs = manifest.get('institutions') if isinstance(manifest, dict) else None
        slugs = [s for s in (slugs or []) if isinstance(s, str)]
        Institution = apps.get_model('institution', 'Institution')
        found = {i.slug: i for i in Institution.objects.filter(slug__in=slugs)}
        return [
            _institution(found[slug]) if slug in found else {'id': None, 'slug': _clip(slug, 100), 'name': ''}
            for slug in slugs
        ]
    if job.scope_type == BackupJobScopeType.MULTI:
        return [_institution(i) for i in job.scopes.all()]
    return [_institution(job.scope)] if job.scope is not None else []


def _date_filter(upload):
    snapshot = upload.confirmed_snapshot if upload is not None else None
    date_filter = snapshot.get('date_filter') if isinstance(snapshot, dict) else None
    date_filter = date_filter if isinstance(date_filter, dict) else {}
    return {
        'start': date_filter.get('start') if isinstance(date_filter.get('start'), str) else None,
        'end': date_filter.get('end') if isinstance(date_filter.get('end'), str) else None,
    }


def _counts(result, date_scoped):
    """Numbers only (and, for a date-scoped run, the archive-pk -> new-pk pairs).
    A failed job (no `result`) carries zeros."""
    if date_scoped:
        summary = (getattr(result, 'summary', None) or {}) if result is not None else {}
        failed = summary.get('failed') or []
        patients = [
            [pair[0], pair[1]] for pair in (getattr(result, 'patients', None) or [])
            if _int_or_none(pair[0]) is not None and _int_or_none(pair[1]) is not None
        ]
        return {
            'imported': _int_or_none(summary.get('imported')) or 0,
            'skipped': _int_or_none(summary.get('skipped')) or 0,
            'excluded': _int_or_none(summary.get('excluded')) or 0,
            # The early-stop entry (archive_pk None) is not a failed patient.
            'failed': sum(1 for entry in failed if isinstance(entry, dict) and entry.get('archive_pk') is not None),
            'media_warnings': len(summary.get('media_warnings') or []),
            'patients': patients,
        }
    records = {key: 0 for key in RESTORE_MODEL_KEYS}
    if result is not None:
        records.update({k: v for k, v in (result.counts or {}).items() if _int_or_none(v) is not None})
    return {
        'records': records,
        'records_loaded': sum(records.values()),
        'referral_links_cleared': _int_or_none(getattr(result, 'referral_links_cleared', 0)) or 0,
        'move_logs_removed': _int_or_none(getattr(result, 'move_logs_removed', 0)) or 0,
        'media_warnings': len(result.warnings or []) if result is not None else 0,
    }


def success_outcome(result):
    """`completed_with_warnings` when the run reported any warning (a failed
    patient, a media warning, an early stop), else `completed`."""
    return OUTCOME_WARNINGS if getattr(result, 'warnings', None) else OUTCOME_COMPLETED


def build_audit(job, *, outcome, error='', result=None, date_scoped=False, started_at=None, finished_at=None):
    """The audit record for `job` as a plain, JSON-serialisable dict.

    `result` is the `RestoreResult`/`ImportResult` of a run that finished (None
    for a failed one); `date_scoped` picks the run's mode; `started_at` and
    `finished_at` default to now."""
    upload = job.restore_upload
    audit = {
        'version': AUDIT_VERSION,
        'actor': _actor(job),
        'upload_id': job.restore_upload_id,
        'archive': {
            'filename': _clip(upload.original_filename, FILENAME_MAX) if upload is not None else '',
            'sha256': (upload.archive_sha256 or '') if upload is not None else '',
            'source_job_id': upload.source_job_id if upload is not None else None,
        },
        'scope': {
            'mode': MODE_DATE_SCOPED if date_scoped else MODE_FULL,
            'scope_type': job.scope_type,
            'institutions': _scope_institutions(job, upload),
            'date_filter': _date_filter(upload),
        },
        'outcome': outcome,
        'started_at': _iso(started_at) or _now_iso(),
        'finished_at': _iso(finished_at) or _now_iso(),
        'snapshot_job_id': job.pre_restore_snapshot_id,
        'counts': _counts(result, date_scoped),
    }
    if outcome == OUTCOME_FAILED:
        audit['error'] = _clip(error, ERROR_MAX)
    return audit


def _log_line(job, audit):
    counts = {k: v for k, v in audit['counts'].items() if k != 'patients'}
    if 'patients' in audit['counts']:
        counts['patients'] = len(audit['counts']['patients'])
    actor = audit['actor']
    log = security_logger.info if audit['outcome'] == OUTCOME_COMPLETED else security_logger.warning
    log(
        "Restore finished: actor=%s (id=%s) upload=%s job=%s mode=%s scope=%s outcome=%s counts=%s snapshot=%s",
        actor['username'], actor['id'], audit['upload_id'], job.id, audit['scope']['mode'],
        ",".join(i['slug'] for i in audit['scope']['institutions']) or '-', audit['outcome'],
        json.dumps(counts, sort_keys=True), audit['snapshot_job_id'],
    )


def record_and_log(job, *, outcome, error='', result=None, date_scoped=False, started_at=None):
    """Build the audit record, put it on `job.restore_audit` (the caller adds
    `'restore_audit'` to its terminal `save(update_fields=...)`) and write the
    security-log line. Best-effort: on any failure it logs and returns None
    (leaving `job.restore_audit` untouched), never raising. The line is written
    before the caller's save, so it exists even if that save fails."""
    try:
        audit = build_audit(
            job, outcome=outcome, error=error, result=result, date_scoped=date_scoped, started_at=started_at,
        )
        json.dumps(audit)   # a record the terminal save could not store must not reach it
        job.restore_audit = audit
    except Exception:
        logger.exception("BackupJob %s: could not build the restore audit record.", getattr(job, 'id', None))
        return None
    try:
        _log_line(job, audit)
    except Exception:
        logger.exception("BackupJob %s: could not write the restore audit log line.", getattr(job, 'id', None))
    return audit


def log_unknown_upload(request, view_name, pk):
    """A super admin named an upload that is not theirs or does not exist: the
    view still answers 404; this leaves the audit line."""
    security_logger.warning(
        "Restore access denied (unknown or foreign upload): user=%s view=%s upload=%s",
        _clip(getattr(request.user, 'username', '?'), 150), view_name, _clip(pk, 40),
    )
