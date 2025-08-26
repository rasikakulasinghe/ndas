from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db import models
from .models import Video
from .utils import format_duration, format_file_size


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'patient_name', 'processing_status_display', 'progress_bar',
        'quality_setting', 'file_size_display', 'duration_display',
        'processing_time_display', 'created_at'
    ]
    
    list_filter = [
        'processing_status', 'target_quality', 'format',
        'created_at', 'processing_started_at', 'processing_completed_at'
    ]
    
    search_fields = [
        'title', 'patient__baby_name', 'patient__nicu_number',
        'description', 'processing_error'
    ]
    
    readonly_fields = [
        'processing_status', 'progress_percentage', 'task_id', 'retry_count',
        'duration_seconds', 'original_resolution', 'original_codec',
        'original_bitrate', 'file_size', 'format', 'processing_time_seconds',
        'compression_ratio', 'processing_metadata', 'processing_started_at',
        'processing_completed_at', 'processing_error'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'patient', 'description', 'recorded_on')
        }),
        ('Files', {
            'fields': ('original_video', 'compressed_video', 'thumbnail'),
            'classes': ('wide',)
        }),
        ('Processing Configuration', {
            'fields': ('target_quality', 'target_resolution', 'target_bitrate'),
            'classes': ('wide',)
        }),
        ('Processing Status', {
            'fields': (
                'processing_status', 'progress_percentage', 'task_id', 'retry_count',
                'processing_started_at', 'processing_completed_at', 'processing_error'
            ),
            'classes': ('wide',)
        }),
        ('Video Metadata', {
            'fields': (
                'duration_seconds', 'original_resolution', 'original_codec',
                'original_bitrate', 'file_size', 'format', 'compression_ratio'
            ),
            'classes': ('collapse', 'wide')
        }),
        ('Processing Metrics', {
            'fields': ('processing_time_seconds', 'processing_metadata'),
            'classes': ('collapse', 'wide')
        }),
    )
    
    actions = ['start_processing', 'cancel_processing', 'retry_processing']
    
    def patient_name(self, obj):
        """Display patient name with link."""
        if obj.patient:
            url = reverse('admin:patients_patient_change', args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, obj.patient.baby_name)
        return '-'
    patient_name.short_description = 'Patient'
    patient_name.admin_order_field = 'patient__baby_name'
    
    def processing_status_display(self, obj):
        """Display processing status with color coding."""
        status = obj.processing_status
        colors = {
            'pending': '#ffc107',      # Yellow
            'uploading': '#17a2b8',    # Info blue
            'processing': '#007bff',   # Primary blue
            'completed': '#28a745',    # Success green
            'failed': '#dc3545',       # Danger red
        }
        color = colors.get(status, '#6c757d')  # Default gray
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, status.title()
        )
    processing_status_display.short_description = 'Status'
    processing_status_display.admin_order_field = 'processing_status'
    
    def progress_bar(self, obj):
        """Display progress bar."""
        if obj.processing_status in ['completed']:
            percentage = 100
            color = '#28a745'  # Green
        elif obj.processing_status == 'failed':
            percentage = obj.progress_percentage
            color = '#dc3545'  # Red
        elif obj.processing_status == 'processing':
            percentage = obj.progress_percentage
            color = '#007bff'  # Blue
        else:
            percentage = 0
            color = '#6c757d'  # Gray
        
        return format_html(
            '<div style="width: 100px; background-color: #f8f9fa; border-radius: 3px; overflow: hidden;">'
            '<div style="width: {}%; height: 20px; background-color: {}; text-align: center; '
            'line-height: 20px; color: white; font-size: 12px; font-weight: bold;">{}</div></div>',
            percentage, color, f'{percentage}%'
        )
    progress_bar.short_description = 'Progress'
    progress_bar.admin_order_field = 'progress_percentage'
    
    def quality_setting(self, obj):
        """Display target quality with description."""
        if obj.target_quality:
            quality_descriptions = {
                'original': 'Original (No compression)',
                'high': 'High (1080p)',
                'medium': 'Medium (720p)',
                'low': 'Low (480p)',
                'mobile': 'Mobile (360p)',
            }
            description = quality_descriptions.get(obj.target_quality, obj.target_quality)
            return f"{obj.target_quality.title()} - {description}"
        return '-'
    quality_setting.short_description = 'Quality'
    quality_setting.admin_order_field = 'target_quality'
    
    def file_size_display(self, obj):
        """Display file size in human readable format."""
        if obj.file_size:
            return format_file_size(obj.file_size)
        return '-'
    file_size_display.short_description = 'File Size'
    file_size_display.admin_order_field = 'file_size'
    
    def duration_display(self, obj):
        """Display video duration in human readable format."""
        if obj.duration_seconds:
            return format_duration(obj.duration_seconds)
        return '-'
    duration_display.short_description = 'Duration'
    duration_display.admin_order_field = 'duration_seconds'
    
    def processing_time_display(self, obj):
        """Display processing time in human readable format."""
        if obj.processing_time_seconds:
            return format_duration(obj.processing_time_seconds)
        return '-'
    processing_time_display.short_description = 'Processing Time'
    processing_time_display.admin_order_field = 'processing_time_seconds'
    
    def start_processing(self, request, queryset):
        """Admin action to start processing selected videos."""
        from .tasks import process_video_task
        
        started_count = 0
        for video in queryset:
            if video.processing_status in ['pending', 'failed']:
                try:
                    task = process_video_task.delay(video.pk)
                    video.task_id = task.id
                    video.processing_status = 'processing'
                    video.processing_started_at = timezone.now()
                    video.save(update_fields=['task_id', 'processing_status', 'processing_started_at'])
                    started_count += 1
                except Exception as e:
                    self.message_user(request, f'Failed to start processing for {video.title}: {e}', level='ERROR')
        
        if started_count > 0:
            self.message_user(request, f'Started processing {started_count} video(s).', level='SUCCESS')
        else:
            self.message_user(request, 'No videos were eligible for processing.', level='WARNING')
    
    start_processing.short_description = 'Start processing selected videos'
    
    def cancel_processing(self, request, queryset):
        """Admin action to cancel processing selected videos."""
        cancelled_count = 0
        for video in queryset:
            if video.processing_status == 'processing':
                try:
                    video.cancel_processing()
                    cancelled_count += 1
                except Exception as e:
                    self.message_user(request, f'Failed to cancel processing for {video.title}: {e}', level='ERROR')
        
        if cancelled_count > 0:
            self.message_user(request, f'Cancelled processing {cancelled_count} video(s).', level='SUCCESS')
        else:
            self.message_user(request, 'No videos were being processed.', level='WARNING')
    
    cancel_processing.short_description = 'Cancel processing selected videos'
    
    def retry_processing(self, request, queryset):
        """Admin action to retry processing failed videos."""
        from .tasks import process_video_task
        
        retried_count = 0
        for video in queryset:
            if video.processing_status == 'failed' and video.retry_count < 3:
                try:
                    video.retry_count += 1
                    task = process_video_task.delay(video.pk)
                    video.task_id = task.id
                    video.processing_status = 'processing'
                    video.processing_started_at = timezone.now()
                    video.processing_error = ''
                    video.save(update_fields=[
                        'retry_count', 'task_id', 'processing_status',
                        'processing_started_at', 'processing_error'
                    ])
                    retried_count += 1
                except Exception as e:
                    self.message_user(request, f'Failed to retry processing for {video.title}: {e}', level='ERROR')
        
        if retried_count > 0:
            self.message_user(request, f'Retried processing {retried_count} video(s).', level='SUCCESS')
        else:
            self.message_user(request, 'No videos were eligible for retry.', level='WARNING')
    
    retry_processing.short_description = 'Retry processing failed videos'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('patient')
    
    def has_delete_permission(self, request, obj=None):
        """Restrict deletion of videos being processed."""
        if obj and obj.processing_status == 'processing':
            return False
        return super().has_delete_permission(request, obj)
    
    class Media:
        css = {
            'all': ('admin/css/video_admin.css',)
        }
        js = ('admin/js/video_admin.js',)
