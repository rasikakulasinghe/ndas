# NDAS URL and View Contracts

Last Updated: 2026-03-09

All views require `@login_required(login_url="user-login")` unless noted as public. All state-changing views use `@require_http_methods(["GET", "POST"])` or `@require_POST`. Rate limits are applied per user-or-IP.

---

## App: patients (mounted at `/`)

### Dashboard and Navigation

| URL Pattern | View | Methods | Rate Limit | Description |
|-------------|------|---------|-----------|-------------|
| `/` | `dashboard` | GET | — | Main dashboard with stats, charts, RC alerts |
| `/print/` | `print` | GET | — | Print-friendly dashboard view |
| `/search/` | `search_start` | GET | — | Search start page |
| `/search/results/` | `search_results` | GET | — | Patient search results |
| `/help/article/` | `help_home` | GET | — | Help content index |
| `/help/article/<int:pk>/` | `help_article` | GET | — | Individual help article |

### Patient CRUD

| URL Pattern | View | Methods | Rate Limit | Description |
|-------------|------|---------|-----------|-------------|
| `/manager/patient/` | `patient_manager` | GET | — | All patients list (filter_type='all') |
| `/manager/patient/<str:filter_type>/` | `patient_manager` | GET | — | Filtered patient list. filter_type: all, new, dx_normal, diagnosed, gma_normal, gma_abnormal, hine, da_normal, da_abnormal, discharged |
| `/patient/add/` | `patient_add` | GET, POST | 10/m | Add new patient |
| `/patient/view/<int:pk>/` | `patient_view` | GET | — | Patient detail view |
| `/patient/edit/<int:pk>/` | `patient_edit` | GET, POST | 10/m | Edit patient record |
| `/patient/delete/<int:pk>/` | `patient_delete` | GET, POST | 5/m | Delete patient and cascade |

### GMA Assessments

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/assessment/add/<int:ptid>/<int:fid>/` | `assessment_add` | GET, POST | Add GMA assessment for patient (ptid) and video (fid) |
| `/assessment/edit/<int:pk>/` | `assessment_edit` | GET, POST | Edit GMA by assessment PK |
| `/assessment/edit/file/id/<int:pk>/` | `assessment_edit_by_fileid` | GET, POST | Edit GMA by video file PK |
| `/assessment/view/<int:pk>/` | `assessment_view` | GET | GMA detail view |
| `/assessment/view/file/id/<int:file_id>/` | `assessment_view_by_fileid` | GET | GMA detail by video file ID |
| `/manager/assessment/` | `assessment_manager` | GET | All GMA assessments list |
| `/manager/assessment/recent/` | `assessment_manager` | GET | Recent assessments (filter_type='recent') |
| `/manager/assessment/normal/` | `assessment_manager` | GET | Normal assessments |
| `/manager/assessment/abnormal/` | `assessment_manager` | GET | Abnormal assessments |
| `/manager/assessment/informed/` | `assessment_manager` | GET | Parent-informed assessments |
| `/manager/assessment/not-informed/` | `assessment_manager` | GET | Parent not yet informed |
| `/manager/assessment/patient/<int:pk>/` | `assessment_manager_by_patients` | GET | GMAs for a specific patient |
| `/assessment/delete/<int:pk>/` | `assessment_delete` | GET, POST | Delete GMA |

### CDIC Records

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/cdic/add/<int:pid>/` | `cdic_assessment_add` | GET, POST | Add CDIC record for patient |
| `/cdic/edit/<int:aid>/` | `cdic_assessment_edit` | GET, POST | Edit CDIC record |
| `/cdic/view/<int:cdic_id>/` | `cdic_assessment_view` | GET | CDIC detail view |
| `/cdic/manager/` | `cdic_assessment_manager` | GET | All CDIC records list |
| `/cdic/manager/patient/<int:pid>/` | `cdic_assessment_manager_by_patients` | GET | CDICs for a patient |
| `/cdic/delete/<int:aid>/` | `cdic_assessment_delete` | GET, POST | Delete CDIC record |

### HINE Assessments

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/hine/add/<int:pid>/` | `hine_assessment_add` | GET, POST | Add HINE assessment |
| `/hine/edit/<int:hine_id>/` | `hine_assessment_edit` | GET, POST | Edit HINE |
| `/hine/view/<int:hine_id>/` | `hine_assessment_view` | GET | HINE detail |
| `/hine/manager/` | `hine_assessment_manager` | GET | All HINE list |
| `/hine/manager/patient/<int:pid>/` | `hine_assessment_manager_by_patients` | GET | HINEs for a patient |
| `/hine/delete/<int:hine_id>/` | `hine_assessment_delete` | GET, POST | Delete HINE |

### Developmental Assessments

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/da/add/<int:pid>/` | `da_assessment_add` | GET, POST | Add DA |
| `/da/edit/<int:da_id>/` | `da_assessment_edit` | GET, POST | Edit DA |
| `/da/view/<int:da_id>/` | `da_assessment_view` | GET | DA detail |
| `/da/manager/` | `da_assessment_manager` | GET | All DA list |
| `/da/manager/patient/<int:pid>/` | `da_assessment_manager_by_patients` | GET | DAs for a patient |
| `/da/delete/<int:da_id>/` | `da_assessment_delete` | GET, POST | Delete DA |

### GPA Records

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/gpa/add/<int:pid>/` | `gpa_add` | GET, POST | Add GPA record |
| `/gpa/edit/<int:gpa_id>/` | `gpa_edit` | GET, POST | Edit GPA |
| `/gpa/view/<int:gpa_id>/` | `gpa_view` | GET | GPA detail |
| `/gpa/manager/` | `gpa_manager` | GET | All GPA list |
| `/gpa/manager/patient/<int:pid>/` | `gpa_manager_by_patient` | GET | GPAs for a patient |
| `/gpa/delete/<int:gpa_id>/` | `gpa_delete` | GET, POST | Delete GPA |

### Attachments

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/attachment/manager/` | `attachment_manager` | GET | All attachments list |
| `/attachment/manager/patient/<int:pid>/` | `attachment_manager_patient` | GET | Attachments for a patient |
| `/attachment/add/<int:pid>/` | `attachment_add` | GET, POST | Upload attachment |
| `/attachment/view/<int:pk>/` | `attachment_view` | GET | Attachment detail |
| `/attachment/edit/<int:pk>/` | `attachment_edit` | GET, POST | Edit attachment metadata |
| `/attachment/delete/<int:pk>/` | `attachment_delete` | GET, POST | Delete attachment and file |

### Bookmarks

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/manager/bookmarks/` | `bookmark_manager` | GET | All bookmarks list |
| `/manager/bookmarks/user/<str:username>/` | `bookmark_manager_user` | GET | Bookmarks for a specific user |
| `/bookmarks/view/<int:pk>/` | `bookmark_view` | GET | Bookmark detail |
| `/bookmarks/edit/<int:pk>/` | `bookmark_edit` | GET, POST | Edit bookmark |
| `/bookmarks/add/<int:item_id>/<str:bookmark_type>/` | `bookmark_add` | GET, POST | Create bookmark for an object |
| `/bookmarks/delete/<int:pk>/` | `bookmark_delete` | GET, POST | Delete bookmark |

---

## App: users (mounted at `/users/`)

### Authentication

| URL Pattern | View | Methods | Auth | Rate Limit | Description |
|-------------|------|---------|------|-----------|-------------|
| `/users/` | `loginPage` | GET, POST | Public | 5/m | Login page and form handler |
| `/users/login/` | `loginPage` | GET, POST | Public | 5/m | Alias for login |
| `/users/logout/` | `logoutPage` | GET | Login required | — | Logout and session flush |

### Password Reset (Public)

| URL Pattern | View | Description |
|-------------|------|-------------|
| `/users/reset_password/` | `RateLimitedPasswordResetView` | Password reset form (rate limited) |
| `/users/reset_password_sent/` | `PasswordResetDoneView` | Confirmation page |
| `/users/reset/<uidb64>/<token>/` | `PasswordResetConfirmView` | Password reset confirm form |
| `/users/reset_password_complete/` | `PasswordResetCompleteView` | Reset complete page |

### User Profile

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/users/view/<str:pk>/` | `userView` | GET | User profile by PK |
| `/users/view-by-username/<str:username>/` | `userViewByUsername` | GET | User profile by username |
| `/users/edit/<str:pk>/` | `userEdit` | GET, POST | Edit own profile |
| `/users/change-password/` | `userChangePassword` | GET, POST | Change password |

### Email Verification

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/users/verify-email/<str:token>/` | `verify_email` | GET | Verify email token |
| `/users/resend-verification/` | `resend_verification_email` | POST | Resend verification email |
| `/users/send-verification/` | `send_verification_email_view` | GET, POST | Send verification page |

### Session Management

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/users/activity/` | `user_activity` | GET | Own activity log view |
| `/users/terminate-session/<int:session_id>/` | `terminate_session` | POST | Kill a specific session |
| `/users/terminate-all-sessions/` | `terminate_all_sessions` | POST | Kill all other sessions |
| `/users/api/activity/` | `get_user_activity_api` | GET | Activity data JSON API |

### Admin User Management

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/users/admin/dashboard/` | `admin_dashboard` | GET | Admin dashboard |
| `/users/admin/users/` | `admin_user_list` | GET | All users list |
| `/users/admin/users/add/` | `admin_user_add` | GET, POST | Add new user |
| `/users/admin/users/<int:pk>/edit/` | `admin_user_edit` | GET, POST | Edit any user |
| `/users/admin/users/<int:pk>/delete/` | `admin_user_delete` | GET, POST | Deactivate user |
| `/users/admin/users/<int:pk>/toggle-status/` | `admin_user_toggle_status` | POST | Toggle active status |
| `/users/admin/users/<int:pk>/activity/` | `admin_user_activity` | GET | Activity log for user |
| `/users/admin/activity-logs/` | `admin_activity_logs` | GET | All activity logs |

### Subscription

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/users/subscription/` | `subscription_detail` | GET | View subscription details |
| `/users/subscription/info/` | `subscription_info` | GET | Subscription info widget |
| `/users/subscription/update/` | `subscription_update` | GET, POST | Update subscription settings |

### Other

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/users/contact-developer/` | `developerContacts` | GET | Developer contact info page |

---

## App: video (mounted at `/video/`, namespace: `video`)

| URL Pattern | View | Methods | Rate Limit | Description |
|-------------|------|---------|-----------|-------------|
| `/video/manager/` | `video_manager` | GET | — | All videos list |
| `/video/manager/patient/<int:patient_id>/` | `video_manager_by_patient` | GET | — | Videos for a patient |
| `/video/manager/new/` | `video_manager_new_only` | GET | — | Videos not yet assessed |
| `/video/add/<int:patient_id>/` | `video_add` | GET, POST | 10/m | Upload new video for patient |
| `/video/view/<int:video_id>/` | `video_view` | GET | — | Video detail with Video.js player |
| `/video/edit/<int:video_id>/` | `video_edit` | GET, POST | 10/m | Edit video metadata |
| `/video/delete/<int:video_id>/` | `video_delete` | GET, POST | 5/m | Delete video (blocked if in assessment) |

URL names use the `video:` namespace prefix, e.g., `{% url 'video:view' video_id=v.pk %}`.

---

## App: reports (mounted at `/reports/`, namespace: `reports`)

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/reports/` | `report_builder` | GET, POST | Report builder — filter and generate |
| `/reports/generate/` | `report_builder` | GET, POST | Alias |
| `/reports/history/` | `report_history` | GET | List of generated reports |
| `/reports/download/<str:file_id>/` | `download_report` | GET | Download generated report file |
| `/reports/delete/<str:file_id>/` | `delete_report` | POST | Delete report file |
| `/reports/pdf/gm/<int:assessment_id>/` | `download_gm_assessment_pdf` | GET | Download GMA assessment PDF |
| `/reports/pdf/hine/<int:assessment_id>/` | `download_hine_assessment_pdf` | GET | Download HINE assessment PDF |
| `/reports/pdf/da/<int:assessment_id>/` | `download_da_assessment_pdf` | GET | Download DA assessment PDF |
| `/reports/pdf/cdic/<int:assessment_id>/` | `download_cdic_assessment_pdf` | GET | Download CDIC record PDF |
| `/reports/pdf/gpa/<int:assessment_id>/` | `download_gpa_assessment_pdf` | GET | Download GPA record PDF |

---

## App: problemlist (mounted at `/problems/`)

| URL Pattern | View | Methods | Rate Limit | Description |
|-------------|------|---------|-----------|-------------|
| `/problems/manager/<str:pid>/` | `problem_manager` | GET | — | Problem list for patient |
| `/problems/add/<str:pid>/` | `problem_add` | GET, POST | 10/m | Add problem for patient |
| `/problems/view/<str:pk>/` | `problem_view` | GET | — | Problem detail |
| `/problems/edit/<str:pk>/` | `problem_edit` | GET, POST | 10/m | Edit problem |
| `/problems/delete/<str:pk>/` | `problem_delete` | GET, POST | 5/m | Delete problem and actions |
| `/problems/status/<str:pk>/` | `problem_status_change` | POST | 10/m | HTMX: change problem status |
| `/problems/timeline/<str:pk>/` | `problem_timeline` | GET | — | Problem timeline view |
| `/problems/action/add/<str:pk>/` | `problem_action_add` | GET, POST | 10/m | Add action log entry |
| `/problems/analysis/` | `problem_analysis` | GET | — | Problem analysis view |
| `/problems/analysis/export/` | `problem_analysis_export` | GET | — | Export problem analysis |

---

## App: institution (mounted at `/institution/`, namespace: `institution`)

| URL Pattern | View | Methods | Access | Description |
|-------------|------|---------|--------|-------------|
| `/institution/` | `institution_selector` | GET | SUPERADMIN | Institution selector / god-view |
| `/institution/switch/<int:institution_id>/` | `institution_switch` | POST | SUPERADMIN | Switch active institution context |
| `/institution/add/` | `institution_add` | GET, POST | SUPERADMIN | Onboard new institution |
| `/institution/edit/<int:institution_id>/` | `superadmin_institution_edit` | GET, POST | SUPERADMIN | Edit institution settings |
| `/institution/superadmin/` | `superadmin_dashboard` | GET | SUPERADMIN | Aggregate analytics dashboard |
| `/institution/superadmin/reports/` | `superadmin_reports` | GET | SUPERADMIN | Cross-institution reports |
| `/institution/patient-move/<int:patient_id>/` | `superadmin_patient_move` | GET, POST | SUPERADMIN | Move patient between institutions |
| `/institution/admin/` | `institution_admin_dashboard` | GET | ADMIN | Institution admin dashboard |
| `/institution/clinicians/` | `institution_clinician_list` | GET | ADMIN | List institution clinicians |
| `/institution/clinicians/add/` | `institution_clinician_add` | GET, POST | ADMIN | Add new clinician to institution |
| `/institution/clinicians/<int:user_id>/toggle-status/` | `institution_clinician_toggle_status` | POST | ADMIN | Activate/deactivate clinician |
| `/institution/settings/` | `institution_settings` | GET, POST | ADMIN | Institution branding and settings |

Also: `GET /media/<path:path>` → `protected_media_view` (debug mode only)

---

## App: referral (mounted at `/referral/`, namespace: `referral`)

| URL Pattern | View | Methods | Description |
|-------------|------|---------|-------------|
| `/referral/initiate/<int:patient_id>/` | `referral_initiate` | GET, POST | Initiate referral for patient |
| `/referral/clinicians/<int:institution_id>/` | `get_institution_clinicians` | GET | HTMX: get clinicians for institution |
| `/referral/inbox/` | `referral_inbox` | GET | Referral inbox (sent and received) |
| `/referral/thread/<uuid:referral_uuid>/` | `referral_thread_panel` | GET | HTMX: thread panel partial |
| `/referral/thread/<uuid:referral_uuid>/reply/` | `referral_reply` | POST | Post reply to referral thread |
| `/referral/thread/<uuid:referral_uuid>/close/` | `referral_close` | POST | Close referral thread |
| `/referral/patient/<int:patient_id>/referrals/` | `patient_referrals_tab` | GET | Referrals tab on patient detail page |
| `/referral/notifications/count/` | `notification_count` | GET | HTMX polling: unread notification count |
| `/referral/notifications/panel/` | `notification_panel` | GET | HTMX: notification panel partial |
| `/referral/notifications/<int:pk>/read/` | `notification_mark_read` | POST | Mark one notification as read |
| `/referral/notifications/mark-all-read/` | `notification_mark_all_read` | POST | Mark all notifications as read |

---

## Error Handlers (Root ndas/urls.py)

| Handler | View | Trigger |
|---------|------|---------|
| `handler404` | `ndas.views.handler404` | Page not found |
| `handler500` | `ndas.views.handler500` | Server error |
| Rate limit exceeded | `ndas.views.handler_rate_limited` | django-ratelimit block |

---

## Debug Route

| URL Pattern | View | Notes |
|-------------|------|-------|
| `/debug/bootstrap/` | `ndas.views.debug_bootstrap` | Bootstrap debug page (dev use) |
