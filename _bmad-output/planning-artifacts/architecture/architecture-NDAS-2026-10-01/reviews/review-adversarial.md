---
name: 'NDAS — Architecture Spine Adversarial Review'
type: review
target: ARCHITECTURE-SPINE.md (architecture-NDAS-2026-10-01)
reviewer: claude-sonnet-5 (adversarial pass)
date: '2026-10-01'
verdict: NEEDS FIXES
---

# Adversarial Review — NDAS Architecture Spine

**Method.** For each AD, I tried to construct two hypothetical (or, where noted, *already-real*) units that each satisfy the Rule's literal text while producing incompatible or unsafe outcomes. Three of the findings below are not hypothetical — I found the actual divergent code in the repo while grounding the scenarios, and they're flagged **[LIVE]**.

**Verdict: NEEDS FIXES.** The spine is well-structured and most ADs hold up, but there are three live violations already in the codebase that the spine's own binding lists fail to cover (AD-8, AD-11), one structural loophole where the sanctioned compliance mechanism *is* the leak path (AD-9), and several binding-list gaps where "closed enumeration" ADs (AD-8) sit next to "future-proofed" ADs (AD-9/AD-10) with no stated rule for which pattern new apps should follow.

---

## AD-1 — Monolithic MVT, no parallel API surface

**Scenario.** Unit A (patients) adds a `JsonResponse` autocomplete endpoint for the existing patient-search page — textbook HTMX partial, clearly compliant. Unit B (institution) adds a `JsonResponse` endpoint on the existing "Sync Status" settings page that an external mobile companion app polls every 30s for sync state. Both devs can honestly say "this is a JSON partial for an existing page" — the Rule's only test is *where the endpoint is wired*, not *who actually consumes it*. B's endpoint is functionally a public API (no HTMX trigger, stable JSON contract, consumed by a non-browser client) but is textually indistinguishable from A's under the Rule.

**Gap.** The Rule conflates "reachable from a page" with "intended for that page's HTMX only." Nothing requires the view to check `HX-Request` header or reject non-HTMX callers. Add: endpoints permitted under this AD must either check `request.htmx` (or equivalent) and 400 otherwise, or the AD should say so explicitly is non-normative and this is fine.

**Severity:** Medium (slow API-surface drift, not an immediate break).

---

## AD-2 — One-way dependency on `custom_codes`

**Scenario.** The dependency diagram shows `reports --> patients` only — no edge from `reports` to `video` or `problemlist`, and no edge *into* `reports` from anywhere. Unit A (reports team) builds a combined patient PDF that needs problem-list entries, so it reaches into `problemlist.models.Problem` directly from `reports/utils/pdf_generator.py` — an undeclared app-to-app import the diagram never forbids (it only shows the *existing* happy-path edges; AD-2's Rule text only constrains `custom_codes` directionality, not inter-app edges in general). Unit B (problemlist team), reading the same diagram and seeing no `problemlist --> reports` edge either, concludes "reports doesn't do problem-list PDFs" and builds its own ad hoc PDF export in `problemlist/utils/pdf.py` using raw `reportlab` — duplicating `BasePDFGenerator`, with its own (weaker) sanitization-before-render logic.

**Gap.** AD-2 only polices the `custom_codes` edge. There is no AD that says "`reports` is the sole owner of PDF/Excel generation; no other app writes its own generator." That rule is implied by the "Reports Module" prose section but never promoted to a binding AD, so two teams converge on two incompatible PDF pipelines while violating nothing written.

**Severity:** Medium-High — directly produces the two-owners-of-one-capability failure mode the spine exists to prevent, and the diagram's silence reads as permission.

---

## AD-3 / AD-4 — Base model inheritance + middleware-populated tracking

**Scenario.** Unit A (backup/restore) writes a management command (`run_restore.py`) that recreates `Patient`, `Video`, etc. rows from an uploaded JSON archive, entirely outside the request/response cycle — `UserActivityMiddleware` never runs because there is no `request`. Unit A, reading AD-4 literally ("views never set them directly" — this is a management command, not a view), sets `added_by=job.triggered_by` manually to avoid `NULL` constraint failures. Unit B (a hypothetical bulk CSV-import feature for problemlist, built later by someone who *also* reads AD-4 literally but takes the stricter reading — "the single population path for `added_by`/`last_edit_by` is the middleware, full stop") refuses to set it manually, and instead special-cases `added_by` as nullable for import-created rows, or runs the import through a synthetic `RequestFactory` request so the middleware fires.

**Result:** two different "how do background-created records get tracked" conventions in the same codebase, both arguably AD-4-compliant by different readings, with different NULL-ability assumptions on the same mixin fields.

**Gap.** AD-4's Rule is written for the request/response path only ("views never set them directly"). It has no stated answer for management commands, signal handlers, or restore/import code paths that run outside a request — which is exactly where `backup` and any future bulk-import feature live.

**Severity:** Medium.

---

## AD-5 — Standard view stack

**Scenario.** Unit A builds a single-patient delete view: `get_object_or_404(Patient, id=pk)` — compliant. Unit B builds a bulk-action endpoint ("archive these 12 selected patients") reading `ids = request.POST.getlist('ids')` and doing `Patient.objects.filter(id__in=ids)`. This is not a "single-object view," so AD-5's `get_object_or_404()` requirement doesn't literally apply; B's endpoint silently no-ops on invalid/cross-institution IDs instead of 404ing, with no equivalent "assert all requested objects existed" contract. Both views are AD-5-compliant; only one has deterministic error behavior.

**Gap.** AD-5 never addresses multi-object/batch endpoints, which `problemlist`, `patients`, and `backup` (restore selection) all plausibly need. Ratelimit tiers are also unaddressed for batch size — is a 12-patient bulk delete one "delete" for the 5/min bucket, or should it be gated differently?

**Severity:** Low-Medium.

---

## AD-6 — Delete permission logic is centralized

**Scenario.** `delete_helpers.py`'s existing "Staff delete own records" rule predates institution scoping (Phase 1) and says nothing about institution boundaries. Unit A adds a new deletable entity (e.g., a `Problem`) and writes its check in `delete_helpers.py` following the existing pattern: `request.user.is_staff or obj.added_by == request.user`. This is textually AD-6-compliant (check lives in `delete_helpers.py`, template uses the shared modal). But because AD-9's Rule only binds "institution-scoped **queries**," and a delete permission check is a boolean function, not a queryset, nothing in either AD-6 or AD-9 requires the check to also assert `obj.institution == request.institution`. A staff user who guesses/enumerates another institution's object `pk` (object is fetched via plain `get_object_or_404(Problem, id=pk)` per AD-5, *not* through `InstitutionScopedManager.for_institution(...)` because AD-5's Rule doesn't mention institution scoping either) can pass the centralized, AD-6-compliant permission check and delete cross-institution data.

**Gap.** AD-6 (delete permission) and AD-9 (institution scoping) each individually compliant in isolation, but neither requires the other — the seam between "centralize permission logic" and "scope by institution" is unguarded for mutations specifically (AD-9 says "queries").

**Severity:** High — this is a cross-institution data-integrity hole, not cosmetic, and it's a natural seam for exactly the "two owners, independently compliant" failure the spine is meant to catch.

---

## AD-7 — Sanitization and export-escaping are mandatory choke points

**Scenario.** The Rule: "no model/form field holding user free text is saved or rendered without passing through `sanitize_text_input()`..." Two non-form text-ingestion paths exist in the real codebase that a literal reading excludes:

1. **Referral `snapshot_data`** (AD-11): captured once at submission as a `JSONField` blob assembled from other already-saved model fields (e.g., `patient.baby_name`, a free-text "reason for referral" field on the referral form itself). If the referral form's free-text reason is serialized straight into the JSON blob rather than round-tripped through a `ModelForm` field with the standard `clean_<field>` sanitization hook, AD-7's Rule doesn't clearly bind it — it's "a JSON value," not "a model/form field" in the CharField/TextField sense the Rule was written against.
2. **Backup restore ingestion** (`backup/restore_apply.py`): patient free text arrives from an uploaded JSON archive and is written via `Model.objects.create(**data)`-style reconstruction, not through a `ModelForm.save()`. A tampered archive re-introduces unsanitized `=`/`+`/`-`/`@`-leading text that later flows untouched into an Excel export of the restored patient, because the restore path and the Excel-export path are maintained by two different teams who each assume "sanitization already happened upstream, on the original save."

Both teams can honestly say "I didn't skip calling `sanitize_text_input()` on a model/form field — this is bulk/JSON data," while the actual XSS/formula-injection surface AD-7 exists to close is wide open on both paths.

**Gap.** AD-7's Rule covers the common form-submission case only. It does not explicitly bind (a) JSON blob construction/deserialization, (b) bulk/management-command/restore ingestion, or (c) signal-handler-triggered saves — exactly the non-form paths the task flagged as the thing to check for.

**Severity:** High — security-relevant, and the exact ambiguity the review was asked to hunt for.

---

## AD-8 — File uploads go through one validation pipeline **[LIVE VIOLATION FOUND]**

**Scenario / evidence.** AD-8's Binds clause is a **closed enumeration**: "video, patients (attachments), institution (logos)" — unlike AD-9/AD-10, it has no "and any future upload type" clause. `reports/models.py` defines:

```python
logo = models.ImageField(
    upload_to="reports/logos/%Y/%m/",
    blank=True, null=True,
    help_text="Logo image for report header (PNG/JPG, max 5MB)"
)
```

on `ReportTemplate`. This field has **no `validators=[...]`, no python-magic MIME check, no `sanitize_filename()`, no institution-aware path** — it's a bare Django `ImageField` with a size limit that exists only in a `help_text` comment, never enforced. It's managed through Django admin (`reports/admin.py` lists `logo` in `fields`). This is not a hypothetical: the field exists today and is reachable by anyone with admin access, uploading arbitrary image bytes with no MIME verification.

A developer who reads AD-8 literally is **correct** that `reports` was never bound by it — the Rule's Prevents clause ("a new upload type skipping MIME verification because its own app wrote a shortcut extension-only check") describes exactly this field, but the Binds clause doesn't reach it.

**Fix needed.** Either (a) change AD-8's Binds to "all apps with file-upload fields, including any future one" to match AD-9/AD-10's future-proofing pattern, or (b) explicitly carve out `reports` with a documented reason. Right now it's an accidental gap, not a decided exception.

**Severity:** High — live, unvalidated file-upload surface in a security-focused spine.

---

## AD-9 — Institution scoping goes through the manager, never a hand-filter

**Scenario — the sanctioned path *is* the leak.** `InstitutionScopedManager.for_institution()`:

```python
def for_institution(self, institution):
    if institution is None:
        # Phase 1 safe: no institution context active -> unfiltered (backward compatible)
        return self.get_queryset()
    return self.get_queryset().filter(institution=institution)
```

AD-9's Rule says the fix for "missing the SUPERADMIN-sees-all / legacy-`None` case" is to always call `for_institution(request.institution)`. Two units each comply to the letter:

- Unit A (a regular staff-facing patient list view) calls `Patient.objects.for_institution(request.institution)`. If `UserActivityMiddleware`/institution-resolution middleware fails to populate `request.institution` for this staff user on some code path (e.g., a URL registered before institution-context middleware was added, or a user whose institution FK was nulled out during a migration), `request.institution` is `None` — and the manager returns **every institution's patients**, unfiltered, to a non-superadmin staff user. This is not a hand-filter bug; it is the sanctioned manager behaving exactly as documented ("Phase 1 safe... unfiltered").
- Unit B (a true SUPERADMIN aggregate view) is *supposed* to see everything, and also gets `None`→unfiltered, by the same code path, correctly.

**There is no way, from inside `for_institution()`, to distinguish "legitimate superadmin, show everything" from "staff user whose institution context silently failed to resolve, show everything by accident."** Both call the one sanctioned API with the one sanctioned argument shape and get the same (for one of them, catastrophic) result. The two units — "regular scoped view" and "superadmin aggregate view" — are indistinguishable to the manager, and AD-9's Rule treats `all_institutions()` and `for_institution(None)` as two separate paths in the docstring prose, but the code makes them the *same* path for any caller that doesn't explicitly use `all_institutions()`.

**Gap.** AD-9 prevents "a view hand-filtering... and missing the None case" — but the *sanctioned* mechanism has the same failure mode baked in, with no required check that `request.institution` is non-None for non-superadmin callers before scoping. This is the single sharpest finding in the review: compliance with the Rule does not prevent the Rule's own stated failure mode.

**Severity:** Critical.

---

## AD-10 — Institution-scoped files use institution-aware paths

**Scenario — the Binds list vs. a model that's institution-scoped but not Patient/referral.** AD-10 Binds: "video, patients (attachments), institution." `reports.ReportTemplate` is not institution-scoped today (it's a global template with no `institution` FK), so it's correctly outside AD-10's scope *as currently modeled*. But consider a plausible next feature: Unit A extends `ReportTemplate` with an `institution` FK so each institution can have its own branded header/footer/logo (a natural, likely request — the demo/live cPanel split already implies multi-tenant branding needs). Unit A, now building an institution-scoped `FileField`, is told by AD-10's Rule to use `get_institution_*_path`. But AD-10's Binds list is also a **closed enumeration** (no "and any future institution-scoped model" clause — contrast with AD-9's Binds, which *does* have that clause). Unit A can correctly observe "AD-10 doesn't bind `reports`," reuse the existing `upload_to="reports/logos/%Y/%m/"` string path, and ship a newly-institution-scoped field that stores every institution's logos in one shared, non-partitioned directory — exactly the filesystem-level cross-institution leak AD-10's Prevents clause describes, while being textually compliant because the Binds clause never reached `reports`.

Meanwhile Unit B, adding a genuinely new institution-scoped upload type inside `patients` (already bound), correctly uses `get_institution_attachment_path`. Two "institution-scoped file upload" features now partition data completely differently — one isolated by institution slug, one not — and both are spine-compliant per their respective AD-10 binding status.

**Gap.** AD-10 needs the same future-proofing language AD-9 already has. Right now the asymmetry between AD-9's open Binds clause and AD-10's closed one is itself the loophole.

**Severity:** High.

---

## AD-11 — Referral records stay FK-independent **[LIVE VIOLATION FOUND]**

**Scenario / evidence.** `referral/signals.py` docstring: *"All `Notification.objects.create()` calls live here — never in view files."* AD-11's Rule: *"`Notification` rows are only ever created from `referral/signals.py`."* But `backup/notifications.py` (`notify_job_finished`, called from `backup/management/commands/run_backup.py` and `run_restore.py`) does:

```python
from referral.models import Notification
...
Notification.objects.create(
    recipient=recipient, notification_type=notification_type,
    title=title, body=body, link=_link_for(job),
    institution=institution, added_by=recipient, last_edit_by=recipient,
)
```

— a direct `Notification.objects.create()` call from `backup`, not from `referral/signals.py`. This is a real, present-day instance of the exact divergence the task description predicts: **AD-11's Binds clause lists only `referral`**, so a `backup`-team developer reading AD-11 literally can correctly say "this AD doesn't bind `backup`; I'm not creating a `ReferralSent`/`ReferralReceived` FK, I'm just reusing the `Notification` model it happens to own." Both `referral/signals.py`'s own docstring claim ("never in view files" — this is a management-command-invoked service module, not a view, so even that narrower claim survives) and `backup/notifications.py` are each locally defensible, yet the system now has **two independent Notification-creation code paths** with no shared dedup, no shared signal-driven audit trail, and no single place to reason about "when does a Notification get created and by what rule."

**Gap.** AD-11's Rule describes a `referral`-internal invariant (notifications *about referrals* go through signals) but reads, and is written, as if `Notification` model mutation is globally centralized. It isn't, and the spine doesn't say whether `backup`'s direct-create pattern is an accepted exception or a drift that should be fixed (e.g., by having `backup` fire a signal that `referral/signals.py` listens to, preserving single-writer semantics).

**Severity:** High — live divergence, and it undermines the one invariant AD-11 is supposed to buy (a single, auditable notification-creation point).

---

## AD-12 — Service-layer threshold for multi-step workflows

**Scenario.** AD-12's Rule: "a workflow with more than one sequential stage, a concurrency hazard, or an audit/rollback need gets its own service module(s)... a single-entity CRUD stays view-direct." Unit A (backup) builds restore as a service module with `job_lock.py` — unambiguous, multi-stage, concurrency-hazardous, correctly service-layered.

Unit B builds a near-identical-looking feature: "bulk-reassign all of a departing clinician's patients to a new clinician." This is, by stage count, exactly two sequential steps — (1) validate the new clinician can accept the load / isn't the same person / institution matches, (2) update N `Patient.assigned_clinician` FKs in a loop — with no explicit lock. Dev B judges this "simple CRUD, just a for-loop over `Patient.objects.filter(...).update(...)`" and keeps it view-direct, because "more than one sequential stage" reads to them as "more than one *distinct business operation*," and a validate-then-bulk-update is, in their mind, one operation with an internal guard clause, not two stages. A different dev, shown the same spec, would call validate+mutate two sequential stages requiring a service module per the letter of the Rule. Nothing in AD-12 defines what counts as a "stage" (is a validation step before a mutation a stage, or a precondition?) — so the same shape of feature gets built as view-direct by one team and service-layered by another, and only the service-layered one gets a concurrency guard — meaning if two admins trigger the reassignment simultaneously for overlapping patient sets, the view-direct version has a race the service-layered sibling would have caught.

**Gap.** "More than one sequential stage" is not operationalized — no example distinguishing a precondition-then-mutation CRUD view (still "simple") from a genuine multi-stage workflow. The task's suspicion here is confirmed: this phrase is judgment-call-shaped, not a bright line.

**Severity:** Medium-High.

---

## AD-13 — Security middleware order is fixed

**Scenario.** Two features each need "a new cross-cutting concern." Unit A adds audit-logging middleware for HIPAA-style access logging and, reading "appended only at a documented, reasoned position relative to the existing 14," appends it *after* `UserActivityMiddleware` (position 10) so it can log the resolved user. Unit B, months later, adds a response-time/APM middleware and also reasons its way to "after `UserActivityMiddleware`, before `MessageMiddleware`" for similar reasons. Both documented, both reasoned, both inserted at "position 10.5" independently without knowledge of each other (different sprints, different devs) — final order depends entirely on merge order of two unrelated PRs, and nothing in AD-13 requires a single source-of-truth *list* of middleware insertions-in-flight to prevent two teams from picking the same slot with different relative-ordering assumptions about each other (A assumes it runs before APM; B assumes it runs after audit logging — whichever merges second silently wins, and neither PR diff makes the other team's assumption visible).

**Gap.** "Documented, reasoned position" has no required artifact (e.g., an ADR entry or a comment block naming what it must run before/after and why) — so two independently-reasoned insertions can still conflict with each other, not just with the fixed 14.

**Severity:** Low-Medium.

---

## AD-14 — Tests stay inside the per-app `tests/` package

Hard to subvert while complying — this AD is close to watertight (filesystem collision is binary, not a judgment call). One edge: a dev scaffolding a brand-new app without running `startapp` conventions might create `newapp/tests.py` *before* ever creating `newapp/tests/`, then a second dev adds `newapp/tests/test_models.py` next to it without deleting the first — both additions are individually innocuous (neither dev "added `tests.py` alongside an existing `tests/` package," since at the time each one acted, the other didn't exist yet) but the merged result is the exact forbidden collision. Low severity, mostly a CI/pre-commit-hook gap rather than a spine wording gap.

**Severity:** Low.

---

## AD-15 — Deployment stays DB-engine-agnostic across both hosting shapes

**Scenario.** Unit A (VPS-targeting feature, e.g., a reporting feature that wants full-text search) uses a Postgres-specific `SearchVectorField`/`TrigramSimilarity`, gated behind `if settings.DB_ENGINE == 'postgresql': ...` with a SQLite fallback using `icontains` — compliant, ORM-portable with explicit gating, per the Rule. Unit B, building a near-identical "fast search" feature for a different model, uses `django.contrib.postgres.indexes.GinIndex` in a `Meta.indexes` list on the model itself. A model-level index declaration isn't naturally "gated" the way a queryset call is — `makemigrations`/`migrate` on SQLite will simply fail outright (no SQLite equivalent of `GinIndex`), not gracefully degrade. Unit B can argue they didn't "assume Postgres-only *behavior* that breaks SQLite" in the query sense the Rule is written for — they added an index, a schema concern, which the Rule's phrasing (framed around runtime behavior/queries) doesn't obviously cover — yet it breaks `migrate` on every cPanel/SQLite deployment the moment the migration ships, which is strictly worse than a behavioral gap (it's a hard deploy-blocker, not a degraded feature).

**Gap.** AD-15's Rule reads as being about query/runtime behavior ("new features stay ORM-portable unless explicitly gated"); it doesn't explicitly call out schema-level Postgres-only constructs (`GinIndex`, `ArrayField`, `JSONField` with Postgres-specific lookups, `ExclusionConstraint`) as needing the same gating discipline, even though those are the more dangerous category (migration-time failure, not request-time).

**Severity:** Medium.

---

## Dependency diagram — happy path only, not a forbidding diagram

The `graph TD` in the spine lists only the edges that exist today (`video --> patients`, `reports --> patients`, etc.) and `custom_codes` as the universal sink. It contains **no edges at all into `reports`**, **no edges between `video`/`problemlist`/`backup` and each other**, and critically, **nothing that visually or textually forbids an edge the diagram doesn't show**. AD-2's Rule only constrains the `custom_codes` direction ("custom_codes never imports a domain app"); it says nothing about, e.g., `problemlist` importing `video` directly, or `video` importing `reports`. Two teams can each add a new cross-app import that isn't in the diagram, and both can correctly say "AD-2 wasn't violated — `custom_codes`'s directionality is intact" — because the diagram was descriptive (what exists) not prescriptive (what's forbidden). See the AD-2 scenario above for the concrete `reports`/`problemlist` PDF-duplication case this produces.

**Recommendation:** Either add an explicit Rule ("no app-to-app import outside the edges shown in the dependency diagram without a spine update") or relabel the diagram as non-normative so nobody mistakes silence for permission.

---

## Deferred section — items that read as "later" but aren't

### Postgres driver pinning
Marked "revisit at the next VPS deployment." Given the stack table pins Django to `~=5.2.0` specifically *because* "cPanel hosts top out at Python 3.11.15," and the repo already supports a full Postgres branch in `settings.py`, this isn't a future unknown — it's a **known gap that silently works today only because nobody has done a from-scratch VPS install.** A team deploying to VPS next week will `pip install -r requirements.txt`, get no `psycopg`/`psycopg2`, and the Postgres branch in `settings.py` will fail at the first DB connection with an unhelpful `ModuleNotFoundError` at runtime, not at install time. This should be **Urgent**, not Deferred, for any team with a VPS deployment on the near-term roadmap — the Deferred framing invites exactly the "someone else's problem" reading the task warned about.

### Task queue / Celery
Correctly deferred *for new features*, but the Deferred note doesn't warn existing code away from assuming Celery is available. Given `backup`'s job pattern (`job_lock.py`, management-command-driven jobs) already looks like hand-rolled "what Celery would do," there's a real risk a future dev "completes" the stray Celery transitive deps by wiring in actual `celery` + a broker, without realizing `backup`'s own service-layer pattern (AD-12) was deliberately built as the *non-Celery* answer to the same problem — producing two parallel background-job mechanisms (Celery tasks vs. `backup`'s lock-file/service-module pattern) for whatever the next multi-stage feature is, each individually "correct" per AD-12 (which doesn't mention Celery at all) and the Deferred note (which only says "revisit," not "and if you do, retire the job_lock pattern in its favor" or vice versa).

**Severity:** Postgres driver gap — High/Urgent (mislabeled as Deferred). Celery — Medium (latent, not yet urgent, but the Deferred note doesn't prevent a collision with AD-12's existing pattern).

---

## Summary table

| AD | Severity | One-line divergence |
|----|----------|----------------------|
| AD-1 | Medium | HTMX-wired JSON endpoint vs. disguised polling API — both "for an existing page" |
| AD-2 | Medium-High | Undeclared `reports`↔`problemlist`↔`video` edges → duplicate PDF pipelines |
| AD-3/4 | Medium | Management-command/restore record creation has no agreed tracking convention outside request cycle |
| AD-5 | Low-Medium | Batch/bulk endpoints fall outside "single-object view," so 404 semantics diverge |
| AD-6 | High | Centralized delete permission has no institution-boundary requirement — cross-tenant delete |
| AD-7 | High | JSON-blob/bulk-import text (referral snapshot, backup restore) reads as outside "model/form field" |
| AD-8 | High (**live**) | `reports.ReportTemplate.logo` is a real, unvalidated upload outside AD-8's closed Binds list |
| AD-9 | Critical | `for_institution(None)` is itself the unfiltered-leak path the Rule claims to prevent |
| AD-10 | High | Closed Binds list (no "future model" clause, unlike AD-9) lets a newly-scoped `reports` field skip institution-aware paths |
| AD-11 | High (**live**) | `backup/notifications.py` creates `Notification` rows directly, bypassing `referral/signals.py` |
| AD-12 | Medium-High | "More than one sequential stage" has no precondition-vs-stage definition — same shape built CRUD-direct vs. service-layered |
| AD-13 | Low-Medium | Two independently "reasoned" middleware insertions can still collide with each other |
| AD-14 | Low | Simultaneous-PR race can still produce the forbidden `tests.py` + `tests/` collision |
| AD-15 | Medium | Rule framed around query/runtime behavior; doesn't call out schema-level Postgres-only constructs (`GinIndex` etc.) that break `migrate` on SQLite |
| Diagram | High | Descriptive, not prescriptive — silence read as permission for undeclared imports |
| Deferred | High/Urgent | Postgres driver gap is mislabeled "later" when it's a next-VPS-deploy blocker |
