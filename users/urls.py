from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .forms import UserPasswordResetForm, UserPasswordResetConfirmForm

urlpatterns = [

    # URLs for user operations
    path("", views.loginPage, name='user-login'),
    path("login/", views.loginPage, name='user-login'),
    path("logout/", views.logoutPage, name='user-logout'),
    path("view/<str:pk>/", views.userView, name="user-view"),
    path("view-by-username/<str:username>/", views.userViewByUsername, name="user-view-by-username"),
    path("edit/<str:pk>/", views.userEdit, name="user-edit"),
    path("change-password/", views.userChangePassword, name="user-change-password"),

    # URLs for password reset
    path('reset_password/', auth_views.PasswordResetView.as_view(template_name='users/password_reset.html', form_class=UserPasswordResetForm), name='reset-password'),
    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(template_name="users/password_reset_sent.html"), name="password_reset_done"),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="users/password_reset_form.html", form_class=UserPasswordResetConfirmForm), name="password_reset_confirm"),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(template_name="users/password_reset_done.html"), name="password_reset_complete"),
    
    # other urls
    path("contac-developer/", views.developerContacts, name="developer-contact"),

]