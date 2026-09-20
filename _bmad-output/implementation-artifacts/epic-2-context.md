# Epic 2 Context: Restore (Import)

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Let a super admin restore data by uploading a backup `.zip` produced by Epic 1: full-scope archives replace the target institution's in-scope data, date-scoped archives additively import only patients not already in the target. Every archive is validated against its manifest and checksums before anything is touched, previewed before confirmation, and protected by an automatic pre-restore snapshot. It matters because it is the recovery path that makes backups useful, and the highest-risk write path in the feature (PHI, destructive deletes, FK remapping). It depends on Epic 1's archive format and `BackupJob` mechanism, not on Epic 3. No project-wide PRD or architecture doc covers this feature; its planning source is the backup/restore SPEC and ARCHITECTURE-SPINE.

## Stories

- Story 2.1: Upload and validate a restore archive
- Story 2.2: Restore preview and confirmation flow
- Story 2.3: Full-scope restore with automatic pre-restore snapshot
- Story 2.4: Date-scoped (partial) restore — match and preview
- Story 2.5: Date-scoped (partial) restore — additive import
- Story 2.6: Restore audit trail

## Requirements & Constraints

- Restore is super-admin-only, by any URL or scope; an institutional admin is always denied. The restore trigger/upload endpoint is rate-limited (`django_ratelimit`).
- An uploaded `.zip` is untrusted: it must pass the same `python-magic` MIME/type/size validation as other uploads, then archive-checksum, per-file checksum, and exact `schema_version` equality checks. Any mismatch rejects with a specific error naming it, before any data is modified.
- Nothing is applied until the super admin explicitly confirms a preview. Navigating away or cancelling leaves the system untouched, and confirmation applies exactly what was previewed.
- Restore runs asynchronously (never in the request cycle), with progress polling and a completion/failure notification, same as backup jobs. Streaming I/O applies in reverse: read the zip entry by entry, never load the whole archive into memory.
- A restore or backup trigger is refused while a conflicting job is pending/running.
- Full-scope archive (`date_filter.applied` false): take a full-scope snapshot first, then per model in fixed dependency order (`Patient`; `Video`, `Attachment`, `GMAssessment`, `HINEAssessment`, `DevelopmentalAssessment`, `CDICRecord`, `GeneralPaediatricAssessment`, `Problem`; `ProblemAction` last), inside one transaction per model, delete existing in-scope rows then reload the archive's rows with original PKs. `Institution` rows are never created by restore; target institutions must already exist, matched by slug.
- Date-scoped archive: additive import only. Each archived patient gets one final, immutable outcome before preview:
  - Excluded (missing-institution): source institution slug has no match in the target. Checked first.
  - Skip: matches an existing target patient on any populated one of `bht`/`nnc_no`/`ptc_no`/`pc_no`/`pin`. A skipped patient is skipped in full (rows and media), never merged or overwritten.
  - Import: no match. A patient with none of the five identifiers is always import (accepted residual duplicate risk).
  - Excluded (ambiguous-conflict): one archived patient matches multiple distinct target patients, or two archived patients match the same target patient. Never guessed.
- Preview lists skip, import, and excluded sets with exclusion reasons. No patient moves between sets afterward, including during apply.
- Import: one DB transaction per import-set patient, with fresh PKs (deserialize with `pk=None`), so one patient's failure rolls back only that patient. Remap every FK:
  - `patient`/`problem` chains via per-patient source-to-new PK maps.
  - `Patient.institution` set to the target institution resolved at match time.
  - `GMAssessment.video_file` via the Video PK map (Video inserts before GMAssessment).
  - `added_by`/`last_edit_by`/`performed_by`: keep if a `CustomUser` with that PK exists in the target, else `NULL`, never attribute to the restoring admin.
  - M2M fields (e.g. `diagnosis`) preserved as-is, treated as shared reference data.
- Media for import-set patients is copied to disk only after that patient's transaction commits, addressed by each row's `fields.file` path. Never blind-copy the whole `media/` folder; skip-set/excluded media is never extracted. A retry after partial failure is safe because already-imported patients reclassify as skip.
- `referral` models and `Bookmark` are out of scope for date-scoped restore (Bookmark for all restore). Restore never creates Institution rows.
- Audit: every completed restore records the acting super admin, timestamp, and scope (full vs date-scoped, institutions, skipped/imported/excluded counts for date-scoped). Denied attempts (institutional admin, checksum/schema rejection) log to `logs/security.log`.

## Technical Decisions

- Restore reuses Epic 1's mechanism: a `BackupJob` with `job_type` `restore`, a detached `manage.py run_restore <job_id>` subprocess (same detached-process, per-job log file, and failed-on-Popen-error rules as backup), and status/`progress_pct` written together in one terminal save. Only the command process writes status transitions after start. `backup/views.py` remains the sole entry point into the service layer.
- `run_restore` branches solely on `manifest.date_filter.applied`, never on record counts or heuristics.
- Authenticity check: the uploaded zip's SHA-256 is compared against `BackupJob.archive_checksum`, located via the manifest's `source_job_id`. Then each file's SHA-256 is verified against `manifest.checksums` before that file is applied. Recompute `schema_version` with the same function the exporter uses (`_compute_schema_version` in `backup/services.py`).
- Pre-restore snapshot: `run_restore`'s first step creates a normal backup through the existing export service with `job_type=pre_restore_snapshot`. It is always full-scope and undated for the target institution(s), even when guarding a date-scoped restore. It is stored like any backup, linked to the restore job, and exempt from Epic 3's retention pruning. Only super admins see it.
- `db_export.json` is one JSON object keyed `"<app_label>.<model_name>"`, each value an array of serializer-shape records (`model`, `pk`, `fields`). All 13 keys are always present, possibly `[]`. Patient ownership in date-scoped archives comes from each record's own `fields.patient`/`problem` value.
- Restore views use the project's `UserType` role check plus `institution/`'s tenant-scoping, `@handle_view_errors`, and the `manager/add/edit/view` template naming (`backup/restore.html` upload form; preview/status reuse AdminLTE 3.2 + Bootstrap 4.6 unchanged).
- No new dependencies. Do not use `loaddata`.

## UX & Interaction Patterns

- Flow: upload form, then validation result (specific error or success), then preview (scope, record counts; for date-scoped, the skip/import/excluded lists with reasons), then explicit confirm or cancel, then status page (HTMX polling), then a bell notification on completion or failure.
- No separate UX contract exists; follow existing AdminLTE patterns.

## Cross-Story Dependencies

- 2.1 gates everything: 2.2 previews only a validated archive; 2.3 and 2.5 apply only what 2.2 confirmed.
- 2.4 must finalize the skip/import/excluded partition before 2.2's preview renders it and 2.5 applies it. The date-scoped preview in 2.2 is really 2.4's output.
- 2.3 builds the restore-job trigger, lock, and `run_restore` scaffold plus snapshot step that 2.5 reuses, so implement 2.3's job machinery first. 2.3 also extends Story 1.5's progress and notification to restore jobs.
- 2.6 audit and logging touches 2.1 (denials and rejections), 2.3, and 2.5 (completion summaries), so it can land last.
- Consumes from Epic 1: archive layout, manifest, `BackupJob`, the export service (for the snapshot), and the concurrency and disk-check patterns. Epic 3's retention and delete must never touch `pre_restore_snapshot` rows.

## Discrepancies (planning docs vs. implemented Epic 1 code)

- **Referral data in date-scoped archives:** planning says a date-scoped archive never includes referral data. The implemented export always writes the three referral keys (`referral.referralsent`, `referral.referralreceived`, `referral.referralmessage`) at full institution scope, even when a date filter is applied (never date-narrowed). Restore must ignore these keys when `date_filter.applied` is true. Also, `ReferralMessage` is scoped via `sender_institution`, not a scoped manager. Planning's full-scope restore order lists no referral models, so whether a full-scope restore reloads referral rows is unspecified and needs a decision.
- **Manifest shape:** the implemented manifest has extra `manifest_version` (1), `checksum_algorithm`, and `scope_type`, and its `date_filter` lacks planning's `field: "patient.created_at"`. `checksums` covers `db_export.json` and `media/...` entries only, not `manifest.json`. `institutions` is a list of slugs. `generated_by` is a username string.
- **Media names and skipped media:** archive media names are `media/<FileField.name>`, i.e. `media/<slug>/videos|attachments/<file>`; the slug can be `pending` for orphaned files. A media file that was missing at backup time is absent from the archive and `checksums` while the job still completes (with a warning in `error_message`), so restore must tolerate DB rows whose file is not in the zip. Duplicate member names are possible and are flagged, not checksummed twice.
- **`BackupJob` fields:** planning names `completed_at` and a self-referential `pre_restore_snapshot` FK. Neither exists yet, so Epic 2 needs a migration. Scope is `scope_type` (single/multi/system) plus `scope` FK, a `scopes` M2M, and `trigger_institution`, not just a nullable `scope`. The job type choices `restore` and `pre_restore_snapshot` already exist.
- **Notifications:** only `BACKUP_COMPLETED`/`BACKUP_FAILED` exist, and `backup/notifications.py` hard-codes "Backup" wording and links to `backup:backup-create`. Restore needs its own notification types and copy. It also needs a delivery institution, since a delivery institution is required.
- **Concurrency lock:** implemented as an institution-set overlap check (system-scoped overlaps everything) across all pending/running jobs of any type, inline in `backup_create`, not a simple same-scope check. Restore triggers must reuse or extract this logic rather than reimplement it.
- **Subprocess and log naming:** the per-job log is `run_backup.log`, not planning's `job.log`. Only the `run_backup` command and trigger exist; `run_restore`, the restore views, the URLs, and `backup/restore.html` are all unbuilt.
- **Authenticity gap:** verifying an upload against `BackupJob.archive_checksum` only works for archives made by this system whose job row still exists. Epic 3's manual delete removes the row, so a deleted job's downloaded archive would fail the authenticity check. Planning does not address this, nor where a validated upload is staged between the preview and confirm steps.
