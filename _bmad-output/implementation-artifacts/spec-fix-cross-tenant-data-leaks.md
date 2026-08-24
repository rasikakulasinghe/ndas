---
title: 'Fix cross-tenant data leaks (for_institution(None) unfiltered access)'
type: 'bugfix'
created: '2026-08-24'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '55dc7e7153cbda057002fc3a05fdbfb428641775'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `InstitutionScopedManager.for_institution(None)` intentionally returns unfiltered data (Phase 1 backward-compat, covered by `institution/tests/test_isolation.py::test_for_institution_none_returns_all` — do not change the manager). Two Phase-2-only referral views (`referral_initiate`, `patient_referrals_tab`) call it without guarding a None institution, so a user with no resolvable institution context (e.g. SUPERADMIN, or a broken institution FK) gets an unfiltered `Patient` queryset — cross-institution PHI exposure. Separately, `ExcelReportGenerator.generate()` accepts an `institution` kwarg (already passed correctly by `reports/views.py:163`) but never applies it to any of its six querysets — every Excel export leaks all institutions' data regardless of caller intent.

**Approach:** In `referral/views.py`, guard both call sites the same way `referral_inbox` (same file, line 157/165) already does: fall back to an empty queryset when `institution` is falsy, instead of passing `None` into `for_institution()`. In `reports/utils/excel_generator.py`, apply `institution` to all six querysets in `generate()`: use `Patient.objects.for_institution(institution)` for the patients sheet, and `.filter(patient__institution=institution)` (only when `institution` is truthy, preserving Phase-1 unfiltered behavior) for the five assessment-sheet querysets — matching the existing pattern already used in `cross_institution_aggregate()` (same file, lines 1031-1034).

## Boundaries & Constraints

**Always:** Preserve Phase-1 backward compatibility — when `institution` is `None`, behavior must stay unfiltered exactly as today (do not touch `institution/managers.py`). Reuse the exact `if institution else X.objects.none()` idiom already established in `referral_inbox`.

**Ask First:** Nothing expected — this is a narrow, well-precedented fix. If a fifth call site or a differently-shaped bug turns up during implementation, stop and ask rather than expanding scope.

**Never:** Do not modify `InstitutionScopedManager.for_institution()` itself (tested Phase-1 contract). Do not touch the `anonymize_data` flag threading in `excel_generator.py` or any other finding from the review — those are deferred (see `deferred-work.md`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Referral initiate, no institution | SUPERADMIN (institution=None) POSTs/GETs `referral_initiate` for any `patient_id` | Patient lookup queryset is empty | `get_object_or_404` raises `Http404`, caught by `@handle_view_errors`, redirects to `manage-patients` with the view's configured error message |
| Patient referrals tab, no institution | User with institution=None requests `patient_referrals_tab` for any `patient_id` | Patient lookup queryset is empty | Same `Http404` → `@handle_view_errors` → redirect `home` |
| Referral initiate, valid institution | User scoped to institution A requests patient belonging to institution B | Patient lookup queryset excludes B's patient | `Http404` as today (unchanged, already correct) |
| Excel export, institution scoped | Institution-scoped user exports all sheet types | Patients sheet + all 5 assessment sheets contain only that institution's records | N/A |
| Excel export, institution=None | Phase-1 caller (no institution) exports | All sheets unfiltered, identical to current behavior | N/A |

</frozen-after-approval>

## Code Map

- `referral/views.py:36-41` (`referral_initiate`) -- apply the `referral_inbox` (line 149-165) None-guard pattern to the patient lookup
- `referral/views.py:442-447` (`patient_referrals_tab`) -- same guard pattern
- `referral/views.py:149-165` (`referral_inbox`) -- READ-ONLY reference: existing correct `if institution else X.objects.none()` idiom to replicate
- `institution/managers.py:22-30` (`InstitutionScopedManager.for_institution`) -- READ-ONLY: confirmed intentional None=unfiltered contract, do not modify
- `reports/utils/excel_generator.py:765-857` (`ExcelReportGenerator.generate`) -- six querysets (patients, gm, hine, developmental, cdic, gpa) need institution scoping applied
- `reports/utils/excel_generator.py:1030-1035` (`cross_institution_aggregate`) -- READ-ONLY reference: existing correct `patient__institution=inst` filter pattern to replicate
- `reports/views.py:158-163` -- READ-ONLY: confirms `institution=getattr(request, 'institution', None)` is already passed into `generate()` correctly; only the generator body needs fixing

## Tasks & Acceptance

**Execution:**
- [x] `referral/views.py` -- in `referral_initiate`, change `Patient.objects.for_institution(institution)` to `(Patient.objects.for_institution(institution) if institution else Patient.objects.none())` -- closes the unfiltered-lookup leak for the initiate flow
- [x] `referral/views.py` -- apply the identical guard in `patient_referrals_tab`'s patient lookup -- closes the unfiltered-lookup leak for the referrals-tab flow
- [x] `reports/utils/excel_generator.py` -- change the patients queryset (line 766) from `Patient.objects.select_related(...).all()` to `Patient.objects.for_institution(institution).select_related(...)` -- scopes the patients sheet
- [x] `reports/utils/excel_generator.py` -- after each of the five assessment querysets (gm/hine/developmental/cdic/gpa, lines ~785/800/815/830/845), add `if institution: queryset = queryset.filter(patient__institution=institution)` before `apply_advanced_filters` is called -- scopes every assessment sheet, preserves Phase-1 unfiltered behavior when institution is None
- [x] `referral/tests/test_initiation.py` -- add a test asserting a user with no resolvable institution context gets a redirect on `referral_initiate` rather than patient data (SUPERADMIN swapped for a plain USER with institution=None: SUPERADMIN is intercepted by InstitutionContextMiddleware before reaching the view, so it can't exercise this guard)
- [x] `referral/tests/test_patient_tab.py` -- add the equivalent no-institution-context test for `patient_referrals_tab`
- [x] `reports/tests/test_security.py` -- add a test asserting `ExcelReportGenerator.generate(institution=inst_a)` excludes institution B's patients and assessments across all six sheet types, and that `institution=None` stays unfiltered

**Acceptance Criteria:**
- Given a user with no resolvable institution, when they hit `referral_initiate` or `patient_referrals_tab` for any patient, then they get a 404/redirect, never another institution's patient data
- Given `institution=None` is passed to `ExcelReportGenerator.generate()`, when the report is built, then all sheets remain unfiltered (unchanged Phase-1 behavior)
- Given `institution=<Institution A>` is passed to `ExcelReportGenerator.generate()`, when the report is built, then every sheet (patients + all 5 assessment types) contains only Institution A's records
- Given the existing `institution/tests/test_isolation.py::test_for_institution_none_returns_all` test, when the full test suite runs, then it still passes unmodified

## Verification

**Commands:**
- `python manage.py test referral.tests.test_initiation referral.tests.test_patient_tab reports.tests.test_security institution.tests.test_isolation` -- expected: all pass, including the new and existing None-context tests

## Suggested Review Order

**Referral view guards (the leak's original entry points)**

- Core fix: guard the patient lookup so `institution=None` yields an empty queryset instead of every patient, mirroring `referral_inbox`'s existing idiom.
  [`referral/views.py:39`](../../referral/views.py#L39)

- Same guard applied to the patient-referrals-tab lookup.
  [`referral/views.py:445`](../../referral/views.py#L445)

**Excel export scoping (the second leak site)**

- Patients sheet now goes through `for_institution()` instead of `.all()`, so it honors the caller-supplied institution for the first time.
  [`reports/utils/excel_generator.py:766`](../../reports/utils/excel_generator.py#L766)

- Each of the 5 assessment querysets gets the same `patient__institution` guard, matching the pattern already used in `cross_institution_aggregate()`.
  [`reports/utils/excel_generator.py:791`](../../reports/utils/excel_generator.py#L791)
  [`reports/utils/excel_generator.py:809`](../../reports/utils/excel_generator.py#L809)
  [`reports/utils/excel_generator.py:827`](../../reports/utils/excel_generator.py#L827)
  [`reports/utils/excel_generator.py:845`](../../reports/utils/excel_generator.py#L845)
  [`reports/utils/excel_generator.py:863`](../../reports/utils/excel_generator.py#L863)

**Tests**

- Regression test: a user with no resolvable institution gets redirected, never handed the patient.
  [`test_initiation.py:136`](../../referral/tests/test_initiation.py#L136)

- Same regression test for the referrals-tab view.
  [`test_patient_tab.py:151`](../../referral/tests/test_patient_tab.py#L151)

- Excel scoping test fixture — deliberately asymmetric (2 patients for inst A, 1 for inst B) so a mis-scoped filter can't pass by coincidence.
  [`test_security.py:157`](../../reports/tests/test_security.py#L157)

- Institution A scoped export returns exactly its 2 records, never institution B's.
  [`test_security.py:262`](../../reports/tests/test_security.py#L262)

- Institution B scoped export returns exactly its 1 record, pinning down that scoping tracks whichever institution is passed in.
  [`test_security.py:279`](../../reports/tests/test_security.py#L279)

- `institution=None` stays fully unfiltered (Phase-1 backward compatibility, unchanged).
  [`test_security.py:294`](../../reports/tests/test_security.py#L294)
