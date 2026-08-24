"""
CRUD operation tests for the patients app.

Covers: Patient add, view (list + detail), edit, delete.
"""

import json
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from patients.models import Patient, HINEAssessment

User = get_user_model()

# Use simple static storage so templates render without running collectstatic
STATIC_OVERRIDE = override_settings(
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
)


# ---------------------------------------------------------------------------
# Shared setUp mixin
# ---------------------------------------------------------------------------

class PatientTestBase(TestCase):
    """Shared setup for patient CRUD tests."""

    PASSWORD = 'SecurePass123!'

    def setUp(self):
        self.client = Client()

        self.superuser = User.objects.create_superuser(
            username='admin',
            password=self.PASSWORD,
            email='admin@test.com',
        )
        self.staff_user = User.objects.create_user(
            username='staff',
            password=self.PASSWORD,
            email='staff@test.com',
            is_staff=True,
        )
        self.other_staff = User.objects.create_user(
            username='other_staff',
            password='OtherPass123!',
            email='other@test.com',
            is_staff=True,
        )

        # Patient owned by staff_user
        self.patient = Patient.objects.create(
            bht='BHT-CRUD-001',
            baby_name='CRUD Baby',
            mother_name='CRUD Mother',
            gender='Male',
            dob_tob=timezone.now() - timezone.timedelta(days=30),
            mo_delivery='Normal vaginal delivery (NVD)',
            pog_wks=38,
            pog_days=0,
            birth_weight=3000,
            ofc=34,
            tp_mobile='0771234567',
            added_by=self.staff_user,
        )

    def _patient_form_data(self, bht='BHT-CRUD-NEW'):
        """Minimal valid PatientForm POST data."""
        return {
            'bht': bht,
            'baby_name': 'Test Baby',
            'mother_name': 'Test Mother',
            'gender': 'Male',
            'dob_tob': (timezone.now() - timezone.timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S'),
            'mo_delivery': 'Normal vaginal delivery (NVD)',
            'pog_wks': '38',
            'pog_days': '0',
            'apgar_1': '10',
            'apgar_5': '10',
            'apgar_10': '10',
            'birth_weight': '3000',
            'ofc': '34',
            'tp_mobile': '0771234568',
        }


# ---------------------------------------------------------------------------
# 1. Patient List View
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class PatientListViewTest(PatientTestBase):
    """Test patient manager (list) view."""

    def test_list_returns_200_for_authenticated_user(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('manage-patients'))
        self.assertEqual(response.status_code, 200)

    def test_list_redirects_unauthenticated(self):
        response = self.client.get(reverse('manage-patients'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


# ---------------------------------------------------------------------------
# 2. Patient Detail View
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class PatientDetailViewTest(PatientTestBase):
    """Test patient detail (view) operation."""

    def test_view_patient_returns_200(self):
        self.client.force_login(self.staff_user)
        url = reverse('view-patient', kwargs={'pk': self.patient.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view_patient_contains_patient_name(self):
        self.client.force_login(self.staff_user)
        url = reverse('view-patient', kwargs={'pk': self.patient.pk})
        response = self.client.get(url)
        self.assertContains(response, self.patient.baby_name)

    def test_view_nonexistent_patient_returns_404(self):
        self.client.force_login(self.staff_user)
        url = reverse('view-patient', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_view_patient_redirects_unauthenticated(self):
        url = reverse('view-patient', kwargs={'pk': self.patient.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


# ---------------------------------------------------------------------------
# 3. Patient Add View
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class PatientAddViewTest(PatientTestBase):
    """Test patient add (create) operation."""

    def test_add_get_returns_200(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('add-patient'))
        self.assertEqual(response.status_code, 200)

    def test_add_post_valid_creates_record(self):
        self.client.force_login(self.staff_user)
        data = self._patient_form_data(bht='BHT-NEW-001')
        response = self.client.post(reverse('add-patient'), data)
        # Should redirect after successful create
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Patient.objects.filter(bht='BHT-NEW-001').exists())

    def test_add_post_missing_required_field_returns_form(self):
        self.client.force_login(self.staff_user)
        data = self._patient_form_data(bht='BHT-INVALID')
        del data['baby_name']  # baby_name is required (no blank=True on model)
        response = self.client.post(reverse('add-patient'), data)
        # Form should be re-displayed with errors (not redirect)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Patient.objects.filter(bht='BHT-INVALID').exists())

    def test_add_post_duplicate_bht_returns_form(self):
        self.client.force_login(self.staff_user)
        data = self._patient_form_data(bht='BHT-CRUD-001')  # Already exists
        response = self.client.post(reverse('add-patient'), data)
        self.assertEqual(response.status_code, 200)

    def test_add_redirects_unauthenticated(self):
        response = self.client.get(reverse('add-patient'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


# ---------------------------------------------------------------------------
# 4. Patient Edit View
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class PatientEditViewTest(PatientTestBase):
    """Test patient edit (update) operation."""

    def test_edit_get_returns_200(self):
        self.client.force_login(self.staff_user)
        url = reverse('edit-patient', kwargs={'pk': self.patient.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_edit_get_prefills_existing_data(self):
        self.client.force_login(self.staff_user)
        url = reverse('edit-patient', kwargs={'pk': self.patient.pk})
        response = self.client.get(url)
        self.assertContains(response, self.patient.bht)

    def test_edit_post_valid_updates_record(self):
        self.client.force_login(self.staff_user)
        url = reverse('edit-patient', kwargs={'pk': self.patient.pk})
        data = self._patient_form_data(bht='BHT-CRUD-001')  # Keep same BHT
        data['baby_name'] = 'Updated Baby Name'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.baby_name, 'Updated Baby Name')

    def test_edit_post_invalid_returns_form(self):
        self.client.force_login(self.staff_user)
        url = reverse('edit-patient', kwargs={'pk': self.patient.pk})
        data = self._patient_form_data(bht='BHT-CRUD-001')
        data['birth_weight'] = 'not-a-number'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)

    def test_edit_nonexistent_patient_redirects(self):
        # @handle_view_errors(redirect_url='manage-patients') catches Http404
        # and redirects rather than propagating 404 to the client.
        self.client.force_login(self.staff_user)
        url = reverse('edit-patient', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('manage', response.url)

    def test_edit_redirects_unauthenticated(self):
        url = reverse('edit-patient', kwargs={'pk': self.patient.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


# ---------------------------------------------------------------------------
# 5. Patient Delete View
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class PatientDeleteViewTest(PatientTestBase):
    """Test patient delete operation (DELETE + JSON password)."""

    def _delete_request(self, pk, password, user):
        """Helper: send DELETE request with JSON password payload."""
        self.client.force_login(user)
        url = reverse('delete-patient', kwargs={'pk': pk})
        return self.client.delete(
            url,
            data=json.dumps({'password': password}),
            content_type='application/json',
        )

    def test_superuser_can_delete_any_patient(self):
        response = self._delete_request(self.patient.pk, self.PASSWORD, self.superuser)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'), msg=data)
        self.assertFalse(Patient.objects.filter(pk=self.patient.pk).exists())

    def test_staff_can_delete_own_patient(self):
        response = self._delete_request(self.patient.pk, self.PASSWORD, self.staff_user)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'), msg=data)
        self.assertFalse(Patient.objects.filter(pk=self.patient.pk).exists())

    def test_staff_cannot_delete_others_patient(self):
        response = self._delete_request(self.patient.pk, 'OtherPass123!', self.other_staff)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Patient.objects.filter(pk=self.patient.pk).exists())

    def test_wrong_password_rejected(self):
        self.client.force_login(self.superuser)
        url = reverse('delete-patient', kwargs={'pk': self.patient.pk})
        response = self.client.delete(
            url,
            data=json.dumps({'password': 'WrongPassword!'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)
        self.assertTrue(Patient.objects.filter(pk=self.patient.pk).exists())

    def test_missing_password_rejected(self):
        self.client.force_login(self.superuser)
        url = reverse('delete-patient', kwargs={'pk': self.patient.pk})
        response = self.client.delete(
            url,
            data=json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_nonexistent_patient_returns_error(self):
        # get_object_or_404 raises Http404 which is now explicitly caught
        # inside patient_delete and returned as 404 JSON.
        self.client.force_login(self.superuser)
        url = reverse('delete-patient', kwargs={'pk': 99999})
        response = self.client.delete(
            url,
            data=json.dumps({'password': self.PASSWORD}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertFalse(data.get('success'))

    def test_delete_nonexistent_patient_comment_corrected(self):
        # Confirms that the inner except Http404 handler in patient_delete
        # returns 404 JSON — NOT a redirect from @handle_view_errors.
        self.client.force_login(self.superuser)
        url = reverse('delete-patient', kwargs={'pk': 99999})
        response = self.client.delete(
            url,
            data=json.dumps({'password': self.PASSWORD}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertFalse(data.get('success'))
        self.assertEqual(data.get('error'), 'Not found')

    def test_delete_requires_authentication(self):
        url = reverse('delete-patient', kwargs={'pk': self.patient.pk})
        response = self.client.delete(
            url,
            data=json.dumps({'password': self.PASSWORD}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)


# ---------------------------------------------------------------------------
# 6. HINE Assessment Manager — score_range='normal' filter
# ---------------------------------------------------------------------------

@STATIC_OVERRIDE
class HINEManagerNormalScoreRangeFilterTest(PatientTestBase):
    """
    Regression tests for the HINE manager's 'normal' score_range filter.

    The filter previously used score__gte=60, but HINEAssessment.is_normal /
    severity_category define "Normal" as score > 73 (60-73 is "Mild
    Abnormality"). Clinicians filtering for 'normal' results were shown
    patients with a mild neurological abnormality. Part of
    spec-fix-medical-data-correctness.
    """

    def setUp(self):
        super().setUp()
        self.mild_abnormal_record = HINEAssessment.objects.create(
            patient=self.patient,
            date_of_assessment=timezone.now() - timezone.timedelta(days=5),
            score=70,  # Mild Abnormality per model (60 < score <= 73)
            assessment_done_by='Dr. Mild',
            added_by=self.staff_user,
        )
        self.normal_record = HINEAssessment.objects.create(
            patient=self.patient,
            date_of_assessment=timezone.now() - timezone.timedelta(days=3),
            score=75,  # Normal per model (score > 73)
            assessment_done_by='Dr. Normal',
            added_by=self.staff_user,
        )

    def test_normal_filter_excludes_mild_abnormality_score(self):
        """score=70 (60-73 'Mild Abnormality') must not appear under score_range=normal."""
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse('hine-assessment-manager'), {'score_range': 'normal'}
        )
        self.assertEqual(response.status_code, 200)
        record_ids = [r.id for r in response.context['hine_record_list']]
        self.assertNotIn(self.mild_abnormal_record.id, record_ids)

    def test_normal_filter_includes_normal_score(self):
        """score=75 (> 73, Normal) must appear under score_range=normal."""
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse('hine-assessment-manager'), {'score_range': 'normal'}
        )
        self.assertEqual(response.status_code, 200)
        record_ids = [r.id for r in response.context['hine_record_list']]
        self.assertIn(self.normal_record.id, record_ids)

    def test_badge_shows_normal_only_above_73(self):
        """
        Regression: templates/hine/manager.html's NORMAL badge previously used
        the same stale score>=60 threshold as the filter — a score of 70 would
        render a green 'NORMAL' badge even though it's excluded from the
        score_range=normal filter results. Both must now agree.
        """
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('hine-assessment-manager'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # score=70's row must not carry the NORMAL badge (it's 60-73, Mild
        # Abnormality) — a crude but sufficient check since manager.html has
        # exactly one NORMAL-badge occurrence per matching row.
        normal_badge_count = content.count('fa-check-circle mr-1"></i>NORMAL')
        self.assertEqual(
            normal_badge_count, 1,
            "Exactly one HINE record (score=75) should render the NORMAL badge, "
            "not the score=70 'Mild Abnormality' record too",
        )

    def test_patient_scoped_manager_normal_filter_excludes_mild_abnormality_score(self):
        """
        Regression: hine_assessment_manager_by_patients duplicates the same
        score_range='normal' filter/stats logic as the general manager, but
        independently — this proves the patient-scoped route was actually
        fixed too, not just the general one (they don't share code, so a
        revert to either one individually would go undetected without this).
        """
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse('hine-assessment-manager-patient', args=[self.patient.id]),
            {'score_range': 'normal'},
        )
        self.assertEqual(response.status_code, 200)
        record_ids = [r.id for r in response.context['hine_record_list']]
        self.assertNotIn(self.mild_abnormal_record.id, record_ids)
        self.assertIn(self.normal_record.id, record_ids)
