# Story 2.4: Cross-Institution Aggregate Analytics Dashboard

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **superadmin**,
I want a read-only analytics dashboard showing activity and subscription health across all institutions,
So that I can identify institutions needing attention and monitor platform-wide clinical volume.

## Acceptance Criteria

1. **Given** the superadmin accesses the superadmin analytics dashboard
   **When** the page loads
   **Then** summary cards are shown for every institution: subscription state, user count, assessment volumes for the current month, and referral activity (sent/received/pending/closed)

2. **Given** the superadmin views the recent events audit log section
   **When** events are rendered
   **Then** cross-institution events appear in reverse chronological order (institution onboardings, subscription changes, patient moves)

3. **Given** the dashboard queries use `Patient.objects.all_institutions()` and equivalent cross-institution reads
   **When** the queries execute
   **Then** institution-scoped filtering is deliberately absent — this is an intentional superadmin aggregate view, not an accidental data leak

4. **Given** one or more institutions have zero activity this month
   **When** their cards are rendered
   **Then** zero values are displayed without raising errors — empty state is handled gracefully

## Tasks / Subtasks

- [ ] Task 1: Add `superadmin_dashboard` view to `institution/views.py` (AC: #1, #2, #3, #4)
  - [ ] SUPERADMIN-only access guard (redirect non-SUPERADMIN to `manage-patients`)
  - [ ] Query all institutions with `user_count` and `patient_count` annotations (`Count('customuser')`, `Count('patient')`)
  - [ ] Build per-institution assessment volume counts for current month using grouped ORM queries
  - [ ] Stub referral activity counts at zero (ReferralSent/ReferralReceived not yet available — Story 4.1)
  - [ ] Build `recent_institutions` (last 10 onboarded, newest first) for audit log section
  - [ ] Compute platform-wide summary totals (total institutions, total patients, total users)
  - [ ] See exact view code in Dev Notes

- [ ] Task 2: Uncomment `superadmin-dashboard` URL in `institution/urls.py` (AC: #1)
  - [ ] Change `# path('superadmin/', views.superadmin_dashboard, name='superadmin-dashboard'),` → active line
  - [ ] See exact URL config change in Dev Notes

- [ ] Task 3: Create `templates/institution/superadmin_dashboard.html` (AC: #1, #2, #4)
  - [ ] Extend `src/base.html`; title "Superadmin Dashboard"
  - [ ] Top summary row: 3 stat cards (total institutions, total patients, total users)
  - [ ] Per-institution cards: subscription badge, user count, patient count, assessment breakdown table, referral activity row
  - [ ] Zero-state handled gracefully (show "0" without error — Jinja `{{ val|default:0 }}`)
  - [ ] Recent events table (institution onboardings — newest first)
  - [ ] "Back to Selector" and "Onboard New Institution" action buttons in page header
  - [ ] See exact template in Dev Notes

- [ ] Task 4: Add link to superadmin dashboard from `templates/institution/selector.html` (AC: #1)
  - [ ] Add "View Analytics" button to the selector page header row
  - [ ] See exact change in Dev Notes

- [ ] Task 5: Write tests in `institution/tests/test_superadmin_dashboard.py` (AC: #1–#4)
  - [ ] See exact test code in Dev Notes

## Dev Notes

### Story 2.4 Position in the 13-Step Sequence

Story 2.4 = **Step 8** (Superadmin views, final piece of god-view dashboard):

```
8.  Superadmin views + god-view dashboard:
    ├── Story 2.1: institution_selector view + selector.html            ← done
    ├── Story 2.2: institution_switch + superadmin_overlay tag          ← done
    ├── Story 2.3: institution_add view + InstitutionOnboardingForm     ← done
    └── Story 2.4: superadmin_dashboard view (aggregate analytics)     ← THIS STORY
```

**Prerequisites:** Stories 2.1, 2.2, 2.3 must be `done`.
```bash
python manage.py test institution.tests.test_selector          # 2.1 tests pass
python manage.py test institution.tests.test_context_switching # 2.2 tests pass
python manage.py test institution.tests.test_institution_add   # 2.3 tests pass
```

**FR Coverage:** FR53 — Superadmin can view cross-institution aggregate analytics: assessment
volumes, referral activity, user counts, and subscription health across all institutions.

---

### Critical: Two Unavailable Models — Stub Gracefully

At the time Story 2.4 is implemented, **two models referenced in the ACs do not yet exist**:

| Model | Added In | Impact on Story 2.4 |
|-------|----------|---------------------|
| `ReferralSent` / `ReferralReceived` | Story 4.1 | Referral activity counts are stubbed to `0` |
| `AuditLog` | Story 2.6 | Patient move events not shown; use Institution.created_at for onboardings only |

**Do NOT attempt to import these models in this story.** The Dev Notes below document
explicit stubs and where to replace them when the models become available.

---

### Assessment Models Reference (CONFIRMED from codebase)

All assessment models are in `patients/models.py`. They link to Patient via `patient` ForeignKey.
Use `created_at` (from `TimeStampedModel`) for month filtering — consistent across all models.

| Model Class | App | `related_name` on Patient | Date field |
|-------------|-----|--------------------------|------------|
| `GMAssessment` | `patients` | `gm_assessments` | `date_of_assessment` |
| `HINEAssessment` | `patients` | `hine_assessments` | `date_of_assessment` |
| `CDICRecord` | `patients` | `cdic_records` | `assessment_date` (DateField) |
| `GeneralPaediatricAssessment` | `patients` | `gpa_assessments` | `assessment_date` (DateTimeField) |
| `DevelopmentalAssessment` | `patients` | `developmental_assessments` | `date_of_assessment` |

**Cross-institution query path:** Assessments do NOT have a direct `institution` FK.
They route through `patient__institution_id`:
```python
GMAssessment.objects.filter(created_at__gte=month_start)
    .values('patient__institution_id')
    .annotate(count=Count('id'))
    .values_list('patient__institution_id', 'count')
```
This gives `{institution_id: count}` in one query per assessment type — O(1) queries total.

**Why `created_at` not `date_of_assessment`:**
`created_at` is uniform across all models (from `TimeStampedModel`). Using it measures
*system activity this month* (when records were entered), not the clinical date of the
assessment. This is the correct metric for a platform activity dashboard.

---

### Reverse FK Names on Institution (CONFIRMED)

When CustomUser and Patient gain institution FKs (Stories 1.2 and 1.4), Django creates
reverse accessors on Institution using the model name in lowercase as the default:

```python
# In the annotation:
Institution.objects.annotate(
    user_count=Count('customuser', distinct=True),   # reverse FK: customuser_set → 'customuser'
    patient_count=Count('patient', distinct=True),   # reverse FK: patient_set → 'patient'
)
```

**If Story 1.2 or 1.4 added an explicit `related_name` to the institution FK**, the
annotation key must change to match. Verify before running:
```python
# Quick check in Django shell:
from users.models import CustomUser
print(CustomUser._meta.get_field('institution').related_query_name())  # Should be 'customuser'

from patients.models import Patient
print(Patient._meta.get_field('institution').related_query_name())  # Should be 'patient'
```
If these return different values, update the `Count(...)` keys in Task 1 accordingly.

---

### Task 1: `superadmin_dashboard` View — Full Code

Add to `institution/views.py` (alongside existing `institution_selector`, `institution_switch`,
`institution_add` from Stories 2.1–2.3):

```python
from django.utils import timezone


@login_required(login_url="user-login")
@require_GET
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(
    redirect_url='institution:institution-selector',
    error_message='Failed to load superadmin analytics dashboard.'
)
def superadmin_dashboard(request):
    """
    Cross-institution aggregate analytics dashboard (FR53).

    READ-ONLY view. Deliberately queries ALL institutions without scoping —
    this is an intentional superadmin aggregate, not an accidental data leak.
    See architecture.md: "Superadmin aggregate queries use .all_institutions() explicitly"

    SUPERADMIN only.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.SUPERADMIN:
        return redirect('manage-patients')

    # ── Date range for "current month" activity ───────────────────────────
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ── All institutions — intentional cross-institution read (FR53) ──────
    # .annotate() uses reverse FK defaults: 'customuser' and 'patient'
    # (verify with related_query_name() if Stories 1.2/1.4 used custom related_name)
    institutions = Institution.objects.annotate(
        user_count=Count('customuser', distinct=True),
        patient_count=Count('patient', distinct=True),
    ).select_related('created_by').order_by('name')

    # ── Assessment volumes this month — grouped by institution ─────────────
    # Each dict maps {institution_id: count} using patient__institution_id path
    # O(5) queries total regardless of institution count — scalable.
    from patients.models import (
        GMAssessment, HINEAssessment, CDICRecord,
        GeneralPaediatricAssessment, DevelopmentalAssessment
    )

    def _assessment_counts(model):
        """Return {institution_id: count} dict for the current month."""
        return dict(
            model.objects.filter(created_at__gte=month_start)
            .values('patient__institution_id')
            .annotate(count=Count('id'))
            .values_list('patient__institution_id', 'count')
        )

    gma_counts  = _assessment_counts(GMAssessment)
    hine_counts = _assessment_counts(HINEAssessment)
    cdic_counts = _assessment_counts(CDICRecord)
    gpa_counts  = _assessment_counts(GeneralPaediatricAssessment)
    da_counts   = _assessment_counts(DevelopmentalAssessment)

    # ── Build per-institution card data ────────────────────────────────────
    institution_data = []
    for inst in institutions:
        inst_id = inst.pk
        a_gma  = gma_counts.get(inst_id, 0)
        a_hine = hine_counts.get(inst_id, 0)
        a_cdic = cdic_counts.get(inst_id, 0)
        a_gpa  = gpa_counts.get(inst_id, 0)
        a_da   = da_counts.get(inst_id, 0)
        total_assessments = a_gma + a_hine + a_cdic + a_gpa + a_da

        institution_data.append({
            'institution': inst,
            'user_count': inst.user_count,
            'patient_count': inst.patient_count,
            'assessment_counts': {
                'gma': a_gma,
                'hine': a_hine,
                'cdic': a_cdic,
                'gpa': a_gpa,
                'da': a_da,
                'total': total_assessments,
            },
            # STUB: ReferralSent/ReferralReceived not yet available (Story 4.1).
            # Replace these zeros with real queries when Story 4.1 is done.
            # Query pattern will be:
            #   sent    = ReferralSent.objects.filter(from_institution=inst).count()
            #   received = ReferralReceived.objects.filter(institution=inst).count()
            #   pending = ReferralSent.objects.filter(from_institution=inst, status=ReferralStatus.PENDING).count()
            #   closed  = ReferralSent.objects.filter(from_institution=inst, status=ReferralStatus.CLOSED).count()
            'referral_counts': {
                'sent': 0,
                'received': 0,
                'pending': 0,
                'closed': 0,
            },
        })

    # ── Recent events: institution onboardings (newest first) ─────────────
    # STUB: AuditLog (patient moves) not yet available — Story 2.6 adds it.
    # When Story 2.6 is done, augment recent_events with AuditLog entries.
    recent_institutions = Institution.objects.select_related(
        'created_by'
    ).order_by('-created_at')[:10]

    # ── Platform-wide summary totals ─────────────────────────────────────
    total_institutions = len(institution_data)
    total_patients = sum(d['patient_count'] for d in institution_data)
    total_users = sum(d['user_count'] for d in institution_data)
    total_assessments_this_month = sum(
        d['assessment_counts']['total'] for d in institution_data
    )

    logger.info(
        "SUPERADMIN '%s' viewed aggregate analytics dashboard (%d institutions)",
        request.user.username, total_institutions
    )

    return render(request, 'institution/superadmin_dashboard.html', {
        'institution_data': institution_data,
        'recent_institutions': recent_institutions,
        'month_name': now.strftime('%B %Y'),
        'total_institutions': total_institutions,
        'total_patients': total_patients,
        'total_users': total_users,
        'total_assessments_this_month': total_assessments_this_month,
    })
```

**Required imports (add to the top of `institution/views.py`):**
```python
from django.utils import timezone
```
All other imports (`Count`, `logger`, `UserType`, `Institution`, `render`, etc.)
are already present from Stories 2.1–2.3.

**Import placement for assessment models:**
Assessment models are imported **inside** the view function to avoid circular imports.
`patients/` imports `institution/` models (for institution FK), so importing `patients`
models at module level in `institution/views.py` would create a circular dependency.
The inside-function import is safe: Django's app registry is fully resolved before
any view function executes.

---

### Task 2: `institution/urls.py` — Exact Change

Uncomment the `superadmin-dashboard` path (was commented out in Story 2.3):

```python
from django.urls import path
from institution import views

app_name = 'institution'

urlpatterns = [
    # Story 2.1 — Institution Selector Screen
    path('', views.institution_selector, name='institution-selector'),

    # Story 2.2 — Context Switching
    path('switch/<int:institution_id>/', views.institution_switch, name='institution-switch'),

    # Story 2.3 — Atomic Institution Onboarding
    path('add/', views.institution_add, name='institution-add'),

    # Story 2.4 — Superadmin Aggregate Analytics Dashboard  ← UNCOMMENT THIS
    path('superadmin/', views.superadmin_dashboard, name='superadmin-dashboard'),

    # Story 2.6 — Patient Move Between Institutions
    # path('patient-move/<int:patient_id>/', views.superadmin_patient_move, name='superadmin-patient-move'),

    # Story 3.1 — Institution Admin Dashboard
    # path('admin/', views.institution_admin_dashboard, name='institution-admin-dashboard'),
]
```

---

### Task 3: `templates/institution/superadmin_dashboard.html` — Full Template

```django
{% extends 'src/base.html' %}
{% load static %}
{% block title %}Superadmin Analytics Dashboard — NDAS{% endblock %}

{% block content_header %}
<div class="row mb-0">
  <div class="col-sm-6">
    <h1 class="m-0">Network Analytics</h1>
    <small class="text-muted">Assessment activity for {{ month_name }}</small>
  </div>
  <div class="col-sm-6">
    <ol class="breadcrumb float-sm-right">
      <li class="breadcrumb-item"><a href="{% url 'institution:institution-selector' %}">Network</a></li>
      <li class="breadcrumb-item active">Analytics</li>
    </ol>
  </div>
</div>
{% endblock content_header %}

{% block main_content %}
<div class="container-fluid">

  {# ── Action Buttons ─────────────────────────────────────────────────── #}
  <div class="row mb-3">
    <div class="col-12 d-flex justify-content-between align-items-center">
      <a href="{% url 'institution:institution-selector' %}" class="btn btn-secondary btn-sm">
        <i class="fas fa-arrow-left mr-1"></i>Back to Selector
      </a>
      <a href="{% url 'institution:institution-add' %}" class="btn btn-primary btn-sm">
        <i class="fas fa-plus-circle mr-1"></i>Onboard New Institution
      </a>
    </div>
  </div>

  {# ── Platform-wide Summary Row ──────────────────────────────────────── #}
  <div class="row">

    <div class="col-lg-3 col-6">
      <div class="small-box bg-info">
        <div class="inner">
          <h3>{{ total_institutions }}</h3>
          <p>Total Institutions</p>
        </div>
        <div class="icon"><i class="fas fa-hospital-alt"></i></div>
      </div>
    </div>

    <div class="col-lg-3 col-6">
      <div class="small-box bg-success">
        <div class="inner">
          <h3>{{ total_patients }}</h3>
          <p>Total Patients</p>
        </div>
        <div class="icon"><i class="fas fa-users"></i></div>
      </div>
    </div>

    <div class="col-lg-3 col-6">
      <div class="small-box bg-warning">
        <div class="inner">
          <h3>{{ total_users }}</h3>
          <p>Total Clinicians</p>
        </div>
        <div class="icon"><i class="fas fa-user-md"></i></div>
      </div>
    </div>

    <div class="col-lg-3 col-6">
      <div class="small-box bg-danger">
        <div class="inner">
          <h3>{{ total_assessments_this_month }}</h3>
          <p>Assessments This Month</p>
        </div>
        <div class="icon"><i class="fas fa-clipboard-list"></i></div>
      </div>
    </div>

  </div>

  {# ── Per-Institution Cards ──────────────────────────────────────────── #}
  {% if institution_data %}
    <h5 class="mb-3">Institution Breakdown</h5>
    <div class="row">
      {% for item in institution_data %}
        {% with inst=item.institution a=item.assessment_counts r=item.referral_counts %}
        <div class="col-lg-6 col-12">
          <div class="card card-outline
            {% if inst.subscription_status == 'ACTIVE' %}card-success
            {% elif inst.subscription_status == 'GRACE' %}card-warning
            {% else %}card-danger{% endif %}">

            <div class="card-header">
              <h3 class="card-title">
                {% if inst.logo %}
                  <img src="{{ inst.logo.url }}" alt="{{ inst.name }}" height="22" class="mr-2"
                       style="object-fit:contain;">
                {% else %}
                  <i class="fas fa-hospital mr-2 text-muted"></i>
                {% endif %}
                {{ inst.name }}
              </h3>
              <div class="card-tools">
                {% if inst.subscription_status == 'ACTIVE' %}
                  <span class="badge badge-success">ACTIVE</span>
                {% elif inst.subscription_status == 'GRACE' %}
                  <span class="badge badge-warning">GRACE</span>
                {% else %}
                  <span class="badge badge-danger">EXPIRED</span>
                {% endif %}
              </div>
            </div>

            <div class="card-body p-0">
              <table class="table table-sm table-borderless mb-0">
                <tbody>
                  <tr>
                    <th class="pl-3" style="width:55%">Clinicians</th>
                    <td>{{ item.user_count }}</td>
                  </tr>
                  <tr>
                    <th class="pl-3">Patients</th>
                    <td>{{ item.patient_count }}</td>
                  </tr>
                  <tr class="table-light">
                    <th class="pl-3" colspan="2">
                      <small class="text-muted">ASSESSMENTS — {{ month_name }}</small>
                    </th>
                  </tr>
                  <tr>
                    <td class="pl-4"><small>GMA</small></td>
                    <td>{{ a.gma }}</td>
                  </tr>
                  <tr>
                    <td class="pl-4"><small>HINE</small></td>
                    <td>{{ a.hine }}</td>
                  </tr>
                  <tr>
                    <td class="pl-4"><small>CDIC</small></td>
                    <td>{{ a.cdic }}</td>
                  </tr>
                  <tr>
                    <td class="pl-4"><small>GPA</small></td>
                    <td>{{ a.gpa }}</td>
                  </tr>
                  <tr>
                    <td class="pl-4"><small>Developmental</small></td>
                    <td>{{ a.da }}</td>
                  </tr>
                  <tr class="font-weight-bold">
                    <td class="pl-3"><small>Total assessments</small></td>
                    <td>{{ a.total }}</td>
                  </tr>
                  <tr class="table-light">
                    <th class="pl-3" colspan="2">
                      {# Referral activity: shows zeros until Story 4.1 adds ReferralSent/ReferralReceived #}
                      <small class="text-muted">REFERRALS</small>
                    </th>
                  </tr>
                  <tr>
                    <td class="pl-4"><small>Sent / Received</small></td>
                    <td>{{ r.sent }} / {{ r.received }}</td>
                  </tr>
                  <tr>
                    <td class="pl-4"><small>Pending / Closed</small></td>
                    <td>{{ r.pending }} / {{ r.closed }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="card-footer d-flex justify-content-between align-items-center p-2">
              <small class="text-muted">
                Slug: <code>{{ inst.slug }}</code>
              </small>
              <a href="{% url 'institution:institution-switch' inst.pk %}"
                 class="btn btn-xs btn-outline-secondary"
                 onclick="
                   {# POST to switch — trigger form submit #}
                   var f = document.getElementById('switch-form-{{ inst.pk }}');
                   if(f){ f.submit(); }
                   return false;
                 ">
                Switch to this institution
              </a>
              {# Hidden POST form for context switch #}
              <form id="switch-form-{{ inst.pk }}"
                    method="post"
                    action="{% url 'institution:institution-switch' inst.pk %}"
                    style="display:none;">
                {% csrf_token %}
              </form>
            </div>

          </div>
        </div>
        {% endwith %}
      {% endfor %}
    </div>

  {% else %}
    {# AC #4: Zero institutions — empty state without errors #}
    <div class="alert alert-info">
      <i class="fas fa-info-circle mr-2"></i>
      No institutions have been onboarded yet.
      <a href="{% url 'institution:institution-add' %}" class="alert-link ml-2">
        Onboard the first institution.
      </a>
    </div>
  {% endif %}

  {# ── Recent Events: Institution Onboardings ────────────────────────── #}
  {# Note: Patient move events (AuditLog) available after Story 2.6 #}
  <div class="row mt-3">
    <div class="col-12">
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">
            <i class="fas fa-history mr-2"></i>Recent Events
          </h3>
          <div class="card-tools">
            <small class="text-muted">Institution onboardings (newest first)</small>
          </div>
        </div>
        <div class="card-body p-0">
          <table class="table table-sm table-hover mb-0">
            <thead>
              <tr>
                <th>Event</th>
                <th>Institution</th>
                <th>By</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {% for inst in recent_institutions %}
              <tr>
                <td><span class="badge badge-success">Onboarded</span></td>
                <td>{{ inst.name }}</td>
                <td>
                  {% if inst.created_by %}{{ inst.created_by.get_full_name|default:inst.created_by.username }}
                  {% else %}<em class="text-muted">—</em>{% endif %}
                </td>
                <td>{{ inst.created_at|date:"d M Y" }}</td>
              </tr>
              {% empty %}
              <tr>
                <td colspan="4" class="text-center text-muted py-3">No events to display.</td>
              </tr>
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

**Template note — Switch button pattern:**
The per-institution "Switch to this institution" button uses a hidden POST form
and a small inline `onclick` handler to submit it. The `onclick` approach uses
`nonce="{{ request.csp_nonce }}"` is NOT needed here because it is an `onclick`
attribute (not a `<script>` tag). The CSPMiddleware allows `onclick` attributes.
However, if the project's CSP policy blocks inline event handlers, wrap in a
`<script nonce="{{ request.csp_nonce }}">` instead.

---

### Task 4: `templates/institution/selector.html` — Add Analytics Link

Add "View Analytics" button to the selector page header (alongside the existing
"Onboard New Institution" button from Story 2.3):

Find this section in `templates/institution/selector.html`:
```django
<a href="{% url 'institution:institution-add' %}"
   class="btn btn-primary">
  <i class="fas fa-plus-circle mr-1"></i>
  Onboard New Institution
</a>
```

Replace with (add the analytics button after the onboard button):
```django
<a href="{% url 'institution:institution-add' %}"
   class="btn btn-primary mr-2">
  <i class="fas fa-plus-circle mr-1"></i>
  Onboard New Institution
</a>
<a href="{% url 'institution:superadmin-dashboard' %}"
   class="btn btn-info">
  <i class="fas fa-chart-bar mr-1"></i>
  View Analytics
</a>
```

---

### Task 5: `institution/tests/test_superadmin_dashboard.py` — Full Code

```python
"""
institution/tests/test_superadmin_dashboard.py

Tests for Cross-Institution Aggregate Analytics Dashboard (Story 2.4).
AC: #1 (per-institution cards with metrics), #2 (recent events),
    #3 (intentional all-institution read), #4 (zero-state handling)
"""

import logging
from datetime import timedelta

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, Position

logger = logging.getLogger(__name__)
User = get_user_model()


class DashboardTestBase(TestCase):
    """
    Shared setup: SUPERADMIN + two institutions with patients and users.
    Assessment data is NOT created here (too complex); see specific test classes.
    """

    def setUp(self):
        # ── SUPERADMIN ────────────────────────────────────────────────────
        self.superadmin = User.objects.create_user(
            username='sa_dash', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771990001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )

        # ── Institution A ─────────────────────────────────────────────────
        self.inst_a = Institution.objects.create(
            name='Alpha Hospital', slug='alpha-hospital',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.admin_a = User.objects.create_user(
            username='admin_a', password='Testpass1!',
            first_name='Alpha', last_name='Admin',
            position='Administrator', mobile_primary='0771990010',
            user_type=UserType.ADMIN, institution=self.inst_a,
        )

        # ── Institution B ─────────────────────────────────────────────────
        self.inst_b = Institution.objects.create(
            name='Beta Clinic', slug='beta-clinic',
            subscription_status=SubscriptionStatus.GRACE, is_active=True,
            created_by=self.superadmin,
        )
        self.admin_b = User.objects.create_user(
            username='admin_b', password='Testpass1!',
            first_name='Beta', last_name='Admin',
            position='Administrator', mobile_primary='0771990020',
            user_type=UserType.ADMIN, institution=self.inst_b,
        )

        self.dashboard_url = reverse('institution:superadmin-dashboard')


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class DashboardAccessTest(DashboardTestBase):
    """Only SUPERADMIN can access the analytics dashboard."""

    def test_superadmin_can_access_dashboard(self):
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)

    def test_admin_redirected_from_dashboard(self):
        """ADMIN must not access superadmin analytics."""
        client = Client()
        client.force_login(self.admin_a)
        response = client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 302,
            "ADMIN must not access cross-institution analytics dashboard")

    def test_unauthenticated_redirected_to_login(self):
        client = Client()
        response = client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'].lower())

    def test_dashboard_only_accessible_via_get(self):
        """Read-only — POST not allowed."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.post(self.dashboard_url)
        self.assertEqual(response.status_code, 405,
            "POST must return 405 Method Not Allowed")


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class DashboardInstitutionCardsTest(DashboardTestBase):
    """AC #1: Per-institution summary cards show correct metrics."""

    def test_all_institutions_appear_on_dashboard(self):
        """AC #1: Every institution has a card on the dashboard."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Alpha Hospital', content,
            "Institution A must appear on the analytics dashboard")
        self.assertIn('Beta Clinic', content,
            "Institution B must appear on the analytics dashboard")

    def test_subscription_status_badges_shown(self):
        """AC #1: Subscription status badges reflect actual status."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.dashboard_url)
        content = response.content.decode()
        self.assertIn('ACTIVE', content,
            "ACTIVE badge must appear for Institution A")
        self.assertIn('GRACE', content,
            "GRACE badge must appear for Institution B")

    def test_user_counts_in_context(self):
        """AC #1: institution_data contains user counts."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.dashboard_url)
        institution_data = response.context['institution_data']
        # inst_a has admin_a (1 user), inst_b has admin_b (1 user)
        user_counts = {d['institution'].slug: d['user_count'] for d in institution_data}
        self.assertGreaterEqual(user_counts['alpha-hospital'], 1,
            "Alpha Hospital must have at least 1 user (the admin)")
        self.assertGreaterEqual(user_counts['beta-clinic'], 1,
            "Beta Clinic must have at least 1 user (the admin)")

    def test_summary_totals_in_context(self):
        """AC #1: Platform-wide totals are passed to template context."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.dashboard_url)
        self.assertIn('total_institutions', response.context)
        self.assertIn('total_patients', response.context)
        self.assertIn('total_users', response.context)
        self.assertIn('total_assessments_this_month', response.context)
        self.assertEqual(response.context['total_institutions'], 2,
            "Should count both institutions")


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class DashboardRecentEventsTest(DashboardTestBase):
    """AC #2: Recent events section shows institution onboardings."""

    def test_recent_institutions_in_context(self):
        """AC #2: recent_institutions is in context and includes both institutions."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.dashboard_url)
        self.assertIn('recent_institutions', response.context)
        slugs = [i.slug for i in response.context['recent_institutions']]
        self.assertIn('alpha-hospital', slugs)
        self.assertIn('beta-clinic', slugs)

    def test_recent_institutions_ordered_newest_first(self):
        """AC #2: Events appear in reverse chronological order."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.dashboard_url)
        recent = list(response.context['recent_institutions'])
        # Verify descending order by created_at
        for i in range(len(recent) - 1):
            self.assertGreaterEqual(
                recent[i].created_at, recent[i + 1].created_at,
                "Recent events must be ordered newest first (reverse chronological)"
            )


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class DashboardCrossInstitutionReadTest(DashboardTestBase):
    """AC #3: Dashboard reads ALL institutions without institution-scoped filtering."""

    def test_all_institutions_returned_regardless_of_active_context(self):
        """
        AC #3: Dashboard shows data for ALL institutions, not just the active context.
        This is an INTENTIONAL cross-institution read (FR53) — not a data leak.
        """
        # Set an active_institution_id in session (pointing to inst_a only)
        client = Client()
        client.force_login(self.superadmin)
        session = client.session
        session['active_institution_id'] = self.inst_a.pk
        session.save()

        response = client.get(self.dashboard_url)
        content = response.content.decode()

        # Both institutions must appear — not just inst_a
        self.assertIn('Alpha Hospital', content,
            "Institution A must appear even when it's the active context")
        self.assertIn('Beta Clinic', content,
            "Institution B must appear even when it's NOT the active context — "
            "superadmin aggregate dashboard must show ALL institutions")

    def test_institution_data_count_matches_all_institutions(self):
        """AC #3: institution_data length matches all institutions — no scoping applied."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.dashboard_url)
        total_in_db = Institution.objects.count()
        self.assertEqual(len(response.context['institution_data']), total_in_db,
            "AC #3: Dashboard must show all institutions without any institution-scoped filtering")


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class DashboardZeroStateTest(DashboardTestBase):
    """AC #4: Zero values display gracefully — no errors raised."""

    def test_institutions_with_zero_activity_rendered_without_error(self):
        """AC #4: Institutions with no patients, no assessments render without raising exceptions."""
        # Both inst_a and inst_b have no patients or assessments in setUp
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200,
            "AC #4: Dashboard must load without error even when all institutions have zero activity")

    def test_zero_patient_count_shown_as_zero(self):
        """AC #4: Zero patient count shown without error."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.dashboard_url)
        for item in response.context['institution_data']:
            # Each institution has 0 patients (no patients created in setUp)
            self.assertIsInstance(item['patient_count'], int,
                "patient_count must be an integer (including 0)")

    def test_assessment_counts_default_to_zero_for_empty_institutions(self):
        """AC #4: Assessment count dict always has all keys with integer values."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.dashboard_url)
        for item in response.context['institution_data']:
            counts = item['assessment_counts']
            for key in ['gma', 'hine', 'cdic', 'gpa', 'da', 'total']:
                self.assertIn(key, counts,
                    f"assessment_counts must have '{key}' key (even for zero-activity institutions)")
                self.assertIsInstance(counts[key], int,
                    f"assessment_counts['{key}'] must be an integer, not None or missing")

    def test_referral_counts_stub_returns_zeros(self):
        """Referral counts are stubbed at 0 until Story 4.1 adds ReferralSent/ReferralReceived."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.dashboard_url)
        for item in response.context['institution_data']:
            r = item['referral_counts']
            self.assertEqual(r['sent'], 0)
            self.assertEqual(r['received'], 0)
            self.assertEqual(r['pending'], 0)
            self.assertEqual(r['closed'], 0)

    def test_empty_institution_list_shows_empty_state(self):
        """AC #4: If no institutions exist, empty state renders without error."""
        # Delete all institutions
        Institution.objects.all().delete()
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200,
            "Dashboard must render without error when no institutions exist")
        content = response.content.decode()
        self.assertIn('No institutions', content,
            "Empty state message must be shown when institution list is empty")
```

---

### Circular Import Warning: Assessment Models

**CRITICAL:** Do NOT put assessment model imports at the top of `institution/views.py`.

`patients/` depends on `institution/` (Patient will have `institution FK` after Story 1.4),
so `institution/views.py` importing from `patients/` creates a **circular import** that
will cause `AppRegistryNotReady` or `ImportError` at Django startup.

**Safe pattern:** Import inside the view function body, AFTER the early-return guards:
```python
def superadmin_dashboard(request):
    # ... access guard first ...

    from patients.models import (
        GMAssessment, HINEAssessment, CDICRecord,
        GeneralPaediatricAssessment, DevelopmentalAssessment
    )
    # ... then use the models ...
```

Django's module import system resolves all apps before any view function runs,
so a function-level import is safe and avoids the startup circular dependency.

---

### Project Structure Notes

**Files CREATED in this story:**
- `templates/institution/superadmin_dashboard.html` — analytics dashboard template
- `institution/tests/test_superadmin_dashboard.py` — 12 tests covering ACs #1–#4

**Files MODIFIED in this story:**
- `institution/views.py` — add `superadmin_dashboard` view + `from django.utils import timezone`
- `institution/urls.py` — uncomment `path('superadmin/', ...)` for `superadmin-dashboard`
- `templates/institution/selector.html` — add "View Analytics" button

**Files NOT touched:**
- `institution/models.py` — no schema changes
- `ndas/urls.py` — already includes `institution/` prefix (Story 2.1)
- Any migration files — no schema changes

---

### Post-Story 4.1 Upgrade Path (When Referral Models Are Available)

After Story 4.1 (`referral` app with `ReferralSent` / `ReferralReceived`) is done,
update `superadmin_dashboard` view's referral stub section:

```python
# Replace the stub dict in institution_data loop with:
from ndas.custom_codes.choice import ReferralStatus
from referral.models import ReferralSent, ReferralReceived

sent     = ReferralSent.objects.filter(from_institution=inst).count()
received = ReferralReceived.objects.filter(institution=inst).count()
pending  = ReferralSent.objects.filter(from_institution=inst, status=ReferralStatus.PENDING).count()
closed   = ReferralSent.objects.filter(from_institution=inst, status=ReferralStatus.CLOSED).count()
```

Also update `test_referral_counts_stub_returns_zeros` — it documents current behavior
and should be replaced with real assertion tests once Story 4.1 is implemented.

### Post-Story 2.6 Upgrade Path (When AuditLog Is Available)

After Story 2.6 (`AuditLog` for patient moves) is done, augment the recent events section:
```python
from referral.models import AuditLog  # or wherever it ends up
recent_audit = AuditLog.objects.select_related('patient', 'from_institution', 'to_institution'
    ).order_by('-created_at')[:10]
```
Pass alongside `recent_institutions` and merge in the template for a unified timeline.

---

### References

- Epics: Story 2.4 ACs — per-institution cards, recent events, all_institutions read, zero state [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.4`]
- Architecture: FR53 — cross-institution aggregate analytics (assessment volumes, referral activity, user counts, subscription health) [Source: `_bmad-output/planning-artifacts/epics.md#FR53`]
- Architecture: "Superadmin aggregate queries use `.all_institutions()` explicitly" [Source: `_bmad-output/planning-artifacts/epics.md#ORM & Data Isolation`]
- Architecture: InstitutionScopedManager — `for_institution()` and `all_institutions()` methods [Source: `_bmad-output/planning-artifacts/epics.md#ORM & Data Isolation`]
- Assessment models (confirmed from codebase):
  - `GMAssessment` (patients/models.py:722) — `related_name='gm_assessments'`
  - `CDICRecord` (patients/models.py:960) — `related_name='cdic_records'`
  - `GeneralPaediatricAssessment` (patients/models.py:1230) — `related_name='gpa_assessments'`
  - `HINEAssessment` (patients/models.py:2425) — `related_name='hine_assessments'`
  - `DevelopmentalAssessment` (patients/models.py:2547) — `related_name='developmental_assessments'`
- Institution model: `name`, `slug`, `logo`, `subscription_status`, `subscription_start`, `grace_period_end`, `is_active`, `created_by` FK [Source: `institution/models.py`]
- Project context: Function-based views; mandatory decorator stack [Source: `_bmad-output/project-context.md#Framework-Specific Rules`]
- Project context: `from django.utils import timezone` for timezone-aware date arithmetic [Source: `_bmad-output/project-context.md`]
- Project context: Assessment imports inside view function to avoid circular import (patients → institution) [Source: `_bmad-output/project-context.md#App Dependency Rules`]
- Story 2.3: `superadmin-dashboard` URL stub already in `institution/urls.py` (commented out) [Source: `_bmad-output/implementation-artifacts/2-3-atomic-institution-onboarding.md#Task 3`]
- Django ORM: `values().annotate()` grouped aggregation pattern for cross-table counts [Django ORM aggregation documentation]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
