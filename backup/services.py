"""
Backup export service — Story 1.1.

`create_export(job)` is the only place that touches the 13-model export
list and the archive layout. `backup/views.py` is the sole caller into this
module (directly, for the disk-space pre-check, and indirectly via
`backup/management/commands/run_backup.py`) — no other app may call into
this service layer directly, so permissions/rate-limiting/audit logging in
the trigger view can't be bypassed by a second code path.
"""
import json
import logging
import os
import shutil
import zipfile

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder

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


def _model_export_plan(institution):
    """
    Build the fixed, ordered 13-model export list as (json_key, queryset)
    pairs, each queryset scoped to `institution` using one of the three
    scoping shapes decided in ARCHITECTURE-SPINE.md AD-3:

      1. Patient, ReferralSent, ReferralReceived carry a scoped manager
         (`InstitutionScopedManager`) -> `.for_institution(institution)`.
      2. ReferralMessage has NEITHER an `institution` FK NOR a scoped
         manager (verified against referral/models.py — it only carries
         `sender_institution`); scoped via `.filter(sender_institution=...)`
         instead of `.for_institution()` as a deliberate, verified deviation
         from the illustrative Design Notes.
      3. Models with a direct `patient` FK -> `.filter(patient__institution=...)`.
      4. ProblemAction (only a `problem` FK) ->
         `.filter(problem__patient__institution=...)`.
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

    return [
        (_model_key(Patient), Patient.objects.for_institution(institution)),
        (_model_key(ReferralSent), ReferralSent.objects.for_institution(institution)),
        (_model_key(ReferralReceived), ReferralReceived.objects.for_institution(institution)),
        (_model_key(ReferralMessage), ReferralMessage.objects.filter(sender_institution=institution)),
        (_model_key(Video), Video.objects.filter(patient__institution=institution)),
        (_model_key(Attachment), Attachment.objects.filter(patient__institution=institution)),
        (_model_key(GMAssessment), GMAssessment.objects.filter(patient__institution=institution)),
        (_model_key(HINEAssessment), HINEAssessment.objects.filter(patient__institution=institution)),
        (_model_key(DevelopmentalAssessment), DevelopmentalAssessment.objects.filter(patient__institution=institution)),
        (_model_key(CDICRecord), CDICRecord.objects.filter(patient__institution=institution)),
        (_model_key(GeneralPaediatricAssessment), GeneralPaediatricAssessment.objects.filter(patient__institution=institution)),
        (_model_key(Problem), Problem.objects.filter(patient__institution=institution)),
        (_model_key(ProblemAction), ProblemAction.objects.filter(problem__patient__institution=institution)),
    ]


def _safe_file_size(file_field):
    try:
        return file_field.size if file_field else 0
    except (OSError, ValueError):
        return 0


def estimate_export_size_bytes(institution):
    """Rough size estimate (media only — db_export.json is negligible by comparison)."""
    Video = apps.get_model('video', 'Video')
    Attachment = apps.get_model('patients', 'Attachment')

    total = 0
    for video in Video.objects.filter(patient__institution=institution).iterator():
        total += _safe_file_size(video.video_file)
    for attachment in Attachment.objects.filter(patient__institution=institution).iterator():
        # A recorded file_size of exactly 0 is a real, if unusual, value —
        # only fall back to a live filesystem check when it's genuinely unset.
        total += (
            attachment.file_size
            if attachment.file_size is not None
            else _safe_file_size(attachment.attachment)
        )
    return total


def has_sufficient_disk_space(institution):
    """
    Disk-capacity pre-check (I/O matrix: 'Insufficient disk').

    Returns (is_sufficient, estimated_bytes, required_free_bytes, actual_free_bytes).
    """
    estimated = estimate_export_size_bytes(institution)
    required = int(estimated * DISK_SAFETY_MULTIPLIER) + DISK_SAFETY_MINIMUM_BYTES
    free = shutil.disk_usage(settings.BASE_DIR).free
    return free >= required, estimated, required, free


def _copy_media_file(zf, file_field):
    """
    Chunked copy of one media file into the open zip — never a whole-file
    .read(). Returns None on success, or a short human-readable description
    of what was skipped and why (the caller aggregates these into the job's
    error_message — see I/O matrix: 'Media file missing/unreadable during
    export' — the job still completes, but the admin must be told).
    """
    try:
        source_path = file_field.path
    except (ValueError, OSError) as e:
        logger.warning("Backup export: media file has no accessible path (%r); skipping.", file_field)
        return f"{file_field.name}: no accessible path ({e})"

    if not os.path.exists(source_path):
        logger.warning("Backup export: media file missing on disk (%s); skipping.", source_path)
        return f"{file_field.name}: file missing on disk"

    arcname = f"media/{file_field.name}"
    try:
        with open(source_path, "rb") as src, zf.open(arcname, "w") as dest:
            shutil.copyfileobj(src, dest, length=COPY_CHUNK_SIZE)
    except OSError as e:
        logger.exception("Backup export: failed to copy media file %s", source_path)
        return f"{file_field.name}: copy failed ({e})"

    return None


def create_export(job, progress_callback=None):
    """
    Stream `job`'s institution-scoped export into
    BASE_DIR/backups/<job_id>/<job_id>.zip as db_export.json + media/...

    One model's queryset at a time via `.iterator()`, one record at a time —
    never a full model or the whole archive buffered in memory. Media files
    referenced by exported Video/Attachment rows are copied via chunked
    `shutil.copyfileobj`.

    Returns (archive_path, skipped_media) — `skipped_media` is a list of
    short descriptions for any media file that couldn't be copied (missing,
    unreadable, etc); the export still completes even when non-empty (see
    I/O matrix: 'Media file missing/unreadable during export' — a human
    confirmed 'complete with a warning' over 'fail the whole job').
    """
    institution = job.scope
    if institution is None:
        # Story 1.1 never creates a job with scope=None itself (that's
        # Epic 1.2's system-wide case) -- reaching here means the
        # institution was deleted after this job was created. Fail loudly
        # rather than silently exporting nothing.
        raise ValueError(f"BackupJob {job.id} has no scope institution (institution deleted?).")

    archive_dir = get_archive_dir(job)
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = get_archive_path(job)

    plan = _model_export_plan(institution)
    total_models = len(plan)
    media_sources = []

    with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        with zf.open("db_export.json", "w") as f:
            f.write(b"{")
            for i, (label, qs) in enumerate(plan):
                if i:
                    f.write(b",")
                f.write(json.dumps(label).encode("utf-8") + b":[")

                for j, obj in enumerate(qs.iterator()):
                    if j:
                        f.write(b",")
                    record = serializers.serialize("python", [obj])[0]
                    f.write(json.dumps(record, cls=DjangoJSONEncoder).encode("utf-8"))

                    if label == VIDEO_MODEL_KEY and obj.video_file:
                        media_sources.append(obj.video_file)
                    elif label == ATTACHMENT_MODEL_KEY and obj.attachment:
                        media_sources.append(obj.attachment)

                f.write(b"]")
                if progress_callback:
                    # DB pass = 0-80% of overall progress.
                    progress_callback(int((i + 1) / total_models * 80))
            f.write(b"}")

        total_media = len(media_sources)
        skipped_media = []
        for k, file_field in enumerate(media_sources):
            skip_reason = _copy_media_file(zf, file_field)
            if skip_reason:
                skipped_media.append(skip_reason)
            if progress_callback and total_media:
                # Media pass = 80-100% of overall progress.
                progress_callback(80 + int((k + 1) / total_media * 20))

    return archive_path, skipped_media
