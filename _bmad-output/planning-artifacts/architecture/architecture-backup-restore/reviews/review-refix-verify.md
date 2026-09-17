# Reviewer Gate — Re-check Pass: AD-3 / AD-5 / AD-18 / AD-19 / Deferred

**File reviewed:** `_bmad-output/planning-artifacts/architecture/architecture-backup-restore/ARCHITECTURE-SPINE.md`
**Scope:** verify the 10 previously-failed findings are actually fixed in the current text, and hunt for any new ambiguity/gap the fixes themselves introduce. Settled scope choices (e.g. Bookmark exclusion, referral-3-models exclusion as a decision) are not re-litigated.

**Verdict: PASS WITH NOTES**

All 10 findings land correctly in the current text. Two non-trivial *new* internal-consistency gaps were introduced by the interaction of the fixes with adjacent, previously-unchanged parts of AD-19 (the step-2 preview promise and the media-application note). Neither is a factual contradiction of what the fix claims to do, but both mean the spine is not yet fully self-consistent about *when* an institution-missing exclusion is discovered relative to the preview and the media copy. Recommend a follow-up amendment rather than another full FAIL cycle.

---

## Fix-by-fix verification

### 1. `GMAssessment.video_file` remap — LANDED
AD-19 step 4: *"`video_file` (`GMAssessment`, `OneToOneField`→`Video`) — remapped through the `Video` source-PK→new-PK map, exactly like `patient`/`problem`. `Video` is inserted before `GMAssessment` in the dependency order above specifically so this map is ready."*
Cross-checked against the dependency order stated three times (AD-3 restore semantics, AD-18, AD-19 step 4): `Video` always precedes `GMAssessment`. Consistent everywhere it's repeated.

### 2. `Patient.institution` remap via slug match — LANDED (see New Gap A)
AD-19 step 4: remapped "from the archived source-institution PK to the **target** `Institution` row sharing the same slug... If no institution with that slug exists in the target system, this patient is excluded from the import and reported as a missing-institution error." Matches the required fix. However, see New Gap A below re: where in the pipeline this is detected.

### 3. `Patient.pin` as 5th identifier + ambiguous-match guard — LANDED
Step 1: "checking **all five** of `bht`, `nnc_no`, `ptc_no`, `pc_no`, `pin`... a match on **any** populated field is a conflict, not just the first one found," plus the ambiguous-match guard for one-archived-patient-matches-many-targets and many-archived-patients-match-one-target, excluding the affected patient(s) and reporting an ambiguous-conflict error. Fully landed, and the Deferred section's "Identifier-less patient on partial restore" bullet was updated to name all five fields too.

### 4. `added_by`/`last_edit_by`/`performed_by` remap — LANDED
Step 4: FK→`CustomUser`, nullable/`SET_NULL`, "if a `CustomUser` with the archived PK still exists in the target system, preserve it as-is... otherwise set the field to `NULL`." Matches exactly.

### 5. `CDICRecord` + `GeneralPaediatricAssessment` added to cascade — LANDED
Present in all three places it needs to be: AD-3's scoped-model bullet (with the explicit "were missing from this list in the original pass — corrected here" note), AD-3's restore dependency order, AD-18's cascade filter list, and AD-19's step-4 dependency order. Also reflected in the Deferred "Cascade model list is hand-maintained" bullet's enumerated list. Consistent across all four occurrences.

### 6. `referral` app models excluded from date-scoped cascade — LANDED, rationale slightly under-supports the scope of what it excludes
AD-3: "**Excluded from AD-18/AD-19's date-scoped cascade entirely**... only a full-scope (undated) archive does." AD-18 cross-references it. The exclusion itself (all 3 referral models) matches what was asked and is not being re-litigated. Minor note: the stated rationale — "`ReferralReceived` and `ReferralMessage` deliberately carry no `patient` FK" — only justifies excluding those two; it doesn't address why `ReferralSent` (which does have a `patient` FK per the task context) is also swept into the same "excluded entirely" rule. The *outcome* is correct and matches the required fix; the *stated justification* is incomplete for one of the three models. Cosmetic, not a landing failure.

### 7. `Bookmark` gap named in Deferred — LANDED
Named in two places, consistently: AD-3's "Known gap, not fixed by this pass" paragraph, and a dedicated Deferred bullet ("`Bookmark` is excluded from backup/restore entirely"). Both describe the same generic-FK mechanism and both say it predates this update. Consistent, not silently dropped.

### 8. Per-import-set-patient transaction (not one for the whole archive) — LANDED (see New Gap A/B)
Step 4 header states "one transaction **per import-set patient**," and a dedicated rationale paragraph follows ("Why one transaction per patient, not one for the whole archive") citing AD-8 progress polling and AD-16/SQLite lock duration, plus safe-resumability on retry. This directly answers the tension the original reviewer flagged.

### 9. Three-way `institution_scope` branch — LANDED
AD-3's "Institution scope resolution" paragraph names all three forms (`for_institution(inst)`, `.filter(institution__in=selected_institutions)`, `all_institutions()`) and states `for_institution` cannot express a subset. AD-18 explicitly reuses it ("starting from AD-3's `institution_scope` resolution... never routed through `for_institution` for a multi-institution subset"). Consistent.

### 10. `db_export.json` key-always-present rule — LANDED
AD-5: "Every model in AD-3's dependency-ordered list is always present as a key, even when its array is empty (`[]`) — a key is never omitted for zero matches, so a reader never has to treat 'key absent' and 'key present with an empty array' as the same thing." Unambiguous, and consistent with the Structural Seed's `db_export.json` comment.

---

## New gaps introduced/exposed by the fixes

### New Gap A (the one worth fixing before build): institution-missing exclusion is detected too late relative to the preview promise

AD-19's pipeline is written as four sequential steps: (1) Match/ambiguous-guard, (2) Partition + **preview shown to admin, "resolved without applying anything yet"**, (3) Skip, (4) Additive import with FK remap (including the institution-slug check that can exclude a patient with a "missing-institution error").

Step 2's preview is explicitly scoped as: *"exactly this partition (plus any ambiguous-conflict exclusions from step 1)"*. It does **not** mention institution-missing exclusions, because the institution-slug remap/rejection (fix #2) is written into step 4, not step 1. Institution-slug matching is a pure function of (archived institution PK's slug, target DB's current institutions) and could in principle be resolved as early as step 1 — but the current text only performs it during the per-patient transactional import, i.e. **after** the admin has already confirmed the preview.

Practical effect: a super admin can confirm a restore preview that shows patient P as "will be imported," and only during actual execution (step 4) does P get silently rerouted to a missing-institution error — a partition the admin never saw before confirming. This doesn't corrupt anything (fix #8's per-patient transaction still isolates the failure cleanly), and it is reported as an error in the "restore result" per the institution bullet's wording — but the **preview accuracy guarantee** step 2 sets up ("resolved without applying anything yet") is now inconsistent with a category of exclusion that fix #2 added but placed downstream of that promise.

This is exactly the composition risk the task asked about: it is *not* clear that a patient excluded on the institution check "never gets to the transaction step at all" — as written, it reaches step 4 (is deserialized, FK remap attempted) and is excluded from *inside* that stage, not turned away before it. Recommend: either (a) fold the institution-slug pre-check into step 1's Match phase so all three exclusion reasons (conflict-match, ambiguous-match, missing-institution) are resolved and shown in one preview, or (b) explicitly state in step 2 that missing-institution failures are a distinct "discovered at apply-time" category not covered by the pre-confirmation preview.

### New Gap B: media-application note's "import-set" label is stale by the time institution exclusion can happen

The media-application bullet says: *"only files referenced by an **import-set** patient's `Video`/`Attachment` rows... are copied... a **skip-set** patient's media entries... are never extracted, so no orphaned file is left on disk for a patient whose DB rows were never applied."*

"Import-set" here is the label a patient receives at step 2 (Partition), before step 4 can still exclude that same patient for a missing institution. If the media copy is literally driven off the step-2 "import-set" list (as the sentence reads), a patient who is later excluded in step 4 for a missing-institution error would still have their media files copied to disk — directly contradicting the bullet's own stated goal of never leaving "an orphaned file... for a patient whose DB rows were never applied." (The pre-existing skip-set case this bullet was written for is unaffected — that exclusion happens at step 2/3, before any copy — so this is specifically an interaction introduced by fix #2's late-stage exclusion, not a defect in the original wording.)

This reads as an oversight rather than a deliberate choice: the fix for #2 added a new exclusion path without updating the media-application note to key off "successfully committed in step 4" rather than "labeled import-set at step 2." Recommend gating the media copy on the same per-patient transaction success that step 4 already tracks (naturally solved if New Gap A's fix (a) is adopted, since then all exclusions — including missing-institution — happen before step 4 and "import-set" becomes a stable, final label again).

### Minor, non-blocking observations
- Fix #6's rationale text doesn't individually justify `ReferralSent`'s exclusion (see above) — cosmetic only, outcome is correct and matches the deliberate scope decision.
- The rationale for fix #8 doesn't state whether patients excluded at step 4 (ambiguous-match already resolved in step 1, but institution-missing resolved in step 4) count toward `BackupJob.progress_pct` the same way a committed patient does. Not a contradiction, just unstated; low priority given New Gap A's fix would likely resolve it as a side effect by moving all exclusions before any transactional/progress-counted stage.

## Everything else checked and found consistent
- Dependency order (`Patient`; `Video, Attachment, GMAssessment, HINEAssessment, DevelopmentalAssessment, CDICRecord, GeneralPaediatricAssessment, Problem`; `ProblemAction` last) is identical, word-for-word list order, in AD-3's restore semantics, AD-18, and AD-19 step 4. No drift.
- `Institution` rows "never recreated by restore... matched by slug" stated consistently in both AD-3 (full-scope) and AD-19 (partial-scope) restore paths.
- AD-5's schema-shape rule (`db_export.json` keyed by `<app_label>.<model_name>`, key always present) matches the Structural Seed's inline comment.
- AD-3's three-way institution-scope branch is defined once and correctly reused (not redefined or drifted) by AD-18.
- Deferred section's "Cascade model list is hand-maintained" and "Multi-institution query path is now explicit but unenforced" bullets both correctly reflect the current (post-fix) model list and scope-resolution mechanism — no stale references to the old, incomplete versions.
