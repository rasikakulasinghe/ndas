"""
patients/tests/test_timeline_utils.py

Regression test for get_patient_timeline_events' GM Assessment event block —
part of spec-fix-gma-timeline-and-video-bookmark-mapping.

The GMA event block referenced `gma.observation`, a field that does not
exist on GMAssessment (patient.models.py has no `observation` field). The
resulting AttributeError was caught by the block's own broad
`except Exception`, so it didn't crash the whole timeline — but it silently
dropped every GM Assessment event from every patient's timeline, since the
exception fired before `events.append(...)` for the 'gma' event. The fix
uses `gma.diagnosis_other` (an existing free-text field) instead.
"""
import json

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from patients.models import Patient, GMAssessment
from patients.timeline_utils import get_patient_timeline_events
from video.models import Video

User = get_user_model()


class GmaTimelineEventTest(TestCase):
    """Regression test: GM Assessment events must appear in the patient timeline."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='timeline_user',
            password='Testpass1!',
            email='timeline_user@example.com',
            is_staff=True,
        )
        self.patient = Patient.objects.create(
            bht='BHT-TL-001',
            baby_name='Timeline Baby',
            mother_name='Timeline Mother',
            gender='Male',
            dob_tob=timezone.now() - timezone.timedelta(days=60),
            mo_delivery='Normal vaginal delivery (NVD)',
            pog_wks=38,
            pog_days=0,
            birth_weight=3000,
            ofc=34,
            tp_mobile='0771234567',
            added_by=self.user,
        )

    def test_gma_event_appears_in_timeline(self):
        video = Video.objects.create(
            patient=self.patient,
            title='Timeline Test Video',
            recorded_on=timezone.now() - timezone.timedelta(days=10),
            added_by=self.user,
        )
        GMAssessment.objects.create(
            patient=self.patient,
            video_file=video,
            date_of_assessment=timezone.now() - timezone.timedelta(days=10),
            diagnosis_conclusion='ABNORMAL',
            diagnosis_other='Asymmetric movements noted',
            added_by=self.user,
        )

        events = get_patient_timeline_events(self.patient)
        gma_events = [e for e in events if e['type'] == 'gma']

        self.assertEqual(
            len(gma_events), 1,
            "GM Assessment event must be present in the timeline, not silently dropped",
        )
        preview = json.loads(gma_events[0]['preview_data'])
        self.assertEqual(preview['notes'], 'Asymmetric movements noted')
        self.assertEqual(preview['diagnosis'], 'ABNORMAL')
        self.assertEqual(preview['video'], 'Timeline Test Video')

    def test_gma_event_handles_missing_diagnosis_other(self):
        """
        diagnosis_other is nullable — the event must still appear, with an
        empty (not a fallback sentence) 'notes' value, so the timeline
        preview's JS can correctly omit the row rather than displaying
        placeholder text like "No notes recorded".
        """
        video = Video.objects.create(
            patient=self.patient,
            title='Timeline Test Video 2',
            recorded_on=timezone.now() - timezone.timedelta(days=5),
            added_by=self.user,
        )
        GMAssessment.objects.create(
            patient=self.patient,
            video_file=video,
            date_of_assessment=timezone.now() - timezone.timedelta(days=5),
            diagnosis_conclusion='NORMAL',
            added_by=self.user,
        )

        events = get_patient_timeline_events(self.patient)
        gma_events = [e for e in events if e['type'] == 'gma']

        self.assertEqual(len(gma_events), 1)
        preview = json.loads(gma_events[0]['preview_data'])
        self.assertEqual(preview['notes'], '')
