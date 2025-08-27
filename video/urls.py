from django.urls import path
from . import views

app_name = "video"

urlpatterns = [
    path("manager/", views.video_manager, name="manager"),
    path("manager/patient/<int:patient_id>/", views.video_manager_by_patient, name="manager-by-patient"),
    path("manager/new/", views.video_manager_new_only, name="manager-new-only"),
    path("add/<int:patient_id>/", views.video_add, name="add"),
    path("view/<int:video_id>/", views.video_view, name="view"),
    path("edit/<int:video_id>/", views.video_edit, name="edit"),
    path("delete/<int:video_id>/", views.video_delete, name="delete"),
    path("delete-confirm/<int:video_id>/", views.video_delete_confirm, name="delete-confirm"),
]