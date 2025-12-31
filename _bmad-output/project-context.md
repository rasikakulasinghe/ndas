---
project_name: 'NDAS'
user_name: 'rasikakulasinghe'
date: '2025-12-31'
sections_completed: ['discovery', 'technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'code_quality_rules', 'workflow_rules', 'critical_rules']
status: 'complete'
rule_count: 125
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

**Framework:** Django 4.2.16 (Python web framework)
**Database:** PostgreSQL (production) / SQLite (development)
**Template Engine:** Django Templates with AdminLTE 3.2
**CSS Framework:** Bootstrap 4.6 + Font Awesome 6.4
**JavaScript Libraries:** HTMX, Video.js
**Static Files:** WhiteNoise with CompressedManifestStaticFilesStorage
**Security:** django-csp, django-permissions-policy, django-ratelimit
**Rich Text:** CKEditor, django-richtextfield
**Media Cleanup:** django-cleanup

---

## Critical Implementation Rules

### Language-Specific Rules (Python/Django)

**Model Inheritance (MANDATORY):**
- ALL models MUST inherit from `TimeStampedModel, UserTrackingMixin`
- Import from: `ndas.custom_codes.Custom_abstract_class`
- NEVER manually set `added_by` or `last_edit_by` - auto-populated by UserActivityMiddleware
- Auto-provides: `created_at`, `updated_at`, `added_by`, `last_edit_by`

**Medical Field Naming (CRITICAL):**
```python
# CORRECT field names - common error source:
patient.bht              # NOT bht_number
patient.nnc_no           # NOT nnc_number
patient.baby_name        # NOT patient_name or name
patient.dob_tob          # NOT date_of_birth or dob
patient.pog_wks          # NOT gestational_age_weeks
patient.pog_days         # NOT gestational_age_days
patient.birth_weight     # NOT birth_weight_g
patient.apgar_1          # NOT apgar_1_min
patient.apgar_5          # NOT apgar_5_min
```

**View Patterns:**
- ALWAYS use `get_object_or_404()`, NEVER `.objects.get()`
- ALWAYS use `select_related()`/`prefetch_related()` for foreign keys
- ALWAYS sanitize input: `sanitize_text_input(request.POST.get('field'))`

**Choices & Validators:**
- NEVER define choices inline in models - add to `ndas/custom_codes/choice.py`
- NEVER define validators inline - add to `ndas/custom_codes/validators.py`

**Settings Access:**
- Use centralized constants: `settings.FILE_UPLOAD_LIMITS['VIDEO_MAX_SIZE']`
- NEVER hardcode file size limits or allowed extensions

**Database Fields:**
- Use `db_index=True` for ALL searchable fields (identifiers, foreign keys)

### Framework-Specific Rules (Django)

**Security Middleware Stack (ORDER IS CRITICAL):**
```python
# NEVER reorder - this exact sequence is required:
1. SecurityMiddleware
2. WhiteNoiseMiddleware
3. CSPMiddleware
4. AdditionalSecurityHeadersMiddleware (custom)
5. SessionMiddleware
6. CommonMiddleware
7. CsrfViewMiddleware
8. AuthenticationMiddleware
9. UserActivityMiddleware (custom - auto-tracks changes)
10. MessageMiddleware
11. XFrameOptionsMiddleware
12. UserAgentMiddleware
13. SubscriptionCheckMiddleware (custom)
14. SecurityHeadersValidationMiddleware (production only)
```

**View Decorators (Security):**
```python
# Standard pattern for views:
@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])  # NEVER use generic methods
@ratelimit(key='user_or_ip', rate='10/m')  # 24+ CRUD operations protected
def my_view(request, pk):
    # Implementation
```

**Template Patterns:**
- ALWAYS extend `'src/base.html'` (authenticated) or `'src/basic_plane.html'` (public)
- Template naming: `manager.html` (list), `add.html` (create), `edit.html` (update), `view.html` (detail)
- NEVER change CSS framework from AdminLTE 3.2 + Bootstrap 4.6

**Content Security Policy (CSP):**
- Production: NEVER use `'unsafe-inline'` or `'unsafe-eval'` for scripts
- Use nonce-based inline scripts: `CSP_INCLUDE_NONCE_IN = ['script-src']`
- `'unsafe-inline'` allowed ONLY for styles (templates use inline styles)

**File Upload Handling:**
- ALWAYS validate MIME type using python-magic, not just extension
- Type-specific limits: Video (2GB), Image (10MB), Document (100MB), Profile (5MB)
- ALWAYS use `sanitize_filename()` before saving files
- Access via `settings.FILE_UPLOAD_LIMITS` and `settings.ALLOWED_FILE_EXTENSIONS`

**Session Configuration:**
- 1 hour timeout (3600s)
- Browser-close expiry enabled
- Cache-based session engine
- `SESSION_SAVE_EVERY_REQUEST = True` to prevent premature expiry

### Testing Rules

**Test Command:**
```bash
python manage.py test [app_name]
```

**Test Organization:**
- Django's built-in test framework (unittest-based)
- Test files in each app directory
- Run tests before commits

**Test Structure Requirements:**
- Use Django's `TestCase` for database-dependent tests
- Use `SimpleTestCase` for tests without database
- Use `TransactionTestCase` for tests requiring transaction control

**Common Test Patterns:**
- ALWAYS test model validation (birth_weight ranges, APGAR scores 0-10, POG validation)
- ALWAYS test view permissions (@login_required enforcement)
- ALWAYS test file upload validation (MIME type, size limits)
- ALWAYS test input sanitization (XSS prevention)
- ALWAYS test rate limiting doesn't break legitimate use

**Mock Usage:**
- Mock file uploads for speed
- Mock external services (email)
- Use Django's test client for view testing

**Coverage Expectations:**
- Test all custom validators in `ndas/custom_codes/validators.py`
- Test all model `clean()` methods
- Test permission checks in delete operations

### Code Quality & Style Rules

**File Organization:**
- **Apps:** `patients/`, `users/`, `video/`, `reports/`, `problemlist/`
- **Custom Codes:** ALL shared utilities in `ndas/custom_codes/` directory
  - `Custom_abstract_class.py` - Base models
  - `choice.py` - ALL TextChoices (NEVER inline)
  - `validators.py` - ALL validators and sanitization
  - `sanitization.py` - HTML sanitization (bleach)
  - `custom_methods.py` - Utility functions
  - `ndas_enums.py` - Enumerations
  - `delete_helpers.py` - Deletion utilities
  - `error_handlers.py` - View decorators
  - `security_middleware.py` - Custom middleware

**Template Organization:**
- `templates/src/` - Base templates (base.html, basic_plane.html)
- `templates/{app}/` - App-specific templates
- Naming: `manager.html`, `add.html`, `edit.html`, `view.html`

**Naming Conventions:**
- Models: PascalCase (`Patient`, `VideoRecord`)
- Views: snake_case (`patient_detail`, `video_upload`)
- URLs: kebab-case (`patient-detail`, `video-upload`)
- Template blocks: snake_case (`{% block main_content %}`)

**Code Organization Rules:**
- NEVER create inline choices - use `choice.py`
- NEVER create inline validators - use `validators.py`
- NEVER duplicate utility functions - add to `custom_methods.py`
- ALWAYS use centralized delete helpers from `delete_helpers.py`
- ALWAYS import from `ndas.custom_codes.*` for shared code

**Documentation Requirements:**
- Docstrings for complex validators (see `sanitize_text_input()` example)
- Comments for security decisions (CSP configuration)
- Help text on all model fields using `help_text=_("description")`

### Development Workflow Rules

**Environment Management:**
```bash
# Windows development environment
venv\Scripts\activate
pip install -r requirements.txt
```

**Database Migrations:**
```bash
python manage.py makemigrations [app]
python manage.py migrate
```

**Development Server:**
```bash
python manage.py runserver
```

**Environment Variables:**
- Use `.env` file with python-decouple
- NEVER commit `.env` to repository
- Required vars: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- Optional: Database config, Redis, Email settings

**Git Repository:**
- Main branch: `main`
- Commit messages: Clear description of what changed
- Example: "Refactor error handlers for CSP compliance"

**Deployment Patterns:**
- PostgreSQL for production (SQLite for development)
- WhiteNoise serves static files (no separate server needed)
- Cache: Redis (production) / LocMem (development)

**Static Files Collection:**
```bash
python manage.py collectstatic --noinput  # Production only
```

### Critical Don't-Miss Rules

**Anti-Patterns to Avoid:**

```python
# ❌ WRONG - Using .objects.get() directly
patient = Patient.objects.get(id=pk)  # Raises DoesNotExist exception

# ✅ CORRECT - Always use get_object_or_404
patient = get_object_or_404(Patient, id=pk)  # Returns 404 page

# ❌ WRONG - Hardcoded file size limits
if uploaded_file.size > 2147483648:  # Magic number

# ✅ CORRECT - Use settings constants
if uploaded_file.size > settings.FILE_UPLOAD_LIMITS['VIDEO_MAX_SIZE']:

# ❌ WRONG - Field name errors (common mistake!)
patient.bht_number  # AttributeError - field doesn't exist
patient.date_of_birth  # AttributeError - field doesn't exist

# ✅ CORRECT - Use actual field names
patient.bht  # Correct
patient.dob_tob  # Correct

# ❌ WRONG - Inline choices
class MyModel(models.Model):
    status = models.CharField(choices=[('A', 'Active'), ...])

# ✅ CORRECT - Centralized choices
from ndas.custom_codes.choice import MY_STATUS_CHOICES
class MyModel(models.Model):
    status = models.CharField(choices=MY_STATUS_CHOICES)

# ❌ WRONG - File extension validation only
if filename.endswith('.mp4'):  # Can be bypassed

# ✅ CORRECT - MIME type validation with python-magic
from ndas.custom_codes.validators import validate_video_file
```

**Edge Cases to Handle:**

- **Birth Weight Validation:** Range 200g-8000g (medical reality, not 0-10000)
- **APGAR Scores:** Exactly 0-10, no negatives or values >10
- **POG (Period of Gestation):** Weeks 20-44, Days 0-6 only
- **Empty Files:** Check `size < 1024` bytes to reject corrupted uploads
- **Medical Notation:** `sanitize_text_input()` preserves "< 5 mg/dl" and "> 38°C"
- **Delete Permissions:** Videos in assessments cannot be deleted (business rule)
- **User Tracking:** NEVER manually set `added_by`/`last_edit_by` - middleware handles it

**Security Rules:**

- **Input Sanitization:** ALWAYS use `sanitize_text_input()` on ALL user input
- **XSS Prevention:** NEVER trust user input, even for medical data
- **CSRF Tokens:** ALWAYS include `{% csrf_token %}` in forms
- **CSP Compliance:** NEVER use inline `onclick` handlers - violates CSP in production
- **Rate Limiting:** Protected operations: 10/min for create/edit, 5/min for delete
- **File Validation:** MIME type + size + extension checks (python-magic required)
- **Path Traversal:** ALWAYS use `sanitize_filename()` before saving files
- **Session Security:** 1 hour timeout enforced, cannot be extended arbitrarily

**Performance Gotchas:**

- **N+1 Queries:** ALWAYS use `select_related()` for foreign keys
- **Middleware Order:** NEVER reorder - breaks security headers and CSP
- **Database Isolation:** PostgreSQL uses 'read committed' (NOT 'serializable') to avoid deadlocks
- **Static Files:** Development uses STATICFILES_DIRS, production uses STATIC_ROOT
- **Large File Uploads:** Videos up to 2GB - use TemporaryFileUploadHandler
- **Git Bash Path Mangling:** Windows Git Bash converts `/media/` to absolute paths - sanitize URLs

**Medical Domain Rules:**

- **Identifiers:** BHT, NNC, PTC, PC, PIN, Disk No. are all unique but optional
- **Assessment Types:** GPA, HINE, CDIC, Developmental
- **Validation Must Match Medical Reality:** Not arbitrary ranges

---

## Usage Guidelines

**For AI Agents:**

- Read this file before implementing any code
- Follow ALL rules exactly as documented
- When in doubt, prefer the more restrictive option
- Update this file if new patterns emerge

**For Humans:**

- Keep this file lean and focused on agent needs
- Update when technology stack changes
- Review quarterly for outdated rules
- Remove rules that become obvious over time

**Last Updated:** 2025-12-31
