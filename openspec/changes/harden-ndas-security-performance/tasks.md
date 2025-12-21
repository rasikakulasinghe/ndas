# Tasks: Harden NDAS Security and Performance

## Phase 1: Critical Security (Week 1 - 10 hours)

### 1.1 Remove CSRF Exemption on API Endpoint (2 hours)
- [ ] Remove `@csrf_exempt` decorator from `users/views.py:471` (get_user_activity_api)
- [ ] Add `@require_http_methods(["POST"])` decorator
- [ ] Update frontend AJAX calls to include CSRF token
- [ ] Test API endpoint returns 403 without CSRF token
- [ ] Verify authenticated API calls work with token
- **Validation**: `python manage.py test tests.test_security::CSRFProtectionTestCase`

### 1.2 Harden Production CSP Configuration (4 hours)
- [ ] Update `ndas/settings.py:272-283` - remove 'unsafe-inline', 'unsafe-eval' from production CSP
- [ ] Add CSP nonce to `templates/src/base.html` inline scripts
- [ ] Add CSP nonce to `templates/patients/index.html` inline scripts
- [ ] Add CSP nonce to `templates/users/login.html` inline scripts
- [ ] Search for all inline `<script>` and `<style>` tags: `rg "<script(?!\s+src)" templates/`
- [ ] Test in browser DevTools Console for CSP violations
- [ ] Verify no functionality breaks with strict CSP
- **Validation**: `python manage.py test tests.test_security::SecurityHeadersTestCase`

### 1.3 Configure Production Email Backend (1 hour)
- [ ] Update `ndas/settings.py:158-168` - environment-based email configuration
- [ ] Add SMTP settings for production (EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS)
- [ ] Add console backend for development
- [ ] Update `.env.example` with email configuration variables
- [ ] Document email setup in deployment guide
- **Validation**: Test password reset flow in staging environment

### 1.4 Add Rate Limiting to Authentication (3 hours)
- [ ] Add `django-ratelimit==4.1.0` to requirements.txt
- [ ] Install django-ratelimit: `pip install django-ratelimit`
- [ ] Add rate limiting to `loginPage` (users/views.py:28) - 5/min IP, 3/min username
- [ ] Add rate limiting to password reset view - 3/hour IP
- [ ] Add rate limiting to email verification resend - 3/hour email
- [ ] Update settings.py with RATELIMIT_USE_CACHE, RATELIMIT_ENABLE
- [ ] Create custom rate limit error handler (ndas/views.py)
- [ ] Create `templates/errors/rate_limited.html` template
- [ ] Test multiple failed login attempts trigger rate limit
- [ ] Verify rate limit error messages are user-friendly
- **Validation**: `python manage.py test tests.test_security::RateLimitingTestCase`

## Phase 2: Performance Optimization (Week 2 - 7 hours)

### 2.1 Optimize Dashboard Queries (4 hours)
- [ ] Baseline dashboard performance: `python scripts/benchmark_dashboard.py` (create script)
- [ ] Refactor `patients/views.py:80-150` dashboard() view
- [ ] Replace `len(queryset)` with `.count()` for all statistics
- [ ] Add `select_related('added_by', 'last_edit_by')` to patient queries
- [ ] Use annotations for video_count instead of filtering
- [ ] Use Exists() subquery for new videos without assessments
- [ ] Add `.only()` to limit fields loaded for list views
- [ ] Verify query count reduced from ~50 to ~15
- [ ] Verify dashboard loads in <1s with 1000+ test patients
- **Validation**: Benchmark comparison shows 60%+ query reduction

### 2.2 Optimize Patient Manager Views (2 hours)
- [ ] Add `select_related('added_by', 'last_edit_by')` to patient_manager (patients/views.py:154)
- [ ] Add prefetch_related for 'indecation_for_gma', 'videos', 'assessments'
- [ ] Apply optimization to patient_manager_diagnosed_any
- [ ] Apply optimization to patient_manager_diagnosis_normal
- [ ] Apply optimization to patient_manager_diagnosed_gma_normal
- [ ] Apply optimization to patient_manager_diagnosed_gma_abnormal
- [ ] Apply optimization to patient_manager_diagnosed_hine
- [ ] Apply optimization to patient_manager_da_normal
- [ ] Apply optimization to patient_manager_da_abnormal
- [ ] Apply optimization to patient_manager_discharged_only
- [ ] Verify no N+1 queries on user references
- **Validation**: Check query count with django-debug-toolbar

### 2.3 Add Database Query Monitoring Tools (1 hour)
- [ ] Add `django-debug-toolbar==4.2.0` to requirements.txt
- [ ] Install debug-toolbar: `pip install django-debug-toolbar`
- [ ] Update settings.py - add debug_toolbar to INSTALLED_APPS (DEBUG mode only)
- [ ] Update settings.py - add DebugToolbarMiddleware to MIDDLEWARE
- [ ] Configure INTERNAL_IPS = ['127.0.0.1', 'localhost']
- [ ] Update ndas/urls.py - add debug toolbar URLs for DEBUG mode
- [ ] Test toolbar appears on dashboard in development
- [ ] Verify SQL panel shows query count and timing
- **Validation**: Visual confirmation of toolbar in browser

## Phase 3: Code Quality Refactoring (Weeks 3-4 - 19 hours)

### 3.1 Eliminate Patient Manager Duplication (6 hours)
- [ ] Create unified patient_manager(request, filter_type='all') in patients/views.py
- [ ] Implement FILTER_MAP dictionary with all filter types
- [ ] Implement FILTER_LABELS dictionary for page titles
- [ ] Add select_related/prefetch_related optimization
- [ ] Add search functionality with Q objects
- [ ] Add pagination (10 per page)
- [ ] Update patients/urls.py - add new unified URL patterns
- [ ] Update patients/urls.py - add redirects from old URLs to new (6-month deprecation)
- [ ] Update templates/patients/manager.html - use filter_label and filter_type
- [ ] Update navigation links to use new URL patterns
- [ ] Test all 9 filter types work correctly (all, diagnosed, dx_normal, etc.)
- [ ] Test search functionality across all filters
- [ ] Test pagination works correctly
- [ ] Remove 8 duplicate patient_manager_* functions
- [ ] Remove old URL patterns after redirect testing
- **Validation**: `python manage.py test patients.tests.test_views::PatientManagerTestCase`

### 3.2 Remove Dead Code (1 hour)
- [ ] Delete users/middleware.py:179-196 (commented signal handler)
- [ ] Delete patients/views.py:69 (commented moviepy import)
- [ ] Delete patients/views.py:58 (duplicate timeline_utils import)
- [ ] Search for other commented code: `rg "^#\s*(def|class|import)" --type py`
- [ ] Remove any additional dead code found
- **Validation**: `git diff` shows only deletions

### 3.3 Add Comprehensive Docstrings (8 hours)
- [ ] Document all view functions in patients/views.py (Google-style)
- [ ] Document all view functions in users/views.py
- [ ] Document custom methods in ndas/custom_codes/custom_methods.py
- [ ] Document model methods in patients/models.py
- [ ] Document model methods in users/models.py
- [ ] Document model methods in video/models.py
- [ ] Verify docstrings include: brief description, Args, Returns, Raises
- [ ] Include example usage where helpful
- **Validation**: Manual review of docstring completeness

### 3.4 Standardize Error Handling (4 hours)
- [ ] Create ndas/custom_codes/error_handlers.py
- [ ] Implement handle_view_errors() decorator
- [ ] Implement log_and_suppress() decorator
- [ ] Add error handling for ObjectDoesNotExist
- [ ] Add error handling for ValidationError
- [ ] Add error handling for IntegrityError
- [ ] Add error handling for PermissionError
- [ ] Add generic Exception catch-all with logging
- [ ] Apply @handle_view_errors to patient CRUD views
- [ ] Apply @handle_view_errors to video CRUD views
- [ ] Apply @handle_view_errors to assessment CRUD views
- [ ] Test error handling displays user-friendly messages
- [ ] Verify errors are logged with user/path context
- **Validation**: Trigger errors and verify handling + logging

## Phase 4: Security Hardening (Week 5 - 15 hours)

### 4.1 Fix Timing Attack Vulnerability (2 hours)
- [ ] Remove username existence check in users/views.py:39-198 loginPage
- [ ] Always call authenticate() without pre-checking username
- [ ] Use generic error message "Invalid username or password" for all auth failures
- [ ] Update failed login logging with generic reason "Invalid credentials"
- [ ] Test invalid username returns same message as invalid password
- [ ] Test response times are consistent (no timing leak)
- **Validation**: `python manage.py test tests.test_security::AuthenticationSecurityTestCase`

### 4.2 Add Security Headers Middleware (3 hours)
- [ ] Create ndas/custom_codes/security_middleware.py
- [ ] Implement SecurityHeadersValidationMiddleware class
- [ ] Implement AdditionalSecurityHeadersMiddleware class
- [ ] Validate required headers: X-Content-Type-Options, X-Frame-Options, CSP
- [ ] Validate HTTPS headers when SSL enabled: Strict-Transport-Security
- [ ] Add Referrer-Policy header
- [ ] Add Cross-Origin-Opener-Policy header
- [ ] Add X-Permitted-Cross-Domain-Policies header
- [ ] Update settings.py MIDDLEWARE - add AdditionalSecurityHeadersMiddleware
- [ ] Update settings.py MIDDLEWARE - add SecurityHeadersValidationMiddleware (production only)
- [ ] Test headers present in production mode
- [ ] Test missing headers trigger critical log messages
- **Validation**: Check response headers in browser DevTools

### 4.3 Add Input Sanitization Layer (4 hours)
- [ ] Add `bleach==6.1.0` to requirements.txt
- [ ] Install bleach: `pip install bleach`
- [ ] Create ndas/custom_codes/sanitization.py
- [ ] Implement sanitize_html() function with allowed tags/attributes
- [ ] Implement sanitize_plain_text() function
- [ ] Implement sanitize_filename() function
- [ ] Update patients/forms.py PatientForm - sanitize baby_name, mother_name
- [ ] Update patients/forms.py PatientForm - sanitize problems, resustn_note (allow HTML)
- [ ] Update patients/forms.py AttachmentForm - sanitize title, description
- [ ] Update patients/forms.py AttachmentForm - sanitize uploaded filenames
- [ ] Update video/forms.py - sanitize title, description
- [ ] Update users/forms.py - sanitize user profile fields
- [ ] Test XSS attempts in forms are sanitized
- [ ] Verify rich text fields preserve allowed formatting
- **Validation**: `python manage.py test tests.test_security::InputSanitizationTestCase`

### 4.4 Add Comprehensive Security Tests (6 hours)
- [ ] Create tests/test_security.py
- [ ] Implement CSRFProtectionTestCase - test login requires CSRF
- [ ] Implement CSRFProtectionTestCase - test patient add requires CSRF
- [ ] Implement SecurityHeadersTestCase - test CSP headers in production
- [ ] Implement SecurityHeadersTestCase - test no unsafe-inline/unsafe-eval
- [ ] Implement SecurityHeadersTestCase - test X-Frame-Options DENY
- [ ] Implement SecurityHeadersTestCase - test X-Content-Type-Options nosniff
- [ ] Implement AuthenticationSecurityTestCase - test no username enumeration
- [ ] Implement RateLimitingTestCase - test login rate limiting
- [ ] Implement InputSanitizationTestCase - test XSS in patient name
- [ ] Implement InputSanitizationTestCase - test script tag removal
- [ ] Run all security tests: `python manage.py test tests.test_security --verbosity=2`
- [ ] Verify 100% pass rate
- **Validation**: All security tests pass

## Phase 5: Testing & Validation (Week 6 - 22 hours)

### 5.1 Add Unit Tests for Refactored Views (8 hours)
- [ ] Create patients/tests/test_views.py
- [ ] Implement PatientManagerTestCase setUp with test data
- [ ] Test patient_manager with 'all' filter
- [ ] Test patient_manager with search by baby name
- [ ] Test patient_manager with search by BHT number
- [ ] Test patient_manager pagination (create 15 test patients)
- [ ] Test all 9 filter type variations work correctly
- [ ] Test filter_type context variable set correctly
- [ ] Test filter_label context variable set correctly
- [ ] Test invalid filter_type defaults to 'all'
- [ ] Run tests: `python manage.py test patients.tests.test_views --verbosity=2`
- [ ] Measure test coverage: `coverage run --source='.' manage.py test patients.tests.test_views`
- [ ] Verify coverage > 80%: `coverage report`
- **Validation**: Test coverage report shows >80%

### 5.2 Add Integration Tests (6 hours)
- [ ] Create tests/test_integration.py
- [ ] Implement PatientWorkflowIntegrationTest setUp
- [ ] Test complete workflow: create patient
- [ ] Test complete workflow: upload video for patient
- [ ] Test complete workflow: create GM assessment
- [ ] Test complete workflow: view patient timeline
- [ ] Verify timeline shows all events correctly
- [ ] Test cross-app data consistency
- [ ] Clean up uploaded test files
- [ ] Run tests: `python manage.py test tests.test_integration --verbosity=2`
- [ ] Verify all integration tests pass
- **Validation**: All integration tests pass

### 5.3 Performance Benchmarking (4 hours)
- [ ] Add `django-silk==5.0.4` to requirements.txt (development only)
- [ ] Install django-silk: `pip install django-silk`
- [ ] Update settings.py - add silk to INSTALLED_APPS (DEBUG mode only)
- [ ] Update settings.py - add SilkyMiddleware to MIDDLEWARE
- [ ] Update ndas/urls.py - add silk URLs for DEBUG mode
- [ ] Create scripts/benchmark_dashboard.py
- [ ] Implement benchmark_dashboard() function with query logging
- [ ] Measure baseline performance BEFORE optimizations
- [ ] Measure performance AFTER optimizations
- [ ] Calculate improvement metrics (query count, response time)
- [ ] Document results in performance_report.md
- [ ] Verify dashboard query count reduced by 60%+
- [ ] Verify dashboard loads in <1s with 1000+ patients
- **Validation**: Performance report shows targets met

### 5.4 Security Audit Validation (4 hours)
- [ ] Add `safety==3.0.1` to requirements.txt
- [ ] Add `bandit==1.7.5` to requirements.txt
- [ ] Install security tools: `pip install safety bandit`
- [ ] Create scripts/security_audit.sh
- [ ] Run dependency vulnerability check: `safety check --json > security/dependency_vulnerabilities.json`
- [ ] Run Python security linter: `bandit -r ndas patients users video -f json -o security/code_security.json`
- [ ] Run Django deployment check: `python manage.py check --deploy > security/django_deployment_check.txt`
- [ ] Run security test suite: `python manage.py test tests.test_security --verbosity=2`
- [ ] Review safety report - resolve any critical/high vulnerabilities
- [ ] Review bandit report - resolve any high severity issues
- [ ] Review Django deployment check - resolve all warnings
- [ ] Download and install OWASP ZAP (manual step)
- [ ] Run OWASP ZAP automated scan on staging environment (manual step)
- [ ] Review OWASP ZAP report - verify no high/critical vulnerabilities
- [ ] Document security audit results
- **Validation**: Security audit report shows no critical issues

## Final Validation Checklist

### Phase 1: Critical Security ✅
- [ ] All API endpoints require CSRF protection (no @csrf_exempt)
- [ ] Production CSP does not contain 'unsafe-inline' or 'unsafe-eval'
- [ ] Email backend configured for SMTP in production
- [ ] Rate limiting active on login, password reset, registration
- [ ] No timing attacks possible (same error message for all auth failures)

### Phase 2: Performance ✅
- [ ] Dashboard loads in < 1 second with 1000+ test patients
- [ ] Query count reduced by at least 60% (documented in benchmark)
- [ ] No N+1 queries in patient manager views (verified with debug-toolbar)

### Phase 3: Code Quality ✅
- [ ] Patient manager functions reduced from 8 to 1 (97.5% code reduction)
- [ ] No commented-out code in production files
- [ ] All public view functions have Google-style docstrings
- [ ] Consistent error handling via @handle_view_errors decorator

### Phase 4: Security Hardening ✅
- [ ] Generic error messages prevent username enumeration
- [ ] All security headers present and validated (middleware checks)
- [ ] User input sanitized in all forms (bleach integration)
- [ ] Security test suite passes 100% (tests/test_security.py)

### Phase 5: Testing ✅
- [ ] Unit test coverage > 80% for refactored code (coverage report)
- [ ] All integration tests pass (tests/test_integration.py)
- [ ] Performance benchmarks documented (performance_report.md)
- [ ] Security audit shows no high/critical vulnerabilities (audit reports)

## Deployment Steps

1. **Backup Database**: `python manage.py dumpdata > backup.json`
2. **Update Dependencies**: `pip install -r requirements.txt`
3. **Run Migrations**: `python manage.py migrate`
4. **Run Tests**: `python manage.py test`
5. **Collect Static Files**: `python manage.py collectstatic --noinput`
6. **Update Environment Variables**: Add EMAIL_*, RATELIMIT_* to .env
7. **Deploy to Staging**: Test all functionality
8. **Security Scan**: Run OWASP ZAP on staging
9. **Performance Test**: Benchmark dashboard with production data
10. **Deploy to Production**: Gradual rollout with monitoring

## Rollback Plan

**If critical issues discovered post-deployment:**

1. **Revert Code**: `git revert <commit-hash>` or `git checkout <previous-tag>`
2. **Restore Database**: `python manage.py loaddata backup.json`
3. **Restart Services**: Gunicorn, Celery workers
4. **Specific Rollbacks**:
   - CSP issues: Temporarily re-enable 'unsafe-inline' in settings.py
   - Rate limiting issues: Set RATELIMIT_ENABLE=False in .env
   - Performance regression: Restore original dashboard/manager views
5. **Monitor Logs**: Check for error patterns
6. **Notify Users**: Communicate any service disruptions

## Notes

- All tasks include validation steps to ensure correctness
- Dependencies between phases respected (e.g., Phase 5 tests validate Phase 4 security)
- Estimated hours per task based on improvement_plan.md (total: 73 hours)
- Each major change includes rollback strategy
- Security and performance targets are measurable and testable
