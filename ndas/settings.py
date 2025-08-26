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
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
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

# Security Headers Configuration
SECURE_BROWSER_XSS_FILTER = False
SECURE_CONTENT_TYPE_NOSNIFF = False
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

# Content Security Policy (CSP)
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
SESSION_COOKIE_AGE = 3600  # 1 hour session timeout
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# Video Upload and Processing Settings
VIDEO_MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
VIDEO_ALLOWED_FORMATS = ['mp4', 'mov', 'avi', 'mkv', 'webm']
VIDEO_COMPRESSION_ENABLED = True
VIDEO_THUMBNAIL_GENERATION = True
VIDEO_DEFAULT_QUALITY = 'medium'

# File Upload Security
DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Media file organization
MEDIA_SUBDIRECTORIES = {
    'videos': 'videos/',
    'video_thumbnails': 'videos/thumbnails/',
    'video_compressed': 'videos/compressed/',
    'attachments': 'attachments/',
    'profile_pictures': 'profile_pictures/',
}

# Redis Configuration
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
REDIS_DB = int(os.environ.get('REDIS_DB', '0'))

# Cache Configuration
# Use local memory cache for development when Redis is not available
try:
    import redis
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    redis_client.ping()
    # Redis is available, use it
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}',
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
            'KEY_PREFIX': 'ndas',
            'TIMEOUT': 300,  # 5 minutes default timeout
        }
    }
except (redis.ConnectionError, redis.RedisError, ImportError):
    # Fallback to local memory cache for development
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

# Celery Configuration
CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Celery Task Configuration
# Temporarily enable synchronous processing when Redis is not available
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'True').lower() == 'true'  # For testing without Redis
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ROUTES = {
    'video.tasks.process_video_task': {'queue': 'video_processing'},
    'video.tasks.extract_video_metadata_task': {'queue': 'video_processing'},
    'video.tasks.generate_thumbnail_task': {'queue': 'video_processing'},
    'video.tasks.compress_video_task': {'queue': 'video_processing'},
    'video.tasks.batch_process_videos': {'queue': 'video_processing'},
}

# Celery Worker Configuration
CELERY_WORKER_CONCURRENCY = int(os.environ.get('CELERY_WORKER_CONCURRENCY', '2'))
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 512000  # 512MB
CELERY_TASK_SOFT_TIME_LIMIT = 1800  # 30 minutes
CELERY_TASK_TIME_LIMIT = 3600  # 1 hour
CELERY_TASK_DEFAULT_RETRY_DELAY = 60
CELERY_TASK_MAX_RETRIES = 3

# Video Processing Configuration
FFMPEG_BINARY = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
FFPROBE_BINARY = os.environ.get('FFPROBE_BINARY', 'ffprobe')

# Video processing limits
MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
MAX_VIDEO_DURATION = 3600  # 1 hour in seconds
MAX_CONCURRENT_PROCESSING = 3

# Supported video formats for processing
SUPPORTED_VIDEO_INPUTS = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v']
VIDEO_OUTPUT_FORMAT = 'mp4'
VIDEO_OUTPUT_CODEC = 'libx264'
AUDIO_OUTPUT_CODEC = 'aac'

# Quality presets for video compression
VIDEO_QUALITY_PRESETS = {
    'original': {
        'description': 'Original Quality (no compression)',
        'width': None,
        'height': None,
        'video_bitrate': None,
        'audio_bitrate': '128k',
        'crf': None,
    },
    'high': {
        'description': 'High Quality (1080p)',
        'width': 1920,
        'height': 1080,
        'video_bitrate': '4000k',
        'audio_bitrate': '128k',
        'crf': 20,
    },
    'medium': {
        'description': 'Medium Quality (720p)',
        'width': 1280,
        'height': 720,
        'video_bitrate': '2500k',
        'audio_bitrate': '128k',
        'crf': 23,
    },
    'low': {
        'description': 'Low Quality (480p)',
        'width': 854,
        'height': 480,
        'video_bitrate': '1000k',
        'audio_bitrate': '96k',
        'crf': 26,
    },
    'mobile': {
        'description': 'Mobile Quality (360p)',
        'width': 640,
        'height': 360,
        'video_bitrate': '500k',
        'audio_bitrate': '64k',
        'crf': 28,
    },
}

# Monitoring and Logging
CELERY_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True

# Periodic tasks (requires django-celery-beat)
# CELERY_BEAT_SCHEDULE = {
#     'cleanup-temp-files': {
#         'task': 'video.tasks.cleanup_temp_files',
#         'schedule': 3600.0,  # Every hour
#     },
# }
