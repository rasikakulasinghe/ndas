from django.urls import path
from institution import views

app_name = 'institution'

urlpatterns = [
    # Story 2.1 — Institution Selector Screen (SUPERADMIN god-view)
    path('', views.institution_selector, name='institution-selector'),

    # Story 2.2 — Context Switching (POST only)
    path('switch/<int:institution_id>/', views.institution_switch, name='institution-switch'),

    # Story 2.3 — Atomic Institution Onboarding
    path('add/', views.institution_add, name='institution-add'),

    # Story 2.4 — Superadmin Aggregate Analytics Dashboard
    path('superadmin/', views.superadmin_dashboard, name='superadmin-dashboard'),

    # Story 2.5 — Cross-Institution Aggregate Reports
    path('superadmin/reports/', views.superadmin_reports, name='superadmin-reports'),

    # Story 2.6 — Patient Move Between Institutions
    path('patient-move/<int:patient_id>/', views.superadmin_patient_move, name='superadmin-patient-move'),

    # Story 3.1 — Institution Admin Dashboard (future)
    # path('admin/', views.institution_admin_dashboard, name='institution-admin-dashboard'),
]
