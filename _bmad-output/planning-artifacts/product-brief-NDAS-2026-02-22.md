---
stepsCompleted: [1, 2, 3, 4, 5, 6]
workflowStatus: complete
completedDate: '2026-02-22'
inputDocuments:
  - _bmad-output/brainstorming/brainstorming-session-2026-02-21.md
  - docs/index.md
  - docs/project-overview.md
  - docs/architecture.md
  - docs/data-models-main.md
  - _bmad-output/planning-artifacts/prd.md
date: '2026-02-22'
author: Rasika
---

# Product Brief: NDAS — Multi-Institution Support

<!-- Content will be appended sequentially through collaborative workflow steps -->

## Executive Summary

NDAS currently requires a separate application deployment for every institution —
server setup, database configuration, code deployment, and ongoing maintenance,
all managed by the developer. With a target network of 10+ institutions, this
model is unsustainable. The Multi-Institution expansion transforms NDAS from a
single-tenant application into a true multi-tenant clinical platform: a new
institution can be onboarded in minutes by a superadmin, not days by a developer.
It brings two capabilities the current model cannot offer — centralised
cross-institution analytics and structured clinical referrals — while keeping
each institution's data completely isolated.

---

## Core Vision

### Problem Statement

Every new hospital or clinic that joins NDAS requires a full, independent
application deployment — managed by the developer. Server configuration,
database setup, code deployment, and maintenance must be repeated for each
institution. As the clinical network grows beyond 10 institutions, this creates
an operational bottleneck that prevents the platform from scaling and diverts
developer effort away from clinical feature development.

### Problem Impact

- Developer time is consumed by infrastructure rather than clinical features
- Patient referrals across institutions have no shared digital record — clinical
  data stays at the originating hospital; the receiving clinician works blind
- The system owner has no visibility into platform-wide activity or
  institutional health across the network
- Every system update must be deployed N times across N isolated servers

### Why Existing Solutions Fall Short

Commercial EMR/EHR platforms (Epic, Athena, Athenahealth) provide
multi-institution capability but are prohibitively complex, expensive, and not
designed for neurodevelopmental assessment workflows. Generic multi-tenancy
libraries handle data isolation but carry no clinical domain knowledge. There is
no off-the-shelf solution that combines multi-institution support with the
specific assessment workflows NDAS provides — GMA, HINE, CDIC, Developmental
Assessment — making a purpose-built expansion the only viable path.

### Proposed Solution

Transform NDAS into a single multi-tenant deployment where each institution is
a fully isolated data tenant. A superadmin onboards a new institution through
one form — institution details and first admin account created atomically in a
single transaction. Institution data is physically partitioned (file storage
under `/{institution_slug}/`) and logically isolated at the ORM level, so no
view can accidentally leak cross-institution data. Each institution manages its
own users, patients, and subscription independently. Cross-institution
capabilities — clinical referral threads and aggregate analytics — are
controlled bridges, not data leaks.

### Key Differentiators

1. **Zero new deployments** — 10+ institutions served from a single codebase
   and a single server, with no additional infrastructure per institution
2. **Superadmin onboarding in minutes** — institution and first admin account
   created atomically; no orphan institutions, no operational gap
3. **Clinical-grade referrals** — a frozen patient snapshot travels with the
   referral thread; the receiving clinician sees exactly what was referred, even
   if the originating record is later updated
4. **Dual-scope analytics** — institution admins see their own institution's
   clinical activity; the superadmin sees cross-institutional aggregate data
   across the entire network
5. **Built for neurodevelopmental workflows** — not a generic EMR adaptation,
   but a platform purpose-built around GMA, HINE, CDIC, and Developmental
   Assessment clinical processes

---

## Target Users

### Primary Users

#### 1. Platform Manager — SUPERADMIN
**Representative:** Rasika (developer) + operational managers

**Context:** Operates outside any single institution. Responsible for the health
of the entire NDAS platform — onboarding new institutions, managing
subscriptions, and monitoring cross-institutional activity.

**Motivations & Goals:**
- Scale to 10+ institutions without spinning up new servers
- Onboard a new hospital in minutes, not days
- Maintain visibility across the entire clinical network from one dashboard

**Current Pain:**
Every new institution means a full deployment cycle — server, database, config,
maintenance. Updates must be applied repeatedly across isolated instances.
There is no single view of platform-wide clinical activity.

**Success Looks Like:**
"I fill in one form — institution name, first admin's details — hit submit, and
the institution is live. I can see all institutions from one screen and jump
into any of them when needed."

---

#### 2. Institution Coordinator — ADMIN
**Representative:** Any responsible clinical person — doctor, nurse manager,
department head, or clinical coordinator, depending on the institution

**Context:** Single-institution actor. Manages the team within their hospital,
monitors clinical activity, and is the point of contact for the superadmin.
May or may not be a practising clinician.

**Motivations & Goals:**
- Get their team registered and operational with minimal setup friction
- Monitor patient activity, assessment volumes, and referral status
- Maintain institutional oversight without deep technical involvement

**Current Pain:**
Currently reliant on the developer for any system changes. No institution-level
analytics dashboard. No visibility into referral activity across the team.

**Success Looks Like:**
"I log in and see my institution's dashboard — who's active, how many patients
are registered, what assessments were done this month, which referrals are
pending. I can add a new clinician myself without calling the developer."

---

#### 3. Multi-Disciplinary Clinician — USER
**Representative:** Consultants, Physiotherapists (PT), Occupational Therapists
(OT), Special Medical Officers, Registrars, Senior Registrars

**Context:** The most numerous user type. Each clinician contributes to their
own clinical section within the patient record. For GMA video analysis — the
platform's flagship collaborative workflow — most or all MDT members are
involved.

**GMA Collaboration Model:**
- Each clinician watches the GMA video independently
- Adds their own clinical opinion as a structured comment
- Selects their diagnosis assessment
- Final decision is reached collaboratively based on the collected opinions
  and rational explanation — not a single clinician's unilateral call

**Motivations & Goals:**
- Access patient records and contribute clinical opinion without friction
- See what colleagues have observed on the same GMA video
- Reach a well-documented, rationally justified final diagnosis
- Send or receive referrals when specialist opinion is needed from another
  institution

**Current Pain:**
In a multi-institution scenario, GMA opinions from specialists at a different
hospital cannot be collected digitally. Referrals for specialist review are
managed by phone, paper, or email — with no structured record of the
consultation.

**Success Looks Like:**
"I get notified that a GMA video is ready for review. I watch it, add my
opinion, select my diagnosis, and see what the consultant and PT have said.
If we need a specialist at another hospital, I send a referral — they get
the frozen patient snapshot and the video, add their opinion, and reply.
The whole consultation thread is permanently in the patient record."

---

### Secondary Users

#### Referring Specialist (Cross-Institution)
A clinician at the receiving institution who provides an expert opinion via the
referral thread. They interact with a read-only frozen snapshot of the patient
record and the GMA video, add their opinion as a referral reply, and close the
consultation. They are a USER within their own institution but act as a
specialist consultant in the referral context.

---

### User Journey

#### SUPERADMIN — Institution Onboarding Journey
1. Logs into God-view dashboard → sees all institution cards with status
2. Clicks "Add Institution" → fills institution details + first admin account
3. Institution created atomically → admin receives credentials
4. Superadmin switches context to new institution → verifies setup
5. Monitors onboarding checklist completion from dashboard

#### Institution ADMIN — Operational Startup Journey
1. Receives credentials from superadmin → logs in → sees onboarding checklist
2. Uploads institution logo → creates clinical team accounts → registers
   first patient
3. Day-to-day: monitors dashboard (patient stats, assessment activity,
   referral queue, team activity)
4. Reviews institution-level reports → sends to clinical management

#### Clinician — GMA Collaborative Review Journey
1. Notified: GMA assessment uploaded and ready for MDT review
2. Opens patient record → GMA tab → watches video
3. Adds structured comment (clinical opinion) + selects diagnosis
4. Reviews peer opinions from other MDT members
5. Team reaches consensus → final diagnosis recorded with rational explanation

#### Clinician — Cross-Institution Referral Journey
1. Patient needs specialist GMA opinion not available at own institution
2. Clinician initiates referral → selects receiving institution + clinician
3. Frozen patient snapshot (with GMA data) automatically attached
4. Receiving specialist notified → reviews snapshot + adds opinion in thread
5. Reply received → originating clinician reads outcome → referral closed
6. Full consultation thread permanently recorded in patient's clinical record

---

## Success Metrics

### User Success

| User | Success Criterion | Target |
|------|------------------|--------|
| SUPERADMIN | New institution live from form submission | < 5 minutes |
| SUPERADMIN | Zero per-institution server deployments | 0 deployment events |
| Clinician (MDT) | GMA opinion + final diagnosis recorded after video upload | Within 7 days |
| Clinician (Referral) | Specialist reply received and consultation thread closed | As promptly as clinically possible |
| Institution ADMIN | Institution onboarding checklist completion | At institution's own pace and discretion |

### Business Objectives

1. **Scale without infrastructure** — Single deployment serves 10+ institutions
   with no additional servers, databases, or deployment cycles per institution
   added. Developer time is never consumed by onboarding a new institution.

2. **Absolute data integrity** — Zero cross-institution data leakage is a
   non-negotiable success criterion. A single instance of data from Institution
   A appearing in Institution B's context constitutes platform failure.

3. **Network reach** — More than 10 institutions active on the platform after
   launch, demonstrating that multi-institution capability drives clinical
   network growth beyond what the single-deployment model could achieve.

4. **Clinical continuity** — All active referrals survive subscription state
   changes and run to completion. No clinical consultation is orphaned by a
   technical or administrative event.

### Key Performance Indicators

| KPI | Measurement Method | Target |
|-----|-------------------|--------|
| Institution onboarding time | Time from form submission to first admin login | < 5 minutes |
| GMA review completion rate | % of GMA assessments with final diagnosis within 7 days | Baseline TBD post-launch |
| Referral response time | Time from referral sent to first specialist reply | Tracked, no hard SLA |
| Cross-institution data incidents | Security audit + automated isolation checks | 0 incidents |
| Active institutions | Count of institutions with ≥1 active user | > 10 post-launch |
| Infrastructure overhead per institution | Developer hours spent per new institution onboarded | 0 hours |
| Referral completion rate | % of sent referrals that reach closed status | Baseline TBD post-launch |

---

## MVP Scope

### Core Features

#### 1. Multi-Institution Foundation
- **Institution Model** — name, slug (immutable), logo, subscription status,
  grace period, active flag; slug is the storage partition key
- **InstitutionContextMiddleware** — resolves active institution on every
  request; ADMIN/USER read from user.institution, SUPERADMIN reads from
  session; replaces current SubscriptionCheckMiddleware
- **InstitutionScopedQuerySet** — custom ORM manager on every model with an
  institution FK; queryset automatically filters to active institution;
  defence-in-depth against accidental cross-institution data exposure
- **institution_context processor** — single context processor injects
  active_institution, user_type, is_superadmin, and institution branding
  into every template; one change point, zero scattered logic
- **InstitutionStorage** — custom file storage backend partitions all uploads
  physically under `/{institution_slug}/videos/`, `/{institution_slug}/
  attachments/`; zero changes to model field declarations
- **User Institution Binding** — institution FK on CustomUser (nullable for
  SUPERADMIN only), user_type field (SUPERADMIN/ADMIN/USER), staff_position
  remains independent
- **Per-Institution Subscription** — subscription status and grace period
  scoped to each institution; grace period gives read-only mode, not hard
  lockout; active referrals survive expiry and run to completion

#### 2. Migration Path
- **MULTI_INSTITUTION_ENABLED feature flag** — when False, system behaves
  exactly as today; when True, full multi-institution mode activates; removed
  after stable production rollout
- **Default institution migration** — existing data migrated atomically to a
  default_institution; existing single-institution deployment becomes a valid
  multi-institution deployment with zero data loss or manual re-entry

#### 3. Superadmin Capabilities
- **Institution Selector Screen** — card grid at `/superadmin/select-
  institution/` showing all institutions with logo, name, subscription status,
  user count, patient count, last activity; landing page for SUPERADMIN with
  no active context
- **Institution Impersonation with Overlay** — superadmin switches context via
  dropdown; persistent top banner reads "Viewing as: [Institution] [Switch ▼]"
  with superadmin-only actions (Move Patient, Edit Subscription, Suspend User)
  injected as additive template tag
- **Atomic Institution Onboarding** — single form creates institution details
  AND first ADMIN account in one transaction; no orphan institutions; superadmin
  hands off immediately at creation time
- **God-View Analytics Dashboard** — cross-institution health cards showing
  subscription state, user counts, assessment volumes, referral activity per
  institution; recent cross-institution events audit log; purely observational
- **Advanced Cross-Institution Aggregate Reports** — exportable Excel/PDF
  reports spanning all institutions; three report scopes using the existing
  ExcelReportGenerator infrastructure: (1) per-patient (existing), (2) per-
  institution aggregate (admin-scoped), (3) cross-institution aggregate
  (superadmin-scoped); superadmin can filter, compare, and export network-wide
  clinical activity data across assessment types, referral volumes, and
  institution health
- **Patient Move Between Institutions** — superadmin-only multi-step flow:
  select patient + destination → impact preview (open referrals, assessments,
  videos, file size) → type institution name to confirm → atomic transaction
  + audit log entry in both institutions + notification to both admins;
  GitHub-style confirmation prevents accidental data moves

#### 4. Institution Admin Capabilities
- **Institution Admin Dashboard** — four-quadrant layout: patient stats by
  status, assessment activity by type this month, referral activity (sent/
  received/pending/closed), team activity (user count and most active
  clinicians); all institution-scoped
- **User Management** — institution admin creates and deactivates clinicians
  within their own institution; superadmin creates the first admin only
- **Institution Profile** — logo upload, institution display settings
- **Institution-Level PDF Branding** — institution logo, name, and header
  injected into all PDF reports generated within that institution's context;
  uses existing BasePDFGenerator/PatientPDFGenerator infrastructure with
  active_institution branding passed from context processor

#### 5. Referral System
- **Referral Model** — dual linked records (ReferralSent + ReferralReceived)
  via referral_uuid; each institution's record self-contained; UUID-linked;
  Institution A deletion does not destroy Institution B's consultation record
- **Frozen Patient Snapshot** — snapshot_data JSONField captures full patient
  profile at referral time; receiving clinician always sees what was referred
  regardless of subsequent updates at originating institution
- **Clinical Consultation Thread** — ReferralMessage model; referral thread
  UI with fixed patient header card, alternating opinion bubbles, clinician +
  institution badge, timestamp; reply box at bottom; snapshot as collapsible
  panel
- **Clinician Referral Inbox** — unified feed: list of threads on left, active
  thread on right; patient thumbnail, referring institution, date, unread
  indicator; familiar messaging metaphor
- **Referral Lifecycle** — PENDING → REPLIED → CLOSED; status badge visible
  at a glance; active referrals survive subscription expiry
- **Patient Referral Tab** — timeline of all referrals (outgoing + incoming)
  in patient detail view; direction, clinician, institution, status, outcome
  without opening thread

#### 6. Notifications
- **Notification Model** — recipient FK, notification_type, title, body, link,
  is_read, created_at; all institution-scoped
- **HTMX Bell Icon** — AdminLTE navbar bell with unread count; pull-based
  polling every 60 seconds; reuses existing AdminLTE bell slot
- **Signal-Driven Referral Events** — post-save signals generate notifications:
  REFERRAL_RECEIVED → receiving clinician; REFERRAL_REPLIED → sending
  clinician; REFERRAL_CLOSED → both clinicians + both institution admins

---

### Out of Scope for MVP

| Feature | Rationale | When |
|---------|-----------|------|
| Referral snapshot versioning | Edge case; send updated snapshot mid-consultation | Phase 2 |
| New institution onboarding checklist | Useful but not blocking adoption | Phase 2 |
| Referral reassignment on clinician departure | Handled manually by admin at launch | Phase 2 |

---

### MVP Success Criteria

The MVP is considered successful when all of the following are true:

1. Existing single-institution data migrated to default_institution with zero
   data loss — verified before feature flag enabled in production
2. New institution onboarded (institution + first admin) in under 5 minutes
3. Zero cross-institution data leakage detected in pre-launch security testing
4. GMA MDT collaborative review workflow intact and unchanged within
   institution context
5. Institution logo and name appear correctly on all generated PDF reports
6. Patient move between institutions completes atomically with audit log
   entries in both institutions
7. Cross-institution aggregate report exports correctly scoped to superadmin
   and institution admin levels respectively
8. At least one complete cross-institution referral sent, replied, and closed
   successfully in staging
9. Feature flag enables safe rollout — production flipped only after staging
   validation passes

---

### Future Vision

**Phase 2 — Operational Polish:**
Referral snapshot versioning, onboarding checklist, referral reassignment
on clinician departure

**Phase 3 — Network Growth:**
API layer for third-party EMR integration, potential expansion beyond
neurodevelopmental to general paediatric clinical networks, mobile-optimised
referral inbox for on-call clinicians
