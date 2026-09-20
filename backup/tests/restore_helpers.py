"""
Shared builders for Story 2.1's restore-upload tests: hand-built restore
archives (valid, corrupt or malicious) and an isolated BASE_DIR so staged
uploads / backup dirs never touch the real checkout.
"""
import hashlib
import io
import json
import shutil
import struct
import tempfile
import warnings
import zipfile
from pathlib import Path

from django.test import override_settings

DB_EXPORT_BYTES = json.dumps({"patients.patient": [], "video.video": []}).encode("utf-8")
SOURCE_JOB_ID = 4242


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def current_schema_version():
    from backup.services import _compute_schema_version
    return _compute_schema_version()


def build_manifest(members, **overrides):
    """A valid manifest for `members` (name -> bytes; manifest.json excluded)."""
    manifest = {
        "source_job_id": SOURCE_JOB_ID,
        "manifest_version": 1,
        "schema_version": current_schema_version(),
        "checksum_algorithm": "sha256",
        "scope_type": "single",
        "institutions": ["test-hosp"],
        "record_counts": {"patients.patient": 0, "video.video": 0},
        "checksums": {name: sha256_bytes(data) for name, data in members.items()},
        "generated_at": "2026-09-20T10:00:00+00:00",
        "generated_by": "tester",
        "date_filter": {"applied": False, "start": None, "end": None},
    }
    manifest.update(overrides)
    return manifest


def build_archive(path, media=None, manifest_overrides=None, manifest=True, db_export=True,
                  extra_members=None, compression=zipfile.ZIP_DEFLATED):
    """
    Write a restore archive at `path`. `media` maps "media/..." names to bytes.
    `manifest`: True -> valid manifest (with `manifest_overrides` applied),
    a dict/bytes -> used verbatim, False -> omitted. `extra_members` is a list
    of (name-or-ZipInfo, bytes) written after the standard members.
    Returns the members dict (name -> bytes) that the manifest checksums cover.
    """
    members = {}
    if db_export:
        # True -> the empty default; bytes -> a custom (e.g. record-bearing) export
        members["db_export.json"] = DB_EXPORT_BYTES if db_export is True else db_export
    members.update(media or {})

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # duplicate-name UserWarning
        with zipfile.ZipFile(path, "w", compression=compression) as zf:
            for name, data in members.items():
                zf.writestr(name, data)
            for name, data in (extra_members or []):
                zf.writestr(name, data)
            if manifest is True:
                manifest_bytes = json.dumps(build_manifest(members, **(manifest_overrides or {}))).encode("utf-8")
                zf.writestr("manifest.json", manifest_bytes)
            elif manifest is not False:
                zf.writestr(
                    "manifest.json",
                    manifest if isinstance(manifest, bytes) else json.dumps(manifest).encode("utf-8"),
                )
    return members


def flag_first_member_encrypted(path):
    """Set the 'encrypted' general-purpose bit in the first central-directory header."""
    data = bytearray(Path(path).read_bytes())
    i = data.index(b"PK\x01\x02")
    data[i + 8] |= 0x1
    Path(path).write_bytes(bytes(data))


def corrupt_member_data(path, name, fill=b"\xff"):
    """Overwrite `name`'s stored/compressed payload so reading it fails
    (bad CRC for a stored member, an invalid stream for a deflated one)."""
    with zipfile.ZipFile(path) as zf:
        info = zf.getinfo(name)
    data = bytearray(Path(path).read_bytes())
    off = info.header_offset
    name_len, extra_len = struct.unpack("<HH", data[off + 26:off + 30])
    start = off + 30 + name_len + extra_len
    end = start + info.compress_size
    data[start:end] = (fill * info.compress_size)[:info.compress_size]
    Path(path).write_bytes(bytes(data))


class IsolatedBaseDirMixin:
    """Point settings.BASE_DIR at a throwaway directory for each test."""

    def setUp(self):
        super().setUp()
        self.base_dir = Path(tempfile.mkdtemp(prefix="ndas_restore_test_"))
        self.addCleanup(shutil.rmtree, self.base_dir, ignore_errors=True)
        self.media_root = self.base_dir / "media"
        self.static_root = self.base_dir / "static"
        self.enterContext(override_settings(
            BASE_DIR=self.base_dir, MEDIA_ROOT=str(self.media_root), STATIC_ROOT=str(self.static_root),
        ))
        self.tmp = self.base_dir / "tmp"
        self.tmp.mkdir()

    def archive_path(self, name="archive.zip"):
        return self.tmp / name


def zip_bytes(**kwargs):
    """A valid archive as bytes (for upload tests)."""
    buf = io.BytesIO()
    tmp = Path(tempfile.mkdtemp(prefix="ndas_zipbytes_"))
    try:
        path = tmp / "a.zip"
        build_archive(path, **kwargs)
        buf.write(path.read_bytes())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return buf.getvalue()
