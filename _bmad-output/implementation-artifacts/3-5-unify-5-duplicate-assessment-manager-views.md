# Story 3.5: Unify 5 Duplicate Assessment Manager Views

Status: done

## Story

As a developer maintaining the NDAS codebase,
I want the 5 filter variants of the GMA assessment manager consolidated into a single parameterised view,
so that search/pagination/query logic is maintained in one place and future changes only need to be made once.

## Acceptance Criteria

1. A single `assessment_manager(request, filter_type='all')` view in `patients/views.py` replaces all 6 existing functions (`assessment_manager`, `assessment_manager_recent`, `assessment_manager_normal`, `assessment_manager_abnormal`, `assessment_manager_informed`, `assessment_manager_not_informed`).
2. The unified view builds one base queryset with `.select_related('patient', 'added_by', 'last_edit_by', 'video_file')`, applies the correct filter per `filter_type`, then applies search/pagination identically to all branches.
3. All 6 URL names are preserved unchanged (`assessment-manager`, `assessment-manager-recent`, `assessment-manager-normal`, `assessment-manager-abnormal`, `assessment-manager-informed`, `assessment-manager-not-informed`) using Django URL kwargs (`{'filter_type': 'recent'}` etc.) in `patients/urls.py`.
4. The `"type"` context key retains its existing uppercase values (`None`, `"RECENT"`, `"NORMAL"`, `"ABNORMAL"`, `"INFORMED"`, `"NOT_INFORMED"`).
5. `templates/assessment/manager.html` is **not modified** — all existing `{% if type == 'RECENT' %}` active-state checks continue to work.
6. `patients/views.py` — the 5 removed functions leave no orphaned references (no imports, no URL wiring pointing to deleted names).
7. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Write unified `assessment_manager` view (AC: #1, #2, #4)
  - [x] Replaced `assessment_manager` body with unified `assessment_manager(request, filter_type='all')`. AC #1, #2, #4 satisfied.
- [x] Task 2: Delete the 5 filter variant view functions (AC: #1, #6)
  - [x] Deleted `assessment_manager_recent`, `_normal`, `_abnormal`, `_informed`, `_not_informed` in a single edit. AC #1 and #6 satisfied.
- [x] Task 3: Update `patients/urls.py` to use URL kwargs (AC: #3)
  - [x] Lines 60–64: replaced 5 view references with `views.assessment_manager` + `{'filter_type': '...'}` kwargs. All 6 URL names preserved. AC #3 satisfied.
- [x] Task 4: Verify (AC: #5, #6, #7)
  - [x] `templates/assessment/manager.html` — no changes made. AC #5 satisfied.
  - [x] No remaining references to deleted function names in `patients/` directory. AC #6 satisfied.
  - [x] System check clean. 6 regression tests pass. AC #7 satisfied.

## Dev Notes

### Current State — `patients/views.py:1195–1390`

Six functions with near-identical bodies — only the queryset filter and `"type"` context value differ:

| Function | Lines | Filter | `"type"` value |
|---|---|---|---|
| `assessment_manager` | 1195–1224 | none (all) | *(key absent)* |
| `assessment_manager_recent` | 1227–1258 | `created_at__gte=thirty_days_ago` | `"RECENT"` |
| `assessment_manager_normal` | 1261–1291 | `diagnosis_conclusion='NORMAL'` | `"NORMAL"` |
| `assessment_manager_abnormal` | 1294–1324 | `diagnosis_conclusion='ABNORMAL'` | `"ABNORMAL"` |
| `assessment_manager_informed` | 1327–1357 | `parent_informed=True` | `"INFORMED"` |
| `assessment_manager_not_informed` | 1360–1390 | `parent_informed=False` | `"NOT_INFORMED"` |

Every function duplicates:
- `select_related('patient', 'added_by', 'last_edit_by', 'video_file')`
- The 4-field Q-search filter block
- `.order_by("-id")`
- `Paginator(assessment_list, 10)` + `get_page(request.GET.get("page"))`
- `render(request, "assessment/manager.html", context)`

### Required State After Fix — Unified `assessment_manager`

Replace the entire block from `assessment_manager` through `assessment_manager_not_informed` (lines 1195–1390) with:

```python
@login_required(login_url="user-login")
@require_GET
def assessment_manager(request, filter_type='all'):
    search_query = request.GET.get('search', '').strip()

    base_qs = GMAssessment.objects.select_related(
        'patient', 'added_by', 'last_edit_by', 'video_file'
    )

    if filter_type == 'recent':
        assessment_list = base_qs.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        )
        view_type = 'RECENT'
    elif filter_type == 'normal':
        assessment_list = base_qs.filter(diagnosis_conclusion='NORMAL')
        view_type = 'NORMAL'
    elif filter_type == 'abnormal':
        assessment_list = base_qs.filter(diagnosis_conclusion='ABNORMAL')
        view_type = 'ABNORMAL'
    elif filter_type == 'informed':
        assessment_list = base_qs.filter(parent_informed=True)
        view_type = 'INFORMED'
    elif filter_type == 'not_informed':
        assessment_list = base_qs.filter(parent_informed=False)
        view_type = 'NOT_INFORMED'
    else:
        assessment_list = base_qs.all()
        view_type = None

    if search_query:
        assessment_list = assessment_list.filter(
            Q(patient__baby_name__icontains=search_query) |
            Q(patient__mother_name__icontains=search_query) |
            Q(patient__bht__icontains=search_query) |
            Q(patient__nnc_no__icontains=search_query)
        )

    assessment_list = assessment_list.order_by("-id")
    paginator = Paginator(assessment_list, 10)
    paginated_assmnt_list = paginator.get_page(request.GET.get("page"))

    context = {
        "assessment_page_obj": paginated_assmnt_list,
        "type": view_type,
        "search_query": search_query,
    }

    return render(request, "assessment/manager.html", context)
```

**Notes:**
- `@require_GET` added (all 6 originals were GET-only, just not decorated — this is a hardening improvement consistent with CLAUDE.md View Pattern).
- `timezone` is already imported at `patients/views.py:3` (`from django.utils import timezone`).
- `timedelta` is already imported at `patients/views.py:2` (`from datetime import timedelta, date`).
- `Q`, `Paginator`, `GMAssessment`, `login_required`, `require_GET` are all already imported in `patients/views.py`.
- The base `assessment_manager` URL uses the default `filter_type='all'` parameter — no URL kwargs needed for the root URL.

### Required State After Fix — `patients/urls.py:59–64`

**Before (6 separate views):**
```python
path("manager/assessment/", views.assessment_manager, name='assessment-manager'),
path("manager/assessment/recent/", views.assessment_manager_recent, name='assessment-manager-recent'),
path("manager/assessment/normal/", views.assessment_manager_normal, name='assessment-manager-normal'),
path("manager/assessment/abnormal/", views.assessment_manager_abnormal, name='assessment-manager-abnormal'),
path("manager/assessment/informed/", views.assessment_manager_informed, name='assessment-manager-informed'),
path("manager/assessment/not-informed/", views.assessment_manager_not_informed, name='assessment-manager-not-informed'),
```

**After (unified view + URL kwargs):**
```python
path("manager/assessment/", views.assessment_manager, name='assessment-manager'),
path("manager/assessment/recent/", views.assessment_manager, {'filter_type': 'recent'}, name='assessment-manager-recent'),
path("manager/assessment/normal/", views.assessment_manager, {'filter_type': 'normal'}, name='assessment-manager-normal'),
path("manager/assessment/abnormal/", views.assessment_manager, {'filter_type': 'abnormal'}, name='assessment-manager-abnormal'),
path("manager/assessment/informed/", views.assessment_manager, {'filter_type': 'informed'}, name='assessment-manager-informed'),
path("manager/assessment/not-informed/", views.assessment_manager, {'filter_type': 'not_informed'}, name='assessment-manager-not-informed'),
```

All 6 URL names are preserved. Templates using `{% url 'assessment-manager-recent' %}` etc. continue to work unchanged.

### Why No Template Changes Are Needed

The base `assessment_manager` function never set `"type"` in its context. The unified view sets `view_type = None` for the `filter_type='all'` case and puts `"type": view_type` in the context. Django templates treat a missing key and a `None` value identically in boolean context — `{% if not type %}` evaluates to `True` for both `None` and an absent key.

The template at `templates/assessment/manager.html` uses:
```django
{% if not type %}          {# active state for "All" nav link #}
{% if type == 'RECENT' %} {# active state for "Recent" nav link #}
{% if type == 'NORMAL' %} {# etc. #}
```

Since `None == 'RECENT'` is `False`, and `not None` is `True`, the template logic is fully compatible with the unified view's `view_type = None` for the all-records case.

### `require_GET` Already Imported

```python
# patients/views.py (existing)
from django.views.decorators.http import require_GET, require_http_methods
```

No new imports needed anywhere.

### `assessment_manager_by_patients` Is NOT Part of This Story

`assessment_manager_by_patients` (URL: `assessment-manager-patient`) is a separate view that filters by patient PK. It is out of scope and untouched by this story. Story 3.6 addresses `select_related` on that view separately.

### No Migration Required

Changes only to `patients/views.py` (rewrite + delete) and `patients/urls.py` (URL kwargs). No models, templates, or migrations.

### Project Structure Notes

- `patients/views.py` — replace lines 1195–1224 (unified function), delete lines ~1225–1390 (5 variants + blank lines)
- `patients/urls.py` — update lines 60–64 (5 filter URLs) to use URL kwargs
- `templates/assessment/manager.html` — **no changes**
- `patients/models.py` — **no changes**

### References

- [Source: _bmad-output/planning-artifacts/epic-3-performance.md#Story-3.5]
- [Source: docs/code-audit-adversarial-review.md#PERF-05]
- [Source: patients/views.py:1195–1390 — 6 duplicate assessment manager functions]
- [Source: patients/urls.py:59–64 — 6 assessment manager URL patterns]
- [Source: templates/assessment/manager.html — type context variable active-state checks]
- [Source: CLAUDE.md#View Pattern]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1 & 2 complete: Replaced the 6 near-identical functions (lines 1195–1391) with a single unified `assessment_manager(request, filter_type='all')` view. `@require_GET` retained. AC #1, #2, #4, #6 satisfied.
- Task 3 complete: `patients/urls.py` lines 60–64 updated to use `{'filter_type': '...'}` URL kwargs pointing at `views.assessment_manager`. All 6 URL names preserved unchanged. AC #3 satisfied.
- Task 4 complete: Template unchanged, no stale references to deleted names, system check clean, 6 regression tests pass. AC #5–7 satisfied.

### File List

patients/views.py
patients/urls.py

## Change Log

- 2026-02-20: Implemented Story 3.5 — unified 6 near-identical GMA assessment manager views into a single `assessment_manager(request, filter_type='all')` function in `patients/views.py`. Updated `patients/urls.py` to use URL kwargs (`{'filter_type': 'recent'}` etc.) so all 6 URL names remain intact. Removed ~150 lines of duplicated code.
