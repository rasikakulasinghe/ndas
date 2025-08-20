from pathlib import Path
import os
from django.contrib.messages import constants as messages
import environ




env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False)
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Take environment variables from .env file
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# ==============================================================================
# SECURITY CONFIGURATION
# ==============================================================================
# Security headers and related configurations have been added at the end of this file
# Search for "Security Headers Configuration" for HTTPS and security settings

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_cleanup.apps.CleanupConfig',
    
    # Security apps
    'csp',  # Content Security Policy
    'django_permissions_policy',  # Permissions Policy
    
    'django_user_agents',
    'users.apps.UsersConfig',
    'patients.apps.PatientsConfig',
    'ckeditor',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add WhiteNoise after SecurityMiddleware
    'csp.middleware.CSPMiddleware',  # Content Security Policy middleware
    # 'django_permissions_policy.PermissionsPolicyMiddleware',  # Temporarily disabled - will fix later
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'users.middleware.UserActivityMiddleware',  # User activity tracking
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_user_agents.middleware.UserAgentMiddleware',
]

ROOT_URLCONF = 'ndas.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',           # Proper Django templates directory
            BASE_DIR / 'static/templates',    # Legacy directory for backwards compatibility
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ndas.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

# TIME_ZONE = 'UTC'
TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = env('STATIC_URL')
MEDIA_URL = env('MEDIA_URL')
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
# STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# LOGIN_URL = 'user-login'
# LOGIN_REDIRECT_URL = "home"
# LOGOUT_REDIRECT_URL = "user-login"

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static')
]

# WhiteNoise configuration for serving static files
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = "users.CustomUser"

#SMTP Configuration
# SMTP Configuration (use environment variables for production)
# Email Configuration
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # For development
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'  # For production
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = ''  # Set this in .env file
EMAIL_HOST_PASSWORD = ''  # Set this in .env file
DEFAULT_FROM_EMAIL = 'noreply@ndas-system.com'

# Email verification settings
EMAIL_VERIFICATION_REQUIRED = True
EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS = 24

# email local settings
EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = str(BASE_DIR.joinpath('sent_emails'))

MESSAGE_TAGS = {
        messages.DEBUG: 'alert-secondary',
        messages.INFO: 'alert-info',
        messages.SUCCESS: 'alert-success',
        messages.WARNING: 'alert-warning',
        messages.ERROR: 'alert-danger',
 }

ADMIN_SITE_HEADER = "Neurodevelopmental Assessment System"
ADMIN_SITE_TITLE = "NDAs"
ADMIN_INDEX_TITLE = "Welcome to NDAs"

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# ==============================================================================
# COMPREHENSIVE SECURITY HEADERS CONFIGURATION
# ==============================================================================

# Basic Security Headers (already configured but enhanced)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# SSL/HTTPS Settings (CRITICAL - Enable in production with HTTPS)
# Uncomment these when deploying with HTTPS
# SECURE_SSL_REDIRECT = True  # Forces HTTPS redirects
# SESSION_COOKIE_SECURE = True  # Ensures session cookies only sent over HTTPS
# CSRF_COOKIE_SECURE = True  # Ensures CSRF cookies only sent over HTTPS
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # For reverse proxy setups

# ==============================================================================
# CONTENT SECURITY POLICY (CSP) CONFIGURATION - NEW FORMAT
# ==============================================================================
# CSP is the most effective protection against XSS attacks

# New CSP configuration format for django-csp 4.0+
if DEBUG:
    # Development CSP - allows inline scripts/styles for admin and development
    CONTENT_SECURITY_POLICY = {
        'DIRECTIVES': {
            'default-src': ("'self'",),
            'script-src': (
                "'self'", 
                "'unsafe-inline'",  # Needed for Django admin and some templates
                "'unsafe-eval'",    # Needed for some JS libraries
                "https://cdn.jsdelivr.net",  # For Chart.js and other CDN scripts
                "https://cdnjs.cloudflare.com",
                "https://vjs.zencdn.net",  # For Video.js scripts
            ),
            'script-src-elem': (  # Add explicit script-src-elem directive
                "'self'", 
                "'unsafe-inline'",
                "https://cdn.jsdelivr.net",
                "https://cdnjs.cloudflare.com", 
                "https://vjs.zencdn.net",
            ),
            'style-src': (
                "'self'", 
                "'unsafe-inline'",  # Needed for Django admin and Bootstrap
                "https://cdn.jsdelivr.net",
                "https://cdnjs.cloudflare.com",
                "https://fonts.googleapis.com",  # For Google Fonts
                "https://vjs.zencdn.net",  # For Video.js styles
            ),
            'style-src-elem': (  # Add explicit style-src-elem directive
                "'self'", 
                "'unsafe-inline'",
                "https://cdn.jsdelivr.net",
                "https://cdnjs.cloudflare.com",
                "https://fonts.googleapis.com",  # For Google Fonts
                "https://vjs.zencdn.net",  # For Video.js styles
            ),
            'img-src': ("'self'", "data:", "blob:", "https:"),
            'font-src': (
                "'self'", 
                "https://cdn.jsdelivr.net", 
                "https://cdnjs.cloudflare.com",
                "https://fonts.gstatic.com",  # For Google Fonts
            ),
            'connect-src': ("'self'",),
            'frame-src': ("'none'",),
            'object-src': ("'none'",),
            'base-uri': ("'self'",),
            'form-action': ("'self'",),
        }
    }
else:
    # Production CSP - more restrictive
    CONTENT_SECURITY_POLICY = {
        'DIRECTIVES': {
            'default-src': ("'self'",),
            'script-src': (
                "'self'",
                # Add specific script hashes or nonces in production
                # Remove 'unsafe-inline' and 'unsafe-eval' for maximum security
            ),
            'style-src': ("'self'",),
            'img-src': ("'self'", "data:"),
            'font-src': ("'self'",),
            'connect-src': ("'self'",),
            'frame-src': ("'none'",),
            'object-src': ("'none'",),
            'base-uri': ("'self'",),
            'form-action': ("'self'",),
        }
    }

# CSP Reporting (optional but recommended for monitoring)
# CSP_REPORT_URI = '/csp-report/'  # Uncomment if you want CSP violation reports

# ==============================================================================
# PERMISSIONS POLICY CONFIGURATION
# ==============================================================================
# Controls browser features like camera, microphone, location, etc.

PERMISSIONS_POLICY = {
    "accelerometer": [],      # Deny access to accelerometer
    "ambient-light-sensor": [],  # Deny access to ambient light sensor
    "autoplay": [],           # Deny autoplay
    "camera": [],             # Deny camera access (important for medical app)
    "display-capture": [],    # Deny screen capture
    "document-domain": [],    # Deny document.domain
    "encrypted-media": [],    # Deny encrypted media
    "fullscreen": ["self"],   # Allow fullscreen only from same origin
    "geolocation": [],        # Deny location access
    "gyroscope": [],          # Deny gyroscope
    "magnetometer": [],       # Deny magnetometer
    "microphone": [],         # Deny microphone access
    "midi": [],               # Deny MIDI access
    "payment": [],            # Deny payment API
    "picture-in-picture": [], # Deny picture-in-picture
    "speaker": [],            # Deny speaker selection
    "usb": [],                # Deny USB access
    "vibrate": [],            # Deny vibration API
    "vr": [],                 # Deny VR access
}

# ==============================================================================
# ADDITIONAL SECURITY SETTINGS
# ==============================================================================

# Cookie Security
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 3600  # 1 hour session timeout
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
CSRF_COOKIE_SAMESITE = 'Lax'     # CSRF protection

# Additional Security Headers
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'  # Prevents some attacks

# ==============================================================================
# SECURITY HEADER TESTING
# ==============================================================================
# After implementing these settings, test your security headers at:
# - https://securityheaders.com/
# - https://observatory.mozilla.org/
# - https://csp-evaluator.withgoogle.com/
