"""
Tests for Story 2.6 — Patient Move Between Institutions.

Covers:
- Only SUPERADMIN can access
- GET shows preview with impact summary
- POST confirm shows confirmation step
- POST execute: name mismatch rejected
- POST execute: valid name commits atomic move
- PatientMoveLog records created on move
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from institution.models import Institution, PatientMoveLog
from ndas.custom_codes.choice import UserType
from patients.models import Patient

User = get_user_model()


def make_superadmin(username='superadmin'):
    return User.objects.create_user(
        username=username, password='testpass123',
        email=f'{username}@test.com', first_name='Super',
        position='Medical Officer', mobile_primary='0771234567',
        user_type=UserType.SUPERADMIN, is_superuser=True, is_staff=True,
    )


def make_patient(institution, baby_name='Test Baby', bht='BHT001'):
    return Patient.objects.create(
        baby_name=baby_name,
        mother_name='Test Mother',
        bht=bht,
        institution=institution,
        gender='Male',
        dob_tob=timezone.now(),
        birth_weight=3000,
        ofc=33,
        mo_delivery='Normal vaginal delivery (NVD)',
        tp_mobile='0771234570',
    )


STATIC_OVERRIDE = override_settings(
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
)


@STATIC_OVERRIDE
class PatientMoveAccessTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.superadmin = make_superadmin()
        self.source = Institution.objects.create(name='Source Hospital', slug='source-hosp')
        self.patient = make_patient(self.source)
        self.url = reverse('institution:superadmin-patient-move', args=[self.patient.pk])

    def test_unauthenticated_redirects(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_superadmin_gets_preview(self):
        self.client.login(username='superadmin', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'institution/superadmin_patient_move.html')
        self.assertEqual(response.context['step'], 'preview')

    def test_nonexistent_patient_is_denied(self):
        """Non-existent patient ID — handle_view_errors converts Http404 to a redirect."""
        self.client.login(username='superadmin', password='testpass123')
        url = reverse('institution:superadmin-patient-move', args=[99999])
        response = self.client.get(url)
        # handle_view_errors catches Http404 and redirects
        self.assertIn(response.status_code, [302, 404])


@STATIC_OVERRIDE
class PatientMoveFlowTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.superadmin = make_superadmin()
        self.source = Institution.objects.create(name='Source Hospital', slug='source-hosp')
        self.dest = Institution.objects.create(name='Destination Clinic', slug='dest-clinic')
        self.patient = make_patient(self.source, baby_name='Baby A', bht='BHT-001')
        self.url = reverse('institution:superadmin-patient-move', args=[self.patient.pk])
        self.client.login(username='superadmin', password='testpass123')

    def test_confirm_step_renders(self):
        response = self.client.post(self.url, {
            'step': 'confirm',
            'destination_institution_id': self.dest.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'confirm')
        self.assertEqual(response.context['destination_institution'], self.dest)

    def test_execute_name_mismatch_rejected(self):
        """Wrong institution name in confirmation field blocks the move."""
        response = self.client.post(self.url, {
            'step': 'execute',
            'destination_institution_id': self.dest.pk,
            'institution_name_confirm': 'Wrong Name',
        })
        self.assertEqual(response.status_code, 200)
        # Patient should NOT have moved
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.institution, self.source)

    def test_execute_correct_name_moves_patient(self):
        """Correct institution name commits the atomic move."""
        response = self.client.post(self.url, {
            'step': 'execute',
            'destination_institution_id': self.dest.pk,
            'institution_name_confirm': self.dest.name,
        })
        self.assertIn(response.status_code, [302, 200])

        self.patient.refresh_from_db()
        self.assertEqual(self.patient.institution, self.dest)

    def test_execute_creates_move_log_records(self):
        """Two PatientMoveLog records are created: one for each institution."""
        log_count_before = PatientMoveLog.objects.count()

        self.client.post(self.url, {
            'step': 'execute',
            'destination_institution_id': self.dest.pk,
            'institution_name_confirm': self.dest.name,
        })

        new_logs = PatientMoveLog.objects.count() - log_count_before
        self.assertEqual(new_logs, 2)

        logs = PatientMoveLog.objects.filter(patient=self.patient)
        self.assertTrue(all(log.from_institution == self.source for log in logs))
        self.assertTrue(all(log.to_institution == self.dest for log in logs))

    def test_move_redirects_to_patient_view(self):
        """After move, user is redirected to the patient view."""
        response = self.client.post(self.url, {
            'step': 'execute',
            'destination_institution_id': self.dest.pk,
            'institution_name_confirm': self.dest.name,
        })
        self.assertRedirects(
            response,
            reverse('view-patient', args=[self.patient.pk]),
            fetch_redirect_response=False,
        )
