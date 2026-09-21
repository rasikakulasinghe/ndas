from django.urls import path
from backup import views

app_name = 'backup'

urlpatterns = [
    # Story 1.1 — Trigger a full-scope backup of my institution's data.
    path('', views.backup_create, name='backup-create'),
    # Story 1.5 — HTMX-polled "Recent Backup Jobs" fragment.
    path('status/', views.backup_status, name='backup-status'),
    # Story 2.1 - Upload and validate a restore archive (super admin only).
    path('restore/', views.restore_upload, name='restore-upload'),
    path('restore/<int:pk>/', views.restore_status, name='restore-status'),
    path('restore/<int:pk>/status/', views.restore_status_fragment, name='restore-status-fragment'),
    # Story 2.2 - Restore preview, confirmation and cancel (super admin only).
    path('restore/<int:pk>/preview/', views.restore_preview, name='restore-preview'),
    path('restore/<int:pk>/confirm/', views.restore_confirm, name='restore-confirm'),
    path('restore/<int:pk>/cancel/', views.restore_cancel, name='restore-cancel'),
]
