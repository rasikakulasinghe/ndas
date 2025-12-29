# Technology Stack - NDAS

**Generated:** 2025-12-29
**Project:** Neurodevelopmental Assessment System (NDAS)
**Architecture:** Django MVT (Model-View-Template) Monolith

---

## Technology Overview

| Category | Technology | Version | Justification |
|----------|-----------|---------|---------------|
| **Backend Framework** | Django | 4.2.16 | Python web framework for rapid development with built-in admin, ORM, and security features |
| **Language** | Python | 3.x | Primary language for Django backend |
| **Database (Dev)** | SQLite | 3.x | Lightweight database for development |
| **Database (Prod)** | PostgreSQL | Configurable | Production-grade relational database |
| **ORM** | Django ORM | 4.2.16 | Built-in Django ORM for database abstraction |
| **Static Files** | WhiteNoise | Latest | Efficient static file serving |
| **Frontend Framework** | AdminLTE | 3.2 | Bootstrap-based admin dashboard template |
| **CSS Framework** | Bootstrap | 4.6 | Responsive CSS framework |
| **JavaScript Enhancement** | HTMX | Latest | Modern approach for dynamic HTML without heavy JS frameworks |
| **Video Player** | Video.js | Latest | HTML5 video player for assessment videos |
| **Rich Text Editor** | CKEditor | Latest | WYSIWYG editor for content management |
| **Form Enhancement** | Select2 | Latest | Advanced select boxes with search |
| **Icons** | Font Awesome | 6.4 | Icon library |

---

## Security Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Content Security Policy** | django-csp | CSP header management and nonce-based script protection |
| **Permissions Policy** | django-permissions-policy | Browser feature permissions control |
| **Security Headers** | Custom Middleware | Additional security headers (HSTS, X-Content-Type-Options, etc.) |
| **User Agent Detection** | django-user-agents | Browser and device detection |
| **Rate Limiting** | django-ratelimit | Brute force protection (10/min CRUD operations) |
| **File Cleanup** | django-cleanup | Automatic cleanup of orphaned files |
| **Input Sanitization** | bleach | HTML sanitization for XSS prevention |
| **File Validation** | python-magic | MIME type verification for uploads |

---

## Architecture Pattern

**Pattern:** Django MVT (Model-View-Template) with Service Layer

**Characteristics:**
- **Models:** Django ORM models with custom abstract base classes (TimeStampedModel, UserTrackingMixin)
- **Views:** Function-based and class-based views with decorators for auth, rate limiting, HTTP methods
- **Templates:** Django template engine with AdminLTE components
- **Service Layer:** Custom business logic in `ndas/custom_codes/`
- **Middleware Stack:** 14-layer middleware for security, session management, and user tracking

---

## Key Dependencies

### Core Django Apps
- `django.contrib.admin` - Admin interface
- `django.contrib.auth` - Authentication system
- `django.contrib.sessions` - Session management
- `django.contrib.staticfiles` - Static file handling

### Custom NDAS Apps
- `ndas` - Core project configuration and custom codes
- `users` - User management and authentication
- `patients` - Patient records and management
- `video` - Video upload, storage, and assessment
- `reports` - PDF/Excel report generation
- `problemlist` - Problem list management

### Third-Party Packages
- `python-decouple` - Environment configuration
- `Pillow` - Image processing
- `reportlab` / `weasyprint` - PDF generation
- `openpyxl` - Excel file generation
- `bleach` - HTML sanitization
- `python-magic` - File type detection

---

## Middleware Stack (Execution Order)

1. `SecurityMiddleware` - Django security features
2. `WhiteNoiseMiddleware` - Static file serving
3. `CSPMiddleware` - Content Security Policy
4. `AdditionalSecurityHeadersMiddleware` - Custom security headers
5. `SessionMiddleware` - Session management
6. `CommonMiddleware` - Common request/response processing
7. `CsrfViewMiddleware` - CSRF protection
8. `AuthenticationMiddleware` - User authentication
9. `UserActivityMiddleware` - Auto-tracks user changes (added_by, last_edit_by)
10. `MessageMiddleware` - Flash messages
11. `XFrameOptionsMiddleware` - Clickjacking protection
12. `UserAgentMiddleware` - User agent parsing
13. `SubscriptionCheckMiddleware` - Subscription validation
14. `SecurityHeadersValidationMiddleware` - Production header validation

---

## Database Configuration

### Development
- **Engine:** SQLite 3
- **Location:** `db.sqlite3` in project root
- **Connection timeout:** 120 seconds

### Production
- **Engine:** PostgreSQL (configurable)
- **Isolation Level:** Read Committed (optimal performance)
- **Connection Pooling:** 300 seconds (CONN_MAX_AGE)
- **Connect Timeout:** 60 seconds

---

## Cache Configuration

### Development
- **Backend:** LocMem (Local Memory Cache)
- **Timeout:** 300 seconds
- **Max Entries:** 1000

### Production (Optional)
- **Backend:** Redis (if REDIS_URL configured)
- **Timeout:** 300 seconds
- **Max Connections:** 50
- **Compression:** zlib

---

## File Upload Limits

| File Type | Max Size | Allowed Extensions |
|-----------|----------|-------------------|
| **Videos** | 2 GB | .mp4, .mov, .avi, .mkv, .webm |
| **Images** | 10 MB | .jpg, .jpeg, .png, .gif, .bmp, .webp |
| **Documents** | 100 MB | .doc, .docx, .txt, .rtf, .odt |
| **Attachments** | 100 MB | Various |
| **Profile Pictures** | 5 MB | Image formats |

---

## Email Configuration

### Development
- **Backend:** Console (prints to console)

### Production
- **Backend:** SMTP
- **Default Host:** smtp.gmail.com
- **Port:** 587
- **TLS:** Enabled
- **Timeout:** 10 seconds
- **Verification:** Optional (configurable)
- **Token Expiry:** 24 hours

---

## Logging Configuration

### Log Files
- **Application Log:** `logs/django.log` (15MB rotation, 10 backups)
- **Security Log:** `logs/security.log` (15MB rotation, 10 backups)

### Log Levels
- **Development:** DEBUG level
- **Production:** INFO level

### Logged Events
- Django framework events
- Security events (authentication, authorization)
- User activity (via UserActivityMiddleware)

---

## Environment Configuration

Uses `python-decouple` for environment variables from `.env` file:

**Required:**
- `SECRET_KEY` - Django secret key

**Optional (with defaults):**
- `DEBUG` - Debug mode (default: False)
- `ALLOWED_HOSTS` - Allowed hosts (default: localhost,127.0.0.1)
- `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` - Database config
- `REDIS_URL` - Redis cache URL
- `EMAIL_*` - Email configuration
- `SECURE_*` - Security settings
- `RATELIMIT_ENABLE` - Rate limiting toggle

---

## Security Features

### Content Security Policy (CSP)
- **Script nonces:** Required for inline scripts (production)
- **Unsafe-inline:** Blocked for scripts, allowed for styles
- **Trusted CDNs:** cdn.jsdelivr.net, cdnjs.cloudflare.com, unpkg.com, vjs.zencdn.net
- **Frame embedding:** Blocked (frame-src: 'none')
- **Object/Embed:** Blocked (object-src: 'none')

### Cookie Security
- **HTTPOnly:** Enabled for session and CSRF cookies
- **Secure:** Configurable (required for HTTPS)
- **SameSite:** Lax mode
- **Session Age:** 1 hour (configurable)
- **Browser Close:** Sessions expire on browser close

### Password Validation
- **Min Length:** 12 characters
- **Similarity Check:** Max 70% similarity to user attributes
- **Common Passwords:** Blocked
- **Numeric Only:** Blocked

### Rate Limiting
- **CRUD Operations:** 10 requests/minute (create, edit)
- **Delete Operations:** 5 requests/minute
- **Coverage:** 24 protected endpoints

---

## Internationalization

- **Language:** English (en-us)
- **Timezone:** Asia/Kolkata
- **i18n:** Enabled
- **Timezone Support:** Enabled

---

## Performance Optimizations

### Static Files
- **Compression:** WhiteNoise with manifest
- **ETags:** Enabled
- **Compression:** Enabled in production

### Database
- **Connection Pooling:** 300 seconds (production)
- **Query Optimization:** Select/prefetch related encouraged

### File Uploads
- **Memory Handler:** Up to 100MB in memory
- **Temporary Files:** Large files use temp storage
- **Streaming:** Supported for large files

---

## Testing Framework

- **Test Runner:** Django built-in test framework
- **Test Database:** SQLite in-memory (fast)
- **Coverage:** Tests in each app's `tests/` directory
- **Command:** `python manage.py test [app_name]`

---

## Deployment Stack

### Static Files
- **Collection:** `python manage.py collectstatic`
- **Storage:** `staticfiles/` directory
- **Serving:** WhiteNoise (production)

### WSGI Server
- **Application:** `ndas.wsgi.application`
- **Recommended:** Gunicorn (for production)

### Process Management
- **Recommended:** systemd or supervisor

### Reverse Proxy
- **Recommended:** Nginx or Apache
- **HTTPS:** Required for production (SSL/TLS)

---

## Medical Domain Features

### Patient Management
- **Identifiers:** BHT, NNC, PTC, PC, PIN, Disk No.
- **Data Validation:** Birth weight (300-8000g), APGAR (0-10), Gestational age (20-44 weeks)

### Assessment Types
- **GPA** - General Physical Assessment
- **HINE** - Hammersmith Infant Neurological Examination
- **CDIC** - Child Development Inventory Checklist
- **Developmental** - General developmental assessments

### Video Processing
- **Storage:** `media/videos/`
- **Metadata Extraction:** Duration, resolution, codec
- **Security:** MIME validation, size limits

### Report Generation
- **PDF:** ReportLab / WeasyPrint
- **Excel:** openpyxl with multi-sheet support
- **Anonymization:** Patient data anonymization for exports

---

## Development Tools

### Linting & Formatting
- Not explicitly configured (manual code review)

### IDE Integration
- VS Code configuration in `.vscode/`

### Version Control
- **Git:** Repository initialized
- **Ignored:** `.env`, `venv/`, `__pycache__/`, `*.pyc`, `db.sqlite3`, `media/`, `staticfiles/`, `logs/`

---

## Future Considerations

### Potential Enhancements
- **Background Tasks:** Celery + Redis for async processing
- **API Layer:** Django REST Framework for mobile/external integrations
- **Real-time:** Django Channels for WebSocket support
- **Monitoring:** Sentry for error tracking
- **APM:** New Relic or DataDog for performance monitoring
