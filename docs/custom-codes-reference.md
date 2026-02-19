# NDAS Custom Codes Reference

> **Location:** `ndas/custom_codes/`
> **Purpose:** Centralized utilities, base classes, validators, and security tools used across all NDAS apps.
> **Critical:** All new code MUST use these modules. Never duplicate their functionality.

---

## Files Overview

| File | Purpose |
|------|---------|
| `Custom_abstract_class.py` | Abstract base models — inherit in ALL models |
| `choice.py` | All TextChoices and tuple choices for dropdowns |
| `validators.py` | Input/file validators, sanitization utilities |
| `sanitization.py` | HTML sanitization via bleach |
| `custom_methods.py` | Utility functions for views and models |
| `ndas_enums.py` | Application-level enumerations |
| `delete_helpers.py` | Centralized delete permission and validation |
| `error_handlers.py` | View error handling decorators |
| `security_middleware.py` | Custom security headers middleware |

---

## 1. `Custom_abstract_class.py` — Base Models

### `TimeStampedModel`
Abstract base providing automatic timestamps. **Inherit in every model.**

```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel

class MyModel(TimeStampedModel):
    pass
# Auto-provides:
#   created_at  (DateTimeField, auto_now_add=True)
#   updated_at  (DateTimeField, auto_now=True)
```

### `UserTrackingMixin`
Abstract base providing user tracking. **Inherit alongside TimeStampedModel.**

```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

class MyModel(TimeStampedModel, UserTrackingMixin):
    pass
# Auto-provides:
#   added_by      (FK → users.CustomUser, SET_NULL, related_name="%(class)s_added")
#   last_edit_by  (FK → users.CustomUser, SET_NULL, related_name="%(class)s_last_edited")
# Note: Both fields auto-populated by UserActivityMiddleware
```

**Full model pattern (mandatory):**
```python
class MyModel(TimeStampedModel, UserTrackingMixin):
    # Your fields here
    class Meta:
        pass  # Do NOT set abstract = True unless intended
```

---

## 2. `choice.py` — All Choices

**Rule:** All dropdown choices live here. Never define choices inline in models.

### Staff Position Choices
```python
from ndas.custom_codes.choice import Position
# Values: Medical Officer, Consultant, Registrar, Physiotherapist,
#         Occupational Therapist, Administrator, Nursing officer, Senior Registrar
# POSSITION = Position.choices  # legacy alias
```

### Patient / Clinical Choices
```python
from ndas.custom_codes.choice import (
    MODE_OF_DELIVERY,   # NVD, AVD, Forcep, Vacume, Emergency LSCS, Elective LSCS, VBAC, Home delivery, Other
    GENDER,             # Male, Female, Undefine
    DX_CONCLUTION,      # NORMAL, ABNORMAL
    LEVEL_OF_INDICATION, # High, Medium, Low
    POG_WKS,            # 20–42 weeks (tuple choices)
    POG_DAYS,           # 0–6 days (tuple choices)
    APGAR,              # 0–10 (tuple choices)
    LOGIN_STATUS_CHOICES, # success, failed, logout
)
```

### Video Choices
```python
from ndas.custom_codes.choice import (
    VIDEO_FORMATS,       # mp4, mov, avi, mkv, webm
    QUALITY_CHOICES,     # original, high, medium, low, mobile
    PROCESSING_STATUS,   # pending, uploading, processing, completed, failed
    ACCESS_LEVEL_CHOICES, # restricted, team, department, public
)
```

### Attachment Choices
```python
from ndas.custom_codes.choice import (
    ATTACHMENT_TYPE,               # Photo, PDF, Video (legacy)
    ATTACHMENT_TYPE_CHOICES,       # image, pdf, video, document, other (current)
    ATTACHMENT_ACCESS_LEVEL_CHOICES, # restricted, team, department, general
    SCAN_RESULT_CHOICES,           # pending, clean, infected, error
)
```

### Subscription Choices
```python
from ndas.custom_codes.choice import (
    SUBSCRIPTION_TYPE_CHOICES,   # free, commercial
    SUBSCRIPTION_STATUS_CHOICES, # active, expired, grace_period
)
```

### Bookmark Choices
```python
from ndas.custom_codes.choice import BOOKMARK_TYPE
# Values: Patient, Video, GMA, HINE, Attachment, DA, CDICR, GPA
```

### Problem List Choices (TextChoices)
```python
from ndas.custom_codes.choice import PROBLEM_STATUS, SEVERITY_CHOICES

# PROBLEM_STATUS: active, resolved, chronic, inactive
# SEVERITY_CHOICES: mild, moderate, severe, life_threatening
```

### File Size Constants
```python
from ndas.custom_codes.choice import FILE_SIZE_LIMITS, ALLOWED_EXTENSIONS
# FILE_SIZE_LIMITS: MAX_FILE_SIZE=100MB, MAX_IMAGE_SIZE=10MB, MAX_VIDEO_SIZE=2GB
# ALLOWED_EXTENSIONS: image, pdf, video, document lists
```

### Report Config
```python
from ndas.custom_codes.choice import ConfigValueTypes
# Values: STRING, INTEGER, BOOLEAN, JSON
```

---

## 3. `validators.py` — Input & File Validators

### Text Sanitization
```python
from ndas.custom_codes.validators import sanitize_text_input, sanitize_filename

# sanitize_text_input(value: str) -> str
# - Removes script tags, event handlers, dangerous protocols
# - Strips HTML tags (preserves content)
# - PRESERVES medical notation: "BP < 120/80", "Temperature > 38°C"
# - Normalizes whitespace
# Use for: all free-text user input fields

# sanitize_filename(filename: str, max_length=100) -> str
# - Removes path traversal (../, ..\)
# - Replaces invalid filesystem chars with underscores
# - Prevents hidden files (starting with .)
# - Limits length preserving extension
# Use for: all uploaded file names
```

### Validation Functions
```python
from ndas.custom_codes.validators import (
    validate_birth_weight,    # value: 200–8000g; returns (False, msg) if invalid
    validate_apgar_score,     # value: 0–10; raises ValidationError
    validate_phone_number,    # format: +999999999, up to 15 digits
    validate_video_file,      # extension + size + min 1KB check; raises ValidationError
    validate_recording_date,  # not future, not >10 years ago; raises ValidationError
    validate_pog_weeks,       # 20–44 weeks; raises ValidationError
    validate_pog_days,        # 0–6 days; raises ValidationError
    validate_attachment_file, # extension + MIME type + size; raises ValidationError
)
```

### File Validation Helpers
```python
from ndas.custom_codes.validators import (
    validate_video_file_upload,   # (file) -> (bool, message)
    validateVideoSize,            # (file) -> bool
    validateVideoType,            # (file) -> bool
    validateAttachmentSize,       # (file) -> bool (type-aware size limits)
    validateAttachmentType,       # (file) -> bool
    getVideoMaxSizeMB,            # () -> int (from settings)
    getFileType,                  # (file) -> "Image"|"Video"|"PDF"|"Document"|"Unknown"
    image_extension_validation,   # (value) Django model validator for jpg/jpeg/png
)
```

### Legacy Validators (keep for backward compat)
```python
BHT_validation(request, value)   # Validates BHT is numeric, non-empty
PHN_validation(request, value)   # Validates PHN is numeric, non-empty
NNC_validation(request, value)   # Validates NNC is numeric, non-empty
Name_baby_validation(request, value)
Name_mother_validation(request, value)
```

---

## 4. `sanitization.py` — HTML Sanitization

```python
from ndas.custom_codes.sanitization import sanitize_html, sanitize_plain_text

# sanitize_html(html_content: str, strip: bool = False) -> str
# - Uses bleach with medical-safe allowed tags
# - Allowed tags: p, br, strong, em, u, h1-h6, ul, ol, li, blockquote, pre, code,
#                 a, span, div, table, thead, tbody, tr, th, td, img
# - Allowed protocols: http, https, mailto, tel
# - Auto-linkifies URLs in content
# Use for: CKEditor / rich text field content before storage

# sanitize_plain_text(text: str, max_length: int = None) -> str
# - Strips ALL HTML tags
# - Normalizes whitespace
# - Optional length truncation with word boundary
# Use for: name fields, titles, plain text inputs

# sanitize_sql_like_pattern(pattern: str) -> str
# - Escapes %, _, \ for use in Django ORM __icontains/__startswith
# Use for: search query handling

# sanitize_search_query(query: str, max_length: int = 200) -> str
# - Removes HTML + injection chars, keeps alphanumeric and basic punctuation
# Use for: all search input fields
```

---

## 5. `custom_methods.py` — Utility Functions

### Core Utilities
```python
from ndas.custom_codes.custom_methods import getCountZeroIfNone, calculate_age_string

# getCountZeroIfNone(queryset) -> int
# - Returns 0 if None, otherwise .count()
# Use for: safe count display in templates/views

# calculate_age_string(start_date, end_date, format_type="detailed") -> str
# - format_type: "detailed" | "medical" | "simple"
# - Returns: "4 days", "1 year and 2 months", "3 weeks and 2 days", etc.
# Use for: patient age at assessment, video recording age
```

### Video Path Generators (for upload_to=)
```python
from ndas.custom_codes.custom_methods import (
    get_video_path_file_name,      # upload_to for original video files
    get_compressed_video_path,     # upload_to for compressed video files
    get_video_thumbnail_path,      # upload_to for video thumbnails
    get_attachment_path_file_name, # upload_to for patient attachments
)
# All generate: media/videos/YYYY/MM/patient_name/filename_timestamp.ext
```

### Video Metadata
```python
from ndas.custom_codes.custom_methods import extract_video_metadata

# extract_video_metadata(video_file_path: str) -> dict | None
# Returns: {duration_seconds, resolution, width, height, fps, codec, bitrate}
# Tries moviepy first, falls back to ffprobe
# Returns None if extraction fails
```

### Statistics & Dashboard
```python
from ndas.custom_codes.custom_methods import (
    get_gma_diagnosis_data,        # GMA diagnosis distribution for charts
    get_all_diagnosis_data,        # {'GMA': n, 'HINE': n, 'DA': n}
    get_userStats,                 # Per-user record counts across all models
    get_admissions_data_barchart,  # Monthly patient admissions (last 5 months)
)
```

### Request Utilities
```python
from ndas.custom_codes.custom_methods import get_ip_address, getFullDeviceDetails

# get_ip_address(request) -> str
# getFullDeviceDetails(request) -> {browser, os, device, ipaddress, is_mobile, ...}
```

### File Utilities
```python
from ndas.custom_codes.custom_methods import (
    getAttachmentType,    # (filename) -> 'image'|'pdf'|'video'|'document'|'other'
    getFileSizeInMb,      # (file) -> int (ceil MB)
    getCurrentDateTime,   # () -> timezone-aware datetime
)
```

---

## 6. `ndas_enums.py` — Enumerations

```python
from ndas.custom_codes.ndas_enums import PtStatus

class PtStatus(Enum):
    NEW           = 'NEW'           # Patients without videos
    DISCHARGED    = 'DISCHARGED'    # Patients with CDICRecord is_discharged=True
    DX_NORMAL     = 'DX_NORMAL'     # Has videos, no abnormal diagnosis
    DIAGNOSED     = 'DIAGNOSED'     # Any abnormal diagnosis
    DX_GMA_NORMAL   = 'DX_GMA_NORMAL'
    DX_GMA_ABNORMAL = 'DX_GMA_ABNORMAL'
    DX_DA_NORMAL    = 'DX_DA_NORMAL'
    DX_DA_ABNORMAL  = 'DX_DA_ABNORMAL'
    DX_HINE         = 'DX_HINE'     # HINE score < 73
    ALL             = 'ALL'
# Use with: getPatientList(PtStatus.XXX)
```

---

## 7. `delete_helpers.py` — Delete System (MANDATORY)

> **Critical:** Never call `obj.delete()` directly in views. Always use this module.

```python
from ndas.custom_codes.delete_helpers import (
    has_delete_permission,
    validate_can_delete,
    get_entity_display_name,
    get_entity_warning_items,
    get_entity_detail_items,
    get_redirect_url,
)

# has_delete_permission(user, entity) -> bool
# - Superusers: can delete any entity
# - Staff: can delete own records (entity.added_by == user)
# - Staff: can always delete Bookmarks
# - Others: cannot delete anything

# validate_can_delete(entity) -> {'can_delete': bool, 'reason': str}
# - Videos: blocked if referenced in GMAssessment (assessment_count > 0)
# - Others: passes

# get_entity_warning_items(entity) -> list[str]
# - Returns user-facing warnings for the delete confirmation modal
# - Patient: lists cascade counts (videos, assessments, attachments, problems)
# - Video: warns file permanently deleted
# - User: soft delete (deactivation), audit trail preserved

# get_entity_detail_items(entity) -> dict
# - Returns display details for delete confirmation modal

# get_redirect_url(entity_type: str, patient_id=None) -> str
# Redirect mapping:
#   Patient → /manager/patient/
#   Video → /video/manager/
#   Assessments (GMAssessment, HINE, CDIC, DA, GPA) → /manager/patient/
#   Attachment → /manager/patient/
#   Bookmark → /manager/patient/
#   CustomUser → /users/admin/users/
#   Problem → /problems/manager/{patient_id}/
```

**View usage pattern:**
```python
# In delete views:
if not has_delete_permission(request.user, entity):
    messages.error(request, "Permission denied")
    return redirect(...)

result = validate_can_delete(entity)
if not result['can_delete']:
    messages.error(request, result['reason'])
    return redirect(...)

entity.delete()
return redirect(get_redirect_url(entity.__class__.__name__))
```

**Template usage:**
```django
{% load delete_modal_tags %}
{% include 'src/partials/delete_confirmation_modal.html' %}
```

---

## 8. `error_handlers.py` — View Error Decorators

```python
from ndas.custom_codes.error_handlers import handle_view_errors, log_and_suppress

# @handle_view_errors(redirect_url=None, error_message=None, render_template=None)
# Catches: ObjectDoesNotExist, ValidationError, IntegrityError, PermissionDenied, Exception
# Usage:
@handle_view_errors(redirect_url='patient-manager', error_message='Error processing patient')
def my_view(request, pk):
    ...

# @log_and_suppress(logger_name=None, default_return=None)
# For non-critical operations — logs error but suppresses it
@log_and_suppress(default_return=0)
def get_some_count():
    return expensive_operation()
```

---

## Import Quick Reference

```python
# Models
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

# Choices
from ndas.custom_codes.choice import Position, GENDER, MODE_OF_DELIVERY, APGAR, POG_WKS, POG_DAYS
from ndas.custom_codes.choice import PROBLEM_STATUS, SEVERITY_CHOICES
from ndas.custom_codes.choice import VIDEO_FORMATS, PROCESSING_STATUS, QUALITY_CHOICES

# Validators
from ndas.custom_codes.validators import sanitize_text_input, sanitize_filename
from ndas.custom_codes.validators import validate_birth_weight, validate_apgar_score
from ndas.custom_codes.validators import validate_video_file, validate_attachment_file

# Sanitization
from ndas.custom_codes.sanitization import sanitize_html, sanitize_plain_text, sanitize_search_query

# Utilities
from ndas.custom_codes.custom_methods import (
    getCountZeroIfNone, calculate_age_string, extract_video_metadata,
    get_video_path_file_name, get_attachment_path_file_name
)

# Enums
from ndas.custom_codes.ndas_enums import PtStatus

# Delete system
from ndas.custom_codes.delete_helpers import (
    has_delete_permission, validate_can_delete,
    get_entity_warning_items, get_entity_detail_items, get_redirect_url
)

# Error handling
from ndas.custom_codes.error_handlers import handle_view_errors, log_and_suppress
```
