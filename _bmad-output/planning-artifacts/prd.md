---
stepsCompleted: [step-01-init, step-02-discovery, step-02b-vision, step-02c-executive-summary, step-03-success, step-04-journeys, step-05-domain, step-06-innovation, step-07-project-type, step-08-scoping, step-09-functional, step-10-nonfunctional, step-11-polish, step-12-complete]
workflowStatus: complete
completedDate: '2026-02-19'
inputDocuments:
  - docs/index.md
  - docs/project-overview.md
  - docs/architecture.md
  - docs/data-models-main.md
  - docs/api-contracts-main.md
  - docs/component-inventory-main.md
  - docs/custom-codes-reference.md
  - docs/development-guide.md
workflowType: 'prd'
briefCount: 0
researchCount: 0
brainstormingCount: 0
projectDocsCount: 8
classification:
  projectType: web_app
  domain: healthcare
  complexity: high
  projectContext: brownfield
  prdScope: existing-capabilities
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

## Project Classification

| Attribute | Value |
|-----------|-------|
| **Project Type** | Web Application (Django multi-page, server-rendered) |
| **Domain** | Healthcare — Neurodevelopmental Paediatrics |
| **Complexity** | High (clinical data integrity, role-based access, medical identifiers, patient safety) |
| **Project Context** | Brownfield — documenting existing system capabilities |
| **Stack** | Django 4.2 · PostgreSQL/SQLite · AdminLTE 3.2 · Bootstrap 4.6 · HTMX · Video.js |

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

**Climax:** Six months later, the admin runs a subscription review. One user account is inactive — the admin deactivates it. Another centre requests access; the admin adds a new user scoped to that centre's patient records.

**Resolution:** The system remains clean: only active, authorised clinicians have access. The audit trail shows every action taken by every user. The admin has full visibility into system activity without touching clinical data.

### Journey Requirements Summary

| Journey | Capabilities Revealed |
|---------|----------------------|
| First assessment | Patient registration · Perinatal data capture · Video upload · HINE scoring · Problem list creation · Intervention planning |
| Follow-up review | Longitudinal record access · Sequential assessment entry · Developmental scoring · Trajectory visibility · PDF report generation |
| Admin onboarding | User account management · Subscription control · Activity log review · Multi-centre access scoping |

## Domain-Specific Requirements

### Compliance & Regulatory

- No national statutory healthcare data regulation currently applies; system operates under institutional and hospital authority policy
- Patient data retained for life with patient consent — records may not be permanently deleted; only deactivated or archived
- All clinical data modifications attributable to a named, authenticated user with timestamp (audit trail mandatory)
- Access restricted to authenticated, authorised clinical staff — no anonymous or public access to patient data

### Clinical Validation Constraints

- All structured assessment instruments (HINE, GMA, CDIC, GPA, Developmental Assessment) enforce complete data entry before submission — partial assessments cannot be saved as final records
- Assessment scoring follows validated clinical protocols: HINE 0–78 (normal threshold > 73); Developmental Assessment across four domains (GM, FMV, HSL, SEB) with age-normed reference (0–72 months corrected age); APGAR 0–10 at 1, 5, and 10 minutes
- Perinatal data validation enforced: birth weight 300g–8000g; gestational age 20–44 weeks + 0–6 days
- GMA assessments require a linked video record; that video cannot be deleted while the assessment link is active

### Integration Requirements

- Currently operates as a standalone system — no live integration with external HIS, PACS, or lab systems
- Architecture supports future multi-centre and multi-institution integration with scoped cross-centre data access
- PDF and Excel export serves as the current integration bridge for referring specialists and research use

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

### Phase 2 — Growth Features (Planned)

- **Per-user notification panel** — clinician-scoped alerts and activity updates
- **Real-time notifications** — instant in-app alerts on patient record changes
- **Referral system** — structured referral workflow between clinicians and specialists
- **Role-specific dashboards:**
  - *Clinician dashboard* — assigned patients, recent activity, notifications
  - *Institutional dashboard* — centre-level patient population, assessment activity, operational metrics
  - *Superuser / Admin dashboard* — system-wide view: all centres, user management, subscription status, system health
- **Multi-centre / multi-institution support** — full operational deployment across multiple sites with scoped data access

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
- **FR3:** Clinicians can search for patients by name, BHT, NNC, or other identifiers
- **FR4:** Clinicians can edit existing patient demographic and perinatal data
- **FR5:** Clinicians can attach clinical documents to a patient record
- **FR6:** Clinicians can bookmark patients for quick personal access
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
- **FR25:** Clinicians can update the status of problems (active, resolved, monitored, etc.)
- **FR26:** Clinicians can view the complete problem, intervention, and response history for a patient

### Reporting & Data Export

- **FR27:** Clinicians can generate a PDF report summarising an individual patient's assessment history
- **FR28:** Clinicians can export assessment data to Excel format
- **FR29:** Clinicians can generate anonymised cohort reports for research use
- **FR30:** Clinicians can filter report data by date range, assessment type, and patient criteria

### User & Access Management

- **FR31:** Administrators can create, edit, and deactivate user accounts
- **FR32:** Administrators can assign and manage user roles (superuser, staff)
- **FR33:** Administrators can manage user subscriptions
- **FR34:** Administrators can view user activity logs
- **FR35:** The system requires authentication for all clinical routes — no unauthenticated access to patient data
- **FR36:** The system enforces role-based access — superusers access all records; staff access records within their scope
- **FR37:** The system automatically records the identity and timestamp of every record creation and modification

### Notifications & Communication *(Phase 2)*

- **FR38:** Clinicians can view a personal notification panel showing alerts relevant to their patients and activity
- **FR39:** The system delivers real-time notifications when patient records associated with a clinician are updated
- **FR40:** Clinicians can submit a structured referral to another clinician or specialist
- **FR41:** Clinicians can view, accept, and manage referrals they have received

### Dashboards & Multi-Centre *(Phase 2)*

- **FR42:** Each user role has access to a role-specific dashboard — clinician view, institutional view, or system-wide admin view
- **FR43:** Administrators can manage multiple clinical centres within a single system instance
- **FR44:** The system scopes patient data, reporting, and dashboards by clinical centre in multi-centre deployments

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
- **NFR10:** All HTTP responses include security headers: CSP, X-Frame-Options, HSTS, and additional headers enforced by middleware

### Reliability

- **NFR11:** The system is available during all clinic operating hours — planned maintenance is scheduled outside clinical session times
- **NFR12:** Patient data is recoverable following system failure — automated daily backups are required
- **NFR13:** All multi-step record operations use database transactions — no partial saves; data integrity enforced at the database level

### Scalability

- **NFR14:** The system architecture supports deployment across multiple clinical centres without per-centre code changes
- **NFR15:** The system supports growth from single-centre to multi-institution deployment without re-architecture of the core application

### Audit & Data Integrity

- **NFR16:** Every record creation, modification, and attempted deletion is logged with user identity and timestamp — the audit trail is permanent and cannot be edited or deleted
- **NFR17:** Hard deletion of clinical records is restricted — superuser authority and business rule validation are required; records with active clinical dependencies cannot be deleted
