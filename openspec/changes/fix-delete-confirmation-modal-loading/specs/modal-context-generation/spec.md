# Spec: Modal Context Generation

## ADDED Requirements

### Requirement: Template tags SHALL generate consistent modal context
**ID**: MODAL-CTX-001
**Priority**: Critical
**Status**: New

Template tags SHALL be created to generate consistent modal IDs and complete context for delete confirmation modals across all entity types.

#### Scenario: Template tag generates consistent modal ID
**Given** a template needs to display delete confirmation for an entity
**When** developer uses `{% delete_modal_id 'Patient' %}` tag
**Then** tag generates ID "deletePatientModal"
**And** ID is consistent across button click handlers and modal includes

**Acceptance Criteria**:
- ✅ Template tag `delete_modal_id` exists
- ✅ Takes entity_type as required parameter
- ✅ Takes optional entity_id parameter for manager pages
- ✅ Returns consistent string ID
- ✅ ID matches JavaScript expectations

#### Scenario: Template tag generates modal ID with entity ID
**Given** a manager page displays multiple entities in a list
**When** developer uses `{% delete_modal_id 'Patient' patient.id %}` in loop
**Then** tag generates unique ID like "deletePatientModal42"
**And** each entity gets unique modal ID

**Acceptance Criteria**:
- ✅ Unique ID per entity on manager pages
- ✅ No ID collisions between modals
- ✅ ID format consistent: base + entity_id

### Requirement: Inclusion tag SHALL generate complete modal with context
**ID**: MODAL-CTX-002
**Priority**: Critical
**Status**: New

An inclusion tag SHALL generate complete delete confirmation modal with all required context automatically populated from entity object.

#### Scenario: Inclusion tag generates modal with entity details
**Given** a template has access to a Patient entity
**When** developer uses `{% delete_modal patient %}` tag
**Then** tag generates complete modal HTML
**And** modal displays patient name, BHT number, gender
**And** modal shows warnings about related records
**And** delete URL is correctly formatted

**Acceptance Criteria**:
- ✅ Template tag `delete_modal` exists
- ✅ Takes entity object as required parameter
- ✅ Optionally takes custom modal_id parameter
- ✅ Auto-generates modal_id if not provided
- ✅ Calls helper functions to generate context
- ✅ Renders complete modal template

#### Scenario: Inclusion tag generates modal for video entity
**Given** a video view page with video entity
**When** developer uses `{% delete_modal video %}` tag
**Then** modal displays video file name and patient
**And** warning about permanent file deletion is shown
**And** delete URL points to video delete endpoint

**Acceptance Criteria**:
- ✅ Video-specific context generated
- ✅ File name displayed
- ✅ Associated patient shown if exists
- ✅ Storage warning included

#### Scenario: Inclusion tag works for all entity types
**Given** any entity type in the system
**When** developer uses `{% delete_modal entity %}` tag
**Then** correct entity type is detected
**And** appropriate context is generated using helper functions
**And** entity-specific warnings are displayed
**And** entity-specific details are shown

**Acceptance Criteria**:
- ✅ Works for Patient, Video, GMAssessment, CDICRecord, HINEAssessment
- ✅ Works for DevelopmentalAssessment, GPARecord, Attachment, Bookmark
- ✅ Works for CustomUser
- ✅ Helper functions called for each entity type
- ✅ Context generation is consistent

### Requirement: Modal SHALL display standard detail level for all entities
**ID**: MODAL-CTX-003
**Priority**: High
**Status**: New

Delete confirmation modals SHALL display 3-5 key fields (standard detail level) that adequately identify the entity being deleted.

#### Scenario: Patient modal shows standard details
**Given** user clicks delete on a patient
**When** delete confirmation modal appears
**Then** modal displays patient name, BHT number, gender
**And** warnings about related records (videos, assessments) are shown
**And** user can clearly identify which patient will be deleted

**Acceptance Criteria**:
- ✅ Patient name displayed
- ✅ BHT number displayed
- ✅ Gender displayed
- ✅ Related record counts shown in warnings

#### Scenario: Video modal shows standard details
**Given** user clicks delete on a video
**When** delete confirmation modal appears
**Then** modal displays file name and associated patient
**And** warning about file storage deletion
**And** user can identify which video will be deleted

**Acceptance Criteria**:
- ✅ Video file name displayed
- ✅ Associated patient shown
- ✅ File storage warning present

#### Scenario: Assessment modal shows standard details
**Given** user clicks delete on any assessment (GMA, HINE, CDIC, GPA, Developmental)
**When** delete confirmation modal appears
**Then** modal displays patient name and assessment date
**And** warning that patient/video won't be deleted
**And** user understands scope of deletion

**Acceptance Criteria**:
- ✅ Patient name displayed for all assessment types
- ✅ Assessment date/created_at shown
- ✅ Warnings clarify cascade behavior

#### Scenario: Attachment modal shows standard details
**Given** user clicks delete on an attachment
**When** delete confirmation modal appears
**Then** modal displays attachment title and file name
**And** warning about permanent file deletion
**And** clarification that patient won't be deleted

**Acceptance Criteria**:
- ✅ Attachment title displayed
- ✅ File name shown
- ✅ Warnings about scope present

### Requirement: Manager pages SHALL generate context for each list item
**ID**: MODAL-CTX-004
**Priority**: High
**Status**: New

Manager pages that display multiple entities in lists SHALL properly generate modal context for each item.

#### Scenario: Patient manager generates modal per patient
**Given** patient manager page displays 20 patients
**When** page renders
**Then** each patient has unique modal ID
**And** each modal shows correct patient details
**And** delete button click handlers reference correct modal ID

**Acceptance Criteria**:
- ✅ 20 unique modal IDs generated
- ✅ Each modal has correct patient context
- ✅ No context mixing between modals
- ✅ Click handlers match modal IDs

#### Scenario: Video manager generates modal per video
**Given** video manager page displays 15 videos
**When** page renders
**Then** each video has unique modal
**And** context generation uses helper functions efficiently
**And** page load performance is acceptable (< 2s)

**Acceptance Criteria**:
- ✅ Unique modals per video
- ✅ Correct video details in each modal
- ✅ Performance: < 2s page load
- ✅ No N+1 query issues

#### Scenario: Assessment manager handles multiple items
**Given** assessment manager displays 30 assessments
**When** page renders
**Then** modals generated efficiently
**And** template tag loops don't cause performance degradation
**And** each modal has correct assessment context

**Acceptance Criteria**:
- ✅ 30 unique modal contexts generated
- ✅ Page renders within acceptable time
- ✅ No browser performance warnings
- ✅ Modal context is accurate

### Requirement: Helper functions SHALL provide entity-specific context
**ID**: MODAL-CTX-005
**Priority**: High
**Status**: New

The existing helper functions in `delete_helpers.py` SHALL be properly integrated with template tags to provide entity-specific context.

#### Scenario: get_entity_detail_items provides correct details
**Given** an entity of any type
**When** `get_entity_detail_items(entity)` is called
**Then** function returns dict with 3-5 key fields
**And** fields are relevant to entity type
**And** values are properly formatted for display

**Acceptance Criteria**:
- ✅ Returns dict for all entity types
- ✅ Patient: name, BHT, gender
- ✅ Video: file name, patient
- ✅ Assessment: patient, date
- ✅ Attachment: title, file
- ✅ User: username, email, full name

#### Scenario: get_entity_warning_items provides appropriate warnings
**Given** an entity with related records
**When** `get_entity_warning_items(entity)` is called
**Then** function returns list of warning strings
**And** warnings indicate cascade deletions if applicable
**And** warnings clarify scope of deletion

**Acceptance Criteria**:
- ✅ Returns list of strings
- ✅ Patient: shows counts of related records
- ✅ Video: file storage warning
- ✅ Assessment: scope clarification
- ✅ Warnings are user-friendly

#### Scenario: Template tag integrates helper functions correctly
**Given** template tag is generating modal context
**When** inclusion tag calls helper functions
**Then** functions receive correct entity object
**And** returned context is passed to modal template
**And** modal displays context correctly

**Acceptance Criteria**:
- ✅ Helper functions called with entity parameter
- ✅ Context dict includes all helper results
- ✅ Modal template receives complete context
- ✅ No template context errors

## MODIFIED Requirements

None - this is new functionality to fix broken implementation

## REMOVED Requirements

None

## Implementation Notes

### Template Tag Module Structure
```python
# ndas/templatetags/delete_modal_tags.py

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def delete_modal_id(entity_type, entity_id=None):
    """Generate consistent modal ID"""
    base_id = f"delete{entity_type}Modal"
    if entity_id:
        return f"{base_id}{entity_id}"
    return base_id

@register.inclusion_tag('src/partials/delete_confirmation_modal.html')
def delete_modal(entity, modal_id=None):
    """Generate complete modal with context"""
    from ndas.custom_codes.delete_helpers import (
        get_entity_display_name,
        get_entity_warning_items,
        get_entity_detail_items,
        get_redirect_url
    )

    entity_type = entity.__class__.__name__
    entity_id = entity.pk

    if not modal_id:
        modal_id = delete_modal_id(entity_type, entity_id)

    return {
        'modal_id': modal_id,
        'entity_type': entity_type,
        'entity_name': get_entity_display_name(entity),
        'delete_url': f'/{entity_type.lower()}/delete/{entity_id}/',
        'redirect_url': get_redirect_url(entity_type),
        'warning_items': get_entity_warning_items(entity),
        'detail_items': get_entity_detail_items(entity),
    }
```

### Template Usage Patterns
```django
{# Detail/Edit Pages (single entity) #}
{% load delete_modal_tags %}
<button onclick="DeleteConfirmation.show('{% delete_modal_id 'Patient' %}')">
  Delete
</button>
{% delete_modal patient %}

{# Manager Pages (multiple entities) #}
{% load delete_modal_tags %}
{% for patient in patients %}
  <tr>
    <td>{{ patient.baby_name }}</td>
    <td>
      {% delete_modal_id 'Patient' patient.id as modal_id %}
      <button onclick="DeleteConfirmation.show('{{ modal_id }}')">Delete</button>
    </td>
  </tr>
{% endfor %}

{# Generate modals outside loop for performance #}
{% for patient in patients %}
  {% delete_modal patient %}
{% endfor %}
```

### Testing Requirements
- Unit tests for template tags
- Integration tests for context generation
- Template rendering tests for all entity types
- Performance tests for manager pages with 50+ items

## Related Requirements
- See `asset-loading/spec.md` for asset loading requirements
- See `error-handling/spec.md` for error handling requirements
