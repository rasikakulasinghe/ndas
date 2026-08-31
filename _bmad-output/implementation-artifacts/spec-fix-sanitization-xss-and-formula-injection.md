---
title: 'Fix sanitize_text_input protocol-obfuscation bypass and Excel formula injection'
type: 'bugfix'
created: '2026-08-31'
status: 'done'
review_loop_iteration: 0
context: []
route: 'one-shot'
---

# Fix sanitization XSS bypass and Excel formula injection

## Intent

**Problem:** Two unrelated injection gaps from the 2026-08-25 whole-app bmad-review: (1) `sanitize_text_input()`'s dangerous-protocol strip used a literal-string regex that a whitespace/control-character-obfuscated payload like `"java\tscript:alert(1)"` sails through untouched, even though a browser still parses it as a live `javascript:` URI; (2) Excel exports (`reports/utils/excel_generator.py`, `problemlist/views.py`) write user-controlled free text into cells with no escaping, so a value starting with `=`/`+`/`-`/`@` becomes a live formula for whoever opens the file (formula/DDE injection).

**Approach:** Hardened the protocol-strip regex to allow `\s*` between every character of each protocol name, guarded by a leading `\b` and a `(?=\S)` lookahead after the colon so ordinary English labels like `"Data: BP 120/80"` are not falsely stripped. Added shared `escape_excel_formula()`/`escape_excel_row()` helpers to `ndas/custom_codes/custom_methods.py` and wired them into every place a data row is written to a workbook.

## Suggested Review Order

1. [ndas/custom_codes/validators.py](../../ndas/custom_codes/validators.py) — `sanitize_text_input()`'s hardened protocol-strip regex
2. [ndas/tests/test_validators_sanitization.py](../../ndas/tests/test_validators_sanitization.py) — obfuscation + false-positive regression tests
3. [ndas/custom_codes/custom_methods.py](../../ndas/custom_codes/custom_methods.py) — `escape_excel_formula`/`escape_excel_row` (shared helpers)
4. [ndas/tests/test_custom_methods.py](../../ndas/tests/test_custom_methods.py) — unit tests for the two helpers
5. [reports/utils/excel_generator.py](../../reports/utils/excel_generator.py) — `sanitize_row()` delegates to the shared helper, wired into all 6 sheet builders
6. [problemlist/views.py](../../problemlist/views.py) — `problem_analysis_export` wired to the shared helper
7. [reports/tests/test_security.py](../../reports/tests/test_security.py), [problemlist/tests.py](../../problemlist/tests.py) — end-to-end escaping tests
8. [CLAUDE.md](../../CLAUDE.md), [docs/custom-codes-reference.md](../../docs/custom-codes-reference.md) — documented for future export code
9. [_bmad-output/implementation-artifacts/deferred-work.md](deferred-work.md) — follow-ups logged from blind-hunter review

## Code Map

- `ndas/custom_codes/validators.py:66-83` -- `sanitize_text_input()` -- hardened protocol-strip regex
- `ndas/custom_codes/custom_methods.py` -- `escape_excel_formula`, `escape_excel_row` (new) -- single source of truth for the fix
- `reports/utils/excel_generator.py` -- `ExcelReportGenerator.sanitize_row()` (now delegates), all 6 `add_*_sheet` methods -- wired in
- `problemlist/views.py:591-606` -- `problem_analysis_export` -- wired in

## Tasks & Acceptance

**Execution:**
- [x] `ndas/custom_codes/validators.py` -- harden the dangerous-protocol regex with `\s*` obfuscation tolerance, `\b` word boundary, `(?=\S)` lookahead -- close the bypass without breaking medical-notation preservation
- [x] `ndas/tests/test_validators_sanitization.py` -- add obfuscation tests (tab/newline/space, all 3 protocols) and false-positive tests (`"Data: BP 120/80"`, `"metadata:version=2"`) -- verify both directions
- [x] `ndas/custom_codes/custom_methods.py` -- add `escape_excel_formula`/`escape_excel_row` (covers `=`/`+`/`-`/`@`/tab/CR) -- shared fix
- [x] `ndas/tests/test_custom_methods.py` -- unit tests for the two helpers -- verify the fix
- [x] `reports/utils/excel_generator.py` -- delegate `sanitize_row()` to the shared helper, apply to all 6 `ws.append(row)` call sites -- close the export leak
- [x] `problemlist/views.py` -- apply `escape_excel_row` to `problem_analysis_export`'s row -- close the export leak
- [x] `reports/tests/test_security.py`, `problemlist/tests.py` -- add end-to-end tests generating a real `.xlsx`, reading it back with openpyxl, asserting escaping -- verify the fix
- [x] `CLAUDE.md`, `docs/custom-codes-reference.md` -- document the helper as mandatory for new Excel exports -- prevent regression
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- log out-of-scope follow-ups (HTML-comment obfuscation bypass class)

**Acceptance Criteria:**
- Given `"java\tscript:alert(1)"`, `"java\nscript:alert(1)"`, `"da ta:text/html,..."`, or `"vb\tscript:msgbox(1)"`, when passed to `sanitize_text_input()`, then the protocol scheme is stripped (verified).
- Given `"Investigation data: pending review"` or `"See metadata:version=2 for details"`, when passed to `sanitize_text_input()`, then the text survives unchanged (verified) — the hardened regex must not regress medical-notation preservation.
- Given a patient/problem field starting with `=`, `+`, `-`, or `@`, when exported via the Excel report builder or `problem_analysis_export`, then the generated `.xlsx` cell value is prefixed with a literal single-quote (verified via real openpyxl write+read round trip for `=`, `+`, `-`; `@` verified end-to-end in `problemlist`, at the unit level for `reports`).

## Verification

**Commands:**
- `python manage.py test ndas.tests.test_validators_sanitization ndas.tests.test_custom_methods reports.tests.test_security problemlist.tests.ProblemAnalysisExportFormulaInjectionTest -v 1` -- expected: `OK` (44/44, verified)
- `python manage.py test ndas reports patients.tests.test_validators -v 1` -- expected: `OK`, no regressions from the `sanitize_text_input` regex change (86/86, verified)
