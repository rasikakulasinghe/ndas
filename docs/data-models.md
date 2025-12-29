# Data Models - NDAS

**Generated:** 2025-12-29
**Project:** Neurodevelopmental Assessment System (NDAS)
**Database:** PostgreSQL (production) / SQLite (development)
**ORM:** Django ORM 4.2.16

---

## Overview

NDAS uses Django ORM with a structured model hierarchy. All models inherit from custom abstract base classes that provide automatic timestamping and user tracking.

**Total Models:** 21 across 5 Django apps

**Base Classes:**
- `TimeStampedModel` - Provides `created_at`, `updated_at` fields
- `UserTrackingMixin` - Provides `added_by`, `last_edit_by` fields (auto-populated by `UserActivityMiddleware`)

---

## Model Inheritance Pattern (MANDATORY)

```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

class MyModel(TimeStampedModel, UserTrackingMixin):
    # Your fields here
    pass
```

**Auto-provided Fields:**
- `created_at` - DateTime when record was created
- `updated_at` - DateTime when record was last modified
- `added_by` - ForeignKey to User who created the record
- `last_edit_by` - ForeignKey to User who last modified the record

---

## Patients App (patients/)

### Patient
**Purpose:** Core patient records with medical identifiers and birth details

**Key Fields:**
- `bht` (CharField, unique, indexed) - BHT Number (Bed Head Ticket)
- `nnc_no` (CharField, unique, indexed) - NNC Number (National Neonatal Care)
- `ptc_no` (CharField, unique, indexed) - PTC Number (Perinatal Transport Card)
- `pc_no` (CharField, unique, indexed) - PC Number (Patient Card)
- `pin` (CharField, unique, indexed) - PIN (Patient Identification Number)
- `disk_no` (CharField) - Physical disk/file number
- `baby_name` (CharField, indexed) - Infant's full name
- `mother_name` (CharField, indexed) - Mother's full name
- `pog_wks` (PositiveSmallIntegerField, choices) - Gestational age in weeks (20-44)
- `pog_days` (PositiveSmallIntegerField, choices) - Additional days (0-6)
- `gender` (CharField, choices, indexed) - Biological sex
- `dob_tob` (DateTimeField, indexed) - Date and time of birth
- `mo_delivery` (CharField, choices) - Mode of delivery (NVD, LSCS, etc.)
- `birth_weight` (PositiveIntegerField) - Birth weight in grams (300-8000g, validated)
- `hc` (FloatField) - Head circumference at birth
- `apgar_1` (PositiveSmallIntegerField, 0-10) - APGAR score at 1 minute
- `apgar_5` (PositiveSmallIntegerField, 0-10) - APGAR score at 5 minutes
- `phone_number` (CharField, validated) - Contact phone number
- `address` (TextField) - Residential address

**Validators:**
- `validate_birth_weight` - Validates 300-8000g range with POG-specific rules
- `validate_apgar_score` - Ensures 0-10 range
- `validate_pog_weeks` - Ensures 20-44 weeks
- `validate_pog_days` - Ensures 0-6 days
- `validate_phone_number` - Validates phone format

**Relationships:**
- One-to-Many with GMAssessment
- One-to-Many with CDICRecord
- One-to-Many with HINEAssessment
- One-to-Many with DevelopmentalAssessment
- One-to-Many with GeneralPaediatricAssessment
- One-to-Many with Video
- One-to-Many with Attachment
- One-to-Many with Problem

**Indexes:** bht, nnc_no, ptc_no, pc_no, pin, baby_name, mother_name, gender, dob_tob

---

### GMAssessment (General Movement Assessment)
**Purpose:** Video-based neurodevelopmental assessment records

**Key Fields:**
- `patient` (ForeignKey to Patient) - Associated patient
- `file_id` (ForeignKey to Video) - Associated video file
- `assessment_age_weeks` (PositiveSmallIntegerField) - Age at assessment
- `assessment_age_days` (PositiveSmallIntegerField) - Additional days
- `assessment_date` (DateField) - Date of assessment
- `diagnosis` (CharField, choices) - Assessment outcome (Normal/Abnormal/Suboptimal)
- `informed` (BooleanField) - Whether parent/guardian was informed
- `remarks` (TextField) - Clinical notes
- `quality_of_gms` (CharField) - Quality rating
- `movement_patterns` (TextField) - Detailed movement observations
- `fidgety_movements` (CharField, choices) - Fidgety movement classification
- `clinical_impressions` (RichTextField) - Rich text clinical impressions

**Relationships:**
- Many-to-One with Patient
- Many-to-One with Video
- Many-to-Many with IndicationsForGMA
- Many-to-Many with DiagnosisList

**Business Rules:**
- Cannot delete if video is linked to other assessments
- Assessment age must be valid for GMA (typically 0-20 weeks)

---

### CDICRecord (Child Development Inventory Checklist)
**Purpose:** Developmental milestone tracking

**Key Fields:**
- `patient` (ForeignKey to Patient) - Associated patient
- `assessment_date` (DateField) - Date of assessment
- `assessment_age_months` (PositiveSmallIntegerField) - Age in months
- `gross_motor_score` (PositiveSmallIntegerField) - Gross motor development score
- `fine_motor_score` (PositiveSmallIntegerField) - Fine motor development score
- `language_score` (PositiveSmallIntegerField) - Language development score
- `social_score` (PositiveSmallIntegerField) - Social development score
- `cognitive_score` (PositiveSmallIntegerField) - Cognitive development score
- `total_score` (PositiveSmallIntegerField) - Calculated total score
- `developmental_age` (PositiveSmallIntegerField) - Developmental age equivalent
- `interpretation` (TextField) - Clinical interpretation
- `recommendations` (TextField) - Follow-up recommendations

**Relationships:**
- Many-to-One with Patient

---

### HINEAssessment (Hammersmith Infant Neurological Examination)
**Purpose:** Neurological examination scoring

**Key Fields:**
- `patient` (ForeignKey to Patient) - Associated patient
- `assessment_date` (DateField) - Date of assessment
- `corrected_age_months` (PositiveSmallIntegerField) - Corrected age
- `posture_score` (PositiveSmallIntegerField) - Posture section score
- `tone_score` (PositiveSmallIntegerField) - Tone section score
- `reflexes_score` (PositiveSmallIntegerField) - Reflexes section score
- `movements_score` (PositiveSmallIntegerField) - Movements section score
- `total_score` (PositiveSmallIntegerField) - Total HINE score (0-78)
- `asymmetry_noted` (BooleanField) - Asymmetry present
- `clinical_interpretation` (TextField) - Clinical notes
- `risk_classification` (CharField, choices) - Risk level (Low/Moderate/High)

**Relationships:**
- Many-to-One with Patient

---

### DevelopmentalAssessment
**Purpose:** General developmental assessment tracking

**Key Fields:**
- `patient` (ForeignKey to Patient) - Associated patient
- `assessment_date` (DateField) - Date of assessment
- `chronological_age_months` (PositiveSmallIntegerField) - Chronological age
- `corrected_age_months` (PositiveSmallIntegerField) - Corrected age (for preterm)
- `physical_development` (TextField) - Physical development notes
- `cognitive_development` (TextField) - Cognitive development notes
- `social_emotional_development` (TextField) - Social-emotional notes
- `language_development` (TextField) - Language development notes
- `motor_development` (TextField) - Motor development notes
- `concerns` (TextField) - Identified concerns
- `strengths` (TextField) - Identified strengths
- `recommendations` (TextField) - Clinical recommendations
- `follow_up_required` (BooleanField) - Follow-up needed
- `follow_up_date` (DateField) - Scheduled follow-up

**Relationships:**
- Many-to-One with Patient

---

### GeneralPaediatricAssessment (GPA)
**Purpose:** General pediatric examination records

**Key Fields:**
- `patient` (ForeignKey to Patient) - Associated patient
- `assessment_date` (DateField) - Date of assessment
- `weight` (FloatField) - Current weight (kg)
- `height` (FloatField) - Current height (cm)
- `head_circumference` (FloatField) - Current HC (cm)
- `temperature` (FloatField) - Body temperature (°C)
- `heart_rate` (PositiveSmallIntegerField) - Heart rate (bpm)
- `respiratory_rate` (PositiveSmallIntegerField) - Respiratory rate
- `blood_pressure_systolic` (PositiveSmallIntegerField) - Systolic BP
- `blood_pressure_diastolic` (PositiveSmallIntegerField) - Diastolic BP
- `physical_examination` (RichTextField) - Detailed examination notes
- `system_review` (RichTextField) - System-by-system review
- `diagnosis` (TextField) - Clinical diagnosis
- `management_plan` (RichTextField) - Treatment and follow-up plan
- `medications_prescribed` (TextField) - Prescribed medications

**Relationships:**
- Many-to-One with Patient

---

### Attachment
**Purpose:** Document and file attachments linked to patients

**Key Fields:**
- `patient` (ForeignKey to Patient) - Associated patient
- `title` (CharField, indexed) - Attachment title
- `description` (TextField) - Description of attachment
- `file` (FileField) - Uploaded file
- `file_type` (CharField, choices) - Type (Document/Image/PDF/Other)
- `file_size` (PositiveBigIntegerField) - Size in bytes
- `file_extension` (CharField) - File extension
- `access_level` (CharField, choices) - Access level (Public/Private/Restricted)
- `mime_type` (CharField) - MIME type (validated)
- `is_archived` (BooleanField) - Archived status

**File Limits:**
- Documents: 100MB max (.doc, .docx, .txt, .rtf, .odt, .pdf)
- Images: 10MB max (.jpg, .jpeg, .png, .gif, .bmp, .webp)

**Validators:**
- `validate_attachment_file` - MIME type and size validation

**Relationships:**
- Many-to-One with Patient

**Upload Path:** `media/attachments/`

---

### Bookmark
**Purpose:** User bookmarks for quick access to patients/assessments

**Key Fields:**
- `user` (ForeignKey to CustomUser) - User who created bookmark
- `bookmark_type` (CharField, choices) - Type (Patient/Assessment/Video/etc.)
- `item_id` (CharField) - ID of bookmarked item
- `title` (CharField) - Bookmark title
- `description` (TextField) - Optional description
- `notes` (TextField) - User notes
- `color` (CharField) - Color tag for organization
- `is_pinned` (BooleanField) - Pinned to top

**Relationships:**
- Many-to-One with CustomUser

---

### IndicationsForGMA
**Purpose:** Lookup table for GMA indication reasons

**Key Fields:**
- `indication` (CharField, unique) - Indication description
- `level` (CharField, choices) - Severity level
- `description` (TextField) - Detailed description

**Relationships:**
- Many-to-Many with GMAssessment

---

### DiagnosisList
**Purpose:** Lookup table for diagnosis options

**Key Fields:**
- `diagnosis_name` (CharField, unique) - Diagnosis name
- `icd_code` (CharField) - ICD-10 code
- `description` (TextField) - Clinical description
- `category` (CharField) - Diagnosis category

**Relationships:**
- Many-to-Many with GMAssessment

---

### Help
**Purpose:** Help article system

**Key Fields:**
- `title` (CharField, indexed) - Help article title
- `slug` (SlugField, unique) - URL-friendly slug
- `content` (RichTextField) - Article content (HTML)
- `category` (CharField) - Article category
- `tags` (CharField) - Comma-separated tags
- `is_published` (BooleanField) - Published status
- `view_count` (PositiveIntegerField) - View counter
- `search_keywords` (TextField) - SEO keywords

**Relationships:** None

---

## Users App (users/)

### CustomUser (extends AbstractUser)
**Purpose:** Extended Django user model with medical system features

**Inherited from AbstractUser:**
- `username`, `email`, `password`, `first_name`, `last_name`
- `is_staff`, `is_active`, `is_superuser`
- `date_joined`, `last_login`

**Additional Fields:**
- `employee_id` (CharField, unique) - Staff employee ID
- `department` (CharField) - Department/unit
- `designation` (CharField) - Job title
- `phone_number` (CharField, validated) - Contact number
- `profile_picture` (ImageField) - Profile photo (5MB max)
- `bio` (TextField) - Professional bio
- `email_verified` (BooleanField) - Email verification status
- `email_verification_token` (CharField) - Verification token
- `failed_login_attempts` (PositiveSmallIntegerField) - Login failure counter
- `account_locked_until` (DateTimeField) - Account lockout timestamp
- `password_changed_at` (DateTimeField) - Last password change
- `require_password_change` (BooleanField) - Force password change
- `two_factor_enabled` (BooleanField) - 2FA status
- `notification_preferences` (JSONField) - Notification settings

**Relationships:**
- One-to-Many with UserActivityLog
- One-to-Many with UserSession
- One-to-Many with Bookmark
- One-to-Many with Subscription
- Foreign keys in all models (added_by, last_edit_by)

**Validators:**
- `validate_phone_number` - Phone format validation
- Image size limit (5MB)

---

### UserActivityLog
**Purpose:** Audit trail for user actions

**Key Fields:**
- `user` (ForeignKey to CustomUser) - User who performed action
- `action_type` (CharField, choices) - Action (CREATE/UPDATE/DELETE/VIEW/LOGIN/LOGOUT)
- `model_name` (CharField) - Model affected
- `object_id` (CharField) - ID of affected object
- `object_repr` (CharField) - String representation of object
- `changes` (JSONField) - Change details (before/after values)
- `ip_address` (GenericIPAddressField) - Client IP
- `user_agent` (TextField) - Browser/device info
- `request_method` (CharField) - HTTP method (GET/POST/etc.)
- `request_path` (CharField) - URL path
- `session_key` (CharField) - Session identifier
- `success` (BooleanField) - Action success status
- `error_message` (TextField) - Error details if failed

**Relationships:**
- Many-to-One with CustomUser

**Indexes:** user, action_type, model_name, created_at

**Retention:** Configurable (recommend 90-180 days)

---

### UserSession
**Purpose:** Active session tracking and management

**Key Fields:**
- `user` (ForeignKey to CustomUser) - Session owner
- `session_key` (CharField, unique, indexed) - Django session key
- `ip_address` (GenericIPAddressField) - Client IP
- `user_agent` (TextField) - Browser/device string
- `device_type` (CharField) - Device classification (Desktop/Mobile/Tablet)
- `browser` (CharField) - Browser name
- `os` (CharField) - Operating system
- `location` (CharField) - Geographic location (if available)
- `is_active` (BooleanField, indexed) - Active session flag
- `last_activity` (DateTimeField, indexed) - Last activity timestamp
- `expires_at` (DateTimeField) - Session expiration

**Relationships:**
- Many-to-One with CustomUser

**Business Rules:**
- Sessions expire after 1 hour of inactivity (SESSION_COOKIE_AGE)
- Users can terminate sessions remotely
- Staff can view/terminate all user sessions

---

### DeveloperContacts
**Purpose:** Developer contact information

**Key Fields:**
- `name` (CharField) - Developer name
- `role` (CharField) - Role/position
- `email` (EmailField) - Contact email
- `phone` (CharField) - Contact phone
- `linkedin` (URLField) - LinkedIn profile
- `github` (URLField) - GitHub profile
- `is_active` (BooleanField) - Active status
- `display_order` (PositiveSmallIntegerField) - Sort order

**Relationships:** None

---

### Subscription
**Purpose:** User subscription/license management

**Key Fields:**
- `user` (ForeignKey to CustomUser) - Subscribed user
- `plan_name` (CharField) - Subscription plan
- `start_date` (DateField) - Subscription start
- `end_date` (DateField) - Subscription end
- `is_active` (BooleanField, indexed) - Active status
- `is_trial` (BooleanField) - Trial subscription flag
- `max_patients` (PositiveIntegerField) - Patient limit
- `max_storage_gb` (PositiveIntegerField) - Storage limit (GB)
- `features` (JSONField) - Enabled features
- `payment_status` (CharField, choices) - Payment status
- `auto_renew` (BooleanField) - Auto-renewal flag
- `renewal_date` (DateField) - Next renewal date

**Relationships:**
- Many-to-One with CustomUser

**Business Rules:**
- Subscription checked by `SubscriptionCheckMiddleware`
- Inactive subscriptions block access to create/edit operations

---

## Video App (video/)

### Video
**Purpose:** Video file storage and metadata for assessments

**Key Fields:**
- `patient` (ForeignKey to Patient) - Associated patient
- `title` (CharField, indexed) - Video title
- `description` (TextField) - Video description
- `file` (FileField) - Video file
- `file_size` (PositiveBigIntegerField) - Size in bytes
- `file_extension` (CharField) - File extension
- `mime_type` (CharField) - MIME type (validated)
- `duration` (DurationField) - Video duration
- `resolution` (CharField) - Video resolution (e.g., "1920x1080")
- `codec` (CharField) - Video codec
- `fps` (PositiveSmallIntegerField) - Frames per second
- `bitrate` (PositiveIntegerField) - Bitrate (kbps)
- `thumbnail` (ImageField) - Video thumbnail
- `is_processed` (BooleanField) - Processing complete flag
- `processing_status` (CharField) - Processing status
- `view_count` (PositiveIntegerField) - View counter

**File Limits:**
- Max size: 2GB
- Allowed formats: .mp4, .mov, .avi, .mkv, .webm

**Validators:**
- MIME type validation (video/*)
- File size limit (2GB)

**Relationships:**
- Many-to-One with Patient
- One-to-Many with GMAssessment (via file_id)

**Upload Path:** `media/videos/`

**Metadata Extraction:** Uses `extract_video_metadata()` utility

---

## Reports App (reports/)

### ReportTemplate
**Purpose:** Reusable report templates

**Key Fields:**
- `name` (CharField, unique) - Template name
- `description` (TextField) - Template description
- `report_type` (CharField, choices) - Type (PDF/Excel/CSV)
- `template_file` (FileField) - Template file
- `is_active` (BooleanField) - Active status
- `default_config` (JSONField) - Default configuration
- `fields_included` (JSONField) - Included data fields
- `filters_available` (JSONField) - Available filter options
- `usage_count` (PositiveIntegerField) - Usage counter

**Relationships:**
- One-to-Many with ReportConfig

---

### ReportConfig
**Purpose:** User-specific report configurations

**Key Fields:**
- `user` (ForeignKey to CustomUser) - Report owner
- `template` (ForeignKey to ReportTemplate) - Base template
- `name` (CharField) - Config name
- `description` (TextField) - Config description
- `filters` (JSONField) - Applied filters
- `columns` (JSONField) - Selected columns
- `sort_order` (JSONField) - Sort configuration
- `is_default` (BooleanField) - Default for user
- `is_shared` (BooleanField) - Shared with other users
- `last_generated` (DateTimeField) - Last generation time

**Relationships:**
- Many-to-One with CustomUser
- Many-to-One with ReportTemplate

---

## Problem List App (problemlist/)

### Problem
**Purpose:** Clinical problem tracking and management

**Key Fields:**
- `patient` (ForeignKey to Patient) - Associated patient
- `title` (CharField, indexed) - Problem title
- `description` (TextField) - Detailed description
- `problem_type` (CharField, choices) - Type (Medical/Social/Developmental/Other)
- `severity` (CharField, choices) - Severity (Low/Medium/High/Critical)
- `status` (CharField, choices, indexed) - Status (Active/Resolved/Under Investigation/Monitoring)
- `identified_date` (DateField) - Date identified
- `resolved_date` (DateField, null) - Date resolved
- `onset_date` (DateField) - Onset date (if known)
- `priority` (PositiveSmallIntegerField) - Priority ranking (1-5)
- `is_chronic` (BooleanField) - Chronic condition flag
- `requires_monitoring` (BooleanField) - Monitoring required
- `monitoring_frequency` (CharField) - Monitoring schedule
- `clinical_notes` (RichTextField) - Clinical notes
- `treatment_plan` (RichTextField) - Treatment approach
- `outcomes` (TextField) - Outcome notes
- `related_assessments` (JSONField) - Linked assessment IDs

**Relationships:**
- Many-to-One with Patient
- One-to-Many with ProblemAction

**Indexes:** patient, title, status, created_at

---

### ProblemAction
**Purpose:** Action log for problem tracking

**Key Fields:**
- `problem` (ForeignKey to Problem) - Associated problem
- `action_type` (CharField, choices) - Action type (Assessment/Treatment/Consultation/Follow-up/Note)
- `action_date` (DateField) - Date of action
- `description` (TextField) - Action description
- `outcome` (TextField) - Action outcome
- `performed_by` (ForeignKey to CustomUser) - Staff who performed action
- `attachments` (JSONField) - Attached document references

**Relationships:**
- Many-to-One with Problem
- Many-to-One with CustomUser (performed_by)

---

## Database Schema Summary

### Total Counts
- **Models:** 21
- **Django Apps:** 5 (patients, users, video, reports, problemlist)
- **Foreign Key Relationships:** 35+
- **Many-to-Many Relationships:** 2

### Indexing Strategy
**Indexed Fields** (for query performance):
- All unique identifiers (BHT, NNC, PTC, PC, PIN)
- Patient names (baby_name, mother_name)
- Date fields (dob_tob, assessment_date, created_at)
- Status fields (is_active, status)
- Foreign keys (automatic index by Django)

### Data Integrity

**Cascade Rules:**
- Patient deletion → CASCADE to all related assessments (with protection if videos exist)
- User deletion → PROTECT (prevent if records exist)
- Video deletion → RESTRICT if linked to assessments

**Unique Constraints:**
- Patient identifiers (bht, nnc_no, ptc_no, pc_no, pin) - individually unique, can be null
- Username, email (in CustomUser)
- Session keys
- Help article slugs

---

## Migration Management

**Migration Directories:**
- `patients/migrations/`
- `users/migrations/`
- `video/migrations/`
- `reports/migrations/`
- `problemlist/migrations/`

**Commands:**
```bash
python manage.py makemigrations [app_name]
python manage.py migrate [app_name]
python manage.py showmigrations
```

**Schema Version Control:**
- All schema changes tracked via Django migrations
- Migration files committed to git
- Production migrations run via deployment scripts

---

## Data Validation Rules

### Medical Domain Validations
- **Birth Weight:** 300-8000g (with POG-specific enhanced validation)
- **APGAR Scores:** 0-10 (both 1-minute and 5-minute)
- **Gestational Age:** 20-44 weeks + 0-6 days
- **Head Circumference:** Positive float value
- **HINE Total Score:** 0-78

### File Upload Validations
- **MIME Type:** Verified using python-magic library
- **File Extensions:** Whitelisted by type
- **Size Limits:** Enforced at model and settings level
- **Path Sanitization:** `sanitize_filename()` utility

### String Validations
- **Phone Numbers:** Regex validation for international formats
- **Email:** Django EmailField validation
- **Text Input:** XSS sanitization via `sanitize_text_input()`
- **HTML Content:** Sanitization via `bleach` library

---

## Query Optimization Patterns

### Recommended Practices
```python
# Use select_related for ForeignKey
patients = Patient.objects.select_related('added_by', 'last_edit_by')

# Use prefetch_related for reverse ForeignKey
patient = Patient.objects.prefetch_related('gmassessment_set').get(pk=pk)

# Use only() for specific fields
patients = Patient.objects.only('bht', 'baby_name', 'dob_tob')

# Use defer() to exclude large fields
patients = Patient.objects.defer('clinical_notes', 'physical_examination')
```

### N+1 Query Prevention
- All list views use `select_related()` for foreign keys
- Assessment views use `prefetch_related()` for related objects
- Avoid accessing foreign keys in templates without prefetching

---

## Database Backup

**Backup Commands:**
```bash
# SQLite backup
cp db.sqlite3 db_backup_$(date +%Y%m%d).sqlite3

# PostgreSQL backup
pg_dump ndas_db > backup_$(date +%Y%m%d).sql
```

**Backup Location:** `db backup/` directory (project root)

**Retention:** Keep last 30 days of backups

---

## Performance Considerations

### Connection Pooling
- **Production:** `CONN_MAX_AGE = 300` (5 minutes)
- **Development:** No pooling (SQLite)

### Query Timeout
- **SQLite:** 120 seconds
- **PostgreSQL:** 60 seconds connection timeout

### Cache Strategy
- Session data cached (Redis/LocMem)
- Query results not cached by default
- Consider Django cache framework for frequently accessed data

---

## Medical Data Privacy

### HIPAA/PHI Considerations
- Patient data considered Protected Health Information (PHI)
- Access controlled via Django authentication
- Activity logged via `UserActivityLog`
- Session timeout: 1 hour
- Audit trail for all data modifications

### Data Anonymization
- Report generation supports anonymization
- Patient identifiers can be excluded from exports
- De-identification utilities in `reports/utils/`

---

## Future Schema Enhancements

### Potential Additions
- **Audit Trail:** Comprehensive versioning system (django-reversion)
- **Soft Delete:** Archived records instead of hard delete
- **Full-Text Search:** PostgreSQL full-text search for clinical notes
- **Data Warehousing:** Separate analytics database
- **Document Versioning:** Track attachment versions
- **Multi-language:** Internationalization fields

---

## Database Diagram

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

┌──────────────┐       ┌──────────────┐       ┌───────────────┐
│ Problem      │       │ Attachment   │       │ Bookmark      │
│              │       │              │       │               │
│ - title      │       │ - file       │       │ - item_id     │
│ - status     │       │ - file_type  │       │ - user        │
│ - severity   │       │ - mime_type  │       └───────────────┘
└──────────────┘       └──────────────┘
```

**Note:** All models inherit TimeStampedModel and UserTrackingMixin, providing automatic created_at, updated_at, added_by, last_edit_by fields.
