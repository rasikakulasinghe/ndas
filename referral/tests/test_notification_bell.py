"""
referral/tests/test_notification_bell.py
Tests for notification bell endpoint and HTMX count view (Story 5.2 — FR38, NFR23).
"""
import uuid
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus, NotificationType
from referral.models import Notification

User = get_user_model()


class NotificationBellBase(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_bell', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771000020',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst = Institution.objects.create(
            name='Bell Inst', slug='bell-inst',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.user = User.objects.create_user(
            username='bell_user', password='Testpass1!',
            first_name='Bell', last_name='User',
            position='Medical Officer', mobile_primary='0771000021',
            user_type=UserType.USER, institution=self.inst,
        )


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class NotificationCountViewTest(NotificationBellBase):
    def test_count_returns_200_for_authenticated_user(self):
        """AC #4: notification-count endpoint returns 200."""
        client = Client()
        client.force_login(self.user)
        url = reverse('referral:notification-count')
        response = client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_count_zero_returns_empty_fragment(self):
        """AC #5: Zero unread notifications returns empty (no badge element)."""
        client = Client()
        client.force_login(self.user)
        url = reverse('referral:notification-count')
        response = client.get(url)
        self.assertNotIn(b'badge', response.content,
            'AC #5: Zero count must not render a badge')

    def test_count_returns_badge_when_unread_notifications_exist(self):
        """AC #1: Badge rendered when unread notifications exist."""
        Notification.objects.create(
            recipient=self.user,
            notification_type=NotificationType.REFERRAL_RECEIVED,
            title='Test notification',
            body='Test body',
            link='/referral/thread/test/',
            is_read=False,
            institution=self.inst,
            added_by=self.user,
            last_edit_by=self.user,
        )
        client = Client()
        client.force_login(self.user)
        url = reverse('referral:notification-count')
        response = client.get(url)
        self.assertIn(b'1', response.content,
            'AC #1: Count badge must show 1 unread notification')

    def test_count_excludes_read_notifications(self):
        """AC #4: Read notifications are not counted."""
        Notification.objects.create(
            recipient=self.user,
            notification_type=NotificationType.REFERRAL_RECEIVED,
            title='Read notification',
            is_read=True,  # Already read
            institution=self.inst,
            added_by=self.user,
            last_edit_by=self.user,
        )
        client = Client()
        client.force_login(self.user)
        url = reverse('referral:notification-count')
        response = client.get(url)
        self.assertNotIn(b'badge', response.content,
            'AC #4: Read notifications must not appear in unread count')

    def test_count_requires_authentication(self):
        """AC #1: Unauthenticated request redirects to login."""
        client = Client()
        url = reverse('referral:notification-count')
        response = client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response['Location'])
