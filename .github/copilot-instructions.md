# NDAS - Neurodevelopmental Assessment System

**Last Updated:** 2025-12-25

Django-based medical records system for managing patient assessments, video recordings, and comprehensive medical data with security-focused architecture.

## Core Architecture Patterns

### Model Design (MANDATORY)
All models inherit from **two abstract base classes** in `ndas/custom_codes/Custom_abstract_class.py`:
```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

class MyModel(TimeStampedModel, UserTrackingMixin):
    # Automatically provides:
    # - created_at, updated_at (TimeStampedModel)
    # - added_by, last_edit_by (UserTrackingMixin - auto-populated by middleware)
    pass
```

### Centralized Configuration
- **Choices**: All dropdown options in `ndas/custom_codes/choice.py` using Django TextChoices
- **Validators**: Medical data validation in `ndas/custom_codes/validators.py`
- **Utilities**: Shared functions in `ndas/custom_codes/custom_methods.py` (includes `getCountZeroIfNone()`, `calculate_age_string()`, `extract_video_metadata()`)
- **Enumerations**: Status and enums in `ndas/custom_codes/ndas_enums.py`
- **Delete Helpers**: Entity deletion utilities in `ndas/custom_codes/delete_helpers.py` (permission checks, business rules, redirects)

### URL Structure
- `""` (root) → `patients/` app (primary interface)
- `users/` → Authentication, profiles, subscriptions, activity tracking
- `video/` → Video file management and processing
- `reports/` → Report generation (PDF and Excel exports with data anonymization)
- `problemlist/` → Patient problem tracking and management
- `admin/` → Django admin with custom branding

## Key Models

### Patient Model
Core entity with multiple unique identifiers (BHT, NNC, PTC, PC, PIN). All searchable fields have `db_index=True`. Rich medical data including birth information, APGAR scores, gestational age.

### Video Model
Linked to patients with metadata, processing status tracking, and FFmpeg integration.

### CustomUser Model
Extended AbstractUser with professional positions, contact info, profile pictures, and activity tracking.

### Assessment Models
- GMAssessment (General Motor Assessment)
- HINEAssessment (Hammersmith Infant Neurological Examination)
- DevelopmentalAssessment
- CDICRecord (Child Development Inventory and Chart)
- GPARecord (General Paediatric Assessment)

## Development Commands

```powershell
# Environment
venv\Scripts\activate
pip install -r requirements.txt

# Database
python manage.py makemigrations && python manage.py migrate
python manage.py createsuperuser

# Development
python manage.py runserver

# Testing
python manage.py test
python manage.py test patients  # Specific app
npx playwright test  # E2E tests
```

## Development Patterns

### Form Pattern
```python
class MyForm(forms.ModelForm):
    field = forms.ChoiceField(
        choices=MY_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"})
    )

    class Meta:
        widgets = {
            "text_field": forms.TextInput(attrs={"class": "form-control"}),
            "textarea_field": forms.Textarea(attrs={"class": "form-control", "rows": 4})
        }
```

### View Pattern
```python
from django.shortcuts import render, redirect, get_object_or_404

@login_required(login_url="user-login")
def my_view(request, pk):
    # ALWAYS use get_object_or_404() instead of .objects.get()
    selected_object = get_object_or_404(MyModel, id=pk)

    # Use select_related for foreign keys to avoid N+1 queries
    related_objects = RelatedModel.objects.filter(parent=selected_object).select_related(
        'added_by', 'last_edit_by'
    ).order_by("-id")

    count = getCountZeroIfNone(related_objects)  # Custom utility
    context = {"object": selected_object, "related": related_objects, "count": count}
    return render(request, "myapp/template.html", context)
```

### Template Pattern (MANDATORY)
```django
{% extends 'src/base.html' %}  # For authenticated pages
{% load static %}
{% block title %}Section - Action | Context{% endblock %}
{% block main_content %}
<div class="container-fluid">
  {% csrf_token %}
  <!-- Content here -->
</div>
{% endblock %}
```

**Template Naming:**
- `manager.html` - List/management views
- `add.html` - Creation forms
- `edit.html` - Update forms
- `view.html` - Detail views

## Frontend Architecture

### Technology Stack (DO NOT CHANGE)
- **AdminLTE 3.2** - Core layout and components
- **Bootstrap 4.6** - Grid system, utilities, forms
- **Font Awesome 6.4** - Icons
- **jQuery 3.6** - DOM manipulation
- **HTMX 1.9** - Dynamic interactions
- **Select2** - Enhanced form controls
- **Video.js** - Video playback
- **CKEditor** - Rich text editing

### UI Component Patterns
- **Info Boxes**: `info-box` class with consistent icons
- **Cards**: `card` class with `card-header`, `card-body`
- **Tables**: `table table-hover table-striped` wrapped in `.table-responsive`
- **Buttons**: Bootstrap button classes with Font Awesome icons
- **Color Scheme**: Primary (blue), success (green), warning (yellow), danger (red)

### Responsive Design
- Mobile-first approach with Bootstrap 4's grid system
- Collapsible sidebar on mobile
- All tables wrapped in `.table-responsive`
- Test on desktop, tablet, and mobile

## Security Architecture

### Middleware Stack (in order - CRITICAL)
1. SecurityMiddleware
2. WhiteNoiseMiddleware
3. CSPMiddleware (Content Security Policy)
4. AdditionalSecurityHeadersMiddleware (custom - Referrer-Policy, Permissions-Policy)
5. SessionMiddleware
6. CommonMiddleware
7. CsrfViewMiddleware
8. AuthenticationMiddleware
9. UserActivityMiddleware (custom - auto-populates added_by/last_edit_by)
10. MessageMiddleware
11. XFrameOptionsMiddleware
12. UserAgentMiddleware
13. SubscriptionCheckMiddleware (custom)
14. SecurityHeadersValidationMiddleware (production only)

### Security Headers (via `ndas/custom_codes/security_middleware.py`)
- Referrer-Policy: strict-origin-when-cross-origin
- Cross-Origin-Opener-Policy: same-origin
- X-Permitted-Cross-Domain-Policies: none
- Permissions-Policy: disables geolocation, camera, microphone, payment, usb

### Security Features
- CSRF protection on all forms
- Rate limiting with django-ratelimit
- Session timeout: 1 hour with browser close expiry
- Comprehensive file upload validation
- User activity tracking for audit trails
- Password validation: minimum 12 characters, complexity checks
- CSP nonces for scripts in production

### File Upload Limits (from `settings.FILE_UPLOAD_LIMITS`)
- Video files: 2GB max (mp4, mov, avi, mkv, webm)
- Images: 10MB max (jpg, jpeg, png, gif, bmp, webp)
- Documents: 100MB max (doc, docx, txt, rtf, odt, pdf)
- Profile pictures: 5MB max
- Memory limit: 100MB

## Critical Rules

### When Adding New Models
1. Inherit from `TimeStampedModel, UserTrackingMixin`
2. Add choices to `ndas/custom_codes/choice.py`
3. Create validators in `ndas/custom_codes/validators.py`
4. Use `db_index=True` for searchable fields
5. Include comprehensive `help_text` for medical fields
6. Run: `python manage.py makemigrations && python manage.py migrate`

### File Upload Handling
```python
file_field = models.FileField(
    upload_to="path/%Y/%m/",
    validators=[validate_video_file],  # Or appropriate validator
)
```

### UI Development Rules
1. Extend `'src/base.html'` for authenticated pages or `'src/basic_plane.html'` for public
2. Include `{% csrf_token %}` in all container-fluid divs
3. Use consistent form classes from `patients/forms.py` patterns
4. Follow AdminLTE structure: info-box, card layouts, table patterns
5. Initialize components properly: Bootstrap tooltips, Select2, HTMX
6. Use custom utilities from `static/js/app-utils.js`

## Production Features

- **Database**: SQLite (dev), PostgreSQL (production-ready)
- **Caching**: Redis with django-redis
- **Task Processing**: Celery for video processing
- **Monitoring**: Sentry SDK
- **Static Files**: WhiteNoise with compression
- **Environment**: `.env` file with python-decouple

## Data Flow Patterns

- **Patient → Video → Assessment**: Core workflow
- **User tracking**: All CUD operations auto-track user via middleware
- **Status management**: Use `ndas_enums.PtStatus` for patient status filtering
- **Search optimization**: Indexed fields, use `getPatientList()` for filtered queries

## Medical Domain Context

### Patient Identifiers
- BHT (Bed Head Ticket)
- NNC (National Neonatal Code)
- PTC (Perinatal Transport Card)
- PC (Patient Card)
- PIN (Patient Identification Number)
- Disk No. (Disk Number)

### Medical Data Validation
- Birth weights: 300g - 8000g
- APGAR scores: 0-10 scale
- Gestational age (POG): 20-44 weeks + 0-6 days
- Date validations for medical timelines

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

## Reports Module

### PDF Generation (`reports/utils/pdf_generator.py`)
- `BasePDFGenerator` - Base class with common styling, headers/footers
- `PatientPDFGenerator` - Comprehensive patient reports
- `GMAssessmentPDFGenerator`, `HINEAssessmentPDFGenerator`, `DAAssessmentPDFGenerator`, `CDICAssessmentPDFGenerator`, `GPAAssessmentPDFGenerator` - Assessment-specific reports

### Excel Generation (`reports/utils/excel_generator.py`)
- `ExcelReportGenerator` - Research data exports with:
  - Customizable field selection
  - Data anonymization (replaces patient identifiers with anonymous IDs)
  - Advanced filtering (POG, APGAR, GM diagnosis, HINE score, gender, resuscitation status)
  - Data quality metrics and summary statistics

### Report Models (`reports/models.py`)
- `ReportTemplate` - Configurable header/footer/logo templates
- `ReportConfig` - System-wide report configuration settings

## Delete Helpers Module

### Entity Deletion (`ndas/custom_codes/delete_helpers.py`)
```python
from ndas.custom_codes.delete_helpers import (
    has_delete_permission,    # Check user permission for deletion
    validate_can_delete,      # Business rule validation
    get_entity_display_name,  # Human-readable entity name
    get_redirect_url,         # Post-deletion redirect
    get_entity_warning_items, # Cascade deletion warnings
    get_entity_detail_items,  # Entity details for modal
)
```

**Deletion Rules:**
- Superusers can delete any entity
- Staff can delete their own records (based on `added_by`)
- Videos cannot be deleted if referenced in assessments
- Patients show warnings for cascade-deleted videos/assessments/attachments

## Unified Delete Confirmation System

### JavaScript Module (`static/js/delete-confirmation.js`)
- Singleton `window.DeleteConfirmation` object
- Password-verified deletion via AJAX DELETE requests
- Event delegation for dynamic content support

### Modal Template (`templates/src/partials/delete_confirmation_modal.html`)
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

### Usage Pattern
```html
<!-- Trigger button -->
<button class="delete-trigger-btn" data-modal-target="deletePatientModal">
    <i class="fas fa-trash"></i> Delete
</button>
```

## Known Issues

See `BUG_AND_PERFORMANCE_ANALYSIS.md` and `BUG_FIX_PLAN.md` for:
- Critical bugs (DevelopmentalAssessment.save(), missing get_object_or_404)
- Performance optimizations (N+1 queries, database indexes)
- Security improvements (rate limiting, validation)

## Development Anti-Patterns

**Never:**
- Create models without inheriting from both base classes
- Add choices directly in models (use `ndas/custom_codes/choice.py`)
- Skip field validation
- Ignore indexing on searchable fields (`db_index=True`)
- Create templates without extending base templates
- Forget CSRF tokens in forms
- Change CSS framework or Bootstrap versions
- Upload files without validation
- Bypass security middleware
- Store sensitive config in code (use `.env`)
- Use incorrect Patient model field names (verify above)
- Delete entities without using delete_helpers for permission/business rule checks
- Use `.objects.get()` without try/except (use `get_object_or_404()` instead)
- Query related objects without `select_related()` or `prefetch_related()`
- Call heavy methods or calculations in templates (compute in views)

## OpenSpec Integration

This project uses OpenSpec for spec-driven development. Before implementing significant changes:
- Check existing specs: `openspec list --specs`
- Check active changes: `openspec list`
- Create proposals for new features, breaking changes, or architecture updates
- See `openspec/AGENTS.md` for complete workflow documentation

When extending functionality, follow established patterns of centralized configuration, comprehensive validation, and consistent user tracking across all data modifications.
