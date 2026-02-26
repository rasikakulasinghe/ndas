"""
institution/tests/test_isolation.py

NFR19 — Zero Cross-Institution Data Leakage Verification

MANDATORY: All tests in this file must PASS before MULTI_INSTITUTION_ENABLED=True
is set in the staging .env. Any failure here is a BLOCKING DEFECT.

Test coverage:
  - ORM-level: for_institution() and all_institutions() (Story 1.4 first pass)
  - Patient list view isolation
  - Patient detail 404 for cross-institution access
  - Patient detail 200 for own-institution access
  - Video manager list isolation
  - Direct URL attack prevention
  - Response body content check (patient name not leaked)
"""
from django.test import TestCase, Client, RequestFactory, override_settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from institution.models import Institution
from patients.models import Patient
from patients.views import patient_view
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()

# Bypass CompressedManifestStaticFilesStorage in view-level tests (requires collectstatic).
_VIEW_SETTINGS = dict(
    MULTI_INSTITUTION_ENABLED=True,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
    RATELIMIT_ENABLE=False,
)


def make_patient(baby_name, institution, bht=None):
    """Helper: create a Patient with all required fields."""
    return Patient.objects.create(
        bht=bht,
        baby_name=baby_name,
        mother_name='Test Mother',
        dob_tob=timezone.now(),
        gender='Male',
        pog_wks=38,
        pog_days=2,
        birth_weight=3000,
        ofc=33,
        mo_delivery='Normal vaginal delivery (NVD)',
        tp_mobile='0711234567',
        institution=institution,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ORM-level isolation tests (Story 1.4 first pass, no view/HTTP)
# ─────────────────────────────────────────────────────────────────────────────

class InstitutionPatientIsolationTest(TestCase):
    """
    AC #1: for_institution() filters correctly.
    AC #2: No cross-institution records returned.
    AC #3: Cross-institution URL attack → 404.
    AC #4: all_institutions() returns all records.
    """

    def setUp(self):
        self.institution_a = Institution.objects.create(
            name='Hospital A',
            slug='hospital-a',
            subscription_status=SubscriptionStatus.ACTIVE,
        )
        self.institution_b = Institution.objects.create(
            name='Hospital B',
            slug='hospital-b',
            subscription_status=SubscriptionStatus.ACTIVE,
        )
        self.clinician_a = User.objects.create_user(
            username='clinician_a',
            password='testpass123',
            first_name='A',
            last_name='Clinician',
            mobile_primary='0771234001',
            user_type=UserType.USER,
            institution=self.institution_a,
        )
        self.clinician_b = User.objects.create_user(
            username='clinician_b',
            password='testpass123',
            first_name='B',
            last_name='Clinician',
            mobile_primary='0771234002',
            user_type=UserType.USER,
            institution=self.institution_b,
        )
        self.patient_a = make_patient('Patient A', self.institution_a, bht='ISO001')
        self.patient_b = make_patient('Patient B', self.institution_b, bht='ISO002')

    def test_for_institution_returns_only_own_patients(self):
        """for_institution(A) returns only A's patients, never B's."""
        qs = Patient.objects.for_institution(self.institution_a)
        self.assertIn(self.patient_a, qs)
        self.assertNotIn(self.patient_b, qs)

    def test_for_institution_b_returns_only_b_patients(self):
        """for_institution(B) returns only B's patients, never A's."""
        qs = Patient.objects.for_institution(self.institution_b)
        self.assertIn(self.patient_b, qs)
        self.assertNotIn(self.patient_a, qs)

    def test_for_institution_none_returns_all(self):
        """for_institution(None) returns all records — Phase 1 / backward-compatible."""
        qs = Patient.objects.for_institution(None)
        self.assertIn(self.patient_a, qs)
        self.assertIn(self.patient_b, qs)

    def test_all_institutions_returns_all_records(self):
        """AC #4: all_institutions() returns records from every institution."""
        qs = Patient.objects.all_institutions()
        self.assertEqual(qs.count(), 2)

    def test_cross_institution_patient_detail_raises_404(self):
        """AC #3: Clinician A gets Http404 when accessing Institution B patient via RequestFactory."""
        factory = RequestFactory()
        request = factory.get(f'/patient/view/{self.patient_b.pk}/')
        request.user = self.clinician_a
        request.institution = self.institution_a

        with self.assertRaises(Http404):
            patient_view(request, pk=self.patient_b.pk)

    def test_own_institution_patient_accessible_via_scoped_queryset(self):
        """AC #3 complement: for_institution(A) lookup for A's patient succeeds."""
        patient = get_object_or_404(
            Patient.objects.for_institution(self.institution_a),
            pk=self.patient_a.pk,
        )
        self.assertEqual(patient.pk, self.patient_a.pk)

    def test_institution_a_count_excludes_b(self):
        """Patient count scoped to A never includes B's patients."""
        count = Patient.objects.for_institution(self.institution_a).count()
        self.assertEqual(count, 1)

    def test_institution_b_count_excludes_a(self):
        """Patient count scoped to B never includes A's patients."""
        count = Patient.objects.for_institution(self.institution_b).count()
        self.assertEqual(count, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Shared base for view-level isolation tests
# ─────────────────────────────────────────────────────────────────────────────

class IsolationTestBase(TestCase):
    """
    Shared setUp for all view-level isolation tests.
    Creates two completely isolated institutions with distinct patients.
    """

    def setUp(self):
        self.client_a = Client()
        self.client_b = Client()

        # ── Institutions
        self.institution_a = Institution.objects.create(
            name='Hospital Alpha',
            slug='hospital-alpha',
            subscription_status=SubscriptionStatus.ACTIVE,
            is_active=True,
        )
        self.institution_b = Institution.objects.create(
            name='Hospital Beta',
            slug='hospital-beta',
            subscription_status=SubscriptionStatus.ACTIVE,
            is_active=True,
        )

        # ── Clinicians
        self.clinician_a = User.objects.create_user(
            username='clinician_alpha', password='Testpass1!',
            first_name='Alice', last_name='Alpha',
            position='Medical Officer',
            mobile_primary='0771110001',
            user_type=UserType.USER,
            institution=self.institution_a,
        )
        self.clinician_b = User.objects.create_user(
            username='clinician_beta', password='Testpass1!',
            first_name='Bob', last_name='Beta',
            position='Medical Officer',
            mobile_primary='0771110002',
            user_type=UserType.USER,
            institution=self.institution_b,
        )

        # ── Patients (unique names for content checks)
        self.patient_a = Patient.objects.create(
            bht='ALPHA-BHT-001',
            baby_name='AlphaBabyUniqueXYZ',
            mother_name='Alpha Mother',
            dob_tob=timezone.now(),
            gender='Male',
            pog_wks=38, pog_days=2,
            birth_weight=3000, ofc=33,
            mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711000001',
            added_by=self.clinician_a,
            institution=self.institution_a,
        )
        self.patient_b = Patient.objects.create(
            bht='BETA-BHT-001',
            baby_name='BetaBabyUniqueXYZ',
            mother_name='Beta Mother',
            dob_tob=timezone.now(),
            gender='Female',
            pog_wks=39, pog_days=0,
            birth_weight=3200, ofc=34,
            mo_delivery='Normal vaginal delivery (NVD)',
            tp_mobile='0711000002',
            added_by=self.clinician_b,
            institution=self.institution_b,
        )

        self.client_a.force_login(self.clinician_a)
        self.client_b.force_login(self.clinician_b)


# ─────────────────────────────────────────────────────────────────────────────
# View-level isolation tests: Patient list
# ─────────────────────────────────────────────────────────────────────────────

@override_settings(**_VIEW_SETTINGS)
class PatientListIsolationTest(IsolationTestBase):
    """AC #1, #2: Patient list view returns only own institution's patients."""

    def test_patient_list_shows_own_institution_only(self):
        """Clinician A sees Patient A; Patient B must not appear in list."""
        response = self.client_a.get(reverse('manage-patients'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('AlphaBabyUniqueXYZ', content,
            "Patient A's name should appear in Institution A's patient list")
        self.assertNotIn('BetaBabyUniqueXYZ', content,
            "Patient B's name must NOT appear in Institution A's patient list (data leak!)")

    def test_patient_b_list_shows_own_institution_only(self):
        """Clinician B sees Patient B; Patient A must not appear."""
        response = self.client_b.get(reverse('manage-patients'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('BetaBabyUniqueXYZ', content)
        self.assertNotIn('AlphaBabyUniqueXYZ', content,
            "Patient A's name must NOT appear in Institution B's patient list (data leak!)")


# ─────────────────────────────────────────────────────────────────────────────
# View-level isolation tests: Patient detail
# ─────────────────────────────────────────────────────────────────────────────

@override_settings(**_VIEW_SETTINGS)
class PatientDetailIsolationTest(IsolationTestBase):
    """AC #2, #3: Patient detail view enforces institution boundary."""

    def test_cross_institution_patient_detail_returns_404(self):
        """AC #3: Clinician A gets 404 for Institution B patient detail."""
        url = reverse('view-patient', args=[self.patient_b.pk])
        response = self.client_a.get(url)
        self.assertEqual(response.status_code, 404,
            f"Expected 404 for cross-institution patient access, got {response.status_code}. "
            f"This is a BLOCKING DEFECT — Institution B patient data is accessible to Institution A!")

    def test_url_attack_response_contains_no_b_data(self):
        """AC #3: 404 response must not contain Institution B patient data."""
        url = reverse('view-patient', args=[self.patient_b.pk])
        response = self.client_a.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('BetaBabyUniqueXYZ', response.content.decode())

    def test_own_patient_detail_response_contains_no_b_data(self):
        """Even on successful own-institution pages, B's data must not appear."""
        url = reverse('view-patient', args=[self.patient_a.pk])
        response = self.client_a.get(url)
        # May succeed (200) or redirect (302) depending on template/session state
        if response.status_code == 200:
            content = response.content.decode()
            self.assertNotIn('BetaBabyUniqueXYZ', content)
            self.assertNotIn('BETA-BHT-001', content)


# ─────────────────────────────────────────────────────────────────────────────
# View-level isolation tests: Video manager
# ─────────────────────────────────────────────────────────────────────────────

@override_settings(**_VIEW_SETTINGS)
class VideoListIsolationTest(IsolationTestBase):
    """AC #2: Video manager list scoped to own institution."""

    def test_video_manager_shows_no_cross_institution_patient_data(self):
        """Video manager must not reference Institution B patient names."""
        response = self.client_a.get(reverse('video:manager'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn('BetaBabyUniqueXYZ', content)
        self.assertNotIn('BETA-BHT-001', content)

    def test_video_by_patient_cross_institution_returns_404(self):
        """video:manager-by-patient with Institution B patient ID → 404."""
        url = reverse('video:manager-by-patient', args=[self.patient_b.pk])
        response = self.client_a.get(url)
        self.assertEqual(response.status_code, 404,
            f"Clinician A should get 404 for Institution B's patient video manager, "
            f"got {response.status_code}")


# ─────────────────────────────────────────────────────────────────────────────
# View-level isolation tests: Direct URL attacks
# ─────────────────────────────────────────────────────────────────────────────

@override_settings(**_VIEW_SETTINGS)
class URLAttackIsolationTest(IsolationTestBase):
    """AC #3: Direct URL attacks must always return 404 for cross-institution resources."""

    def test_patient_detail_url_attack(self):
        """Direct patient detail URL → 404."""
        url = f'/patient/view/{self.patient_b.pk}/'
        response = self.client_a.get(url)
        self.assertEqual(response.status_code, 404)

    def test_patient_edit_url_attack(self):
        """Patient edit URL → 404 (no data returned, no partial edit allowed)."""
        url = f'/patient/edit/{self.patient_b.pk}/'
        response = self.client_a.get(url)
        self.assertIn(response.status_code, [404, 302],
            "Cross-institution patient edit must return 404 or redirect; must never return 200")

    def test_patient_delete_does_not_delete_b_patient(self):
        """Cross-institution patient delete must not execute; B patient still exists."""
        url = f'/patient/delete/{self.patient_b.pk}/'
        response = self.client_a.post(url)
        self.assertIn(response.status_code, [404, 302, 405],
            "Cross-institution patient delete must return 404, redirect, or 405")
        # Critical: Patient B must still exist
        self.assertTrue(Patient.objects.filter(pk=self.patient_b.pk).exists(),
            "Institution B patient should NOT have been deleted by Institution A's attack!")

    def test_video_manager_by_patient_url_attack(self):
        """video:manager-by-patient with Institution B patient ID → 404.
        No actual video file needed — the view scopes by patient institution.
        """
        url = reverse('video:manager-by-patient', args=[self.patient_b.pk])
        response = self.client_a.get(url)
        self.assertEqual(response.status_code, 404,
            f"Clinician A must get 404 for Institution B's video manager via direct URL, "
            f"got {response.status_code}")


# ─────────────────────────────────────────────────────────────────────────────
# View-level isolation tests: Assessment querysets (Story 1.7 AC #2)
# ─────────────────────────────────────────────────────────────────────────────

@override_settings(**_VIEW_SETTINGS)
class AssessmentQuerysetIsolationTest(IsolationTestBase):
    """
    AC #2: Assessment querysets scoped via patient__in=for_institution() must
    never return assessments belonging to another institution's patients.

    This verifies the 'patient__in=_patients_qs' pattern used in patients/views.py
    dashboard counts and any future assessment list views.

    Uses CDICRecord as the representative assessment model (minimal required fields).
    The pattern being verified is universal — if it holds for CDICRecord it holds
    for all assessment types (same patient__in scoping).
    """

    def setUp(self):
        super().setUp()
        from patients.models import CDICRecord
        from django.utils import timezone as tz
        today = tz.now().date()
        self.cdic_a = CDICRecord.objects.create(
            patient=self.patient_a,
            assessment_date=today,
            added_by=self.clinician_a,
        )
        self.cdic_b = CDICRecord.objects.create(
            patient=self.patient_b,
            assessment_date=today,
            added_by=self.clinician_b,
        )

    def test_cdic_scoped_to_institution_a_excludes_b(self):
        """CDICRecord filtered via patient__in=for_institution(A) never returns B's record."""
        from patients.models import CDICRecord
        patients_a = Patient.objects.for_institution(self.institution_a)
        qs = CDICRecord.objects.filter(patient__in=patients_a)
        self.assertIn(self.cdic_a, qs)
        self.assertNotIn(self.cdic_b, qs,
            "Institution B's CDICRecord must NOT appear in Institution A's scoped queryset (data leak!)")

    def test_cdic_scoped_to_institution_b_excludes_a(self):
        """CDICRecord filtered via patient__in=for_institution(B) never returns A's record."""
        from patients.models import CDICRecord
        patients_b = Patient.objects.for_institution(self.institution_b)
        qs = CDICRecord.objects.filter(patient__in=patients_b)
        self.assertIn(self.cdic_b, qs)
        self.assertNotIn(self.cdic_a, qs,
            "Institution A's CDICRecord must NOT appear in Institution B's scoped queryset (data leak!)")

    def test_assessment_count_matches_institution_scope(self):
        """Dashboard pattern: assessment count via patient__in returns institution-specific totals."""
        from patients.models import CDICRecord
        patients_a = Patient.objects.for_institution(self.institution_a)
        patients_b = Patient.objects.for_institution(self.institution_b)
        count_a = CDICRecord.objects.filter(patient__in=patients_a).count()
        count_b = CDICRecord.objects.filter(patient__in=patients_b).count()
        self.assertEqual(count_a, 1, "Institution A should have exactly 1 CDICRecord")
        self.assertEqual(count_b, 1, "Institution B should have exactly 1 CDICRecord")
        # Verify no double-counting: total must equal the sum of scoped counts
        total = CDICRecord.objects.count()
        self.assertEqual(total, count_a + count_b,
            "Total CDICRecords must equal sum of per-institution counts — no double-counting")


# ─────────────────────────────────────────────────────────────────────────────
# Feature flag off: Phase 1 regression
# ─────────────────────────────────────────────────────────────────────────────

@override_settings(
    MULTI_INSTITUTION_ENABLED=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
    RATELIMIT_ENABLE=False,
)
class FeatureFlagOffRegressionTest(IsolationTestBase):
    """AC #5: With MULTI_INSTITUTION_ENABLED=False, Phase 1 behaviour is unchanged."""

    def test_patient_list_accessible_with_flag_off(self):
        """Patient list works normally when multi-institution is disabled."""
        response = self.client_a.get(reverse('manage-patients'))
        self.assertIn(response.status_code, [200, 302])

    def test_no_500_errors_with_flag_off(self):
        """With flag off, views must not crash with 500 errors."""
        response = self.client_a.get(reverse('manage-patients'))
        self.assertNotEqual(response.status_code, 500,
            "Page must not crash with 500 when MULTI_INSTITUTION_ENABLED=False")
