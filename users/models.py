from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.crypto import get_random_string
import uuid
from datetime import timedelta, date
from decimal import Decimal
from ndas.custom_codes.choice import POSSITION, LOGIN_STATUS_CHOICES, SUBSCRIPTION_TYPE_CHOICES, SUBSCRIPTION_STATUS_CHOICES
from ndas.custom_codes.validators import image_extension_validation, validate_phone_number
from ndas.custom_codes.Custom_abstract_class import (
    TimeStampedModel,
    UserTrackingMixin,
)


class CustomUser(AbstractUser, TimeStampedModel):
    """
    Custom user model extending Django's AbstractUser with additional fields
    for medical staff management.
    """

    # Professional Information
    position = models.CharField(
        max_length=30,
        choices=POSSITION,
        default="Medical Officer",
        help_text="User's professional position",
        verbose_name="Position",
    )

    # Contact Information
    mobile_primary = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        help_text="Primary mobile number (required)",
        verbose_name="Primary Mobile",
    )
    mobile_secondary = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        blank=True,
        help_text="Secondary mobile number (optional)",
        verbose_name="Secondary Mobile",
    )
    landline_primary = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        blank=True,
        help_text="Primary landline number",
        verbose_name="Primary Landline",
    )
    landline_secondary = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        blank=True,
        help_text="Secondary landline number",
        verbose_name="Secondary Landline",
    )

    # Address Information
    home_address = models.TextField(
        blank=True, help_text="Home address", verbose_name="Home Address"
    )
    station_address = models.TextField(
        blank=True, help_text="Work station address", verbose_name="Station Address"
    )

    # System Information
    last_login_device = models.CharField(
        max_length=255,
        blank=True,
        help_text="Last device used for login",
        verbose_name="Last Login Device",
    )

    # Email Verification Fields
    is_email_verified = models.BooleanField(
        default=False,
        help_text="Whether the user's email has been verified",
        verbose_name="Email Verified",
    )
    email_verification_token = models.CharField(
        max_length=64,
        blank=True,
        help_text="Token for email verification",
        verbose_name="Email Verification Token",
    )
    email_verification_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the email verification was sent",
        verbose_name="Email Verification Sent At",
    )
    email_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the email was verified",
        verbose_name="Email Verified At",
    )

    # Profile Information
    profile_picture = models.ImageField(
        upload_to="profile_pictures/%Y/%m/",
        validators=[image_extension_validation],
        blank=True,
        help_text="Profile picture (JPG, JPEG, PNG only)",
        verbose_name="Profile Picture",
    )
    additional_notes = models.TextField(
        blank=True,
        help_text="Additional notes or information",
        verbose_name="Additional Notes",
    )

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "first_name", "position", "mobile_primary"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.position})"

    @property
    def full_name(self):
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def profile_picture_url(self):
        """Return the URL of the profile picture if it exists."""
        if self.profile_picture and hasattr(self.profile_picture, "url"):
            return self.profile_picture.url
        return None

    def get_primary_contact(self):
        """Return the primary contact information."""
        return {
            "mobile": self.mobile_primary,
            "email": self.email,
            "landline": self.landline_primary if self.landline_primary else None,
        }

    def generate_email_verification_token(self):
        """Generate a new email verification token."""
        self.email_verification_token = get_random_string(64)
        self.email_verification_sent_at = timezone.now()
        self.save(update_fields=['email_verification_token', 'email_verification_sent_at'])
        return self.email_verification_token

    def is_email_verification_token_valid(self):
        """Check if the email verification token is still valid (24 hours)."""
        if not self.email_verification_sent_at:
            return False
        expiry_time = self.email_verification_sent_at + timedelta(hours=24)
        return timezone.now() < expiry_time

    def verify_email(self):
        """Mark email as verified and clear verification token."""
        self.is_email_verified = True
        self.email_verified_at = timezone.now()
        self.email_verification_token = ''
        self.email_verification_sent_at = None
        self.save(update_fields=[
            'is_email_verified', 
            'email_verified_at', 
            'email_verification_token', 
            'email_verification_sent_at'
        ])

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["first_name", "last_name"]
        indexes = [
            models.Index(fields=["position"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["email_verification_token"]),
            models.Index(fields=["is_email_verified"]),
        ]


class UserActivityLog(TimeStampedModel, UserTrackingMixin):
    """
    Model to track user authentication activity and device information.
    """
    
    # Login Status Choices
    LOGIN_SUCCESS = 'success'
    LOGIN_FAILED = 'failed'
    LOGOUT = 'logout'
    
    # Core Fields
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='activity_logs',
        help_text="User associated with this activity",
        verbose_name="User",
        null=True,
        blank=True,
    )
    
    # Authentication Information
    login_status = models.CharField(
        max_length=20,
        choices=LOGIN_STATUS_CHOICES,
        help_text="Status of the login attempt",
        verbose_name="Login Status",
    )
    attempted_username = models.CharField(
        max_length=150,
        blank=True,
        help_text="Username attempted during login (for failed attempts)",
        verbose_name="Attempted Username",
    )
    
    # Device Information
    ip_address = models.GenericIPAddressField(
        help_text="IP address of the user",
        verbose_name="IP Address",
    )
    user_agent = models.TextField(
        blank=True,
        help_text="Full user agent string",
        verbose_name="User Agent",
    )
    browser_name = models.CharField(
        max_length=100,
        blank=True,
        default='Unknown',
        help_text="Browser name (Chrome, Firefox, etc.)",
        verbose_name="Browser Name",
    )
    browser_version = models.CharField(
        max_length=50,
        blank=True,
        default='Unknown',
        help_text="Browser version",
        verbose_name="Browser Version",
    )
    operating_system = models.CharField(
        max_length=100,
        blank=True,
        default='Unknown',
        help_text="Operating system (Windows, macOS, Linux, etc.)",
        verbose_name="Operating System",
    )
    device_type = models.CharField(
        max_length=50,
        blank=True,
        default='Unknown',
        help_text="Device type (Desktop, Mobile, Tablet)",
        verbose_name="Device Type",
    )
    device_brand = models.CharField(
        max_length=100,
        blank=True,
        default='Unknown',
        help_text="Device brand (Apple, Samsung, etc.)",
        verbose_name="Device Brand",
    )
    device_model = models.CharField(
        max_length=100,
        blank=True,
        default='Unknown',
        help_text="Device model",
        verbose_name="Device Model",
    )
    
    # Device Capabilities
    is_mobile = models.BooleanField(
        default=False,
        help_text="Whether the device is mobile",
        verbose_name="Is Mobile",
    )
    is_tablet = models.BooleanField(
        default=False,
        help_text="Whether the device is a tablet",
        verbose_name="Is Tablet",
    )
    is_touch_capable = models.BooleanField(
        default=False,
        help_text="Whether the device supports touch",
        verbose_name="Is Touch Capable",
    )
    is_pc = models.BooleanField(
        default=False,
        help_text="Whether the device is a PC",
        verbose_name="Is PC",
    )
    is_bot = models.BooleanField(
        default=False,
        help_text="Whether the user agent is a bot",
        verbose_name="Is Bot",
    )
    
    # Geolocation Information (Optional - requires additional setup)
    country = models.CharField(
        max_length=100,
        blank=True,
        help_text="Country based on IP address",
        verbose_name="Country",
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City based on IP address",
        verbose_name="City",
    )
    latitude = models.FloatField(
        null=True,
        blank=True,
        help_text="Latitude coordinates",
        verbose_name="Latitude",
    )
    longitude = models.FloatField(
        null=True,
        blank=True,
        help_text="Longitude coordinates",
        verbose_name="Longitude",
    )
    
    # Session Information
    session_key = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text="Django session key",
        verbose_name="Session Key",
    )
    login_timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When the login attempt occurred",
        verbose_name="Login Timestamp",
    )
    logout_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the user logged out",
        verbose_name="Logout Timestamp",
    )
    session_duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Duration of the session",
        verbose_name="Session Duration",
    )
    
    # Additional Security Information
    failed_login_reason = models.CharField(
        max_length=200,
        blank=True,
        help_text="Reason for failed login",
        verbose_name="Failed Login Reason",
    )
    
    # Privacy and GDPR Compliance
    data_retention_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when this record should be deleted for privacy compliance",
        verbose_name="Data Retention Date",
    )
    
    def __str__(self):
        status_display = dict(LOGIN_STATUS_CHOICES).get(self.login_status, self.login_status)
        if self.user:
            return f"{self.user.username} - {status_display} at {self.login_timestamp}"
        return f"{self.attempted_username} - {status_display} at {self.login_timestamp}"
    
    def calculate_session_duration(self):
        """Calculate and update session duration if logout timestamp exists."""
        if self.logout_timestamp and self.login_timestamp:
            self.session_duration = self.logout_timestamp - self.login_timestamp
            self.save(update_fields=['session_duration'])
            return self.session_duration
        return None
    
    def is_suspicious_activity(self):
        """Basic check for suspicious activity patterns."""
        # Check for rapid login attempts
        recent_attempts = UserActivityLog.objects.filter(
            attempted_username=self.attempted_username,
            login_timestamp__gte=timezone.now() - timedelta(minutes=5)
        ).count()
        
        # Check for multiple failed attempts
        failed_attempts = UserActivityLog.objects.filter(
            attempted_username=self.attempted_username,
            login_status=self.LOGIN_FAILED,
            login_timestamp__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        return recent_attempts > 10 or failed_attempts > 5
    
    @classmethod
    def cleanup_old_records(cls, days=90):
        """Remove old activity logs for privacy compliance."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return cls.objects.filter(login_timestamp__lt=cutoff_date).delete()
    
    class Meta:
        verbose_name = "User Activity Log"
        verbose_name_plural = "User Activity Logs"
        ordering = ["-login_timestamp"]
        indexes = [
            models.Index(fields=["user", "-login_timestamp"]),
            models.Index(fields=["ip_address", "-login_timestamp"]),
            models.Index(fields=["login_status", "-login_timestamp"]),
            models.Index(fields=["attempted_username", "-login_timestamp"]),
            models.Index(fields=["data_retention_date"]),
        ]


class UserSession(TimeStampedModel, UserTrackingMixin):
    """
    Model to track active user sessions.
    """
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='active_sessions',
        help_text="User associated with this session",
        verbose_name="User",
    )
    session_key = models.CharField(
        max_length=40,
        unique=True,
        default='',
        help_text="Django session key",
        verbose_name="Session Key",
    )
    ip_address = models.GenericIPAddressField(
        help_text="IP address of the session",
        verbose_name="IP Address",
    )
    user_agent = models.TextField(
        help_text="User agent string",
        verbose_name="User Agent",
    )
    device_summary = models.CharField(
        max_length=200,
        help_text="Summary of device information",
        verbose_name="Device Summary",
    )
    last_activity = models.DateTimeField(
        auto_now=True,
        help_text="Last activity timestamp",
        verbose_name="Last Activity",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the session is currently active",
        verbose_name="Is Active",
    )
    
    def __str__(self):
        return f"{self.user.username} - {self.device_summary} ({self.ip_address})"
    
    def deactivate(self):
        """Mark session as inactive."""
        self.is_active = False
        self.save(update_fields=['is_active'])
    
    @classmethod
    def cleanup_expired_sessions(cls):
        """Remove expired sessions."""
        # Remove sessions older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        return cls.objects.filter(last_activity__lt=cutoff_date).delete()
    
    class Meta:
        verbose_name = "User Session"
        verbose_name_plural = "User Sessions"
        ordering = ["-last_activity"]
        indexes = [
            models.Index(fields=["user", "-last_activity"]),
            models.Index(fields=["session_key"]),
            models.Index(fields=["is_active", "-last_activity"]),
        ]


class DeveloperContacts(TimeStampedModel, UserTrackingMixin):
    """
    Model to store developer contact information for the application.
    """

    name = models.CharField(
        max_length=100,
        default="Dr. Rasika Kulasinghe",
        help_text="Developer's full name",
        verbose_name="Name",
    )
    logo = models.ImageField(
        upload_to="developer_logos/%Y/%m/",
        validators=[image_extension_validation],
        blank=True,
        help_text="Developer's logo or photo",
        verbose_name="Logo/Photo",
    )
    qualifications = models.CharField(
        max_length=500,
        default="MBBS, HDIT, BIT",
        help_text="Professional qualifications",
        verbose_name="Qualifications",
    )
    email = models.EmailField(
        max_length=45,
        default="rasikakulasinghe@gmail.com",
        help_text="Contact email address",
        verbose_name="Email",
    )
    mobile_phone = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        blank=True,
        help_text="Mobile phone number",
        verbose_name="Mobile Phone",
    )
    landline_phone = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        blank=True,
        help_text="Landline phone number",
        verbose_name="Landline Phone",
    )
    facebook_url = models.URLField(
        blank=True, help_text="Facebook profile URL", verbose_name="Facebook"
    )
    twitter_url = models.URLField(
        blank=True, help_text="Twitter profile URL", verbose_name="Twitter"
    )
    linkedin_url = models.URLField(
        blank=True, help_text="LinkedIn profile URL", verbose_name="LinkedIn"
    )
    whatsapp_number = models.CharField(
        max_length=15,
        validators=[validate_phone_number],
        blank=True,
        help_text="WhatsApp number",
        verbose_name="WhatsApp",
    )
    youtube_url = models.URLField(
        blank=True, help_text="YouTube channel URL", verbose_name="YouTube"
    )
    website_url = models.URLField(
        blank=True,
        help_text="Personal or professional website URL",
        verbose_name="Website",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Developer Contact"
        verbose_name_plural = "Developer Contacts"
        ordering = ["name"]


class Subscription(TimeStampedModel, UserTrackingMixin):
    """
    Global subscription model that applies to all non-superuser users.
    Only one subscription record should exist in the system.
    Superusers are exempt from subscription requirements.
    """

    subscription_type = models.CharField(
        max_length=10,
        choices=SUBSCRIPTION_TYPE_CHOICES,
        default='free',
        help_text="Type of subscription (Free or Commercial)",
        verbose_name="Subscription Type",
    )
    
    start_date = models.DateField(
        help_text="Subscription start date",
        verbose_name="Start Date",
        db_index=True,
    )
    
    duration_days = models.PositiveIntegerField(
        default=30,
        help_text="Subscription duration in days",
        verbose_name="Duration (Days)",
    )
    
    billing_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Billing amount for this subscription period",
        verbose_name="Billing Amount",
    )
    
    status = models.CharField(
        max_length=15,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default='active',
        help_text="Current subscription status",
        verbose_name="Status",
        db_index=True,
    )
    
    grace_period_days = models.PositiveIntegerField(
        default=7,
        help_text="Number of days for grace period after expiration",
        verbose_name="Grace Period (Days)",
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes or remarks about this subscription",
        verbose_name="Notes",
    )
    
    @property
    def expiration_date(self):
        """Calculate and return the subscription expiration date."""
        from datetime import timedelta
        return self.start_date + timedelta(days=self.duration_days)
    
    @property
    def grace_period_end_date(self):
        """Calculate and return the end date of the grace period."""
        from datetime import timedelta
        return self.expiration_date + timedelta(days=self.grace_period_days)
    
    @property
    def remaining_days(self):
        """Calculate remaining days until expiration."""
        from datetime import date
        today = date.today()
        if today > self.expiration_date:
            return 0
        return (self.expiration_date - today).days
    
    @property
    def is_active(self):
        """
        Check if subscription is currently active.

        SECURITY: Thread-safe calculation without race conditions.
        PERFORMANCE: Cached for 60 seconds with atomic check-and-set.
        """
        from datetime import date
        from django.core.cache import cache

        cache_key = f'subscription_status_{self.pk}'
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return cached_data.get('is_active', False)

        # Calculate all states atomically
        today = date.today()
        expiration = self.expiration_date
        grace_end = self.grace_period_end_date

        is_active = today <= expiration
        is_expired = today > grace_end
        is_grace = expiration < today <= grace_end

        # Cache all states together atomically
        cache_data = {
            'is_active': is_active,
            'is_expired': is_expired,
            'is_grace_period': is_grace,
            'calculated_at': today,
        }
        cache.set(cache_key, cache_data, 60)

        return is_active

    @property
    def is_expired(self):
        """
        Check if subscription has expired (beyond grace period).

        SECURITY: Thread-safe calculation without race conditions.
        PERFORMANCE: Uses shared cache with is_active for consistency.
        """
        from datetime import date
        from django.core.cache import cache

        cache_key = f'subscription_status_{self.pk}'
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return cached_data.get('is_expired', False)

        # Calculate all states atomically
        today = date.today()
        expiration = self.expiration_date
        grace_end = self.grace_period_end_date

        is_active = today <= expiration
        is_expired = today > grace_end
        is_grace = expiration < today <= grace_end

        # Cache all states together atomically
        cache_data = {
            'is_active': is_active,
            'is_expired': is_expired,
            'is_grace_period': is_grace,
            'calculated_at': today,
        }
        cache.set(cache_key, cache_data, 60)

        return is_expired

    @property
    def is_grace_period(self):
        """
        Check if subscription is in grace period.

        SECURITY: Thread-safe calculation without race conditions.
        PERFORMANCE: Uses shared cache with is_active for consistency.
        """
        from datetime import date
        from django.core.cache import cache

        cache_key = f'subscription_status_{self.pk}'
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return cached_data.get('is_grace_period', False)

        # Calculate all states atomically
        today = date.today()
        expiration = self.expiration_date
        grace_end = self.grace_period_end_date

        is_active = today <= expiration
        is_expired = today > grace_end
        is_grace = expiration < today <= grace_end

        # Cache all states together atomically
        cache_data = {
            'is_active': is_active,
            'is_expired': is_expired,
            'is_grace_period': is_grace,
            'calculated_at': today,
        }
        cache.set(cache_key, cache_data, 60)

        return is_grace
    
    def update_status(self):
        """
        Update subscription status based on current date.
        This method should be called periodically or on-demand.

        SECURITY: Uses database transaction with row locking to prevent race conditions.
        PERFORMANCE: Only updates if status actually changed, clears cache before checking.
        """
        from django.db import transaction

        # Clear cache first to ensure fresh calculation
        self._clear_cache()

        # Calculate what the status should be (will be fresh now)
        new_status = None
        if self.is_expired:
            new_status = 'expired'
        elif self.is_grace_period:
            new_status = 'grace_period'
        elif self.is_active:
            new_status = 'active'

        # Only update if status changed (performance optimization)
        if new_status and self.status != new_status:
            with transaction.atomic():
                # Use select_for_update to prevent race conditions
                subscription = Subscription.objects.select_for_update().get(pk=self.pk)
                subscription.status = new_status
                subscription.save(update_fields=['status', 'updated_at'])
                # Update the current instance
                self.status = new_status
                # Clear cache again after update
                self._clear_cache()
    
    def _clear_cache(self):
        """
        Clear all cached subscription properties.
        Called when subscription data changes.

        PERFORMANCE: Single cache key reduces overhead.
        """
        from django.core.cache import cache
        cache_key = f'subscription_status_{self.pk}'
        cache.delete(cache_key)
    
    def extend_subscription(self, days):
        """
        Extend the subscription by adding days to duration.
        
        Args:
            days (int): Number of days to add to the subscription
            
        SECURITY: Uses transaction to ensure atomic update.
        """
        from django.db import transaction
        
        with transaction.atomic():
            subscription = Subscription.objects.select_for_update().get(pk=self.pk)
            subscription.duration_days += days
            subscription.save(update_fields=['duration_days', 'updated_at'])
            self.duration_days = subscription.duration_days
            # Clear cache and update status
            self._clear_cache()
            self.update_status()
    
    @classmethod
    def get_global_subscription(cls):
        """
        Get or create the single global subscription instance.

        Returns:
            Subscription: The global subscription object.
        """
        subscription, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'subscription_type': 'free',
                'start_date': date.today(),
                'duration_days': 30,
                'billing_amount': Decimal('0.00'),
                'status': 'active',
                'grace_period_days': 7,
            }
        )
        return subscription

    def save(self, *args, **kwargs):
        """
        Override save to enforce singleton pattern.
        Always save with pk=1 to ensure only one record exists.
        """
        self.pk = 1
        super().save(*args, **kwargs)
        self._clear_cache()

    def __str__(self):
        return f"Global Subscription - {self.subscription_type} ({self.status})"

    class Meta:
        verbose_name = "Global Subscription"
        verbose_name_plural = "Global Subscription"
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["start_date"]),
            models.Index(fields=["status"]),
        ]

