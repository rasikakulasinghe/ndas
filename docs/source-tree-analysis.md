# NDAS — Source Tree Analysis

## Repository Overview

NDAS is a Django MVT monolith hosted on a single server. It contains a core Django config package (`ndas/`), seven Django application packages, a project-wide templates directory, project-wide static assets, a media upload store, test suites at the app level, BMAD planning tooling, and deployment artifacts. The repository follows a standard Django single-project layout with no micro-services, no separate frontend build step, and no Celery workers (report generation is synchronous).

---

## Annotated Directory Tree

```
NDAS/                                        # Repository root
│
├── manage.py                                # Django management entry point
├── db.sqlite3                               # SQLite database (dev/local only)
├── deploy.sh                                # Deployment shell script
├── DEPLOYMENT.md                            # Server deployment instructions
├── CLAUDE.md                                # AI coding-assistant project rules
├── AGENTS.md                                # BMAD agent orchestration instructions
│
├── ndas/                                    # Django project package (config)
│   ├── __init__.py
│   ├── settings.py                          # All settings — env-var driven; controls DB,
│   │                                        #   cache, middleware order, file upload limits,
│   │                                        #   allowed extensions, CSP, session config
│   ├── urls.py                              # Root URL dispatcher — routes to all apps
│   ├── views.py                             # Project-level views (handler404, handler500,
│   │                                        #   debug_bootstrap)
│   ├── wsgi.py                              # WSGI entry point (production)
│   ├── asgi.py                              # ASGI entry point (async-capable, not yet used)
│   ├── templatetags/
│   │   └── delete_modal_tags.py             # Template tag: renders delete confirmation modal
│   └── custom_codes/                        # Shared utilities — imported by ALL apps
│       ├── Custom_abstract_class.py         # TimeStampedModel (created_at, updated_at)
│       │                                    #   + UserTrackingMixin (added_by, last_edit_by)
│       │                                    #   — base classes for every model in the project
│       ├── choice.py                        # All TextChoices/IntegerChoices used in models
│       │                                    #   and forms (GENDER, MODE_OF_DELIVERY, APGAR,
│       │                                    #   BOOKMARK_TYPE, DX_CONCLUTION, etc.)
│       ├── validators.py                    # Field validators: validate_birth_weight(),
│       │                                    #   validate_apgar_score(), validate_pog_weeks(),
│       │                                    #   sanitize_text_input(), sanitize_filename(),
│       │                                    #   validate_attachment_file(),
│       │                                    #   get_institution_attachment_path()
│       ├── sanitization.py                  # HTML sanitization via bleach:
│       │                                    #   sanitize_html(), sanitize_plain_text()
│       ├── custom_methods.py                # Utility functions: getCountZeroIfNone(),
│       │                                    #   checkRCState(), calculate_age_string(),
│       │                                    #   extract_video_metadata()
│       ├── ndas_enums.py                    # Python enumerations (PtStatus, etc.)
│       ├── delete_helpers.py                # Deletion guards: has_delete_permission(),
│       │                                    #   validate_can_delete(), get_entity_warning_items(),
│       │                                    #   get_entity_detail_items()
│       ├── security_middleware.py           # CSPMiddleware, AdditionalSecurityHeadersMiddleware,
│       │                                    #   SecurityHeadersValidationMiddleware
│       └── error_handlers.py               # View decorators: @handle_view_errors(),
│                                            #   @log_and_suppress()
│
├── patients/                                # PRIMARY APP — root URL catch-all ("")
│   │                                        # Patient records, all assessment types,
│   │                                        # attachments, bookmarks, search
│   ├── models.py                            # Patient, GMAssessment, CDICRecord,
│   │                                        #   GeneralPaediatricAssessment, Attachment,
│   │                                        #   Bookmark, IndicationsForGMA, DiagnosisList,
│   │                                        #   Help, HINEAssessment, DevelopmentalAssessment
│   ├── views.py                             # All patient-facing views (list, add, edit,
│   │                                        #   view, search, assessment CRUD)
│   ├── urls.py                              # URL patterns rooted at "" — catch-all last
│   ├── forms.py                             # Patient and assessment forms
│   ├── admin.py                             # Django admin registrations
│   ├── apps.py                              # App config (label="patients")
│   ├── timeline_utils.py                    # Builds chronological patient timeline data
│   ├── migrations/                          # 10 migrations (0001–0010)
│   └── tests/
│       ├── test_validators.py               # Validator unit tests
│       └── test_views.py                    # View integration tests
│
├── users/                                   # Authentication and user management (prefix: users/)
│   ├── models.py                            # CustomUser (extends AbstractUser),
│   │                                        #   UserActivityLog, UserSession,
│   │                                        #   DeveloperContacts, Subscription
│   ├── views.py                             # Login, logout, profile, password reset,
│   │                                        #   subscription, admin user management,
│   │                                        #   email verification
│   ├── urls.py                              # URL patterns under users/
│   ├── forms.py                             # Login, registration, profile edit forms
│   ├── admin.py                             # Admin registrations
│   ├── apps.py                              # App config (label="users")
│   ├── decorators.py                        # @subscription_required, role-check decorators
│   ├── middleware.py                        # UserActivityMiddleware (auto-populates
│   │                                        #   added_by/last_edit_by on every request),
│   │                                        #   SubscriptionCheckMiddleware,
│   │                                        #   UserAgentMiddleware
│   ├── utils.py                             # Email sending helpers, token utilities
│   ├── migrations/                          # 9 migrations (0001–0009)
│   └── tests.py                             # User auth tests
│
├── video/                                   # Video upload and management (prefix: video/)
│   ├── models.py                            # Video (VideoQuerySet, VideoManager, Video model)
│   │                                        #   — stores file path, duration, resolution,
│   │                                        #   processing_status, patient FK
│   ├── views.py                             # Upload, list, stream, delete views
│   ├── urls.py                              # URL patterns under video/
│   ├── forms.py                             # Video upload form with MIME validation
│   ├── admin.py                             # Admin registration
│   ├── apps.py                              # App config (label="video")
│   ├── management/
│   │   └── commands/
│   │       └── fix_video_durations.py       # Management command: backfills duration metadata
│   ├── migrations/                          # 7 migrations (0001–0007)
│   └── tests.py                             # Video upload/stream tests
│
├── reports/                                 # PDF and Excel report generation (prefix: reports/)
│   ├── models.py                            # ReportTemplate, ReportConfig
│   ├── views.py                             # Report builder, history, download views
│   ├── urls.py                              # URL patterns under reports/
│   ├── tasks.py                             # Synchronous report generation tasks
│   ├── admin.py                             # Admin registration
│   ├── apps.py                              # App config (label="reports")
│   ├── utils/
│   │   ├── pdf_generator.py                 # BasePDFGenerator, PatientPDFGenerator,
│   │   │                                    #   assessment-specific PDF generators
│   │   └── excel_generator.py              # ExcelReportGenerator (anonymization,
│   │                                        #   filtering, multi-sheet export)
│   ├── templates/
│   │   └── reports/
│   │       ├── builder.html                 # Report builder UI
│   │       └── history.html                 # Report history/download list
│   ├── migrations/                          # 2 migrations (0001–0002)
│   └── tests.py                             # Report generation tests
│
├── problemlist/                             # Clinical problem list (prefix: problems/)
│   ├── models.py                            # Problem, ProblemAction
│   ├── views.py                             # Problem CRUD, action add, analysis, timeline
│   ├── urls.py                              # URL patterns under problems/
│   ├── forms.py                             # Problem and action forms
│   ├── admin.py                             # Admin registration
│   ├── apps.py                              # App config (label="problemlist")
│   ├── migrations/                          # 2 migrations (0001–0002)
│   └── tests.py                             # Problem list tests
│
├── institution/                             # Phase 2 — multi-institution foundation
│   │                                        # (prefix: institution/)
│   ├── models.py                            # Institution, PatientMoveLog
│   ├── views.py                             # Institution CRUD, selector, superadmin
│   │                                        #   dashboard, clinician management, patient
│   │                                        #   move, superadmin reports, protected media
│   ├── urls.py                              # URL patterns under institution/
│   ├── forms.py                             # Institution add/edit forms
│   ├── apps.py                              # App config (label="institution")
│   ├── managers.py                          # InstitutionScopedManager — .for_institution()
│   │                                        #   query helper for row-level data isolation
│   ├── middleware.py                        # InstitutionContextMiddleware — injects
│   │                                        #   current institution into request session
│   ├── context_processors.py               # Makes institution context available to all
│   │                                        #   templates (current_institution, etc.)
│   ├── templatetags/
│   │   └── institution_tags.py              # Template tags for institution-aware rendering
│   ├── migrations/                          # 5 migrations (0001–0005)
│   └── tests/                              # Comprehensive test suite (17 test modules)
│       ├── test_models.py
│       ├── test_middleware.py
│       ├── test_isolation.py
│       ├── test_context_switching.py
│       ├── test_admin_dashboard.py
│       ├── test_superadmin_dashboard.py
│       ├── test_superadmin_reports.py
│       ├── test_clinician_management.py
│       ├── test_institution_add.py
│       ├── test_selector.py
│       ├── test_sidebar_access.py
│       ├── test_patient_move.py
│       ├── test_data_migration.py
│       ├── test_feature_flag.py
│       ├── test_file_storage.py
│       ├── test_branding.py
│       └── test_pdf_branding.py
│
├── referral/                                # Phase 2 — cross-institution referral system
│   │                                        # (prefix: referral/)
│   ├── models.py                            # ReferralSent, ReferralReceived,
│   │                                        #   ReferralMessage, Notification
│   │                                        #   — dual-record pattern: both institutions
│   │                                        #   hold an immutable record linked by UUID
│   ├── views.py                             # Referral initiation, inbox, thread,
│   │                                        #   notification panel, notification bell
│   ├── urls.py                              # URL patterns under referral/
│   ├── forms.py                             # Referral initiation form
│   ├── signals.py                           # Post-save signals for notification creation
│   ├── utils.py                             # Referral helper utilities
│   ├── admin.py                             # Admin registration
│   ├── apps.py                              # App config (label="referral")
│   ├── migrations/                          # 2 migrations (0001–0002)
│   └── tests/                              # Test suite (9 test modules)
│       ├── test_models.py
│       ├── test_initiation.py
│       ├── test_lifecycle.py
│       ├── test_inbox.py
│       ├── test_thread.py
│       ├── test_notifications.py
│       ├── test_notification_bell.py
│       ├── test_notification_panel.py
│       └── test_patient_tab.py
│
├── templates/                               # Project-wide HTML templates
│   ├── 404.html                             # HTTP 404 error page
│   ├── 500.html                             # HTTP 500 error page
│   ├── src/                                 # Base layout and reusable partials
│   │   ├── base.html                        # PRIMARY base — all authenticated pages
│   │   │                                    #   extend this; includes AdminLTE shell,
│   │   │                                    #   navbar, sidebar, CSRF, JS/CSS links
│   │   ├── basic_plane.html                 # Minimal base for public/unauthenticated pages
│   │   ├── navbar.html                      # Top navigation bar partial
│   │   ├── main_sidebar_menu.html           # Left sidebar navigation partial
│   │   ├── control_sidebar.html             # Right control sidebar partial
│   │   ├── main_footer.html                 # Footer partial
│   │   ├── content_headder.html             # Page content header / breadcrumb partial
│   │   ├── main_content.html                # Main content area wrapper
│   │   ├── messages.html                    # Django messages (alerts) partial
│   │   ├── form_error.html                  # Form validation error partial
│   │   ├── logout_modal.html                # Logout confirmation modal
│   │   ├── logout_modal_simple.html         # Simplified logout modal
│   │   ├── advance_search.html              # Advanced patient search form
│   │   ├── search.html                      # Quick search partial
│   │   ├── error_404.html                   # Inline 404 fragment
│   │   └── partials/
│   │       └── delete_confirmation_modal.html  # Generic delete confirmation modal
│   │                                            #   (used via {% load delete_modal_tags %})
│   ├── patients/                            # Patient record templates
│   │   ├── index.html                       # Patient dashboard / home
│   │   ├── manager.html                     # Patient list
│   │   ├── add.html                         # Add patient form
│   │   ├── edit.html                        # Edit patient form
│   │   ├── view.html                        # Patient detail view
│   │   ├── search.html                      # Search form
│   │   ├── results.html                     # Search results
│   │   ├── search_notfound.html             # No results found state
│   │   └── partials/
│   │       ├── patients_list.html           # HTMX-swappable patient list rows
│   │       ├── patient_identification_details.html  # Patient ID card partial
│   │       ├── patient_timeline.html        # Chronological timeline partial
│   │       └── patient_view.html            # Patient summary card partial
│   ├── assessment/                          # GMA assessment templates
│   │   ├── manager.html, add.html, edit.html, view.html
│   ├── cdic_record/                         # CDIC record templates
│   │   ├── manager.html, add.html, edit.html, view.html
│   ├── gpa_record/                          # GPA record templates
│   │   ├── manager.html, add.html, edit.html, view.html
│   ├── hine/                                # HINE assessment templates
│   │   ├── manager.html, add.html, edit.html, view.html
│   ├── develop_assemnt/                     # Developmental assessment templates
│   │   ├── manager.html, add.html, edit.html, view.html
│   ├── attachment/                          # Patient attachment templates
│   │   ├── manager.html, add.html, edit.html, view.html
│   ├── bookmark/                            # Bookmark templates
│   │   ├── manager.html, add.html, edit.html, view.html
│   ├── problemlist/                         # Problem list templates
│   │   ├── manager.html, add.html, edit.html, view.html
│   │   ├── action_add.html                  # Add action to problem
│   │   ├── analysis.html                    # Problem analysis view
│   │   ├── timeline.html                    # Problem timeline
│   │   ├── delete_confirm.html              # Delete confirmation
│   │   ├── _problem_list_section.html       # Reusable section partial
│   │   └── _problem_row.html                # Reusable row partial
│   ├── institution/                         # Institution management templates
│   │   ├── add.html, edit.html              # Institution CRUD
│   │   ├── selector.html                    # Institution context switcher
│   │   ├── settings.html                    # Institution settings
│   │   ├── admin_dashboard.html             # Institution admin dashboard
│   │   ├── superadmin_dashboard.html        # Superadmin cross-institution dashboard
│   │   ├── superadmin_patient_move.html     # Patient move UI
│   │   ├── superadmin_reports.html          # Cross-institution reports
│   │   ├── clinician_list.html              # Clinician management list
│   │   ├── clinician_add.html               # Add clinician to institution
│   │   └── partials/
│   │       └── superadmin_overlay.html      # Superadmin context overlay partial
│   ├── referral/                            # Referral system templates
│   │   ├── initiate.html                    # Initiate referral form
│   │   ├── inbox.html                       # Referral inbox (received referrals)
│   │   ├── thread_panel.html                # Referral message thread
│   │   ├── patient_referrals_tab.html       # Referrals tab on patient view
│   │   ├── notification_panel.html          # Notification dropdown panel
│   │   └── notification_count_badge.html    # HTMX-polled notification count badge
│   ├── users/                               # User account templates
│   │   ├── login.html                       # Login page
│   │   ├── user_view.html                   # User profile view
│   │   ├── user_edit.html                   # Edit own profile
│   │   ├── user_change_password.html        # Change password form
│   │   ├── user_activity.html               # Personal activity log
│   │   ├── subscription_detail.html         # Subscription info
│   │   ├── subscription_expired.html        # Subscription expired gate
│   │   ├── subscription_update.html         # Update subscription
│   │   ├── contact-developer.html           # Contact developer form
│   │   ├── send_verification.html           # Email verification prompt
│   │   ├── verification_expired.html        # Expired verification link
│   │   ├── password_reset*.html             # Password reset flow (5 templates)
│   │   ├── admin/                           # Admin user management templates
│   │   │   ├── admin_dashboard.html
│   │   │   ├── user_list.html
│   │   │   ├── user_add.html
│   │   │   ├── user_edit.html
│   │   │   ├── activity_logs.html
│   │   │   └── user_activity.html
│   │   └── emails/                          # HTML email templates
│   │       ├── login_alert.html
│   │       └── verify_email.html
│   ├── help/                                # In-app help templates
│   │   ├── home.html
│   │   ├── article.html
│   │   └── article_index.html
│   ├── errors/
│   │   └── rate_limited.html               # Rate limit exceeded page
│   └── print/
│       └── patients.html                   # Print-optimised patient record
│
├── static/                                  # Project static assets (served by WhiteNoise)
│   ├── css/                                 # Custom stylesheets
│   │   ├── ndas-theme.css                   # Global NDAS theme overrides
│   │   ├── ndas-sidebar.css                 # Sidebar custom styles
│   │   ├── custom_css.css                   # Miscellaneous custom styles
│   │   ├── patient-timeline.css             # Timeline component styles
│   │   ├── auth-pages.css                   # Login / auth page styles
│   │   ├── login.css                        # Login page specific styles
│   │   ├── menu.css                         # Menu styles
│   │   ├── delete-confirmation.css          # Delete modal styles
│   │   ├── social.css                       # Social/contact page styles
│   │   └── user-templates.css               # User profile page styles
│   ├── js/                                  # Custom JavaScript
│   │   ├── main.js                          # Global app initialisation
│   │   ├── app-utils.js                     # Shared utility functions
│   │   ├── event-handlers.js                # Global DOM event handlers
│   │   ├── manager.js                       # List/table manager helpers
│   │   ├── patient-timeline.js              # Timeline rendering
│   │   ├── patient-deletion.js              # Patient delete confirmation flow
│   │   ├── video-manager.js                 # Video.js player initialisation
│   │   ├── videojs-failsafe.js              # Video.js error recovery
│   │   ├── zoomrotate.js                    # Video zoom/rotate controls
│   │   ├── rotate.js                        # Image/video rotation helper
│   │   ├── delete-confirmation.js           # Generic delete confirmation JS
│   │   ├── logout-modal.js                  # Logout modal JS
│   │   ├── login.js                         # Login page JS
│   │   └── debug.js                         # Debug utilities (dev only)
│   ├── plugins/                             # Vendored third-party libraries
│   │   ├── HTMX/
│   │   │   └── htmx.min.js                  # HTMX 1.x (partial page updates)
│   │   └── select2/                         # Select2 4.x (enhanced dropdowns)
│   │       ├── css/select2.min.css
│   │       └── js/  (+ i18n/ locale files)
│   ├── dist/                                # AdminLTE 3.2 / Bootstrap dist assets
│   │   └── img/
│   │       ├── gif/converting.gif           # Processing indicator animation
│   │       └── locked.png                   # Locked/restricted icon
│   └── img/
│       └── default_institution_logo.png     # Default logo placeholder
│
├── media/                                   # User-uploaded files (runtime, not committed)
│   ├── default/                             # Default institution uploads
│   │   ├── attachments/                     # Patient attachment files
│   │   └── videos/YYYY/MM/                  # Videos organised by year/month
│   ├── profile_pictures/YYYY/MM/            # User profile photos
│   ├── reports/logos/YYYY/MM/               # Institution logos for PDF reports
│   ├── developer_logos/YYYY/MM/             # Developer contact logos
│   ├── attachments/                         # Legacy / fallback attachment path
│   └── exports/                             # Generated export files
│       ├── institution/                     # Per-institution data exports
│       └── network/                         # Cross-institution network exports
│
├── logs/                                    # Application log files (runtime, not committed)
│   ├── django.log                           # General Django application log
│   └── security.log                         # Security events log (auth, rate limits)
│
├── tests/                                   # Project-wide integration test directory
│                                            #   (currently empty — tests live in app tests/)
│
├── scripts/                                 # Utility/maintenance scripts
│                                            #   (currently empty)
│
├── _bmad/                                   # BMAD planning agent tooling (not app code)
│   ├── core/                                # Core BMAD agent definitions
│   ├── bmm/                                 # BMAD methodology module
│   ├── bmb/                                 # BMAD brainstorming module
│   ├── cis/                                 # Change impact scoring tools
│   ├── tea/                                 # Task/effort analysis tools
│   ├── _config/                             # BMAD configuration
│   └── _memory/                             # BMAD persistent memory
│
├── _bmad-output/                            # BMAD-generated planning artifacts
│   ├── project-context.md                   # Living project context (92 rules)
│   └── planning-artifacts/
│       ├── prd.md                           # Product Requirements Document (v3, FR1–FR70)
│       └── architecture.md                  # Architecture Decision Record (Phase 2)
│
├── docs/                                    # Project documentation (this directory)
│
├── backup and restore/                      # Database backup/restore utilities
│   ├── backup_tables.py                     # Backup specific tables to JSON
│   ├── restore_tables.py                    # Restore tables from JSON backups
│   ├── verify_restore.py                    # Verify restore integrity
│   └── *.json                               # JSON backup snapshots
│
├── env files/                               # Environment variable file templates
│
├── temp_documents/                          # Temporary working documents (not committed)
│
└── venv/                                    # Python virtual environment (not committed)
```

---

## Critical Entry Points

| Entry Point | Path | Purpose |
|-------------|------|---------|
| Django CLI | `manage.py` | All management commands (`runserver`, `migrate`, `test`, etc.) |
| WSGI server | `ndas/wsgi.py` | Production WSGI gateway (gunicorn/uwsgi target) |
| ASGI server | `ndas/asgi.py` | ASGI gateway (for async use if adopted) |
| Root URLs | `ndas/urls.py` | Dispatches every URL to an app's urlconf |
| Root app catch-all | `patients/urls.py` | Receives all unmatched URLs (routed from `path("", include("patients.urls"))`) |
| Settings | `ndas/settings.py` | Single settings module; reads all secrets from `.env` / environment |

---

## Key Integration Points

### How Apps Connect

- **patients** is the root app — it receives all non-prefixed URLs and is the hub that other apps link back to (every assessment model has a `ForeignKey` to `Patient`).
- **video** stores `Video` records linked to `Patient` via FK; `GMAssessment` in `patients` references `video.Video` via `video_file` FK.
- **reports** reads `Patient` and all assessment models to produce PDF/Excel output; no FK to reports from patients.
- **problemlist** has `Problem.patient` FK back to `patients.Patient`.
- **institution** provides the `Institution` model that `Patient.institution` and `CustomUser.institution` foreign-key into. `InstitutionScopedManager` (in `institution/managers.py`) is imported into `patients/models.py` to scope querysets.
- **referral** has FKs to `Institution` (sending/receiving) and stores a frozen snapshot of `Patient` data; `Notification` links to `CustomUser`.
- **users** provides `CustomUser` which every model's `added_by`/`last_edit_by` tracking fields reference.

### Middleware Stack (order in settings.py)

1. `SecurityMiddleware`
2. `WhiteNoiseMiddleware`
3. `CSPMiddleware` (custom — `ndas/custom_codes/security_middleware.py`)
4. `AdditionalSecurityHeadersMiddleware` (custom)
5. `SessionMiddleware`
6. `CommonMiddleware`
7. `CsrfViewMiddleware`
8. `AuthenticationMiddleware`
9. `UserActivityMiddleware` (custom — `users/middleware.py`; auto-populates `added_by`/`last_edit_by`)
10. `MessageMiddleware`
11. `XFrameOptionsMiddleware`
12. `UserAgentMiddleware` (custom — `users/middleware.py`)
13. `SubscriptionCheckMiddleware` (custom — `users/middleware.py`)
14. `SecurityHeadersValidationMiddleware` (custom — production only)

---

## Template Hierarchy

All authenticated pages follow a two-level inheritance chain:

```
templates/src/base.html                    ← AdminLTE 3.2 shell, navbar, sidebar,
│                                             all CDN/local CSS+JS, CSRF meta tag
├── templates/patients/manager.html        ← typical leaf template ({% extends 'src/base.html' %})
├── templates/assessment/view.html
├── templates/institution/admin_dashboard.html
└── ... (all app templates follow the same pattern)

templates/src/basic_plane.html             ← stripped base for public/unauthenticated pages
├── templates/users/login.html
├── templates/users/password_reset*.html
└── templates/users/subscription_expired.html
```

### Naming Convention for Leaf Templates

| Template name | Purpose |
|---------------|---------|
| `manager.html` | List/table view of a model |
| `add.html` | Create form |
| `edit.html` | Update form |
| `view.html` | Read-only detail view |

### Partials

Templates named with a leading underscore (`_problem_row.html`) or placed in a `partials/` subdirectory are reusable fragments, often HTMX targets. They are not full pages and do not extend a base.

---

## Static Files Organization

```
static/
├── css/          Custom NDAS stylesheets (theme, sidebar, components)
├── js/           Custom JavaScript (player, timeline, delete flows, utilities)
├── plugins/      Vendored libraries (HTMX, Select2)
├── dist/img/     AdminLTE bundled images (loading GIF, locked icon)
└── img/          Project images (default institution logo)
```

AdminLTE 3.2, Bootstrap 4.6, Font Awesome 6.4, and Video.js are loaded from CDN in `src/base.html` and are **not** present in `static/`. Do not replace or version-bump these CDN references.

WhiteNoise serves everything under `static/` in production. `collectstatic` outputs to a directory configured in `settings.py`.

---

## Media Storage

```
media/
├── default/              Institution-scoped uploads for the "default" institution
│   ├── attachments/      Patient attachment files
│   └── videos/YYYY/MM/   Videos, partitioned by upload year/month
├── profile_pictures/     User profile photos (YYYY/MM/ sub-path)
├── reports/logos/        Institution logos embedded in generated PDFs
├── developer_logos/      Logos for developer contact records
├── exports/              Generated export files (institution-scoped / network)
└── attachments/          Legacy fallback path (pre-institution scoping)
```

Upload paths are computed by `get_institution_attachment_path()` in `ndas/custom_codes/validators.py`, which namespaces files under the institution slug. Size and extension limits are enforced at validation time using values from `settings.FILE_UPLOAD_LIMITS` and `settings.ALLOWED_FILE_EXTENSIONS`.

The `media/` directory is excluded from version control. In development, files are served via `protected_media_view` (institution-scoped access check). In production, media must be served by a reverse proxy with the same access controls.
