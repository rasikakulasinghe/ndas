"""
Enhanced video views with complete upload and processing functionality.
"""
import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q

from patients.models import Patient
from .models import Video
from .forms import VideoForm

logger = logging.getLogger(__name__)

@login_required(login_url='user-login')
def video_add(request, patient_id):
    """Enhanced video upload with proper form handling and progress tracking"""
    try:
        patient = get_object_or_404(Patient, id=patient_id)
    except Patient.DoesNotExist:
        messages.error(request, 'Patient not found.')
        return redirect('manage-patients')
    
    if request.method == 'POST':
        return handle_video_upload(request, patient)
    else:
        # GET request - show the upload form
        context = {
            'patient': patient,
            'today': timezone.now().strftime('%Y%m%d'),
            'video_form': VideoForm(),
        }
        return render(request, 'video/add.html', context)

def handle_video_upload(request, patient):
    """Enhanced video upload handler with full form field support"""
    try:
        form = VideoForm(request.POST, request.FILES)
        
        if form.is_valid():
            video = form.save(commit=False)
            video.patient = patient
            video.added_by = request.user
            
            video.save()
            
            # Determine if compression is needed
            needs_compression = video.file_size and video.file_size > 25 * 1024 * 1024  # 25MB
            
            # Start processing for large files or if requested
            if needs_compression:
                try:
                    # Trigger processing by updating status
                    video.processing_status = 'pending'
                    video.save(update_fields=['processing_status'])
                    logger.info(f"Video {video.id} queued for processing")
                except Exception as e:
                    logger.error(f"Failed to queue video processing: {e}")
            
            response_data = {
                'success': True,
                'msg': 'Video uploaded successfully!',
                'f_id': video.id,
                'needs_compression': needs_compression,
                'redirect_url': f'/video/process/{video.id}/' if needs_compression else f'/video/view/{video.id}/'
            }
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(response_data)
            else:
                messages.success(request, response_data['msg'])
                return redirect(response_data['redirect_url'])
        else:
            error_msg = 'Please correct the errors below.'
            for field, errors in form.errors.items():
                error_msg += f' {field}: {", ".join([str(e) for e in errors])}'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'msg': error_msg})
            else:
                messages.error(request, error_msg)
                return render(request, 'video/add.html', {
                    'patient': patient,
                    'video_form': form,
                })
    
    except Exception as e:
        logger.error(f"Error in handle_video_upload: {str(e)}")
        error_msg = 'An error occurred while uploading the video. Please try again.'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'msg': error_msg})
        else:
            messages.error(request, error_msg)
            return redirect('manage-patients')

@login_required(login_url='user-login')
def video_processing_progress(request, video_id):
    """Display video processing progress page"""
    try:
        video = get_object_or_404(Video, id=video_id)
        
        # Check basic access permissions
        if not request.user.is_staff and video.added_by != request.user:
            messages.error(request, "You don't have permission to access this video.")
            return redirect('manage-patients')
        
        context = {
            'video': video,
            'patient': video.patient,
            'processing_status': video.processing_status,
            'task_id': getattr(video, 'task_id', None),
        }
        
        return render(request, 'video/processing_progress.html', context)
        
    except Video.DoesNotExist:
        messages.error(request, 'Video not found.')
        return redirect('manage-patients')
    except Exception as e:
        logger.error(f"Error in video_processing_progress: {str(e)}")
        messages.error(request, 'An error occurred while loading the processing status.')
        return redirect('manage-patients')

@login_required(login_url='user-login') 
@csrf_exempt
@require_http_methods(["GET"])
def video_processing_status_api(request, video_id):
    """API endpoint to check video processing status"""
    try:
        video = get_object_or_404(Video, id=video_id)
        
        # Get task status if task_id exists
        task_status = None
        task_result = None
        
        if hasattr(video, 'task_id') and video.task_id:
            try:
                from celery.result import AsyncResult
                task = AsyncResult(video.task_id)
                task_status = task.status
                task_result = task.result if task.ready() else None
            except Exception as e:
                logger.error(f"Error getting task status: {e}")
        
        # Calculate progress based on processing status
        progress_mapping = {
            'pending': 0,
            'processing': 30,
            'extracting_metadata': 20,
            'generating_thumbnails': 40,
            'compressing': 60,
            'finalizing': 90,
            'completed': 100,
            'failed': 0,
        }
        
        progress = progress_mapping.get(video.processing_status, 0)
        
        # If task is running and has progress info
        if task_result and isinstance(task_result, dict):
            if 'current' in task_result:
                progress = task_result['current']
        
        response_data = {
            'video_id': video.id,
            'status': video.processing_status,
            'progress': progress,
            'task_id': getattr(video, 'task_id', None),
            'task_status': task_status,
            'error_message': getattr(video, 'processing_error', None),
            'is_complete': video.processing_status == 'completed',
            'is_failed': video.processing_status == 'failed',
            'metadata': {
                'duration': getattr(video, 'duration_seconds', None),
                'resolution': getattr(video, 'original_resolution', None),
                'codec': getattr(video, 'original_codec', None),
                'file_size': getattr(video, 'file_size', None),
            }
        }
        
        # If processing is complete, add completion details
        if video.processing_status == 'completed':
            response_data['redirect_url'] = f'/video/view/{video.id}/'
            if hasattr(video, 'compressed_video') and video.compressed_video:
                response_data['compressed_available'] = True
        
        return JsonResponse(response_data)
        
    except Video.DoesNotExist:
        return JsonResponse({'error': 'Video not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in video_processing_status_api: {str(e)}")
        return JsonResponse({'error': 'Server error'}, status=500)

@login_required(login_url='user-login')
def video_view(request, video_id):
    """View video details and player"""
    try:
        video = get_object_or_404(Video, id=video_id)
        
        # Check access permissions
        if not request.user.is_staff and video.added_by != request.user:
            messages.error(request, 'You do not have permission to view this video.')
            return redirect('manage-patients')
        
        # Check for existing bookmark
        from patients.models import Bookmark
        try:
            bookmark = Bookmark.objects.get(
                object_id=video.id,
                bookmark_type='Video',
                added_by=request.user
            )
        except Bookmark.DoesNotExist:
            bookmark = None
        
        context = {
            'video': video,
            'patient': video.patient,
            'bookmark': bookmark,
        }
        
        return render(request, 'video/view.html', context)
        
    except Video.DoesNotExist:
        messages.error(request, 'Video not found.')
        return redirect('manage-patients')
    except Exception as e:
        logger.error(f"Error in video_view: {str(e)}")
        messages.error(request, 'An error occurred while loading the video.')
        return redirect('manage-patients')

@login_required(login_url='user-login')
def video_edit(request, video_id):
    """Edit video details"""
    try:
        video = get_object_or_404(Video, id=video_id)
        
        # Check permissions
        if not request.user.is_staff and video.added_by != request.user:
            messages.error(request, 'You do not have permission to edit this video.')
            return redirect('manage-patients')
        
        if request.method == 'POST':
            form = VideoForm(request.POST, request.FILES, instance=video)
            
            if form.is_valid():
                updated_video = form.save(commit=False)
                updated_video.last_edit_by = request.user
                updated_video.save()
                
                messages.success(request, 'Video information updated successfully.')
                return redirect(f'/video/view/{video.id}/')
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            form = VideoForm(instance=video)
        
        context = {
            'video': video,
            'patient': video.patient,
            'video_form': form,
        }
        
        return render(request, 'video/edit.html', context)
        
    except Video.DoesNotExist:
        messages.error(request, 'Video not found.')
        return redirect('manage-patients')

@login_required(login_url='user-login')
@csrf_exempt
@require_http_methods(["POST"])
def trigger_video_processing(request, video_id):
    """Manually trigger video processing"""
    try:
        video = get_object_or_404(Video, id=video_id)
        
        # Check permissions
        if not request.user.is_staff and video.added_by != request.user:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Check if already processing
        if video.processing_status == 'processing':
            return JsonResponse({'error': 'Video is already being processed'}, status=400)
        
        # Start processing
        try:
            video.processing_status = 'pending'
            video.save(update_fields=['processing_status'])
            
            return JsonResponse({
                'success': True,
                'message': 'Video processing started successfully'
            })
        except Exception as e:
            logger.error(f"Failed to start video processing: {e}")
            return JsonResponse({'error': 'Failed to start processing'}, status=500)
            
    except Video.DoesNotExist:
        return JsonResponse({'error': 'Video not found'}, status=404)

# Legacy views for compatibility - you can add these based on existing functionality
@login_required(login_url='user-login')
def video_manager(request):
    """Video manager view - placeholder"""
    return redirect('manage-patients')

@login_required(login_url='user-login')
def video_manager_new_only(request):
    """Video manager new only view - placeholder"""
    return redirect('manage-patients')

@login_required(login_url='user-login')
def video_manager_by_patient(request, patient_id):
    """Video manager by patient view - placeholder"""
    return redirect('view-patient', patient_id=patient_id)

@login_required(login_url='user-login')
def video_delete_confirm(request, video_id):
    """Video delete confirmation view - placeholder"""
    return redirect('manage-patients')

@login_required(login_url='user-login')
def video_delete(request, video_id):
    """Video delete view - placeholder"""
    return redirect('manage-patients')
