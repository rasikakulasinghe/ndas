---
title: 'Story 2.1: Upload and validate a restore archive'
type: 'feature'
created: '2026-09-20'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'fe2a306df4bb710a135fb7a198c0f97a3ceb5f68'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Epic 1 produces backup archives but nothing accepts one back. An uploaded `.zip` is untrusted input, so before any later restore step may touch data it must be proven intact, compatible with this database's schema, and (where possible) authentic.

**Approach:** A super-admin-only upload form stages the file to non-public storage (hashing it as it streams), then a detached background command validates it — zip safety, manifest, exact `schema_version`, origin authenticity, every per-file checksum — while an HTMX-polled page shows progress and then a specific verdict. Nothing is applied to any data.

## Boundaries & Constraints

**Always:**
- Restore is `UserType.SUPERADMIN`-only for every restore view (upload, status page, status fragment). Institutional admins and all other users are denied by any URL; a denial creates no row and stages no bytes. HTML views flash an error and redirect home (like `backup_create`); the polled fragment returns an empty `403`, and an anonymous poll gets `204` + `HX-Redirect` to login (Story 1.5's pattern). Denials and archive rejections also log at `WARNING` to a logger under `django.security` so they reach `security.log`.
- The upload is checked **before anything else**: a `.zip` extension; size ≤ `settings.FILE_UPLOAD_LIMITS['RESTORE_ARCHIVE_MAX_SIZE']` (default 50 GiB, overridable from `.env`); content sniffed with the existing `detect_file_mime` (a *detected* non-zip MIME rejects; an undetectable one falls through, the same fail-open convention as every other upload, which is safe because the zip parse below is authoritative); and enough free disk for the upload plus a safety margin. Any failure here is a form error — nothing is staged and no row is created.
- Staging streams the upload in chunks to `BASE_DIR/restore_uploads/<upload_id>/upload.zip` (non-public, never under `MEDIA_ROOT`/`STATIC_ROOT`), computing its SHA-256 in the same pass. The whole file is never held in memory. `restore_uploads/` is gitignored.
- Validation runs in a **detached subprocess** (`manage.py validate_restore_upload <id>`), never in the request cycle — at the 50 GiB limit, hashing the archive and re-reading every member takes far longer than a request survives. It follows Story 1.1's launch rules: detached process group, per-upload log file, failed-on-`Popen`-error, and only the command writes status after launch.
- At most one `validating` upload per super admin (a second upload is refused, no row created). A new upload deletes that user's earlier finished (`validated`/`rejected`/`failed`) uploads — rows and staged files.
- Checks run in this order; the first failure stops validation with its own error code and a message that names the specific mismatch:
  1. **Zip safety** — opens as a zip; no encrypted members; no duplicate member names; members limited to `manifest.json`, `db_export.json` and `media/...`; absolute, `..`, backslash, drive-letter and symlink members rejected; implausible expansion (any member > 1000:1) or a total declared size above 4× the upload limit rejected.
  2. **Manifest** — present, valid JSON, every required field present and correctly typed, `manifest_version == 1`, `checksum_algorithm == "sha256"`; `db_export.json` present.
  3. **Schema** — `manifest.schema_version` equals this database's `_compute_schema_version()` exactly; the error names both values.
  4. **Origin authenticity** — look up the `backup`-type `BackupJob` named by `manifest.source_job_id`. If it exists with a non-empty `archive_checksum`, the upload's SHA-256 must equal it or the upload is rejected (`archive_checksum_mismatch`). If it doesn't exist (or has no checksum), the upload is accepted **only** when the form's "allow unverified origin" box was ticked, and is recorded as `unverified`; otherwise it is rejected (`origin_not_verifiable`) with a message pointing at that checkbox.
  5. **Per-file checksums** — every `manifest.checksums` key is a zip member; every member except `manifest.json` is listed; each streamed SHA-256 matches. Progress is reported as files are verified.
- On success the row becomes `validated`, records `authenticity` (`verified`/`unverified`) and a manifest summary (`source_job_id`, `manifest_version`, `schema_version`, `scope_type`, `institutions`, `record_counts`, `date_filter`, `generated_at`, `generated_by`). On a rejection the row becomes `rejected` with `error_code` + `error_message`, and the staged file is deleted immediately (the row stays so the result can be shown). An unexpected exception becomes `failed` with the file deleted. Terminal status, `progress_pct` and result fields are written in one save.
- The status page and its polled fragment reuse Story 1.5's pattern: the fragment's root carries `hx-trigger="every 5s"` only while `validating`, so polling stops itself; its own `30/m` rate limit; the upload POST is `10/m`. An upload is visible only to the super admin who made it (`404` for anyone else).
- The sidebar gains a "Backup" entry (institution admins, and super admins with an active institution) and a "Restore" entry (super admins with an active institution) — no navigation link to the Epic 1 backup page exists today.

**Ask First:** None — the unverified-origin policy (accept-and-flag behind an explicit checkbox), the 50 GiB default, and background validation are decided.

**Never:**
- Nothing is applied: no write to any domain model, no media extraction, no preview, confirm or restore job (Stories 2.2/2.3).
- No parsing of `db_export.json`'s contents, and no check that media rows have their files in the zip (a file missing at backup time is legitimately absent).
- No notification (the user watches the polled page), no audit trail beyond the security log (Story 2.6), no cancel/delete UI (Story 2.2), and no cleanup of abandoned staged uploads beyond replace-on-new-upload (recorded as deferred work).
- No change to backup creation's behavior. Any extraction of the shared detached-launch code must keep it in `backup/views.py` and call `subprocess.Popen` through that module — existing tests patch `backup.views.subprocess.Popen`, and a helper elsewhere would let them spawn real subprocesses.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | Super admin uploads a valid archive whose originating job still exists with a matching checksum | Staged, validated in the background; row `validated`, `authenticity=verified`, summary stored; page shows the summary | N/A |
| Wrong extension | e.g. `.tar.gz`, `.exe` | Rejected in the request | Form error; nothing staged, no row |
| Wrong content | `.zip` extension, detected MIME not zip | Rejected in the request | Form error; nothing staged, no row |
| Too large | Size above `RESTORE_ARCHIVE_MAX_SIZE` | Rejected in the request | Form error; nothing staged, no row |
| No disk | Free space below upload + margin | Rejected in the request | Form error; nothing staged, no row |
| Not permitted | Institutional admin (or any non-super-admin) by any restore URL | Denied | No row, no staged bytes; logged to the security logger |
| Bad zip structure | Truncated, encrypted, duplicate names, `../` or absolute member, symlink, unexpected member, implausible expansion | `rejected` with a specific code | Staged file deleted |
| Bad manifest | Missing, invalid JSON, missing/mistyped field, unsupported `manifest_version`/algorithm, no `db_export.json` | `rejected` naming the problem | Staged file deleted |
| Schema mismatch | `schema_version` differs from this database | `rejected`; message shows both values | Staged file deleted |
| Origin found, hash differs | Job exists with a checksum that doesn't equal the upload's | `rejected` (`archive_checksum_mismatch`) | Staged file deleted |
| Origin not found | No matching job (e.g. a fresh server) | Box unticked: `rejected` (`origin_not_verifiable`). Box ticked: `validated`, `authenticity=unverified` | Staged file deleted on rejection |
| Per-file problem | Listed member absent, member not listed, or hash mismatch | `rejected` naming the member | Staged file deleted |
| Concurrent upload | Second upload while the user's previous one is `validating` | Refused in the request | No new row |
| Replacement | New upload after an earlier finished one | Earlier row and staged file deleted; new one proceeds | N/A |
| Launch or crash | `Popen` fails, or the command raises unexpectedly | `failed` with a message | Staged file deleted |
| Someone else's upload | Another super admin opens the id | `404` | N/A |

</frozen-after-approval>

## Code Map

- `backup/views.py:368-393` -- the detached-launch block inside `backup_create` (`manage_py`, `popen_kwargs` for Windows/POSIX, guarded `mkdir` + `subprocess.Popen(...)` with `stdout`/`stderr` to a per-job log). Extract into a private helper in this same file used by both `backup_create` and the new restore view. `backup/views.py:207-209` (`@ratelimit` + `backup_create`) and `:416-417` (`backup_status`, `30/m`, `HX-Redirect` for anonymous) are the patterns to mirror; the new restore views belong in this file (epic 1's rule: `backup/views.py` is the sole entry point into the service layer).
- `backup/services.py:327` (`_compute_schema_version`) -- the exact function the exporter used; recompute with it, never reimplement. `:33-36` (`DISK_SAFETY_MULTIPLIER`, `DISK_SAFETY_MINIMUM_BYTES`, `COPY_CHUNK_SIZE`) and `:42` (`get_archive_dir`) are the constants and path convention to reuse for staging (`restore_uploads/<id>/`).
- `backup/models.py` (`BackupJob`) and `ndas/custom_codes/choice.py:195-198` (`UserType`), `:242-` (`BackupJobType`/`BackupJobStatus`/`BackupJobScopeType`) -- model and `TextChoices` conventions. The three new `TextChoices` (`RestoreUploadStatus`, `RestoreAuthenticity`, `RestoreRejectionCode`) go in `choice.py`.
- `backup/management/commands/run_backup.py` -- the command shape to mirror: load row, mark running, progress callback, one terminal save, failure handling that removes the staged artifact and logs.
- `ndas/custom_codes/validators.py:415` (`detect_file_mime`) and `:104` (`sanitize_filename`) -- reuse for the content sniff and the stored `original_filename`. Note `validate_file_content_matches_extension` (`:440`) is keyed by an attachments-only MIME map; do not add `.zip` there, call `detect_file_mime` directly.
- `ndas/settings.py:373-379` (`FILE_UPLOAD_LIMITS`) -- add `RESTORE_ARCHIVE_MAX_SIZE` via `config(..., default=50 * 1024**3, cast=int)`. `:284-288` (`LOGGING['loggers']['django.security']`) -- the `security_file` handler (which only writes when `DEBUG` is false); log under a child such as `django.security.restore`. `.gitignore:4` (`backups/`) -- add `restore_uploads/` beside it.
- `templates/src/main_sidebar_menu.html` -- context already exposes `is_superadmin`, `user_type` and `active_institution`; entries gate on those (see the existing `{% if not is_superadmin or active_institution %}` pattern near line 103). The whole file renders on every page, so this edit needs a regression check.
- `backup/templates/backup/status.html` and `create.html` -- the polled-partial and card conventions (Bootstrap 4.6 progress bar, self-terminating `hx-*` root) for the new `restore.html` upload form, `restore_status.html` page and its progress partial.
- Middleware note: `InstitutionContextMiddleware` redirects a super admin with no active institution to the selector before any view runs, so the restore pages need an active institution context exactly as the backup page does.
- `epic-2-context.md` -- the "Discrepancies" section lists where the implemented archive differs from the planning docs; the ones that matter here: `manifest.json` is not in `checksums`, `institutions` is a list of slugs, `manifest_version`/`checksum_algorithm`/`scope_type` exist, and duplicate member names are possible in principle (rejected here).

## Tasks & Acceptance

**Execution:**
- [x] `ndas/settings.py`, `.gitignore` -- add `FILE_UPLOAD_LIMITS['RESTORE_ARCHIVE_MAX_SIZE']`; ignore `restore_uploads/`
- [x] `ndas/custom_codes/choice.py` -- add `RestoreUploadStatus` (`validating`/`validated`/`rejected`/`failed`), `RestoreAuthenticity` (`verified`/`unverified`), `RestoreRejectionCode` (one value per specific rejection in the matrix)
- [x] `backup/models.py` + `backup/migrations/0010_...` -- new `RestoreUpload` (`TimeStampedModel`, `UserTrackingMixin`): `uploaded_by` (nullable FK, `SET_NULL`), `original_filename`, `size_bytes`, `archive_sha256` (indexed), `allow_unverified`, `status`, `progress_pct`, `error_code`, `error_message`, `authenticity`, `source_job_id`, `manifest_summary` (JSON, nullable). Generated via `makemigrations backup --no-input`.
- [x] `backup/restore_validation.py` (new) -- staging helpers (chunked write + SHA-256, disk check, replace-old-uploads) and the five-stage validation engine, each stage raising a typed rejection carrying its code and message; streamed, never whole-file reads
- [x] `backup/management/commands/validate_restore_upload.py` (new) -- drives a row `validating → validated | rejected | failed`, reports progress during the per-file stage, deletes the staged file on any non-`validated` outcome
- [x] `backup/forms.py` -- `RestoreUploadForm`: the file field (extension, size, `detect_file_mime`) and the "allow unverified origin" checkbox
- [x] `backup/views.py` -- extract the detached-launch helper (behavior-preserving); add `restore_upload`, `restore_status` (page) and its polled fragment with the gates, rate limits and `404`/`403`/`HX-Redirect` behavior above
- [x] `backup/urls.py` -- `restore/`, `restore/<int:pk>/`, `restore/<int:pk>/status/`
- [x] `backup/templates/backup/restore.html`, `restore_status.html` and a progress partial -- upload form (with the size limit stated), progress bar, specific error display, and the validated-manifest summary
- [x] `templates/src/main_sidebar_menu.html` -- "Backup" and "Restore" entries with the role gating above
- [x] `backup/tests/` -- `test_restore_validation.py` (each stage and error code, against archives built by the real `create_export` for the happy path plus hand-built corrupt/malicious zips), `test_restore_views.py` (gates, form rejections, concurrency, replacement, `404`, polling trigger, `Popen` failure), a command test, and sidebar-visibility tests. Cover every row of the matrix.

**Acceptance Criteria:**
- Given a super admin uploads a valid archive from this system, when validation finishes, then the upload is `validated` with `authenticity=verified` and its manifest summary is shown.
- Given an upload that isn't a real zip, exceeds the size limit, or fails the content check, when it is submitted, then it is rejected before anything is staged or any row created.
- Given an archive whose schema version differs, whose originating job's checksum differs, or in which any file's checksum differs, when validation runs, then it is rejected with an error naming that specific mismatch and the staged file is removed.
- Given the originating job is unknown here, when the "allow unverified origin" box is unticked, then the archive is rejected; when ticked, then it is validated and flagged `unverified`.
- Given an institutional admin, when they request any restore URL, then they are denied and nothing is created or staged.
- Given a validating upload, when the page is open, then it updates itself until the verdict and then stops polling; and no domain data is ever modified by any of this.

## Spec Change Log

- **Verification pass (2026-09-20) — three-layer review (blind-hunter, edge-case-hunter, verification-gap); no spec-level ambiguity, so no loopback. Everything below was patched unless listed under Deferred/Rejected:**
  - **Real bug, fixed:** the status partial iterated `summary.record_counts.items`. Django resolves `.items` as a dict *key* before the method, so a manifest with a `record_counts` key named `items` would have 500'd that upload's page and polled fragment permanently. The view now passes a sorted list of pairs, and `record_counts` keys must look like model labels.
  - **Real bug, fixed:** a new upload deleted the user's earlier validated archive *before* the new file was staged, so a failed re-upload lost a good archive. Deletion now happens only after the new upload is staged, and a row is kept if its files could not be removed (previously it was deleted and the multi-GB file orphaned).
  - **Concurrency:** the one-`validating`-upload rule relied on `select_for_update()`, which locks nothing when no row exists and is a no-op on SQLite. It is now backed by a partial unique constraint on `(uploaded_by)` where `status='validating'`, with the view treating the `IntegrityError` as "busy".
  - **Failure windows closed:** anything raising between row creation and launch now marks the row `failed` and removes its files; the command guards staged-file deletion (`OSError`) and falls back to a best-effort `failed` save if the terminal save raises; `ZipFile()` parse errors beyond `BadZipFile` (`ValueError`, `OverflowError`, `struct.error`, ...) are `NOT_A_ZIP` rejections, not `failed`.
  - **Hardening of untrusted input:** control characters (log injection into `security.log`), `:` (NTFS streams), trailing dot/space, Windows reserved device names, over-long names and case-insensitive duplicate names rejected; member-count cap, an overlapping-entry check (`sum(compress_size)` vs the archive's real size) and a total-size cap tied to the real archive size; manifest `schema_version` and every checksum must be 64 hex characters, and string, list and object sizes are bounded, with all attacker-controlled text clipped before it reaches an error message, the security log or a page. Origin lookup now requires a *completed* backup job.
  - **Wording and audit:** an `unverified` archive no longer reads as fully confirmed. The page says the checksums come from the archive itself (they detect corruption, not tampering) and labels its claimed origin as claims; accepting an unverified archive is logged at WARNING to `django.security.restore`. `error_code` gained `choices`; `restore_status` gained a `30/m` limit.
  - **Tests added:** live rate limits for both restore endpoints; the `Popen` keyword arguments (both OS branches, both commands) that the launch-helper refactor moved; a read-only guarantee test that can actually fail (real records and media in the archive, nothing extracted anywhere); corrupt and oversized manifest members; a staging-outside-public-roots test that no longer compares against an import-time path; and a test for each behaviour patched above.
  - **Deferred (recorded in deferred-work.md):** orphaned `validating` rows lock the uploader out (needs Story 2.2's cancel or a staleness rule); staged archives are never cleaned up and the staging root is not configurable; oversized bodies are spooled to temp disk by CSRF middleware before any view check (deployment-level limit); Stories 2.2/2.3 must re-hash the staged archive before using it.
  - **Rejected, with reasons:** cross-validating manifest institutions and media paths against local data (the spec's "Never"; belongs to 2.2-2.4); allowing directory entries in the zip (the strict member allow-list is deliberate and the exporter never writes them); exception text shown on the page (super-admin-only and identical to the backup pages); i18n and an auth-decorator refactor (consistent with the backup views); PID tracking and zombie reaping (same launch code as Story 1.1); atomic command claiming (the command is only ever launched once per upload); failing on a non-positive `RESTORE_ARCHIVE_MAX_SIZE` (every other setting behaves the same).
  - **Process notes:** after a session restart the shell's bare `python` was the *global* interpreter (Django 4.2.7, no `python-magic`), not the project venv (Django 6.0). The implementation agent's first round of results ran there. Everything reported here was re-run with `venv/Scripts/python.exe`, and the migration was regenerated under it. The agent also died to a rate limit mid-way through the patch round; its source changes had landed and I completed and verified the rest.
  - Full suite (venv, Django 6.0, working `python-magic`): `backup` 285/285 pass; `institution` 191 tests with only the 2 baseline failures; migrations clean.

## Design Notes

Why background validation: with a 50 GiB ceiling the upload alone can take an hour, and validation adds a full hash of the archive (folded into the staging pass, so effectively free) plus a second streamed read of every member to verify per-file checksums — minutes to tens of minutes. That cannot live inside a request on typical hosting, so it reuses Story 1.1's detached-subprocess mechanism and Story 1.5's polling.

Known limitations, accepted:
- Authenticity only works against a job row that still exists on *this* system. A job ID that happens to collide with a local job from a different server produces a `archive_checksum_mismatch` for a genuine archive; the message names the job so a super admin can tell. The checkbox path exists precisely for restores onto a system that never made the backup.
- A staged upload that is never replaced or consumed stays on disk until a later story adds cleanup or cancel (deferred).
- The polled page keeps a super admin on the restore page for the duration of validation; if they leave, the row and result are still there when they return via the sidebar.

## Verification

**Commands:**
- `python manage.py test backup` -- expected: all existing tests plus the new ones pass. Run it once, in the foreground; concurrent runs collide on the shared file-based test database.
- `python manage.py test institution` -- expected: no *new* failures versus the pre-change baseline, since the sidebar template renders on every page. Baseline captured at `fe2a306` before any edits: 191 tests, exactly 2 failures (`test_admin_cannot_create_admin_type_user`, `test_multi_institution_enabled_is_false_by_default`, both already in deferred-work.md) -- so 191 tests with only those same 2 failures is the bar, not "all pass".
- `python manage.py makemigrations --check backup --no-input` -- expected: no missing migrations (the unrelated `problemlist` drift warning is pre-existing and ignorable).

**Manual checks (if no CLI):**
- Create a backup, upload it on the restore page, watch validation progress and the verdict; then tamper with a copy (edit a media file inside the zip) and confirm a specific rejection. **Not done in this session**: the flow is covered by the Django test client and by calling the command directly, with `Popen` mocked -- the real detached subprocess and a browser were never exercised.

## Suggested Review Order

**The validation engine (start here -- it parses untrusted input)**

- Five stages in fixed order; first failure wins, each with its own code and a specific message.
  [`restore_validation.py:551`](../../backup/restore_validation.py#L551)
- Path and structure safety: traversal, control characters, NTFS streams, reserved names, duplicates, bombs.
  [`restore_validation.py:208`](../../backup/restore_validation.py#L208)
  [`restore_validation.py:234`](../../backup/restore_validation.py#L234)
- Origin authenticity: verified against a completed job, or accepted only behind the explicit checkbox.
  [`restore_validation.py:449`](../../backup/restore_validation.py#L449)
- Per-file checksums, streamed, with progress.
  [`restore_validation.py:480`](../../backup/restore_validation.py#L480)

**Upload, staging, and who may do it**

- The upload view: super-admin gate, stage before replacing old uploads, everything after row creation guarded.
  [`views.py:494`](../../backup/views.py#L494)
- The concurrency rule, enforced by the database rather than a lock that locks nothing.
  [`models.py:244`](../../backup/models.py#L244)
- Chunked staging that hashes as it writes.
  [`restore_validation.py:144`](../../backup/restore_validation.py#L144)
- The upload form's cheap checks that run before anything is staged.
  [`forms.py:117`](../../backup/forms.py#L117)
- The 50 GiB default, overridable from `.env`.
  [`settings.py:381`](../../ndas/settings.py#L381)

**Background run and status page**

- The detached command drives a row to validated, rejected or failed in one terminal save.
  [`validate_restore_upload.py:67`](../../backup/management/commands/validate_restore_upload.py#L67)
- Shared detached-launch helper, extracted from `backup_create`; must stay here because tests patch `backup.views.subprocess.Popen`.
  [`views.py:212`](../../backup/views.py#L212)
- Record counts handed to the template as pairs, never a dict.
  [`views.py:614`](../../backup/views.py#L614)
- Status page and polled fragment.
  [`views.py:629`](../../backup/views.py#L629)
  [`views.py:642`](../../backup/views.py#L642)

**Navigation**

- New Backup and Restore sidebar entries (no link to the backup page existed before).
  [`main_sidebar_menu.html:276`](../../templates/src/main_sidebar_menu.html#L276)

**Tests**

- Each stage and error code, against a real `create_export` archive plus hand-built corrupt and malicious zips.
  [`test_restore_validation.py`](../../backup/tests/test_restore_validation.py#L1)
- Gates, form rejections, concurrency, replacement, rate limits, launch options.
  [`test_restore_views.py`](../../backup/tests/test_restore_views.py#L1)
  [`test_restore_command.py`](../../backup/tests/test_restore_command.py#L1)
