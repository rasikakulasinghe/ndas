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

    def __init__(self, template=None, institution=None):
        """
        Initialize PDF generator with optional template and institution branding.

        Args:
            template: ReportTemplate instance (uses default if None)
            institution: Institution instance for branding injection (Story 3.4 — FR59)
        """
        self.template = template or self.get_template()
        self.institution = institution  # Phase 2: institution-specific branding (Story 3.4)
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

        # Draw header — institution branding takes priority over template (FR59)
        if self.institution:
            # Institution name as centred header text
            canvas_obj.setFont('Helvetica-Bold', 10)
            canvas_obj.drawCentredString(
                doc.width / 2 + doc.leftMargin,
                doc.height + doc.topMargin + 0.5 * inch,
                str(self.institution.name)[:100]
            )
            # Institution logo if available (AC #2: omit gracefully when absent)
            if self.institution.logo:
                try:
                    logo_path = self.institution.logo.path
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
                    pass  # AC #2: no broken placeholder — graceful skip
        else:
            # Fall back to template-based header when no institution context
            if self.template and self.template.header_text:
                from django.utils.html import strip_tags
                header_text = strip_tags(self.template.header_text)
                canvas_obj.setFont('Helvetica-Bold', 10)
                canvas_obj.drawCentredString(
                    doc.width / 2 + doc.leftMargin,
                    doc.height + doc.topMargin + 0.5 * inch,
                    header_text[:100]
                )

            # Draw template logo if available
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
        # Load patient data with optimized query (prefetch all related assessments)
        try:
            patient = Patient.objects.select_related(
                'added_by', 'last_edit_by'
            ).prefetch_related(
                'gm_assessments',
                'hine_assessments',
                'developmental_assessments',
                'cdic_records',
                'gpa_assessments',
                'videos',
                'attachments'
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
            f"Patient Report: {patient.baby_name or 'N/A'}",
            self.styles['CustomTitle']
        ))
        story.append(Spacer(1, 0.2 * inch))

        # Patient Demographics
        story.append(Paragraph("Patient Information", self.styles['CustomHeading']))
        demo_data = [
            ['Patient Name:', patient.baby_name or 'N/A'],
            ['Gender:', patient.gender or 'N/A'],
            ['Date of Birth:', patient.dob_tob.strftime('%Y-%m-%d') if patient.dob_tob else 'N/A'],
            ['BHT Number:', patient.bht or 'N/A'],
            ['NNC Number:', patient.nnc_no or 'N/A'],
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
            ['Gestational Age:', f"{patient.pog_wks} weeks {patient.pog_days} days" if patient.pog_wks else 'N/A'],
            ['Birth Weight:', f"{patient.birth_weight} g" if patient.birth_weight else 'N/A'],
            ['APGAR 1 min:', str(patient.apgar_1) if patient.apgar_1 is not None else 'N/A'],
            ['APGAR 5 min:', str(patient.apgar_5) if patient.apgar_5 is not None else 'N/A'],
            ['Mode of Delivery:', patient.mo_delivery or 'N/A'],
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
            assessment = GMAssessment.objects.select_related('patient').prefetch_related('diagnosis').get(id=assessment_id)
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
        patient = assessment.patient
        story.append(Paragraph(f"Patient: {patient.baby_name or 'N/A'}", self.styles['Normal']))
        story.append(Paragraph(f"BHT: {patient.bht or 'N/A'}", self.styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        # Assessment Details
        story.append(Paragraph("Assessment Details", self.styles['CustomHeading']))

        # Calculate age at assessment
        age_at_assessment = 'N/A'
        if patient.dob_tob and assessment.date_of_assessment:
            age_delta = assessment.date_of_assessment.date() - patient.dob_tob.date()
            age_weeks = age_delta.days // 7
            age_days = age_delta.days % 7
            age_at_assessment = f"{age_weeks} weeks {age_days} days"

        assessment_data = [
            ['Assessment Date:', assessment.date_of_assessment.strftime('%Y-%m-%d %H:%M') if assessment.date_of_assessment else 'N/A'],
            ['Age at Assessment:', age_at_assessment],
            ['Diagnosis Conclusion:', assessment.get_diagnosis_conclusion_display() if assessment.diagnosis_conclusion else 'N/A'],
            ['Management Plan:', assessment.management_plan or 'N/A'],
        ]

        assessment_table = Table(assessment_data, colWidths=[2.5 * inch, 3.5 * inch])
        assessment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(assessment_table)
        story.append(Spacer(1, 0.2 * inch))

        # Diagnosis details if available
        diagnosis_list = assessment.diagnosis.all()
        if diagnosis_list or assessment.diagnosis_other:
            story.append(Paragraph("Diagnosis Details", self.styles['CustomHeading']))
            if diagnosis_list:
                for dx in diagnosis_list:
                    story.append(Paragraph(f"• {dx.name}", self.styles['Normal']))
            if assessment.diagnosis_other:
                story.append(Paragraph(f"Other: {assessment.diagnosis_other}", self.styles['Normal']))
            story.append(Spacer(1, 0.2 * inch))

        # Follow-up information
        if assessment.next_assessment_date:
            story.append(Paragraph("Follow-up Planning", self.styles['CustomHeading']))
            followup_data = [
                ['Next Assessment Date:', assessment.next_assessment_date.strftime('%Y-%m-%d')],
                ['Parent Informed:', 'Yes' if assessment.parent_informed else 'No'],
            ]
            followup_table = Table(followup_data, colWidths=[2.5 * inch, 3.5 * inch])
            followup_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e3f2fd')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ]))
            story.append(followup_table)

        # Build PDF
        doc.build(story, onFirstPage=self.create_header_footer, onLaterPages=self.create_header_footer)

        return output_path


class HINEAssessmentPDFGenerator(BasePDFGenerator):
    """Generate HINE Assessment report PDF"""

    def generate(self, assessment_id, output_path=None):
        """Generate HINE Assessment PDF"""
        try:
            assessment = HINEAssessment.objects.select_related('patient').get(id=assessment_id)
        except HINEAssessment.DoesNotExist:
            raise ValueError(f"HINE Assessment with ID {assessment_id} not found")

        if output_path is None:
            filename = f"hine_assessment_{assessment_id}_{uuid.uuid4()}.pdf"
            output_path = self.get_temp_path(filename)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=100,
            bottomMargin=72
        )

        story = []

        # Title
        story.append(Paragraph("HINE Assessment Report", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.2 * inch))

        # Patient Info
        patient = assessment.patient
        story.append(Paragraph(f"Patient: {patient.baby_name or 'N/A'}", self.styles['Normal']))
        story.append(Paragraph(f"BHT: {patient.bht or 'N/A'}", self.styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        # Assessment Details
        story.append(Paragraph("Assessment Details", self.styles['CustomHeading']))
        assessment_data = [
            ['Assessment Date:', assessment.date_of_assessment.strftime('%Y-%m-%d %H:%M') if assessment.date_of_assessment else 'N/A'],
            ['HINE Score:', str(assessment.score) if assessment.score is not None else 'N/A'],
            ['Assessed By:', assessment.assessment_done_by or 'N/A'],
            ['Comments:', assessment.comment or 'N/A'],
        ]

        assessment_table = Table(assessment_data, colWidths=[2.5 * inch, 3.5 * inch])
        assessment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(assessment_table)

        doc.build(story, onFirstPage=self.create_header_footer, onLaterPages=self.create_header_footer)
        return output_path


class DAAssessmentPDFGenerator(BasePDFGenerator):
    """Generate Developmental Assessment report PDF"""

    def generate(self, assessment_id, output_path=None):
        """Generate Developmental Assessment PDF"""
        try:
            assessment = DevelopmentalAssessment.objects.select_related('patient').get(id=assessment_id)
        except DevelopmentalAssessment.DoesNotExist:
            raise ValueError(f"Developmental Assessment with ID {assessment_id} not found")

        if output_path is None:
            filename = f"da_assessment_{assessment_id}_{uuid.uuid4()}.pdf"
            output_path = self.get_temp_path(filename)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=100,
            bottomMargin=72
        )

        story = []

        # Title
        story.append(Paragraph("Developmental Assessment Report", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.2 * inch))

        # Patient Info
        patient = assessment.patient
        story.append(Paragraph(f"Patient: {patient.baby_name or 'N/A'}", self.styles['Normal']))
        story.append(Paragraph(f"BHT: {patient.bht or 'N/A'}", self.styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        # Assessment Details
        story.append(Paragraph("Assessment Details", self.styles['CustomHeading']))
        story.append(Paragraph(f"Assessment Date: {assessment.date_of_assessment.strftime('%Y-%m-%d %H:%M') if assessment.date_of_assessment else 'N/A'}", self.styles['Normal']))
        story.append(Spacer(1, 0.1 * inch))

        # Gross Motor Domain
        story.append(Paragraph("Gross Motor Development", self.styles['CustomSubHeading']))
        gm_data = [
            ['Age Range:', f"{assessment.gm_age_from}-{assessment.gm_age_to} months" if assessment.gm_age_from else 'N/A'],
            ['Details:', assessment.gm_details or 'N/A'],
        ]
        gm_table = Table(gm_data, colWidths=[2 * inch, 4 * inch])
        gm_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(gm_table)
        story.append(Spacer(1, 0.2 * inch))

        # Fine Motor & Vision Domain
        story.append(Paragraph("Fine Motor & Vision Development", self.styles['CustomSubHeading']))
        fmv_data = [
            ['Age Range:', f"{assessment.fmv_age_from}-{assessment.fmv_age_to} months" if assessment.fmv_age_from else 'N/A'],
            ['Details:', assessment.fmv_details or 'N/A'],
        ]
        fmv_table = Table(fmv_data, colWidths=[2 * inch, 4 * inch])
        fmv_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(fmv_table)

        doc.build(story, onFirstPage=self.create_header_footer, onLaterPages=self.create_header_footer)
        return output_path


class CDICAssessmentPDFGenerator(BasePDFGenerator):
    """Generate CDIC Record report PDF"""

    def generate(self, assessment_id, output_path=None):
        """Generate CDIC Record PDF"""
        try:
            assessment = CDICRecord.objects.select_related('patient').get(id=assessment_id)
        except CDICRecord.DoesNotExist:
            raise ValueError(f"CDIC Record with ID {assessment_id} not found")

        if output_path is None:
            filename = f"cdic_record_{assessment_id}_{uuid.uuid4()}.pdf"
            output_path = self.get_temp_path(filename)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=100,
            bottomMargin=72
        )

        story = []

        # Title
        story.append(Paragraph("CDIC Record", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.2 * inch))

        # Patient Info
        patient = assessment.patient
        story.append(Paragraph(f"Patient: {patient.baby_name or 'N/A'}", self.styles['Normal']))
        story.append(Paragraph(f"BHT: {patient.bht or 'N/A'}", self.styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        # Assessment Details
        story.append(Paragraph("Assessment Details", self.styles['CustomHeading']))
        assessment_data = [
            ['Assessment Date:', assessment.assessment_date.strftime('%Y-%m-%d') if assessment.assessment_date else 'N/A'],
            ['Assessed By:', assessment.assessment_done_by or 'N/A'],
            ['Assessment:', assessment.assessment or 'N/A'],
            ['Today\'s Interventions:', assessment.today_interventions or 'N/A'],
        ]

        assessment_table = Table(assessment_data, colWidths=[2.5 * inch, 3.5 * inch])
        assessment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(assessment_table)
        story.append(Spacer(1, 0.2 * inch))

        # Follow-up Planning
        if assessment.next_appointment_date or assessment.next_appointment_plan:
            story.append(Paragraph("Follow-up Planning", self.styles['CustomHeading']))
            followup_data = [
                ['Next Appointment:', assessment.next_appointment_date.strftime('%Y-%m-%d %H:%M') if assessment.next_appointment_date else 'N/A'],
                ['Plan:', assessment.next_appointment_plan or 'N/A'],
            ]
            followup_table = Table(followup_data, colWidths=[2.5 * inch, 3.5 * inch])
            followup_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(followup_table)
            story.append(Spacer(1, 0.2 * inch))

        # Discharge Status
        if assessment.is_discharged:
            story.append(Paragraph("Discharge Information", self.styles['CustomHeading']))
            discharge_data = [
                ['Discharge Date:', assessment.discharge_date.strftime('%Y-%m-%d') if assessment.discharge_date else 'N/A'],
                ['Discharged By:', assessment.discharged_by or 'N/A'],
            ]
            discharge_table = Table(discharge_data, colWidths=[2.5 * inch, 3.5 * inch])
            discharge_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f5e9')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ]))
            story.append(discharge_table)

        doc.build(story, onFirstPage=self.create_header_footer, onLaterPages=self.create_header_footer)
        return output_path


class GPAAssessmentPDFGenerator(BasePDFGenerator):
    """Generate GPA Assessment report PDF"""

    def generate(self, assessment_id, output_path=None):
        """Generate General Paediatric Assessment PDF"""
        try:
            assessment = GeneralPaediatricAssessment.objects.select_related('patient').get(id=assessment_id)
        except GeneralPaediatricAssessment.DoesNotExist:
            raise ValueError(f"GPA Assessment with ID {assessment_id} not found")

        if output_path is None:
            filename = f"gpa_assessment_{assessment_id}_{uuid.uuid4()}.pdf"
            output_path = self.get_temp_path(filename)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=100,
            bottomMargin=72
        )

        story = []

        # Title
        story.append(Paragraph("General Paediatric Assessment", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.2 * inch))

        # Patient Info
        patient = assessment.patient
        story.append(Paragraph(f"Patient: {patient.baby_name or 'N/A'}", self.styles['Normal']))
        story.append(Paragraph(f"BHT: {patient.bht or 'N/A'}", self.styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        # Assessment Header
        story.append(Paragraph("Assessment Information", self.styles['CustomHeading']))
        header_data = [
            ['Assessment Date:', assessment.assessment_date.strftime('%Y-%m-%d %H:%M') if assessment.assessment_date else 'N/A'],
            ['Healthcare Provider:', assessment.healthcare_provider or 'N/A'],
        ]
        header_table = Table(header_data, colWidths=[2.5 * inch, 3.5 * inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.2 * inch))

        # Clinical Assessment
        story.append(Paragraph("Clinical Assessment", self.styles['CustomHeading']))
        clinical_data = [
            ['Current Problems:', assessment.current_problems or 'N/A'],
            ['Physical Examination:', assessment.physical_examination or 'N/A'],
            ['Investigation Summary:', assessment.investigation_summary or 'N/A'],
            ['Prescribed Medications:', assessment.prescribed_medications or 'N/A'],
            ['Next Plan/Goals:', assessment.next_plan or 'N/A'],
        ]
        clinical_table = Table(clinical_data, colWidths=[2.5 * inch, 3.5 * inch])
        clinical_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(clinical_table)
        story.append(Spacer(1, 0.2 * inch))

        # Follow-up
        if assessment.next_assessment_date:
            story.append(Paragraph("Follow-up Planning", self.styles['CustomHeading']))
            followup_data = [
                ['Next Assessment Date:', assessment.next_assessment_date.strftime('%Y-%m-%d %H:%M')],
            ]
            followup_table = Table(followup_data, colWidths=[2.5 * inch, 3.5 * inch])
            followup_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e3f2fd')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ]))
            story.append(followup_table)

        doc.build(story, onFirstPage=self.create_header_footer, onLaterPages=self.create_header_footer)
        return output_path
