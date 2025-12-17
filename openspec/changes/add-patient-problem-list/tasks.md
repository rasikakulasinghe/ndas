# Implementation Tasks: Add Patient Problem List

## 1. Project Setup
- [x] 1.1 Create `problemlist` Django app using `python manage.py startapp problemlist`
- [x] 1.2 Add `'problemlist'` to `INSTALLED_APPS` in `ndas/settings.py`
- [x] 1.3 Create directory structure: `problemlist/templates/problemlist/`

## 2. Database Model
- [x] 2.1 Create `ProblemList` model in `problemlist/models.py` inheriting from `TimeStampedModel` and `UserTrackingMixin`
- [x] 2.2 Add fields: `patient` (ForeignKey), `date_of_start` (DateField with `db_index=True`), `problem` (CharField max_length=500), `full_details` (TextField), `action_taken` (TextField), `is_settled` (BooleanField with `db_index=True` and default=False), `notes` (TextField, blank=True, null=True)
- [x] 2.3 Add model `__str__` method returning f"{self.patient.baby_name} - {self.problem[:50]}"
- [x] 2.4 Add model `Meta` with ordering `['-date_of_start']` and verbose names
- [x] 2.5 Run `python manage.py makemigrations problemlist` to create migration
- [x] 2.6 Run `python manage.py migrate` to apply migration

## 3. Forms
- [x] 3.1 Create `problemlist/forms.py` with `ProblemListForm` class
- [x] 3.2 Define form fields: date_of_start, problem, full_details, action_taken, is_settled, notes
- [x] 3.3 Add Bootstrap 4.6 widget classes: `form-control` for text/textarea, `form-check-input` for checkbox
- [x] 3.4 Add HTML5 date picker for date_of_start: `type="date"` attribute
- [x] 3.5 Add help_text for clinical fields (problem, full_details, action_taken, is_settled)
- [x] 3.6 Add placeholders for guidance on each field
- [x] 3.7 Add custom validation for date_of_start (cannot be future date, cannot be before patient DOB)

## 4. Views - Problem Manager
- [x] 4.1 Create `problemlist/views.py` with imports (Patient, ProblemList, decorators, helpers)
- [x] 4.2 Implement `problem_manager(request, pid)` view with `@login_required` decorator
- [x] 4.3 Get patient using `get_object_or_404(Patient, pk=pid)`
- [x] 4.4 Query all problems for patient: `ProblemList.objects.filter(patient=patient).order_by('-date_of_start')`
- [x] 4.5 Calculate count using `getCountZeroIfNone(problems)`
- [x] 4.6 Render `problemlist/manager.html` with context: patient, problems, count

## 5. Views - Add Problem
- [x] 5.1 Implement `problem_add(request, pid)` view with `@login_required` decorator
- [x] 5.2 Get patient using `get_object_or_404(Patient, pk=pid)`
- [x] 5.3 Handle GET request: instantiate `ProblemListForm()` and render `problemlist/add.html`
- [x] 5.4 Handle POST request: instantiate `ProblemListForm(request.POST)`
- [x] 5.5 Validate form and save with `commit=False` to set patient before saving
- [x] 5.6 Display success message and redirect to `problem-manager` with patient ID
- [x] 5.7 Handle validation errors by re-rendering form with errors

## 6. Views - View Problem
- [x] 6.1 Implement `problem_view(request, pk)` view with `@login_required` decorator
- [x] 6.2 Get problem using `get_object_or_404(ProblemList, pk=pk)`
- [x] 6.3 Get related patient from problem
- [x] 6.4 Render `problemlist/view.html` with context: problem, patient

## 7. Views - Edit Problem
- [x] 7.1 Implement `problem_edit(request, pk)` view with `@login_required` decorator
- [x] 7.2 Get problem using `get_object_or_404(ProblemList, pk=pk)`
- [x] 7.3 Handle GET request: instantiate `ProblemListForm(instance=problem)` and render `problemlist/edit.html`
- [x] 7.4 Handle POST request: instantiate `ProblemListForm(request.POST, instance=problem)`
- [x] 7.5 Validate form and save (patient already set, no need to modify)
- [x] 7.6 Display success message and redirect to `problem-view` with problem ID
- [x] 7.7 Handle validation errors by re-rendering form with errors

## 8. Views - Delete Problem
- [x] 8.1 Implement `problem_delete(request, pk)` view with `@login_required` decorator
- [x] 8.2 Get problem using `get_object_or_404(ProblemList, pk=pk)`
- [x] 8.3 Import delete helper functions: `has_delete_permission`, `get_redirect_url`
- [x] 8.4 Check permission using `has_delete_permission(request.user, problem, "problemlist")`
- [x] 8.5 If permitted, store patient ID, delete problem, display success message
- [x] 8.6 Redirect using `get_redirect_url("problemlist", problem)` (to problem-manager for patient)
- [x] 8.7 If not permitted, display error message and redirect to problem-manager

## 9. URL Configuration
- [x] 9.1 Create `problemlist/urls.py` with app_name (if used) and urlpatterns list
- [x] 9.2 Add URL pattern: `path("manager/<str:pid>/", views.problem_manager, name='problem-manager')`
- [x] 9.3 Add URL pattern: `path("add/<str:pid>/", views.problem_add, name='problem-add')`
- [x] 9.4 Add URL pattern: `path("view/<str:pk>/", views.problem_view, name='problem-view')`
- [x] 9.5 Add URL pattern: `path("edit/<str:pk>/", views.problem_edit, name='problem-edit')`
- [x] 9.6 Add URL pattern: `path("delete/<str:pk>/", views.problem_delete, name='problem-delete')`
- [x] 9.7 Include problemlist URLs in `ndas/urls.py`: `path("problems/", include("problemlist.urls"))`

## 10. Templates - Manager Page
- [x] 10.1 Create `problemlist/templates/problemlist/manager.html` extending `src/base.html`
- [x] 10.2 Set block title: "Problem List - [Patient Name] | NDAS"
- [x] 10.3 Add breadcrumb navigation: Home > Patients > Patient Name > Problem List
- [x] 10.4 Display patient basic info card: baby_name, bht, nnc_no (read-only)
- [x] 10.5 Add "Back to Patient" button linking to `view-patient` with patient ID
- [x] 10.6 Add "Add New Problem" button linking to `problem-add` with patient ID
- [x] 10.7 Create problems table with columns: Date, Problem, Status, Actions
- [x] 10.8 Display is_settled status with badge (success for settled, warning for active)
- [x] 10.9 Add action buttons: View, Edit, Delete (with delete confirmation modal or unified modal)
- [x] 10.10 Display problem count and "No problems found" message if count is zero
- [x] 10.11 Make table responsive with `table-responsive` Bootstrap class

## 11. Templates - Add Form
- [x] 11.1 Create `problemlist/templates/problemlist/add.html` extending `src/base.html`
- [x] 11.2 Set block title: "Add Problem - [Patient Name] | NDAS"
- [x] 11.3 Add breadcrumb navigation: Home > Patients > Patient Name > Add Problem
- [x] 11.4 Display patient name and identifiers (read-only info box)
- [x] 11.5 Create form with POST method and `{% csrf_token %}`
- [x] 11.6 Render form fields using Bootstrap styling: date_of_start, problem, full_details, action_taken, is_settled, notes
- [x] 11.7 Add form validation error display
- [x] 11.8 Add "Save Problem" submit button and "Cancel" button (back to patient view)
- [x] 11.9 Add help text and placeholders for medical guidance

## 12. Templates - View Page
- [x] 12.1 Create `problemlist/templates/problemlist/view.html` extending `src/base.html`
- [x] 12.2 Set block title: "View Problem - [Problem Summary] | NDAS"
- [x] 12.3 Add breadcrumb navigation: Home > Patients > Patient Name > Problem List > Problem Details
- [x] 12.4 Display patient info card: baby_name, bht
- [x] 12.5 Display problem details card with all fields: date_of_start, problem, full_details, action_taken, is_settled, notes
- [x] 12.6 Display metadata: created_at, updated_at, added_by, last_edit_by
- [x] 12.7 Add action buttons: Edit, Delete, Back to Problem List
- [x] 12.8 Use AdminLTE card components with consistent styling

## 13. Templates - Edit Form
- [x] 13.1 Create `problemlist/templates/problemlist/edit.html` extending `src/base.html`
- [x] 13.2 Set block title: "Edit Problem - [Problem Summary] | NDAS"
- [x] 13.3 Add breadcrumb navigation: Home > Patients > Patient Name > Problem List > Edit Problem
- [x] 13.4 Display patient name (read-only)
- [x] 13.5 Create form with POST method, `{% csrf_token %}`, and pre-populated with problem data
- [x] 13.6 Render form fields (same as add.html but with existing values)
- [x] 13.7 Add form validation error display
- [x] 13.8 Add "Update Problem" submit button and "Cancel" button (back to problem view)

## 14. Templates - Patient View Integration
- [x] 14.1 Create `problemlist/templates/problemlist/_problem_list_section.html` partial template
- [x] 14.2 Query latest 5 problems: `patient.problems.all()[:5]` (use related_name='problems')
- [x] 14.3 Display problems in compact table: Date, Problem, Status
- [x] 14.4 Show "Active" or "Settled" badge for each problem
- [x] 14.5 Add "View All Problems" link if problem count > 5 (link to problem-manager)
- [x] 14.6 Display "No problems recorded" message if no problems exist
- [x] 14.7 Modify `patients/templates/patients/view.html` to include section after assessments
- [x] 14.8 Add new card div with header "Patient Problems" and body including the partial template
- [x] 14.9 Add `{% include 'problemlist/_problem_list_section.html' with patient=patient %}` in card body

## 15. Delete Helpers Integration
- [x] 15.1 Open `ndas/custom_codes/delete_helpers.py`
- [x] 15.2 Add "problemlist" to `ENTITY_CONFIGS` dictionary
- [x] 15.3 Configure: `"name": "Problem List Entry"`
- [x] 15.4 Configure: `"model": "problemlist.ProblemList"`
- [x] 15.5 Configure: `"permission_field": "added_by"`
- [x] 15.6 Configure: `"display_fields": ["problem", "date_of_start", "is_settled"]`
- [x] 15.7 Configure: `"redirect": lambda entity: reverse("problem-manager", kwargs={"pid": entity.patient.pk})`
- [x] 15.8 Test permission checks: superuser can delete all, staff can delete own only

## 16. Testing - Unit Tests
- [x] 16.1 Create `problemlist/tests.py` with Django TestCase imports
- [x] 16.2 Write test for problem list model creation with all required fields
- [x] 16.3 Write test for patient cascade deletion (problems deleted when patient deleted)
- [x] 16.4 Write test for user tracking: added_by and last_edit_by auto-population
- [x] 16.5 Write test for problem manager view (authenticated access)
- [x] 16.6 Write test for problem add view (form rendering and submission)
- [x] 16.7 Write test for problem edit view (form pre-population and update)
- [x] 16.8 Write test for problem delete permission (own vs others, superuser vs staff)
- [x] 16.9 Write test for unauthenticated access (redirect to login)
- [x] 16.10 Write test for date validation (future dates, dates before patient DOB)

## 17. Testing - Integration Tests
- [x] 17.1 Test problem list section appears in patient view template
- [x] 17.2 Test "View All Problems" link redirects correctly when >5 problems exist
- [x] 17.3 Test problem count accuracy in manager page
- [x] 17.4 Test settled/active badge display in templates
- [x] 17.5 Test navigation flow: patient view → add problem → manager → view → edit → delete → manager

## 18. Testing - Manual UI Tests
- [x] 18.1 Test responsive design on mobile (320px width)
- [x] 18.2 Test responsive design on tablet (768px width)
- [x] 18.3 Test form validation error messages display correctly
- [x] 18.4 Test AdminLTE styling consistency across all pages
- [x] 18.5 Test date picker functionality in forms
- [x] 18.6 Test checkbox styling for is_settled field
- [x] 18.7 Test delete confirmation (if using modal)

## 19. Documentation
- [x] 19.1 Add docstrings to model class explaining purpose and fields
- [x] 19.2 Add docstrings to view functions explaining parameters and behavior
- [x] 19.3 Add comments in forms explaining validation logic
- [x] 19.4 Update `CLAUDE.md` if needed with problemlist app references
- [x] 19.5 Document problem list feature in help system (if applicable)

## 20. Final Validation
- [x] 20.1 Run all tests: `python manage.py test problemlist`
- [x] 20.2 Run all tests across project: `python manage.py test`
- [x] 20.3 Run migrations check: `python manage.py makemigrations --check --dry-run`
- [x] 20.4 Run Django system checks: `python manage.py check`
- [x] 20.5 Test complete workflow: create patient → add 6 problems → view patient (see latest 5) → view all → edit problem → mark as settled → delete problem
- [x] 20.6 Verify user tracking fields populated correctly in database
- [x] 20.7 Verify delete permissions work correctly (test with staff and superuser accounts)
- [x] 20.8 Verify responsive design on actual mobile/tablet devices
- [x] 20.9 Run `openspec validate add-patient-problem-list --strict` to confirm proposal compliance
- [x] 20.10 Update all task checkboxes to [x] in `tasks.md` when complete
