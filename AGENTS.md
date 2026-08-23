# NDAS AI Agent Instructions

Workflow guidance for AI agents. For project patterns and architecture, see `CLAUDE.md`.

**Last Updated:** 2025-12-25

<!-- bmad:context -->
<!-- Verified 2026-08-23 against 6f7aa29. Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## NDAS

Django medical system for patient records, video-based neurodevelopmental assessments, and evaluation workflows. Solo-maintained, single `main` branch, no CI. Architecture and patterns: `CLAUDE.md`. Generated reference docs (data models, API contracts, source tree, dev guide): `docs/index.md`.

## Policy

- Never commit `.env` — real config (including `SECRET_KEY`) was committed here before; it's gitignored now, don't re-add it.
- Never set `MULTI_INSTITUTION_ENABLED=True` in production until `institution/tests/test_isolation.py` passes on staging — any cross-institution data leak is a blocking defect.

## Where things are

- `institution/` (multi-institution isolation) and `referral/` (cross-institution referrals) are Phase 2 apps, undocumented in `CLAUDE.md` — see `docs/index.md` and `docs/architecture.md`.
- Proposals / architecture changes: use the BMAD skills `bmad-spec` and `bmad-architecture` — OpenSpec was removed from this repo (old pointers are dead).
- Security test suites `video/tests/test_security.py`, `users/tests/test_security.py`, `reports/tests/test_security.py` cover ownership/isolation/rate-limit checks — run them when touching views or permissions in those apps.

## Running and verifying

- No `requirements.txt` is tracked (deleted, never restored) — reconstruct from the working `venv` (`pip freeze`) rather than `pip install -r requirements.txt`.
- `python run_qa_tests.py` is a separate Playwright E2E smoke suite (needs `python manage.py runserver` already running, logs in as `testadmin`) — distinct from `python manage.py test`.
- Test fixtures: `UserActivityMiddleware` doesn't run under the test client — set `added_by=user` manually in `Model.objects.create()` inside `setUp()`. Authenticate with `force_login(user)`, not `client.login()`. Test classes that render full templates need `@override_settings(STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})` or they fail on a staticfiles manifest error.

## Conventions that differ from defaults

- Historical/audit FK fields (e.g. `InstitutionSwitchLog.previous_institution_id`) use `IntegerField`, not `ForeignKey(..., on_delete=SET_NULL)` — so the historical ID survives the related record's deletion.
- Atomic cache ops use `cache.add(key, value, timeout)`, never `cache.get()` + `cache.set()` — the latter race-conditions.

## Known pitfalls

- Inline `<script>` tags need `nonce="{{ request.csp_nonce }}"` in DEBUG too, not just production — `unsafe-inline`/`unsafe-eval` are removed from `CSP_SCRIPT_SRC` in both; a script without a nonce silently fails everywhere.
- `institution_scope()` (`ndas/custom_codes/custom_methods.py`) raises `PermissionDenied` when a non-superuser has `institution_id` set but `request.institution` is `None` — that signals a middleware misconfiguration; never swallow it.
- Staff may only edit/delete videos they personally uploaded (`video.added_by == request.user`); a bare `is_staff` bypass was a real security defect here once — gate unrestricted access on `is_superuser`, not `is_staff`.
- `InstitutionScopedManager.for_institution(None)` returns ALL records — intentional Phase 1-compatibility fallback, not a bug. Don't "fix" it.
- Any new report-download endpoint must verify the `report_owner_{file_id}_{session_key}` cache key set by `report_builder` before serving the file — a UUID/file_id alone is not access control.

<!-- /bmad:context -->

## Pre-Task Checklist

Before starting any task:
- [ ] Read `CLAUDE.md` for project patterns
- [ ] Verify Patient field names (common errors in CLAUDE.md)

## Development Workflows

### Bug Fixes

1. Use `get_object_or_404()` not `.objects.get()`
2. Test: `python manage.py test [app_name]`

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
