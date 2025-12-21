# Harden NDAS Security and Performance

## Summary
Comprehensive system hardening addressing critical security vulnerabilities, performance bottlenecks, code quality issues, and establishing robust testing infrastructure. Implements 5-phase improvement plan covering 23 security issues, 5 performance problems, and 12 code quality concerns identified in security audit.

## Problem
NDAS currently has **MODERATE** system health with critical blockers preventing production deployment:

**Security (CRITICAL - 23 issues):**
- CSRF exemption on authenticated API endpoint (users/views.py:471)
- Production CSP allows 'unsafe-inline' and 'unsafe-eval' (undermines XSS protection)
- File-based email backend (password resets won't work in production)
- No rate limiting on authentication endpoints (brute force vulnerable)
- Timing attack vulnerability in login (username enumeration possible)

**Performance (HIGH - 5 issues):**
- N+1 queries in dashboard view (~50 queries loading all patients/videos)
- Missing select_related in patient manager views
- Inefficient counting without pagination

**Code Quality (MEDIUM - 12 issues):**
- ~2000 lines of duplicated code (8 patient manager functions)
- Dead/commented code in production files
- Missing docstrings on public functions
- Inconsistent error handling patterns

**Testing Gap:**
- No security test suite
- No performance benchmarks
- Insufficient test coverage for critical views

## Goals
Transform NDAS from MODERATE health to **PRODUCTION-READY** status:

1. **Security Hardening**: Eliminate all critical/high security vulnerabilities
2. **Performance Optimization**: Dashboard < 1s load time, 60%+ query reduction
3. **Code Quality**: DRY principles, comprehensive documentation, error handling
4. **Test Coverage**: 80%+ coverage with security/performance/integration tests
5. **Maintainability**: Standardized patterns, monitoring tools, audit capability

## Success Criteria

### Phase 1: Critical Security ✅
- [ ] All API endpoints require CSRF protection or proper token auth
- [ ] Production CSP does not contain 'unsafe-inline' or 'unsafe-eval'
- [ ] Email backend configured for production (emails send successfully)
- [ ] Rate limiting active on all authentication endpoints
- [ ] No timing attacks possible on login

### Phase 2: Performance ✅
- [ ] Dashboard loads in < 1 second with 1000+ patients
- [ ] Query count reduced by at least 60%
- [ ] No N+1 queries in patient manager views

### Phase 3: Code Quality ✅
- [ ] Patient manager functions reduced from 8 to 1
- [ ] No commented-out code in production
- [ ] All public functions have docstrings
- [ ] Consistent error handling across all views

### Phase 4: Security Hardening ✅
- [ ] Generic error messages prevent username enumeration
- [ ] All security headers present and validated
- [ ] User input sanitized in all forms
- [ ] Security test suite passes 100%

### Phase 5: Testing ✅
- [ ] Unit test coverage > 80% for refactored code
- [ ] All integration tests pass
- [ ] Performance benchmarks documented
- [ ] OWASP ZAP scan shows no high/critical vulnerabilities

## Non-Goals
- Migrating from SQLite to PostgreSQL (infrastructure decision)
- Implementing new features or functionality
- Changing UI/UX or visual design
- Modifying AdminLTE framework or Bootstrap versions
- Retroactive data sanitization (only new inputs)

## Scope

### In Scope
**Phase 1 - Critical Security (Week 1, 10 hours):**
- Remove CSRF exemption from API endpoint
- Configure production CSP without unsafe directives
- Configure SMTP email backend for production
- Add django-ratelimit to authentication endpoints
- Fix timing attack in login flow

**Phase 2 - Performance (Week 2, 7 hours):**
- Optimize dashboard queries with select_related/prefetch_related
- Add select_related to patient manager views
- Install django-debug-toolbar for development monitoring

**Phase 3 - Code Quality (Weeks 3-4, 19 hours):**
- Consolidate 8 patient manager functions into unified view
- Remove dead/commented code
- Add Google-style docstrings to all public functions
- Standardize error handling with decorator pattern

**Phase 4 - Security Hardening (Week 5, 15 hours):**
- Fix authentication timing attacks
- Add security headers validation middleware
- Implement input sanitization with bleach library
- Create comprehensive security test suite

**Phase 5 - Testing (Week 6, 22 hours):**
- Unit tests for refactored views
- Integration tests for patient workflows
- Performance benchmarking with django-silk
- Security audit validation (safety, bandit, OWASP ZAP)

### Out of Scope
- Database migration scripts (SQLite → PostgreSQL)
- Cloud deployment configuration
- CI/CD pipeline setup
- Feature additions or enhancements
- Third-party API integrations
- Frontend framework changes

## Affected Areas

### Modified Components
- `users/views.py` - Login flow, API endpoints, rate limiting
- `patients/views.py` - Dashboard, patient manager consolidation
- `ndas/settings.py` - Security headers, email config, CSP policy
- `requirements.txt` - Add 8 new dependencies
- `ndas/custom_codes/` - New error handlers, sanitization, security middleware

### New Components
- `ndas/custom_codes/error_handlers.py` - Standardized error handling decorators
- `ndas/custom_codes/sanitization.py` - Input sanitization utilities
- `ndas/custom_codes/security_middleware.py` - Security headers validation
- `tests/test_security.py` - Security test suite
- `tests/test_integration.py` - Integration test suite
- `patients/tests/test_views.py` - Patient view unit tests
- `scripts/benchmark_dashboard.py` - Performance benchmarking
- `scripts/security_audit.sh` - Automated security audit

### Potentially Affected (External Dependencies)
- All templates with inline scripts (CSP nonce required)
- Forms requiring sanitization updates
- Views using old patient_manager_* functions

## Dependencies
**New Python Packages (Production):**
- `django-ratelimit==4.1.0` - Rate limiting for authentication
- `bleach==6.1.0` - HTML sanitization for XSS prevention

**New Python Packages (Development/Testing):**
- `django-debug-toolbar==4.2.0` - Query monitoring in development
- `django-silk==5.0.4` - Performance profiling
- `safety==3.0.1` - Dependency vulnerability scanner
- `bandit==1.7.5` - Python security linter

**External Tools (Manual Installation):**
- OWASP ZAP - Security scanning (manual download)

## Risks & Mitigation

### High Risk
**Risk**: CSP changes break inline scripts in templates
**Mitigation**: Use CSP nonces, update all templates incrementally, test thoroughly with browser DevTools

**Risk**: URL refactoring breaks bookmarks/external links
**Mitigation**: Keep old URLs as redirects to new consolidated endpoints for 6 months deprecation period

**Risk**: Patient manager refactoring introduces subtle filtering bugs
**Mitigation**: Comprehensive unit tests for all filter types, side-by-side comparison testing

### Medium Risk
**Risk**: Rate limiting blocks legitimate users
**Mitigation**: Conservative limits (5/min IP, 3/min username), clear error messages, logging

**Risk**: Performance optimizations don't achieve 60% query reduction
**Mitigation**: Baseline benchmarks before changes, iterative optimization with django-silk profiling

**Risk**: New dependencies introduce vulnerabilities
**Mitigation**: Use `safety check` on all new packages, pin versions, regular updates

### Low Risk
**Risk**: Docstring additions take longer than estimated
**Mitigation**: Prioritize critical views, defer non-public functions to Phase 6 if needed

## Timeline
- **Week 1**: Phase 1 - Critical Security (MANDATORY before production)
- **Week 2**: Phase 2 - Performance Optimization
- **Weeks 3-4**: Phase 3 - Code Quality Refactoring
- **Week 5**: Phase 4 - Security Hardening
- **Week 6**: Phase 5 - Testing & Validation

**Total Estimated Effort**: 73 hours (6 weeks)
**Minimum Viable Production**: 19 hours (Phase 1 + 2.1 + 4.1)

## Alternatives Considered

### Alternative 1: Phased Rollout (5 Separate Changes)
**Rejected**: Dependencies between phases too complex, duplicates validation effort, delays security fixes

### Alternative 2: Security-Only Quick Fix
**Rejected**: Leaves performance/quality debt, re-work needed later when issues surface under load

### Alternative 3: Use Django REST Framework for API
**Rejected**: Overkill for single API endpoint, significant refactoring overhead, adds complexity

### Alternative 4: Keep Patient Manager Duplication
**Rejected**: 2000 lines of duplicated code unmaintainable, any bug fix needs 8 updates

## Open Questions
None - all clarifications resolved:
- ✅ Single comprehensive change preferred
- ✅ Include all dependencies in requirements.txt
- ✅ Full refactoring freedom for optimization
- ✅ Sanitize new inputs only (no retroactive migration)
