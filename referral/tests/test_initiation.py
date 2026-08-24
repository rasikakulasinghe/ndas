"""
referral/tests/test_initiation.py
Tests for Referral Initiation (Story 4.2 — FR60, FR61, NFR22).
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
import datetime

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, ReferralStatus
from referral.models import ReferralSent, ReferralReceived

User = get_user_model()

STATIC_OVERRIDE = override_settings(
    MULTI_INSTITUTION_ENABLED=True,
    RATELIMIT_ENABLE=False,
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)

# Valid patient fields — Patient.save() calls full_clean() which validates all required fields
VALID_PATIENT_FIELDS = {
    'baby_name': 'Initiation Patient',
    'mother_name': 'Test Mother',
    'gender': 'Male',
    'dob_tob': datetime.datetime(2023, 1, 15, 8, 30, tzinfo=datetime.timezone.utc),
    'mo_delivery': 'Normal vaginal delivery (NVD)',
    'birth_weight': 3000,
    'ofc': 33,
    'tp_mobile': '0771000001',
}


class ReferralInitiateTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_init', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771331001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='Sending Hospital', slug='sending-hosp',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Receiving Clinic', slug='receiving-clinic',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.clinician_a = User.objects.create_user(
            username='clin_a_init', password='Testpass1!',
            first_name='Sender', last_name='Clinician',
            position='Medical Officer', mobile_primary='0771331002',
            user_type=UserType.USER, institution=self.inst_a,
        )
        self.clinician_b = User.objects.create_user(
            username='clin_b_init', password='Testpass1!',
            first_name='Receiver', last_name='Specialist',
            position='Consultant', mobile_primary='0771331003',
            user_type=UserType.USER, institution=self.inst_b,
        )
        from patients.models import Patient
        self.patient = Patient.objects.create(
            institution=self.inst_a,
            added_by=self.clinician_a, last_edit_by=self.clinician_a,
            **VALID_PATIENT_FIELDS,
        )
        self.initiate_url = reverse('referral:referral-initiate', args=[self.patient.id])


@STATIC_OVERRIDE
class ReferralAtomicCreationTest(ReferralInitiateTestBase):
    def test_creates_both_records_atomically(self):
        """AC #1, NFR22: Both ReferralSent and ReferralReceived are created atomically."""
        client = Client()
        client.force_login(self.clinician_a)
        response = client.post(self.initiate_url, {
            'to_institution': self.inst_b.pk,
            'to_clinician': self.clinician_b.pk,
            'initial_message': 'Please assess this patient.',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ReferralSent.objects.count(), 1, "AC #1: ReferralSent must be created")
        self.assertEqual(ReferralReceived.objects.count(), 1, "AC #1: ReferralReceived must be created")

    def test_shared_uuid(self):
        """AC #1: Both records share the same referral_uuid."""
        client = Client()
        client.force_login(self.clinician_a)
        client.post(self.initiate_url, {
            'to_institution': self.inst_b.pk,
            'to_clinician': self.clinician_b.pk,
            'initial_message': 'Test referral.',
        })
        sent = ReferralSent.objects.first()
        received = ReferralReceived.objects.first()
        self.assertEqual(sent.referral_uuid, received.referral_uuid,
            "AC #1: Both records must share the same referral_uuid")

    def test_snapshot_included(self):
        """AC #2: snapshot_data must be non-empty and include schema_version."""
        client = Client()
        client.force_login(self.clinician_a)
        client.post(self.initiate_url, {
            'to_institution': self.inst_b.pk,
            'to_clinician': self.clinician_b.pk,
            'initial_message': 'Snapshot test.',
        })
        sent = ReferralSent.objects.first()
        self.assertIn('schema_version', sent.snapshot_data,
            "AC #2: snapshot_data must include schema_version")
        self.assertIn('captured_at', sent.snapshot_data,
            "AC #2: snapshot_data must include captured_at")
        self.assertIn('demographics', sent.snapshot_data,
            "AC #2: snapshot_data must include demographics")

    def test_self_institution_referral_rejected(self):
        """AC #5: Referral to own institution must be rejected."""
        client = Client()
        client.force_login(self.clinician_a)
        response = client.post(self.initiate_url, {
            'to_institution': self.inst_a.pk,
            'to_clinician': self.clinician_a.pk,
            'initial_message': 'Self-referral attempt.',
        })
        # Form re-renders (200) with validation error — no redirect
        self.assertEqual(response.status_code, 200,
            "AC #5: Self-institution referral must re-render form, not redirect")
        self.assertEqual(ReferralSent.objects.count(), 0,
            "AC #5: No ReferralSent must be created for self-institution referral")

    def test_no_institution_context_gets_no_patient_data(self):
        """
        Security regression: a user with no resolvable institution context
        (e.g. a broken/unset institution FK — the transitional Phase-1 state
        InstitutionContextMiddleware._resolve_user_context permits through with
        request.institution=None) must NOT receive an unfiltered Patient
        queryset from for_institution(None) — they must get a 404/redirect
        instead of any other institution's patient data.

        Note: SUPERADMIN is not used here — InstitutionContextMiddleware
        intercepts SUPERADMIN requests with no active_institution_id in
        session and redirects to the institution selector before the view is
        ever reached, so it cannot exercise this view-level guard.
        """
        no_institution_user = User.objects.create_user(
            username='no_inst_init', password='Testpass1!',
            first_name='No', last_name='Institution',
            position='Medical Officer', mobile_primary='0771331004',
            user_type=UserType.USER, institution=None,
        )
        client = Client()
        client.force_login(no_institution_user)
        response = client.get(self.initiate_url)
        # Http404 raised by get_object_or_404 is caught by @handle_view_errors
        # and redirected to 'manage-patients' — never a 200 with patient data.
        self.assertEqual(response.status_code, 302,
            "User with no institution context must be redirected, not shown the patient")
        self.assertEqual(response.url, reverse('manage-patients'))
