# Review — Version Verification

**Target:** `ARCHITECTURE-SPINE.md` (architecture-NDAS-2026-10-01)
**Reviewer scope:** every version/technology claim in the "Stack" table, plus supporting prose, checked against `requirements.txt`, `ndas/settings.py`, `DEPLOYMENT.md`, `docs/architecture.md`, `docs/project-overview.md`, and the committed `static/vendor/*` frontend assets.
**Method:** repo-as-source-of-truth (brownfield ratification, not web lookup), per task instructions.

## Verdict: PASS WITH NOTES

All pip-installable package versions in the Stack table are verified, byte-for-byte accurate, against `requirements.txt`. The Django/Python/cPanel compatibility narrative is verified accurate against both `requirements.txt` comments and `DEPLOYMENT.md`. However, the three "no pinned version tracked" frontend entries (HTMX, Video.js, and implicitly AdminLTE/Bootstrap/Font Awesome) were not checked against the actual committed vendor files in `static/vendor/`, where exact versions are trivially readable — two of them (HTMX, Video.js) were left as unverified gaps in the spine when verification was one `head`/`grep` away. There is also one Deferred-section omission (Redis client pinning) that is the same class of gap the spine already caught for Postgres, but missed for Redis.

## Findings

### 1. [MODERATE] HTMX and Video.js versions were available in-repo but not verified — spine states "no pinned version tracked" as if that's the end of the story

- **Spine claim (line 153, 154):**
  `HTMX | (dynamic partials; no pinned version tracked in requirements.txt)`
  `Video.js | (video playback; no pinned version tracked in requirements.txt)`
- **Reality:** This is true only of `requirements.txt` (a Python package manifest — HTMX/Video.js are frontend JS, so of course they aren't there). But the actual files are committed in the repo at `static/vendor/htmx/htmx.min.js` and `static/vendor/videojs/video.min.js`, and both carry their version in plain text:
  - `static/vendor/videojs/video.min.js` — header comment: `Video.js 8.10.0 <http://videojs.com/>`
  - `static/vendor/htmx/htmx.min.js` — embedded string: `version:"1.9.12"`
- **Why it matters:** The spine's own `sources:` frontmatter lists `docs/architecture.md, docs/project-overview.md, CLAUDE.md, ndas/settings.py, requirements.txt, DEPLOYMENT.md` — it never lists the `static/vendor/` tree, which is why this was missed. But the task brief for this spine was explicitly to "ratify brownfield reality," and the reality (exact pinned frontend versions) was sitting in a comment at the top of a committed file. This reads as an assumption ("untracked, therefore unknowable") dressed as fact, when a two-second check would have produced an exact version.
- **Recommendation:** Update the Stack table to `HTMX | 1.9.12 (vendored at static/vendor/htmx/htmx.min.js; self-hosted, no npm/pip pin)` and `Video.js | 8.10.0 (vendored at static/vendor/videojs/video.min.js; self-hosted, no npm/pip pin)`.

### 2. [LOW] AdminLTE/Bootstrap/Font Awesome versions are correct but were apparently not cross-checked against the vendored files either — got the right answer, for reasons that aren't evidenced

- **Spine claims:** AdminLTE 3.2, Bootstrap 4.6, Font Awesome 6.4 — all match the committed vendor CSS header comments exactly:
  - `static/vendor/adminlte/css/adminlte.min.css` → `AdminLTE v3.2.0`
  - `static/vendor/bootstrap/css/bootstrap.min.css` → `Bootstrap v4.6.2`
  - `static/vendor/fontawesome/css/all.min.css` → `Font Awesome Free 6.4.0`
- **Minor wrinkle (not a spine error):** `adminlte.min.css` bundles its own copy of Bootstrap CSS headed `Bootstrap v4.6.1`, one patch behind the standalone `bootstrap.min.css` at `v4.6.2`, served separately. Both round to "4.6" so the spine's single entry is still accurate, but this is worth a footnote if anyone later asks "why do two different 4.6.x strings show up in grep."
- **Severity rationale:** These three entries happen to be correct, so this is not a factual error — but combined with finding #1, it suggests the frontend vendor tree as a whole was not a verification pass, and these three just happened to match pre-existing CLAUDE.md prose rather than being independently re-derived from `static/vendor/`.

### 3. [LOW] Deferred section catches the Postgres-driver gap but misses an analogous Redis-client gap

- **Spine's existing Deferred entry (accurate):** "No `psycopg`/`psycopg2` is pinned in `requirements.txt` despite `settings.py` supporting a full Postgres branch for VPS deploys."
- **What's missing:** `ndas/settings.py` (lines ~405–413) has a parallel full Redis branch — `CACHES['default']['BACKEND'] = 'django.core.cache.backends.redis.RedisCache'` with `'CLIENT_CLASS': 'django_redis.client.DefaultClient'` under `OPTIONS` — gated on `REDIS_URL` being set, exactly like the Postgres branch is gated on `DB_ENGINE`. But `requirements.txt` has no `redis` and no `django-redis` package anywhere. (Django's built-in `redis.RedisCache` backend needs the `redis` pip package at minimum; the `CLIENT_CLASS` option referenced is actually a `django-redis`-specific option that Django's built-in backend doesn't consume — a second, unrelated latent bug worth a separate ticket, not a spine issue.)
- **Why it matters here:** This is the exact same category of brownfield gap the spine already flagged for Postgres (code path exists, dependency doesn't), and the spine's own Stack table entry — `Redis | optional — prod cache/session backend when configured` — presents the Redis path as a working configured option without noting that, as pinned, `pip install -r requirements.txt` would not actually make that branch functional.
- **Recommendation:** Add a Deferred bullet mirroring the Postgres one: "No `redis`/`django-redis` pinned despite `settings.py` CACHES/SESSION_ENGINE branches on `REDIS_URL`; revisit before relying on the Redis path, and reconcile the `CLIENT_CLASS: django_redis...` option against the built-in `django.core.cache.backends.redis.RedisCache` backend actually selected."

### 4. [INFO — confirms spine is correct] All requirements.txt-sourced versions and the Django/Python/cPanel narrative check out exactly

Verified identical, line for line, against `requirements.txt`:
`Django~=5.2.0`, `bleach==6.3.0`, `openpyxl==3.1.5`, `reportlab==4.4.3`, `django-ratelimit==4.1.0`, `django_csp==3.8`, `whitenoise==6.9.0`, `django-cleanup==7.0.0`, `python-magic==0.4.27` (+ `python-magic-bin==0.4.14; sys_platform=="win32"`, matching the spine's "(+ python-magic-bin, win32 only)" parenthetical), `moviepy==2.2.1`, `playwright==1.55.0`.

The "pinned off 6.0 — cPanel hosts top out at Python 3.11.15, Django 6.0 needs >=3.12" claim is verified word-for-concept against both the `requirements.txt` inline comment (lines 21–24) and `DEPLOYMENT.md` line 21 and line 616, which state the identical constraint independently in two places. "Python 3.10+ (3.11 recommended)" matches `DEPLOYMENT.md` line 21 exactly. "Database (VPS/prod option) PostgreSQL 12+" matches `DEPLOYMENT.md` line 22 exactly.

The Deferred section's "Stale brownfield docs" claim — that `docs/architecture.md`/`docs/project-overview.md` say Django 4.2.16/Python 3.9+ and omit the `backup` app — is independently verified: `docs/project-overview.md` line 20–21 literally states `Framework | Django 4.2.16` / `Language | Python 3.9+`, and a search for "backup" in that file returns zero matches.

## What was NOT found to be a problem

- No deprecated/abandoned package is being enshrined: bleach, openpyxl, reportlab, django-ratelimit, django_csp, whitenoise, django-cleanup, python-magic, moviepy, playwright, Django 5.2 LTS, AdminLTE 3.2/Bootstrap 4.6/Font Awesome 6.4/HTMX/Video.js are all actively maintained as of the stated dates, and each still fits its stated purpose in the Stack table (no scope mismatch, e.g. nothing here is a frontend router being misused as a templating engine, etc.).
- No version number in the Stack table appears to be fabricated or hallucinated from training-data defaults — every number present traces to either `requirements.txt` or `DEPLOYMENT.md`/`settings.py`. The only gap is the two entries that were left *blank with an explanation* (HTMX, Video.js) rather than filled with a fabricated-sounding number — which is the right failure mode (honest "untracked" beats a guessed version), but as finding #1 shows, the "untracked" framing itself wasn't fully earned since the real versions were one file-read away.
