# Epic 3: Performance Optimization

**Priority:** High — fix this sprint
**Source:** Code Audit Adversarial Review (2026-02-20)
**Scope:** `ndas/custom_codes/custom_methods.py`, `patients/views.py`, `patients/models.py`

Eliminate N+1 queries, unbounded querysets, and redundant database round-trips.

---

## Story 3.1: Rewrite `get_userStats()` with Count Annotations

**Audit Finding:** PERF-01
**File:** `ndas/custom_codes/custom_methods.py:41–73`
**Severity:** Critical

### Description

`get_userStats()` loads ALL records of every model type into Python memory, then filters per-user with N queries per user. With 10 users this produces ~89 queries per dashboard load; with 50 users, ~409 queries. Fix: use a single `values('added_by').annotate(count=Count('id'))` query per model type and build the stats dict from the results.

### Acceptance Criteria

- [ ] `get_userStats()` rewritten to use `values('added_by').annotate(count=Count('id'))` for each model
- [ ] Total DB queries for `get_userStats()` is O(number of model types), not O(users × model types)
- [ ] Dashboard user statistics table displays the same counts as before
- [ ] No `Model.objects.all()` calls remain inside `get_userStats()`
- [ ] `Count` imported from `django.db.models` at the top of the file
- [ ] Tested with Django debug toolbar or query logging to confirm query count reduction

---

## Story 3.2: Fix Unbounded Bookmark Queryset in Dashboard

**Audit Finding:** PERF-02
**File:** `patients/views.py:128`
**Severity:** Critical

### Description

`bookmark = Bookmark.objects.all()` loads every bookmark in the system into memory on every dashboard request. Should be filtered to the current user with a reasonable limit.

### Acceptance Criteria

- [ ] `Bookmark.objects.all()` replaced with `Bookmark.objects.filter(owner=request.user).select_related('patient')[:20]` (or appropriate limit matching the template's display)
- [ ] Dashboard bookmark display still works correctly
- [ ] No full-table bookmark scan on dashboard load
- [ ] If the dashboard displays a bookmark count separately, a `.count()` query is used for that

---

## Story 3.3: Fix Timezone-Naive Date in Admissions Bar Chart

**Audit Finding:** PERF-03
**File:** `ndas/custom_codes/custom_methods.py:78`
**Severity:** Medium

### Description

`datetime.now().date()` is timezone-naive. With `USE_TZ = True` and `TIME_ZONE = 'Asia/Kolkata'`, this can produce incorrect date boundaries (e.g., wrong day at midnight). Fix: use `timezone.now().date()`.

### Acceptance Criteria

- [ ] `datetime.now().date()` replaced with `timezone.now().date()`
- [ ] `from django.utils import timezone` import present (add if missing)
- [ ] `from datetime import datetime` import removed if `datetime.now()` was its only usage
- [ ] Admissions bar chart continues to display correct data

---

## Story 3.4: Eliminate N+1 Query Properties in Patient Model

**Audit Finding:** PERF-04
**File:** `patients/models.py`
**Severity:** Critical

### Description

`@property` methods (`isDischarged`, `isScreeningPositive`, `isBookmarked`, and others) execute DB queries on every access. In a list of 50 patients with 5 such properties, this is 250+ extra queries per page load.

The fix requires two parts:
1. Add manager/queryset methods with `annotate()` for each property
2. Update list views to use `annotate()` instead of accessing the property

### Acceptance Criteria

- [ ] Each property that executes a DB query (`isDischarged`, `isScreeningPositive`, `isBookmarked`, and any others identified) has a corresponding `annotate()` method on the model manager
- [ ] List views (`patient_manager`, `assessment_manager`) use annotated querysets instead of per-object property access
- [ ] Template references updated to use the annotated field names
- [ ] `@property` methods retained for backwards compatibility with single-object views (they still work, just not called in list contexts)
- [ ] Patient list page loads with the same correct data as before

---

## Story 3.5: Unify 5 Duplicate Assessment Manager Views

**Audit Finding:** PERF-05
**File:** `patients/views.py:1239–1402`
**Severity:** Medium

### Description

Five views (`assessment_manager_recent`, `assessment_manager_normal`, `assessment_manager_abnormal`, `assessment_manager_informed`, `assessment_manager_not_informed`) repeat identical logic with only a queryset filter difference. Should be unified into `assessment_manager(filter_type='all')` following the same pattern used for `patient_manager`.

### Acceptance Criteria

- [ ] A single `assessment_manager` view accepts a `filter_type` URL parameter
- [ ] Supported `filter_type` values: `all`, `recent`, `normal`, `abnormal`, `informed`, `not_informed`
- [ ] The 5 individual views either removed or reduced to thin wrappers that redirect to the unified view
- [ ] All existing URL names continue to resolve to the correct filtered views
- [ ] Pagination, search, and `select_related` work correctly for all filter types
- [ ] Templates updated to use the single unified template (or remain separate if template structure differs significantly)

---

## Story 3.6: Add `select_related` to `assessment_manager_by_patients`

**Audit Finding:** PERF-06
**File:** `patients/views.py:1412`
**Severity:** Medium

### Description

`assessment_manager_by_patients` fetches `GMAssessment.objects.filter(patient=patient)` without `.select_related()`. Every other assessment manager view uses `select_related`. In a list of 10 assessments, this causes 30–40 extra queries from template field access.

### Acceptance Criteria

- [ ] `.select_related('patient', 'added_by', 'last_edit_by', 'video_file')` added to the queryset in `assessment_manager_by_patients`
- [ ] Query count for this view reduced to the base query + no per-row relation queries
- [ ] View and template continue to render correctly

---

## Story 3.7: Fix User List Loading on Validation Failure in `search_results`

**Audit Finding:** PERF-07
**File:** `patients/views.py:688–703`
**Severity:** Low–Medium

### Description

`search_results` loads `CustomUser.objects.all()` on every validation error path (5 separate times in the function). The user list should be loaded once before the validation checks and reused across all error paths.

### Acceptance Criteria

- [ ] `CustomUser.objects.all()` called once at the start of the view function
- [ ] All 5 validation error return paths reuse the same user list
- [ ] `.select_related('groups')` added to avoid template-triggered relation queries
- [ ] Search functionality unchanged

---

## Story 3.8: Remove Unnecessary Full Querysets from Delete Modal Context

**Audit Finding:** PERF-08
**File:** `patients/views.py:451–474`
**Severity:** Low

### Description

The patient view passes 7 full querysets (`var_file_video`, `var_file_attachments`, `var_gma`, `var_hine`, `var_da`, `var_cdic`, `var_gpa`) to the template context for delete modal rendering. Delete modals only need counts (already in context) and the patient name — not full querysets.

### Acceptance Criteria

- [ ] Identify which context variables are actually used in the delete confirmation modal template
- [ ] Remove any full queryset context variables that are only used to provide counts (replace with `.count()` if needed separately, or confirm counts are already in context)
- [ ] Patient detail page (view, edit, delete modal) renders correctly with no missing data
- [ ] Template access to removed context variables confirmed to not exist in templates
