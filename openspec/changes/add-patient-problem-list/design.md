# Design: Patient Problem List Management

## Context
The NDAS system currently tracks patient demographics, assessments (GPA, HINE, CDIC, Developmental), videos, and attachments, but lacks a structured way to document ongoing patient problems and clinical issues. Medical professionals need to:
- Document patient problems as they arise
- Track actions taken for each problem
- Monitor problem resolution status
- Review problem history at a glance

This feature must integrate seamlessly with existing patient management workflows while maintaining NDAS security and medical data standards.

## Goals / Non-Goals

**Goals:**
- Create dedicated app for patient problem tracking
- Enable CRUD operations for problem list entries
- Display recent problems in patient detail view
- Provide comprehensive problem history view
- Follow NDAS architectural patterns (TimeStampedModel, UserTrackingMixin)
- Maintain AdminLTE UI consistency
- Support user activity tracking and permissions
- Enable problem resolution status tracking

**Non-Goals:**
- Integration with external medical record systems (future consideration)
- Problem categorization/taxonomy (start simple with free-text)
- Automated problem recommendations or clinical decision support
- Multi-patient problem correlation or analytics
- Problem templates or standardized problem lists

## Decisions

### Decision 1: Separate Django App vs Extension of Patients App
**Choice**: Create separate `problemlist` Django app

**Rationale**:
- Follows NDAS pattern of app separation (patients, video, reports, users)
- Better code organization and maintainability
- Clear separation of concerns
- Easier to extend with future features (problem templates, categories)
- Aligns with Django best practices for feature modules

**Alternatives considered**:
- **Extend patients app**: Would work but violates single responsibility principle; patients app is already large
- **Add to reports app**: Doesn't fit - reports are for data export, not data entry

### Decision 2: Model Field Structure
**Choice**: Use comprehensive clinical fields with status/severity tracking and separate audit log

**Problem Model Fields**:
- `patient` (FK), `name` (short clinical name), `description` (detailed clinical description)
- `date_of_onset` (when problem started), `date_identified` (when documented)
- `status` (active/resolved/chronic/inactive) - replaces boolean `is_settled`
- `severity` (mild/moderate/severe/life_threatening)
- `action_taken` (summary of treatments/interventions), `outcome` (response to treatment)
- `date_resolved` (auto-populated when status='resolved', with manual override)
- `comments` (additional notes)

**ProblemAction Model** (separate audit log):
- `problem` (FK to Problem), `action` (TextField), `date` (DateTimeField)
- `performed_by` (FK to User) - tracks who performed each action

**Rationale**:
- **Status-based tracking**: Problems persist over time with dynamic status (core design principle)
- **Structured yet flexible**: Severity and status provide structure; text fields allow narrative detail
- **Separate action log**: Audit-level tracking of all interventions without cluttering main model
- **Clinical workflow alignment**: date_of_onset vs date_identified matches real-world documentation
- **Analytics-ready**: Status and severity fields enable filtering and reporting

**Alternatives considered**:
- **Boolean is_settled**: Too simplistic; doesn't capture chronic or inactive states
- **Combined action field**: Separate ProblemAction model provides better audit trail
- **Problem categories/taxonomy**: Deferred to future iteration (keep flexible for now)

### Decision 3: Display Strategy in Patient View
**Choice**: Show latest 5 problems with "View All" link to dedicated page; active problems first, resolved problems greyed out; add "Add Problem" button for quick access

**Rationale**:
- Matches user requirement exactly
- Keeps patient view uncluttered
- Provides quick access to recent problems
- **Add Problem button**: Direct link from patient view to add problem page (pre-filled with patient)
- **Active problems first**: Clinical priority on current issues
- **Visual differentiation**: Greyed-out resolved problems reduce visual noise
- Dedicated page allows for filtering/sorting/searching

**Alternatives considered**:
- **Accordion/collapsible section**: Could work but adds UI complexity
- **Modal popup**: Harder to work with for multiple problems
- **Inline table with pagination**: Clutters patient view
- **Hide resolved problems**: Too aggressive; clinicians want to see resolution history

### Decision 4: Problem Analysis Page with Advanced Filtering
**Choice**: Create dedicated analysis page with comprehensive filters (patient, status, severity, date range) and export functionality

**Rationale**:
- **Research and reporting needs**: Medical staff need to analyze problems across patients
- **Patient search**: Select2 autocomplete for efficient patient selection from large databases
- **Multi-criteria filtering**: Status, severity, and date range enable targeted queries
- **Export capability**: Excel/PDF export for reports and research
- **Performance**: Filtered queries with indexed fields ensure fast response times

**Alternatives considered**:
- **Manager page with filters**: Would work but lacks cross-patient analysis
- **Report generation only**: Analysis page allows interactive exploration before export
- **Simple dropdowns**: Select2 autocomplete better for large patient databases

## Database Impact

### New Model: Problem

```python
from django.db import models
from django.utils import timezone
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

PROBLEM_STATUS = [
    ('active', 'Active'),
    ('resolved', 'Resolved'),
    ('chronic', 'Chronic'),
    ('inactive', 'Inactive'),
]

SEVERITY_CHOICES = [
    ('mild', 'Mild'),
    ('moderate', 'Moderate'),
    ('severe', 'Severe'),
    ('life_threatening', 'Life Threatening'),
]

class Problem(TimeStampedModel, UserTrackingMixin):
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE, related_name='problems')
    name = models.CharField(max_length=255, help_text="Short clinical name (e.g., Bronchial Asthma)")
    description = models.TextField(blank=True, help_text="Detailed clinical description")
    date_of_onset = models.DateField(null=True, blank=True)
    date_identified = models.DateField(default=timezone.now, help_text="Date problem was first documented")
    status = models.CharField(max_length=20, choices=PROBLEM_STATUS, default='active')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, null=True, blank=True)
    date_resolved = models.DateField(null=True, blank=True)
    action_taken = models.TextField(blank=True, help_text="Treatment, investigations, referrals")
    outcome = models.TextField(blank=True, help_text="Response to treatment / current outcome")
    comments = models.TextField(blank=True)
```

**Inherited Fields** (via TimeStampedModel, UserTrackingMixin):
- `created_at` - Timestamp of record creation
- `updated_at` - Timestamp of last modification
- `added_by` - User who created the record
- `last_edit_by` - User who last modified the record

**Indexes**:
- `patient` - Foreign key index (automatic)
- `patient, status` - Composite index for filtering active/resolved problems per patient
- `date_identified` - For chronological queries (add `db_index=True`)

**Cascade Behavior**:
- When patient is deleted, all associated problems are deleted (CASCADE)

### New Model: ProblemAction (Audit Log)

```python
class ProblemAction(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='actions')
    action = models.TextField()
    date = models.DateTimeField(default=timezone.now)
    performed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-date']
```

**Purpose**: Separate audit-level tracking of all actions performed on a problem. Distinct from `action_taken` field (which is a summary). Each ProblemAction represents a timestamped intervention or note.

### Migration Strategy
- Single migration file in `problemlist/migrations/0001_initial.py`
- Automatic migration via `python manage.py makemigrations problemlist`
- No data migration needed (new feature, no existing data)
- Safe to apply: `python manage.py migrate`

## Security Considerations

### User Tracking
- Automatic user tracking via `UserActivityMiddleware`
- `added_by` field populated on creation
- `last_edit_by` field updated on modification
- No manual intervention required in views

### Permission Checks
- Delete operations use centralized `delete_helpers.py` functions:
  - `has_delete_permission(user, entity, entity_type)` - Superusers can delete all; staff can delete own records
  - `validate_can_delete(entity, entity_type)` - Business rule validation
  - `get_redirect_url(entity_type, entity)` - Post-deletion redirect

### CSRF Protection
- All forms include `{% csrf_token %}`
- Django's CsrfViewMiddleware enforces protection

### Access Control
- All views decorated with `@login_required(login_url="user-login")`
- Medical data visible only to authenticated users
- Session timeout: 1 hour (existing NDAS configuration)

### HIPAA Considerations
- Problem descriptions and actions may contain sensitive clinical information
- Follows existing NDAS security patterns
- User activity tracking provides audit trail
- No special encryption required (handled at infrastructure level)

## UI/UX Impact

### AdminLTE Components Used
- **Patient View Section**: Info box (info-box-primary) with problem list table
- **Manager Page**: Card component with DataTable
- **Add/Edit Forms**: Form controls with Bootstrap 4.6 styling
- **View Page**: Card with problem details

### Template Structure
```
problemlist/templates/problemlist/
├── manager.html                # All problems for patient (extends src/base.html)
├── add.html                    # Create new problem (extends src/base.html)
├── edit.html                   # Update problem (extends src/base.html)
├── view.html                   # Problem details (extends src/base.html)
├── timeline.html               # Expanded timeline view (extends src/base.html)
├── analysis.html               # Problem analysis with filters (extends src/base.html)
├── _problem_list_section.html  # Include for patient view (latest 5)
└── _problem_row.html           # HTMX swap target for status changes
```

### Analysis Page Template Structure

The analysis page (`analysis.html`) follows add patient page styling:

```django
{% extends 'src/base.html' %}
{% block title %}Problem Analysis | NDAS{% endblock %}

{% block extra_css %}
<link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet" />
<link href="https://cdn.jsdelivr.net/npm/select2-bootstrap4-theme@1.0.0/dist/select2-bootstrap4.min.css" rel="stylesheet" />
{% endblock %}

{% block main_content %}
<div class="container-fluid">
  <div class="row justify-content-center">
    <div class="col-12">
      <!-- Filter Card -->
      <div class="card card-primary card-outline">
        <div class="card-header">
          <h3 class="card-title"><i class="fas fa-filter"></i> Problem Analysis Filters</h3>
        </div>
        <div class="card-body">
          <form method="GET" action="{% url 'problem-analysis' %}">
            <div class="row">
              <!-- Patient Selection with Select2 -->
              <div class="col-md-6">
                <div class="form-group">
                  <label for="patient-select">Patient</label>
                  <select id="patient-select" name="patient" class="form-control select2">
                    <option value="">-- All Patients --</option>
                    {% for p in patients %}
                    <option value="{{p.pk}}" {% if filters.patient_id == p.pk|stringformat:"s" %}selected{% endif %}>
                      {{p.bht}} - {{p.baby_name}} ({{p.mother_name}})
                    </option>
                    {% endfor %}
                  </select>
                </div>
              </div>

              <!-- Status Filter (Multiple) -->
              <div class="col-md-3">
                <div class="form-group">
                  <label>Status</label>
                  <select name="status" multiple class="form-control select2" data-placeholder="All Statuses">
                    <option value="active" {% if 'active' in filters.status_filter %}selected{% endif %}>Active</option>
                    <option value="chronic" {% if 'chronic' in filters.status_filter %}selected{% endif %}>Chronic</option>
                    <option value="resolved" {% if 'resolved' in filters.status_filter %}selected{% endif %}>Resolved</option>
                    <option value="inactive" {% if 'inactive' in filters.status_filter %}selected{% endif %}>Inactive</option>
                  </select>
                </div>
              </div>

              <!-- Severity Filter (Multiple) -->
              <div class="col-md-3">
                <div class="form-group">
                  <label>Severity</label>
                  <select name="severity" multiple class="form-control select2" data-placeholder="All Severities">
                    <option value="mild" {% if 'mild' in filters.severity_filter %}selected{% endif %}>Mild</option>
                    <option value="moderate" {% if 'moderate' in filters.severity_filter %}selected{% endif %}>Moderate</option>
                    <option value="severe" {% if 'severe' in filters.severity_filter %}selected{% endif %}>Severe</option>
                    <option value="life_threatening" {% if 'life_threatening' in filters.severity_filter %}selected{% endif %}>Life Threatening</option>
                  </select>
                </div>
              </div>
            </div>

            <!-- Date Range -->
            <div class="row">
              <div class="col-md-3">
                <div class="form-group">
                  <label for="date_from">Date From</label>
                  <input type="date" name="date_from" id="date_from" class="form-control" value="{{filters.date_from}}">
                </div>
              </div>
              <div class="col-md-3">
                <div class="form-group">
                  <label for="date_to">Date To</label>
                  <input type="date" name="date_to" id="date_to" class="form-control" value="{{filters.date_to}}">
                </div>
              </div>
              <div class="col-md-6 align-self-end">
                <div class="form-group">
                  <button type="submit" class="btn btn-primary">
                    <i class="fas fa-search"></i> Apply Filters
                  </button>
                  <a href="{% url 'problem-analysis' %}" class="btn btn-default">
                    <i class="fas fa-redo"></i> Clear
                  </a>
                  <a href="{% url 'problem-analysis-export' %}?{{request.GET.urlencode}}" class="btn btn-success">
                    <i class="fas fa-file-excel"></i> Export to Excel
                  </a>
                </div>
              </div>
            </div>
          </form>
        </div>
      </div>

      <!-- Results Card -->
      <div class="card card-info card-outline">
        <div class="card-header">
          <h3 class="card-title"><i class="fas fa-list"></i> Analysis Results ({{count}} problems)</h3>
        </div>
        <div class="card-body">
          <div class="table-responsive">
            <table class="table table-hover">
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Problem</th>
                  <th>Status</th>
                  <th>Severity</th>
                  <th>Date Identified</th>
                  <th>Date Resolved</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {% for problem in problems %}
                <tr class="{% if problem.status in 'resolved,inactive' %}text-muted{% endif %}">
                  <td>{{problem.patient.bht}}<br><small>{{problem.patient.baby_name}}</small></td>
                  <td>{{problem.name}}</td>
                  <td><span class="badge badge-{{problem.status_badge_class}}">{{problem.get_status_display}}</span></td>
                  <td>{{problem.get_severity_display|default:"N/A"}}</td>
                  <td>{{problem.date_identified|date:"Y-m-d"}}</td>
                  <td>{{problem.date_resolved|date:"Y-m-d"|default:"--"}}</td>
                  <td>
                    <a href="{% url 'problem-view' problem.pk %}" class="btn btn-sm btn-info">
                      <i class="fas fa-eye"></i>
                    </a>
                  </td>
                </tr>
                {% empty %}
                <tr>
                  <td colspan="7" class="text-center text-muted">No problems found matching the filters.</td>
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
<script>
$(document).ready(function() {
    $('.select2').select2({
        theme: 'bootstrap4',
        width: '100%'
    });
});
</script>
{% endblock %}
```

### Responsive Design
- Tables use Bootstrap responsive classes: `table-responsive`
- Forms use `form-control` for consistent styling
- Mobile-friendly card layouts
- Tablet-optimized for medical settings

### JavaScript Libraries
- **DataTables** (if needed for manager page): Sorting, filtering, pagination
- **HTMX** (recommended): Dynamic inline status changes without full page reload
- **DatePicker**: Bootstrap DatePicker for date_of_onset, date_identified, and date range filters
- **Select2**: Advanced autocomplete for patient selection in analysis page

### UI Theme and Styling (Matching Add Patient Page)

**Card Colors and Icons** (from patients/add.html):
- **Medical Record Identifiers**: `card-primary card-outline` with `fa-id-card` icon
- **Personal Information**: `card-info card-outline` with `fa-user` icon
- **Problem Details**: `card-success card-outline` with `fa-notes-medical` icon
- **Clinical Data**: `card-warning card-outline` with `fa-stethoscope` icon
- **Optional/Additional**: `card-light card-outline` with collapse button

**Form Styling**:
- Input groups with append/prepend for units (e.g., `<span class="input-group-text">days</span>`)
- Required fields marked with `<span class="text-danger">*</span>`
- Help text with `<small class="form-text text-muted">`
- Error display with `<div class="text-danger small">`
- Callout components for conditional fields: `<div class="callout callout-warning">`

**Button Styling**:
- Primary action: `btn btn-success` with `fa-save` icon
- Secondary action: `btn btn-default` with `fa-arrow-left` icon
- Delete action: `btn btn-danger` with `fa-trash` icon
- Action buttons in `card-footer` with row/col layout

**Layout**:
- Two-column form layout: `col-lg-6` for left and right columns
- Responsive: `col-md-6` for tablets, `col-12` for mobile
- Row spacing with `mb-2`, `mb-3` classes

### UI Design Principles (Core Requirements)

**1. Active Problems First**
- Manager page displays problems with `ORDER BY status='active' DESC, date_identified DESC`
- Active/chronic problems appear at top; resolved/inactive at bottom
- Visual priority on current clinical issues

**2. Grey Out Resolved Problems**
- Resolved and inactive problems use muted text color (`text-muted` class)
- Optional strikethrough for resolved status (`text-decoration: line-through`)
- Maintains visibility for history review while reducing visual weight

**3. Inline Status Change (Quick Actions)**
- Quick-action buttons in manager table: "Mark Resolved", "Mark Chronic", "Reactivate"
- HTMX-powered: updates status without page reload
- Auto-populates date_resolved when status changes to 'resolved' (with manual override in edit form)
- Confirmation required for status changes (inline or modal)

**4. Timeline View (Per Problem)**
- **Inline timeline section** in problem detail view:
  - Shows ProblemAction entries chronologically
  - Displays: date, action, performed_by
  - Collapsible section to conserve space
- **Expanded timeline page** (`/problems/timeline/<pk>/`):
  - Full-screen chronological view of all actions
  - Shows problem status changes (tracked via ProblemAction)
  - Better for complex cases with many interventions

### Patient View Integration

**1. Add "Add Problem" Button** to `patients/templates/patients/partials/patient_view.html`:
```django
<!-- Add to action buttons section (near edit/delete buttons) -->
<a href="{% url 'problem-add' patient.pk %}" class="btn btn-success btn-sm">
  <i class="fas fa-plus-circle"></i> Add Problem
</a>
```

**2. Add Problem List Section** to `patients/templates/patients/view.html`:
```django
<!-- Problem List Section -->
<div class="row">
  <div class="col-md-12">
    <div class="card card-primary">
      <div class="card-header">
        <h3 class="card-title">
          <i class="fas fa-notes-medical"></i> Patient Problems
        </h3>
        <div class="card-tools">
          <a href="{% url 'problem-manager' patient.pk %}" class="btn btn-tool btn-sm">
            <i class="fas fa-external-link-alt"></i> View All
          </a>
        </div>
      </div>
      <div class="card-body">
        {% include 'problemlist/_problem_list_section.html' %}
      </div>
    </div>
  </div>
</div>
```

## URL Structure

```python
# problemlist/urls.py
urlpatterns = [
    path("manager/<str:pid>/", views.problem_manager, name='problem-manager'),
    path("add/<str:pid>/", views.problem_add, name='problem-add'),
    path("view/<str:pk>/", views.problem_view, name='problem-view'),
    path("edit/<str:pk>/", views.problem_edit, name='problem-edit'),
    path("delete/<str:pk>/", views.problem_delete, name='problem-delete'),
    path("status/<str:pk>/", views.problem_status_change, name='problem-status-change'),  # HTMX endpoint
    path("timeline/<str:pk>/", views.problem_timeline, name='problem-timeline'),  # Expanded timeline
    path("action/add/<str:pk>/", views.problem_action_add, name='problem-action-add'),  # Add ProblemAction
    path("analysis/", views.problem_analysis, name='problem-analysis'),  # NEW: Analysis page with filters
    path("analysis/export/", views.problem_analysis_export, name='problem-analysis-export'),  # NEW: Export filtered results
]

# Include in ndas/urls.py
path("problems/", include("problemlist.urls")),
```

**Pattern Consistency**:
- Follows NDAS URL naming: `{action}-{entity}`
- Uses `pid` for patient ID, `pk` for problem ID (consistent with existing patterns)
- Manager page scoped to patient (not global)
- **New endpoints**: status change (HTMX), timeline view, action log entry, analysis page, export

## Form Pattern

```python
# problemlist/forms.py
from django import forms
from problemlist.models import Problem, ProblemAction

class ProblemForm(forms.ModelForm):
    class Meta:
        model = Problem
        fields = [
            "name",
            "description",
            "date_of_onset",
            "date_identified",
            "status",
            "severity",
            "date_resolved",
            "action_taken",
            "outcome",
            "comments",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Bronchial Asthma"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Detailed clinical description"}),
            "date_of_onset": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "date_identified": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "severity": forms.Select(attrs={"class": "form-control"}),
            "date_resolved": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "action_taken": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Treatment, investigations, referrals"}),
            "outcome": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Response to treatment / current outcome"}),
            "comments": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Additional notes (optional)"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        date_resolved = cleaned_data.get('date_resolved')

        # Auto-populate date_resolved if status is 'resolved' and date_resolved is empty
        if status == 'resolved' and not date_resolved:
            from django.utils import timezone
            cleaned_data['date_resolved'] = timezone.now().date()

        # Clear date_resolved if status is not 'resolved'
        if status != 'resolved':
            cleaned_data['date_resolved'] = None

        return cleaned_data

class ProblemActionForm(forms.ModelForm):
    class Meta:
        model = ProblemAction
        fields = ["action"]
        widgets = {
            "action": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Describe action taken"}),
        }
```

## View Pattern

```python
# problemlist/views.py
from django.contrib.auth.decorators import login_required
from django.db.models import Case, When, Value, IntegerField, Q
from ndas.custom_codes.custom_methods import getCountZeroIfNone
from django.http import HttpResponse
import openpyxl
from io import BytesIO

@login_required(login_url="user-login")
def problem_manager(request, pid):
    patient = get_object_or_404(Patient, pk=pid)

    # Active problems first, then resolved (core design principle)
    problems = Problem.objects.filter(patient=patient).annotate(
        priority=Case(
            When(status__in=['active', 'chronic'], then=Value(1)),
            When(status__in=['resolved', 'inactive'], then=Value(2)),
            default=Value(3),
            output_field=IntegerField()
        )
    ).order_by('priority', '-date_identified')

    count = getCountZeroIfNone(problems)
    context = {
        "patient": patient,
        "problems": problems,
        "count": count,
    }
    return render(request, "problemlist/manager.html", context)

@login_required(login_url="user-login")
def problem_status_change(request, pk):
    """HTMX endpoint for inline status changes"""
    problem = get_object_or_404(Problem, pk=pk)
    new_status = request.POST.get('status')

    if new_status in dict(PROBLEM_STATUS).keys():
        problem.status = new_status

        # Auto-populate date_resolved when status becomes 'resolved'
        if new_status == 'resolved' and not problem.date_resolved:
            from django.utils import timezone
            problem.date_resolved = timezone.now().date()

        # Clear date_resolved if status is not 'resolved'
        if new_status != 'resolved':
            problem.date_resolved = None

        problem.save()

        # Log action
        ProblemAction.objects.create(
            problem=problem,
            action=f"Status changed to {new_status}",
            performed_by=request.user
        )

    # Return updated row HTML (HTMX will swap it)
    return render(request, "problemlist/_problem_row.html", {"problem": problem})

@login_required(login_url="user-login")
def problem_timeline(request, pk):
    """Expanded timeline view for problem actions"""
    problem = get_object_or_404(Problem, pk=pk)
    actions = problem.actions.all()  # Already ordered by -date
    return render(request, "problemlist/timeline.html", {"problem": problem, "actions": actions})

@login_required(login_url="user-login")
def problem_analysis(request):
    """Problem analysis page with advanced filtering"""
    from patients.models import Patient

    # Get filter parameters
    patient_id = request.GET.get('patient')
    status_filter = request.GET.getlist('status')  # Multiple selection
    severity_filter = request.GET.getlist('severity')  # Multiple selection
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    # Start with all problems
    problems = Problem.objects.select_related('patient', 'added_by').all()

    # Apply filters
    if patient_id:
        problems = problems.filter(patient_id=patient_id)

    if status_filter:
        problems = problems.filter(status__in=status_filter)

    if severity_filter:
        problems = problems.filter(severity__in=severity_filter)

    if date_from:
        problems = problems.filter(date_identified__gte=date_from)

    if date_to:
        problems = problems.filter(date_identified__lte=date_to)

    # Order by date
    problems = problems.order_by('-date_identified')

    # Get all patients for Select2 dropdown
    patients = Patient.objects.all().values('pk', 'baby_name', 'bht', 'mother_name')

    count = getCountZeroIfNone(problems)

    context = {
        "problems": problems,
        "patients": patients,
        "count": count,
        "filters": {
            "patient_id": patient_id,
            "status_filter": status_filter,
            "severity_filter": severity_filter,
            "date_from": date_from,
            "date_to": date_to,
        }
    }
    return render(request, "problemlist/analysis.html", context)

@login_required(login_url="user-login")
def problem_analysis_export(request):
    """Export filtered problems to Excel"""
    # Apply same filters as analysis page
    # ... (filter logic same as problem_analysis view)

    # Create Excel workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Problem Analysis"

    # Headers
    ws.append(['Patient BHT', 'Patient Name', 'Problem', 'Status', 'Severity', 'Date Identified', 'Date Resolved'])

    # Data rows
    for problem in problems:
        ws.append([
            problem.patient.bht,
            problem.patient.baby_name,
            problem.name,
            problem.get_status_display(),
            problem.get_severity_display() if problem.severity else 'N/A',
            problem.date_identified.strftime('%Y-%m-%d'),
            problem.date_resolved.strftime('%Y-%m-%d') if problem.date_resolved else 'N/A',
        ])

    # Save to BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=problem_analysis.xlsx'

    return response
```

## Delete Helpers Integration

Extend `ndas/custom_codes/delete_helpers.py`:

```python
# Add to ENTITY_CONFIGS
"problem": {
    "name": "Patient Problem",
    "model": "problemlist.Problem",
    "permission_field": "added_by",
    "display_fields": ["name", "date_identified", "status"],
    "redirect": lambda entity: reverse("problem-manager", kwargs={"pid": entity.patient.pk}),
},
```

**Business Rules**:
- Superusers can delete any problem entry
- Staff users can delete only their own entries (based on `added_by`)
- Cascade warning: Deleting a problem also deletes all associated ProblemAction entries

## Choices Integration

Add to `ndas/custom_codes/choice.py`:

```python
class PROBLEM_STATUS(models.TextChoices):
    ACTIVE = "active", "Active"
    RESOLVED = "resolved", "Resolved"
    CHRONIC = "chronic", "Chronic"
    INACTIVE = "inactive", "Inactive"

class SEVERITY_CHOICES(models.TextChoices):
    MILD = "mild", "Mild"
    MODERATE = "moderate", "Moderate"
    SEVERE = "severe", "Severe"
    LIFE_THREATENING = "life_threatening", "Life Threatening"
```

**Design Decision**: Status-based tracking (not boolean) allows for richer clinical workflows. Chronic problems persist but are managed; inactive problems may recur.

## Migration Plan

### Step 1: Create App Structure
```bash
python manage.py startapp problemlist
```

### Step 2: Register App
Add to `ndas/settings.py`:
```python
INSTALLED_APPS = [
    # ...existing apps...
    'problemlist',
]
```

### Step 3: Create Models
Implement `Problem` and `ProblemAction` models in `problemlist/models.py`

### Step 4: Generate Migration
```bash
python manage.py makemigrations problemlist
python manage.py migrate
```

### Step 5: Implement CRUD Operations
- Forms (`problemlist/forms.py`)
- Views (`problemlist/views.py`)
- Templates (`problemlist/templates/`)
- URLs (`problemlist/urls.py`)

### Step 6: Integrate with Patient View
Modify `patients/templates/patients/view.html` to include problem list section

### Step 7: Update Delete Helpers
Extend `ndas/custom_codes/delete_helpers.py` with problem list entity configuration

### Step 8: Testing
- Unit tests for model creation, validation
- View tests for CRUD operations
- Permission tests for delete operations
- UI tests for responsive design

### Rollback Strategy
If issues arise:
1. Remove app from `INSTALLED_APPS`
2. Run `python manage.py migrate problemlist zero` to unapply migrations
3. Revert patient view template changes
4. Revert URL configuration

## Testing Strategy

### Unit Tests
```python
# problemlist/tests.py
class ProblemListModelTest(TestCase):
    def test_problem_creation(self):
        # Test model creation with all required fields

    def test_problem_patient_cascade(self):
        # Test cascade deletion when patient is deleted

    def test_user_tracking(self):
        # Test added_by and last_edit_by auto-population

class ProblemListViewTest(TestCase):
    def test_problem_add_authenticated(self):
        # Test authenticated users can add problems

    def test_problem_delete_permission(self):
        # Test delete permissions (own records vs others)

    def test_problem_manager_display(self):
        # Test problem list display and ordering
```

### Integration Tests
- Test problem list section appears in patient view
- Test "View All" link redirects correctly
- Test problem count accuracy

### UI Tests
- Verify responsive design on mobile/tablet
- Test form validation and error messages
- Verify AdminLTE styling consistency

## Core Design Principles (Opinionated)

These principles guide the problem list implementation and reflect clinical workflow best practices:

### 1. One Problem = One Row, Persists Over Time
- Each problem is a single database record that evolves
- No duplication or versioning; status changes update the same record
- Historical tracking via ProblemAction audit log, not problem copies

**Rationale**: Matches clinical mental model. Problems are ongoing entities, not discrete events.

### 2. Status is Dynamic (Active / Resolved / Chronic / Inactive)
- Problems transition between states as clinical situation evolves
- Status field captures workflow reality better than boolean "settled"
- Chronic status recognizes long-term managed conditions

**Rationale**: Clinical problems aren't just "open" or "closed". Chronic conditions exist indefinitely.

### 3. Actions and Outcomes are Traceable
- `action_taken` field: Summary of interventions (free text, editable)
- `ProblemAction` model: Audit log of timestamped actions
- `outcome` field: Current clinical response

**Rationale**: Dual-level tracking: summary for quick reference, audit log for detailed history.

### 4. Structured Enough for Analytics, Flexible Enough for Narrative
- Structured fields: status, severity, dates (enables filtering, reporting)
- Narrative fields: description, action_taken, outcome (captures clinical nuance)
- No rigid taxonomy or controlled vocabularies

**Rationale**: Balance between clinical documentation freedom and data analytics needs.

### 5. UI Prioritizes Current Clinical Issues
- Active/chronic problems appear first (always)
- Resolved/inactive problems visible but de-emphasized (greyed out)
- Quick status changes via inline buttons (minimize clicks)

**Rationale**: Support clinical workflow; recent/active problems need immediate attention.

## Open Questions

1. **Problem categorization**: Should we add problem categories/types in future iterations?
   - **Recommendation**: Start without categories, add if users request standardization

2. **Problem relationships**: Should problems link to specific assessments or videos?
   - **Recommendation**: Not required initially; can add via many-to-many in future

3. **Bulk operations**: Should users be able to mark multiple problems as resolved at once?
   - **Recommendation**: Not needed for MVP; individual updates sufficient

4. **Notifications**: Should users be notified of new/updated problems?
   - **Recommendation**: Out of scope for initial implementation

5. **Export**: Should problem lists be included in patient PDF reports?
   - **Recommendation**: Future enhancement; can extend `reports/utils/pdf_generator.py`
