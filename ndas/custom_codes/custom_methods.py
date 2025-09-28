from datetime import datetime, timedelta
from django.db.models.functions import TruncMonth
from django.db.models import Count, Q
import os, math
from django.utils.timezone import localtime, now
from django.utils import timezone
from django.utils.text import slugify
from .ndas_enums import PtStatus


def get_gma_diagnosis_data():
    from patients.models import GMAssessment

    # Use annotate to get a count of patients for each diagnosis title
    data = GMAssessment.objects.values('diagnosis__abr').annotate(patient_count=Count('patient'))

    # Create a dictionary mapping diagnosis titles to patient counts
    diagnosis_data = {}
    for item in data:
        diagnosis_abr = item['diagnosis__abr']
        patient_count = item['patient_count']
        diagnosis_data[diagnosis_abr] = patient_count
    
    return diagnosis_data

def get_all_diagnosis_data():
    from patients.models import GMAssessment, HINEAssessment, DevelopmentalAssessment

    dx_gma_data = getCountZeroIfNone(GMAssessment.objects.filter(diagnosis_conclusion='ABNORMAL'))
    dx_hine_data = getCountZeroIfNone(HINEAssessment.objects.filter(score__lt = 73))
    dx_da_data = getCountZeroIfNone(DevelopmentalAssessment.objects.filter(is_dx_normal=False))

    # Create a dictionary mapping diagnosis titles to patient counts
    diagnosis_data = {'GMA': dx_gma_data,
        'HINE': dx_hine_data,
        'DA': dx_da_data}

    return diagnosis_data

def get_userStats():
    from patients.models import GMAssessment, HINEAssessment, DevelopmentalAssessment, Patient, CDICRecord, Attachment, Bookmark
    from video.models import Video
    from users.models import CustomUser

    user_list = CustomUser.objects.all()
    pt_list = Patient.objects.all()
    video_list = Video.objects.all()
    gma_list = GMAssessment.objects.all()
    hine_list = HINEAssessment.objects.all()
    da_list = DevelopmentalAssessment.objects.all()
    cdic_list = CDICRecord.objects.all()
    attachments_list = Attachment.objects.all()
    bookmark_list = Bookmark.objects.all()
    
    user_stats_val = {}
    user_stats = {}
    
    for u_o in user_list:
        user_stats_val = {'Patient': getCountZeroIfNone(pt_list.filter(added_by=u_o)),
        'Video': getCountZeroIfNone(video_list.filter(added_by=u_o)),
        'GMA': getCountZeroIfNone(gma_list.filter(added_by=u_o)),
        'HINE': getCountZeroIfNone(hine_list.filter(added_by=u_o)),
        'DA': getCountZeroIfNone(da_list.filter(added_by=u_o)),
        'CDIC': getCountZeroIfNone(cdic_list.filter(added_by=u_o)),
        'Attachment': getCountZeroIfNone(attachments_list.filter(added_by=u_o)),
        'Bookmark': getCountZeroIfNone(bookmark_list.filter(owner=u_o)),
        }
        
        # add each users data to final list
        user_stats[u_o.username] = user_stats_val
        
    return user_stats

def get_admissions_data_barchart():
    from patients.models import Patient

    today = datetime.now().date()
    five_months_ago = today - timedelta(days=30*5)

    admissions = (
        Patient.objects
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
    Enhanced video file naming with proper organization
    """
    import os
    from django.utils.text import slugify
    from django.utils import timezone
    
    ext = filename.split('.')[-1]
    patient_name = slugify(instance.patient.baby_name) if instance.patient else 'unknown'
    title = slugify(instance.title) if hasattr(instance, 'title') and instance.title else slugify(instance.caption if hasattr(instance, 'caption') else 'video')
    
    # Create organized folder structure: videos/YYYY/MM/patient_name/
    now = timezone.now()
    year = now.strftime('%Y')
    month = now.strftime('%m')
    
    # Generate unique filename
    timestamp = now.strftime('%Y%m%d_%H%M%S')
    filename = f"{patient_name}_{title}_original_{timestamp}.{ext}"
    
    return os.path.join('videos', year, month, patient_name, filename)


def get_compressed_video_path(instance, filename):
    """
    Generate path for compressed video files
    """
    import os
    from django.utils.text import slugify
    from django.utils import timezone
    
    ext = os.path.splitext(filename)[1].lower()
    # Use .mp4 for all compressed videos for consistency
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
    Generate path for video thumbnail images
    """
    import os
    from django.utils.text import slugify
    from django.utils import timezone
    
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
    ext = filename.split('.')[-1]
    
    filename = f"{instance.title}_{getAttachmentType(filename)}_{instance.added_by}_{getCurrentDateTime()}.{ext}"
    return os.path.join('attachments/', filename)

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
    import logging
    import os
    logger = logging.getLogger(__name__)

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
    import os
    import logging

    logger = logging.getLogger(__name__)

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


# get patients according to type
def getPatientList(pts_type):
    from patients.models import Patient
    
    var_ptl = Patient.objects.all()

    if pts_type == PtStatus.ALL:
        return var_ptl
    elif pts_type == PtStatus.NEW:
        return var_ptl.filter(videos__isnull=True).distinct()
    elif pts_type == PtStatus.DISCHARGED:
        return var_ptl.filter(cdicrecord__is_discharged=True).distinct()
    elif pts_type == PtStatus.DIAGNOSED:
        return var_ptl.filter(Q(gmassessment__diagnosis_conclusion='ABNORMAL') | Q(hine_assessments__score__lt = 73) | Q(developmental_assessments__is_dx_normal=False)).distinct()
    elif pts_type == PtStatus.DX_NORMAL:
        return var_ptl.exclude(Q(gmassessment__diagnosis_conclusion='ABNORMAL') and Q(hine_assessments__score__lt = 73) and Q(developmental_assessments__is_dx_normal=False)).exclude(videos__isnull=True).distinct()
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

