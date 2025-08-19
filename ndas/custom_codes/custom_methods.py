from datetime import datetime, timedelta
from django.db.models.functions import TruncMonth
from django.db.models import Count, Q
import os, math
from django.utils.timezone import localtime, now
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

    dx_gma_data = getCountZeroIfNone(GMAssessment.objects.filter(diagnosis_conclution='ABNORMAL'))
    dx_hine_data = getCountZeroIfNone(HINEAssessment.objects.filter(score__lt = 73))
    dx_da_data = getCountZeroIfNone(DevelopmentalAssessment.objects.filter(isDxNormal=False))

    # Create a dictionary mapping diagnosis titles to patient counts
    diagnosis_data = {'GMA': dx_gma_data,
        'HINE': dx_hine_data,
        'DA': dx_da_data}

    return diagnosis_data

def get_userStats():
    from patients.models import GMAssessment, HINEAssessment, DevelopmentalAssessment, Patient, Video, CDICRecord, Attachment, Bookmark
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
        'Video': getCountZeroIfNone(video_list.filter(uploaded_by=u_o)),
        'GMA': getCountZeroIfNone(gma_list.filter(created_by=u_o)),
        'HINE': getCountZeroIfNone(hine_list.filter(added_by=u_o)),
        'DA': getCountZeroIfNone(da_list.filter(added_by=u_o)),
        'CDIC': getCountZeroIfNone(cdic_list.filter(created_by=u_o)),
        'Attachment': getCountZeroIfNone(attachments_list.filter(uploaded_by=u_o)),
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
    ext = filename.split('.')[-1]
    filename = f"{instance.patient.baby_name}_{instance.caption}_{instance.uploaded_by}_{getCurrentDateTime()}.{ext}"
    return os.path.join('videos/', filename)

# set uploaded attachment name
def get_attachment_path_file_name(instance, filename):
    ext = filename.split('.')[-1]
    
    filename = f"{instance.title}_{getAttachmentType(filename)}_{instance.uploaded_by}_{getCurrentDateTime()}.{ext}"
    return os.path.join('attachments/', filename)

# get attachment type according to file extension
def getAttachmentType(var_attachment):
    extension = os.path.splitext(str(var_attachment))[1].lower()

    if extension in ['.jpg', '.jpeg']:
        return 'Image'
    elif extension in ['.pdf']:
        return 'PDF'
    elif extension in ['.mp4', '.mov']:
        return 'Video'
    else:
        return 'Undefined'
    
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

# get patients according to type
def getPatientList(pts_type):
    from patients.models import Patient
    
    try:
        var_ptl = Patient.objects.all()
    except:
        var_ptl = None

    if pts_type == PtStatus.ALL:
        return var_ptl
    elif pts_type == PtStatus.NEW:
        return var_ptl.filter(video__isnull=True).distinct()
    elif pts_type == PtStatus.DISCHARGED:
        return var_ptl.filter(cdicrecord__is_discharged=True).distinct()
    elif pts_type == PtStatus.DIAGNOSED:
        return var_ptl.filter(Q(gmassessment__diagnosis_conclution='ABNORMAL') | Q(hineassessment__score__lt = 73) | Q(developmentalassessment__isDxNormal=False)).distinct()
    elif pts_type == PtStatus.DX_NORMAL:
        return var_ptl.exclude(Q(gmassessment__diagnosis_conclution='ABNORMAL') and Q(hineassessment__score__lt = 73) and Q(developmentalassessment__isDxNormal=False)).exclude(video__isnull=True).distinct()
    elif pts_type == PtStatus.DX_GMA_ABNORMAL:
        return var_ptl.filter(gmassessment__diagnosis_conclution='ABNORMAL').distinct()
    elif pts_type == PtStatus.DX_GMA_NORMAL:
        return var_ptl.filter(gmassessment__diagnosis_conclution='NORMAL').distinct()
    elif pts_type == PtStatus.DX_DA_NORMAL:
        return var_ptl.filter(developmentalassessment__isDxNormal=True).distinct()
    elif pts_type == PtStatus.DX_DA_ABNORMAL:
        return var_ptl.filter(developmentalassessment__isDxNormal=False).distinct()
    elif pts_type == PtStatus.DX_HINE:
        return var_ptl.filter(Q(hineassessment__score__lt = 73)).distinct()
    else:
        return None

