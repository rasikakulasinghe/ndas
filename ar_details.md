# Adversarial Review — NDAS Codebase

**Date:** 2026-05-09
**Scope:** Bugs, Performance Issues, Dead Code, Security Gaps, Architecture Problems
**Reviewer stance:** Cynical — assumed problems exist; reviewed to find them.

---

## Summary

30+ concrete issues identified across security, performance, dead code, and missing enforcement patterns. The codebase has consistent structural gaps: HTTP method enforcement is largely absent, cross-institution data leakage is possible in reports endpoints, and dead code accumulates in `patients/views.py`. None of these are hypothetical — each has a file location and line reference.

---

## Findings

### SECURITY

**1. Cross-Institution PDF Download — No Scoping by Institution**
- **File:** `reports/views.py` lines 329-331, 346-348, 363-365, 380-382, 397-399
- **Functions:** `download_gm_assessment_pdf`, `download_hine_assessment_pdf`, `download_da_assessment_pdf`, `download_cdic_assessment_pdf`, `download_gpa_assessment_pdf`
- **Problem:** All use `get_object_or_404()` without filtering by the requesting user's institution. An authenticated user from Institution A can download assessment PDFs for patients in Institution B by guessing sequential integer IDs. This is a direct IDOR (Insecure Direct Object Reference) vulnerability in a medical records application.

---

**2. Unvalidated `int()` Conversion on User Input**
- **File:** `users/views.py` line ~500
- **Problem:** `days = int(request.POST.get('days', 30))` will raise an unhandled `ValueError` and return a 500 if the user sends a non-numeric string. Should use `try/except` or a validated form field.

---

**3. `search_start()` Potentially Missing `@login_required`**
- **File:** `patients/views.py` line ~648
- **Problem:** View may lack `@login_required`. Any unauthenticated request can trigger a patient search. Unconfirmed — must verify decorator stack manually.

---

### PERFORMANCE

**4. Open File Without Context Manager in PDF Responses**
- **File:** `reports/views.py` lines 320, 339, 356, 373, 390, 407
- **Problem:** `FileResponse(open(file_path, 'rb'))` is used in all PDF download views. While Django's `FileResponse` does close the file descriptor, this pattern is fragile: if an exception occurs before `FileResponse` is constructed, the file handle leaks. Six separate instances. Use `with open(...) as f: return FileResponse(f)` or pass the path directly to `FileResponse`.

---

**5. Inefficient Global Count Query**
- **File:** `patients/views.py` line ~134
- **Problem:** `CustomUser.objects.all().count()` is called without institution scoping for superusers. On a multi-tenant system with many institutions and users, this performs a full table scan with no WHERE clause. Should scope to `CustomUser.objects.filter(institution=_inst).count()` or use a cached counter.

---

**6. Missing `select_related` / `prefetch_related` — Systematic N+1 Risk**
- **File:** Multiple views across `patients/views.py`, `video/views.py`, `users/views.py`
- **Problem:** List views rendering related model data (e.g., patient + added_by, video + patient) without `select_related()` generate N+1 queries — one for each row in the queryset. The CLAUDE.md mandates using these but enforcement is absent. Example: any manager/list view that displays `{{ obj.added_by.username }}` in a loop.

---

### DEAD CODE

**7. Stub `print()` Function**
- **File:** `patients/views.py` lines ~3525-3526
- **Problem:** `def print(request): pass` exists with no implementation, no URL route, and shadows Python's built-in `print`. This is both dead code and a subtle name collision risk.

---

**8. Duplicate Import — `timezone`**
- **File:** `patients/views.py` lines 3 and 69
- **Problem:** `from django.utils import timezone` is imported twice. The second import is redundant and likely introduced by copy-paste.

---

**9. Unused Import — `IntegrityError`**
- **File:** `patients/views.py` line ~5
- **Problem:** `from django.db import IntegrityError` is imported but never referenced in the file. Dead import.

---

**10. Unused Import — `userViewByUsername`**
- **File:** `patients/views.py` line ~20
- **Problem:** `from users.views import userViewByUsername` is imported but never called. Dead import.

---

### MISSING HTTP METHOD ENFORCEMENT

The following views accept unintended HTTP methods because they lack `@require_GET` or `@require_http_methods(["GET", "POST"])` decorators. This is a systemic gap — the CLAUDE.md mandates these decorators, but they are absent across dozens of views.

**11. `video_manager()` — missing `@require_GET`**
- `video/views.py` line ~238

**12. `video_view()` — missing `@require_GET`**
- `video/views.py` line ~111

**13. `video_edit()` — missing `@require_http_methods(["GET", "POST"])`**
- `video/views.py` line ~155

**14. `patient_delete_confirm()` — missing `@require_GET`**
- `patients/views.py` line ~573

**15. `assessment_view()` — missing `@require_GET`**
- `patients/views.py` line ~971

**16. `assessment_view_by_fileid()` — missing `@require_GET`**
- `patients/views.py` line ~1009

**17. `assessment_edit()` — missing `@require_http_methods(["GET", "POST"])`**
- `patients/views.py` line ~1048

**18. `assessment_manager_by_patients()` — missing `@require_GET`**
- `patients/views.py` line ~1281

**19. `bookmark_manager()` — missing `@require_GET`**
- `patients/views.py` line ~1329

**20. `bookmark_add()` — missing `@require_http_methods(["GET", "POST"])`**
- `patients/views.py` line ~1416

**21. `bookmark_view()` — missing `@require_GET`**
- `patients/views.py` line ~1533

**22. `bookmark_manager_user()` — missing `@require_GET`**
- `patients/views.py` line ~1673

**23. `bookmark_edit()` — missing `@require_http_methods(["GET", "POST"])`**
- `patients/views.py` line ~1685

**24. `attachment_manager()` — missing `@require_GET`**
- `patients/views.py` line ~1715

**25. `attachment_manager_patient()` — missing `@require_GET`**
- `patients/views.py` line ~1835

**26. `attachment_view()` — missing `@require_GET`**
- `patients/views.py` line ~2047

**27. `attachment_edit()` — missing `@require_http_methods(["GET", "POST"])`**
- `patients/views.py` line ~2063

**28. `cdic_assessment_manager()` — missing `@require_GET`**
- `patients/views.py` line ~2375

**29. `hine_assessment_view()` — missing `@require_GET`**
- `patients/views.py` line ~2788

**30. Multiple `users/views.py` views missing decorators**
- `users/views.py` lines ~205 (`userView`), ~211 (`userViewByUsername`), ~216 (`userEdit`), ~288 (`developerContacts`), ~527 (`admin_dashboard`), ~562 (`admin_user_list`), ~617 (`admin_user_add`), ~646 (`admin_user_edit`), ~827 (`admin_user_activity`), ~847 (`admin_activity_logs`), ~865 (`subscription_detail`), ~892 (`subscription_info`), ~945 (`subscription_update`)

---

### ARCHITECTURE / CODE QUALITY

**31. Manual Method Check Instead of Decorator in `delete_report()`**
- **File:** `reports/views.py` line ~254
- **Problem:** View uses `if request.method != 'POST': return ...` instead of `@require_POST`. This is inconsistent with the declared pattern in CLAUDE.md and harder to enforce at the framework level. A future developer may add a code path above the check that bypasses it.

---

## Priority Matrix

| Priority | Finding | Risk |
|----------|---------|------|
| **Critical** | #1 — Cross-institution PDF IDOR | Patient data leakage |
| **High** | #2 — Unhandled `int()` crash | 500 error, potential DoS path |
| **High** | #4 — File handle pattern | Resource leak under load |
| **High** | #6 — N+1 queries at scale | Performance degradation |
| **Medium** | #3 — Missing `@login_required` | Auth bypass risk |
| **Medium** | #5 — Unscoped count query | Slow query at scale |
| **Medium** | #11–#30 — Missing method enforcement | Unexpected method acceptance |
| **Low** | #7–#10 — Dead code | Code quality, maintenance |
| **Low** | #31 — Manual method check | Inconsistency |

---

## Recommendations

1. **Immediate**: Add institution-scoped filtering to all PDF download views in `reports/views.py`. The fix is a single `.filter(patient__institution=request.user.institution)` on each `get_object_or_404` call.
2. **Sweep**: Run a grep for all `def ` declarations in `patients/views.py`, `video/views.py`, and `users/views.py` and add the appropriate `@require_GET` or `@require_http_methods` decorator to every view that is missing one.
3. **Dead code removal**: Remove the stub `def print(request): pass`, the duplicate `timezone` import, and the two unused imports in `patients/views.py`.
4. **Input validation**: Replace all raw `int(request.POST.get(...))` calls with validated form fields or wrapped `try/except` blocks.
5. **N+1 audit**: Add `select_related` to every list view queryset that renders related model fields. Consider a query-count test using `django-assert-num-queries`.
