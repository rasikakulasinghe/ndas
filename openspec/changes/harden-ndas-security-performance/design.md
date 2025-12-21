# Design: Harden NDAS Security and Performance

## Architecture Overview

This comprehensive hardening effort follows a **layered security and performance optimization approach** across 5 integrated phases:

```
┌─────────────────────────────────────────────────────────────┐
│                     Phase 1: Critical Security              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ CSRF         │  │ CSP          │  │ Rate         │     │
│  │ Protection   │  │ Hardening    │  │ Limiting     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│                   Phase 2: Performance                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Query        │  │ select_      │  │ Debug        │     │
│  │ Optimization │  │ related      │  │ Toolbar      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Phase 3: Code Quality                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Unified      │  │ Docstrings   │  │ Error        │     │
│  │ Manager      │  │ & Cleanup    │  │ Handling     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│                 Phase 4: Security Hardening                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Input        │  │ Security     │  │ Security     │     │
│  │ Sanitization │  │ Middleware   │  │ Tests        │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│                   Phase 5: Testing                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Unit Tests   │  │ Integration  │  │ Security     │     │
│  │ (80%+ cover) │  │ Tests        │  │ Audit        │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. CSRF Protection Strategy

**Decision**: Remove `@csrf_exempt` decorator, use standard Django CSRF tokens

**Rationale**:
- Single API endpoint (`get_user_activity_api`) doesn't justify REST framework overhead
- Already authenticated users, just need CSRF token validation
- Minimal code change, maximum security improvement

**Implementation**:
```python
# BEFORE (VULNERABLE)
@csrf_exempt
def get_user_activity_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

# AFTER (SECURE)
@require_http_methods(["POST"])
def get_user_activity_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    # CSRF token automatically validated by CsrfViewMiddleware
```

**Trade-offs**:
- ✅ Simple, follows Django conventions
- ✅ No new dependencies
- ❌ Frontend must include CSRF token in AJAX calls (minor breaking change)

### 2. Content Security Policy (CSP) Hardening

**Decision**: Remove 'unsafe-inline'/'unsafe-eval', use nonce-based approach

**Rationale**:
- Current CSP with unsafe directives provides **zero XSS protection**
- Nonce-based CSP allows controlled inline scripts while blocking injected code
- Already configured `CSP_INCLUDE_NONCE_IN` in settings

**Implementation**:
```python
# Production CSP (settings.py)
if not DEBUG:
    CSP_SCRIPT_SRC = ("'self'", "https://cdn.jsdelivr.net", ...)  # NO 'unsafe-inline'
    CSP_STYLE_SRC = ("'self'", "https://cdn.jsdelivr.net", ...)
    CSP_INCLUDE_NONCE_IN = ['script-src', 'style-src']

# Templates
<script nonce="{{ request.csp_nonce }}">
    // Inline scripts with nonce are allowed
</script>
```

**Affected Templates**:
- `templates/src/base.html`
- `templates/patients/index.html`
- `templates/users/login.html`
- Any template with `<script>` or `<style>` tags

**Trade-offs**:
- ✅ Proper XSS protection
- ✅ Granular control over allowed scripts
- ❌ Requires template updates (estimated 4 hours)

### 3. Rate Limiting Architecture

**Decision**: Use `django-ratelimit` with dual key strategy (IP + username)

**Rationale**:
- Lightweight decorator-based approach
- Dual key prevents both IP-based and account-based brute force
- Integrates with Django cache (Redis in production)

**Implementation**:
```python
@ratelimit(key='ip', rate='5/m', method='POST', block=True)
@ratelimit(key='post:username', rate='3/m', method='POST', block=True)
def loginPage(request):
    # 5 attempts/min per IP, 3 attempts/min per username
```

**Rate Limits**:
- Login: 5/min per IP, 3/min per username
- Password reset: 3/hour per IP
- Registration: 3/hour per IP
- Email verification resend: 3/hour per email

**Trade-offs**:
- ✅ Prevents brute force without lockout complexity
- ✅ Conservative limits avoid blocking legitimate users
- ❌ Requires Redis for production (already in tech stack)

### 4. Patient Manager Consolidation

**Decision**: Single unified view with `filter_type` parameter

**Current State** (8 duplicate functions):
```python
def patient_manager(request): ...              # ~250 lines
def patient_manager_diagnosed_any(request): ... # ~250 lines
def patient_manager_diagnosis_normal(request): ... # ~250 lines
# ... 5 more identical functions
# Total: ~2000 lines of duplicated code
```

**Refactored Design**:
```python
@login_required(login_url="user-login")
def patient_manager(request, filter_type='all'):
    FILTER_MAP = {
        'all': Patient.objects.all(),
        'diagnosed': getPatientList(PtStatus.DIAGNOSED),
        'dx_normal': getPatientList(PtStatus.DX_NORMAL),
        # ... other filters
    }
    patients_list = FILTER_MAP.get(filter_type, Patient.objects.all())
    # ... unified search, pagination, rendering logic
```

**URL Patterns**:
```python
# New unified URLs
path('manager/patient/', views.patient_manager, name='manager'),
path('manager/patient/<str:filter_type>/', views.patient_manager, name='manager-filtered'),

# Old URLs (kept as redirects for 6 months)
path('manager/patient/diagnosed/', redirect_to_manager('diagnosed'), name='manager-diagnosed'),
```

**Benefits**:
- 97.5% code reduction (2000 → 50 lines)
- Single point of maintenance
- Easier to add new filters
- Consistent behavior across all views

**Trade-offs**:
- ✅ Massive maintainability improvement
- ✅ DRY principle compliance
- ⚠️ Requires URL migration strategy (redirects provided)

### 5. Query Optimization Strategy

**Problem**: Dashboard generates ~50 queries due to N+1 patterns

**Current Anti-Pattern**:
```python
var_patients = getPatientList(PtStatus.ALL)  # Loads all patients
var_new_Patients = var_patients.filter(videos__isnull=True).distinct()
Patients_new_list_10 = var_new_Patients[:5]  # Slices in Python, not SQL
```

**Optimized Pattern**:
```python
# Count without loading data
patients_total_count = Patient.objects.count()

# Load only needed records with relationships
Patients_new_list_10 = Patient.objects.annotate(
    video_count=Count('videos')
).filter(
    video_count=0
).select_related(
    'added_by', 'last_edit_by'
).only(
    'id', 'baby_name', 'bht', 'added_by__username'
)[:5]
```

**Optimization Techniques**:
1. **Count vs Load**: Use `.count()` for statistics, not `len(queryset)`
2. **select_related**: Join ForeignKey in single query
3. **prefetch_related**: Efficient M2M/reverse FK loading
4. **only()**: Load specific fields, not entire rows
5. **Annotations**: Database-level aggregations
6. **Exists subqueries**: Faster than joins for filtering

**Expected Impact**:
- Query count: 50 → 15 (70% reduction)
- Load time: 2-3s → <1s with 1000+ patients

### 6. Error Handling Standardization

**Decision**: Decorator-based error handling with logging

**Current State**: Inconsistent try/except patterns, generic error messages

**New Pattern**:
```python
@handle_view_errors(redirect_url='patient-manager', error_message='Error processing patient')
def patient_edit(request, pk):
    # View logic - exceptions handled by decorator
    # - ObjectDoesNotExist → user-friendly 404
    # - ValidationError → field-specific messages
    # - IntegrityError → database constraint messages
    # - Generic Exception → logged + safe error message
```

**Benefits**:
- Consistent error messages across all views
- Comprehensive logging with user/path context
- Centralized error handling logic
- Better user experience

### 7. Input Sanitization Architecture

**Decision**: Form-level sanitization with bleach library

**Sanitization Layers**:
1. **Plain Text Fields** (names, identifiers): `escape()` HTML entities
2. **Rich Text Fields** (medical notes): `bleach.clean()` with allowed tags
3. **Filenames**: Path traversal prevention

**Implementation**:
```python
# Sanitization utilities (ndas/custom_codes/sanitization.py)
ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'h1-h6', 'a', 'blockquote']
ALLOWED_ATTRIBUTES = {'a': ['href', 'title']}

def sanitize_html(html_content):
    return bleach.clean(html_content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

# Form integration
class PatientForm(forms.ModelForm):
    def clean_baby_name(self):
        return sanitize_plain_text(self.cleaned_data.get('baby_name'))

    def clean_problems(self):
        return sanitize_html(self.cleaned_data.get('problems'))
```

**Scope**:
- **Sanitize**: New form inputs only (per user preference)
- **No Migration**: Existing database records unchanged
- **Display**: Raw data displayed (Django's auto-escaping provides baseline protection)

**Trade-offs**:
- ✅ Defense-in-depth XSS protection
- ✅ Preserves rich text formatting where appropriate
- ❌ Doesn't fix existing data (acceptable per decision)

### 8. Testing Strategy

**Multi-Layer Testing Approach**:

```
┌───────────────────────────────────────────────────────┐
│  Security Tests (tests/test_security.py)              │
│  - CSRF protection validation                         │
│  - CSP header verification                            │
│  - Rate limiting enforcement                          │
│  - Authentication security                            │
│  - Input sanitization                                 │
└───────────────────────────────────────────────────────┘
           ↓
┌───────────────────────────────────────────────────────┐
│  Unit Tests (patients/tests/test_views.py)            │
│  - Patient manager filter variations                  │
│  - Search functionality                               │
│  - Pagination correctness                             │
│  - Query optimization verification                    │
└───────────────────────────────────────────────────────┘
           ↓
┌───────────────────────────────────────────────────────┐
│  Integration Tests (tests/test_integration.py)        │
│  - Full patient workflow (create → video → assess)    │
│  - Cross-app interactions                             │
│  - Timeline generation                                │
└───────────────────────────────────────────────────────┘
           ↓
┌───────────────────────────────────────────────────────┐
│  Performance Benchmarks (scripts/benchmark_*.py)      │
│  - Dashboard query count                              │
│  - Response time measurements                         │
│  - Query profiling with django-silk                   │
└───────────────────────────────────────────────────────┘
           ↓
┌───────────────────────────────────────────────────────┐
│  Security Audit (scripts/security_audit.sh)           │
│  - safety check (dependency vulnerabilities)          │
│  - bandit (Python code security)                      │
│  - python manage.py check --deploy                    │
│  - OWASP ZAP automated scan (manual step)             │
└───────────────────────────────────────────────────────┘
```

**Test Coverage Target**: 80%+ for refactored code

**Automated Validation**:
```bash
# Run as part of CI/CD or pre-deployment
python manage.py test tests.test_security --verbosity=2
python manage.py test patients.tests.test_views
python manage.py test tests.test_integration
python scripts/benchmark_dashboard.py
bash scripts/security_audit.sh
```

## Data Flow Changes

### Login Flow (Before → After)

**BEFORE (Vulnerable)**:
```
User submits credentials
    ↓
Check if username exists ← TIMING ATTACK VECTOR
    ↓ YES                      ↓ NO
Authenticate             Show "Wrong username"
    ↓                          (Different message)
Success/Wrong password
    (Different messages)
```

**AFTER (Secure)**:
```
User submits credentials
    ↓
Rate limit check (5/min IP, 3/min username)
    ↓ PASS                    ↓ BLOCKED
Always authenticate      Show rate limit error
    ↓                          (Log attempt)
Success or generic error
    ("Invalid username or password")
    (Same message for all failures)
```

### Dashboard Query Flow (Before → After)

**BEFORE (Inefficient)**:
```
Load ALL patients → Filter in Python → Count in Python → Slice [:5] in Python
Load ALL videos → Filter in Python → Count in Python
Load ALL assessments → Count in Python
Template accesses patient.added_by → N+1 queries
```

**AFTER (Optimized)**:
```
Count patients in DB → Single COUNT query
Annotate + filter + select_related → Single JOIN query with LIMIT 5
Count videos with subquery → Single COUNT with EXISTS
Prefetch relationships → Batch loading, no N+1
```

## Security Model

### Defense-in-Depth Layers

**Layer 1: Input Validation**
- Form-level sanitization (bleach)
- File upload validation (type, size, content)
- CSRF tokens on all POST requests

**Layer 2: Authentication & Authorization**
- Rate limiting (django-ratelimit)
- Secure session management (1-hour timeout)
- No timing attacks (generic error messages)

**Layer 3: Application Security**
- CSP with nonces (blocks XSS injection)
- Security headers (X-Frame-Options, X-Content-Type-Options, etc.)
- Error handling (no sensitive info leakage)

**Layer 4: Monitoring & Audit**
- User activity logging (UserActivityMiddleware)
- Security test suite (automated regression prevention)
- Security audit tools (safety, bandit, OWASP ZAP)

## Deployment Considerations

### Environment Configuration

**Development** (DEBUG=True):
```python
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
RATELIMIT_ENABLE = False
INSTALLED_APPS += ['debug_toolbar', 'silk']
CSP allows 'unsafe-inline' for easier development
```

**Production** (DEBUG=False):
```python
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
RATELIMIT_ENABLE = True
No debug tooling installed
Strict CSP without unsafe directives
```

### Migration Path

**Phase 1 → Phase 2**: Independent (can run in parallel)
**Phase 2 → Phase 3**: Must complete Phase 2 first (performance baseline needed)
**Phase 3 → Phase 4**: Independent (code quality doesn't block security)
**Phase 4 → Phase 5**: Must complete Phase 4 before security tests (tests validate hardening)

### Rollback Strategy

**Critical Fixes (Phase 1)**:
- Revert CSP changes → Re-enable 'unsafe-inline' temporarily
- Revert rate limiting → Remove decorators
- Revert CSRF fix → Re-add @csrf_exempt (NOT RECOMMENDED)

**Performance Changes (Phase 2)**:
- Revert optimized queries → Restore original view code
- Keep monitoring tools (debug-toolbar, silk) → No harm in development

**Code Quality (Phase 3)**:
- Revert unified manager → Restore 8 duplicate functions
- Keep docstrings and error handling → Only improvements

**Testing (Phase 5)**:
- Low risk → Tests don't affect runtime behavior

## Open Issues

None - all design decisions finalized based on clarifications:
- ✅ Single comprehensive change approach
- ✅ Full refactoring freedom for optimization
- ✅ All dependencies included in requirements.txt
- ✅ Sanitize new inputs only (no retroactive migration)
