"""
Enhanced video views with complete upload and processing functionality.
"""

import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden, Http404
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q
from django.urls import reverse
from django.core.exceptions import ValidationError

from patients.models import Patient
from .models import Video
from .forms import VideoForm
from ndas.custom_codes.choice import PROCESSING_STATUS

logger = logging.getLogger(__name__)


@login_required(login_url="user-login")
def video_add(request, patient_id):
    """Enhanced video upload with proper form handling and progress tracking"""
    patient = get_object_or_404(Patient, id=patient_id)

    if request.method == "POST":
        form = VideoForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                video = form.save(commit=False)
                video.patient = patient
                video.added_by = request.user
                
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
    video = get_object_or_404(Video, id=video_id)

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
    except:
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


@login_required(login_url="user-login")
def video_edit(request, video_id):
    """Edit video details with enhanced validation and error handling"""
    video = get_object_or_404(Video, id=video_id)

    # Check permissions
    if not request.user.is_staff and video.added_by != request.user:
        messages.error(request, "You do not have permission to edit this video.")
        return redirect("manage-patients")

    if request.method == "POST":
        form = VideoForm(request.POST, request.FILES, instance=video)

        if form.is_valid():
            try:
                updated_video = form.save(commit=False)
                updated_video.last_edit_by = request.user
                
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
    patient_filter = request.GET.get("patient", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    page_number = request.GET.get("page", 1)

    # Base queryset with optimized related data loading
    queryset = (
        Video.objects.select_related("patient", "added_by", "last_edit_by")
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

    # Apply status filter
    if status_filter:
        queryset = queryset.filter(processing_status=status_filter)

    # Apply patient filter with proper error handling
    if patient_filter:
        try:
            patient_id = int(patient_filter)
            queryset = queryset.filter(patient_id=patient_id)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid patient filter value: {patient_filter}")
            messages.warning(request, "Invalid patient filter. Showing all patients.")

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

    # Get total count before pagination
    total_count = queryset.count()

    # Pagination with proper error handling
    paginator = Paginator(queryset, 25)  # Show 25 videos per page
    try:
        page_obj = paginator.get_page(page_number)
    except Exception as e:
        logger.error(f"Pagination error: {str(e)}")
        page_obj = paginator.get_page(1)

    # Get unique patients for filter dropdown (optimized query)
    patients = (
        Patient.objects.filter(videos__isnull=False)
        .distinct()
        .only("id", "baby_name")
        .order_by("baby_name")
    )

    # Get processing status choices for filter dropdown
    status_choices = PROCESSING_STATUS

    # Build context dictionary
    context = {
        "file_list": page_obj,  # Keep for template compatibility
        "videos": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        "patient_filter": patient_filter,
        "date_from": date_from,
        "date_to": date_to,
        "patients": patients,
        "status_choices": status_choices,
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
    # Base queryset for new videos only
    queryset = (
        Video.objects.select_related("patient", "added_by", "last_edit_by")
        .filter(is_new_file=True)
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
    patient = get_object_or_404(Patient, id=patient_id)

    # Base queryset for specific patient
    queryset = (
        Video.objects.select_related("patient", "added_by", "last_edit_by")
        .filter(patient_id=patient_id)
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
        "subtitle": f"File No: {patient.file_no or 'N/A'}",
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


@login_required(login_url="user-login")
def video_delete_confirm(request, video_id):
    """Video delete confirmation page"""
    try:
        video = get_object_or_404(Video, id=video_id)

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

        return render(request, "video/delete_confirm.html", context)

    except Video.DoesNotExist:
        messages.error(request, "Video not found.")
        return redirect("video:manager")
    except Exception as e:
        logger.error(f"Error in video_delete_confirm: {str(e)}")
        messages.error(request, "An error occurred while loading the video.")
        return redirect("video:manager")


@login_required(login_url="user-login")
@require_http_methods(["POST"])
def video_delete(request, video_id):
    """Delete video after confirmation"""
    try:
        video = get_object_or_404(Video, id=video_id)

        # Check permissions
        if not request.user.is_staff and video.added_by != request.user:
            messages.error(request, "You do not have permission to delete this video.")
            return redirect("video:manager")

        # Check if video is used in assessments
        from patients.models import GMAssessment

        if GMAssessment.objects.filter(video_file=video).exists():
            messages.error(request, "Cannot delete video that is used in assessments.")
            return redirect("video:delete-confirm", video_id=video_id)

        # Store patient info for redirect
        patient_id = video.patient.id
        video_title = video.title

        # Delete the video file from storage
        if video.video_file:
            try:
                video.video_file.delete(save=False)
            except Exception as e:
                logger.warning(f"Failed to delete video file: {e}")

        # Delete the database record
        video.delete()

        messages.success(
            request, f'Video "{video_title}" has been deleted successfully.'
        )

        # Redirect based on referer or default to manager
        referer = request.META.get("HTTP_REFERER", "")
        if "patient" in referer:
            return redirect("view-patient", pk=patient_id)
        else:
            return redirect("video:manager")

    except Video.DoesNotExist:
        messages.error(request, "Video not found.")
        return redirect("video:manager")
    except Exception as e:
        logger.error(f"Error in video_delete: {str(e)}")
        messages.error(request, "An error occurred while deleting the video.")
        return redirect("video:manager")
