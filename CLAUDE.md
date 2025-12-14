# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

**Technology Stack:**
- Django 4.2.16 LTS + Python 3.x
- Database: SQLite (dev) / PostgreSQL (prod)
- Frontend: AdminLTE 3.2 + Bootstrap 4.6 + Font Awesome 6.4
- JavaScript: jQuery 3.6, HTMX 1.9, Select2, Video.js
- Static Files: WhiteNoise with compression
- Video Processing: FFmpeg
- Session/Cache: Redis (production)
- Monitoring: Sentry SDK

**Django Apps:**
- `patients/` - Patient management, assessments, medical records
- `video/` - Video file handling, processing, metadata
- `users/` - Custom user authentication, permissions, subscriptions, activity tracking
- `reports/` - Report generation and management
- `ndas/` - Project settings, URLs, core configuration

## Development Commands

### Environment Setup
```bash
# Activate virtual environment (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
# Create .env file in project root with required variables
```

### Django Management
```bash
# Run development server
python manage.py runserver

# Database operations
python manage.py makemigrations [app_name]
python manage.py migrate

# User management
python manage.py createsuperuser

# Django shell
python manage.py shell

# Testing
python manage.py test                          # All tests
python manage.py test patients                 # App tests
python manage.py test users.tests.TestClassName  # Specific test class
```

### OpenSpec Commands
```bash
# List active changes and specs
openspec list
openspec list --specs

# View changes or specs
openspec show [item]

# Validate changes
openspec validate [change-id] --strict

# Archive deployed changes
openspec archive <change-id> --yes
```

## Architecture Patterns

### Model Development (MANDATORY)

All models MUST inherit from both base abstract classes:

```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

class MyModel(TimeStampedModel, UserTrackingMixin):
    # Automatically provides:
    # - created_at, updated_at (TimeStampedModel)
    # - added_by, last_edit_by (UserTrackingMixin - auto-populated via middleware)

    # Your fields here
    pass
```

**Model Development Rules:**
1. Inherit from `TimeStampedModel, UserTrackingMixin`
2. Add choices to `ndas/custom_codes/choice.py` (use Django TextChoices)
3. Use validators from `ndas/custom_codes/validators.py`
4. Add `db_index=True` for searchable/filterable fields
5. Include comprehensive `help_text` for medical fields
6. Use date-based upload paths: `upload_to="path/%Y/%m/"`

**Custom Code Organization:**
- `ndas/custom_codes/Custom_abstract_class.py` - Base models (TimeStampedModel, UserTrackingMixin)
- `ndas/custom_codes/choice.py` - Centralized TextChoices for medical terminology
- `ndas/custom_codes/validators.py` - Field validators (birth weight, APGAR, file uploads)
- `ndas/custom_codes/custom_methods.py` - Utility functions (e.g., `getCountZeroIfNone()`)
- `ndas/custom_codes/ndas_enums.py` - Enumerations (e.g., PtStatus)
- `ndas/custom_codes/delete_helpers.py` - Safe deletion utilities

### View Development

Standard view pattern with login requirement and custom utilities:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from ndas.custom_codes.custom_methods import getCountZeroIfNone

@login_required(login_url="user-login")
def my_view(request):
    var_objects = MyModel.objects.all()
    count = getCountZeroIfNone(var_objects)
    context = {"var_objects": var_objects, "count": count}
    return render(request, "myapp/template.html", context)
```

### Form Development

Follow Bootstrap 4.6 styling pattern:

```python
from django import forms

class MyForm(forms.ModelForm):
    field = forms.ChoiceField(
        choices=MY_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"})
    )

    class Meta:
        model = MyModel
        fields = ["field1", "field2"]
        widgets = {
            "text_field": forms.TextInput(attrs={"class": "form-control"}),
            "textarea_field": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "date_field": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }
```

### Template Development (MANDATORY)

```django
{% extends 'src/base.html' %}  {# For authenticated pages #}
{% load static %}
{% block title %}Section - Action | Context{% endblock %}
{% block main_content %}
<div class="container-fluid">
  {% csrf_token %}
  <!-- Content here -->
</div>
{% endblock %}
```

**Template Rules:**
1. Extend `'src/base.html'` for authenticated pages, `'src/basic_plane.html'` for public pages
2. Include `{% csrf_token %}` in all container-fluid divs
3. Follow AdminLTE structure: `info-box`, `card`, `table table-hover table-striped`
4. **DO NOT change CSS framework** - AdminLTE 3.2 + Bootstrap 4.6 + Font Awesome 6.4
5. Use Bootstrap 4.6 modal structure with proper ARIA attributes
6. Initialize JavaScript components: Bootstrap tooltips, Select2, HTMX

**Template Naming Conventions:**
- `manager.html` - List/management views
- `add.html` - Creation forms
- `edit.html` - Update forms
- `view.html` - Detail views

**Template Locations:**
- `templates/src/base.html` - Main authenticated layout
- `templates/src/basic_plane.html` - Public/auth pages layout
- `templates/src/` - Reusable partials (navbar, sidebar, messages)
- App-specific: `templates/{app_name}/` directories

### Security Architecture

**Middleware Stack (CRITICAL ORDER):**
1. `SecurityMiddleware`
2. `WhiteNoiseMiddleware`
3. `CSPMiddleware` (Content Security Policy)
4. `SessionMiddleware`
5. `CommonMiddleware`
6. `CsrfViewMiddleware`
7. `AuthenticationMiddleware`
8. `UserActivityMiddleware` (custom - auto-populates added_by/last_edit_by)
9. `MessageMiddleware`
10. `XFrameOptionsMiddleware`
11. `UserAgentMiddleware`
12. `SubscriptionCheckMiddleware` (custom - subscription validation)

**Security Features:**
- Rate limiting with django-ratelimit
- HSTS and comprehensive security headers
- Session timeout: 1 hour with browser-close expiry
- CSRF and XSS protection
- File upload validation (type, size, content)
- Medical data privacy (HIPAA awareness)

**File Upload Limits:**
- Video files: 2GB max (mp4, mov, avi, mkv, webm)
- General uploads: 100MB memory limit
- Profile pictures: 5MB max

### URL Routing

```
Root URLconf (ndas/urls.py):
├── admin/ → Django admin interface
├── users/ → Authentication, profiles, admin functions, subscriptions
├── reports/ → Report generation and management
├── video/ → Video file management
├── djrichtextfield/ → Rich text editor integration
└── "" → patients/ app (primary interface)
```

### Database Patterns

**Development:** SQLite (`db.sqlite3`)
**Production:** PostgreSQL with connection pooling

**Migration Workflow:**
1. Create model inheriting from `TimeStampedModel, UserTrackingMixin`
2. Add choices to `ndas/custom_codes/choice.py`
3. Reference validators from `ndas/custom_codes/validators.py`
4. Run `python manage.py makemigrations [app_name]`
5. Review generated migration
6. Apply with `python manage.py migrate`

**Data Flow:**
- **Patient → Video → Assessment** - Core workflow
- **User tracking** - All CUD operations auto-track user via UserActivityMiddleware
- **Status management** - Use `ndas_enums.PtStatus` for patient status filtering
- **Search optimization** - Indexed fields, use `getPatientList()` for filtered queries

## Medical Domain Context

**Patient Identifiers:**
- BHT (Bed Head Ticket)
- NNC (National Neonatal Code)
- PTC, PC, PIN numbers

**Birth Data Validation:**
- Birth weight: 300g - 8000g
- APGAR scores: 0-10 scale
- Gestational age (POG): 20-44 weeks
- Delivery modes: Normal, C-section, Assisted

**Assessment Types:**
- **GPA**: General Paediatric Assessment
- **HINE**: Hammersmith Infant Neurological Examination
- **CDIC**: Child Development Inventory and Chart
- **Developmental Assessments**: Comprehensive developmental tracking

**Key Models:**
- `Patient` - Core patient data with medical identifiers, birth data, APGAR scores
- `Video` - Video files linked to patients with processing status
- `CustomUser` - Extended Django user with profile, activity tracking, subscriptions
- `GMAssessment` - General Movement assessments
- `CDICRecord`, `HINEAssessment`, `DevelopmentalAssessment` - Specialized assessments
- `Attachment` - File attachments with access control
- `Bookmark` - User bookmark system

## Important Constraints

**Technical:**
- Windows-based development environment
- Session timeout: 1 hour for security compliance
- Browser support: Modern browsers with ES6+ JavaScript
- FFmpeg required for video processing

**Security:**
- Medical data requires strict security (HIPAA awareness)
- Login required for all patient data access
- User tracking on all CUD operations for audit compliance
- CSRF protection mandatory on all forms
- Content Security Policy enforced

**Business:**
- Professional medical-grade UI required
- Responsive design for tablets/mobile (medical settings)
- Complete audit trails for compliance
- Medical data validation accuracy critical

## Development Anti-Patterns

**Never:**
- Create models without inheriting from `TimeStampedModel, UserTrackingMixin`
- Add choices directly in models (use `ndas/custom_codes/choice.py`)
- Skip field validation or indexing on searchable fields
- Create templates without extending base templates
- Forget CSRF tokens in forms
- Change CSS framework or Bootstrap versions
- Upload files without validation
- Bypass or reorder security middleware
- Store sensitive config in code (use `.env`)

## Static Files Architecture

**Custom Files:**
- JavaScript: `static/js/app-utils.js`, `video-manager.js`, `patient-timeline.js`
- CSS: `static/css/patient-timeline.css`

**Static File Serving:**
- Development: Django's `django.contrib.staticfiles`
- Production: WhiteNoise with compression and caching
- Location: `STATIC_ROOT = staticfiles/`, `STATICFILES_DIRS = [static/]`

## Testing Strategy

**Framework:** Django's built-in test framework + Playwright for E2E

**Test Commands:**
```bash
python manage.py test                           # All tests
python manage.py test patients                  # App-specific
python manage.py test users.tests.TestClassName # Specific class
```

**Testing Requirements:**
- Basic CRUD tests for all new models
- Form validation tests for custom validators
- Security/access control tests
- File upload validation tests

## External Dependencies

**Required for Production:**
- FFmpeg - Video processing
- Redis - Caching and session storage
- PostgreSQL - Primary database
- Celery Workers - Async task processing

**Optional:**
- Sentry - Error tracking and monitoring
- Email Service - Password reset (SMTP configuration)

## Quick Reference

**Base Class Import:**
```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
```

**Custom Utilities:**
```python
from ndas.custom_codes.custom_methods import getCountZeroIfNone
from ndas.custom_codes.choice import MY_CHOICES
from ndas.custom_codes.validators import validate_video_file
from ndas.custom_codes.ndas_enums import PtStatus
```

**Common Template Paths:**
- Authenticated: `templates/src/base.html`
- Public: `templates/src/basic_plane.html`
- App templates: `templates/{app_name}/`

**Middleware Auto-Tracking:**
- `added_by` - Set automatically on creation via UserActivityMiddleware
- `last_edit_by` - Updated automatically on save via UserActivityMiddleware
- No manual intervention needed in views or forms
