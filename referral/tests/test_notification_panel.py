"""
referral/tests/test_notification_panel.py
Tests for notification panel and mark-as-read views (Story 5.3 — FR38, FR70).
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, NotificationType
from referral.models import Notification

User = get_user_model()

# Use StaticFilesStorage to avoid ManifestStaticFilesStorage errors in tests that
# trigger 404/500 error pages (which use the base template with static tags).
STATIC_OVERRIDE = override_settings(
    MULTI_INSTITUTION_ENABLED=True,
    RATELIMIT_ENABLE=False,
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)


class NotificationPanelBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_np', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771000030',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(
            name='Panel Inst', slug='panel-inst',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.user = User.objects.create_user(
            username='panel_user', password='Testpass1!',
            first_name='Panel', last_name='User',
            position='Medical Officer', mobile_primary='0771000031',
            user_type=UserType.USER, institution=self.inst,
        )
        self.other_user = User.objects.create_user(
            username='other_user_np', password='Testpass1!',
            first_name='Other', last_name='User',
            position='Consultant', mobile_primary='0771000032',
            user_type=UserType.USER, institution=self.inst,
        )

    def _make_notification(self, user=None, is_read=False, title='Test Notification'):
        user = user or self.user
        return Notification.objects.create(
            recipient=user,
            notification_type=NotificationType.REFERRAL_RECEIVED,
            title=title,
            body='Test notification body.',
            link='/referral/inbox/',
            is_read=is_read,
            institution=self.inst,
            added_by=user,
            last_edit_by=user,
        )


@STATIC_OVERRIDE
class NotificationPanelViewTest(NotificationPanelBase):
    def test_panel_returns_200(self):
        """AC #1: notification-panel endpoint returns 200."""
        self._make_notification()
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('referral:notification-panel'))
        self.assertEqual(response.status_code, 200)

    def test_panel_shows_notification_title(self):
        """AC #1: Panel renders notification title."""
        self._make_notification(title='Referral Notification Title')
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('referral:notification-panel'))
        self.assertContains(response, 'Referral Notification Title')

    def test_panel_excludes_other_users_notifications(self):
        """AC #5: Only own notifications are returned."""
        self._make_notification(user=self.other_user, title='Other User Notification')
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('referral:notification-panel'))
        self.assertNotContains(response, 'Other User Notification',
            msg_prefix='AC #5: Other user notifications must not appear in panel')

    def test_panel_shows_empty_state_when_no_notifications(self):
        """AC #1: Panel renders empty state when no notifications."""
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('referral:notification-panel'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No notifications')


@STATIC_OVERRIDE
class NotificationMarkReadTest(NotificationPanelBase):
    def test_mark_read_sets_is_read_true(self):
        """AC #3: Clicking notification marks it as read."""
        notif = self._make_notification(is_read=False)
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('referral:notification-mark-read', args=[notif.pk]))
        # Should redirect to notification's link
        self.assertEqual(response.status_code, 302)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read, 'AC #3: Notification must be marked as read after clicking')

    def test_mark_read_prevents_cross_user_access(self):
        """AC #5: Cannot mark another user's notification as read."""
        other_notif = self._make_notification(user=self.other_user)
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('referral:notification-mark-read', args=[other_notif.pk]))
        self.assertEqual(response.status_code, 404,
            'AC #5: Cross-user notification access must return 404')

    def test_mark_read_redirects_to_notification_link(self):
        """AC #3: After marking read, redirects to notification's link."""
        notif = self._make_notification()
        notif.link = '/referral/inbox/'
        notif.save()
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('referral:notification-mark-read', args=[notif.pk]))
        self.assertRedirects(response, '/referral/inbox/', fetch_redirect_response=False)


@STATIC_OVERRIDE
class NotificationMarkAllReadTest(NotificationPanelBase):
    def test_mark_all_read_sets_all_is_read_true(self):
        """AC #4: Mark all read sets is_read=True on all user's unread notifications."""
        self._make_notification(is_read=False, title='Notif 1')
        self._make_notification(is_read=False, title='Notif 2')
        self._make_notification(is_read=True, title='Already Read')

        client = Client()
        client.force_login(self.user)
        response = client.post(reverse('referral:notification-mark-all-read'))
        self.assertEqual(response.status_code, 200)

        unread_count = Notification.objects.filter(
            recipient=self.user, institution=self.inst, is_read=False,
        ).count()
        self.assertEqual(unread_count, 0,
            'AC #4: All notifications must be marked as read after mark-all-read')

    def test_mark_all_read_does_not_affect_other_users(self):
        """AC #5: Mark-all-read only affects own notifications."""
        other_notif = self._make_notification(user=self.other_user, is_read=False)

        client = Client()
        client.force_login(self.user)
        client.post(reverse('referral:notification-mark-all-read'))

        other_notif.refresh_from_db()
        self.assertFalse(other_notif.is_read,
            'AC #5: Other users notifications must not be affected by mark-all-read')
