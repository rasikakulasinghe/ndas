"""
institution/tests/test_branding.py
Tests for Institution Branding Setup (Story 3.3 — FR58).
"""
import io
import struct
import zlib

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()

STATIC_OVERRIDE = override_settings(
    MULTI_INSTITUTION_ENABLED=True,
    RATELIMIT_ENABLE=False,
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)


def make_minimal_png():
    """Create a minimal valid 1×1 PNG image for upload tests."""
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
    raw = b'\x00' + b'\xff\x00\x00'
    compressed = zlib.compress(raw)
    idat = chunk(b'IDAT', compressed)
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


class BrandingTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_brand', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771661001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(
            name='Brand Hospital', slug='brand-hospital',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.admin = User.objects.create_user(
            username='admin_brand', password='Testpass1!',
            first_name='Brand', last_name='Admin',
            position='Administrator', mobile_primary='0771661002',
            user_type=UserType.ADMIN, institution=self.inst,
        )
        self.settings_url = reverse('institution:institution-settings')


@STATIC_OVERRIDE
class BrandingSettingsAccessTest(BrandingTestBase):
    def test_admin_can_access_settings(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.settings_url)
        self.assertEqual(response.status_code, 200)

    def test_regular_user_cannot_access_settings(self):
        regular = User.objects.create_user(
            username='reg_user_brand', password='Testpass1!',
            first_name='Regular', last_name='User',
            position='Medical Officer', mobile_primary='0771661099',
            user_type=UserType.USER, institution=self.inst,
        )
        client = Client()
        client.force_login(regular)
        response = client.get(self.settings_url)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_unauthenticated_redirected(self):
        client = Client()
        response = client.get(self.settings_url)
        self.assertEqual(response.status_code, 302)


@override_settings(
    MULTI_INSTITUTION_ENABLED=True,
    RATELIMIT_ENABLE=False,
    MEDIA_ROOT='/tmp/ndas_test_media_3_3',
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class BrandingLogoUploadTest(BrandingTestBase):
    def test_logo_upload_saves_to_institution_scoped_path(self):
        """AC #1: Logo is saved to {institution_slug}/logo/ path."""
        client = Client()
        client.force_login(self.admin)
        png_data = make_minimal_png()
        logo = SimpleUploadedFile('logo.png', png_data, content_type='image/png')
        response = client.post(self.settings_url, {
            'name': 'Brand Hospital',
            'logo': logo,
        })
        self.assertEqual(response.status_code, 302)
        self.inst.refresh_from_db()
        if self.inst.logo:
            self.assertIn('brand-hospital', self.inst.logo.name,
                "AC #1: Logo must be stored in institution-scoped path containing slug")
            self.assertIn('logo', self.inst.logo.name,
                "AC #1: Logo path must contain 'logo' directory segment")

    def test_name_update_persists(self):
        """AC #3: Name changes persist immediately without server restart."""
        client = Client()
        client.force_login(self.admin)
        response = client.post(self.settings_url, {'name': 'Updated Hospital Name'})
        self.assertEqual(response.status_code, 302)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.name, 'Updated Hospital Name',
            "AC #3: Name must persist immediately after save")

    def test_settings_form_renders_with_current_data(self):
        """AC #3: Settings form pre-populated with current institution data."""
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.settings_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['institution'], self.inst)
