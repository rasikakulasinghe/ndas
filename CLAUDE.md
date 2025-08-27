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

### Environment Setup
- Virtual environment is in `venv/` directory
- Activate with: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Unix)
- Install dependencies: `pip install -r requirements.txt`

## Architecture Overview

### Core Structure
This is a Django-based **Neurodevelopmental Assessment System (NDAS)** that manages patient records, video assessments, and user authentication.

**Main Django Apps:**
- `patients/` - Patient management, assessments, and medical records
- `video/` - Video file handling, processing, and metadata management  
- `users/` - Custom user authentication, permissions, and activity tracking
- `ndas/` - Project settings, URLs, and core configuration

### Key Models and Relationships
- **Patient**: Core patient model with medical history, demographics, assessments
- **Video**: Video files linked to patients with processing status and metadata
- **CustomUser**: Extended Django user model with profile and activity tracking
- **GMAssessment**: Patient assessment records with rich text fields
- **Attachment**: File attachments for patients with access control

### Custom Code Organization
- `ndas/custom_codes/` contains reusable components:
  - `Custom_abstract_class.py` - Base models with timestamps and user tracking
  - `choice.py` - Predefined choices for form fields and models
  - `validators.py` - Custom field validators
  - `custom_methods.py` - Utility functions

### Templates and Static Files
- Templates in `templates/` organized by app (patients/, video/, users/)
- Static files in `static/` with CSS, JS, and third-party plugins
- Uses WhiteNoise for static file serving in production
- CKEditor integration for rich text editing

### Security Features
- Content Security Policy (CSP) middleware configured
- File upload validation and size limits
- User activity tracking and session management
- CSRF protection and secure cookie settings

### Database and Media
- SQLite database (`db.sqlite3`) for development
- Media files organized in `media/` by type (videos/, profile_pictures/, etc.)
- Video files uploaded to `media/videos/%Y/%m/` structure

### Key Configuration
- Environment variables managed via `.env` file with `django-environ`
- Email configuration for file-based backend in development
- Custom admin site branding and headers
- Session timeout set to 1 hour with browser close expiry

## Testing
- Test files exist but are minimal: `video/tests.py`, `users/tests.py`
- Use standard Django test framework: `python manage.py test`

## File Upload Limits
- Video files: 2GB maximum, formats: mp4, mov, avi, mkv, webm
- General uploads: 100MB memory limit
- Attachment validation through custom validators