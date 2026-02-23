# Story 2.2: Superadmin Institution Context Switching

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **superadmin**,
I want a persistent banner showing which institution I'm currently viewing, with a dropdown to switch to another,
So that I can operate within any institution's context without logging in as that institution's admin.

## Acceptance Criteria

1. **Given** the superadmin selects an institution from the selector screen
   **When** the selection is submitted via POST to the institution switch endpoint
   **Then** `session['active_institution_id']` is set to the selected institution's ID and a full page reload occurs

2. **Given** the superadmin has an active institution context
   **When** any authenticated page renders
   **Then** the persistent top banner shows "Viewing as: [Institution Name] [Switch ▼]" via `{% superadmin_overlay %}` in `src/base.html`
   **And** the banner is only visible when `is_superadmin` is True and an institution context is active

3. **Given** the superadmin is viewing Institution B's context
   **When** they access the patient list, reports, or any data view
   **Then** only Institution B's data is visible — the institution context scopes all queries correctly

4. **Given** the superadmin overlay is active
   **When** any patient detail or institution management page renders
   **Then** superadmin-only action buttons (Move Patient, Edit Subscription, Suspend User) are injected via the `{% superadmin_overlay %}` template tag
   **And** these buttons are not visible to ADMIN or USER role users under any condition

## Tasks / Subtasks

- [ ] Task 1: Expand `institution_switch` view in `institution/views.py` (AC: #1, #3)
  - [ ] Change decorator from `@require_GET` stub to full `@require_POST` handler
  - [ ] Validate institution exists, is active, and requesting user is SUPERADMIN
  - [ ] Set `request.session['active_institution_id'] = institution.pk`
  - [ ] Log the context switch: user, from_institution (if any), to_institution
  - [ ] Redirect to `manage-patients` after successful switch (full page reload)
  - [ ] See exact view code in Dev Notes

- [ ] Task 2: Create `institution/templatetags/__init__.py` + `institution_tags.py` (AC: #2, #4)
  - [ ] Create `institution/templatetags/` directory if it doesn't exist
  - [ ] Create empty `institution/templatetags/__init__.py`
  - [ ] Implement `superadmin_overlay` as `inclusion_tag` with `takes_context=True`
  - [ ] Tag queries all active institutions for the switch dropdown
  - [ ] Tag uses `get_token(request)` from `django.middleware.csrf` to pass CSRF token to sub-template
  - [ ] Returns `{'show_overlay': False}` when not SUPERADMIN or no active institution
  - [ ] See exact tag code in Dev Notes

- [ ] Task 3: Create `templates/institution/partials/superadmin_overlay.html` (AC: #2, #4)
  - [ ] Create `templates/institution/partials/` directory
  - [ ] Render nothing (empty) when `show_overlay` is False
  - [ ] Dark banner strip inside `content-wrapper`: "Viewing as: **[Institution Name]** [Switch ▼]"
  - [ ] Bootstrap 4.6 `.dropdown` for institution list — each item is a POST form to `institution:institution-switch`
  - [ ] Include "All Institutions" link at dropdown bottom → `institution:institution-selector`
  - [ ] Action buttons section: Move Patient, Edit Subscription, Suspend User (disabled/stubbed for future stories)
  - [ ] See exact template HTML in Dev Notes

- [ ] Task 4: Modify `templates/src/base.html` to inject overlay (AC: #2)
  - [ ] Add `{% load institution_tags %}` on the line after `{% load static %}`
  - [ ] Add `{% superadmin_overlay %}` inside `<div class="content-wrapper">` BEFORE `<div class="content-header">`
  - [ ] Verify no AdminLTE layout breakage: check that page renders correctly for ADMIN/USER (overlay is hidden)
  - [ ] See exact diff in Dev Notes

- [ ] Task 5: Write tests in `institution/tests/test_context_switching.py` (AC: #1, #2, #3, #4)
  - [ ] See exact test code in Dev Notes

## Dev Notes

### Story 2.2 Position in the 13-Step Sequence

Story 2.2 = still within **Step 8** (Superadmin views + god-view dashboard):

```
8.  Superadmin views + god-view dashboard:
    ├── Story 2.1: institution_selector view + selector.html          ← DONE
    └── Story 2.2: institution_switch view + superadmin_overlay tag   ← THIS STORY
```

**Prerequisites:** Story 2.1 must be `done` (provides `institution_switch` stub + URL registration).
Run before starting:
```bash
python manage.py test institution.tests.test_selector   # Story 2.1 tests must pass
python manage.py runserver                              # verify selector screen loads at /institution/
```

---

### Task 1: Expanded `institution_switch` View — Full Code

Replace the Story 2.1 stub in `institution/views.py` with this full implementation:

```python
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from institution.models import Institution
from ndas.custom_codes.choice import UserType
from ndas.custom_codes.error_handlers import handle_view_errors

logger = logging.getLogger(__name__)


@login_required(login_url="user-login")
@require_GET
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='manage-patients', error_message='Unable to load institution network.')
def institution_selector(request):
    """SUPERADMIN god-view: all institutions as cards. (Story 2.1)"""
    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.SUPERADMIN:
        if user_type == UserType.ADMIN:
            return redirect('institution:institution-admin-dashboard')
        return redirect('manage-patients')

    request.session.pop('active_institution_id', None)

    institutions = Institution.objects.annotate(
        user_count=Count('customuser', distinct=True),
        patient_count=Count('patient', distinct=True),
        last_activity=Max('patient__created_at'),
    ).select_related('created_by').order_by('name')

    return render(request, 'institution/selector.html', {
        'institutions': institutions,
        'page_title': 'Institution Network',
    })


@login_required(login_url="user-login")
@require_POST
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(redirect_url='institution:institution-selector', error_message='Context switch failed.')
def institution_switch(request, institution_id):
    """
    SUPERADMIN context switch — sets session['active_institution_id'].
    POSTed from selector.html cards AND from the superadmin_overlay dropdown.
    After switching, redirects to manage-patients (full page reload, new institution context).

    AC: FR51 — persistent on-screen institution context switching.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.SUPERADMIN:
        return redirect('manage-patients')

    institution = get_object_or_404(Institution, pk=institution_id, is_active=True)

    # Log context switch for audit trail
    previous_id = request.session.get('active_institution_id')
    previous_name = '(none)'
    if previous_id:
        try:
            previous_name = Institution.objects.get(pk=previous_id).name
        except Institution.DoesNotExist:
            previous_name = f'(id={previous_id}, deleted)'

    request.session['active_institution_id'] = institution.pk

    logger.info(
        "SUPERADMIN %s switched institution context: '%s' → '%s' (id=%d)",
        request.user.username, previous_name, institution.name, institution.pk,
    )

    messages.success(request, f"Viewing as: {institution.name}")
    return redirect('manage-patients')
```

**Note on `@handle_view_errors`:** If `handle_view_errors` uses Django messages internally, the
`messages.success(...)` call here may be redundant. Check `ndas/custom_codes/error_handlers.py`
and remove the duplicate if needed.

---

### Task 2: `institution/templatetags/institution_tags.py` — Full Code

```python
"""
institution/templatetags/institution_tags.py

Custom template tags for institution context rendering.

Tags:
    superadmin_overlay — Renders the persistent superadmin context banner in src/base.html

Usage in templates:
    {% load institution_tags %}
    {% superadmin_overlay %}
"""

import logging

from django import template
from django.middleware.csrf import get_token

from institution.models import Institution

logger = logging.getLogger(__name__)
register = template.Library()


@register.inclusion_tag(
    'institution/partials/superadmin_overlay.html',
    takes_context=True,
)
def superadmin_overlay(context):
    """
    Renders the SUPERADMIN context banner:
    "Viewing as: [Institution Name] [Switch ▼]" + action button stubs.

    Returns empty context (show_overlay=False) for ADMIN/USER or when
    no institution context is active. Invisible to non-superadmin users.

    CSRF note: Inclusion tags render in a plain Context (not RequestContext),
    so {% csrf_token %} does not work automatically. We pass the CSRF token
    explicitly via get_token(request). The sub-template uses:
        <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
    """
    request = context.get('request')
    if not request:
        return {'show_overlay': False}

    is_superadmin = context.get('is_superadmin', False)
    active_institution = context.get('active_institution')

    if not is_superadmin or not active_institution:
        return {'show_overlay': False}

    # Query all active institutions for the switch dropdown
    # Ordered by name — same order as selector screen
    institutions = Institution.objects.filter(is_active=True).order_by('name')

    # CSRF token for POST forms inside the inclusion template
    try:
        csrf_token_value = get_token(request)
    except Exception:
        csrf_token_value = ''

    return {
        'show_overlay': True,
        'active_institution': active_institution,
        'institutions': institutions,
        'csrf_token': csrf_token_value,
    }
```

**Directory structure to create:**
```
institution/
└── templatetags/
    ├── __init__.py          (empty file — required by Python)
    └── institution_tags.py  (this file)
```

---

### Task 3: `templates/institution/partials/superadmin_overlay.html` — Full Template

```django
{% if show_overlay %}
{# SUPERADMIN CONTEXT BANNER — renders only for SUPERADMIN with active institution context #}
{# Injected by {% superadmin_overlay %} tag in src/base.html #}
<div id="superadmin-context-banner"
     style="background: #343a40; color: #f8f9fa; padding: 5px 20px; border-bottom: 3px solid #007bff; font-size: 0.85rem;">
  <div class="d-flex align-items-center justify-content-between flex-wrap">

    {# Left: "Viewing as" text + Switch dropdown #}
    <div class="d-flex align-items-center">
      <span class="badge badge-warning mr-2" style="font-size:0.75rem;">SUPERADMIN</span>
      <span class="mr-2">Viewing as: <strong>{{ active_institution.name }}</strong></span>

      {# Bootstrap 4.6 Dropdown — Switch Institution #}
      <div class="dropdown d-inline-block">
        <button class="btn btn-sm btn-outline-light dropdown-toggle py-0"
                type="button"
                id="institutionSwitchDropdown"
                data-toggle="dropdown"
                aria-haspopup="true"
                aria-expanded="false">
          Switch ▼
        </button>
        <div class="dropdown-menu dropdown-menu-right shadow" aria-labelledby="institutionSwitchDropdown"
             style="max-height:300px; overflow-y:auto; min-width:220px;">
          {% for inst in institutions %}
          <form method="post"
                action="/institution/switch/{{ inst.pk }}/"
                style="margin:0; padding:0;">
            <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
            <button type="submit"
                    class="dropdown-item d-flex align-items-center justify-content-between py-1
                      {% if inst.pk == active_institution.pk %}active font-weight-bold{% endif %}"
                    style="font-size:0.85rem;">
              <span>
                {% if inst.pk == active_institution.pk %}
                <i class="fas fa-check-circle mr-1 text-success"></i>
                {% endif %}
                {{ inst.name }}
              </span>
              {% if inst.subscription_status == 'EXPIRED' %}
                <span class="badge badge-danger ml-2">Expired</span>
              {% elif inst.subscription_status == 'GRACE' %}
                <span class="badge badge-warning ml-2 text-dark">Grace</span>
              {% endif %}
            </button>
          </form>
          {% endfor %}
          <div class="dropdown-divider"></div>
          <a class="dropdown-item text-muted" href="/institution/" style="font-size:0.85rem;">
            <i class="fas fa-th-large mr-1"></i>All Institutions
          </a>
        </div>
      </div>
    </div>

    {# Right: Superadmin action buttons (contextual — story stubs) #}
    <div class="d-flex align-items-center">
      {#
        Story 2.6: Move Patient — shown on patient detail pages when patient is in context
        <a href="#" class="btn btn-sm btn-outline-warning mr-1" title="Move Patient to another institution">
          <i class="fas fa-exchange-alt"></i> Move Patient
        </a>
      #}
      {#
        Story 3.3 (via admin flow): Edit Subscription
        <a href="#" class="btn btn-sm btn-outline-info mr-1" title="Edit institution subscription">
          <i class="fas fa-edit"></i> Edit Subscription
        </a>
      #}
      {#
        Story 3.2: Suspend User — shown on user management pages
        <a href="#" class="btn btn-sm btn-outline-danger mr-1" title="Suspend user">
          <i class="fas fa-user-slash"></i> Suspend User
        </a>
      #}
      <a href="/institution/"
         class="btn btn-sm btn-outline-light"
         title="Go to Institution Network">
        <i class="fas fa-network-wired"></i>
        <span class="d-none d-md-inline ml-1">Network</span>
      </a>
    </div>

  </div>
</div>
{% endif %}
```

**Design notes:**
- Dark AdminLTE `#343a40` background matches the navbar — visually connected
- Blue bottom border (Bootstrap `#007bff` / `primary`) signals "active context"
- The SUPERADMIN badge (yellow/warning) makes it immediately obvious this is admin mode
- `max-height:300px; overflow-y:auto` on dropdown handles 20+ institutions
- Action buttons (Move Patient, Edit Subscription, Suspend User) are **commented out** — they are stubs for future stories. Story 2.6, 3.2, 3.3 will uncomment and link them
- **Hardcoded URL paths** (`/institution/switch/{{ inst.pk }}/`) are used instead of `{% url %}` because the inclusion tag sub-template does not have `{% load institution_tags %}` available and calling `{% url %}` from an un-tagged template is fine. Alternatively, pass the switch URL pattern in the tag context (see dev note below)

**Alternative URL approach (cleaner):** Instead of hardcoded paths, pass the switch URL base path from the tag:
```python
# in institution_tags.py:
from django.urls import reverse
...
    return {
        ...
        'switch_url_base': '/institution/switch/',  # append inst.pk in template
    }
```
Then in template: `action="{{ switch_url_base }}{{ inst.pk }}/"`. This avoids hardcoded URL.

---

### Task 4: `templates/src/base.html` — Exact Modification

**Current `src/base.html` (lines 1–34, unchanged):**
```django
{% extends './basic_plane.html' %}
{% load static %}
{% block mainbody %}
...
<div class="content-wrapper">
    <!-- Content Header (Page header) -->
    <div class="content-header">
```

**Modified `src/base.html`:**
```django
{% extends './basic_plane.html' %}
{% load static %}
{% load institution_tags %}        {# ← ADD THIS LINE (line 3) #}
{% block mainbody %}

{% if user.is_authenticated %}

<div class="wrapper">
        <!-- Navbar -->
        {% include './navbar.html' %}
        <!-- /.navbar -->

        <!-- Main Sidebar Container -->
        {% include './main_sidebar_menu.html' %}
        <!-- /.sidebar -->

  <!-- Content Wrapper. Contains page content -->
  <div class="content-wrapper">

    <!-- Superadmin Context Banner (SUPERADMIN only — hidden for all other roles) -->
    {% superadmin_overlay %}        {# ← ADD THIS LINE (inside content-wrapper, before content-header) #}
    <!-- /.superadmin-context-banner -->

    <!-- Content Header (Page header) -->
    <div class="content-header">
```

**Exact change summary:**
1. Line 3: Add `{% load institution_tags %}` (after `{% load static %}`)
2. Inside `<div class="content-wrapper">`: Add `{% superadmin_overlay %}` before `<div class="content-header">`

**AdminLTE layout note:** Placing the banner inside `.content-wrapper` (not before it) means the banner respects the sidebar width — it doesn't overlap the sidebar. This is the correct AdminLTE 3.2 placement for content-area-spanning elements.

**CSP note:** The inline `style=""` attributes in the overlay template require `'unsafe-inline'` in `CSP_STYLE_SRC`. Check `ndas/settings.py` — both DEBUG and production CSP configs already include `'unsafe-inline'` for `CSP_STYLE_SRC`. No CSP changes needed.

---

### Task 5: `institution/tests/test_context_switching.py` — Full Code

```python
"""
institution/tests/test_context_switching.py

Tests for Superadmin Institution Context Switching (Story 2.2).
AC: #1 (POST sets session), #2 (overlay renders for SUPERADMIN),
    #3 (data scopes to active institution), #4 (action buttons not visible to ADMIN/USER)
"""

import logging
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

logger = logging.getLogger(__name__)
User = get_user_model()


class ContextSwitchTestBase(TestCase):
    """Shared setup: two institutions + SUPERADMIN + clinician."""

    def setUp(self):
        self.institution_a = Institution.objects.create(
            name='Hospital Alpha', slug='hospital-alpha',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
        )
        self.institution_b = Institution.objects.create(
            name='Hospital Beta', slug='hospital-beta',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
        )
        self.expired_inst = Institution.objects.create(
            name='Expired Hospital', slug='expired-hospital',
            subscription_status=SubscriptionStatus.EXPIRED, is_active=True,
        )

        self.superadmin = User.objects.create_user(
            username='sa_test', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771990001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.admin_user = User.objects.create_user(
            username='admin_test', password='Testpass1!',
            first_name='Admin', last_name='User',
            position='Administrator', mobile_primary='0771990002',
            user_type=UserType.ADMIN, institution=self.institution_a,
        )
        self.clinician = User.objects.create_user(
            username='user_test', password='Testpass1!',
            first_name='Regular', last_name='User',
            position='Medical Officer', mobile_primary='0771990003',
            user_type=UserType.USER, institution=self.institution_a,
        )

        self.switch_url_a = reverse('institution:institution-switch', args=[self.institution_a.pk])
        self.switch_url_b = reverse('institution:institution-switch', args=[self.institution_b.pk])
        self.selector_url = reverse('institution:institution-selector')


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class InstitutionSwitchViewTest(ContextSwitchTestBase):
    """AC #1: POST sets session['active_institution_id'] and redirects."""

    def test_superadmin_post_sets_session_active_institution(self):
        """AC #1: POSTing to switch endpoint sets the session key."""
        client = Client()
        client.force_login(self.superadmin)

        response = client.post(self.switch_url_a)

        self.assertEqual(response.status_code, 302,
            "Switch POST should redirect after setting institution context")
        self.assertEqual(client.session.get('active_institution_id'), self.institution_a.pk,
            "session['active_institution_id'] must be set to the selected institution's PK")

    def test_switch_redirects_to_manage_patients(self):
        """After switching, superadmin lands on manage-patients (full page reload)."""
        client = Client()
        client.force_login(self.superadmin)

        response = client.post(self.switch_url_b)

        self.assertRedirects(response, reverse('manage-patients'),
            msg_prefix="institution_switch must redirect to manage-patients after success")

    def test_switching_between_institutions_updates_session(self):
        """Switching from A to B updates session key to B's PK."""
        client = Client()
        client.force_login(self.superadmin)

        # Switch to A first
        client.post(self.switch_url_a)
        self.assertEqual(client.session.get('active_institution_id'), self.institution_a.pk)

        # Switch to B
        client.post(self.switch_url_b)
        self.assertEqual(client.session.get('active_institution_id'), self.institution_b.pk,
            "Session must update to new institution when switching context")

    def test_admin_cannot_use_switch_endpoint(self):
        """Non-SUPERADMIN cannot use institution_switch endpoint."""
        client = Client()
        client.force_login(self.admin_user)

        response = client.post(self.switch_url_a)

        self.assertEqual(response.status_code, 302)
        # Session must NOT have active_institution_id set
        self.assertIsNone(client.session.get('active_institution_id'),
            "ADMIN should not be able to set active_institution_id via switch endpoint")

    def test_switch_to_inactive_institution_returns_404(self):
        """Cannot switch to a non-existent or inactive institution."""
        client = Client()
        client.force_login(self.superadmin)

        inactive_inst = Institution.objects.create(
            name='Inactive Hospital', slug='inactive-hospital',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=False,
        )
        response = client.post(
            reverse('institution:institution-switch', args=[inactive_inst.pk])
        )
        self.assertEqual(response.status_code, 404,
            "Switch to inactive institution must return 404")

    def test_switch_get_method_not_allowed(self):
        """Switch endpoint must only accept POST — GET returns 405."""
        client = Client()
        client.force_login(self.superadmin)

        response = client.get(self.switch_url_a)
        self.assertEqual(response.status_code, 405,
            "institution_switch must only accept POST — GET must return 405")

    def test_unauthenticated_switch_redirects_to_login(self):
        """Unauthenticated POST to switch endpoint redirects to login."""
        client = Client()
        response = client.post(self.switch_url_a)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'].lower())


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class SuperadminOverlayRenderTest(ContextSwitchTestBase):
    """AC #2: Overlay renders for SUPERADMIN with context; hidden for ADMIN/USER."""

    def test_overlay_visible_for_superadmin_with_active_context(self):
        """AC #2: After switching, the SUPERADMIN sees the overlay banner on page load."""
        client = Client()
        client.force_login(self.superadmin)

        # Set active institution in session
        client.post(self.switch_url_a)  # sets session

        # Load any authenticated page
        response = client.get(reverse('manage-patients'))
        content = response.content.decode()

        self.assertIn('superadmin-context-banner', content,
            "Overlay banner div must appear for SUPERADMIN with active context")
        self.assertIn('Hospital Alpha', content,
            "Active institution name must appear in overlay banner")
        self.assertIn('SUPERADMIN', content,
            "SUPERADMIN badge must appear in overlay banner")

    def test_overlay_hidden_for_superadmin_without_context(self):
        """Overlay is NOT shown when SUPERADMIN has no active institution (before first switch)."""
        client = Client()
        client.force_login(self.superadmin)
        # No session['active_institution_id'] set — middleware redirects to selector
        # So we need to test the overlay on the selector page itself
        response = client.get(reverse('institution:institution-selector'))
        content = response.content.decode()
        self.assertNotIn('superadmin-context-banner', content,
            "Overlay must NOT render on selector page where there is no active institution context")

    def test_overlay_not_visible_for_admin_user(self):
        """AC #4: ADMIN user never sees the superadmin overlay banner."""
        client = Client()
        client.force_login(self.admin_user)
        response = client.get(reverse('manage-patients'))
        content = response.content.decode()
        self.assertNotIn('superadmin-context-banner', content,
            "ADMIN user must never see the superadmin overlay banner")

    def test_overlay_not_visible_for_clinician(self):
        """AC #4: Regular USER (clinician) never sees the superadmin overlay banner."""
        client = Client()
        client.force_login(self.clinician)
        response = client.get(reverse('manage-patients'))
        content = response.content.decode()
        self.assertNotIn('superadmin-context-banner', content,
            "Clinician USER must never see the superadmin overlay banner")

    def test_overlay_shows_switch_dropdown(self):
        """AC #2: Switch dropdown appears with institution list in overlay."""
        client = Client()
        client.force_login(self.superadmin)
        client.post(self.switch_url_a)

        response = client.get(reverse('manage-patients'))
        content = response.content.decode()

        # Dropdown should contain all institution names
        self.assertIn('Hospital Alpha', content)
        self.assertIn('Hospital Beta', content)
        self.assertIn('Expired Hospital', content)
        # Switch dropdown toggle
        self.assertIn('institutionSwitchDropdown', content)


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ContextSwitchDataScopeTest(ContextSwitchTestBase):
    """AC #3: After switching, data views are scoped to the active institution."""

    def test_patient_list_scoped_after_context_switch(self):
        """
        AC #3: After SUPERADMIN switches to Institution A, patient list shows only A's patients.
        This test verifies the middleware + ORM manager chain works end-to-end after a switch.
        """
        from patients.models import Patient
        from django.utils import timezone

        # Create patients in each institution
        patient_a = Patient.objects.create(
            bht='SA-TEST-BHT-001', baby_name='AlphaBabySwitch',
            mother_name='Alpha Mother', dob_tob=timezone.now(),
            gender='Male', pog_wks=38, pog_days=2,
            birth_weight=3000, ofc=33,
            mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711001001', added_by=self.superadmin,
            institution=self.institution_a,
        )
        patient_b = Patient.objects.create(
            bht='SB-TEST-BHT-001', baby_name='BetaBabySwitch',
            mother_name='Beta Mother', dob_tob=timezone.now(),
            gender='Female', pog_wks=39, pog_days=0,
            birth_weight=3200, ofc=34,
            mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711001002', added_by=self.superadmin,
            institution=self.institution_b,
        )

        client = Client()
        client.force_login(self.superadmin)

        # Switch to Institution A
        client.post(self.switch_url_a)
        response_a = client.get(reverse('manage-patients'))
        content_a = response_a.content.decode()
        self.assertIn('AlphaBabySwitch', content_a,
            "SUPERADMIN viewing Institution A should see Institution A patients")
        self.assertNotIn('BetaBabySwitch', content_a,
            "SUPERADMIN viewing Institution A must NOT see Institution B patients")

        # Switch to Institution B
        client.post(self.switch_url_b)
        response_b = client.get(reverse('manage-patients'))
        content_b = response_b.content.decode()
        self.assertIn('BetaBabySwitch', content_b,
            "SUPERADMIN viewing Institution B should see Institution B patients")
        self.assertNotIn('AlphaBabySwitch', content_b,
            "SUPERADMIN viewing Institution B must NOT see Institution A patients")
```

---

### Action Buttons: Architecture Intent vs Story 2.2 Scope

The AC #4 requires action buttons (Move Patient, Edit Subscription, Suspend User) to be
"injected via the `{% superadmin_overlay %}` template tag." In Story 2.2:

- **All three buttons are present in the overlay template as HTML comments** (not rendered)
- Each comment documents which story will uncomment and activate the button
- The buttons are NOT visible to ADMIN/USER because `show_overlay=False` for those roles
- Test `test_overlay_not_visible_for_admin_user` verifies the entire overlay div is absent

When future stories implement the views, they **uncomment the button markup** in
`institution/partials/superadmin_overlay.html`. No template structure change is needed.

**Story-to-button mapping:**
| Button | Activating Story | URL to link |
|--------|-----------------|-------------|
| Move Patient | Story 2.6 | `institution:superadmin-patient-move` |
| Edit Subscription | Story 3.3 (via institution edit) | `institution:institution-edit` |
| Suspend User | Story 3.2 | `institution:institution-user-deactivate` |

---

### CSRF in Inclusion Tags — Technical Deep Dive

Django's `inclusion_tag` renders sub-templates with a plain `Context` object, NOT a
`RequestContext`. This means `{% csrf_token %}` does NOT work automatically inside the
overlay template. The correct solution used in this story:

```python
# institution_tags.py
from django.middleware.csrf import get_token

def superadmin_overlay(context):
    request = context.get('request')
    csrf_token_value = get_token(request)  # generates/retrieves the CSRF cookie
    return {
        ...
        'csrf_token': csrf_token_value,
    }
```

```html
<!-- superadmin_overlay.html — explicit CSRF input -->
<input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
```

`get_token(request)` sets the CSRF cookie on the response (if not already set) and returns
the token string. This is the Django-approved pattern for CSRF in inclusion tags.
See Django source: `django/middleware/csrf.py` — `get_token(request)`.

---

### Overlay Placement in AdminLTE 3.2

The overlay is placed INSIDE `<div class="content-wrapper">`, BEFORE `<div class="content-header">`.

```
.wrapper
├── .main-header.navbar  (position:fixed; top:0)
├── .main-sidebar        (position:fixed; left:0)
└── .content-wrapper     (margin-left:250px; margin-top:57px)
    ├── #superadmin-context-banner   ← OVERLAY HERE
    ├── .content-header
    └── section.content
```

This placement:
- Respects the sidebar width (doesn't overlap `.main-sidebar`)
- Sits below the navbar (below the 57px fixed navbar)
- Scrolls with page content (acceptable for admin metadata)
- Zero CSS changes required — standard block-level div in normal flow

If Rasika wants the banner to be "sticky" (stays at top while scrolling):
```css
/* Add to a stylesheet or inline style on the banner div */
#superadmin-context-banner {
    position: sticky;
    top: 0;
    z-index: 1029;  /* below AdminLTE navbar (z-index: 1030) */
}
```
This is an optional enhancement — document it in the story but do NOT implement unless requested.

---

### Project Structure Notes

**Files CREATED in this story:**
- `institution/templatetags/__init__.py` — empty, required by Python package
- `institution/templatetags/institution_tags.py` — `superadmin_overlay` inclusion_tag
- `templates/institution/partials/superadmin_overlay.html` — overlay banner HTML
- `institution/tests/test_context_switching.py` — 10 tests covering all 4 ACs

**Files MODIFIED in this story:**
- `institution/views.py` — replace `institution_switch` stub with full POST handler
- `templates/src/base.html` — add `{% load institution_tags %}` + `{% superadmin_overlay %}`

**Files NOT touched:**
- `institution/models.py` — no model changes
- `institution/urls.py` — already registered `institution-switch` URL in Story 2.1
- `ndas/settings.py` — no changes needed
- Any migration files — no schema changes

---

### Prerequisite Verification Checklist

Before starting implementation, verify:
- [ ] `institution/views.py` exists with `institution_selector` and `institution_switch` stub (Story 2.1)
- [ ] `institution/urls.py` has `institution-switch` URL registered (Story 2.1)
- [ ] `ndas/urls.py` has `path("institution/", include("institution.urls"))` (Story 2.1)
- [ ] `institution_context` context processor registered in `settings.py` (Story 1.3)
  - `institution.context_processors.institution_context` in `TEMPLATES[0]['OPTIONS']['context_processors']`
  - Provides `active_institution`, `user_type`, `is_superadmin` to all templates
- [ ] `InstitutionContextMiddleware` at position 13 in `MIDDLEWARE` (Story 1.3)
- [ ] `MULTI_INSTITUTION_ENABLED` in `settings.py` (Story 1.6)

If any of these are missing, add them before implementing Story 2.2.

---

### References

- Architecture: `{% superadmin_overlay %}` in `src/base.html`; banner: "Viewing as: [Name] [Switch ▼]" [Source: `_bmad-output/planning-artifacts/architecture.md#Frontend Architecture`]
- Architecture: `institution-switch` URL name; `institution_switch` view function [Source: `_bmad-output/planning-artifacts/architecture.md#Naming Patterns`]
- Architecture: `session['active_institution_id']` set on context switch; full page reload [Source: `_bmad-output/planning-artifacts/architecture.md#API & Communication Patterns`]
- Architecture: SUPERADMIN carries `is_superuser=True`; all Phase 1 permission checks unchanged [Source: `_bmad-output/planning-artifacts/architecture.md#Authentication & Security`]
- Architecture: Superadmin context resolution — reads `session['active_institution_id']` in `InstitutionContextMiddleware` [Source: `_bmad-output/planning-artifacts/architecture.md#Authentication & Security`]
- Architecture: `institution/templatetags/institution_tags.py` — `{% superadmin_overlay %}` [Source: `_bmad-output/planning-artifacts/architecture.md#Project Structure`]
- Epics: Story 2.2 ACs — POST sets session, banner renders, data scoped, action buttons [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.2`]
- FR51: Superadmin context switch via persistent on-screen selector [Source: `_bmad-output/planning-artifacts/epics.md#FR51`]
- Story 2.1: `institution_switch` stub + `institution/urls.py` + `ndas/urls.py` change [Source: `_bmad-output/implementation-artifacts/2-1-institution-selector-screen.md`]
- Project context: Function-based views; `@require_POST` for POST-only endpoints [Source: `_bmad-output/project-context.md#Framework-Specific Rules`]
- Project context: `logger = logging.getLogger(__name__)` at module level [Source: `_bmad-output/project-context.md#Language-Specific Rules`]
- `base.html` structure: `{% load static %}` at line 2; overlay inside `.content-wrapper` before `.content-header` [Source: `templates/src/base.html`]
- Django docs: `get_token(request)` for CSRF in inclusion tags [Source: `django/middleware/csrf.py`]
- Settings: CSP already has `'unsafe-inline'` in `CSP_STYLE_SRC` — inline styles in overlay are permitted [Source: `ndas/settings.py:287,303`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
