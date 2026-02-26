from django.urls import path
from referral import views

app_name = 'referral'

urlpatterns = [
    # Story 4.2: Referral initiation
    path('initiate/<int:patient_id>/', views.referral_initiate, name='referral-initiate'),
    path('clinicians/<int:institution_id>/', views.get_institution_clinicians, name='get-institution-clinicians'),

    # Story 4.3: Referral Inbox (stub view implemented in 4.2 for redirect target)
    path('inbox/', views.referral_inbox, name='referral-inbox'),

    # Story 4.3: Thread Panel (HTMX partial)
    path('thread/<uuid:referral_uuid>/', views.referral_thread_panel, name='referral-thread-panel'),

    # Story 4.4: Reply
    path('thread/<uuid:referral_uuid>/reply/', views.referral_reply, name='referral-reply'),

    # Story 4.5: Close
    path('thread/<uuid:referral_uuid>/close/', views.referral_close, name='referral-close'),

    # Story 4.6: Patient referrals tab
    path('patient/<int:patient_id>/referrals/', views.patient_referrals_tab, name='patient-referrals-tab'),

    # Story 5.2: Notification count (HTMX polling)
    path('notifications/count/', views.notification_count, name='notification-count'),

    # Story 5.3: Notification panel + mark as read
    path('notifications/panel/', views.notification_panel, name='notification-panel'),
    path('notifications/<int:pk>/read/', views.notification_mark_read, name='notification-mark-read'),
    path('notifications/mark-all-read/', views.notification_mark_all_read, name='notification-mark-all-read'),
]
