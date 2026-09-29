---
title: 'Story 3.2: Download a completed backup'
type: 'feature'
created: '2026-09-28'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'b7fbc0519dc3468867221c919aa7b1b9aa4e2002'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 3.1's history page lists backups with a size column but no way to actually retrieve one -- an admin who wants an off-system copy or to inspect an archive manually has no path to it.

**Approach:** A permission-checked download view, scoped exactly like Story 3.1's history list, streams a completed backup's `.zip` via the project's existing `FileResponse` pattern (the Excel-export precedent). A job that isn't `completed`, or whose archive is missing from disk, gets a specific, friendly refusal -- never an unhandled exception or a partial/corrupt file. Every download is logged to `logs/security.log`.

## Boundaries & Constraints

**Always:**
- **View and scope.** New `backup_download(request, pk)`, URL `backup/history/<int:pk>/download/`, name `backup:backup-download`. Same `UserType.ADMIN`/`SUPERADMIN` gate as `backup_history` (non-admin or no institution context -> redirect home, no data leaked). The row must come from `_history_jobs_for(institution, is_superadmin)` (Story 3.1's exact scoped queryset -- same job-type exclusion, same institution/multi/system coverage, same `pre_restore_snapshot` super-admin-only rule) filtered to `status=completed`, via `get_object_or_404`, per AD-7. A `pk` outside the viewer's scope, of the wrong status, or that does not exist is indistinguishable: plain 404, no information about why.
- **Streaming.** `FileResponse(open(get_archive_path(job), 'rb'), content_type='application/zip')` + `Content-Disposition: attachment; filename="..."` -- the exact shape AD-7 names (matches `institution/views.py`'s Excel-export precedent). The filename is server-constructed from the job's own fields only (id, type, created date) -- never from user input.
- **Vanished archive.** `get_object_or_404` can confirm the job row is `completed` but not that the `.zip` still exists on disk (Story 3.1 already handles this for the list's size column). Opening the file for the response is wrapped so a missing or unreadable archive (`OSError`) never reaches the client as a raw exception or a truncated stream: the request is refused with a message naming the backup as no longer available, and the admin is sent back to the history page. Nothing on disk is modified.
- **Logging.** Every download attempt through this view writes one line to `logs/security.log` (`django.security` logger family, matching the restore views' convention): a successful stream (INFO, actor + job id + archive size) and a refusal -- non-admin, wrong status/out-of-scope/unknown pk, or vanished archive (WARNING, actor + job id + reason). This is the audit trail AD-7/CAP-7 require for download, since it has no model mutation of its own to hang an entry on.
- **Rate limit.** `@ratelimit(key='user_or_ip', rate='30/m')`, matching the other read-only GET views in this file (`restore_status`, `restore_preview`, the new `backup_history`).
- **List integration.** `backup/templates/backup/manager.html` gains a download link/button on each row whose `job.status == 'completed'` and `job.archive_size_bytes is not None` (Story 3.1's own missing-archive signal); a `pending`/`running`/`failed` row, or a `completed` row already showing "unavailable", shows no download affordance, matching Story 3.1's own "not offered as downloadable" language.

**Ask First:** None -- the split between AD-7's literal `get_object_or_404(status="completed")` (a plain 404 for wrong-status/out-of-scope/unknown) and an explicit friendly refusal only for the vanished-archive case is this spec's own call, flagged in Design Notes.

**Never:**
- No change to `_history_jobs_for`, Story 3.1's scoping rules, or `manager.html`'s existing columns beyond adding the download affordance.
- No delete action, no retention policy (Stories 3.3-3.4). No new model or field.
- No archive ever served from a publicly-accessible static/media path; no bypass of the `completed`-status or scope filter for any role, including super admin (a super admin still only downloads what `_history_jobs_for` returns them).

## I/O & Edge-Case Matrix

| Scenario | Behaviour |
|----------|-----------|
| Completed backup within the admin's scope | `.zip` streamed via `FileResponse`, `Content-Disposition: attachment`; one INFO log line |
| Completed `pre_restore_snapshot`, super admin | Streamed (super admin only, per AD-14 -- an institutional admin's scoped queryset never contains this row, so it 404s for them) |
| Job `pending`, `running`, or `failed` | 404 (never offered as downloadable; matches Story 3.1) |
| Job's `.zip` missing from disk (pruned/moved externally) | Friendly refusal, redirect to history page, no exception, no partial file; one WARNING log line |
| `pk` belongs to another institution's job (institutional admin) | 404, no information leaked about the job's existence |
| `pk` is a `restore` job or does not exist | 404 |
| Non-admin, or admin with no institution context | Redirected home, same as `backup_history`; one WARNING log line |
| Two downloads of the same archive | Each served independently; the file is never modified or moved by a download |

</frozen-after-approval>

## Code Map

- `backup/views.py:192` (`_history_jobs_for`) -- reuse verbatim as the base queryset for `get_object_or_404`; do not duplicate its scoping logic. `:483` (`backup_history`, the gate pattern and the `archive_size_bytes`/missing-archive convention) -- mirror the gate; the new view sits beside it.
- `backup/services.py:44` (`get_archive_dir`), `:47` (`get_archive_path`) -- `BASE_DIR/backups/<job_id>/<job_id>.zip`; open this path for the response, catching `OSError`.
- `institution/views.py:456` (`superadmin_reports`, the `FileResponse(open(...), content_type=...)` + `Content-Disposition` block) -- the exact precedent AD-7 names; match its shape, not its content type.
- `backup/urls.py` -- add `path('history/<int:pk>/download/', views.backup_download, name='backup-download')`, beside the `backup-history` route.
- `backup/restore_validation.py` (`security_logger = logging.getLogger('django.security.restore')`) and `backup/views.py:47` (`security_logger = restore_validation.security_logger`) -- reuse the existing module-level `security_logger` for both the success and refusal log lines (a new, download-specific child logger under `django.security` is fine if clearer, but must stay under the `django.security` family so it reaches `security.log`).
- `backup/templates/backup/manager.html` -- add the download link inside the existing per-row markup, gated on `job.status == 'completed' and job.archive_size_bytes is not None`.
- `ndas/custom_codes/choice.py:254` (`BackupJobStatus`) -- reuse `COMPLETED` as-is.
- Facts (verified): `BASE_DIR/backups/` is distinct from `MEDIA_ROOT` (`BASE_DIR/media`) and `STATIC_ROOT` (`BASE_DIR/staticfiles`) -- already non-public; `FileResponse` closes its wrapped file object automatically, no explicit `close()` needed (matches the Excel-export precedent, which does not call it either); no existing scope-label/friendly-filename helper exists in `backup/` -- the filename is built from the job's own `id`/`job_type`/`created_at` only.

## Tasks & Acceptance

**Execution:**
- [x] `backup/views.py` -- `backup_download` view (gate, scoped lookup, stream-or-refuse, log both outcomes).
- [x] `backup/urls.py` -- `backup:backup-download` route.
- [x] `backup/templates/backup/manager.html` -- the per-row download link/button, correctly gated.
- [x] Tests for every matrix row: happy path (institutional admin and super admin), `pre_restore_snapshot` download by super admin and its 404 for an institutional admin, non-`completed` statuses 404, out-of-scope job 404, missing archive on disk (friendly refusal, no exception), non-admin/no-institution-context redirect, both log lines (`assertLogs`), rate limit.

**Acceptance Criteria:**
- Given a completed backup within an admin's scope, when they request the download, it is returned via `FileResponse` from a view scoped the same as Story 3.1.
- Given a backup that is `pending`, `running`, or `failed`, or whose `.zip` has vanished from disk, when a download is requested, a specific "backup not available" outcome is returned -- never an unhandled exception or a partial/corrupt file served as valid.
- Given a download occurs, when it completes, it is logged to `logs/security.log`.

## Spec Change Log

**Review pass 1 (three layers: blind-hunter, edge-case-hunter, verification-gap).** Triage produced no `intent_gap` and no `bad_spec` finding, so the frozen block was not changed and no loopback was needed; `review_loop_iteration` stays 0. Patch findings, fixed in one pass:

- A real bug, caught independently by two reviewers: a rare `os.fstat` failure right after a successful `open()` left the file handle unclosed. Fixed, with a test that forces the failure and asserts the handle closes.
- A real, confirmed coverage gap: nothing rendered `manager.html` and asserted the new Download link's per-row gating, so the gate could regress silently in either direction. Three tests added, rendering the real page through `backup_history`.
- Hardening: `Cache-Control: no-store, private` on the archive response; the refusal log now distinguishes a genuine existence-check failure (`exists=unknown`) from a clean "no such job" (`exists=False`), instead of folding both into the same value.
- Coverage: 405 on a non-GET request; `Content-Length` asserted against the archive's actual size.
- Polish: `job.pk`/`job.id` unified to `job.id`; a stray extra blank line removed.
- Rejected as noise or already decided by the spec/Code Map: a persisted DB audit row (frozen "Never" list forbids a new model); checksum/integrity validation before streaming (not in the AC); reusing `_history_jobs_for` wholesale for the single-row lookup (the Code Map explicitly directs reuse, not a new lighter query); the non-`Http404` exception bypassing `handle_view_errors` (traced against the codebase: this is the pre-existing `restore_status`/`_own_upload_or_404` pattern, not a regression this story introduced).
- Deferred (see `deferred-work.md`): no persisted, queryable audit row for downloads; no archive integrity check before streaming; the shared `django.security.restore` logger now also carries backup-download lines; a TOCTOU gap between opening and streaming the archive, relevant to Stories 3.3/3.4's future delete/prune; the systemic undecorated-`handle_view_errors` pattern; a stale rate-limit count in CLAUDE.md.

**Verification.** The patch agent's own full `backup` suite run: pass, clean `makemigrations --check`. Confirmed independently: 676 tests, OK, 1385s (background run), and `makemigrations --check --dry-run backup` clean.

## Design Notes

- **404 for wrong-status/out-of-scope, a friendly redirect only for a vanished archive.** AD-7's literal mechanism (`get_object_or_404(..., status="completed")`) already gives a clean, information-safe 404 for "not completed" and "not in my scope" in one step -- that's the natural, secure default for those cases (no hint whether the id belongs to someone else's job or doesn't exist at all). The vanished-archive case is different: the job row itself confirms the backup is real and completed, so a bare 404 there would misleadingly suggest the job doesn't exist; a message naming the backup as no longer available is more honest and matches the epic's "specific... error" wording. **Needs approval at the checkpoint.**
- **Filename kept simple.** No scope-name/institution-slug is included in the downloaded filename (unlike the Excel export's institution-slug naming) -- there's no existing scope-label helper for `BackupJob`, and building one is unrelated surface area for a story that only needs a working download link. A later story can improve it without touching this one's behaviour.

## Verification

**Commands:**
- `venv/Scripts/python.exe manage.py test backup --noinput` (background; one run at a time) -- all pass, including the new download tests. Confirmed independently: 676 tests, OK, 1385s.
- `venv/Scripts/python.exe manage.py makemigrations --check --dry-run backup` -- no changes (no model changes in this story). Confirmed independently.
