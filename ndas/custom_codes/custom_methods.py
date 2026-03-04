from datetime import timedelta
from django.db.models.functions import TruncMonth
from django.db.models import Count, Q, Exists, OuterRef
import os, math
from django.utils.timezone import localtime, now
from django.utils import timezone
from django.utils.text import slugify
from .ndas_enums import PtStatus
from .validators import sanitize_filename
import logging

logger = logging.getLogger(__name__)


def get_gma_diagnosis_data(institution=None):
    from patients.models import GMAssessment, Patient
    _pts = Patient.objects.for_institution(institution)
    # Use annotate to get a count of patients for each diagnosis title
    data = GMAssessment.objects.filter(patient__in=_pts).values('diagnosis__abr').annotate(patient_count=Count('patient'))

    # Create a dictionary mapping diagnosis titles to patient counts
    diagnosis_data = {}
    for item in data:
        diagnosis_abr = item['diagnosis__abr']
        patient_count = item['patient_count']
        diagnosis_data[diagnosis_abr] = patient_count
    
    return diagnosis_data

def get_all_diagnosis_data(institution=None):
    from patients.models import GMAssessment, HINEAssessment, DevelopmentalAssessment, Patient
    _pts = Patient.objects.for_institution(institution)
    dx_gma_data = getCountZeroIfNone(GMAssessment.objects.filter(patient__in=_pts, diagnosis_conclusion='ABNORMAL'))
    dx_hine_data = getCountZeroIfNone(HINEAssessment.objects.filter(patient__in=_pts, score__lt=73))
    dx_da_data = getCountZeroIfNone(DevelopmentalAssessment.objects.filter(patient__in=_pts, is_dx_normal=False))

    # Create a dictionary mapping diagnosis titles to patient counts
    diagnosis_data = {'GMA': dx_gma_data,
        'HINE': dx_hine_data,
        'DA': dx_da_data}

    return diagnosis_data

def get_userStats(institution=None):
    from patients.models import GMAssessment, HINEAssessment, DevelopmentalAssessment, Patient, CDICRecord, Attachment, Bookmark
    from video.models import Video
    from users.models import CustomUser

    def _counts(qs, field='added_by_id'):
        return {row[field]: row['count'] for row in qs.values(field).annotate(count=Count('id'))}

    _pts = Patient.objects.for_institution(institution)
    pt_counts         = _counts(_pts)
    video_counts      = _counts(Video.objects.filter(patient__in=_pts))
    gma_counts        = _counts(GMAssessment.objects.filter(patient__in=_pts))
    hine_counts       = _counts(HINEAssessment.objects.filter(patient__in=_pts))
    da_counts         = _counts(DevelopmentalAssessment.objects.filter(patient__in=_pts))
    cdic_counts       = _counts(CDICRecord.objects.filter(patient__in=_pts))
    attachment_counts = _counts(Attachment.objects.filter(patient__in=_pts))
    bookmark_counts   = _counts(
        Bookmark.objects.filter(owner__institution=institution) if institution else Bookmark.objects.all(),
        field='owner_id'
    )

    # Note: superuser contributions (institution=None) are excluded from this breakdown.
    # Dashboard total counts above remain correct; only the per-user breakdown is affected.
    _users_qs = CustomUser.objects.filter(institution=institution).only('id', 'username') if institution else CustomUser.objects.only('id', 'username')
    user_stats = {}
    for user in _users_qs:
        uid = user.id
        user_stats[user.username] = {
            'Patient':    pt_counts.get(uid, 0),
            'Video':      video_counts.get(uid, 0),
            'GMA':        gma_counts.get(uid, 0),
            'HINE':       hine_counts.get(uid, 0),
            'DA':         da_counts.get(uid, 0),
            'CDIC':       cdic_counts.get(uid, 0),
            'Attachment': attachment_counts.get(uid, 0),
            'Bookmark':   bookmark_counts.get(uid, 0),
        }
    return user_stats

def get_admissions_data_barchart(institution=None):
    from patients.models import Patient

    today = timezone.now().date()
    five_months_ago = today - timedelta(days=30*5)

    admissions = (
        Patient.objects.for_institution(institution)
        .filter(dob_tob__gte=five_months_ago)
        .annotate(month=TruncMonth('dob_tob'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    months = []
    counts = []
    
    for admission in admissions:
        months.append(admission['month'].strftime('%b %Y'))
        counts.append(admission['count'])

    return {
        'labels': months,
        'data': counts,
    }

def getCurrentDateTime():
    # return datetime.now()
    return localtime(now())

# get IP address
def get_ip_address(request):
    user_ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
    if user_ip_address:
        ip = user_ip_address.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

# get device details
def getFullDeviceDetails(request):
    ua = request.user_agent
    return {'browser': ua.browser, 'os': ua.os, 'device': ua.device, 'ipaddress' : get_ip_address(request),
            'is_mobile': ua.is_mobile, 'is_tablet': ua.is_tablet, 'is_touch_capable': ua.is_touch_capable, 'is_pc': ua.is_pc, 'is_bot': ua.is_bot}

# set uploaded video name
def get_video_path_file_name(instance, filename):
    """
    Enhanced video file naming with proper organization and security.

    Security: Sanitizes filename and extension to prevent path traversal.
    """
    import os
    from django.utils.text import slugify
    from django.utils import timezone

    # Sanitize filename first, then extract extension safely
    sanitized = sanitize_filename(filename)
    ext = os.path.splitext(sanitized)[1].lower()
    if not ext:
        ext = '.mp4'  # Default to mp4 if no extension

    patient_name = slugify(instance.patient.baby_name) if instance.patient else 'unknown'
    title = slugify(instance.title) if hasattr(instance, 'title') and instance.title else slugify(instance.caption if hasattr(instance, 'caption') else 'video')

    # Create organized folder structure: videos/YYYY/MM/patient_name/
    now = timezone.now()
    year = now.strftime('%Y')
    month = now.strftime('%m')

    # Generate unique filename
    timestamp = now.strftime('%Y%m%d_%H%M%S')
    filename = f"{patient_name}_{title}_original_{timestamp}{ext}"

    return os.path.join('videos', year, month, patient_name, filename)


def get_compressed_video_path(instance, filename):
    """
    Generate path for compressed video files with security sanitization.

    Security: Sanitizes filename to prevent path traversal.
    Note: Always uses .mp4 for compressed videos regardless of input.
    """
    import os
    from django.utils.text import slugify
    from django.utils import timezone

    # Sanitize input filename (defensive, even though we override extension)
    sanitized = sanitize_filename(filename)

    # Always use .mp4 for all compressed videos for consistency
    compressed_ext = '.mp4'

    patient_name = slugify(instance.patient.baby_name) if instance.patient else 'unknown'
    title = slugify(instance.title) if hasattr(instance, 'title') and instance.title else slugify(instance.caption if hasattr(instance, 'caption') else 'video')

    # Create organized folder structure
    now = timezone.now()
    year = now.strftime('%Y')
    month = now.strftime('%m')

    timestamp = now.strftime('%Y%m%d_%H%M%S')
    filename = f"{patient_name}_{title}_compressed_{timestamp}{compressed_ext}"

    return os.path.join('videos', year, month, patient_name, 'compressed', filename)


def get_video_thumbnail_path(instance, filename):
    """
    Generate path for video thumbnail images with security sanitization.

    Security: Sanitizes filename to prevent path traversal.
    Note: Always uses .jpg for thumbnails regardless of input.
    """
    import os
    from django.utils.text import slugify
    from django.utils import timezone

    # Sanitize input filename (defensive, even though we override extension)
    sanitized = sanitize_filename(filename)

    patient_name = slugify(instance.patient.baby_name) if instance.patient else 'unknown'
    title = slugify(instance.title) if hasattr(instance, 'title') and instance.title else slugify(instance.caption if hasattr(instance, 'caption') else 'video')

    # Create organized folder structure
    now = timezone.now()
    year = now.strftime('%Y')
    month = now.strftime('%m')

    timestamp = now.strftime('%Y%m%d_%H%M%S')
    filename = f"{patient_name}_{title}_thumb_{timestamp}.jpg"

    return os.path.join('videos', year, month, patient_name, 'thumbnails', filename)

# set uploaded attachment name
def get_attachment_path_file_name(instance, filename):
    """
    Generate secure file path for attachment uploads with sanitization.

    Security measures:
    - Sanitizes instance.title to prevent path traversal
    - Sanitizes original filename and extension
    - Ensures filename is filesystem-safe

    Args:
        instance: Attachment model instance
        filename: Original uploaded filename

    Returns:
        str: Secure file path for storage
    """
    # Sanitize the original filename first to get a safe extension
    sanitized_original = sanitize_filename(filename)
    ext = os.path.splitext(sanitized_original)[1].lower()

    # If no valid extension, try to get from original (but sanitized)
    if not ext:
        ext = '.bin'  # Default extension for unknown types

    # Sanitize the title (user input) to prevent path traversal
    safe_title = sanitize_filename(instance.title, max_length=50)

    # Build filename components (all safe at this point)
    attachment_type = getAttachmentType(filename)
    timestamp = getCurrentDateTime().strftime('%Y%m%d_%H%M%S')

    # Handle added_by which may be None during initial save (before middleware runs)
    user_identifier = str(instance.added_by.id) if instance.added_by else 'system'

    # Combine into final filename
    filename_parts = [safe_title, attachment_type, user_identifier, timestamp]
    base_name = '_'.join(filename_parts)

    # Final sanitization of complete filename (defensive)
    final_filename = sanitize_filename(f"{base_name}{ext}", max_length=200)

    return os.path.join('attachments/', final_filename)

# get attachment type according to file extension
def getAttachmentType(var_attachment):
    """Get attachment type based on file extension - updated for new model choices"""
    extension = os.path.splitext(str(var_attachment))[1].lower()

    # Updated to match ATTACHMENT_TYPE_CHOICES in choice.py
    if extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        return 'image'  # lowercase to match new choices
    elif extension in ['.pdf']:
        return 'pdf'    # lowercase to match new choices
    elif extension in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
        return 'video'  # lowercase to match new choices
    elif extension in ['.doc', '.docx', '.txt', '.rtf', '.odt']:
        return 'document'
    else:
        return 'other'  # matches new choices
    
# get file size in mega bites
def getFileSizeInMb(file):
        return math.ceil(file.size / (1024 * 1024))  # round up to the nearest whole number

# function to check recommendation parameter Display value True or False
def checkRCState(variable):
    if 'display' in variable and isinstance(variable['display'], bool):
        return variable['display']
    else:
        return None  # Or you can return a default value if the 'display' key is missing or not a boolean

def getCountZeroIfNone(var_value):
    if var_value == None:
        return 0
    else:
        return var_value.count()


def extract_video_metadata(video_file_path):
    """
    Extract video metadata including duration using multiple methods

    Args:
        video_file_path (str): Path to the video file

    Returns:
        dict: Video metadata containing duration_seconds, resolution, etc.
        Returns None if extraction fails
    """
    if not os.path.exists(video_file_path):
        logger.error(f"Video file not found: {video_file_path}")
        return None

    # Method 1: Try moviepy first (already in requirements)
    try:
        from moviepy.editor import VideoFileClip

        with VideoFileClip(video_file_path) as clip:
            duration_seconds = int(clip.duration) if clip.duration else None

            # Get resolution
            width, height = clip.size if hasattr(clip, 'size') else (None, None)
            resolution = f"{width}x{height}" if width and height else None

            return {
                'duration_seconds': duration_seconds,
                'resolution': resolution,
                'width': width,
                'height': height,
                'fps': getattr(clip, 'fps', None),
            }

    except ImportError:
        logger.warning("moviepy not available, trying ffprobe")
    except Exception as e:
        logger.warning(f"moviepy failed for {video_file_path}: {str(e)}, trying ffprobe")

    # Method 2: Fallback to ffprobe if moviepy fails
    try:
        import subprocess
        import json

        # Use ffprobe to extract video metadata
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_file_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            logger.warning(f"ffprobe failed for {video_file_path}: {result.stderr}")
            return None

        metadata = json.loads(result.stdout)

        # Extract video stream information
        video_stream = None
        for stream in metadata.get('streams', []):
            if stream.get('codec_type') == 'video':
                video_stream = stream
                break

        if not video_stream:
            logger.warning(f"No video stream found in {video_file_path}")
            return None

        # Extract duration and other metadata
        duration_seconds = None
        format_info = metadata.get('format', {})

        # Try to get duration from format first, then from video stream
        if 'duration' in format_info:
            duration_seconds = int(float(format_info['duration']))
        elif 'duration' in video_stream:
            duration_seconds = int(float(video_stream['duration']))

        # Extract resolution
        width = video_stream.get('width')
        height = video_stream.get('height')
        resolution = f"{width}x{height}" if width and height else None

        return {
            'duration_seconds': duration_seconds,
            'resolution': resolution,
            'width': width,
            'height': height,
            'codec': video_stream.get('codec_name'),
            'bitrate': format_info.get('bit_rate'),
        }

    except subprocess.TimeoutExpired:
        logger.error(f"ffprobe timeout for {video_file_path}")
        return None
    except FileNotFoundError:
        logger.warning("ffprobe not found. Install ffmpeg for better metadata extraction.")
        return None
    except Exception as e:
        logger.error(f"Error extracting video metadata with ffprobe: {str(e)}")
        return None


def simple_video_duration_estimate(video_file_path):
    """
    Provide a basic duration estimate when advanced tools are not available.
    This is a fallback that assumes typical video properties for medical videos.

    Args:
        video_file_path (str): Path to the video file

    Returns:
        dict: Basic metadata estimate or None
    """
    try:
        if not os.path.exists(video_file_path):
            return None

        # Get file size in bytes
        file_size = os.path.getsize(video_file_path)

        # Basic estimation for medical videos (typical bitrates 1-5 Mbps)
        # This is a rough estimate and will not be perfectly accurate

        # Assume average bitrate of 2 Mbps for estimation
        estimated_bitrate_mbps = 2.0
        estimated_bitrate_bps = estimated_bitrate_mbps * 1024 * 1024

        # Duration = file_size_bits / bitrate_bps
        file_size_bits = file_size * 8
        estimated_duration = file_size_bits / estimated_bitrate_bps

        logger.info(f"Estimated duration for {video_file_path}: {estimated_duration:.0f} seconds (file size: {file_size} bytes)")

        return {
            'duration_seconds': int(estimated_duration),
            'resolution': None,  # Cannot estimate resolution from file size
            'width': None,
            'height': None,
            'estimated': True,  # Mark this as an estimate
        }

    except Exception as e:
        logger.error(f"Error estimating video duration: {str(e)}")
        return None


def calculate_age_string(start_date, end_date, format_type="detailed"):
    """
    Calculate age string between two dates with flexible formatting options.

    Args:
        start_date (date): The starting date (e.g., birth date, recording date)
        end_date (date): The ending date (e.g., recording date, current date)
        format_type (str): Format type - "detailed", "medical", or "simple"

    Returns:
        str: Formatted age string

    Examples:
        >>> calculate_age_string(date(2023,1,1), date(2023,1,5), "detailed")
        "4 days"
        >>> calculate_age_string(date(2023,1,1), date(2024,2,15), "medical")
        "1 year and 1 month"
    """
    # Input validation
    if not start_date or not end_date:
        return "Unknown"
        
    if end_date < start_date:
        return "Invalid: End date before start date"
        
    delta = end_date - start_date
    total_days = delta.days
    
    # Same day
    if total_days == 0:
        return "Same day" if format_type != "medical" else "0 days"
    
    # Less than a week
    elif total_days < 7:
        return f"{total_days} day{'s' if total_days != 1 else ''}"
    
    # Less than a month (detailed breakdown for medical purposes)
    elif total_days < 30:
        weeks, days = divmod(total_days, 7)
        if days == 0:
            return f"{weeks} week{'s' if weeks != 1 else ''}"
        if format_type == "simple":
            return f"{weeks} week{'s' if weeks != 1 else ''}"
        return f"{weeks} week{'s' if weeks != 1 else ''} and {days} day{'s' if days != 1 else ''}"
    
    # Less than a year
    elif total_days < 365:
        months, remaining_days = divmod(total_days, 30)
        weeks, days = divmod(remaining_days, 7)
        
        if format_type == "simple":
            return f"{months} month{'s' if months != 1 else ''}"
        elif format_type == "medical" and weeks == 0 and days == 0:
            return f"{months} month{'s' if months != 1 else ''}"
        elif days == 0 and weeks > 0:
            return f"{months} month{'s' if months != 1 else ''} and {weeks} week{'s' if weeks != 1 else ''}"
        elif days == 0:
            return f"{months} month{'s' if months != 1 else ''}"
        elif format_type == "medical":
            return f"{months} month{'s' if months != 1 else ''} and {days} day{'s' if days != 1 else ''}"
        return f"{months} month{'s' if months != 1 else ''} and {days} day{'s' if days != 1 else ''}"
    
    # One year or more
    else:
        years, remaining_days = divmod(total_days, 365)
        months, days = divmod(remaining_days, 30)
        
        if format_type == "simple":
            return f"{years} year{'s' if years != 1 else ''}"
        elif months == 0 and days == 0:
            return f"{years} year{'s' if years != 1 else ''}"
        elif days == 0:
            return f"{years} year{'s' if years != 1 else ''} and {months} month{'s' if months != 1 else ''}"
        elif format_type == "medical":
            return f"{years} year{'s' if years != 1 else ''} and {months} month{'s' if months != 1 else ''}"
        return f"{years} year{'s' if years != 1 else ''} and {months} month{'s' if months != 1 else ''}"


def getPatientList(pts_type, institution=None):
    """
    Get filtered patient queryset based on patient status type.

    Optimized with select_related and prefetch_related to eliminate N+1 queries
    on user references and related assessments.

    Args:
        pts_type (PtStatus): Patient status filter type from PtStatus enum:
            - PtStatus.ALL: All patients
            - PtStatus.NEW: Patients without videos
            - PtStatus.DISCHARGED: Patients marked as discharged
            - PtStatus.DIAGNOSED: Patients with any abnormal diagnosis
            - PtStatus.DX_NORMAL: Patients with normal diagnosis
            - PtStatus.DX_GMA_NORMAL: Patients with normal GMA diagnosis
            - PtStatus.DX_GMA_ABNORMAL: Patients with abnormal GMA diagnosis
            - PtStatus.DX_HINE: Patients with HINE score < 73
            - PtStatus.DX_DA_NORMAL: Patients with normal DA
            - PtStatus.DX_DA_ABNORMAL: Patients with abnormal DA
        institution: Institution to scope the queryset to (None = all institutions,
            Phase 1 backward-compatible). Uses InstitutionScopedManager.for_institution().

    Returns:
        QuerySet: Optimized Patient queryset with related objects prefetched

    Example:
        >>> all_patients = getPatientList(PtStatus.ALL, institution=request.institution)
        >>> diagnosed = getPatientList(PtStatus.DIAGNOSED)
    """
    from patients.models import Patient, CDICRecord, Bookmark, GMAssessment, HINEAssessment

    # Optimized queryset with select_related and prefetch_related to reduce N+1 queries
    var_ptl = Patient.objects.for_institution(institution).select_related(
        'added_by', 'last_edit_by'
    ).prefetch_related(
        'indecation_for_gma', 'videos', 'gm_assessments',
        'hine_assessments', 'developmental_assessments', 'cdic_records'
    )

    from video.models import Video

    # Add N+1-eliminating annotations to base queryset — available on every returned Patient
    var_ptl = var_ptl.annotate(
        has_videos_ann=Exists(Video.objects.filter(patient=OuterRef('pk'))),
        is_discharged_ann=Exists(CDICRecord.objects.filter(patient=OuterRef('pk'), is_discharged=True)),
        is_bookmarked_ann=Exists(Bookmark.objects.filter(bookmark_type='Patient', object_id=OuterRef('pk'))),
        is_gma_abnormal_ann=Exists(GMAssessment.objects.filter(patient=OuterRef('pk'), diagnosis_conclusion='ABNORMAL')),
        is_hine_abnormal_ann=Exists(HINEAssessment.objects.filter(patient=OuterRef('pk'), score__lt=73)),
    )

    if pts_type == PtStatus.ALL:
        return var_ptl
    elif pts_type == PtStatus.NEW:
        return var_ptl.filter(has_videos_ann=False)
    elif pts_type == PtStatus.DISCHARGED:
        return var_ptl.filter(cdic_records__is_discharged=True).distinct()
    elif pts_type == PtStatus.DIAGNOSED:
        return var_ptl.filter(Q(gmassessment__diagnosis_conclusion='ABNORMAL') | Q(hine_assessments__score__lt = 73) | Q(developmental_assessments__is_dx_normal=False)).distinct()
    elif pts_type == PtStatus.DX_NORMAL:
        return var_ptl.exclude(
            Q(gmassessment__diagnosis_conclusion='ABNORMAL') and
            Q(hine_assessments__score__lt = 73) and
            Q(developmental_assessments__is_dx_normal=False)
        ).filter(has_videos_ann=True).distinct()
    elif pts_type == PtStatus.DX_GMA_ABNORMAL:
        return var_ptl.filter(gmassessment__diagnosis_conclusion='ABNORMAL').distinct()
    elif pts_type == PtStatus.DX_GMA_NORMAL:
        return var_ptl.filter(gmassessment__diagnosis_conclusion='NORMAL').distinct()
    elif pts_type == PtStatus.DX_DA_NORMAL:
        return var_ptl.filter(developmental_assessments__is_dx_normal=True).distinct()
    elif pts_type == PtStatus.DX_DA_ABNORMAL:
        return var_ptl.filter(developmental_assessments__is_dx_normal=False).distinct()
    elif pts_type == PtStatus.DX_HINE:
        return var_ptl.filter(Q(hine_assessments__score__lt = 73)).distinct()
    else:
        return None

