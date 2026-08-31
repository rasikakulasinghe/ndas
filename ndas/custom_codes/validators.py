import os, math, mimetypes, re, html, logging
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.validators import RegexValidator
from django.utils import timezone


def sanitize_text_input(value):
    """
    Sanitize text input to prevent XSS attacks while preserving medical notation.

    Security measures:
    - Removes HTML tags and script elements
    - Strips JavaScript event handlers and dangerous protocols
    - Preserves medical notation (e.g., "< 5 mg/dl", "> 38°C")
    - Normalizes whitespace

    Args:
        value (str): Input text to sanitize

    Returns:
        str: Sanitized text safe for storage and display

    Examples:
        >>> sanitize_text_input("Temperature > 38°C")
        "Temperature > 38°C"
        >>> sanitize_text_input("<script>alert('xss')</script>Test")
        "alert('xss')Test"
        >>> sanitize_text_input("BP < 120/80 mmHg")
        "BP < 120/80 mmHg"
    """
    if not value:
        return value

    # Convert to string if not already
    text = str(value)

    # Unescape HTML entities first to prevent double-encoding bypasses.
    # Without this, an entity-encoded payload like "&lt;script&gt;...&lt;/script&gt;"
    # contains no raw "<" characters when the strip regexes below run, so it
    # would pass every filter untouched and only become live markup afterward.
    # Decoding first ensures the strips below actually see (and remove) it.
    # Loop to a fixed point (bounded) rather than a single pass: html.unescape()
    # only decodes one layer per call, so a multiply-encoded payload like
    # "&amp;lt;script&amp;gt;" would otherwise still have one layer of
    # encoding left over after a single call, undecoded but also unstripped.
    for _ in range(3):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded

    # Remove script tags and their content (case insensitive)
    text = re.sub(
        r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL
    )
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)

    # Remove event handlers (onclick, onload, onerror, etc.)
    text = re.sub(r'\s*on\w+\s*=\s*["\']?[^"\']*["\']?', "", text, flags=re.IGNORECASE)

    # Remove dangerous protocols from URLs (javascript:, data:, vbscript:).
    # Browsers strip whitespace/control characters (tab, newline, CR, etc.) from
    # a URL before parsing its scheme, so "java\tscript:alert(1)" is still parsed
    # as a live javascript: URI even though the literal string "javascript:" never
    # appears. Match each protocol name with optional \s* between every character
    # so such obfuscated payloads are still recognized and stripped.
    #
    # Two guards keep this from over-matching ordinary prose (CLAUDE.md requires
    # preserving medical notation): a leading \b so "metadata:" (a word ending in
    # "data:") is not treated as the "data" protocol, and a `(?=\S)` lookahead so
    # "Data: BP 120/80" / "Investigation data: pending" (colon-then-space, the
    # normal English label pattern) are left untouched — a real dangerous URI
    # never has whitespace immediately after its scheme's colon.
    text = re.sub(
        r"\bj\s*a\s*v\s*a\s*s\s*c\s*r\s*i\s*p\s*t\s*:(?=\S)"
        r"|\bd\s*a\s*t\s*a\s*:(?=\S)"
        r"|\bv\s*b\s*s\s*c\s*r\s*i\s*p\s*t\s*:(?=\S)",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove HTML tags while preserving content
    # This regex preserves medical notation like "< 5" or "> 38"
    # by only matching tags that start with < followed by a letter
    text = re.sub(r"<(/)?([a-zA-Z][a-zA-Z0-9]*)[^>]*>", "", text)

    # Normalize whitespace (replace multiple spaces/tabs/newlines with single space)
    # Preserve single newlines for paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces/tabs to single space
    text = re.sub(r"\n\s*\n", "\n\n", text)  # Multiple newlines to double newline

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def sanitize_filename(filename, max_length=100):
    """
    Sanitize filename to prevent path traversal and filesystem issues.

    Security measures:
    - Removes path traversal attempts (../, .., etc.)
    - Replaces invalid filesystem characters with underscores
    - Limits filename length while preserving extension
    - Prevents hidden files (starting with .)
    - Ensures filename is not empty

    Args:
        filename (str): Original filename to sanitize
        max_length (int): Maximum allowed filename length (default: 100)

    Returns:
        str: Sanitized filename safe for filesystem storage

    Examples:
        >>> sanitize_filename("../../etc/passwd")
        "etc_passwd"
        >>> sanitize_filename("file<script>.txt")
        "file_script_.txt"
        >>> sanitize_filename("valid_file-name.pdf")
        "valid_file-name.pdf"
    """
    if not filename:
        return "unnamed_file"

    # Convert to string and get basename (removes any directory components)
    filename = os.path.basename(str(filename))

    # Split into name and extension
    name, ext = os.path.splitext(filename)

    # Remove path traversal attempts and null bytes
    name = name.replace("..", "").replace("\0", "")
    ext = ext.replace("..", "").replace("\0", "")

    # Replace invalid filesystem characters with underscores
    # Invalid characters: / \ : * ? " < > | and control characters
    invalid_chars = r'[/\\:*?"<>|\x00-\x1f\x7f]'
    name = re.sub(invalid_chars, "_", name)
    ext = re.sub(invalid_chars, "_", ext)

    # Remove leading/trailing spaces and dots (Windows filesystem issues)
    name = name.strip(". ")
    ext = ext.strip(". ")

    # Ensure extension starts with a dot
    if ext and not ext.startswith("."):
        ext = "." + ext

    # Prevent hidden files (Unix/Linux)
    if name.startswith("."):
        name = "file_" + name.lstrip(".")

    # If name is empty after sanitization, use default
    if not name:
        name = "unnamed_file"

    # Limit length while preserving extension
    # Reserve space for extension plus some buffer
    max_name_length = max_length - len(ext) - 1
    if len(name) > max_name_length:
        name = name[:max_name_length]

    # Combine name and extension
    sanitized = name + ext if ext else name

    # Final check: ensure result is not empty and doesn't exceed max_length
    if not sanitized or sanitized.isspace():
        sanitized = "unnamed_file"

    return sanitized[:max_length]


def image_extension_validation(value):
    ext = os.path.splitext(value.name)[1]  # [0]
    valid_extensions = [".jpg", ".jpeg", ".png"]
    if not ext.lower() in valid_extensions:
        raise ValidationError(
            "Unsupported file extension, pls use .jpg, .jpeg, .png formats"
        )


def validate_video_file_upload(var_uploaded_file):
    """
    Enhanced video file validation for uploads
    """
    # Check file type
    if not validateVideoType(var_uploaded_file):
        return (
            False,
            "Only video files are allowed and it must be in .mp4, .mov, .avi, .mkv, or .webm format",
        )

    # Check file size
    if not validateVideoSize(var_uploaded_file):
        return (
            False,
            f"File size too large. Maximum allowed size is {getVideoMaxSizeMB()}MB",
        )

    # Check for empty files
    if var_uploaded_file.size < 1024:  # Less than 1KB
        return False, "File appears to be empty or corrupted"

    return True, "File is valid"


def getVideoMaxSizeMB():
    """Get maximum video file size in MB from settings - FIX 3.1"""
    # Use centralized FILE_UPLOAD_LIMITS from settings
    limits = getattr(settings, "FILE_UPLOAD_LIMITS", {})
    max_size_bytes = limits.get("VIDEO_MAX_SIZE", 2 * 1024 * 1024 * 1024)
    return max_size_bytes // (1024 * 1024)


def validateVideoSize(var_uploaded_file):
    """Enhanced video size validation - FIX 3.1"""
    # Use centralized FILE_UPLOAD_LIMITS from settings
    limits = getattr(settings, "FILE_UPLOAD_LIMITS", {})
    max_size_bytes = limits.get("VIDEO_MAX_SIZE", 2 * 1024 * 1024 * 1024)
    return var_uploaded_file.size <= max_size_bytes


def validateVideoType(var_uploaded_file):
    """Enhanced video type validation"""
    extension = os.path.splitext(var_uploaded_file.name)[1].lower()
    valid_extensions = [".mp4", ".mov", ".avi", ".mkv", ".webm"]
    return extension in valid_extensions


def getFileType(var_uploaded_file):
    """Enhanced file type detection"""
    extension = os.path.splitext(var_uploaded_file.name)[1].lower()

    # Image types
    if extension in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]:
        return "Image"
    # Video types
    elif extension in [".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv"]:
        return "Video"
    # Document types
    elif extension in [".pdf"]:
        return "PDF"
    elif extension in [".doc", ".docx"]:
        return "Document"
    elif extension in [".xls", ".xlsx"]:
        return "Spreadsheet"
    else:
        return "Unknown"


def validateVideoMetadata(var_uploaded_file):
    """
    Validate video metadata (requires ffmpeg-python)
    This is a placeholder for advanced validation
    """
    try:
        # TODO: Implement with ffmpeg-python for production
        # import ffmpeg
        # probe = ffmpeg.probe(var_uploaded_file.temporary_file_path())
        # video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        #
        # if not video_stream:
        #     return False, "No video stream found in file"
        #
        # # Check duration
        # duration = float(video_stream.get('duration', 0))
        # if duration > 3600:  # 1 hour max
        #     return False, "Video duration exceeds maximum allowed length (1 hour)"
        #
        # return True, "Video metadata is valid"

        return True, "Metadata validation skipped (ffmpeg not available)"

    except Exception as e:
        return False, f"Metadata validation error: {str(e)}"


def estimateCompressionSize(original_size_bytes, target_quality="medium"):
    """
    Estimate compressed file size based on target quality
    """
    compression_ratios = {
        "original": 1.0,
        "high": 0.7,  # 30% compression
        "medium": 0.5,  # 50% compression
        "low": 0.3,  # 70% compression
        "mobile": 0.2,  # 80% compression
    }

    ratio = compression_ratios.get(target_quality, 0.5)
    return int(original_size_bytes * ratio)


# Legacy validation functions for backward compatibility
def BHT_validation(request, value):
    if value == "":
        messages.error(request, "Please enter BHT number, field cant be empty...")
        return False
    elif not value.isnumeric():
        messages.error(
            request, "Please enter valid BHT number, it cant contain any letter..."
        )
        return False
    else:
        return True


# validate PHN
def PHN_validation(request, value):
    if value == "":
        messages.error(request, "Please enter PHN number, field cant be empty...")
        return False
    elif not value.isnumeric():
        messages.error(
            request, "Please enter valid PHN number, it cant contain any letter..."
        )
        return False
    else:
        return True


# validate NNC
def NNC_validation(request, value):
    if value == "":
        messages.error(request, "Please enter NNC number, field cant be empty...")
        return False
    elif not value.isnumeric():
        messages.error(
            request, "Please enter valid NNC number, it cant contain any letter..."
        )
        return False
    else:
        return True


# validate name of baby
def Name_baby_validation(request, value):
    if value == "":
        messages.error(request, "Please enter babies name, field cant be empty...")
    else:
        return True


# validate name of mother
def Name_mother_validation(request, value):
    if value == "":
        messages.error(request, "Please enter mothers name, field cant be empty...")
        return False
    else:
        return True


def validateAttachmentSize(var_uploaded_file):
    """
    Validate attachment file size based on file type.
    Uses settings-based limits: Images (10MB), Videos (2GB), Documents (100MB)
    """
    from django.conf import settings

    extension = os.path.splitext(var_uploaded_file.name)[1].lower()
    file_size = var_uploaded_file.size

    # Get limits from settings
    limits = getattr(settings, "FILE_UPLOAD_LIMITS", {})
    allowed_extensions = getattr(settings, "ALLOWED_FILE_EXTENSIONS", {})

    # Determine file type and get appropriate limit
    max_size = limits.get("ATTACHMENT_MAX_SIZE", 100 * 1024 * 1024)  # Default 100MB

    if extension in allowed_extensions.get("IMAGE", []):
        max_size = limits.get("IMAGE_MAX_SIZE", 10 * 1024 * 1024)
    elif extension in allowed_extensions.get("VIDEO", []):
        max_size = limits.get("VIDEO_MAX_SIZE", 2 * 1024 * 1024 * 1024)
    elif extension in allowed_extensions.get("PDF", []) or extension in allowed_extensions.get("DOCUMENT", []):
        max_size = limits.get("DOCUMENT_MAX_SIZE", 100 * 1024 * 1024)

    return file_size <= max_size


def validateAttachmentType(var_uploaded_file):
    """
    Validate attachment file type.
    Uses settings-based allowed extensions for all attachment types.
    """
    from django.conf import settings

    extension = os.path.splitext(var_uploaded_file.name)[1].lower()

    # Get allowed extensions from settings
    allowed_extensions_dict = getattr(settings, "ALLOWED_FILE_EXTENSIONS", {})

    # Collect all allowed extensions
    all_allowed = []
    for ext_list in allowed_extensions_dict.values():
        all_allowed.extend(ext_list)

    # Fallback to basic extensions if settings not configured
    if not all_allowed:
        all_allowed = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
                      '.mp4', '.mov', '.avi', '.mkv', '.webm',
                      '.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt']

    return extension in all_allowed


# New Django Model Validators for NDAS System


def validate_birth_weight(value):
    if value < 300 or value > 8000:
        raise ValidationError("Birth weight must be between 300g and 8000g")


def validate_apgar_score(value):
    """Validate APGAR score is between 0-10"""
    if value < 0 or value > 10:
        raise ValidationError("APGAR score must be between 0 and 10")


def validate_phone_number(value):
    """Validate phone number format"""
    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message="Phone number must be entered in format: '+999999999'. Up to 15 digits allowed.",
    )
    phone_regex(value)


def validate_video_file(value):
    """
    Comprehensive video file validation for Django model fields - FIX 3.1
    """
    if not value:
        return

    # Get allowed extensions from settings
    allowed_extensions_dict = getattr(settings, "ALLOWED_FILE_EXTENSIONS", {})
    valid_extensions = allowed_extensions_dict.get(
        "VIDEO", [".mp4", ".mov", ".avi", ".mkv", ".webm"]
    )

    # Check file extension
    ext = os.path.splitext(value.name)[1].lower()

    if ext not in valid_extensions:
        raise ValidationError(
            f"Unsupported video format. Allowed formats: {', '.join(valid_extensions)}"
        )

    # Check file size using centralized limits.
    # Use try/except because stored FieldFiles may not be accessible on disk
    # (e.g. test environments) — size validation applies to new uploads only.
    try:
        file_size = value.size
    except OSError:
        logger.warning(
            "validate_video_file: could not read size for %r — skipping size check", value.name
        )
        return
    limits = getattr(settings, "FILE_UPLOAD_LIMITS", {})
    max_size = limits.get("VIDEO_MAX_SIZE", 2 * 1024 * 1024 * 1024)
    if file_size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        raise ValidationError(
            f"File size too large. Maximum allowed size is {int(max_size_mb)} MB."
        )

    # Minimum file size check (1KB to avoid empty files)
    min_size = 1024  # 1KB
    if file_size < min_size:
        raise ValidationError("File appears to be empty or corrupted.")


def validate_recording_date(value):
    """
    Validate video recording date for Django model fields
    """
    if not value:
        return

    # Cannot be in the future
    if value > timezone.now():
        raise ValidationError("Recording date cannot be in the future.")

    # Cannot be more than 10 years in the past (reasonable medical record limit)
    ten_years_ago = timezone.now() - timezone.timedelta(days=365 * 10)
    if value < ten_years_ago:
        raise ValidationError("Recording date cannot be more than 10 years ago.")


def validate_pog_weeks(value):
    """Validate period of gestation weeks (20-44 weeks)"""
    if value < 20 or value > 44:
        raise ValidationError("Period of gestation must be between 20-44 weeks")


def validate_pog_days(value):
    """Validate period of gestation days (0-6 days)"""
    if value < 0 or value > 6:
        raise ValidationError("Period of gestation days must be between 0-6")


def validate_attachment_file(value):
    """
    Comprehensive file validation for attachments - FIX 3.1

    Validates newly uploaded files. Skips validation for existing files (FieldFile)
    to avoid FileNotFoundError when files are stored on different servers.
    """
    from django.db.models.fields.files import FieldFile
    from django.core.files.uploadedfile import UploadedFile

    # Skip validation for existing files (not being changed)
    # Only validate new uploads (InMemoryUploadedFile, TemporaryUploadedFile)
    if isinstance(value, FieldFile) and not isinstance(value.file, UploadedFile):
        # This is an existing file that's not being replaced, skip validation
        return

    # Get file size limits from settings
    limits = getattr(settings, "FILE_UPLOAD_LIMITS", {})
    MAX_ATTACHMENT_SIZE = limits.get("ATTACHMENT_MAX_SIZE", 100 * 1024 * 1024)
    MAX_IMAGE_SIZE = limits.get("IMAGE_MAX_SIZE", 10 * 1024 * 1024)
    MAX_VIDEO_SIZE = limits.get("VIDEO_MAX_SIZE", 2 * 1024 * 1024 * 1024)

    # Get allowed extensions from settings
    allowed_extensions_dict = getattr(settings, "ALLOWED_FILE_EXTENSIONS", {})

    # Check file extension
    ext = os.path.splitext(value.name)[1].lower()

    # Get all allowed extensions from settings
    all_allowed_extensions = []
    for extensions in allowed_extensions_dict.values():
        all_allowed_extensions.extend(extensions)

    # Fallback defaults if settings not configured
    if not all_allowed_extensions:
        all_allowed_extensions = [
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",
            ".pdf",
            ".mp4",
            ".mov",
            ".avi",
            ".mkv",
            ".webm",
            ".doc",
            ".docx",
            ".txt",
            ".rtf",
            ".odt",
        ]

    if ext not in all_allowed_extensions:
        raise ValidationError(
            f"Unsupported file format. Allowed formats: {', '.join(all_allowed_extensions)}"
        )

    # Check file size (use largest allowed size)
    if value.size > MAX_VIDEO_SIZE:
        max_size_gb = MAX_VIDEO_SIZE / (1024 * 1024 * 1024)
        raise ValidationError(
            f"File size too large. Maximum allowed size is {max_size_gb:.1f} GB."
        )

    # Minimum file size check (avoid empty files)
    min_size = 1  # 1 byte
    if value.size < min_size:
        raise ValidationError("File appears to be empty.")

    # MIME type validation
    mime_type, _ = mimetypes.guess_type(value.name)
    if mime_type:
        dangerous_types = [
            "application/x-executable",
            "application/x-msdownload",
            "application/x-dosexec",
        ]
        if mime_type in dangerous_types:
            raise ValidationError(
                "Executable files are not allowed for security reasons."
            )


# ─── Story 1.5: Institution-aware upload paths ───────────────────────────────

def get_institution_video_path(instance, filename):
    """Return institution-partitioned upload path for Video files."""
    try:
        institution = instance.patient.institution if instance.patient_id else None
        slug = institution.slug if institution else 'pending'
    except AttributeError:
        slug = 'pending'
    return f"{slug}/videos/{sanitize_filename(filename)}"


def get_institution_attachment_path(instance, filename):
    """Return institution-partitioned upload path for Attachment files."""
    try:
        institution = instance.patient.institution if instance.patient_id else None
        slug = institution.slug if institution else 'pending'
    except AttributeError:
        slug = 'pending'
    return f"{slug}/attachments/{sanitize_filename(filename)}"


def get_institution_logo_path(instance, filename):
    """
    Upload path for institution logo files (Story 3.3 — FR58).

    Stores at: MEDIA_ROOT/{institution_slug}/logo/{sanitized_filename}

    `instance` is an Institution model instance.
    """
    try:
        slug = instance.slug if instance.slug else 'pending'
    except AttributeError:
        slug = 'pending'
    return f"{slug}/logo/{sanitize_filename(filename)}"


# ─── POG-specific birth weight validation ────────────────────────────────────

BIRTH_WEIGHT_RANGES_BY_POG = {
    20: {'min': 300,  'max': 700,  'typical_min': 300,  'typical_max': 600},
    22: {'min': 400,  'max': 900,  'typical_min': 400,  'typical_max': 750},
    24: {'min': 400,  'max': 1100, 'typical_min': 500,  'typical_max': 900},
    26: {'min': 400,  'max': 1400, 'typical_min': 600,  'typical_max': 1100},
    28: {'min': 700,  'max': 1600, 'typical_min': 800,  'typical_max': 1400},
    30: {'min': 900,  'max': 2000, 'typical_min': 1000, 'typical_max': 1800},
    31: {'min': 1000, 'max': 2200, 'typical_min': 1100, 'typical_max': 1900},
    32: {'min': 1100, 'max': 2500, 'typical_min': 1200, 'typical_max': 2100},
    34: {'min': 1500, 'max': 2900, 'typical_min': 1700, 'typical_max': 2500},
    35: {'min': 1700, 'max': 3200, 'typical_min': 2000, 'typical_max': 2900},
    36: {'min': 1900, 'max': 3500, 'typical_min': 2100, 'typical_max': 3000},
    37: {'min': 2200, 'max': 4000, 'typical_min': 2500, 'typical_max': 3500},
    38: {'min': 2400, 'max': 4500, 'typical_min': 2700, 'typical_max': 3800},
    39: {'min': 2500, 'max': 4800, 'typical_min': 2800, 'typical_max': 4000},
    40: {'min': 2600, 'max': 5000, 'typical_min': 2900, 'typical_max': 4200},
    41: {'min': 2800, 'max': 5200, 'typical_min': 3000, 'typical_max': 4400},
    42: {'min': 2900, 'max': 5400, 'typical_min': 3100, 'typical_max': 4500},
    43: {'min': 3000, 'max': 5500, 'typical_min': 3200, 'typical_max': 4700},
    44: {'min': 3000, 'max': 5500, 'typical_min': 3200, 'typical_max': 4700},
}


def validate_birth_weight_for_gestational_age(weight, pog_weeks, pog_days=0, strict=False):
    """
    Validate birth weight against gestational age using POG-specific ranges.

    Returns (True, "") when weight or pog_weeks is None (validation not applicable).
    Uses linear interpolation between table entries for fractional weeks.

    Args:
        weight: Birth weight in grams (int/float or None)
        pog_weeks: Gestational age in completed weeks (int or None)
        pog_days: Additional gestational days 0-6 (default 0)
        strict: If True, validates against typical range instead of absolute min/max

    Returns:
        tuple: (bool is_valid, str message)
    """
    if weight is None or pog_weeks is None:
        return True, ""

    if pog_weeks < 20 or pog_weeks > 44:
        return False, f"Gestational age {pog_weeks} weeks is outside medical range (20-44 weeks)."

    pog_exact = pog_weeks + (pog_days / 7.0)
    sorted_weeks = sorted(BIRTH_WEIGHT_RANGES_BY_POG.keys())

    lower_week = sorted_weeks[0]
    upper_week = sorted_weeks[-1]
    for w in sorted_weeks:
        if w <= pog_exact:
            lower_week = w
        if w >= pog_exact:
            upper_week = w
            break

    if lower_week == upper_week:
        r = BIRTH_WEIGHT_RANGES_BY_POG[lower_week]
        min_w, max_w = r['min'], r['max']
        typ_min, typ_max = r['typical_min'], r['typical_max']
    else:
        lo = BIRTH_WEIGHT_RANGES_BY_POG[lower_week]
        hi = BIRTH_WEIGHT_RANGES_BY_POG[upper_week]
        frac = (pog_exact - lower_week) / (upper_week - lower_week)
        min_w = int(lo['min'] + (hi['min'] - lo['min']) * frac)
        max_w = int(lo['max'] + (hi['max'] - lo['max']) * frac)
        typ_min = int(lo['typical_min'] + (hi['typical_min'] - lo['typical_min']) * frac)
        typ_max = int(lo['typical_max'] + (hi['typical_max'] - lo['typical_max']) * frac)

    pog_str = f"{pog_weeks}+{pog_days} weeks" if pog_days else f"{pog_weeks} weeks"

    if weight < min_w:
        return False, f"Birth weight {weight}g is unusually low for {pog_str} (minimum: {min_w}g)."
    if weight > max_w:
        return False, f"Birth weight {weight}g is unusually high for {pog_str} (maximum: {max_w}g)."
    if strict:
        if weight < typ_min:
            return False, f"Birth weight {weight}g is extremely low for {pog_str} (typical minimum: {typ_min}g)."
        if weight > typ_max:
            return False, f"Birth weight {weight}g is extremely high for {pog_str} (typical maximum: {typ_max}g)."

    return True, ""
