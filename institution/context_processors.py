from ndas.custom_codes.choice import UserType


def institution_context(request):
    """
    Injects institution context into every template context.

    Provides:
      active_institution  — Institution object (or None for unresolved SUPERADMIN)
      user_type           — UserType string ('SUPERADMIN', 'ADMIN', 'USER')
      is_superadmin       — bool shorthand for user_type == SUPERADMIN

    Template usage (CORRECT):
      {{ active_institution.name }}
      {{ active_institution.logo.url }}
      {% if is_superadmin %}...{% endif %}
      {% if user_type == 'ADMIN' %}...{% endif %}

    NEVER use in templates:
      {{ request.user.institution.name }}  ← breaks SUPERADMIN context switching
      {% if request.user.is_superuser %}   ← use is_superadmin instead
    """
    if not request.user.is_authenticated:
        return {}

    active_institution = getattr(request, 'institution', None)
    user_type = getattr(request.user, 'user_type', UserType.USER)
    is_superadmin = (user_type == UserType.SUPERADMIN)

    return {
        'active_institution': active_institution,
        'user_type': user_type,
        'is_superadmin': is_superadmin,
    }
