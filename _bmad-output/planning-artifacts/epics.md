---
stepsCompleted: [1, 2, 3]
inputDocuments: [_bmad-output/specs/spec-backup-restore/SPEC.md, _bmad-output/planning-artifacts/architecture/architecture-backup-restore/ARCHITECTURE-SPINE.md, _bmad-output/specs/spec-backup-restore/professional-options.md, _bmad-output/planning-artifacts/architecture.md]
---

# NDAS - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the **Institutional Admin & Super Admin Data Backup/Restore** feature (SPEC-backup-restore), decomposing SPEC.md's capabilities and ARCHITECTURE-SPINE.md's architecture decisions into implementable stories. There is no UX design contract for this feature and no project-wide PRD coverage — `prd.md` and `architecture.md` predate this feature and are listed here only for traceability of the "DB backup strategy" deferred-gap note that originally motivated it.

## Requirements Inventory

### Functional Requirements

FR1: An institutional admin or super admin can trigger creation of a backup packaged as a single downloadable `.zip` file containing their scoped database records, media files, and attachments (institution-scoped for an institutional admin; system-wide or an explicitly selected institution subset for a super admin).

FR2: A backup trigger can optionally specify a date or date range filtered against patient profile creation date; when set, only patients created within that window are included, but every related record for each included patient (assessments, videos, attachments, etc.) is exported in full regardless of that related record's own date. Omitting the filter exports the full scope as today.

FR3: The database portion of a backup archive is a single consolidated JSON file (not split per model/table); media files are preserved in their existing per-institution/type folder structure inside the archive, so it can be manually browsed without special tooling.

FR4: Every backup archive carries a manifest recording schema/app version, included institution(s), record counts, checksums, and whether a date/date-range filter was applied (and its bounds), so a restore can validate compatibility, integrity, and scope before applying.

FR5: A super admin can restore data by uploading a previously downloaded backup `.zip` file (full-scope or date-scoped); the system automatically snapshots current state before applying. Institutional admins can never trigger a restore, regardless of scope.

FR6: Restoring a full-scope archive replaces the target institution's in-scope data (delete-scoped-then-reload, preserving original PKs). Restoring a date-scoped archive additively imports only patients not already present in the target system (matched against `bht`/`nnc_no`/`ptc_no`/`pc_no`/`pin`), skipping in full — never merging or overwriting — any patient that already exists; the admin sees a preview of exactly which patients will be skipped, imported, or excluded (missing-institution / ambiguous-conflict) before confirming.

FR7: Restoring an archive with a mismatched schema version, an altered checksum, or corrupted contents is rejected with a clear error before any data is modified.

FR8: Backup and restore jobs run asynchronously in the background with visible progress and a completion/failure notification, so large media sets never block the requesting admin's session or time out the HTTP request.

FR9: Admins can view backup history scoped to their permissions (who triggered it, when, size, scope), and download or delete individual backups within their scope.

FR10: A super admin can optionally enable a system-wide, age-based retention policy (max age in days) that automatically prunes old backups; disabled by default until explicitly turned on.

FR11: Every backup creation, download, and restore action is recorded in the audit trail with the acting user, timestamp, and scope.

### NonFunctional Requirements

NFR1 (Security/PHI): Backup archives must never be stored under or served via a publicly-accessible static/media path; download requires authenticated, permission-checked access only — the primary protective control since archives are unencrypted at rest by decision.

NFR2 (Security): Restore is restricted to super admins only. An uploaded restore `.zip` must pass the same MIME/type/size validation as other uploads (`python-magic` pattern), then the manifest/checksum validation (FR4/FR7), before any content is trusted.

NFR3 (Security/Abuse prevention): Backup/restore trigger endpoints must be rate-limited per the existing `django_ratelimit` pattern.

NFR4 (Performance/Scalability): Backup/restore I/O must be implemented as streaming/chunked from the start (no full-archive or full-model in-memory buffering), with no artificial dataset-size cap deferred to later.

NFR5 (Reliability): Backup/restore must run as background/async jobs, never synchronous request-response, given existing file-size limits (2GB video, 100MB doc) multiplied across many records.

NFR6 (Data integrity): On a date-scoped (partial) restore, a patient already present in the target system must be skipped in full together with all related records — never field-level merged or overwritten.

NFR7 (Auditability/Compliance): Every backup/restore action must be traceable via the audit trail, consistent with the existing `UserActivityMiddleware`/`UserTrackingMixin` conventions.

### Additional Requirements

- **No starter/greenfield template applies** — this is a brownfield feature addition inside the existing Django monolith, not a new project. Epic 1 Story 1 scaffolds a new `backup/` app rather than initializing a template.
- New top-level `backup/` app: `models.py` (`BackupJob`, `BackupRetentionPolicy`), `views.py`, `services.py`, `management/commands/run_backup.py` + `run_restore.py`, `urls.py`, `templates/backup/`, `tests/` package — one-app-per-domain convention (AD-1). Both models inherit `TimeStampedModel` + `UserTrackingMixin`.
- Async execution via detached OS subprocess (`subprocess.Popen` running a management command), not Celery — no new task-queue infrastructure introduced (AD-2).
- DB export streams into a single `db_export.json` (one JSON object keyed by `app_label.model_name`, every key always present even as `[]`), one model's queryset at a time via `.iterator()`, per-record streaming — no full-model or full-archive in-memory buffering (AD-3, AD-5, AD-13).
- Institution scope resolution is a 3-way branch reused by both export paths: `for_institution(inst)` (single), `.filter(institution__in=selected)` (explicit multi-institution subset), `all_institutions()` (system-wide) — never routed incorrectly (AD-3).
- Archive layout: `manifest.json` + `db_export.json` + `media/{institution_slug}/videos|attachments/...` inside one `.zip`, stored under non-public `BASE_DIR/backups/<job_id>/` (AD-4, AD-5).
- Manifest schema: `schema_version` (hash of applied migrations, exact-equality check), per-file SHA-256 checksums, `date_filter` block, whole-archive checksum stored in `BackupJob.archive_checksum` (AD-6).
- Download and restore-upload reuse the existing `FileResponse` pattern already used for Excel export (AD-7).
- Progress via `BackupJob` status/`progress_pct` + HTMX polling; completion/failure also raises a `referral` app `Notification` row, reusing the existing notification bell (AD-8).
- Retention pruning is lazy/on-access (runs only when a super admin loads the backup list), age-based only, disabled by default, never touches `pre_restore_snapshot` rows or backups tied to an in-progress job (AD-9).
- Authorization reuses `institution/`'s existing tenant-scoping; restore views add an explicit super-admin-only check on top (AD-10).
- Job-level concurrency lock per scope (AD-16) and a disk-capacity pre-check before starting any job (AD-17).
- **Full-scope restore** (no date filter): delete-scoped-then-reload per model, preserving original PKs, in a fixed dependency order that now includes `CDICRecord` and `GeneralPaediatricAssessment` alongside the models already covered (AD-3).
- **Date-scoped (partial) restore**: additive import with full FK remapping — `patient`/`problem` chain, `institution` (remapped by matching target `Institution.slug`, resolved up front before the preview), `GMAssessment.video_file` (via the `Video` PK map), `added_by`/`last_edit_by`/`performed_by` (preserve if the `CustomUser` PK exists in target, else `NULL`), M2M fields (e.g. `diagnosis`) preserved as shared reference data. Conflict-matching checks all five of `bht`/`nnc_no`/`ptc_no`/`pc_no`/`pin`, with an ambiguous-match guard. One DB transaction per import-set patient, not one for the whole archive. Media application mirrors the same final per-patient partition — a skipped or excluded patient's media is never extracted to disk (AD-18, AD-19).
- Pre-restore safety snapshot reuses the backup mechanism itself (`job_type="pre_restore_snapshot"`), exempt from retention auto-pruning, always full-scope even when guarding a date-scoped restore (AD-14).
- Manual per-backup deletion is a separate, permission-gated view distinct from retention auto-pruning (AD-15).
- **Explicitly out of scope for export/restore**: the `referral` app's 3 models (stay full-scope-only if ever included; excluded entirely from date-scoped export/restore) and `Bookmark` (generic polymorphic reference, not a direct FK) — both named gaps in ARCHITECTURE-SPINE.md's Deferred section, not silently dropped.
- No new external dependencies: `zipfile`/`hashlib`/`subprocess`/`json`/`django.core.serializers` are stdlib/Django; `python-magic` and `django-ratelimit` are already project dependencies.
- Template naming follows the project's existing `manager/add/edit/view` convention: `backup/manager.html` (history/list), `backup/create.html` (trigger), `backup/status.html` (polled partial), `backup/restore.html` (upload form) — AdminLTE 3.2 + Bootstrap 4.6, unchanged per CLAUDE.md.

### UX Design Requirements

N/A — no UX design contract exists for this feature. Template and interaction patterns follow the project's existing AdminLTE 3.2 + Bootstrap 4.6 conventions and the `manager/add/edit/view` naming pattern (see Additional Requirements above); no new visual system, component library, or accessibility audit was scoped by SPEC.md or ARCHITECTURE-SPINE.md.

### FR Coverage Map

FR1: Epic 1 - trigger full/institution-scoped backup creation
FR2: Epic 1 - optional date/date-range export filter (patient-anchored cascade)
FR3: Epic 1 - single JSON + media folder archive format
FR4: Epic 1 - manifest generation (validated in Epic 2)
FR5: Epic 2 - super-admin-only restore upload + automatic pre-restore snapshot
FR6: Epic 2 - full-scope vs date-scoped restore semantics + preview
FR7: Epic 2 - manifest/checksum rejection before any data is modified
FR8: Epic 1 & Epic 2 - async execution + progress (creation and restore jobs)
FR9: Epic 3 - backup history, download, delete
FR10: Epic 3 - age-based retention policy
FR11: Epic 1, Epic 2 & Epic 3 - audit trail (creation, restore, download — delete has no separate audit requirement in SPEC.md's CAP-7)

## Epic List

### Epic 1: Backup Creation (Export)
An institutional admin or super admin can trigger a backup — full-scope or narrowed to a specific date/date-range of patients — that downloads as a single browsable `.zip` (one JSON database file + organized media folders) with an integrity manifest, running as a background job with visible progress. Standalone value: data is protected and manually inspectable even before restore exists.
**FRs covered:** FR1, FR2, FR3, FR4, FR8, FR11

### Epic 2: Restore (Import)
A super admin can restore data by uploading a backup — full-scope (replaces the target institution's data) or date-scoped (additively imports only patients not already present, skipping any that already exist) — validated against its manifest, previewed before confirmation, protected by an automatic pre-restore snapshot. Depends on Epic 1's archive format, not on Epic 3.
**FRs covered:** FR5, FR6, FR7, FR8, FR11

### Epic 3: Backup History, Download, Delete & Retention
Admins see backup history scoped to their permissions, download or delete individual backups; a super admin can optionally enable age-based retention pruning. Depends on Epic 1, independent of Epic 2.
**FRs covered:** FR9, FR10, FR11

## Epic 1: Backup Creation (Export)

An institutional admin or super admin can trigger a backup — full-scope or narrowed to a specific date/date-range of patients — that downloads as a single browsable `.zip` (one JSON database file + organized media folders) with an integrity manifest, running as a background job with visible progress. Standalone value: data is protected and manually inspectable even before restore exists.

### Story 1.1: Trigger a full-scope backup of my institution's data

As an institutional admin,
I want to trigger creation of a backup containing all of my institution's database records, media files, and attachments,
So that my institution's data is protected against loss.

**Acceptance Criteria:**

**Given** an institutional admin is logged in
**When** they trigger a backup with no date filter
**Then** a `BackupJob` row is created with `status=pending`, `triggered_by` set to the requesting user, and a detached subprocess is launched
**And** the HTTP request returns immediately — the export never runs synchronously in the request/response cycle

**Given** the backup job completes
**When** the admin checks its status
**Then** `status=completed` and a `.zip` exists under non-public storage (`BASE_DIR/backups/<job_id>/`, never under `MEDIA_ROOT`/`STATIC_ROOT`)
**And** the `.zip` contains `db_export.json` with only that admin's institution's records, plus a `media/` folder mirroring the existing `{institution_slug}/videos/` and `{institution_slug}/attachments/` structure

**Given** the trigger view checks `shutil.disk_usage` before launching
**When** available space is below the safety margin
**Then** the job is refused immediately with `status=failed` and a clear error, never starting a partial write

**Given** a `BackupJob` for the same scope is already `pending` or `running`
**When** a second trigger for that same scope is attempted
**Then** it is refused before a new job row is created

**Given** the backup trigger endpoint
**When** it is called more times than the configured rate limit allows
**Then** the extra requests are rejected per the existing `django_ratelimit` convention

### Story 1.2: Super admin — system-wide or selected-institutions backup scope

As a super admin,
I want to back up the whole system or an explicit subset of institutions I choose,
So that I can protect data across multiple institutions in one archive.

**Acceptance Criteria:**

**Given** a super admin selects "system-wide" when triggering a backup
**When** the job runs
**Then** the archive includes every institution's in-scope records, and the manifest's `institutions` list and `record_counts` reflect the whole system

**Given** a super admin selects two or more specific institutions
**When** the job runs
**Then** only those institutions' records are included, resolved via `.filter(institution__in=selected)` — never via `for_institution`, which cannot express a multi-institution subset

**Given** an institutional admin (not a super admin)
**When** they view the backup trigger form
**Then** no system-wide or multi-institution option is presented — they can only ever back up their own institution

### Story 1.3: Integrity manifest on every backup

As an admin,
I want every backup archive to carry an integrity manifest,
So that a later restore can verify the archive is authentic and uncorrupted before any data is touched.

**Acceptance Criteria:**

**Given** a completed backup
**When** its `manifest.json` is inspected
**Then** it contains `schema_version` (a hash of applied migrations), `institutions`, per-model `record_counts`, per-file SHA-256 `checksums`, `generated_at`, `generated_by`, and a `date_filter` block with `applied=false`

**Given** the `.zip` is finalized
**When** its own SHA-256 is computed
**Then** it is stored in `BackupJob.archive_checksum` (a trusted DB field) — `manifest.json` never tries to embed a hash of itself

**Given** the manifest's `record_counts`
**When** compared against the actual exported querysets for each model
**Then** they match exactly, computed via the same scoped queries used for the export

### Story 1.4: Date/date-range-scoped export

As an institutional admin or super admin,
I want to optionally narrow a backup to patients created within a specific date or date range,
So that I can export a targeted subset of data instead of everything.

**Acceptance Criteria:**

**Given** an admin supplies a date or date range when triggering a backup
**When** the export runs
**Then** only patients whose profile was created within that window (`Patient.created_at`) are included

**Given** a patient qualifies by creation date
**When** their related records are exported (videos, attachments, GM/HINE/Developmental assessments, CDIC records, GPA records, problems, problem actions)
**Then** every one of those related records is included in full, regardless of that record's own date

**Given** no date filter is supplied
**When** a backup is triggered
**Then** the full institution-scoped set is exported exactly as in Story 1.1/1.2 — no regression

**Given** a date-scoped export
**When** the archive is built
**Then** `referral` app data is never included (full-scope archives only), and `manifest.json`'s `date_filter` block has `applied=true` with the correct `start`/`end` bounds

### Story 1.5: Progress visibility and completion notification

As an admin,
I want to see live progress on a backup I've triggered and get notified when it finishes or fails,
So that I don't have to guess whether a large job is done.

**Acceptance Criteria:**

**Given** a backup job is running
**When** the admin views its status page
**Then** an HTMX-polled partial shows current status/progress without a full page reload

**Given** a backup job completes or fails
**When** that happens
**Then** `progress_pct=100` and `status=completed` (or `status=failed` with `error_message`) are written together in one save — never treated as two separate signals
**And** a `Notification` row is created so the admin is alerted even after navigating away, reusing the existing notification bell

## Epic 2: Restore (Import)

A super admin can restore data by uploading a backup — full-scope (replaces the target institution's data) or date-scoped (additively imports only patients not already present, skipping any that already exist) — validated against its manifest, previewed before confirmation, protected by an automatic pre-restore snapshot.

### Story 2.1: Upload and validate a restore archive

As a super admin,
I want to upload a previously downloaded backup `.zip`,
So that the system verifies it's trustworthy before touching any data.

**Acceptance Criteria:**

**Given** a super admin uploads a `.zip` on the restore form
**When** the file is received
**Then** it passes the same `python-magic` MIME/type/size validation used for every other upload before anything else happens

**Given** an uploaded archive
**When** its SHA-256 is checked against the originating `BackupJob.archive_checksum`, or any per-file checksum in `manifest.json` doesn't match, or `schema_version` doesn't exactly equal the target DB's current one
**Then** the restore is rejected with a clear, specific error naming the mismatch, before any data is modified

**Given** an institutional admin (not a super admin)
**When** they attempt to reach the restore upload view, by any URL or scope
**Then** they are denied — restore is never available to them under any circumstance

### Story 2.2: Restore preview and confirmation flow

As a super admin,
I want to see exactly what a restore will do before committing to it,
So that I never apply an archive blind.

**Acceptance Criteria:**

**Given** a validated archive from Story 2.1
**When** the super admin reaches the preview step
**Then** it shows the archive's scope — institution(s), full-scope vs. date-scoped, and record counts — with no data yet modified

**Given** the preview is shown
**When** the super admin does not explicitly confirm
**Then** nothing is applied and the system remains untouched, whether they navigate away or explicitly cancel

**Given** the super admin explicitly confirms the preview
**When** confirmation is submitted
**Then** the restore is handed off to apply exactly as previewed — never with a silently different scope

### Story 2.3: Full-scope restore with automatic pre-restore snapshot

As a super admin,
I want a confirmed full-scope restore to take an automatic safety snapshot before applying,
So that a bad restore can always be undone.

**Acceptance Criteria:**

**Given** a full-scope restore confirmed via Story 2.2's preview
**When** `run_restore.py` begins applying it
**Then** it first creates a full-scope (undated) snapshot of current state via the same backup mechanism (`job_type=pre_restore_snapshot`), exempt from AD-9's retention auto-pruning

**Given** the pre-restore snapshot exists
**When** the restore proceeds
**Then** each model is restored in the fixed dependency order (`Patient`; `Video`, `Attachment`, `GMAssessment`, `HINEAssessment`, `DevelopmentalAssessment`, `CDICRecord`, `GeneralPaediatricAssessment`, `Problem`; then `ProblemAction`), deleting existing rows matching the archive's institution scope and reloading the archive's rows with their original PKs preserved

**Given** a restore job for a given scope is already `pending` or `running`
**When** a second restore or backup job for that same scope is triggered
**Then** it is refused (job-level concurrency lock)

**Given** a full-scope restore job (backup or restore, per AD-8's shared mechanism)
**When** it runs
**Then** the same `BackupJob`-based progress polling and completion/failure notification built in Story 1.5 applies to it — a super admin sees live status and is notified without needing to watch the page (FR8, restore-side)

### Story 2.4: Date-scoped (partial) restore — match and preview

As a super admin,
I want a date-scoped archive's restore preview to show exactly which patients will be skipped, imported, or excluded,
So that I can trust the outcome before confirming.

**Acceptance Criteria:**

**Given** a date-scoped archive's `"patients.patient"` records
**When** each is processed
**Then** its source institution is resolved to the target `Institution` by matching slug first; no matching slug excludes that patient (missing-institution) before identity matching ever runs

**Given** a patient with a resolved target institution
**When** its identity is checked against existing target patients on all five of `bht`/`nnc_no`/`ptc_no`/`pc_no`/`pin`
**Then** any populated-field match places it in the skip-set; no match places it in the import-set; a patient with none of the five fields set is always import-set (accepted residual risk of an eventual duplicate)

**Given** an archived patient matches more than one distinct target patient, or two archived patients both match the same target patient
**When** this ambiguity is detected
**Then** the affected patient(s) are excluded (ambiguous-conflict) rather than guessed, with the reason reported

**Given** the match step has finished for every archived patient
**When** the restore preview is displayed
**Then** it lists the skip-set, import-set, and excluded set with reasons, and this partition is final — no patient can move between categories after this point, including during the apply step

### Story 2.5: Date-scoped (partial) restore — additive import

As a super admin,
I want confirming a date-scoped restore to import only the new patients with all their data intact,
So that existing patients are never touched, merged, or duplicated.

**Acceptance Criteria:**

**Given** the confirmed import-set from Story 2.4
**When** each patient is applied
**Then** it happens in its own DB transaction (Patient first, then its cascaded rows in dependency order) with a fresh PK on every row — a failure on one patient rolls back only that patient, and already-committed patients before it stay imported

**Given** an imported row's foreign keys
**When** it is saved
**Then** `patient`/`problem` chains and `GMAssessment.video_file` are remapped through this patient's source-PK→new-PK maps, `institution` is set to the target institution already resolved in Story 2.4, and `added_by`/`last_edit_by`/`performed_by` are preserved if that `CustomUser` PK exists in the target system or set to `NULL` otherwise

**Given** a skip-set or excluded patient
**When** the import step runs
**Then** none of their rows or media files are extracted or applied — left exactly as they were

**Given** an import-set patient's media files in the archive
**When** they are applied
**Then** they are copied to disk only after that patient's DB transaction has committed, referenced via each row's `fields.file` path — never a blind copy of the whole `media/` folder

**Given** a retried restore of the same archive after a prior partial failure
**When** it runs again
**Then** patients already imported are now found present in the target and correctly re-classified as skip-set (Story 2.4), so the retry is safe and non-duplicating

### Story 2.6: Restore audit trail

As a compliance-conscious admin,
I want every restore attempt — successful, failed, or denied — recorded in the audit trail,
So that we can always answer "who restored what and when."

**Acceptance Criteria:**

**Given** a completed restore
**When** the audit trail is reviewed
**Then** it shows the acting super admin, timestamp, and scope (full vs. date-scoped, institutions involved, and for a date-scoped restore, patient counts skipped/imported/excluded)

**Given** a denied restore attempt (e.g. an institutional admin attempting one, or a checksum/schema rejection)
**When** it happens
**Then** it is logged to `logs/security.log`, consistent with the project's dedicated security-event logging convention

## Epic 3: Backup History, Download, Delete & Retention

Admins see backup history scoped to their permissions, download or delete individual backups; a super admin can optionally enable age-based retention pruning.

### Story 3.1: View backup history scoped to my permissions

As an admin,
I want to see a list of past backups scoped to my permissions,
So that I know what's been backed up and by whom.

**Acceptance Criteria:**

**Given** an institutional admin views the backup list
**When** it loads
**Then** only their own institution's backups are shown, with who triggered it, when, size, and scope

**Given** a super admin views the backup list
**When** it loads
**Then** backups system-wide are shown, including `pre_restore_snapshot` rows — visible only to super admins, per AD-14

**Given** a backup that is still `pending` or `running`
**When** it appears in the list
**Then** it is shown with its current status but is not offered as downloadable yet

### Story 3.2: Download a completed backup

As an admin,
I want to download a completed backup within my permission scope,
So that I can keep an off-system copy or inspect it manually.

**Acceptance Criteria:**

**Given** a completed backup within an admin's scope
**When** they request the download
**Then** it is returned via the existing `FileResponse` pattern (matching the Excel export precedent), from a permission-checked view scoped the same as Story 3.1

**Given** a backup that is `pending`, `running`, or `failed`, or whose `.zip` has vanished from disk (e.g. pruned between list render and download)
**When** a download is requested
**Then** a specific "backup not available" error is returned — never an unhandled exception or a partial/corrupt file served as valid

**Given** a download occurs
**When** it completes
**Then** it is logged to `logs/security.log`, since download has no natural model mutation of its own to hang the audit entry on

### Story 3.3: Delete an individual backup

As an admin,
I want to delete an individual backup within my scope,
So that I can free space or remove one I no longer need, independent of any automatic policy.

**Acceptance Criteria:**

**Given** an institutional admin
**When** they delete a backup
**Then** only a backup belonging to their own institution can be deleted

**Given** a super admin
**When** they delete a backup
**Then** any backup, regardless of institution, can be deleted

**Given** a delete action is confirmed
**When** it executes
**Then** both the `.zip` on disk and the `BackupJob` row are removed — distinct from Story 3.4's automatic age-based pruning

### Story 3.4: System-wide age-based retention policy

As a super admin,
I want to optionally enable an age-based retention policy,
So that old backups are pruned automatically instead of accumulating forever.

**Acceptance Criteria:**

**Given** the retention policy at its default (disabled)
**When** any amount of time passes
**Then** no backup is ever auto-deleted

**Given** a super admin enables the policy and sets a max-age-in-days value
**When** a super admin next loads the backup list
**Then** the prune sweep runs lazily at that moment (never on an institutional admin's page load, no scheduler or cron) and removes backups older than that age, measured from `completed_at`

**Given** the prune sweep runs
**When** it evaluates candidates for deletion
**Then** it excludes every `pre_restore_snapshot` row and any backup that is the source of a `BackupJob` currently `pending` or `running`

**Given** backups are pruned
**When** the sweep completes
**Then** the action is logged as a system-attributed entry, not any individual user's action
