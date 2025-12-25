# Patient Management - Bug Fixes and Performance Optimization

## MODIFIED Requirements

### Requirement: Model Save Operations
All Patient-related models MUST properly persist data to the database by calling `super().save()` in overridden save methods.

#### Scenario: DevelopmentalAssessment save completes successfully
- **WHEN** a DevelopmentalAssessment instance is saved
- **THEN** the `is_dx_normal` field is updated from `is_normal`
- **AND** `super().save(*args, **kwargs)` is called to persist to database
- **AND** the record is retrievable from the database

#### Scenario: Model changes persist after save
- **WHEN** any model with custom save logic is saved
- **THEN** all field updates are written to the database
- **AND** the instance can be retrieved with updated values

### Requirement: Model String Representation
Model `__str__()` methods MUST return accurate, human-readable representations for display in admin and forms.

#### Scenario: DiagnosisList displays with abbreviation
- **WHEN** a DiagnosisList instance is converted to string
- **THEN** the format is "Title (Abbreviation)"
- **AND** NOT "Title (Title)"

#### Scenario: Admin interface shows correct diagnosis labels
- **WHEN** viewing DiagnosisList in Django admin
- **THEN** each entry displays title with abbreviation in parentheses

### Requirement: URL Pattern Standards
All URL patterns MUST follow Django conventions with trailing slashes to prevent unnecessary redirects.

#### Scenario: URL accessed with trailing slash
- **WHEN** a user requests a URL with trailing slash (e.g., `/manager/patient/new/`)
- **THEN** the view responds directly with 200 status
- **AND** no 301 redirect occurs

#### Scenario: POST data preserved on form submission
- **WHEN** a form is submitted via POST to a URL
- **THEN** POST data is not lost due to redirect
- **AND** form processing completes successfully

### Requirement: Object Retrieval Error Handling
Views MUST use `get_object_or_404()` for object retrieval to provide proper HTTP 404 responses for missing resources.

#### Scenario: Missing patient returns 404
- **WHEN** a view requests a Patient with non-existent ID
- **THEN** HTTP 404 response is returned
- **AND** NOT HTTP 500 Internal Server Error

#### Scenario: User sees appropriate error page
- **WHEN** accessing a deleted or non-existent patient
- **THEN** user sees "Not Found" page
- **AND** error is logged appropriately

### Requirement: Query Performance Optimization
Patient views MUST use `select_related()` and `prefetch_related()` to minimize database queries.

#### Scenario: Patient detail view loads efficiently
- **WHEN** displaying patient detail page
- **THEN** all related objects (videos, attachments, assessments) are fetched with JOINs
- **AND** number of queries is less than 10 regardless of related object count

#### Scenario: Patient list displays with user tracking
- **WHEN** displaying patient manager list
- **THEN** `added_by` and `last_edit_by` user data is fetched with single query
- **AND** no N+1 query pattern occurs

### Requirement: Error Message Display
Form validation errors MUST be displayed with appropriate message level (error, not success).

#### Scenario: Form validation fails
- **WHEN** form submission contains validation errors
- **THEN** errors are displayed with `messages.error()` level
- **AND** NOT with `messages.success()` level
- **AND** user sees red/error-styled message

#### Scenario: User distinguishes between success and error
- **WHEN** viewing flash messages
- **THEN** errors appear in error style (red)
- **AND** success messages appear in success style (green)

## ADDED Requirements

### Requirement: Database Indexes for Search Fields
Patient-related models MUST have database indexes on searchable and filterable fields for query performance.

#### Scenario: Diagnosis search performs efficiently
- **WHEN** searching DiagnosisList by title
- **THEN** database uses index for WHERE clause
- **AND** query completes in less than 100ms for 1000+ records

#### Scenario: Indication filtering is optimized
- **WHEN** filtering IndicationsForGMA by level
- **THEN** database uses index for filter operation
- **AND** no full table scan occurs

### Requirement: Unique Constraints on Identifiers
Lookup fields that serve as identifiers MUST have unique constraints to prevent duplicates.

#### Scenario: Duplicate diagnosis abbreviation rejected
- **WHEN** attempting to create DiagnosisList with existing abbreviation
- **THEN** database raises IntegrityError
- **AND** user sees validation error message

#### Scenario: Data integrity maintained
- **WHEN** querying by diagnosis abbreviation
- **THEN** exactly one result is returned
- **AND** no ambiguity exists

### Requirement: Field Type Appropriateness
Text fields MUST use appropriate field types (CharField vs TextField) based on expected length and usage.

#### Scenario: DiagnosisList title uses CharField
- **WHEN** DiagnosisList model is defined
- **THEN** title field is CharField with max_length=255
- **AND** database creates indexed VARCHAR column
- **AND** NOT TEXT column without constraint

#### Scenario: Long descriptions use TextField
- **WHEN** model has potentially long text content
- **THEN** TextField is used for unlimited length
- **AND** CharField is used for bounded text

### Requirement: Patient Property Performance
Patient model properties that query the database MUST be optimized to avoid N+1 patterns when used in templates or lists.

#### Scenario: New patient status determined efficiently
- **WHEN** checking if patient is new (has no videos)
- **THEN** use database annotation with Exists() subquery
- **AND** NOT property that triggers separate query per patient

#### Scenario: Patient list loads without query explosion
- **WHEN** displaying 50 patients with status indicators
- **THEN** total queries remain under 20
- **AND** status fields are pre-computed via annotations

### Requirement: Birth Weight Validation
Patient birth weight MUST be validated against comprehensive gestational age ranges for data accuracy.

#### Scenario: Extreme preterm weight validated
- **WHEN** entering birth weight for 24-week gestation
- **THEN** weight between 400-1200g is accepted
- **AND** weight < 250g or > 1350g raises validation error

#### Scenario: Term baby weight validated
- **WHEN** entering birth weight for 38-week gestation
- **THEN** weight between 2000-5000g is accepted
- **AND** unusually high/low weights are flagged

## REMOVED Requirements

### Requirement: IndicationsForGMA Property Method
**Reason:** Property `getIndicationList` returns all database records instead of instance data - architectural error
**Migration:** Remove property entirely or convert to class method if listing all indications is needed

#### Scenario: Code using getIndicationList fails gracefully
- **WHEN** existing code attempts to use removed property
- **THEN** AttributeError is raised with clear message
- **OR** class method `get_all_indications()` is available if needed

## Technical Notes

### Database Migrations Required

**Migration 1: Add Indexes**
```python
# patients/migrations/0XXX_add_indexes.py
operations = [
    migrations.AlterField(
        model_name='indicationsforgma',
        name='title',
        field=models.CharField(max_length=75, db_index=True),
    ),
    migrations.AlterField(
        model_name='indicationsforgma',
        name='level',
        field=models.CharField(max_length=6, db_index=True),
    ),
    migrations.AlterField(
        model_name='diagnosislist',
        name='abr',
        field=models.CharField(max_length=6, unique=True, db_index=True),
    ),
]
```

**Migration 2: TextField to CharField**
```python
# Check max length first to ensure no data truncation
operations = [
    migrations.AlterField(
        model_name='diagnosislist',
        name='title',
        field=models.CharField(max_length=255, db_index=True),
    ),
]
```

### Performance Targets

- **Patient detail view:** < 10 database queries
- **Patient list (50 items):** < 15 database queries
- **Search by diagnosis:** < 100ms query time
- **Form validation:** < 50ms for all checks

### Affected Files

- `patients/models.py` - Save methods, field types, indexes, properties
- `patients/views.py` - get_object_or_404, select_related, message levels
- `patients/urls.py` - Trailing slashes, namespaces
- `patients/forms.py` - Validation enhancements
- `patients/templates/` - Remove property calls, use annotated fields
