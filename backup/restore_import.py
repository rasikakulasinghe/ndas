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
when a patient failed or a media file did not copy); nothing committed and at
least one patient failed -> `RestoreError` (data unchanged).
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
from django.core.exceptions import SuspiciousFileOperation
from django.db import connection, transaction
from django.utils._os import safe_join

from backup import restore_apply, restore_validation
from backup.export_stream import START, ExportFormatError, iter_export_records
from backup.models import RestoreUpload
from backup.restore_apply import (
    MAX_LISTED_WARNINGS,
    MEDIA_FIELDS,
    MEDIA_MEMBER_SIZE_CEILING,
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


class ImportFailure(Exception):
    """One patient could not be imported; that patient's transaction rolled back."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


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
    import_pks = []
    for entry in match['import']:
        pk = entry.get('archive_pk') if isinstance(entry, dict) else None
        if isinstance(pk, bool) or not isinstance(pk, int):
            raise RestoreError("The confirmed import list holds an entry without an integer archive patient id.")
        import_pks.append(pk)
    if len(set(import_pks)) != len(import_pks):
        raise RestoreError("The confirmed import list names the same archive patient more than once.")
    return match, import_pks


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
        os.makedirs(directory, exist_ok=True)
        self._conn = sqlite3.connect(os.path.join(directory, 'spool.sqlite3'))
        self._conn.execute('PRAGMA journal_mode = OFF')
        self._conn.execute('PRAGMA synchronous = OFF')
        self._conn.execute(
            'CREATE TABLE records (seq INTEGER PRIMARY KEY, patient INTEGER NOT NULL, '
            'key TEXT NOT NULL, body TEXT NOT NULL)'
        )

    def add_many(self, rows):
        self._conn.executemany('INSERT INTO records (patient, key, body) VALUES (?, ?, ?)', rows)

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
                batch.append((owner, key, json.dumps(record)))
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
    `ImportFailure` (the transaction rolled back) on any problem."""
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
    except Exception as e:
        logger.warning("Restore import: archive patient %s failed and was rolled back: %s", archive_pk, e)
        raise ImportFailure(f"{type(e).__name__}: {_clip(e, 200)}")
    return media


# --------------------------------------------------------------------------
# Media: after the patient's commit, never over an existing file
# --------------------------------------------------------------------------

def _fresh_name(name, max_length):
    """An unused name next to `name` under MEDIA_ROOT (a short random suffix
    before the extension, within the field's `max_length`), or None."""
    root, ext = os.path.splitext(name)
    for _ in range(FRESH_NAME_ATTEMPTS):
        suffix = f"_{uuid.uuid4().hex[:7]}"
        keep = (max_length - len(suffix) - len(ext)) if max_length else len(root)
        if keep < 1:
            return None
        candidate = f"{root[:keep]}{suffix}{ext}"
        try:
            if not os.path.lexists(safe_join(settings.MEDIA_ROOT, candidate)):
                return candidate
        except (SuspiciousFileOperation, ValueError):
            return None
    return None


def _place_media(zf, checksums, key, file_field, new_pk, name):
    """Copy `media/<name>` to MEDIA_ROOT for the new row `key`/`new_pk`. Returns
    a short warning, or None on success. The path is confined to MEDIA_ROOT, the
    bytes go to a temp file whose SHA-256 must equal the manifest's, and only
    then is it `os.replace`d into place -- under a fresh name, with the row
    repointed to it, when a file already exists at the target path."""
    name = str(name)
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
        if os.path.lexists(target):
            # An existing file belongs to an existing patient: never overwrite it.
            new_name = _fresh_name(name, model._meta.get_field(file_field).max_length)
            if new_name is None:
                return f"{label}: a file already exists there and no free name was found"
            final_path = safe_join(settings.MEDIA_ROOT, new_name)
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
        os.replace(temp_path, final_path)
        temp_path = None
        if new_name != name:
            # A queryset update: no signals, no `django_cleanup` file handling.
            model._base_manager.filter(pk=new_pk).update(**{file_field: new_name})
    except (OSError, ValueError, SuspiciousFileOperation, *restore_validation._ZIP_READ_ERRORS) as e:
        return f"{label}: could not be written ({_clip(e, 80)})"
    except Exception as e:
        # The file was placed but its row could not be repointed: do not leave an orphan.
        if final_path and temp_path is None and final_path != target:
            try:
                os.unlink(final_path)
            except OSError:
                pass
        return f"{label}: could not be recorded ({_clip(e, 80)})"
    finally:
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


def format_failure(entry):
    return f"archive patient {entry['archive_pk']}: {_clip(entry['reason'], 120)}"


def format_import_message(summary):
    """The job's message for a run that committed at least one patient: '' when
    everything went cleanly, else the counts and (capped) what needs attention."""
    failed = summary['failed']
    media = summary['media_warnings']
    if not failed and not media:
        return ""
    parts = [
        f"Restore completed with warnings: {summary['imported']} patient(s) imported, "
        f"{summary['skipped']} skipped, {summary['excluded']} excluded, {len(failed)} failed."
    ]
    if failed:
        parts.append("Failed: " + _listed(failed, format_failure) + ".")
    if media:
        parts.append(f"{len(media)} media warning(s): " + _listed(media, str) + ".")
    return " ".join(parts)


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def _import_all(upload, job, target, import_pks, progress):
    """Step 4. Returns `(imported, failed, media_warnings)`."""
    import_set = set(import_pks)
    imported = 0
    failed = []
    media_warnings = []
    if not import_pks:
        return imported, failed, media_warnings  # nothing to import: the archive is not even read
    ctx = _ImportContext(target)
    spool = _Spool(str(restore_validation.get_upload_dir(upload) / f"import-spool-{job.id}"))
    try:
        _spool_import_set(upload, import_set, spool, progress.span(*SPOOL_RANGE))
        progress.report(SPOOL_RANGE[1])
        report_import = progress.span(*IMPORT_RANGE)
        total = len(import_pks)

        with zipfile.ZipFile(restore_validation.get_upload_path(upload)) as zf:
            checksums = restore_apply._manifest_checksums(zf)
            for done, archive_pk in enumerate(import_pks, start=1):
                try:
                    media = _import_patient(archive_pk, spool.records_for(archive_pk), ctx)
                except ImportFailure as e:
                    failed.append({'archive_pk': archive_pk, 'reason': _clip(e.reason, FAILURE_REASON_MAX)})
                else:
                    imported += 1
                    for key, file_field, new_pk, name in media:
                        try:
                            warning = _place_media(zf, checksums, key, file_field, new_pk, name)
                        except Exception as e:  # never let media undo a committed patient
                            logger.exception("Restore import: media copy raised for archive patient %s.", archive_pk)
                            warning = f"{_clip(name, 100)}: could not be copied ({_clip(e, 80)})"
                        if warning:
                            media_warnings.append(f"archive patient {archive_pk}: {warning}")
                report_import(done / total)
    finally:
        spool.close()
    return imported, failed, media_warnings


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

    snapshot, snapshot_skipped = restore_apply.take_snapshot(job, progress.span(*SNAPSHOT_RANGE))
    progress.report(SNAPSHOT_RANGE[1])

    imported, failed, media_warnings = _import_all(upload, job, target, import_pks, progress)

    if failed and not imported:
        raise RestoreError(
            f"None of the {len(failed)} patient(s) could be imported, so nothing was changed. "
            + _listed(failed, format_failure) + "."
        )

    if snapshot_skipped:
        media_warnings.append(
            f"the pre-restore snapshot (job {snapshot.id}) skipped {len(snapshot_skipped)} media file(s)"
        )
    summary = {
        'mode': MODE_DATE_SCOPED,
        'imported': imported,
        'failed': failed,
        'skipped': len(match['skip']),
        'excluded': len(match['excluded']),
        'media_warnings': media_warnings,
    }
    warnings = [format_failure(entry) for entry in failed] + list(media_warnings)
    logger.info(
        "RestoreUpload %s: date-scoped import by job %s: %s imported, %s failed, %s skipped, %s excluded, "
        "%s media warning(s).", upload.id, job.id, imported, len(failed), summary['skipped'],
        summary['excluded'], len(media_warnings),
    )
    return ImportResult(snapshot=snapshot, summary=summary, warnings=warnings, message=format_import_message(summary))
