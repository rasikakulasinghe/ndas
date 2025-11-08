# Design: Unified Delete Confirmation System

**Change ID:** `refactor-delete-confirmation`

## Architecture Overview

The unified delete confirmation system consists of three layers that work together to provide consistent, secure deletion across all NDAS entities.

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Unified Modal Component (Bootstrap 4.6)             │   │
│  │  - templates/src/partials/delete_confirmation_modal  │   │
│  │  - Configurable via data attributes                  │   │
│  │  - Password input + warning display                  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Interaction Layer                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Centralized JavaScript Handler                      │   │
│  │  - static/js/delete-confirmation.js                  │   │
│  │  - AJAX deletion with password                       │   │
│  │  - Error handling + loading states                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      Backend Layer                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Standardized Delete Views                           │   │
│  │  - Accept DELETE method with JSON                    │   │
│  │  - Verify password with user.check_password()        │   │
│  │  - Return JSON {success, message, redirect_url}      │   │
│  │  - Audit logging for all operations                  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. Unified Modal Template

**File:** `templates/src/partials/delete_confirmation_modal.html`

**Design Principles:**
- Single reusable component included via `{% include %}`
- Configuration via context variables, NOT hardcoded content
- Bootstrap 4.6 standard modal structure
- Accessibility: proper ARIA labels, keyboard navigation
- Responsive: works on mobile and desktop

**Configuration Interface:**
```django
{% include 'src/partials/delete_confirmation_modal.html' with
    modal_id="deletePatientModal"
    entity_type="Patient"
    entity_name=patient.baby_name
    delete_url=delete_url
    redirect_url=redirect_url
    warning_items=warning_items
    detail_items=detail_items
%}
```

**Modal Structure:**
```html
<div class="modal fade" id="{{ modal_id }}" tabindex="-1" role="dialog">
  <div class="modal-dialog" role="document">
    <div class="modal-content">
      <!-- Header with entity type -->
      <div class="modal-header bg-danger text-white">
        <h5><i class="fas fa-exclamation-triangle"></i> Confirm {{ entity_type }} Deletion</h5>
      </div>

      <!-- Body with warnings, details, password -->
      <div class="modal-body">
        <!-- Dynamic warning section -->
        <div class="alert alert-danger">
          <h6><strong>Warning: This action cannot be undone!</strong></h6>
          <ul>
            {% for item in warning_items %}
            <li>{{ item }}</li>
            {% endfor %}
          </ul>
        </div>

        <!-- Entity details display -->
        <div class="entity-info bg-light p-3 rounded">
          <h6><strong>{{ entity_type }} Details:</strong></h6>
          {% for key, value in detail_items.items %}
          <p><strong>{{ key }}:</strong> {{ value }}</p>
          {% endfor %}
        </div>

        <!-- Password verification -->
        <div class="mt-3">
          <label for="deletePassword"><strong>Enter your password to confirm:</strong></label>
          <input type="password" class="form-control" id="deletePassword"
                 placeholder="Enter your password" required>
          <div id="deleteError" class="text-danger mt-2" style="display: none;"></div>
        </div>
      </div>

      <!-- Footer with actions -->
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button>
        <button type="button" class="btn btn-danger" id="confirmDeleteBtn"
                data-delete-url="{{ delete_url }}"
                data-redirect-url="{{ redirect_url }}"
                onclick="DeleteConfirmation.execute(this)">
          <span class="spinner-border spinner-border-sm" style="display: none;"></span>
          <i class="fas fa-trash-alt"></i> Delete {{ entity_type }}
        </button>
      </div>
    </div>
  </div>
</div>
```

**Why This Design:**
- **Reusable**: Works for any entity type with simple context variables
- **Flexible**: Warning items and details customize per entity
- **Secure**: Password field always present
- **Consistent**: Same look/feel across all deletions
- **Maintainable**: One file to update for modal changes

### 2. Centralized JavaScript Handler

**File:** `static/js/delete-confirmation.js`

**Design Pattern:** Singleton module with public API

```javascript
/**
 * NDAS Unified Delete Confirmation System
 * Provides consistent deletion behavior with password verification
 */
(function() {
    'use strict';

    window.DeleteConfirmation = {
        /**
         * Show deletion modal with entity-specific configuration
         * @param {string} modalId - Modal DOM ID
         * @param {Object} config - Configuration object
         */
        show: function(modalId, config) {
            const modal = $('#' + modalId);
            modal.data('delete-config', config);
            modal.modal('show');
            $('#deletePassword').val('');
            $('#deleteError').hide();
        },

        /**
         * Execute deletion after password verification
         * @param {HTMLElement} button - Delete button element with data attributes
         */
        execute: function(button) {
            const deleteUrl = button.dataset.deleteUrl;
            const redirectUrl = button.dataset.redirectUrl;
            const password = $('#deletePassword').val();
            const deleteBtn = $(button);
            const spinner = deleteBtn.find('.spinner-border');
            const errorDiv = $('#deleteError');

            // Client-side validation
            if (!password) {
                errorDiv.text('Please enter your password').show();
                return;
            }

            // Show loading state
            deleteBtn.prop('disabled', true);
            spinner.show();
            errorDiv.hide();

            // Make AJAX DELETE request
            fetch(deleteUrl, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ password: password })
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.message || data.error || 'Delete operation failed');
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Close modal
                    $('.modal').modal('hide');

                    // Show success message
                    this._showSuccessMessage(data.message);

                    // Redirect after delay
                    setTimeout(() => {
                        window.location.href = data.redirect_url || redirectUrl;
                    }, 1500);
                } else {
                    throw new Error(data.message || 'Delete operation failed');
                }
            })
            .catch(error => {
                errorDiv.text(error.message || 'An error occurred during deletion').show();
            })
            .finally(() => {
                deleteBtn.prop('disabled', false);
                spinner.hide();
            });
        },

        /**
         * Show success alert
         * @private
         */
        _showSuccessMessage: function(message) {
            document.body.insertAdjacentHTML('afterbegin',
                `<div class="alert alert-success alert-dismissible m-3">
                    <button type="button" class="close" data-dismiss="alert">&times;</button>
                    <i class="fas fa-check-circle"></i> ${message}
                </div>`
            );
        },

        /**
         * Initialize event handlers
         */
        init: function() {
            // Handle Enter key in password field
            $(document).on('keypress', '#deletePassword', function(e) {
                if (e.which === 13) {
                    $('#confirmDeleteBtn').click();
                }
            });

            // Clear error when typing
            $(document).on('input', '#deletePassword', function() {
                $('#deleteError').hide();
            });
        }
    };

    // Auto-initialize when DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => DeleteConfirmation.init());
    } else {
        DeleteConfirmation.init();
    }

})();
```

**Why This Design:**
- **Separation of Concerns**: UI logic separate from backend communication
- **Reusable**: One handler for all entity types
- **Testable**: Clear public API, isolated functions
- **Error Handling**: Comprehensive error states with user feedback
- **Progressive Enhancement**: Works with minimal configuration

### 3. Backend View Pattern

**Common Pattern for All Delete Views:**

```python
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import json
import logging

logger = logging.getLogger(__name__)

@login_required(login_url="user-login")
@require_http_methods(["DELETE"])
def entity_delete(request, pk):
    """
    Unified delete endpoint with password verification

    Expected JSON payload: {"password": "user_password"}
    Returns: {"success": bool, "message": str, "redirect_url": str}
    """
    try:
        # 1. Retrieve entity
        entity = get_object_or_404(EntityModel, pk=pk)

        # 2. Check permissions
        if not has_delete_permission(request.user, entity):
            logger.warning(
                f"Unauthorized deletion attempt: user={request.user.username}, "
                f"entity={entity.__class__.__name__}, id={pk}"
            )
            return JsonResponse({
                "success": False,
                "error": "Permission denied",
                "message": "You do not have permission to delete this record."
            }, status=403)

        # 3. Verify password
        try:
            data = json.loads(request.body)
            password = data.get('password', '')
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "error": "Invalid request",
                "message": "Invalid request format."
            }, status=400)

        if not password:
            return JsonResponse({
                "success": False,
                "error": "Password required",
                "message": "Password is required to confirm deletion."
            }, status=400)

        if not request.user.check_password(password):
            logger.warning(
                f"Invalid password for deletion: user={request.user.username}, "
                f"entity={entity.__class__.__name__}, id={pk}"
            )
            return JsonResponse({
                "success": False,
                "error": "Invalid password",
                "message": "Incorrect password. Please try again."
            }, status=401)

        # 4. Check business rules (e.g., cascade restrictions)
        validation_result = validate_can_delete(entity)
        if not validation_result['can_delete']:
            return JsonResponse({
                "success": False,
                "error": "Cannot delete",
                "message": validation_result['reason']
            }, status=400)

        # 5. Store info for logging and response
        entity_name = get_entity_display_name(entity)
        entity_type = entity.__class__.__name__

        # 6. Perform deletion
        entity.delete()

        # 7. Audit log
        logger.info(
            f"Deletion successful: user={request.user.username}, "
            f"entity={entity_type}, name={entity_name}, id={pk}"
        )

        # 8. Return success
        return JsonResponse({
            "success": True,
            "message": f"{entity_type} '{entity_name}' has been deleted successfully.",
            "redirect_url": get_redirect_url(entity_type)
        })

    except Exception as e:
        logger.error(
            f"Deletion error: user={request.user.username}, "
            f"entity={pk}, error={str(e)}"
        )
        return JsonResponse({
            "success": False,
            "error": "Server error",
            "message": f"An error occurred during deletion: {str(e)}"
        }, status=500)
```

**Helper Functions (Centralized):**

```python
# ndas/custom_codes/delete_helpers.py

def has_delete_permission(user, entity):
    """Check if user has permission to delete entity"""
    # Example implementation
    if user.is_superuser:
        return True

    if hasattr(entity, 'added_by'):
        return entity.added_by == user

    return user.is_staff

def validate_can_delete(entity):
    """Check business rules for deletion"""
    # Example: Check if video is used in assessments
    if isinstance(entity, Video):
        from patients.models import GMAssessment
        count = GMAssessment.objects.filter(video_file=entity).count()
        if count > 0:
            return {
                'can_delete': False,
                'reason': f"Cannot delete video that is used in {count} assessment(s)."
            }

    return {'can_delete': True, 'reason': ''}

def get_entity_display_name(entity):
    """Get human-readable name for entity"""
    if hasattr(entity, 'baby_name'):
        return entity.baby_name
    elif hasattr(entity, 'title'):
        return entity.title
    elif hasattr(entity, 'username'):
        return entity.username
    else:
        return str(entity.pk)

def get_redirect_url(entity_type):
    """Get redirect URL after deletion"""
    redirect_map = {
        'Patient': '/manager/patient/',
        'Video': '/video/manager/',
        'GMAssessment': '/assessment/manager/',
        'Attachment': '/attachment/manager/',
        # ... etc
    }
    return redirect_map.get(entity_type, '/')
```

**Why This Design:**
- **Consistency**: Every delete view follows same pattern
- **Security**: Password verification always required
- **Audit Trail**: Comprehensive logging
- **Error Handling**: Proper status codes and messages
- **Maintainability**: Helper functions reduce duplication

## Data Flow

### Typical Delete Operation Flow

```
1. User clicks delete button on manager/view page
   ↓
2. JavaScript shows modal (DeleteConfirmation.show())
   - Pre-populate entity details
   - Focus password field
   ↓
3. User enters password and confirms
   ↓
4. JavaScript executes deletion (DeleteConfirmation.execute())
   - Client-side validation
   - Show loading state
   ↓
5. AJAX DELETE request to backend
   - JSON payload: {password: "xxx"}
   - CSRF token in headers
   ↓
6. Backend view processes request
   - Validate permissions
   - Verify password
   - Check business rules
   - Perform deletion
   - Log audit trail
   ↓
7. Backend returns JSON response
   - {success: true, message: "...", redirect_url: "..."}
   - OR {success: false, error: "...", message: "..."}
   ↓
8. JavaScript handles response
   - Hide modal on success
   - Show success message
   - Redirect after 1.5s
   - OR show error in modal
```

## Integration Points

### Template Integration

**Before (Old Pattern):**
```django
<!-- Separate delete-confirm.html page -->
<a href="{% url 'delete-confirm-patient' patient.id %}">Delete</a>
```

**After (New Pattern):**
```django
<!-- Include unified modal once at bottom of page -->
{% include 'src/partials/delete_confirmation_modal.html' with
    modal_id="deletePatientModal"
    entity_type="Patient"
    entity_name=patient.baby_name
    delete_url=delete_url
    redirect_url=redirect_url
    warning_items=warning_items
    detail_items=detail_items
%}

<!-- Trigger button -->
<button type="button" class="btn btn-danger btn-sm"
        onclick="DeleteConfirmation.show('deletePatientModal')">
    <i class="fas fa-trash"></i> Delete
</button>
```

### URL Pattern Changes

**Before:**
```python
path("patient/delete/confirm/<str:pk>/", views.patient_delete_confirm, name='delete-confirm-patient'),
path("patient/delete/<str:pk>/", views.patient_delete, name='delete-patient'),
```

**After:**
```python
# Remove confirm page, keep only delete endpoint
path("patient/delete/<str:pk>/", views.patient_delete, name='delete-patient'),
```

## Error Handling Strategy

### Client-Side Validation
- Empty password: Show inline error, don't submit
- Network errors: Show error in modal, allow retry

### Server-Side Errors
- 400 (Bad Request): Validation errors → show in modal
- 401 (Unauthorized): Wrong password → show in modal
- 403 (Forbidden): Permission denied → show in modal
- 404 (Not Found): Entity missing → redirect with error message
- 500 (Server Error): Generic error → show in modal

### Error Message Display
```html
<div id="deleteError" class="text-danger mt-2" style="display: none;">
    <!-- Error messages injected here by JavaScript -->
</div>
```

## Testing Strategy

### Unit Tests
- Test each delete view independently
- Mock password verification
- Test permission checks
- Test business rule validation

### Integration Tests
- Test full delete flow end-to-end
- Test with different user roles
- Test error scenarios

### Frontend Tests
- Test modal display
- Test password validation
- Test AJAX request/response handling
- Test error display

### Manual QA Checklist
- [ ] All entity types deletable via unified modal
- [ ] Password always required and verified
- [ ] Success messages display correctly
- [ ] Redirects work properly
- [ ] Error messages clear and helpful
- [ ] Loading states visible
- [ ] Keyboard navigation works (Enter to confirm, Esc to cancel)
- [ ] Mobile responsive
- [ ] Permissions respected
- [ ] Audit logs generated

## Security Considerations

### Password Verification
- Always use `user.check_password(password)` - NEVER compare plain text
- Log failed password attempts for security monitoring
- Rate limit deletion attempts (use existing rate limiting)

### CSRF Protection
- Always include CSRF token in AJAX headers
- Verify token on backend (Django does this automatically)

### Permission Checks
- Check permissions BEFORE password verification
- Don't reveal entity existence to unauthorized users
- Log unauthorized attempts

### Audit Logging
- Log successful deletions with user, entity, timestamp
- Log failed attempts with reason
- Log permission denials

## Rollback Plan

If issues arise during migration:

1. **Per-Entity Rollback**: Keep old views and templates temporarily
2. **Feature Flag**: Add setting to toggle between old/new system
3. **Revert Commits**: Each entity migration is separate commit
4. **Fallback Route**: Old URLs redirect to new system, can reverse

## Performance Considerations

### AJAX vs Full Page
- AJAX: Faster, better UX, requires JavaScript
- Fallback: If JavaScript fails, fall back to POST form submission

### Modal Loading
- Modal loaded once per page, not per entity
- JavaScript loaded globally in base template
- Minimal performance impact

### Database Queries
- No additional queries introduced
- Existing deletion logic preserved

## Maintenance Plan

### Adding New Deletable Entity

**3 Simple Steps:**

1. **Add Delete View** (follow pattern):
```python
@login_required(login_url="user-login")
@require_http_methods(["DELETE"])
def myentity_delete(request, pk):
    # Use standard pattern from delete_helpers
    pass
```

2. **Add URL**:
```python
path("myentity/delete/<str:pk>/", views.myentity_delete, name='myentity-delete'),
```

3. **Add Modal to Template**:
```django
{% include 'src/partials/delete_confirmation_modal.html' with
    modal_id="deleteMyEntityModal"
    entity_type="MyEntity"
    entity_name=entity.name
    delete_url="{% url 'myentity-delete' entity.id %}"
    redirect_url="{% url 'myentity-manager' %}"
    warning_items=warning_items
    detail_items=detail_items
%}
```

**That's it!** ~10 lines of code total.

## Documentation Updates

Files to update after implementation:
- `CLAUDE.md`: Update delete confirmation pattern
- `README.md` (if exists): Document unified system
- Code comments: Explain configuration options
- Developer guide: Add "how to add deletable entity" section
