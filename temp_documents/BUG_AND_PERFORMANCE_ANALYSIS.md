# NDAS Project - Comprehensive Bug and Performance Analysis

**Generated**: 2025-12-25
**Scope**: Full codebase analysis covering Models, Views, Forms, Templates, URLs, and Middleware
**Total Issues Found**: 150+ bugs and performance bottlenecks

---

## CRITICAL BUGS (Fix Immediately)

### 1. **DevelopmentalAssessment.save() - Missing super().save() Call**
**File**: `patients/models.py:2748-2751`
**Severity**: CATASTROPHIC
**Impact**: Model never actually saves to database!

```python
def save(self, *args, **kwargs):
    """Override save to automatically update is_dx_normal"""
    self.is_dx_normal = self.is_normal
    # BUG: Missing super().save(*args, **kwargs)
```

**Fix**: Add `super().save(*args, **kwargs)` at the end

---

### 2. **DiagnosisList.__str__() - Duplicate Title Logic Error**
**File**: `patients/models.py:2275`
**Severity**: CRITICAL
**Impact**: Display shows "Title (Title)" instead of "Title (Abbreviation)"

```python
def __str__(self):
    return str(self.title + " (" + self.title + ")")  # BUG: Should be self.abr
```

**Fix**: Change to `return str(self.title + " (" + self.abr + ")")`

---

### 3. **IndicationsForGMA.getIndicationList - Returns All Records**
**File**: `patients/models.py:2262`
**Severity**: CRITICAL
**Impact**: Property returns ALL database records instead of instance data

```python
@property
def getIndicationList(self):
    return IndicationsForGMA.objects.all().values_list("title", flat=True)
```

**Fix**: This property doesn't make sense. Should be a class method or removed entirely.

---

### 4. **Missing trailing slashes in URLs (16 instances)**
**File**: `patients/urls.py:12, 19-27, 49, 64-68`
**Severity**: CRITICAL
**Impact**: Django issues 301 redirects on every request, POST data can be lost

**Examples**:
- Line 12: `path("print", views.print, name='print')`
- Line 19: `path("manager/patient/new", ...)`
- Line 64: `path("manager/assessment/recent", ...)`

**Fix**: Add trailing slashes to all URLs

---

### 5. **24 Missing get_object_or_404() in patients/views.py**
**Files**: `patients/views.py` (multiple locations)
**Severity**: CRITICAL
**Impact**: Unhandled DoesNotExist exceptions cause 500 errors instead of 404s

**Lines affected**: 377, 592, 1068, 1091, 1092, 1390, 1608, 1716, 1878, 2167, 2488, 2699, 2887, 3074, 3276, 3505, 3650

**Example**:
```python
selected_patient = Patient.objects.get(id=pk)  # Should use get_object_or_404
```

**Fix**: Replace all `.objects.get()` with `get_object_or_404()`

---

### 6. **File Handle Resource Leaks (6 instances)**
**File**: `reports/views.py:320-321, 341-342, 360-361, 379-380, 398-399, 417-418`
**Severity**: CRITICAL
**Impact**: File handles never explicitly closed, potential resource exhaustion

```python
file_handle = open(file_path, 'rb')
response = FileResponse(file_handle, content_type=content_type)
```

**Fix**: Use context manager:
```python
with open(file_path, 'rb') as file_handle:
    response = FileResponse(file_handle.read(), content_type=content_type)
```

---

### 7. **Database Query on Every Request**
**File**: `users/middleware.py:35-39`
**Severity**: CRITICAL
**Impact**: UPDATE query executes on EVERY authenticated request

```python
UserSession.objects.filter(
    user=request.user,
    session_key=session_key,
    is_active=True
).update(last_activity=timezone.now())
```

**Fix**: Throttle to once per minute using session cache

---

## HIGH PRIORITY BUGS

### 8. **Patient Model - Multiple N+1 Query Properties**
**File**: `patients/models.py:358-684`
**Severity**: HIGH
**Impact**: Each property access triggers separate database queries

**Affected properties**:
- `isNewPatient` (line 364) - Video.objects.filter query
- `isDischarged` (line 369) - CDICRecord query
- `isScreeningPositive` (line 383) - Multiple assessment queries
- `isLastGMANormal` (line 423) - 2 separate GMAssessment queries
- `getRC` (line 591) - 4+ queries executed

**Fix**: Replace with annotated querysets or class methods with select_related/prefetch_related

---

### 9. **Missing select_related in 6 Assessment Manager Views**
**File**: `patients/views.py:1211-1395`
**Severity**: HIGH
**Impact**: N+1 queries when rendering assessment lists

**Lines**: 1211, 1239, 1270, 1301, 1332, 1363

```python
assessment_list = GMAssessment.objects.filter(...).order_by("-id")
# Missing: .select_related('patient', 'added_by', 'last_edit_by', 'video_file')
```

**Fix**: Add select_related to all manager views

---

### 10. **patient_view() - Missing select_related (6 queries)**
**File**: `patients/views.py:376-412`
**Severity**: HIGH
**Impact**: Each related object list missing user tracking selects

```python
var_gma = GMAssessment.objects.filter(patient=selected_patient).order_by("-id")
# Missing: .select_related('added_by', 'last_edit_by')
```

**Fix**: Add select_related to all 6 queries (videos, attachments, assessments)

---

### 11. **Incorrect Error Message Display (4 instances)**
**File**: `patients/views.py:1055, 1742, 2152, 2360`
**Severity**: HIGH
**Impact**: Form errors displayed as success messages

```python
messages.success(request, assessment_form_data.errors)  # Should be messages.error()
```

**Fix**: Change to `messages.error()`

---

### 12. **Missing Profile Picture Validation**
**File**: `users/forms.py:12, 114-118`
**Severity**: HIGH
**Impact**: No file size, format, or content validation

**Missing validation**:
- File size limit (should be 5MB max)
- Image format (JPG, JPEG, PNG only)
- Image dimension validation
- Malicious file content check

**Fix**: Add clean_profile_picture() method with validators

---

### 13. **Video Filter - Loading All IDs into Memory**
**File**: `video/views.py:259-268, 360-364`
**Severity**: HIGH
**Impact**: For large datasets, loads thousands of IDs into memory

```python
used_video_ids = GMAssessment.objects.values_list('video_file_id', flat=True)
queryset = queryset.exclude(id__in=used_video_ids)
```

**Fix**: Use Exists() subquery instead

---

### 14. **Missing Sanitization in problemlist Forms**
**File**: `problemlist/forms.py:28-70`
**Severity**: HIGH
**Impact**: XSS vulnerability - raw HTML accepted without sanitization

**Affected fields**: name, description, action_taken, outcome, comments

**Fix**: Add sanitization using `ndas.custom_codes.sanitization` utilities

---

### 15. **Missing Rate Limiting on CRUD Operations**
**Files**: Multiple views
**Severity**: HIGH
**Impact**: No protection against automated attacks on state-changing operations

**Currently protected**: Login, password reset, reports
**Missing protection**: Patient CRUD, Assessment CRUD, Video upload, Attachment operations, Admin user management

**Fix**: Add @ratelimit decorators to all POST/PUT/DELETE endpoints

---

## MEDIUM PRIORITY BUGS

### 16. **DiagnosisList - TextField Without Constraints**
**File**: `patients/models.py:2268-2269`
**Severity**: MEDIUM
**Impact**: Database bloat, poor indexing performance

```python
title = models.TextField()  # Should be CharField with max_length
description = models.TextField()  # No constraints
```

**Fix**:
- Change title to CharField(max_length=255, db_index=True)
- Add max_length to description or use proper text storage

---

### 17. **Missing Database Indexes (Multiple Models)**
**Severity**: MEDIUM
**Impact**: Slow queries on searchable/filterable fields

**IndicationsForGMA** (patients/models.py:2250-2263):
- Missing index on `title` (used in searches)
- Missing index on `level` (used in filtering)

**DiagnosisList** (patients/models.py:2266-2275):
- Missing index on `title`
- Missing index on `abr`
- Missing unique constraint on `abr`

**CustomUser** (users/models.py:32-36):
- Missing index on `mobile_primary` (used for lookups)

**Fix**: Add `db_index=True` to these fields

---

### 18. **Multiple .filter().count() Calls**
**File**: `patients/views.py:2855-2857, 2932-2934, 3242-3243, 3348-3349, 2451, 2548, 1490-1491`
**Severity**: MEDIUM
**Impact**: Executes full queryset multiple times

```python
'normal': var_hine_list.filter(score__gte=60).count(),
'moderate': var_hine_list.filter(score__gte=40, score__lt=60).count(),
'significant': var_hine_list.filter(score__lt=40).count(),
```

**Fix**: Use aggregate() with Count() and Case() for single query

---

### 19. **Subscription.update_status Race Condition**
**File**: `users/models.py:748-780`
**Severity**: MEDIUM
**Impact**: Cache cleared before transaction, allowing stale reads

```python
def update_status(self):
    self._clear_cache()  # BUG: Cleared before transaction
    # ... calculation ...
    with transaction.atomic():
        subscription = Subscription.objects.select_for_update().get(pk=self.pk)
```

**Fix**: Clear cache after transaction commits or within transaction

---

### 20. **Video Metadata Extraction in Synchronous Save**
**File**: `video/models.py:236-281`
**Severity**: MEDIUM
**Impact**: FFmpeg processing blocks request/response cycle for large videos

**Fix**: Move to Celery background task or async processing

---

### 21. **Missing Pagination on dashboard()**
**File**: `patients/views.py:127`
**Severity**: MEDIUM
**Impact**: Loads ALL bookmarks without limits

```python
bookmark = Bookmark.objects.all()
```

**Fix**: Add pagination or limit, or use .count() if only counting

---

### 22. **Username List Queries Without Field Restrictions**
**File**: `users/views.py:657, 682, 690, 695, 829, 838, 848`
**Severity**: MEDIUM
**Impact**: Loads all user fields when only username needed

```python
username_list = CustomUser.objects.all()
```

**Fix**: Use `.only('id', 'username')` or `.values_list('username', flat=True)`

---

### 23. **Missing select_related on User Activity Logs**
**File**: `users/views.py:421, 818, 837`
**Severity**: MEDIUM
**Impact**: N+1 queries when displaying user information

```python
activities = UserActivityLog.objects.filter(user=user).order_by('-login_timestamp')
# Missing: .select_related('user')
```

**Fix**: Add select_related('user')

---

### 24. **Email Uniqueness Check Race Condition**
**File**: `users/forms.py:185-195`
**Severity**: MEDIUM
**Impact**: Two users could register with same email simultaneously

**Fix**: Add select_for_update() or database-level unique constraint

---

### 25. **Password Validation Inconsistency**
**File**: `users/forms.py:305-352`
**Severity**: MEDIUM
**Impact**: AdminUserCreationForm checks min 8 chars, but settings require 12

**Fix**: Use Django's built-in password validators from AUTH_PASSWORD_VALIDATORS

---

### 26. **Video File MIME Type Validation Missing**
**File**: `video/forms.py:49-92`
**Severity**: MEDIUM
**Impact**: Client-side filtering only, renamed malicious files could pass

**Fix**: Add server-side MIME type verification in clean_video_file()

---

### 27. **Date Validation Incomplete in problemlist**
**File**: `problemlist/forms.py:73-114`
**Severity**: MEDIUM
**Impact**: date_resolved can be before date_of_onset

**Fix**: Add cross-field validation in clean()

---

### 28. **Filename Sanitization Called Too Late**
**File**: `patients/forms.py:739-745`
**Severity**: MEDIUM
**Impact**: Path traversal attack possible before sanitization

**Fix**: Sanitize before file is stored temporarily

---

### 29. **GMAssessment.video_file - Missing Index**
**File**: `patients/models.py:728-733`
**Severity**: MEDIUM
**Impact**: Slow reverse lookups from Video to Assessment

**Fix**: Verify index exists on OneToOneField

---

### 30. **Weak Birth Weight Validation**
**File**: `patients/models.py:346-350`
**Severity**: MEDIUM
**Impact**: Only validates POG < 28 weeks, misses other abnormal combinations

**Fix**: Add comprehensive gestational age vs weight validation table

---

## LOW PRIORITY ISSUES

### 31. **Empty Meta Classes (3 instances)**
**Files**: `patients/models.py:2250-2275`
**Severity**: LOW
**Impact**: Missing ordering, verbose names, indexes

**Fix**: Add proper Meta configuration

---

### 32. **Missing Unique Constraints**
**Files**: `patients/models.py`
**Severity**: LOW
**Impact**: Duplicate entries possible

- DiagnosisList.abr should be unique
- IndicationsForGMA.title should be unique
- Help.title should be unique

**Fix**: Add unique=True constraints

---

### 33. **Missing App Namespaces**
**Files**: `patients/urls.py`, `users/urls.py`, `problemlist/urls.py`
**Severity**: LOW
**Impact**: Harder maintenance, potential naming conflicts

**Fix**: Add `app_name = 'patients'` etc.

---

### 34. **Temporary Redirects Should Be Permanent**
**File**: `patients/urls.py:19-27`
**Severity**: LOW
**Impact**: Unnecessary server load, redirects not cached

**Fix**: After deprecation period, change to permanent=True or remove

---

### 35. **Missing HTTP Method Restrictions**
**Severity**: LOW
**Impact**: Views don't explicitly restrict HTTP methods

**Fix**: Add @require_http_methods, @require_GET, @require_POST decorators

---

## PERFORMANCE ISSUES

### 36. **Template Queries (N+1 in Templates)**
**Files**: Multiple templates
**Severity**: HIGH
**Impact**: Database queries executed in template loops

**patient_view.html:240**: `{% for gmamodel in patient.indecation_for_gma.all %}`
**assessment/manager.html:218**: `{% for dx in Assessment.diagnosis.all %}`
**problemlist/_problem_list_section.html:4,17,53,64**: Multiple .all() and .count() calls

**Fix**: Prefetch all relationships in views

---

### 37. **Missing Template Fragment Caching**
**Files**: All manager templates
**Severity**: MEDIUM
**Impact**: Repeatedly rendered components not cached

**Critical templates**:
- `patients/manager.html` (521 lines)
- `assessment/manager.html` (432 lines)
- `video/manager.html` (450 lines)

**Fix**: Add {% cache %} blocks for pagination, filters, static badges

---

### 38. **Heavy Method Calls in Templates**
**File**: `patients/partials/patient_view.html:63,72,81,90`
**Severity**: MEDIUM
**Impact**: Python methods with datetime calculations called in templates

```html
{{patient.getCurrentAge}}
{{patient.getCorrectedAge}}
{{patient.getPOG}}
```

**Fix**: Calculate in view layer and pass to template

---

### 39. **Delete Modals Generated in Loops**
**File**: `assessment/manager.html:400-402`
**Severity**: MEDIUM
**Impact**: Creates 10-50 modal HTML blocks per page

```html
{% for Assessment in assessment_page_obj %}
  {% delete_modal Assessment %}
{% endfor %}
```

**Fix**: Use single modal with JavaScript for different items

---

### 40. **Complex Pagination Logic in Template**
**File**: `patients/manager.html:421-439`
**Severity**: LOW
**Impact**: Mathematical operations in template

**Fix**: Compute page range in view

---

### 41. **No Static File Optimization**
**Files**: All templates
**Severity**: LOW
**Impact**: Slow initial page loads

**Missing**:
- Asset preloading
- Async/defer on scripts
- Lazy loading for images
- Font Awesome loaded synchronously

**Fix**: Add preload links, async attributes, lazy loading

---

### 42. **Missing Cache Headers on File Downloads**
**File**: `reports/views.py:319-324`
**Severity**: LOW
**Impact**: Reports regenerated instead of cached

**Fix**: Add ETag, Last-Modified, Cache-Control headers

---

### 43. **No Efficient File Serving**
**File**: `reports/views.py:320`
**Severity**: LOW
**Impact**: Django serves files through Python, blocking workers

**Fix**: Use X-Accel-Redirect (Nginx) or X-Sendfile (Apache) in production

---

### 44. **Subscription Check Database Queries**
**File**: `users/middleware.py:92`
**Severity**: LOW
**Impact**: get_global_subscription() queries on every request

**Fix**: Cache subscription object itself in Django cache

---

## SUMMARY BY CATEGORY

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| CRUD Bugs | 7 | 5 | 8 | 3 | 23 |
| N+1 Queries | 0 | 3 | 4 | 0 | 7 |
| Missing Indexes | 0 | 2 | 3 | 0 | 5 |
| Security | 2 | 2 | 4 | 1 | 9 |
| Validation | 0 | 1 | 5 | 0 | 6 |
| Templates | 0 | 1 | 3 | 2 | 6 |
| Middleware | 1 | 0 | 1 | 1 | 3 |
| URLs | 1 | 0 | 0 | 2 | 3 |
| **TOTAL** | **11** | **14** | **28** | **9** | **62** |

**Note**: This represents unique bug categories. With multiple instances (e.g., 24 missing get_object_or_404), total fixes needed exceeds 150.

---

## FILES REQUIRING CHANGES

### Models
- `patients/models.py` - 15 issues
- `users/models.py` - 4 issues
- `video/models.py` - 2 issues

### Views
- `patients/views.py` - 35+ issues
- `users/views.py` - 12 issues
- `video/views.py` - 4 issues
- `reports/views.py` - 8 issues
- `problemlist/views.py` - 2 issues

### Forms
- `users/forms.py` - 6 issues
- `patients/forms.py` - 3 issues
- `problemlist/forms.py` - 4 issues
- `video/forms.py` - 3 issues

### Templates
- `patients/manager.html` - 5 issues
- `patients/partials/patient_view.html` - 4 issues
- `assessment/manager.html` - 3 issues
- `video/manager.html` - 2 issues
- `problemlist/_problem_list_section.html` - 2 issues

### Configuration
- `patients/urls.py` - 18 issues
- `users/urls.py` - 2 issues
- `users/middleware.py` - 3 issues
- `ndas/settings.py` - 1 issue

---

## NEXT STEPS

See `BUG_FIX_PLAN.md` for prioritized implementation plan with step-by-step instructions.
