# Architecture Document - NDAS (As-Built)

**Document Type:** As-Built Architecture Documentation
**System Name:** Neurodevelopmental Assessment System (NDAS)
**Architecture Pattern:** Django MVT Monolith
**Version:** Current Production System
**Date:** 2025-12-30
**Author:** System Documentation (Generated from Codebase Analysis)

---

## Executive Summary

NDAS is implemented as a Django-based monolithic web application following the Model-View-Template (MVT) architectural pattern. The system is designed for small to medium clinical practices (100-10,000 patients) with a focus on security, maintainability, and medical domain compliance. The architecture emphasizes defense-in-depth security, comprehensive audit logging, and clear separation of concerns through Django's app-based modularity.

**Architecture Characteristics:**
- **Pattern:** Monolithic Django MVT (server-side rendered)
- **Scale:** Single-server deployment with vertical scaling capability
- **Security:** Healthcare-grade with 14-layer middleware stack
- **Data:** Relational (PostgreSQL/SQLite) with 21 models across 5 apps
- **Frontend:** Server-rendered AdminLTE 3.2 with HTMX enhancements

---

## Table of Contents

1. [System Context](#system-context)
2. [Architecture Overview](#architecture-overview)
3. [Component Architecture](#component-architecture)
4. [Data Architecture](#data-architecture)
5. [Security Architecture](#security-architecture)
6. [Deployment Architecture](#deployment-architecture)
7. [Infrastructure Architecture](#infrastructure-architecture)
8. [Design Decisions](#design-decisions)
9. [Quality Attributes](#quality-attributes)
10. [Constraints & Assumptions](#constraints--assumptions)

---

## 1. System Context

### 1.1 System Purpose

NDAS serves as a comprehensive neurodevelopmental assessment management system for clinical settings. It provides clinicians with tools to manage patient records, conduct standardized assessments, store and review assessment videos, track clinical problems, and generate detailed reports.

### 1.2 Stakeholders

**Primary Users:**
- **Clinical Staff** - Physicians, nurses, therapists conducting assessments
- **Administrative Staff** - User management, system oversight, operational reporting
- **Clinical Researchers** - Data analysis, cohort studies, outcome tracking

**Secondary Stakeholders:**
- **IT Administrators** - System deployment, maintenance, security
- **Compliance Officers** - HIPAA/PHI compliance oversight
- **Parents/Caregivers** - Recipients of assessment reports (indirect users)

### 1.3 External Systems & Integrations

**Current State:**
- Standalone system with no external integrations
- Email service (SMTP) for notifications and password resets
- Browser-based access only (no API consumers)

**Future Considerations:**
- Hospital information systems (HIS) integration potential
- Laboratory information systems (LIS) integration potential
- Electronic health records (EHR) integration potential
- Telemedicine platform integration potential

### 1.4 Context Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Internet/Intranet                        │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                          NDAS System                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Django Application                      │ │
│  │  • Patient Management  • Assessments  • Reporting          │ │
│  │  • Video Management    • User Management                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                             ↓                                    │
│  ┌──────────────────┐            ┌──────────────────────────┐   │
│  │   PostgreSQL     │            │   File Storage           │   │
│  │   Database       │            │   (Media Files)          │   │
│  └──────────────────┘            └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                             ↓
                    ┌────────────────────┐
                    │   SMTP Server      │
                    │ (Email Delivery)   │
                    └────────────────────┘

Users:
├─ Clinical Staff (Web Browser)
├─ Administrators (Web Browser)
└─ Researchers (Web Browser)
```

---

## 2. Architecture Overview

### 2.1 Architectural Pattern: Django MVT Monolith

NDAS follows Django's Model-View-Template (MVT) pattern, a variant of the traditional MVC pattern optimized for web applications.

**Pattern Components:**

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser (Client)                       │
│          AdminLTE 3.2 + Bootstrap 4.6 + HTMX                │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/HTTPS
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Django Application                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           URL Dispatcher (ndas/urls.py)              │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         ↓                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Middleware Stack (14 layers)                 │   │
│  │  • Security (CSP, CSRF, XSS, Clickjacking)           │   │
│  │  • Authentication & Session Management               │   │
│  │  • User Activity Tracking (custom)                   │   │
│  │  • Subscription Validation (custom)                  │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         ↓                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              View Layer (Function-Based)             │   │
│  │  • patients/views.py (100+ views)                    │   │
│  │  • users/views.py (authentication, admin)            │   │
│  │  • video/views.py (uploads, streaming)               │   │
│  │  • reports/views.py (PDF/Excel generation)           │   │
│  │  • problemlist/views.py (problem tracking)           │   │
│  └──────────┬────────────────────────────────┬──────────┘   │
│             ↓                                ↓               │
│  ┌────────────────────┐          ┌────────────────────────┐ │
│  │   Model Layer      │          │   Template Layer       │ │
│  │  (Django ORM)      │          │ (Django Templates)     │ │
│  │                    │          │                        │ │
│  │  • 21 Models       │          │  • AdminLTE Layouts    │ │
│  │  • 5 Django Apps   │          │  • Bootstrap Forms     │ │
│  │  • Relationships   │          │  • Partials/Components │ │
│  └─────────┬──────────┘          └────────────────────────┘ │
│            ↓                                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            Service Layer (custom_codes/)             │   │
│  │  • Validators & Sanitizers                           │   │
│  │  • Business Logic Utilities                          │   │
│  │  • File Handling                                     │   │
│  │  • PDF/Excel Generators                              │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                  Data & Storage Layer                        │
│  ┌────────────────────┐        ┌────────────────────────┐   │
│  │   PostgreSQL/      │        │   Filesystem Storage   │   │
│  │   SQLite Database  │        │   (Videos, Docs)       │   │
│  └────────────────────┘        └────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Key Architectural Decisions:**
- **Monolithic:** Single deployable unit for simplicity and ease of maintenance
- **Server-rendered:** HTML generated server-side for security and SEO
- **Relational database:** Structured medical data with strong consistency requirements
- **File-based media:** Videos and documents stored on filesystem with database metadata

### 2.2 High-Level System Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                         NDAS Monolith                         │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              ndas/ (Core Configuration)                 │ │
│  │  • Settings, URL routing, WSGI/ASGI                     │ │
│  │  • custom_codes/ (shared utilities)                     │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │         patients/ (Primary Application)                 │ │
│  │  URL: / (root)                                          │ │
│  │  • Patient Records (CRUD)                               │ │
│  │  • Assessments (GMA, CDIC, HINE, DA, GPA)               │ │
│  │  • Attachments & Bookmarks                              │ │
│  │  • Help System                                          │ │
│  │  • Dashboard & Search                                   │ │
│  │  Models: 11 | Views: 100+ | Templates: 50+             │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │         users/ (Authentication & Admin)                 │ │
│  │  URL: /users/                                           │ │
│  │  • Login/Logout, Password Reset                         │ │
│  │  • User Profiles & Settings                             │ │
│  │  • Session Management                                   │ │
│  │  • Activity Logging (audit trail)                       │ │
│  │  • Admin User Management                                │ │
│  │  • Subscription Handling                                │ │
│  │  Models: 5 | Middleware: 2                              │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │         video/ (Video Management)                       │ │
│  │  URL: /video/                                           │ │
│  │  • Video Uploads (up to 2GB)                            │ │
│  │  • Metadata Extraction                                  │ │
│  │  • Video Player (Video.js)                              │ │
│  │  Models: 1 | Supported: MP4, MOV, AVI, MKV, WEBM       │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │         reports/ (Report Generation)                    │ │
│  │  URL: /reports/                                         │ │
│  │  • PDF Reports (Assessment-specific)                    │ │
│  │  • Excel Exports (with anonymization)                   │ │
│  │  • Report Builder & Templates                           │ │
│  │  Models: 2 | Utilities: PDF & Excel generators         │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │         problemlist/ (Problem Tracking)                 │ │
│  │  URL: /problems/                                        │ │
│  │  • Clinical Problem Tracking                            │ │
│  │  • Problem Timeline & Actions                           │ │
│  │  • Analysis & Export                                    │ │
│  │  Models: 2 | HTMX: Dynamic status updates              │ │
│  └─────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

---

## 3. Component Architecture

### 3.1 Application Modules (Django Apps)

NDAS is organized into 5 primary Django apps, each with clear responsibilities and boundaries.

#### 3.1.1 Core Configuration (ndas/)

**Purpose:** Project-wide configuration and shared utilities

**Responsibilities:**
- Django settings (database, middleware, security)
- Root URL routing
- WSGI/ASGI server configuration
- Global views (error handlers, debug utilities)
- Custom template tags

**Key Components:**
- `settings.py` - Configuration hub
- `urls.py` - Root URL dispatcher
- `custom_codes/` - Shared service layer
  - `Custom_abstract_class.py` - Base models (TimeStampedModel, UserTrackingMixin)
  - `choice.py` - TextChoices for all dropdowns
  - `validators.py` - Field validators and sanitizers
  - `sanitization.py` - HTML/text sanitization (bleach)
  - `custom_methods.py` - Utility functions
  - `ndas_enums.py` - Enumerations (PtStatus, etc.)
  - `delete_helpers.py` - Entity deletion with business rules
  - `security_middleware.py` - Custom security headers, CSP
  - `error_handlers.py` - View error decorators

**Design Pattern:** DRY (Don't Repeat Yourself) - All shared logic centralized

#### 3.1.2 Patients App (patients/)

**Purpose:** Primary patient record and assessment management

**Responsibilities:**
- Patient CRUD operations
- Five assessment types (GMA, CDIC, HINE, DA, GPA)
- Attachment management
- Bookmark system
- Help articles
- Dashboard and search

**Models (11):**
- `Patient` - Core patient records
- `GMAssessment` - General Movement Assessment
- `CDICRecord` - Child Development Inventory
- `HINEAssessment` - Hammersmith Neurological Exam
- `DevelopmentalAssessment` - General development
- `GeneralPaediatricAssessment` - Physical exams
- `Attachment` - Patient documents/files
- `Bookmark` - User bookmarks
- `IndicationsForGMA` - GMA indication lookup
- `DiagnosisList` - Diagnosis lookup
- `Help` - Help article system

**Views:** 100+ function-based views with decorators for:
- Authentication (@login_required)
- HTTP methods (@require_GET, @require_http_methods)
- Rate limiting (@ratelimit)

**URL Pattern:** Root URL `/` - Primary application interface

#### 3.1.3 Users App (users/)

**Purpose:** Authentication, user management, and audit logging

**Responsibilities:**
- User authentication (login, logout, password reset)
- User profile management
- Email verification
- Session tracking and management
- Activity audit logging
- Admin user management
- Subscription/license handling

**Models (5):**
- `CustomUser` - Extended Django user model
- `UserActivityLog` - Audit trail for all actions
- `UserSession` - Active session tracking
- `DeveloperContacts` - Developer information
- `Subscription` - License/subscription management

**Middleware (2 custom):**
- `UserActivityMiddleware` - Auto-tracks created_by, modified_by on all models
- `SubscriptionCheckMiddleware` - Enforces subscription limits

**URL Pattern:** `/users/*`

#### 3.1.4 Video App (video/)

**Purpose:** Video file management for assessments

**Responsibilities:**
- Video file upload (up to 2GB)
- Metadata extraction (duration, resolution, codec, FPS, bitrate)
- Video player integration (Video.js)
- Video library management

**Models (1):**
- `Video` - Video files with metadata

**Supported Formats:** MP4, MOV, AVI, MKV, WEBM

**Security:**
- MIME validation via python-magic
- File size limits enforced
- Authenticated access only

**URL Pattern:** `/video/*`

#### 3.1.5 Reports App (reports/)

**Purpose:** PDF and Excel report generation

**Responsibilities:**
- PDF generation for assessments
- Excel export with customization
- Report templates and configurations
- Anonymization for research data

**Models (2):**
- `ReportTemplate` - Reusable report templates
- `ReportConfig` - User-specific configurations

**Utilities:**
- `utils/pdf_generator.py` - BasePDFGenerator and assessment-specific generators
- `utils/excel_generator.py` - ExcelReportGenerator with anonymization

**Technologies:**
- PDF: ReportLab / WeasyPrint
- Excel: openpyxl

**URL Pattern:** `/reports/*`

#### 3.1.6 Problem List App (problemlist/)

**Purpose:** Clinical problem tracking and management

**Responsibilities:**
- Problem documentation
- Timeline tracking
- Action logging
- Status management (HTMX-powered)
- Analysis and export

**Models (2):**
- `Problem` - Clinical problems
- `ProblemAction` - Action log

**HTMX Integration:** Dynamic status updates without page reload

**URL Pattern:** `/problems/*`

### 3.2 Service Layer Architecture

The `custom_codes/` directory provides cross-cutting concerns and shared business logic.

**Component Diagram:**

```
┌─────────────────────────────────────────────────────────────┐
│                    custom_codes/                             │
│                  (Service Layer)                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Base Classes                                                │
│  ├─ Custom_abstract_class.py                                │
│  │   ├─ TimeStampedModel (created_at, updated_at)           │
│  │   └─ UserTrackingMixin (added_by, last_edit_by)          │
│  │                                                           │
│  Domain Logic                                                │
│  ├─ choice.py - All TextChoices (diagnosis, status, etc.)   │
│  ├─ ndas_enums.py - Enumerations (PtStatus, etc.)           │
│  │                                                           │
│  Validation & Sanitization                                   │
│  ├─ validators.py                                            │
│  │   ├─ Field validators (birth weight, APGAR, POG)         │
│  │   ├─ File validators (MIME, size, extension)             │
│  │   └─ Input sanitizers (sanitize_text_input)              │
│  ├─ sanitization.py                                          │
│  │   ├─ HTML sanitization (sanitize_html - bleach)          │
│  │   └─ Plain text sanitization                             │
│  │                                                           │
│  Utilities                                                   │
│  ├─ custom_methods.py                                        │
│  │   ├─ getCountZeroIfNone()                                │
│  │   ├─ calculate_age_string()                              │
│  │   └─ extract_video_metadata()                            │
│  ├─ delete_helpers.py                                        │
│  │   ├─ has_delete_permission()                             │
│  │   ├─ validate_can_delete()                               │
│  │   └─ get_entity_warning_items()                          │
│  │                                                           │
│  Security & Middleware                                       │
│  ├─ security_middleware.py                                   │
│  │   ├─ CSPMiddleware (custom CSP headers)                  │
│  │   └─ AdditionalSecurityHeadersMiddleware                 │
│  └─ error_handlers.py                                        │
│      ├─ @handle_view_errors()                               │
│      └─ @log_and_suppress()                                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Usage Pattern:**
All apps import from `custom_codes/` - this ensures DRY principles and consistent behavior across the system.

---

## 4. Data Architecture

### 4.1 Database Schema Overview

**Database:** PostgreSQL (production), SQLite (development)
**ORM:** Django ORM 4.2.16
**Total Models:** 21 across 5 apps

**Mandatory Base Model Pattern:**
```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

class MyModel(TimeStampedModel, UserTrackingMixin):
    # Auto-provides:
    # - created_at, updated_at (TimeStampedModel)
    # - added_by, last_edit_by (UserTrackingMixin - auto-populated by middleware)
    pass
```

### 4.2 Entity Relationship Diagram

```
┌─────────────┐       ┌──────────────┐       ┌───────────────┐
│ CustomUser  │───────│  Patient     │───────│ GMAssessment  │
│             │       │              │       │               │
│ - username  │       │ - bht        │       │ - diagnosis   │
│ - email     │       │ - baby_name  │       │ - file_id     │
│ - is_staff  │       │ - dob_tob    │       │ - remarks     │
└─────────────┘       │ - pog_wks    │       └───────────────┘
       │              │ - birth_wt   │              │
       │              └──────────────┘              │
       │                     │                      │
       │                     │                      │
       ├─────────────────────┼──────────────────────┤
       │                     │                      │
┌─────────────┐       ┌──────────────┐       ┌───────────────┐
│ UserSession │       │  Video       │       │ HINEAssessment│
│             │       │              │       │               │
│ - session   │       │ - file       │       │ - total_score │
│ - ip_addr   │       │ - duration   │       │ - risk_class  │
└─────────────┘       │ - mime_type  │       └───────────────┘
                      └──────────────┘
                             │
┌──────────────┐       ┌──────────────┐       ┌───────────────┐
│ Problem      │       │ Attachment   │       │ Bookmark      │
│              │       │              │       │               │
│ - title      │       │ - file       │       │ - item_id     │
│ - status     │       │ - file_type  │       │ - user        │
│ - severity   │       │ - mime_type  │       └───────────────┘
└──────────────┘       └──────────────┘
       │
       ↓
┌──────────────┐
│ProblemAction │
│              │
│ - action     │
│ - outcome    │
└──────────────┘
```

**Full Relationships:**
- Patient → 1:N → GMAssessment, CDICRecord, HINEAssessment, DevelopmentalAssessment, GeneralPaediatricAssessment
- Patient → 1:N → Video, Attachment, Problem
- CustomUser → 1:N → UserActivityLog, UserSession, Subscription, Bookmark
- CustomUser → FK on all models → added_by, last_edit_by (auto-populated)
- Video → 1:N → GMAssessment (via file_id)
- Problem → 1:N → ProblemAction
- GMAssessment → M:N → IndicationsForGMA, DiagnosisList

**Total Relationships:**
- Foreign Keys: 35+
- Many-to-Many: 2

### 4.3 Data Integrity & Constraints

**Cascade Rules:**
- Patient deletion → CASCADE to all assessments (with protection if videos exist)
- User deletion → PROTECT (prevent if records exist - data integrity)
- Video deletion → RESTRICT if linked to assessments

**Unique Constraints:**
- Patient identifiers (bht, nnc_no, ptc_no, pc_no, pin) - individually unique, can be null
- Username, email (CustomUser)
- Session keys (UserSession)
- Help article slugs

**Indexes (Performance):**
- All unique identifiers (BHT, NNC, PTC, PC, PIN)
- Patient names (baby_name, mother_name)
- Date fields (dob_tob, assessment_date, created_at)
- Status fields (is_active, status)
- Foreign keys (automatic Django index)

### 4.4 Data Validation Rules

**Medical Domain Validations:**
- Birth weight: 300-8000g (POG-specific enhanced validation)
- APGAR scores: 0-10 (both 1-min and 5-min)
- Gestational age: 20-44 weeks + 0-6 days
- Head circumference: Positive float
- HINE total score: 0-78

**File Upload Validations:**
- MIME type verification (python-magic)
- File size limits enforced (2GB videos, 100MB docs, 10MB images)
- Whitelist of allowed extensions
- Path sanitization (`sanitize_filename()`)

**String Validations:**
- Phone numbers: Regex validation for international formats
- Email: Django EmailField validation
- Text input: XSS sanitization (`sanitize_text_input()`)
- HTML content: Bleach library sanitization

---

## 5. Security Architecture

### 5.1 Defense-in-Depth Security Model

NDAS implements multiple layers of security controls to protect Protected Health Information (PHI) and ensure healthcare compliance.

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Layer 1: Network Security                                   │
│  ├─ HTTPS/TLS encryption (production required)              │
│  ├─ Firewall configuration                                  │
│  └─ Reverse proxy (Nginx) with SSL termination              │
│                                                              │
│  Layer 2: Application Security (Middleware - 14 layers)      │
│  ├─ SecurityMiddleware (Django built-in)                    │
│  ├─ CSPMiddleware (Content Security Policy)                 │
│  ├─ AdditionalSecurityHeadersMiddleware (custom)            │
│  ├─ CsrfViewMiddleware (CSRF protection)                    │
│  ├─ AuthenticationMiddleware (user auth)                    │
│  ├─ XFrameOptionsMiddleware (clickjacking)                  │
│  └─ SubscriptionCheckMiddleware (custom licensing)          │
│                                                              │
│  Layer 3: Authentication & Authorization                     │
│  ├─ Session-based authentication (1-hour timeout)           │
│  ├─ Password validation (12+ chars, complexity)             │
│  ├─ Failed login tracking & lockout                         │
│  ├─ Permission-based access control                         │
│  └─ Email verification (optional)                           │
│                                                              │
│  Layer 4: Input Validation & Sanitization                   │
│  ├─ Model-level validators                                  │
│  ├─ Form-level validation                                   │
│  ├─ XSS sanitization (bleach library)                       │
│  ├─ MIME validation (python-magic)                          │
│  └─ Path sanitization (file uploads)                        │
│                                                              │
│  Layer 5: Rate Limiting                                      │
│  ├─ 10 requests/min: Create/edit operations                 │
│  ├─ 5 requests/min: Delete operations                       │
│  └─ 24 protected endpoints                                  │
│                                                              │
│  Layer 6: Audit & Monitoring                                 │
│  ├─ UserActivityLog (all CRUD operations)                   │
│  ├─ IP address & user agent tracking                        │
│  ├─ Change tracking (before/after values)                   │
│  └─ Login/logout event logging                              │
│                                                              │
│  Layer 7: Session Security                                   │
│  ├─ HTTPOnly cookies                                         │
│  ├─ Secure cookies (HTTPS only in prod)                     │
│  ├─ SameSite=Lax protection                                 │
│  ├─ 1-hour session timeout                                  │
│  └─ Browser-close session expiry                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Middleware Stack (Order Critical)

The middleware stack executes in strict order. Each layer provides specific security controls.

```python
# settings.py MIDDLEWARE configuration (ORDER CRITICAL)
MIDDLEWARE = [
    1.  'django.middleware.security.SecurityMiddleware',
    2.  'whitenoise.middleware.WhiteNoiseMiddleware',
    3.  'csp.middleware.CSPMiddleware',
    4.  'ndas.custom_codes.security_middleware.AdditionalSecurityHeadersMiddleware',
    5.  'django.contrib.sessions.middleware.SessionMiddleware',
    6.  'django.middleware.common.CommonMiddleware',
    7.  'django.middleware.csrf.CsrfViewMiddleware',
    8.  'django.contrib.auth.middleware.AuthenticationMiddleware',
    9.  'users.middleware.UserActivityMiddleware',
    10. 'django.contrib.messages.middleware.MessageMiddleware',
    11. 'django.middleware.clickjacking.XFrameOptionsMiddleware',
    12. 'django_user_agents.middleware.UserAgentMiddleware',
    13. 'users.middleware.SubscriptionCheckMiddleware',
    14. 'ndas.custom_codes.security_middleware.SecurityHeadersValidationMiddleware',
]
```

**Key Middleware Functions:**

**UserActivityMiddleware (Custom):**
- Automatically populates `added_by` on creation
- Automatically populates `last_edit_by` on update
- Tracks all CRUD operations in UserActivityLog
- Captures IP address, user agent, timestamp

**SubscriptionCheckMiddleware (Custom):**
- Validates active subscription before CRUD operations
- Enforces patient limits based on subscription tier
- Redirects to subscription page if inactive
- Allows read-only access for expired subscriptions

### 5.3 Content Security Policy (CSP)

**Production CSP Configuration:**
```python
# Nonce-based script execution (no unsafe-inline)
CSP_SCRIPT_SRC = ("'self'", "cdn.jsdelivr.net", "cdnjs.cloudflare.com", "'nonce-{nonce}'")

# Styles allow inline (for dynamic template styles)
CSP_STYLE_SRC = ("'self'", "cdn.jsdelivr.net", "cdnjs.cloudflare.com", "'unsafe-inline'")

# Block frame embedding
CSP_FRAME_SRC = ("'none'",)

# Block object/embed tags
CSP_OBJECT_SRC = ("'none'",)

# Trusted CDNs for fonts, scripts, styles
CSP_FONT_SRC = ("'self'", "cdn.jsdelivr.net", "cdnjs.cloudflare.com")
```

**CSP Benefits:**
- Prevents XSS attacks through script injection
- Blocks clickjacking via frame embedding
- Restricts resource loading to trusted domains
- Mitigates data exfiltration attempts

---

## 6. Deployment Architecture

### 6.1 Single-Server Deployment (Current Recommended)

```
┌─────────────────────────────────────────────────────────────┐
│                      Internet                                │
└────────────────────┬─────────────────────────────────────────┘
                     │ HTTPS (443)
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              Nginx (Reverse Proxy)                           │
│  • SSL Termination (Let's Encrypt recommended)               │
│  • Request routing to Gunicorn                               │
│  • Optional: Static file serving (can use WhiteNoise)        │
│  • Security headers enforcement                              │
└────────────────────┬─────────────────────────────────────────┘
                     │ HTTP (127.0.0.1:8000)
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              Gunicorn (WSGI Server)                          │
│  • Workers: 2-4 (formula: 2 * CPU + 1)                       │
│  • Threads: 2-4 per worker                                   │
│  • Timeout: 120s (accommodates video uploads)                │
│  • Worker class: sync (default)                              │
└────────────────────┬─────────────────────────────────────────┘
                     │ Python WSGI
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              Django Application (NDAS)                       │
│  • Static files: WhiteNoise (gzip, far-future headers)       │
│  • Media files: FileSystemStorage                            │
│  • Session backend: Database or Redis                        │
└────┬───────────────────────────────────┬────────────────────┘
     │                                   │
     ↓                                   ↓
┌──────────────────────┐      ┌────────────────────────┐
│  PostgreSQL          │      │  Redis (Optional)      │
│  • Port: 5432        │      │  • Port: 6379          │
│  • Conn Pool: 300s   │      │  • Sessions & Cache    │
│  • Isolation: RC     │      │  • Rate Limit Data     │
│  • Backups: Daily    │      │  • Pub/Sub (future)    │
└──────────────────────┘      └────────────────────────┘
```

---

## 7. Design Decisions

### 7.1 Key Architectural Decisions

#### Decision 1: Monolithic Architecture

**Rationale:**
- Simplicity for small-medium scale
- Strong transactional guarantees for medical data
- Single server deployment reduces operational complexity
- Lower infrastructure costs
- Suitable for team size (<5 developers)

**Trade-offs:**
- Vertical scaling initially
- All components deployed together
- Technology stack lock-in

#### Decision 2: Server-Side Rendering

**Rationale:**
- Enhanced security for medical data
- Reduced attack surface
- Simpler to secure and audit
- HTMX provides dynamic updates without SPA complexity

**Trade-offs:**
- Full page reloads (mitigated by HTMX)
- Limited offline capabilities

#### Decision 3: PostgreSQL Database

**Rationale:**
- ACID compliance critical for medical data
- Relational model fits medical domain
- Excellent Django ORM support
- Battle-tested in healthcare
- Open source (no licensing costs)

**Trade-offs:**
- Schema migrations required
- Vertical scaling limits at very high scale

---

## 8. Quality Attributes

### 8.1 Reliability
- Target: 99.5% uptime
- Database transactions for data integrity
- Daily automated backups
- 30-day retention

### 8.2 Performance
- Page load: <2 seconds
- Search results: <1 second
- PDF generation: <5 seconds
- Excel export: <10 seconds (1000 records)

### 8.3 Security
- Healthcare-grade security
- 14-layer middleware stack
- Comprehensive audit logging
- HTTPS required in production
- Session timeout: 1 hour

### 8.4 Scalability
- Current: 10-50 concurrent users
- Patients: 1,000-10,000 supported
- Vertical scaling first
- Horizontal scaling path defined

---

## 9. Constraints & Assumptions

### 9.1 Technical Constraints
- Python 3.x runtime required
- PostgreSQL 10+ or SQLite 3
- Modern web browser required
- Single-server architecture (current)

### 9.2 Operational Constraints
- Single-server deployment only
- Manual scaling (vertical)
- No zero-downtime deployment built-in
- Requires maintenance windows

### 9.3 Security Constraints
- Not HIPAA-certified out-of-box
- No built-in encryption at rest
- Session-based authentication only
- No multi-factor authentication built-in

---

## Appendix: Deployment Checklist

**Pre-Deployment:**
- [ ] .env file configured
- [ ] DEBUG=False
- [ ] SECRET_KEY generated
- [ ] SSL certificate obtained
- [ ] Database created

**Deployment:**
- [ ] Dependencies installed
- [ ] Migrations run
- [ ] Static files collected
- [ ] Superuser created
- [ ] Permissions set

**Security:**
- [ ] HTTPS enforced
- [ ] Secure cookies enabled
- [ ] CSP headers verified
- [ ] File upload limits enforced

---

**Document End**

*This Architecture Document describes the NDAS system as currently designed and deployed. It serves as the definitive reference for technical stakeholders, architects, developers, and operations teams.*
