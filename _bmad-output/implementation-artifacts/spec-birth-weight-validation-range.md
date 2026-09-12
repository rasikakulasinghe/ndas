---
title: 'Simplify birth weight validation to a flat 200-8000g range'
type: 'refactor'
created: '2026-09-12'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'b8c699a04f9c51bed0db6ee6f5efb8d00a9bc57f'
route: 'one-shot'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Birth weight validation was split across two mechanisms: a basic 300-8000g field-level check (`validate_birth_weight`) and a gestational-age-aware (POG-specific) check in `Patient.clean()` that rejected weights implausible for a given gestational age. The user wants a single, simple rule instead.

**Approach:** Removed the POG-specific gestational-age check entirely (`validate_birth_weight_for_gestational_age`, `BIRTH_WEIGHT_RANGES_BY_POG`, the call site in `Patient.clean()`, and their dedicated tests) and changed the basic field-level validator's floor from 300g to 200g, so birth weight is now validated purely as "is it within 200-8000g" with no age-specific logic. Note: this reverts a deliberate, frozen, previously-approved fix in `spec-fix-medical-data-correctness.md` that had wired the POG-specific check in; the user was shown this conflict and explicitly chose to proceed anyway (see that spec's Change Log for the supersession note).

</frozen-after-approval>

## Suggested Review Order

**Validation range change**

- Core rule: floor changed from 300g to 200g; this is now the only birth-weight check.
  [`validators.py:499`](../../ndas/custom_codes/validators.py#L499)

- Removed call site: `Patient.clean()` no longer runs the gestational-age-aware check.
  [`models.py:454`](../../patients/models.py#L454)

**Removed POG-specific logic**

- `validate_birth_weight_for_gestational_age()` and `BIRTH_WEIGHT_RANGES_BY_POG` deleted outright (previously at the end of `validators.py`).

- `patients/tests/test_validators.py` deleted — it existed solely to test the removed POG-specific logic.

**Test coverage for the new range**

- Boundary tests for the new floor/ceiling (150/199/200/8000/8001) at the view layer.
  [`test_views.py:646`](../../patients/tests/test_views.py#L646)

**Peripherals**

- Validation-range doc comment updated to match.
  [`CLAUDE.md:159`](../../CLAUDE.md#L159)

- Supersession note recorded against the frozen spec this change knowingly reverts.
  [`spec-fix-medical-data-correctness.md:78`](../../_bmad-output/implementation-artifacts/spec-fix-medical-data-correctness.md#L78)
