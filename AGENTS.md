# NDAS AI Agent Instructions

Workflow guidance for AI agents. For project patterns and architecture, see `CLAUDE.md`.

**Last Updated:** 2025-12-25

<!-- OPENSPEC:START -->
## OpenSpec Instructions

For proposals, breaking changes, or architecture work, see `openspec/AGENTS.md` for the complete spec-driven workflow.

<!-- OPENSPEC:END -->

## Pre-Task Checklist

Before starting any task:
- [ ] Read `CLAUDE.md` for project patterns
- [ ] Check `openspec list` for active changes
- [ ] Verify Patient field names (common errors in CLAUDE.md)

## Development Workflows

### Bug Fixes

1. Check `temp_documents/BUG_AND_PERFORMANCE_ANALYSIS.md` for existing documentation
2. Use `get_object_or_404()` not `.objects.get()`
3. Test: `python manage.py test [app_name]`

### Model Changes

1. Inherit from `TimeStampedModel, UserTrackingMixin`
2. Add choices to `ndas/custom_codes/choice.py`
3. Add validators to `ndas/custom_codes/validators.py`
4. Add `db_index=True` to searchable fields
5. Run: `python manage.py makemigrations && python manage.py migrate`

### View Changes

1. Use `@login_required(login_url="user-login")`
2. Add `@require_GET` or `@require_http_methods(["GET", "POST"])`
3. Add `@ratelimit(key='user_or_ip', rate='10/m')` for state changes
4. Use `select_related()`/`prefetch_related()` for related objects
5. Use `get_object_or_404()` for lookups

### Template Changes

1. Extend `'src/base.html'` (authenticated) or `'src/basic_plane.html'` (public)
2. Include `{% csrf_token %}` in container-fluid divs
3. Follow naming: `manager.html`, `add.html`, `edit.html`, `view.html`
4. **Never** change CSS framework (AdminLTE 3.2 + Bootstrap 4.6)

### Delete Operations

```python
from ndas.custom_codes.delete_helpers import (
    has_delete_permission, validate_can_delete,
    get_entity_warning_items, get_entity_detail_items
)
```

Use `{% load delete_modal_tags %}` for confirmation modals.

### Security Implementation

- Rate limit: `@ratelimit(key='user_or_ip', rate='10/m')` create/edit, `5/m` delete
- Sanitize: `sanitize_text_input()` for user text, `sanitize_filename()` for uploads
- HTTP methods: `@require_GET`, `@require_http_methods(["GET", "POST"])`

### Performance Optimization

```python
# Use aggregate() instead of multiple count()
from django.db.models import Count, Q
stats = Model.objects.aggregate(
    total=Count('id'),
    active=Count('id', filter=Q(status='active'))
)

# Use Exists() for filter checks
from django.db.models import Exists, OuterRef
Model.objects.annotate(has_video=Exists(Video.objects.filter(patient=OuterRef('pk'))))

# Use .only() for specific fields
Model.objects.only('id', 'name', 'status')
```

## Pre-Commit Checklist

- [ ] Models inherit `TimeStampedModel, UserTrackingMixin`
- [ ] Views use `get_object_or_404()`
- [ ] Templates extend base, include CSRF
- [ ] File uploads validated
- [ ] No N+1 queries (select_related/prefetch_related)
- [ ] Rate limiting on state changes
- [ ] Input sanitization applied
- [ ] HTTP method decorators on views
- [ ] Tests pass: `python manage.py test`

## Common Patterns

### Error Handling

```python
from ndas.custom_codes.error_handlers import handle_view_errors

@handle_view_errors(redirect_url='patient-manager', error_message='Error processing patient')
def my_view(request, pk):
    # View logic - errors automatically handled with logging
    pass
```

### File Uploads

```python
from django.conf import settings
settings.FILE_UPLOAD_LIMITS['VIDEO_MAX_SIZE']  # 2GB
settings.ALLOWED_FILE_EXTENSIONS['VIDEO']      # ['.mp4', '.mov', ...]
```

### Patient Field Reference

```python
patient.bht, patient.nnc_no, patient.baby_name, patient.dob_tob
patient.pog_wks, patient.pog_days, patient.birth_weight, patient.hc
patient.apgar_1, patient.apgar_5, patient.apgar_10
```

Full reference with common errors in `CLAUDE.md`.
