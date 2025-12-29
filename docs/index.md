# NDAS Project Documentation

**Generated:** 2025-12-29
**Project:** Neurodevelopmental Assessment System (NDAS)
**Type:** Django Web Application (Monolith)
**Domain:** Medical / Healthcare

---

## 🎯 Quick Start

**This is the primary entry point for AI-assisted development.**

All documentation is generated from an **exhaustive scan** of the NDAS codebase. Use this index to navigate to specific technical details.

---

## 📋 Project Overview

### What is NDAS?

NDAS is a Django-based web application for managing neurodevelopmental assessments in clinical settings. The system handles:

- **Patient Records** - Comprehensive patient data with multiple medical identifiers
- **Video-Based Assessments** - General Movement Assessment (GMA) with video analysis
- **Standardized Examinations** - HINE, CDIC, Developmental, and General Pediatric Assessments
- **Clinical Problem Tracking** - Problem list management with timeline and actions
- **Report Generation** - PDF and Excel exports with anonymization options

### Architecture Type

**Monolithic Django Application** - Server-side rendered with AdminLTE 3.2 UI

**Primary Language:** Python 3.x
**Framework:** Django 4.2.16
**Database:** PostgreSQL (production) / SQLite (development)
**Frontend:** AdminLTE 3.2 + Bootstrap 4.6 + HTMX

---

## 🗂️ Documentation Structure

### Core Documentation

| Document | Purpose | Key Information |
|----------|---------|-----------------|
| **[Architecture](./architecture.md)** | System architecture and design patterns | MVT pattern, component architecture, deployment, security architecture |
| **[Technology Stack](./technology-stack.md)** | Complete technology inventory | All technologies, versions, configurations, dependencies |
| **[API Contracts](./api-contracts.md)** | All HTTP endpoints | 150+ endpoints across 5 apps, request/response formats, authentication |
| **[Data Models](./data-models.md)** | Database schema | 21 models, relationships, validation rules, query patterns |
| **[Source Tree Analysis](./source-tree-analysis.md)** | Directory structure and file organization | Annotated file tree, critical directories, import hierarchy |

### Existing Project Documentation

| Document | Location | Purpose |
|----------|----------|---------|
| **CLAUDE.md** | Project root | AI assistant guidance, architecture patterns, quick commands |
| **AGENTS.md** | Project root | Agent-specific instructions and context |
| **DEPLOYMENT.md** | Project root | Deployment procedures and configuration |
| **openspec/AGENTS.md** | openspec/ | OpenSpec change proposal workflow |

---

## 🏗️ Architecture at a Glance

### Repository Type
**Monolith** - Single cohesive Django application

### Technology Summary

| Category | Technology |
|----------|-----------|
| Backend Framework | Django 4.2.16 |
| Language | Python 3.x |
| Database | PostgreSQL / SQLite |
| Frontend | AdminLTE 3.2 + Bootstrap 4.6 |
| JavaScript | HTMX + Video.js |
| Security | django-csp, bleach, rate limiting |
| Reports | ReportLab / WeasyPrint (PDF), openpyxl (Excel) |

### Django Apps (5 Apps)

```
ndas/              # Project configuration & utilities
  └── custom_codes/  # Shared utilities, base classes, validators

patients/          # Main app (root URL /) - 11 models
  ├── Patient records
  ├── 5 assessment types (GMA, CDIC, HINE, DA, GPA)
  ├── Attachments & Bookmarks
  └── Help system

users/             # Authentication (/users/) - 5 models
  ├── Login/logout, password reset
  ├── User profiles & admin
  ├── Activity logging & sessions
  └── Subscription management

video/             # Video management (/video/) - 1 model
  ├── Video uploads (up to 2GB)
  └── Video.js player

reports/           # Report generation (/reports/) - 2 models
  ├── PDF reports (assessment-specific)
  └── Excel exports (customizable)

problemlist/       # Problem tracking (/problems/) - 2 models
  ├── Clinical problem lists
  └── Timeline & actions (HTMX)
```

---

## 📊 Quick Reference

### Project Statistics

- **Total Models:** 21 (across 5 Django apps)
- **API Endpoints:** 150+
- **URL Patterns:** 100+ (patients app alone)
- **Middleware Layers:** 14 (security-focused)
- **Django Apps:** 5 (patients, users, video, reports, problemlist)
- **Primary Templates:** 50+ (AdminLTE-based)

### Key Features

**Security:**
- Content Security Policy (CSP) with nonce-based scripts
- Rate limiting (24 protected endpoints)
- CSRF protection on all forms
- Session timeout (1 hour)
- Audit logging (UserActivityLog)
- Input sanitization (XSS prevention)

**File Upload:**
- Videos: 2GB max (.mp4, .mov, .avi, .mkv, .webm)
- Documents: 100MB max
- Images: 10MB max
- MIME validation via python-magic

**Medical Domain:**
- Patient identifiers: BHT, NNC, PTC, PC, PIN, Disk No.
- Assessment types: GMA, HINE, CDIC, DA, GPA
- Validation: Birth weight (300-8000g), APGAR (0-10), POG (20-44 weeks)

---

## 🔍 Finding What You Need

### For API Integration
→ **[API Contracts](./api-contracts.md)** - All 150+ endpoints with request/response formats

### For Database Work
→ **[Data Models](./data-models.md)** - Complete schema with 21 models, relationships, validation rules

### For Architecture Decisions
→ **[Architecture](./architecture.md)** - System design, security model, deployment architecture

### For Technology Questions
→ **[Technology Stack](./technology-stack.md)** - All technologies, versions, configurations

### For File Navigation
→ **[Source Tree Analysis](./source-tree-analysis.md)** - Annotated directory structure

### For Development Patterns
→ **CLAUDE.md** (project root) - Coding patterns, quick commands, architecture rules

---

## 🚀 Getting Started

### Development Setup

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate environment (Windows)
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
# Copy .env template and configure SECRET_KEY, database settings

# 5. Run migrations
python manage.py migrate

# 6. Create superuser
python manage.py createsuperuser

# 7. Run development server
python manage.py runserver
```

### Key Commands

```bash
# Database
python manage.py makemigrations [app_name]
python manage.py migrate [app_name]

# Testing
python manage.py test [app_name]

# Static files (production)
python manage.py collectstatic --no-input

# Run server
python manage.py runserver
```

---

## 📂 Directory Overview

```
NDAS/
├── manage.py                  # Django CLI entry point
├── db.sqlite3                 # Development database
├── .env                       # Environment configuration (not in git)
│
├── ndas/                      # Django project config
│   ├── settings.py            # Core settings (DB, security, middleware)
│   ├── urls.py                # Root URL routing
│   ├── custom_codes/          # Shared utilities (validators, base models)
│   └── templatetags/          # Custom template tags
│
├── patients/                  # Primary app (root URL /)
│   ├── models.py              # 11 models (Patient, assessments, etc.)
│   ├── views.py               # 100+ views
│   ├── urls.py                # Patient/assessment routing
│   └── migrations/            # Database migrations
│
├── users/                     # Authentication & admin (/users/)
│   ├── models.py              # CustomUser, activity logs, sessions
│   ├── views.py               # Auth, profile, admin views
│   ├── middleware.py          # UserActivityMiddleware, SubscriptionCheck
│   └── migrations/
│
├── video/                     # Video management (/video/)
│   ├── models.py              # Video model
│   ├── views.py               # Upload, player views
│   └── migrations/
│
├── reports/                   # Report generation (/reports/)
│   ├── models.py              # Report templates & configs
│   ├── utils/                 # PDF & Excel generators
│   └── migrations/
│
├── problemlist/               # Problem tracking (/problems/)
│   ├── models.py              # Problem, ProblemAction
│   └── migrations/
│
├── templates/                 # Django templates (global)
│   ├── src/                   # Base layouts (AdminLTE)
│   ├── patients/              # Patient templates
│   ├── users/                 # User templates
│   └── [other apps]/
│
├── static/                    # Static files
│   ├── css/                   # Custom stylesheets
│   ├── js/                    # Custom JavaScript
│   ├── plugins/               # HTMX, Select2
│   └── dist/                  # AdminLTE 3.2
│
├── media/                     # User uploads
│   ├── videos/                # Video files (up to 2GB)
│   ├── attachments/           # Patient attachments
│   └── profile_pictures/      # User photos
│
├── docs/                      # Generated documentation (this folder)
│   ├── index.md               # This file (master index)
│   ├── architecture.md
│   ├── technology-stack.md
│   ├── api-contracts.md
│   ├── data-models.md
│   └── source-tree-analysis.md
│
└── logs/                      # Application logs
    ├── django.log             # General logs
    └── security.log           # Security events
```

---

## 🔐 Security Features

### Multi-Layer Security

1. **Middleware Stack (14 layers)**
   - SecurityMiddleware, CSPMiddleware, CSRF, Authentication
   - Custom: UserActivityMiddleware, SubscriptionCheckMiddleware

2. **Content Security Policy (CSP)**
   - Nonce-based script execution (production)
   - No `unsafe-inline` for scripts
   - Frame embedding blocked

3. **Rate Limiting**
   - 10 requests/minute: Create/edit operations
   - 5 requests/minute: Delete operations
   - 24 protected endpoints

4. **Input Validation**
   - Model-level validators
   - Form-level validation
   - XSS sanitization (bleach library)
   - File MIME validation (python-magic)

5. **Authentication & Sessions**
   - 1-hour session timeout
   - Session expires on browser close
   - Failed login tracking & account lockout
   - Password validation (12+ chars, complexity)

6. **Audit Logging**
   - All CRUD operations logged (UserActivityLog)
   - IP address, user agent, timestamps
   - Change tracking (before/after values)

---

## 🏥 Medical Domain Features

### Patient Identifiers (All Optional, Indexed)
- **BHT** - Bed Head Ticket (hospital ID)
- **NNC** - National Neonatal Care number
- **PTC** - Perinatal Transport Card
- **PC** - Patient Card number
- **PIN** - Patient Identification Number
- **Disk No** - Physical file number

### Assessment Types
| Type | Full Name | Purpose |
|------|-----------|---------|
| **GMA** | General Movement Assessment | Video-based neurodevelopmental assessment |
| **HINE** | Hammersmith Infant Neurological Examination | Neurological scoring (0-78) |
| **CDIC** | Child Development Inventory Checklist | Developmental milestones |
| **DA** | Developmental Assessment | General development tracking |
| **GPA** | General Paediatric Assessment | Physical examination & vitals |

### Validation Rules
| Field | Validation |
|-------|------------|
| Birth Weight | 300-8000g (POG-specific enhanced) |
| APGAR Scores | 0-10 (both 1-min and 5-min) |
| Gestational Age | 20-44 weeks + 0-6 days |
| HINE Score | 0-78 |

---

## 🎨 Frontend Architecture

### UI Framework
**AdminLTE 3.2** - Bootstrap-based admin template

**CSS Framework:** Bootstrap 4.6
**Icons:** Font Awesome 6.4
**JavaScript:** HTMX (dynamic updates), Video.js (video player)

### Template Structure
```
Base Templates:
  ├── src/base.html (authenticated users)
  └── src/basic_plane.html (public/auth pages)

App Templates:
  ├── manager.html (list views)
  ├── view.html (detail views)
  ├── add.html (create forms)
  └── edit.html (edit forms)

Partials:
  ├── navbar.html
  ├── sidebar.html
  ├── footer.html
  └── delete_confirmation_modal.html
```

### Template Engine
Django Templates (server-side rendering)

---

## 📈 Performance Optimization

### Database
- **Connection Pooling:** 300 seconds (production)
- **Indexes:** All unique identifiers, search fields, dates
- **Query Optimization:** `select_related()`, `prefetch_related()`

### Static Files
- **WhiteNoise:** Gzip compression, far-future expires
- **AdminLTE:** Pre-minified CSS/JS
- **CDNs:** Font Awesome, Video.js

### Caching
- **Sessions:** Redis (production) / LocMem (development)
- **Rate Limiting:** Cache-backed

---

## 🧪 Testing

### Test Structure
```
<app>/tests/
  ├── test_models.py        # Model validation, methods
  ├── test_views.py         # HTTP responses, auth
  ├── test_forms.py         # Form validation
  └── test_integration.py   # End-to-end workflows
```

### Running Tests
```bash
# All tests
python manage.py test

# Specific app
python manage.py test patients

# Specific test file
python manage.py test patients.tests.test_models
```

### Test Database
In-memory SQLite (fast, isolated)

---

## 🚢 Deployment

### Recommended Stack
```
Internet (HTTPS:443)
    ↓
Nginx (Reverse Proxy, SSL Termination)
    ↓
Gunicorn (WSGI Server, 2-4 workers)
    ↓
Django Application (NDAS)
    ↓
PostgreSQL Database + Redis Cache
```

### Environment Configuration
Create `.env` file with:
```
SECRET_KEY=<your-secret-key>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=ndas_db
DB_USER=ndas_user
DB_PASSWORD=<secure-password>
DB_HOST=localhost
DB_PORT=5432

# Cache (optional)
REDIS_URL=redis://localhost:6379/0

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<email>
EMAIL_HOST_PASSWORD=<app-password>

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### Deployment Commands
```bash
# Collect static files
python manage.py collectstatic --no-input

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start Gunicorn
gunicorn ndas.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

**See:** `DEPLOYMENT.md` (project root) for complete deployment guide

---

## 🔄 Development Workflow

### Adding New Features

1. **Model Changes:**
   ```bash
   # Edit models.py
   python manage.py makemigrations <app_name>
   python manage.py migrate
   ```

2. **View/URL Changes:**
   - Update `views.py`
   - Update `urls.py`
   - Add rate limiting decorators if needed

3. **Template Changes:**
   - Create/edit templates in `templates/<app>/`
   - Extend `src/base.html`
   - Use AdminLTE components

4. **Testing:**
   ```bash
   python manage.py test <app_name>
   ```

### Code Standards

**ALWAYS:**
- Inherit from `TimeStampedModel, UserTrackingMixin` for models
- Use `get_object_or_404()` (never `.get()` directly)
- Add rate limiting to CRUD endpoints (`@ratelimit`)
- Use HTTP method decorators (`@require_GET`, `@require_http_methods`)
- Sanitize user input (`sanitize_text_input()`, `sanitize_html()`)
- Validate file uploads (MIME + size)

**NEVER:**
- Store secrets in code (use `.env`)
- Skip CSRF tokens on forms
- Allow `unsafe-inline` scripts in production CSP
- Commit `.env`, `db.sqlite3`, or `media/` files

---

## 📚 Additional Resources

### Internal Documentation
- **CLAUDE.md** - AI assistant guidance, architecture patterns
- **AGENTS.md** - Agent-specific instructions
- **DEPLOYMENT.md** - Deployment procedures
- **openspec/AGENTS.md** - Change proposal workflow

### Django Resources
- Django Documentation: https://docs.djangoproject.com/
- Django ORM: https://docs.djangoproject.com/en/4.2/topics/db/
- Django Templates: https://docs.djangoproject.com/en/4.2/topics/templates/

### AdminLTE Resources
- AdminLTE 3.2 Documentation: https://adminlte.io/docs/3.2/
- Bootstrap 4.6 Documentation: https://getbootstrap.com/docs/4.6/

---

## 📞 Next Steps for AI-Assisted Development

### For New Features
1. Read `CLAUDE.md` for coding patterns
2. Review `data-models.md` for database schema
3. Review `api-contracts.md` for existing endpoints
4. Check `architecture.md` for system design principles

### For Bug Fixes
1. Check `architecture.md` for system overview
2. Review relevant model in `data-models.md`
3. Check view implementation in `api-contracts.md`
4. Test fix with `python manage.py test`

### For Refactoring
1. Review `architecture.md` for design patterns
2. Check `source-tree-analysis.md` for file organization
3. Review `CLAUDE.md` for project-specific rules
4. Ensure all tests pass after changes

### For API Integration
1. Review `api-contracts.md` for all endpoints
2. Check authentication requirements
3. Review rate limits and CSRF requirements
4. Test with appropriate user permissions

---

## ✅ Documentation Quality

**Scan Type:** Exhaustive
**Files Scanned:** All source files in critical directories
**Scan Date:** 2025-12-29
**Documentation Files:** 6 (including this index)

**Coverage:**
- ✓ Complete technology stack documented
- ✓ All 150+ API endpoints cataloged
- ✓ All 21 database models documented
- ✓ Complete source tree with annotations
- ✓ Comprehensive architecture documentation
- ✓ Security, performance, and deployment covered

---

## 🎯 Summary

NDAS is a **production-ready Django monolith** for neurodevelopmental assessment management with:

**Strengths:**
- Comprehensive security (14-layer middleware, CSP, rate limiting)
- Medical domain expertise (specialized validation, clinical workflows)
- Robust data model (21 models with proper relationships)
- Well-organized codebase (DRY principles, modular apps)
- Complete documentation (this index + 5 detailed docs)

**Scale:** Small to medium clinical practices (100-10,000 patients)
**Deployment:** Single-server recommended (vertical scaling first)
**Maintainability:** High (good separation of concerns, comprehensive docs)

---

**For questions about this documentation or the NDAS system, refer to the specific documentation files linked above.**

**Last Updated:** 2025-12-29
**Documentation Version:** 1.0
