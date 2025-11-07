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

## OpenSpec Workflow Integration

This project uses OpenSpec for spec-driven development. Before implementing significant changes:

1. **Check existing specs**: `openspec list --specs` and `openspec list` to see active changes
2. **Create proposals** for:
   - New features or capabilities
   - Breaking changes (API, database schema)
   - Architecture or security pattern changes
   - Performance optimizations that change behavior
3. **Skip proposals** for:
   - Bug fixes restoring intended behavior
   - Typos, formatting, comments
   - Non-breaking dependency updates
   - Configuration changes

**Key Commands:**
- `openspec list` - View active changes
- `openspec show [item]` - Display change or spec details
- `openspec validate [change] --strict` - Validate before implementation
- `openspec archive <change-id> --yes` - Archive after deployment

See `openspec/AGENTS.md` for complete workflow documentation.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Django Management
- **Run development server**: `python manage.py runserver`
- **Database migrations**: `python manage.py makemigrations && python manage.py migrate`
- **Create superuser**: `python manage.py createsuperuser`
- **Django shell**: `python manage.py shell`
- **Collect static files**: `python manage.py collectstatic`
- **Run tests**: `python manage.py test`
- **Run specific app tests**: `python manage.py test patients` or `python manage.py test users.tests.TestClassName`
- **Make migrations for specific app**: `python manage.py makemigrations patients`
- **Reset database** (development only): `python manage.py flush`

### Environment Setup
- Virtual environment is in `venv/` directory
- Activate with: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Unix)
- Install dependencies: `pip install -r requirements.txt`
- Environment variables: Configure `.env` file in project root for development settings

## Architecture Overview

### Core Structure
This is a Django-based **Neurodevelopmental Assessment System (NDAS)** that manages patient records, video assessments, and user authentication.

**Main Django Apps:**
- `patients/` - Patient management, assessments, and medical records
- `video/` - Video file handling, processing, and metadata management  
- `users/` - Custom user authentication, permissions, and activity tracking
- `ndas/` - Project settings, URLs, and core configuration

### Key Models and Relationships
- **Patient**: Core patient model with comprehensive medical data:
  - Multiple unique identifiers (BHT, NNC, PTC, PC, PIN numbers)
  - Birth information (gestational age, APGAR scores, delivery mode)
  - Proper indexing on searchable fields (baby_name, mother_name, gender)
- **Video**: Video files linked to patients with processing status and metadata
- **CustomUser**: Extended Django user model with profile and activity tracking
- **GMAssessment**: Patient assessment records with rich text fields
- **Attachment**: File attachments for patients with access control
- **Specialized Assessments**: CDICRecord, HINEAssessment, DevelopmentalAssessment
- **Bookmark**: User bookmark system for patient records

### Custom Code Organization
- `ndas/custom_codes/` contains reusable components:
  - `Custom_abstract_class.py` - Base models with timestamps and user tracking:
    - `TimeStampedModel`: Provides created_at/updated_at fields
    - `UserTrackingMixin`: Tracks who added/modified records
  - `choice.py` - Predefined choices using Django's TextChoices for consistency
  - `validators.py` - Custom field validators for medical data and file uploads
  - `custom_methods.py` - Utility functions like `getCountZeroIfNone()`

### Model Architecture Patterns (MANDATORY)
- **All models MUST inherit from both abstract base classes**:
  ```python
  class MyModel(TimeStampedModel, UserTrackingMixin):
      # Your fields here
      pass
  ```
- **Medical data validation** through custom validators (birth weight, APGAR scores)
- **Choice standardization** using centralized TextChoices for medical terminology
- **File upload validation** with size limits and type checking
- **Searchable fields** must have `db_index=True` for performance
- **Rich medical data** includes comprehensive help_text for medical fields

### Frontend Architecture
- **AdminLTE-based UI framework** with professional medical interface design
- Templates in `templates/` organized by app with reusable partials:
  - `src/base.html` - Main layout for logged-in users
  - `src/basic_plane.html` - Layout for authentication pages
  - App-specific templates with consistent design patterns
- Static files in `static/` with enhanced functionality:
  - Custom JavaScript utilities (`app-utils.js`, `video-manager.js`)
  - HTMX integration for dynamic interactions
  - Select2 for enhanced form controls
  - Video.js for video playback
- Uses WhiteNoise for static file serving in production
- CKEditor integration for rich text editing

### Patient Timeline Feature
- **Unified Timeline View**: Chronological visualization of all patient events in a single card
- **Event Sources**: Aggregates birth event, assessments (GMA, HINE, Developmental, CDIC, GPA), videos, and attachments
- **Implementation Components**:
  - `patients/timeline_utils.py` - Backend event aggregation and formatting utilities
    - `get_patient_timeline_events(patient)` - Main function to aggregate all patient events
    - `format_event_datetime(dt)` - Format datetimes for display
    - `get_event_age_at_time(birth_date, event_date)` - Calculate patient age at event
  - `templates/patients/partials/patient_timeline.html` - Timeline card template
  - `static/css/patient-timeline.css` - Responsive timeline styles
  - `static/js/patient-timeline.js` - Interactive filtering and preview functionality
- **Features**:
  - Event type filtering (All, Assessments, Media)
  - Inline preview modals for quick event details
  - Links to detailed views (open in new window)
  - Responsive design (desktop, tablet, mobile)
  - Keyboard navigation and accessibility support
  - Age-at-event calculation for developmental context
- **Usage**: Automatically displayed on patient detail view after Media Card
- **Performance**: Uses select_related/prefetch_related for optimized queries


### Security Architecture
- **Comprehensive security middleware stack**:
  - Content Security Policy (CSP) and Permissions Policy
  - Rate limiting with django-ratelimit
  - HSTS and security headers (X-Frame-Options, X-Content-Type-Nosniff)
- **Session and authentication security**:
  - Session timeout set to 1 hour with browser close expiry  
  - User activity tracking middleware
  - CSRF and XSS protection
- **File upload security**:
  - Comprehensive validation for medical data and uploads
  - Size limits: Video files 2GB max, general uploads 100MB memory limit
  - File type validation and access control

### Database and Media
- **Development**: SQLite database (`db.sqlite3`) 
- **Production ready**: PostgreSQL support with connection pooling
- **Caching**: Redis integration for performance
- Media files organized in `media/` by type with date-based structure:
  - Video files: `media/videos/%Y/%m/` 
  - Profile pictures, attachments organized by type

### Production Features
- **Environment management**: `.env` file with python-decouple for security
- **Static file serving**: WhiteNoise configured for production
- **Caching**: Redis support with django-redis
- **Task processing**: Celery integration for video processing
- **Monitoring**: Sentry SDK for error tracking and health checks
- **Performance**: Database connection pooling and query optimization

## Testing
- Test files exist but are minimal: `video/tests.py`, `users/tests.py`
- Use standard Django test framework: `python manage.py test`

## URL Structure and Routing
- **Root (`""`)**: patients app - Primary interface for patient management
- **`"users/"`**: User authentication, password reset, profile management  
- **`"video/"`**: Video file management and processing
- **`"admin/"`**: Django admin interface with custom branding

## File Upload System
- **Video files**: 2GB maximum, formats: mp4, mov, avi, mkv, webm
- **General uploads**: 100MB memory limit
- **Validation**: Through custom validators in `ndas/custom_codes/validators.py`
- **Storage**: Organized by date and type for efficient management
- **Processing**: FFmpeg integration for video processing tasks

## Development Patterns (MANDATORY)

### Form Development Pattern
All forms MUST follow consistent Bootstrap styling from `patients/forms.py`:
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

### View Development Pattern
All views follow this structure:
```python
@login_required(login_url="user-login")
def my_view(request):
    # Standard pattern for data loading
    var_objects = MyModel.objects.all()
    count = getCountZeroIfNone(var_objects)  # Use custom method

    # Template context with consistent naming
    context = {"var_objects": var_objects, "count": count}
    return render(request, "myapp/template.html", context)
```

### Template Structure (MANDATORY)
```django
{% extends 'src/base.html' %}  # Always for authenticated pages
{% load static %}
{% block title %}Section - Action | Context{% endblock %}
{% block main_content %}
<div class="container-fluid">
  {% csrf_token %}
  <!-- Content here -->
</div>
{% endblock %}
```

### UI Component Patterns (AdminLTE)
Follow these established patterns for consistency:
- **Info Boxes**: Use AdminLTE's `info-box` class with consistent icons
- **Cards**: Bootstrap `card` class with `card-header`, `card-body`
- **Tables**: `table table-hover table-striped` wrapped in `.table-responsive`
- **Buttons**: Bootstrap button classes with Font Awesome icons
- **Color Scheme**: Primary (blue), success (green), warning (yellow), danger (red)
- **JavaScript Stack**: jQuery 3.6, Bootstrap 4 JS, HTMX 1.9, Select2, Video.js

## Critical Development Rules

### When Adding New Models
1. Inherit from `TimeStampedModel, UserTrackingMixin`
2. Add choices to `ndas/custom_codes/choice.py`
3. Create validators in `ndas/custom_codes/validators.py`
4. Use `db_index=True` for searchable fields
5. Include comprehensive help_text for medical fields

### File Upload Handling
Always use custom validators from `ndas/custom_codes/validators.py`:
```python
file_field = models.FileField(
    upload_to="path/%Y/%m/",
    validators=[validate_video_file],  # Or appropriate validator
)
```

### UI Development Rules
1. **Always extend** `'src/base.html'` for authenticated pages
2. **Include CSRF token** in all container-fluid divs: `{% csrf_token %}`
3. **Use consistent form classes** from `patients/forms.py` patterns
4. **Follow AdminLTE structure**: info-box, card layouts, table patterns
5. **Maintain responsive design** with mobile-first CSS
6. **DO NOT change CSS framework**: AdminLTE 3.2 + Bootstrap 4.6 + Font Awesome 6.4
7. **Initialize components properly**: Bootstrap tooltips, Select2, HTMX in templates
8. **Use custom utilities**: Reference `static/js/app-utils.js` for common functions
9. **Bootstrap Modals**: Use standard Bootstrap 4.6 modal structure with proper ARIA attributes
   - Trigger: `data-toggle="modal"` and `data-target="#modalId"`
   - Structure: `.modal > .modal-dialog > .modal-content > .modal-header/.modal-body/.modal-footer`
   - Accessibility: Include `role="dialog"`, `aria-labelledby`, `aria-hidden` attributes
   - JavaScript: Handle focus management and external link security (see `static/js/login.js` for modal example)

## Data Flow Patterns
- **Patient → Video → Assessment**: Core workflow where patients have videos, videos have assessments
- **User tracking**: All CUD operations automatically track user via middleware
- **Status management**: Use `ndas_enums.PtStatus` for patient status filtering
- **Search optimization**: Key fields indexed, use `getPatientList()` for filtered queries

## Key Dependencies and Integration
- **Django 4.2.16**: Latest LTS with security updates
- **Frontend**: AdminLTE, Bootstrap 4, Select2, Video.js, HTMX
- **Security**: django-csp, django-ratelimit, django-permissions-policy
- **File Processing**: FFmpeg, Pillow for image handling
- **PDF Generation**: ReportLab for medical reports
- **Production**: PostgreSQL, Redis, Celery, Gunicorn, WhiteNoise

## Environment and Tooling

### Development Environment
- **Platform**: Windows (uses `venv\Scripts\activate` for virtualenv)
- **Python**: Django 4.2.16 LTS with comprehensive security configuration
- **Database**: SQLite for development (`db.sqlite3`), PostgreSQL production-ready
- **Frontend Testing**: Playwright with Node.js setup in `node_modules/`

### Additional Development Commands
- **Activate virtual environment**: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Unix)
- **Install frontend deps**: `npm install` (for Playwright testing)
- **Run Playwright tests**: `npx playwright test`
- **Database shell**: `python manage.py dbshell`
- **Check migrations**: `python manage.py showmigrations`
- **Load fixtures**: `python manage.py loaddata [fixture_file]`

## Advanced Architecture Details

### Security Middleware Stack (Complete Order)
1. `SecurityMiddleware` - Basic Django security
2. `WhiteNoiseMiddleware` - Static file serving
3. `CSPMiddleware` - Content Security Policy enforcement
4. `SessionMiddleware` - Session handling
5. `CommonMiddleware` - Common processing
6. `CsrfViewMiddleware` - CSRF protection
7. `AuthenticationMiddleware` - User authentication
8. `UserActivityMiddleware` - Custom activity tracking (users/middleware.py)
9. `MessageMiddleware` - Django messages framework
10. `XFrameOptionsMiddleware` - X-Frame-Options header
11. `UserAgentMiddleware` - User agent parsing

### Model Inheritance Architecture (Critical Pattern)
**All models MUST inherit from BOTH base classes in this exact order**:
```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

class MyModel(TimeStampedModel, UserTrackingMixin):
    # Model fields here
    class Meta:
        # Meta configuration
```

The `UserActivityMiddleware` automatically populates `added_by` and `last_edit_by` fields during save operations.

### Validation System Architecture
- **Choice Standardization**: All choices defined in `ndas/custom_codes/choice.py` using Django TextChoices
- **Field Validation**: Custom validators in `ndas/custom_codes/validators.py` for medical data integrity
- **File Upload Security**: Comprehensive validation with size limits, type checking, and security scanning
- **Medical Data Validation**: Specialized validators for birth weights (300g-8000g), APGAR scores (0-10), POG weeks (20-44)

### Template Architecture and Naming Conventions
- **Base Templates**:
  - `src/base.html` - Main layout for authenticated users (AdminLTE structure)
  - `src/basic_plane.html` - Layout for authentication pages
- **Partial Templates**: Organized in `templates/src/` for reusable components:
  - `main_sidebar_menu.html` - Navigation structure
  - `messages.html` - Django messages display
  - `form_error.html` - Consistent error handling
- **App-Specific Templates**: Organized by Django app with consistent naming:
  - `manager.html` - List/management views
  - `add.html` - Creation forms
  - `edit.html` - Update forms
  - `view.html` - Detail views
  - `delete-confirm.html` - Deletion confirmation

### URL Routing Structure
```
Root URLconf (ndas/urls.py):
├── admin/ → Django admin interface
├── users/ → Authentication, profiles, admin functions
├── video/ → Video management and processing
├── djrichtextfield/ → Rich text editor integration
└── "" (empty) → patients/ app (primary interface)
```

### Error Handling and Production Features
- **Custom Error Pages**: 404 and 500 handlers defined in `ndas.views`
- **Logging Configuration**: Comprehensive logging to `logs/` directory with rotation
  - `django.log` - General application logs
  - `security.log` - Security-related events
- **Environment Configuration**: Uses `python-decouple` for secure environment variable management
- **Production Security**: HSTS, CSP, Permissions Policy, session security configured

### File Organization Standards
- **Media Files**: Organized by type and date (`media/videos/%Y/%m/`, etc.)
- **Static Files**: WhiteNoise serving with compression enabled in production
- **Custom JavaScript**: Organized in `static/js/` with utilities in `app-utils.js`
- **CSS Framework**: AdminLTE 3.2 + Bootstrap 4.6 with custom overrides

## Development Anti-Patterns to Avoid

### Model Development
- **Never** create models without inheriting from both base classes
- **Never** add choices directly in models - use `ndas/custom_codes/choice.py`
- **Never** skip field validation - use or create appropriate validators
- **Never** ignore indexing on searchable fields (`db_index=True`)

### Template Development
- **Never** create templates without extending `src/base.html` or `src/basic_plane.html`
- **Never** forget CSRF tokens in forms within `container-fluid` divs
- **Never** hardcode Bootstrap classes - follow existing form patterns
- **Never** create inconsistent navigation - use established sidebar structure

### Security Considerations
- **Never** bypass the security middleware stack order
- **Never** disable CSRF protection or other security features
- **Never** store sensitive configuration in code - use `.env` file
- **Never** upload files without validation through custom validators

## Critical Development Workflows

### Adding New Model Workflow
1. Create model inheriting from `TimeStampedModel, UserTrackingMixin`
2. Add any new choices to `ndas/custom_codes/choice.py`
3. Create/reference validators in `ndas/custom_codes/validators.py`
4. Add `db_index=True` for searchable fields
5. Include comprehensive `help_text` for medical fields
6. Run `python manage.py makemigrations [app_name]`
7. Review generated migration before applying
8. Apply with `python manage.py migrate`

### Template Creation Workflow
1. Determine if authenticated (extend `src/base.html`) or public (extend `src/basic_plane.html`)
2. Follow established naming conventions (`manager.html`, `add.html`, etc.)
3. Include proper block structure (`title`, `main_content`)
4. Add CSRF token in `container-fluid` div
5. Use consistent Bootstrap form classes from existing examples
6. Test responsive behavior on mobile devices

### File Upload Implementation Workflow
1. Use appropriate validator from `ndas/custom_codes/validators.py`
2. Set proper `upload_to` path with date organization (`"%Y/%m/"`)
3. Configure size limits appropriate to file type
4. Test upload with various file types and sizes
5. Verify security restrictions are enforced

This architecture ensures consistency, security, and maintainability across the entire NDAS system while following Django best practices and medical data handling requirements.