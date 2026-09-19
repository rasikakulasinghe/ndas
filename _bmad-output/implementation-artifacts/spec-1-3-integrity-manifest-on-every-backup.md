---
title: 'Story 1.3: Integrity manifest on every backup'
type: 'feature'
created: '2026-09-19'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '4cc4dfff564bc97e5f51d7f8b5320dcc634bccce'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A Story 1.1/1.2 archive is just `db_export.json` + `media/` — nothing in it (or about it) lets a later restore (Epic 2) verify the archive wasn't corrupted, was produced by a compatible schema, or actually contains what it claims to.

**Approach:** Add a `manifest.json` entry to every archive (schema version, scope, per-model record counts, per-file checksums, generation metadata) written in the same single streaming pass as `db_export.json`/media, plus a whole-archive SHA-256 computed after the `.zip` is finalized and stored on `BackupJob.archive_checksum`.

## Boundaries & Constraints

**Always:**
- `manifest.json` is written into the same open `zipfile.ZipFile` as `db_export.json` and `media/`, after both (its own `record_counts`/`checksums` values are only fully known once the DB pass and media pass have both completed).
- Manifest fields (from epic-1-context.md's Technical Decisions, plus `scope_type` — needed for Epic 2's restore logic to disambiguate "system-wide" from "multi happened to include every institution", not explicitly named in the epic doc but additive, not contradictory): `source_job_id`, `schema_version`, `scope_type`, `institutions` (list of institution slugs this archive actually covers — for `system`, every institution slug at generation time), `record_counts` (one entry per exported model key, matching `db_export.json`'s keys, always present even as `0`), `checksums` (SHA-256 per archive member, keyed by the exact string as it appears in `zipfile.namelist()`), `generated_at`, `generated_by` (triggering user's username), `date_filter` (`{"applied": false, "start": null, "end": null}` — always this constant shape until Story 1.4 implements date filtering; the key must exist now so Epic 2/Story 1.4 don't need a manifest schema migration later).
- `schema_version` is a SHA-256 over the sorted `"<app_label>.<name>"` list of every currently-applied migration (via `django.db.migrations.recorder.MigrationRecorder(connection).applied_migrations()`), computed once per export.
- `checksums` covers every member actually written to the zip (`db_export.json` + every successfully-copied media file) — a media file recorded in Story 1.1's `skipped_media` list (missing/unreadable) has no checksum entry (it was never written), consistent with `record_counts` still reflecting the DB row count regardless.
- The whole-archive checksum is computed by hashing the finished `.zip` file on disk (chunked read, never a whole-file read()) **after** the `zipfile.ZipFile` context manager closes — never embedded inside `manifest.json` itself (avoids the manifest needing to describe its own file's hash). Stored on `BackupJob.archive_checksum` (new field), not in the archive.
- `create_export`'s streaming/never-buffer-a-whole-model-or-archive invariant (Story 1.1) is preserved: record counts and per-file hashes accumulate incrementally during the existing single pass, never via a second read-through.
- `backup/management/commands/run_backup.py` persists `archive_checksum` onto the `BackupJob` row in the same final save that sets `status=completed`.

**Ask First:** None — every field and computation above is fully decided from epic-1-context.md plus this spec's `scope_type` addition (additive, doesn't conflict with anything frozen elsewhere).

**Never:**
- No restore-side validation of `schema_version`/checksums — that's Epic 2's job; Story 1.3 only *produces* a correct, complete manifest.
- No change to the 13-model export list, its order, or the three scoping shapes (Stories 1.1/1.2, untouched).
- No date-range filtering (Story 1.4) — `date_filter` is always the constant unapplied shape.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | Any completed backup (single/multi/system) | Archive contains `manifest.json` with all fields populated correctly; `BackupJob.archive_checksum` is a 64-hex-char SHA-256 matching the actual `.zip` file's hash | N/A |
| Missing media file | A `Video`/`Attachment` row's file is missing/unreadable (Story 1.1 "complete with a warning" case) | `manifest.json`'s `checksums` has no entry for that file; `record_counts` still counts the DB row; job still `completed` | N/A (Story 1.1's existing skipped-media warning is unchanged) |
| Empty scope | A `multi`/`system` job whose resolved institution set has zero patients | `manifest.json` still generated; every `record_counts` entry is `0`; `checksums` has only `db_export.json`'s entry | N/A |
| `schema_version` reproducibility | Two backups triggered with no migrations applied in between | Both archives' `manifest.json` have an identical `schema_version` value | N/A |

</frozen-after-approval>

## Code Map

- `backup/services.py:272-354` (`create_export`) -- current single-pass structure: opens the zip, writes `db_export.json` streaming from `plan` (the 13-model list), then copies media via `_copy_media_file`. Story 1.3 adds manifest assembly around/after this same pass and changes the return shape.
- `backup/services.py:243-269` (`_copy_media_file`) -- currently returns `None` (success) or a skip-reason string; needs to also surface the copied file's SHA-256 on success (e.g. return `(skip_reason_or_None, sha256_hex_or_None)`) without a second file read -- compute the hash inline during the existing chunked `shutil.copyfileobj`-based copy (replace with a manual chunked loop that both writes and hashes, since `copyfileobj` has no hash hook).
- `backup/services.py:81-186` (`_model_export_plan`) -- the ordered `(json_key, queryset)` pairs; `record_counts` keys must exactly match these `json_key` strings.
- `backup/services.py:38-44` (`get_archive_dir`/`get_archive_path`) -- reuse unchanged for locating the finished `.zip` to hash for `archive_checksum`.
- `backup/models.py:65-97` (`BackupJob.scope`/`scope_type`/`scopes`) -- add `archive_checksum` alongside these (new `CharField(max_length=64, blank=True, default="")`).
- `backup/management/commands/run_backup.py:63-96` -- `create_export(job, progress_callback=...)` call site (line 64) and the final `COMPLETED` save (lines 82-90) -- must unpack the new 3rd return value and add `archive_checksum` to `update_fields`.
- `backup/tests/test_services.py:137-142` (`_export`/`_export_with_skipped` helpers) and `:174` (`zf.namelist()` usage, not exhaustive-equality -- confirmed safe for a new `manifest.json` member) -- both helpers unpack `create_export`'s return value and need updating for the new 3-tuple.
- `backup/tests/test_management.py:60-61` -- mocks `create_export`'s `return_value` as a 2-tuple `(archive_path, skipped_media)`; needs updating to the new 3-tuple shape.
- `django.db.migrations.recorder.MigrationRecorder` -- stdlib Django API for `schema_version`: `MigrationRecorder(connection).applied_migrations()` returns `{(app_label, name): Migration}`; sort the `"<app_label>.<name>"` keys before hashing for determinism.

## Tasks & Acceptance

**Execution:**
- [x] `backup/models.py` -- add `BackupJob.archive_checksum = models.CharField(max_length=64, blank=True, default="")`
- [x] `backup/migrations/0005_...` -- generated via `makemigrations backup`
- [x] `backup/services.py` -- new `_compute_schema_version()` helper using `MigrationRecorder`
- [x] `backup/services.py` -- `_copy_media_file` reworked to a manual chunked read/write loop that also accumulates a SHA-256, returning `(skip_reason_or_None, checksum_or_None)`
- [x] `backup/services.py` -- `create_export` extended: accumulate `record_counts` per model during the existing DB-write loop, accumulate `checksums` (db_export.json + each successfully-copied media file) during the existing passes, write `manifest.json` as a third zip member after both passes complete, then (after the `with zipfile.ZipFile(...)` block closes) compute the whole-archive SHA-256 via chunked read and return it as a 3rd tuple element: `(archive_path, skipped_media, archive_checksum)`
- [x] `backup/management/commands/run_backup.py` -- unpack the new 3-tuple, persist `job.archive_checksum` in the final `COMPLETED` save's `update_fields`
- [x] `backup/tests/test_services.py` -- update `_export`/`_export_with_skipped` helpers for the 3-tuple; new cases: manifest field presence/correctness (all fields, all three scope types), `record_counts` correctness, `checksums` excludes skipped media but includes `db_export.json`, `schema_version` reproducibility across two calls with no migration changes between them
- [x] `backup/tests/test_management.py` -- update the mocked `create_export` return value to a 3-tuple; new case: `job.archive_checksum` is persisted on successful completion

**Acceptance Criteria:**
- Given a completed backup of any scope type, when the archive is unzipped, then `manifest.json` is present with every field from the Boundaries list correctly populated.
- Given a media file was skipped (missing/unreadable), when the manifest is inspected, then `checksums` has no entry for it, but `record_counts` still counts its DB row.
- Given `BackupJob.archive_checksum` after a completed job, when independently hashing the actual `.zip` file on disk, then the two SHA-256 values match exactly.
- Given two backups triggered with no intervening migrations, when their manifests are compared, then `schema_version` is identical between them.

## Spec Change Log

- **Verification pass (2026-09-19) — patch-only fixes from the three-layer review (blind-hunter, edge-case-hunter, verification-gap), no spec-level ambiguity found:**
  - `_copy_media_file` now returns `arcname` alongside the checksum (computed once, never independently recomputed by `create_export`), with a duplicate-arcname guard so a second file resolving to the same archive member name never silently overwrites the first's checksum.
  - Added `manifest_version` and `checksum_algorithm` fields to `manifest.json` (additive, not in epic-1-context.md's original field list but non-contradictory — forward-compat for Epic 2's restore-side reader).
  - Added `db_index=True` to `BackupJob.archive_checksum` per CLAUDE.md's documented convention for searchable fields.
  - `_compute_schema_version()` moved to before any file I/O starts (fail-fast).
  - Added tests: `generated_by` empty when `triggered_by` is `None`, duplicate-arcname handling, `archive_checksum` stays `""` when `create_export` raises.
  - Full suite: 67/67 pass.

## Design Notes

Manual chunked copy-with-hash (replaces `shutil.copyfileobj` in `_copy_media_file`), illustrative:

```python
hasher = hashlib.sha256()
with open(source_path, "rb") as src, zf.open(arcname, "w") as dest:
    while chunk := src.read(COPY_CHUNK_SIZE):
        hasher.update(chunk)
        dest.write(chunk)
return None, hasher.hexdigest()
```

`db_export.json`'s own checksum: wrap the existing `f.write(...)` calls inside `create_export`'s DB-writing loop with the same running-hasher-update pattern, since that data is already generated incrementally.

Whole-archive checksum, after the `with zipfile.ZipFile(...)` block has closed:

```python
hasher = hashlib.sha256()
with open(archive_path, "rb") as f:
    while chunk := f.read(COPY_CHUNK_SIZE):
        hasher.update(chunk)
archive_checksum = hasher.hexdigest()
```

## Verification

**Commands:**
- `python manage.py test backup` -- expected: all existing tests (updated for the 3-tuple) plus new manifest tests pass
- `python manage.py makemigrations --check backup` -- expected: no missing migrations

## Suggested Review Order

**Manifest assembly (the core of this story)**

- Entry point: schema_version computed fail-fast, then the same single pass now also builds the manifest.
  [`services.py:306`](../../backup/services.py#L306)
- All manifest fields assembled here, after both the DB and media passes complete.
  [`services.py:443`](../../backup/services.py#L443)
- DB schema fingerprint -- a stable SHA-256 over applied migration names.
  [`services.py:292`](../../backup/services.py#L292)

**Checksum accumulation (no second read-through)**

- Media file hash accumulated inline during its one copy pass; `arcname` computed once and returned, never re-derived by the caller.
  [`services.py:247`](../../backup/services.py#L247)
- `db_export.json`'s hash accumulated via the same `_write` closure already streaming its bytes.
  [`services.py:384`](../../backup/services.py#L384)
- Duplicate-arcname guard -- the one place a second file could silently clobber an earlier checksum.
  [`services.py:421`](../../backup/services.py#L421)
- Whole-archive SHA-256 -- the one deliberate second read, only after the zip is finished.
  [`services.py:427`](../../backup/services.py#L427)

**Persistence**

- New `archive_checksum` field, indexed since it's a value an admin would look a job up by.
  [`models.py:103`](../../backup/models.py#L103)
- `run_backup.py` unpacks the 3-tuple and persists the checksum in the same final save as `status=completed`.
  [`run_backup.py:64`](../../backup/management/commands/run_backup.py#L64)

**Tests**

- Manifest field correctness across all three scope types, plus the edge cases the review pass added.
  [`test_services.py`](../../backup/tests/test_services.py#L1)
  [`test_management.py`](../../backup/tests/test_management.py#L1)

**Manual checks (if no CLI):**
- Trigger a backup, unzip the archive, `cat manifest.json` and confirm every field is populated and `record_counts`/`checksums` match the archive's actual contents; independently `sha256sum` the `.zip` and compare to `BackupJob.archive_checksum`.
