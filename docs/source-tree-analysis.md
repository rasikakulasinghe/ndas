# Source Tree Analysis - NDAS

**Generated:** 2025-12-29
**Project:** Neurodevelopmental Assessment System (NDAS)
**Structure:** Django Monolith

---

## Project Root Structure

```
NDAS/
├── manage.py                          # Django management script (entry point)
├── db.sqlite3                         # SQLite database (development)
├── .env                               # Environment configuration
├── deploy.sh                          # Deployment automation script
├── CLAUDE.md                          # AI assistant guidance
├── AGENTS.md                          # Agent-specific instructions
├── DEPLOYMENT.md                      # Deployment documentation
│
├── ndas/                              # Django project configuration
│   ├── __init__.py
│   ├── settings.py                    # ⚙️ Core settings (DB, security, middleware)
│   ├── urls.py                        # 🔗 Root URL routing
│   ├── wsgi.py                        # WSGI entry point (production)
│   ├── asgi.py                        # ASGI entry point (async support)
│   ├── views.py                       # Global views (404/500 handlers, debug)
│   │
│   ├── custom_codes/                  # 🔧 Custom utilities & base classes
│   │   ├── Custom_abstract_class.py   # TimeStampedModel, UserTrackingMixin
│   │   ├── choice.py                  # TextChoices for all dropdowns
│   │   ├── validators.py              # Field validators, sanitizers
│   │   ├── sanitization.py            # HTML sanitization (bleach)
│   │   ├── custom_methods.py          # Utility functions
│   │   ├── ndas_enums.py              # Enumerations (PtStatus, etc.)
│   │   ├── delete_helpers.py          # Entity deletion utilities
│   │   ├── security_middleware.py     # Custom security headers, CSP
│   │   └── error_handlers.py          # View error decorators
│   │
│   └── templatetags/                  # Custom Django template tags
│       └── ...
│
├── patients/                          # 🏥 Patient Records & Assessments (Root URL)
│   ├── models.py                      # Patient, GMAssessment, CDIC, HINE, DA, GPA
│   ├── views.py                       # Patient CRUD, assessment management
│   ├── forms.py                       # Django forms with validation
│   ├── urls.py                        # URL routing (root /)
│   ├── admin.py                       # Django admin configuration
│   ├── tests/                         # Unit and integration tests
│   └── migrations/                    # Database migrations
│
├── users/                             # 👤 Authentication & User Management
│   ├── models.py                      # CustomUser, UserActivityLog, UserSession
│   ├── views.py                       # Login, registration, profile, admin
│   ├── forms.py                       # Auth forms (login, password reset)
│   ├── urls.py                        # /users/* routing
│   ├── middleware.py                  # UserActivityMiddleware, SubscriptionCheckMiddleware
│   ├── tests/                         # User-related tests
│   └── migrations/                    # Database migrations
│
├── video/                             # 🎥 Video Upload & Management
│   ├── models.py                      # Video model
│   ├── views.py                       # Video CRUD, player views
│   ├── forms.py                       # Video upload forms
│   ├── urls.py                        # /video/* routing
│   ├── tests/                         # Video functionality tests
│   └── migrations/                    # Database migrations
│
├── reports/                           # 📊 PDF/Excel Report Generation
│   ├── models.py                      # ReportTemplate, ReportConfig
│   ├── views.py                       # Report builder, download, history
│   ├── forms.py                       # Report configuration forms
│   ├── urls.py                        # /reports/* routing
│   │
│   ├── utils/                         # Report generation utilities
│   │   ├── pdf_generator.py           # BasePDFGenerator, assessment PDFs
│   │   └── excel_generator.py         # ExcelReportGenerator
│   │
│   ├── static/                        # Report-specific assets
│   ├── templates/                     # Report templates
│   ├── tests/                         # Report generation tests
│   └── migrations/                    # Database migrations
│
├── problemlist/                       # 📝 Problem Tracking System
│   ├── models.py                      # Problem, ProblemAction
│   ├── views.py                       # Problem CRUD, timeline, analysis
│   ├── forms.py                       # Problem forms
│   ├── urls.py                        # /problems/* routing
│   ├── tests/                         # Problem list tests
│   └── migrations/                    # Database migrations
│
├── templates/                         # 🎨 Django Templates (Global)
│   ├── src/                           # Base templates
│   │   ├── base.html                  # Main layout (AdminLTE)
│   │   ├── basic_plane.html           # Public layout
│   │   ├── login.html                 # Login page
│   │   └── partials/                  # Reusable components
│   │       ├── navbar.html
│   │       ├── sidebar.html
│   │       ├── footer.html
│   │       └── delete_confirmation_modal.html
│   │
│   ├── patients/                      # Patient app templates
│   │   ├── manager.html               # Patient list
│   │   ├── add.html                   # Add patient
│   │   ├── edit.html                  # Edit patient
│   │   └── view.html                  # Patient detail
│   │
│   ├── assessment/                    # GMA assessment templates
│   ├── cdic_record/                   # CDIC templates
│   ├── hine/                          # HINE templates
│   ├── develop_assemnt/               # DA templates
│   ├── gpa_record/                    # GPA templates
│   ├── attachment/                    # Attachment templates
│   ├── bookmark/                      # Bookmark templates
│   ├── users/                         # User templates
│   ├── video/                         # Video templates
│   ├── reports/                       # Report templates
│   ├── problemlist/                   # Problem list templates
│   ├── errors/                        # Error pages (404, 500)
│   ├── help/                          # Help system templates
│   └── print/                         # Print-optimized templates
│
├── static/                            # 📦 Static Files
│   ├── css/                           # Custom CSS
│   │   ├── main.css                   # Main stylesheet
│   │   └── custom.css                 # Custom overrides
│   │
│   ├── js/                            # JavaScript
│   │   ├── main.js                    # Main JS file
│   │   ├── form-handlers.js           # Form interaction handlers
│   │   ├── confirmation-handlers.js   # Delete confirmation
│   │   └── password-toggle-handlers.js # Password visibility
│   │
│   ├── plugins/                       # Third-party libraries
│   │   ├── HTMX/                      # HTMX library
│   │   └── select2/                   # Select2 plugin
│   │
│   └── dist/                          # AdminLTE 3.2 distribution
│       ├── css/
│       ├── js/
│       └── img/
│
├── media/                             # 📁 User Uploads
│   ├── videos/                        # Video files (up to 2GB each)
│   ├── attachments/                   # Patient attachments
│   ├── profile_pictures/              # User profile photos
│   ├── reports/                       # Generated reports
│   └── developer_logos/               # Developer contact images
│
├── logs/                              # 📋 Application Logs
│   ├── django.log                     # General application log
│   └── security.log                   # Security events log
│
├── docs/                              # 📚 Generated Documentation
│   ├── index.md                       # Master index (entry point)
│   ├── project-overview.md
│   ├── technology-stack.md
│   ├── api-contracts.md
│   ├── data-models.md
│   ├── source-tree-analysis.md
│   ├── architecture.md
│   └── project-scan-report.json       # Workflow state file
│
├── openspec/                          # OpenSpec Documentation
│   ├── AGENTS.md                      # OpenSpec agent instructions
│   ├── specs/                         # Spec files
│   └── changes/                       # Change proposals
│
├── venv/                              # Python virtual environment (ignored)
├── db backup/                         # Database backups
├── backup and restore/                # Backup scripts
├── env files/                         # Environment file templates
└── scripts/                           # Utility scripts

```

---

## Critical Directories Explained

### Core Application (`ndas/`)
**Purpose:** Django project configuration and shared utilities

**Entry Points:**
- `manage.py` - CLI management interface
- `settings.py` - Application configuration hub
- `urls.py` - Root URL dispatcher
- `wsgi.py` - Production WSGI server entry

**Key Components:**
- `custom_codes/` - Shared utilities, validators, base models
  - All custom apps import from here
  - Provides `TimeStampedModel` and `UserTrackingMixin` base classes
  - Centralized validators prevent code duplication

**Middleware Stack Location:** `settings.py` (14-layer stack)

---

### Django Apps

#### `patients/` - Primary Application (Root URL)
**URL Base:** `/` (root of site)

**Responsibilities:**
- Patient record management (CRUD)
- All assessment types (GMA, CDIC, HINE, DA, GPA)
- Bookmarks and attachments
- Help system
- Dashboard and search

**Models:** 11 models (50% of application data)

**Routes:** 100+ URL patterns (largest app)

**Templates:** Most comprehensive template set

---

#### `users/` - Authentication & User Management
**URL Base:** `/users/`

**Responsibilities:**
- Login/logout
- User profiles and settings
- Password reset (rate-limited)
- Email verification
- Session management
- User activity logging
- Admin user management
- Subscription handling

**Models:** 5 models

**Middleware:** 2 custom middleware classes
- `UserActivityMiddleware` - Auto-tracks user changes
- `SubscriptionCheckMiddleware` - Enforces subscription limits

**Security:** Password validation, failed login tracking, account lockout

---

#### `video/` - Video Management
**URL Base:** `/video/`

**Responsibilities:**
- Video file uploads (up to 2GB)
- Video metadata extraction
- Video player integration (Video.js)
- Video library management

**Models:** 1 model (Video)

**File Handling:**
- Supports: MP4, MOV, AVI, MKV, WEBM
- MIME validation via python-magic
- Metadata extraction (duration, resolution, codec, fps, bitrate)

---

#### `reports/` - Report Generation
**URL Base:** `/reports/`

**Responsibilities:**
- PDF generation (ReportLab/WeasyPrint)
- Excel generation (openpyxl)
- Report templates and configurations
- Assessment-specific PDF downloads
- Report history and management

**Models:** 2 models

**Utilities:**
- `utils/pdf_generator.py` - PDF generation classes
- `utils/excel_generator.py` - Excel export with anonymization

---

#### `problemlist/` - Problem Tracking
**URL Base:** `/problems/`

**Responsibilities:**
- Clinical problem tracking
- Problem timeline and actions
- Status management (HTMX-powered)
- Problem analysis and export

**Models:** 2 models

**HTMX Integration:** Dynamic status updates without page reload

---

### Templates (`templates/`)
**Location:** Project root (global templates)

**Structure:**
- `src/` - Base layouts (AdminLTE)
- App-specific folders - Each app's templates
- `partials/` - Reusable components (navbar, sidebar, modals)

**Template Inheritance:**
```
base.html (authenticated users)
  ├── manager.html (list views)
  ├── view.html (detail views)
  ├── add.html (create forms)
  └── edit.html (edit forms)

basic_plane.html (public/auth pages)
  └── login.html
```

**Template Engine:** Django Templates

**CSS Framework:** AdminLTE 3.2 + Bootstrap 4.6

---

### Static Files (`static/`)
**Collection Command:** `python manage.py collectstatic`

**Development:** Served by Django (`/static/`)

**Production:** Served by WhiteNoise (`staticfiles/`)

**Structure:**
- `css/` - Custom stylesheets
- `js/` - Custom JavaScript (CSP-compliant)
- `plugins/` - HTMX, Select2
- `dist/` - AdminLTE distribution

**CDN Resources:** Font Awesome 6.4, Video.js, Google Fonts

---

### Media Files (`media/`)
**Serving:** Django FileSystemStorage

**Access Control:**
- Authenticated users only
- Permission checks in views
- No direct file serving (routed through Django)

**File Limits:**
- Videos: 2GB
- Documents: 100MB
- Images: 10MB
- Profile Pictures: 5MB

**Storage Path:** `BASE_DIR / 'media'`

---

### Logs (`logs/`)
**Log Files:**
- `django.log` - Application events (15MB rotation, 10 backups)
- `security.log` - Security events (authentication, authorization)

**Log Levels:**
- Development: DEBUG
- Production: INFO

**Logged Events:**
- Django framework events
- User authentication/authorization
- User activity (via middleware)
- Security incidents

---

### Documentation (`docs/`)
**Purpose:** AI-generated project documentation

**Master Index:** `index.md` (primary entry point)

**Generated Files:**
- `technology-stack.md` - Tech stack details
- `api-contracts.md` - All API endpoints
- `data-models.md` - Database schema
- `source-tree-analysis.md` - This file
- `architecture.md` - System architecture

**Scan State:** `project-scan-report.json` - Workflow resume data

---

## Application Flow

### User Journey
```
1. Login (/users/login/)
   ↓
2. Dashboard (/)
   ↓
3. Patient Management
   ├── Search/Filter
   ├── View Patient (/patient/view/<pk>/)
   ├── Add/Edit Patient
   └── Assessments
       ├── Add GMA (/assessment/add/<ptid>/<fid>/)
       ├── Add CDIC (/cdic/add/<pid>/)
       ├── Add HINE (/hine/add/<pid>/)
       └── Add DA (/da/add/<pid>/)
   ↓
4. Video Management (/video/)
   ├── Upload Video
   └── Link to Assessment
   ↓
5. Reports (/reports/)
   ├── Generate PDF
   └── Export Excel
```

### Request Flow
```
Browser Request
   ↓
Django URL Dispatcher (urls.py)
   ↓
Middleware Stack (14 layers)
   ├── SecurityMiddleware
   ├── CSPMiddleware
   ├── AuthenticationMiddleware
   ├── UserActivityMiddleware (custom)
   └── SubscriptionCheckMiddleware (custom)
   ↓
View Function
   ├── Authentication Check (@login_required)
   ├── Rate Limiting (@ratelimit)
   ├── HTTP Method Check (@require_http_methods)
   ├── Database Query (Django ORM)
   └── Business Logic
   ↓
Template Rendering
   ├── Context Data
   ├── Template Tags
   └── AdminLTE Components
   ↓
Response
```

---

## Integration Points

### Database
- **Development:** SQLite (`db.sqlite3`)
- **Production:** PostgreSQL (via `.env` configuration)
- **Migrations:** `<app>/migrations/`

### Cache
- **Development:** LocMem cache
- **Production:** Redis (optional, via `REDIS_URL`)
- **Usage:** Sessions, rate limiting

### Email
- **Development:** Console backend (printed to terminal)
- **Production:** SMTP (Gmail default, configurable)

### File Storage
- **Static:** WhiteNoise (production), Django dev server (development)
- **Media:** FileSystemStorage
- **Future:** S3-compatible storage possible

---

## Testing Structure

### Test Locations
```
patients/tests/
users/tests/
video/tests/
reports/tests/
problemlist/tests/
```

### Test Command
```bash
python manage.py test [app_name]
```

### Test Database
- In-memory SQLite (fast)
- Automatically created and destroyed
- Isolated from development database

---

## Deployment Structure

### Entry Points
- **WSGI:** `ndas/wsgi.py` (Gunicorn, uWSGI)
- **ASGI:** `ndas/asgi.py` (Daphne, Uvicorn - async support)

### Static Files Collection
```bash
python manage.py collectstatic --no-input
```
Output: `staticfiles/` directory

### Database Migrations
```bash
python manage.py migrate
```

### Process Management
- **Recommended:** systemd or supervisor
- **Web Server:** Gunicorn behind Nginx/Apache
- **Workers:** Optional Celery workers (future)

---

## File Naming Conventions

### Python Files
- `models.py` - Django models (one per app)
- `views.py` - View functions/classes
- `forms.py` - Django forms
- `urls.py` - URL routing
- `admin.py` - Admin interface configuration
- `middleware.py` - Custom middleware
- `tests.py` or `tests/` - Test cases

### Templates
- `manager.html` - List views
- `add.html` - Create forms
- `edit.html` - Edit forms
- `view.html` - Detail views
- `base.html` - Layout base

### Static Files
- `main.css` - Main stylesheet
- `main.js` - Main JavaScript
- `*-handlers.js` - Specific functionality handlers

---

## Configuration Files

### Environment (`.env`)
```
SECRET_KEY=...
DEBUG=True/False
ALLOWED_HOSTS=...
DB_ENGINE=...
REDIS_URL=...
```

### Django Settings (`ndas/settings.py`)
- Database configuration
- Middleware stack
- Security settings (CSP, CORS, etc.)
- File upload limits
- Cache configuration
- Logging configuration

### Deployment (`deploy.sh`)
- Environment setup
- Dependency installation
- Database migration
- Static file collection
- Service restart

---

## Import Hierarchy

### Dependency Flow
```
ndas/custom_codes/  (base utilities)
    ↓
Django Apps (patients, users, video, reports, problemlist)
    ↓
Templates (reference models and views)
```

### Circular Import Prevention
- `Custom_abstract_class.py` has no app dependencies
- Models import from `custom_codes/` only
- Views import models, forms
- Forms import models
- Use `django.apps.apps.get_model()` for reverse lookups

---

## Code Organization Principles

### DRY (Don't Repeat Yourself)
- **Base Models:** `TimeStampedModel`, `UserTrackingMixin`
- **Validators:** Centralized in `custom_codes/validators.py`
- **Choices:** All choices in `custom_codes/choice.py`
- **Utilities:** Shared functions in `custom_codes/custom_methods.py`

### Separation of Concerns
- **Models:** Data structure and business logic
- **Views:** Request handling and response
- **Forms:** Validation and data cleaning
- **Templates:** Presentation layer
- **Custom Codes:** Cross-cutting concerns

### Security by Design
- Input validation at model level
- CSRF protection on all forms
- Rate limiting on sensitive endpoints
- File upload validation (MIME + size)
- Content Security Policy (CSP)

---

## Development Workflow

### Local Setup
```bash
1. Clone repository
2. Create virtual environment: python -m venv venv
3. Activate: venv\Scripts\activate (Windows)
4. Install dependencies: pip install -r requirements.txt
5. Copy .env template and configure
6. Run migrations: python manage.py migrate
7. Create superuser: python manage.py createsuperuser
8. Run dev server: python manage.py runserver
```

### Making Changes
```bash
1. Create feature branch
2. Make code changes
3. Create migrations (if models changed): python manage.py makemigrations
4. Run tests: python manage.py test
5. Test manually: python manage.py runserver
6. Commit changes (include migrations)
7. Push and create PR
```

---

## Performance Considerations

### Query Optimization
- Use `select_related()` for ForeignKey
- Use `prefetch_related()` for reverse ForeignKey
- Use `only()` to limit fields
- Use `defer()` to exclude large fields

### Caching Strategy
- Session caching (default)
- Query result caching (manual, per-view)
- Template fragment caching (future)

### Static File Optimization
- WhiteNoise compression (production)
- AdminLTE pre-minified
- CDN for external resources

---

## Future Directory Additions

### Potential Expansions
- `api/` - REST API (Django REST Framework)
- `tasks/` - Background tasks (Celery)
- `channels/` - WebSocket support (Django Channels)
- `i18n/` - Internationalization
- `analytics/` - Data analytics app
- `notifications/` - Notification system

---

## Notes

- **Ignored in Git:** `venv/`, `__pycache__/`, `*.pyc`, `.env`, `db.sqlite3`, `media/`, `staticfiles/`, `logs/`
- **Backup Location:** `db backup/` (manual backups, not in git)
- **Media Security:** Files served through Django views (no direct access)
- **Static Collection:** Run `collectstatic` before each deployment
- **Migration Discipline:** All migrations committed to version control
