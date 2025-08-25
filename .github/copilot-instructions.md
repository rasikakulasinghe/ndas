# NDAS (Neonatal Development Assessment System) - AI Coding Instructions

## Project Overview
NDAS is a Django-based medical system for tracking neonatal neurological development through video assessments, patient records, and clinical data management.

## Architecture & Core Patterns

### Application Structure
- **Main Apps**: `patients/` (core medical data), `users/` (authentication/staff management)
- **Custom Codes**: `ndas/custom_codes/` contains reusable components:
  - `Custom_abstract_class.py`: `TimeStampedModel` & `UserTrackingMixin` base classes
  - `choice.py`: Django choices using TextChoices pattern
  - `ndas_enums.py`: Python enums for patient status (`PtStatus`)
  - `validators.py`: Custom field validators for medical data

### Data Model Conventions
```python
# All models inherit from these base classes
class MyModel(TimeStampedModel, UserTrackingMixin):
    # Automatic created_at, updated_at, added_by, last_edit_by fields
```

### Patient Status Workflow
Patient records follow this enum-based status flow:
```
NEW → DISCHARGED/DIAGNOSED → DX_GMA_NORMAL/ABNORMAL → DX_DA_NORMAL/ABNORMAL → DX_HINE
```
Use `getPatientList(PtStatus.ENUM_VALUE)` from `custom_methods.py` for filtered queries.

## Authentication & Authorization

### User Model
- Custom user model: `users.CustomUser` (extends AbstractUser)
- Position-based roles: Medical Officer, Consultant, Registrar, etc.
- Use custom decorators: `@admin_required`, `@superuser_required`

### Session Management
- `UserActivityMiddleware` tracks all user activity
- `UserSession` model for session management
- Activity logging via `users.utils.log_user_activity()`

## Frontend Architecture

### Template System
- **Base**: `templates/src/base.html` → AdminLTE3 framework
- **Structure**: All pages extend base template with sidebar navigation
- **Components**: Modular includes in `templates/src/` (navbar, sidebar, messages)
- **UI Framework**: AdminLTE3 + Bootstrap 4 + jQuery + Video.js for media

### JavaScript Organization
- `static/js/main.js`: Core initialization
- `static/js/video-manager.js`: Video.js integration for medical video playback
- `static/js/rotate.js`: Video rotation functionality
- Use Video.js for all video components with rotation/zoom features

## Development Workflows

### Database Operations
```bash
# Run migrations (common workflow)
python manage.py makemigrations
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser
```

### Testing Patient Data
- Use TESTS directory for all test cases
- Use fixtures or factory methods in `custom_methods.py`
- Patient test data should include proper POG (Period of Gestation) values
- Video files must match `VIDEO_FORMATS` choices in `choice.py`

## Key Integration Points

### File Upload Handling
- Patient attachments: Photos, PDFs, Videos via `Attachment` model
- Video processing with size/type validation in `validators.py`
- Storage: `MEDIA_ROOT` with organized subdirectories by year

### Security Features
- CSP (Content Security Policy) middleware enabled
- Rate limiting via `django-ratelimit`
- File type validation for all uploads
- User activity logging for audit trails

### Custom Form Patterns
```python
# Forms follow this pattern with custom validation
class PatientForm(forms.ModelForm):
    def clean_field_name(self):
        # Use validators from ndas.custom_codes.validators
        return validated_data
```

## URL Patterns
- **Root**: `/` → patients app (dashboard)
- **Admin**: `/admin/` → Django admin
- **Users**: `/users/` → authentication flows
- **Patient Management**: Hierarchical status-based URLs in `patients/urls.py`

## Critical Files for Context
- `patients/models.py`: Core medical data models (2900+ lines)
- `ndas/custom_codes/choice.py`: All dropdown/choice definitions
- `ndas/settings.py`: Django configuration with security middlewares
- `templates/src/base.html`: UI layout foundation

## Common Tasks
1. **Adding new assessment types**: Extend models with `TimeStampedModel` + `UserTrackingMixin`
2. **Status transitions**: Update `ndas_enums.py` and corresponding view logic
3. **New user roles**: Modify `choice.py` Position choices and decorator logic
4. **UI components**: Follow AdminLTE3 patterns in existing templates

## Debug & Logging
- Debug logs in `debug.log`
- User activity tracked in `UserActivityLog` model
- Video processing errors logged to Django logger
