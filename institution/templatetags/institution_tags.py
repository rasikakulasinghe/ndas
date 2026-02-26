"""
institution/templatetags/institution_tags.py

Template tags for Story 2.2 — SUPERADMIN on-screen context indicator.

Usage in templates:
    {% load institution_tags %}
    {% superadmin_overlay %}
"""
from django import template
from django.middleware.csrf import get_token

from institution.models import Institution
from ndas.custom_codes.choice import UserType

register = template.Library()


@register.inclusion_tag('institution/partials/superadmin_overlay.html', takes_context=True)
def superadmin_overlay(context):
    """
    Render the SUPERADMIN context-switching overlay banner.
    Visible only when request.user is SUPERADMIN (UserType.SUPERADMIN).
    Passes the active institution (if set) and the full institutions list
    for the in-banner context switcher dropdown.
    """
    request = context.get('request')
    if request is None:
        return {}

    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.SUPERADMIN:
        return {}

    active_institution = getattr(request, 'institution', None)

    if not active_institution:
        # No active context — overlay is not shown, skip the DB query
        return {}

    # Load institutions list only when overlay will actually render
    institutions = Institution.objects.filter(is_active=True).order_by('name')

    return {
        'request': request,
        'active_institution': active_institution,
        'institutions': institutions,
        'csrf_token': get_token(request),
    }
