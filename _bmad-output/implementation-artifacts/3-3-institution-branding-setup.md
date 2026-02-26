# Story 3.3: Institution Branding Setup

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **institution admin**,
I want to upload my institution's logo and manage its display settings,
So that my institution is correctly identified throughout the system and in all exported documents.

## Acceptance Criteria

1. **Given** the institution admin navigates to institution settings
   **When** they upload a logo image (jpg/png/gif, max 10MB per existing NDAS validation rules)
   **Then** the logo is saved to `MEDIA_ROOT/{institution_slug}/logo/` and displayed on the institution's card on the superadmin selector screen

2. **Given** the logo has been uploaded successfully
   **When** any page within that institution's context renders
   **Then** the institution logo is displayed in the AdminLTE sidebar brand-logo slot via the `active_institution` context variable

3. **Given** the institution admin saves updated display settings
   **When** they submit the settings form
   **Then** changes are persisted and reflected immediately across all institution-scoped views without a server restart

## Tasks / Subtasks

- [x] Task 1: Add `get_institution_logo_path` callable to `ndas/custom_codes/validators.py` (AC: #1)
  - [x] Path formula: `{institution_slug}/logo/{sanitized_filename}` — stored under `MEDIA_ROOT/`
  - [x] Use `sanitize_filename()` from the same module
  - [x] See exact callable code in Dev Notes

- [x] Task 2: Update `Institution.logo` field `upload_to` in `institution/models.py` (AC: #1)
  - [x] Change `upload_to='institution_logos/'` to `upload_to=get_institution_logo_path`
  - [x] Run `python manage.py makemigrations institution` (no schema change, upload_to is not in DB, but makemigrations still detects the change to the callable)
  - [x] See exact field change in Dev Notes

- [x] Task 3: Create `InstitutionSettingsForm` in `institution/forms.py` (AC: #3)
  - [x] Fields: `logo` (ImageField, not required, max 10MB), `name` (CharField, display name only — slug is immutable)
  - [x] MIME type validation: use `image_extension_validation` from `validators.py`
  - [x] Max size: 10MB via `settings.FILE_UPLOAD_LIMITS['IMAGE_MAX_SIZE']`
  - [x] See exact form code in Dev Notes

- [x] Task 4: Add `institution_settings` view to `institution/views.py` (AC: #1, #2, #3)
  - [x] ADMIN only (or SUPERADMIN viewing institution context)
  - [x] GET: render form with current institution data
  - [x] POST: validate + save logo + name; redirect back to settings page with success message
  - [x] See exact view code in Dev Notes

- [x] Task 5: Add `institution-settings` URL to `institution/urls.py` (AC: #1)
  - [x] `path('settings/', views.institution_settings, name='institution-settings')`

- [x] Task 6: Create `templates/institution/settings.html` (AC: #1, #3)
  - [x] Extend `src/base.html`; title "Institution Settings"
  - [x] AdminLTE card with logo upload input + current logo preview
  - [x] Institution name field with note that slug is immutable
  - [x] `enctype="multipart/form-data"` on form
  - [x] See exact template in Dev Notes

- [x] Task 7: Update `templates/src/base.html` sidebar brand-logo slot (AC: #2)
  - [x] Conditionally show `active_institution.logo.url` in the sidebar brand area if logo exists
  - [x] See exact template change in Dev Notes

- [x] Task 8: Write tests in `institution/tests/test_branding.py` (AC: #1–#3)
  - [x] See exact test code in Dev Notes

## Dev Notes

### Story 3.3 Position in the 13-Step Sequence

Story 3.3 = **Step 9** (Institution admin views — branding):

```
9.  Institution admin views:
    ├── Story 3.1: institution admin dashboard  ← done
    ├── Story 3.2: clinician account management ← done
    ├── Story 3.3: institution branding setup   ← THIS STORY
    └── Story 3.4: PDF report branding
```

**Prerequisites:** Story 3.2 done. `institution/forms.py` already exists (created in Story 3.2).

**FR Coverage:** FR58 — Institution admins can upload logo and manage display settings.

---

### Task 1: `get_institution_logo_path` Callable

Add to `ndas/custom_codes/validators.py`:

```python
def get_institution_logo_path(instance, filename):
    """
    Upload path for institution logo files.

    Stores at: MEDIA_ROOT/{institution_slug}/logo/{sanitized_filename}

    FR58 / Story 1.5 pattern: institution-scoped file paths.
    `instance` is an Institution model instance.
    """
    safe_name = sanitize_filename(filename)
    return f"{instance.slug}/logo/{safe_name}"
```

This follows the same pattern as `get_institution_video_path` and `get_institution_attachment_path`
from Story 1.5.

---

### Task 2: Update `Institution.logo` Field

In `institution/models.py`, change:

```python
# BEFORE (Story 1.1 temporary path):
logo = models.ImageField(
    upload_to='institution_logos/',  # temporary path; Story 1.5 adds institution-aware paths
    null=True, blank=True
)

# AFTER (Story 3.3 — institution-aware path):
logo = models.ImageField(
    upload_to='institution.validators.get_institution_logo_path',
    null=True, blank=True
)
```

**Import at top of `institution/models.py`:**
```python
from ndas.custom_codes.validators import get_institution_logo_path
```

**Exact field change:**
```python
logo = models.ImageField(
    upload_to=get_institution_logo_path,
    null=True, blank=True,
)
```

**Note:** Django's migration system detects changes to `upload_to` callable references.
Run `python manage.py makemigrations institution` to capture this change.

---

### Task 3: `InstitutionSettingsForm` — Add to `institution/forms.py`

```python
from django.conf import settings as django_settings
from ndas.custom_codes.validators import image_extension_validation


class InstitutionSettingsForm(forms.ModelForm):
    """
    Form for institution admin to update logo and display name (FR58).
    Slug is NOT editable (immutable after creation — enforced by Institution.save()).
    """
    class Meta:
        model = Institution
        fields = ['name', 'logo']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo and hasattr(logo, 'size'):
            max_size = django_settings.FILE_UPLOAD_LIMITS.get('IMAGE_MAX_SIZE', 10 * 1024 * 1024)
            if logo.size > max_size:
                raise forms.ValidationError(
                    f"Logo file size must not exceed {max_size // (1024*1024)}MB."
                )
            # Validate extension via existing validator
            try:
                image_extension_validation(logo)
            except Exception as e:
                raise forms.ValidationError(str(e))
        return logo
```

**Import needed at top of `institution/forms.py`:**
```python
from institution.models import Institution
```

---

### Task 4: `institution_settings` View — Full Code

Add to `institution/views.py`:

```python
@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='home', error_message='Failed to save institution settings.')
def institution_settings(request):
    """
    Institution admin: upload logo + manage display settings (FR58).
    ADMIN only (or SUPERADMIN viewing institution context).
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type not in (UserType.ADMIN, UserType.SUPERADMIN):
        return redirect('home')

    institution = request.institution
    from institution.forms import InstitutionSettingsForm

    if request.method == 'POST':
        form = InstitutionSettingsForm(request.POST, request.FILES, instance=institution)
        if form.is_valid():
            form.save()
            logger.info(
                "User '%s' updated settings for institution '%s'",
                request.user.username, institution.name,
            )
            from django.contrib import messages as django_messages
            django_messages.success(request, "Institution settings saved successfully.")
            return redirect('institution:institution-settings')
    else:
        form = InstitutionSettingsForm(instance=institution)

    return render(request, 'institution/settings.html', {
        'form': form,
        'institution': institution,
    })
```

---

### Task 5: URL

Add to `institution/urls.py`:

```python
    # Story 3.3 — Institution Branding Setup
    path('settings/', views.institution_settings, name='institution-settings'),
```

---

### Task 6: `templates/institution/settings.html`

```django
{% extends 'src/base.html' %}
{% load static %}
{% block title %}Institution Settings — {{ institution.name }}{% endblock %}

{% block content_header %}
<div class="row mb-0">
  <div class="col-sm-6">
    <h1 class="m-0">Institution Settings</h1>
    <small class="text-muted">{{ institution.name }}</small>
  </div>
  <div class="col-sm-6">
    <ol class="breadcrumb float-sm-right">
      <li class="breadcrumb-item"><a href="{% url 'institution:institution-admin-dashboard' %}">Admin</a></li>
      <li class="breadcrumb-item active">Settings</li>
    </ol>
  </div>
</div>
{% endblock content_header %}

{% block main_content %}
<div class="container-fluid">
  <div class="row justify-content-center">
    <div class="col-lg-7">
      <div class="card card-primary card-outline">
        <div class="card-header"><h3 class="card-title">Branding & Display</h3></div>
        <div class="card-body">
          <form method="post" enctype="multipart/form-data">
            {% csrf_token %}
            {% include 'src/form_error.html' %}

            <div class="form-group">
              <label class="font-weight-bold">Institution Name</label>
              {{ form.name }}
              <small class="form-text text-muted">Display name only. The slug ({{ institution.slug }}) is permanent and cannot be changed.</small>
            </div>

            <div class="form-group">
              <label class="font-weight-bold">Institution Logo</label>
              {% if institution.logo %}
              <div class="mb-2">
                <img src="{{ institution.logo.url }}" alt="{{ institution.name }} logo"
                     style="max-height: 80px; max-width: 200px; object-fit: contain;">
                <small class="d-block text-muted mt-1">Current logo. Upload a new file to replace it.</small>
              </div>
              {% endif %}
              {{ form.logo }}
              <small class="form-text text-muted">JPG, PNG, or GIF. Maximum 10 MB. Recommended: transparent PNG, 200×80px.</small>
            </div>

            <div class="form-group">
              <label class="font-weight-bold">Slug (immutable)</label>
              <input type="text" class="form-control" value="{{ institution.slug }}" disabled>
              <small class="form-text text-muted">The institution slug cannot be changed after creation.</small>
            </div>

            <div class="d-flex justify-content-between mt-3">
              <a href="{% url 'institution:institution-admin-dashboard' %}" class="btn btn-secondary btn-sm">Cancel</a>
              <button type="submit" class="btn btn-primary btn-sm">
                <i class="fas fa-save mr-1"></i>Save Settings
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

---

### Task 7: Sidebar Brand-Logo Update in `templates/src/base.html`

The AdminLTE sidebar brand section is in `templates/src/basic_plane.html` (which `base.html` extends).
Find the sidebar brand logo area (typically contains `.brand-link` and `.brand-image`).

If the brand logo is in `basic_plane.html`, look for a pattern like:
```html
<a href="..." class="brand-link">
  <img src="..." class="brand-image img-circle elevation-3" alt="Logo">
  <span class="brand-text font-weight-light">NDAS</span>
</a>
```

Update it to use `active_institution` (injected by the `institution_context` context processor):

```django
<a href="{% url 'home' %}" class="brand-link">
  {% if active_institution and active_institution.logo %}
    <img src="{{ active_institution.logo.url }}"
         class="brand-image elevation-3"
         alt="{{ active_institution.name }}"
         style="max-height:33px; max-width:33px; object-fit:contain;">
  {% else %}
    <img src="{% static 'img/AdminLTELogo.png' %}"
         class="brand-image img-circle elevation-3"
         alt="NDAS">
  {% endif %}
  <span class="brand-text font-weight-light">
    {% if active_institution %}{{ active_institution.name|truncatechars:20 }}{% else %}NDAS{% endif %}
  </span>
</a>
```

**Note:** Locate the exact brand section in `templates/src/basic_plane.html` before modifying.
The file path is `templates/src/basic_plane.html` per the project structure.

---

### Task 8: `institution/tests/test_branding.py`

```python
"""
institution/tests/test_branding.py
Tests for Institution Branding Setup (Story 3.3 — FR58).
"""
import io
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()


class BrandingTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_brand', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771661001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(
            name='Brand Hospital', slug='brand-hospital',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.admin = User.objects.create_user(
            username='admin_brand', password='Testpass1!',
            first_name='Brand', last_name='Admin',
            position='Administrator', mobile_primary='0771661002',
            user_type=UserType.ADMIN, institution=self.inst,
        )
        self.settings_url = reverse('institution:institution-settings')


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class BrandingSettingsAccessTest(BrandingTestBase):
    def test_admin_can_access_settings(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.settings_url)
        self.assertEqual(response.status_code, 200)

    def test_regular_user_cannot_access_settings(self):
        regular = User.objects.create_user(
            username='reg_user_brand', password='Testpass1!',
            first_name='Regular', last_name='User',
            position='Medical Officer', mobile_primary='0771661099',
            user_type=UserType.USER, institution=self.inst,
        )
        client = Client()
        client.force_login(regular)
        response = client.get(self.settings_url)
        self.assertEqual(response.status_code, 302)


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False, MEDIA_ROOT='/tmp/ndas_test_media')
class BrandingLogoUploadTest(BrandingTestBase):
    def _make_png(self):
        """Create a minimal valid PNG for upload tests."""
        import struct, zlib
        def make_png(width=1, height=1):
            def chunk(ctype, data):
                c = ctype + data
                return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
            sig = b'\x89PNG\r\n\x1a\n'
            ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            raw = b'\x00' + b'\xff\x00\x00' * width
            compressed = zlib.compress(raw * height)
            idat = chunk(b'IDAT', compressed)
            iend = chunk(b'IEND', b'')
            return sig + ihdr + idat + iend
        return io.BytesIO(make_png())

    def test_logo_upload_saves_to_institution_scoped_path(self):
        """AC #1: Logo is saved to {institution_slug}/logo/ path."""
        client = Client()
        client.force_login(self.admin)
        png_data = self._make_png().read()
        logo = SimpleUploadedFile('logo.png', png_data, content_type='image/png')
        response = client.post(self.settings_url, {
            'name': 'Brand Hospital',
            'logo': logo,
        })
        self.assertEqual(response.status_code, 302)
        self.inst.refresh_from_db()
        if self.inst.logo:
            self.assertIn('brand-hospital', self.inst.logo.name,
                "AC #1: Logo must be stored in institution-scoped path")

    def test_name_update_persists(self):
        """AC #3: Name changes persist immediately."""
        client = Client()
        client.force_login(self.admin)
        response = client.post(self.settings_url, {'name': 'Updated Hospital Name'})
        self.assertEqual(response.status_code, 302)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.name, 'Updated Hospital Name', "AC #3: Name must persist after save")
```

---

### Project Structure Notes

**Files MODIFIED in this story:**
- `ndas/custom_codes/validators.py` — add `get_institution_logo_path` callable
- `institution/models.py` — update `Institution.logo.upload_to` + add import
- `institution/forms.py` — add `InstitutionSettingsForm` class
- `institution/views.py` — add `institution_settings` view
- `institution/urls.py` — add `institution-settings` path
- `templates/src/basic_plane.html` — update brand-logo slot (conditional on `active_institution.logo`)

**Files CREATED in this story:**
- `templates/institution/settings.html` — settings form template
- `institution/tests/test_branding.py` — 5+ tests
- `institution/migrations/000X_logo_path_callable.py` — generated by makemigrations

**Files NOT touched:**
- `reports/utils/pdf_generator.py` — PDF branding is Story 3.4's responsibility

---

### References

- FR58: Institution logo upload and display settings [Source: `_bmad-output/planning-artifacts/epics.md#Story 3.3`]
- Architecture: Logo stored at `MEDIA_ROOT/{institution_slug}/logo/` [Source: `_bmad-output/planning-artifacts/epics.md#File Storage`]
- Architecture: `institution_context` context processor provides `active_institution` to all templates [Source: `_bmad-output/planning-artifacts/epics.md#Templates & Frontend`]
- Story 1.5: `get_institution_video_path`, `get_institution_attachment_path` pattern for callable `upload_to` [Source: `_bmad-output/implementation-artifacts/1-5-institution-aware-file-storage.md`]
- Project context: Image max size via `settings.FILE_UPLOAD_LIMITS['IMAGE_MAX_SIZE']` [Source: `_bmad-output/project-context.md#File Upload Limits`]
- Project context: `image_extension_validation` in `validators.py` [Source: `_bmad-output/project-context.md#Custom Codes Directory`]
- Project context: `enctype="multipart/form-data"` required for file upload forms [Source: standard Django requirement]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- `makemigrations institution` failed interactively due to unrelated problemlist pending migration. Wrote migration 0004 manually (upload_to change is a no-op DB change).
- Logo upload test failed: `STORAGES` override for `staticfiles` replaced the entire dict, losing `default` storage. Fixed by including both `default` and `staticfiles` in the override.

### Completion Notes List

- Added `get_institution_logo_path()` callable to validators.py (pattern matches existing video/attachment path callables from Story 1.5).
- Updated `Institution.logo.upload_to` from string to callable; created manual migration 0004.
- Added `InstitutionSettingsForm` to forms.py with size validation and image extension check.
- Added `institution_settings` view (ADMIN/SUPERADMIN only, uses `_get_admin_institution` helper).
- Added `institution-settings` URL.
- Created `settings.html` template with logo preview and form.
- Added brand-link with institution logo to `main_sidebar_menu.html` (renders via `active_institution` context processor).
- 6/6 tests pass covering AC #1–#3.

### File List

- ndas/custom_codes/validators.py (modified — added get_institution_logo_path callable)
- institution/models.py (modified — updated logo upload_to, added import)
- institution/migrations/0004_institution_logo_path_callable.py (created)
- institution/forms.py (modified — added InstitutionSettingsForm)
- institution/views.py (modified — added institution_settings view)
- institution/urls.py (modified — added institution-settings path)
- templates/institution/settings.html (created)
- templates/src/main_sidebar_menu.html (modified — added brand-link with institution logo)
- institution/tests/test_branding.py (created — 6 tests)

### Change Log

- 2026-02-26: Story 3.3 implemented — Institution Branding Setup (FR58). Logo path callable, settings form/view/URL/template, sidebar brand-logo slot.
