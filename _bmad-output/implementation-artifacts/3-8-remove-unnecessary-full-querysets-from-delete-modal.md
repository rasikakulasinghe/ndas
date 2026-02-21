# Story 3.8: Eliminate Redundant COUNT Queries in Patient View

Status: done

## Story

As a clinician viewing a patient detail page,
I want the page to fetch each related record type only once from the database,
so that the 7 separate COUNT(*) queries and 7 LIMIT-5 display queries are eliminated when the same full data is already fetched for delete modal rendering.

## Acceptance Criteria

1. Each of the 7 related-record querysets in `patient_view` (`patients/views.py:386–419`) is evaluated to a Python list exactly once, replacing 3 queries (COUNT + LIMIT-5 + full fetch) per type with 1 query (full fetch).
2. Counts are derived using `len()` on the already-fetched list — no separate `SELECT COUNT(*)` query.
3. Display slices (top-5) are derived using Python list slicing (`list[:5]`) — no separate `SELECT ... LIMIT 5` query.
4. Template context variables (`file_videos`, `file_video_count`, `var_file_video`, etc.) retain the same names — no template changes needed.
5. Patient detail page renders correctly — counts, display lists, and delete modals all work.
6. `python manage.py test patients` — no new failures.

## Tasks / Subtasks

- [x] Task 1: Evaluate the 7 querysets to lists and derive counts/slices in `patient_view` (AC: #1, #2, #3)
  - [x] Replaced all 7 queryset+count+slice patterns with `list()` evaluate + `len()` + list slicing. AC #1, #2, #3 satisfied.
- [x] Task 2: Verify template context keys are unchanged (AC: #4, #5)
  - [x] All 7 `var_*` context keys are now Python lists — Django `{% for %}` iterates lists identically.
  - [x] All count keys correct integers via `len()`.
  - [x] `gm_last_assessment = var_gma[0] if var_gma else None` — no extra query. AC #4 and #5 satisfied.
- [x] Task 3: Verify (AC: #6)
  - [x] 7 regression tests pass (including `PatientViewContextTest` which directly tests `gm_last_assessment`). AC #6 satisfied.

## Dev Notes

### Why the Audit Finding Needed Correction

The original audit finding (PERF-08) suggested "delete modals only need counts — remove full querysets". Investigation shows this is incorrect:

`templates/patients/partials/patient_view.html:884–910` iterates every record in each full queryset to generate one delete modal per record:

```django
{% for Assessment in var_gma %}
{% delete_modal Assessment %}
{% endfor %}
```

The delete modals require the full object (ID for delete URL, name for confirmation text). Removing the full querysets would break delete functionality for all assessments, videos, and attachments listed on the patient view.

**The real inefficiency is different:** the current code issues 3 separate SQL queries per record type (COUNT, LIMIT-5, full fetch) when only 1 is needed (full fetch, from which count and top-5 are derived in Python).

### Current State — `patients/views.py:386–419` (3 queries per type × 7 types = 21 queries)

```python
var_file_video = Video.objects.select_related(...).filter(patient=selected_patient).order_by("-id")
file_video_count = var_file_video.count()   # query 1: SELECT COUNT(*)
file_videos = var_file_video[:5]            # query 2 in template: SELECT ... LIMIT 5

var_file_attachments = Attachment.objects.select_related(...).filter(...).order_by("-id")
file_attachment_count = var_file_attachments.count()   # query 3: SELECT COUNT(*)
file_attachment = var_file_attachments[:5]             # query 4 in template: SELECT ... LIMIT 5

var_gma = GMAssessment.objects.select_related(...).filter(...).order_by("-id")
gm_assessments_count = var_gma.count()      # query 5: SELECT COUNT(*)
gm_assessments = var_gma[:5]               # query 6 in template: SELECT ... LIMIT 5
gm_last_assessment = var_gma.first()       # query 7: SELECT ... LIMIT 1

# ... same pattern for var_hine, var_da, var_cdic, var_gpa
```

Then in the template, `{% for video in var_file_video %}` issues query 8 (full fetch), and similarly for each of the other 6 `var_*` context variables.

**Total: ~21–22 extra queries** (7 COUNT + 7 LIMIT-5 display + 7 full fetch for delete modals + 1 `.first()` for last GMA).

### Required State After Fix — 1 query per type = 7 queries total

```python
# Video files — 1 query, derive count and display slice in Python
var_file_video = list(
    Video.objects.select_related('added_by', 'last_edit_by')
    .filter(patient=selected_patient).order_by("-id")
)
file_video_count = len(var_file_video)
file_videos = var_file_video[:5]

# Attachments — 1 query
var_file_attachments = list(
    Attachment.objects.select_related('added_by', 'last_edit_by')
    .filter(patient=selected_patient).order_by("-id")
)
file_attachment_count = len(var_file_attachments)
file_attachment = var_file_attachments[:5]

# GMA assessments — 1 query
var_gma = list(
    GMAssessment.objects.select_related('added_by', 'last_edit_by', 'video_file')
    .filter(patient=selected_patient).order_by("-id")
)
gm_assessments_count = len(var_gma)
gm_assessments = var_gma[:5]
gm_last_assessment = var_gma[0] if var_gma else None

# HINE assessments — 1 query
var_hine = list(
    HINEAssessment.objects.select_related('added_by', 'last_edit_by')
    .filter(patient=selected_patient).order_by("-id")
)
hine_assessments_count = len(var_hine)
hine_assessments = var_hine[:5]

# Developmental assessments — 1 query
var_da = list(
    DevelopmentalAssessment.objects.select_related('added_by', 'last_edit_by')
    .filter(patient=selected_patient).order_by("-id")
)
da_assessments_count = len(var_da)
da_assessments = var_da[:5]

# CDIC records — 1 query
var_cdic = list(
    CDICRecord.objects.select_related('added_by', 'last_edit_by')
    .filter(patient=selected_patient).order_by("-id")
)
cdic_record_count = len(var_cdic)
cdic_record = var_cdic[:5]

# GPA assessments — 1 query
var_gpa = list(
    GeneralPaediatricAssessment.objects.filter(patient=selected_patient)
    .select_related('discharged_authorized_by', 'added_by')
    .order_by("-assessment_date")
)
gpa_assessments_count = len(var_gpa)
gpa_assessments = var_gpa[:5]
```

**The context dict is unchanged** — all 7 `var_*` keys pass lists (which template `{% for %}` iterates identically to querysets), all count keys remain integers, and all top-5 display lists are Python list slices.

### `gm_last_assessment` Fix

Current: `gm_last_assessment = var_gma.first()` — issues one extra `SELECT ... LIMIT 1` query.
After: `gm_last_assessment = var_gma[0] if var_gma else None` — uses already-fetched list, zero queries.

### Memory Trade-off

For a patient with many records (e.g. 50 GMA assessments), fetching all 50 into a Python list uses more memory than the current approach (which lazily fetches 1+5+all = 3 passes). However:
- The current code already fetches all records for delete modals (the `{% for %}` loop in the template)
- So the same data was already being fetched — the fix consolidates into one fetch
- Peak memory is no worse; total query count drops from ~21 to ~7

### No Template Changes

All context variable names are preserved exactly. Django templates iterate Python lists with the same syntax as querysets. No template changes needed.

### No New Imports Required

All model classes (`Video`, `Attachment`, `GMAssessment`, `HINEAssessment`, `DevelopmentalAssessment`, `CDICRecord`, `GeneralPaediatricAssessment`) are already imported in `patients/views.py`.

### No Migration Required

View function refactor only. No models, templates, URLs, or migrations changed.

### Project Structure Notes

- File changed: `patients/views.py:386–419` — replace 7 queryset+count+slice patterns with list+len+slice patterns
- No other files changed

### References

- [Source: _bmad-output/planning-artifacts/epic-3-performance.md#Story-3.8]
- [Source: docs/code-audit-adversarial-review.md#PERF-08]
- [Source: patients/views.py:380–480 — patient_view function]
- [Source: templates/patients/partials/patient_view.html:884–910 — delete modal loops over full querysets]
- [Source: CLAUDE.md#View Pattern — "use select_related()/prefetch_related() for related objects"]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1 complete: Replaced 7 queryset+count+slice patterns (3 queries each = 21 total) with `list()` evaluation + `len()` + Python slicing (1 query each = 7 total). `gm_last_assessment` changed from `.first()` to `var_gma[0] if var_gma else None`. All context variable names unchanged. AC #1–3 satisfied.
- Task 2 & 3 complete: 7 regression tests pass including `PatientViewContextTest` which directly validates `gm_last_assessment`. AC #4–6 satisfied.

### File List

patients/views.py

## Change Log

- 2026-02-20: Implemented Story 3.8 — replaced 7 queryset+COUNT+LIMIT-5 patterns in `patient_view` with `list()` evaluate + `len()` + Python slicing in `patients/views.py`. Reduces per-request DB queries from ~21 to 7 for the patient detail page. All context variable names, template references, and delete modal functionality unchanged.
