from django.urls import path
from . import views
from django.views.generic import TemplateView, RedirectView

urlpatterns = [

    # Test route for JavaScript fixes
    path("test-js-fixes/", TemplateView.as_view(template_name='test_js_fixes.html'), name='test-js-fixes'),

    # URLs for patients operations
    path("", views.dashboard, name='home'),
    path("print/", views.print, name='print'),

    # Unified patient manager with filter type
    path("manager/patient/", views.patient_manager, {'filter_type': 'all'}, name='manage-patients'),
    path("manager/patient/<str:filter_type>/", views.patient_manager, name='manage-patients-filtered'),

    # Legacy URLs (redirects for backward compatibility - 6 month deprecation)
    path("manager/patient/new/", RedirectView.as_view(pattern_name='manage-patients-filtered', permanent=False), {'filter_type': 'new'}, name='manage-patients-new'),
    path("manager/patient/normal/", RedirectView.as_view(pattern_name='manage-patients-filtered', permanent=False), {'filter_type': 'dx_normal'}, name='manage-patients-diagnosis-normal'),
    path("manager/patient/diagnosed/any/", RedirectView.as_view(pattern_name='manage-patients-filtered', permanent=False), {'filter_type': 'diagnosed'}, name='manage-patients-diagnosed-any'),
    path("manager/patient/diagnosed/gma/normal/", RedirectView.as_view(pattern_name='manage-patients-filtered', permanent=False), {'filter_type': 'gma_normal'}, name='manage-patients-diagnosed-gma-normal'),
    path("manager/patient/diagnosed/gma/abnormal/", RedirectView.as_view(pattern_name='manage-patients-filtered', permanent=False), {'filter_type': 'gma_abnormal'}, name='manage-patients-diagnosed-gma-abnormal'),
    path("manager/patient/diagnosed/hine/", RedirectView.as_view(pattern_name='manage-patients-filtered', permanent=False), {'filter_type': 'hine'}, name='manage-patients-diagnosed-hine'),
    path("manager/patient/diagnosed/da/normal/", RedirectView.as_view(pattern_name='manage-patients-filtered', permanent=False), {'filter_type': 'da_normal'}, name='manage-patients-diagnosed-da-normal'),
    path("manager/patient/diagnosed/da/abnormal/", RedirectView.as_view(pattern_name='manage-patients-filtered', permanent=False), {'filter_type': 'da_abnormal'}, name='manage-patients-diagnosed-da-abnormal'),
    path("manager/patient/discharged/", RedirectView.as_view(pattern_name='manage-patients-filtered', permanent=False), {'filter_type': 'discharged'}, name='manage-patients-discharged'),
    path("patient/add/", views.patient_add, name='add-patient'),
    path("patient/view/<int:pk>/", views.patient_view, name='view-patient'),
    path("patient/edit/<int:pk>/", views.patient_edit, name='edit-patient'),
    path("patient/delete/<int:pk>/", views.patient_delete, name='delete-patient'),
    path("search/", views.search_start, name='search-start'),
    path("search/results/", views.search_results, name='search-results'),
    path("help/article/", views.help_home, name='help-home'),
    path("help/article/<int:pk>/", views.help_article, name='help-article'),

    # URLs for bookmarks
    path("manager/bookmarks/", views.bookmark_manager, name='bookmark-manager'),
    path("manager/bookmarks/user/<str:username>/", views.bookmark_manager_user, name='bookmark-manager-user'),
    path("bookmarks/view/<int:pk>/", views.bookmark_view, name='bookmark-view'),
    path("bookmarks/edit/<int:pk>/", views.bookmark_edit, name='bookmark-edit'),
    path("bookmarks/add/<int:item_id>/<str:bookmark_type>/", views.bookmark_add, name='bookmark-add'),
    path("bookmarks/delete/<int:pk>/", views.bookmark_delete, name='bookmark-delete'),

    # URLs for attachments
    path("attachment/manager/", views.attachment_manager, name='attachment-manager'),
    path("attachment/manager/patient/<int:pid>/", views.attachment_manager_patient, name='attachment-manager-patient'),
    path("attachment/add/<int:pid>/", views.attachment_add, name='attachment-add'),
    path("attachment/view/<int:pk>/", views.attachment_view, name='attachment-view'),
    path("attachment/edit/<int:pk>/", views.attachment_edit, name='attachment-edit'),
    path("attachment/delete/<int:pk>/", views.attachment_delete, name='attachment-delete'),

    # URLs for GMA assessment record operations
    path("assessment/add/<int:ptid>/<int:fid>/", views.assessment_add, name='assessment-add'),
    path("assessment/edit/<int:pk>/", views.assessment_edit, name='assessment-edit'),
    path("assessment/edit/file/id/<int:pk>/", views.assessment_edit_by_fileid, name='assessment-edit-by-file-id'),
    path("assessment/view/<int:pk>/", views.assessment_view, name='assessment-view'),
    path("assessment/view/file/id/<int:file_id>/", views.assessment_view_by_fileid, name='assessment-view-by-file-id'),
    path("manager/assessment/", views.assessment_manager, name='assessment-manager'),
    path("manager/assessment/recent/", views.assessment_manager, {'filter_type': 'recent'}, name='assessment-manager-recent'),
    path("manager/assessment/normal/", views.assessment_manager, {'filter_type': 'normal'}, name='assessment-manager-normal'),
    path("manager/assessment/abnormal/", views.assessment_manager, {'filter_type': 'abnormal'}, name='assessment-manager-abnormal'),
    path("manager/assessment/informed/", views.assessment_manager, {'filter_type': 'informed'}, name='assessment-manager-informed'),
    path("manager/assessment/not-informed/", views.assessment_manager, {'filter_type': 'not_informed'}, name='assessment-manager-not-informed'),
    path("manager/assessment/patient/<int:pk>/", views.assessment_manager_by_patients, name='assessment-manager-patient'),
    path("assessment/delete/<int:pk>/", views.assessment_delete, name='assessment-delete'),

    # URLs for CDIC assessment record operations
    path("cdic/add/<int:pid>/", views.cdic_assessment_add, name='cdic-assessment-add'),
    path("cdic/edit/<int:aid>/", views.cdic_assessment_edit, name='cdic-assessment-edit'),
    path("cdic/view/<int:cdic_id>/", views.cdic_assessment_view, name='cdic-assessment-view'),
    path("cdic/manager/", views.cdic_assessment_manager, name='cdic-assessment-manager'),
    path("cdic/manager/patient/<int:pid>/", views.cdic_assessment_manager_by_patients, name='cdic-assessment-manager-patient'),
    path("cdic/delete/<int:aid>/", views.cdic_assessment_delete, name='cdic-assessment-delete'),

    # URLs for HINE assessment record operations
    path("hine/add/<int:pid>/", views.hine_assessment_add, name='hine-assessment-add'),
    path("hine/edit/<int:hine_id>/", views.hine_assessment_edit, name='hine-assessment-edit'),
    path("hine/view/<int:hine_id>/", views.hine_assessment_view, name='hine-assessment-view'),
    path("hine/manager/", views.hine_assessment_manager, name='hine-assessment-manager'),
    path("hine/manager/patient/<int:pid>/", views.hine_assessment_manager_by_patients, name='hine-assessment-manager-patient'),
    path("hine/delete/<int:hine_id>/", views.hine_assessment_delete, name='hine-assessment-delete'),

    # URLs for Develompental assessment record operations
    path("da/add/<int:pid>/", views.da_assessment_add, name='da-assessment-add'),
    path("da/edit/<int:da_id>/", views.da_assessment_edit, name='da-assessment-edit'),
    path("da/view/<int:da_id>/", views.da_assessment_view, name='da-assessment-view'),
    path("da/manager/", views.da_assessment_manager, name='da-assessment-manager'),
    path("da/manager/patient/<int:pid>/", views.da_assessment_manager_by_patients, name='da-assessment-manager-patient'),
    path("da/delete/<int:da_id>/", views.da_assessment_delete, name='da-assessment-delete'),

    # URLs for General Paediatric Assessment (GPA) record operations
    path("gpa/add/<int:pid>/", views.gpa_add, name='gpa-add'),
    path("gpa/edit/<int:gpa_id>/", views.gpa_edit, name='gpa-edit'),
    path("gpa/view/<int:gpa_id>/", views.gpa_view, name='gpa-view'),
    path("gpa/manager/", views.gpa_manager, name='gpa-manager'),
    path("gpa/manager/patient/<int:pid>/", views.gpa_manager_by_patient, name='gpa-manager-patient'),
    path("gpa/delete/<int:gpa_id>/", views.gpa_delete, name='gpa-delete'),

    ]