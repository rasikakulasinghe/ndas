from django.urls import path
from . import views
from . import api

app_name = "video"

urlpatterns = [
    # Video management
    path("manager/", views.video_manager, name="manager"),
    path("manager/new/", views.video_manager_new_only, name="manager-new"),
    path(
        "manager/patient/<int:patient_id>/",
        views.video_manager_by_patient,
        name="manager-by-patient",
    ),
    # Video CRUD operations
    path("add/<int:patient_id>/", views.video_add, name="add"),
    path("view/<int:video_id>/", views.video_view, name="view"),
    path("edit/<int:video_id>/", views.video_edit, name="edit"),
    # Video processing
    path(
        "processing/<int:video_id>/",
        views.video_processing_progress,
        name="processing-progress",
    ),
    # Video deletion
    path(
        "delete/confirm/<int:video_id>/",
        views.video_delete_confirm,
        name="delete-confirm",
    ),
    path("delete/<int:video_id>/", views.video_delete, name="delete"),
    
    # API endpoints for video processing
    path("api/status/<int:video_id>/", api.video_processing_status, name="api-status"),
    path("api/start/<int:video_id>/", api.start_video_processing, name="api-start"),
    path("api/cancel/<int:video_id>/", api.cancel_video_processing, name="api-cancel"),
    path("api/estimate/<int:video_id>/", api.video_estimate, name="api-estimate"),
    path("api/queue/status/", api.processing_queue_status, name="api-queue-status"),
    path("api/batch/process/", api.batch_process_videos_api, name="api-batch-process"),
    path("api/statistics/", api.processing_statistics, name="api-statistics"),
]
