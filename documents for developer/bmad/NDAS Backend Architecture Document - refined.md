Based on a thorough analysis of the provided architecture document, here is a refined and optimized version. The original document is well-structured, but this revision addresses areas of ambiguity, adds critical specificity, and integrates the recommendations from the self-assessment directly into the architecture, making it a more actionable and robust blueprint for development.

-----

# NDAS Backend Architecture (Version 2.0)

## 1\. Introduction

This document outlines the refined backend architecture for the NDAS project. Its primary goal is to provide a clear, actionable, and optimized blueprint for development, ensuring all enhancements are secure, scalable, and maintainable. This version supersedes all previous drafts and incorporates key decisions based on a brownfield analysis of the existing system.

**Relationship to Frontend Architecture:**
This document is the definitive source for the core technology stack and backend patterns. Any frontend architecture MUST align with the choices specified herein.

### Change Log

| Date | Version | Description | Author |
| :--- | :--- | :--- | :--- |
| 2025-08-19 | 1.0 | Initial architecture draft based on brownfield analysis. | Winston |
| 2025-08-19 | 2.0 | Refined architecture with enhanced specificity in deployment, security, and file handling. Integrated checklist recommendations. | Gemini |

### Project Foundation

This project enhances an existing, standard Django application. There is no starter template. The current structure serves as the foundation, and all new development will align with the patterns and technologies outlined in this document, with a focus on progressive refactoring and modernization.

-----

## 2\. High-Level Architecture

### Technical Summary

The architecture is a **production-hardened monolithic Django application**. The strategic focus is to evolve the existing monolith by addressing critical security vulnerabilities, optimizing performance, and ensuring stability. This will be achieved by migrating to a robust PostgreSQL database, introducing a Redis cache, implementing a clear separation of concerns with a service layer, and securing file handling with dedicated object storage.

### High-Level Overview

  * **Architectural Style**: **Monolithic**. This approach is maintained to simplify development, testing, and deployment for the core application.
  * **Repository Structure**: **Monorepo**. A single repository will house the entire Django project.
  * **Service Architecture**: A single Django service logically partitioned into distinct apps (`users`, `patients`, `clinical_records`).
  * **Primary Data Flow**: User requests are received by the Gunicorn server and passed to the Django application. Django's URL router directs requests to views, which orchestrate business logic via a service layer. The service layer interacts with the database (via repositories) and other resources. Finally, views render HTML templates to the user.

### High-Level Project Diagram

```mermaid
graph TD
    A[User's Browser] --> B{Gunicorn WSGI Server};
    B --> C[Django Application (NDAS)];

    subgraph "Django Application Logic"
        C -- Reads/Writes --> D[Database (PostgreSQL)];
        C -- Caches Data --> F[Cache (Redis)];
        C -- Serves Static CSS/JS --> G[Static Assets (WhiteNoise)];
        C -- Handles Media Uploads/Downloads --> E[File Storage (Cloud Object Storage)];
    end

    G --> A;
    E --> A;
    C --> A;

    subgraph "Containerized Environment (Docker)"
        B
        C
        F
    end
```

### Architectural and Design Patterns

  * **Monolithic Architecture**: Intentionally chosen to focus development efforts on feature enhancement and refactoring rather than managing a distributed system.
  * **Repository Pattern**: This pattern will be adopted to abstract data access logic. It decouples the business logic from the ORM, centralizes query logic, and improves testability by allowing data access to be easily mocked.
  * **Explicit Service Layer**: A logical layer will be introduced to contain business logic, preventing "fat views." This promotes cleaner, more reusable code and separates the concerns of HTTP handling from core application processes.

-----

## 3\. Tech Stack

### Cloud Infrastructure

  * **Provider**: To be deployed on a standard cloud provider (e.g., AWS, Google Cloud, Azure).
  * **Key Services**:
      * **Compute**: Virtual Private Server (e.g., EC2, Compute Engine) for running the Dockerized application.
      * **Database**: Managed PostgreSQL Database (e.g., RDS, Cloud SQL).
      * **Caching**: Managed Redis Instance (e.g., ElastiCache, Memorystore).
      * **File Storage**: Object Storage for media files (e.g., S3, Google Cloud Storage).
  * **Deployment Regions**: To be determined based on primary user geography to minimize latency.

### Technology Stack Table

| Category | Technology | Version | Purpose | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **Runtime** | Python | 3.10 | Core application language | Provides stability and maintains consistency with the existing setup. |
| **Framework** | Django | 4.2.16 | Web framework | Uses the latest security-patched version of the existing framework. |
| **WSGI Server** | Gunicorn | 23.0.0 | Serves the Django application | A battle-tested, industry-standard server for Python web apps. |
| **Database**| **PostgreSQL**| 13+ | Production-grade relational database | **Critical Upgrade**: Mitigates the severe security and performance risks of using SQLite in production. This is an immediate priority. |
| **Caching** | **Redis** | 5.0+ | In-memory data store | **New Addition**: Improves application performance by caching expensive queries and computed results, as recommended in the performance analysis. |
| **Static Files**| WhiteNoise | 6.9.0 | Serves compiled static files | An efficient and simple solution for serving static assets (CSS, JS) directly from the application container without needing a separate web server. |
| **Login Tracking** | django-user-agents | 0.4.0 | Parses User-Agent strings | Leveraged for login auditing to track user device types. |
| **Containerization**| Docker | Latest | Container runtime | Ensures a consistent and reproducible deployment environment. |

-----

## 4\. Data Models

Data models will be managed via Django's ORM. Key entities include:

  * **`User` (extends `users.CustomUser`)**: Represents all system users. Will be enhanced with fields for role-based access control (RBAC) and detailed login auditing (e.g., `last_login_ip`, `last_login_device`).
  * **`Patient` (based on `patients.Patient`)**: The central model for patient information. **Database indexes will be added** to key search fields (e.g., name, patient ID) to improve query performance.
  * **`ClinicalRecord` (New Model)**: A new structured model for storing clinical data from general pediatric visits, linked to the `Patient` model.

-----

## 5\. Components

The application is logically structured into the following Django apps:

  * **`users` App**: Manages user authentication, registration, password management, RBAC, and login auditing.
  * **`patients` App**: The core clinical component for managing patient data, assessments, and associated media files (videos, attachments). This app will interface directly with the object storage service.
  * **`clinical_records` App (New)**: Manages structured records for general clinic visits, linking patients to their clinical data.

### Component Interaction Diagram

```mermaid
graph TD
    subgraph "Django Monolith"
        A(users App)
        B(patients App)
        C(clinical_records App)
    end

    D[Database (PostgreSQL)]
    E[File Storage (Object Storage)]

    A -- Manages User Records --> D
    B -- Manages Patient Records --> D
    C -- Manages Clinical Records --> D

    B -- Stores/Retrieves Media Files --> E

    A -- "Authenticates/Authorizes Users for" --> B
    A -- "Authenticates/Authorizes Users for" --> C
    C -- "Links Records to" --> B
```

-----

## 6\. Infrastructure and Deployment

  * **Containerization**: The application, including Gunicorn and Django, will be containerized using Docker.
  * **CI/CD Pipeline**: A pipeline will be established (e.g., using GitHub Actions, Jenkins) to automate testing, building, and deploying the application.
  * **Deployment Strategy**: A **rolling deployment** strategy will be used to ensure zero-downtime updates.
  * **Environments**: Separate environments for development, staging, and production will be maintained to ensure proper testing before release.
  * **Configuration Management**: Environment variables will be used for all configuration, including database credentials and secret keys, to avoid hardcoding sensitive information.

-----

## 7\. Security

Security is a top priority. The following measures are **mandatory**:

  * **CSRF Protection**: All instances of the `@csrf_exempt` decorator **must be removed** and replaced with proper CSRF token handling. This is an immediate priority.
  * **Authentication**: Secure, password-based authentication will be enforced. All password hashing will use Django's default (PBKDF2) or stronger algorithms.
  * **Secrets Management**: The `SECRET_KEY` and other sensitive credentials will be managed via environment variables or a secrets management service (e.g., AWS Secrets Manager, HashiCorp Vault).
  * **Security Headers**: The application will be configured to return security-enhancing HTTP headers, including:
      * `Strict-Transport-Security (HSTS)`
      * `X-Content-Type-Options`
      * `X-Frame-Options`
      * `Content-Security-Policy (CSP)`
  * **Input Validation**: All incoming data will be validated and sanitized using Django Forms or serializers to prevent injection attacks.

-----

## 8\. Error Handling and Logging

  * **Centralized Exception Handling**: A custom middleware will be implemented to catch unhandled exceptions.
  * **Standardized Error Responses**: For API-like requests (if any) or AJAX calls, the middleware will return a standardized JSON error response:
    ```json
    {
      "status": "error",
      "error_code": "internal_server_error",
      "message": "An unexpected error occurred. Please try again later."
    }
    ```
  * **Logging**: A structured logging format (e.g., JSON) will be used. All exceptions, along with the request context, will be logged to facilitate debugging.

-----

## 9\. Coding and Testing Standards

  * **Coding Standards**: All code must adhere to **PEP 8**.
      * **Formatting**: **Black** will be used for automated code formatting.
      * **Linting**: **Flake8** will be used to enforce code quality and identify potential errors.
      * These checks will be integrated into the CI/CD pipeline to reject non-compliant code.
  * **Test Strategy**: A multi-layered testing strategy is required.
      * **Unit Tests**: For testing individual functions and classes in isolation (using `pytest`).
      * **Integration Tests**: For testing interactions between components (e.g., service layer to repository).
      * **End-to-End (E2E) Tests**: For simulating user workflows (e.g., using Selenium or Playwright).
      * **Code Coverage**: A minimum target of **80% code coverage** will be enforced via the CI/CD pipeline.