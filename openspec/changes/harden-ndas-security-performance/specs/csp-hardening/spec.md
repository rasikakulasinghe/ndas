# Spec: Content Security Policy Hardening

## REMOVED Requirements

### Requirement: Production CSP allows unsafe inline scripts and eval

**Rationale**: The current production CSP configuration includes 'unsafe-inline' and 'unsafe-eval' directives which completely undermine XSS protection. This must be removed.

**Current State** (settings.py:272-283):
```python
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdn.jsdelivr.net", ...)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", ...)
```

#### Scenario: Production CSP includes unsafe directives (REMOVED)

**Given** the application is running in production mode (DEBUG=False)
**When** a page is loaded and CSP headers are inspected
**Then** the `Content-Security-Policy` header includes `'unsafe-inline'` and `'unsafe-eval'`

This scenario is being **REMOVED** - the new requirement forbids unsafe directives.

## ADDED Requirements

### Requirement: Production CSP must enforce strict XSS protection

Production Content Security Policy MUST NOT include 'unsafe-inline' or 'unsafe-eval' directives. Instead, nonce-based CSP must be used for inline scripts and styles.

#### Scenario: Production CSP rejects unsafe inline scripts

**Given** the application is running in production mode (DEBUG=False)
**When** a page is loaded and CSP headers are inspected
**Then** the `Content-Security-Policy` header does NOT contain `'unsafe-inline'`
**And** the header does NOT contain `'unsafe-eval'`
**And** inline scripts without nonce are blocked

#### Scenario: Production CSP allows nonce-based inline scripts

**Given** the application is configured with `CSP_INCLUDE_NONCE_IN = ['script-src', 'style-src']`
**When** a template includes an inline script with CSP nonce: `<script nonce="{{ request.csp_nonce }}">`
**Then** the script executes successfully
**And** the browser console shows no CSP violations

Example:
```django
<script nonce="{{ request.csp_nonce }}">
    console.log('This inline script is allowed via nonce');
</script>
```

#### Scenario: Production CSP blocks injected malicious scripts

**Given** an attacker attempts XSS injection via user input
**When** the injected script tries to execute: `<script>alert('XSS')</script>`
**Then** the browser blocks the script due to CSP violation
**And** the browser console logs CSP violation error
**And** no alert dialog is shown to the user

### Requirement: CSP configuration differs between development and production

Development mode (DEBUG=True) MAY use relaxed CSP for easier debugging, but production mode (DEBUG=False) MUST enforce strict CSP without unsafe directives.

#### Scenario: Development mode allows unsafe inline for debugging

**Given** the application is running in development mode (DEBUG=True)
**When** a page is loaded with inline scripts without nonce
**Then** the scripts execute successfully
**And** no CSP violations are logged

#### Scenario: Production mode enforces strict CSP

**Given** the application is running in production mode (DEBUG=False)
**When** a page is loaded
**Then** the CSP header enforces strict policy
**And** only allows scripts from 'self' and whitelisted CDNs
**And** requires nonce for all inline scripts

### Requirement: All templates must use CSP nonces for inline scripts

All Django templates with inline `<script>` or `<style>` tags MUST include the CSP nonce attribute.

#### Scenario: Base template includes nonce on inline scripts

**Given** the file `templates/src/base.html`
**When** reviewing inline script tags
**Then** all `<script>` tags include `nonce="{{ request.csp_nonce }}"`
**And** all `<style>` tags include `nonce="{{ request.csp_nonce }}"`

#### Scenario: Patient index template uses nonce for dashboard scripts

**Given** the file `templates/patients/index.html`
**When** reviewing Chart.js initialization scripts
**Then** the `<script>` tag includes `nonce="{{ request.csp_nonce }}"`

Example:
```django
<script nonce="{{ request.csp_nonce }}">
    // Chart.js initialization
    var ctx = document.getElementById('myChart').getContext('2d');
    new Chart(ctx, { /* config */ });
</script>
```

### Requirement: CSP whitelist only necessary external resources

The CSP script-src and style-src directives MUST only whitelist CDNs and external resources that are actually used by the application.

#### Scenario: CSP allows required CDNs for AdminLTE

**Given** the application uses AdminLTE framework
**When** the CSP header is inspected
**Then** `script-src` includes:
  - `'self'`
  - `https://cdn.jsdelivr.net` (AdminLTE assets)
  - `https://cdnjs.cloudflare.com` (libraries)
  - `https://unpkg.com` (additional libraries)
  - `https://vjs.zencdn.net` (Video.js)
**And** does NOT include unused CDNs

#### Scenario: CSP blocks unauthorized external scripts

**Given** the CSP is configured with whitelist
**When** a compromised dependency tries to load script from `https://malicious-cdn.com`
**Then** the browser blocks the request due to CSP violation
**And** logs a CSP violation error

## MODIFIED Requirements

None - this replaces the previous insecure CSP configuration entirely.

## Cross-References

- **Depends on**: `django-csp` middleware already installed
- **Related to**: `csrf-protection` - Both are XSS defense layers
- **Related to**: `security-testing` - CSP validated by SecurityHeadersTestCase
- **Impact**: All templates with inline scripts require updates

## Implementation Notes

**Settings Configuration** (ndas/settings.py):
```python
if not DEBUG:
    # Production - Strict CSP
    CSP_DEFAULT_SRC = ("'self'",)
    CSP_SCRIPT_SRC = (
        "'self'",
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com",
        "https://unpkg.com",
        "https://vjs.zencdn.net"
    )
    CSP_STYLE_SRC = (
        "'self'",
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com",
        "https://fonts.googleapis.com",
        "https://vjs.zencdn.net"
    )
    CSP_IMG_SRC = ("'self'", "data:", "blob:", "https:")
    CSP_FONT_SRC = ("'self'", "data:", "https://cdn.jsdelivr.net", "https://fonts.gstatic.com")
    CSP_CONNECT_SRC = ("'self'",)
    CSP_FRAME_SRC = ("'none'",)
    CSP_OBJECT_SRC = ("'none'",)
    CSP_BASE_URI = ("'self'",)
    CSP_FORM_ACTION = ("'self'",)
    CSP_INCLUDE_NONCE_IN = ['script-src', 'style-src']
else:
    # Development - Relaxed CSP
    CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdn.jsdelivr.net")
    CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net")
```

**Template Updates Required:**
- `templates/src/base.html` - Add nonce to all inline scripts
- `templates/patients/index.html` - Add nonce to Chart.js initialization
- `templates/users/login.html` - Add nonce to any inline scripts
- Search all templates: `rg "<script(?!\s+src)" templates/`

**Validation Strategy:**
1. Browser DevTools Console - Check for CSP violations
2. Unit test - Verify CSP header doesn't contain 'unsafe-inline'
3. Manual test - Verify all functionality works with strict CSP
4. Security scan - OWASP ZAP validates CSP configuration

**Rollback Strategy:**
If strict CSP breaks critical functionality:
1. Temporarily re-enable 'unsafe-inline' in production CSP
2. Add FIXME comment with issue tracker reference
3. Identify templates missing nonce attribute
4. Update templates and re-apply strict CSP
5. Never keep 'unsafe-inline' in production long-term
