"""
Patient Timeline Utilities Module

This module provides utility functions for aggregating and formatting patient timeline events
from various sources (assessments, videos, attachments) into a unified chronological display.

Usage:
    from patients.timeline_utils import get_patient_timeline_events

    timeline_events = get_patient_timeline_events(patient_instance)
    # Returns list of event dictionaries sorted by datetime (newest first)

Author: NDAS Development Team
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.urls import reverse
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def format_event_datetime(dt: Optional[datetime]) -> Dict[str, str]:
    """
    Format a datetime object into multiple display formats for timeline events.

    Args:
        dt: Datetime object to format (can be timezone-aware or naive)

    Returns:
        Dictionary containing:
            - 'date': Formatted date string (e.g., "Jan 15, 2024")
            - 'time': Formatted time string (e.g., "14:30")
            - 'iso': ISO 8601 formatted string for machine-readable attributes

    Example:
        >>> dt = datetime(2024, 1, 15, 14, 30, 0)
        >>> format_event_datetime(dt)
        {'date': 'Jan 15, 2024', 'time': '14:30', 'iso': '2024-01-15T14:30:00'}
    """
    if dt is None:
        return {
            'date': 'Unknown date',
            'time': '',
            'iso': ''
        }

    # Handle timezone-aware datetimes
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)

    return {
        'date': dt.strftime('%b %d, %Y'),
        'time': dt.strftime('%H:%M'),
        'iso': dt.isoformat()
    }


def get_event_age_at_time(birth_date: Optional[datetime], event_date: Optional[datetime]) -> str:
    """
    Calculate patient age at the time of a specific event.

    Args:
        birth_date: Patient's date of birth
        event_date: Date of the event

    Returns:
        Formatted age string (e.g., "2 months, 5 days", "1 year, 3 months", "At birth")

    Example:
        >>> birth = datetime(2024, 1, 1)
        >>> event = datetime(2024, 3, 6)
        >>> get_event_age_at_time(birth, event)
        '2 months, 5 days'
    """
    if birth_date is None or event_date is None:
        return "Unknown age"

    # Handle timezone-aware datetimes
    if timezone.is_aware(birth_date):
        birth_date = timezone.localtime(birth_date).replace(tzinfo=None)
    if timezone.is_aware(event_date):
        event_date = timezone.localtime(event_date).replace(tzinfo=None)

    # Same day as birth
    if event_date.date() == birth_date.date():
        return "At birth"

    # Calculate age difference
    age_delta = event_date - birth_date
    total_days = age_delta.days

    if total_days < 0:
        return "Before birth"

    # Calculate years, months, and days
    years = total_days // 365
    remaining_days = total_days % 365
    months = remaining_days // 30
    days = remaining_days % 30

    # Format age string
    age_parts = []
    if years > 0:
        age_parts.append(f"{years} year{'s' if years > 1 else ''}")
    if months > 0 and years < 2:  # Only show months if less than 2 years old
        age_parts.append(f"{months} month{'s' if months > 1 else ''}")
    if days > 0 and years == 0:  # Only show days if less than 1 year old
        age_parts.append(f"{days} day{'s' if days > 1 else ''}")

    return ", ".join(age_parts) if age_parts else "0 days"


def get_patient_timeline_events(patient) -> List[Dict[str, Any]]:
    """
    Aggregate all timeline events for a patient from multiple sources.

    Collects events from:
        - Birth event (patient.dob_tob)
        - GM Assessments (GMAssessment model)
        - HINE Assessments (HINEAssessment model)
        - Developmental Assessments (DevelopmentalAssessment model)
        - CDIC Records (CDICRecord model)
        - GPA Assessments (GeneralPaediatricAssessment model)
        - Videos (Video model)
        - Attachments (Attachment model)

    Args:
        patient: Patient model instance

    Returns:
        List of event dictionaries sorted by datetime (newest first), each containing:
            - datetime: Python datetime object for sorting
            - formatted_datetime: Dict with 'date', 'time', 'iso' keys
            - age_at_event: Formatted age string
            - type: Event type string (e.g., 'birth', 'gma', 'video')
            - icon: Font Awesome icon class
            - color: AdminLTE color class (primary, success, info, warning, danger)
            - title: Event title/headline
            - description: Event description/details
            - detail_url: URL to detailed view (opens in new window)
            - can_preview: Boolean indicating if inline preview available
            - preview_data: Optional dict with preview information

    Example:
        >>> patient = Patient.objects.get(id=1)
        >>> events = get_patient_timeline_events(patient)
        >>> len(events)
        15
        >>> events[0]['type']
        'gpa'
    """
    events = []

    # Task 1.4: Create birth event
    try:
        if patient.dob_tob:
            birth_datetime = patient.dob_tob
            events.append({
                'datetime': birth_datetime,
                'formatted_datetime': format_event_datetime(birth_datetime),
                'age_at_event': 'At birth',
                'type': 'birth',
                'icon': 'fa-birthday-cake',
                'color': 'primary',
                'title': 'Birth',
                'description': f"{patient.baby_name or 'Baby'} was born",
                'detail_url': None,
                'can_preview': False,
                'preview_data': {}
            })
    except Exception as e:
        logger.error(f"Error creating birth event for patient {patient.id}: {str(e)}")

    # Task 1.5: Add GM Assessment events
    try:
        gma_assessments = patient.gm_assessments.select_related('video_file', 'added_by').all()
        for gma in gma_assessments:
            if gma.date_of_assessment:
                assessment_datetime = gma.date_of_assessment

                # Get diagnosis conclusion for preview
                diagnosis_text = gma.diagnosis_conclusion if gma.diagnosis_conclusion else 'Not assessed'

                events.append({
                    'datetime': assessment_datetime,
                    'formatted_datetime': format_event_datetime(assessment_datetime),
                    'age_at_event': get_event_age_at_time(patient.dob_tob, assessment_datetime),
                    'type': 'gma',
                    'icon': 'fa-video',
                    'color': 'success',
                    'title': 'GM Assessment',
                    'description': f"Video assessment - {diagnosis_text} by {gma.added_by.get_full_name() if gma.added_by else 'Unknown'}",
                    'detail_url': reverse('assessment-view', args=[gma.id]),
                    'can_preview': True,
                    'preview_data': {
                        'diagnosis_conclusion': diagnosis_text,
                        'management_plan': gma.management_plan[:200] if gma.management_plan else 'No management plan recorded',
                        'video': gma.video_file.title if gma.video_file else None
                    }
                })
    except Exception as e:
        logger.error(f"Error aggregating GM assessments for patient {patient.id}: {str(e)}")

    # Task 1.6: Add HINE Assessment events
    try:
        hine_assessments = patient.hine_assessments.select_related('added_by').all()
        for hine in hine_assessments:
            if hine.date_of_assessment:
                assessment_datetime = hine.date_of_assessment

                total_score = hine.score if hasattr(hine, 'score') and hine.score else 'N/A'
                events.append({
                    'datetime': assessment_datetime,
                    'formatted_datetime': format_event_datetime(assessment_datetime),
                    'age_at_event': get_event_age_at_time(patient.dob_tob, assessment_datetime),
                    'type': 'hine',
                    'icon': 'fa-brain',
                    'color': 'info',
                    'title': 'HINE Assessment',
                    'description': f"Neurological assessment - Score: {total_score} by {hine.added_by.get_full_name() if hine.added_by else 'Unknown'}",
                    'detail_url': reverse('hine-assessment-view', args=[hine.id]),
                    'can_preview': True,
                    'preview_data': {
                        'score': total_score,
                        'assessor': hine.added_by.get_full_name() if hine.added_by else 'Unknown'
                    }
                })
    except Exception as e:
        logger.error(f"Error aggregating HINE assessments for patient {patient.id}: {str(e)}")

    # Task 1.7: Add Developmental Assessment events
    try:
        dev_assessments = patient.developmental_assessments.select_related('added_by').all()
        for dev in dev_assessments:
            if dev.date_of_assessment:
                assessment_datetime = dev.date_of_assessment

                is_normal = "Normal development" if dev.isNormal else "Developmental concerns"
                events.append({
                    'datetime': assessment_datetime,
                    'formatted_datetime': format_event_datetime(assessment_datetime),
                    'age_at_event': get_event_age_at_time(patient.dob_tob, assessment_datetime),
                    'type': 'developmental',
                    'icon': 'fa-child',
                    'color': 'success' if dev.isNormal else 'warning',
                    'title': 'Developmental Assessment',
                    'description': f"{is_normal} by {dev.added_by.get_full_name() if dev.added_by else 'Unknown'}",
                    'detail_url': reverse('da-assessment-view', args=[dev.id]),
                    'can_preview': True,
                    'preview_data': {
                        'status': is_normal,
                        'assessor': dev.added_by.get_full_name() if dev.added_by else 'Unknown'
                    }
                })
    except Exception as e:
        logger.error(f"Error aggregating developmental assessments for patient {patient.id}: {str(e)}")

    # Task 1.8: Add CDIC Record events
    try:
        cdic_records = patient.cdic_records.select_related('added_by').all()
        for cdic in cdic_records:
            if cdic.assessment_date:
                # CDIC uses DateField, convert to datetime
                assessment_datetime = datetime.combine(cdic.assessment_date, datetime.min.time())
                if timezone.is_aware(patient.dob_tob):
                    assessment_datetime = timezone.make_aware(assessment_datetime)

                events.append({
                    'datetime': assessment_datetime,
                    'formatted_datetime': format_event_datetime(assessment_datetime),
                    'age_at_event': get_event_age_at_time(patient.dob_tob, assessment_datetime),
                    'type': 'cdic',
                    'icon': 'fa-hands-helping',
                    'color': 'info',
                    'title': 'CDIC Record',
                    'description': f"Support assessment by {cdic.added_by.get_full_name() if cdic.added_by else 'Unknown'}",
                    'detail_url': reverse('cdic-assessment-view', args=[cdic.id]),
                    'can_preview': True,
                    'preview_data': {
                        'assessor': cdic.added_by.get_full_name() if cdic.added_by else 'Unknown'
                    }
                })
    except Exception as e:
        logger.error(f"Error aggregating CDIC records for patient {patient.id}: {str(e)}")

    # Task 1.9: Add GPA Assessment events
    try:
        gpa_assessments = patient.gpa_assessments.select_related('added_by').all()
        for gpa in gpa_assessments:
            if gpa.assessment_date:
                assessment_datetime = gpa.assessment_date

                provider = gpa.healthcare_provider if hasattr(gpa, 'healthcare_provider') and gpa.healthcare_provider else 'Unknown provider'
                events.append({
                    'datetime': assessment_datetime,
                    'formatted_datetime': format_event_datetime(assessment_datetime),
                    'age_at_event': get_event_age_at_time(patient.dob_tob, assessment_datetime),
                    'type': 'gpa',
                    'icon': 'fa-stethoscope',
                    'color': 'primary',
                    'title': 'General Paediatric Assessment',
                    'description': f"Medical assessment by {provider}",
                    'detail_url': reverse('gpa-view', args=[gpa.id]),
                    'can_preview': True,
                    'preview_data': {
                        'provider': provider,
                        'added_by': gpa.added_by.get_full_name() if gpa.added_by else 'Unknown'
                    }
                })
    except Exception as e:
        logger.error(f"Error aggregating GPA assessments for patient {patient.id}: {str(e)}")

    # Task 1.10: Add Video events
    try:
        videos = patient.videos.select_related('added_by').all()
        for video in videos:
            if video.recorded_on:
                video_datetime = video.recorded_on

                events.append({
                    'datetime': video_datetime,
                    'formatted_datetime': format_event_datetime(video_datetime),
                    'age_at_event': get_event_age_at_time(patient.dob_tob, video_datetime),
                    'type': 'video',
                    'icon': 'fa-video',
                    'color': 'danger',
                    'title': f"Video: {video.title}",
                    'description': f"Uploaded by {video.added_by.get_full_name() if video.added_by else 'Unknown'}",
                    'detail_url': reverse('video:view', args=[video.id]),
                    'can_preview': False,
                    'preview_data': {}
                })
    except Exception as e:
        logger.error(f"Error aggregating videos for patient {patient.id}: {str(e)}")

    # Task 1.11: Add Attachment events
    try:
        attachments = patient.attachments.select_related('added_by').all()
        for attachment in attachments:
            if attachment.created_at:
                upload_datetime = attachment.created_at

                # Determine if preview is available based on file type
                can_preview = False
                if hasattr(attachment, 'attachment') and attachment.attachment:
                    file_ext = attachment.attachment.name.split('.')[-1].lower()
                    can_preview = file_ext in ['jpg', 'jpeg', 'png', 'gif', 'pdf']

                attachment_type = attachment.attachment_type if hasattr(attachment, 'attachment_type') else 'File'
                events.append({
                    'datetime': upload_datetime,
                    'formatted_datetime': format_event_datetime(upload_datetime),
                    'age_at_event': get_event_age_at_time(patient.dob_tob, upload_datetime),
                    'type': 'attachment',
                    'icon': 'fa-paperclip',
                    'color': 'secondary',
                    'title': f"Attachment: {attachment_type}",
                    'description': f"{attachment.attachment.name.split('/')[-1] if attachment.attachment else 'Unknown file'} uploaded by {attachment.added_by.get_full_name() if attachment.added_by else 'Unknown'}",
                    'detail_url': reverse('attachment-view', args=[attachment.id]),
                    'can_preview': can_preview,
                    'preview_data': {
                        'filename': attachment.attachment.name.split('/')[-1] if attachment.attachment else 'Unknown',
                        'type': attachment_type
                    }
                })
    except Exception as e:
        logger.error(f"Error aggregating attachments for patient {patient.id}: {str(e)}")

    # Task 1.12: Sort events by datetime (newest first)
    try:
        # Filter out events with None datetime, then sort
        events_with_datetime = [e for e in events if e.get('datetime') is not None]
        events_without_datetime = [e for e in events if e.get('datetime') is None]

        sorted_events = sorted(events_with_datetime, key=lambda x: x['datetime'], reverse=True)

        # Append events without datetime at the end
        sorted_events.extend(events_without_datetime)

        return sorted_events
    except Exception as e:
        logger.error(f"Error sorting events for patient {patient.id}: {str(e)}")
        return events  # Return unsorted if sorting fails
