"""
institution/tests/test_pdf_branding.py
Tests for PDF Report Branding (Story 3.4 — FR59).

Verifies that BasePDFGenerator accepts institution parameter
and that institution branding is injected correctly.
"""
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()


class PDFBrandingTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_pdf', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771551001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='Alpha PDF Hospital', slug='alpha-pdf',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Beta PDF Clinic', slug='beta-pdf',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )


@override_settings(MULTI_INSTITUTION_ENABLED=True)
class BasePDFGeneratorBrandingTest(PDFBrandingTestBase):
    """AC #1–#3: BasePDFGenerator stores institution for branding injection."""

    def test_generator_accepts_institution_param(self):
        """AC #1: BasePDFGenerator must accept institution= keyword argument."""
        from reports.utils.pdf_generator import BasePDFGenerator
        try:
            generator = BasePDFGenerator(institution=self.inst_a)
            self.assertEqual(generator.institution, self.inst_a,
                "AC #1: generator.institution must store the passed institution")
        except TypeError as e:
            self.fail(f"AC #1: BasePDFGenerator must accept institution= parameter. "
                      f"Ensure Story 2.5 Task 1 is implemented. Error: {e}")

    def test_generator_default_institution_is_none(self):
        """AC #1: Default institution=None means no-branding (backwards compatible)."""
        from reports.utils.pdf_generator import BasePDFGenerator
        generator = BasePDFGenerator()
        self.assertIsNone(generator.institution,
            "Default institution must be None — backward-compatible for non-institution contexts")

    def test_patient_pdf_generator_accepts_institution(self):
        """AC #1: PatientPDFGenerator (subclass) inherits institution parameter."""
        from reports.utils.pdf_generator import PatientPDFGenerator
        try:
            generator = PatientPDFGenerator(institution=self.inst_a)
            self.assertEqual(generator.institution, self.inst_a)
        except TypeError as e:
            self.fail(f"AC #1: PatientPDFGenerator must accept institution= parameter: {e}")

    def test_institution_b_context_uses_b_branding(self):
        """AC #3: Superadmin viewing Institution B gets Institution B's branding."""
        from reports.utils.pdf_generator import BasePDFGenerator
        generator_a = BasePDFGenerator(institution=self.inst_a)
        generator_b = BasePDFGenerator(institution=self.inst_b)
        self.assertEqual(generator_a.institution.name, 'Alpha PDF Hospital')
        self.assertEqual(generator_b.institution.name, 'Beta PDF Clinic')
        self.assertNotEqual(generator_a.institution, generator_b.institution,
            "AC #3: Separate generator instances must carry separate institution branding")

    def test_no_logo_institution_does_not_raise(self):
        """AC #2: Institution without logo does not cause generator to fail."""
        from reports.utils.pdf_generator import BasePDFGenerator
        # inst_a has no logo
        self.assertFalse(bool(self.inst_a.logo),
            "Test precondition: inst_a must have no logo for this test")
        try:
            generator = BasePDFGenerator(institution=self.inst_a)
            # Cannot call generate() in unit tests without a PDF template + patient data,
            # but we verify the generator instantiates correctly.
            self.assertEqual(generator.institution, self.inst_a)
        except Exception as e:
            self.fail(f"AC #2: Generator must not raise when institution has no logo: {e}")
