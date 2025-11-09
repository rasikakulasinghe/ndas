# NDAS - Neurodevelopmental Assessment System

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
- **Utilities**: Shared functions in `ndas/custom_codes/custom_methods.py`

### URL Structure
- `""` (root) → `patients/` app (primary interface)
- `users/` → Authentication, profiles, activity tracking
- `video/` → Video file management and processing
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
@login_required(login_url="user-login")
def my_view(request):
    var_objects = MyModel.objects.all()
    count = getCountZeroIfNone(var_objects)  # Custom utility
    context = {"var_objects": var_objects, "count": count}
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

### Middleware Stack (in order)
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

### Security Features
- CSRF protection on all forms
- Rate limiting with django-ratelimit
- Session timeout: 1 hour with browser close expiry
- Comprehensive file upload validation
- User activity tracking for audit trails

### File Upload Limits
- Video files: 2GB max (mp4, mov, avi, mkv, webm)
- General uploads: 100MB memory limit
- Profile pictures: 5MB max

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

### Medical Data Validation
- Birth weights: 300g - 8000g
- APGAR scores: 0-10 scale
- Gestational age (POG): 20-44 weeks
- Date validations for medical timelines

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

## OpenSpec Integration

This project uses OpenSpec for spec-driven development. Before implementing significant changes:
- Check existing specs: `openspec list --specs`
- Check active changes: `openspec list`
- Create proposals for new features, breaking changes, or architecture updates
- See `openspec/AGENTS.md` for complete workflow documentation

When extending functionality, follow established patterns of centralized configuration, comprehensive validation, and consistent user tracking across all data modifications.
