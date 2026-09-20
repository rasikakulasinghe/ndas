---
title: 'Story 1.5: Progress visibility and completion notification'
type: 'feature'
created: '2026-09-20'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '6bbcf69bbdca2247f52143a664a06dd3f1ac1d72'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A triggered backup runs in a detached subprocess, but the backup page only shows a static snapshot of each job — the admin must manually reload to see progress, and if they navigate away nothing tells them when the job finishes or fails.

**Approach:** Turn the "Recent Backup Jobs" table into an HTMX-polled partial that shows a live progress bar and stops polling once nothing is active; when `run_backup` reaches a terminal state, create an in-app notification (the existing `referral`-app `Notification`, shown in the navbar bell) for the user who triggered the job.

## Boundaries & Constraints

**Always:**
- The polled partial (`backup/status.html`) replaces the inline jobs table in `create.html`, and reuses the existing `_recent_jobs_for` visibility rules — an admin sees only their institution's jobs, a superadmin also sees the jobs they triggered. The status endpoint applies the same `ADMIN`/`SUPERADMIN` permission gate as `backup_create`, returning an empty `403` (not a redirect) on failure, since its response is swapped into a page fragment.
- Polling stops on its own: the partial's root element carries `hx-get`/`hx-trigger="every 5s"`/`hx-swap="outerHTML"` **only while at least one listed job is `pending` or `running`**; once none are, the re-rendered fragment carries no trigger and polling ends. No client-side JS beyond htmx attributes.
- The status endpoint is polled far more often than the project's default `10/m` limit allows, so it uses its own higher `@ratelimit` (`30/m`); `backup_create` keeps `10/m`.
- The progress bar shows `progress_pct`; a `running` job at `>= 99%` shows a "Finalizing (verifying archive)…" label, because the whole-archive checksum runs after the last progress update. A `completed` job with a non-empty `error_message` (skipped media, Story 1.1's "complete with a warning") renders as a warning; a `failed` job renders its error as an error.
- `run_backup` creates the notification only **after** the terminal `BackupJob` save (status + `progress_pct` already written together in one save, unchanged), for every terminal outcome it drives: completed (clean or with skipped media → `BACKUP_COMPLETED`) and failed, including "failed to start" (`BACKUP_FAILED`).
- Notification creation lives in a new `backup/notifications.py` (`notify_job_finished(job)`), called only from `run_backup`. It is strictly best-effort: any exception is caught and logged and must never change the job's terminal state or make the command fail.
- `NotificationType` (in `ndas/custom_codes/choice.py`) gains `BACKUP_COMPLETED` and `BACKUP_FAILED`. The notification's recipient is `job.triggered_by`; its `link` is `reverse('backup:backup-create')` (the existing notification mark-read view redirects there); its `institution` is the institution context the job was triggered from.
- `BackupJob` gains a nullable `trigger_institution` FK (`SET_NULL`), set by `backup_create` on every job it creates. The bell and panel only list notifications for the user's *active* institution, and `Notification.institution` is required, so a super admin's multi-institution or system-wide job (`scope=None`) needs this to deliver to the institution they triggered from. Delivery institution is `trigger_institution`, falling back to `scope` for older jobs that predate the field.
- If no recipient (`triggered_by` is `NULL`) or no institution can be resolved, skip the notification silently apart from a log line.

**Ask First:** None — the polling shape, notification type names, and delivery-institution rule above are decided from epic-1-context.md plus the existing bell's institution-scoping constraint.

**Never:**
- No change to how `progress_pct` is computed (0–80% DB pass, 80–100% media pass, clamped to 99 until the terminal save) or to the export itself.
- No notification for failures the trigger *view* already reports synchronously (insufficient disk, subprocess launch failure) — the user is present and gets a flash message.
- No email, push, or websocket delivery; no new external dependencies.
- No stale-job detection or timeouts (a subprocess killed mid-run leaves its job `running`; that is a pre-existing gap, recorded as deferred work rather than solved here).
- No backfill of `trigger_institution` on Stories 1.1–1.4's existing jobs.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Active job | A visible job is `pending`/`running` | Partial shows its progress bar and status; root element carries the 5-second polling trigger | N/A |
| Job finishes cleanly | `run_backup` saves `completed` | Next poll shows `completed` with no polling trigger; one unread `BACKUP_COMPLETED` notification for `triggered_by`, delivered to the trigger institution | N/A |
| Finishes with skipped media | `completed` with non-empty `error_message` | Row renders as a warning; notification is still `BACKUP_COMPLETED` but its title/body say it completed with warnings | N/A |
| Job fails | Export raises, or the job fails to start | Row shows the error; one `BACKUP_FAILED` notification carrying a summary of `error_message` | N/A |
| Notification creation fails | `Notification.objects.create` raises | Job's terminal state and the command's exit are unaffected | Exception logged, swallowed |
| No recipient / institution | `triggered_by` is `NULL`, or neither `trigger_institution` nor `scope` is set | No notification is created | Log line only, no error |
| Nothing active | Every visible job is terminal | Partial renders with no polling trigger | N/A |
| Unauthorized poll | Non-admin user hits the status endpoint | Empty `403`, no job data | N/A |
| Cross-institution isolation | Another institution's jobs exist | Never appear in the partial for an admin who isn't in that institution | N/A |

</frozen-after-approval>

## Code Map

- `backup/views.py:164-177` (`_recent_jobs_for`) -- the visibility query the new status view must reuse rather than duplicate. `backup/views.py:194` (`backup_create`) and its two `BackupJob.objects.create(...)` calls at `:278` (insufficient-disk FAILED row) and `:331` (PENDING row) need `trigger_institution=institution`. New `backup_status` view goes here; mirror `backup_create`'s permission gate but return `HttpResponseForbidden`, and use `@ratelimit(rate='30/m')`.
- `backup/urls.py` -- add a `status/` route (e.g. `backup-status`).
- `backup/templates/backup/create.html:~140-175` -- the inline "Recent Backup Jobs" card body/table; replace with `{% include 'backup/status.html' %}`. `backup/templates/backup/status.html` -- new partial. Bootstrap 4.6 progress bar (`.progress`/`.progress-bar`), AdminLTE conventions; htmx is already loaded via `templates/src/basic_plane.html:61` (`base.html` extends it).
- `templates/src/navbar.html:113-123` -- the existing bell: `hx-trigger="load, every 60s"` on `referral:notification-count`. Precedent for htmx polling in this codebase; note it polls at 60s, so the backup partial's 5s cadence needs its own rate limit.
- `referral/models.py:266-303` (`Notification`) -- fields: `recipient` FK, `notification_type` (choices = `NotificationType`), `title` (200), `body`, `link` (500), `is_read`, `institution` FK (required), plus `TimeStampedModel`/`UserTrackingMixin`. Its docstring says it is "created exclusively by referral/signals.py" -- update that line to acknowledge `backup/notifications.py` as a second producer. `referral/signals.py:22-46` shows the `try/except` + `logger.error` best-effort pattern to mirror (set `added_by`/`last_edit_by` to the actor as it does).
- `referral/views.py:574-600` (`notification_mark_read`) -- scopes by `recipient=request.user` **and** `institution=request.institution`, then redirects to `notif.link`. This is why delivery institution matters.
- `ndas/custom_codes/choice.py:220-224` (`NotificationType`) -- add the two backup types; `referral/migrations/` (`0001`, `0002_notification_and_more`) -- adding choices changes the field, so a `referral` migration `0003` is expected.
- `backup/management/commands/run_backup.py:37-97` -- three terminal exits to hook: "failed to start" (`:41-52`), "failed during export" (`:65-77`), and success (`:82-97`). Call `notify_job_finished(job)` after each terminal save.
- `backup/models.py` (`BackupJob`) -- add `trigger_institution` alongside `scope`/`scopes`; migration `backup/0009_...`.
- `backup/tests/test_management.py:58-` -- existing `run_backup` tests mock `create_export`; the new notification call will run for real inside them (their jobs have `triggered_by` and a scope), so they are the natural place for the terminal-state notification tests.

## Tasks & Acceptance

**Execution:**
- [x] `ndas/custom_codes/choice.py` -- add `NotificationType.BACKUP_COMPLETED` / `BACKUP_FAILED`
- [x] `referral/models.py` -- update the `Notification` docstring to name `backup/notifications.py` as a second producer
- [x] `referral/migrations/0003_...` -- generated via `makemigrations referral --no-input`
- [x] `backup/models.py` -- add `BackupJob.trigger_institution` (nullable FK, `SET_NULL`, distinct `related_name`)
- [x] `backup/migrations/0009_...` -- generated via `makemigrations backup --no-input`
- [x] `backup/notifications.py` (new) -- `notify_job_finished(job)`: resolve recipient and delivery institution, build title/body per outcome, `Notification.objects.create(...)`, all wrapped best-effort
- [x] `backup/management/commands/run_backup.py` -- call `notify_job_finished(job)` after each of the three terminal saves
- [x] `backup/views.py` -- set `trigger_institution=institution` on both `BackupJob.objects.create` calls; add `backup_status` view (permission gate → `HttpResponseForbidden`, `30/m` ratelimit, renders the partial via `_recent_jobs_for`)
- [x] `backup/urls.py` -- route for `backup_status`
- [x] `backup/templates/backup/status.html` (new) and `create.html` -- partial with progress bars, warning/error rendering, conditional polling trigger; `create.html` includes it
- [x] `backup/tests/test_notifications.py` (new), `test_management.py`, `test_views.py` -- cover the I/O matrix (notification content per outcome, best-effort behaviour, no-recipient/no-institution skips, polling trigger present/absent, `403`, isolation, `trigger_institution` persisted, bell count reflects the notification)

**Acceptance Criteria:**
- Given a running backup, when the admin opens the backup page, then the jobs table updates itself every few seconds without a manual reload and stops updating once no job is active.
- Given a backup completes, when the admin has navigated elsewhere, then an unread notification appears in the navbar bell for the triggering user, and clicking it opens the backup page.
- Given a backup fails, when the job reaches its terminal state, then a failure notification carrying the error summary is created.
- Given the notification cannot be created, when `run_backup` finishes, then the job is still marked completed/failed exactly as before.
- Given a super admin triggers a system-wide backup from institution X, when it finishes, then the notification is delivered under institution X (visible in their bell while X is active).

## Spec Change Log

- **Verification pass (2026-09-20) — three-layer review (blind-hunter, edge-case-hunter, verification-gap); no spec-level ambiguity, so no loopback:**
  - **Fixed:** an unauthenticated poll (e.g. logged out in another tab) hit `@login_required`'s redirect, and htmx would have swapped the whole login page into the card. `backup_status` now returns `204` with an `HX-Redirect` to the login page for anonymous users; an authenticated non-admin still gets the empty `403` this spec requires. (Narrower than reported: `SESSION_SAVE_EVERY_REQUEST=True` means each poll refreshes the session.)
  - **Fixed:** warning details used `text-warning` (yellow on white, poor contrast) -- now `text-dark`; the progress bar gained an `aria-label`. No `aria-live`: the region is replaced every 5s and would announce constantly.
  - **Tests added:** an invalid-POST re-render still lists jobs and keeps polling; "notify only after the terminal save" now proven for all three terminal exits by a spy that re-reads the row (previously success only); the `institution is None` gate; `405` on non-GET.
  - **Rejected, with reasons:** `NotificationType` consumers mis-rendering (none exist outside the model and signals); `has_active_jobs` only covering the newest 10 jobs (polling only exists to refresh rows on screen, so an undisplayed job doesn't need it); the 30/m limit under 3+ tabs and background-tab polling (the limit is fixed in this spec's frozen block, and a `hx-trigger` visibility filter needs `eval`, which the project's CSP likely blocks); notifying view-created FAILED rows (the spec's "Never"); raw error text and filenames in the notification body (its only reader is the triggering user, who already sees the same `error_message` on the backup page); `error_message` as the warning channel and the hard-coded status strings/99 threshold (Story 1.1's approved design, kept consistent).
  - **Deferred (pre-existing, not this story):** stale `running` jobs polling forever and blocking the overlap lock; `run_backup`'s unguarded failure-path save and un-caught `BaseException`; CLAUDE.md's Django 5.2 vs the venv's 6.0. All in deferred-work.md.
  - **Process note:** the implementation agent left an invalid UTF-8 byte (a Windows-1252 em dash) in `backup/urls.py`, which breaks Python's import of that file, despite reporting all tests passing. Caught during independent verification and fixed; every changed file was then re-scanned for encoding damage.
  - Full suite: `backup` 135/135 pass; `referral` 65 tests with only the 2 baseline failures.

## Design Notes

Polling-that-stops-itself (the fragment's root decides whether the next poll happens):

```django
<div id="backup-status"
     {% if has_active_jobs %}
       hx-get="{% url 'backup:backup-status' %}"
       hx-trigger="every 5s" hx-swap="outerHTML"
     {% endif %}>
  ... table ...
</div>
```

Known limitation, accepted: the existing bell only lists notifications for the user's *active* institution, so a super admin who switches institution after triggering a multi/system-wide job will not see its notification until they switch back. The backup page's table (which lists everything they triggered) still shows the result.

## Verification

**Commands:**
- `python manage.py test backup` -- expected: all existing tests plus the new ones pass
- `python manage.py test referral` -- expected: no *new* failures versus the pre-change baseline. Baseline captured at `6bbcf69` before any edits: 65 tests, exactly 2 failures (`test_count_excludes_read_notifications`, `test_count_zero_returns_empty_fragment` in `referral/tests/test_notification_bell.py`, both already in deferred-work.md), so "all pass" is not the bar -- 65 tests with only those same 2 failures is
- `python manage.py makemigrations --check backup referral --no-input` -- expected: no missing migrations for either app (the unrelated `problemlist` drift warning is pre-existing and ignorable)

**Manual checks (if no CLI):**
- Trigger a backup, stay on the page, and watch the progress bar advance and polling stop on completion; navigate away, trigger another, and confirm the bell shows the completion notification. **Not done in this session** -- live polling and the bell are covered by the Django test client only, not exercised in a browser.

## Suggested Review Order

**Live progress (polled partial)**

- The fragment decides whether the next poll happens: `hx-*` attributes only render while a job is active, so polling stops itself.
  [`status.html:9`](../../backup/templates/backup/status.html#L9)
- Job list and `has_active_jobs` evaluated once so the table and the trigger can't disagree.
  [`views.py:180`](../../backup/views.py#L180)
- The status endpoint: empty 403 for the permission gate, `HX-Redirect` for anonymous users, own 30/m limit.
  [`views.py:417`](../../backup/views.py#L417)

**Completion notification**

- Best-effort by construction: builds the content, resolves recipient and institution, and swallows every exception.
  [`notifications.py:52`](../../backup/notifications.py#L52)
- Called only after each terminal save, so status and progress are already durable when it runs.
  [`run_backup.py:79`](../../backup/management/commands/run_backup.py#L79)
- Why `trigger_institution` exists: the bell only lists the active institution, and a super admin's system-wide job has no `scope`.
  [`models.py:79`](../../backup/models.py#L79)
- Set on both job-creation paths.
  [`views.py:352`](../../backup/views.py#L352)
- The two new notification types (drives a `referral` migration).
  [`choice.py:225`](../../ndas/custom_codes/choice.py#L225)

**Tests**

- Content per outcome, best-effort behaviour, skip cases, bell count and mark-read redirect.
  [`test_notifications.py`](../../backup/tests/test_notifications.py#L1)
- Terminal-save ordering spies for all three exits.
  [`test_management.py`](../../backup/tests/test_management.py#L1)
- Polling trigger, gates, isolation, and the invalid-POST re-render.
  [`test_views.py`](../../backup/tests/test_views.py#L1)
