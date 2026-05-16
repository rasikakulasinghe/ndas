from pathlib import Path
import os
from django.contrib.messages import constants as messages
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_cleanup.apps.CleanupConfig',
    'csp',  # Content Security Policy
    'django_permissions_policy',
    'django_user_agents',
    'ndas',  # Core NDAS app (for template tags)
    'institution.apps.InstitutionConfig',
    'referral.apps.ReferralConfig',
    'users.apps.UsersConfig',
    'patients.apps.PatientsConfig',
    'video.apps.VideoConfig',
    'reports.apps.ReportsConfig',
    'problemlist.apps.ProblemlistConfig',
    'ckeditor',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'csp.middleware.CSPMiddleware',
    'ndas.custom_codes.security_middleware.AdditionalSecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'users.middleware.UserActivityMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_user_agents.middleware.UserAgentMiddleware',
    'users.middleware.SubscriptionCheckMiddleware',
    'institution.middleware.InstitutionContextMiddleware',
]

if not DEBUG:
    # Add security headers validation middleware in production only
    MIDDLEWARE.append('ndas.custom_codes.security_middleware.SecurityHeadersValidationMiddleware')

ROOT_URLCONF = 'ndas.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates', BASE_DIR / 'static/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'institution.context_processors.institution_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'ndas.wsgi.application'

# Database - PostgreSQL for Production, SQLite for Development
DB_ENGINE = config('DB_ENGINE', default=None)
if DB_ENGINE:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default=5432, cast=int),
            'OPTIONS': {
                'connect_timeout': 60,
                # FIX 2.3: Changed from 'serializable' to 'read committed' for better performance
                # 'serializable' can cause deadlocks and is too strict for most web applications
                # 'read committed' provides sufficient isolation without performance penalty
                'options': '-c default_transaction_isolation="read committed"'
            },
        }
    }
else:
    # Fallback to SQLite for development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {
                'timeout': 120,
            },
        }
    }

# Database connection pooling for production
if not DEBUG:
    DATABASES['default']['CONN_MAX_AGE'] = 300

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        'OPTIONS': {'max_similarity': 0.7}
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12}
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# Git Bash on Windows may convert /media/ paths to absolute paths (e.g., C:/Program Files/Git/media/)
# Ensure we always use relative URLs for STATIC_URL and MEDIA_URL
_static_url = config('STATIC_URL', default='/static/')
_media_url = config('MEDIA_URL', default='/media/')

# Sanitize URLs to prevent Git Bash path mangling
# If the URL contains a colon (indicating an absolute path), use default
STATIC_URL = '/static/' if ':' in _static_url else _static_url
MEDIA_URL = '/media/' if ':' in _media_url else _media_url

# Use environment paths if provided, otherwise use defaults
STATIC_ROOT_ENV = config('STATIC_ROOT', default=None)
if STATIC_ROOT_ENV:
    STATIC_ROOT = STATIC_ROOT_ENV
else:
    STATIC_ROOT = BASE_DIR / 'staticfiles'  # Changed from 'static' to 'staticfiles'

MEDIA_ROOT_ENV = config('MEDIA_ROOT', default=None)
# Only use environment MEDIA_ROOT if it's a valid path and doesn't contain Git Bash artifacts
if MEDIA_ROOT_ENV and MEDIA_ROOT_ENV.strip() and 'Program Files/Git' not in MEDIA_ROOT_ENV:
    MEDIA_ROOT = MEDIA_ROOT_ENV
else:
    MEDIA_ROOT = BASE_DIR / 'media'

# Directory where Django looks for static files during development
STATICFILES_DIRS = [BASE_DIR / 'static']

# WhiteNoise configuration for serving static files
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# ─── Phase 2: Multi-Institution ─────────────────────────────────────────────
MULTI_INSTITUTION_ENABLED = config('MULTI_INSTITUTION_ENABLED', default=True, cast=bool)
DEFAULT_INSTITUTION_NAME = config('DEFAULT_INSTITUTION_NAME', default='Default Institution')
DEFAULT_INSTITUTION_SLUG = config('DEFAULT_INSTITUTION_SLUG', default='default')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = "users.CustomUser"

# Email Configuration - Environment-based
if DEBUG:
    # Development: Console backend for testing
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    # Production: SMTP backend
    EMAIL_BACKEND = config('EMAIL_BACKEND', default="django.core.mail.backends.smtp.EmailBackend")
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=10, cast=int)

DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@ndas-system.com')
EMAIL_VERIFICATION_REQUIRED = config('EMAIL_VERIFICATION_REQUIRED', default=True, cast=bool)
EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS = config('EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS', default=24, cast=int)

MESSAGE_TAGS = {
    messages.DEBUG: 'alert-secondary',
    messages.INFO: 'alert-info',
    messages.SUCCESS: 'alert-success',
    messages.WARNING: 'alert-warning',
    messages.ERROR: 'alert-danger',
}

# Admin site customization
ADMIN_SITE_HEADER = "Neurodevelopmental Assessment System"
ADMIN_SITE_TITLE = "NDAs"
ADMIN_INDEX_TITLE = "Welcome to NDAs"

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO' if not DEBUG else 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
            'filters': ['require_debug_false'],
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'] if DEBUG else ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['security_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'users.middleware': {
            'handlers': ['security_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Security Headers Configuration
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=False, cast=bool)
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if config('SECURE_PROXY_SSL_HEADER', default=False, cast=bool) else None
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

# Content Security Policy (CSP)
# Only include nonces for scripts - inline styles are less risky and templates use many inline styles
# When nonces are present for styles, 'unsafe-inline' is ignored and all inline styles get blocked
CSP_INCLUDE_NONCE_IN = ['script-src']
CSP_EXCLUDE_URL_PREFIXES = ('/admin/',)

if DEBUG:
    SECURE_HSTS_SECONDS = 0
    CSP_DEFAULT_SRC = ("'self'",)
    CSP_SCRIPT_SRC = ("'self'", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com", "https://unpkg.com", "https://vjs.zencdn.net")
    CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com", "https://fonts.googleapis.com", "https://vjs.zencdn.net")
    CSP_IMG_SRC = ("'self'", "data:", "blob:", "https:")
    CSP_FONT_SRC = ("'self'", "data:", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com", "https://fonts.gstatic.com")
    CSP_CONNECT_SRC = ("'self'", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com", "https://unpkg.com", "https://vjs.zencdn.net")
    CSP_FRAME_SRC = ("'none'",)
    CSP_OBJECT_SRC = ("'none'",)
    CSP_BASE_URI = ("'self'",)
    CSP_FORM_ACTION = ("'self'",)
else:
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    # Production CSP - Strict policy with nonce-based inline scripts
    # 'unsafe-inline' allowed for styles (templates and libraries use inline styles)
    # No 'unsafe-inline' or 'unsafe-eval' for scripts for XSS protection
    CSP_DEFAULT_SRC = ("'self'",)
    CSP_SCRIPT_SRC = ("'self'", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com", "https://unpkg.com", "https://vjs.zencdn.net")
    CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com", "https://fonts.googleapis.com", "https://vjs.zencdn.net")
    CSP_IMG_SRC = ("'self'", "data:", "blob:", "https:")
    CSP_FONT_SRC = ("'self'", "data:", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com", "https://fonts.gstatic.com")
    CSP_CONNECT_SRC = ("'self'", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com", "https://unpkg.com", "https://vjs.zencdn.net")
    CSP_FRAME_SRC = ("'none'",)
    CSP_OBJECT_SRC = ("'none'",)
    CSP_BASE_URI = ("'self'",)
    CSP_FORM_ACTION = ("'self'",)

# Permissions Policy - Control browser features
PERMISSIONS_POLICY = {
    "accelerometer": [],
    "camera": [],
    "display-capture": [],
    "fullscreen": ["self"],
    "geolocation": [],
    "microphone": [],
    "payment": [],
    "usb": [],
}

# Cookie Security
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)
SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=3600, cast=int)  # 1 hour default
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = True

# FIX 3.1: Comprehensive File Upload Configuration
# Video Upload and Processing Settings
VIDEO_MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
VIDEO_ALLOWED_FORMATS = ['mp4', 'mov', 'avi', 'mkv', 'webm']

# File Upload Size Limits (centralized for consistency)
FILE_UPLOAD_LIMITS = {
    'VIDEO_MAX_SIZE': 2 * 1024 * 1024 * 1024,  # 2GB for videos
    'IMAGE_MAX_SIZE': 10 * 1024 * 1024,  # 10MB for images
    'DOCUMENT_MAX_SIZE': 100 * 1024 * 1024,  # 100MB for documents
    'ATTACHMENT_MAX_SIZE': 100 * 1024 * 1024,  # 100MB for general attachments
    'PROFILE_PICTURE_MAX_SIZE': 5 * 1024 * 1024,  # 5MB for profile pictures
}

# Allowed File Extensions by Type
ALLOWED_FILE_EXTENSIONS = {
    'IMAGE': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'],
    'VIDEO': ['.mp4', '.mov', '.avi', '.mkv', '.webm'],
    'PDF': ['.pdf'],
    'DOCUMENT': ['.doc', '.docx', '.txt', '.rtf', '.odt'],
}

# File Upload Security
DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Media file organization
MEDIA_SUBDIRECTORIES = {
    'videos': 'videos/',
    'attachments': 'attachments/',
    'profile_pictures': 'profile_pictures/',
}

# Cache Configuration
REDIS_URL = config('REDIS_URL', default=None)
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'TIMEOUT': 300,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'CONNECTION_POOL_KWARGS': {'max_connections': 50},
                'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
                'IGNORE_EXCEPTIONS': True,
            }
        }
    }
else:
    # Use local memory cache for development
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
            'TIMEOUT': 300,
            'OPTIONS': {
                'MAX_ENTRIES': 1000,
            }
        }
    }

# Session Configuration
if DEBUG:
    # Use cached_db in development: sessions persist across server restarts
    SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
else:
    # Use cache in production: sessions backed by Redis for performance
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Rate Limiting and Brute Force Protection
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_ENABLE = config('RATELIMIT_ENABLE', default=True, cast=bool)
RATELIMIT_VIEW = 'ndas.views.handler_rate_limited'

# Performance Optimizations
USE_ETAGS = True
USE_L10N = True

# File Upload Optimization
FILE_UPLOAD_HANDLERS = [
    'django.core.files.uploadhandler.MemoryFileUploadHandler',
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]

# Static Files Compression
# STATICFILES_STORAGE is deprecated in Django 4.2+, using STORAGES instead
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG

# Additional Security Settings
SILENCED_SYSTEM_CHECKS = [
    'security.W019',  # Silenced when nginx/load balancer terminates SSL and SECURE_PROXY_SSL_HEADER is set in .env
] if config('SECURE_PROXY_SSL_HEADER', default=False, cast=bool) else []

# Production optimizations
if not DEBUG:
    # Security enhancements
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # Disable admin docs in production
    ADMINS = []
    MANAGERS = []

# Create logs directory if it doesn't exist
import os
os.makedirs(BASE_DIR / 'logs', exist_ok=True)