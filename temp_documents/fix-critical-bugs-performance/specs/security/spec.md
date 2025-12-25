# Security - Rate Limiting and Comprehensive Validation

## ADDED Requirements

### Requirement: CRUD Operation Rate Limiting
All state-changing operations (Create, Update, Delete) MUST have rate limiting to prevent abuse and DoS attacks.

#### Scenario: Patient creation rate limited per user
- **WHEN** authenticated user creates patients
- **THEN** maximum 10 creates per minute are allowed
- **AND** 11th attempt within minute is blocked with 429 status

#### Scenario: IP-based rate limit as backup
- **WHEN** user attempts to bypass user-based limit
- **THEN** IP-based limit of 20 creates per minute applies
- **AND** prevents automated attacks

#### Scenario: Delete operations more strictly limited
- **WHEN** user attempts delete operations
- **THEN** maximum 5 deletes per minute per user allowed
- **AND** maximum 10 deletes per minute per IP allowed
- **AND** prevents accidental bulk deletions

#### Scenario: Rate limit applies to all CRUD endpoints
- **WHEN** accessing any POST/PUT/DELETE endpoint
- **THEN** appropriate rate limit is enforced
- **AND** includes: patients, assessments, videos, attachments, users

#### Scenario: Rate limit reset after time window
- **WHEN** rate limit is hit at time T
- **AND** user waits 60 seconds
- **THEN** counter resets
- **AND** operations are allowed again

#### Scenario: Clear error message on rate limit
- **WHEN** rate limit is exceeded
- **THEN** user sees message "Too many requests. Please try again in a minute."
- **AND** HTTP 429 status is returned
- **AND** Retry-After header indicates wait time

### Requirement: Rate Limit Monitoring
Rate limit violations MUST be logged for security monitoring and threshold adjustment.

#### Scenario: Rate limit hits logged
- **WHEN** user exceeds rate limit
- **THEN** event is logged with user ID, IP, endpoint, timestamp
- **AND** security team can review patterns

#### Scenario: Repeated violations flagged
- **WHEN** user hits rate limit 10+ times in hour
- **THEN** automated alert is generated
- **AND** potential abuse is investigated

### Requirement: HTTP Method Restrictions
Views MUST explicitly restrict allowed HTTP methods to prevent unexpected behavior.

#### Scenario: GET-only view rejects POST
- **WHEN** sending POST to patient detail view
- **THEN** HTTP 405 Method Not Allowed is returned
- **AND** view only accepts GET

#### Scenario: POST-only delete endpoint rejects GET
- **WHEN** attempting GET request to delete endpoint
- **THEN** HTTP 405 is returned
- **AND** accidental deletions via URL access prevented

#### Scenario: Form views accept GET and POST
- **WHEN** accessing patient add/edit view
- **THEN** GET displays form
- **AND** POST processes form
- **AND** other methods return 405

### Requirement: Template Fragment Caching
Frequently rendered template components MUST use fragment caching to improve performance.

#### Scenario: Filter controls cached
- **WHEN** rendering patient manager page
- **THEN** filter controls are cached for 1 hour
- **AND** HTML is not regenerated on each request

#### Scenario: Pagination cached per page
- **WHEN** rendering pagination controls
- **THEN** cache key includes page number
- **AND** each page's pagination is cached separately

#### Scenario: Cache invalidated on data change
- **WHEN** new patient is added
- **THEN** relevant cache fragments are cleared
- **AND** updated list displays on next request

### Requirement: Static File Optimization
Static file loading MUST use performance best practices (preload, async, defer).

#### Scenario: Critical CSS preloaded
- **WHEN** page loads
- **THEN** AdminLTE and Bootstrap CSS are preloaded
- **AND** rendering is not blocked

#### Scenario: Non-critical JavaScript deferred
- **WHEN** page loads
- **THEN** AdminLTE and Bootstrap JS use defer attribute
- **AND** page becomes interactive faster

#### Scenario: Font Awesome loaded efficiently
- **WHEN** page uses icons
- **THEN** Font Awesome CSS is preloaded
- **AND** icon flash (FOUT) is minimized

## Technical Notes

### Rate Limiting Implementation

```python
from django_ratelimit.decorators import ratelimit

# For create/update operations
@login_required(login_url="user-login")
@ratelimit(key='user', rate='10/m', method='POST')
@ratelimit(key='ip', rate='20/m', method='POST')
def patient_add(request):
    # ... existing code ...

# For delete operations
@login_required(login_url="user-login")
@ratelimit(key='user', rate='5/m', method='POST')
@ratelimit(key='ip', rate='10/m', method='POST')
def patient_delete(request, pk):
    # ... existing code ...

# Check if rate limited
from django_ratelimit.core import is_ratelimited

if is_ratelimited(request, group='patient_add', key='user', rate='10/m', increment=True):
    return HttpResponse('Too many requests. Please try again in a minute.', status=429)
```

**Endpoints to protect:**
- `patients/views.py`: patient_add, patient_edit, patient_delete
- `patients/views.py`: all assessment CRUD operations
- `video/views.py`: video_add, video_edit, video_delete
- `patients/views.py`: attachment CRUD operations
- `users/views.py`: admin user management operations

### HTTP Method Restrictions

```python
from django.views.decorators.http import require_http_methods, require_GET, require_POST

@require_GET
def patient_view(request, pk):
    # ... existing code ...

@require_http_methods(["GET", "POST"])
def patient_add(request):
    # ... existing code ...

@require_POST
def patient_delete(request, pk):
    # ... existing code ...
```

### Template Fragment Caching

```django
{% load cache %}

{# Cache filter controls - rarely change #}
{% cache 3600 patient_filters %}
<div class="filter-controls">
    <!-- Lines 77-159 of patients/manager.html -->
</div>
{% endcache %}

{# Cache pagination - changes per page but can cache per page number #}
{% cache 600 patient_pagination page_obj.number %}
<div class="pagination">
    <!-- Lines 394-471 of patients/manager.html -->
</div>
{% endcache %}
```

**Cache settings required:**
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}
```

### Static File Optimization

```django
{# In templates/src/base.html #}

{# Preload critical CSS #}
<link rel="preload" href="{% static 'adminlte/dist/css/adminlte.min.css' %}" as="style">
<link rel="preload" href="{% static 'plugins/fontawesome-free/css/all.min.css' %}" as="style">

{# Load CSS #}
<link rel="stylesheet" href="{% static 'adminlte/dist/css/adminlte.min.css' %}">
<link rel="stylesheet" href="{% static 'plugins/fontawesome-free/css/all.min.css' %}">

{# Critical JavaScript (synchronous) #}
<script src="{% static 'plugins/jquery/jquery.min.js' %}"></script>

{# Defer non-critical JavaScript #}
<script defer src="{% static 'plugins/bootstrap/js/bootstrap.bundle.min.js' %}"></script>
<script defer src="{% static 'adminlte/dist/js/adminlte.min.js' %}"></script>
```

### Affected Files

**Rate Limiting:**
- `patients/views.py` - All CRUD operations
- `video/views.py` - Video CRUD operations
- `users/views.py` - User management operations

**HTTP Method Restrictions:**
- All view files - Add decorators to all views

**Template Caching:**
- `patients/manager.html` - Filter controls, pagination
- `assessment/manager.html` - Similar components
- `video/manager.html` - Similar components

**Static Files:**
- `templates/src/base.html` - Add preload/defer attributes
- `templates/src/basic_plane.html` - Same optimizations

### Performance Targets

- **Rate limit overhead:** < 5ms per request
- **Template cache hit rate:** > 80%
- **Page load time improvement:** 40-60% with caching
- **First Contentful Paint:** < 1.5 seconds
- **Time to Interactive:** < 3 seconds

### Security Targets

- **Automated attack prevention:** 100% of CRUD endpoints protected
- **DoS mitigation:** Limit impact to single user/IP
- **Method enforcement:** 0 accidental operations via wrong HTTP method
