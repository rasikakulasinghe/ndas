---
title: 'Story 1.1: Trigger a full-scope backup of my institution''s data'
type: 'feature'
created: '2026-09-17'
status: 'done'
review_loop_iteration: 1
baseline_commit: 'ab62a3eeedcfbd9624b460a22408d81e2cd95ca7'
context: [D:/Projects/Current Projects/NDAS - Project/NDAS/_bmad-output/implementation-artifacts/epic-1-context.md]
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** NDAS has no backup capability at all today — institutional admins have no way to protect their institution's data against loss.

**Approach:** Add a new `backup` Django app with a `BackupJob` model, a permission-gated trigger view that launches a detached OS subprocess running a `run_backup` management command, which streams the institution's records from a fixed set of models into one `db_export.json` plus copies media files into a `media/` folder, both zipped together under non-public storage.

## Boundaries & Constraints

**Always:**
- Reuse `institution/`'s existing tenant-scoping (`InstitutionScopedManager`, `request.institution`, `UserType` checks) — never a parallel permission mechanism.
- Trigger view only: permission check → concurrency-lock check → disk-space check → create `BackupJob` row → launch subprocess → return immediately. The export itself never runs synchronously in the request.
- Export every one of these 13 models, scoped to the triggering admin's institution, in this order: `Patient`; `ReferralSent`, `ReferralReceived`, `ReferralMessage`; `Video`, `Attachment`, `GMAssessment`, `HINEAssessment`, `DevelopmentalAssessment`, `CDICRecord`, `GeneralPaediatricAssessment`, `Problem`; `ProblemAction` last.
- Stream into one `db_export.json` (object keyed by `"<app_label>.<model_name>"`, every key present even as `[]`) inside the open `zipfile.ZipFile`, one model's queryset at a time via `.iterator()`, writing one record at a time — never buffer a full model or the whole archive in memory. Copy media via chunked `shutil.copyfileobj`, never `read()` whole.
- Store the archive at `BASE_DIR/backups/<job_id>/<job_id>.zip` — never under `MEDIA_ROOT`/`STATIC_ROOT`.
- `BackupJob.triggered_by` set explicitly (`request.user`) at creation — mirror the manual `added_by=request.user` pattern, not automatic middleware.
- `backup/tests/` is a package (`__init__.py`), never a bare `tests.py`.

**Ask First:** None — architecture (`ARCHITECTURE-SPINE.md` AD-1/AD-2/AD-3/AD-4/AD-13/AD-16/AD-17) is fully decided for this slice.

**Never:**
- No Celery or other task-queue infrastructure.
- No `manifest.json`, checksums, or schema-version hashing — that's Story 1.3. This story's archive is only `db_export.json` + `media/`.
- No date-range filtering, multi-institution/system-wide scope, or HTMX progress polling/notifications — Stories 1.2, 1.4, 1.5 respectively.
- Never export the `referral` app's `Notification` model (excluded from the 13-model list) or anything from other epics' scope.
- Never use `dumpdata`/`loaddata` (cannot be scoped to an institution).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | Institutional admin triggers backup, sufficient disk space | `BackupJob` created `status=pending`, subprocess launched, request returns immediately; job later reaches `status=completed` with a `.zip` containing `db_export.json` (all 13 models, scoped to the admin's institution) + `media/{institution_slug}/videos\|attachments/...` | N/A |
| Insufficient disk | `shutil.disk_usage` below safety margin | Trigger refuses the job before creating the subprocess | `status=failed` set immediately with a clear `error_message`, no partial write |
| Concurrent job | A `BackupJob` for the same scope is already `pending`/`running` | New trigger refused | No new row created; clear error to the admin |
| Rate limit exceeded | Admin triggers more than the configured rate | Extra requests rejected | Standard `django_ratelimit` response |
| Subprocess launch fails | `Popen` raises before the child process starts | The trigger view itself (not the never-started command) sets `status=failed` | `error_message` names the launch failure |
| Media file missing/unreadable during export | A `Video`/`Attachment` row's file is missing or unreadable on disk at export time | The export continues to completion (does not abort the whole job) | `BackupJob.error_message` lists which file(s) were skipped; `status` stays `completed` — a completed-with-warnings job is distinguishable from a clean one by a non-empty `error_message` (human-approved: "complete with a warning" over "fail the whole job") |

</frozen-after-approval>

## Code Map

- `institution/managers.py:8-37` -- `InstitutionScopedManager.for_institution(institution)` (L22-30) and `all_institutions()` (L32-37); reuse for `Patient`/referral models' scoping.
- `django.db.transaction.atomic` + `.select_for_update()` -- required for the concurrency-lock check below (review finding: the naive `.filter(...).exists()` then `.create()` is a check-then-act race independently flagged by three review passes).
- `institution/middleware.py` (`InstitutionContextMiddleware`) -- sets `request.institution` (an `Institution` or `None`); use to resolve the triggering admin's institution.
- `institution/views.py:877-879` -- admin-or-superadmin permission check pattern (`user_type in (UserType.ADMIN, UserType.SUPERADMIN)`); copy for the trigger view's gate.
- `institution/views.py:388-394` (also `referral/views.py:43-46`) -- decorator stacking order: `@login_required(login_url="user-login")` → `@require_http_methods([...])` → `@ratelimit(key='user_or_ip', rate='10/m')` → `@handle_view_errors(...)`.
- `ndas/custom_codes/Custom_abstract_class.py:5-22, 25-50` -- `TimeStampedModel`, `UserTrackingMixin` (import both for `BackupJob`).
- `video/views.py:318` -- manual `added_by=request.user` pattern; mirror for `BackupJob.triggered_by`.
- `ndas/settings.py:7` `BASE_DIR`; `:18-37` `INSTALLED_APPS` (insert `'backup.apps.BackupConfig'`); `:429-431` rate-limit settings. No `CELERY_*` settings exist anywhere -- confirmed absent.
- `video/management/commands/fix_video_durations.py:18-176` -- `BaseCommand` structure (`add_arguments`, `handle`, `self.stdout.write`/`self.style.*`) to copy for `run_backup.py`.
- `institution/apps.py:4-10` -- `AppConfig` pattern for `backup/apps.py`.
- `ndas/urls.py:11-22` -- `path("<prefix>/", include("<app>.urls"))` pattern; add `path("backup/", include("backup.urls"))` before the `patients.urls` catch-all.
- `patients/models.py:155,420` -- `Patient(TimeStampedModel, UserTrackingMixin)`, `institution` FK at L420.
- `video/models.py:78,106` -- `Video(TimeStampedModel, UserTrackingMixin)`, `patient` FK at L106 -- scope via `.filter(patient__institution=institution)`.
- `patients/models.py` -- `Attachment`, `GMAssessment`, `HINEAssessment`, `DevelopmentalAssessment`, `CDICRecord`, `GeneralPaediatricAssessment` all carry a direct `patient` FK -- same `.filter(patient__institution=institution)` scoping.
- `problemlist/models.py` -- `Problem` (`patient` FK, same scoping); `ProblemAction` (`problem` FK only -- scope via `.filter(problem__patient__institution=institution)`).
- `referral/models.py` -- `ReferralSent`, `ReferralReceived`, `ReferralMessage` -- scope via their `InstitutionScopedManager`, same as `Patient`. Exclude `Notification` (4th model in this app, not part of the export).
- `ndas/custom_codes/validators.py:689-706` -- `get_institution_video_path`/`get_institution_attachment_path` -- confirms on-disk media layout is `{institution_slug}/videos|attachments/{filename}` with no patient-id in the path; drive media copying from each exported `Video`/`Attachment` row's actual file path, not a directory walk.

## Tasks & Acceptance

**Execution:**
- [x] `backup/apps.py`, `backup/__init__.py` -- scaffold the app (`AppConfig` per `institution/apps.py` pattern) -- required before anything else registers
- [x] `ndas/settings.py` -- register `'backup.apps.BackupConfig'` in `INSTALLED_APPS` after `institution` -- must happen before `makemigrations` can see the app
- [x] `backup/models.py` -- `BackupJob(TimeStampedModel, UserTrackingMixin)`: `job_type` (choices incl. `backup`; `restore`/`pre_restore_snapshot` values reserved for Epic 2), `status` (`pending|running|completed|failed`), `progress_pct` (int, default 0), `error_message`, `triggered_by` (set manually, not via mixin), `scope` (nullable `Institution` FK) -- the shared job-tracking record every later story extends. (`job_type`/`status` choices added to `ndas/custom_codes/choice.py` per CLAUDE.md convention.)
- [x] `backup/migrations/0001_initial.py` -- generated via `makemigrations backup`
- [x] `backup/services.py` -- `create_export(job)`: opens the target `.zip`, iterates the 13-model list in dependency order, writes `db_export.json`'s keyed sections via `.iterator()`, copies each exported `Video`/`Attachment` row's media file into `media/{institution_slug}/...` via chunked copy. Deviation from the illustrative Design Notes, verified against real code: `ReferralMessage` has neither an `institution` FK nor a scoped manager (only `sender_institution`), so it's scoped via `.filter(sender_institution=institution)` instead of `.for_institution()`.
- [x] `backup/management/commands/run_backup.py` -- `BaseCommand` invoking `services.create_export`, writing `status`/`progress_pct`/`error_message` transitions on `BackupJob`
- [x] `backup/views.py` -- trigger view: permission gate, **atomic** concurrency-lock check (`transaction.atomic()` + `BackupJob.objects.select_for_update().filter(scope=institution, status__in=['pending','running'])` -- the lock-check-then-create must be one atomic unit, not two separate steps, per review finding), disk-space check (`shutil.disk_usage`, wrapped so an `OSError` here fails the job cleanly rather than propagating), create `BackupJob`, `mkdir` + `subprocess.Popen(...)` both inside the same guarded block so a failure at either point marks the job `failed` (not left `pending` forever), redirect -- the only entry point into the backup service logic
- [x] `backup/services.py` -- `create_export` collects missing/unreadable media filenames instead of only logging them, and returns them to the caller so `run_backup.py` can populate `BackupJob.error_message` with a "completed with N file(s) skipped" note while still marking the job `completed` (human-approved policy, see I/O matrix)
- [x] `backup/management/commands/run_backup.py` -- failure cleanup removes only the partial `.zip`, never the whole `archive_dir` (that directory also holds this process's own `run_backup.log`, which Windows can't delete while the file is open) -- initial `status=running` save wrapped so a failure there also marks the job `failed` instead of leaving it stuck `pending`
- [x] `ndas/custom_codes/choice.py` / `backup/models.py` -- `progress_pct` gains a `MaxValueValidator(100)`
- [x] `backup/services.py` -- `estimate_export_size_bytes`: fixed `attachment.file_size or _safe_file_size(...)` treating a genuine `0` as falsy -- now `is not None`
- [x] `.gitignore` -- exclude `backups/` (the new non-public archive storage root) alongside the existing `.env_backups/` entry
- [x] `backup/templates/backup/create.html` -- removed the stray `{% csrf_token %}` outside the `<form>` (dead markup; the one inside the form is the real one)
- [x] `backup/urls.py` -- trigger URL
- [x] `ndas/urls.py` -- `path("backup/", include("backup.urls"))` before the patients catch-all
- [x] `backup/templates/backup/create.html` -- minimal trigger form, `src/base.html` + AdminLTE conventions
- [x] `backup/tests/__init__.py`, `backup/tests/test_views.py`, `backup/tests/test_services.py` -- cover the I/O matrix above (20 tests total; a live rate-limit test was added during review since the initial cut only smoke-tested with rate limiting disabled)
- [x] `backup/tests/test_management.py` -- new: exercises `run_backup` command directly (`pending -> running -> completed`, the exception branch, and that failure cleanup removes only the `.zip` not the log)
- [x] `backup/tests/test_views.py` -- new cases: no-institution-context branch, GET path of the non-admin permission gate, and the atomic concurrency lock under two overlapping requests
- [x] `backup/tests/test_services.py` -- new cases: missing-media-file produces a non-empty `error_message` with `status` still `completed`; `Attachment.file_size == 0` is respected (not treated as "unset")

**Acceptance Criteria:**
- [x] Given an institutional admin triggers a backup with sufficient disk space, when the request is submitted, then a `BackupJob` is created with `triggered_by` set and the HTTP response returns immediately without waiting for the export.
- [x] Given the job completes, when the resulting `.zip` is inspected, then it contains `db_export.json` with all 13 in-scope models scoped to only that admin's institution, and a `media/` folder mirroring the existing per-institution/type structure.
- [x] Given insufficient disk space, when the trigger view checks capacity, then the job is refused with `status=failed` before any subprocess is launched.
- [x] Given a `BackupJob` for the same scope is already `pending`/`running`, when a second trigger is attempted, then it is refused before a new row is created.
- [x] Given the trigger endpoint is called beyond its configured rate limit, when the extra request arrives, then it is rejected per `django_ratelimit` (the 11th request in a minute returns HTTP 403 — see Spec Change Log).
- [x] Given two near-simultaneous triggers for the same institution, when both requests race past the naive check, then exactly one `BackupJob`/subprocess is created and the other is refused (atomic lock, not check-then-act).
- [x] Given a media file referenced by an exported row is missing or unreadable, when the job finishes, then `status=completed` but `error_message` names the skipped file(s) — never a silent, fully-clean-looking success.

## Spec Change Log

- **Finding (Matrix Test Audit):** the I/O matrix's "Rate limit exceeded" row had no live-triggering test — every test in the suite disabled rate limiting (`RATELIMIT_ENABLE=False`), matching a project-wide convention (confirmed identical in `video/`, `reports/`, `users/` `test_security.py`). Added `BackupTriggerRateLimitTest` (in `backup/tests/test_views.py`) that enables rate limiting and confirms the 11th request in a minute is rejected.
- **Amendment:** that test initially asserted a 429 response (matching `settings.RATELIMIT_VIEW = 'ndas.views.handler_rate_limited'`'s intent), but the actual response is a plain 403. Root cause: `django_ratelimit.middleware.RatelimitMiddleware` — the piece that catches the `Ratelimited` exception and routes it to `RATELIMIT_VIEW` — is not registered in `settings.MIDDLEWARE`, so `Ratelimited` (a `PermissionDenied` subclass) falls through to Django's generic 403 handler instead. This is a **pre-existing, project-wide gap** affecting every `@ratelimit`-decorated view in the codebase, not something introduced by this story; fixing it (registering the middleware) is out of scope here since it's a cross-cutting change with effects on every rate-limited endpoint. The test now asserts the actual, current 403 behavior. **Flagged for the user/team to decide whether to fix the middleware registration separately** (likely via `bmad-correct-course` or a dedicated chore, since it touches every rate-limited view project-wide).

- **Review loop 1 — bad_spec + intent_gap findings from the parallel review (blind-hunter, edge-case-hunter, verification-gap):**
  - **bad_spec (fixed directly, root cause outside the frozen block):** the concurrency-lock check specified in Boundaries ("concurrency-lock check → disk-space check → create BackupJob row") never specified atomicity; the Code Map/Tasks I wrote translated it into a naive `.filter(...).exists()` then `.create()` — a check-then-act race independently flagged by all three review passes. Amended the Code Map/Tasks to require `transaction.atomic()` + `select_for_update()`. The already-approved *outcome* ("second trigger for the same scope is refused, no new row") is unchanged — only the implementation must actually guarantee it under concurrent requests.
  - **intent_gap (looped back to the human):** the frozen I/O matrix never had a scenario for a media file missing/unreadable on disk during export — a real gap in captured intent, not something derivable from the existing spec. Asked the human: complete-with-warning vs fail-whole-job. **Resolved: complete with a warning** — `status` stays `completed`, `error_message` names the skipped file(s). Added as a new frozen I/O matrix row (human-approved, not a unilateral amendment).
  - **KEEP (must survive this pass unchanged):** the 13-model export plan and its order (including the verified `ReferralMessage` → `sender_institution` scoping deviation); the single `db_export.json` streaming shape (one model at a time, one record at a time, no full-model/archive buffering); the view → service → management-command layering with `services.py` as the sole entry point; the `BackupJob` field set and choices; all 20 already-passing tests and their scenarios (only additive test cases were introduced, none of the existing ones were weakened or removed); the `.gitignore`/`progress_pct` validator/dead-`csrf_token`/`file_size==0`/mkdir-guard/log-file-rmtree patch-level fixes folded into this same pass rather than deferred to a second loop.

- **Verification pass (2026-09-18) — environment + test-only fixes, no production-code changes:**
  - **Environment blocker (unrelated to this story's code):** this venv had a corrupted `python-magic`/`python-magic-bin` install pairing that crashed the Python process with a native access violation on any `import magic` (`magic/compat.py` calling into a mismatched libmagic DLL). This crashed `backup.tests.test_services.CreateExportTest` the moment it created a real `Attachment` (whose `full_clean()` runs `validators.py`'s content-based MIME check). Fixed by a clean reinstall of both pinned packages (`pip install --force-reinstall --no-deps python-magic==0.4.27` then `python-magic-bin==0.4.14`, in that order) — no code or requirements.txt change; this would have crashed any other code path using `magic` too.
  - **bad_test (fixed):** `test_superadmin_with_no_institution_context_denied_gracefully` asserted a redirect to `home`, but `institution.middleware.InstitutionContextMiddleware` already redirects a superadmin with no `active_institution_id` to the institution selector before `backup_create` is ever reached — `backup_create`'s own "no institution context" `redirect('home')` branch (views.py:54-56) is real, defensive code but unreachable for superadmins via this path. Test now asserts the actual (correct) redirect target.
  - **bad_test + settings fix (fixed):** `test_two_simultaneous_triggers_create_exactly_one_job` errored (not merely failed) with `sqlite3.OperationalError: database table is locked` before the atomic-lock assertion ever ran. Root cause: Django's default sqlite test DB uses a shared-cache in-memory URI (`file:memorydb_default?mode=memory&cache=shared`), which raises `SQLITE_LOCKED` for concurrent writers from separate threads — a different error class from `SQLITE_BUSY`, which the existing `OPTIONS.timeout=120` busy-timeout setting does not cover at all (confirmed empirically in isolation, independent of Django). Fixed by adding `DATABASES['default']['TEST']['NAME']` (`ndas/settings.py`) to force a real file-based sqlite test DB for the whole suite, which uses standard `SQLITE_BUSY` locking compatible with the existing timeout. Also fixed the test's `fire()` thread target to call `connections.close_all()` in a `finally` block — each thread's un-closed connection was otherwise left holding the file-based test DB open, so Windows couldn't delete it during teardown (`PermissionError: WinError 32`) even though all 32 tests passed.
  - Full suite now passes clean: `python manage.py test backup` → 32/32, teardown succeeds, no stray `test_db.sqlite3` left behind (`.gitignore` updated).

## Design Notes

Streaming shape for `db_export.json` (illustrative, not literal code to copy verbatim):

```python
with zf.open("db_export.json", "w") as f:
    f.write(b"{")
    for i, (label, qs) in enumerate(MODEL_QUERYSETS):
        if i: f.write(b",")
        f.write(json.dumps(label).encode() + b":[")
        for j, obj in enumerate(qs.iterator()):
            if j: f.write(b",")
            f.write(json.dumps(serializers.serialize("python", [obj])[0]).encode())
        f.write(b"]")
    f.write(b"}")
```

Institution scoping per model category (three shapes only, per AD-3):
1. `Patient`, `ReferralSent`, `ReferralReceived`, `ReferralMessage` → `Model.objects.for_institution(institution)`
2. `Video`, `Attachment`, `GMAssessment`, `HINEAssessment`, `DevelopmentalAssessment`, `CDICRecord`, `GeneralPaediatricAssessment`, `Problem` → `Model.objects.filter(patient__institution=institution)`
3. `ProblemAction` → `ProblemAction.objects.filter(problem__patient__institution=institution)`

## Verification

**Commands:**
- `python manage.py test backup` -- expected: all new tests pass
- `python manage.py makemigrations --check backup` -- expected: no missing migrations

**Manual checks (if no CLI):**
- Trigger a backup as a seeded institutional admin in a local dev DB; unzip the resulting archive by hand and confirm `db_export.json` has all 13 model keys and only that institution's records, and `media/` mirrors existing upload paths.
