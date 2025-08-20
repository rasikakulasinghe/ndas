"""
Tests for email verification and user activity tracking functionality.
"""

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from users.models import UserActivityLog, UserSession
from users.utils import send_email_verification

User = get_user_model()


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class EmailVerificationTestCase(TestCase):
    """Test email verification functionality."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            position='Medical Officer',
            mobile_primary='+1234567890'
        )
    
    def test_user_created_with_unverified_email(self):
        """Test that new users have unverified email status."""
        self.assertFalse(self.user.is_email_verified)
        self.assertIsNone(self.user.email_verified_at)
        self.assertEqual(self.user.email_verification_token, '')
    
    def test_generate_verification_token(self):
        """Test generating email verification token."""
        token = self.user.generate_email_verification_token()
        
        self.assertIsNotNone(token)
        self.assertEqual(len(token), 64)
        self.assertEqual(self.user.email_verification_token, token)
        self.assertIsNotNone(self.user.email_verification_sent_at)
    
    def test_token_validation(self):
        """Test email verification token validation."""
        # Fresh token should be valid
        self.user.generate_email_verification_token()
        self.assertTrue(self.user.is_email_verification_token_valid())
        
        # Expired token should be invalid
        self.user.email_verification_sent_at = timezone.now() - timedelta(hours=25)
        self.user.save()
        self.assertFalse(self.user.is_email_verification_token_valid())
    
    def test_email_verification(self):
        """Test email verification process."""
        token = self.user.generate_email_verification_token()
        
        # Verify email
        self.user.verify_email()
        
        self.assertTrue(self.user.is_email_verified)
        self.assertIsNotNone(self.user.email_verified_at)
        self.assertEqual(self.user.email_verification_token, '')
        self.assertIsNone(self.user.email_verification_sent_at)
    
    def test_verify_email_view_valid_token(self):
        """Test email verification view with valid token."""
        token = self.user.generate_email_verification_token()
        
        response = self.client.get(reverse('verify-email', args=[token]))
        
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # Reload user from database
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)
    
    def test_verify_email_view_invalid_token(self):
        """Test email verification view with invalid token."""
        response = self.client.get(reverse('verify-email', args=['invalid-token']))
        
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # User should still be unverified
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class UserActivityTrackingTestCase(TestCase):
    """Test user activity tracking functionality."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            position='Medical Officer',
            mobile_primary='+1234567890'
        )
        # Mark email as verified to allow login
        self.user.is_email_verified = True
        self.user.save()
    
    def test_login_creates_activity_log(self):
        """Test that successful login creates an activity log entry."""
        # Count existing logs
        initial_count = UserActivityLog.objects.count()
        
        # Login
        response = self.client.post(reverse('user-login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Check that activity log was created
        self.assertEqual(UserActivityLog.objects.count(), initial_count + 1)
        
        # Check the log entry
        log_entry = UserActivityLog.objects.latest('login_timestamp')
        self.assertEqual(log_entry.user, self.user)
        self.assertEqual(log_entry.login_status, UserActivityLog.LOGIN_SUCCESS)
        self.assertIsNotNone(log_entry.ip_address)
    
    def test_failed_login_creates_activity_log(self):
        """Test that failed login creates an activity log entry."""
        initial_count = UserActivityLog.objects.count()
        
        # Attempt login with wrong password
        response = self.client.post(reverse('user-login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        
        # Check that activity log was created
        self.assertEqual(UserActivityLog.objects.count(), initial_count + 1)
        
        # Check the log entry
        log_entry = UserActivityLog.objects.latest('login_timestamp')
        self.assertEqual(log_entry.login_status, UserActivityLog.LOGIN_FAILED)
        self.assertEqual(log_entry.attempted_username, 'testuser')
    
    def test_login_creates_user_session(self):
        """Test that successful login creates a user session."""
        initial_count = UserSession.objects.count()
        
        # Login
        self.client.post(reverse('user-login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Check that session was created
        self.assertEqual(UserSession.objects.count(), initial_count + 1)
        
        # Check the session entry
        session = UserSession.objects.latest('created_at')
        self.assertEqual(session.user, self.user)
        self.assertTrue(session.is_active)
    
    def test_logout_updates_activity_log(self):
        """Test that logout updates the activity log with session duration."""
        # Login first
        self.client.post(reverse('user-login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Get the login activity log
        login_log = UserActivityLog.objects.filter(
            user=self.user,
            login_status=UserActivityLog.LOGIN_SUCCESS
        ).latest('login_timestamp')
        
        # Logout
        self.client.post(reverse('user-logout'))
        
        # Check that logout activity was logged
        logout_logs = UserActivityLog.objects.filter(
            user=self.user,
            login_status=UserActivityLog.LOGOUT
        )
        self.assertTrue(logout_logs.exists())
        
        # Check that the login log was updated with logout timestamp
        login_log.refresh_from_db()
        self.assertIsNotNone(login_log.logout_timestamp)
        self.assertIsNotNone(login_log.session_duration)
    
    def test_unverified_email_prevents_login(self):
        """Test that unverified email prevents login."""
        # Set user email as unverified
        self.user.is_email_verified = False
        self.user.save()
        
        response = self.client.post(reverse('user-login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Should remain on login page with warning message
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'verify your email')
    
    def test_suspicious_activity_detection(self):
        """Test detection of suspicious activity patterns."""
        # Create multiple failed login attempts
        for i in range(6):
            UserActivityLog.objects.create(
                attempted_username='testuser',
                login_status=UserActivityLog.LOGIN_FAILED,
                ip_address='192.168.1.1',
                user_agent='Test Browser',
                browser_name='Chrome',
                operating_system='Windows',
                device_type='Desktop',
                login_timestamp=timezone.now() - timedelta(minutes=i),
                data_retention_date=timezone.now() + timedelta(days=90)
            )
        
        # Latest log should detect suspicious activity
        latest_log = UserActivityLog.objects.latest('login_timestamp')
        self.assertTrue(latest_log.is_suspicious_activity())


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class UserActivityCleanupTestCase(TestCase):
    """Test cleanup functionality for old user data."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            position='Medical Officer',
            mobile_primary='+1234567890'
        )
    
    def test_cleanup_old_activity_logs(self):
        """Test cleanup of old activity logs."""
        # Create old activity log
        old_log = UserActivityLog.objects.create(
            user=self.user,
            login_status=UserActivityLog.LOGIN_SUCCESS,
            ip_address='192.168.1.1',
            user_agent='Test Browser',
            browser_name='Chrome',
            operating_system='Windows',
            device_type='Desktop',
            login_timestamp=timezone.now() - timedelta(days=100),
            data_retention_date=timezone.now() + timedelta(days=90)
        )
        
        # Create recent activity log
        recent_log = UserActivityLog.objects.create(
            user=self.user,
            login_status=UserActivityLog.LOGIN_SUCCESS,
            ip_address='192.168.1.1',
            user_agent='Test Browser',
            browser_name='Chrome',
            operating_system='Windows',
            device_type='Desktop',
            login_timestamp=timezone.now() - timedelta(days=30),
            data_retention_date=timezone.now() + timedelta(days=90)
        )
        
        # Run cleanup
        deleted_count = UserActivityLog.cleanup_old_records(days=90)
        
        # Check that old log was deleted but recent one remains
        self.assertFalse(UserActivityLog.objects.filter(pk=old_log.pk).exists())
        self.assertTrue(UserActivityLog.objects.filter(pk=recent_log.pk).exists())
    
    def test_cleanup_expired_sessions(self):
        """Test cleanup of expired sessions."""
        # Create old session
        old_session = UserSession.objects.create(
            user=self.user,
            session_key='old-session-key',
            ip_address='192.168.1.1',
            user_agent='Test Browser',
            device_summary='Chrome on Windows',
            last_activity=timezone.now() - timedelta(days=40)
        )
        
        # Create recent session
        recent_session = UserSession.objects.create(
            user=self.user,
            session_key='recent-session-key',
            ip_address='192.168.1.1',
            user_agent='Test Browser',
            device_summary='Chrome on Windows',
            last_activity=timezone.now() - timedelta(days=10)
        )
        
        # Run cleanup
        deleted_count = UserSession.cleanup_expired_sessions()
        
        # Check that old session was deleted but recent one remains
        self.assertFalse(UserSession.objects.filter(pk=old_session.pk).exists())
        self.assertTrue(UserSession.objects.filter(pk=recent_session.pk).exists())
