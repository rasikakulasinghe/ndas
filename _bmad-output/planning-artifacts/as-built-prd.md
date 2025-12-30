# Product Requirements Document - NDAS (As-Built)

**Document Type:** As-Built System Documentation
**System Name:** Neurodevelopmental Assessment System (NDAS)
**Version:** Current Production System
**Date:** 2025-12-30
**Author:** System Documentation (Generated from Codebase Analysis)

---

## Executive Summary

NDAS is a comprehensive Django-based web application designed for managing neurodevelopmental assessments in clinical settings. The system serves as a complete patient record management platform with specialized support for video-based assessments, standardized neurological examinations, and comprehensive reporting capabilities.

**System Classification:**
- **Architecture:** Monolithic Django MVT Application
- **Domain:** Healthcare / Medical (Neurodevelopmental Assessment)
- **Deployment:** Single-server deployment with PostgreSQL
- **Scale:** Small to medium clinical practices (100-10,000 patients)

**Core Value Proposition:**
NDAS provides clinicians with a secure, comprehensive platform to manage patient records, conduct and document neurodevelopmental assessments (GMA, HINE, CDIC, DA, GPA), track clinical problems, and generate detailed reports - all while maintaining healthcare-grade security and comprehensive audit logging.

---

## Product Overview

### What is NDAS?

NDAS is a production-ready medical system that handles:

1. **Patient Record Management**
   - Comprehensive patient data with multiple medical identifiers (BHT, NNC, PTC, PC, PIN, Disk No.)
   - Birth details including gestational age, birth weight, APGAR scores
   - Complete contact information and medical history

2. **Video-Based Assessments**
   - General Movement Assessment (GMA) with video analysis
   - Video upload support up to 2GB (MP4, MOV, AVI, MKV, WEBM)
   - Metadata extraction (duration, resolution, codec, FPS, bitrate)
   - Video.js player integration

3. **Standardized Examinations**
   - **HINE** (Hammersmith Infant Neurological Examination) - Neurological scoring (0-78)
   - **CDIC** (Child Development Inventory Checklist) - Developmental milestones
   - **DA** (Developmental Assessment) - General development tracking
   - **GPA** (General Paediatric Assessment) - Physical examination & vitals

4. **Clinical Problem Tracking**
   - Problem list management with timeline
   - Action logging and status tracking
   - HTMX-powered dynamic updates

5. **Report Generation**
   - PDF reports for each assessment type (ReportLab/WeasyPrint)
   - Excel exports with anonymization options (openpyxl)
   - Customizable report templates
   - Multi-sheet Excel reports

### Technology Foundation

**Backend:**
- Django 4.2.16 on Python 3.x
- PostgreSQL (production) / SQLite (development)
- 5 Django apps: patients, users, video, reports, problemlist
- 21 database models with comprehensive relationships

**Frontend:**
- AdminLTE 3.2 admin dashboard template
- Bootstrap 4.6 responsive framework
- HTMX for dynamic interactions
- Video.js for video playback
- Font Awesome 6.4 icons

**Security:**
- 14-layer middleware stack
- Content Security Policy (CSP) with nonce-based scripts
- Rate limiting (10/min CRUD, 5/min deletes)
- CSRF protection on all forms
- Session timeout (1 hour)
- Comprehensive audit logging

---

## User Personas

### Primary Users

#### 1. Clinical Staff (Physicians, Nurses, Therapists)
**Role:** Direct patient care and assessment
**Goals:**
- Quickly access patient records during consultations
- Document assessment findings accurately
- Track patient developmental progress
- Generate clinical reports for parents/caregivers

**Key Tasks:**
- Patient registration and record management
- Conducting and documenting assessments (GMA, HINE, CDIC, DA, GPA)
- Uploading and reviewing assessment videos
- Tracking clinical problems and interventions
- Generating PDF reports

**Pain Points Solved:**
- Centralized patient record access
- Structured assessment documentation
- Video-based assessment review
- Automated report generation

#### 2. Administrative Staff
**Role:** User management, system administration, data oversight
**Goals:**
- Manage user accounts and permissions
- Monitor system usage and activity
- Ensure data integrity
- Generate operational reports

**Key Tasks:**
- User account creation and management
- Activity log review
- Session management
- Subscription/license management
- Excel export generation for analysis

**Pain Points Solved:**
- Centralized user management
- Comprehensive audit trails
- Activity monitoring
- Data export capabilities

#### 3. Researchers/Clinical Researchers
**Role:** Data analysis and clinical studies
**Goals:**
- Extract anonymized data for research
- Analyze patient cohorts
- Track outcome trends
- Generate statistical reports

**Key Tasks:**
- Excel report generation with customizable filters
- Data anonymization for research compliance
- Cohort analysis across multiple patients
- Longitudinal data tracking

**Pain Points Solved:**
- Anonymized data export
- Customizable report builder
- Multi-patient analysis capabilities
- Structured data access

---

## Features & Capabilities

### 1. Patient Management

**Core Capabilities:**
- Complete patient record CRUD operations
- Multiple medical identifier support (BHT, NNC, PTC, PC, PIN, Disk No.)
- Birth details tracking (POG weeks/days, birth weight, APGAR scores)
- Advanced search and filtering
- Patient status management (New, Diagnosed, Discharged, etc.)
- Bookmark system for quick access

**Key Features:**
- Indexed search across all identifiers
- Filter by diagnosis, status, date ranges
- Patient timeline view
- Attachment management (documents, images, up to 100MB)
- Print-friendly patient lists

**Data Validation:**
- Birth weight: 300-8000g (POG-specific validation)
- APGAR scores: 0-10 range
- Gestational age: 20-44 weeks + 0-6 days
- Phone number format validation
- Medical identifier uniqueness

### 2. Assessment Management

#### General Movement Assessment (GMA)
- Video-linked assessment documentation
- Movement pattern analysis
- Fidgety movement classification
- Quality of GMS rating
- Diagnosis tracking (Normal/Abnormal/Suboptimal)
- Parent notification tracking
- Rich text clinical impressions

#### HINE Assessment
- Neurological examination scoring
- Four component scores: Posture, Tone, Reflexes, Movements
- Total score calculation (0-78)
- Asymmetry notation
- Risk classification (Low/Moderate/High)
- Age-appropriate scoring tables

#### CDIC Assessment
- Five domain scoring: Gross Motor, Fine Motor, Language, Social, Cognitive
- Total score calculation
- Developmental age equivalent
- Clinical interpretation notes
- Recommendations tracking

#### Developmental Assessment (DA)
- Multi-domain development tracking
- Chronological and corrected age tracking
- Concerns and strengths documentation
- Follow-up scheduling
- Comprehensive development notes

#### General Paediatric Assessment (GPA)
- Physical measurements (weight, height, head circumference)
- Vital signs (temperature, heart rate, respiratory rate, blood pressure)
- System-by-system review
- Diagnosis and management plan
- Medication tracking

### 3. Video Management

**Upload Capabilities:**
- File size: Up to 2GB
- Formats: MP4, MOV, AVI, MKV, WEBM
- MIME type validation (python-magic)
- Metadata extraction (duration, resolution, codec, FPS, bitrate)

**Player Features:**
- Video.js HTML5 player
- Streaming playback
- Metadata display
- View counter
- Patient-linked organization

**Security:**
- Authenticated access only
- File validation on upload
- Secure storage in media directory
- Audit logging of access

### 4. Reporting System

#### PDF Reports
- Assessment-specific templates
- Professional formatting with ReportLab/WeasyPrint
- Patient details and assessment data
- Clinical notes and recommendations
- Downloadable via browser

**Report Types:**
- GM Assessment PDF
- HINE Assessment PDF
- CDIC Assessment PDF
- DA Assessment PDF
- GPA Assessment PDF

#### Excel Reports
- Customizable report builder
- Multi-sheet exports (patients, assessments, videos)
- Data anonymization options
- Filter configuration
- Column selection
- Sort ordering
- Usage tracking

**Anonymization Features:**
- Remove patient identifiers (BHT, NNC, names)
- Generate anonymous IDs
- Preserve data relationships
- Research compliance support

### 5. Problem List System

**Problem Tracking:**
- Clinical problem documentation
- Problem type classification (Medical/Social/Developmental/Other)
- Severity levels (Low/Medium/High/Critical)
- Status tracking (Active/Resolved/Under Investigation/Monitoring)
- Priority ranking (1-5)

**Timeline Features:**
- Problem action logging
- Action type categorization
- Outcome tracking
- Staff attribution
- HTMX dynamic status updates

**Analysis:**
- Problem analysis dashboard
- Export capabilities
- Related assessment linking

### 6. User Management & Security

**Authentication:**
- Session-based authentication
- Login/logout functionality
- Password reset (rate-limited)
- Email verification (optional)
- Failed login tracking and account lockout

**User Profiles:**
- Employee ID and department
- Designation and contact information
- Profile pictures (up to 5MB)
- Professional bio
- Notification preferences

**Session Management:**
- Active session tracking
- Device/browser identification
- Remote session termination
- Multi-session support
- 1-hour session timeout

**Activity Logging:**
- All CRUD operations logged
- IP address and user agent tracking
- Change tracking (before/after values)
- Login/logout events
- Failed authentication attempts

**Admin Capabilities:**
- User account management
- Activity log review
- Session termination
- Subscription management
- System-wide oversight

### 7. Help System

- Context-sensitive help articles
- Category organization
- Search functionality
- View tracking
- Rich text content

---

## User Stories & Use Cases

### Clinical Workflows

#### Story 1: New Patient Registration
**As a** clinical staff member
**I want to** register a new patient with complete birth details
**So that** I can begin assessment and treatment

**Acceptance Criteria:**
- Can enter all patient identifiers (BHT, NNC, PTC, PC, PIN, Disk No.)
- Birth details validated (POG, birth weight, APGAR)
- Contact information captured
- System assigns created_at timestamp
- User automatically recorded as added_by

#### Story 2: Video-Based Assessment
**As a** clinician
**I want to** upload an assessment video and link it to a patient
**So that** I can review movement patterns and document findings

**Acceptance Criteria:**
- Upload video up to 2GB
- MIME validation ensures video format
- Metadata automatically extracted
- Video linked to patient record
- GMA assessment can reference video
- Video playback available in browser

#### Story 3: HINE Assessment Documentation
**As a** neurologist
**I want to** conduct and document a HINE assessment
**So that** I can track neurological development over time

**Acceptance Criteria:**
- Enter scores for all four components
- Total score automatically calculated (0-78)
- Risk classification assigned
- Can note asymmetry if present
- Saved with timestamp and user attribution
- Can generate PDF report

#### Story 4: Clinical Problem Tracking
**As a** care coordinator
**I want to** track clinical problems with actions and outcomes
**So that** I can manage ongoing patient issues effectively

**Acceptance Criteria:**
- Create problem with type, severity, priority
- Log actions with dates and outcomes
- Update status dynamically (HTMX)
- Link related assessments
- View problem timeline
- Export problem analysis

#### Story 5: Research Data Export
**As a** clinical researcher
**I want to** export anonymized patient data to Excel
**So that** I can analyze cohorts for research studies

**Acceptance Criteria:**
- Configure report with filters and columns
- Select anonymization option
- Generate multi-sheet Excel file
- Identifiers removed when anonymized
- Data relationships preserved
- Download link provided

### Administrative Workflows

#### Story 6: User Account Management
**As an** administrator
**I want to** manage user accounts and permissions
**So that** only authorized staff can access the system

**Acceptance Criteria:**
- Create new user accounts
- Assign roles (staff, superuser)
- Set employee ID and department
- Enable/disable accounts
- Reset passwords
- View user activity logs

#### Story 7: Session Monitoring
**As an** administrator
**I want to** view active sessions and terminate suspicious ones
**So that** I can maintain system security

**Acceptance Criteria:**
- View all active sessions
- See device and browser information
- Identify last activity timestamp
- Terminate specific sessions remotely
- Terminate all sessions for a user
- Activity logged for audit

#### Story 8: Activity Audit
**As an** administrator
**I want to** review system activity logs
**So that** I can ensure compliance and investigate issues

**Acceptance Criteria:**
- View activity by user, action type, date
- See before/after changes for updates
- Filter by model, IP address
- Export activity logs
- Search by object ID or description
- View failed login attempts

---

## Technical Requirements

### System Requirements

**Server Environment:**
- Python 3.x runtime
- PostgreSQL 10+ (production) or SQLite 3 (development)
- 4GB RAM minimum (8GB recommended)
- 100GB+ storage (video files require significant space)
- Linux/Windows server OS

**Network:**
- HTTPS required for production
- Minimum 10Mbps upload for video streaming
- Firewall configuration for port 443/8000

**Client Requirements:**
- Modern web browser (Chrome, Firefox, Edge, Safari)
- JavaScript enabled
- 1024x768 minimum resolution (1920x1080 recommended)
- Broadband internet for video playback

### Database Schema

**Models:** 21 total across 5 apps

**Patients App (11 models):**
- Patient, GMAssessment, CDICRecord, HINEAssessment
- DevelopmentalAssessment, GeneralPaediatricAssessment
- Attachment, Bookmark, IndicationsForGMA, DiagnosisList, Help

**Users App (5 models):**
- CustomUser, UserActivityLog, UserSession, DeveloperContacts, Subscription

**Video App (1 model):**
- Video

**Reports App (2 models):**
- ReportTemplate, ReportConfig

**Problem List App (2 models):**
- Problem, ProblemAction

**Relationships:**
- 35+ foreign key relationships
- 2 many-to-many relationships
- Automatic user tracking on all models (added_by, last_edit_by)
- Automatic timestamps (created_at, updated_at)

### API Endpoints

**Total Endpoints:** 150+

**Patients App:** 100+ endpoints
- Patient CRUD, filtering, search
- 5 assessment types (GMA, CDIC, HINE, DA, GPA)
- Bookmarks and attachments
- Help system

**Users App:** 30+ endpoints
- Authentication (login, logout, password reset)
- User profiles and settings
- Admin user management
- Activity logs and session management
- Email verification

**Video App:** 10+ endpoints
- Video upload, view, edit, delete
- Patient-specific video filtering

**Reports App:** 15+ endpoints
- Report builder and generation
- PDF downloads (5 assessment types)
- Excel exports
- Report history

**Problem List App:** 10+ endpoints
- Problem CRUD
- Timeline and action logging
- HTMX status updates
- Analysis and export

### Security Requirements

**Authentication & Authorization:**
- Session-based authentication required for all endpoints (except login/password reset)
- 1-hour session timeout
- Password validation: 12+ characters, complexity requirements
- Failed login tracking with account lockout
- Email verification support

**Input Validation:**
- Model-level field validators
- Form-level validation
- XSS sanitization on all text input (bleach library)
- File MIME validation (python-magic)
- Path sanitization for file uploads

**Rate Limiting:**
- 10 requests/minute: Create/edit operations
- 5 requests/minute: Delete operations
- 24 protected endpoints
- User-based and IP-based limiting

**Content Security Policy:**
- Nonce-based script execution (production)
- No unsafe-inline for scripts
- Trusted CDNs whitelisted
- Frame embedding blocked
- Object/embed tags blocked

**Audit Logging:**
- All CRUD operations logged
- IP address and user agent captured
- Change tracking (before/after values)
- Login/logout events
- Failed authentication attempts
- 90-day retention recommended

**Data Protection:**
- HTTPS required in production
- Session cookies: HTTPOnly, Secure, SameSite=Lax
- CSRF protection on all forms
- Encrypted database connections
- File upload size limits enforced

### File Storage

**Upload Limits:**
- Videos: 2GB max
- Documents: 100MB max
- Images: 10MB max
- Profile Pictures: 5MB max

**Allowed Extensions:**
- Videos: .mp4, .mov, .avi, .mkv, .webm
- Documents: .doc, .docx, .txt, .rtf, .odt, .pdf
- Images: .jpg, .jpeg, .png, .gif, .bmp, .webp

**Storage Structure:**
```
media/
├── videos/
├── attachments/
├── profile_pictures/
├── reports/
└── developer_logos/
```

### Performance Requirements

**Response Times:**
- Page load: <2 seconds (typical)
- Video upload: Progress indicator for >100MB
- PDF generation: <5 seconds
- Excel export: <10 seconds for 1000 records
- Search results: <1 second

**Query Optimization:**
- select_related() for foreign keys
- prefetch_related() for reverse relationships
- Database indexes on all searchable fields
- Connection pooling (300 second max age)

**Caching:**
- Session data cached (Redis/LocMem)
- Static file compression (WhiteNoise)
- Rate limit data cached

**Scalability:**
- Current: 10-50 concurrent users
- Database: Supports 1,000-10,000 patients
- Video storage: Limited by disk capacity
- Vertical scaling recommended first

---

## Success Metrics

### User Adoption

**Current System Usage:**
- User accounts: Unlimited (subscription-based)
- Patient records: Designed for 1,000-10,000 patients
- Concurrent users: 10-50 supported
- Assessment types: 5 standardized assessments

**Key Metrics:**
- Daily active users
- Patients registered per month
- Assessments completed per week
- Videos uploaded per month
- Reports generated per week

### System Performance

**Uptime:**
- Target: 99.5% uptime (healthcare standard)
- Session timeout: 1 hour
- Automatic logout on browser close

**Data Integrity:**
- All CRUD operations logged
- User attribution on all records
- Timestamp tracking on all models
- Change tracking for audit compliance

**Security:**
- Failed login tracking
- Account lockout after repeated failures
- Session hijacking protection
- Comprehensive audit trails

### Clinical Value

**Documentation Efficiency:**
- Structured assessment templates reduce documentation time
- Automatic calculations (HINE total score, etc.)
- Pre-filled forms with patient data
- Rich text editors for detailed notes

**Information Access:**
- All patient data centralized
- Cross-referenced assessments
- Historical tracking
- Quick search and filtering

**Reporting Capability:**
- Assessment-specific PDFs
- Customizable Excel exports
- Anonymized research data
- Print-friendly formats

---

## Non-Functional Requirements

### Reliability

**Data Integrity:**
- Database transactions for data consistency
- Foreign key constraints enforced
- Cascade deletion rules defined
- Unique constraint validation

**Backup:**
- Database backup recommended: Daily
- Backup retention: 30 days minimum
- Backup location: Separate from production
- Media files: Included in backup strategy

**Error Handling:**
- Custom error pages (404, 500)
- Error logging to files
- Security log separation
- User-friendly error messages

### Usability

**Interface:**
- AdminLTE 3.2 professional dashboard
- Bootstrap 4.6 responsive design
- Font Awesome 6.4 icons
- Consistent navigation across all pages

**Accessibility:**
- Keyboard navigation support
- Screen reader compatibility (basic)
- High-contrast support
- Responsive design for various devices

**Help System:**
- Context-sensitive help articles
- Searchable help documentation
- Developer contact information
- Category organization

### Maintainability

**Code Organization:**
- Django MVT architecture
- 5 modular apps
- DRY principles (custom_codes utilities)
- Comprehensive inline documentation

**Testing:**
- Test structure in each app
- Unit tests for models and forms
- Integration tests for workflows
- Test database isolation

**Deployment:**
- Environment-based configuration (.env)
- Database migrations versioned
- Static file collection automated
- WSGI/ASGI support for various servers

### Compliance

**Healthcare Considerations:**
- PHI (Protected Health Information) handling
- Access control and authentication
- Audit logging for compliance
- Data anonymization for research

**Recommendations for Full Compliance:**
- HIPAA compliance review (if U.S. deployment)
- Encryption at rest (database-level)
- Regular security audits
- Penetration testing
- Data retention policy
- Disaster recovery plan
- Staff HIPAA training

### Internationalization

**Current Support:**
- Language: English (en-us)
- Timezone: Asia/Kolkata
- i18n framework enabled
- Timezone support enabled

**Future Expansion:**
- Multi-language support ready
- Translation framework in place
- Locale-specific formatting

---

## Deployment & Operations

### Deployment Architecture

**Recommended Stack:**
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

**Environment Configuration:**
- .env file for secrets
- DEBUG=False in production
- ALLOWED_HOSTS configured
- HTTPS enforced
- Secure cookies enabled

**Process Management:**
- systemd or supervisor recommended
- Automatic restart on failure
- Log rotation configured
- Resource limits set

### Monitoring & Logging

**Application Logs:**
- django.log - General application events
- security.log - Security-related events
- 15MB rotation with 10 backups
- Centralized log aggregation recommended

**Metrics:**
- User activity tracking
- Session monitoring
- File upload volumes
- Database query performance
- Error rate tracking

### Maintenance

**Database:**
- Regular migrations for schema updates
- Index optimization
- Query performance monitoring
- Connection pool tuning

**Files:**
- Media file cleanup for deleted records (django-cleanup)
- Disk space monitoring
- Backup verification
- Archive old data

**Security:**
- Regular dependency updates
- Security patch application
- SSL certificate renewal
- Password policy enforcement

---

## Constraints & Limitations

### Current Limitations

**Scalability:**
- Single-server architecture
- SQLite limited to ~1,000 patients
- No horizontal scaling built-in
- File storage on local filesystem

**Features:**
- No REST API for external integrations
- No mobile native apps
- No real-time collaboration features
- No built-in telemedicine/video conferencing

**Internationalization:**
- English only (framework ready for expansion)
- Single timezone configuration
- No multi-currency support

**Accessibility:**
- Basic accessibility support
- Not fully WCAG 2.1 compliant
- Limited screen reader optimization

### Technical Debt

**Future Enhancements:**
- REST API layer (Django REST Framework)
- Background task processing (Celery)
- Real-time features (Django Channels)
- Full-text search (PostgreSQL/ElasticSearch)
- Mobile applications (React Native/Flutter)
- Data analytics dashboard
- Advanced reporting with visualizations

**Infrastructure:**
- Microservices architecture (if needed at scale)
- Object storage integration (S3/MinIO)
- Load balancing for multiple servers
- Database replication
- CDN integration

---

## Dependencies

### External Services

**Required:**
- PostgreSQL database server
- Email server (SMTP) for notifications
- Web server (Nginx/Apache recommended)

**Optional:**
- Redis for caching and sessions
- Backup service/storage
- Monitoring service (Sentry, New Relic, DataDog)
- SSL certificate provider

### Third-Party Libraries

**Backend:**
- Django 4.2.16
- python-decouple (environment config)
- Pillow (image processing)
- reportlab/weasyprint (PDF generation)
- openpyxl (Excel generation)
- bleach (HTML sanitization)
- python-magic (file type detection)
- django-csp (Content Security Policy)
- django-ratelimit (rate limiting)
- django-cleanup (file cleanup)

**Frontend:**
- AdminLTE 3.2
- Bootstrap 4.6
- Font Awesome 6.4
- HTMX
- Video.js
- Select2
- CKEditor

---

## Appendix

### Glossary

**Medical Terms:**
- **BHT** - Bed Head Ticket (hospital patient ID)
- **NNC** - National Neonatal Care number
- **PTC** - Perinatal Transport Card
- **POG** - Period of Gestation (gestational age)
- **APGAR** - Appearance, Pulse, Grimace, Activity, Respiration score
- **GMA** - General Movement Assessment
- **HINE** - Hammersmith Infant Neurological Examination
- **CDIC** - Child Development Inventory Checklist
- **DA** - Developmental Assessment
- **GPA** - General Paediatric Assessment

**Technical Terms:**
- **MVT** - Model-View-Template (Django architecture pattern)
- **CRUD** - Create, Read, Update, Delete
- **WSGI** - Web Server Gateway Interface
- **CSP** - Content Security Policy
- **MIME** - Multipurpose Internet Mail Extensions
- **PHI** - Protected Health Information

### File Locations

**Core Files:**
- Project root: `NDAS/`
- Settings: `ndas/settings.py`
- Main URL config: `ndas/urls.py`
- Custom utilities: `ndas/custom_codes/`

**App Directories:**
- Patients: `patients/`
- Users: `users/`
- Video: `video/`
- Reports: `reports/`
- Problem List: `problemlist/`

**Static & Media:**
- Static source: `static/`
- Static collected: `staticfiles/` (production)
- User uploads: `media/`

**Documentation:**
- Generated docs: `docs/`
- Project guidance: `CLAUDE.md`
- Deployment guide: `DEPLOYMENT.md`

### Key Commands

**Development:**
```bash
# Setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Database
python manage.py makemigrations [app]
python manage.py migrate
python manage.py createsuperuser

# Run
python manage.py runserver

# Tests
python manage.py test [app]
```

**Production:**
```bash
# Static files
python manage.py collectstatic --no-input

# Database
python manage.py migrate

# Server
gunicorn ndas.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

---

**Document End**

*This PRD documents the NDAS system as currently built and deployed. It serves as a comprehensive reference for stakeholders, developers, and anyone needing to understand the system's capabilities, architecture, and requirements.*
