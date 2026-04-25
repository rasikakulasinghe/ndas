---
stepsCompleted:
  - step-01-init
  - step-02-context
  - step-03-starter
  - step-04-decisions
  - step-05-patterns
  - step-06-structure
  - step-07-validation
  - step-08-complete
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/project-context.md
  - docs/index.md
  - docs/architecture.md
workflowType: 'architecture'
workflowStatus: complete
lastStep: 8
completedAt: '2026-04-25'
project_name: NDAS
user_name: Rasika
date: '2026-04-25'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
58 FRs across 14 capability areas spanning three phases. Phase 1 (FR1–FR31) is fully operational — patient records, five assessment workflows, video management, reports, problem list, user management. Phase 2 (FR32–FR51) is implemented and pending stabilisation — multi-institution isolation, referral system, notifications, patient transfer. Phase 3 (FR56–FR58) is planned — AI-assisted GMA classification and structured data clinical suggestions. Cross-cutting audit trail FRs (FR52–FR55) apply to all phases.

**Non-Functional Requirements:**
23 NFRs across 7 categories. Architecturally significant: data isolation absolute constraint (NFR13 — zero leakage between institutions), immutable referral snapshots (NFR14), atomic dual-record creation (NFR15), video upload with real-time progress and no silent failures (NFR17), ≥10 institutions at ≥500 cases/month without >10% performance degradation (NFR18), notification delivery within 120 seconds (NFR6), CSP on every response with nonce-based inline scripts (NFR8), rate limiting on all 24 CRUD ops (NFR10).

**Scale & Complexity:**
- Primary domain: Healthcare Web Application — Django MVT Monolith + HTMX
- Complexity level: High
- Project context: Brownfield — Phase 1 operational, Phase 2 implemented, Phase 3 planned
- Estimated architectural components: 7 Django apps + shared custom_codes layer + 14-layer middleware stack + Phase 3 AI pipeline (TBD)

### Technical Constraints & Dependencies

- **Stack is frozen for Phase 2:** Django 4.2.16, AdminLTE 3.2 + Bootstrap 4.6 + Font Awesome 6.4, HTMX, Video.js — no new packages permitted for Phase 2; all capability uses existing stack
- **Deployment flexibility:** must support on-premise hospital servers and cloud without architectural changes; all env-specific config via environment variables only
- **Database:** SQLite (dev) / PostgreSQL (prod) — ORM-level portability required; no raw SQL in views or models (aggregations excepted)
- **Video constraints:** up to 2GB files, HTTP range requests required for Video.js seek, Gunicorn 300s timeout must accommodate large uploads
- **Windows dev / Linux prod:** path handling, file operations, and shell commands must account for environment differences
- **No external integrations in Phase 1/2:** standalone system; data model identifiers (BHT, NNC, etc.) designed for future HIS integration without model changes
- **Phase 3 dependency:** AI pipeline requires accumulated training data from Phase 1/2 clinical use before model training can begin

### Cross-Cutting Concerns Identified

1. **Institution-scoped data isolation** — every data query in Phase 2 views must route through `InstitutionScopedManager.for_institution(request.institution)`; applies to Patient, Video, Attachment, Referral, Notification models
2. **Audit trail via middleware** — `UserActivityMiddleware` auto-populates `added_by` / `last_edit_by` on all model saves; never set manually in views; logs all create/edit/delete
3. **Rate limiting** — all 24 CRUD operations protected; create/edit at 10/m, delete at 5/m; must be accounted for in test setup (mock or bypass in tests)
4. **CSP nonce injection** — all inline `<script>` tags require `nonce="{{ request.csp_nonce }}"`; missing nonces cause silent script failures in production
5. **Feature flag gating** — `MULTI_INSTITUTION_ENABLED` env var separates Phase 1 and Phase 2 behaviour; Phase 1 fallback must remain fully functional when flag is False
6. **Phase 3 data readiness** — schema decisions for assessment fields and video metadata storage made in Phase 1/2 directly constrain Phase 3 AI training pipeline design

## Starter Template Evaluation

### Primary Technology Domain

Django MVT Monolith — Server-rendered Multi-Page Application with HTMX partials. Identified from existing brownfield project structure and project context rules.

### Starter Options Considered

Not applicable — NDAS is a brownfield project. The existing Django scaffold established at project creation serves as the technical foundation. No new project initialisation is required.

### Established Foundation: Django 4.2.16 Monolith

**Rationale:**
The project was initialised as a Django MVT monolith appropriate for a clinical system where server-side rendering provides security (no client-side data exposure), reliability (no hydration failures), and developer familiarity. HTMX provides dynamic interaction without a JavaScript framework, keeping the stack minimal and maintainable by a small clinical software team.

**Initialization Command:** N/A — project already exists.

**Architectural Decisions Established by Foundation:**

**Language & Runtime:**
Python 3.x with Django 4.2.16 LTS. Type safety enforced by convention and code review, not a type checker. No async views — all views are synchronous FBVs.

**Styling Solution:**
AdminLTE 3.2 + Bootstrap 4.6 + Font Awesome 6.4. Versions are frozen — no upgrades, no additional CSS frameworks. All templates use Bootstrap grid for responsive layout.

**Build Tooling:**
WhiteNoise 6.9.0 for production static file serving. No Webpack, Vite, or bundler — static files are served directly. `collectstatic --noinput` before each production deploy.

**Testing Framework:**
Django built-in test runner (`python manage.py test [app_name]`). TestCase for all model/view tests (DB access required). No pytest. No coverage enforcement currently.

**Code Organisation:**
7 Django apps (`patients`, `users`, `video`, `reports`, `problemlist`, `institution`, `referral`) + `ndas/custom_codes/` shared utility layer. Templates centralised in root `templates/` directory — never inside app directories. All choices, validators, sanitizers, and utilities live exclusively in `custom_codes/`.

**Development Experience:**
Django dev server (`python manage.py runserver`). Windows venv activation: `venv\Scripts\activate`. No hot module replacement — full page reload on change.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Institution-scoped data isolation via `InstitutionScopedManager` — enforced on all Phase 2 queries
- Atomic dual-record referral creation via `transaction.atomic()` — either both records created or neither
- Immutable referral snapshot — `snapshot_data` JSONField written once, never updated
- Phase 2 production go-live gates — must all pass before `MULTI_INSTITUTION_ENABLED=True`

**Important Decisions (Shape Architecture):**
- Phase 3 AI integration as a separate microservice — Django monolith untouched; AI service communicates via internal HTTP
- PostgreSQL connection persistence via `CONN_MAX_AGE` — zero infrastructure cost, sufficient for current scale
- CI/CD — manual deploys maintained for now; revisit when team grows or deploy frequency increases

**Deferred Decisions (Post-Phase 2 Stabilisation):**
- PgBouncer connection pooling — defer until actual connection saturation observed at scale
- Phase 3 ML framework selection (PyTorch vs TensorFlow) — deferred to Phase 3 start
- Phase 3 video processing pipeline details — deferred; requires video quality standards definition first

---

### Data Architecture

| Decision | Choice | Rationale |
|---|---|---|
| Primary database | PostgreSQL (prod) / SQLite (dev) | ORM portability; env-var switched; no raw SQL |
| ORM | Django ORM exclusively | Raw SQL only for aggregations; never in views or models |
| Base model | `TimeStampedModel + UserTrackingMixin` | All models inherit both; auto-provides created_at, updated_at, added_by, last_edit_by |
| Migrations | Django migrations, per-app | `makemigrations [app_name]` always — never bare; institution before referral |
| Cache | LocMemCache (dev) / Redis (prod) | Redis via `REDIS_URL` env var; atomic ops use `cache.add()` not get+set |
| Data isolation | `InstitutionScopedManager.for_institution(request.institution)` | All Phase 2 scoped queries; `.all_institutions()` superadmin only |
| Connection pooling | Django `CONN_MAX_AGE` persistent connections | Zero infrastructure cost; sufficient for ≥10 institutions at current Gunicorn worker count |
| Indexes | `db_index=True` on all filterable fields; `Meta.indexes` for composites | N+1 query patterns are blocking defects |

---

### Authentication & Security

| Decision | Choice | Rationale |
|---|---|---|
| Authentication | Django built-in auth + `CustomUser` | Sessions, not tokens; clinical system with server-rendered pages |
| Password hashing | PBKDF2+SHA256 (Django default) | No plaintext or reversible storage anywhere |
| Password policy | Min 12 chars, max similarity 0.7, common password check | Enforced by Django validators in settings |
| Session | 1-hour inactivity timeout, browser-close expiry | Shared clinical workstations; `cached_db` (dev) / `cache` Redis (prod) |
| Rate limiting | django-ratelimit 4.1.0 — create/edit 10/m, delete 5/m, key=user_or_ip | 24 CRUD ops protected; bypass in tests |
| CSP | django-csp 3.8, nonce-based for scripts | All inline `<script>` require `nonce="{{ request.csp_nonce }}"` or silently fail in prod |
| Input sanitisation | `sanitize_text_input()` (free text), `sanitize_html()` (rich text), `sanitize_filename()` (uploads) | Not interchangeable — wrong choice causes XSS or strips valid HTML |
| File validation | MIME type + extension + size checked before storage | Executable MIME types blocked; size limits from `settings.FILE_UPLOAD_LIMITS` |
| Middleware order | 14-layer stack — order fixed, never reorder | `UserActivityMiddleware` must follow `AuthenticationMiddleware`; CSP before session |

---

### API & Communication Patterns

| Decision | Choice | Rationale |
|---|---|---|
| Primary pattern | Django server-rendered HTML (MVT) | No API layer; clinical reliability over client-side interactivity |
| Dynamic interaction | HTMX partial updates only | Notification badge, dynamic form sections — not full-page HTMX navigation |
| No REST/GraphQL API | N/A for Phase 1/2 | All data access is view-driven; Phase 3 AI service will have its own internal contract |
| Error handling | `@handle_view_errors(redirect_url, error_message)` decorator | Catches ObjectDoesNotExist, ValidationError, IntegrityError, PermissionDenied consistently |
| Cross-institution comms | Referral dual-record pattern within same monolith | No inter-service calls; both institutions served by same Django process |
| Notification delivery | HTMX polling every 60 seconds on bell icon | No WebSockets; ≤120-second end-to-end delivery target |

---

### Frontend Architecture

| Decision | Choice | Rationale |
|---|---|---|
| UI framework | AdminLTE 3.2 + Bootstrap 4.6 + Font Awesome 6.4 | Frozen — no version upgrades, no additional CSS libraries |
| Dynamic UI | HTMX | No SPA, no React/Vue/Angular; targeted partial updates only |
| Video playback | Video.js | Embedded player; HTTP range requests required for seek; first frame ≤5s |
| State management | None (server-side session) | All state in Django session and DB; no client-side store |
| Responsive layout | Bootstrap grid — all templates use column classes | Primary desktop; secondary mobile/tablet |
| Script safety | All `<script>` tags need `nonce="{{ request.csp_nonce }}"` | Missing nonce = silent failure in production |

---

### Infrastructure & Deployment

| Decision | Choice | Rationale |
|---|---|---|
| WSGI server | Gunicorn (3 workers, 300s timeout) | 300s timeout accommodates large video uploads |
| Reverse proxy | Nginx | SSL termination, HTTP range request support for video streaming |
| Static files | WhiteNoise 6.9.0 | Serve compressed static files directly from Django; `collectstatic --noinput` before deploy |
| Environment config | `.env` / environment variables exclusively | No secrets in source; `django.conf.settings` access in code, never `os.environ` directly |
| Deployment flexibility | On-premise or cloud, same codebase | All env-specific config via env vars; no architecture changes between targets |
| CI/CD | Manual deploys (current) | Sufficient for current team size and deploy frequency; revisit when team grows |
| Logging | Rotating file logs (`logs/django.log`, `logs/security.log`) | 15MB × 10 retention; security events to dedicated log; production-only security log |
| Monitoring | None currently configured | To be defined; Phase 2 go-live a natural trigger for adding uptime monitoring |

---

### Phase 3 AI Integration Architecture

**Decision: Separate AI Microservice**

When Phase 3 development begins, the AI/ML capability will be implemented as a separate Python service (FastAPI or Flask) running independently of the Django monolith.

**Integration contract:**
- Django calls the AI service via internal HTTP after an assessment is saved (asynchronous — does not block the Django request)
- AI service returns inference results; Django stores them and surfaces in the assessment view
- Training pipeline reads directly from the PostgreSQL database or an exported dataset — no Django involvement in training
- AI service deployed independently; model updates do not require Django redeploy

**Rationale:** Keeps the Django monolith stable and unchanged. AI team can use PyTorch or TensorFlow independently. Memory-intensive model loading does not pressure Gunicorn workers. Inference failures do not crash clinical views.

**Phase 3 data readiness requirements (must be in place before Phase 3 starts):**
- All assessment field values stored in structured, queryable form (already true — no JSON blobs for clinical data)
- Video files stored with consistent path patterns and linked to `GMAssessment` via OneToOne (already true)
- `extract_video_metadata()` returns duration, resolution, codec — available for quality filtering
- No schema changes needed in Phase 1/2 models to support Phase 3 training pipeline

---

### Phase 2 Production Go-Live Gates

Before setting `MULTI_INSTITUTION_ENABLED=True` in any production environment, all of the following must be verified:

1. `institution/tests/test_isolation.py` passes in full on staging with real PostgreSQL (not SQLite)
2. Referral dual-record atomic creation tested end-to-end: both `ReferralSent` and `ReferralReceived` created or neither
3. Notification delivery validated at ≤120 seconds from trigger event to visible badge
4. At least one institution admin onboarding dry-run completed (logo upload, user creation, branding)
5. `python manage.py check --deploy` returns no warnings on the staging environment

---

### Decision Impact Analysis

**Implementation Sequence:**
1. Phase 2 stabilisation — fix known bugs, run isolation test suite, validate referral lifecycle and notifications
2. Phase 2 go-live gate validation — all 5 gates above must pass on staging
3. `MULTI_INSTITUTION_ENABLED=True` on production
4. Phase 3 planning — define video quality standards, training dataset size threshold, AI service tech stack
5. Phase 3 implementation — separate AI microservice, training pipeline, Django integration

**Cross-Component Dependencies:**
- `institution` migrations must run before `referral` migrations — dependency order is fixed
- `InstitutionContextMiddleware` (position 14) depends on `AuthenticationMiddleware` (position 8) — middleware order is invariant
- `ReferralSent` + `ReferralReceived` creation must be wrapped in `transaction.atomic()` — violating atomicity creates orphaned records
- Phase 3 AI service depends on `Video.file` path being stable and `GMAssessment.video_file` OneToOne being intact — these must not be refactored before Phase 3 design is finalised

## Implementation Patterns & Consistency Rules

### Critical Conflict Points Identified

15 areas where AI agents could make incompatible choices when working on NDAS.

---

### Naming Patterns

**Django Model & Database Naming:**
- Tables: Django auto-names as `appname_modelname` (snake_case plural) — never override `Meta.db_table`
- Model classes: PascalCase — `GMAssessment`, `ReferralSent`, `Institution` (never `GmAssessment` or `referral_sent`)
- Model fields: snake_case — `baby_name`, `pog_wks`, `dob_tob` — never guess; check `docs/data-models-main.md` first
- Multi-field uniqueness: `UniqueConstraint` in `Meta.constraints` — never deprecated `unique_together`
- Default ordering: `Meta.ordering = ['-created_at']` on all models

**URL Pattern Naming:**
- URL names: kebab-case — `patient-manager`, `assessment-add`, `video-delete`, `referral-inbox`
- Delete views: suffix `-delete` and `@require_POST` only
- List views: suffix `-manager`; create: `-add`; update: `-edit`; detail: `-view`

**Code Naming:**
- View functions: snake_case — `patient_manager`, `referral_send`, `notification_count`
- Signal names: snake_case — `referral_received`, `referral_replied`, `referral_closed`
- Logger: always `logger = logging.getLogger(__name__)` at module level — never `logging.getLogger("django")`

**Template File Naming:**
- List: `manager.html` | Create: `add.html` | Update: `edit.html` | Detail: `view.html`

---

### Structure Patterns

**Where Things Must Live (Non-Negotiable):**

| What | Where | Never |
|---|---|---|
| TextChoices / IntegerChoices | `ndas/custom_codes/choice.py` | Inline in model field definitions |
| Field validators | `ndas/custom_codes/validators.py` | App-level files or inline |
| HTML sanitization | `ndas/custom_codes/sanitization.py` | App-level helpers |
| Utility functions | `ndas/custom_codes/custom_methods.py` | Re-implemented in app files |
| Enumerations | `ndas/custom_codes/ndas_enums.py` | App-level enum files |
| Delete guards | `ndas/custom_codes/delete_helpers.py` | Direct `.delete()` calls in views |
| Error decorator | `ndas/custom_codes/error_handlers.py` | Try/except blocks in view bodies |
| Signal handlers | `referral/signals.py` | Views or model `save()` |
| Templates | Root `templates/` directory | Inside app directories |
| Tests | `tests/` directory within each app | Co-located with source files |

**New Phase 2 Utilities:**
Cross-app utilities (scoping helpers, path generators) go in `ndas/custom_codes/` — never in `institution/` or `referral/`.

---

### Format Patterns

**View Decorator Stack — Exact Order (All CRUD Views):**

```python
@login_required(login_url="user-login")          # 1st — always
@require_http_methods(["GET", "POST"])           # 2nd — or @require_GET / @require_POST
@ratelimit(key='user_or_ip', rate='10/m')        # 3rd — 5/m for delete views
@handle_view_errors(redirect_url='...')          # 4th — always last
def my_view(request):
```

Never reverse, skip, or add decorators between these four.

**Object Lookup — Always `get_object_or_404()`:**

```python
# CORRECT
obj = get_object_or_404(MyModel, id=pk)

# FORBIDDEN — never in any view
obj = MyModel.objects.get(id=pk)
```

**Input Sanitization — Choose Correctly (Not Interchangeable):**

```python
# Free-text clinical fields → preserves medical notation (BP < 120/80)
value = sanitize_text_input(request.POST['notes'])

# Rich text / CKEditor fields → bleach with medical-safe tag whitelist
value = sanitize_html(request.POST['rich_content'])

# Uploaded filenames → blocks path traversal, hidden files
name = sanitize_filename(uploaded_file.name)

# Search inputs → strips query injection characters
query = sanitize_search_query(request.GET['q'])
```

**Redirect After POST — Always:**

```python
# CORRECT — redirect on success
if form.is_valid():
    form.save()
    return redirect('patient-manager')

# FORBIDDEN — never re-render same template on success
if form.is_valid():
    form.save()
    return render(request, 'patients/add.html', {'form': form})
```

---

### Communication Patterns

**Institution-Scoped Data Access — Phase 2 Views:**

```python
# CORRECT — all Phase 2 queries
patients = Patient.objects.for_institution(request.institution).select_related(...)

# FORBIDDEN — raw filter bypasses isolation
patients = Patient.objects.filter(institution=request.institution)

# SUPERADMIN AGGREGATE VIEWS ONLY — never in regular views
patients = Patient.objects.all_institutions()
```

**Template Context Variables — Phase 2:**

```django
{# CORRECT #}
{% if is_superadmin %}
{{ active_institution.name }}

{# FORBIDDEN — never access request.user directly for institution context #}
{% if request.user.is_superuser %}
{{ request.user.institution.name }}
```

**Signal Handling — Referral System:**

All `Notification.objects.create()` calls live in `referral/signals.py` only — never in views, never in model `save()`. All signal handlers use `try/except` + logging — a signal failure must never break the triggering action.

**Cache Atomic Operations:**

```python
# CORRECT — atomic check-and-set
cache.add(key, value, timeout)

# FORBIDDEN — race condition
if not cache.get(key):
    cache.set(key, value, timeout)
```

**Inline Scripts — CSP Nonce Required:**

```django
{# CORRECT — script will execute in production #}
<script nonce="{{ request.csp_nonce }}">...</script>

{# FORBIDDEN — silently fails in production, no error shown #}
<script>...</script>
```

---

### Process Patterns

**Delete Flow — Always Three Steps:**

```python
from ndas.custom_codes.delete_helpers import has_delete_permission, validate_can_delete

# Step 1 — permission check
if not has_delete_permission(request.user, entity):
    raise PermissionDenied

# Step 2 — business rule check
result = validate_can_delete(entity)
if not result['can_delete']:
    messages.error(request, result['reason'])
    return redirect(...)

# Step 3 — safe to delete
entity.delete()
```

**File Upload Path Generators — Never Hardcode:**

```python
# CORRECT — use existing generators
video.file.field.upload_to = get_video_path_file_name
attachment.file.field.upload_to = get_attachment_path_file_name

# FORBIDDEN — hardcoded upload path
video = models.FileField(upload_to='videos/')
```

**Referral Dual-Record Creation — Always Atomic:**

```python
# Both records created or neither — no exceptions
with transaction.atomic():
    ReferralSent.objects.create(...)
    ReferralReceived.objects.create(...)
```

**User Tracking — Never Set Manually:**

```python
# CORRECT — UserActivityMiddleware auto-populates on save()
obj.save()

# FORBIDDEN — middleware already handles this
obj.added_by = request.user
obj.save()
```

---

### Enforcement Guidelines

**All AI Agents MUST:**
1. Read `_bmad-output/project-context.md` before writing any code in this project
2. Check `ndas/custom_codes/` before writing any helper, utility, or validator
3. Check `docs/data-models-main.md` for exact field names before writing any query
4. Check `docs/api-contracts-main.md` for existing URL names before defining new routes
5. Run `python manage.py test [app_name]` after every change — all existing tests must pass
6. Apply the four-decorator stack to every CRUD view without exception
7. Never use `Model.objects.get()` in view code — always `get_object_or_404()`
8. Never add choices, validators, or utilities outside `ndas/custom_codes/`
9. Never create a class-based view — all views are function-based
10. Never place a template inside an app directory — root `templates/` only

**Pattern Verification Checklist (before any PR):**
- [ ] No inline choices in model field definitions
- [ ] No `Model.objects.get()` in any view
- [ ] No `added_by`/`last_edit_by` set manually in any view
- [ ] No `<script>` tags without `nonce="{{ request.csp_nonce }}"`
- [ ] No Phase 2 views using `.filter(institution=...)` directly
- [ ] No templates inside app directories
- [ ] All new models inherit `TimeStampedModel, UserTrackingMixin`
- [ ] All new signals in `referral/signals.py` with try/except guards

## Project Structure & Boundaries

### Complete Project Directory Structure

```
NDAS/                                        # Repository root
├── manage.py                                # Django management entry point
├── db.sqlite3                               # SQLite DB (dev only — never commit)
├── deploy.sh                                # Production deployment script
├── requirements.txt                         # Python dependencies
├── .env                                     # Secrets (never commit)
├── CLAUDE.md                                # AI agent project rules
│
├── ndas/                                    # Django project package (config)
│   ├── settings.py                          # All settings — env-var driven
│   ├── urls.py                              # Root URL dispatcher → all apps
│   ├── views.py                             # handler404, handler500
│   ├── wsgi.py / asgi.py                    # WSGI/ASGI entry points
│   ├── templatetags/
│   │   └── delete_modal_tags.py             # Universal delete modal tag
│   └── custom_codes/                        # SHARED UTILITY LAYER (all apps import here)
│       ├── Custom_abstract_class.py         # TimeStampedModel + UserTrackingMixin
│       ├── choice.py                        # ALL TextChoices/IntegerChoices
│       ├── validators.py                    # ALL field validators + sanitize helpers
│       ├── sanitization.py                  # HTML sanitization (bleach)
│       ├── custom_methods.py                # Shared utilities + path generators
│       ├── ndas_enums.py                    # Python enumerations
│       ├── delete_helpers.py                # Delete permission + validation guards
│       ├── security_middleware.py           # CSP + security header middleware
│       └── error_handlers.py               # @handle_view_errors, @log_and_suppress
│
├── patients/                                # Phase 1 — PRIMARY app (root URL "")
│   ├── models.py                            # Patient, GMAssessment, CDICRecord, GPA,
│   │                                        #   HINEAssessment, DevelopmentalAssessment,
│   │                                        #   Attachment, Bookmark, IndicationsForGMA,
│   │                                        #   DiagnosisList, Help
│   ├── views.py                             # All patient/assessment CRUD views
│   ├── urls.py                              # URL patterns (root catch-all — must be last)
│   ├── forms.py                             # Patient + assessment forms
│   ├── timeline_utils.py                    # Patient timeline data builder
│   ├── migrations/                          # 10 migrations
│   └── tests/
│       ├── test_validators.py
│       └── test_views.py
│
├── users/                                   # Phase 1 — Auth & user management (users/)
│   ├── models.py                            # CustomUser, UserActivityLog, UserSession,
│   │                                        #   DeveloperContacts, Subscription
│   ├── views.py                             # Login, logout, profile, admin user mgmt
│   ├── middleware.py                        # UserActivityMiddleware (pos 9),
│   │                                        #   SubscriptionCheckMiddleware (pos 13)
│   ├── decorators.py                        # @subscription_required, role decorators
│   ├── utils.py                             # Email helpers, token utilities
│   ├── migrations/                          # 9 migrations
│   └── tests.py
│
├── video/                                   # Phase 1 — Video management (video/)
│   ├── models.py                            # Video (VideoQuerySet, VideoManager)
│   ├── views.py                             # Upload, stream, delete
│   ├── forms.py                             # VideoForm with MIME validation
│   ├── management/commands/
│   │   └── fix_video_durations.py           # Backfill duration metadata
│   ├── migrations/                          # 7 migrations
│   └── tests.py
│
├── reports/                                 # Phase 1 — PDF/Excel reports (reports/)
│   ├── models.py                            # ReportTemplate, ReportConfig
│   ├── tasks.py                             # Synchronous report generation
│   ├── utils/
│   │   ├── pdf_generator.py                 # BasePDFGenerator + subclasses
│   │   └── excel_generator.py              # ExcelReportGenerator
│   ├── migrations/                          # 2 migrations
│   └── tests.py
│
├── problemlist/                             # Phase 1 — Problem list (problems/)
│   ├── models.py                            # Problem, ProblemAction
│   ├── migrations/                          # 2 migrations
│   └── tests.py
│
├── institution/                             # Phase 2 — Multi-institution (institution/)
│   ├── models.py                            # Institution, PatientMoveLog,
│   │                                        #   InstitutionSwitchLog
│   ├── managers.py                          # InstitutionScopedManager (.for_institution())
│   ├── middleware.py                        # InstitutionContextMiddleware (pos 14)
│   ├── context_processors.py               # Injects active_institution, is_superadmin
│   ├── templatetags/
│   │   └── institution_tags.py
│   ├── migrations/                          # 5 migrations
│   └── tests/                              # 17 test modules including test_isolation.py
│
├── referral/                                # Phase 2 — Referral system (referral/)
│   ├── models.py                            # ReferralSent, ReferralReceived,
│   │                                        #   ReferralMessage, Notification
│   ├── signals.py                           # ALL notification creation lives here
│   ├── utils.py                             # Referral helper utilities
│   ├── migrations/                          # 2 migrations
│   └── tests/                              # 9 test modules
│
├── templates/                               # ALL templates centralised here (never in apps)
│   ├── src/                                 # Base layout + shared partials
│   │   ├── base.html                        # Primary base — all authenticated views
│   │   ├── basic_plane.html                 # Public/unauthenticated views
│   │   └── partials/
│   │       └── delete_confirmation_modal.html
│   ├── patients/                            # Patient + assessment templates
│   ├── assessment/, cdic_record/, gpa_record/, hine/, develop_assemnt/
│   ├── attachment/, bookmark/, problemlist/
│   ├── institution/, referral/
│   ├── users/, video/, reports/
│   └── 404.html, 500.html
│
├── static/                                  # Static assets (CSS, JS, AdminLTE, fonts)
├── media/                                   # Uploaded files (never commit)
│   └── {institution_slug}/
│       ├── videos/
│       ├── attachments/
│       └── logo/
└── logs/
    ├── django.log                           # Application log (rotating 15MB × 10)
    └── security.log                         # Security events (production only)
```

---

### Architectural Boundaries

**App Dependency Order (no circular imports):**

```
patients    ← root app; all others depend on it, not vice versa
users       ← auth foundation; patients, institution, referral depend on it
institution ← Phase 2 foundation; patients, referral, users depend on it
referral    ← depends on institution + patients; nothing depends on referral
video       ← depends on patients (OneToOne with GMAssessment)
reports     ← depends on patients
problemlist ← depends on patients; references users via settings.AUTH_USER_MODEL
```

**URL Routing Boundary (order matters):**

| URL Prefix | App | Phase |
|---|---|---|
| `/admin/` | Django admin | All |
| `/institution/` | institution.urls | Phase 2 |
| `/referral/` | referral.urls | Phase 2 |
| `/users/` | users.urls | Phase 1 |
| `/reports/` | reports.urls | Phase 1 |
| `/problems/` | problemlist.urls | Phase 1 |
| `/video/` | video.urls | Phase 1 |
| `/` (root, catch-all last) | patients.urls | Phase 1 |

**Data Boundaries:**

| Model | Scoping | Notes |
|---|---|---|
| `Patient` | Per-institution (Phase 2) | `InstitutionScopedManager` |
| `GMAssessment` | Via Patient FK | OneToOne with Video — never break this coupling |
| `Video` | Via Patient FK | Stored at `{institution_slug}/videos/` |
| `Attachment` | Via Patient FK | Stored at `{institution_slug}/attachments/` |
| `ReferralSent` | Sending institution only | No FK to ReferralReceived |
| `ReferralReceived` | Receiving institution only | Linked only by `referral_uuid` |
| `Notification` | Per-institution, per-user | Created via signals only |
| `UserActivityLog` | Superadmin: all; InstitutionAdmin: own only | Middleware-written, not editable via UI |

---

### Requirements to Structure Mapping

**Phase 1 FR Mapping:**

| FR Category | Primary Location |
|---|---|
| Patient Record Management (FR1–5) | `patients/models.py`, `patients/views.py`, `templates/patients/` |
| Assessment Workflows (FR6–12) | `patients/models.py`, `templates/assessment/` + `cdic_record/` + `gpa_record/` + `hine/` + `develop_assemnt/` |
| Video Management (FR13–16) | `video/models.py`, `video/views.py`, `templates/video/` |
| Multi-Clinician Opinion (FR17–19) | `patients/models.py` (DiagnosisList), `patients/views.py` |
| Problem List (FR20–22) | `problemlist/models.py`, `templates/problemlist/` |
| Report Generation (FR23–25) | `reports/utils/pdf_generator.py`, `reports/utils/excel_generator.py` |
| Attachments & Bookmarks (FR26–27) | `patients/models.py`, `templates/attachment/`, `templates/bookmark/` |
| User Management & Access (FR28–31) | `users/models.py`, `users/views.py`, `users/decorators.py` |

**Phase 2 FR Mapping:**

| FR Category | Primary Location |
|---|---|
| Multi-Institution Foundation (FR32–37) | `institution/models.py`, `institution/managers.py`, `institution/middleware.py` |
| Patient Referral System (FR38–45) | `referral/models.py`, `referral/views.py`, `referral/utils.py` |
| Consultation Thread & Notifications (FR46–49) | `referral/models.py` (ReferralMessage, Notification), `referral/signals.py` |
| Patient Transfer (FR50–51) | `institution/models.py` (PatientMoveLog), `institution/views.py` |
| Audit Trail (FR52–55) | `users/middleware.py` (UserActivityMiddleware), `users/models.py` (UserActivityLog) |

**Cross-Cutting Concern Locations:**

| Concern | Location |
|---|---|
| Security middleware | `ndas/custom_codes/security_middleware.py` + `ndas/settings.py` |
| Rate limiting | `ndas/settings.py` config; `@ratelimit` decorator per-view |
| Input sanitization | `ndas/custom_codes/validators.py` + `ndas/custom_codes/sanitization.py` |
| Delete guards | `ndas/custom_codes/delete_helpers.py` |
| Error handling | `ndas/custom_codes/error_handlers.py` |
| Base model | `ndas/custom_codes/Custom_abstract_class.py` |

---

### Data Flow

**Clinical Assessment Flow (Phase 1):**
```
Browser → Nginx → Gunicorn → Django 14-layer middleware stack
  → @login_required → @ratelimit → @handle_view_errors
  → patients/views.py → get_object_or_404(Patient)
  → sanitize_text_input() on all user input
  → form.save() → UserActivityMiddleware auto-sets added_by/last_edit_by
  → redirect() → server-rendered HTML response
```

**Video Upload Flow:**
```
Browser (chunked upload with progress) → video/views.py
  → validate MIME + extension + size (settings.FILE_UPLOAD_LIMITS)
  → sanitize_filename()
  → get_video_path_file_name() → media/{institution_slug}/videos/
  → extract_video_metadata() (FFmpeg / moviepy fallback)
  → Video.objects.create() with patient FK
```

**Cross-Institution Referral Flow (Phase 2):**
```
Clinician initiates referral → referral/views.py
  → validate target institution ≠ source institution
  → capture snapshot_data = frozen JSON of full patient record
  → transaction.atomic():
      ReferralSent.objects.create(referral_uuid=uuid4(), snapshot_data=...)
      ReferralReceived.objects.create(referral_uuid=same_uuid, snapshot_data=...)
  → post-save signal → referral/signals.py
      → Notification.objects.create() for receiving institution users
  → HTMX polls /referral/notification-count/ every 60s → badge within 120s
```

**Phase 3 AI Integration Flow (planned):**
```
GMAssessment saved → Django fires async HTTP to AI microservice
  → AI service reads Video file from GMAssessment.video_file path
  → returns inference result (movement classification)
  → Django stores on GMAssessment → surfaces in assessment view
  (AI service independent; Django monolith unchanged)
```

## Architecture Validation Results

### Coherence Validation ✅

All architectural decisions are mutually compatible. Technology stack (Django 4.2.16, HTMX, AdminLTE 3.2, django-csp, django-ratelimit, InstitutionScopedManager) has no internal conflicts. CSP nonce injection and HTMX partial requests are compatible. Phase 3 AI microservice is deliberately isolated — no monolith coupling conflicts possible. Naming conventions, the four-decorator stack, custom_codes/ utility layer, and template naming are consistent across all 7 apps.

### Requirements Coverage Validation ✅

All 58 FRs and 23 NFRs are architecturally supported:
- Phase 1 (FR1–31): Full coverage across patients, users, video, reports, problemlist apps
- Phase 2 (FR32–51): Full coverage via institution/, referral/, InstitutionScopedManager, dual-record referral, atomic creation, HTMX polling
- Phase 3 (FR56–58): Deferred cleanly — AI microservice architecture defined with prerequisites
- Cross-cutting Audit (FR52–55): UserActivityMiddleware + UserActivityLog with role-scoped access
- All 7 NFR categories addressed: Performance, Security, Data Integrity, Reliability, Scalability, Maintainability, Compatibility

### Implementation Readiness: HIGH ✅

All critical decisions documented with versions. All 15 agent conflict points addressed with correct/forbidden code examples. PR verification checklist defined. Complete project tree drawn from actual source tree.

### Gap Analysis

**Critical Gaps:** None — all FRs and NFRs are architecturally covered.

**Important Gaps (address before epics/stories):**

1. **Media file access control pattern** — `institution/views.py` contains protected media serving views but the pattern for institution-scoped media access control is not explicitly documented. Agents adding new file-serving views should reference the existing protected media view implementation before writing new ones.

2. **Email backend decision** — `users/utils.py` handles email verification and password reset. Email backend not documented. Current assumption: Django console backend (dev) / SMTP (prod via env vars). Confirm and document in settings before any work on user onboarding flows.

3. **Subscription state machine boundary** — `SubscriptionCheckMiddleware` and grace period exemption for `/referral/` URLs are referenced but the subscription lifecycle (active → inactive → grace → expired, what triggers each state) is not architecturally documented. Agents touching subscription-adjacent code should read `users/models.py` (Subscription) and `users/middleware.py` (SubscriptionCheckMiddleware) before implementing.

**Nice-to-Have Gaps:** Uptime monitoring (deferred to Phase 2 go-live), DB backup strategy, Django admin conventions.

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analyzed (92 rules from project-context.md)
- [x] Scale and complexity assessed (High — clinical, multi-tenant, large uploads)
- [x] Technical constraints identified (frozen stack, deployment flexibility, Phase 3 deps)
- [x] Cross-cutting concerns mapped (6 concerns across all phases)

**✅ Architectural Decisions**
- [x] Critical decisions documented (data isolation, atomic referral, immutable snapshot)
- [x] Technology stack fully specified (all versions pinned)
- [x] Phase 3 integration architecture decided (separate AI microservice)
- [x] Phase 2 go-live gates defined (5 gates)

**✅ Implementation Patterns**
- [x] 15 agent conflict points identified and resolved
- [x] Naming conventions established (models, URLs, views, templates, signals)
- [x] Correct/forbidden code examples for all major patterns
- [x] PR verification checklist defined (8 checks)

**✅ Project Structure**
- [x] Complete directory structure from actual source tree
- [x] App dependency order and URL routing order documented
- [x] All 58 FRs mapped to specific files and directories
- [x] Data flow documented for all major flows (assessment, video, referral, Phase 3)

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION**

**Confidence Level: HIGH**

**Key Strengths:**
- Brownfield project with existing, well-structured codebase — architecture validates against actual code, not hypothetical design
- 92 existing agent rules in project-context.md provide deep implementation guidance
- Phase 2 multi-institution architecture (InstitutionScopedManager + dual-record referral) is a well-thought-out isolation model with no known design flaws
- Phase 3 AI microservice decision cleanly isolates future ML work from the stable monolith

**Areas for Future Enhancement:**
- Uptime monitoring and alerting (natural Phase 2 go-live trigger)
- Media file access control pattern documentation
- Email backend formal decision and documentation
- Subscription state machine documentation

### Implementation Handoff

**AI Agent Guidelines:**
1. Read `_bmad-output/project-context.md` before writing any code
2. Read `docs/data-models-main.md` before writing any ORM query
3. Read `docs/api-contracts-main.md` before defining any new URL
4. Follow all 15 pattern rules in the "Implementation Patterns & Consistency Rules" section
5. Apply the PR verification checklist before any commit
6. Run `python manage.py test [app_name]` after every change

**First Implementation Priority:**
Phase 2 stabilisation — resolve known bugs, run `institution/tests/test_isolation.py` on staging with PostgreSQL, validate all 5 Phase 2 go-live gates. No new development until Phase 2 is production-ready.
