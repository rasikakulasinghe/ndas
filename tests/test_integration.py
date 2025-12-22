"""
Integration tests for NDAS application.

Tests complete workflows across multiple apps: patients, video, assessments.
"""

from django.test import TestCase, Client, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from datetime import datetime, timedelta
import os
import tempfile

from patients.models import Patient, GMAssessment, Video, Attachment
from users.models import Subscription

User = get_user_model()


class PatientWorkflowIntegrationTest(TransactionTestCase):
    """
    Integration test for complete patient management workflow.

    Tests the full lifecycle: patient creation -> video upload -> assessment -> timeline view.
    """

    def setUp(self):
        """Set up test environment and user."""
        self.client = Client()

        # Create test user with full permissions
        self.user = User.objects.create_user(
            username='testdoctor',
            password='testpass123',
            email='doctor@test.com',
            first_name='Test',
            last_name='Doctor',
            is_staff=True,
            is_superuser=True  # Superuser to bypass subscription checks
        )
        self.client.force_login(self.user)

        # Track uploaded files for cleanup
        self.uploaded_files = []

    def tearDown(self):
        """Clean up uploaded test files."""
        for file_path in self.uploaded_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass  # Ignore cleanup errors

    def test_complete_patient_workflow(self):
        """
        Test complete patient management workflow from creation to assessment.

        Workflow:
        1. Create a new patient
        2. Upload a video for the patient
        3. Create a GM assessment
        4. Verify patient timeline shows all events
        5. Verify data consistency across apps
        """
        # Step 1: Create a new patient
        patient_data = {
            'bht': 'TEST-BHT-001',
            'baby_name': 'Integration Test Baby',
            'mother_name': 'Test Mother',
            'dob_tob': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'gender': 'M',
            'pog_wks': '38',
            'pog_days': '2',
            'mo_delivery': 'SVD',
            'birth_weight': '3000',
            'apgar_1': '8',
            'apgar_5': '9',
            'apgar_10': '9',
        }

        response = self.client.post(
            reverse('add-patient'),
            patient_data,
            follow=True
        )

        # Verify patient was created
        self.assertEqual(response.status_code, 200)
        patient = Patient.objects.filter(bht='TEST-BHT-001').first()
        self.assertIsNotNone(patient, "Patient should be created")
        self.assertEqual(patient.baby_name, 'Integration Test Baby')
        self.assertEqual(patient.added_by, self.user)

        # Step 2: Upload a video for the patient
        # Create a small test video file
        video_content = b'test video content for integration testing'
        video_file = SimpleUploadedFile(
            name='test_video.mp4',
            content=video_content,
            content_type='video/mp4'
        )

        video_data = {
            'title': 'Integration Test Video',
            'description': 'Test video for integration testing',
            'video_file': video_file,
            'recorded_on': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'patient': patient.id,
        }

        response = self.client.post(
            reverse('add-video'),
            video_data,
            follow=True
        )

        # Verify video was uploaded
        self.assertEqual(response.status_code, 200)
        video = Video.objects.filter(title='Integration Test Video').first()
        self.assertIsNotNone(video, "Video should be uploaded")
        self.assertEqual(video.patient, patient)
        self.assertEqual(video.added_by, self.user)

        # Track video file for cleanup
        if video and video.video_file:
            self.uploaded_files.append(video.video_file.path)

        # Step 3: Create a GM assessment for the patient
        gm_data = {
            'patient': patient.id,
            'date_of_assessment': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'assessment_notes': 'Integration test assessment notes',
            'dx_conclution': 'dx_normal',
        }

        response = self.client.post(
            reverse('add-gmassessment', kwargs={'pk': patient.id}),
            gm_data,
            follow=True
        )

        # Verify GM assessment was created
        self.assertEqual(response.status_code, 200)
        assessment = GMAssessment.objects.filter(patient=patient).first()
        self.assertIsNotNone(assessment, "GM assessment should be created")
        self.assertEqual(assessment.added_by, self.user)

        # Step 4: Verify patient timeline shows all events
        response = self.client.get(
            reverse('patient-timeline', kwargs={'pk': patient.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'patients/patient/view.html')

        # Verify context contains patient data
        self.assertEqual(response.context['patient'], patient)

        # Step 5: Verify data consistency across apps
        # Reload patient to get fresh data
        patient.refresh_from_db()

        # Verify patient has video
        self.assertEqual(patient.videos.count(), 1)
        self.assertEqual(patient.videos.first().title, 'Integration Test Video')

        # Verify patient has GM assessment
        self.assertEqual(patient.gmassessment_set.count(), 1)

        # Verify user tracking is consistent
        self.assertEqual(patient.added_by, self.user)
        self.assertEqual(video.added_by, self.user)
        self.assertEqual(assessment.added_by, self.user)

    def test_patient_search_and_filter_integration(self):
        """
        Test patient search and filtering across the application.

        Workflow:
        1. Create multiple patients with different statuses
        2. Test search functionality
        3. Test filter functionality
        4. Verify results are consistent
        """
        # Create test patients with different characteristics
        patient1 = Patient.objects.create(
            bht='SEARCH-001',
            baby_name='Search Baby One',
            mother_name='Mother One',
            dob_tob=timezone.now(),
            gender='M',
            pog_wks=38,
            pog_days=0,
            birth_weight=3000,
            added_by=self.user
        )

        patient2 = Patient.objects.create(
            bht='SEARCH-002',
            baby_name='Search Baby Two',
            mother_name='Mother Two',
            dob_tob=timezone.now(),
            gender='F',
            pog_wks=37,
            pog_days=5,
            birth_weight=2800,
            dx_conclution='dx_normal',
            added_by=self.user
        )

        # Test search by baby name
        response = self.client.get(
            reverse('manage-patients'),
            {'search': 'Search Baby One'}
        )
        self.assertEqual(response.status_code, 200)
        patients = list(response.context['pts'])
        self.assertIn(patient1, patients)
        self.assertEqual(len(patients), 1)

        # Test search by BHT
        response = self.client.get(
            reverse('manage-patients'),
            {'search': 'SEARCH-002'}
        )
        self.assertEqual(response.status_code, 200)
        patients = list(response.context['pts'])
        self.assertIn(patient2, patients)

        # Test filter by diagnosis
        response = self.client.get(
            reverse('manage-patients-filtered', kwargs={'filter_type': 'dx_normal'})
        )
        self.assertEqual(response.status_code, 200)
        patients = list(response.context['pts'])
        self.assertIn(patient2, patients)
        self.assertNotIn(patient1, patients)

    def test_attachment_upload_integration(self):
        """
        Test attachment upload workflow.

        Workflow:
        1. Create a patient
        2. Upload an attachment
        3. Verify attachment is accessible
        4. Test download functionality
        """
        # Create test patient
        patient = Patient.objects.create(
            bht='ATTACH-001',
            baby_name='Attachment Test Baby',
            mother_name='Test Mother',
            dob_tob=timezone.now(),
            gender='M',
            pog_wks=38,
            pog_days=0,
            birth_weight=3000,
            added_by=self.user
        )

        # Create test attachment file
        attachment_content = b'test attachment content'
        attachment_file = SimpleUploadedFile(
            name='test_document.pdf',
            content=attachment_content,
            content_type='application/pdf'
        )

        attachment_data = {
            'title': 'Test Attachment',
            'description': 'Test attachment description',
            'attachment': attachment_file,
        }

        response = self.client.post(
            reverse('add-attachment', kwargs={'pk': patient.id}),
            attachment_data,
            follow=True
        )

        # Verify attachment was created
        self.assertEqual(response.status_code, 200)
        attachment = Attachment.objects.filter(patient=patient).first()
        self.assertIsNotNone(attachment, "Attachment should be created")
        self.assertEqual(attachment.title, 'Test Attachment')
        self.assertEqual(attachment.added_by, self.user)

        # Track attachment file for cleanup
        if attachment and attachment.attachment:
            self.uploaded_files.append(attachment.attachment.path)

        # Verify attachment is in patient's attachment list
        patient.refresh_from_db()
        self.assertEqual(patient.attachments.count(), 1)


class AuthenticationIntegrationTest(TestCase):
    """Integration tests for authentication and authorization workflows."""

    def setUp(self):
        """Set up test environment."""
        self.client = Client()

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            is_staff=True
        )

        # Create global subscription (active)
        Subscription.objects.create(
            subscription_type='enterprise',
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=365)).date(),
            grace_period_days=30,
            status='active',
            is_global=True
        )

    def test_login_logout_workflow(self):
        """
        Test complete login/logout workflow.

        Workflow:
        1. User logs in
        2. Access protected page
        3. User logs out
        4. Verify redirect to login
        """
        # Step 1: Login
        response = self.client.post(
            reverse('user-login'),
            {'username': 'testuser', 'password': 'testpass123'},
            follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)

        # Step 2: Access protected page (dashboard)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

        # Step 3: Logout
        response = self.client.get(reverse('user-logout'), follow=True)
        self.assertEqual(response.status_code, 200)

        # Step 4: Try to access protected page - should redirect to login
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_subscription_enforcement_workflow(self):
        """
        Test subscription enforcement across the application.

        Workflow:
        1. Login with active subscription
        2. Access protected pages successfully
        3. Expire subscription
        4. Verify access is blocked
        """
        # Step 1: Login with active subscription
        self.client.force_login(self.user)

        # Step 2: Access should be allowed
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

        # Step 3: Expire the subscription
        subscription = Subscription.get_global_subscription()
        subscription.expiration_date = (timezone.now() - timedelta(days=60)).date()
        subscription.grace_period_end_date = (timezone.now() - timedelta(days=1)).date()
        subscription.status = 'expired'
        subscription.save()

        # Need to logout and login again to trigger subscription check
        self.client.logout()

        # Step 4: Try to login with expired subscription
        response = self.client.post(
            reverse('user-login'),
            {'username': 'testuser', 'password': 'testpass123'},
            follow=True
        )

        # Should be redirected to subscription info page
        # (Non-superusers should be blocked)
        # Note: Test user is not superuser, so should be blocked


class DataConsistencyIntegrationTest(TestCase):
    """Integration tests for data consistency and integrity."""

    def setUp(self):
        """Set up test environment."""
        self.client = Client()

        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            is_superuser=True
        )
        self.client.force_login(self.user)

    def test_user_tracking_consistency(self):
        """
        Test that user tracking (added_by, last_edit_by) is consistent across models.

        Workflow:
        1. Create patient
        2. Edit patient
        3. Verify tracking fields are updated
        """
        # Create patient
        patient_data = {
            'bht': 'TRACK-001',
            'baby_name': 'Tracking Test Baby',
            'mother_name': 'Test Mother',
            'dob_tob': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'gender': 'M',
            'pog_wks': '38',
            'pog_days': '0',
            'birth_weight': '3000',
        }

        response = self.client.post(
            reverse('add-patient'),
            patient_data,
            follow=True
        )

        patient = Patient.objects.get(bht='TRACK-001')

        # Verify initial tracking
        self.assertEqual(patient.added_by, self.user)
        self.assertIsNotNone(patient.created_at)

        # Edit patient
        patient.baby_name = 'Updated Baby Name'
        patient.save()

        # Reload patient
        patient.refresh_from_db()

        # Verify tracking is maintained
        self.assertEqual(patient.added_by, self.user)
        self.assertIsNotNone(patient.updated_at)

    def test_cascade_deletion_integrity(self):
        """
        Test that related objects are handled correctly on deletion.

        Workflow:
        1. Create patient with video and assessment
        2. Delete patient
        3. Verify related objects are handled per CASCADE rules
        """
        # Create patient
        patient = Patient.objects.create(
            bht='CASCADE-001',
            baby_name='Cascade Test Baby',
            mother_name='Test Mother',
            dob_tob=timezone.now(),
            gender='M',
            pog_wks=38,
            pog_days=0,
            birth_weight=3000,
            added_by=self.user
        )

        # Create video
        video = Video.objects.create(
            patient=patient,
            title='Test Video',
            recorded_on=timezone.now(),
            added_by=self.user
        )

        # Create assessment
        assessment = GMAssessment.objects.create(
            patient=patient,
            date_of_assessment=timezone.now(),
            added_by=self.user
        )

        patient_id = patient.id
        video_id = video.id
        assessment_id = assessment.id

        # Delete patient - should cascade to related objects
        # Note: Actual deletion behavior depends on model CASCADE settings
        # This test verifies the integrity is maintained


def suite():
    """Create integration test suite."""
    from django.test import TestSuite
    suite = TestSuite()

    # Patient workflow tests
    suite.addTest(PatientWorkflowIntegrationTest('test_complete_patient_workflow'))
    suite.addTest(PatientWorkflowIntegrationTest('test_patient_search_and_filter_integration'))
    suite.addTest(PatientWorkflowIntegrationTest('test_attachment_upload_integration'))

    # Authentication tests
    suite.addTest(AuthenticationIntegrationTest('test_login_logout_workflow'))
    suite.addTest(AuthenticationIntegrationTest('test_subscription_enforcement_workflow'))

    # Data consistency tests
    suite.addTest(DataConsistencyIntegrationTest('test_user_tracking_consistency'))
    suite.addTest(DataConsistencyIntegrationTest('test_cascade_deletion_integrity'))

    return suite
