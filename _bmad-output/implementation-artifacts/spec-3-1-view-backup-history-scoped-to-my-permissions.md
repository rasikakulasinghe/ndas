---
title: 'Story 3.1: View backup history scoped to my permissions'
type: 'feature'
created: '2026-09-28'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '92a1dc2adf74951c68118c284c1eaa12eebd2f4b'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Admins have no full view of past backups. The only existing listing (Story 1.5's "Recent Backup Jobs" widget on the trigger page) caps at 10 rows, mis-scopes a super admin to `scope=institution OR triggered_by=me` (not system-wide), never shows who triggered a job or its scope, and has no notion of downloadable vs not.

**Approach:** A new, dedicated, paginated backup-history page reusing the existing `backup/` app, correctly scoped by permission: an institutional admin sees every `BackupJob` whose scope covers their institution (single, multi, or system-wide); a super admin sees every `BackupJob` system-wide, including `pre_restore_snapshot` rows. Each row shows who triggered it, when, size, scope and status; a row not yet `completed` is visibly not downloadable (the download link itself is Story 3.2).

## Boundaries & Constraints

**Always:**
- **Scope.** `job_type` in `{backup, pre_restore_snapshot}` only (a `restore` job has no archive of its own to list; it is covered by Story 2.6's audit trail). Institutional admin (`UserType.ADMIN`): jobs whose scope covers their institution -- `scope_type='single' AND scope=institution`, or `scope_type='multi' AND institution in scopes`, or `scope_type='system'`. An institutional admin never sees a `pre_restore_snapshot` row (AD-14: super-admin-only, regardless of scope match). Super admin (`UserType.SUPERADMIN`): every matching job, unfiltered, including every `pre_restore_snapshot` row.
- **Columns.** Who triggered it (`triggered_by.username`, or "System" when null -- a deleted user), when (`created_at`; no `completed_at` field exists on `BackupJob` yet), size, and scope (single institution's name, the multi set's names, or "System-wide"). A `pending`/`running` job shows its live status and progress but no size (unknown until the archive is finalized) and is visibly not downloadable; a `failed` job shows no size either. A `completed` job's size is read from the archive file on disk (`backup/services.py:get_archive_path`) at render time, once per row; when the file is missing (e.g. pruned since the list was last loaded) the row shows "unavailable" instead of a size or a broken download affordance.
- **Pagination.** `django.core.paginator.Paginator`, page size 25 (the project's existing convention for list-heavy admin pages), newest first (`-created_at`).
- **Template.** New `backup/templates/backup/manager.html` (the project's `manager/add/edit/view` naming), extending `src/base.html`, AdminLTE 3.2 + Bootstrap 4.6 unchanged. New view `backup_history` in `backup/views.py`, URL `backup/history/` named `backup:backup-history`. Reuses `institution/`'s tenant-scoping (`request.institution`) exactly as `backup_create`/`backup_status` already do; no parallel permission mechanism.
- **Access.** `UserType.ADMIN` or `UserType.SUPERADMIN` only (same gate as the existing backup views); a non-admin is redirected home. `@login_required`, `@require_GET`, `@handle_view_errors`.

**Ask First:** None -- the job-type scope (excluding `restore` rows), the page size, and computing size from disk rather than adding a field are this spec's own calls, flagged in Design Notes.

**Never:**
- No change to the existing Story 1.5 "Recent Backup Jobs" widget, its route, or its own (narrower) scoping -- it stays as the trigger page's own live-activity glance; this story adds a separate, full history page.
- No download link, no delete action, no retention policy (Stories 3.2-3.4). No new model, no new field on `BackupJob`.
- No restore job rows (`job_type='restore'`) in this list.

## I/O & Edge-Case Matrix

| Scenario | Behaviour |
|----------|-----------|
| Institutional admin, single-scope backup of their institution | Shown |
| Institutional admin, multi-scope backup that includes their institution | Shown |
| Institutional admin, system-wide backup | Shown |
| Institutional admin, another institution's single-scope backup | Not shown |
| Institutional admin, any `pre_restore_snapshot` row | Not shown, even if its scope covers their institution |
| Super admin | Every `backup`/`pre_restore_snapshot` job system-wide, including every `pre_restore_snapshot` |
| Job `pending` or `running` | Shown with live status/progress, no size, not downloadable |
| Job `failed` | Shown with status, no size |
| Job `completed`, archive file present | Size read from disk |
| Job `completed`, archive file missing from disk | Row shows "unavailable" instead of a size |
| `triggered_by` user deleted (`SET_NULL`) | Row shows "System" |
| No backups in scope | Empty-state row, same wording style as the existing widget's `{% empty %}` |
| More than one page of results | Paginated, 25 per page, newest first |
| Non-admin user requests the page | Redirected home, no data leaked |

</frozen-after-approval>

## Code Map

- `backup/views.py:176` (`_recent_jobs_for`) -- the Story 1.5 widget's own scoping (10-row cap, `scope=institution OR triggered_by=user` for a super admin); read as precedent only, do not modify or reuse its queryset (it under-scopes multi-institution jobs for an institutional admin and over-restricts a super admin). New `_history_jobs_for(institution, is_superadmin)` beside it.
- `backup/views.py:50` (`_get_admin_institution`), `:242` (`backup_create`, the gate pattern: `UserType.ADMIN`/`SUPERADMIN` check, redirect home otherwise) -- reuse verbatim for the new `backup_history` view.
- `backup/models.py:11` (`BackupJob`): `job_type`, `status`, `scope`/`scope_type`/`scopes` (Story 1.2), `triggered_by` (`SET_NULL`), `created_at`/`updated_at` (from `TimeStampedModel`); no `size_bytes` or `completed_at` field exists on `BackupJob` (only `RestoreUpload` has `size_bytes` -- a planning/implementation discrepancy already noted in `epic-2-context.md`).
- `backup/services.py:44` (`get_backup_dir`), `:47` (`get_archive_path`) -- `BASE_DIR/backups/<job_id>/<job_id>.zip`; stat this path for the size column, catching `OSError`/`FileNotFoundError`.
- `backup/templates/backup/status.html` -- the widget's status-badge and job-type-badge markup (`pending`/`running`/`completed`/`completed with warnings`/`failed`) is the precedent to match visually; do not alter this file.
- `backup/urls.py` -- add `path('history/', views.backup_history, name='backup-history')`.
- `ndas/custom_codes/choice.py:246` (`BackupJobType`), `:195` (`UserType`) -- reuse as-is.
- Facts (verified): `institution/middleware.py` sets `request.institution` (or `None`); `Institution` has no soft-delete visible to this query path; `patients/views.py` uses `Paginator(..., 25)` for a comparable admin list as the closest size precedent; `BackupJob.scopes` is unordered M2M (order with `.order_by('name')` for display).

## Tasks & Acceptance

**Execution:**
- [x] `backup/views.py` -- `_history_jobs_for`, `backup_history` view (gate, paginate, render).
- [x] `backup/urls.py` -- `backup:backup-history` route.
- [x] `backup/templates/backup/manager.html` -- the history table (columns, badges, pagination controls, empty state), matching AdminLTE conventions.
- [x] Tests for every matrix row: institutional-admin single/multi/system scoping, `pre_restore_snapshot` exclusion for an institutional admin and inclusion for a super admin, `restore` job-type exclusion, size-from-disk with a missing file, deleted `triggered_by`, pagination, non-admin redirect.

**Acceptance Criteria:**
- Given an institutional admin views the backup list, when it loads, then only backups whose scope covers their institution are shown, with who triggered it, when, size, and scope.
- Given a super admin views the backup list, when it loads, then backups are shown system-wide, including `pre_restore_snapshot` rows.
- Given a backup that is still `pending` or `running`, when it appears in the list, then it is shown with its current status but not offered as downloadable.

## Spec Change Log

**Review pass 1 (three layers: blind-hunter, edge-case-hunter, verification-gap).** Triage produced no `intent_gap` and no `bad_spec` finding, so the frozen block was not changed and no loopback was needed; `review_loop_iteration` stays 0. Patch findings, fixed in one pass:

- A real bug: the pagination widget's left ellipsis marker didn't mirror the right one, so one page number could be silently dropped from the page list with no link and no "…" to mark the gap. Fixed to be symmetric; a regression test walks a 10-page run and asserts no page is ever silently missing.
- Deterministic ordering (`-created_at, -id` tiebreak), the missing `@ratelimit` on the new view (matching its GET siblings), a docstring that read as self-contradictory, a test assertion that was always true regardless of the code under test (replaced with one that fails on a real regression), and two small accessibility attributes.
- One coverage addition: a test for the "Full History" link on the trigger page.
- Deviation from the patch instruction, accepted: P4 asked for the `default_if_none` filter for the deleted-`triggered_by` fallback; the agent found (and verified against Django's template-resolution code) that a chained `None.username` lookup raises before any filter runs, so `default_if_none` would never fire and the fallback would silently regress to a blank cell. It used `{% if job.triggered_by %}...{% else %}System{% endif %}` instead, which checks the real condition ("null FK", not "falsy username") and is covered by the existing `deleted_triggered_by` test.
- Rejected as noise or already decided by the spec: a download link, a delete action, and a failure-message display (all Story 3.2/out of scope by the frozen "Never" list); a report of "invalid diff hunks" (an artifact of how the review diff was assembled, not a code issue); broadening the size-lookup exception handling beyond `OSError` (the spec's Code Map names that catch explicitly, and `get_archive_path` cannot raise otherwise here).
- Deferred (see `deferred-work.md`): the history page shows only a status badge, not the failure/warning text `status.html` already shows for the same jobs; the page's only entry point is the one link on the trigger page, no sidebar/menu entry; no query-count regression test and no end-to-end assertion of the exact multi-scope column text or header wording.

**Verification.** The patch agent's own full `backup` suite run: 655/655, clean `makemigrations --check`. Confirmed independently: 655 tests, OK, 833s (background run), and `makemigrations --check --dry-run backup` clean.

## Design Notes

- **Job-type scope excludes `restore`.** The epic's AC and CAP-6 both say "backup", not "restore" -- a `restore` job applies an archive rather than producing a downloadable one of its own; it has no `.zip` under `backups/`. Restore's own audit and status live in Story 2.6 and its status page. **Needs approval at the checkpoint.**
- **Size computed from disk, not a new field.** `BackupJob` never got a `size_bytes` field (unlike `RestoreUpload`, which has one from Story 2.1). Adding one now would need a migration and a backfill for every past job; reading the file at render time is exact and needs neither, at the cost of one stat call per completed row on a 25-row page. **Needs approval at the checkpoint.**
- **Separate page, not a widened widget.** Story 1.5's fragment is a small, actively-polled "what's running right now" glance embedded in the trigger page; retrofitting pagination, full permission scoping and new columns onto it would change its polling behaviour and layout for a purpose it wasn't built for. **Needs approval at the checkpoint.**

## Verification

**Commands:**
- `venv/Scripts/python.exe manage.py test backup --noinput` (background; one run at a time) -- all pass, including the new history tests. Confirmed independently: 655 tests, OK, 833s.
- `venv/Scripts/python.exe manage.py makemigrations --check --dry-run backup` -- no changes. Confirmed independently.
