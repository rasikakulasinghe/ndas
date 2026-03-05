"""
Enhanced video views with complete upload and processing functionality.
"""

import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django_ratelimit.decorators import ratelimit
from django.http import JsonResponse, HttpResponseForbidden, Http404
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q
from django.urls import reverse
from django.core.exceptions import ValidationError

from patients.models import Patient
from .models import Video
from ndas.custom_codes.custom_methods import institution_scope
from .forms import VideoForm
from ndas.custom_codes.choice import PROCESSING_STATUS
from ndas.custom_codes.error_handlers import handle_view_errors

logger = logging.getLogger(__name__)


@handle_view_errors(redirect_url='video:manager', error_message='Error adding video')
@ratelimit(key='user', rate='10/m', method='POST')
@ratelimit(key='ip', rate='20/m', method='POST')
@login_required(login_url="user-login")
def video_add(request, patient_id):
    """Enhanced video upload with proper form handling and progress tracking"""
    patient = get_object_or_404(Patient.objects.for_institution(getattr(request, 'institution', None)), id=patient_id)

    if request.method == "POST":
        form = VideoForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                video = form.save(commit=False)
                video.patient = patient

                # Additional validation now that patient is assigned
                if video.recorded_on and hasattr(patient, 'dob_tob') and patient.dob_tob:
                    if video.recorded_on.date() < patient.dob_tob.date():
                        form.add_error('recorded_on', 'Recording date cannot be before patient birth date.')
                        raise ValidationError('Recording date cannot be before patient birth date.')
                
                video.save()

                logger.info(f"Video uploaded successfully: {video.id} by user {request.user.id}")

                # Prepare response data
                response_data = {
                    "success": True,
                    "msg": "Video uploaded successfully!",
                    "f_id": video.id,
                    "video_title": video.title,
                    "file_size": video.file_size_mb,
                    "redirect_url": reverse("video:view", kwargs={"video_id": video.id}),
                }

                # For AJAX requests, return JSON response
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(response_data)
                else:
                    # For regular form submissions, redirect with success message
                    messages.success(request, response_data["msg"])
                    return redirect("video:view", video_id=video.id)

            except ValidationError as e:
                logger.error(f"Validation error in video upload: {e}")
                form.add_error(None, str(e))
            except Exception as e:
                logger.error(f"Unexpected error in video upload: {e}")
                form.add_error(None, "An unexpected error occurred during upload.")

        # Form has errors
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            # Convert form errors to a more readable format for AJAX
            errors = {}
            for field, error_list in form.errors.items():
                if field == '__all__':
                    errors['general'] = error_list
                else:
                    errors[field] = error_list
            
            return JsonResponse({
                "success": False, 
                "errors": errors,
                "msg": "Please correct the errors and try again."
            })
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        # GET request - show the upload form
        form = VideoForm()

    context = {
        "patient": patient,
        "today": timezone.now().strftime("%Y-%m-%d"),
        "video_form": form,
        "page_title": f"Upload Video - {patient.baby_name}",
    }
    return render(request, "video/add.html", context)


@login_required(login_url="user-login")
def video_view(request, video_id):
    """View video details and player"""
    video = get_object_or_404(Video, id=video_id, **institution_scope(request))

    # Check access permissions
    if not request.user.is_staff and video.added_by != request.user:
        messages.error(request, "You do not have permission to view this video.")
        return redirect("manage-patients")

    # Check for existing bookmark
    from patients.models import Bookmark

    bookmark = Bookmark.objects.filter(
        object_id=video.id, bookmark_type="Video", added_by=request.user
    ).first()

    # Check if video is new (not used in assessments)
    try:
        is_new_file = video.is_new_file()
    except Exception as e:
        logger.warning(f"Could not determine new-file status for video {video.id}: {e}")
        is_new_file = True

    context = {
        "video": video,
        "file": video,  # For backward compatibility with template
        "patient": video.patient,
        "bookmark": bookmark,
        "is_new_file": is_new_file,
        "page_title": f"Video: {video.title}",
        "breadcrumbs": [
            {"name": "Dashboard", "url": reverse("home")},
            {"name": "Patient", "url": reverse("view-patient", args=[video.patient.id])},
            {"name": "Video", "url": None},
        ],
    }

    return render(request, "video/view.html", context)


@handle_view_errors(redirect_url='video:manager', error_message='Error editing video')
@ratelimit(key='user', rate='10/m', method='POST')
@ratelimit(key='ip', rate='20/m', method='POST')
@login_required(login_url="user-login")
def video_edit(request, video_id):
    """Edit video details with enhanced validation and error handling"""
    video = get_object_or_404(Video, id=video_id, **institution_scope(request))

    # Check permissions
    if not request.user.is_staff and video.added_by != request.user:
        messages.error(request, "You do not have permission to edit this video.")
        return redirect("manage-patients")

    if request.method == "POST":
        form = VideoForm(request.POST, request.FILES, instance=video)

        if form.is_valid():
            try:
                updated_video = form.save(commit=False)

                # Additional validation for recording date with patient
                if updated_video.recorded_on and hasattr(video.patient, 'dob_tob') and video.patient.dob_tob:
                    if updated_video.recorded_on.date() < video.patient.dob_tob.date():
                        form.add_error('recorded_on', 'Recording date cannot be before patient birth date.')
                        raise ValidationError('Recording date cannot be before patient birth date.')
                
                updated_video.save()

                logger.info(f"Video updated successfully: {video.id} by user {request.user.id}")
                messages.success(request, "Video information updated successfully.")
                
                # Return JSON for AJAX requests
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({
                        "success": True,
                        "msg": "Video updated successfully!",
                        "redirect_url": reverse("video:view", kwargs={"video_id": video.id}),
                    })
                
                return redirect("video:view", video_id=video.id)
                
            except ValidationError as e:
                logger.error(f"Validation error in video edit: {e}")
                form.add_error(None, str(e))
                messages.error(request, "Please correct the errors below.")
            except Exception as e:
                logger.error(f"Unexpected error in video edit: {e}")
                form.add_error(None, "An unexpected error occurred during update.")
                messages.error(request, "An unexpected error occurred. Please try again.")
        else:
            messages.error(request, "Please correct the errors below.")
            
        # Return JSON errors for AJAX requests
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            errors = {}
            for field, error_list in form.errors.items():
                if field == '__all__':
                    errors['general'] = error_list
                else:
                    errors[field] = error_list
            
            return JsonResponse({
                "success": False, 
                "errors": errors,
                "msg": "Please correct the errors and try again."
            })
    else:
        form = VideoForm(instance=video)

    context = {
        "video": video,
        "file": video,  # For backward compatibility
        "patient": video.patient,
        "video_form": form,
        "page_title": f"Edit Video - {video.title}",
        "breadcrumbs": [
            {"name": "Dashboard", "url": reverse("home")},
            {"name": "Patient", "url": reverse("view-patient", args=[video.patient.id])},
            {"name": "Video", "url": reverse("video:view", args=[video.id])},
            {"name": "Edit", "url": None},
        ],
    }

    return render(request, "video/edit.html", context)


@login_required(login_url="user-login")
def video_manager(request):
    """Enhanced video manager with filtering, search, and pagination following Django best practices"""
    # Get search and filter parameters with proper defaults
    search_query = request.GET.get("search", "").strip()
    status_filter = request.GET.get("status", "")
    uploader_filter = request.GET.get("uploader", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    bookmarked_filter = request.GET.get("bookmarked_only", "")
    page_number = request.GET.get("page", 1)

    # Base queryset with optimized related data loading, scoped to institution
    _inst = getattr(request, 'institution', None)
    _patients_qs = Patient.objects.for_institution(_inst)
    queryset = (
        Video.objects.filter(patient__in=_patients_qs)
        .select_related("patient", "added_by", "last_edit_by")
        .order_by("-recorded_on", "-created_at")
    )

    # Apply search filter using Q objects for complex queries
    if search_query:
        queryset = queryset.filter(
            Q(title__icontains=search_query)
            | Q(patient__baby_name__icontains=search_query)
                | Q(patient__disk_no__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    # Apply status filter (new vs assessed videos)
    if status_filter == "new":
        # New videos - not used in assessments
        from patients.models import GMAssessment
        used_video_ids = GMAssessment.objects.values_list('video_file_id', flat=True)
        queryset = queryset.exclude(id__in=used_video_ids)
    elif status_filter == "assessed":
        # Assessed videos - used in assessments
        from patients.models import GMAssessment
        used_video_ids = GMAssessment.objects.values_list('video_file_id', flat=True)
        queryset = queryset.filter(id__in=used_video_ids)

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
            queryset = queryset.filter(recorded_on__date__gte=date_from_parsed)
        except ValueError as e:
            logger.warning(f"Invalid date_from format: {date_from}")
            messages.warning(
                request, "Invalid 'from' date format. Please use YYYY-MM-DD format."
            )

    if date_to:
        try:
            from datetime import datetime

            date_to_parsed = datetime.strptime(date_to, "%Y-%m-%d").date()
            queryset = queryset.filter(recorded_on__date__lte=date_to_parsed)
        except ValueError as e:
            logger.warning(f"Invalid date_to format: {date_to}")
            messages.warning(
                request, "Invalid 'to' date format. Please use YYYY-MM-DD format."
            )

    # Apply bookmarked filter
    if bookmarked_filter:
        from patients.models import Bookmark
        bookmarked_video_ids = Bookmark.objects.filter(
            bookmark_type="Video"
        ).values_list('object_id', flat=True)
        queryset = queryset.filter(id__in=bookmarked_video_ids)

    # Get total count before pagination
    total_count = queryset.count()

    # Pagination with proper error handling
    paginator = Paginator(queryset, 25)  # Show 25 videos per page
    try:
        page_obj = paginator.get_page(page_number)
    except Exception as e:
        logger.error(f"Pagination error: {str(e)}")
        page_obj = paginator.get_page(1)

    # Get unique uploaders for filter dropdown (users who have uploaded videos)
    from users.models import CustomUser
    uploaders = (
        CustomUser.objects.filter(video_added__isnull=False, **institution_scope(request, 'institution'))
        .distinct()
        .only("id", "username", "first_name", "last_name")
        .order_by("first_name", "last_name")
    )

    # Build context dictionary
    context = {
        "file_list": page_obj,  # Keep for template compatibility
        "videos": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        "uploader_filter": uploader_filter,
        "date_from": date_from,
        "date_to": date_to,
        "bookmarked_filter": bookmarked_filter,
        "uploaders": uploaders,
        "total_count": total_count,
        "page_title": "Video Manager",
        "breadcrumbs": [
            {"name": "Dashboard", "url": reverse("home")},
            {"name": "Video Manager", "url": None},
        ],
    }

    return render(request, "video/manager.html", context)


@login_required(login_url="user-login")
def video_manager_new_only(request):
    """Video manager showing only new videos (not used in assessments)"""
    # Base queryset for new videos only - we need to filter using a subquery
    from patients.models import GMAssessment

    used_video_ids = GMAssessment.objects.values_list('video_file_id', flat=True)
    _inst = getattr(request, 'institution', None)
    _patients_qs = Patient.objects.for_institution(_inst)
    queryset = (
        Video.objects.filter(patient__in=_patients_qs)
        .select_related("patient", "added_by", "last_edit_by")
        .exclude(id__in=used_video_ids)
        .order_by("-recorded_on", "-created_at")
    )

    # Get total count
    total_count = queryset.count()

    # Pagination
    paginator = Paginator(queryset, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Get processing status choices for filter dropdown
    status_choices = PROCESSING_STATUS

    context = {
        "file_list": page_obj,
        "videos": page_obj,
        "status_choices": status_choices,
        "total_count": total_count,
        "page_title": "New Videos Manager",
        "subtitle": "Videos not yet used in assessments",
        "breadcrumbs": [
            {"name": "Dashboard", "url": reverse("home")},
            {"name": "Video Manager", "url": reverse("video:manager")},
            {"name": "New Videos", "url": None},
        ],
    }

    return render(request, "video/manager.html", context)


@login_required(login_url="user-login")
def video_manager_by_patient(request, patient_id):
    """Video manager filtered by specific patient"""
    # Get patient object or 404
    patient = get_object_or_404(Patient.objects.for_institution(getattr(request, 'institution', None)), id=patient_id)

    # Base queryset for specific patient
    _inst = getattr(request, 'institution', None)
    _patients_qs = Patient.objects.for_institution(_inst)
    queryset = (
        Video.objects.select_related("patient", "added_by", "last_edit_by")
        .filter(patient__in=_patients_qs, patient_id=patient_id)
        .order_by("-recorded_on", "-created_at")
    )

    # Get search parameter
    search_query = request.GET.get("search", "").strip()
    if search_query:
        queryset = queryset.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Get status filter
    status_filter = request.GET.get("status", "")
    if status_filter:
        queryset = queryset.filter(processing_status=status_filter)

    # Get total count
    total_count = queryset.count()

    # Pagination
    paginator = Paginator(queryset, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Get processing status choices for filter dropdown
    status_choices = PROCESSING_STATUS

    context = {
        "file_list": page_obj,
        "videos": page_obj,
        "patient": patient,
        "search_query": search_query,
        "status_filter": status_filter,
        "status_choices": status_choices,
        "total_count": total_count,
        "page_title": f"Videos for {patient.baby_name}",
        "subtitle": f"Disk No: {patient.disk_no or 'N/A'}",
        "breadcrumbs": [
            {"name": "Dashboard", "url": reverse("home")},
            {"name": "Patient Manager", "url": reverse("manage-patients")},
            {
                "name": patient.baby_name,
                "url": reverse("view-patient", args=[patient.id]),
            },
            {"name": "Videos", "url": None},
        ],
    }

    return render(request, "video/manager.html", context)


@handle_view_errors(redirect_url='video:manager', error_message='Error loading delete confirmation')
@login_required(login_url="user-login")
def video_delete_confirm(request, video_id):
    """Video delete confirmation page"""
    try:
        video = get_object_or_404(Video, id=video_id, **institution_scope(request))

        # Check permissions
        if not request.user.is_staff and video.added_by != request.user:
            messages.error(request, "You do not have permission to delete this video.")
            return redirect("video:manager")

        # Check if video is used in assessments
        from patients.models import GMAssessment

        assessments_count = GMAssessment.objects.filter(video_file=video).count()

        context = {
            "video": video,
            "patient": video.patient,
            "assessments_count": assessments_count,
            "can_delete": assessments_count == 0,
        }

        return render(request, "video/delete-confirm.html", context)

    except Video.DoesNotExist:
        messages.error(request, "Video not found.")
        return redirect("video:manager")
    except Exception as e:
        logger.error(f"Error in video_delete_confirm: {str(e)}")
        messages.error(request, "An error occurred while loading the video.")
        return redirect("video:manager")


@handle_view_errors(redirect_url='video:manager', error_message='Error deleting video')
@ratelimit(key='user', rate='5/m', method='DELETE')
@ratelimit(key='ip', rate='10/m', method='DELETE')
@login_required(login_url="user-login")
@require_http_methods(["DELETE"])
def video_delete(request, video_id):
    """
    Unified video deletion endpoint with password verification
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
        # 1. Retrieve video
        video = get_object_or_404(Video, id=video_id, **institution_scope(request))

        # 2. Check permissions
        if not has_delete_permission(request.user, video):
            logger.warning(
                f"Unauthorized deletion attempt: user={request.user.username}, "
                f"entity=Video, id={video_id}"
            )
            return JsonResponse({
                "success": False,
                "error": "Permission denied",
                "message": "You do not have permission to delete this video."
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
                f"entity=Video, id={video_id}"
            )
            return JsonResponse({
                "success": False,
                "error": "Invalid password",
                "message": "Incorrect password. Please try again."
            }, status=401)

        # 4. Check business rules (video used in assessments)
        validation_result = validate_can_delete(video)
        if not validation_result['can_delete']:
            return JsonResponse({
                "success": False,
                "error": "Cannot delete",
                "message": validation_result['reason']
            }, status=400)

        # 5. Store info for logging and response
        video_name = get_entity_display_name(video)
        video_title = video.title or 'Unknown'

        # 6. Delete the video file from storage
        if video.video_file:
            try:
                video.video_file.delete(save=False)
            except Exception as e:
                logger.warning(f"Failed to delete video file: {e}")

        # 7. Perform deletion
        video.delete()

        # 8. Audit log
        logger.info(
            f"Deletion successful: user={request.user.username}, "
            f"entity=Video, name={video_name}, id={video_id}"
        )

        # 9. Return success
        return JsonResponse({
            "success": True,
            "message": f"Video '{video_title}' has been deleted successfully.",
            "redirect_url": get_redirect_url('Video')
        })

    except Exception as e:
        logger.error(
            f"Deletion error: user={request.user.username}, "
            f"entity=Video, id={video_id}, error={str(e)}"
        )
        return JsonResponse({
            "success": False,
            "error": "Server error",
            "message": "An unexpected error occurred. Please try again."
        }, status=500)
