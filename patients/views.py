from django.shortcuts import redirect, render
from patients.models import Patient, Video, GMAssessment, CDICRecord, Help, Bookmark, Attachment, HINEAssessment, DevelopmentalAssessment
from users.models import CustomUser
from users.views import userViewByUsername
from patients.forms import PatientForm, GMAssessmentForm, BookmarkForm, AttachmentkForm, VideoForm, CDICRecordForm, HINEAssessmentForm, DevelopmentalAssessmentForm
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ndas.custom_codes.validators import Name_baby_validation, Name_mother_validation, BHT_validation, PHN_validation, NNC_validation, validateVideoSize, validateVideoType, validateAttachmentSize,validateAttachmentType
from ndas.custom_codes.custom_methods import get_admissions_data_barchart, get_gma_diagnosis_data, get_all_diagnosis_data, get_userStats, getAttachmentType, getCurrentDateTime, getFileSizeInMb, getPatientList, getCountZeroIfNone
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
import pytz, os
from django.http import JsonResponse
from django.utils.timezone import localtime, now
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
# from moviepy.editor import VideoFileClip  # Temporarily commented out
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from ndas.custom_codes.ndas_enums import PtStatus

# Create your views here
@login_required(login_url='user-login')
def dashboard(request):
    # load common record as variables
    var_patients = getPatientList(PtStatus.ALL)
    var_videos = Video.objects.all()
    var_gm_assessments = GMAssessment.objects.all()
    var_hine_assessments = HINEAssessment.objects.all()
    var_da_assessments = DevelopmentalAssessment.objects.all()
    var_cdic_records = CDICRecord.objects.all()

    var_new_Patients = var_patients.filter(videos__isnull=True).distinct()
    Patients_new_list_10 = var_new_Patients[:5]
    patients_new_count = getCountZeroIfNone(var_new_Patients)
    patients_total_count = getCountZeroIfNone(var_patients)
    patients_discharged_count = getCountZeroIfNone(getPatientList(PtStatus.DISCHARGED))
    
    bookmark = Bookmark.objects.all()
    attachments_count = getCountZeroIfNone(Attachment.objects.all())
    users_total_count = getCountZeroIfNone(CustomUser.objects.all())

    videos_total_count = getCountZeroIfNone(var_videos)
    var_new_videos = var_videos.filter(gmassessment__isnull=True).distinct()
    new_videos = var_new_videos[:5]
    new_videos_count = getCountZeroIfNone(var_new_videos)
    
    all_gm_assessments_count = getCountZeroIfNone(var_gm_assessments)
    all_hine_assessments_count = getCountZeroIfNone(var_hine_assessments)
    all_da_assessments_count = getCountZeroIfNone(var_da_assessments)
    all_cdic_records_count = getCountZeroIfNone(var_cdic_records)
    
    dx_gm_assessments_count = getCountZeroIfNone(GMAssessment.objects.exclude(diagnosis_conclution='NORMAL'))
    dx_hine_assessments_count = getCountZeroIfNone(HINEAssessment.objects.filter(score__lt=73))
    dx_da_assessments_count = getCountZeroIfNone(DevelopmentalAssessment.objects.filter(isDxNormal=False))

    # get data for bar chart
    bar_chart_monthly_admissions = get_admissions_data_barchart()
    diagnosis_data_gma = get_gma_diagnosis_data()
    diagnosis_data_all = get_all_diagnosis_data()
    user_stat = get_userStats()
    
    context = {
        'videos_total_count' : videos_total_count,

        'dx_gm_assessments_count' : dx_gm_assessments_count,
        'dx_hine_assessments_count' : dx_hine_assessments_count,
        'dx_da_assessments_count' : dx_da_assessments_count,
        
        'all_gm_assessments_count' : all_gm_assessments_count,
        'all_hine_assessments_count' : all_hine_assessments_count,
        'all_da_assessments_count' : all_da_assessments_count,
        
        'all_cdic_records_count' : all_cdic_records_count,

        'new_videos' : new_videos,
        'new_videos_count' : new_videos_count,
        'videos_total_count' : videos_total_count,
        
        'patients_total_count' : patients_total_count,
        'Patients_new_list_10' : Patients_new_list_10,
        'patients_new_count' : patients_new_count,
        'patients_discharged_count' : patients_discharged_count,
        
        'bookmark' : bookmark,
        'bar_chart_monthly_admissions' : bar_chart_monthly_admissions,
        'diagnosis_data_gma' : diagnosis_data_gma,
        'diagnosis_data_all' : diagnosis_data_all,

        'users_total_count' : users_total_count,
        'attachments_count' : attachments_count,
        
        'user_stat' : user_stat,
        }

    return render (request, 'patients/index.html', context)

@login_required(login_url='user-login')
def patient_manager(request):
    patients_list = Patient.objects.all().order_by('-id')
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get('page')
    paginated_pt_list = paginator.get_page(page_number)
    return render (request, 'patients/manager.html', {'patients_page_obj': paginated_pt_list})

@login_required(login_url='user-login')
def patient_manager_diagnosed_any(request):
    patients_list = getPatientList(PtStatus.DIAGNOSED).order_by('-id')
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get('page')
    paginated_pt_list = paginator.get_page(page_number)
    return render (request, 'patients/manager.html', {'patients_page_obj': paginated_pt_list, 'type' : 'DIAGNOSED'})

@login_required(login_url='user-login')
def patient_manager_diagnosis_normal(request):
    patients_list = getPatientList(PtStatus.DX_NORMAL).order_by('-id')
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get('page')
    paginated_pt_list = paginator.get_page(page_number)
    return render (request, 'patients/manager.html', {'patients_page_obj': paginated_pt_list, 'type' : 'DX_NORMAL'})

@login_required(login_url='user-login')
def patient_manager_diagnosed_gma_normal(request):
    patients_list = getPatientList(PtStatus.DX_GMA_NORMAL).order_by('-id')
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get('page')
    paginated_pt_list = paginator.get_page(page_number)
    return render (request, 'patients/manager.html', {'patients_page_obj': paginated_pt_list, 'type' : 'DX_GMA_NORMAL'})

@login_required(login_url='user-login')
def patient_manager_diagnosed_gma_abnormal(request):
    patients_list = getPatientList(PtStatus.DX_GMA_ABNORMAL).order_by('-id')
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get('page')
    paginated_pt_list = paginator.get_page(page_number)
    return render (request, 'patients/manager.html', {'patients_page_obj': paginated_pt_list, 'type' : 'DX_GMA_ABNORMAL'})

@login_required(login_url='user-login')
def patient_manager_diagnosed_hine(request):
    patients_list = getPatientList(PtStatus.DX_HINE).order_by('-id')
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get('page')
    paginated_pt_list = paginator.get_page(page_number)
    return render (request, 'patients/manager.html', {'patients_page_obj': paginated_pt_list, 'type' : 'DX_HINE'})

@login_required(login_url='user-login')
def patient_manager_da_normal(request):
    patients_list = getPatientList(PtStatus.DX_DA_NORMAL).order_by('-id')
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get('page')
    paginated_pt_list = paginator.get_page(page_number)
    return render (request, 'patients/manager.html', {'patients_page_obj': paginated_pt_list, 'type' : 'DX_DA_NORMAL'})

@login_required(login_url='user-login')
def patient_manager_da_abnormal(request):
    patients_list = getPatientList(PtStatus.DX_DA_ABNORMAL).order_by('-id')
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get('page')
    paginated_pt_list = paginator.get_page(page_number)
    return render (request, 'patients/manager.html', {'patients_page_obj': paginated_pt_list, 'type' : 'DX_DA_ABNORMAL'})

@login_required(login_url='user-login')
def patient_manager_discharged_only(request):
    patients_list = getPatientList(PtStatus.DISCHARGED).order_by('-id')
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get('page')
    paginated_pt_list = paginator.get_page(page_number)
    return render (request, 'patients/manager.html', {'patients_page_obj': paginated_pt_list, 'type' : 'DISCHARGED'})

@login_required(login_url='user-login')
def patient_manager_new_only(request):
    patients_list = Patient.objects.filter(videos__isnull=True).order_by('-id')
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get('page')
    paginated_pt_list = paginator.get_page(page_number)
    return render (request, 'patients/manager.html', {'patients_page_obj': paginated_pt_list, 'type' : 'NEW'})

@login_required(login_url='user-login')
def patient_add(request):
    empty_form = PatientForm()
    if request.user.is_authenticated:
        if request.method == 'POST':
            data_form = PatientForm(request.POST)
            if data_form.is_valid():
                var_pt_add = data_form.save()
                var_pt_add.added_by = request.user
                var_pt_add.last_edit_by = None
                var_pt_add.last_edit_on = None
                var_pt_add.save()
                messages.success(request, 'New patient added succussfully...')
                return redirect('manage-patients')
            else:
                return render (request, 'patients/add.html', {'form' : data_form})
        else:
            return render (request, 'patients/add.html', {'form' : empty_form})
    else:
        messages.error(request, 'You are not authorized to perform this action, please login')
        return redirect('user-login')

@login_required(login_url='user-login')
def patient_view(request, pk):
    selected_patient = Patient.objects.get(id=pk)
    indications = selected_patient.indecation_for_gma
    
    var_file_video = Video.objects.filter(patient=selected_patient).order_by('-id')
    file_video_count = var_file_video.count()
    file_videos = var_file_video[:5]
    
    var_file_attachments = Attachment.objects.filter(patient=selected_patient).order_by('-id')
    file_attachment_count = var_file_attachments.count()
    file_attachment = var_file_attachments[:5]

    var_gma = GMAssessment.objects.filter(patient=selected_patient).order_by('-id')
    gm_assessments_count = var_gma.count()
    gm_assessments = var_gma[:5]
    gm_last_assessment = var_gma.last
    
    var_hine = HINEAssessment.objects.filter(patient=selected_patient).order_by('-id')
    hine_assessments_count = var_hine.count()
    hine_assessments = var_hine[:5]
    
    var_da = DevelopmentalAssessment.objects.filter(patient=selected_patient).order_by('-id')
    da_assessments_count = var_da.count()
    da_assessments = var_da[:5]
    
    var_cdic = CDICRecord.objects.filter(patient=selected_patient).order_by('-id')
    cdic_record_count = var_cdic.count()
    cdic_record = var_cdic[:5]
    
    #check bookmark
    bm = Bookmark.objects.filter(bookmark_type='Patient').filter(object_id=selected_patient.id).first

    context = {'patient' : selected_patient,
               'file_videos' : file_videos, 'file_video_count' : file_video_count,
               'file_attachment' : file_attachment, 'file_attachment_count' : file_attachment_count,
               'indications' : indications,
               'bookmark' : bm,
               'gm_assessments_new' : '',
               'gm_assessments_completed' : '',
               'gm_assessments' : gm_assessments,
               'gm_assessments_count' : gm_assessments_count,
               'gm_last_assessment' : gm_last_assessment,
               'hine_assessments_count' : hine_assessments_count,
               'hine_assessments' : hine_assessments,
               'da_assessments_count' : da_assessments_count,
               'da_assessments' : da_assessments,
               'cdic_record_count' : cdic_record_count,
               'cdic_record' : cdic_record,
               }

    return render (request, 'patients/view.html', context)

@login_required(login_url='user-login')
def patient_delete(request, pk):
    if request.method == 'POST':
        patient = Patient.objects.get(id=pk)
        user = request.user
        if user.check_password(request.POST['password']):
            if patient.delete():
                messages.success(request, 'Patient has deleted succusfully...')
                return redirect('manage-patients')
            else:
                messages.error(request, 'Something went wrong while deleting the patient...')
                return render (request, 'patients/delete-confirm.html', {'patient' : patient})
        else:
            messages.error(request, 'Wrong password, please try again with correct password')
            return render (request, 'patients/delete-confirm.html', {'patient' : patient})
        
@login_required(login_url='user-login')
def patient_delete_confirm(request, pk):
    patient = Patient.objects.get(id=pk)
    user = request.user
    if user.is_superuser:
        return render (request, 'patients/delete-confirm.html', {'patient' : patient})
    else:
        messages.warning(request, 'You dont have permission to delete this record. Please contact Administrator/ Developer')
        return render (request, 'patients/delete-confirm.html', {'patient' : patient, 'hide':True})

@login_required(login_url='user-login')
def patient_edit(request, pk):
    selected_patient = Patient.objects.get(id=pk)
    data_form = PatientForm(instance=selected_patient)
    
    if request.method == 'POST':
        data_form_modified = PatientForm(request.POST, instance=selected_patient)
        if data_form_modified.is_valid():
            data_form_modified.save()
            # save object to update last edited user
            selected_patient.last_edit_by = request.user
            selected_patient.save()
            messages.success(request, 'Patient details updated succussfully...')
            return redirect('manage-patients')
        else:
            return render(request, 'patients/edit.html', {'form' : data_form_modified, 'patient' : selected_patient})
    else:
        return render(request, 'patients/edit.html', {'form' : data_form, 'patient' : selected_patient})

@login_required(login_url='user-login')
def search_start(request):
    username_list = CustomUser.objects.all()
    return render (request, 'patients/search.html', {'username_list' : username_list})

@login_required(login_url='user-login')
def search_results(request):
    combo_record_type = request.POST.get('combo_record_type', None)
    combo_pt_param_type = request.POST.get('combo_pt_param_type', None)
    como_user_username = request.POST.get('combo_users', None)
    pagn = ''
    search_text = request.POST.get('search_text', None)

# search patients --------------------------------------------------------------
    if (combo_record_type == 'rtype_pt'):
        patient = Patient()
        if combo_pt_param_type == 'pts_bht' and BHT_validation(request, search_text):
            pagn = " : Patients > BHT > " + str(search_text)
            try:
                pagn = " : Patients > BHT > " + str(search_text)
                patient = Patient.objects.get(bht=search_text)
                messages.success(request, 'Search results for : %s' % pagn)
                return render (request, 'patients/view.html', {'patient' : patient, 'pgn' : pagn})
            except patient.DoesNotExist:
                pagn = " : Patients > BHT > " + str(search_text)
                return render (request, 'patients/search_notfound.html', {'patient' : patient, 'pgn' : pagn})

        elif combo_pt_param_type == 'pts_phn' and PHN_validation(request, search_text):
            pagn = " : Patients > PHN > " + str(search_text)
            try:
                patient = Patient.objects.get(pin=search_text)
                messages.success(request, 'Search results for : %s' % pagn)
                return render (request, 'patients/view.html', {'patient' : patient})
            except patient.DoesNotExist:
                return render (request, 'patients/search_notfound.html', {'patient' : patient, 'pgn' : pagn})

        elif combo_pt_param_type == 'pts_nnc_no' and NNC_validation(request, search_text):
            try:
                patient = Patient.objects.get(nnc_no=search_text)
                messages.success(request, 'Search results for : %s' % pagn)
                return render (request, 'patients/view.html', {'patient' : patient, 'pgn' : pagn})
            except patient.DoesNotExist:
                return render (request, 'patients/search_notfound.html', {'patient' : patient, 'pgn' : pagn})

        elif combo_pt_param_type == 'pts_name_baby' and Name_baby_validation(request, search_text):
            pagn = " : Patients > Name of the baby > " + str(search_text)
            try:
                patient = Patient.objects.filter(Q(baby_name__startswith=search_text) | Q(baby_name__icontains=search_text))
            except patient.DoesNotExist:
                return render (request, 'patients/search_notfound.html', {'pgn' : pagn})
            if len(patient) == 1:
                messages.success(request, 'Search results for : %s' % pagn)
                return render (request, 'patients/view.html', {'patient' : patient.first(), 'patients_page_obj' : None, 'pgn' : pagn})
            if len(patient) > 1:
                paginator = Paginator(patient, 10)
                page_number = request.GET.get('page')
                paginated_pt_list = paginator.get_page(page_number)
                return render (request, 'patients/results.html', {'patient' : None, 'patients_page_obj' : paginated_pt_list, 'pgn' : pagn})
            else:
                return render (request, 'patients/search_notfound.html', {'pgn' : pagn})

        elif combo_pt_param_type == 'pts_name_mother'  and Name_mother_validation(request, search_text):
            pagn = " : Patients > Name of the mother > " + str(search_text)
            try:
                patient = Patient.objects.filter(Q(mother_name__startswith=search_text) | Q(mother_name__icontains=search_text))
            except patient.DoesNotExist:
                return render (request, 'patients/search_notfound.html', {'pgn' : pagn})

            if len(patient) == 1:
                messages.success(request, 'Search results for : %s' % pagn)
                return render (request, 'patients/view.html', {'patient' : patient.first(), 'patients_page_obj' : None, 'pgn' : pagn})
            if len(patient) > 1:
                paginator = Paginator(patient, 10)
                page_number = request.GET.get('page')
                paginated_pt_list = paginator.get_page(page_number)
                return render (request, 'patients/results.html', {'patient' : None, 'patients_page_obj' : paginated_pt_list, 'pgn' : pagn})
            else:
                return render (request, 'patients/results.html', {'patient' : patient, 'patients_page_obj' : None, 'pgn' : pagn})
        else:
            username_list = CustomUser.objects.all()
            return render (request, 'patients/search.html', {'username_list' : username_list})

    # search users --------------------------------------------------------------
    elif (combo_record_type == 'rtype_user'):
        pagn = " : Users > by username > " + como_user_username
        messages.success(request, 'Search results for : %s' % pagn)
        return userViewByUsername(request, como_user_username)
    else:
        messages.success(request, 'No search results, please use appropriate option and try again...')
        return render (request, 'patients/search_notfound.html')

# methods for file operations ------------------------------------------------------------------------------
@csrf_exempt
@login_required(login_url='user-login')
def video_add(request, pk):
    selected_patient = Patient.objects.get(id=pk)
    temp_file = None
    if request.method == 'POST':
        
        caption = request.POST['file_title']
        uploaded_file = request.FILES['file']
        recorded_on = request.POST["recorded_on"]
        var_description = request.POST["descreption"]
        
        # create recorded time with time zone infomation
        formated_recorded_date = datetime.strptime(recorded_on, '%Y-%m-%d')
        asia_timezone = pytz.timezone('Asia/Kolkata')
        new_recorded_on = asia_timezone.localize(formated_recorded_date)
        
        if validateVideoType(uploaded_file) :
            
            if getFileSizeInMb(uploaded_file) < 1000:
                
                if getFileSizeInMb(uploaded_file) > 30:
                    try:
                        fs = FileSystemStorage()
                        filename = fs.save(uploaded_file.name, uploaded_file)
                        input_file = fs.path(filename)
                        
                        converted_file_name =  f'{request.user.username}_{filename}'
                        
                        # Set the format and file extension for the output video
                        output_format = 'mp4'
                        output_file_name, _ = os.path.splitext(converted_file_name)
                        output_file_path = output_file_name + '.' + output_format
                        
                        bitrate = '1000k'
                        
                        clip = VideoFileClip(input_file)
                        
                        if clip.rotation in (90, 270):
                            clip = clip.resize(clip.size[::-1])
                            clip.rotation = 0
                            
                        vwidth, vheight = clip.size
                        
                        if vwidth > vheight:
                            #Calculate aspect ratio
                            original_aspect_ratio = clip.size[0] / clip.size[1]
                            resized_height = int(1280 / original_aspect_ratio)
                            ffmpeg_params = ['-vf', 'scale=1280:{}'.format(resized_height)]
                            clip = clip.resize(width=1280)
                        else:
                            #Calculate aspect ratio
                            original_aspect_ratio = clip.size[0] / clip.size[1]
                            resized_height = int(720 / original_aspect_ratio)
                            ffmpeg_params = ['-vf', 'scale=720:{}'.format(resized_height)]
                            clip = clip.resize(width=720)
                            
                        clip.write_videofile(output_file_path, preset='medium', ffmpeg_params=ffmpeg_params, bitrate=bitrate, fps=clip.fps, codec = 'libx264', audio=False)
                        clip.close()
                        
                        # save file object
                        temp_file = Video(
                        patient = selected_patient,
                        caption = caption,
                        recorded_on = new_recorded_on,
                        description = var_description,
                        uploaded_by = request.user,
                        last_edit_by = None,
                        last_edit_on = None,)

                        temp_file.save()
                        
                        with open(output_file_path, 'rb') as f:
                            temp_file.video.save(output_file_path, File(f))
                        temp_file.save(update_fields=["video"])
                        temp_file.save()
                        
                        # Delete the saved file from the temporary location
                        fs.delete(filename)
                        os.remove(output_file_path)
                        
                        if temp_file != None:
                            return JsonResponse({'success': True, 'msg': 'OK', 'p_id': selected_patient.id, 'f_id': temp_file.id})
                        else:
                            return None
                        
                    except (BufferError, TypeError, TypeError, EOFError, MemoryError, AttributeError, FileExistsError, EnvironmentError, FileNotFoundError) as e:
                        return JsonResponse({'success': False, 'msg': e, 'p_id': selected_patient.id, 'f_id': ''})
                else:
                    # in case of no need to convert the file save file object
                    temp_file = Video(
                    patient = selected_patient,
                    caption = caption,
                    video = uploaded_file,
                    recorded_on = new_recorded_on,
                    description = var_description,
                    uploaded_by = request.user,
                    last_edit_by = None,
                    last_edit_on = None,)
                    
                    temp_file.save()
                    
                    if temp_file != None:
                        return JsonResponse({'success': True, 'msg': 'OK', 'p_id': selected_patient.id, 'f_id': temp_file.id})
                    else:
                        return None
                    
            else:
                return JsonResponse({'success': False, 'msg': 'You cant upload >1000mb files...'})
        else:
            return JsonResponse({'success': False, 'msg': 'Only video files are allowed and it must be in .mp4 or .mov format...'})
    else:
        return render (request, 'video/add.html', {'patient' : selected_patient})

@login_required(login_url='user-login')
def video_view(request, f_id):
    uploaded_file = Video.objects.get(id=f_id)
    patient = Patient.objects.get(id=uploaded_file.patient.id)

    try:
        assessment_id = GMAssessment.objects.get(video_file = uploaded_file).id
    except ObjectDoesNotExist:
        assessment_id = False
        
    total_assessments_count = GMAssessment.objects.filter(patient= patient).count()
    # total_completed_assessments_count = GMAssessment.objects.filter(patient= patient, erert = True).count()
    # total_incompleted_assessments_count = GMAssessment.objects.filter(patient= patient, werwe = False).count()
    
    #check bookmark
    bm = Bookmark.objects.filter(bookmark_type='File').filter(object_id=uploaded_file.id).first
    
    context = {'patient' : patient,
               'file' : uploaded_file,
               'assessment_id' : assessment_id,
               'total_assessments_count' : total_assessments_count,
               'total_completed_assessments_count' : total_assessments_count,
               'bookmark' : bm,
               'total_incompleted_assessments_count' : total_assessments_count}
    
    return render (request, 'video/view.html', context)

@login_required(login_url='user-login')
def video_edit(request, f_id):
    uploaded_file_object = Video.objects.get(id=f_id)
    selected_patient = Patient.objects.get(id=uploaded_file_object.patient.id)
    video_form = VideoForm(instance=uploaded_file_object)
    
    if request.method == 'POST':
        video_form_updated = VideoForm(request.POST, request.FILES, instance=uploaded_file_object)
        
        if video_form_updated.is_valid():
            var_uploaded_file = video_form_updated.cleaned_data['video']
            if validateVideoSize(var_uploaded_file):
                if validateVideoType(var_uploaded_file):
                    video_form_updated.save()

                    uploaded_file_object.last_edit_by = request.user
                    uploaded_file_object.last_edit_on = localtime(now())
                    uploaded_file_object.save(update_fields=['last_edit_by', 'last_edit_on']) 

                    new_updated_file_object = Video.objects.get(id=f_id)
                    new_updated_file_object.save()
                    
                    messages.success(request, 'Video infomations are updated succussfully...')
                    return render (request, 'video/view.html', {'patient' : selected_patient, 'file' : new_updated_file_object})
                else:
                    messages.warning(request, 'Only video files(mp4, mov) are allowed to upload...')
                    return render (request, 'video/edit.html', {'file' : uploaded_file_object, 'patient' : selected_patient, 'video_form' : video_form_updated})
            else:
                messages.warning(request, 'You cant upload file size > 100mb video...')
                return render (request, 'video/edit.html', {'file' : uploaded_file_object, 'patient' : selected_patient, 'video_form' : video_form_updated})
        else:
            messages.error(request, video_form_updated.errors)
            return render (request, 'video/edit.html', {'file' : uploaded_file_object, 'patient' : selected_patient, 'video_form' : video_form_updated})
    else:
        return render (request, 'video/edit.html', {'file' : uploaded_file_object, 'patient' : selected_patient, 'video_form' : video_form})

@login_required(login_url='user-login')
def video_delete_start(request, pk):
    file = Video.objects.get(id=pk)
    patient = Patient.objects.get(id=file.patient.id)
    return render (request, 'video/delete-confirm.html', {'file' : file, 'patient' : patient})

@login_required(login_url='user-login')
def video_delete(request, pk):
    if request.method == 'POST':
        file = Video.objects.get(id=pk)
        patient = Patient.objects.get(id=file.patient.id)
        user = request.user
        if user.check_password(request.POST['password']):
            if file.delete():
                messages.success(request, 'File was deleted succussfully')
                return redirect('view-patient', pk=patient.id)
            else:
                return render (request, 'video/delete-confirm.html', {'file' : file, 'patient' : patient})
        else:
            messages.error(request, 'Wrong password, please try again with correct password')
            return render (request, 'video/delete-confirm.html', {'file' : file, 'patient' : patient})

@login_required(login_url='user-login')
def video_manager_by_patient(request, patient_id):
    patient = Patient.objects.get(id=patient_id)
    var_file_list = Video.objects.filter(patient=patient).order_by('-id')
    paginator = Paginator(var_file_list, 25)
    page_number = request.GET.get('page')
    file_list = paginator.get_page(page_number)
    context= {'patient' : patient, 'file_list' : file_list}
    return render (request, 'video/manager.html', context)

@login_required(login_url='user-login')
def video_manager(request):
    var_file_list = Video.objects.all().order_by('-id')
    paginator = Paginator(var_file_list, 25)
    page_number = request.GET.get('page')
    file_list = paginator.get_page(page_number)
    return render (request, 'video/manager.html', {'patient' : '', 'file_list' : file_list})

@login_required(login_url='user-login')
def video_manager_new_only(request):
    var_file_list = Video.objects.filter(gmassessment__isnull=True)
    paginator = Paginator(var_file_list, 25)
    page_number = request.GET.get('page')
    file_list = paginator.get_page(page_number)
    return render (request, 'video/manager.html', {'patient' : '', 'file_list' : file_list})

# methods for assessment operations ------------------------------------------------------------------------------
@login_required(login_url='user-login')
def assessment_add(request, ptid, fid):
    patient = Patient.objects.get(pk=ptid)
    assessment_form = GMAssessmentForm()
    file = Video.objects.get(pk=fid)
    
    if request.method == 'POST':
        
        assessment_form_data = GMAssessmentForm(request.POST)
        if assessment_form_data.is_valid():
            
            date = assessment_form_data.cleaned_data['date_of_assessment']
            diagnosis = assessment_form_data.cleaned_data['diagnosis']
            diagnosis_other = assessment_form_data.cleaned_data['diagnosis_other']
            management_plan = assessment_form_data.cleaned_data['management_plan']
            next_assessment_date = assessment_form_data.cleaned_data['next_assessment_date']
            parent_informed = assessment_form_data.cleaned_data['parent_informed']
            
            #check assessment already added to this file
            if GMAssessment.objects.filter(video_file=file).exists() == False:
                
                prep_assessment = GMAssessment.objects.create(
                patient = patient,
                video_file = file,
                date_of_assessment = date,
                diagnosis_other = diagnosis_other,
                management_plan = management_plan,
                next_assessment_date = next_assessment_date,
                parent_informed = parent_informed,
                added_by = request.user,
                last_edit_by = None)

                prep_assessment.diagnosis.set(diagnosis)
                prep_assessment.save()

                messages.success(request, 'New assessment added succusfully')
                return redirect('assessment-view', pk=prep_assessment.id)
            else:
                previous_assmnt = GMAssessment.objects.get(files=file)
                messages.warning(request, 'One assessment already there for this file...')
                return redirect('assessment-view', pk=previous_assmnt.id)
        else:
            messages.error(request, assessment_form_data.errors)
            return render (request, 'assessment/add.html', {'form' : assessment_form_data, 'patient' : patient, 'file' : file})
    else:
        return render (request, 'assessment/add.html', {'form' : assessment_form, 'patient' : patient, 'file' : file})

@login_required(login_url='user-login')
def assessment_view(request, pk):
    assmnt = GMAssessment.objects.get(id=pk)
    #check bookmark
    bm = Bookmark.objects.filter(bookmark_type='Assessment').filter(object_id=assmnt.id).first
    return render (request, 'assessment/view.html', {'assessment' : assmnt, 'bookmark' : bm})

@login_required(login_url='user-login')
def assessment_view_by_fileid(request, file_id):
    assmnt = GMAssessment.objects.get(video_file=file_id)
    return render (request, 'assessment/view.html', {'assessment' : assmnt})

@login_required(login_url='user-login')
def assessment_edit(request, pk):
    assmnt = GMAssessment.objects.get(id=pk)
    assessment_form = GMAssessmentForm(instance=assmnt)
    if request.method == 'POST':
        assessment_form_data = GMAssessmentForm(request.POST, instance=assmnt)
        if assessment_form_data.is_valid():
            assessment_form_data.save()
            messages.success(request, 'Assessment details are updated succesfully...')
            return redirect('assessment-view', pk=assmnt.id)
        else:
            messages.success(request, assessment_form_data.errors)
            return render (request, 'assessment/edit.html', {'form' : assessment_form_data, 'assmnt' : assmnt})
    return render (request, 'assessment/edit.html', {'form' : assessment_form, 'assmnt' : assmnt})

@login_required(login_url='user-login')
def assessment_edit_by_fileid(request, pk):
    assmnt = GMAssessment.objects.get(files=pk)
    assessment_form = GMAssessmentForm(instance=assmnt)
    if request.method == 'POST':
        assessment_form_data = GMAssessmentForm(request.POST, instance=assmnt)
        if assessment_form_data.is_valid():
            assessment_form_data.save()
            messages.success(request, 'Assessment details are updated succesfully...')
            return redirect('assessment-view', pk=assmnt.id)
        else:
            messages.success(request, assessment_form_data.errors)
            return render (request, 'assessment/edit.html', {'form' : assessment_form_data, 'assmnt' : assmnt})
    return render (request, 'assessment/edit.html', {'form' : assessment_form, 'assmnt' : assmnt})

@login_required(login_url='user-login')
def assessment_delete_start(request, pk):
    assemnt = GMAssessment.objects.get(id=pk)
    patient = Patient.objects.get(id=assemnt.patient.id)
    return render (request, 'assessment/delete-confirm.html', {'assemnt' : assemnt, 'patient' : patient})

@login_required(login_url='user-login')
def assessment_delete(request, pk):
    if request.method == 'POST':
        assemnt = GMAssessment.objects.get(id=pk)
        patient = Patient.objects.get(id=assemnt.patient.id)
        user = request.user
        if user.check_password(request.POST['password']):
            if assemnt.delete():
                messages.success(request, 'Assessment deleted succusfully...')
                return redirect('assessment-manager-patient', pk=patient.id)
            else:
                messages.error(request, 'Something went wrong while deleting the assessment...')
                return render (request, 'assessment/delete-confirm.html', {'assemnt' : assemnt, 'patient' : patient})
        else:
            messages.error(request, 'Wrong password, please try again with correct password')
            return render (request, 'assessment/delete-confirm.html', {'assemnt' : assemnt, 'patient' : patient})

@login_required(login_url='user-login')
def assessment_manager(request):
    assessment_list = GMAssessment.objects.all().order_by('-id')
    paginator = Paginator(assessment_list, 10)
    page_number = request.GET.get('page')
    paginated_assmnt_list = paginator.get_page(page_number)
    return render (request, 'assessment/manager.html', {'assessment_page_obj': paginated_assmnt_list})

@login_required(login_url='user-login')
def assessment_manager_by_patients(request, pk):
    patient = Patient.objects.get(id=pk)
    assessment_list = GMAssessment.objects.filter(patient=patient).order_by('-id')
    paginator = Paginator(assessment_list, 10)
    page_number = request.GET.get('page')
    paginated_assmnt_list = paginator.get_page(page_number)
    return render (request, 'assessment/manager.html', {'patient' : patient, 'assessment_page_obj': paginated_assmnt_list})

# Help/ tutorials

@login_required(login_url='user-login')
def help_home(request):
    articles = Help.objects.all()
    return render (request, 'help/home.html', {'articles' : articles})

@login_required(login_url='user-login')
def help_article(request, pk):
    article = Help.objects.get(id=pk)
    articles = Help.objects.all()
    return render (request, 'help/article.html', {'article' : article, 'articles' : articles})

@login_required(login_url='user-login')
def bookmark_manager(request):
    var_patients_list = Bookmark.objects.all().order_by('-id')
    paginator = Paginator(var_patients_list, 10)
    page_number = request.GET.get('page')
    bookmark_list = paginator.get_page(page_number)
    return render (request, 'bookmark/manager.html', {'bookmark_page_obj': bookmark_list})

@login_required(login_url='user-login')
def bookmark_add(request, item_id, bookmark_type):
    bookmark_form = BookmarkForm()
    
    if request.method == 'POST':
        bookmark_form_data = BookmarkForm(request.POST)
        if bookmark_form_data.is_valid():
            
            title = bookmark_form_data.cleaned_data['title']
            description = bookmark_form_data.cleaned_data['description']

            #check bookmark already exist
            if Bookmark.objects.filter(bookmark_type=bookmark_type).filter(object_id=item_id).exists() == False:
                
                prep_bm = Bookmark.objects.create(
                title = title,
                bookmark_type = bookmark_type,
                object_id = item_id,
                description = description,
                owner = request.user,
                last_edit_by = None,
                last_edit_on = None,
                )

                messages.success(request, 'New bookmark created succusfully')
                return redirect('bookmark-view', pk=prep_bm.id)
            else:
                messages.warning(request, 'Already bookmarked, please remove before create new bookmark...')
                return render (request, 'bookmark/add.html', {'form' : bookmark_form_data, 'item_id' : item_id, 'bookmark_type' : bookmark_type})
        else:
            messages.error(request, bookmark_form_data.errors)
            return render (request, 'bookmark/add.html', {'form' : bookmark_form_data, 'item_id' : item_id, 'bookmark_type' : bookmark_type})
    else:
        return render (request, 'bookmark/add.html', {'form' : bookmark_form, 'item_id' : item_id, 'bookmark_type' : bookmark_type})
    
@login_required(login_url='user-login')
def bookmark_view(request, pk):
    bookmark = Bookmark.objects.get(id=pk)
    return render (request, 'bookmark/view.html', {'bookmark' : bookmark})

@login_required(login_url='user-login')
def bookmark_delete(request, pk):
    bookmark = Bookmark.objects.get(id=pk)
    if bookmark.owner == request.user:
        bookmark.delete()
        messages.success(request, 'Bookmark deleted succusfully')
        return redirect('bookmark-manager-user', request.user.username)
    else:
        messages.error(request, 'You have no permission to remove this book mark...')
        return render (request, 'bookmark/view.html', {'bookmark' : bookmark})

@login_required(login_url='user-login')
def bookmark_manager_user(request, username):
    user = CustomUser.objects.get(username=username)
    var_patients_list = Bookmark.objects.filter(owner=user).order_by('-id')
    paginator = Paginator(var_patients_list, 10)
    page_number = request.GET.get('page')
    bookmark_list = paginator.get_page(page_number)
    return render (request, 'bookmark/manager.html', {'bookmark_page_obj': bookmark_list})

@login_required(login_url='user-login')
def bookmark_edit(request, pk):
    selected_bm = Bookmark.objects.get(id=pk)
    bm_form = BookmarkForm(instance=selected_bm)
    if request.method == 'POST':
        bm_form_data = BookmarkForm(request.POST, instance=selected_bm)
        if bm_form_data.is_valid():
            title = bm_form_data.cleaned_data['title']
            description = bm_form_data.cleaned_data['description']
            selected_bm.title = title
            selected_bm.description = description
            selected_bm.last_edit_by = request.user
            selected_bm.last_edit_on = localtime(now())
            selected_bm.save(update_fields=['title', 'description', 'last_edit_by', 'last_edit_on']) 
            selected_bm.save()
            messages.success(request, 'Bookmark details are updated succesfully...')
            return redirect('bookmark-view', pk=selected_bm.id)
        else:
            messages.success(request, bm_form_data.errors)
            return render (request, 'bookmark/edit.html', {'form' : bm_form_data, 'bookmark' : selected_bm})
    return render (request, 'bookmark/edit.html', {'form' : bm_form, 'bookmark' : selected_bm})

# functionf for attachment operations

@login_required(login_url='user-login')
def attachment_manager(request):
    var_attachment_list = Attachment.objects.order_by('-id')
    paginator = Paginator(var_attachment_list, 10)
    page_number = request.GET.get('page')
    attachment_list = paginator.get_page(page_number)
    return render (request, 'attachment/manager.html', {'attachment_page_obj': attachment_list})

@login_required(login_url='user-login')
def attachment_manager_patient(request, pid):
    var_attachment_list = Attachment.objects.filter(patient=pid).order_by('-id')
    paginator = Paginator(var_attachment_list, 10)
    page_number = request.GET.get('page')
    attachment_list = paginator.get_page(page_number)
    return render (request, 'attachment/manager.html', {'attachment_page_obj': attachment_list})

@csrf_exempt
@login_required(login_url='user-login')
def attachment_add(request, pid):
    
    selected_patient = Patient.objects.get(pk=pid)
    attachment_form = AttachmentkForm()
    
    temp_file = None
    
    if request.method == 'POST':
        title = request.POST['title']
        attachment = request.FILES['attachment']
        description = request.POST["descreption"]
        
        if validateAttachmentSize(attachment):
            if validateAttachmentType(attachment):
                # save file object
                temp_file = Attachment(
                patient = selected_patient,
                title = title,
                attachment = attachment,
                attachment_type = getAttachmentType(attachment),
                description = description,
                uploaded_by = request.user,
                uploaded_on = getCurrentDateTime(),
                last_edit_by = None,
                last_edit_on = None,)

                temp_file.save()

                if temp_file != None:
                    return JsonResponse({'success': True, 'msg': 'OK', 'p_id': selected_patient.id, 'f_id': temp_file.id})
                else:
                    return JsonResponse({'success': False, 'msg': 'Something went wrong during file uploading, Please try again...'})
            else:
                return JsonResponse({'success': False, 'msg': 'Only allowed file types are PDF, Videos (.mp4, .mov), Images (.jpg, .jpeg)...'})
        else:
            return JsonResponse({'success': False, 'msg': 'You cant upload >100mb files...'})
    else:
        return render (request, 'attachment/add.html', {'patient' : selected_patient, 'attachment_form' : attachment_form})

@login_required(login_url='user-login')
def attachment_view(request, pk):
    sa = Attachment.objects.get(pk=pk)
    return render (request, 'attachment/view.html', {'patient': sa.patient, 'attachment': sa})

@login_required(login_url='user-login')
def attachment_edit(request, pk):
    sa = Attachment.objects.get(pk=pk)

    a_form = AttachmentkForm(instance=sa)
    
    if request.method == 'POST':
        bm_form_data = AttachmentkForm(request.POST, request.FILES, instance=sa)
        
        if bm_form_data.is_valid():
            attachment = bm_form_data.cleaned_data['attachment']
            if validateAttachmentSize(attachment):
                if validateAttachmentType(attachment):
                    bm_form_data.save()

                    sa.attachment_type = getAttachmentType(attachment)

                    sa.last_edit_by = request.user
                    sa.last_edit_on = localtime(now())
                    sa.save(update_fields=['attachment_type', 'last_edit_by', 'last_edit_on'])
                    sa.save()
                    
                    messages.success(request, 'Attachment details are updated succesfully...')
                    return redirect('attachment-view', pk=sa.id)
                else:
                    messages.warning(request, 'You cant upload files other dan videos(mp4, mov), image(jpg, jpeg), PDF...')
                    return render (request, 'attachment/edit.html', {'form' : a_form, 'attachment' : sa})
            else:
                messages.warning(request, 'You cant upload file size >100mb...')
                return render (request, 'attachment/edit.html', {'form' : a_form, 'attachment' : sa})
        else:
            messages.success(request, bm_form_data.errors)
            return render (request, 'attachment/edit.html', {'form' : bm_form_data, 'attachment' : sa})
    else:
        return render (request, 'attachment/edit.html', {'form' : a_form, 'attachment' : sa})

@login_required(login_url='user-login')
def attachment_delete_confirm(request, pk):
    attachment = Attachment.objects.get(id=pk)
    patient = attachment.patient
    return render (request, 'attachment/delete-confirm.html', {'attachment' : attachment, 'patient' : patient}) 

@login_required(login_url='user-login')
def attachment_delete(request, pk):
    user = request.user
    attachment = Attachment.objects.get(pk=pk)
    
    if user.check_password(request.POST['password']):
        if attachment.delete():
            messages.success('Attachment deleted succussfully...')
            return redirect('attachment-manager')
        else:
            messages.error('Something went wrong during delete the attachment...')
            return render (request, 'attachment/view.html', {'patient': attachment.patient, 'attachment': attachment})
    else:
        messages.error(request, 'Wrong password, please try again with correct password')
        return render (request, 'attachment/view.html', {'patient': attachment.patient, 'attachment': attachment})

# Functions for cdic assessments

@login_required(login_url='user-login')
def cdic_assessment_add(request, pid):
    selected_patient = Patient.objects.get(pk=pid)
    cdic_assemnt_form = CDICRecordForm()

    if request.method == 'POST':
        cdic_assemnt_form_data = CDICRecordForm(request.POST)
        if cdic_assemnt_form_data.is_valid():
            cdic_record = cdic_assemnt_form_data.save(commit=False)
            cdic_record.patient = selected_patient
            cdic_record.created_by = request.user
            cdic_record.save()
            messages.success(request, 'New CDIC record addes successfully...')
            return redirect('cdic-assessment-view', cdic_record.id)
    else:
        return render (request, 'cdic_record/add.html', {'patient' : selected_patient, 'cdic_assemnt_form' : cdic_assemnt_form})

@login_required(login_url='user-login')
def cdic_assessment_edit(request, aid):
    srecord = CDICRecord.objects.get(id=aid)
    spt = srecord.patient
    
    cdicr_form = CDICRecordForm(instance=srecord)
    
    if request.method == 'POST':
        cdicr_form_data = CDICRecordForm(request.POST, instance=srecord)
        if cdicr_form_data.is_valid():
            cdicr = cdicr_form_data.save(commit=False)

            cdicr.edit_by = request.user
            cdicr.edit_on = getCurrentDateTime()
            cdicr.save()
            
            messages.success(request, 'CDIC record updated succesfully...')
            return redirect('cdic-assessment-view', cdicr.id)
        else:
            messages.success(request, cdicr_form_data.errors)
            return render (request, 'cdic_record/edit.html', {'cdic_assemnt_form' : cdicr_form_data, 'patient' : spt})
    return render (request, 'cdic_record/edit.html', {'cdic_assemnt_form' : cdicr_form, 'cdic_record' : srecord, 'patient' : spt})

@login_required(login_url='user-login')
def cdic_assessment_view(request, cdic_id):
    selected_cdic_record = CDICRecord.objects.get(pk=cdic_id)
    return render (request, 'cdic_record/view.html', {'CDICRecord' : selected_cdic_record})

@login_required(login_url='user-login')
def cdic_assessment_manager(request):
    var_cdic_list = CDICRecord.objects.all().order_by('-id')
    paginator = Paginator(var_cdic_list, 10)
    page_number = request.GET.get('page')
    cdic_record_list = paginator.get_page(page_number)
    return render (request, 'cdic_record/manager.html', {'cdic_record_list': cdic_record_list})

@login_required(login_url='user-login')
def cdic_assessment_manager_by_patients(request, pid):
    sp = Patient.objects.get(pk=pid)
    var_cdic_list = CDICRecord.objects.filter(patient=sp.id).order_by('-id')
    paginator = Paginator(var_cdic_list, 10)
    page_number = request.GET.get('page')
    cdic_record_list = paginator.get_page(page_number)
    return render (request, 'cdic_record/manager.html', {'patient' : sp, 'cdic_record_list': cdic_record_list})

@login_required(login_url='user-login')
def cdic_assessment_delete_start(request, aid):
    srecord = CDICRecord.objects.get(id=aid)
    return render (request, 'cdic_record/delete-confirm.html', {'patient' : srecord.patient, 'cdic_record': srecord})

@login_required(login_url='user-login')
def cdic_assessment_delete(request, aid):
    user = request.user
    srecord = CDICRecord.objects.get(pk=aid)
    
    if user.check_password(request.POST['password']):
        if srecord.delete():
            messages.success(request, 'Record deleted succussfully...')
            return redirect('cdic-assessment-manager')
        else:
            messages.error(request, 'Something went wrong during delete the record...')
            return render (request, 'cdic_record/view.html', {'patient': srecord.patient, 'CDICRecord': srecord})
    else:
        messages.error(request, 'Wrong password, please try again with correct password')
        return render (request, 'cdic_record/view.html', {'patient': srecord.patient, 'CDICRecord': srecord})

# Functions for HINE assessments
@login_required(login_url='user-login')
def hine_assessment_add(request, pid):
    sp = Patient.objects.get(pk=pid)
    hine_form = HINEAssessmentForm()
    if request.method == 'POST':
        hine_form_data = HINEAssessmentForm(request.POST)
        if hine_form_data.is_valid():
            hine_record = hine_form_data.save(commit=False)
            hine_record.patient = sp
            hine_record.added_by = request.user
            hine_record.added_on = getCurrentDateTime()
            hine_record.save()
            messages.success(request, 'New HINE record created successfully...')
            return redirect('hine-assessment-view', hine_record.id)
        else:
            messages.error(request, hine_form_data.errors)
            return render (request, 'hine/add.html', {'patient': sp, 'hine_form': hine_form_data})
    else:
        return render (request, 'hine/add.html', {'patient': sp, 'hine_form': hine_form})

@login_required(login_url='user-login')
def hine_assessment_edit(request, hine_id):
    shr = HINEAssessment.objects.get(pk=hine_id)
    sp = shr.patient
    hine_form = HINEAssessmentForm(instance=shr)
    if request.method == 'POST':
        hine_form_data = HINEAssessmentForm(request.POST, instance=shr)
        if hine_form_data.is_valid():
            hine_record = hine_form_data.save(commit=False)
            hine_record.patient = sp
            hine_record.last_edit_by = request.user
            hine_record.save()
            messages.success(request, 'New HINE record created successfully...')
            return redirect('hine-assessment-view', hine_record.id)
        else:
            messages.error(request, hine_form_data.errors)
            return render (request, 'hine/edit.html', {'patient': sp, 'shr': shr, 'hine_form': hine_form_data})
    else:
        return render (request, 'hine/edit.html', {'patient': sp, 'shr': shr, 'hine_form': hine_form})

@login_required(login_url='user-login')
def hine_assessment_view(request, hine_id):
    sh = HINEAssessment.objects.get(pk=hine_id)
    return render (request, 'hine/view.html', {'patient': sh.patient, 'HINERecord': sh})

@login_required(login_url='user-login')
def hine_assessment_manager(request):
    var_hine_list = HINEAssessment.objects.all().order_by('-id')
    paginator = Paginator(var_hine_list, 10)
    page_number = request.GET.get('page')
    hine_record_list = paginator.get_page(page_number)
    return render (request, 'hine/manager.html', {'patient' : '', 'hine_record_list': hine_record_list})

@login_required(login_url='user-login')
def hine_assessment_manager_by_patients(request, pid):
    sp = Patient.objects.get(pk=pid)
    var_hine_list = HINEAssessment.objects.filter(patient=sp.id).order_by('-id')
    paginator = Paginator(var_hine_list, 10)
    page_number = request.GET.get('page')
    hine_record_list = paginator.get_page(page_number)
    return render (request, 'hine/manager.html', {'patient' : sp, 'hine_record_list': hine_record_list})

@login_required(login_url='user-login')
def hine_assessment_delete_start(request, hine_id):
    shr = HINEAssessment.objects.get(id=hine_id)
    return render (request, 'hine/delete-confirm.html', {'patient' : shr.patient, 'hine_record': shr})

@login_required(login_url='user-login')
def hine_assessment_delete(request, hine_id):
    user = request.user
    shr = HINEAssessment.objects.get(id=hine_id)
    
    if user.check_password(request.POST['password']):
        if shr.delete():
            messages.success(request, 'Record deleted succussfully...')
            return redirect('hine-assessment-manager')
        else:
            messages.error(request, 'Something went wrong during delete the record...')
            return render (request, 'hine/view.html', {'patient': shr.patient, 'HINERecord': shr})
    else:
        messages.error(request, 'Wrong password, please try again with correct password')
        return render (request, 'hine/view.html', {'patient': shr.patient, 'HINERecord': shr})

# Functions for Developmental assessments
@login_required(login_url='user-login')
def da_assessment_add(request, pid):
    sp = Patient.objects.get(pk=pid)
    da_form = DevelopmentalAssessmentForm()
    if request.method == 'POST':
        da_form_data = DevelopmentalAssessmentForm(request.POST)
        if da_form_data.is_valid():
            da_record = da_form_data.save(commit=False)
            da_record.patient = sp
            da_record.added_by = request.user
            da_record.save()
            messages.success(request, 'New developmental assessment record created successfully...')
            return redirect('da-assessment-view', da_record.id)
        else:
            messages.error(request, da_form_data.errors)
            return render (request, 'develop_assemnt/add.html', {'patient': sp, 'da_form': da_form_data})
    else:
        return render (request, 'develop_assemnt/add.html', {'patient': sp, 'da_form': da_form})

@login_required(login_url='user-login')
def da_assessment_edit(request, da_id):
    dar = DevelopmentalAssessment.objects.get(id=da_id)
    assessment_form = DevelopmentalAssessmentForm(instance=dar)
    if request.method == 'POST':
        assessment_form_data = DevelopmentalAssessmentForm(request.POST, instance=dar)
        if assessment_form_data.is_valid():
            da_record = assessment_form_data.save(commit=False)
            da_record.last_edit_by = request.user
            da_record.save()
            messages.success(request, 'Developmental assessment details are updated succesfully...')
            return redirect('da-assessment-view', dar.id)
        else:
            messages.success(request, assessment_form_data.errors)
            return render (request, 'develop_assemnt/edit.html', {'da_form' : assessment_form_data, 'dar' : dar})
    return render (request, 'develop_assemnt/edit.html', {'da_form' : assessment_form, 'dar' : dar})

@login_required(login_url='user-login')
def da_assessment_view(request, da_id):
    sdar = DevelopmentalAssessment.objects.get(pk=da_id)
    return render (request, 'develop_assemnt/view.html', {'DARecord': sdar})

@login_required(login_url='user-login')
def da_assessment_manager(request):
    var_da_list = DevelopmentalAssessment.objects.all().order_by('-id')
    paginator = Paginator(var_da_list, 10)
    page_number = request.GET.get('page')
    da_record_list = paginator.get_page(page_number)
    return render (request, 'develop_assemnt/manager.html', {'patient' : '', 'da_record_list': da_record_list})

@login_required(login_url='user-login')
def da_assessment_manager_by_patients(request, pid):
    sp = Patient.objects.get(pk=pid)
    var_da_list = DevelopmentalAssessment.objects.filter(patient=sp.id).order_by('-id')
    paginator = Paginator(var_da_list, 10)
    page_number = request.GET.get('page')
    da_record_list = paginator.get_page(page_number)
    return render (request, 'develop_assemnt/manager.html', {'patient' : sp, 'da_record_list': da_record_list})

@login_required(login_url='user-login')
def da_assessment_delete_start(request, da_id):
    sdr = DevelopmentalAssessment.objects.get(id=da_id)
    return render (request, 'develop_assemnt/delete-confirm.html', {'patient' : sdr.patient, 'da_record': sdr})

@login_required(login_url='user-login')
def da_assessment_delete(request, da_id):
    user = request.user
    sdar = DevelopmentalAssessment.objects.get(id=da_id)
    
    if user.check_password(request.POST['password']):
        if sdar.delete():
            messages.success(request, 'Record deleted succussfully...')
            return redirect('da-assessment-manager')
        else:
            messages.error(request, 'Something went wrong during delete the record...')
            return render (request, 'develop_assemnt/view.html', {'patient': sdar.patient, 'DARecord': sdar})
    else:
        messages.error(request, 'Wrong password, please try again with correct password')
        return render (request, 'develop_assemnt/view.html', {'patient': sdar.patient, 'DARecord': sdar})

@login_required(login_url='user-login')
def print(request):
    pass