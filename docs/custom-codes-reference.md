# NDAS Custom Codes Reference

> The `ndas/custom_codes/` directory is the shared utility library for the entire NDAS project. All apps import from here. Never add choices inline in models, never duplicate validators — always use these shared modules.

---

## Directory Overview

| File | Purpose | Key Exports |
|------|---------|-------------|
| `Custom_abstract_class.py` | Abstract base model mixins with auto-tracking fields | `TimeStampedModel`, `UserTrackingMixin` |
| `choice.py` | All TextChoices, tuple choices, and constants for model fields | `Position`, `ConfigValueTypes`, `UserType`, `SubscriptionStatus`, `ReferralStatus`, `NotificationType`, `PROBLEM_STATUS`, `SEVERITY_CHOICES`, `MODE_OF_DELIVERY`, `GENDER`, `BOOKMARK_TYPE`, `ATTACHMENT_TYPE`, `DX_CONCLUTION`, `POG_WKS`, `POG_DAYS`, `APGAR`, `VIDEO_FORMATS`, `QUALITY_CHOICES`, `PROCESSING_STATUS`, `ACCESS_LEVEL_CHOICES`, `ATTACHMENT_TYPE_CHOICES`, `ATTACHMENT_ACCESS_LEVEL_CHOICES`, `SCAN_RESULT_CHOICES`, `SUBSCRIPTION_TYPE_CHOICES`, `SUBSCRIPTION_STATUS_CHOICES`, `FILE_SIZE_LIMITS`, `ALLOWED_EXTENSIONS`, `LOGIN_STATUS_CHOICES` |
| `validators.py` | Field validators, file validation, upload path helpers, and `sanitize_text_input()` / `sanitize_filename()` | `sanitize_text_input`, `sanitize_filename`, `validate_birth_weight`, `validate_apgar_score`, `validate_video_file`, `validate_attachment_file`, `validateVideoType`, `validateVideoSize`, `validateAttachmentType`, `validateAttachmentSize`, `get_institution_video_path`, `get_institution_attachment_path`, `get_institution_logo_path` |
| `sanitization.py` | HTML sanitization using bleach; SQL/search query sanitization | `sanitize_html`, `sanitize_plain_text`, `sanitize_filename`, `sanitize_sql_like_pattern`, `sanitize_search_query` |
| `custom_methods.py` | General utility functions: path generators, data aggregators, age calculation, video metadata | `getCountZeroIfNone`, `calculate_age_string`, `extract_video_metadata`, `getPatientList`, `institution_scope`, `get_video_path_file_name`, `get_attachment_path_file_name` |
| `ndas_enums.py` | Python Enum classes used as type-safe constants | `PtStatus` |
| `delete_helpers.py` | Deletion permission checks, business rule validation, and modal data builders | `has_delete_permission`, `validate_can_delete`, `get_entity_warning_items`, `get_entity_detail_items`, `get_entity_display_name`, `get_redirect_url` |
| `security_middleware.py` | Custom security header middleware classes | `AdditionalSecurityHeadersMiddleware`, `SecurityHeadersValidationMiddleware` |
| `error_handlers.py` | View error-handling decorators for consistent exception management | `handle_view_errors`, `log_and_suppress` |

---

## `Custom_abstract_class.py` — Base Models

### TimeStampedModel

Abstract Django model that provides self-updating timestamp fields. All NDAS models must inherit this as part of the standard base.

**Fields added:**

| Field | Type | Behaviour |
|-------|------|-----------|
| `created_at` | `DateTimeField` | Set once on record creation (`auto_now_add=True`). Never changes. |
| `updated_at` | `DateTimeField` | Updated automatically on every `.save()` call (`auto_now=True`). |

```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel

class MyModel(TimeStampedModel):
    # created_at and updated_at are automatically available
    pass
```

---

### UserTrackingMixin

Abstract Django model that stores ForeignKey references to the user who created the record and the user who last modified it. Fields are auto-populated by `UserActivityMiddleware` — views do not need to set these manually.

**Fields added:**

| Field | Type | Behaviour |
|-------|------|-----------|
| `added_by` | `ForeignKey → users.CustomUser` | `SET_NULL` on user deletion. Populated by middleware on create. |
| `last_edit_by` | `ForeignKey → users.CustomUser` | `SET_NULL` on user deletion. Updated by middleware on every save. |

Both fields are `null=True, blank=True`. The `related_name` uses `%(class)s_added` and `%(class)s_last_edited` patterns to avoid clashes across models.

```python
from ndas.custom_codes.Custom_abstract_class import UserTrackingMixin

class MyModel(UserTrackingMixin):
    # added_by and last_edit_by are automatically available
    pass
```

---

### Combined Usage (Standard NDAS Pattern — Mandatory)

Every concrete model in the project must inherit both mixins. The order `TimeStampedModel, UserTrackingMixin` is the project convention.

```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

class MyModel(TimeStampedModel, UserTrackingMixin):
    name = models.CharField(max_length=200)
    # Auto-provides: created_at, updated_at, added_by, last_edit_by
    # UserActivityMiddleware auto-populates added_by / last_edit_by

    class Meta:
        ordering = ['-created_at']
```

---

## `choice.py` — TextChoices and Constants

### Position *(TextChoices)*

Staff position/role for user profiles.

| Value (DB) | Display Label |
|-----------|---------------|
| `"Medical Officer"` | Medical Officer |
| `"Consultant"` | Consultant |
| `"Registrar"` | Registrar |
| `"Physiotherapist"` | Physiotherapist |
| `"Occupational Therapist"` | Occupational Therapist |
| `"Nursing officer"` | Nursing officer |
| `"Senior Registrar"` | Senior Registrar |

**Backward-compatible alias:** `POSSITION = Position.choices` (legacy tuple format).

```python
from ndas.custom_codes.choice import Position
position = models.CharField(max_length=50, choices=Position.choices)
```

---

### ConfigValueTypes *(TextChoices)*

Specifies the data type of a report configuration value.

| Value (DB) | Display Label |
|-----------|---------------|
| `"STRING"` | String |
| `"INTEGER"` | Integer |
| `"BOOLEAN"` | Boolean |
| `"JSON"` | JSON |

Used by: `reports` app configuration models.

---

### UserType *(TextChoices — Phase 2 Multi-Institution)*

Defines the three user access tiers in the multi-institution expansion.

| Value (DB) | Display Label | Description |
|-----------|---------------|-------------|
| `"USER"` | Clinician / User | Access to own institution + referral bridge |
| `"ADMIN"` | Institution Admin | Manages own institution |
| `"SUPERADMIN"` | Super Admin | Access across all institutions (`is_superuser=True`) |

---

### SubscriptionStatus *(TextChoices — Phase 2 Multi-Institution)*

Institution subscription lifecycle states.

| Value (DB) | Display Label |
|-----------|---------------|
| `"ACTIVE"` | Active |
| `"GRACE"` | Grace Period |
| `"EXPIRED"` | Expired |

Note: A separate tuple `SUBSCRIPTION_STATUS_CHOICES` exists for legacy/non-TextChoices usage.

---

### ReferralStatus *(TextChoices — Phase 2 Referral System, FR64)*

Lifecycle states for patient referrals between institutions. Progression is one-way: `PENDING → REPLIED → CLOSED`.

| Value (DB) | Display Label |
|-----------|---------------|
| `"PENDING"` | Pending |
| `"REPLIED"` | Replied |
| `"CLOSED"` | Closed |

---

### NotificationType *(TextChoices — Phase 2 Referral System, FR67–FR69)*

In-app notification types triggered by referral lifecycle events.

| Value (DB) | Display Label |
|-----------|---------------|
| `"REFERRAL_RECEIVED"` | Referral Received |
| `"REFERRAL_REPLIED"` | Referral Replied |
| `"REFERRAL_CLOSED"` | Referral Closed |

---

### PROBLEM_STATUS *(TextChoices)*

Status values for problem list entries.

| Value (DB) | Display Label |
|-----------|---------------|
| `"active"` | Active |
| `"resolved"` | Resolved |
| `"chronic"` | Chronic |
| `"inactive"` | Inactive |

Used by: `problemlist` app.

---

### SEVERITY_CHOICES *(TextChoices)*

Severity classification for problems.

| Value (DB) | Display Label |
|-----------|---------------|
| `"mild"` | Mild |
| `"moderate"` | Moderate |
| `"severe"` | Severe |
| `"life_threatening"` | Life Threatening |

Used by: `problemlist` app.

---

### LOGIN_STATUS_CHOICES *(tuple list)*

Login event types for `UserActivityLog`.

| Value | Display |
|-------|---------|
| `'success'` | Login Success |
| `'failed'` | Login Failed |
| `'logout'` | Logout |

---

### MODE_OF_DELIVERY *(tuple)*

Obstetric delivery modes for patient birth records.

| Value | Display |
|-------|---------|
| `"Normal vaginal delivery (NVD)"` | Normal vaginal delivery (NVD) |
| `"Assisted vaginal delivery (AVD)"` | Assisted vaginal delivery (AVD) |
| `"Forcep delivery"` | Forcep delivery |
| `"Vacume delivery"` | Vacume delivery |
| `"Emergency LSCS"` | Emergency LSCS |
| `"Elective LSCS"` | Elective LSCS |
| `"VBAC"` | Vaginal birth after CS (VBAC) |
| `"Home delivery"` | Home delivery |
| `"Other"` | Other |

---

### GENDER *(tuple)*

Patient gender options.

| Value | Display |
|-------|---------|
| `"Male"` | Male |
| `"Female"` | Female |
| `"Undefine"` | Undefine |

---

### BOOKMARK_TYPE *(tuple)*

Record types that can be bookmarked.

| Value | Display |
|-------|---------|
| `"Patient"` | Patient |
| `"Video"` | Video |
| `"GMA"` | GMA |
| `"HINE"` | HINE |
| `"Attachment"` | Attachment |
| `"DA"` | DA |
| `"CDICR"` | CDICR |
| `"GPA"` | GPA |

---

### ATTACHMENT_TYPE *(tuple — legacy)*

Legacy attachment type choices. Superseded by `ATTACHMENT_TYPE_CHOICES` for new models.

| Value | Display |
|-------|---------|
| `"Photo"` | Photo |
| `"PDF"` | PDF |
| `"Video"` | Video |

---

### DX_CONCLUTION *(tuple)*

Diagnosis conclusion options.

| Value | Display |
|-------|---------|
| `"NORMAL"` | NORMAL |
| `"ABNORMAL"` | ABNORMAL |

---

### POG_WKS *(tuple)*

Period of gestation weeks choices. Integer values `20` through `42`.

---

### POG_DAYS *(tuple)*

Period of gestation days choices. Integer values `0` through `6`.

---

### APGAR *(tuple)*

APGAR score choices. Integer values `0` through `10`.

---

### VIDEO_FORMATS *(list)*

Supported video file formats.

| Value | Display |
|-------|---------|
| `"mp4"` | MP4 |
| `"mov"` | MOV/QuickTime |
| `"avi"` | AVI |
| `"mkv"` | MKV |
| `"webm"` | WebM |

---

### QUALITY_CHOICES *(list)*

Video quality/resolution tiers for compression.

| Value | Display |
|-------|---------|
| `"original"` | Original Quality |
| `"high"` | High Quality (1080p) |
| `"medium"` | Medium Quality (720p) |
| `"low"` | Low Quality (480p) |
| `"mobile"` | Mobile Quality (360p) |

---

### PROCESSING_STATUS *(list)*

Video processing pipeline states.

| Value | Display |
|-------|---------|
| `"pending"` | Pending Upload |
| `"uploading"` | Uploading |
| `"processing"` | Processing |
| `"completed"` | Completed |
| `"failed"` | Failed |

---

### ACCESS_LEVEL_CHOICES *(list)*

Video access level options.

| Value | Display |
|-------|---------|
| `"restricted"` | Restricted |
| `"team"` | Team Access |
| `"department"` | Department Access |
| `"public"` | Public Access |

---

### ATTACHMENT_TYPE_CHOICES *(list)*

Current attachment type choices (replaces legacy `ATTACHMENT_TYPE`).

| Value | Display |
|-------|---------|
| `"image"` | Image |
| `"pdf"` | PDF Document |
| `"video"` | Video File |
| `"document"` | Document |
| `"other"` | Other |

---

### ATTACHMENT_ACCESS_LEVEL_CHOICES *(list)*

Attachment access level options.

| Value | Display |
|-------|---------|
| `"restricted"` | Restricted Access |
| `"team"` | Team Access |
| `"department"` | Department Access |
| `"general"` | General Access |

---

### SCAN_RESULT_CHOICES *(list)*

File virus/malware scan result states.

| Value | Display |
|-------|---------|
| `"pending"` | Scan Pending |
| `"clean"` | Clean |
| `"infected"` | Infected |
| `"error"` | Scan Error |

---

### SUBSCRIPTION_TYPE_CHOICES *(list — Phase 2)*

Institution subscription tier.

| Value | Display |
|-------|---------|
| `'free'` | Free |
| `'commercial'` | Commercial |

---

### FILE_SIZE_LIMITS *(dict constant)*

In-module file size limit constants (reference only — the authoritative values are in `settings.FILE_UPLOAD_LIMITS`).

| Key | Value |
|-----|-------|
| `"MAX_FILE_SIZE"` | 100 MB |
| `"MAX_IMAGE_SIZE"` | 10 MB |
| `"MAX_VIDEO_SIZE"` | 2 GB |

---

### ALLOWED_EXTENSIONS *(dict constant)*

In-module allowed extension lists (reference only — the authoritative values are in `settings.ALLOWED_FILE_EXTENSIONS`).

| Key | Extensions |
|-----|-----------|
| `"image"` | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp` |
| `"pdf"` | `.pdf` |
| `"video"` | `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm` |
| `"document"` | `.doc`, `.docx`, `.txt`, `.rtf`, `.odt` |

---

## `validators.py` — Validators & File Utilities

### `sanitize_text_input(value)`

Sanitizes free-text input to prevent XSS while preserving medical notation (e.g., `< 5 mg/dl`, `> 38°C`).

- **Parameters:** `value` (str) — raw input text
- **Returns:** `str` — sanitized text safe for storage and display
- **What it does:**
  1. Removes `<script>` and `<style>` tags and their content
  2. Strips JavaScript event handlers (`onclick=`, `onload=`, etc.)
  3. Removes dangerous protocols (`javascript:`, `data:`, `vbscript:`)
  4. Strips HTML tags whose names start with a letter (preserves `< 5` medical notation)
  5. Unescapes HTML entities to prevent double-encoding
  6. Normalizes whitespace (multiple spaces/tabs → single space; multiple newlines → double newline)
  7. Strips leading/trailing whitespace

```python
from ndas.custom_codes.validators import sanitize_text_input

clean = sanitize_text_input(request.POST.get('notes', ''))
```

---

### `sanitize_filename(filename, max_length=100)`

Sanitizes a filename to prevent path traversal and filesystem issues.

- **Parameters:**
  - `filename` (str) — original filename (may include path)
  - `max_length` (int) — maximum total filename length, default 100
- **Returns:** `str` — a safe filename
- **What it does:**
  1. Extracts `os.path.basename` (strips directory components)
  2. Removes `..` sequences and null bytes
  3. Replaces invalid filesystem characters with underscores
  4. Strips leading/trailing spaces and dots
  5. Prevents Unix hidden files (prepends `file_` to names starting with `.`)
  6. Truncates to `max_length` while preserving extension
  7. Falls back to `"unnamed_file"` if result is empty

```python
from ndas.custom_codes.validators import sanitize_filename

safe = sanitize_filename(uploaded_file.name)
```

---

### `image_extension_validation(value)`

Django field validator for image uploads. Accepts `.jpg`, `.jpeg`, `.png` only.

- **Parameters:** `value` — Django `UploadedFile`
- **Raises:** `ValidationError` if extension is not in the allowed list

```python
from ndas.custom_codes.validators import image_extension_validation

profile_pic = models.ImageField(validators=[image_extension_validation])
```

---

### `validate_video_file_upload(var_uploaded_file)`

Composite validation for video upload forms (not a Django model validator; returns a tuple).

- **Parameters:** `var_uploaded_file` — Django `UploadedFile`
- **Returns:** `(bool, str)` — `(True, "File is valid")` or `(False, error_message)`
- **Checks in order:**
  1. File extension via `validateVideoType()`
  2. File size via `validateVideoSize()` (limit from `settings.FILE_UPLOAD_LIMITS`)
  3. Minimum size ≥ 1 KB (guards against empty/corrupted files)

```python
from ndas.custom_codes.validators import validate_video_file_upload

is_valid, msg = validate_video_file_upload(request.FILES['video'])
if not is_valid:
    messages.error(request, msg)
```

---

### `getVideoMaxSizeMB()`

Returns the maximum video file size in **megabytes** from `settings.FILE_UPLOAD_LIMITS['VIDEO_MAX_SIZE']`. Defaults to 2 GB (2048 MB) if the setting is absent.

- **Returns:** `int` — max video size in MB

---

### `validateVideoSize(var_uploaded_file)`

Checks whether a video file's size is within the configured limit.

- **Parameters:** `var_uploaded_file` — Django `UploadedFile`
- **Returns:** `bool`

---

### `validateVideoType(var_uploaded_file)`

Checks whether a video file's extension is in the allowed list (`.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`).

- **Parameters:** `var_uploaded_file` — Django `UploadedFile`
- **Returns:** `bool`

---

### `getFileType(var_uploaded_file)`

Detects a file's broad category from its extension.

- **Parameters:** `var_uploaded_file` — Django `UploadedFile` or any object with a `.name`
- **Returns:** `str` — one of `"Image"`, `"Video"`, `"PDF"`, `"Document"`, `"Spreadsheet"`, `"Unknown"`

---

### `validateVideoMetadata(var_uploaded_file)`

Placeholder for advanced ffmpeg-based video metadata validation. Currently always returns `(True, "Metadata validation skipped (ffmpeg not available)")`.

- **Returns:** `(bool, str)`

---

### `estimateCompressionSize(original_size_bytes, target_quality="medium")`

Estimates the compressed file size given a target quality setting.

- **Parameters:**
  - `original_size_bytes` (int) — original file size in bytes
  - `target_quality` (str) — one of `"original"`, `"high"`, `"medium"`, `"low"`, `"mobile"`
- **Returns:** `int` — estimated compressed size in bytes
- **Compression ratios:** original=1.0, high=0.7, medium=0.5, low=0.3, mobile=0.2

---

### `BHT_validation(request, value)` *(legacy)*

Validates a BHT number is non-empty and numeric. Adds Django messages on failure.

- **Returns:** `bool`

---

### `PHN_validation(request, value)` *(legacy)*

Validates a PHN number is non-empty and numeric. Adds Django messages on failure.

- **Returns:** `bool`

---

### `NNC_validation(request, value)` *(legacy)*

Validates a NNC number is non-empty and numeric. Adds Django messages on failure.

- **Returns:** `bool`

---

### `Name_baby_validation(request, value)` *(legacy)*

Validates baby name is non-empty. Adds a Django message on failure.

- **Returns:** `True` or `None`

---

### `Name_mother_validation(request, value)` *(legacy)*

Validates mother's name is non-empty. Adds a Django message on failure.

- **Returns:** `bool`

---

### `validateAttachmentSize(var_uploaded_file)`

Validates attachment size against type-specific limits from `settings.FILE_UPLOAD_LIMITS`.

- **Parameters:** `var_uploaded_file` — Django `UploadedFile`
- **Returns:** `bool`
- **Limits applied:** images → `IMAGE_MAX_SIZE`; videos → `VIDEO_MAX_SIZE`; documents/PDFs → `DOCUMENT_MAX_SIZE`; default → `ATTACHMENT_MAX_SIZE` (100 MB)

---

### `validateAttachmentType(var_uploaded_file)`

Validates attachment extension against `settings.ALLOWED_FILE_EXTENSIONS`. Falls back to a hardcoded list if the setting is absent.

- **Parameters:** `var_uploaded_file` — Django `UploadedFile`
- **Returns:** `bool`

---

### `validate_birth_weight(value)`

Django model field validator. Accepts birth weight between 300 g and 8000 g.

- **Parameters:** `value` (int/float) — birth weight in grams
- **Raises:** `ValidationError` if outside `[300, 8000]`

```python
from ndas.custom_codes.validators import validate_birth_weight

birth_weight = models.IntegerField(validators=[validate_birth_weight])
```

---

### `validate_apgar_score(value)`

Django model field validator. Accepts APGAR scores 0–10.

- **Parameters:** `value` (int)
- **Raises:** `ValidationError` if outside `[0, 10]`

---

### `validate_phone_number(value)`

Django model field validator using `RegexValidator`. Accepts `+999999999` format, 9–15 digits.

- **Parameters:** `value` (str)
- **Raises:** `ValidationError` if format does not match

---

### `validate_video_file(value)`

Django model field validator for `FileField`/`ImageField` holding video uploads.

- **Parameters:** `value` — Django file object
- **Raises:** `ValidationError` for:
  - Invalid extension (checked against `settings.ALLOWED_FILE_EXTENSIONS['VIDEO']`)
  - File too large (checked against `settings.FILE_UPLOAD_LIMITS['VIDEO_MAX_SIZE']`)
  - File too small (< 1 KB — empty/corrupted)

---

### `validate_recording_date(value)`

Django model field validator for video recording dates.

- **Parameters:** `value` — `datetime` object
- **Raises:** `ValidationError` if:
  - Date is in the future
  - Date is more than 10 years in the past

---

### `validate_pog_weeks(value)`

Django model field validator for gestational age weeks.

- **Parameters:** `value` (int)
- **Raises:** `ValidationError` if outside `[20, 44]`

---

### `validate_pog_days(value)`

Django model field validator for gestational age days.

- **Parameters:** `value` (int)
- **Raises:** `ValidationError` if outside `[0, 6]`

---

### `validate_attachment_file(value)`

Comprehensive Django model field validator for attachment `FileField`. Skips validation for existing `FieldFile` objects that are not being replaced (avoids `FileNotFoundError` on read-only access).

- **Parameters:** `value` — Django file object
- **Raises:** `ValidationError` for:
  - Invalid extension (checked against all `settings.ALLOWED_FILE_EXTENSIONS` groups)
  - File exceeds `VIDEO_MAX_SIZE` (largest allowed limit)
  - Empty file (< 1 byte)
  - Executable MIME types (`application/x-executable`, `application/x-msdownload`, `application/x-dosexec`)

---

### `get_institution_video_path(instance, filename)`

Django `upload_to` callable for Video model. Returns institution-partitioned path.

- **Returns:** `str` — `"{institution_slug}/videos/{sanitized_filename}"`, falls back to `"pending/videos/..."` if institution unavailable
- **Used on:** `Video.file` (Phase 2 Story 1.5)

---

### `get_institution_attachment_path(instance, filename)`

Django `upload_to` callable for Attachment model. Returns institution-partitioned path.

- **Returns:** `str` — `"{institution_slug}/attachments/{sanitized_filename}"`, falls back to `"pending/attachments/..."`
- **Used on:** `Attachment.file` (Phase 2 Story 1.5)

---

### `get_institution_logo_path(instance, filename)`

Django `upload_to` callable for Institution logo. Returns institution-partitioned path.

- **Returns:** `str` — `"{institution_slug}/logo/{sanitized_filename}"`, falls back to `"pending/logo/..."`
- **Used on:** `Institution.logo` (Phase 2 Story 3.3 — FR58)

---

## `sanitization.py` — HTML Sanitization

Uses the `bleach` library. Defines module-level constants for allowed HTML elements.

### Module Constants

**`ALLOWED_TAGS`** — Tags permitted in rich-text fields:
`p`, `br`, `strong`, `em`, `u`, `h1`–`h6`, `ul`, `ol`, `li`, `blockquote`, `pre`, `code`, `a`, `span`, `div`, `table`, `thead`, `tbody`, `tr`, `th`, `td`, `img`

**`ALLOWED_ATTRIBUTES`** — Attributes permitted per tag:
- `a`: `href`, `title`, `target`, `rel`
- `img`: `src`, `alt`, `title`, `width`, `height`
- `span`, `div`, `p`: `class`
- `table`: `class`, `border`, `cellpadding`, `cellspacing`
- `td`, `th`: `colspan`, `rowspan`

**`ALLOWED_PROTOCOLS`**: `http`, `https`, `mailto`, `tel`

---

### `sanitize_html(html_content, strip=False)`

Sanitizes HTML content using bleach. Strips or escapes disallowed tags. Also linkifies plain URLs and email addresses using `bleach.linkify`.

- **Parameters:**
  - `html_content` (str) — raw HTML to sanitize
  - `strip` (bool) — if `True`, strip disallowed tags entirely; if `False` (default), escape them as entities
- **Returns:** `str` — sanitized HTML safe for rendering
- **Used for:** rich-text clinical notes, report body fields

```python
from ndas.custom_codes.sanitization import sanitize_html

safe_notes = sanitize_html(form.cleaned_data['notes'])
```

---

### `sanitize_plain_text(text, max_length=None)`

Strips all HTML tags and normalizes whitespace. For fields that must contain only plain text.

- **Parameters:**
  - `text` (str) — raw input
  - `max_length` (int, optional) — truncate to this length, appending `...`
- **Returns:** `str` — clean plain text with normalized whitespace

```python
from ndas.custom_codes.sanitization import sanitize_plain_text

clean_name = sanitize_plain_text(request.POST.get('baby_name', ''))
```

---

### `sanitize_filename(filename, max_length=255)` *(sanitization.py version)*

A second `sanitize_filename` implementation in `sanitization.py`. Keeps only alphanumeric characters, underscores, hyphens, and dots. More aggressive than the `validators.py` version.

- **Parameters:**
  - `filename` (str) — raw filename
  - `max_length` (int) — max total length, default 255
- **Returns:** `str` — safe filename

> Note: Both `validators.py` and `sanitization.py` define `sanitize_filename`. Import from `validators.py` for upload-path helpers; import from `sanitization.py` when stricter character filtering is required.

---

### `sanitize_sql_like_pattern(pattern)`

Escapes special SQL LIKE wildcard characters to prevent unexpected matches or SQL injection in LIKE queries.

- **Parameters:** `pattern` (str) — user-supplied search pattern
- **Returns:** `str` — pattern with `%`, `_`, and `\` escaped
- **Escapes:** `\` → `\\`, `%` → `\%`, `_` → `\_`

```python
from ndas.custom_codes.sanitization import sanitize_sql_like_pattern

safe_pattern = sanitize_sql_like_pattern(query)
qs = Patient.objects.filter(baby_name__icontains=safe_pattern)
```

---

### `sanitize_search_query(query, max_length=200)`

Sanitizes free-text search input. Removes HTML tags, strips injection-risk characters, normalizes whitespace, and enforces a length limit.

- **Parameters:**
  - `query` (str) — raw search query from user input
  - `max_length` (int) — maximum query length, default 200
- **Returns:** `str` — safe query string containing only `[a-zA-Z0-9_\s\-.,@()]`

```python
from ndas.custom_codes.sanitization import sanitize_search_query

q = sanitize_search_query(request.GET.get('q', ''))
```

---

## `custom_methods.py` — Utility Functions

### `institution_scope(request, field='patient__institution')`

Returns ORM filter kwargs for institution scoping. Returns `{}` in Phase 1 (where `request.institution` is `None`), enabling backward-compatible queryset filtering.

- **Parameters:**
  - `request` — Django `HttpRequest` (reads `request.institution`)
  - `field` (str) — ORM field path to filter on, default `'patient__institution'`
- **Returns:** `dict` — `{field: institution}` or `{}` if institution is None

```python
from ndas.custom_codes.custom_methods import institution_scope

qs = Video.objects.filter(**institution_scope(request))
```

---

### `get_gma_diagnosis_data(institution=None)`

Returns a dict mapping GMA diagnosis abbreviations to patient counts, scoped to institution.

- **Parameters:** `institution` — Institution instance or `None` for all
- **Returns:** `dict` — `{diagnosis_abr: patient_count}`
- **Imports:** `patients.models.GMAssessment`, `patients.models.Patient`

---

### `get_all_diagnosis_data(institution=None)`

Returns abnormal diagnosis counts across GMA, HINE, and DA assessments for the given institution.

- **Parameters:** `institution` — Institution instance or `None`
- **Returns:** `dict` — `{'GMA': int, 'HINE': int, 'DA': int}`
- **HINE threshold:** score < 73 is counted as abnormal

---

### `get_userStats(institution=None)`

Returns per-user contribution counts (patients, videos, assessments, attachments, bookmarks) for all users in the institution.

- **Parameters:** `institution` — Institution instance or `None`
- **Returns:** `dict` — `{username: {'Patient': int, 'Video': int, 'GMA': int, 'HINE': int, 'DA': int, 'CDIC': int, 'Attachment': int, 'Bookmark': int}}`

---

### `get_admissions_data_barchart(institution=None)`

Returns monthly patient admissions data for the last 5 months, formatted for a bar chart.

- **Parameters:** `institution` — Institution instance or `None`
- **Returns:** `dict` — `{'labels': ['Jan 2025', ...], 'data': [count, ...]}`

---

### `getCurrentDateTime()`

Returns the current local datetime using `django.utils.timezone.localtime(now())`.

- **Returns:** timezone-aware `datetime` in the current local timezone

---

### `get_ip_address(request)`

Extracts the real client IP address, respecting `X-Forwarded-For` headers.

- **Parameters:** `request` — Django `HttpRequest`
- **Returns:** `str` — IP address string

---

### `getFullDeviceDetails(request)`

Returns a dictionary of browser/device/OS details using `request.user_agent` (requires `django-user-agents` middleware).

- **Parameters:** `request` — Django `HttpRequest`
- **Returns:** `dict` with keys: `browser`, `os`, `device`, `ipaddress`, `is_mobile`, `is_tablet`, `is_touch_capable`, `is_pc`, `is_bot`

---

### `get_video_path_file_name(instance, filename)`

Django `upload_to` callable for Video file fields. Generates an organized, secure path.

- **Parameters:** `instance` — Video model instance; `filename` — original filename
- **Returns:** `str` — path of form `videos/{YYYY}/{MM}/{patient_name}/{patient_name}_{title}_original_{timestamp}{ext}`
- **Security:** sanitizes filename and extension before use

---

### `get_compressed_video_path(instance, filename)`

Django `upload_to` callable for compressed video files. Always outputs `.mp4`.

- **Returns:** `str` — `videos/{YYYY}/{MM}/{patient_name}/compressed/{patient_name}_{title}_compressed_{timestamp}.mp4`

---

### `get_video_thumbnail_path(instance, filename)`

Django `upload_to` callable for video thumbnail images. Always outputs `.jpg`.

- **Returns:** `str` — `videos/{YYYY}/{MM}/{patient_name}/thumbnails/{patient_name}_{title}_thumb_{timestamp}.jpg`

---

### `get_attachment_path_file_name(instance, filename)`

Django `upload_to` callable for attachment uploads. Sanitizes title and filename.

- **Parameters:** `instance` — Attachment model instance; `filename` — original filename
- **Returns:** `str` — `attachments/{safe_title}_{attachment_type}_{user_id}_{timestamp}{ext}`

---

### `getAttachmentType(var_attachment)`

Maps a file extension to an `ATTACHMENT_TYPE_CHOICES` value.

- **Parameters:** `var_attachment` — filename string or file object with `.name`
- **Returns:** `str` — one of `'image'`, `'pdf'`, `'video'`, `'document'`, `'other'`

---

### `getFileSizeInMb(file)`

Returns the file size rounded up to the nearest megabyte.

- **Parameters:** `file` — Django `UploadedFile` with `.size` attribute
- **Returns:** `int` — size in MB (ceiling)

---

### `checkRCState(variable)`

Checks for a `display` boolean key in a recommendation parameter dictionary.

- **Parameters:** `variable` (dict)
- **Returns:** `bool` if `variable['display']` is a `bool`; `None` otherwise

---

### `getCountZeroIfNone(var_value)`

Returns `0` if the QuerySet or value is `None`; otherwise calls `.count()` on it.

- **Parameters:** `var_value` — QuerySet or `None`
- **Returns:** `int`

```python
from ndas.custom_codes.custom_methods import getCountZeroIfNone

video_count = getCountZeroIfNone(patient.videos.filter(active=True))
```

---

### `escape_excel_formula(value)`

Neutralizes spreadsheet formula injection in a single cell value. openpyxl/Excel treats any string cell whose first character is `=`, `+`, `-`, `@`, tab, or carriage return as a live formula; prefixes a leading single-quote so it's stored as literal text instead. Non-string values pass through unchanged.

- **Parameters:** `value` — the raw cell value (any type)
- **Returns:** the value unchanged, or `"'" + value` if it's a string starting with a formula-trigger character

### `escape_excel_row(row)`

Applies `escape_excel_formula` to every cell in a data row. **Call this on every row of user-controlled free text before `ws.append(row)`** in any Excel export — this is mandatory, not optional, for any new export path.

```python
from ndas.custom_codes.custom_methods import escape_excel_row

ws.append(escape_excel_row([patient.baby_name, patient.mother_name, patient.bht]))
```

---

### `extract_video_metadata(video_file_path)`

Extracts video metadata (duration, resolution, codec, bitrate) using moviepy first, falling back to `ffprobe`.

- **Parameters:** `video_file_path` (str) — absolute filesystem path to the video file
- **Returns:** `dict` or `None`
  - On success: `{'duration_seconds': int, 'resolution': str, 'width': int, 'height': int, 'fps': float, 'codec': str, 'bitrate': str}`
  - On failure: `None`
- **Fallback chain:** moviepy → ffprobe subprocess → `None`

```python
from ndas.custom_codes.custom_methods import extract_video_metadata

meta = extract_video_metadata('/media/videos/patient_video.mp4')
if meta:
    print(meta['duration_seconds'])
```

---

### `simple_video_duration_estimate(video_file_path)`

Estimates video duration from file size alone, assuming 2 Mbps average bitrate. Use only when `extract_video_metadata` is unavailable.

- **Parameters:** `video_file_path` (str)
- **Returns:** `dict` or `None` — `{'duration_seconds': int, 'resolution': None, 'width': None, 'height': None, 'estimated': True}`

---

### `calculate_age_string(start_date, end_date, format_type="detailed")`

Calculates a human-readable age/duration string between two dates.

- **Parameters:**
  - `start_date` (date) — start date (e.g., date of birth)
  - `end_date` (date) — end date (e.g., recording date or today)
  - `format_type` (str) — `"detailed"` (default), `"medical"`, or `"simple"`
- **Returns:** `str` — formatted age string
- **Format behaviours:**
  - `"simple"` — largest unit only (e.g., `"2 years"`)
  - `"medical"` — years+months or months+days (e.g., `"1 year and 3 months"`)
  - `"detailed"` — full breakdown (e.g., `"2 months and 3 days"`)
- **Edge cases:** returns `"Unknown"` if either date is `None`; `"Invalid: End date before start date"` if `end_date < start_date`; `"Same day"` if delta is 0

```python
from ndas.custom_codes.custom_methods import calculate_age_string

age = calculate_age_string(patient.dob_tob.date(), video.recording_date, "medical")
```

---

### `getPatientList(pts_type, institution=None)`

Returns an optimized, filtered Patient queryset based on a `PtStatus` enum value.

- **Parameters:**
  - `pts_type` (PtStatus) — filter type from `PtStatus` enum
  - `institution` — Institution instance or `None`
- **Returns:** `QuerySet[Patient]` with `select_related` and `prefetch_related` applied, plus the following annotations on every returned instance:
  - `has_videos_ann` (bool)
  - `is_discharged_ann` (bool)
  - `is_bookmarked_ann` (bool)
  - `is_gma_abnormal_ann` (bool)
  - `is_hine_abnormal_ann` (bool)

| `pts_type` | Filter applied |
|-----------|----------------|
| `PtStatus.ALL` | All patients |
| `PtStatus.NEW` | No associated videos |
| `PtStatus.DISCHARGED` | Has a CDICRecord with `is_discharged=True` |
| `PtStatus.DIAGNOSED` | Any abnormal GMA, HINE score < 73, or abnormal DA |
| `PtStatus.DX_NORMAL` | Has videos but no abnormal assessments |
| `PtStatus.DX_GMA_ABNORMAL` | GMA diagnosis = ABNORMAL |
| `PtStatus.DX_GMA_NORMAL` | GMA diagnosis = NORMAL |
| `PtStatus.DX_DA_NORMAL` | DA `is_dx_normal=True` |
| `PtStatus.DX_DA_ABNORMAL` | DA `is_dx_normal=False` |
| `PtStatus.DX_HINE` | HINE score < 73 |

```python
from ndas.custom_codes.custom_methods import getPatientList
from ndas.custom_codes.ndas_enums import PtStatus

patients = getPatientList(PtStatus.DIAGNOSED, institution=request.institution)
```

---

## `ndas_enums.py` — Enumerations

### PtStatus

Python `Enum` (not Django TextChoices) for use as a type-safe constant when calling `getPatientList()`. Stores string values matching the filter logic in `custom_methods.py`.

| Member | Value | Description |
|--------|-------|-------------|
| `PtStatus.NEW` | `'NEW'` | Patients with no associated videos |
| `PtStatus.DISCHARGED` | `'DISCHARGED'` | Patients with a discharge record |
| `PtStatus.DX_NORMAL` | `'DX_NORMAL'` | Patients with normal diagnosis (have videos) |
| `PtStatus.DIAGNOSED` | `'DIAGNOSED'` | Patients with any abnormal assessment |
| `PtStatus.DX_GMA_NORMAL` | `'DX_GMA_NORMAL'` | Normal GMA |
| `PtStatus.DX_GMA_ABNORMAL` | `'DX_GMA_ABNORMAL'` | Abnormal GMA |
| `PtStatus.DX_DA_NORMAL` | `'DX_DA_NORMAL'` | Normal developmental assessment |
| `PtStatus.DX_DA_ABNORMAL` | `'DX_DA_ABNORMAL'` | Abnormal developmental assessment |
| `PtStatus.DX_HINE` | `'DX_HINE'` | HINE score < 73 |
| `PtStatus.ALL` | `'ALL'` | All patients regardless of status |

```python
from ndas.custom_codes.ndas_enums import PtStatus

# Use with getPatientList
patients = getPatientList(PtStatus.DX_HINE, institution=request.institution)

# Comparison
if filter_type == PtStatus.ALL:
    ...
```

---

## `delete_helpers.py` — Deletion Utilities

### Permission Rules Summary

| User Type | Can Delete |
|-----------|-----------|
| Unauthenticated | Nothing |
| Non-staff authenticated | Nothing |
| Staff — own records (`added_by == user`) | Yes |
| Staff — any `Bookmark` | Yes (bookmarks are always own) |
| Superuser | Any entity |
| Any user — Video used in assessments | No (blocked by business rule) |

---

### `has_delete_permission(user, entity)`

Checks if a user is authorized to delete a given entity.

- **Parameters:**
  - `user` — `CustomUser` instance
  - `entity` — any Django model instance
- **Returns:** `bool`
- **Business rules:**
  1. Unauthenticated → `False`
  2. Superuser → `True`
  3. Staff + `entity.added_by == user` → `True`
  4. Staff + entity is `Bookmark` → `True`
  5. All other cases → `False`

```python
from ndas.custom_codes.delete_helpers import has_delete_permission

if not has_delete_permission(request.user, video):
    raise PermissionDenied
```

---

### `validate_can_delete(entity)`

Checks entity-specific business rules that may block deletion regardless of user permissions.

- **Parameters:** `entity` — any Django model instance
- **Returns:** `dict` — `{'can_delete': bool, 'reason': str}`
- **Business rules enforced:**
  - `Video` used in one or more `GMAssessment` records → blocked with count in reason
  - All other entity types → allowed (cascades are noted via `get_entity_warning_items`)

```python
from ndas.custom_codes.delete_helpers import validate_can_delete

result = validate_can_delete(video)
if not result['can_delete']:
    messages.error(request, result['reason'])
    return redirect(...)
```

---

### `get_entity_display_name(entity)`

Returns a human-readable name for the entity, suitable for display in modals/logs.

- **Parameters:** `entity` — any Django model instance
- **Returns:** `str` — resolves fields in this priority: `baby_name` → `title` → `username` → `name` → `file_name` → `filename` → `str(entity)` → `"ID: {pk}"`

---

### `get_redirect_url(entity_type, patient_id=None)`

Returns the appropriate URL to redirect to after successful deletion.

- **Parameters:**
  - `entity_type` (str) — `entity.__class__.__name__`
  - `patient_id` (int, optional) — required for `Problem` entities
- **Returns:** `str` — URL path

| Entity Type | Redirect URL |
|-------------|-------------|
| `Patient` | `/manager/patient/` |
| `Video` | `/video/manager/` |
| `GMAssessment`, `HINEAssessment`, `CDICRecord`, `DevelopmentalAssessment`, `GPARecord` | `/manager/patient/` |
| `Attachment`, `Bookmark` | `/manager/patient/` |
| `CustomUser`, `User` | `/users/admin/users/` |
| `Problem` (with patient_id) | `/problems/manager/{patient_id}/` |
| Unknown | `/` |

---

### `get_entity_warning_items(entity)`

Returns a list of warning strings for the deletion confirmation modal.

- **Parameters:** `entity` — any Django model instance
- **Returns:** `list[str]` — contextual warnings

| Entity Type | Warnings Generated |
|-------------|-------------------|
| `Patient` | Permanent deletion notice; counts of videos, assessments, attachments, problems |
| `Video` | File permanently deleted; cannot be undone |
| `*Assessment`, `CDICRecord`, `GPARecord` | Assessment data lost; patient/video unaffected |
| `Attachment` | File permanently deleted; patient unaffected |
| `Bookmark` | Bookmark removed from list |
| `Problem` | Problem and action log counts deleted; patient unaffected |
| `CustomUser`, `User` | Account deactivated (soft delete); audit trail preserved |
| Others | Generic "record will be permanently deleted" |

---

### `get_entity_detail_items(entity)`

Returns a key-value dict of entity details to display in the deletion confirmation modal.

- **Parameters:** `entity` — any Django model instance
- **Returns:** `dict[str, str]`

| Entity Type | Keys Returned |
|-------------|--------------|
| `Patient` | Name, BHT Number, Gender |
| `Video` | File Name, Patient |
| `*Assessment`, `CDICRecord`, `GPARecord` | Patient, Date |
| `Attachment` | Title, File |
| `Bookmark` | Patient |
| `Problem` | Problem, Patient, Status, Date Identified |
| `CustomUser`, `User` | Username, Email, Full Name |

---

## `security_middleware.py` — Security Middleware

### AdditionalSecurityHeadersMiddleware

Adds supplementary HTTP security headers that are not covered by Django's built-in `SecurityMiddleware`. Applied to every response via `process_response`.

**Headers added (if not already present):**

| Header | Value | Purpose |
|--------|-------|---------|
| `Referrer-Policy` | `strict-origin-when-cross-origin` (or from `settings.SECURE_REFERRER_POLICY`) | Controls referrer info sent to cross-origin requests |
| `Cross-Origin-Opener-Policy` | `same-origin` (or from `settings.SECURE_CROSS_ORIGIN_OPENER_POLICY`) | Prevents `window.opener` access from cross-origin pages |
| `X-Permitted-Cross-Domain-Policies` | `none` | Blocks Flash and PDF cross-domain policy files |
| `Permissions-Policy` | Disables geolocation, microphone, camera, payment, usb, magnetometer, gyroscope, accelerometer | Restricts browser feature access |

**Position in middleware stack:** #4 (after `CSPMiddleware`, before `SessionMiddleware`)

```python
# settings.py MIDDLEWARE
MIDDLEWARE = [
    ...
    'ndas.custom_codes.security_middleware.AdditionalSecurityHeadersMiddleware',
    ...
]
```

---

### SecurityHeadersValidationMiddleware

Validates that required security headers are present on HTML responses. **Production only** — skips all checks when `DEBUG=True`.

**Validated headers (always required):**
- `X-Content-Type-Options`
- `X-Frame-Options`
- `Content-Security-Policy`

**Validated headers (when `SECURE_SSL_REDIRECT=True`):**
- `Strict-Transport-Security`

**Skips validation for:** `/static/`, `/media/`, `/admin/` paths; non-`text/html` responses.

**On missing headers:** logs a `WARNING` with the path, missing header names, method, and username. Does not modify or block the response.

**Position in middleware stack:** #14 (last, production only)

---

## `error_handlers.py` — Error Handling Decorators

### `@handle_view_errors(redirect_url=None, error_message=None, render_template=None)`

Decorator factory that wraps a view function with comprehensive exception handling. Catches all common Django exceptions, sets user-facing messages, and redirects or re-renders appropriately.

- **Parameters:**
  - `redirect_url` (str, optional) — URL name (for `reverse`/`redirect`) to go to on error. If `None`, may raise `Http404` or redirect to `'home'`.
  - `error_message` (str, optional) — override the default user-facing error message
  - `render_template` (str, optional) — template path to render on `ValidationError` or `IntegrityError` (instead of redirecting to home)

**Exceptions caught and their behaviour:**

| Exception | Default Message | Action |
|-----------|----------------|--------|
| `ObjectDoesNotExist` | "The requested item was not found." | `messages.error` + redirect or `raise Http404` |
| `ValidationError` | "Please correct the errors in the form." | Iterates field errors into messages + redirect/render/home |
| `IntegrityError` | "Unable to save. This may be a duplicate entry or violates database constraints." | `messages.error` + redirect/render/home |
| `PermissionDenied` | "You don't have permission to perform this action." | `messages.error` + redirect to `'home'` |
| `Exception` (generic) | "An unexpected error occurred. Please try again or contact support." | `logger.exception` (full traceback) + redirect/home |

All exceptions are logged with the view function name, username, and request path.

```python
from ndas.custom_codes.error_handlers import handle_view_errors

@login_required(login_url='user-login')
@handle_view_errors(redirect_url='patient-manager', error_message='Error loading patient')
def patient_edit(request, pk):
    patient = get_object_or_404(Patient, id=pk)
    # ... view logic
```

---

### `@log_and_suppress(logger_name=None, default_return=None)`

Decorator factory for non-critical helper functions. Catches all exceptions, logs them with `logger.exception`, and returns a safe default value instead of propagating.

- **Parameters:**
  - `logger_name` (str, optional) — logger name to use. Defaults to `ndas.custom_codes.error_handlers`.
  - `default_return` — value to return on exception. Defaults to `None`.
- **Returns:** the function's normal return value, or `default_return` on any exception

```python
from ndas.custom_codes.error_handlers import log_and_suppress

@log_and_suppress(default_return=0)
def get_video_count(patient):
    return patient.videos.filter(active=True).count()

# If this raises, it returns 0 without breaking the calling view
count = get_video_count(patient)
```

---

## Quick Import Reference

```python
# Base models (mandatory for all NDAS models)
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

# Choices — TextChoices classes
from ndas.custom_codes.choice import (
    Position,
    ConfigValueTypes,
    UserType,
    SubscriptionStatus,
    ReferralStatus,
    NotificationType,
    PROBLEM_STATUS,
    SEVERITY_CHOICES,
)

# Choices — tuple/list constants
from ndas.custom_codes.choice import (
    POSSITION,                      # legacy alias for Position.choices
    LOGIN_STATUS_CHOICES,
    MODE_OF_DELIVERY,
    GENDER,
    BOOKMARK_TYPE,
    ATTACHMENT_TYPE,                 # legacy
    DX_CONCLUTION,
    POG_WKS,
    POG_DAYS,
    APGAR,
    VIDEO_FORMATS,
    QUALITY_CHOICES,
    PROCESSING_STATUS,
    ACCESS_LEVEL_CHOICES,
    ATTACHMENT_TYPE_CHOICES,
    ATTACHMENT_ACCESS_LEVEL_CHOICES,
    SCAN_RESULT_CHOICES,
    SUBSCRIPTION_TYPE_CHOICES,
    SUBSCRIPTION_STATUS_CHOICES,
    FILE_SIZE_LIMITS,
    ALLOWED_EXTENSIONS,
)

# Validators — text and field validators
from ndas.custom_codes.validators import (
    sanitize_text_input,
    sanitize_filename,
    validate_birth_weight,
    validate_apgar_score,
    validate_phone_number,
    validate_video_file,
    validate_recording_date,
    validate_pog_weeks,
    validate_pog_days,
    validate_attachment_file,
    image_extension_validation,
)

# Validators — file upload helpers
from ndas.custom_codes.validators import (
    validate_video_file_upload,
    validateVideoType,
    validateVideoSize,
    getVideoMaxSizeMB,
    validateAttachmentType,
    validateAttachmentSize,
    getFileType,
    estimateCompressionSize,
)

# Validators — institution-aware upload_to callables (Phase 2)
from ndas.custom_codes.validators import (
    get_institution_video_path,
    get_institution_attachment_path,
    get_institution_logo_path,
)

# Validators — legacy form-level validators
from ndas.custom_codes.validators import (
    BHT_validation,
    PHN_validation,
    NNC_validation,
    Name_baby_validation,
    Name_mother_validation,
)

# Sanitization (bleach-based)
from ndas.custom_codes.sanitization import (
    sanitize_html,
    sanitize_plain_text,
    sanitize_filename,           # stricter version than validators.py
    sanitize_sql_like_pattern,
    sanitize_search_query,
)

# Utility functions
from ndas.custom_codes.custom_methods import (
    getCountZeroIfNone,
    calculate_age_string,
    extract_video_metadata,
    simple_video_duration_estimate,
    getPatientList,
    institution_scope,
    get_gma_diagnosis_data,
    get_all_diagnosis_data,
    get_userStats,
    get_admissions_data_barchart,
    getCurrentDateTime,
    get_ip_address,
    getFullDeviceDetails,
    getAttachmentType,
    getFileSizeInMb,
    checkRCState,
    get_video_path_file_name,
    get_compressed_video_path,
    get_video_thumbnail_path,
    get_attachment_path_file_name,
)

# Enums
from ndas.custom_codes.ndas_enums import PtStatus

# Delete helpers
from ndas.custom_codes.delete_helpers import (
    has_delete_permission,
    validate_can_delete,
    get_entity_warning_items,
    get_entity_detail_items,
    get_entity_display_name,
    get_redirect_url,
)

# Error handlers
from ndas.custom_codes.error_handlers import handle_view_errors, log_and_suppress

# Security middleware (referenced in settings.py, not imported in views)
# ndas.custom_codes.security_middleware.AdditionalSecurityHeadersMiddleware
# ndas.custom_codes.security_middleware.SecurityHeadersValidationMiddleware
```
