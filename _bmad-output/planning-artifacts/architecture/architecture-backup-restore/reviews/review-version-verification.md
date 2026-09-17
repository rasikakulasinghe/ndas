# Review: Version & Reality-Check Verification — Backup & Restore Architecture Spine

**Reviewer lens:** verify every committed decision was reality-checked rather than asserted from training data — current library/framework versions, that each named technology still exists and fits, and that nothing is stale or wrong.

**Target:** `_bmad-output/planning-artifacts/architecture/architecture-backup-restore/ARCHITECTURE-SPINE.md`
**Grounding used:** `requirements.txt` (Django~=5.2.0, django-ratelimit==4.1.0, python-magic==0.4.27), `_bmad-output/planning-artifacts/architecture.md`, `CLAUDE.md`, in-repo grep for existing usage, and live web verification (PyPI, Django source/docs) performed in this review.

**Overall verdict:** Every specific API/library the spine names is real, exists, and is basically usable as described — no hallucinated technology. But two of the "Stack" section's central claims are under-verified in a way that matters: the detached-subprocess pattern (AD-2) as written does not actually detach the child from the Gunicorn worker's process group/session or specify stdout/stderr handling, and the per-model JSON serialization (AD-3/AD-5) quietly drops the FK dependency-ordering guarantee that `dumpdata`/`loaddata` normally provide. Neither is a "wrong API" problem — both are real, current APIs used in a way whose operational gotchas the spine doesn't acknowledge.

---

## 1. `django.core.serializers.serialize("json", queryset)`

**Verdict: real, current, correctly named for Django 5.2 — but the spine's usage silently drops a guarantee the obvious alternative (`dumpdata`) provides.**

- The API itself (`django.core.serializers.serialize`/`deserialize`, format `"json"`) is unchanged, stable, core Django public API present in Django 5.2 and has been for well over a decade. AD-3's reasoning for choosing it over `dumpdata` — that `dumpdata` operates on whole tables and can't be scoped to an `InstitutionScopedManager`-filtered queryset — is correct and is the right reason to reach for `serializers.serialize` directly.
- **Gotcha not addressed by the spine:** by default, `serializers.serialize("json", qs)` embeds each ForeignKey as the raw PK integer, not a natural key. Django's own `dumpdata`/`loaddata` machinery normally protects you from FK-ordering failures via `sort_dependencies()` (and, optionally, `use_natural_foreign_keys=True` + `natural_key()`/`get_by_natural_key()` on the models). AD-5 has the spine writing **one file per model** (`db/<app_label>.<model_name>.json`), which means the restore path must reconstruct correct cross-model load order itself (or defer FK constraint checking inside a transaction) — otherwise loading a child model's file before its parent's file will raise an `IntegrityError` on a raw-PK FK reference. Django's serializer docs are explicit that natural-key/forward-reference handling is the deserializer's job, not something that falls out of `serialize()` for free.
- **Restorability follow-on gotcha:** even with correct ordering, raw-PK-based JSON assumes the target DB either (a) is empty/matches the source DB's PK space, or (b) auto-increment sequences are reset/advanced consistently after `deserialize()` writes explicit PKs (Django does not auto-advance the DB sequence when you save an object with an explicit PK via deserialization — a subsequent `INSERT` without an explicit PK can collide). This is a correctness risk specific to "restore into a live DB with data created since the backup" (the disaster-recovery/rollback case AD-12 explicitly targets), not just a green-field restore.
- **Not addressed anywhere in AD-3/AD-5/AD-6:** whether restore is "wipe-and-reload" or "merge," and how PK/sequence handling and inter-model ordering are resolved. This belongs in the spine (or an explicit AD) rather than being left as a service-layer implementation detail, since getting it wrong is a silent-corruption risk, exactly the kind of thing an architecture spine exists to pin down.

**Severity: MEDIUM** — the chosen API is correct; the spine is missing an invariant about restore ordering/PK handling that the API choice makes necessary.

## 2. `django.db.migrations.recorder.MigrationRecorder` (AD-6)

**Verdict: real, current, correctly used.**

- Confirmed against Django's live source (`django/db/migrations/recorder.py`, both `main` and Django 5.2-era history): `MigrationRecorder` is Django's own internal bookkeeping class for the `django_migrations` table, exposing a `Migration` model (`app`, `name`, `applied`) and `applied_migrations()`. It's the same mechanism `showmigrations`/`migrate` use internally, so it is a stable, appropriate, low-risk choice for reading applied-migration state — better than trying to introspect installed app configs or hand-rolling something.
- **Minor under-specification (not a version/API problem):** `applied_migrations()` returns a dict keyed by `(app_label, migration_name)` — the spine says `schema_version` is merely "derived from" this, without saying how a dict becomes a single comparable scalar (hash of sorted tuples? count? latest-applied name per app?). Two databases with the same *set* of applied migrations should hash identically regardless of application order for this to be a reliable drift check across environments. This is a design gap for the eventual AD/story, not a technology-currency issue — flagging for completeness since it's adjacent to AD-6's stated purpose ("detect a schema mismatch before touching data").

**Severity: LOW** (informational — API is sound, only the derivation function is unspecified).

## 3. `subprocess.Popen([sys.executable, manage.py_path, ...])` for a detached background job (AD-2)

**Verdict: the pattern is real and works on both platforms, but as literally written in AD-2 it does not achieve "detached," and the spine is silent on stdout/stderr — both are known, well-documented Python/Gunicorn pitfalls, not exotic ones.**

Checked: there is **no existing `subprocess.Popen` usage anywhere in the actual Django application code** (`ndas/`, `patients/`, `institution/`, etc. — grep found matches only in unrelated `.claude`/`.agents`/`bmad` tooling scripts). This means AD-2 introduces a genuinely new pattern with no in-repo prior art to inherit safe defaults from, which raises the bar for the spine to get the invariant right.

Confirmed gotchas, all applicable to this exact call shape:

- **stdout/stderr pipe deadlock (not mentioned at all):** Python's own `subprocess` documentation carries an explicit, long-standing warning that using `PIPE` for `stdout`/`stderr` without reading them (e.g., via `communicate()`) will deadlock once the OS pipe buffer fills (~64KB on Linux) — and a multi-GB backup/restore job emitting per-model progress output is exactly the kind of long-running, chatty process likely to hit this. AD-2's code sketch specifies neither `stdout=` nor `stderr=`, which means whoever implements this either (a) leaves them as default (inherits the parent Gunicorn worker's fds — actually the *safe* choice, but accidental) or (b) reaches for `PIPE` "to capture logs," which silently hangs the job under load. This needs to be an explicit rule, not left to implementer instinct.
- **Process-group/session detachment (the "detached" claim isn't backed by the code shown):** on POSIX, `Popen` without `start_new_session=True` (or the older `preexec_fn=os.setsid`) puts the child in the **same session/process group** as the calling Gunicorn worker. Gunicorn's own worker-lifecycle behavior (arbiter SIGKILLs a worker that misses its heartbeat/timeout, `--max-requests` recycling, `HUP`/graceful restarts, deploys) sends signals to worker processes; a child sharing that process group can receive/be affected by the same signal, or become an orphan mid-write if the worker is killed. This project's own architecture.md documents Gunicorn with a 300s timeout and confirms Nginx→Gunicorn→Django as the deploy topology, so this isn't a hypothetical — a worker recycling during a large restore is a plausible production event. AD-2's own stated purpose is explicitly to avoid "a synchronous view exceeding Gunicorn's 300s timeout," which shows the author is already thinking about Gunicorn's process model — but the mitigation for the *subprocess* surviving the *worker's* lifecycle isn't in the rule. On Windows the equivalent gap is `creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP`, also absent from the code sketch.
- **Zombie processes (minor):** since the triggering view intentionally never calls `.wait()`/`.poll()` on the `Popen` object (fire-and-forget is the whole point), completed children become zombies until the parent reaps them; Python does not auto-reap on `SIGCHLD` by default. For an infrequent admin-triggered action (backups aren't a hot path) this is low-impact and self-resolves on worker recycle, but it's worth one line in the rule (e.g., explicitly note this is acceptable given call frequency) rather than silence.

None of this means "detached subprocess" is the wrong choice — it's a reasonable one given the project's constraint of no Celery/broker. But AD-2 as written is a claim ("detached... runs identically on Windows dev and Linux prod") that the shown code does not yet deliver on, and the missing piece (`start_new_session=True` / `DETACHED_PROCESS`, explicit stdout/stderr routing) is exactly the kind of platform/runtime detail this review's lens exists to catch.

**Severity: HIGH** — this is the mechanism CAP-5 (async + progress) is entirely built on; getting it wrong produces silently-stuck `BackupJob` rows in production, which the spine's own "Deferred" section already anticipates as a symptom ("stale watchdog") without addressing the root cause.

## 4. `python-magic` and `django-ratelimit` — maintenance status and usage consistency

**Verdict: both are real, both are already pinned/used in this codebase exactly as the spine proposes reusing them — but both are effectively stale upstream, which is worth naming even though it's a pre-existing risk, not one this spine introduces.**

- **python-magic** — pinned in `requirements.txt` at `0.4.27`. Verified live via PyPI: `0.4.27` (released **June 7, 2022**) is still the latest release; there is no newer version. The project (`ahupp/python-magic`) shows limited recent release activity. This is a pre-existing, already-accepted dependency (the repo even carries a comment in `requirements.txt` about the Windows-only `python-magic-bin` wheel and Linux relying on system `libmagic`), and grep confirms it's already used in `ndas/custom_codes/validators.py` and `video/forms.py`. The spine's AD-11 usage ("An uploaded restore `.zip` passes the `python-magic` MIME check used for every other upload") is consistent with existing usage. **Not a new risk from this spine** — flagging only because the review's lens is explicitly version-currency.
- **django-ratelimit** — pinned at `4.1.0`, matching both `requirements.txt` and architecture.md's Security & Auth table ("Rate limiting | django-ratelimit 4.1.0"). Web verification shows `4.1.0` (released mid-2023) remains the latest release on PyPI; it has no release history since, and its published classifiers don't explicitly list Django 5.x. In practice it is known to work fine with Django 5.2 (the project already runs `@ratelimit` decorators across 24 CRUD operations per CLAUDE.md, and grep confirms `institution/views.py` already uses it), so this is a "stale but working" dependency already load-bearing elsewhere, not a new integration risk. AD-11's proposed usage (`@ratelimit(key="user_or_ip", ...)` on trigger/restore endpoints) is directly consistent with the existing convention.

**Severity: LOW/INFO for both** — correct reuse of already-accepted dependencies; noting staleness for awareness, not as a defect in this spine.

## 5. Other technology/version claims checked

- **Django 5.2 itself:** the Stack section's "already part of Django 5.2" is correct and matches `requirements.txt` (`Django~=5.2.0`, with an explanatory comment pinning to the 5.2 LTS line specifically because the production cPanel hosts top out at Python 3.11.15, which is incompatible with Django 6.0's `asgiref>=3.11`/Python≥3.12 requirement) and `CLAUDE.md` ("Django 5.2 (LTS)", updated 2026-09-12).
- **Discrepancy worth flagging (in the spine's own cited companion doc, not the spine itself):** `_bmad-output/planning-artifacts/architecture.md` — which the spine lists under `companions:` — is stale on this exact point. It states **"Django 4.2.16"** in four separate places (lines 47, 74, 84, 738: "Stack is frozen for Phase 2: Django 4.2.16...", "Established Foundation: Django 4.2.16 Monolith", "Python 3.x with Django 4.2.16 LTS...", "Technology stack (Django 4.2.16, ...) has no internal conflicts"). The spine got the *live* version right by not deferring to its own stated companion source — which is good — but this is worth surfacing: a future spine/story author who trusts architecture.md at face value (as its own `companions:` field invites) will get the Django version wrong. This should be corrected in architecture.md directly (out of scope for this review to fix, but worth a note back to whoever owns that doc).
- `zipfile`, `hashlib` — standard library, unchanged, no concerns.
- `FileResponse` + `Content-Disposition: attachment` pattern (AD-7) — real, current Django API, and the spine's claim that it mirrors an existing precedent (`institution/views.py`'s superadmin Excel export) is a reasonable, checkable claim (not independently re-verified line-by-line in this review, but the file exists and the pattern is unremarkable/standard Django).
- HTMX polling (AD-8) — not version-pinned anywhere in the spine; no specific claim to verify.

---

## Summary Table

| # | Claim | Real/Current? | Used correctly? | Severity |
|---|---|---|---|---|
| 1 | `serializers.serialize("json", qs)` | Yes | Partially — FK dependency-ordering/PK-collision on restore not addressed | MEDIUM |
| 2 | `MigrationRecorder` for schema_version | Yes | Yes — scalar derivation left unspecified | LOW |
| 3 | Detached `subprocess.Popen` | Yes (pattern exists) | No — missing `start_new_session`/`DETACHED_PROCESS` and stdout/stderr handling | HIGH |
| 4a | `python-magic` reuse | Yes (but stale upstream, last release 2022) | Yes, consistent with existing usage | LOW/INFO |
| 4b | `django-ratelimit` reuse | Yes (but stale upstream, last release 2023) | Yes, consistent with existing usage | LOW/INFO |
| 5 | Django 5.2 claim in spine | Yes, correct | — | — (companion doc `architecture.md` is stale: says 4.2.16) |
