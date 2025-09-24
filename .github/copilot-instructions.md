# NDAS - Neurodevelopmental Assessment System

A Django-based medical records system for managing patient assessments, video recordings, and comprehensive medical data with security-focused architecture.

## Core Architecture Patterns

### Model Design Philosophy
All models inherit from **two abstract base classes** in `ndas/custom_codes/Custom_abstract_class.py`:
- `TimeStampedModel`: Auto-managed created_at/updated_at fields
- `UserTrackingMixin`: Tracks who created/modified records via added_by/last_edit_by

**Example pattern:**
```python
class MyModel(TimeStampedModel, UserTrackingMixin):
    # Your fields here
    pass
```

### Centralized Configuration
- **Choices**: All dropdown options in `ndas/custom_codes/choice.py` using Django's TextChoices
- **Validators**: Medical data validation in `ndas/custom_codes/validators.py`
- **Utilities**: Shared functions in `ndas/custom_codes/custom_methods.py`

### URL Structure & App Boundaries
- Root path (`""`) → `patients/` app (primary interface)
- `users/` → Authentication, profiles, activity tracking
- `video/` → Video file management and processing
- `admin/` → Django admin with custom branding

## Key Models & Relationships

### Patient Model (`patients/models.py`)
Core entity with **multiple unique identifiers**: BHT, NNC, PTC, PC, PIN numbers. All searchable fields have `db_index=True`. Rich medical data including birth information, APGAR scores, gestational age.

### Video Model (`video/models.py`) 
Linked to patients with comprehensive metadata, processing status tracking, and FFmpeg integration for video processing.

### CustomUser Model (`users/models.py`)
Extended AbstractUser with professional positions, contact info, profile pictures, and activity tracking.

## Development Workflows

### Essential Commands (Windows PowerShell)
```powershell
# Environment setup
venv\Scripts\activate
pip install -r requirements.txt

# Database operations
python manage.py makemigrations; python manage.py migrate
python manage.py createsuperuser

# Development server
python manage.py runserver

# Testing
python manage.py test
python manage.py test patients  # Specific app
npx playwright test  # E2E tests
```

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

### Security & File Handling
- **CSP and security headers** configured in `settings.py`
- **File uploads**: Video files (2GB max), general uploads (100MB memory limit)
- **Validation**: Custom validators for medical data, file types, and sizes
- **User activity tracking** via `users.middleware.UserActivityMiddleware`

### Frontend Architecture & UI Consistency
- **AdminLTE 3.2 + Bootstrap 4.6** professional medical interface
- **Template inheritance**: `templates/src/base.html` for logged-in users, `templates/src/basic_plane.html` for auth
- **Enhanced interactions**: HTMX, Select2, Video.js, CKEditor
- **Static files**: WhiteNoise serving with custom utilities in `static/js/`

### UI/UX Consistency Standards

#### Template Structure (MANDATORY)
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

#### CSS Framework Stack (DO NOT CHANGE)
- **AdminLTE 3.2**: Core layout and components
- **Bootstrap 4.6**: Grid system, utilities, forms
- **Font Awesome 6.4**: Icons throughout
- **Custom CSS**: `static/dist/css/` (custom_css.css, ndas-sidebar.css)

#### Component Patterns
- **Info Boxes**: Use AdminLTE's `info-box` class with consistent icons
- **Cards**: Bootstrap `card` class with `card-header`, `card-body`
- **Tables**: `table table-hover table-striped` for data displays
- **Buttons**: Bootstrap button classes with FontAwesome icons
- **Navigation**: AdminLTE sidebar structure in `main_sidebar_menu.html`

#### Color Scheme & Branding
- **Primary**: AdminLTE's default primary blue
- **Medical context**: Use consistent success (green), warning (yellow), danger (red)
- **Sidebar**: `sidebar-dark-primary` theme
- **User panel**: Profile pictures with `img-circle elevation-2`

#### JavaScript Standards
- **jQuery 3.6**: Primary DOM manipulation
- **Bootstrap 4 JS**: Component initialization
- **HTMX 1.9**: Dynamic content loading
- **Select2**: Enhanced dropdowns
- **Video.js**: Video playback
- **Custom utilities**: Use `static/js/app-utils.js` for common functions

#### Responsive Design Rules
- **Mobile-first**: All templates include responsive CSS
- **Breakpoints**: Bootstrap 4's grid system (xs, sm, md, lg, xl)
- **Navigation**: Collapsible sidebar on mobile
- **Tables**: Always wrap in `.table-responsive`

## Critical Development Practices

### When Adding New Models
1. Inherit from `TimeStampedModel, UserTrackingMixin`
2. Add choices to `ndas/custom_codes/choice.py`
3. Create validators in `ndas/custom_codes/validators.py`
4. Use `db_index=True` for searchable fields
5. Include comprehensive help_text for medical fields

### File Upload Handling
Always use custom validators from `ndas/custom_codes/validators.py`. Example:
```python
file_field = models.FileField(
    upload_to="path/%Y/%m/",
    validators=[validate_video_file],  # Or appropriate validator
)
```

### Security Considerations
- All forms inherit security middleware (CSRF, rate limiting)
- User activity automatically tracked via middleware
- File access controlled through custom access level choices
- Session timeout: 1 hour with browser close expiry

### UI/UX Development Rules
1. **Always extend** `'src/base.html'` for authenticated pages
2. **Include CSRF token** in all container-fluid divs: `{% csrf_token %}`
3. **Use consistent form classes** from `patients/forms.py` patterns
4. **Initialize components** in templates: Bootstrap tooltips, Select2, HTMX
5. **Follow AdminLTE structure**: info-box, card layouts, table patterns
6. **Maintain responsive design** with mobile-first CSS
7. **Use custom utilities** from `static/js/app-utils.js` for common functions

### Testing Strategy
- Django tests: `python manage.py test [app_name]`
- Playwright E2E tests in `tests/` directory
- Test files minimal but framework established

## Production Features
- **Environment**: `.env` file with python-decouple
- **Database**: PostgreSQL ready with connection pooling
- **Caching**: Redis integration configured
- **Task processing**: Celery for video processing with FFmpeg
- **Monitoring**: Sentry SDK integration
- **Static files**: WhiteNoise for production serving

## Common Integration Points
- **Video processing**: FFmpeg integration for metadata extraction via `ffmpeg-python`
- **Rich text**: CKEditor for assessment fields
- **PDF generation**: ReportLab for medical reports
- **Authentication**: Custom user model with professional roles
- **File organization**: Date-based media structure (`%Y/%m/`)

## Data Flow Patterns
- **Patient → Video → Assessment**: Core workflow where patients have videos, videos have assessments
- **User tracking**: All CUD operations automatically track user via middleware
- **Status management**: Use `ndas_enums.PtStatus` for patient status filtering
- **Search optimization**: Key fields indexed, use `getPatientList()` for filtered queries

When extending functionality, follow the established patterns of centralized configuration, comprehensive validation, and consistent user tracking across all data modifications.