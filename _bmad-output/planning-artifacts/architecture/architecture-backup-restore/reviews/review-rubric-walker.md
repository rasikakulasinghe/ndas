# Independent Review — ARCHITECTURE-SPINE.md (Backup & Restore)

**Reviewer role:** independent quality reviewer, rubric-walker
**Reviewed:** `_bmad-output/planning-artifacts/architecture/architecture-backup-restore/ARCHITECTURE-SPINE.md` (AD-1..AD-12)
**Cross-checked against:** `.memlog.md` (same dir), `_bmad-output/specs/spec-backup-restore/SPEC.md` + `professional-options.md`, `_bmad-output/planning-artifacts/architecture.md`, and the live codebase (`institution/managers.py`, `patients/models.py`, `video/models.py`, `problemlist/models.py`, `users/middleware.py`, `ndas/custom_codes/Custom_abstract_class.py`, `institution/views.py`, `scripts/switch_env.py`)

## Verdict

**Not build-ready.** The spine is well-organized, its low-risk ADs (async mechanism, storage path, archive layout, manifest schema, download pattern, no-encryption stance) are sound and correctly ratify existing brownfield precedent — but three of its highest-stakes rules either rest on a factually false premise or simply don't exist, and all three bear directly on PHI correctness/leakage in a multi-tenant medical-records system. This needs another pass before `bmad-build` should start on CAP-1/CAP-3.

---

## Critical findings

### C1 — AD-3's core PHI-leakage prevention rule doesn't work for ~80% of the schema it must scope
**Location:** AD-3 (DB export via `serializers`)

AD-3's entire stated purpose is preventing cross-institution PHI leakage, via: *"calls `django.core.serializers.serialize("json", queryset)` per model against `InstitutionScopedManager`-filtered querysets."* I verified against the actual codebase which models carry `InstitutionScopedManager`:

- `Patient` — yes, via `PatientManager(InstitutionScopedManager)` (`patients/models.py:141,432`)
- `ReferralSent`, `ReferralReceived`, `Notification` — yes (`referral/models.py:112,206,294`)
- `Video` — **no**. `objects = VideoManager()` (`video/models.py:80`), a plain `models.Manager` subclass with no institution scoping at all.
- `GMAssessment`, `CDICRecord`, `Attachment`, `Bookmark`, `HINEAssessment`, `DevelopmentalAssessment` (`patients/models.py`), `Problem`, `ProblemAction` (`problemlist/models.py`) — **no**. All inherit only `TimeStampedModel, UserTrackingMixin` with the implicit default manager. These are exactly the models CAP-1 requires an institutional admin's scoped backup to include (assessments, attachments, bookmarks, problem list), and per `architecture.md`'s own Data Boundaries table they're scoped only indirectly, via their `Patient` FK.

AD-3 as written gives an implementer no actual method to call for most of the exportable schema. Two implementers will diverge exactly where it matters most: one invents ad hoc `.filter(patient__institution=...)` per model (untested, unspecified whether that's even the sanctioned shape), another calls a nonexistent `.for_institution()` and gets an `AttributeError`, or — worst case — falls back to unscoped `Model.objects.all()` per model, which is precisely the cross-institution leak AD-3 exists to prevent. `architecture.md` names institution-scoped isolation as a "Critical Decision (Block Implementation)" with an "absolute constraint — zero leakage" NFR (NFR13); this AD does not actually deliver on that for this feature.

**Fix direction:** AD-3 needs a per-model scoping table (or a stated derivation rule — e.g. "for models without `InstitutionScopedManager`, scope via the model's `patient__institution` (or equivalent FK chain) instead, enumerated per model") before this is safe to build.

### C2 — CAP-3's entire safety mechanism (pre-restore snapshot + rollback + preview/confirm) has no governing AD
**Location:** CAP-3 in the Capability → Architecture Map; Deferred → "Sandbox/preview restore environment"

SPEC.md's CAP-3 success criterion is explicit: *"A restore completes only after the super admin uploads the `.zip` and confirms a preview step; if the restore fails or is cancelled, the automatic pre-restore snapshot can return the system to its prior state."* Scanning AD-1 through AD-12, none of them define:

- **How/when** the pre-restore snapshot is actually taken (a synchronous internal `run_backup`-equivalent invoked first inside `run_restore.py`? A raw pre-restore DB dump using a different mechanism?)
- **Where** it's stored, and whether AD-4's non-public-path rule and AD-6's manifest/checksum rules apply to it the same way a normal backup does
- Whether it is **exempt from AD-9's retention pruning** (if not stated exempt, an enabled retention policy could prune the one archive a failed restore needs to roll back from)
- What **"return system to prior state"** concretely means operationally — an automated rollback command the system runs itself on failure, or a manual runbook step where the super admin re-uploads the auto-snapshot through the same restore flow?
- What the **preview step** shows (presumably AD-6's manifest fields — institutions, record counts, checksums — rendered before commit) and how upload → preview → confirm is sequenced as a UI/request flow. The Structural Seed's `restore.html` is listed simply as "upload form" (singular), which doesn't obviously accommodate a two-step preview-then-confirm flow.
- Whether there's any **cancel** mechanism for an in-flight restore, given CAP-3 explicitly mentions "or is cancelled."

The Deferred section's own text papers over this: *"Sandbox/preview restore environment — SPEC.md resolved restore applies directly (**with a pre-restore snapshot**), no separate sandbox."* That parenthetical treats the pre-restore snapshot as an already-decided mechanism; it isn't — it's asserted, not architected. Deferring "no sandbox" is a legitimate simplification; silently deferring the snapshot/rollback/preview mechanism itself is not, since it's the load-bearing safety net for a super-admin operation that overwrites live PHI. (Note: `scripts/switch_env.py` already has an analogous "back up before overwrite" idiom in this repo — copy-aside before replace — that could inform this, but nothing in the spine points to it or resolves the DB-level analogue.)

**Fix direction:** add an AD (or two) that pins the snapshot mechanism, its storage/retention treatment, and the preview→confirm request flow, before CAP-3 goes to `bmad-build`.

### C3 — No concurrency control for restore vs. concurrent writes or concurrent jobs
**Location:** AD-2, AD-8, AD-9 (absent); not listed in Deferred either

Restore "applies directly" to production data (CAP-3, ratified by the Deferred note above) — there is no shadow DB, no maintenance-mode gate, and no job-mutex anywhere in the spine. Nothing prevents:
- A restore running while a clinician is mid-save on a `Patient`/`GMAssessment` record through the ordinary UI (FK/ordering conflicts, partial overwrite, silent data loss)
- Two backup jobs, or a backup and a restore, running concurrently and racing on the same institution's files/rows
- A second restore being triggered while one is already `running`

For a system whose entire purpose here is protecting PHI against data loss, an unlocked restore racing with live writes is itself a data-loss vector the feature is nominally built to prevent. This is not mentioned anywhere as a decided rule or as an explicit Deferred item (unlike the orphaned-job watchdog, which *is* honestly deferred with a stated interim mitigation).

**Fix direction:** at minimum, an AD stating that `run_restore.py` refuses to start while another `BackupJob` for the same scope is `running`, and/or that a restore in progress flips some read-only/maintenance flag checked by the normal write paths (even a coarse one) — enumerated as a real AD, not silence.

---

## High-severity findings

### H1 — AD-3 doesn't satisfy SPEC's explicit "streaming/chunked from the start" constraint
**Location:** AD-3

SPEC.md's Constraints section states plainly: *"Backup/restore I/O must be implemented as streaming/chunked from the start — no artificial dataset-size cap deferred to 'later.'"* `django.core.serializers.serialize("json", queryset)` called without `.iterator()` on the queryset and without the `stream=` kwarg (writing straight to an open file handle) will materialize the full queryset and the full JSON string in memory before anything hits disk. For a "many GB of video" / many-thousand-record institution (CAP-5's own framing), this is exactly the pattern the constraint rules out, and AD-3 gives no guidance to avoid it.

### H2 — CAP-6's explicit "delete individual backups" capability has no view, AD, or map entry
**Location:** AD-1 (Structural Seed `views.py` list), Capability → Architecture Map (CAP-6 row)

CAP-6's intent text is explicit: *"...download the `.zip` **or delete** individual backups within their scope..."* AD-1's structural seed enumerates `views.py` as "trigger, status, list/history, download, restore-upload" — delete is absent, and the CAP-6 row in the Capability Map cites only AD-7 (download pattern) and AD-9 (retention pruning), neither of which covers an admin-initiated single-backup delete. This is a named, testable capability with zero architectural coverage. CLAUDE.md's own Delete System convention (`has_delete_permission`/`validate_can_delete` from `delete_helpers.py`, `delete_confirmation_modal.html`) exists precisely for this shape of feature and isn't bound to it anywhere in the spine.

### H3 — AD-2's "detached subprocess" doesn't specify the flags that make it actually detached
**Location:** AD-2

The rule pins the invocation shape (`[sys.executable, manage.py, "run_backup"|"run_restore", job_id]`) for cross-platform parity, which is good — but doesn't require `start_new_session=True` (POSIX) or the Windows equivalent (`creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP`). A plain `subprocess.Popen([...])` without these stays in the launching Gunicorn worker's process group; if that worker is recycled (timeout, `max_requests`, a deploy restart) while a multi-GB job is running, the child can be torn down with it. AD-2's whole stated purpose — surviving past the request/worker — isn't actually guaranteed by the rule as written.

### H4 — CAP-5's "be notified" (after navigating away) has no binding AD
**Location:** AD-8; Capability → Architecture Map (CAP-5 row)

CAP-5's success criterion: *"...the admin can navigate away, and later see completion status **and be notified**..."* AD-8 wires HTMX polling into a status-page partial only — if the admin navigates away, that polling stops, and nothing else surfaces completion elsewhere in the UI. The project already has a working mechanism built for exactly this shape of problem (referral app's `Notification` model + `referral/signals.py` + the bell, polled every 60s per `architecture.md`). The spine doesn't decide whether backup/restore completion piggybacks on that, is log-file-only (per the current Logging row), or is deliberately narrowed to "come back and check the history page." `professional-options.md` lists "email/in-app notification" as a beyond-v1 candidate, which suggests the narrower reading is probably intended — but that should be a stated, ratified scoping decision in the spine, not something left to be inferred from a companion doc.

---

## Medium-severity findings

### M1 — `BackupJob` has no backup/restore discriminator field
**Location:** AD-8

`run_backup.py` and `run_restore.py` both write to `BackupJob` per the Structural Seed, but AD-8's field list (`status, progress_pct, error_message, created_at, updated_at, triggered_by, scope`) has no `job_type`/`action` field. CAP-6 ("backup history") and CAP-7 ("every backup creation, download, and restore action recorded") both need to distinguish backup rows from restore rows in the same table; nothing pins how. (Related: CAP-6's success text also names "size" as history-list metadata, which also isn't a field on `BackupJob` — recoverable via `os.path.getsize()` at render time, but unstated either way.)

### M2 — `BackupJob.scope` isn't pinned to the project's canonical institution-scoping pattern
**Location:** AD-8, AD-10

`scope` is listed as a bare field with no type/shape given, rather than an explicit `Institution` FK filtered the way every other Phase 2-scoped model is required to be (`InstitutionScopedManager.for_institution()`, per `architecture.md`'s own "FORBIDDEN — raw filter bypasses isolation" rule). Given CAP-4 requires strict per-institution visibility into backup history/list/download, an ad hoc `scope` field is exactly the shape of thing `architecture.md` warns against elsewhere in this project.

### M3 — No AD addresses local disk-capacity risk for `BASE_DIR/backups/`
**Location:** AD-4; absent from Deferred

`architecture.md` explicitly preserves on-premise deployment as a target, and CAP-5 itself frames jobs as "many GB of video." Nothing in the spine addresses free-space checking before a job starts, a size cap/quota, or defined behavior if the disk fills mid-write (job left `failed` with a partial file cleaned up? left on disk indefinitely?). AD-6's checksum check does catch a corrupted archive before a *restore* is applied, so this isn't a silent-corruption risk — but it's an unaddressed operational reliability gap for a feature whose entire purpose is protecting against data loss.

### M4 — Minor internal ambiguity between AD-2 and the "State & mutation" convention row
**Location:** AD-2 vs. Consistency Conventions → State & mutation

AD-2 requires the trigger view to *create* the initial `BackupJob` row before launching the subprocess. The Consistency Conventions table states *"views are read-only on that model."* The charitable reading (views don't drive `pending → running → completed/failed` *transitions*, but the initial insert is fine) is probably what's intended, but it's imprecise enough that an implementer could read it literally and either move row-creation into the subprocess (breaking AD-2) or get confused about the write boundary.

---

## Low-severity findings

### L1 — CAP-7's audit-trail framing overstates what `UserActivityMiddleware`/`UserTrackingMixin` actually do
**Location:** Capability → Architecture Map (CAP-7 row)

Verified in code: `UserActivityMiddleware.process_request` (`users/middleware.py:29-53`) only throttle-updates `UserSession.last_activity`; it does not auto-populate `added_by`/`last_edit_by` anywhere. `Custom_abstract_class.py`'s `UserTrackingMixin` is just two plain FK fields with no signal or middleware wiring behind it. Every real call site sets `added_by=request.user` **manually** in the view (`referral/views.py:93,106,356`, `video/views.py:124,318`, `patients/views.py:2073`) — directly contradicting CLAUDE.md's own "auto-populated by UserActivityMiddleware... never set manually" claim. This inaccuracy is inherited from CLAUDE.md/`architecture.md`, not invented by this spine, and the spine's actual plan (view sets `triggered_by=request.user` explicitly when creating the `BackupJob` row) happens to match the real pattern regardless — but repeating the "auto-populated" framing in the Capability Map risks an implementer assuming `triggered_by` gets set "for free" and skipping it.

### L2 — No stated test-directory convention for the new `backup/` app
**Location:** Structural Seed

CLAUDE.md explicitly flags the `tests.py` vs `tests/` package collision as a project-wide footgun ("adding a top-level `<app>/tests.py`... breaks `python manage.py test` discovery for the entire project"). The spine's Structural Seed doesn't mention a tests location at all for the new app. Low stakes (one obvious correct answer — `backup/tests/` package, matching `institution/`/`referral/`), but worth one line given the CLAUDE.md warning exists specifically because this has apparently bitten this project before.

---

## What the spine gets right (for balance)

- AD-2 (subprocess over Celery), AD-4 (non-public storage path), AD-7 (FileResponse reuse), and AD-12 (no-encryption stance) are all verified against real precedent in the codebase (`institution/views.py`'s `FileResponse` export pattern checks out exactly as described) and correctly ratify rather than reinvent existing conventions.
- AD-9 (lazy/on-access retention pruning, no cron/Celery-beat) is a well-reasoned, consistent choice given this project's stated "boring technology" bias, and is honestly justified in the memlog.
- The Deferred list's orphaned-job watchdog entry is a model of how to defer correctly: it states the gap, gives a cheap interim mitigation (staleness check on `updated_at`), and ties the real fix to a named prerequisite (project-wide monitoring) — this is the pattern C2/C3 above should have followed instead of silence.
- AD-6's manifest schema and AD-11's upload-trust ordering (MIME check → manifest/checksum validation → only then trust content) are enforceable and correctly sequenced.

---

## Summary table

| ID | Severity | Location | One-line |
|---|---|---|---|
| C1 | Critical | AD-3 | Scoping rule assumes `InstitutionScopedManager` exists on models that don't have it (Video, GMAssessment, Attachment, etc.) |
| C2 | Critical | CAP-3 map row / Deferred | Pre-restore snapshot, rollback, and preview/confirm flow are asserted, never architected |
| C3 | Critical | AD-2/AD-8/AD-9 (absent) | No concurrency lock for restore vs. live writes or overlapping jobs |
| H1 | High | AD-3 | Doesn't satisfy SPEC's streaming/chunked-from-the-start constraint |
| H2 | High | AD-1 / CAP-6 map row | No delete-single-backup view/AD despite explicit CAP-6 requirement |
| H3 | High | AD-2 | "Detached" subprocess doesn't specify actual OS-level detachment flags |
| H4 | High | AD-8 / CAP-5 map row | "Be notified" after navigating away isn't wired to anything beyond the status page |
| M1 | Medium | AD-8 | `BackupJob` has no backup/restore discriminator field (or size field) |
| M2 | Medium | AD-8/AD-10 | `scope` field isn't pinned to the canonical `InstitutionScopedManager` pattern |
| M3 | Medium | AD-4 | No disk-capacity/quota handling for local `BASE_DIR/backups/` |
| M4 | Medium | AD-2 vs. Conventions | "Views are read-only on BackupJob" mildly contradicts AD-2's view-creates-row rule |
| L1 | Low | CAP-7 map row | Audit-trail framing overstates what `UserActivityMiddleware` actually auto-populates (inherited inaccuracy) |
| L2 | Low | Structural Seed | No stated `backup/tests/` convention |
