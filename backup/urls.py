from django.urls import path
from backup import views

app_name = 'backup'

urlpatterns = [
    # Story 1.1 — Trigger a full-scope backup of my institution's data.
    path('', views.backup_create, name='backup-create'),
]
