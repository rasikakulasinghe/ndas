# Brownfield Enhancement PRD: NDAS Security and Performance Overhaul

## 1. Introduction

This document outlines the requirements for a brownfield enhancement of the Neurodevelopmental Assessment System (NDAS). The primary goal of this initiative is to address critical security vulnerabilities and improve the overall performance and stability of the application, transforming it from a development prototype to a production-ready system.

## 2. Problem Statement

The NDAS application, in its current state, contains several critical security flaws and performance bottlenecks that make it unsuitable for a production environment. These issues pose a significant risk to data integrity, user privacy, and system stability. The application needs a comprehensive overhaul to address these vulnerabilities and ensure it is a secure, reliable, and scalable platform for medical professionals.

## 3. Goals and Objectives

### 3.1. Goals

* **Enhance Security:** Remediate all critical security vulnerabilities to protect sensitive patient data and prevent unauthorized access.
* **Improve Performance:** Optimize the application's performance to ensure a smooth and responsive user experience, even with a growing dataset.
* **Increase Stability:** Improve the overall stability and reliability of the application to ensure it is suitable for a production environment.

### 3.2. Objectives

* Secure the application against common web vulnerabilities, including Cross-Site Scripting (XSS), Cross-Site Request Forgery (CSRF), and SQL injection.
* Implement proper security headers and cookie settings.
* Optimize database queries to reduce load times and prevent bottlenecks.
* Implement a caching strategy to improve application performance.
* Migrate the database to a production-grade system.
* Establish a secure and efficient development and deployment workflow.

## 4. User Stories

### 4.1. Security Epics

**Epic 1: Secure Application Configuration**

* **As a system administrator,** I want the `SECRET_KEY` to be managed securely so that it is not exposed in version control.
* **As a system administrator,** I want `DEBUG` mode to be disabled in production so that sensitive information is not exposed to end-users.
* **As a system administrator,** I want the application to use a production-grade database so that the data is stored securely and reliably.

**Epic 2: Implement Application-Level Security**

* **As a developer,** I want to implement security headers to protect against common web vulnerabilities.
* **As a developer,** I want to remove all instances of `@csrf_exempt` and implement proper CSRF protection to prevent cross-site request forgery attacks.
* **As a developer,** I want to validate all user input to prevent injection attacks and ensure data integrity.
* **As a developer,** I want to implement secure file upload validation to prevent malicious file uploads.

### 4.2. Performance Epics

**Epic 3: Optimize Database Performance**

* **As a developer,** I want to optimize database queries using `select_related` and `prefetch_related` to reduce the number of queries and improve page load times.
* **As a developer,** I want to add database indexes to frequently queried fields to speed up data retrieval.
* **As a developer,** I want to implement a caching strategy to reduce database load and improve application responsiveness.

**Epic 4: Improve File Handling**

* **As a developer,** I want to implement chunked file processing for large file uploads to prevent server timeouts and improve the user experience.

## 5. Technical Requirements

### 5.1. Security

* The `SECRET_KEY` must be loaded from an environment variable and the `.env` file must be added to `.gitignore`.
* The `DEBUG` setting must be set to `False` in production environments.
* The application must be migrated from SQLite to a production-grade database such as PostgreSQL.
* The following security headers must be implemented in `ndas/settings.py`:
    * `SECURE_BROWSER_XSS_FILTER = True`
    * `SECURE_CONTENT_TYPE_NOSNIFF = True`
    * `SECURE_HSTS_SECONDS = 31536000`
    * `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
    * `SECURE_HSTS_PRELOAD = True`
    * `X_FRAME_OPTIONS = 'DENY'`
    * `SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'`
* All instances of the `@csrf_exempt` decorator must be removed and replaced with proper CSRF protection.
* All user input must be validated using Django forms or serializers.
* File uploads must be validated for file type, size, and content.

### 5.2. Performance

* All Django QuerySets must be reviewed and optimized using `select_related` and `prefetch_related` where appropriate to address N+1 query problems.
* Database indexes must be added to the following fields in the `Patient` model: `bht`, `nnc_no`, `baby_name`, `mother_name`, `added_on`, and `dob_tob`.
* A caching backend such as Redis must be implemented and configured in `ndas/settings.py`.
* Large file uploads, particularly videos, must be handled in chunks to avoid memory issues.

## 6. Success Metrics

* All critical security vulnerabilities identified in `security improvments.md` are addressed.
* The application achieves a passing grade on a security header scan (e.g., securityheaders.com).
* Page load times for the main dashboard and patient list are reduced by at least 50%.
* The application can handle at least 50 concurrent users without significant performance degradation.