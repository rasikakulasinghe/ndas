---
project_name: 'NDAS'
user_name: 'Rasika'
date: '2026-03-05'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'quality_rules', 'workflow_rules', 'anti_patterns', 'phase2_multi_institution']
status: 'complete'
rule_count: 88
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

**Apps (Phase 1):** `patients` · `users` · `video` · `reports` · `problemlist`
**Apps (Phase 2 additions):** `institution` · `referral`

---

## Critical Implementation Rules

### Language-Specific Rules (Python)

- **Import order:** stdlib → Django → third-party → local (`custom_codes` first, then app-level)
- **All models** must inherit `TimeStampedModel, UserTrackingMixin` — never `models.Model` directly
- **Choices** must be defined in `ndas/custom_codes/choice.py`, never inline in model field definitions
- **Validators** must be added to `ndas/custom_codes/validators.py`, never defined inline or in app files
- **Enumerations** (e.g. `PtStatus`, `UserType`, `ReferralStatus`) live in `ndas/custom_codes/ndas_enums.py` or `choice.py`
- **User tracking** (`added_by`, `last_edit_by`) is auto-populated by `UserActivityMiddleware` — never set manually in views
- **Age calculation:** use `calculate_age_string()` from `custom_methods.py`, not custom datetime logic
- **Safe counts:** use `getCountZeroIfNone()` from `custom_methods.py` instead of `.count()` where None is possible
- **Logger placement:** Always define `logger = logging.getLogger(__name__)` at module level — never inside a function or method
- **Institution scoping helper:** `institution_scope(request, field='patient__institution')` in `custom_methods.py` — returns ORM filter kwargs `{field: inst}` when `request.institution` is set, `{}` in Phase 1 (institution is None). Use this in views needing flexible scoping without the full `InstitutionScopedManager` chain (e.g. cross-model queries). Never write manual `filter(institution=request.institution)` in views.
- **Dashboard/stats functions require `institution` parameter:** `get_gma_diagnosis_data(institution)`, `get_all_diagnosis_data(institution)`, `get_userStats(institution)`, `get_admissions_data_barchart(institution)` — always pass `request.institution` from views, not `None`.
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

**`@handle_view_errors` Behaviour (ValidationError):**
- `redirect_url` set → redirects there (most common)
- `render_template` set → renders template with `{'error': error_msg}`
- Neither set → redirects to `'home'`
- Does NOT re-call the view to re-render forms — handle form re-rendering inside the view before any save that could raise ValidationError

**URLs:**
- URL names follow kebab-case: `patient-manager`, `assessment-add`, `video-delete`
- Delete views accept only POST — use `@require_POST`. Read-only views use `@require_GET`. Standard form views use `@require_http_methods(["GET", "POST"])`.

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
- **Test per app:** run isolated — `patients`, `users`, `video`, `reports`, `problemlist`, `institution`, `referral`
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
- Institution logos → `get_institution_logo_path()` (from `validators.py`)
- All paths follow `YYYY/MM/patient_name/filename_timestamp.ext` pattern

**Caching:**
- **Atomic cache check-and-set:** Use `cache.add(key, value, timeout)` for atomic "set if not exists" (e.g. throttling in middleware). Never use `cache.get()` + `cache.set()` together — it creates a race condition.

**Secrets & Configuration:**
- All secrets in `.env` — never hardcoded; access via `django.conf.settings`, not `os.environ` in views

### Development Workflow Rules

**Environment (Windows):**
- Activate: `venv\Scripts\activate` | Install: `pip install -r requirements.txt`
- Never commit: `venv/`, `db.sqlite3`, `.env`, `media/`, `logs/`

**Database:**
- After model change: `python manage.py makemigrations [app_name]` then `python manage.py migrate`
- Always specify app name in `makemigrations` — never run bare `makemigrations` across multiple apps

**Middleware Stack — Never Reorder (14 layers):**
1. SecurityMiddleware
2. WhiteNoiseMiddleware
3. CSPMiddleware
4. AdditionalSecurityHeadersMiddleware (custom)
5. SessionMiddleware
6. CommonMiddleware
7. CsrfViewMiddleware
8. AuthenticationMiddleware
9. UserActivityMiddleware (custom)
10. MessageMiddleware
11. XFrameOptionsMiddleware
12. UserAgentMiddleware
13. SubscriptionCheckMiddleware (Phase 1) / `InstitutionContextMiddleware` (Phase 2 — position 14)
14. `InstitutionContextMiddleware` (always present; acts as Phase1 passthrough when `MULTI_INSTITUTION_ENABLED=False`)
- `SecurityHeadersValidationMiddleware` is production-only — conditionally loaded
- New middleware: insert after position 12 (`UserAgentMiddleware`), before `InstitutionContextMiddleware`

**Security — Never Skip:**
- `{% csrf_token %}` in every form; rate limit all create/edit at `10/m`, delete at `5/m`
- Session: 1-hour timeout, expires on browser close

**Deployment:**
- Always run `python manage.py check --deploy` and `collectstatic --noinput` before production deploy

**Report Generation:**
- PDF: extend `BasePDFGenerator` / assessment subclasses in `reports/utils/pdf_generator.py`
- Excel: use `ExcelReportGenerator` in `reports/utils/excel_generator.py`
- Both use `ReportTemplate` for branding — never hardcode clinic details

---

## Phase 2: Multi-Institution Rules

### Feature Flag

- `MULTI_INSTITUTION_ENABLED` (env var, default `False`) controls Phase 2 behaviour
- All Phase 2 code paths must check `settings.MULTI_INSTITUTION_ENABLED` or be gated by `InstitutionContextMiddleware`'s mode
- When `False`, system behaves identically to Phase 1 (backward compatible)

### Data Isolation — InstitutionScopedManager

- **All institution-scoped models** use `InstitutionScopedManager` as their default manager
- **ALWAYS** query scoped models via `.for_institution(request.institution)` in regular views — never raw `.all()` or `.filter(institution=...)`
- **SUPERADMIN aggregate views only** may use `.all_institutions()` — never call this in regular views
- Pattern: `Patient.objects.for_institution(request.institution).select_related(...)`
- If `request.institution` is `None` (transitional Phase 1 → Phase 2 migration state), `for_institution(None)` returns all records (safe fallback)

### User Roles (UserType choices)

- `UserType.USER` — Clinician; scoped to own institution
- `UserType.ADMIN` — Institution Admin; manages own institution's users and settings
- `UserType.SUPERADMIN` — Platform-level; `is_superuser=True`; context-switches across institutions via session
- Check role in views/templates via: `request.user.user_type` or template vars `is_superadmin`, `user_type`
- **NEVER** use `request.user.is_superuser` in templates — use `is_superadmin` context variable instead (breaks SUPERADMIN context switching)
- **NEVER** use `request.user.institution` in templates — use `active_institution` context variable instead

### Institution Context (request.institution)

- `request.institution` is set by `InstitutionContextMiddleware` on every request
- For SUPERADMIN: resolved from `request.session['active_institution_id']`; redirects to `institution:institution-selector` if not set
- For ADMIN/USER: resolved from `request.user.institution`
- Context processors (`institution.context_processors.institution_context`) inject into every template: `active_institution`, `user_type`, `is_superadmin`

### Institution Model Rules

- `Institution.slug` is **immutable** — cannot be changed after creation (enforced in `save()` and `clean()`)
- `Institution.short_name` — `CharField(max_length=10, blank=True)` — used for sidebar/badge display in constrained UI spaces. Prefer `short_name` if set, fall back to `name`. Included in `SuperadminInstitutionEditForm` automatically.
- Institution logo path uses `get_institution_logo_path()` — never set `upload_to` inline
- `InstitutionContextMiddleware` (position 14) replaces `SubscriptionCheckMiddleware` in Phase 2; both coexist in `settings.py` for migration safety

### Referral System Rules

- `ReferralSent` (owned by sending institution) and `ReferralReceived` (owned by receiving institution) are **independent records with NO FK between them**
- They are linked only by `referral_uuid` (UUID field, same value on both, generated once from `ReferralSent`, copied to `ReferralReceived`)
- Both records must be created **atomically** using `transaction.atomic()` — either both succeed or neither is created
- `snapshot_data` JSONField is **immutable** after creation — never update it after the referral is submitted
- `ReferralMessage.referral_uuid` links to both records without a direct FK — this is intentional
- Referral lifecycle: `PENDING → REPLIED → CLOSED` (ReferralStatus choices)
- Grace period exemption: `/referral/` URLs are exempt from write-blocking during `GRACE` subscription status — active referrals continue to completion

### Notification System Rules

- **All `Notification.objects.create()` calls must live in `referral/signals.py`** — never in views or elsewhere
- Signals use try/except with logging so a signal failure never breaks the triggering action
- `referral_status_changed` is a **custom signal** (not `post_save`) — dispatched manually from the close view because bulk updates skip `post_save`
- `Notification` uses `InstitutionScopedManager` — always query via `.for_institution(request.institution)`
- Notification bell / panel uses **HTMX polling** — no WebSockets

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
- ❌ Using `Model.objects.all()` or `.filter(institution=...)` on institution-scoped models → use `.for_institution(request.institution)`
- ❌ Calling `get_gma_diagnosis_data()` / `get_all_diagnosis_data()` / `get_userStats()` / `get_admissions_data_barchart()` without `institution` argument → always pass `request.institution`
- ❌ Manual `filter(institution=request.institution)` in views where `institution_scope()` or `InstitutionScopedManager` applies → use the appropriate scoping utility
- ❌ `logging.getLogger("django")` in app views → always `logging.getLogger(__name__)`
- ❌ `request.user.institution` in templates → use `active_institution` context variable
- ❌ `{% if request.user.is_superuser %}` in templates → use `{% if is_superadmin %}`
- ❌ `Notification.objects.create()` in views → all notifications must go through `referral/signals.py`
- ❌ Modifying `snapshot_data` after referral creation → it is immutable

**Security Gotchas:**
- Inline scripts need `nonce="{{ request.csp_nonce }}"` — CSP nonce injected by `CSPMiddleware`
- `InstitutionContextMiddleware` (Phase 2) or `SubscriptionCheckMiddleware` (Phase 1) blocks ALL views on expired/grace subscriptions
- File upload: MIME type AND extension must both pass — not just extension
- `sanitize_text_input()` is NOT interchangeable with `sanitize_html()` — wrong choice causes XSS or strips valid HTML

**Medical Domain Gotchas:**
- Validation ranges: birth weight 300g–8000g; APGAR 0–10; gestational age 20–44 wks + 0–6 days
- `calculate_age_string()` returns a display string — do not do arithmetic on the result
- Always display all identifiers (BHT, NNC, PTC, PC, PIN, Disk No.) — none is the sole display key

**Performance Gotchas:**
- `patients/models.py` is 2800+ lines — always `select_related('added_by', 'last_edit_by')` in list views to avoid N+1
- After changing `Subscription.status` or `Institution.subscription_status` — invalidate cache explicitly
- Video metadata extraction needs FFmpeg in PATH; falls back to moviepy; returns blank gracefully if neither available

**App Dependency Rules:**
- `patients` is the root app (`/`) — all others depend on it, not vice versa
- `institution` is a foundation app — `referral`, `patients`, `users` all depend on it
- `video.Video` ↔ `patients.GMAssessment` is a critical OneToOne — never break this coupling
- `problemlist.ProblemAction` → use `settings.AUTH_USER_MODEL`, not a direct `User` import
- `referral` depends on `institution` and `patients` — never create circular imports

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code in this project
- Follow ALL rules exactly as documented — when in doubt, prefer the more restrictive option
- Check `ndas/custom_codes/` before writing any new utility or helper
- Update this file if new patterns emerge during implementation
- Phase 2 rules apply to ALL new institution/referral code regardless of `MULTI_INSTITUTION_ENABLED`

**For Humans:**
- Keep this file lean and focused on agent needs — remove rules that become obvious over time
- Update when technology stack or patterns change
- Review quarterly for outdated rules

_Last Updated: 2026-03-05_
