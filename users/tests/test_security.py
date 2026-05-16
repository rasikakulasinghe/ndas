"""
Security tests for users app.

Covers: AC 3-7 (Fix #3 cross-institution user views, Fix #4 activity log scoping).
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from institution.models import Institution
from users.models import UserActivityLog

User = get_user_model()

STATIC_OVERRIDE = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
    MULTI_INSTITUTION_ENABLED=True,
    RATELIMIT_ENABLE=False,
)


class UserSecurityBase(TestCase):
    """Shared setup for user security tests."""

    def setUp(self):
        self.client = Client()
        self.inst_a = Institution.objects.create(name='Inst Alpha', slug='inst-alpha')
        self.inst_b = Institution.objects.create(name='Inst Beta', slug='inst-beta')

        self.superuser = User.objects.create_superuser(
            username='super', password='SuperPass123!', email='super@test.com',
            mobile_primary='0700000001',
        )
        self.staff_a = User.objects.create_user(
            username='staff_a', password='StaffPass123!', email='staff_a@test.com',
            is_staff=True, institution=self.inst_a, mobile_primary='0700000002',
        )
        self.staff_b = User.objects.create_user(
            username='staff_b', password='StaffPass123!', email='staff_b@test.com',
            is_staff=True, institution=self.inst_b, mobile_primary='0700000003',
        )
        self.staff_a2 = User.objects.create_user(
            username='staff_a2', password='StaffPass123!', email='staff_a2@test.com',
            is_staff=True, institution=self.inst_a, mobile_primary='0700000004',
        )


@STATIC_OVERRIDE
class UserViewByUsernameSecurityTest(UserSecurityBase):
    """AC 3-5: Institution scoping on userViewByUsername."""

    def test_cross_institution_user_returns_404(self):
        """AC 3: Staff from inst_a cannot view a user from inst_b."""
        self.client.force_login(self.staff_a)
        url = reverse('user-view-by-username', kwargs={'username': self.staff_b.username})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_same_institution_user_returns_200(self):
        """AC 4: Staff from inst_a can view another user from inst_a."""
        self.client.force_login(self.staff_a)
        url = reverse('user-view-by-username', kwargs={'username': self.staff_a2.username})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_view_any_user(self):
        """AC 5: Superuser bypasses institution scoping."""
        self.client.force_login(self.superuser)
        url = reverse('user-view-by-username', kwargs={'username': self.staff_b.username})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


@STATIC_OVERRIDE
class UserViewByPKSecurityTest(UserSecurityBase):
    """Institution scoping on userView (PK version)."""

    def test_cross_institution_user_by_pk_returns_404(self):
        """Staff from inst_a cannot view a user from inst_b by PK."""
        self.client.force_login(self.staff_a)
        url = reverse('user-view', kwargs={'pk': self.staff_b.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_same_institution_user_by_pk_returns_200(self):
        """Staff from inst_a can view a user from inst_a by PK."""
        self.client.force_login(self.staff_a)
        url = reverse('user-view', kwargs={'pk': self.staff_a2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


@STATIC_OVERRIDE
class AdminActivityLogScopingTest(UserSecurityBase):
    """AC 6-7: Institution scoping on admin_activity_logs."""

    def setUp(self):
        super().setUp()
        # Create activity logs for both institutions
        UserActivityLog.objects.create(
            user=self.staff_a,
            login_timestamp=timezone.now(),
            login_status='success',
            ip_address='127.0.0.1',
        )
        UserActivityLog.objects.create(
            user=self.staff_b,
            login_timestamp=timezone.now(),
            login_status='success',
            ip_address='127.0.0.2',
        )

    def test_staff_sees_only_own_institution_logs(self):
        """AC 6: Staff from inst_a sees only inst_a activity logs."""
        self.client.force_login(self.staff_a)
        url = reverse('admin-activity-logs')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check that inst_b user does not appear in activity logs
        page_obj = response.context['page_obj']
        user_ids_in_logs = {log.user_id for log in page_obj.object_list}
        self.assertIn(self.staff_a.pk, user_ids_in_logs)
        self.assertNotIn(self.staff_b.pk, user_ids_in_logs)

    def test_superuser_sees_all_institution_logs(self):
        """AC 7: Superuser sees activity logs from all institutions."""
        self.client.force_login(self.superuser)
        url = reverse('admin-activity-logs')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        page_obj = response.context['page_obj']
        user_ids_in_logs = {log.user_id for log in page_obj.object_list}
        self.assertIn(self.staff_a.pk, user_ids_in_logs)
        self.assertIn(self.staff_b.pk, user_ids_in_logs)
