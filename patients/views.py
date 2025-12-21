from django.shortcuts import redirect, render, get_object_or_404
from datetime import timedelta, date
from django.utils import timezone
from django.urls import reverse
import json
from patients.models import (
    Patient,
    GMAssessment,
    CDICRecord,
    Help,
    Bookmark,
    Attachment,
    HINEAssessment,
    DevelopmentalAssessment,
    GeneralPaediatricAssessment,
)
from video.models import Video
from users.models import CustomUser
from users.views import userViewByUsername
from patients.forms import (
    PatientForm,
    GMAssessmentForm,
    BookmarkForm,
    AttachmentkForm,
    CDICRecordForm,
    HINEAssessmentForm,
    DevelopmentalAssessmentForm,
    GeneralPaediatricAssessmentForm,
)
from ndas.custom_codes.choice import BOOKMARK_TYPE
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ndas.custom_codes.validators import (
    Name_baby_validation,
    Name_mother_validation,
    BHT_validation,
    PHN_validation,
    NNC_validation,
    validateVideoSize,
    validateVideoType,
    validateAttachmentSize,
    validateAttachmentType,
    validate_video_file_upload,
    getVideoMaxSizeMB,
)
from ndas.custom_codes.custom_methods import (
    get_admissions_data_barchart,
    get_gma_diagnosis_data,
    get_all_diagnosis_data,
    get_userStats,
    getAttachmentType,
    getCurrentDateTime,
    getFileSizeInMb,
    getPatientList,
    getCountZeroIfNone,
)
from patients.timeline_utils import get_patient_timeline_events
from patients.timeline_utils import get_patient_timeline_events
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import pytz, os, logging, subprocess, tempfile
from django.http import JsonResponse
from django.utils.timezone import localtime, now
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

# from moviepy.editor import VideoFileClip  # Temporarily commented out
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from ndas.custom_codes.ndas_enums import PtStatus

# Configure logger for patient operations
logger = logging.getLogger("django")


# Create your views here
@login_required(login_url="user-login")
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

    dx_gm_assessments_count = getCountZeroIfNone(
        GMAssessment.objects.exclude(diagnosis_conclusion="NORMAL")
    )
    dx_hine_assessments_count = getCountZeroIfNone(
        HINEAssessment.objects.filter(score__lt=73)
    )
    dx_da_assessments_count = getCountZeroIfNone(
        DevelopmentalAssessment.objects.filter(is_dx_normal=False)
    )

    # get data for bar chart
    bar_chart_monthly_admissions = get_admissions_data_barchart()
    diagnosis_data_gma = get_gma_diagnosis_data()
    diagnosis_data_all = get_all_diagnosis_data()
    user_stat = get_userStats()

    context = {
        "videos_total_count": videos_total_count,
        "dx_gm_assessments_count": dx_gm_assessments_count,
        "dx_hine_assessments_count": dx_hine_assessments_count,
        "dx_da_assessments_count": dx_da_assessments_count,
        "all_gm_assessments_count": all_gm_assessments_count,
        "all_hine_assessments_count": all_hine_assessments_count,
        "all_da_assessments_count": all_da_assessments_count,
        "all_cdic_records_count": all_cdic_records_count,
        "new_videos": new_videos,
        "new_videos_count": new_videos_count,
        "videos_total_count": videos_total_count,
        "patients_total_count": patients_total_count,
        "Patients_new_list_10": Patients_new_list_10,
        "patients_new_count": patients_new_count,
        "patients_discharged_count": patients_discharged_count,
        "bookmark": bookmark,
        "bar_chart_monthly_admissions": bar_chart_monthly_admissions,
        "diagnosis_data_gma": diagnosis_data_gma,
        "diagnosis_data_all": diagnosis_data_all,
        "users_total_count": users_total_count,
        "attachments_count": attachments_count,
        "user_stat": user_stat,
    }

    return render(request, "patients/index.html", context)


@login_required(login_url="user-login")
def patient_manager(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Filter patients based on search query
    if search_query:
        patients_list = Patient.objects.filter(
            Q(baby_name__icontains=search_query) |
            Q(mother_name__icontains=search_query) |
            Q(bht__icontains=search_query) |
            Q(nnc_no__icontains=search_query)
        ).order_by("-id")
    else:
        patients_list = Patient.objects.all().order_by("-id")

    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get("page")
    paginated_pt_list = paginator.get_page(page_number)

    context = {
        "patients_page_obj": paginated_pt_list,
        "search_query": search_query,
    }

    return render(request, "patients/manager.html", context)


@login_required(login_url="user-login")
def patient_manager_diagnosed_any(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Get base filtered list
    patients_list = getPatientList(PtStatus.DIAGNOSED)

    # Apply search filter if provided
    if search_query:
        patients_list = patients_list.filter(
            Q(baby_name__icontains=search_query) |
            Q(mother_name__icontains=search_query) |
            Q(bht__icontains=search_query) |
            Q(nnc_no__icontains=search_query)
        )

    patients_list = patients_list.order_by("-id")
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get("page")
    paginated_pt_list = paginator.get_page(page_number)

    context = {
        "patients_page_obj": paginated_pt_list,
        "type": "DIAGNOSED",
        "search_query": search_query,
    }

    return render(request, "patients/manager.html", context)


@login_required(login_url="user-login")
def patient_manager_diagnosis_normal(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Get base filtered list
    patients_list = getPatientList(PtStatus.DX_NORMAL)

    # Apply search filter if provided
    if search_query:
        patients_list = patients_list.filter(
            Q(baby_name__icontains=search_query) |
            Q(mother_name__icontains=search_query) |
            Q(bht__icontains=search_query) |
            Q(nnc_no__icontains=search_query)
        )

    patients_list = patients_list.order_by("-id")
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get("page")
    paginated_pt_list = paginator.get_page(page_number)

    context = {
        "patients_page_obj": paginated_pt_list,
        "type": "DX_NORMAL",
        "search_query": search_query,
    }

    return render(request, "patients/manager.html", context)


@login_required(login_url="user-login")
def patient_manager_diagnosed_gma_normal(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Get base filtered list
    patients_list = getPatientList(PtStatus.DX_GMA_NORMAL)

    # Apply search filter if provided
    if search_query:
        patients_list = patients_list.filter(
            Q(baby_name__icontains=search_query) |
            Q(mother_name__icontains=search_query) |
            Q(bht__icontains=search_query) |
            Q(nnc_no__icontains=search_query)
        )

    patients_list = patients_list.order_by("-id")
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get("page")
    paginated_pt_list = paginator.get_page(page_number)

    context = {
        "patients_page_obj": paginated_pt_list,
        "type": "DX_GMA_NORMAL",
        "search_query": search_query,
    }

    return render(request, "patients/manager.html", context)


@login_required(login_url="user-login")
def patient_manager_diagnosed_gma_abnormal(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Get base filtered list
    patients_list = getPatientList(PtStatus.DX_GMA_ABNORMAL)

    # Apply search filter if provided
    if search_query:
        patients_list = patients_list.filter(
            Q(baby_name__icontains=search_query) |
            Q(mother_name__icontains=search_query) |
            Q(bht__icontains=search_query) |
            Q(nnc_no__icontains=search_query)
        )

    patients_list = patients_list.order_by("-id")
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get("page")
    paginated_pt_list = paginator.get_page(page_number)

    context = {
        "patients_page_obj": paginated_pt_list,
        "type": "DX_GMA_ABNORMAL",
        "search_query": search_query,
    }

    return render(request, "patients/manager.html", context)


@login_required(login_url="user-login")
def patient_manager_diagnosed_hine(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Get base filtered list
    patients_list = getPatientList(PtStatus.DX_HINE)

    # Apply search filter if provided
    if search_query:
        patients_list = patients_list.filter(
            Q(baby_name__icontains=search_query) |
            Q(mother_name__icontains=search_query) |
            Q(bht__icontains=search_query) |
            Q(nnc_no__icontains=search_query)
        )

    patients_list = patients_list.order_by("-id")
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get("page")
    paginated_pt_list = paginator.get_page(page_number)

    context = {
        "patients_page_obj": paginated_pt_list,
        "type": "DX_HINE",
        "search_query": search_query,
    }

    return render(request, "patients/manager.html", context)


@login_required(login_url="user-login")
def patient_manager_da_normal(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Get base filtered list
    patients_list = getPatientList(PtStatus.DX_DA_NORMAL)

    # Apply search filter if provided
    if search_query:
        patients_list = patients_list.filter(
            Q(baby_name__icontains=search_query) |
            Q(mother_name__icontains=search_query) |
            Q(bht__icontains=search_query) |
            Q(nnc_no__icontains=search_query)
        )

    patients_list = patients_list.order_by("-id")
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get("page")
    paginated_pt_list = paginator.get_page(page_number)

    context = {
        "patients_page_obj": paginated_pt_list,
        "type": "DX_DA_NORMAL",
        "search_query": search_query,
    }

    return render(request, "patients/manager.html", context)


@login_required(login_url="user-login")
def patient_manager_da_abnormal(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Get base filtered list
    patients_list = getPatientList(PtStatus.DX_DA_ABNORMAL)

    # Apply search filter if provided
    if search_query:
        patients_list = patients_list.filter(
            Q(baby_name__icontains=search_query) |
            Q(mother_name__icontains=search_query) |
            Q(bht__icontains=search_query) |
            Q(nnc_no__icontains=search_query)
        )

    patients_list = patients_list.order_by("-id")
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get("page")
    paginated_pt_list = paginator.get_page(page_number)

    context = {
        "patients_page_obj": paginated_pt_list,
        "type": "DX_DA_ABNORMAL",
        "search_query": search_query,
    }

    return render(request, "patients/manager.html", context)


@login_required(login_url="user-login")
def patient_manager_discharged_only(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Get base filtered list
    patients_list = getPatientList(PtStatus.DISCHARGED)

    # Apply search filter if provided
    if search_query:
        patients_list = patients_list.filter(
            Q(baby_name__icontains=search_query) |
            Q(mother_name__icontains=search_query) |
            Q(bht__icontains=search_query) |
            Q(nnc_no__icontains=search_query)
        )

    patients_list = patients_list.order_by("-id")
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get("page")
    paginated_pt_list = paginator.get_page(page_number)

    context = {
        "patients_page_obj": paginated_pt_list,
        "type": "DISCHARGED",
        "search_query": search_query,
    }

    return render(request, "patients/manager.html", context)


@login_required(login_url="user-login")
def patient_manager_new_only(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Get base filtered list
    patients_list = Patient.objects.filter(videos__isnull=True)

    # Apply search filter if provided
    if search_query:
        patients_list = patients_list.filter(
            Q(baby_name__icontains=search_query) |
            Q(mother_name__icontains=search_query) |
            Q(bht__icontains=search_query) |
            Q(nnc_no__icontains=search_query)
        )

    patients_list = patients_list.order_by("-id")
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get("page")
    paginated_pt_list = paginator.get_page(page_number)

    context = {
        "patients_page_obj": paginated_pt_list,
        "type": "NEW",
        "search_query": search_query,
    }

    return render(request, "patients/manager.html", context)


@login_required(login_url="user-login")
def patient_add(request):
    if not request.user.is_authenticated:
        messages.error(
            request, "You are not authorized to perform this action, please login"
        )
        return redirect("user-login")

    if request.method == "POST":
        data_form = PatientForm(request.POST)

        if data_form.is_valid():
            # Additional server-side validation
            cleaned_data = data_form.cleaned_data

            # Validate POG ranges
            pog_wks = cleaned_data.get("pog_wks")
            pog_days = cleaned_data.get("pog_days")

            if pog_wks and (int(pog_wks) < 20 or int(pog_wks) > 44):
                data_form.add_error("pog_wks", "POG weeks must be between 20 and 44")

            if pog_days and (int(pog_days) < 0 or int(pog_days) > 6):
                data_form.add_error("pog_days", "POG days must be between 0 and 6")

            # Validate APGAR scores
            apgar_fields = ["apgar_1", "apgar_5", "apgar_10"]
            for field in apgar_fields:
                value = cleaned_data.get(field)
                if value is not None and (int(value) < 0 or int(value) > 10):
                    data_form.add_error(
                        field,
                        f'{field.replace("_", " ").title()} score must be between 0 and 10',
                    )

            # Validate birth weight
            birth_weight = cleaned_data.get("birth_weight")
            if birth_weight and (birth_weight < 200 or birth_weight > 8000):
                data_form.add_error(
                    "birth_weight", "Birth weight must be between 200g and 8000g"
                )

            # Validate measurements
            length = cleaned_data.get("length")
            if length and (length < 10 or length > 90):
                data_form.add_error("length", "Length must be between 10cm and 90cm")

            ofc = cleaned_data.get("ofc")
            if ofc and (ofc < 15 or ofc > 70):
                data_form.add_error("ofc", "OFC must be between 15cm and 70cm")

            # Check for duplicate BHT
            bht = cleaned_data.get("bht")
            if bht and Patient.objects.filter(bht=bht).exists():
                data_form.add_error("bht", "A patient with this BHT already exists")

            # Validate date of birth (not in future)
            dob_tob = cleaned_data.get("dob_tob")
            if dob_tob and dob_tob > timezone.now():
                data_form.add_error("dob_tob", "Date of birth cannot be in the future")

            # If validation passes, save the patient
            if not data_form.errors:
                try:
                    var_pt_add = data_form.save(commit=False)
                    var_pt_add.added_by = request.user
                    var_pt_add.last_edit_by = None
                    var_pt_add.save()

                    # Save many-to-many relationships (including GMA indicators)
                    data_form.save_m2m()

                    # Get count of GMA indicators for success message
                    gma_count = var_pt_add.indecation_for_gma.count()
                    gma_message = (
                        f" with {gma_count} GMA indicator(s)" if gma_count > 0 else ""
                    )

                    messages.success(
                        request,
                        f'New patient "{var_pt_add.baby_name}" added successfully{gma_message}!',
                    )
                    return redirect("view-patient", var_pt_add.id)

                except Exception as e:
                    messages.error(
                        request,
                        "An error occurred while saving the patient. Please try again.",
                    )
                    return render(request, "patients/add.html", {"form": data_form})

        # If form is not valid, return with errors
        return render(request, "patients/add.html", {"form": data_form})

    else:
        empty_form = PatientForm()
        return render(request, "patients/add.html", {"form": empty_form})


@login_required(login_url="user-login")
def patient_view(request, pk):
    selected_patient = Patient.objects.get(id=pk)
    indications = selected_patient.indecation_for_gma

    var_file_video = Video.objects.filter(patient=selected_patient).order_by("-id")
    file_video_count = var_file_video.count()
    file_videos = var_file_video[:5]

    var_file_attachments = Attachment.objects.filter(patient=selected_patient).order_by(
        "-id"
    )
    file_attachment_count = var_file_attachments.count()
    file_attachment = var_file_attachments[:5]

    var_gma = GMAssessment.objects.filter(patient=selected_patient).order_by("-id")
    gm_assessments_count = var_gma.count()
    gm_assessments = var_gma[:5]
    gm_last_assessment = var_gma.last

    var_hine = HINEAssessment.objects.filter(patient=selected_patient).order_by("-id")
    hine_assessments_count = var_hine.count()
    hine_assessments = var_hine[:5]

    var_da = DevelopmentalAssessment.objects.filter(patient=selected_patient).order_by(
        "-id"
    )
    da_assessments_count = var_da.count()
    da_assessments = var_da[:5]

    var_cdic = CDICRecord.objects.filter(patient=selected_patient).order_by("-id")
    cdic_record_count = var_cdic.count()
    cdic_record = var_cdic[:5]

    var_gpa = GeneralPaediatricAssessment.objects.filter(patient=selected_patient).select_related(
        'discharged_authorized_by', 'added_by'
    ).order_by("-assessment_date")
    gpa_assessments_count = var_gpa.count()
    gpa_assessments = var_gpa[:5]

    # Get timeline events
    timeline_events = get_patient_timeline_events(selected_patient)

    # check bookmark
    bm = (
        Bookmark.objects.filter(bookmark_type="Patient")
        .filter(object_id=selected_patient.id)
        .first()
    )

    # Prepare delete modal context
    warning_list = [
        f"All associated assessments ({gm_assessments_count} GMA, {hine_assessments_count} HINE, {da_assessments_count} Developmental, {cdic_record_count} CDIC, {gpa_assessments_count} GPA) will be deleted",
        f"All video files ({file_video_count}) and attachments ({file_attachment_count}) will be permanently removed",
        "All bookmarks related to this patient will be deleted",
        "This patient record will be permanently deleted from the system"
    ]

    patient_details = {
        "Baby Name": selected_patient.baby_name,
        "Mother Name": selected_patient.mother_name,
        "BHT": selected_patient.bht or "Not specified",
        "Gender": selected_patient.gender,
        "Date of Birth": selected_patient.dob_tob.strftime("%b %d, %Y") if selected_patient.dob_tob else "Not specified"
    }

    context = {
        "patient": selected_patient,
        "file_videos": file_videos,
        "file_video_count": file_video_count,
        "var_file_video": var_file_video,  # Full queryset for delete modals
        "file_attachment": file_attachment,
        "file_attachment_count": file_attachment_count,
        "var_file_attachments": var_file_attachments,  # Full queryset for delete modals
        "indications": indications,
        "bookmark": bm,
        "gm_assessments_new": "",
        "gm_assessments_completed": "",
        "gm_assessments": gm_assessments,
        "gm_assessments_count": gm_assessments_count,
        "gm_last_assessment": gm_last_assessment,
        "var_gma": var_gma,  # Full queryset for delete modals
        "hine_assessments_count": hine_assessments_count,
        "hine_assessments": hine_assessments,
        "var_hine": var_hine,  # Full queryset for delete modals
        "da_assessments_count": da_assessments_count,
        "da_assessments": da_assessments,
        "var_da": var_da,  # Full queryset for delete modals
        "cdic_record_count": cdic_record_count,
        "cdic_record": cdic_record,
        "var_cdic": var_cdic,  # Full queryset for delete modals
        "gpa_assessments_count": gpa_assessments_count,
        "gpa_assessments": gpa_assessments,
        "var_gpa": var_gpa,  # Full queryset for delete modals
        "timeline_events": timeline_events,
        "warning_list": warning_list,  # For patient delete modal
        "patient_details": patient_details,  # For patient delete modal
    }

    return render(request, "patients/view.html", context)


@login_required(login_url="user-login")
@require_http_methods(["DELETE"])
def patient_delete(request, pk):
    """
    Unified patient deletion endpoint with password verification and audit logging
    Part of refactor-delete-confirmation change

    Accepts: DELETE method with JSON payload {password: str}
    Returns: JSON {success: bool, message: str, redirect_url: str}
    """
    from ndas.custom_codes.delete_helpers import (
        has_delete_permission,
        validate_can_delete,
        get_entity_display_name,
        get_redirect_url
    )

    try:
        # 1. Retrieve patient
        patient = get_object_or_404(Patient, id=pk)

        # 2. Check permissions
        if not has_delete_permission(request.user, patient):
            logger.warning(
                f"Unauthorized deletion attempt: user={request.user.username}, "
                f"entity=Patient, id={pk}"
            )
            return JsonResponse({
                "success": False,
                "error": "Permission denied",
                "message": "You do not have permission to delete this patient."
            }, status=403)

        # 3. Verify password
        try:
            data = json.loads(request.body)
            password = data.get('password', '')
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "error": "Invalid request",
                "message": "Invalid request format."
            }, status=400)

        if not password:
            return JsonResponse({
                "success": False,
                "error": "Password required",
                "message": "Password is required to confirm deletion."
            }, status=400)

        if not request.user.check_password(password):
            logger.warning(
                f"Invalid password for deletion: user={request.user.username}, "
                f"entity=Patient, id={pk}"
            )
            return JsonResponse({
                "success": False,
                "error": "Invalid password",
                "message": "Incorrect password. Please try again."
            }, status=401)

        # 4. Check business rules
        validation_result = validate_can_delete(patient)
        if not validation_result['can_delete']:
            return JsonResponse({
                "success": False,
                "error": "Cannot delete",
                "message": validation_result['reason']
            }, status=400)

        # 5. Store info for logging and response
        patient_name = get_entity_display_name(patient)
        patient_info = {
            "id": patient.id,
            "baby_name": patient.baby_name,
            "mother_name": patient.mother_name,
            "bht": patient.bht,
            "deleted_by": request.user.username,
            "deleted_at": timezone.now().isoformat(),
        }

        # 6. Perform deletion
        patient.delete()

        # 7. Audit log
        logger.info(
            f"Deletion successful: user={request.user.username}, "
            f"entity=Patient, name={patient_name}, id={pk}, "
            f"details={patient_info}"
        )

        # 8. Return success
        return JsonResponse({
            "success": True,
            "message": f"Patient '{patient_name}' has been deleted successfully.",
            "redirect_url": get_redirect_url('Patient')
        })

    except Exception as e:
        logger.error(
            f"Deletion error: user={request.user.username}, "
            f"entity=Patient, id={pk}, error={str(e)}"
        )
        return JsonResponse({
            "success": False,
            "error": "Server error",
            "message": f"An error occurred during deletion: {str(e)}"
        }, status=500)


@login_required(login_url="user-login")
def patient_delete_confirm(request, pk):
    patient = Patient.objects.get(id=pk)
    user = request.user
    if user.is_superuser:
        return render(request, "patients/delete-confirm.html", {"patient": patient})
    else:
        messages.warning(
            request,
            "You dont have permission to delete this record. Please contact Administrator/ Developer",
        )
        return render(
            request, "patients/delete-confirm.html", {"patient": patient, "hide": True}
        )


@login_required(login_url="user-login")
def patient_edit(request, pk):
    try:
        selected_patient = Patient.objects.get(id=pk)
    except Patient.DoesNotExist:
        messages.error(request, "Patient not found.")
        return redirect("manage-patients")

    if request.method == "POST":
        data_form_modified = PatientForm(request.POST, instance=selected_patient)

        if data_form_modified.is_valid():
            try:
                # Save the form data
                patient = data_form_modified.save(commit=False)
                patient.last_edit_by = request.user
                patient.save()

                # Save many-to-many relationships
                data_form_modified.save_m2m()

                messages.success(request, "Patient details updated successfully.")
                return redirect("manage-patients")

            except Exception as e:
                messages.error(request, f"An error occurred while saving: {str(e)}")
                return render(
                    request,
                    "patients/edit.html",
                    {"form": data_form_modified, "patient": selected_patient},
                )
        else:
            # Form has validation errors
            messages.warning(request, "Please correct the errors below and try again.")
            return render(
                request,
                "patients/edit.html",
                {"form": data_form_modified, "patient": selected_patient},
            )
    else:
        # GET request - display form with current data
        data_form = PatientForm(instance=selected_patient)
        return render(
            request,
            "patients/edit.html",
            {"form": data_form, "patient": selected_patient},
        )


@login_required(login_url="user-login")
def search_start(request):
    username_list = CustomUser.objects.all()
    return render(request, "patients/search.html", {"username_list": username_list})


@login_required(login_url="user-login")
def search_results(request):
    """
    Enhanced search results view with improved error handling and performance optimization.
    Supports patient and user searches with comprehensive validation.
    """
    # Early validation for POST method
    if request.method != "POST":
        messages.warning(request, "Please use the search form to perform searches.")
        return redirect("search-start")

    # Get search parameters
    combo_record_type = request.POST.get("combo_record_type", "").strip()
    combo_pt_param_type = request.POST.get("combo_pt_param_type", "").strip()
    combo_user_username = request.POST.get("combo_users", "").strip()
    search_text = request.POST.get("search_text", "").strip()
    pagn = ""

    # Validate required parameters
    if not combo_record_type:
        messages.error(request, "Please select a record type.")
        username_list = CustomUser.objects.all()
        return render(request, "patients/search.html", {"username_list": username_list})

    # Search patients --------------------------------------------------------------
    if combo_record_type == "rtype_pt":
        # Validate patient search parameters
        if not combo_pt_param_type:
            messages.error(request, "Please select a patient search parameter.")
            username_list = CustomUser.objects.all()
            return render(request, "patients/search.html", {"username_list": username_list})

        if not search_text:
            messages.error(request, "Please enter search text.")
            username_list = CustomUser.objects.all()
            return render(request, "patients/search.html", {"username_list": username_list})

        # Search by BHT
        if combo_pt_param_type == "pts_bht" and BHT_validation(request, search_text):
            pagn = f"Patients > BHT > {search_text}"
            try:
                patient = Patient.objects.get(bht=search_text)
                messages.success(request, f"Found patient with BHT: {search_text}")
                return render(
                    request, "patients/view.html", {"patient": patient, "pgn": pagn}
                )
            except Patient.DoesNotExist:
                messages.warning(request, f"No patient found with BHT: {search_text}")
                return render(
                    request,
                    "patients/search_notfound.html",
                    {"pgn": pagn},
                )

        # Search by PHN
        elif combo_pt_param_type == "pts_phn" and PHN_validation(request, search_text):
            pagn = f"Patients > PHN > {search_text}"
            try:
                patient = Patient.objects.get(pin=search_text)
                messages.success(request, f"Found patient with PHN: {search_text}")
                return render(
                    request, "patients/view.html", {"patient": patient, "pgn": pagn}
                )
            except Patient.DoesNotExist:
                messages.warning(request, f"No patient found with PHN: {search_text}")
                return render(
                    request,
                    "patients/search_notfound.html",
                    {"pgn": pagn},
                )

        # Search by NNC number
        elif combo_pt_param_type == "pts_nnc_no" and NNC_validation(request, search_text):
            pagn = f"Patients > Clinic Number > {search_text}"
            try:
                patient = Patient.objects.get(nnc_no=search_text)
                messages.success(request, f"Found patient with clinic number: {search_text}")
                return render(
                    request, "patients/view.html", {"patient": patient, "pgn": pagn}
                )
            except Patient.DoesNotExist:
                messages.warning(request, f"No patient found with clinic number: {search_text}")
                return render(
                    request,
                    "patients/search_notfound.html",
                    {"pgn": pagn},
                )

        # Search by baby name
        elif combo_pt_param_type == "pts_name_baby" and Name_baby_validation(request, search_text):
            pagn = f"Patients > Baby Name > {search_text}"
            # Use indexed fields for better performance
            patients = Patient.objects.filter(
                Q(baby_name__istartswith=search_text) | Q(baby_name__icontains=search_text)
            ).order_by("baby_name")

            if not patients.exists():
                messages.warning(request, f"No patients found with baby name containing: {search_text}")
                return render(request, "patients/search_notfound.html", {"pgn": pagn})

            if patients.count() == 1:
                messages.success(request, f"Found 1 patient with baby name: {search_text}")
                return render(
                    request,
                    "patients/view.html",
                    {
                        "patient": patients.first(),
                        "patients_page_obj": None,
                        "pgn": pagn,
                    },
                )
            else:
                # Multiple results - paginate
                paginator = Paginator(patients, 10)
                page_number = request.GET.get("page", 1)
                paginated_pt_list = paginator.get_page(page_number)
                messages.success(request, f"Found {patients.count()} patients with baby name containing: {search_text}")
                return render(
                    request,
                    "patients/results.html",
                    {
                        "patient": None,
                        "patients_page_obj": paginated_pt_list,
                        "pgn": pagn,
                    },
                )

        # Search by mother name
        elif combo_pt_param_type == "pts_name_mother" and Name_mother_validation(request, search_text):
            pagn = f"Patients > Mother Name > {search_text}"
            # Use indexed fields for better performance
            patients = Patient.objects.filter(
                Q(mother_name__istartswith=search_text) | Q(mother_name__icontains=search_text)
            ).order_by("mother_name")

            if not patients.exists():
                messages.warning(request, f"No patients found with mother name containing: {search_text}")
                return render(request, "patients/search_notfound.html", {"pgn": pagn})

            if patients.count() == 1:
                messages.success(request, f"Found 1 patient with mother name: {search_text}")
                return render(
                    request,
                    "patients/view.html",
                    {
                        "patient": patients.first(),
                        "patients_page_obj": None,
                        "pgn": pagn,
                    },
                )
            else:
                # Multiple results - paginate
                paginator = Paginator(patients, 10)
                page_number = request.GET.get("page", 1)
                paginated_pt_list = paginator.get_page(page_number)
                messages.success(request, f"Found {patients.count()} patients with mother name containing: {search_text}")
                return render(
                    request,
                    "patients/results.html",
                    {
                        "patient": None,
                        "patients_page_obj": paginated_pt_list,
                        "pgn": pagn,
                    },
                )
        else:
            # Validation failed
            messages.error(request, "Invalid search parameters. Please check your input and try again.")
            username_list = CustomUser.objects.all()
            return render(
                request, "patients/search.html", {"username_list": username_list}
            )

    # Search users --------------------------------------------------------------
    elif combo_record_type == "rtype_user":
        if not combo_user_username:
            messages.error(request, "Please select a user.")
            username_list = CustomUser.objects.all()
            return render(request, "patients/search.html", {"username_list": username_list})

        pagn = f"Users > Username > {combo_user_username}"
        messages.success(request, f"Viewing user profile: {combo_user_username}")
        return userViewByUsername(request, combo_user_username)

    # Invalid record type
    else:
        messages.error(request, "Invalid record type selected. Please try again.")
        username_list = CustomUser.objects.all()
        return render(request, "patients/search.html", {"username_list": username_list})


# methods for assessment operations ------------------------------------------------------------------------------
@login_required(login_url="user-login")
def assessment_add(request, ptid, fid):
    """Enhanced assessment creation with proper validation and error handling"""
    from django.http import JsonResponse
    from django.core.exceptions import ValidationError
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        patient = Patient.objects.get(pk=ptid)
        video_file = Video.objects.get(pk=fid)
    except (Patient.DoesNotExist, Video.DoesNotExist) as e:
        messages.error(request, "Patient or video file not found.")
        return redirect("manage-patients")

    # Check if assessment already exists for this video
    existing_assessment = GMAssessment.objects.filter(video_file=video_file).first()
    if existing_assessment:
        messages.warning(request, "An assessment already exists for this video.")
        return redirect("assessment-view", pk=existing_assessment.id)

    if request.method == "POST":
        assessment_form = GMAssessmentForm(request.POST)
        
        if assessment_form.is_valid():
            try:
                # Create assessment with proper validation
                assessment = assessment_form.save(commit=False)
                assessment.patient = patient
                assessment.video_file = video_file
                assessment.added_by = request.user
                
                # Additional validation
                if assessment.next_assessment_date and assessment.date_of_assessment:
                    if assessment.next_assessment_date <= assessment.date_of_assessment.date():
                        assessment_form.add_error('next_assessment_date', 
                            'Next assessment date must be after the current assessment date.')
                        raise ValidationError('Invalid next assessment date.')
                
                assessment.save()
                
                # Handle many-to-many relationship for diagnosis
                diagnosis_list = assessment_form.cleaned_data.get('diagnosis', [])
                if diagnosis_list:
                    assessment.diagnosis.set(diagnosis_list)
                
                logger.info(f"Assessment created successfully: {assessment.id} by user {request.user.id}")
                messages.success(request, "Assessment added successfully!")
                
                # Return JSON for AJAX requests
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({
                        "success": True,
                        "msg": "Assessment added successfully!",
                        "assessment_id": assessment.id,
                        "redirect_url": reverse("assessment-view", kwargs={"pk": assessment.id}),
                    })
                
                return redirect("assessment-view", pk=assessment.id)
                
            except ValidationError as e:
                logger.error(f"Validation error in assessment creation: {e}")
                messages.error(request, "Please correct the errors below.")
            except Exception as e:
                logger.error(f"Unexpected error in assessment creation: {e}")
                assessment_form.add_error(None, "An unexpected error occurred. Please try again.")
                messages.error(request, "An unexpected error occurred. Please try again.")
        
        # Form has errors - return for both AJAX and regular requests
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            errors = {}
            for field, error_list in assessment_form.errors.items():
                if field == '__all__':
                    errors['general'] = error_list
                else:
                    errors[field] = error_list
            
            return JsonResponse({
                "success": False, 
                "errors": errors,
                "msg": "Please correct the errors and try again."
            })
        
        # For regular form submissions, show errors in template
        messages.error(request, "Please correct the errors below.")
        
    else:
        # GET request - create new form
        assessment_form = GMAssessmentForm()

    context = {
        "form": assessment_form,
        "patient": patient,
        "file": video_file,  # For backward compatibility
        "video": video_file,
        "page_title": f"Create Assessment - {patient.baby_name}",
        "breadcrumbs": [
            {"name": "Dashboard", "url": reverse("home")},
            {"name": "Patient", "url": reverse("view-patient", args=[patient.id])},
            {"name": "Video", "url": reverse("video:view", args=[video_file.id])},
            {"name": "New Assessment", "url": None},
        ],
    }
    
    return render(request, "assessment/add.html", context)


@login_required(login_url="user-login")
def assessment_view(request, pk):
    """Enhanced assessment view with error handling and logging"""
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get assessment with related objects to reduce database queries
        assessment = GMAssessment.objects.select_related(
            'patient', 'video_file', 'added_by', 'last_edit_by'
        ).prefetch_related('diagnosis').get(id=pk)
        
        # Check for existing bookmark
        bookmark = Bookmark.objects.filter(
            bookmark_type="GMA",
            object_id=assessment.id
        ).first()
        
        context = {
            'assessment': assessment,
            'bookmark': bookmark,
            'page_title': f"Assessment - {assessment.patient.baby_name}",
        }
        
        logger.info(f"User {request.user.username} viewed assessment {assessment.id} for patient {assessment.patient.baby_name}")
        
        return render(request, "assessment/view.html", context)
        
    except GMAssessment.DoesNotExist:
        logger.warning(f"User {request.user.username} attempted to view non-existent assessment {pk}")
        messages.error(request, 'Assessment not found.')
        return redirect('assessment-manager')
        
    except Exception as e:
        logger.error(f"Error viewing assessment {pk}: {str(e)}")
        messages.error(request, 'An error occurred while loading the assessment.')
        return redirect('assessment-manager')


@login_required(login_url="user-login")
def assessment_view_by_fileid(request, file_id):
    """Enhanced assessment view by file ID with error handling"""
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get assessment by video file ID with related objects
        assessment = GMAssessment.objects.select_related(
            'patient', 'video_file', 'added_by', 'last_edit_by'
        ).prefetch_related('diagnosis').get(video_file=file_id)
        
        # Check for existing bookmark
        bookmark = Bookmark.objects.filter(
            bookmark_type="GMA",
            object_id=assessment.id
        ).first()
        
        context = {
            'assessment': assessment,
            'bookmark': bookmark,
            'page_title': f"Assessment - {assessment.patient.baby_name}",
        }
        
        logger.info(f"User {request.user.username} viewed assessment by file ID {file_id} for patient {assessment.patient.baby_name}")
        
        return render(request, "assessment/view.html", context)
        
    except GMAssessment.DoesNotExist:
        logger.warning(f"User {request.user.username} attempted to view assessment for non-existent file {file_id}")
        messages.error(request, 'Assessment not found for this video file.')
        return redirect('video:view', file_id)
        
    except Exception as e:
        logger.error(f"Error viewing assessment by file ID {file_id}: {str(e)}")
        messages.error(request, 'An error occurred while loading the assessment.')
        return redirect('home')


@login_required(login_url="user-login")
def assessment_edit(request, pk):
    try:
        assmnt = GMAssessment.objects.select_related('patient', 'added_by', 'last_edit_by').get(id=pk)
    except GMAssessment.DoesNotExist:
        messages.error(request, "Assessment not found.")
        return redirect("assessment-manager")
    assessment_form = GMAssessmentForm(instance=assmnt)
    if request.method == "POST":
        assessment_form_data = GMAssessmentForm(request.POST, instance=assmnt)
        if assessment_form_data.is_valid():
            assessment_form_data.save()
            messages.success(request, "Assessment details are updated succesfully...")
            return redirect("assessment-view", pk=assmnt.id)
        else:
            messages.success(request, assessment_form_data.errors)
            return render(
                request,
                "assessment/edit.html",
                {"form": assessment_form_data, "assmnt": assmnt},
            )
    return render(
        request, "assessment/edit.html", {"form": assessment_form, "assmnt": assmnt}
    )


@login_required(login_url="user-login")
def assessment_edit_by_fileid(request, pk):
    assmnt = GMAssessment.objects.get(video_file=pk)
    assessment_form = GMAssessmentForm(instance=assmnt)
    if request.method == "POST":
        assessment_form_data = GMAssessmentForm(request.POST, instance=assmnt)
        if assessment_form_data.is_valid():
            assessment_form_data.save()
            messages.success(request, "Assessment details are updated succesfully...")
            return redirect("assessment-view", pk=assmnt.id)
        else:
            messages.success(request, assessment_form_data.errors)
            return render(
                request,
                "assessment/edit.html",
                {"form": assessment_form_data, "assmnt": assmnt},
            )
    return render(
        request, "assessment/edit.html", {"form": assessment_form, "assmnt": assmnt}
    )


@login_required(login_url="user-login")
def assessment_delete_start(request, pk):
    """DEPRECATED: Use unified delete modal instead"""
    assemnt = GMAssessment.objects.get(id=pk)
    patient = Patient.objects.get(id=assemnt.patient.id)
    return render(
        request,
        "assessment/delete-confirm.html",
        {"assemnt": assemnt, "patient": patient},
    )


@login_required(login_url="user-login")
@require_http_methods(["DELETE"])
def assessment_delete(request, pk):
    """
    Unified GMA assessment deletion endpoint with password verification
    Part of refactor-delete-confirmation change

    Accepts: DELETE method with JSON payload {password: str}
    Returns: JSON {success: bool, message: str, redirect_url: str}
    """
    from ndas.custom_codes.delete_helpers import (
        has_delete_permission,
        validate_can_delete,
        get_entity_display_name,
        get_redirect_url
    )

    try:
        # 1. Retrieve assessment
        assessment = get_object_or_404(GMAssessment, id=pk)
        patient = assessment.patient

        # 2. Check permissions
        if not has_delete_permission(request.user, assessment):
            logger.warning(
                f"Unauthorized deletion attempt: user={request.user.username}, "
                f"entity=GMAssessment, id={pk}"
            )
            return JsonResponse({
                "success": False,
                "error": "Permission denied",
                "message": "You do not have permission to delete this assessment."
            }, status=403)

        # 3. Verify password
        try:
            data = json.loads(request.body)
            password = data.get('password', '')
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "error": "Invalid request",
                "message": "Invalid request format."
            }, status=400)

        if not password:
            return JsonResponse({
                "success": False,
                "error": "Password required",
                "message": "Password is required to confirm deletion."
            }, status=400)

        if not request.user.check_password(password):
            logger.warning(
                f"Invalid password for deletion: user={request.user.username}, "
                f"entity=GMAssessment, id={pk}"
            )
            return JsonResponse({
                "success": False,
                "error": "Invalid password",
                "message": "Incorrect password. Please try again."
            }, status=401)

        # 4. Check business rules
        validation_result = validate_can_delete(assessment)
        if not validation_result['can_delete']:
            return JsonResponse({
                "success": False,
                "error": "Cannot delete",
                "message": validation_result['reason']
            }, status=400)

        # 5. Store info for logging and response
        assessment_name = get_entity_display_name(assessment)

        # 6. Perform deletion
        assessment.delete()

        # 7. Audit log
        logger.info(
            f"Deletion successful: user={request.user.username}, "
            f"entity=GMAssessment, name={assessment_name}, id={pk}, "
            f"patient={patient.baby_name}"
        )

        # 8. Return success
        return JsonResponse({
            "success": True,
            "message": f"GMA Assessment has been deleted successfully.",
            "redirect_url": reverse("view-patient", kwargs={'pk': patient.id})
        })

    except Exception as e:
        logger.error(
            f"Deletion error: user={request.user.username}, "
            f"entity=GMAssessment, id={pk}, error={str(e)}"
        )
        return JsonResponse({
            "success": False,
            "error": "Server error",
            "message": f"An error occurred during deletion: {str(e)}"
        }, status=500)


@login_required(login_url="user-login")
def assessment_manager(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Filter assessments based on search query
    if search_query:
        assessment_list = GMAssessment.objects.filter(
            Q(patient__baby_name__icontains=search_query) |
            Q(patient__mother_name__icontains=search_query) |
            Q(patient__bht__icontains=search_query) |
            Q(patient__nnc_no__icontains=search_query)
        ).order_by("-id")
    else:
        assessment_list = GMAssessment.objects.all().order_by("-id")

    paginator = Paginator(assessment_list, 10)
    page_number = request.GET.get("page")
    paginated_assmnt_list = paginator.get_page(page_number)

    context = {
        "assessment_page_obj": paginated_assmnt_list,
        "search_query": search_query,
    }

    return render(request, "assessment/manager.html", context)


@login_required(login_url="user-login")
def assessment_manager_recent(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Get assessments from last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)
    assessment_list = GMAssessment.objects.filter(created_at__gte=thirty_days_ago)

    # Apply search filter if provided
    if search_query:
        assessment_list = assessment_list.filter(
            Q(patient__baby_name__icontains=search_query) |
            Q(patient__mother_name__icontains=search_query) |
            Q(patient__bht__icontains=search_query) |
            Q(patient__nnc_no__icontains=search_query)
        )

    assessment_list = assessment_list.order_by("-id")
    paginator = Paginator(assessment_list, 10)
    page_number = request.GET.get("page")
    paginated_assmnt_list = paginator.get_page(page_number)

    context = {
        "assessment_page_obj": paginated_assmnt_list,
        "type": "RECENT",
        "search_query": search_query,
    }

    return render(request, "assessment/manager.html", context)


@login_required(login_url="user-login")
def assessment_manager_normal(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Get assessments with normal diagnosis
    assessment_list = GMAssessment.objects.filter(diagnosis_conclusion='NORMAL')

    # Apply search filter if provided
    if search_query:
        assessment_list = assessment_list.filter(
            Q(patient__baby_name__icontains=search_query) |
            Q(patient__mother_name__icontains=search_query) |
            Q(patient__bht__icontains=search_query) |
            Q(patient__nnc_no__icontains=search_query)
        )

    assessment_list = assessment_list.order_by("-id")
    paginator = Paginator(assessment_list, 10)
    page_number = request.GET.get("page")
    paginated_assmnt_list = paginator.get_page(page_number)

    context = {
        "assessment_page_obj": paginated_assmnt_list,
        "type": "NORMAL",
        "search_query": search_query,
    }

    return render(request, "assessment/manager.html", context)


@login_required(login_url="user-login")
def assessment_manager_abnormal(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Get assessments with abnormal diagnosis
    assessment_list = GMAssessment.objects.filter(diagnosis_conclusion='ABNORMAL')

    # Apply search filter if provided
    if search_query:
        assessment_list = assessment_list.filter(
            Q(patient__baby_name__icontains=search_query) |
            Q(patient__mother_name__icontains=search_query) |
            Q(patient__bht__icontains=search_query) |
            Q(patient__nnc_no__icontains=search_query)
        )

    assessment_list = assessment_list.order_by("-id")
    paginator = Paginator(assessment_list, 10)
    page_number = request.GET.get("page")
    paginated_assmnt_list = paginator.get_page(page_number)

    context = {
        "assessment_page_obj": paginated_assmnt_list,
        "type": "ABNORMAL",
        "search_query": search_query,
    }

    return render(request, "assessment/manager.html", context)


@login_required(login_url="user-login")
def assessment_manager_informed(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Get assessments where parent is informed
    assessment_list = GMAssessment.objects.filter(parent_informed=True)

    # Apply search filter if provided
    if search_query:
        assessment_list = assessment_list.filter(
            Q(patient__baby_name__icontains=search_query) |
            Q(patient__mother_name__icontains=search_query) |
            Q(patient__bht__icontains=search_query) |
            Q(patient__nnc_no__icontains=search_query)
        )

    assessment_list = assessment_list.order_by("-id")
    paginator = Paginator(assessment_list, 10)
    page_number = request.GET.get("page")
    paginated_assmnt_list = paginator.get_page(page_number)

    context = {
        "assessment_page_obj": paginated_assmnt_list,
        "type": "INFORMED",
        "search_query": search_query,
    }

    return render(request, "assessment/manager.html", context)


@login_required(login_url="user-login")
def assessment_manager_not_informed(request):
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Get assessments where parent is not informed
    assessment_list = GMAssessment.objects.filter(parent_informed=False)

    # Apply search filter if provided
    if search_query:
        assessment_list = assessment_list.filter(
            Q(patient__baby_name__icontains=search_query) |
            Q(patient__mother_name__icontains=search_query) |
            Q(patient__bht__icontains=search_query) |
            Q(patient__nnc_no__icontains=search_query)
        )

    assessment_list = assessment_list.order_by("-id")
    paginator = Paginator(assessment_list, 10)
    page_number = request.GET.get("page")
    paginated_assmnt_list = paginator.get_page(page_number)

    context = {
        "assessment_page_obj": paginated_assmnt_list,
        "type": "NOT_INFORMED",
        "search_query": search_query,
    }

    return render(request, "assessment/manager.html", context)


@login_required(login_url="user-login")
def assessment_manager_by_patients(request, pk):
    patient = Patient.objects.get(id=pk)
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Filter assessments based on search query
    assessment_list = GMAssessment.objects.filter(patient=patient)
    if search_query:
        assessment_list = assessment_list.filter(
            Q(patient__baby_name__icontains=search_query) |
            Q(patient__mother_name__icontains=search_query) |
            Q(patient__bht__icontains=search_query) |
            Q(patient__nnc_no__icontains=search_query)
        )

    assessment_list = assessment_list.order_by("-id")
    paginator = Paginator(assessment_list, 10)
    page_number = request.GET.get("page")
    paginated_assmnt_list = paginator.get_page(page_number)

    context = {
        "patient": patient,
        "assessment_page_obj": paginated_assmnt_list,
        "search_query": search_query,
    }

    return render(request, "assessment/manager.html", context)


@login_required(login_url="user-login")
def help_home(request):
    articles = Help.objects.filter(is_active=True).order_by("display_order", "title")
    return render(request, "help/home.html", {"articles": articles})


@login_required(login_url="user-login")
def help_article(request, pk):
    try:
        article = Help.objects.get(id=pk)
    except Help.DoesNotExist:
        messages.error(request, "Help article not found.")
        return redirect("help-home")

    articles = Help.objects.filter(is_active=True).order_by("display_order", "title")
    return render(
        request, "help/article.html", {"article": article, "articles": articles}
    )


@login_required(login_url="user-login")
def bookmark_manager(request):
    try:
        # Get all bookmarks
        var_bookmarks_list = Bookmark.objects.select_related('owner', 'last_edit_by').all().order_by("-id")
        
        # Search and filter functionality
        search_query = request.GET.get('search', '').strip()
        search_title = request.GET.get('search_title', '').strip()  # Keep for backward compatibility
        bookmark_type = request.GET.get('bookmark_type', '')
        owner = request.GET.get('owner', '').strip()
        date_range = request.GET.get('date_range', '')

        # Use search_query if provided, otherwise fall back to search_title
        search_term = search_query or search_title

        # Apply search filters
        if search_term:
            var_bookmarks_list = var_bookmarks_list.filter(
                Q(title__icontains=search_term) |
                Q(description__icontains=search_term)
            )
        
        if bookmark_type:
            var_bookmarks_list = var_bookmarks_list.filter(
                bookmark_type=bookmark_type
            )
        
        if owner:
            var_bookmarks_list = var_bookmarks_list.filter(
                owner__username__icontains=owner
            )
        
        # Apply date range filters
        if date_range:
            now = timezone.now()
            if date_range == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                var_bookmarks_list = var_bookmarks_list.filter(created_at__gte=start_date)
            elif date_range == 'week':
                start_date = now - timedelta(days=7)
                var_bookmarks_list = var_bookmarks_list.filter(created_at__gte=start_date)
            elif date_range == 'month':
                start_date = now - timedelta(days=30)
                var_bookmarks_list = var_bookmarks_list.filter(created_at__gte=start_date)
            elif date_range == 'year':
                start_date = now - timedelta(days=365)
                var_bookmarks_list = var_bookmarks_list.filter(created_at__gte=start_date)
        
        # Calculate statistics
        bookmark_stats = {
            'total': var_bookmarks_list.count(),
            'patient': var_bookmarks_list.filter(bookmark_type='Patient').count(),
            'video': var_bookmarks_list.filter(bookmark_type='Video').count(),
            'assessment': var_bookmarks_list.filter(
                bookmark_type__in=['GMA', 'HINE', 'DA', 'CDICR']
            ).count(),
        }
        
        # Pagination
        paginator = Paginator(var_bookmarks_list, 15)
        page_number = request.GET.get("page")
        bookmark_page_obj = paginator.get_page(page_number)
        
        context = {
            "bookmark_page_obj": bookmark_page_obj,
            "bookmark_stats": bookmark_stats,
            "search_query": search_term,
        }
        
        return render(request, "bookmark/manager.html", context)
        
    except Exception as e:
        messages.error(request, f"Error loading bookmark records: {str(e)}")
        return render(request, "bookmark/manager.html", {
            "bookmark_page_obj": None,
            "bookmark_stats": {'total': 0, 'patient': 0, 'video': 0, 'assessment': 0},
        })


@login_required(login_url="user-login")
def bookmark_add(request, item_id, bookmark_type):
    # Validate bookmark type
    valid_types = [choice[0] for choice in BOOKMARK_TYPE]
    if bookmark_type not in valid_types:
        messages.error(request, "Invalid bookmark type.")
        return redirect("manage-patients")
    
    bookmark_form = BookmarkForm()

    if request.method == "POST":
        bookmark_form_data = BookmarkForm(request.POST)
        if bookmark_form_data.is_valid():
            try:
                title = bookmark_form_data.cleaned_data["title"]
                description = bookmark_form_data.cleaned_data["description"]

                # Check if bookmark already exists for this user
                existing_bookmark = Bookmark.objects.filter(
                    bookmark_type=bookmark_type,
                    object_id=item_id,
                    owner=request.user
                ).first()

                if not existing_bookmark:
                    prep_bm = Bookmark.objects.create(
                        title=title,
                        bookmark_type=bookmark_type,
                        object_id=item_id,
                        description=description,
                        owner=request.user,
                        added_by=request.user,
                    )

                    messages.success(request, "New bookmark created successfully.")
                    return redirect("bookmark-view", pk=prep_bm.id)
                else:
                    messages.warning(
                        request,
                        "You have already bookmarked this item. Please remove the existing bookmark before creating a new one.",
                    )
                    return render(
                        request,
                        "bookmark/add.html",
                        {
                            "form": bookmark_form_data,
                            "item_id": item_id,
                            "bookmark_type": bookmark_type,
                        },
                    )
            except Exception as e:
                messages.error(request, f"Error creating bookmark: {str(e)}")
                return render(
                    request,
                    "bookmark/add.html",
                    {
                        "form": bookmark_form_data,
                        "item_id": item_id,
                        "bookmark_type": bookmark_type,
                    },
                )
        else:
            # Format errors for better user experience
            error_messages = []
            for field, errors in bookmark_form_data.errors.items():
                field_name = bookmark_form_data.fields[field].label or field.replace('_', ' ').title()
                for error in errors:
                    error_messages.append(f"{field_name}: {error}")
            
            if error_messages:
                messages.error(request, "Please correct the following errors: " + "; ".join(error_messages))
            
            return render(
                request,
                "bookmark/add.html",
                {
                    "form": bookmark_form_data,
                    "item_id": item_id,
                    "bookmark_type": bookmark_type,
                },
            )
    else:
        return render(
            request,
            "bookmark/add.html",
            {"form": bookmark_form, "item_id": item_id, "bookmark_type": bookmark_type},
        )


@login_required(login_url="user-login")
def bookmark_view(request, pk):
    bookmark = Bookmark.objects.get(id=pk)
    return render(request, "bookmark/view.html", {"bookmark": bookmark})


@login_required(login_url="user-login")
@require_http_methods(["DELETE"])
def bookmark_delete(request, pk):
    """
    Unified bookmark deletion endpoint with password verification
    Part of refactor-delete-confirmation change

    Accepts: DELETE method with JSON payload {password: str}
    Returns: JSON {success: bool, message: str, redirect_url: str}
    """
    from ndas.custom_codes.delete_helpers import (
        has_delete_permission,
        validate_can_delete,
        get_entity_display_name,
        get_redirect_url
    )

    try:
        # 1. Retrieve bookmark
        bookmark = get_object_or_404(Bookmark, id=pk)

        # 2. Check permissions
        if not has_delete_permission(request.user, bookmark):
            logger.warning(
                f"Unauthorized deletion attempt: user={request.user.username}, "
                f"entity=Bookmark, id={pk}"
            )
            return JsonResponse({
                "success": False,
                "error": "Permission denied",
                "message": "You do not have permission to delete this bookmark."
            }, status=403)

        # 3. Verify password
        try:
            data = json.loads(request.body)
            password = data.get('password', '')
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "error": "Invalid request",
                "message": "Invalid request format."
            }, status=400)

        if not password:
            return JsonResponse({
                "success": False,
                "error": "Password required",
                "message": "Password is required to confirm deletion."
            }, status=400)

        if not request.user.check_password(password):
            logger.warning(
                f"Invalid password for deletion: user={request.user.username}, "
                f"entity=Bookmark, id={pk}"
            )
            return JsonResponse({
                "success": False,
                "error": "Invalid password",
                "message": "Incorrect password. Please try again."
            }, status=401)

        # 4. Check business rules
        validation_result = validate_can_delete(bookmark)
        if not validation_result['can_delete']:
            return JsonResponse({
                "success": False,
                "error": "Cannot delete",
                "message": validation_result['reason']
            }, status=400)

        # 5. Store info for logging and response
        bookmark_name = get_entity_display_name(bookmark)

        # 6. Perform deletion
        bookmark.delete()

        # 7. Audit log
        logger.info(
            f"Deletion successful: user={request.user.username}, "
            f"entity=Bookmark, name={bookmark_name}, id={pk}"
        )

        # 8. Return success
        return JsonResponse({
            "success": True,
            "message": f"Bookmark has been deleted successfully.",
            "redirect_url": reverse("bookmark-manager-user", kwargs={'username': request.user.username})
        })

    except Exception as e:
        logger.error(
            f"Deletion error: user={request.user.username}, "
            f"entity=Bookmark, id={pk}, error={str(e)}"
        )
        return JsonResponse({
            "success": False,
            "error": "Server error",
            "message": f"An error occurred during deletion: {str(e)}"
        }, status=500)


@login_required(login_url="user-login")
def bookmark_manager_user(request, username):
    user = CustomUser.objects.get(username=username)
    var_patients_list = Bookmark.objects.filter(owner=user).order_by("-id")
    paginator = Paginator(var_patients_list, 10)
    page_number = request.GET.get("page")
    bookmark_list = paginator.get_page(page_number)
    return render(
        request, "bookmark/manager.html", {"bookmark_page_obj": bookmark_list}
    )


@login_required(login_url="user-login")
def bookmark_edit(request, pk):
    try:
        selected_bm = Bookmark.objects.select_related('owner', 'added_by', 'last_edit_by').get(id=pk)
    except Bookmark.DoesNotExist:
        messages.error(request, "Bookmark not found.")
        return redirect("bookmark-manager-user", request.user.username)
    bm_form = BookmarkForm(instance=selected_bm)
    if request.method == "POST":
        bm_form_data = BookmarkForm(request.POST, instance=selected_bm)
        if bm_form_data.is_valid():
            selected_bm = bm_form_data.save(commit=False)
            selected_bm.last_edit_by = request.user
            selected_bm.save()
            messages.success(request, "Bookmark details are updated succesfully...")
            return redirect("bookmark-view", pk=selected_bm.id)
        else:
            messages.success(request, bm_form_data.errors)
            return render(
                request,
                "bookmark/edit.html",
                {"form": bm_form_data, "bookmark": selected_bm},
            )
    return render(
        request, "bookmark/edit.html", {"form": bm_form, "bookmark": selected_bm}
    )


# functionf for attachment operations


@login_required(login_url="user-login")
def attachment_manager(request):
    """Enhanced attachment manager with filtering, search, and pagination following Django best practices"""
    # Get search and filter parameters with proper defaults
    search_query = request.GET.get("search", "").strip()
    type_filter = request.GET.get("type", "")
    uploader_filter = request.GET.get("uploader", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    bookmarked_filter = request.GET.get("bookmarked_only", "")
    page_number = request.GET.get("page", 1)

    # Base queryset with optimized related data loading
    queryset = (
        Attachment.objects.select_related("patient", "added_by", "last_edit_by")
        .order_by("-created_at")
    )

    # Apply search filter using Q objects for complex queries
    if search_query:
        queryset = queryset.filter(
            Q(title__icontains=search_query)
            | Q(patient__baby_name__icontains=search_query)
            | Q(patient__disk_no__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(patient__bht__icontains=search_query)
        )

    # Apply type filter
    if type_filter and type_filter != "all":
        if type_filter == "bookmarked":
            # Special case for bookmarked filter
            bookmarked_attachment_ids = Bookmark.objects.filter(
                bookmark_type="Attachment"
            ).values_list('object_id', flat=True)
            queryset = queryset.filter(id__in=bookmarked_attachment_ids)
        else:
            queryset = queryset.filter(attachment_type=type_filter)

    # Apply uploader filter with proper error handling
    if uploader_filter:
        try:
            uploader_id = int(uploader_filter)
            queryset = queryset.filter(added_by_id=uploader_id)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid uploader filter value: {uploader_filter}")
            messages.warning(request, "Invalid uploader filter. Showing all uploaders.")

    # Apply date range filters with proper error handling
    if date_from:
        try:
            from datetime import datetime
            date_from_parsed = datetime.strptime(date_from, "%Y-%m-%d").date()
            queryset = queryset.filter(created_at__date__gte=date_from_parsed)
        except ValueError as e:
            logger.warning(f"Invalid date_from format: {date_from}")
            messages.warning(
                request, "Invalid 'from' date format. Please use YYYY-MM-DD format."
            )

    if date_to:
        try:
            from datetime import datetime
            date_to_parsed = datetime.strptime(date_to, "%Y-%m-%d").date()
            queryset = queryset.filter(created_at__date__lte=date_to_parsed)
        except ValueError as e:
            logger.warning(f"Invalid date_to format: {date_to}")
            messages.warning(
                request, "Invalid 'to' date format. Please use YYYY-MM-DD format."
            )

    # Apply bookmarked filter
    if bookmarked_filter:
        bookmarked_attachment_ids = Bookmark.objects.filter(
            bookmark_type="Attachment"
        ).values_list('object_id', flat=True)
        queryset = queryset.filter(id__in=bookmarked_attachment_ids)

    # Get total count before pagination
    total_count = queryset.count()

    # Pagination with proper error handling
    paginator = Paginator(queryset, 25)  # Show 25 attachments per page
    try:
        page_obj = paginator.get_page(page_number)
    except Exception as e:
        logger.error(f"Pagination error: {str(e)}")
        page_obj = paginator.get_page(1)

    # Get unique uploaders for filter dropdown (users who have uploaded attachments)
    uploaders = (
        CustomUser.objects.filter(attachment_added__isnull=False)
        .distinct()
        .only("id", "username", "first_name", "last_name")
        .order_by("first_name", "last_name")
    )

    # Build context dictionary
    context = {
        "attachment_page_obj": page_obj,  # Keep for template compatibility
        "attachments": page_obj,
        "search_query": search_query,
        "type": type_filter,
        "uploader_filter": uploader_filter,
        "date_from": date_from,
        "date_to": date_to,
        "bookmarked_filter": bookmarked_filter,
        "uploaders": uploaders,
        "total_count": total_count,
        "page_title": "Attachment Manager",
        "breadcrumbs": [
            {"name": "Dashboard", "url": reverse("home")},
            {"name": "Attachment Manager", "url": None},
        ],
    }

    return render(request, "attachment/manager.html", context)


@login_required(login_url="user-login")
def attachment_manager_patient(request, pid):
    """Enhanced patient-specific attachment manager with filtering and search"""
    patient = Patient.objects.get(pk=pid)

    # Get search and filter parameters with proper defaults
    search_query = request.GET.get("search", "").strip()
    type_filter = request.GET.get("type", "")
    uploader_filter = request.GET.get("uploader", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    bookmarked_filter = request.GET.get("bookmarked_only", "")
    page_number = request.GET.get("page", 1)

    # Base queryset with optimized related data loading
    queryset = (
        Attachment.objects.filter(patient=pid)
        .select_related("patient", "added_by", "last_edit_by")
        .order_by("-created_at")
    )

    # Apply search filter using Q objects for complex queries
    if search_query:
        queryset = queryset.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    # Apply type filter
    if type_filter and type_filter != "all":
        if type_filter == "bookmarked":
            # Special case for bookmarked filter
            bookmarked_attachment_ids = Bookmark.objects.filter(
                bookmark_type="Attachment"
            ).values_list('object_id', flat=True)
            queryset = queryset.filter(id__in=bookmarked_attachment_ids)
        else:
            queryset = queryset.filter(attachment_type=type_filter)

    # Apply uploader filter with proper error handling
    if uploader_filter:
        try:
            uploader_id = int(uploader_filter)
            queryset = queryset.filter(added_by_id=uploader_id)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid uploader filter value: {uploader_filter}")
            messages.warning(request, "Invalid uploader filter. Showing all uploaders.")

    # Apply date range filters with proper error handling
    if date_from:
        try:
            from datetime import datetime
            date_from_parsed = datetime.strptime(date_from, "%Y-%m-%d").date()
            queryset = queryset.filter(created_at__date__gte=date_from_parsed)
        except ValueError as e:
            logger.warning(f"Invalid date_from format: {date_from}")
            messages.warning(
                request, "Invalid 'from' date format. Please use YYYY-MM-DD format."
            )

    if date_to:
        try:
            from datetime import datetime
            date_to_parsed = datetime.strptime(date_to, "%Y-%m-%d").date()
            queryset = queryset.filter(created_at__date__lte=date_to_parsed)
        except ValueError as e:
            logger.warning(f"Invalid date_to format: {date_to}")
            messages.warning(
                request, "Invalid 'to' date format. Please use YYYY-MM-DD format."
            )

    # Apply bookmarked filter
    if bookmarked_filter:
        bookmarked_attachment_ids = Bookmark.objects.filter(
            bookmark_type="Attachment"
        ).values_list('object_id', flat=True)
        queryset = queryset.filter(id__in=bookmarked_attachment_ids)

    # Get total count before pagination
    total_count = queryset.count()

    # Pagination with proper error handling
    paginator = Paginator(queryset, 25)  # Show 25 attachments per page
    try:
        page_obj = paginator.get_page(page_number)
    except Exception as e:
        logger.error(f"Pagination error: {str(e)}")
        page_obj = paginator.get_page(1)

    # Get unique uploaders for filter dropdown (users who have uploaded attachments for this patient)
    uploaders = (
        CustomUser.objects.filter(attachment_added__patient=pid)
        .distinct()
        .only("id", "username", "first_name", "last_name")
        .order_by("first_name", "last_name")
    )

    # Build context dictionary
    context = {
        "attachment_page_obj": page_obj,  # Keep for template compatibility
        "attachments": page_obj,
        "patient": patient,
        "search_query": search_query,
        "type": type_filter,
        "uploader_filter": uploader_filter,
        "date_from": date_from,
        "date_to": date_to,
        "bookmarked_filter": bookmarked_filter,
        "uploaders": uploaders,
        "total_count": total_count,
        "page_title": f"Attachments for {patient.baby_name}",
        "breadcrumbs": [
            {"name": "Dashboard", "url": reverse("home")},
            {"name": "Patients", "url": reverse("view-patient", args=[pid])},
            {"name": f"Attachments for {patient.baby_name}", "url": None},
        ],
    }

    return render(request, "attachment/manager.html", context)


@login_required(login_url="user-login")
def attachment_add(request, pid):
    """
    Handle attachment upload for a patient.
    Updated to support new Attachment model fields and proper error handling.
    """
    try:
        selected_patient = Patient.objects.get(pk=pid)
    except Patient.DoesNotExist:
        if request.method == "POST":
            return JsonResponse(
                {"success": False, "msg": "Patient not found."},
                status=404
            )
        messages.error(request, "Patient not found.")
        return redirect("manage-patients")

    attachment_form = AttachmentkForm()

    if request.method == "POST":
        # Use .get() to safely access POST/FILES data
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()

        # Validate required fields
        if not title:
            return JsonResponse(
                {"success": False, "msg": "Title is required."},
                status=400
            )

        if "attachment" not in request.FILES:
            return JsonResponse(
                {"success": False, "msg": "No file was uploaded."},
                status=400
            )

        attachment = request.FILES["attachment"]

        # Validate file size
        if not validateAttachmentSize(attachment):
            return JsonResponse(
                {"success": False, "msg": "File size exceeds the maximum allowed limit. Images: 10MB, Videos: 2GB, Documents: 100MB."},
                status=400
            )

        # Validate file type
        if not validateAttachmentType(attachment):
            return JsonResponse(
                {
                    "success": False,
                    "msg": "Invalid file type. Allowed types: Images (jpg, jpeg, png, gif, bmp, webp), Videos (mp4, mov, avi, mkv, webm), Documents (pdf, doc, docx, txt).",
                },
                status=400
            )

        try:
            # Create attachment with new model fields
            temp_file = Attachment(
                patient=selected_patient,
                title=title,
                attachment=attachment,
                attachment_type=getAttachmentType(attachment),
                description=description,
                original_filename=attachment.name,
                file_size=attachment.size,
                # User tracking handled by middleware
            )

            temp_file.save()

            return JsonResponse(
                {
                    "success": True,
                    "msg": "File uploaded successfully!",
                    "p_id": selected_patient.id,
                    "f_id": temp_file.id,
                }
            )

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error saving attachment: {str(e)}", exc_info=True)

            return JsonResponse(
                {
                    "success": False,
                    "msg": f"Error saving file: {str(e)}",
                },
                status=500
            )
    else:
        return render(
            request,
            "attachment/add.html",
            {"patient": selected_patient, "attachment_form": attachment_form},
        )


@login_required(login_url="user-login")
def attachment_view(request, pk):
    try:
        sa = Attachment.objects.select_related('patient', 'added_by', 'last_edit_by').get(pk=pk)
    except Attachment.DoesNotExist:
        messages.error(request, "Attachment not found.")
        return redirect("manage-patients")
    return render(
        request, "attachment/view.html", {"patient": sa.patient, "attachment": sa}
    )


@login_required(login_url="user-login")
def attachment_edit(request, pk):
    try:
        sa = Attachment.objects.select_related('patient', 'added_by', 'last_edit_by').get(pk=pk)
    except Attachment.DoesNotExist:
        messages.error(request, "Attachment not found.")
        return redirect("manage-patients")

    a_form = AttachmentkForm(instance=sa)

    if request.method == "POST":
        bm_form_data = AttachmentkForm(request.POST, request.FILES, instance=sa)

        if bm_form_data.is_valid():
            attachment = bm_form_data.cleaned_data["attachment"]
            if validateAttachmentSize(attachment):
                if validateAttachmentType(attachment):
                    bm_form_data.save()

                    sa.attachment_type = getAttachmentType(attachment)

                    sa.last_edit_by = request.user
                    sa.last_edit_by = request.user
                    sa.save(update_fields=["attachment_type", "last_edit_by"])
                    sa.save()

                    messages.success(
                        request, "Attachment details are updated succesfully..."
                    )
                    return redirect("attachment-view", pk=sa.id)
                else:
                    messages.warning(
                        request,
                        "You cant upload files other dan videos(mp4, mov), image(jpg, jpeg), PDF...",
                    )
                    return render(
                        request,
                        "attachment/edit.html",
                        {"form": a_form, "attachment": sa},
                    )
            else:
                messages.warning(request, "You cant upload file size >100mb...")
                return render(
                    request, "attachment/edit.html", {"form": a_form, "attachment": sa}
                )
        else:
            messages.success(request, bm_form_data.errors)
            return render(
                request,
                "attachment/edit.html",
                {"form": bm_form_data, "attachment": sa},
            )
    else:
        return render(
            request, "attachment/edit.html", {"form": a_form, "attachment": sa}
        )


@login_required(login_url="user-login")
def attachment_delete_confirm(request, pk):
    """DEPRECATED: Use unified delete modal instead"""
    attachment = Attachment.objects.get(id=pk)
    patient = attachment.patient
    return render(
        request,
        "attachment/delete-confirm.html",
        {"attachment": attachment, "patient": patient},
    )


@login_required(login_url="user-login")
@require_http_methods(["DELETE"])
def attachment_delete(request, pk):
    """
    Unified attachment deletion endpoint with password verification
    Part of refactor-delete-confirmation change

    Accepts: DELETE method with JSON payload {password: str}
    Returns: JSON {success: bool, message: str, redirect_url: str}
    """
    from ndas.custom_codes.delete_helpers import (
        has_delete_permission,
        validate_can_delete,
        get_entity_display_name,
        get_redirect_url
    )

    try:
        # 1. Retrieve attachment
        attachment = get_object_or_404(Attachment, id=pk)
        patient = attachment.patient

        # 2. Check permissions
        if not has_delete_permission(request.user, attachment):
            logger.warning(
                f"Unauthorized deletion attempt: user={request.user.username}, "
                f"entity=Attachment, id={pk}"
            )
            return JsonResponse({
                "success": False,
                "error": "Permission denied",
                "message": "You do not have permission to delete this attachment."
            }, status=403)

        # 3. Verify password
        try:
            data = json.loads(request.body)
            password = data.get('password', '')
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "error": "Invalid request",
                "message": "Invalid request format."
            }, status=400)

        if not password:
            return JsonResponse({
                "success": False,
                "error": "Password required",
                "message": "Password is required to confirm deletion."
            }, status=400)

        if not request.user.check_password(password):
            logger.warning(
                f"Invalid password for deletion: user={request.user.username}, "
                f"entity=Attachment, id={pk}"
            )
            return JsonResponse({
                "success": False,
                "error": "Invalid password",
                "message": "Incorrect password. Please try again."
            }, status=401)

        # 4. Check business rules
        validation_result = validate_can_delete(attachment)
        if not validation_result['can_delete']:
            return JsonResponse({
                "success": False,
                "error": "Cannot delete",
                "message": validation_result['reason']
            }, status=400)

        # 5. Store info for logging and response
        attachment_name = get_entity_display_name(attachment)

        # 6. Delete file from storage
        if attachment.attachment:
            try:
                attachment.attachment.delete(save=False)
            except Exception as e:
                logger.warning(f"Failed to delete attachment file: {e}")

        # 7. Perform deletion
        attachment.delete()

        # 8. Audit log
        logger.info(
            f"Deletion successful: user={request.user.username}, "
            f"entity=Attachment, name={attachment_name}, id={pk}, "
            f"patient={patient.baby_name}"
        )

        # 9. Return success
        return JsonResponse({
            "success": True,
            "message": f"Attachment has been deleted successfully.",
            "redirect_url": reverse("view-patient", kwargs={'pk': patient.id})
        })

    except Exception as e:
        logger.error(
            f"Deletion error: user={request.user.username}, "
            f"entity=Attachment, id={pk}, error={str(e)}"
        )
        return JsonResponse({
            "success": False,
            "error": "Server error",
            "message": f"An error occurred during deletion: {str(e)}"
        }, status=500)




@login_required(login_url="user-login")
def cdic_assessment_add(request, pid):
    try:
        selected_patient = Patient.objects.get(pk=pid)
    except Patient.DoesNotExist:
        messages.error(request, "Patient not found.")
        return redirect("manage-patients")
    
    cdic_assemnt_form = CDICRecordForm()

    if request.method == "POST":
        cdic_assemnt_form_data = CDICRecordForm(request.POST)
        if cdic_assemnt_form_data.is_valid():
            try:
                cdic_record = cdic_assemnt_form_data.save(commit=False)
                cdic_record.patient = selected_patient
                cdic_record.added_by = request.user
                cdic_record.save()
                messages.success(request, "New CDIC record added successfully.")
                return redirect("cdic-assessment-view", cdic_record.id)
            except Exception as e:
                messages.error(request, f"Error saving CDIC record: {str(e)}")
                return render(
                    request,
                    "cdic_record/add.html",
                    {"patient": selected_patient, "cdic_assemnt_form": cdic_assemnt_form_data},
                )
        else:
            # Format errors for better user experience
            error_messages = []
            for field, errors in cdic_assemnt_form_data.errors.items():
                field_name = cdic_assemnt_form_data.fields[field].label or field.replace('_', ' ').title()
                for error in errors:
                    error_messages.append(f"{field_name}: {error}")
            
            if error_messages:
                messages.error(request, "Please correct the following errors: " + "; ".join(error_messages))
            
            return render(
                request,
                "cdic_record/add.html",
                {"patient": selected_patient, "cdic_assemnt_form": cdic_assemnt_form_data},
            )
    else:
        return render(
            request,
            "cdic_record/add.html",
            {"patient": selected_patient, "cdic_assemnt_form": cdic_assemnt_form},
        )


@login_required(login_url="user-login")
def cdic_assessment_edit(request, aid):
    try:
        srecord = CDICRecord.objects.select_related('patient', 'added_by', 'last_edit_by').get(id=aid)
        spt = srecord.patient
    except CDICRecord.DoesNotExist:
        messages.error(request, "CDIC record not found.")
        return redirect("cdic-assessment-manager")

    cdicr_form = CDICRecordForm(instance=srecord)

    if request.method == "POST":
        cdicr_form_data = CDICRecordForm(request.POST, instance=srecord)
        if cdicr_form_data.is_valid():
            cdicr = cdicr_form_data.save(commit=False)

            cdicr.last_edit_by = request.user
            cdicr.save()

            messages.success(request, "CDIC record updated succesfully...")
            return redirect("cdic-assessment-view", cdicr.id)
        else:
            messages.success(request, cdicr_form_data.errors)
            return render(
                request,
                "cdic_record/edit.html",
                {"cdic_assemnt_form": cdicr_form_data, "patient": spt},
            )
    return render(
        request,
        "cdic_record/edit.html",
        {"cdic_assemnt_form": cdicr_form, "cdic_record": srecord, "patient": spt},
    )


@login_required(login_url="user-login")
def cdic_assessment_view(request, cdic_id):
    try:
        selected_cdic_record = CDICRecord.objects.select_related('patient', 'added_by', 'last_edit_by').get(pk=cdic_id)
    except CDICRecord.DoesNotExist:
        messages.error(request, "CDIC record not found.")
        return redirect("cdic-assessment-manager")
    return render(
        request, "cdic_record/view.html", {"CDICRecord": selected_cdic_record}
    )


@login_required(login_url="user-login")
def cdic_assessment_manager(request):
    try:
        # Get all CDIC records
        var_cdic_list = CDICRecord.objects.select_related('patient', 'added_by', 'last_edit_by').all().order_by("-id")
        
        # Search and filter functionality
        search_patient = request.GET.get('search_patient', '').strip()
        date_range = request.GET.get('date_range', '')
        follow_up_status = request.GET.get('follow_up_status', '')
        created_by = request.GET.get('created_by', '').strip()
        
        # Apply search filters
        if search_patient:
            var_cdic_list = var_cdic_list.filter(
                patient__baby_name__icontains=search_patient
            )
        
        if created_by:
            var_cdic_list = var_cdic_list.filter(
                added_by__username__icontains=created_by
            )

        # Apply date range filters
        if date_range:
            now = timezone.now()
            if date_range == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                var_cdic_list = var_cdic_list.filter(assessment_date__gte=start_date)
            elif date_range == 'week':
                start_date = now - timedelta(days=7)
                var_cdic_list = var_cdic_list.filter(assessment_date__gte=start_date)
            elif date_range == 'month':
                start_date = now - timedelta(days=30)
                var_cdic_list = var_cdic_list.filter(assessment_date__gte=start_date)
            elif date_range == 'quarter':
                start_date = now - timedelta(days=90)
                var_cdic_list = var_cdic_list.filter(assessment_date__gte=start_date)
            elif date_range == 'year':
                start_date = now - timedelta(days=365)
                var_cdic_list = var_cdic_list.filter(assessment_date__gte=start_date)

        # Apply follow-up status filters
        if follow_up_status:
            today = date.today()

            if follow_up_status == 'pending':
                var_cdic_list = var_cdic_list.filter(
                    next_appointment_date__isnull=False,
                    next_appointment_date__gte=today
                )
            elif follow_up_status == 'completed':
                var_cdic_list = var_cdic_list.filter(
                    next_appointment_date__isnull=True
                )
            elif follow_up_status == 'overdue':
                var_cdic_list = var_cdic_list.filter(
                    next_appointment_date__isnull=False,
                    next_appointment_date__lt=today
                )

        # Calculate statistics
        today = date.today()

        cdic_stats = {
            'total': var_cdic_list.count(),
            'completed': var_cdic_list.filter(next_appointment_date__isnull=True).count(),
            'pending': var_cdic_list.filter(
                next_appointment_date__isnull=False,
                next_appointment_date__gte=today
            ).count(),
            'this_week': var_cdic_list.filter(
                assessment_date__gte=today - timedelta(days=7)
            ).count(),
        }
        
        # Pagination
        paginator = Paginator(var_cdic_list, 15)
        page_number = request.GET.get("page")
        cdic_record_list = paginator.get_page(page_number)
        
        context = {
            "cdic_record_list": cdic_record_list,
            "cdic_stats": cdic_stats,
            "patient": None,
        }
        
        return render(request, "cdic_record/manager.html", context)
        
    except Exception as e:
        messages.error(request, f"Error loading CDIC assessment records: {str(e)}")
        return render(request, "cdic_record/manager.html", {
            "cdic_record_list": None,
            "cdic_stats": {'total': 0, 'completed': 0, 'pending': 0, 'this_week': 0},
            "patient": None,
        })


@login_required(login_url="user-login")
def cdic_assessment_manager_by_patients(request, pid):
    try:
        # Get patient with error handling
        try:
            sp = Patient.objects.get(pk=pid)
        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")
            return redirect("manage-patients")
        
        # Get CDIC records for this patient
        var_cdic_list = CDICRecord.objects.select_related('patient', 'added_by', 'last_edit_by').filter(patient=sp.id).order_by("-id")
        
        # Search and filter functionality (same as general manager but for specific patient)
        date_range = request.GET.get('date_range', '')
        follow_up_status = request.GET.get('follow_up_status', '')
        created_by = request.GET.get('created_by', '').strip()
        
        # Apply filters
        if created_by:
            var_cdic_list = var_cdic_list.filter(
                added_by__username__icontains=created_by
            )

        if date_range:
            now = timezone.now()
            if date_range == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                var_cdic_list = var_cdic_list.filter(assessment_date__gte=start_date)
            elif date_range == 'week':
                start_date = now - timedelta(days=7)
                var_cdic_list = var_cdic_list.filter(assessment_date__gte=start_date)
            elif date_range == 'month':
                start_date = now - timedelta(days=30)
                var_cdic_list = var_cdic_list.filter(assessment_date__gte=start_date)
            elif date_range == 'quarter':
                start_date = now - timedelta(days=90)
                var_cdic_list = var_cdic_list.filter(assessment_date__gte=start_date)
            elif date_range == 'year':
                start_date = now - timedelta(days=365)
                var_cdic_list = var_cdic_list.filter(assessment_date__gte=start_date)

        if follow_up_status:
            today = date.today()
            
            if follow_up_status == 'pending':
                var_cdic_list = var_cdic_list.filter(
                    next_appointment_date__isnull=False,
                    next_appointment_date__gte=today
                )
            elif follow_up_status == 'completed':
                var_cdic_list = var_cdic_list.filter(
                    next_appointment_date__isnull=True
                )
            elif follow_up_status == 'overdue':
                var_cdic_list = var_cdic_list.filter(
                    next_appointment_date__isnull=False,
                    next_appointment_date__lt=today
                )

        # Calculate statistics for this patient
        today = date.today()

        cdic_stats = {
            'total': var_cdic_list.count(),
            'completed': var_cdic_list.filter(next_appointment_date__isnull=True).count(),
            'pending': var_cdic_list.filter(
                next_appointment_date__isnull=False,
                next_appointment_date__gte=today
            ).count(),
            'this_week': var_cdic_list.filter(
                assessment_date__gte=today - timedelta(days=7)
            ).count(),
        }
        
        # Pagination
        paginator = Paginator(var_cdic_list, 15)
        page_number = request.GET.get("page")
        cdic_record_list = paginator.get_page(page_number)
        
        context = {
            "patient": sp,
            "cdic_record_list": cdic_record_list,
            "cdic_stats": cdic_stats,
        }
        
        return render(request, "cdic_record/manager.html", context)
        
    except Exception as e:
        messages.error(request, f"Error loading CDIC assessment records for patient: {str(e)}")
        return redirect("view-patient", pk=pid)


@login_required(login_url="user-login")
def cdic_assessment_delete_start(request, aid):
    """DEPRECATED: Use unified delete modal instead"""
    try:
        srecord = CDICRecord.objects.select_related('patient').get(id=aid)
    except CDICRecord.DoesNotExist:
        messages.error(request, "CDIC record not found.")
        return redirect("cdic-assessment-manager")
    return render(
        request,
        "cdic_record/delete-confirm.html",
        {"patient": srecord.patient, "cdic_record": srecord},
    )


@login_required(login_url="user-login")
@require_http_methods(["DELETE"])
def cdic_assessment_delete(request, aid):
    """
    Unified CDIC Record deletion endpoint with password verification
    Part of refactor-delete-confirmation change

    Accepts: DELETE method with JSON payload {password: str}
    Returns: JSON {success: bool, message: str, redirect_url: str}
    """
    from ndas.custom_codes.delete_helpers import (
        has_delete_permission,
        validate_can_delete,
        get_entity_display_name,
        get_redirect_url
    )

    try:
        # 1. Retrieve CDIC record
        cdic_record = get_object_or_404(CDICRecord, id=aid)
        patient = cdic_record.patient

        # 2. Check permissions
        if not has_delete_permission(request.user, cdic_record):
            logger.warning(
                f"Unauthorized deletion attempt: user={request.user.username}, "
                f"entity=CDICRecord, id={aid}"
            )
            return JsonResponse({
                "success": False,
                "error": "Permission denied",
                "message": "You do not have permission to delete this CDIC record."
            }, status=403)

        # 3. Verify password
        try:
            data = json.loads(request.body)
            password = data.get('password', '')
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "error": "Invalid request",
                "message": "Invalid request format."
            }, status=400)

        if not password:
            return JsonResponse({
                "success": False,
                "error": "Password required",
                "message": "Password is required to confirm deletion."
            }, status=400)

        if not request.user.check_password(password):
            logger.warning(
                f"Invalid password for deletion: user={request.user.username}, "
                f"entity=CDICRecord, id={aid}"
            )
            return JsonResponse({
                "success": False,
                "error": "Invalid password",
                "message": "Incorrect password. Please try again."
            }, status=401)

        # 4. Check business rules
        validation_result = validate_can_delete(cdic_record)
        if not validation_result['can_delete']:
            return JsonResponse({
                "success": False,
                "error": "Cannot delete",
                "message": validation_result['reason']
            }, status=400)

        # 5. Store info for logging and response
        cdic_name = get_entity_display_name(cdic_record)

        # 6. Perform deletion
        cdic_record.delete()

        # 7. Audit log
        logger.info(
            f"Deletion successful: user={request.user.username}, "
            f"entity=CDICRecord, name={cdic_name}, id={aid}, "
            f"patient={patient.baby_name}"
        )

        # 8. Return success
        return JsonResponse({
            "success": True,
            "message": f"CDIC Record has been deleted successfully.",
            "redirect_url": reverse("view-patient", kwargs={'pk': patient.id})
        })

    except Exception as e:
        logger.error(
            f"Deletion error: user={request.user.username}, "
            f"entity=CDICRecord, id={aid}, error={str(e)}"
        )
        return JsonResponse({
            "success": False,
            "error": "Server error",
            "message": f"An error occurred during deletion: {str(e)}"
        }, status=500)


# Functions for HINE assessments
@login_required(login_url="user-login")
def hine_assessment_add(request, pid):
    try:
        sp = Patient.objects.get(pk=pid)
    except Patient.DoesNotExist:
        messages.error(request, "Patient not found.")
        return redirect("manage-patients")
    
    if request.method == "POST":
        hine_form = HINEAssessmentForm(request.POST, patient=sp)
        if hine_form.is_valid():
            try:
                hine_record = hine_form.save(commit=False)
                hine_record.patient = sp
                hine_record.added_by = request.user
                hine_record.save()
                messages.success(request, "New HINE assessment record created successfully.")
                return redirect("hine-assessment-view", hine_record.id)
            except Exception as e:
                messages.error(request, f"Error saving HINE record: {str(e)}")
                return render(
                    request, "hine/add.html", {"patient": sp, "hine_form": hine_form}
                )
        else:
            # Format errors for better user experience
            error_messages = []
            for field, errors in hine_form.errors.items():
                if field != '__all__':
                    field_name = hine_form.fields.get(field, None)
                    if field_name:
                        field_name = field_name.label or field.replace('_', ' ').title()
                    else:
                        field_name = field.replace('_', ' ').title()
                    for error in errors:
                        error_messages.append(f"{field_name}: {error}")
                else:
                    for error in errors:
                        error_messages.append(str(error))
            
            if error_messages:
                messages.error(request, "Please correct the following errors: " + "; ".join(error_messages))
            
            return render(
                request, "hine/add.html", {"patient": sp, "hine_form": hine_form}
            )
    else:
        hine_form = HINEAssessmentForm(patient=sp)
        return render(request, "hine/add.html", {"patient": sp, "hine_form": hine_form})


@login_required(login_url="user-login")
def hine_assessment_edit(request, hine_id):
    try:
        shr = HINEAssessment.objects.get(pk=hine_id)
        sp = shr.patient
    except HINEAssessment.DoesNotExist:
        messages.error(request, "HINE assessment not found.")
        return redirect("hine-assessment-manager")
    
    if request.method == "POST":
        hine_form = HINEAssessmentForm(request.POST, instance=shr, patient=sp)
        if hine_form.is_valid():
            hine_record = hine_form.save(commit=False)
            hine_record.patient = sp
            hine_record.last_edit_by = request.user
            hine_record.save()
            messages.success(request, "HINE record updated successfully.")
            return redirect("hine-assessment-view", hine_record.id)
        else:
            # Format errors for better user experience
            error_messages = []
            for field, errors in hine_form.errors.items():
                if field != '__all__':
                    field_name = hine_form.fields.get(field, None)
                    if field_name:
                        field_name = field_name.label or field.replace('_', ' ').title()
                    else:
                        field_name = field.replace('_', ' ').title()
                    for error in errors:
                        error_messages.append(f"{field_name}: {error}")
                else:
                    for error in errors:
                        error_messages.append(str(error))
            
            if error_messages:
                messages.error(request, "Please correct the following errors: " + "; ".join(error_messages))
            
            return render(
                request,
                "hine/edit.html",
                {"patient": sp, "shr": shr, "hine_form": hine_form},
            )
    else:
        hine_form = HINEAssessmentForm(instance=shr, patient=sp)
        return render(
            request,
            "hine/edit.html",
            {"patient": sp, "shr": shr, "hine_form": hine_form},
        )


@login_required(login_url="user-login")
def hine_assessment_view(request, hine_id):
    try:
        sh = HINEAssessment.objects.select_related('patient', 'added_by', 'last_edit_by').get(pk=hine_id)
    except HINEAssessment.DoesNotExist:
        messages.error(request, "HINE assessment record not found.")
        return redirect("hine-assessment-manager")
    return render(request, "hine/view.html", {"patient": sh.patient, "HINERecord": sh})


@login_required(login_url="user-login")
def hine_assessment_manager(request):
    try:
        # Get all HINE assessments
        var_hine_list = HINEAssessment.objects.select_related('patient', 'added_by', 'last_edit_by').all().order_by("-id")
        
        # Search and filter functionality
        search_patient = request.GET.get('search_patient', '').strip()
        search_assessor = request.GET.get('search_assessor', '').strip()
        score_range = request.GET.get('score_range', '')
        date_range = request.GET.get('date_range', '')
        
        # Apply search filters
        if search_patient:
            var_hine_list = var_hine_list.filter(
                patient__baby_name__icontains=search_patient
            )
        
        if search_assessor:
            var_hine_list = var_hine_list.filter(
                assessment_done_by__icontains=search_assessor
            )
        
        if score_range:
            if score_range == 'normal':
                var_hine_list = var_hine_list.filter(score__gte=60)
            elif score_range == 'moderate':
                var_hine_list = var_hine_list.filter(score__gte=40, score__lt=60)
            elif score_range == 'significant':
                var_hine_list = var_hine_list.filter(score__lt=40)

        # Apply date range filters
        if date_range:
            now = timezone.now()
            if date_range == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                var_hine_list = var_hine_list.filter(date_of_assessment__gte=start_date)
            elif date_range == 'week':
                start_date = now - timedelta(days=7)
                var_hine_list = var_hine_list.filter(date_of_assessment__gte=start_date)
            elif date_range == 'month':
                start_date = now - timedelta(days=30)
                var_hine_list = var_hine_list.filter(date_of_assessment__gte=start_date)
            elif date_range == 'year':
                start_date = now - timedelta(days=365)
                var_hine_list = var_hine_list.filter(date_of_assessment__gte=start_date)
        
        # Calculate statistics
        hine_stats = {
            'total': var_hine_list.count(),
            'normal': var_hine_list.filter(score__gte=60).count(),
            'moderate': var_hine_list.filter(score__gte=40, score__lt=60).count(),
            'significant': var_hine_list.filter(score__lt=40).count(),
        }
        
        # Pagination
        paginator = Paginator(var_hine_list, 15)  # Increased page size
        page_number = request.GET.get("page")
        hine_record_list = paginator.get_page(page_number)
        
        context = {
            "patient": None,
            "hine_record_list": hine_record_list,
            "hine_stats": hine_stats,
        }
        
        return render(request, "hine/manager.html", context)
        
    except Exception as e:
        messages.error(request, f"Error loading HINE assessment records: {str(e)}")
        return render(request, "hine/manager.html", {
            "patient": None,
            "hine_record_list": None,
            "hine_stats": {'total': 0, 'normal': 0, 'moderate': 0, 'significant': 0},
        })


@login_required(login_url="user-login")
def hine_assessment_manager_by_patients(request, pid):
    try:
        # Get patient with error handling
        try:
            sp = Patient.objects.get(pk=pid)
        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")
            return redirect("manage-patients")
        
        # Get HINE assessments for this patient
        var_hine_list = HINEAssessment.objects.select_related('patient', 'added_by', 'last_edit_by').filter(patient=sp.id).order_by("-id")
        
        # Search and filter functionality (same as general manager but for specific patient)
        search_assessor = request.GET.get('search_assessor', '').strip()
        score_range = request.GET.get('score_range', '')
        date_range = request.GET.get('date_range', '')
        
        # Apply filters
        if search_assessor:
            var_hine_list = var_hine_list.filter(
                assessment_done_by__icontains=search_assessor
            )
        
        if score_range:
            if score_range == 'normal':
                var_hine_list = var_hine_list.filter(score__gte=60)
            elif score_range == 'moderate':
                var_hine_list = var_hine_list.filter(score__gte=40, score__lt=60)
            elif score_range == 'significant':
                var_hine_list = var_hine_list.filter(score__lt=40)

        if date_range:
            now = timezone.now()
            if date_range == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                var_hine_list = var_hine_list.filter(date_of_assessment__gte=start_date)
            elif date_range == 'week':
                start_date = now - timedelta(days=7)
                var_hine_list = var_hine_list.filter(date_of_assessment__gte=start_date)
            elif date_range == 'month':
                start_date = now - timedelta(days=30)
                var_hine_list = var_hine_list.filter(date_of_assessment__gte=start_date)
            elif date_range == 'year':
                start_date = now - timedelta(days=365)
                var_hine_list = var_hine_list.filter(date_of_assessment__gte=start_date)

        # Calculate statistics for this patient
        hine_stats = {
            'total': var_hine_list.count(),
            'normal': var_hine_list.filter(score__gte=60).count(),
            'moderate': var_hine_list.filter(score__gte=40, score__lt=60).count(),
            'significant': var_hine_list.filter(score__lt=40).count(),
        }
        
        # Pagination
        paginator = Paginator(var_hine_list, 15)
        page_number = request.GET.get("page")
        hine_record_list = paginator.get_page(page_number)
        
        context = {
            "patient": sp,
            "hine_record_list": hine_record_list,
            "hine_stats": hine_stats,
        }
        
        return render(request, "hine/manager.html", context)
        
    except Exception as e:
        messages.error(request, f"Error loading HINE assessment records for patient: {str(e)}")
        return redirect("view-patient", pk=pid)


@login_required(login_url="user-login")
def hine_assessment_delete_start(request, hine_id):
    """DEPRECATED: Use unified delete modal instead"""
    shr = HINEAssessment.objects.get(id=hine_id)
    return render(
        request,
        "hine/delete-confirm.html",
        {"patient": shr.patient, "hine_record": shr},
    )


@login_required(login_url="user-login")
@require_http_methods(["DELETE"])
def hine_assessment_delete(request, hine_id):
    """
    Unified HINE Assessment deletion endpoint with password verification
    Part of refactor-delete-confirmation change

    Accepts: DELETE method with JSON payload {password: str}
    Returns: JSON {success: bool, message: str, redirect_url: str}
    """
    from ndas.custom_codes.delete_helpers import (
        has_delete_permission,
        validate_can_delete,
        get_entity_display_name,
        get_redirect_url
    )

    try:
        # 1. Retrieve HINE assessment
        hine_assessment = get_object_or_404(HINEAssessment, id=hine_id)
        patient = hine_assessment.patient

        # 2. Check permissions
        if not has_delete_permission(request.user, hine_assessment):
            logger.warning(
                f"Unauthorized deletion attempt: user={request.user.username}, "
                f"entity=HINEAssessment, id={hine_id}"
            )
            return JsonResponse({
                "success": False,
                "error": "Permission denied",
                "message": "You do not have permission to delete this HINE assessment."
            }, status=403)

        # 3. Verify password
        try:
            data = json.loads(request.body)
            password = data.get('password', '')
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "error": "Invalid request",
                "message": "Invalid request format."
            }, status=400)

        if not password:
            return JsonResponse({
                "success": False,
                "error": "Password required",
                "message": "Password is required to confirm deletion."
            }, status=400)

        if not request.user.check_password(password):
            logger.warning(
                f"Invalid password for deletion: user={request.user.username}, "
                f"entity=HINEAssessment, id={hine_id}"
            )
            return JsonResponse({
                "success": False,
                "error": "Invalid password",
                "message": "Incorrect password. Please try again."
            }, status=401)

        # 4. Check business rules
        validation_result = validate_can_delete(hine_assessment)
        if not validation_result['can_delete']:
            return JsonResponse({
                "success": False,
                "error": "Cannot delete",
                "message": validation_result['reason']
            }, status=400)

        # 5. Store info for logging and response
        hine_name = get_entity_display_name(hine_assessment)

        # 6. Perform deletion
        hine_assessment.delete()

        # 7. Audit log
        logger.info(
            f"Deletion successful: user={request.user.username}, "
            f"entity=HINEAssessment, name={hine_name}, id={hine_id}, "
            f"patient={patient.baby_name}"
        )

        # 8. Return success
        return JsonResponse({
            "success": True,
            "message": f"HINE Assessment has been deleted successfully.",
            "redirect_url": reverse("view-patient", kwargs={'pk': patient.id})
        })

    except Exception as e:
        logger.error(
            f"Deletion error: user={request.user.username}, "
            f"entity=HINEAssessment, id={hine_id}, error={str(e)}"
        )
        return JsonResponse({
            "success": False,
            "error": "Server error",
            "message": f"An error occurred during deletion: {str(e)}"
        }, status=500)


# Functions for Developmental assessments
@login_required(login_url="user-login")
def da_assessment_add(request, pid):
    try:
        sp = Patient.objects.get(pk=pid)
    except Patient.DoesNotExist:
        messages.error(request, "Patient not found.")
        return redirect("manage-patients")

    if request.method == "POST":
        da_form_data = DevelopmentalAssessmentForm(request.POST, patient=sp)
        if da_form_data.is_valid():
            try:
                da_record = da_form_data.save(commit=False)
                da_record.patient = sp
                da_record.added_by = request.user
                da_record.save()
                messages.success(
                    request, "New developmental assessment record created successfully."
                )
                return redirect("da-assessment-view", da_record.id)
            except Exception as e:
                messages.error(request, f"Error saving developmental assessment record: {str(e)}")
                # Pass the form data without the unsaved instance to avoid RelatedObjectDoesNotExist
                return render(
                    request,
                    "develop_assemnt/add.html",
                    {"patient": sp, "da_form": da_form_data},
                )
        else:
            # Format errors for better user experience
            error_messages = []
            for field, errors in da_form_data.errors.items():
                field_name = da_form_data.fields[field].label or field.replace('_', ' ').title()
                for error in errors:
                    error_messages.append(f"{field_name}: {error}")

            if error_messages:
                messages.error(request, "Please correct the following errors: " + "; ".join(error_messages))

            # Pass form data directly without saving to avoid patient relation issues
            return render(
                request,
                "develop_assemnt/add.html",
                {"patient": sp, "da_form": da_form_data},
            )
    else:
        da_form = DevelopmentalAssessmentForm(patient=sp)
        return render(
            request, "develop_assemnt/add.html", {"patient": sp, "da_form": da_form}
        )


@login_required(login_url="user-login")
def da_assessment_edit(request, da_id):
    try:
        dar = DevelopmentalAssessment.objects.select_related('patient', 'added_by', 'last_edit_by').get(id=da_id)
    except DevelopmentalAssessment.DoesNotExist:
        messages.error(request, "Developmental assessment record not found.")
        return redirect("da-assessment-manager")

    if request.method == "POST":
        assessment_form_data = DevelopmentalAssessmentForm(request.POST, instance=dar, patient=dar.patient)
        if assessment_form_data.is_valid():
            da_record = assessment_form_data.save(commit=False)
            da_record.last_edit_by = request.user
            da_record.save()
            messages.success(
                request, "Developmental assessment details are updated succesfully..."
            )
            return redirect("da-assessment-view", dar.id)
        else:
            messages.success(request, assessment_form_data.errors)
            return render(
                request,
                "develop_assemnt/edit.html",
                {"da_form": assessment_form_data, "dar": dar},
            )
    else:
        assessment_form = DevelopmentalAssessmentForm(instance=dar, patient=dar.patient)
        return render(
            request, "develop_assemnt/edit.html", {"da_form": assessment_form, "dar": dar}
        )


@login_required(login_url="user-login")
def da_assessment_view(request, da_id):
    try:
        sdar = DevelopmentalAssessment.objects.select_related('patient', 'added_by', 'last_edit_by').get(pk=da_id)
    except DevelopmentalAssessment.DoesNotExist:
        messages.error(request, "Developmental assessment record not found.")
        return redirect("da-assessment-manager")
    return render(request, "develop_assemnt/view.html", {"DARecord": sdar})


@login_required(login_url="user-login")
def da_assessment_manager(request):
    try:
        # Get all developmental assessments
        var_da_list = DevelopmentalAssessment.objects.select_related('patient', 'added_by', 'last_edit_by').all().order_by("-id")
        
        # Search and filter functionality
        search_patient = request.GET.get('search_patient', '').strip()
        development_status = request.GET.get('development_status', '')
        age_range = request.GET.get('age_range', '')
        date_range = request.GET.get('date_range', '')
        assessor = request.GET.get('assessor', '').strip()
        
        # Apply search filters
        if search_patient:
            var_da_list = var_da_list.filter(
                patient__baby_name__icontains=search_patient
            )
        
        if assessor:
            var_da_list = var_da_list.filter(
                assessment_done_by__icontains=assessor
            )
        
        if development_status:
            if development_status == 'normal':
                var_da_list = var_da_list.filter(is_dx_normal=True)
            elif development_status == 'delayed':
                var_da_list = var_da_list.filter(is_dx_normal=False)
        
        # Apply age range filters (assuming getAssessmentAgeInMonths method exists)
        if age_range:
            age_ranges = {
                '0-6': (0, 6),
                '6-12': (6, 12),
                '12-24': (12, 24),
                '24-36': (24, 36),
                '36-48': (36, 48),
                '48-72': (48, 72),
            }
            if age_range in age_ranges:
                min_age, max_age = age_ranges[age_range]
                # This would require a custom filter or database function
                # For now, we'll filter in Python (not ideal for large datasets)
                filtered_ids = []
                for record in var_da_list:
                    try:
                        age_months = record.getAssessmentAgeInMonths
                        if isinstance(age_months, str):
                            # Extract numeric value if it's a string like "12 months"
                            age_months = int(''.join(filter(str.isdigit, age_months)))
                        if min_age <= age_months <= max_age:
                            filtered_ids.append(record.id)
                    except (ValueError, AttributeError):
                        continue
                var_da_list = var_da_list.filter(id__in=filtered_ids)
        
        # Apply date range filters
        if date_range:
            now = timezone.now()
            if date_range == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                var_da_list = var_da_list.filter(date_of_assessment__gte=start_date)
            elif date_range == 'week':
                start_date = now - timedelta(days=7)
                var_da_list = var_da_list.filter(date_of_assessment__gte=start_date)
            elif date_range == 'month':
                start_date = now - timedelta(days=30)
                var_da_list = var_da_list.filter(date_of_assessment__gte=start_date)
            elif date_range == 'quarter':
                start_date = now - timedelta(days=90)
                var_da_list = var_da_list.filter(date_of_assessment__gte=start_date)
            elif date_range == 'year':
                start_date = now - timedelta(days=365)
                var_da_list = var_da_list.filter(date_of_assessment__gte=start_date)
        
        # Calculate statistics
        da_stats = {
            'total': var_da_list.count(),
            'normal': var_da_list.filter(is_dx_normal=True).count(),
            'delayed': var_da_list.filter(is_dx_normal=False).count(),
            'this_month': var_da_list.filter(
                date_of_assessment__gte=timezone.now() - timedelta(days=30)
            ).count(),
        }
        
        # Pagination
        paginator = Paginator(var_da_list, 15)
        page_number = request.GET.get("page")
        da_record_list = paginator.get_page(page_number)
        
        context = {
            "patient": None,
            "da_record_list": da_record_list,
            "da_stats": da_stats,
        }
        
        return render(request, "develop_assemnt/manager.html", context)
        
    except Exception as e:
        messages.error(request, f"Error loading developmental assessment records: {str(e)}")
        return render(request, "develop_assemnt/manager.html", {
            "patient": None,
            "da_record_list": None,
            "da_stats": {'total': 0, 'normal': 0, 'delayed': 0, 'this_month': 0},
        })


@login_required(login_url="user-login")
def da_assessment_manager_by_patients(request, pid):
    try:
        # Get patient with error handling
        try:
            sp = Patient.objects.get(pk=pid)
        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")
            return redirect("manage-patients")
        
        # Get developmental assessments for this patient
        var_da_list = DevelopmentalAssessment.objects.select_related('patient', 'added_by', 'last_edit_by').filter(patient=sp.id).order_by("-id")
        
        # Search and filter functionality (same as general manager but for specific patient)
        development_status = request.GET.get('development_status', '')
        age_range = request.GET.get('age_range', '')
        date_range = request.GET.get('date_range', '')
        assessor = request.GET.get('assessor', '').strip()
        
        # Apply filters
        if assessor:
            var_da_list = var_da_list.filter(
                assessment_done_by__icontains=assessor
            )
        
        if development_status:
            if development_status == 'normal':
                var_da_list = var_da_list.filter(is_dx_normal=True)
            elif development_status == 'delayed':
                var_da_list = var_da_list.filter(is_dx_normal=False)
        
        # Apply age range filters
        if age_range:
            age_ranges = {
                '0-6': (0, 6),
                '6-12': (6, 12),
                '12-24': (12, 24),
                '24-36': (24, 36),
                '36-48': (36, 48),
                '48-72': (48, 72),
            }
            if age_range in age_ranges:
                min_age, max_age = age_ranges[age_range]
                filtered_ids = []
                for record in var_da_list:
                    try:
                        age_months = record.getAssessmentAgeInMonths
                        if isinstance(age_months, str):
                            age_months = int(''.join(filter(str.isdigit, age_months)))
                        if min_age <= age_months <= max_age:
                            filtered_ids.append(record.id)
                    except (ValueError, AttributeError):
                        continue
                var_da_list = var_da_list.filter(id__in=filtered_ids)
        
        # Apply date range filters
        if date_range:
            now = timezone.now()
            if date_range == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                var_da_list = var_da_list.filter(date_of_assessment__gte=start_date)
            elif date_range == 'week':
                start_date = now - timedelta(days=7)
                var_da_list = var_da_list.filter(date_of_assessment__gte=start_date)
            elif date_range == 'month':
                start_date = now - timedelta(days=30)
                var_da_list = var_da_list.filter(date_of_assessment__gte=start_date)
            elif date_range == 'quarter':
                start_date = now - timedelta(days=90)
                var_da_list = var_da_list.filter(date_of_assessment__gte=start_date)
            elif date_range == 'year':
                start_date = now - timedelta(days=365)
                var_da_list = var_da_list.filter(date_of_assessment__gte=start_date)
        
        # Calculate statistics for this patient
        da_stats = {
            'total': var_da_list.count(),
            'normal': var_da_list.filter(is_dx_normal=True).count(),
            'delayed': var_da_list.filter(is_dx_normal=False).count(),
            'this_month': var_da_list.filter(
                date_of_assessment__gte=timezone.now() - timedelta(days=30)
            ).count(),
        }
        
        # Pagination
        paginator = Paginator(var_da_list, 15)
        page_number = request.GET.get("page")
        da_record_list = paginator.get_page(page_number)
        
        context = {
            "patient": sp,
            "da_record_list": da_record_list,
            "da_stats": da_stats,
        }
        
        return render(request, "develop_assemnt/manager.html", context)
        
    except Exception as e:
        messages.error(request, f"Error loading developmental assessment records for patient: {str(e)}")
        return redirect("view-patient", pk=pid)


@login_required(login_url="user-login")
def da_assessment_delete_start(request, da_id):
    """DEPRECATED: Use unified delete modal instead"""
    try:
        sdr = DevelopmentalAssessment.objects.select_related('patient').get(id=da_id)
    except DevelopmentalAssessment.DoesNotExist:
        messages.error(request, "Developmental assessment record not found.")
        return redirect("da-assessment-manager")
    return render(
        request,
        "develop_assemnt/delete-confirm.html",
        {"patient": sdr.patient, "da_record": sdr},
    )


@login_required(login_url="user-login")
@require_http_methods(["DELETE"])
def da_assessment_delete(request, da_id):
    """
    Unified Developmental Assessment deletion endpoint with password verification
    Part of refactor-delete-confirmation change

    Accepts: DELETE method with JSON payload {password: str}
    Returns: JSON {success: bool, message: str, redirect_url: str}
    """
    from ndas.custom_codes.delete_helpers import (
        has_delete_permission,
        validate_can_delete,
        get_entity_display_name,
        get_redirect_url
    )

    try:
        # 1. Retrieve Developmental assessment
        da_assessment = get_object_or_404(DevelopmentalAssessment, id=da_id)
        patient = da_assessment.patient

        # 2. Check permissions
        if not has_delete_permission(request.user, da_assessment):
            logger.warning(
                f"Unauthorized deletion attempt: user={request.user.username}, "
                f"entity=DevelopmentalAssessment, id={da_id}"
            )
            return JsonResponse({
                "success": False,
                "error": "Permission denied",
                "message": "You do not have permission to delete this developmental assessment."
            }, status=403)

        # 3. Verify password
        try:
            data = json.loads(request.body)
            password = data.get('password', '')
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "error": "Invalid request",
                "message": "Invalid request format."
            }, status=400)

        if not password:
            return JsonResponse({
                "success": False,
                "error": "Password required",
                "message": "Password is required to confirm deletion."
            }, status=400)

        if not request.user.check_password(password):
            logger.warning(
                f"Invalid password for deletion: user={request.user.username}, "
                f"entity=DevelopmentalAssessment, id={da_id}"
            )
            return JsonResponse({
                "success": False,
                "error": "Invalid password",
                "message": "Incorrect password. Please try again."
            }, status=401)

        # 4. Check business rules
        validation_result = validate_can_delete(da_assessment)
        if not validation_result['can_delete']:
            return JsonResponse({
                "success": False,
                "error": "Cannot delete",
                "message": validation_result['reason']
            }, status=400)

        # 5. Store info for logging and response
        da_name = get_entity_display_name(da_assessment)

        # 6. Perform deletion
        da_assessment.delete()

        # 7. Audit log
        logger.info(
            f"Deletion successful: user={request.user.username}, "
            f"entity=DevelopmentalAssessment, name={da_name}, id={da_id}, "
            f"patient={patient.baby_name}"
        )

        # 8. Return success
        return JsonResponse({
            "success": True,
            "message": f"Developmental Assessment has been deleted successfully.",
            "redirect_url": reverse("view-patient", kwargs={'pk': patient.id})
        })

    except Exception as e:
        logger.error(
            f"Deletion error: user={request.user.username}, "
            f"entity=DevelopmentalAssessment, id={da_id}, error={str(e)}"
        )
        return JsonResponse({
            "success": False,
            "error": "Server error",
            "message": f"An error occurred during deletion: {str(e)}"
        }, status=500)


@login_required(login_url="user-login")
def print(request):
    pass


# ================================
# General Paediatric Assessment (GPA) Views
# ================================

@login_required(login_url="user-login")
def gpa_add(request, pid):
    """Create a new General Paediatric Assessment record for a patient"""
    try:
        patient = Patient.objects.get(pk=pid)
    except Patient.DoesNotExist:
        messages.error(request, "Patient not found")
        return redirect("patient-manager")

    if request.method == "POST":
        form = GeneralPaediatricAssessmentForm(request.POST)
        if form.is_valid():
            gpa_record = form.save(commit=False)
            gpa_record.patient = patient
            gpa_record.save()
            messages.success(
                request,
                f"General Paediatric Assessment for {patient.baby_name} has been successfully created"
            )
            return redirect("view-patient", pk=patient.pk)
        else:
            messages.error(request, "Please correct the errors below")
    else:
        form = GeneralPaediatricAssessmentForm()

    context = {
        "form": form,
        "patient": patient,
    }
    return render(request, "gpa_record/add.html", context)


@login_required(login_url="user-login")
def gpa_edit(request, gpa_id):
    """Edit an existing General Paediatric Assessment record"""
    try:
        gpa_record = GeneralPaediatricAssessment.objects.select_related(
            "patient", "discharged_authorized_by"
        ).get(pk=gpa_id)
    except GeneralPaediatricAssessment.DoesNotExist:
        messages.error(request, "GPA record not found")
        return redirect("gpa-manager")

    if request.method == "POST":
        form = GeneralPaediatricAssessmentForm(request.POST, instance=gpa_record)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"GPA record for {gpa_record.patient.baby_name} has been successfully updated"
            )
            return redirect("gpa-view", gpa_id=gpa_record.pk)
        else:
            messages.error(request, "Please correct the errors below")
    else:
        form = GeneralPaediatricAssessmentForm(instance=gpa_record)

    context = {
        "form": form,
        "gpa_record": gpa_record,
        "patient": gpa_record.patient,
    }
    return render(request, "gpa_record/edit.html", context)


@login_required(login_url="user-login")
def gpa_view(request, gpa_id):
    """View detailed information about a specific GPA record"""
    try:
        gpa_record = GeneralPaediatricAssessment.objects.select_related(
            "patient",
            "discharged_authorized_by",
            "added_by",
            "last_edit_by"
        ).get(pk=gpa_id)
    except GeneralPaediatricAssessment.DoesNotExist:
        messages.error(request, "GPA record not found")
        return redirect("gpa-manager")

    context = {
        "gpa_record": gpa_record,
        "patient": gpa_record.patient,
    }
    return render(request, "gpa_record/view.html", context)


@login_required(login_url="user-login")
def gpa_manager(request):
    """List all General Paediatric Assessment records with filtering, search, and pagination"""
    # Get filter and search parameters
    filter_type = request.GET.get("filter", "")
    search_query = request.GET.get("search", "").strip()
    page_number = request.GET.get("page", 1)

    # Base queryset with optimized query
    queryset = GeneralPaediatricAssessment.objects.select_related(
        "patient",
        "discharged_authorized_by",
        "added_by"
    ).order_by("-assessment_date")

    # Apply search filter
    if search_query:
        queryset = queryset.filter(
            Q(patient__baby_name__icontains=search_query)
            | Q(patient__disk_no__icontains=search_query)
            | Q(patient__bht__icontains=search_query)
            | Q(healthcare_provider__icontains=search_query)
            | Q(current_problems__icontains=search_query)
        )

    # Apply status filters
    if filter_type == "recent":
        # Last 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        queryset = queryset.filter(assessment_date__gte=cutoff_date)
    elif filter_type == "active":
        queryset = queryset.filter(is_discharged=False)
    elif filter_type == "discharged":
        queryset = queryset.filter(is_discharged=True)

    # Get total count before pagination
    count = queryset.count()

    # Pagination with proper error handling
    paginator = Paginator(queryset, 25)  # Show 25 records per page
    try:
        page_obj = paginator.get_page(page_number)
    except Exception as e:
        logger.error(f"Pagination error in gpa_manager: {str(e)}")
        page_obj = paginator.get_page(1)

    # Annotate with bookmark information for efficient display
    for gpa in page_obj:
        gpa.isBookmarked = gpa.is_bookmarked

    context = {
        "gpa_page_obj": page_obj,
        "count": count,
        "filter_type": filter_type,
        "search_query": search_query,
    }
    return render(request, "gpa_record/manager.html", context)


@login_required(login_url="user-login")
def gpa_manager_by_patient(request, pid):
    """List all GPA records for a specific patient with search and pagination"""
    try:
        patient = Patient.objects.get(pk=pid)
    except Patient.DoesNotExist:
        messages.error(request, "Patient not found")
        return redirect("patient-manager")

    # Get search parameter
    search_query = request.GET.get("search", "").strip()
    page_number = request.GET.get("page", 1)

    # Base queryset filtered by patient
    queryset = GeneralPaediatricAssessment.objects.filter(
        patient=patient
    ).select_related(
        "discharged_authorized_by",
        "added_by"
    ).order_by("-assessment_date")

    # Apply search filter if provided
    if search_query:
        queryset = queryset.filter(
            Q(healthcare_provider__icontains=search_query)
            | Q(current_problems__icontains=search_query)
        )

    # Get total count before pagination
    count = queryset.count()

    # Pagination with proper error handling
    paginator = Paginator(queryset, 25)  # Show 25 records per page
    try:
        page_obj = paginator.get_page(page_number)
    except Exception as e:
        logger.error(f"Pagination error in gpa_manager_by_patient: {str(e)}")
        page_obj = paginator.get_page(1)

    # Annotate with bookmark information for efficient display
    for gpa in page_obj:
        gpa.isBookmarked = gpa.is_bookmarked

    context = {
        "gpa_page_obj": page_obj,
        "count": count,
        "patient": patient,
        "search_query": search_query,
        "filter_type": "patient",
    }
    return render(request, "gpa_record/manager.html", context)


@login_required(login_url="user-login")
def gpa_delete_start(request, gpa_id):
    """DEPRECATED: Use unified delete modal instead"""
    try:
        gpa_record = GeneralPaediatricAssessment.objects.select_related(
            "patient"
        ).get(pk=gpa_id)
    except GeneralPaediatricAssessment.DoesNotExist:
        messages.error(request, "GPA record not found")
        return redirect("gpa-manager")

    context = {
        "gpa_record": gpa_record,
        "patient": gpa_record.patient,
    }
    return render(request, "gpa_record/delete_confirm.html", context)


@login_required(login_url="user-login")
@require_http_methods(["DELETE"])
def gpa_delete(request, gpa_id):
    """
    Unified General Paediatric Assessment deletion endpoint with password verification
    Part of refactor-delete-confirmation change

    Accepts: DELETE method with JSON payload {password: str}
    Returns: JSON {success: bool, message: str, redirect_url: str}
    """
    from ndas.custom_codes.delete_helpers import (
        has_delete_permission,
        validate_can_delete,
        get_entity_display_name,
        get_redirect_url
    )

    try:
        # 1. Retrieve GPA record
        gpa_record = get_object_or_404(GeneralPaediatricAssessment, id=gpa_id)
        patient = gpa_record.patient

        # 2. Check permissions
        if not has_delete_permission(request.user, gpa_record):
            logger.warning(
                f"Unauthorized deletion attempt: user={request.user.username}, "
                f"entity=GeneralPaediatricAssessment, id={gpa_id}"
            )
            return JsonResponse({
                "success": False,
                "error": "Permission denied",
                "message": "You do not have permission to delete this GPA record."
            }, status=403)

        # 3. Verify password
        try:
            data = json.loads(request.body)
            password = data.get('password', '')
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "error": "Invalid request",
                "message": "Invalid request format."
            }, status=400)

        if not password:
            return JsonResponse({
                "success": False,
                "error": "Password required",
                "message": "Password is required to confirm deletion."
            }, status=400)

        if not request.user.check_password(password):
            logger.warning(
                f"Invalid password for deletion: user={request.user.username}, "
                f"entity=GeneralPaediatricAssessment, id={gpa_id}"
            )
            return JsonResponse({
                "success": False,
                "error": "Invalid password",
                "message": "Incorrect password. Please try again."
            }, status=401)

        # 4. Check business rules
        validation_result = validate_can_delete(gpa_record)
        if not validation_result['can_delete']:
            return JsonResponse({
                "success": False,
                "error": "Cannot delete",
                "message": validation_result['reason']
            }, status=400)

        # 5. Store info for logging and response
        gpa_name = get_entity_display_name(gpa_record)

        # 6. Perform deletion
        gpa_record.delete()

        # 7. Audit log
        logger.info(
            f"Deletion successful: user={request.user.username}, "
            f"entity=GeneralPaediatricAssessment, name={gpa_name}, id={gpa_id}, "
            f"patient={patient.baby_name}"
        )

        # 8. Return success
        return JsonResponse({
            "success": True,
            "message": f"General Paediatric Assessment has been deleted successfully.",
            "redirect_url": reverse("view-patient", kwargs={'pk': patient.id})
        })

    except Exception as e:
        logger.error(
            f"Deletion error: user={request.user.username}, "
            f"entity=GeneralPaediatricAssessment, id={gpa_id}, error={str(e)}"
        )
        return JsonResponse({
            "success": False,
            "error": "Server error",
            "message": f"An error occurred during deletion: {str(e)}"
        }, status=500)


