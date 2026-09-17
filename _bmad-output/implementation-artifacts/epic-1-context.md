# Epic 1 Context: Backup Creation (Export)

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Give institutional admins and super admins a way to protect their data by triggering creation of a downloadable, human-browsable backup archive — full-scope or narrowed to a date/date-range of patients — that runs as a background job with visible progress, so large media-heavy exports never block or time out the requesting admin's session. This is the foundational epic: it defines the archive format and export mechanism that Epic 2 (restore) and Epic 3 (history/download/delete/retention) both build on, and it delivers standalone value (protected, inspectable data) even before restore exists. No project-wide PRD or architecture doc covers this feature; its planning source is SPEC-backup-restore's SPEC.md and ARCHITECTURE-SPINE.md.

## Stories

- Story 1.1: Trigger a full-scope backup of my institution's data
- Story 1.2: Super admin — system-wide or selected-institutions backup scope
- Story 1.3: Integrity manifest on every backup
- Story 1.4: Date/date-range-scoped export
- Story 1.5: Progress visibility and completion notification

## Requirements & Constraints

- A backup is one downloadable `.zip` containing scoped DB records, media, and attachments. Institutional admins are always scoped to their own institution; super admins can choose their own institution, an explicit multi-institution subset, or system-wide.
- An optional date/date-range filter narrows by patient profile creation date only; every related record of a qualifying patient (videos, attachments, assessments, problems/actions) is still exported in full regardless of its own date. Omitting the filter exports the full scope unchanged.
- The database portion is always a single consolidated JSON file, never split per model/table; media retains its existing per-institution/type folder layout so the archive is manually browsable without tooling.
- Every archive carries a manifest (schema/app version, institutions, per-model record counts, per-file checksums, whether/how a date filter was applied) — this is what lets a later restore validate the archive before touching data (Epic 2 consumes it; this epic only produces it correctly).
- Backup creation must run asynchronously with visible progress and a completion/failure notification — never synchronously in the request/response cycle, given existing 2GB video / 100MB doc upload limits multiplied across many records.
- I/O must stream/chunk from the start (no full-archive or full-model in-memory buffering, no dataset-size cap deferred to later).
- Backup archives must never live under a publicly-accessible static/media path; only authenticated, permission-checked access can reach them.
- The trigger endpoint is rate-limited via the existing `django_ratelimit` convention.
- Every backup creation is recorded in the audit trail (acting user, timestamp, scope).
- Out of scope for this epic's export: the `referral` app's 3 models and `Bookmark` are excluded from date-scoped export (referral stays full-scope-only; `Bookmark` is excluded entirely, a known named gap, not silently dropped).

## Technical Decisions

- New top-level `backup/` app (one-app-per-domain convention): `models.py` (`BackupJob`, `BackupRetentionPolicy`, both inheriting `TimeStampedModel`+`UserTrackingMixin`), `views.py`, `services.py`, `management/commands/run_backup.py`, `urls.py`, `templates/backup/`, `tests/` package. `backup/views.py` is the sole entry point into `services.py` — no other app may call the service layer directly, so rate limiting/permissions/audit can't be bypassed by a second code path.
- Async execution is a detached OS subprocess (`subprocess.Popen` invoking `manage.py run_backup <job_id>`), not Celery — no task-queue infrastructure introduced. The trigger view only does: permission check → concurrency-lock check → disk-space check → create `BackupJob` row → launch subprocess → redirect. The child process must survive the launching worker's lifecycle (detached process group on POSIX/Windows); stdout/stderr go to a per-job log file, never `PIPE`. If `Popen` itself fails to start the child, the trigger view (not the command) writes `status="failed"`.
- Institution scope resolution is a 3-way branch reused everywhere: single institution via `for_institution(inst)`, an explicit multi-institution subset via `.filter(institution__in=selected)` (never routed through `for_institution`), system-wide via `all_institutions()`.
- DB export streams into one `db_export.json` inside the open `zipfile.ZipFile`, one model's queryset at a time via `.iterator()`, record-by-record — never buffering a full model or archive in memory. Each model is scoped via whichever real FK path reaches `Institution` (a scoped manager for `Patient`/referral models; explicit `.filter(patient__institution=...)` or the cascade chain for models with no scoped manager). `dumpdata`/`loaddata` are never used (can't be scoped).
- Archive layout: `manifest.json` + `db_export.json` + `media/{institution_slug}/videos|attachments/...`, mirroring the existing media path helpers verbatim. `db_export.json` is one JSON object keyed by `"<app_label>.<model_name>"`; every in-scope model key is always present even when empty (`[]`).
- Manifest fields: `source_job_id`, `schema_version` (SHA-256 over applied migration names, exact-equality check on restore), `institutions`, `record_counts`, per-file SHA-256 `checksums` (POSIX-style relative paths matching `zipfile` namelist output), `generated_at`, `generated_by`, `date_filter` (`applied`, `start`, `end`). The whole-archive SHA-256 is computed after finalizing the `.zip` and stored in `BackupJob.archive_checksum` (a DB field) rather than embedded in the manifest.
- Storage is non-public: `BASE_DIR/backups/<job_id>/`, never under `MEDIA_ROOT`/`STATIC_ROOT`, with no URLconf exposing it directly.
- `BackupJob` fields include `job_type`, `status` (pending/running/completed/failed), `progress_pct`, `archive_checksum`, `error_message`, `triggered_by` (set explicitly by the view, like other manual `added_by` patterns in this codebase — not automatic middleware), and `scope` (nullable Institution FK; null = system-wide). The terminal `progress_pct=100` + `status="completed"` (or `failed` + `error_message`) are written together in one save, never as two signals. Status is polled via an HTMX partial; completion/failure also creates a `referral`-app `Notification` row so the admin is alerted even after navigating away.
- Date-scoped export resolves `patient_qs` from the same 3-way institution scope, narrowed by `created_at__date__range`, then filters every other in-scope model relative to `patient_qs` (directly or via the `problem__patient` chain) rather than by institution or its own date — guaranteeing referentially complete patients. `referral` models never participate in this cascade.
- Authorization reuses `institution/`'s existing tenant-scoping middleware/context processors; no parallel permission mechanism.
- A job-level concurrency lock refuses a new backup/restore trigger for a scope that already has a `pending`/`running` `BackupJob`. A disk-capacity pre-check (`shutil.disk_usage` against an estimated-size safety margin) refuses to start a job it can't safely complete, failing immediately rather than mid-write.
- No new external dependencies: `zipfile`, `hashlib`, `subprocess`, `json`, `django.core.serializers` are stdlib/Django; `python-magic` and `django-ratelimit` are already project dependencies.
- Templates follow the existing `manager/add/edit/view` naming convention (`backup/create.html` for trigger, `backup/status.html` for the polled partial), using AdminLTE 3.2 + Bootstrap 4.6 unchanged.

## Cross-Story Dependencies

- Story 1.1 establishes the base trigger/job/subprocess/storage mechanism that 1.2 (scope selection), 1.3 (manifest), 1.4 (date filter), and 1.5 (progress/notification) all extend rather than duplicate.
- Epic 2 (restore) depends entirely on this epic's archive format, manifest schema, and `BackupJob`/subprocess mechanism being correct — it does not depend on Epic 3.
- Epic 3 (history, download, delete, retention) also depends on this epic's `BackupJob` model and storage layout, independent of Epic 2.
