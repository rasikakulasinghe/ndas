"""
Restore apply -- Story 2.3.

Applies a confirmed, full-scope restore upload: a detached `run_restore`
process re-verifies the staged archive, takes a full-scope snapshot of the
current data, and then replaces the target institutions' rows for the ten
restorable models with the archive's, all in ONE database transaction. Only
after that transaction commits are the archive's media files copied into
place. Referral models and `Bookmark` are never read or changed.

Two halves, like `restore_validation`:

  * `start_restore(...)` / `abort_start(...)` -- used by `backup/views.py`
    at trigger time: the refusal checks, the job lock and the creation of the
    `restore` `BackupJob`. (The view launches the process.)
  * `execute_restore(job, progress_callback)` -- used by
    `manage.py run_restore`: `check_upload_ready`, `verify_confirmed`,
    `take_snapshot`, `preflight`, `apply_restore`, `restore_media`. Any
    failure before `apply_restore` changes no domain data; a failure inside
    it rolls the transaction back, so the data is exactly as before.

The archive's `db_export.json` is streamed (`ExportReader`, incremental
`json.JSONDecoder.raw_decode`): nothing loads the archive or a whole model
into memory.

**Known, accepted deviation (2026-09-22 review checkpoint).** The frozen
spec's Never section says "nothing is read twice except the deliberate
re-hash", but `preflight()` and `_load_records()` each independently open
the archive zip and stream the whole of `db_export.json` -- once each, plus
`verify_confirmed()`'s own already-deliberate whole-archive re-hash, so
`db_export.json` is actually read three times in total across one restore.
Raised by the three-layer adversarial review, and the user was asked and
chose to accept and document this rather than merge preflight and load into
one pass: `db_export.json` is JSON *record metadata*, not the archive's
`media/` payload -- the part that can reach 50 GiB and really is never
re-read. Re-streaming a metadata file twice is a second pass over a small
part of the archive, not a second read of its bulk. See
`spec-2-3-full-scope-restore-with-automatic-pre-restore-snapshot.md`'s Spec
Change Log and `deferred-work.md` for the single-pass refactor this could
still become if `db_export.json` sizes ever become a real cost.
"""
import hashlib
import hmac
import json
import logging
import os
import shutil
import uuid
import zipfile
from dataclasses import dataclass, field

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import serializers
from django.core.exceptions import SuspiciousFileOperation
from django.core.management.color import no_style
from django.db import connection, transaction
from django.utils._os import safe_join

from backup import restore_preview, restore_validation
from backup.export_stream import START, ExportFormatError, ExportReader
from backup.job_lock import create_job_unless_overlapping
from backup.models import BackupJob, RestoreUpload
from backup.restore_preview import EXPORT_MODEL_KEYS, REFERRAL_MODEL_KEYS, SNAPSHOT_VERSION
from backup.services import (
    COPY_CHUNK_SIZE,
    DISK_SAFETY_MINIMUM_BYTES,
    DISK_SAFETY_MULTIPLIER,
    _model_export_plan,
    create_export,
    estimate_export_size_bytes,
    get_archive_path,
)
from ndas.custom_codes.choice import (
    BackupJobScopeType,
    BackupJobStatus,
    BackupJobType,
    RestoreUploadStatus,
)

security_logger = restore_validation.security_logger
logger = logging.getLogger(__name__)
_clip = restore_validation._clip

# The ten restorable models, in load order (the export's fixed order minus the
# three referral models). Rows are deleted in the reverse of this order.
RESTORE_MODEL_KEYS = tuple(key for key in EXPORT_MODEL_KEYS if key not in REFERRAL_MODEL_KEYS)

PATIENT_KEY = 'patients.patient'
PATIENT_IDENTIFIER_FIELDS = ('bht', 'nnc_no', 'ptc_no', 'pc_no', 'pin')
# (model key, file field) of the models whose files are restored after commit.
MEDIA_FIELDS = (('video.video', 'video_file'), ('patients.attachment', 'attachment'))

# A defensive per-member ceiling on a restored media file's DECLARED
# (uncompressed) size, checked before any disk I/O for that member. Reuses
# `VIDEO_MAX_SIZE` -- the larger of the two restored file types' own upload
# limits (Video, Attachment) -- as a sane cap: a genuinely oversized zip
# entry is rejected up front instead of only after a full write-and-hash.
MEDIA_MEMBER_SIZE_CEILING = settings.FILE_UPLOAD_LIMITS['VIDEO_MAX_SIZE']

LOAD_BATCH_SIZE = 500     # records deserialized and saved per batch
LOOKUP_BATCH_SIZE = 500   # records checked against the database per preflight query
MAX_LISTED_WARNINGS = 20  # media warnings named in the job's message

# Refusal codes returned by `start_restore`.
NOT_CONFIRMED = 'not_confirmed'
BAD_SNAPSHOT = 'bad_snapshot'
INSTITUTION_MISSING = 'institution_missing'
DATE_SCOPED = 'date_scoped'
DIGEST_CHANGED = 'digest_changed'
ARCHIVE_PROBLEM = 'archive_problem'
DISK_UNKNOWN = 'disk_unknown'
DISK_TOO_SMALL = 'disk_too_small'
LOCK_CONFLICT = 'lock_conflict'


class RestoreError(Exception):
    """A specific, user-presentable reason the restore cannot proceed."""

    def __init__(self, message, audit_message=None):
        super().__init__(message)
        self.message = message
        # Story 2.6: a value-free variant for the audit record, when `message`
        # quotes data or a raw exception.
        self.audit_message = audit_message


@dataclass
class StartOutcome:
    ok: bool
    code: str = ''
    message: str = ''
    job: object = None


@dataclass
class PreflightResult:
    counts: dict = field(default_factory=dict)  # model key -> records in the archive

    @property
    def total(self):
        return sum(self.counts.values())


@dataclass
class RestoreResult:
    snapshot: object
    warnings: list
    counts: dict
    # Story 2.6: what `apply_restore` already returned, kept for the audit record.
    referral_links_cleared: int = 0
    move_logs_removed: int = 0


# --------------------------------------------------------------------------
# Progress
# --------------------------------------------------------------------------

# The restore job's overall progress, by step (0-99 until the terminal save).
REHASH_RANGE = (0, 20)
SNAPSHOT_RANGE = (20, 50)
PREFLIGHT_RANGE = (50, 60)
APPLY_START = 60  # the apply step is one transaction: nothing inside it is visible before it commits
APPLY_DONE = 90
MEDIA_RANGE = (90, 99)


class Progress:
    """
    Monotonic, capped-at-99 progress. `report(pct)` never goes backwards and
    calls `callback` only when the value changes; `span(lo, hi)` returns a
    function taking a 0..1 fraction of that step.
    """

    def __init__(self, callback=None):
        self._callback = callback
        self.last = 0

    def report(self, pct):
        pct = min(int(pct), 99)
        if pct > self.last:
            self.last = pct
            if self._callback:
                self._callback(pct)

    def span(self, low, high):
        def _report(fraction):
            self.report(low + (high - low) * min(max(fraction, 0.0), 1.0))
        return _report


# --------------------------------------------------------------------------
# Scope
# --------------------------------------------------------------------------

def scope_args(job):
    """
    `(scope_arg, system_wide, institutions)` for `job`, resolved exactly as
    `create_export` resolves a job's scope: `_model_export_plan` takes
    `scope_arg` (a single Institution, a list of them, or None) plus
    `system_wide`. Raises `RestoreError` when the job's institutions are gone.
    """
    if job.scope_type == BackupJobScopeType.SYSTEM:
        return None, True, []
    if job.scope_type == BackupJobScopeType.MULTI:
        institutions = list(job.scopes.all())
        if not institutions:
            raise RestoreError("The restore job has scope 'multi' but no institutions in its scope.")
        return institutions, False, institutions
    if job.scope is None:
        raise RestoreError("The restore job's scope institution no longer exists.")
    return job.scope, False, [job.scope]


def _restore_plan(job):
    """{model key: queryset} of the rows a same-scope backup would export, for
    the ten restorable models -- the delete set. Never date-narrowed."""
    scope_arg, system_wide, _institutions = scope_args(job)
    plan = dict(_model_export_plan(scope_arg, system_wide=system_wide))
    return {key: plan[key] for key in RESTORE_MODEL_KEYS}


def _target_institution_ids(upload, job):
    """`(ids, allow_null)`: the institution ids a restored `Patient` may
    belong to. A single/multi job's own institutions; for a system job every
    institution the manifest names that exists here, and a patient without an
    institution (a system export includes those)."""
    _scope_arg, system_wide, institutions = scope_args(job)
    if not system_wide:
        return {inst.id for inst in institutions}, False
    Institution = apps.get_model('institution', 'Institution')
    slugs = (upload.manifest_summary or {}).get('institutions') or []
    return set(Institution.objects.filter(slug__in=slugs).values_list('id', flat=True)), True


# --------------------------------------------------------------------------
# Start (view side)
# --------------------------------------------------------------------------

def has_sufficient_restore_disk(scope_arg, system_wide, archive_size):
    """
    Disk pre-check for a restore: the snapshot (estimated as a backup of the
    same scope) plus the archive's media, with the export's 1.2x margin and
    500 MB floor. Returns `(ok, estimated, required, free)`.
    """
    estimated = estimate_export_size_bytes(scope_arg, system_wide=system_wide)
    required = int((estimated + int(archive_size)) * DISK_SAFETY_MULTIPLIER) + DISK_SAFETY_MINIMUM_BYTES
    free = shutil.disk_usage(settings.BASE_DIR).free
    return free >= required, estimated, required, free


def is_date_scoped(snapshot):
    """Whether the confirmed snapshot `snapshot` records a date-scoped archive.
    `run_restore` chooses its branch from this alone."""
    date_filter = snapshot.get('date_filter') if isinstance(snapshot, dict) else None
    return bool(isinstance(date_filter, dict) and date_filter.get('applied'))


def _date_scoped_problem(preview, snapshot):
    """Story 2.5: why a date-scoped archive cannot be restored, or None.
    A full-scope archive is never a problem here. A date-scoped one can be
    restored only with Story 2.4's usable match, both in the rebuilt preview
    and carried in the confirmed snapshot (the partition is read from there)."""
    if not preview['date_filter']['applied']:
        return None
    if preview['date_scope_match'] is None:
        return (
            "This archive is date-scoped, but it has no usable computed match (only a single-institution "
            "date-scoped archive whose match was computed can be restored). Cancel this upload and "
            "upload the archive again."
        )
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get('date_scope_match'), dict):
        return (
            "This archive is date-scoped, but its confirmation record holds no match to apply. "
            "Cancel this upload and upload the archive again."
        )
    return None


def _refuse(user, upload_id, code, message, log_detail=''):
    security_logger.warning(
        "Restore start refused (%s): user=%s upload=%s %s", code, user.username, upload_id, log_detail,
    )
    return StartOutcome(False, code, message)


def start_restore(upload, user, trigger_institution):
    """
    Start `upload`'s restore (the caller has already established that `user`
    owns it). Refused, changing nothing, unless the upload is `confirmed`, its
    facts still hash to the confirmed digest, every institution it names still
    exists, it is either full-scope or date-scoped with a usable match
    (Story 2.5), its staged file is intact, the disk has room and no
    overlapping job is pending or running.

    On success the `restore` `BackupJob` (pending) is created inside the lock's
    atomic block together with the upload's flip to `applying`, and returned in
    the outcome; the caller launches `run_restore` and, if that fails, calls
    `abort_start`.
    """
    Institution = apps.get_model('institution', 'Institution')

    if upload.status != RestoreUploadStatus.CONFIRMED:
        return _refuse(user, upload.id, NOT_CONFIRMED, "This upload is not a confirmed restore.", f"status={upload.status}")

    snapshot = upload.confirmed_snapshot
    if (
        not isinstance(snapshot, dict)
        or snapshot.get('snapshot_version') != SNAPSHOT_VERSION
        or not snapshot.get('digest')
    ):
        return _refuse(
            user, upload.id, BAD_SNAPSHOT,
            "This upload's confirmation record is not one this system can apply. Cancel it and upload the archive again.",
        )

    preview = restore_preview.build_preview(upload)

    missing = [i['slug'] for i in preview['institutions'] if not i['exists']]
    if missing:
        return _refuse(
            user, upload.id, INSTITUTION_MISSING,
            "These institutions named by the archive no longer exist on this system: "
            + ", ".join(_clip(slug, 60) for slug in missing) + ". A restore never creates institutions.",
        )
    date_scoped_problem = _date_scoped_problem(preview, snapshot)
    if date_scoped_problem:
        return _refuse(user, upload.id, DATE_SCOPED, date_scoped_problem)
    if not hmac.compare_digest(str(snapshot['digest']).encode('utf-8'), preview['digest'].encode('ascii')):
        return _refuse(
            user, upload.id, DIGEST_CHANGED,
            "What this restore would do no longer matches what you confirmed (the archive or the "
            "institutions changed). Cancel it and review the archive again.",
        )
    scope_type = preview['scope_type']
    institutions = list(Institution.objects.filter(slug__in=[i['slug'] for i in preview['institutions']]))
    if not institutions or (scope_type == BackupJobScopeType.SINGLE and len(institutions) != 1):
        return _refuse(
            user, upload.id, BAD_SNAPSHOT,
            "The archive's scope does not match the institutions it names. Cancel it and upload the archive again.",
        )
    problem = restore_preview._staged_archive_problem(upload)
    if problem:
        return _refuse(user, upload.id, ARCHIVE_PROBLEM, problem)

    system_wide = scope_type == BackupJobScopeType.SYSTEM
    if system_wide:
        scope_arg, institutions = None, []
    elif scope_type == BackupJobScopeType.MULTI:
        scope_arg = institutions
    else:
        scope_arg = institutions[0]

    try:
        sufficient, estimated, required, free = has_sufficient_restore_disk(scope_arg, system_wide, upload.size_bytes)
    except OSError:
        logger.exception("Restore start: disk-space check raised for upload=%s", upload.id)
        return _refuse(
            user, upload.id, DISK_UNKNOWN,
            "Could not verify available disk space. Please try again or contact support.",
        )
    if not sufficient:
        return _refuse(
            user, upload.id, DISK_TOO_SMALL,
            "Not enough free disk space to safely run this restore (it must first snapshot the current "
            "data). Please contact your system administrator.",
            f"free={free} required={required} estimated={estimated}",
        )

    with transaction.atomic():
        locked = RestoreUpload.objects.select_for_update().filter(
            pk=upload.pk, uploaded_by=user, status=RestoreUploadStatus.CONFIRMED,
        ).first()
        if locked is None:
            return _refuse(user, upload.id, NOT_CONFIRMED, "This upload is not a confirmed restore.", "lost race")
        job = create_job_unless_overlapping(
            scope_type, institutions,
            job_type=BackupJobType.RESTORE,
            status=BackupJobStatus.PENDING,
            trigger_institution=trigger_institution,
            triggered_by=user,
            restore_upload=locked,
        )
        if job is None:
            return _refuse(
                user, upload.id, LOCK_CONFLICT,
                "A backup or restore overlapping this scope is already pending or running. "
                "Please wait for it to finish, then start the restore again.",
            )
        locked.status = RestoreUploadStatus.APPLYING
        locked.last_edit_by = user
        locked.save(update_fields=['status', 'last_edit_by', 'updated_at'])

    security_logger.info(
        "Restore started: user=%s upload=%s job=%s digest=%s", user.username, upload.id, job.id, snapshot['digest'],
    )
    return StartOutcome(True, job=job)


def revert_upload_to_confirmed(upload):
    """Put an `applying` upload back to `confirmed` (the data is unchanged, so
    it can be retried or cancelled). If it cannot legitimately go back to
    `confirmed` (its `confirmed_at`/`confirmed_snapshot` are missing or
    invalid -- should not happen, but `check_upload_ready` alone does not
    guarantee it here), it is marked `failed` instead, mirroring
    `views._mark_upload_failed`'s pattern: a real, user-presentable
    `error_message` is recorded and the staged archive is deleted, since
    `restore_status_partial.html`'s `failed` branch unconditionally states
    that the uploaded file has been removed. Any other status is left alone."""
    try:
        upload.refresh_from_db()
        if upload.status != RestoreUploadStatus.APPLYING:
            return
        if upload.confirmed_at is not None and isinstance(upload.confirmed_snapshot, dict):
            upload.status = RestoreUploadStatus.CONFIRMED
            upload.save(update_fields=['status', 'updated_at'])
            return
        upload.status = RestoreUploadStatus.FAILED
        upload.error_message = (
            "The restore failed and this upload's confirmation record is missing or invalid, so it "
            "could not be returned to 'confirmed' for a retry. Upload the archive again."
        )
        upload.save(update_fields=['status', 'error_message', 'updated_at'])
        try:
            restore_validation.delete_staged_archive(upload)
        except OSError:
            logger.exception(
                "RestoreUpload %s: could not delete the staged archive after marking it failed.", upload.id,
            )
    except Exception:
        logger.exception("RestoreUpload %s: could not return it to 'confirmed'.", getattr(upload, 'id', None))


def mark_applied(upload):
    """The restore committed: the upload is `applied` and its staged archive
    (never its directory: the running command's log is open in it) is removed."""
    try:
        upload.refresh_from_db()
        upload.status = RestoreUploadStatus.APPLIED
        upload.save(update_fields=['status', 'updated_at'])
    except Exception:
        logger.exception("RestoreUpload %s: could not mark it 'applied'.", getattr(upload, 'id', None))
    try:
        restore_validation.delete_staged_archive(upload)
    except OSError:
        logger.exception("RestoreUpload %s: could not delete the staged archive.", getattr(upload, 'id', None))


def abort_start(job, upload, message):
    """The `run_restore` process could not be launched: fail the job and give
    the upload back to the user as `confirmed`."""
    job.status = BackupJobStatus.FAILED
    job.error_message = message
    job.save(update_fields=['status', 'error_message', 'updated_at'])
    revert_upload_to_confirmed(upload)


# --------------------------------------------------------------------------
# Step 1-2: readiness and re-verification
# --------------------------------------------------------------------------

def check_upload_ready(upload):
    """Step 1: the upload must be `applying` with a version-1 confirmation."""
    snapshot = upload.confirmed_snapshot
    if (
        upload.status != RestoreUploadStatus.APPLYING
        or not isinstance(snapshot, dict)
        or snapshot.get('snapshot_version') != SNAPSHOT_VERSION
        or not snapshot.get('digest')
    ):
        raise RestoreError(
            "The upload is not in the 'applying' state with a version-1 confirmation record, so it cannot be applied."
        )


def _hash_file(path, progress=None):
    """Streamed SHA-256 of `path` (never a whole-file read); `progress` gets a 0..1 fraction."""
    size = path.stat().st_size
    hasher = hashlib.sha256()
    done = 0
    with open(path, 'rb') as f:
        while chunk := f.read(COPY_CHUNK_SIZE):
            hasher.update(chunk)
            done += len(chunk)
            if progress and size:
                progress(done / size)
    return hasher.hexdigest()


def verify_confirmed(upload, progress=None):
    """
    Step 2: re-check what was confirmed. Re-hashes the whole staged archive
    against `archive_sha256` (Story 2.1's deferred precondition: nothing pinned
    the bytes between validation and use), rebuilds the preview facts and
    requires their digest to equal the confirmed digest. Raises `RestoreError`.
    """
    path = restore_validation.get_upload_path(upload)
    try:
        actual = _hash_file(path, progress)
    except OSError as e:
        raise RestoreError(f"The staged archive could not be read ({_clip(e, 200)}).")
    if actual != upload.archive_sha256.lower():
        raise RestoreError(
            "The staged archive no longer matches the file that was validated (its SHA-256 changed). "
            "Cancel this restore and upload the archive again."
        )

    preview = restore_preview.build_preview(upload)
    missing = [i['slug'] for i in preview['institutions'] if not i['exists']]
    if missing:
        raise RestoreError(
            "These institutions named by the archive no longer exist on this system: "
            + ", ".join(_clip(slug, 60) for slug in missing) + "."
        )
    date_scoped_problem = _date_scoped_problem(preview, upload.confirmed_snapshot)
    if date_scoped_problem:
        raise RestoreError(date_scoped_problem)
    if not hmac.compare_digest(
        str(upload.confirmed_snapshot['digest']).encode('utf-8'), preview['digest'].encode('ascii'),
    ):
        raise RestoreError(
            "What this restore would do no longer matches what was confirmed (the preview digest changed)."
        )


# --------------------------------------------------------------------------
# Step 3: the pre-restore snapshot
# --------------------------------------------------------------------------

def take_snapshot(job, progress=None):
    """
    Step 3 (AC a): a full-scope, undated snapshot of the current data for the
    restore's own scope, run in-process through `create_export` as its own
    `pre_restore_snapshot` job (created without the job lock: the restore
    job's lock covers it) and linked from `job.pre_restore_snapshot`. Raises
    `RestoreError` if it fails -- nothing has been touched. Returns
    `(snapshot_job, skipped_media)`.
    """
    snapshot = BackupJob.objects.create(
        job_type=BackupJobType.PRE_RESTORE_SNAPSHOT,
        status=BackupJobStatus.PENDING,
        scope_type=job.scope_type,
        scope=job.scope,
        trigger_institution=job.trigger_institution,
        triggered_by=job.triggered_by,
    )
    if job.scope_type == BackupJobScopeType.MULTI:
        snapshot.scopes.set(job.scopes.all())
    job.pre_restore_snapshot = snapshot
    job.save(update_fields=['pre_restore_snapshot', 'updated_at'])

    snapshot.status = BackupJobStatus.RUNNING
    snapshot.save(update_fields=['status', 'updated_at'])

    def _on_progress(pct):
        try:
            snapshot.progress_pct = min(max(pct, 0), 99)
            snapshot.save(update_fields=['progress_pct', 'updated_at'])
        except Exception:
            logger.exception("Pre-restore snapshot %s: failed to persist progress update.", snapshot.id)
        if progress:
            progress(min(max(pct, 0), 99) / 100)

    try:
        archive_path, skipped_media, archive_checksum = create_export(snapshot, progress_callback=_on_progress)
        if not archive_path.exists():
            raise RestoreError("the snapshot archive is not on disk")
    except Exception as e:
        logger.exception("Pre-restore snapshot %s failed.", snapshot.id)
        get_archive_path(snapshot).unlink(missing_ok=True)
        snapshot.status = BackupJobStatus.FAILED
        snapshot.progress_pct = 0
        snapshot.error_message = f"Snapshot export failed: {e}"
        snapshot.save(update_fields=['status', 'progress_pct', 'error_message', 'updated_at'])
        raise RestoreError(
            f"The pre-restore snapshot (job {snapshot.id}) failed, so nothing was changed: {_clip(e, 200)}",
            audit_message=(
                f"The pre-restore snapshot (job {snapshot.id}) failed, so nothing was changed ({type(e).__name__})."
            ),
        )

    snapshot.status = BackupJobStatus.COMPLETED
    snapshot.progress_pct = 100
    snapshot.archive_checksum = archive_checksum
    snapshot.error_message = (
        "Completed with {} media file(s) skipped: {}".format(len(skipped_media), "; ".join(skipped_media))
        if skipped_media else ""
    )
    snapshot.save(update_fields=['status', 'progress_pct', 'archive_checksum', 'error_message', 'updated_at'])
    return snapshot, skipped_media


# --------------------------------------------------------------------------
# db_export.json streaming reader
# --------------------------------------------------------------------------
# `START`, `ExportFormatError` and `ExportReader` moved to `backup/export_stream`
# in Story 2.4 so `restore_validation`'s Stage 6 and this module import one
# implementation. `iter_export_records` stays here as a thin wrapper keeping
# this module's own default (referral keys skipped) for its existing callers.

def iter_export_records(stream, skip_keys=REFERRAL_MODEL_KEYS):
    """`ExportReader` over `stream` (referral keys skipped by default)."""
    return ExportReader(stream, skip_keys=skip_keys)


def _open_export(zf):
    try:
        return zf.getinfo(restore_validation.DB_EXPORT_NAME)
    except KeyError:
        raise ExportFormatError("The archive has no db_export.json.")


def _check_record_shape(key, record):
    label = restore_preview.model_label(key)
    if not isinstance(record, dict):
        raise ExportFormatError(f"A {label} record in db_export.json is not an object.")
    pk = record.get('pk')
    if isinstance(pk, bool) or not isinstance(pk, int):
        raise ExportFormatError(f"A {label} record in db_export.json has no integer primary key.")
    if record.get('model') != key:
        raise ExportFormatError(
            f"{label} {pk} in db_export.json is labelled as model '{_clip(record.get('model'), 60)}'."
        )
    if not isinstance(record.get('fields'), dict):
        raise ExportFormatError(f"{label} {pk} in db_export.json has no field values.")


# --------------------------------------------------------------------------
# Step 4: preflight (read-only)
# --------------------------------------------------------------------------

def preflight(upload, job, progress=None):
    """
    Step 4: stream `db_export.json` once and reject the restore, with a
    specific message, if the archive could not be applied safely. Reads and
    writes nothing but the archive and read-only queries. `progress` gets a
    0..1 fraction. Returns a `PreflightResult` (records per model).

    NOTE -- accepted deviation: `_load_records` (step 5) streams
    `db_export.json` again later, so this file is read twice per restore
    (module docstring has the full explanation the user signed off on: it is
    JSON metadata, not the archive's much larger `media/` payload).
    """
    plan = _restore_plan(job)
    target_ids, allow_null_institution = _target_institution_ids(upload, job)
    m2m_fields = {
        key: [(f.name, f.related_model) for f in apps.get_model(key)._meta.many_to_many]
        for key in RESTORE_MODEL_KEYS
    }
    known_refs = {}  # related model -> ids known to exist
    identifiers_seen = {name: set() for name in PATIENT_IDENTIFIER_FIELDS}
    counts = {key: 0 for key in RESTORE_MODEL_KEYS}

    state = {'key': None, 'seen_pks': set(), 'batch': []}

    def _flush():
        batch = state['batch']
        if batch:
            _check_batch(state['key'], batch, plan, m2m_fields, known_refs)
            state['batch'] = []

    with zipfile.ZipFile(restore_validation.get_upload_path(upload)) as zf:
        info = _open_export(zf)
        with zf.open(info) as stream:
            reader = iter_export_records(stream)
            last_index = -1
            for key, record in reader:
                if record is START:
                    _flush()
                    if key not in EXPORT_MODEL_KEYS:
                        raise ExportFormatError(f"db_export.json has an unknown model key ('{_clip(key, 60)}').")
                    index = EXPORT_MODEL_KEYS.index(key)
                    if index <= last_index:
                        raise ExportFormatError(
                            f"db_export.json lists '{key}' out of order (or more than once); "
                            "the models must follow the export's fixed order."
                        )
                    last_index = index
                    state['key'] = key
                    state['seen_pks'] = set()
                    if progress and info.file_size:
                        progress(reader.bytes_read / info.file_size)
                    continue

                _check_record_shape(key, record)
                label = restore_preview.model_label(key)
                pk = record['pk']
                if pk in state['seen_pks']:
                    raise ExportFormatError(f"{label} {pk} appears more than once in db_export.json.")
                state['seen_pks'].add(pk)

                if key == PATIENT_KEY:
                    _check_patient_record(record, target_ids, allow_null_institution, identifiers_seen)
                counts[key] += 1
                state['batch'].append(record)
                if len(state['batch']) >= LOOKUP_BATCH_SIZE:
                    _flush()
                    if progress and info.file_size:
                        progress(reader.bytes_read / info.file_size)
            _flush()

    if progress:
        progress(1.0)
    return PreflightResult(counts=counts)


def _check_patient_record(record, target_ids, allow_null_institution, identifiers_seen):
    pk = record['pk']
    institution_id = record['fields'].get('institution')
    if institution_id is None:
        if not allow_null_institution:
            raise ExportFormatError(f"Patient {pk} in the archive has no institution.")
    elif isinstance(institution_id, bool) or institution_id not in target_ids:
        raise ExportFormatError(
            f"Patient {pk} in the archive belongs to institution id {_clip(institution_id, 20)}, which is not one "
            "of the institutions being restored. Archives made on a different system (with different "
            "institution ids) cannot be restored yet."
        )
    for name, seen in identifiers_seen.items():
        value = record['fields'].get(name)
        if isinstance(value, str) and value:
            if value in seen:
                raise ExportFormatError(
                    f"The patient identifier {name} '{_clip(value, 40)}' appears on more than one patient in the archive.",
                    audit_message=f"The patient identifier {name} appears on more than one patient in the archive.",
                )
            seen.add(value)


def _check_batch(key, batch, plan, m2m_fields, known_refs):
    """The database-facing preflight checks for one batch of `key`'s records."""
    model = apps.get_model(key)
    label = restore_preview.model_label(key)

    # A primary key that already exists outside the rows about to be deleted
    # (e.g. a patient moved to another institution since the backup) would
    # clash with the load.
    pks = [record['pk'] for record in batch]
    existing = set(model._base_manager.filter(pk__in=pks).values_list('pk', flat=True))
    if existing:
        in_scope = set(plan[key].filter(pk__in=existing).values_list('pk', flat=True))
        outside = existing - in_scope
        if outside:
            raise ExportFormatError(
                f"{label} {min(outside)} in the archive already exists on this system outside the scope "
                "being restored (it may have been moved to another institution since the backup)."
            )

    if key == PATIENT_KEY:
        Patient = model
        for name in PATIENT_IDENTIFIER_FIELDS:
            values = {
                record['fields'].get(name) for record in batch
                if isinstance(record['fields'].get(name), str) and record['fields'].get(name)
            }
            if not values:
                continue
            clash = (
                Patient._base_manager.filter(**{f'{name}__in': values})
                .exclude(pk__in=plan[PATIENT_KEY].values('pk'))
                .values_list(name, flat=True).first()
            )
            if clash is not None:
                raise ExportFormatError(
                    f"The patient identifier {name} '{_clip(clash, 40)}' in the archive already belongs to a "
                    "patient on this system outside the scope being restored.",
                    audit_message=(
                        f"A patient identifier ({name}) in the archive already belongs to a "
                        "patient on this system outside the scope being restored."
                    ),
                )

    for name, related in m2m_fields[key]:
        wanted = set()
        for record in batch:
            values = record['fields'].get(name, [])
            if not isinstance(values, list) or any(isinstance(v, bool) or not isinstance(v, int) for v in values):
                raise ExportFormatError(f"{label} {record['pk']} has a malformed '{name}' list in the archive.")
            wanted.update(values)
        known = known_refs.setdefault(related, set())
        unknown = wanted - known
        if unknown:
            found = set(related._base_manager.filter(pk__in=unknown).values_list('pk', flat=True))
            known |= found
            missing = unknown - found
            if missing:
                raise ExportFormatError(
                    f"The archive's {label} records refer to {related.__name__} {min(missing)}, which does not "
                    "exist on this system."
                )


# --------------------------------------------------------------------------
# Step 5: apply (one transaction)
# --------------------------------------------------------------------------

class _UserResolver:
    """Nulls user foreign keys whose user does not exist on this system,
    checking each batch's user ids with one query and remembering the answers."""

    def __init__(self):
        self._User = get_user_model()
        self._exists = set()
        self._missing = set()
        self._fields = {}

    def _user_fields(self, model):
        if model not in self._fields:
            self._fields[model] = [
                f.name for f in model._meta.concrete_fields
                if f.is_relation and f.related_model is self._User
            ]
        return self._fields[model]

    def null_missing(self, model, records):
        names = self._user_fields(model)
        if not names:
            return
        wanted = {
            record['fields'][name] for record in records for name in names
            if record['fields'].get(name) is not None
        }
        # Anything that is not an integer id cannot be a user here.
        wanted = {uid for uid in wanted if isinstance(uid, int) and not isinstance(uid, bool)}
        unknown = wanted - self._exists - self._missing
        if unknown:
            found = set(self._User._base_manager.filter(pk__in=unknown).values_list('pk', flat=True))
            self._exists |= found
            self._missing |= unknown - found
        for record in records:
            for name in names:
                uid = record['fields'].get(name)
                if uid is not None and uid not in self._exists:
                    record['fields'][name] = None


def _delete_scope(plan):
    """Delete the scope's rows for the ten models in reverse load order with
    `_raw_delete`: no cascade into rows that belong elsewhere (`PatientMoveLog`,
    `ReferralSent`), no signals, and no `django_cleanup` file deletion. The
    many-to-many through rows, which the cascade would have removed, go
    explicitly."""
    for key in reversed(RESTORE_MODEL_KEYS):
        queryset = plan[key]
        model = queryset.model
        for m2m in model._meta.local_many_to_many:
            through = m2m.remote_field.through
            if through._meta.auto_created:
                through._base_manager.filter(
                    **{f'{m2m.m2m_field_name()}__in': queryset.values('pk')}
                )._raw_delete(queryset.db)
        queryset._raw_delete(queryset.db)


def _load_records(upload):
    """Stream the archive's records into the database, in forward order, in
    batches, keeping their primary keys and (via `save_base(raw=True)`) their
    `created_at`/`updated_at`. Returns the number of records loaded."""
    users = _UserResolver()
    loaded = 0
    state = {'key': None, 'batch': []}

    def _flush():
        nonlocal loaded
        batch = state['batch']
        if not batch:
            return
        key = state['key']
        model = apps.get_model(key)
        users.null_missing(model, batch)
        for obj in serializers.deserialize('python', batch):
            # The scope's rows are gone, so every row is a new INSERT; forcing
            # it means an unexpected pk clash fails instead of overwriting.
            obj.save(force_insert=True)
        loaded += len(batch)
        state['batch'] = []

    with zipfile.ZipFile(restore_validation.get_upload_path(upload)) as zf:
        info = _open_export(zf)
        with zf.open(info) as stream:
            for key, record in iter_export_records(stream):
                if record is START:
                    _flush()
                    state['key'] = key
                    continue
                _check_record_shape(key, record)
                state['batch'].append(record)
                if len(state['batch']) >= LOAD_BATCH_SIZE:
                    _flush()
            _flush()
    return loaded


def _fix_references():
    """What the cascade/SET_NULL of a real delete would have done for patients
    that no longer exist, and nothing else. Returns `(referrals_nulled, move_logs_removed)`."""
    Patient = apps.get_model('patients', 'Patient')
    ReferralSent = apps.get_model('referral', 'ReferralSent')
    PatientMoveLog = apps.get_model('institution', 'PatientMoveLog')

    live_patients = Patient._base_manager.values('pk')
    nulled = (
        ReferralSent._base_manager.filter(patient__isnull=False)
        .exclude(patient__in=live_patients)
        .update(patient=None)
    )
    orphaned_logs = PatientMoveLog._base_manager.exclude(patient__in=live_patients)
    removed = orphaned_logs._raw_delete(orphaned_logs.db)
    return nulled, removed


def _check_constraints_table_names():
    """
    `db_table` names for `connection.check_constraints()` in `apply_restore`:
    the ten restored models (an archive's own record could reference another
    restored model whose row turns out to be missing) plus the two tables
    outside the restored set that hold a foreign key into it --
    `referral.ReferralSent.patient` and `institution.PatientMoveLog.patient`.
    Per the Code Map's reference facts, every OTHER inbound foreign key to
    the ten models is a non-null CASCADE *inside* the restored set, so it can
    only ever dangle within it -- these two are the only foreign keys from
    outside that set, and `_fix_references` already repairs them explicitly.
    Scoping the check to just these tables (instead of a full-database scan)
    keeps the destructive transaction's write lock shorter.
    """
    tables = {apps.get_model(key)._meta.db_table for key in RESTORE_MODEL_KEYS}
    tables.add(apps.get_model('referral', 'ReferralSent')._meta.db_table)
    tables.add(apps.get_model('institution', 'PatientMoveLog')._meta.db_table)
    return sorted(tables)


def _reset_sequences():
    """PostgreSQL keeps its own sequences, which explicit-pk inserts do not
    advance; SQLite's `sequence_reset_sql` is empty."""
    models = [apps.get_model(key) for key in RESTORE_MODEL_KEYS]
    statements = connection.ops.sequence_reset_sql(no_style(), models)
    if statements:
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)


def apply_restore(upload, job):
    """
    Step 5 (AC b): delete the scope's rows and load the archive's, all in ONE
    `transaction.atomic()`. Any failure -- a bad record, a constraint, a
    dangling reference found by `connection.check_constraints()` (called
    inside the block so it fails here and not at commit) -- rolls everything
    back and raises `RestoreError`: the data is exactly as before. Returns
    `(records_loaded, referrals_nulled, move_logs_removed)`.
    """
    plan = _restore_plan(job)
    try:
        with transaction.atomic():
            _delete_scope(plan)
            loaded = _load_records(upload)
            nulled, removed = _fix_references()
            connection.check_constraints(table_names=_check_constraints_table_names())
            _reset_sequences()
    except (RestoreError, ExportFormatError):
        raise
    except Exception as e:
        logger.exception("RestoreUpload %s: applying the archive failed and was rolled back.", upload.id)
        raise RestoreError(
            f"Applying the archive failed and was rolled back, so no data was changed: {_clip(e, 200)}",
            audit_message=(
                f"Applying the archive failed and was rolled back, so no data was changed ({type(e).__name__})."
            ),
        )
    return loaded, nulled, removed


# --------------------------------------------------------------------------
# Step 6: media (after commit only)
# --------------------------------------------------------------------------

def _manifest_checksums(zf):
    try:
        manifest = json.loads(zf.read(restore_validation.MANIFEST_NAME).decode('utf-8'))
        checksums = manifest['checksums']
        return checksums if isinstance(checksums, dict) else {}
    except (KeyError, TypeError, *restore_validation._ZIP_READ_ERRORS):
        return {}


def _restore_one_media(zf, checksums, name):
    """Copy `media/<name>` from the archive to `MEDIA_ROOT/<name>`. Returns a
    short warning, or None on success. The path is confined to MEDIA_ROOT, the
    bytes go to a temp file whose SHA-256 must equal the manifest's, and only
    then is it `os.replace`d into place (overwriting any existing file)."""
    name = str(name)
    arcname = f"{restore_validation.MEDIA_PREFIX}{name}"
    try:
        info = zf.getinfo(arcname)
    except KeyError:
        return f"{_clip(name, 100)}: missing from the archive"
    expected = checksums.get(arcname)
    if not isinstance(expected, str):
        return f"{_clip(name, 100)}: not listed in the archive's manifest"
    if info.file_size > MEDIA_MEMBER_SIZE_CEILING:
        return (
            f"{_clip(name, 100)}: declared size ({info.file_size} bytes) exceeds the "
            f"{MEDIA_MEMBER_SIZE_CEILING}-byte per-file limit"
        )
    try:
        target = safe_join(settings.MEDIA_ROOT, name)
    except (SuspiciousFileOperation, ValueError):
        return f"{_clip(name, 100)}: path is outside the media folder"

    temp_path = None
    try:
        target_dir = os.path.dirname(target)
        os.makedirs(target_dir, exist_ok=True)
        temp_path = os.path.join(target_dir, f".{uuid.uuid4().hex}.restore.tmp")
        hasher = hashlib.sha256()
        with zf.open(info) as src, open(temp_path, 'xb') as dest:
            while chunk := src.read(COPY_CHUNK_SIZE):
                hasher.update(chunk)
                dest.write(chunk)
        if hasher.hexdigest() != expected.lower():
            return f"{_clip(name, 100)}: checksum mismatch"
        os.replace(temp_path, target)
        temp_path = None
    except (OSError, ValueError, *restore_validation._ZIP_READ_ERRORS) as e:
        return f"{_clip(name, 100)}: could not be written ({_clip(e, 80)})"
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    return None


def restore_media(upload, job, progress=None):
    """
    Step 6: after the database commit, copy the archive's media for every
    restored `Video.video_file` / `Attachment.attachment` into `MEDIA_ROOT`.
    The database is already restored, so nothing here can fail the restore:
    every problem becomes an entry in the returned list of warnings. Files of
    deleted rows that the archive does not contain are never deleted.
    """
    warnings = []
    try:
        plan = _restore_plan(job)
        total = sum(plan[key].count() for key, _field in MEDIA_FIELDS)
        done = 0
        with zipfile.ZipFile(restore_validation.get_upload_path(upload)) as zf:
            checksums = _manifest_checksums(zf)
            for key, file_field in MEDIA_FIELDS:
                names = (
                    plan[key].exclude(**{file_field: ''}).exclude(**{f'{file_field}__isnull': True})
                    .values_list(file_field, flat=True)
                )
                for name in names.iterator():
                    warning = _restore_one_media(zf, checksums, name)
                    if warning:
                        warnings.append(warning)
                    done += 1
                    if progress and total:
                        progress(done / total)
    except Exception as e:
        logger.exception("RestoreUpload %s: media restore stopped early.", upload.id)
        warnings.append(f"the media restore stopped early ({_clip(e, 100)})")
    return warnings


def format_media_warnings(warnings):
    shown = "; ".join(warnings[:MAX_LISTED_WARNINGS])
    if len(warnings) > MAX_LISTED_WARNINGS:
        shown += f"; ... and {len(warnings) - MAX_LISTED_WARNINGS} more"
    return f"Restored with {len(warnings)} warning(s): {shown}"


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def execute_restore(job, progress_callback=None):
    """
    Run steps 1-6 for the `restore` `job` (the upload is `job.restore_upload`).
    `progress_callback(pct)` is called with a monotonic 0..99 value. Raises
    `RestoreError` (or `ExportFormatError` when `db_export.json` is malformed
    or holds records this restore refuses) on any failure; before
    `apply_restore` that changes no domain data, and `apply_restore` rolls
    back on its own. The caller writes
    the terminal states. Returns a `RestoreResult`.
    """
    progress = Progress(progress_callback)
    upload = RestoreUpload.objects.filter(pk=job.restore_upload_id).first()
    if upload is None:
        raise RestoreError("The restore job's upload no longer exists.")

    check_upload_ready(upload)
    if is_date_scoped(upload.confirmed_snapshot):
        # Story 2.5: `verify_confirmed` now accepts a date-scoped upload, and this
        # path REPLACES the scope's rows: it must never be reached for one.
        raise RestoreError(
            "This archive is date-scoped and must be applied by the additive import, not a full-scope restore."
        )
    verify_confirmed(upload, progress.span(*REHASH_RANGE))
    progress.report(REHASH_RANGE[1])

    snapshot, snapshot_skipped = take_snapshot(job, progress.span(*SNAPSHOT_RANGE))
    progress.report(SNAPSHOT_RANGE[1])

    counts = preflight(upload, job, progress.span(*PREFLIGHT_RANGE)).counts
    progress.report(PREFLIGHT_RANGE[1])

    progress.report(APPLY_START)
    loaded, nulled, removed = apply_restore(upload, job)
    progress.report(APPLY_DONE)
    logger.info(
        "RestoreUpload %s applied by job %s: %s records loaded, %s referral patient link(s) cleared, "
        "%s move log(s) removed.", upload.id, job.id, loaded, nulled, removed,
    )

    warnings = restore_media(upload, job, progress.span(*MEDIA_RANGE))
    if snapshot_skipped:
        warnings.append(
            f"the pre-restore snapshot (job {snapshot.id}) skipped {len(snapshot_skipped)} media file(s)"
        )
    return RestoreResult(
        snapshot=snapshot, warnings=warnings, counts=counts,
        referral_links_cleared=nulled, move_logs_removed=removed,
    )
