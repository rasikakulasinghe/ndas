from django.contrib import admin
from referral.models import ReferralSent, ReferralReceived, ReferralMessage


@admin.register(ReferralSent)
class ReferralSentAdmin(admin.ModelAdmin):
    list_display = ['referral_uuid', 'from_institution', 'to_institution', 'status', 'created_at']
    list_filter = ['status', 'from_institution']
    readonly_fields = ['referral_uuid']


@admin.register(ReferralReceived)
class ReferralReceivedAdmin(admin.ModelAdmin):
    list_display = ['referral_uuid', 'from_institution', 'to_institution', 'status', 'created_at']
    list_filter = ['status', 'to_institution']
    readonly_fields = ['referral_uuid']


@admin.register(ReferralMessage)
class ReferralMessageAdmin(admin.ModelAdmin):
    list_display = ['referral_uuid', 'sender', 'message_type', 'created_at']
    readonly_fields = ['referral_uuid']
