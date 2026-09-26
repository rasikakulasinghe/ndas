"""
Date-scoped (partial) restore -- Story 2.5: the additive import.

A confirmed date-scoped archive (Story 2.4) carries a locked-in
skip/import/excluded partition in `confirmed_snapshot['date_scope_match']`.
`execute_import(job, progress_callback)` applies ONLY the import-set:

  1. upload ready and version-1 snapshot (`restore_apply.check_upload_ready`);
  2. the whole staged archive re-hashed and the preview digest re-checked
     (`restore_apply.verify_confirmed`);
  3. the same full-scope, undated pre-restore snapshot of the target
     institution as Story 2.3 (`restore_apply.take_snapshot`, unchanged);
  4. the import: `db_export.json` is streamed once and the import-set's records
     are regrouped by patient in a temporary on-disk spool (never in memory);
     then, for each import-set patient in archive order, ONE
     `transaction.atomic()` inserts the patient and its children with fresh
     primary keys and remapped foreign keys, and only after it commits are that
     patient's media files copied (never over an existing file).

Existing data is never updated, merged, overwritten or deleted. The partition
is read from the confirmed snapshot and nowhere else (no re-matching).
Skip-set, excluded, unknown and referral records are dropped while streaming:
never written to the database, never extracted.

Outcome: at least one patient committed -> the run is a success (with warnings
when a patient failed, a media file did not copy, or an unexpected error made
the import stop early: `aborted`); nothing committed and at least one patient
failed, or an unexpected error before any commit -> `RestoreError` (data
unchanged). Once a patient has committed the upload never goes back to
`confirmed`: its stored partition is stale, a retry is a re-upload.

Failure reasons shown to the user are mapped, value-free texts; the full
exception text only ever goes to the server log.
"""
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import uuid
import zipfile
from dataclasses import dataclass, field

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.exceptions import ObjectDoesNotExist, SuspiciousFileOperation, ValidationError
from django.core.serializers.base import DeserializationError
from django.db import DataError, IntegrityError, connection, transaction
from django.utils._os import safe_join

from backup import restore_apply, restore_validation
from backup.export_stream import START, ExportFormatError, iter_export_records
from backup.models import RestoreUpload
from backup.restore_apply import (
    MAX_LISTED_WARNINGS,
    MEDIA_FIELDS,
    MEDIA_MEMBER_SIZE_CEILING,
    PATIENT_IDENTIFIER_FIELDS,
    PATIENT_KEY,
    REHASH_RANGE,
    RESTORE_MODEL_KEYS,
    SNAPSHOT_RANGE,
    Progress,
    RestoreError,
)
from backup.restore_preview import EXPORT_MODEL_KEYS, REFERRAL_MODEL_KEYS, model_label
from backup.services import COPY_CHUNK_SIZE

logger = logging.getLogger(__name__)
security_logger = restore_validation.security_logger   # 'django.security.restore'
_clip = restore_validation._clip

VIDEO_KEY = 'video.video'
GM_KEY = 'patients.gmassessment'
PROBLEM_KEY = 'problemlist.problem'
PROBLEM_ACTION_KEY = 'problemlist.problemaction'

SPOOL_RANGE = (50, 60)
IMPORT_RANGE = (60, 99)

SPOOL_BATCH_SIZE = 500          # records written to the spool per insert
FAILURE_REASON_MAX = 300        # characters kept of one patient's failure reason
FRESH_NAME_ATTEMPTS = 20        # tries to find an unused media file name
MODE_DATE_SCOPED = 'date_scoped'

# Mapped, value-free texts: no database message and no patient value ever
# reaches `restore_result`, the job message, the notification or the status page.
REASON_CONSTRAINT = "a unique or reference constraint failed (for example a patient identifier already exists here)"
REASON_INVALID = "the archived record is not valid for this system"

# The only errors that are about ONE patient's data. Anything else (a lost
# database connection, a full disk, an out-of-memory...) is an environment
# error: it aborts the run instead of failing every remaining patient.
DATA_ERRORS = (
    IntegrityError, DataError, ValidationError, ObjectDoesNotExist, DeserializationError,
    ValueError, TypeError, KeyError,
)


class ImportFailure(Exception):
    """One patient could not be imported; that patient's transaction rolled back.
    `reason` is user-presentable and value-free; `detail` (server log only) may
    hold the original exception text."""

    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _failure_reason(error):
    """The user-presentable, value-free reason for a data error."""
    if isinstance(error, ImportFailure):
        return error.reason
    if isinstance(error, IntegrityError):
        return REASON_CONSTRAINT
    return REASON_INVALID


@dataclass
class ImportResult:
    snapshot: object
    summary: dict                                # the job's `restore_result`
    warnings: list = field(default_factory=list)  # user-presentable, for the job message
    message: str = ''                             # '' when nothing needs the user's attention


# --------------------------------------------------------------------------
# Confirmed partition and target institution
# --------------------------------------------------------------------------

def _read_partition(upload):
    """`(match, import_pks)` from `confirmed_snapshot['date_scope_match']` and
    nothing else. Raises `RestoreError` when it is not a well-formed partition."""
    snapshot = upload.confirmed_snapshot if isinstance(upload.confirmed_snapshot, dict) else {}
    match = snapshot.get('date_scope_match')
    if not isinstance(match, dict) or not all(isinstance(match.get(part), list) for part in ('skip', 'import', 'excluded')):
        raise RestoreError("The confirmation record holds no usable date-scoped match, so nothing can be imported.")
    for part in ('skip', 'import', 'excluded'):
        if not all(isinstance(entry, dict) for entry in match[part]):
            raise RestoreError(f"The confirmed {part} list holds an entry that is not a record.")
    import_pks = []
    for entry in match['import']:
        pk = entry.get('archive_pk')
        if isinstance(pk, bool) or not isinstance(pk, int):
            raise RestoreError("The confirmed import list holds an entry without an integer archive patient id.")
        import_pks.append(pk)
    if len(set(import_pks)) != len(import_pks):
        raise RestoreError("The confirmed import list names the same archive patient more than once.")
    elsewhere = {
        entry.get('archive_pk') for part in ('skip', 'excluded') for entry in match[part]
    }
    if elsewhere.intersection(import_pks):
        raise RestoreError(
            "The confirmed partition lists an archive patient to import that is also skipped or excluded."
        )
    return match, import_pks


def _identifiers_by_pk(match):
    """`{archive pk: identifiers}` from the confirmed import entries (Story 2.4
    stores each patient's identifiers there), for naming failed patients."""
    result = {}
    for entry in match['import']:
        identifiers = entry.get('identifiers')
        # Only the five known identifier names: the dict is rendered on the
        # status page, so an unknown key (for example "items") must not pass.
        result[entry['archive_pk']] = (
            {
                name: _clip(identifiers[name], 80) for name in PATIENT_IDENTIFIER_FIELDS
                if identifiers.get(name) not in (None, '')
            }
            if isinstance(identifiers, dict) else {}
        )
    return result


def _resolve_target(job, match):
    """The target institution, re-resolved by its slug; its id must equal the
    snapshot's `target_institution_id` (and the job's scope), else `RestoreError`
    -- before any patient is touched."""
    Institution = apps.get_model('institution', 'Institution')
    slug = match.get('institution_slug')
    target = Institution.objects.filter(slug=slug).first() if isinstance(slug, str) and slug else None
    if target is None:
        raise RestoreError("The archive's institution no longer exists on this system, so nothing was imported.")
    expected = match.get('target_institution_id')
    if isinstance(expected, bool) or not isinstance(expected, int) or target.id != expected or job.scope_id != target.id:
        raise RestoreError(
            "The archive's institution is no longer the institution that was confirmed (its id changed), "
            "so nothing was imported. Cancel this restore and upload the archive again."
        )
    return target


# --------------------------------------------------------------------------
# The spool: the import-set's records, regrouped by patient, on disk
# --------------------------------------------------------------------------

class _Spool:
    """A temporary SQLite file (stdlib `sqlite3`, its own connection -- not the
    application database) holding `(patient, model key, record JSON)` in stream
    order. Memory stays bounded: records are inserted in batches and read back
    one patient at a time."""

    def __init__(self, directory):
        self.directory = directory
        self._conn = None
        try:
            os.makedirs(directory, exist_ok=True)
            self._conn = sqlite3.connect(os.path.join(directory, 'spool.sqlite3'))
            self._conn.execute('PRAGMA journal_mode = OFF')
            self._conn.execute('PRAGMA synchronous = OFF')
            self._conn.execute(
                'CREATE TABLE records (seq INTEGER PRIMARY KEY, patient INTEGER NOT NULL, '
                'key TEXT NOT NULL, src INTEGER NOT NULL, body TEXT NOT NULL, UNIQUE (key, src))'
            )
        except BaseException:
            # A half-built spool must not leave a connection or a directory behind.
            self.close()
            raise

    def add_many(self, rows):
        """`rows`: `(patient, model key, source pk, record JSON)`. The same
        `(model key, source pk)` twice is an archive that lists one record
        twice: `ExportFormatError` (it would corrupt the per-patient maps)."""
        try:
            self._conn.executemany('INSERT INTO records (patient, key, src, body) VALUES (?, ?, ?, ?)', rows)
        except sqlite3.IntegrityError:
            raise ExportFormatError(
                "db_export.json lists the same record more than once (a patient to import, or one of "
                "its records, appears twice)."
            )

    def finish(self):
        self._conn.commit()
        self._conn.execute('CREATE INDEX records_patient ON records (patient, seq)')
        self._conn.commit()

    def records_for(self, patient_pk):
        """One patient's `(key, record)` pairs in stream order (a patient's own
        records only: small)."""
        rows = self._conn.execute(
            'SELECT key, body FROM records WHERE patient = ? ORDER BY seq', (patient_pk,)
        ).fetchall()
        return [(key, json.loads(body)) for key, body in rows]

    def close(self):
        try:
            if self._conn is not None:
                self._conn.close()
        except sqlite3.Error:
            pass
        shutil.rmtree(self.directory, ignore_errors=True)


def _int_or_none(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _spool_import_set(upload, import_set, spool, progress=None):
    """Stream `db_export.json` once and route each import-set record to its
    patient: a record's own `patient` (a `ProblemAction`'s `problem`, through
    the problem-to-patient map seen earlier in the stream). Everything else --
    skip-set, excluded, unknown and referral records -- is dropped. Returns the
    number of records spooled."""
    problem_owner = {}   # source problem pk -> archive patient pk (import-set only)
    spooled = 0
    batch = []
    last_index = -1

    with zipfile.ZipFile(restore_validation.get_upload_path(upload)) as zf:
        info = restore_apply._open_export(zf)
        with zf.open(info) as stream:
            reader = iter_export_records(stream, skip_keys=REFERRAL_MODEL_KEYS)
            for key, record in reader:
                if record is START:
                    if key not in EXPORT_MODEL_KEYS:
                        raise ExportFormatError(f"db_export.json has an unknown model key ('{_clip(key, 60)}').")
                    index = EXPORT_MODEL_KEYS.index(key)
                    if index <= last_index:
                        raise ExportFormatError(
                            f"db_export.json lists '{key}' out of order (or more than once); "
                            "the models must follow the export's fixed order."
                        )
                    last_index = index
                    if progress and info.file_size:
                        progress(reader.bytes_read / info.file_size)
                    continue

                restore_apply._check_record_shape(key, record)
                fields = record['fields']
                if key == PATIENT_KEY:
                    owner = record['pk']
                elif key == PROBLEM_ACTION_KEY:
                    owner = problem_owner.get(_int_or_none(fields.get('problem')))
                else:
                    owner = _int_or_none(fields.get('patient'))
                if owner is None or owner not in import_set:
                    continue
                if key == PROBLEM_KEY:
                    problem_owner[record['pk']] = owner
                batch.append((owner, key, record['pk'], json.dumps(record)))
                spooled += 1
                if len(batch) >= SPOOL_BATCH_SIZE:
                    spool.add_many(batch)
                    batch = []
                    if progress and info.file_size:
                        progress(reader.bytes_read / info.file_size)
    if batch:
        spool.add_many(batch)
    spool.finish()
    if progress:
        progress(1.0)
    return spooled


# --------------------------------------------------------------------------
# One patient, one transaction
# --------------------------------------------------------------------------

class _ImportContext:
    """Per-run state shared by every patient's import."""

    def __init__(self, target):
        self.target = target
        self.users = restore_apply._UserResolver()
        self.known_refs = {}   # related model -> ids known to exist here
        self.m2m_fields = {
            key: [(f.name, f.related_model) for f in apps.get_model(key)._meta.many_to_many]
            for key in RESTORE_MODEL_KEYS
        }
        tables = {apps.get_model(key)._meta.db_table for key in RESTORE_MODEL_KEYS}
        for key in RESTORE_MODEL_KEYS:
            for m2m in apps.get_model(key)._meta.local_many_to_many:
                if m2m.remote_field.through._meta.auto_created:
                    tables.add(m2m.remote_field.through._meta.db_table)
        self.check_tables = sorted(tables)


def _check_m2m(ctx, key, record):
    label = model_label(key)
    for name, related in ctx.m2m_fields[key]:
        values = record['fields'].get(name, [])
        if not isinstance(values, list) or any(isinstance(v, bool) or not isinstance(v, int) for v in values):
            raise ImportFailure(f"{label} {record['pk']} has a malformed '{name}' list in the archive.")
        known = ctx.known_refs.setdefault(related, set())
        unknown = set(values) - known
        if unknown:
            found = set(related._base_manager.filter(pk__in=unknown).values_list('pk', flat=True))
            known |= found
            missing = unknown - found
            if missing:
                raise ImportFailure(
                    f"{label} {record['pk']} refers to {related.__name__} {min(missing)}, "
                    "which does not exist on this system."
                )


def _mapped(id_map, value, what):
    mapped = id_map.get(_int_or_none(value))
    if mapped is None:
        raise ImportFailure(what)
    return mapped


def _import_patient(archive_pk, records, ctx):
    """Insert one archive patient and its children in ONE transaction, each row
    with a fresh primary key. Returns the media to copy after the commit:
    `[(model key, file field, new pk, archived file name)]`. Raises
    `ImportFailure` (the transaction rolled back) when this patient's DATA is
    the problem; any other exception (an environment error) propagates after
    the same rollback."""
    id_maps = {PATIENT_KEY: {}, VIDEO_KEY: {}, PROBLEM_KEY: {}}
    media = []
    try:
        with transaction.atomic():
            new_patient_pk = None
            for key, record in records:
                model = apps.get_model(key)
                source_pk = record['pk']
                label = model_label(key)
                fields = dict(record['fields'])
                data = {'model': key, 'pk': None, 'fields': fields}

                if key == PATIENT_KEY:
                    fields['institution'] = ctx.target.pk
                else:
                    if new_patient_pk is None:
                        raise ImportFailure("The patient's own record is not in the archive.")
                    if key == PROBLEM_ACTION_KEY:
                        fields['problem'] = _mapped(
                            id_maps[PROBLEM_KEY], fields.get('problem'),
                            f"{label} {source_pk} refers to a problem that is not this patient's.",
                        )
                    else:
                        fields['patient'] = new_patient_pk
                    if key == GM_KEY:
                        fields['video_file'] = _mapped(
                            id_maps[VIDEO_KEY], fields.get('video_file'),
                            f"{label} {source_pk} refers to a video that is not this patient's.",
                        )

                ctx.users.null_missing(model, [data])
                _check_m2m(ctx, key, data)

                deserialized = next(iter(serializers.deserialize('python', [data])))
                # `save_base(raw=True)`: custom `save()` overrides are bypassed and
                # created_at/updated_at kept; a fresh pk is always an INSERT.
                deserialized.save(force_insert=True)
                new_pk = deserialized.object.pk

                if key in id_maps:
                    id_maps[key][source_pk] = new_pk
                if key == PATIENT_KEY:
                    new_patient_pk = new_pk
                for media_key, file_field in MEDIA_FIELDS:
                    name = fields.get(file_field) if key == media_key else None
                    if isinstance(name, str) and name:
                        media.append((key, file_field, new_pk, name))

            if new_patient_pk is None:
                raise ImportFailure("The patient's own record is not in the archive.")
            # A dangling reference fails this patient here, not at the commit.
            connection.check_constraints(table_names=ctx.check_tables)
    except ImportFailure:
        raise
    except DATA_ERRORS as e:
        # This patient's data is the problem: it rolled back alone. The full
        # exception text (which can quote values) stays in the server log.
        raise ImportFailure(_failure_reason(e), detail=f"{type(e).__name__}: {_clip(e, 300)}")
    # Anything else (OperationalError, InterfaceError, OSError, MemoryError...)
    # is about the environment, not this patient: it propagates and aborts the run.
    return media


# --------------------------------------------------------------------------
# Media: after the patient's commit, never over an existing file
# --------------------------------------------------------------------------

def _fresh_names(name, max_length):
    """Candidate names next to `name` under MEDIA_ROOT (a short random suffix
    before the extension, within the field's `max_length`). Whether one is
    really free is decided only by the atomic placement, never by a look-up."""
    root, ext = os.path.splitext(name)
    for _ in range(FRESH_NAME_ATTEMPTS):
        suffix = f"_{uuid.uuid4().hex[:7]}"
        keep = (max_length - len(suffix) - len(ext)) if max_length else len(root)
        if keep < 1:
            return
        yield f"{root[:keep]}{suffix}{ext}"


def _link_no_overwrite(temp_path, final_path):
    """Move `temp_path` to `final_path` without ever replacing what is there:
    `os.link` is atomic and refuses an existing name, so two writers cannot
    both win. True when placed (the temp file is then removed), False when
    `final_path` already exists. Where hard links are unsupported it falls back
    to a look-up plus `os.replace`."""
    try:
        os.link(temp_path, final_path)
    except FileExistsError:
        return False
    except OSError:
        if os.path.lexists(final_path):
            return False
        os.replace(temp_path, final_path)
        return True
    try:
        os.unlink(temp_path)
    except OSError:
        pass  # the caller's cleanup retries; the file is placed
    return True


def _place_media(zf, checksums, key, file_field, new_pk, name):
    """Copy `media/<name>` to MEDIA_ROOT for the new row `key`/`new_pk`. Returns
    a short warning, or None on success. The path is confined to MEDIA_ROOT, the
    bytes go to a temp file whose SHA-256 must equal the manifest's, and only
    then is it placed with an atomic no-overwrite operation -- under a fresh
    name, with the row repointed to it, when a file already exists at the
    target path.

    On ANY failure the new row must not be left pointing at somebody else's
    file: when a file exists at the row's archived path (it belongs to another
    patient, we never wrote it), the row's file field is cleared."""
    name = str(name)
    try:
        warning = _copy_media(zf, checksums, key, file_field, new_pk, name)
    except Exception as e:  # never let media undo a committed patient
        logger.exception("Restore import: media copy raised for %s %s.", key, new_pk)
        warning = f"{_clip(name, 100)}: could not be copied ({type(e).__name__})"
    if warning is None:
        return None
    try:
        foreign = os.path.lexists(safe_join(settings.MEDIA_ROOT, name))
    except (SuspiciousFileOperation, ValueError, OSError):
        foreign = False
    if not foreign:
        return warning  # nothing exists there: the archived name dangles, exactly as in the source
    try:
        # A queryset update: no signals, no `django_cleanup` file handling.
        apps.get_model(key)._base_manager.filter(pk=new_pk).update(**{file_field: ''})
    except Exception:
        logger.exception("Restore import: could not clear the file field of %s %s.", key, new_pk)
        return f"{warning}; the archived file name is already used by another file and this row could not be cleared"
    return f"{warning}; the archived file name is already used by another file, so this row has no file"


def _copy_media(zf, checksums, key, file_field, new_pk, name):
    label = _clip(name, 100)
    arcname = f"{restore_validation.MEDIA_PREFIX}{name}"
    try:
        info = zf.getinfo(arcname)
    except KeyError:
        return f"{label}: missing from the archive"
    expected = checksums.get(arcname)
    if not isinstance(expected, str):
        return f"{label}: not listed in the archive's manifest"
    if info.file_size > MEDIA_MEMBER_SIZE_CEILING:
        return (
            f"{label}: declared size ({info.file_size} bytes) exceeds the "
            f"{MEDIA_MEMBER_SIZE_CEILING}-byte per-file limit"
        )
    try:
        target = safe_join(settings.MEDIA_ROOT, name)
    except (SuspiciousFileOperation, ValueError):
        return f"{label}: path is outside the media folder"

    model = apps.get_model(key)
    temp_path = None
    final_path = None
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
            return f"{label}: checksum mismatch"

        new_name = name
        final_path = target
        if not _link_no_overwrite(temp_path, target):
            # A file is already there (it belongs to an existing patient, or
            # another writer just won): never overwrite it; use a fresh name.
            final_path = None
            max_length = model._meta.get_field(file_field).max_length
            for candidate in _fresh_names(name, max_length):
                candidate_path = safe_join(settings.MEDIA_ROOT, candidate)
                os.makedirs(os.path.dirname(candidate_path), exist_ok=True)
                if _link_no_overwrite(temp_path, candidate_path):
                    new_name, final_path = candidate, candidate_path
                    break
            if final_path is None:
                return f"{label}: a file already exists there and no free name was found"
            try:
                # A queryset update: no signals, no `django_cleanup` file handling.
                model._base_manager.filter(pk=new_pk).update(**{file_field: new_name})
            except Exception as e:
                # The file was placed but its row could not be repointed: no orphan.
                try:
                    os.unlink(final_path)
                except OSError:
                    pass
                logger.warning("Restore import: %s %s could not be repointed: %s", key, new_pk, e)
                return f"{label}: could not be recorded ({type(e).__name__})"
    except (OSError, ValueError, SuspiciousFileOperation, *restore_validation._ZIP_READ_ERRORS) as e:
        logger.warning("Restore import: %s could not be written: %s", label, e)
        return f"{label}: could not be written ({type(e).__name__})"
    finally:
        # After a successful placement the temp file is already gone.
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    return None


# --------------------------------------------------------------------------
# Result text
# --------------------------------------------------------------------------

def _listed(items, formatter):
    shown = "; ".join(formatter(item) for item in items[:MAX_LISTED_WARNINGS])
    if len(items) > MAX_LISTED_WARNINGS:
        shown += f"; ... and {len(items) - MAX_LISTED_WARNINGS} more"
    return shown


def failed_patients(failed):
    """The `failed` entries that name a patient (the early-stop entry, whose
    `archive_pk` is None, is not one)."""
    return [entry for entry in failed if entry.get('archive_pk') is not None]


def _identifier_text(identifiers):
    if not isinstance(identifiers, dict) or not identifiers:
        return ""
    return " (" + ", ".join(f"{name}: {value}" for name, value in identifiers.items()) + ")"


def format_failure(entry):
    reason = _clip(entry.get('reason', ''), FAILURE_REASON_MAX)
    if entry.get('archive_pk') is None:
        return reason
    return f"archive patient {entry['archive_pk']}{_identifier_text(entry.get('identifiers'))}: {reason}"


def format_import_message(summary):
    """The job's message for a run that committed at least one patient: '' when
    everything went cleanly, else the counts and (capped) what needs attention."""
    failed = summary['failed']
    media = summary['media_warnings']
    if not failed and not media:
        return ""
    patients = failed_patients(failed)
    parts = [
        f"Restore completed with warnings: {summary['imported']} patient(s) imported, "
        f"{summary['skipped']} skipped, {summary['excluded']} excluded, {len(patients)} failed."
    ]
    for entry in failed:
        if entry.get('archive_pk') is None:
            reason = format_failure(entry)
            parts.append(reason[:1].upper() + reason[1:] + ".")
    if patients:
        parts.append("Failed: " + _listed(patients, format_failure) + ".")
    if media:
        parts.append(f"{len(media)} media warning(s): " + _listed(media, str) + ".")
    return " ".join(parts)


EMPTY_IMPORT_MESSAGE = (
    "Nothing was imported: every patient in the archive was skipped or excluded, so nothing needed importing."
)


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

@dataclass
class _Outcome:
    """What step 4 did so far. `processed` counts patients finished (imported
    or failed); `aborted` is set when an unexpected error stopped the run after
    at least one patient had committed."""
    imported: int = 0
    processed: int = 0
    failed: list = field(default_factory=list)
    media_warnings: list = field(default_factory=list)
    aborted: bool = False
    not_attempted: int = 0


def _stop_early(outcome, error, total):
    """An unexpected (non-`ImportFailure`) error. With nothing committed the
    data is unchanged: `RestoreError` (the job fails, the upload goes back to
    `confirmed`). Once a patient has committed the upload must never return to
    `confirmed` (its partition is stale: a retry would import committed
    patients again), so the run ends here WITH WARNINGS instead."""
    name = type(error).__name__
    security_logger.error(
        "Restore import: unexpected %s after %s committed patient(s): %s",
        name, outcome.imported, _clip(error, 300), exc_info=error,
    )
    if not outcome.imported:
        raise RestoreError(f"The import could not run ({name}), so nothing was changed.")
    outcome.aborted = True
    outcome.not_attempted = total - outcome.processed
    outcome.failed.append({
        'archive_pk': None,
        'identifiers': {},
        'reason': f"the import stopped early: {name}; {outcome.not_attempted} patient(s) were not imported",
    })


def _import_all(upload, job, target, import_pks, progress, identifiers=None):
    """Step 4 (a non-empty import-set). Returns an `_Outcome`."""
    identifiers = identifiers or {}
    import_set = set(import_pks)
    total = len(import_pks)
    outcome = _Outcome()
    spool = None
    try:
        ctx = _ImportContext(target)
        spool = _Spool(str(restore_validation.get_upload_dir(upload) / f"import-spool-{job.id}"))
        _spool_import_set(upload, import_set, spool, progress.span(*SPOOL_RANGE))
        progress.report(SPOOL_RANGE[1])
        report_import = progress.span(*IMPORT_RANGE)

        with zipfile.ZipFile(restore_validation.get_upload_path(upload)) as zf:
            checksums = restore_apply._manifest_checksums(zf)
            for archive_pk in import_pks:
                try:
                    media = _import_patient(archive_pk, spool.records_for(archive_pk), ctx)
                except ImportFailure as e:
                    entry = {
                        'archive_pk': archive_pk,
                        'identifiers': identifiers.get(archive_pk, {}),
                        'reason': _clip(e.reason, FAILURE_REASON_MAX),
                    }
                    outcome.failed.append(entry)
                    security_logger.warning(
                        "Restore import: archive patient %s failed and was rolled back: %s%s", archive_pk,
                        entry['reason'], f" [{e.detail}]" if e.detail else "",
                    )
                else:
                    outcome.imported += 1
                    for key, file_field, new_pk, name in media:
                        warning = _place_media(zf, checksums, key, file_field, new_pk, name)
                        if warning:
                            outcome.media_warnings.append(f"archive patient {archive_pk}: {warning}")
                outcome.processed += 1
                report_import(outcome.processed / total)
    except (RestoreError, ExportFormatError):
        raise
    except Exception as e:
        _stop_early(outcome, e, total)
    finally:
        if spool is not None:
            spool.close()
    return outcome


def execute_import(job, progress_callback=None):
    """
    Run steps 1-4 for the date-scoped `restore` `job` (its upload is
    `job.restore_upload`). `progress_callback(pct)` gets a monotonic 0..99
    value. Raises `RestoreError` / `ExportFormatError` before any patient is
    touched, or when nothing could be imported; the caller writes the terminal
    states. Returns an `ImportResult`.
    """
    progress = Progress(progress_callback)
    upload = RestoreUpload.objects.filter(pk=job.restore_upload_id).first()
    if upload is None:
        raise RestoreError("The restore job's upload no longer exists.")

    restore_apply.check_upload_ready(upload)
    if not restore_apply.is_date_scoped(upload.confirmed_snapshot):
        raise RestoreError("This archive is not date-scoped, so the additive import cannot apply it.")
    restore_apply.verify_confirmed(upload, progress.span(*REHASH_RANGE))
    progress.report(REHASH_RANGE[1])

    match, import_pks = _read_partition(upload)
    target = _resolve_target(job, match)
    skipped, excluded = len(match['skip']), len(match['excluded'])

    if not import_pks:
        # Nothing will change: no snapshot is taken and the archive is not read.
        summary = {
            'mode': MODE_DATE_SCOPED, 'imported': 0, 'failed': [], 'skipped': skipped,
            'excluded': excluded, 'media_warnings': [],
        }
        _log_summary(upload, job, summary, aborted=False)
        return ImportResult(snapshot=None, summary=summary, warnings=[], message=EMPTY_IMPORT_MESSAGE)

    snapshot, snapshot_skipped = restore_apply.take_snapshot(job, progress.span(*SNAPSHOT_RANGE))
    progress.report(SNAPSHOT_RANGE[1])

    outcome = _import_all(upload, job, target, import_pks, progress, _identifiers_by_pk(match))

    if outcome.failed and not outcome.imported:
        raise RestoreError(
            f"None of the {len(outcome.failed)} patient(s) could be imported, so nothing was changed. "
            + _listed(outcome.failed, format_failure) + "."
        )

    media_warnings = outcome.media_warnings
    if snapshot_skipped:
        media_warnings.append(
            f"the pre-restore snapshot (job {snapshot.id}) skipped {len(snapshot_skipped)} media file(s)"
        )
    summary = {
        'mode': MODE_DATE_SCOPED,
        'imported': outcome.imported,
        'failed': outcome.failed,
        'skipped': skipped,
        'excluded': excluded,
        'media_warnings': media_warnings,
    }
    if outcome.aborted:
        summary['aborted'] = True
        summary['not_attempted'] = outcome.not_attempted
    warnings = [format_failure(entry) for entry in outcome.failed] + list(media_warnings)
    _log_summary(upload, job, summary, aborted=outcome.aborted)
    return ImportResult(snapshot=snapshot, summary=summary, warnings=warnings, message=format_import_message(summary))


def _log_summary(upload, job, summary, aborted):
    security_logger.info(
        "Restore import summary: upload=%s job=%s imported=%s failed=%s skipped=%s excluded=%s "
        "media_warnings=%s aborted=%s",
        upload.id, job.id, summary['imported'], len(failed_patients(summary['failed'])), summary['skipped'],
        summary['excluded'], len(summary['media_warnings']), aborted,
    )
