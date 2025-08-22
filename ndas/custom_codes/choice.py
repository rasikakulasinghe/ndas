from django.db import models

class Position(models.TextChoices):
    MEDICAL_OFFICER = "Medical Officer", "Medical Officer"
    CONSULTANT = "Consultant", "Consultant"
    REGISTRAR = "Registrar", "Registrar"
    PHYSIOTHERAPIST = "Physiotherapist", "Physiotherapist"
    OCCUPATIONAL_THERAPIST = "Occupational Therapist", "Occupational Therapist"
    ADMINISTRATOR = "Administrator", "Administrator"
    NURSING_OFFICER = "Nursing officer", "Nursing officer"
    SENIOR_REGISTRAR = "Senior Registrar", "Senior Registrar"

# Keep the old POSSITION for backward compatibility
POSSITION = Position.choices

# Login Status Choices for UserActivityLog
LOGIN_STATUS_CHOICES = [
    ('success', 'Login Success'),
    ('failed', 'Login Failed'),
    ('logout', 'Logout'),
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
)

ATTACHMENT_TYPE = (("Photo", "Photo"), ("PDF", "PDF"), ("Video", "Video"))
DX_CONCLUTION = (("NORMAL", "NORMAL"), ("ABNORMAL", "ABNORMAL"))

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
