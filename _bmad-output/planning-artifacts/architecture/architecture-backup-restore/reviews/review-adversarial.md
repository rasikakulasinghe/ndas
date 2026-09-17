# Adversarial Review — Backup & Restore Spine Amendment (single `db_export.json`, AD-18, AD-19)

**Reviewed:** `ARCHITECTURE-SPINE.md` (architecture-backup-restore, updated 2026-09-17)
**Scope:** AD-3 (amended), AD-5 (amended), AD-6 (amended), AD-18 (new), AD-19 (new), and their interaction with unchanged AD-2, AD-8, AD-14, AD-16.
**Lens:** two units one level down (e.g. an export/writer engineer and a restore/reader engineer) who each follow every AD to the letter, checked against the actual model code (`patients/models.py`, `problemlist/models.py`, `video/models.py`, `institution/managers.py`) rather than assumed shapes.

**Verdict up front:** the single-`db_export.json` shape and the Problem→ProblemAction two-level remap are both genuinely closed — AD-5 and AD-19 point 4 name them explicitly and correctly. But the amendment's PK-remap table is **incomplete against the real model graph**, not just ambiguous: it omits two FK relationships that provably exist in code (`Patient.institution`, `GMAssessment.video_file`) and one identifier field (`Patient.pin`) that participates in the same uniqueness family AD-19 already reasons about for the other four. These are not places where two careful implementers diverge — a competent implementer following AD-19 exactly, with no deviation, ships a restore that corrupts institution scoping and/or crashes on any archive containing a GMAssessment. In addition, AD-19's single-giant-transaction requirement is in real, unaddressed tension with AD-8's polling model and AD-16's "relatively brief" justification for its accepted residual risk, and AD-18's multi-institution composition relies on a manager method that only accepts one institution at a time.

---

## Finding 1 — `GMAssessment.video_file` (a `OneToOneField` to `Video`) has no remap rule at all

**Severity: Critical**

`patients/models.py:863` — `GMAssessment.video_file = models.OneToOneField("video.Video", on_delete=models.CASCADE)`. This is a second direct FK from a cascade model to *another cascade model being imported in the same batch* (Video), structurally identical in kind to the `Problem`→`Patient` and `ProblemAction`→`Problem` relationships AD-19 does handle — but AD-19 point 4 only names two remap tables: `patient` and `problem` (via a `Problem` source-PK→new-PK map). It never establishes a `Video` source-PK→new-PK map, and never instructs remapping `GMAssessment.video_file`.

Consequence for an implementer following AD-19 to the letter: `Video` rows are imported with `pk=None` (fresh target-DB PK, per point 4's general rule), so the archived `GMAssessment.fields.video_file` value (the *source* Video's PK) almost certainly does not identify the correct row in the target DB. One of two things happens, both bad:
- The source PK doesn't exist in the target DB at all → `IntegrityError` on the `GMAssessment` insert, which — because AD-19 point 4 wraps "the entire apply step" in one transaction — aborts and rolls back the *whole* import-set, not just this one patient.
- The source PK happens to collide with an unrelated `Video` row already in the target DB. Since `video_file` is a `OneToOneField`, if that row is already claimed by another `GMAssessment`, the insert raises a uniqueness `IntegrityError` (same whole-batch-abort outcome); if it isn't yet claimed, the newly-imported `GMAssessment` silently attaches to the **wrong patient's video** — a clinical-data-integrity and PHI-boundary failure of exactly the kind AD-3 states it exists to prevent.

Video is processed before GMAssessment in the fixed dependency order, so a Video PK-remap table *could* be built in time — AD-19 simply never says to build or use one.

**Fix needed:** AD-19 point 4 must add a `Video` source-PK→new-PK map (built as `Video` rows are inserted, symmetric with the `Problem` map) and explicitly require remapping `GMAssessment.video_file` through it before save.

---

## Finding 2 — `Patient.institution` is never remapped, only matched by slug

**Severity: Critical**

AD-19 point 4's remap enumeration is closed: "remap any FK field that points at another object being imported in this same batch (`patient`, or `problem`...)". `Institution` rows are explicitly *not* imported by restore ("`Institution` rows are never created by restore... matched by slug"), so by the letter of the rule, `institution` is not "another object being imported in this same batch" and is not on the remap list.

But every archived `Patient` record's `fields.institution` value is the **source** DB's `Institution` PK. Source and target `Institution` PKs are ordinary auto-increment integers with no reason to coincide across two separate deployments (or even the same deployment after institutions were added/removed in a different order). AD-19 never states that, after resolving the target institution by slug, its PK must be substituted into every imported `Patient.institution` field before save. A literal implementation therefore either:
- leaves the source PK verbatim, silently attaching newly-imported patients to whichever institution happens to occupy that PK slot in the target DB (a cross-institution PHI leak — the exact failure AD-3 names as its own "Prevents" reason), or
- fails outright with an FK constraint violation if no institution has that PK in the target DB, again aborting the whole batch transaction.

This gap sits directly beside AD-18's own multi-institution question (Finding 5) — both stem from AD-19 treating "target institution" as settled once matched by slug, without tracing that resolved value into the rows being written.

**Fix needed:** AD-19 must add `institution` (on `Patient`) to the explicit remap set: resolve the target `Institution` by slug once, then set every imported `Patient.institution_id` to that resolved PK — not the archived source PK — before save.

---

## Finding 3 — `Patient.pin` is a fifth unique-if-set identifier AD-19's conflict-match ignores

**Severity: High**

`patients/models.py` defines five fields with `unique=True, null=True, blank=True`: `bht`, `nnc_no`, `ptc_no`, `pc_no`, and **`pin`** (PIN — Patient Identification Number). AD-19's match step checks only the first four. A record with `bht`/`nnc_no`/`ptc_no`/`pc_no` all null but a populated `pin` that already exists on a target-DB patient is, per AD-19's literal rule, "unmatchable" and "always treated as new" — then, per point 4's single-transaction import, the insert hits the target DB's `unique=True` constraint on `pin` and raises `IntegrityError`, rolling back the *entire* batch (every other, unrelated patient in the date-scoped archive included) because of one overlooked identifier on one patient.

This is not an implementer-divergence hole — the AD text is unambiguous, and any implementer who follows it correctly still ships this bug. It's a completeness gap in the AD itself, made worse by AD-19 point 4's all-or-nothing transaction (Finding 6): the blast radius of one missed field is the whole import, not one row.

**Fix needed:** either add `pin` to AD-19's match-field list (fifth priority, or explicitly excluded with a stated reason if PIN is deliberately not meant to disambiguate patients across institutions), and separately decide what happens on an unexpected unique-constraint collision during the import phase (per-patient savepoint + skip-with-warning, vs. current whole-batch abort).

---

## Finding 4 — Many-to-one match: two distinct archived patients can each match the *same* target patient via different fields

**Severity: Medium**

The task's specific worry — two archived rows in the *same* export sharing one identical identifier value — is correctly ruled out by the source DB's own `unique=True` constraints, and AD-19 says so ("all four are unique-if-set on `Patient`"). That part is sound.

But AD-19 doesn't rule out the adjacent, real case: archived patient **X** has `bht=123` (populated) and matches target patient **A** via `bht`. Archived patient **Y** — a genuinely different real patient in the same export — has `bht` null but `nnc_no=555` populated, and target patient **A** *also* happens to have `nnc_no=555` set (e.g. a hospital's historical practice of recording more than one identifier per admission, or a data-entry duplicate). Because AD-19 evaluates each archived record independently against the whole target DB, both X and Y land in the skip-set against the *same* target row A. X's skip is presumably correct; Y's is not — Y is a different patient whose entire record (and any date-window-anchored related rows) is silently dropped, with no signal that two different source identities were folded into one target match. AD-19's restore preview (step 2) shows the skip/import partition but has no stated mechanism to surface "these two archived patients both matched the same target row" as a reviewable anomaly.

**Fix needed:** AD-19 should state whether a target patient can legitimately be the match target of more than one archived record in the same batch, and if not, require detecting and flagging (not silently applying) an ambiguous many-to-one match before the transaction runs.

---

## Finding 5 — AD-18's `patient_qs` formula only handles one institution or "all"; CAP-1's explicit multi-institution subset has no defined path

**Severity: Medium-High**

`institution/managers.py`'s `InstitutionScopedManager.for_institution(institution)` takes a single `Institution` or `None` ("Phase 1 safe: unfiltered" — i.e., *all* institutions, not a chosen subset). AD-18 writes `patient_qs = Patient.objects.for_institution(institution).filter(created_at__date__range=(start, end))` using the same singular parameter. CAP-1 (per AD-3's own "target institution(s)" plural framing) explicitly allows a super admin to select an explicit multi-institution subset for a backup — something `for_institution()` cannot express directly (it is neither "exactly one" nor "unfiltered/all").

Two implementers filling this real gap diverge, and neither violates AD-18's literal text:
- **Implementer A** loops `for institution in selected_institutions: patient_qs |= Patient.objects.for_institution(institution).filter(...)`, staying inside the sanctioned manager method (N queries, but honors the manager docstring's "single point of truth for data isolation" rule and its explicit "NEVER... inline `.filter(institution=...)`" warning).
- **Implementer B**, to keep the per-model streaming loop to one query per model, writes `Patient.objects.filter(institution__in=selected_institutions, created_at__date__range=...)` directly — bypassing `for_institution()` entirely, which is exactly the pattern the manager's own docstring warns against, and which means the multi-institution date-scoped path is no longer going through the codebase's single sanctioned institution-scoping mechanism at all.

Both compute the same patient set here, but B routes a PHI-scoping decision around the "single point of truth" AD-3 relies on elsewhere, and nothing in AD-18/AD-3 says which is required — future scoping-logic changes made only inside `for_institution()` would silently not apply to B's export path.

**Fix needed:** AD-18 (or AD-3) should state explicitly how a super-admin-selected multi-institution subset is expressed against `patient_qs` — e.g. "loop `for_institution()` per selected institution and union the querysets" — rather than leaving the manager's single-institution signature to be worked around ad hoc.

---

## Finding 6 — AD-19's "one transaction for the entire apply step" is unreconciled with AD-8's polling and AD-16's "relatively brief" premise

**Severity: High**

AD-19 point 4: "Inside one DB transaction covering the entire apply step... for each import-set patient... deserialize... save." This is a single `transaction.atomic()` (or equivalent) spanning every patient in the date-scoped batch.

- **AD-8 (progress polling):** `run_restore.py` runs as a detached subprocess (AD-2) holding its own DB connection; the trigger view / status page runs as a separate web-request connection. If `BackupJob.progress_pct` is updated on the *same* row inside the still-open apply transaction, those writes are invisible to the status page's connection until the transaction commits (standard read-committed semantics on Postgres; on SQLite the writer connection holds the database-wide write lock for the same duration). A restore covering many patients would show frozen/stale progress for the entire apply phase, then jump straight to 100% at commit — silently defeating AD-8's "actively-watched job" polling design for exactly the operation (a multi-patient partial restore) most likely to run long enough for an admin to want a live progress signal. Nothing in AD-8 or AD-19 says progress updates must happen on a separate connection/transaction, or that the apply step should checkpoint in smaller units instead.
- **AD-16 (job-level lock, accepted residual risk):** AD-16's acceptance of "an ordinary clinician's live save colliding with an in-progress restore" as residual risk is explicitly justified by restores being "rare, admin-triggered, and relatively brief." A single all-or-nothing transaction across a potentially large date window's worth of patients (and, on SQLite, an exclusive DB-wide write lock for that whole span) is a materially different risk profile than the "brief" restores AD-16 was evaluated against — long enough to plausibly starve concurrent live writes DB-wide, not just on the restored rows. AD-19 doesn't re-open or re-justify AD-16's acceptance in light of this; it inherited a risk acceptance made before the giant-transaction design existed.

**Fix needed:** either (a) state that `BackupJob` progress writes during the apply step use an autonomous transaction/connection so polling stays live, and cap or checkpoint the apply step (e.g. one transaction per patient with a resumable/idempotent marker) rather than one transaction for the whole batch, or (b) explicitly re-affirm AD-16's residual-risk acceptance covers this longer-duration, DB-wide-lock scenario (on SQLite in particular) with a stated reason.

---

## Finding 7 — Omitted-vs-empty-array ambiguity for zero-match models in `db_export.json`

**Severity: Low-Medium**

AD-5 specifies `db_export.json` as "one JSON object keyed by `<app_label>.<model_name>`", but never states whether a model with zero matching records in a date-scoped export must still appear as an empty array (`[]`) or may be omitted from the object entirely. A writer that skips empty keys (a reasonable, unstated economy) is fully AD-5-compliant; a reader (AD-19 step 1: "read the `patients.patient` array from `db_export.json`", and by extension any other model section a restore or report step reads) that does `data["problemlist.problemaction"]` rather than `data.get(key, [])` throws on a legitimate, easy-to-hit edge case (a date window with patients but no problem actions yet).

**Fix needed:** AD-5 should state that every model key from the fixed dependency-order list is always present, even with an empty array, so readers never need defensive `.get()` fallbacks to distinguish "no records" from "key omitted."

---

## Findings not raised (checked, and closed)

- **`db_export.json` overall shape** (single top-level dict, keyed by `app_label.model_name`, `{model, pk, fields}` per-record shape matching `django.core.serializers`) is unambiguous and correctly reconciles the old per-model-file/multi-institution tension (AD-5 explicitly states no institution tag is needed for full-scope, and date-scoped restore uses `fields.patient`/`fields.problem`-chain instead) — this closes what was Finding 7 in the prior adversarial-divergence review.
- **`Problem`→`Patient` and `ProblemAction`→`Problem` two-level remap** is explicitly and correctly named in AD-19 point 4 (both maps called out by name).
- **Duplicate identical-identifier collision within one export** is correctly ruled out by source-DB `unique=True` constraints, and AD-19 says so — sound reasoning, not just an assertion.

---

## Summary Table

| # | Finding | Severity |
| --- | --- | --- |
| 1 | `GMAssessment.video_file` (OneToOneField to `Video`) has no PK-remap rule — whole-batch transaction abort or silent cross-patient video attachment | Critical |
| 2 | `Patient.institution` never remapped from source PK to target-institution PK after slug match — cross-institution PHI leak or FK failure | Critical |
| 3 | `Patient.pin` (5th unique-if-set identifier) excluded from AD-19's match fields — guaranteed `IntegrityError` aborts whole batch on any PIN collision | High |
| 4 | Two distinct archived patients can both match one target patient via different identifier fields — silent many-to-one data loss, undetected | Medium |
| 5 | AD-18's `patient_qs` formula has no defined path for an explicit multi-institution subset; `for_institution()` only takes one institution or "all" | Medium-High |
| 6 | AD-19's single whole-batch transaction is unreconciled with AD-8's live progress polling and AD-16's "relatively brief" risk-acceptance premise | High |
| 7 | Empty-array vs. omitted-key ambiguity for zero-match models in `db_export.json` | Low-Medium |
