"""
Restore archive staging and validation -- Story 2.1.

An uploaded restore archive is untrusted input. This module has two halves:

  * Staging helpers, used by `backup/views.py`: stream the upload to
    non-public storage (`BASE_DIR/restore_uploads/<upload_id>/upload.zip`)
    hashing it in the same pass, check free disk, replace a user's earlier
    finished uploads.
  * The five-stage validation engine, used by
    `manage.py validate_restore_upload`: zip safety, manifest, schema,
    origin authenticity, per-file checksums. Each stage raises a
    `RestoreRejection` carrying its own error code and a message naming the
    specific mismatch; the first failure stops validation.

Nothing here writes to any domain model, extracts media, or parses
`db_export.json`'s contents -- it is only ever hashed.
"""
import hashlib
import json
import logging
import os
import re
import shutil
import stat
import struct
import zipfile
import zlib
from dataclasses import dataclass, field

from django.conf import settings

from backup.services import (
    COPY_CHUNK_SIZE,
    DISK_SAFETY_MINIMUM_BYTES,
    _compute_schema_version,
)
from ndas.custom_codes.choice import (
    BackupJobType,
    RestoreAuthenticity,
    RestoreRejectionCode as Code,
    RestoreUploadStatus,
)

# Denials and archive rejections must reach `security.log` (the
# `django.security` logger's `security_file` handler).
security_logger = logging.getLogger('django.security.restore')
logger = logging.getLogger(__name__)

UPLOAD_FILENAME = 'upload.zip'

MANIFEST_NAME = 'manifest.json'
DB_EXPORT_NAME = 'db_export.json'
MEDIA_PREFIX = 'media/'

MAX_EXPANSION_RATIO = 1000  # any single member above this uncompressed:compressed ratio is a zip bomb
TOTAL_SIZE_LIMIT_MULTIPLIER = 4  # total declared size may not exceed 4x the upload limit
MANIFEST_MAX_BYTES = 64 * 1024 * 1024  # manifest.json is parsed in memory; bound it
MAX_SOURCE_JOB_ID = 2 ** 31 - 1  # fits the PositiveIntegerField / a DB integer lookup
MAX_MEMBERS = 500_000  # cap on zip member count (each member costs memory in infolist())
COMPRESSED_SIZE_SLACK = 64 * 1024  # sum(compress_size) may exceed the file size by this much
MAX_MEMBER_NAME_LENGTH = 1024

# Bounds on attacker-controlled manifest values (they also bound `manifest_summary`).
MAX_SHORT_TEXT = 255
MAX_INSTITUTIONS = 1000
MAX_RECORD_COUNT_KEYS = 100
MAX_MODEL_LABEL_LENGTH = 100

_DRIVE_LETTER_RE = re.compile(r'^[A-Za-z]:')
_CONTROL_CHARS_RE = re.compile(r'[\x00-\x1f\x7f]')
_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
_SHA256_ANYCASE_RE = re.compile(r'^[0-9a-fA-F]{64}$')
_MODEL_LABEL_RE = re.compile(r'^[a-z0-9_]+\.[a-z0-9_]+$')
_WINDOWS_RESERVED_NAMES = frozenset(
    {'CON', 'PRN', 'AUX', 'NUL'}
    | {f'COM{i}' for i in range(1, 10)}
    | {f'LPT{i}' for i in range(1, 10)}
)

# Everything zipfile can raise while parsing or reading a malformed archive.
_ZIP_ERRORS = (
    zipfile.BadZipFile, EOFError, ValueError, OverflowError, struct.error, NotImplementedError,
)
_ZIP_READ_ERRORS = _ZIP_ERRORS + (zlib.error, RuntimeError)

# Statuses in which an upload is finished and may be replaced by a new one.
# `confirmed` (Story 2.2) is deliberately NOT here: a confirmed archive is
# awaiting a restore and is only ever removed by an explicit cancel.
FINISHED_STATUSES = (
    RestoreUploadStatus.VALIDATED,
    RestoreUploadStatus.REJECTED,
    RestoreUploadStatus.FAILED,
)


class RestoreRejection(Exception):
    """A specific, user-presentable reason the archive is rejected."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = str(code)
        self.message = message


@dataclass
class ValidationResult:
    authenticity: str
    summary: dict = field(default_factory=dict)


def _clip(value, n=120):
    """Attacker-controlled text made safe for a message or log line: control
    characters (newlines etc.) replaced, length bounded."""
    text = _CONTROL_CHARS_RE.sub('?', str(value))
    return text if len(text) <= n else text[:n] + '...'


# --------------------------------------------------------------------------
# Staging
# --------------------------------------------------------------------------

def get_restore_uploads_root():
    """Non-public storage root for every staged upload (never under MEDIA_ROOT)."""
    return settings.BASE_DIR / 'restore_uploads'


def get_upload_dir(upload):
    return get_restore_uploads_root() / str(upload.id)


def get_upload_path(upload):
    return get_upload_dir(upload) / UPLOAD_FILENAME


def has_sufficient_restore_space(size_bytes):
    """
    Disk pre-check for staging an upload of `size_bytes`: it must fit with
    Story 1.1's flat safety margin on top. Returns `(ok, required, free)`.
    """
    required = int(size_bytes) + DISK_SAFETY_MINIMUM_BYTES
    free = shutil.disk_usage(settings.BASE_DIR).free
    return free >= required, required, free


def stage_upload(upload, uploaded_file):
    """
    Stream `uploaded_file` to `BASE_DIR/restore_uploads/<id>/upload.zip` in
    chunks, hashing it in the same pass -- the file is never held in memory.
    Returns `(size_bytes, sha256_hexdigest)`.
    """
    upload_dir = get_upload_dir(upload)
    upload_dir.mkdir(parents=True, exist_ok=True)
    hasher = hashlib.sha256()
    size = 0
    with open(get_upload_path(upload), 'wb') as dest:
        for chunk in uploaded_file.chunks(COPY_CHUNK_SIZE):
            hasher.update(chunk)
            dest.write(chunk)
            size += len(chunk)
    return size, hasher.hexdigest()


def delete_staged_archive(upload):
    """Remove only the staged .zip. The upload directory also holds the
    validation command's own log, still open in that process on Windows."""
    get_upload_path(upload).unlink(missing_ok=True)


def delete_upload_files(upload):
    shutil.rmtree(get_upload_dir(upload), ignore_errors=True)


def delete_finished_uploads(user, keep_id=None):
    """
    A new upload replaces the user's earlier finished ones -- rows and staged
    files. A `validating` upload is never touched. A row is deleted only once
    its files are really gone: if they can't be removed (e.g. a Windows lock)
    the row is kept, a warning is logged, and the next upload retries.
    """
    from backup.models import RestoreUpload

    stale = RestoreUpload.objects.filter(uploaded_by=user, status__in=FINISHED_STATUSES)
    if keep_id is not None:
        stale = stale.exclude(pk=keep_id)
    for old in list(stale):
        try:
            shutil.rmtree(get_upload_dir(old))
        except FileNotFoundError:
            pass
        except OSError:
            logger.warning(
                "Could not remove staged files for RestoreUpload %s; keeping its row to retry later.",
                old.id, exc_info=True,
            )
            continue
        old.delete()


# --------------------------------------------------------------------------
# Validation engine
# --------------------------------------------------------------------------

def _is_symlink(info):
    # Unix mode lives in the high 16 bits of external_attr when the archive
    # was created on a Unix-like system.
    return stat.S_ISLNK(info.external_attr >> 16)


def _unsafe_path_reason(name):
    if not name:
        return 'empty name'
    if len(name) > MAX_MEMBER_NAME_LENGTH:
        return f'is longer than {MAX_MEMBER_NAME_LENGTH} characters'
    if _CONTROL_CHARS_RE.search(name):
        return 'contains a control character'
    if '\\' in name:
        return 'contains a backslash'
    if name.startswith('/'):
        return 'is an absolute path'
    if _DRIVE_LETTER_RE.match(name):
        return 'starts with a drive letter'
    if ':' in name:
        return "contains ':' (NTFS alternate data stream)"
    parts = name.rstrip('/').split('/')
    for part in parts:
        if part in ('', '.', '..'):
            return "contains an empty, '.' or '..' path segment"
        if part.endswith('.') or part.endswith(' '):
            return "has a path segment ending in '.' or a space"
        if part.split('.', 1)[0].strip().upper() in _WINDOWS_RESERVED_NAMES:
            return 'uses a reserved Windows device name'
    return None


def _check_zip_safety(zf, archive_size):
    """Stage 1. Structure only: reads headers, never member contents."""
    infos = zf.infolist()

    if len(infos) > MAX_MEMBERS:
        raise RestoreRejection(
            Code.EXCESSIVE_EXPANSION,
            f"The archive has {len(infos)} members, above the {MAX_MEMBERS} limit.",
        )

    for info in infos:
        if info.flag_bits & 0x1:
            raise RestoreRejection(
                Code.ENCRYPTED_MEMBER,
                f"The archive contains an encrypted member ('{_clip(info.filename)}'). "
                "Backup archives are never encrypted.",
            )

    seen = set()
    for info in infos:
        folded = info.filename.casefold()
        if folded in seen:
            raise RestoreRejection(
                Code.DUPLICATE_MEMBER,
                f"The archive contains more than one member named '{_clip(info.filename)}' "
                "(names are compared case-insensitively).",
            )
        seen.add(folded)

    for info in infos:
        reason = _unsafe_path_reason(info.filename)
        if reason:
            raise RestoreRejection(
                Code.UNSAFE_MEMBER_PATH,
                f"The archive contains an unsafe member path ('{_clip(info.filename)}' {reason}).",
            )
        if _is_symlink(info):
            raise RestoreRejection(
                Code.SYMLINK_MEMBER,
                f"The archive contains a symbolic link ('{_clip(info.filename)}').",
            )

    for info in infos:
        name = info.filename
        allowed = (
            name in (MANIFEST_NAME, DB_EXPORT_NAME)
            or (name.startswith(MEDIA_PREFIX) and not name.endswith('/') and len(name) > len(MEDIA_PREFIX))
        )
        if not allowed:
            raise RestoreRejection(
                Code.UNEXPECTED_MEMBER,
                f"The archive contains an unexpected member ('{_clip(name)}'). Only manifest.json, "
                "db_export.json and media/... files are allowed.",
            )

    total_declared = 0
    total_compressed = 0
    for info in infos:
        total_declared += info.file_size
        total_compressed += info.compress_size
        if info.file_size > MAX_EXPANSION_RATIO * max(info.compress_size, 1):
            raise RestoreRejection(
                Code.EXCESSIVE_EXPANSION,
                f"Member '{_clip(info.filename)}' expands implausibly ({info.file_size} bytes from "
                f"{info.compress_size} compressed, above {MAX_EXPANSION_RATIO}:1).",
            )

    # Members that claim more compressed bytes than the file even holds
    # overlap each other -- the classic way to build a zip bomb whose
    # per-member ratios all look reasonable.
    if total_compressed > archive_size + COMPRESSED_SIZE_SLACK:
        raise RestoreRejection(
            Code.EXCESSIVE_EXPANSION,
            f"The archive's members declare {total_compressed} compressed bytes but the file is only "
            f"{archive_size} bytes; its members overlap.",
        )

    total_limit = min(
        TOTAL_SIZE_LIMIT_MULTIPLIER * settings.FILE_UPLOAD_LIMITS['RESTORE_ARCHIVE_MAX_SIZE'],
        MAX_EXPANSION_RATIO * archive_size,
    )
    if total_declared > total_limit:
        raise RestoreRejection(
            Code.EXCESSIVE_EXPANSION,
            f"The archive declares {total_declared} bytes of content in total, above the "
            f"{total_limit}-byte limit.",
        )


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_short_str(value, limit=MAX_SHORT_TEXT):
    return isinstance(value, str) and len(value) <= limit


def _is_nullable_short_str(value):
    return value is None or _is_short_str(value, 64)


def _record_counts_problem(value):
    if not isinstance(value, dict):
        return "field 'record_counts' must be an object of model counts"
    if len(value) > MAX_RECORD_COUNT_KEYS:
        return f"field 'record_counts' has more than {MAX_RECORD_COUNT_KEYS} entries"
    for key, count in value.items():
        if len(key) > MAX_MODEL_LABEL_LENGTH or not _MODEL_LABEL_RE.match(key):
            return f"field 'record_counts' has a key that is not a model label ('{_clip(key, 40)}')"
        if not _is_int(count) or count < 0:
            return f"field 'record_counts' must map model labels to non-negative integers ('{_clip(key, 40)}')"
    return None


def _checksums_problem(value):
    if not isinstance(value, dict):
        return "field 'checksums' must be an object of file checksums"
    for key, digest in value.items():
        if len(key) > MAX_MEMBER_NAME_LENGTH:
            return f"field 'checksums' has a file name longer than {MAX_MEMBER_NAME_LENGTH} characters"
        if not isinstance(digest, str) or not _SHA256_ANYCASE_RE.match(digest):
            return f"field 'checksums' has a value that is not a SHA-256 hex digest (for '{_clip(key, 40)}')"
    return None


def _manifest_field_problem(manifest):
    """Return a description of the first missing/mistyped/out-of-bounds field, or None."""
    checks = (
        ('source_job_id', lambda v: _is_int(v) and 0 < v <= MAX_SOURCE_JOB_ID, 'a positive integer'),
        ('manifest_version', _is_int, 'an integer'),
        ('schema_version', lambda v: isinstance(v, str) and bool(_SHA256_RE.match(v)),
         'a 64-character lowercase hex string'),
        ('checksum_algorithm', lambda v: _is_short_str(v), f'a string of at most {MAX_SHORT_TEXT} characters'),
        ('scope_type', lambda v: _is_short_str(v), f'a string of at most {MAX_SHORT_TEXT} characters'),
        ('institutions',
         lambda v: isinstance(v, list) and len(v) <= MAX_INSTITUTIONS and all(_is_short_str(i) for i in v),
         f'a list of at most {MAX_INSTITUTIONS} strings of at most {MAX_SHORT_TEXT} characters'),
        ('generated_at', lambda v: _is_short_str(v), f'a string of at most {MAX_SHORT_TEXT} characters'),
        ('generated_by', lambda v: _is_short_str(v), f'a string of at most {MAX_SHORT_TEXT} characters'),
        ('date_filter',
         lambda v: isinstance(v, dict) and isinstance(v.get('applied'), bool)
         and _is_nullable_short_str(v.get('start')) and _is_nullable_short_str(v.get('end')),
         "an object with a boolean 'applied' and string-or-null 'start'/'end'"),
    )
    for key in ('source_job_id', 'manifest_version', 'schema_version', 'checksum_algorithm', 'scope_type',
                'institutions', 'record_counts', 'checksums', 'generated_at', 'generated_by', 'date_filter'):
        if key not in manifest:
            return f"required field '{key}' is missing"
    for key, ok, expected in checks:
        if not ok(manifest[key]):
            return f"field '{key}' must be {expected}"
    return _record_counts_problem(manifest['record_counts']) or _checksums_problem(manifest['checksums'])


def _read_manifest(zf):
    """Stage 2. Returns the parsed, validated manifest dict."""
    try:
        info = zf.getinfo(MANIFEST_NAME)
    except KeyError:
        raise RestoreRejection(Code.MANIFEST_MISSING, "The archive has no manifest.json.")

    if info.file_size > MANIFEST_MAX_BYTES:
        raise RestoreRejection(
            Code.MANIFEST_INVALID,
            f"manifest.json is implausibly large ({info.file_size} bytes).",
        )
    try:
        with zf.open(info) as f:
            raw = f.read(MANIFEST_MAX_BYTES + 1)
    except _ZIP_READ_ERRORS as e:
        raise RestoreRejection(
            Code.MANIFEST_INVALID, f"manifest.json could not be read from the archive ({_clip(e)}).",
        )
    if len(raw) > MANIFEST_MAX_BYTES:
        raise RestoreRejection(Code.MANIFEST_INVALID, "manifest.json is implausibly large.")
    try:
        manifest = json.loads(raw.decode('utf-8'))
    except (ValueError, RecursionError) as e:  # UnicodeDecodeError and JSONDecodeError are ValueErrors
        raise RestoreRejection(Code.MANIFEST_INVALID, f"manifest.json is not valid JSON ({_clip(e)}).")

    if not isinstance(manifest, dict):
        raise RestoreRejection(Code.MANIFEST_INVALID, "manifest.json must contain a JSON object.")

    problem = _manifest_field_problem(manifest)
    if problem:
        raise RestoreRejection(Code.MANIFEST_INVALID, f"manifest.json is invalid: {problem}.")

    if manifest['manifest_version'] != 1:
        raise RestoreRejection(
            Code.MANIFEST_UNSUPPORTED,
            f"Unsupported manifest_version {manifest['manifest_version']!r}; this system reads version 1.",
        )
    if manifest['checksum_algorithm'] != 'sha256':
        raise RestoreRejection(
            Code.MANIFEST_UNSUPPORTED,
            f"Unsupported checksum_algorithm {_clip(manifest['checksum_algorithm'], 40)!r}; "
            "this system reads 'sha256'.",
        )
    if DB_EXPORT_NAME not in zf.namelist():
        raise RestoreRejection(Code.DB_EXPORT_MISSING, "The archive has no db_export.json.")
    return manifest


def _check_schema(manifest):
    """Stage 3."""
    local = _compute_schema_version()
    if manifest['schema_version'] != local:
        raise RestoreRejection(
            Code.SCHEMA_MISMATCH,
            f"Schema version mismatch: the archive was made against schema "
            f"{manifest['schema_version']} but this database is at {local}. "
            "Restore the archive on a system running the same version of NDAS.",
        )


def _check_origin(manifest, archive_sha256, allow_unverified):
    """Stage 4. Returns the authenticity value to record."""
    from backup.models import BackupJob
    from ndas.custom_codes.choice import BackupJobStatus

    job_id = manifest['source_job_id']
    # An archive's checksum is only ever recorded when its job completes.
    job = BackupJob.objects.filter(
        pk=job_id, job_type=BackupJobType.BACKUP, status=BackupJobStatus.COMPLETED,
    ).first()
    if job is not None and job.archive_checksum:
        if archive_sha256.lower() != job.archive_checksum.lower():
            raise RestoreRejection(
                Code.ARCHIVE_CHECKSUM_MISMATCH,
                f"The uploaded archive's SHA-256 ({archive_sha256}) does not match the checksum "
                f"recorded for backup job {job_id} ({job.archive_checksum}). The file was "
                "modified after it was created, or job ID "
                f"{job_id} on this system belongs to a different backup.",
            )
        return RestoreAuthenticity.VERIFIED

    if allow_unverified:
        return RestoreAuthenticity.UNVERIFIED
    raise RestoreRejection(
        Code.ORIGIN_NOT_VERIFIABLE,
        f"This system has no completed backup record with a checksum for backup job {job_id}, so "
        "the archive's origin cannot be verified. If you trust the source, upload it again with "
        "the 'Allow unverified origin' box ticked.",
    )


def _verify_file_checksums(zf, manifest, progress_callback):
    """Stage 5. Streams every member once, never reading a whole file."""
    checksums = manifest['checksums']
    infos = {info.filename: info for info in zf.infolist()}

    for name in checksums:
        if name not in infos:
            raise RestoreRejection(
                Code.FILE_MISSING,
                f"The manifest lists '{_clip(name)}' but it is not in the archive.",
            )
    for name in infos:
        if name != MANIFEST_NAME and name not in checksums:
            raise RestoreRejection(
                Code.FILE_NOT_LISTED,
                f"The archive contains '{_clip(name)}' but the manifest does not list it.",
            )

    total_bytes = sum(infos[name].file_size for name in checksums)
    done_bytes = 0
    last_pct = -1

    def _report():
        nonlocal last_pct
        if progress_callback and total_bytes:
            pct = min(int(done_bytes / total_bytes * 100), 99)
            if pct != last_pct:
                last_pct = pct
                progress_callback(pct)

    for name, expected in checksums.items():
        hasher = hashlib.sha256()
        try:
            with zf.open(infos[name]) as f:
                while chunk := f.read(COPY_CHUNK_SIZE):
                    hasher.update(chunk)
                    done_bytes += len(chunk)
                    _report()
        except _ZIP_READ_ERRORS as e:
            raise RestoreRejection(
                Code.FILE_CHECKSUM_MISMATCH,
                f"'{_clip(name)}' is corrupt and could not be read from the archive ({_clip(e)}).",
            )
        if hasher.hexdigest() != expected.lower():
            raise RestoreRejection(
                Code.FILE_CHECKSUM_MISMATCH,
                f"Checksum mismatch for '{_clip(name)}': the manifest records {expected.lower()} but the "
                f"archive's copy hashes to {hasher.hexdigest()}.",
            )
        _report()


def _manifest_summary(manifest):
    date_filter = manifest['date_filter']
    return {
        'source_job_id': manifest['source_job_id'],
        'manifest_version': manifest['manifest_version'],
        'schema_version': manifest['schema_version'],
        'scope_type': manifest['scope_type'],
        'institutions': manifest['institutions'],
        'record_counts': manifest['record_counts'],
        'date_filter': {
            'applied': date_filter['applied'],
            'start': date_filter.get('start'),
            'end': date_filter.get('end'),
        },
        'generated_at': manifest['generated_at'],
        'generated_by': manifest['generated_by'],
    }


def validate_restore_archive(archive_path, archive_sha256, allow_unverified=False, progress_callback=None) -> ValidationResult:
    """
    Run the five validation stages, in order, against the staged archive at
    `archive_path` (whose SHA-256 was computed during staging). Raises
    `RestoreRejection` on the first failure; any other exception is an
    unexpected error for the caller to record as `failed`.

    `progress_callback(pct)` is called with an int in 0..99 while the
    per-file stage streams the archive.
    """
    try:
        zf = zipfile.ZipFile(archive_path)
    except _ZIP_ERRORS as e:
        raise RestoreRejection(Code.NOT_A_ZIP, f"The file is not a valid zip archive ({_clip(e)}).")

    with zf:
        _check_zip_safety(zf, os.path.getsize(archive_path))
        manifest = _read_manifest(zf)
        _check_schema(manifest)
        authenticity = _check_origin(manifest, archive_sha256, allow_unverified)
        _verify_file_checksums(zf, manifest, progress_callback)

    return ValidationResult(authenticity=authenticity, summary=_manifest_summary(manifest))
