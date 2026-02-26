"""
referral/tests/test_patient_tab.py
Tests for Patient Referrals Tab (Story 4.6 — FR65, FR66).
"""
import uuid
import datetime
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus
from referral.models import ReferralSent, ReferralReceived

User = get_user_model()

# Required fields for Patient.save() (calls full_clean())
VALID_PATIENT_FIELDS = {
    'gender': 'Male',
    'dob_tob': datetime.datetime(2023, 6, 1, 8, 0, tzinfo=datetime.timezone.utc),
    'mo_delivery': 'Normal vaginal delivery (NVD)',
    'birth_weight': 3200,
    'ofc': 34,
    'tp_mobile': '0770991004',
}

STATIC_OVERRIDE = override_settings(
    MULTI_INSTITUTION_ENABLED=True,
    RATELIMIT_ENABLE=False,
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)


class PatientTabTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_pt_tab', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0770991001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='Tab Alpha', slug='tab-alpha',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Tab Beta', slug='tab-beta',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.clin_a = User.objects.create_user(
            username='clin_a_tab', password='Testpass1!',
            first_name='Tab', last_name='Alpha',
            position='Medical Officer', mobile_primary='0770991002',
            user_type=UserType.USER, institution=self.inst_a,
        )
        self.clin_b = User.objects.create_user(
            username='clin_b_tab', password='Testpass1!',
            first_name='Tab', last_name='Beta',
            position='Consultant', mobile_primary='0770991003',
            user_type=UserType.USER, institution=self.inst_b,
        )
        from patients.models import Patient
        self.patient = Patient.objects.create(
            institution=self.inst_a,
            baby_name='Tab Patient',
            mother_name='Test Mother',
            added_by=self.clin_a,
            last_edit_by=self.clin_a,
            **VALID_PATIENT_FIELDS,
        )
        self.tab_url = reverse('referral:patient-referrals-tab', args=[self.patient.id])


@STATIC_OVERRIDE
class PatientReferralsTabAccessTest(PatientTabTestBase):
    def test_tab_loads_without_error(self):
        """AC #1: Patient referrals tab loads without errors (200 OK)."""
        client = Client()
        client.force_login(self.clin_a)
        response = client.get(self.tab_url)
        self.assertEqual(response.status_code, 200)

    def test_empty_state_no_exception(self):
        """AC #4: Empty referral timeline loads without errors."""
        client = Client()
        client.force_login(self.clin_a)
        response = client.get(self.tab_url)
        self.assertEqual(response.context['referral_count'], 0)


@STATIC_OVERRIDE
class PatientReferralsTimelineTest(PatientTabTestBase):
    def test_sent_referral_appears_in_timeline(self):
        """AC #1, #2: Sent referral appears in patient referrals tab with correct direction."""
        shared_uuid = uuid.uuid4()
        ReferralSent.objects.create(
            from_institution=self.inst_a, to_institution=self.inst_b,
            institution=self.inst_a, patient=self.patient,
            from_clinician=self.clin_a, to_clinician=self.clin_b,
            referral_uuid=shared_uuid, initial_message='Test referral.',
            snapshot_data={'schema_version': 1},
            added_by=self.clin_a, last_edit_by=self.clin_a,
        )
        client = Client()
        client.force_login(self.clin_a)
        response = client.get(self.tab_url)
        self.assertEqual(response.context['referral_count'], 1)
        entry = response.context['timeline'][0]
        self.assertEqual(entry['direction'], 'sent')

    def test_other_institution_referral_not_visible(self):
        """AC #5: Referrals from unrelated institutions must not appear in patient tab."""
        # Create a referral between inst_b and a third institution — NOT involving inst_a
        inst_c = Institution.objects.create(
            name='Tab Gamma', slug='tab-gamma',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        clin_c = User.objects.create_user(
            username='clin_c_tab', password='Testpass1!',
            first_name='Tab', last_name='Gamma',
            position='Medical Officer', mobile_primary='0770991099',
            user_type=UserType.USER, institution=inst_c,
        )
        # Unrelated referral — from inst_b, not inst_a
        shared_uuid_unrelated = uuid.uuid4()
        ReferralSent.objects.create(
            from_institution=self.inst_b, to_institution=inst_c,
            institution=self.inst_b, patient=None,
            from_clinician=self.clin_b, to_clinician=clin_c,
            referral_uuid=shared_uuid_unrelated, initial_message='Unrelated.',
            snapshot_data={'schema_version': 1},
            added_by=self.clin_b, last_edit_by=self.clin_b,
        )

        # inst_a clinician's view of the patient tab — must NOT see inst_b's referral
        client = Client()
        client.force_login(self.clin_a)
        response = client.get(self.tab_url)
        uuids = [str(e['referral_uuid']) for e in response.context['timeline']]
        self.assertNotIn(
            str(shared_uuid_unrelated), uuids,
            "AC #5: Unrelated institution's referral must not appear in patient tab",
        )
