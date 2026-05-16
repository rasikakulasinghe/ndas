---
project_name: 'NDAS'
user_name: 'Rasika'
date: '2026-05-16'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'quality_rules', 'workflow_rules', 'anti_patterns', 'phase2_multi_institution']
status: 'complete'
rule_count: 112
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

- **Framework:** Django 6.0 (Python 3.13)
- **Database:** SQLite (development) / PostgreSQL (production via env vars)
- **Frontend:** AdminLTE 3.2 + Bootstrap 4.6 + Font Awesome 6.4 — NEVER change versions
- **Dynamic UI:** HTMX (no full-page JS framework; use hx-* attributes in templates)
- **Video Player:** Video.js
- **HTML Sanitization:** bleach 6.3.0
- **PDF Reports:** reportlab 4.4.3
- **Excel Reports:** openpyxl 3.1.5
- **Rate Limiting:** django-ratelimit 4.1.0
- **Content Security Policy:** django-csp 3.8
- **Static Files (prod):** whitenoise 6.9.0
- **Rich Text:** django-ckeditor 6.5.1
- **WSGI Server (prod):** Gunicorn (3 workers, 300s timeout) behind Nginx
- **Cache:** LocMemCache (dev) / Redis (prod via REDIS_URL env var)

**Apps (Phase 1 — operational):** `patients` · `users` · `video` · `reports` · `problemlist`
**Apps (Phase 2 — in development):** `institution` · `referral`

**No new packages planned for Phase 2** — all new capability uses the existing stack.

---

## Critical Implementation Rules

### Language-Specific Rules (Python)

- **All models** must inherit `TimeStampedModel, UserTrackingMixin` — never `models.Model` directly
- **Choices** must be defined in `ndas/custom_codes/choice.py` — never inline in model field definitions
- **Validators** must be added to `ndas/custom_codes/validators.py` — never defined inline or in app files
- **Enumerations** live in `ndas/custom_codes/ndas_enums.py` or `choice.py` — not in app-level files
- **User tracking** (`added_by`, `last_edit_by`) is auto-populated by `UserActivityMiddleware` — never set manually in views
- **Age calculation:** use `calculate_age_string()` from `custom_methods.py`, not custom datetime logic
- **Safe counts:** use `getCountZeroIfNone()` from `custom_methods.py` instead of `.count()` where None is possible
- **Logger:** always `logger = logging.getLogger(__name__)` at module level — never `logging.getLogger("django")` in app code, never inside functions
- **Import order:** stdlib → Django → third-party → local (`custom_codes` first, then app-level)
- **Institution scoping helper:** `institution_scope(request, field='patient__institution')` in `custom_methods.py` returns ORM filter kwargs — use instead of manual `filter(institution=request.institution)` in views. Raises `PermissionDenied` if a non-superuser has `institution_id` set but `request.institution` is `None` (middleware misconfiguration guard added 2026-05-16). Returns `{}` only for genuine Phase 1 / superuser contexts where `institution_id` is also `None`.
- **Dashboard/stats functions require `institution` parameter:** `get_gma_diagnosis_data(institution)`, `get_all_diagnosis_data(institution)`, `get_userStats(institution)`, `get_admissions_data_barchart(institution)` — always pass `request.institution`, never `None`
- **Audit log FK pattern:** when a model records historical state that must survive related-record deletion, use `IntegerField` (not `ForeignKey`) for the historical ID field. Example: `InstitutionSwitchLog.previous_institution_id` is an `IntegerField` — a FK with `SET_NULL` would destroy the historical reference on institution delete.
- **Video edit/delete ownership:** Staff may only modify (`video_edit`, `video_delete_confirm`) videos they personally uploaded (`video.added_by == request.user`). Superusers retain unrestricted access. Never use a bare `is_staff` bypass that removes the ownership check — this was a security defect corrected on 2026-05-16.
- **Patient field names are exact — do not guess:**
  - `patient.bht` (not `bht_number`), `patient.nnc_no` (not `nnc_number`)
  - `patient.baby_name` (not `patient_name` or `name`), `patient.dob_tob` (not `dob` or `date_of_birth`)
  - `patient.pog_wks` / `patient.pog_days` (not `gestational_age_weeks/days`)
  - `patient.birth_weight` (not `birth_weight_g`), `patient.hc` (not `head_circumference`)
  - `patient.apgar_1` / `patient.apgar_5` / `patient.apgar_10` (not `apgar_1_min` / `apgar_5_min` / `apgar_10_min`)

### Framework-Specific Rules (Django)

**Views:**
- All views are **function-based** — no class-based views (CBVs)
- Mandatory decorator stack (in this exact order):
  1. `@login_required(login_url="user-login")`
  2. `@require_http_methods(["GET", "POST"])` or `@require_GET` or `@require_POST`
  3. `@ratelimit(key='user_or_ip', rate='10/m')` for create/edit; `'5/m'` for delete
  4. `@handle_view_errors(redirect_url=..., error_message=...)`
- `userEdit` and `userChangePassword` are now rate-limited at `10/m` (fixed 2026-05-16 — they were previously unthrottled). All user account management views must carry `@ratelimit` without exception.
- **Always** use `get_object_or_404()` — never `Model.objects.get()`
- **Always** use `select_related()` / `prefetch_related()` for queries with related objects
- Redirect on successful POST — never re-render the same template on success
- `@handle_view_errors` with `redirect_url` redirects on error; with `render_template` renders with `{'error': msg}`; neither → redirects to `'home'`. It does NOT re-render forms — handle form re-rendering inside the view before any save that could raise `ValidationError`
- **Admin activity logs:** `admin_activity_logs` view must filter by `user__institution` for non-superuser staff — branch on `request.user.is_superuser`, same pattern as `admin_user_list`. Never return all-institution logs to a plain `is_staff` user.
- **Report temp file ownership:** immediately after generating a report `file_id` in `report_builder`, call `cache.set(f"report_owner_{file_id}_{request.session.session_key}", request.user.pk, 24*3600)`. In `download_report`, retrieve and verify this cache key before serving the file — raise `PermissionDenied` if absent or mismatched. Requires `from django.core.cache import cache` in `reports/views.py`.

**Models:**
- Add `db_index=True` to all filterable/searchable fields
- Define composite indexes in `Meta.indexes` — never rely on single-field indexes alone
- Default `Meta.ordering = ['-created_at']`
- Use `UniqueConstraint` (not deprecated `unique_together`) for multi-field uniqueness
- Never set `abstract = True` unless intentionally creating a base class

**Templates:**
- Extend `'src/base.html'` (authenticated views) or `'src/basic_plane.html'` (public views)
- Template naming: `manager.html` (list), `add.html` (create), `edit.html` (update), `view.html` (detail)
- All templates live in `templates/` (centralised root) — never inside app directories
- Always include `{% csrf_token %}` in every form
- Include `{% include 'src/form_error.html' %}` in all forms for error display
- Use AdminLTE card pattern: `<div class="card"><div class="card-body">...</div></div>`
- Inline `<script>` tags need `nonce="{{ request.csp_nonce }}"` in **all environments** (DEBUG and production). As of 2026-05-16, `'unsafe-inline'` and `'unsafe-eval'` are removed from `CSP_SCRIPT_SRC` in the DEBUG block — nonces are required in development too. Scripts without a nonce silently fail everywhere.
- **Never** change CSS framework or add conflicting CSS libraries

**URLs:**
- URL names: kebab-case (e.g. `patient-manager`, `assessment-add`, `video-delete`)
- Delete views: `@require_POST` only; read-only views: `@require_GET`; forms: `@require_http_methods(["GET", "POST"])`

**Delete System:**
- Always call `has_delete_permission(request.user, entity)` before deleting
- Always call `validate_can_delete(entity)` and check `result['can_delete']`
- Add `{% load delete_modal_tags %}` and include `delete_confirmation_modal.html` in templates
- Videos cannot be deleted if linked to a `GMAssessment` (enforced by `validate_can_delete`)

**File Uploads:**
- Access size limits via `settings.FILE_UPLOAD_LIMITS[...]` — never hardcode sizes
  - Video: `settings.FILE_UPLOAD_LIMITS['VIDEO_MAX_SIZE']` (2 GB)
  - Image: `settings.FILE_UPLOAD_LIMITS['IMAGE_MAX_SIZE']` (10 MB)
  - Document: `settings.FILE_UPLOAD_LIMITS['MAX_FILE_SIZE']` (100 MB)
- Always validate both MIME type AND extension — not just extension
- Use existing path generators — never hardcode `upload_to` strings:
  - Videos → `get_video_path_file_name()`, compressed → `get_compressed_video_path()`, thumbnails → `get_video_thumbnail_path()`
  - Attachments → `get_attachment_path_file_name()`
  - Institution logos → `get_institution_logo_path()`

**Protected Media Serving:**
- In dev, media files are served through `institution/views.py:protected_media_view` which enforces institution isolation: institution-partitioned paths (`/{slug}/videos/`, `/{slug}/attachments/`) are restricted to users whose `request.institution.slug` matches the path slug; SUPERADMIN bypasses this check
- In production, Nginx serves media files directly — the recommended pattern for file isolation is X-Accel-Redirect with a Django auth endpoint
- When adding any new view that serves media files, reference `protected_media_view` as the implementation model — never call `django.views.static.serve` directly without the institution slug-isolation check

**Input Sanitization (use the right one — they are NOT interchangeable):**
- Free-text fields → `sanitize_text_input()` (preserves medical notation like `BP < 120/80`)
- Rich text / CKEditor fields → `sanitize_html()` (bleach, medical-safe tag whitelist)
- File names → `sanitize_filename()` (blocks path traversal, hidden files)
- Search query inputs → `sanitize_search_query()`

**Caching:**
- Atomic check-and-set: use `cache.add(key, value, timeout)` — never `cache.get()` + `cache.set()` together (race condition)

**Video / GMA Coupling:**
- `GMAssessment` URL takes both `<ptid>` (patient ID) and `<fid>` (video/file ID)
- Each `Video` has at most ONE `GMAssessment` (OneToOne) — enforce at model level

### Testing Rules

- **Test runner:** `python manage.py test [app_name]` — standard Django test runner, no pytest
- **Test location:** `tests/` directory within each app (e.g. `patients/tests/test_crud.py`)
- **Run per app:** `patients`, `users`, `video`, `reports`, `problemlist`, `institution`, `referral`
- **Target specific test:** `python manage.py test patients.tests.test_patient_crud.PatientListViewTest.test_method`
- **Test database:** Django creates a temporary SQLite test DB automatically — no manual setup needed
- **Model tests:** use `TestCase` (not `SimpleTestCase`) — requires DB access
- **View tests:** use Django `Client`; always authenticate with `force_login(user)` — not `client.login(username=..., password=...)` which is slower and error-prone
- **Rate-limited views:** disable or mock `@ratelimit` in tests to avoid unexpected 403s
- **File upload tests:** use `SimpleUploadedFile` from `django.core.files.uploadedfile`
- **Static files in template-rendering tests:** wrap test classes with `@override_settings(STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})` — without this, tests that render full templates fail with a staticfiles manifest error
- **`added_by` in test fixtures:** `UserActivityMiddleware` does not run in tests — set `added_by=user` directly in `Model.objects.create()` inside `setUp()`. This is the only context where setting `added_by` manually is correct.
- **Shared setUp:** use a `TestBase(TestCase)` mixin per test module — create superuser, staff_user, and other_staff users as the standard fixture set
- **No coverage enforcement** currently configured — focus on critical path coverage
- **Avoid testing middleware directly** — test view behaviour end-to-end instead
- **Isolation test suite** (`institution/tests/test_isolation.py`) is mandatory before enabling `MULTI_INSTITUTION_ENABLED=True` in production — any cross-institution data leakage is a blocking defect
- **Security test suites (added 2026-05-16):** `reports/tests/test_security.py`, `users/tests/test_security.py`, `video/tests/test_security.py` — cover institution isolation on PDF downloads, ownership checks on video edit/delete, rate limiting on user account views, and report download ownership. Run these when modifying views or permissions in the corresponding apps.

### Code Quality & Style Rules

**Naming Conventions:**
- URL pattern names: kebab-case (`patient-manager`, `video-delete`, `referral-inbox`)
- Template files: `manager.html`, `add.html`, `edit.html`, `view.html`
- Model class names: PascalCase (`GMAssessment`, `ReferralSent`, `Institution`)
- View function names: snake_case (`patient_manager`, `referral_send`, `notification_count`)
- Signal names: snake_case (`referral_received`, `referral_replied`, `referral_closed`)
- Custom utility files: PascalCase for class files (`Custom_abstract_class.py`), snake_case for others

**Custom Codes — Never Duplicate:**
- All shared utilities live exclusively in `ndas/custom_codes/` — never re-implement in app files
- Before writing any helper, check `custom_methods.py`, `validators.py`, `sanitization.py` first
- New Phase 2 utilities that are cross-app (scoping helpers, path generators) go in `custom_codes/` — not in `institution/` or `referral/`

**Secrets & Configuration:**
- All secrets in `.env` — never hardcoded; access via `django.conf.settings`, not `os.environ` directly in views

**Report Generation:**
- PDF: extend `BasePDFGenerator` / assessment subclasses in `reports/utils/pdf_generator.py`
- Excel: use `ExcelReportGenerator` in `reports/utils/excel_generator.py`
- Both use `ReportTemplate` for branding — never hardcode clinic name or logo path

**Medical Domain Constraints:**
- Validation ranges: birth weight 300g–8000g; APGAR 0–10; gestational age 20–44 wks + 0–6 days
- `calculate_age_string()` returns a display string — do not do arithmetic on the result
- Always display all patient identifiers (BHT, NNC, PTC, PC, PIN, Disk No.) — none is the sole display key
- **Patient field alias traps:**
  - `patient.apgar_1` / `patient.apgar_5` / `patient.apgar_10` (not `apgar_1_min`, `apgar_5_min`, `apgar_10_min`)
  - `patient.ofc` (Occipital Frontal Circumference in cm) — distinct from `patient.hc` (Head Circumference); do not conflate
  - `patient.length` (length in cm) — not `height` or `length_cm`

**Institution Display:**
- `Institution.short_name` (max 10 chars) — prefer over `Institution.name` in space-constrained UI slots (nav headers, badges, table cells)

### Development Workflow Rules

**Environment (Windows):**
- Activate venv: `venv\Scripts\activate` | Install: `pip install -r requirements.txt`
- Never commit: `venv/`, `db.sqlite3`, `.env`, `media/`, `logs/`

**Database:**
- After model change: `python manage.py makemigrations [app_name]` then `python manage.py migrate`
- Always specify app name in `makemigrations` — never run bare `makemigrations` across all apps at once
- Phase 2 migration sequence is dependency-ordered: `institution` migrations must run before `referral` migrations

**Middleware Stack — Never Reorder (14 layers):**
1. SecurityMiddleware
2. WhiteNoiseMiddleware
3. CSPMiddleware
4. AdditionalSecurityHeadersMiddleware (custom)
5. SessionMiddleware
6. CommonMiddleware
7. CsrfViewMiddleware
8. AuthenticationMiddleware
9. UserActivityMiddleware (custom — auto-tracks added_by/last_edit_by)
10. MessageMiddleware
11. XFrameOptionsMiddleware
12. UserAgentMiddleware
13. SubscriptionCheckMiddleware (Phase 1 — remains in settings.py during Phase 2 migration)
14. InstitutionContextMiddleware (Phase 2 — always present; passthrough when `MULTI_INSTITUTION_ENABLED=False`)
- `SecurityHeadersValidationMiddleware` is production-only — conditionally loaded
- Any new custom middleware: insert after position 12, before `InstitutionContextMiddleware`

**Security — Never Skip:**
- `{% csrf_token %}` in every form
- Rate limit: all create/edit views at `10/m`, delete views at `5/m`
- Session: 1-hour timeout, expires on browser close

**Deployment:**
- Always run `python manage.py check --deploy` and `collectstatic --noinput` before production deploy
- No new servers or infrastructure per institution — all institutions served by the same Gunicorn + Nginx stack
- **DEBUG CSP script policy (changed 2026-05-16):** `'unsafe-inline'` and `'unsafe-eval'` are removed from `CSP_SCRIPT_SRC` in the DEBUG block. New inline scripts must carry `nonce="{{ request.csp_nonce }}"` in development — you will no longer get a silent pass locally. Test script execution during development before assuming production behaviour.

**App Dependency Order (never create circular imports):**
- `patients` is the root app (`/`) — all other apps depend on it, not vice versa
- `institution` is the Phase 2 foundation — `referral`, `patients`, `users` all depend on it
- `referral` depends on both `institution` and `patients`
- `video.Video` ↔ `patients.GMAssessment` is a critical OneToOne — never break this coupling
- `problemlist` references users via `settings.AUTH_USER_MODEL`, not a direct `User` import

### Critical Anti-Patterns — Never Do These

- ❌ `Model.objects.get(id=pk)` → always `get_object_or_404()`
- ❌ Inline choices in model fields → add to `ndas/custom_codes/choice.py`
- ❌ `entity.delete()` directly in views → use `has_delete_permission()` + `validate_can_delete()` first
- ❌ Setting `added_by` / `last_edit_by` manually in views → auto-handled by `UserActivityMiddleware` (exception: test fixtures in `setUp()` only)
- ❌ Reordering middleware → breaks security, session, and CSP nonce injection
- ❌ Changing Bootstrap/AdminLTE/Font Awesome versions → breaks the entire UI
- ❌ Hardcoding `upload_to` paths → use existing path generator functions
- ❌ Raw SQL in views or models → use Django ORM (aggregations are the only exception)
- ❌ Secrets in source code → always use `.env`
- ❌ New utilities in app files → always extend `ndas/custom_codes/`
- ❌ `logging.getLogger("django")` in app code → always `logging.getLogger(__name__)`
- ❌ `sanitize_text_input()` and `sanitize_html()` used interchangeably → wrong choice causes XSS or strips valid HTML
- ❌ `cache.get()` + `cache.set()` for atomic ops → use `cache.add()` to avoid race conditions
- ❌ `ForeignKey` with `SET_NULL` for audit log "previous state" fields → use `IntegerField` so the historical ID survives the related record's deletion (see `InstitutionSwitchLog.previous_institution_id`)
- ❌ Serving media files from a view without institution slug validation → always follow the `protected_media_view` pattern in `institution/views.py`; never call `django.views.static.serve` directly without the slug-isolation check
- ❌ `client.login(username=..., password=...)` in tests → use `self.client.force_login(user)` — faster and not affected by password hashing
- ❌ Rendering full templates in tests without static override → always decorate test classes with `@override_settings(STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})` to avoid manifest errors
- ❌ Assuming `institution_scope()` returns `{}` safely for all non-superusers → it now raises `PermissionDenied` when a non-superuser has `institution_id` set but `request.institution` is `None`; never swallow this exception — it signals a middleware misconfiguration
- ❌ Staff bypassing video ownership with `is_staff` check → staff may only edit/delete their own uploads; use `request.user.is_superuser` to gate unrestricted access, not `request.user.is_staff`
- ❌ Serving report temp files without ownership verification → always set `cache.set(f"report_owner_{file_id}_{request.session.session_key}", request.user.pk, 24*3600)` at generation time and verify at download time; a UUID alone is not an access control
- ❌ Adding `'unsafe-inline'` or `'unsafe-eval'` to `CSP_SCRIPT_SRC` for any environment → both are removed from the DEBUG block as of 2026-05-16; restoring them (even temporarily) undermines the nonce-based script safety model across all environments

### Phase 2: Multi-Institution Rules

**Feature Flag:**
- `MULTI_INSTITUTION_ENABLED` (env var, default `False`) gates all Phase 2 behaviour
- When `False`, system is fully Phase 1 compatible — no behaviour change
- Do not flip to `True` in production until `institution/tests/test_isolation.py` passes on staging

**Data Isolation — InstitutionScopedManager:**
- All institution-scoped models use `InstitutionScopedManager` as their default manager
- Regular views: always query via `.for_institution(request.institution)` — never raw `.all()` or `.filter(institution=...)`
- SUPERADMIN aggregate views only: may use `.all_institutions()` — never in regular views
- Pattern: `Patient.objects.for_institution(request.institution).select_related(...)`
- `for_institution(None)` returns all records (Phase 1 safe fallback) — not a bug

**Institution Context:**
- `request.institution` set by `InstitutionContextMiddleware` on every request
- ADMIN/USER: resolved from `request.user.institution`
- SUPERADMIN: resolved from `request.session['active_institution_id']`; redirects to `institution:institution-selector` if unset
- Context processor injects into every template: `active_institution`, `user_type`, `is_superadmin`
- ❌ `request.user.institution` in templates → use `active_institution` context variable
- ❌ `{% if request.user.is_superuser %}` in templates → use `{% if is_superadmin %}`

**Institution Model:**
- `Institution.slug` is immutable after creation — enforced in `save()` and `clean()`
- `Institution.short_name` (`CharField(max_length=10, blank=True)`) — prefer over `name` in space-constrained UI slots

**Referral System:**
- `ReferralSent` and `ReferralReceived` have NO FK between them — linked only by `referral_uuid`
- Both must be created atomically via `transaction.atomic()` — either both or neither
- `snapshot_data` JSONField is immutable after referral submission — never update it
- Referral lifecycle: `PENDING → REPLIED → CLOSED` only
- Grace period exemption: `/referral/` URLs remain writable during `GRACE` subscription status

**Notification System:**
- All `Notification.objects.create()` calls live in `referral/signals.py` — never in views
- `referral_status_changed` is a custom signal (not `post_save`) — dispatched manually from the close view
- Signals use try/except + logging — a signal failure must never break the triggering action
- Notification delivery: HTMX polling every 60 seconds on bell icon — no WebSockets

**Performance Gotchas:**
- `patients/models.py` is 2800+ lines — always `select_related('added_by', 'last_edit_by')` in list views to avoid N+1
- Video metadata extraction needs FFmpeg in PATH; falls back to moviepy; returns blank gracefully if neither is available
- After changing subscription status — invalidate related cache keys explicitly

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code in this project
- Follow ALL rules exactly as documented — when in doubt, prefer the more restrictive option
- Check `ndas/custom_codes/` before writing any new utility or helper function
- Check `docs/data-models-main.md` for exact field names before writing any ORM query
- Check `docs/api-contracts-main.md` for existing URL names before defining new routes
- Phase 2 rules apply to all new `institution/` and `referral/` code regardless of `MULTI_INSTITUTION_ENABLED` value
- Update this file if new patterns emerge during implementation

**For Humans:**
- Keep this file lean and focused on agent needs — remove rules that become obvious over time
- Update when technology stack or architectural patterns change
- Review quarterly for outdated rules

_Last Updated: 2026-05-16_
