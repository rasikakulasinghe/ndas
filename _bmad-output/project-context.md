---
project_name: 'NDAS'
user_name: 'Rasika'
date: '2026-02-21'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'quality_rules', 'workflow_rules', 'anti_patterns']
status: 'complete'
rule_count: 67
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

- **Framework:** Django 4.2.16 (Python 3.x)
- **Database:** SQLite (development) / PostgreSQL (production via env vars)
- **Frontend:** AdminLTE 3.2 + Bootstrap 4.6 + Font Awesome 6.4 — NEVER change versions
- **Dynamic UI:** HTMX (no full-page JS framework)
- **Video Player:** Video.js
- **HTML Sanitization:** bleach 6.1.0
- **PDF Reports:** reportlab 4.4.3
- **Excel Reports:** openpyxl 3.1.5
- **Rate Limiting:** django-ratelimit 4.1.0
- **Content Security Policy:** django-csp 3.8
- **Static Files (prod):** whitenoise 6.9.0
- **Rich Text:** django-ckeditor 6.5.1
- **WSGI Server (prod):** Gunicorn (3 workers, 300s timeout) behind Nginx
- **Cache:** LocMemCache (dev) / Redis (prod)

---

## Critical Implementation Rules

### Language-Specific Rules (Python)

- **Import order:** stdlib → Django → third-party → local (`custom_codes` first, then app-level)
- **All models** must inherit `TimeStampedModel, UserTrackingMixin` — never `models.Model` directly
- **Choices** must be defined in `ndas/custom_codes/choice.py`, never inline in model field definitions
- **Validators** must be added to `ndas/custom_codes/validators.py`, never defined inline or in app files
- **Enumerations** (e.g. `PtStatus`) live in `ndas/custom_codes/ndas_enums.py`
- **User tracking** (`added_by`, `last_edit_by`) is auto-populated by `UserActivityMiddleware` — never set manually in views
- **Age calculation:** use `calculate_age_string()` from `custom_methods.py`, not custom datetime logic
- **Safe counts:** use `getCountZeroIfNone()` from `custom_methods.py` instead of `.count()` where None is possible
- **Logger placement:** Always define `logger = logging.getLogger(__name__)` at module level — never inside a function or method. In-function logger assignments shadow the module logger and break log hierarchy.
- **Patient field names are critical** — use exact names only:
  - `patient.bht` (not `bht_number`), `patient.nnc_no` (not `nnc_number`)
  - `patient.baby_name` (not `patient_name` or `name`), `patient.dob_tob` (not `dob` or `date_of_birth`)
  - `patient.pog_wks` / `patient.pog_days` (not `gestational_age_weeks/days`)
  - `patient.birth_weight` (not `birth_weight_g`), `patient.hc` (not `head_circumference`)
  - `patient.apgar_1` / `patient.apgar_5` (not `apgar_1_min` / `apgar_5_min`)

### Framework-Specific Rules (Django)

**Views:**
- All views are **function-based** — no class-based views (CBVs)
- Mandatory decorator stack (in this order):
  1. `@login_required(login_url="user-login")`
  2. `@require_http_methods(["GET", "POST"])` or `@require_GET`
  3. `@ratelimit(key='user_or_ip', rate='10/m')` for create/edit; `'5/m'` for delete
  4. `@handle_view_errors(redirect_url=..., error_message=...)`
- **Always** use `get_object_or_404()` — never `Model.objects.get()`
- **Always** use `select_related()` / `prefetch_related()` for queries with related objects
- Redirect on successful POST — never re-render on success

**Models:**
- Add `db_index=True` to all filterable/searchable fields
- Define composite indexes in `Meta.indexes` — never rely on single-field indexes alone
- Default `Meta.ordering = ['-created_at']`
- Use `UniqueConstraint` (not `unique_together`) for multi-field uniqueness
- Never use `abstract = True` unless intentionally creating a base class

**Templates:**
- Extend `'src/base.html'` (authenticated views) or `'src/basic_plane.html'` (public views)
- Template naming: `manager.html` (list), `add.html` (create), `edit.html` (update), `view.html` (detail)
- All templates live in `templates/` (centralised) — never inside app directories
- Always include `{% csrf_token %}` in every form
- Include `{% include 'src/form_error.html' %}` in all forms for error display
- Use AdminLTE card pattern: `<div class="card"><div class="card-body">...</div></div>`
- **Never** change CSS framework (AdminLTE 3.2 + Bootstrap 4.6) or add conflicting CSS libraries

**URLs:**
- URL names follow kebab-case: `patient-manager`, `assessment-add`, `video-delete`
- Delete views accept only POST — use `@require_POST` (shorthand). Use `@require_GET` for read-only views, `@require_http_methods(["GET", "POST"])` for standard form views.

**Delete System:**
- Always call `has_delete_permission(request.user, entity)` before deleting
- Always call `validate_can_delete(entity)` and check `result['can_delete']`
- Add `{% load delete_modal_tags %}` and include `delete_confirmation_modal.html` in templates
- Videos cannot be deleted if linked to a `GMAssessment` (enforced by `validate_can_delete`)

**Video / GMA Coupling:**
- `GMAssessment` takes both `<ptid>` (patient ID) and `<fid>` (video/file ID) in its URL
- Each `Video` has at most ONE `GMAssessment` (OneToOne) — enforce at model level

### Testing Rules

- **Test runner:** `python manage.py test [app_name]` — standard Django test runner, no pytest
- **Test file location:** `tests/` directory within each app or `test_*.py` files at app root
- **Test per app:** run isolated — `patients`, `users`, `video`, `reports`, `problemlist`
- **Specific test targeting:** `python manage.py test patients.tests.PatientModelTest.test_method_name`
- **Test database:** Django creates a temporary SQLite test DB automatically — no manual setup needed
- **Model tests:** use `TestCase` (not `SimpleTestCase`) — requires DB access
- **View tests:** use Django `Client` or `RequestFactory`; always log in before testing protected views
- **Rate-limited views:** disable or mock `@ratelimit` in tests to avoid 403s from rate limiting
- **File upload tests:** use `SimpleUploadedFile` from `django.core.files.uploadedfile`
- **No coverage enforcement** currently configured — focus on critical path coverage
- **Avoid testing middleware directly** — test view behaviour end-to-end instead

### Code Quality & Style Rules

**Naming Conventions:**
- URL pattern names: kebab-case (e.g. `patient-manager`, `video-delete`)
- Template files: `manager.html`, `add.html`, `edit.html`, `view.html`
- Model class names: `PascalCase` (e.g. `GMAssessment`, `VideoManager`)
- View function names: `snake_case` (e.g. `patient_manager`, `assessment_add`)
- Custom utility files: `PascalCase` for class files (e.g. `Custom_abstract_class.py`), `snake_case` for others

**Custom Codes — Never Duplicate:**
- All shared utilities live exclusively in `ndas/custom_codes/` — never re-implement in app files
- Before writing any helper, check `custom_methods.py`, `validators.py`, `sanitization.py` first

**Input Sanitization (context-specific — use the right one):**
- Free-text fields → `sanitize_text_input()` (preserves medical notation like `BP < 120/80`)
- Rich text / CKEditor fields → `sanitize_html()` (bleach, medical-safe tag whitelist)
- File names → `sanitize_filename()` (blocks path traversal, hidden files)
- Search query inputs → `sanitize_search_query()` (strips HTML + injection chars)

**File Upload Limits (access via settings, never hardcode):**
- Video: 2 GB → `settings.FILE_UPLOAD_LIMITS['VIDEO_MAX_SIZE']`
- Image: 10 MB → `settings.FILE_UPLOAD_LIMITS['IMAGE_MAX_SIZE']`
- Document: 100 MB → `settings.FILE_UPLOAD_LIMITS['MAX_FILE_SIZE']`
- Always validate MIME type (not just extension) using validators from `validators.py`

**File Path Generators (never hardcode upload paths):**
- Videos → `get_video_path_file_name()`, compressed → `get_compressed_video_path()`, thumbnails → `get_video_thumbnail_path()`
- Attachments → `get_attachment_path_file_name()`
- All paths follow `YYYY/MM/patient_name/filename_timestamp.ext` pattern

**Caching:**
- **Atomic cache check-and-set:** Use `cache.add(key, value, timeout)` for atomic "set if not exists" (e.g. throttling in middleware). Never use `cache.get()` + `cache.set()` together — it creates a race condition under concurrent requests.

**Secrets & Configuration:**
- All secrets in `.env` — never hardcoded; access via `django.conf.settings`, not `os.environ` in views

### Development Workflow Rules

**Environment (Windows):**
- Activate: `venv\Scripts\activate` | Install: `pip install -r requirements.txt`
- Never commit: `venv/`, `db.sqlite3`, `.env`, `media/`, `logs/`

**Database:**
- After model change: `python manage.py makemigrations [app_name]` then `python manage.py migrate`
- Always specify app name in `makemigrations` — never run bare `makemigrations` across multiple apps

**Middleware Stack — Never Reorder:**
- The 13-layer stack in `ndas/settings.py` is order-critical — see `docs/architecture.md`
- New middleware: insert after position 12 (`UserAgentMiddleware`), before `SubscriptionCheckMiddleware`
- `SecurityHeadersValidationMiddleware` is production-only — conditionally loaded

**Security — Never Skip:**
- `{% csrf_token %}` in every form; rate limit all create/edit at `10/m`, delete at `5/m`
- Session: 1-hour timeout, expires on browser close

**Deployment:**
- Always run `python manage.py check --deploy` and `collectstatic --noinput` before production deploy

**Report Generation:**
- PDF: extend `BasePDFGenerator` / assessment subclasses in `reports/utils/pdf_generator.py`
- Excel: use `ExcelReportGenerator` in `reports/utils/excel_generator.py`
- Both use `ReportTemplate` for branding — never hardcode clinic details

### Critical Don't-Miss Rules

**Anti-Patterns — Never Do These:**
- ❌ `Model.objects.get(id=pk)` → always `get_object_or_404()`
- ❌ Inline choices in model fields → add to `ndas/custom_codes/choice.py`
- ❌ `entity.delete()` in views → use `has_delete_permission()` + `validate_can_delete()` first
- ❌ Setting `added_by` / `last_edit_by` manually → auto-handled by `UserActivityMiddleware`
- ❌ Reordering middleware → breaks security, session, CSP nonce injection
- ❌ Changing Bootstrap/AdminLTE/Font Awesome versions → breaks the entire UI
- ❌ Hardcoding `upload_to` paths → use existing path generator functions
- ❌ Raw SQL → use Django ORM (aggregations are the only exception)
- ❌ Secrets in source code → always use `.env`
- ❌ New utilities in app files → always extend `ndas/custom_codes/`

**Security Gotchas:**
- Inline scripts need `nonce="{{ request.csp_nonce }}"` — CSP nonce injected by `CSPMiddleware`
- `SubscriptionCheckMiddleware` blocks ALL views if `Subscription.status != 'active'`
- File upload: MIME type AND extension must both pass — not just extension
- `sanitize_text_input()` is NOT interchangeable with `sanitize_html()` — wrong choice causes XSS or strips valid HTML

**Medical Domain Gotchas:**
- Validation ranges: birth weight 300g–8000g; APGAR 0–10; gestational age 20–44 wks + 0–6 days
- `calculate_age_string()` returns a display string — do not do arithmetic on the result
- Always display all identifiers (BHT, NNC, PTC, PC, PIN, Disk No.) — none is the sole display key

**Performance Gotchas:**
- `patients/models.py` is 2800+ lines — always `select_related('added_by', 'last_edit_by')` in list views to avoid N+1
- After changing `Subscription.status` — invalidate cache explicitly
- Video metadata extraction needs FFmpeg in PATH; falls back to moviepy; returns blank gracefully if neither available

**App Dependency Rules:**
- `patients` is the root app (`/`) — all others depend on it, not vice versa
- `video.Video` ↔ `patients.GMAssessment` is a critical OneToOne — never break this coupling
- `problemlist.ProblemAction` → use `settings.AUTH_USER_MODEL`, not a direct `User` import

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code in this project
- Follow ALL rules exactly as documented — when in doubt, prefer the more restrictive option
- Check `ndas/custom_codes/` before writing any new utility or helper
- Update this file if new patterns emerge during implementation

**For Humans:**
- Keep this file lean and focused on agent needs — remove rules that become obvious over time
- Update when technology stack or patterns change
- Review quarterly for outdated rules

_Last Updated: 2026-02-21_
