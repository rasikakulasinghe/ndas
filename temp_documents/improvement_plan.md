# NDAS System Improvement Plan

**Project:** Neurodevelopmental Assessment System (NDAS)
**Audit Date:** December 21, 2025
**Django Version:** 4.1.6
**Document Version:** 1.0

---

## Executive Summary

This document outlines a comprehensive improvement plan for the NDAS Django application based on a thorough code audit. The codebase demonstrates solid architectural foundations but requires critical security fixes, performance optimizations, and code quality improvements before production deployment.

**Overall Health:** MODERATE ⚠️
**Total Estimated Effort:** 73 hours (6 weeks)
**Minimum Viable Production:** 19 hours (Phase 1 + Phase 2.1 + Phase 4.1)

---

## Critical Findings Overview

### Security Issues (23 total)
- **3 Critical** - CSRF exemption, CSP misconfiguration, email backend
- **2 High** - Missing rate limiting, timing attacks
- **3 Medium** - Session security, error handling

### Performance Issues (5 total)
- **2 High** - N+1 queries in dashboard and manager views
- **3 Medium** - Inefficient counting, missing pagination

### Code Quality Issues (12 total)
- **1 Critical** - ~2000 lines of duplicated code
- **5 Medium** - Dead code, missing docstrings, magic strings

---

## Phase 1: Critical Security Fixes (Week 1)

**Priority:** IMMEDIATE - Cannot deploy to production without these fixes
**Total Time:** 10 hours

### Issue 1.1: CSRF Exemption on API Endpoint ⚠️ CRITICAL

**File:** `users/views.py:471`

**Current Code:**
```python
@csrf_exempt  # ❌ CRITICAL VULNERABILITY
def get_user_activity_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
```

**Problem:** Vulnerable to Cross-Site Request Forgery attacks even with authentication check.

**Solution:**
```python
# Option 1: Remove CSRF exemption, require POST with token
from django.views.decorators.http import require_http_methods

@require_http_methods(["POST"])
def get_user_activity_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    user = request.user
    days = int(request.POST.get('days', 30))
    activity_summary = get_user_activity_summary(user, days)
    # ... rest of code

# Option 2: Use Django REST Framework with token authentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_activity_api(request):
    # Token-based auth doesn't need CSRF protection
    user = request.user
    days = int(request.GET.get('days', 30))
    # ... rest of code
```

**Estimated Time:** 2 hours
**Testing:** Verify CSRF token validation works, no authentication bypass possible

---

### Issue 1.2: Production CSP Allows Unsafe Inline/Eval ⚠️ CRITICAL

**File:** `settings.py:272-283`

**Current Code:**
```python
# Production CSP - Still allows unsafe inline!
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdn.jsdelivr.net", ...)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", ...)
```

**Problem:** `'unsafe-inline'` and `'unsafe-eval'` completely undermine XSS protection.

**Solution:**
```python
# Production CSP - SECURE VERSION
if not DEBUG:
    CSP_DEFAULT_SRC = ("'self'",)

    # Remove 'unsafe-inline' and 'unsafe-eval' from production
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

    # Use nonces for inline scripts (already configured)
    CSP_INCLUDE_NONCE_IN = ['script-src', 'style-src']
```

**Template Updates Required:**
```django
{# Update all inline scripts to use CSP nonce #}
<script nonce="{{ request.csp_nonce }}">
    // Your inline JavaScript here
    console.log('Using CSP nonce for security');
</script>

{# Update inline styles #}
<style nonce="{{ request.csp_nonce }}">
    .custom-class {
        color: red;
    }
</style>
```

**Files to Update:**
- `templates/src/base.html`
- `templates/patients/index.html`
- `templates/users/login.html`
- Any template with inline `<script>` or `<style>` tags

**Estimated Time:** 4 hours
**Testing:** Use browser DevTools to check CSP violations, validate no functionality breaks

---

### Issue 1.3: File-Based Email Backend ⚠️ HIGH

**File:** `settings.py:158-168`

**Current Code:**
```python
EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = BASE_DIR / 'sent_emails'
```

**Problem:** Emails saved to files instead of being sent. Password resets won't work in production.

**Solution:**
```python
# Environment-based email configuration
if DEBUG:
    # Console backend for development (prints to terminal)
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    # SMTP backend for production
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@ndas-system.com')
    EMAIL_TIMEOUT = 30  # 30 second timeout for email operations

# Common settings
EMAIL_VERIFICATION_REQUIRED = True
EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS = 24
```

**Environment Variables to Add (.env.production):**
```bash
# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@ndas-system.com
```

**Estimated Time:** 1 hour
**Testing:** Test password reset and email verification flows in staging

---

### Issue 1.4: Missing Rate Limiting on Authentication ⚠️ HIGH

**File:** `users/views.py:28` (loginPage function)

**Current Code:**
```python
def loginPage(request):
    # No rate limiting - vulnerable to brute force
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        # ... authentication logic
```

**Problem:** Unlimited login attempts allow brute force attacks.

**Solution:**
```python
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited

@ratelimit(key='ip', rate='5/m', method='POST', block=True)
@ratelimit(key='post:username', rate='3/m', method='POST', block=True)
def loginPage(request):
    """
    Login page with rate limiting:
    - 5 attempts per minute per IP address
    - 3 attempts per minute per username
    """
    logged_user = request.user

    # Check if rate limited
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        messages.error(
            request,
            'Too many login attempts. Please wait a few minutes and try again.'
        )
        # Log the rate limit event
        logger.warning(
            f"Rate limit triggered for IP {request.META.get('REMOTE_ADDR')} "
            f"attempting username: {request.POST.get('username', 'N/A')}"
        )
        return render(request, 'users/login.html', {
            'logged_user': logged_user,
            'developer': developer,
            'rate_limited': True
        })

    # ... rest of existing login code
```

**Also Apply Rate Limiting To:**

1. **Password Reset Request** (`users/views.py` - password reset view):
```python
@ratelimit(key='ip', rate='3/h', method='POST', block=True)
def password_reset_request(request):
    # ...
```

2. **User Registration** (if public registration enabled):
```python
@ratelimit(key='ip', rate='3/h', method='POST', block=True)
def register(request):
    # ...
```

3. **Email Verification Resend**:
```python
@ratelimit(key='post:email', rate='3/h', method='POST', block=True)
def resend_verification_email(request):
    # ...
```

**Settings Update:**
```python
# settings.py
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_ENABLE = config('RATELIMIT_ENABLE', default=True, cast=bool)
RATELIMIT_VIEW = 'ndas.views.rate_limited_error'  # Custom error page
```

**Custom Rate Limit Error Handler:**
```python
# ndas/views.py
def rate_limited_error(request, exception):
    """Custom view for rate limit errors."""
    return render(request, 'errors/rate_limited.html', status=429)
```

**Estimated Time:** 3 hours
**Testing:** Attempt multiple failed logins, verify blocking after threshold

---

## Phase 2: Performance Optimization (Week 2)

**Priority:** HIGH - Prevents scalability issues
**Total Time:** 7 hours

### Issue 2.1: N+1 Queries in Dashboard ⚠️ HIGH

**File:** `patients/views.py:80-150`

**Current Code:**
```python
@login_required(login_url="user-login")
def dashboard(request):
    var_patients = getPatientList(PtStatus.ALL)  # Loads all patients
    var_videos = Video.objects.all()              # Loads all videos
    var_gm_assessments = GMAssessment.objects.all()  # Loads all assessments
    # ... more queries

    var_new_Patients = var_patients.filter(videos__isnull=True).distinct()
    Patients_new_list_10 = var_new_Patients[:5]  # Slices in Python, not SQL
```

**Problem:** Loads all records, creates N+1 queries when templates access relationships.

**Solution:**
```python
from django.db.models import Count, Q, Prefetch, Exists, OuterRef

@login_required(login_url="user-login")
def dashboard(request):
    # Efficient count queries without loading data
    patients_total_count = Patient.objects.count()
    patients_discharged_count = Patient.objects.filter(
        do_discharge__isnull=False
    ).count()

    # Get new patients efficiently with annotation
    patients_new_query = Patient.objects.annotate(
        video_count=Count('videos')
    ).filter(video_count=0)

    # Only load 5 records with related user data
    Patients_new_list_10 = patients_new_query.select_related(
        'added_by', 'last_edit_by'
    )[:5]

    patients_new_count = patients_new_query.count()

    # Efficient video queries with optimization
    videos_total_count = Video.objects.count()

    # New videos (not assessed) - optimized query
    new_videos_subquery = GMAssessment.objects.filter(
        video_file_id=OuterRef('pk')
    )

    new_videos = Video.objects.annotate(
        has_assessment=Exists(new_videos_subquery)
    ).filter(
        has_assessment=False
    ).select_related(
        'patient', 'added_by'
    ).only(
        'id', 'title', 'recorded_on', 'duration_seconds',
        'patient__baby_name', 'patient__bht',
        'added_by__username'
    )[:5]

    new_videos_count = Video.objects.filter(
        gmassessment__isnull=True
    ).count()

    # Assessment counts - direct count without loading
    all_gm_assessments_count = GMAssessment.objects.count()
    all_hine_assessments_count = HINEAssessment.objects.count()
    all_da_assessments_count = DevelopmentalAssessment.objects.count()
    all_cdic_records_count = CDICRecord.objects.count()

    # Diagnosis counts with efficient filtering
    dx_gm_assessments_count = GMAssessment.objects.exclude(
        diagnosis_conclusion="NORMAL"
    ).count()

    dx_hine_assessments_count = HINEAssessment.objects.filter(
        score__lt=73
    ).count()

    dx_da_assessments_count = DevelopmentalAssessment.objects.filter(
        is_dx_normal=False
    ).count()

    # Bookmarks - only load needed fields
    bookmark = Bookmark.objects.select_related(
        'added_by'
    ).only(
        'id', 'bookmark_type', 'object_id', 'title',
        'added_by__username'
    )

    attachments_count = Attachment.objects.count()
    users_total_count = CustomUser.objects.count()

    # Chart data methods (keep as is - these are aggregations)
    bar_chart_monthly_admissions = get_admissions_data_barchart()
    diagnosis_data_gma = get_gma_diagnosis_data()
    diagnosis_data_all = get_all_diagnosis_data()
    user_stat = get_userStats()

    context = {
        "videos_total_count": videos_total_count,
        "dx_gm_assessments_count": dx_gm_assessments_count,
        "dx_hine_assessments_count": dx_hine_assessments_count,
        "dx_da_assessments_count": dx_da_assessments_count,
        "all_gm_assessments_count": all_gm_assessments_count,
        "all_hine_assessments_count": all_hine_assessments_count,
        "all_da_assessments_count": all_da_assessments_count,
        "all_cdic_records_count": all_cdic_records_count,
        "new_videos": new_videos,
        "new_videos_count": new_videos_count,
        "videos_total_count": videos_total_count,
        "patients_total_count": patients_total_count,
        "Patients_new_list_10": Patients_new_list_10,
        "patients_new_count": patients_new_count,
        "patients_discharged_count": patients_discharged_count,
        "bookmark": bookmark,
        "bar_chart_monthly_admissions": bar_chart_monthly_admissions,
        "diagnosis_data_gma": diagnosis_data_gma,
        "diagnosis_data_all": diagnosis_data_all,
        "users_total_count": users_total_count,
        "attachments_count": attachments_count,
        "user_stat": user_stat,
    }

    return render(request, "patients/index.html", context)
```

**Estimated Time:** 4 hours
**Expected Improvement:** 60-80% query reduction (from ~50 queries to ~15 queries)
**Testing:** Use django-debug-toolbar to verify query count before/after

---

### Issue 2.2: Missing select_related in Patient Manager ⚠️ HIGH

**File:** `patients/views.py:154-410` (All patient_manager_* views)

**Current Code:**
```python
def patient_manager(request):
    patients_list = Patient.objects.all().order_by("-id")
    # Template accessing patient.added_by.username creates N+1 queries
```

**Problem:** Each patient's user relationships trigger separate queries in templates.

**Solution:**
```python
from django.db.models import Prefetch

def patient_manager(request):
    search_query = request.GET.get('search', '').strip()

    # Optimize with select_related for ForeignKey lookups
    patients_list = Patient.objects.select_related(
        'added_by',          # User who created the patient
        'last_edit_by'       # User who last edited
    ).prefetch_related(
        'indecation_for_gma',  # ManyToMany field
        Prefetch(
            'videos',
            queryset=Video.objects.only('id', 'patient_id', 'title', 'recorded_on')
        ),
        Prefetch(
            'assessments',
            queryset=GMAssessment.objects.only('id', 'patient_id', 'diagnosis_conclusion')
        )
    )

    if search_query:
        patients_list = patients_list.filter(
            Q(baby_name__icontains=search_query) |
            Q(mother_name__icontains=search_query) |
            Q(bht__icontains=search_query) |
            Q(nnc_no__icontains=search_query)
        )

    patients_list = patients_list.order_by("-id")

    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get("page")
    paginated_pt_list = paginator.get_page(page_number)

    context = {
        "patients_page_obj": paginated_pt_list,
        "search_query": search_query,
    }

    return render(request, "patients/manager.html", context)
```

**Apply to All Manager Views:**
- `patient_manager_diagnosed_any()`
- `patient_manager_diagnosis_normal()`
- `patient_manager_diagnosed_gma_normal()`
- `patient_manager_diagnosed_gma_abnormal()`
- `patient_manager_diagnosed_hine()`
- `patient_manager_da_normal()`
- `patient_manager_da_abnormal()`
- `patient_manager_discharged_only()`

**Estimated Time:** 2 hours
**Expected Improvement:** Eliminates N+1 queries on user references
**Testing:** Check query count in manager views with django-debug-toolbar

---

### Issue 2.3: Add Database Query Monitoring

**File:** Create new development tools configuration

**Action:** Add django-debug-toolbar for development query analysis.

**Installation:**
```bash
pip install django-debug-toolbar
```

**Configuration:**
```python
# settings.py
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']

    INTERNAL_IPS = [
        '127.0.0.1',
        'localhost',
    ]

    DEBUG_TOOLBAR_CONFIG = {
        'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG,
        'SHOW_COLLAPSED': True,
    }
```

**URL Configuration:**
```python
# ndas/urls.py
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
```

**Estimated Time:** 1 hour
**Benefit:** Real-time query monitoring during development

---

## Phase 3: Code Quality Refactoring (Weeks 3-4)

**Priority:** MEDIUM - Improves maintainability
**Total Time:** 19 hours

### Issue 3.1: Eliminate Patient Manager Duplication ⚠️ CRITICAL

**Files:** `patients/views.py:154-410` (8 duplicate functions)

**Current Situation:**
- 8 nearly identical functions (~250 lines each)
- ~2000 lines of duplicated code
- Any bug fix requires updating 8+ places

**Solution: Create Unified Patient Manager**

```python
@login_required(login_url="user-login")
def patient_manager(request, filter_type='all'):
    """
    Unified patient manager with filtering and search.

    Args:
        request: HTTP request object
        filter_type: Filter to apply - 'all', 'diagnosed', 'dx_normal',
                     'dx_gma_normal', 'dx_gma_abnormal', 'dx_hine',
                     'dx_da_normal', 'dx_da_abnormal', 'discharged'

    Returns:
        Rendered patient manager page with paginated results
    """
    # Get search parameter
    search_query = request.GET.get('search', '').strip()

    # Apply filter based on type
    FILTER_MAP = {
        'all': Patient.objects.all(),
        'diagnosed': getPatientList(PtStatus.DIAGNOSED),
        'dx_normal': getPatientList(PtStatus.DX_NORMAL),
        'dx_gma_normal': getPatientList(PtStatus.DX_GMA_NORMAL),
        'dx_gma_abnormal': getPatientList(PtStatus.DX_GMA_ABNORMAL),
        'dx_hine': getPatientList(PtStatus.DX_HINE),
        'dx_da_normal': getPatientList(PtStatus.DX_DA_NORMAL),
        'dx_da_abnormal': getPatientList(PtStatus.DX_DA_ABNORMAL),
        'discharged': getPatientList(PtStatus.DISCHARGED),
    }

    patients_list = FILTER_MAP.get(filter_type, Patient.objects.all())

    # Apply search filter if provided
    if search_query:
        patients_list = patients_list.filter(
            Q(baby_name__icontains=search_query) |
            Q(mother_name__icontains=search_query) |
            Q(bht__icontains=search_query) |
            Q(nnc_no__icontains=search_query)
        )

    # Optimize query with select_related
    patients_list = patients_list.select_related(
        'added_by', 'last_edit_by'
    ).order_by("-id")

    # Paginate results
    paginator = Paginator(patients_list, 10)
    page_number = request.GET.get("page")
    paginated_pt_list = paginator.get_page(page_number)

    # Build context with filter information
    FILTER_LABELS = {
        'all': 'All Patients',
        'diagnosed': 'Diagnosed Patients',
        'dx_normal': 'Normal Diagnosis',
        'dx_gma_normal': 'GMA Normal',
        'dx_gma_abnormal': 'GMA Abnormal',
        'dx_hine': 'HINE Diagnosed',
        'dx_da_normal': 'DA Normal',
        'dx_da_abnormal': 'DA Abnormal',
        'discharged': 'Discharged Patients',
    }

    context = {
        "patients_page_obj": paginated_pt_list,
        "filter_type": filter_type,
        "filter_label": FILTER_LABELS.get(filter_type, 'All Patients'),
        "search_query": search_query,
    }

    return render(request, "patients/manager.html", context)
```

**URL Configuration Update:**
```python
# patients/urls.py
from django.urls import path
from . import views

app_name = 'patients'

urlpatterns = [
    # Unified patient manager
    path('manager/patient/', views.patient_manager, name='manager'),
    path('manager/patient/<str:filter_type>/', views.patient_manager, name='manager-filtered'),

    # Remove these old URLs:
    # path('manager/patient/diagnosed/', views.patient_manager_diagnosed_any, name='manager-diagnosed'),
    # path('manager/patient/normal/', views.patient_manager_diagnosis_normal, name='manager-normal'),
    # ... etc (remove all 8 separate manager URLs)
]
```

**Template Update:**
```django
{# templates/patients/manager.html #}
{# Update page title to use filter_label #}
<h1>{{ filter_label }}</h1>

{# Update navigation links #}
<a href="{% url 'patients:manager' %}">All Patients</a>
<a href="{% url 'patients:manager-filtered' 'diagnosed' %}">Diagnosed</a>
<a href="{% url 'patients:manager-filtered' 'dx_normal' %}">Normal</a>
{# ... etc #}
```

**Migration Steps:**
1. Create new unified `patient_manager()` function
2. Update URL patterns to use new function
3. Test all filter types work correctly
4. Update navigation links in templates
5. Remove old duplicate functions
6. Remove old URL patterns

**Estimated Time:** 6 hours (includes testing)
**Impact:** Reduces codebase by ~1950 lines (97.5% reduction)
**Benefit:** Single point of maintenance, consistent behavior across all filters

---

### Issue 3.2: Remove Dead Code

**Files to Clean:**

1. **users/middleware.py:179-196** - Commented signal handler
```python
# DELETE LINES 179-196:
# @receiver(user_logged_in)
# def log_user_login(sender, request, user, **kwargs):
#     """
#     Signal handler for successful user login.
#     """
#     ...
```

2. **patients/views.py:69** - Commented import
```python
# DELETE LINE 69:
# from moviepy.editor import VideoFileClip  # Temporarily commented out
```

3. **patients/views.py:58** - Duplicate import
```python
# DELETE LINE 58 (keep line 57):
from patients.timeline_utils import get_patient_timeline_events  # Line 57 - KEEP
from patients.timeline_utils import get_patient_timeline_events  # Line 58 - DELETE
```

**Estimated Time:** 1 hour
**Impact:** Cleaner, more maintainable codebase

---

### Issue 3.3: Add Comprehensive Docstrings

**Standard:** Use Google-style docstrings

**Template:**
```python
def function_name(arg1, arg2, kwarg1=None):
    """
    Brief one-line description.

    Longer description explaining what the function does, any important
    business logic, and key behaviors.

    Args:
        arg1 (Type): Description of arg1
        arg2 (Type): Description of arg2
        kwarg1 (Type, optional): Description. Defaults to None.

    Returns:
        Type: Description of return value

    Raises:
        ExceptionType: When this exception is raised

    Example:
        >>> result = function_name('value1', 'value2')
        >>> print(result)
        'expected output'
    """
    # Implementation
```

**Priority Files to Document:**
1. All view functions in `patients/views.py`
2. All view functions in `users/views.py`
3. Custom methods in `ndas/custom_codes/custom_methods.py`
4. Model methods in all `models.py` files

**Example Application:**
```python
@login_required(login_url="user-login")
def patient_view(request, pk):
    """
    Display detailed view of a single patient record.

    Shows comprehensive patient information including demographics, birth details,
    medical history, and related records (videos, assessments, attachments).
    Includes timeline of all patient-related events.

    Args:
        request (HttpRequest): The HTTP request object
        pk (int): Primary key of the patient record to display

    Returns:
        HttpResponse: Rendered patient detail page

    Raises:
        Http404: If patient with given pk does not exist

    Permissions:
        - User must be authenticated
        - No additional permission checks (all authenticated users can view)

    Template:
        patients/view.html
    """
    patient = get_object_or_404(Patient, pk=pk)
    # ... rest of implementation
```

**Estimated Time:** 8 hours
**Benefit:** Easier onboarding, better IDE support, clearer intent

---

### Issue 3.4: Standardize Error Handling

**Create Error Handling Utilities:**

```python
# ndas/custom_codes/error_handlers.py
"""
Centralized error handling utilities for NDAS views.
"""
import logging
from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError

logger = logging.getLogger(__name__)


def handle_view_errors(redirect_url='home', error_message="An error occurred"):
    """
    Decorator to standardize error handling in views.

    Args:
        redirect_url (str): URL name to redirect to on error
        error_message (str): Default error message to show user

    Returns:
        Decorated view function with error handling

    Example:
        @login_required(login_url="user-login")
        @handle_view_errors(redirect_url='patient-manager',
                           error_message="Error processing patient")
        def patient_edit(request, pk):
            # View code that may raise exceptions
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                return view_func(request, *args, **kwargs)

            except ObjectDoesNotExist as e:
                logger.error(
                    f"Object not found in {view_func.__name__}: {e}",
                    extra={'user': request.user.username, 'path': request.path}
                )
                messages.error(request, "The requested item was not found.")
                return redirect(redirect_url)

            except ValidationError as e:
                logger.warning(
                    f"Validation error in {view_func.__name__}: {e}",
                    extra={'user': request.user.username, 'path': request.path}
                )
                # Extract meaningful validation messages
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            messages.error(request, f"{field}: {error}")
                else:
                    messages.error(request, f"Validation error: {e}")
                return redirect(request.path)

            except IntegrityError as e:
                logger.error(
                    f"Database integrity error in {view_func.__name__}: {e}",
                    extra={'user': request.user.username, 'path': request.path},
                    exc_info=True
                )
                messages.error(
                    request,
                    "A database error occurred. This may be due to duplicate data or constraint violations."
                )
                return redirect(redirect_url)

            except PermissionError as e:
                logger.warning(
                    f"Permission denied in {view_func.__name__}: {e}",
                    extra={'user': request.user.username, 'path': request.path}
                )
                messages.error(request, "You do not have permission to perform this action.")
                return redirect('home')

            except Exception as e:
                # Catch-all for unexpected errors
                logger.exception(
                    f"Unexpected error in {view_func.__name__}: {e}",
                    extra={'user': request.user.username, 'path': request.path}
                )
                messages.error(request, error_message)
                return redirect(redirect_url)

        return wrapper
    return decorator


def log_and_suppress(default_return=None):
    """
    Decorator to log exceptions and return default value instead of raising.
    Use for non-critical operations where failures should not break the flow.

    Args:
        default_return: Value to return if exception occurs

    Example:
        @log_and_suppress(default_return=[])
        def get_optional_data():
            # Code that may fail but isn't critical
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error in {func.__name__} (suppressed): {e}",
                    exc_info=True
                )
                return default_return
        return wrapper
    return decorator
```

**Usage in Views:**
```python
from ndas.custom_codes.error_handlers import handle_view_errors

@login_required(login_url="user-login")
@handle_view_errors(redirect_url='patient-manager',
                   error_message="Error updating patient")
def patient_edit(request, pk):
    """Edit patient record with standardized error handling."""
    patient = get_object_or_404(Patient, pk=pk)

    if request.method == 'POST':
        form = PatientForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()  # Validation errors handled by decorator
            messages.success(request, 'Patient updated successfully!')
            return redirect('patient-view', pk=patient.pk)
    else:
        form = PatientForm(instance=patient)

    return render(request, 'patients/edit.html', {'form': form})
```

**Estimated Time:** 4 hours
**Benefit:** Consistent error handling, better logging, improved user experience

---

## Phase 4: Additional Security Hardening (Week 5)

**Priority:** MEDIUM-HIGH - Defense in depth
**Total Time:** 15 hours

### Issue 4.1: Fix Timing Attack Vulnerability ⚠️ MEDIUM

**File:** `users/views.py:39-198`

**Current Code:**
```python
if CustomUser.objects.filter(username=username).exists():  # ❌ Reveals username exists
    user = authenticate(request, username=username, password=password)
    if user is not None:
        # login success
    else:
        messages.error(request, 'Wrong password. ...')  # ❌ Different message
else:
    messages.error(request, 'Wrong username. ...')  # ❌ Different message
```

**Problem:** Different error messages allow username enumeration through timing attacks.

**Solution:**
```python
def loginPage(request):
    logged_user = request.user

    # Fetch developer contact
    try:
        developer = DeveloperContacts.objects.get(id=1)
    except DeveloperContacts.DoesNotExist:
        developer = DeveloperContacts.objects.first() or DeveloperContacts.objects.create()

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember')

        # Basic validation
        if not username or not password:
            messages.error(request, 'Username and password are required.')
            return render(request, 'users/login.html', {
                'logged_user': logged_user,
                'developer': developer
            })

        # SECURITY FIX: Always call authenticate, never check username existence first
        # This prevents timing attacks and username enumeration
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Check email verification
            if check_email_verification_required(user):
                messages.warning(request, 'Please verify your email address before logging in.')
                return render(request, 'users/login.html', {
                    'logged_user': logged_user,
                    'developer': developer,
                    'show_resend_verification': True,
                    'unverified_user_email': user.email
                })

            # Check subscription status (existing code)
            if not user.is_superuser:
                try:
                    subscription = Subscription.get_global_subscription()
                    subscription.update_status()

                    if subscription.is_expired:
                        messages.error(
                            request,
                            f'The system subscription expired. Please contact support.'
                        )
                        log_user_activity(
                            request, None, UserActivityLog.LOGIN_FAILED,
                            attempted_username=username,
                            failed_reason="Subscription expired"
                        )
                        return render(request, 'users/login.html', {
                            'logged_user': logged_user,
                            'developer': developer
                        })

                    if subscription.is_grace_period:
                        days_until_lockout = (subscription.grace_period_end_date - date.today()).days
                        messages.warning(
                            request,
                            f'URGENT: Subscription expired. {days_until_lockout} days until lockout.'
                        )

                except Exception as e:
                    logger.error(f"Subscription check failed: {e}")
                    messages.error(request, 'Unable to verify subscription. Please contact support.')
                    return render(request, 'users/login.html', {
                        'logged_user': logged_user,
                        'developer': developer
                    })

            # Successful login
            login(request, user)

            # Handle remember me
            if remember_me:
                request.session.set_expiry(30 * 24 * 60 * 60)
            else:
                request.session.set_expiry(0)

            if not request.session.session_key:
                request.session.save()

            # Update device info
            try:
                device_details = getFullDeviceDetails(request)
                user.last_login_device = device_details
                user.save(update_fields=["last_login_device"])
            except Exception as e:
                logger.error(f"Error updating last_login_device: {e}")

            # Log activity
            try:
                log_user_activity(request, user, UserActivityLog.LOGIN_SUCCESS)
                create_or_update_user_session(request, user)
            except Exception as e:
                logger.error(f"Error logging user activity: {e}")

            messages.success(request, 'You have successfully logged in!')
            return redirect('home')

        else:
            # SECURITY FIX: Generic error message - same for invalid username OR password
            # This prevents attackers from determining if username exists
            log_user_activity(
                request, None, UserActivityLog.LOGIN_FAILED,
                attempted_username=username,
                failed_reason="Invalid credentials"
            )
            messages.error(request, 'Invalid username or password. Please try again.')
            return render(request, 'users/login.html', {
                'logged_user': logged_user,
                'developer': developer
            })

    else:
        if request.user.is_authenticated:
            return redirect('home')
        return render(request, 'users/login.html', {
            'logged_user': logged_user,
            'developer': developer
        })
```

**Key Changes:**
1. Remove `CustomUser.objects.filter(username=username).exists()` check
2. Always call `authenticate()` first
3. Use generic error message "Invalid username or password" for all auth failures
4. Log failed attempts with generic reason "Invalid credentials"

**Estimated Time:** 2 hours
**Testing:** Verify error messages are identical for invalid username and invalid password

---

### Issue 4.2: Add Security Headers Middleware

**Create:** `ndas/custom_codes/security_middleware.py`

```python
"""
Security headers validation middleware for production.
"""
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersValidationMiddleware:
    """
    Validate that critical security headers are present in production.
    This middleware acts as a safety check to ensure security configurations
    are working correctly.
    """

    REQUIRED_HEADERS = [
        'X-Content-Type-Options',
        'X-Frame-Options',
        'Content-Security-Policy',
    ]

    REQUIRED_HEADERS_HTTPS = [
        'Strict-Transport-Security',  # Only required when HTTPS is enabled
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        self.validation_enabled = not settings.DEBUG

    def __call__(self, request):
        response = self.get_response(request)

        # Only validate in production
        if self.validation_enabled:
            self._validate_security_headers(request, response)

        return response

    def _validate_security_headers(self, request, response):
        """Validate that security headers are present."""
        missing_headers = []

        # Check required headers
        for header in self.REQUIRED_HEADERS:
            if header not in response:
                missing_headers.append(header)

        # Check HTTPS-specific headers if SSL is enabled
        if settings.SECURE_SSL_REDIRECT:
            for header in self.REQUIRED_HEADERS_HTTPS:
                if header not in response:
                    missing_headers.append(header)

        # Log missing headers (critical security issue)
        if missing_headers:
            logger.critical(
                f"SECURITY WARNING: Missing security headers on {request.path}: "
                f"{', '.join(missing_headers)}",
                extra={
                    'missing_headers': missing_headers,
                    'path': request.path,
                    'user': request.user.username if request.user.is_authenticated else 'anonymous'
                }
            )


class AdditionalSecurityHeadersMiddleware:
    """
    Add additional security headers not covered by Django's SecurityMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Add Referrer-Policy if not already set
        if 'Referrer-Policy' not in response:
            response['Referrer-Policy'] = settings.SECURE_REFERRER_POLICY

        # Add Cross-Origin-Opener-Policy
        if 'Cross-Origin-Opener-Policy' not in response:
            response['Cross-Origin-Opener-Policy'] = settings.SECURE_CROSS_ORIGIN_OPENER_POLICY

        # Add X-Permitted-Cross-Domain-Policies
        if 'X-Permitted-Cross-Domain-Policies' not in response:
            response['X-Permitted-Cross-Domain-Policies'] = 'none'

        return response
```

**Configuration:**
```python
# settings.py
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'csp.middleware.CSPMiddleware',
    'ndas.custom_codes.security_middleware.AdditionalSecurityHeadersMiddleware',  # ADD THIS
    'django.contrib.sessions.middleware.SessionMiddleware',
    # ... rest of middleware
]

# Add at the end of middleware (after all response processing)
if not DEBUG:
    MIDDLEWARE.append('ndas.custom_codes.security_middleware.SecurityHeadersValidationMiddleware')
```

**Estimated Time:** 3 hours
**Benefit:** Early detection of security misconfigurations

---

### Issue 4.3: Add Input Sanitization Layer

**Install Bleach:**
```bash
pip install bleach
```

**Create Sanitization Utilities:**

```python
# ndas/custom_codes/sanitization.py
"""
Input sanitization utilities for NDAS.
"""
import bleach
from django.utils.html import escape


# Allowed HTML tags for rich text fields
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'a', 'blockquote', 'code', 'pre',
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title'],
}

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


def sanitize_html(html_content, allowed_tags=None, allowed_attrs=None):
    """
    Sanitize HTML content to prevent XSS attacks.

    Args:
        html_content (str): Raw HTML content to sanitize
        allowed_tags (list, optional): Custom list of allowed tags
        allowed_attrs (dict, optional): Custom dict of allowed attributes

    Returns:
        str: Sanitized HTML safe for rendering

    Example:
        >>> dirty_html = '<script>alert("XSS")</script><p>Safe content</p>'
        >>> clean_html = sanitize_html(dirty_html)
        >>> print(clean_html)
        '<p>Safe content</p>'
    """
    if not html_content:
        return ''

    tags = allowed_tags or ALLOWED_TAGS
    attrs = allowed_attrs or ALLOWED_ATTRIBUTES

    return bleach.clean(
        html_content,
        tags=tags,
        attributes=attrs,
        protocols=ALLOWED_PROTOCOLS,
        strip=True
    )


def sanitize_plain_text(text):
    """
    Sanitize plain text by escaping HTML entities.
    Use for fields that should not contain any HTML.

    Args:
        text (str): Text to sanitize

    Returns:
        str: Escaped text safe for rendering
    """
    if not text:
        return ''

    return escape(text)


def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal attacks.

    Args:
        filename (str): Original filename

    Returns:
        str: Sanitized filename
    """
    import os
    import re

    # Get basename (removes any path components)
    filename = os.path.basename(filename)

    # Remove any characters that aren't alphanumeric, dash, underscore, or dot
    filename = re.sub(r'[^\w\-\.]', '_', filename)

    # Prevent multiple dots (could hide extension)
    filename = re.sub(r'\.{2,}', '.', filename)

    # Ensure filename isn't empty
    if not filename or filename == '.':
        filename = 'unnamed_file'

    return filename
```

**Update Forms to Use Sanitization:**

```python
# patients/forms.py
from ndas.custom_codes.sanitization import sanitize_html, sanitize_plain_text

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['baby_name', 'mother_name', 'problems', ...]

    def clean_baby_name(self):
        """Sanitize baby name - plain text only."""
        baby_name = self.cleaned_data.get('baby_name')
        return sanitize_plain_text(baby_name)

    def clean_mother_name(self):
        """Sanitize mother name - plain text only."""
        mother_name = self.cleaned_data.get('mother_name')
        return sanitize_plain_text(mother_name)

    def clean_problems(self):
        """Sanitize problems field - allow some HTML formatting."""
        problems = self.cleaned_data.get('problems')
        if problems:
            return sanitize_html(problems)
        return problems

    def clean_resustn_note(self):
        """Sanitize resuscitation notes - allow medical formatting."""
        resustn_note = self.cleaned_data.get('resustn_note')
        if resustn_note:
            return sanitize_html(resustn_note)
        return resustn_note


class AttachmentkForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ['title', 'file', 'description', ...]

    def clean_title(self):
        """Sanitize title - plain text only."""
        title = self.cleaned_data.get('title')
        return sanitize_plain_text(title)

    def clean_description(self):
        """Sanitize description - allow some HTML."""
        description = self.cleaned_data.get('description')
        if description:
            return sanitize_html(description)
        return description

    def clean_file(self):
        """Sanitize and validate uploaded file."""
        file = self.cleaned_data.get('file')
        if file:
            from ndas.custom_codes.sanitization import sanitize_filename
            file.name = sanitize_filename(file.name)
        return file
```

**Estimated Time:** 4 hours
**Benefit:** Additional XSS protection layer, file upload security

---

### Issue 4.4: Add Comprehensive Security Tests

**Create:** `tests/test_security.py`

```python
"""
Security-focused test suite for NDAS.
Tests CSRF protection, CSP headers, rate limiting, and authentication security.
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.conf import settings
from users.models import CustomUser


class CSRFProtectionTestCase(TestCase):
    """Test CSRF protection on POST endpoints."""

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!',
            mobile_primary='0771234567'
        )

    def test_login_requires_csrf_token(self):
        """POST to login without CSRF token should fail."""
        response = self.client.post(reverse('user-login'), {
            'username': 'testuser',
            'password': 'TestPass123!'
        })
        self.assertEqual(response.status_code, 403)

    def test_patient_add_requires_csrf_token(self):
        """POST to patient add without CSRF token should fail."""
        self.client.force_login(self.user)
        response = self.client.post(reverse('patient-add'), {
            'baby_name': 'Test Baby'
        })
        self.assertEqual(response.status_code, 403)


class SecurityHeadersTestCase(TestCase):
    """Test security headers are properly set."""

    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!',
            mobile_primary='0771234567'
        )

    @override_settings(DEBUG=False)
    def test_csp_headers_in_production(self):
        """CSP headers should be present in production."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertIn('Content-Security-Policy', response)

        csp = response['Content-Security-Policy']

        # In production, unsafe-inline and unsafe-eval should NOT be present
        self.assertNotIn('unsafe-inline', csp)
        self.assertNotIn('unsafe-eval', csp)

    def test_x_frame_options_deny(self):
        """X-Frame-Options should be DENY."""
        response = self.client.get(reverse('user-login'))
        self.assertIn('X-Frame-Options', response)
        self.assertEqual(response['X-Frame-Options'], 'DENY')

    def test_x_content_type_options(self):
        """X-Content-Type-Options should be nosniff."""
        response = self.client.get(reverse('user-login'))
        self.assertIn('X-Content-Type-Options', response)
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')


class AuthenticationSecurityTestCase(TestCase):
    """Test authentication security measures."""

    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!',
            mobile_primary='0771234567'
        )

    def test_no_username_enumeration(self):
        """Invalid username and invalid password should return same message."""
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

        # Both should have same error message
        messages1 = list(response1.context['messages'])
        messages2 = list(response2.context['messages'])

        self.assertTrue(len(messages1) > 0)
        self.assertTrue(len(messages2) > 0)

        # Messages should be identical (prevents username enumeration)
        self.assertEqual(str(messages1[0]), str(messages2[0]))


class RateLimitingTestCase(TestCase):
    """Test rate limiting on authentication endpoints."""

    def setUp(self):
        self.client = Client()

    @override_settings(RATELIMIT_ENABLE=True)
    def test_login_rate_limiting(self):
        """Excessive login attempts should be rate limited."""
        # Attempt to login 10 times with wrong credentials
        for i in range(10):
            response = self.client.post(reverse('user-login'), {
                'username': f'user{i}',
                'password': 'wrongpass'
            })

        # Next attempt should be rate limited
        response = self.client.post(reverse('user-login'), {
            'username': 'testuser',
            'password': 'wrongpass'
        }, follow=True)

        # Should show rate limit message
        messages = list(response.context['messages'])
        self.assertTrue(
            any('too many' in str(m).lower() for m in messages),
            "Rate limit message not found"
        )


class InputSanitizationTestCase(TestCase):
    """Test input sanitization prevents XSS."""

    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!',
            mobile_primary='0771234567',
            is_staff=True
        )
        self.client.force_login(self.user)

    def test_xss_in_patient_name(self):
        """XSS attempt in patient name should be sanitized."""
        from patients.forms import PatientForm

        form_data = {
            'baby_name': '<script>alert("XSS")</script>Test Baby',
            'mother_name': 'Test Mother',
            'gender': 'MALE',
            'dob_tob': '2024-01-01 10:00',
            'birth_weight': 3000,
            'ofc': 35,
            'tp_mobile': '0771234567',
            # ... other required fields
        }

        form = PatientForm(data=form_data)
        if form.is_valid():
            patient = form.save(commit=False)
            # Script tag should be escaped/removed
            self.assertNotIn('<script>', patient.baby_name)
            self.assertNotIn('alert', patient.baby_name)
```

**Run Tests:**
```bash
python manage.py test tests.test_security
```

**Estimated Time:** 6 hours
**Benefit:** Automated security regression testing

---

## Phase 5: Testing & Validation (Week 6)

**Priority:** HIGH - Ensures changes work correctly
**Total Time:** 22 hours

### Task 5.1: Add Unit Tests for Refactored Views

**Create:** `patients/tests/test_views.py`

```python
"""
Unit tests for patient views.
"""
from django.test import TestCase, Client
from django.urls import reverse
from patients.models import Patient
from users.models import CustomUser
from datetime import datetime


class PatientManagerTestCase(TestCase):
    """Test unified patient manager view with all filter types."""

    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!',
            mobile_primary='0771234567',
            is_staff=True
        )
        self.client.force_login(self.user)

        # Create test patients
        self.patient1 = Patient.objects.create(
            baby_name='Test Baby 1',
            mother_name='Test Mother 1',
            bht='BHT001',
            gender='MALE',
            dob_tob=datetime(2024, 1, 1, 10, 0),
            birth_weight=3000,
            ofc=35,
            tp_mobile='0771234567',
            pog_wks=40,
            pog_days=0,
            apgar_1=9,
            apgar_5=10,
            apgar_10=10,
            mo_delivery='NVD',
            added_by=self.user
        )

        self.patient2 = Patient.objects.create(
            baby_name='Test Baby 2',
            mother_name='Test Mother 2',
            bht='BHT002',
            gender='FEMALE',
            dob_tob=datetime(2024, 2, 1, 10, 0),
            birth_weight=2800,
            ofc=33,
            tp_mobile='0771234568',
            pog_wks=38,
            pog_days=5,
            apgar_1=8,
            apgar_5=9,
            apgar_10=10,
            mo_delivery='LSCS',
            added_by=self.user
        )

    def test_patient_manager_all(self):
        """Test patient manager with 'all' filter."""
        response = self.client.get(reverse('patients:manager'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Baby 1')
        self.assertContains(response, 'Test Baby 2')

    def test_patient_manager_with_search(self):
        """Test patient manager search functionality."""
        response = self.client.get(reverse('patients:manager'), {
            'search': 'Baby 1'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Baby 1')
        self.assertNotContains(response, 'Test Baby 2')

    def test_patient_manager_search_by_bht(self):
        """Test search by BHT number."""
        response = self.client.get(reverse('patients:manager'), {
            'search': 'BHT001'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Baby 1')
        self.assertNotContains(response, 'Test Baby 2')

    def test_patient_manager_pagination(self):
        """Test pagination works correctly."""
        # Create 15 patients to test pagination (10 per page)
        for i in range(3, 18):
            Patient.objects.create(
                baby_name=f'Test Baby {i}',
                mother_name=f'Test Mother {i}',
                bht=f'BHT{i:03d}',
                gender='MALE',
                dob_tob=datetime(2024, 1, i, 10, 0),
                birth_weight=3000,
                ofc=35,
                tp_mobile=f'077123456{i}',
                pog_wks=40,
                pog_days=0,
                apgar_1=9,
                apgar_5=10,
                apgar_10=10,
                mo_delivery='NVD',
                added_by=self.user
            )

        # Test page 1
        response = self.client.get(reverse('patients:manager'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['patients_page_obj']), 10)

        # Test page 2
        response = self.client.get(reverse('patients:manager'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.context['patients_page_obj']) > 0)

    def test_patient_manager_filter_types(self):
        """Test all filter type variations."""
        filter_types = [
            'all', 'diagnosed', 'dx_normal', 'dx_gma_normal',
            'dx_gma_abnormal', 'dx_hine', 'dx_da_normal',
            'dx_da_abnormal', 'discharged'
        ]

        for filter_type in filter_types:
            response = self.client.get(
                reverse('patients:manager-filtered', kwargs={'filter_type': filter_type})
            )
            self.assertEqual(
                response.status_code, 200,
                f"Filter type '{filter_type}' failed"
            )
            self.assertIn('filter_type', response.context)
            self.assertEqual(response.context['filter_type'], filter_type)
```

**Estimated Time:** 8 hours
**Benefit:** Prevents regressions in refactored code

---

### Task 5.2: Add Integration Tests

**Create:** `tests/test_integration.py`

```python
"""
Integration tests for complete workflows.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from patients.models import Patient, GMAssessment
from video.models import Video
from users.models import CustomUser
from datetime import datetime
import os


class PatientWorkflowIntegrationTest(TestCase):
    """Test complete patient workflow from creation to assessment."""

    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            username='testdoctor',
            email='doctor@example.com',
            password='SecurePass123!',
            mobile_primary='0771234567',
            is_staff=True
        )
        self.client.force_login(self.user)

    def test_complete_patient_workflow(self):
        """
        Test complete workflow:
        1. Create patient
        2. Upload video
        3. Create GM assessment
        4. View patient timeline
        """
        # Step 1: Create patient
        patient_data = {
            'baby_name': 'Integration Test Baby',
            'mother_name': 'Integration Test Mother',
            'bht': 'BHT-INT-001',
            'gender': 'MALE',
            'dob_tob': '2024-01-01 10:00',
            'birth_weight': 3200,
            'ofc': 36,
            'tp_mobile': '0771234567',
            'pog_wks': 40,
            'pog_days': 2,
            'apgar_1': 9,
            'apgar_5': 10,
            'apgar_10': 10,
            'mo_delivery': 'NVD',
        }

        response = self.client.post(
            reverse('patient-add'),
            patient_data,
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        # Verify patient was created
        patient = Patient.objects.get(bht='BHT-INT-001')
        self.assertEqual(patient.baby_name, 'Integration Test Baby')

        # Step 2: Upload video for this patient
        # Create a small test video file
        video_content = b'fake video content for testing'
        video_file = SimpleUploadedFile(
            "test_video.mp4",
            video_content,
            content_type="video/mp4"
        )

        video_data = {
            'title': 'Integration Test Video',
            'patient': patient.id,
            'recorded_on': '2024-01-15 14:00',
            'description': 'Test video for integration testing',
            'video_file': video_file,
        }

        response = self.client.post(
            reverse('video:add'),
            video_data,
            follow=True
        )

        # Verify video was uploaded
        video = Video.objects.filter(title='Integration Test Video').first()
        self.assertIsNotNone(video)
        self.assertEqual(video.patient, patient)

        # Step 3: Create GM assessment
        assessment_data = {
            'patient': patient.id,
            'video_file': video.id,
            'assessment_date': '2024-01-15',
            'diagnosis_conclusion': 'NORMAL',
            # ... other assessment fields
        }

        response = self.client.post(
            reverse('gm-assessment-add'),
            assessment_data,
            follow=True
        )

        # Verify assessment was created
        assessment = GMAssessment.objects.filter(patient=patient).first()
        self.assertIsNotNone(assessment)
        self.assertEqual(assessment.video_file, video)

        # Step 4: View patient timeline
        response = self.client.get(
            reverse('patient-view', kwargs={'pk': patient.pk})
        )
        self.assertEqual(response.status_code, 200)

        # Timeline should show all events
        self.assertContains(response, 'Integration Test Baby')
        self.assertContains(response, 'Integration Test Video')

        # Cleanup
        if video.video_file:
            if os.path.exists(video.video_file.path):
                os.remove(video.video_file.path)
```

**Estimated Time:** 6 hours
**Benefit:** Ensures complete workflows work end-to-end

---

### Task 5.3: Performance Benchmarking

**Install Django Silk:**
```bash
pip install django-silk
```

**Configuration:**
```python
# settings.py (development only)
if DEBUG:
    INSTALLED_APPS += ['silk']
    MIDDLEWARE += ['silk.middleware.SilkyMiddleware']

    SILKY_PYTHON_PROFILER = True
    SILKY_PYTHON_PROFILER_BINARY = True
    SILKY_META = True
```

**URL Configuration:**
```python
# ndas/urls.py
if settings.DEBUG:
    urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
```

**Benchmark Script:**
```python
# scripts/benchmark_dashboard.py
"""
Benchmark dashboard performance before and after optimizations.
"""
import time
from django.test import Client
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import override_settings

User = get_user_model()


def benchmark_dashboard():
    """Benchmark dashboard view performance."""
    client = Client()
    user = User.objects.first()
    client.force_login(user)

    # Reset query counter
    connection.queries_log.clear()

    # Measure time
    start_time = time.time()
    response = client.get('/')
    end_time = time.time()

    # Calculate metrics
    query_count = len(connection.queries)
    response_time = end_time - start_time

    print(f"Dashboard Performance:")
    print(f"  Response time: {response_time:.3f} seconds")
    print(f"  Database queries: {query_count}")
    print(f"  Avg query time: {response_time/query_count:.4f} seconds")

    # Show slowest queries
    queries_sorted = sorted(
        connection.queries,
        key=lambda q: float(q['time']),
        reverse=True
    )

    print(f"\nTop 5 slowest queries:")
    for i, query in enumerate(queries_sorted[:5], 1):
        print(f"  {i}. {query['time']}s - {query['sql'][:100]}...")

    return {
        'response_time': response_time,
        'query_count': query_count,
        'queries': connection.queries
    }


if __name__ == '__main__':
    import django
    django.setup()

    with override_settings(DEBUG=True):
        results = benchmark_dashboard()
```

**Run Benchmark:**
```bash
python scripts/benchmark_dashboard.py
```

**Estimated Time:** 4 hours
**Deliverable:** Before/after performance comparison report

---

### Task 5.4: Security Audit Validation

**Tools to Use:**
1. OWASP ZAP (Zed Attack Proxy)
2. Safety (Python dependency checker)
3. Bandit (Python security linter)

**Security Validation Checklist:**

```bash
# 1. Check for vulnerable dependencies
pip install safety
safety check

# 2. Run security linter on Python code
pip install bandit
bandit -r . -f json -o security_report.json

# 3. Check Django security settings
python manage.py check --deploy

# 4. Manual OWASP ZAP scan
# - Install OWASP ZAP
# - Configure proxy to localhost:8000
# - Run automated scan
# - Review and fix findings
```

**Create Security Audit Script:**
```bash
# scripts/security_audit.sh
#!/bin/bash

echo "Running NDAS Security Audit..."
echo "================================"

echo "\n1. Checking for vulnerable dependencies..."
safety check --json > security/dependency_vulnerabilities.json

echo "\n2. Running Python security linter..."
bandit -r ndas patients users video reports problemlist -f json -o security/code_security.json

echo "\n3. Checking Django deployment configuration..."
python manage.py check --deploy > security/django_deployment_check.txt

echo "\n4. Running Django security tests..."
python manage.py test tests.test_security --verbosity=2

echo "\nSecurity audit complete. Review reports in security/ directory."
```

**Estimated Time:** 4 hours
**Deliverable:** Security audit report with all critical issues resolved

---

## Implementation Timeline

### Week 1: Critical Security (MANDATORY BEFORE PRODUCTION)
- **Day 1-2:** Fix CSRF exemption, configure production email
- **Day 3:** Fix production CSP
- **Day 4-5:** Add rate limiting, fix timing attacks

### Week 2: Performance Optimization
- **Day 1-2:** Optimize dashboard queries
- **Day 3:** Optimize patient manager views
- **Day 4-5:** Add monitoring tools, benchmark improvements

### Week 3-4: Code Quality Refactoring
- **Day 1-3:** Eliminate patient manager duplication
- **Day 4:** Remove dead code, add docstrings
- **Day 5:** Standardize error handling

### Week 5: Security Hardening
- **Day 1:** Fix authentication timing attacks
- **Day 2:** Add security headers middleware
- **Day 3:** Add input sanitization
- **Day 4-5:** Write security tests

### Week 6: Testing & Validation
- **Day 1-2:** Unit tests for refactored views
- **Day 3:** Integration tests
- **Day 4:** Performance benchmarking
- **Day 5:** Security audit validation

---

## Success Criteria

### Phase 1 (Critical Security)
- [ ] All API endpoints require CSRF protection or proper token auth
- [ ] Production CSP does not contain 'unsafe-inline' or 'unsafe-eval'
- [ ] Email backend configured for production (emails send successfully)
- [ ] Rate limiting active on all authentication endpoints
- [ ] No timing attacks possible on login

### Phase 2 (Performance)
- [ ] Dashboard loads in < 1 second with 1000+ patients
- [ ] Query count reduced by at least 60%
- [ ] No N+1 queries in patient manager views

### Phase 3 (Code Quality)
- [ ] Patient manager functions reduced from 8 to 1
- [ ] No commented-out code in production
- [ ] All public functions have docstrings
- [ ] Consistent error handling across all views

### Phase 4 (Security Hardening)
- [ ] Generic error messages prevent username enumeration
- [ ] All security headers present and validated
- [ ] User input sanitized in all forms
- [ ] Security test suite passes 100%

### Phase 5 (Testing)
- [ ] Unit test coverage > 80% for refactored code
- [ ] All integration tests pass
- [ ] Performance benchmarks documented
- [ ] OWASP ZAP scan shows no high/critical vulnerabilities

---

## Maintenance & Monitoring

### Post-Implementation Monitoring

1. **Security Monitoring:**
   - Weekly: `python manage.py check --deploy`
   - Monthly: `safety check` for dependency vulnerabilities
   - Quarterly: Full OWASP ZAP security scan

2. **Performance Monitoring:**
   - Enable Django Debug Toolbar in development
   - Use django-silk for production query profiling
   - Monitor slow query logs

3. **Code Quality:**
   - Pre-commit hooks for code formatting (black, isort)
   - Monthly code review sessions
   - Track technical debt in issues

### Update Schedule

- **Dependencies:** Monthly security updates
- **Django:** Upgrade within 3 months of new LTS release
- **Security patches:** Apply within 48 hours

---

## Getting Help

If you encounter issues during implementation:

1. **Django Security:** https://docs.djangoproject.com/en/4.2/topics/security/
2. **OWASP Top 10:** https://owasp.org/www-project-top-ten/
3. **Django Performance:** https://docs.djangoproject.com/en/4.2/topics/db/optimization/
4. **Testing:** https://docs.djangoproject.com/en/4.2/topics/testing/

---

## Document Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-12-21 | Initial comprehensive improvement plan | Code Audit |

---

**END OF IMPROVEMENT PLAN**
