# NDAS Codebase Adversarial Review

> **Generated:** 2026-02-20
> **Scope:** Full codebase audit — `patients/`, `users/`, `video/`, `reports/`, `problemlist/`, `ndas/`
> **Method:** Adversarial static analysis — assumes problems exist and looks for them
> **Categories:** Security vulnerabilities · Best practice violations · Unused/dead code · Performance issues

---

## CRITICAL BUGS (Fix Immediately)

---

### BUG-01 — Method Reference Stored Instead of Method Result
**File:** `patients/views.py:399`
**Severity:** 🔴 Critical

```python
# WRONG — stores the method object itself, not the result
gm_last_assessment = var_gma.last

# CORRECT
gm_last_assessment = var_gma.last()
```

`var_gma.last` (without parentheses) stores a bound method reference. When the template accesses `gm_last_assessment`, it renders the method's string representation, not the actual last assessment. This silently produces garbage in any template that uses this value.

---

### BUG-02 — Birth Weight Validation Range Inconsistency
**File:** `patients/views.py:320` vs `CLAUDE.md`
**Severity:** 🔴 Critical

```python
# View rejects 200g as minimum
if birth_weight and (birth_weight < 200 or birth_weight > 8000):
```

CLAUDE.md documents the valid range as **300g–8000g** (basic). The view uses 200g as the lower bound. Clinicians entering a 250g premature infant's weight will be accepted by the view but rejected by the model validator — causing a confusing 500 error instead of a helpful form message.

---

### BUG-03 — Duplicate Context Key in Dashboard
**File:** `patients/views.py:175` and `patients/views.py:185`
**Severity:** 🟡 Medium

```python
context = {
    "videos_total_count": videos_total_count,   # line 175
    ...
    "videos_total_count": videos_total_count,   # line 185 — duplicate key, Python silently uses last value
}
```

Python dicts silently overwrite duplicate keys. This is a latent bug — currently both lines assign the same value, but if one line is edited in future, the other will silently take precedence.

---

## SECURITY VULNERABILITIES

---

### SEC-01 — Internal Exception Details Leaked to Client
**File:** `patients/views.py:588–594`, `patients/views.py:1195–1204`, and similar delete handlers
**Severity:** 🔴 Critical

```python
return JsonResponse({
    "success": False,
    "error": "Server error",
    "message": f"An error occurred during deletion: {str(e)}"  # leaks exception internals
}, status=500)
```

Every delete endpoint (`patient_delete`, `assessment_delete`, `bookmark_delete`, `attachment_delete`, `cdic_assessment_delete`, `hine_assessment_delete`, `da_assessment_delete`, `gpa_delete`) returns raw exception `str(e)` to the browser. This can expose:
- Database schema details (column names, table names from IntegrityError)
- File system paths (from FileNotFoundError)
- Internal model structure

**Fix:** Return a generic message to client; log the full exception server-side only.

---

### SEC-02 — `csrf_exempt` Imported But Potentially Unused
**File:** `patients/views.py:62`, `users/views.py:11`, `video/views.py:13`
**Severity:** 🟡 Medium

`csrf_exempt` is imported in three view files. Grep confirms it is not applied to any view in `patients/views.py`. Its presence is either dead import (noise) or a latent risk — if a developer assumes it is already applied and references the wrong view, it could accidentally disable CSRF protection on a sensitive endpoint. Remove all unused imports.

---

### SEC-03 — URL Routes Use `<str:pk>` for Integer IDs
**File:** `patients/urls.py` — multiple routes
**Severity:** 🟡 Medium

```python
path("patient/view/<str:pk>/", views.patient_view, name='view-patient'),
path("patient/delete/<str:pk>/", views.patient_delete, name='delete-patient'),
path("assessment/delete/<str:pk>/", views.assessment_delete, name='assessment-delete'),
# ... 15+ more routes
```

All patient/assessment/attachment routes use `<str:pk>` instead of `<int:pk>`. This means:
1. Arbitrary strings (including `../`, `%2F`, SQL fragments) reach the view before Django validates them
2. `get_object_or_404(Patient, id=pk)` will raise a `ValueError` (not 404) if `pk` is non-numeric, causing a 500 error
3. Inconsistent with video routes which correctly use `<int:video_id>`

**Fix:** Change all `<str:pk>` to `<int:pk>` for integer primary keys.

---

### SEC-04 — Missing Rate Limiting on Multiple Destructive Endpoints
**File:** Various views
**Severity:** 🟡 Medium

Views missing `@ratelimit` on POST/mutating operations:

| View | File | Issue |
|------|------|-------|
| `assessment_add` | `patients/views.py:861` | No ratelimit on POST |
| `assessment_edit` | `patients/views.py:1044` | No ratelimit on POST |
| `assessment_edit_by_fileid` | `patients/views.py:1070` | No ratelimit, no `@require_http_methods` |
| `search_results` | `patients/views.py:668` | POST endpoint, no ratelimit |
| `assessment_manager` | `patients/views.py:1207` | No `@require_GET` |
| `bookmark_manager` | `patients/views.py:1455` | No ratelimit |
| `hine_assessment_add` | `patients/views.py` | Check needed |

---

### SEC-05 — Redundant Auth Check Creates Dead Code
**File:** `patients/views.py:283–289`
**Severity:** 🟠 Low–Medium

```python
@login_required(login_url="user-login")   # handles unauthenticated users
@require_http_methods(["GET", "POST"])
def patient_add(request):
    if not request.user.is_authenticated:  # DEAD — @login_required already redirected
        messages.error(request, "You are not authorized...")
        return redirect("user-login")
```

The inner auth check is unreachable dead code. `@login_required` redirects before the function body executes. This is misleading to readers.

---

### SEC-06 — Login Rate Limit Enables Username Enumeration
**File:** `users/views.py:32–33`
**Severity:** 🟡 Medium

```python
@ratelimit(key='post:username', rate='3/m', method='POST', block=True)
```

Rate limiting by username means: after 3 failed attempts, username `X` is blocked. An attacker can enumerate valid usernames by seeing which usernames trigger the 429 response vs which usernames always fail silently. Should rate limit by IP (`key='ip'`) first, then username.

---

### SEC-07 — `attachment_delete_confirm` Uses `.objects.get()` Without 404
**File:** `patients/views.py:2211`
**Severity:** 🟡 Medium

```python
def attachment_delete_confirm(request, pk):
    """DEPRECATED: Use unified delete modal instead"""
    attachment = Attachment.objects.get(id=pk)  # unhandled DoesNotExist
```

This deprecated view (still in the codebase) uses raw `.get()` which raises an unhandled `ObjectDoesNotExist`, producing a 500 error for invalid IDs.

---

### SEC-08 — CSP Allows `unsafe-eval` and `unsafe-inline` in Debug Mode
**File:** `ndas/settings.py:286–287`
**Severity:** 🟠 Low (debug-only)

```python
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'", ...)
```

Development CSP entirely disables XSS protections. If a developer runs the app with `DEBUG=True` against real patient data (common practice), there is zero XSS protection. Should maintain minimal CSP even in debug.

---

### SEC-09 — Patient Data in Context Even When Permission Denied
**File:** `patients/views.py:599–611`
**Severity:** 🟠 Low

```python
def patient_delete_confirm(request, pk):
    patient = get_object_or_404(Patient, id=pk)
    if user.is_superuser:
        return render(request, "...", {"patient": patient})
    else:
        return render(request, "...", {"patient": patient, "hide": True})
```

Even when the user lacks delete permission, the full `patient` object is passed to the template context. If the template has a bug or a `hide` flag is ignored, patient data is exposed. Should only pass the patient object when permission is confirmed.

---

## BEST PRACTICE VIOLATIONS

---

### BP-01 — Multiple Views Use `.objects.get()` Instead of `get_object_or_404()`
**File:** `patients/views.py` — 10 occurrences
**Severity:** 🟡 Medium
**Violates:** CLAUDE.md "Use `get_object_or_404()` not `.objects.get()`"

```
patients/views.py:709  — Patient.objects.get(bht=search_text)
patients/views.py:726  — Patient.objects.get(pin=search_text)
patients/views.py:743  — Patient.objects.get(nnc_no=search_text)
patients/views.py:1071 — GMAssessment.objects.get(video_file=pk)
patients/views.py:1444 — Help.objects.get(id=pk)
patients/views.py:1630 — Bookmark.objects.get(id=pk)
patients/views.py:1738 — CustomUser.objects.get(username=username)
patients/views.py:2211 — Attachment.objects.get(id=pk)
patients/views.py:2801 — HINEAssessment.objects.get(pk=hine_id)
patients/views.py:3025 — HINEAssessment.objects.get(id=hine_id)
```

Each of these raises an unhandled `ObjectDoesNotExist` on missing records, producing 500 errors instead of proper 404 responses.

---

### BP-02 — Six Deprecated Views Still in Codebase
done
---

### BP-03 — Module-Level Logger Overridden Inside Function Bodies
**File:** `patients/views.py` — multiple views
**Severity:** 🟠 Low

```python
# Line 75 — correct module-level logger
logger = logging.getLogger("django")

# Line 867 — inside assessment_add() — redundant and inconsistent
logger = logging.getLogger(__name__)

# Lines 968, 1008 — same pattern repeated
```

The module-level logger uses `"django"` logger name, but in-function loggers use `__name__`. These are different loggers with different configurations. Logs from assessment operations go to the wrong logger.

---

### BP-04 — Redundant Imports Inside Function Bodies
**File:** `patients/views.py:863–865`
**Severity:** 🟠 Low

```python
def assessment_add(request, ptid, fid):
    from django.http import JsonResponse          # already imported at line 65
    from django.core.exceptions import ValidationError  # already imported at line 68
    import logging                                 # already imported at line 64
```

All three are already imported at module level. The in-function imports are wasteful (Python caches them but it's still noise) and misleading.

---

### BP-05 — Unused Imports in `patients/views.py`
**File:** `patients/views.py`
**Severity:** 🟠 Low

Imports confirmed as unused by absence of usage in the full view file:

```python
import pytz           # line 64 — no timezone.activate() calls found
import subprocess     # line 64 — not used in views (used in custom_methods.py)
import tempfile       # line 64 — not used in views
from django.core.files.storage import FileSystemStorage  # line 71 — unused
from django.core.files import File                       # line 70 — unused
from django.views.decorators.csrf import csrf_exempt     # line 62 — unused
```

---

### BP-06 — `search_results` Does Manual Method Check Instead of Decorator
**File:** `patients/views.py:668–677`
**Severity:** 🟠 Low

```python
@login_required(login_url="user-login")
def search_results(request):
    if request.method != "POST":  # manual check instead of @require_POST
        messages.warning(...)
        return redirect("search-start")
```

Should use `@require_http_methods(["POST"])` per CLAUDE.md patterns. Also missing `@ratelimit`.

---

### BP-07 — Validation Duplicated Between Forms and Views
**File:** `patients/views.py:298–332` and `patients/forms.py`
**Severity:** 🟡 Medium

APGAR, POG, birth weight, and date validation appear in both the view (`patient_add`) and the form/model validators. This violates DRY: when one range changes, the other must be updated manually. All validation belongs in the form's `clean_<field>()` methods.

---

### BP-08 — `assessment_edit_by_fileid` Missing All Security Decorators
**File:** `patients/views.py:1069–1088`
**Severity:** 🟡 Medium

```python
@login_required(login_url="user-login")   # ← only this
def assessment_edit_by_fileid(request, pk):
    assmnt = GMAssessment.objects.get(video_file=pk)   # no 404, no method guard, no ratelimit
```

Compared to `patient_edit` which has `@handle_view_errors`, `@ratelimit`, and `@require_http_methods`, this view has only `@login_required`. A POST request with an invalid `pk` will produce a 500 error.

---

### BP-09 — `help_article` Uses `.objects.get()` With Manual Exception Catching
**File:** `patients/views.py:1443–1447`
**Severity:** 🟠 Low

```python
try:
    article = Help.objects.get(id=pk)
except Help.DoesNotExist:
    messages.error(request, "Help article not found.")
    return redirect("help-home")
```

This is an anti-pattern that `get_object_or_404()` was invented to solve. The manual catch also misses non-DoesNotExist exceptions from the DB.

---

## PERFORMANCE ISSUES

---

### PERF-01 — `get_userStats()` Is an N+1 Query Catastrophe
**File:** `ndas/custom_codes/custom_methods.py:41–73`
**Severity:** 🔴 Critical

```python
def get_userStats():
    user_list = CustomUser.objects.all()           # 1 query
    pt_list = Patient.objects.all()               # 1 query (loads ALL patients)
    video_list = Video.objects.all()              # 1 query (loads ALL videos)
    gma_list = GMAssessment.objects.all()         # 1 query (loads ALL assessments)
    hine_list = HINEAssessment.objects.all()      # 1 query
    da_list = DevelopmentalAssessment.objects.all()  # 1 query
    cdic_list = CDICRecord.objects.all()          # 1 query
    attachments_list = Attachment.objects.all()   # 1 query (loads ALL)
    bookmark_list = Bookmark.objects.all()        # 1 query

    for u_o in user_list:                         # N iterations
        user_stats_val = {
            'Patient': getCountZeroIfNone(pt_list.filter(added_by=u_o)),  # 1 query per user
            'Video': getCountZeroIfNone(video_list.filter(added_by=u_o)), # 1 query per user
            ... # 6 more queries PER USER
        }
```

With 10 users: **9 initial queries + (10 users × 8 filtered queries) = 89 queries** per dashboard load.
With 50 users: **9 + 400 = 409 queries** per dashboard load.
Additionally, **all records are loaded into Python memory** even though only counts are needed.

**Fix:** Use a single query with `Count` annotations grouped by user:
```python
Patient.objects.values('added_by').annotate(count=Count('id'))
```

---

### PERF-02 — Dashboard Loads All Bookmarks Into Memory
**File:** `patients/views.py:128`
**Severity:** 🔴 Critical

```python
bookmark = Bookmark.objects.all()   # loads EVERY bookmark in the system
```

This queryset is evaluated somewhere in the template. As the system grows to hundreds of bookmarks, this loads them all into memory on every dashboard hit. There is no pagination, no `.count()`, no limit. The variable `bookmark` is passed to the context — unclear what the template does with it. Almost certainly should be `Bookmark.objects.filter(owner=request.user)` with a limit.

---

### PERF-03 — `get_admissions_data_barchart()` Uses Non-Timezone-Aware Date
**File:** `ndas/custom_codes/custom_methods.py:78`
**Severity:** 🟡 Medium

```python
today = datetime.now().date()   # naive, not timezone-aware
```

With `USE_TZ = True` and `TIME_ZONE = 'Asia/Kolkata'`, this may produce incorrect date boundaries. Should use:
```python
today = timezone.now().date()
```

---

### PERF-04 — Model Properties Execute Queries on Every Access
**File:** `patients/models.py` — multiple `@property` definitions
**Severity:** 🔴 Critical

Properties like `isDischarged`, `isScreeningPositive`, `isBookmarked`, and others execute database queries every time they're accessed. When a patient list renders 10–50 patients, each property access triggers a query:

```python
@property
def isDischarged(self):
    latest_record = CDICRecord.objects.filter(patient=self).order_by("-id").first()
    # ↑ 1 DB query per patient in any list view
```

A list of 50 patients with 5 such properties = **250 extra queries per page load**, on top of the base list query.

---

### PERF-05 — Multiple Duplicate Assessment Manager Views
**File:** `patients/views.py:1239–1402`
**Severity:** 🟡 Medium (Maintainability + Performance)

Five separate views (`assessment_manager_recent`, `assessment_manager_normal`, `assessment_manager_abnormal`, `assessment_manager_informed`, `assessment_manager_not_informed`) copy-paste the identical pattern:
1. Get search query
2. Build filtered queryset with `select_related`
3. Apply search filter
4. Paginate

This duplicates ~30 lines of code 5 times. Like `patient_manager` was refactored into a single unified view with a `filter_type` parameter, these should be unified into `assessment_manager(filter_type='all')`.

---

### PERF-06 — `assessment_manager_by_patients` Missing `select_related`
**File:** `patients/views.py:1412`
**Severity:** 🟡 Medium

```python
assessment_list = GMAssessment.objects.filter(patient=patient)
# ↑ Missing: .select_related('patient', 'added_by', 'last_edit_by', 'video_file')
```

Every other `assessment_manager_*` view correctly uses `select_related`, but this one doesn't. In a template rendering 10 assessments, this causes 30–40 extra queries.

---

### PERF-07 — `search_results` Loads All Users on Every Validation Failure
**File:** `patients/views.py:688–703`
**Severity:** 🟠 Low–Medium

```python
if not combo_pt_param_type:
    messages.error(request, "Please select a patient search parameter.")
    username_list = CustomUser.objects.all()   # loads ALL users — no select_related, no limit
    return render(request, "patients/search.html", {"username_list": username_list})
```

This pattern appears 5 times in `search_results`. Every validation error path loads all users from the database with no `select_related('groups', 'user_permissions')`. Should load the user list once before the validation checks begin.

---

### PERF-08 — Full Querysets Passed to Template for Delete Modals
**File:** `patients/views.py:451–474`
**Severity:** 🟠 Low

```python
context = {
    "var_file_video": var_file_video,          # full queryset — all patient videos
    "var_file_attachments": var_file_attachments,   # full queryset — all attachments
    "var_gma": var_gma,                        # full queryset — all GMA assessments
    "var_hine": var_hine,                      # full queryset — all HINE assessments
    "var_da": var_da,                          # ...
    "var_cdic": var_cdic,
    "var_gpa": var_gpa,
}
```

These querysets are lazy until the template accesses them, but passing 7 full querysets to the template for delete modal rendering is excessive. Delete modals only need counts (already in context) and the patient name. The full querysets serve no purpose here.

---

## DEAD CODE / UNUSED ITEMS

---

### DEAD-01 — `DATABASE_ENGINE_OPTIONS` Contains MySQL-Specific Settings
**File:** `ndas/settings.py:416–421`
**Severity:** 🟡 Medium

```python
DATABASE_ENGINE_OPTIONS = {
    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",   # MySQL only
    'charset': 'utf8mb4',                                    # MySQL only
    'autocommit': True,                                      # MySQL only
}
```

This dictionary is defined but **never referenced** by the `DATABASES` setting. Even if it were, these are MySQL-specific options that have no effect on PostgreSQL or SQLite (the two databases actually used). This is dead configuration that will mislead anyone reading the settings.

---

### DEAD-02 — `CONN_MAX_AGE` Defined Twice
**File:** `ndas/settings.py:112` and `ndas/settings.py:447`

```python
# Line 112 — correctly sets DB connection pooling
if not DEBUG:
    DATABASES['default']['CONN_MAX_AGE'] = 300

# Line 447 — defines a module-level variable that has no effect on Django
CONN_MAX_AGE = 300
```

The second definition is a plain Python variable. Django reads `CONN_MAX_AGE` from `DATABASES['default']`, not from module scope. This setting has no effect.

---

### DEAD-03 — `COMPRESS_ENABLED` / `COMPRESS_OFFLINE` Without `django-compressor`
**File:** `ndas/settings.py:438–440`

```python
if not DEBUG:
    COMPRESS_ENABLED = config('COMPRESS_ENABLED', default=True, cast=bool)
    COMPRESS_OFFLINE = config('COMPRESS_OFFLINE', default=True, cast=bool)
```

These settings require `django-compressor` in `INSTALLED_APPS`. Neither `django-compressor` is in requirements nor `compressor` appears in `INSTALLED_APPS`. These settings do nothing.

---

### DEAD-04 — `SECURE_BROWSER_XSS_FILTER` Is Deprecated
**File:** `ndas/settings.py:267`

```python
SECURE_BROWSER_XSS_FILTER = True   # deprecated since Django 4.0, removed in 5.0
```

This setting was deprecated in Django 4.0 and removed in Django 5.0. Django 4.2.16 is used; this setting has no effect and generates a deprecation warning. Remove it.

---

### DEAD-05 — `django-debug-toolbar` in Requirements Without App Registration
**File:** `temp_documents/requirements_clean.txt:97`

```
django-debug-toolbar==4.2.0
```

Not listed in `INSTALLED_APPS`. Either:
1. It was installed for development but never configured — meaning it's dead weight in production requirements
2. It should be in a `requirements-dev.txt` file that doesn't exist

Either way, a production requirements file should not include debugging tools.

---

### DEAD-06 — `checkRCState` Function With Unclear Caller
**File:** `ndas/custom_codes/custom_methods.py:277–281`

```python
def checkRCState(variable):
    if 'display' in variable and isinstance(variable['display'], bool):
        return variable['display']
    else:
        return None
```

This function is defined in `custom_methods.py` and imported in `patients/models.py`, but the import grep shows only 4 files import it. Cross-referencing actual usage confirms it's called by model code. However the function's purpose and the data structure it expects (`variable` with `display` key) is undocumented. If the caller is removed, this becomes pure dead code.

---

### DEAD-07 — `MEDIA_URL_EXPIRY` and `SECURE_FILE_UPLOADS` Settings Have No Effect
**File:** `ndas/settings.py:428–429`

```python
MEDIA_URL_EXPIRY = 3600   # no Django feature reads this key
SECURE_FILE_UPLOADS = True  # no Django feature reads this key
```

These are custom-named settings that Django does not recognize. They do not affect any Django behavior unless explicitly read by custom code somewhere. If not read anywhere, they are dead configuration creating false confidence.

---

### DEAD-08 — `SILENCED_SYSTEM_CHECKS` Suppresses Security Warnings
**File:** `ndas/settings.py:432–434`

```python
SILENCED_SYSTEM_CHECKS = [
    'security.W019',
] if config('SECURE_PROXY_SSL_HEADER', default=False, cast=bool) else []
```

`W019` is the "SECURE_PROXY_SSL_HEADER not set" check. Suppressing Django security checks means `python manage.py check --deploy` will not alert on this issue. This silencing should only exist with documented justification. If not using an SSL proxy, `SECURE_PROXY_SSL_HEADER` should simply not be set.

---

### DEAD-09 — HSTS Enabled Unconditionally (Including Development)
**File:** `ndas/settings.py:269`

```python
SECURE_HSTS_SECONDS = 31536000   # 1 year — outside any DEBUG conditional
```

HSTS tells browsers to use HTTPS for 1 year. Setting this in development (even if SSL redirect is off) means browsers that connect to the dev server may cache the HSTS directive. If a developer uses a real domain name for local testing, subsequent non-HTTPS connections will be silently blocked by the browser for a year. This should be inside the `if not DEBUG:` block.

---

## CONFIGURATION ISSUES

---

### CFG-01 — Session Engine Uses Cache for Sessions Without Redis Fallback Guarantee
**File:** `ndas/settings.py:397`

```python
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
```

Sessions are stored only in the cache. In development, this is `LocMemCache` — which is **in-process memory**. This means:
1. Sessions are wiped on every server restart during development
2. Each gunicorn worker has its own separate session cache — sessions don't share between processes

For production with Redis this is fine, but in development it creates confusing behavior. Should use `cached_db` backend: `django.contrib.sessions.backends.cached_db`.

---

### CFG-02 — Race Condition in Cache-Based Throttle Pattern
**File:** `users/middleware.py:36–49`, `users/middleware.py:106–113`

```python
last_update = cache.get(cache_key)
if last_update is None:
    # Update session activity (non-atomic)
    UserSession.objects.filter(...).update(last_activity=timezone.now())
    cache.set(cache_key, timezone.now(), 60)
```

Two concurrent requests from the same user can both see `last_update is None` (before either sets the cache) and both fire the DB update. Under normal load this is benign, but in a multi-process deployment this creates unnecessary DB writes. Should use `cache.add()` which is atomic: `if cache.add(cache_key, True, 60): # do update`.

---

### CFG-03 — `EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS` Not Used in Model
**File:** `ndas/settings.py:189` and `users/models.py` (hardcoded `timedelta(hours=24)`)

```python
# settings.py
EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS = config('EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS', default=24, cast=int)

# users/models.py — hardcoded, ignores the setting
expiry_time = self.email_verification_sent_at + timedelta(hours=24)
```

The setting exists and is configurable via `.env`, but the model uses a hardcoded `24`. Changing the environment variable has no effect.

---

### CFG-04 — Subscription Singleton Pattern Lacks Database Constraint
**File:** `users/models.py` (Subscription model)

```python
def save(self, *args, **kwargs):
    self.pk = 1   # forces pk=1
    super().save(*args, **kwargs)
```

Forcing pk=1 in application code is fragile. A race condition (two simultaneous object creations) or a direct DB insert bypassing Django can create duplicate records, breaking `get_global_subscription()`. Should add a unique constraint at the DB level.

---

## SUMMARY

| # | Category | Findings | Max Severity |
|---|----------|----------|-------------|
| BUG | Critical Bugs | 3 | 🔴 Critical |
| SEC | Security | 9 | 🔴 Critical |
| BP | Best Practices | 9 | 🟡 Medium |
| PERF | Performance | 8 | 🔴 Critical |
| DEAD | Dead/Unused Code | 9 | 🟡 Medium |
| CFG | Configuration | 4 | 🟡 Medium |
| **Total** | | **42** | |

---

## PRIORITY FIX LIST

**Fix this week:**

1. `patients/views.py:399` — `gm_last_assessment = var_gma.last` → `var_gma.last()`
2. `patients/views.py:588` — Remove `str(e)` from all delete endpoint error responses
3. `ndas/custom_codes/custom_methods.py:41` — Rewrite `get_userStats()` using `values/annotate/Count`
4. `patients/views.py:128` — Replace `Bookmark.objects.all()` with filtered + limited queryset
5. `patients/urls.py` — Change all `<str:pk>` to `<int:pk>` for integer IDs
6. `patients/models.py` properties — Move DB queries out of `@property` into manager annotations

**Fix this sprint:**

7. done mannually
8. Remove unused imports: `pytz`, `subprocess`, `tempfile`, `FileSystemStorage`, `File`, `csrf_exempt` from `patients/views.py`
9. Replace all 10 raw `.objects.get()` calls with `get_object_or_404()`
10. Add `@require_http_methods` and `@ratelimit` to `assessment_add`, `assessment_edit`, `assessment_edit_by_fileid`, `search_results`, `assessment_manager`
11. Fix `EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS` — use `settings.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS` in model
12. Remove dead settings: `DATABASE_ENGINE_OPTIONS`, duplicate `CONN_MAX_AGE`, `COMPRESS_ENABLED`, `SECURE_BROWSER_XSS_FILTER`, `MEDIA_URL_EXPIRY`, `SECURE_FILE_UPLOADS`
13. Move `SECURE_HSTS_SECONDS` inside `if not DEBUG:` block
14. Merge 5 duplicate assessment manager views into one unified view with `filter_type` parameter
15. Unify validation to form `clean_<field>()` methods — remove duplicate view-level validation
