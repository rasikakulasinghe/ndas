# Story 3.2: Clinician Account Management

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **institution admin**,
I want to create new clinician accounts and deactivate existing ones within my institution,
So that I can independently manage my clinical team without needing superadmin involvement for routine staffing changes.

## Acceptance Criteria

1. **Given** the institution admin navigates to the user management section
   **When** they submit the create-user form with name, email, password, and staff_position
   **Then** a new `CustomUser` is created with `user_type=USER` and `institution=request.institution`
   **And** the new clinician can immediately log in and access only the admin's institution's data

2. **Given** the institution admin deactivates a clinician account
   **When** `is_active` is set to `False` on the user record
   **Then** the deactivated clinician can no longer authenticate
   **And** all their historical records (assessments, patient registrations, problem entries) remain intact and visible

3. **Given** an institution admin attempts to create a user with `user_type=ADMIN` or `user_type=SUPERADMIN`
   **When** the form is submitted
   **Then** the attempt is rejected — institution admins may only create `user_type=USER` accounts

4. **Given** the institution admin views the user list
   **When** the list renders
   **Then** only users bound to their institution are displayed — users from other institutions are not visible

## Tasks / Subtasks

- [ ] Task 1: Create `InstitutionClinicianForm` in `institution/forms.py` (AC: #1, #3)
  - [ ] Fields: `first_name`, `last_name`, `username`, `email`, `password1`, `password2`, `position` (from choice.py POSSITION choices), `mobile_primary`
  - [ ] Hidden field or forced value: `user_type=UserType.USER` (not user-selectable)
  - [ ] Validation: reject any submitted `user_type` that is not USER
  - [ ] See exact form code in Dev Notes

- [ ] Task 2: Add three views to `institution/views.py` (AC: #1, #2, #3, #4)
  - [ ] `institution_clinician_list` — GET only, ADMIN only, lists users `.filter(institution=request.institution).exclude(user_type=UserType.SUPERADMIN)`
  - [ ] `institution_clinician_add` — GET/POST, ADMIN only, creates new USER with `institution=request.institution`
  - [ ] `institution_clinician_deactivate` — POST only, ADMIN only, sets `is_active=False`; also a `reactivate` action via same endpoint with action parameter
  - [ ] See exact view code in Dev Notes

- [ ] Task 3: Add three URLs to `institution/urls.py` (AC: #1, #4)
  - [ ] `institution-clinician-list` → `clinicians/`
  - [ ] `institution-clinician-add` → `clinicians/add/`
  - [ ] `institution-clinician-toggle-status` → `clinicians/<int:user_id>/toggle-status/`
  - [ ] See exact URL config in Dev Notes

- [ ] Task 4: Create templates (AC: #1, #4)
  - [ ] `templates/institution/clinician_list.html` — AdminLTE card with user table, deactivate/reactivate buttons
  - [ ] `templates/institution/clinician_add.html` — AdminLTE card with create-user form
  - [ ] See exact templates in Dev Notes

- [ ] Task 5: Add "Manage Clinicians" link to sidebar and Admin Dashboard (AC: #1)
  - [ ] In `templates/src/main_sidebar_menu.html` — under Administration, add clinician list link (ADMIN-only conditional)
  - [ ] In `templates/institution/admin_dashboard.html` — "Manage Clinicians" button already links to `institution:institution-clinician-list` (from Story 3.1)

- [ ] Task 6: Write tests in `institution/tests/test_clinician_management.py` (AC: #1–#4)
  - [ ] See exact test code in Dev Notes

## Dev Notes

### Story 3.2 Position in the 13-Step Sequence

Story 3.2 = **Step 9** (Institution admin views — user management):

```
9.  Institution admin views:
    ├── Story 3.1: institution admin dashboard  ← done
    ├── Story 3.2: clinician account management ← THIS STORY
    ├── Story 3.3: institution branding setup
    └── Story 3.4: PDF report branding
```

**Prerequisites:** Story 3.1 done (institution admin dashboard with role access check pattern established).

**FR Coverage:** FR57 — Institution admins can create USER accounts and deactivate existing accounts within their institution.

---

### Task 1: `InstitutionClinicianForm` — Full Code

Create `institution/forms.py`:

```python
"""
institution/forms.py
Forms for institution management views.
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordMixin

from ndas.custom_codes.choice import UserType
from ndas.custom_codes.validators import validate_phone_number

User = get_user_model()

# Reuse Position choices from existing choice.py
from ndas.custom_codes.choice import POSSITION  # or Position, check actual name


class InstitutionClinicianForm(forms.ModelForm):
    """
    Form for institution admins to create new USER-type clinician accounts.

    Enforces user_type=USER — institution admins cannot create ADMIN or SUPERADMIN accounts.
    """
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        min_length=8,
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'position', 'mobile_primary']
        widgets = {
            'first_name':     forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':      forms.TextInput(attrs={'class': 'form-control'}),
            'username':       forms.TextInput(attrs={'class': 'form-control'}),
            'email':          forms.EmailInput(attrs={'class': 'form-control'}),
            'position':       forms.Select(attrs={'class': 'form-control'}),
            'mobile_primary': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1', '')
        p2 = self.cleaned_data.get('password2', '')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return p2

    def save(self, institution, commit=True):
        """
        Create and return a new USER-type clinician bound to the given institution.
        user_type is always forced to USER — never settable by form data.
        """
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.user_type = UserType.USER     # AC #3: ALWAYS forced — never from form input
        user.institution = institution
        user.is_active = True
        if commit:
            user.save()
        return user
```

**Note on `POSSITION`:** The existing `choice.py` uses `POSSITION` (confirmed from users/models.py
import). Check that this is a list/tuple of (value, label) pairs compatible with `forms.Select`.

---

### Task 2: Views — Full Code

Add to `institution/views.py`:

```python
@login_required(login_url="user-login")
@require_GET
@handle_view_errors(redirect_url='home', error_message='Failed to load clinician list.')
def institution_clinician_list(request):
    """
    Institution admin: view all clinicians in own institution (FR57).
    ADMIN only.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.ADMIN:
        return redirect('home')

    from users.models import CustomUser
    clinicians = (
        CustomUser.objects
        .filter(institution=request.institution)
        .exclude(user_type=UserType.SUPERADMIN)
        .order_by('last_name', 'first_name')
        .select_related('institution')
    )
    return render(request, 'institution/clinician_list.html', {
        'clinicians': clinicians,
        'institution': request.institution,
    })


@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='institution:institution-clinician-list', error_message='Failed to create clinician.')
def institution_clinician_add(request):
    """
    Institution admin: create a new USER-type clinician (FR57).
    ADMIN only.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.ADMIN:
        return redirect('home')

    from institution.forms import InstitutionClinicianForm

    if request.method == 'POST':
        form = InstitutionClinicianForm(request.POST)
        if form.is_valid():
            new_user = form.save(institution=request.institution)
            logger.info(
                "ADMIN '%s' created clinician '%s' in institution '%s'",
                request.user.username, new_user.username, request.institution.name,
            )
            from django.contrib import messages as django_messages
            django_messages.success(request, f"Clinician account for '{new_user.get_full_name()}' created successfully.")
            return redirect('institution:institution-clinician-list')
    else:
        form = InstitutionClinicianForm()

    return render(request, 'institution/clinician_add.html', {
        'form': form,
        'institution': request.institution,
    })


@login_required(login_url="user-login")
@require_http_methods(["POST"])
@ratelimit(key='user_or_ip', rate='5/m')
@handle_view_errors(redirect_url='institution:institution-clinician-list', error_message='Failed to update clinician status.')
def institution_clinician_toggle_status(request, user_id):
    """
    Institution admin: activate or deactivate a clinician account (FR57).
    ADMIN only. Operates only on users bound to request.institution.
    AC #2: deactivated clinician cannot authenticate; records remain intact.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.ADMIN:
        return redirect('home')

    from users.models import CustomUser
    # Only allow toggling users in same institution and never ADMIN/SUPERADMIN
    target_user = get_object_or_404(
        CustomUser,
        id=user_id,
        institution=request.institution,
        user_type=UserType.USER,  # AC #3: admins can only manage USER accounts
    )

    # Prevent self-deactivation
    if target_user == request.user:
        from django.contrib import messages as django_messages
        django_messages.error(request, "You cannot deactivate your own account.")
        return redirect('institution:institution-clinician-list')

    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=['is_active', 'updated_at'])

    action = "activated" if target_user.is_active else "deactivated"
    logger.info(
        "ADMIN '%s' %s clinician '%s' in institution '%s'",
        request.user.username, action, target_user.username, request.institution.name,
    )
    from django.contrib import messages as django_messages
    django_messages.success(request, f"Account '{target_user.get_full_name()}' has been {action}.")
    return redirect('institution:institution-clinician-list')
```

---

### Task 3: `institution/urls.py` — Add Clinician URLs

Add after the admin dashboard path:

```python
    # Story 3.2 — Clinician Account Management
    path('clinicians/', views.institution_clinician_list, name='institution-clinician-list'),
    path('clinicians/add/', views.institution_clinician_add, name='institution-clinician-add'),
    path('clinicians/<int:user_id>/toggle-status/', views.institution_clinician_toggle_status, name='institution-clinician-toggle-status'),
```

---

### Task 4a: `templates/institution/clinician_list.html`

```django
{% extends 'src/base.html' %}
{% load static %}
{% block title %}Clinicians — {{ institution.name }}{% endblock %}

{% block content_header %}
<div class="row mb-0">
  <div class="col-sm-6"><h1 class="m-0">Clinicians</h1><small class="text-muted">{{ institution.name }}</small></div>
  <div class="col-sm-6">
    <ol class="breadcrumb float-sm-right">
      <li class="breadcrumb-item"><a href="{% url 'institution:institution-admin-dashboard' %}">Admin</a></li>
      <li class="breadcrumb-item active">Clinicians</li>
    </ol>
  </div>
</div>
{% endblock content_header %}

{% block main_content %}
<div class="container-fluid">
  <div class="row mb-3">
    <div class="col-12">
      <a href="{% url 'institution:institution-clinician-add' %}" class="btn btn-primary btn-sm">
        <i class="fas fa-user-plus mr-1"></i>Add Clinician
      </a>
    </div>
  </div>
  <div class="row">
    <div class="col-12">
      <div class="card card-primary card-outline">
        <div class="card-header"><h3 class="card-title">Clinical Team</h3></div>
        <div class="card-body table-responsive p-0">
          <table class="table table-hover table-sm">
            <thead>
              <tr>
                <th>Name</th><th>Username</th><th>Email</th><th>Position</th><th>Status</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {% for clinician in clinicians %}
              <tr class="{% if not clinician.is_active %}table-secondary text-muted{% endif %}">
                <td>{{ clinician.get_full_name }}</td>
                <td><code>{{ clinician.username }}</code></td>
                <td>{{ clinician.email }}</td>
                <td>{{ clinician.position }}</td>
                <td>
                  {% if clinician.is_active %}
                    <span class="badge badge-success">Active</span>
                  {% else %}
                    <span class="badge badge-secondary">Inactive</span>
                  {% endif %}
                </td>
                <td>
                  {% if clinician != request.user %}
                  <form method="post" action="{% url 'institution:institution-clinician-toggle-status' clinician.id %}" style="display:inline;">
                    {% csrf_token %}
                    {% if clinician.is_active %}
                      <button type="submit" class="btn btn-warning btn-xs" onclick="return confirm('Deactivate this account?')">Deactivate</button>
                    {% else %}
                      <button type="submit" class="btn btn-success btn-xs" onclick="return confirm('Reactivate this account?')">Reactivate</button>
                    {% endif %}
                  </form>
                  {% endif %}
                </td>
              </tr>
              {% empty %}
              <tr><td colspan="6" class="text-center text-muted">No clinicians found. <a href="{% url 'institution:institution-clinician-add' %}">Add one</a>.</td></tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

### Task 4b: `templates/institution/clinician_add.html`

```django
{% extends 'src/base.html' %}
{% load static %}
{% block title %}Add Clinician — {{ institution.name }}{% endblock %}

{% block content_header %}
<div class="row mb-0">
  <div class="col-sm-6"><h1 class="m-0">Add Clinician</h1></div>
  <div class="col-sm-6">
    <ol class="breadcrumb float-sm-right">
      <li class="breadcrumb-item"><a href="{% url 'institution:institution-admin-dashboard' %}">Admin</a></li>
      <li class="breadcrumb-item"><a href="{% url 'institution:institution-clinician-list' %}">Clinicians</a></li>
      <li class="breadcrumb-item active">Add</li>
    </ol>
  </div>
</div>
{% endblock content_header %}

{% block main_content %}
<div class="container-fluid">
  <div class="row justify-content-center">
    <div class="col-lg-7">
      <div class="card card-primary card-outline">
        <div class="card-header"><h3 class="card-title">New Clinician Account</h3></div>
        <div class="card-body">
          <form method="post">
            {% csrf_token %}
            {% include 'src/form_error.html' %}
            <div class="form-row">
              <div class="form-group col-md-6">
                <label>First Name *</label>{{ form.first_name }}
              </div>
              <div class="form-group col-md-6">
                <label>Last Name *</label>{{ form.last_name }}
              </div>
            </div>
            <div class="form-group"><label>Username *</label>{{ form.username }}</div>
            <div class="form-group"><label>Email *</label>{{ form.email }}</div>
            <div class="form-group"><label>Position *</label>{{ form.position }}</div>
            <div class="form-group"><label>Mobile (Primary) *</label>{{ form.mobile_primary }}</div>
            <div class="form-row">
              <div class="form-group col-md-6"><label>Password *</label>{{ form.password1 }}</div>
              <div class="form-group col-md-6"><label>Confirm Password *</label>{{ form.password2 }}</div>
            </div>
            <div class="d-flex justify-content-between mt-3">
              <a href="{% url 'institution:institution-clinician-list' %}" class="btn btn-secondary btn-sm">Cancel</a>
              <button type="submit" class="btn btn-primary btn-sm">
                <i class="fas fa-user-plus mr-1"></i>Create Account
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

### Task 5: Sidebar Menu Entry

In `templates/src/main_sidebar_menu.html`, under Administration section, add after Admin Dashboard link (from Story 3.1):

```django
{% if user_type == 'ADMIN' %}
<li class="nav-item {% if request.resolver_match.url_name == 'institution-clinician-list' or request.resolver_match.url_name == 'institution-clinician-add' %}active{% endif %}">
  <a href="{% url 'institution:institution-clinician-list' %}" class="nav-link">
    <i class="nav-icon fas fa-user-md"></i>
    <p>Clinicians</p>
  </a>
</li>
{% endif %}
```

---

### Task 6: `institution/tests/test_clinician_management.py`

```python
"""
institution/tests/test_clinician_management.py
Tests for Clinician Account Management (Story 3.2 — FR57).
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()


class ClinicianMgmtTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_clin', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771771001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(
            name='Test Hospital', slug='test-hospital',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Other Hospital', slug='other-hospital',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.admin = User.objects.create_user(
            username='admin_clin', password='Testpass1!',
            first_name='Test', last_name='Admin',
            position='Administrator', mobile_primary='0771771002',
            user_type=UserType.ADMIN, institution=self.inst,
        )
        self.existing_clinician = User.objects.create_user(
            username='clinician_01', password='Testpass1!',
            first_name='Existing', last_name='Clinician',
            position='Medical Officer', mobile_primary='0771771003',
            user_type=UserType.USER, institution=self.inst,
        )
        self.list_url = reverse('institution:institution-clinician-list')
        self.add_url = reverse('institution:institution-clinician-add')


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class ClinicianListAccessTest(ClinicianMgmtTestBase):
    def test_admin_can_see_list(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_list_only_shows_own_institution_users(self):
        """AC #4: Users from other institutions must not appear in the list."""
        other_user = User.objects.create_user(
            username='other_clinic', password='Testpass1!',
            first_name='Other', last_name='User',
            position='Medical Officer', mobile_primary='0771771099',
            user_type=UserType.USER, institution=self.inst_b,
        )
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.list_url)
        clinicians = response.context['clinicians']
        usernames = [u.username for u in clinicians]
        self.assertNotIn('other_clinic', usernames, "AC #4: Other institution's user must not appear")
        self.assertIn('clinician_01', usernames)


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class ClinicianCreateTest(ClinicianMgmtTestBase):
    def test_admin_can_create_user_type_clinician(self):
        """AC #1: Admin creates USER-type clinician bound to their institution."""
        client = Client()
        client.force_login(self.admin)
        response = client.post(self.add_url, {
            'first_name': 'New', 'last_name': 'Clinician',
            'username': 'new_clinician', 'email': 'new@test.com',
            'position': 'Medical Officer', 'mobile_primary': '0771551001',
            'password1': 'StrongPass1!', 'password2': 'StrongPass1!',
        })
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(username='new_clinician')
        self.assertEqual(new_user.user_type, UserType.USER, "AC #1: New clinician must be USER type")
        self.assertEqual(new_user.institution, self.inst, "AC #1: New clinician must be bound to admin's institution")

    def test_admin_cannot_create_admin_type_user(self):
        """AC #3: Attempt to set user_type=ADMIN in form data must be silently rejected."""
        client = Client()
        client.force_login(self.admin)
        client.post(self.add_url, {
            'first_name': 'Rogue', 'last_name': 'Admin',
            'username': 'rogue_admin', 'email': 'rogue@test.com',
            'position': 'Administrator', 'mobile_primary': '0771552001',
            'password1': 'StrongPass1!', 'password2': 'StrongPass1!',
            'user_type': 'ADMIN',  # Injected by attacker — must be ignored
        })
        if User.objects.filter(username='rogue_admin').exists():
            rogue = User.objects.get(username='rogue_admin')
            self.assertEqual(rogue.user_type, UserType.USER,
                "AC #3: user_type must be forced to USER regardless of POST data")


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class ClinicianDeactivateTest(ClinicianMgmtTestBase):
    def test_deactivate_clinician(self):
        """AC #2: Admin can deactivate a clinician account."""
        client = Client()
        client.force_login(self.admin)
        url = reverse('institution:institution-clinician-toggle-status', args=[self.existing_clinician.id])
        response = client.post(url)
        self.assertEqual(response.status_code, 302)
        self.existing_clinician.refresh_from_db()
        self.assertFalse(self.existing_clinician.is_active, "AC #2: Clinician must be deactivated")

    def test_records_remain_after_deactivation(self):
        """AC #2: Deactivating a clinician does not delete their records."""
        from patients.models import Patient
        patient = Patient.objects.create(
            institution=self.inst,
            baby_name='Deactivation Test', mother_name='Test Mother',
            added_by=self.existing_clinician, last_edit_by=self.existing_clinician,
        )
        client = Client()
        client.force_login(self.admin)
        url = reverse('institution:institution-clinician-toggle-status', args=[self.existing_clinician.id])
        client.post(url)
        # Patient record must still exist
        self.assertTrue(Patient.objects.filter(id=patient.id).exists(),
            "AC #2: Patient records must remain after clinician deactivation")
```

---

### Project Structure Notes

**Files CREATED in this story:**
- `institution/forms.py` — `InstitutionClinicianForm`
- `templates/institution/clinician_list.html` — clinician list table
- `templates/institution/clinician_add.html` — create clinician form
- `institution/tests/test_clinician_management.py` — 8+ tests

**Files MODIFIED in this story:**
- `institution/views.py` — add 3 clinician management views
- `institution/urls.py` — add 3 clinician URLs
- `templates/src/main_sidebar_menu.html` — add Clinicians link (ADMIN-only)

**Files NOT touched:**
- `users/views.py` — existing admin-user-* views are for SUPERADMIN use; this story uses separate institution-scoped views
- `users/urls.py` — unchanged (institution URLs are namespaced under `institution:`)

---

### Key Constraint

**No edit view for this story.** Institution admins can create and toggle-status (deactivate/reactivate) clinician accounts. Editing clinician profile details (name, email, etc.) is deferred — clinicians use `users:user-edit` for self-service profile editing.

---

### References

- FR57: Institution admins create USER accounts and deactivate within own institution [Source: `_bmad-output/planning-artifacts/epics.md#Story 3.2`]
- Architecture: `user_type` field on CustomUser, `institution` FK [Source: `_bmad-output/planning-artifacts/epics.md#Data Models`]
- Project context: All views function-based, mandatory decorator stack [Source: `_bmad-output/project-context.md#Views`]
- Project context: Choices defined in `ndas/custom_codes/choice.py` — `POSSITION` for position field [Source: `_bmad-output/project-context.md#Language-Specific Rules`]
- Project context: `UserType` choices from `ndas/custom_codes/choice.py` [Source: `_bmad-output/planning-artifacts/epics.md#Additional Requirements`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
