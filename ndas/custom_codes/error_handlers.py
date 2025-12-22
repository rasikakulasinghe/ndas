"""
Standardized error handling decorators and utilities for NDAS views.

Provides consistent error handling, logging, and user-friendly error messages
across all views in the application.
"""

import logging
from functools import wraps
from django.shortcuts import redirect, render
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError, PermissionDenied
from django.db import IntegrityError
from django.http import Http404

logger = logging.getLogger(__name__)


def handle_view_errors(redirect_url=None, error_message=None, render_template=None):
    """
    Decorator to handle common view errors with consistent logging and user feedback.

    Catches and handles:
        - ObjectDoesNotExist: 404 errors with user-friendly message
        - ValidationError: Form validation errors
        - IntegrityError: Database constraint violations
        - PermissionDenied: Authorization errors
        - Generic Exception: Unexpected errors

    Args:
        redirect_url (str, optional): URL name to redirect to on error.
                                       If None, re-renders current template.
        error_message (str, optional): Custom error message for users.
                                        Defaults to error-specific messages.
        render_template (str, optional): Template to render on error if not redirecting.

    Returns:
        function: Decorated view function with error handling

    Example:
        @handle_view_errors(redirect_url='patient-manager',
                           error_message='Error processing patient')
        def patient_edit(request, pk):
            patient = Patient.objects.get(pk=pk)
            # ... view logic
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            try:
                return view_func(request, *args, **kwargs)

            except ObjectDoesNotExist as e:
                # Object not found - 404
                error_msg = error_message or f"The requested item was not found."
                logger.warning(
                    f"ObjectDoesNotExist in {view_func.__name__}: {e} "
                    f"[User: {request.user.username if request.user.is_authenticated else 'Anonymous'}, "
                    f"Path: {request.path}]"
                )
                messages.error(request, error_msg)
                if redirect_url:
                    return redirect(redirect_url)
                raise Http404(error_msg)

            except ValidationError as e:
                # Form validation error
                error_msg = error_message or "Please correct the errors in the form."
                # Extract validation error messages
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            messages.error(request, f"{field}: {error}")
                elif hasattr(e, 'messages'):
                    for msg in e.messages:
                        messages.error(request, msg)
                else:
                    messages.error(request, str(e))

                logger.info(
                    f"ValidationError in {view_func.__name__}: {e} "
                    f"[User: {request.user.username if request.user.is_authenticated else 'Anonymous'}]"
                )
                if redirect_url:
                    return redirect(redirect_url)
                # Let the view handle re-rendering the form with errors
                return view_func(request, *args, **kwargs)

            except IntegrityError as e:
                # Database constraint violation
                error_msg = error_message or "Unable to save. This may be a duplicate entry or violates database constraints."
                logger.error(
                    f"IntegrityError in {view_func.__name__}: {e} "
                    f"[User: {request.user.username if request.user.is_authenticated else 'Anonymous'}, "
                    f"Path: {request.path}]"
                )
                messages.error(request, error_msg)
                if redirect_url:
                    return redirect(redirect_url)
                if render_template:
                    return render(request, render_template, {'error': error_msg})
                return redirect('home')

            except PermissionDenied as e:
                # Authorization error
                error_msg = error_message or "You don't have permission to perform this action."
                logger.warning(
                    f"PermissionDenied in {view_func.__name__}: {e} "
                    f"[User: {request.user.username if request.user.is_authenticated else 'Anonymous'}, "
                    f"Path: {request.path}]"
                )
                messages.error(request, error_msg)
                return redirect('home')

            except Exception as e:
                # Unexpected error - log with full context
                error_msg = error_message or "An unexpected error occurred. Please try again or contact support."
                logger.exception(
                    f"Unexpected error in {view_func.__name__}: {e} "
                    f"[User: {request.user.username if request.user.is_authenticated else 'Anonymous'}, "
                    f"Path: {request.path}, Method: {request.method}]"
                )
                messages.error(request, error_msg)
                if redirect_url:
                    return redirect(redirect_url)
                return redirect('home')

        return wrapped_view
    return decorator


def log_and_suppress(logger_name=None, default_return=None):
    """
    Decorator to log exceptions but suppress them (return default value).

    Useful for non-critical operations where failure shouldn't break the view.

    Args:
        logger_name (str, optional): Name of logger to use. Defaults to __name__.
        default_return: Value to return if exception occurs. Defaults to None.

    Returns:
        function: Decorated function that suppresses exceptions

    Example:
        @log_and_suppress(default_return=0)
        def get_count():
            # If this fails, return 0 instead of breaking
            return expensive_operation()
    """
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log = logging.getLogger(logger_name or __name__)
                log.error(f"Suppressed error in {func.__name__}: {e}")
                return default_return
        return wrapped
    return decorator
