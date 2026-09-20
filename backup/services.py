"""
Backup export service — Story 1.1, extended by Story 1.2 with the three
scope shapes (`single` / `multi` / `system`) that `_resolve_scope()` and
`_model_export_plan()` branch on below.

`create_export(job)` is the only place that touches the 13-model export
list and the archive layout. `backup/views.py` is the sole caller into this
module (directly, for the disk-space pre-check, and indirectly via
`backup/management/commands/run_backup.py`) — no other app may call into
this service layer directly, so permissions/rate-limiting/audit logging in
the trigger view can't be bypassed by a second code path.
"""
import hashlib
import json
import logging
import os
import shutil
import zipfile

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

from ndas.custom_codes.choice import BackupJobScopeType

logger = logging.getLogger(__name__)

# Disk-capacity pre-check: required_free = estimated_size * MULTIPLIER + MINIMUM_BYTES.
DISK_SAFETY_MULTIPLIER = 1.2
DISK_SAFETY_MINIMUM_BYTES = 500 * 1024 * 1024  # 500MB floor regardless of estimate

COPY_CHUNK_SIZE = 1024 * 1024  # 1MB — chunked media copy, never a whole-file read()

VIDEO_MODEL_KEY = "video.video"
ATTACHMENT_MODEL_KEY = "patients.attachment"


def get_archive_dir(job):
    """Non-public storage root for this job: BASE_DIR/backups/<job_id>/."""
    return settings.BASE_DIR / "backups" / str(job.id)


def get_archive_path(job):
    return get_archive_dir(job) / f"{job.id}.zip"


def _model_key(model):
    return f"{model._meta.app_label}.{model._meta.model_name}"


def _resolve_scope(institution_or_institutions, system_wide):
    """
    Normalize the three scope shapes (Story 1.2) into a single descriptor
    consumed by every per-model queryset builder below:

      - ("system", None)                  -- system_wide=True: unfiltered.
      - ("single", <Institution>)          -- `institution_or_institutions` is
        a single Institution instance (Story 1.1's original call shape,
        preserved unchanged) -> routed through `.for_institution(inst)`.
      - ("multi", [<Institution>, ...])    -- any other iterable of
        Institution instances -> routed through `.filter(x__in=...)`,
        *never* `.for_institution()` (that footgun treats an empty/None arg
        as "unfiltered", which multi must never do).
    """
    if system_wide:
        return "system", None
    if institution_or_institutions is None:
        # Every caller (`_model_export_plan`, `estimate_export_size_bytes`,
        # `has_sufficient_disk_space`) defaults to
        # (institution_or_institutions=None, system_wide=False) -- calling
        # any of them with no scope info at all is a caller bug. Without
        # this guard it falls through to the "multi" branch below and
        # `list(None)` raises a confusing TypeError instead of a clear one.
        raise ValueError("institution_or_institutions is required unless system_wide=True")
    Institution = apps.get_model('institution', 'Institution')
    if isinstance(institution_or_institutions, Institution):
        return "single", institution_or_institutions
    return "multi", list(institution_or_institutions)


def _resolve_patient_qs(institution_or_institutions, system_wide, date_start=None, date_end=None):
    """
    Story 1.4: institution-scoped `Patient` queryset (the same three shapes
    as `_resolve_scope`), optionally narrowed to `Patient.created_at`'s date
    falling in `[date_start, date_end]` (either bound may be None for an
    open-ended range; both None leaves the queryset unfiltered by date).

    Returns `(mode, value, patient_qs)` — `mode`/`value` are `_resolve_scope`'s
    own return values, handed back so callers that also need to scope
    referral querysets (never date-narrowed -- referral models stay
    full-scope always, per spec) don't have to re-derive the institution
    shape a second time.

    Shared by `_model_export_plan` and `estimate_export_size_bytes` so the
    institution+date resolution logic exists in exactly one place — a small,
    deliberate exception to this module's usual explicit-branches-over-
    abstraction style (see `_model_export_plan`'s docstring for that style's
    rationale elsewhere).
    """
    Patient = apps.get_model('patients', 'Patient')
    mode, value = _resolve_scope(institution_or_institutions, system_wide)

    if mode == "system":
        # Intentionally unfiltered by Institution.is_active -- see
        # `_model_export_plan`'s "system" branch for the full rationale.
        patient_qs = Patient.objects.all_institutions()
    elif mode == "single":
        patient_qs = Patient.objects.for_institution(value)
    else:  # "multi"
        patient_qs = Patient.objects.filter(institution__in=value)

    if date_start:
        patient_qs = patient_qs.filter(created_at__date__gte=date_start)
    if date_end:
        patient_qs = patient_qs.filter(created_at__date__lte=date_end)

    return mode, value, patient_qs


def _model_export_plan(institution_or_institutions=None, system_wide=False, date_start=None, date_end=None):
    """
    Build the fixed, ordered 13-model export list as (json_key, queryset)
    pairs, each queryset scoped using one of the three scoping shapes
    decided in ARCHITECTURE-SPINE.md AD-3 / epic-1-context.md:

      1. Patient carries a scoped manager (`InstitutionScopedManager`) ->
         `.for_institution(institution)` (single) /
         `.filter(institution__in=...)` (multi) / `.all_institutions()`
         (system) -- via `_resolve_patient_qs`, Story 1.4 also optionally
         narrows this by `created_at`'s date (`date_start`/`date_end`).
      2. ReferralSent/ReferralReceived carry the same scoped manager, scoped
         the same three ways, but NEVER date-narrowed (referral models stay
         full institution-scope always, per spec -- the date filter is a
         `Patient`-only concept).
      3. ReferralMessage has NEITHER an `institution` FK NOR a scoped
         manager (verified against referral/models.py — it only carries
         `sender_institution`); scoped via `.filter(sender_institution=...)`
         / `.filter(sender_institution__in=...)` / `.all()`, also never
         date-narrowed.
      4. The 9 patient-linked models (Video, Attachment, GMAssessment,
         HINEAssessment, DevelopmentalAssessment, CDICRecord,
         GeneralPaediatricAssessment, Problem, and ProblemAction via its
         `problem__patient` path) are all filtered relative to the already
         institution-*and*-date-scoped `patient_qs` (`patient__in=patient_qs`
         / `problem__patient__in=patient_qs`) rather than each re-deriving
         its own institution filter -- this is how the date filter reaches
         them too.

    `institution_or_institutions` accepts a single Institution instance
    (Story 1.1's exact single-institution call shape, reproduced byte-for-
    byte) or an iterable of Institution instances (Story 1.2's explicit
    multi-institution subset); `system_wide=True` ignores it entirely.
    `date_start`/`date_end` (Story 1.4) are optional and independent of each
    other (an open-ended range is allowed); both `None` reproduces Stories
    1.1-1.3's exact unfiltered-by-date behavior.
    """
    Patient = apps.get_model('patients', 'Patient')
    ReferralSent = apps.get_model('referral', 'ReferralSent')
    ReferralReceived = apps.get_model('referral', 'ReferralReceived')
    ReferralMessage = apps.get_model('referral', 'ReferralMessage')
    Video = apps.get_model('video', 'Video')
    Attachment = apps.get_model('patients', 'Attachment')
    GMAssessment = apps.get_model('patients', 'GMAssessment')
    HINEAssessment = apps.get_model('patients', 'HINEAssessment')
    DevelopmentalAssessment = apps.get_model('patients', 'DevelopmentalAssessment')
    CDICRecord = apps.get_model('patients', 'CDICRecord')
    GeneralPaediatricAssessment = apps.get_model('patients', 'GeneralPaediatricAssessment')
    Problem = apps.get_model('problemlist', 'Problem')
    ProblemAction = apps.get_model('problemlist', 'ProblemAction')

    mode, value, patient_qs = _resolve_patient_qs(
        institution_or_institutions, system_wide, date_start=date_start, date_end=date_end
    )

    if mode == "system":
        # Intentionally unfiltered by Institution.is_active: unlike the
        # `multi` mode's institution-*selection* list (BackupScopeForm only
        # offers active institutions to choose from), a system-wide export
        # is meant to be a complete point-in-time snapshot of everything,
        # including data belonging to since-deactivated institutions.
        referral_sent_qs = ReferralSent.objects.all_institutions()
        referral_received_qs = ReferralReceived.objects.all_institutions()
        referral_message_qs = ReferralMessage.objects.all()
    elif mode == "single":
        institution = value
        referral_sent_qs = ReferralSent.objects.for_institution(institution)
        referral_received_qs = ReferralReceived.objects.for_institution(institution)
        referral_message_qs = ReferralMessage.objects.filter(sender_institution=institution)
    else:  # "multi"
        institutions = value
        referral_sent_qs = ReferralSent.objects.filter(institution__in=institutions)
        referral_received_qs = ReferralReceived.objects.filter(institution__in=institutions)
        referral_message_qs = ReferralMessage.objects.filter(sender_institution__in=institutions)

    video_qs = Video.objects.filter(patient__in=patient_qs)
    attachment_qs = Attachment.objects.filter(patient__in=patient_qs)
    gm_qs = GMAssessment.objects.filter(patient__in=patient_qs)
    hine_qs = HINEAssessment.objects.filter(patient__in=patient_qs)
    dev_qs = DevelopmentalAssessment.objects.filter(patient__in=patient_qs)
    cdic_qs = CDICRecord.objects.filter(patient__in=patient_qs)
    gpa_qs = GeneralPaediatricAssessment.objects.filter(patient__in=patient_qs)
    problem_qs = Problem.objects.filter(patient__in=patient_qs)
    problem_action_qs = ProblemAction.objects.filter(problem__patient__in=patient_qs)

    return [
        (_model_key(Patient), patient_qs),
        (_model_key(ReferralSent), referral_sent_qs),
        (_model_key(ReferralReceived), referral_received_qs),
        (_model_key(ReferralMessage), referral_message_qs),
        (_model_key(Video), video_qs),
        (_model_key(Attachment), attachment_qs),
        (_model_key(GMAssessment), gm_qs),
        (_model_key(HINEAssessment), hine_qs),
        (_model_key(DevelopmentalAssessment), dev_qs),
        (_model_key(CDICRecord), cdic_qs),
        (_model_key(GeneralPaediatricAssessment), gpa_qs),
        (_model_key(Problem), problem_qs),
        (_model_key(ProblemAction), problem_action_qs),
    ]


def _safe_file_size(file_field):
    try:
        return file_field.size if file_field else 0
    except (OSError, ValueError):
        return 0


def estimate_export_size_bytes(institution_or_institutions=None, system_wide=False, date_start=None, date_end=None):
    """
    Rough size estimate (media only — db_export.json is negligible by
    comparison). Accepts the same three scope shapes as `_model_export_plan`
    (single Institution / iterable of Institutions / system_wide=True), plus
    Story 1.4's optional `date_start`/`date_end` -- resolved via the same
    `_resolve_patient_qs` helper `_model_export_plan` uses, so the estimate
    stays accurate (smaller) under a date filter instead of over-counting
    media belonging to patients the filter would actually exclude.
    """
    Video = apps.get_model('video', 'Video')
    Attachment = apps.get_model('patients', 'Attachment')

    _mode, _value, patient_qs = _resolve_patient_qs(
        institution_or_institutions, system_wide, date_start=date_start, date_end=date_end
    )
    video_qs = Video.objects.filter(patient__in=patient_qs)
    attachment_qs = Attachment.objects.filter(patient__in=patient_qs)

    total = 0
    for video in video_qs.iterator():
        total += _safe_file_size(video.video_file)
    for attachment in attachment_qs.iterator():
        # A recorded file_size of exactly 0 is a real, if unusual, value —
        # only fall back to a live filesystem check when it's genuinely unset.
        total += (
            attachment.file_size
            if attachment.file_size is not None
            else _safe_file_size(attachment.attachment)
        )
    return total


def has_sufficient_disk_space(institution_or_institutions=None, system_wide=False, date_start=None, date_end=None):
    """
    Disk-capacity pre-check (I/O matrix: 'Insufficient disk'). Accepts the
    same three scope shapes as `_model_export_plan`, plus Story 1.4's
    optional `date_start`/`date_end`.

    Returns (is_sufficient, estimated_bytes, required_free_bytes, actual_free_bytes).
    """
    estimated = estimate_export_size_bytes(
        institution_or_institutions, system_wide=system_wide, date_start=date_start, date_end=date_end
    )
    required = int(estimated * DISK_SAFETY_MULTIPLIER) + DISK_SAFETY_MINIMUM_BYTES
    free = shutil.disk_usage(settings.BASE_DIR).free
    return free >= required, estimated, required, free


def _copy_media_file(zf, file_field):
    """
    Chunked copy of one media file into the open zip — never a whole-file
    .read(). Returns (skip_reason_or_None, checksum_or_None, arcname):

      - `arcname` (the "media/<name>" string this file was/would be written
        under) is always returned, computed exactly once here, so callers
        never independently recompute it and risk drifting out of sync with
        the name actually passed to `zf.open()`.
      - success: (None, sha256_hexdigest, arcname) -- the hash is
        accumulated inline during the same chunked read/write loop that
        copies the file, so there is never a second read-through just to
        hash it.
      - skipped: (short human-readable description, None, arcname) -- the
        caller aggregates these into the job's error_message (see I/O
        matrix: 'Media file missing/unreadable during export' — the job
        still completes, but the admin must be told) and the file is absent
        from `manifest.json`'s `checksums` (it was never written to the
        zip).
    """
    arcname = f"media/{file_field.name}"

    try:
        source_path = file_field.path
    except (ValueError, OSError) as e:
        logger.warning("Backup export: media file has no accessible path (%r); skipping.", file_field)
        return f"{file_field.name}: no accessible path ({e})", None, arcname

    if not os.path.exists(source_path):
        logger.warning("Backup export: media file missing on disk (%s); skipping.", source_path)
        return f"{file_field.name}: file missing on disk", None, arcname

    hasher = hashlib.sha256()
    try:
        with open(source_path, "rb") as src, zf.open(arcname, "w") as dest:
            while chunk := src.read(COPY_CHUNK_SIZE):
                hasher.update(chunk)
                dest.write(chunk)
    except OSError as e:
        logger.exception("Backup export: failed to copy media file %s", source_path)
        return f"{file_field.name}: copy failed ({e})", None, arcname

    return None, hasher.hexdigest(), arcname


def _compute_schema_version():
    """
    SHA-256 over the sorted "<app_label>.<name>" list of every currently-
    applied migration -- a stable fingerprint of the DB schema this export
    was taken against (Epic 2's restore-side compatibility check consumes
    this; Story 1.3 only produces it).
    """
    applied = MigrationRecorder(connection).applied_migrations()
    labels = sorted(f"{app_label}.{name}" for app_label, name in applied)
    hasher = hashlib.sha256()
    hasher.update("\n".join(labels).encode("utf-8"))
    return hasher.hexdigest()


def create_export(job, progress_callback=None):
    """
    Stream `job`'s institution-scoped export into
    BASE_DIR/backups/<job_id>/<job_id>.zip as db_export.json + media/... +
    manifest.json.

    One model's queryset at a time via `.iterator()`, one record at a time —
    never a full model or the whole archive buffered in memory. Media files
    referenced by exported Video/Attachment rows are copied via a chunked
    read/write loop that also accumulates each file's SHA-256 inline (Story
    1.3) during that same copy pass — no *individual file* is ever read
    twice to hash it.

    `manifest.json` (Story 1.3) is written into the same open zip as a third
    member, after both the DB pass and the media pass have completed (its
    `record_counts`/`checksums` values are only fully known at that point).
    The whole-archive SHA-256 is the one deliberate exception to the
    never-read-twice rule above: by design, it requires one full second
    read of the finished `.zip` from disk (chunked, never a whole-file
    read()), computed after the `zipfile.ZipFile` context manager closes —
    there is no way to know an archive's own hash before the archive is
    finished.

    Returns (archive_path, skipped_media, archive_checksum) —
    `skipped_media` is a list of short descriptions for any media file that
    couldn't be copied (missing, unreadable, etc); the export still
    completes even when non-empty (see I/O matrix: 'Media file
    missing/unreadable during export' — a human confirmed 'complete with a
    warning' over 'fail the whole job').
    """
    Institution = apps.get_model('institution', 'Institution')

    if job.scope_type == BackupJobScopeType.SYSTEM:
        system_wide = True
        scope_arg = None
        # System-wide is a complete point-in-time snapshot -- intentionally
        # unfiltered by is_active, mirroring `_model_export_plan`'s "system"
        # branch, so an archive's manifest lists every institution its data
        # could actually contain, including since-deactivated ones.
        institutions = list(Institution.objects.order_by('slug').values_list('slug', flat=True))
    elif job.scope_type == BackupJobScopeType.MULTI:
        system_wide = False
        scope_arg = list(job.scopes.all())
        if not scope_arg:
            # The trigger view never creates a multi job with an empty
            # `scopes` set (BackupScopeForm refuses it before any row is
            # created) -- reaching here means the institutions were removed
            # from `scopes` after job creation. Fail loudly rather than
            # silently exporting nothing.
            raise ValueError(f"BackupJob {job.id} has scope_type=multi but no institutions in scopes.")
        institutions = sorted(inst.slug for inst in scope_arg)
    else:
        system_wide = False
        scope_arg = job.scope
        if scope_arg is None:
            # Story 1.1 never creates a scope_type=single job with scope=None
            # itself -- reaching here means the institution was deleted
            # after this job was created. Fail loudly rather than silently
            # exporting nothing.
            raise ValueError(f"BackupJob {job.id} has no scope institution (institution deleted?).")
        institutions = [scope_arg.slug]

    # Computed up front, before any file I/O starts: a failure querying the
    # migrations table must fail fast, not discard an already-completed
    # DB+media pass over a multi-GB archive.
    schema_version = _compute_schema_version()

    # Story 1.4: the real applied date filter, recorded on the job at
    # trigger time (null/null for every pre-1.4 job and any job triggered
    # without a date range -- see `manifest` below).
    date_start = job.date_filter_start
    date_end = job.date_filter_end

    archive_dir = get_archive_dir(job)
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = get_archive_path(job)

    plan = _model_export_plan(scope_arg, system_wide=system_wide, date_start=date_start, date_end=date_end)
    total_models = len(plan)
    media_sources = []
    record_counts = {}
    checksums = {}

    with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        db_hasher = hashlib.sha256()
        with zf.open("db_export.json", "w") as f:
            def _write(chunk_bytes):
                db_hasher.update(chunk_bytes)
                f.write(chunk_bytes)

            _write(b"{")
            for i, (label, qs) in enumerate(plan):
                if i:
                    _write(b",")
                _write(json.dumps(label).encode("utf-8") + b":[")

                count = 0
                for j, obj in enumerate(qs.iterator()):
                    if j:
                        _write(b",")
                    record = serializers.serialize("python", [obj])[0]
                    _write(json.dumps(record, cls=DjangoJSONEncoder).encode("utf-8"))
                    count += 1

                    if label == VIDEO_MODEL_KEY and obj.video_file:
                        media_sources.append(obj.video_file)
                    elif label == ATTACHMENT_MODEL_KEY and obj.attachment:
                        media_sources.append(obj.attachment)

                _write(b"]")
                record_counts[label] = count
                if progress_callback:
                    # DB pass = 0-80% of overall progress.
                    progress_callback(int((i + 1) / total_models * 80))
            _write(b"}")

        checksums["db_export.json"] = db_hasher.hexdigest()

        total_media = len(media_sources)
        skipped_media = []
        for k, file_field in enumerate(media_sources):
            skip_reason, media_checksum, arcname = _copy_media_file(zf, file_field)
            if skip_reason:
                skipped_media.append(skip_reason)
            elif arcname in checksums:
                # Two exported media files resolved to the same archive
                # member name (e.g. a shared/reused underlying file). Both
                # remain physically in the zip (zipfile permits duplicate
                # member names), but the manifest must never silently drop
                # the first file's checksum by overwriting it with the
                # second's -- flag the second occurrence instead.
                skipped_media.append(f"{file_field.name}: duplicate archive member, skipped")
            else:
                checksums[arcname] = media_checksum
            if progress_callback and total_media:
                # Media pass = 80-100% of overall progress.
                progress_callback(80 + int((k + 1) / total_media * 20))

        # manifest.json is the one deliberate, bounded exception to this
        # module's "never buffer a whole structure in memory" rule: unlike
        # db_export.json/media (arbitrarily large), its size is bounded by
        # the fixed model count (13) plus the number of media files in this
        # archive, so building it as a single in-memory dict is safe.
        manifest = {
            "source_job_id": job.id,
            "manifest_version": 1,  # shape of manifest.json itself -- distinct from schema_version (the DB schema fingerprint); bump if these fields change.
            "schema_version": schema_version,
            "checksum_algorithm": "sha256",
            "scope_type": job.scope_type,
            "institutions": institutions,
            "record_counts": record_counts,
            "checksums": checksums,
            "generated_at": timezone.now().isoformat(),
            "generated_by": job.triggered_by.username if job.triggered_by else "",
            # Story 1.4: the real applied date filter -- "applied" is True
            # whenever either bound was set (an open-ended one-sided range
            # still counts as applied). `date_start`/`date_end` are plain
            # `datetime.date` objects; DjangoJSONEncoder serializes them as
            # ISO date strings, matching the pre-1.4 stub's shape exactly
            # when both are None.
            "date_filter": {
                "applied": bool(date_start or date_end),
                "start": date_start,
                "end": date_end,
            },
        }
        with zf.open("manifest.json", "w") as mf:
            mf.write(json.dumps(manifest, cls=DjangoJSONEncoder).encode("utf-8"))

    # Whole-archive checksum: hashed from the finished .zip on disk, after
    # the ZipFile context manager has closed -- never embedded inside
    # manifest.json itself, and never a whole-file read().
    archive_hasher = hashlib.sha256()
    with open(archive_path, "rb") as af:
        while chunk := af.read(COPY_CHUNK_SIZE):
            archive_hasher.update(chunk)
    archive_checksum = archive_hasher.hexdigest()

    return archive_path, skipped_media, archive_checksum
