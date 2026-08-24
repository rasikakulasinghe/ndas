---
title: 'Fix medical-data-correctness bugs (DX_NORMAL short-circuit, HINE thresholds, birth-weight validation, HINE latest-record)'
type: 'bugfix'
created: '2026-08-24'
status: 'done'
review_loop_iteration: 1
context: []
baseline_commit: '78ba8aa93ca2f6b22bd48b3fd5907772132c598d'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Four independent clinical-classification bugs from the codebase review's "medical-data-correctness" group: (1) `getPatientList`'s `PtStatus.DX_NORMAL` branch combines three `Q` objects with Python's `and` operator instead of a real ORM combinator, so `and` short-circuits and only the last `Q` object survives — patients with an abnormal GMA or HINE result but a normal/absent developmental assessment are wrongly classified as "DX_NORMAL"; (2) the HINE assessment manager's `score_range='normal'` filter uses `score__gte=60`, but the model's own `is_normal`/`severity_category` define "Normal" as `score > 73` (60-73 is "Mild Abnormality") — clinicians filtering for normal results are shown patients with a mild neurological abnormality; (3) `Patient.clean()` calls the wrong validator (`validate_birth_weight`, which raises rather than returning a tuple) for its POG-specific birth-weight check, so `if result is not None` is always False and the documented gestational-age-aware validation never runs (the basic 300-8000g field-level check still runs independently via the field's own validator, so this is not a total validation bypass — the POG-specific implausible-weight-for-gestational-age check specifically never fires); (4) `Patient.getRC` fetches the "latest" HINE score via `.filter(patient=self).last()`, but `HINEAssessment.Meta.ordering` is `["-date_of_assessment"]` (descending), so `.last()` returns the OLDEST record — the physiotherapy-referral recommendation is computed from stale data.

**Approach:** (1) Combine the three `Q` objects with `|` (OR) instead of `and` in the `DX_NORMAL` branch — "normal" means abnormal in *none* of GMA/HINE/DA, so `.exclude()` must drop anyone abnormal in *any* one of them (De Morgan's law: NOT(A or B or C) = exclude(A or B or C)); combining with `&` instead would only exclude patients abnormal in all three simultaneously, still misclassifying the single/double-abnormality cases the finding describes. This matches the sibling `DIAGNOSED` branch's existing `|`-combined style two lines above. (2) Change all four `score__gte=60` "normal" occurrences in `patients/views.py` (two filter branches, two stats aggregates) to `score__gt=73`, matching the model's canonical threshold. (3) In `Patient.clean()`, call `validate_birth_weight_for_gestational_age(self.birth_weight, self.pog_wks, pog_days)` (already implemented and unit-tested in `validators.py`, just never wired into the model) instead of `validate_birth_weight(self.birth_weight)`. (4) In `getRC`, replace the inline `.filter(patient=self).last()` query with a call to the already-correct `self.get_latest_hine_assessment()` method on the same model, reusing existing logic instead of duplicating a corrected query.

## Boundaries & Constraints

**Always:** Preserve existing behavior for every other `PtStatus`/`score_range` branch untouched by these findings. Keep the basic 300-8000g field-level `validate_birth_weight` validator on the `birth_weight` field as-is — only `Patient.clean()`'s dead POG-specific branch is being fixed.

**Ask First:** Nothing expected — each fix is narrow, has a clearly-documented canonical definition to match, and (for #3 and #4) an existing correct implementation elsewhere in the same file to reuse.

**Never:** Do not redesign the HINE manager's 3-bucket (normal/moderate/significant) UI filter scheme to fully match the model's 4-category scheme (Normal/Mild/Moderate/Severe) — out of scope; only the "normal" threshold mismatch is being fixed. Do not touch `validate_birth_weight_for_gestational_age` itself (already correct, already unit-tested). Do not touch `get_latest_hine_assessment`/`get_latest_gma_assessment` (already correct, reused as-is).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| DX_NORMAL, abnormal GMA + normal DA | Patient with GMA diagnosis_conclusion='ABNORMAL', has videos | Excluded from DX_NORMAL list | N/A |
| DX_NORMAL, abnormal HINE + normal DA | Patient with HINEAssessment score<73, has videos | Excluded from DX_NORMAL list | N/A |
| DX_NORMAL, all normal | No abnormal GMA/HINE, DA is_dx_normal=True (or absent), has videos | Included in DX_NORMAL list | N/A |
| HINE manager, score_range=normal | HINEAssessment.score=65 (Mild Abnormality per model) | Excluded from 'normal' filter results | N/A |
| HINE manager, score_range=normal | HINEAssessment.score=75 (Normal per model) | Included in 'normal' filter results | N/A |
| Patient save, implausible weight/POG | birth_weight=3000, pog_wks=22 (22-week baby at term weight) | `full_clean()`/`save()` raises `ValidationError` on `birth_weight` | Caught by calling view's existing try/except |
| Patient save, plausible weight/POG | birth_weight=500, pog_wks=22 | Saves successfully | N/A |
| getRC, multiple HINE records | HINE records dated older and newer | `last_hine_score` reflects the newest `date_of_assessment`, not the oldest | N/A |
| getRC, no HINE records | No HINEAssessment rows for patient | `last_hine_score` = 0 (unchanged) | N/A |

</frozen-after-approval>

## Code Map

- `ndas/custom_codes/custom_methods.py:623-628` (`getPatientList`, `PtStatus.DX_NORMAL` branch) -- fix `and` → `|`
- `ndas/custom_codes/custom_methods.py:621-622` (`PtStatus.DIAGNOSED` branch) -- READ-ONLY reference: already correctly uses `|` between `Q` objects; DX_NORMAL should mirror this exact style
- `patients/views.py:2832,2859,2915,2941` (`hine_assessment_manager`, `hine_assessment_manager_by_patients`) -- change `score__gte=60` to `score__gt=73` at all four sites
- `patients/models.py:2674-2689` (`HINEAssessment.is_normal`, `.severity_category`) -- READ-ONLY reference: canonical threshold (`score > 73` = Normal) these four filters must match
- `patients/models.py:454-478` (`Patient.clean`) -- replace `validate_birth_weight` call with `validate_birth_weight_for_gestational_age`
- `ndas/custom_codes/validators.py:629-` (`validate_birth_weight_for_gestational_age`) -- READ-ONLY reference: already correct, already unit-tested in `patients/tests/test_validators.py`
- `patients/models.py:738-751` (`Patient.getRC`) -- replace `.filter(patient=self).last()` with `self.get_latest_hine_assessment()`
- `patients/models.py:843-851` (`Patient.get_latest_hine_assessment`) -- READ-ONLY reference: already-correct method being reused

## Tasks & Acceptance

**Execution:**
- [x] `ndas/custom_codes/custom_methods.py` -- in the `DX_NORMAL` branch, change `Q(...) and Q(...) and Q(...)` to `Q(...) | Q(...) | Q(...)` (matching the sibling `DIAGNOSED` branch's style), and fix the `gmassessment__diagnosis_conclusion` field reference to the correct related_name `gm_assessments__diagnosis_conclusion` (a separate, pre-existing invalid-field bug on the same line, silently masked by the `and` short-circuit until now — the other two `Q` objects were never reached, so Django never tried to resolve it) -- restores the exclusion of abnormal-GMA and abnormal-HINE patients from the DX_NORMAL classification
- [x] `patients/views.py` -- change all four `score__gte=60` occurrences (lines ~2832, 2859, 2915, 2941) to `score__gt=73` -- aligns the "normal" filter/stat with the model's canonical `is_normal`/`severity_category` definition
- [x] `patients/models.py` -- in `Patient.clean()`, import and call `validate_birth_weight_for_gestational_age(self.birth_weight, self.pog_wks, pog_days)` in place of `validate_birth_weight(self.birth_weight)`, keeping the existing `is_valid, message = result; if not is_valid: raise ValidationError(...)` structure -- activates the dead POG-specific validation
- [x] `patients/models.py` -- in `Patient.getRC`, replace `HINEAssessment.objects.filter(patient=self).last()` with `self.get_latest_hine_assessment()` -- fixes stale-data bug and reuses existing correct logic
- [x] new test file `ndas/tests/test_custom_methods.py` -- add tests for `getPatientList(PtStatus.DX_NORMAL)`: a patient with abnormal GMA (and otherwise-normal DA) is excluded; a patient with abnormal HINE (and otherwise-normal GMA/DA) is excluded; a fully-normal patient with videos is included
- [x] new test file `patients/tests/test_models.py` -- add tests for `Patient.getRC`: with two HINE records at different dates, the score used matches the most recent `date_of_assessment`, not the oldest
- [x] `patients/tests/test_validators.py` -- add a test that `Patient.full_clean()` (via `save()`) raises `ValidationError` on `birth_weight` for an implausible weight/gestational-age combination (e.g. `birth_weight=3000, pog_wks=22`), proving the POG-specific check is now wired into the model, not just the standalone validator function
- [x] `patients/tests/test_patient_crud.py` or same new file -- add a test asserting the HINE `score_range='normal'` filter excludes a score in the 60-73 "Mild Abnormality" range and includes a score above 73

**Acceptance Criteria:**
- Given a patient with an abnormal GMA diagnosis and a normal/absent developmental assessment, when `getPatientList(PtStatus.DX_NORMAL)` runs, then that patient is excluded
- Given a HINE assessment with score=70, when filtered with `score_range='normal'`, then it does not appear in the results
- Given a `Patient` with `birth_weight=3000` and `pog_wks=22`, when saved, then `ValidationError` is raised referencing `birth_weight`
- Given a patient with HINE records on 2026-01-01 (score=50) and 2026-06-01 (score=75), when `getRC` is evaluated, then the score used is 75, not 50

## Spec Change Log

- **Finding:** The implementation subagent flagged that this spec's Approach/Tasks text specified combining the DX_NORMAL branch's three `Q` objects with `&`, but `&` does not fix the bug the Problem statement describes — it would only exclude patients abnormal in all three of GMA/HINE/DA simultaneously, still misclassifying the (more common) single- or double-abnormality cases as DX_NORMAL. `|` is the correct combinator (De Morgan's law: excluding "any abnormality present" requires OR inside `.exclude()`), matching the sibling `DIAGNOSED` branch's existing style and the original codebase-review artifact's own corrected code snippet (`codebase-review-2026-08-23.md` adversarial finding #9), which used `|`. My draft had inherited `&` from a second, contradictory suggestion elsewhere in that same review document (its edge-case-hunter section) without independently re-deriving the boolean logic.
- **Amended:** `and` → `|` (not `&`) in both the Approach prose and the Tasks checklist item for the DX_NORMAL fix, plus documented the incidentally-required `gmassessment` → `gm_assessments` related-name correction the subagent made (necessary for the `|`-combined query to even execute — previously masked by the `and` short-circuit).
- **Known-bad state avoided:** Implementing `&` as originally specified would have shipped a DX_NORMAL classification that still silently mislabels most abnormal patients as normal — the exact defect this spec exists to fix, just narrowed to a rarer trigger condition.
- **KEEP:** Everything else in the Approach/Tasks — the `|` fix, the `gm_assessments` field correction, and all three other independent fixes (HINE thresholds, birth-weight validator, `getRC`) — was correctly implemented and verified against this spec's Acceptance Criteria and I/O Matrix, which were accurate all along and did not need amendment.

## Verification

**Commands:**
- `python manage.py test ndas.tests.test_custom_methods patients.tests.test_models patients.tests.test_validators patients.tests.test_patient_crud` -- expected: all pass

## Suggested Review Order

**DX_NORMAL misclassification (Q-object short-circuit)**

- Core fix: `and` → `|`, plus the incidentally-required `gm_assessments` field-name correction, with an inline comment against reintroducing the bug.
  [`custom_methods.py:623`](../../ndas/custom_codes/custom_methods.py#L623)

- Regression coverage for both abnormal legs independently — the pre-fix bug only ever evaluated the developmental-assessment condition.
  [`test_custom_methods.py:55`](../../ndas/tests/test_custom_methods.py#L55)
  [`test_custom_methods.py:91`](../../ndas/tests/test_custom_methods.py#L91)

**HINE "normal" threshold mismatch (score>=60 vs model's score>73)**

- The four call sites (two filters, two stats aggregates) across the general and patient-scoped HINE managers.
  [`views.py:2832`](../../patients/views.py#L2832)
  [`views.py:2859`](../../patients/views.py#L2859)
  [`views.py:2915`](../../patients/views.py#L2915)
  [`views.py:2941`](../../patients/views.py#L2941)

- The template's NORMAL badge used the same stale threshold — found by the verification-gap review layer, fixed to keep the filter and the display consistent.
  [`manager.html:169`](../../templates/hine/manager.html#L169)
  [`manager.html:195`](../../templates/hine/manager.html#L195)

- Filter, badge, and the previously-uncovered patient-scoped route, all independently regression-tested.
  [`test_patient_crud.py:365`](../../patients/tests/test_patient_crud.py#L365)
  [`test_patient_crud.py:385`](../../patients/tests/test_patient_crud.py#L385)
  [`test_patient_crud.py:406`](../../patients/tests/test_patient_crud.py#L406)

**Birth-weight POG validation (dead validator call)**

- Swaps the raise-only `validate_birth_weight` for the tuple-returning, already-unit-tested `validate_birth_weight_for_gestational_age`.
  [`models.py:474`](../../patients/models.py#L474)

- Proves it's wired in at the model/save() level, not just correct as a standalone function.
  [`test_validators.py:224`](../../patients/tests/test_validators.py#L224)

**getRC stale-HINE-record bug (`.last()` on a descending-ordered queryset)**

- Reuses the already-correct `get_latest_hine_assessment()` instead of duplicating a broken query; the now-dead `try/except AttributeError` around it was removed too.
  [`models.py:747`](../../patients/models.py#L747)

- Confirms the newest score is used, with an inline sanity check showing what `.last()` would have wrongly returned.
  [`test_models.py:49`](../../patients/tests/test_models.py#L49)
