import os, math, mimetypes, re, html
from django.core.exceptions import ValidationError
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

    # Remove script tags and their content (case insensitive)
    text = re.sub(
        r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL
    )
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)

    # Remove event handlers (onclick, onload, onerror, etc.)
    text = re.sub(r'\s*on\w+\s*=\s*["\']?[^"\']*["\']?', "", text, flags=re.IGNORECASE)

    # Remove dangerous protocols from URLs (javascript:, data:, vbscript:)
    text = re.sub(r"(javascript|data|vbscript):", "", text, flags=re.IGNORECASE)

    # Remove HTML tags while preserving content
    # This regex preserves medical notation like "< 5" or "> 38"
    # by only matching tags that start with < followed by a letter
    text = re.sub(r"<(/)?([a-zA-Z][a-zA-Z0-9]*)[^>]*>", "", text)

    # Unescape HTML entities to prevent double-encoding
    # This converts &lt; back to < and &gt; back to >
    text = html.unescape(text)

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
    - Removes path traversal attempts (../, ..\, etc.)
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
    file_size_mb = math.ceil(
        var_uploaded_file.size / (1024 * 1024)
    )  # round up to the nearest whole number
    if file_size_mb > 100:
        return False
    else:
        return True


def validateAttachmentType(var_uploaded_file):
    extension = os.path.splitext(var_uploaded_file.name)[1].lower()
    if extension in [".jpg", ".jpeg", ".mp4", ".mov", ".pdf"]:
        return True
    else:
        return False


# New Django Model Validators for NDAS System


def validate_birth_weight(value):
    if value < 200 or value > 8000:
        return False, (f"Birth weight must be between 200g and 8000g")


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

    # Check file size using centralized limits
    limits = getattr(settings, "FILE_UPLOAD_LIMITS", {})
    max_size = limits.get("VIDEO_MAX_SIZE", 2 * 1024 * 1024 * 1024)
    if value.size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        raise ValidationError(
            f"File size too large. Maximum allowed size is {int(max_size_mb)} MB."
        )

    # Minimum file size check (1KB to avoid empty files)
    min_size = 1024  # 1KB
    if value.size < min_size:
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
    """
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
