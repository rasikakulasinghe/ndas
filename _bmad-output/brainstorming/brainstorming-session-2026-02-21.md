---
stepsCompleted: [1, 2, 3]
inputDocuments: []
session_topic: 'Multi-institution support for NDAS'
session_goals: 'Generate ideas across all dimensions: architecture, data model, UX/dashboards, access control, referrals, and subscriptions'
selected_approach: 'ai-recommended'
techniques_used: ['First Principles Thinking', 'Cross-Pollination', 'Morphological Analysis']
ideas_generated: 27
context_file: ''
---

# Brainstorming Session Results

**Facilitator:** Rasika
**Date:** 2026-02-21

## Session Overview

**Topic:** Multi-institution support for NDAS
**Goals:** Generate ideas across all dimensions — architecture, data model, UX/dashboards, access control, referrals, and subscriptions

### Session Setup

Brownfield Django 4.2 medical system. Currently single-institution with Singleton Subscription, flat user model, no institution FK, and system-wide middleware gating. Expanding to full multi-institution support.

## Technique Selection

**Approach:** AI-Recommended Techniques
**Analysis Context:** Multi-institution support for NDAS with focus on all design dimensions

**Recommended Techniques:**
- **First Principles Thinking:** Strip away single-institution assumptions to find bedrock truths before designing the multi-tenant architecture
- **Cross-Pollination:** Draw from Salesforce, Epic/Athena, Stripe Connect, AWS Organizations, Atlassian — adapt proven multi-institution patterns to NDAS's Django stack
- **Morphological Analysis:** Map all design axes to find optimal combinations

**AI Rationale:** Complex architectural + product problem requiring truth-finding → broad ideation → structured synthesis before implementation planning

---

## Phase 1: First Principles Thinking — Bedrock Truths

### 24 Non-Negotiable Truths for Multi-Institution NDAS

| # | Truth |
|---|-------|
| 1 | Patient ownership is institutional — cross-institution visibility requires superadmin action |
| 2 | Subscriptions are per-institution contracts (active / grace / expired) |
| 3 | Superadmin is the only cross-boundary actor |
| 4 | File storage is physically partitioned by institution slug |
| 5 | Two-level permission hierarchy: superadmin sees all, institution admin sees own |
| 6 | 3 user types (SUPERADMIN/ADMIN/USER) + clinical role are independent axes |
| 7 | ADMIN and USER are single-institution beings — fixed at account creation |
| 8 | SUPERADMIN steps into institutions via dropdown context selection |
| 9 | Superadmin actions inside an institution are attributed to that institution |
| 10 | Referrals are controlled data bridges — not patient transfers |
| 11 | Superadmin has a God-view analytics dashboard (population-level only) |
| 12 | Full patient profile travels as a read-only snapshot in referrals |
| 13 | Every clinician has a personal referral inbox |
| 14 | A referral is a clinical consultation thread (message + reply) |
| 15 | Institution onboarding is superadmin-only |
| 16 | Subscription expiry is institution-scoped |
| 17 | Institution-level PDF branding (logo, name, header per institution) |
| 18 | In-app referral notifications only |
| 19 | Active referrals survive subscription expiry — run to completion |
| 20 | Referrals are part of the patient's permanent clinical record (when/why/outcome) |
| 21 | Subscription is activation-only — no feature limits, no user caps |
| 22 | Institution admin is the sole user creator within their institution |
| 23 | Institution dashboard and report analysis are admin-only |
| 24 | Patient assessment records are created by anyone (SUPERADMIN/ADMIN/USER) |

### Permission Matrix

| Action | SUPERADMIN | ADMIN | USER |
|--------|:---:|:---:|:---:|
| Create institution | ✓ | ✗ | ✗ |
| Manage subscription | ✓ | ✗ | ✗ |
| Move patient between institutions | ✓ | ✗ | ✗ |
| God-view analytics dashboard | ✓ | ✗ | ✗ |
| Create first admin for institution | ✓ | ✗ | ✗ |
| Create users/admins within institution | ✗ | ✓ | ✗ |
| Institution dashboard + report analysis | ✓ (overlay) | ✓ | ✗ |
| Create/edit patient records | ✓ | ✓ | ✓ |
| Create/edit assessments | ✓ | ✓ | ✓ |
| Send/receive referrals | ✓ | ✓ | ✓ |
| Personal referral inbox | ✓ | ✓ | ✓ |

---

## Phase 2: Cross-Pollination — 27 Ideas Generated

### Architecture Ideas

**[Architecture #1]: Institutional Impersonation with Persistent Overlay**
_Concept:_ Superadmin's institution dropdown triggers a full context switch — they see exactly what that institution's admin sees but a persistent top banner reads "Viewing as: [Institution] [Switch ▼]" with superadmin-only action buttons injected — Move Patient, Edit Subscription, Suspend User. One middleware reads `request.session['active_institution']` for all users including superadmin.
_Novelty:_ No view-level special-casing needed — institution context always resolved from session. Superadmin overlay is purely additive via template tag, not a separate view system.

**[Architecture #2]: Split Referral Records — Dual Ownership**
_Concept:_ Every referral creates two linked records — `ReferralSent` (owned by Institution A, visible in patient's Referral tab) and `ReferralReceived` (owned by Institution B, visible in clinician's inbox). Linked by `referral_uuid`. Each institution's record holds the full snapshot independently.
_Novelty:_ Removes fragile FK dependency between institutions. Each institution's data is self-contained even after referral closes. Institution A deletion does not destroy Institution B's consultation record.

**[Architecture #3 — REMOVED]:** Capability caps — not applicable. Subscriptions have no feature limits.

**[Architecture #4 — REVISED]: Superadmin God-View Dashboard**
_Concept:_ Shows institutional health (subscription state, user counts, assessment volumes, referral activity) — not usage meters. Institution cards with click-to-activate context.
_Novelty:_ Purely observational — no direct action from God-view. Keeps the dashboard clean and analytical.

**[Architecture #5]: Institution Bootstrap — First Owner Pattern**
_Concept:_ Institution creation form has two sections: Institution Details + First Admin Account. On submit, NDAS creates the institution AND first ADMIN user atomically. No orphan institutions.
_Novelty:_ Eliminates operational gap where institution exists with no admin. Superadmin hands off immediately at creation time.

**[Architecture #6]: Institution-Scoped Audit Trail with Cross-Institution Events**
_Concept:_ Every action log entry carries: user, user_type, institution (acting), action, target_object, timestamp. Cross-institution events generate audit entries in BOTH institutions — marked OUTGOING/INCOMING.
_Novelty:_ Full regulatory compliance. Every cross-boundary event permanently traceable from both sides.

**[Architecture #7]: Context Processor as Single Source of Truth**
_Concept:_ Single `institution_context` processor runs on every request. For ADMIN/USER: reads `request.user.institution`. For SUPERADMIN: reads `request.session['active_institution']`. Returns active_institution, user_type, is_superadmin, institution_branding to all templates.
_Novelty:_ One place to change. Institution-awareness becomes infrastructure, not scattered logic.

### Data Model Ideas

**[Data Model #8]: The Institution Model — Minimal but Complete**
_Concept:_ `Institution`: name, slug (immutable after creation), logo, subscription_status, subscription_start, grace_period_end, is_active, created_by (superadmin FK), created_at. Slug is the storage partition key — protected after first save.
_Novelty:_ Slug immutability enforced in model `save()` override. Clean separation of identity from capability.

**[Data Model #9]: UserInstitution Bridge — Direct FK Approach**
_Concept:_ `CustomUser` gets institution FK (nullable for SUPERADMIN only), user_type (SUPERADMIN/ADMIN/USER), staff_position (existing). `get_active_institution(request)` utility reads user.institution for ADMIN/USER and session for SUPERADMIN.
_Novelty:_ No separate membership table needed. Simple enough for the permission model. Single utility function used everywhere consistently.

**[Data Model #10]: Referral Model — Full Structure**
_Concept:_ `Referral`: referral_uuid (UUID), patient FK, from_institution, from_clinician, to_institution, to_clinician, when_referred, why_referred (rich text), snapshot_data (JSONField — full patient profile at referral time), status (PENDING/REPLIED/CLOSED), outcome (text), outcome_recorded_by, outcome_recorded_at, survives_expiry=True. `ReferralMessage`: referral FK, sender, body, timestamp.
_Novelty:_ snapshot_data freezes patient state at referral time. Receiving clinician always sees what patient looked like when referred, even if Institution A updates later.

### UX Ideas

**[UX #5]: Institution Badge Notifications for Superadmin Dropdown**
_Concept:_ Superadmin's institution dropdown shows live badges — pending referrals, subscription warnings, users awaiting approval. Superadmin knows which institution needs attention before switching context.
_Novelty:_ Dropdown becomes a triage tool — not just a selector.

**[UX #6]: Clinician Referral Inbox as Unified Feed**
_Concept:_ Referral inbox: list of referral threads on left, active thread on right. Each thread shows patient thumbnail, referring institution name, date, unread reply indicator. Replying feels like clinical messaging.
_Novelty:_ Familiar messaging metaphor — reduces training overhead in clinical settings.

**[UX #7]: Three-Tier Report Architecture**
_Concept:_ Reports at three scopes — (1) Patient report: existing PDF/Excel per assessment, (2) Institution report: admin-only aggregate across all patients, (3) God-view report: superadmin cross-institution aggregate. Same engine, three scopes.
_Novelty:_ Existing ExcelReportGenerator gets institution scope injected. No duplicate infrastructure.

**[UX #8]: Persistent Institution Identity in the UI**
_Concept:_ Every page shows institution logo + name in AdminLTE sidebar header. When superadmin switches institution, sidebar updates to selected institution's branding. Users always know which institution they're in.
_Novelty:_ Uses existing AdminLTE brand-logo + brand-text slots. One template context processor injects active_institution globally.

**[UX #9]: Referral Thread UI — Clinical Consultation Card**
_Concept:_ Fixed header card: Patient name + BHT, sending/receiving institution + clinician, date, status badge. Below: message thread with alternating bubbles, clinician name, institution badge, timestamp. Reply box at bottom. Patient snapshot as collapsible panel.
_Novelty:_ Conversation paradigm reduces form-filling friction. Status badge makes lifecycle visible at a glance.

### Implementation Ideas

**[Implementation #11]: Institution-Aware URL Routing — No Slug in URLs**
_Concept:_ Institution context lives in session, NOT in URL. URLs remain clean: /patients/, /reports/, /referrals/. Zero URL restructuring of existing 5 apps — institution awareness injected at middleware level only.
_Novelty:_ Preserves all existing URL patterns. 50+ existing views need only queryset filtering changes. Migration effort drops dramatically.

**[Implementation #12]: Institution Middleware — The Gatekeeper**
_Concept:_ New `InstitutionContextMiddleware` runs after AuthenticationMiddleware. Resolves active institution, attaches request.institution and request.user_type, checks subscription status, redirects SUPERADMIN with no context to institution selector. Replaces current SubscriptionCheckMiddleware.
_Novelty:_ Single insertion point. One middleware replaces entire current subscription gating system and adds institution context simultaneously.

**[Implementation #13]: InstitutionScopedQuerySet — ORM-Level Isolation**
_Concept:_ Reusable custom manager on every model with institution FK. `Patient.objects.all()` automatically filters to `institution=request.institution` via thread-local. Views cannot accidentally leak cross-institution data even if developer forgets to filter.
_Novelty:_ Defence-in-depth. Even incorrectly written views enforce isolation. Reduces "forgot to filter by institution" security bugs to near-zero.

**[Implementation #14]: InstitutionStorage — Custom File Storage Backend**
_Concept:_ Custom `FileSystemStorage` subclass overrides `_save()` to inject institution slug: `/{institution_slug}/videos/{filename}`, `/{institution_slug}/attachments/{filename}`. All FileField/ImageField declarations use `storage=InstitutionStorage()`. Slug retrieved from thread-local.
_Novelty:_ Zero changes to model field declarations. Directory isolation is physical — not just a database filter.

**[Implementation #15]: Superadmin Institution Selector Screen**
_Concept:_ SUPERADMIN with no active_institution lands on `/superadmin/select-institution/` — card grid showing all institutions with logo, name, subscription status badge, user count, patient count, last activity, pending-action badge.
_Novelty:_ Institution selection is deliberate and informed. Card grid doubles as quick status monitor.

### Edge Case Ideas

**[Edge Case #16]: Patient Move — Multi-Step Confirmation Flow**
_Concept:_ Patient move is multi-step: select patient + destination → impact preview (open referrals, assessments, videos, file size) → type institution name to confirm → atomic transaction + audit log in both institutions + notification to both admins.
_Novelty:_ GitHub-style "type the name" forces deliberate intent. Full impact preview prevents accidental data disruption.

**[Edge Case #17]: Referral Continuity When Clinician Leaves**
_Concept:_ When USER is deactivated, incoming pending referrals reassigned to institution admin. Outgoing referrals remain attributed to original clinician but flagged "Clinician no longer active — contact [admin]." No referral silently orphaned.
_Novelty:_ Referral continuity protected through staff turnover — common clinical reality.

**[Edge Case #18]: Subscription Grace Period — Graceful Degradation**
_Concept:_ During grace period: system works normally + persistent warning banner. After grace_period_end: login blocked but 30-day read-only mode for viewing records and downloading reports.
_Novelty:_ Clinical data never suddenly inaccessible. Patient safety feature — not just a business feature.

**[Edge Case #19]: Referral Snapshot Versioning**
_Concept:_ "Send Updated Snapshot" creates new ReferralMessage of type SNAPSHOT_UPDATE with JSONField diff — changed fields highlighted in receiving clinician's view. Original snapshot never overwritten.
_Novelty:_ Addresses real clinical scenario where patient condition evolves during consultation.

**[Edge Case #20]: New Institution Onboarding Checklist**
_Concept:_ New admin sees persistent checklist: ☐ Upload logo, ☐ Set report template, ☐ Create first user, ☐ Register first patient, ☐ Send first referral. Driven by data — checks whether logo exists, users exist, patient exists. Disappears when complete.
_Novelty:_ Reduces activation time. No manual needed. Tracks institution.onboarding_complete boolean.

### Notification Ideas

**[Notification #21]: In-App Notification System — Lightweight**
_Concept:_ `Notification` model: recipient FK, notification_type, title, body, link, is_read, created_at. AdminLTE navbar bell icon shows unread count. HTMX polling every 60 seconds. All institution-scoped.
_Novelty:_ Reuses existing AdminLTE bell slot. Pull-based — no WebSocket needed. Fits server-side rendering architecture.

**[Notification #22]: Signal-Driven Referral Notifications**
_Concept:_ Every referral state change generates notifications via post-save signals. REFERRAL_RECEIVED → notify receiving clinician. REFERRAL_REPLIED → notify sending clinician. REFERRAL_CLOSED → notify both clinicians + both institution admins.
_Novelty:_ Signal-driven means no view can accidentally skip a notification. Adding new types requires only new signal handler.

### Dashboard Ideas

**[Dashboard #23]: Institution Admin Dashboard — Four Quadrant Layout**
_Concept:_ Four AdminLTE card quadrants: (1) Patient Stats by status, (2) Assessment Activity by type this month, (3) Referral Activity sent/received/pending/closed, (4) Team Activity user count and most active clinicians. All institution-scoped.
_Novelty:_ Complete clinical operations picture in one screen. Each quadrant links to full management section.

**[Dashboard #24]: God-View Superadmin Dashboard — Cross-Institution Aggregate**
_Concept:_ Three sections: (1) Platform Health — total institutions/patients/assessments/referrals, (2) Institution Cards — sortable by status/activity with click-to-activate context, (3) Recent Cross-Institution Events — audit log of patient moves, institution creations, subscription changes.
_Novelty:_ Purely observational — all management happens inside institution context. Clean analytical tool.

**[Dashboard #25]: Patient Record — Referrals Tab**
_Concept:_ New Referrals tab in patient detail: timeline of all referrals (outgoing + incoming), direction arrow, clinician + institution, status badge, outcome. Each entry links to full thread. When/why/outcome visible in timeline without opening referrals.
_Novelty:_ Referral history becomes part of longitudinal care documentation alongside assessments.

### Migration Ideas

**[Migration #26]: Zero-Downtime Migration Path**
_Concept:_ Step 1: create default_institution. Step 2: data migration adds institution_id FK to all existing records pointing to default_institution. Step 3: move existing MEDIA files to /default/ subdirectory. Step 4: Subscription singleton becomes default_institution's subscription. Existing installations continue working unchanged.
_Novelty:_ Existing single-institution deployments become valid multi-institution deployments automatically. No data loss, no manual entry, no downtime.

**[Migration #27]: Feature Flag During Rollout**
_Concept:_ `MULTI_INSTITUTION_ENABLED = False` in settings controls rollout. When False: system behaves exactly as today. When True: full multi-institution mode activates. Flag checked only in middleware and top-level template tags. Removed when stable.
_Novelty:_ Ship data models and migrations first, test on staging, flip flag in production. Zero production risk during development.

---

## Phase 3: Morphological Analysis

### 9 Design Axes Evaluated

| Axis | Decision | Winner | Rationale |
|------|----------|--------|-----------|
| A — Data Isolation | Row-level (ORM) vs Schema vs Database | **A1: Row-level** | Native Django, InstitutionScopedQuerySet manager |
| B — Context Resolution | Session vs URL-prefix vs Subdomain | **B1: Session-based** | Preserves all existing URL patterns |
| C — User Binding | Direct FK vs Membership table vs Hybrid | **C1: Direct FK (null for SUPERADMIN)** | Simplest model for confirmed permission structure |
| D — Referral Architecture | Single record vs Dual linked vs Shared space | **D2: Dual linked records** | Institution data self-contained, UUID-linked |
| E — Subscription Enforcement | Middleware vs Model property vs Both | **E3: Both** | Defence-in-depth enforcement |
| F — Superadmin Context | Impersonation+overlay vs Separate views vs Query param | **F1: Impersonation with overlay** | Confirmed by product owner |
| G — File Storage | Custom backend vs Dynamic MEDIA_ROOT vs Cloud | **G1: Custom InstitutionStorage** | Transparent physical file partitioning |
| H — Notifications | HTMX pull vs WebSocket vs Email+in-app | **H1: HTMX pull-based** | Consistent with existing SSR architecture |
| I — Migration | Feature flag vs Big bang vs Parallel systems | **I1: Feature flag + default institution** | Zero-risk brownfield migration |

### Conflict Check — All Clear

All 8 axis combinations checked: ✅ No conflicts detected. The optimal combination is fully coherent.

### The Optimal Architecture Summary

**Data:** Row-level institution isolation via InstitutionScopedQuerySet manager on every model
**Context:** Session-based resolution via InstitutionContextMiddleware + institution_context processor
**Users:** institution FK on CustomUser (null for SUPERADMIN), user_type field, staff_position independent
**Referrals:** Dual linked records (ReferralSent + ReferralReceived) via referral_uuid, snapshot_data JSONField
**Subscription:** Middleware gate + institution.is_active model property, grace period with read-only fallback
**Superadmin:** Full institution impersonation via session dropdown, persistent overlay with elevated actions
**Storage:** InstitutionStorage custom backend, /{institution_slug}/videos/ physical partitioning
**Notifications:** Notification model + HTMX bell icon polling, signal-driven creation
**Migration:** MULTI_INSTITUTION_ENABLED feature flag, existing data → default_institution atomically
