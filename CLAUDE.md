# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Django Management
- **Run development server**: `python manage.py runserver`
- **Database migrations**: `python manage.py makemigrations && python manage.py migrate`
- **Create superuser**: `python manage.py createsuperuser`
- **Django shell**: `python manage.py shell`
- **Collect static files**: `python manage.py collectstatic`
- **Run tests**: `python manage.py test`
- **Run specific app tests**: `python manage.py test patients` or `python manage.py test users.tests.TestClassName`
- **Make migrations for specific app**: `python manage.py makemigrations patients`
- **Reset database** (development only): `python manage.py flush`

### Environment Setup
- Virtual environment is in `venv/` directory
- Activate with: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Unix)
- Install dependencies: `pip install -r requirements.txt`
- Environment variables: Configure `.env` file in project root for development settings

## Architecture Overview

### Core Structure
This is a Django-based **Neurodevelopmental Assessment System (NDAS)** that manages patient records, video assessments, and user authentication.

**Main Django Apps:**
- `patients/` - Patient management, assessments, and medical records
- `video/` - Video file handling, processing, and metadata management  
- `users/` - Custom user authentication, permissions, and activity tracking
- `ndas/` - Project settings, URLs, and core configuration

### Key Models and Relationships
- **Patient**: Core patient model with comprehensive medical data:
  - Multiple unique identifiers (BHT, NNC, PTC, PC, PIN numbers)
  - Birth information (gestational age, APGAR scores, delivery mode)
  - Proper indexing on searchable fields (baby_name, mother_name, gender)
- **Video**: Video files linked to patients with processing status and metadata
- **CustomUser**: Extended Django user model with profile and activity tracking
- **GMAssessment**: Patient assessment records with rich text fields
- **Attachment**: File attachments for patients with access control
- **Specialized Assessments**: CDICRecord, HINEAssessment, DevelopmentalAssessment
- **Bookmark**: User bookmark system for patient records

### Custom Code Organization
- `ndas/custom_codes/` contains reusable components:
  - `Custom_abstract_class.py` - Base models with timestamps and user tracking:
    - `TimeStampedModel`: Provides created_at/updated_at fields
    - `UserTrackingMixin`: Tracks who added/modified records
  - `choice.py` - Predefined choices using Django's TextChoices for consistency
  - `validators.py` - Custom field validators for medical data and file uploads
  - `custom_methods.py` - Utility functions

### Model Architecture Patterns
- **All models inherit from abstract base classes** for consistent auditing
- **Medical data validation** through custom validators (birth weight, APGAR scores)
- **Choice standardization** using centralized TextChoices for medical terminology
- **File upload validation** with size limits and type checking

### Frontend Architecture
- **AdminLTE-based UI framework** with professional medical interface design
- Templates in `templates/` organized by app with reusable partials:
  - `src/base.html` - Main layout for logged-in users
  - `src/basic_plane.html` - Layout for authentication pages
  - App-specific templates with consistent design patterns
- Static files in `static/` with enhanced functionality:
  - Custom JavaScript utilities (`app-utils.js`, `video-manager.js`)
  - HTMX integration for dynamic interactions
  - Select2 for enhanced form controls
  - Video.js for video playback
- Uses WhiteNoise for static file serving in production
- CKEditor integration for rich text editing

### Security Architecture
- **Comprehensive security middleware stack**:
  - Content Security Policy (CSP) and Permissions Policy
  - Rate limiting with django-ratelimit
  - HSTS and security headers (X-Frame-Options, X-Content-Type-Nosniff)
- **Session and authentication security**:
  - Session timeout set to 1 hour with browser close expiry  
  - User activity tracking middleware
  - CSRF and XSS protection
- **File upload security**:
  - Comprehensive validation for medical data and uploads
  - Size limits: Video files 2GB max, general uploads 100MB memory limit
  - File type validation and access control

### Database and Media
- **Development**: SQLite database (`db.sqlite3`) 
- **Production ready**: PostgreSQL support with connection pooling
- **Caching**: Redis integration for performance
- Media files organized in `media/` by type with date-based structure:
  - Video files: `media/videos/%Y/%m/` 
  - Profile pictures, attachments organized by type

### Production Features
- **Environment management**: `.env` file with python-decouple for security
- **Static file serving**: WhiteNoise configured for production
- **Caching**: Redis support with django-redis
- **Task processing**: Celery integration for video processing
- **Monitoring**: Sentry SDK for error tracking and health checks
- **Performance**: Database connection pooling and query optimization

## Testing
- Test files exist but are minimal: `video/tests.py`, `users/tests.py`
- Use standard Django test framework: `python manage.py test`

## URL Structure and Routing
- **Root (`""`)**: patients app - Primary interface for patient management
- **`"users/"`**: User authentication, password reset, profile management  
- **`"video/"`**: Video file management and processing
- **`"admin/"`**: Django admin interface with custom branding

## File Upload System
- **Video files**: 2GB maximum, formats: mp4, mov, avi, mkv, webm
- **General uploads**: 100MB memory limit
- **Validation**: Through custom validators in `ndas/custom_codes/validators.py`
- **Storage**: Organized by date and type for efficient management
- **Processing**: FFmpeg integration for video processing tasks

## Key Dependencies and Integration
- **Django 4.2.16**: Latest LTS with security updates
- **Frontend**: AdminLTE, Bootstrap 4, Select2, Video.js, HTMX
- **Security**: django-csp, django-ratelimit, django-permissions-policy
- **File Processing**: FFmpeg, Pillow for image handling
- **PDF Generation**: ReportLab for medical reports
- **Production**: PostgreSQL, Redis, Celery, Gunicorn, WhiteNoise