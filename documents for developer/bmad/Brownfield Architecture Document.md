# NDAS Project Brownfield Architecture Document

## Introduction

This document captures the CURRENT STATE of the NDAS (Neurodevelopmental Assessment System) codebase, including technical debt, workarounds, and real-world patterns. It serves as a reference for AI agents working on enhancements.

### Document Scope

Comprehensive documentation of the entire system.

### Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2025-08-19 | 1.0 | Initial brownfield analysis | NDAS Project |

-----

## Quick Reference - Key Files and Entry Points

### Critical Files for Understanding the System

  * **Main Entry**: `manage.py`
  * **Configuration**: `ndas/settings.py`
  * **Core Business Logic**: `patients/views.py`, `users/views.py`
  * **API Definitions**: `ndas/urls.py`, `patients/urls.py`, `users/urls.py`
  * **Database Models**: `patients/models.py`, `users/models.py`
  * **Key Algorithms**: Custom methods in `ndas/custom_codes/custom_methods.py`

-----

## High Level Architecture

### Technical Summary

The Neurodevelopmental Assessment System (NDAS) is a monolithic Django application designed for managing patient data, assessments, and related medical records. The system is containerized using Docker for deployment.

### Actual Tech Stack (from requirements.txt)

| Category | Technology | Version | Notes |
| --- | --- | --- | --- |
| Runtime | Python | 3.10-buster | Defined in Dockerfile |
| Framework | Django | 4.2.16 | Updated for security patches |
| WSGI Server | Gunicorn | 23.0.0 | |
| Database | SQLite | 3 | Default for development, not suitable for production |
| Static Files | WhiteNoise | 6.9.0 | |
| Rich Text Editor | django-richtextfield | 1.6.1 | |

### Repository Structure Reality Check

  * **Type**: Monolith
  * **Package Manager**: pip
  * **Notable**: The project is structured into two main Django apps: `users` and `patients`. There's also a `custom_codes` directory for shared utilities.

-----

## Source Tree and Module Organization

### Project Structure (Actual)

```text
ndas/
├── ndas/                  # Main Django project
│   ├── settings.py        # Project settings
│   ├── urls.py            # Root URL configuration
│   └── wsgi.py            # WSGI entry point
├── patients/              # Patient management app
│   ├── models.py          # Patient-related models
│   ├── views.py           # Patient-related views
│   └── urls.py            # Patient app URLs
├── users/                 # User management app
│   ├── models.py          # Custom user model
│   ├── views.py           # User-related views
│   └── urls.py            # User app URLs
├── static/                # Static files (CSS, JS, images)
├── templates/             # HTML templates
├── manage.py              # Django management script
└── requirements.txt       # Python dependencies
```

### Key Modules and Their Purpose

  * **User Management**: `users` app - Handles user authentication, profiles, and permissions.
  * **Patient Records**: `patients` app - Manages patient information, assessments (GMA, HINE, etc.), videos, and other medical records.
  * **Custom Utilities**: `ndas/custom_codes` - Contains custom choices, methods, and validators used across the application.

-----

## Data Models and APIs

### Data Models

  * **User Model**: See `users/models.py` for the `CustomUser` model.
  * **Patient Model**: See `patients/models.py` for the `Patient` model and related assessment models.

### API Specifications

The project uses Django's URL routing system. Refer to `ndas/urls.py`, `patients/urls.py`, and `users/urls.py` for the URL patterns.

-----

## Technical Debt and Known Issues

### Critical Technical Debt

1.  **SQLite in Production**: The project is configured to use SQLite, which is not suitable for a production environment.
2.  **CSRF Exemptions**: The `@csrf_exempt` decorator is used in `patients/views.py`, which is a security risk.
3.  **Lack of Input Validation**: The views directly access `request.POST` data without proper validation, which could lead to errors and security vulnerabilities.
4.  **No Automated Testing**: There are no automated tests for the application.

### Workarounds and Gotchas

  * The `moviepy` library is commented out in `patients/views.py`, indicating a potential issue with video processing.

-----

## Integration Points and External Dependencies

The project does not have any significant external service integrations.

-----

## Development and Deployment

### Local Development Setup

The project can be run locally using Docker.

### Build and Deployment Process

  * **Build Command**: `docker-compose build`
  * **Deployment**: The `docker-compose.yml` file defines the services for deployment.
  * **Environments**: The project uses a `.env` file for environment variables.

-----

## Appendix - Useful Commands and Scripts

### Frequently Used Commands

```bash
# Run the application
docker-compose up

# Run Django management commands
docker-compose run app python manage.py <command>
```