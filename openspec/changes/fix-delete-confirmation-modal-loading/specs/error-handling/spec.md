# Spec: Delete Confirmation Error Handling

## ADDED Requirements

### Requirement: Modal not found errors SHALL provide diagnostic information
**ID**: ERROR-HANDLE-001
**Priority**: Critical
**Status**: New

When a delete confirmation modal cannot be found by JavaScript, the error message SHALL provide actionable diagnostic information to help resolve the issue.

#### Scenario: Modal not found shows helpful error message
**Given** JavaScript attempts to show modal with ID "deletePatientModal42"
**And** modal with that ID does not exist in DOM
**When** DeleteConfirmation.show() is called
**Then** error message displays "Modal deletePatientModal42 not found"
**And** console logs list of available delete modals on page
**And** console logs checks jQuery availability
**And** user-friendly alert shows with refresh instruction

**Acceptance Criteria**:
- ✅ Console error includes requested modal ID
- ✅ Console lists available modal IDs on page
- ✅ Console checks for jQuery availability
- ✅ User sees friendly alert with instructions
- ✅ Error doesn't crash page JavaScript

#### Scenario: Diagnostic information aids troubleshooting
**Given** developer encounters "modal not found" error
**When** developer checks browser console
**Then** console shows which modal was requested
**And** console shows which modals are available
**And** developer can identify ID mismatch

**Acceptance Criteria**:
- ✅ Clear console logging of issue
- ✅ Lists all modals with IDs containing "Modal"
- ✅ Shows count of delete modals found
- ✅ Helps identify typos or missing modals

### Requirement: JavaScript initialization SHALL be verifiable
**ID**: ERROR-HANDLE-002
**Priority**: High
**Status**: New

DeleteConfirmation module initialization SHALL be clearly logged and verifiable for troubleshooting.

#### Scenario: Successful initialization logs to console
**Given** page loads with delete confirmation JS
**When** DeleteConfirmation.init() executes
**Then** console shows "DeleteConfirmation system initialized" message
**And** window.DeleteConfirmation object is accessible
**And** event handlers are registered

**Acceptance Criteria**:
- ✅ Initialization message logged
- ✅ window.DeleteConfirmation exists
- ✅ No initialization errors in console

#### Scenario: Initialization failure shows clear error
**Given** page loads but jQuery is not available
**When** DeleteConfirmation.js attempts to run
**Then** console shows clear error about missing jQuery
**And** module doesn't break other page scripts

**Acceptance Criteria**:
- ✅ Dependency errors are clear
- ✅ Graceful degradation if possible
- ✅ No cascading script errors

### Requirement: Password verification errors SHALL be user-friendly
**ID**: ERROR-HANDLE-003
**Priority**: High
**Status**: New

When password verification fails, error messages SHALL be clear, secure (no information leakage), and help user proceed correctly.

#### Scenario: Incorrect password shows helpful error
**Given** user enters wrong password in delete modal
**When** backend returns 401 status
**Then** error displays "Incorrect password. Please try again."
**And** password field is cleared
**And** password field receives focus
**And** modal stays open for retry

**Acceptance Criteria**:
- ✅ Clear error message
- ✅ Password field cleared automatically
- ✅ Focus returned to password field
- ✅ Modal doesn't close
- ✅ Delete button re-enabled for retry

#### Scenario: Missing password shows validation error
**Given** user clicks delete without entering password
**When** JavaScript validates input
**Then** error displays "Please enter your password"
**And** password field receives focus
**And** no backend request is made

**Acceptance Criteria**:
- ✅ Client-side validation prevents empty submission
- ✅ Clear validation message
- ✅ No unnecessary backend calls

### Requirement: Permission errors SHALL be clear and non-retryable
**ID**: ERROR-HANDLE-004
**Priority**: High
**Status**: New

When user lacks permission to delete, error SHALL clearly indicate this and not allow retry.

#### Scenario: Permission denied shows clear message
**Given** user attempts to delete record they don't own
**When** backend returns 403 status
**Then** error displays "You do not have permission to delete this record"
**And** delete button remains disabled
**And** modal can be closed to cancel

**Acceptance Criteria**:
- ✅ Clear permission error message
- ✅ Button stays disabled (no retry)
- ✅ User can cancel operation
- ✅ No confusion about why deletion failed

### Requirement: Business rule violations SHALL show entity-specific messages
**ID**: ERROR-HANDLE-005
**Priority**: High
**Status**: New

When deletion violates business rules, error message SHALL explain the specific rule that was violated.

#### Scenario: Video used in assessment shows specific error
**Given** user attempts to delete video used in 3 assessments
**When** backend validates and finds violation
**Then** error displays "Cannot delete video used in 3 assessment(s)"
**And** error explains to remove video from assessments first
**And** modal stays open showing the error

**Acceptance Criteria**:
- ✅ Specific violation explained
- ✅ Count of blocking references shown
- ✅ Remediation steps suggested
- ✅ Modal remains open for user to read

#### Scenario: Self-deletion attempt shows clear error
**Given** user attempts to delete their own account
**When** backend validates deletion
**Then** error displays "Cannot delete your own account"
**And** suggests contacting administrator
**And** operation is blocked

**Acceptance Criteria**:
- ✅ Self-deletion prevented
- ✅ Clear explanation provided
- ✅ Alternative action suggested

### Requirement: Network errors SHALL be handled gracefully
**ID**: ERROR-HANDLE-006
**Priority**: Medium
**Status**: New

Network failures during delete operations SHALL be handled with clear errors and recovery options.

#### Scenario: Network timeout shows helpful error
**Given** user submits delete confirmation
**And** network request times out
**When** fetch promise rejects with network error
**Then** error displays "Network error. Please check connection and try again."
**And** delete button is re-enabled for retry
**And** modal stays open

**Acceptance Criteria**:
- ✅ Network errors caught and handled
- ✅ User-friendly error message
- ✅ Retry is possible
- ✅ Loading state cleared

#### Scenario: Server error shows generic message
**Given** user submits delete confirmation
**And** backend returns 500 error
**When** response is processed
**Then** error displays "Server error. Please try again later."
**And** error is logged to backend
**And** user is not shown technical details

**Acceptance Criteria**:
- ✅ Generic user-facing message
- ✅ Technical details hidden from user
- ✅ Error logged for debugging
- ✅ Operation can be retried

### Requirement: CSRF token errors SHALL prompt page refresh
**ID**: ERROR-HANDLE-007
**Priority**: High
**Status**: New

When CSRF token is missing or invalid, error SHALL prompt user to refresh page to get new token.

#### Scenario: Missing CSRF token shows refresh instruction
**Given** CSRF token cannot be found in page
**When** JavaScript prepares delete request
**Then** error displays "Security token missing. Please refresh the page."
**And** delete operation is aborted
**And** no backend request is made

**Acceptance Criteria**:
- ✅ CSRF check before request
- ✅ Clear refresh instruction
- ✅ Operation aborted safely
- ✅ No partial deletion

#### Scenario: Invalid CSRF token from backend
**Given** user submits delete with expired CSRF token
**When** backend returns 403 CSRF error
**Then** error displays "Session expired. Please refresh the page."
**And** user is instructed to refresh

**Acceptance Criteria**:
- ✅ CSRF errors identified correctly
- ✅ Clear session expiry message
- ✅ Refresh instruction provided

### Requirement: Success feedback SHALL be clear and automatic
**ID**: ERROR-HANDLE-008
**Priority**: Medium
**Status**: New

Successful deletion SHALL provide clear feedback and automatic redirect to appropriate page.

#### Scenario: Successful deletion shows success message
**Given** user successfully deletes a patient
**When** backend returns success response
**Then** modal closes automatically
**And** success toast notification appears
**And** message says "Patient deleted successfully"
**And** notification auto-dismisses after 3 seconds
**And** page redirects after 1.5 seconds

**Acceptance Criteria**:
- ✅ Modal closes on success
- ✅ Success notification displayed
- ✅ Message includes entity type
- ✅ Auto-dismiss after 3s
- ✅ Redirect after 1.5s delay

#### Scenario: Success redirect goes to appropriate page
**Given** different entity types are deleted
**When** deletion succeeds
**Then** patient deletion redirects to patient manager
**And** video deletion redirects to video manager
**And** assessment deletion redirects to patient view or manager
**And** redirect URL comes from backend or default

**Acceptance Criteria**:
- ✅ Redirect URL determined by entity type
- ✅ Backend can override redirect URL
- ✅ Appropriate manager/list page shown
- ✅ Deleted item no longer visible

## MODIFIED Requirements

### Requirement: Enhanced JavaScript error handling SHALL support all scenarios
**ID**: ERROR-HANDLE-009
**Status**: Modified

Existing `DeleteConfirmation.execute()` error handling SHALL be enhanced to support all new error scenarios.

#### Scenario: Error handling covers all HTTP status codes
**Given** any HTTP error occurs during deletion
**When** error response is processed
**Then** appropriate status-specific message is shown
**And** error is logged to console for debugging
**And** UI state is reset appropriately

**Acceptance Criteria**:
- ✅ 400: Shows specific validation error
- ✅ 401: Shows password error, clears field
- ✅ 403: Shows permission error, disables retry
- ✅ 404: Shows "record not found" error
- ✅ 500: Shows generic server error
- ✅ Network: Shows connection error

## Implementation Notes

### Error Handling Flow
```javascript
// Enhanced error handling in delete-confirmation.js

_handleError: function(errorDiv, deleteBtn, spinner, message) {
    // Display error with icon
    errorDiv.html('<i class="fas fa-exclamation-circle"></i> ' +
                  this._escapeHtml(message)).show();

    // Reset UI state for retry (unless permission error)
    if (!message.includes('permission')) {
        deleteBtn.prop('disabled', false);
    }
    spinner.hide();
},

_handleSuccess: function(data, modalId, redirectUrl) {
    // Close modal
    $('#' + modalId).modal('hide');

    // Show success notification
    this._showSuccessMessage(data.message || 'Deletion successful');

    // Redirect after delay
    setTimeout(() => {
        window.location.href = data.redirect_url || redirectUrl || '/';
    }, 1500);
}
```

### Error Message Standards
- **Client-side**: Specific, actionable, guides user
- **User-facing**: Clear, non-technical, helpful
- **Console logs**: Technical details for debugging
- **Security**: No information leakage in error messages

### Testing Requirements
- Test each error scenario individually
- Verify error messages are appropriate
- Confirm UI state reset correctly
- Check that retry works after errors
- Validate console logging is helpful

## Related Requirements
- See `asset-loading/spec.md` for initialization requirements
- See `modal-context-generation/spec.md` for modal display requirements
