from django.db import models

class Position(models.TextChoices):
    MEDICAL_OFFICER = "Medical Officer", "Medical Officer"
    CONSULTANT = "Consultant", "Consultant"
    REGISTRAR = "Registrar", "Registrar"
    PHYSIOTHERAPIST = "Physiotherapist", "Physiotherapist"
    OCCUPATIONAL_THERAPIST = "Occupational Therapist", "Occupational Therapist"
    NURSING_OFFICER = "Nursing officer", "Nursing officer"
    SENIOR_REGISTRAR = "Senior Registrar", "Senior Registrar"
    SPEECH_THERAPIST = "Speech Therapist", "Speech Therapist"
    PSYCHOLOGIST = "Psychologist", "Psychologist"

# Keep the old POSSITION for backward compatibility
POSSITION = Position.choices

# Login Status Choices for UserActivityLog
LOGIN_STATUS_CHOICES = [
    ('success', 'Login Success'),
    ('failed', 'Login Failed'),
    ('logout', 'Logout'),
    ('admin', 'Admin Action'),
]

MODE_OF_DELIVERY = (
    ("Normal vaginal delivery (NVD)", "Normal vaginal delivery (NVD)"),
    ("Assisted vaginal delivery (AVD)", "Assisted vaginal delivery (AVD)"),
    ("Forcep delivery", "Forcep delivery"),
    ("Vacume delivery", "Vacume delivery"),
    ("Emergency LSCS", "Emergency LSCS"),
    ("Elective LSCS", "Elective LSCS"),
    ("VBAC", "Vaginal birth after CS (VBAC)"),
    ("Home delivery", "Home delivery"),
    ("Other", "Other"),
)

GENDER = (("Male", "Male"), ("Female", "Female"), ("Undefine", "Undefine"))

BOOKMARK_TYPE = (
    ("Patient", "Patient"),
    ("Video", "Video"),
    ("GMA", "GMA"),
    ("HINE", "HINE"),
    ("Attachment", "Attachment"),
    ("DA", "DA"),
    ("CDICR", "CDICR"),
    ("GPA", "GPA"),
)

ATTACHMENT_TYPE = (("Photo", "Photo"), ("PDF", "PDF"), ("Video", "Video"))
DX_CONCLUTION = (("NORMAL", "NORMAL"), ("ABNORMAL", "ABNORMAL"))

# Report Configuration Value Types
class ConfigValueTypes(models.TextChoices):
    STRING = "STRING", "String"
    INTEGER = "INTEGER", "Integer"
    BOOLEAN = "BOOLEAN", "Boolean"
    JSON = "JSON", "JSON"

LEVEL_OF_INDICATION = (("High", "High"), ("Medium", "Medium"), ("Low", "Low"))

POG_WKS = (
    (20, "20"),
    (21, "21"),
    (22, "22"),
    (23, "23"),
    (24, "24"),
    (25, "25"),
    (26, "26"),
    (27, "27"),
    (28, "28"),
    (29, "29"),
    (30, "30"),
    (31, "31"),
    (32, "32"),
    (33, "33"),
    (34, "34"),
    (35, "35"),
    (36, "36"),
    (37, "37"),
    (38, "38"),
    (39, "39"),
    (40, "40"),
    (41, "41"),
    (42, "42"),
)

POG_DAYS = (
    (0, "0"),
    (1, "1"),
    (2, "2"),
    (3, "3"),
    (4, "4"),
    (5, "5"),
    (6, "6"),
)

APGAR = (
    (0, "0"),
    (1, "1"),
    (2, "2"),
    (3, "3"),
    (4, "4"),
    (5, "5"),
    (6, "6"),
    (7, "7"),
    (8, "8"),
    (9, "9"),
    (10, "10"),
)

# Video-related choices
VIDEO_FORMATS = [
    ("mp4", "MP4"),
    ("mov", "MOV/QuickTime"),
    ("avi", "AVI"),
    ("mkv", "MKV"),
    ("webm", "WebM"),
]

QUALITY_CHOICES = [
    ("original", "Original Quality"),
    ("high", "High Quality (1080p)"),
    ("medium", "Medium Quality (720p)"),
    ("low", "Low Quality (480p)"),
    ("mobile", "Mobile Quality (360p)"),
]

PROCESSING_STATUS = [
    ("pending", "Pending Upload"),
    ("uploading", "Uploading"),
    ("processing", "Processing"),
    ("completed", "Completed"),
    ("failed", "Failed"),
]
    
ACCESS_LEVEL_CHOICES = [
    ("restricted", "Restricted"),
    ("team", "Team Access"),
    ("department", "Department Access"),
    ("public", "Public Access"),
]

# Attachment-related choices
ATTACHMENT_TYPE_CHOICES = [
    ("image", "Image"),
    ("pdf", "PDF Document"),
    ("video", "Video File"),
    ("document", "Document"),
    ("other", "Other"),
]

ATTACHMENT_ACCESS_LEVEL_CHOICES = [
    ("restricted", "Restricted Access"),
    ("team", "Team Access"),
    ("department", "Department Access"),
    ("general", "General Access"),
]

SCAN_RESULT_CHOICES = [
    ("pending", "Scan Pending"),
    ("clean", "Clean"),
    ("infected", "Infected"),
    ("error", "Scan Error"),
]

# File size limits and allowed extensions
FILE_SIZE_LIMITS = {
    "MAX_FILE_SIZE": 100 * 1024 * 1024,  # 100MB
    "MAX_IMAGE_SIZE": 10 * 1024 * 1024,  # 10MB for images
    "MAX_VIDEO_SIZE": 2 * 1024 * 1024 * 1024,  # 2GB for videos
}

ALLOWED_EXTENSIONS = {
    "image": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
    "pdf": [".pdf"],
    "video": [".mp4", ".mov", ".avi", ".mkv", ".webm"],
    "document": [".doc", ".docx", ".txt", ".rtf", ".odt"],
}

# Subscription Type Choices
SUBSCRIPTION_TYPE_CHOICES = [
    ('free', 'Free'),
    ('commercial', 'Commercial'),
]

# Subscription Status Choices
SUBSCRIPTION_STATUS_CHOICES = [
    ('active', 'Active'),
    ('expired', 'Expired'),
    ('grace_period', 'Grace Period'),
]

# User Type TextChoices (Phase 2 — Multi-Institution)
class UserType(models.TextChoices):
    USER = 'USER', 'Clinician / User'
    ADMIN = 'ADMIN', 'Institution Admin'
    SUPERADMIN = 'SUPERADMIN', 'Super Admin'


# Subscription Status TextChoices (Phase 2 — Multi-Institution)
class SubscriptionStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    GRACE = 'GRACE', 'Grace Period'
    EXPIRED = 'EXPIRED', 'Expired'


# Referral lifecycle status (Phase 2 — Referral System, Story 4.1 — FR64)
class ReferralStatus(models.TextChoices):
    """
    Referral lifecycle status — FR64.
    PENDING → REPLIED → CLOSED (one-way progression).
    """
    PENDING = 'PENDING', 'Pending'
    REPLIED = 'REPLIED', 'Replied'
    CLOSED  = 'CLOSED',  'Closed'


# Notification types for referral lifecycle events (Phase 2 — Story 5.1 — FR67-FR69)
class NotificationType(models.TextChoices):
    """In-app notification types: referral lifecycle events and backup/restore job outcomes."""
    REFERRAL_RECEIVED = 'REFERRAL_RECEIVED', 'Referral Received'
    REFERRAL_REPLIED  = 'REFERRAL_REPLIED',  'Referral Replied'
    REFERRAL_CLOSED   = 'REFERRAL_CLOSED',   'Referral Closed'
    BACKUP_COMPLETED  = 'BACKUP_COMPLETED',  'Backup Completed'
    BACKUP_FAILED     = 'BACKUP_FAILED',     'Backup Failed'
    RESTORE_COMPLETED = 'RESTORE_COMPLETED', 'Restore Completed'
    RESTORE_FAILED    = 'RESTORE_FAILED',    'Restore Failed'


# Problem List Choices
class PROBLEM_STATUS(models.TextChoices):
    ACTIVE = "active", "Active"
    RESOLVED = "resolved", "Resolved"
    CHRONIC = "chronic", "Chronic"
    INACTIVE = "inactive", "Inactive"

class SEVERITY_CHOICES(models.TextChoices):
    MILD = "mild", "Mild"
    MODERATE = "moderate", "Moderate"
    SEVERE = "severe", "Severe"
    LIFE_THREATENING = "life_threatening", "Life Threatening"


# Backup/Restore job tracking (Epic 1/2 — SPEC-backup-restore)
class BackupJobType(models.TextChoices):
    """Job kinds tracked by BackupJob. BACKUP is Story 1.1's; RESTORE and
    PRE_RESTORE_SNAPSHOT are Story 2.3's (a restore and the snapshot it takes first)."""
    BACKUP = 'backup', 'Backup'
    RESTORE = 'restore', 'Restore'
    PRE_RESTORE_SNAPSHOT = 'pre_restore_snapshot', 'Pre-Restore Snapshot'


class BackupJobStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    RUNNING = 'running', 'Running'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class BackupJobScopeType(models.TextChoices):
    """
    Institution-scoping shape for a BackupJob (Story 1.2). Only SUPERADMIN
    may choose MULTI/SYSTEM; ADMIN (and a superadmin with no elevated
    selection made) is always coerced server-side to SINGLE.
    """
    SINGLE = 'single', 'Single Institution'
    MULTI = 'multi', 'Multiple Institutions'
    SYSTEM = 'system', 'System-Wide'


# Restore upload validation (Epic 2, Story 2.1)
class RestoreUploadStatus(models.TextChoices):
    """Lifecycle of a staged restore archive upload."""
    VALIDATING = 'validating', 'Validating'
    VALIDATED = 'validated', 'Validated'
    CONFIRMED = 'confirmed', 'Confirmed'
    APPLYING = 'applying', 'Applying'
    APPLIED = 'applied', 'Applied'
    REJECTED = 'rejected', 'Rejected'
    FAILED = 'failed', 'Failed'


class RestoreAuthenticity(models.TextChoices):
    """Whether the archive's origin was confirmed against a local BackupJob."""
    VERIFIED = 'verified', 'Verified'
    UNVERIFIED = 'unverified', 'Unverified origin'


class RestoreRejectionCode(models.TextChoices):
    """One value per specific reason a restore archive is rejected."""
    # Stage 1 -- zip safety
    NOT_A_ZIP = 'not_a_zip', 'Not a valid zip archive'
    ENCRYPTED_MEMBER = 'encrypted_member', 'Archive contains an encrypted member'
    DUPLICATE_MEMBER = 'duplicate_member', 'Archive contains duplicate member names'
    UNEXPECTED_MEMBER = 'unexpected_member', 'Archive contains an unexpected member'
    UNSAFE_MEMBER_PATH = 'unsafe_member_path', 'Archive contains an unsafe member path'
    SYMLINK_MEMBER = 'symlink_member', 'Archive contains a symlink'
    EXCESSIVE_EXPANSION = 'excessive_expansion', 'Archive expands implausibly'
    # Stage 2 -- manifest
    MANIFEST_MISSING = 'manifest_missing', 'manifest.json is missing'
    MANIFEST_INVALID = 'manifest_invalid', 'manifest.json is invalid'
    MANIFEST_UNSUPPORTED = 'manifest_unsupported', 'Unsupported manifest version or algorithm'
    DB_EXPORT_MISSING = 'db_export_missing', 'db_export.json is missing'
    # Stage 3 -- schema
    SCHEMA_MISMATCH = 'schema_mismatch', 'Schema version mismatch'
    # Stage 4 -- origin authenticity
    ARCHIVE_CHECKSUM_MISMATCH = 'archive_checksum_mismatch', 'Archive checksum mismatch'
    ORIGIN_NOT_VERIFIABLE = 'origin_not_verifiable', 'Origin cannot be verified'
    # Stage 5 -- per-file checksums
    FILE_MISSING = 'file_missing', 'A listed file is missing from the archive'
    FILE_NOT_LISTED = 'file_not_listed', 'An archive file is not listed in the manifest'
    FILE_CHECKSUM_MISMATCH = 'file_checksum_mismatch', 'File checksum mismatch'
