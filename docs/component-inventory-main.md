# NDAS Component Inventory

Last Updated: 2026-03-09

---

## Template Inheritance Hierarchy

```
templates/src/basic_plane.html
    Used for: Login, password reset, public error pages
    No sidebar; minimal layout

templates/src/base.html
    Used for: All authenticated pages
    Includes:
        templates/src/navbar.html
        templates/src/main_sidebar_menu.html
        templates/src/main_footer.html
        templates/src/messages.html
        templates/src/logout_modal.html (or logout_modal_simple.html)
    Block: {% block main_content %}
    Block: {% block title %}
    Block: {% block extra_js %}
    Block: {% block extra_css %}
```

All app templates extend `'src/base.html'` (authenticated) or `'src/basic_plane.html'` (public). Templates do not use Django's app-level `templates/` directories; all templates reside in the project-root `templates/` directory.

---

## Template Directory Inventory

### `templates/src/` — Base Layout

| Template | Purpose |
|----------|---------|
| `base.html` | Master layout for authenticated pages (AdminLTE 3.2) |
| `basic_plane.html` | Minimal layout for public pages |
| `navbar.html` | Top navigation bar with user menu, institution switcher, notification bell |
| `main_sidebar_menu.html` | Left sidebar navigation with all app links |
| `main_footer.html` | Page footer |
| `messages.html` | Django messages display (Bootstrap alerts) |
| `logout_modal.html` | Full logout confirmation modal |
| `logout_modal_simple.html` | Simple logout modal variant |
| `content_headder.html` | Page content header with breadcrumbs |
| `control_sidebar.html` | Right control sidebar |
| `error_404.html` | 404 error template |
| `form_error.html` | Generic form error display |
| `main_content.html` | Inner content wrapper |
| `advance_search.html` | Advanced search panel |
| `search.html` | Search input component |

### `templates/src/partials/`

| Template | Purpose |
|----------|---------|
| `delete_confirmation_modal.html` | Universal delete confirmation modal with entity details and warning items |

### `templates/patients/`

| Template | Purpose |
|----------|---------|
| `index.html` | Dashboard / home page |
| `manager.html` | Patient list with filter tabs |
| `add.html` | Add patient form |
| `edit.html` | Edit patient form |
| `view.html` | Patient detail view with all assessments |
| `search.html` | Patient search form |
| `results.html` | Search results |
| `search_notfound.html` | No results message |
| `admin/contact-developer.html` | Developer contact page |

### `templates/patients/partials/`

| Template | Purpose |
|----------|---------|
| `patient_identification_details.html` | Patient ID card partial (used in multiple views) |
| `patient_timeline.html` | Assessment timeline HTMX partial |
| `patient_view.html` | Patient view body partial |
| `patients_list.html` | Patient list rows partial |

### `templates/assessment/` — GMA

| Template | Purpose |
|----------|---------|
| `manager.html` | GMA list with filter tabs |
| `add.html` | Add GMA assessment form (links video to patient) |
| `edit.html` | Edit GMA form |
| `view.html` | GMA detail with diagnosis, management plan |

### `templates/hine/` — HINE

| Template | Purpose |
|----------|---------|
| `manager.html` | HINE list |
| `add.html` | Add HINE form |
| `edit.html` | Edit HINE |
| `view.html` | HINE detail with score interpretation |

### `templates/develop_assemnt/` — DA

| Template | Purpose |
|----------|---------|
| `manager.html` | DA list |
| `add.html` | Add DA form (four developmental domains) |
| `edit.html` | Edit DA |
| `view.html` | DA detail |

### `templates/cdic_record/` — CDIC

| Template | Purpose |
|----------|---------|
| `manager.html` | CDIC list |
| `add.html` | Add CDIC record form |
| `edit.html` | Edit CDIC |
| `view.html` | CDIC detail with discharge info |

### `templates/gpa_record/` — GPA

| Template | Purpose |
|----------|---------|
| `manager.html` | GPA list |
| `add.html` | Add GPA form |
| `edit.html` | Edit GPA |
| `view.html` | GPA detail |

### `templates/attachment/`

| Template | Purpose |
|----------|---------|
| `manager.html` | All attachments list |
| `add.html` | Upload attachment form |
| `edit.html` | Edit attachment metadata |
| `view.html` | Attachment detail with preview (images/PDF) |

### `templates/bookmark/`

| Template | Purpose |
|----------|---------|
| `manager.html` | Bookmark list |
| `add.html` | Add bookmark form |
| `edit.html` | Edit bookmark |
| `view.html` | Bookmark detail |

### `templates/video/`

| Template | Purpose |
|----------|---------|
| `manager.html` | Video list |
| `add.html` | Video upload form |
| `edit.html` | Edit video metadata |
| `view.html` | Video detail with Video.js player |

### `templates/help/`

| Template | Purpose |
|----------|---------|
| `home.html` | Help content index |
| `article_index.html` | Article listing |
| `article.html` | Individual help article |

### `templates/problemlist/`

| Template | Purpose |
|----------|---------|
| `manager.html` | Problem list for a patient |
| `add.html` | Add problem form |
| `edit.html` | Edit problem |
| `view.html` | Problem detail |
| `delete_confirm.html` | Delete confirmation |
| `timeline.html` | Problem timeline view |
| `action_add.html` | Add action log entry form |
| `analysis.html` | Problem analysis dashboard |
| `_problem_list_section.html` | HTMX partial: problem list section |
| `_problem_row.html` | HTMX partial: single problem row |

### `templates/users/`

| Template | Purpose |
|----------|---------|
| `login.html` | Login page (extends basic_plane.html) |
| `user_view.html` | User profile view |
| `user_edit.html` | Edit own profile |
| `user_change_password.html` | Change password form |
| `user_activity.html` | User activity log |
| `subscription_detail.html` | Subscription details page |
| `subscription_expired.html` | Subscription expired block page |
| `subscription_update.html` | Admin subscription update form |
| `send_verification.html` | Send verification email page |
| `verification_expired.html` | Token expired message |
| `password_reset.html` | Password reset request form |
| `password_reset_sent.html` | Reset email sent confirmation |
| `password_reset_form.html` | New password form |
| `password_reset_done.html` | Reset complete confirmation |

### `templates/users/admin/`

| Template | Purpose |
|----------|---------|
| `admin_dashboard.html` | Admin user management dashboard |
| `user_list.html` | All users table |
| `user_add.html` | Add new user form |
| `user_edit.html` | Edit any user form |
| `user_activity.html` | User's activity log |
| `activity_logs.html` | System-wide activity logs |

### `templates/institution/`

| Template | Purpose |
|----------|---------|
| `selector.html` | SUPERADMIN institution selector |
| `add.html` | Onboard new institution form |
| `edit.html` | Edit institution form |
| `settings.html` | Institution branding/settings form |
| `superadmin_dashboard.html` | Aggregate analytics for SUPERADMIN |
| `superadmin_reports.html` | Cross-institution reports |
| `superadmin_patient_move.html` | Move patient between institutions |
| `admin_dashboard.html` | Institution admin dashboard |
| `clinician_list.html` | Institution clinician list |
| `clinician_add.html` | Add clinician to institution |
| `partials/` | Institution-specific partials |

### `templates/referral/`

| Template | Purpose |
|----------|---------|
| `initiate.html` | Referral initiation form |
| `inbox.html` | Referral inbox (sent + received) |
| `thread_panel.html` | HTMX partial: referral thread panel |
| `patient_referrals_tab.html` | HTMX partial: patient referrals tab |
| `notification_count_badge.html` | HTMX polling: notification count badge |
| `notification_panel.html` | HTMX partial: notification panel |

### `templates/errors/`

| Template | Purpose |
|----------|---------|
| Various error templates | 4xx/5xx error pages |

---

## Key UI Patterns

### HTMX Usage

HTMX is used for lightweight partial-page updates without full page reloads:

| Pattern | Where Used |
|---------|-----------|
| Problem status change (`hx-post`) | Problem list rows — `_problem_row.html` |
| Problem list section reload (`hx-swap`) | After add/edit/delete — `_problem_list_section.html` |
| Patient timeline | `patient_timeline.html` partial |
| Referral thread panel | `thread_panel.html` |
| Notification count polling (`hx-trigger="every 30s"`) | `notification_count_badge.html` |
| Notification panel | `notification_panel.html` |
| Institution clinician dropdown | `get_institution_clinicians` endpoint |

All HTMX requests include the CSRF token via meta tag or header injection.

### Delete Confirmation Modal

Universal pattern using `delete_modal_tags` template tag library:
```django
{% load delete_modal_tags %}
{% include 'src/partials/delete_confirmation_modal.html' %}
```

The modal displays:
- Entity display name
- Entity-specific detail items (name, BHT, date, etc.)
- Warning items (what will be cascade-deleted)
- Confirm/Cancel buttons

### Bootstrap 4.6 Components Used

| Component | Usage |
|-----------|-------|
| Cards | Dashboard stats cards, content panels |
| DataTables | All list/manager views |
| Badges | Assessment status, problem severity, HINE score categories |
| Alerts | Django messages (success, error, warning, info) |
| Modals | Delete confirmation, logout confirmation |
| Tabs | Patient view (assessments, timeline, referrals) |
| Tooltips | Field help text, action buttons |
| Progress bars | Dashboard stats, subscription status |
| Forms | All CRUD forms with validation feedback |
| Breadcrumbs | Page header navigation |

---

## Form Components

All forms use Bootstrap 4.6 form styling. Key form features:

- Django form rendering with field-level validation errors
- CSRF token included via `{% csrf_token %}` in all POST forms
- Date/datetime pickers (Bootstrap-compatible)
- File upload with client-side size validation
- Select2 for searchable dropdown (diagnosis selection, indication selection)
- CKEditor rich text fields (help content, report templates)

---

## Modal Components

| Modal | Template | Purpose |
|-------|----------|---------|
| Delete Confirmation | `src/partials/delete_confirmation_modal.html` | Universal delete confirm with entity details |
| Logout | `src/logout_modal.html` | Logout confirmation |
| Logout Simple | `src/logout_modal_simple.html` | Simplified logout confirm |

---

## Video Player Component

`Video.js` is used for all video playback. Key configuration:

```html
<video-js class="vjs-default-skin" controls>
    <source src="{{ video.video_file.url }}" type="video/mp4">
</video-js>
```

Custom script `static/js/videojs-failsafe.js` handles Video.js initialization failures gracefully.

---

## JavaScript Components

All custom JS files live in `static/js/`:

| File | Purpose |
|------|---------|
| `main.js` | Core initialization, AdminLTE setup |
| `app-utils.js` | Shared utility functions |
| `delete-confirmation.js` | Delete modal JS logic, CSRF header injection for fetch |
| `event-handlers.js` | Global event handlers |
| `manager.js` | DataTables initialization for list views |
| `patient-deletion.js` | Patient-specific delete flow |
| `patient-timeline.js` | Patient timeline rendering |
| `video-manager.js` | Video list initialization |
| `videojs-failsafe.js` | Defensive Video.js initialization |
| `login.js` | Login page JS |
| `logout-modal.js` | Logout modal trigger |
| `rotate.js` | Video rotation utility |
| `zoomrotate.js` | Video zoom/rotate controls |
| `debug.js` | Debug utilities (development only) |

---

## Static Asset Structure

```
static/
├── css/                # Custom CSS overrides
├── dist/               # AdminLTE 3.2 compiled assets
├── img/                # Static images (logos, icons)
├── js/                 # Custom JavaScript (see table above)
└── plugins/            # Third-party plugins (DataTables, Select2, etc.)
```

`whitenoise` serves static files in production via `CompressedManifestStaticFilesStorage` (hashed filenames + Brotli/gzip compression).

---

## Context Processors

| Processor | Injects |
|-----------|---------|
| `django.template.context_processors.request` | `request` object |
| `django.contrib.auth.context_processors.auth` | `user` |
| `django.contrib.messages.context_processors.messages` | `messages` |
| `institution.context_processors.institution_context` | `current_institution`, institution meta for navbar |

---

## Template Tags

| Tag Library | Location | Purpose |
|-------------|----------|---------|
| `delete_modal_tags` | `ndas/templatetags/` | Renders delete modal context |
| `static` | Django built-in | `{% load static %}` for static asset URLs |

---

## CSS Framework

**AdminLTE 3.2** + **Bootstrap 4.6** + **Font Awesome 6.4**

Do not upgrade or replace these versions — the UI is tightly integrated with AdminLTE 3.2 component classes.

All custom CSS overrides go in `static/css/`. Do not add inline `<style>` to templates.
