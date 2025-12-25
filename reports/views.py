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
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')

        # Parse dates from string to date objects
        start_date = None
        end_date = None
        try:
            if start_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            context = {
                'error': 'Invalid date format. Please use YYYY-MM-DD format.',
                'start_date': start_date_str,
                'end_date': end_date_str
            }
            return render(request, 'reports/builder.html', context)

        # Parse anonymization setting
        anonymize_data = request.POST.get('anonymize_data', 'off') == 'on'

        # Parse selected patient fields (if field selection is used)
        patient_fields = request.POST.getlist('patient_fields')
        # If no specific fields selected, use all fields
        if not patient_fields:
            patient_fields = [
                'id', 'baby_name', 'mother_name', 'bht', 'nnc_no', 'ptc_no', 'pc_no', 'pin', 'disk_no',
                'sex', 'dob_tob', 'pog_wks', 'pog_days', 'mode_of_delivery',
                'apgar_1', 'apgar_5', 'apgar_10',
                'resuscitated', 'created_at', 'updated_at'
            ]

        # Parse advanced filters
        filters = {}

        # Gestational age filter (POG)
        pog_min = request.POST.get('pog_min')
        pog_max = request.POST.get('pog_max')
        if pog_min:
            try:
                filters['pog_min'] = int(pog_min)
            except ValueError:
                pass
        if pog_max:
            try:
                filters['pog_max'] = int(pog_max)
            except ValueError:
                pass

        # APGAR score filter
        apgar_timepoint = request.POST.get('apgar_timepoint')
        apgar_min = request.POST.get('apgar_min')
        apgar_max = request.POST.get('apgar_max')
        if apgar_timepoint and (apgar_min or apgar_max):
            filters['apgar_timepoint'] = apgar_timepoint
            if apgar_min:
                try:
                    filters['apgar_min'] = int(apgar_min)
                except ValueError:
                    pass
            if apgar_max:
                try:
                    filters['apgar_max'] = int(apgar_max)
                except ValueError:
                    pass

        # GM Assessment diagnosis filter
        gm_diagnosis = request.POST.getlist('gm_diagnosis')
        if gm_diagnosis:
            filters['gm_diagnosis'] = gm_diagnosis

        # HINE Assessment score filter
        hine_score_min = request.POST.get('hine_score_min')
        hine_score_max = request.POST.get('hine_score_max')
        if hine_score_min:
            try:
                filters['hine_score_min'] = int(hine_score_min)
            except ValueError:
                pass
        if hine_score_max:
            try:
                filters['hine_score_max'] = int(hine_score_max)
            except ValueError:
                pass

        # Gender filter
        gender = request.POST.getlist('gender')
        if gender:
            filters['gender'] = gender

        # Resuscitation status filter
        resuscitation_status = request.POST.getlist('resuscitation_status')
        if resuscitation_status:
            filters['resuscitation_status'] = resuscitation_status

        # Parse parameters
        parameters = {
            'patients': request.POST.get('patients', 'off') == 'on',
            'gm_assessments': request.POST.get('gm_assessments', 'off') == 'on',
            'hine_assessments': request.POST.get('hine_assessments', 'off') == 'on',
            'developmental_assessments': request.POST.get('developmental_assessments', 'off') == 'on',
            'cdic_records': request.POST.get('cdic_records', 'off') == 'on',
            'gpa_assessments': request.POST.get('gpa_assessments', 'off') == 'on',
            'anonymize_data': anonymize_data,
            'patient_fields': patient_fields,
            'filters': filters,
        }

        # Generate Excel research export (synchronous for now)
        try:
            generator = ExcelReportGenerator()
            file_path, metadata = generator.generate(
                start_date=start_date,
                end_date=end_date,
                parameters=parameters
            )
            # Extract just the filename (with .xlsx extension already included)
            file_id = os.path.basename(file_path)

            # Add success message with metadata
            from django.contrib import messages
            total_records = metadata.get('total_records', 0)
            sheet_count = len(metadata.get('sheets', {}))
            messages.success(
                request,
                f'Report generated successfully! {total_records} total records across {sheet_count} sheets.'
            )

            return redirect('reports:download', file_id=file_id)

        except Exception as e:
            import logging
            logger = logging.getLogger('django')
            logger.error(f'Report generation error: {str(e)}', exc_info=True)

            context = {
                'error': f'Error generating report: {str(e)}',
                'start_date': start_date.isoformat() if start_date else '',
                'end_date': end_date.isoformat() if end_date else ''
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
    """Display report generation history from temp directory"""
    reports = []
    temp_dir = os.path.join(settings.MEDIA_ROOT, 'reports', 'temp')

    try:
        # Ensure directory exists
        os.makedirs(temp_dir, exist_ok=True)

        # Scan for report files
        if os.path.exists(temp_dir):
            for filename in os.listdir(temp_dir):
                if filename.endswith('.xlsx') or filename.endswith('.pdf'):
                    file_path = os.path.join(temp_dir, filename)
                    file_stat = os.stat(file_path)

                    # Calculate file age
                    file_age = datetime.now() - datetime.fromtimestamp(file_stat.st_mtime)
                    hours_old = file_age.total_seconds() / 3600

                    # Only show files less than 24 hours old
                    if hours_old < 24:
                        reports.append({
                            'filename': filename,
                            'file_id': filename,
                            'size': file_stat.st_size,
                            'size_mb': round(file_stat.st_size / (1024 * 1024), 2),
                            'created': datetime.fromtimestamp(file_stat.st_mtime),
                            'hours_old': round(hours_old, 1),
                            'expires_in': round(24 - hours_old, 1),
                            'type': 'Excel' if filename.endswith('.xlsx') else 'PDF',
                        })
                    else:
                        # Delete expired files
                        try:
                            os.remove(file_path)
                        except:
                            pass

        # Sort by creation time (newest first)
        reports.sort(key=lambda x: x['created'], reverse=True)

    except Exception as e:
        import logging
        logger = logging.getLogger('django')
        logger.error(f'Error reading report history: {str(e)}')

    context = {
        'reports': reports,
        'total_reports': len(reports),
    }
    return render(request, 'reports/history.html', context)


@login_required(login_url='user-login')
@ratelimit(key='user', rate='50/h', method='POST')
def delete_report(request, file_id):
    """
    Delete a generated report file

    Args:
        file_id: File identifier (UUID.pdf or UUID.xlsx)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required'}, status=405)

    try:
        # Validate file_id format
        file_path = get_validated_report_path(file_id)

        if not os.path.exists(file_path):
            return JsonResponse({'success': False, 'error': 'Report file not found'}, status=404)

        # Delete the file
        os.remove(file_path)

        return JsonResponse({
            'success': True,
            'message': 'Report deleted successfully'
        })

    except Http404 as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=404)
    except PermissionDenied as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=403)
    except Exception as e:
        import logging
        logger = logging.getLogger('django')
        logger.error(f'Error deleting report {file_id}: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)


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

    # Serve file with proper resource management
    with open(file_path, 'rb') as file_handle:
        response = FileResponse(file_handle.read(), content_type=content_type)
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

    # Serve file with proper resource management
    filename = f"GM_Assessment_{assessment_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    with open(file_path, 'rb') as file_handle:
        response = FileResponse(file_handle.read(), content_type='application/pdf')
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

    # Serve file with proper resource management
    filename = f"HINE_Assessment_{assessment_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    with open(file_path, 'rb') as file_handle:
        response = FileResponse(file_handle.read(), content_type='application/pdf')
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

    # Serve file with proper resource management
    filename = f"DA_Assessment_{assessment_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    with open(file_path, 'rb') as file_handle:
        response = FileResponse(file_handle.read(), content_type='application/pdf')
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

    # Serve file with proper resource management
    filename = f"CDIC_Record_{assessment_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    with open(file_path, 'rb') as file_handle:
        response = FileResponse(file_handle.read(), content_type='application/pdf')
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

    # Serve file with proper resource management
    filename = f"GPA_Assessment_{assessment_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    with open(file_path, 'rb') as file_handle:
        response = FileResponse(file_handle.read(), content_type='application/pdf')
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
    # Validate filename format (allows report_ prefix and UUID)
    # Matches: report_uuid.xlsx or uuid.pdf or uuid.xlsx
    filename_pattern = r'^(report_)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(pdf|xlsx)$'

    if not re.match(filename_pattern, file_id, re.IGNORECASE):
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
