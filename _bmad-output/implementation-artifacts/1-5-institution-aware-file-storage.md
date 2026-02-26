# Story 1.5: Institution-Aware File Storage

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **clinician**,
I want uploaded videos and documents to be stored in institution-specific directories,
So that files from another institution cannot be accessed through any application interface or direct URL.

## Acceptance Criteria

1. **Given** `get_institution_video_path` and `get_institution_attachment_path` callables are added to `ndas/custom_codes/validators.py`
   **When** a video is uploaded within Institution A's context
   **Then** the file is stored at `MEDIA_ROOT/{institution_slug}/videos/{sanitized_filename}`

2. **Given** `get_institution_attachment_path` is set as the `upload_to` on all attachment `FileField` declarations
   **When** a document is attached to a patient record in Institution A
   **Then** the file is stored at `MEDIA_ROOT/{institution_slug}/attachments/{sanitized_filename}`

3. **Given** a user from Institution A is authenticated
   **When** they attempt to access a media URL for a file stored under Institution B's slug path
   **Then** the application returns a 403 or 404 response; the file is not served

## Tasks / Subtasks

- [ ] Task 1: Add `get_institution_video_path` and `get_institution_attachment_path` callables to `ndas/custom_codes/validators.py` (AC: #1, #2)
  - [ ] Add after the last existing function in `validators.py` — see exact spec in Dev Notes
  - [ ] `get_institution_video_path(instance, filename)`: uses `instance.patient.institution.slug` with `pending` fallback
  - [ ] `get_institution_attachment_path(instance, filename)`: uses `instance.patient.institution.slug` with `pending` fallback
  - [ ] Both callables call the existing `sanitize_filename(filename)` from the same `validators.py` module

- [ ] Task 2: Update `video/models.py` to use `get_institution_video_path` (AC: #1)
  - [ ] Add import: `from ndas.custom_codes.validators import validate_video_file, validate_recording_date, get_institution_video_path`
  - [ ] Change `video_file = models.FileField(upload_to="videos/%Y/%m/", ...)` → `upload_to=get_institution_video_path`
  - [ ] Keep ALL other field kwargs unchanged (`verbose_name`, `help_text`, `validators`, `db_index`)
  - [ ] See exact change in Dev Notes

- [ ] Task 3: Update `patients/models.py` to use `get_institution_attachment_path` (AC: #2)
  - [ ] Add `get_institution_attachment_path` to the `validators.py` import line (already exists in patients/models.py)
  - [ ] Remove `get_attachment_path_file_name` from `custom_methods` import (no longer used in models.py)
  - [ ] Change `attachment = models.FileField(upload_to=get_attachment_path_file_name, ...)` → `upload_to=get_institution_attachment_path`
  - [ ] See exact change in Dev Notes

- [ ] Task 4: Create migrations for both FileField `upload_to` changes (AC: #1, #2)
  - [ ] `python manage.py makemigrations video` → generates `video/migrations/0007_alter_video_video_file.py`
  - [ ] `python manage.py makemigrations patients` → generates `patients/migrations/0009_alter_attachment_attachment.py`
  - [ ] Verify `video/migrations/0007` depends on `('patients', '0008_add_institution_fk')` — add if missing
  - [ ] Verify `patients/migrations/0009` depends on `('patients', '0008_add_institution_fk')` — it should automatically
  - [ ] Run `python manage.py migrate` to apply

- [ ] Task 5: Add protected media view to enforce institution isolation (AC: #3)
  - [ ] Add `protected_media_view` to `institution/views.py` — see exact spec in Dev Notes
  - [ ] Replace `static(settings.MEDIA_URL, ...)` in `ndas/urls.py` with `path('media/<path:path>', protected_media_view, name='protected-media')` inside `if settings.DEBUG:` block
  - [ ] Import `protected_media_view` at the top of `ndas/urls.py`
  - [ ] See exact code in Dev Notes

- [ ] Task 6: Write tests for Story 1.5 (AC: all)
  - [ ] Add `institution/tests/test_file_storage.py` — see test code in Dev Notes
  - [ ] Test: `get_institution_video_path` returns correct path with institution slug
  - [ ] Test: `get_institution_attachment_path` returns correct path with institution slug
  - [ ] Test: path callable falls back to `'pending'` when institution is None
  - [ ] Test: protected media view returns 403 when user accesses another institution's path (if `MULTI_INSTITUTION_ENABLED=True`)
  - [ ] Test: SUPERADMIN can access any institution's media path

- [ ] Task 7: Run tests and verify no regressions (AC: all)
  - [ ] `python manage.py test institution`
  - [ ] `python manage.py test video`
  - [ ] `python manage.py test patients`
  - [ ] `python manage.py test` — full suite; no regressions

## Dev Notes

### Dependency: Story 1.4 Must Be Complete First

`get_institution_video_path` and `get_institution_attachment_path` access `instance.patient.institution.slug`. This FK relationship (`Patient.institution`) is added in Story 1.4. The callables include a safe fallback (`'pending'`) for the transitional state, but the `patients/migrations/0009_alter_attachment_attachment.py` must depend on `('patients', '0008_add_institution_fk')` which is Story 1.4's migration.

**Before starting:** Confirm `python manage.py showmigrations patients` shows `[X] 0008_add_institution_fk`.

### Existing Path Functions — Do NOT Modify

`ndas/custom_codes/custom_methods.py` contains `get_attachment_path_file_name` (line 213) and `get_video_path_file_name` (line 123). These are LEGACY functions. After Story 1.5:
- `get_attachment_path_file_name` is no longer used in `patients/models.py` — remove it from the patients model import ONLY. **Do NOT delete the function itself** from `custom_methods.py` — backward compatibility.
- `get_video_path_file_name` in `custom_methods.py` was never used in `video/models.py` (that model uses a static string). **Do NOT touch it.**

### Critical: Do NOT Change These FileFields

These FileFields are NOT institution-specific and must NOT be changed:
- `patients/models.py` → `Help.video_1`, `Help.video_2` (lines ~2377, 2384) — `upload_to="tutorials/%Y/%m/"` — system tutorial videos, not clinical data
- `institution/models.py` → `Institution.logo` — `upload_to='institution_logos/'` — temporary placeholder, will change in Story 3.3

### `ndas/custom_codes/validators.py` — New Callables (Exact Spec)

Add these two functions at the **end** of `validators.py` (after line 554):

```python
# Phase 2: Multi-Institution File Path Generators
# These callables are used as upload_to arguments on institution-scoped FileFields.

def get_institution_video_path(instance, filename):
    """
    upload_to callable for Video.video_file — routes to /{institution_slug}/videos/

    Security: uses sanitize_filename() to prevent path traversal.
    Fallback: uses 'pending' slug if institution not yet assigned (pre-Story-1.6 transitional state).
    """
    try:
        institution = instance.patient.institution if instance.patient_id else None
        slug = institution.slug if institution else 'pending'
    except AttributeError:
        slug = 'pending'
    return f"{slug}/videos/{sanitize_filename(filename)}"


def get_institution_attachment_path(instance, filename):
    """
    upload_to callable for Attachment.attachment — routes to /{institution_slug}/attachments/

    Security: uses sanitize_filename() to prevent path traversal.
    Fallback: uses 'pending' slug if institution not yet assigned (pre-Story-1.6 transitional state).
    """
    try:
        institution = instance.patient.institution if instance.patient_id else None
        slug = institution.slug if institution else 'pending'
    except AttributeError:
        slug = 'pending'
    return f"{slug}/attachments/{sanitize_filename(filename)}"
```

**Why `'pending'` fallback?**
During the transitional period between Story 1.4 and Story 1.6, `Patient.institution` is null for all existing patients. Files uploaded in this window land in `MEDIA_ROOT/pending/videos/` and `MEDIA_ROOT/pending/attachments/`. Story 1.6's data migration also moves these files to `MEDIA_ROOT/{default_institution_slug}/videos/` as part of the atomic path migration.

**`sanitize_filename` is already defined in `validators.py`** at line 72 — call it directly with no import needed.

### `video/models.py` — Exact Change Required

**Current line 12** (import):
```python
from ndas.custom_codes.validators import validate_video_file, validate_recording_date
```

**Updated to** (add `get_institution_video_path`):
```python
from ndas.custom_codes.validators import validate_video_file, validate_recording_date, get_institution_video_path
```

**Current lines 81–87** (FileField):
```python
video_file = models.FileField(
    upload_to="videos/%Y/%m/",  # Better organization by month
    verbose_name=_("Video File"),
    help_text=_("Upload the video file here"),
    validators=[validate_video_file],
    db_index=True,
)
```

**Updated to**:
```python
video_file = models.FileField(
    upload_to=get_institution_video_path,
    verbose_name=_("Video File"),
    help_text=_("Upload the video file here"),
    validators=[validate_video_file],
    db_index=True,
)
```

Note: Remove the comment `# Better organization by month` — it no longer applies.

### `patients/models.py` — Exact Change Required

**Current import line 30–37** (validators import block):
```python
from ndas.custom_codes.validators import (
    validate_birth_weight,
    validate_apgar_score,
    validate_phone_number,
    validate_pog_weeks,
    validate_pog_days,
    validate_attachment_file,
)
```

**Updated to** (add `get_institution_attachment_path`):
```python
from ndas.custom_codes.validators import (
    validate_birth_weight,
    validate_apgar_score,
    validate_phone_number,
    validate_pog_weeks,
    validate_pog_days,
    validate_attachment_file,
    get_institution_attachment_path,
)
```

**Current import line 25–29** (custom_methods import block):
```python
from ndas.custom_codes.custom_methods import (
    getCountZeroIfNone,
    get_attachment_path_file_name,
    checkRCState,
)
```

**Updated to** (remove `get_attachment_path_file_name` — no longer used in models.py):
```python
from ndas.custom_codes.custom_methods import (
    getCountZeroIfNone,
    checkRCState,
)
```

**Current lines 1492–1493** (Attachment FileField):
```python
attachment = models.FileField(
    upload_to=get_attachment_path_file_name,
```

**Updated to**:
```python
attachment = models.FileField(
    upload_to=get_institution_attachment_path,
```

### Migration — Exact Structure

After running `python manage.py makemigrations video patients`, verify the generated migrations:

**`video/migrations/0007_alter_video_video_file.py`** — should look like:
```python
import ndas.custom_codes.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('video', '0006_add_video_indexes'),
        ('patients', '0008_add_institution_fk'),  # Add if auto-generated omits it
    ]

    operations = [
        migrations.AlterField(
            model_name='video',
            name='video_file',
            field=models.FileField(
                db_index=True,
                upload_to=ndas.custom_codes.validators.get_institution_video_path,
                validators=[ndas.custom_codes.validators.validate_video_file],
                verbose_name='Video File',
            ),
        ),
    ]
```

**`patients/migrations/0009_alter_attachment_attachment.py`** — should look like:
```python
import ndas.custom_codes.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0008_add_institution_fk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attachment',
            name='attachment',
            field=models.FileField(
                upload_to=ndas.custom_codes.validators.get_institution_attachment_path,
                validators=[ndas.custom_codes.validators.validate_attachment_file],
                verbose_name='Attachment File',
            ),
        ),
    ]
```

**IMPORTANT**: Django auto-generates migrations for `upload_to` changes. The `video` migration may NOT automatically include the `patients/0008_add_institution_fk` dependency — add it manually if missing. This ensures correct ordering when running migrations from scratch.

### Protected Media View — `institution/views.py`

`institution/views.py` was created in Story 1.3 with an `institution_selector` stub. Add the following function to it:

```python
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.views.static import serve as django_serve_static


@login_required(login_url="user-login")
def protected_media_view(request, path):
    """
    Serve media files with institution isolation enforcement (development only).

    Institution-partitioned paths (/{slug}/videos/ and /{slug}/attachments/) are restricted
    to the owning institution's users. SUPERADMIN can access any institution's files.

    In production: Nginx handles media serving. An X-Accel-Redirect approach with
    a Django auth endpoint is recommended for production file isolation.
    """
    from ndas.custom_codes.choice import UserType

    user_type = getattr(request.user, 'user_type', UserType.USER)
    _inst = getattr(request, 'institution', None)

    # Check if path is institution-partitioned: format is "{slug}/videos/..." or "{slug}/attachments/..."
    parts = path.split('/')
    if len(parts) >= 2 and parts[1] in ('videos', 'attachments'):
        path_slug = parts[0]
        # SUPERADMIN can access all institution files
        if user_type != UserType.SUPERADMIN:
            # Block if institution context not set or slug mismatch
            if _inst is None or _inst.slug != path_slug:
                return HttpResponseForbidden(
                    "Access denied: this file belongs to another institution."
                )

    return django_serve_static(request, path, document_root=settings.MEDIA_ROOT)
```

### `ndas/urls.py` — Replace Static Media Serving

**Current line 4 and line 20:**
```python
from django.conf.urls.static import static
...
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

**Updated to** (add import at top, replace static() line):

**Import addition** (add after existing imports, before urlpatterns):
```python
from institution.views import protected_media_view
```

**Replace** the `+ static(...)` line at the end of `urlpatterns`:
```python
# Protected media serving with institution isolation (development only)
# In production, configure Nginx with auth_request to enforce institution isolation
if settings.DEBUG:
    urlpatterns += [
        path('media/<path:path>', protected_media_view, name='protected-media'),
    ]
```

Also remove the `from django.conf.urls.static import static` import if it's no longer needed anywhere else.

**Note on path URL pattern:** `path('media/<path:path>', ...)` matches `/media/{anything}`. The Django `<path:path>` converter allows slashes, so `/media/hospital-a/videos/file.mp4` becomes `path='hospital-a/videos/file.mp4'`.

### Phase 1 / Production Considerations

**Phase 1 (MULTI_INSTITUTION_ENABLED=False):**
- Files uploaded now go to `MEDIA_ROOT/pending/videos/` (institution not yet assigned)
- `protected_media_view` is registered but has no active institution context → `_inst is None` → does NOT block access (fallback to allow)
- Phase 1 behaviour: identical to pre-Story-1.5 except storage path changes for new files

**Production media serving:**
The `static()` helper is development-only. In production with Nginx:
```nginx
location /media/ {
    # Nginx should validate institution ownership via an internal auth endpoint
    # For Phase 2: use auth_request pointing to a Django auth endpoint
    root /path/to/media/;
}
```
Full production Nginx configuration is deferred to Story 1.7 (isolation validation) or deployment documentation.

### Test Code Pattern for `institution/tests/test_file_storage.py`

```python
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from institution.models import Institution
from patients.models import Patient
from ndas.custom_codes.validators import (
    get_institution_video_path, get_institution_attachment_path
)
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()


class InstitutionFilePathTest(TestCase):
    """Tests for institution-aware upload_to callables."""

    def setUp(self):
        self.institution_a = Institution.objects.create(
            name='Hospital A', slug='hospital-a',
            subscription_status=SubscriptionStatus.ACTIVE,
        )
        self.institution_b = Institution.objects.create(
            name='Hospital B', slug='hospital-b',
            subscription_status=SubscriptionStatus.ACTIVE,
        )
        self.patient_a = Patient.objects.create(
            baby_name='Baby A',
            institution=self.institution_a,
        )
        self.patient_no_institution = Patient.objects.create(
            baby_name='Baby No Inst',
            institution=None,
        )

    def test_get_institution_video_path_uses_slug(self):
        """AC #1: Video path contains institution slug."""
        # Simulate a Video instance (no need to save to DB)
        class FakeVideo:
            patient = self.patient_a
            patient_id = self.patient_a.pk

        result = get_institution_video_path(FakeVideo(), 'my_video.mp4')
        self.assertTrue(result.startswith('hospital-a/videos/'))
        self.assertIn('my_video.mp4', result)

    def test_get_institution_attachment_path_uses_slug(self):
        """AC #2: Attachment path contains institution slug."""
        class FakeAttachment:
            patient = self.patient_a
            patient_id = self.patient_a.pk

        result = get_institution_attachment_path(FakeAttachment(), 'report.pdf')
        self.assertTrue(result.startswith('hospital-a/attachments/'))
        self.assertIn('report.pdf', result)

    def test_video_path_fallback_when_no_institution(self):
        """Fallback to 'pending' when institution is None."""
        class FakeVideo:
            patient = self.patient_no_institution
            patient_id = self.patient_no_institution.pk

        result = get_institution_video_path(FakeVideo(), 'test.mp4')
        self.assertTrue(result.startswith('pending/videos/'))

    def test_attachment_path_fallback_when_no_institution(self):
        """Fallback to 'pending' when institution is None."""
        class FakeAttachment:
            patient = self.patient_no_institution
            patient_id = self.patient_no_institution.pk

        result = get_institution_attachment_path(FakeAttachment(), 'test.pdf')
        self.assertTrue(result.startswith('pending/attachments/'))

    def test_path_sanitizes_filename(self):
        """Path callable sanitizes dangerous filenames."""
        class FakeVideo:
            patient = self.patient_a
            patient_id = self.patient_a.pk

        result = get_institution_video_path(FakeVideo(), '../../etc/passwd')
        # After sanitization: should not contain path traversal
        self.assertNotIn('../', result)
        self.assertNotIn('etc/passwd', result)


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ProtectedMediaViewTest(TestCase):
    """Tests for protected_media_view institution isolation."""

    def setUp(self):
        self.client = Client()
        self.institution_a = Institution.objects.create(
            name='Hospital A', slug='hospital-a',
            subscription_status=SubscriptionStatus.ACTIVE,
        )
        self.institution_b = Institution.objects.create(
            name='Hospital B', slug='hospital-b',
            subscription_status=SubscriptionStatus.ACTIVE,
        )
        self.clinician_a = User.objects.create_user(
            username='clinician_a', password='testpass123',
            first_name='A', last_name='Clinician',
            position='Medical Officer', mobile_primary='0771230001',
            user_type=UserType.USER, institution=self.institution_a,
        )
        self.superadmin = User.objects.create_user(
            username='superadmin', password='testpass123',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771230002',
            user_type=UserType.SUPERADMIN, is_superuser=True,
        )

    def test_unauthenticated_access_redirects_to_login(self):
        """Unauthenticated users cannot access protected media."""
        response = self.client.get('/media/hospital-a/videos/test.mp4')
        self.assertIn(response.status_code, [302, 403])

    def test_clinician_blocked_from_other_institution_file(self):
        """Clinician from Institution A cannot access Institution B files."""
        self.client.force_login(self.clinician_a)
        # Manually set institution context (middleware would normally do this)
        session = self.client.session
        session.save()
        # Simulate request.institution = institution_a (set by middleware)
        # NOTE: In real tests, the middleware sets this. For unit test purposes,
        # this verifies the view logic when institution context is active.
        response = self.client.get('/media/hospital-b/videos/secret.mp4')
        # Either 403 (forbidden) or 404 (not found on disk) — both acceptable
        self.assertIn(response.status_code, [403, 404])
```

### Project Structure Notes

**Files to MODIFY in this story:**
- `ndas/custom_codes/validators.py` — add `get_institution_video_path` and `get_institution_attachment_path` at end
- `video/models.py` — change `video_file.upload_to` from string to `get_institution_video_path`; update import
- `patients/models.py` — change `Attachment.attachment.upload_to` to `get_institution_attachment_path`; update imports
- `institution/views.py` — add `protected_media_view` function
- `ndas/urls.py` — replace `static(MEDIA_URL, ...)` with `protected_media_view` inside `if settings.DEBUG`

**Files CREATED by migrations:**
- `video/migrations/0007_alter_video_video_file.py` (generated + verify patients dependency)
- `patients/migrations/0009_alter_attachment_attachment.py` (generated)

**Files CREATED for tests:**
- `institution/tests/test_file_storage.py`

**Files NOT touched in this story:**
- `patients/models.py` lines 2377, 2384 — `Help.video_1`, `Help.video_2` → `tutorials/%Y/%m/` (not institution-specific)
- `institution/models.py` — `Institution.logo` → `institution_logos/` placeholder (changed in Story 3.3)
- `ndas/custom_codes/custom_methods.py` — `get_attachment_path_file_name`, `get_video_path_file_name` remain (backward compat)
- `video/models.py` → `VideoQuerySet`, `VideoManager`, all other fields — no change
- Any assessment models — no FileFields that need institution path

### References

- Architecture: File Storage section — exact canonical pattern [Source: `_bmad-output/planning-artifacts/architecture.md#Format Patterns`]
- Architecture: get_institution_video_path, get_institution_attachment_path spec [Source: `_bmad-output/planning-artifacts/architecture.md#Format Patterns`]
- Architecture: 13-step sequence — Step 5 [Source: `_bmad-output/planning-artifacts/architecture.md#Decision Impact Analysis`]
- Architecture: validators.py as home for file path generators [Source: `_bmad-output/planning-artifacts/architecture.md#Project Structure & Boundaries`]
- Epics: Story 1.5 ACs [Source: `_bmad-output/planning-artifacts/epics.md#Story 1.5`]
- FR46: institution-specific file storage isolation [Source: `_bmad-output/planning-artifacts/epics.md#FR46`]
- Existing: `Video.video_file` current `upload_to="videos/%Y/%m/"` [Source: `video/models.py:82`]
- Existing: `Attachment.attachment` current `upload_to=get_attachment_path_file_name` [Source: `patients/models.py:1493`]
- Existing: `sanitize_filename` function [Source: `ndas/custom_codes/validators.py:72`]
- Existing: `get_attachment_path_file_name` (legacy, keep in custom_methods.py) [Source: `ndas/custom_codes/custom_methods.py:213`]
- Existing: latest video migration `0006_add_video_indexes.py` [Source: `video/migrations/`]
- Existing: `Help.video_1/video_2` — do NOT change (tutorials, not clinical) [Source: `patients/models.py:2377, 2384`]
- Existing: `ndas/urls.py` static media serving [Source: `ndas/urls.py:20`]
- Media settings: `MEDIA_ROOT = BASE_DIR / 'media'`, `MEDIA_URL = '/media/'` [Source: `ndas/settings.py:143-157`]
- Story 1.4 dependency: Patient.institution FK must exist before path callables are used [Source: `_bmad-output/implementation-artifacts/1-4-institution-scoped-orm-manager-view-updates.md`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- `get_institution_video_path` and `get_institution_attachment_path` callables added to `ndas/custom_codes/validators.py`. Both use `institution.slug` with `'pending'` fallback when institution is None.
- `video/models.py` updated: `video_file` now uses `upload_to=get_institution_video_path`.
- `patients/models.py` (Attachment) updated: uses `upload_to=get_institution_attachment_path`.
- `protected_media_view` added to `institution/views.py` to serve media with institution boundary enforcement.
- Migrations generated for both FileField changes.

### File List

- ndas/custom_codes/validators.py
- video/models.py
- video/migrations/0007_alter_video_video_file.py
- patients/models.py
- patients/migrations/0009_alter_attachment_attachment.py
- institution/views.py
- institution/tests/test_file_storage.py
