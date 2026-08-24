- source_spec: none
  summary: Fix auth/permission bypasses (bookmark IDOR, CSRF-unsafe GET mutation, open redirect, bookmark delete-permission bug)
  evidence: Split from "fix all issues in codebase-review-2026-08-23" — distinct root cause (access control) from the cross-tenant data-scoping fix, independently shippable per the review's suggested fixation order group 2. See codebase-review-2026-08-23.md items patients/views.py:1672-1681, referral/views.py:548-572, institution/middleware.py:136-138, ndas/custom_codes/delete_helpers.py:47-50.

- source_spec: none
  summary: Fix medical-data-correctness bugs (DX_NORMAL Q-object short-circuit, HINE "normal" threshold mismatch, birth-weight validation never running, HINE .last() vs .first() bug)
  evidence: Split from "fix all issues in codebase-review-2026-08-23" — distinct root cause (clinical classification logic) from the cross-tenant data-scoping fix, independently shippable per the review's suggested fixation order group 3. See codebase-review-2026-08-23.md items ndas/custom_codes/custom_methods.py:623-628, patients/views.py:2824-2830, patients/models.py:471-478, patients/models.py:748-751.

- source_spec: none
  summary: Fix security-sanitization gaps (sanitize-then-unescape XSS bypass, reverse-tabnabbing missing rel=noopener, virus-scan stub always reports clean)
  evidence: Split from "fix all issues in codebase-review-2026-08-23" — distinct root cause (input/output sanitization) from the cross-tenant data-scoping fix, independently shippable per the review's suggested fixation order group 4. See codebase-review-2026-08-23.md items ndas/custom_codes/validators.py:42-61, ndas/custom_codes/sanitization.py:37-61, patients/models.py:1931-1937.

- source_spec: none
  summary: Batch-fix remaining ~180 mechanical findings (N+1 queries, missing db_index, bare except-Exception error-swallowing, duplicate sanitize_filename/clean_profile_picture helpers, dead code, admin/UI bugs) across all 8 apps
  evidence: Split from "fix all issues in codebase-review-2026-08-23" — lower-risk, high-volume cross-cutting cleanup best tackled as its own batch(es) per the review's suggested fixation order group 5, rather than folded into the higher-risk security/correctness fixes tackled first.

- source_spec: `_bmad-output/implementation-artifacts/spec-fix-cross-tenant-data-leaks.md`
  summary: reports/tasks.py's generate_excel_report_task (Celery async Excel export) never passes institution into ExcelReportGenerator.generate(), so it silently defaults to unfiltered/all-institutions
  evidence: Surfaced independently by both the blind-hunter and verification-gap review layers during the cross-tenant-leak fix. Confirmed via repo-wide search that the task has no .delay()/.apply_async() call site today (unreachable), so it's out of scope for this story, but it reintroduces the exact leak this spec fixes the moment it's wired up — should be fixed before that task is ever dispatched.

- source_spec: `_bmad-output/implementation-artifacts/spec-fix-cross-tenant-data-leaks.md`
  summary: InstitutionScopedManager has no safe helper (e.g. for_institution_or_none()) to stop future call sites from repeating the for_institution(None)-returns-unfiltered footgun this spec just patched at multiple call sites
  evidence: Raised by the blind-hunter review layer — the fix pattern (`for_institution(institution) if institution else X.objects.none()`) is now duplicated ad hoc across referral/views.py (x3) and the Excel generator with no shared abstraction or guard, so the next call site can silently reintroduce the same cross-tenant leak. Architectural improvement, not appropriate to bundle into this narrow bugfix (spec's Never section forbids touching InstitutionScopedManager itself).
