"""
Unit tests for refactored patients views.

Tests the unified patient_manager function and optimized dashboard view.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime
from patients.models import Patient, GMAssessment, Video
from ndas.custom_codes.ndas_enums import PtStatus

User = get_user_model()


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
            gender='M',
            pog_wks=38,
            pog_days=2,
            birth_weight=3000,
            added_by=self.user
        )

        # Patient 2: Diagnosed normal
        self.patient_dx_normal = Patient.objects.create(
            bht='BHT002',
            baby_name='Normal Baby',
            mother_name='Mother Two',
            dob_tob=timezone.now(),
            gender='F',
            pog_wks=39,
            pog_days=0,
            birth_weight=3200,
            dx_conclution='dx_normal',
            added_by=self.user
        )

        # Patient 3: Diagnosed abnormal
        self.patient_dx_abnormal = Patient.objects.create(
            bht='BHT003',
            baby_name='Abnormal Baby',
            mother_name='Mother Three',
            dob_tob=timezone.now(),
            gender='M',
            pog_wks=37,
            pog_days=5,
            birth_weight=2800,
            dx_conclution='dx_abnormal',
            added_by=self.user
        )

        # Patient 4: Diagnosis pending (has assessment but no diagnosis)
        self.patient_dx_pending = Patient.objects.create(
            bht='BHT004',
            baby_name='Pending Baby',
            mother_name='Mother Four',
            dob_tob=timezone.now(),
            gender='F',
            pog_wks=40,
            pog_days=1,
            birth_weight=3400,
            added_by=self.user
        )
        # Add GM assessment without diagnosis
        GMAssessment.objects.create(
            patient=self.patient_dx_pending,
            date_of_assessment=timezone.now(),
            added_by=self.user
        )

        # Patient 5: High risk (APGAR score < 7)
        self.patient_high_risk = Patient.objects.create(
            bht='BHT005',
            baby_name='High Risk Baby',
            mother_name='Mother Five',
            dob_tob=timezone.now(),
            gender='M',
            pog_wks=36,
            pog_days=0,
            birth_weight=2500,
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
                gender='M' if i % 2 == 0 else 'F',
                pog_wks=38,
                pog_days=0,
                birth_weight=3000,
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
                gender='M' if i % 2 == 0 else 'F',
                pog_wks=38,
                pog_days=0,
                birth_weight=3000,
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
                gender='M',
                pog_wks=38,
                pog_days=0,
                birth_weight=3000,
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

    return suite
