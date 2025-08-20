from django.contrib import admin
from .models import CustomUser, DeveloperContacts, UserActivityLog, UserSession
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

class CustomUserAdmin(UserAdmin):
    list_display = (
        'username',
        'position',
        'first_name',
        'last_name',
        'email',
        'email_verified_status',
        'mobile_primary',
        'is_active',
        'date_joined',
    )
    list_filter = ('position', 'is_active', 'is_staff', 'is_email_verified', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'mobile_primary')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {
            'fields': ('first_name', 'last_name', 'email', 'position', 'profile_picture')
        }),
        ('Email Verification', {
            'fields': (
                'is_email_verified', 'email_verified_at', 
                'email_verification_token', 'email_verification_sent_at'
            ),
            'classes': ('collapse',)
        }),
        ('Contact Information', {
            'fields': (
                'mobile_primary', 'mobile_secondary', 
                'landline_primary', 'landline_secondary',
                'home_address', 'station_address'
            )
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')
        }),
        ('Additional Information', {
            'fields': ('last_login_device', 'additional_notes'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('last_login', 'date_joined', 'created_at', 'updated_at', 'email_verified_at', 'email_verification_sent_at')
    
    def email_verified_status(self, obj):
        if obj.is_email_verified:
            return format_html('<span style="color: green;">✓ Verified</span>')
        else:
            return format_html('<span style="color: red;">✗ Not Verified</span>')
    email_verified_status.short_description = 'Email Status'
    
@admin.register(DeveloperContacts)
class DeveloperContactsAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'mobile_phone', 'created_at')
    search_fields = ('name', 'email')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'logo', 'qualifications', 'email')
        }),
        ('Contact Details', {
            'fields': ('mobile_phone', 'landline_phone', 'whatsapp_number')
        }),
        ('Social Media', {
            'fields': ('facebook_url', 'twitter_url', 'youtube_url', 'website_url'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        'user_display',
        'login_status',
        'ip_address',
        'device_type',
        'browser_name',
        'operating_system',
        'location_display',
        'login_timestamp',
        'session_duration',
    )
    list_filter = (
        'login_status',
        'device_type',
        'browser_name',
        'operating_system',
        'is_mobile',
        'is_tablet',
        'is_pc',
        'is_bot',
        'login_timestamp',
    )
    search_fields = (
        'user__username',
        'user__email',
        'attempted_username',
        'ip_address',
        'browser_name',
        'operating_system',
        'country',
        'city',
    )
    readonly_fields = (
        'user',
        'login_status',
        'attempted_username',
        'ip_address',
        'user_agent',
        'browser_name',
        'browser_version',
        'operating_system',
        'device_type',
        'device_brand',
        'device_model',
        'is_mobile',
        'is_tablet',
        'is_touch_capable',
        'is_pc',
        'is_bot',
        'country',
        'city',
        'latitude',
        'longitude',
        'session_key',
        'login_timestamp',
        'logout_timestamp',
        'session_duration',
        'failed_login_reason',
        'data_retention_date',
    )
    ordering = ('-login_timestamp',)
    date_hierarchy = 'login_timestamp'
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'attempted_username', 'login_status', 'failed_login_reason')
        }),
        ('Device Information', {
            'fields': (
                'ip_address', 'user_agent', 'browser_name', 'browser_version',
                'operating_system', 'device_type', 'device_brand', 'device_model'
            )
        }),
        ('Device Capabilities', {
            'fields': ('is_mobile', 'is_tablet', 'is_touch_capable', 'is_pc', 'is_bot'),
            'classes': ('collapse',)
        }),
        ('Location Information', {
            'fields': ('country', 'city', 'latitude', 'longitude'),
            'classes': ('collapse',)
        }),
        ('Session Information', {
            'fields': ('session_key', 'login_timestamp', 'logout_timestamp', 'session_duration')
        }),
        ('Privacy & Compliance', {
            'fields': ('data_retention_date',),
            'classes': ('collapse',)
        }),
    )
    
    def user_display(self, obj):
        if obj.user:
            return obj.user.username
        return obj.attempted_username
    user_display.short_description = 'User'
    
    def location_display(self, obj):
        if obj.city and obj.country:
            return f"{obj.city}, {obj.country}"
        return obj.country or "Unknown"
    location_display.short_description = 'Location'
    
    def has_add_permission(self, request):
        return False  # Prevent manual creation of activity logs
    
    def has_change_permission(self, request, obj=None):
        return False  # Prevent editing of activity logs
    
    actions = ['cleanup_old_records']
    
    def cleanup_old_records(self, request, queryset):
        # Allow cleanup of old records for privacy compliance
        cutoff_date = timezone.now() - timedelta(days=90)
        count = queryset.filter(login_timestamp__lt=cutoff_date).count()
        queryset.filter(login_timestamp__lt=cutoff_date).delete()
        self.message_user(request, f"Cleaned up {count} old activity records.")
    cleanup_old_records.short_description = "Cleanup old records (90+ days)"


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'device_summary',
        'ip_address',
        'is_active',
        'created_at',
        'last_activity',
        'session_duration_display',
    )
    list_filter = (
        'is_active',
        'created_at',
        'last_activity',
    )
    search_fields = (
        'user__username',
        'user__email',
        'ip_address',
        'device_summary',
        'session_key',
    )
    readonly_fields = (
        'user',
        'session_key',
        'ip_address',
        'user_agent',
        'device_summary',
        'created_at',
        'last_activity',
    )
    ordering = ('-last_activity',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Session Information', {
            'fields': ('user', 'session_key', 'is_active')
        }),
        ('Device Information', {
            'fields': ('ip_address', 'user_agent', 'device_summary')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_activity')
        }),
    )
    
    def session_duration_display(self, obj):
        if obj.created_at and obj.last_activity:
            duration = obj.last_activity - obj.created_at
            hours = duration.total_seconds() // 3600
            minutes = (duration.total_seconds() % 3600) // 60
            return f"{int(hours)}h {int(minutes)}m"
        return "Unknown"
    session_duration_display.short_description = 'Duration'
    
    def has_add_permission(self, request):
        return False  # Prevent manual creation of sessions
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser  # Only allow superusers to modify sessions
    
    actions = ['deactivate_sessions', 'cleanup_expired_sessions']
    
    def deactivate_sessions(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {count} sessions.")
    deactivate_sessions.short_description = "Deactivate selected sessions"
    
    def cleanup_expired_sessions(self, request, queryset):
        cutoff_date = timezone.now() - timedelta(days=30)
        count = queryset.filter(last_activity__lt=cutoff_date).count()
        queryset.filter(last_activity__lt=cutoff_date).delete()
        self.message_user(request, f"Cleaned up {count} expired sessions.")
    cleanup_expired_sessions.short_description = "Cleanup expired sessions (30+ days)"


# Register your models here.
admin.site.register(CustomUser, CustomUserAdmin)
