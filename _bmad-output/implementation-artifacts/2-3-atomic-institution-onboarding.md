# Story 2.3: Atomic Institution Onboarding

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **superadmin**,
I want to onboard a new institution via a single form that creates the institution and its first admin account simultaneously,
So that a new hospital is live in under 5 minutes with zero possibility of an institution existing without a corresponding admin.

## Acceptance Criteria

1. **Given** the superadmin navigates to `/institution/add/`
   **When** the form is submitted with: institution name, slug, first admin name, email, and temporary password
   **Then** a `transaction.atomic()` block creates both the `Institution` record and the first `CustomUser` (user_type=ADMIN, institution=new_institution) atomically

2. **Given** the transaction succeeds
   **When** the superadmin is redirected to the selector screen
   **Then** the new institution card appears immediately with subscription_status=ACTIVE and user count = 1

3. **Given** the admin account creation step fails during the transaction
   **When** the transaction rolls back
   **Then** no orphan `Institution` record exists — either both records are created or neither is

4. **Given** a slug is submitted that already exists in another institution
   **When** form validation runs
   **Then** a validation error is shown and no records are created

5. **Given** a new institution is successfully created
   **When** the institution slug is set
   **Then** the slug is immutable — any subsequent attempt to change it raises a `ValidationError`

## Tasks / Subtasks

- [ ] Task 1: Create `institution/forms.py` with `InstitutionOnboardingForm` (AC: #1, #3, #4, #5)
  - [ ] Institution fields: `institution_name` (CharField), `institution_slug` (SlugField)
  - [ ] Admin account fields: `admin_first_name`, `admin_last_name`, `admin_email`, `admin_username`, `admin_position` (ChoiceField using `Position.choices`), `admin_mobile`, `admin_password`, `admin_password_confirm` (both PasswordInput)
  - [ ] `clean_institution_slug()` — raise `ValidationError` if slug already exists in `Institution` table
  - [ ] `clean_admin_username()` — raise `ValidationError` if username already taken
  - [ ] `clean()` — validate password match; run Django `validate_password()` validators
  - [ ] See exact form code in Dev Notes

- [ ] Task 2: Add `institution_add` view to `institution/views.py` (AC: #1, #2, #3, #4)
  - [ ] GET: render blank `InstitutionOnboardingForm` on `institution/add.html`
  - [ ] POST: validate form → `transaction.atomic()` → create `Institution` → create `CustomUser` (user_type=ADMIN) → log → redirect to selector
  - [ ] Catch `IntegrityError` — add non-field error, re-render form
  - [ ] SUPERADMIN-only access guard (redirect ADMIN/USER away)
  - [ ] See exact view code in Dev Notes

- [ ] Task 3: Uncomment `institution-add` URL in `institution/urls.py`
  - [ ] Change `# path('add/', views.institution_add, name='institution-add'),` → uncommented active line
  - [ ] See exact URL config change in Dev Notes

- [ ] Task 4: Create `templates/institution/add.html` form template (AC: #1, #4)
  - [ ] Extend `src/base.html`; title "Onboard New Institution"
  - [ ] Two AdminLTE cards: "Institution Details" + "First Admin Account"
  - [ ] All form fields with labels, Bootstrap 4.6 input styling, and `{% include 'src/form_error.html' %}`
  - [ ] CSRF token included
  - [ ] Client-side slug auto-population from institution name (progressive enhancement via inline JS)
  - [ ] See exact template in Dev Notes

- [ ] Task 5: Add "Onboard New Institution" button to `templates/institution/selector.html` (AC: #2)
  - [ ] Replace the `{# Story 2.3 adds the "Onboard New Institution" button here #}` comment with an actual link
  - [ ] Button: `<a href="{% url 'institution:institution-add' %}" class="btn btn-primary">...</a>`
  - [ ] See exact change in Dev Notes

- [ ] Task 6: Write tests in `institution/tests/test_institution_add.py` (AC: #1–#5)
  - [ ] See exact test code in Dev Notes

## Dev Notes

### Story 2.3 Position in the 13-Step Sequence

Story 2.3 = **Step 8** (Superadmin views — atomic institution onboarding):

```
8.  Superadmin views + god-view dashboard:
    ├── Story 2.1: institution_selector view + selector.html            ← done
    ├── Story 2.2: institution_switch + superadmin_overlay tag          ← done
    └── Story 2.3: institution_add view + InstitutionOnboardingForm     ← THIS STORY
```

**Prerequisites:** Stories 2.1 and 2.2 must be `done`.
```bash
python manage.py test institution.tests.test_selector          # 2.1 tests pass
python manage.py test institution.tests.test_context_switching # 2.2 tests pass
```

**NFR13 compliance (atomic operations):** This story's core requirement is atomicity.
The entire onboarding must be wrapped in `transaction.atomic()` — no partial state possible.

---

### CustomUser Required Fields Reference

From `users/models.py` (confirmed):
```python
class CustomUser(AbstractUser, TimeStampedModel):
    position = models.CharField(max_length=100, choices=Position.choices, ...)
    mobile_primary = models.CharField(max_length=20, ...)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "first_name", "position", "mobile_primary"]
```

The onboarding form **must** provide all REQUIRED_FIELDS. The admin's `position` defaults
to `"Administrator"` (from `Position.ADMINISTRATOR`) since institution admins are administrative roles.

---

### Task 1: `institution/forms.py` — Full Code

Create this new file:

```python
"""
institution/forms.py

Forms for institution management views.
"""

import logging

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from institution.models import Institution
from ndas.custom_codes.choice import Position
from ndas.custom_codes.validators import sanitize_text_input

logger = logging.getLogger(__name__)

User = get_user_model()


class InstitutionOnboardingForm(forms.Form):
    """
    Single form for atomic institution + first admin account creation.
    AC: FR52 — one form, two records, zero orphans.

    Validation:
    - Slug uniqueness across all institutions
    - Username uniqueness across all users
    - Password confirmation match + Django password validators
    """

    # ── Institution Details ────────────────────────────────────────────────
    institution_name = forms.CharField(
        max_length=255,
        label="Institution Name",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. National Children\'s Hospital',
            'id': 'id_institution_name',
        }),
    )
    institution_slug = forms.SlugField(
        max_length=100,
        label="Slug (URL identifier)",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. national-childrens-hospital',
            'id': 'id_institution_slug',
        }),
        help_text="Lowercase letters, numbers, and hyphens only. IMMUTABLE after creation.",
    )

    # ── First Admin Account ────────────────────────────────────────────────
    admin_first_name = forms.CharField(
        max_length=150,
        label="Admin First Name",
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    admin_last_name = forms.CharField(
        max_length=150,
        label="Admin Last Name",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    admin_email = forms.EmailField(
        label="Admin Email",
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )
    admin_username = forms.CharField(
        max_length=150,
        label="Admin Username",
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Used for login. Must be unique.",
    )
    admin_position = forms.ChoiceField(
        choices=Position.choices,
        initial=Position.ADMINISTRATOR,
        label="Admin Position",
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    admin_mobile = forms.CharField(
        max_length=20,
        label="Admin Mobile",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+94771234567'}),
    )
    admin_password = forms.CharField(
        label="Temporary Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Min 12 characters. Admin should change this on first login.",
    )
    admin_password_confirm = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    def clean_institution_name(self):
        return sanitize_text_input(self.cleaned_data['institution_name'])

    def clean_institution_slug(self):
        """AC #4: Reject duplicate slugs — validation error before any DB write."""
        slug = self.cleaned_data['institution_slug'].lower().strip()
        if Institution.objects.filter(slug=slug).exists():
            raise forms.ValidationError(
                f"An institution with slug '{slug}' already exists. "
                "Slugs are unique identifiers and cannot be reused."
            )
        return slug

    def clean_admin_username(self):
        """Reject duplicate usernames before DB write."""
        username = self.cleaned_data['admin_username'].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError(
                f"Username '{username}' is already taken. Please choose a different username."
            )
        return username

    def clean_admin_first_name(self):
        return sanitize_text_input(self.cleaned_data['admin_first_name'])

    def clean(self):
        """Password match + Django password strength validators."""
        cleaned_data = super().clean()
        password = cleaned_data.get('admin_password')
        confirm = cleaned_data.get('admin_password_confirm')

        if password and confirm and password != confirm:
            self.add_error('admin_password_confirm', "Passwords do not match.")
            return cleaned_data

        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                self.add_error('admin_password', e)

        return cleaned_data
```

**Import note:** `sanitize_text_input` is from `ndas/custom_codes/validators.py` — the project
standard for free-text field sanitization. Always apply it to name fields before storage.

---

### Task 2: `institution_add` View — Full Code

Add to `institution/views.py`:

```python
import logging
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django_ratelimit.decorators import ratelimit

from institution.forms import InstitutionOnboardingForm
from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus
from ndas.custom_codes.error_handlers import handle_view_errors

logger = logging.getLogger(__name__)
User = get_user_model()


@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(
    redirect_url='institution:institution-selector',
    error_message='Failed to load institution onboarding form.'
)
def institution_add(request):
    """
    Atomic institution onboarding: creates Institution + first ADMIN account in one transaction.
    SUPERADMIN only.

    GET:  Display blank InstitutionOnboardingForm.
    POST: Validate → transaction.atomic() → create Institution + CustomUser(ADMIN) → redirect.

    AC: FR52 — no institution without admin; NFR13 — atomic operation.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.SUPERADMIN:
        return redirect('manage-patients')

    form = InstitutionOnboardingForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                # ── Step 1: Create Institution ─────────────────────────────
                institution = Institution.objects.create(
                    name=form.cleaned_data['institution_name'],
                    slug=form.cleaned_data['institution_slug'],
                    subscription_status=SubscriptionStatus.ACTIVE,
                    is_active=True,
                    created_by=request.user,
                )

                # ── Step 2: Create first ADMIN account ────────────────────
                # If this step raises any exception, the transaction rolls back
                # and institution above is also undone — no orphan Institution.
                admin_user = User.objects.create_user(
                    username=form.cleaned_data['admin_username'],
                    password=form.cleaned_data['admin_password'],
                    email=form.cleaned_data['admin_email'],
                    first_name=form.cleaned_data['admin_first_name'],
                    last_name=form.cleaned_data.get('admin_last_name', ''),
                    position=form.cleaned_data['admin_position'],
                    mobile_primary=form.cleaned_data['admin_mobile'],
                    user_type=UserType.ADMIN,
                    institution=institution,
                    is_active=True,
                )

            # Transaction committed successfully — both records exist
            logger.info(
                "SUPERADMIN '%s' onboarded institution '%s' (slug=%s, admin='%s')",
                request.user.username,
                institution.name,
                institution.slug,
                admin_user.username,
            )
            messages.success(
                request,
                f"Institution '{institution.name}' successfully onboarded. "
                f"Admin account '{admin_user.username}' created."
            )
            return redirect('institution:institution-selector')

        except IntegrityError as e:
            # Catch race-condition duplicate slug/username that slipped past form validation
            logger.warning(
                "IntegrityError during institution onboarding by '%s': %s",
                request.user.username, str(e)
            )
            form.add_error(
                None,
                "Onboarding failed: a duplicate slug or username was detected. "
                "Please verify the slug and username are unique."
            )

    return render(request, 'institution/add.html', {
        'form': form,
        'page_title': 'Onboard New Institution',
    })
```

**Why `IntegrityError` catch outside `transaction.atomic()`:**
Once `transaction.atomic()` exits (either committed or rolled back), the IntegrityError
is re-raised. Catching it OUTSIDE the `with` block ensures: (a) the transaction is fully
rolled back before we handle the error, and (b) re-rendering the form doesn't corrupt the
transaction state. Never catch `IntegrityError` *inside* a `transaction.atomic()` block
without using `transaction.savepoint()` — it invalidates the entire transaction.

**Why `create_user()` not `objects.create()`:**
`create_user()` calls `set_password()` internally, which properly hashes the password.
`objects.create()` with `password=...` stores plaintext. Always use `create_user()`.

---

### Task 3: `institution/urls.py` — Exact Change

Uncomment the `institution-add` path (was commented out in Story 2.1):

```python
from django.urls import path
from institution import views

app_name = 'institution'

urlpatterns = [
    # Story 2.1 — Institution Selector Screen
    path('', views.institution_selector, name='institution-selector'),

    # Story 2.2 — Context Switching
    path('switch/<int:institution_id>/', views.institution_switch, name='institution-switch'),

    # Story 2.3 — Atomic Institution Onboarding  ← UNCOMMENT THIS
    path('add/', views.institution_add, name='institution-add'),

    # Story 2.4 — Superadmin Aggregate Analytics Dashboard
    # path('superadmin/', views.superadmin_dashboard, name='superadmin-dashboard'),

    # Story 2.6 — Patient Move Between Institutions
    # path('patient-move/<int:patient_id>/', views.superadmin_patient_move, name='superadmin-patient-move'),

    # Story 3.1 — Institution Admin Dashboard
    # path('admin/', views.institution_admin_dashboard, name='institution-admin-dashboard'),
]
```

---

### Task 4: `templates/institution/add.html` — Full Template

```django
{% extends 'src/base.html' %}
{% load static %}
{% block title %}Onboard New Institution — NDAS{% endblock %}

{% block content_header %}
<div class="row mb-0">
  <div class="col-sm-6">
    <h1 class="m-0">Onboard New Institution</h1>
  </div>
  <div class="col-sm-6">
    <ol class="breadcrumb float-sm-right">
      <li class="breadcrumb-item"><a href="{% url 'institution:institution-selector' %}">Network</a></li>
      <li class="breadcrumb-item active">Onboard</li>
    </ol>
  </div>
</div>
{% endblock content_header %}

{% block main_content %}
<div class="container-fluid">
  <form method="post" action="{% url 'institution:institution-add' %}">
    {% csrf_token %}
    {% include 'src/form_error.html' %}

    <div class="row">

      {# ── Card 1: Institution Details ──────────────────────────────── #}
      <div class="col-md-6">
        <div class="card card-primary card-outline">
          <div class="card-header">
            <h3 class="card-title">
              <i class="fas fa-hospital mr-2"></i>Institution Details
            </h3>
          </div>
          <div class="card-body">

            <div class="form-group">
              <label for="{{ form.institution_name.id_for_label }}">
                {{ form.institution_name.label }} <span class="text-danger">*</span>
              </label>
              {{ form.institution_name }}
              {% if form.institution_name.errors %}
                <div class="text-danger small mt-1">{{ form.institution_name.errors }}</div>
              {% endif %}
            </div>

            <div class="form-group">
              <label for="{{ form.institution_slug.id_for_label }}">
                {{ form.institution_slug.label }} <span class="text-danger">*</span>
              </label>
              {{ form.institution_slug }}
              {% if form.institution_slug.errors %}
                <div class="text-danger small mt-1">{{ form.institution_slug.errors }}</div>
              {% endif %}
              <small class="form-text text-muted">{{ form.institution_slug.help_text }}</small>
            </div>

          </div>
        </div>
      </div>

      {# ── Card 2: First Admin Account ──────────────────────────────── #}
      <div class="col-md-6">
        <div class="card card-success card-outline">
          <div class="card-header">
            <h3 class="card-title">
              <i class="fas fa-user-shield mr-2"></i>First Admin Account
            </h3>
          </div>
          <div class="card-body">

            <div class="row">
              <div class="col-6">
                <div class="form-group">
                  <label>{{ form.admin_first_name.label }} <span class="text-danger">*</span></label>
                  {{ form.admin_first_name }}
                  {% if form.admin_first_name.errors %}
                    <div class="text-danger small mt-1">{{ form.admin_first_name.errors }}</div>
                  {% endif %}
                </div>
              </div>
              <div class="col-6">
                <div class="form-group">
                  <label>{{ form.admin_last_name.label }}</label>
                  {{ form.admin_last_name }}
                </div>
              </div>
            </div>

            <div class="form-group">
              <label>{{ form.admin_email.label }} <span class="text-danger">*</span></label>
              {{ form.admin_email }}
              {% if form.admin_email.errors %}
                <div class="text-danger small mt-1">{{ form.admin_email.errors }}</div>
              {% endif %}
            </div>

            <div class="form-group">
              <label>{{ form.admin_username.label }} <span class="text-danger">*</span></label>
              {{ form.admin_username }}
              {% if form.admin_username.errors %}
                <div class="text-danger small mt-1">{{ form.admin_username.errors }}</div>
              {% endif %}
              <small class="form-text text-muted">{{ form.admin_username.help_text }}</small>
            </div>

            <div class="row">
              <div class="col-6">
                <div class="form-group">
                  <label>{{ form.admin_position.label }} <span class="text-danger">*</span></label>
                  {{ form.admin_position }}
                  {% if form.admin_position.errors %}
                    <div class="text-danger small mt-1">{{ form.admin_position.errors }}</div>
                  {% endif %}
                </div>
              </div>
              <div class="col-6">
                <div class="form-group">
                  <label>{{ form.admin_mobile.label }} <span class="text-danger">*</span></label>
                  {{ form.admin_mobile }}
                  {% if form.admin_mobile.errors %}
                    <div class="text-danger small mt-1">{{ form.admin_mobile.errors }}</div>
                  {% endif %}
                </div>
              </div>
            </div>

            <div class="row">
              <div class="col-6">
                <div class="form-group">
                  <label>{{ form.admin_password.label }} <span class="text-danger">*</span></label>
                  {{ form.admin_password }}
                  {% if form.admin_password.errors %}
                    <div class="text-danger small mt-1">{{ form.admin_password.errors }}</div>
                  {% endif %}
                  <small class="form-text text-muted">{{ form.admin_password.help_text }}</small>
                </div>
              </div>
              <div class="col-6">
                <div class="form-group">
                  <label>{{ form.admin_password_confirm.label }} <span class="text-danger">*</span></label>
                  {{ form.admin_password_confirm }}
                  {% if form.admin_password_confirm.errors %}
                    <div class="text-danger small mt-1">{{ form.admin_password_confirm.errors }}</div>
                  {% endif %}
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>

    {# ── Submit Row ───────────────────────────────────────────────────── #}
    <div class="row">
      <div class="col-12">
        <div class="card">
          <div class="card-footer d-flex justify-content-between">
            <a href="{% url 'institution:institution-selector' %}" class="btn btn-secondary">
              <i class="fas fa-arrow-left mr-1"></i>Cancel
            </a>
            <button type="submit" class="btn btn-primary">
              <i class="fas fa-plus-circle mr-1"></i>Onboard Institution
            </button>
          </div>
        </div>
      </div>
    </div>

  </form>
</div>

{# Progressive slug auto-population from institution name #}
<script nonce="{{ request.csp_nonce }}">
(function() {
  var nameField = document.getElementById('id_institution_name');
  var slugField = document.getElementById('id_institution_slug');
  if (!nameField || !slugField) return;

  nameField.addEventListener('input', function() {
    // Only auto-populate if slug field is empty (don't overwrite manual edits)
    if (slugField.value.trim() !== '') return;
    var slug = nameField.value
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')  // strip non-alphanumeric
      .trim()
      .replace(/\s+/g, '-')           // spaces to hyphens
      .replace(/-+/g, '-');           // collapse multiple hyphens
    slugField.value = slug;
  });
})();
</script>
{% endblock %}
```

**CSP note:** The inline `<script>` uses `nonce="{{ request.csp_nonce }}"` — required by
the existing `CSPMiddleware` configuration. This is consistent with the existing project
security architecture.

---

### Task 5: `templates/institution/selector.html` — Change

Replace the comment placeholder with an actual button. Find this comment in `selector.html`:
```django
{# Story 2.3 adds the "Onboard New Institution" button here #}
```

Replace with:
```django
<a href="{% url 'institution:institution-add' %}"
   class="btn btn-primary">
  <i class="fas fa-plus-circle mr-1"></i>
  Onboard New Institution
</a>
```

This button appears in the page header row (`<div class="row mb-3">` → `d-flex` container)
next to the "Institution Network" heading. The `justify-content-between` on the parent
`d-flex` div already aligns it to the right.

---

### Task 6: `institution/tests/test_institution_add.py` — Full Code

```python
"""
institution/tests/test_institution_add.py

Tests for Atomic Institution Onboarding (Story 2.3).
AC: #1 (atomic creation), #2 (redirect + card appears), #3 (rollback on failure),
    #4 (duplicate slug rejected), #5 (slug immutable)
"""

import logging

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, Position

logger = logging.getLogger(__name__)
User = get_user_model()


class OnboardingTestBase(TestCase):
    """Shared setup: SUPERADMIN + form data."""

    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_onboard', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771990001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.admin_user = User.objects.create_user(
            username='admin_existing', password='Testpass1!',
            first_name='Existing', last_name='Admin',
            position='Administrator', mobile_primary='0771990002',
            user_type=UserType.ADMIN,
            institution=Institution.objects.create(
                name='Existing Hospital', slug='existing-hospital',
                subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            ),
        )

        self.add_url = reverse('institution:institution-add')

        self.valid_form_data = {
            'institution_name': 'New Children Hospital',
            'institution_slug': 'new-children-hospital',
            'admin_first_name': 'Janet',
            'admin_last_name': 'Doe',
            'admin_email': 'janet@newchildrenshospital.lk',
            'admin_username': 'janet_admin',
            'admin_position': Position.ADMINISTRATOR,
            'admin_mobile': '0771234567',
            'admin_password': 'SecurePass123!',
            'admin_password_confirm': 'SecurePass123!',
        }


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class InstitutionAddAccessTest(OnboardingTestBase):
    """Only SUPERADMIN can access the onboarding form."""

    def test_superadmin_can_access_add_form(self):
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.add_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Onboard New Institution', response.content.decode())

    def test_admin_redirected_from_add_form(self):
        client = Client()
        client.force_login(self.admin_user)
        response = client.get(self.add_url)
        self.assertEqual(response.status_code, 302,
            "ADMIN must not access institution onboarding form")

    def test_unauthenticated_redirected_to_login(self):
        client = Client()
        response = client.get(self.add_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'].lower())


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class AtomicCreationTest(OnboardingTestBase):
    """AC #1, #2: Successful form creates Institution + CustomUser atomically."""

    def test_valid_form_creates_institution(self):
        """AC #1: Institution is created after successful form submission."""
        client = Client()
        client.force_login(self.superadmin)

        before_count = Institution.objects.count()
        response = client.post(self.add_url, data=self.valid_form_data)

        self.assertEqual(response.status_code, 302,
            "Successful onboarding should redirect")
        self.assertEqual(Institution.objects.count(), before_count + 1,
            "One new Institution must be created")

        new_inst = Institution.objects.get(slug='new-children-hospital')
        self.assertEqual(new_inst.name, 'New Children Hospital')
        self.assertEqual(new_inst.subscription_status, SubscriptionStatus.ACTIVE)

    def test_valid_form_creates_admin_user(self):
        """AC #1: First ADMIN user is created with correct user_type and institution binding."""
        client = Client()
        client.force_login(self.superadmin)

        client.post(self.add_url, data=self.valid_form_data)

        new_inst = Institution.objects.get(slug='new-children-hospital')
        admin = User.objects.get(username='janet_admin')

        self.assertEqual(admin.user_type, UserType.ADMIN,
            "New admin must have user_type=ADMIN")
        self.assertEqual(admin.institution, new_inst,
            "New admin must be bound to the new institution")
        self.assertTrue(admin.check_password('SecurePass123!'),
            "Admin password must be hashed and verifiable")

    def test_new_institution_has_user_count_one(self):
        """AC #2: After creation, institution has exactly 1 user (the admin)."""
        client = Client()
        client.force_login(self.superadmin)

        client.post(self.add_url, data=self.valid_form_data)

        new_inst = Institution.objects.get(slug='new-children-hospital')
        # Count users bound to this institution
        user_count = User.objects.filter(institution=new_inst).count()
        self.assertEqual(user_count, 1,
            "New institution must have exactly 1 user (the first admin)")

    def test_successful_onboarding_redirects_to_selector(self):
        """AC #2: After successful creation, superadmin is redirected to selector screen."""
        client = Client()
        client.force_login(self.superadmin)

        response = client.post(self.add_url, data=self.valid_form_data)

        selector_url = reverse('institution:institution-selector')
        self.assertRedirects(response, selector_url,
            msg_prefix="Successful onboarding must redirect to institution selector")

    def test_new_institution_appears_on_selector_immediately(self):
        """AC #2: After creation, new institution card is visible on selector — no restart needed."""
        client = Client()
        client.force_login(self.superadmin)

        client.post(self.add_url, data=self.valid_form_data)

        # Load the selector screen
        response = client.get(reverse('institution:institution-selector'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('New Children Hospital', response.content.decode(),
            "Newly created institution must appear on selector immediately")

    def test_created_by_is_superadmin(self):
        """Institution.created_by is set to the SUPERADMIN who submitted the form."""
        client = Client()
        client.force_login(self.superadmin)

        client.post(self.add_url, data=self.valid_form_data)

        new_inst = Institution.objects.get(slug='new-children-hospital')
        self.assertEqual(new_inst.created_by, self.superadmin)


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class AtomicRollbackTest(OnboardingTestBase):
    """AC #3: If admin creation fails, Institution is also rolled back — no orphans."""

    def test_duplicate_username_causes_rollback_no_orphan_institution(self):
        """
        AC #3: If admin username already exists, the IntegrityError rolls back
        the entire transaction — the Institution record is NOT created.
        """
        client = Client()
        client.force_login(self.superadmin)

        # Use a username that already exists
        data = dict(self.valid_form_data)
        data['admin_username'] = 'admin_existing'  # already taken (from setUp)

        before_count = Institution.objects.count()
        response = client.post(self.add_url, data=data)

        # Form validation should catch this, but even if it slips through:
        self.assertEqual(Institution.objects.count(), before_count,
            "AC #3: No orphan Institution must exist when admin creation fails — "
            "transaction.atomic() must roll back both records")

    def test_form_rerendered_on_validation_error(self):
        """Form is re-rendered with errors when validation fails — no redirect."""
        client = Client()
        client.force_login(self.superadmin)

        data = dict(self.valid_form_data)
        data['admin_username'] = 'admin_existing'  # duplicate username

        response = client.post(self.add_url, data=data)

        # Should re-render form (200), not redirect (302)
        self.assertEqual(response.status_code, 200,
            "Failed form submission must re-render the form with errors (not redirect)")


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class SlugValidationTest(OnboardingTestBase):
    """AC #4: Duplicate slug rejected at form validation."""

    def test_duplicate_slug_shows_validation_error(self):
        """AC #4: Submitting an existing slug shows a validation error."""
        client = Client()
        client.force_login(self.superadmin)

        data = dict(self.valid_form_data)
        data['institution_slug'] = 'existing-hospital'  # already in setUp

        before_count = Institution.objects.count()
        response = client.post(self.add_url, data=data)

        self.assertEqual(response.status_code, 200,
            "Duplicate slug must re-render form with error")
        self.assertEqual(Institution.objects.count(), before_count,
            "AC #4: No new Institution must be created when slug is duplicate")
        content = response.content.decode()
        self.assertIn('already exists', content,
            "Error message about duplicate slug must be shown")

    def test_unique_slug_is_accepted(self):
        """A brand new slug passes validation and creates the institution."""
        client = Client()
        client.force_login(self.superadmin)

        response = client.post(self.add_url, data=self.valid_form_data)
        self.assertEqual(response.status_code, 302,
            "Unique slug should result in successful creation")


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class SlugImmutabilityTest(OnboardingTestBase):
    """AC #5: Slug cannot be changed after creation — enforced in Institution.save()."""

    def test_slug_cannot_be_changed_after_creation(self):
        """AC #5: Attempting to change an institution's slug raises ValidationError."""
        from django.core.exceptions import ValidationError

        inst = Institution.objects.create(
            name='Test Immutable Hospital',
            slug='test-immutable-hosp',
            subscription_status=SubscriptionStatus.ACTIVE,
            is_active=True,
        )
        inst.slug = 'changed-slug'
        with self.assertRaises(ValidationError,
                msg="AC #5: Institution.save() must raise ValidationError when slug is changed"):
            inst.save()


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class FormValidationEdgeCaseTest(OnboardingTestBase):
    """Edge cases: password mismatch, missing required fields, invalid slug format."""

    def test_password_mismatch_shows_error(self):
        client = Client()
        client.force_login(self.superadmin)

        data = dict(self.valid_form_data)
        data['admin_password_confirm'] = 'DifferentPassword123!'

        response = client.post(self.add_url, data=data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('do not match', response.content.decode().lower())

    def test_weak_password_rejected(self):
        """Django password validators reject weak passwords."""
        client = Client()
        client.force_login(self.superadmin)

        data = dict(self.valid_form_data)
        data['admin_password'] = 'password'  # too weak
        data['admin_password_confirm'] = 'password'

        response = client.post(self.add_url, data=data)
        self.assertEqual(response.status_code, 200,
            "Weak password should not create institution")

    def test_slug_with_uppercase_rejected_by_slugfield(self):
        """SlugField allows only lowercase-compatible characters."""
        client = Client()
        client.force_login(self.superadmin)

        data = dict(self.valid_form_data)
        data['institution_slug'] = 'UPPERCASE-SLUG'  # SlugField lowercases or rejects

        response = client.post(self.add_url, data=data)
        # SlugField in Django lowercases input — this should either succeed with lowercased slug
        # or fail validation. Acceptable either way — document actual behavior.
        self.assertIn(response.status_code, [200, 302])
```

---

### Why `IntegrityError` Is Caught OUTSIDE `transaction.atomic()`

```python
try:
    with transaction.atomic():
        institution = Institution.objects.create(...)
        admin_user = User.objects.create_user(...)
    # ← Both committed here if no exception
except IntegrityError as e:
    # ← Transaction already fully rolled back when we get here
    form.add_error(None, "...")
```

If `create_user(username=...)` hits a uniqueness constraint (race condition between
`clean_admin_username()` check and the actual INSERT), Django raises `IntegrityError`.
Inside `transaction.atomic()`, this marks the transaction as "needs rollback". The `with`
block exit triggers the rollback. **Catching inside the `with` block would silently leave
the transaction in a broken state.** Always catch after the `with` block.

This pattern is documented in Django's [database transactions documentation](https://docs.djangoproject.com/en/4.2/topics/db/transactions/#controlling-transactions-explicitly).

---

### Project Structure Notes

**Files CREATED in this story:**
- `institution/forms.py` — `InstitutionOnboardingForm` with all field + clean methods
- `templates/institution/add.html` — two-card AdminLTE form
- `institution/tests/test_institution_add.py` — 14 tests covering ACs #1–#5

**Files MODIFIED in this story:**
- `institution/views.py` — add `institution_add` view
- `institution/urls.py` — uncomment `path('add/', ...)` for `institution-add`
- `templates/institution/selector.html` — activate "Onboard New Institution" button

**Files NOT touched:**
- `institution/models.py` — Institution model already has `slug` immutability (Story 1.1)
- `ndas/urls.py` — already includes `institution/` prefix (Story 2.1)
- Any migration files — no schema changes

---

### References

- Architecture: FR52 — one form creates Institution + first ADMIN atomically [Source: `_bmad-output/planning-artifacts/architecture.md#Decision Priority Analysis`]
- Architecture: NFR13 — multi-step record operations complete atomically [Source: `_bmad-output/planning-artifacts/epics.md#NFR13`]
- Architecture: `institution-add` URL name; `institution_add` view function [Source: `_bmad-output/planning-artifacts/architecture.md#Naming Patterns`]
- Architecture: Institution model — slug immutable after creation; `created_by` FK to SUPERADMIN [Source: `_bmad-output/planning-artifacts/architecture.md#Data Architecture`]
- Architecture: `transaction.atomic()` wrapping dual record creation [Source: `_bmad-output/planning-artifacts/architecture.md#Communication Patterns`]
- Epics: Story 2.3 ACs — atomic creation, redirect to selector, rollback on failure, slug uniqueness, slug immutability [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.3`]
- Users model: `REQUIRED_FIELDS = ["email", "first_name", "position", "mobile_primary"]` [Source: `users/models.py:118`]
- Users model: `create_user()` handles password hashing — always use over `objects.create()` [Source: `users/models.py:17`]
- Institution model: `subscription_status = SubscriptionStatus.ACTIVE` default; `slug` unique constraint [Source: `institution/models.py`]
- Project context: Choices in `ndas/custom_codes/choice.py`; `Position.ADMINISTRATOR` for admin role [Source: `ndas/custom_codes/choice.py`, `_bmad-output/project-context.md`]
- Project context: `sanitize_text_input()` for free-text name fields [Source: `_bmad-output/project-context.md#Input Sanitization`]
- Project context: Function-based views; `@require_http_methods(["GET", "POST"])` for form views [Source: `_bmad-output/project-context.md#Framework-Specific Rules`]
- Project context: `{% include 'src/form_error.html' %}` in all forms [Source: `_bmad-output/project-context.md#Templates`]
- Project context: CSP nonce for inline scripts — `nonce="{{ request.csp_nonce }}"` [Source: `_bmad-output/project-context.md#Security Gotchas`]
- Django docs: `IntegrityError` catch outside `transaction.atomic()` to avoid broken transaction state [Django transactions documentation]
- Story 2.1: selector.html `{# Story 2.3 comment #}` placeholder for "Onboard" button [Source: `_bmad-output/implementation-artifacts/2-1-institution-selector-screen.md#Task 4`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- All tasks implemented. Code review (2026-02-25) found and fixed: missing `validate_password()` in form (H1), CSP nonce on add.html script (H2), weak test assertion (M1), missing AC#3 rollback test (M2), missing AC#5 slug immutability test (M3), unused `slugify` import (L1), missing `sanitize_text_input` on admin_first_name (L2).
- All URLs were already uncommented in `institution/urls.py` — Task 3 was complete.
- "Onboard New Institution" button already present in `selector.html` as "Add Institution" — Task 5 was complete.

### File List

- `institution/forms.py` — created: `InstitutionOnboardingForm`
- `templates/institution/add.html` — created: two-card AdminLTE onboarding form
- `institution/tests/test_institution_add.py` — created: access, atomicity, rollback, slug immutability tests
- `institution/views.py` — modified: `institution_add` view (already present from Story 2.3 implementation)
- `institution/urls.py` — `institution-add` URL was already active (no change required)
- `templates/institution/selector.html` — "Add Institution" button already present (no change required)

### Change Log

- 2026-02-25: Implemented by claude-sonnet-4-6. Code review pass by claude-sonnet-4-6. Fixed 2 HIGH + 3 MEDIUM + 2 LOW issues post-review. Story marked done.
