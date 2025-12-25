# Implementation Tasks

## Phase 1: Critical Fixes (MUST FIX IMMEDIATELY)

### 1.1 Model Save Method Fixes
- [x] 1.1.1 Fix `DevelopmentalAssessment.save()` - add `super().save(*args, **kwargs)` at line 2751
- [x] 1.1.2 Test DevelopmentalAssessment creation and persistence
- [x] 1.1.3 Verify existing records still load correctly

### 1.2 Model String Representation
- [x] 1.2.1 Fix `DiagnosisList.__str__()` - change `self.title` to `self.abr` at line 2275
- [x] 1.2.2 Test admin interface displays "Title (Abbreviation)"
- [x] 1.2.3 Verify form dropdowns show correct format

### 1.3 Model Property Issues
- [x] 1.3.1 Search codebase for usage of `getIndicationList` property
- [x] 1.3.2 If unused, remove property from IndicationsForGMA model
- [x] 1.3.3 If used, convert to class method `get_all_indications()`
- [x] 1.3.4 Update callers if necessary

### 1.4 URL Trailing Slashes
- [x] 1.4.1 Add trailing slash to `path("print/", ...)` at line 12 in patients/urls.py
- [x] 1.4.2 Add trailing slashes to manager URLs (lines 19-27)
- [x] 1.4.3 Add trailing slash to attachment manager URL (line 49)
- [x] 1.4.4 Add trailing slashes to assessment manager URLs (lines 64-68)
- [x] 1.4.5 Test all URLs return 200 without redirect
- [x] 1.4.6 Verify POST data is not lost

### 1.5 Replace .objects.get() in patients/views.py
- [x] 1.5.1 Verify `get_object_or_404` is imported
- [x] 1.5.2 Replace Patient.objects.get at lines: 377, 592, 1068, 1091, 1092, 1390, 1608, 1716, 1878, 2167, 2488, 2699, 2887, 3074, 3276, 3505, 3650
- [x] 1.5.3 Test accessing non-existent patient IDs returns 404
- [x] 1.5.4 Verify no 500 errors occur for missing objects

### 1.6 Replace .objects.get() in users/views.py
- [x] 1.6.1 Replace CustomUser.objects.get at line 215 with `get_object_or_404(CustomUser, id=pk)`
- [x] 1.6.2 Replace CustomUser.objects.get at line 221 with `get_object_or_404(CustomUser, username=username)`
- [x] 1.6.3 Replace UserSession.objects.get at line 443 with `get_object_or_404(UserSession, id=session_id, user=request.user)`
- [x] 1.6.4 Test 404 responses for invalid users/sessions

### 1.7 Fix File Handle Resource Leaks
- [x] 1.7.1 Fix download_report (lines 320-321) - use context manager
- [x] 1.7.2 Fix download_gm_assessment_pdf (lines 341-342) - use context manager
- [x] 1.7.3 Fix download_hine_assessment_pdf (lines 360-361) - use context manager
- [x] 1.7.4 Fix download_da_assessment_pdf (lines 379-380) - use context manager
- [x] 1.7.5 Fix download_cdic_assessment_pdf (lines 398-399) - use context manager
- [x] 1.7.6 Fix download_gpa_assessment_pdf (lines 417-418) - use context manager
- [x] 1.7.7 Test downloads work correctly
- [x] 1.7.8 Verify file handles close with `lsof` or Process Explorer

### 1.8 Optimize Middleware Database Queries
- [x] 1.8.1 Add cache import to users/middleware.py
- [x] 1.8.2 Implement session update throttling with 60-second cache
- [x] 1.8.3 Test session updates occur at most once per minute
- [x] 1.8.4 Monitor database query reduction using query logging

### 1.9 Fix Error Message Display
- [x] 1.9.1 Change `messages.success` to `messages.error` at line 1055 in patients/views.py
- [x] 1.9.2 Change `messages.success` to `messages.error` at line 1742
- [x] 1.9.3 Change `messages.success` to `messages.error` at line 2152
- [x] 1.9.4 Change `messages.success` to `messages.error` at line 2360
- [x] 1.9.5 Test form errors display in red/error style

### 1.10 Phase 1 Testing and Deployment
- [x] 1.10.1 Run full test suite: `python manage.py test`
- [x] 1.10.2 Manual testing of all critical fixes
- [x] 1.10.3 Create git branch: `git checkout -b fix/phase1-critical-bugs`
- [x] 1.10.4 Commit all Phase 1 changes
- [ ] 1.10.5 Deploy to staging environment
- [ ] 1.10.6 Run smoke tests on staging
- [ ] 1.10.7 Deploy to production with monitoring
- [ ] 1.10.8 Monitor for 24 hours for issues

## Phase 2: High Priority Fixes (Performance & Security)

### 2.1 Add select_related to Assessment Managers
- [x] 2.1.1 Fix `assessment_manager()` at line 1211 - add select_related('patient', 'added_by', 'last_edit_by', 'video_file')
- [x] 2.1.2 Fix `assessment_manager_recent()` at line 1239
- [x] 2.1.3 Fix `assessment_manager_normal()` at line 1270
- [x] 2.1.4 Fix `assessment_manager_abnormal()` at line 1301
- [x] 2.1.5 Fix `assessment_manager_informed()` at line 1332
- [x] 2.1.6 Fix `assessment_manager_not_informed()` at line 1363
- [x] 2.1.7 Test query count reduction using database query logging
- [x] 2.1.8 Benchmark: Should go from ~50 queries to ~5 for 10 assessments

### 2.2 Add select_related to patient_view()
- [x] 2.2.1 Add select_related to Video query (line 390)
- [x] 2.2.2 Add select_related to Attachment query (line 395)
- [x] 2.2.3 Add select_related to GMAssessment query (line 400)
- [x] 2.2.4 Add select_related to HINEAssessment query (line 405)
- [x] 2.2.5 Add select_related to DevelopmentalAssessment query (line 410)
- [x] 2.2.6 Add select_related to CDICRecord query (line 412)
- [x] 2.2.7 Test patient detail page query count using database logging
- [x] 2.2.8 Verify significant query count reduction

### 2.3 Refactor Patient Model Properties
- [ ] 2.3.1 Create PatientQuerySet and PatientManager classes in patients/models.py
- [ ] 2.3.2 Implement `with_status_annotations()` method
- [ ] 2.3.3 Implement `with_related_data()` method
- [ ] 2.3.4 Add manager to Patient model: `objects = PatientManager()`
- [ ] 2.3.5 Update existing properties to use annotations when available
- [ ] 2.3.6 Mark properties as deprecated in docstrings
- [ ] 2.3.7 Update patient_manager view to use `Patient.objects.with_full_data()`
- [ ] 2.3.8 Test extensively - verify all views still work
- [ ] 2.3.9 Gradual template migration to use annotated fields

### 2.4 Add Profile Picture Validation
- [x] 2.4.1 Add `clean_profile_picture()` method to users/forms.py after line 245
- [x] 2.4.2 Implement file size validation (5MB max)
- [x] 2.4.3 Implement file extension validation (JPG, JPEG, PNG only)
- [x] 2.4.4 Implement PIL image verification
- [x] 2.4.5 Implement dimension validation (4000x4000 max)
- [x] 2.4.6 Add imports: `import os` and `from PIL import Image`
- [x] 2.4.7 Test uploading valid images
- [x] 2.4.8 Test uploading oversized images (should fail)
- [x] 2.4.9 Test uploading non-images renamed to .jpg (should fail)
- [x] 2.4.10 Test uploading oversized dimensions (should fail)

### 2.5 Optimize Video Filters
- [ ] 2.5.1 Replace video filter at lines 259-268 with Exists() subquery
- [ ] 2.5.2 Replace video filter at lines 360-364 with Exists() subquery
- [ ] 2.5.3 Add import: `from django.db.models import Exists, OuterRef`
- [ ] 2.5.4 Test "new videos only" filter
- [ ] 2.5.5 Verify query performance using database query logging

### 2.6 Add Input Sanitization to problemlist Forms
- [ ] 2.6.1 Install bleach: `pip install bleach`
- [ ] 2.6.2 Add bleach import to problemlist/forms.py
- [ ] 2.6.3 Define ALLOWED_TAGS and ALLOWED_ATTRS constants
- [ ] 2.6.4 Add `clean_name()` method (no HTML allowed)
- [ ] 2.6.5 Add `clean_description()` method (limited HTML)
- [ ] 2.6.6 Add `clean_action_taken()` method (limited HTML)
- [ ] 2.6.7 Add `clean_outcome()` method (limited HTML)
- [ ] 2.6.8 Add `clean_comments()` method (limited HTML)
- [ ] 2.6.9 Test submitting forms with HTML/JavaScript
- [ ] 2.6.10 Verify malicious code is stripped

### 2.7 Add Rate Limiting to CRUD Operations
- [ ] 2.7.1 Verify django-ratelimit is installed
- [ ] 2.7.2 Add ratelimit decorators to patient_add (10/min user, 20/min IP)
- [ ] 2.7.3 Add ratelimit decorators to patient_edit (10/min user, 20/min IP)
- [ ] 2.7.4 Add ratelimit decorators to patient_delete (5/min user, 10/min IP)
- [ ] 2.7.5 Add ratelimit to all assessment CRUD operations
- [ ] 2.7.6 Add ratelimit to video CRUD operations
- [ ] 2.7.7 Add ratelimit to attachment operations
- [ ] 2.7.8 Add ratelimit to user management operations
- [ ] 2.7.9 Test rapid form submissions
- [ ] 2.7.10 Verify rate limiting activates and shows appropriate error

### 2.8 Optimize Multiple filter().count() Calls
- [x] 2.8.1 Fix hine_assessment_manager (lines 2855-2857) with aggregate()
- [x] 2.8.2 Fix hine_assessment_manager_by_patients (lines 2932-2934)
- [x] 2.8.3 Fix da_assessment_manager (lines 3242-3243)
- [ ] 2.8.4 Fix da_assessment_manager_by_patients (lines 3348-3349)
- [ ] 2.8.5 Fix cdic managers (lines 2451, 2548)
- [ ] 2.8.6 Fix bookmark_manager (lines 1490-1491)
- [x] 2.8.7 Add imports: `from django.db.models import Count, Case, When, IntegerField, Q`
- [x] 2.8.8 Test counts are accurate
- [x] 2.8.9 Verify query reduction using database query logging

### 2.9 Phase 2 Testing and Deployment
- [ ] 2.9.1 Run performance tests using database query logging and profiling
- [ ] 2.9.2 Run security tests for XSS and rate limiting
- [ ] 2.9.3 Create git branch: `git checkout -b fix/phase2-performance`
- [ ] 2.9.4 Commit all Phase 2 changes
- [ ] 2.9.5 Deploy to staging
- [ ] 2.9.6 Load testing on staging
- [ ] 2.9.7 Deploy to production
- [ ] 2.9.8 Monitor performance metrics

## Phase 3: Medium Priority Fixes (Database Optimization)

### 3.1 Add Missing Database Indexes
- [ ] 3.1.1 Add `db_index=True` to IndicationsForGMA.title (line 2251)
- [ ] 3.1.2 Add `db_index=True` to IndicationsForGMA.level (line 2252)
- [ ] 3.1.3 Add `db_index=True` to DiagnosisList.abr (line 2267)
- [ ] 3.1.4 Add `db_index=True` to DiagnosisList.title (line 2268)
- [ ] 3.1.5 Add `db_index=True` to CustomUser.mobile_primary (line 32)
- [ ] 3.1.6 Create migration: `python manage.py makemigrations`
- [ ] 3.1.7 Test migration on staging database copy
- [ ] 3.1.8 Run migration: `python manage.py migrate`
- [ ] 3.1.9 Verify indexes created in database
- [ ] 3.1.10 Test search/filter operations for performance

### 3.2 Fix DiagnosisList TextField to CharField
- [ ] 3.2.1 Check existing data max length: `DiagnosisList.objects.annotate(title_len=Length('title')).aggregate(Max('title_len'))`
- [ ] 3.2.2 Verify max length < 255 characters
- [ ] 3.2.3 Change DiagnosisList.title to CharField(max_length=255, db_index=True)
- [ ] 3.2.4 Create migration: `python manage.py makemigrations`
- [ ] 3.2.5 Test migration on staging
- [ ] 3.2.6 Run migration: `python manage.py migrate`
- [ ] 3.2.7 Verify all diagnosis titles display correctly

### 3.3 Add Unique Constraints
- [ ] 3.3.1 Check for duplicate DiagnosisList.abr: `DiagnosisList.objects.values('abr').annotate(count=Count('id')).filter(count__gt=1)`
- [ ] 3.3.2 Check for duplicate IndicationsForGMA.title
- [ ] 3.3.3 Check for duplicate Help.title
- [ ] 3.3.4 Clean up duplicates if found
- [ ] 3.3.5 Add `unique=True` to DiagnosisList.abr
- [ ] 3.3.6 Add `unique=True` to IndicationsForGMA.title
- [ ] 3.3.7 Add `unique=True` to Help.title
- [ ] 3.3.8 Create migration: `python manage.py makemigrations`
- [ ] 3.3.9 Test migration on staging
- [ ] 3.3.10 Run migration: `python manage.py migrate`
- [ ] 3.3.11 Test creating duplicate entries (should fail)

### 3.4 Fix Subscription.update_status Race Condition
- [ ] 3.4.1 Import transaction at top of users/models.py
- [ ] 3.4.2 Wrap status update in `transaction.atomic()` block
- [ ] 3.4.3 Add `select_for_update()` to lock row
- [ ] 3.4.4 Move `_clear_cache()` to after transaction commits
- [ ] 3.4.5 Test concurrent subscription updates
- [ ] 3.4.6 Verify no race conditions occur

### 3.5 Add select_related to User Activity Logs
- [x] 3.5.1 Add `.select_related('user')` to query at line 421 in users/views.py
- [x] 3.5.2 Add `.select_related('user')` to query at line 818
- [x] 3.5.3 Add `.select_related('user')` to query at line 837
- [x] 3.5.4 Test activity log pages using database query logging
- [x] 3.5.5 Verify query count reduction

### 3.6 Optimize Username List Queries
- [x] 3.6.1 Optimized `recent_users` query at line 538 with `.only()` to fetch limited fields
- [x] 3.6.2 Note: Line numbers from analysis shifted due to Phase 1-2 changes
- [x] 3.6.3 Used `.only('id', 'username', 'position', 'is_active', 'date_joined')` for dashboard
- [x] 3.6.4 Test dropdowns/lists still work correctly
- [x] 3.6.5 Verify memory usage reduction

### 3.7 Add Video MIME Type Validation
- [x] 3.7.1 Install python-magic: `pip install python-magic-bin` (Windows) - COMPLETED
- [x] 3.7.2 Add MIME type validation to `clean_video_file()` in video/forms.py
- [x] 3.7.3 Define allowed MIME types list (9 video MIME types including variants)
- [x] 3.7.4 Read file header (2048 bytes) and verify MIME type
- [x] 3.7.5 Reset file pointer after validation
- [x] 3.7.6 Logging added for security monitoring
- [x] 3.7.7 Graceful fallback if python-magic not available

### 3.8 Add Date Cross-Validation in problemlist Forms
- [x] 3.8.1 Add `clean()` method to problemlist forms
- [x] 3.8.2 Validate date_identified >= date_of_onset
- [x] 3.8.3 Validate date_resolved >= date_of_onset
- [x] 3.8.4 Raise appropriate ValidationError with field-specific messages
- [x] 3.8.5 Test submitting forms with invalid date combinations
- [x] 3.8.6 Verify validation errors display correctly

### 3.9 Move Filename Sanitization Earlier
- [ ] 3.9.1 Create upload_to callable function in patients/models.py
- [ ] 3.9.2 Implement sanitization in upload_to function
- [ ] 3.9.3 Update Attachment.file field to use callable
- [ ] 3.9.4 Remove sanitization from form clean method
- [ ] 3.9.5 Test uploading files with dangerous names
- [ ] 3.9.6 Verify sanitization happens before storage

### 3.10 Improve Birth Weight Validation
- [ ] 3.10.1 Create comprehensive validation ranges dictionary in Patient.clean()
- [ ] 3.10.2 Add validation for 20-23 weeks (300-700g)
- [ ] 3.10.3 Add validation for 24-27 weeks (400-1200g)
- [ ] 3.10.4 Add validation for 28-31 weeks (800-2000g)
- [ ] 3.10.5 Add validation for 32-36 weeks (1200-3000g)
- [ ] 3.10.6 Add validation for 37-44 weeks (2000-5000g)
- [ ] 3.10.7 Test various POG/weight combinations
- [ ] 3.10.8 Verify appropriate validation errors

### 3.11 Phase 3 Testing and Deployment
- [ ] 3.11.1 Full database backup before migrations
- [ ] 3.11.2 Test all migrations on staging database copy
- [ ] 3.11.3 Create git branch: `git checkout -b fix/phase3-database`
- [ ] 3.11.4 Commit all Phase 3 changes
- [ ] 3.11.5 Deploy to staging during maintenance window
- [ ] 3.11.6 Verify migrations applied successfully
- [ ] 3.11.7 Run query performance tests
- [ ] 3.11.8 Create rollback migration scripts
- [ ] 3.11.9 Deploy to production during maintenance window
- [ ] 3.11.10 Monitor for migration issues

## Phase 4: Low Priority Optimizations (Maintainability)

### 4.1 Add App Namespaces to URLs
- [ ] 4.1.1 Add `app_name = 'patients'` to patients/urls.py
- [ ] 4.1.2 Add `app_name = 'users'` to users/urls.py
- [ ] 4.1.3 Add `app_name = 'problemlist'` to problemlist/urls.py
- [ ] 4.1.4 Update all URL references in templates to use namespaces
- [ ] 4.1.5 Update all reverse() calls in views
- [ ] 4.1.6 Test all URL reversals work correctly

### 4.2 Add Meta Classes to Models
- [ ] 4.2.1 Add Meta class to IndicationsForGMA with verbose_name, ordering, indexes
- [ ] 4.2.2 Add Meta class to DiagnosisList with verbose_name, ordering, indexes
- [ ] 4.2.3 Test admin interface displays correct names
- [ ] 4.2.4 Verify default ordering works

### 4.3 Add Template Fragment Caching
- [ ] 4.3.1 Add `{% load cache %}` to patients/manager.html
- [ ] 4.3.2 Cache filter controls (lines 77-159) for 3600 seconds
- [ ] 4.3.3 Cache pagination controls (lines 394-471) for 600 seconds with page key
- [ ] 4.3.4 Repeat for assessment/manager.html
- [ ] 4.3.5 Repeat for video/manager.html
- [ ] 4.3.6 Configure Django cache backend in settings
- [ ] 4.3.7 Test pages update correctly
- [ ] 4.3.8 Test cache clearing on data changes

### 4.4 Move Heavy Computations from Templates to Views
- [ ] 4.4.1 Calculate patient ages in patient_view and pass as context
- [ ] 4.4.2 Calculate corrected ages in view
- [ ] 4.4.3 Pre-filter RC items in view
- [ ] 4.4.4 Update templates to use context variables instead of properties
- [ ] 4.4.5 Test all patient views display correctly
- [ ] 4.4.6 Verify performance improvement using database query logging

### 4.5 Optimize Delete Modals
- [ ] 4.5.1 Create single delete modal outside loop in assessment/manager.html
- [ ] 4.5.2 Add JavaScript function to populate modal dynamically
- [ ] 4.5.3 Replace loop-generated modals with button onclick calls
- [ ] 4.5.4 Repeat for video/manager.html
- [ ] 4.5.5 Test delete functionality works for all items
- [ ] 4.5.6 Verify modal content updates correctly

### 4.6 Add Static File Optimization
- [ ] 4.6.1 Add preload links for critical CSS in templates/src/base.html
- [ ] 4.6.2 Add defer attribute to non-critical JavaScript
- [ ] 4.6.3 Keep jQuery synchronous (required for other scripts)
- [ ] 4.6.4 Test page load times with browser dev tools
- [ ] 4.6.5 Verify all JavaScript still works with defer
- [ ] 4.6.6 Measure First Contentful Paint and Time to Interactive

### 4.7 Add Prefetch to Template Queries
- [ ] 4.7.1 Add prefetch_related to patient_view for indecation_for_gma, problem_list, diagnosis
- [ ] 4.7.2 Pre-calculate counts in view instead of template
- [ ] 4.7.3 Update templates to use prefetched data
- [ ] 4.7.4 Test using database query logging - verify no template queries
- [ ] 4.7.5 Repeat for other views with template queries

### 4.8 Change Temporary Redirects to Permanent
- [ ] 4.8.1 Verify 6-month deprecation period has passed
- [ ] 4.8.2 Change RedirectView to `permanent=True` for deprecated URLs
- [ ] 4.8.3 Test browser caches 301 redirects
- [ ] 4.8.4 Document in CHANGELOG

### 4.9 Add Cache Headers to File Downloads
- [ ] 4.9.1 Add Cache-Control header to download_report
- [ ] 4.9.2 Add Last-Modified header using file timestamp
- [ ] 4.9.3 Add ETag header using report ID + format hash
- [ ] 4.9.4 Repeat for all report download functions
- [ ] 4.9.5 Test downloading same report twice
- [ ] 4.9.6 Verify browser caching behavior

### 4.10 Add HTTP Method Restrictions
- [ ] 4.10.1 Import decorators: `from django.views.decorators.http import require_http_methods, require_GET, require_POST`
- [ ] 4.10.2 Add `@require_GET` to all detail/list views
- [ ] 4.10.3 Add `@require_http_methods(["GET", "POST"])` to all form views
- [ ] 4.10.4 Add `@require_POST` to all delete views
- [ ] 4.10.5 Apply to all view files
- [ ] 4.10.6 Test sending wrong HTTP methods returns 405

### 4.11 Phase 4 Testing and Deployment
- [ ] 4.11.1 Performance testing for caching improvements
- [ ] 4.11.2 Visual regression testing for template changes
- [ ] 4.11.3 Create git branch: `git checkout -b fix/phase4-templates`
- [ ] 4.11.4 Commit all Phase 4 changes
- [ ] 4.11.5 Deploy to staging
- [ ] 4.11.6 A/B test performance improvements
- [ ] 4.11.7 Deploy to production
- [ ] 4.11.8 Monitor page load times and cache hit rates

## Final Validation and Documentation

### 5.1 Comprehensive Testing
- [ ] 5.1.1 Run full test suite: `python manage.py test`
- [ ] 5.1.2 Run test coverage: `coverage run --source='.' manage.py test && coverage report`
- [ ] 5.1.3 Manual testing of all major features
- [ ] 5.1.4 Performance testing with 1000+ records
- [ ] 5.1.5 Security testing for XSS, file uploads, rate limiting
- [ ] 5.1.6 Load testing with concurrent users

### 5.2 Documentation Updates
- [ ] 5.2.1 Update CHANGELOG.md with all fixes
- [ ] 5.2.2 Update CLAUDE.md if patterns changed
- [ ] 5.2.3 Document new validation requirements
- [ ] 5.2.4 Document performance improvements achieved
- [ ] 5.2.5 Create migration guide for production deployment

### 5.3 Monitoring Setup
- [ ] 5.3.1 Configure error monitoring (Sentry)
- [ ] 5.3.2 Set up query performance monitoring
- [ ] 5.3.3 Configure rate limit violation logging
- [ ] 5.3.4 Set up alerts for performance regressions

### 5.4 Final Deployment
- [ ] 5.4.1 Merge all phase branches to main
- [ ] 5.4.2 Create production deployment plan
- [ ] 5.4.3 Schedule maintenance window if needed
- [ ] 5.4.4 Deploy to production
- [ ] 5.4.5 Monitor for 48 hours
- [ ] 5.4.6 Mark BUG_FIX_PLAN.md as complete

## Dependencies and Parallelization

**Can be done in parallel within each phase:**
- Phase 1: Tasks 1.1-1.6 can run concurrently
- Phase 2: Tasks 2.1-2.8 independent except 2.3 affects 2.1
- Phase 3: All migrations should be tested sequentially
- Phase 4: All optimizations can run in parallel

**Dependencies:**
- Phase 2 requires Phase 1 completion
- Phase 3 migrations require Phase 1-2 code changes
- Phase 4 requires stable Phase 3 database

**Critical path:**
- Phase 1.1 (save methods) → Phase 1.10 (deployment)
- Phase 2.3 (Patient refactor) → Phase 4.4 (template changes)
- Phase 3.1-3.3 (migrations) → Phase 3.11 (deployment)
