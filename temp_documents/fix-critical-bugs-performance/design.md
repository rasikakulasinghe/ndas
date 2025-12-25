# Design: Critical Bug Fixes and Performance Optimization

## Context

The NDAS codebase has accumulated 150+ bugs and performance issues across models, views, forms, templates, and middleware. A comprehensive analysis (BUG_AND_PERFORMANCE_ANALYSIS.md) identified issues ranging from catastrophic (models not saving) to optimization opportunities (template caching).

**Stakeholders:**
- Medical staff using the system (directly affected by bugs and performance)
- System administrators (resource usage, stability)
- Development team (maintainability, technical debt)

**Constraints:**
- No breaking changes allowed (medical data system in production)
- Database migrations must be reversible
- Must maintain HIPAA-aware security posture
- Windows development environment with SQLite/PostgreSQL support

## Goals / Non-Goals

**Goals:**
- Fix all critical bugs that prevent core functionality
- Eliminate N+1 query patterns causing performance degradation
- Close security vulnerabilities (XSS, validation gaps, rate limiting)
- Add missing database indexes for searchable fields
- Optimize resource usage (file handles, database connections, memory)
- Maintain backward compatibility with existing data and API

**Non-Goals:**
- Rewrite or refactor working code without performance/security justification
- Change UI/UX beyond what's required for bug fixes
- Migrate to different frameworks or major dependency upgrades
- Add new features (this is purely bug fixes and optimization)

## Decisions

### Decision 1: Phased Implementation Approach

**What:** Implement fixes in 4 phases based on severity and risk
**Why:**
- Critical bugs (Phase 1) must be fixed immediately to restore functionality
- Allows incremental testing and validation between phases
- Minimizes deployment risk by grouping related changes
- Enables rollback at phase boundaries if issues occur

**Alternatives considered:**
- Big-bang approach: Fix all issues at once
  - Rejected: Too risky, difficult to test, hard to rollback
- Fix on-demand as issues are reported
  - Rejected: Reactive approach leaves known critical bugs unfixed

### Decision 2: Use get_object_or_404() Pattern Universally

**What:** Replace all `.objects.get()` calls with `get_object_or_404()` in views
**Why:**
- Prevents unhandled DoesNotExist exceptions causing 500 errors
- Provides proper 404 responses for missing resources
- Django best practice for web views
- Improves user experience and error handling

**Alternatives considered:**
- Try/except blocks around each .objects.get()
  - Rejected: More verbose, error-prone, inconsistent
- Custom exception middleware
  - Rejected: Masks underlying issues, harder to debug

### Decision 3: Query Optimization Strategy

**What:** Use select_related() for foreign keys, prefetch_related() for reverse relations, and annotate() for aggregations
**Why:**
- Reduces N+1 queries systematically
- Django ORM best practices
- Measurable performance improvements (60-80% query reduction)
- Minimal code changes, no API breaks

**Implementation pattern:**
```python
# Before (N+1 queries)
assessments = GMAssessment.objects.filter(patient=patient)
# In template: {{ assessment.added_by.username }} triggers N queries

# After (optimized)
assessments = GMAssessment.objects.filter(patient=patient).select_related(
    'patient', 'added_by', 'last_edit_by', 'video_file'
)
# Single query with JOINs
```

**Alternatives considered:**
- Raw SQL queries
  - Rejected: Loses ORM benefits, harder to maintain, security risks
- Caching layer
  - Rejected: Adds complexity, doesn't solve root cause
- Database views
  - Rejected: Requires schema changes, less portable

### Decision 4: Model Property Refactoring for Patient

**What:** Convert expensive properties to manager methods with annotations
**Why:**
- Patient model has 20+ properties that trigger N+1 queries
- Properties called in templates cause hidden performance issues
- Manager methods make query cost explicit and controllable

**Pattern:**
```python
# Before (property - hidden cost)
@property
def isNewPatient(self):
    return not Video.objects.filter(patient=self.pk).exists()

# After (manager method with annotation)
class PatientQuerySet(models.QuerySet):
    def with_status_annotations(self):
        return self.annotate(
            is_new=~Exists(Video.objects.filter(patient=OuterRef('pk')))
        )

# Usage in views
patients = Patient.objects.with_status_annotations().filter(...)
# In template: {{ patient.is_new }} - no additional query
```

**Backward compatibility:**
- Keep existing properties as fallbacks
- Mark as deprecated with docstrings
- Gradually migrate templates to use annotated fields

**Alternatives considered:**
- Eager loading all relations
  - Rejected: Wastes memory when data not needed
- Remove properties entirely
  - Rejected: Breaking change, affects many templates

### Decision 5: Input Sanitization Approach

**What:** Use bleach library for HTML sanitization with strict allowlists
**Why:**
- Industry-standard library for HTML sanitization
- Configurable tag/attribute allowlists
- Well-tested against XSS attacks
- Already in Django ecosystem

**Configuration:**
```python
import bleach

ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li']
ALLOWED_ATTRS = {}

def clean_text_field(self):
    value = self.cleaned_data.get('field_name', '')
    return bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
```

**Alternatives considered:**
- django-bleach package
  - Considered: Good option but adds dependency
- Custom regex sanitization
  - Rejected: Error-prone, likely to miss edge cases
- No sanitization (use Django's auto-escaping)
  - Rejected: Doesn't prevent stored XSS

### Decision 6: File Handle Management

**What:** Use context managers (with statements) for all file operations
**Why:**
- Guarantees file closure even if exceptions occur
- Python best practice
- Prevents resource leaks
- Minimal code changes

**Pattern:**
```python
# Before (resource leak)
file_handle = open(file_path, 'rb')
response = FileResponse(file_handle, content_type=content_type)

# After (safe)
with open(file_path, 'rb') as file_handle:
    response = FileResponse(file_handle.read(), content_type=content_type)
```

**Alternatives considered:**
- StreamingHttpResponse for large files
  - Decision: Use for files >10MB, regular FileResponse for smaller
- Manual try/finally blocks
  - Rejected: More verbose than context managers

### Decision 7: Middleware Query Throttling

**What:** Cache session update timestamps to reduce database writes
**Why:**
- Current: UPDATE query on every authenticated request
- After: UPDATE only once per minute per user
- Reduces database load by 95%+ on session updates

**Implementation:**
```python
from django.core.cache import cache

cache_key = f"user_session_update_{request.user.id}_{session_key}"
last_update = cache.get(cache_key)

if last_update is None or (timezone.now() - last_update).seconds > 60:
    UserSession.objects.filter(...).update(last_activity=timezone.now())
    cache.set(cache_key, timezone.now(), 120)
```

**Alternatives considered:**
- Remove activity tracking
  - Rejected: Required for audit compliance
- Update on logout only
  - Rejected: Loses session timeout functionality
- Use Redis TTL directly
  - Considered: Good option for production, cache layer works for both dev/prod

### Decision 8: Database Index Strategy

**What:** Add indexes to all fields used in WHERE, JOIN, or ORDER BY clauses
**Why:**
- Significant query performance improvements (10-100x)
- Minimal storage overhead
- Django provides db_index=True for easy implementation

**Fields to index:**
- Search fields: IndicationsForGMA.title, DiagnosisList.title
- Filter fields: IndicationsForGMA.level
- Lookup fields: DiagnosisList.abr, CustomUser.mobile_primary
- Foreign keys: Already indexed by Django

**Alternatives considered:**
- Composite indexes
  - Decision: Add only if query profiling shows need
- Full-text search indexes
  - Deferred: Requires PostgreSQL-specific features

## Risks / Trade-offs

### Risk 1: Migration Failures
**Risk:** Database migrations may fail if data doesn't meet new constraints
**Mitigation:**
- Check for duplicate data before adding unique constraints
- Provide data migration scripts for cleanup
- Test migrations on copy of production database
- Document rollback procedures

### Risk 2: Query Optimization Regressions
**Risk:** Adding select_related/prefetch_related could slow down queries that don't need the data
**Mitigation:**
- Profile with database query logging and EXPLAIN ANALYZE before and after
- Only add for fields actually used in templates
- Use prefetch_related for reverse relations (many-to-many)
- Monitor query times in production

### Risk 3: Template Changes
**Risk:** Moving computations from templates to views may break custom templates
**Mitigation:**
- Keep backward compatibility by maintaining old properties
- Document deprecation timeline
- Test all templates after changes
- Gradual rollout by template section

### Risk 4: Cache Invalidation
**Risk:** Middleware caching could show stale session data
**Mitigation:**
- Use short TTL (120 seconds)
- Clear cache on logout
- Monitor for session timeout issues
- Fall back to database if cache unavailable

### Risk 5: Rate Limiting False Positives
**Risk:** Legitimate users may hit rate limits
**Mitigation:**
- Set reasonable limits (10/min for creates, 5/min for deletes)
- Separate limits for user and IP
- Log rate limit hits for monitoring
- Provide clear error messages

## Migration Plan

### Phase 1: Critical Fixes (Week 1)
1. Create feature branch: `fix/phase1-critical-bugs`
2. Fix model save methods (DevelopmentalAssessment, etc.)
3. Replace .objects.get() with get_object_or_404()
4. Fix file handle leaks
5. Add URL trailing slashes
6. Fix error message display
7. Test thoroughly with existing data
8. Deploy to staging
9. Run smoke tests
10. Deploy to production with monitoring

**Rollback:** Git revert if critical issues found

### Phase 2: Performance & Security (Week 2)
1. Create branch: `fix/phase2-performance`
2. Add select_related() to views
3. Optimize middleware queries
4. Add input sanitization
5. Add profile picture validation
6. Add rate limiting
7. Performance testing using database query logging and profiling
8. Security testing for XSS
9. Deploy to staging
10. Load testing
11. Deploy to production

**Rollback:** Database rollback not needed (no schema changes)

### Phase 3: Database Optimization (Week 3)
1. Create branch: `fix/phase3-database`
2. Check for duplicate data in DiagnosisList, IndicationsForGMA
3. Clean duplicates if found
4. Create migrations for indexes and constraints
5. Test migrations on staging database copy
6. Apply migrations to staging
7. Verify query performance improvements
8. Create rollback migration scripts
9. Deploy to production during maintenance window
10. Monitor for migration issues

**Rollback:**
```bash
python manage.py migrate patients <previous_migration>
python manage.py migrate users <previous_migration>
```

### Phase 4: Template Optimization (Week 4)
1. Create branch: `fix/phase4-templates`
2. Add template caching
3. Move computations to views
4. Optimize static files
5. Test page load times
6. Verify no visual regressions
7. Deploy to staging
8. A/B test performance
9. Deploy to production

**Rollback:** Git revert if rendering issues

## Deployment Strategy

**Prerequisites:**
- Full database backup before migrations
- Staging environment testing
- Performance baseline measurements
- Rollback scripts prepared

**Deployment order:**
1. Phase 1 (Critical) - Immediate deployment after testing
2. Phase 2 (Performance) - Deploy after Phase 1 stable for 3 days
3. Phase 3 (Database) - Deploy during maintenance window
4. Phase 4 (Templates) - Deploy after Phase 3 verified

**Monitoring:**
- Error rates (Sentry)
- Query performance (database query logs, slow query log)
- Page load times (browser metrics)
- User session timeout issues
- Rate limit hits

## Open Questions

1. **Should we add Celery for video processing optimization?**
   - Current: FFmpeg runs synchronously in save method
   - Proposal: Move to background task
   - Decision: Deferred to separate change (not a bug fix)

2. **Should we migrate from SQLite to PostgreSQL in development?**
   - Current: SQLite for dev, PostgreSQL for prod
   - Issue: Some optimizations only work on PostgreSQL
   - Decision: Document PostgreSQL-specific features, keep SQLite for simplicity

3. **What's the deprecation timeline for Patient model properties?**
   - Proposal: Keep for 6 months with deprecation warnings
   - Decision: Document in CHANGELOG, remove in next major version

4. **Should we add automated performance regression testing?**
   - Proposal: Add query count assertions to tests
   - Decision: Yes, add to Phase 2 tasks
