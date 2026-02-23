---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-01-confirmed
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
workflowStatus: complete
completedDate: '2026-02-23'
epicCount: 5
storyCount: 26
frCoverage: '32/32 Phase 2 FRs'
---

# NDAS - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for NDAS, decomposing the requirements from the PRD and Architecture documents into implementable stories. Scope: **Phase 2 — Multi-Institution Expansion** (institutional isolation + referral system), built on top of Phase 1 (fully operational, FR1–FR37).

---

## Requirements Inventory

### Functional Requirements

#### Phase 1 — Operational (Reference Only — already implemented)

| FR | Description |
|----|-------------|
| FR1 | Clinicians can register a new patient with full demographic, perinatal, and clinical identifier data (BHT, NNC, PTC, PC, PIN, Disk No.) |
| FR2 | Clinicians can view a patient's complete longitudinal record — all assessments, videos, problems, and attachments — in a single view |
| FR3 | Clinicians can search for patients by name, BHT, NNC, PTC, PC, PIN, or Disk No. |
| FR4 | Clinicians can edit existing patient demographic and perinatal data |
| FR5 | Clinicians can attach clinical documents to a patient record |
| FR6 | Clinicians can bookmark patients for personal reference access |
| FR7 | The system enforces clinical validation ranges on all patient data fields (birth weight, gestational age, APGAR scores) |
| FR8 | Patient records are retained permanently with patient consent and cannot be permanently deleted |
| FR9 | Clinicians can create a General Movement Assessment (GMA) linked to a video recording |
| FR10 | Clinicians can create a HINE assessment with structured scoring across all items (0–78) |
| FR11 | Clinicians can create a CDIC record for rehabilitation and intervention centre tracking |
| FR12 | Clinicians can create a General Paediatric Assessment (GPA) |
| FR13 | Clinicians can create a Developmental Assessment scored across four domains (GM, FMV, HSL, SEB) with corrected age reference (0–72 months) |
| FR14 | The system enforces complete data entry on all assessment instruments before a record can be saved as final |
| FR15 | Clinicians can view all assessment records for a patient in chronological order |
| FR16 | Clinicians can edit or delete their own assessment records subject to business rules (superusers can delete any; videos block deletion if assessment-linked) |
| FR17 | Clinicians can upload video files for clinical assessment use |
| FR18 | Clinicians can play back uploaded videos within the clinical interface |
| FR19 | Clinicians can link an uploaded video to a GMA assessment record |
| FR20 | The system prevents deletion of any video linked to an active assessment |
| FR21 | The system validates video file type and size at upload and rejects invalid files |
| FR22 | Clinicians can add clinical problems to a patient's active problem list |
| FR23 | Clinicians can create intervention plans linked to specific problems |
| FR24 | Clinicians can record and update intervention responses over time |
| FR25 | Clinicians can update the status of problems; valid statuses: Active, Resolved, Monitoring, Discontinued |
| FR26 | Clinicians can view the complete problem, intervention, and response history for a patient |
| FR27 | Clinicians can generate a PDF report summarising an individual patient's assessment history |
| FR28 | Clinicians can export assessment data to Excel format |
| FR29 | Clinicians can generate anonymised cohort reports for research use |
| FR30 | Clinicians can filter report data by date range, assessment type, and patient criteria (status, age range, diagnosis) |
| FR31 | Administrators can create, edit, and deactivate user accounts |
| FR32 | Administrators can assign and manage user roles (superuser, staff) |
| FR33 | Administrators can activate, deactivate, and extend user subscriptions and view current subscription status for all accounts within their managed scope |
| FR34 | Administrators can view user activity logs |
| FR35 | The system requires authentication for all clinical routes — no unauthenticated access to patient data |
| FR36 | The system enforces role-based access — superusers access all patient records, assessments, and user accounts system-wide; staff access only records they have registered or to which they are explicitly assigned |
| FR37 | The system automatically records the identity and timestamp of every record creation and modification |

#### Phase 2 — Multi-Institution Expansion (To Be Implemented)

**Notifications & Communication**

| FR | Description |
|----|-------------|
| FR38 | Clinicians can view a personal notification panel displaying alerts for referrals received, replies to referrals they have sent, and referral closure events; each notification links to the relevant patient record or referral thread |
| FR40 | Clinicians can submit a structured referral to another clinician or specialist |
| FR41 | Clinicians can view referrals they have received, reply with a clinical opinion, and close the referral thread — all within the referral inbox interface |

**Dashboards & Multi-Centre**

| FR | Description |
|----|-------------|
| FR42 | Each user role has access to a role-specific dashboard — clinician view, institutional view, or system-wide admin view |
| FR43 | The system serves multiple clinical institutions from a single deployed instance; institution-specific administration is provided through the superadmin capabilities (FR50–FR55) and institution admin capabilities (FR56–FR59) |
| FR44 | The system scopes patient data, reporting, and dashboards by clinical centre in multi-centre deployments |

**Multi-Institution Foundation**

| FR | Description |
|----|-------------|
| FR45 | The system ensures that all patient data, assessments, reports, and clinical records accessed by a user are restricted to that user's institution — no query or view returns data from outside the active institution's boundary under any access path |
| FR46 | All files uploaded within an institution's context — videos and attachments — are stored in institution-specific isolation such that users and processes operating in a different institution cannot access them through the application interface or by direct URL |
| FR47 | The system binds every non-superadmin user to exactly one institution — a user cannot access patient data, assessments, or reports outside their bound institution |
| FR48 | Each institution has an independent subscription status — grace period grants read-only access; active referrals are excluded from read-only restrictions and continue to completion |
| FR49 | The system supports a controlled migration path — multi-institution capability can be enabled or disabled without redeployment or data loss; when disabled, all behaviour is identical to the pre-Phase-2 single-institution deployment |

**Superadmin Capabilities**

| FR | Description |
|----|-------------|
| FR50 | The superadmin can view all institutions on a single dashboard showing subscription status, user count, patient count, and last activity for each institution |
| FR51 | The superadmin can switch institution context via a persistent on-screen selector — all subsequent views and data are scoped to the selected institution |
| FR52 | The superadmin can onboard a new institution by submitting one form that creates the institution record and the first ADMIN account atomically — no institution record exists without a corresponding admin account |
| FR53 | The superadmin can view cross-institution aggregate analytics: assessment volumes, referral activity, user counts, and subscription health across all institutions |
| FR54 | The superadmin can export cross-institution aggregate reports in Excel and PDF formats at three scopes: per-patient, per-institution aggregate, and cross-institution aggregate |
| FR55 | The superadmin can move a patient between institutions via a multi-step confirmation flow — impact preview → institution-name confirmation → atomic transfer with audit log entries at both institutions and notifications to both admins |

**Institution Admin Capabilities**

| FR | Description |
|----|-------------|
| FR56 | Institution admins can view a role-specific dashboard showing patient stats by status, assessment activity by type for the current month, referral activity (sent/received/pending/closed), and team activity — all scoped to their institution |
| FR57 | Institution admins can create USER accounts within their own institution and deactivate existing accounts |
| FR58 | Institution admins can upload an institution logo and manage institution display settings |
| FR59 | All PDF reports generated within an institution's context include the institution logo, name, and header |

**Referral System**

| FR | Description |
|----|-------------|
| FR60 | Clinicians can initiate a cross-institution referral by selecting a receiving institution, a receiving clinician, and a referral message — the system automatically attaches a frozen snapshot of the patient record at submission time |
| FR61 | The frozen patient snapshot captures the full patient profile (demographics, perinatal data, all assessment scores and records) at the moment of referral; subsequent updates to the originating record do not alter the snapshot |
| FR62 | Clinicians can view and reply to referral threads they have received — each thread displays a fixed patient header, the frozen snapshot as a collapsible panel, and alternating entries with clinician name, institution badge, and timestamp |
| FR63 | Clinicians can view all referrals (sent and received) in a unified inbox: thread list with patient thumbnail, referring institution, date, and unread indicator on the left; active thread on the right |
| FR64 | Referrals progress through a defined lifecycle: PENDING → REPLIED → CLOSED; status is visible at a glance on all referral list views |
| FR65 | The patient detail view includes a Referrals tab showing a timeline of all outgoing and incoming referrals for that patient: direction, clinician, institution, status, and outcome |
| FR66 | Both the sending and receiving institution retain an independent referral record linked by a shared UUID — deletion or suspension of one institution does not destroy the other institution's consultation record |

**Referral Notifications**

| FR | Description |
|----|-------------|
| FR67 | The system notifies the receiving clinician when a new referral arrives at their institution |
| FR68 | The system notifies the sending clinician when a referral they submitted receives a reply |
| FR69 | The system notifies both clinicians and both institution admins when a referral is closed |
| FR70 | Clinicians can view unread notification count in the navigation bar; the count refreshes automatically within 120 seconds without navigating away from the current page |

---

### NonFunctional Requirements

#### Phase 1 NFRs (Reference Only — already met by existing system)

| NFR | Category | Description |
|-----|----------|-------------|
| NFR1 | Performance | Standard page views (patient list, assessment forms) load within 2 seconds on a typical hospital intranet connection |
| NFR2 | Performance | Video playback begins within 5 seconds of initiating playback under hospital network conditions |
| NFR3 | Performance | The system supports a minimum of 20 concurrent users without measurable performance degradation |
| NFR4 | Performance | Video uploads up to 2GB are handled asynchronously — upload progress is visible and does not block other user operations |
| NFR5 | Security | All patient data is transmitted exclusively over HTTPS (TLS) — unencrypted clinical data in transit is not permitted |
| NFR6 | Security | User sessions expire after 60 minutes of inactivity and immediately on browser close |
| NFR7 | Security | All 24 CRUD operations are rate-limited (10/min for create/edit, 5/min for delete) to prevent automated abuse |
| NFR8 | Security | All user input is sanitised prior to storage — XSS vectors and injection attacks are neutralised without loss of clinical notation |
| NFR9 | Security | File uploads are validated by MIME type and file size at ingestion — invalid or oversized files are rejected before storage |
| NFR10 | Security | All HTTP responses include security headers — Content Security Policy, anti-clickjacking, and transport security directives applied consistently |
| NFR11 | Reliability | The system maintains 99% uptime during clinic operating hours (08:00–18:00, Monday–Saturday) |
| NFR12 | Reliability | Patient data is recoverable following system failure — RPO: ≤ 24 hours; RTO: ≤ 4 hours; automated daily backups required |
| NFR13 | Reliability | All multi-step record operations complete atomically — no partial saves are possible |
| NFR14 | Scalability | The system architecture supports deployment across multiple clinical centres without per-centre code changes |
| NFR15 | Scalability | The system supports growth from single-centre to multi-institution deployment without re-architecture of the core application |
| NFR16 | Audit | Every record creation, modification, and attempted deletion is logged with user identity and timestamp — the audit trail is permanent and cannot be edited or deleted |
| NFR17 | Audit | Hard deletion of clinical records is restricted — superuser authority and business rule validation are required |
| NFR18 | Accessibility | The system meets WCAG 2.1 Level AA accessibility standards — keyboard navigation, screen reader compatibility, colour contrast ratios (4.5:1 normal text, 3:1 large text) |

#### Phase 2 NFRs (To Be Implemented)

| NFR | Category | Description |
|-----|----------|-------------|
| NFR19 | Multi-Institution | Zero cross-institution data leakage — automated isolation tests must confirm that no query, view, or report returns data outside the active institution's scope before multi-institution mode is enabled in production; any leakage incident constitutes a blocking defect |
| NFR20 | Multi-Institution | The system supports a minimum of 20 concurrent institutions without additional infrastructure — institution count growth requires no new servers, databases, or code deployments |
| NFR21 | Multi-Institution | Multi-institution capability deactivation restores single-institution behaviour completely — all multi-institution capabilities are inactive when disabled, verified by the existing regression test suite |
| NFR22 | Multi-Institution | Referral record creation across the sending and receiving institution is atomic — either both institution records are created or neither is; no partial referral state is possible under any failure condition |
| NFR23 | Multi-Institution | Referral event notifications (REFERRAL_RECEIVED, REFERRAL_REPLIED, REFERRAL_CLOSED) are delivered within 120 seconds of the triggering event; no notification is silently dropped |

---

### Additional Requirements

*Technical implementation requirements derived from the Architecture document that directly shape epics and stories:*

**App Structure**
- New `institution/` Django app must be created with: Institution model, InstitutionContextMiddleware, InstitutionScopedManager, context_processors.py, templatetags/institution_tags.py, migrations/, tests/
- New `referral/` Django app must be created with: ReferralSent, ReferralReceived, ReferralMessage, Notification models, signals.py, utils.py (build_patient_snapshot), migrations/, tests/
- `institution/` app must have no reverse imports from any app it underlies (patients/, video/, reports/, problemlist/, referral/, users/)

**Data Models**
- Institution model fields: name, slug (immutable after creation), logo, subscription_status (ACTIVE/GRACE/EXPIRED), grace_period_end, is_active, created_by FK, inherits TimeStampedModel
- CustomUser extended with: institution FK (nullable for SUPERADMIN only), user_type CharField using UserType TextChoices (SUPERADMIN/ADMIN/USER)
- ReferralSent: institution FK, patient FK, from_institution, to_institution, from_clinician, to_clinician, referral_uuid (UUID4, db_index), status (PENDING/REPLIED/CLOSED), snapshot_data JSONField, outcome
- ReferralReceived: linked by same referral_uuid; self-contained copy of snapshot_data; FK to receiving institution
- ReferralMessage: FK to referral via UUID, sender, body, timestamp, message_type (OPINION)
- Notification: recipient FK, notification_type (REFERRAL_RECEIVED/REFERRAL_REPLIED/REFERRAL_CLOSED), title, body, link, is_read, created_at; institution-scoped
- All new models inherit TimeStampedModel + UserTrackingMixin
- New TextChoices added to ndas/custom_codes/choice.py: UserType, SubscriptionStatus, ReferralStatus, NotificationType

**Middleware**
- InstitutionContextMiddleware inserts at position 13, replacing SubscriptionCheckMiddleware
- Context resolution: ADMIN/USER → request.institution = request.user.institution; SUPERADMIN → request.institution = session['active_institution_id']; SUPERADMIN with no context → redirect to institution selector
- Subscription enforcement exclusively in middleware (grace=read-only, expired=login blocked, active referrals exempt); never duplicated in views
- Feature flag MULTI_INSTITUTION_ENABLED in settings.py; when False, system behaves identically to pre-Phase-2

**ORM & Data Isolation**
- InstitutionScopedManager with for_institution(institution) and all_institutions() methods added to institution/managers.py
- Every model with an institution FK must use InstitutionScopedManager as objects manager
- All institution-scoped views must call .for_institution(request.institution) — never .all() or inline .filter(institution=...)
- Superadmin aggregate queries use .all_institutions() explicitly

**File Storage**
- get_institution_video_path and get_institution_attachment_path callables added to ndas/custom_codes/validators.py
- All FileField upload_to in video/ and patients/ apps updated to use these callables
- Physical files partitioned to MEDIA_ROOT/{institution_slug}/videos/ and MEDIA_ROOT/{institution_slug}/attachments/

**Data Migration**
- Single atomic Django data migration migrates all existing patients, assessments, videos, attachments, and users to default_institution
- Existing Subscription singleton values copied to default_institution fields before retirement
- Existing file paths migrated to /{default_institution_slug}/ directory structure
- MULTI_INSTITUTION_ENABLED=False until staging isolation tests pass

**Referral Atomicity**
- ReferralSent + ReferralReceived created together inside transaction.atomic() (NFR22)
- referral_uuid generated once at ReferralSent creation; ReferralReceived copies it — never regenerated
- build_patient_snapshot(patient) called once at ReferralSent creation; snapshot is immutable thereafter

**Notifications**
- Notifications created exclusively in referral/signals.py via Django post_save signals
- Signals registered in apps.py ready() — never in models.py or views.py
- HTMX polling hx-trigger="every 60s" on navbar bell icon targets #notification-bell-count
- Bell icon endpoint: hx-get="/referral/notifications/count/"

**Templates & Frontend**
- institution_context context processor injects active_institution, user_type, is_superadmin into all templates
- Persistent superadmin overlay banner rendered via {% superadmin_overlay %} template tag in src/base.html
- Referral inbox: AdminLTE card split-panel (thread list left, active thread right, HTMX-loaded)
- Frozen snapshot rendered as collapsible <details> panel within thread view
- All new templates extend src/base.html; naming: manager.html / add.html / edit.html / view.html

**Reports**
- BasePDFGenerator extended to inject active institution logo, name, header into all PDF output
- ExcelReportGenerator extended with per_institution_aggregate() and cross_institution_aggregate() scopes

**View Pattern**
- All new views: function-based with mandatory decorator stack @login_required → @require_http_methods → @ratelimit → @handle_view_errors
- No new Python packages required

**13-Step Dependency-Ordered Implementation Sequence (from Architecture)**
1. institution app — Institution model + migrations
2. CustomUser extensions — institution FK + user_type field + migrations
3. InstitutionContextMiddleware — replaces SubscriptionCheckMiddleware
4. InstitutionScopedManager — add to all institution-FK models
5. Institution-aware upload_to callables — update all FileField upload_to functions
6. Data migration — atomic migration of existing data to default_institution
7. referral app — Referral + Notification models
8. Superadmin views + god-view dashboard
9. Institution admin views + dashboard
10. Referral inbox + thread UI
11. Signal-driven notifications + HTMX bell icon
12. PDF/Excel branding extensions
13. Isolation test suite + feature flag enable on staging

---

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR38 | Epic 5 | Notification panel with referral alerts |
| FR40 | Epic 4 | Submit structured referral |
| FR41 | Epic 4 | Receive, reply, close referral thread |
| FR42 | Epics 2 & 3 | Role-specific dashboards (superadmin / admin) |
| FR43 | Epic 1 | Single instance multi-institution serving |
| FR44 | Epic 1 | Data/reporting scoped by clinical centre |
| FR45 | Epic 1 | Institution-scoped data access isolation |
| FR46 | Epic 1 | Institution-scoped file storage isolation |
| FR47 | Epic 1 | User-to-institution binding |
| FR48 | Epic 1 | Per-institution subscription status |
| FR49 | Epic 1 | Controlled migration path (feature flag) |
| FR50 | Epic 2 | Superadmin god-view dashboard |
| FR51 | Epic 2 | Superadmin institution context switching |
| FR52 | Epic 2 | Atomic institution + admin onboarding form |
| FR53 | Epic 2 | Cross-institution aggregate analytics |
| FR54 | Epic 2 | Cross-institution aggregate reports (3 scopes) |
| FR55 | Epic 2 | Patient move between institutions |
| FR56 | Epic 3 | Institution admin dashboard (4 quadrants) |
| FR57 | Epic 3 | Institution admin: create/deactivate clinicians |
| FR58 | Epic 3 | Institution logo upload & display settings |
| FR59 | Epic 3 | Institution branding in PDF reports |
| FR60 | Epic 4 | Initiate cross-institution referral + snapshot |
| FR61 | Epic 4 | Frozen patient snapshot at referral time |
| FR62 | Epic 4 | View/reply to referral thread |
| FR63 | Epic 4 | Unified referral inbox |
| FR64 | Epic 4 | Referral lifecycle: PENDING→REPLIED→CLOSED |
| FR65 | Epic 4 | Patient Referrals tab (timeline view) |
| FR66 | Epic 4 | Dual institution referral records via UUID |
| FR67 | Epic 5 | Notification: referral received |
| FR68 | Epic 5 | Notification: referral reply |
| FR69 | Epic 5 | Notification: referral closed (both parties) |
| FR70 | Epic 5 | Navbar bell with 120-second auto-refresh |

---

## Epic List

### Epic 1: Institution Foundation & Safe Data Isolation
The system can serve multiple institutions from a single deployment with guaranteed data isolation. Clinicians and admins log in knowing their institution's data is completely protected — no cross-institution leakage is possible under any access path. The existing single-institution deployment migrates safely to become the first institution in the network.
**FRs covered:** FR43, FR44, FR45, FR46, FR47, FR48, FR49

### Epic 2: Superadmin Network Operations
The platform operator (superadmin) can onboard a new institution in under 5 minutes via a single form, monitor subscription health and activity across the entire network from a god-view dashboard, switch into any institution's context, export cross-institution reports, and move patients between institutions — all without developer involvement.
**FRs covered:** FR42 *(superadmin role dashboard)*, FR50, FR51, FR52, FR53, FR54, FR55

### Epic 3: Institution Admin Self-Management
Institution admins can independently manage their clinical team, create and deactivate clinician accounts, monitor patient and assessment activity, personalise their institution's branding, and ensure all PDF reports carry their institution's identity — with no superadmin intervention needed for day-to-day operations.
**FRs covered:** FR42 *(admin role dashboard)*, FR56, FR57, FR58, FR59

### Epic 4: Cross-Institution Clinical Referrals
Clinicians can send structured referrals to specialists at other institutions on the network, attaching a frozen snapshot of the patient's complete clinical record at the time of referral. The receiving specialist can view the snapshot, reply with their clinical opinion in a documented consultation thread, and the originating clinician can close the referral — the full consultation permanently recorded in the patient's record.
**FRs covered:** FR40, FR41, FR60, FR61, FR62, FR63, FR64, FR65, FR66

### Epic 5: Referral Notifications & Real-Time Awareness
Clinicians are notified of all referral events (new referral received, reply from specialist, referral closed) via an in-app notification panel that updates automatically within 120 seconds — no manual refresh or navigation required. The notification count is visible in the navbar at all times.
**FRs covered:** FR38, FR67, FR68, FR69, FR70

---

---

## Epic 1: Institution Foundation & Safe Data Isolation

The system can serve multiple institutions from a single deployment with guaranteed data isolation. Clinicians and admins log in knowing their institution's data is completely protected — no cross-institution leakage is possible under any access path. The existing single-institution deployment migrates safely to become the first institution in the network.

### Story 1.1: Institution Model & App Bootstrap

As a **platform operator**,
I want the system to have an Institution entity with a name, immutable slug, and subscription status,
So that multiple distinct clinical institutions can exist as data-isolated tenants within a single deployment.

**Acceptance Criteria:**

**Given** the `institution/` Django app is created and registered in `INSTALLED_APPS`
**When** a new Institution is saved with name, slug, and subscription_status
**Then** the record is persisted with `TimeStampedModel` fields (created_at, updated_at) and `UserTrackingMixin` fields (added_by, last_edit_by)
**And** `SubscriptionStatus` choices (ACTIVE/GRACE/EXPIRED) exist in `ndas/custom_codes/choice.py`

**Given** an Institution has been saved with a slug value
**When** an attempt is made to change the slug and save again
**Then** the `save()` override raises a `ValidationError` blocking the change, and the slug remains unchanged

**Given** `MULTI_INSTITUTION_ENABLED=False` in `settings.py`
**When** any request is processed by the application
**Then** the system behaves identically to the pre-Phase-2 single-institution deployment with no new behaviour active

---

### Story 1.2: User Institution Binding & Role Extension

As a **clinician or institution admin**,
I want my user account to be bound to exactly one institution,
So that my access is always scoped to my institution and I can never see data from other institutions.

**Acceptance Criteria:**

**Given** `UserType` choices (SUPERADMIN/ADMIN/USER) are added to `ndas/custom_codes/choice.py`
**When** a `CustomUser` record is created with any `user_type` value
**Then** the field is persisted correctly and the user_type is queryable

**Given** a `CustomUser` with `user_type=USER` or `user_type=ADMIN`
**When** the user's `institution` FK is set to a specific institution
**Then** the user is bound to that institution and cannot be reassigned to another institution without explicit superadmin action

**Given** a `CustomUser` with `user_type=SUPERADMIN`
**When** the `institution` FK is null
**Then** the model saves without error (nullable FK is valid for SUPERADMIN only)

**Given** the migration adding `institution` FK and `user_type` to `CustomUser` is applied
**When** existing user records are migrated
**Then** all existing users have `user_type=USER`, `institution` set to `default_institution`, with zero null institution FKs on non-SUPERADMIN accounts

---

### Story 1.3: Institution Context Middleware

As a **clinician**,
I want every request I make to automatically resolve to my institution's context,
So that all views return only my institution's data without requiring per-view configuration.

**Acceptance Criteria:**

**Given** `InstitutionContextMiddleware` is at position 13 in `MIDDLEWARE`, replacing `SubscriptionCheckMiddleware`
**When** an ADMIN or USER makes any authenticated request
**Then** `request.institution` is set to `request.user.institution` before the view function executes

**Given** a SUPERADMIN has `session['active_institution_id']` set
**When** the SUPERADMIN makes any request
**Then** `request.institution` is set to the institution identified by the session value

**Given** a SUPERADMIN has no `active_institution_id` in session
**When** the SUPERADMIN accesses any institution-scoped view
**Then** the middleware redirects to the institution selector screen

**Given** an institution's `subscription_status` is GRACE
**When** a user makes a GET request
**Then** the request proceeds (read-only access granted)
**And** when the same user makes a POST request that is not part of an active referral thread, the middleware blocks the request

**Given** an institution's `subscription_status` is EXPIRED
**When** any ADMIN or USER attempts to authenticate
**Then** login is blocked and a subscription-expired message is shown

**Given** the `institution_context` context processor is registered in `settings.py`
**When** any authenticated template is rendered
**Then** `active_institution`, `user_type`, and `is_superadmin` are available as template context variables
**And** `{{ request.user.institution }}` is never used directly in templates — only `{{ active_institution }}` from the context processor

---

### Story 1.4: Institution-Scoped ORM Manager & View Updates

As a **clinician**,
I want all patient, video, assessment, and report queries to automatically filter to my institution,
So that cross-institution data is never returned regardless of the access path used.

**Acceptance Criteria:**

**Given** `InstitutionScopedManager` is defined in `institution/managers.py` with `for_institution(institution)` and `all_institutions()` methods
**When** `Patient.objects.for_institution(request.institution)` is called
**Then** only patients belonging to that institution are returned; zero patients from other institutions appear

**Given** `InstitutionScopedManager` is set as the `objects` manager on `Patient` and all other models with an `institution` FK
**When** a clinician from Institution A accesses the patient list, patient detail, video list, or any assessment view
**Then** no Institution B records appear in any response

**Given** a clinician from Institution A requests a patient detail using a `patient_id` that belongs to Institution B
**When** the view executes `get_object_or_404(Patient.objects.for_institution(request.institution), id=pk)`
**Then** a 404 response is returned — not a 403, not the Institution B patient record

**Given** all `patients/`, `video/`, `reports/`, and `problemlist/` views have been updated to call `.for_institution(request.institution)` on every queryset
**When** a SUPERADMIN calls `Patient.objects.all_institutions()` in an aggregate view
**Then** records from all institutions are returned (this is the only permitted cross-institution read)

---

### Story 1.5: Institution-Aware File Storage

As a **clinician**,
I want uploaded videos and documents to be stored in institution-specific directories,
So that files from another institution cannot be accessed through any application interface or direct URL.

**Acceptance Criteria:**

**Given** `get_institution_video_path` and `get_institution_attachment_path` callables are added to `ndas/custom_codes/validators.py`
**When** a video is uploaded within Institution A's context
**Then** the file is stored at `MEDIA_ROOT/{institution_slug}/videos/{sanitized_filename}`

**Given** `get_institution_attachment_path` is set as the `upload_to` on all attachment `FileField` declarations
**When** a document is attached to a patient record in Institution A
**Then** the file is stored at `MEDIA_ROOT/{institution_slug}/attachments/{sanitized_filename}`

**Given** a user from Institution A is authenticated
**When** they attempt to access a media URL for a file stored under Institution B's slug path
**Then** the application returns a 403 or 404 response; the file is not served

---

### Story 1.6: Default Institution Data Migration

As a **platform operator**,
I want all existing patient, user, and file data migrated atomically to a default institution,
So that the existing single-institution deployment becomes the first institution in the multi-institution network with zero data loss.

**Acceptance Criteria:**

**Given** Django data migration `institution/migrations/0002_default_institution_data.py` is applied
**When** the migration runs
**Then** a `default_institution` record is created atomically with the existing `Subscription` singleton's values copied to its subscription fields

**Given** the migration completes successfully
**When** all `Patient` records are queried
**Then** every patient has `institution=default_institution` — zero null `institution` FKs exist

**Given** the migration completes successfully
**When** all `Video` and `Attachment` file paths are checked
**Then** every file reference is updated to `/{default_institution_slug}/videos/` or `/{default_institution_slug}/attachments/`

**Given** all `CustomUser` records (non-SUPERADMIN) are checked after migration
**When** the user queryset is reviewed
**Then** every non-SUPERADMIN user has `institution=default_institution` with no nulls

**Given** `MULTI_INSTITUTION_ENABLED=False` after the migration has been applied
**When** the system processes requests
**Then** behaviour is identical to the pre-Phase-2 single-institution deployment

---

### Story 1.7: Isolation Test Suite & Feature Flag Validation

As a **QA engineer**,
I want an automated test suite that verifies zero cross-institution data leakage across all views and export paths,
So that multi-institution mode can be safely enabled in production with demonstrable confidence.

**Acceptance Criteria:**

**Given** `institution/tests/test_isolation.py` exists and runs as part of `python manage.py test institution`
**When** the suite runs with two institutions each having distinct patient, video, and assessment data
**Then** every institution-scoped view for a clinician from Institution A returns zero records from Institution B

**Given** a clinician from Institution A is authenticated
**When** they access patient list, patient detail, video list, any assessment form, PDF report, and Excel export
**Then** Institution B data does not appear in any response body or exported file content

**Given** a direct URL attack: a clinician from Institution A requests `/patients/{institution_b_patient_id}/view/`
**When** the view executes
**Then** a 404 response is returned — Institution B's patient detail is not accessible

**Given** all isolation tests pass on a staging environment
**When** `MULTI_INSTITUTION_ENABLED` is set to `True` in `settings.py`
**Then** the system operates in full multi-institution mode with all Phase 2 middleware and context resolution active

**Given** `MULTI_INSTITUTION_ENABLED` is set back to `False`
**When** the existing Phase 1 regression test suite runs
**Then** all tests pass — no Phase 1 functionality is broken

---

## Epic 2: Superadmin Network Operations

The platform operator can onboard a new institution in under 5 minutes, monitor subscription health and activity across the entire network, switch into any institution's context, export cross-institution reports, and move patients between institutions — all without developer involvement.

### Story 2.1: Institution Selector Screen

As a **superadmin**,
I want a dashboard showing all institutions as cards with their key metrics,
So that I can monitor the health of the entire network at a glance and navigate into any institution.

**Acceptance Criteria:**

**Given** the superadmin navigates to the institution selector screen (no active institution context in session)
**When** the page loads
**Then** a card grid is displayed showing every institution with: logo (or placeholder), name, subscription status badge, user count, patient count, and last activity timestamp

**Given** an institution has `subscription_status=EXPIRED`
**When** its card is rendered
**Then** a visually distinct status indicator differentiates it from ACTIVE and GRACE institutions

**Given** the superadmin has no `active_institution_id` in session
**When** they access any institution-scoped view
**Then** the middleware redirects them to this selector screen before any institution-scoped data is accessed

**Given** a new institution has just been created via the onboarding form
**When** the superadmin returns to the selector screen
**Then** the new institution card appears without requiring a server restart or cache flush

---

### Story 2.2: Superadmin Institution Context Switching

As a **superadmin**,
I want a persistent banner showing which institution I'm currently viewing, with a dropdown to switch to another,
So that I can operate within any institution's context without logging in as that institution's admin.

**Acceptance Criteria:**

**Given** the superadmin selects an institution from the selector screen
**When** the selection is submitted via POST to the institution switch endpoint
**Then** `session['active_institution_id']` is set to the selected institution's ID and a full page reload occurs

**Given** the superadmin has an active institution context
**When** any authenticated page renders
**Then** the persistent top banner shows "Viewing as: [Institution Name] [Switch ▼]" via `{% superadmin_overlay %}` in `src/base.html`
**And** the banner is only visible when `is_superadmin` is True and an institution context is active

**Given** the superadmin is viewing Institution B's context
**When** they access the patient list, reports, or any data view
**Then** only Institution B's data is visible — the institution context scopes all queries correctly

**Given** the superadmin overlay is active
**When** any patient detail or institution management page renders
**Then** superadmin-only action buttons (Move Patient, Edit Subscription, Suspend User) are injected via the `{% superadmin_overlay %}` template tag
**And** these buttons are not visible to ADMIN or USER role users under any condition

---

### Story 2.3: Atomic Institution Onboarding

As a **superadmin**,
I want to onboard a new institution via a single form that creates the institution and its first admin account simultaneously,
So that a new hospital is live in under 5 minutes with zero possibility of an institution existing without a corresponding admin.

**Acceptance Criteria:**

**Given** the superadmin navigates to `/institution/add/`
**When** the form is submitted with: institution name, slug, first admin name, email, and temporary password
**Then** a `transaction.atomic()` block creates both the `Institution` record and the first `CustomUser` (user_type=ADMIN, institution=new_institution) atomically

**Given** the transaction succeeds
**When** the superadmin is redirected to the selector screen
**Then** the new institution card appears immediately with subscription_status=ACTIVE and user count = 1

**Given** the admin account creation step fails during the transaction
**When** the transaction rolls back
**Then** no orphan `Institution` record exists — either both records are created or neither is

**Given** a slug is submitted that already exists in another institution
**When** form validation runs
**Then** a validation error is shown and no records are created

**Given** a new institution is successfully created
**When** the institution slug is set
**Then** the slug is immutable — any subsequent attempt to change it raises a `ValidationError`

---

### Story 2.4: Cross-Institution Aggregate Analytics Dashboard

As a **superadmin**,
I want a read-only analytics dashboard showing activity and subscription health across all institutions,
So that I can identify institutions needing attention and monitor platform-wide clinical volume.

**Acceptance Criteria:**

**Given** the superadmin accesses the superadmin analytics dashboard
**When** the page loads
**Then** summary cards are shown for every institution: subscription state, user count, assessment volumes for the current month, and referral activity (sent/received/pending/closed)

**Given** the superadmin views the recent events audit log section
**When** events are rendered
**Then** cross-institution events appear in reverse chronological order (institution onboardings, subscription changes, patient moves)

**Given** the dashboard queries use `Patient.objects.all_institutions()` and equivalent cross-institution reads
**When** the queries execute
**Then** institution-scoped filtering is deliberately absent — this is an intentional superadmin aggregate view, not an accidental data leak

**Given** one or more institutions have zero activity this month
**When** their cards are rendered
**Then** zero values are displayed without raising errors — empty state is handled gracefully

---

### Story 2.5: Cross-Institution Aggregate Reports

As a **superadmin**,
I want to export reports at three scopes — per-patient, per-institution aggregate, and cross-institution aggregate,
So that I can provide institutional stakeholders with their own data and maintain an overarching view of network-wide activity.

**Acceptance Criteria:**

**Given** the superadmin selects "per-institution aggregate" scope and a target institution
**When** the export is triggered
**Then** `ExcelReportGenerator.per_institution_aggregate()` generates a workbook containing only that institution's patient and assessment data

**Given** the superadmin selects "cross-institution aggregate" scope
**When** the export is triggered
**Then** `ExcelReportGenerator.cross_institution_aggregate()` generates a workbook spanning all institutions, with per-institution breakdown and a summary sheet

**Given** the superadmin exports a PDF report while viewing an institution's context
**When** `BasePDFGenerator` renders the document
**Then** the active institution's logo, name, and header are injected into the PDF output

**Given** an institution has zero patients at export time
**When** it appears in the cross-institution aggregate export
**Then** its row or sheet shows zeros without raising an exception

---

### Story 2.6: Patient Move Between Institutions

As a **superadmin**,
I want to move a patient from one institution to another via a multi-step confirmation flow,
So that patients who transfer clinical centres have their complete records moved safely with a full audit trail at both institutions.

**Acceptance Criteria:**

**Given** the superadmin opens the patient move flow from a patient's detail view (superadmin overlay active)
**When** they select the destination institution
**Then** an impact preview is displayed: count of open referrals, assessments, videos, attachments, and estimated file size

**Given** the superadmin reviews the impact preview and types the destination institution name to confirm
**When** the confirmation form is submitted
**Then** a `transaction.atomic()` block: sets `patient.institution` to the destination, creates `AuditLog` entries at both source and destination institutions, and creates `Notification` records for both institution admins

**Given** the atomic transaction succeeds
**When** a clinician from the destination institution accesses the patient list
**Then** the moved patient appears in their institution's scope
**And** the moved patient no longer appears in the source institution's patient list

**Given** the atomic transaction fails at any step
**When** the rollback completes
**Then** `patient.institution` is unchanged and no partial audit records exist at either institution

**Given** the patient has open referral threads at the time of the move
**When** the move completes
**Then** the open referral records remain intact and both institutions' clinicians retain access to their respective referral thread records via the shared `referral_uuid`

---

## Epic 3: Institution Admin Self-Management

Institution admins can independently manage their clinical team, create and deactivate clinician accounts, monitor patient and assessment activity, personalise their institution's branding, and ensure all PDF reports carry their institution's identity — with no superadmin intervention needed for day-to-day operations.

### Story 3.1: Institution Admin Dashboard

As an **institution admin**,
I want a dashboard showing patient activity, assessment volume, referral status, and team activity all scoped to my institution,
So that I can monitor the health and productivity of my clinical team without requiring superadmin involvement.

**Acceptance Criteria:**

**Given** the institution admin navigates to the admin dashboard
**When** the page loads
**Then** a four-quadrant AdminLTE card layout is displayed with institution-scoped data:
- Quadrant 1: Patient stats by status (Active, Discharged, etc.)
- Quadrant 2: Assessment activity by type for the current month (GMA, HINE, CDIC, GPA, DA counts)
- Quadrant 3: Referral activity (sent / received / pending / closed counts)
- Quadrant 4: Team activity (total user count, most active clinicians this month)

**Given** all four dashboard quadrants query the institution's data
**When** the queries execute
**Then** every query uses `.for_institution(request.institution)` — zero cross-institution data is returned

**Given** the institution has just been onboarded (empty state — no patients, no activity)
**When** the dashboard loads
**Then** all quadrants display zeros without raising errors

**Given** only ADMIN users access this dashboard
**When** a USER or SUPERADMIN navigates to the admin dashboard URL
**Then** they are redirected appropriately — USER to the clinician view, SUPERADMIN to the superadmin dashboard

---

### Story 3.2: Clinician Account Management

As an **institution admin**,
I want to create new clinician accounts and deactivate existing ones within my institution,
So that I can independently manage my clinical team without needing superadmin involvement for routine staffing changes.

**Acceptance Criteria:**

**Given** the institution admin navigates to the user management section
**When** they submit the create-user form with name, email, password, and staff_position
**Then** a new `CustomUser` is created with `user_type=USER` and `institution=request.institution`
**And** the new clinician can immediately log in and access only the admin's institution's data

**Given** the institution admin deactivates a clinician account
**When** `is_active` is set to `False` on the user record
**Then** the deactivated clinician can no longer authenticate
**And** all their historical records (assessments, patient registrations, problem entries) remain intact and visible

**Given** an institution admin attempts to create a user with `user_type=ADMIN` or `user_type=SUPERADMIN`
**When** the form is submitted
**Then** the attempt is rejected — institution admins may only create `user_type=USER` accounts

**Given** the institution admin views the user list
**When** the list renders
**Then** only users bound to their institution are displayed — users from other institutions are not visible

---

### Story 3.3: Institution Branding Setup

As an **institution admin**,
I want to upload my institution's logo and manage its display settings,
So that my institution is correctly identified throughout the system and in all exported documents.

**Acceptance Criteria:**

**Given** the institution admin navigates to institution settings
**When** they upload a logo image (jpg/png/gif, max 10MB per existing NDAS validation rules)
**Then** the logo is saved to `MEDIA_ROOT/{institution_slug}/logo/` and displayed on the institution's card on the superadmin selector screen

**Given** the logo has been uploaded successfully
**When** any page within that institution's context renders
**Then** the institution logo is displayed in the AdminLTE sidebar brand-logo slot via the `active_institution` context variable

**Given** the institution admin saves updated display settings
**When** they submit the settings form
**Then** changes are persisted and reflected immediately across all institution-scoped views without a server restart

---

### Story 3.4: PDF Report Branding

As an **institution admin**,
I want all PDF reports generated within my institution to include the institution logo, name, and header,
So that exported patient reports are professionally branded and clearly attributed to my institution.

**Acceptance Criteria:**

**Given** `BasePDFGenerator` is extended to accept active institution branding from the context
**When** a PDF report is generated for any patient within Institution A's context
**Then** Institution A's logo, name, and header are rendered at the top of every page of the PDF

**Given** the institution has not yet uploaded a logo
**When** a PDF is generated
**Then** the institution name and header are rendered — the logo slot is omitted gracefully with no broken image placeholder

**Given** a superadmin is viewing Institution B's context via context switching
**When** they trigger a PDF report generation
**Then** Institution B's branding (from `request.institution`) is injected into the PDF

**Given** an existing PDF was generated before institution branding was configured
**When** a new PDF is generated after the logo and name are set
**Then** the new PDF includes the branding — no cached unbranded version is served

---

## Epic 4: Cross-Institution Clinical Referrals

Clinicians can send structured referrals to specialists at other institutions with a frozen snapshot of the patient's complete clinical record. The receiving specialist views the snapshot, replies in a documented thread, and the originating clinician closes the referral — the full consultation permanently recorded in the patient's record.

### Story 4.1: Referral App & Data Models

As a **clinician**,
I want the system to have the data structures needed to record cross-institution referrals independently at both institutions,
So that each institution's consultation record is self-contained and survives the other institution being suspended or deleted.

**Acceptance Criteria:**

**Given** the `referral/` Django app is created and registered in `INSTALLED_APPS`
**When** the initial migration runs
**Then** `ReferralSent`, `ReferralReceived`, and `ReferralMessage` tables are created with all specified fields
**And** `ReferralStatus` choices (PENDING/REPLIED/CLOSED) exist in `ndas/custom_codes/choice.py`

**Given** a `ReferralSent` record is created with a new `referral_uuid` (UUID4)
**When** `ReferralReceived` is created for the same referral
**Then** `ReferralReceived` copies the same `referral_uuid` — no new UUID is generated
**And** both records default to `status=PENDING`

**Given** `ReferralSent` is deleted or Institution A is suspended
**When** Institution B queries `ReferralReceived` by `referral_uuid`
**Then** the `ReferralReceived` record remains intact and fully accessible — the two records are independently self-contained

**Given** all new referral models are inspected
**When** their base classes are checked
**Then** all inherit `TimeStampedModel` and `UserTrackingMixin`, and all institution-FK models use `InstitutionScopedManager`

---

### Story 4.2: Referral Initiation & Frozen Patient Snapshot

As a **clinician**,
I want to send a cross-institution referral with a complete frozen snapshot of my patient's clinical record,
So that the receiving specialist has everything they need to assess the patient regardless of any subsequent changes to the originating record.

**Acceptance Criteria:**

**Given** the clinician opens the New Referral form from a patient's detail page
**When** they select a receiving institution, a receiving clinician from that institution, and write a referral message
**Then** a `transaction.atomic()` block creates `ReferralSent` (institution=sending institution) and `ReferralReceived` (institution=receiving institution) with the same `referral_uuid`

**Given** `build_patient_snapshot(patient)` is called in `referral/utils.py` at submission time
**When** the snapshot is captured
**Then** `snapshot_data` JSONField contains: patient demographics, all identifiers (BHT, NNC, PTC, PC, PIN, Disk No.), perinatal data, all assessment records (HINE scores, GMA metadata, DA, GPA, CDIC), active problem list with interventions, and attachments metadata (filename/type/date — no binary)
**And** `schema_version: 1` and `captured_at` timestamp are included

**Given** the referral is submitted and the patient record is later updated at the originating institution
**When** the receiving clinician views the frozen snapshot
**Then** the snapshot shows the patient data exactly as it was at referral submission time — not the updated values

**Given** the `transaction.atomic()` block fails at any step
**When** the rollback completes
**Then** neither `ReferralSent` nor `ReferralReceived` exist — no partial referral state is possible

**Given** a clinician attempts to send a referral to a clinician at their own institution
**When** the form is submitted
**Then** a validation error is shown — self-institution referrals are not permitted

---

### Story 4.3: Referral Inbox

As a **clinician**,
I want a unified inbox showing all my sent and received referral threads with their status,
So that I can track the status of every consultation at a glance and open any thread instantly.

**Acceptance Criteria:**

**Given** the clinician navigates to `/referral/inbox/`
**When** the page loads
**Then** a split-panel layout is displayed: thread list on the left (patient thumbnail, referring/receiving institution, date, status badge, unread indicator) and an empty thread panel on the right

**Given** the clinician has both sent and received referrals
**When** the inbox renders
**Then** both outgoing and incoming referrals appear in the thread list, each with a direction indicator (Sent / Received)

**Given** the clinician clicks a thread item in the left panel
**When** the click is processed
**Then** the referral thread is loaded into the right panel via `hx-get` HTMX partial — no full page reload occurs

**Given** a referral thread has an unread reply
**When** it appears in the thread list
**Then** an unread indicator (bold text or dot badge) is visible on that thread item

**Given** the clinician has no referrals yet
**When** the inbox loads
**Then** an empty state message is displayed in both panels without errors

---

### Story 4.4: Referral Thread View & Reply

As a **clinician**,
I want to view a full referral thread with the frozen patient snapshot and all consultation messages, and reply with my clinical opinion,
So that the consultation is fully documented with clinician identity, institution badge, and timestamp on every entry.

**Acceptance Criteria:**

**Given** a clinician opens a referral thread
**When** the thread panel loads
**Then** a fixed patient header card is displayed at the top with the patient's name and key identifiers (BHT, NNC)

**Given** the thread panel renders the frozen snapshot section
**When** it is displayed
**Then** it appears as a collapsible `<details>` panel — collapsed by default, expandable on click — showing the full patient data captured at referral time

**Given** the thread has existing messages
**When** they are rendered
**Then** each entry alternates visually and shows: clinician name, institution badge, timestamp, and message body

**Given** a clinician writes a reply and submits the reply form
**When** the submission is processed
**Then** a `ReferralMessage` record is created with `message_type=OPINION` linked to the referral via UUID
**And** the `ReferralSent` status updates to `REPLIED`
**And** the new message entry appears in the thread immediately

**Given** a clinician attempts to reply to a `CLOSED` referral
**When** the reply form is submitted
**Then** the system rejects the reply — no messages can be added to a closed referral thread

---

### Story 4.5: Referral Lifecycle & Closure

As a **clinician**,
I want to close a referral once the consultation is complete,
So that the thread is sealed with a permanent record and the CLOSED status is visible at a glance on all referral views.

**Acceptance Criteria:**

**Given** a referral is in `PENDING` or `REPLIED` status
**When** the sending clinician clicks "Close Referral" and confirms
**Then** both `ReferralSent.status` and `ReferralReceived.status` are set to `CLOSED`

**Given** a referral is `CLOSED`
**When** it appears in the inbox thread list
**Then** a CLOSED status badge is visible on the thread item
**And** the reply input is hidden — no further messages can be added to the thread

**Given** a referral progresses through `PENDING → REPLIED → CLOSED`
**When** each status transition occurs
**Then** the status badge updates correctly on all referral list views (inbox and patient referrals tab)

**Given** an institution's subscription status is `GRACE`
**When** a clinician attempts to reply or close an active referral thread via POST
**Then** the action is permitted — active referrals are explicitly exempt from the read-only subscription restriction

---

### Story 4.6: Patient Referrals Tab

As a **clinician**,
I want a Referrals tab within the patient detail view showing a timeline of all referrals for that patient,
So that any clinician opening the patient record has complete visibility of all past and active consultations without navigating to the inbox.

**Acceptance Criteria:**

**Given** the clinician opens a patient's detail view and selects the Referrals tab
**When** the tab content loads
**Then** a timeline is displayed showing all outgoing and incoming referrals for that patient

**Given** each referral entry in the timeline
**When** it is rendered
**Then** it shows: direction (Sent/Received), referring clinician name, referring/receiving institution, date, current status badge, and outcome (if closed)

**Given** a clinician clicks a referral entry in the timeline
**When** the click is processed
**Then** the clinician is navigated to the corresponding referral thread in the inbox

**Given** the patient has no referrals
**When** the Referrals tab is selected
**Then** an empty state message is displayed without errors

**Given** the referral query runs for the patient referrals tab
**When** results are returned
**Then** only referrals where this institution is either the sender or the receiver are shown — no referrals from unrelated institutions appear

---

## Epic 5: Referral Notifications & Real-Time Awareness

Clinicians are notified of all referral events (new referral received, reply from specialist, referral closed) via an in-app notification panel that updates automatically within 120 seconds — no manual refresh or navigation required. The unread count is visible in the navbar at all times.

### Story 5.1: Notification Model & Signal Infrastructure

As a **clinician**,
I want the system to automatically create a notification for every referral event — new referral received, reply from specialist, referral closed,
So that I am always informed of consultation activity without having to poll the inbox manually.

**Acceptance Criteria:**

**Given** the `Notification` model is created in `referral/models.py` with fields: `recipient` FK, `notification_type`, `title`, `body`, `link`, `is_read`, `created_at`, and `institution` FK
**When** the migration runs
**Then** the `Notification` table is created
**And** `NotificationType` choices (REFERRAL_RECEIVED / REFERRAL_REPLIED / REFERRAL_CLOSED) exist in `ndas/custom_codes/choice.py`

**Given** Django `post_save` signal handlers are defined in `referral/signals.py` and registered in `ReferralConfig.ready()` in `referral/apps.py`
**When** a new `ReferralSent` is created (referral submitted)
**Then** a `Notification` with `notification_type=REFERRAL_RECEIVED` is created for the receiving clinician
**And** the notification `link` points to the relevant referral thread URL

**Given** a `ReferralMessage` is saved with `message_type=OPINION`
**When** the `post_save` signal fires
**Then** a `Notification` with `notification_type=REFERRAL_REPLIED` is created for the sending clinician

**Given** a referral's status transitions to `CLOSED`
**When** the `post_save` signal fires
**Then** `Notification` records with `notification_type=REFERRAL_CLOSED` are created for: the sending clinician, the receiving clinician, the sending institution's ADMIN, and the receiving institution's ADMIN

**Given** the signal handlers are inspected
**When** their module location is checked
**Then** all `Notification.objects.create()` calls exist exclusively in `referral/signals.py` — no view file contains direct notification creation

---

### Story 5.2: Notification Bell & Real-Time Count

As a **clinician**,
I want an unread notification count displayed in the navbar that refreshes automatically,
So that I can see pending referral activity within 120 seconds of it occurring without leaving my current page.

**Acceptance Criteria:**

**Given** the navbar bell icon is wired up in `src/base.html`
**When** any authenticated page renders
**Then** the bell icon displays the current unread notification count in a badge targeting `#notification-bell-count`

**Given** the bell icon uses HTMX polling
**When** the page has been open for 60 seconds
**Then** `hx-get="/referral/notifications/count/"` fires automatically, updating `#notification-bell-count` with the latest unread count

**Given** a new referral notification is created
**When** up to 120 seconds elapse
**Then** the navbar bell count increments to reflect the new unread notification — satisfying NFR23

**Given** the `notification_count` view at `/referral/notifications/count/` is called
**When** the request is processed
**Then** it returns only the unread count for `request.user` scoped to `request.institution` — no cross-institution notification counts are returned

**Given** the clinician has zero unread notifications
**When** the bell renders
**Then** either no badge or a zero badge is shown — no error is raised

---

### Story 5.3: Notification Panel & Mark as Read

As a **clinician**,
I want to open a notification panel showing all my recent alerts with links to the relevant referral threads, and mark them as read,
So that I can action notifications directly and keep my unread count accurate.

**Acceptance Criteria:**

**Given** the clinician clicks the navbar bell icon
**When** the notification panel opens
**Then** a list of recent notifications is displayed, each showing: notification type label, title, body, timestamp, and a link to the relevant patient record or referral thread

**Given** the notification list renders
**When** unread and read notifications are both present
**Then** unread notifications are visually distinguished (e.g., bold or highlighted row)

**Given** the clinician clicks a notification link
**When** the navigation occurs
**Then** the notification is marked as `is_read=True`
**And** the navbar bell count decrements by 1 on the next poll

**Given** the clinician marks all notifications as read via a "Mark all read" action
**When** the action completes
**Then** all `Notification` records for `request.user` have `is_read=True`
**And** the bell count returns to zero on the next poll

**Given** the notification panel queries notifications
**When** the query runs
**Then** only notifications where `recipient=request.user` and scoped to `request.institution` are returned — no other clinician's or institution's notifications are visible

---
