from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from ndas.custom_codes.choice import UserType


def admin_required(view_func):
    """Decorator to require admin access (staff, superuser, or ADMIN/SUPERADMIN user_type)."""
    @wraps(view_func)
    @login_required(login_url='user-login')
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not (
            user.is_staff
            or user.is_superuser
            or getattr(user, 'user_type', None) in (UserType.ADMIN, UserType.SUPERADMIN)
        ):
            messages.error(request, 'You do not have permission to access this area.')
            return redirect('user-view', pk=request.user.pk)
        return view_func(request, *args, **kwargs)
    return wrapper


def superuser_required(view_func):
    """Decorator to require superuser access."""
    @wraps(view_func)
    @login_required(login_url='user-login')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'You do not have permission to access this area.')
            return redirect('user-view', pk=request.user.pk)
        return view_func(request, *args, **kwargs)
    return wrapper
