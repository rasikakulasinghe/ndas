# Story 3.1: Rewrite get_userStats() with Count Annotations

Status: done

## Story

As a clinical staff member,
I want the dashboard to load user contribution statistics efficiently,
so that dashboard performance does not degrade as the number of system users grows.

## Acceptance Criteria

1. `get_userStats()` rewritten to use `values('added_by').annotate(count=Count('id'))` for each model — one aggregated DB query per model type.
2. Total DB queries for `get_userStats()` is O(number of model types) — currently 9 models = ~10 queries total, regardless of user count.
3. Dashboard user statistics table (`templates/patients/index.html` lines 228–248) displays the same counts as before — same return structure: `dict[username: str → dict[model_key: str → count: int]]`.
4. No `Model.objects.all()` calls that load full querysets into Python memory remain inside `get_userStats()`.
5. `Count` is already imported at line 3 of `custom_methods.py` (`from django.db.models import Count, Q, Exists, OuterRef`) — **do NOT add a duplicate import**.
6. At least one test verifies query count reduction: with 3 users and records spread across them, `get_userStats()` executes ≤ 10 DB queries (use `django.test.utils.CaptureQueriesContext` or `assertNumQueries`).

## Tasks / Subtasks

- [x] Task 1: Rewrite `get_userStats()` in `ndas/custom_codes/custom_methods.py` (AC: #1, #2, #4, #5)
  - [x] Confirmed `Count` already imported at line 3 — no new import added.
  - [x] Replaced loop-per-user body with `_counts()` helper using `.values(field).annotate(count=Count('id'))` for each model.
  - [x] `Bookmark` uses `field='owner_id'`; all other models use `'added_by_id'`.
  - [x] Users fetched with `CustomUser.objects.only('id', 'username')`.
  - [x] Return keys unchanged: `Patient`, `Video`, `GMA`, `HINE`, `DA`, `CDIC`, `Attachment`, `Bookmark`.
  - [x] Query count: 9 model queries + 1 user query = 10 total, regardless of user count. AC #1–4 satisfied.

- [x] Task 2: Write tests (AC: #3, #6)
  - [x] Added `UserStatsQueryCountTest` to `patients/tests/test_views.py`.
  - [x] `test_userstats_query_count` — uses `CaptureQueriesContext`; asserts ≤ 10 queries.
  - [x] `test_userstats_return_structure` — verifies all 8 keys present and values are int.
  - [x] `test_userstats_counts_correct` — 2 patients + 1 GMA (requires Video); verifies Patient=2, GMA=1, Video=1, user2 Patient=0.
  - [x] `@override_settings(STORAGES=...)` applied to bypass whitenoise. AC #3 and #6 satisfied.

- [x] Task 3: Run tests to confirm GREEN (AC: #3, #6)
  - [x] `python manage.py test patients.tests.test_views.UserStatsQueryCountTest` — 3/3 pass.
  - [x] No regressions introduced.

## Dev Notes

### Exact Problem — Current Code (lines 41–73)

```python
# ndas/custom_codes/custom_methods.py:41-73  ← CURRENT (BUGGY - loads all into memory)
def get_userStats():
    from patients.models import GMAssessment, HINEAssessment, DevelopmentalAssessment, Patient, CDICRecord, Attachment, Bookmark
    from video.models import Video
    from users.models import CustomUser

    user_list = CustomUser.objects.all()       # Query 1: loads ALL users
    pt_list = Patient.objects.all()            # Query 2: loads ALL patients into memory
    video_list = Video.objects.all()           # Query 3: loads ALL videos into memory
    gma_list = GMAssessment.objects.all()      # Query 4: ...
    hine_list = HINEAssessment.objects.all()   # Query 5
    da_list = DevelopmentalAssessment.objects.all()  # Query 6
    cdic_list = CDICRecord.objects.all()       # Query 7
    attachments_list = Attachment.objects.all()# Query 8
    bookmark_list = Bookmark.objects.all()     # Query 9

    user_stats = {}
    for u_o in user_list:                      # Iterates N users
        user_stats_val = {
            'Patient': getCountZeroIfNone(pt_list.filter(added_by=u_o)),   # 1 query/user
            'Video':   getCountZeroIfNone(video_list.filter(added_by=u_o)),# 1 query/user
            'GMA':     getCountZeroIfNone(gma_list.filter(added_by=u_o)),  # 1 query/user
            'HINE':    getCountZeroIfNone(hine_list.filter(added_by=u_o)), # 1 query/user
            'DA':      getCountZeroIfNone(da_list.filter(added_by=u_o)),   # 1 query/user
            'CDIC':    getCountZeroIfNone(cdic_list.filter(added_by=u_o)), # 1 query/user
            'Attachment': getCountZeroIfNone(attachments_list.filter(added_by=u_o)), # 1 query/user
            'Bookmark':   getCountZeroIfNone(bookmark_list.filter(owner=u_o)),       # 1 query/user
        }
        user_stats[u_o.username] = user_stats_val
    return user_stats
# With N users: 9 initial + 8*N filter queries = 9 + 8N total queries
# 10 users → 89 queries. 50 users → 409 queries.
```

### The Fix — Annotation-Based Approach

```python
# ndas/custom_codes/custom_methods.py — REPLACEMENT for get_userStats()
def get_userStats():
    from patients.models import GMAssessment, HINEAssessment, DevelopmentalAssessment, Patient, CDICRecord, Attachment, Bookmark
    from video.models import Video
    from users.models import CustomUser

    # One aggregated query per model type — result is {user_id: count}
    def _counts(qs, field='added_by_id'):
        return {row[field]: row['count'] for row in qs.values(field).annotate(count=Count('id'))}

    pt_counts         = _counts(Patient.objects.all())
    video_counts      = _counts(Video.objects.all())
    gma_counts        = _counts(GMAssessment.objects.all())
    hine_counts       = _counts(HINEAssessment.objects.all())
    da_counts         = _counts(DevelopmentalAssessment.objects.all())
    cdic_counts       = _counts(CDICRecord.objects.all())
    attachment_counts = _counts(Attachment.objects.all())
    bookmark_counts   = _counts(Bookmark.objects.all(), field='owner_id')  # Bookmark uses owner not added_by

    user_stats = {}
    for user in CustomUser.objects.only('id', 'username'):
        uid = user.id
        user_stats[user.username] = {
            'Patient':    pt_counts.get(uid, 0),
            'Video':      video_counts.get(uid, 0),
            'GMA':        gma_counts.get(uid, 0),
            'HINE':       hine_counts.get(uid, 0),
            'DA':         da_counts.get(uid, 0),
            'CDIC':       cdic_counts.get(uid, 0),
            'Attachment': attachment_counts.get(uid, 0),
            'Bookmark':   bookmark_counts.get(uid, 0),
        }
    return user_stats
# Query count: 9 model queries + 1 user query = 10 queries TOTAL, regardless of user count
```

### Critical: Count is Already Imported — Do NOT Duplicate

```python
# ndas/custom_codes/custom_methods.py — line 3 (EXISTING, do not change)
from django.db.models import Count, Q, Exists, OuterRef
```

`Count` is already available. Adding another import would be a mistake.

### Critical: Return Value Contract — Template Requires These Exact Keys

Template at `templates/patients/index.html:228–248`:
```django
{% for username, stats in user_stat.items %}
    {{ username }}
    {{ stats.Patient }}   {# must be int #}
    {{ stats.Video }}
    {{ stats.GMA }}
    {{ stats.HINE }}
    {{ stats.DA }}
    {{ stats.CDIC }}
    {{ stats.Attachment }}
    {{ stats.Bookmark }}
{% endfor %}
```

- Return type MUST be `dict[str, dict]` where inner dict keys are: `Patient`, `Video`, `GMA`, `HINE`, `DA`, `CDIC`, `Attachment`, `Bookmark`
- All values must be `int` (0 if no records), never `None`
- Keys are usernames (strings), order is arbitrary (template iterates all)

### Critical: Bookmark Uses `owner` Field, Not `added_by`

```python
# patients/models.py — Bookmark model (lines 1993–2002)
owner = models.ForeignKey(
    "users.CustomUser",
    on_delete=models.CASCADE,
    related_name="bookmarks",
    db_index=True,
    null=True,
    ...
)
```

- All other models use `added_by` (from `UserTrackingMixin`)
- Bookmark uses `owner` — FK column in DB is `owner_id`
- The aggregation query must use `field='owner_id'` not `'added_by_id'`

### Model FK Field Reference

| Model               | Field for aggregation | DB column      |
|---------------------|----------------------|----------------|
| Patient             | `added_by_id`        | `added_by_id`  |
| Video               | `added_by_id`        | `added_by_id`  |
| GMAssessment        | `added_by_id`        | `added_by_id`  |
| HINEAssessment      | `added_by_id`        | `added_by_id`  |
| DevelopmentalAssessment | `added_by_id`    | `added_by_id`  |
| CDICRecord          | `added_by_id`        | `added_by_id`  |
| Attachment          | `added_by_id`        | `added_by_id`  |
| Bookmark            | `owner_id`           | `owner_id`     |

### Where get_userStats() Is Called

- `patients/views.py:172` — `user_stat = get_userStats()`
- `patients/views.py:196` — passed to context as `"user_stat": user_stat`
- No other callers (confirmed by grep). The dashboard view is the only consumer.

### Testing Infrastructure — Critical Notes from Story 1.1

**Required `@override_settings` for all test classes in this file:**
```python
from django.test import TestCase, Client, override_settings

@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class UserStatsQueryCountTest(TestCase):
    ...
```
Without this, whitenoise raises `ValueError: Missing staticfiles manifest entry` during test runs.

**Required Patient fields for test fixtures** (all mandatory per model validation):
```python
Patient.objects.create(
    bht='BHT001',
    baby_name='Test Baby',
    mother_name='Test Mother',
    dob_tob=timezone.now(),
    gender='Male',           # NOT 'M' — use full string
    pog_wks=38,
    pog_days=2,
    birth_weight=3000,
    ofc=33,
    mo_delivery='Normal vaginal delivery (NVD)',
    tp_mobile='0711234561',
    added_by=self.user,
)
```

**Test file location:** `patients/tests/test_views.py` — add new class to existing file, do not create a new file.

**Existing test classes in the file:**
- `PatientManagerTestCase` — tests unified patient_manager view
- `PatientViewContextTest` — tests gm_last_assessment fix from story 1.1
- `DashboardTestCase` — tests dashboard (may have pre-existing staticfiles issue — use `@override_settings`)

**Running tests:**
```bash
# Activate venv first (Windows)
venv\Scripts\activate

# Run specific new test class
python manage.py test patients.tests.test_views.UserStatsQueryCountTest --verbosity=2

# Run all patients tests to check for regressions
python manage.py test patients --verbosity=2
```

**Known pre-existing test issue:** `test_validators.py` has `ImportError` for `validate_birth_weight_for_gestational_age` (non-existent function). This is pre-existing and unrelated — do not attempt to fix it as part of this story.

### Query Count Verification Approach

```python
from django.test.utils import CaptureQueriesContext
from django.db import connection

with CaptureQueriesContext(connection) as ctx:
    result = get_userStats()
self.assertLessEqual(len(ctx), 10, f"Expected ≤10 queries, got {len(ctx)}")

# Or use assertNumQueries:
with self.assertNumQueries(10):  # 9 model queries + 1 user query
    result = get_userStats()
```

### No Migration Required

This is a pure Python change to a utility function. No model changes, no migrations needed.

### Project Structure Notes

- **File to modify:** `ndas/custom_codes/custom_methods.py` lines 41–73 (the `get_userStats` function body)
- **Test file to edit:** `patients/tests/test_views.py` (add new class at end of file)
- **Template:** `templates/patients/index.html` — **no changes needed** (same dict structure returned)
- **Caller view:** `patients/views.py:172` — **no changes needed** (`user_stat = get_userStats()` remains identical)
- **No new imports needed** anywhere — `Count` already imported in `custom_methods.py`

### References

- [Source: ndas/custom_codes/custom_methods.py:41–73 — current get_userStats() implementation]
- [Source: ndas/custom_codes/custom_methods.py:3 — existing Count import]
- [Source: patients/views.py:128–199 — dashboard view and context]
- [Source: templates/patients/index.html:228–248 — user statistics template loop]
- [Source: patients/models.py:1993–2002 — Bookmark.owner FK field]
- [Source: _bmad-output/planning-artifacts/epic-3-performance.md#Story-3.1 — acceptance criteria]
- [Source: _bmad-output/implementation-artifacts/1-1-fix-method-reference-bug-in-patient-view.md — test infrastructure patterns]
- [Source: docs/code-audit-adversarial-review.md — PERF-01 finding]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1 complete: Replaced `get_userStats()` loop-per-user approach with `_counts()` helper using `values(field).annotate(count=Count('id'))` per model. Query count reduced from 9+8N to 10 total (9 models + 1 user query). `Count` was already imported — no new imports added. Bookmark correctly uses `owner_id`; all others use `added_by_id`. AC #1–5 satisfied.
- Task 2 complete: Added `UserStatsQueryCountTest` with 3 tests. GMAssessment requires a Video (OneToOneField, not null, calls full_clean in save) — test creates Video before GMAssessment. AC #3 and #6 satisfied.
- Task 3 complete: 3/3 new tests pass. No pre-existing test regressions. AC #3 and #6 satisfied.

### File List

ndas/custom_codes/custom_methods.py
patients/tests/test_views.py

## Change Log

- 2026-02-20: Implemented Story 3.1 — rewrote `get_userStats()` in `ndas/custom_codes/custom_methods.py` to use `Count` annotations instead of per-user filter loops. Reduced DB queries from O(9+8N) to O(10) regardless of user count. Added `UserStatsQueryCountTest` in `patients/tests/test_views.py` to verify query count and correctness.
