"""
Delete Modal Template Tags
File: ndas/templatetags/delete_modal_tags.py
Part of fix-delete-confirmation-modal-loading change

Provides template tags for consistent delete confirmation modal generation:
- delete_modal_id: Generate consistent modal IDs
- delete_modal: Generate complete modal with context from entity
"""

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def delete_modal_id(entity_type, entity_id=None):
    """
    Generate consistent modal ID for delete confirmation.

    Args:
        entity_type (str): Type of entity (Patient, Video, etc.)
        entity_id (int, optional): Entity ID for manager pages with multiple items

    Returns:
        str: Consistent modal ID string

    Examples:
        {% delete_modal_id 'Patient' %} -> 'deletePatientModal'
        {% delete_modal_id 'Patient' 42 %} -> 'deletePatientModal42'
    """
    base_id = f"delete{entity_type}Modal"
    if entity_id is not None:
        return f"{base_id}{entity_id}"
    return base_id


@register.inclusion_tag('src/partials/delete_confirmation_modal.html')
def delete_modal(entity, modal_id=None):
    """
    Generate and render complete delete confirmation modal with context.

    This inclusion tag automatically generates all required context for the
    delete confirmation modal using helper functions from delete_helpers.py.

    Args:
        entity: The entity object to be deleted (Patient, Video, etc.)
        modal_id (str, optional): Custom modal ID (auto-generated if not provided)

    Returns:
        dict: Context dictionary for modal template with:
            - modal_id: Unique modal identifier
            - entity_type: Human-readable entity type name
            - entity_name: Display name of the entity
            - delete_url: Backend DELETE endpoint URL
            - redirect_url: Where to redirect after successful deletion
            - warning_items: List of warning strings
            - detail_items: Dict of entity detail key-value pairs

    Examples:
        {# Single entity page #}
        {% load delete_modal_tags %}
        {% delete_modal patient %}

        {# Manager page with custom ID #}
        {% delete_modal video modal_id %}

        {# In loop with auto-generated IDs #}
        {% for patient in patients %}
          {% delete_modal patient %}
        {% endfor %}
    """
    from ndas.custom_codes.delete_helpers import (
        get_entity_display_name,
        get_entity_warning_items,
        get_entity_detail_items,
        get_redirect_url
    )

    # Get entity metadata
    entity_type = entity.__class__.__name__
    entity_id = entity.pk

    # Auto-generate modal ID if not provided
    if not modal_id:
        modal_id = delete_modal_id(entity_type, entity_id)

    # Map entity types to URL patterns
    # This handles the various URL naming conventions in the project
    url_map = {
        'Patient': f'/patient/delete/{entity_id}/',
        'Video': f'/video/delete/{entity_id}/',
        'GMAssessment': f'/assessment/delete/{entity_id}/',
        'HINEAssessment': f'/hine/delete/{entity_id}/',
        'CDICRecord': f'/cdic/delete/{entity_id}/',
        'DevelopmentalAssessment': f'/da/delete/{entity_id}/',
        'GPARecord': f'/gpa/delete/{entity_id}/',
        'Attachment': f'/attachment/delete/{entity_id}/',
        'Bookmark': f'/bookmarks/delete/{entity_id}/',
        'CustomUser': f'/users/admin/user/delete/{entity_id}/',
        'User': f'/users/admin/user/delete/{entity_id}/',
    }

    delete_url = url_map.get(entity_type, f'/{entity_type.lower()}/delete/{entity_id}/')

    # Generate context using helper functions
    return {
        'modal_id': modal_id,
        'entity_type': entity_type,
        'entity_name': get_entity_display_name(entity),
        'delete_url': delete_url,
        'redirect_url': get_redirect_url(entity_type),
        'warning_items': get_entity_warning_items(entity),
        'detail_items': get_entity_detail_items(entity),
    }
