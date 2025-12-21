# Spec: Database Query Optimization

## REMOVED Requirements

### Requirement: Dashboard loads all patient and video records into memory

**Rationale**: Current implementation loads ALL patients and videos using `Patient.objects.all()` and `Video.objects.all()`, then filters in Python. This causes N+1 queries and slow performance with large datasets.

**Current Anti-Pattern** (patients/views.py:80-150):
```python
var_patients = getPatientList(PtStatus.ALL)  # Loads all patients
var_new_Patients = var_patients.filter(videos__isnull=True).distinct()
Patients_new_list_10 = var_new_Patients[:5]  # Slices in Python, not SQL
```

This requirement is being **REMOVED** and replaced with database-level filtering.

## ADDED Requirements

### Requirement: Dashboard must use count queries instead of loading full querysets

Dashboard statistics MUST use database `COUNT` queries instead of loading full querysets and counting in Python with `len()`.

#### Scenario: Patient count uses database COUNT query

**Given** the dashboard view needs total patient count
**When** calculating `patients_total_count`
**Then** the query uses `Patient.objects.count()`
**And** does NOT load patient objects into memory
**And** generates a single `SELECT COUNT(*) FROM patients` query

#### Scenario: Discharged patient count uses filtered COUNT

**Given** the dashboard needs discharged patient count
**When** calculating `patients_discharged_count`
**Then** the query uses `Patient.objects.filter(do_discharge__isnull=False).count()`
**And** does NOT load patient objects
**And** generates `SELECT COUNT(*) FROM patients WHERE do_discharge IS NOT NULL`

#### Scenario: Video count uses database COUNT query

**Given** the dashboard needs total video count
**When** calculating `videos_total_count`
**Then** the query uses `Video.objects.count()`
**And** generates a single COUNT query without loading video objects

### Requirement: Dashboard must optimize queries with select_related and prefetch_related

Dashboard MUST use `select_related()` for ForeignKey relationships and `prefetch_related()` for ManyToMany relationships to eliminate N+1 queries.

#### Scenario: New patient list uses select_related for user fields

**Given** the dashboard displays list of 5 newest patients
**When** loading `Patients_new_list_10`
**Then** the query includes `.select_related('added_by', 'last_edit_by')`
**And** user information is fetched in a single JOIN query
**And** template access to `patient.added_by.username` does NOT trigger additional queries

Example:
```python
Patients_new_list_10 = Patient.objects.annotate(
    video_count=Count('videos')
).filter(
    video_count=0
).select_related(
    'added_by', 'last_edit_by'
)[:5]
```

#### Scenario: Video list uses select_related for patient relationship

**Given** the dashboard displays list of new videos
**When** loading videos
**Then** the query includes `.select_related('patient', 'added_by')`
**And** patient and user data loaded in single query
**And** template access to `video.patient.baby_name` does NOT trigger N+1 queries

### Requirement: Dashboard must use database-level filtering and limiting

Dashboard MUST use database-level `LIMIT` clauses instead of Python slicing to restrict result sets.

#### Scenario: New patient list limits results in database

**Given** the dashboard only displays 5 newest patients
**When** building the queryset
**Then** the query includes `[:5]` AFTER all filters
**And** generates `SELECT ... LIMIT 5` in SQL
**And** does NOT load more than 5 records into memory

#### Scenario: Patient filtering uses database WHERE clause

**Given** filtering for patients without videos
**When** building the query
**Then** use `.annotate(video_count=Count('videos')).filter(video_count=0)`
**And** filtering happens in database with `HAVING` clause
**And** does NOT load all patients and filter in Python

### Requirement: Dashboard must use annotations for aggregations

Dashboard MUST use database-level annotations for counting related objects instead of loading relationships and counting in Python.

#### Scenario: Patient video count uses annotation

**Given** filtering patients by video count
**When** building the queryset
**Then** use `.annotate(video_count=Count('videos'))`
**And** count is calculated in database query
**And** does NOT require loading video objects

#### Scenario: New videos identified with EXISTS subquery

**Given** identifying videos without GM assessments
**When** building the query
**Then** use `Exists()` subquery: `GMAssessment.objects.filter(video_file_id=OuterRef('pk'))`
**And** videos are filtered at database level
**And** does NOT load all assessments to check

Example:
```python
from django.db.models import Exists, OuterRef

new_videos_subquery = GMAssessment.objects.filter(video_file_id=OuterRef('pk'))
new_videos = Video.objects.annotate(
    has_assessment=Exists(new_videos_subquery)
).filter(
    has_assessment=False
).select_related('patient', 'added_by')[:5]
```

### Requirement: Dashboard query count must be reduced by at least 60%

After optimization, the dashboard MUST generate no more than 15 database queries (down from ~50 baseline).

#### Scenario: Baseline dashboard generates ~50 queries

**Given** the dashboard before optimization
**When** loading the dashboard page
**Then** django-debug-toolbar shows ~50 queries
**And** includes N+1 queries for patient.added_by, video.patient
**And** includes inefficient len(queryset) patterns

#### Scenario: Optimized dashboard generates ~15 queries

**Given** the dashboard after optimization
**When** loading the dashboard page with 100+ patients
**Then** django-debug-toolbar shows ≤15 queries
**And** no N+1 query patterns detected
**And** query count reduction is ≥60%

#### Scenario: Dashboard loads in under 1 second with 1000+ patients

**Given** a database with 1000+ patient records
**When** loading the dashboard page
**Then** the response time is <1 second
**And** measured using `python scripts/benchmark_dashboard.py`

## MODIFIED Requirements

None - this entirely replaces the inefficient query patterns.

## Cross-References

- **Related to**: `patient-manager-refactor` - Same optimization techniques applied
- **Depends on**: Django ORM capabilities (select_related, prefetch_related, annotations)
- **Validated by**: Performance benchmarking in Phase 5
- **Tools**: django-debug-toolbar, django-silk for monitoring

## Implementation Notes

**Optimization Techniques:**

1. **Count vs Load:**
```python
# BEFORE (loads all objects)
count = len(Patient.objects.all())

# AFTER (database COUNT)
count = Patient.objects.count()
```

2. **select_related (ForeignKey):**
```python
# BEFORE (N+1 queries)
patients = Patient.objects.all()[:5]
for p in patients:
    print(p.added_by.username)  # Separate query per patient

# AFTER (single JOIN)
patients = Patient.objects.select_related('added_by', 'last_edit_by')[:5]
```

3. **Annotations:**
```python
# BEFORE (loads all videos to count)
patients = Patient.objects.all()
for p in patients:
    video_count = p.videos.count()  # Separate query

# AFTER (database aggregation)
patients = Patient.objects.annotate(video_count=Count('videos'))
```

4. **only() for field limitation:**
```python
# BEFORE (loads all fields)
patients = Patient.objects.all()[:5]

# AFTER (loads specific fields only)
patients = Patient.objects.only(
    'id', 'baby_name', 'bht',
    'patient__baby_name', 'added_by__username'
)[:5]
```

5. **Exists() for filtering:**
```python
# BEFORE (JOIN and count)
videos = Video.objects.filter(gmassessment__isnull=True)

# AFTER (EXISTS subquery)
new_videos_subquery = GMAssessment.objects.filter(video_file_id=OuterRef('pk'))
videos = Video.objects.annotate(
    has_assessment=Exists(new_videos_subquery)
).filter(has_assessment=False)
```

**Files to Modify:**
- `patients/views.py` lines 80-150 - dashboard() function complete rewrite
- `patients/views.py` lines 154-410 - All patient_manager_* views

**Expected Performance Impact:**
- Query count: 50 → 15 (70% reduction)
- Response time with 100 patients: 2-3s → <500ms
- Response time with 1000+ patients: 5-10s → <1s
- Memory usage: Significantly reduced (no full table loads)

**Testing Strategy:**
1. Create benchmark script: `python scripts/benchmark_dashboard.py`
2. Measure BEFORE optimization (baseline)
3. Apply optimizations incrementally
4. Measure AFTER each optimization
5. Use django-debug-toolbar to visualize query count
6. Use django-silk for detailed query profiling

**Validation Metrics:**
```python
# scripts/benchmark_dashboard.py output format
Dashboard Performance:
  Response time: 0.458 seconds (was 2.341s) - 80% improvement
  Database queries: 14 (was 52) - 73% reduction
  Avg query time: 0.033 seconds

Top 5 slowest queries:
  1. 0.045s - SELECT COUNT(*) FROM patients
  2. 0.038s - SELECT * FROM patients ... LIMIT 5
  ...
```

**Rollback Strategy:**
- Keep original dashboard() function in git history
- If performance regression: `git revert <commit>`
- If subtle bugs in filtering: Restore original logic, re-apply optimizations carefully
