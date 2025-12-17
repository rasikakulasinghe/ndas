# Change: Add Patient Problem List Management

## Why
Medical professionals need a structured way to track, document, and manage ongoing patient problems and conditions within the NDAS system. Currently, there's no dedicated mechanism to record patient problems, actions taken, and their resolution status. This creates gaps in comprehensive patient care documentation and makes it difficult to track the progression of patient issues over time.

## What Changes
- Add new Django app called `problemlist` for managing patient problems
- Create `Problem` model with comprehensive clinical tracking fields:
  - Patient reference, name, description, date_of_onset, date_identified, date_resolved
  - Status field (active, resolved, chronic, inactive) - replaces boolean is_settled
  - Severity field (mild, moderate, severe, life_threatening)
  - action_taken, outcome, comments fields for clinical documentation
- Create `ProblemAction` model for audit-level action logging (separate from action_taken field)
- Add CRUD operations (Create, Read, Update, Delete) for problem list entries
- Display latest 5 problems in patient detail view with "View All" link
- Add "Add Problem" button in patient view section linking to problem add page
- Create dedicated manager page showing all patient problems (active first, resolved greyed out)
- Add inline status change via quick-action buttons (e.g., "Mark Resolved")
- Add timeline view for problem history: inline section in detail view + expanded timeline page
- Auto-populate date_resolved when status changes to 'resolved' (with manual override)
- **NEW: Problem Analysis page** with advanced filtering:
  - Filter by patient (extensive autocomplete/search input using Select2)
  - Filter by status (active/resolved/chronic/inactive)
  - Filter by severity (mild/moderate/severe/life_threatening)
  - Filter by date range (from/to dates)
  - Export filtered results to Excel/PDF
- **UI Theme**: Match add patient page styling (colored card outlines, icons, form layouts)
- Follow NDAS architectural patterns (TimeStampedModel, UserTrackingMixin, delete helpers)
- Integrate with existing patient management workflow
- Maintain AdminLTE UI consistency

## Impact
- **Affected specs**: New capability `problem-list` (patient problem tracking)
- **Affected code**:
  - New app: `problemlist/` (models, views, forms, templates, URLs)
  - Modified: `patients/templates/patients/partials/patient_view.html` (add "Add Problem" button)
  - Modified: `patients/templates/patients/view.html` (add problem list section)
  - Modified: `ndas/settings.py` (register new app)
  - Modified: `ndas/urls.py` (include problemlist URLs)
  - Modified: `ndas/custom_codes/choice.py` (problem status and severity choices)
  - Modified: `ndas/custom_codes/delete_helpers.py` (add problem entity support)
  - New view: `problem_analysis` with filters and export functionality
- **Database migrations**: Yes - new `Problem` and `ProblemAction` tables with foreign keys to Patient and User
- **UI changes**: Yes - "Add Problem" button in patient view, new section showing latest 5 problems, new manager page, add/edit/view templates with colored card outlines matching add patient page, new problem analysis page with advanced filters
- **Security considerations**: User tracking via middleware, permission checks for delete operations
- **Medical data**: Problem descriptions and clinical actions require proper validation and help text
