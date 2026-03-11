---
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
classification:
  projectType: web_app
  domain: healthcare
  jurisdiction: Sri Lanka
  complexity: high
  projectContext: brownfield
  scope: full-redocumentation-phase1-and-phase2
  audience:
    - developers
    - clinical-stakeholders
    - management
inputDocuments:
  - docs/index.md
  - docs/project-overview.md
  - docs/architecture.md
  - docs/data-models-main.md
  - docs/api-contracts-main.md
  - docs/component-inventory-main.md
  - docs/development-guide.md
  - docs/custom-codes-reference.md
  - _bmad-output/project-context.md
documentCounts:
  briefCount: 0
  researchCount: 0
  brainstormingCount: 0
  projectDocsCount: 9
workflowType: 'prd'
workflowStatus: complete
project_name: NDAS
user_name: Rasika
date: '2026-03-09'
---

# Product Requirements Document - NDAS

**Author:** Rasika
**Date:** 2026-03-10

## Executive Summary

NDAS (Neurodevelopmental Assessment System) is a purpose-built clinical web platform for neurodevelopmental assessment and patient record management, developed to address the complete absence of video-based GMA tooling in the Sri Lankan healthcare context. The system serves clinicians, neurologists, and paediatricians who require an integrated environment for conducting, documenting, and sharing structured neurodevelopmental assessments — workflows that generic hospital information systems cannot support.

The system is deployed in two phases: Phase 1 (fully operational) delivers comprehensive single-institution clinical management including patient records, five assessment types, video management, problem tracking, report generation, and clinical attachments. Phase 2 (implemented) extends the platform to multi-institution operation with row-level data isolation, cross-institution patient referrals, expert consultation threads, and HTMX-driven notifications — enabling Sri Lankan clinical networks to share complex case expertise across hospital boundaries. A third phase targeting AI-assisted assessment analysis is on the planning horizon, leveraging the structured video and assessment data accumulated through Phases 1 and 2.

**Target users:** Clinical staff (data entry, assessment recording), clinicians and neurologists (assessment review, referral), institution administrators (user management, branding), and system superadmins (cross-institution oversight).

### What Makes This Special

NDAS is the only system in the Sri Lankan clinical context that unifies all commonly used neurodevelopmental assessment types — General Movement Assessment (video-based), HINE, CDIC, General Paediatric Assessment, and Developmental Assessment — in a single patient-centred workflow. The video-to-assessment linkage is core: a Video is directly coupled to a GMAssessment record, making the clinical evidence and its structured interpretation inseparable. Phase 2 elevates this further by enabling multi-expert consultation — a clinician at one institution can refer a case and receive structured clinical opinions from specialists at other institutions, a capability impossible in isolated single-institution deployments. The platform is built on a security-first architecture with 14-layer middleware, rate-limited CRUD operations, and institution-level data isolation, reflecting the sensitivity of the patient data it manages.

## Project Classification

| Dimension | Value |
|-----------|-------|
| **Project Type** | Web Application (Django MVT — server-rendered MPA with HTMX) |
| **Domain** | Healthcare — Clinical / Neurodevelopmental (Sri Lanka jurisdiction) |
| **Complexity** | High — regulated clinical domain, patient data sensitivity, multi-institution architecture |
| **Project Context** | Brownfield — Phase 1 fully operational; Phase 2 implemented; Phase 3 (AI) planned |
| **PRD Scope** | Full re-documentation — Phase 1 operational features + Phase 2 multi-institution + referral |
| **Audience** | Developers (primary), clinical stakeholders, management teams |

## Success Criteria

### User Success

A clinical user session is successful when:
- A patient record is created or updated without data loss, and all identifier fields (BHT, NNC, PTC, PC, PIN, Disk No.) are correctly captured
- An assessment (GMA, HINE, CDIC, GPA, or Developmental) is completed end-to-end and a formatted PDF or Excel report is generated without error
- A video upload completes without failure and is correctly linked to the corresponding GMAssessment record
- A referral is sent to another institution, a specialist adds a consultation reply, and the referring clinician receives a notification within 120 seconds

**User failure indicators (must be eliminated):**
- Video upload failures or silent data loss during upload
- Partially completed patient records or assessments that are ambiguous — no clear visual indicator of completeness state
- Assessment records that cannot be located, duplicated, or linked to the wrong patient

### Business Success

| Metric | Target | Timeframe |
|--------|--------|-----------|
| Institutions onboarded (Phase 2) | ≥ 10 institutions | 12 months post Phase 2 launch |
| Case volume | ≥ 500 cases/month per institution | Steady state per institution |
| Cross-institution referrals processed | Measurable referral throughput with reply rate tracked | Post Phase 2 go-live |
| Phase 3 AI accuracy | Demonstrable improvement in assessment classification accuracy vs. manual baseline | Phase 3 validation |
| Phase 3 automation | Automated clinical suggestions accepted by clinicians at a meaningful rate | Phase 3 evaluation |

### Technical Success

- **Availability:** 100% uptime during daytime clinic hours (defined per institution operating hours); planned maintenance windows outside clinic hours only
- **Video reliability:** Zero silent upload failures; all failed uploads surface a clear error with recovery path
- **Data integrity:** No cross-institution data leakage (validated by isolation test suite before each Phase 2 institution onboarding)
- **Audit trail:** All create/edit/delete actions tracked via `UserActivityLog` with user, timestamp, and record reference
- **Security:** Rate limiting active on all 24 CRUD operations; session expiry enforced; CSP headers applied on all responses

### Measurable Outcomes

- **Phase 1 baseline:** All 5 assessment types completable end-to-end; report generation functional for PDF and Excel; zero known data loss scenarios
- **Phase 2 baseline:** Data isolation test suite passes before each institution onboarded; referral lifecycle (PENDING → REPLIED → CLOSED) functions correctly; notifications delivered within 120 seconds
- **Compliance readiness:** Sri Lankan health data regulations not yet formally implemented — system architecture (audit trail, access control, data residency capability) is designed to accommodate future regulatory requirements when formalised
- **Phase 3 readiness:** Structured assessment data and video metadata accumulated through Phases 1–2 are clean and accessible for AI pipeline consumption

## Product Scope

### Phase 1 — Core Platform (Fully Operational)

- Patient record management (full identifier set, birth data, clinical history)
- Five assessment workflows: GMA (video-linked), HINE, CDIC, General Paediatric Assessment, Developmental Assessment
- Video upload, streaming, and GMAssessment coupling
- Problem list with action history
- PDF and Excel report generation with institution branding
- Clinical attachments and bookmarks
- User management, role-based access, subscription control
- Security: 14-layer middleware, rate limiting, input sanitisation, session management

### Phase 2 — Multi-Institution + Referral (Implemented)

- Institution model with row-level data isolation (`InstitutionScopedManager`)
- Superadmin cross-institution dashboard, context switching, aggregate analytics
- Institution admin: user management, logo/branding, PDF branding
- Patient referral system: dual-record pattern, frozen clinical snapshot, UUID linkage
- Consultation thread: messages between institutions on a referral
- Cross-institution notifications: HTMX polling, ≤120-second delivery
- Patient move between institutions (with audit log)
- Feature flag (`MULTI_INSTITUTION_ENABLED`) for controlled rollout

### Phase 3 — AI Integration (Planned)

- AI-assisted GMA assessment classification — improving accuracy of neurodevelopmental outcome prediction
- Automated clinical suggestions surfaced during assessment workflows
- Training data pipeline leveraging structured assessment records and video metadata from Phases 1–2
- Scope and implementation approach to be defined in a future PRD iteration

## User Journeys

### Journey 1 — The Clinician: A Routine Assessment Day

**Persona:** Dr. Amali, a paediatric neurologist at a regional teaching hospital. She sees 15–20 patients per week and relies on structured documentation to track neurodevelopmental progress over time.

**Opening Scene:** Dr. Amali begins her morning clinic. A 4-month-old infant is brought in for a GMA follow-up. A nursing staff member has already registered the patient in NDAS with the BHT, NNC, and birth data. Dr. Amali opens the patient record and sees the prior assessment history at a glance.

**Rising Action:** She opens a new GMAssessment, selects the linked video recorded during the consultation, and works through the structured assessment fields. She adds indications, records her clinical observations, and notes the diagnosis. She navigates to the HINE section and completes a parallel HINE assessment for the same visit. She adds a problem entry to the problem list noting a concern for follow-up.

**Climax:** With both assessments complete, Dr. Amali generates a PDF report directly from the record — branded with her institution's header and logo. The report is ready to share with the referring GP and to file in the hospital record. The entire workflow — from patient record to signed report — took under 15 minutes.

**Resolution:** The patient's record is complete, timestamped, and linked to the video evidence. Three months later, when the infant returns, Dr. Amali has a full longitudinal picture at her fingertips.

**Capabilities revealed:** Patient registration, assessment workflow (GMA + HINE), video upload and linkage, problem list, PDF report generation, audit trail.

---

### Journey 2 — The Clinician in Doubt: Seeking a Second Opinion

**Persona:** Dr. Amali again — same clinician, harder case. An 8-month-old with atypical movement patterns that don't fit cleanly into her usual classification schema.

**Opening Scene:** Dr. Amali has completed her assessment but is uncertain about the outcome classification. She knows a specialist at the National Children's Hospital has seen hundreds of similar cases. Under the old system, she would have sent a WhatsApp message with a video clip and waited days for an informal reply.

**Rising Action:** Instead, she opens the referral panel on the patient record and initiates a referral to the National Children's Hospital. The system captures a frozen snapshot of the patient's full clinical record at this moment — demographics, all assessments, the linked video. She writes a brief clinical question and submits.

**Climax:** Within the hour, the specialist at the receiving institution — Dr. Roshan — reviews the referral in his institution's inbox. He has the full clinical picture in front of him: the frozen snapshot, the video, Dr. Amali's assessment notes. He writes a structured consultation reply with his classification and reasoning. NDAS notifies Dr. Amali within 120 seconds.

**Resolution:** Dr. Amali reads the specialist's opinion, updates her diagnosis, and appends a note to the problem list. The referral thread is now a permanent part of the patient record — a documented clinical consultation, not a lost chat message. She closes the referral.

**Capabilities revealed:** Referral creation, clinical snapshot, referral inbox, consultation thread, notifications, referral lifecycle (PENDING → REPLIED → CLOSED).

---

### Journey 3 — The Clinical Staff: Getting Patients into the System

**Persona:** Nimal, a clinical data entry officer at a district hospital. He is the first touchpoint for new patients — his job is to ensure every patient is correctly registered before the clinician sees them.

**Opening Scene:** A mother arrives with her premature infant for a neurodevelopmental follow-up. The infant was born at 28 weeks and has a complex birth history. Nimal needs to register the infant in NDAS before Dr. Amali's afternoon clinic.

**Rising Action:** Nimal opens the patient registration form. He enters the infant's identifiers (BHT, NNC), birth details (POG weeks and days, birth weight, HC), APGAR scores, and mother's details. The system validates the birth weight against gestational-age-specific ranges and flags an entry error — he corrects it before saving.

**Climax:** The patient record is saved and immediately visible to Dr. Amali in the afternoon's patient list. Nimal attaches the referring hospital's discharge summary as a clinical attachment directly to the record.

**Resolution:** By the time Dr. Amali opens the clinic session, every patient's record is complete and clinically ready. No paper forms, no transcription errors from paper to screen during the consultation.

**Capabilities revealed:** Patient registration, field validation, clinical attachments, user access controls (data entry role separate from clinical role).

---

### Journey 4 — The Institution Admin: Onboarding and Managing Users

**Persona:** Priya, the IT administrator at a newly onboarded hospital joining the NDAS network. She is responsible for setting up her institution on the platform and managing staff access.

**Opening Scene:** The superadmin has just created her institution in NDAS and sent her the admin credentials. Priya logs in for the first time.

**Rising Action:** Priya uploads her hospital's logo, sets the institution's short name (used in space-constrained UI slots), and configures the PDF branding so reports carry the hospital's header. She then creates user accounts for 8 clinical staff members, assigns appropriate roles, and sets initial passwords.

**Climax:** She reviews the institution dashboard — active users, recent patient registrations, assessment activity. One of her clinicians reports they can't log in; Priya resets their password without needing to escalate to the superadmin.

**Resolution:** Within two hours of receiving credentials, Priya's institution is operational. Her clinicians are logging in and registering their first patients.

**Capabilities revealed:** Institution branding, user management (admin scope), institution dashboard, credential management.

---

### Journey 5 — The Superadmin: Cross-Institution Oversight

**Persona:** The NDAS system administrator — responsible for the health of the entire platform across all institutions.

**Opening Scene:** It's Monday morning. The superadmin logs in and switches to the aggregate cross-institution view. He wants to check whether a newly onboarded hospital is active and how referral volume is trending across the network.

**Rising Action:** He reviews the superadmin dashboard — total cases, referral counts, active institutions, user activity by institution. He notices one institution has had no activity in two weeks. He switches context to that institution's view to investigate, confirms it's a known training period, and notes it.

**Climax:** A hospital wants to join the network. The superadmin runs the atomic institution onboarding flow: creates the Institution record, assigns an admin user, and the new institution is live — isolated from all other institutions' data. He runs a quick check against the isolation test results logged from the last deploy to confirm data boundaries are intact.

**Resolution:** The network grows by one institution. The superadmin has full visibility across all institutions without ever breaking data isolation boundaries for individual users.

**Capabilities revealed:** Superadmin dashboard, institution context switching, institution onboarding, aggregate analytics, data isolation validation.

---

### Journey Requirements Summary

| Journey | Core Capabilities Required |
|---------|---------------------------|
| Routine Assessment | Patient registration · 5 assessment workflows · Video-GMA linkage · Report generation · Problem list · Audit trail |
| Second Opinion Referral | Referral creation · Clinical snapshot · Referral inbox · Consultation thread · Notifications · Referral lifecycle |
| Clinical Staff Registration | Patient form + validation · Attachments · Role-based access |
| Institution Admin Onboarding | Institution branding · User management · Institution dashboard |
| Superadmin Oversight | Cross-institution dashboard · Context switching · Onboarding flow · Aggregate analytics · Isolation validation |

## Domain-Specific Requirements

### Compliance & Regulatory

- **Sri Lankan Health Data Regulations:** No formal regulations currently enacted. System architecture is designed to accommodate future regulatory requirements — audit trail, access control, data residency flexibility, and role-based data boundaries are implemented ahead of regulation.
- **Clinical Decision Support Classification:** NDAS functions as a clinical decision support tool, not merely a record-storage system. Assessment workflows incorporate structured recommendations aligned with local Sri Lankan neurodevelopmental clinical guidelines. This classification carries clinical responsibility — outputs that influence diagnosis or treatment must be based on validated clinical criteria and clearly attributed to the assessing clinician.
- **Assessment Guideline Alignment:** All assessment scoring, threshold values, and clinical recommendations must conform to locally accepted neurodevelopmental guidelines (including GMA classification criteria, HINE scoring thresholds, and developmental milestone ranges). Deviations from guideline-defined values require explicit validation before deployment.
- **Phase 3 AI Regulatory Readiness:** AI-generated clinical suggestions in Phase 3 must be positioned as decision support (not autonomous diagnosis), traceable to the underlying model and training data, and aligned with the same local guidelines governing manual assessments. Clinical validation of AI outputs is required before production use.

### Technical Constraints

- **Deployment Flexibility:** System must support both on-premise (local hospital servers) and cloud deployment without architectural changes. Environment-specific configuration managed entirely via environment variables.
- **Data Isolation (Critical):** A clinician at Institution A must never be able to view, search, or access patient records belonging to Institution B under any circumstance, except: a patient has been formally referred (frozen clinical snapshot accessible to receiving institution only), formally transferred (PatientMoveLog with full audit trail), or a superadmin is viewing in cross-institution context.
- **Audit Trail:** All create, edit, and delete actions on patient records, assessments, videos, referrals, and user accounts are logged via `UserActivityLog` with user identity, timestamp, and record reference. Access is role-scoped:
  - **Superadmin** — can view activity logs for all users across all institutions
  - **Institution Admin** — can view activity logs for users within their own institution only
  - **Regular users** — no access to activity logs
- **Session Security:** 1-hour session timeout with browser-close expiry. Rate limiting on all 24 CRUD operations. CSP headers on all responses.
- **Patient Consent:** No explicit patient consent workflow required at the application level — institutional approval processes operate outside the system boundary.

### Integration Requirements

- **Current state:** Standalone system — no integration with external HIS, laboratory, or imaging systems at this time.
- **Future readiness:** Data models use structured identifiers (BHT, NNC, PTC, PC, PIN, Disk No.) that align with Sri Lankan hospital record systems, enabling future HIS integration without model changes.

### Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Cross-institution data leakage | `InstitutionScopedManager` enforces row-level isolation at ORM level; automated isolation test suite must pass before each new institution is onboarded |
| Clinical recommendation error | All assessment thresholds and recommendation logic must reference validated local guideline values; changes to clinical logic require explicit review |
| Video loss during upload | Client-side upload failure detection with clear error messaging and recovery path; no silent failures permitted |
| Audit log access control | Logs written at middleware level — not editable via application views; superadmin sees all institutions; institution admin sees own institution only; regular users have no access |
| Phase 3 AI misuse | AI outputs labelled as decision support only; final clinical decision always attributed to and owned by the assessing clinician |

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. Video-Linked Clinical Assessment with Multi-Clinician Opinion Layer**

The core GMA workflow establishes a strict OneToOne coupling between a clinical video and its assessment record — making clinical evidence and its structured interpretation architecturally inseparable. Beyond the primary assessment, the system supports a multi-clinician opinion layer: additional users can log their own diagnosis selection with a written justification comment against the same assessment, creating a timestamped, attributed opinion log. This enables intra-institution peer review without disrupting the primary assessment record. Combined with the cross-institution referral system, NDAS implements a two-tier expert consultation model: informal peer review within an institution, and formal documented consultation across institutions.

**2. Frozen Clinical Snapshot for Asynchronous Multi-Expert Consultation**

When a cross-institution referral is created, the system atomically captures an immutable snapshot of the patient's full clinical record — demographics, all assessments, linked video, problem list — at the exact moment of referral. The receiving specialist works from this frozen record, immune to subsequent changes by the referring clinician. This solves a fundamental problem in asynchronous clinical collaboration: the specialist and the referring clinician must be working from the same clinical picture. The dual-record pattern (ReferralSent + ReferralReceived, linked only by UUID) ensures both institutions hold an independent, permanent record of the consultation.

**3. Dual-Pathway AI for Neurodevelopmental Assessment (Phase 3)**

Phase 3 positions NDAS as an AI-assisted clinical decision support platform through two complementary input pathways:
- **Computer vision pathway:** Direct analysis of GMA movement videos to detect movement quality patterns correlated with neurodevelopmental outcomes
- **Structured data pathway:** Classification using the accumulated assessment fields, scoring values, and clinical observations captured through normal clinical use in Phases 1–2

The platform generates its own AI training dataset through routine clinical operation — every completed assessment and linked video contributes to the training corpus. This self-reinforcing data flywheel, grounded in Sri Lankan clinical population data, is the foundation for locally-validated AI models rather than models trained on foreign clinical datasets.

### Market Context & Competitive Landscape

NDAS addresses a gap specific to the Sri Lankan clinical context: no existing system combines video-based GMA assessment, structured neurodevelopmental scoring, multi-institution collaboration, and local clinical guideline alignment in a single platform. Generic EMR systems handle records but not video-linked clinical assessment. International GMA tools (if available) do not address local workflows, multi-institution collaboration, or local guideline recommendations.

### Validation Approach

| Innovation | Validation Method |
|------------|------------------|
| Multi-clinician opinion layer | Clinical workflow validation — do clinicians use and trust the opinion log? Do divergent opinions surface useful clinical discussion? |
| Frozen snapshot referral | Integrity check — snapshot content verified against source record at referral time; immutability enforced at model level |
| Phase 3 AI (computer vision) | Clinical validation against expert-graded video assessments; accuracy benchmarked against manual classification baseline |
| Phase 3 AI (structured data) | Cross-validation against existing assessment records; sensitivity/specificity reported against known outcomes |

### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Multi-opinion confusion | Primary assessment clearly distinguished from opinion log; opinion log entries are attributed and timestamped — not anonymous |
| AI over-reliance | All AI outputs labelled as decision support; clinician attribution mandatory on every assessment regardless of AI suggestion |
| Training data bias | Phase 3 models trained on Sri Lankan clinical population data from NDAS — not repurposed from foreign datasets; local guideline alignment verified |
| Snapshot data staleness | Snapshot clearly date-stamped at referral creation; receiving specialist sees snapshot date — not the current record state |

## Web Application Specific Requirements

### Project-Type Overview

NDAS is a server-rendered Multi-Page Application (MPA) built on Django MVT with HTMX for dynamic interactions. There is no client-side JavaScript framework — all page rendering is server-side, with HTMX handling targeted partial-page updates (notifications, dynamic form interactions) without full-page reloads. This architecture prioritises clinical reliability and security over client-side interactivity.

### Browser Matrix

| Browser | Support Level |
|---------|--------------|
| Chrome (latest) | Primary — full support required |
| Firefox (latest) | Primary — full support required |
| Mobile Chrome (Android) | Secondary — responsive layout required |
| Mobile Safari (iOS) | Secondary — responsive layout required |
| Tablet browsers (Chrome/Safari) | Secondary — responsive layout required |
| Internet Explorer / Legacy Edge | Not supported |

All modern browser features used (HTMX, Video.js, CSP nonces, fetch API) are compatible with the supported browser matrix. No polyfills required.

### Responsive Design

- **Primary device:** Desktop / laptop — clinical data entry, assessment completion, report generation
- **Secondary devices:** Mobile and tablet — used for quick lookups, reviewing records, notifications review; full assessment completion on mobile is a secondary use case
- **Framework:** AdminLTE 3.2 + Bootstrap 4.6 grid — inherently responsive; all templates must use Bootstrap column classes for multi-device layout
- **Video playback:** Video.js player must be functional and usable on tablet screens; mobile video playback is secondary
- **No native app:** NDAS is web-only — no hybrid app wrapper, no PWA manifest required

### Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Standard page load | < 3 seconds | Clinical list and detail views |
| Video upload (100MB typical) | Progress indicator required; no silent hang | Upload must show real-time progress; failure must surface explicit error with retry |
| Video playback start | < 5 seconds to first frame | Streaming via Video.js; server must support HTTP range requests |
| Notification polling | ≤ 120 seconds end-to-end | HTMX polls every 60 seconds |
| Report generation (PDF/Excel) | < 10 seconds | Synchronous generation acceptable at current scale |
| Patient list / search | < 2 seconds | `select_related()` required; N+1 queries are a blocking defect |

**Video file size context:** Typical GMA assessment videos are approximately 100MB. The system's configured maximum is 2GB (accommodating edge cases). Upload handling must use chunked progress tracking — a 100MB upload on a hospital network (10–50 Mbps) takes 15–80 seconds and must not appear frozen.

### SEO Strategy

Not applicable. All clinical views are protected by `@login_required`. The only public-facing surface is the login page — no SEO optimisation required.

### Accessibility Level

No formal WCAG compliance requirement at this time. Standard AdminLTE semantic HTML structure provides baseline accessibility. Screen reader or keyboard-navigation optimisation is out of scope.

### Implementation Considerations

- **HTMX usage pattern:** Targeted partial updates only (notification badge, dynamic form sections) — not full-page HTMX navigation
- **Inline scripts:** All `<script>` tags require `nonce="{{ request.csp_nonce }}"` — enforced by CSPMiddleware; missing nonces will cause scripts to silently fail in production
- **AdminLTE constraints:** UI framework is frozen at AdminLTE 3.2 + Bootstrap 4.6 + Font Awesome 6.4 — no version upgrades, no additional CSS frameworks
- **Video streaming:** Server must support HTTP range requests for Video.js seek functionality; static file serving via WhiteNoise in production
- **Session behaviour:** 1-hour timeout with browser-close expiry — clinicians on shared workstations will need to re-authenticate each session

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Platform MVP — NDAS is not a concept being validated; it is an operational clinical system. The scoping exercise defines stabilisation boundaries per phase and the minimum viable scope for the next development horizon (Phase 3 AI).

**Overall posture:** Phase 1 and Phase 2 are implemented and operational. Ongoing effort in both phases is stabilisation (bug fixes + targeted refinements), not new capability development. Phase 3 is the active development frontier.

---

### Phase 1 — Core Platform (Operational / Stabilisation)

**Status:** Fully implemented and in clinical use.

**Core User Journeys Supported:**
- Routine clinical assessment (Journey 1) — patient registration → GMA + parallel assessments → report generation
- Clinical staff data entry (Journey 3) — patient registration, field validation, attachment upload
- Multi-clinician opinion layer on GMA assessment — intra-institution peer review

**Must-Have Capabilities (all implemented):**
- Patient record management with full Sri Lankan clinical identifier set
- Five assessment workflows: GMA (video-linked), HINE, CDIC, GPA, Developmental
- Video upload with progress tracking, streaming, and OneToOne GMA coupling
- Multi-clinician opinion log per GMA assessment (diagnosis selection + justification comment)
- Problem list with action history
- PDF and Excel report generation with institution branding
- Clinical attachments and bookmarks
- User management, role-based access, subscription control
- 14-layer security middleware stack, rate limiting, audit trail

**Ongoing Stabilisation Scope:**
- Known bug fixes across Phase 1 workflows
- Targeted refinements to existing clinical workflows based on clinical user feedback
- No new Phase 1 capability additions planned

---

### Phase 2 — Multi-Institution + Referral (Operational / Stabilisation)

**Status:** Fully implemented; production rollout pending stabilisation validation.

**Core User Journeys Supported:**
- Clinician seeking second opinion (Journey 2) — referral creation → frozen snapshot → consultation thread → notification
- Institution admin onboarding (Journey 4) — branding, user management, institution dashboard
- Superadmin oversight (Journey 5) — cross-institution dashboard, context switching, institution onboarding

**Must-Have Capabilities (all implemented):**
- Institution model with row-level data isolation (`InstitutionScopedManager`)
- Superadmin: cross-institution dashboard, context switching, aggregate analytics, atomic institution onboarding
- Institution admin: user management, logo/branding, PDF branding, institution dashboard
- Patient referral: dual-record pattern, frozen clinical snapshot, UUID linkage, consultation thread
- Cross-institution notifications: HTMX polling, ≤120-second delivery
- Patient move between institutions with audit log
- Audit log access: superadmin (all institutions), institution admin (own institution only)
- Feature flag (`MULTI_INSTITUTION_ENABLED`) for controlled rollout

**Ongoing Stabilisation Scope:**
- Bug fixes and refinements to multi-institution and referral workflows
- Data isolation test suite (`institution/tests/test_isolation.py`) must pass before `MULTI_INSTITUTION_ENABLED=True` in production
- No new Phase 2 capability additions planned

---

### Phase 3 — AI Integration (Planned)

**Minimum Viable AI Feature:**
Automatic movement type identification from GMA video — computer vision analysis of recorded infant movement to classify movement quality patterns according to GMA criteria. This is the highest-value, most direct application of AI to the core clinical workflow.

**Phase 3 Growth Features (post-minimum viable):**
- Structured data classification: risk scoring and clinical outcome prediction using accumulated assessment fields, scoring values, and clinical observations from Phases 1–2
- Automated clinical suggestions surfaced during assessment workflows, aligned with local Sri Lankan neurodevelopmental guidelines

**Phase 3 Prerequisites:**
- Sufficient training data accumulated through Phase 1–2 clinical use (video + assessment records)
- Clinical validation of AI outputs against expert-graded assessments before production deployment
- AI outputs must be labelled as decision support — clinician attribution remains mandatory

---

### Explicitly Out of Scope

| Feature | Rationale |
|---------|-----------|
| Billing / financial management | Out of scope by design — NDAS is a clinical tool, not a practice management system |
| Patient-facing portal | Not planned — system is for clinical staff only |
| Telemedicine / video conferencing | Not planned — NDAS manages recorded assessments, not live consultations |
| External HIS / laboratory integration | Not planned for current phases — future readiness built into data model identifiers |
| WCAG accessibility compliance | Not required at this time |

---

### Risk Mitigation Strategy

| Risk Category | Risk | Mitigation |
|---------------|------|------------|
| **Technical** | Phase 3 computer vision model requires large, high-quality labelled video dataset | Accumulate training data through Phase 1–2 clinical use before Phase 3 development begins; validate dataset size before committing to model training |
| **Technical** | Phase 3 CV model performance variability with different video recording conditions | Define minimum video quality standards; include quality check step in Phase 3 upload workflow |
| **Market** | Phase 2 institution adoption slower than projected | Feature flag allows single-institution fallback at any time; no disruption to Phase 1 users |
| **Resource** | Phase 3 requires ML/CV expertise beyond current Django stack | Phase 3 is a separate technical domain — plan for dedicated ML engineering capability or partnership |
| **Stability** | Known bugs in Phase 1 and Phase 2 affecting clinical workflows | Structured bug triage before Phase 3 development begins; clinical workflows must be stable before AI layer is added |

---

## Functional Requirements

FRs are organised by capability area with phase labels (Phase 1 / Phase 2 / Phase 3 / Cross-cutting). Each FR defines a user or system capability — not an implementation approach. The FR Summary table at the end of this section maps all 58 FRs to their phase.

### Capability Area 1 — Patient Record Management

**FR1:** A clinical staff member can register a new patient with the full Sri Lankan clinical identifier set (BHT, NNC, PTC, PC, PIN, Disk No.), birth data, gestational age (weeks + days), birth weight, head circumference, APGAR scores, and maternal history.

**FR2:** The system validates birth weight against gestational-age-specific ranges at registration and flags out-of-range entries before saving; the user must correct or explicitly acknowledge the flag to proceed.

**FR3:** A clinician can view the complete patient record — all prior assessments (across all types), linked videos, problem list, attachments, and referral history — from a single patient detail view.

**FR4:** An authorised user can edit an existing patient record; all field-level changes are captured in the audit log with user identity, timestamp, and record reference.

**FR5:** A clinical user can search and filter the patient list by name, BHT, NNC, or any standard identifier field, with results returned within 2 seconds.

---

### Capability Area 2 — Assessment Workflows

**FR6:** A clinician can create a GMA (General Movement Assessment) record for a patient, specifying indications for GMA, clinical observations, and diagnosis, with the record permanently linked to a specific uploaded video.

**FR7:** A clinician can create a HINE (Hammersmith Infant Neurological Examination) assessment for a patient with all structured HINE scoring fields.

**FR8:** A clinician can create a CDIC assessment for a patient with all structured CDIC data fields.

**FR9:** A clinician can create a General Paediatric Assessment (GPA) for a patient with all structured GPA fields.

**FR10:** A clinician can create a Developmental Assessment for a patient with all structured developmental milestone fields.

**FR11:** A clinician can view the full assessment history for a patient in chronological order, spanning all five assessment types, from the patient detail view.

**FR12:** A clinician can edit an existing assessment record; all changes are tracked in the audit log.

---

### Capability Area 3 — Video Management

**FR13:** A clinical user can upload a video file (supported formats: mp4, mov, avi, mkv, webm; maximum 2GB) to a patient record with a real-time progress indicator; upload failures surface an explicit error message with a recovery path — silent failures are not permitted.

**FR14:** The system enforces a strict OneToOne coupling between a video and its linked GMAssessment — one video maps to exactly one GMA record; a video cannot be linked to more than one assessment.

**FR15:** A clinician can stream a patient's linked video directly within the patient or assessment record via an embedded video player with seek, pause, and playback controls, with the first frame available within 5 seconds.

**FR16:** An authorised user can delete a video; deletion is blocked if the video is linked to an active GMAssessment record.

---

### Capability Area 4 — Multi-Clinician Opinion Layer

**FR17:** Any authorised clinician within the same institution can add a secondary opinion to an existing GMA assessment by selecting a diagnosis and writing a justification comment, without altering the primary assessment record or the primary assessor's data.

**FR18:** All secondary opinions on a GMA assessment are stored as an attributed, timestamped opinion log; each entry displays the author's name, their diagnosis selection, and their written justification.

**FR19:** A clinician can view all secondary opinions on a GMA assessment alongside the primary assessment record in a single view.

---

### Capability Area 5 — Problem List

**FR20:** A clinician can add a clinical problem entry to a patient's problem list with a description, problem category, and clinical status.

**FR21:** A clinician can add action history entries to an existing problem, documenting follow-up actions, dates, and outcomes.

**FR22:** A clinician can view the complete problem list and full action history timeline for a patient.

---

### Capability Area 6 — Report Generation

**FR23:** A clinician can generate a formatted PDF report for a patient that includes selected demographic fields, selected assessment records, and the institution's configured branding (logo and header).

**FR24:** A clinician or administrator can generate an Excel report for one or more patient records with configurable field selection, optional anonymisation, and multi-sheet output.

**FR25:** PDF report generation completes within 10 seconds for a typical patient record; the generated report is downloadable immediately.

---

### Capability Area 7 — Clinical Attachments & Bookmarks

**FR26:** A clinical user can upload and attach documents or images (document: max 100MB; image: max 10MB) to a patient record; file type and size are validated before upload proceeds.

**FR27:** A clinical user can bookmark a patient record and access their bookmarks list for quick navigation to frequently reviewed patients.

---

### Capability Area 8 — User Management & Access Control

**FR28:** An institution admin can create, edit, deactivate, and reset passwords for user accounts within their own institution; an institution admin cannot create or modify user accounts in other institutions.

**FR29:** The system enforces role-based access control with distinct permission sets for: clinical staff (patient registration, attachments), clinician (assessments, referrals, reports), institution admin (user management, institution configuration), and superadmin (cross-institution access).

**FR30:** An institution admin can manage subscription status for users within their institution; users with an inactive subscription are blocked from creating or editing records.

**FR31:** All authenticated sessions enforce a 1-hour inactivity timeout and browser-close expiry; upon expiry the user is redirected to the login page.

---

### Capability Area 9 — Multi-Institution Foundation (Phase 2)

**FR32:** The system enforces strict row-level data isolation — a user at Institution A cannot view, search, query, or access any patient records, assessments, videos, or referrals belonging to Institution B, except through a formal referral or authorised transfer.

**FR33:** A superadmin can create a new institution record with full configuration (name, short name, logo, branding); the new institution is immediately active and its data is isolated from all other institutions.

**FR34:** A superadmin can switch context to any institution and view that institution's data without granting cross-institution access to any other user.

**FR35:** An institution admin can configure their institution's display name, short name, logo, and PDF report branding without superadmin involvement.

**FR36:** A superadmin can view aggregate analytics across all institutions including total patient registrations, assessment counts, referral volume, and active user counts per institution.

**FR37:** The system supports a controlled rollout toggle that enables or disables multi-institution features without requiring redeployment; single-institution fallback must remain fully functional when multi-institution mode is disabled.

---

### Capability Area 10 — Patient Referral System (Phase 2)

**FR38:** A clinician can initiate a cross-institution referral for a patient to a specific target institution, writing a clinical question or context note at the time of referral creation.

**FR39:** When a referral is created, the system atomically captures an immutable frozen clinical snapshot of the patient's full record — demographics, all assessment records, linked video, and problem list — at the exact moment of referral creation.

**FR40:** The frozen clinical snapshot is permanently immutable; subsequent edits to the source patient record do not alter the snapshot held by the receiving institution.

**FR41:** A referral generates dual records — one at the sending institution (ReferralSent) and one at the receiving institution (ReferralReceived) — linked only by a shared UUID; both records are permanently retained by each institution independently.

**FR42:** A clinician at the receiving institution can view the full frozen clinical snapshot — including all assessments and the linked video — when reviewing an incoming referral.

**FR43:** The referral lifecycle enforces the sequence PENDING → REPLIED → CLOSED; each state transition is logged with user identity and timestamp.

**FR44:** A clinician at the receiving institution can add a structured consultation reply to a referral, including diagnosis selection and written commentary; the reply transitions the referral from PENDING to REPLIED.

**FR45:** A clinician can close a referral after consultation is complete; the closed referral thread is permanently accessible to both institutions.

---

### Capability Area 11 — Consultation Thread & Notifications (Phase 2)

**FR46:** A clinician can send and receive messages within a referral's consultation thread; all messages are attributed to the sender with a timestamp and are permanently retained.

**FR47:** A clinician receives a notification within 120 seconds of a referral event: new referral received, consultation reply received, or referral closed.

**FR48:** Notifications are delivered via HTMX polling on a ≤60-second poll cycle, achieving end-to-end delivery within 120 seconds.

**FR49:** A clinician can view their notification inbox and navigate directly from a notification to the relevant referral record in a single click.

---

### Capability Area 12 — Patient Transfer (Phase 2)

**FR50:** A superadmin can formally transfer a patient record from one institution to another; the transfer is logged in full (source institution, destination institution, transferred by, timestamp).

**FR51:** After a formal transfer, the patient record is accessible only to the destination institution; the source institution retains a read-only transfer log entry and no further access to the patient's data.

---

### Capability Area 13 — Audit Trail & Activity Logging

**FR52:** The system logs all create, edit, and delete actions on patient records, assessments, videos, referrals, and user accounts with: acting user identity, action type, affected record reference, and timestamp.

**FR53:** A superadmin can view activity logs for all users across all institutions.

**FR54:** An institution admin can view activity logs for users within their own institution only; regular users have no access to any activity logs.

**FR55:** Audit log entries are written at middleware level and are not editable or deletable through any application view.

---

### Capability Area 14 — Phase 3 AI Integration (Planned)

**FR56:** The system will provide AI-assisted movement type identification from GMA videos — surfacing movement quality pattern classifications to the assessing clinician during the GMA assessment workflow — based on computer vision analysis of the linked assessment video.

**FR57:** The system will surface automated clinical suggestions aligned with local Sri Lankan neurodevelopmental guidelines during assessment completion workflows, labelled clearly as decision support (not autonomous diagnosis).

**FR58:** All AI-generated suggestions and classifications must be explicitly labelled as decision support in the UI; clinician attribution remains mandatory on every assessment regardless of AI suggestions; the assessing clinician's recorded diagnosis owns the clinical record.

---

### FR Summary

| Capability Area | FR Range | Count | Phase |
|-----------------|----------|-------|-------|
| Patient Record Management | FR1–FR5 | 5 | Phase 1 |
| Assessment Workflows | FR6–FR12 | 7 | Phase 1 |
| Video Management | FR13–FR16 | 4 | Phase 1 |
| Multi-Clinician Opinion Layer | FR17–FR19 | 3 | Phase 1 |
| Problem List | FR20–FR22 | 3 | Phase 1 |
| Report Generation | FR23–FR25 | 3 | Phase 1 |
| Clinical Attachments & Bookmarks | FR26–FR27 | 2 | Phase 1 |
| User Management & Access Control | FR28–FR31 | 4 | Phase 1 |
| Multi-Institution Foundation | FR32–FR37 | 6 | Phase 2 |
| Patient Referral System | FR38–FR45 | 8 | Phase 2 |
| Consultation Thread & Notifications | FR46–FR49 | 4 | Phase 2 |
| Patient Transfer | FR50–FR51 | 2 | Phase 2 |
| Audit Trail & Activity Logging | FR52–FR55 | 4 | Cross-cutting |
| Phase 3 AI Integration | FR56–FR58 | 3 | Phase 3 |
| **TOTAL** | | **58** | |

---

## Non-Functional Requirements

NFRs specify how well the system must perform. Only categories relevant to NDAS are documented: Performance, Security, Data Integrity, Reliability, Scalability, Maintainability, and Compatibility. Accessibility (out of scope per scoping decision) and Integration (no active integrations required) are omitted.

### Performance

**NFR1:** Standard clinical page loads (patient list, patient detail, assessment detail) complete within 3 seconds under normal clinic operating load.

**NFR2:** Patient list and search results are returned within 2 seconds; N+1 query patterns in any list or search view are a blocking defect — `select_related()` and `prefetch_related()` are mandatory for all related object access in list views.

**NFR3:** Video streaming delivers the first frame within 5 seconds; the server must support HTTP range requests to enable Video.js seek functionality.

**NFR4:** Video upload (typical 100MB file) displays a real-time progress indicator and does not appear frozen at any point during transfer; upload progress must be visually updated at least every 5 seconds.

**NFR5:** PDF and Excel report generation completes within 10 seconds for a typical single-patient record; the generated file is immediately downloadable upon completion.

**NFR6:** Notification end-to-end delivery from trigger event to clinician-visible badge occurs within 120 seconds; HTMX polling cycle must not exceed 60 seconds.

---

### Security

**NFR7:** All data in transit is encrypted via HTTPS/TLS; `SECURE_SSL_REDIRECT` is enforced in production; HTTP connections are not accepted.

**NFR8:** Content Security Policy (CSP) headers are applied on every HTTP response; all inline `<script>` tags require a server-issued nonce — missing nonces cause silent script failure in production (enforced by CSPMiddleware).

**NFR9:** Session timeout is enforced at 1-hour inactivity with browser-close expiry on all authenticated sessions; expired sessions redirect to the login page without data loss.

**NFR10:** Rate limiting is enforced on all 24 CRUD operations: create and edit views at 10 requests/minute, delete views at 5 requests/minute, keyed per user-or-IP.

**NFR11:** All user-supplied text input is sanitised to remove XSS vectors before persistence; all uploaded file MIME types are validated against the allowed extension list; file size limits are enforced before storage is allocated.

**NFR12:** User credentials are stored using Django's PBKDF2+SHA256 default password hasher; no plaintext or reversible credential storage is permitted anywhere in the system.

---

### Data Integrity

**NFR13:** Cross-institution data isolation is absolute — no application code path exists by which a user at Institution A can retrieve, display, or modify patient records, assessments, or referrals belonging to Institution B, except through a formal referral or superadmin-authorised transfer. This constraint is validated by an automated isolation test suite that must pass before multi-institution mode is enabled in any production environment.

**NFR14:** Frozen referral snapshots are written once at referral creation time and are never subsequently modified; immutability is enforced at the model level, not solely by application convention.

**NFR15:** Referral dual-record creation is atomic — either both the sending and receiving institution records are created or neither is; partial creation leaving orphaned records is not permitted.

---

### Reliability

**NFR16:** System availability during each institution's defined daytime clinic hours targets 100%; planned maintenance windows are scheduled exclusively outside clinic hours with advance notice to institution admins.

**NFR17:** Video upload failures surface an explicit, user-readable error message with a clear recovery path immediately upon failure detection; silent upload failures — where an upload appears to complete but data is not stored — are not permitted under any circumstances.

---

### Scalability

**NFR18:** The system must support ≥10 active institutions each generating ≥500 patient cases per month without standard page load performance degrading more than 10% versus single-institution baseline metrics.

**NFR19:** Institution onboarding (creating a new Institution record and assigning its first admin user) executes as an atomic operation with no measurable impact on existing institutions' data access, query performance, or session state.

---

### Maintainability

**NFR20:** All new Django models must inherit from `TimeStampedModel` and `UserTrackingMixin`; all choice definitions must be added to `ndas/custom_codes/choice.py`; all field validators must be added to `ndas/custom_codes/validators.py`; inline model choices and ad-hoc validators defined outside `custom_codes/` are not permitted.

**NFR21:** All searchable model fields must declare `db_index=True`; foreign key and related object access in views must use `select_related()` or `prefetch_related()` — unoptimised related object access in any list or search view is treated as a defect.

**NFR22:** `get_object_or_404()` must be used for all single-object lookups in views; direct `.objects.get()` calls in view code are not permitted.

---

### Compatibility

**NFR23:** Full functionality is required on Chrome (latest) and Firefox (latest) desktop; responsive layout is required on mobile Chrome (Android) and mobile Safari (iOS); Internet Explorer and legacy Edge are not supported.

---

### NFR Summary

| Category | NFR Range | Count |
|---|---|---|
| Performance | NFR1–NFR6 | 6 |
| Security | NFR7–NFR12 | 6 |
| Data Integrity | NFR13–NFR15 | 3 |
| Reliability | NFR16–NFR17 | 2 |
| Scalability | NFR18–NFR19 | 2 |
| Maintainability | NFR20–NFR22 | 3 |
| Compatibility | NFR23 | 1 |
| **TOTAL** | | **23** |
