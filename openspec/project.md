# Project Context

OpenSpec project conventions for NDAS. For full documentation, see `CLAUDE.md`.

**Last Updated:** 2025-12-25

## Purpose

**NDAS** - Django medical system for patient records and neurodevelopmental assessments.

**Stack:** Django 4.2.16 | PostgreSQL/SQLite | AdminLTE 3.2 | Bootstrap 4.6

## Project Conventions

### Code Style

- **Python**: snake_case (functions, variables), PascalCase (classes), UPPER_SNAKE_CASE (constants)
- **Templates**: lowercase with hyphens, naming: `manager.html`, `add.html`, `edit.html`, `view.html`
- **URLs**: kebab-case in paths

### Architecture Patterns

All models inherit from both base classes:
```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

class MyModel(TimeStampedModel, UserTrackingMixin):
    pass
```

**Key Rules:**
- Choices in `ndas/custom_codes/choice.py`
- Validators in `ndas/custom_codes/validators.py`
- Utilities in `ndas/custom_codes/custom_methods.py`
- Use `db_index=True` for searchable fields
- Use `upload_to="path/%Y/%m/"` for file fields

### Testing

```bash
python manage.py test                    # All tests
python manage.py test patients           # Specific app
npx playwright test                      # E2E tests
```

### Git Workflow

- Main branch: `main`
- Feature branches: `feature/descriptive-name`
- Descriptive commit messages

## Domain Context

**Medical Data:**
- Patient identifiers: BHT, NNC, PTC, PC, PIN
- Birth weight: 300g-8000g (POG-specific validation available)
- APGAR scores: 0-10
- Gestational age: 20-44 weeks + 0-6 days

**Assessment Types:** GPA, HINE, CDIC, Developmental

## Constraints

**Technical:**
- Windows development environment
- SQLite (dev) / PostgreSQL (prod)
- Video files: 2GB max

**Security (HIPAA-aware):**
- Login required for patient data
- CSRF protection on all forms
- Rate limiting on CRUD operations
- File upload validation (MIME type, size)
- Session timeout: 1 hour

## External Dependencies

**Required:** FFmpeg (video processing)
**Production:** Redis (cache), PostgreSQL, Celery (optional)
**CDN:** AdminLTE, Bootstrap, Font Awesome, jQuery, HTMX, Video.js
