# Professional/Enterprise Backup Options (Candidate, Beyond v1)

Catalog of enhancements that turn the CAP-1..CAP-7 baseline into a production-grade, enterprise-credible backup component. None of these are committed capabilities — each is a candidate for a later spec update once its matching Open Question in `SPEC.md` is resolved. Grouped by concern so architecture/PRD work can pull in whole groups at once.

## Storage & transport

- **Offsite/cloud target** — push archives to S3-compatible or Azure Blob storage in addition to (or instead of) local disk, for disaster recovery if the server itself is lost. Ties to the offsite-storage Open Question.
- **Compression tuning** — configurable compression level/algorithm (e.g. zstd vs gzip) to trade archive size against backup/restore speed for large media sets.
- **Incremental/differential backups** — after the first full backup, subsequent runs capture only changed records/files, cutting storage and job duration for frequent backups.
- **Chunked/streamed transfer** — for very large institutions, stream the archive in parts rather than building one file in memory/disk, avoiding a single point-of-failure on a multi-GB job.

## Security & compliance

- **Encryption at rest** — encrypt the archive itself (not just the storage volume), so a leaked archive file is not directly readable. Ties to the encryption Open Question.
- **Encryption in transit** — signed URLs or authenticated streaming for download, never a raw static link.
- **Per-institution or per-backup access keys** — separate decryption/access credentials per institution so a super admin's system-wide backup key can't unlock an individual institution's isolated archive on its own if scoped that way.
- **Compliance-oriented retention proof** — a tamper-evident log entry (hash chain) proving a backup existed and was not altered, useful for audit/regulatory review.

## Scheduling & automation

- **Scheduled backups** — nightly/weekly automatic backups per institution or system-wide, configurable by super admin (and optionally by institutional admin for their own scope). Ties to the scheduling Open Question.
- **Pre-migration/pre-deploy auto-backup** — trigger an automatic backup before a risky operation (e.g. a schema migration in production), similar to the existing `switch_env.py` backup-before-overwrite pattern already used elsewhere in this repo.
- **Retention policy automation** — auto-prune backups by age or count once a policy is configured, rather than requiring manual deletion.

## Reliability & verification

- **Test-restore verification** — periodically restore a backup into an isolated sandbox environment automatically, to prove backups are actually restorable rather than trusting they succeeded silently.
- **Manifest-driven compatibility check** — block a restore attempt across incompatible app/schema versions before any data is touched (already captured as CAP-2, listed here as the anchor for the deeper "restore rehearsal" idea above).
- **Partial/selective restore** — restore a subset of an archive (e.g. one patient record, one institution within a system-wide backup) instead of an all-or-nothing restore.

## Observability & UX

- **Progress bar with ETA** — live progress reporting for long-running backup/restore jobs (builds on CAP-5's async execution).
- **Email/in-app notification on completion or failure** — so an admin doesn't need to keep the tab open (builds on CAP-5).
- **Backup size/duration estimation before trigger** — show an admin an estimate before they commit to a large job.
- **Downloadable backup report/manifest summary (PDF)** — human-readable summary of what a given backup contains, for record-keeping outside the system itself.

## Governance & retention

- **Role-gated retention policy control** — decide (per the matching Open Question) whether institutional admins can set their own institution's retention policy or whether it is system-wide/super-admin-only.
- **Storage quota per institution** — cap how much backup storage an institution can consume, with a warning before the cap blocks new backups.
- **Legal hold** — flag a specific backup as exempt from retention pruning (e.g. during litigation or an active investigation), independent of the normal retention policy.
