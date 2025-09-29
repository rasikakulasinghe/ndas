from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings


def handler404(request, exception):
    """
    Custom 404 error handler that renders our professional 404 page
    """
    return render(request, '404.html', status=404)


def handler500(request):
    """
    Custom 500 error handler for server errors
    """
    return render(request, '500.html', status=500)


@login_required(login_url="user-login")
def debug_bootstrap(request):
    """
    Debug page to check Bootstrap and dependency loading
    Only available in DEBUG mode or for superusers
    """
    if not settings.DEBUG and not request.user.is_superuser:
        return render(request, '404.html', status=404)

    return render(request, 'debug_bootstrap.html')
