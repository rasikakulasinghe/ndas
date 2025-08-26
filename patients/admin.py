from django.contrib import admin
from patients.models import (
    Patient,
    GMAssessment,
    DevelopmentalAssessment,
    IndicationsForGMA,
    DiagnosisList,
    Help,
    Bookmark,
    Attachment,
    CDICRecord,
    HINEAssessment,
)


class PatientsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bht",
        "nnc_no",
        "ptc_no",
        "pin",
        "disk_no",
        "baby_name",
        "gender",
        "dob_tob",
        "address",
    )
    ordering = ("-created_at",)
    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()
    readonly_fields = ()
    fields = (
        "bht",
        "nnc_no",
        "ptc_no",
        "pc_no",
        "pin",
        "disk_no",
        "baby_name",
        "mother_name",
        "pog_wks",
        "pog_days",
        "gender",
        "dob_tob",
        "mo_delivery",
        "apgar_1",
        "apgar_5",
        "apgar_10",
        "resuscitated",
        "resustn_note",
        "birth_weight",
        "length",
        "ofc",
        "address",
        "tp_mobile",
        "tp_lan",
        "problems",
        "indecation_for_gma",
        "antenatal_hx",
        "postnatal_hx",
        "other_relavent_details",
        "added_by",
        "last_edit_by",
    )


class IndicationsForGMAAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "level",
        "description",
    )
    ordering = ("-id",)
    filter_horizontal = ()
    list_filter = ("level",)
    fieldsets = ()
    readonly_fields = ("added_by", "created_at", "last_edit_by", "updated_at")
    fields = (
        "title",
        "level",
        "description",
    )


class GMAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "date_of_assessment",
        "parent_informed",
        "added_by",
        "created_at",
    )
    ordering = ("-id",)
    filter_horizontal = ()
    list_filter = (
        "date_of_assessment",
        "parent_informed",
    )
    fieldsets = ()
    readonly_fields = ("last_edit_by", "updated_at", "added_by", "created_at")
    fields = (
        "patient",
        "video_file",
        "date_of_assessment",
        "diagnosis",
        "diagnosis_other",
        "management_plan",
        "parent_informed",
        "next_assessment_date",
    )


class HelpAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "description",
        "video_1",
        "video_2",
    )
    ordering = ("-id",)
    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()
    readonly_fields = ()
    fields = (
        "title",
        "description",
        "video_1",
        "video_2",
    )


class BookmarkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "description",
        "bookmark_type",
        "owner",
        "created_at",
        "updated_at",
    )
    ordering = ("-id",)
    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()
    readonly_fields = ()
    fields = (
        "title",
        "description",
        "bookmark_type",
        "owner",
        "object_id",
    )


class AttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "title",
        "description",
        "attachment_type",
        "added_by",
        "created_at",
    )
    ordering = ("-id",)
    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()
    readonly_fields = ()
    fields = (
        "title",
        "description",
        "file",
        "attachment_type",
        "patient",
        "added_by",
    )


class CDICRecordAdmin(admin.ModelAdmin):
    list_display = (
        "patient",
        "assessment_date",
        "assessment",
        "assessment_done_by",
        "today_interventions",
        "next_appointment_date",
        "next_appointment_plan",
        "is_discharged",
        "discharged_by",
        "discharge_date",
        "discharge_plan",
        "added_by",
        "created_at",
        "last_edit_by",
        "updated_at",
    )
    ordering = ("-id",)
    filter_horizontal = ()
    list_filter = ("is_discharged", "assessment_date", "discharge_date")
    fieldsets = ()
    readonly_fields = ("created_at", "updated_at", "added_by", "last_edit_by")
    fields = (
        "patient",
        "assessment_date",
        "assessment",
        "assessment_done_by",
        "today_interventions",
        "next_appointment_date",
        "next_appointment_plan",
        "is_discharged",
        "discharged_by",
        "discharge_date",
        "discharge_plan",
    )


class HINEAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "patient",
        "date_of_assessment",
        "score",
        "assessment_done_by",
        "comment",
        "added_by",
        "created_at",
        "last_edit_by",
        "updated_at",
    )
    ordering = ("-id",)
    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()
    readonly_fields = ()
    fields = (
        "patient",
        "date_of_assessment",
        "score",
        "assessment_done_by",
        "comment",
        "added_by",
    )


class DevelopmentalAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "patient",
        "date_of_assessment",
        "is_dx_normal",
        "assessment_done_by",
        "comment",
        "added_by",
        "created_at",
    )
    ordering = ("-id",)
    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()
    readonly_fields = ()
    fields = (
        "patient",
        "date_of_assessment",
        "assessment_done_by",
        "gm_age_from",
        "gm_age_to",
        "gm_details",
        "fmv_age_from",
        "fmv_age_to",
        "fmv_details",
        "hsl_age_from",
        "hsl_age_to",
        "hsl_details",
        "seb_age_from",
        "seb_age_to",
        "seb_details",
        "comment",
        "added_by",
    )


# Register your models here.
admin.site.register(Patient, PatientsAdmin)
admin.site.register(DiagnosisList)
admin.site.register(IndicationsForGMA, IndicationsForGMAAdmin)
admin.site.register(GMAssessment, GMAssessmentAdmin)
admin.site.register(Help, HelpAdmin)
admin.site.register(Bookmark, BookmarkAdmin)
admin.site.register(Attachment, AttachmentAdmin)
admin.site.register(CDICRecord, CDICRecordAdmin)
admin.site.register(HINEAssessment, HINEAssessmentAdmin)
admin.site.register(DevelopmentalAssessment, DevelopmentalAssessmentAdmin)
