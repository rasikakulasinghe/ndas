"""
Delete Helper Utilities
File: ndas/custom_codes/delete_helpers.py
Part of refactor-delete-confirmation change

Centralized helper functions for entity deletion operations across NDAS.
Provides consistent permission checks, business rule validation, and redirect logic.
"""

from typing import Dict, Any, Optional
from django.contrib.auth import get_user_model

User = get_user_model()


def has_delete_permission(user: User, entity: Any) -> bool:
    """
    Check if user has permission to delete the specified entity.

    Args:
        user: The user attempting the deletion
        entity: The entity to be deleted

    Returns:
        bool: True if user has delete permission, False otherwise

    Business Rules:
        - Superusers can delete any entity
        - Staff users can delete their own records (based on added_by field)
        - Non-staff users cannot delete anything
    """
    if not user or not user.is_authenticated:
        return False

    # Superusers can delete everything
    if user.is_superuser:
        return True

    # Check if entity has an 'added_by' field
    if hasattr(entity, 'added_by'):
        # Staff users can delete their own records
        if user.is_staff and entity.added_by == user:
            return True

    # Staff users can delete certain entity types regardless of ownership
    # (Add specific logic for different entity types here if needed)
    if user.is_staff:
        # Allow staff to delete bookmarks (always own their bookmarks)
        if entity.__class__.__name__ == 'Bookmark':
            return True

    return False


def validate_can_delete(entity: Any) -> Dict[str, Any]:
    """
    Check business rules to determine if entity can be deleted.

    Args:
        entity: The entity to be deleted

    Returns:
        dict: {
            'can_delete': bool,
            'reason': str  # Empty if can_delete is True, otherwise explanation
        }

    Business Rules:
        - Videos cannot be deleted if referenced in assessments
        - Patients with related records show warning but can be deleted (cascade)
        - Add more entity-specific rules as needed
    """
    entity_type = entity.__class__.__name__

    # Check video-specific rules
    if entity_type == 'Video':
        # Import here to avoid circular imports
        from patients.models import GMAssessment

        assessment_count = GMAssessment.objects.filter(video_file=entity).count()
        if assessment_count > 0:
            return {
                'can_delete': False,
                'reason': f"Cannot delete video that is used in {assessment_count} assessment(s). "
                         f"Please remove the video from assessments first."
            }

    # Check user-specific rules (prevent deleting own account)
    if entity_type == 'CustomUser' or entity_type == 'User':
        # This check is handled in the view itself
        # Just ensure it's documented here
        pass

    # All checks passed
    return {
        'can_delete': True,
        'reason': ''
    }


def get_entity_display_name(entity: Any) -> str:
    """
    Get human-readable display name for an entity.

    Args:
        entity: The entity to get name for

    Returns:
        str: Display name suitable for showing to users

    Name Priority:
        1. baby_name (for patients)
        2. title (for general records)
        3. username (for users)
        4. name field
        5. Primary key as fallback
    """
    # Try common name fields in priority order
    name_fields = ['baby_name', 'title', 'username', 'name', 'file_name', 'filename']

    for field in name_fields:
        if hasattr(entity, field):
            value = getattr(entity, field)
            if value:
                return str(value)

    # Fallback to string representation or PK
    try:
        str_repr = str(entity)
        if str_repr and str_repr != f"{entity.__class__.__name__} object":
            return str_repr
    except:
        pass

    # Last resort: primary key
    return f"ID: {entity.pk}"


def get_redirect_url(entity_type: str, patient_id: int = None) -> str:
    """
    Get appropriate redirect URL after successful deletion.

    Args:
        entity_type: The class name of the deleted entity
        patient_id: Optional patient ID for patient-specific entities (like Problem)

    Returns:
        str: URL path to redirect to (usually the manager/list page)

    Redirect Mapping:
        - Patient → patient manager
        - Video → video manager
        - Assessments → patient view (since they're patient-specific)
        - Attachments → patient view
        - Bookmarks → patient manager
        - Problem → patient's problem manager (requires patient_id)
        - Users → user admin list
    """
    # Define redirect URL mapping
    redirect_map = {
        'Patient': '/manager/patient/',
        'Video': '/video/manager/',
        'GMAssessment': '/manager/patient/',  # Redirect to patient manager
        'HINEAssessment': '/manager/patient/',
        'CDICRecord': '/manager/patient/',
        'DevelopmentalAssessment': '/manager/patient/',
        'GPARecord': '/manager/patient/',
        'Attachment': '/manager/patient/',
        'Bookmark': '/manager/patient/',
        'CustomUser': '/users/admin/users/',
        'User': '/users/admin/users/',
    }

    # Handle Problem type with patient_id
    if entity_type == 'Problem' and patient_id:
        return f'/problems/manager/{patient_id}/'

    return redirect_map.get(entity_type, '/')


def get_entity_warning_items(entity: Any) -> list:
    """
    Get warning items specific to entity type for deletion modal.

    Args:
        entity: The entity being deleted

    Returns:
        list: List of warning strings to display

    Warnings Include:
        - Related records that will be cascade deleted
        - Data loss implications
        - Entity-specific cautions
    """
    entity_type = entity.__class__.__name__
    warnings = []

    if entity_type == 'Patient':
        # Count related records
        video_count = entity.videos.count() if hasattr(entity, 'videos') else 0
        assessment_count = entity.assessments.count() if hasattr(entity, 'assessments') else 0
        attachment_count = entity.attachments.count() if hasattr(entity, 'attachments') else 0
        problem_count = entity.problem_list.count() if hasattr(entity, 'problem_list') else 0

        warnings.append("All patient data will be permanently deleted")
        if video_count > 0:
            warnings.append(f"{video_count} associated video(s) will be deleted")
        if assessment_count > 0:
            warnings.append(f"{assessment_count} assessment record(s) will be deleted")
        if attachment_count > 0:
            warnings.append(f"{attachment_count} attachment(s) will be deleted")
        if problem_count > 0:
            warnings.append(f"{problem_count} problem record(s) will be deleted")

    elif entity_type == 'Video':
        warnings.append("Video file will be permanently deleted from storage")
        warnings.append("This action cannot be undone")

    elif 'Assessment' in entity_type or entity_type == 'CDICRecord' or entity_type == 'GPARecord':
        warnings.append("Assessment data will be permanently lost")
        warnings.append("This will not delete the associated patient or video")

    elif entity_type == 'Attachment':
        warnings.append("File will be permanently deleted from storage")
        warnings.append("This will not delete the associated patient")

    elif entity_type == 'Bookmark':
        warnings.append("Bookmark will be removed from your list")

    elif entity_type == 'Problem':
        # Count related problem actions
        action_count = entity.actions.count() if hasattr(entity, 'actions') else 0
        warnings.append("Problem record will be permanently deleted")
        if action_count > 0:
            warnings.append(f"{action_count} associated action log(s) will be deleted")
        warnings.append("This will not delete the associated patient")

    elif entity_type == 'CustomUser' or entity_type == 'User':
        warnings.append("User account will be deactivated (soft delete)")
        warnings.append("User will not be able to log in")
        warnings.append("Historical records will be preserved for audit trail")

    # Default warning if no specific warnings
    if not warnings:
        warnings.append("This record will be permanently deleted")

    return warnings


def get_entity_detail_items(entity: Any) -> Dict[str, str]:
    """
    Get detail items to display for entity in deletion modal.

    Args:
        entity: The entity being deleted

    Returns:
        dict: Key-value pairs of entity details to display
    """
    entity_type = entity.__class__.__name__
    details = {}

    if entity_type == 'Patient':
        details['Name'] = entity.baby_name or 'Unknown'
        details['BHT Number'] = entity.bht or 'N/A'
        details['Gender'] = entity.get_gender_display() if hasattr(entity, 'get_gender_display') else entity.gender

    elif entity_type == 'Video':
        details['File Name'] = entity.file.name if hasattr(entity, 'file') else 'Unknown'
        if hasattr(entity, 'patient'):
            details['Patient'] = str(entity.patient)

    elif 'Assessment' in entity_type or entity_type == 'CDICRecord' or entity_type == 'GPARecord':
        if hasattr(entity, 'patient'):
            details['Patient'] = str(entity.patient)
        if hasattr(entity, 'created_at'):
            details['Date'] = entity.created_at.strftime('%Y-%m-%d')

    elif entity_type == 'Attachment':
        if hasattr(entity, 'title'):
            details['Title'] = entity.title
        if hasattr(entity, 'file'):
            details['File'] = entity.file.name

    elif entity_type == 'Bookmark':
        if hasattr(entity, 'patient'):
            details['Patient'] = str(entity.patient)

    elif entity_type == 'Problem':
        details['Problem'] = entity.name
        if hasattr(entity, 'patient'):
            details['Patient'] = str(entity.patient)
        if hasattr(entity, 'status'):
            details['Status'] = entity.get_status_display() if hasattr(entity, 'get_status_display') else entity.status
        if hasattr(entity, 'date_identified'):
            details['Date Identified'] = entity.date_identified.strftime('%Y-%m-%d')

    elif entity_type == 'CustomUser' or entity_type == 'User':
        details['Username'] = entity.username
        details['Email'] = entity.email or 'N/A'
        details['Full Name'] = entity.get_full_name() if hasattr(entity, 'get_full_name') else 'N/A'

    return details
