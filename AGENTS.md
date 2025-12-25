# NDAS AI Agent Instructions

**Last Updated:** 2025-12-25 (Context Sync)

This file provides workflow guidance for AI agents working on the NDAS project.

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

## Agent Workflows

### 1. Bug Fix Workflow

When fixing bugs:
1. **Verify the bug** - Reproduce the issue if possible
2. **Check `BUG_AND_PERFORMANCE_ANALYSIS.md`** - The bug may already be documented with a fix plan
3. **Check `BUG_FIX_PLAN.md`** - Follow the prioritized fix instructions if applicable
4. **Use proper error handling** - Always use `get_object_or_404()` instead of `.objects.get()`
5. **Test the fix** - Run relevant tests with `python manage.py test [app_name]`

### 2. Model Development Workflow

When creating or modifying models:
1. **Inherit from base classes** (MANDATORY):
   ```python
   from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin
   class MyModel(TimeStampedModel, UserTrackingMixin):
       pass
   ```
2. **Add choices to `ndas/custom_codes/choice.py`** - Never define choices inline
3. **Add validators to `ndas/custom_codes/validators.py`**
4. **Add `db_index=True`** to searchable/filterable fields
5. **Run migrations**: `python manage.py makemigrations && python manage.py migrate`

### 3. View Development Workflow

When creating or modifying views:
1. **Always use `get_object_or_404()`** instead of `.objects.get()`
2. **Add `@login_required(login_url="user-login")`** decorator
3. **Use `select_related()`** for foreign keys to avoid N+1 queries
4. **Use `prefetch_related()`** for reverse relations and many-to-many
5. **Pass computed values to templates** - Don't call heavy methods in templates

### 4. Template Development Workflow

When creating or modifying templates:
1. **Extend base templates**:
   - `'src/base.html'` for authenticated pages
   - `'src/basic_plane.html'` for public pages
2. **Include `{% csrf_token %}`** in container-fluid divs
3. **Use established CSS classes** - AdminLTE 3.2 + Bootstrap 4.6
4. **Follow naming conventions**:
   - `manager.html` - List views
   - `add.html` - Create forms
   - `edit.html` - Update forms
   - `view.html` - Detail views

### 5. Delete Operation Workflow

When implementing entity deletion:
1. **Use delete_helpers module**:
   ```python
   from ndas.custom_codes.delete_helpers import (
       has_delete_permission, validate_can_delete,
       get_entity_warning_items, get_entity_detail_items
   )
   ```
2. **Include delete confirmation modal** using `{% load delete_modal_tags %}`
3. **Check business rules** - Videos cannot be deleted if in assessments
4. **Handle cascade warnings** for related records

### 6. Security Review Workflow

When reviewing security:
1. **Check middleware order** - Critical for security headers
2. **Verify CSP configuration** - Nonces for scripts in production
3. **Validate file uploads** - Use centralized settings from `FILE_UPLOAD_LIMITS`
4. **Check rate limiting** - Critical operations should be rate-limited

## Common Patterns Reference

### Patient Model Field Names (CRITICAL)

Always verify field names - common mistakes:
```python
patient.bht              # NOT bht_number
patient.baby_name        # NOT patient_name or name
patient.dob_tob          # NOT date_of_birth or dob
patient.pog_wks          # NOT gestational_age_weeks
patient.birth_weight     # NOT birth_weight_g or weight
patient.hc               # NOT head_circumference
patient.apgar_1          # NOT apgar_1_min or apgar1
```

### File Upload Settings

Access centralized limits:
```python
from django.conf import settings
settings.FILE_UPLOAD_LIMITS['VIDEO_MAX_SIZE']      # 2GB
settings.FILE_UPLOAD_LIMITS['IMAGE_MAX_SIZE']      # 10MB
settings.FILE_UPLOAD_LIMITS['PROFILE_PICTURE_MAX_SIZE']  # 5MB
settings.ALLOWED_FILE_EXTENSIONS['VIDEO']          # ['.mp4', '.mov', ...]
```

### 7. Security Implementation Workflow

When implementing security features:
1. **Use rate limiting** for CRUD operations:
   ```python
   from django_ratelimit.decorators import ratelimit
   @ratelimit(key='user_or_ip', rate='10/m')  # Create/Edit: 10/min
   @ratelimit(key='user_or_ip', rate='5/m')   # Delete: 5/min
   ```
2. **Sanitize user input** using `sanitize_text_input()` from validators
3. **Validate file uploads** with MIME type checking (python-magic)
4. **Add HTTP method restrictions**:
   ```python
   from django.views.decorators.http import require_GET, require_http_methods
   @require_GET  # For read-only views
   @require_http_methods(["GET", "POST"])  # For form views
   ```
5. **Check middleware order** before modifying security configuration

### 8. Performance Optimization Workflow

When optimizing queries:
1. **Use select_related()** for ForeignKey fields
2. **Use prefetch_related()** for reverse relations and ManyToMany
3. **Use aggregate()** instead of multiple `.count()` calls:
   ```python
   from django.db.models import Count, Q
   stats = Model.objects.aggregate(
       total=Count('id'),
       active=Count('id', filter=Q(status='active'))
   )
   ```
4. **Use Exists()** subqueries instead of loading IDs into memory
5. **Use .only()** to load only needed fields

## Pre-Commit Checklist

Before completing any task:
- [ ] All models inherit from `TimeStampedModel, UserTrackingMixin`
- [ ] Views use `get_object_or_404()` not `.objects.get()`
- [ ] Templates extend proper base template
- [ ] CSRF tokens included in forms
- [ ] File uploads validated with proper limits
- [ ] No N+1 query issues (use select_related/prefetch_related)
- [ ] Rate limiting applied to state-changing operations
- [ ] Input sanitization for user-provided text
- [ ] HTTP method decorators on views
- [ ] Tests pass: `python manage.py test`

## Recent Optimizations Reference

### Performance Improvements (December 2025)

| Optimization | Impact | Location |
|--------------|--------|----------|
| Query count reduction | 60-96% | patients/views.py, users/views.py |
| Middleware session throttling | 95% DB write reduction | users/middleware.py |
| Aggregate count queries | 75% query reduction | All manager views |
| Exists() subqueries | Improved filter performance | video/views.py |

### Security Hardening (December 2025)

| Feature | Coverage | Status |
|---------|----------|--------|
| Rate limiting | 24 CRUD operations | Complete |
| Input sanitization | problemlist forms | Complete |
| MIME type validation | Video uploads | Complete |
| Filename sanitization | All file uploads | Complete |
| HTTP method restrictions | Key patient views | Complete |

### Database Optimizations (December 2025)

| Change | Fields/Tables | Purpose |
|--------|---------------|---------|
| Added indexes | 5 fields | Query performance |
| Unique constraints | DiagnosisList.abr, IndicationsForGMA.title | Data integrity |
| TextField to CharField | DiagnosisList.title | Better indexing |
| Meta classes | 2 models | Admin display, ordering |