# Story 2.1: Institution Selector Screen

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **superadmin**,
I want a dashboard showing all institutions as cards with their key metrics,
So that I can monitor the health of the entire network at a glance and navigate into any institution.

## Acceptance Criteria

1. **Given** the superadmin navigates to the institution selector screen (no active institution context in session)
   **When** the page loads
   **Then** a card grid is displayed showing every institution with: logo (or placeholder), name, subscription status badge, user count, patient count, and last activity timestamp

2. **Given** an institution has `subscription_status=EXPIRED`
   **When** its card is rendered
   **Then** a visually distinct status indicator differentiates it from ACTIVE and GRACE institutions

3. **Given** the superadmin has no `active_institution_id` in session
   **When** they access any institution-scoped view
   **Then** the middleware redirects them to this selector screen before any institution-scoped data is accessed

4. **Given** a new institution has just been created via the onboarding form
   **When** the superadmin returns to the selector screen
   **Then** the new institution card appears without requiring a server restart or cache flush

## Tasks / Subtasks

- [ ] Task 1: Create `institution/views.py` with `institution_selector` view (AC: #1, #2, #3, #4)
  - [ ] Implement SUPERADMIN-only access guard — redirect ADMIN to admin dashboard, USER to `manage-patients`
  - [ ] Query all institutions with annotated `user_count`, `patient_count`, `last_activity` using `Count`/`Max`
  - [ ] Pop `session['active_institution_id']` on selector load (clears stale institution context)
  - [ ] Pass `institutions` queryset to `institution/selector.html` template
  - [ ] See exact code in Dev Notes

- [ ] Task 2: Create `institution/urls.py` with `app_name = 'institution'` URL config (AC: #3)
  - [ ] Register `institution-selector` URL at `''` (index of `/institution/` prefix)
  - [ ] Add placeholder for `institution-switch` URL (POST endpoint — Story 2.2 implements the full view)
  - [ ] See exact URL config in Dev Notes

- [ ] Task 3: Register `institution/` URL prefix in `ndas/urls.py`
  - [ ] Add `path("institution/", include("institution.urls"))` to `urlpatterns`
  - [ ] Verify no URL conflicts with existing patterns (`patients/`, `users/`, `video/`, `reports/`, `problems/`)

- [ ] Task 4: Create `templates/institution/selector.html` card grid template (AC: #1, #2)
  - [ ] Extend `src/base.html` — page title "Institution Network"
  - [ ] Build AdminLTE Bootstrap 4.6 card grid — 3 columns on desktop (col-lg-4), 2 on tablet (col-md-6), 1 on mobile (col-12)
  - [ ] Per card: institution logo (or FontAwesome `fa-hospital` placeholder if no logo), name as card title, subscription status badge (ACTIVE=badge-success, GRACE=badge-warning, EXPIRED=badge-danger)
  - [ ] Per card footer: user count, patient count, last activity date (or "No activity yet" if null)
  - [ ] Per card: "Enter" button → POST to `institution:institution-switch` (stub URL — functional in Story 2.2)
  - [ ] Show "No institutions found" empty state if queryset is empty
  - [ ] See template structure in Dev Notes

- [ ] Task 5: Verify `InstitutionContextMiddleware` whitelist for selector URL (AC: #3)
  - [ ] Open `institution/middleware.py` and confirm the middleware skips redirect when `request.path` starts with the selector URL
  - [ ] If whitelist is absent: add `if request.path.startswith(reverse('institution:institution-selector')): return self.get_response(request)` before the redirect logic in the SUPERADMIN no-context branch
  - [ ] This prevents the infinite redirect loop: middleware redirects to selector → middleware runs on selector → would redirect again

- [ ] Task 6: Write tests in `institution/tests/test_selector.py` (AC: #1, #2, #3, #4)
  - [ ] See exact test code in Dev Notes

## Dev Notes

### Story 2.1 Position in the 13-Step Sequence

Story 2.1 = **Step 8** (Superadmin views + god-view dashboard):

```
1.  institution app — Institution model + migrations              ← Story 1.1 ✓ (ready-for-dev)
2.  CustomUser extensions — institution FK + user_type            ← Story 1.2 ✓ (ready-for-dev)
3.  InstitutionContextMiddleware                                  ← Story 1.3 ✓ (ready-for-dev)
4.  InstitutionScopedManager — all institution-FK models          ← Story 1.4 ✓ (ready-for-dev)
5.  Institution-aware upload_to callables                         ← Story 1.5 ✓ (ready-for-dev)
6.  Data migration — default_institution                          ← Story 1.6 ✓ (ready-for-dev)
7.  referral app — Referral + Notification models                 ← NOT required for this story
8.  Superadmin views + god-view dashboard                         ← THIS STORY (2.1)
```

**All Epic 1 stories (1.1–1.7) must be `done` with migrations applied before this story begins.**

Run before starting:
```bash
python manage.py showmigrations institution  # should show 0001_initial + 0002_default_institution_data applied
python manage.py showmigrations users         # should show institution FK + user_type migration applied
python manage.py showmigrations patients      # should show institution FK migration applied
python manage.py test institution             # should pass (Story 1.7 verified)
```

---

### Critical: Infinite Redirect Loop Prevention

`InstitutionContextMiddleware` (Story 1.3) redirects SUPERADMIN without `active_institution_id`
in session to the institution selector URL. If the middleware also runs on the selector URL itself,
this creates an infinite redirect loop.

**Story 1.3 should have added this whitelist in `InstitutionContextMiddleware`:**

```python
# institution/middleware.py — InstitutionContextMiddleware.process_request (or __call__)
from django.urls import reverse, NoReverseMatch

def __call__(self, request):
    if not settings.MULTI_INSTITUTION_ENABLED:
        return self.get_response(request)

    if not request.user.is_authenticated:
        return self.get_response(request)

    # ── Whitelist: never redirect on the selector itself ─────────────────────
    try:
        selector_url = reverse('institution:institution-selector')
        if request.path.startswith(selector_url):
            return self.get_response(request)
    except NoReverseMatch:
        pass  # institution URLs not yet registered; safe to skip
    # ─────────────────────────────────────────────────────────────────────────

    user_type = getattr(request.user, 'user_type', None)

    if user_type in ('ADMIN', 'USER'):
        request.institution = request.user.institution
    elif user_type == 'SUPERADMIN':
        active_id = request.session.get('active_institution_id')
        if active_id:
            try:
                from institution.models import Institution
                request.institution = Institution.objects.get(pk=active_id, is_active=True)
            except Institution.DoesNotExist:
                request.session.pop('active_institution_id', None)
                return redirect(reverse('institution:institution-selector'))
        else:
            return redirect(reverse('institution:institution-selector'))

    return self.get_response(request)
```

**Task 5 of this story explicitly requires verifying this whitelist exists.** If missing,
add it before any other redirect logic in the SUPERADMIN branch.

---

### Task 1: `institution/views.py` — Full Code

```python
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET
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
    """
    SUPERADMIN god-view: shows all institutions as cards with aggregate metrics.
    Destination for InstitutionContextMiddleware redirect when SUPERADMIN has no active context.

    AC: FR50 — superadmin network overview dashboard.
    """
    user_type = getattr(request.user, 'user_type', None)

    # Access guard: only SUPERADMIN can see the network selector
    if user_type != UserType.SUPERADMIN:
        if user_type == UserType.ADMIN:
            return redirect('institution:institution-admin-dashboard')
        return redirect('manage-patients')

    # Clear active institution context — being on the selector means no institution is selected
    request.session.pop('active_institution_id', None)

    # Aggregate all institutions with user count, patient count, last activity
    # NOTE: 'customuser' and 'patient' are the reverse related_query_names for:
    #   - CustomUser.institution FK (added in Story 1.2) — default: 'customuser'
    #   - Patient.institution FK    (added in Story 1.4) — default: 'patient'
    # If Story 1.2/1.4 defined explicit related_name values, update these strings to match.
    # Example: if related_name='institution_users' → use Count('institution_users')
    institutions = Institution.objects.annotate(
        user_count=Count('customuser', distinct=True),
        patient_count=Count('patient', distinct=True),
        last_activity=Max('patient__created_at'),
    ).select_related('created_by').order_by('name')

    return render(request, 'institution/selector.html', {
        'institutions': institutions,
        'page_title': 'Institution Network',
    })
```

**Annotation related_query_name verification (IMPORTANT):**

After Story 1.2 adds `CustomUser.institution` FK, check the FK declaration:
```python
# If Story 1.2 wrote this (no related_name):
institution = models.ForeignKey('institution.Institution', on_delete=models.SET_NULL, null=True, blank=True)
# → Use Count('customuser') in annotation ✓

# If Story 1.2 wrote this (with related_name):
institution = models.ForeignKey('institution.Institution', related_name='institution_users', ...)
# → Use Count('institution_users') in annotation ✓
```
Run `python manage.py shell -c "from institution.models import Institution; from django.db.models import Count; list(Institution.objects.annotate(uc=Count('customuser')))"` to verify before building the template.

---

### Task 2: `institution/urls.py` — Full Code

```python
from django.urls import path
from institution import views

app_name = 'institution'

urlpatterns = [
    # Story 2.1 — Institution Selector Screen (SUPERADMIN god-view)
    path('', views.institution_selector, name='institution-selector'),

    # Story 2.2 — Context Switching (POST only; full view implemented in Story 2.2)
    # Placeholder: redirects to selector until Story 2.2 implements the real view
    path('switch/<int:institution_id>/', views.institution_switch, name='institution-switch'),

    # Story 2.3 — Atomic Institution Onboarding
    # path('add/', views.institution_add, name='institution-add'),       ← Story 2.3

    # Story 2.4 — Superadmin Aggregate Analytics Dashboard
    # path('superadmin/', views.superadmin_dashboard, name='superadmin-dashboard'),  ← Story 2.4

    # Story 2.6 — Patient Move Between Institutions
    # path('patient-move/<int:patient_id>/', views.superadmin_patient_move, name='superadmin-patient-move'),  ← Story 2.6

    # Story 3.1 — Institution Admin Dashboard
    # path('admin/', views.institution_admin_dashboard, name='institution-admin-dashboard'),  ← Story 3.1
]
```

**`institution_switch` stub (required for Story 2.1 to avoid NoReverseMatch on template render):**

Add to `institution/views.py`:
```python
from django.views.decorators.http import require_POST

@login_required(login_url="user-login")
@require_POST
@ratelimit(key='user_or_ip', rate='10/m')
def institution_switch(request, institution_id):
    """
    Stub: full implementation in Story 2.2.
    Sets session active_institution_id and redirects to manage-patients.
    Story 2.2 will add the persistent overlay banner logic.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.SUPERADMIN:
        return redirect('manage-patients')

    try:
        institution = Institution.objects.get(pk=institution_id, is_active=True)
        request.session['active_institution_id'] = institution.pk
        logger.info(
            "SUPERADMIN %s switched context to institution %s (id=%d)",
            request.user.username, institution.name, institution.pk
        )
    except Institution.DoesNotExist:
        pass

    return redirect('manage-patients')
```

**Note:** Story 2.2 will **expand** `institution_switch` with the persistent overlay banner template
tag injection and full redirect logic. Do NOT create `institution-admin-dashboard` URL in
this story — Story 3.1 implements that view. The commented-out paths above document
planned URLs for future stories.

---

### Task 3: `ndas/urls.py` — Change Required

Add one line to `urlpatterns` in `ndas/urls.py`:

```python
# BEFORE (current ndas/urls.py):
urlpatterns = [
    path("admin/", admin.site.urls),
    path("users/", include("users.urls")),
    path("reports/", include("reports.urls")),
    path("problems/", include("problemlist.urls")),
    path("", include("patients.urls")),
    path("djrichtextfield/", include("djrichtextfield.urls")),
    path("video/", include("video.urls")),
    path("debug/bootstrap/", views.debug_bootstrap, name="debug-bootstrap"),
]

# AFTER — add institution/ before the root patients include:
urlpatterns = [
    path("admin/", admin.site.urls),
    path("institution/", include("institution.urls")),  # ← ADD THIS
    path("users/", include("users.urls")),
    path("reports/", include("reports.urls")),
    path("problems/", include("problemlist.urls")),
    path("", include("patients.urls")),
    path("djrichtextfield/", include("djrichtextfield.urls")),
    path("video/", include("video.urls")),
    path("debug/bootstrap/", views.debug_bootstrap, name="debug-bootstrap"),
]
```

Position matters: `institution/` must appear BEFORE the root `""` catch-all for patients to
avoid URL conflicts.

---

### Task 4: `templates/institution/selector.html` — Full Template

```django
{% extends 'src/base.html' %}
{% load static %}
{% block title %}Institution Network — NDAS{% endblock %}

{% block main_content %}
<div class="container-fluid">

  <!-- Page Header -->
  <div class="row mb-3">
    <div class="col-12">
      <div class="d-flex justify-content-between align-items-center">
        <h1 class="h3 mb-0">
          <i class="fas fa-network-wired mr-2 text-primary"></i>
          Institution Network
        </h1>
        {# Story 2.3 adds the "Onboard New Institution" button here #}
      </div>
      <p class="text-muted mt-1 mb-0">
        Select an institution to enter its context. Showing {{ institutions|length }} institution{{ institutions|length|pluralize }}.
      </p>
    </div>
  </div>

  {% if institutions %}
  <!-- Institution Card Grid -->
  <div class="row">
    {% for inst in institutions %}
    <div class="col-12 col-md-6 col-lg-4 mb-4">
      <div class="card h-100 shadow-sm
        {% if inst.subscription_status == 'EXPIRED' %}border-danger{% elif inst.subscription_status == 'GRACE' %}border-warning{% else %}border-success{% endif %}">

        <!-- Card Header: logo or placeholder -->
        <div class="card-header text-center py-3" style="background:#f8f9fa; min-height:80px; display:flex; align-items:center; justify-content:center;">
          {% if inst.logo %}
            <img src="{{ inst.logo.url }}" alt="{{ inst.name }} logo"
                 class="img-fluid" style="max-height:60px; max-width:180px; object-fit:contain;">
          {% else %}
            <i class="fas fa-hospital fa-3x text-secondary"></i>
          {% endif %}
        </div>

        <!-- Card Body: name + subscription badge -->
        <div class="card-body">
          <h5 class="card-title font-weight-bold mb-1">{{ inst.name }}</h5>
          <div class="mb-2">
            {% if inst.subscription_status == 'ACTIVE' %}
              <span class="badge badge-success"><i class="fas fa-check-circle mr-1"></i>Active</span>
            {% elif inst.subscription_status == 'GRACE' %}
              <span class="badge badge-warning text-dark"><i class="fas fa-exclamation-circle mr-1"></i>Grace Period</span>
              {% if inst.grace_period_end %}
                <small class="text-muted d-block mt-1">Expires: {{ inst.grace_period_end|date:"d M Y" }}</small>
              {% endif %}
            {% else %}
              <span class="badge badge-danger"><i class="fas fa-times-circle mr-1"></i>Expired</span>
            {% endif %}
          </div>
          <p class="text-muted small mb-0">Slug: <code>{{ inst.slug }}</code></p>
        </div>

        <!-- Card Footer: metrics -->
        <div class="card-footer bg-white">
          <div class="row text-center small">
            <div class="col-4 border-right">
              <div class="font-weight-bold text-primary">{{ inst.user_count }}</div>
              <div class="text-muted">Users</div>
            </div>
            <div class="col-4 border-right">
              <div class="font-weight-bold text-success">{{ inst.patient_count }}</div>
              <div class="text-muted">Patients</div>
            </div>
            <div class="col-4">
              <div class="font-weight-bold text-secondary">
                {% if inst.last_activity %}{{ inst.last_activity|date:"d M" }}{% else %}—{% endif %}
              </div>
              <div class="text-muted">Last Activity</div>
            </div>
          </div>
          <!-- Enter Institution button (POST to switch endpoint) -->
          <form method="post" action="{% url 'institution:institution-switch' inst.pk %}" class="mt-3">
            {% csrf_token %}
            <button type="submit" class="btn btn-primary btn-block btn-sm
              {% if inst.subscription_status == 'EXPIRED' %}btn-secondary{% endif %}">
              <i class="fas fa-sign-in-alt mr-1"></i>
              Enter Institution
            </button>
          </form>
        </div>

      </div>
    </div>
    {% endfor %}
  </div>

  {% else %}
  <!-- Empty state -->
  <div class="row justify-content-center mt-5">
    <div class="col-md-6 text-center">
      <i class="fas fa-hospital fa-5x text-muted mb-3"></i>
      <h4 class="text-muted">No Institutions Yet</h4>
      <p class="text-muted">Use the "Onboard New Institution" button to add the first institution.</p>
      {# Story 2.3 will add the onboarding button/link here #}
    </div>
  </div>
  {% endif %}

</div>
{% endblock %}
```

**Template notes:**
- `{{ inst.user_count }}` / `{{ inst.patient_count }}` come from the annotated queryset
- `{{ inst.last_activity }}` is `Max('patient__created_at')` — may be `None` for new institutions
- Badge colours: ACTIVE=`badge-success`, GRACE=`badge-warning text-dark`, EXPIRED=`badge-danger`
- This matches Bootstrap 4.6 badge classes (consistent with AdminLTE 3.2)
- The Enter button is a `<form>` POST (not a GET link) to satisfy Story 2.2's AC: "submitted via POST"
- EXPIRED institutions still show the Enter button (SUPERADMIN may need to access them for admin tasks)

---

### Task 6: `institution/tests/test_selector.py` — Full Code

```python
"""
institution/tests/test_selector.py

Tests for the Institution Selector Screen (Story 2.1).
AC: #1 (card grid with metrics), #2 (EXPIRED visually distinct),
    #3 (redirect for no-context SUPERADMIN), #4 (new institution appears immediately)
"""

import logging

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

logger = logging.getLogger(__name__)
User = get_user_model()


class SelectorTestBase(TestCase):
    """Shared setup: two institutions + three user types."""

    def setUp(self):
        self.active_inst = Institution.objects.create(
            name='Active Hospital',
            slug='active-hospital',
            subscription_status=SubscriptionStatus.ACTIVE,
            is_active=True,
        )
        self.grace_inst = Institution.objects.create(
            name='Grace Hospital',
            slug='grace-hospital',
            subscription_status=SubscriptionStatus.GRACE,
            is_active=True,
        )
        self.expired_inst = Institution.objects.create(
            name='Expired Hospital',
            slug='expired-hospital',
            subscription_status=SubscriptionStatus.EXPIRED,
            is_active=True,
        )

        # SUPERADMIN — institution=None, is_superuser=True
        self.superadmin = User.objects.create_user(
            username='superadmin_test', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator',
            mobile_primary='0771990001',
            user_type=UserType.SUPERADMIN,
            is_superuser=True,
            institution=None,
        )

        # ADMIN — bound to active_inst
        self.admin_user = User.objects.create_user(
            username='admin_test', password='Testpass1!',
            first_name='Admin', last_name='User',
            position='Administrator',
            mobile_primary='0771990002',
            user_type=UserType.ADMIN,
            institution=self.active_inst,
        )

        # USER (clinician) — bound to active_inst
        self.clinician = User.objects.create_user(
            username='clinician_test', password='Testpass1!',
            first_name='Regular', last_name='Clinician',
            position='Medical Officer',
            mobile_primary='0771990003',
            user_type=UserType.USER,
            institution=self.active_inst,
        )

        self.selector_url = reverse('institution:institution-selector')


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class SelectorAccessTest(SelectorTestBase):
    """AC #3: Only SUPERADMIN can access the selector directly."""

    def test_superadmin_can_access_selector(self):
        """SUPERADMIN with no session context sees the selector (200)."""
        client = Client()
        client.force_login(self.superadmin)
        # Ensure no active institution in session
        response = client.get(self.selector_url)
        self.assertEqual(response.status_code, 200,
            "SUPERADMIN should get 200 on institution selector")

    def test_admin_redirected_from_selector(self):
        """ADMIN user is redirected away from the selector screen."""
        client = Client()
        client.force_login(self.admin_user)
        response = client.get(self.selector_url)
        self.assertEqual(response.status_code, 302,
            "ADMIN should be redirected away from institution selector")

    def test_clinician_redirected_from_selector(self):
        """Regular USER (clinician) is redirected away from the selector screen."""
        client = Client()
        client.force_login(self.clinician)
        response = client.get(self.selector_url)
        self.assertEqual(response.status_code, 302,
            "Clinician USER should be redirected away from institution selector")

    def test_unauthenticated_redirected_to_login(self):
        """Unauthenticated request is redirected to login."""
        client = Client()
        response = client.get(self.selector_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'].lower())


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class SelectorContentTest(SelectorTestBase):
    """AC #1, #2: Card grid content and subscription status display."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.superadmin)

    def test_selector_shows_all_institutions(self):
        """AC #1: All institutions appear on the selector page."""
        response = self.client.get(self.selector_url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Active Hospital', content)
        self.assertIn('Grace Hospital', content)
        self.assertIn('Expired Hospital', content)

    def test_selector_shows_subscription_status_badges(self):
        """AC #1: Subscription status badges are rendered."""
        response = self.client.get(self.selector_url)
        content = response.content.decode()
        # ACTIVE: green badge
        self.assertIn('badge-success', content)
        # GRACE: warning badge
        self.assertIn('badge-warning', content)
        # EXPIRED: danger badge
        self.assertIn('badge-danger', content)

    def test_expired_institution_badge_is_danger(self):
        """AC #2: EXPIRED institution shows 'badge-danger' — visually distinct."""
        response = self.client.get(self.selector_url)
        content = response.content.decode()
        # Verify that 'Expired Hospital' name co-occurs with 'badge-danger' in the response
        # (Simple presence check — both must appear in the same page)
        self.assertIn('Expired Hospital', content)
        self.assertIn('badge-danger', content)

    def test_selector_shows_institution_slugs(self):
        """Slug displayed in each card."""
        response = self.client.get(self.selector_url)
        content = response.content.decode()
        self.assertIn('active-hospital', content)
        self.assertIn('grace-hospital', content)
        self.assertIn('expired-hospital', content)

    def test_enter_institution_button_present(self):
        """Each card has an Enter Institution button with correct form action."""
        response = self.client.get(self.selector_url)
        content = response.content.decode()
        self.assertIn('Enter Institution', content)
        self.assertIn('institution-switch', content)


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class SelectorSessionManagementTest(SelectorTestBase):
    """Visiting the selector clears stale active_institution_id from session."""

    def test_selector_clears_active_institution_session_key(self):
        """Visiting selector pops active_institution_id from session."""
        client = Client()
        client.force_login(self.superadmin)
        # Manually set a stale session value
        session = client.session
        session['active_institution_id'] = self.active_inst.pk
        session.save()

        response = client.get(self.selector_url)
        self.assertEqual(response.status_code, 200)
        # Session key should be cleared
        self.assertNotIn('active_institution_id', client.session,
            "Visiting selector should clear any active institution session context")


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class SelectorNewInstitutionTest(SelectorTestBase):
    """AC #4: New institution appears immediately without cache flush."""

    def test_new_institution_appears_without_restart(self):
        """AC #4: Newly created institution card appears on selector without any server restart."""
        client = Client()
        client.force_login(self.superadmin)

        # Create institution AFTER the client is set up (simulates onboarding)
        new_inst = Institution.objects.create(
            name='Brand New Hospital',
            slug='brand-new-hospital',
            subscription_status=SubscriptionStatus.ACTIVE,
            is_active=True,
        )

        # Next page load should show it immediately (no view-level caching)
        response = client.get(self.selector_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Brand New Hospital', response.content.decode(),
            "Newly created institution must appear on selector without server restart")
```

---

### Access Control Pattern — Why `user_type` Not `is_superuser`

Phase 2 architecture specifies: "all 37 Phase 1 permission checks using `is_superuser` remain
untouched." The selector view is a Phase 2 view — use `user_type == UserType.SUPERADMIN` for
Phase 2 routing decisions, not `is_superuser`. The architecture enforces:

```
SUPERADMIN: user_type=SUPERADMIN + is_superuser=True (always set together)
ADMIN:      user_type=ADMIN     + is_staff=False, is_superuser=False
USER:       user_type=USER      + is_staff=True, is_superuser=False
```

Using `user_type` is explicit, readable, and consistent with Phase 2 context processor rules.

---

### Query Performance Note

The annotated queryset in `institution_selector` makes 1 SQL query with joins:
```sql
SELECT institution.*, COUNT(DISTINCT customuser.id) AS user_count,
       COUNT(DISTINCT patient.id) AS patient_count,
       MAX(patient.created_at) AS last_activity
FROM institution
LEFT OUTER JOIN users_customuser ON customuser.institution_id = institution.id
LEFT OUTER JOIN patients_patient ON patient.institution_id = institution.id
GROUP BY institution.id
ORDER BY institution.name
```
This is efficient for up to 20–50 institutions (NFR20 supports 20+). No caching needed at
this scale. For very large deployments (100+ institutions), consider adding a DB index on
`institution_id` FK columns — which Stories 1.2 and 1.4 should have added via `db_index=True`.

---

### Settings Prerequisites Check

Before running the server after implementing this story, verify `ndas/settings.py` has:

```python
# 1. institution.apps.InstitutionConfig in INSTALLED_APPS (should exist from Story 1.1):
'institution.apps.InstitutionConfig',

# 2. InstitutionContextMiddleware at position 13, replacing SubscriptionCheckMiddleware
#    (added in Story 1.3):
'institution.middleware.InstitutionContextMiddleware',  # position 13

# 3. institution_context context processor (added in Story 1.3):
'institution.context_processors.institution_context',

# 4. MULTI_INSTITUTION_ENABLED (added in Story 1.6):
MULTI_INSTITUTION_ENABLED = config('MULTI_INSTITUTION_ENABLED', default=False, cast=bool)
```

If any of these are missing, add them as part of this story (they're marked as Story 1.3/1.6
prerequisites, not new work here).

---

### What Story 2.2 Adds On Top of Story 2.1

Story 2.2 (Superadmin Institution Context Switching) will:
- Expand `institution_switch` from a stub to a full implementation
- Add the persistent top banner `{% superadmin_overlay %}` to `src/base.html`
- Implement the `{% superadmin_overlay %}` template tag in `institution/templatetags/institution_tags.py`
- Add institution-specific action buttons visible only to SUPERADMIN

**Do NOT implement these in Story 2.1.**

---

### Project Structure Notes

**Files CREATED in this story:**
- `institution/views.py` — `institution_selector` view + `institution_switch` stub
- `institution/urls.py` — `app_name = 'institution'`, `institution-selector` + `institution-switch` URLs
- `templates/institution/selector.html` — SUPERADMIN card grid template
- `institution/tests/test_selector.py` — view access + content + session tests

**Files MODIFIED in this story:**
- `ndas/urls.py` — add `path("institution/", include("institution.urls"))` before patients include
- `institution/middleware.py` — add selector URL whitelist (if missing from Story 1.3)

**Files NOT touched:**
- `institution/models.py` — no model changes
- Any migration files — no schema changes
- `ndas/settings.py` — no changes (Story 1.3 and 1.6 added the needed settings)
- `src/base.html` — overlay banner is Story 2.2's work

---

### References

- Architecture: Step 8 — "Superadmin views + god-view dashboard" [Source: `_bmad-output/planning-artifacts/architecture.md#Decision Impact Analysis`]
- Architecture: `institution-selector` URL name + `institution_selector` view function [Source: `_bmad-output/planning-artifacts/architecture.md#Naming Patterns`]
- Architecture: "deliberately absent" institution filter for aggregate views — intentional, not a data leak [Source: `_bmad-output/planning-artifacts/architecture.md#Format Patterns`]
- Architecture: `institution_context` context processor injects `active_institution`, `user_type`, `is_superadmin` [Source: `_bmad-output/planning-artifacts/architecture.md#Frontend Architecture`]
- Architecture: Middleware — SUPERADMIN with no active context → redirect to institution selector [Source: `_bmad-output/planning-artifacts/architecture.md#Authentication & Security`]
- Architecture: App dependency rules — `institution/` must not import from apps it underlies [Source: `_bmad-output/planning-artifacts/architecture.md#Architectural Boundaries`]
- Epics: Story 2.1 ACs — card grid, EXPIRED visual distinction, middleware redirect [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.1`]
- FR50: Superadmin god-view dashboard — subscription status, user count, patient count, last activity [Source: `_bmad-output/planning-artifacts/epics.md#FR50`]
- FR51 (partial): Selector screen is the landing for context-switching flow; POST to switch endpoint [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.2`]
- Project context: Function-based views, mandatory decorator stack, `@require_GET` for read-only views [Source: `_bmad-output/project-context.md#Framework-Specific Rules`]
- Project context: `logger = logging.getLogger(__name__)` at module level [Source: `_bmad-output/project-context.md#Language-Specific Rules`]
- Project context: Extend `src/base.html` for authenticated views [Source: `_bmad-output/project-context.md#Framework-Specific Rules`]
- Story 1.3: `InstitutionContextMiddleware` sets `request.institution` + redirect logic [Source: `_bmad-output/implementation-artifacts/1-3-institution-context-middleware.md`]
- Story 1.2: `user_type` field on `CustomUser` using `UserType` TextChoices [Source: `_bmad-output/planning-artifacts/architecture.md#Data Architecture`]
- Settings: `RATELIMIT_ENABLE = config(...)` — use `@override_settings(RATELIMIT_ENABLE=False)` in tests if needed [Source: `ndas/settings.py:408`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
