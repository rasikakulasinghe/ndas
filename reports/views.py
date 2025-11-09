"""
Report Views

This module contains views for report generation, download, and management.
"""

import os
import re
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse, Http404
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django_ratelimit.decorators import ratelimit

from reports.utils.pdf_generator import (
    PatientPDFGenerator, GMAssessmentPDFGenerator,
    HINEAssessmentPDFGenerator, DAAssessmentPDFGenerator,
    CDICAssessmentPDFGenerator, GPAAssessmentPDFGenerator
)
from reports.utils.excel_generator import ExcelReportGenerator
from patients.models import (
    Patient, GMAssessment, HINEAssessment,
    DevelopmentalAssessment, CDICRecord, GeneralPaediatricAssessment
)


@login_required(login_url='user-login')
@ratelimit(key='user', rate='10/h', method='POST')
def report_builder(request):
    """
    Report builder interface

    GET: Display report builder form
    POST: Generate report (sync or async based on size)
    """
    if request.method == 'POST':
        # Get form data
        report_format = request.POST.get('format', 'pdf')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        # Parse parameters
        parameters = {
            'patients': request.POST.get('patients', 'off') == 'on',
            'gm_assessments': request.POST.get('gm_assessments', 'off') == 'on',
            'hine_assessments': request.POST.get('hine_assessments', 'off') == 'on',
        }

        # For MVP: Generate small reports synchronously
        try:
            if report_format == 'excel':
                generator = ExcelReportGenerator()
                file_path, metadata = generator.generate(
                    start_date=start_date,
                    end_date=end_date,
                    parameters=parameters
                )
                file_id = os.path.basename(file_path).replace('.xlsx', '')
                return redirect('reports:download', file_id=file_id + '.xlsx')
            else:
                # PDF generation - would need patient selection for this MVP
                # For now, return to builder with message
                context = {
                    'message': 'PDF generation requires patient selection. Please use patient view.',
                    'start_date': start_date,
                    'end_date': end_date
                }
                return render(request, 'reports/builder.html', context)

        except Exception as e:
            context = {
                'error': f'Error generating report: {str(e)}',
                'start_date': start_date,
                'end_date': end_date
            }
            return render(request, 'reports/builder.html', context)

    # GET request - show form
    # Default date range: last 30 days
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)

    context = {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
    }
    return render(request, 'reports/builder.html', context)


@login_required(login_url='user-login')
def report_history(request):
    """Display report generation history"""
    context = {
        'reports': []  # For MVP, no persistent history
    }
    return render(request, 'reports/history.html', context)


@login_required(login_url='user-login')
@ratelimit(key='user', rate='100/h')
def download_report(request, file_id):
    """
    Download generated report file

    Args:
        file_id: File identifier (UUID.pdf or UUID.xlsx)
    """
    # Validate file_id format
    file_path = get_validated_report_path(file_id)

    if not os.path.exists(file_path):
        raise Http404("Report file not found or has expired")

    # Check file age
    file_age_hours = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(file_path))).total_seconds() / 3600

    if file_age_hours > 24:
        raise Http404("Report has expired. Please generate a new one.")

    # Determine content type
    if file_id.endswith('.xlsx'):
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        filename = f"report_{datetime.now().strftime('%Y%m%d')}.xlsx"
    else:
        content_type = 'application/pdf'
        filename = f"report_{datetime.now().strftime('%Y%m%d')}.pdf"

    # Serve file
    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


# Assessment PDF Download Views

@login_required(login_url='user-login')
@ratelimit(key='user', rate='100/h')
def download_gm_assessment_pdf(request, assessment_id):
    """Download GM Assessment PDF"""
    assessment = get_object_or_404(GMAssessment, id=assessment_id)

    # Generate PDF
    generator = GMAssessmentPDFGenerator()
    file_path = generator.generate(assessment_id)

    # Serve file
    filename = f"GM_Assessment_{assessment_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@login_required(login_url='user-login')
@ratelimit(key='user', rate='100/h')
def download_hine_assessment_pdf(request, assessment_id):
    """Download HINE Assessment PDF"""
    assessment = get_object_or_404(HINEAssessment, id=assessment_id)

    # Generate PDF
    generator = HINEAssessmentPDFGenerator()
    file_path = generator.generate(assessment_id)

    # Serve file
    filename = f"HINE_Assessment_{assessment_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@login_required(login_url='user-login')
@ratelimit(key='user', rate='100/h')
def download_da_assessment_pdf(request, assessment_id):
    """Download Developmental Assessment PDF"""
    assessment = get_object_or_404(DevelopmentalAssessment, id=assessment_id)

    # Generate PDF
    generator = DAAssessmentPDFGenerator()
    file_path = generator.generate(assessment_id)

    # Serve file
    filename = f"DA_Assessment_{assessment_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@login_required(login_url='user-login')
@ratelimit(key='user', rate='100/h')
def download_cdic_assessment_pdf(request, assessment_id):
    """Download CDIC Record PDF"""
    assessment = get_object_or_404(CDICRecord, id=assessment_id)

    # Generate PDF
    generator = CDICAssessmentPDFGenerator()
    file_path = generator.generate(assessment_id)

    # Serve file
    filename = f"CDIC_Record_{assessment_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@login_required(login_url='user-login')
@ratelimit(key='user', rate='100/h')
def download_gpa_assessment_pdf(request, assessment_id):
    """Download GPA Assessment PDF"""
    assessment = get_object_or_404(GeneralPaediatricAssessment, id=assessment_id)

    # Generate PDF
    generator = GPAAssessmentPDFGenerator()
    file_path = generator.generate(assessment_id)

    # Serve file
    filename = f"GPA_Assessment_{assessment_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


# Helper Functions

def get_validated_report_path(file_id):
    """
    Validate and return safe file path

    Args:
        file_id: File identifier with extension

    Returns:
        str: Validated absolute file path

    Raises:
        Http404: If file_id is invalid or path is unsafe
    """
    # Validate UUID format (basic check)
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(pdf|xlsx)$'

    if not re.match(uuid_pattern, file_id, re.IGNORECASE):
        raise Http404("Invalid file identifier")

    # Construct path
    temp_dir = os.path.join(settings.MEDIA_ROOT, 'reports', 'temp')
    file_path = os.path.join(temp_dir, file_id)

    # Verify path is within allowed directory (prevent path traversal)
    if not is_safe_path(file_path, temp_dir):
        raise PermissionDenied("Invalid file path")

    return file_path


def is_safe_path(file_path, allowed_dir):
    """
    Check if file path is within allowed directory

    Args:
        file_path: File path to check
        allowed_dir: Allowed base directory

    Returns:
        bool: True if safe, False otherwise
    """
    try:
        # Resolve to absolute paths
        file_abs = os.path.abspath(file_path)
        dir_abs = os.path.abspath(allowed_dir)

        # Check common path
        return os.path.commonpath([file_abs, dir_abs]) == dir_abs
    except (ValueError, TypeError):
        return False
