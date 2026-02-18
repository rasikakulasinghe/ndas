---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
inputDocuments:
  - 'docs/index.md'
  - 'docs/architecture.md'
  - 'docs/technology-stack.md'
  - 'docs/api-contracts.md'
  - 'docs/data-models.md'
  - 'docs/source-tree-analysis.md'
documentCounts:
  briefCount: 0
  researchCount: 0
  brainstormingCount: 0
  projectDocsCount: 6
workflowType: 'prd'
lastStep: 11
completedDate: "2026-02-18"
workflowStatus: "complete"
---

# Product Requirements Document - NDAS

**Author:** rasikakulasinghe
**Date:** 2025-12-29

## Executive Summary

NDAS currently serves as a comprehensive neurodevelopmental assessment management system with strong capabilities in patient record management, video-based assessments (GMA, HINE, CDIC, DA, GPA), and basic reporting. This PRD defines enhancements that transform NDAS from a **record-keeping system** into an **intelligent clinical decision support platform**.

**Vision:** Enable clinicians to identify at-risk patients earlier, track developmental trajectories with confidence, and make evidence-based intervention decisions through predictive analytics - all while maintaining the system's robust security and medical data compliance.

**Target Users:**
- **Clinicians** - Need rapid access to predictive insights and outcome trends for individual patients during clinical consultations
- **Researchers** - Require cohort analysis, longitudinal tracking, and statistical comparisons for clinical studies
- **Administrators** - Need operational metrics, outcome tracking, and performance dashboards

**Core Enhancements:**

1. **Predictive Analytics Engine**
   - Patient outcome trend analysis using historical assessment data
   - Longitudinal tracking with developmental trajectory predictions
   - Statistical comparisons against age-matched cohorts
   - Early warning indicators for at-risk patients

2. **Enhanced Multi-Format Reporting**
   - Interactive dashboards with visualizations (individual patient & cohort views)
   - Enhanced PDF/Excel reports with analytical insights
   - Role-specific report templates (clinical, research, administrative)

3. **UI Consistency & Experience Refinement**
   - Unified form layouts aligned with AdminLTE design system
   - Consistent button styles and navigation patterns across all 5 apps
   - Improved responsive behavior for various device sizes
   - Cohesive interaction patterns that reduce cognitive load

### What Makes This Special

**The key differentiator is speed-to-insight for clinical decision-making.** Rather than requiring clinicians to manually review historical assessments and calculate trends, the system will surface predictive insights at the point of care. When a clinician views a patient record, they'll immediately see:

- Developmental trajectory with confidence intervals
- Risk indicators based on assessment patterns
- Comparison to similar patient cohorts
- Recommended follow-up actions based on predictive models

This transforms clinical workflows from reactive (recording what happened) to proactive (predicting what might happen and guiding interventions). For researchers, it enables discovery of patterns across hundreds of patients that would be impossible to detect manually. For administrators, it provides visibility into clinical outcomes and operational effectiveness.

## Project Classification

**Technical Type:** Web Application (Django MVT Monolith)
**Domain:** Healthcare (Neurodevelopmental Assessments)
**Complexity:** High
**Project Context:** Brownfield - extending existing system

**Existing Architecture:**
- Django 4.2.16 on Python 3.x with PostgreSQL/SQLite
- 5 Django apps: patients, users, video, reports, problemlist
- 21 database models with comprehensive relationships
- 150+ API endpoints with rate limiting and security
- AdminLTE 3.2 + Bootstrap 4.6 frontend
- 14-layer security middleware stack with CSP, audit logging

**New Additions Will:**
- Leverage existing models (Patient, GMAssessment, CDIC, HINE, DA, GPA) for analytics
- Extend reports app with analytics engine and visualization capabilities
- Apply consistent design patterns across all templates and views
- Maintain existing security, compliance, and audit requirements
- Integrate seamlessly with current Django MVT architecture

**Domain Complexity Considerations:**
- Medical data requires careful handling (HIPAA/PHI considerations)
- Predictive models must be clinically validated
- Analytics must respect patient privacy and data anonymization
- UI improvements must maintain accessibility standards
- All changes must preserve comprehensive audit logging

## Success Criteria

### User Success

**Clinicians (Primary User)**
- Predictive risk indicators visible within 3 seconds of opening a patient record
- Clinicians can identify at-risk patients without manually reviewing historical assessments — risk flags surfaced automatically
- Developmental trajectory and confidence intervals displayed at-a-glance on the patient detail page
- At least 80% of clinicians rate the analytics as "useful" or "very useful" in post-launch feedback
- Cohort comparison available in ≤2 clicks from any patient view

**Researchers**
- Cohort filtering and export completed in under 60 seconds for datasets up to 500 patients
- Longitudinal tracking queries return results without manual data aggregation or spreadsheet exports
- Anonymized cohort export preserves all assessment fields needed for statistical analysis

**Administrators**
- Operational dashboard loads in under 2 seconds
- Outcome metrics (assessment completion rates, follow-up compliance, at-risk patient counts) visible without running manual reports

### Business Success

**3-Month Targets (Post-Launch)**
- Predictive Analytics Engine live and integrated with existing GMA, HINE, CDIC, DA, and GPA assessment data
- Enhanced PDF/Excel reports deployed with analytical insights embedded
- All 5 Django apps (patients, users, video, reports, problemlist) show consistent UI patterns

**12-Month Targets**
- Clinicians are consulting predictive insights in ≥60% of patient consultations where assessment history exists
- Report generation time reduced by 50% vs. manual processes
- Zero regressions to existing security, compliance, or audit logging behaviours introduced by new analytics features

**Adoption**
- All active system users onboarded to analytics features without additional training sessions (self-discoverable UI)

### Technical Success

- Analytics engine queries complete in ≤500ms for individual patient views (using existing Django ORM with select_related/prefetch_related patterns)
- No degradation to existing 14-layer security middleware stack or CSP policy
- All new views follow mandatory patterns: TimeStampedModel inheritance, rate limiting, login_required, get_object_or_404
- Patient data anonymization preserved in all analytics exports
- Full audit logging (UserActivityLog) for all analytics data access events
- Test coverage ≥80% for new analytics utilities and views
- System handles 10,000-patient datasets without timeout on list/dashboard views (PostgreSQL production target)

### Measurable Outcomes

| Metric | Baseline | Target |
|--------|----------|--------|
| Time to identify at-risk patient | Manual review (minutes) | Automatic flag (seconds) |
| Report generation time | Manual export | 50% reduction |
| Clinician dashboard load time | N/A (new) | ≤2 seconds |
| Analytics query time (per patient) | N/A (new) | ≤500ms |
| UI consistency across apps | Inconsistent | 100% AdminLTE 3.2 aligned |

## Product Scope

### MVP - Minimum Viable Product

- **Predictive Analytics Engine** (core): Trend analysis using existing GMAssessment, HINEAssessment, CDICRecord, DevelopmentalAssessment, and GeneralPaediatricAssessment data
- **Early warning indicators**: Risk flags on patient detail page based on assessment pattern analysis
- **Enhanced PDF reports**: Analytical insights embedded in existing assessment-specific PDFs (GM, HINE, DA, CDIC, GPA)
- **UI consistency pass**: Unified form layouts and button styles across all 5 apps aligned to AdminLTE 3.2

### Growth Features (Post-MVP)

- **Interactive dashboards**: Chart-based visualisations (individual patient & cohort views) with filtering
- **Longitudinal trajectory views**: Developmental trajectory with confidence intervals displayed graphically
- **Role-specific report templates**: Separate clinical, research, and administrative report formats
- **Cohort comparison**: Statistical comparisons against age-matched cohorts
- **Enhanced Excel exports**: Multi-sheet analytics reports with anonymization options

### Vision (Future)

- **Recommended follow-up actions**: System-suggested interventions based on predictive model outputs
- **Automated at-risk alerts**: Notification system when new assessment data triggers risk thresholds
- **Research-grade analytics**: Integration with external statistical tools or REST API for data science workflows
- **Multi-site deployment**: Analytics aggregated across multiple clinical sites (horizontal scaling path)

## User Journeys

### Journey 1: Dr. Amara Silva — The Clinician Racing Against Time

Dr. Amara Silva is a paediatric neurologist at a busy regional hospital. She sees 20 patients a day, and her biggest frustration is the gap between what the data says and what she can act on in time. Before the NDAS enhancements, she would open a patient record, then spend 8-12 minutes manually scrolling through past GMA, HINE, and CDIC assessments, scribbling trends on a notepad before forming a clinical impression. By appointment 10, she's tired and worried she might be missing a subtle pattern in a patient she saw six months ago.

One Tuesday morning she opens the record for 8-month-old Kavindu — a premature baby with borderline HINE scores across three visits. Instead of the blank patient header she's used to, a risk indicator banner greets her: **"Developmental trajectory: Moderate concern — HINE scores declining across 3 assessments. Cohort comparison: lower 20th percentile for corrected age."** The predictive panel shows a simple trajectory chart with a confidence band. She immediately knows this child needs an urgent follow-up referral.

The consultation that would have taken 20 minutes of mental arithmetic takes 4. Amara documents her decision, the system logs it automatically, and she moves to the next patient feeling confident rather than uncertain. Six months later, Kavindu has been referred and enrolled in early intervention — two months earlier than he would have been under the old system.

**This journey reveals requirements for:**
- Patient detail page analytics panel (risk flags, trajectory chart, cohort percentile)
- Automated risk classification based on multi-assessment trend analysis
- GMA, HINE, CDIC, DA, GPA data aggregation for the analytics engine
- Sub-3-second page load for analytics panel on patient view

---

### Journey 2: Dr. Amara Silva — Incomplete Data, No Clear Picture

Three weeks later, Dr. Amara opens a record for a new referral — 14-month-old Dilshan, transferred from another clinic with only one HINE assessment on file. The risk panel displays: **"Insufficient assessment history for trend analysis — 1 assessment recorded. Add a second assessment to enable trajectory tracking."** Rather than a confusing blank state or a misleading chart, she sees a clear, actionable message.

She completes a HINE and CDIC assessment during the visit, saves them, and the analytics panel immediately refreshes with an initial baseline. No trajectory yet (two data points needed), but the system flags the HINE raw score as below the 30th percentile for corrected age. Amara schedules a follow-up in 8 weeks. The system's behaviour in this edge case is trustworthy — it never fabricates confidence when data is sparse.

**This journey reveals requirements for:**
- Graceful degradation when assessment history is insufficient (minimum 2 data points for trend)
- Clear empty-state messaging with actionable guidance
- Real-time analytics panel refresh after new assessment is saved (no page reload)
- Cohort percentile display even for single-assessment patients (snapshot, not trend)

---

### Journey 3: Dr. Nimal Chen — The Researcher Chasing a Pattern

Dr. Nimal Chen is a clinical researcher studying outcomes for extremely premature infants (born at <28 weeks POG). He has a hypothesis: infants with APGAR scores below 5 at 1 minute have significantly different HINE trajectories at 12 months corrected age compared to those with scores of 6-10. Testing this manually across NDAS would take weeks of export-and-spreadsheet work.

He opens the enhanced report builder. He selects: **Cohort filter** → POG ≤ 28 weeks → APGAR 1-min < 5. He adds a second cohort: APGAR 1-min ≥ 6. He selects **HINE total score** and **corrected age months** as his longitudinal variables. He checks **Anonymize patient identifiers** and clicks **Generate Cohort Report**.

Forty-five seconds later, a multi-sheet Excel file downloads. Sheet 1: patient-level anonymised data. Sheet 2: cohort summary statistics. Sheet 3: longitudinal HINE means by corrected age month. Dr. Chen pastes the cohort means into his statistical software and within an hour has his preliminary findings — a statistically significant difference he can now pursue in a formal study.

**This journey reveals requirements for:**
- Multi-variable cohort filtering (POG, APGAR, diagnosis, assessment scores)
- Longitudinal data export with corrected-age normalisation
- Anonymization toggle in the report builder (remove BHT, NNC, baby name, mother name)
- Multi-sheet Excel export (patient data, cohort summary, longitudinal aggregates)
- Report generation time ≤60 seconds for 500-patient cohorts

---

### Journey 4: Admin Ruwani — Keeping the Clinical Operation Honest

Ruwani is the clinical operations manager responsible for NDAS across three consultants. Each month she manually compiles a report for hospital administration: how many assessments completed, how many patients followed up within recommended windows, how many at-risk patients were referred. It takes her half a day of copy-pasting from individual patient records.

After the enhancements go live, Ruwani opens the new **Administration Dashboard**. She sees at a glance: 47 active patients, 12 flagged as moderate-to-high risk, 89% follow-up compliance rate this quarter, and 6 overdue referrals. She drills into the overdue referrals list, sees the patient IDs and responsible clinician, and sends a reminder in seconds. Her monthly report now takes 15 minutes instead of 4 hours — she exports the dashboard summary directly to Excel and pastes it into the hospital reporting template.

**This journey reveals requirements for:**
- Administrative dashboard with operational KPIs (patient counts, risk distribution, follow-up compliance)
- Overdue referral/follow-up list with drill-down to patient level
- One-click export of dashboard summary data to Excel
- Role-based access: admins see operational metrics; clinicians see clinical analytics
- Dashboard data refresh: near real-time (within 5 minutes of assessment updates)

### Journey Requirements Summary

| Journey | User Type | Key Capabilities Required |
|---------|-----------|--------------------------|
| Dr. Amara — Success Path | Clinician | Risk panel, trajectory chart, cohort percentile, sub-3s load |
| Dr. Amara — Edge Case | Clinician | Graceful degradation, empty states, real-time panel refresh |
| Dr. Nimal — Researcher | Researcher | Cohort filtering, longitudinal export, anonymization, multi-sheet Excel |
| Ruwani — Admin | Administrator | Ops dashboard, KPIs, overdue lists, role-based access, export |

## Domain-Specific Requirements

### Healthcare Compliance & Regulatory Overview

NDAS operates in a clinical healthcare setting managing Protected Health Information (PHI) for paediatric neurodevelopmental assessments. The planned enhancements — particularly the Predictive Analytics Engine and clinical risk indicators — introduce Clinical Decision Support Software (CDSS) capabilities that carry specific regulatory, validation, and liability considerations.

While NDAS operates in a non-US jurisdiction (Sri Lanka context), equivalent data protection, clinical validation, and patient safety obligations apply regardless of geography. All analytics features must be designed with these constraints as first-class requirements, not afterthoughts.

### Key Domain Concerns

**1. Clinical Decision Support Classification**
The predictive risk flags and trajectory analytics qualify as passive CDSS — they present information to clinicians who make the final decision. This classification is important: NDAS must NOT autonomously make clinical decisions or replace clinician judgment. All risk indicators must be clearly labelled as decision-support tools, not diagnoses. The system surfaces data; the clinician acts on it.

**2. Clinical Validation of Predictive Models**
Any trend analysis, risk classification, or cohort percentile calculation must be grounded in clinically accepted methodologies. Predictive models must be:
- Based on validated assessment instruments (GMA, HINE, CDIC, DA, GPA norms)
- Validated against known clinical outcomes before production deployment
- Transparent about their methodology (no "black box" risk scores)
- Reviewed by a clinical expert before release

**3. Patient Safety — No False Confidence**
The greatest patient safety risk is the system generating misleading predictions from insufficient data. Requirements:
- Minimum data thresholds enforced before any trend/risk output is displayed
- Confidence levels displayed alongside all predictions
- Clear "insufficient data" states that prevent incomplete analytics from appearing as conclusive findings
- Risk flags must never suppress a clinician's own clinical assessment

**4. Data Privacy & PHI Handling**
All existing PHI handling obligations are extended to analytics:
- Analytics computations must never expose one patient's data in another patient's view
- Cohort analytics must enforce anonymization before any export
- Audit logging (UserActivityLog) must cover all analytics data access events
- Aggregate statistics must be suppressed if cohort size is too small (< 5 patients) to prevent re-identification

**5. Liability & Clinical Disclaimer**
Risk indicators and trajectory predictions must be accompanied by appropriate clinical disclaimers. The system is a tool to assist clinical judgment — it does not replace it. Liability implications require:
- Clear UI labelling: "Clinical Decision Support — Not a Diagnosis"
- Documentation of the methodology behind each prediction type
- Audit trail of when/how risk flags were viewed and acted upon
- Version tracking of the analytics algorithms deployed

### Compliance Requirements

| Requirement | Applies To | Implementation |
|-------------|-----------|----------------|
| PHI data isolation | All analytics queries | Patient data never cross-exposed in analytics |
| Anonymization on export | Cohort reports | BHT, NNC, baby_name, mother_name masked |
| Audit logging | All analytics views | UserActivityLog entries for every access |
| Small cohort suppression | Cohort statistics | Suppress counts/stats if N < 5 |
| CDSS disclaimer | All risk/prediction UI | Visible label on every analytics panel |
| Assessment instrument validity | Predictive models | Only use validated scoring norms |
| Session security | Analytics access | Existing 1-hour session timeout preserved |
| Encryption in transit | All data | Existing HTTPS/TLS requirement maintained |

### Clinical Requirements

**Assessment Instrument Norms**
All cohort percentile calculations must use published, peer-reviewed norms for each assessment type:
- **GMA**: Prechtl's General Movement Assessment classification norms
- **HINE**: Hammersmith Infant Neurological Examination age-specific score distributions
- **CDIC**: Child Development Inventory age-referenced milestone norms
- **DA/GPA**: Age-appropriate developmental milestone references

The source and version of each norm set must be documented in the system and visible to users reviewing analytics outputs.

**Corrected Age vs. Chronological Age**
All analytics for preterm infants must use **corrected age** (not chronological age) for percentile calculations and cohort comparisons. The existing `pog_wks` and `pog_days` fields on the Patient model provide the data needed for this calculation. This is a clinical correctness requirement, not optional.

**Minimum Assessment History for Trends**
- Trend analysis: minimum 2 assessments of the same type
- Trajectory prediction: minimum 3 assessments recommended (flagged if only 2)
- Single-assessment patients: percentile snapshot only, no trend line

### Regulatory Pathway

NDAS is an internal clinical tool (not a commercially distributed medical device), which significantly reduces regulatory burden. However, if the system is ever deployed across multiple hospitals or offered as a service:

- **Internal deployment**: Clinical validation by the hospital's clinical team is sufficient; institutional ethics committee review recommended for the predictive analytics module
- **Multi-site / commercial deployment**: Formal medical device software registration under the national medical device regulatory authority would be required before deployment

For the current scope, the validation pathway is:
1. Analytics algorithm review by supervising clinician(s)
2. Shadow-mode testing: run predictions alongside current clinical practice for 3 months without surfacing results to clinicians
3. Accuracy review: compare predictions against actual clinical outcomes
4. Clinical sign-off before production go-live of risk indicators

### Validation Methodology

**Predictive Model Validation Plan**
- **Retrospective validation**: Run analytics against historical NDAS data (existing assessments) and compare predicted risk classifications against documented clinical outcomes
- **Prospective shadow testing**: 3-month period where analytics run silently and results are reviewed by clinicians without influencing their decisions
- **Accuracy threshold**: Risk classification must achieve ≥80% agreement with clinician retrospective assessment before go-live
- **Ongoing monitoring**: Monthly review of flag accuracy rate post-launch; automatic flag if accuracy drops below threshold

### Safety Measures

- **No autonomous decisions**: System surfaces data only; all clinical decisions remain with the clinician
- **Graceful degradation**: When data is insufficient, system shows "no prediction" state — never an uninformed guess
- **Algorithm transparency**: Methodology documentation accessible from within every analytics panel ("How is this calculated?" link)
- **Clinical override**: Clinicians can dismiss or annotate risk flags; dismissals are audit-logged
- **Version control on algorithms**: Any change to prediction methodology triggers a new version tag; historical assessments retain the version that generated their risk flag

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. Passive CDSS via Multi-Stream Assessment Analytics**
The most significant innovation in NDAS is the aggregation of five independent assessment data streams (GMA, HINE, CDIC, DA, GPA) into a unified predictive analytics layer. Most clinical record systems store assessments in silos — a clinician must open each assessment type separately to piece together a developmental picture. NDAS will be the first system in this workflow to surface a unified risk view synthesised across all assessment types at the point of care, without additional clinician effort.

**2. Corrected-Age Normalised Cohort Benchmarking for Preterm Infants**
Standard paediatric analytics tools use chronological age for cohort comparisons. NDAS's cohort engine will use **corrected age** derived from the existing `pog_wks` / `pog_days` fields, making comparisons clinically meaningful for the predominantly preterm population that NDAS serves. This is a domain-specific innovation that general analytics platforms cannot provide out-of-the-box.

**3. Temporal Risk Trajectory from Sparse Clinical Data**
Unlike high-frequency monitoring systems (ICU telemetry, wearables), NDAS assessments are sparse — a patient may have 3-6 assessments over 18 months. Generating meaningful trend signals from sparse, irregularly-spaced clinical data is a genuine technical and statistical challenge. The innovation is in producing clinically trustworthy risk signals from limited data points while being transparent about confidence levels and data sufficiency.

**4. Brownfield Analytics Integration Without Architectural Disruption**
The analytics engine must integrate seamlessly into an existing 14-layer security middleware stack, Django MVT monolith, and AdminLTE UI — without compromising security posture, performance, or existing functionality. This is an architectural innovation challenge: adding a CDSS capability to a system not originally designed for analytics, while maintaining zero regressions.

### Market Context & Competitive Landscape

Existing clinical analytics platforms (e.g., Tableau Healthcare, Power BI for healthcare) require separate deployments, data exports, and licencing. They are not embedded in the clinical workflow — a clinician must leave their patient record system, open a separate tool, and manually query data.

NDAS's innovation is **embedded point-of-care analytics** — the insight surfaces in the same view where the clinician is already working, with no workflow interruption. For resource-constrained clinical settings (which are the primary deployment context for NDAS), this is a meaningful competitive advantage over enterprise analytics tools.

For neurodevelopmental assessment specifically, no widely available system offers corrected-age cohort benchmarking with multi-assessment trend synthesis in an integrated record-keeping platform. NDAS would be differentiated in this niche.

### Validation Approach

**Analytics Innovation Validation:**
- **Retrospective accuracy test**: Apply the risk classification algorithm to historical data; compare flagged patients against those who received clinical intervention (ground truth)
- **Clinician agreement study**: Present anonymised risk flag outputs to 3-5 clinicians independently; measure inter-rater agreement with the system's classifications
- **Sparse data stress test**: Test prediction quality with 2, 3, 4, and 5+ assessment data points; validate that confidence labelling correctly reflects uncertainty at lower data counts
- **Corrected-age validation**: Verify percentile outputs against published HINE and CDIC norms for corrected-age cohorts; spot-check against known clinical cases

**UI Innovation Validation:**
- **Time-to-insight benchmark**: Measure clinician time to form an initial risk impression with vs. without the analytics panel (target: 3× faster)
- **Usability test**: 5-user think-aloud protocol with the analytics panel before full deployment; iterate on layout and labelling

### Risk Mitigation

| Innovation Risk | Likelihood | Impact | Mitigation |
|----------------|-----------|--------|------------|
| Predictive model produces inaccurate risk flags | Medium | High | 3-month shadow testing; clinician sign-off before go-live |
| Sparse data yields misleading confidence | Medium | High | Enforce minimum data thresholds; explicit uncertainty labels |
| Performance degradation from analytics queries | Low | Medium | Query optimisation with select_related; caching for cohort aggregates |
| Clinician over-reliance on system flags | Low | High | CDSS disclaimer; "How calculated?" transparency links; training |
| Corrected-age calculation errors for edge cases | Low | Medium | Unit tests covering boundary POG values; clinical QA review |
| UI analytics panel adds cognitive load | Low | Medium | Collapsible panel; progressive disclosure; usability testing |

## Web Application Specific Requirements

### Project-Type Overview

NDAS is a **Multi-Page Application (MPA)** using Django's server-side rendering with selective HTMX-powered dynamic interactions. This architecture is maintained for the enhancements — no migration to a SPA framework. The analytics and reporting additions follow the existing MVT pattern: server-rendered HTML pages with targeted HTMX partials for real-time panel updates.

The application is deployed as an **authenticated internal clinical tool** — all pages require login, SEO is not applicable, and the primary access device is a hospital desktop or workstation. Mobile access is secondary.

### Browser Matrix

| Browser | Version | Support Level | Notes |
|---------|---------|--------------|-------|
| Google Chrome | Latest -1 | Full | Primary clinical workstation browser |
| Microsoft Edge | Latest -1 | Full | Common in hospital Windows environments |
| Mozilla Firefox | Latest -1 | Full | Secondary support |
| Safari | Latest -1 | Partial | macOS/iPad access; VideoJS compatibility verified |
| Internet Explorer | Any | None | Not supported — AdminLTE 3.2 requires modern browsers |

**Mobile Browsers:** Functional but not optimised. AdminLTE 3.2 provides basic responsive behaviour. Mobile access is not a primary use case for clinical workflows but must not break on tablet (iPad, Android tablet) screen sizes.

### Responsive Design

**Primary viewport target:** 1280×800 (standard hospital workstation monitor)
**Secondary viewport target:** 1920×1080 (higher-resolution clinic monitors)
**Tablet viewport:** 768×1024 (iPad — occasional clinician use)

**Design approach:** AdminLTE 3.2 Bootstrap 4.6 responsive grid — no custom breakpoint changes permitted. The analytics panel on the patient detail page must stack vertically on tablet widths (≤768px) without horizontal overflow. The cohort report builder must remain usable at 1024px wide minimum.

**Print layout:** Existing print-optimised templates (`templates/print/`) maintained. PDF reports generated server-side (ReportLab/WeasyPrint) — not dependent on browser print CSS.

### Performance Targets

| Page / Action | Target | Constraint |
|--------------|--------|-----------|
| Patient detail page (with analytics panel) | ≤3 seconds | Includes analytics query |
| Analytics panel HTMX refresh (post-assessment save) | ≤1.5 seconds | Partial page update only |
| Patient list / dashboard | ≤2 seconds | select_related() required |
| Cohort report generation (≤500 patients) | ≤60 seconds | Background-tolerant (progress indicator) |
| PDF download (single assessment) | ≤5 seconds | Existing WeasyPrint pipeline |
| Excel export (cohort, anonymised) | ≤60 seconds | openpyxl generation |
| Admin operational dashboard | ≤2 seconds | Aggregated queries; consider caching |

**Database:** Performance targets assume PostgreSQL in production. SQLite in development may be slower for analytics queries — this is acceptable.

**Caching strategy for analytics:**
- Per-patient analytics results: cache with 5-minute TTL, invalidated on new assessment save for that patient
- Cohort percentile norms: cache indefinitely (static reference data), cleared only on norm version update
- Admin dashboard aggregates: cache with 5-minute TTL, refreshed on schedule

**Query optimisation requirements:**
- All analytics queries must use `select_related()` / `prefetch_related()`
- No N+1 queries permitted in analytics views
- Cohort queries must use database-level aggregation (`annotate()`, `aggregate()`) rather than Python-level loops

### SEO Strategy

**Not applicable.** NDAS is a fully authenticated internal clinical application. All pages require login (`@login_required`). No public-facing pages exist except the login page. Search engine indexing of clinical data would be a security concern.

`robots.txt` must disallow all crawling (`Disallow: /`).

### Accessibility Level

**Target:** WCAG 2.1 Level AA

| Requirement | Implementation |
|-------------|---------------|
| Analytics panel keyboard navigable | Tab order through risk flags, chart, cohort data |
| Risk flag colour not sole indicator | Icon + colour + text label (never colour-only) |
| Chart data available as table | Analytics charts accompanied by data table for screen readers |
| Form labels on all filter inputs | Report builder cohort filters must have explicit `<label>` elements |
| Error messages programmatically associated | `aria-describedby` on invalid filter inputs |
| Focus management after HTMX updates | Re-focus to updated analytics panel after partial page refresh |

### Implementation Considerations

**HTMX integration for analytics panel:**
- The patient detail page analytics panel renders server-side on page load
- After a new assessment is saved, an HTMX `hx-trigger` fires to refresh the analytics panel partial — no full page reload
- HTMX partial endpoint: `GET /patient/analytics/<pk>/` returns the analytics panel HTML fragment
- CSP compliance: all HTMX interactions must use nonce-based requests; no inline event handlers

**Static assets for analytics visualisations:**
- Chart library (e.g., Chart.js) loaded via CDN with CSP-approved domain or served from `static/plugins/`
- Charts rendered as `<canvas>` elements with accompanying `<table>` data for accessibility
- No external data calls from client-side — all data served via Django views

**Template structure for analytics:**
- Analytics panel: `templates/patients/partials/analytics_panel.html`
- Risk flag component: `templates/patients/partials/risk_flag.html`
- Admin dashboard: `templates/users/admin_dashboard.html`
- Cohort report builder: extends existing `templates/reports/` structure

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-Solving MVP — solve the core clinical insight lag problem with a focused, reliable feature set before adding visualisation and research tools.

**Rationale:** The 3-month shadow testing requirement (from domain requirements) means the analytics engine must be built and validated *before* risk flags are surfaced to clinicians. This creates a natural phasing: build the engine first (Phase 1a), run shadow validation, then activate the clinical-facing UI (Phase 1b).

**Resource Requirements:** 1-2 backend developers, 1 clinician reviewer for validation sign-off. No new infrastructure required — existing Django/PostgreSQL stack is sufficient for MVP analytics workloads.

### Phase 1a: Analytics Engine (Shadow Mode)

**Goal:** Build and validate the analytics computation layer — invisible to clinicians until validated.

**Must-Have Capabilities:**
- Analytics computation module (`reports/utils/analytics_engine.py`):
  - Trend calculation from GMAssessment, HINEAssessment, CDICRecord, DevelopmentalAssessment, GeneralPaediatricAssessment data
  - Corrected-age calculation using `pog_wks` / `pog_days`
  - Risk classification: Low / Moderate / High based on score trajectory
  - Cohort percentile lookup against built-in norm tables (HINE, CDIC)
  - Minimum data threshold enforcement (≥2 assessments for trend)
- Shadow mode flag: analytics computed and logged but NOT displayed
- Retrospective validation tooling: compare risk classifications against historical outcomes for clinician review
- Unit tests ≥80% coverage on all analytics utilities

**User journeys supported:** None visible yet — internal validation only

**Success gate:** Clinician sign-off on ≥80% agreement with retrospective classifications before Phase 1b activation

### Phase 1b: Clinical-Facing Analytics MVP

**Goal:** Surface validated analytics to clinicians at point of care.

**Must-Have Capabilities:**

- **Patient detail page analytics panel** (HTMX partial):
  - Risk flag banner (Low / Moderate / High) with icon + colour + text label
  - Corrected-age cohort percentile display (single number + percentile band)
  - Trend summary: "Score improving / stable / declining across N assessments"
  - "Insufficient data" graceful state (< 2 assessments)
  - "How is this calculated?" transparency link
  - CDSS disclaimer label on every panel
  - Dismissal/annotation capability (audit-logged)
- **Analytics HTMX endpoint:** `GET /patient/analytics/<pk>/`
- **Enhanced PDF reports:** Analytical summary section embedded in existing GM, HINE, DA, CDIC, GPA assessment PDFs
- **Algorithm version tracking:** Version tag stored with each risk classification
- **Audit logging:** All analytics panel views logged to UserActivityLog

**UI Consistency Pass (bundled with Phase 1b):**
- Unified form layouts across all 5 apps aligned to AdminLTE 3.2 standards
- Consistent button styles, spacing, and navigation patterns

**User journeys supported:**
- Journey 1: Dr. Amara — Success Path ✓
- Journey 2: Dr. Amara — Edge Case (incomplete data) ✓

### Phase 2: Research & Reporting Tools (Post-MVP)

**Goal:** Enable researcher cohort analysis and enhanced data export.

**Planned Capabilities:**
- **Cohort report builder** enhancements:
  - Multi-variable cohort filtering (POG, APGAR, diagnosis, assessment scores)
  - Longitudinal data export with corrected-age normalisation
  - Anonymization toggle (BHT, NNC, baby_name, mother_name masked)
  - Multi-sheet Excel export (patient data, cohort summary, longitudinal aggregates)
  - Small cohort suppression (N < 5)
- **Interactive trajectory charts:** Chart.js visualisation with confidence band and accessible data table
- **Administrative operational dashboard:**
  - Patient counts, risk distribution, follow-up compliance KPIs
  - Overdue referral/follow-up list with drill-down
  - One-click Excel export of dashboard summary
  - Role-based access (admin vs. clinician views)

**User journeys supported:**
- Journey 3: Dr. Nimal — Researcher ✓
- Journey 4: Ruwani — Admin ✓

### Phase 3: Expansion (Future Vision)

**Planned Capabilities:**
- Automated at-risk alerts (notification system when new assessment triggers risk threshold)
- System-suggested follow-up actions based on predictive model outputs
- REST API endpoints for external research tool integration
- Multi-site deployment with cross-site aggregate analytics
- Role-specific PDF/report templates (clinical, research, administrative)

### Risk Mitigation Strategy

| Risk Area | Risk | Mitigation |
|-----------|------|------------|
| Technical | Analytics queries degrade page performance | Caching layer (5-min TTL); query profiling before Phase 1b go-live |
| Technical | Corrected-age edge cases (extreme prematurity) | Boundary unit tests; clinical QA review of norm table coverage |
| Clinical | Shadow testing reveals poor model accuracy | Extend shadow period; revise risk thresholds with clinician input |
| Clinical | Clinicians over-rely on risk flags | CDSS disclaimer; mandatory "How calculated?" link; training session |
| Resource | Small team, large scope | Strict phase gating — Phase 1b does not start until 1a is validated |
| Resource | Brownfield regressions | Existing test suite must pass before any phase deployment |

### Out of Scope (All Phases)

- WebSocket real-time notifications (HTMX polling acceptable)
- Mobile-native app
- External EHR/EMR system integration
- Natural language query interface
- Machine learning model training (analytics use statistical rules, not ML)
- Multi-language UI (English only)

## Functional Requirements

> **Capability Contract:** Every feature built must trace to one of these requirements. Capabilities not listed here will not exist in the final product.

### Clinical Analytics Engine

- **FR1:** The system can compute a risk classification (Low / Moderate / High) for a patient based on score trends across their assessment history
- **FR2:** The system can calculate corrected age from a patient's gestational age (pog_wks / pog_days) and date of birth for use in all analytics computations
- **FR3:** The system can aggregate assessment data across all five assessment types (GMA, HINE, CDIC, DA, GPA) for a single patient into a unified analytics result
- **FR4:** The system can determine a patient's percentile ranking within a corrected-age cohort for each assessment type using built-in clinical norm tables
- **FR5:** The system can detect whether a patient's assessment scores are trending improving, stable, or declining across sequential assessments
- **FR6:** The system can enforce minimum data thresholds before producing any trend or risk output (minimum 2 assessments of the same type required)
- **FR7:** The system can operate in shadow mode where analytics are computed and logged internally but not displayed to any user
- **FR8:** Administrators can access a retrospective validation report comparing the analytics engine's risk classifications against historical patient outcomes
- **FR9:** The system can attach a version identifier to each risk classification result, tracking which algorithm version produced it

### Patient Analytics Display

- **FR10:** Clinicians can view a summary analytics panel on the patient detail page showing the current risk classification, trend direction, and corrected-age cohort percentile
- **FR11:** Clinicians can view a "no prediction available" state with an actionable explanation when a patient has insufficient assessment history for trend analysis
- **FR12:** Clinicians can trigger a refresh of the patient analytics panel after saving a new assessment without reloading the full page
- **FR13:** Clinicians can view a trajectory chart showing a patient's assessment scores plotted over corrected age with a confidence band (Phase 2)
- **FR14:** Clinicians can dismiss or annotate a risk flag on a patient record, with the dismissal recorded in the audit log
- **FR15:** Clinicians can access a methodology explanation for any risk classification displayed on their patient record

### Report Generation & Export

- **FR16:** Clinicians can download an enhanced PDF report for any assessment (GM, HINE, DA, CDIC, GPA) that includes an analytical summary section alongside existing clinical data
- **FR17:** Users can generate a multi-sheet Excel export containing patient data, cohort summary statistics, and longitudinal assessment aggregates
- **FR18:** Users can toggle anonymization when generating an Excel export, causing all patient identifiers (BHT, NNC, baby name, mother name) to be replaced with anonymous references
- **FR19:** The system can suppress cohort statistics in any export when the cohort contains fewer than 5 patients to prevent re-identification
- **FR20:** Administrators can export an operational dashboard summary to Excel with a single action

### Research & Cohort Analysis

- **FR21:** Researchers can filter patients into a cohort using combinations of clinical variables including gestational age, APGAR scores, diagnosis, and assessment score ranges
- **FR22:** Researchers can define and compare two distinct patient cohorts side-by-side in the report builder
- **FR23:** Researchers can select longitudinal assessment variables (assessment score + corrected age month) for inclusion in a cohort export
- **FR24:** Researchers can retrieve cohort export results with corrected-age normalisation applied to all longitudinal data points
- **FR25:** Researchers can view aggregate statistics (mean, count, distribution) for their defined cohort before generating a full export

### Administrative Dashboard & Operations

- **FR26:** Administrators can view an operational dashboard showing total active patient count, risk distribution (Low / Moderate / High counts), and follow-up compliance rate
- **FR27:** Administrators can view a list of patients with overdue follow-up assessments, filtered by responsible clinician
- **FR28:** Administrators can drill down from the operational dashboard to individual patient records
- **FR29:** The system can present role-appropriate views: clinicians see clinical analytics panels; administrators see operational metrics dashboards
- **FR30:** The system can refresh administrative dashboard aggregates within 5 minutes of new assessment data being saved

### Clinical Safety & Compliance

- **FR31:** The system can display a Clinical Decision Support disclaimer on every analytics output visible to clinical users
- **FR32:** The system can log every analytics panel view event to the audit trail (UserActivityLog), including the user, patient, timestamp, and algorithm version shown
- **FR33:** The system can log every risk flag dismissal or annotation event to the audit trail with full context
- **FR34:** The system can display confidence level or data sufficiency indicators alongside every trend or risk prediction shown to users
- **FR35:** Administrators can view the algorithm version history for a patient's risk classifications, showing which version produced each result

### UI Consistency & Accessibility

- **FR36:** All five application areas (patients, users, video, reports, problemlist) can present form layouts, button styles, and navigation patterns consistent with the AdminLTE 3.2 design system
- **FR37:** All analytics risk flag indicators can convey their status through a combination of icon, colour, and text label (never colour alone)
- **FR38:** All analytics charts can present their underlying data as an accessible data table alongside the visual chart
- **FR39:** All new form controls in the cohort report builder can be operated using keyboard navigation alone
- **FR40:** The system can maintain WCAG 2.1 Level AA compliance across all new analytics and reporting interfaces

## Non-Functional Requirements

### Performance

- **NFR-P1:** The patient detail page including the analytics panel must load within 3 seconds for any patient with up to 50 assessment records on PostgreSQL in production
- **NFR-P2:** The analytics HTMX partial refresh (triggered after saving a new assessment) must complete within 1.5 seconds
- **NFR-P3:** The patient list and dashboard must load within 2 seconds for lists of up to 500 patients
- **NFR-P4:** Cohort report generation (Excel export) for up to 500 patients must complete within 60 seconds; a progress indicator must be shown for operations exceeding 5 seconds
- **NFR-P5:** The administrative operational dashboard must load within 2 seconds using cached aggregates; cache staleness must not exceed 5 minutes
- **NFR-P6:** Analytics computation results for individual patients must be cached with a 5-minute TTL; cache must be invalidated immediately when a new assessment is saved for that patient
- **NFR-P7:** No analytics view may introduce N+1 database query patterns; all queries must use select_related() or prefetch_related() as appropriate

### Security

- **NFR-S1:** All Protected Health Information (PHI) must be transmitted exclusively over HTTPS/TLS; no plaintext transmission of patient data is permitted at any layer
- **NFR-S2:** All new analytics endpoints must be protected by the existing @login_required decorator; unauthenticated requests must receive a 302 redirect to the login page, never a data response
- **NFR-S3:** All new POST/PUT/DELETE endpoints must enforce CSRF token validation; analytics HTMX requests must include the CSRF token
- **NFR-S4:** All new create and edit analytics operations must be rate-limited at 10 requests per minute per user; all delete operations at 5 per minute
- **NFR-S5:** The existing 14-layer security middleware stack order must not be modified by any analytics or reporting implementation
- **NFR-S6:** The Content Security Policy (CSP) must remain intact for all new pages; any new JavaScript (chart libraries, HTMX extensions) must be loaded via CSP-approved CDN domains or served from static/ with nonce support in production
- **NFR-S7:** All analytics data access events (panel views, report generation, export downloads) must be logged to UserActivityLog with user, patient reference, timestamp, and action type
- **NFR-S8:** Analytics cohort exports must never include one patient's identifiable data in another patient's analytical results; query isolation must be verified by unit tests
- **NFR-S9:** Session timeout of 1 hour must apply equally to all analytics and reporting pages; no analytics session extension mechanisms are permitted
- **NFR-S10:** User input in cohort filter fields must be validated and sanitized using the existing sanitize_text_input() utility before use in any database query

### Scalability

- **NFR-SC1:** The analytics engine must return results within performance targets (NFR-P1 to NFR-P3) for any patient with up to 100 assessment records across all assessment types
- **NFR-SC2:** The cohort report builder must support cohort queries across the full patient dataset (up to 10,000 patients on PostgreSQL) without timeout; queries must use database-level aggregation (annotate/aggregate) rather than Python-level iteration
- **NFR-SC3:** The administrative dashboard aggregation queries must complete within 5 seconds even when the patient dataset reaches 10,000 records; if not achievable via ORM alone, a scheduled cache-warming task is acceptable
- **NFR-SC4:** The analytics module must not consume more than 20% additional database query time on existing non-analytics pages

### Reliability

- **NFR-R1:** The analytics panel on the patient detail page must degrade gracefully if the analytics computation fails — the patient record must still load and display fully; analytics errors must not prevent clinical data access
- **NFR-R2:** Analytics computation failures must be logged to the application error log with full stack trace and patient context; they must not surface raw error details to the clinical user
- **NFR-R3:** Cohort report generation failures must present a user-facing error message with a retry option; partial or corrupt exports must not be offered for download
- **NFR-R4:** All new database migrations must be reversible (down migration provided); no irreversible schema changes permitted without explicit documented justification
- **NFR-R5:** The full existing test suite must pass before any analytics phase is deployed to production; no phase may be released with known test failures

### Maintainability

- **NFR-M1:** All new analytics utility functions must achieve ≥80% unit test coverage; coverage must be verified as part of the standard test run
- **NFR-M2:** All new models must inherit from TimeStampedModel and UserTrackingMixin; no model may define created_at, updated_at, added_by, or last_edit_by fields directly
- **NFR-M3:** All new TextChoices must be added to ndas/custom_codes/choice.py; no inline choice definitions in model fields are permitted
- **NFR-M4:** All new validators must be added to ndas/custom_codes/validators.py; no inline validation logic in model or form field definitions
- **NFR-M5:** Algorithm version identifiers for the analytics engine must be defined as named constants in a dedicated module; hard-coded version strings in view or model code are not permitted
- **NFR-M6:** The analytics engine computation logic must be implemented in the service/utility layer (reports/utils/ or ndas/custom_codes/) and not embedded directly in view functions

### Data Integrity

- **NFR-D1:** Analytics computations must be read-only operations on existing assessment data; no analytics process may modify Patient, GMAssessment, HINEAssessment, CDICRecord, DevelopmentalAssessment, or GeneralPaediatricAssessment records
- **NFR-D2:** Risk classification results stored for audit purposes must be immutable after creation; stored classifications must not be updated retroactively when the algorithm changes (new version creates new record)
- **NFR-D3:** Cohort export files must include a generation timestamp and algorithm version in the file metadata; exports must be reproducible from the same data snapshot
- **NFR-D4:** Anonymized exports must undergo a verification step confirming that no direct patient identifiers (BHT, NNC, baby_name, mother_name, phone_number) are present in any exported row before the download is served

### Accessibility

- **NFR-A1:** All new analytics and reporting interfaces must conform to WCAG 2.1 Level AA as defined by FR40
- **NFR-A2:** No analytics information may be conveyed exclusively through colour; every colour-coded element must have a redundant icon or text label
- **NFR-A3:** All interactive analytics elements (analytics panel, chart controls, report builder filters) must be operable via keyboard without requiring a mouse
- **NFR-A4:** Page focus must be programmatically managed after HTMX partial page updates; focus must return to the updated region to support screen reader users
- **NFR-A5:** All analytics data charts must have an equivalent data table representation accessible to screen readers
