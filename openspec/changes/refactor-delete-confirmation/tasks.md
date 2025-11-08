# Tasks: Refactor Delete Confirmation System

**Change ID:** `refactor-delete-confirmation`

## Task Organization

Tasks are organized into phases for systematic implementation. Each task is small, verifiable, and delivers incremental progress. Dependencies are noted where tasks must run sequentially.

---

## Phase 1: Foundation Setup

### Task 1: Create Unified Modal Template
**Deliverable:** `templates/src/partials/delete_confirmation_modal.html`

**Steps:**
1. Create file at `templates/src/partials/delete_confirmation_modal.html`
2. Implement Bootstrap 4.6 modal structure with:
   - Modal header with dynamic entity type
   - Warning section with configurable list
   - Entity details display section
   - Password input field
   - Error message display area
   - Footer with Cancel and Delete buttons
3. Use Django template variables for configuration:
   - `modal_id`: Unique modal ID
   - `entity_type`: Display name (e.g., "Patient", "Video")
   - `entity_name`: Specific entity identifier
   - `delete_url`: Backend DELETE endpoint
   - `redirect_url`: Post-deletion redirect
   - `warning_items`: List of warning messages
   - `detail_items`: Dict of entity details
4. Add proper ARIA attributes for accessibility
5. Add data attributes for JavaScript integration

**Validation:**
- [ ] Template renders without errors
- [ ] Modal displays correctly when included in test page
- [ ] All configuration variables work as expected
- [ ] ARIA attributes present and valid
- [ ] Mobile responsive layout

**Dependencies:** None

---

### Task 2: Implement Centralized JavaScript Handler
**Deliverable:** `static/js/delete-confirmation.js`

**Steps:**
1. Create file at `static/js/delete-confirmation.js`
2. Implement singleton module pattern
3. Create `DeleteConfirmation.show(modalId, config)` function
4. Create `DeleteConfirmation.execute(button)` function with:
   - Client-side password validation
   - Loading state management
   - AJAX DELETE request with JSON payload
   - CSRF token handling
   - Success handling (hide modal, show message, redirect)
   - Error handling (display inline, re-enable button)
5. Create `DeleteConfirmation.init()` for event handlers:
   - Enter key in password field
   - Clear error on password input
6. Add auto-initialization on DOMContentLoaded
7. Add comprehensive JSDoc comments

**Validation:**
- [ ] JavaScript loads without errors
- [ ] Public API accessible via `window.DeleteConfirmation`
- [ ] Mock AJAX calls work correctly
- [ ] Error handling displays messages properly
- [ ] Loading states visible
- [ ] Keyboard navigation works (Enter to submit)

**Dependencies:** Task 1 (modal template)

---

### Task 3: Add Shared CSS Styling
**Deliverable:** `static/css/delete-confirmation.css` (or add to existing CSS)

**Steps:**
1. Add styling for modal error messages
2. Add loading spinner animations
3. Add entity-info section styling
4. Ensure consistency with AdminLTE theme
5. Add mobile responsive adjustments

**Validation:**
- [ ] Styles apply correctly to modal
- [ ] Error messages styled appropriately
- [ ] Loading spinners animate smoothly
- [ ] Consistent with AdminLTE design language
- [ ] Mobile layout works well

**Dependencies:** Task 1 (modal template)

---

### Task 4: Update Base Template with JavaScript
**Deliverable:** Modified `templates/src/base.html`

**Steps:**
1. Add `<script src="{% static 'js/delete-confirmation.js' %}"></script>` to base template
2. Place after jQuery and Bootstrap JS
3. Ensure CSRF token meta tag present in head

**Validation:**
- [ ] JavaScript loads on all pages using base template
- [ ] No console errors
- [ ] CSRF token accessible to JavaScript

**Dependencies:** Task 2 (JavaScript handler)

---

## Phase 2: Backend Standardization

### Task 5: Create Delete Helper Utilities
**Deliverable:** `ndas/custom_codes/delete_helpers.py`

**Steps:**
1. Create file at `ndas/custom_codes/delete_helpers.py`
2. Implement `has_delete_permission(user, entity)` function
3. Implement `validate_can_delete(entity)` function with business rules
4. Implement `get_entity_display_name(entity)` function
5. Implement `get_redirect_url(entity_type)` function
6. Add comprehensive docstrings and type hints

**Validation:**
- [ ] All helper functions work correctly
- [ ] Business rules properly enforced
- [ ] Permissions checked accurately
- [ ] Unit tests pass

**Dependencies:** None (can run in parallel with Phase 1)

---

### Task 6: Refactor Patient Delete View
**Deliverable:** Modified `patients/views.py::patient_delete`

**Steps:**
1. Update `patient_delete` to accept DELETE method only
2. Add JSON request body parsing
3. Implement password verification with `user.check_password()`
4. Add permission checks using helper function
5. Add business rule validation
6. Implement audit logging for success/failure
7. Return JSON response with standard format
8. Remove or deprecate `patient_delete_confirm` view
9. Update `patients/urls.py` to remove confirm URL

**Validation:**
- [ ] DELETE request with valid password succeeds
- [ ] DELETE request with invalid password returns 401
- [ ] Permission checks work correctly
- [ ] Audit logs generated
- [ ] JSON response format correct
- [ ] Old confirm URL returns 404

**Dependencies:** Task 5 (helper utilities)

---

### Task 7: Refactor Video Delete View
**Deliverable:** Modified `video/views.py::video_delete`

**Steps:**
1. Update `video_delete` to accept DELETE method (currently POST)
2. Change from form POST to JSON request body
3. Add password verification
4. Update permission checks
5. Keep business rule check (assessments using video)
6. Add audit logging
7. Return JSON response
8. Remove `video_delete_confirm` view
9. Update `video/urls.py` to remove confirm URL

**Validation:**
- [ ] DELETE request works correctly
- [ ] Cannot delete video with active assessments
- [ ] Password verification required
- [ ] JSON response format correct
- [ ] Old confirm URL returns 404

**Dependencies:** Task 5 (helper utilities)

---

### Task 8: Refactor GMA Assessment Delete View
**Deliverable:** Modified `patients/views.py::assessment_delete`

**Steps:**
1. Update `assessment_delete` to accept DELETE method
2. Add JSON request parsing
3. Add password verification
4. Add permission checks
5. Add audit logging
6. Return JSON response
7. Remove `assessment_delete_start` view
8. Update URLs

**Validation:**
- [ ] DELETE request works
- [ ] Password required
- [ ] Permissions checked
- [ ] JSON response correct

**Dependencies:** Task 5 (helper utilities)

---

### Task 9: Refactor HINE Assessment Delete View
**Deliverable:** Modified `patients/views.py::hine_assessment_delete`

**Steps:**
1. Update to accept DELETE method
2. Add JSON parsing and password verification
3. Add permission checks and audit logging
4. Return JSON response
5. Remove `hine_assessment_delete_start` view
6. Update URLs

**Validation:**
- [ ] DELETE request works
- [ ] Password verification in place
- [ ] Audit logs generated

**Dependencies:** Task 5 (helper utilities)

---

### Task 10: Refactor CDIC Assessment Delete View
**Deliverable:** Modified `patients/views.py::cdic_assessment_delete`

**Steps:**
1. Update to accept DELETE method
2. Add JSON parsing and password verification
3. Add permission checks and audit logging
4. Return JSON response
5. Remove `cdic_assessment_delete_start` view
6. Update URLs

**Validation:**
- [ ] DELETE request works
- [ ] Password verification in place
- [ ] Audit logs generated

**Dependencies:** Task 5 (helper utilities)

---

### Task 11: Refactor Developmental Assessment Delete View
**Deliverable:** Modified `patients/views.py::da_assessment_delete`

**Steps:**
1. Update to accept DELETE method
2. Add JSON parsing and password verification
3. Add permission checks and audit logging
4. Return JSON response
5. Remove `da_assessment_delete_start` view
6. Update URLs

**Validation:**
- [ ] DELETE request works
- [ ] Password verification in place
- [ ] Audit logs generated

**Dependencies:** Task 5 (helper utilities)

---

### Task 12: Refactor GPA Delete View
**Deliverable:** Modified `patients/views.py::gpa_delete`

**Steps:**
1. Update to accept DELETE method
2. Add JSON parsing and password verification
3. Add permission checks and audit logging
4. Return JSON response
5. Remove `gpa_delete_start` view
6. Update URLs

**Validation:**
- [ ] DELETE request works
- [ ] Password verification in place
- [ ] Audit logs generated

**Dependencies:** Task 5 (helper utilities)

---

### Task 13: Refactor Attachment Delete View
**Deliverable:** Modified `patients/views.py::attachment_delete`

**Steps:**
1. Update to accept DELETE method
2. Add JSON parsing and password verification
3. Add permission checks and audit logging
4. Return JSON response
5. Remove `attachment_delete_confirm` view
6. Update URLs

**Validation:**
- [ ] DELETE request works
- [ ] File deletion handled properly
- [ ] Password verification in place

**Dependencies:** Task 5 (helper utilities)

---

### Task 14: Refactor Bookmark Delete View
**Deliverable:** Modified `patients/views.py::bookmark_delete`

**Steps:**
1. Update to accept DELETE method
2. Add JSON parsing and password verification (currently has none)
3. Add audit logging
4. Return JSON response

**Validation:**
- [ ] DELETE request works
- [ ] Password verification added
- [ ] JSON response correct

**Dependencies:** Task 5 (helper utilities)

---

### Task 15: Refactor User Delete View (Admin)
**Deliverable:** Modified `users/views.py::admin_user_delete`

**Steps:**
1. Update to accept DELETE method
2. Add JSON parsing and password verification
3. Maintain soft delete logic (deactivation)
4. Add enhanced audit logging
5. Return JSON response
6. Keep existing safeguards (can't delete self, permission checks)

**Validation:**
- [ ] DELETE request works
- [ ] Soft delete (deactivation) still functions
- [ ] Cannot delete own account
- [ ] Password verification required
- [ ] Superuser protections work

**Dependencies:** Task 5 (helper utilities)

---

## Phase 3: Frontend Integration

### Task 16: Update Patient Manager Template
**Deliverable:** Modified `templates/patients/manager.html` or equivalent

**Steps:**
1. Add unified modal include at bottom of template
2. Configure modal with patient-specific details
3. Update delete buttons to trigger modal instead of navigate
4. Remove any inline delete JavaScript
5. Test with multiple patients

**Validation:**
- [ ] Modal displays on delete button click
- [ ] Patient details show correctly
- [ ] Delete operation works end-to-end
- [ ] Redirects to manager after deletion

**Dependencies:** Tasks 1-4 (foundation), Task 6 (patient delete view)

---

### Task 17: Update Patient View/Edit Templates
**Deliverable:** Modified `templates/patients/partials/patient_view.html` and `templates/patients/edit.html`

**Steps:**
1. Remove inline delete modal code (lines 640-686 in edit.html, 870+ in patient_view.html)
2. Remove inline JavaScript for deletion (lines 688-750 in edit.html)
3. Add unified modal include
4. Update delete buttons to trigger unified modal
5. Test from both view and edit pages

**Validation:**
- [ ] Inline modal code removed
- [ ] Inline JavaScript removed
- [ ] Unified modal works from edit page
- [ ] Unified modal works from view page
- [ ] No broken functionality

**Dependencies:** Tasks 1-4 (foundation), Task 6 (patient delete view)

---

### Task 18: Update Video Manager/View Templates
**Deliverable:** Modified `templates/video/manager.html` and `templates/video/view.html`

**Steps:**
1. Add unified modal include
2. Configure with video-specific warnings (check assessments)
3. Update delete buttons
4. Remove references to old delete-confirm page

**Validation:**
- [ ] Modal displays video details
- [ ] Cannot delete video with assessments
- [ ] Delete works for videos without assessments
- [ ] Proper redirect after deletion

**Dependencies:** Tasks 1-4 (foundation), Task 7 (video delete view)

---

### Task 19: Update Assessment Manager Templates
**Deliverable:** Modified assessment manager templates for all types (GMA, HINE, CDIC, DA, GPA)

**Steps:**
1. For each assessment type template:
   - Add unified modal include
   - Configure with assessment-specific details
   - Update delete buttons
   - Remove references to old delete-confirm pages
2. Update templates:
   - `templates/assessment/manager.html`
   - `templates/hine/manager.html`
   - `templates/cdic_record/manager.html`
   - `templates/develop_assemnt/manager.html`
   - `templates/gpa_record/manager.html`

**Validation (per type):**
- [ ] Modal displays assessment details
- [ ] Delete operation works
- [ ] Proper redirect after deletion
- [ ] No broken links

**Dependencies:** Tasks 1-4 (foundation), Tasks 8-12 (assessment delete views)

---

### Task 20: Update Attachment and Bookmark Templates
**Deliverable:** Modified `templates/attachment/manager.html` and `templates/bookmark/manager.html`

**Steps:**
1. Add unified modal to attachment manager
2. Add unified modal to bookmark manager
3. Update delete buttons for both
4. Configure modals with appropriate details

**Validation:**
- [ ] Attachment deletion works with modal
- [ ] Bookmark deletion works with modal
- [ ] Password required for both

**Dependencies:** Tasks 1-4 (foundation), Tasks 13-14 (attachment/bookmark delete views)

---

### Task 21: Update User Admin Template
**Deliverable:** Modified `templates/users/admin/user_list.html`

**Steps:**
1. Replace inline browser confirm with unified modal
2. Add modal include at bottom
3. Update delete button/form to trigger modal
4. Configure with user details

**Validation:**
- [ ] Modal displays user details
- [ ] Soft delete (deactivation) works
- [ ] Cannot delete own account
- [ ] Password verification required

**Dependencies:** Tasks 1-4 (foundation), Task 15 (user delete view)

---

## Phase 4: Cleanup

### Task 22: Remove Old Delete Confirmation Templates
**Deliverable:** Deleted template files

**Steps:**
1. Delete the following template files:
   - `templates/patients/delete-confirm.html`
   - `templates/video/delete-confirm.html`
   - `templates/assessment/delete-confirm.html`
   - `templates/cdic_record/delete-confirm.html`
   - `templates/develop_assemnt/delete-confirm.html`
   - `templates/hine/delete-confirm.html`
   - `templates/gpa_record/delete_confirm.html`
   - `templates/attachment/delete-confirm.html`
2. Search codebase for any remaining references to deleted templates
3. Update any found references

**Validation:**
- [ ] All old templates deleted
- [ ] No broken template references remain
- [ ] Grep search shows no lingering references
- [ ] Application runs without template errors

**Dependencies:** All frontend integration tasks (16-21) must be complete

**Command for validation:**
```bash
rg -i "delete-confirm\.html" templates/
```

---

### Task 23: Remove Deprecated Delete JavaScript Files
**Deliverable:** Deleted or cleaned up JavaScript files

**Steps:**
1. Delete `static/js/patient-deletion.js` (replaced by unified handler)
2. Search for any other entity-specific delete JavaScript
3. Update any references in templates

**Validation:**
- [ ] Old JavaScript files deleted
- [ ] No broken script references
- [ ] No console errors

**Dependencies:** All frontend integration tasks complete

---

## Phase 5: Testing & Validation

### Task 24: Backend Unit Tests
**Deliverable:** Test suite for delete views

**Steps:**
1. Create test file: `tests/test_delete_views.py`
2. Write tests for each entity delete view:
   - Test successful deletion with valid password
   - Test rejection with invalid password (401)
   - Test rejection with no permission (403)
   - Test rejection with missing password (400)
   - Test business rule violations (400)
3. Write tests for helper functions
4. Run test suite: `python manage.py test`

**Validation:**
- [ ] All tests pass
- [ ] 100% code coverage for delete views
- [ ] Edge cases covered

**Dependencies:** All backend refactoring tasks (6-15) complete

---

### Task 25: Frontend Integration Tests
**Deliverable:** Playwright E2E tests

**Steps:**
1. Create test file: `tests/e2e/test_delete_modal.spec.js`
2. Write tests for:
   - Modal display on button click
   - Password validation
   - Successful deletion flow
   - Error message display
   - Cancel button functionality
   - Keyboard navigation (Enter, Esc)
3. Test on multiple browsers
4. Run: `npx playwright test`

**Validation:**
- [ ] All E2E tests pass
- [ ] Tests pass on Chrome, Firefox, Safari
- [ ] Mobile viewport tests pass

**Dependencies:** All frontend integration tasks (16-21) complete

---

### Task 26: Manual QA Checklist
**Deliverable:** QA report

**Steps:**
1. Test each entity type deletion:
   - [ ] Patient deletion from manager
   - [ ] Patient deletion from view page
   - [ ] Patient deletion from edit page
   - [ ] Video deletion from manager
   - [ ] Video deletion (with/without assessments)
   - [ ] GMA assessment deletion
   - [ ] HINE assessment deletion
   - [ ] CDIC assessment deletion
   - [ ] Developmental assessment deletion
   - [ ] GPA assessment deletion
   - [ ] Attachment deletion
   - [ ] Bookmark deletion
   - [ ] User deletion (admin)
2. Test error scenarios:
   - [ ] Empty password
   - [ ] Wrong password
   - [ ] No permission
   - [ ] Network error
3. Test UX:
   - [ ] Modal appearance consistent
   - [ ] Loading states visible
   - [ ] Success messages clear
   - [ ] Error messages helpful
   - [ ] Keyboard navigation works
4. Test on devices:
   - [ ] Desktop (1920x1080)
   - [ ] Tablet (768x1024)
   - [ ] Mobile (375x667)
5. Test browsers:
   - [ ] Chrome
   - [ ] Firefox
   - [ ] Safari
   - [ ] Edge

**Validation:**
- [ ] All manual tests pass
- [ ] No regressions found
- [ ] UX meets requirements

**Dependencies:** All implementation tasks complete

---

### Task 27: Performance Validation
**Deliverable:** Performance report

**Steps:**
1. Measure modal load time (should be <100ms)
2. Measure AJAX deletion time (should be <2s)
3. Measure page load impact of delete-confirmation.js (should be <50ms)
4. Test with slow network (3G simulation)
5. Test with 100+ entities on manager page

**Validation:**
- [ ] Modal loads quickly
- [ ] Deletion completes in reasonable time
- [ ] No performance regression
- [ ] Works acceptably on slow connections

**Dependencies:** All implementation tasks complete

---

### Task 28: Accessibility Audit
**Deliverable:** Accessibility report

**Steps:**
1. Run axe DevTools on pages with delete modals
2. Test with keyboard navigation only
3. Test with screen reader (NVDA or VoiceOver)
4. Verify ARIA labels correct
5. Check focus management
6. Verify color contrast

**Validation:**
- [ ] No axe violations
- [ ] Keyboard navigation complete
- [ ] Screen reader announces correctly
- [ ] Focus management proper
- [ ] WCAG 2.1 AA compliant

**Dependencies:** All implementation tasks complete

---

## Phase 6: Documentation

### Task 29: Update CLAUDE.md
**Deliverable:** Modified `CLAUDE.md`

**Steps:**
1. Add section on unified delete confirmation system
2. Document how to add deletable entity (3-step process)
3. Update examples with new pattern
4. Remove references to old delete-confirm templates

**Validation:**
- [ ] Documentation clear and accurate
- [ ] Examples work correctly
- [ ] No outdated information

**Dependencies:** All implementation complete

---

### Task 30: Create Developer Guide
**Deliverable:** New file `docs/delete-confirmation-guide.md`

**Steps:**
1. Document architecture of unified system
2. Provide code examples for:
   - Adding new deletable entity
   - Customizing modal warnings
   - Implementing business rules
3. Document troubleshooting common issues
4. Add FAQs

**Validation:**
- [ ] Guide comprehensive
- [ ] Examples accurate
- [ ] Helpful for future developers

**Dependencies:** All implementation complete

---

## Task Summary

**Total Tasks:** 30

**Phase Breakdown:**
- Phase 1 (Foundation): 4 tasks
- Phase 2 (Backend): 11 tasks
- Phase 3 (Frontend): 6 tasks
- Phase 4 (Cleanup): 2 tasks
- Phase 5 (Testing): 5 tasks
- Phase 6 (Documentation): 2 tasks

**Parallelization Opportunities:**
- Phase 1 tasks can mostly run in parallel
- Phase 2 backend tasks can run in parallel after Task 5
- Phase 3 frontend tasks can run in parallel after Phase 1 & 2 complete
- Testing tasks can run in parallel after implementation complete

**Critical Path:**
1. Tasks 1-4 (Foundation) →
2. Task 5 (Helpers) →
3. Any backend refactor (Tasks 6-15) + corresponding frontend integration (Tasks 16-21) →
4. Testing & Cleanup

**Estimated Timeline:**
- Phase 1: 2-4 hours
- Phase 2: 6-8 hours (parallelizable)
- Phase 3: 4-6 hours (parallelizable)
- Phase 4: 1 hour
- Phase 5: 3-4 hours
- Phase 6: 1-2 hours
- **Total: ~17-25 hours**

## Validation Commands

**Check for old template references:**
```bash
rg -i "delete-confirm" templates/
rg -i "delete_confirm" templates/
```

**Check for old JavaScript:**
```bash
rg -i "patient-deletion\.js" .
```

**Run tests:**
```bash
python manage.py test
npx playwright test
```

**Check audit logs:**
```bash
tail -f logs/django.log | grep -i deletion
```

**Validate all deletions work:**
```bash
# For each entity type, test:
# 1. Valid password → success
# 2. Invalid password → 401
# 3. No permission → 403
# 4. Business rule violation → 400
```
