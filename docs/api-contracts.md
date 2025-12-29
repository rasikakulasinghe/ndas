# API Contracts - NDAS

**Generated:** 2025-12-29
**Project:** Neurodevelopmental Assessment System (NDAS)
**Architecture:** Django URL Routing (Server-Side Rendered)

---

## Overview

NDAS uses Django's URL routing system with function-based and class-based views. The application primarily serves server-side rendered HTML pages with HTMX for dynamic interactions. This document catalogs all URL endpoints organized by Django app.

**Authentication:** Most endpoints require authentication via `@login_required` decorator (login URL: `/users/login/`)

**HTTP Methods:** Determined by view decorators (`@require_GET`, `@require_http_methods(["GET", "POST"])`)

**Rate Limiting:** 10 requests/minute for create/edit operations, 5 requests/minute for deletes

---

## Root URL Configuration (ndas/urls.py)

### Admin
- `GET /admin/` - Django admin interface

### App Includes
- `/users/` → users app URLs
- `/reports/` → reports app URLs
- `/problems/` → problemlist app URLs
- `/` (root) → patients app URLs (primary interface)
- `/video/` → video app URLs

### Debug
- `GET /debug/bootstrap/` - Bootstrap component testing (debug only)

### Error Handlers
- `404` → Custom 404 handler (`ndas.views.handler404`)
- `500` → Custom 500 handler (`ndas.views.handler500`)

---

## Patients App (/)

**Purpose:** Patient records, assessments, bookmarks, and attachments management

### Dashboard & Search
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/` | `dashboard` | Home dashboard with patient overview |
| GET | `/print/` | `print` | Print-friendly patient list |
| GET | `/search/` | `search_start` | Search interface |
| GET | `/search/results/` | `search_results` | Search results page |

### Patient Management
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/manager/patient/` | `patient_manager` | All patients list (default filter) |
| GET | `/manager/patient/<filter_type>/` | `patient_manager` | Filtered patient list (new, dx_normal, diagnosed, discharged, etc.) |
| GET/POST | `/patient/add/` | `patient_add` | Add new patient |
| GET | `/patient/view/<pk>/` | `patient_view` | View patient details |
| GET/POST | `/patient/edit/<pk>/` | `patient_edit` | Edit patient record |
| POST | `/patient/delete/<pk>/` | `patient_delete` | Delete patient (requires confirmation) |

**Legacy Redirect URLs:** (6-month deprecation period)
- `/manager/patient/new/` → redirects to filtered view
- `/manager/patient/normal/` → redirects to dx_normal filter
- Various diagnosis-specific URLs redirect to unified filter

### Bookmarks
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/manager/bookmarks/` | `bookmark_manager` | All bookmarks |
| GET | `/manager/bookmarks/user/<username>/` | `bookmark_manager_user` | User-specific bookmarks |
| GET | `/bookmarks/view/<pk>/` | `bookmark_view` | View bookmark |
| GET/POST | `/bookmarks/edit/<pk>/` | `bookmark_edit` | Edit bookmark |
| POST | `/bookmarks/add/<item_id>/<bookmark_type>/` | `bookmark_add` | Add bookmark |
| POST | `/bookmarks/delete/<pk>/` | `bookmark_delete` | Delete bookmark |

### Attachments
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/attachment/manager/` | `attachment_manager` | All attachments |
| GET | `/attachment/manager/patient/<pid>/` | `attachment_manager_patient` | Patient-specific attachments |
| GET/POST | `/attachment/add/<pid>/` | `attachment_add` | Add attachment (file upload) |
| GET | `/attachment/view/<pk>/` | `attachment_view` | View attachment |
| GET/POST | `/attachment/edit/<pk>/` | `attachment_edit` | Edit attachment metadata |
| POST | `/attachment/delete/<pk>/` | `attachment_delete` | Delete attachment |

### GMA Assessment (General Movement Assessment)
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET/POST | `/assessment/add/<ptid>/<fid>/` | `assessment_add` | Add GMA assessment |
| GET/POST | `/assessment/edit/<pk>/` | `assessment_edit` | Edit GMA assessment |
| GET/POST | `/assessment/edit/file/id/<pk>/` | `assessment_edit_by_fileid` | Edit GMA by file ID |
| GET | `/assessment/view/<pk>/` | `assessment_view` | View GMA assessment |
| GET | `/assessment/view/file/id/<file_id>/` | `assessment_view_by_fileid` | View GMA by file ID |
| GET | `/manager/assessment/` | `assessment_manager` | All GMA assessments |
| GET | `/manager/assessment/recent/` | `assessment_manager_recent` | Recent assessments |
| GET | `/manager/assessment/normal/` | `assessment_manager_normal` | Normal assessments |
| GET | `/manager/assessment/abnormal/` | `assessment_manager_abnormal` | Abnormal assessments |
| GET | `/manager/assessment/informed/` | `assessment_manager_informed` | Informed patients |
| GET | `/manager/assessment/not-informed/` | `assessment_manager_not_informed` | Not informed patients |
| GET | `/manager/assessment/patient/<pk>/` | `assessment_manager_by_patients` | Patient-specific assessments |
| POST | `/assessment/delete/<pk>/` | `assessment_delete` | Delete assessment |

### CDIC Assessment (Child Development Inventory Checklist)
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET/POST | `/cdic/add/<pid>/` | `cdic_assessment_add` | Add CDIC assessment |
| GET/POST | `/cdic/edit/<aid>/` | `cdic_assessment_edit` | Edit CDIC assessment |
| GET | `/cdic/view/<cdic_id>/` | `cdic_assessment_view` | View CDIC assessment |
| GET | `/cdic/manager/` | `cdic_assessment_manager` | All CDIC assessments |
| GET | `/cdic/manager/patient/<pid>/` | `cdic_assessment_manager_by_patients` | Patient-specific CDIC |
| POST | `/cdic/delete/<aid>/` | `cdic_assessment_delete` | Delete CDIC assessment |

### HINE Assessment (Hammersmith Infant Neurological Examination)
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET/POST | `/hine/add/<pid>/` | `hine_assessment_add` | Add HINE assessment |
| GET/POST | `/hine/edit/<hine_id>/` | `hine_assessment_edit` | Edit HINE assessment |
| GET | `/hine/view/<hine_id>/` | `hine_assessment_view` | View HINE assessment |
| GET | `/hine/manager/` | `hine_assessment_manager` | All HINE assessments |
| GET | `/hine/manager/patient/<pid>/` | `hine_assessment_manager_by_patients` | Patient-specific HINE |
| POST | `/hine/delete/<hine_id>/` | `hine_assessment_delete` | Delete HINE assessment |

### DA Assessment (Developmental Assessment)
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET/POST | `/da/add/<pid>/` | `da_assessment_add` | Add DA assessment |
| GET/POST | `/da/edit/<da_id>/` | `da_assessment_edit` | Edit DA assessment |
| GET | `/da/view/<da_id>/` | `da_assessment_view` | View DA assessment |
| GET | `/da/manager/` | `da_assessment_manager` | All DA assessments |
| GET | `/da/manager/patient/<pid>/` | `da_assessment_manager_by_patients` | Patient-specific DA |
| POST | `/da/delete/<da_id>/` | `da_assessment_delete` | Delete DA assessment |

### GPA (General Paediatric Assessment)
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET/POST | `/gpa/add/<pid>/` | `gpa_add` | Add GPA record |
| GET/POST | `/gpa/edit/<gpa_id>/` | `gpa_edit` | Edit GPA record |
| GET | `/gpa/view/<gpa_id>/` | `gpa_view` | View GPA record |
| GET | `/gpa/manager/` | `gpa_manager` | All GPA records |
| GET | `/gpa/manager/patient/<pid>/` | `gpa_manager_by_patient` | Patient-specific GPA |
| POST | `/gpa/delete/<gpa_id>/` | `gpa_delete` | Delete GPA record |

### Help System
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/help/article/` | `help_home` | Help home page |
| GET | `/help/article/<pk>/` | `help_article` | View help article |

---

## Users App (/users/)

**Purpose:** Authentication, user management, and subscription handling

### Authentication
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET/POST | `/users/` | `loginPage` | Login page (root) |
| GET/POST | `/users/login/` | `loginPage` | Login page |
| POST | `/users/logout/` | `logoutPage` | Logout |
| GET | `/users/test-logout-modal/` | `test_logout_modal` | Test logout modal UI |

### User Profile
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/users/view/<pk>/` | `userView` | View user profile by ID |
| GET | `/users/view-by-username/<username>/` | `userViewByUsername` | View user by username |
| GET/POST | `/users/edit/<pk>/` | `userEdit` | Edit user profile |
| GET/POST | `/users/change-password/` | `userChangePassword` | Change password |

### Password Reset (Rate-Limited)
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET/POST | `/users/reset_password/` | `RateLimitedPasswordResetView` | Request password reset |
| GET | `/users/reset_password_sent/` | `PasswordResetDoneView` | Reset email sent confirmation |
| GET/POST | `/users/reset/<uidb64>/<token>/` | `PasswordResetConfirmView` | Set new password |
| GET | `/users/reset_password_complete/` | `PasswordResetCompleteView` | Reset complete confirmation |

### Email Verification
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/users/verify-email/<token>/` | `verify_email` | Verify email with token |
| POST | `/users/resend-verification/` | `resend_verification_email` | Resend verification email |
| POST | `/users/send-verification/` | `send_verification_email_view` | Send verification email |

### User Activity & Session Management
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/users/activity/` | `user_activity` | View user activity log |
| POST | `/users/terminate-session/<session_id>/` | `terminate_session` | Terminate specific session |
| POST | `/users/terminate-all-sessions/` | `terminate_all_sessions` | Terminate all user sessions |

### API Endpoints
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/users/api/activity/` | `get_user_activity_api` | JSON API for user activity |

### Admin User Management (Staff Only)
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/users/admin/dashboard/` | `admin_dashboard` | Admin dashboard |
| GET | `/users/admin/users/` | `admin_user_list` | List all users |
| GET/POST | `/users/admin/users/add/` | `admin_user_add` | Add new user |
| GET/POST | `/users/admin/users/<pk>/edit/` | `admin_user_edit` | Edit user |
| POST | `/users/admin/users/<pk>/delete/` | `admin_user_delete` | Delete user |
| POST | `/users/admin/users/<pk>/toggle-status/` | `admin_user_toggle_status` | Enable/disable user |
| GET | `/users/admin/users/<pk>/activity/` | `admin_user_activity` | View user activity (admin) |
| GET | `/users/admin/activity-logs/` | `admin_activity_logs` | System-wide activity logs |

### Subscription Management
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/users/subscription/` | `subscription_detail` | View subscription details |
| GET | `/users/subscription/info/` | `subscription_info` | Subscription information modal |
| POST | `/users/subscription/update/` | `subscription_update` | Update subscription |

### Developer Contact
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/users/contact-developer/` | `developerContacts` | Developer contact information |

---

## Video App (/video/)

**Purpose:** Video upload, storage, and management for assessments

| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/video/manager/` | `video_manager` | All videos list |
| GET | `/video/manager/patient/<patient_id>/` | `video_manager_by_patient` | Patient-specific videos |
| GET | `/video/manager/new/` | `video_manager_new_only` | Recently added videos |
| GET/POST | `/video/add/<patient_id>/` | `video_add` | Upload new video (2GB max, mp4/mov/avi/mkv/webm) |
| GET | `/video/view/<video_id>/` | `video_view` | View video with Video.js player |
| GET/POST | `/video/edit/<video_id>/` | `video_edit` | Edit video metadata |
| POST | `/video/delete/<video_id>/` | `video_delete` | Delete video |

**File Upload:** Supports up to 2GB video files with MIME validation

---

## Reports App (/reports/)

**Purpose:** PDF and Excel report generation and download

### Report Builder
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET/POST | `/reports/` | `report_builder` | Report builder interface (root) |
| GET/POST | `/reports/generate/` | `report_builder` | Generate custom report |
| GET | `/reports/history/` | `report_history` | Report generation history |

### Report Management
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/reports/download/<file_id>/` | `download_report` | Download generated report |
| POST | `/reports/delete/<file_id>/` | `delete_report` | Delete generated report |

### Assessment PDF Downloads
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/reports/pdf/gm/<assessment_id>/` | `download_gm_assessment_pdf` | Download GM assessment PDF |
| GET | `/reports/pdf/hine/<assessment_id>/` | `download_hine_assessment_pdf` | Download HINE assessment PDF |
| GET | `/reports/pdf/da/<assessment_id>/` | `download_da_assessment_pdf` | Download DA assessment PDF |
| GET | `/reports/pdf/cdic/<assessment_id>/` | `download_cdic_assessment_pdf` | Download CDIC assessment PDF |
| GET | `/reports/pdf/gpa/<assessment_id>/` | `download_gpa_assessment_pdf` | Download GPA assessment PDF |

**Report Formats:** PDF (ReportLab/WeasyPrint), Excel (openpyxl)

---

## Problem List App (/problems/)

**Purpose:** Problem tracking and management system

### Problem Management
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/problems/manager/<pid>/` | `problem_manager` | Patient-specific problem list |
| GET/POST | `/problems/add/<pid>/` | `problem_add` | Add new problem |
| GET | `/problems/view/<pk>/` | `problem_view` | View problem details |
| GET/POST | `/problems/edit/<pk>/` | `problem_edit` | Edit problem |
| POST | `/problems/delete/<pk>/` | `problem_delete` | Delete problem |

### HTMX Endpoints
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| POST | `/problems/status/<pk>/` | `problem_status_change` | Change problem status (HTMX) |

### Timeline & Actions
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/problems/timeline/<pk>/` | `problem_timeline` | Problem timeline view |
| GET/POST | `/problems/action/add/<pk>/` | `problem_action_add` | Add action to problem |

### Analysis & Export
| Method | Endpoint | View | Purpose |
|--------|----------|------|---------|
| GET | `/problems/analysis/` | `problem_analysis` | Problem analysis dashboard |
| GET | `/problems/analysis/export/` | `problem_analysis_export` | Export analysis data |

---

## Security & Rate Limiting

### Rate-Limited Endpoints (10/minute)
- All POST endpoints for create/edit operations
- Password reset requests
- User registration/profile updates

### Rate-Limited Endpoints (5/minute)
- All DELETE operations
- Bulk data exports

### CSRF Protection
- All POST/PUT/DELETE requests require valid CSRF token
- Token automatically included in forms via `{% csrf_token %}`

### Authentication Required
- All endpoints except:
  - `/users/login/`
  - `/users/reset_password/`
  - `/users/verify-email/<token>/`
  - Error handlers (404, 500)

---

## URL Parameter Types

| Parameter | Type | Example | Purpose |
|-----------|------|---------|---------|
| `pk` | String/Int | `B00123` or `42` | Primary key (patient ID or record ID) |
| `pid` | String | `B00123` | Patient ID (BHT number) |
| `aid` | Int | `42` | Assessment ID |
| `fid` | Int | `5` | File ID (video) |
| `file_id` | String | `uuid-string` | Generated file ID for reports |
| `username` | String | `johndoe` | Username |
| `filter_type` | String | `new`, `dx_normal`, `diagnosed` | Patient filter type |
| `bookmark_type` | String | `patient`, `assessment` | Bookmark target type |

---

## Response Types

### Server-Side Rendered
- Most endpoints return HTML rendered with Django templates
- Uses AdminLTE 3.2 + Bootstrap 4.6 components

### HTMX Partial Responses
- Some endpoints return HTML fragments for dynamic updates
- Examples: problem status changes, form submissions

### File Downloads
- PDF reports: `Content-Type: application/pdf`
- Excel reports: `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Videos: `Content-Type: video/mp4` (and other video MIME types)

### JSON API
- `/users/api/activity/` returns JSON for AJAX requests

---

## Common Query Parameters

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `?next=<url>` | Redirect after login | `?next=/patient/view/B00123/` |
| `?filter=<type>` | Filter results | `?filter=recent` |
| `?search=<term>` | Search query | `?search=john` |
| `?page=<num>` | Pagination | `?page=2` |

---

## Deprecated Endpoints

The following endpoints have been deprecated as part of refactoring efforts:

### Delete Confirmation Pages (Unified Modal Approach)
- `/patient/delete/confirm/<pk>/`
- `/attachment/delete/confirm/<pk>/`
- `/assessment/delete/confirm/<pk>/`
- `/cdic/delete/confirm/<aid>/`
- `/hine/delete/confirm/<hine_id>/`
- `/da/delete/confirm/<da_id>/`
- `/gpa/delete/confirm/<gpa_id>/`
- `/video/delete-confirm/<video_id>/`

**Migration:** Use unified delete modal with direct DELETE endpoint

### Legacy Patient Manager URLs (6-Month Deprecation)
- Various `/manager/patient/<specific_filter>/` URLs now redirect to unified filter system

---

## Notes

- All endpoints use Django's CSRF protection
- File uploads validate MIME types using python-magic
- Video uploads support streaming for files up to 2GB
- Rate limiting uses `django-ratelimit` with cache backend
- Session-based authentication with 1-hour timeout
- User activity automatically tracked via `UserActivityMiddleware`
