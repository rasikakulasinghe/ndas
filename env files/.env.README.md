# Environment Configuration Guide

This guide explains how to configure NDAS for different deployment scenarios using environment files.

## Quick Start

**Choose your deployment scenario:**

1. **Local Development**
   ```bash
   cp .env.development.example .env
   ```

2. **Production - Shared Hosting (cPanel with SQLite)**
   ```bash
   cp .env.production.example .env
   nano .env  # Edit with your settings
   ```

3. **Production - VPS/Cloud (PostgreSQL)**
   ```bash
   cp .env.production.postgresql.example .env
   nano .env  # Edit with your settings
   ```

## Available Environment Files

| File | Purpose | Use Case |
|------|---------|----------|
| `.env.example` | General template showing all options | Reference for all available settings |
| `.env.development.example` | Local development | Running on localhost with SQLite |
| `.env.production.example` | cPanel/Shared hosting | Small to medium deployments with SQLite |
| `.env.production.postgresql.example` | VPS/Cloud hosting | Large deployments with PostgreSQL |

## Configuration Sections

### 1. Core Settings (REQUIRED)

```env
SECRET_KEY=your-secret-key-here
DEBUG=False  # NEVER True in production
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

**Generate SECRET_KEY:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 2. Database Configuration

**Option A: SQLite (Default)**
```env
# Leave empty to use SQLite
# DB_ENGINE=
# DB_NAME=
```

**Option B: PostgreSQL (Recommended for production)**
```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=ndas_production
DB_USER=ndas_user
DB_PASSWORD=your-secure-password
DB_HOST=localhost
DB_PORT=5432
```

**Option C: MySQL/MariaDB**
```env
DB_ENGINE=django.db.backends.mysql
DB_NAME=ndas_db
DB_USER=ndas_user
DB_PASSWORD=your-secure-password
DB_HOST=localhost
DB_PORT=3306
```

### 3. Static and Media Files

**Development (leave commented):**
```env
STATIC_URL=/static/
MEDIA_URL=/media/
# STATIC_ROOT and MEDIA_ROOT not needed
```

**Production (set absolute paths):**
```env
STATIC_URL=/static/
MEDIA_URL=/media/
STATIC_ROOT=/var/www/yourdomain.com/static/
MEDIA_ROOT=/var/www/yourdomain.com/media/
```

### 4. Email Configuration

**Development (Console):**
```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

**Production (SMTP):**
```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@yourdomain.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

**Common SMTP Providers:**

| Provider | Host | Port | TLS |
|----------|------|------|-----|
| Gmail | smtp.gmail.com | 587 | Yes |
| Outlook | smtp-mail.outlook.com | 587 | Yes |
| SendGrid | smtp.sendgrid.net | 587 | Yes |
| AWS SES | email-smtp.region.amazonaws.com | 587 | Yes |
| cPanel | mail.yourdomain.com | 587 | Yes |

### 5. SSL/HTTPS Configuration

**Development (HTTP):**
```env
SECURE_SSL_REDIRECT=False
SECURE_PROXY_SSL_HEADER=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
```

**Production (HTTPS):**
```env
SECURE_SSL_REDIRECT=True
SECURE_PROXY_SSL_HEADER=True
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

⚠️ **Important**: Only enable HTTPS settings after SSL certificate is installed and tested!

### 6. Cache Configuration

**No Redis (File-based cache):**
```env
REDIS_URL=
```

**With Redis:**
```env
REDIS_URL=redis://localhost:6379/0
```

**Redis Cloud:**
```env
REDIS_URL=redis://:password@host:port/0
```

### 7. Security Settings

```env
# Rate limiting (production: True, development: False)
RATELIMIT_ENABLE=True

# Session timeout (seconds) - 3600 = 1 hour
SESSION_COOKIE_AGE=3600
```

### 8. File Upload Limits

```env
# Maximum upload size in bytes
# 104857600 = 100MB
# 2147483648 = 2GB
MAX_UPLOAD_SIZE=104857600

# Allowed extensions (comma-separated, no spaces)
ALLOWED_VIDEO_EXTENSIONS=mp4,avi,mov,wmv,webm,mkv
ALLOWED_IMAGE_EXTENSIONS=jpg,jpeg,png,gif,webp
ALLOWED_DOCUMENT_EXTENSIONS=pdf,doc,docx,txt
```

### 9. Logging

```env
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Development: DEBUG
# Production: INFO or WARNING
LOG_LEVEL=INFO
```

### 10. Timezone and Localization

```env
# Set your timezone
TIME_ZONE=Asia/Kolkata

# Language
LANGUAGE_CODE=en-us
```

**Common Timezones:**
- `UTC` - Coordinated Universal Time
- `Asia/Kolkata` - India Standard Time
- `America/New_York` - Eastern Time (US)
- `Europe/London` - British Time
- `Asia/Tokyo` - Japan Standard Time
- `Australia/Sydney` - Australian Eastern Time

## Environment-Specific Examples

### Development Configuration

Perfect for local development with minimal setup:

```env
SECRET_KEY=dev-secret-key-not-for-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# SQLite (default)
# No database configuration needed

# Console email backend
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# No SSL
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False

# Disabled rate limiting for testing
RATELIMIT_ENABLE=False

# Debug logging
LOG_LEVEL=DEBUG
```

### Production - cPanel Configuration

For shared hosting with cPanel:

```env
SECRET_KEY=generated-secret-key-from-django
DEBUG=False
ALLOWED_HOSTS=demo-ndas.rasikakulasinghe.com,www.demo-ndas.rasikakulasinghe.com

# SQLite (default for shared hosting)
# Database file: db.sqlite3

# Paths
STATIC_ROOT=/home/username/public_html/yourdomain.com/static/
MEDIA_ROOT=/home/username/public_html/yourdomain.com/media/

# Email via cPanel
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mail.yourdomain.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@yourdomain.com
EMAIL_HOST_PASSWORD=secure-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# SSL enabled
SECURE_SSL_REDIRECT=True
SECURE_PROXY_SSL_HEADER=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# No Redis (file-based cache)
REDIS_URL=

# Production settings
RATELIMIT_ENABLE=True
SESSION_COOKIE_AGE=3600
LOG_LEVEL=INFO
TIME_ZONE=Asia/Kolkata
```

### Production - VPS Configuration

For VPS/Cloud hosting with PostgreSQL:

```env
SECRET_KEY=generated-secret-key-from-django
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,api.yourdomain.com

# PostgreSQL
DB_ENGINE=django.db.backends.postgresql
DB_NAME=ndas_production
DB_USER=ndas_user
DB_PASSWORD=very-secure-database-password
DB_HOST=localhost
DB_PORT=5432

# Paths
STATIC_ROOT=/var/www/yourdomain.com/static/
MEDIA_ROOT=/var/www/yourdomain.com/media/

# Email via Gmail
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@yourdomain.com
EMAIL_HOST_PASSWORD=app-specific-password
DEFAULT_FROM_EMAIL=NDAS System <noreply@yourdomain.com>

# SSL enabled
SECURE_SSL_REDIRECT=True
SECURE_PROXY_SSL_HEADER=True
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Redis cache
REDIS_URL=redis://localhost:6379/0

# Production settings
RATELIMIT_ENABLE=True
SESSION_COOKIE_AGE=3600
MAX_UPLOAD_SIZE=2147483648
LOG_LEVEL=INFO
TIME_ZONE=Asia/Kolkata
```

## Security Best Practices

### 1. Secret Key
- ✅ Generate unique SECRET_KEY for each environment
- ✅ Use long, random strings (50+ characters)
- ❌ Never commit SECRET_KEY to version control
- ❌ Never reuse SECRET_KEY across environments

### 2. Debug Mode
- ✅ DEBUG=False in production
- ✅ DEBUG=True only in local development
- ❌ NEVER use DEBUG=True in production (exposes sensitive data)

### 3. HTTPS/SSL
- ✅ Enable SSL redirect after SSL certificate is installed
- ✅ Test HTTPS works before enabling HSTS
- ⚠️ HSTS can lock you out if SSL breaks - be cautious

### 4. File Permissions
```bash
chmod 600 .env  # Only owner can read/write
```

### 5. Database Passwords
- ✅ Use strong passwords (16+ characters)
- ✅ Mix uppercase, lowercase, numbers, symbols
- ❌ Never use default passwords
- ❌ Never commit database passwords to git

## Validation

After configuring your `.env` file:

```bash
# Check Django configuration
python manage.py check

# Check deployment settings (production)
python manage.py check --deploy

# Test database connection
python manage.py migrate --plan

# Test email configuration
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Test', 'from@example.com', ['to@example.com'])
```

## Troubleshooting

### .env file not being read

1. Verify file is named exactly `.env` (not `.env.txt` or `env`)
2. Check file is in project root (same directory as `manage.py`)
3. Verify `python-decouple` is installed: `pip install python-decouple`

### Database connection errors

1. Verify database credentials are correct
2. Check database server is running
3. Verify database user has proper permissions
4. Test connection manually (PostgreSQL: `psql -U user -d database`)

### Email not sending

1. Verify SMTP credentials are correct
2. Check if email host requires app-specific password (Gmail)
3. Verify firewall allows outbound connections on email port
4. Test SMTP: `telnet smtp.host.com 587`

### SSL/HTTPS issues

1. Verify SSL certificate is installed and valid
2. Test HTTPS works before enabling `SECURE_SSL_REDIRECT`
3. Check nginx/apache SSL configuration
4. Verify `ALLOWED_HOSTS` includes your domain

## Additional Resources

- **Main Documentation**: See `DEPLOYMENT.md` for full deployment guide
- **Project Settings**: Review `CLAUDE.md` for project guidelines
- **Django Docs**: https://docs.djangoproject.com/en/4.2/howto/deployment/
- **python-decouple**: https://pypi.org/project/python-decouple/

## Support

For issues or questions:
1. Review `DEPLOYMENT.md` for detailed deployment instructions
2. Check Django deployment checklist: `python manage.py check --deploy`
3. Review logs: `tail -f logs/django.log`
4. Contact system administrator

---

**Last Updated**: 2025-12-23
