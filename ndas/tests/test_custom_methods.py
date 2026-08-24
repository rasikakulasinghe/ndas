"""
ndas/tests/test_custom_methods.py

Regression tests for getPatientList(PtStatus.DX_NORMAL) — part of
spec-fix-medical-data-correctness.

The DX_NORMAL branch previously combined three Q objects with Python's
`and` operator instead of the ORM's `|`. Since `and` short-circuits on
truthy Q objects, only the last Q object (developmental_assessments)
survived, so patients with an abnormal GMA or HINE result but a normal
(or absent) developmental assessment were wrongly classified as
DX_NORMAL. The fix combines the Q objects with `|` (excluding anyone
abnormal in *any* of GMA/HINE/DA, per De Morgan's law) — `&` would only
exclude patients abnormal in all three simultaneously.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from ndas.custom_codes.custom_methods import getPatientList
from ndas.custom_codes.ndas_enums import PtStatus
from patients.models import Patient, GMAssessment
from video.models import Video

User = get_user_model()


class GetPatientListDxNormalTest(TestCase):
    """Regression tests for the DX_NORMAL branch's Q-object short-circuit fix."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='cm_user',
            password='Testpass1!',
            email='cm_user@example.com',
            is_staff=True,
        )

    def _make_patient(self, bht):
        return Patient.objects.create(
            bht=bht,
            baby_name=f'Baby {bht}',
            mother_name='Test Mother',
            gender='Male',
            dob_tob=timezone.now() - timezone.timedelta(days=200),
            mo_delivery='Normal vaginal delivery (NVD)',
            pog_wks=38,
            pog_days=0,
            birth_weight=3000,
            ofc=34,
            tp_mobile='0771234567',
            added_by=self.user,
        )

    def test_abnormal_gma_with_normal_da_excluded_from_dx_normal(self):
        """
        A patient with an abnormal GMA diagnosis and an otherwise-normal
        developmental assessment must NOT appear in DX_NORMAL — the
        pre-fix short-circuit bug wrongly included such patients because
        only the (normal) DA condition was actually evaluated.
        """
        patient = self._make_patient('BHT-CM-001')
        video = Video.objects.create(
            patient=patient,
            title='CM Test Video',
            recorded_on=timezone.now(),
            added_by=self.user,
        )
        GMAssessment.objects.create(
            patient=patient,
            video_file=video,
            date_of_assessment=timezone.now(),
            diagnosis_conclusion='ABNORMAL',
            added_by=self.user,
        )
        # Otherwise-normal developmental assessment: no domain age ranges
        # set, so DevelopmentalAssessment.is_normal (and thus is_dx_normal,
        # auto-computed on save()) evaluates to True.
        patient.developmental_assessments.create(
            date_of_assessment=timezone.now(),
            assessment_done_by='Dr. Test',
            added_by=self.user,
        )

        result_ids = list(
            getPatientList(PtStatus.DX_NORMAL).values_list('id', flat=True)
        )

        self.assertNotIn(patient.id, result_ids)

    def test_abnormal_hine_with_normal_da_excluded_from_dx_normal(self):
        """
        A patient with an abnormal HINE score (and an otherwise-normal GMA/DA)
        must NOT appear in DX_NORMAL — covers the HINE-abnormal leg of the
        original `and`-short-circuit bug independently of the GMA-abnormal
        leg (the pre-fix bug only ever evaluated the DA condition, so either
        abnormal leg alone would have been wrongly included).
        """
        patient = self._make_patient('BHT-CM-003')
        Video.objects.create(
            patient=patient,
            title='CM HINE Test Video',
            recorded_on=timezone.now(),
            added_by=self.user,
        )
        patient.hine_assessments.create(
            date_of_assessment=timezone.now(),
            score=50,  # < 73: abnormal per HINEAssessment.is_normal
            assessment_done_by='Dr. Test',
            added_by=self.user,
        )
        patient.developmental_assessments.create(
            date_of_assessment=timezone.now(),
            assessment_done_by='Dr. Test',
            added_by=self.user,
        )

        result_ids = list(
            getPatientList(PtStatus.DX_NORMAL).values_list('id', flat=True)
        )

        self.assertNotIn(patient.id, result_ids)

    def test_fully_normal_patient_with_videos_included_in_dx_normal(self):
        """A patient with no abnormal GMA/HINE/DA records and videos is included."""
        patient = self._make_patient('BHT-CM-002')
        Video.objects.create(
            patient=patient,
            title='CM Normal Video',
            recorded_on=timezone.now(),
            added_by=self.user,
        )

        result_ids = list(
            getPatientList(PtStatus.DX_NORMAL).values_list('id', flat=True)
        )

        self.assertIn(patient.id, result_ids)
