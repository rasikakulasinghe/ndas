# Specification: Patient Problem List Management

## ADDED Requirements

### Requirement: Problem Model Creation
The system SHALL provide a `Problem` model that inherits from `TimeStampedModel` and `UserTrackingMixin` to track patient problems with comprehensive clinical fields and automatic user activity tracking.

#### Scenario: Create problem record with comprehensive fields
- **WHEN** a new problem record is created
- **THEN** the record SHALL include patient reference, name, description, date_of_onset, date_identified, status, severity, date_resolved, action_taken, outcome, and comments fields
- **AND** the record SHALL automatically populate created_at, updated_at, added_by, and last_edit_by fields via base classes
- **AND** status SHALL default to 'active'
- **AND** date_identified SHALL default to current date

#### Scenario: Problem status field with multiple states
- **WHEN** defining problem status
- **THEN** the system SHALL support status values: 'active', 'resolved', 'chronic', 'inactive'
- **AND** status transitions SHALL be tracked via ProblemAction audit log

#### Scenario: Problem severity field with clinical levels
- **WHEN** defining problem severity
- **THEN** the system SHALL support severity values: 'mild', 'moderate', 'severe', 'life_threatening'
- **AND** severity field SHALL be optional (null=True, blank=True)

#### Scenario: Problem cascade deletion
- **WHEN** a patient is deleted from the system
- **THEN** all associated problem entries SHALL be automatically deleted (CASCADE behavior)
- **AND** all associated ProblemAction entries SHALL also be deleted (CASCADE from Problem)

#### Scenario: Problem indexing for performance
- **WHEN** querying problems by patient and status
- **THEN** the database SHALL use composite index on (patient, status) for optimal filtering performance
- **AND** the database SHALL use index on date_identified for chronological queries

### Requirement: ProblemAction Model Creation
The system SHALL provide a `ProblemAction` model for audit-level tracking of all actions performed on problems.

#### Scenario: Create ProblemAction for audit logging
- **WHEN** a problem action is logged
- **THEN** the record SHALL include problem reference (FK), action (TextField), date (DateTimeField), and performed_by (FK to User)
- **AND** the date field SHALL default to current timestamp
- **AND** actions SHALL be ordered by date descending (newest first)

#### Scenario: ProblemAction cascade deletion
- **WHEN** a problem is deleted from the system
- **THEN** all associated ProblemAction entries SHALL be automatically deleted (CASCADE behavior)

### Requirement: Problem Creation
The system SHALL allow authenticated users to create new problem entries for any patient with comprehensive clinical documentation.

#### Scenario: Add new problem for patient
- **WHEN** an authenticated user accesses the add problem form for a patient
- **THEN** the system SHALL display a form with fields: name, description, date_of_onset, date_identified, status, severity, action_taken, outcome, and comments
- **AND** the form SHALL use Bootstrap 4.6 styling with form-control classes
- **AND** date fields SHALL use HTML5 date picker
- **AND** status and severity fields SHALL use dropdown selects with defined choices

#### Scenario: Save new problem with validation
- **WHEN** a user submits a valid problem form
- **THEN** the system SHALL create a new Problem record linked to the patient
- **AND** the system SHALL automatically populate added_by with the current user
- **AND** the system SHALL redirect to the problem manager page for that patient
- **AND** the system SHALL display a success message

#### Scenario: Auto-populate date_resolved on status change
- **WHEN** a user creates a problem with status='resolved' and no date_resolved specified
- **THEN** the system SHALL automatically set date_resolved to the current date
- **AND** the user SHALL be able to override this date in the edit form

#### Scenario: Reject invalid problem submission
- **WHEN** a user submits a problem form with missing required fields (name, patient, date_identified)
- **THEN** the system SHALL display validation errors
- **AND** the system SHALL NOT create a problem record
- **AND** the form SHALL retain entered values for correction

### Requirement: Problem Viewing
The system SHALL allow authenticated users to view individual problem details and lists of all problems for a patient with visual priority on active problems.

#### Scenario: View individual problem details
- **WHEN** an authenticated user accesses a problem detail page
- **THEN** the system SHALL display all problem fields including name, description, date_of_onset, date_identified, status, severity, date_resolved, action_taken, outcome, comments
- **AND** the system SHALL display metadata: created_at, updated_at, added_by, last_edit_by
- **AND** the system SHALL display inline timeline section showing recent ProblemAction entries
- **AND** the system SHALL use AdminLTE card component with consistent styling

#### Scenario: View all problems for a patient with prioritized ordering
- **WHEN** an authenticated user accesses the problem manager page for a patient
- **THEN** the system SHALL display problems ordered by status priority (active/chronic first, resolved/inactive last) then by date_identified descending
- **AND** the system SHALL display basic patient information (baby_name, bht, nnc_no)
- **AND** the system SHALL show total problem count
- **AND** the system SHALL provide links to add, edit, view, and delete problems
- **AND** the system SHALL provide quick-action status change buttons

#### Scenario: Visual differentiation of resolved problems
- **WHEN** displaying problem lists
- **THEN** problems with status='resolved' or status='inactive' SHALL use muted text color (text-muted class)
- **AND** problems with status='active' or status='chronic' SHALL use standard text color
- **AND** resolved problems MAY use strikethrough styling for additional visual distinction

#### Scenario: View latest 5 problems in patient detail
- **WHEN** an authenticated user views a patient detail page
- **THEN** the system SHALL display a "Patient Problems" section
- **AND** the section SHALL show the latest 5 problems ordered by status priority then by date_identified descending
- **AND** each problem SHALL display: name, date_identified, status badge
- **AND** if more than 5 problems exist, the system SHALL display a "View All Problems" link to the problem manager page

#### Scenario: Quick add problem button in patient view
- **WHEN** an authenticated user views a patient detail page
- **THEN** the system SHALL display an "Add Problem" button in the action buttons section
- **AND** clicking the button SHALL navigate to the problem add page with patient pre-selected
- **AND** the button SHALL use `btn btn-success btn-sm` styling with `fa-plus-circle` icon

### Requirement: Problem Updating
The system SHALL allow authenticated users to edit existing problem entries and change status inline.

#### Scenario: Edit existing problem
- **WHEN** an authenticated user accesses the edit problem form
- **THEN** the system SHALL display a form pre-populated with existing problem data
- **AND** the form SHALL allow modification of name, description, date_of_onset, date_identified, status, severity, date_resolved, action_taken, outcome, and comments
- **AND** the patient field SHALL be read-only (cannot change problem to different patient)

#### Scenario: Save problem updates
- **WHEN** a user submits a valid edit form
- **THEN** the system SHALL update the problem record with new values
- **AND** the system SHALL automatically update last_edit_by with the current user
- **AND** the system SHALL automatically update updated_at timestamp
- **AND** the system SHALL redirect to the problem view page
- **AND** the system SHALL display a success message

#### Scenario: Status change with automatic date_resolved handling
- **WHEN** a user changes status to 'resolved' and date_resolved is empty
- **THEN** the system SHALL automatically populate date_resolved with the current date
- **AND** the user SHALL be able to manually override the date_resolved value
- **WHEN** a user changes status away from 'resolved'
- **THEN** the system SHALL clear the date_resolved field

### Requirement: Inline Status Change
The system SHALL provide quick-action buttons for common status transitions without full page reload.

#### Scenario: Quick status change via HTMX
- **WHEN** a user clicks a quick-action status button in the problem manager table
- **THEN** the system SHALL send an HTMX POST request to update the problem status
- **AND** the system SHALL return updated row HTML
- **AND** the browser SHALL swap the updated row without full page reload
- **AND** the system SHALL create a ProblemAction entry logging the status change

#### Scenario: Available quick-action buttons
- **WHEN** displaying a problem in the manager table
- **THEN** the system SHALL provide quick-action buttons based on current status:
  - For active problems: "Mark Resolved", "Mark Chronic"
  - For resolved problems: "Reactivate"
  - For chronic problems: "Mark Resolved"
  - For inactive problems: "Reactivate"

#### Scenario: Auto-populate date_resolved on inline status change
- **WHEN** a user clicks "Mark Resolved" quick-action button
- **THEN** the system SHALL update status to 'resolved'
- **AND** the system SHALL auto-populate date_resolved with current date if empty
- **AND** the system SHALL create a ProblemAction entry with text "Status changed to resolved"

### Requirement: Problem Timeline View
The system SHALL provide chronological timeline views of problem actions for audit and review purposes.

#### Scenario: Inline timeline section in problem detail
- **WHEN** viewing a problem detail page
- **THEN** the system SHALL display an inline timeline section showing ProblemAction entries
- **AND** timeline SHALL be collapsible to conserve space
- **AND** each action SHALL display: date, action text, performed_by user
- **AND** actions SHALL be ordered by date descending (newest first)
- **AND** timeline SHALL show the 10 most recent actions by default

#### Scenario: Expanded timeline page
- **WHEN** a user accesses the expanded timeline page for a problem
- **THEN** the system SHALL display a full-screen chronological view of all ProblemAction entries
- **AND** timeline SHALL include all actions without pagination limit
- **AND** timeline SHALL show problem status changes tracked via ProblemAction
- **AND** page SHALL provide navigation back to problem detail view

### Requirement: ProblemAction Logging
The system SHALL automatically log significant problem actions for audit trail purposes.

#### Scenario: Log status changes
- **WHEN** a problem status is changed (via form or quick-action button)
- **THEN** the system SHALL create a ProblemAction entry with action text "Status changed to [new_status]"
- **AND** the performed_by field SHALL be set to the current user
- **AND** the date field SHALL be set to current timestamp

#### Scenario: Manual action entry
- **WHEN** a user adds a manual action note to a problem
- **THEN** the system SHALL create a ProblemAction entry with the user-provided action text
- **AND** the performed_by field SHALL be set to the current user
- **AND** the date field SHALL be set to current timestamp
- **AND** the system SHALL redirect back to the problem detail view

### Requirement: Problem Deletion
The system SHALL allow authorized users to delete problem entries with proper permission checks and cascade warnings.

#### Scenario: Delete own problem as staff user
- **WHEN** a staff user attempts to delete a problem they created (added_by matches current user)
- **THEN** the system SHALL use has_delete_permission() from delete_helpers.py to verify permission
- **AND** the system SHALL delete the problem record and all associated ProblemAction entries (CASCADE)
- **AND** the system SHALL redirect to the problem manager page for that patient
- **AND** the system SHALL display a success message

#### Scenario: Delete any problem as superuser
- **WHEN** a superuser attempts to delete any problem
- **THEN** the system SHALL use has_delete_permission() from delete_helpers.py to verify permission
- **AND** the system SHALL delete the problem record regardless of who created it

#### Scenario: Reject unauthorized deletion
- **WHEN** a staff user attempts to delete a problem created by another user
- **THEN** the system SHALL use has_delete_permission() from delete_helpers.py to verify permission
- **AND** the system SHALL reject the deletion with a permission denied message
- **AND** the problem record SHALL remain unchanged

#### Scenario: Cascade deletion warning
- **WHEN** displaying delete confirmation for a problem
- **THEN** the system SHALL warn that all associated ProblemAction entries will also be deleted
- **AND** the system SHALL display the count of actions that will be deleted

### Requirement: Problem URL Structure
The system SHALL provide RESTful URL patterns for problem operations following NDAS conventions.

#### Scenario: URL routing for problem operations
- **WHEN** accessing problem URLs
- **THEN** the system SHALL route requests according to the following patterns:
  - `/problems/manager/<patient_id>/` → problem_manager view
  - `/problems/add/<patient_id>/` → problem_add view
  - `/problems/view/<problem_id>/` → problem_view view
  - `/problems/edit/<problem_id>/` → problem_edit view
  - `/problems/delete/<problem_id>/` → problem_delete view
  - `/problems/status/<problem_id>/` → problem_status_change view (HTMX endpoint)
  - `/problems/timeline/<problem_id>/` → problem_timeline view (expanded timeline)
  - `/problems/action/add/<problem_id>/` → problem_action_add view (add ProblemAction)
  - `/problems/analysis/` → problem_analysis view (analysis page with filters)
  - `/problems/analysis/export/` → problem_analysis_export view (export filtered results)

#### Scenario: Named URL patterns for templates
- **WHEN** templates reference problem URLs
- **THEN** the system SHALL provide named URL patterns:
  - `problem-manager` - List all problems for patient
  - `problem-add` - Create new problem
  - `problem-view` - View problem details
  - `problem-edit` - Edit problem
  - `problem-delete` - Delete problem
  - `problem-status-change` - HTMX inline status change
  - `problem-timeline` - Expanded timeline view
  - `problem-action-add` - Add action log entry
  - `problem-analysis` - Problem analysis page
  - `problem-analysis-export` - Export analysis results

### Requirement: Problem Security
The system SHALL enforce authentication and authorization for all problem operations.

#### Scenario: Require authentication for all views
- **WHEN** an unauthenticated user attempts to access any problem view
- **THEN** the system SHALL redirect to the login page (user-login)
- **AND** the system SHALL preserve the intended destination for post-login redirect

#### Scenario: CSRF protection on forms
- **WHEN** rendering problem add or edit forms or processing HTMX status changes
- **THEN** the system SHALL include CSRF tokens in form submissions
- **AND** the system SHALL validate CSRF tokens via CsrfViewMiddleware

#### Scenario: User tracking middleware integration
- **WHEN** creating or updating a problem record
- **THEN** the system SHALL automatically populate added_by on creation via UserActivityMiddleware
- **AND** the system SHALL automatically populate last_edit_by on update via UserActivityMiddleware

#### Scenario: ProblemAction user tracking
- **WHEN** creating a ProblemAction entry
- **THEN** the system SHALL set performed_by to the current authenticated user
- **AND** the system SHALL NOT allow modification of performed_by after creation

### Requirement: Problem UI Consistency
The system SHALL maintain AdminLTE 3.2 and Bootstrap 4.6 styling consistency across all problem interfaces with visual priority on active problems.

#### Scenario: Template inheritance and structure
- **WHEN** rendering problem templates
- **THEN** all templates SHALL extend 'src/base.html'
- **AND** templates SHALL use {% block main_content %} for content
- **AND** templates SHALL include {% csrf_token %} in container-fluid divs

#### Scenario: Form styling consistency
- **WHEN** rendering problem forms
- **THEN** form fields SHALL use "form-control" CSS class
- **AND** select dropdowns SHALL use "form-control" CSS class
- **AND** form layouts SHALL follow NDAS form patterns (labels, help text, validation messages)

#### Scenario: Status badge styling
- **WHEN** displaying problem status
- **THEN** the system SHALL use Bootstrap badge components
- **AND** active status SHALL use "badge-success" class
- **AND** resolved status SHALL use "badge-secondary" class
- **AND** chronic status SHALL use "badge-warning" class
- **AND** inactive status SHALL use "badge-light" class

#### Scenario: Responsive design
- **WHEN** viewing problems on mobile or tablet devices
- **THEN** tables SHALL use "table-responsive" Bootstrap class
- **AND** cards SHALL stack appropriately for smaller screens
- **AND** forms SHALL remain usable on touch devices
- **AND** quick-action buttons SHALL be touch-friendly with adequate spacing

### Requirement: Problem Template Naming
The system SHALL follow NDAS template naming conventions for consistency.

#### Scenario: Template file structure
- **WHEN** organizing problem templates
- **THEN** templates SHALL be located in `problemlist/templates/problemlist/` directory
- **AND** templates SHALL follow naming: manager.html (list), add.html (create), edit.html (update), view.html (detail), timeline.html (expanded timeline), analysis.html (analysis with filters)
- **AND** reusable components SHALL use underscore prefix: `_problem_list_section.html`, `_problem_row.html` (HTMX swap target)

### Requirement: Delete Helpers Integration
The system SHALL integrate problem entity configuration into centralized delete_helpers.py module.

#### Scenario: Register problem entity in delete helpers
- **WHEN** delete_helpers.py is loaded
- **THEN** the ENTITY_CONFIGS dictionary SHALL include "problem" configuration
- **AND** configuration SHALL specify model path "problemlist.Problem"
- **AND** configuration SHALL specify permission_field as "added_by"
- **AND** configuration SHALL specify display_fields as ["name", "date_identified", "status"]
- **AND** configuration SHALL specify redirect function returning problem-manager URL for patient

#### Scenario: Use delete helper functions in views
- **WHEN** problem deletion is requested
- **THEN** the view SHALL use has_delete_permission(user, problem, "problem") to check permissions
- **AND** the view SHALL use get_redirect_url("problem", problem) for post-deletion redirect
- **AND** the view SHALL use get_entity_display_name("problem") for messages
- **AND** the view SHALL display cascade warning showing count of ProblemAction entries to be deleted

### Requirement: Problem Analysis and Reporting
The system SHALL provide comprehensive problem analysis capabilities with advanced filtering and export functionality for research and reporting purposes.

#### Scenario: Access problem analysis page
- **WHEN** an authenticated user accesses the problem analysis page
- **THEN** the system SHALL display filter controls for patient, status, severity, and date range
- **AND** the page SHALL display all problems by default (no filters applied)
- **AND** the page SHALL use Select2 for patient selection with autocomplete search
- **AND** the page SHALL follow add patient page UI styling (colored card outlines, icons)

#### Scenario: Filter problems by patient
- **WHEN** a user selects a patient from the Select2 dropdown
- **THEN** the system SHALL filter results to show only problems for that patient
- **AND** the Select2 SHALL display patient BHT, baby name, and mother name for identification
- **AND** the Select2 SHALL support search/autocomplete for large patient databases

#### Scenario: Filter problems by status
- **WHEN** a user selects one or more status values (active, resolved, chronic, inactive)
- **THEN** the system SHALL filter results to show only problems with selected statuses
- **AND** the status filter SHALL support multiple selection
- **AND** no selection SHALL mean "all statuses"

#### Scenario: Filter problems by severity
- **WHEN** a user selects one or more severity values (mild, moderate, severe, life_threatening)
- **THEN** the system SHALL filter results to show only problems with selected severities
- **AND** the severity filter SHALL support multiple selection
- **AND** no selection SHALL mean "all severities"

#### Scenario: Filter problems by date range
- **WHEN** a user specifies date_from and/or date_to
- **THEN** the system SHALL filter results based on date_identified field
- **AND** date_from SHALL filter problems identified on or after that date
- **AND** date_to SHALL filter problems identified on or before that date
- **AND** both filters SHALL work together to define a date range

#### Scenario: Combined filtering
- **WHEN** a user applies multiple filters simultaneously
- **THEN** the system SHALL apply all filters using AND logic
- **AND** the results SHALL display problem count
- **AND** the results SHALL be ordered by date_identified descending (newest first)

#### Scenario: Display filtered results
- **WHEN** displaying problem analysis results
- **THEN** the system SHALL show a table with columns: Patient, Problem, Status, Severity, Date Identified, Date Resolved, Actions
- **AND** the table SHALL use Bootstrap responsive classes
- **AND** resolved/inactive problems SHALL use text-muted styling
- **AND** status SHALL be displayed as colored badges
- **AND** each row SHALL have a view button linking to problem detail page

#### Scenario: Clear filters
- **WHEN** a user clicks the "Clear" button
- **THEN** the system SHALL reset all filters to default (no filters)
- **AND** the system SHALL reload the page showing all problems

#### Scenario: Export filtered results to Excel
- **WHEN** a user clicks "Export to Excel" button
- **THEN** the system SHALL export currently filtered results to Excel file
- **AND** the Excel file SHALL include columns: Patient BHT, Patient Name, Problem, Status, Severity, Date Identified, Date Resolved
- **AND** the Excel file SHALL be named "problem_analysis.xlsx"
- **AND** the file SHALL download immediately
- **AND** the export SHALL use the openpyxl library

#### Scenario: Preserve filter state in URL
- **WHEN** filters are applied
- **THEN** the system SHALL encode filter parameters in URL query string
- **AND** the export link SHALL include current filter parameters
- **AND** filter selections SHALL persist when navigating back to the page

### Requirement: Problem Data Validation
The system SHALL validate problem data to ensure medical data integrity and clinical accuracy.

#### Scenario: Required field validation
- **WHEN** creating or updating a problem
- **THEN** the system SHALL require patient, name, date_identified, and status fields
- **AND** the system SHALL allow description, date_of_onset, severity, action_taken, outcome, and comments to be optional
- **AND** the system SHALL require date_resolved if status is 'resolved' (or auto-populate it)

#### Scenario: Date validation for date_of_onset
- **WHEN** a user enters a date_of_onset
- **THEN** the system SHALL accept valid dates
- **AND** the system SHALL reject future dates (problems cannot start in the future)
- **AND** the system SHALL reject dates before patient's date of birth

#### Scenario: Date validation for date_identified
- **WHEN** a user enters a date_identified
- **THEN** the system SHALL accept valid dates
- **AND** the system SHALL default to current date if not specified
- **AND** the system SHALL reject dates before patient's date of birth

#### Scenario: Date validation for date_resolved
- **WHEN** a user enters a date_resolved
- **THEN** the system SHALL accept valid dates
- **AND** the system SHALL reject dates before date_of_onset or date_identified
- **AND** the system SHALL reject future dates

#### Scenario: Status and severity choices validation
- **WHEN** a user selects status or severity
- **THEN** the system SHALL only accept values from defined choices in PROBLEM_STATUS and SEVERITY_CHOICES
- **AND** the system SHALL reject invalid status or severity values

#### Scenario: Text field length validation
- **WHEN** a user enters problem information
- **THEN** the name field SHALL accept up to 255 characters
- **AND** the description field SHALL accept unlimited text (TextField)
- **AND** the action_taken field SHALL accept unlimited text (TextField)
- **AND** the outcome field SHALL accept unlimited text (TextField)
- **AND** the comments field SHALL accept unlimited text (TextField)
