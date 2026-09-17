# Adversarial Divergence Review — Backup & Restore Architecture Spine

**Reviewed:** `ARCHITECTURE-SPINE.md` (architecture-backup-restore, updated 2026-09-16)
**Driving spec:** `SPEC.md` (SPEC-backup-restore)
**Lens:** For each finding, construct two implementers/units who each follow every AD *to the letter* yet produce incompatible artifacts, ownership, or state-mutation behavior. Every pair below is a hole that needs a new or tightened AD.

**Verdict up front:** the spine is well-shaped at the layer/paradigm level (app boundary, subprocess-vs-Celery, storage path, download pattern are all genuinely closed) but it is **silent or ambiguous at exactly the points where two developers would independently have to invent a convention**: the pre-restore snapshot's storage/lifecycle, the state-machine's crash/failure paths, checksum computation mechanics, schema-version comparison semantics, and retention-pruning's blast radius. None of these are exotic edge cases — they are the first questions an implementer hits when writing `run_backup.py`, `run_restore.py`, and the status/list views. As written, two competent implementers who never talk to each other will build a backup writer and a restore reader that cannot correctly interoperate, and a retention prune that can delete data another request is mid-read on.

---

## Finding 1 — The pre-restore snapshot (CAP-3) has no owner, no storage rule, no lifecycle

**Severity: High**

SPEC.md CAP-3 requires: "the system automatically snapshotting current state before applying the restore... if the restore fails or is cancelled, the automatic pre-restore snapshot can return the system to its prior state." This is a hard requirement with real data-loss consequences if implemented wrong.

The spine never assigns this artifact a location, a naming scheme, a `BackupJob` relationship, a visibility rule, or a cleanup trigger. AD-4 only pins down storage for "backups" in general (`BASE_DIR/backups/<job_id>/`); the Structural Seed only shows the shape of a normal backup zip. Nothing says whether the snapshot *is* a `BackupJob` row at all.

- **Implementer A** (`run_restore.py`): before touching data, calls the same `backup/services.py` function used by `run_backup.py`, creating a brand-new `BackupJob` row (its own `job_id`) with `scope` describing it as an auto-snapshot, written to `BASE_DIR/backups/<snapshot_job_id>/<snapshot_job_id>.zip` — fully consistent with AD-4 and AD-5. Because it's a normal `BackupJob`, it now shows up in `backup/manager.html`'s history list (CAP-6), is downloadable via the AD-7 `FileResponse` view, and — critically — is subject to AD-9's lazy age-based pruning like any other backup.
- **Implementer B** (also `run_restore.py`, different dev): treats the snapshot as an internal implementation detail of the restore job, not a first-class backup — writes it to `BASE_DIR/backups/<restore_job_id>/pre_restore_snapshot.zip` alongside the restore `BackupJob`'s own record, never creates a second `BackupJob` row for it, and deletes it automatically once the super admin confirms the restore succeeded.

Both readings satisfy every AD's literal rule text (AD-4's path constraint, AD-7's download pattern, AD-9's pruning rule). They are operationally incompatible and each has a distinct failure mode the other doesn't:

- Under A, the snapshot can be **auto-pruned by AD-9's age policy** while it's still the only rollback path for a restore an admin hasn't yet decided to keep or discard — CAP-3's own success criterion ("if the restore fails or is cancelled, the snapshot can return the system to its prior state") can silently stop being true with no error and no warning, purely because `max_age_days` elapsed.
- Under A, the snapshot also leaks into an **institutional admin's scoped history view** (CAP-6: "scoped to their permissions") even though it was triggered by a super admin restoring system-wide data the institutional admin doesn't own — a scope/visibility violation neither AD-9 nor AD-10 anticipates.
- Under B, there is no audit trail entry for the snapshot's own existence (CAP-7 requires every "backup creation... action" to be logged; if the snapshot isn't a `BackupJob`, is it a "backup creation" for audit purposes? Undefined) and no way for a super admin to manually retain/download it if the restore workflow's own cleanup logic has a bug.

**Fix needed:** a new AD that pins the snapshot's storage path, whether it is a `BackupJob` row (and if so, a `job_type`/`scope` discriminator so it's excluded from CAP-6's admin-facing history and AD-9's prune query by construction, not by convention), and its cleanup trigger (on confirm, on cancel, on TTL — pick one and rule out AD-9 pruning it prematurely).

---

## Finding 2 — AD-9's lazy prune races with a concurrent download or restore of the same backup

**Severity: High**

AD-9's rule: "The backup-list view, when `enabled` is true, deletes any backup past `max_age_days` **before rendering the remaining list**." This is a synchronous delete-then-render inside a GET request handler, with no mention of any lock, reference count, or "is this backup currently in use" check.

- **Implementer A** builds the AD-7 download view straightforwardly: `FileResponse(open(path, "rb"), ...)` after a permission check, exactly as specified — no existence re-check beyond what `open()` naturally does, no try/except around a mid-stream deletion.
- **Implementer B** builds `run_restore.py` under the assumption that once a restore `BackupJob` is created and the trigger view has validated the uploaded/selected archive exists, the archive path is stable for the life of the job — there is nothing in AD-9 telling them the backup they're reading from could be atomically removed out from under them by an unrelated admin's page view.

Concrete race: Admin 1 starts a large restore at `BASE_DIR/backups/42/42.zip` (job now "running"). Admin 2, on a completely unrelated screen, loads `backup/manager.html` with retention `enabled=True` and `max_age_days` small enough that backup 42 (created, say, 91 days ago per `created_at`, retention set to 90) qualifies for pruning — AD-9's rule says nothing about excluding a backup an active `run_restore.py`/download is currently reading. The list view deletes `42.zip` mid-read. Depending on OS/filesystem semantics (POSIX allows continued reads on an unlinked-but-open fd; Windows — this project's dev target per AD-2 — generally does **not**, and can raise a sharing-violation or truncate visibility), Implementer B's subprocess either silently succeeds against a half-file, crashes, or (on Windows) can't even open the file the list view is mid-deleting. Implementer A's download view, hitting the same race on a plain download rather than a restore, gets an unhandled `FileNotFoundError` inside `open()` that `@handle_view_errors` will convert to a generic 500 rather than a meaningful "this backup was just pruned" message.

Neither implementer violated any AD. AD-9 simply never states that pruning must skip backups referenced by a non-terminal `BackupJob` (any row with `status in {pending, running}` pointing at that path), nor that download/restore should defend against a vanished file with a specific error.

**Fix needed:** AD-9 needs an explicit exclusion clause — prune query must skip any backup that is the source of a `BackupJob` currently `pending`/`running` (a snapshot source, a restore source) — plus AD-7 needs a documented "file vanished mid-serve" error contract.

---

## Finding 3 — No single owner of "is this job done" when the subprocess never gets to write a terminal status

**Severity: High**

The Consistency Conventions table states: "Only the `run_backup`/`run_restore` command process writes `BackupJob` status transitions (`pending → running → completed/failed`); views are read-only on that model." This sentence is the crux of the ambiguity, not a resolution of it: the **trigger view** is the thing that calls `subprocess.Popen(...)` (AD-2), and it is the only code that can ever know Popen itself failed (e.g., `OSError`, resource exhaustion, `manage.py` not found) — a failure that happens *before* `run_backup.py`'s own process even starts running, so "the command process" never exists to write `status=failed`.

- **Implementer A** (trigger view in `backup/views.py`) reads the "views are read-only" rule as applying only to *successful* launches, and wraps the `Popen` call in try/except: on failure, writes `job.status = "failed"; job.error_message = "..."` directly from the view, reasoning that nobody else ever will.
- **Implementer B** (same view, different dev, or a strict reading enforced in code review against the literal Consistency Conventions text) treats "views are read-only on that model" as absolute — never writes `status` from any view under any circumstance — and instead just lets the `Popen` exception propagate to `@handle_view_errors`, which logs and shows an error page but **leaves the `BackupJob` row permanently at `status="pending"`**, since nothing ever transitions it.

Both are literal, defensible readings of the same sentence. Under B, a `BackupJob` stuck at `pending` forever is indistinguishable — to every other reader in the system — from a job whose subprocess is about to start. The status page just keeps polling. AD-9's prune query (Finding 2) has no defined behavior for `pending` rows either (is a `pending` row "a backup" that's past `max_age_days`, or does age only count from `completed`? AD-9 doesn't say — it just says "deletes any backup past `max_age_days`"). The Deferred section explicitly punts the *symmetric* problem — a subprocess that starts but then crashes/OOMs before writing `status=failed`, leaving `status=running` with a stale `updated_at` — to a future "watchdog," acknowledging staleness is a real, expected failure mode. But that Deferred note only covers the crash-after-start case; it says nothing about the crash-before-start case Implementer A/B diverge on, and it explicitly leaves the "flag as stale" logic unbuilt in this slice — meaning in the shipped feature, *nothing* ever definitively answers "did this job die" for either failure path, and two implementers building the status view vs. the list/download views can each build a different ad hoc heuristic (or none at all).

**Fix needed:** AD-8 needs to explicitly carve out "launch failure" as a case the trigger view itself is responsible for terminalizing (`status=failed`, with a specific `error_message` convention), separate from the "views are read-only once the subprocess exists" rule — and needs to state whether `pending`/`running` rows count toward AD-9's age-based pruning at all.

---

## Finding 4 — AD-8's status+progress writes aren't specified as atomic, so a poll can observe `progress_pct=100` with `status=running`

**Severity: Medium**

`BackupJob(status, progress_pct, ...)` are two separate fields with no stated write-ordering or atomicity contract. If `run_backup.py` is written as the natural two-step sequence — finish the last unit of work, `job.progress_pct = 100; job.save()`, then perform final cleanup/manifest-write, then `job.status = "completed"; job.save()` — that's two separate UPDATE/commit points with an arbitrary window between them.

- **Implementer A** (status HTMX partial) renders "Finishing up…" whenever it observes `progress_pct == 100 and status == "running"`, treating that combination as a normal, expected transient state.
- **Implementer B** (a different consumer of the same row — e.g., a notification/toast piece wired to CAP-5's "completion... notification," or a second status widget on a dashboard) treats `progress_pct == 100` itself as the completion signal (it's the more intuitive read of "100%") and fires the "backup complete" notification/redirect-to-download-ready state a poll cycle before `status` actually flips — racing ahead of AD-7's (unstated, see Finding 10) download-readiness gate.

Neither reads `BackupJob.status`/`progress_pct` incorrectly per any rule in the spine — AD-8 never states which field is authoritative for "done," nor that both fields must be updated in a single `.save(update_fields=[...])` call.

**Fix needed:** AD-8 should name `status` as the sole authoritative "done" signal, require the terminal `progress_pct=100` write and `status=completed` write to happen in the same `.save()`/transaction, and state that consumers must never treat `progress_pct` alone as a completion signal.

---

## Finding 5 — AD-6 checksums: path key format (Windows vs. Linux separators) and the manifest's own un-checksummed integrity

**Severity: Medium-High**

AD-6: `checksums: {path: sha256}`. Two things are underspecified: what "path" means as a dict key, and whether `manifest.json` covers its own integrity.

- **Implementer A**, developing/testing on the project's stated Windows dev environment (AD-2 explicitly calls out "Windows dev and Linux prod" as a real concern this spine already had to solve once, for the subprocess invocation), builds the checksum-key logic using `os.path.join(...)` / `pathlib.Path` string conversion while walking the pre-zip staging directory — producing keys like `db\patients.patient.json` on Windows.
- **Implementer B**, building the restore-side validator, reads `zipfile.ZipFile.namelist()` (which the ZIP spec — and Python's `zipfile` — always normalizes to forward slashes, on every OS) and looks up each entry's checksum via `manifest["checksums"][entry_name]`.

On any archive actually produced by a Windows-dev run of A's writer, every single lookup in B's validator misses (`db\patients.patient.json` != `db/patients.patient.json`), and CAP-2's success criterion ("an altered checksum... is rejected with a clear error before any data is modified") fires as a false positive on every legitimate archive — or, if B's implementer instead wrote a lenient fallback ("checksum key not found → skip verification for that file"), it fires as a silent integrity-check bypass, which is worse. AD-6 never states the path separator/normalization convention for its own dict keys, despite the sibling AD-2 explicitly having had to solve this exact Windows/Linux class of problem for subprocess invocation.

Separately: the checksums dict is computed over the archive's *other* contents and then written into `manifest.json` itself — which means `manifest.json` cannot contain its own checksum (chicken-and-egg: you'd have to hash a file that includes its own hash). AD-6 doesn't acknowledge this or provide an alternative (e.g., a separate `manifest.json.sha256` sidecar, or a top-level zip-wide checksum in addition to per-file ones). A restore validator has no spine-defined way to detect a tampered/corrupted `manifest.json` itself — only tampering in the files `manifest.json` describes.

**Fix needed:** AD-6 should pin the path-key format explicitly (forward-slash, POSIX-style, relative to zip root — matching `zipfile.namelist()` output) regardless of build OS, and should either add a manifest-covering mechanism (sidecar hash, or a separate whole-zip digest) or explicitly declare manifest.json's own integrity out of scope with a stated compensating control.

---

## Finding 6 — AD-6 `schema_version`: shape and "compatible" are both undefined, so writer and restorer can each build a valid-but-incompatible check

**Severity: Medium-High**

AD-6: "`schema_version` is derived from Django's applied-migration state (`MigrationRecorder`) so a restore can detect a schema mismatch before touching data." This names the *source* of truth but not the *shape* or the *comparison semantics*.

- **Implementer A** (`run_backup.py`) serializes `schema_version` as a dict `{app_label: latest_applied_migration_name}` for every installed app — a natural, literal reading of "derived from... applied-migration state."
- **Implementer B** (`run_restore.py` validator, built independently) serializes/expects a single hash string, `sha256(",".join(sorted(f"{app}.{name}" for app, name in applied_migrations)))` — also a perfectly literal reading of the same AD-6 sentence.

These two are simply incompatible JSON shapes; a restore built against B's expectation cannot parse a manifest built by A's writer at all (`TypeError` or silent `KeyError`, not a clean "schema mismatch" error — undermining CAP-2's own success criterion that a mismatch produces "a clear error").

Even granting both implementers converge on the same shape, "compatible" is never defined. Does compatibility mean **exact equality** of the full migration state (so restoring a six-month-old backup onto a DB that has since picked up one unrelated migration in, say, `django.contrib.admin` fails outright — plausible under active development, and arguably too brittle for a real recovery tool)? Or **subset/superset** (target DB's applied migrations must be a superset of the backup's, permitting forward-compatible restores)? Or **per-app relevance** (only compare migration state for apps that actually appear in `db/<app_label>.<model_name>.json` inside the archive, ignoring unrelated apps' schema drift)? A implementer building the check strictly ("any difference blocks restore") and one building it loosely ("only compare apps present in the archive") both satisfy AD-6's literal text ("detect a schema mismatch before touching data") while accepting/rejecting a materially different set of real-world restore attempts — this is exactly the kind of silent behavioral fork that won't surface until a real restore during an incident, the worst possible time.

**Fix needed:** AD-6 needs to pin the exact `schema_version` JSON shape and state the comparison rule (equality vs. superset vs. per-app-relevant-subset) explicitly, not just name the data source.

---

## Finding 7 — AD-5's "one file per model" doesn't reconcile with per-institution restore scoping for multi-institution super-admin backups

**Severity: Medium-High**

AD-5: `db/<app_label>.<model_name>.json` (**one file per model**). AD-3: `services.py` calls `serializers.serialize(...)` per model against `InstitutionScopedManager`-filtered querysets — implying scoping happens per-institution. CAP-1 explicitly allows a super admin's backup to cover "system-wide or explicitly selected institution(s)." SPEC's non-goals explicitly rule out "cross-institution data merging during restore — a restore applies only within the scope it was created for," which presupposes a restore can be scoped to a subset of what a multi-institution archive contains.

- **Implementer A** (`run_backup.py`), reading AD-5's path pattern literally ("one file per model," singular path, no institution segment), loops over every selected institution's scoped queryset for a given model and **unions them into a single `db/patients.patient.json` file** — matching the stated path exactly.
- **Implementer B** (`run_restore.py`/services.py restore-apply logic), needing to honor the "no cross-institution merging on restore" non-goal for a restore that a super admin scopes to just one institution out of a multi-institution archive, needs institution-taggable restore units — and since AD-5 gives no row-level institution tag inside the json (the file is just whatever `serializers.serialize` emits for the model, which may or may not include the institution FK depending on the model), writes their own convention on the *writer* side instead: `db/{institution_slug}/patients.patient.json`, one subtree per institution — deviating from AD-5's literal single-path-per-model rule, but doing so precisely *because* AD-5 as written can't actually support a restore that must apply "only within the scope it was created for" when multiple institutions are unioned into one file.

Whichever writer convention actually ships, a restore-reader built independently against the *other* convention either can't find the per-institution slice it needs to scope a partial restore to (A's shape has no institution boundary to restore against), or globs for `db/*.*.json` and silently skips B's `db/{slug}/*.*.json` files entirely (path-pattern mismatch, silently-incomplete restore rather than an error). AD-5 was written to "prevent backup-writer and restore-reader code drifting on where each piece lives" — but it only pins this down for the single-institution case; the moment CAP-1's multi-institution super-admin archive is in play, the rule as stated is actually ambiguous, not settled.

**Fix needed:** AD-5 needs an explicit rule for the multi-institution case — either institution-namespaced db paths (and a stated restore-scoping mechanism that reads them), or a stated row-level institution tag every serialized model is guaranteed to carry, with a defined way for `run_restore.py` to filter a merged file down to one institution.

---

## Finding 8 — AD-9's prune query scope (system-wide vs. viewer-scoped) determines whose data an ordinary GET request can delete, and it's unstated

**Severity: Medium**

AD-9: "The backup-list view, when `enabled` is true, deletes any backup past `max_age_days` before rendering **the remaining list**." CAP-6 says the list is "scoped to [the viewer's] permissions" and that retention is "system-wide." AD-9 never states whether the *delete query* itself is scoped to the viewer or system-wide — only that the *rendered remainder* is scoped.

- **Implementer A**, reasoning defensively ("a view should only ever touch data in its own request's authorization scope"), runs the prune delete against `BackupJob.objects.filter(institution=request.institution, ...)` before rendering an institutional admin's own scoped list. Consequence: retention is no longer reliably "system-wide" per CAP-6 — an institution whose admin rarely opens the backup history page (or a super admin's own system-wide backups, if nobody ever loads the super-admin list view) never gets pruned, regardless of how long `max_age_days` has elapsed, silently contradicting CAP-6's stated success criterion that "once a super admin enables [retention] with a max-age value, backups older than that age are automatically removed" (unconditionally, not "removed the next time someone happens to look").
- **Implementer B**, reasoning from "system-wide" in CAP-6's own wording, runs the prune delete against `BackupJob.objects.all()` unconditionally before rendering *any* viewer's list — meaning an **institutional admin's ordinary page load silently deletes another institution's (or the super admin's own) old backups** as a side effect of a GET request that institutional admin has no visibility or permission into. This is also a CAP-7 audit-trail question the spine never answers: is that deletion logged as performed "by" the viewing institutional admin (who has no actual authority to touch another institution's backups per AD-10/CAP-4), or by "system"? Neither `BackupJob`'s stated fields (`triggered_by` — the *creator*, not the *pruner*) nor the Logging convention row addresses who/what gets attributed for a prune-on-access deletion.

Both are literal, good-faith readings of "deletes any backup past `max_age_days`," and they trade off two different violations of the spec's own stated guarantees (either retention silently doesn't work as "automatic," or a low-privilege viewer's page load has a destructive side effect outside their own scope with no clear audit attribution).

**Fix needed:** AD-9 must state explicitly that the prune delete query is unscoped (system-wide, matching "system-wide... policy" in CAP-6) or scoped, and must state what/who CAP-7's audit entry attributes a prune-on-access deletion to.

---

## Finding 9 — AD-1's app boundary is aspirational prose, not an enforced rule; nothing stops `institution/views.py` from calling `backup/services.py` directly

**Severity: Medium**

AD-1's "Prevents" column says it prevents "backup logic scattered across `institution/`," but the actual "Rule" clause only mandates *creating* the `backup/` app with a specified file layout — it never states that other apps must not trigger backup jobs, construct `BackupJob` rows, or import `backup/services.py` directly. The Design Paradigm section explicitly calls `services.py` "framework-agnostic Python" (i.e., designed to be importable/reusable), which if anything invites exactly this.

- **Implementer A** builds `backup/views.py`'s `POST /backup/create` as the sole trigger path, with `@ratelimit` (AD-11), permission check, `BackupJob` creation, and `Popen` launch all co-located there, per the Design Paradigm's own layering description.
- **Implementer B**, working on `institution/` (which "already carr[ies] full Phase 2 scope" per AD-1's own prose, i.e., institution admins already live there and already have permission-check plumbing in that app) adds a "Quick Backup" convenience button to the institution admin dashboard, wiring it to a new view in `institution/views.py` that does `from backup.services import create_backup_job; create_backup_job(...)` directly, reusing `institution/`'s own already-present tenant-scoping (satisfying AD-10's letter — "reuses `institution/`'s existing tenant-scoping" — trivially, since it *is* `institution/`'s own view) and never touching `dumpdata`/storage path/manifest logic directly (satisfying AD-3, AD-4, AD-5, AD-6 by construction, since those all live inside the `services.py` call it delegates to).

Nothing in AD-1's actual Rule text is violated by B. Yet the system now has two independent trigger code paths for the same capability, each of which must independently remember to apply AD-11's rate limiting (B's new `institution/views.py` endpoint is easy to forget to `@ratelimit`, since AD-11's rule text specifically calls out "backup/restore trigger endpoints" in a way a reviewer skimming `institution/` app changes might not flag as one), independently get CAP-7's audit-logging convention right, and independently get the permission-check-before-create ordering right — a classic "prevents scattering" intent that the rule as literally written doesn't actually prevent.

**Fix needed:** AD-1's Rule (not just its Prevents column) should state that `BackupJob` creation and `backup/services.py`'s trigger-level functions may only be invoked from `backup/views.py` — i.e., make the app boundary an enforced single-entry-point rule, not just a "create this app" instruction.

---

## Finding 10 — AD-7 never states a status precondition for download, so a `pending`/`running`/`failed` job's (partial or nonexistent) zip can be requested

**Severity: Medium**

AD-7's rule for the download view is only about the response mechanism (`FileResponse` + `Content-Disposition`, permission-checked) — it never states that the view must first check `BackupJob.status == "completed"`.

- **Implementer A** adds the natural guard: download view first does `get_object_or_404(BackupJob, id=pk, status="completed")` (or an explicit `if job.status != "completed": return 404/error`), reasoning that AD-4/AD-5 imply the zip only exists in its final, valid form once the job is done.
- **Implementer B**, focused purely on AD-7's literal text (permission check → `FileResponse` from the stored path), builds the download view as `get_object_or_404(BackupJob, id=pk)` (any status) → permission check → `FileResponse(open(path, "rb"), ...)`, since AD-7 says nothing about `status` at all and the path is deterministically derivable from `job_id` per AD-4 regardless of job state.

Under B, a user who navigates directly to a download URL for a job still `status="pending"` or `"running"` (e.g., by guessing/reusing a URL from the status page before completion, or via the race in Finding 2/3 where a job is stuck) hits `open()` against a file that doesn't exist yet or is a half-written in-progress zip — an unhandled exception on a nonexistent path, or worse, a **truncated, structurally-invalid but partially-readable zip being served and downloaded as if it were a valid backup**, silently violating CAP-2's integrity guarantee for anyone who later tries to restore from that half-written download. Neither implementer's view is inconsistent with AD-7 as written.

**Fix needed:** AD-7 should state the required `status` precondition (`completed`, and arguably also exclude backups currently mid-restore-read or mid-prune per Finding 2) for the download view, plus the specific error behavior for a not-yet-ready or vanished backup.

---

## Summary Table

| # | Finding | Severity |
| --- | --- | --- |
| 1 | Pre-restore snapshot (CAP-3): no storage rule, no `BackupJob` status, no visibility scope, no cleanup trigger — can be auto-pruned by AD-9 before it's ever used | High |
| 2 | AD-9 lazy prune races with a concurrent download/restore reading the same file — no exclusion for in-use backups | High |
| 3 | No terminal-status owner for a subprocess-launch failure or silent crash — "views are read-only" vs. "someone must mark it failed" is unresolved | High |
| 4 | `status`/`progress_pct` writes not specified as atomic — pollers can observe `progress_pct=100` with `status=running` and race ahead of actual completion | Medium |
| 5 | Checksum dict key format (path separators, Windows vs. Linux) unspecified; manifest.json has no defined self-integrity mechanism | Medium-High |
| 6 | `schema_version` shape and "compatible" comparison semantics (exact/superset/per-app) both unspecified | Medium-High |
| 7 | AD-5's "one file per model" doesn't reconcile with per-institution restore scoping for multi-institution super-admin backups | Medium-High |
| 8 | AD-9 prune-delete query scope (system-wide vs. viewer-scoped) unstated — determines whether retention silently doesn't fire, or a low-privilege GET deletes another institution's data | Medium |
| 9 | AD-1's app-boundary rule doesn't actually forbid other apps (e.g. `institution/`) from calling `backup/services.py` directly, duplicating trigger/permission/rate-limit paths | Medium |
| 10 | AD-7 download view has no stated `status` precondition — a pending/running/failed job's path can be requested and served partial/nonexistent | Medium |
