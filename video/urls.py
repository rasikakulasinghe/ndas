from django.urls import path
from . import views

app_name = "video"

urlpatterns = [
    path("manager/", views.video_manager, name="video-manager"),
    path("add/<int:patient_id>/", views.video_add, name="video-add"),
    path("view/<int:video_id>/", views.video_view, name="video-view"),
    path("edit/<int:video_id>/", views.video_edit, name="video-edit"),
    path("delete/<int:video_id>/", views.video_delete, name="video-delete"),
    path("delete-confirm/<int:video_id>/", views.video_delete_confirm, name="video-delete-confirm"),
]