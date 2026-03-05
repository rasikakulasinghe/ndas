---
title: 'Institution Short-Name, Superadmin Edit, and Role-Based Navigation'
slug: 'institution-shortname-nav-rbac'
created: '2026-03-04'
status: 'Completed'
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
tech_stack: ['Django 4.2', 'AdminLTE 3.2', 'Bootstrap 4.6', 'HTMX', 'SQLite/PostgreSQL']
files_to_modify:
  - 'institution/models.py'
  - 'institution/forms.py'
  - 'institution/views.py'
  - 'institution/urls.py'
  - 'templates/src/main_sidebar_menu.html'
  - 'templates/institution/selector.html'
  - 'templates/institution/settings.html'
  - 'templates/institution/add.html'
  - 'video/views.py'
  - 'problemlist/views.py'
  - 'patients/views.py'
files_to_create:
  - 'institution/migrations/0005_institution_short_name.py'
  - 'templates/institution/edit.html'
code_patterns:
  - 'Model.objects.filter(patient__institution=getattr(request, institution, None)).get(pk=pk)'
  - 'Patient.objects.for_institution(getattr(request, institution, None))'
  - '{% if user_type == "ADMIN" or is_superadmin %}'
  - 'data-toggle="tooltip" data-placement="right" data-container="body"'
test_patterns:
  - 'patientstests/'
---

# Tech-Spec: Institution Short-Name, Superadmin Edit, and Role-Based Navigation

**Created:** 2026-03-04

## Overview

### Problem Statement

The `Institution` model lacks a compact short-name identifier (e.g., 'LRH') needed for the sidebar brand slot. SUPERADMIN has no view to edit any institution's profile directly — only the institution's own ADMIN can do so via `institution_settings`. The left sidebar navigation is not fully role-differentiated: the Reports section is visible to plain USER accounts, ADMIN users do not see the Administration collapsible (gate uses `is_staff or is_superuser` rather than `user_type`), and ADMIN-specific navigation items are split across two separate sections (Administration and a standalone MY INSTITUTION block). All patient-owned records (assessments, videos, attachments, problem lists, bookmarks) must be strictly isolated to their owning institution — no cross-institution access is permitted except through the existing referral system. Deep investigation confirmed 26 UNSAFE lookups across `video/views.py` (4), `problemlist/views.py` (7), and `patients/views.py` (15+) that allow cross-institution data access — all must be fixed.

### Solution

Add `short_name` CharField to `Institution`, update the sidebar brand slot to display it with a Bootstrap tooltip showing the full name, add a SUPERADMIN-only institution-edit view (by institution pk), update both `InstitutionOnboardingForm` and `InstitutionSettingsForm` to include `short_name`, consolidate the sidebar into a single `Administration` collapsible correctly gated by `user_type`, remove the orphaned MY INSTITUTION section, hide Reports from plain USERs, and fix all 26 institution isolation gaps across three view files.

### Scope

**In Scope:**
- Add `short_name` CharField (max 10, blank=True at model level, required at form level) to `Institution` + migration `0005`
- Update `InstitutionOnboardingForm` and `institution_add` view to accept `short_name`
- Update `InstitutionSettingsForm` to include `short_name` (for ADMIN self-edit)
- New `SuperadminInstitutionEditForm` + `superadmin_institution_edit` view + URL + template
- Sidebar brand-text → `short_name`; Bootstrap tooltip on brand-link with `data-container="body"`
- Sidebar reorganization: single `Administration` collapsible; Reports gated; MY INSTITUTION section removed
- Fix all 26 UNSAFE institution isolation lookups

**Out of Scope:**
- Slug immutability (unchanged)
- Institution deletion
- Referral system changes
- Report generator logic
- Deep user-management institution-scoping audit
- ADMIN creating ADMIN-type accounts

## Context for Development

### Codebase Patterns

**View decorator stack (mandatory on all new views):**
```python
@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='home', error_message='...')
```

**Institution context — always use these in templates, never Django built-ins:**
- `active_institution` — Institution object from `institution/context_processors.py`
- `user_type` — `'USER'`, `'ADMIN'`, or `'SUPERADMIN'`
- `is_superadmin` — bool
- **NEVER** `request.user.institution` → always `request.institution` (SUPERADMIN context-switching makes them different)
- **NEVER** `{% if request.user.is_superuser %}` in templates → always `{% if is_superadmin %}`

**Patient isolation — custom manager (already exists, use consistently):**
```python
patient = get_object_or_404(
    Patient.objects.for_institution(getattr(request, 'institution', None)), pk=pid
)
```

**Child record isolation — two fix patterns depending on existing code structure:**

Pattern A — for views already using `get_object_or_404`:
```python
# BEFORE (unsafe)
obj = get_object_or_404(Video, id=video_id)
# AFTER (safe)
obj = get_object_or_404(Video, id=video_id,
                        patient__institution=getattr(request, 'institution', None))
```

Pattern B — for views using `.get()` inside `try/except` (preserves existing error messaging):
```python
# BEFORE (unsafe)
assessment = GMAssessment.objects.select_related(...).get(id=pk)
# AFTER (safe) — add .filter() before .get()
assessment = GMAssessment.objects.select_related(...)\
    .filter(patient__institution=getattr(request, 'institution', None)).get(id=pk)
```

Pattern C — for list/manager views using base queryset:
```python
# BEFORE
base_qs = GMAssessment.objects.select_related(...)
# AFTER — add institution filter immediately after select_related
base_qs = GMAssessment.objects.select_related(...)\
    .filter(patient__institution=getattr(request, 'institution', None))
```

**Bookmark model** — Uses `owner` FK (not `added_by`). Confirmed from `patients/models.py:2010`. Scope via `owner__institution`:
```python
# List
Bookmark.objects.filter(owner__institution=getattr(request, 'institution', None))
# Detail
get_object_or_404(Bookmark, id=pk, owner__institution=getattr(request, 'institution', None))
```

**Bootstrap tooltip** — Already initialised in `static/js/main.js:67-69`. Add `data-toggle="tooltip" data-placement="right" data-container="body"` — `data-container="body"` required for correct display inside AdminLTE sidebar. No JS change needed.

**Migration** — Next number is `0005`. Field added as `blank=True, default=''` so Django auto-generates migration without interactive prompt. `RunPython` fills existing rows. Form-level validation enforces required — not model level (Django ORM does not call `.full_clean()` on `.save()`).

**Sidebar gate convention:**
```django
{# WRONG — uses Django built-ins, misses ADMIN user_type #}
{% if user.is_staff or user.is_superuser %}
{# RIGHT — uses context processor vars #}
{% if user_type == 'ADMIN' or is_superadmin %}
```

### Files to Reference

| File | Purpose | Key Lines |
| ---- | ------- | --------- |
| `institution/models.py` | Add `short_name` field | 8–51 |
| `institution/forms.py` | Update `InstitutionOnboardingForm` (21), `InstitutionSettingsForm` (186); add `SuperadminInstitutionEditForm` | 21, 186 |
| `institution/views.py` | Update `institution_add` (145); add `superadmin_institution_edit` after it | 123–200, 808 |
| `institution/urls.py` | Add URL | All 35 lines |
| `institution/migrations/` | Next = `0005` (after `0004_institution_logo_path_callable`) | — |
| `templates/src/main_sidebar_menu.html` | Brand slot + full sidebar rewrite | 8–478 |
| `templates/institution/selector.html` | Add Edit button per card | 98–107 (card-footer) |
| `templates/institution/settings.html` | Add `short_name` field | 37–42 |
| `templates/institution/add.html` | Add `short_name` field | 53–75 |
| `templates/institution/edit.html` | **NEW** superadmin edit template | — |
| `video/views.py` | Fix 4 unsafe lookups | 112, 156, 473, 525 |
| `problemlist/views.py` | Fix 7 unsafe lookups | 40, 113, 141, 189, 345, 392, 419 |
| `patients/views.py` | Fix 18 unsafe lookups | 987, 1023, 1056, 1084, 1123, 1213, 1311, 1482, 1505, 1962, 1976, 2079, 2486, 2623, 2667, 2680, 2861, 3043, 3282, 3591 |
| `static/js/main.js` | Tooltip init at 67–69 — **no change** | 67–69 |
| `patients/models.py` | Bookmark model: `owner` FK at line 2010 — reference only | 2010 |

### Technical Decisions

- **`short_name` field**: `CharField(max_length=10, blank=True, default='')` in the model. `blank=True` + `default=''` ensures Django generates the migration cleanly without an interactive prompt. Required enforcement is at form level (both `InstitutionOnboardingForm` and `InstitutionSettingsForm` declare it required — no `required=False`). `SuperadminInstitutionEditForm` also treats it as required.
- **Migration strategy**: 3-step in one migration file: (1) add column with `default=''`, (2) `RunPython` populates existing rows, (3) no alter needed — column stays `blank=True` at DB level; form enforces it.
- **Superadmin edit form** (`SuperadminInstitutionEditForm`): `ModelForm` on `Institution`, fields `['name', 'short_name', 'logo', 'is_active', 'subscription_status']`. Slug excluded (immutable). `clean_logo` fully copies from `InstitutionSettingsForm` (see Task 2c).
- **Video `added_by` check is kept**: Task 8 adds institution scoping but does NOT remove the existing `added_by`/`is_staff` permission checks — those prevent intra-institution record access by the wrong user and are a separate concern.
- **Bootstrap tooltip on brand-link**: Must add `data-container="body"` to avoid AdminLTE sidebar event interference.
- **Sidebar active-link detection for moved items**: Add `'institution-admin-dashboard' in request.resolver_match.url_name or 'institution-settings' in request.resolver_match.url_name or 'institution-clinician' in request.resolver_match.url_name` to the Administration `<li>` `menu-open` condition.
- **Bootstrap 4.6 compatibility**: Use `class="btn btn-outline-secondary btn-sm ml-2"` on the Edit button in selector.html — no `gap-*` utilities (Bootstrap 5 only).
- **Attachment/assessment views using `.get()`**: Use Pattern B (add `.filter()` before `.get()`) to preserve the existing `try/except` error messaging and redirects.

## Implementation Plan

### Tasks

---

**Task 1 — Add `short_name` to Institution model + migration**

File: `institution/models.py`
- Add field after `slug` (line 10):
```python
short_name = models.CharField(max_length=10, blank=True, default='')
```

File: `institution/migrations/0005_institution_short_name.py` — write this file manually:
```python
from django.db import migrations, models

def populate_short_name(apps, schema_editor):
    Institution = apps.get_model('institution', 'Institution')
    for inst in Institution.objects.filter(short_name=''):
        inst.short_name = inst.name[:10].upper()
        inst.save(update_fields=['short_name'])

class Migration(migrations.Migration):

    dependencies = [
        ('institution', '0004_institution_logo_path_callable'),
    ]

    operations = [
        migrations.AddField(
            model_name='institution',
            name='short_name',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
        migrations.RunPython(populate_short_name, migrations.RunPython.noop),
    ]
```

Verify: `python manage.py migrate` completes; `python manage.py makemigrations --check` shows no pending migrations.

---

**Task 2 — Update forms**

File: `institution/forms.py`

**2a. `InstitutionOnboardingForm`** — add field after `institution_slug` declaration, and add clean method inside the class:
```python
institution_short_name = forms.CharField(
    max_length=10,
    label="Short Name",
    widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'e.g. LRH',
        'id': 'id_institution_short_name',
    }),
    help_text="Compact identifier shown in sidebar (max 10 chars, e.g. LRH).",
)

def clean_institution_short_name(self):
    return sanitize_text_input(self.cleaned_data['institution_short_name']).upper()
```
Note: `clean_institution_short_name` is a method of `InstitutionOnboardingForm` — indent at class level.

**2b. `InstitutionSettingsForm`** — update `Meta.fields` and `Meta.widgets`:
```python
class Meta:
    model = Institution
    fields = ['name', 'short_name', 'logo']
    widgets = {
        'name': forms.TextInput(attrs={'class': 'form-control'}),
        'short_name': forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. LRH',
        }),
        'logo': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
    }
```

**2c. New `SuperadminInstitutionEditForm`** — add after `InstitutionSettingsForm`:
```python
class SuperadminInstitutionEditForm(forms.ModelForm):
    """SUPERADMIN: edit any institution's profile by pk."""

    class Meta:
        model = Institution
        fields = ['name', 'short_name', 'logo', 'is_active', 'subscription_status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'short_name': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. LRH',
            }),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'subscription_status': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_short_name(self):
        return sanitize_text_input(self.cleaned_data['short_name']).upper()

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo and hasattr(logo, 'size'):
            max_size = getattr(django_settings, 'FILE_UPLOAD_LIMITS', {}).get(
                'IMAGE_MAX_SIZE', 10 * 1024 * 1024
            )
            if logo.size > max_size:
                raise forms.ValidationError(
                    f"Logo file size must not exceed {max_size // (1024 * 1024)}MB."
                )
            try:
                image_extension_validation(logo)
            except Exception as e:
                raise forms.ValidationError(str(e))
        return logo
```
Note: `django_settings` and `image_extension_validation` are already imported at the top of `institution/forms.py` (lines 9–16) — no new imports needed.

---

**Task 3 — Update `institution_add`; add `superadmin_institution_edit`**

File: `institution/views.py`

**3a.** In `institution_add` view, update `Institution.objects.create(...)` at line 145 to include `short_name`:
```python
institution = Institution.objects.create(
    name=form.cleaned_data['institution_name'],
    slug=form.cleaned_data['institution_slug'],
    short_name=form.cleaned_data['institution_short_name'],
    subscription_status=SubscriptionStatus.ACTIVE,
    is_active=True,
    created_by=request.user,
)
```

**3b.** Add `SuperadminInstitutionEditForm` to the import in `institution_add` view body (it lazy-imports from `institution.forms`) — or add to the module-level imports at top of file alongside `InstitutionOnboardingForm`.

**3c.** Add new view after `institution_add`:
```python
@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(
    redirect_url='institution:institution-selector',
    error_message='Failed to save institution settings.'
)
def superadmin_institution_edit(request, institution_id):
    """
    SUPERADMIN: edit any institution's profile by pk.
    No is_active filter — superadmin can edit/reactivate inactive institutions.
    """
    from institution.forms import SuperadminInstitutionEditForm

    if getattr(request.user, 'user_type', None) != UserType.SUPERADMIN:
        return redirect('manage-patients')

    institution = get_object_or_404(Institution, pk=institution_id)

    form = SuperadminInstitutionEditForm(
        request.POST or None,
        request.FILES or None,
        instance=institution,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        logger.info(
            "SUPERADMIN '%s' edited institution '%s' (id=%d)",
            request.user.username, institution.name, institution.pk,
        )
        messages.success(request, f"Institution '{institution.name}' updated successfully.")
        return redirect('institution:institution-selector')

    return render(request, 'institution/edit.html', {
        'form': form,
        'institution': institution,
        'page_title': f'Edit Institution — {institution.name}',
    })
```

---

**Task 4 — Add URL**

File: `institution/urls.py` — insert after the `institution-add` path:
```python
path('edit/<int:institution_id>/', views.superadmin_institution_edit, name='superadmin-institution-edit'),
```

---

**Task 5 — Update templates for `short_name`**

**5a. `templates/institution/add.html`** — add inside Institution Details card, after the slug `form-group` div (after line 75, before the closing `</div>` of the card-body):
```html
<div class="form-group">
  <label for="{{ form.institution_short_name.id_for_label }}">
    Short Name <span class="text-danger">*</span>
    <i class="fas fa-info-circle text-muted ml-1"
       data-toggle="tooltip"
       data-placement="top"
       title="Compact identifier shown in the sidebar (max 10 chars)."></i>
  </label>
  {{ form.institution_short_name }}
  {% if form.institution_short_name.errors %}
  <div class="text-danger small mt-1">{{ form.institution_short_name.errors.0 }}</div>
  {% endif %}
  <small class="form-text text-muted">{{ form.institution_short_name.help_text }}</small>
</div>
```

**5b. `templates/institution/settings.html`** — add after the `name` form-group div (after line 43):
```html
<div class="form-group">
  <label class="font-weight-bold">Short Name</label>
  {{ form.short_name }}
  {% if form.short_name.errors %}
  <div class="text-danger small">{{ form.short_name.errors.0 }}</div>
  {% endif %}
  <small class="form-text text-muted">Compact identifier shown in the sidebar (max 10 chars, e.g. LRH).</small>
</div>
```

**5c. `templates/institution/selector.html`** — replace the existing card-footer (lines 98–107) with:
```html
<div class="card-footer py-2 d-flex">
  <form method="post" action="{% url 'institution:institution-switch' inst.pk %}" class="flex-grow-1">
    {% csrf_token %}
    <button type="submit" class="btn btn-primary btn-sm btn-block"
      {% if not inst.is_active %}disabled{% endif %}>
      <i class="fas fa-sign-in-alt mr-1"></i>Enter
    </button>
  </form>
  <a href="{% url 'institution:superadmin-institution-edit' inst.pk %}"
     class="btn btn-outline-secondary btn-sm ml-2"
     data-toggle="tooltip" data-placement="top" title="Edit institution profile">
    <i class="fas fa-edit"></i>
  </a>
</div>
```
Note: `ml-2` not `gap-2` — Bootstrap 4.6 does not have `gap-*` utilities.

**5d. New `templates/institution/edit.html`** — create this file:
```html
{% extends 'src/base.html' %}
{% load static %}

{% block title %}Edit Institution — {{ institution.name }}{% endblock %}

{% block content_header %}
<div class="row mb-0">
  <div class="col-sm-6">
    <h1 class="m-0">Edit Institution</h1>
    <small class="text-muted">{{ institution.name }}</small>
  </div>
  <div class="col-sm-6">
    <ol class="breadcrumb float-sm-right">
      <li class="breadcrumb-item">
        <a href="{% url 'institution:institution-selector' %}">All Institutions</a>
      </li>
      <li class="breadcrumb-item active">Edit</li>
    </ol>
  </div>
</div>
{% endblock content_header %}

{% block main_content %}
<div class="container-fluid">
  <div class="row justify-content-center">
    <div class="col-lg-7">
      <div class="card card-primary card-outline">
        <div class="card-header">
          <h3 class="card-title">
            <i class="fas fa-hospital mr-2"></i>Institution Profile
          </h3>
        </div>
        <div class="card-body">
          <form method="post" enctype="multipart/form-data">
            {% csrf_token %}
            {% if form.non_field_errors %}
            <div class="alert alert-danger">
              {% for error in form.non_field_errors %}{{ error }}{% endfor %}
            </div>
            {% endif %}

            <div class="form-group">
              <label class="font-weight-bold">Institution Name</label>
              {{ form.name }}
              {% if form.name.errors %}
              <div class="text-danger small">{{ form.name.errors.0 }}</div>
              {% endif %}
              <small class="form-text text-muted">
                The slug (<code>{{ institution.slug }}</code>) is permanent and cannot be changed.
              </small>
            </div>

            <div class="form-group">
              <label class="font-weight-bold">Short Name</label>
              {{ form.short_name }}
              {% if form.short_name.errors %}
              <div class="text-danger small">{{ form.short_name.errors.0 }}</div>
              {% endif %}
              <small class="form-text text-muted">Compact identifier shown in sidebar (max 10 chars).</small>
            </div>

            <div class="form-group">
              <label class="font-weight-bold">Logo</label>
              {% if institution.logo %}
              <div class="mb-2">
                <img src="{{ institution.logo.url }}" alt="{{ institution.name }} logo"
                     style="max-height:80px; max-width:200px; object-fit:contain;
                            border:1px solid #dee2e6; padding:4px;">
                <small class="d-block text-muted mt-1">Current logo. Upload to replace.</small>
              </div>
              {% endif %}
              {{ form.logo }}
              {% if form.logo.errors %}
              <div class="text-danger small">{{ form.logo.errors.0 }}</div>
              {% endif %}
              <small class="form-text text-muted">JPG, PNG, or GIF. Maximum 10 MB.</small>
            </div>

            <div class="form-group">
              <label class="font-weight-bold">Subscription Status</label>
              {{ form.subscription_status }}
              {% if form.subscription_status.errors %}
              <div class="text-danger small">{{ form.subscription_status.errors.0 }}</div>
              {% endif %}
            </div>

            <div class="form-group">
              <div class="custom-control custom-checkbox">
                {{ form.is_active }}
                <label class="custom-control-label font-weight-bold" for="{{ form.is_active.id_for_label }}">
                  Active
                </label>
              </div>
              {% if form.is_active.errors %}
              <div class="text-danger small">{{ form.is_active.errors.0 }}</div>
              {% endif %}
              <small class="form-text text-muted">Uncheck to deactivate this institution.</small>
            </div>

            <div class="d-flex justify-content-between mt-4">
              <a href="{% url 'institution:institution-selector' %}" class="btn btn-secondary btn-sm">
                <i class="fas fa-arrow-left mr-1"></i>Cancel
              </a>
              <button type="submit" class="btn btn-primary btn-sm">
                <i class="fas fa-save mr-1"></i>Save Changes
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

**Task 6 — Update sidebar brand slot**

File: `templates/src/main_sidebar_menu.html`

**6a.** For each of the 4 brand-link `<a>` variants (at lines 9, 13, 17, 21), add `data-toggle="tooltip" data-placement="right" data-container="body"` to the existing `<a>` tag. The `title` attribute already contains the full institution name on each variant — no change to `title` needed.

Example (line 9):
```html
{# BEFORE #}
<a href="{% url 'institution:superadmin-dashboard' %}" class="brand-link"
   title="{{ active_institution.name }}"
   aria-label="{{ active_institution.name }} — Superadmin Dashboard">

{# AFTER #}
<a href="{% url 'institution:superadmin-dashboard' %}" class="brand-link"
   title="{{ active_institution.name }}"
   aria-label="{{ active_institution.name }} — Superadmin Dashboard"
   data-toggle="tooltip" data-placement="right" data-container="body">
```
Apply the same addition to lines 13, 17, and 21.

**6b.** Replace brand-text span (lines 46–48):
```django
{# BEFORE #}
<span class="brand-text font-weight-light">
  {% if active_institution %}{{ active_institution.name|truncatechars:20 }}{% else %}NDAS{% endif %}
</span>

{# AFTER #}
<span class="brand-text font-weight-light">
  {% if active_institution %}
    {{ active_institution.short_name|default:active_institution.name|slice:":10" }}
  {% else %}NDAS{% endif %}
</span>
```
The `default` filter handles the (edge-case) of an institution with an empty `short_name` by falling back to the first 10 chars of the full name.

---

**Task 7 — Sidebar reorganization**

File: `templates/src/main_sidebar_menu.html`

**7a. Update the Administration `<li>` opening tag** (line 292–297) — change the gate condition and expand the `menu-open` / `active` detection to cover moved institution-admin URL names:
```django
{# BEFORE #}
<li
  class="nav-item {% if 'admin' in request.resolver_match.url_name or is_superadmin and request.resolver_match.namespace == 'institution' %}menu-open{% endif %}"
>
  <a
    href="#"
    class="nav-link {% if 'admin' in request.resolver_match.url_name or is_superadmin and request.resolver_match.namespace == 'institution' %}active{% endif %}"
  >

{# AFTER #}
{% with admin_active='admin' in request.resolver_match.url_name or request.resolver_match.namespace == 'institution' %}
<li class="nav-item {% if admin_active %}menu-open{% endif %}">
  <a href="#"
     class="nav-link {% if admin_active %}active{% endif %}">
{% endwith %}
```
Note: The `{% with %}` tag must wrap the `<li>` and its `<a>`, and be closed (`{% endwith %}`) after the `</a>` tag and before the `<ul class="nav nav-treeview">`.

**7b. Replace the gate condition** wrapping the entire Administration block (line 290):
```django
{# BEFORE #}
{% if user.is_staff or user.is_superuser %}

{# AFTER #}
{% if user_type == 'ADMIN' or is_superadmin %}
```

**7c. Replace the Administration treeview `<ul>...</ul>`** (lines 305–386) with:
```django
<ul class="nav nav-treeview">

  {# ── Shared: ADMIN and SUPERADMIN ── #}
  <li class="nav-item">
    <a href="{% url 'admin-dashboard' %}"
       class="nav-link {% if request.resolver_match.url_name == 'admin-dashboard' %}active{% endif %}">
      <i class="far fa-circle nav-icon"></i><p>Staff Dashboard</p>
    </a>
  </li>
  <li class="nav-item">
    <a href="{% url 'admin-user-list' %}"
       class="nav-link {% if request.resolver_match.url_name == 'admin-user-list' %}active{% endif %}">
      <i class="far fa-circle nav-icon"></i><p>Users</p>
    </a>
  </li>
  <li class="nav-item">
    <a href="{% url 'admin-user-add' %}"
       class="nav-link {% if request.resolver_match.url_name == 'admin-user-add' %}active{% endif %}">
      <i class="far fa-circle nav-icon"></i><p>Add User</p>
    </a>
  </li>
  <li class="nav-item">
    <a href="{% url 'admin-activity-logs' %}"
       class="nav-link {% if request.resolver_match.url_name == 'admin-activity-logs' %}active{% endif %}">
      <i class="far fa-circle nav-icon"></i><p>Activity Logs</p>
    </a>
  </li>

  {# ── ADMIN-only: My Institution ── #}
  {% if user_type == 'ADMIN' %}
  <li class="nav-header">MY INSTITUTION</li>
  <li class="nav-item">
    <a href="{% url 'institution:institution-admin-dashboard' %}"
       class="nav-link {% if request.resolver_match.url_name == 'institution-admin-dashboard' %}active{% endif %}">
      <i class="far fa-circle nav-icon"></i><p>Admin Dashboard</p>
    </a>
  </li>
  <li class="nav-item">
    <a href="{% url 'institution:institution-settings' %}"
       class="nav-link {% if request.resolver_match.url_name == 'institution-settings' %}active{% endif %}">
      <i class="far fa-circle nav-icon"></i><p>Institution Settings</p>
    </a>
  </li>
  <li class="nav-item">
    <a href="{% url 'institution:institution-clinician-list' %}"
       class="nav-link {% if request.resolver_match.url_name in 'institution-clinician-list institution-clinician-add' %}active{% endif %}">
      <i class="far fa-circle nav-icon"></i><p>Clinicians</p>
    </a>
  </li>
  {% endif %}

  {# ── SUPERADMIN-only: Network ── #}
  {% if is_superadmin %}
  <li class="nav-header">NETWORK</li>
  <li class="nav-item">
    <a href="{% url 'institution:institution-selector' %}"
       class="nav-link {% if request.resolver_match.url_name == 'institution-selector' %}active{% endif %}">
      <i class="far fa-circle nav-icon"></i><p>All Institutions</p>
    </a>
  </li>
  <li class="nav-item">
    <a href="{% url 'institution:institution-add' %}"
       class="nav-link {% if request.resolver_match.url_name == 'institution-add' %}active{% endif %}">
      <i class="far fa-circle nav-icon"></i><p>Add Institution</p>
    </a>
  </li>
  <li class="nav-item">
    <a href="{% url 'institution:superadmin-dashboard' %}"
       class="nav-link {% if request.resolver_match.url_name == 'superadmin-dashboard' %}active{% endif %}">
      <i class="far fa-circle nav-icon"></i><p>Superadmin Dashboard</p>
    </a>
  </li>
  <li class="nav-item">
    <a href="{% url 'institution:superadmin-reports' %}"
       class="nav-link {% if request.resolver_match.url_name == 'superadmin-reports' %}active{% endif %}">
      <i class="far fa-circle nav-icon"></i><p>Aggregate Reports</p>
    </a>
  </li>
  {% endif %}

  {# ── Superuser-only ── #}
  {% if user.is_superuser %}
  <li class="nav-item">
    <a href="{% url 'subscription-update' %}"
       class="nav-link {% if request.resolver_match.url_name == 'subscription-update' %}active{% endif %}">
      <i class="far fa-circle nav-icon"></i><p>Update Subscription</p>
    </a>
  </li>
  {% endif %}

</ul>
```

**7d. Gate the Reports section** — wrap the existing Reports `<li class="nav-item ...">` block (lines 254–288) with:
```django
{% if user_type == 'ADMIN' or is_superadmin %}
  {# ... existing Reports li block, unchanged ... #}
{% endif %}
```

**7e. Delete the standalone MY INSTITUTION block** — remove lines 391–414 entirely (the `{% if user_type == 'ADMIN' %}` block with nav-header "MY INSTITUTION"). Its items are now inside Administration.

---

**Task 8 — Fix institution isolation: `video/views.py`**

File: `video/views.py` — 4 views, all use `get_object_or_404(Video, ...)` → apply Pattern A.

**DO NOT remove the existing `added_by` / `is_staff` permission checks** — those control intra-institution access and are a separate concern. Only add the institution scope.

| Line | View | Change |
|------|------|--------|
| 112 | `video_view` | `get_object_or_404(Video, id=video_id)` → `get_object_or_404(Video, id=video_id, patient__institution=getattr(request, 'institution', None))` |
| 156 | `video_edit` | Same |
| 473 | `video_delete_confirm` | Same |
| 525 | `video_delete` | Same |

---

**Task 9 — Fix institution isolation: `problemlist/views.py`**

File: `problemlist/views.py` — 7 views.

| Line | View | Current | Fix |
|------|------|---------|-----|
| 40 | `problem_manager` | `get_object_or_404(Patient, pk=pid)` | `get_object_or_404(Patient.objects.for_institution(getattr(request, 'institution', None)), pk=pid)` |
| 113 | `problem_view` | `get_object_or_404(Problem, pk=pk)` | `get_object_or_404(Problem, pk=pk, patient__institution=getattr(request, 'institution', None))` |
| 141 | `problem_edit` | Same | Same fix |
| 189 | `problem_delete` | Same | Same fix |
| 345 | `problem_status_change` | Same | Same fix — if institution mismatch returns 404, the HTMX partial will render a 404 fragment into the swap target; this is acceptable (the request was unauthorized) |
| 392 | `problem_timeline` | Same | Same fix |
| 419 | `problem_action_add` | Same | Same fix |

---

**Task 10 — Fix institution isolation: `patients/views.py`**

File: `patients/views.py` — 18 unsafe lookups. Use Pattern B (add `.filter()` before `.get()`) for views using `.get()` in try/except; Pattern A for views already using `get_object_or_404`; Pattern C for manager/list views.

**GMAssessment — 6 fixes:**

| Line | View | Pattern | Change |
|------|------|---------|--------|
| 987 | `assessment_view` | B | `GMAssessment.objects.select_related(...).get(id=pk)` → `GMAssessment.objects.select_related(...).filter(patient__institution=getattr(request, 'institution', None)).get(id=pk)` |
| 1023 | `assessment_view_by_fileid` | B | Add `.filter(patient__institution=...)` to the existing queryset chain before `.get(...)` |
| 1056 | `assessment_edit` | B | Same as line 987 |
| 1084 | `assessment_edit_by_fileid` | A | `get_object_or_404(GMAssessment, video_file=pk)` → `get_object_or_404(GMAssessment, video_file=pk, patient__institution=getattr(request, 'institution', None))` |
| 1123 | `assessment_delete` | A | `get_object_or_404(GMAssessment, id=pk)` → add `patient__institution=getattr(request, 'institution', None)` |
| 1213 | `assessment_manager` | C | `base_qs = GMAssessment.objects.select_related(...)` → append `.filter(patient__institution=getattr(request, 'institution', None))` at the end of the `select_related(...)` chain on the same line |

**Bookmark — 3 fixes (use `owner__institution`, NOT `added_by__institution`):**

Confirmed: `Bookmark` model at `patients/models.py:2010` uses `owner` FK.

| Line | View | Pattern | Change |
|------|------|---------|--------|
| 1311 | `bookmark_manager` | C | `Bookmark.objects.all().order_by("-id")` → `Bookmark.objects.filter(owner__institution=getattr(request, 'institution', None)).order_by("-id")` |
| 1482 | `bookmark_view` | A | `get_object_or_404(Bookmark, id=pk)` → add `owner__institution=getattr(request, 'institution', None)` |
| 1505 | `bookmark_delete` | A | Same |

**Attachment — 3 fixes (view + edit + delete all use `.get()` in try/except):**

| Line | View | Pattern | Change |
|------|------|---------|--------|
| 1964 | `attachment_view` | B | `Attachment.objects.select_related(...).get(pk=pk)` → add `.filter(patient__institution=getattr(request, 'institution', None))` before `.get(pk=pk)` |
| 1978 | `attachment_edit` | B | Same |
| 2079 | `attachment_delete` | A or B | Apply same institution filter pattern |

**CDICRecord — 1 fix:**

| Line | View | Pattern | Change |
|------|------|---------|--------|
| 2486 | `cdic_record_*` | B | Add `.filter(patient__institution=getattr(request, 'institution', None))` before `.get(id=aid)` |

**HINEAssessment — 4 fixes:**

| Line | View | Pattern | Change |
|------|------|---------|--------|
| 2623 | `hine_assessment_edit` | A | `get_object_or_404(HINEAssessment, pk=hine_id)` → add `patient__institution=getattr(request, 'institution', None)` |
| 2667 | `hine_assessment_view` | B | `HINEAssessment.objects.select_related(...).get(pk=hine_id)` → add `.filter(patient__institution=...)` before `.get()` |
| 2680 | `hine_assessment_manager` | C | Add `.filter(patient__institution=...)` to base queryset |
| 2861 | `hine_assessment_delete` | A | `get_object_or_404(HINEAssessment, id=hine_id)` → add `patient__institution=getattr(request, 'institution', None)` |

**DevelopmentalAssessment — 3 fixes:**

| Line | View | Pattern | Change |
|------|------|---------|--------|
| 3043 | `da_assessment_manager` | C | Add `.filter(patient__institution=...)` to base queryset |
| 3282 | `da_assessment_delete` | A | `get_object_or_404(DevelopmentalAssessment, id=da_id)` → add `patient__institution=getattr(request, 'institution', None)` |
| (view/edit lines) | `da_assessment_view`, `da_assessment_edit` | B | Add `.filter(patient__institution=...)` before `.get()` in try/except block |

**GeneralPaediatricAssessment — 1+ fixes:**

| Line | View | Pattern | Change |
|------|------|---------|--------|
| 3591 | `gpa_record_view/edit/delete` | B or A | Add `patient__institution=getattr(request, 'institution', None)` to each lookup |

### Acceptance Criteria

**AC-1: short_name model + migration**
- Given: An existing NDAS installation with at least one Institution. When: `python manage.py migrate` runs. Then: All existing institutions have `short_name` auto-populated as `name[:10].upper()` and the migration completes without errors.
- Given: The Add Institution form. When: Submitted with `short_name` field left blank. Then: The form rejects submission with a required-field validation error on short_name (form-level validation, not model-level).
- Given: The migration is applied. When: `python manage.py makemigrations --check` is run. Then: Output shows no pending migrations.

**AC-2: Onboarding form includes short_name**
- Given: A SUPERADMIN on the Add Institution page (`/institution/add/`). When: They submit without filling in Short Name. Then: Form rejects with a required-field error on that field.
- Given: A SUPERADMIN submits with `short_name='lrh'`. When: The form saves. Then: `Institution.short_name` is stored as `'LRH'` (auto-uppercased by `clean_institution_short_name`).

**AC-3: Superadmin can edit any institution**
- Given: A SUPERADMIN on the Institution Selector (`/institution/`). When: They click the Edit button on any institution card (active or inactive). Then: They are navigated to `/institution/edit/<pk>/` and the edit form loads with pre-filled values.
- Given: SUPERADMIN submits the edit form with valid data. When: Save succeeds. Then: The institution's name, short_name, logo, is_active, and subscription_status are updated; user is redirected to the selector with a success message.
- Given: An ADMIN user (user_type='ADMIN'). When: They navigate directly to `/institution/edit/<pk>/`. Then: They are redirected to `manage-patients` (not a 403 or 500).
- Given: A plain USER (user_type='USER'). When: They navigate to `/institution/edit/<pk>/`. Then: Redirected to `manage-patients`.
- Given: An anonymous (unauthenticated) user. When: They navigate to `/institution/edit/<pk>/`. Then: `@login_required` redirects them to the login page (not `manage-patients`).
- Given: SUPERADMIN on an inactive institution's edit form. When: They set `is_active=True` and save. Then: The institution is reactivated successfully.

**AC-4: Brand slot shows short_name with tooltip**
- Given: An authenticated user with an active institution that has a `short_name`. When: Any page loads. Then: The sidebar brand-text shows `short_name` (e.g., "LRH"), not the full name.
- Given: An institution whose `short_name` is empty (edge case). When: Sidebar loads. Then: Brand-text falls back to the first 10 chars of the full name.
- Given: A user hovers over the sidebar brand-link. When: Tooltip appears. Then: The tooltip shows the full institution name and is rendered via Bootstrap tooltip (not the browser native title tooltip), positioned to the right.
- Given: An institution with no logo. When: Sidebar loads. Then: The initial-letter badge still shows and the brand-text shows `short_name`.

**AC-5: Sidebar Administration gate**
- Given: A plain USER (user_type='USER'). When: They view any authenticated page. Then: The Administration collapsible is NOT present in the sidebar HTML.
- Given: An ADMIN user (user_type='ADMIN'). When: They view any page. Then: Administration collapsible IS visible and contains: Staff Dashboard, Users, Add User, Activity Logs, a "MY INSTITUTION" sub-header, Admin Dashboard, Institution Settings, Clinicians. The NETWORK sub-section is NOT present.
- Given: A SUPERADMIN. When: They view any page. Then: Administration contains the shared items AND the "NETWORK" sub-header with All Institutions, Add Institution, Superadmin Dashboard, Aggregate Reports. The "MY INSTITUTION" sub-section is NOT present.
- Given: An ADMIN navigates to Institution Settings (`/institution/settings/`). When: The page loads. Then: The Administration collapsible is open (menu-open class applied) because `'institution-settings' in request.resolver_match.url_name`.

**AC-6: Reports section gate**
- Given: A plain USER. When: They view any page. Then: The Reports section is NOT visible in the sidebar HTML.
- Given: An ADMIN or SUPERADMIN. When: They view any page. Then: Reports IS visible with "Generate Report" and "Report History" links.

**AC-7: MY INSTITUTION orphan section removed**
- Given: An ADMIN user. When: They view any page. Then: There is NO standalone `nav-header` labelled "MY INSTITUTION" outside the Administration collapsible. All institution-admin links appear only inside the Administration treeview.

**AC-8: Video isolation**
- Given: User A (Institution A). When: They directly navigate to `/video/view/<id>/` using a video ID that belongs to Institution B. Then: They receive a 404.
- Given: Same cross-institution attack. When: Attempted against `/video/edit/<id>/`, `/video/delete-confirm/<id>/`, or `/video/delete/<id>/`. Then: All return 404.
- Given: User A navigates to a video that belongs to their own institution. When: Page loads. Then: Video is accessible normally (no regression).

**AC-9: Problem isolation**
- Given: User A (Institution A). When: They navigate to a Problem record (view/edit/delete/status-change/timeline) using a pk from Institution B. Then: 404.
- Given: User A navigates to `/problem/patient/<pid>/` using a Patient pk from Institution B. Then: 404.
- Given: User A accesses their own institution's Problem records. Then: Normal access (no regression).

**AC-10: Assessment + Bookmark + Attachment isolation**
- Given: User A. When: They directly access a GMAssessment, HINEAssessment, DevelopmentalAssessment, CDICRecord, or GeneralPaediatricAssessment by PK from Institution B. Then: 404.
- Given: User A. When: They view the Bookmark manager. Then: Only bookmarks with `owner__institution == Institution A` appear; Institution B bookmarks are absent.
- Given: User A. When: They access a Bookmark by pk from Institution B. Then: 404.
- Given: User A. When: They access an Attachment (view/edit/delete) by pk from Institution B. Then: 404.
- Given: User A. When: They view assessment manager lists (GM, HINE, DA, GPA, CDIC). Then: Only assessments for Institution A patients appear.

## Additional Context

### Dependencies

- **Task 1 must complete before Tasks 2–7**: `short_name` field must exist in the DB before forms can save it, and before the sidebar template can reference `active_institution.short_name`.
- **Task 2 must complete before Task 3**: Views reference form classes.
- **Task 3 + 4 must complete before Task 5c/5d**: Selector template links to `superadmin-institution-edit` URL which must exist.
- **Tasks 8–10 are independent**: Can be done in any order relative to Tasks 1–7, and in parallel with each other.

### Testing Strategy

- **Migrate**: `python manage.py migrate` — confirm zero errors; existing institutions have `short_name` populated.
- **Makemigrations check**: `python manage.py makemigrations --check` — no pending migrations.
- **Manual role gate test**:
  - Login as USER → no Administration in sidebar, no Reports.
  - Login as ADMIN → Administration visible with MY INSTITUTION sub-section; standalone MY INSTITUTION section absent.
  - Login as SUPERADMIN → Administration visible with NETWORK sub-section.
- **Manual brand test**: Login as any user → brand-text shows `short_name`; hover → Bootstrap tooltip shows full name.
- **Manual isolation test**: Create Institution A and Institution B (or use existing). Login as User of Institution A. Navigate directly to a video, problem, assessment URL from Institution B using a known ID → confirm 404 response.
- **Regression**: `python manage.py test` — all existing tests pass.

### Notes

- All assessment views (GM, HINE, DA, GPA, CDIC) live in `patients/views.py` (3600+ lines) — not separate app view files. The fixes are mechanical but numerous.
- The existing `institution_settings` view at line 808 already allows SUPERADMIN to edit the active-context institution. The new `superadmin_institution_edit` view complements it by allowing edit-by-explicit-pk without requiring context switching.
- `data-container="body"` on the brand-link tooltip prevents AdminLTE sidebar overflow-hidden from clipping the tooltip popup.
- Bookmark model uses `owner` FK (confirmed at `patients/models.py:2010`) — all Bookmark isolation fixes use `owner__institution`, not `added_by__institution`.
- The `added_by` permission checks in `video_view` and `video_edit` (lines 115, 159) are NOT removed by Task 8 — they control intra-institution record ownership and remain valid.
- Referral frozen snapshots are the only legitimate cross-institution access path; they are not touched by any of these fixes.

## Review Notes

- Adversarial review completed (Step 5): 18 findings total
- Resolution approach: Auto-fix [F]
- Findings fixed (6): F1, F2, F3, F4, F5, F7
- Findings skipped (12): F6 (audit log — feature gap), F8 (media protection — complex), F9 (mitigated by middleware), F10–F18 (medium/low priority)
- Key fix: Added `institution_scope()` helper to `ndas/custom_codes/custom_methods.py` — replaces all `patient__institution=getattr(request, 'institution', None)` patterns with a Phase-1-safe conditional filter (returns `{}` when institution is None, avoiding NULL-filter bug)
- Also fixed: `attachment_manager` institution scoping (F2), bookmark_add item validation (F4), uploaders dropdown isolation (F5), `clean_name()` in both settings forms (F7)
