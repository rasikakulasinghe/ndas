from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.crypto import get_random_string
import uuid
from datetime import timedelta
from ndas.custom_codes.choice import POSSITION, LOGIN_STATUS_CHOICES
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
