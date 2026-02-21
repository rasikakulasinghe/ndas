# Epic 1: Critical Bug Fixes

**Priority:** Immediate — fix before next deployment
**Source:** Code Audit Adversarial Review (2026-02-20)
**Scope:** `patients/views.py`, `patients/models.py`

Fix the three confirmed bugs that produce incorrect output or silent data corruption in the application.

---

## Story 1.1: Fix Method Reference Bug in Patient View

**Audit Finding:** BUG-01
**File:** `patients/views.py:399`
**Severity:** Critical

### Description

`gm_last_assessment = var_gma.last` stores the bound method object itself instead of calling it. The template receives a method reference and renders its string representation instead of the actual last GMAssessment object. This silently shows garbage in any template using this value.

### Acceptance Criteria

- [ ] `var_gma.last` is changed to `var_gma.last()` at `patients/views.py:399`
- [ ] The patient view template correctly renders the last GMA assessment data
- [ ] No other `.last` or `.first` method references without parentheses exist in `patients/views.py`
- [ ] Manual verification: load a patient detail page and confirm the last assessment displays correctly

---

## Story 1.2: Fix Birth Weight Validation Range Inconsistency

**Audit Finding:** BUG-02
**File:** `patients/views.py:320` vs `CLAUDE.md`
**Severity:** Critical

### Description

The view validates birth weight with a lower bound of 200g (`birth_weight < 200`), but CLAUDE.md documents the valid range as 300g–8000g. The model validator enforces 300g. A weight of 250g passes the view check but fails the model validator with an unhandled 500 error instead of a user-friendly form message.

### Acceptance Criteria

- [ ] Birth weight lower bound in `patients/views.py` changed from `200` to `300`
- [ ] The view validation range matches CLAUDE.md and the model validator exactly (300g–8000g)
- [ ] Entering 250g in the patient add form returns a user-friendly validation error message
- [ ] Entering 300g is accepted normally
- [ ] Entering 200g is rejected with a clear error message

---

## Story 1.3: Remove Duplicate Context Key in Dashboard View

**Audit Finding:** BUG-03
**File:** `patients/views.py:175` and `patients/views.py:185`
**Severity:** Medium

### Description

The dashboard context dict contains `"videos_total_count"` as a duplicate key. Python silently uses the last value. Currently both lines assign the same variable so the bug is latent, but it will silently break if either line is edited in future.

### Acceptance Criteria

- [ ] The duplicate `"videos_total_count"` key is removed from the dashboard context dict
- [ ] Only one `"videos_total_count"` key appears in the context
- [ ] Dashboard renders correctly and shows the correct video count
- [ ] A search for duplicate keys in the same context dict confirms no other duplicates exist
