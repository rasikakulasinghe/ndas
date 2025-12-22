"""
Security middleware for additional security headers and validation.

Provides two middleware classes:
1. AdditionalSecurityHeadersMiddleware - Adds additional security headers to all responses
2. SecurityHeadersValidationMiddleware - Validates required security headers are present (production only)
"""

import logging
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class AdditionalSecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add additional security headers to all HTTP responses.

    Adds the following headers:
    - Referrer-Policy: Controls referrer information sent with requests
    - Cross-Origin-Opener-Policy: Prevents window.opener access from cross-origin
    - X-Permitted-Cross-Domain-Policies: Restricts Flash/PDF cross-domain policies

    Note: Other security headers are handled by Django's SecurityMiddleware:
    - X-Content-Type-Options (SECURE_CONTENT_TYPE_NOSNIFF)
    - X-Frame-Options (handled by XFrameOptionsMiddleware)
    - Strict-Transport-Security (SECURE_HSTS_SECONDS)
    """

    def process_response(self, request, response):
        """
        Add security headers to the response.

        Args:
            request: HttpRequest object
            response: HttpResponse object

        Returns:
            HttpResponse with additional security headers
        """
        # Referrer-Policy - already set in settings.py via SECURE_REFERRER_POLICY
        # but we ensure it's present on all responses
        if 'Referrer-Policy' not in response:
            response['Referrer-Policy'] = getattr(
                settings,
                'SECURE_REFERRER_POLICY',
                'strict-origin-when-cross-origin'
            )

        # Cross-Origin-Opener-Policy - already set in settings.py via SECURE_CROSS_ORIGIN_OPENER_POLICY
        # but we ensure it's present on all responses
        if 'Cross-Origin-Opener-Policy' not in response:
            response['Cross-Origin-Opener-Policy'] = getattr(
                settings,
                'SECURE_CROSS_ORIGIN_OPENER_POLICY',
                'same-origin'
            )

        # X-Permitted-Cross-Domain-Policies - restrict cross-domain policy files
        # Prevents Flash and PDF files from loading data from this domain
        if 'X-Permitted-Cross-Domain-Policies' not in response:
            response['X-Permitted-Cross-Domain-Policies'] = 'none'

        # Permissions-Policy - restrict browser features
        # Replaces Feature-Policy (deprecated)
        if 'Permissions-Policy' not in response:
            # Disable potentially dangerous features
            response['Permissions-Policy'] = (
                'geolocation=(), '
                'microphone=(), '
                'camera=(), '
                'payment=(), '
                'usb=(), '
                'magnetometer=(), '
                'gyroscope=(), '
                'accelerometer=()'
            )

        return response


class SecurityHeadersValidationMiddleware(MiddlewareMixin):
    """
    Middleware to validate that required security headers are present on responses.

    This middleware should ONLY be enabled in production (DEBUG=False) to catch
    configuration issues that could lead to security vulnerabilities.

    Validates the presence of:
    - X-Content-Type-Options (prevents MIME-sniffing)
    - X-Frame-Options (prevents clickjacking)
    - Content-Security-Policy (prevents XSS)
    - Strict-Transport-Security (HTTPS enforcement - when SSL is enabled)

    Logs warnings when required headers are missing.
    """

    # Required headers for all responses
    REQUIRED_HEADERS = [
        'X-Content-Type-Options',
        'X-Frame-Options',
        'Content-Security-Policy',
    ]

    # Required headers when SSL is enabled
    SSL_REQUIRED_HEADERS = [
        'Strict-Transport-Security',
    ]

    def process_response(self, request, response):
        """
        Validate security headers on the response.

        Args:
            request: HttpRequest object
            response: HttpResponse object

        Returns:
            HttpResponse (unchanged - only logs warnings)
        """
        # Only validate in production
        if settings.DEBUG:
            return response

        # Skip validation for specific paths (static files, media, admin)
        if any(request.path.startswith(path) for path in ['/static/', '/media/', '/admin/']):
            return response

        # Skip validation for non-HTML responses
        content_type = response.get('Content-Type', '')
        if not content_type.startswith('text/html'):
            return response

        # Check required headers
        missing_headers = []
        for header in self.REQUIRED_HEADERS:
            if header not in response:
                missing_headers.append(header)

        # Check SSL-required headers if SSL is enabled
        if getattr(settings, 'SECURE_SSL_REDIRECT', False):
            for header in self.SSL_REQUIRED_HEADERS:
                if header not in response:
                    missing_headers.append(header)

        # Log warnings for missing headers
        if missing_headers:
            logger.warning(
                f"Security headers missing on {request.path}: {', '.join(missing_headers)}. "
                f"Request: {request.method} {request.path}, "
                f"User: {request.user.username if request.user.is_authenticated else 'Anonymous'}"
            )

        return response
