# Architecture - NDAS

**Generated:** 2025-12-29
**Project:** Neurodevelopmental Assessment System (NDAS)
**Pattern:** Django MVT Monolith
**Domain:** Medical / Healthcare

---

## Executive Summary

NDAS is a Django-based web application for managing neurodevelopmental assessments in a clinical setting. The system handles patient records, video-based assessments (General Movement Assessment), standardized neurological examinations (HINE, CDIC, DA, GPA), and comprehensive reporting.

**Key Characteristics:**
- **Architecture:** Monolithic Django application (server-side rendered)
- **Scale:** Small to medium clinical practices (designed for 100-1000 patients)
- **Security:** Healthcare-grade security with CSP, rate limiting, audit logging
- **Data Sensitivity:** Protected Health Information (PHI) compliant
- **Deployment:** Single-server deployment with optional PostgreSQL

---

## Architecture Pattern

### Django MVT (Model-View-Template)

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

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | Django 4.2.16 | Web framework, ORM, admin |
| **Language** | Python 3.x | Primary programming language |
| **Database** | PostgreSQL / SQLite | Relational data storage |
| **Frontend** | AdminLTE 3.2 | Admin dashboard UI framework |
| **CSS** | Bootstrap 4.6 | Responsive styling |
| **JavaScript** | HTMX + Video.js | Dynamic interactions, video playback |
| **Static Files** | WhiteNoise | Static file serving (production) |
| **PDF Generation** | ReportLab / WeasyPrint | Report generation |
| **Excel Export** | openpyxl | Data export |
| **Security** | django-csp, bleach | Content Security Policy, sanitization |
| **Cache** | Redis / LocMem | Session storage, rate limiting |

**See:** `docs/technology-stack.md` for complete details

---

## Application Architecture

### Django Apps (Modular Components)

```
┌─────────────────────────────────────────────────────────────┐
│                         NDAS Project                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              ndas/ (Core Configuration)              │   │
│  │  • Settings, URL routing, WSGI/ASGI                  │   │
│  │  • custom_codes/ (shared utilities)                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         patients/ (Primary Application)              │   │
│  │  URL: / (root)                                       │   │
│  │  • Patient Records (CRUD)                            │   │
│  │  • Assessments (GMA, CDIC, HINE, DA, GPA)            │   │
│  │  • Attachments & Bookmarks                           │   │
│  │  • Help System                                       │   │
│  │  • Dashboard & Search                                │   │
│  │  Models: 11 | Views: 100+ | Templates: 50+          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         users/ (Authentication & Admin)              │   │
│  │  URL: /users/                                        │   │
│  │  • Login/Logout, Password Reset                      │   │
│  │  • User Profiles & Settings                          │   │
│  │  • Session Management                                │   │
│  │  • Activity Logging (audit trail)                    │   │
│  │  • Admin User Management                             │   │
│  │  • Subscription Handling                             │   │
│  │  Models: 5 | Middleware: 2                           │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         video/ (Video Management)                    │   │
│  │  URL: /video/                                        │   │
│  │  • Video Uploads (up to 2GB)                         │   │
│  │  • Metadata Extraction                               │   │
│  │  • Video Player (Video.js)                           │   │
│  │  Models: 1 | Supported: MP4, MOV, AVI, MKV, WEBM    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         reports/ (Report Generation)                 │   │
│  │  URL: /reports/                                      │   │
│  │  • PDF Reports (Assessment-specific)                 │   │
│  │  • Excel Exports (with anonymization)                │   │
│  │  • Report Builder & Templates                        │   │
│  │  Models: 2 | Utilities: PDF & Excel generators      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         problemlist/ (Problem Tracking)              │   │
│  │  URL: /problems/                                     │   │
│  │  • Clinical Problem Tracking                         │   │
│  │  • Problem Timeline & Actions                        │   │
│  │  • Analysis & Export                                 │   │
│  │  Models: 2 | HTMX: Dynamic status updates           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Architecture

### Database Schema (21 Models Across 5 Apps)

**Core Entities:**
```
Patient (Central Entity)
  ├── GMAssessment (1:N)
  ├── CDICRecord (1:N)
  ├── HINEAssessment (1:N)
  ├── DevelopmentalAssessment (1:N)
  ├── GeneralPaediatricAssessment (1:N)
  ├── Video (1:N)
  ├── Attachment (1:N)
  ├── Bookmark (M:N via user)
  └── Problem (1:N)

CustomUser (User Management)
  ├── UserActivityLog (1:N) - Audit trail
  ├── UserSession (1:N) - Active sessions
  ├── Subscription (1:N) - License management
  └── All models via added_by/last_edit_by (User Tracking)

Video
  └── GMAssessment (1:N via file_id)

Problem
  └── ProblemAction (1:N) - Action log

ReportTemplate
  └── ReportConfig (1:N) - User configurations
```

**Base Model Pattern (MANDATORY):**
```python
class MyModel(TimeStampedModel, UserTrackingMixin):
    # Inherits:
    # - created_at, updated_at (automatic timestamps)
    # - added_by, last_edit_by (automatic user tracking)
    pass
```

**Auto-Tracking:** All create/edit operations automatically populate user tracking fields via `UserActivityMiddleware`.

**See:** `docs/data-models.md` for complete schema

---

## Security Architecture

### Multi-Layer Security Model

#### 1. Middleware Stack (14 Layers - Order Critical)
```python
1.  SecurityMiddleware              # Django security features
2.  WhiteNoiseMiddleware            # Static file serving
3.  CSPMiddleware                   # Content Security Policy
4.  AdditionalSecurityHeadersMiddleware  # Custom headers
5.  SessionMiddleware               # Session management
6.  CommonMiddleware                # Common request/response processing
7.  CsrfViewMiddleware              # CSRF protection
8.  AuthenticationMiddleware        # User authentication
9.  UserActivityMiddleware          # Custom - Auto user tracking
10. MessageMiddleware               # Flash messages
11. XFrameOptionsMiddleware         # Clickjacking protection
12. UserAgentMiddleware             # User agent parsing
13. SubscriptionCheckMiddleware     # Custom - License validation
14. SecurityHeadersValidationMiddleware  # Production header validation
```

#### 2. Content Security Policy (CSP)
**Production Policy:**
- `script-src`: nonce-based (no `unsafe-inline`, no `unsafe-eval`)
- `style-src`: `'unsafe-inline'` allowed (template styles)
- `frame-src`: `'none'` (no iframe embedding)
- `object-src`: `'none'` (no Flash/Java)
- Trusted CDNs: cdn.jsdelivr.net, cdnjs.cloudflare.com, vjs.zencdn.net

#### 3. Input Validation & Sanitization
**Validation Layers:**
1. **Model Level:** Field validators (`validate_birth_weight`, `validate_apgar_score`, etc.)
2. **Form Level:** Django form validation
3. **View Level:** Permission checks, business rules
4. **Sanitization:** `sanitize_text_input()`, `sanitize_html()` (bleach)

**File Upload Security:**
- MIME type verification (python-magic)
- File size limits enforced
- Whitelist of allowed extensions
- Path sanitization (`sanitize_filename()`)

#### 4. Rate Limiting
**Protected Operations:**
- **CRUD (10/min):** Create, Edit operations
- **Delete (5/min):** Delete operations
- **Auth (varies):** Login, password reset

**24 protected endpoints** across all apps

#### 5. Authentication & Authorization
**Features:**
- Session-based authentication (1-hour timeout)
- Password validation (12+ chars, complexity rules)
- Failed login tracking & account lockout
- Email verification (optional)
- Two-factor authentication (ready for implementation)
- Permission-based access control

#### 6. Session Security
- `SESSION_COOKIE_AGE`: 1 hour
- `SESSION_EXPIRE_AT_BROWSER_CLOSE`: True
- `SESSION_COOKIE_HTTPONLY`: True
- `SESSION_COOKIE_SECURE`: True (production)
- `SESSION_COOKIE_SAMESITE`: 'Lax'
- Session hijacking protection via UserAgent validation

#### 7. Audit Logging
**UserActivityLog Model:**
- All CRUD operations logged
- IP address, user agent, timestamp
- Change tracking (before/after values)
- Login/logout events
- Failed authentication attempts

---

## Component Architecture

### Custom Codes (Shared Service Layer)

Located in `ndas/custom_codes/`, provides cross-cutting concerns:

| Component | Purpose | Used By |
|-----------|---------|---------|
| `Custom_abstract_class.py` | Base models (TimeStampedModel, UserTrackingMixin) | All models (21 models) |
| `choice.py` | TextChoices for dropdowns | All models with choice fields |
| `validators.py` | Field validators, sanitizers | Models, forms |
| `sanitization.py` | HTML/text sanitization (bleach) | Views, forms |
| `custom_methods.py` | Utility functions | Views, models |
| `ndas_enums.py` | Enumerations | Business logic |
| `delete_helpers.py` | Entity deletion with rules | Delete views |
| `security_middleware.py` | Custom security headers, CSP | Middleware stack |
| `error_handlers.py` | View error decorators | All views |

**Design Pattern:** DRY (Don't Repeat Yourself) - All shared logic centralized

---

### Video Processing Pipeline

```
User Upload (2GB max)
    ↓
MIME Validation (python-magic)
    ↓
File Storage (media/videos/)
    ↓
Metadata Extraction
  • Duration (ffprobe)
  • Resolution (e.g., 1920x1080)
  • Codec, FPS, Bitrate
    ↓
Thumbnail Generation (future)
    ↓
Video Model Saved
    ↓
Link to Assessment (GMAssessment.file_id)
    ↓
Video.js Player (streaming playback)
```

**Supported Formats:** MP4, MOV, AVI, MKV, WEBM

**Metadata Utility:** `extract_video_metadata()` in `custom_methods.py`

---

### Report Generation Pipeline

#### PDF Reports (Assessment-Specific)
```
User Request (e.g., Download GM Assessment PDF)
    ↓
View: download_gm_assessment_pdf()
    ↓
Generator: GMAssessmentPDFGenerator (inherits BasePDFGenerator)
    ↓
Data Gathering
  • Assessment data
  • Patient details
  • Video metadata
  • Clinical notes
    ↓
Template Rendering (ReportLab / WeasyPrint)
    ↓
PDF Generation
    ↓
File Response (Content-Type: application/pdf)
```

#### Excel Reports (Custom Builder)
```
User Configures Report (Report Builder UI)
    ↓
User Selects:
  • Data fields
  • Filters (date range, diagnosis, etc.)
  • Anonymization options
    ↓
View: report_builder() [POST]
    ↓
Generator: ExcelReportGenerator
    ↓
Query Execution (filtered data)
    ↓
Anonymization (if requested)
  • Remove identifiers (BHT, NNC, names)
  • Generate anonymous IDs
    ↓
Excel Generation (openpyxl)
  • Multiple sheets (patients, assessments, videos)
  • Formatting & styling
    ↓
File Saved (media/reports/)
    ↓
Download Link Provided
```

**Report Types:**
- Patient List
- Assessment Summary
- Video Library
- Problem List Analysis
- Custom (user-configured)

---

## Deployment Architecture

### Single-Server Deployment (Recommended)

```
┌─────────────────────────────────────────────────────────────┐
│                      Internet                                │
└────────────────────┬─────────────────────────────────────────┘
                     │ HTTPS (443)
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              Nginx (Reverse Proxy)                           │
│  • SSL Termination                                           │
│  • Static file serving (optional, can use WhiteNoise)        │
│  • Request routing                                           │
└────────────────────┬─────────────────────────────────────────┘
                     │ HTTP (8000)
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              Gunicorn (WSGI Server)                          │
│  • Workers: 2-4 (2 * CPU + 1)                                │
│  • Threads: 2-4 per worker                                   │
│  • Timeout: 120s (for video uploads)                         │
└────────────────────┬─────────────────────────────────────────┘
                     │ Python
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              Django Application                              │
│  • NDAS (patients, users, video, reports, problemlist)       │
│  • Static: WhiteNoise (gzip compression)                     │
│  • Media: Filesystem storage                                 │
└────┬───────────────────────────────────┬────────────────────┘
     │                                   │
     ↓                                   ↓
┌──────────────────────┐      ┌────────────────────────┐
│  PostgreSQL          │      │  Redis (Optional)      │
│  • Port: 5432        │      │  • Port: 6379          │
│  • Conn Pool: 300s   │      │  • Sessions & Cache    │
│  • Isolation: RC     │      │  • Rate Limit Data     │
└──────────────────────┘      └────────────────────────┘
```

### Process Management
**Recommended:** systemd

**Service Units:**
- `ndas-gunicorn.service` - Django app
- `postgresql.service` - Database
- `redis.service` - Cache (optional)
- `nginx.service` - Web server

---

## Development vs Production

| Aspect | Development | Production |
|--------|-------------|------------|
| **DEBUG** | True | False |
| **Database** | SQLite | PostgreSQL |
| **Cache** | LocMem | Redis |
| **Static Files** | Django dev server | WhiteNoise |
| **CSP** | Relaxed (`unsafe-inline` allowed) | Strict (nonce-based) |
| **SSL** | Not required | Required (HTTPS) |
| **Session Secure** | False | True |
| **Logging Level** | DEBUG | INFO |
| **Email Backend** | Console | SMTP |
| **Workers** | 1 (dev server) | 2-4 (Gunicorn) |

---

## Performance Optimization

### Database Optimization
**Query Patterns:**
```python
# Use select_related for ForeignKey (1 query instead of N+1)
patients = Patient.objects.select_related('added_by', 'last_edit_by')

# Use prefetch_related for reverse ForeignKey (2 queries instead of N+1)
patient = Patient.objects.prefetch_related('gmassessment_set').get(pk=pk)

# Use only() for specific fields
patients = Patient.objects.only('bht', 'baby_name', 'dob_tob')

# Use defer() to exclude large text fields
patients = Patient.objects.defer('clinical_notes')
```

**Indexes:**
- All unique identifiers indexed (BHT, NNC, PTC, PC, PIN)
- Search fields indexed (baby_name, mother_name)
- Date fields indexed (dob_tob, created_at)
- ForeignKeys automatically indexed by Django

**Connection Pooling:**
- `CONN_MAX_AGE = 300` (5 minutes, production)
- Reduces connection overhead

### Static File Optimization
**WhiteNoise Features:**
- Gzip compression
- Far-future expires headers
- Immutable cache headers
- Compressed manifests

**AdminLTE:** Pre-minified CSS/JS

**CDNs:** Font Awesome, Video.js from CDN

### Caching Strategy
**Current:**
- Session data cached (Redis/LocMem)
- Rate limit data cached

**Future Enhancements:**
- Query result caching (per-view)
- Template fragment caching
- Patient list caching (invalidate on CRUD)

### File Upload Handling
**Strategy:**
- Files <100MB: In-memory handler
- Files >100MB: Temporary file handler
- Streaming uploads for large videos
- No blocking during upload (async future consideration)

---

## Medical Domain Architecture

### Clinical Workflow Support

```
Patient Registration
    ↓
Patient Record Created
  • BHT, NNC, PTC identifiers
  • Birth details (POG, weight, APGAR)
  • Contact information
    ↓
Video Upload (if applicable)
  • Assessment video captured
  • Uploaded to system
  • Metadata extracted
    ↓
Assessment Selection
  ├── GMA (General Movement)
  ├── CDIC (Development Inventory)
  ├── HINE (Neurological Exam)
  ├── DA (Developmental)
  └── GPA (General Pediatric)
    ↓
Assessment Completion
  • Clinical observations
  • Scoring (age-appropriate norms)
  • Diagnosis/interpretation
  • Recommendations
    ↓
Parent Notification
  • Inform flag updated
  • Communication logged
    ↓
Report Generation
  • PDF for clinical record
  • Excel for research/analysis
    ↓
Problem List (if issues identified)
  • Problem tracking
  • Action logging
  • Timeline management
    ↓
Follow-up Scheduling
  • Next assessment planned
  • Monitoring requirements set
```

### Data Validation (Medical Rules)

**Birth Weight:**
- Range: 300-8000g
- POG-specific validation (enhanced)
- Alerts for outliers

**APGAR Scores:**
- Range: 0-10 (both 1-min and 5-min)
- Required for all patients

**Gestational Age:**
- Weeks: 20-44
- Days: 0-6
- Combined validation

**HINE Total Score:**
- Range: 0-78
- Component scores validated

**Assessment Age:**
- Must be valid for assessment type
- GMA: typically 0-20 weeks post-term age
- HINE: age-appropriate scoring tables

### Medical Identifiers

**Unique Identifiers (Optional but Indexed):**
- **BHT** - Bed Head Ticket (hospital)
- **NNC** - National Neonatal Care number
- **PTC** - Perinatal Transport Card
- **PC** - Patient Card
- **PIN** - Patient Identification Number
- **Disk No** - Physical file number

**Search Strategy:** Can search by any identifier or patient/mother name

---

## Testing Architecture

### Test Structure
```
<app>/tests/
  ├── test_models.py        # Model tests (validation, methods)
  ├── test_views.py         # View tests (HTTP responses, auth)
  ├── test_forms.py         # Form tests (validation, cleaning)
  └── test_integration.py   # End-to-end workflows
```

### Test Database
- In-memory SQLite (fast)
- Automatically created/destroyed
- Test isolation (no production data impact)

### Testing Strategy
**Unit Tests:**
- Model validation
- Custom methods
- Utilities (validators, sanitizers)

**Integration Tests:**
- User workflows (login → create patient → add assessment)
- File uploads
- Report generation

**Manual Testing:**
- Browser compatibility (Chrome, Firefox, Edge)
- Mobile responsiveness
- Print layouts

**Future:**
- Selenium/Playwright for UI testing
- Performance testing (load testing)
- Security testing (penetration testing)

---

## Scalability Considerations

### Current Capacity
- **Patients:** 1,000-10,000 (SQLite: 1k, PostgreSQL: 10k+)
- **Concurrent Users:** 10-50
- **Video Storage:** Limited by disk space
- **Database Size:** 1-10 GB typical

### Scaling Strategies

#### Vertical Scaling (Recommended First)
- Increase server RAM (handle more concurrent connections)
- Faster CPU (report generation, video processing)
- SSD storage (database performance, video streaming)

#### Horizontal Scaling (Future)
- **Load Balancer:** Multiple Gunicorn workers behind Nginx
- **Database:** PostgreSQL replication (read replicas)
- **Cache:** Redis cluster
- **Static/Media:** S3-compatible object storage (AWS S3, MinIO)
- **Sessions:** Redis-backed sessions (for multi-server)

#### Performance Bottlenecks
1. **Video Upload:** Large files (2GB) can block workers
   - **Solution:** Chunked uploads, async task queue (Celery)
2. **Report Generation:** CPU-intensive PDF rendering
   - **Solution:** Background task queue (Celery + Redis)
3. **Database Queries:** N+1 queries on list views
   - **Solution:** select_related/prefetch_related (already implemented)

---

## Security Compliance

### Healthcare Considerations

**HIPAA (U.S.) / Similar Regulations:**
- ✓ Access control (authentication required)
- ✓ Audit logs (UserActivityLog)
- ✓ Session timeout (1 hour)
- ✓ Encryption in transit (HTTPS)
- ⚠ Encryption at rest (database-level encryption recommended)
- ✓ User permissions (Django auth system)
- ✓ Data anonymization (report export feature)

**Additional Recommendations:**
- Regular security audits
- Penetration testing
- HIPAA compliance review (if U.S. deployment)
- Data retention policy implementation
- Backup encryption
- Disaster recovery plan

---

## Future Architecture Enhancements

### Planned Improvements
1. **API Layer (REST API)**
   - Django REST Framework
   - Mobile app integration
   - Third-party integrations
   - OpenAPI/Swagger documentation

2. **Background Task Processing**
   - Celery + Redis
   - Async video processing
   - Scheduled report generation
   - Email notifications

3. **Real-Time Features**
   - Django Channels (WebSocket)
   - Live notifications
   - Real-time collaboration

4. **Search Optimization**
   - PostgreSQL full-text search
   - ElasticSearch integration (advanced search)

5. **Data Analytics**
   - Separate analytics database
   - Data warehousing
   - Business intelligence dashboards

6. **Microservices (If Needed)**
   - Separate video processing service
   - Report generation service
   - Notification service

---

## Architectural Principles

### Design Principles Applied
1. **Separation of Concerns:** Models, Views, Templates separated
2. **DRY (Don't Repeat Yourself):** Shared logic in custom_codes
3. **Convention Over Configuration:** Django defaults used where appropriate
4. **Security by Design:** Multiple security layers (defense in depth)
5. **Simplicity:** Monolithic architecture for maintainability
6. **Scalability:** Prepared for future horizontal scaling

### Django Best Practices
- All models inherit from abstract base classes
- Use `get_object_or_404` (never `.get()` directly)
- Use decorators for auth, HTTP methods, rate limiting
- Sanitize all user input (XSS prevention)
- Validate all file uploads (MIME + size)
- Use transactions for data integrity
- Never store secrets in code (use `.env`)

---

## Documentation References

- **Technology Stack:** `docs/technology-stack.md`
- **API Contracts:** `docs/api-contracts.md` (150+ endpoints)
- **Data Models:** `docs/data-models.md` (21 models, complete schema)
- **Source Tree:** `docs/source-tree-analysis.md`
- **Project Guidance:** `CLAUDE.md` (root)
- **Deployment:** `DEPLOYMENT.md` (root)

---

## Summary

NDAS is a well-architected Django monolith designed for neurodevelopmental assessment management in clinical settings. The architecture prioritizes:

**Security:** Multi-layer security model with CSP, rate limiting, audit logging
**Maintainability:** Modular Django apps, DRY principles, comprehensive documentation
**Medical Domain:** Specialized validation, clinical workflows, PHI handling
**Performance:** Query optimization, caching, connection pooling
**Scalability:** Prepared for growth (vertical first, horizontal future)

The monolithic architecture is appropriate for current scale (small to medium clinical practices) while providing clear pathways for future scaling and feature additions.
