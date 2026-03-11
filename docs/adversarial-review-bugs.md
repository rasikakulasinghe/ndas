# NDAS Adversarial Review — Major Bugs, Inconsistencies & Performance Issues

**Review Date:** 2026-03-10
**Reviewer:** Claude Code (Adversarial Review — General)
**Scope:** Full codebase — backend (Django views, models, middleware, utilities) and frontend (templates, HTMX, forms)
**Method:** Static analysis across all apps: `patients/`, `users/`, `video/`, `reports/`, `problemlist/`, `institution/`, `ndas/custom_codes/`

---

## Severity Classification

| Level | Meaning |
|-------|---------|
| **CRITICAL** | Direct data breach, security bypass, or production stability risk |
| **MAJOR** | Significant bug, data integrity risk, or severe performance degradation |

---

## Findings

---

### 1. Assessment Querysets Unscoped by Institution

**Severity:** CRITICAL
**File:** `patients/views.py` lines ~377–426
**Type:** Security — Data Isolation

**Description:**
The `patient_view()` function retrieves all related assessments using only `filter(patient=selected_patient)` with no institution scoping applied:

```python
var_gma  = list(GMAssessment.objects.select_related(...).filter(patient=selected_patient).order_by("-id"))
var_hine = list(HINEAssessment.objects.select_related(...).filter(patient=selected_patient).order_by("-id"))
var_da   = list(DevelopmentalAssessment.objects.select_related(...).filter(patient=selected_patient).order_by("-id"))
var_cdic = list(CDICRecord.objects.select_related(...).filter(patient=selected_patient).order_by("-id"))
var_gpa  = list(GeneralPaediatricAssessment.objects.select_related(...).filter(patient=selected_patient).order_by("-id"))
var_file_video = list(Video.objects.select_related(...).filter(patient=selected_patient).order_by("-id"))
```

`institution_scope()` is never applied to any of these querysets. A superadmin switching institution context, or any edge-case where `selected_patient` is not validated against the active institution, exposes all assessments for that patient regardless of institutional ownership.

**Risk:** Cross-institutional clinical data exposure — violates FR47 and NFR21 (data isolation requirements).

**Fix:** Apply `institution_scope(request)` or equivalent filter to every assessment queryset in this view.

---

### 2. Full Queryset Materialized into Memory Before Slicing

**Severity:** CRITICAL
**File:** `patients/views.py` lines ~377–426
**Type:** Performance — Memory Exhaustion

**Description:**
Every assessment queryset in `patient_view()` is cast to a Python `list()` before any slicing or counting occurs:

```python
var_gma = list(GMAssessment.objects.filter(patient=selected_patient).order_by("-id"))
gm_assessments_count = len(var_gma)   # Counts full in-memory list
gm_assessments = var_gma[:5]           # Uses only 5 of potentially thousands
gm_last_assessment = var_gma[0] if var_gma else None
```

For a patient with years of assessment history, this loads every record into memory just to display five rows and a count. This pattern is repeated for 6 separate model types in a single view.

**Risk:** OOM kills on large datasets; severe dashboard load latency; effectively a self-inflicted DoS for busy patients.

**Fix:**
```python
gm_assessments_count = GMAssessment.objects.filter(patient=selected_patient).count()
gm_assessments = GMAssessment.objects.filter(patient=selected_patient).order_by("-id")[:5]
gm_last_assessment = GMAssessment.objects.filter(patient=selected_patient).order_by("-id").first()
```

---

### 3. Email and Token Endpoints Vulnerable to Enumeration

**Severity:** CRITICAL
**File:** `users/views.py` lines ~310, 352
**Type:** Security — User Enumeration

**Description:**
Email verification and password-reset flows perform direct `.get()` lookups on user-supplied values with no rate limiting beyond the global session rate:

```python
user = CustomUser.objects.get(email_verification_token=token)  # line ~310
user = CustomUser.objects.get(email=email)                      # line ~352
```

Neither endpoint applies `@ratelimit`. An attacker can enumerate valid email addresses by comparing response times and error messages, or brute-force short/predictable tokens.

**Risk:** Account enumeration, token brute-force, targeted phishing of confirmed accounts.

**Fix:** Apply `@ratelimit(key='ip', rate='5/m')` to both endpoints. Use constant-time comparison for tokens. Ensure error messages are identical for found vs. not-found cases.

---

### 4. Bookmark Institution Scope Inconsistent with Patient Institution Scope

**Severity:** MAJOR
**File:** `patients/views.py` line ~1319
**Type:** Security — Data Isolation

**Description:**
Bookmarks are scoped by the owner's institution:

```python
Bookmark.objects.filter(**institution_scope(request, 'owner__institution'))
```

But patients are scoped by the patient's institution. If Institution A's user bookmarks a patient that was later transferred to or originally owned by Institution B, the bookmark filter (`owner__institution = A`) will still return the bookmark — giving Institution A a handle on Institution B's patient record.

**Risk:** Cross-institutional patient access via stale bookmarks.

**Fix:** Add a secondary filter asserting the bookmarked patient also belongs to the active institution: `filter(patient__institution=request.institution)`.

---

### 5. Video Retrieval Relies on Implicit Upstream Queryset for Institution Isolation

**Severity:** MAJOR
**File:** `patients/views.py` line ~884
**Type:** Security — Data Isolation

**Description:**
```python
video_file = get_object_or_404(Video.objects.filter(patient__in=_pts_qs), pk=fid)
```

Institution isolation depends entirely on `_pts_qs` being correctly scoped before this line. There is no explicit institution assertion on the Video retrieval itself. If `_pts_qs` is ever refactored, reordered, or reused in a different context, this silently becomes unscoped.

**Risk:** Cross-institutional video access.

**Fix:** Add an explicit institution assertion: `Video.objects.filter(patient__in=_pts_qs, patient__institution=request.institution)`.

---

### 6. Institution `is_active` Not Re-Checked Per Request in Middleware

**Severity:** MAJOR
**File:** `institution/middleware.py` lines ~66–76
**Type:** Security — Session Staleness

**Description:**
The middleware resolves the superadmin's active institution from the session and checks `is_active=True` only at session-key resolution time:

```python
request.institution = Institution.objects.get(pk=active_id, is_active=True)
```

If an institution is deactivated between requests, the superadmin's in-flight session continues operating against it until the next full session resolution. No per-request liveness check exists.

**Risk:** Superadmin continues reading/writing deactivated institution data after it should be locked out.

**Fix:** Re-query `is_active` on every request (or cache with a very short TTL). Redirect immediately if the institution is now inactive.

---

### 7. Bare `except Exception` Swallows All Error Types

**Severity:** MAJOR
**File:** `patients/views.py` (multiple locations — bookmark, search, assessment views)
**Type:** Reliability — Silent Failure / Audit Gap

**Description:**
Numerous view functions catch all exceptions with `except Exception as e` and render a generic error message:

```python
except Exception as e:
    messages.error(request, f"Error loading bookmark records: {str(e)}")
    return render(request, "bookmark/manager.html", {...})
```

`ValidationError`, `IntegrityError`, `PermissionDenied`, and unknown runtime errors all produce identical user-facing output and are logged the same way. Security violations blend into the noise; DB corruption errors do not halt execution.

**Risk:** Silent data corruption, undetected permission bypasses, incomplete audit trail.

**Fix:** Handle specific exception types explicitly. Re-raise `PermissionDenied` and unexpected exceptions after logging. Never continue rendering after an `IntegrityError`.

---

### 8. Raw `.objects.get()` Instead of `get_object_or_404()` in User Views

**Severity:** MAJOR
**File:** `users/views.py` lines ~42, 287, 310, 352, 881, 900
**Type:** Exception Handling — Inconsistent 404/500 Behaviour

**Description:**
Multiple locations call `.objects.get()` directly, bypassing the Django convention of returning a proper 404:

```python
developer = DeveloperContacts.objects.get(id=1)   # Hardcoded PK — breaks silently if deleted
user = CustomUser.objects.get(email_verification_token=token)
user = CustomUser.objects.get(email=email)
```

`DeveloperContacts.objects.get(id=1)` is particularly fragile — a hardcoded primary key that will raise `DoesNotExist` and produce a 500 error if the record is ever deleted or if the ID shifts.

**Risk:** Unhandled 500 errors surfacing to users; hardcoded PK is a maintenance landmine.

**Fix:** Replace with `get_object_or_404()`. Remove the hardcoded `id=1` lookup — query by a stable unique field or a settings-defined constant.

---

### 9. `MultipleObjectsReturned` Unhandled in Patient Search

**Severity:** MAJOR
**File:** `patients/views.py` lines ~724, 741, 758
**Type:** Exception Handling — Unhandled Exception Path

**Description:**
BHT, PIN, and NNC patient searches call `.get()` on user-supplied text:

```python
patient = Patient.objects.for_institution(...).get(bht=search_text)
patient = Patient.objects.for_institution(...).get(pin=search_text)
patient = Patient.objects.for_institution(...).get(nnc_no=search_text)
```

The `try/except` blocks catch `Patient.DoesNotExist`, but `Patient.MultipleObjectsReturned` is not explicitly handled. If duplicate identifiers exist in the database (data integrity lapse, migration error), this raises an unhandled exception producing a 500 error in production.

**Risk:** Unhandled 500 in production if duplicate identifiers exist; exposes internal exception messages.

**Fix:** Catch `Patient.MultipleObjectsReturned` explicitly and return a meaningful user-facing message. Alternatively, use `.filter().first()` with a `None` check.

---

### 10. N+1 Query Pattern in `get_userStats()` Dashboard Function

**Severity:** MAJOR
**File:** `ndas/custom_codes/custom_methods.py` lines ~50–87
**Type:** Performance — N+1 Queries

**Description:**
`get_userStats()` iterates over a user queryset and issues individual COUNT queries per user inside the loop:

```python
for user in _users_qs:
    user_stats[user.username] = {
        'patients': Patient.objects.filter(added_by=user).count(),
        'assessments': ...,
        ...
    }
```

With 50 users, this generates 50+ COUNT queries per dashboard load. With multiple institutions and hundreds of users, this scales to thousands of queries per page request.

**Risk:** Dashboard becomes unusable at scale; DB connection pool exhaustion under concurrent load.

**Fix:** Replace the loop with a single aggregation query using `values('added_by').annotate(Count(...))` and build the stats dict from the result set.

---

### 11. Assessment Deletion Race Condition on Institution Boundary

**Severity:** MAJOR
**File:** `patients/views.py` lines ~1113–1213
**Type:** Concurrency — Race Condition

**Description:**
The delete view fetches the assessment with institution scope, then retrieves the patient from the assessment without re-validating institution membership:

```python
assessment = get_object_or_404(GMAssessment, id=pk, **institution_scope(request))
patient = assessment.patient  # Institution NOT re-validated here
# ... permission checks ...
assessment.delete()
```

If institution assignment on the patient changes between the `get_object_or_404` call and the `delete()` call (concurrent request, admin action), a deletion crosses institution boundaries.

**Risk:** Cross-institutional data deletion under concurrent access.

**Fix:** Use `select_for_update()` within a transaction, or re-assert `patient.institution == request.institution` before delete.

---

### 12. Signal Side-Effects Escape `transaction.atomic()` Block

**Severity:** MAJOR
**File:** `patients/views.py` lines ~914–918
**Type:** Data Consistency — Partial State

**Description:**
Assessment creation wraps `.save()` and `.set()` in a transaction:

```python
with transaction.atomic():
    assessment.save()
    assessment.diagnosis.set(diagnosis_list)
```

If a post-save signal (e.g. cache invalidation, audit log write, notification trigger) fires inside `.save()`, those side-effects execute before the M2M `.set()` completes. If `.set()` then fails and the transaction rolls back, the signals have already fired with incomplete data and cannot be rolled back.

**Risk:** External systems (cache, audit logs, notifications) receive a state that is then rolled back — phantom records and stale caches.

**Fix:** Move signal-triggering logic to `transaction.on_commit()` hooks so they only fire after the full transaction succeeds.

---

### 13. `institution_scope()` Field-Path Argument is an ORM Injection Vector

**Severity:** MAJOR
**File:** `patients/views.py` line ~1319; `ndas/custom_codes/` scope utility
**Type:** Security — ORM Injection (Latent)

**Description:**
`institution_scope()` accepts a field-path string and constructs a filter kwargs dict via `**{field_path: value}`:

```python
Bookmark.objects.filter(**institution_scope(request, 'owner__institution'))
```

All current call sites pass hardcoded strings, so the risk is currently latent. However, the function signature does not validate or whitelist the field-path. If any future code path passes user-controlled input to this argument (e.g. a view that accepts a `field` query parameter), it becomes a Django ORM traversal injection — allowing arbitrary `__` relationship lookups.

**Risk:** Latent ORM injection; one future misuse creates a full filter bypass.

**Fix:** Whitelist the accepted field-path values inside `institution_scope()`. Raise `ValueError` on unrecognised paths.

---

## Summary

| # | File | Lines | Issue | Severity |
|---|------|-------|-------|----------|
| 1 | `patients/views.py` | ~377–426 | Assessment querysets unscoped by institution | CRITICAL |
| 2 | `patients/views.py` | ~377–426 | Full queryset `list()` materialization before slicing | CRITICAL |
| 3 | `users/views.py` | ~310, 352 | Email/token enumeration, no rate limiting | CRITICAL |
| 4 | `patients/views.py` | ~1319 | Bookmark vs. patient institution scope mismatch | MAJOR |
| 5 | `patients/views.py` | ~884 | Video scope relies on implicit upstream queryset | MAJOR |
| 6 | `institution/middleware.py` | ~66–76 | No per-request institution `is_active` re-check | MAJOR |
| 7 | `patients/views.py` | multiple | Bare `except Exception` swallows all error types | MAJOR |
| 8 | `users/views.py` | ~42, 287, 310, 352, 881, 900 | Raw `.objects.get()` without 404 handling | MAJOR |
| 9 | `patients/views.py` | ~724, 741, 758 | `MultipleObjectsReturned` unhandled in search | MAJOR |
| 10 | `custom_codes/custom_methods.py` | ~50–87 | N+1 queries in `get_userStats()` | MAJOR |
| 11 | `patients/views.py` | ~1113–1213 | Deletion race condition on institution boundary | MAJOR |
| 12 | `patients/views.py` | ~914–918 | Signal side-effects escape `transaction.atomic()` | MAJOR |
| 13 | `patients/views.py` | ~1319 | `institution_scope()` ORM injection via field-path | MAJOR |

---

## Recommended Priority Order

1. **Fix #1 and #3 immediately** — data breach and account enumeration are production-critical in a medical system.
2. **Fix #2** — memory exhaustion is a stability blocker under real load.
3. **Fix #4, #5, #6** — remaining institution isolation gaps.
4. **Fix #7, #8, #9** — exception handling cleanup to restore audit trail integrity.
5. **Fix #10** — performance fix before scaling to multiple institutions.
6. **Fix #11, #12, #13** — concurrency and injection hardening.
