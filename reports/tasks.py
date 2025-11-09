"""
Celery tasks for asynchronous report generation

This module contains Celery tasks for generating reports asynchronously
to prevent UI blocking for large datasets.
"""

import os
import logging
from datetime import datetime, timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings

from reports.utils.pdf_generator import PatientPDFGenerator
from reports.utils.excel_generator import ExcelReportGenerator
from users.models import CustomUser

logger = logging.getLogger('ndas.reports')


@shared_task(bind=True, soft_time_limit=600)
def generate_patient_pdf_task(self, user_id, patient_id, start_date=None, end_date=None, params=None):
    """
    Celery task for generating patient PDF report

    Args:
        user_id: User requesting the report
        patient_id: Patient ID
        start_date: Optional start date filter
        end_date: Optional end date filter
        params: Optional report parameters

    Returns:
        dict: {'status': 'success'|'error', 'file_id': str, 'filename': str}
    """
    try:
        # Update state to PROGRESS
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': 'Initializing PDF generation...'}
        )

        # Get user for logging
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            user = None

        logger.info(f"Starting PDF generation for patient {patient_id} by user {user_id}")

        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={'current': 30, 'total': 100, 'status': 'Loading patient data...'}
        )

        # Generate PDF
        generator = PatientPDFGenerator()
        file_path = generator.generate(
            patient_id=patient_id,
            start_date=start_date,
            end_date=end_date
        )

        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={'current': 90, 'total': 100, 'status': 'Finalizing PDF...'}
        )

        # Extract file ID from path
        file_id = os.path.basename(file_path).replace('.pdf', '')
        filename = f"patient_{patient_id}_report.pdf"

        logger.info(f"PDF generated successfully: {file_id} for patient {patient_id}")

        return {
            'status': 'success',
            'file_id': file_id,
            'filename': filename
        }

    except SoftTimeLimitExceeded:
        logger.error(f"PDF generation timeout for patient {patient_id}")
        return {
            'status': 'error',
            'message': 'Report generation timeout. Please try with a smaller date range.'
        }
    except Exception as e:
        logger.error(f"PDF generation error for patient {patient_id}: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error generating report: {str(e)}'
        }


@shared_task(bind=True, soft_time_limit=600)
def generate_excel_report_task(self, user_id, start_date=None, end_date=None, params=None):
    """
    Celery task for generating Excel research export

    Args:
        user_id: User requesting the report
        start_date: Optional start date filter
        end_date: Optional end date filter
        params: Dict of data to include

    Returns:
        dict: {'status': 'success'|'error', 'file_id': str, 'filename': str, 'metadata': dict}
    """
    try:
        # Update state to PROGRESS
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': 'Initializing Excel generation...'}
        )

        logger.info(f"Starting Excel generation by user {user_id}")

        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={'current': 30, 'total': 100, 'status': 'Querying database...'}
        )

        # Generate Excel
        generator = ExcelReportGenerator()
        file_path, metadata = generator.generate(
            start_date=start_date,
            end_date=end_date,
            parameters=params or {}
        )

        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={'current': 90, 'total': 100, 'status': 'Finalizing Excel workbook...'}
        )

        # Extract file ID from path
        file_id = os.path.basename(file_path).replace('.xlsx', '')
        filename = f"research_export_{datetime.now().strftime('%Y%m%d')}.xlsx"

        logger.info(f"Excel generated successfully: {file_id} with {metadata}")

        return {
            'status': 'success',
            'file_id': file_id,
            'filename': filename,
            'metadata': metadata
        }

    except SoftTimeLimitExceeded:
        logger.error(f"Excel generation timeout for user {user_id}")
        return {
            'status': 'error',
            'message': 'Report generation timeout. Please try with a smaller date range.'
        }
    except Exception as e:
        logger.error(f"Excel generation error: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error generating report: {str(e)}'
        }


@shared_task
def cleanup_old_reports():
    """
    Celery task to clean up old temporary report files

    Runs daily via Celery beat to delete files older than configured retention period.

    Returns:
        dict: {'deleted': int, 'failed': int, 'errors': list}
    """
    try:
        from reports.models import ReportConfig

        # Get retention hours from config
        try:
            retention_config = ReportConfig.objects.get(key='temp_file_retention_hours')
            retention_hours = retention_config.get_value()
        except ReportConfig.DoesNotExist:
            retention_hours = 24  # Default 24 hours

        temp_dir = os.path.join(settings.MEDIA_ROOT, 'reports', 'temp')

        if not os.path.exists(temp_dir):
            logger.info("Temp directory does not exist, skipping cleanup")
            return {'deleted': 0, 'failed': 0, 'errors': []}

        deleted_count = 0
        failed_count = 0
        errors = []

        cutoff_time = datetime.now() - timedelta(hours=retention_hours)

        # Scan and delete old files
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)

            # Verify it's a file and within temp directory
            if not os.path.isfile(file_path):
                continue

            # Check file age
            try:
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                if file_mtime < cutoff_time:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Deleted old report file: {filename}")

            except Exception as e:
                failed_count += 1
                errors.append(f"{filename}: {str(e)}")
                logger.error(f"Failed to delete {filename}: {str(e)}")

        logger.info(f"Cleanup completed: {deleted_count} deleted, {failed_count} failed")

        return {
            'deleted': deleted_count,
            'failed': failed_count,
            'errors': errors
        }

    except Exception as e:
        logger.error(f"Cleanup task error: {str(e)}")
        return {
            'deleted': 0,
            'failed': 0,
            'errors': [str(e)]
        }
