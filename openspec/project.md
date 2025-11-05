# Project Context

## Purpose
**Neurodevelopmental Assessment System (NDAS)** - A comprehensive Django-based medical information system for managing patient records, neurodevelopmental assessments, and video-based evaluations in pediatric healthcare settings.

**Primary Goals:**
- Centralized patient record management with comprehensive medical history tracking
- Video-based assessment storage and processing for developmental evaluations
- Multi-user access with role-based permissions and activity tracking
- Standardized assessment workflows (GPA, HINE, CDIC, Developmental)
- Secure file attachment management for medical documentation
- Professional medical-grade UI using AdminLTE framework

## Tech Stack

### Backend
- **Framework**: Django 4.2.16 LTS
- **Language**: Python 3.x
- **Database**: SQLite (development), PostgreSQL (production-ready)
- **Caching**: Redis with django-redis
- **Task Processing**: Celery for video processing
- **WSGI Server**: Gunicorn (production)

### Frontend
- **UI Framework**: AdminLTE 3.2 (Bootstrap 4.6 based)
- **CSS Framework**: Bootstrap 4.6.2
- **Icons**: Font Awesome 6.4
- **JavaScript Libraries**:
  - jQuery 3.6
  - HTMX 1.9 (dynamic interactions)
  - Select2 (enhanced form controls)
  - Video.js (video playback)
- **Rich Text**: CKEditor (django-richtextfield)
- **Static Files**: WhiteNoise for production serving

### Security & Middleware
- **Security Headers**: django-csp, django-permissions-policy
- **Rate Limiting**: django-ratelimit
- **Monitoring**: Sentry SDK
- **Session Security**: 1-hour timeout with activity tracking

### File Processing
- **Video Processing**: FFmpeg
- **Image Handling**: Pillow
- **PDF Generation**: ReportLab

### Development & Testing
- **Testing Framework**: Django test framework, Playwright (E2E)
- **Environment Management**: python-decouple
- **Virtual Environment**: venv (Windows-based development)

## Project Conventions

### Code Style

**Naming Conventions:**
- **Python**: snake_case for functions, variables, module names
- **Classes**: PascalCase for models, forms, views
- **Constants**: UPPER_SNAKE_CASE
- **Template files**: lowercase with hyphens (e.g., `delete-confirm.html`)
- **URL patterns**: kebab-case in paths

**File Organization:**
- Models: One file per app (`models.py`)
- Views: Organized by functionality in `views.py`
- Forms: Centralized in `forms.py` per app
- Templates: App-specific directories with consistent naming (`manager.html`, `add.html`, `edit.html`, `view.html`)
- Static files: Organized by type in `static/` (js/, css/, images/)
- Custom reusable code: `ndas/custom_codes/` directory

### Architecture Patterns

**Model Architecture (MANDATORY):**
All models MUST inherit from both base abstract classes:
```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

class MyModel(TimeStampedModel, UserTrackingMixin):
    # Automatically provides:
    # - created_at, updated_at (TimeStampedModel)
    # - added_by, last_edit_by (UserTrackingMixin)
    pass
```

**Key Architectural Decisions:**
- **Choice Standardization**: All choices defined in `ndas/custom_codes/choice.py` using Django TextChoices
- **Field Validation**: Custom validators centralized in `ndas/custom_codes/validators.py`
- **Utility Functions**: Reusable methods in `ndas/custom_codes/custom_methods.py`
- **User Tracking**: Automatic via `UserActivityMiddleware` in middleware stack
- **File Organization**: Date-based paths (`upload_to="path/%Y/%m/"`)
- **Searchable Fields**: Must use `db_index=True` for performance

**View Pattern:**
```python
@login_required(login_url="user-login")
def my_view(request):
    var_objects = MyModel.objects.all()
    count = getCountZeroIfNone(var_objects)  # Custom utility
    context = {"var_objects": var_objects, "count": count}
    return render(request, "myapp/template.html", context)
```

**Form Pattern:**
All forms follow consistent Bootstrap styling:
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

**Template Pattern:**
```django
{% extends 'src/base.html' %}
{% load static %}
{% block title %}Section - Action | Context{% endblock %}
{% block main_content %}
<div class="container-fluid">
  {% csrf_token %}
  <!-- Content here -->
</div>
{% endblock %}
```

**Security Middleware Stack Order:**
1. SecurityMiddleware
2. WhiteNoiseMiddleware
3. CSPMiddleware
4. SessionMiddleware
5. CommonMiddleware
6. CsrfViewMiddleware
7. AuthenticationMiddleware
8. UserActivityMiddleware (custom)
9. MessageMiddleware
10. XFrameOptionsMiddleware
11. UserAgentMiddleware

### Testing Strategy

**Framework:** Django's built-in test framework with Playwright for E2E testing

**Test Commands:**
- Run all tests: `python manage.py test`
- Run specific app: `python manage.py test patients`
- Run specific test class: `python manage.py test users.tests.TestClassName`
- E2E tests: `npx playwright test`

**Test Organization:**
- Unit tests: Within each Django app (`tests.py` or `tests/` directory)
- E2E tests: Playwright setup in `node_modules/`
- Test data: Django fixtures for consistent test scenarios

**Testing Requirements:**
- All new models must include basic CRUD tests
- Form validation tests for custom validators
- Security tests for access control and permissions
- File upload tests for validation and size limits

### Git Workflow

**Branching Strategy:**
- `main` - Production-ready code
- Feature branches: `feature/descriptive-name`
- Never work directly on main/master

**Commit Conventions:**
- Use descriptive commit messages (avoid "fix", "update", "changes")
- Follow pattern: "Implement X to enhance Y and fix Z"
- Always review changes with `git diff` before committing
- Commit frequently with incremental changes

**Pre-Commit Checklist:**
- Run migrations: `python manage.py migrate`
- Check for errors: `python manage.py check`
- Run tests: `python manage.py test`
- Verify static files: `python manage.py collectstatic --noinput`

## Domain Context

**Medical/Healthcare Domain:**
- **Patient Identifiers**: BHT (Bed Head Ticket), NNC (National Neonatal Code), PTC, PC, PIN numbers
- **Birth Data**: Gestational age, APGAR scores (0-10), delivery modes, birth weight (300g-8000g)
- **Assessment Types**:
  - **GPA**: General Paediatric Assessment
  - **HINE**: Hammersmith Infant Neurological Examination
  - **CDIC**: Child Development Inventory and Chart
  - **Developmental Assessments**: Comprehensive developmental tracking

**Medical Data Validation:**
- Birth weights: 300g - 8000g range validation
- APGAR scores: 0-10 scale with standardized interpretation
- Gestational age (POG): 20-44 weeks validation
- Date validations for medical timelines

**User Roles:**
- Medical professionals with varying access levels
- Activity tracking for audit compliance
- Session security (1-hour timeout)

**File Management:**
- Video assessments: Up to 2GB, formats: mp4, mov, avi, mkv, webm
- General uploads: 100MB memory limit
- Medical documentation attachments with access control

## Important Constraints

**Technical Constraints:**
- **Platform**: Windows-based development environment
- **Database**: SQLite for development (single-file, no concurrent writes)
- **File Size Limits**: Video 2GB max, general uploads 100MB
- **Session Timeout**: 1 hour for security compliance
- **Browser Support**: Modern browsers with ES6+ JavaScript support

**Security Constraints:**
- **HIPAA Awareness**: Medical data handling requires strict security
- **Access Control**: Login required for all patient data access
- **User Tracking**: All CUD operations must track user for audit
- **CSRF Protection**: Required on all forms
- **File Upload Security**: Comprehensive validation and type checking
- **Content Security Policy**: Strict CSP headers enforced

**Business Constraints:**
- **Medical-Grade UI**: Professional appearance required (AdminLTE)
- **Mobile Responsive**: Must work on tablets and mobile devices
- **Audit Trails**: Complete activity logging for compliance
- **Data Integrity**: Medical data must be validated and accurate

**Regulatory Constraints:**
- Medical record retention requirements
- Patient data privacy and confidentiality
- Secure authentication and authorization
- Activity logging for compliance audits

## External Dependencies

**Critical External Services:**
- **FFmpeg**: Required for video processing (must be installed on server)
- **Redis** (Production): Caching and session storage
- **PostgreSQL** (Production): Primary database
- **Celery Workers** (Production): Async task processing

**Optional Integrations:**
- **Sentry**: Error tracking and monitoring
- **Email Service**: For password reset functionality (configured via SMTP settings)

**CDN Resources:**
- AdminLTE assets (can be served locally or via CDN)
- Font Awesome icons
- Bootstrap CSS/JS
- jQuery, HTMX, Select2, Video.js libraries

**Development Dependencies:**
- Node.js and npm (for Playwright testing)
- Python virtual environment (venv)
- SQLite (bundled with Python)

**API Integrations:**
None currently - system is self-contained. Future integrations may include:
- Laboratory information systems
- PACS (Picture Archiving and Communication System)
- National health databases
