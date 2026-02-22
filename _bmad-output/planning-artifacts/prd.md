---
workflowType: 'prd'
workflow: 'edit'
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
  - step-e-01-discovery
  - step-e-02-review
  - step-e-03-edit
workflowStatus: complete
completedDate: '2026-02-19'
lastEdited: '2026-02-22 (edit 3)'
inputDocuments:
  - docs/index.md
  - docs/project-overview.md
  - docs/architecture.md
  - docs/data-models-main.md
  - docs/api-contracts-main.md
  - docs/component-inventory-main.md
  - docs/custom-codes-reference.md
  - docs/development-guide.md
  - _bmad-output/planning-artifacts/product-brief-NDAS-2026-02-22.md
classification:
  projectType: web_app
  domain: healthcare
  complexity: high
  projectContext: brownfield
  prdScope: existing-capabilities
briefCount: 0
researchCount: 0
brainstormingCount: 0
projectDocsCount: 8
editHistory:
  - date: '2026-02-22'
    changes: >
      14 targeted improvements from validation-report-2026-02-22:
      Added NFR18 (WCAG 2.1 AA accessibility); added Journey 4 (research coordinator cohort export);
      rewrote FR33 (subscription operations), FR36 (staff scope definition);
      added RPO/RTO to NFR12; added SLA to NFR11; removed implementation leakage from NFR10 and NFR13;
      added MFA status note and software validation approach to Domain-Specific Requirements;
      clarified FR3 (identifiers), FR25 (problem statuses), FR30 (patient filter criteria);
      removed vague "quick" from FR6; added SEO N/A note.
  - date: '2026-02-22'
    source: validation-report-2026-02-22.md
    changes: >
      12 targeted improvements from second validation pass (edit 3):
      FR38 rewritten (specific notification triggers enumerated);
      FR39 removed (superseded by FR67-FR69);
      FR41 rewritten (manage → specific actions: view, reply, close);
      FR43 rewritten (pointer to FR50-55 and FR56-59);
      FR45 rewritten (ORM layer removed → capability-level isolation);
      FR46 rewritten (slug path removed → capability-level file isolation);
      FR49 rewritten (feature flag/code paths removed → controlled migration path);
      FR70 rewritten (polling mechanism removed → 120-second refresh capability);
      NFR21 rewritten (code paths removed → capabilities inactive);
      NFR22 rewritten (model names/transaction removed → atomic dual-institution record);
      Journey 3 multi-centre reference annotated as Phase 2;
      Phase 2 out-of-scope list added (snapshot versioning, onboarding checklist, referral reassignment).
  - date: '2026-02-22'
    source: product-brief-NDAS-2026-02-22.md
    changes: >
      Multi-Institution Expansion incorporated from product brief:
      Executive Summary Phase 2 paragraph; new Target Users section (SUPERADMIN/ADMIN/USER);
      Multi-Institution Success Criteria (6 metrics);
      Journeys 5-7 (superadmin onboarding, institution admin startup, cross-institution referral);
      Multi-Institution Data Isolation subsection in Domain Requirements;
      Product Scope Phase 2 replaced with 6 detailed capability groups
      (Multi-Institution Foundation, Migration Path, Superadmin Capabilities, Institution Admin Capabilities,
      Referral System, Notifications);
      FR45-FR70 added (33 new Phase 2 FRs across 5 groups, FR38-FR44 retained);
      NFR19-NFR23 added (Multi-Institution quality attributes).
---

# Product Requirements Document - NDAS

**Author:** Rasika
**Date:** 2026-02-19

---

## Executive Summary

NDAS (Neurodevelopmental Assessment System) is a clinician-facing web application built to support early detection of neurodevelopmental disabilities — including cerebral palsy — in neonatal and paediatric patients. The system consolidates patient records, structured clinical assessments, video-based evaluations, and intervention tracking into a single longitudinal platform, eliminating paper-based record loss and enabling timely clinical decisions. Secondary purpose: generating a structured clinical dataset for neurodevelopmental research.

**Target Users:** Clinicians and neurodevelopmental specialists conducting assessments and managing patient follow-up across the care continuum.

**Core Problem Solved:** Neurodevelopmental conditions are often missed or detected late due to fragmented records, lack of structured assessment tools, and no systematic follow-up mechanism. NDAS enforces a structured clinical workflow from first assessment through intervention response monitoring.

### What Makes This Special

NDAS is not a generic EMR. It is purpose-built for neurodevelopmental surveillance — providing structured instruments (GMA, HINE, CDIC, GPA, Developmental Assessment) tied directly to individual patient timelines. The critical differentiator is longitudinal tracking: each patient's assessments, interventions, and outcomes are linked, allowing clinicians to see trajectory, not just snapshots. Video-based GMA assessments are integrated natively into the clinical workflow, enabling remote review and standardised scoring. The problem list module adds active clinical management capability, connecting diagnoses to actionable interventions and tracking their responses over time.

### Phase 2 — Multi-Institution Expansion

NDAS Phase 2 transforms the platform from a single-institution deployment into a true multi-tenant clinical network. A single NDAS instance serves 10+ hospitals and clinics with complete data isolation between institutions — no additional servers, databases, or deployment cycles per institution added. A superadmin onboards a new institution in under five minutes via one form; no developer involvement required after initial deployment. Two cross-institution capabilities are added as controlled bridges: structured clinical referrals (with frozen patient snapshots) enable specialist consultations across institution boundaries, and a god-view analytics dashboard gives the platform operator aggregate visibility across the entire network.

## Project Classification

| Attribute | Value |
|-----------|-------|
| **Project Type** | Web Application (Django multi-page, server-rendered) |
| **Domain** | Healthcare — Neurodevelopmental Paediatrics |
| **Complexity** | High (clinical data integrity, role-based access, medical identifiers, patient safety) |
| **Project Context** | Brownfield — documenting existing system capabilities |
| **Stack** | Django 4.2 · PostgreSQL/SQLite · AdminLTE 3.2 · Bootstrap 4.6 · HTMX · Video.js |

## Target Users

| Role | Scope | Responsibilities |
|------|-------|-----------------|
| **SUPERADMIN** | All institutions | Onboards institutions, manages subscriptions, monitors cross-institutional activity from a god-view dashboard; operates outside any single institution |
| **ADMIN** | Own institution | Manages the clinical team within their institution — creates and deactivates clinician accounts, monitors patient activity, assessment volumes, and referral status |
| **USER** | Own institution (referrals bridge institutions) | Registers patients, conducts assessments (GMA, HINE, CDIC, GPA, Developmental Assessment), manages problem lists, sends and receives cross-institution referrals |

## Success Criteria

### User Success

- Clinicians access a patient's complete neurodevelopmental history — all assessments, interventions, and videos — from a single record
- Structured assessment tools (GMA, HINE, CDIC, GPA, DA) guide clinicians through standardised protocols, reducing evaluation variability
- Early identification of at-risk patients through structured scoring (e.g., HINE < 73 triggers clinical review)
- Zero patient records lost — all clinical data persisted with full audit trail (user and timestamp on every record)

### Clinical / Organisational Success

- Earlier CP and neurodevelopmental disability diagnosis through systematic video-based GMA and HINE workflows
- Fewer missed follow-ups through centralised patient tracking — all patients visible on dashboard regardless of referral source
- Timely interventions supported by the problem list module, connecting diagnoses to actionable clinical plans
- Collaborative specialist involvement: multiple clinicians share access to the same patient record and assessment data across centres
- Research-quality data captured: aggregated assessment scores, cohort-level reporting, anonymised export capability

### Technical Success

- Multi-user concurrent access: multiple clinicians operate simultaneously without data conflicts
- Multi-centre deployment: single instance supports multiple clinical sites with user-level access control
- Secure clinical data handling: role-based access (superuser/staff), 1-hour session timeout, rate limiting on all 24 CRUD operations
- Full audit trail: every record creation and modification tracked to a named user and timestamp
- File integrity: video uploads (up to 2GB) and document attachments validated by MIME type and size limits

### Measurable Outcomes

- 100% of patient assessments captured digitally — no paper records required for core clinical workflows
- All five assessment types (GMA, HINE, CDIC, GPA, DA) operational within a single patient record
- Cohort reports and aggregated assessment data exportable for research use
- All data modifications auditable to a named user and timestamp
- System accessible concurrently by multiple clinicians across multiple clinical centres

### Multi-Institution Success *(Phase 2)*

- New institution live (institution created + first admin active) within 5 minutes of superadmin form submission — zero developer involvement after initial platform deployment
- Zero cross-institution data leakage incidents — patient data from Institution A never appears in Institution B's context; verified by automated isolation checks and pre-launch security testing before multi-institution mode is enabled in production
- Existing single-institution data migrated atomically to default institution with zero data loss before multi-institution flag is enabled
- More than 10 institutions active on the platform post-launch
- 0 developer hours consumed per new institution onboarded after initial deployment
- All active referrals survive subscription state changes and run to clinical completion

## User Journeys

### Journey 1 — Dr. Amara: First Assessment of a High-Risk Infant

**Persona:** Dr. Amara is a neurodevelopmental specialist at a paediatric unit. She receives referrals from community PHMs for infants with suspected movement abnormalities. Before NDAS, she kept paper notes that were frequently incomplete or missing by the next visit.

**Opening Scene:** A 3-month-old is referred with suspected abnormal general movements. Dr. Amara opens NDAS and registers the patient — entering the BHT, NNC, date of birth, gestational age (32 weeks + 4 days), birth weight, and APGAR scores from the hospital record. The perinatal picture is captured in full in under five minutes.

**Rising Action:** She uploads the GMA video recorded during the clinic visit. While it processes, she opens a new HINE assessment and works through the scoring items systematically. The structured form enforces completeness — no field can be skipped. She scores 54/78.

**Climax:** HINE < 73 — clinically abnormal. Combined with the GMA video showing absent fidgety movements, the picture is clear. Dr. Amara adds "High-risk for Cerebral Palsy" to the problem list, links it to both assessments, and creates an intervention plan for early physiotherapy referral. Everything is in one place, timestamped, and attributed to her.

**Resolution:** Three months earlier than would have been possible with paper records, this infant is on an intervention pathway. The record is ready for the next clinician who sees this patient — at any centre — with zero information lost.

### Journey 2 — Dr. Amara: Six-Month Follow-Up and Trajectory Review

**Opening Scene:** The same patient returns for a 6-month review. Dr. Amara opens the record and immediately sees the full timeline: the original GMA video, the HINE score of 54, the physiotherapy intervention started at 3 months.

**Rising Action:** She conducts a new HINE assessment. Score: 67 — still below normal threshold but meaningfully improved. She adds a new CDIC record and completes a Developmental Assessment across all four domains (GM, FMV, HSL, SEB). The system stores age-normed scores against the patient's corrected age.

**Climax:** The trajectory is visible: from 54 to 67 on HINE over 3 months of intervention. Dr. Amara updates the problem list — response to physiotherapy documented, intervention continued. She generates a PDF report for the referring specialist summarising the patient's full assessment history in a single document.

**Resolution:** The specialist receives a complete, structured clinical picture. The collaborative care model works because the record is shared and up to date. No phone calls to reconstruct history. No missing notes.

### Journey 3 — System Administrator: Onboarding a New Clinician

**Opening Scene:** A new neurodevelopmental specialist joins the centre's NDAS deployment. The administrator logs in with superuser credentials.

**Rising Action:** The admin creates a new user account — name, credentials, role set to staff. Subscription is activated. The clinician receives login details and accesses the system immediately. The admin reviews the user activity log to confirm first login.

**Climax:** Six months later, the admin runs a subscription review. One user account is inactive — the admin deactivates it. Another centre requests access; the admin adds a new user scoped to that centre's patient records *(Phase 2)*.

**Resolution:** The system remains clean: only active, authorised clinicians have access. The audit trail shows every action taken by every user. The admin has full visibility into system activity without touching clinical data.

### Journey 4 — Dr. Silva (Research Coordinator): Monthly Cohort Export

**Persona:** Dr. Silva is a neurodevelopmental researcher coordinating a longitudinal study. Each month she extracts an anonymised dataset from NDAS covering the current study cohort — infants assessed in the past 30 days with GMA and HINE records.

**Opening Scene:** The monthly data cut is due. Dr. Silva logs into NDAS with her staff credentials and navigates to the reporting module.

**Rising Action:** She filters by date range (past 30 days), assessment types (GMA and HINE), and patient status (active). The system shows a preview count: 23 patients in the filtered cohort. She selects anonymised export.

**Climax:** NDAS generates an Excel workbook — one row per patient, assessment scores across columns, no identifying data. The structured, validated data requires no manual cleaning: field names are standardised, ranges were enforced at entry, and no partially complete assessments appear in the export.

**Resolution:** The monthly cohort file is submitted to the research database before the deadline. No phone calls to clinicians for missing data. No manual transcription errors. NDAS's completeness enforcement at assessment entry is what makes the export clean.

### Journey 5 — Superadmin: Onboarding a New Institution *(Phase 2)*

**Persona:** Rasika (platform operator) needs to bring a new district hospital onto NDAS. Under the current model this requires a full deployment cycle. Under Phase 2 it is a form submission.

**Opening Scene:** A new hospital has confirmed their subscription. Rasika logs into the NDAS superadmin dashboard — a god-view showing all institutions as cards with subscription status, user count, patient count, and last activity.

**Rising Action:** Rasika clicks "Add Institution" and fills in one form: institution name, slug, and the first admin's name, email, and temporary password. She submits.

**Climax:** A single atomic transaction creates the institution record and the admin account simultaneously — no orphan institution is possible. Rasika sees the new institution card appear on the dashboard. She switches context into the new institution via the persistent top banner and verifies the setup.

**Resolution:** The hospital admin receives their credentials and logs in. NDAS serves institution eleven from the same codebase and the same server. Rasika's involvement ends at form submission — no server provisioning, no code deployment, no database configuration.

### Journey 6 — Institution Admin: Operational Startup *(Phase 2)*

**Persona:** A nurse manager at a newly onboarded district hospital receives credentials from Rasika and is responsible for getting her clinical team operational.

**Opening Scene:** She logs in for the first time and lands on the institution dashboard — four quadrants: patient stats by status, assessment activity by type this month, referral activity (sent/received/pending/closed), team activity (user count and most active clinicians). All currently empty.

**Rising Action:** She uploads the institution logo. She creates clinician accounts — name, credentials, staff position. She registers the first patient and confirms the record appears on the dashboard.

**Climax:** A week later the dashboard shows 12 patients registered, 8 HINE assessments this month, 2 referrals sent. She reviews the team activity panel — one clinician has not logged in. She deactivates the inactive account.

**Resolution:** The institution is self-sufficient. The admin manages her team, monitors clinical activity, and maintains institutional oversight without developer involvement.

### Journey 7 — Clinician: Cross-Institution Referral *(Phase 2)*

**Persona:** Dr. Amara has a patient whose GMA video requires specialist interpretation from a consultant at a tertiary referral centre — a different institution on the NDAS network.

**Opening Scene:** Dr. Amara opens the patient record and navigates to the Referrals tab. She clicks "New Referral", selects the receiving institution and the receiving consultant, and writes a referral message.

**Rising Action:** NDAS automatically attaches a frozen snapshot of the patient record — demographics, perinatal history, all assessment scores, and the GMA video — at the moment of referral submission. The receiving consultant is notified. She reviews the frozen snapshot and the video, adds her clinical opinion in the referral thread, and replies.

**Climax:** Dr. Amara receives a notification that the referral has a reply. She opens the consultation thread — fixed patient header card, frozen snapshot as collapsible panel, alternating opinion entries with clinician name, institution badge, and timestamp. The specialist's opinion is fully documented.

**Resolution:** Dr. Amara closes the referral. The complete consultation thread is permanently recorded in the patient's clinical record — direction, clinician, institution, status, outcome — visible in the Patient Referral Tab. No phone calls, no paper trail, no missing context for the next clinician who opens this record.

### Journey Requirements Summary

| Journey | Capabilities Revealed |
|---------|----------------------|
| First assessment | Patient registration · Perinatal data capture · Video upload · HINE scoring · Problem list creation · Intervention planning |
| Follow-up review | Longitudinal record access · Sequential assessment entry · Developmental scoring · Trajectory visibility · PDF report generation |
| Admin onboarding | User account management · Subscription control · Activity log review · Multi-centre access scoping |
| Research cohort export | Date-filtered cohort selection · Assessment-type filtering · Patient status filtering · Anonymised Excel export · Research-quality data completeness |
| Superadmin institution onboarding *(Phase 2)* | God-view dashboard · Atomic institution + admin creation · Institution context switching · Zero-deployment onboarding |
| Institution admin startup *(Phase 2)* | Institution dashboard · Clinician account creation · Logo upload · Team activity monitoring · Account deactivation |
| Cross-institution referral *(Phase 2)* | Referral initiation · Frozen patient snapshot · Consultation thread · Specialist reply · Referral closure · Patient referral tab |

## Domain-Specific Requirements

### Compliance & Regulatory

- No national statutory healthcare data regulation currently applies; system operates under institutional and hospital authority policy
- Patient data retained for life with patient consent — records may not be permanently deleted; only deactivated or archived
- All clinical data modifications attributable to a named, authenticated user with timestamp (audit trail mandatory)
- Access restricted to authenticated, authorised clinical staff — no anonymous or public access to patient data
- Multi-factor authentication (MFA) is not currently enforced; institutional network controls and password policy serve as compensating controls — MFA evaluation is deferred to Phase 2

### Clinical Validation Constraints

- All structured assessment instruments (HINE, GMA, CDIC, GPA, Developmental Assessment) enforce complete data entry before submission — partial assessments cannot be saved as final records
- Assessment scoring follows validated clinical protocols: HINE 0–78 (normal threshold > 73); Developmental Assessment across four domains (GM, FMV, HSL, SEB) with age-normed reference (0–72 months corrected age); APGAR 0–10 at 1, 5, and 10 minutes
- Perinatal data validation enforced: birth weight 300g–8000g; gestational age 20–44 weeks + 0–6 days
- GMA assessments require a linked video record; that video cannot be deleted while the assessment link is active

### Integration Requirements

- Currently operates as a standalone system — no live integration with external HIS, PACS, or lab systems
- Architecture supports future multi-centre and multi-institution integration with scoped cross-centre data access
- PDF and Excel export serves as the current integration bridge for referring specialists and research use

### Software Validation Approach

System changes are validated through user acceptance testing (UAT) with clinical staff before production deployment. Validation scope covers: new assessment workflows, data entry and retrieval, access control changes, and report generation. No formal IEC 62304 or FDA 21 CFR Part 11 compliance is required at the current regulatory stage; UAT sign-off by the responsible clinician and system owner is the accepted release gate.

### Domain Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| Unauthorised access to patient records | Role-based access (superuser/staff), session timeout, authentication required on all routes |
| Incomplete or invalid assessment data | Form-level validation, mandatory fields, clinical range checks on all numeric inputs |
| Video loss breaking GMA assessment integrity | Business rule: video deletion blocked while linked to an active assessment |
| Record loss / data corruption | Daily automated backups, audit trail on all changes, no hard delete on clinical records |
| Concurrent edit conflicts | Database-level integrity constraints, timestamped records |
| Multi-centre data leakage (Phase 2) | Role and centre-scoped access control; query filtering per institution |
| Referral workflow complexity (Phase 2) | Lightweight structured handoff design — not a full workflow engine |
| Notification system reliability (Phase 2) | HTMX polling as interim; WebSocket/SSE for production real-time |

### Multi-Institution Data Isolation *(Phase 2)*

- Zero cross-institution data leakage is a non-negotiable platform invariant — patient data from Institution A must never appear in Institution B's context under any query, view, or export path
- Institution data is physically partitioned in file storage under `/{institution_slug}/` and logically isolated at the ORM layer — every model with an institution foreign key is filtered to the active institution on every query with no per-view filtering required
- Superadmin context-switching does not relax isolation — data remains scoped to the selected institution; superadmin aggregate views are explicit cross-institution reads, not accidental leaks
- Active referrals survive subscription state changes and institution suspension — clinical consultations in progress run to completion regardless of administrative events
- Feature flag (`MULTI_INSTITUTION_ENABLED`) gates activation — when disabled, system behaves identically to the current single-institution deployment; flag removed after stable production rollout

## Web Application Requirements

### Architecture

NDAS is a server-rendered multi-page application (MPA) built with Django 4.2. Dynamic interactivity is delivered via HTMX for partial page updates — keeping the application responsive on clinical networks without the overhead of a full SPA. The UI is built on AdminLTE 3.2 + Bootstrap 4.6, providing a structured, responsive clinical dashboard interface.

- **Rendering:** SSR via Django templates; HTMX handles partial updates, inline status changes, and form submissions without full-page reload
- **Static Assets:** WhiteNoiseMiddleware serves compressed, cached static files with long-lived cache headers
- **Video Playback:** Video.js provides cross-browser HTML5 video playback for GMA assessment review
- **Session Management:** 1-hour inactivity timeout; expires on browser close
- **CSRF Protection:** CsrfViewMiddleware on all POST requests; tokens embedded in all forms
- **HTMX Patterns:** Used for problem list status changes, inline interactions, and dynamic content loading
- **Template Architecture:** All authenticated views extend `src/base.html`; public views extend `src/basic_plane.html`
- **Future — Real-time Notifications:** Architecture accommodates future WebSocket or SSE for instant clinician notifications; HTMX polling serves as interim approach

### Browser Support

| Browser | Support Level |
|---------|--------------|
| Chrome (latest) | Primary |
| Firefox (latest) | Primary |
| Microsoft Edge (latest) | Primary |
| Mobile browsers (Chrome / Safari) | Supported — fully responsive |
| Internet Explorer | Not supported |

### SEO

SEO is not applicable — NDAS is a closed, authentication-gated clinical intranet system with no public-facing pages.

### Responsive Design

- Bootstrap 4.6 grid — fully responsive across desktop, tablet, and mobile viewports
- Primary use case: desktop clinical workstations (1024px+) for assessment entry and record management
- Secondary use case: tablet and mobile for ward rounds and bedside reference
- AdminLTE 3.2 sidebar collapses to mobile-friendly navigation on smaller screens
- Assessment entry forms collapse to single-column on mobile viewports
- Video.js player adapts responsively to viewport width

## Product Scope & Development Roadmap

### Phase 1 — Core System (Operational)

NDAS Phase 1 is fully delivered — a complete neurodevelopmental surveillance workflow for a single clinical centre.

- Patient record management — full demographic, perinatal, and identifier capture (BHT, NNC, PTC, PC, PIN, Disk No.)
- Five structured assessment modules: GMA (video-linked), HINE (0–78, normal > 73), CDIC, GPA, Developmental Assessment (four domains, 0–72 months corrected age)
- Video management — upload, storage, cross-browser playback, GMA linkage with deletion protection
- Problem list — active problem tracking, intervention plans, response monitoring with status tracking
- Reporting — PDF and Excel export for individual patients; anonymised cohort export for research
- User management — role-based access (superuser/staff), subscription control, activity logging
- Attachment management and patient bookmarking
- Security infrastructure — audit trail, rate limiting (24 CRUD operations), CSP headers, session management, input sanitisation, MIME-type file validation

### Phase 2 — Multi-Institution Expansion (Planned)

#### 1. Multi-Institution Foundation

- **Institution Model** — name, slug (immutable, storage partition key), logo, subscription status, grace period, active flag
- **Institution Context Middleware** — resolves active institution on every request; ADMIN/USER read from `user.institution`; SUPERADMIN reads from session; replaces current SubscriptionCheckMiddleware
- **Institution-Scoped QuerySet** — custom ORM manager on every model with an institution FK; queryset automatically filters to active institution; defence-in-depth against cross-institution data exposure
- **Institution Storage** — custom file storage backend partitions all uploads under `/{institution_slug}/videos/` and `/{institution_slug}/attachments/`; zero changes to model field declarations
- **User Institution Binding** — institution FK on CustomUser (nullable for SUPERADMIN only); user_type field (SUPERADMIN / ADMIN / USER)
- **Per-Institution Subscription** — subscription status and grace period scoped to each institution; grace period gives read-only mode; active referrals are excluded from read-only restrictions

#### 2. Migration Path

- **Feature flag** (`MULTI_INSTITUTION_ENABLED`) — when False, system behaves identically to current single-institution deployment; when True, full multi-institution mode activates; removed after stable production rollout
- **Default institution migration** — existing data migrated atomically to a default institution; zero data loss or manual re-entry; existing deployment becomes a valid multi-institution deployment from day one

#### 3. Superadmin Capabilities

- **Institution Selector Screen** — card grid showing all institutions with logo, name, subscription status, user count, patient count, and last activity
- **Institution Impersonation with Overlay** — superadmin switches institution context via dropdown; persistent top banner reads "Viewing as: [Institution] [Switch ▼]"; superadmin-only actions (Move Patient, Edit Subscription, Suspend User) injected via template tag
- **Atomic Institution Onboarding** — single form creates institution details and first ADMIN account in one transaction; no orphan institutions
- **God-View Analytics Dashboard** — cross-institution health cards: subscription state, user counts, assessment volumes, referral activity per institution; recent cross-institution events audit log; read-only observational view
- **Cross-Institution Aggregate Reports** — exportable Excel/PDF reports spanning all institutions; three scopes using existing ExcelReportGenerator: per-patient (existing), per-institution aggregate (admin-scoped), cross-institution aggregate (superadmin-scoped)
- **Patient Move Between Institutions** — superadmin-only multi-step flow: select patient + destination → impact preview (open referrals, assessments, videos, file size) → institution-name confirmation → atomic transfer with audit log entries at both institutions and notifications to both admins

#### 4. Institution Admin Capabilities

- **Institution Admin Dashboard** — four-quadrant layout: patient stats by status, assessment activity by type this month, referral activity (sent/received/pending/closed), team activity (user count and most active clinicians); all institution-scoped
- **User Management** — institution admin creates and deactivates clinicians (USER) within their own institution; superadmin creates the first ADMIN only
- **Institution Profile** — logo upload and institution display settings
- **Institution-Level PDF Branding** — institution logo, name, and header injected into all PDF reports generated within that institution's context; uses existing BasePDFGenerator infrastructure

#### 5. Referral System

- **Referral Model** — dual linked records (ReferralSent + ReferralReceived) via referral UUID; each institution's record is self-contained; Institution A deletion does not destroy Institution B's consultation record
- **Frozen Patient Snapshot** — `snapshot_data` JSONField captures the full patient profile at referral time; receiving clinician sees exactly what was referred regardless of subsequent updates at the originating institution
- **Clinical Consultation Thread** — structured thread UI with fixed patient header card, alternating opinion entries with clinician name, institution badge, and timestamp; frozen snapshot as collapsible panel; reply box at bottom
- **Clinician Referral Inbox** — unified feed: thread list (patient thumbnail, referring institution, date, unread indicator) on left; active thread on right
- **Referral Lifecycle** — PENDING → REPLIED → CLOSED; status badge visible at a glance on all referral list views; active referrals survive subscription expiry
- **Patient Referral Tab** — timeline of all referrals (outgoing + incoming) in patient detail view: direction, clinician, institution, status, outcome

#### 6. Notifications

- **Notification Model** — recipient FK, notification_type, title, body, link, is_read, created_at; all institution-scoped
- **HTMX Bell Icon** — navbar bell with unread count; pull-based polling every 60 seconds; reuses existing AdminLTE bell slot
- **Signal-Driven Referral Events** — post-save signals generate notifications: REFERRAL_RECEIVED → receiving clinician; REFERRAL_REPLIED → sending clinician; REFERRAL_CLOSED → both clinicians and both institution admins

#### Out of Scope for Phase 2

The following items were considered for Phase 2 and explicitly deferred:

- **Referral snapshot versioning** — sending an updated patient snapshot mid-consultation; deferred to Phase 3
- **Institution onboarding checklist** — guided setup checklist surfaced to new institution admins after first login; deferred to Phase 3
- **Referral reassignment on clinician departure** — automated handover of open referral threads when a clinician account is deactivated; handled manually by the institution admin at launch; deferred to Phase 3

### Phase 3 — Vision (Future)

- Automated risk-scoring and early-warning flags based on longitudinal assessment trajectories
- Population-level analytics for neurodevelopmental surveillance
- EMR / PACS / HIS integration for cross-system data exchange
- Research export pipeline with de-identification and IRB-ready data packages
- Mobile PWA or offline-capable version for bedside and remote use

## Functional Requirements

### Patient Record Management

- **FR1:** Clinicians can register a new patient with full demographic, perinatal, and clinical identifier data (BHT, NNC, PTC, PC, PIN, Disk No.)
- **FR2:** Clinicians can view a patient's complete longitudinal record — all assessments, videos, problems, and attachments — in a single view
- **FR3:** Clinicians can search for patients by name, BHT, NNC, PTC, PC, PIN, or Disk No.
- **FR4:** Clinicians can edit existing patient demographic and perinatal data
- **FR5:** Clinicians can attach clinical documents to a patient record
- **FR6:** Clinicians can bookmark patients for personal reference access
- **FR7:** The system enforces clinical validation ranges on all patient data fields (birth weight, gestational age, APGAR scores)
- **FR8:** Patient records are retained permanently with patient consent and cannot be permanently deleted

### Clinical Assessment

- **FR9:** Clinicians can create a General Movement Assessment (GMA) linked to a video recording
- **FR10:** Clinicians can create a HINE assessment with structured scoring across all items (0–78)
- **FR11:** Clinicians can create a CDIC record for rehabilitation and intervention centre tracking
- **FR12:** Clinicians can create a General Paediatric Assessment (GPA)
- **FR13:** Clinicians can create a Developmental Assessment scored across four domains (GM, FMV, HSL, SEB) with corrected age reference (0–72 months)
- **FR14:** The system enforces complete data entry on all assessment instruments before a record can be saved as final
- **FR15:** Clinicians can view all assessment records for a patient in chronological order
- **FR16:** Clinicians can edit or delete their own assessment records subject to business rules (superusers can delete any; videos block deletion if assessment-linked)

### Video Management

- **FR17:** Clinicians can upload video files for clinical assessment use
- **FR18:** Clinicians can play back uploaded videos within the clinical interface
- **FR19:** Clinicians can link an uploaded video to a GMA assessment record
- **FR20:** The system prevents deletion of any video linked to an active assessment
- **FR21:** The system validates video file type and size at upload and rejects invalid files

### Problem List & Intervention Management

- **FR22:** Clinicians can add clinical problems to a patient's active problem list
- **FR23:** Clinicians can create intervention plans linked to specific problems
- **FR24:** Clinicians can record and update intervention responses over time
- **FR25:** Clinicians can update the status of problems; valid statuses: Active, Resolved, Monitoring, Discontinued
- **FR26:** Clinicians can view the complete problem, intervention, and response history for a patient

### Reporting & Data Export

- **FR27:** Clinicians can generate a PDF report summarising an individual patient's assessment history
- **FR28:** Clinicians can export assessment data to Excel format
- **FR29:** Clinicians can generate anonymised cohort reports for research use
- **FR30:** Clinicians can filter report data by date range, assessment type, and patient criteria (status, age range, diagnosis)

### User & Access Management

- **FR31:** Administrators can create, edit, and deactivate user accounts
- **FR32:** Administrators can assign and manage user roles (superuser, staff)
- **FR33:** Administrators can activate, deactivate, and extend user subscriptions and view current subscription status for all accounts within their managed scope
- **FR34:** Administrators can view user activity logs
- **FR35:** The system requires authentication for all clinical routes — no unauthenticated access to patient data
- **FR36:** The system enforces role-based access — superusers access all patient records, assessments, and user accounts system-wide; staff access only records they have registered or to which they are explicitly assigned
- **FR37:** The system automatically records the identity and timestamp of every record creation and modification

### Notifications & Communication *(Phase 2)*

- **FR38:** Clinicians can view a personal notification panel displaying alerts for referrals received, replies to referrals they have sent, and referral closure events; each notification links to the relevant patient record or referral thread
- **FR40:** Clinicians can submit a structured referral to another clinician or specialist
- **FR41:** Clinicians can view referrals they have received, reply with a clinical opinion, and close the referral thread — all within the referral inbox interface

### Dashboards & Multi-Centre *(Phase 2)*

- **FR42:** Each user role has access to a role-specific dashboard — clinician view, institutional view, or system-wide admin view
- **FR43:** The system serves multiple clinical institutions from a single deployed instance; institution-specific administration is provided through the superadmin capabilities (FR50–FR55) and institution admin capabilities (FR56–FR59)
- **FR44:** The system scopes patient data, reporting, and dashboards by clinical centre in multi-centre deployments

### Multi-Institution Foundation *(Phase 2)*

- **FR45:** The system ensures that all patient data, assessments, reports, and clinical records accessed by a user are restricted to that user's institution — no query or view returns data from outside the active institution's boundary under any access path
- **FR46:** All files uploaded within an institution's context — videos and attachments — are stored in institution-specific isolation such that users and processes operating in a different institution cannot access them through the application interface or by direct URL
- **FR47:** The system binds every non-superadmin user to exactly one institution — a user cannot access patient data, assessments, or reports outside their bound institution
- **FR48:** Each institution has an independent subscription status — grace period grants read-only access; active referrals are excluded from read-only restrictions and continue to completion
- **FR49:** The system supports a controlled migration path — multi-institution capability can be enabled or disabled without redeployment or data loss; when disabled, all behaviour is identical to the pre-Phase-2 single-institution deployment

### Superadmin Capabilities *(Phase 2)*

- **FR50:** The superadmin can view all institutions on a single dashboard showing subscription status, user count, patient count, and last activity for each institution
- **FR51:** The superadmin can switch institution context via a persistent on-screen selector — all subsequent views and data are scoped to the selected institution
- **FR52:** The superadmin can onboard a new institution by submitting one form that creates the institution record and the first ADMIN account atomically — no institution record exists without a corresponding admin account
- **FR53:** The superadmin can view cross-institution aggregate analytics: assessment volumes, referral activity, user counts, and subscription health across all institutions
- **FR54:** The superadmin can export cross-institution aggregate reports in Excel and PDF formats at three scopes: per-patient, per-institution aggregate, and cross-institution aggregate
- **FR55:** The superadmin can move a patient between institutions via a multi-step confirmation flow — impact preview (open referrals, assessments, videos, file size) → institution-name confirmation → atomic transfer with audit log entries at both institutions and notifications to both admins

### Institution Admin Capabilities *(Phase 2)*

- **FR56:** Institution admins can view a role-specific dashboard showing patient stats by status, assessment activity by type for the current month, referral activity (sent/received/pending/closed), and team activity (user count and most active clinicians) — all scoped to their institution
- **FR57:** Institution admins can create USER accounts within their own institution and deactivate existing accounts
- **FR58:** Institution admins can upload an institution logo and manage institution display settings
- **FR59:** All PDF reports generated within an institution's context include the institution logo, name, and header

### Referral System *(Phase 2)*

- **FR60:** Clinicians can initiate a cross-institution referral by selecting a receiving institution, a receiving clinician, and a referral message — the system automatically attaches a frozen snapshot of the patient record at submission time
- **FR61:** The frozen patient snapshot captures the full patient profile (demographics, perinatal data, all assessment scores and records) at the moment of referral; subsequent updates to the originating record do not alter the snapshot
- **FR62:** Clinicians can view and reply to referral threads they have received — each thread displays a fixed patient header, the frozen snapshot as a collapsible panel, and alternating entries with clinician name, institution badge, and timestamp
- **FR63:** Clinicians can view all referrals (sent and received) in a unified inbox: thread list with patient thumbnail, referring institution, date, and unread indicator on the left; active thread on the right
- **FR64:** Referrals progress through a defined lifecycle: PENDING → REPLIED → CLOSED; status is visible at a glance on all referral list views
- **FR65:** The patient detail view includes a Referrals tab showing a timeline of all outgoing and incoming referrals for that patient: direction, clinician, institution, status, and outcome
- **FR66:** Both the sending and receiving institution retain an independent referral record linked by a shared UUID — deletion or suspension of one institution does not destroy the other institution's consultation record

### Referral Notifications *(Phase 2)*

- **FR67:** The system notifies the receiving clinician when a new referral arrives at their institution
- **FR68:** The system notifies the sending clinician when a referral they submitted receives a reply
- **FR69:** The system notifies both clinicians and both institution admins when a referral is closed
- **FR70:** Clinicians can view unread notification count in the navigation bar; the count refreshes automatically within 120 seconds without navigating away from the current page

## Non-Functional Requirements

### Performance

- **NFR1:** Standard page views (patient list, assessment forms) load within 2 seconds on a typical hospital intranet connection
- **NFR2:** Video playback begins within 5 seconds of initiating playback under hospital network conditions
- **NFR3:** The system supports a minimum of 20 concurrent users without measurable performance degradation
- **NFR4:** Video uploads up to 2GB are handled asynchronously — upload progress is visible and does not block other user operations

### Security

- **NFR5:** All patient data is transmitted exclusively over HTTPS (TLS) — unencrypted clinical data in transit is not permitted
- **NFR6:** User sessions expire after 60 minutes of inactivity and immediately on browser close
- **NFR7:** All 24 CRUD operations are rate-limited (10/min for create/edit, 5/min for delete) to prevent automated abuse
- **NFR8:** All user input is sanitised prior to storage — XSS vectors and injection attacks are neutralised without loss of clinical notation
- **NFR9:** File uploads are validated by MIME type and file size at ingestion — invalid or oversized files are rejected before storage
- **NFR10:** All HTTP responses include security headers — Content Security Policy, anti-clickjacking, and transport security directives applied consistently across all responses

### Reliability

- **NFR11:** The system maintains 99% uptime during clinic operating hours (08:00–18:00, Monday–Saturday); planned maintenance is scheduled outside these hours
- **NFR12:** Patient data is recoverable following system failure — Recovery Point Objective (RPO): ≤ 24 hours; Recovery Time Objective (RTO): ≤ 4 hours; automated daily backups required
- **NFR13:** All multi-step record operations complete atomically — no partial saves are possible; a failure at any step rolls back the entire operation

### Scalability

- **NFR14:** The system architecture supports deployment across multiple clinical centres without per-centre code changes
- **NFR15:** The system supports growth from single-centre to multi-institution deployment without re-architecture of the core application

### Audit & Data Integrity

- **NFR16:** Every record creation, modification, and attempted deletion is logged with user identity and timestamp — the audit trail is permanent and cannot be edited or deleted
- **NFR17:** Hard deletion of clinical records is restricted — superuser authority and business rule validation are required; records with active clinical dependencies cannot be deleted

### Accessibility

- **NFR18:** The system meets WCAG 2.1 Level AA accessibility standards — all clinical workflows are operable via keyboard navigation; form inputs and navigation elements are compatible with screen readers; informational content meets minimum colour contrast ratios (4.5:1 normal text, 3:1 large text)

### Multi-Institution *(Phase 2)*

- **NFR19:** Zero cross-institution data leakage — automated isolation tests must confirm that no query, view, or report returns data outside the active institution's scope before multi-institution mode is enabled in production; any leakage incident constitutes a blocking defect
- **NFR20:** The system supports a minimum of 20 concurrent institutions without additional infrastructure — institution count growth requires no new servers, databases, or code deployments
- **NFR21:** Multi-institution capability deactivation restores single-institution behaviour completely — all multi-institution capabilities are inactive when disabled, verified by the existing regression test suite
- **NFR22:** Referral record creation across the sending and receiving institution is atomic — either both institution records are created or neither is; no partial referral state is possible under any failure condition
- **NFR23:** Referral event notifications (REFERRAL_RECEIVED, REFERRAL_REPLIED, REFERRAL_CLOSED) are delivered within 120 seconds of the triggering event as measured by the 60-second polling interval plus processing time; no notification is silently dropped
