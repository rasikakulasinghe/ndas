# Report Generation - Resource Management and Caching

## MODIFIED Requirements

### Requirement: File Handle Resource Management
Report file serving MUST properly manage file handles to prevent resource leaks.

#### Scenario: PDF download closes file handle
- **WHEN** generating and downloading PDF report
- **THEN** file is opened using context manager (with statement)
- **AND** file handle is guaranteed to close after response
- **AND** no resource leak occurs even if exception happens

#### Scenario: Multiple concurrent downloads
- **WHEN** 50 users download reports simultaneously
- **THEN** file handles are properly released after each download
- **AND** server does not exhaust file descriptors
- **AND** system remains stable

#### Scenario: Large file download handles memory
- **WHEN** downloading report larger than 10MB
- **THEN** StreamingHttpResponse is used for efficient serving
- **AND** entire file is not loaded into memory at once
- **AND** memory usage remains bounded

## ADDED Requirements

### Requirement: Report File Caching
Report downloads MUST include appropriate HTTP cache headers to improve performance.

#### Scenario: Report cached by browser
- **WHEN** user downloads same report multiple times
- **THEN** Cache-Control header specifies caching policy
- **AND** ETag header provided for validation
- **AND** Last-Modified header indicates file timestamp

#### Scenario: Conditional request returns 304
- **WHEN** browser sends If-None-Match with matching ETag
- **THEN** server returns 304 Not Modified
- **AND** file content is not re-transmitted
- **AND** bandwidth is saved

#### Scenario: Cache invalidation on report update
- **WHEN** report is regenerated
- **THEN** new ETag is computed
- **AND** browser detects change and downloads new version

### Requirement: Efficient File Serving
Report file serving MUST use efficient methods appropriate for production environment.

#### Scenario: Development uses Django FileResponse
- **WHEN** serving files in development environment
- **THEN** Django's FileResponse is used for simplicity
- **AND** files are served directly by Django

#### Scenario: Production uses web server acceleration
- **WHEN** serving files in production with Nginx
- **THEN** X-Accel-Redirect header is set
- **AND** Nginx serves file directly without Django blocking
- **AND** worker processes remain available for other requests

#### Scenario: File serve configuration detects environment
- **WHEN** settings.DEBUG is False
- **THEN** production file serving method is used
- **AND** appropriate headers for web server are set

## Technical Notes

### File Handle Fix Pattern

**Before (resource leak):**
```python
file_handle = open(file_path, 'rb')
response = FileResponse(file_handle, content_type=content_type)
```

**After (safe):**
```python
# For small files (<10MB)
with open(file_path, 'rb') as file_handle:
    response = FileResponse(file_handle.read(), content_type=content_type)

# For large files (>10MB)
from django.http import StreamingHttpResponse

def file_iterator(file_path, chunk_size=8192):
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            yield chunk

response = StreamingHttpResponse(file_iterator(file_path), content_type=content_type)
```

### Cache Headers Implementation

```python
from django.utils.http import http_date
import time
import hashlib

def download_report(request, report_id, format_type):
    # ... existing code ...

    with open(file_path, 'rb') as file_handle:
        response = FileResponse(file_handle.read(), content_type=content_type)

    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Add caching headers
    response['Cache-Control'] = 'private, max-age=3600'  # Cache for 1 hour
    response['Last-Modified'] = http_date(os.path.getmtime(file_path))

    # Add ETag for validation
    etag = hashlib.md5(f"{report_id}-{format_type}".encode()).hexdigest()
    response['ETag'] = f'"{etag}"'

    return response
```

### Production File Serving (Nginx)

```python
from django.conf import settings

def download_report(request, report_id, format_type):
    # ... existing code to find file_path ...

    if settings.DEBUG:
        # Development: Django serves file
        with open(file_path, 'rb') as f:
            response = FileResponse(f.read(), content_type=content_type)
    else:
        # Production: Nginx serves file
        response = HttpResponse()
        response['X-Accel-Redirect'] = f'/protected/{relative_path}'
        response['Content-Type'] = content_type

    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
```

**Nginx configuration:**
```nginx
location /protected/ {
    internal;
    alias /path/to/media/reports/;
}
```

### Affected Files

**reports/views.py:**
- Line 320-321: `download_report()`
- Line 341-342: `download_gm_assessment_pdf()`
- Line 360-361: `download_hine_assessment_pdf()`
- Line 379-380: `download_da_assessment_pdf()`
- Line 398-399: `download_cdic_assessment_pdf()`
- Line 417-418: `download_gpa_assessment_pdf()`

### Performance Targets

- **File handle closure:** 100% guaranteed via context managers
- **Memory usage:** < 100MB for any single file serve operation
- **Cache hit rate:** > 60% for repeated downloads
- **Production throughput:** 100+ concurrent downloads without worker exhaustion
