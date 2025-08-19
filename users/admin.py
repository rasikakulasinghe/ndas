from django.contrib import admin
from .models import CustomUser, DevoloperContacts
from django.contrib.auth.admin import UserAdmin

class CustomUserAdmin(UserAdmin):
    list_display = (
        'username',
        'possition',
        'first_name',
        'email',
    )
    ordering = ('-date_joined', )
    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()
    readonly_fields = ('last_login', 'date_joined',)
    fields = ('username', 'email', 'possition', 'first_name', 'last_name', 'tp_mobile_1', 'tp_lan_1', 'tp_mobile_2', 'tp_lan_2', 'address_station', 'profile_pic', 'other',
    'user_permissions', 'groups', 'is_superuser', 'is_staff', 'is_active', 'last_login', 'last_login_device', 'date_joined')

# Register your models here.
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(DevoloperContacts)
