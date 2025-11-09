"""
Excel Report Generation Utilities

This module contains Excel generator classes for creating data export reports
using openpyxl for research and statistical analysis.
"""

import os
import uuid
from datetime import datetime

from django.conf import settings
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

from patients.models import (
    Patient, GMAssessment, HINEAssessment,
    DevelopmentalAssessment, CDICRecord, GeneralPaediatricAssessment
)


class ExcelReportGenerator:
    """Generate Excel reports for research data exports"""

    def __init__(self):
        """Initialize Excel generator"""
        self.workbook = None

    def create_workbook(self):
        """Initialize new workbook"""
        self.workbook = Workbook()
        # Remove default sheet
        if 'Sheet' in self.workbook.sheetnames:
            del self.workbook['Sheet']

    def style_header_row(self, worksheet, row_num=1):
        """Apply styling to header row"""
        header_fill = PatternFill(
            start_color='4472C4',
            end_color='4472C4',
            fill_type='solid'
        )
        header_font = Font(bold=True, color='FFFFFF', size=11)
        header_alignment = Alignment(horizontal='center', vertical='center')

        for cell in worksheet[row_num]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment

    def auto_adjust_column_widths(self, worksheet):
        """Auto-adjust column widths based on content"""
        for column in worksheet.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)

            for cell in column:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass

            adjusted_width = min(max_length + 2, 50)  # Max width 50
            worksheet.column_dimensions[column_letter].width = adjusted_width

    def add_patients_sheet(self, workbook, queryset):
        """
        Add Patients worksheet

        Args:
            workbook: Openpyxl workbook object
            queryset: Patient queryset
        """
        ws = workbook.create_sheet("Patients")

        # Headers
        headers = [
            'ID', 'Patient Name', 'BHT Number', 'NNC Number', 'PTC Number',
            'PC Number', 'PIN', 'Gender', 'Date of Birth', 'Gestational Age (weeks)',
            'Gestational Age (days)', 'Birth Weight (g)', 'APGAR 1min', 'APGAR 5min',
            'Mode of Delivery', 'Created At'
        ]
        ws.append(headers)

        # Style header
        self.style_header_row(ws)

        # Data rows
        for patient in queryset:
            row = [
                patient.id,
                patient.patient_name or '',
                patient.bht_number or '',
                patient.nnc_number or '',
                patient.ptc_number or '',
                patient.pc_number or '',
                patient.pin or '',
                patient.gender or '',
                patient.date_of_birth,
                patient.gestational_age_weeks,
                patient.gestational_age_days,
                patient.birth_weight_g,
                patient.apgar_1_min,
                patient.apgar_5_min,
                patient.mode_of_delivery or '',
                patient.created_at,
            ]
            ws.append(row)

        # Auto-adjust widths
        self.auto_adjust_column_widths(ws)

    def add_gm_assessments_sheet(self, workbook, queryset):
        """Add GM Assessments worksheet"""
        ws = workbook.create_sheet("GM Assessments")

        # Headers
        headers = [
            'ID', 'Patient BHT', 'Patient Name', 'Assessment Date',
            'Age at Assessment (weeks)', 'Age at Assessment (days)',
            'Classification', 'Created At'
        ]
        ws.append(headers)

        # Style header
        self.style_header_row(ws)

        # Data rows
        for assessment in queryset.select_related('patient_id'):
            row = [
                assessment.id,
                assessment.patient_id.bht_number or '',
                assessment.patient_id.patient_name or '',
                assessment.assessment_date,
                assessment.age_at_assessment_weeks,
                assessment.age_at_assessment_days,
                assessment.classification or '',
                assessment.created_at,
            ]
            ws.append(row)

        # Auto-adjust widths
        self.auto_adjust_column_widths(ws)

    def add_hine_assessments_sheet(self, workbook, queryset):
        """Add HINE Assessments worksheet"""
        ws = workbook.create_sheet("HINE Assessments")

        # Headers
        headers = [
            'ID', 'Patient BHT', 'Patient Name', 'Assessment Date',
            'Age at Assessment (weeks)', 'Age at Assessment (days)',
            'Total Score', 'Created At'
        ]
        ws.append(headers)

        # Style header
        self.style_header_row(ws)

        # Data rows
        for assessment in queryset.select_related('patient_id'):
            row = [
                assessment.id,
                assessment.patient_id.bht_number or '',
                assessment.patient_id.patient_name or '',
                assessment.assessment_date,
                assessment.age_at_assessment_weeks,
                assessment.age_at_assessment_days,
                getattr(assessment, 'total_score', ''),
                assessment.created_at,
            ]
            ws.append(row)

        # Auto-adjust widths
        self.auto_adjust_column_widths(ws)

    def generate(self, output_path=None, start_date=None, end_date=None, parameters=None):
        """
        Generate Excel report with selected data

        Args:
            output_path: Optional output file path
            start_date: Optional start date filter
            end_date: Optional end date filter
            parameters: Dict of what to include {'patients': bool, 'gm_assessments': bool, ...}

        Returns:
            tuple: (file_path, metadata dict with counts)
        """
        if parameters is None:
            parameters = {
                'patients': True,
                'gm_assessments': True,
                'hine_assessments': True,
            }

        # Generate output path
        if output_path is None:
            filename = f"report_{uuid.uuid4()}.xlsx"
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'reports', 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            output_path = os.path.join(temp_dir, filename)

        # Create workbook
        self.create_workbook()

        metadata = {'sheets': {}}

        # Add sheets based on parameters
        if parameters.get('patients', False):
            queryset = Patient.objects.all()
            if start_date:
                queryset = queryset.filter(created_at__gte=start_date)
            if end_date:
                queryset = queryset.filter(created_at__lte=end_date)

            self.add_patients_sheet(self.workbook, queryset)
            metadata['sheets']['Patients'] = queryset.count()

        if parameters.get('gm_assessments', False):
            queryset = GMAssessment.objects.all()
            if start_date:
                queryset = queryset.filter(assessment_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(assessment_date__lte=end_date)

            self.add_gm_assessments_sheet(self.workbook, queryset)
            metadata['sheets']['GM Assessments'] = queryset.count()

        if parameters.get('hine_assessments', False):
            queryset = HINEAssessment.objects.all()
            if start_date:
                queryset = queryset.filter(assessment_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(assessment_date__lte=end_date)

            self.add_hine_assessments_sheet(self.workbook, queryset)
            metadata['sheets']['HINE Assessments'] = queryset.count()

        # Save workbook
        self.workbook.save(output_path)

        return output_path, metadata
