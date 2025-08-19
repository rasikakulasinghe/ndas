from django.urls import path
from . import views

urlpatterns = [

    # URLs for patients operations
    path("", views.dashboard, name='home'),
    path("print", views.print, name='print'),
    path("manager/patient/", views.patient_manager, name='manage-patients'),
    path("manager/patient/new", views.patient_manager_new_only, name='manage-patients-new'),
    path("manager/patient/normal", views.patient_manager_diagnosis_normal, name='manage-patients-diagnosis-normal'),
    path("manager/patient/diagnosed/any", views.patient_manager_diagnosed_any, name='manage-patients-diagnosed-any'),
    path("manager/patient/diagnosed/gma/normal", views.patient_manager_diagnosed_gma_normal, name='manage-patients-diagnosed-gma-normal'),
    path("manager/patient/diagnosed/gma/abnormal", views.patient_manager_diagnosed_gma_abnormal, name='manage-patients-diagnosed-gma-abnormal'),
    path("manager/patient/diagnosed/hine", views.patient_manager_diagnosed_hine, name='manage-patients-diagnosed-hine'),
    path("manager/patient/diagnosed/da/normal", views.patient_manager_da_normal, name='manage-patients-diagnosed-da-normal'),
    path("manager/patient/diagnosed/da/abnormal", views.patient_manager_da_abnormal, name='manage-patients-diagnosed-da-abnormal'),
    path("manager/patient/discharged", views.patient_manager_discharged_only, name='manage-patients-discharged'),
    path("patient/add/", views.patient_add, name='add-patient'),
    path("patient/view/<str:pk>/", views.patient_view, name='view-patient'),
    path("patient/edit/<str:pk>/", views.patient_edit, name='edit-patient'),
    path("patient/delete/confirm/<str:pk>/", views.patient_delete_confirm, name='delete-confirm-patient'),
    path("patient/delete/<str:pk>/", views.patient_delete, name='delete-patient'),
    path("search/", views.search_start, name='search-start'),
    path("search/results/", views.earch_results, name='search-results'),
    path("help/article/", views.help_home, name='help-home'),
    path("help/article/<str:pk>/", views.help_article, name='help-article'),

    # URLs for bookmarks
    path("manager/bookmarks/", views.bookmark_manager, name='bookmark-manager'),
    path("manager/bookmarks/user/<str:username>/", views.bookmark_manager_user, name='bookmark-manager-user'),
    path("bookmarks/view/<str:pk>/", views.bookmark_view, name='bookmark-view'),
    path("bookmarks/edit/<str:pk>/", views.bookmark_edit, name='bookmark-edit'),
    path("bookmarks/add/<str:item_id>/<str:bookmark_type>/", views.bookmark_add, name='bookmark-add'),
    path("bookmarks/delete/<str:pk>/", views.bookmark_delete, name='bookmark-delete'),
    
    # URLs for attachments
    path("attachment/manager/", views.attachment_manager, name='attachment-manager'),
    path("attachment/manager/patient/<str:pid>", views.attachment_manager_patient, name='attachment-manager-patient'),
    path("attachment/add/<str:pid>/", views.attachment_add, name='attachment-add'),
    path("attachment/view/<str:pk>/", views.attachment_view, name='attachment-view'),
    path("attachment/edit/<str:pk>/", views.attachment_edit, name='attachment-edit'),
    path("attachment/delete/confirm/<str:pk>/", views.attachment_delete_confirm, name='attachment-delete-confirm'),
    path("attachment/delete/<str:pk>/", views.attachment_delete, name='attachment-delete'),

    # URLs for video file operations
    path("video/add/<str:pk>/", views.video_add, name='file-add'),
    path("video/view/<str:f_id>/", views.video_view, name='file-view'),
    path("video/edit/<str:f_id>/", views.video_edit, name='file-edit'),
    path("manager/video/filter/<str:patient_id>/", views.video_manager_by_patient, name='file-manager-patient'),
    # path("manager/video/<str:patient_id>/<str:file_type>/", views.video_manager_by_patient_type, name='file-manager-patient-type'),
    path("manager/video/", views.video_manager, name='file-manager-common'),
    path("manager/video/new/", views.video_manager_new_only, name='file-manager-common-new'),
    path("video/delete/confirm/<str:pk>/", views.video_delete_start, name='file-delete_start'),
    path("video/delete/<str:pk>/", views.video_delete, name='file-delete'),

    # URLs for GMA assessment record operations
    path("assessment/add/<str:ptid>/<str:fid>/", views.assessment_add, name='assessment-add'),
    path("assessment/edit/<str:pk>/", views.assessment_edit, name='assessment-edit'),
    path("assessment/edit/file/id/<str:pk>/", views.assessment_edit_by_fileid, name='assessment-edit-by-file-id'),
    path("assessment/view/<str:pk>/", views.assessment_view, name='assessment-view'),
    path("assessment/view/file/id/<str:file_id>/", views.assessment_view_by_fileid, name='assessment-view-by-file-id'),
    path("manager/assessment/", views.assessment_manager, name='assessment-manager'),
    path("manager/assessment/patient/<str:pk>/", views.assessment_manager_by_patients, name='assessment-manager-patient'),
    path("assessment/delete/confirm/<str:pk>/", views.assessment_delete_start, name='assessment-delete_start'),
    path("assessment/delete/<str:pk>/", views.assessment_delete, name='assessment-delete'),
    
    # URLs for CDIC assessment record operations
    path("cdic/add/<str:pid>/", views.cdic_assessment_add, name='cdic-assessment-add'),
    path("cdic/edit/<str:aid>/", views.cdic_assessment_edit, name='cdic-assessment-edit'),
    path("cdic/view/<str:cdic_id>/", views.cdic_assessment_view, name='cdic-assessment-view'),
    path("cdic/manager/", views.cdic_assessment_manager, name='cdic-assessment-manager'),
    path("cdic/manager/patient/<str:pid>/", views.cdic_assessment_manager_by_patients, name='cdic-assessment-manager-patient'),
    path("cdic/delete/confirm/<str:aid>/", views.cdic_assessment_delete_start, name='cdic-assessment-delete_start'),
    path("cdic/delete/<str:aid>/", views.cdic_assessment_delete, name='cdic-assessment-delete'),
    
    # URLs for HINE assessment record operations
    path("hine/add/<str:pid>/", views.hine_assessment_add, name='hine-assessment-add'),
    path("hine/edit/<str:hine_id>/", views.hine_assessment_edit, name='hine-assessment-edit'),
    path("hine/view/<str:hine_id>/", views.hine_assessment_view, name='hine-assessment-view'),
    path("hine/manager/", views.hine_assessment_manager, name='hine-assessment-manager'),
    path("hine/manager/patient/<str:pid>/", views.hine_assessment_manager_by_patients, name='hine-assessment-manager-patient'),
    path("hine/delete/confirm/<str:hine_id>/", views.hine_assessment_delete_start, name='hine-assessment-delete_start'),
    path("hine/delete/<str:hine_id>/", views.hine_assessment_delete, name='hine-assessment-delete'),
    
    # URLs for Develompental assessment record operations
    path("da/add/<str:pid>/", views.da_assessment_add, name='da-assessment-add'),
    path("da/edit/<str:da_id>/", views.da_assessment_edit, name='da-assessment-edit'),
    path("da/view/<str:da_id>/", views.da_assessment_view, name='da-assessment-view'),
    path("da/manager/", views.da_assessment_manager, name='da-assessment-manager'),
    path("da/manager/patient/<str:pid>/", views.da_assessment_manager_by_patients, name='da-assessment-manager-patient'),
    path("da/delete/confirm/<str:da_id>/", views.da_assessment_delete_start, name='da-assessment-delete_start'),
    path("da/delete/<str:da_id>/", views.da_assessment_delete, name='da-assessment-delete'),

    ]