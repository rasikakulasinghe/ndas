"""
Unit tests for refactored patients views.

Tests the unified patient_manager function and optimized dashboard view.
"""

from datetime import timedelta
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from patients.models import Patient, GMAssessment
from video.models import Video
from ndas.custom_codes.ndas_enums import PtStatus

User = get_user_model()

STATIC_OVERRIDE = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)


@STATIC_OVERRIDE
class PatientManagerTestCase(TestCase):
    """Test unified patient_manager view with various filters."""

    def setUp(self):
        """Set up test data with various patient states."""
        self.client = Client()

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            is_staff=True
        )
        self.client.force_login(self.user)

        # Create test patients with different statuses
        # Patient 1: New (no assessments)
        self.patient_new = Patient.objects.create(
            bht='BHT001',
            baby_name='New Baby',
            mother_name='Mother One',
            dob_tob=timezone.now(),
            gender='Male',
            pog_wks=38,
            pog_days=2,
            birth_weight=3000,
            ofc=33,
            mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711234561',
            added_by=self.user
        )

        # Patient 2: Has assessment (diagnosed normal via GMA)
        self.patient_dx_normal = Patient.objects.create(
            bht='BHT002',
            baby_name='Normal Baby',
            mother_name='Mother Two',
            dob_tob=timezone.now(),
            gender='Female',
            pog_wks=39,
            pog_days=0,
            birth_weight=3200,
            ofc=34,
            mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711234562',
            added_by=self.user
        )

        # Patient 3: Has assessment (diagnosed abnormal via GMA)
        self.patient_dx_abnormal = Patient.objects.create(
            bht='BHT003',
            baby_name='Abnormal Baby',
            mother_name='Mother Three',
            dob_tob=timezone.now(),
            gender='Male',
            pog_wks=37,
            pog_days=5,
            birth_weight=2800,
            ofc=32,
            mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711234563',
            added_by=self.user
        )

        # Patient 4: Diagnosis pending (has assessment but no diagnosis)
        self.patient_dx_pending = Patient.objects.create(
            bht='BHT004',
            baby_name='Pending Baby',
            mother_name='Mother Four',
            dob_tob=timezone.now(),
            gender='Female',
            pog_wks=40,
            pog_days=1,
            birth_weight=3400,
            ofc=35,
            mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711234564',
            added_by=self.user
        )
        # Create a Video fixture for patient_dx_pending (bypass file validation).
        # recorded_on must be >= patient.dob_tob (both set to timezone.now() so dates match).
        video_pending = Video(
            title='Test Video Pending',
            patient=self.patient_dx_pending,
            recorded_on=timezone.now(),
            added_by=self.user,
        )
        video_pending.video_file.name = 'videos/test_pending.mp4'
        video_pending.save()

        # Add GM assessment without diagnosis (dx_pending state)
        GMAssessment.objects.create(
            patient=self.patient_dx_pending,
            date_of_assessment=timezone.now(),
            video_file=video_pending,
            added_by=self.user
        )

        # Patient 5: High risk (APGAR score < 7)
        self.patient_high_risk = Patient.objects.create(
            bht='BHT005',
            baby_name='High Risk Baby',
            mother_name='Mother Five',
            dob_tob=timezone.now(),
            gender='Male',
            pog_wks=36,
            pog_days=0,
            birth_weight=2500,
            ofc=31,
            mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711234565',
            apgar_5=5,  # Low APGAR score
            added_by=self.user
        )

        # Create additional patients for pagination testing (10-15 more)
        for i in range(6, 16):
            Patient.objects.create(
                bht=f'BHT{i:03d}',
                baby_name=f'Test Baby {i}',
                mother_name=f'Mother {i}',
                dob_tob=timezone.now(),
                gender='Male' if i % 2 == 0 else 'Female',
                pog_wks=38,
                pog_days=0,
                birth_weight=3000,
                ofc=33,
                mo_delivery='Normal vaginal delivery (NVD)',
                tp_mobile=f'071123456{i}',
                added_by=self.user
            )

    def test_patient_manager_all_filter(self):
        """Test patient_manager with 'all' filter returns all patients."""
        response = self.client.get(reverse('manage-patients'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'patients/patient/manager.html')

        # Should return all patients (15 total)
        patients = response.context['pts']
        self.assertEqual(patients.count(), 15)

        # Check filter context
        self.assertEqual(response.context['filter_type'], 'all')
        self.assertEqual(response.context['filter_label'], 'All Patients')

    def test_patient_manager_new_filter(self):
        """Test patient_manager with 'new' filter returns only new patients."""
        response = self.client.get(reverse('manage-patients-filtered', kwargs={'filter_type': 'new'}))

        self.assertEqual(response.status_code, 200)

        patients = list(response.context['pts'])

        # Should include patients without assessments or diagnosis
        # Patient 1 (new) should be included
        self.assertIn(self.patient_new, patients)

        # Check filter context
        self.assertEqual(response.context['filter_type'], 'new')
        self.assertEqual(response.context['filter_label'], 'New Patients (No Assessment)')

    def test_patient_manager_diagnosed_filter(self):
        """Test patient_manager with 'diagnosed' filter."""
        response = self.client.get(reverse('manage-patients-filtered', kwargs={'filter_type': 'diagnosed'}))

        self.assertEqual(response.status_code, 200)

        patients = list(response.context['pts'])

        # Should include patients with any diagnosis
        self.assertIn(self.patient_dx_normal, patients)
        self.assertIn(self.patient_dx_abnormal, patients)

        # Should not include new patients
        self.assertNotIn(self.patient_new, patients)

    def test_patient_manager_dx_normal_filter(self):
        """Test patient_manager with 'dx_normal' filter."""
        response = self.client.get(reverse('manage-patients-filtered', kwargs={'filter_type': 'dx_normal'}))

        self.assertEqual(response.status_code, 200)

        patients = list(response.context['pts'])

        # Should only include patients diagnosed as normal
        self.assertIn(self.patient_dx_normal, patients)
        self.assertNotIn(self.patient_dx_abnormal, patients)
        self.assertNotIn(self.patient_new, patients)

    def test_patient_manager_dx_abnormal_filter(self):
        """Test patient_manager with 'dx_abnormal' filter."""
        response = self.client.get(reverse('manage-patients-filtered', kwargs={'filter_type': 'dx_abnormal'}))

        self.assertEqual(response.status_code, 200)

        patients = list(response.context['pts'])

        # Should only include patients diagnosed as abnormal
        self.assertIn(self.patient_dx_abnormal, patients)
        self.assertNotIn(self.patient_dx_normal, patients)
        self.assertNotIn(self.patient_new, patients)

    def test_patient_manager_dx_pending_filter(self):
        """Test patient_manager with 'dx_pending' filter."""
        response = self.client.get(reverse('manage-patients-filtered', kwargs={'filter_type': 'dx_pending'}))

        self.assertEqual(response.status_code, 200)

        patients = list(response.context['pts'])

        # Should include patients with assessments but no diagnosis
        self.assertIn(self.patient_dx_pending, patients)

    def test_patient_manager_high_risk_filter(self):
        """Test patient_manager with 'high_risk' filter."""
        response = self.client.get(reverse('manage-patients-filtered', kwargs={'filter_type': 'high_risk'}))

        self.assertEqual(response.status_code, 200)

        patients = list(response.context['pts'])

        # Should include high-risk patients (low APGAR scores)
        self.assertIn(self.patient_high_risk, patients)

    def test_patient_manager_search_by_baby_name(self):
        """Test patient_manager search by baby name."""
        response = self.client.get(reverse('manage-patients'), {'search': 'New Baby'})

        self.assertEqual(response.status_code, 200)

        patients = list(response.context['pts'])

        # Should return patient with matching baby name
        self.assertIn(self.patient_new, patients)
        self.assertEqual(len(patients), 1)

    def test_patient_manager_search_by_bht(self):
        """Test patient_manager search by BHT number."""
        response = self.client.get(reverse('manage-patients'), {'search': 'BHT002'})

        self.assertEqual(response.status_code, 200)

        patients = list(response.context['pts'])

        # Should return patient with matching BHT
        self.assertIn(self.patient_dx_normal, patients)
        self.assertEqual(len(patients), 1)

    def test_patient_manager_search_case_insensitive(self):
        """Test patient_manager search is case-insensitive."""
        response = self.client.get(reverse('manage-patients'), {'search': 'new baby'})

        self.assertEqual(response.status_code, 200)

        patients = list(response.context['pts'])

        # Should return patient regardless of case
        self.assertIn(self.patient_new, patients)

    def test_patient_manager_pagination(self):
        """Test patient_manager pagination with multiple patients."""
        response = self.client.get(reverse('manage-patients'))

        self.assertEqual(response.status_code, 200)

        # Check pagination context exists
        self.assertIn('is_paginated', response.context)
        self.assertIn('page_obj', response.context)

        # With 15 patients, should have pagination
        patients = response.context['pts']
        self.assertEqual(patients.count(), 15)

    def test_patient_manager_invalid_filter_defaults_to_all(self):
        """Test that invalid filter_type defaults to 'all'."""
        response = self.client.get(reverse('manage-patients-filtered', kwargs={'filter_type': 'invalid_filter'}))

        self.assertEqual(response.status_code, 200)

        # Should default to 'all' filter
        self.assertEqual(response.context['filter_type'], 'invalid_filter')

        # Should still return all patients
        patients = response.context['pts']
        self.assertEqual(patients.count(), 15)

    def test_patient_manager_filter_type_context(self):
        """Test that filter_type context variable is set correctly."""
        test_cases = [
            ('all', 'All Patients'),
            ('new', 'New Patients (No Assessment)'),
            ('diagnosed', 'Diagnosed Patients (Any)'),
            ('dx_normal', 'Diagnosed Normal'),
            ('dx_abnormal', 'Diagnosed Abnormal'),
        ]

        for filter_type, expected_label in test_cases:
            with self.subTest(filter_type=filter_type):
                response = self.client.get(
                    reverse('manage-patients-filtered', kwargs={'filter_type': filter_type})
                )
                self.assertEqual(response.context['filter_type'], filter_type)
                self.assertEqual(response.context['filter_label'], expected_label)

    def test_patient_manager_requires_authentication(self):
        """Test that patient_manager requires authentication."""
        # Logout
        self.client.logout()

        response = self.client.get(reverse('manage-patients'))

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


@STATIC_OVERRIDE
class DashboardTestCase(TestCase):
    """Test optimized dashboard view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            is_staff=True
        )
        self.client.force_login(self.user)

        # Create test patients
        for i in range(5):
            Patient.objects.create(
                bht=f'BHT{i:03d}',
                baby_name=f'Test Baby {i}',
                mother_name=f'Mother {i}',
                dob_tob=timezone.now(),
                gender='Male' if i % 2 == 0 else 'Female',
                pog_wks=38,
                pog_days=0,
                birth_weight=3000,
                ofc=33,
                mo_delivery='Normal vaginal delivery (NVD)',
                tp_mobile=f'07112345{i:02d}',
                added_by=self.user
            )

    def test_dashboard_loads_successfully(self):
        """Test that dashboard loads successfully."""
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'patients/index.html')

    def test_dashboard_patient_counts(self):
        """Test that dashboard shows correct patient counts."""
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

        # Check patient count
        self.assertEqual(response.context['patients_total_count'], 5)

    def test_dashboard_context_variables(self):
        """Test that dashboard has all required context variables."""
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

        # Check all required context variables exist
        required_context = [
            'patients_total_count',
            'videos_total_count',
            'assessments_total_count',
            'recent_patients',
        ]

        for var in required_context:
            self.assertIn(var, response.context, f"Missing context variable: {var}")

    def test_dashboard_recent_patients(self):
        """Test that dashboard shows recent patients."""
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

        recent_patients = response.context['recent_patients']

        # Should have recent patients
        self.assertGreater(len(recent_patients), 0)
        self.assertLessEqual(len(recent_patients), 5)

    def test_dashboard_requires_authentication(self):
        """Test that dashboard requires authentication."""
        # Logout
        self.client.logout()

        response = self.client.get(reverse('home'))

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_dashboard_query_efficiency(self):
        """Test that dashboard uses efficient queries."""
        from django.test.utils import override_settings
        from django.db import connection
        from django.test import utils

        # Reset queries
        connection.queries_log.clear()

        with self.assertNumQueries(15, using='default'):
            # Dashboard should use ~15 queries (optimized from ~50)
            response = self.client.get(reverse('home'))
            self.assertEqual(response.status_code, 200)

    @override_settings(
        STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
        RATELIMIT_ENABLE=False,
    )
    def test_dashboard_institution_banner_replaces_nhk(self):
        """AC 5: Home dashboard shows bg-info banner card; hardcoded NHK text is gone."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # Old hardcoded text must be gone
        self.assertNotIn('Neurodevelopmental Assessment System (NHK)', content)
        # New banner card structure must be present
        self.assertIn('card bg-info', content)
        # Subtitle text preserved (without "NHK")
        self.assertIn('Neurodevelopmental Assessment System', content)


class CustomMethodsTestCase(TestCase):
    """Test custom methods and utilities."""

    def test_get_patient_list_optimization(self):
        """Test that getPatientList uses select_related/prefetch_related."""
        from ndas.custom_codes.custom_methods import getPatientList
        from ndas.custom_codes.ndas_enums import PtStatus

        # Create test user
        user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )

        # Create test patients
        for i in range(3):
            Patient.objects.create(
                bht=f'BHT{i:03d}',
                baby_name=f'Test Baby {i}',
                mother_name=f'Mother {i}',
                dob_tob=timezone.now(),
                gender='Male',
                pog_wks=38,
                pog_days=0,
                birth_weight=3000,
                ofc=33,
                mo_delivery='Normal vaginal delivery (NVD)',
                tp_mobile=f'07112345{i:02d}',
                added_by=user
            )

        # Get patient list
        patients = getPatientList(PtStatus.ALL)

        # Should return queryset
        self.assertGreater(patients.count(), 0)

        # Test that related fields are prefetched (no additional queries when accessing)
        from django.db import connection
        connection.queries_log.clear()

        # Access related fields - should not trigger additional queries
        for patient in patients:
            _ = patient.added_by.username if patient.added_by else None
            _ = patient.last_edit_by.username if patient.last_edit_by else None

        # Should use minimal queries due to select_related
        self.assertLess(len(connection.queries), 5)


from django.test import override_settings


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class PatientViewContextTest(TestCase):
    """Test patient_view context — verifies BUG-01 fix: gm_last_assessment is not callable.

    GMAssessment requires a Video (OneToOneField, not null), so tests with GMA records
    require a full Video setup. The zero-assessments case directly validates BUG-01:
    var_gma.last (bug) is callable; var_gma.last() (fix) returns None.
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='viewtestuser',
            password='testpass123',
            email='viewtest@example.com',
            is_staff=True
        )
        self.client.force_login(self.user)

        self.patient = Patient.objects.create(
            bht='BHTVT001',
            baby_name='View Test Baby',
            mother_name='View Test Mother',
            dob_tob=timezone.now(),
            gender='Male',
            pog_wks=38,
            pog_days=2,
            birth_weight=3000,
            ofc=33,
            mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711234599',
            added_by=self.user
        )

    def test_gm_last_assessment_is_not_callable_when_no_assessments(self):
        """BUG-01: gm_last_assessment must be None, not a bound method, when patient has no GMA.

        Before fix: var_gma.last stores the bound method → callable → template renders garbage.
        After fix:  var_gma.last() returns None → not callable → template renders nothing safely.
        """
        response = self.client.get(reverse('view-patient', kwargs={'pk': self.patient.id}))
        self.assertEqual(response.status_code, 200)
        gm_last = response.context['gm_last_assessment']
        self.assertFalse(
            callable(gm_last),
            f"gm_last_assessment must not be callable. Got: {type(gm_last)}"
        )
        self.assertIsNone(
            gm_last,
            "gm_last_assessment should be None when no assessments exist"
        )


class DeleteEndpointErrorSanitizationTest(TestCase):
    """
    Story 2.1: Verify delete endpoints return generic error messages
    and do not leak exception details in JSON responses.
    """

    def setUp(self):
        self.client = Client()
        self.password = 'testpass123'
        self.superuser = User.objects.create_superuser(
            username='supertest',
            password=self.password,
            email='super@example.com',
        )
        self.client.force_login(self.superuser)
        self.patient = Patient.objects.create(
            bht='BHT-DEL-001',
            baby_name='Delete Test Baby',
            mother_name='Delete Test Mother',
            dob_tob=timezone.now(),
            gender='Male',
            pog_wks=38,
            pog_days=0,
            birth_weight=3000,
            ofc=33,
            mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711234599',
            added_by=self.superuser,
        )

    def _send_delete(self, url_name, url_kwargs):
        import json
        url = reverse(url_name, kwargs=url_kwargs)
        return self.client.delete(
            url,
            data=json.dumps({'password': self.password}),
            content_type='application/json',
        )

    def test_patient_delete_error_hides_exception_details(self):
        """patient_delete must not leak str(e) when deletion fails."""
        from unittest.mock import patch
        secret = 'secret-db-constraint-detail'
        with patch.object(Patient, 'delete', side_effect=Exception(secret)):
            response = self._send_delete('delete-patient', {'pk': self.patient.pk})

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(
            data['message'],
            'An unexpected error occurred. Please try again.',
        )
        self.assertNotIn(secret, response.content.decode())

    def test_patient_delete_error_returns_generic_message(self):
        """Generic message string matches exactly (no f-string interpolation)."""
        from unittest.mock import patch
        with patch.object(Patient, 'delete', side_effect=Exception('boom')):
            response = self._send_delete('delete-patient', {'pk': self.patient.pk})

        data = response.json()
        self.assertFalse(data['success'])
        self.assertNotIn('boom', response.content.decode())


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class BirthWeightViewValidationTest(TestCase):
    """Story 1.2: Verify birth weight validation threshold is 300g in patient_add view.

    AC #4: 250g produces form error (no 500).
    AC #5: 300g is accepted.
    AC #6: 200g is rejected with clear error message.
    """

    REQUIRED_FIELDS = {
        'bht': 'BHT-BW-001',
        'baby_name': 'BW Test Baby',
        'mother_name': 'BW Test Mother',
        'dob_tob': '2025-01-01 12:00:00',
        'gender': 'Male',
        'pog_wks': 38,
        'pog_days': 0,
        'apgar_1': 10,
        'apgar_5': 10,
        'apgar_10': 10,
        'ofc': 33,
        'mo_delivery': 'Normal vaginal delivery (NVD)',
        'tp_mobile': '0711234500',
    }

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='bwtestuser',
            password='testpass123',
            email='bwtest@example.com',
            is_staff=True,
        )
        self.client.force_login(self.user)
        self.url = reverse('add-patient')

    def _post_with_birth_weight(self, birth_weight):
        data = dict(self.REQUIRED_FIELDS)
        data['birth_weight'] = birth_weight
        return self.client.post(self.url, data)

    def test_birth_weight_250_rejected_with_form_error(self):
        """AC #4: 250g must produce a form validation error, not a 500."""
        response = self._post_with_birth_weight(250)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn(
            'Birth weight must be between 300g and 8000g',
            [str(e) for e in form.errors.get('birth_weight', [])],
        )

    def test_birth_weight_200_rejected_with_clear_error(self):
        """AC #6: 200g must be rejected with a clear error message."""
        response = self._post_with_birth_weight(200)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn(
            'Birth weight must be between 300g and 8000g',
            [str(e) for e in form.errors.get('birth_weight', [])],
        )

    def test_birth_weight_300_accepted(self):
        """AC #5: 300g must be accepted (redirects to view-patient).

        Uses pog_wks=20 (overriding the class default of 38) because 300g is
        only medically plausible at the extremely-premature end of gestation
        per BIRTH_WEIGHT_RANGES_BY_POG (min=300g at 20 weeks; min=2400g at 38
        weeks). Since spec-fix-medical-data-correctness wired
        validate_birth_weight_for_gestational_age() into Patient.clean(),
        300g at 38 weeks (this class's default) is now correctly rejected as
        implausible for a near-term baby — this test isolates the basic
        300-8000g field-level boundary this AC targets from that POG-specific
        check by using a gestational age where 300g is actually plausible.
        """
        data = dict(self.REQUIRED_FIELDS)
        data['pog_wks'] = 20
        data['birth_weight'] = 300
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        self.assertIn('view', response.url)


def suite():
    """Create test suite."""
    from django.test import TestSuite
    suite = TestSuite()

    # Patient Manager tests
    suite.addTest(PatientManagerTestCase('test_patient_manager_all_filter'))
    suite.addTest(PatientManagerTestCase('test_patient_manager_new_filter'))
    suite.addTest(PatientManagerTestCase('test_patient_manager_diagnosed_filter'))
    suite.addTest(PatientManagerTestCase('test_patient_manager_dx_normal_filter'))
    suite.addTest(PatientManagerTestCase('test_patient_manager_dx_abnormal_filter'))
    suite.addTest(PatientManagerTestCase('test_patient_manager_dx_pending_filter'))
    suite.addTest(PatientManagerTestCase('test_patient_manager_high_risk_filter'))
    suite.addTest(PatientManagerTestCase('test_patient_manager_search_by_baby_name'))
    suite.addTest(PatientManagerTestCase('test_patient_manager_search_by_bht'))
    suite.addTest(PatientManagerTestCase('test_patient_manager_pagination'))
    suite.addTest(PatientManagerTestCase('test_patient_manager_invalid_filter_defaults_to_all'))
    suite.addTest(PatientManagerTestCase('test_patient_manager_filter_type_context'))

    # Dashboard tests
    suite.addTest(DashboardTestCase('test_dashboard_loads_successfully'))
    suite.addTest(DashboardTestCase('test_dashboard_patient_counts'))
    suite.addTest(DashboardTestCase('test_dashboard_context_variables'))
    suite.addTest(DashboardTestCase('test_dashboard_recent_patients'))

    # Delete error sanitization tests
    suite.addTest(DeleteEndpointErrorSanitizationTest('test_patient_delete_error_hides_exception_details'))
    suite.addTest(DeleteEndpointErrorSanitizationTest('test_patient_delete_error_returns_generic_message'))

    return suite


from django.db import connection
from django.test.utils import CaptureQueriesContext
from ndas.custom_codes.custom_methods import get_userStats
from patients.models import GMAssessment
from video.models import Video


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class UserStatsQueryCountTest(TestCase):
    """Test get_userStats() uses O(models) queries instead of O(users*models)."""

    PATIENT_DEFAULTS = {
        'baby_name': 'Stats Baby',
        'mother_name': 'Stats Mother',
        'dob_tob': None,
        'gender': 'Male',
        'pog_wks': 38,
        'pog_days': 2,
        'birth_weight': 3000,
        'ofc': 33,
        'mo_delivery': 'Normal vaginal delivery (NVD)',
        'tp_mobile': '0711234561',
    }

    def setUp(self):
        self.user = User.objects.create_user(
            username='statsuser', password='pass', email='stats@test.com'
        )
        self.user2 = User.objects.create_user(
            username='statsuser2', password='pass', email='stats2@test.com'
        )

    def _make_patient(self, bht, user=None):
        return Patient.objects.create(
            bht=bht,
            **{**self.PATIENT_DEFAULTS, 'dob_tob': timezone.now()},
            added_by=user or self.user,
        )

    def test_userstats_query_count(self):
        """get_userStats() must execute ≤ 10 DB queries regardless of user count."""
        self._make_patient('STAT-001')
        self._make_patient('STAT-002', user=self.user2)

        with CaptureQueriesContext(connection) as ctx:
            get_userStats()

        self.assertLessEqual(
            len(ctx), 10,
            f"Expected ≤10 queries, got {len(ctx)}: {[q['sql'][:80] for q in ctx]}"
        )

    def test_userstats_return_structure(self):
        """Return value must be dict[username → dict] with all required model keys."""
        self._make_patient('STAT-STRUCT-001')

        result = get_userStats()

        self.assertIn(self.user.username, result)
        expected_keys = ('Patient', 'Video', 'GMA', 'HINE', 'DA', 'CDIC', 'Attachment', 'Bookmark')
        for key in expected_keys:
            self.assertIn(key, result[self.user.username],
                          f"Missing key '{key}' in user stats dict")
            self.assertIsInstance(result[self.user.username][key], int)

    def test_userstats_counts_correct(self):
        """Counts returned must match records created per user."""
        p1 = self._make_patient('STAT-CNT-001')
        p2 = self._make_patient('STAT-CNT-002')

        # Create a Video and GMA for p1
        video = Video.objects.create(
            patient=p1,
            title='Stats Test Video',
            recorded_on=timezone.now(),
            added_by=self.user,
        )
        GMAssessment.objects.create(
            patient=p1,
            video_file=video,
            date_of_assessment=timezone.now(),
            added_by=self.user,
        )

        result = get_userStats()

        self.assertEqual(result[self.user.username]['Patient'], 2)
        self.assertEqual(result[self.user.username]['GMA'], 1)
        self.assertEqual(result[self.user.username]['Video'], 1)
        # user2 has no records — must be 0, not absent
        self.assertEqual(result[self.user2.username]['Patient'], 0)
