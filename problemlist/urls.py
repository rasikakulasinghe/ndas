from django.urls import path
from problemlist import views

urlpatterns = [
    # Problem CRUD operations
    path("manager/<str:pid>/", views.problem_manager, name='problem-manager'),
    path("add/<str:pid>/", views.problem_add, name='problem-add'),
    path("view/<str:pk>/", views.problem_view, name='problem-view'),
    path("edit/<str:pk>/", views.problem_edit, name='problem-edit'),
    path("delete/<str:pk>/", views.problem_delete, name='problem-delete'),

    # Status change (HTMX endpoint)
    path("status/<str:pk>/", views.problem_status_change, name='problem-status-change'),

    # Timeline views
    path("timeline/<str:pk>/", views.problem_timeline, name='problem-timeline'),

    # Action logging
    path("action/add/<str:pk>/", views.problem_action_add, name='problem-action-add'),

    # Analysis and export
    path("analysis/", views.problem_analysis, name='problem-analysis'),
    path("analysis/export/", views.problem_analysis_export, name='problem-analysis-export'),
]
