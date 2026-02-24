# Story 3.1: Institution Admin Dashboard

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **institution admin**,
I want a dashboard showing patient activity, assessment volume, referral status, and team activity all scoped to my institution,
So that I can monitor the health and productivity of my clinical team without requiring superadmin involvement.

## Acceptance Criteria

1. **Given** the institution admin navigates to the admin dashboard
   **When** the page loads
   **Then** a four-quadrant AdminLTE card layout is displayed with institution-scoped data:
   - Quadrant 1: Patient stats by status (Active, Discharged, etc.)
   - Quadrant 2: Assessment activity by type for the current month (GMA, HINE, CDIC, GPA, DA counts)
   - Quadrant 3: Referral activity (sent / received / pending / closed counts)
   - Quadrant 4: Team activity (total user count, most active clinicians this month)

2. **Given** all four dashboard quadrants query the institution's data
   **When** the queries execute
   **Then** every query uses `.for_institution(request.institution)` — zero cross-institution data is returned

3. **Given** the institution has just been onboarded (empty state — no patients, no activity)
   **When** the dashboard loads
   **Then** all quadrants display zeros without raising errors

4. **Given** only ADMIN users access this dashboard
   **When** a USER or SUPERADMIN navigates to the admin dashboard URL
   **Then** they are redirected appropriately — USER to the clinician view (`home`), SUPERADMIN to the superadmin dashboard (`institution:superadmin-dashboard`)

## Tasks / Subtasks

- [ ] Task 1: Add `institution_admin_dashboard` view to `institution/views.py` (AC: #1, #2, #3, #4)
  - [ ] ADMIN-only access: redirect USER → `home`, redirect SUPERADMIN → `institution:superadmin-dashboard`
  - [ ] Patient stats: counts by pt_status using `Patient.objects.for_institution(request.institution)`
  - [ ] Assessment counts (current month): lazy-import assessment models inside function body (circular import safety)
  - [ ] Referral activity: stub as zeros until Story 4.1 is done (try/except ImportError)
  - [ ] Team activity: user count + annotation for most active clinicians this month
  - [ ] See exact view code in Dev Notes

- [ ] Task 2: Uncomment `institution-admin-dashboard` URL in `institution/urls.py` (AC: #1)
  - [ ] Uncomment: `path('admin/', views.institution_admin_dashboard, name='institution-admin-dashboard')`
  - [ ] See exact URL config in Dev Notes

- [ ] Task 3: Create `templates/institution/admin_dashboard.html` (AC: #1, #3)
  - [ ] Extend `src/base.html`; title "Admin Dashboard — [institution name]"
  - [ ] 2×2 AdminLTE card grid (patient stats, assessment activity, referral activity, team activity)
  - [ ] Empty state: zero values displayed gracefully (no "None" or template errors)
  - [ ] "Manage Clinicians" link → `institution:institution-clinician-list`; "Settings" link → `institution:institution-settings`
  - [ ] See exact template in Dev Notes

- [ ] Task 4: Add "Admin Dashboard" entry to `templates/src/main_sidebar_menu.html` (AC: #1)
  - [ ] Under Administration section, add link conditional on `user_type == 'ADMIN'`
  - [ ] URL: `{% url 'institution:institution-admin-dashboard' %}`
  - [ ] See exact placement in Dev Notes

- [ ] Task 5: Write tests in `institution/tests/test_admin_dashboard.py` (AC: #1–#4)
  - [ ] See exact test code in Dev Notes

## Dev Notes

### Story 3.1 Position in the 13-Step Sequence

Story 3.1 = **Step 9** (Institution admin views):

```
9.  Institution admin views + dashboard:
    ├── Story 3.1: institution admin dashboard   ← THIS STORY
    ├── Story 3.2: clinician account management
    ├── Story 3.3: institution branding setup
    └── Story 3.4: PDF report branding
```

**Prerequisites:** Stories 2.1–2.3 done (institution context middleware, context processor active).

**FR Coverage:** FR42 (admin role dashboard), FR56 — Institution admin dashboard with 4 quadrants.

---

### Patient Status Counts (Quadrant 1)

The existing `patients/models.py` Patient model uses a `pt_status` field added in Story 1.2.
Query it via:

```python
from patients.models import Patient
from django.db.models import Count

patient_qs = Patient.objects.for_institution(request.institution)

# Count by status
from ndas.custom_codes.ndas_enums import PtStatus  # or from choice.py if TextChoices
status_counts = (
    patient_qs
    .values('pt_status')
    .annotate(count=Count('id'))
    .order_by('pt_status')
)

# Or simpler individual counts:
total_patients = patient_qs.count()
# Add more pt_status-specific counts based on actual field choices
```

**Note:** If `pt_status` uses `PtStatus` enum (from `ndas_enums.py`), use its values. Check
`ndas/custom_codes/ndas_enums.py` for the actual enum values. The field was introduced in Story 1.2.

---

### Assessment Counts (Quadrant 2 — Current Month)

Assessment models live in `patients/` app. Import inside the function body:

```python
from django.utils import timezone

month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

# Lazy imports to prevent circular import (institution → patients would create a cycle)
from patients.models import (
    GMAssessment, HINEAssessment, CDICRecord,
    GeneralPaediatricAssessment, DevelopmentalAssessment,
)

def _assessment_count(model, institution, since):
    """Count assessments scoped to institution for the current month."""
    return model.objects.filter(
        patient__institution=institution,
        created_at__gte=since,
    ).count()

gma_count  = _assessment_count(GMAssessment, request.institution, month_start)
hine_count = _assessment_count(HINEAssessment, request.institution, month_start)
cdic_count = _assessment_count(CDICRecord, request.institution, month_start)
gpa_count  = _assessment_count(GeneralPaediatricAssessment, request.institution, month_start)
da_count   = _assessment_count(DevelopmentalAssessment, request.institution, month_start)
```

---

### Referral Activity Stub (Quadrant 3)

Until Story 4.1 is implemented, referral counts must default to 0:

```python
referral_sent_count = 0
referral_received_count = 0
referral_pending_count = 0
referral_closed_count = 0
try:
    from referral.models import ReferralSent, ReferralReceived
    from ndas.custom_codes.choice import ReferralStatus
    referral_sent_count = ReferralSent.objects.filter(
        from_institution=request.institution
    ).count()
    referral_received_count = ReferralReceived.objects.filter(
        to_institution=request.institution
    ).count()
    referral_pending_count = ReferralSent.objects.filter(
        from_institution=request.institution,
        status=ReferralStatus.PENDING,
    ).count()
    referral_closed_count = ReferralSent.objects.filter(
        from_institution=request.institution,
        status=ReferralStatus.CLOSED,
    ).count()
except ImportError:
    pass
```

---

### Team Activity (Quadrant 4)

```python
from users.models import CustomUser
from django.db.models import Count, Q

user_qs = CustomUser.objects.filter(
    institution=request.institution,
    is_active=True,
)
total_users = user_qs.count()

# Most active clinicians this month: count records they added
# UserTrackingMixin's added_by field is on all models
# Use Patient created_by as a proxy for activity
most_active = (
    CustomUser.objects.filter(institution=request.institution, is_active=True)
    .annotate(
        patients_added_this_month=Count(
            'patients_added',  # related_name from Patient.added_by
            filter=Q(patients_added__created_at__gte=month_start),
        )
    )
    .order_by('-patients_added_this_month')[:5]
)
```

**Note:** The `related_name` for `Patient.added_by` reverse FK may differ — check the actual
`UserTrackingMixin.added_by` `related_name`. Use `getattr()` or `try/except` if uncertain.

---

### Task 1: `institution_admin_dashboard` View — Full Code

Add to `institution/views.py`:

```python
@login_required(login_url="user-login")
@require_GET
@handle_view_errors(
    redirect_url='home',
    error_message='Dashboard failed to load. Please try again.'
)
def institution_admin_dashboard(request):
    """
    Institution admin role dashboard — 4 quadrants (FR56).

    ADMIN only. Redirects:
      USER       → 'home'
      SUPERADMIN → 'institution:superadmin-dashboard'
    """
    from django.utils import timezone
    from django.db.models import Count, Q

    user_type = getattr(request.user, 'user_type', None)
    if user_type == UserType.SUPERADMIN:
        return redirect('institution:superadmin-dashboard')
    if user_type != UserType.ADMIN:
        return redirect('home')

    institution = request.institution
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ── Quadrant 1: Patient stats ─────────────────────────────────────────
    from patients.models import Patient
    patient_qs = Patient.objects.for_institution(institution)
    total_patients = patient_qs.count()

    # ── Quadrant 2: Assessment activity (current month) ───────────────────
    from patients.models import (
        GMAssessment, HINEAssessment, CDICRecord,
        GeneralPaediatricAssessment, DevelopmentalAssessment,
    )

    def _count_this_month(model):
        return model.objects.filter(
            patient__institution=institution,
            created_at__gte=month_start,
        ).count()

    assessment_counts = {
        'gma':  _count_this_month(GMAssessment),
        'hine': _count_this_month(HINEAssessment),
        'cdic': _count_this_month(CDICRecord),
        'gpa':  _count_this_month(GeneralPaediatricAssessment),
        'da':   _count_this_month(DevelopmentalAssessment),
    }
    assessment_counts['total'] = sum(assessment_counts.values())

    # ── Quadrant 3: Referral activity (stub until Story 4.1) ──────────────
    referral_stats = {'sent': 0, 'received': 0, 'pending': 0, 'closed': 0}
    try:
        from referral.models import ReferralSent, ReferralReceived
        from ndas.custom_codes.choice import ReferralStatus
        referral_stats['sent']     = ReferralSent.objects.filter(from_institution=institution).count()
        referral_stats['received'] = ReferralReceived.objects.filter(to_institution=institution).count()
        referral_stats['pending']  = ReferralSent.objects.filter(from_institution=institution, status=ReferralStatus.PENDING).count()
        referral_stats['closed']   = ReferralSent.objects.filter(from_institution=institution, status=ReferralStatus.CLOSED).count()
    except ImportError:
        pass

    # ── Quadrant 4: Team activity ─────────────────────────────────────────
    from users.models import CustomUser
    total_users = CustomUser.objects.filter(institution=institution, is_active=True).count()
    recent_registrations = Patient.objects.for_institution(institution).order_by('-created_at')[:5]

    context = {
        'institution': institution,
        'total_patients': total_patients,
        'assessment_counts': assessment_counts,
        'referral_stats': referral_stats,
        'total_users': total_users,
        'recent_registrations': recent_registrations,
        'month_start': month_start,
    }
    return render(request, 'institution/admin_dashboard.html', context)
```

---

### Task 2: `institution/urls.py` — Uncomment Admin Dashboard

Uncomment (or add) in `institution/urls.py`:

```python
    # Story 3.1 — Institution Admin Dashboard
    path('admin/', views.institution_admin_dashboard, name='institution-admin-dashboard'),
```

---

### Task 3: `templates/institution/admin_dashboard.html` — Template Sketch

```django
{% extends 'src/base.html' %}
{% load static %}
{% block title %}Admin Dashboard — {{ institution.name }}{% endblock %}

{% block content_header %}
<div class="row mb-0">
  <div class="col-sm-6">
    <h1 class="m-0">Admin Dashboard</h1>
    <small class="text-muted">{{ institution.name }}</small>
  </div>
  <div class="col-sm-6">
    <ol class="breadcrumb float-sm-right">
      <li class="breadcrumb-item active">Admin Dashboard</li>
    </ol>
  </div>
</div>
{% endblock content_header %}

{% block main_content %}
<div class="container-fluid">

  {# Action bar #}
  <div class="row mb-3">
    <div class="col-12">
      <a href="{% url 'institution:institution-clinician-list' %}" class="btn btn-primary btn-sm mr-2">
        <i class="fas fa-users mr-1"></i>Manage Clinicians
      </a>
      <a href="{% url 'institution:institution-settings' %}" class="btn btn-secondary btn-sm">
        <i class="fas fa-cog mr-1"></i>Institution Settings
      </a>
    </div>
  </div>

  {# ── Row 1: Quadrant 1 + 2 ─────────────────────────────────────────── #}
  <div class="row">

    {# Quadrant 1: Patient Stats #}
    <div class="col-lg-6">
      <div class="card card-primary card-outline">
        <div class="card-header">
          <h3 class="card-title"><i class="fas fa-procedures mr-2"></i>Patient Statistics</h3>
        </div>
        <div class="card-body">
          <div class="row text-center">
            <div class="col-12">
              <h2 class="font-weight-bold">{{ total_patients }}</h2>
              <p class="text-muted mb-0">Total Patients</p>
            </div>
          </div>
          {% if total_patients == 0 %}
          <p class="text-center text-muted mt-3"><i class="fas fa-info-circle mr-1"></i>No patients registered yet.</p>
          {% endif %}
        </div>
      </div>
    </div>

    {# Quadrant 2: Assessment Activity #}
    <div class="col-lg-6">
      <div class="card card-info card-outline">
        <div class="card-header">
          <h3 class="card-title"><i class="fas fa-chart-bar mr-2"></i>Assessments This Month</h3>
        </div>
        <div class="card-body p-0">
          <table class="table table-sm mb-0">
            <tbody>
              <tr><th>GMA</th><td class="text-right">{{ assessment_counts.gma }}</td></tr>
              <tr><th>HINE</th><td class="text-right">{{ assessment_counts.hine }}</td></tr>
              <tr><th>Developmental</th><td class="text-right">{{ assessment_counts.da }}</td></tr>
              <tr><th>CDIC</th><td class="text-right">{{ assessment_counts.cdic }}</td></tr>
              <tr><th>GPA</th><td class="text-right">{{ assessment_counts.gpa }}</td></tr>
              <tr class="font-weight-bold table-light"><th>Total</th><td class="text-right">{{ assessment_counts.total }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

  </div>

  {# ── Row 2: Quadrant 3 + 4 ─────────────────────────────────────────── #}
  <div class="row">

    {# Quadrant 3: Referral Activity #}
    <div class="col-lg-6">
      <div class="card card-warning card-outline">
        <div class="card-header">
          <h3 class="card-title"><i class="fas fa-share-square mr-2"></i>Referral Activity</h3>
        </div>
        <div class="card-body p-0">
          <table class="table table-sm mb-0">
            <tbody>
              <tr><th>Sent</th><td class="text-right">{{ referral_stats.sent }}</td></tr>
              <tr><th>Received</th><td class="text-right">{{ referral_stats.received }}</td></tr>
              <tr><th>Pending</th><td class="text-right"><span class="badge badge-warning">{{ referral_stats.pending }}</span></td></tr>
              <tr><th>Closed</th><td class="text-right"><span class="badge badge-secondary">{{ referral_stats.closed }}</span></td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    {# Quadrant 4: Team Activity #}
    <div class="col-lg-6">
      <div class="card card-success card-outline">
        <div class="card-header">
          <h3 class="card-title"><i class="fas fa-user-md mr-2"></i>Team Activity</h3>
        </div>
        <div class="card-body">
          <p class="mb-2"><strong>Active Clinicians:</strong> {{ total_users }}</p>
          {% if recent_registrations %}
          <p class="text-muted mb-1"><small>Recent Registrations:</small></p>
          <ul class="list-unstyled mb-0">
            {% for p in recent_registrations %}
            <li><i class="fas fa-user-circle mr-1 text-muted"></i>
              <a href="{% url 'view-patient' p.id %}">{{ p.baby_name }}</a>
              <small class="text-muted">— {{ p.created_at|date:"d M Y" }}</small>
            </li>
            {% endfor %}
          </ul>
          {% else %}
          <p class="text-muted"><i class="fas fa-info-circle mr-1"></i>No patients registered yet.</p>
          {% endif %}
        </div>
      </div>
    </div>

  </div>

</div>
{% endblock %}
```

---

### Task 4: Sidebar Menu Entry

In `templates/src/main_sidebar_menu.html`, within the **Administration** section (around line 232–298), add after the existing admin links and before the closing `</ul>`:

```django
{# Institution Admin Dashboard — only for ADMIN role #}
{% if user_type == 'ADMIN' %}
<li class="nav-item {% if request.resolver_match.url_name == 'institution-admin-dashboard' %}active{% endif %}">
  <a href="{% url 'institution:institution-admin-dashboard' %}" class="nav-link">
    <i class="nav-icon fas fa-tachometer-alt"></i>
    <p>Admin Dashboard</p>
  </a>
</li>
{% endif %}
```

---

### Task 5: `institution/tests/test_admin_dashboard.py` — Test Outline

```python
"""
institution/tests/test_admin_dashboard.py
Tests for Institution Admin Dashboard (Story 3.1 — FR42, FR56).
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()


class AdminDashboardTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_dash', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771881001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(
            name='Test Hospital', slug='test-hospital',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.admin = User.objects.create_user(
            username='admin_dash', password='Testpass1!',
            first_name='Test', last_name='Admin',
            position='Administrator', mobile_primary='0771881002',
            user_type=UserType.ADMIN, institution=self.inst,
        )
        self.user = User.objects.create_user(
            username='user_dash', password='Testpass1!',
            first_name='Test', last_name='User',
            position='Medical Officer', mobile_primary='0771881003',
            user_type=UserType.USER, institution=self.inst,
        )
        self.url = reverse('institution:institution-admin-dashboard')


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class AdminDashboardAccessTest(AdminDashboardTestBase):
    def test_admin_can_access_dashboard(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_user_redirected_to_home(self):
        client = Client()
        client.force_login(self.user)
        response = client.get(self.url)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_superadmin_redirected_to_superadmin_dashboard(self):
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 302)


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class AdminDashboardEmptyStateTest(AdminDashboardTestBase):
    def test_empty_state_no_exceptions(self):
        """AC #3: Empty institution loads dashboard without errors."""
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_total_patients_zero(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        self.assertEqual(response.context['total_patients'], 0)

    def test_assessment_counts_zero(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        counts = response.context['assessment_counts']
        for key in ('gma', 'hine', 'cdic', 'gpa', 'da', 'total'):
            self.assertEqual(counts[key], 0, f"AC #3: {key} must be 0 for empty institution")

    def test_referral_stats_zero(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.url)
        stats = response.context['referral_stats']
        for key in ('sent', 'received', 'pending', 'closed'):
            self.assertEqual(stats[key], 0, f"AC #3: referral {key} must be 0 (stub)")
```

---

### Project Structure Notes

**Files MODIFIED in this story:**
- `institution/views.py` — add `institution_admin_dashboard` view
- `institution/urls.py` — uncomment `institution-admin-dashboard` path
- `templates/src/main_sidebar_menu.html` — add Admin Dashboard link (ADMIN-only conditional)

**Files CREATED in this story:**
- `templates/institution/admin_dashboard.html` — 4-quadrant dashboard template
- `institution/tests/test_admin_dashboard.py` — 7+ tests covering ACs #1–#4

**Files NOT touched:**
- `patients/` app — no changes to patient views
- `reports/` app — unchanged

---

### References

- FR56: 4-quadrant institution admin dashboard [Source: `_bmad-output/planning-artifacts/epics.md#Story 3.1`]
- FR42 (admin role): role-specific dashboard [Source: `_bmad-output/planning-artifacts/epics.md#FR42`]
- Architecture: `institution_context` context processor injects `user_type`, `is_superadmin`, `active_institution` [Source: `_bmad-output/planning-artifacts/epics.md#Additional Requirements`]
- Architecture: All institution-scoped views call `.for_institution(request.institution)` [Source: `_bmad-output/planning-artifacts/epics.md#ORM & Data Isolation`]
- Project context: circular import prevention — lazy imports inside function body [Source: confirmed pattern from Story 2.4]
- Project context: `@require_GET` for read-only views [Source: `_bmad-output/project-context.md#Framework-Specific Rules`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
