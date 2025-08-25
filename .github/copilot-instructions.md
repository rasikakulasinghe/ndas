# NDAS (Neonatal Development Assessment System) - AI Coding Instructions

## Project Overview
NDAS is a Django-based medical system for tracking neonatal neurological development through video assessments, patient records, and clinical data management. Built with modern security practices and comprehensive audit trails.

## Architecture & Core Patterns

### Application Structure
- **Main Apps**: `patients/` (core medical data), `users/` (authentication/staff management)
- **Custom Codes**: `ndas/custom_codes/` contains reusable components:
  - `Custom_abstract_class.py`: `TimeStampedModel` & `UserTrackingMixin` base classes
  - `choice.py`: Django choices using TextChoices pattern
  - `ndas_enums.py`: Python enums for patient status (`PtStatus`)
  - `validators.py`: Custom field validators for medical data
  - `custom_methods.py`: Business logic utilities and file path handlers

### Data Model Conventions
All models inherit from audit-tracked base classes:
```python
class MyModel(TimeStampedModel, UserTrackingMixin):
    # Automatic: created_at, updated_at, added_by, last_edit_by fields
```

### Patient Status Workflow
Patient records follow this enum-based status flow:
```
NEW → DISCHARGED/DIAGNOSED → DX_GMA_NORMAL/ABNORMAL → DX_DA_NORMAL/ABNORMAL → DX_HINE
```
Use `getPatientList(PtStatus.ENUM_VALUE)` from `custom_methods.py` for filtered queries.

## Environment Setup

### Development Environment
```bash
# Virtual environment setup
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Environment variables (copy .env and modify)
cp .env.example .env  # Edit SECRET_KEY, DEBUG, ALLOWED_HOSTS

# Database setup
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### Security Stack
- **CSP**: Content Security Policy middleware active
- **Rate Limiting**: Built-in via `django-ratelimit`
- **Activity Tracking**: `UserActivityMiddleware` logs all user actions
- **File Validation**: Custom validators for uploads in `validators.py`
- **Session Security**: Enhanced session tracking via `UserSession` model

## Authentication & Authorization

### User Model & Roles
- Custom user model: `users.CustomUser` (extends AbstractUser)
- Position-based roles: Medical Officer, Consultant, Registrar, etc. (see `choice.py`)
- Use custom decorators: `@admin_required`, `@superuser_required` from `users.decorators`

### Session Management
- `UserActivityMiddleware` tracks all user activity with IP/device logging
- `UserSession` model for comprehensive session management
- Activity logging via `users.utils.log_user_activity()`

## Frontend Architecture

### Template System
- **Base**: `templates/src/base.html` → AdminLTE3 framework
- **Structure**: All pages extend base with sidebar navigation
- **Components**: Modular includes in `templates/src/` (navbar, sidebar, messages)
- **UI Framework**: AdminLTE3 + Bootstrap 4 + jQuery + Video.js

### JavaScript Architecture
- `static/js/video-manager.js`: Unified Video.js management with error handling
- `static/js/rotate.js`: Video rotation/zoom functionality for medical videos
- `static/js/main.js`: Core initialization and utilities
- **Pattern**: All video components use Video.js with medical-specific plugins

## File & Media Management

### Upload Organization
- **Video Files**: Organized by year via `get_video_path_file_name()` in `custom_methods.py`
- **Attachments**: Patient photos/PDFs via `get_attachment_path_file_name()`
- **Processing**: Video compression and thumbnail generation
- **Security**: File type validation in `validators.py`, size limits enforced

### Video Processing Pipeline
1. Upload validation (`validate_video_file`)
2. Compressed version generation (`get_compressed_video_path`)
3. Thumbnail creation (`get_video_thumbnail_path`)
4. Processing status tracking in Video model

## URL Architecture

### Status-Based Patient Management
URLs follow patient status hierarchy in `patients/urls.py`:
- `/manager/patient/new` → NEW status patients
- `/manager/patient/diagnosed/gma/normal` → GMA normal diagnosis
- `/manager/patient/diagnosed/hine` → HINE assessment complete

### Medical Assessment Routes
- Video operations: `/video/add/<pk>/`, `/video/view/<f_id>/`
- Assessments: GMA, HINE, DA (Developmental Assessment)
- Attachments: Patient photos, PDFs, medical documents

## Database Patterns

### Core Medical Models
- **Patient**: Central record with POG (Period of Gestation) tracking
- **Video**: Medical video files with processing metadata
- **GMAssessment**: General Movement Assessment data
- **HINEAssessment**: Hammersmith Infant Neurological Examination
- **DevelopmentalAssessment**: Multi-domain development tracking
- **CDICRecord**: Communication Development Inventory records

### Query Utilities
Use functions from `custom_methods.py`:
- `get_gma_diagnosis_data()`: Aggregate GMA diagnosis statistics
- `get_all_diagnosis_data()`: Cross-assessment diagnosis summary
- `get_userStats()`: System-wide statistics for dashboard

## Production Considerations

### Security Requirements
- Environment variables via `django-environ` (see `.env`)
- WhiteNoise for static file serving
- Database migrations with proper indexes
- User activity audit trails mandatory

### Performance Patterns
- Video file compression for web delivery
- Organized media storage by year
- Database indexes on status fields and timestamps
- Efficient query patterns in `custom_methods.py`

## Development Tasks

### Adding Assessment Types
1. Create model inheriting `TimeStampedModel` + `UserTrackingMixin`
2. Add choices to `choice.py` if needed
3. Update status enum in `ndas_enums.py`
4. Create corresponding views following status-based URL pattern
5. Add AdminLTE3-compliant templates

### Medical Data Validation
- Use validators from `ndas.custom_codes.validators`
- POG (Period of Gestation) validation: `validate_pog_weeks`, `validate_pog_days`
- APGAR scores: `validate_apgar_score`
- Birth weight: `validate_birth_weight`

## Critical Files Reference
- `patients/models.py`: Core medical data models (2900+ lines)
- `ndas/custom_codes/choice.py`: All dropdown/choice definitions
- `ndas/settings.py`: Security middleware stack configuration
- `static/js/video-manager.js`: Video.js medical video integration
- `users/middleware.py`: Activity tracking implementation
