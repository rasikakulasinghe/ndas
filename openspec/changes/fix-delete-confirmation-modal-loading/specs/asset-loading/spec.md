# Spec: Delete Confirmation Asset Loading

## ADDED Requirements

### Requirement: Delete confirmation assets SHALL load on all authenticated pages
**ID**: ASSET-LOAD-001
**Priority**: Critical
**Status**: New

The delete confirmation JavaScript and CSS files SHALL be properly loaded on all pages where authenticated users can access delete functionality.

#### Scenario: Assets load via base template inheritance
**Given** a user is logged in and viewing any application page
**When** the page loads
**Then** the delete-confirmation.js file is loaded and executed
**And** the delete-confirmation.css file is applied
**And** the DeleteConfirmation JavaScript module is initialized
**And** console shows "DeleteConfirmation system initialized" message

**Acceptance Criteria**:
- ✅ JS file loads after jQuery and Bootstrap
- ✅ CSS file loads in document head
- ✅ window.DeleteConfirmation object exists
- ✅ No JavaScript errors in console during initialization

#### Scenario: Asset loading verified on patient management pages
**Given** user navigates to patient edit page
**When** the page finishes loading
**Then** browser console shows DeleteConfirmation initialized
**And** delete button click handler is attached
**And** modal functions are available

**Acceptance Criteria**:
- ✅ Patient edit page loads assets correctly
- ✅ Patient view page loads assets correctly
- ✅ Patient manager page loads assets correctly

#### Scenario: Asset loading verified on video management pages
**Given** user navigates to video manager page
**When** the page finishes loading
**Then** delete confirmation assets are loaded
**And** JavaScript initialization completes successfully

**Acceptance Criteria**:
- ✅ Video view page loads assets
- ✅ Video edit page loads assets
- ✅ Video manager page loads assets

#### Scenario: Asset loading verified on assessment pages
**Given** user navigates to any assessment page (GMA, HINE, CDIC, GPA, Developmental)
**When** the page finishes loading
**Then** delete confirmation assets are loaded
**And** modal functionality is available

**Acceptance Criteria**:
- ✅ All 5 assessment types load assets correctly
- ✅ Assessment manager pages load assets
- ✅ Assessment view pages load assets

### Requirement: Asset loading MUST NOT break existing functionality
**ID**: ASSET-LOAD-002
**Priority**: Critical
**Status**: New

Changes to asset loading in base templates MUST NOT cause regressions in other page functionality.

#### Scenario: Other page JavaScript continues to work
**Given** delete confirmation assets are loaded in base template
**When** user interacts with non-delete features
**Then** all existing functionality continues to work
**And** no JavaScript conflicts occur
**And** page performance is not degraded

**Acceptance Criteria**:
- ✅ Form submissions work correctly
- ✅ HTMX interactions function properly
- ✅ Select2 dropdowns operate normally
- ✅ Video player controls work
- ✅ No console errors from script conflicts

#### Scenario: CSS styles do not conflict
**Given** delete-confirmation.css is loaded on all pages
**When** user views pages without delete functionality
**Then** no visual regressions occur
**And** page layout remains correct

**Acceptance Criteria**:
- ✅ No style conflicts with AdminLTE
- ✅ No layout shifts from CSS additions
- ✅ Modal styles only apply to delete modals

### Requirement: Asset loading order MUST be correct
**ID**: ASSET-LOAD-003
**Priority**: High
**Status**: New

Delete confirmation assets MUST load after their dependencies (jQuery, Bootstrap) to ensure proper initialization.

#### Scenario: JavaScript loads in correct dependency order
**Given** page is loading
**When** scripts are parsed and executed
**Then** jQuery loads first
**Then** Bootstrap loads second
**Then** delete-confirmation.js loads third
**And** DeleteConfirmation.init() executes successfully

**Acceptance Criteria**:
- ✅ No "$ is not defined" errors
- ✅ No "Bootstrap is not defined" errors
- ✅ DeleteConfirmation module initializes correctly

#### Scenario: CSS loads before page render
**Given** page is loading
**When** browser parses HTML head
**Then** delete-confirmation.css loads in head section
**And** styles are applied before first paint
**And** no flash of unstyled content occurs

**Acceptance Criteria**:
- ✅ CSS in document head
- ✅ No FOUC (Flash of Unstyled Content)
- ✅ Modal appears styled on first display

## Implementation Notes

### Template Structure
```django
<!-- templates/src/basic_plane.html -->
<head>
  <!-- Existing CSS -->
  <link rel="stylesheet" href="{% static 'css/delete-confirmation.css' %}">
</head>
<body>
  <!-- Content -->

  <!-- Scripts at end of body -->
  <script src="{% static 'js/jquery.min.js' %}"></script>
  <script src="{% static 'js/bootstrap.bundle.min.js' %}"></script>
  <script src="{% static 'js/delete-confirmation.js' %}"></script>
</body>
```

### Verification Commands
```bash
# Check if files exist
ls static/js/delete-confirmation.js
ls static/css/delete-confirmation.css

# Collect static files
python manage.py collectstatic --noinput

# Test in browser console
console.log(window.DeleteConfirmation);
```

### Testing Matrix
| Page Type | Template | Asset Loading | Modal Function |
|-----------|----------|---------------|----------------|
| Patient Edit | patients/edit.html | ✅ | ✅ |
| Patient Manager | patients/manager.html | ✅ | ✅ |
| Video View | video/view.html | ✅ | ✅ |
| Assessment View | assessment/view.html | ✅ | ✅ |
| CDIC Manager | cdic_record/manager.html | ✅ | ✅ |
| Attachment View | attachment/view.html | ✅ | ✅ |
| User Admin | users/admin/user_list.html | ✅ | ✅ |

## Related Requirements
- See `modal-context-generation/spec.md` for modal content requirements
- See `error-handling/spec.md` for error handling requirements
