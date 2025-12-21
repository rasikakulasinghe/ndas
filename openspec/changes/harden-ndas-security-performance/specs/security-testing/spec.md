# Spec: Comprehensive Security Testing

## REMOVED Requirements

None - this establishes new security testing infrastructure.

## ADDED Requirements

### Requirement: Security test suite must validate all Phase 1 and Phase 4 security hardening

The security test suite MUST include automated tests for CSRF protection, CSP headers, rate limiting, authentication security, and input sanitization.

#### Scenario: CSRF protection test suite validates token requirements

**Given** the file `tests/test_security.py`
**When** running `python manage.py test tests.test_security::CSRFProtectionTestCase`
**Then** the following tests pass:
  - `test_login_requires_csrf_token`: POST to login without CSRF returns 403
  - `test_patient_add_requires_csrf_token`: POST to patient add without CSRF returns 403
  - `test_api_endpoint_requires_csrf_token`: POST to API without CSRF returns 403
**And** all tests use `Client(enforce_csrf_checks=True)`

Example:
```python
class CSRFProtectionTestCase(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def test_login_requires_csrf_token(self):
        response = self.client.post(reverse('user-login'), {
            'username': 'testuser',
            'password': 'TestPass123!'
        })
        self.assertEqual(response.status_code, 403)
```

#### Scenario: Security headers test suite validates production configuration

**Given** the file `tests/test_security.py`
**When** running `python manage.py test tests.test_security::SecurityHeadersTestCase`
**Then** the following tests pass:
  - `test_csp_headers_in_production`: CSP header present when DEBUG=False
  - `test_csp_no_unsafe_inline`: Production CSP doesn't contain 'unsafe-inline'
  - `test_csp_no_unsafe_eval`: Production CSP doesn't contain 'unsafe-eval'
  - `test_x_frame_options_deny`: X-Frame-Options header is DENY
  - `test_x_content_type_options`: X-Content-Type-Options is nosniff
**And** tests use `@override_settings(DEBUG=False)` for production simulation

Example:
```python
@override_settings(DEBUG=False)
def test_csp_no_unsafe_inline(self):
    self.client.force_login(self.user)
    response = self.client.get(reverse('home'))
    csp = response['Content-Security-Policy']
    self.assertNotIn('unsafe-inline', csp)
    self.assertNotIn('unsafe-eval', csp)
```

#### Scenario: Authentication security test prevents username enumeration

**Given** the file `tests/test_security.py`
**When** running `python manage.py test tests.test_security::AuthenticationSecurityTestCase`
**Then** the test `test_no_username_enumeration` passes:
  - Invalid username returns same error message as invalid password
  - Response messages are identical (prevents timing attacks)
**And** verifies generic error "Invalid username or password"

Example:
```python
def test_no_username_enumeration(self):
    # Try with non-existent username
    response1 = self.client.post(reverse('user-login'), {
        'username': 'nonexistent',
        'password': 'wrongpass'
    }, follow=True)

    # Try with valid username but wrong password
    response2 = self.client.post(reverse('user-login'), {
        'username': 'testuser',
        'password': 'wrongpass'
    }, follow=True)

    messages1 = list(response1.context['messages'])
    messages2 = list(response2.context['messages'])

    # Messages must be identical
    self.assertEqual(str(messages1[0]), str(messages2[0]))
```

#### Scenario: Rate limiting test suite validates brute force protection

**Given** the file `tests/test_security.py`
**When** running `python manage.py test tests.test_security::RateLimitingTestCase`
**Then** the test `test_login_rate_limiting` passes:
  - 10 rapid login attempts trigger rate limit
  - 11th attempt shows "too many" error message
  - Rate limit error is user-friendly
**And** test uses `@override_settings(RATELIMIT_ENABLE=True)`

Example:
```python
@override_settings(RATELIMIT_ENABLE=True)
def test_login_rate_limiting(self):
    # Attempt 10 logins
    for i in range(10):
        self.client.post(reverse('user-login'), {
            'username': f'user{i}',
            'password': 'wrongpass'
        })

    # 11th attempt should be rate limited
    response = self.client.post(reverse('user-login'), {
        'username': 'testuser',
        'password': 'wrongpass'
    }, follow=True)

    messages = list(response.context['messages'])
    self.assertTrue(any('too many' in str(m).lower() for m in messages))
```

#### Scenario: Input sanitization test suite validates XSS prevention

**Given** the file `tests/test_security.py`
**When** running `python manage.py test tests.test_security::InputSanitizationTestCase`
**Then** the following tests pass:
  - `test_xss_in_patient_name`: Script tags in patient name are escaped
  - `test_xss_in_medical_notes`: Script tags in notes are removed
  - `test_safe_html_preserved`: Allowed HTML in rich text is preserved
  - `test_filename_sanitization`: Path traversal in filenames prevented
**And** tests submit malicious input and verify sanitization

Example:
```python
def test_xss_in_patient_name(self):
    form_data = {
        'baby_name': '<script>alert("XSS")</script>Test Baby',
        # ... other required fields
    }
    form = PatientForm(data=form_data)
    if form.is_valid():
        patient = form.save(commit=False)
        self.assertNotIn('<script>', patient.baby_name)
        self.assertNotIn('alert', patient.baby_name)
```

### Requirement: Security test suite must achieve 100% pass rate

All security tests MUST pass before the change is considered complete.

#### Scenario: All security tests pass in test suite

**Given** all security test cases are implemented
**When** running `python manage.py test tests.test_security --verbosity=2`
**Then** the output shows:
```
Ran 15 tests in 3.245s
OK
```
**And** zero failures
**And** zero errors
**And** 100% pass rate

#### Scenario: Security tests are run in CI/CD pipeline

**Given** a continuous integration environment
**When** a pull request is submitted
**Then** security tests run automatically
**And** PR cannot merge if any security test fails
**And** ensures no security regressions

### Requirement: Security audit tools must validate production readiness

Security audit tooling (safety, bandit, OWASP ZAP) MUST be integrated and show no critical/high vulnerabilities.

#### Scenario: Dependency vulnerability scan shows no critical issues

**Given** the command `safety check --json`
**When** scanning Python dependencies
**Then** the report shows zero CRITICAL severity vulnerabilities
**And** the report shows zero HIGH severity vulnerabilities
**And** output is saved to `security/dependency_vulnerabilities.json`

#### Scenario: Python security linter shows no high severity code issues

**Given** the command `bandit -r ndas patients users video -f json`
**When** scanning Python code for security anti-patterns
**Then** the report shows zero HIGH severity issues
**And** the report shows zero CRITICAL severity issues
**And** output is saved to `security/code_security.json`
**And** common vulnerabilities detected:
  - SQL injection patterns
  - Hardcoded passwords/secrets
  - Unsafe pickle usage
  - Shell injection risks

#### Scenario: Django deployment check shows no warnings

**Given** the command `python manage.py check --deploy`
**When** validating production deployment configuration
**Then** the output shows zero errors
**And** the output shows zero warnings
**And** all Django security settings validated:
  - SECRET_KEY not using default
  - DEBUG=False in production
  - ALLOWED_HOSTS configured
  - Security middleware enabled
  - CSRF middleware enabled

#### Scenario: OWASP ZAP scan shows no high/critical vulnerabilities

**Given** OWASP ZAP automated scan on staging environment
**When** scanning all application URLs
**Then** the report shows zero HIGH risk vulnerabilities
**And** the report shows zero CRITICAL risk vulnerabilities
**And** automated security testing validates:
  - SQL injection protection
  - XSS protection (CSP validation)
  - CSRF protection
  - Clickjacking protection
  - Security headers presence

### Requirement: Performance benchmarks must be documented and validated

Performance improvements from Phase 2 MUST be measured and documented.

#### Scenario: Dashboard performance benchmark shows query reduction

**Given** the script `python scripts/benchmark_dashboard.py`
**When** running performance benchmark
**Then** the output shows:
  - Query count: ≤15 (down from ~50, ≥60% reduction)
  - Response time: <1.0 seconds with 1000+ patients
  - Average query time: documented
  - Top 5 slowest queries: listed
**And** results are saved to `performance_report.md`

Example output:
```
Dashboard Performance:
  Response time: 0.458 seconds (was 2.341s) - 80% improvement ✓
  Database queries: 14 (was 52) - 73% reduction ✓
  Avg query time: 0.033 seconds

Top 5 slowest queries:
  1. 0.045s - SELECT COUNT(*) FROM patients
  2. 0.038s - SELECT * FROM patients ... LIMIT 5
  ...
```

#### Scenario: Unit test coverage exceeds 80% threshold

**Given** the command `coverage run --source='.' manage.py test patients.tests.test_views`
**When** measuring test coverage for refactored code
**Then** the coverage report shows:
  - Overall coverage: ≥80%
  - patients/views.py: ≥80% coverage
  - Unified patient_manager function: 100% coverage
**And** coverage report saved with `coverage html`

### Requirement: Security audit script automates all validation checks

A comprehensive security audit script MUST run all security validation tools.

#### Scenario: Security audit script runs all checks

**Given** the script `bash scripts/security_audit.sh`
**When** executing the audit script
**Then** the script runs in sequence:
  1. `safety check --json` - Dependency vulnerabilities
  2. `bandit -r ...` - Python code security
  3. `python manage.py check --deploy` - Django deployment
  4. `python manage.py test tests.test_security` - Security test suite
**And** all outputs are saved to `security/` directory
**And** script exits with non-zero code if any check fails

Example script:
```bash
#!/bin/bash
echo "Running NDAS Security Audit..."

echo "\n1. Checking for vulnerable dependencies..."
safety check --json > security/dependency_vulnerabilities.json

echo "\n2. Running Python security linter..."
bandit -r ndas patients users video -f json -o security/code_security.json

echo "\n3. Checking Django deployment configuration..."
python manage.py check --deploy > security/django_deployment_check.txt

echo "\n4. Running Django security tests..."
python manage.py test tests.test_security --verbosity=2

echo "\nSecurity audit complete. Review reports in security/ directory."
```

## MODIFIED Requirements

None - this establishes new testing infrastructure.

## Cross-References

- **Validates**: `csrf-protection`, `csp-hardening`, `rate-limiting`, `input-sanitization`
- **Depends on**: Test database configuration, test fixtures
- **Related to**: `query-optimization` - Performance benchmarks
- **Tools**: safety, bandit, OWASP ZAP, django-debug-toolbar, coverage

## Implementation Notes

**Dependencies:**
```txt
# requirements.txt (development/testing)
safety==3.0.1
bandit==1.7.5
coverage==7.3.2
```

**Test File Structure:**
```
tests/
├── __init__.py
├── test_security.py          # Security test suite
├── test_integration.py       # Integration tests
└── fixtures/
    └── test_data.json

patients/tests/
├── __init__.py
└── test_views.py             # Patient view unit tests

scripts/
├── benchmark_dashboard.py    # Performance benchmarking
└── security_audit.sh         # Automated security audit

security/                     # Audit reports (gitignored)
├── dependency_vulnerabilities.json
├── code_security.json
└── django_deployment_check.txt
```

**Test Commands:**
```bash
# Run specific test suites
python manage.py test tests.test_security --verbosity=2
python manage.py test tests.test_integration
python manage.py test patients.tests.test_views

# Run all tests
python manage.py test

# Coverage measurement
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report

# Security audit
bash scripts/security_audit.sh

# Performance benchmark
python scripts/benchmark_dashboard.py

# Django deployment check
python manage.py check --deploy
```

**Success Criteria:**
- ✅ All security tests pass (100% pass rate)
- ✅ No critical/high vulnerabilities in safety scan
- ✅ No high severity issues in bandit scan
- ✅ Django deployment check shows zero warnings
- ✅ OWASP ZAP scan shows no high/critical risks
- ✅ Dashboard query count reduced by ≥60%
- ✅ Dashboard loads in <1s with 1000+ patients
- ✅ Test coverage ≥80% for refactored code

**Validation Workflow:**
1. Develop security hardening features (Phases 1-4)
2. Write corresponding security tests
3. Run security test suite → verify all pass
4. Run security audit script → verify clean reports
5. Run performance benchmarks → verify targets met
6. Measure test coverage → verify ≥80%
7. Manual OWASP ZAP scan on staging → verify no high/critical
8. Document results in security audit report
9. Approve for production deployment

**Rollback Strategy:**
- Tests don't affect runtime → low risk
- If tests fail after deployment: Indicates regression, rollback entire change
- Keep test suite even if feature rollback needed (prevents re-introduction of bugs)
