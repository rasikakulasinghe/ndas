from pathlib import Path
import os
from django.contrib.messages import constants as messages
import environ

env = environ.Env(DEBUG=(bool, False))

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Take environment variables from .env file
environ.Env.read_env(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

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
    'django_permissions_policy',  # Permissions Policy
    'django_user_agents',
    'users.apps.UsersConfig',
    'patients.apps.PatientsConfig',
    'video.apps.VideoConfig',
    'ckeditor',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'csp.middleware.CSPMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'users.middleware.UserActivityMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_user_agents.middleware.UserAgentMiddleware',
]

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
            ],
        },
    },
]

WSGI_APPLICATION = 'ndas.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 120,
            # 'init_command': (
            #     'PRAGMA journal_mode=WAL;'
            #     'PRAGMA synchronous=NORMAL;'
            #     'PRAGMA cache_size=1000;'
            #     'PRAGMA temp_store=memory;'
            #     'PRAGMA mmap_size=268435456;'  # 256MB
            # ),
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
STATIC_URL = env('STATIC_URL')
MEDIA_URL = env('MEDIA_URL')
MEDIA_ROOT = BASE_DIR / 'media'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise configuration for serving static files
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = "users.CustomUser"

# Email Configuration
EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = BASE_DIR / 'sent_emails'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
try:
    EMAIL_HOST_USER = env('EMAIL_HOST_USER')
except:
    EMAIL_HOST_USER = ''
try:
    EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
except:
    EMAIL_HOST_PASSWORD = ''
DEFAULT_FROM_EMAIL = 'noreply@ndas-system.com'
EMAIL_VERIFICATION_REQUIRED = True
EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS = 24

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
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = env('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False)
SECURE_HSTS_PRELOAD = env('SECURE_HSTS_PRELOAD', default=False)
SECURE_SSL_REDIRECT = env('SECURE_SSL_REDIRECT', default=False)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if env('USE_SSL_PROXY', default=False) else None
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

# Content Security Policy (CSP)
CSP_INCLUDE_NONCE_IN = ['script-src', 'style-src']
CSP_EXCLUDE_URL_PREFIXES = ('/admin/',)

if DEBUG:
    CSP_DEFAULT_SRC = ("'self'",)
    CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com", "https://vjs.zencdn.net")
    CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com", "https://fonts.googleapis.com", "https://vjs.zencdn.net")
    CSP_IMG_SRC = ("'self'", "data:", "blob:", "https:")
    CSP_FONT_SRC = ("'self'", "data:", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com", "https://fonts.gstatic.com")
    CSP_CONNECT_SRC = ("'self'",)
    CSP_FRAME_SRC = ("'none'",)
    CSP_OBJECT_SRC = ("'none'",)
    CSP_BASE_URI = ("'self'",)
    CSP_FORM_ACTION = ("'self'",)
else:
    CSP_DEFAULT_SRC = ("'self'",)
    CSP_SCRIPT_SRC = ("'self'",)
    CSP_STYLE_SRC = ("'self'",)
    CSP_IMG_SRC = ("'self'", "data:")
    CSP_FONT_SRC = ("'self'", "data:")
    CSP_CONNECT_SRC = ("'self'",)
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
SESSION_COOKIE_SECURE = env('SESSION_COOKIE_SECURE', default=False)
CSRF_COOKIE_SECURE = env('CSRF_COOKIE_SECURE', default=False)
SESSION_COOKIE_AGE = env('SESSION_COOKIE_AGE', default=3600)  # 1 hour default
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = True

# Video Upload and Processing Settings
VIDEO_MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
VIDEO_ALLOWED_FORMATS = ['mp4', 'mov', 'avi', 'mkv', 'webm']

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
if env('REDIS_URL', default=None):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': env('REDIS_URL'),
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
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Rate Limiting and Brute Force Protection
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_ENABLE = env('RATELIMIT_ENABLE', default=True)

# Performance Optimizations
USE_ETAGS = True
USE_L10N = True

# File Upload Optimization
FILE_UPLOAD_HANDLERS = [
    'django.core.files.uploadhandler.MemoryFileUploadHandler',
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]

# Database Query Optimization
DATABASE_ENGINE_OPTIONS = {
    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
    'charset': 'utf8mb4',
    'autocommit': True,
}

# Static Files Compression
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG

# Media Files Security
MEDIA_URL_EXPIRY = 3600  # 1 hour
SECURE_FILE_UPLOADS = True

# Additional Security Settings
SILENCED_SYSTEM_CHECKS = [
    'security.W019',  # Only if using HTTPS proxy
] if env('USE_SSL_PROXY', default=False) else []

# Create logs directory if it doesn't exist
import os
os.makedirs(BASE_DIR / 'logs', exist_ok=True)