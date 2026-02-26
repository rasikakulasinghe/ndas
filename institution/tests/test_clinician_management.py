"""
institution/tests/test_clinician_management.py
Tests for Clinician Account Management (Story 3.2 — FR57).
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

User = get_user_model()

STATIC_OVERRIDE = override_settings(
    MULTI_INSTITUTION_ENABLED=True,
    RATELIMIT_ENABLE=False,
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)


class ClinicianMgmtTestBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_clin', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771771001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(
            name='Test Hospital', slug='test-hospital',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Other Hospital', slug='other-hospital',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.admin = User.objects.create_user(
            username='admin_clin', password='Testpass1!',
            first_name='Test', last_name='Admin',
            position='Administrator', mobile_primary='0771771002',
            user_type=UserType.ADMIN, institution=self.inst,
        )
        self.existing_clinician = User.objects.create_user(
            username='clinician_01', password='Testpass1!',
            first_name='Existing', last_name='Clinician',
            position='Medical Officer', mobile_primary='0771771003',
            user_type=UserType.USER, institution=self.inst,
        )
        self.list_url = reverse('institution:institution-clinician-list')
        self.add_url = reverse('institution:institution-clinician-add')


@STATIC_OVERRIDE
class ClinicianListAccessTest(ClinicianMgmtTestBase):
    def test_admin_can_see_list(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_user_redirected_from_list(self):
        client = Client()
        client.force_login(self.existing_clinician)
        response = client.get(self.list_url)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_list_only_shows_own_institution_users(self):
        """AC #4: Users from other institutions must not appear in the list."""
        other_user = User.objects.create_user(
            username='other_clinic', password='Testpass1!',
            first_name='Other', last_name='User',
            position='Medical Officer', mobile_primary='0771771099',
            user_type=UserType.USER, institution=self.inst_b,
        )
        client = Client()
        client.force_login(self.admin)
        response = client.get(self.list_url)
        clinicians = response.context['clinicians']
        usernames = [u.username for u in clinicians]
        self.assertNotIn('other_clinic', usernames, "AC #4: Other institution user must not appear")
        self.assertIn('clinician_01', usernames)


@STATIC_OVERRIDE
class ClinicianCreateTest(ClinicianMgmtTestBase):
    def test_admin_can_create_user_type_clinician(self):
        """AC #1: Admin creates USER-type clinician bound to their institution."""
        client = Client()
        client.force_login(self.admin)
        response = client.post(self.add_url, {
            'first_name': 'New', 'last_name': 'Clinician',
            'username': 'new_clinician', 'email': 'new@test.com',
            'position': 'Medical Officer', 'mobile_primary': '0771551001',
            'password1': 'StrongPass1!', 'password2': 'StrongPass1!',
        })
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(username='new_clinician')
        self.assertEqual(new_user.user_type, UserType.USER, "AC #1: New clinician must be USER type")
        self.assertEqual(new_user.institution, self.inst, "AC #1: New clinician must be bound to admin's institution")
        self.assertTrue(new_user.is_active)

    def test_admin_cannot_create_admin_type_user(self):
        """AC #3: Attempt to set user_type=ADMIN in form data must be silently rejected."""
        client = Client()
        client.force_login(self.admin)
        client.post(self.add_url, {
            'first_name': 'Rogue', 'last_name': 'Admin',
            'username': 'rogue_admin', 'email': 'rogue@test.com',
            'position': 'Administrator', 'mobile_primary': '0771552001',
            'password1': 'StrongPass1!', 'password2': 'StrongPass1!',
            'user_type': 'ADMIN',  # Injected by attacker — must be ignored
        })
        if User.objects.filter(username='rogue_admin').exists():
            rogue = User.objects.get(username='rogue_admin')
            self.assertEqual(rogue.user_type, UserType.USER,
                "AC #3: user_type must be forced to USER regardless of POST data")

    def test_password_mismatch_rejected(self):
        client = Client()
        client.force_login(self.admin)
        response = client.post(self.add_url, {
            'first_name': 'Test', 'last_name': 'User',
            'username': 'mismatch_user', 'email': 'mm@test.com',
            'position': 'Medical Officer', 'mobile_primary': '0771553001',
            'password1': 'StrongPass1!', 'password2': 'WrongPass1!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='mismatch_user').exists())


@STATIC_OVERRIDE
class ClinicianDeactivateTest(ClinicianMgmtTestBase):
    def test_deactivate_clinician(self):
        """AC #2: Admin can deactivate a clinician account."""
        client = Client()
        client.force_login(self.admin)
        url = reverse('institution:institution-clinician-toggle-status', args=[self.existing_clinician.id])
        response = client.post(url)
        self.assertEqual(response.status_code, 302)
        self.existing_clinician.refresh_from_db()
        self.assertFalse(self.existing_clinician.is_active, "AC #2: Clinician must be deactivated")

    def test_reactivate_clinician(self):
        """Deactivated clinician can be reactivated."""
        self.existing_clinician.is_active = False
        self.existing_clinician.save()
        client = Client()
        client.force_login(self.admin)
        url = reverse('institution:institution-clinician-toggle-status', args=[self.existing_clinician.id])
        client.post(url)
        self.existing_clinician.refresh_from_db()
        self.assertTrue(self.existing_clinician.is_active)

    def test_records_remain_after_deactivation(self):
        """AC #2: Deactivating a clinician only sets is_active=False, record is not deleted."""
        client = Client()
        client.force_login(self.admin)
        url = reverse('institution:institution-clinician-toggle-status', args=[self.existing_clinician.id])
        client.post(url)
        # Clinician user record must still exist (not deleted)
        self.assertTrue(
            User.objects.filter(id=self.existing_clinician.id).exists(),
            "AC #2: Clinician user record must persist after deactivation"
        )
        self.existing_clinician.refresh_from_db()
        self.assertFalse(self.existing_clinician.is_active)

    def test_cannot_toggle_status_of_other_institution_user(self):
        """AC #4: Admin cannot deactivate users from another institution (Http404 → 302 redirect)."""
        other_user = User.objects.create_user(
            username='other_tgt', password='Testpass1!',
            first_name='Other', last_name='Target',
            position='Medical Officer', mobile_primary='0771771088',
            user_type=UserType.USER, institution=self.inst_b,
        )
        client = Client()
        client.force_login(self.admin)
        url = reverse('institution:institution-clinician-toggle-status', args=[other_user.id])
        response = client.post(url)
        # @handle_view_errors catches Http404 and redirects — status is 302
        self.assertEqual(response.status_code, 302)
        # Other institution user must remain unchanged
        other_user.refresh_from_db()
        self.assertTrue(other_user.is_active, "AC #4: Other institution user must not be deactivated")
