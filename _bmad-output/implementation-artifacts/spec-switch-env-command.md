---
title: 'One-command dev/production .env switching'
type: 'feature'
created: '2026-09-04'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'a7be2d9e46a2e1e41b941777d611c352b3520a4c'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Switching NDAS locally between development and production requires manual `cp` + hand-editing of `.env`, with no backup step — a switch can silently destroy locally-tuned settings. No single documented workflow exists.

**Approach:** Add `python scripts/switch_env.py <mode>`: backs up the current `.env`, copies the matching template from `env files/`, prints what changed. Update `env files/.env.README.md` to document it as the primary workflow, keeping manual `cp` as fallback.

## Boundaries & Constraints

**Always:**
- Back up existing root `.env` (if present) before overwriting — timestamped, never silently discarded.
- Read templates only from `env files/` (confirmed canonical this session). Never touch `setup env files/` (out of scope draft).
- Implement as a plain stdlib script, not a Django management command — `ndas/settings.py:10` does `SECRET_KEY = config('SECRET_KEY')` with no default, so `python manage.py` crashes on a missing/broken `.env` before any command runs. A plain script has no such bootstrap dependency and can repair a broken `.env`.
- On switching to a production mode, print a reminder to fill in real secrets (`SECRET_KEY`, `DB_PASSWORD`, `EMAIL_HOST_PASSWORD`, `ALLOWED_HOSTS`) — never auto-fill them.
- Must run identically via `python scripts\switch_env.py <mode>` (PowerShell) and the Bash equivalent.

**Ask First:** none anticipated — additive tooling, no runtime/app code touched.

**Never:** commit `.env` or its backups; modify `env files/` template contents; touch `setup env files/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Switch mode | `switch_env.py development\|production\|production-postgresql`, `.env` exists | Backs up old `.env` to `.env_backups/`, overwrites with matching template, confirms mode (+ secrets reminder for production modes) | N/A |
| No `.env` yet | `.env` absent | Skips backup, creates `.env` from template, confirms | N/A |
| Unknown mode / no argument | e.g. `switch_env.py staging` or bare `switch_env.py` | N/A | Print usage + valid mode list, exit non-zero, `.env` untouched |
| Missing template | Template file not found under `env files/` | N/A | Print error naming the missing path, exit non-zero, `.env` untouched |

</frozen-after-approval>

## Code Map

- `scripts/switch_env.py` -- NEW. Standalone script, matching convention of `scripts/security_audit.py` / `scripts/benchmark_dashboard.py` (plain script, docstring header, stdlib only, no test harness precedent to match). `BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))`.
- `ndas/settings.py:4,10,13,15,83-92` -- READ ONLY. Confirms decouple-read vars (`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DB_*`) and that `SECRET_KEY`/DB creds have no defaults — why this must be a plain script.
- `env files/.env.example`, `.env.development.example`, `.env.production.example`, `.env.production.postgresql.example` -- READ ONLY source templates.
- `.env` (repo root) -- WRITE target; back up then replace.
- `.gitignore:6` -- ignores exact filename `.env` only. ADD `.env_backups/` entry.
- `env files/.env.README.md` -- UPDATE: add one-command workflow to top of Quick Start; keep manual `cp` steps below as fallback.
- `scripts/tests/test_switch_env.py` -- NEW. Stdlib `unittest` coverage of the I/O & Edge-Case Matrix, added in the patch-fix pass (see Tasks & Acceptance) after review flagged the backup-before-overwrite guarantee as having zero automated coverage.

## Tasks & Acceptance

**Execution:**
- [x] `scripts/switch_env.py` -- create, accepting one positional mode arg (`development`|`production`|`production-postgresql`), mapping to templates in `env files/`, backing up existing `.env` to `.env_backups/.env.<ISO-timestamp>.bak`, copying template to `.env`, printing confirmation + production secrets reminder -- delivers the one-command switch
- [x] `.gitignore` -- add `.env_backups/` -- keeps backups out of version control
- [x] `env files/.env.README.md` -- add "Switching Modes (Recommended)" section documenting the command + mode table, above existing manual steps -- delivers the guidance doc ask
- [x] Manually run all four I/O-matrix scenarios and record the transcript under Verification -- no existing `scripts/` test harness to extend

**Patch-fix pass (post-review, auto-fix, all applied):**
- [x] Wrap `os.makedirs(BACKUP_DIR, ...)` and both `shutil.copyfile()` calls in `try/except OSError`; on failure print a clear stderr error and return 1 without touching `.env`. A failure in the template->`.env` copy (which happens after the backup already succeeded) names the existing `backup_path` in the error so the user can recover manually.
- [x] Made backup filenames collision-safe: `_unique_backup_path()` appends an incrementing `-N` suffix if the second-granularity timestamped path already exists, so two switches within the same second never clobber one backup with another.
- [x] Reworded the production reminder heading from "fill in real secrets" to "review these production values before deploying", since `ALLOWED_HOSTS` (included in the list) is config, not a secret.
- [x] Added a `production-postgresql`-only reminder to run `python manage.py migrate` against the new database, since swapping `.env` alone doesn't create/update its schema.
- [x] Aligned the mode->template mapping spacing consistently across the module docstring, the argparse `--help` epilog, and confirmed the README table needs no equivalent change (Markdown tables render from `|` delimiters, not manual spacing).
- [x] `env files/.env.README.md` -- corrected the "prints what changed" claim (script reports mode/template/backup path, not a value-level diff); added "Restart required" (Django/decouple read `.env` once at process start), "Restoring a backup" (copy the desired file from `.env_backups/` back over `.env`), and "Backup contents are plaintext" (git-ignored but not otherwise protected) notes.
- [x] `scripts/tests/test_switch_env.py` -- NEW, stdlib `unittest` only. Sandboxes `switch_env`'s module-level path constants (`BASE_DIR`/`ENV_FILES_DIR`/`BACKUP_DIR`/`TARGET_ENV`) into a temp dir with fake templates and covers: each of the 3 modes (backup preserves original content + new `.env` exactly matches that mode's template), no existing `.env` (no backup, `.env` created, exit 0), unknown mode / missing argument (`.env` byte-for-byte untouched, non-zero exit, checked both with and without a pre-existing `.env`), and missing template (`.env` untouched, exit 1, error names the missing path). Run directly with `python scripts/tests/test_switch_env.py`.
- Explicitly deferred (logged to `deferred-work.md`, not implemented here): restore/rollback subcommand, backup pruning/rotation, an "already in this mode" idempotency check, a dry-run/preview option, an interactive confirmation prompt before production switches.

**Acceptance Criteria:**
- Given a dev `.env`, running `switch_env.py production` backs it up under `.env_backups/`, makes `.env` match `env files/.env.production.example`, and prints the new mode + secrets reminder.
- Given no `.env`, running `switch_env.py development` creates one from the development template with no false backup claim, exit 0.
- Given an invalid mode, `.env` is left untouched and the script exits non-zero listing valid modes.

## Design Notes

Stdlib only (`os`, `sys`, `shutil`, `datetime`) so the script never depends on the `.env`/Django bootstrap it may be repairing. CLI arg uses a hyphen (`production-postgresql`) though templates/settings use other separators — document this mapping in both `--help` text and the README table.

## Verification

**Commands:**
- `python scripts\switch_env.py development` -- `.env` matches `env files\.env.development.example`; backup created
- `python scripts\switch_env.py production` -- `.env` matches `env files\.env.production.example`; secrets reminder printed
- `python scripts\switch_env.py bogus-mode` -- non-zero exit, `.env` unchanged, valid modes printed
- `python manage.py check` (after switching to development) -- no errors, confirms new `.env` boots Django

**Manual checks (if no CLI):**
- Regenerated `.env` has no leftover values from the previous mode (e.g. dev→production shouldn't still show `DEBUG=True`).

## Suggested Review Order

**Mode dispatch & template resolution**

- Entry point — orchestrates validate template, back up, copy, report for every invocation.
  [`switch_env.py:124`](../../scripts/switch_env.py#L124)

- Single source of truth mapping CLI mode names to template filenames under `env files/`.
  [`switch_env.py:37`](../../scripts/switch_env.py#L37)

**Backup safety guarantee**

- Never silently discards the prior `.env` — the feature's core promise.
  [`switch_env.py:95`](../../scripts/switch_env.py#L95)

- Collision-safe backup naming so two switches in the same second don't clobber each other.
  [`switch_env.py:78`](../../scripts/switch_env.py#L78)

**Failure handling (patch-fix pass)**

- A failed backup step leaves `.env` completely untouched.
  [`switch_env.py:133`](../../scripts/switch_env.py#L133)

- A failed template copy (after backup already succeeded) points the user at that backup for manual recovery.
  [`switch_env.py:140`](../../scripts/switch_env.py#L140)

**CLI surface & production reminders**

- `argparse` choices give a clean error + valid-mode list for bad input, no traceback.
  [`switch_env.py:70`](../../scripts/switch_env.py#L70)

- Production reminder reworded so non-secret `ALLOWED_HOSTS` isn't labeled a secret.
  [`switch_env.py:165`](../../scripts/switch_env.py#L165)

- `production-postgresql`-only reminder to run `migrate` — swapping `.env` alone doesn't touch the schema.
  [`switch_env.py:172`](../../scripts/switch_env.py#L172)

**Documentation**

- New one-command workflow documented as primary, manual `cp` kept as fallback below it.
  [`.env.README.md:7`](../../env%20files/.env.README.md#L7)

**Peripherals**

- Automated regression coverage for the I/O & Edge-Case Matrix, replacing reliance on the one-time manual transcript.
  [`test_switch_env.py:32`](../../scripts/tests/test_switch_env.py#L32)

- Keeps timestamped backups (which may contain real secrets once used against a live `.env`) out of version control.
  [`.gitignore:7`](../../.gitignore#L7)

**Transcript (2026-09-04, real root `.env` snapshotted first and restored byte-for-byte after -- checksum verified):**

1. `python scripts/switch_env.py development` (existing dev `.env` present) -- exit 0; `diff .env "env files/.env.development.example"` empty (match); printed `Previous .env backed up to: .env_backups\.env.2026-09-04T14-08-10.bak`.
2. `python scripts/switch_env.py production` (existing `.env` present) -- exit 0; `diff .env "env files/.env.production.example"` empty (match); printed backup path + secrets reminder block (`SECRET_KEY`, `DB_PASSWORD`, `EMAIL_HOST_PASSWORD`, `ALLOWED_HOSTS`).
3. Removed `.env`, then `python scripts/switch_env.py development` -- exit 0; `.env` created and matches template; printed `No existing .env found -- created a new one (no backup needed).`; backup count in `.env_backups/` unchanged (no false backup).
4. `python scripts/switch_env.py bogus-mode` -- exit 2; argparse usage + `choose from development, production, production-postgresql`; `.env` md5 unchanged before/after.
   `python scripts/switch_env.py` (bare) -- exit 2; usage + `the following arguments are required: mode`; `.env` md5 unchanged.
5. (Extra, beyond the matrix) Temporarily renamed `env files/.env.production.example` away, then `python scripts/switch_env.py production` -- exit 1; `ERROR: template not found: ...\env files\.env.production.example` / `.env was left untouched.`; md5 confirmed unchanged. Template renamed back immediately after.
6. `python scripts/switch_env.py --help` -- prints usage, mode choices, and the CLI-mode -> template-filename mapping table.
7. Switched to `development`, then `venv\Scripts\activate && python manage.py check` -- `System check identified no issues (0 silenced).`
8. Restored the original root `.env` from a pre-test snapshot; md5 matched the pre-test value (`fe13a7c4...`), confirming no net change to the developer's real `.env`.

9. Audit follow-up: the "Switch mode" matrix row bundles three sub-scenarios but only `development`/`production` had been exercised. Ran `python scripts/switch_env.py production-postgresql` (real `.env` snapshotted first) -- exit 0; `diff .env "env files/.env.production.postgresql.example"` empty (match); backup created; secrets reminder printed. `.env` restored from snapshot immediately after; `.env_backups/` removed.

All four I/O-matrix scenarios (including all three `switch mode` sub-variants) and both acceptance-criteria checks passed as specified.

**Automated test run (added in the patch-fix pass, `scripts/tests/test_switch_env.py`, stdlib `unittest`, sandboxed temp dir -- never touches the real repo `.env`):**

```
$ python scripts/tests/test_switch_env.py
test_missing_template_leaves_env_untouched_exit_1_names_path ... ok
test_no_existing_env_creates_from_template_no_backup ... ok
test_each_mode_backs_up_and_switches ... ok
test_missing_mode_argument_leaves_env_untouched_and_exits_nonzero ... ok
test_unknown_mode_leaves_env_untouched_and_exits_nonzero ... ok
test_unknown_mode_with_no_env_leaves_it_absent ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.046s

OK
```

All 6 tests passed (PASS). Ad hoc scripts (not committed, sandboxed temp dirs, run and discarded during this session) additionally confirmed: (a) collision-safe backup naming under a frozen clock -- two switches with an identical timestamp produced two distinct backup files (`....bak` and `....-1.bak`) each preserving the correct original content; (b) the OSError-guard path -- a simulated failure in the template->`.env` copy (forced *after* the backup succeeded) left `.env` at its pre-switch content, returned exit 1, and the stderr message named the exact backup path to recover from.

**Re-verification transcript (2026-09-04, after the patch-fix pass; real root `.env` snapshotted first and restored byte-for-byte after -- checksum `fe13a7c4ab628caa15d6fd304fb12a34` verified unchanged before/after):**

1. `switch_env.py development` (existing `.env`) -- exit 0, `.env` matches template, backup created.
2. `switch_env.py production` (existing `.env`) -- exit 0, `.env` matches template; reminder now reads "review these production values before deploying" (no longer mislabels `ALLOWED_HOSTS` as a secret).
3. `switch_env.py production-postgresql` (existing `.env`) -- exit 0, `.env` matches template; production review reminder printed, plus the new `python manage.py migrate` reminder.
4. Removed `.env`, `switch_env.py development` -- exit 0, `.env` created from template, no false backup claim (backup count unchanged from step 1-3's 3 files).
5. `switch_env.py bogus-mode` and bare `switch_env.py` -- both exit 2, usage + valid-mode list, `.env` md5 unchanged before/after.
6. `switch_env.py --help` -- mode->template mapping now consistently aligned (`development`, `production`, `production-postgresql` columns line up).
7. Missing-template case (`env files/.env.production.example` renamed away, then restored) -- exit 1, error names the missing path, `.env` md5 unchanged.
8. Switched to `development`, `venv\Scripts\activate && python manage.py check` -- `System check identified no issues (0 silenced).`
9. Restored the real root `.env` from the pre-test snapshot; md5 matched (`fe13a7c4ab628caa15d6fd304fb12a34`); test-only `.env_backups/` and `scripts/__pycache__/` removed afterward.

No regressions found. All patch-level findings applied and re-verified.
