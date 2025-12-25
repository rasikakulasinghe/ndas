# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Last Updated:** 2025-12-25

<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

## Project Overview

**Neurodevelopmental Assessment System (NDAS)** - Django-based medical information system for managing patient records, video-based neurodevelopmental assessments, and standardized evaluation workflows in pediatric healthcare settings.

**Stack:** Django 4.2.16 + PostgreSQL/SQLite + AdminLTE 3.2 + Bootstrap 4.6 + HTMX + Video.js

**Apps:**
- `patients/` - Patient management, assessments, medical records (primary app at root URL)
- `video/` - Video file handling and processing
- `users/` - Authentication, profiles, subscriptions, activity tracking
- `reports/` - Report generation (PDF and Excel exports with data anonymization)
- `problemlist/` - Patient problem tracking and management

## Development Commands

```bash
# Environment (Windows)
venv\Scripts\activate
pip install -r requirements.txt

# Database
python manage.py makemigrations [app_name]
python manage.py migrate
python manage.py createsuperuser

# Run
python manage.py runserver

# Testing
python manage.py test                          # All tests
python manage.py test patients                 # App tests
python manage.py test users.tests.TestClassName  # Specific test

# OpenSpec
openspec list                                  # List active changes
openspec show [item]                           # View change/spec
openspec validate [change-id] --strict         # Validate change
openspec archive <change-id> --yes             # Archive deployed
```

## Architecture Patterns

### Model Development (MANDATORY)

All models MUST inherit from both base classes:

```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

class MyModel(TimeStampedModel, UserTrackingMixin):
    # Auto-provides: created_at, updated_at, added_by, last_edit_by
    # User tracking auto-populated by UserActivityMiddleware
    pass
```

**Custom Code Organization:**
- `ndas/custom_codes/Custom_abstract_class.py` - Base models
- `ndas/custom_codes/choice.py` - All TextChoices for dropdowns
- `ndas/custom_codes/validators.py` - Field validators and sanitization functions
- `ndas/custom_codes/custom_methods.py` - Utilities (e.g., `getCountZeroIfNone()`, `calculate_age_string()`, `extract_video_metadata()`)
- `ndas/custom_codes/ndas_enums.py` - Enumerations (e.g., `PtStatus`)
- `ndas/custom_codes/delete_helpers.py` - Centralized entity deletion utilities (permission checks, business rules, redirects)
- `ndas/custom_codes/security_middleware.py` - Custom security headers and CSP middleware

**Model Rules:**
1. Add choices to `choice.py` (use Django TextChoices)
2. Use validators from `validators.py`
3. Add `db_index=True` for searchable/filterable fields
4. Use date-based upload paths: `upload_to="path/%Y/%m/"`

### View Pattern

```python
from django.contrib.auth.decorators import login_required
from ndas.custom_codes.custom_methods import getCountZeroIfNone

@login_required(login_url="user-login")
def my_view(request):
    var_objects = MyModel.objects.all()
    count = getCountZeroIfNone(var_objects)
    return render(request, "myapp/template.html", {"var_objects": var_objects, "count": count})
```

### Form Pattern

```python
class MyForm(forms.ModelForm):
    class Meta:
        model = MyModel
        fields = ["field1", "field2"]
        widgets = {
            "text_field": forms.TextInput(attrs={"class": "form-control"}),
            "date_field": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }
```

### Template Pattern (MANDATORY)

```django
{% extends 'src/base.html' %}  {# Authenticated pages #}
{% load static %}
{% block title %}Section - Action | Context{% endblock %}
{% block main_content %}
<div class="container-fluid">
  {% csrf_token %}
  <!-- Content -->
</div>
{% endblock %}
```

**Template Rules:**
- Extend `'src/base.html'` (authenticated) or `'src/basic_plane.html'` (public)
- Include `{% csrf_token %}` in container-fluid divs
- **DO NOT change CSS framework** - AdminLTE 3.2 + Bootstrap 4.6 + Font Awesome 6.4
- Naming: `manager.html` (lists), `add.html` (create), `edit.html` (update), `view.html` (detail)

### Security Architecture

**Middleware Stack (CRITICAL ORDER):**
1. SecurityMiddleware
2. WhiteNoiseMiddleware
3. CSPMiddleware
4. AdditionalSecurityHeadersMiddleware (custom - adds Referrer-Policy, Permissions-Policy)
5. SessionMiddleware
6. CommonMiddleware
7. CsrfViewMiddleware
8. AuthenticationMiddleware
9. UserActivityMiddleware (custom - auto-tracks user changes)
10. MessageMiddleware
11. XFrameOptionsMiddleware
12. UserAgentMiddleware
13. SubscriptionCheckMiddleware (custom)
14. SecurityHeadersValidationMiddleware (production only - validates headers)

**Security Headers (via `ndas/custom_codes/security_middleware.py`):**
- Referrer-Policy: strict-origin-when-cross-origin
- Cross-Origin-Opener-Policy: same-origin
- X-Permitted-Cross-Domain-Policies: none
- Permissions-Policy: disables geolocation, camera, microphone, payment, usb

**Content Security Policy (CSP):**
- Nonces enabled for script-src (production only)
- Inline styles allowed (templates use many inline styles)
- CDN sources whitelisted: jsdelivr, cdnjs, googleapis, zencdn

**Security Features:**
- Session timeout: 1 hour with browser-close expiry
- Rate limiting with django-ratelimit (24 CRUD operations protected)
  * Create/Edit: 10/min per user + 20/min per IP
  * Delete: 5/min per user + 10/min per IP
- Input sanitization for XSS prevention (`sanitize_text_input()`)
  * Removes HTML tags, scripts, event handlers
  * Preserves medical notation (e.g., "< 5 mg/dL", "> 38°C")
- Filename sanitization (`sanitize_filename()`)
  * Prevents path traversal attacks (../, ..\)
  * Removes invalid filesystem characters
  * Applied to all file uploads (videos, attachments, thumbnails)
- File upload validation (type, size, content)
- Medical data privacy (HIPAA awareness)
- Password validation: minimum 12 characters, complexity checks

**File Upload Limits (from `settings.FILE_UPLOAD_LIMITS`):**
- Videos: 2GB (mp4, mov, avi, mkv, webm)
- Images: 10MB (jpg, jpeg, png, gif, bmp, webp)
- Documents: 100MB (doc, docx, txt, rtf, odt, pdf)
- Profile pictures: 5MB
- Memory limit: 100MB

## Medical Domain

**Patient Identifiers:** BHT, NNC, PTC, PC, PIN, Disk No.

**Validation Ranges:**
- Birth weight: 300g - 8000g (basic), or POG-specific ranges (enhanced)
- APGAR scores: 0-10
- Gestational age: 20-44 weeks + 0-6 days

**POG-Specific Birth Weight Validation:**
The system provides enhanced birth weight validation based on gestational age:
```python
from ndas.custom_codes.validators import (
    validate_birth_weight_for_gestational_age,
    BIRTH_WEIGHT_RANGES_BY_POG
)

# Example usage
is_valid, message = validate_birth_weight_for_gestational_age(
    birth_weight=500,   # grams
    pog_weeks=22,       # weeks
    pog_days=3,         # optional additional days
    strict=False        # True uses typical ranges, False uses absolute ranges
)

# Ranges support linear interpolation for POG+days
# Example ranges (BIRTH_WEIGHT_RANGES_BY_POG):
# 22 weeks: min=350g, max=700g, typical_min=400g, typical_max=600g
# 37 weeks: min=2200g, max=4500g, typical_min=2500g, typical_max=4000g
```

**Assessment Types:** GPA, HINE, CDIC, Developmental

### Patient Model Field Reference (CRITICAL)

**Common Field Errors - Always verify field names:**

```python
# Identifiers
patient.bht              # NOT bht_number
patient.nnc_no           # NOT nnc_number
patient.ptc_no           # NOT ptc_number
patient.pc_no            # NOT pc_number
patient.pin              # NOT pin_number
patient.disk_no          # NOT disk_number

# Demographics
patient.baby_name        # NOT patient_name or name
patient.mother_name      # NOT mother
patient.gender           # ✓ correct
patient.dob_tob          # NOT date_of_birth or dob

# Birth Data
patient.pog_wks          # NOT gestational_age_weeks or pog_weeks
patient.pog_days         # NOT gestational_age_days
patient.mo_delivery      # NOT mode_of_delivery
patient.birth_weight     # NOT birth_weight_g or weight
patient.length           # ✓ correct
patient.hc               # NOT head_circumference

# APGAR Scores
patient.apgar_1          # NOT apgar_1_min or apgar1
patient.apgar_5          # NOT apgar_5_min or apgar5
patient.apgar_10         # NOT apgar_10_min or apgar10
```

## Key Development Rules

**Always:**
- Inherit models from `TimeStampedModel, UserTrackingMixin`
- Add choices to `ndas/custom_codes/choice.py`
- Use validators from `ndas/custom_codes/validators.py`
- Index searchable fields with `db_index=True`
- Extend base templates (`src/base.html` or `src/basic_plane.html`)
- Include CSRF tokens in forms
- Validate file uploads

**Never:**
- Add choices directly in models
- Skip field validation or indexing
- Change CSS framework or Bootstrap versions
- Bypass or reorder security middleware
- Store sensitive config in code (use `.env`)
- Use incorrect Patient model field names (verify above)

## Production Configuration

**Database:** SQLite (dev) / PostgreSQL (prod with connection pooling)
**Cache/Session:** Redis (prod) / LocMem (dev)
**Static Files:** WhiteNoise with compression
**External Dependencies:** FFmpeg, Redis, PostgreSQL, Celery (optional)

## Reports Module

**PDF Generation** (`reports/utils/pdf_generator.py`):
- `BasePDFGenerator` - Base class with styling, headers/footers, page configuration
- `PatientPDFGenerator` - Comprehensive patient reports
- `GMAssessmentPDFGenerator` - GM Assessment reports
- `HINEAssessmentPDFGenerator` - HINE Assessment reports
- `DAAssessmentPDFGenerator` - Developmental Assessment reports
- `CDICAssessmentPDFGenerator` - CDIC Record reports
- `GPAAssessmentPDFGenerator` - General Paediatric Assessment reports

**Excel Generation** (`reports/utils/excel_generator.py`):
- `ExcelReportGenerator` - Research data exports with:
  - Customizable field selection
  - Data anonymization for research compliance
  - Advanced filtering (POG, APGAR, GM diagnosis, HINE score, gender)
  - Data quality metrics and summary statistics
  - Multi-sheet workbooks with assessment-specific worksheets

**Report Models** (`reports/models.py`):
- `ReportTemplate` - Configurable header/footer/logo templates
- `ReportConfig` - System-wide report configuration settings

## Delete Helpers Module

**Entity Deletion Utilities** (`ndas/custom_codes/delete_helpers.py`):
```python
from ndas.custom_codes.delete_helpers import (
    has_delete_permission,    # Check user permission for entity deletion
    validate_can_delete,      # Business rule validation (e.g., videos in assessments)
    get_entity_display_name,  # Human-readable name for entities
    get_redirect_url,         # Post-deletion redirect URL by entity type
    get_entity_warning_items, # Cascade deletion warnings
    get_entity_detail_items,  # Entity details for confirmation modal
)
```

**Deletion Business Rules:**
- Superusers can delete any entity
- Staff can delete their own records (based on `added_by`)
- Videos cannot be deleted if referenced in assessments
- Patients show cascade warnings for related videos/assessments/attachments

## Unified Delete Confirmation System

**JavaScript Module** (`static/js/delete-confirmation.js`):
- Singleton `window.DeleteConfirmation` object
- Handles password-verified deletion via AJAX DELETE requests
- Uses event delegation for dynamic content support

**Modal Template** (`templates/src/partials/delete_confirmation_modal.html`):
```django
{% load delete_modal_tags %}
{% include 'src/partials/delete_confirmation_modal.html' with
    modal_id="deletePatientModal"
    entity_type="Patient"
    delete_url=delete_url
    redirect_url=redirect_url
    warning_items=warning_items
    detail_items=detail_items
%}
```

**Template Tag** (`{% load delete_modal_tags %}`):
- Provides `{% delete_modal entity %}` for quick modal generation

**Usage Pattern:**
```html
<!-- Trigger button -->
<button class="delete-trigger-btn" data-modal-target="deletePatientModal">
    <i class="fas fa-trash"></i> Delete
</button>
<!-- Modal renders with password verification and AJAX handling -->
```

## Recent Optimizations (December 2025)

Major performance and security improvements completed across three phases:

### Phase 2: Performance & Security

**Input Sanitization (XSS Prevention):**
- `sanitize_text_input()` function in validators.py
- Applied to 6 text fields in ProblemForm and ProblemActionForm
- Preserves medical notation (e.g., "< 5 mg/dL", "> 38C")
- Removes HTML tags, script elements, event handlers
- 7 comprehensive tests added

**Rate Limiting on CRUD Operations (24 operations protected):**
- Pattern: 10/min user + 20/min IP for create/edit
- Pattern: 5/min user + 10/min IP for delete
- Applied to: patients, video, problemlist, HINE, CDIC, DA, GPA, attachments

**Video Filter Optimization:**
- Replaced LEFT JOIN filters with Exists() subqueries in `getPatientList()`
- Optimized PtStatus.NEW and PtStatus.DX_NORMAL filters
- Significant query performance improvement

**Count Query Optimization:**
- Replaced 4 separate `.count()` calls with single `aggregate()` query in 7 manager functions
- 75% query reduction using Q objects and conditional aggregation

### Phase 3: Database Optimization

**Database Indexes Added (5 fields):**
- `CustomUser.mobile_primary`
- `IndicationsForGMA.title` and `.level`
- `DiagnosisList.abr` and `.title`

**TextField to CharField Conversion:**
- `DiagnosisList.title`: TextField to CharField(255)
- Better database performance (VARCHAR vs TEXT)

**Unique Constraints Added (3 fields):**
- `DiagnosisList.abr`
- `IndicationsForGMA.title`

**Subscription Race Condition Fix:**
- Moved `_clear_cache()` outside `transaction.atomic()`

**Activity Log Query Optimization:**
- Added `select_related('user')` to 3 queries
- 96% query reduction (51 to 2 queries for 50 logs)

**Username List Query Optimization:**
- Optimized `recent_users` query in admin dashboard
- Uses `.only('id', 'username', 'position', 'is_active', 'date_joined')`
- Reduces memory usage and query overhead

**Video MIME Type Validation (Security):**
- Added `python-magic-bin` dependency for content-based file type detection
- Validates video file content (not just extension) in `video/forms.py`
- Prevents malicious file uploads disguised as videos
- Supports 9 video MIME types (mp4, mov, avi, mkv, webm, wmv variants)
- Security logging for rejected uploads
- Graceful fallback if python-magic unavailable

**Date Cross-Validation in problemlist Forms:**
- `date_identified >= date_of_onset`
- `date_resolved >= date_of_onset`
- `date_resolved >= date_identified`

**Comprehensive Filename Sanitization:**
- `sanitize_filename()` function in validators.py
- Prevents path traversal attacks (../, ..\)
- Removes invalid filesystem characters
- Applied to 4 upload_to functions (videos, attachments, thumbnails)

**POG-Specific Birth Weight Validation:**
- `BIRTH_WEIGHT_RANGES_BY_POG` dictionary with medical ranges (20-44 weeks)
- `validate_birth_weight_for_gestational_age()` function
- Supports linear interpolation for POG+days
- 20 comprehensive tests added

### Remaining Known Issues

See `temp_documents/BUG_AND_PERFORMANCE_ANALYSIS.md` and `temp_documents/BUG_FIX_PLAN.md` for:
- Additional performance optimizations (template caching, prefetch_related)
- Static file optimization opportunities
- HTTP method restrictions (require_GET, require_POST)

## Quick Reference

```python
# Base model imports (MANDATORY for all new models)
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

# Custom utilities
from ndas.custom_codes.custom_methods import getCountZeroIfNone, calculate_age_string, extract_video_metadata
from ndas.custom_codes.choice import MY_CHOICES  # Replace with actual choice class
from ndas.custom_codes.ndas_enums import PtStatus
from ndas.custom_codes.delete_helpers import (
    has_delete_permission, validate_can_delete, get_redirect_url,
    get_entity_warning_items, get_entity_detail_items
)

# Validators (validators.py - comprehensive validation and sanitization)
from ndas.custom_codes.validators import (
    # File validation
    validate_video_file,
    validate_attachment_file,
    sanitize_filename,           # Prevents path traversal, removes invalid chars

    # Text sanitization (XSS prevention)
    sanitize_text_input,         # Removes HTML/scripts, preserves medical notation

    # Medical validation
    validate_birth_weight,       # Basic range: 300g - 8000g
    validate_birth_weight_for_gestational_age,  # POG-specific validation
    BIRTH_WEIGHT_RANGES_BY_POG,  # Reference ranges by gestational age
    validate_apgar_score,        # Range: 0-10
    validate_pog_weeks,          # Range: 20-44 weeks
    validate_pog_days,           # Range: 0-6 days
)

# Django shortcuts (ALWAYS use get_object_or_404 instead of .objects.get())
from django.shortcuts import render, redirect, get_object_or_404

# Rate limiting (applied to 24 CRUD operations)
from django_ratelimit.decorators import ratelimit
# Patterns: 10/m user + 20/m IP for create/edit, 5/m user + 10/m IP for delete

# Middleware auto-tracking (no manual intervention needed)
# added_by - Set on creation
# last_edit_by - Updated on save

# Age calculation utility
age_str = calculate_age_string(birth_date, current_date, format_type="medical")
# Returns: "2 weeks and 3 days", "1 year and 2 months", etc.

# Video metadata extraction
metadata = extract_video_metadata(video_path)
# Returns: {'duration_seconds': 120, 'resolution': '1920x1080', ...}

# File upload limits (from settings)
from django.conf import settings
max_video_size = settings.FILE_UPLOAD_LIMITS['VIDEO_MAX_SIZE']  # 2GB
allowed_video_ext = settings.ALLOWED_FILE_EXTENSIONS['VIDEO']  # ['.mp4', '.mov', ...]

# Sanitization examples
clean_text = sanitize_text_input("<script>alert('xss')</script>Test")  # Returns: "alert('xss')Test"
clean_name = sanitize_filename("../../etc/passwd")  # Returns: "etc_passwd"

# POG-specific birth weight validation
is_valid, msg = validate_birth_weight_for_gestational_age(500, 22, pog_days=3, strict=False)
```

## Environment Configuration

**Required Environment Variables (.env):**
```bash
SECRET_KEY=your-secret-key
DEBUG=True/False
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (optional - defaults to SQLite)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=ndas
DB_USER=user
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# Cache (optional - defaults to LocMem)
REDIS_URL=redis://localhost:6379/0

# Security (production)
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```
