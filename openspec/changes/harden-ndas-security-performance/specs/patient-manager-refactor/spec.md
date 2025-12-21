# Spec: Patient Manager Code Deduplication

## REMOVED Requirements

### Requirement: Patient manager has separate view function for each filter type

**Rationale**: Current implementation has 8 nearly identical functions (~250 lines each) with only the queryset filter differing. This creates ~2000 lines of duplicated code that is unmaintainable.

**Current State** (patients/views.py:154-410):
```python
def patient_manager(request):  # All patients
    patients_list = Patient.objects.all().order_by("-id")
    # ... 250 lines of search, pagination, context building

def patient_manager_diagnosed_any(request):  # Diagnosed patients
    patients_list = getPatientList(PtStatus.DIAGNOSED).order_by("-id")
    # ... 250 lines of IDENTICAL search, pagination, context building

def patient_manager_diagnosis_normal(request):  # Normal diagnosis
    patients_list = getPatientList(PtStatus.DX_NORMAL).order_by("-id")
    # ... 250 lines of IDENTICAL code

# ... 5 more duplicate functions (dx_gma_normal, dx_gma_abnormal, dx_hine, dx_da_normal, dx_da_abnormal, discharged)
```

**Impact**: Any bug fix or feature requires updating 8 separate functions. This violates DRY principle.

This requirement is being **REMOVED** and replaced with unified view.

#### Scenario: Eight separate patient manager functions exist (REMOVED)

**Given** the file `patients/views.py`
**When** searching for patient manager view functions
**Then** 8 separate functions exist:
  - `patient_manager()`
  - `patient_manager_diagnosed_any()`
  - `patient_manager_diagnosis_normal()`
  - `patient_manager_diagnosed_gma_normal()`
  - `patient_manager_diagnosed_gma_abnormal()`
  - `patient_manager_diagnosed_hine()`
  - `patient_manager_da_normal()`
  - `patient_manager_da_abnormal()`
  - `patient_manager_discharged_only()`
**And** each contains ~250 lines of duplicated code

This scenario represents the problematic state being **REMOVED**.

## ADDED Requirements

### Requirement: Single unified patient manager view handles all filter types

Patient manager MUST use a single view function with a `filter_type` parameter to handle all filtering scenarios.

#### Scenario: Unified patient manager accepts filter type parameter

**Given** the unified patient_manager view
**When** called with URL parameter `filter_type='diagnosed'`
**Then** the view applies diagnosed patient filter
**And** uses the same search, pagination, and rendering logic
**And** displays "Diagnosed Patients" as page title

#### Scenario: Patient manager supports all legacy filter types

**Given** the unified patient manager
**When** any of these filter types are requested:
  - 'all' (all patients)
  - 'diagnosed' (any diagnosis)
  - 'dx_normal' (normal diagnosis)
  - 'dx_gma_normal' (GMA normal)
  - 'dx_gma_abnormal' (GMA abnormal)
  - 'dx_hine' (HINE diagnosed)
  - 'dx_da_normal' (DA normal)
  - 'dx_da_abnormal' (DA abnormal)
  - 'discharged' (discharged patients)
**Then** the appropriate filter is applied using FILTER_MAP dictionary
**And** the correct page title is displayed using FILTER_LABELS

Example:
```python
FILTER_MAP = {
    'all': Patient.objects.all(),
    'diagnosed': getPatientList(PtStatus.DIAGNOSED),
    'dx_normal': getPatientList(PtStatus.DX_NORMAL),
    # ... other filters
}

FILTER_LABELS = {
    'all': 'All Patients',
    'diagnosed': 'Diagnosed Patients',
    # ... other labels
}

patients_list = FILTER_MAP.get(filter_type, Patient.objects.all())
```

#### Scenario: Invalid filter type defaults to all patients

**Given** the unified patient manager
**When** called with an invalid filter_type like 'invalid_filter'
**Then** the view defaults to showing all patients
**And** uses FILTER_MAP.get(filter_type, Patient.objects.all())
**And** displays "All Patients" as page title

### Requirement: Unified patient manager must preserve all existing functionality

The refactored unified view MUST maintain feature parity with the 8 original views.

#### Scenario: Search functionality works across all filter types

**Given** the unified patient manager with filter_type='diagnosed'
**And** a search query parameter `?search=Baby`
**When** the view processes the request
**Then** the search is applied to baby_name, mother_name, bht, nnc_no fields
**And** results are filtered by both diagnosed status AND search query
**And** search works identically across all filter types

#### Scenario: Pagination works for all filter types

**Given** the unified patient manager with any filter type
**And** more than 10 patients match the filter
**When** loading page 2 with `?page=2`
**Then** the view displays patients 11-20
**And** pagination works identically across all filter types
**And** uses Paginator with 10 patients per page

#### Scenario: Query optimization applied to all filter types

**Given** the unified patient manager
**When** loading any filter type
**Then** the query includes `.select_related('added_by', 'last_edit_by')`
**And** eliminates N+1 queries for user relationships
**And** optimization is applied consistently across all filters

### Requirement: URL patterns must support both new unified URLs and legacy redirects

The URL configuration MUST provide new unified URL patterns while maintaining backward compatibility via redirects.

#### Scenario: New unified URL pattern for filtered manager

**Given** the URL configuration in `patients/urls.py`
**When** accessing `/manager/patient/`
**Then** the unified patient_manager view is called with filter_type='all'

**When** accessing `/manager/patient/diagnosed/`
**Then** the unified patient_manager view is called with filter_type='diagnosed'

Example URL patterns:
```python
path('manager/patient/', views.patient_manager, name='manager'),
path('manager/patient/<str:filter_type>/', views.patient_manager, name='manager-filtered'),
```

#### Scenario: Legacy URLs redirect to new unified URLs

**Given** old URL patterns exist for backward compatibility
**When** accessing `/manager/patient/diagnosed-any/` (old URL)
**Then** the request redirects to `/manager/patient/diagnosed/` (new URL)
**And** HTTP 301 Permanent Redirect is used
**And** deprecation notice logged

**Given** a 6-month deprecation period
**When** the deprecation period expires
**Then** old URL patterns can be safely removed
**And** redirects are well-documented for users

### Requirement: Template must adapt to filter type dynamically

The patient manager template MUST use filter_type and filter_label context variables to display appropriate content.

#### Scenario: Template displays filter-specific page title

**Given** the template `templates/patients/manager.html`
**And** context variable `filter_label='Diagnosed Patients'`
**When** the template renders
**Then** the page title displays "Diagnosed Patients"
**And** uses `<h1>{{ filter_label }}</h1>`

#### Scenario: Template navigation links use new URL patterns

**Given** the template has navigation links
**When** rendering filter navigation
**Then** links use `{% url 'patients:manager' %}` for "All Patients"
**And** links use `{% url 'patients:manager-filtered' 'diagnosed' %}` for filters
**And** active filter is highlighted based on filter_type

Example:
```django
<a href="{% url 'patients:manager' %}" class="{% if filter_type == 'all' %}active{% endif %}">
    All Patients
</a>
<a href="{% url 'patients:manager-filtered' 'diagnosed' %}" class="{% if filter_type == 'diagnosed' %}active{% endif %}">
    Diagnosed
</a>
```

## MODIFIED Requirements

None - this is a refactoring that replaces existing implementation.

## Cross-References

- **Related to**: `query-optimization` - Both improve patient manager performance
- **Depends on**: Patient model and PtStatus enum (existing code)
- **Impact**: URL patterns change (backward compatibility via redirects)
- **Validated by**: `patients/tests/test_views.py::PatientManagerTestCase`

## Implementation Notes

**Code Reduction:**
- Before: 8 functions × ~250 lines = ~2000 lines
- After: 1 function × ~50 lines = ~50 lines
- **Reduction**: 97.5% (1950 lines removed)

**Unified View Implementation** (patients/views.py):
```python
@login_required(login_url="user-login")
def patient_manager(request, filter_type='all'):
    """
    Unified patient manager with filtering and search.

    Args:
        request: HTTP request object
        filter_type: Filter to apply - 'all', 'diagnosed', 'dx_normal',
                     'dx_gma_normal', 'dx_gma_abnormal', 'dx_hine',
                     'dx_da_normal', 'dx_da_abnormal', 'discharged'

    Returns:
        Rendered patient manager page with paginated results
    """
    search_query = request.GET.get('search', '').strip()

    # Apply filter based on type
    FILTER_MAP = {
        'all': Patient.objects.all(),
        'diagnosed': getPatientList(PtStatus.DIAGNOSED),
        'dx_normal': getPatientList(PtStatus.DX_NORMAL),
        'dx_gma_normal': getPatientList(PtStatus.DX_GMA_NORMAL),
        'dx_gma_abnormal': getPatientList(PtStatus.DX_GMA_ABNORMAL),
        'dx_hine': getPatientList(PtStatus.DX_HINE),
        'dx_da_normal': getPatientList(PtStatus.DX_DA_NORMAL),
        'dx_da_abnormal': getPatientList(PtStatus.DX_DA_ABNORMAL),
        'discharged': getPatientList(PtStatus.DISCHARGED),
    }

    patients_list = FILTER_MAP.get(filter_type, Patient.objects.all())

    # Apply search filter
    if search_query:
        patients_list = patients_list.filter(
            Q(baby_name__icontains=search_query) |
            Q(mother_name__icontains=search_query) |
            Q(bht__icontains=search_query) |
            Q(nnc_no__icontains=search_query)
        )

    # Optimize query
    patients_list = patients_list.select_related(
        'added_by', 'last_edit_by'
    ).order_by("-id")

    # Paginate
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get("page")
    paginated_pt_list = paginator.get_page(page_number)

    # Build context
    FILTER_LABELS = {
        'all': 'All Patients',
        'diagnosed': 'Diagnosed Patients',
        'dx_normal': 'Normal Diagnosis',
        'dx_gma_normal': 'GMA Normal',
        'dx_gma_abnormal': 'GMA Abnormal',
        'dx_hine': 'HINE Diagnosed',
        'dx_da_normal': 'DA Normal',
        'dx_da_abnormal': 'DA Abnormal',
        'discharged': 'Discharged Patients',
    }

    context = {
        "patients_page_obj": paginated_pt_list,
        "filter_type": filter_type,
        "filter_label": FILTER_LABELS.get(filter_type, 'All Patients'),
        "search_query": search_query,
    }

    return render(request, "patients/manager.html", context)
```

**Migration Strategy:**
1. Create unified patient_manager() function (new code)
2. Add new URL patterns with redirects from old URLs
3. Test all filter types work correctly
4. Update template to use filter_label
5. Update navigation links to use new URLs
6. Monitor for 6 months (log deprecated URL usage)
7. Remove old patient_manager_* functions
8. Remove old URL patterns and redirects

**Testing Requirements:**
- Test all 9 filter types return correct patients
- Test search works with each filter type
- Test pagination works correctly
- Test query optimization eliminates N+1
- Test old URLs redirect to new URLs
- Test template renders correctly for each filter

**Rollback Strategy:**
- Keep old functions commented during initial rollout
- If issues found: Temporarily route old URLs back to old functions
- Fix bugs in unified view
- Re-enable unified view
- Complete removal only after stable for 1 month
