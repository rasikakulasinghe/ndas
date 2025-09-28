from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):

    list_display = [
        "title",
        "patient_link",
        "recorded_on",
        "duration_formatted",
        "file_size_display",
        "created_at",
    ]

    list_filter = [
        "recorded_on",
        "created_at",
        ("patient", admin.RelatedOnlyFieldListFilter),
    ]

    search_fields = [
        "title",
        "patient__name_baby",
        "patient__name_mother",
        "patient__bht",
        "description",
    ]

    readonly_fields = [
        "file_size_bytes",
        "duration_seconds",
        "age_on_recording_display",
        "file_info_display",
        "created_at",
        "updated_at",
        "added_by",
        "last_edit_by",
    ]

    fieldsets = [
        (
            "Basic Information",
            {
                "fields": (
                    "title",
                    "patient",
                    "recorded_on",
                    "description",
                )
            },
        ),
        (
            "Video File",
            {
                "fields": (
                    "video_file",
                    "file_info_display",
                )
            },
        ),
        (
            "Computed Information",
            {
                "classes": ("collapse",),
                "fields": (
                    "age_on_recording_display",
                    "file_size_bytes",
                ),
            },
        ),
        (
            "Audit Trail",
            {
                "classes": ("collapse",),
                "fields": (
                    "created_at",
                    "updated_at",
                    "added_by",
                    "last_edit_by",
                ),
            },
        ),
    ]

    ordering = ["-recorded_on", "-created_at"]
    date_hierarchy = "recorded_on"

    def patient_link(self, obj):
        """Display patient as a clickable link."""
        if obj.patient:
            url = reverse("admin:patients_patient_change", args=[obj.patient.pk])
            return format_html('<a href="{}">{}</a>', url, str(obj.patient))
        return "-"

    patient_link.short_description = "Patient"
    patient_link.admin_order_field = "patient__name_baby"

    def file_size_display(self, obj):
        """Display file size in human readable format."""
        if obj.file_size_mb:
            if obj.file_size_mb > 1000:
                return f"{obj.file_size_mb / 1000:.1f} GB"
            return f"{obj.file_size_mb} MB"
        return "-"

    file_size_display.short_description = "File Size"
    file_size_display.admin_order_field = "file_size_bytes"

    def age_on_recording_display(self, obj):
        """Display patient age at recording time."""
        return obj.age_on_recording or "-"

    age_on_recording_display.short_description = "Age at Recording"

    def file_info_display(self, obj):
        """Display comprehensive file information."""
        if not obj.video_file:
            return "No file uploaded"

        info_parts = []

        # File name
        info_parts.append(f"<strong>File:</strong> {obj.video_file.name}")

        # File size
        if obj.file_size_mb:
            info_parts.append(f"<strong>Size:</strong> {obj.file_size_display()}")

        # Duration
        if obj.duration_seconds:
            info_parts.append(f"<strong>Duration:</strong> {obj.duration_formatted}")

        # Extension
        if obj.file_extension:
            info_parts.append(f"<strong>Format:</strong> {obj.file_extension.upper()}")

        return mark_safe("<br>".join(info_parts))

    file_info_display.short_description = "File Information"
