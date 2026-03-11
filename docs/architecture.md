# NDAS Architecture

Last Updated: 2026-03-09

---

## Architecture Pattern

NDAS follows the Django MVT (Model-View-Template) monolithic architecture pattern. All business logic, data access, and rendering are handled within a single Django process. There is no API layer, separate frontend framework, or microservices — templates are server-rendered with HTMX providing lightweight dynamic interaction.

---

## Django Project Structure

```
ndas/                    # Project core (settings, urls, wsgi)
  custom_codes/          # Shared utilities and base classes
patients/                # Domain app: patient records and assessments
users/                   # Domain app: auth and user management
video/                   # Domain app: video management
reports/                 # Domain app: reporting (PDF/Excel)
problemlist/             # Domain app: problem list
institution/             # Phase 2: institution management
referral/                # Phase 2: cross-institution referrals
```

---

## Middleware Stack (Order Critical)

The middleware stack is defined in `ndas/settings.py` and must not be reordered.

| # | Middleware | Source | Purpose |
|---|-----------|--------|---------|
| 1 | `SecurityMiddleware` | Django | HTTPS redirect, HSTS headers, content type sniffing protection |
| 2 | `WhiteNoiseMiddleware` | whitenoise | Serve compressed static files directly from Django |
| 3 | `CSPMiddleware` | django-csp | Content Security Policy headers |
| 4 | `AdditionalSecurityHeadersMiddleware` | `ndas/custom_codes/security_middleware.py` | Adds Referrer-Policy, Cross-Origin-Opener-Policy, X-Permitted-Cross-Domain-Policies, Permissions-Policy |
| 5 | `SessionMiddleware` | Django | Session management |
| 6 | `CommonMiddleware` | Django | URL normalization, Content-Length |
| 7 | `CsrfViewMiddleware` | Django | CSRF token validation |
| 8 | `AuthenticationMiddleware` | Django | Attaches `request.user` |
| 9 | `UserActivityMiddleware` | `users/middleware.py` | Auto-populates `added_by` / `last_edit_by` on models; logs login/logout activity |
| 10 | `MessageMiddleware` | Django | Django messages framework |
| 11 | `XFrameOptionsMiddleware` | Django | X-Frame-Options: DENY |
| 12 | `UserAgentMiddleware` | django-user-agents | Parses `request.user_agent` (browser, OS, device) |
| 13 | `SubscriptionCheckMiddleware` | `users/middleware.py` | Redirects non-superusers if global subscription has expired |
| 14 | `InstitutionContextMiddleware` | `institution/middleware.py` | Attaches `request.institution` for Phase 2 scoping |
| 15 | `SecurityHeadersValidationMiddleware` | `ndas/custom_codes/security_middleware.py` | **Production only** — logs warnings when required security headers are missing |

---

## Security Architecture

### Content Security Policy
- Nonce-based for scripts (`CSP_INCLUDE_NONCE_IN = ['script-src']`)
- Development: allows `'unsafe-inline'` and `'unsafe-eval'` for scripts
- Production: strict — no `'unsafe-inline'`/`'unsafe-eval'` for scripts; `'unsafe-inline'` allowed only for styles
- Admin path excluded from CSP enforcement

### Rate Limiting
All CRUD endpoints are protected with `django-ratelimit`:
- Create/Edit operations: 10 requests/minute (`10/m`)
- Delete operations: 5 requests/minute (`5/m`)
- Login: 5 attempts/minute
- Rate limit violations redirect to `ndas.views.handler_rate_limited`

### Session Security
- Cookie age: 1 hour (`SESSION_COOKIE_AGE = 3600`)
- Expires on browser close (`SESSION_EXPIRE_AT_BROWSER_CLOSE = True`)
- `SESSION_COOKIE_HTTPONLY = True`
- `CSRF_COOKIE_HTTPONLY = True`
- SameSite: `Lax` for both session and CSRF cookies
- Development: `cached_db` session engine; Production: `cache` (Redis)

### Password Validation
- Minimum length: 12 characters
- Max similarity to user attributes: 0.7
- Common password check
- Numeric-only check

### HTTP Method Enforcement
Every view uses either `@require_GET` or `@require_http_methods(["GET", "POST"])`.

### File Upload Security
All uploads validated for:
- Extension against `ALLOWED_FILE_EXTENSIONS` settings
- Size against `FILE_UPLOAD_LIMITS` settings
- MIME type check (executable types blocked)
- Filename sanitization via `sanitize_filename()`

---

## Custom Codes System (`ndas/custom_codes/`)

The `custom_codes/` directory is the shared utility layer. All apps import from here.

| File | Purpose |
|------|---------|
| `Custom_abstract_class.py` | `TimeStampedModel` (created_at, updated_at) and `UserTrackingMixin` (added_by, last_edit_by) abstract base models |
| `choice.py` | All `TextChoices` and tuple-choice constants used in model fields and forms |
| `validators.py` | Field validators (`validate_birth_weight`, `validate_apgar_score`, `validate_video_file`, etc.) and `sanitize_text_input()`, `sanitize_filename()` |
| `sanitization.py` | HTML sanitization using bleach: `sanitize_html()`, `sanitize_plain_text()` |
| `custom_methods.py` | Utilities: `getCountZeroIfNone()`, `calculate_age_string()`, `extract_video_metadata()`, `getPatientList()`, dashboard data helpers, file upload path generators |
| `ndas_enums.py` | `PtStatus` enum for patient filter types |
| `delete_helpers.py` | `has_delete_permission()`, `validate_can_delete()`, `get_entity_warning_items()`, `get_entity_detail_items()`, `get_redirect_url()` |
| `security_middleware.py` | `AdditionalSecurityHeadersMiddleware`, `SecurityHeadersValidationMiddleware` |
| `error_handlers.py` | `@handle_view_errors()` decorator and `@log_and_suppress()` decorator |

---

## Base Model Pattern

Every model in NDAS (except those extending Django's `AbstractUser`) inherits from both abstract base classes:

```python
class MyModel(TimeStampedModel, UserTrackingMixin):
    pass
```

**Fields provided automatically:**

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `created_at` | DateTimeField | `TimeStampedModel` | `auto_now_add=True` |
| `updated_at` | DateTimeField | `TimeStampedModel` | `auto_now=True` |
| `added_by` | ForeignKey → CustomUser | `UserTrackingMixin` | SET_NULL; populated by `UserActivityMiddleware` |
| `last_edit_by` | ForeignKey → CustomUser | `UserTrackingMixin` | SET_NULL; updated by `UserActivityMiddleware` |

`UserActivityMiddleware` automatically populates these fields on every `save()` call within a request context — views do not need to set them manually.

---

## View Pattern

Standard view structure for all CRUD views:

```python
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_http_methods
from django_ratelimit.decorators import ratelimit
from ndas.custom_codes.error_handlers import handle_view_errors

@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='home')
def my_view(request, pk):
    obj = get_object_or_404(MyModel, id=pk)
    related = Related.objects.filter(parent=obj).select_related('added_by')
    return render(request, "app/template.html", {"obj": obj})
```

All views must use `get_object_or_404()` — never `.objects.get()`.

---

## Template Inheritance Hierarchy

```
templates/src/basic_plane.html      # Public pages (login, password reset)
templates/src/base.html             # All authenticated pages
  └── templates/src/navbar.html         # Top navigation bar
  └── templates/src/main_sidebar_menu.html  # Left sidebar nav
  └── templates/src/main_footer.html    # Footer
  └── templates/src/messages.html       # Django messages display
  └── templates/src/partials/delete_confirmation_modal.html  # Universal delete modal
  └── [app]/[action].html              # Page-specific content blocks
```

Template naming convention:
- `manager.html` — list/index views
- `add.html` — create views
- `edit.html` — update views
- `view.html` — detail views

---

## URL Routing Structure

Root `ndas/urls.py` routes to each app:

| Prefix | App | Notes |
|--------|-----|-------|
| `/admin/` | Django admin | |
| `/institution/` | `institution.urls` | Must precede root catch-all |
| `/referral/` | `referral.urls` | Phase 2 |
| `/users/` | `users.urls` | |
| `/reports/` | `reports.urls` | |
| `/problems/` | `problemlist.urls` | |
| `/video/` | `video.urls` | |
| `/` (root) | `patients.urls` | Dashboard, patient CRUD, all assessments, attachments, bookmarks |

Custom error handlers: `handler404`, `handler500` in `ndas/views.py`.

---

## File Upload System

### Size Limits (from `settings.py`)

| Category | Limit | Setting Key |
|---------|-------|-------------|
| Video | 2 GB | `FILE_UPLOAD_LIMITS['VIDEO_MAX_SIZE']` |
| Image | 10 MB | `FILE_UPLOAD_LIMITS['IMAGE_MAX_SIZE']` |
| Document (PDF/DOC) | 100 MB | `FILE_UPLOAD_LIMITS['DOCUMENT_MAX_SIZE']` |
| General attachment | 100 MB | `FILE_UPLOAD_LIMITS['ATTACHMENT_MAX_SIZE']` |
| Profile picture | 5 MB | `FILE_UPLOAD_LIMITS['PROFILE_PICTURE_MAX_SIZE']` |

### Allowed Extensions (from `settings.py`)

| Type | Extensions |
|------|----------|
| Image | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp` |
| Video | `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm` |
| PDF | `.pdf` |
| Document | `.doc`, `.docx`, `.txt`, `.rtf`, `.odt` |

### Storage Paths (Phase 2 institution-aware)

| Upload Type | Path Generator | Result Pattern |
|------------|---------------|----------------|
| Patient videos | `get_institution_video_path()` | `{institution_slug}/videos/{filename}` |
| Patient attachments | `get_institution_attachment_path()` | `{institution_slug}/attachments/{filename}` |
| Institution logos | `get_institution_logo_path()` | `{institution_slug}/logo/{filename}` |
| Videos (Phase 1) | `get_video_path_file_name()` | `videos/{YYYY}/{MM}/{patient_slug}/{filename}` |
| Attachments (Phase 1) | `get_attachment_path_file_name()` | `attachments/{filename}` |

---

## Delete System

The delete system is centralised in `ndas/custom_codes/delete_helpers.py`.

### Permission Check
```python
from ndas.custom_codes.delete_helpers import has_delete_permission, validate_can_delete

if not has_delete_permission(request.user, entity):
    # 403
if not validate_can_delete(entity)['can_delete']:
    # Show reason
```

### Business Rules
- Superusers: can delete any entity
- Staff: can delete their own records (`added_by == request.user`)
- Staff: can always delete own bookmarks
- Videos: cannot be deleted if referenced in any `GMAssessment`
- Users: soft-deleted (deactivated) via `admin_user_delete` view

### Delete Modal
All delete operations use a universal modal partial:
```django
{% load delete_modal_tags %}
{% include 'src/partials/delete_confirmation_modal.html' %}
```

---

## Error Handling

### `@handle_view_errors(redirect_url, error_message, render_template)`

Catches and handles in a consistent way:
- `ObjectDoesNotExist` → logs warning, shows error message, raises Http404
- `ValidationError` → extracts all field errors, logs warning, redirects
- `IntegrityError` → logs error, redirects
- `PermissionDenied` → logs warning, redirects to home
- `Exception` → logs exception with full context, redirects

### `@log_and_suppress(default_return=None)`

For non-critical operations — suppresses exceptions and returns a default value while logging.

---

## Authentication Flow

1. `GET /users/` or `GET /users/login/` → renders login form
2. `POST /users/login/` → Django `authenticate()`, session creation, `UserActivityLog` entry
3. `UserActivityMiddleware` logs login event with IP, device, browser details
4. All protected views use `@login_required(login_url="user-login")`
5. Email verification: token generated via `generate_email_verification_token()`, verified at `/users/verify-email/{token}/`
6. Subscription check: `SubscriptionCheckMiddleware` checks `Subscription.get_global_subscription().is_active` and redirects to subscription expired page if lapsed
7. `GET /users/logout/` → session flush, `UserActivityLog` logout entry

---

## Logging Configuration

| Log | File | Level | Notes |
|-----|------|-------|-------|
| Application | `logs/django.log` | DEBUG (dev), INFO (prod) | Rotating, 15MB × 10 |
| Security | `logs/security.log` | INFO | Production only, rotating |
| Console | stdout | INFO | Development only |

Security events (login attempts, rate limit hits, header violations) go to `logs/security.log`.

---

## Phase 2 Multi-Institution Architecture

### Institution Context
`InstitutionContextMiddleware` attaches `request.institution` on every authenticated request based on session data. Views use this for data scoping.

### Institution-Scoped Manager
`Patient` and referral models use `InstitutionScopedManager` from `institution/managers.py`:
```python
Patient.objects.for_institution(request.institution)
```
Returns all patients when `institution=None` (SUPERADMIN/Phase 1 compatibility).

### Context Processor
`institution.context_processors.institution_context` injects institution data into every template context.

### Data Isolation
All patient data, video files, and attachments are partitioned by institution slug in both the database (via `institution` FK on `Patient`) and the file system (via institution-aware upload path functions).

### Referral System
Cross-institution referrals use dual independent records (`ReferralSent` + `ReferralReceived`) linked by a shared `referral_uuid` (UUID). Neither record has a FK to the other, ensuring independence if one institution is suspended. Patient snapshot (`snapshot_data` JSONField) is captured once at referral submission and is immutable.

Referral lifecycle: `PENDING → REPLIED → CLOSED` (one-way, defined in `ReferralStatus` TextChoices).

In-app notifications are created exclusively via Django signals in `referral/signals.py` and stored in the `Notification` model, scoped to the recipient's institution.
