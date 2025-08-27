from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    pass