# NDAS Project Overview

**Neurodevelopmental Assessment System**
Last Updated: 2026-03-09

---

## Purpose

NDAS is a Django-based medical information system for managing patient records, video-based neurodevelopmental assessments, and clinical evaluation workflows. It is designed for use in neonatal and paediatric care units that perform General Movement Assessments (GMA), HINE neurological examinations, and developmental assessments.

The system supports the full clinical lifecycle: patient registration, video capture and review, structured assessment recording, problem list management, reporting, and discharge planning. A Phase 2 multi-institution expansion adds institution isolation, cross-institution referrals, and notification infrastructure.

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Framework | Django 4.2.16 |
| Language | Python 3.9+ |
| Database (dev) | SQLite 3 |
| Database (prod) | PostgreSQL 12+ |
| Frontend CSS | AdminLTE 3.2 + Bootstrap 4.6 |
| Icons | Font Awesome 6.4 |
| Dynamic UI | HTMX |
| Video Playback | Video.js |
| Rich Text Editor | CKEditor (django-ckeditor) |
| PDF Generation | ReportLab |
| Excel Export | openpyxl |
| Static Files | WhiteNoise |
| Caching | Redis (prod) / LocMemCache (dev) |
| Rate Limiting | django-ratelimit |
| CSP | django-csp |
| Age Calculation | python-dateutil (relativedelta) |
| Video Metadata | moviepy / ffprobe (ffmpeg) |
| File Cleanup | django-cleanup |
| Env Config | python-decouple |

---

## Application Architecture

The project uses a monolithic Django MVT architecture. The `ndas/` directory is the Django project core. Business logic is split across five domain apps plus two Phase 2 apps.

| App | Purpose |
|-----|---------|
| `patients/` | Core domain: patient records, GMA/HINE/DA/CDIC/GPA assessments, attachments, bookmarks, help content. Mounted at root URL (`/`). |
| `users/` | Authentication, custom user model, user activity logging, session management, subscription management. Mounted at `/users/`. |
| `video/` | Video upload, metadata extraction, viewing, and management. Linked to patients. Mounted at `/video/`. |
| `reports/` | PDF and Excel report generation with configurable templates. Assessment-specific PDF downloads. Mounted at `/reports/`. |
| `problemlist/` | Patient problem list: problem CRUD, action audit log, timeline view, analysis. Mounted at `/problems/`. |
| `institution/` | Phase 2: Institution onboarding, selector, context switching, admin dashboard, clinician management, branding. Mounted at `/institution/`. |
| `referral/` | Phase 2: Cross-institution referral initiation, inbox, threaded messaging, lifecycle management, in-app notifications. Mounted at `/referral/`. |

---

## Key Features

### Patient Management
- Patient registration with full neonatal data (BHT, NNC, PTC, PC, PIN identifiers)
- Birth details: gestational age (POG weeks/days), APGAR scores, mode of delivery, birth weight, OFC
- Medical history fields: antenatal, intranatal, postnatal history
- Age calculations: chronological age, corrected age, corrected gestational age
- Recommendation and care (RC) status logic based on GMA and HINE results
- Admission and discharge tracking

### Assessment Workflow
- **GMA (General Movement Assessment)**: Video-linked assessments with diagnosis selection, management plans, follow-up scheduling, parent notification tracking
- **HINE (Hammersmith Infant Neurological Examination)**: Score-based neurological assessment (0–78), severity categorization
- **Developmental Assessment (DA)**: Four developmental domains — Gross Motor (GM), Fine Motor & Vision (FMV), Hearing Speech & Language (HSL), Social/Emotional/Behavioural (SEB) — with age-range recording
- **CDIC Record**: Child Development and Intervention Centre visit records with discharge management
- **GPA (General Paediatric Assessment)**: Comprehensive clinical assessment with investigations, medications, next plan

### Video Management
- Upload with automatic metadata extraction (duration, resolution) via moviepy/ffprobe
- Institution-partitioned file storage paths
- Custom VideoQuerySet with N+1-free annotations for assessment status
- Processing status tracking

### Problem List
- Patient-linked problem records with status lifecycle (active → resolved/chronic/inactive)
- Severity tracking (mild, moderate, severe, life-threatening)
- Action audit log with timestamped entries
- Timeline view and analysis/export

### Reporting
- PDF generation via ReportLab with configurable templates
- Per-assessment PDF downloads (GMA, HINE, DA, CDIC, GPA)
- Excel export with anonymization for research data
- Report history and download management

### Bookmarks
- Generic bookmark system supporting: Patient, Video, GMA, HINE, Attachment, DA, CDICR, GPA
- Priority levels, tags, public/private visibility
- Per-user and global bookmark management

### Attachments
- Multi-type file attachments per patient (image, PDF, video, document)
- File metadata extraction (size, MIME type, original filename)
- Access level control (restricted, team, department, general)
- Virus scan status tracking (pending, clean, infected, error)
- Institution-partitioned storage paths

---

## User Roles and Permissions

### Phase 1 Roles
| Role | Django Flags | Access |
|------|-------------|--------|
| Superuser | `is_superuser=True` | Full system access; can delete any record |
| Staff | `is_staff=True` | Can delete own records; all CRUD on patients/assessments |
| User | Standard | Can create/edit records; cannot delete |

### Phase 2 Roles (`UserType` field on `CustomUser`)
| UserType | Access Scope |
|----------|-------------|
| `SUPERADMIN` | All institutions, aggregate analytics, patient moves, institution onboarding |
| `ADMIN` | Own institution: clinician management, institution branding, institution-scoped analytics |
| `USER` | Own institution data + referral bridge to other institutions |

### Delete Permissions
- Superusers can delete any entity
- Staff users can delete records where `added_by == request.user`
- Videos cannot be deleted if referenced in a GMA assessment
- Users are soft-deleted (deactivated, not removed)

---

## Medical Domain Context

NDAS operates in Sri Lankan neonatal/paediatric care. Key medical identifiers:

| Identifier | Meaning |
|-----------|---------|
| BHT | Bed Head Ticket (hospital admission ID) |
| NNC | National Neonatal Care number |
| PTC | Perinatal Transport Card number |
| PC | Patient Card number |
| PIN | Patient Identification Number |
| Disk No. | Physical file/disk number |
| MOH Area | Medical Officer of Health area |
| PHM Area | Public Health Midwife area |

Assessment thresholds:
- **HINE**: Score > 73 = normal; ≤ 73 = abnormal (triggers referral recommendation)
- **APGAR**: 0–10 at 1, 5, 10 minutes
- **Birth weight**: 300g–8000g (validated)
- **POG**: 20–44 weeks + 0–6 days

---

## Repository Structure

```
NDAS/
├── ndas/                    # Django project core
│   ├── settings.py          # Centralised settings with env vars
│   ├── urls.py              # Root URL config
│   ├── views.py             # Error handlers (404, 500, rate-limited)
│   └── custom_codes/        # Shared utilities (see Architecture doc)
├── patients/                # Core domain app
├── users/                   # Auth and user management
├── video/                   # Video management
├── reports/                 # PDF/Excel reporting
├── problemlist/             # Problem list management
├── institution/             # Phase 2 multi-institution
├── referral/                # Phase 2 cross-institution referrals
├── templates/               # Global templates
│   ├── src/                 # Base layout templates
│   ├── patients/            # Patient CRUD templates
│   ├── users/               # Auth and user templates
│   ├── video/               # Video templates
│   ├── assessment/          # GMA templates
│   ├── hine/                # HINE templates
│   ├── develop_assemnt/     # DA templates
│   ├── cdic_record/         # CDIC templates
│   ├── gpa_record/          # GPA templates
│   ├── attachment/          # Attachment templates
│   ├── bookmark/            # Bookmark templates
│   ├── problemlist/         # Problem list templates
│   ├── institution/         # Institution templates
│   └── referral/            # Referral templates
├── static/                  # Static assets (CSS, JS, images)
├── media/                   # Uploaded media files
├── logs/                    # Application and security logs
├── docs/                    # Project documentation
├── _bmad-output/            # Planning artifacts (PRD, architecture, etc.)
├── manage.py
├── CLAUDE.md                # Developer guidance for Claude Code
├── DEPLOYMENT.md            # Deployment guide
└── db.sqlite3               # SQLite database (development)
```
