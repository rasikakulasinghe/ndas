---
title: 'Story 2.2: Restore preview and confirmation flow'
type: 'feature'
created: '2026-09-21'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'cb4153180caf18d277f6a5998f533dc12ecaad6c'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A validated archive currently ends at a summary page. Nothing shows what restoring it would do to this system's data, and there is no way to say yes or no — so nothing can safely be applied blind, and an abandoned upload can only sit on disk.

**Approach:** A read-only preview of a validated upload that shows the archive's scope and, per model, what it contains against what is in this system now (referral models marked "not restored"). The super admin then explicitly confirms or cancels. Confirming records an immutable snapshot of exactly what was previewed and marks the upload `confirmed`, for a later story to apply; cancelling discards the staged archive. Nothing in this story applies, deletes or loads any data.

## Boundaries & Constraints

**Always:**
- Same access rules as Story 2.1 for every new view: `UserType.SUPERADMIN` only (HTML views flash an error and redirect home and log to `django.security.restore`; anonymous users go to login), and a super admin only ever sees their own uploads (`404` otherwise). Confirm and cancel are `POST` only, CSRF-protected.
- The preview is available only for a `validated` upload (anything else redirects to that upload's status page with a message). Rendering the preview is strictly read-only: a `GET` writes no row and touches no file. It is built from the validated `manifest_summary` (never by re-opening the zip in the request) plus live counts from the database.
- The preview shows: the source job, `generated_at`/`generated_by`, scope type, the date filter, authenticity (an `unverified` archive keeps Story 2.1's warning wording and labels its claimed origin as claimed), each institution named by the archive with whether it **exists on this system** (matched by slug), and a per-model table of all 13 export models with the archive's record count (from the manifest, `0` if absent), the count currently in this system for the same institutions, and the action: **Replaced** for `Patient`, `Video`, `Attachment`, `GMAssessment`, `HINEAssessment`, `DevelopmentalAssessment`, `CDICRecord`, `GeneralPaediatricAssessment`, `Problem`, `ProblemAction`; **Not restored** for the three `referral` models (existing referrals are left untouched; the archive's referral rows are ignored). A short note states that `Bookmark` is never restored. Live counts use the export service's institution scoping for the institutions that exist here.
- Confirmation is blocked, and refused server-side regardless of what the page showed, when: any institution named by the archive does not exist on this system (the preview lists them; a restore never creates institutions, and it never restores "some of" an archive); the archive is date-scoped (`date_filter.applied` — its match/skip/import preview is Story 2.4, so confirming one is not offered yet); or the upload is not `validated`.
- Confirmation needs a `POST` with an explicit acknowledgement checkbox **and** the preview's digest. The digest is a SHA-256 over a canonical JSON of the decision-relevant, non-volatile facts: `archive_sha256`, `scope_type`, the institutions with their exists-here flags, `date_filter`, the archive's record counts, each model's action, and `authenticity`. Live counts are deliberately excluded (they change with normal use). The digest is recomputed at confirm time; if it differs from the one submitted, confirmation is refused ("the preview changed — review it again") and nothing is recorded.
- A successful confirm writes, in one save: `status = confirmed`, `confirmed_by`, `confirmed_at`, and `confirmed_snapshot` (the exact facts previewed, plus the live counts at that moment, plus the digest). It creates no job, deletes nothing, modifies no domain data, and the page says plainly that the restore has **not** been applied yet. A repeat confirm (double submit, replay) is refused and changes nothing.
- Not confirming changes nothing: navigating away leaves the upload `validated` and previewable again later. An explicit cancel (`POST`) deletes the upload's staged files and its row, for any upload that is `validated`, `confirmed`, `rejected` or `failed`, and for a `validating` upload only when it is **stale** (no update for 30 minutes — progress saves are its heartbeat), which is how a validator process that died no longer locks the uploader out. A live `validating` upload cannot be cancelled. A row is deleted only once its files are really gone.
- A `confirmed` upload is protected: a new upload never replaces or deletes it (`delete_finished_uploads` excludes it), and a new upload is refused while the user has one ("cancel it first").
- Confirm, cancel, blocked attempts and digest mismatches are logged to `django.security.restore` (actor, upload id, digest). Preview `GET` is limited to `30/m`, confirm and cancel to `10/m`.
- The Story 2.1 status page gains: a "Review restore preview" action for a `validated` upload, a confirmed panel for a `confirmed` one, and a cancel action wherever cancelling is allowed.

**Ask First:** None — referral handling (shown as not restored) and blocking on a missing institution are decided; the rest follows from the epic.

**Never:**
- No restore application, restore job, pre-restore snapshot, or any write to a domain model or media file (Stories 2.3/2.5).
- No date-scoped match/skip/import/excluded computation (Story 2.4); confirming a date-scoped archive is not offered.
- No re-parsing or extraction of the zip in a request; no background job in this story.
- No time-based auto-expiry or cleanup of uncancelled uploads, and no notification (Story 2.6 owns the audit trail).
- No change to Story 2.1's validation stages or its rejection behavior.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Preview, full-scope | Validated upload; every named institution exists here | Scope, institutions (all present), per-model archive vs current counts, actions; authenticity | Read-only: no row or file written |
| Preview, unverified | `authenticity=unverified` | Same, plus the unverified warning; confirm still allowed (already opted in at upload) | N/A |
| Missing institution | An archive institution slug is absent here | Missing ones listed; Confirm disabled | A forced `POST` is refused, nothing recorded |
| Date-scoped archive | `date_filter.applied` | Scope shown; Confirm not offered, with a pointer to the later match preview | A forced `POST` is refused |
| Confirm | Checkbox ticked and digest matches | `confirmed`, snapshot stored, "not applied yet" shown | No data touched, no job created |
| No acknowledgement | Checkbox missing | Refused with a form error | Nothing recorded |
| Preview changed | Digest differs at confirm (e.g. an institution added or removed since the page loaded) | Refused: "review it again" | Nothing recorded; logged |
| Replay | Confirm on an already-`confirmed` upload | Refused | No change |
| Walk away | Close or navigate away | Upload stays `validated` and previewable | N/A |
| Cancel | `validated` / `confirmed` / `rejected` / `failed` | Staged files and row deleted | Row kept if its files can't be removed |
| Cancel a `validating` upload | Fresh, or stale (> 30 min without update) | Fresh: refused. Stale: allowed | N/A |
| Not previewable | Upload is `validating`, `rejected` or `failed` | Redirect to its status page with a message | N/A |
| Confirmed upload in the way | User has a `confirmed` upload and uploads again | Refused ("cancel it first"); the confirmed row is never auto-deleted | N/A |
| Access | Non-super-admin; another user's upload; anonymous | Denied and logged / `404` / login redirect | N/A |

</frozen-after-approval>

## Code Map

- `backup/models.py:171` (`RestoreUpload`) -- add `confirmed_by` (nullable FK to the user model, `SET_NULL`), `confirmed_at`, `confirmed_snapshot` (`JSONField`, null); the existing partial unique constraint on `validating` is unaffected. Migration `0011_...`, generated with `venv/Scripts/python.exe manage.py makemigrations backup --no-input` (create only the backup migration).
- `ndas/custom_codes/choice.py:271` (`RestoreUploadStatus`) -- add `CONFIRMED = 'confirmed', 'Confirmed'`.
- `backup/restore_validation.py:88` (`FINISHED_STATUSES`) and `:172-198` (`delete_finished_uploads`) -- `confirmed` must stay out of `FINISHED_STATUSES` so a new upload can never delete a confirmed archive. `delete_upload_files`/`delete_staged_archive` are the removal helpers for cancel; keep the "delete the row only once the files are gone" rule.
- `backup/views.py:494` (`restore_upload`) -- add the "user already has a `confirmed` upload" refusal beside the existing busy check. `:473-491` (`_is_superadmin`, `_deny_restore`, `_latest_upload_for`) and `:629-652` (`restore_status`, `restore_status_fragment`) are the gate/ownership pattern the new views copy; the new views live in this file (epic 1's rule: `views.py` is the sole entry point into the service layer).
- `backup/services.py:124` (`_model_export_plan`) and `:51` (`_model_key`) -- the 13 model keys in fixed order and the institution scoping used for live counts (pass an `Institution` list for the institutions that exist here; an empty list must be skipped, never passed, since it is the "multi" shape). Do not reimplement the scoping.
- New `backup/restore_preview.py` -- `build_preview(upload)` (facts, per-institution exists flags, per-model rows with counts and action, block reasons, digest) and the confirm/cancel service functions, kept out of the views so they are unit-testable. The three `referral` keys are `referral.referralsent`, `referral.referralreceived`, `referral.referralmessage`.
- `backup/urls.py` -- `restore/<int:pk>/preview/`, `restore/<int:pk>/confirm/`, `restore/<int:pk>/cancel/`.
- `backup/templates/backup/restore_status_partial.html` (validated block ~line 53) and `restore_status.html` -- the actions to add; new `restore_preview.html`. Bootstrap 4.6 + AdminLTE, no inline JS.
- `epic-2-context.md` "Cross-Story Dependencies" -- 2.2 gates 2.3/2.5, "2.3 and 2.5 apply only what 2.2 confirmed"; the `confirmed_snapshot` is that hand-off contract.

## Tasks & Acceptance

**Execution:**
- [x] `ndas/custom_codes/choice.py` -- add `RestoreUploadStatus.CONFIRMED`
- [x] `backup/models.py` + `backup/migrations/0011_...` -- `confirmed_by`, `confirmed_at`, `confirmed_snapshot`
- [x] `backup/restore_preview.py` (new) -- `build_preview`, digest, confirm and cancel services (block reasons, digest recheck, stale-validating rule, delete-only-when-files-gone)
- [x] `backup/restore_validation.py` -- keep `confirmed` protected from replacement
- [x] `backup/views.py`, `backup/urls.py` -- `restore_preview`, `restore_confirm`, `restore_cancel` with the gates, methods and rate limits above; the confirmed-upload refusal in `restore_upload`
- [x] `backup/templates/backup/restore_preview.html` (new); `restore_status_partial.html` / `restore_status.html` -- preview link, confirmed panel, cancel actions
- [x] `backup/tests/` -- `test_restore_preview.py` (service: counts, actions, digest stability and sensitivity, block reasons) and view tests for every matrix row, including "a `GET` preview writes nothing" and "confirm never modifies domain data or creates a `BackupJob`"

**Acceptance Criteria:**
- Given a validated full-scope archive whose institutions all exist here, when a super admin opens its preview, then it shows the scope, each institution's presence, and per-model archive vs current counts with referral models marked not restored, and no row or file has changed.
- Given the preview is open, when the super admin navigates away or clicks cancel, then no data is modified, and cancel additionally removes the staged archive.
- Given the super admin ticks the acknowledgement and confirms an unchanged preview, then the upload becomes `confirmed` with a snapshot of exactly what was previewed, no restore is applied, and no job exists.
- Given the previewed state changed before confirmation (digest mismatch), or an institution is missing, or the archive is date-scoped, then confirmation is refused and nothing is recorded.
- Given a `validating` upload whose validator died, when it is stale, then cancelling it succeeds and the super admin can upload again.

## Spec Change Log

- **Verification pass (2026-09-21) — three-layer review (blind-hunter, edge-case-hunter, verification-gap) plus a full test run; no spec-level ambiguity, so no loopback:**
  - **The first full run of the committed work was 353 tests with 3 failures, all in the new tests and all test bugs:** one hard-coded an institution count of 1 (the `institution` app seeds a default), one built a CSRF client with no active institution so `InstitutionContextMiddleware` redirected before CSRF was ever checked (CSRF is not exempted on any new view; the test now uses a client with institution context and enforced CSRF, for confirm and cancel), and one flagged the project's own session-activity write as a write by the preview (it now allows only session-bookkeeping tables and additionally asserts the upload row and staged bytes are unchanged).
  - **Real bugs, fixed:** a non-ASCII digest made `hmac.compare_digest` raise (a 500 from inside the transaction; now compared as UTF-8 bytes, a clean mismatch); confirm never checked the staged archive, so a missing or short file could be confirmed (now a block reason from a read-only stat; the hash re-verify stays Story 2.3's job); `delete_finished_uploads` could delete an upload that had just been confirmed (each row is now re-checked under lock at deletion time); an archive with `start`/`end` set but `applied` falsy was treated as full-scope (now date-scoped); empty institution lists and unknown scope types are blocked; a double-cancel race redirected to a deleted upload's page (now to the upload form); form errors on a forced confirm of a blocked preview were invisible.
  - **Hand-off contract tightened:** the snapshot key formerly named `live_counts` is now `live_counts_at_confirmation` (they are the counts when confirmed, not what the page showed) and the snapshot carries `snapshot_version: 1`. A new migration `0012` adds a check constraint that a `confirmed` row always has its timestamp and snapshot (`0011` was already pushed, so it was left alone).
  - **Conventions and hygiene:** the three new views are wrapped in `handle_view_errors` through inner functions, so the spec's "another user's upload is a 404" is not turned into a redirect by the decorator; digest and slug values are logged with `%r`; the confirmed-upload refusal in `restore_upload` is now logged; the acknowledgement checkbox has `required`.
  - **Tests added:** live rate limits for preview, confirm and cancel; validator progress saves refresh `updated_at` (the heartbeat the stale-cancel rule depends on); a validator whose row was cancelled away exits cleanly and never re-inserts it (every save already used `update_fields`); confirming an unverified upload; the lost-race branch of confirm; the non-ASCII digest; missing staged file; and tightened assertions where words like "disabled" could match unrelated text.
  - **Rejected, with reasons:** making a repeat confirm succeed (the spec says it is refused); keeping the row when cancelling a confirmed upload (the audit trail is Story 2.6); deleting the row before the files (the spec says a row is deleted only once its files are gone); including live counts in the digest (they drift with normal use by design); re-hashing the archive in the request (a 50 GiB read; recorded as Story 2.3's precondition); inactive-institution handling, blocking on unknown model keys (Story 2.1 already validates keys and unknown ones are never applied), an HMAC/nonce, a delete modal, gettext, CLAUDE.md edits, and "immutable" enforcement beyond the new constraint.
  - **Deferred (recorded in deferred-work.md):** confirmed uploads have no lifecycle (expiry, orphaning if the uploader leaves, no global one-active-restore rule); the confirmation gate is a single generic checkbox plus an unkeyed digest, and cancel is one click with no confirmation step.
  - **Process notes:** the implementation agent stalled once, because a stale `test_db.sqlite3` made `manage.py test` wait on a "delete old test database?" prompt with stdin piped; every later run used `--noinput`. A background test run of mine was also killed by Claude Code for low system memory and was not restarted until asked. All results reported here are from the project venv (Django 6.0).
  - Full suite (venv): `backup` 383/383 pass; migrations clean.

## Design Notes

Why a digest that ignores live counts: "apply exactly what was previewed" must pin the parts that define the restore — which archive, which institutions, which models are replaced — but live row counts drift with ordinary use, so including them would make confirmation fail whenever a clinician saved a record. The counts are still shown and stored in the snapshot as evidence of what the admin saw.

The hand-off contract for Story 2.3: it must read `confirmed_snapshot`, apply exactly that institution set and those model actions, refuse if the snapshot's institutions no longer all exist, and re-hash the staged archive against `archive_sha256` before touching anything (the Story 2.1 validator trusts the hash from staging time, and the file sits on disk between confirmation and use). A `confirmed` upload is not consumed by anything yet, so the UI must not imply otherwise.

Cancel doubles as the recovery path Story 2.1 deferred: a stale `validating` row can be cancelled, which frees both the disk and the one-validating-upload-per-user slot. 30 minutes is safe because validation saves progress at every percent change.

## Verification

**Commands:**
- `venv/Scripts/python.exe manage.py test backup` -- expected: all existing tests (285 at `cb41531`, all passing) plus the new ones. Always use the venv interpreter: bare `python` in this shell is the global Python 3.13 (Django 4.2.7, no `python-magic`). Run it once, in the foreground, with no other `manage.py test` alive; concurrent runs collide on the shared file-based test database.
- `venv/Scripts/python.exe manage.py makemigrations --check --dry-run backup` -- expected: no missing migrations (the unrelated `problemlist` drift warning is pre-existing and ignorable).

**Manual checks (if no CLI):**
- Upload and validate an archive, open its preview, confirm the counts look right, then cancel and check the staged folder under `restore_uploads/` is gone. **Not done in this session**: everything is covered by the Django test client only, never a browser.

## Suggested Review Order

**The confirmation gate (start here -- it is the safety-critical part)**

- What the preview shows and every reason confirmation can be blocked; read-only by construction.
  [`restore_preview.py:154`](../../backup/restore_preview.py#L154)
- The digest: only decision-relevant, non-volatile facts, so ordinary use doesn't invalidate a confirmation.
  [`restore_preview.py:120`](../../backup/restore_preview.py#L120)
- Confirm: acknowledgement, blocks, constant-time digest check, then one conditional write so a double submit confirms at most once.
  [`restore_preview.py:276`](../../backup/restore_preview.py#L276)
- The snapshot Story 2.3 must apply exactly.
  [`restore_preview.py:264`](../../backup/restore_preview.py#L264)
- Cancel: allowed states, the stale-`validating` rule, row deleted only once its files are gone.
  [`restore_preview.py:340`](../../backup/restore_preview.py#L340)
  [`restore_preview.py:125`](../../backup/restore_preview.py#L125)

**Views and protection of a confirmed upload**

- Preview, confirm and cancel: super-admin gate and ownership lookup outside `handle_view_errors` so another user's upload stays a 404.
  [`views.py:699`](../../backup/views.py#L699)
  [`views.py:726`](../../backup/views.py#L726)
  [`views.py:777`](../../backup/views.py#L777)
- A new upload must never delete a confirmed one, even by a race; each row is re-checked under lock.
  [`restore_validation.py:175`](../../backup/restore_validation.py#L175)

**Model and migrations**

- New `confirmed` status.
  [`choice.py:275`](../../ndas/custom_codes/choice.py#L275)
- Confirmation fields, and the check constraint that a confirmed row always carries its snapshot.
  [`models.py:245`](../../backup/models.py#L245)

**Tests**

- Service, views, rate limits, races and the heartbeat.
  [`test_restore_preview.py`](../../backup/tests/test_restore_preview.py#L1)
  [`test_restore_command.py`](../../backup/tests/test_restore_command.py#L1)
  [`test_restore_views.py`](../../backup/tests/test_restore_views.py#L1)
