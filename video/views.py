from django.shortcuts import render

# Create your views here.
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
    """Handle the actual video upload and processing"""
    try:
        form = VideoForm(request.POST, request.FILES)
        
        if form.is_valid():
            video = form.save(commit=False)
            video.patient = patient
            video.added_by = request.user
            video.save()
            
            # Determine if compression is needed
            needs_compression = video.file_size > 25 * 1024 * 1024  # 25MB
            
            response_data = {
                'success': True,
                'msg': 'Video uploaded successfully!',
                'f_id': video.id,
                'needs_compression': needs_compression,
                'redirect_url': f'/video/view/{video.id}/' if not needs_compression else f'/video/processing/{video.id}/'
            }
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(response_data)
            else:
                messages.success(request, response_data['msg'])
                return redirect(response_data['redirect_url'])
        else:
            error_msg = 'Please correct the errors below.'
            for field, errors in form.errors.items():
                error_msg += f' {field}: {", ".join(errors)}'
            
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
def video_view(request, video_id):
    """View video details and player"""
    try:
        video = get_object_or_404(Video, id=video_id)
        
        # Check access permissions
        if not video.can_be_accessed_by(request.user):
            messages.error(request, 'You do not have permission to view this video.')
            return redirect('manage-patients')
        
        # Check for bookmarks (if bookmark functionality exists)
        bookmark = None
        # TODO: Implement bookmark checking if needed
        
        context = {
            'file': video,  # Legacy naming for template compatibility
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
                return redirect('video:view', video_id=video.id)
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            form = VideoForm(instance=video)
        
        context = {
            'file': video,  # Legacy naming
            'patient': video.patient,
            'video_form': form,
        }
        
        return render(request, 'video/edit.html', context)
        
    except Video.DoesNotExist:
        messages.error(request, 'Video not found.')
        return redirect('manage-patients')

@login_required(login_url='user-login')
def video_processing_progress(request, video_id):
    """View to show video processing progress"""
    try:
        video = get_object_or_404(Video, id=video_id)
        
        # Check if user has permission to view this video
        if not request.user.is_staff and video.added_by != request.user:
            messages.error(request, 'You do not have permission to view this video.')
            return redirect('manage-patients')
        
        # Calculate compression percentage if both sizes are available
        compression_percentage = None
        space_saved_mb = None
        
        if video.compressed_file_size and video.file_size and video.file_size > 0:
            compression_percentage = round((video.compressed_file_size * 100) / video.file_size)
            space_saved_mb = round((video.file_size - video.compressed_file_size) / (1024 * 1024), 1)
        
        # Calculate processing time if available
        processing_duration = None
        if video.processing_started_at and video.processing_completed_at:
            processing_duration = video.processing_completed_at - video.processing_started_at
        
        context = {
            'video': video,
            'compression_percentage': compression_percentage,
            'space_saved_mb': space_saved_mb,
            'processing_duration': processing_duration,
        }
        
        return render(request, 'video/conversion_progress.html', context)
        
    except Video.DoesNotExist:
        messages.error(request, 'Video not found.')
        return redirect('manage-patients')

@login_required(login_url='user-login')
def video_manager(request):
    """Video manager with pagination and filtering"""
    video_list = Video.objects.select_related('patient', 'added_by').all()
    
    # Apply filters if needed
    search_query = request.GET.get('search')
    if search_query:
        video_list = video_list.filter(
            Q(title__icontains=search_query) |
            Q(patient__baby_name__icontains=search_query) |
            Q(patient__bht__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(video_list, 25)
    page_number = request.GET.get('page')
    file_list = paginator.get_page(page_number)
    
    context = {
        'file_list': file_list,
        'search_query': search_query,
    }
    
    return render(request, 'video/manager.html', context)

@login_required(login_url='user-login')
def video_manager_new_only(request):
    """Show only videos without assessments"""
    video_list = Video.objects.filter(gmassessment__isnull=True).select_related('patient', 'added_by')
    
    paginator = Paginator(video_list, 25)
    page_number = request.GET.get('page')
    file_list = paginator.get_page(page_number)
    
    context = {
        'file_list': file_list,
        'patient': '',
    }
    
    return render(request, 'video/manager.html', context)

@login_required(login_url='user-login')
def video_manager_by_patient(request, patient_id):
    """Show videos for specific patient"""
    try:
        patient = get_object_or_404(Patient, id=patient_id)
        video_list = Video.objects.filter(patient=patient).select_related('added_by')
        
        paginator = Paginator(video_list, 25)
        page_number = request.GET.get('page')
        file_list = paginator.get_page(page_number)
        
        context = {
            'file_list': file_list,
            'patient': patient,
        }
        
        return render(request, 'video/manager.html', context)
        
    except Patient.DoesNotExist:
        messages.error(request, 'Patient not found.')
        return redirect('manage-patients')

@login_required(login_url='user-login')
def video_delete_confirm(request, video_id):
    """Show video deletion confirmation"""
    try:
        video = get_object_or_404(Video, id=video_id)
        
        # Check permissions
        if not request.user.is_staff and video.added_by != request.user:
            messages.error(request, 'You do not have permission to delete this video.')
            return redirect('manage-patients')
        
        context = {
            'file': video,  # Legacy naming
        }
        
        return render(request, 'video/delete-confirm.html', context)
        
    except Video.DoesNotExist:
        messages.error(request, 'Video not found.')
        return redirect('manage-patients')

@login_required(login_url='user-login')
@require_http_methods(["POST"])
def video_delete(request, video_id):
    """Delete video and associated files"""
    try:
        video = get_object_or_404(Video, id=video_id)
        
        # Check permissions
        if not request.user.is_staff and video.added_by != request.user:
            messages.error(request, 'You do not have permission to delete this video.')
            return redirect('manage-patients')
        
        patient_id = video.patient.id
        
        # Delete associated files
        if video.original_video:
            video.original_video.delete(save=False)
        if video.compressed_video:
            video.compressed_video.delete(save=False)
        if video.thumbnail:
            video.thumbnail.delete(save=False)
        
        # Delete the video record
        video.delete()
        
        messages.success(request, 'Video deleted successfully.')
        return redirect('patients:view', pk=patient_id)
        
    except Video.DoesNotExist:
        messages.error(request, 'Video not found.')
        return redirect('manage-patients')