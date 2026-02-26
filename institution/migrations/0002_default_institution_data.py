# institution/migrations/0002_default_institution_data.py

import os
import shutil
import logging
from datetime import timedelta, date
from django.db import migrations
from django.conf import settings

logger = logging.getLogger(__name__)


# Status mapping: old Subscription.status (lowercase) → new SubscriptionStatus (uppercase)
_SUBSCRIPTION_STATUS_MAP = {
    'active': 'ACTIVE',
    'expired': 'EXPIRED',
    'grace_period': 'GRACE',
}


def migrate_to_default_institution(apps, schema_editor):
    """
    Atomic data migration: create default_institution from existing Subscription singleton,
    then assign all existing Patients, Users, and file records to it.

    Physical media files are moved to the institution-partitioned directory structure.
    File move failures are logged as warnings but do NOT abort the migration.
    """
    from django.db import transaction

    Institution = apps.get_model('institution', 'Institution')
    Subscription = apps.get_model('users', 'Subscription')
    Patient = apps.get_model('patients', 'Patient')
    CustomUser = apps.get_model('users', 'CustomUser')
    Video = apps.get_model('video', 'Video')
    Attachment = apps.get_model('patients', 'Attachment')

    with transaction.atomic():
        # ── Step A: Resolve default institution config ───────────────────────
        default_name = getattr(settings, 'DEFAULT_INSTITUTION_NAME', 'Default Institution')
        default_slug = getattr(settings, 'DEFAULT_INSTITUTION_SLUG', 'default')

        # ── Step B: Read Subscription singleton ──────────────────────────────
        sub = Subscription.objects.filter(pk=1).first()

        # Map subscription fields
        if sub:
            old_status = sub.status  # 'active', 'expired', 'grace_period'
            new_status = _SUBSCRIPTION_STATUS_MAP.get(old_status, 'ACTIVE')
            subscription_start = sub.start_date
            # grace_period_end = expiration_date + grace_period_days
            expiration = sub.start_date + timedelta(days=sub.duration_days)
            grace_period_end = expiration + timedelta(days=sub.grace_period_days)
        else:
            # No subscription record exists — use safe defaults
            new_status = 'ACTIVE'
            subscription_start = date.today()
            grace_period_end = None

        # ── Step C: Create the default institution ────────────────────────────
        default_institution = Institution.objects.create(
            name=default_name,
            slug=default_slug,
            subscription_status=new_status,
            subscription_start=subscription_start,
            grace_period_end=grace_period_end,
            is_active=True,
        )

        # ── Step D: Assign all Patients to default_institution ────────────────
        patient_count = Patient.objects.filter(institution__isnull=True).update(
            institution=default_institution
        )
        logger.info(f"[Migration 0002] Assigned {patient_count} patients to {default_slug}")

        # ── Step E: Assign all non-SUPERADMIN Users to default_institution ────
        user_count = CustomUser.objects.filter(
            institution__isnull=True,
        ).exclude(
            user_type='SUPERADMIN'
        ).exclude(
            is_superuser=True
        ).update(institution=default_institution)
        logger.info(f"[Migration 0002] Assigned {user_count} users to {default_slug}")

        # ── Step F: Update Video file path references in DB ───────────────────
        _migrate_video_paths(Video, default_slug)

        # ── Step G: Update Attachment file path references in DB ──────────────
        _migrate_attachment_paths(Attachment, default_slug)

    # ── Step H: Move physical files on disk (OUTSIDE transaction) ────────────
    # File system operations cannot be rolled back — run after DB commit
    media_root = str(settings.MEDIA_ROOT)
    _move_physical_video_files(Video, default_slug, media_root)
    _move_physical_attachment_files(Attachment, default_slug, media_root)


def _migrate_video_paths(Video, default_slug):
    """
    Update Video.video_file DB field to use institution-partitioned path.

    Old path pattern: 'videos/{year}/{month}/{filename}'
    New path pattern: '{default_slug}/videos/{year}/{month}/{filename}'

    If old path does NOT start with 'videos/', prefix with '{slug}/videos/' as fallback.
    Already-migrated paths (starting with '{slug}/') are left unchanged (idempotent).
    """
    updated = 0
    for video in Video.objects.all().only('pk', 'video_file'):
        old_name = video.video_file.name if video.video_file else ''
        if not old_name or old_name.startswith(f'{default_slug}/'):
            continue  # Already migrated or empty

        if old_name.startswith('videos/'):
            # Replace 'videos/' prefix with '{slug}/videos/'
            new_name = f"{default_slug}/videos/{old_name[len('videos/'):]}"
        else:
            # Unknown prefix: just put under {slug}/videos/
            new_name = f"{default_slug}/videos/{os.path.basename(old_name)}"

        Video.objects.filter(pk=video.pk).update(video_file=new_name)
        updated += 1
    logger.info(f"[Migration 0002] Updated {updated} video file paths to {default_slug}/videos/")


def _migrate_attachment_paths(Attachment, default_slug):
    """
    Update Attachment.attachment DB field to use institution-partitioned path.

    Old path pattern: 'attachments/{filename}'
    New path pattern: '{default_slug}/attachments/{filename}'

    Already-migrated paths are left unchanged (idempotent).
    """
    updated = 0
    for att in Attachment.objects.all().only('pk', 'attachment'):
        old_name = att.attachment.name if att.attachment else ''
        if not old_name or old_name.startswith(f'{default_slug}/'):
            continue  # Already migrated or empty

        if old_name.startswith('attachments/'):
            new_name = f"{default_slug}/attachments/{old_name[len('attachments/'):]}"
        else:
            new_name = f"{default_slug}/attachments/{os.path.basename(old_name)}"

        Attachment.objects.filter(pk=att.pk).update(attachment=new_name)
        updated += 1
    logger.info(f"[Migration 0002] Updated {updated} attachment file paths to {default_slug}/attachments/")


def _move_physical_video_files(Video, default_slug, media_root):
    """
    Move physical video files from old paths to institution-partitioned paths on disk.

    Resilient: failures are logged as warnings, not raised — migration has already committed.
    """
    moved, skipped, failed = 0, 0, 0
    for video in Video.objects.all().only('pk', 'video_file'):
        new_name = video.video_file.name if video.video_file else ''
        if not new_name:
            continue

        # Derive old name: reverse the path migration
        # New: '{slug}/videos/...' → Old: 'videos/...'
        if new_name.startswith(f'{default_slug}/videos/'):
            old_relative = 'videos/' + new_name[len(f'{default_slug}/videos/'):]
        else:
            skipped += 1
            continue

        old_path = os.path.join(media_root, old_relative)
        new_path = os.path.join(media_root, new_name)

        if not os.path.exists(old_path):
            skipped += 1
            continue  # File not on this server (may be prod with separate storage)

        if os.path.exists(new_path):
            skipped += 1
            continue  # Already moved

        try:
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.move(old_path, new_path)
            moved += 1
        except OSError as e:
            logger.warning(f"[Migration 0002] Could not move video file {old_path} -> {new_path}: {e}")
            failed += 1

    logger.info(f"[Migration 0002] Video files: moved={moved}, skipped={skipped}, failed={failed}")
    if failed > 0:
        logger.warning(
            f"[Migration 0002] {failed} video file(s) could not be moved. "
            f"DB references are correct; run 'python manage.py fix_media_paths' manually to relocate files."
        )


def _move_physical_attachment_files(Attachment, default_slug, media_root):
    """
    Move physical attachment files from old paths to institution-partitioned paths on disk.
    """
    moved, skipped, failed = 0, 0, 0
    for att in Attachment.objects.all().only('pk', 'attachment'):
        new_name = att.attachment.name if att.attachment else ''
        if not new_name:
            continue

        if new_name.startswith(f'{default_slug}/attachments/'):
            old_relative = 'attachments/' + new_name[len(f'{default_slug}/attachments/'):]
        else:
            skipped += 1
            continue

        old_path = os.path.join(media_root, old_relative)
        new_path = os.path.join(media_root, new_name)

        if not os.path.exists(old_path):
            skipped += 1
            continue

        if os.path.exists(new_path):
            skipped += 1
            continue

        try:
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.move(old_path, new_path)
            moved += 1
        except OSError as e:
            logger.warning(f"[Migration 0002] Could not move attachment {old_path} -> {new_path}: {e}")
            failed += 1

    logger.info(f"[Migration 0002] Attachment files: moved={moved}, skipped={skipped}, failed={failed}")
    if failed > 0:
        logger.warning(
            f"[Migration 0002] {failed} attachment file(s) could not be moved. "
            f"DB references are correct; files can be relocated manually."
        )


def reverse_migration(apps, schema_editor):
    """
    Reverse this migration — deletes the default_institution record.

    IMPORTANT: Physical file moves CANNOT be reversed automatically.
    Reversing will attempt to delete the Institution record. This will fail with
    a django.db.models.ProtectedError if any Patient or CustomUser still FK-references it.
    Run only in a clean test environment.
    """
    Institution = apps.get_model('institution', 'Institution')
    default_slug = getattr(settings, 'DEFAULT_INSTITUTION_SLUG', 'default')
    Institution.objects.filter(slug=default_slug).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('institution', '0001_initial'),
        ('patients', '0008_alter_diagnosislist_options_and_more'),
        ('patients', '0009_alter_attachment_attachment'),
        ('video', '0007_alter_video_video_file'),
        ('users', '0009_customuser_institution_customuser_user_type'),
    ]

    operations = [
        migrations.RunPython(
            migrate_to_default_institution,
            reverse_code=reverse_migration,
        ),
    ]
