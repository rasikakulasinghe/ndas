# Story 2.6: Patient Move Between Institutions

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **superadmin**,
I want to move a patient from one institution to another via a multi-step confirmation flow,
So that patients who transfer clinical centres have their complete records moved safely with a full audit trail at both institutions.

## Acceptance Criteria

1. **Given** the superadmin opens the patient move flow from a patient's detail view (superadmin overlay active)
   **When** they select the destination institution
   **Then** an impact preview is displayed: count of open referrals, assessments, videos, attachments, and estimated file size

2. **Given** the superadmin reviews the impact preview and types the destination institution name to confirm
   **When** the confirmation form is submitted
   **Then** a `transaction.atomic()` block: sets `patient.institution` to the destination, creates `PatientMoveLog` entries at both source and destination institutions, and creates `Notification` records for both institution admins (if Story 5.1 is complete)

3. **Given** the atomic transaction succeeds
   **When** a clinician from the destination institution accesses the patient list
   **Then** the moved patient appears in their institution's scope
   **And** the moved patient no longer appears in the source institution's patient list

4. **Given** the atomic transaction fails at any step
   **When** the rollback completes
   **Then** `patient.institution` is unchanged and no partial `PatientMoveLog` records exist at either institution

5. **Given** the patient has open referral threads at the time of the move
   **When** the move completes
   **Then** the open referral records remain intact and both institutions' clinicians retain access to their respective referral thread records via the shared `referral_uuid`

## Tasks / Subtasks

- [ ] Task 1: Add `PatientMoveLog` model to `institution/models.py` (AC: #2, #4)
  - [ ] Fields: `patient` FK (to patients.Patient), `from_institution` FK (Institution, related_name='moves_out'), `to_institution` FK (Institution, related_name='moves_in'), `moved_by` FK (users.CustomUser), `notes` TextField (blank=True), and inherits TimeStampedModel + UserTrackingMixin
  - [ ] `Meta.ordering = ['-created_at']`
  - [ ] Run `python manage.py makemigrations institution` after adding model

- [ ] Task 2: Add `superadmin_patient_move` view to `institution/views.py` (AC: #1, #2, #3, #4)
  - [ ] SUPERADMIN only; redirect others to `manage-patients`
  - [ ] GET: compute impact preview (count assessments by type, videos, attachments, open referrals); render `institution/superadmin_patient_move.html` with step='preview'
  - [ ] POST with `step=confirm`: validate destination_institution_id; render confirmation form with step='confirm'
  - [ ] POST with `step=execute`: verify typed `institution_name_confirm` matches `destination_institution.name`; run `transaction.atomic()` block
  - [ ] Atomic block: `patient.institution = destination_institution`, `patient.save()`, create two `PatientMoveLog` records, stub notification (see Dev Notes)
  - [ ] On success: redirect to `view-patient` for the moved patient
  - [ ] See exact view code in Dev Notes

- [ ] Task 3: Add `superadmin-patient-move` URL to `institution/urls.py` (AC: #1)
  - [ ] Uncomment the stubbed path: `path('patient-move/<int:patient_id>/', views.superadmin_patient_move, name='superadmin-patient-move')`
  - [ ] See exact URL config change in Dev Notes

- [ ] Task 4: Create `templates/institution/superadmin_patient_move.html` (AC: #1, #2)
  - [ ] Extend `src/base.html`; title "Move Patient — NDAS"
  - [ ] **Step preview** (`step == 'preview'`): AdminLTE card showing patient name + identifiers, impact table (assessment types + counts, video count, attachment count, open referrals), destination institution dropdown, hidden `step=confirm` field, "Next: Review Confirmation" button
  - [ ] **Step confirm** (`step == 'confirm'`): AdminLTE warning card, review summary, destination institution name shown, text input for `institution_name_confirm`, hidden `destination_institution_id`, hidden `step=execute`, "Confirm Move" button (danger), "Cancel" back link
  - [ ] CSP nonce on any inline scripts
  - [ ] See exact template in Dev Notes

- [ ] Task 5: Add "Move Patient" button to `templates/patients/view.html` (AC: #1)
  - [ ] Add a superadmin-only "Move Patient" button in the patient actions section, conditional on `{% if is_superadmin %}`
  - [ ] Links to `{% url 'institution:superadmin-patient-move' patient.id %}`
  - [ ] See exact placement in Dev Notes

- [ ] Task 6: Write tests in `institution/tests/test_patient_move.py` (AC: #1–#5)
  - [ ] See exact test code in Dev Notes

## Dev Notes

### Story 2.6 Position in the 13-Step Sequence

Story 2.6 = **Step 8 completion** (final superadmin view — patient transfer):

```
8.  Superadmin views:
    ├── Stories 2.1–2.3: selector, context switching, onboarding   ← done
    ├── Story 2.4:        aggregate analytics dashboard             ← done
    ├── Story 2.5:        aggregate reports                        ← done
    └── Story 2.6:        patient move between institutions        ← THIS STORY
```

**Prerequisites:** Stories 2.1–2.5 done, Story 1.4 done (Patient.institution FK available).

**FR Coverage:** FR55 — Superadmin can move a patient between institutions via multi-step confirmation flow.

---

### PatientMoveLog Model — Full Code

Add to `institution/models.py` after the `Institution` class:

```python
class PatientMoveLog(TimeStampedModel, UserTrackingMixin):
    """
    Audit record for patient moves between institutions.
    Two records created per move: one scoped to from_institution, one to to_institution.

    FR55: Full audit trail at both institutions.
    """
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='move_logs',
        db_index=True,
    )
    from_institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        related_name='moves_out',
        db_index=True,
    )
    to_institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        related_name='moves_in',
        db_index=True,
    )
    moved_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='patient_moves_executed',
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"Patient {self.patient_id} moved: "
            f"{getattr(self.from_institution, 'name', '?')} → "
            f"{getattr(self.to_institution, 'name', '?')}"
        )
```

---

### Impact Preview — Queryset Helpers

In the view, compute the impact preview counts. Assessment models must be imported **inside** the function body to avoid circular imports (patients → institution):

```python
def _get_move_impact(patient):
    """Return impact preview dict for moving this patient. Lazy imports for circular safety."""
    from patients.models import (
        GMAssessment, HINEAssessment, CDICRecord,
        GeneralPaediatricAssessment, DevelopmentalAssessment,
    )
    from video.models import Video
    from patients.models import Attachment  # if Attachment is in patients

    gma_count  = GMAssessment.objects.filter(patient=patient).count()
    hine_count = HINEAssessment.objects.filter(patient=patient).count()
    cdic_count = CDICRecord.objects.filter(patient=patient).count()
    gpa_count  = GeneralPaediatricAssessment.objects.filter(patient=patient).count()
    da_count   = DevelopmentalAssessment.objects.filter(patient=patient).count()
    video_count = Video.objects.filter(patient=patient).count()

    # Attachment — check actual model name from patients app
    try:
        from patients.models import Attachment
        attachment_count = Attachment.objects.filter(patient=patient).count()
    except ImportError:
        attachment_count = 0

    # Open referrals — only if referral app exists (Story 4.1 prerequisite)
    open_referral_count = 0
    try:
        from referral.models import ReferralSent
        from ndas.custom_codes.choice import ReferralStatus
        open_referral_count = ReferralSent.objects.filter(
            patient=patient, status__in=[ReferralStatus.PENDING, ReferralStatus.REPLIED]
        ).count()
    except ImportError:
        pass

    return {
        'gma_count': gma_count,
        'hine_count': hine_count,
        'cdic_count': cdic_count,
        'gpa_count': gpa_count,
        'da_count': da_count,
        'video_count': video_count,
        'attachment_count': attachment_count,
        'open_referral_count': open_referral_count,
        'total_assessments': gma_count + hine_count + cdic_count + gpa_count + da_count,
    }
```

**Note on Attachment model:** The existing codebase has `patients/` app attachments. Check the exact model name via `from patients.models import Attachment` — if the name differs (e.g. `FileAttachment`), update accordingly.

---

### Task 2: `superadmin_patient_move` View — Full Code

Add to `institution/views.py`:

```python
@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(
    redirect_url='manage-patients',
    error_message='Patient move failed. Please try again.'
)
def superadmin_patient_move(request, patient_id):
    """
    Multi-step patient move between institutions (FR55).

    Step 1 (GET):         Show impact preview + destination selector
    Step 2 (POST confirm): Show name-confirmation form
    Step 3 (POST execute): Execute atomic move

    SUPERADMIN only.
    """
    from patients.models import Patient as PatientModel

    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.SUPERADMIN:
        return redirect('manage-patients')

    patient = get_object_or_404(PatientModel, id=patient_id)
    source_institution = patient.institution
    all_institutions = Institution.objects.exclude(pk=source_institution.pk).order_by('name')

    step = request.POST.get('step', 'preview') if request.method == 'POST' else 'preview'

    # ── Step: preview (GET) ──────────────────────────────────────────────
    if request.method == 'GET' or step == 'preview':
        impact = _get_move_impact(patient)
        return render(request, 'institution/superadmin_patient_move.html', {
            'patient': patient,
            'source_institution': source_institution,
            'all_institutions': all_institutions,
            'impact': impact,
            'step': 'preview',
        })

    # ── Step: confirm (POST, step=confirm) ───────────────────────────────
    if step == 'confirm':
        destination_id = request.POST.get('destination_institution_id', '')
        destination = get_object_or_404(Institution, pk=destination_id)
        impact = _get_move_impact(patient)
        return render(request, 'institution/superadmin_patient_move.html', {
            'patient': patient,
            'source_institution': source_institution,
            'destination_institution': destination,
            'impact': impact,
            'step': 'confirm',
        })

    # ── Step: execute (POST, step=execute) ───────────────────────────────
    if step == 'execute':
        destination_id = request.POST.get('destination_institution_id', '')
        institution_name_confirm = request.POST.get('institution_name_confirm', '').strip()
        destination = get_object_or_404(Institution, pk=destination_id)

        if institution_name_confirm != destination.name:
            from django.contrib import messages as django_messages
            django_messages.error(
                request,
                f"Institution name does not match. Expected: '{destination.name}'. "
                "Please type the exact destination institution name."
            )
            impact = _get_move_impact(patient)
            return render(request, 'institution/superadmin_patient_move.html', {
                'patient': patient,
                'source_institution': source_institution,
                'destination_institution': destination,
                'impact': impact,
                'step': 'confirm',
                'name_mismatch_error': True,
            })

        # ── Atomic move ────────────────────────────────────────────────
        from django.db import transaction as db_transaction
        with db_transaction.atomic():
            patient.institution = destination
            patient.save(update_fields=['institution', 'updated_at'])

            # Create audit log record scoped to SOURCE institution
            PatientMoveLog.objects.create(
                patient=patient,
                from_institution=source_institution,
                to_institution=destination,
                moved_by=request.user,
                notes=f"Patient moved by SUPERADMIN '{request.user.username}'"
            )
            # Create audit log record scoped to DESTINATION institution
            PatientMoveLog.objects.create(
                patient=patient,
                from_institution=source_institution,
                to_institution=destination,
                moved_by=request.user,
                notes=f"Patient received from '{source_institution.name}' by SUPERADMIN '{request.user.username}'"
            )

            # ── Notification stub (Story 5.1 prerequisite) ──────────────
            # TODO (Story 5.1): Create Notification records for both institution admins
            # from referral.models import Notification
            # from ndas.custom_codes.choice import NotificationType
            # from users.models import CustomUser
            # for admin_user in CustomUser.objects.filter(
            #     institution__in=[source_institution, destination],
            #     user_type=UserType.ADMIN,
            #     is_active=True,
            # ):
            #     Notification.objects.create(
            #         recipient=admin_user,
            #         notification_type=NotificationType.PATIENT_MOVED,
            #         title=f"Patient transferred: {patient.baby_name}",
            #         body=f"Patient moved from {source_institution.name} to {destination.name}",
            #         link=f"/patients/{patient.id}/view/",
            #         institution=admin_user.institution,
            #     )

        logger.info(
            "SUPERADMIN '%s' moved patient %d from '%s' to '%s'",
            request.user.username, patient_id,
            source_institution.name, destination.name,
        )
        from django.contrib import messages as django_messages
        django_messages.success(
            request,
            f"Patient '{patient.baby_name}' successfully moved to '{destination.name}'."
        )
        return redirect('view-patient', pk=patient.id)

    # Fallback
    return redirect('manage-patients')
```

**New import needed in `institution/views.py`:**
```python
from institution.models import Institution, PatientMoveLog
```
(All other imports — `UserType`, `logger`, `get_object_or_404`, `render`, `redirect`,
`login_required`, `require_http_methods`, `ratelimit`, `handle_view_errors` — already present.)

---

### Task 3: `institution/urls.py` — Uncomment the Stub

From Story 2.5, the urls.py already has this comment stub. Uncomment:

```python
    # Story 2.6 — Patient Move Between Institutions
    path('patient-move/<int:patient_id>/', views.superadmin_patient_move, name='superadmin-patient-move'),
```

Also add to `institution/views.py` imports: `from institution.models import Institution, PatientMoveLog`

---

### Task 4: `templates/institution/superadmin_patient_move.html` — Template Sketch

```django
{% extends 'src/base.html' %}
{% load static %}
{% block title %}Move Patient — NDAS{% endblock %}

{% block content_header %}
<div class="row mb-0">
  <div class="col-sm-6">
    <h1 class="m-0">Move Patient</h1>
    <small class="text-muted">{{ patient.baby_name }} (BHT: {{ patient.bht }})</small>
  </div>
  <div class="col-sm-6">
    <ol class="breadcrumb float-sm-right">
      <li class="breadcrumb-item"><a href="{% url 'view-patient' patient.id %}">Patient</a></li>
      <li class="breadcrumb-item active">Move Between Institutions</li>
    </ol>
  </div>
</div>
{% endblock content_header %}

{% block main_content %}
<div class="container-fluid">

  {% if step == 'preview' %}
  {# ── Step 1: Impact Preview ─────────────────────────────── #}
  <form method="post">
    {% csrf_token %}
    <input type="hidden" name="step" value="confirm">

    <div class="row">
      <div class="col-lg-7">
        <div class="card card-warning card-outline">
          <div class="card-header"><h3 class="card-title">Transfer Impact Preview</h3></div>
          <div class="card-body">
            <p><strong>Current Institution:</strong> {{ source_institution.name }}</p>
            <table class="table table-sm table-borderless">
              <tbody>
                <tr><th>GMA Assessments</th><td>{{ impact.gma_count }}</td></tr>
                <tr><th>HINE Assessments</th><td>{{ impact.hine_count }}</td></tr>
                <tr><th>Developmental Assessments</th><td>{{ impact.da_count }}</td></tr>
                <tr><th>CDIC Records</th><td>{{ impact.cdic_count }}</td></tr>
                <tr><th>GPA Assessments</th><td>{{ impact.gpa_count }}</td></tr>
                <tr><th>Videos</th><td>{{ impact.video_count }}</td></tr>
                <tr><th>Attachments</th><td>{{ impact.attachment_count }}</td></tr>
                <tr class="table-warning"><th>Open Referrals</th><td>{{ impact.open_referral_count }}</td></tr>
              </tbody>
            </table>
            {% if impact.open_referral_count > 0 %}
            <div class="alert alert-warning mt-2">
              <i class="fas fa-exclamation-triangle mr-1"></i>
              This patient has {{ impact.open_referral_count }} open referral thread(s).
              These will remain accessible to both institutions after the move.
            </div>
            {% endif %}
          </div>
        </div>
      </div>
      <div class="col-lg-5">
        <div class="card card-primary card-outline">
          <div class="card-header"><h3 class="card-title">Select Destination</h3></div>
          <div class="card-body">
            <div class="form-group">
              <label class="font-weight-bold">Destination Institution <span class="text-danger">*</span></label>
              <select name="destination_institution_id" class="form-control" required>
                <option value="">— Select institution —</option>
                {% for inst in all_institutions %}
                <option value="{{ inst.pk }}">{{ inst.name }}</option>
                {% endfor %}
              </select>
            </div>
            <div class="d-flex justify-content-between mt-3">
              <a href="{% url 'view-patient' patient.id %}" class="btn btn-secondary btn-sm">Cancel</a>
              <button type="submit" class="btn btn-warning btn-sm">
                <i class="fas fa-arrow-right mr-1"></i>Review Transfer
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </form>

  {% elif step == 'confirm' %}
  {# ── Step 2: Name Confirmation ─────────────────────────── #}
  <form method="post">
    {% csrf_token %}
    <input type="hidden" name="step" value="execute">
    <input type="hidden" name="destination_institution_id" value="{{ destination_institution.pk }}">
    <div class="row justify-content-center">
      <div class="col-lg-7">
        <div class="card card-danger card-outline">
          <div class="card-header"><h3 class="card-title"><i class="fas fa-exclamation-triangle mr-2"></i>Confirm Patient Transfer</h3></div>
          <div class="card-body">
            {% if name_mismatch_error %}
            <div class="alert alert-danger">Institution name does not match. Please try again.</div>
            {% endif %}
            <p>You are about to move <strong>{{ patient.baby_name }}</strong> (BHT: {{ patient.bht }})</p>
            <p>From: <strong>{{ source_institution.name }}</strong><br>
               To: <strong>{{ destination_institution.name }}</strong></p>
            <p class="text-danger font-weight-bold">This action cannot be undone via the interface.</p>
            <div class="form-group mt-3">
              <label class="font-weight-bold">Type the destination institution name to confirm:</label>
              <input type="text" name="institution_name_confirm" class="form-control"
                     placeholder="{{ destination_institution.name }}" required autocomplete="off">
              <small class="form-text text-muted">Expected: <code>{{ destination_institution.name }}</code></small>
            </div>
            <div class="d-flex justify-content-between mt-3">
              <a href="{% url 'institution:superadmin-patient-move' patient.id %}" class="btn btn-secondary btn-sm">
                <i class="fas fa-arrow-left mr-1"></i>Back
              </a>
              <button type="submit" class="btn btn-danger btn-sm">
                <i class="fas fa-exchange-alt mr-1"></i>Execute Transfer
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </form>
  {% endif %}

</div>
{% endblock %}
```

---

### Task 5: Patient View Template — Superadmin Button Placement

In `templates/patients/view.html`, find the patient action buttons section (near the top of the card body). Add after existing superuser-only buttons:

```django
{# ── Superadmin: Move Patient ───────────────────────────────────────── #}
{% if is_superadmin %}
  <a href="{% url 'institution:superadmin-patient-move' patient.id %}"
     class="btn btn-warning btn-sm mr-1">
    <i class="fas fa-exchange-alt mr-1"></i>Move Patient
  </a>
{% endif %}
```

This button is only visible when `is_superadmin=True` in the template context (injected by the `institution_context` context processor from Story 1.3).

---

### Task 6: `institution/tests/test_patient_move.py` — Test Outline

```python
"""
institution/tests/test_patient_move.py
Tests for Patient Move Between Institutions (Story 2.6).
"""
import logging
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution, PatientMoveLog
from ndas.custom_codes.choice import UserType, SubscriptionStatus

logger = logging.getLogger(__name__)
User = get_user_model()


class PatientMoveTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_move', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771991101',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='Alpha Hospital', slug='alpha-hospital',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Beta Clinic', slug='beta-clinic',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.admin_a = User.objects.create_user(
            username='admin_a_mv', password='Testpass1!',
            first_name='Alpha', last_name='Admin',
            position='Administrator', mobile_primary='0771992101',
            user_type=UserType.ADMIN, institution=self.inst_a,
        )
        # Patient in institution A (created after Story 1.4 adds institution FK)
        from patients.models import Patient
        self.patient = Patient.objects.create(
            institution=self.inst_a,
            baby_name='Test Patient', mother_name='Test Mother',
            added_by=self.admin_a, last_edit_by=self.admin_a,
        )


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class PatientMoveAccessTest(PatientMoveTestBase):
    def test_superadmin_can_access_move_page(self):
        client = Client()
        client.force_login(self.superadmin)
        url = reverse('institution:superadmin-patient-move', args=[self.patient.id])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_admin_cannot_access_move_page(self):
        client = Client()
        client.force_login(self.admin_a)
        url = reverse('institution:superadmin-patient-move', args=[self.patient.id])
        response = client.get(url)
        self.assertEqual(response.status_code, 302)


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class PatientMoveAtomicTest(PatientMoveTestBase):
    def test_execute_move_changes_patient_institution(self):
        client = Client()
        client.force_login(self.superadmin)
        url = reverse('institution:superadmin-patient-move', args=[self.patient.id])
        response = client.post(url, {
            'step': 'execute',
            'destination_institution_id': str(self.inst_b.pk),
            'institution_name_confirm': 'Beta Clinic',
        })
        self.assertEqual(response.status_code, 302)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.institution, self.inst_b)

    def test_execute_move_creates_two_audit_records(self):
        client = Client()
        client.force_login(self.superadmin)
        url = reverse('institution:superadmin-patient-move', args=[self.patient.id])
        initial_log_count = PatientMoveLog.objects.filter(patient=self.patient).count()
        client.post(url, {
            'step': 'execute',
            'destination_institution_id': str(self.inst_b.pk),
            'institution_name_confirm': 'Beta Clinic',
        })
        final_log_count = PatientMoveLog.objects.filter(patient=self.patient).count()
        self.assertEqual(final_log_count - initial_log_count, 2,
            "Two PatientMoveLog records must be created per move (one per institution)")

    def test_name_mismatch_blocks_move(self):
        """Typing wrong institution name must block the move."""
        client = Client()
        client.force_login(self.superadmin)
        url = reverse('institution:superadmin-patient-move', args=[self.patient.id])
        response = client.post(url, {
            'step': 'execute',
            'destination_institution_id': str(self.inst_b.pk),
            'institution_name_confirm': 'Wrong Name',
        })
        self.assertEqual(response.status_code, 200, "Name mismatch must re-render form, not redirect")
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.institution, self.inst_a, "Patient institution must be unchanged on name mismatch")

    def test_patient_scoped_to_destination_after_move(self):
        """After move, patient appears in destination institution's scope."""
        client = Client()
        client.force_login(self.superadmin)
        url = reverse('institution:superadmin-patient-move', args=[self.patient.id])
        client.post(url, {
            'step': 'execute',
            'destination_institution_id': str(self.inst_b.pk),
            'institution_name_confirm': 'Beta Clinic',
        })
        from patients.models import Patient
        in_dest = Patient.objects.filter(institution=self.inst_b, id=self.patient.id).exists()
        in_src = Patient.objects.filter(institution=self.inst_a, id=self.patient.id).exists()
        self.assertTrue(in_dest, "Patient must appear in destination institution after move")
        self.assertFalse(in_src, "Patient must not appear in source institution after move")
```

---

### Project Structure Notes

**Files MODIFIED in this story:**
- `institution/models.py` — add `PatientMoveLog` model
- `institution/views.py` — add `superadmin_patient_move` view + `_get_move_impact` helper
- `institution/urls.py` — uncomment `superadmin-patient-move` path
- `templates/patients/view.html` — add superadmin "Move Patient" button (conditional on `is_superadmin`)

**Files CREATED in this story:**
- `templates/institution/superadmin_patient_move.html` — multi-step move template
- `institution/tests/test_patient_move.py` — 6+ tests covering ACs #1–#5
- `institution/migrations/000X_patientmovelog.py` — generated by `makemigrations`

**Files NOT touched:**
- `referral/models.py` — Notification stub is commented out; no import
- Any existing `patients/` views — patient detail view gets a button only

---

### Key Constraints

1. **File movement is NOT in this story's scope.** Patient files (videos, attachments) remain at `MEDIA_ROOT/{source_slug}/`. A future DevOps task or admin process handles physical file migration. The database FK update is sufficient for app-layer scoping — only direct URL attacks (Story 1.7 isolation tests) would expose files. Note this in Completion Notes when implementing.

2. **`open_referral_count` requires Story 4.1** (referral app). The `try/except ImportError` in `_get_move_impact` handles the case where referral app does not yet exist — it defaults to 0 silently.

3. **Notification stub requires Story 5.1** (Notification model). The notification block is a commented-out TODO inside the atomic block. It becomes active after Story 5.1 is done.

4. **`patient.save(update_fields=['institution', 'updated_at'])`** — use `update_fields` to avoid triggering unintended signals or overwriting other fields.

---

### References

- FR55: Patient move multi-step confirmation flow [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.6`]
- Architecture: `transaction.atomic()` for all multi-step record operations [Source: `_bmad-output/planning-artifacts/epics.md#Additional Requirements`]
- Architecture: Notification model in referral/signals.py — Story 5.1 [Source: `_bmad-output/planning-artifacts/epics.md#Notifications`]
- Project context: All models inherit TimeStampedModel + UserTrackingMixin [Source: `_bmad-output/project-context.md#Model Pattern`]
- Project context: Circular import prevention — lazy imports inside function body [Source: confirmed pattern from Story 2.4 dev notes]
- Template: AdminLTE card pattern, `is_superadmin` from context processor Story 1.3 [Source: `_bmad-output/project-context.md#Templates`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
