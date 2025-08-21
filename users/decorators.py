from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def admin_required(view_func):
    """Decorator to require admin access (staff or superuser)."""
    @wraps(view_func)
    @login_required(login_url='user-login')
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
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
