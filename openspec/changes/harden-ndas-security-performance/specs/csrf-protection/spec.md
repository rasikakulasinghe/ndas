# Spec: CSRF Protection for API Endpoints

## REMOVED Requirements

None - this is a new security capability.

## ADDED Requirements

### Requirement: API endpoints must enforce CSRF protection

All API endpoints that modify state or access authenticated data MUST use Django's CSRF protection mechanism instead of exempting endpoints with `@csrf_exempt` decorator.

#### Scenario: AJAX API call without CSRF token is rejected

**Given** a user is authenticated
**And** makes an AJAX request to `/users/activity-api/`
**When** the request does not include a valid CSRF token
**Then** the server responds with HTTP 403 Forbidden
**And** the response contains an error message about CSRF validation failure

#### Scenario: AJAX API call with valid CSRF token succeeds

**Given** a user is authenticated
**And** the frontend includes `X-CSRFToken` header from cookie
**When** making a POST request to `/users/activity-api/`
**Then** the server processes the request successfully
**And** returns JSON response with user activity data

#### Scenario: GET requests to API endpoints do not require CSRF

**Given** a user is authenticated
**And** the API endpoint only reads data (no state modification)
**When** making a GET request to a read-only API
**Then** CSRF validation is not enforced
**And** the request succeeds without CSRF token

### Requirement: Remove CSRF exemptions from existing code

All instances of `@csrf_exempt` decorator MUST be removed from the codebase and replaced with proper CSRF protection.

#### Scenario: CSRF exempt decorator removed from user activity API

**Given** the file `users/views.py` at line 471
**When** reviewing the `get_user_activity_api` function
**Then** the `@csrf_exempt` decorator is not present
**And** the function uses standard CSRF protection

#### Scenario: Codebase scan finds no CSRF exemptions in production code

**Given** a security audit is performed
**When** searching for `@csrf_exempt` in all Python files
**Then** no instances are found except in test files
**And** all API endpoints rely on Django's CSRF middleware

### Requirement: Frontend AJAX calls must include CSRF tokens

All JavaScript AJAX requests to endpoints requiring CSRF protection MUST include the CSRF token in either:
- HTTP header `X-CSRFToken`
- POST data field `csrfmiddlewaretoken`

#### Scenario: AJAX setup includes CSRF token from cookie

**Given** a Django template with JavaScript code
**When** making an AJAX POST request using fetch or jQuery
**Then** the request includes `X-CSRFToken` header
**And** the token value is read from `csrftoken` cookie

Example:
```javascript
fetch('/users/activity-api/', {
    method: 'POST',
    headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({days: 30})
})
```

#### Scenario: HTMX requests automatically include CSRF token

**Given** the application uses HTMX for dynamic interactions
**When** HTMX makes a POST request
**Then** the CSRF token is automatically included via meta tag

Example:
```html
<meta name="csrf-token" content="{{ csrf_token }}">
<script>
document.body.addEventListener('htmx:configRequest', (event) => {
    event.detail.headers['X-CSRFToken'] = document.querySelector('[name=csrf-token]').content;
});
</script>
```

## MODIFIED Requirements

None - this is new functionality, not modifying existing requirements.

## Cross-References

- **Depends on**: Security middleware stack must be properly configured (CsrfViewMiddleware)
- **Related to**: `rate-limiting` - Both enhance authentication security
- **Related to**: `security-testing` - CSRF protection validated by security test suite
- **Impact**: Frontend JavaScript files making AJAX requests must be updated

## Implementation Notes

**Files to Modify:**
- `users/views.py` line 471 - Remove `@csrf_exempt`, add `@require_http_methods(["POST"])`
- Templates with AJAX calls - Add CSRF token to request headers
- `static/js/` files - Ensure CSRF token included in all POST requests

**Testing Strategy:**
- Unit test: API call without CSRF token returns 403
- Unit test: API call with valid CSRF token succeeds
- Integration test: Frontend AJAX calls work end-to-end with CSRF protection
- Security test: Automated scan finds no `@csrf_exempt` decorators

**Rollback Strategy:**
- If CSRF breaks critical functionality: Temporarily re-add `@csrf_exempt` with FIXME comment
- Identify and fix frontend calls missing CSRF token
- Remove exemption once frontend updated
