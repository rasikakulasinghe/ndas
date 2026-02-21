# Story 3.6: Add `select_related` to `assessment_manager_by_patients`

Status: done

## Story

As a clinician viewing a patient's GMA assessment history,
I want the per-patient assessment list to load without per-row database round-trips,
so that the view performs as efficiently as all other assessment manager views.

## Acceptance Criteria

1. `.select_related('patient', 'added_by', 'last_edit_by', 'video_file')` added to the `GMAssessment` queryset in `assessment_manager_by_patients` (`patients/views.py:1400`).
2. No other changes to the view logic, context, template, or URL.
3. The per-patient assessment list renders correctly with all fields displayed.
4. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Add `select_related` to the queryset (AC: #1)
  - [x] `patients/views.py:1253` — changed `GMAssessment.objects.filter(patient=patient)` → `GMAssessment.objects.select_related('patient', 'added_by', 'last_edit_by', 'video_file').filter(patient=patient)`. AC #1 satisfied.
- [x] Task 2: Verify (AC: #2, #3, #4)
  - [x] No other changes made to the view or template. AC #2 satisfied.
  - [x] System check clean. 6 regression tests pass. AC #3 and #4 satisfied.

## Dev Notes

### Current State — `patients/views.py:1393–1420`

```python
@login_required(login_url="user-login")
def assessment_manager_by_patients(request, pk):
    patient = get_object_or_404(Patient, id=pk)
    search_query = request.GET.get('search', '').strip()

    assessment_list = GMAssessment.objects.filter(patient=patient)  # ← missing select_related
    if search_query:
        assessment_list = assessment_list.filter(
            Q(patient__baby_name__icontains=search_query) |
            Q(patient__mother_name__icontains=search_query) |
            Q(patient__bht__icontains=search_query) |
            Q(patient__nnc_no__icontains=search_query)
        )

    assessment_list = assessment_list.order_by("-id")
    paginator = Paginator(assessment_list, 10)
    page_number = request.GET.get("page")
    paginated_assmnt_list = paginator.get_page(page_number)

    context = {
        "patient": patient,
        "assessment_page_obj": paginated_assmnt_list,
        "search_query": search_query,
    }

    return render(request, "assessment/manager.html", context)
```

### Required State After Fix — Changed Line Only

```python
    assessment_list = GMAssessment.objects.select_related(
        'patient', 'added_by', 'last_edit_by', 'video_file'
    ).filter(patient=patient)
```

Everything else in the function is unchanged.

### Why This Matters

The template `assessment/manager.html` accesses `assessment.patient`, `assessment.added_by`, `assessment.last_edit_by`, and `assessment.video_file` in the row loop. Without `select_related`, Django issues a separate SQL query for each of these 4 relations on every row. For a page of 10 assessments that is 40+ extra queries — the same N+1 pattern that every other assessment manager view already avoids by having `select_related`.

All 5 unified views (`assessment_manager` with each `filter_type`) already have:
```python
GMAssessment.objects.select_related('patient', 'added_by', 'last_edit_by', 'video_file')
```
This view was simply missed.

### No New Imports Required

`GMAssessment`, `get_object_or_404`, `Paginator`, `Q`, `login_required` are all already imported in `patients/views.py`.

### No Migration Required

Single queryset method addition. No models, templates, URLs, or migrations changed.

### Project Structure Notes

- File changed: `patients/views.py` — line 1400 only (the `GMAssessment.objects.filter(...)` line)
- No other files changed

### References

- [Source: _bmad-output/planning-artifacts/epic-3-performance.md#Story-3.6]
- [Source: docs/code-audit-adversarial-review.md#PERF-06]
- [Source: patients/views.py:1393–1420 — assessment_manager_by_patients function]
- [Source: patients/views.py:1195–1224 — assessment_manager (unified) uses select_related as reference]
- [Source: templates/assessment/manager.html — accesses patient, added_by, last_edit_by, video_file per row]
- [Source: CLAUDE.md#View Pattern — "use select_related()/prefetch_related() for related objects"]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1 complete: Added `.select_related('patient', 'added_by', 'last_edit_by', 'video_file')` to the queryset in `assessment_manager_by_patients` (`patients/views.py:1253`). AC #1 satisfied.
- Task 2 complete: No other changes. System check clean. 6 regression tests pass. AC #2–4 satisfied.

### File List

patients/views.py

## Change Log

- 2026-02-20: Implemented Story 3.6 — added `.select_related('patient', 'added_by', 'last_edit_by', 'video_file')` to the `GMAssessment` queryset in `assessment_manager_by_patients` in `patients/views.py`. Eliminates 40+ N+1 queries per page load for the per-patient assessment list.
