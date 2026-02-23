---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-02-23'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/product-brief-NDAS-2026-02-22.md
  - _bmad-output/project-context.md
  - docs/index.md
  - docs/architecture.md
  - docs/data-models-main.md
  - docs/api-contracts-main.md
  - docs/component-inventory-main.md
  - docs/custom-codes-reference.md
  - docs/project-overview.md
  - docs/development-guide.md
  - _bmad-output/brainstorming/brainstorming-session-2026-02-21.md
workflowType: 'architecture'
project_name: 'NDAS'
user_name: 'Rasika'
date: '2026-02-23'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

---

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**

Phase 2 adds 26 FRs (FR45–FR70; FR39 retired) across five groups:

| Group | FRs | Core Capability |
|-------|-----|-----------------|
| Multi-Institution Foundation | FR45–49 | Data isolation, file isolation, user binding, per-institution subscription, migration path |
| Superadmin Capabilities | FR50–55 | God-view dashboard, context switching, atomic institution onboarding, aggregate analytics/reports, patient move |
| Institution Admin Capabilities | FR56–59 | Admin dashboard, user management, logo/branding, PDF branding |
| Referral System | FR60–66 | Cross-institution referrals, frozen snapshot, consultation thread, unified inbox, lifecycle, patient tab, dual records |
| Referral Notifications | FR67–70 | Signal-driven notifications, bell icon, 120-second refresh |

Phase 1 (FR1–FR37) is fully operational — all 37 FRs remain unchanged.

**Non-Functional Requirements (Phase 2 — architecturally driving):**

| NFR | Requirement | Architectural Impact |
|-----|-------------|----------------------|
| NFR19 | Zero cross-institution data leakage; automated isolation tests before prod enable | Defence-in-depth: ORM manager + middleware + test suite |
| NFR20 | 20+ institutions, no additional infrastructure | Mandatory row-level isolation (excludes schema-per-tenant, DB-per-tenant) |
| NFR21 | Feature flag deactivation restores single-institution behaviour | All Phase 2 code paths must be additive and flag-gated |
| NFR22 | Referral record creation atomic (both or neither) | Database transaction wrapping dual-record creation |
| NFR23 | Notifications within 120 seconds of trigger | HTMX 60-second polling confirmed as delivery mechanism |

**Scale & Complexity:**

- Primary domain: Server-rendered Django MPA (HTMX for dynamic interactions)
- Complexity level: Enterprise
- Estimated new architectural components: Institution model + middleware + ORM manager + storage backend + referral models + notification model + 4 dashboard surfaces + migration layer

### Technical Constraints & Dependencies

**Brownfield Constraints (non-negotiable):**

- `patients/models.py` 2837 lines — all existing field names, relationships, and constraints must be preserved exactly
- 13-layer middleware stack is order-critical — new `InstitutionContextMiddleware` inserts before `SubscriptionCheckMiddleware` (which it replaces)
- AdminLTE 3.2 + Bootstrap 4.6 frozen — new UI surfaces must reuse existing AdminLTE slots (sidebar, navbar bell, card grid)
- All views function-based — decorator stack `@login_required → @require_http_methods → @ratelimit → @handle_view_errors` applies to all new views
- `patients` app is the root URL (`/`) — new `institution` app must carry no reverse dependencies on other apps
- Existing file paths (`YYYY/MM/patient_name/`) must migrate to institution-partitioned paths atomically

**Existing Components Being Extended or Replaced:**

| Component | Current State | Phase 2 Change |
|-----------|--------------|----------------|
| `Subscription` model | Singleton, users app | Replaced by per-institution subscription on `Institution` model |
| `SubscriptionCheckMiddleware` | Middleware layer 13 | Replaced by `InstitutionContextMiddleware` |
| `CustomUser` | superuser/staff boolean + staff_position | Extended with `institution` FK + `user_type` field |
| `BasePDFGenerator` / `PatientPDFGenerator` | Clinic name from `ReportTemplate` | Extended with active institution logo, name, header |
| `ExcelReportGenerator` | Per-patient and anonymised cohort | Extended with per-institution and cross-institution scope |

### Cross-Cutting Concerns Identified

1. **Data Isolation** — Every model with an institution FK requires automatic queryset filtering; no view should be able to return cross-institution data accidentally
2. **Institution Context Resolution** — Every authenticated request must resolve active institution (from `user.institution` for ADMIN/USER, from session for SUPERADMIN) — single point of truth, used by views, templates, storage, and reports
3. **Subscription Enforcement** — Grace period (read-only), expiry (login blocked), and active-referral exemption must be consistently enforced across middleware and model layer
4. **File Storage Partitioning** — All video and attachment uploads must be physically routed to `/{institution_slug}/` without changes to model field declarations
5. **Audit Trail** — Every record creation, modification, and cross-institution event (patient move, referral) requires entries at both institutions
6. **PDF/Excel Branding** — All report generators must inject active institution logo and name from context processor — zero per-view special-casing
7. **Notification Delivery** — Signal-driven creation on referral events; HTMX polling at 60s for delivery; all notifications institution-scoped
8. **Migration Safety** — Feature flag gates all Phase 2 behaviour; existing data migrates to `default_institution` atomically before flag is enabled in production

---

## Starter Template Evaluation

### Primary Technology Domain

Brownfield server-rendered Django MPA expansion. No CLI starter applies —
the existing NDAS codebase is the foundation for Phase 2.

### Technology Foundation (Existing — Locked)

| Category | Stack | Phase 2 Impact |
|----------|-------|----------------|
| Framework | Django 4.2.16 (Python 3.x) | New app(s), migrations to existing apps |
| Database | SQLite (dev) / PostgreSQL (prod) | New tables via Django ORM migrations |
| Frontend | AdminLTE 3.2 + Bootstrap 4.6 | New templates reuse existing card/sidebar/bell slots |
| Dynamic UI | HTMX | Bell icon polling; referral thread interactions |
| Data Fields | Django 4.2 built-in JSONField | Frozen patient snapshot storage |
| File Storage | Django built-in FileSystemStorage | Custom subclass for institution partitioning |
| Signals | Django built-in signals | Referral event notifications |
| Reports | reportlab 4.4.3 + openpyxl 3.1.5 | Extended with institution branding and 3-scope reports |
| UUID | Python stdlib uuid | Referral record linking |

### New Packages Required

None. All Phase 2 capabilities are implemented using the existing stack.

### Architectural Patterns (Inherited)

- **Code organisation:** All shared utilities in `ndas/custom_codes/` — Phase 2 adds to existing modules
- **View pattern:** Function-based views, mandatory decorator stack, `get_object_or_404()` everywhere
- **Model pattern:** `TimeStampedModel + UserTrackingMixin` on all new models
- **Template pattern:** Extend `src/base.html`; naming `manager.html / add.html / edit.html / view.html`
- **Choice pattern:** All new TextChoices in `ndas/custom_codes/choice.py`
- **Validator pattern:** All new validators in `ndas/custom_codes/validators.py`
- **Delete pattern:** `has_delete_permission()` + `validate_can_delete()` before any delete

---

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Institution isolation strategy — row-level ORM with explicit `.for_institution()`
- InstitutionContextMiddleware — replaces SubscriptionCheckMiddleware
- New app structure — `institution/` + `referral/`
- Feature flag gating — all Phase 2 behaviour behind `MULTI_INSTITUTION_ENABLED`
- Atomic default institution migration — must complete before flag enabled in production

**Important Decisions (Shape Architecture):**
- Dual referral records via UUID — institution data self-contained
- Custom institution-aware file path generation — physical file partitioning
- SUPERADMIN carries `is_superuser=True` — existing permission checks unchanged
- Frozen snapshot = full clinical record — faithful to FR61

**Deferred Decisions (Post-Phase 2):**
- Referral snapshot versioning (Phase 3 — explicitly out of scope per PRD)
- WebSocket/SSE for real-time notifications (Phase 3 — HTMX polling confirmed for Phase 2)
- Onboarding checklist (Phase 3 — out of scope per PRD)

---

### Data Architecture

**Isolation Strategy:** Row-level ORM via custom `InstitutionScopedManager` on every model
with an institution FK. Views explicitly call `.for_institution(request.institution)` — no
thread-local. Superadmin aggregate queries use `.all_institutions()` or omit institution
filter intentionally. Enforced by isolation test suite (NFR19) before production flag enable.

**App Structure:**
- `institution/` — Institution model, InstitutionContextMiddleware,
  InstitutionScopedManager, institution-aware file path generators, subscription logic,
  superadmin views, institution admin dashboard, institution context processor
- `referral/` — ReferralSent, ReferralReceived, ReferralMessage, Notification
  models, referral inbox views, notification views, Django signals

**Institution Model fields:** `name`, `slug` (immutable after creation — enforced in
`save()` override + `clean()`), `logo`, `subscription_status`, `subscription_start`,
`grace_period_end`, `is_active`, `created_by` (SUPERADMIN FK), inherits
`TimeStampedModel`.

**CustomUser extensions:** `institution` FK (nullable for SUPERADMIN only),
`user_type` CharField with TextChoices (SUPERADMIN/ADMIN/USER) added to `ndas/custom_codes/choice.py`.
Existing `staff_position` field unchanged.

**Referral models:**
- `ReferralSent` — owned by originating institution; FK to patient, from_institution,
  to_institution, from_clinician, to_clinician, `referral_uuid` (UUID4), status
  (PENDING/REPLIED/CLOSED), `snapshot_data` JSONField, outcome, `survives_expiry=True`
- `ReferralReceived` — owned by receiving institution; linked by same `referral_uuid`;
  contains its own copy of `snapshot_data`; self-contained even if Institution A is suspended
- `ReferralMessage` — FK to ReferralSent/ReferralReceived via UUID; sender, body, timestamp,
  message_type (OPINION)
- `Notification` — recipient FK, `notification_type` (REFERRAL_RECEIVED/REFERRAL_REPLIED/
  REFERRAL_CLOSED), title, body, link, `is_read`, `created_at`; institution-scoped

**Frozen snapshot scope (`snapshot_data` JSONField):** Captured at referral submission;
immutable thereafter. Contains: patient demographics + all identifiers (BHT, NNC, PTC, PC,
PIN, Disk No.) + perinatal data + all assessment records and scores (HINE, GMA metadata,
DA, GPA, CDIC) + active problem list with interventions and responses + attachments metadata
(filename, type, date — no binary data). Estimated size: 20–50KB per referral.

**Subscription model:** Singleton `Subscription` in `users` app retired. Per-institution
subscription fields live on `Institution` model: `subscription_status`
(ACTIVE/GRACE/EXPIRED), `grace_period_end`. Active referrals are exempt from
read-only restrictions regardless of subscription state.

**Migration path:** Single Django data migration atomically assigns all existing patients,
assessments, videos, attachments, and users to `default_institution`. Existing
`Subscription` singleton values copied to `default_institution` fields. Existing
file paths migrated to `/{default_institution_slug}/` directory structure.
`MULTI_INSTITUTION_ENABLED=False` until staging validation passes.

---

### Authentication & Security

**SUPERADMIN identity:** `user_type=SUPERADMIN` + `is_superuser=True` always set together
at account creation. All 37 existing Phase 1 permission checks using `is_superuser`
remain untouched. `user_type` is the authority for institution-scoping logic only.

**Institution context resolution:**
- ADMIN/USER: `request.institution = request.user.institution` (set in middleware)
- SUPERADMIN: `request.institution = session['active_institution_id']` (set in middleware)
- SUPERADMIN with no active context: redirected to institution selector screen

**Subscription enforcement (defence-in-depth):**
- Middleware layer: checks `institution.subscription_status` on every request
- Model property: `Institution.is_subscription_active` for programmatic checks
- Grace period: read-only mode (GET allowed, POST blocked) except active referral threads
- Expiry: login blocked entirely

**Isolation testing (NFR19):** Automated test suite verifies no query returns data
outside the active institution. Must pass on staging before `MULTI_INSTITUTION_ENABLED`
is flipped in production. Any leakage incident is a blocking defect.

**File access security:** Institution-aware `upload_to` callables route all uploads to
`MEDIA_ROOT/{institution_slug}/videos/` and `MEDIA_ROOT/{institution_slug}/attachments/`.
Direct URL access to another institution's files blocked at application layer.

---

### API & Communication Patterns

**URL structure:** Institution context lives in session — NOT in URL. All existing URL
patterns (`/patients/`, `/reports/`, `/video/`, `/problems/`) unchanged. New URL namespaces:
- `institution/` — superadmin and institution admin views
- `referral/` — referral inbox, thread views, notification endpoints

**HTMX patterns (Phase 2 additions):**
- Bell icon: `hx-get="/referral/notifications/count/"` polling every 60 seconds,
  target `#notification-bell-count`
- Referral thread: `hx-get` on thread-item click loads thread into `#referral-thread-panel`
- Superadmin overlay switch: full page reload on institution context change

**Error handling:** All new views use `@handle_view_errors()` decorator (existing pattern).
Referral atomic transaction failures surface as user-visible error messages, not silent failures.

---

### Frontend Architecture

**Institution branding:** `institution_context` context processor injects `active_institution`,
`user_type`, `is_superadmin`, and institution branding (logo URL, name) into every template.
AdminLTE sidebar brand-logo and brand-text slots display active institution identity.

**Superadmin overlay:** Persistent top banner rendered via `{% superadmin_overlay %}` template
tag in `src/base.html`. Conditionally visible when `is_superadmin` is True and an institution
context is active. Banner content: "Viewing as: [Institution Name] [Switch ▼]" + elevated
action buttons (Move Patient, Edit Subscription, Suspend User).

**Referral inbox layout:** AdminLTE card split-panel — thread list (left column, scrollable)
+ active thread (right column, HTMX-loaded). Patient thumbnail, referring institution,
date, unread indicator in each list item. Thread panel: fixed patient header card, frozen
snapshot as collapsible `<details>` panel, alternating message bubbles with clinician +
institution badge + timestamp, reply textarea at bottom.

**New dashboard surfaces:**
- God-view (SUPERADMIN): card grid of all institutions, cross-institution aggregate stats,
  recent events audit log
- Institution admin: four-quadrant AdminLTE card layout (patient stats / assessment activity /
  referral activity / team activity)

---

### Infrastructure & Deployment

**Feature flag:** `MULTI_INSTITUTION_ENABLED` in `ndas/settings.py`. Checked only in
`InstitutionContextMiddleware` and top-level superadmin template tags. Removed from
codebase after stable production rollout (Phase 2 complete).

**Deployment:** No new servers, databases, or deployment cycles per institution.
Single Gunicorn + Nginx deployment serves all institutions. Institution count growth
is a data operation, not an infrastructure operation (NFR20).

**Scaling:** 20+ concurrent institutions supported via row-level isolation on existing
PostgreSQL instance. No per-institution connection pools or database shards required.

---

### Decision Impact Analysis

**Implementation sequence (dependency order):**
1. `institution` app — Institution model + migrations first (everything else depends on it)
2. CustomUser extensions — institution FK + user_type field + migrations
3. InstitutionContextMiddleware — replaces SubscriptionCheckMiddleware
4. InstitutionScopedManager — add to all institution-FK models
5. Institution-aware upload_to callables — update all FileField upload_to functions
6. Data migration — atomic migration of existing data to default_institution
7. `referral` app — Referral + Notification models (depend on institution app)
8. Superadmin views + god-view dashboard
9. Institution admin views + dashboard
10. Referral inbox + thread UI
11. Signal-driven notifications + HTMX bell icon
12. PDF/Excel branding extensions
13. Isolation test suite + feature flag enable on staging

**Cross-component dependencies:**
- `InstitutionContextMiddleware` must be in place before any institution-scoped view works
- `institution` app must be migrated before `referral` app (FK dependency)
- Data migration to default_institution must complete before `MULTI_INSTITUTION_ENABLED=True`
- Isolation test suite must pass before production flag flip

---

## Implementation Patterns & Consistency Rules

### Critical Conflict Points Identified

10 areas where AI agents could make incompatible choices without explicit rules.

---

### Naming Patterns

**New URL Names (kebab-case, consistent with existing):**
```
institution-selector         institution-add          institution-edit
institution-admin-dashboard  institution-logo-upload  institution-user-add
institution-user-deactivate  superadmin-dashboard     superadmin-patient-move
referral-inbox               referral-send            referral-thread
referral-reply               referral-close           referral-patient-tab
notification-count           notification-list        notification-mark-read
```

**New Model Class Names (PascalCase):**
`Institution` · `ReferralSent` · `ReferralReceived` · `ReferralMessage` · `Notification`

**New View Function Names (snake_case):**
`institution_selector` · `institution_add` · `institution_admin_dashboard`
`referral_inbox` · `referral_send` · `referral_thread` · `referral_reply` · `referral_close`
`notification_count` · `notification_list`

**New Signal Names:** `referral_received` · `referral_replied` · `referral_closed`

**New Choice Keys (all added to `ndas/custom_codes/choice.py`):**

```python
class UserType(models.TextChoices):
    SUPERADMIN = 'SUPERADMIN', 'Super Admin'
    ADMIN = 'ADMIN', 'Institution Admin'
    USER = 'USER', 'Clinician'

class SubscriptionStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    GRACE = 'GRACE', 'Grace Period'
    EXPIRED = 'EXPIRED', 'Expired'

class ReferralStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    REPLIED = 'REPLIED', 'Replied'
    CLOSED = 'CLOSED', 'Closed'

class NotificationType(models.TextChoices):
    REFERRAL_RECEIVED = 'REFERRAL_RECEIVED', 'Referral Received'
    REFERRAL_REPLIED  = 'REFERRAL_REPLIED',  'Referral Replied'
    REFERRAL_CLOSED   = 'REFERRAL_CLOSED',   'Referral Closed'
```

---

### Structure Patterns

**New App Directory Structures:**

```
institution/
├── __init__.py
├── apps.py                    # AppConfig — registers signals in ready()
├── context_processors.py      # institution_context processor
├── managers.py                # InstitutionScopedManager
├── middleware.py              # InstitutionContextMiddleware
├── migrations/
├── models.py                  # Institution model only
├── templatetags/
│   ├── __init__.py
│   └── institution_tags.py    # {% superadmin_overlay %}
├── tests/
│   ├── test_isolation.py      # NFR19 — mandatory isolation checks
│   ├── test_middleware.py
│   └── test_models.py
├── urls.py
└── views.py

referral/
├── __init__.py
├── apps.py                    # AppConfig — registers referral signals in ready()
├── migrations/
├── models.py                  # ReferralSent, ReferralReceived, ReferralMessage, Notification
├── signals.py                 # All signal handlers — ONLY place Notifications are created
├── tests/
│   ├── test_referral_lifecycle.py
│   ├── test_notifications.py
│   └── test_snapshot.py
├── urls.py
├── utils.py                   # build_patient_snapshot() — sole snapshot builder
└── views.py
```

---

### Format Patterns

**InstitutionScopedManager — Canonical Usage:**

```python
# institution/managers.py
class InstitutionScopedManager(models.Manager):
    def for_institution(self, institution):
        """Standard institution-filtered queryset. Use in ALL institution-scoped views."""
        return self.get_queryset().filter(institution=institution)

    def all_institutions(self):
        """Unfiltered queryset for SUPERADMIN aggregate use ONLY."""
        return self.get_queryset()
```

Every model with an institution FK MUST declare:
```python
class Patient(TimeStampedModel, UserTrackingMixin):
    institution = models.ForeignKey('institution.Institution', on_delete=models.PROTECT)
    objects = InstitutionScopedManager()
```

**✅ CORRECT — every institution-scoped view:**
```python
patients  = Patient.objects.for_institution(request.institution)
referrals = ReferralSent.objects.for_institution(request.institution)
```

**❌ WRONG — never write these:**
```python
patients = Patient.objects.all()                              # leaks cross-institution data
patients = Patient.objects.filter(institution=request.institution)  # bypasses manager
```

**✅ CORRECT — superadmin aggregate only:**
```python
total = Patient.objects.all_institutions().count()
```

---

**Institution-Aware File Path Generators — Canonical Pattern:**

Add to `ndas/custom_codes/validators.py`:

```python
def get_institution_video_path(instance, filename):
    """upload_to callable for Video.file — routes to /{slug}/videos/"""
    slug = instance.patient.institution.slug
    return f"{slug}/videos/{sanitize_filename(filename)}"

def get_institution_attachment_path(instance, filename):
    """upload_to callable for Attachment.file — routes to /{slug}/attachments/"""
    slug = instance.patient.institution.slug
    return f"{slug}/attachments/{sanitize_filename(filename)}"
```

**✅ CORRECT — model FileField declaration:**
```python
file = models.FileField(upload_to=get_institution_video_path)
```

**❌ WRONG:**
```python
file = models.FileField(upload_to=get_video_path_file_name)  # no institution slug
file = models.FileField(upload_to='videos/')                  # no institution slug
```

---

**Frozen Snapshot — Canonical JSON Schema (`referral/utils.py`):**

```json
{
  "captured_at": "2026-02-23T10:30:00Z",
  "schema_version": 1,
  "patient": {
    "baby_name": "...", "bht": "...", "nnc_no": "...",
    "ptc": "...",       "pc": "...",  "pin": "...",    "disk_no": "...",
    "dob_tob": "2025-08-15",
    "gender": "...",
    "pog_wks": 32,      "pog_days": 4,
    "birth_weight": 1500, "hc": 32.0,
    "apgar_1": 7,       "apgar_5": 9,  "apgar_10": null
  },
  "assessments": {
    "hine":  [{"id": 1, "date": "...", "total_score": 54, "examiner": "..."}],
    "gma":   [{"id": 1, "date": "...", "assessment_type": "...", "examiner": "..."}],
    "da":    [{"id": 1, "date": "...", "gm": 12, "fmv": 10, "hsl": 11, "seb": 9,
               "corrected_age_months": 6}],
    "gpa":   [{"id": 1, "date": "..."}],
    "cdic":  [{"id": 1, "date": "...", "centre": "..."}]
  },
  "problems": [
    {"problem": "...", "status": "Active",
     "interventions": [{"intervention": "...", "response": "...", "status": "Active"}]}
  ],
  "attachments": [{"filename": "...", "type": "pdf", "uploaded_at": "..."}]
}
```

`build_patient_snapshot(patient)` in `referral/utils.py` is the **only** place this is built.
Called once at `ReferralSent` creation. Snapshot is immutable after that point.

---

### Communication Patterns

**Signal Registration — Canonical Pattern:**

Signals MUST be registered in `apps.py` `ready()`. Never in `models.py` or `views.py`.

```python
# referral/apps.py
class ReferralConfig(AppConfig):
    name = 'referral'
    def ready(self):
        import referral.signals  # noqa: F401
```

**Notifications MUST be created only inside `referral/signals.py` — never in views.**

**✅ CORRECT:**
```python
# referral/signals.py only
@receiver(post_save, sender=ReferralSent)
def handle_referral_state_change(sender, instance, created, **kwargs):
    if created:
        Notification.objects.create(recipient=..., notification_type=NotificationType.REFERRAL_RECEIVED, ...)
```

**❌ WRONG:**
```python
# In any view — never create Notification directly
Notification.objects.create(...)
```

---

**Referral UUID — Canonical Pattern:**

Generated once at `ReferralSent` creation. `ReferralReceived` copies it. Never regenerated.

```python
class ReferralSent(TimeStampedModel, UserTrackingMixin):
    referral_uuid = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
```

Both records created in one atomic transaction:
```python
with transaction.atomic():
    sent     = ReferralSent.objects.create(referral_uuid=new_uuid, snapshot_data=build_patient_snapshot(patient), ...)
    received = ReferralReceived.objects.create(referral_uuid=new_uuid, snapshot_data=build_patient_snapshot(patient), ...)
```

---

### Process Patterns

**Subscription Check — Middleware Only. Never duplicate in views.**

**✅ CORRECT — views have no subscription check:**
```python
@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='patient-manager', error_message='...')
def patient_add(request):
    ...  # middleware already handled subscription gate
```

**❌ WRONG:**
```python
def patient_add(request):
    if request.institution.subscription_status != 'ACTIVE':  # never duplicate middleware logic
        ...
```

---

**Context Processor Variables — Template Access Rules:**

**✅ CORRECT:**
```django
{{ active_institution.name }}
{{ active_institution.logo.url }}
{% if is_superadmin %}...{% endif %}
{% if user_type == 'ADMIN' %}...{% endif %}
```

**❌ WRONG:**
```django
{{ request.user.institution.name }}    {# breaks SUPERADMIN context switching #}
{% if request.user.is_superuser %}...{% endif %}  {# use is_superadmin instead #}
```

---

**Cross-Institution Audit — Both Institutions in One Atomic Transaction:**

```python
with transaction.atomic():
    patient.institution = destination
    patient.save()
    AuditLog.objects.create(institution=source, action='PATIENT_MOVED_OUT', ...)
    AuditLog.objects.create(institution=destination, action='PATIENT_MOVED_IN', ...)
    Notification.objects.bulk_create([source_admin_note, dest_admin_note])
```

---

### Enforcement Guidelines

**All AI Agents MUST:**

1. Call `.for_institution(request.institution)` on every queryset in every institution-scoped view
2. Use `active_institution`, `user_type`, `is_superadmin` from context processor in all templates
3. Register signals in `apps.py` `ready()` — never in `models.py` or `views.py`
4. Create Notifications only in `referral/signals.py` — never directly in views
5. Wrap dual `ReferralSent` + `ReferralReceived` creation in `transaction.atomic()`
6. Call `build_patient_snapshot(patient)` from `referral/utils.py` for all snapshots
7. Use `get_institution_video_path` / `get_institution_attachment_path` for all institution-scoped `upload_to`
8. Never add subscription checks in views — middleware is the sole enforcement point
9. Log cross-institution events at BOTH institutions in a single `transaction.atomic()`
10. Share `referral_uuid` between `ReferralSent` and `ReferralReceived` — never regenerate

**Isolation Test Requirement (NFR19):** `institution/tests/test_isolation.py` MUST verify
that no query, view, or export returns data outside the active institution scope.
These tests must pass before `MULTI_INSTITUTION_ENABLED=True` on any environment.

**Anti-Patterns:**

| Anti-Pattern | Correct Pattern |
|-------------|-----------------|
| `Patient.objects.all()` in scoped view | `Patient.objects.for_institution(request.institution)` |
| `Notification.objects.create()` in view | Create only in `referral/signals.py` |
| Subscription check in view | `InstitutionContextMiddleware` only |
| `request.user.institution` in template | `{{ active_institution }}` from context processor |
| New `uuid.uuid4()` for `ReferralReceived` | Copy `referral_uuid` from `ReferralSent` |
| Snapshot built inline in view | `build_patient_snapshot(patient)` from `referral/utils.py` |
| Signal handler in `models.py` | `apps.py` `ready()` → `signals.py` handler |
| Single audit log for patient move | Dual entries in `transaction.atomic()` |

---

## Project Structure & Boundaries

### Complete Project Directory Structure

_Legend: [NEW] = new file/directory · [MOD] = modified existing file · (existing) = unchanged_

```
NDAS/
├── CLAUDE.md                                       (existing)
├── manage.py                                       (existing)
├── requirements.txt                                (existing — no new packages)
├── .env                                            [MOD] + MULTI_INSTITUTION_ENABLED
│
├── ndas/
│   ├── settings.py                                 [MOD] INSTALLED_APPS, MIDDLEWARE, CONTEXT_PROCESSORS, MULTI_INSTITUTION_ENABLED
│   ├── urls.py                                     [MOD] include institution.urls, referral.urls
│   ├── wsgi.py                                     (existing)
│   └── custom_codes/
│       ├── Custom_abstract_class.py                (existing)
│       ├── choice.py                               [MOD] + UserType, SubscriptionStatus, ReferralStatus, NotificationType
│       ├── validators.py                           [MOD] + get_institution_video_path, get_institution_attachment_path
│       ├── sanitization.py                         (existing)
│       ├── custom_methods.py                       (existing)
│       ├── ndas_enums.py                           (existing)
│       ├── delete_helpers.py                       (existing)
│       ├── security_middleware.py                  (existing)
│       └── error_handlers.py                       (existing)
│
├── institution/                                    [NEW]
│   ├── __init__.py
│   ├── apps.py                                     InstitutionConfig — ready() registers signals
│   ├── context_processors.py                       institution_context → active_institution, user_type, is_superadmin
│   ├── managers.py                                 InstitutionScopedManager (for_institution / all_institutions)
│   ├── middleware.py                               InstitutionContextMiddleware — replaces SubscriptionCheckMiddleware
│   ├── models.py                                   Institution model
│   ├── templatetags/
│   │   ├── __init__.py
│   │   └── institution_tags.py                     {% superadmin_overlay %}
│   ├── migrations/
│   │   ├── 0001_initial.py                         Institution table
│   │   └── 0002_default_institution_data.py        Data migration — existing records → default_institution
│   ├── tests/
│   │   ├── test_isolation.py                       NFR19 — mandatory isolation checks
│   │   ├── test_middleware.py                      Context resolution, subscription gate, grace period
│   │   └── test_models.py                          Slug immutability, subscription logic
│   ├── urls.py
│   └── views.py                                    institution_selector, institution_add, institution_admin_dashboard,
│                                                    superadmin_dashboard, superadmin_patient_move
│
├── referral/                                       [NEW]
│   ├── __init__.py
│   ├── apps.py                                     ReferralConfig — ready() imports referral.signals
│   ├── models.py                                   ReferralSent, ReferralReceived, ReferralMessage, Notification
│   ├── signals.py                                  All signal handlers — ONLY place Notifications are created
│   ├── utils.py                                    build_patient_snapshot(patient) — sole snapshot builder
│   ├── migrations/
│   │   └── 0001_initial.py
│   ├── tests/
│   │   ├── test_referral_lifecycle.py
│   │   ├── test_notifications.py
│   │   └── test_snapshot.py
│   ├── urls.py
│   └── views.py                                    referral_inbox, referral_send, referral_thread,
│                                                    referral_reply, referral_close, notification_count
│
├── patients/                                       [MOD] institution FK + InstitutionScopedManager
│   ├── models.py                                   [MOD] + institution FK + objects = InstitutionScopedManager()
│   ├── views.py                                    [MOD] all querysets → .for_institution(request.institution)
│   ├── urls.py                                     (existing)
│   ├── migrations/
│   │   └── 0XXX_add_institution_fk.py              [NEW]
│   └── tests/                                      (existing)
│
├── users/                                          [MOD] CustomUser extended
│   ├── models.py                                   [MOD] + institution FK + user_type; Subscription deprecated
│   ├── views.py                                    [MOD] user creation forms updated for institution binding
│   ├── urls.py                                     (existing)
│   ├── migrations/
│   │   └── 0XXX_add_user_type_institution.py       [NEW]
│   └── tests/                                      (existing)
│
├── video/                                          [MOD] institution-aware upload_to
│   ├── models.py                                   [MOD] Video.file upload_to → get_institution_video_path
│   ├── views.py                                    [MOD] querysets → .for_institution(request.institution)
│   ├── urls.py                                     (existing)
│   ├── migrations/
│   │   └── 0XXX_update_video_paths.py              [NEW]
│   └── tests/                                      (existing)
│
├── reports/                                        [MOD] branding + 3-scope reports
│   ├── utils/
│   │   ├── pdf_generator.py                        [MOD] BasePDFGenerator accepts active_institution branding
│   │   └── excel_generator.py                      [MOD] + per_institution_aggregate() + cross_institution_aggregate()
│   ├── views.py                                    [MOD] querysets + pass active_institution to generators
│   ├── urls.py                                     (existing)
│   └── tests/                                      (existing)
│
├── problemlist/                                    [MOD] querysets updated
│   ├── models.py                                   (existing — Problem FK to Patient, inherits scope)
│   ├── views.py                                    [MOD] querysets → .for_institution(request.institution)
│   ├── urls.py                                     (existing)
│   └── tests/                                      (existing)
│
├── templates/
│   ├── src/
│   │   ├── base.html                               [MOD] institution branding, {% superadmin_overlay %}, HTMX bell
│   │   ├── basic_plane.html                        (existing)
│   │   ├── form_error.html                         (existing)
│   │   └── partials/
│   │       └── delete_confirmation_modal.html      (existing)
│   ├── institution/                                [NEW]
│   │   ├── selector.html                           God-view institution card grid
│   │   ├── add.html                                Atomic institution + first admin form
│   │   ├── edit.html                               Institution settings
│   │   ├── admin_dashboard.html                    Four-quadrant admin dashboard
│   │   └── superadmin_dashboard.html               Cross-institution analytics
│   ├── referral/                                   [NEW]
│   │   ├── inbox.html                              Split-panel inbox
│   │   ├── thread.html                             HTMX-loaded thread panel
│   │   ├── send.html                               New referral form
│   │   └── patient_tab.html                        Patient Referrals tab timeline
│   ├── patients/                                   (existing)
│   ├── users/                                      (existing)
│   ├── video/                                      (existing)
│   ├── reports/                                    (existing)
│   └── problemlist/                                (existing)
│
└── media/
    └── {institution_slug}/                         [NEW] physical file partitioning
        ├── videos/
        └── attachments/
```

### Architectural Boundaries

**App Dependency Rules (no reverse imports):**

```
institution/  ←  patients/    institution/ provides the base; others build on it
institution/  ←  video/       institution/ MUST NOT import from any app it underlies
institution/  ←  reports/
institution/  ←  problemlist/
institution/  ←  referral/    referral depends on institution, not vice versa
institution/  ←  users/       CustomUser gets institution FK
patients/     ←  users/       existing dependency preserved
```

**Middleware Stack (updated — position 13 replaced):**

| Position | Middleware | Notes |
|----------|-----------|-------|
| 1 | SecurityMiddleware | (existing) |
| 2 | WhiteNoiseMiddleware | (existing) |
| 3 | CSPMiddleware | (existing) |
| 4 | AdditionalSecurityHeadersMiddleware | (existing) |
| 5 | SessionMiddleware | (existing) |
| 6 | CommonMiddleware | (existing) |
| 7 | CsrfViewMiddleware | (existing) |
| 8 | AuthenticationMiddleware | (existing) |
| 9 | UserActivityMiddleware | (existing) |
| 10 | MessageMiddleware | (existing) |
| 11 | XFrameOptionsMiddleware | (existing) |
| 12 | UserAgentMiddleware | (existing) |
| **13** | **InstitutionContextMiddleware** | **[REPLACES SubscriptionCheckMiddleware]** |
| 14 | SecurityHeadersValidationMiddleware | production only (existing) |

### Requirements to Structure Mapping

| FR | File(s) |
|----|---------|
| FR45 (data isolation) | `institution/managers.py` + all app `views.py` |
| FR46 (file isolation) | `ndas/custom_codes/validators.py` (path generators) |
| FR47 (user binding) | `users/models.py` + `institution/middleware.py` |
| FR48 (per-institution subscription) | `institution/models.py` + `institution/middleware.py` |
| FR49 (migration path) | `ndas/settings.py` + `institution/migrations/0002_*.py` |
| FR50 (god-view dashboard) | `institution/views.py` + `templates/institution/selector.html` |
| FR51 (context switching) | `institution/middleware.py` + `institution/templatetags/institution_tags.py` |
| FR52 (atomic onboarding) | `institution/views.py` + `templates/institution/add.html` |
| FR53 (aggregate analytics) | `institution/views.py` + `templates/institution/superadmin_dashboard.html` |
| FR54 (aggregate reports) | `reports/utils/excel_generator.py` + `reports/utils/pdf_generator.py` |
| FR55 (patient move) | `institution/views.py` (superadmin_patient_move) |
| FR56 (admin dashboard) | `institution/views.py` + `templates/institution/admin_dashboard.html` |
| FR57 (user management) | `institution/views.py` + `users/views.py` |
| FR58 (logo upload) | `institution/views.py` (institution_edit) |
| FR59 (PDF branding) | `reports/utils/pdf_generator.py` |
| FR60–61 (referral + snapshot) | `referral/views.py` + `referral/utils.py` |
| FR62–63 (thread + inbox) | `referral/views.py` + `templates/referral/inbox.html` + `templates/referral/thread.html` |
| FR64 (lifecycle) | `referral/models.py` + `referral/views.py` |
| FR65 (patient referral tab) | `referral/views.py` + `templates/referral/patient_tab.html` |
| FR66 (dual records) | `referral/models.py` (ReferralSent + ReferralReceived) |
| FR67–69 (notifications) | `referral/signals.py` |
| FR70 (bell icon / 120s) | `templates/src/base.html` + `referral/views.py` (notification_count) |
| NFR19 (isolation tests) | `institution/tests/test_isolation.py` |
| NFR21 (feature flag) | `ndas/settings.py` + `institution/middleware.py` |
| NFR22 (referral atomicity) | `referral/views.py` (`transaction.atomic()`) |
| NFR23 (120s notifications) | `templates/src/base.html` (`hx-trigger="every 60s"`) |

### Data Flow

**Standard Institution-Scoped Request:**
```
Browser → Nginx → Gunicorn → Django Middleware Stack
→ InstitutionContextMiddleware sets request.institution
→ View calls .for_institution(request.institution)
→ InstitutionScopedManager filters queryset
→ Django ORM → PostgreSQL
→ Template uses {{ active_institution }} from context processor
→ Response
```

**Cross-Institution Referral Creation:**
```
referral_send view
→ build_patient_snapshot(patient)         [referral/utils.py]
→ transaction.atomic():
    ReferralSent.create(institution=A)
    ReferralReceived.create(institution=B, same UUID)
→ post_save signal                         [referral/signals.py]
→ Notification.create(recipient=B_clinician)
→ B_clinician bell polls /notification/count/ within 60s
```

**Superadmin Context Switch:**
```
POST /institution/switch/<id>/
→ session['active_institution_id'] = selected_id
→ Full page reload
→ InstitutionContextMiddleware reads new session value
→ Persistent banner: "Viewing as: [Institution] [Switch ▼]"
→ All subsequent views scoped to selected institution
```

---

## Architecture Validation Results

### Coherence Validation ✅

All decisions are mutually compatible and non-contradictory:
- Explicit `.for_institution()` pattern is consistent with `upload_to` callable approach — no
  thread-local is used anywhere in Phase 2; both are explicit injection patterns
- SUPERADMIN carrying `is_superuser=True` preserves all 37 Phase 1 permission checks without
  any modification
- `referral/` app FK dependency on `institution/` is unidirectional — `institution/` imports
  nothing from `referral/`; dependency graph is acyclic
- Feature flag gates `InstitutionContextMiddleware` only — when disabled, system behaviour is
  identical to pre-Phase-2 deployment
- Notification creation exclusively in `referral/signals.py` ensures no view can bypass
  delivery on any referral state transition

**Implementation note:** `institution_context` context processor must guard anonymous requests:
```python
def institution_context(request):
    if not request.user.is_authenticated:
        return {}
```

### Requirements Coverage Validation ✅

All 26 Phase 2 FRs (FR45–FR70) are architecturally supported with specific file mappings.
All 5 Phase 2 NFRs (NFR19–NFR23) are addressed:
- NFR19: three-layer defence (InstitutionScopedManager + middleware + `test_isolation.py`)
- NFR20: row-level isolation — institution growth is a data operation, not infrastructure
- NFR21: `MULTI_INSTITUTION_ENABLED` with single coupling point in middleware
- NFR22: `transaction.atomic()` wrapping dual ReferralSent + ReferralReceived creation
- NFR23: `hx-trigger="every 60s"` on bell icon ensures delivery within 120 seconds

Phase 1 FRs (FR1–FR37) and NFRs (NFR1–NFR18) fully preserved. Zero Phase 1 changes
required except adding `.for_institution(request.institution)` to existing querysets.

### Implementation Readiness Validation ✅

- All 9 brainstorming-confirmed decisions documented with rationale
- All 4 collaborative open decisions documented
- Complete file tree annotated NEW / MOD / existing
- All 26 FRs mapped to specific files
- 13-step dependency-ordered implementation sequence defined
- Frozen snapshot JSON schema with `schema_version` field defined
- 4 new TextChoices defined with exact keys
- 10 explicit anti-patterns with correct alternatives

### Gap Analysis Results

| Priority | Gap | Resolution |
|----------|-----|-----------|
| Minor | Context processor anonymous guard | `if not request.user.is_authenticated: return {}` |
| Minor | INSTALLED_APPS order | `institution` before `referral` before dependent apps |
| Minor | Subscription model retirement | 0002 migration copies values; model deprecated, not deleted |

No critical or blocking gaps identified.

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Project context thoroughly analysed (67 project rules, 12 input documents)
- [x] Scale and complexity assessed (Enterprise — 26 Phase 2 FRs + 5 NFRs)
- [x] Technical constraints identified (brownfield, frozen stack, middleware order)
- [x] Cross-cutting concerns mapped (8 concerns)

**Architectural Decisions**
- [x] 9 brainstorming-confirmed decisions documented
- [x] 4 open decisions collaboratively resolved
- [x] Technology stack fully specified — no new packages required
- [x] Integration patterns defined (URL structure, HTMX, signal patterns)

**Implementation Patterns**
- [x] Naming conventions established (URLs, models, views, signals, choices)
- [x] Structure patterns defined (app, test, template directories)
- [x] Communication patterns specified (signals, HTMX polling, UUID sharing)
- [x] Process patterns documented (subscription, context processor, audit trail)
- [x] 10 anti-patterns with correct alternatives

**Project Structure**
- [x] Complete directory tree with all files annotated
- [x] App dependency rules and middleware stack defined
- [x] All 26 FRs mapped to specific files
- [x] Three data flow diagrams documented

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** HIGH

**Key Strengths:**
1. All Phase 2 code is purely additive — zero Phase 1 regression risk
2. Defence-in-depth for NFR19: three independent layers (manager + middleware + test suite)
3. Single point of truth for institution context — no scattered resolution logic
4. No new packages required — zero dependency or compatibility risk
5. 10 explicit anti-patterns prevent the most common AI agent mistakes
6. 13-step dependency-ordered implementation sequence prevents build-order conflicts

**Areas for Future Enhancement (Phase 3):**
- WebSocket/SSE for true real-time notifications (replaces HTMX polling)
- Celery async task for `build_patient_snapshot()` on very large patient records
- Referral snapshot versioning

### Implementation Handoff

**First Implementation Step:**
```bash
python manage.py startapp institution
```
Then follow the 13-step dependency-ordered sequence in the Core Architectural Decisions section.

**AI Agent Guidelines:**
- Read the Implementation Patterns section before writing any Phase 2 code
- Follow the anti-patterns table — violations are security risks (NFR19)
- Every institution-scoped view MUST call `.for_institution(request.institution)` on every queryset
- Run `python manage.py test institution.tests.test_isolation` after every institution-scoped change
- Do not set `MULTI_INSTITUTION_ENABLED=True` in production until staging isolation tests pass
