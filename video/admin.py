from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    """
    Enhanced admin interface for Video model with better organization and display.
    """
    
    list_display = [
        'title',
        'patient_link',
        'recorded_on',
        'duration_formatted',
        'file_size_display',
        'processing_status_display',
        'is_assessment_ready',
        'created_at',
    ]
    
    list_filter = [
        'processing_status',
        'is_assessment_ready',
        'recorded_on',
        'created_at',
        ('patient', admin.RelatedOnlyFieldListFilter),
    ]
    
    search_fields = [
        'title',
        'patient__name_baby',
        'patient__name_mother',
        'patient__bht',
        'description',
    ]
    
    readonly_fields = [
        'file_size_bytes',
        'duration_seconds',
        'width',
        'height',
        'age_on_recording_display',
        'file_info_display',
        'created_at',
        'updated_at',
        'added_by',
        'last_edit_by',
    ]
    
    fieldsets = [
        ('Basic Information', {
            'fields': (
                'title',
                'patient',
                'recorded_on',
                'description',
            )
        }),
        ('Video File', {
            'fields': (
                'video_file',
                'file_info_display',
            )
        }),
        ('Processing & Status', {
            'fields': (
                'processing_status',
                'is_assessment_ready',
                'duration_seconds',
                'width',
                'height',
            )
        }),
        ('Computed Information', {
            'classes': ('collapse',),
            'fields': (
                'age_on_recording_display',
                'file_size_bytes',
            )
        }),
        ('Audit Trail', {
            'classes': ('collapse',),
            'fields': (
                'created_at',
                'updated_at',
                'added_by',
                'last_edit_by',
            )
        }),
    ]
    
    ordering = ['-recorded_on', '-created_at']
    date_hierarchy = 'recorded_on'
    
    actions = [
        'mark_as_assessment_ready',
        'mark_as_processing_pending',
        'mark_as_processing_failed',
    ]
    
    def patient_link(self, obj):
        """Display patient as a clickable link."""
        if obj.patient:
            url = reverse('admin:patients_patient_change', args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, str(obj.patient))
        return '-'
    patient_link.short_description = 'Patient'
    patient_link.admin_order_field = 'patient__name_baby'
    
    def file_size_display(self, obj):
        """Display file size in human readable format."""
        if obj.file_size_mb:
            if obj.file_size_mb > 1000:
                return f"{obj.file_size_mb / 1000:.1f} GB"
            return f"{obj.file_size_mb} MB"
        return '-'
    file_size_display.short_description = 'File Size'
    file_size_display.admin_order_field = 'file_size_bytes'
    
    def processing_status_display(self, obj):
        """Display processing status with color coding."""
        colors = {
            'pending': '#ffa500',  # orange
            'processing': '#0066cc',  # blue
            'completed': '#28a745',  # green
            'failed': '#dc3545',  # red
        }
        color = colors.get(obj.processing_status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_processing_status_display()
        )
    processing_status_display.short_description = 'Processing Status'
    processing_status_display.admin_order_field = 'processing_status'
    
    def age_on_recording_display(self, obj):
        """Display patient age at recording time."""
        return obj.age_on_recording or '-'
    age_on_recording_display.short_description = 'Age at Recording'
    
    def file_info_display(self, obj):
        """Display comprehensive file information."""
        if not obj.video_file:
            return 'No file uploaded'
            
        info_parts = []
        
        # File name
        info_parts.append(f"<strong>File:</strong> {obj.video_file.name}")
        
        # File size
        if obj.file_size_mb:
            info_parts.append(f"<strong>Size:</strong> {obj.file_size_display()}")
        
        # Duration
        if obj.duration_seconds:
            info_parts.append(f"<strong>Duration:</strong> {obj.duration_formatted}")
            
        # Resolution
        if obj.width and obj.height:
            info_parts.append(f"<strong>Resolution:</strong> {obj.resolution}")
            
        # Extension
        if obj.file_extension:
            info_parts.append(f"<strong>Format:</strong> {obj.file_extension.upper()}")
        
        return mark_safe('<br>'.join(info_parts))
    file_info_display.short_description = 'File Information'
    
    # Admin actions
    def mark_as_assessment_ready(self, request, queryset):
        """Mark selected videos as ready for assessment."""
        updated = queryset.update(is_assessment_ready=True, processing_status='completed')
        self.message_user(
            request, 
            f'{updated} video(s) marked as assessment ready.'
        )
    mark_as_assessment_ready.short_description = 'Mark as assessment ready'
    
    def mark_as_processing_pending(self, request, queryset):
        """Mark selected videos as pending processing."""
        updated = queryset.update(processing_status='pending', is_assessment_ready=False)
        self.message_user(
            request, 
            f'{updated} video(s) marked as pending processing.'
        )
    mark_as_processing_pending.short_description = 'Mark as pending processing'
    
    def mark_as_processing_failed(self, request, queryset):
        """Mark selected videos as processing failed."""
        updated = queryset.update(processing_status='failed', is_assessment_ready=False)
        self.message_user(
            request, 
            f'{updated} video(s) marked as processing failed.'
        )
    mark_as_processing_failed.short_description = 'Mark as processing failed'