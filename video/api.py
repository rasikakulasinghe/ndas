"""
API views for video processing monitoring and control.
"""
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Min, Max
from django.utils import timezone
from datetime import timedelta

from video.models import Video
from video.tasks import process_video_task, batch_process_videos
from video.utils import video_manager, format_duration, format_file_size


@login_required
@require_http_methods(["GET"])
def video_processing_status(request, video_id):
    """Get current processing status for a video."""
    video = get_object_or_404(Video, id=video_id)
    
    # Check if user has permission to view this video
    if not request.user.is_staff and video.patient.created_by != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    status_data = {
        'video_id': video.id,
        'title': video.title,
        'processing_status': video.processing_status,
        'progress_percentage': video.progress_percentage,
        'processing_started_at': video.processing_started_at.isoformat() if video.processing_started_at else None,
        'processing_completed_at': video.processing_completed_at.isoformat() if video.processing_completed_at else None,
        'processing_time_seconds': video.processing_time_seconds,
        'processing_time_formatted': format_duration(video.processing_time_seconds) if video.processing_time_seconds else None,
        'processing_error': video.processing_error,
        'retry_count': video.retry_count,
        'task_id': video.task_id,
    }
    
    # Add Celery task status if task_id exists
    if video.task_id:
        task_status = video.get_task_status()
        if task_status:
            status_data['celery_task'] = task_status
    
    # Add file information
    if video.original_video:
        status_data['original_file'] = {
            'name': video.original_video.name,
            'size': video.file_size,
            'size_formatted': format_file_size(video.file_size) if video.file_size else None,
            'url': video.original_video.url,
        }
    
    if video.compressed_video:
        status_data['compressed_file'] = {
            'name': video.compressed_video.name,
            'url': video.compressed_video.url,
        }
    
    if video.thumbnail:
        status_data['thumbnail'] = {
            'url': video.thumbnail.url,
        }
    
    # Add metadata
    if video.processing_metadata:
        status_data['metadata'] = video.processing_metadata
    
    return JsonResponse(status_data)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def start_video_processing(request, video_id):
    """Start processing a video."""
    video = get_object_or_404(Video, id=video_id)
    
    # Check permissions
    if not request.user.is_staff and video.patient.created_by != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Check if already processing
    if video.processing_status == 'processing':
        return JsonResponse({'error': 'Video is already being processed'}, status=400)
    
    if video.processing_status == 'completed':
        return JsonResponse({'error': 'Video has already been processed'}, status=400)
    
    try:
        # Parse quality setting from request
        data = json.loads(request.body) if request.body else {}
        quality = data.get('quality', video.target_quality or 'medium')
        
        # Update quality if provided
        if quality != video.target_quality:
            video.target_quality = quality
            video.save(update_fields=['target_quality'])
        
        # Start processing
        task = process_video_task.delay(video.id)
        video.task_id = task.id
        video.processing_status = 'processing'
        video.processing_started_at = timezone.now()
        video.save(update_fields=['task_id', 'processing_status', 'processing_started_at'])
        
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'message': 'Video processing started',
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def cancel_video_processing(request, video_id):
    """Cancel video processing."""
    video = get_object_or_404(Video, id=video_id)
    
    # Check permissions
    if not request.user.is_staff and video.patient.created_by != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if video.processing_status != 'processing':
        return JsonResponse({'error': 'Video is not currently being processed'}, status=400)
    
    try:
        video.cancel_processing()
        return JsonResponse({
            'success': True,
            'message': 'Video processing cancelled',
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def processing_queue_status(request):
    """Get status of the video processing queue."""
    # Get queue statistics
    pending_count = Video.objects.filter(processing_status='pending').count()
    processing_count = Video.objects.filter(processing_status='processing').count()
    failed_count = Video.objects.filter(processing_status='failed').count()
    completed_today = Video.objects.filter(
        processing_status='completed',
        processing_completed_at__gte=timezone.now() - timedelta(days=1)
    ).count()
    
    # Get average processing time
    avg_processing_time = Video.objects.filter(
        processing_status='completed',
        processing_time_seconds__isnull=False
    ).aggregate(avg_time=Avg('processing_time_seconds'))['avg_time']
    
    # Get recent processing activity
    recent_videos = Video.objects.filter(
        processing_status__in=['processing', 'completed', 'failed'],
        processing_started_at__gte=timezone.now() - timedelta(hours=24)
    ).select_related('patient').order_by('-processing_started_at')[:10]
    
    recent_activity = []
    for video in recent_videos:
        recent_activity.append({
            'id': video.id,
            'title': video.title,
            'patient': video.patient.baby_name,
            'status': video.processing_status,
            'progress': video.progress_percentage,
            'started_at': video.processing_started_at.isoformat() if video.processing_started_at else None,
            'completed_at': video.processing_completed_at.isoformat() if video.processing_completed_at else None,
        })
    
    # System resources (if available)
    system_resources = video_manager.get_system_resources()
    
    return JsonResponse({
        'queue_stats': {
            'pending': pending_count,
            'processing': processing_count,
            'failed': failed_count,
            'completed_today': completed_today,
        },
        'performance': {
            'average_processing_time': avg_processing_time,
            'average_processing_time_formatted': format_duration(avg_processing_time) if avg_processing_time else None,
        },
        'recent_activity': recent_activity,
        'system_resources': system_resources,
        'timestamp': timezone.now().isoformat(),
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def batch_process_videos_api(request):
    """Start batch processing of videos."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        data = json.loads(request.body) if request.body else {}
        
        # Get parameters
        status = data.get('status', 'pending')
        quality = data.get('quality', 'medium')
        max_videos = min(int(data.get('max_videos', 10)), 50)  # Limit to 50
        
        # Get videos to process
        queryset = Video.objects.filter(processing_status=status)
        
        if status == 'failed':
            # For failed videos, only retry those with low retry count
            queryset = queryset.filter(retry_count__lt=3)
        
        videos = list(queryset[:max_videos])
        
        if not videos:
            return JsonResponse({
                'error': f'No videos found with status: {status}',
            }, status=400)
        
        # Start batch processing
        video_ids = [video.id for video in videos]
        task = batch_process_videos.delay(video_ids, quality)
        
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'video_count': len(video_ids),
            'video_ids': video_ids,
            'quality': quality,
            'message': f'Started batch processing {len(video_ids)} videos',
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def processing_statistics(request):
    """Get detailed processing statistics."""
    # Date range filter
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    # Basic statistics
    total_videos = Video.objects.count()
    processed_in_period = Video.objects.filter(
        processing_completed_at__gte=start_date
    ).count()
    
    # Status breakdown
    status_breakdown = Video.objects.values('processing_status').annotate(
        count=Count('id')
    ).order_by('processing_status')
    
    # Quality breakdown for completed videos
    quality_breakdown = Video.objects.filter(
        processing_status='completed',
        target_quality__isnull=False
    ).values('target_quality').annotate(
        count=Count('id')
    ).order_by('target_quality')
    
    # Processing time statistics
    time_stats = Video.objects.filter(
        processing_status='completed',
        processing_time_seconds__isnull=False,
        processing_completed_at__gte=start_date
    ).aggregate(
        avg_time=Avg('processing_time_seconds'),
        min_time=Min('processing_time_seconds'),
        max_time=Max('processing_time_seconds'),
    )
    
    # Daily processing volume (last 30 days)
    daily_stats = []
    for i in range(min(days, 30)):
        day_start = timezone.now() - timedelta(days=i+1)
        day_end = timezone.now() - timedelta(days=i)
        
        daily_count = Video.objects.filter(
            processing_completed_at__gte=day_start,
            processing_completed_at__lt=day_end,
            processing_status='completed'
        ).count()
        
        daily_stats.append({
            'date': day_start.date().isoformat(),
            'completed_videos': daily_count,
        })
    
    # Error analysis
    recent_errors = Video.objects.filter(
        processing_status='failed',
        processing_error__isnull=False,
        processing_started_at__gte=start_date
    ).values('processing_error').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    return JsonResponse({
        'period_days': days,
        'total_videos': total_videos,
        'processed_in_period': processed_in_period,
        'status_breakdown': list(status_breakdown),
        'quality_breakdown': list(quality_breakdown),
        'processing_time': {
            'average': time_stats['avg_time'],
            'average_formatted': format_duration(time_stats['avg_time']) if time_stats['avg_time'] else None,
            'minimum': time_stats['min_time'],
            'maximum': time_stats['max_time'],
        },
        'daily_stats': daily_stats,
        'recent_errors': list(recent_errors),
        'generated_at': timezone.now().isoformat(),
    })


@login_required
@require_http_methods(["GET"])
def video_estimate(request, video_id):
    """Get processing estimates for a video."""
    video = get_object_or_404(Video, id=video_id)
    
    # Check permissions
    if not request.user.is_staff and video.patient.created_by != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if not video.original_video:
        return JsonResponse({'error': 'No video file found'}, status=400)
    
    try:
        quality = request.GET.get('quality', 'medium')
        estimate = video_manager.get_processing_estimate(
            video.original_video.path, quality
        )
        
        if not estimate:
            return JsonResponse({'error': 'Unable to generate estimate'}, status=500)
        
        # Format the response
        return JsonResponse({
            'video_id': video.id,
            'quality': quality,
            'duration': estimate['duration'],
            'duration_formatted': format_duration(estimate['duration']),
            'original_size': estimate['original_size'],
            'original_size_formatted': format_file_size(estimate['original_size']),
            'estimated_output_size': estimate['estimated_output_size'],
            'estimated_output_size_formatted': format_file_size(estimate['estimated_output_size']),
            'estimated_processing_time': estimate['estimated_processing_time'],
            'estimated_processing_time_formatted': format_duration(estimate['estimated_processing_time']),
            'compression_ratio': estimate['compression_ratio'],
            'quality_preset': estimate['quality_preset'],
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
