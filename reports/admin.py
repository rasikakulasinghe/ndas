from django.contrib import admin
from .models import ReportTemplate, ReportConfig


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    """Admin interface for Report Templates"""

    list_display = ['name', 'is_active', 'is_default', 'created_at', 'added_by']
    list_filter = ['is_active', 'is_default', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'added_by', 'last_edit_by']

    fieldsets = (
        ('Template Information', {
            'fields': ('name', 'description')
        }),
        ('Header and Footer Content', {
            'fields': ('header_text', 'footer_text', 'logo'),
            'description': 'Configure the header and footer content for reports'
        }),
        ('Settings', {
            'fields': ('is_active', 'is_default')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'added_by', 'last_edit_by'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReportConfig)
class ReportConfigAdmin(admin.ModelAdmin):
    """Admin interface for Report Configuration"""

    list_display = ['key', 'value', 'value_type', 'updated_at']
    list_filter = ['value_type', 'created_at']
    search_fields = ['key', 'description']
    readonly_fields = ['created_at', 'updated_at', 'added_by', 'last_edit_by']

    fieldsets = (
        ('Configuration', {
            'fields': ('key', 'value', 'value_type', 'description')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'added_by', 'last_edit_by'),
            'classes': ('collapse',)
        }),
    )
