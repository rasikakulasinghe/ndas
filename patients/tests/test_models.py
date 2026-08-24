"""
patients/tests/test_models.py

Regression tests for Patient.getRC — part of spec-fix-medical-data-correctness.

Patient.getRC previously fetched the "latest" HINE score via
`HINEAssessment.objects.filter(patient=self).last()`. Since
HINEAssessment.Meta.ordering is `["-date_of_assessment"]` (descending),
`.last()` returned the OLDEST record instead of the newest, so the
physiotherapy-referral recommendation was computed from stale data.
The fix reuses `Patient.get_latest_hine_assessment()`, which orders
explicitly and takes `.first()`.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from patients.models import Patient, HINEAssessment, GMAssessment
from video.models import Video

User = get_user_model()


class PatientGetRCTest(TestCase):
    """Regression tests for the getRC stale-HINE-record fix."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='rc_user',
            password='Testpass1!',
            email='rc_user@example.com',
            is_staff=True,
        )
        self.patient = Patient.objects.create(
            bht='BHT-RC-001',
            baby_name='RC Baby',
            mother_name='RC Mother',
            gender='Male',
            dob_tob=timezone.now() - timezone.timedelta(days=365),
            mo_delivery='Normal vaginal delivery (NVD)',
            pog_wks=38,
            pog_days=0,
            birth_weight=3000,
            ofc=34,
            tp_mobile='0771234567',
            added_by=self.user,
        )

    def test_getrc_uses_most_recent_hine_score_not_oldest(self):
        """
        With HINE records on 2026-01-01 (score=50) and 2026-06-01 (score=75),
        getRC's physiotherapy-indication check must use the newest score (75),
        not the oldest (50).
        """
        older = timezone.make_aware(timezone.datetime(2026, 1, 1))
        newer = timezone.make_aware(timezone.datetime(2026, 6, 1))

        # Make isLastGMANormal False so is_pt_indicated's display actually
        # depends on last_hine_score (otherwise the GMA-normal short-circuit
        # would mask the getRC bug this test targets).
        video = Video.objects.create(
            patient=self.patient,
            title='RC Test Video',
            recorded_on=older,
            added_by=self.user,
        )
        GMAssessment.objects.create(
            patient=self.patient,
            video_file=video,
            date_of_assessment=older,
            diagnosis_conclusion='ABNORMAL',
            added_by=self.user,
        )

        HINEAssessment.objects.create(
            patient=self.patient,
            date_of_assessment=older,
            score=50,
            assessment_done_by='Dr. Old',
            added_by=self.user,
        )
        HINEAssessment.objects.create(
            patient=self.patient,
            date_of_assessment=newer,
            score=75,
            assessment_done_by='Dr. New',
            added_by=self.user,
        )

        # Sanity check: .last() on the model's default ordering would
        # return the OLDEST record (the pre-fix bug) since ordering is
        # `["-date_of_assessment"]` (descending).
        self.assertEqual(
            HINEAssessment.objects.filter(patient=self.patient).last().score, 50
        )
        # The correct "latest" lookup used by the fix:
        self.assertEqual(self.patient.get_latest_hine_assessment().score, 75)

        rc = self.patient.getRC
        self.assertIsNot(rc, False, "getRC should return the status list, not False")
        is_pt_indicated = rc[5]
        # score=75 is > 73 (Normal per HINEAssessment.is_normal), so the
        # physiotherapy-referral message must NOT be displayed once the
        # newest score is used (it would be displayed if the stale score
        # of 50 were used instead).
        self.assertFalse(is_pt_indicated['display'])

    def test_getrc_no_hine_records_score_defaults_to_zero(self):
        """
        With no HINEAssessment rows, last_hine_score must default to 0 (a
        comparable int < 73), not None or anything else the `< 73` comparison
        below it would choke on. isLastGMANormal returns True with zero GMA
        records, which would itself block is_pt_indicated regardless of
        last_hine_score — so an abnormal GMA is added here (same pattern as
        the test above) to make is_pt_indicated['display'] actually observe
        last_hine_score's default value, not just short-circuit past it.
        """
        video = Video.objects.create(
            patient=self.patient,
            title='RC No-HINE Test Video',
            recorded_on=timezone.now(),
            added_by=self.user,
        )
        GMAssessment.objects.create(
            patient=self.patient,
            video_file=video,
            date_of_assessment=timezone.now(),
            diagnosis_conclusion='ABNORMAL',
            added_by=self.user,
        )
        self.assertIsNone(self.patient.get_latest_hine_assessment())

        rc = self.patient.getRC
        self.assertIsNot(rc, False, "getRC should not raise/return False with no HINE records")
        is_pt_indicated = rc[5]
        self.assertTrue(
            is_pt_indicated['display'],
            "last_hine_score must default to 0 (< 73) so an abnormal-GMA, "
            "no-HINE patient is still flagged for physiotherapy referral",
        )
