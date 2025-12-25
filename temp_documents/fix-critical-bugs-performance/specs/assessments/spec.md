# Assessment Management - Performance Optimization

## MODIFIED Requirements

### Requirement: Assessment Manager Query Optimization
Assessment manager views MUST use `select_related()` to eagerly load related objects and prevent N+1 query patterns.

#### Scenario: GM Assessment list loads efficiently
- **WHEN** displaying GM Assessment manager page with 50 assessments
- **THEN** all patient, user, and video data is fetched with JOINs
- **AND** total queries is less than 10
- **AND** NOT 50+ queries (one per assessment)

#### Scenario: Assessment with user tracking displays fast
- **WHEN** rendering assessment list showing "Added by" and "Last edited by"
- **THEN** user data is pre-fetched via select_related
- **AND** no additional query per assessment occurs

#### Scenario: Video file metadata available without extra queries
- **WHEN** displaying GM Assessment with video reference
- **THEN** video file data is included in initial query
- **AND** video filename and metadata display without additional database hits

### Requirement: Assessment Filtering Performance
Assessment manager filter views MUST optimize queries for different filter criteria (recent, normal, abnormal, informed status).

#### Scenario: Recent assessments filtered efficiently
- **WHEN** filtering assessments by recent date range
- **THEN** single query with WHERE clause and JOINs executes
- **AND** no N+1 pattern for related objects

#### Scenario: Normal vs abnormal filtering
- **WHEN** filtering assessments by diagnosis status
- **THEN** database index on status field is used
- **AND** query completes in less than 100ms for 1000+ records

### Requirement: Assessment Statistics Aggregation
Assessment statistics (normal, moderate, significant counts) MUST be computed with single database query using aggregation.

#### Scenario: HINE score statistics computed efficiently
- **WHEN** calculating counts of normal (≥60), moderate (40-59), and significant (<40) scores
- **THEN** single query with COUNT(CASE) aggregation is used
- **AND** NOT three separate .filter().count() queries

#### Scenario: Dashboard shows assessment counts fast
- **WHEN** displaying assessment statistics on dashboard
- **THEN** all counts are computed in one database round-trip
- **AND** page load time is under 500ms

### Requirement: Assessment Detail View Optimization
Individual assessment detail views MUST prefetch all related data to minimize queries.

#### Scenario: Assessment view shows complete data
- **WHEN** viewing single assessment detail page
- **THEN** patient, user, diagnosis, and indication data is prefetched
- **AND** total queries is less than 8

#### Scenario: Patient assessments listed on patient page
- **WHEN** patient detail page shows all assessments
- **THEN** assessments are fetched with select_related
- **AND** no additional queries for assessment user tracking

## ADDED Requirements

### Requirement: Assessment Count Optimization
Assessment-related count queries MUST use database aggregation instead of loading objects into memory.

#### Scenario: Bookmark assessment counts
- **WHEN** displaying count of bookmarked assessments
- **THEN** .count() query is used
- **AND** NOT .all() followed by len()

#### Scenario: Patient assessment summary
- **WHEN** showing count of GM, HINE, DA, CDIC assessments for patient
- **THEN** single query with multiple COUNT() aggregations is used
- **AND** objects are not loaded into memory for counting

### Requirement: Assessment Template Query Elimination
Assessment templates MUST receive pre-computed data from views rather than executing queries in templates.

#### Scenario: Age calculations done in view
- **WHEN** assessment template needs to display patient age
- **THEN** age is calculated in view and passed as context
- **AND** template does not call patient.getCurrentAge property

#### Scenario: Diagnosis lists prefetched
- **WHEN** template displays assessment diagnosis list
- **THEN** diagnoses are prefetched with assessments
- **AND** template iteration does not trigger database queries

## Technical Notes

### Query Optimization Patterns

**Assessment Manager Views:**
```python
# Before (N+1 queries)
assessment_list = GMAssessment.objects.filter(patient=patient).order_by("-id")

# After (optimized)
assessment_list = GMAssessment.objects.filter(patient=patient).select_related(
    'patient', 'added_by', 'last_edit_by', 'video_file'
).order_by("-id")
```

**Statistics Aggregation:**
```python
# Before (3 queries)
normal = var_hine_list.filter(score__gte=60).count()
moderate = var_hine_list.filter(score__gte=40, score__lt=60).count()
significant = var_hine_list.filter(score__lt=40).count()

# After (1 query)
from django.db.models import Count, Case, When, IntegerField, Q

stats = var_hine_list.aggregate(
    normal=Count(Case(When(score__gte=60, then=1), output_field=IntegerField())),
    moderate=Count(Case(When(Q(score__gte=40) & Q(score__lt=60), then=1), output_field=IntegerField())),
    significant=Count(Case(When(score__lt=40, then=1), output_field=IntegerField())),
)
```

### Affected Views

**patients/views.py:**
- `assessment_manager()` - line 1211
- `assessment_manager_recent()` - line 1239
- `assessment_manager_normal()` - line 1270
- `assessment_manager_abnormal()` - line 1301
- `assessment_manager_informed()` - line 1332
- `assessment_manager_not_informed()` - line 1363
- `patient_view()` - lines 390-412 (6 queries)
- `hine_assessment_manager()` - lines 2855-2857
- `hine_assessment_manager_by_patients()` - lines 2932-2934
- `da_assessment_manager()` - lines 3242-3243
- `da_assessment_manager_by_patients()` - lines 3348-3349
- `cdic` managers - lines 2451, 2548
- `bookmark_manager()` - lines 1490-1491

### Performance Targets

- **Assessment list (50 items):** < 10 queries
- **Assessment detail:** < 8 queries
- **Statistics computation:** 1 query for all counts
- **Patient page with assessments:** < 15 queries total
