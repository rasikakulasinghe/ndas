---
id: SPEC-backup-restore
companions: [professional-options.md, ../../planning-artifacts/architecture/architecture-backup-restore/ARCHITECTURE-SPINE.md]
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Institutional Admin & Super Admin Data Backup/Restore

## Why

NDAS has no data backup or restore capability today; `architecture.md` already names "DB backup strategy" as a deferred gap, and this spec activates that deferred item (a pain to solve + a mandate every production medical-records system needs). Institutional admins and super admins currently have no way to protect against data loss or recover from a mistake, and the existing `institution/` app's tenant-scoping model needs a backup/restore feature that respects it rather than bypassing it. This matters now because the system holds PHI across multiple institutions with no recovery path if data is lost, corrupted, or needs to be moved. (Admins may refer to this colloquially as data export/import — export = backup, import = restore.)

## Capabilities

- **CAP-1**
  - **intent:** An institutional admin or super admin can trigger creation of a backup packaged as a single downloadable `.zip` file containing their scoped database records, media files, and attachments. Scope is institution-based as today, with an optional additional filter to a specific date or date range applied against patient profile creation date: when set, only patients whose profile was created within that window are included, but every related record for each included patient (assessments, videos, attachments, etc.) is exported in full regardless of that related record's own date, so no included patient's data is exported partially. Omitting the date filter exports the full institution-scoped set as today. Database information is exported into a single consolidated JSON file (not split per model/table), and media files are preserved in their existing organized folder structure (e.g. `{institution}/videos/`, `{institution}/attachments/`) so the archive can be manually browsed without special tooling.
  - **success:** Triggering a backup produces one `.zip` containing exactly one JSON file with the scoped database export and a media folder laid out in clear per-institution/type subfolders; an institutional admin's `.zip` contains only their institution's data, a super admin's contains system-wide or explicitly selected institution(s) data; when a date/date-range filter is applied, the JSON and media both contain only patients created in that window plus every one of each such patient's related records in full, and omitting the filter exports the full available scope.

- **CAP-2**
  - **intent:** Every backup archive carries a manifest (schema/app version, included institution(s), record counts, checksums, and whether a date/date-range filter was applied and its bounds) so a restore can validate compatibility, integrity, and scope before applying.
  - **success:** Restoring an archive with a mismatched schema version, an altered checksum, or corrupted contents is rejected with a clear error before any data is modified; the manifest correctly reflects whether the archive is full-scope or date-scoped.

- **CAP-3**
  - **intent:** A super admin can restore data by uploading a previously downloaded backup `.zip` file — whether a full-scope or date-scoped (partial) archive — with the system automatically snapshotting current state before applying. When restoring a date-scoped archive, any patient in the archive that already exists in the target system is skipped in full together with all of that patient's related records, leaving the existing live patient untouched; only patients not already present are imported, each with its complete set of related records. Restore is restricted to super admins only — institutional admins cannot trigger a restore under any circumstance, even for their own institution's data.
  - **success:** A restore completes only after the super admin uploads the `.zip` and confirms a preview step; for a date-scoped archive, the preview lists which patients will be skipped as already-existing and which will be imported; if the restore fails or is cancelled, the automatic pre-restore snapshot can return the system to its prior state; an institutional admin attempting to trigger a restore is denied regardless of scope.

- **CAP-4**
  - **intent:** Backup creation and management (CAP-1, CAP-6) are permitted per the existing institutional-admin/super-admin roles, reusing the `institution/` app's tenant-scoping rather than a parallel mechanism; restore (CAP-3) is further restricted to super admins only, regardless of institution scope.
  - **success:** An institutional admin attempting to back up or manage backups outside their own institution is denied; any institutional admin attempting to trigger a restore — even for their own institution's data — is denied.

- **CAP-5**
  - **intent:** Backup and restore run as background jobs with visible progress and a completion/failure notification, so large media sets never block the requesting user's session.
  - **success:** A backup/restore job over a large dataset (many GB of video) can be started, the admin can navigate away, and later see completion status and be notified without the HTTP request timing out.

- **CAP-6**
  - **intent:** Admins can view backup history scoped to their permissions (who triggered it, when, size, scope), download the `.zip` or delete individual backups within their scope, and the super admin can optionally enable a system-wide, age-based retention policy (max age in days) that prunes old backups automatically. The policy is disabled by default — nothing is auto-deleted until a super admin explicitly turns it on and sets a value.
  - **success:** The backup list shows prior backups with metadata scoped to the viewer's permissions; deleting a backup within scope removes the `.zip`; with the policy left at its default (disabled), no backup is ever auto-deleted; once a super admin enables it with a max-age value, backups older than that age are automatically removed.

- **CAP-7**
  - **intent:** Every backup creation, download, and restore action is recorded in the audit trail with the acting user, timestamp, and scope, consistent with the existing `UserActivityMiddleware`/`UserTrackingMixin` pattern.
  - **success:** Reviewing the audit log shows who created or restored a given backup and when.

## Constraints

- Backup archives must never be stored under or served via a publicly-accessible static/media path; download requires authenticated, permission-checked access only — this is the primary protective control for PHI since archives are not encrypted at rest by decision.
- Media files inside the archive must preserve the existing per-institution/type folder structure, so the archive can be manually browsed.
- Backup/restore I/O must be implemented as streaming/chunked from the start — no artificial dataset-size cap deferred to "later."
- Backup/restore must run as background/async jobs, not synchronous request-response, given existing file-size limits (2GB video, 100MB doc) multiplied across many records; the specific execution mechanism is an architecture-phase decision.
- Restore is restricted to super admins only; institutional admins may create and manage their own institution's backups but must never be able to trigger a restore.
- An uploaded restore `.zip` is itself a file upload and must pass the same MIME/type/size validation as other uploads (the `python-magic` pattern) before being trusted, and must pass CAP-2's manifest/checksum validation before any data is touched.
- Backup/restore trigger endpoints must be rate-limited per the existing `django_ratelimit` pattern to prevent abuse via repeated large-job triggers.
- The database portion of an export archive must be a single consolidated JSON file, not split per model/table — this is a user-visible contract requirement, not an implementation detail left open to the architecture phase.
- On a date-scoped (partial) restore, a patient already present in the target system must be skipped in full together with all of that patient's related records — never field-level merged or overwritten — and the preview step must enumerate every patient that will be skipped before the admin can confirm.

## Non-goals

- Real-time or continuous data replication / point-in-time recovery — this is snapshot-based backup, not an HA/replication solution.
- Cross-institution data merging during restore — a restore applies only within the scope it was created for.
- Automatic offsite/cloud storage upload (S3, Azure Blob) — deferred to Phase 2; see `professional-options.md`.
- Backup/restore of deployment configuration (Django settings, environment secrets) — already covered separately by `scripts/switch_env.py`; this feature covers application data (DB + media/attachments) only.
- Encryption at rest of backup archives — explicit decision to keep the archive human-browsable; PHI protection instead relies on the storage-path and access-control constraints above.
- Scheduled/automatic backup or restore triggering — every action is always explicitly initiated by an admin; no cron/periodic automation.
- Institutional-admin-initiated restore — restore is exclusively a super-admin operation.

## Success signal

A super admin triggers a full-system backup and an institutional admin triggers a scoped backup of only their own institution's data, each downloading a `.zip`; the super admin later restores by uploading either `.zip` through a preview-confirm flow with an automatic pre-restore snapshot, and every action appears in the audit trail — demonstrable end-to-end on staging with production-representative media volume, with no Django shell or manual DB intervention required. Unpacking either `.zip` by hand shows a single readable JSON database export and a clearly organized media folder structure. A super admin also creates a date-range-scoped export limited to patients created in that window and later restores it: a patient already present in the target system is skipped in full while new patients import with their complete related records, both visible in the restore preview before confirmation.

## Assumptions

- Assumed "attachments" in the request refers to the Document/Image/Video file types already defined in `FILE_UPLOAD_LIMITS`, not a new attachment type.
- Assumed the specific async execution mechanism for admin-triggered backup/restore jobs (Celery, background thread, OS-scheduled management command) is an architecture-phase decision; the no-automatic-scheduling decision removes the need for a recurring-job scheduler specifically, but non-blocking execution is still required per Constraints.
- Assumed "single JSON file" means one JSON document containing all in-scope models/records (e.g. keyed by `app_label.model_name`); the exact internal JSON shape is an architecture-phase decision.
- Assumed conflict-detection during a partial restore matches patients on whichever unique identifier they have populated (`bht`, `nnc_no`, `ptc_no`, `pc_no`, or `pin` — all unique-if-set on `Patient`), not internal DB primary key, since a restored patient's live PK may differ across environments. A match on any one of the five is a conflict; a patient with none of the five set cannot be matched and is always treated as new (accepted residual risk of an eventual duplicate) — resolved by the architecture pass rather than left open.
