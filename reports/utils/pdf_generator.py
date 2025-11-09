"""
PDF Report Generation Utilities

This module contains PDF generator classes for creating professional medical reports
using reportlab. All generators inherit from BasePDFGenerator for consistent styling.
"""

import os
import uuid
from datetime import datetime
from io import BytesIO

from django.conf import settings
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, PageBreak, Image as RLImage
)
from reportlab.pdfgen import canvas

from reports.models import ReportTemplate, ReportConfig
from patients.models import (
    Patient, GMAssessment, HINEAssessment,
    DevelopmentalAssessment, CDICRecord, GeneralPaediatricAssessment
)


class BasePDFGenerator:
    """Base class for PDF generation with common utilities"""

    def __init__(self, template=None):
        """
        Initialize PDF generator with optional template

        Args:
            template: ReportTemplate instance (uses default if None)
        """
        self.template = template or self.get_template()
        self.styles = self.get_styles()
        self.page_size = self.get_page_size()

    def get_template(self):
        """Load active default template"""
        try:
            return ReportTemplate.objects.filter(
                is_active=True,
                is_default=True
            ).first()
        except ReportTemplate.DoesNotExist:
            return None

    def get_page_size(self):
        """Get configured page size"""
        try:
            config = ReportConfig.objects.get(key='pdf_page_size')
            page_size_name = config.get_value()
            return letter if page_size_name == 'LETTER' else A4
        except ReportConfig.DoesNotExist:
            return A4

    def get_styles(self):
        """Configure paragraph and text styles"""
        styles = getSampleStyleSheet()

        # Custom title style
        styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            alignment=TA_CENTER
        ))

        # Custom heading style
        styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#34495e'),
            spaceAfter=10,
            spaceBefore=12
        ))

        # Custom subheading style
        styles.add(ParagraphStyle(
            name='CustomSubHeading',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#7f8c8d'),
            spaceAfter=8,
            spaceBefore=10
        ))

        return styles

    def create_header_footer(self, canvas_obj, doc):
        """Draw header and footer on each page"""
        canvas_obj.saveState()

        # Draw header
        if self.template and self.template.header_text:
            # Simple text header (strip HTML tags for PDF)
            from django.utils.html import strip_tags
            header_text = strip_tags(self.template.header_text)
            canvas_obj.setFont('Helvetica-Bold', 10)
            canvas_obj.drawCentredString(
                doc.width / 2 + doc.leftMargin,
                doc.height + doc.topMargin + 0.5 * inch,
                header_text[:100]  # Limit length
            )

        # Draw logo if available
        if self.template and self.template.logo:
            try:
                logo_path = self.template.logo.path
                if os.path.exists(logo_path):
                    canvas_obj.drawImage(
                        logo_path,
                        doc.leftMargin,
                        doc.height + doc.topMargin + 0.3 * inch,
                        width=1.5 * inch,
                        height=0.5 * inch,
                        preserveAspectRatio=True
                    )
            except Exception:
                pass  # Skip logo if error

        # Draw footer
        if self.template and self.template.footer_text:
            from django.utils.html import strip_tags
            footer_text = strip_tags(self.template.footer_text)
            canvas_obj.setFont('Helvetica', 8)
            canvas_obj.drawCentredString(
                doc.width / 2 + doc.leftMargin,
                0.5 * inch,
                footer_text[:150]
            )

        # Page number
        canvas_obj.setFont('Helvetica', 9)
        canvas_obj.drawRightString(
            doc.width + doc.leftMargin,
            0.5 * inch,
            f"Page {doc.page}"
        )

        # Generation timestamp
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.drawString(
            doc.leftMargin,
            0.5 * inch,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        canvas_obj.restoreState()

    def get_temp_path(self, filename=None):
        """Generate temp file path for PDF"""
        if filename is None:
            filename = f"{uuid.uuid4()}.pdf"

        temp_dir = os.path.join(settings.MEDIA_ROOT, 'reports', 'temp')
        os.makedirs(temp_dir, exist_ok=True)

        return os.path.join(temp_dir, filename)


class PatientPDFGenerator(BasePDFGenerator):
    """Generate comprehensive patient report PDF"""

    def generate(self, patient_id, start_date=None, end_date=None, output_path=None):
        """
        Generate comprehensive patient report

        Args:
            patient_id: Patient ID
            start_date: Optional start date for filtering assessments
            end_date: Optional end date for filtering assessments
            output_path: Optional output file path (auto-generated if None)

        Returns:
            str: Path to generated PDF file
        """
        # Load patient data
        try:
            patient = Patient.objects.select_related(
                'user_id'
            ).get(id=patient_id)
        except Patient.DoesNotExist:
            raise ValueError(f"Patient with ID {patient_id} not found")

        # Generate output path
        if output_path is None:
            filename = f"patient_{patient_id}_{uuid.uuid4()}.pdf"
            output_path = self.get_temp_path(filename)

        # Create PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=100,
            bottomMargin=72
        )

        # Build content
        story = []

        # Title
        story.append(Paragraph(
            f"Patient Report: {patient.patient_name or 'N/A'}",
            self.styles['CustomTitle']
        ))
        story.append(Spacer(1, 0.2 * inch))

        # Patient Demographics
        story.append(Paragraph("Patient Information", self.styles['CustomHeading']))
        demo_data = [
            ['Patient Name:', patient.patient_name or 'N/A'],
            ['Gender:', patient.gender or 'N/A'],
            ['Date of Birth:', patient.date_of_birth.strftime('%Y-%m-%d') if patient.date_of_birth else 'N/A'],
            ['BHT Number:', patient.bht_number or 'N/A'],
            ['NNC Number:', patient.nnc_number or 'N/A'],
        ]

        demo_table = Table(demo_data, colWidths=[2.5 * inch, 3.5 * inch])
        demo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(demo_table)
        story.append(Spacer(1, 0.3 * inch))

        # Birth Data
        story.append(Paragraph("Birth Information", self.styles['CustomHeading']))
        birth_data = [
            ['Gestational Age:', f"{patient.gestational_age_weeks} weeks {patient.gestational_age_days} days" if patient.gestational_age_weeks else 'N/A'],
            ['Birth Weight:', f"{patient.birth_weight_g} g" if patient.birth_weight_g else 'N/A'],
            ['APGAR 1 min:', str(patient.apgar_1_min) if patient.apgar_1_min is not None else 'N/A'],
            ['APGAR 5 min:', str(patient.apgar_5_min) if patient.apgar_5_min is not None else 'N/A'],
            ['Mode of Delivery:', patient.mode_of_delivery or 'N/A'],
        ]

        birth_table = Table(birth_data, colWidths=[2.5 * inch, 3.5 * inch])
        birth_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(birth_table)
        story.append(Spacer(1, 0.3 * inch))

        # Build PDF
        doc.build(story, onFirstPage=self.create_header_footer, onLaterPages=self.create_header_footer)

        return output_path


class GMAssessmentPDFGenerator(BasePDFGenerator):
    """Generate GM Assessment report PDF"""

    def generate(self, assessment_id, output_path=None):
        """
        Generate GM Assessment PDF

        Args:
            assessment_id: GMAssessment ID
            output_path: Optional output file path

        Returns:
            str: Path to generated PDF file
        """
        # Load assessment with patient data
        try:
            assessment = GMAssessment.objects.select_related('patient_id').get(id=assessment_id)
        except GMAssessment.DoesNotExist:
            raise ValueError(f"GM Assessment with ID {assessment_id} not found")

        # Generate output path
        if output_path is None:
            filename = f"gm_assessment_{assessment_id}_{uuid.uuid4()}.pdf"
            output_path = self.get_temp_path(filename)

        # Create PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=100,
            bottomMargin=72
        )

        # Build content
        story = []

        # Title
        story.append(Paragraph(
            "GM Assessment Report",
            self.styles['CustomTitle']
        ))
        story.append(Spacer(1, 0.2 * inch))

        # Patient Info
        patient = assessment.patient_id
        story.append(Paragraph(f"Patient: {patient.patient_name or 'N/A'}", self.styles['Normal']))
        story.append(Paragraph(f"BHT: {patient.bht_number or 'N/A'}", self.styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        # Assessment Details
        story.append(Paragraph("Assessment Details", self.styles['CustomHeading']))
        assessment_data = [
            ['Assessment Date:', assessment.assessment_date.strftime('%Y-%m-%d') if assessment.assessment_date else 'N/A'],
            ['Age at Assessment:', f"{assessment.age_at_assessment_weeks} weeks {assessment.age_at_assessment_days} days" if assessment.age_at_assessment_weeks else 'N/A'],
            ['Classification:', assessment.classification or 'N/A'],
        ]

        assessment_table = Table(assessment_data, colWidths=[2.5 * inch, 3.5 * inch])
        assessment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        story.append(assessment_table)

        # Build PDF
        doc.build(story, onFirstPage=self.create_header_footer, onLaterPages=self.create_header_footer)

        return output_path


# Similar generators for other assessment types
class HINEAssessmentPDFGenerator(GMAssessmentPDFGenerator):
    """Generate HINE Assessment report PDF - inherits from GM for similar structure"""
    pass


class DAAssessmentPDFGenerator(GMAssessmentPDFGenerator):
    """Generate Developmental Assessment report PDF"""
    pass


class CDICAssessmentPDFGenerator(GMAssessmentPDFGenerator):
    """Generate CDIC Record report PDF"""
    pass


class GPAAssessmentPDFGenerator(GMAssessmentPDFGenerator):
    """Generate GPA Assessment report PDF"""
    pass
