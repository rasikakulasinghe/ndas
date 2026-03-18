# Adversarial Review — NDAS Codebase
**Date:** 2026-03-12
**Scope:** Inconsistencies, bugs, dead code, performance issues, security misalignments
**Total Findings:** 22

---

## CRITICAL

### 1. Institution Scope Not Enforced on `bookmark_view`
**File:** `patients/views.py:1572`
An explicit `# TODO: enforce institution scope` comment exists. Users from Institution A can access bookmarks belonging to Institution B. Multi-tenancy isolation is broken here.

### 2. Unimplemented Virus Scanning
**File:** `patients/models.py:1808`
A `# TODO: Implement actual virus scanning with ClamAV or similar` comment is in place. All file uploads (videos, documents, images) enter the system and are served to other users with zero malware detection.

### 3. `MultipleObjectsReturned` Not Caught on `.objects.get()` Calls
**Files:** `users/views.py:300`, `users/views.py:342`, `institution/middleware.py:69`
These locations only catch `DoesNotExist`. If data constraints are violated, uncaught `MultipleObjectsReturned` causes 500 errors. The middleware failure breaks every request for every user.

---

## HIGH

### 4. Catastrophic N+1 Queries from Patient Model Properties
**File:** `patients/models.py:384–543`
Properties `isNewPatient`, `isDischarged`, `isLastGMANormal`, `isLastHINENormal`, `isLastDANormal`, and `getDiagnosisList` each fire separate DB queries on every access. The dashboard iterating over a patient list triggers hundreds of queries. These properties are used in templates without any warning of their cost.

### 5. Compound N+1 Chain via `isDiagnosisNormal`
**File:** `patients/models.py:479–481`
This single property delegates to three other DB-hitting properties, firing 6+ queries per access. Templates cannot see this cost.

### 6. Middleware Fires a Raw DB Query on Every Request
**File:** `institution/middleware.py:69`
`Institution.objects.get(pk=active_id, is_active=True)` is called for every single HTTP request for every user. No caching. Under load, this exhausts database connections and takes down the application.

### 7. Weak Login Rate Limiting (Per-IP Only)
**File:** `users/views.py:36`
Uses `ratelimit(key='ip', rate='3/m')`. No rate limiting per username. Attackers distribute attempts across IPs, achieving unlimited brute-force with 3 attempts per IP per minute.

### 8. Weak Password Reset Rate Limiting
**File:** `users/views.py:369–382`
Limits only 3/hour per IP. No per-email limiting. Attackers can flood target users with reset emails from different IPs.

### 9. `institution_scope()` Output Not Validated
**File:** `patients/views.py:1595`
This function is security-critical for multi-tenancy isolation, yet its return value is splatted directly into querysets with `**institution_scope(...)`. If the middleware fails to set institution context, this silently fails in unpredictable ways.

### 10. Incomplete Access Control Architecture
**File:** `patients/models.py:1896–1899`
Two consecutive `# TODO: Implement department-based access` and `# TODO: Implement team-based access` comments. Access control only falls back to institution-level, meaning intra-institution data segregation does not exist.

### 11. Missing Transaction Isolation on Concurrent Video Uploads
**File:** `video/models.py:215–285`
The `save()` method checks metadata fields, then performs expensive extraction (seconds), then saves. A concurrent request can overwrite changes in the window between check and save. No `atomic()` block wraps the operation.

### 12. No Audit Trail for Institution Context Switches
**File:** `institution/views.py:78+`
Successful institution access switches are not logged. In a healthcare system, forensic analysis cannot trace which institution a user accessed data from or when. This is a compliance gap.

---

## MEDIUM

### 13. Missing Pagination on Assessment Querysets
**File:** `patients/views.py:1284`
`base_qs.all()` fetches ALL assessments with no pagination. Patients with years of records will cause full-table loads into memory, making the UI unusable.

### 14. Commented-Out Form Fields Create Invisible Data Loss
**File:** `patients/forms.py:671–674`
Fields `is_discharged`, `discharg_on`, `discharg_plan`, `other_details` exist in the CDIC model but are commented out of the form's widget definitions. The fields exist but the UI can never populate them; existing data is silently ignored on re-save.

### 15. Broad `except Exception` Clauses Mask Real Errors
**Files:** Multiple views in `patients/views.py`
Catching `Exception` swallows `AttributeError`, `TypeError`, `SystemExit`, and `KeyboardInterrupt`. Real programming bugs are silently logged and suppressed, making debugging very difficult.

### 16. CSRF `querySelector` Can Throw if DOM Is Malformed
**File:** `templates/attachment/add.html`
JavaScript does `document.querySelector('[name=csrfmiddlewaretoken]').value` with no null check. If the CSRF field is absent due to template inheritance issues, this throws `TypeError` silently and the upload fails with no user-facing message.

### 17. Timezone Handling Inconsistency
**Files:** Various views and `video/models.py:46–47`
Some code uses `timezone.now()` while other parts use `date.today()`. Video recording date validation mixes timezone-aware and naive comparisons, which can reject valid records or accept invalid ones depending on UTC offset.

### 18. Unhandled `IntegrityError` Types
**Files:** Multiple edit/add views in `patients/views.py`
Broad `except IntegrityError` returns a generic message regardless of whether it's a duplicate key (user error), foreign key violation (data corruption), or check constraint failure (validation bug). Different causes need different responses.

### 19. Orphaned Temporary Files on Extraction Failure
**File:** `video/models.py:297–318`
`tempfile.NamedTemporaryFile(delete=False, ...)` creates temp files that may not be cleaned up if an exception occurs before the `finally` block. On Windows, locked files resist deletion entirely, slowly consuming disk space.

---

## LOW / CODE QUALITY

### 20. Inconsistent Naming Convention (camelCase vs snake_case)
**File:** `patients/models.py`
Model properties use camelCase (`isNewPatient`, `isDischarged`, `getAPGAR`, `getDiagnosisList`) alongside Django's snake_case convention. Backward compatibility aliases are scattered without a clean migration path. New developers will perpetuate the wrong convention.

### 21. Significant Code Duplication Across View Handlers
**File:** `patients/views.py`
`patient_add`, `patient_edit`, and `patient_manager` repeat the same validation, institution scoping, and error-handling blocks. Security fixes applied to one are likely missed in others.

### 22. Unsafe Redundant Field Filter on PK Lookup
**File:** `institution/middleware.py:69`
`Institution.objects.get(pk=active_id, is_active=True)` — PK is already uniquely constraining. Adding `is_active=True` means a soft-deleted institution with a valid PK causes `DoesNotExist` instead of a meaningful soft-delete error, masking the real state.

---

## Summary Table

| # | Severity | Category | Issue | File |
|---|----------|----------|-------|------|
| 1 | CRITICAL | Security | Institution scope missing on bookmark_view | `patients/views.py:1572` |
| 2 | CRITICAL | Security | Virus scanning not implemented | `patients/models.py:1808` |
| 3 | CRITICAL | Reliability | `MultipleObjectsReturned` uncaught | `users/views.py:300,342`; `institution/middleware.py:69` |
| 4 | HIGH | Performance | N+1 queries in Patient model properties | `patients/models.py:384–543` |
| 5 | HIGH | Performance | Compound N+1 via `isDiagnosisNormal` | `patients/models.py:479–481` |
| 6 | HIGH | Performance | Middleware DB query on every request | `institution/middleware.py:69` |
| 7 | HIGH | Security | Weak login rate limiting (IP only) | `users/views.py:36` |
| 8 | HIGH | Security | Weak password reset rate limiting | `users/views.py:369–382` |
| 9 | HIGH | Security | `institution_scope()` output unvalidated | `patients/views.py:1595` |
| 10 | HIGH | Security | Incomplete dept/team access control | `patients/models.py:1896–1899` |
| 11 | HIGH | Reliability | No transaction isolation on video save | `video/models.py:215–285` |
| 12 | HIGH | Compliance | No audit log for institution access | `institution/views.py:78+` |
| 13 | MEDIUM | Performance | No pagination on assessment queryset | `patients/views.py:1284` |
| 14 | MEDIUM | Code Quality | Commented-out form fields cause data loss | `patients/forms.py:671–674` |
| 15 | MEDIUM | Reliability | Broad `except Exception` masks real bugs | `patients/views.py` (multiple) |
| 16 | MEDIUM | Reliability | CSRF querySelector no null check | `templates/attachment/add.html` |
| 17 | MEDIUM | Reliability | Mixed timezone-aware/naive comparisons | `video/models.py:46–47` |
| 18 | MEDIUM | Reliability | All IntegrityError types get same response | `patients/views.py` (multiple) |
| 19 | MEDIUM | Stability | Temp files can be orphaned on failure | `video/models.py:297–318` |
| 20 | LOW | Code Quality | camelCase/snake_case naming mix | `patients/models.py` |
| 21 | LOW | Maintainability | Code duplication across view handlers | `patients/views.py` |
| 22 | LOW | Code Quality | Redundant is_active filter on PK lookup | `institution/middleware.py:69` |
