import os, math, mimetypes
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.validators import RegexValidator
from django.utils import timezone


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
    """Get maximum video file size in MB from settings"""
    default_size = 2048  # 2GB default
    max_size_bytes = getattr(
        settings, "VIDEO_MAX_FILE_SIZE", default_size * 1024 * 1024
    )
    return max_size_bytes // (1024 * 1024)


def validateVideoSize(var_uploaded_file):
    """Enhanced video size validation"""
    max_size_bytes = getattr(
        settings, "VIDEO_MAX_FILE_SIZE", 2 * 1024 * 1024 * 1024
    )  # 2GB default
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
        # duration = float(video_stream.get('duration', 0))
        # if duration > 3600:  # 1 hour limit
        #     return False, "Video duration exceeds 1 hour limit"
        #
        # width = int(video_stream.get('width', 0))
        # height = int(video_stream.get('height', 0))
        # if width > 4096 or height > 4096:  # 4K limit
        #     return False, "Video resolution exceeds 4K limit"

        return True, "Video metadata is valid"

    except Exception as e:
        return False, f"Error validating video metadata: {str(e)}"


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
    """Validate birth weight is within realistic range (300g - 8000g)"""
    if value < 300 or value > 8000:
        raise ValidationError(_("Birth weight must be between 300g and 8000g"))


def validate_apgar_score(value):
    """Validate APGAR score is between 0-10"""
    if value < 0 or value > 10:
        raise ValidationError(_("APGAR score must be between 0 and 10"))


def validate_phone_number(value):
    """Validate phone number format"""
    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message=_(
            "Phone number must be entered in format: '+999999999'. Up to 15 digits allowed."
        ),
    )
    phone_regex(value)


def validate_video_file(value):
    """
    Comprehensive video file validation
    """
    # Check file extension
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [".mp4", ".mov", ".avi", ".mkv", ".webm"]

    if ext not in valid_extensions:
        raise ValidationError(
            _("Unsupported video format. Allowed formats: %(formats)s")
            % {"formats": ", ".join(valid_extensions)}
        )

    # Check file size (default max: 2GB, configurable)
    max_size = getattr(settings, "VIDEO_MAX_FILE_SIZE", 2 * 1024 * 1024 * 1024)  # 2GB
    if value.size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        raise ValidationError(
            _("File size too large. Maximum allowed size is %(max_size)d MB.")
            % {"max_size": int(max_size_mb)}
        )

    # Minimum file size check (1KB to avoid empty files)
    min_size = 1024  # 1KB
    if value.size < min_size:
        raise ValidationError(_("File appears to be empty or corrupted."))


def validate_recording_date(value):
    """
    Validate video recording date
    """
    # Cannot be in the future
    if value > timezone.now():
        raise ValidationError(_("Recording date cannot be in the future."))

    # Cannot be more than 10 years in the past (reasonable medical record limit)
    ten_years_ago = timezone.now() - timezone.timedelta(days=365 * 10)
    if value < ten_years_ago:
        raise ValidationError(_("Recording date cannot be more than 10 years ago."))


def validate_pog_weeks(value):
    """Validate period of gestation weeks (20-44 weeks)"""
    if value < 20 or value > 44:
        raise ValidationError(_("Period of gestation must be between 20-44 weeks"))


def validate_pog_days(value):
    """Validate period of gestation days (0-6 days)"""
    if value < 0 or value > 6:
        raise ValidationError(_("Period of gestation days must be between 0-6"))


def validate_attachment_file(value):
    """
    Comprehensive file validation for attachments
    """
    # File size limits (in bytes)
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB for images
    MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024  # 2GB for videos

    # Allowed file extensions
    ALLOWED_EXTENSIONS = {
        "image": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
        "pdf": [".pdf"],
        "video": [".mp4", ".mov", ".avi", ".mkv", ".webm"],
        "document": [".doc", ".docx", ".txt", ".rtf", ".odt"],
    }

    # Check file extension
    ext = os.path.splitext(value.name)[1].lower()

    # Get all allowed extensions
    all_allowed_extensions = []
    for extensions in ALLOWED_EXTENSIONS.values():
        all_allowed_extensions.extend(extensions)

    if ext not in all_allowed_extensions:
        raise ValidationError(
            _("Unsupported file format. Allowed formats: %(formats)s")
            % {"formats": ", ".join(all_allowed_extensions)}
        )

    # Check file size (basic check - more specific validation in model)
    if value.size > MAX_VIDEO_SIZE:  # Use largest allowed size
        max_size_gb = MAX_VIDEO_SIZE / (1024 * 1024 * 1024)
        raise ValidationError(
            _("File size too large. Maximum allowed size is %(max_size).1f GB.")
            % {"max_size": max_size_gb}
        )

    # Minimum file size check (avoid empty files)
    min_size = 1  # 1 byte
    if value.size < min_size:
        raise ValidationError(_("File appears to be empty."))

    # MIME type validation
    mime_type, _ = mimetypes.guess_type(value.name)
    if mime_type:
        dangerous_types = [
            "application/x-executable",
            "application/x-msdownload",
            "application/x-dosexec",
        ]
        if mime_type in dangerous_types:
            raise ValidationError(_("Executable files are not allowed for security reasons."))
