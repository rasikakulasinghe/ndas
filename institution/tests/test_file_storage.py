"""
Story 1.5 — Institution-aware file storage tests.
Tests for path callables and protected media view isolation.
"""
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from institution.models import Institution
from institution.views import protected_media_view
from patients.models import Patient
from ndas.custom_codes.validators import (
    get_institution_video_path,
    get_institution_attachment_path,
)
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()


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


class InstitutionFilePathTest(TestCase):
    """Tests for institution-aware upload_to callables."""

    def setUp(self):
        self.institution_a = Institution.objects.create(
            name='Hospital A',
            slug='hospital-a',
            subscription_status=SubscriptionStatus.ACTIVE,
        )
        self.patient_a = make_patient('Baby A', self.institution_a, bht='FS001')
        self.patient_no_institution = make_patient('Baby No Inst', None, bht='FS002')

    def test_get_institution_video_path_uses_slug(self):
        """AC #1: Video path contains institution slug."""
        class FakeVideo:
            patient = self.patient_a
            patient_id = self.patient_a.pk

        result = get_institution_video_path(FakeVideo(), 'my_video.mp4')
        self.assertTrue(result.startswith('hospital-a/videos/'))
        self.assertIn('my_video.mp4', result)

    def test_get_institution_attachment_path_uses_slug(self):
        """AC #2: Attachment path contains institution slug."""
        class FakeAttachment:
            patient = self.patient_a
            patient_id = self.patient_a.pk

        result = get_institution_attachment_path(FakeAttachment(), 'report.pdf')
        self.assertTrue(result.startswith('hospital-a/attachments/'))
        self.assertIn('report.pdf', result)

    def test_video_path_fallback_when_no_institution(self):
        """Fallback to 'pending' when institution is None."""
        class FakeVideo:
            patient = self.patient_no_institution
            patient_id = self.patient_no_institution.pk

        result = get_institution_video_path(FakeVideo(), 'test.mp4')
        self.assertTrue(result.startswith('pending/videos/'))

    def test_attachment_path_fallback_when_no_institution(self):
        """Fallback to 'pending' when institution is None."""
        class FakeAttachment:
            patient = self.patient_no_institution
            patient_id = self.patient_no_institution.pk

        result = get_institution_attachment_path(FakeAttachment(), 'test.pdf')
        self.assertTrue(result.startswith('pending/attachments/'))

    def test_video_path_fallback_when_no_patient(self):
        """Fallback to 'pending' when patient_id is falsy."""
        class FakeVideo:
            patient = None
            patient_id = None

        result = get_institution_video_path(FakeVideo(), 'test.mp4')
        self.assertTrue(result.startswith('pending/videos/'))

    def test_path_sanitizes_filename(self):
        """Path callable sanitizes dangerous filenames (path traversal)."""
        class FakeVideo:
            patient = self.patient_a
            patient_id = self.patient_a.pk

        result = get_institution_video_path(FakeVideo(), '../../etc/passwd')
        self.assertNotIn('../', result)
        self.assertNotIn('etc/passwd', result)


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class ProtectedMediaViewTest(TestCase):
    """Tests for protected_media_view institution isolation."""

    def setUp(self):
        self.factory = RequestFactory()
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
            username='clinician_a_fs',
            password='testpass123',
            first_name='A',
            last_name='Clinician',
            mobile_primary='0771230011',
            user_type=UserType.USER,
            institution=self.institution_a,
        )
        self.superadmin = User.objects.create_user(
            username='superadmin_fs',
            password='testpass123',
            first_name='Super',
            last_name='Admin',
            mobile_primary='0771230012',
            user_type=UserType.SUPERADMIN,
            is_superuser=True,
        )

    def _make_media_request(self, path, user, institution):
        """Helper: create a media request with institution context."""
        request = self.factory.get(f'/media/{path}')
        request.user = user
        request.institution = institution
        return request

    def test_clinician_blocked_from_other_institution_file(self):
        """AC #3: Clinician from Institution A cannot access Institution B files."""
        request = self._make_media_request(
            'hospital-b/videos/secret.mp4',
            self.clinician_a,
            self.institution_a,
        )
        response = protected_media_view(request, path='hospital-b/videos/secret.mp4')
        self.assertEqual(response.status_code, 403)

    def test_clinician_allowed_own_institution_path(self):
        """Clinician from Institution A can access Institution A's path structure.

        The view passes the institution check and calls django_serve_static().
        Since no actual file exists in the test environment, Http404 is expected —
        that is NOT a 403 and confirms the access check passed.
        """
        from django.http import Http404

        request = self._make_media_request(
            'hospital-a/videos/my_video.mp4',
            self.clinician_a,
            self.institution_a,
        )
        try:
            response = protected_media_view(request, path='hospital-a/videos/my_video.mp4')
            # If a response is returned, it must not be 403
            self.assertNotEqual(response.status_code, 403)
        except Http404:
            # Http404 means the file doesn't exist on disk — access check PASSED
            pass

    def test_superadmin_can_access_any_institution_file(self):
        """AC #3 complement: SUPERADMIN can access any institution's media path."""
        from django.http import Http404

        request = self._make_media_request(
            'hospital-b/videos/secret.mp4',
            self.superadmin,
            None,  # SUPERADMIN has no single institution context
        )
        try:
            response = protected_media_view(request, path='hospital-b/videos/secret.mp4')
            # If response is returned, it must not be 403
            self.assertNotEqual(response.status_code, 403)
        except Http404:
            # Http404 means file doesn't exist on disk — access check PASSED for SUPERADMIN
            pass

    def test_clinician_blocked_from_other_institution_logo(self):
        """Clinician from Institution A cannot access Institution B's logo path."""
        request = self._make_media_request(
            'hospital-b/logo/logo.png',
            self.clinician_a,
            self.institution_a,
        )
        response = protected_media_view(request, path='hospital-b/logo/logo.png')
        self.assertEqual(response.status_code, 403)

    def test_clinician_allowed_own_institution_logo_path(self):
        """Clinician from Institution A can access Institution A's own logo path structure."""
        from django.http import Http404

        request = self._make_media_request(
            'hospital-a/logo/logo.png',
            self.clinician_a,
            self.institution_a,
        )
        try:
            response = protected_media_view(request, path='hospital-a/logo/logo.png')
            self.assertNotEqual(response.status_code, 403)
        except Http404:
            # File doesn't exist on disk — access check PASSED
            pass

    def test_superadmin_can_access_any_institution_logo(self):
        """SUPERADMIN can access any institution's logo path."""
        from django.http import Http404

        request = self._make_media_request(
            'hospital-b/logo/logo.png',
            self.superadmin,
            None,
        )
        try:
            response = protected_media_view(request, path='hospital-b/logo/logo.png')
            self.assertNotEqual(response.status_code, 403)
        except Http404:
            # File doesn't exist on disk — access check PASSED for SUPERADMIN
            pass

    def test_clinician_allowed_own_logo_when_request_institution_unset(self):
        """Regression: InstitutionContextMiddleware exempts '/media/' from context
        resolution, so real media requests never get request.institution set by the
        middleware. The view must fall back to request.user.institution instead of
        treating an unset request.institution as "no institution" (which would 403
        every clinician out of their own institution's logo/video/attachment files).
        """
        from django.http import Http404

        request = self.factory.get('/media/hospital-a/logo/logo.png')
        request.user = self.clinician_a
        # Deliberately NOT setting request.institution — matches real middleware behavior.
        try:
            response = protected_media_view(request, path='hospital-a/logo/logo.png')
            self.assertNotEqual(response.status_code, 403)
        except Http404:
            # File doesn't exist on disk — access check PASSED
            pass

    def test_clinician_blocked_from_other_institution_logo_when_request_institution_unset(self):
        """Regression companion: the fallback must still enforce isolation."""
        request = self.factory.get('/media/hospital-b/logo/logo.png')
        request.user = self.clinician_a
        response = protected_media_view(request, path='hospital-b/logo/logo.png')
        self.assertEqual(response.status_code, 403)

    def test_non_institution_path_not_blocked(self):
        """Non-partitioned paths (e.g. institution_logos/) are not blocked by institution check."""
        from django.http import Http404

        request = self._make_media_request(
            'institution_logos/logo.png',
            self.clinician_a,
            self.institution_a,
        )
        try:
            response = protected_media_view(request, path='institution_logos/logo.png')
            # Not a {slug}/videos/ or {slug}/attachments/ path — no institution check
            self.assertNotEqual(response.status_code, 403)
        except Http404:
            # File doesn't exist on disk — access check was not triggered (correct)
            pass


@override_settings(MULTI_INSTITUTION_ENABLED=True, DEBUG=False)
class ProtectedMediaViewProductionModeTest(TestCase):
    """
    Regression test for the NDAS-01 fix: in production (DEBUG=False),
    Nginx must never serve /media/ from disk directly, since that bypasses
    institution isolation entirely. protected_media_view must instead
    perform the same authorization check and then hand serving off to
    Nginx via X-Accel-Redirect, rather than skipping the check.
    """

    def setUp(self):
        self.factory = RequestFactory()
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
            username='clinician_a_prod',
            password='testpass123',
            first_name='A',
            last_name='Clinician',
            mobile_primary='0771230021',
            user_type=UserType.USER,
            institution=self.institution_a,
        )

    def _make_media_request(self, path, user, institution):
        request = self.factory.get(f'/media/{path}')
        request.user = user
        request.institution = institution
        return request

    def test_authorized_request_gets_x_accel_redirect_not_raw_bytes(self):
        """A clinician's own-institution file is authorized, then delegated to
        Nginx via X-Accel-Redirect — Django never reads the file from disk."""
        request = self._make_media_request(
            'hospital-a/videos/assessment.mp4',
            self.clinician_a,
            self.institution_a,
        )
        response = protected_media_view(request, path='hospital-a/videos/assessment.mp4')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['X-Accel-Redirect'],
            '/x-accel-media/hospital-a/videos/assessment.mp4',
        )

    def test_cross_institution_request_still_blocked_before_x_accel_redirect(self):
        """The authorization check must still run — and still 403 — before any
        X-Accel-Redirect is issued, even when Django isn't serving the bytes itself."""
        request = self._make_media_request(
            'hospital-b/videos/secret.mp4',
            self.clinician_a,
            self.institution_a,
        )
        response = protected_media_view(request, path='hospital-b/videos/secret.mp4')

        self.assertEqual(response.status_code, 403)
        self.assertNotIn('X-Accel-Redirect', response)
