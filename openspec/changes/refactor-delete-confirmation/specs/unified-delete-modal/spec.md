# Spec: Unified Delete Confirmation Modal

**Capability:** `unified-delete-modal`
**Change:** `refactor-delete-confirmation`

## Overview

This specification defines the unified delete confirmation system that replaces 11+ separate delete confirmation templates with a single reusable modal component, centralized JavaScript handler, and standardized backend API.

---

## ADDED Requirements

### Requirement: Reusable Modal Component

The system SHALL provide a single reusable Bootstrap modal component for all entity deletion operations across the NDAS application.

**Rationale:** Eliminates code duplication, ensures consistency, and simplifies maintenance by providing one source of truth for deletion UI.

**Acceptance Criteria:**
- Single template file at `templates/src/partials/delete_confirmation_modal.html`
- Configurable via Django template context variables
- Uses Bootstrap 4.6 modal structure
- Includes password verification field
- Displays entity-specific warnings and details
- Supports ARIA attributes for accessibility

#### Scenario: Display Patient Deletion Modal

**Given** a patient manager page with patient records
**When** a user with delete permissions clicks the delete button for a patient
**Then** the system SHALL:
- Display a Bootstrap modal with title "Confirm Patient Deletion"
- Show warning message about irreversible action
- List all related records that will be deleted (videos, assessments, attachments, etc.)
- Display patient identifying information (name, BHT, gender)
- Provide password input field with label "Enter your password to confirm:"
- Show Cancel and "Delete Patient" buttons
- Focus the password input field

**Expected State:**
- Modal visible with overlay
- Password field empty and focused
- Delete button enabled
- Cancel button enabled

---

### Requirement: Centralized JavaScript Handler

The system SHALL provide a unified JavaScript module for handling all deletion operations with password verification and AJAX communication.

**Rationale:** Consolidates deletion logic, provides consistent error handling, and enables smooth UX without page reloads.

**Acceptance Criteria:**
- Single JavaScript file at `static/js/delete-confirmation.js`
- Exposes public API: `DeleteConfirmation.show()` and `DeleteConfirmation.execute()`
- Handles AJAX DELETE requests with JSON payload
- Validates password client-side before submission
- Shows loading states during deletion
- Displays error messages inline in modal
- Redirects on success with success message
- Supports keyboard navigation (Enter to confirm)

#### Scenario: Execute Deletion with Valid Password

**Given** a delete confirmation modal is displayed
**And** the user has entered their correct password
**When** the user clicks the "Delete" button
**Then** the system SHALL:
- Disable the delete button
- Show loading spinner
- Send DELETE request to backend with JSON payload `{password: "user_password"}`
- Include CSRF token in request headers
- On success response:
  - Hide the modal
  - Display success message alert
  - Redirect to appropriate manager page after 1.5 seconds
- On error response:
  - Keep modal open
  - Display error message below password field
  - Re-enable delete button
  - Hide loading spinner

**Expected Backend Request:**
```http
DELETE /patient/delete/123/
Content-Type: application/json
X-CSRFToken: [token]

{"password": "user_password"}
```

**Expected Success Response:**
```json
{
  "success": true,
  "message": "Patient 'Baby Name' has been deleted successfully.",
  "redirect_url": "/manager/patient/"
}
```

#### Scenario: Reject Deletion with Invalid Password

**Given** a delete confirmation modal is displayed
**And** the user has entered an incorrect password
**When** the user clicks the "Delete" button
**Then** the system SHALL:
- Send DELETE request to backend
- Receive 401 Unauthorized response
- Display error message "Incorrect password. Please try again."
- Keep modal open
- Clear password field
- Re-focus password field
- Log failed attempt on backend

**Expected Error Response:**
```json
{
  "success": false,
  "error": "Invalid password",
  "message": "Incorrect password. Please try again."
}
```

#### Scenario: Prevent Deletion with Empty Password

**Given** a delete confirmation modal is displayed
**And** the password field is empty
**When** the user clicks the "Delete" button
**Then** the system SHALL:
- NOT send request to backend
- Display error message "Please enter your password"
- Keep modal open
- Focus password field

---

### Requirement: Standardized Delete Views

All entity deletion views SHALL follow a consistent pattern accepting DELETE method requests with JSON payload and returning standardized JSON responses.

**Rationale:** Ensures uniform security, error handling, and audit logging across all deletion operations.

**Acceptance Criteria:**
- Accept DELETE HTTP method only
- Require JSON payload with password field
- Verify user password using `user.check_password()`
- Check entity-specific permissions before deletion
- Validate business rules (e.g., cascade restrictions)
- Perform audit logging for all deletion attempts
- Return JSON response with success/error structure
- Use consistent HTTP status codes (200, 400, 401, 403, 404, 500)

#### Scenario: Delete Patient with Proper Authorization

**Given** a patient record with ID 123 exists
**And** the requesting user is a superuser
**And** the user provides correct password
**When** a DELETE request is made to `/patient/delete/123/`
**Then** the system SHALL:
- Verify user is authenticated
- Check user has delete permission (is_superuser)
- Verify provided password matches user's password
- Check business rules (no blocking constraints)
- Delete the patient record
- Cascade delete related records (videos, assessments, attachments)
- Log deletion: `"Deletion successful: user=admin, entity=Patient, name=Baby Name, id=123"`
- Return 200 response with success JSON

**Expected Response:**
```json
{
  "success": true,
  "message": "Patient 'Baby Name' has been deleted successfully.",
  "redirect_url": "/manager/patient/"
}
```

#### Scenario: Reject Deletion Due to Insufficient Permissions

**Given** a patient record with ID 123 exists
**And** the requesting user is not a superuser
**And** the patient was not added by the requesting user
**When** a DELETE request is made to `/patient/delete/123/`
**Then** the system SHALL:
- Verify user is authenticated
- Check user permissions
- Find user lacks delete permission
- Log unauthorized attempt: `"Unauthorized deletion attempt: user=john, entity=Patient, id=123"`
- Return 403 Forbidden response
- NOT delete the patient

**Expected Response:**
```json
{
  "success": false,
  "error": "Permission denied",
  "message": "You do not have permission to delete this record."
}
```

#### Scenario: Reject Video Deletion with Active Assessments

**Given** a video record with ID 456 exists
**And** the video is referenced in 3 GMAssessment records
**And** the requesting user has delete permissions
**And** the user provides correct password
**When** a DELETE request is made to `/video/delete/456/`
**Then** the system SHALL:
- Verify user authentication and permissions
- Verify password
- Check business rules for video deletion
- Find video is used in 3 assessments
- Return 400 Bad Request response
- NOT delete the video

**Expected Response:**
```json
{
  "success": false,
  "error": "Cannot delete",
  "message": "Cannot delete video that is used in 3 assessment(s)."
}
```

---

### Requirement: Template Integration Pattern

All entity manager and view templates SHALL integrate the unified delete modal using a consistent include pattern with entity-specific configuration.

**Rationale:** Provides clear, maintainable integration pattern that developers can easily follow when adding new deletable entities.

**Acceptance Criteria:**
- Include modal once per page at bottom of template
- Configure via context variables passed to include tag
- Trigger modal with data attributes on delete button
- No inline JavaScript in templates (use centralized handler)
- Consistent button styling across all pages

#### Scenario: Integrate Delete Modal in Patient Manager

**Given** the patient manager template
**When** rendering the page with patient list
**Then** the system SHALL:
- Include unified modal partial at bottom: `{% include 'src/partials/delete_confirmation_modal.html' %}`
- Configure modal with patient-specific details
- Render delete buttons in patient list with proper data attributes
- Load delete-confirmation.js in base template

**Expected Template Structure:**
```django
{% extends 'src/base.html' %}

{% block main_content %}
<div class="container-fluid">
  <!-- Patient list with delete buttons -->
  <table class="table">
    <tr>
      <td>{{ patient.baby_name }}</td>
      <td>
        <button type="button" class="btn btn-danger btn-sm"
                onclick="DeleteConfirmation.show('deletePatientModal')">
          <i class="fas fa-trash"></i> Delete
        </button>
      </td>
    </tr>
  </table>

  <!-- Include unified modal once -->
  {% include 'src/partials/delete_confirmation_modal.html' with
      modal_id="deletePatientModal"
      entity_type="Patient"
      entity_name=patient.baby_name
      delete_url=delete_url
      redirect_url=redirect_url
      warning_items=warning_items
      detail_items=detail_items
  %}
</div>
{% endblock %}
```

---

### Requirement: Audit Logging for All Deletions

The system SHALL log all deletion attempts (successful and failed) with comprehensive details for security audit and compliance.

**Rationale:** Medical systems require complete audit trails for regulatory compliance and security monitoring.

**Acceptance Criteria:**
- Log successful deletions with: user, entity type, entity name, entity ID, timestamp
- Log failed deletions with: user, entity type, entity ID, failure reason, timestamp
- Log invalid password attempts with: user, entity type, entity ID, timestamp
- Log permission denials with: user, entity type, entity ID, timestamp
- Use Python logging module with appropriate levels (INFO for success, WARNING for failures)
- Logs written to configured log file

#### Scenario: Audit Trail for Successful Patient Deletion

**Given** a patient deletion is successfully completed
**When** the deletion operation finishes
**Then** the system SHALL write to audit log:

```
[2025-11-07 14:23:45] INFO: Deletion successful: user=dr_smith, entity=Patient, name=Baby John, id=123
```

#### Scenario: Audit Trail for Failed Password Attempt

**Given** a user attempts deletion with incorrect password
**When** the password verification fails
**Then** the system SHALL write to audit log:

```
[2025-11-07 14:25:10] WARNING: Invalid password for deletion: user=dr_smith, entity=Patient, id=123
```

---

### Requirement: Consistent Error Handling

The system SHALL provide consistent, user-friendly error messages for all deletion failure scenarios with appropriate HTTP status codes.

**Rationale:** Clear error messages help users understand what went wrong and how to fix it, reducing support burden.

**Acceptance Criteria:**
- Use standard HTTP status codes (400, 401, 403, 404, 500)
- Provide clear, actionable error messages
- Never expose internal system details in error messages
- Display errors inline in modal (not as browser alerts)
- Support error retry without page reload

#### Scenario: Handle Network Error During Deletion

**Given** a delete modal is displayed
**And** the user has entered correct password
**When** the user clicks delete
**And** a network error occurs during AJAX request
**Then** the system SHALL:
- Catch the network error
- Display message "An error occurred during deletion. Please check your connection and try again."
- Keep modal open
- Re-enable delete button
- Allow user to retry

---

## MODIFIED Requirements

### Requirement: Patient Deletion SHALL Use Unified Modal

Patient deletion SHALL use the unified modal component with centralized JavaScript handler instead of separate confirmation pages. The `patient_delete` view SHALL accept DELETE method with JSON payload and SHALL require password verification.

**Previous Behavior:** Patient deletion required navigating to separate confirmation page at `/patient/delete/confirm/<pk>/`, then submitting form to `/patient/delete/<pk>/` OR using inline modal in edit/view pages with custom JavaScript.

**Rationale:** Consolidates patient deletion to use the new unified system, eliminating duplicate code and improving consistency.

**Acceptance Criteria:**
- Patient deletion SHALL trigger unified modal from all pages (manager, view, edit)
- The `patient_delete` view SHALL accept DELETE method with JSON payload
- The system SHALL remove `patient_delete_confirm` view and URL
- Templates SHALL use unified modal include instead of inline modals

**Changes:**
- Remove dedicated `patient_delete_confirm` view and URL
- Remove `templates/patients/delete-confirm.html` template
- Remove inline modal code from `templates/patients/edit.html` and `templates/patients/partials/patient_view.html`
- Refactor `patient_delete` view to accept DELETE method with JSON
- Update templates to use unified modal include

#### Scenario: Delete Patient from Manager Page

**Given** the patient manager page
**And** a patient record exists with ID 123
**And** the user has delete permissions
**When** user clicks delete button for the patient
**Then** the system SHALL display unified modal with patient details
**And** the user SHALL be able to enter their password
**And** upon correct password, the system SHALL delete the patient
**And** the system SHALL redirect to manager page showing success message

---

### Requirement: Video Deletion SHALL Use Unified Modal

Video deletion SHALL use the unified modal component with AJAX submission instead of full-page confirmation pages. The `video_delete` view SHALL accept DELETE method with JSON and SHALL require password verification. The system SHALL maintain business rules preventing deletion of videos used in assessments.

**Previous Behavior:** Video deletion required navigating to full-page confirmation at `/video/delete-confirm/<id>/`, reviewing details, entering password in form, and submitting POST request.

**Rationale:** Aligns video deletion with unified system, removing unnecessary page navigation and improving user experience.

**Acceptance Criteria:**
- Video deletion SHALL trigger unified modal component
- The `video_delete` view SHALL accept DELETE method with JSON (not POST)
- The system SHALL remove `video_delete_confirm` view and URL
- The system SHALL maintain business rule preventing deletion of videos used in assessments

**Changes:**
- Remove `templates/video/delete-confirm.html` template
- Remove `video_delete_confirm` view and URL
- Refactor `video_delete` view to accept DELETE method with JSON (currently POST only)
- Update video manager/view templates to use unified modal include

#### Scenario: Delete Video from Video Manager

**Given** the video manager page
**And** a video record exists with ID 456
**And** the video is not used in any assessments
**And** the user has delete permissions
**When** user clicks delete button for the video
**Then** the system SHALL display unified modal with video details
**And** upon correct password entry, the system SHALL delete the video file
**And** the system SHALL delete the video database record
**And** the system SHALL redirect to video manager with success message

---

### Requirement: All Assessment Deletions SHALL Use Unified Modal

All assessment type deletions (GMA, HINE, CDIC, DA, GPA) SHALL use the unified modal component with consistent behavior. All assessment delete views SHALL accept DELETE method with JSON and SHALL require password verification. The system SHALL remove all assessment-specific delete confirmation templates and confirmation page views.

**Previous Behavior:** Each assessment type (GMA, HINE, CDIC, DA, GPA) had separate delete confirmation template and used separate URL patterns.

**Rationale:** Eliminates duplicate templates and ensures consistent deletion behavior for all assessment types.

**Acceptance Criteria:**
- All five assessment types SHALL use unified modal for deletion
- All assessment delete views SHALL accept DELETE method with JSON
- The system SHALL remove all assessment-specific delete confirmation templates
- The system SHALL remove all `*_delete_start` confirmation page views

**Changes:**
- Remove `templates/assessment/delete-confirm.html`
- Remove `templates/hine/delete-confirm.html`
- Remove `templates/cdic_record/delete-confirm.html`
- Remove `templates/develop_assemnt/delete-confirm.html`
- Remove `templates/gpa_record/delete_confirm.html`
- Remove all `*_delete_start` views (confirmation page views)
- Refactor all `*_delete` views to accept DELETE method with JSON
- Update all assessment manager templates to use unified modal

#### Scenario: Delete GMA Assessment

**Given** a GMA assessment exists with ID 789
**And** the user is on assessment manager page
**And** the user has delete permissions
**When** user clicks delete button for the assessment
**Then** the system SHALL display unified modal with assessment details
**And** upon correct password entry, the system SHALL delete the assessment
**And** the system SHALL redirect to patient view page with success message

#### Scenario: Delete HINE Assessment

**Given** a HINE assessment exists with ID 101
**And** the user has delete permissions
**When** user initiates deletion from any page
**Then** the system SHALL use the same unified modal as GMA assessments
**And** the system SHALL follow the same deletion workflow

---

### Requirement: Attachment and Bookmark Deletion SHALL Use Unified Modal

Both attachment and bookmark deletions SHALL use the unified modal component with mandatory password verification. The `attachment_delete` and `bookmark_delete` views SHALL accept DELETE method with JSON payload. The system SHALL remove the attachment-specific confirmation template.

**Previous Behavior:** Attachments had separate confirmation template, bookmarks used basic browser confirm dialog without password verification.

**Rationale:** Adds security to bookmark deletion and consolidates attachment deletion to unified system.

**Acceptance Criteria:**
- Attachment deletion SHALL use unified modal
- Bookmark deletion SHALL use unified modal
- Both SHALL require password verification (bookmark currently has none)
- The system SHALL remove attachment-specific confirmation template

**Changes:**
- Remove `templates/attachment/delete-confirm.html`
- Remove `attachment_delete_confirm` view
- Add password verification to `bookmark_delete` view
- Refactor both views to accept DELETE method with JSON
- Update templates to use unified modal

#### Scenario: Delete Attachment with Password

**Given** an attachment exists with ID 202
**And** the user has delete permissions
**When** user clicks delete button for the attachment
**Then** the system SHALL display unified modal
**And** the system SHALL require password verification
**And** upon correct password, the system SHALL delete the attachment file
**And** the system SHALL delete the attachment database record

#### Scenario: Delete Bookmark with New Password Requirement

**Given** a bookmark exists
**And** the user owns the bookmark
**When** user initiates bookmark deletion
**Then** the system SHALL display unified modal requiring password
**And** the system SHALL NOT allow deletion without password (new requirement)
**And** upon correct password, the system SHALL delete the bookmark

---

### Requirement: User Deletion SHALL Use Unified Modal with Password

User deletion in the admin panel SHALL use the unified modal component with mandatory password verification. The `admin_user_delete` view SHALL accept DELETE method with JSON and SHALL require admin password verification. The system SHALL maintain soft delete (deactivation) behavior and SHALL prevent admins from deleting their own account.

**Previous Behavior:** User deletion in admin panel used basic browser confirm dialog and performed soft delete (deactivation) via POST without password verification.

**Rationale:** Adds security layer to user deletion while preserving existing soft delete behavior for audit trail preservation.

**Acceptance Criteria:**
- User deletion SHALL use unified modal component
- User deletion SHALL require admin password verification
- The system SHALL maintain soft delete (deactivation) logic
- The system SHALL prevent admins from deleting their own account
- The system SHALL prevent non-superusers from deleting superuser accounts

**Changes:**
- Update `admin_user_delete` view to accept DELETE method with JSON
- Update `templates/users/admin/user_list.html` to use unified modal
- Maintain soft delete logic (deactivation, not physical deletion)
- Add password verification requirement

#### Scenario: Admin Deletes User Account

**Given** an admin user is on user management page
**And** a user account exists with ID 303
**And** the user account is not the admin's own account
**When** admin clicks delete button for the user
**Then** the system SHALL display unified modal with user details
**And** upon admin entering correct password
**Then** the system SHALL deactivate (soft delete) the user account
**And** the system SHALL log the admin action
**And** the system SHALL redirect to user list with success message

#### Scenario: Prevent Admin Self-Deletion

**Given** an admin user is on user management page
**And** the admin attempts to delete their own account
**When** admin clicks delete button for their own account
**Then** the system SHALL display error message
**And** the system SHALL NOT show deletion modal
**And** the system SHALL NOT allow the deletion

---

## REMOVED Requirements

### Requirement: Separate Delete Confirmation Pages

**Previous Behavior:** Each entity type had dedicated URL and view for delete confirmation page (e.g., `/patient/delete/confirm/<pk>/`).

**Justification for Removal:** Unified modal eliminates need for separate confirmation pages, reducing navigation complexity and improving UX.

**Affected URLs:**
- `/patient/delete/confirm/<pk>/`
- `/video/delete-confirm/<id>/`
- `/assessment/delete/confirm/<pk>/`
- `/cdic/delete/confirm/<aid>/`
- `/hine/delete/confirm/<hine_id>/`
- `/da/delete/confirm/<da_id>/`
- `/gpa/delete/confirm/<gpa_id>/`
- `/attachment/delete/confirm/<pk>/`

**Migration Path:** All delete buttons now trigger modal instead of navigating to confirmation page.

---

### Requirement: Entity-Specific Delete Confirmation Templates

**Previous Behavior:** 11+ separate HTML templates for delete confirmation, one per entity type.

**Justification for Removal:** Single unified modal template replaces all entity-specific templates, eliminating duplication.

**Removed Templates:**
- `templates/patients/delete-confirm.html`
- `templates/video/delete-confirm.html`
- `templates/assessment/delete-confirm.html`
- `templates/cdic_record/delete-confirm.html`
- `templates/develop_assemnt/delete-confirm.html`
- `templates/hine/delete-confirm.html`
- `templates/gpa_record/delete_confirm.html`
- `templates/attachment/delete-confirm.html`
- Inline modals in `templates/patients/edit.html` (lines 640-686)
- Inline modals in `templates/patients/partials/patient_view.html` (lines 870+)

**Migration Path:** All references updated to use `{% include 'src/partials/delete_confirmation_modal.html' %}`.

---

### Requirement: Inline Delete Handling JavaScript

**Previous Behavior:** Delete JavaScript embedded in individual templates (e.g., `templates/patients/edit.html` lines 688-750).

**Justification for Removal:** Centralized JavaScript handler eliminates inline scripts, improving maintainability and code organization.

**Removed Code:**
- `<script>` blocks in `templates/patients/edit.html`
- `<script>` blocks in `templates/patients/partials/patient_view.html`
- Custom deletion functions per entity type

**Migration Path:** All deletion logic moved to `static/js/delete-confirmation.js`.

---

## Dependencies

### Internal Dependencies
- Bootstrap 4.6 modal component (already in use)
- jQuery 3.6 for AJAX (already in use)
- Django CSRF token handling (already implemented)
- Existing permission system
- Existing audit logging infrastructure

### External Dependencies
None - all required dependencies already in place.

---

## Testing Requirements

### Unit Tests
- Test unified modal renders with correct configuration
- Test JavaScript handler with mock AJAX
- Test each delete view with password verification
- Test permission checks for each entity type
- Test business rule validation (e.g., video with assessments)

### Integration Tests
- Test complete delete flow for each entity type
- Test with different user roles and permissions
- Test error scenarios (wrong password, no permission, etc.)
- Test cascade deletions
- Test audit log generation

### Acceptance Tests
- Manual QA checklist covering all entity types
- Test on multiple browsers and devices
- Test keyboard navigation
- Test screen reader compatibility
- Performance testing for modal load times

---

## Rollout Plan

### Phase 1: Foundation
1. Create unified modal template
2. Implement centralized JavaScript handler
3. Add CSS styling

### Phase 2: Backend Refactoring
4. Refactor patient deletion view
5. Refactor video deletion view
6. Refactor assessment deletion views (5 types)
7. Refactor attachment/bookmark deletion views
8. Refactor user deletion view

### Phase 3: Frontend Integration
9. Update all manager templates
10. Update all view templates
11. Remove old delete confirmation templates

### Phase 4: Testing & Validation
12. Run test suite
13. Manual QA
14. Performance validation

---

## Security Considerations

- **Password Verification**: Always use `user.check_password()`, never plain text comparison
- **CSRF Protection**: Include CSRF token in all AJAX DELETE requests
- **Permission Checks**: Verify permissions before password check
- **Audit Logging**: Log all deletion attempts (success and failure)
- **Rate Limiting**: Use existing rate limiting to prevent brute force
- **Session Security**: Leverage existing 1-hour session timeout

---

## Performance Impact

- **Minimal Impact**: Modal loaded once per page, JavaScript loaded globally
- **Improved UX**: AJAX calls faster than full page navigation
- **No Additional Queries**: Maintains existing database access patterns
- **Reduced Code**: Less JavaScript and HTML to parse

---

## Backward Compatibility

**Breaking Changes:**
- Old delete confirmation URLs will return 404
- Direct POST to delete endpoints will fail (must use DELETE method)

**Migration Support:**
- Document URL changes in migration guide
- Provide redirect from old URLs to entity manager pages (temporary)
- Update any bookmarks or external links

---

## Documentation Updates

- Update `CLAUDE.md` with new delete pattern
- Add developer guide: "How to Add Deletable Entity"
- Update API documentation with DELETE endpoints
- Add troubleshooting guide for common issues
