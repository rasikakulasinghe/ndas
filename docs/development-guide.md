# NDAS Development Guide

Last Updated: 2026-03-09

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.9 or higher | 3.11+ recommended |
| pip | Current | Comes with Python |
| Git | Any | |
| FFmpeg | Any | Optional but recommended for video duration extraction |
| Redis | 6+ | Optional; falls back to LocMemCache |
| PostgreSQL | 12+ | Optional; falls back to SQLite |

---

## Environment Setup

### 1. Clone and Enter the Project

```bash
cd "D:\Projects\Current Projects\NDAS - Project\NDAS"
```

### 2. Create and Activate Virtual Environment

```bash
# Create
python -m venv venv

# Activate (Windows CMD/PowerShell)
venv\Scripts\activate

# Activate (Windows Git Bash)
source venv/Scripts/activate

# Activate (Linux/Mac)
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Key packages installed:
- `Django==4.2.16` — web framework
- `python-decouple` — environment variable management
- `whitenoise` — static file serving
- `django-csp`, `django-permissions-policy` — security headers
- `django-ratelimit` — rate limiting
- `django-user-agents` — user agent parsing
- `reportlab`, `openpyxl` — PDF/Excel generation
- `moviepy` — video metadata extraction
- `bleach` — HTML sanitization
- `pillow` — image handling
- `python-dateutil` — relativedelta for age calculations
- `django-cleanup` — automatic media file cleanup on model delete
- `django-ckeditor` — rich text editor
- `django-richtextfield` — rich text field for models

---

## Environment Variables

Create a `.env` file in the project root. Never commit this file.

```env
# Required
SECRET_KEY=your-secret-key-minimum-50-characters-long
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (defaults to SQLite if omitted)
# DB_ENGINE=django.db.backends.postgresql
# DB_NAME=ndas
# DB_USER=ndas_user
# DB_PASSWORD=secure_password
# DB_HOST=localhost
# DB_PORT=5432

# Cache (defaults to LocMemCache if omitted)
# REDIS_URL=redis://localhost:6379/0

# Multi-institution (defaults shown)
MULTI_INSTITUTION_ENABLED=True
DEFAULT_INSTITUTION_NAME=Default Institution
DEFAULT_INSTITUTION_SLUG=default

# Email (defaults to console backend in DEBUG mode)
# EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# EMAIL_HOST=smtp.gmail.com
# EMAIL_PORT=587
# EMAIL_USE_TLS=True
# EMAIL_HOST_USER=your-email@gmail.com
# EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@ndas-system.com
EMAIL_VERIFICATION_REQUIRED=True
EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS=24

# Static/Media (optional — defaults to project/staticfiles and project/media)
# STATIC_ROOT=/path/to/staticfiles
# MEDIA_ROOT=/path/to/media

# Rate limiting
RATELIMIT_ENABLE=True

# Security (production only)
# SECURE_SSL_REDIRECT=True
# SESSION_COOKIE_SECURE=True
# CSRF_COOKIE_SECURE=True
# SECURE_HSTS_INCLUDE_SUBDOMAINS=True
# SECURE_HSTS_PRELOAD=True
# SECURE_PROXY_SSL_HEADER=True
```

---

## Database Setup

### SQLite (Default — Development)

No configuration needed. Database file is `db.sqlite3` at project root.

```bash
python manage.py migrate
python manage.py createsuperuser
```

### PostgreSQL (Optional)

```bash
# Create database
psql -U postgres
CREATE DATABASE ndas;
CREATE USER ndas_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE ndas TO ndas_user;
\q
```

Set `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` in `.env`, then:

```bash
python manage.py migrate
python manage.py createsuperuser
```

---

## Running the Development Server

```bash
# Ensure venv is activated
python manage.py runserver

# Custom port
python manage.py runserver 0.0.0.0:8080
```

The server runs at `http://127.0.0.1:8000/` by default. Login at `http://127.0.0.1:8000/users/`.

---

## Running Tests

```bash
# All tests
python manage.py test

# Specific app
python manage.py test patients
python manage.py test users
python manage.py test video

# With verbosity
python manage.py test --verbosity=2

# Specific test class or method
python manage.py test patients.tests.PatientModelTests
python manage.py test patients.tests.PatientModelTests.test_birth_weight_validation
```

Test files are located in:
- `patientstests/` — patient app tests
- `tests/` — general/integration tests
- `ndas/tests/` — core tests

---

## Migration Workflow

```bash
# After changing a model — specify the app
python manage.py makemigrations patients
python manage.py makemigrations users
python manage.py makemigrations video

# Apply migrations
python manage.py migrate

# Check migration status
python manage.py showmigrations

# Preview SQL for a migration (debugging)
python manage.py sqlmigrate patients 0001
```

**Important:** Always create migrations for the specific app, not with `makemigrations` alone (which creates migrations for all apps and can produce unexpected results).

---

## Adding a New Feature: Step-by-Step

### Step 1: Create the Model

In the app's `models.py`:

```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

class MyModel(TimeStampedModel, UserTrackingMixin):
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='my_models',
        db_index=True,
    )
    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'My Model'
        verbose_name_plural = 'My Models'

    def __str__(self):
        return self.name
```

Rules:
- Always inherit from `TimeStampedModel, UserTrackingMixin`
- Add `db_index=True` to fields used in filtering/ordering
- Put all choices in `ndas/custom_codes/choice.py`
- Put validators in `ndas/custom_codes/validators.py`

### Step 2: Create Migration

```bash
python manage.py makemigrations <app_name>
python manage.py migrate
```

### Step 3: Register in Admin

In the app's `admin.py`:

```python
from django.contrib import admin
from .models import MyModel

@admin.register(MyModel)
class MyModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'patient', 'created_at']
    search_fields = ['name', 'patient__baby_name']
```

### Step 4: Create the View

In the app's `views.py`:

```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_http_methods
from django_ratelimit.decorators import ratelimit
from ndas.custom_codes.error_handlers import handle_view_errors
from .models import MyModel

@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='home')
def my_model_add(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    if request.method == 'POST':
        form = MyModelForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.patient = patient
            obj.save()
            messages.success(request, 'Created successfully.')
            return redirect('my-model-view', pk=obj.pk)
    else:
        form = MyModelForm()
    return render(request, 'myapp/add.html', {'patient': patient, 'form': form})
```

### Step 5: Create Form

In the app's `forms.py`:

```python
from django import forms
from .models import MyModel

class MyModelForm(forms.ModelForm):
    class Meta:
        model = MyModel
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
```

### Step 6: Create URLs

In the app's `urls.py`:

```python
from django.urls import path
from . import views

urlpatterns = [
    path('my-model/add/<int:patient_id>/', views.my_model_add, name='my-model-add'),
    path('my-model/view/<int:pk>/', views.my_model_view, name='my-model-view'),
    path('my-model/edit/<int:pk>/', views.my_model_edit, name='my-model-edit'),
    path('my-model/delete/<int:pk>/', views.my_model_delete, name='my-model-delete'),
]
```

Include in root `ndas/urls.py` if adding a new app:

```python
path("myprefix/", include("myapp.urls")),
```

### Step 7: Create Templates

Template file: `templates/myapp/add.html`

```django
{% extends 'src/base.html' %}
{% load static %}

{% block title %}My Model - Add{% endblock %}

{% block main_content %}
<div class="container-fluid">
    {% csrf_token %}
    <form method="post">
        {% csrf_token %}
        {{ form.as_p }}
        <button type="submit" class="btn btn-primary">Save</button>
        <a href="{% url 'home' %}" class="btn btn-secondary">Cancel</a>
    </form>
</div>
{% endblock %}
```

Naming convention: `manager.html` (list), `add.html` (create), `edit.html` (update), `view.html` (detail)

---

## Code Conventions

### Critical Field Names (Do Not Rename)

```python
# Patient identifiers
patient.bht              # NOT bht_number
patient.nnc_no           # NOT nnc_number
patient.baby_name        # NOT patient_name or name
patient.dob_tob          # NOT date_of_birth or dob

# Birth data
patient.pog_wks          # NOT gestational_age_weeks
patient.pog_days         # NOT gestational_age_days
patient.birth_weight     # NOT birth_weight_g
patient.ofc              # NOT head_circumference or hc

# APGAR
patient.apgar_1          # NOT apgar_1_min
patient.apgar_5          # NOT apgar_5_min
patient.apgar_10         # NOT apgar_10_min
```

### Choices Convention

All choices go in `ndas/custom_codes/choice.py`. Use `TextChoices` for new work:

```python
# In choice.py
class MyStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    CLOSED = 'CLOSED', 'Closed'

# In model
from ndas.custom_codes.choice import MyStatus
status = models.CharField(max_length=20, choices=MyStatus.choices, default=MyStatus.ACTIVE)
```

### Import Convention

Always import from `ndas.custom_codes.*`:

```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
from ndas.custom_codes.validators import sanitize_text_input, validate_birth_weight
from ndas.custom_codes.custom_methods import getCountZeroIfNone, calculate_age_string
from ndas.custom_codes.ndas_enums import PtStatus
from ndas.custom_codes.delete_helpers import has_delete_permission, validate_can_delete
from ndas.custom_codes.error_handlers import handle_view_errors
```

### Query Optimization

- Always use `select_related()` for ForeignKey relations accessed in templates
- Always use `prefetch_related()` for ManyToMany and reverse FK relations
- For institution-scoped queries: `Patient.objects.for_institution(request.institution)`
- Never use `.objects.get()` in views — always `get_object_or_404()`

```python
# Good
patients = Patient.objects.for_institution(request.institution).select_related(
    'added_by', 'last_edit_by'
).prefetch_related('gm_assessments', 'hine_assessments')

# Bad
patient = Patient.objects.get(pk=pk)  # raises unhandled exception
```

### Input Sanitization

```python
from ndas.custom_codes.validators import sanitize_text_input

# For text fields from user input
cleaned_value = sanitize_text_input(request.POST.get('notes', ''))
```

---

## Security Checklist

Before submitting any view/form:

- [ ] View decorated with `@login_required(login_url="user-login")`
- [ ] View has `@require_GET` or `@require_http_methods(["GET", "POST"])`
- [ ] State-changing views have `@ratelimit` applied
- [ ] Forms include `{% csrf_token %}`
- [ ] Objects fetched with `get_object_or_404()`, not `.get()`
- [ ] File uploads validated with `validate_video_file` or `validate_attachment_file`
- [ ] User input sanitized with `sanitize_text_input()` where appropriate
- [ ] Delete operations check `has_delete_permission()` and `validate_can_delete()`
- [ ] No secrets in source code (use `.env`)
- [ ] CSS framework unchanged (AdminLTE 3.2 + Bootstrap 4.6)
- [ ] No middleware reordering

---

## Deployment Notes

Full deployment instructions are in `DEPLOYMENT.md`. Summary:

### cPanel / Shared Hosting (SQLite)

1. Upload code to server (outside `public_html`)
2. Create Python App via cPanel
3. Copy `.env.production.example` to `.env` and configure
4. `pip install -r requirements.txt`
5. `python manage.py migrate`
6. `python manage.py collectstatic --noinput`
7. `python manage.py createsuperuser`
8. Create `passenger_wsgi.py` for Passenger/WSGI

### VPS with PostgreSQL

1. Install system packages: `python3-pip python3-venv postgresql nginx redis-server ffmpeg`
2. Configure PostgreSQL database
3. Clone repo, create virtualenv, install requirements
4. Configure Nginx as reverse proxy
5. Configure Gunicorn or uWSGI as WSGI server
6. Run `collectstatic` and `migrate`
7. Configure SSL (Let's Encrypt recommended)

### Production Environment Variables (Additional)

```env
DEBUG=False
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
DB_ENGINE=django.db.backends.postgresql
REDIS_URL=redis://localhost:6379/0
```

### Cron Jobs

```bash
# Database backup daily at 2 AM
0 2 * * * cd /path/to/ndas && python manage.py backup_database

# Clear expired sessions daily at 4 AM
0 4 * * * cd /path/to/ndas && python manage.py clearsessions
```

---

## Logging

Logs are written to the `logs/` directory (auto-created on startup):

| File | Contents |
|------|---------|
| `logs/django.log` | All application logs (INFO+ in prod, DEBUG+ in dev). 15MB rotating, 10 backups |
| `logs/security.log` | Security events: login attempts, rate limit hits, header violations (production only) |

To view recent security events:
```bash
tail -f logs/security.log
```

---

## Common Management Commands

```bash
# Create superuser
python manage.py createsuperuser

# Open Django shell
python manage.py shell

# Database inspection
python manage.py dbshell

# List all URL patterns
python manage.py show_urls  # requires django-extensions

# Check for system issues
python manage.py check
python manage.py check --deploy  # production readiness check

# Clear sessions
python manage.py clearsessions

# Collect static files
python manage.py collectstatic --noinput
```
