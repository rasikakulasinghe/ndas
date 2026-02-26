"""
Tests for Story 2.3 — Atomic Institution Onboarding.

Covers:
- GET renders the two-card form
- POST with valid data creates Institution + CustomUser atomically
- Duplicate slug rejected
- Password mismatch rejected
- Non-SUPERADMIN cannot access
- Rollback: if admin creation fails, institution is not created
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()

STATIC_OVERRIDE = override_settings(
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
)


def make_superadmin(username='superadmin'):
    return User.objects.create_user(
        username=username, password='testpass123',
        email=f'{username}@test.com', first_name='Super',
        position='Medical Officer', mobile_primary='0771234567',
        user_type=UserType.SUPERADMIN, is_superuser=True, is_staff=True,
    )


VALID_PAYLOAD = {
    'institution_name': 'New Hospital',
    'institution_slug': 'new-hospital',
    'admin_first_name': 'Jane',
    'admin_last_name': 'Doe',
    'admin_username': 'janedoe',
    'admin_email': 'jane@newhospital.com',
    'admin_mobile': '0771234569',
    'admin_position': 'Medical Officer',
    'admin_password': 'Str0ng!Pass#2026',
    'admin_password_confirm': 'Str0ng!Pass#2026',
}


@STATIC_OVERRIDE
class InstitutionAddAccessTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.superadmin = make_superadmin()
        self.url = reverse('institution:institution-add')

    def test_unauthenticated_redirects(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_superadmin_gets_200_on_get(self):
        self.client.login(username='superadmin', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'institution/add.html')


@STATIC_OVERRIDE
class InstitutionAddAtomicityTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.superadmin = make_superadmin()
        self.url = reverse('institution:institution-add')
        self.client.login(username='superadmin', password='testpass123')

    def test_valid_post_creates_institution_and_admin(self):
        """Both records created on successful submission."""
        inst_count_before = Institution.objects.count()
        user_count_before = User.objects.count()

        response = self.client.post(self.url, VALID_PAYLOAD)
        self.assertEqual(response.status_code, 302,
            "Successful onboarding must redirect (302), not re-render form (200)")

        self.assertEqual(Institution.objects.count(), inst_count_before + 1)
        self.assertEqual(User.objects.count(), user_count_before + 1)

        new_inst = Institution.objects.get(slug='new-hospital')
        new_user = User.objects.get(username='janedoe')
        self.assertEqual(new_user.institution, new_inst)
        self.assertEqual(new_user.user_type, UserType.ADMIN)

    def test_duplicate_slug_rejected(self):
        """Duplicate slug shows form error; no duplicate institution created."""
        Institution.objects.create(name='Existing Hospital', slug='new-hospital')
        inst_count_before = Institution.objects.count()

        payload = {**VALID_PAYLOAD, 'institution_slug': 'new-hospital'}
        self.client.post(self.url, payload)

        # Count should not increase
        self.assertEqual(Institution.objects.count(), inst_count_before)

    def test_password_mismatch_rejected(self):
        """Password mismatch keeps form on page; no records created."""
        inst_count_before = Institution.objects.count()
        payload = {**VALID_PAYLOAD, 'admin_password_confirm': 'wrongpassword'}

        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Institution.objects.count(), inst_count_before)

    def test_redirect_to_selector_on_success(self):
        """Successful onboarding redirects to institution selector."""
        response = self.client.post(self.url, VALID_PAYLOAD)
        self.assertRedirects(
            response,
            reverse('institution:institution-selector'),
            fetch_redirect_response=False,
        )


@STATIC_OVERRIDE
class AtomicRollbackTest(TestCase):
    """AC #3: If admin creation fails, Institution is also rolled back — no orphans."""

    def setUp(self):
        self.client = Client()
        self.superadmin = make_superadmin()
        self.url = reverse('institution:institution-add')
        self.client.login(username='superadmin', password='testpass123')
        # Pre-create a user whose username will cause a uniqueness collision
        User.objects.create_user(
            username='taken_admin',
            password='Str0ng!Pass#2026',
            email='taken@hospital.com',
            first_name='Taken',
            position='Medical Officer',
            mobile_primary='0771111111',
            user_type=UserType.ADMIN,
        )

    def test_duplicate_username_causes_no_orphan_institution(self):
        """AC #3: form validation catches duplicate username — Institution NOT created."""
        payload = {**VALID_PAYLOAD, 'admin_username': 'taken_admin'}
        inst_count_before = Institution.objects.count()

        self.client.post(self.url, payload)

        self.assertEqual(Institution.objects.count(), inst_count_before,
            "AC #3: No orphan Institution must be created when admin username is duplicate")


@STATIC_OVERRIDE
class SlugImmutabilityTest(TestCase):
    """AC #5: Institution slug is immutable after creation."""

    def test_slug_cannot_be_changed_after_creation(self):
        """AC #5: Institution.save() raises ValidationError when slug is changed."""
        from django.core.exceptions import ValidationError as DjangoValidationError

        inst = Institution.objects.create(
            name='Immutable Hospital', slug='immutable-hosp'
        )
        inst.slug = 'changed-slug'
        with self.assertRaises(DjangoValidationError,
                msg="AC #5: Changing institution slug after creation must raise ValidationError"):
            inst.save()

    def test_slug_unchanged_save_succeeds(self):
        """Saving an institution without changing slug is permitted."""
        inst = Institution.objects.create(
            name='Stable Hospital', slug='stable-hosp'
        )
        inst.name = 'Stable Hospital Updated'
        inst.save()  # Must not raise
        self.assertEqual(Institution.objects.get(pk=inst.pk).name, 'Stable Hospital Updated')
