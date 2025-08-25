from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .forms import UserPasswordResetForm, UserPasswordResetConfirmForm

urlpatterns = [

    # URLs for user operations
    path("", views.loginPage, name='user-login'),
    path("login/", views.loginPage, name='user-login'),
    path("logout/", views.logoutPage, name='user-logout'),
    path("test-logout-modal/", views.test_logout_modal, name='test-logout-modal'),
    path("view/<str:pk>/", views.userView, name="user-view"),
    path("view-by-username/<str:username>/", views.userViewByUsername, name="user-view-by-username"),
    path("edit/<str:pk>/", views.userEdit, name="user-edit"),
    path("change-password/", views.userChangePassword, name="user-change-password"),

    # URLs for password reset
    path('reset_password/', auth_views.PasswordResetView.as_view(template_name='users/password_reset.html', form_class=UserPasswordResetForm), name='reset-password'),
    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(template_name="users/password_reset_sent.html"), name="password_reset_done"),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="users/password_reset_form.html", form_class=UserPasswordResetConfirmForm), name="password_reset_confirm"),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(template_name="users/password_reset_done.html"), name="password_reset_complete"),
    
    # Email Verification URLs
    path('verify-email/<str:token>/', views.verify_email, name='verify-email'),
    path('resend-verification/', views.resend_verification_email, name='resend-verification'),
    path('send-verification/', views.send_verification_email_view, name='send-verification'),
    
    # User Activity and Session Management URLs
    path('activity/', views.user_activity, name='user-activity'),
    path('terminate-session/<int:session_id>/', views.terminate_session, name='terminate-session'),
    path('terminate-all-sessions/', views.terminate_all_sessions, name='terminate-all-sessions'),
    
    # API URLs
    path('api/activity/', views.get_user_activity_api, name='user-activity-api'),
    
    # Admin User Management URLs
    path('admin/dashboard/', views.admin_dashboard, name='admin-dashboard'),
    path('admin/users/', views.admin_user_list, name='admin-user-list'),
    path('admin/users/add/', views.admin_user_add, name='admin-user-add'),
    path('admin/users/<int:pk>/edit/', views.admin_user_edit, name='admin-user-edit'),
    path('admin/users/<int:pk>/delete/', views.admin_user_delete, name='admin-user-delete'),
    path('admin/users/<int:pk>/toggle-status/', views.admin_user_toggle_status, name='admin-user-toggle-status'),
    path('admin/users/<int:pk>/activity/', views.admin_user_activity, name='admin-user-activity'),
    path('admin/activity-logs/', views.admin_activity_logs, name='admin-activity-logs'),
    
    # other urls
    path("contact-developer/", views.developerContacts, name="developer-contact"),

]