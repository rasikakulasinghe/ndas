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

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Django Management
- **Run server**: `python manage.py runserver`
- **Database migrations**: `python manage.py makemigrations && python manage.py migrate`
- **Create superuser**: `python manage.py createsuperuser`
- **Django shell**: `python manage.py shell`
- **Run tests**: `python manage.py test`
- **Run app tests**: `python manage.py test patients` or `python manage.py test users.tests.TestClassName`

### Environment
- **Activate venv**: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Unix)
- **Install deps**: `pip install -r requirements.txt`
- **Environment variables**: Configure `.env` file in project root

## Architecture Overview

### Core Structure
Django-based **Neurodevelopmental Assessment System (NDAS)** managing patient records, video assessments, and user authentication.

**Django Apps:**
- `patients/` - Patient management, assessments, medical records
- `video/` - Video file handling, processing, metadata
- `users/` - Custom user authentication, permissions, activity tracking
- `ndas/` - Project settings, URLs, core configuration

### Key Models
- **Patient**: Core model with medical identifiers (BHT, NNC, PTC, PC, PIN), birth data, APGAR scores
- **Video**: Video files linked to patients with processing status
- **CustomUser**: Extended Django user with profile and activity tracking
- **GMAssessment**: Patient assessment records
- **Attachment**: File attachments with access control
- **Specialized Assessments**: CDICRecord, HINEAssessment, DevelopmentalAssessment
- **Bookmark**: User bookmark system

### Custom Code Organization
`ndas/custom_codes/` contains reusable components:
- `Custom_abstract_class.py` - Base models:
  - `TimeStampedModel`: Auto created_at/updated_at timestamps
  - `UserTrackingMixin`: Auto added_by/last_edit_by user tracking
- `choice.py` - Centralized TextChoices for medical terminology
- `validators.py` - Field validators (birth weight, APGAR, file uploads)
- `custom_methods.py` - Utility functions like `getCountZeroIfNone()`

## Critical Development Patterns

### Model Development (MANDATORY)
All models MUST inherit from both base classes:
```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

class MyModel(TimeStampedModel, UserTrackingMixin):
    # Your fields here
    pass
```

**Rules:**
1. Inherit from `TimeStampedModel, UserTrackingMixin`
2. Add choices to `ndas/custom_codes/choice.py`
3. Use validators from `ndas/custom_codes/validators.py`
4. Add `db_index=True` for searchable fields
5. Include comprehensive `help_text` for medical fields

### Form Development
Follow Bootstrap styling pattern from `patients/forms.py`:
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

### View Development
Standard view pattern:
```python
@login_required(login_url="user-login")
def my_view(request):
    var_objects = MyModel.objects.all()
    count = getCountZeroIfNone(var_objects)  # Use custom method
    context = {"var_objects": var_objects, "count": count}
    return render(request, "myapp/template.html", context)
```

### Template Development (MANDATORY)
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

**Template Naming Conventions:**
- `manager.html` - List/management views
- `add.html` - Creation forms
- `edit.html` - Update forms
- `view.html` - Detail views

### UI Development Rules
1. Extend `'src/base.html'` for authenticated pages or `'src/basic_plane.html'` for public pages
2. Include `{% csrf_token %}` in all container-fluid divs
3. Follow AdminLTE structure: `info-box`, `card`, `table table-hover table-striped`
4. **DO NOT change CSS framework**: AdminLTE 3.2 + Bootstrap 4.6 + Font Awesome 6.4
5. Use Bootstrap 4.6 modal structure with proper ARIA attributes
6. Initialize components: Bootstrap tooltips, Select2, HTMX

### File Upload Handling
Always use custom validators:
```python
file_field = models.FileField(
    upload_to="path/%Y/%m/",
    validators=[validate_video_file],  # Or appropriate validator
)
```

**File Upload Limits:**
- Video files: 2GB max (mp4, mov, avi, mkv, webm)
- General uploads: 100MB memory limit
- Profile pictures: 5MB max

## Frontend Architecture

**Technology Stack:**
- AdminLTE 3.2 + Bootstrap 4.6 + Font Awesome 6.4
- jQuery 3.6, HTMX 1.9, Select2, Video.js
- CKEditor for rich text editing

**Templates:**
- `src/base.html` - Main layout for authenticated users
- `src/basic_plane.html` - Layout for authentication pages
- `templates/src/` - Reusable partials (navbar, sidebar, messages)
- App-specific templates organized by Django app

**Static Files:**
- Custom JS: `static/js/app-utils.js`, `video-manager.js`, `patient-timeline.js`
- Custom CSS: `static/css/patient-timeline.css`
- WhiteNoise for production static file serving

## Patient Timeline Feature

**Components:**
- `patients/timeline_utils.py` - Event aggregation utilities
  - `get_patient_timeline_events(patient)` - Aggregates all patient events
  - `format_event_datetime(dt)` - Formats datetimes
  - `get_event_age_at_time(birth_date, event_date)` - Calculates patient age
- `templates/patients/partials/patient_timeline.html` - Timeline card template
- `static/css/patient-timeline.css` - Responsive styles
- `static/js/patient-timeline.js` - Filtering and preview functionality

**Features:**
- Event type filtering (All, Assessments, Media)
- Inline preview modals
- Links to detailed views
- Responsive design
- Age-at-event calculation

## Security Architecture

**Middleware Stack (in order):**
1. SecurityMiddleware
2. WhiteNoiseMiddleware
3. CSPMiddleware (Content Security Policy)
4. SessionMiddleware
5. CommonMiddleware
6. CsrfViewMiddleware
7. AuthenticationMiddleware
8. UserActivityMiddleware (custom - auto-populates added_by/last_edit_by)
9. MessageMiddleware
10. XFrameOptionsMiddleware
11. UserAgentMiddleware

**Security Features:**
- Rate limiting with django-ratelimit
- HSTS and security headers
- Session timeout: 1 hour with browser close expiry
- CSRF and XSS protection
- Comprehensive file upload validation

## Database and Production

**Development:** SQLite (`db.sqlite3`)
**Production Ready:** PostgreSQL with connection pooling

**Caching:** Redis with django-redis
**Task Processing:** Celery for video processing
**Monitoring:** Sentry SDK for error tracking
**Static Files:** WhiteNoise with compression

## URL Routing
```
Root URLconf (ndas/urls.py):
├── admin/ → Django admin
├── users/ → Authentication, profiles, admin functions
├── video/ → Video management
├── djrichtextfield/ → Rich text editor
└── "" → patients/ app (primary interface)
```

## Data Flow Patterns
- **Patient → Video → Assessment**: Core workflow
- **User tracking**: All CUD operations auto-track user via middleware
- **Status management**: Use `ndas_enums.PtStatus` for filtering
- **Search optimization**: Indexed fields, use `getPatientList()` for filtered queries

## Key Dependencies
- Django 4.2.16 LTS
- Frontend: AdminLTE, Bootstrap 4, Select2, Video.js, HTMX
- Security: django-csp, django-ratelimit, django-permissions-policy
- File Processing: FFmpeg, Pillow
- PDF: ReportLab
- Production: PostgreSQL, Redis, Celery, Gunicorn, WhiteNoise

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

## Migration Workflow

When adding new models:
1. Create model inheriting from `TimeStampedModel, UserTrackingMixin`
2. Add choices to `ndas/custom_codes/choice.py`
3. Reference validators from `ndas/custom_codes/validators.py`
4. Run `python manage.py makemigrations [app_name]`
5. Review generated migration
6. Apply with `python manage.py migrate`
