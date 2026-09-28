# Epic 3 Context: Backup History, Download, Delete & Retention

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Admins need visibility into and control over backups already created (by Epic 1): a permission-scoped history list, the ability to download or delete an individual backup within their scope, and an optional system-wide, age-based retention policy a super admin can enable to prune old backups automatically instead of letting them accumulate forever. This epic depends on Epic 1's `BackupJob` records and archive files existing; it is independent of Epic 2 (restore).

## Stories

- Story 3.1: View backup history scoped to my permissions
- Story 3.2: Download a completed backup
- Story 3.3: Delete an individual backup
- Story 3.4: System-wide age-based retention policy

## Requirements & Constraints

- Backup history is scoped to the viewer: an institutional admin sees only their own institution's backups; a super admin sees system-wide backups, including `pre_restore_snapshot` rows (visible to super admins only). List entries show who triggered it, when, size, and scope.
- A backup still `pending`/`running` appears in the list with its current status but is never offered as downloadable yet.
- Download requires authenticated, permission-checked access only — archives are never stored under or served via a publicly-accessible static/media path (this is the primary PHI protection since archives are unencrypted at rest by decision).
- Requesting a download for a `pending`/`running`/`failed` job, or one whose `.zip` has since vanished from disk (e.g. pruned between list render and download), returns a specific "backup not available" error — never an unhandled exception or a partial/corrupt file served as valid.
- Deleting a backup: an institutional admin may delete only their own institution's backups; a super admin may delete any. Deletion removes both the `.zip` on disk and the `BackupJob` row, and is distinct from automatic retention pruning.
- Retention policy is disabled by default — nothing is ever auto-deleted until a super admin explicitly enables it and sets a max-age-in-days value. Only a super admin can configure it.
- The prune sweep runs lazily, only when a super admin loads the backup list (never on an institutional admin's page load, no scheduler/cron). It excludes every `pre_restore_snapshot` row and any backup that is the current source of a `BackupJob` still `pending`/`running`. Age is measured from `completed_at`, not `created_at`.
- Every backup creation, download, and restore action is recorded in the audit trail with acting user, timestamp, and scope; a system-driven prune sweep is logged as a system-attributed entry, never as an individual user's action.

## Technical Decisions

- All history/download/delete/retention logic lives in the existing `backup/` app (`views.py`, `models.py`) — no new app. `BackupJob` and `BackupRetentionPolicy` both inherit `TimeStampedModel` + `UserTrackingMixin`.
- Download reuses the existing `FileResponse` pattern already used for Excel export (`institution/views.py`): `FileResponse(open(path, "rb"), content_type="application/zip")` + `Content-Disposition: attachment`, from a permission-checked view that requires `get_object_or_404(BackupJob, id=pk, status="completed")` before serving.
- Retention lives in a single-row `BackupRetentionPolicy` model (`enabled: bool = False`, `max_age_days: int`), editable by super admin only. No OS cron entry, no Celery beat — the sweep is triggered purely by a super admin's backup-list page load.
- Manual per-backup deletion (Story 3.3) is a separate, permission-gated view, distinct from the automatic age-based prune sweep (Story 3.4) — do not conflate the two code paths.
- Authorization reuses `institution/`'s existing tenant-scoping (`middleware.py`, `context_processors.py`); no parallel permission mechanism.
- Audit trail split by action type: backup **creation** is captured structurally via `BackupJob.triggered_by`/`created_at`, set explicitly by the view (`request.user`) — the same manual pattern used elsewhere in this codebase (`referral/views.py`, `video/views.py`), not an automatic middleware behavior despite how CLAUDE.md's shorthand describes `UserTrackingMixin`. **Download** has no natural model mutation to hang an audit entry on, so it is explicitly logged to `logs/security.log` via the existing dedicated security-event logging convention.
- Every view uses the project's `@handle_view_errors(...)` decorator per existing convention.
- Template naming follows the project's `manager/add/edit/view` convention: `backup/manager.html` is the history/list template (AdminLTE 3.2 + Bootstrap 4.6, unchanged).

## Cross-Story Dependencies

- Epic 3 as a whole depends on Epic 1 (backup creation produces the `BackupJob` rows and `.zip` archives this epic lists, downloads, deletes, and prunes). It does not depend on Epic 2 (restore).
- Story 3.2 (download) and Story 3.3 (delete) both build on the same permission-scoped queryset established in Story 3.1 (institutional admin: own institution only; super admin: system-wide including `pre_restore_snapshot` rows).
- Story 3.4's retention prune sweep executes at the same load point as Story 3.1's list view (triggered only on a super admin's page load), so the two are implemented together in that view.
- `pre_restore_snapshot` rows (created by Epic 2's restore flow) are exempt from Story 3.4's auto-pruning and visible only to super admins in Story 3.1's list — Epic 3 must respect that exemption even though it doesn't create those rows itself.
