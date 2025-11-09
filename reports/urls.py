# URL patterns for reports app
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Report builder and management
    path('', views.report_builder, name='builder'),
    path('generate/', views.report_builder, name='generate'),
    path('history/', views.report_history, name='history'),

    # Report download
    path('download/<str:file_id>/', views.download_report, name='download'),

    # Assessment PDF downloads
    path('pdf/gm/<int:assessment_id>/', views.download_gm_assessment_pdf, name='pdf-gm'),
    path('pdf/hine/<int:assessment_id>/', views.download_hine_assessment_pdf, name='pdf-hine'),
    path('pdf/da/<int:assessment_id>/', views.download_da_assessment_pdf, name='pdf-da'),
    path('pdf/cdic/<int:assessment_id>/', views.download_cdic_assessment_pdf, name='pdf-cdic'),
    path('pdf/gpa/<int:assessment_id>/', views.download_gpa_assessment_pdf, name='pdf-gpa'),
]
