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
                video.save()

                # Determine if compression is needed
                needs_compression = (
                    video.file_size_bytes and video.file_size_bytes > 25 * 1024 * 1024
                )

                response_data = {
                    "success": True,
                    "msg": "Video uploaded successfully!",
                    "f_id": video.id,
                    "needs_compression": needs_compression,
                    "redirect_url": reverse(
                        "video:view", kwargs={"video_id": video.id}
                    ),
                }

                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(response_data)
                else:
                    messages.success(request, response_data["msg"])
                    return redirect("video:view", video_id=video.id)

            except ValidationError as e:
                form.add_error(None, e)

        # Form has errors
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            errors = form.errors.as_json()
            return JsonResponse({"success": False, "errors": errors})
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        # GET request - show the upload form
        form = VideoForm()

    context = {
        "patient": patient,
        "today": timezone.now().strftime("%Y%m%d"),
        "video_form": form,
    }
    return render(request, "video/add.html", context)


@login_required(login_url="user-login")
def video_processing_progress(request, video_id):
    """Display video processing progress page"""
    try:
        video = get_object_or_404(Video, id=video_id)

        # Check basic access permissions
        if not request.user.is_staff and video.added_by != request.user:
            messages.error(request, "You don't have permission to access this video.")
            return redirect("manage-patients")

        context = {
            "video": video,
            "patient": video.patient,
            "processing_status": video.processing_status,
            "task_id": getattr(video, "task_id", None),
        }

        return render(request, "video/processing_progress.html", context)

    except Video.DoesNotExist:
        messages.error(request, "Video not found.")
        return redirect("manage-patients")
    except Exception as e:
        logger.error(f"Error in video_processing_progress: {str(e)}")
        messages.error(
            request, "An error occurred while loading the processing status."
        )
        return redirect("manage-patients")


@login_required(login_url="user-login")
@csrf_exempt
@require_http_methods(["GET"])
def video_processing_status_api(request, video_id):
    """API endpoint to check video processing status"""
    try:
        video = get_object_or_404(Video, id=video_id)

        # Get task status if task_id exists
        task_status = None
        task_result = None

        if hasattr(video, "task_id") and video.task_id:
            try:
                from celery.result import AsyncResult

                task = AsyncResult(video.task_id)
                task_status = task.status
                task_result = task.result if task.ready() else None
            except Exception as e:
                logger.error(f"Error getting task status: {e}")

        # Calculate progress based on processing status
        progress_mapping = {
            "pending": 0,
            "processing": 30,
            "extracting_metadata": 20,
            "generating_thumbnails": 40,
            "compressing": 60,
            "finalizing": 90,
            "completed": 100,
            "failed": 0,
        }

        progress = progress_mapping.get(video.processing_status, 0)

        # If task is running and has progress info
        if task_result and isinstance(task_result, dict):
            if "current" in task_result:
                progress = task_result["current"]

        response_data = {
            "video_id": video.id,
            "status": video.processing_status,
            "progress": progress,
            "task_id": getattr(video, "task_id", None),
            "task_status": task_status,
            "error_message": getattr(video, "processing_error", None),
            "is_complete": video.processing_status == "completed",
            "is_failed": video.processing_status == "failed",
            "metadata": {
                "duration": getattr(video, "duration_seconds", None),
                "resolution": getattr(video, "original_resolution", None),
                "codec": getattr(video, "original_codec", None),
                "file_size": getattr(video, "file_size_bytes", None),
            },
        }

        # If processing is complete, add completion details
        if video.processing_status == "completed":
            response_data["redirect_url"] = f"/video/view/{video.id}/"
            response_data["processing_complete"] = True

        return JsonResponse(response_data)

    except Video.DoesNotExist:
        return JsonResponse({"error": "Video not found"}, status=404)
    except Exception as e:
        logger.error(f"Error in video_processing_status_api: {str(e)}")
        return JsonResponse({"error": "Server error"}, status=500)


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

    context = {
        "video": video,
        "patient": video.patient,
        "bookmark": bookmark,
    }

    return render(request, "video/view.html", context)


@login_required(login_url="user-login")
def video_edit(request, video_id):
    """Edit video details"""
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
                updated_video.updated_by = request.user
                updated_video.save()

                messages.success(request, "Video information updated successfully.")
                return redirect("video:view", video_id=video.id)
            except ValidationError as e:
                form.add_error(None, e)
                messages.error(request, "Please correct the errors below.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = VideoForm(instance=video)

    context = {
        "video": video,
        "patient": video.patient,
        "video_form": form,
    }

    return render(request, "video/edit.html", context)


@login_required(login_url="user-login")
@csrf_exempt
@require_http_methods(["POST"])
def trigger_video_processing(request, video_id):
    """Manually trigger video processing"""
    try:
        video = get_object_or_404(Video, id=video_id)

        # Check permissions
        if not request.user.is_staff and video.added_by != request.user:
            return JsonResponse({"error": "Permission denied"}, status=403)

        # Check if already processing
        if video.processing_status == "processing":
            return JsonResponse(
                {"error": "Video is already being processed"}, status=400
            )

        # Start processing
        try:
            video.processing_status = "pending"
            video.save(update_fields=["processing_status"])

            return JsonResponse(
                {"success": True, "message": "Video processing started successfully"}
            )
        except Exception as e:
            logger.error(f"Failed to start video processing: {e}")
            return JsonResponse({"error": "Failed to start processing"}, status=500)

    except Video.DoesNotExist:
        return JsonResponse({"error": "Video not found"}, status=404)


@login_required(login_url="user-login")
def video_manager(request):
    """Enhanced video manager with filtering, search, and pagination"""
    try:
        # Get search and filter parameters
        search_query = request.GET.get("search", "").strip()
        status_filter = request.GET.get("status", "")
        patient_filter = request.GET.get("patient", "")
        date_from = request.GET.get("date_from", "")
        date_to = request.GET.get("date_to", "")

        # Base queryset with related data
        videos = Video.objects.select_related(
            "patient", "added_by", "updated_by"
        ).order_by("-recorded_on", "-created_at")

        # Apply search filter
        if search_query:
            videos = videos.filter(
                Q(title__icontains=search_query)
                | Q(patient__baby_name__icontains=search_query)
                | Q(patient__file_no__icontains=search_query)
                | Q(description__icontains=search_query)
            )

        # Apply status filter
        if status_filter:
            videos = videos.filter(processing_status=status_filter)

        # Apply patient filter
        if patient_filter:
            try:
                patient_id = int(patient_filter)
                videos = videos.filter(patient_id=patient_id)
            except (ValueError, TypeError):
                pass

        # Apply date range filter
        if date_from:
            try:
                from datetime import datetime

                date_from_parsed = datetime.strptime(date_from, "%Y-%m-%d").date()
                videos = videos.filter(recorded_on__date__gte=date_from_parsed)
            except ValueError:
                pass

        if date_to:
            try:
                from datetime import datetime

                date_to_parsed = datetime.strptime(date_to, "%Y-%m-%d").date()
                videos = videos.filter(recorded_on__date__lte=date_to_parsed)
            except ValueError:
                pass

        # Pagination
        paginator = Paginator(videos, 25)  # Show 25 videos per page
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        # Get unique patients for filter dropdown
        patients = (
            Patient.objects.filter(videos__isnull=False)
            .distinct()
            .order_by("baby_name")
        )

        # Get processing status choices for filter dropdown
        status_choices = PROCESSING_STATUS

        context = {
            "file_list": page_obj,  # Keep the same variable name as template expects
            "videos": page_obj,
            "search_query": search_query,
            "status_filter": status_filter,
            "patient_filter": patient_filter,
            "date_from": date_from,
            "date_to": date_to,
            "patients": patients,
            "status_choices": status_choices,
            "total_count": videos.count(),
        }

        return render(request, "video/manager.html", context)

    except Exception as e:
        logger.error(f"Error in video_manager: {str(e)}")
        messages.error(request, "An error occurred while loading the video manager.")
        return render(request, "video/manager.html", {"file_list": []})


@login_required(login_url="user-login")
def video_manager_new_only(request):
    pass


@login_required(login_url="user-login")
def video_manager_by_patient(request, patient_id):
    pass


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
