# NDAS Project Documentation Index

> **Generated:** 2026-03-09 | **Scan Level:** Exhaustive | **Type:** Django Monolith (Backend + Web)

## Project Overview

- **Type:** Monolith (Django MVT)
- **Primary Language:** Python 3.x
- **Architecture:** MVT + Custom Middleware Stack
- **Description:** Medical system for patient records, video-based neurodevelopmental assessments, and evaluation workflows. Supports General Movement Assessment (GMA), HINE, CDIC, GPA, and Developmental Assessment workflows. Phase 2 adds multi-institution support and a cross-institution referral system.

---

## Quick Reference

- **Tech Stack:** Django 4.2.16 | PostgreSQL/SQLite | AdminLTE 3.2 | Bootstrap 4.6 | HTMX | Video.js
- **Entry Point:** `patients/urls.py` (root URL dispatcher via `ndas/urls.py`)
- **Architecture Pattern:** Django MVT Monolith with Security-First Middleware
- **Base Models:** `TimeStampedModel + UserTrackingMixin` (`ndas/custom_codes/Custom_abstract_class.py`)

---

## Django Apps

| App | URL Prefix | Purpose | Key Models |
|-----|-----------|---------|------------|
| `patients` | `` (root) | Patient records, all assessment types, attachments, bookmarks, search | `Patient`, `GMAssessment`, `CDICRecord`, `GeneralPaediatricAssessment`, `HINEAssessment`, `DevelopmentalAssessment`, `Attachment`, `Bookmark`, `IndicationsForGMA`, `DiagnosisList`, `Help` |
| `users` | `users/` | Authentication, user management, subscriptions, activity logging | `CustomUser`, `UserActivityLog`, `UserSession`, `DeveloperContacts`, `Subscription` |
| `video` | `video/` | Video upload, streaming, and management linked to patients | `Video` |
| `reports` | `reports/` | PDF and Excel report generation with anonymization support | `ReportTemplate`, `ReportConfig` |
| `problemlist` | `problems/` | Clinical problem tracking with action history | `Problem`, `ProblemAction` |
| `institution` | `institution/` | Phase 2 — multi-institution foundation, row-level data isolation | `Institution`, `PatientMoveLog` |
| `referral` | `referral/` | Phase 2 — cross-institution referral system and notifications | `ReferralSent`, `ReferralReceived`, `ReferralMessage`, `Notification` |

---

## Generated Documentation

| Document | Description |
|----------|-------------|
| [Project Overview](./project-overview.md) | High-level product description, user roles, feature scope |
| [Architecture](./architecture.md) | Middleware stack, security architecture, Phase 2 design decisions |
| [Source Tree Analysis](./source-tree-analysis.md) | Fully annotated directory tree with purpose of every file and directory |
| [Data Models](./data-models-main.md) | Model fields, relationships, and constraints for all apps |
| [API Contracts / URL Reference](./api-contracts-main.md) | All URL patterns, view signatures, HTTP methods |
| [Component Inventory](./component-inventory-main.md) | Template inventory, form inventory, reusable partials |
| [Development Guide](./development-guide.md) | Step-by-step workflow for adding features, running tests, deploying |
| [Custom Codes Reference](./custom-codes-reference.md) | Complete reference for ndas/custom_codes/ — all choices, validators, utilities, decorators |

---

## Getting Started

### Quick Start (Development)

```bash
# Windows
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Environment Variables

Create a `.env` file at the project root (see `env files/` for templates):

```bash
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (defaults to SQLite if omitted)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=ndas
DB_USER=user
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# Cache (defaults to LocMem if omitted)
REDIS_URL=redis://localhost:6379/0

# Security (required in production)
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### Running Tests

```bash
python manage.py test patients
python manage.py test users
python manage.py test institution
python manage.py test referral
```

---

## Key Conventions

### Model Convention (mandatory for every new model)

```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

class MyModel(TimeStampedModel, UserTrackingMixin):
    # Auto-provides: created_at, updated_at, added_by, last_edit_by
    pass
```

### View Convention

```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
def my_view(request, pk):
    obj = get_object_or_404(MyModel, id=pk)
    ...
```

### Template Convention

```django
{% extends 'src/base.html' %}
{% load static %}
{% block title %}Section - Action{% endblock %}
{% block main_content %}
<div class="container-fluid">{% csrf_token %}<!-- content --></div>
{% endblock %}
```

### Where Things Live

| What | Where |
|------|-------|
| TextChoices / IntegerChoices | `ndas/custom_codes/choice.py` |
| Field validators | `ndas/custom_codes/validators.py` |
| HTML sanitisation | `ndas/custom_codes/sanitization.py` |
| Utility functions | `ndas/custom_codes/custom_methods.py` |
| Enumerations | `ndas/custom_codes/ndas_enums.py` |
| Delete guards | `ndas/custom_codes/delete_helpers.py` |
| Error handler decorator | `ndas/custom_codes/error_handlers.py` |
| Delete modal template tag | `ndas/templatetags/delete_modal_tags.py` |
| Institution template tags | `institution/templatetags/institution_tags.py` |

---

## For AI-Assisted Development

When working on a new feature, consult in this order:

1. **Source Tree Analysis** — understand where files live before creating anything new
2. **Architecture** — confirm middleware, base patterns, and security requirements apply
3. **Data Models** — get exact field names and model relationships before writing queries
4. **API Contracts** — check existing URL names to avoid conflicts when adding new routes
5. **Component Inventory** — find available templates and UI patterns before writing new HTML
6. **Development Guide** — follow the step-by-step checklist for adding a feature

### Critical Field Names (avoid common errors)

| Field | Correct | Wrong |
|-------|---------|-------|
| Patient hospital ID | `patient.bht` | `patient.bht_number` |
| NNC number | `patient.nnc_no` | `patient.nnc_number` |
| Patient name | `patient.baby_name` | `patient.name` or `patient.patient_name` |
| Date of birth | `patient.dob_tob` | `patient.dob` or `patient.date_of_birth` |
| Gestational age (weeks) | `patient.pog_wks` | `patient.gestational_age_weeks` |
| Gestational age (days) | `patient.pog_days` | `patient.gestational_age_days` |
| Birth weight | `patient.birth_weight` | `patient.birth_weight_g` |
| Head circumference | `patient.hc` | `patient.head_circumference` |
| APGAR at 1 min | `patient.apgar_1` | `patient.apgar_1_min` |
| APGAR at 5 min | `patient.apgar_5` | `patient.apgar_5_min` |

### Security Rules That Must Not Be Broken

- Never reorder the middleware stack — `UserActivityMiddleware` must follow `AuthenticationMiddleware`
- Never skip `@login_required`, `@require_http_methods`, or `@ratelimit` on CRUD views
- Never use `.objects.get()` — always use `get_object_or_404()`
- Never add choices inline in a model — add to `ndas/custom_codes/choice.py`
- Never change Bootstrap version, AdminLTE version, or Font Awesome version
- Never store secrets in code — use `.env` / environment variables

### File Upload Limits

| Type | Max Size | Allowed Extensions |
|------|----------|--------------------|
| Video | 2 GB | mp4, mov, avi, mkv, webm |
| Image | 10 MB | jpg, jpeg, png, gif, bmp, webp |
| Document | 100 MB | doc, docx, txt, rtf, odt, pdf |
| Profile picture | 5 MB | (image extensions) |

### Rate Limiting

24 CRUD operations are protected:
- Create / edit views: `rate='10/m'`
- Delete views: `rate='5/m'`
- Key: `user_or_ip`

---

## Phase 2 Status (Multi-Institution)

Phase 2 apps (`institution/` and `referral/`) are present and partially active. Key architecture points:

- **Data isolation:** Row-level via `InstitutionScopedManager` (`institution/managers.py`); call `.for_institution(institution)` on querysets
- **Session context:** `InstitutionContextMiddleware` (`institution/middleware.py`) injects active institution from session; `institution/context_processors.py` exposes it to templates
- **Referral lifecycle:** `PENDING` → `REPLIED` → `CLOSED`; dual-record pattern (both institutions hold an immutable UUID-linked record)
- **Notifications:** HTMX polling via `notification_count_badge.html` partial; delivery target is within 120 seconds of trigger
- **Superadmin:** `is_superuser=True` users can access all institutions and the superadmin dashboard

Planning artifacts for Phase 2 are in `_bmad-output/planning-artifacts/`.
