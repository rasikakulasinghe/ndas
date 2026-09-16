---
id: SPEC-backup-restore
companions: [professional-options.md]
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Institutional Admin & Super Admin Data Backup/Restore

## Why

NDAS has no data backup or restore capability today; `architecture.md` already names "DB backup strategy" as a deferred gap, and this spec activates that deferred item (a pain to solve + a mandate every production medical-records system needs). Institutional admins and super admins currently have no way to protect against data loss or recover from a mistake, and the existing `institution/` app's tenant-scoping model needs a backup/restore feature that respects it rather than bypassing it. This matters now because the system holds PHI across multiple institutions with no recovery path if data is lost, corrupted, or needs to be moved.

## Capabilities

- **CAP-1**
  - **intent:** An institutional admin or super admin can trigger creation of a backup archive containing their scoped database records, media files, and attachments, with database information exported in human-readable form and media files preserved in their existing organized folder structure (e.g. `{institution}/videos/`, `{institution}/attachments/`) so the archive can be manually browsed without special tooling.
  - **success:** Triggering a backup produces one archive whose database export is readable (not an opaque binary-only dump) and whose media files are laid out in clear per-institution/type subfolders; an institutional admin's archive contains only their institution's data, a super admin's contains system-wide or explicitly selected institution(s) data.

- **CAP-2**
  - **intent:** Every backup archive carries a manifest (schema/app version, included institution(s), record counts, checksums) so a restore can validate compatibility and integrity before applying.
  - **success:** Restoring an archive with a mismatched schema version, an altered checksum, or corrupted contents is rejected with a clear error before any data is modified.

- **CAP-3**
  - **intent:** A super admin can restore data from a previously created backup archive, with the system automatically snapshotting current state before applying the restore. Restore is restricted to super admins only — institutional admins cannot trigger a restore under any circumstance, even for their own institution's data.
  - **success:** A restore completes only after a preview/confirmation step and only when initiated by a super admin; if the restore fails or is cancelled, the automatic pre-restore snapshot can return the system to its prior state; an institutional admin attempting to trigger a restore is denied regardless of scope.

- **CAP-4**
  - **intent:** Backup creation and management (CAP-1, CAP-6) are permitted per the existing institutional-admin/super-admin roles, reusing the `institution/` app's tenant-scoping rather than a parallel mechanism; restore (CAP-3) is further restricted to super admins only, regardless of institution scope.
  - **success:** An institutional admin attempting to back up or manage backups outside their own institution is denied; any institutional admin attempting to trigger a restore — even for their own institution's data — is denied.

- **CAP-5**
  - **intent:** Backup and restore run as background jobs with visible progress and a completion/failure notification, so large media sets never block the requesting user's session.
  - **success:** A backup/restore job over a large dataset (many GB of video) can be started, the admin can navigate away, and later see completion status and be notified without the HTTP request timing out.

- **CAP-6**
  - **intent:** Admins can view backup history scoped to their permissions (who triggered it, when, size, scope), download or delete individual backups within their scope, and the super admin can configure a system-wide retention policy that prunes old backups automatically.
  - **success:** The backup list shows prior backups with metadata scoped to the viewer's permissions; deleting a backup within scope removes the archive; an enabled system-wide retention policy automatically removes backups past its configured threshold.

- **CAP-7**
  - **intent:** Every backup creation, download, and restore action is recorded in the audit trail with the acting user, timestamp, and scope, consistent with the existing `UserActivityMiddleware`/`UserTrackingMixin` pattern.
  - **success:** Reviewing the audit log shows who created or restored a given backup and when.

## Constraints

- Backup archives must never be stored under or served via a publicly-accessible static/media path; download requires authenticated, permission-checked access only — this is the primary protective control for PHI since archives are not encrypted at rest by decision.
- Database information inside the archive must be exported in human-readable form (not an opaque binary-only dump), and media files must preserve the existing per-institution/type folder structure, so the archive can be manually browsed.
- Backup/restore I/O must be implemented as streaming/chunked from the start — no artificial dataset-size cap deferred to "later."
- Backup/restore must run as background/async jobs, not synchronous request-response, given existing file-size limits (2GB video, 100MB doc) multiplied across many records; the specific execution mechanism is an architecture-phase decision.
- Restore is restricted to super admins only; institutional admins may create and manage their own institution's backups but must never be able to trigger a restore.
- A restore archive is itself a file upload and must pass the same MIME/type/size validation as other uploads (the `python-magic` pattern) before being trusted.
- Backup/restore trigger endpoints must be rate-limited per the existing `django_ratelimit` pattern to prevent abuse via repeated large-job triggers.

## Non-goals

- Real-time or continuous data replication / point-in-time recovery — this is snapshot-based backup, not an HA/replication solution.
- Cross-institution data merging during restore — a restore applies only within the scope it was created for.
- Automatic offsite/cloud storage upload (S3, Azure Blob) — deferred to Phase 2; see `professional-options.md`.
- Backup/restore of deployment configuration (Django settings, environment secrets) — already covered separately by `scripts/switch_env.py`; this feature covers application data (DB + media/attachments) only.
- Encryption at rest of backup archives — explicit decision to keep the archive human-browsable; PHI protection instead relies on the storage-path and access-control constraints above.
- Scheduled/automatic backup or restore triggering — every action is always explicitly initiated by an admin; no cron/periodic automation.
- Institutional-admin-initiated restore — restore is exclusively a super-admin operation.

## Success signal

A super admin triggers a full-system backup and an institutional admin triggers a scoped backup of only their own institution's data; the super admin later restores from either archive through a preview-confirm flow with an automatic pre-restore snapshot, and every action appears in the audit trail — demonstrable end-to-end on staging with production-representative media volume, with no Django shell or manual DB intervention required. Unpacking either archive by hand shows a readable database export and a clearly organized media folder structure.

## Assumptions

- Assumed backup format is a single compressed archive per backup event, structured internally with human-readable DB exports and organized media folders rather than an opaque blob, consistent with the no-encryption/manual-browse decision.
- Assumed "attachments" in the request refers to the Document/Image/Video file types already defined in `FILE_UPLOAD_LIMITS`, not a new attachment type.
- Assumed the specific async execution mechanism for admin-triggered backup/restore jobs (Celery, background thread, OS-scheduled management command) is an architecture-phase decision; the no-automatic-scheduling decision removes the need for a recurring-job scheduler specifically, but non-blocking execution is still required per Constraints.

## Open Questions

- What should the default system-wide retention values be (keep last N backups, max age in days, or both) for the super-admin-controlled retention policy?
