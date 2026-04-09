"""
CRUD operation tests for the patients app.

Covers: Patient add, view (list + detail), edit, delete.
"""

import json
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from patients.models import Patient

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
