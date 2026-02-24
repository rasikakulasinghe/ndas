# Story 2.5: Cross-Institution Aggregate Reports

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **superadmin**,
I want to export reports at three scopes — per-patient, per-institution aggregate, and cross-institution aggregate,
So that I can provide institutional stakeholders with their own data and maintain an overarching view of network-wide activity.

## Acceptance Criteria

1. **Given** the superadmin selects "per-institution aggregate" scope and a target institution
   **When** the export is triggered
   **Then** `ExcelReportGenerator.per_institution_aggregate()` generates a workbook containing only that institution's patient and assessment data

2. **Given** the superadmin selects "cross-institution aggregate" scope
   **When** the export is triggered
   **Then** `ExcelReportGenerator.cross_institution_aggregate()` generates a workbook spanning all institutions, with per-institution breakdown and a summary sheet

3. **Given** the superadmin exports a PDF report while viewing an institution's context
   **When** `BasePDFGenerator` renders the document
   **Then** the active institution's logo, name, and header are injected into the PDF output

4. **Given** an institution has zero patients at export time
   **When** it appears in the cross-institution aggregate export
   **Then** its row or sheet shows zeros without raising an exception

## Tasks / Subtasks

- [ ] Task 1: Extend `BasePDFGenerator` in `reports/utils/pdf_generator.py` (AC: #3)
  - [ ] Add `institution=None` parameter to `__init__(self, template=None, institution=None)`
  - [ ] Store as `self.institution = institution`
  - [ ] Modify `create_header_footer()` to inject institution logo/name BEFORE template header when `self.institution` is set
  - [ ] Institution logo path check: `self.institution.logo` + `os.path.exists(logo_path)` before drawing
  - [ ] See exact code in Dev Notes

- [ ] Task 2: Add `per_institution_aggregate()` to `ExcelReportGenerator` in `reports/utils/excel_generator.py` (AC: #1, #4)
  - [ ] Reuse existing `add_patients_sheet()`, `add_gm_assessments_sheet()`, etc. methods
  - [ ] All querysets filtered by `institution`: `Patient.objects.filter(institution=institution)`
  - [ ] Assessment querysets filtered via `patient__institution=institution`
  - [ ] Summary statistics sheet at position 0
  - [ ] Zero patients → sheet created with headers only, no error raised
  - [ ] See exact method code in Dev Notes

- [ ] Task 3: Add `cross_institution_aggregate()` to `ExcelReportGenerator` (AC: #2, #4)
  - [ ] Sheet 1 "Network Summary" — one row per institution: name, subscription status, user count, patient count, assessment type counts, total assessments
  - [ ] Sheets 2..N — one sheet per institution showing that institution's aggregate summary
  - [ ] Zero-patient institutions: show all zeros without raising exceptions
  - [ ] Summary row at bottom of Network Summary sheet (grand totals)
  - [ ] See exact method code in Dev Notes

- [ ] Task 4: Add `superadmin_reports` view to `institution/views.py` (AC: #1, #2, #3, #4)
  - [ ] SUPERADMIN only; redirect others to `manage-patients`
  - [ ] GET: render blank scope selector form with institution dropdown
  - [ ] POST: parse `scope` (`per_institution` or `cross_institution`), `format` (`excel` or `pdf`), optional `institution_id`
  - [ ] For `per_institution` Excel: call `ExcelReportGenerator().per_institution_aggregate(institution)`
  - [ ] For `cross_institution` Excel: call `ExcelReportGenerator().cross_institution_aggregate()`
  - [ ] For PDF (any scope): call `PatientPDFGenerator(institution=request.institution).generate(...)` — institution branding auto-injected
  - [ ] Return `FileResponse` with correct `Content-Disposition` header
  - [ ] See exact view code in Dev Notes

- [ ] Task 5: Add `superadmin-reports` URL to `institution/urls.py` (AC: #1)
  - [ ] Add `path('superadmin/reports/', views.superadmin_reports, name='superadmin-reports')` after `superadmin-dashboard`
  - [ ] See exact URL config change in Dev Notes

- [ ] Task 6: Create `templates/institution/superadmin_reports.html` (AC: #1, #2)
  - [ ] Extend `src/base.html`; title "Superadmin Reports"
  - [ ] AdminLTE card with scope selector radio group (Per-Institution / Cross-Institution)
  - [ ] Institution dropdown (shown only when Per-Institution selected — JS visibility toggle)
  - [ ] Format selector radio group (Excel / PDF)
  - [ ] Submit button "Generate Report"
  - [ ] "Back to Analytics" and "Back to Selector" nav links
  - [ ] Inline JS for conditional institution dropdown visibility (with CSP nonce)
  - [ ] See exact template in Dev Notes

- [ ] Task 7: Write tests in `institution/tests/test_superadmin_reports.py` (AC: #1–#4)
  - [ ] See exact test code in Dev Notes

## Dev Notes

### Story 2.5 Position in the 13-Step Sequence

Story 2.5 = **Step 8** (Superadmin views — completing the reporting scope):

```
8.  Superadmin views + god-view dashboard:
    ├── Stories 2.1–2.3: selector, context switching, onboarding   ← done
    ├── Story 2.4:        aggregate analytics dashboard             ← done
    └── Story 2.5:        aggregate reports (Excel + PDF scopes)   ← THIS STORY
```

**Prerequisites:** Stories 2.1–2.4 must be `done`.
```bash
python manage.py test institution.tests.test_superadmin_dashboard  # 2.4 tests pass
```

**FR Coverage:** FR54 — Superadmin can export cross-institution aggregate reports in Excel
and PDF formats at three scopes: per-patient, per-institution aggregate, and cross-institution
aggregate.

---

### Existing ExcelReportGenerator API (CONFIRMED from codebase)

`reports/utils/excel_generator.py` — key existing methods:

```python
class ExcelReportGenerator:
    def __init__(self):
        self.workbook = None

    def generate(self, output_path=None, start_date=None, end_date=None, parameters=None):
        """EXISTING: all-institution export. No institution filtering. Returns (path, metadata)."""

    def create_workbook(self):
        """Initialize empty workbook, removes default sheet."""

    def add_patients_sheet(self, workbook, queryset, selected_fields=None, anonymize=False):
        """Add "Patients" sheet from patient queryset."""

    def add_gm_assessments_sheet(self, workbook, queryset):
    def add_hine_assessments_sheet(self, workbook, queryset):
    def add_developmental_assessments_sheet(self, workbook, queryset):
    def add_cdic_records_sheet(self, workbook, queryset):
    def add_gpa_assessments_sheet(self, workbook, queryset):
    def add_summary_statistics_sheet(self, workbook, metadata):
        """Add "Summary Statistics" sheet at position 0."""

    def style_header_row(self, worksheet, row_num=1):
    def auto_adjust_column_widths(self, worksheet):
    def make_naive(dt):  # static
```

All `add_*_sheet()` methods accept a queryset — they work with ANY queryset,
not just global `.all()`. The new methods can pass institution-scoped querysets
to the existing sheet builders.

---

### Existing BasePDFGenerator API (CONFIRMED from codebase)

`reports/utils/pdf_generator.py` — key existing structure:

```python
class BasePDFGenerator:
    def __init__(self, template=None):
        self.template = template or self.get_template()  # ReportTemplate
        self.styles = self.get_styles()
        self.page_size = self.get_page_size()

    def create_header_footer(self, canvas_obj, doc):
        canvas_obj.saveState()
        # Header from self.template.header_text (Helvetica-Bold 10pt, centered)
        # Logo from self.template.logo (drawn at leftMargin, 1.5in x 0.5in)
        # Footer from self.template.footer_text (Helvetica 8pt, centered)
        # Page number (Helvetica 9pt, right-aligned at 0.5 inch)
        # Generation timestamp (Helvetica 8pt, left-aligned at 0.5 inch)
        canvas_obj.restoreState()

    def get_temp_path(self, filename=None):
        """Returns path in MEDIA_ROOT/reports/temp/"""
```

**Existing file serving pattern (confirmed from reports/views.py):**
```python
response = FileResponse(open(file_path, 'rb'), content_type=content_type)
response['Content-Disposition'] = f'attachment; filename="{filename}"'
return response
```
FileResponse handles file closing automatically — no explicit cleanup needed.

---

### Task 1: Extend `BasePDFGenerator` — Full Code Change

**Exact modification to `reports/utils/pdf_generator.py`:**

Change `__init__` from:
```python
def __init__(self, template=None):
    self.template = template or self.get_template()
    self.styles = self.get_styles()
    self.page_size = self.get_page_size()
```

To:
```python
def __init__(self, template=None, institution=None):
    self.template = template or self.get_template()
    self.institution = institution   # Phase 2: institution-specific branding (Story 2.5)
    self.styles = self.get_styles()
    self.page_size = self.get_page_size()
```

**Exact modification to `create_header_footer()` — add institution branding block BEFORE
the existing template header block:**

Find this line in `create_header_footer()`:
```python
        # Draw header
        if self.template and self.template.header_text:
```

Insert the following BEFORE that block (keeping all existing code below it unchanged):
```python
        # ── Institution branding (Phase 2: takes precedence over template) ──
        if self.institution:
            from django.utils.html import strip_tags
            # Institution name as header text
            canvas_obj.setFont('Helvetica-Bold', 10)
            canvas_obj.drawCentredString(
                doc.width / 2 + doc.leftMargin,
                doc.height + doc.topMargin + 0.5 * inch,
                self.institution.name[:100],
            )
            # Institution logo (if uploaded — Story 3.3 adds logo upload UI)
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
                            preserveAspectRatio=True,
                        )
                except Exception:
                    pass  # Skip logo on any error — name header still renders
        else:
            # Draw header (existing template-based logic — unchanged)
            if self.template and self.template.header_text:
```

**IMPORTANT:** When wrapping the existing template header in `else:`, add a closing `# end else`
comment and check indentation. The full patched block looks like:
```python
        # ── Institution branding (Phase 2 — overrides template when present) ──
        if self.institution:
            from django.utils.html import strip_tags
            canvas_obj.setFont('Helvetica-Bold', 10)
            canvas_obj.drawCentredString(
                doc.width / 2 + doc.leftMargin,
                doc.height + doc.topMargin + 0.5 * inch,
                self.institution.name[:100],
            )
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
                            preserveAspectRatio=True,
                        )
                except Exception:
                    pass
        else:
            # Draw header — template-based (existing, unchanged)
            if self.template and self.template.header_text:
                from django.utils.html import strip_tags
                header_text = strip_tags(self.template.header_text)
                canvas_obj.setFont('Helvetica-Bold', 10)
                canvas_obj.drawCentredString(
                    doc.width / 2 + doc.leftMargin,
                    doc.height + doc.topMargin + 0.5 * inch,
                    header_text[:100]
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
                            preserveAspectRatio=True,
                        )
                except Exception:
                    pass  # Skip logo if error
        # end institution / template header block

        # Draw footer — always from template (institution footer handled in future story)
        if self.template and self.template.footer_text:
            ...  # existing footer code UNCHANGED
```

**All existing subclasses** (`PatientPDFGenerator`, `GMAssessmentPDFGenerator`, etc.)
will work unchanged — `institution=None` is the default, preserving existing behavior.

**How calling code passes institution:**
```python
# In superadmin_reports view (Task 4):
generator = PatientPDFGenerator(institution=request.institution)
file_path = generator.generate(patient_id)
```

---

### Task 2: `ExcelReportGenerator.per_institution_aggregate()` — Full Method

Add to `reports/utils/excel_generator.py` inside `ExcelReportGenerator` class:

```python
def per_institution_aggregate(self, institution, output_path=None, start_date=None, end_date=None):
    """
    Export all patient and assessment data scoped to a single institution.

    AC: FR54 — per-institution aggregate scope.
    Reuses existing add_*_sheet() methods with institution-filtered querysets.

    Args:
        institution: Institution model instance (the target institution)
        output_path: Optional file path (auto-generated if None)
        start_date: Optional date filter (start)
        end_date: Optional date filter (end)

    Returns:
        tuple: (output_path, metadata)
    """
    from datetime import datetime, time

    if output_path is None:
        filename = f"institution_{institution.slug}_{uuid.uuid4().hex[:8]}.xlsx"
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'reports', 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        output_path = os.path.join(temp_dir, filename)

    # Convert dates to timezone-aware datetimes
    start_datetime = None
    end_datetime = None
    if start_date:
        start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
    if end_date:
        end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))

    self.create_workbook()

    metadata = {
        'institution': institution.name,
        'institution_slug': institution.slug,
        'sheets': {},
        'total_records': 0,
        'start_date': start_date.strftime('%Y-%m-%d') if start_date else 'All',
        'end_date': end_date.strftime('%Y-%m-%d') if end_date else 'All',
        'quality_metrics': {},
    }

    # ── Patients — scoped to institution ─────────────────────────────────
    # Patient.objects.filter(institution=institution) uses InstitutionScopedManager
    # if available; plain filter() is safe here too (intentional, explicit scope)
    patient_qs = Patient.objects.filter(institution=institution).select_related(
        'added_by', 'last_edit_by'
    )
    if start_datetime:
        patient_qs = patient_qs.filter(created_at__gte=start_datetime)
    if end_datetime:
        patient_qs = patient_qs.filter(created_at__lte=end_datetime)
    self.add_patients_sheet(self.workbook, patient_qs)
    patient_count = patient_qs.count()
    metadata['sheets']['Patients'] = patient_count
    metadata['total_records'] += patient_count

    # ── GMA — via patient__institution ────────────────────────────────────
    gma_qs = GMAssessment.objects.filter(patient__institution=institution).select_related('patient', 'added_by')
    if start_datetime:
        gma_qs = gma_qs.filter(created_at__gte=start_datetime)
    if end_datetime:
        gma_qs = gma_qs.filter(created_at__lte=end_datetime)
    self.add_gm_assessments_sheet(self.workbook, gma_qs)
    count = gma_qs.count()
    metadata['sheets']['GM Assessments'] = count
    metadata['total_records'] += count

    # ── HINE ─────────────────────────────────────────────────────────────
    hine_qs = HINEAssessment.objects.filter(patient__institution=institution).select_related('patient', 'added_by')
    if start_datetime:
        hine_qs = hine_qs.filter(created_at__gte=start_datetime)
    if end_datetime:
        hine_qs = hine_qs.filter(created_at__lte=end_datetime)
    self.add_hine_assessments_sheet(self.workbook, hine_qs)
    count = hine_qs.count()
    metadata['sheets']['HINE Assessments'] = count
    metadata['total_records'] += count

    # ── Developmental Assessment ──────────────────────────────────────────
    da_qs = DevelopmentalAssessment.objects.filter(patient__institution=institution).select_related('patient', 'added_by')
    if start_datetime:
        da_qs = da_qs.filter(created_at__gte=start_datetime)
    if end_datetime:
        da_qs = da_qs.filter(created_at__lte=end_datetime)
    self.add_developmental_assessments_sheet(self.workbook, da_qs)
    count = da_qs.count()
    metadata['sheets']['Developmental Assessments'] = count
    metadata['total_records'] += count

    # ── CDIC Records ──────────────────────────────────────────────────────
    cdic_qs = CDICRecord.objects.filter(patient__institution=institution).select_related('patient', 'added_by')
    if start_datetime:
        cdic_qs = cdic_qs.filter(created_at__gte=start_datetime)
    if end_datetime:
        cdic_qs = cdic_qs.filter(created_at__lte=end_datetime)
    self.add_cdic_records_sheet(self.workbook, cdic_qs)
    count = cdic_qs.count()
    metadata['sheets']['CDIC Records'] = count
    metadata['total_records'] += count

    # ── GPA Assessments ───────────────────────────────────────────────────
    gpa_qs = GeneralPaediatricAssessment.objects.filter(patient__institution=institution).select_related('patient', 'added_by')
    if start_datetime:
        gpa_qs = gpa_qs.filter(created_at__gte=start_datetime)
    if end_datetime:
        gpa_qs = gpa_qs.filter(created_at__lte=end_datetime)
    self.add_gpa_assessments_sheet(self.workbook, gpa_qs)
    count = gpa_qs.count()
    metadata['sheets']['GPA Assessments'] = count
    metadata['total_records'] += count

    # Summary statistics sheet (position 0)
    self.add_summary_statistics_sheet(self.workbook, metadata)

    self.workbook.save(output_path)
    return output_path, metadata
```

**Import already present** at top of excel_generator.py:
```python
from patients.models import (
    Patient, GMAssessment, HINEAssessment,
    DevelopmentalAssessment, CDICRecord, GeneralPaediatricAssessment
)
```

Also need to add `Institution` import to `excel_generator.py`:
```python
# Add after existing patients import:
from institution.models import Institution
```

**Zero-patient handling (AC #4):** When `patient_qs` has zero results, `add_patients_sheet()`
writes headers but no data rows — this is the existing behavior. No special handling needed.
Zero results correctly result in zero-row sheets, not exceptions.

---

### Task 3: `ExcelReportGenerator.cross_institution_aggregate()` — Full Method

Add after `per_institution_aggregate()`:

```python
def cross_institution_aggregate(self, output_path=None, start_date=None, end_date=None):
    """
    Export aggregate summary spanning all institutions.

    Workbook structure:
    - Sheet 1 "Network Summary": one row per institution (aggregate stats)
    - Sheets 2..N: per-institution summary details

    AC: FR54 — cross-institution aggregate scope.
    NFR19 compliance: this is an INTENTIONAL cross-institution read, not a leak.

    Args:
        output_path: Optional file path (auto-generated if None)
        start_date: Optional date filter
        end_date: Optional date filter

    Returns:
        tuple: (output_path, metadata)
    """
    from django.db.models import Count, Q
    from datetime import datetime, time

    if output_path is None:
        filename = f"cross_institution_{uuid.uuid4().hex[:8]}.xlsx"
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'reports', 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        output_path = os.path.join(temp_dir, filename)

    start_datetime = None
    end_datetime = None
    if start_date:
        start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
    if end_date:
        end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))

    self.create_workbook()

    # ── Sheet 1: Network Summary ─────────────────────────────────────────
    ws_summary = self.workbook.create_sheet("Network Summary")

    # Title rows
    title_font = Font(bold=True, size=14, color='1F4E78')
    ws_summary['A1'] = 'NDAS Cross-Institution Network Report'
    ws_summary['A1'].font = title_font
    ws_summary.merge_cells('A1:K1')
    ws_summary['A2'] = f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    ws_summary['A3'] = f'Date Range: {start_date.strftime("%Y-%m-%d") if start_date else "All"} to {end_date.strftime("%Y-%m-%d") if end_date else "All"}'

    # Column headers (row 5)
    headers = [
        'Institution', 'Slug', 'Subscription Status',
        'Users', 'Patients', 'GMA', 'HINE', 'DA', 'CDIC', 'GPA', 'Total Assessments'
    ]
    ws_summary.append([])  # Row 4 blank
    ws_summary.append(headers)  # Row 5
    self.style_header_row(ws_summary, row_num=5)

    # Data rows — one per institution
    all_institutions = Institution.objects.all().order_by('name')
    grand_totals = {
        'users': 0, 'patients': 0, 'gma': 0, 'hine': 0, 'da': 0, 'cdic': 0, 'gpa': 0
    }

    date_filter = Q()
    if start_datetime:
        date_filter &= Q(created_at__gte=start_datetime)
    if end_datetime:
        date_filter &= Q(created_at__lte=end_datetime)

    for inst in all_institutions:
        # Counts for this institution — scoped queries (intentional aggregate)
        user_count = inst.customuser_set.count() if hasattr(inst, 'customuser_set') else 0
        # Alternative if related_name was set explicitly:
        # user_count = User.objects.filter(institution=inst).count()

        patient_qs = Patient.objects.filter(Q(institution=inst) & date_filter)
        patient_count = patient_qs.count()

        gma_count  = GMAssessment.objects.filter(Q(patient__institution=inst) & date_filter).count()
        hine_count = HINEAssessment.objects.filter(Q(patient__institution=inst) & date_filter).count()
        da_count   = DevelopmentalAssessment.objects.filter(Q(patient__institution=inst) & date_filter).count()
        cdic_count = CDICRecord.objects.filter(Q(patient__institution=inst) & date_filter).count()
        gpa_count  = GeneralPaediatricAssessment.objects.filter(Q(patient__institution=inst) & date_filter).count()
        total_assessments = gma_count + hine_count + da_count + cdic_count + gpa_count

        ws_summary.append([
            inst.name,
            inst.slug,
            inst.get_subscription_status_display(),
            user_count,
            patient_count,
            gma_count,
            hine_count,
            da_count,
            cdic_count,
            gpa_count,
            total_assessments,
        ])

        grand_totals['users']    += user_count
        grand_totals['patients'] += patient_count
        grand_totals['gma']  += gma_count
        grand_totals['hine'] += hine_count
        grand_totals['da']   += da_count
        grand_totals['cdic'] += cdic_count
        grand_totals['gpa']  += gpa_count

    # Grand totals row
    totals_row = [
        'NETWORK TOTAL', '', '',
        grand_totals['users'],
        grand_totals['patients'],
        grand_totals['gma'],
        grand_totals['hine'],
        grand_totals['da'],
        grand_totals['cdic'],
        grand_totals['gpa'],
        sum(grand_totals[k] for k in ['gma', 'hine', 'da', 'cdic', 'gpa']),
    ]
    ws_summary.append(totals_row)
    # Bold the totals row
    totals_row_num = ws_summary.max_row
    for col in range(1, 12):
        ws_summary.cell(row=totals_row_num, column=col).font = Font(bold=True)

    self.auto_adjust_column_widths(ws_summary)

    # ── Sheets 2..N: Per-institution summary sheets ───────────────────────
    for inst in all_institutions:
        # Truncate sheet name to Excel's 31-char limit
        sheet_name = inst.name[:28]  # Leave room for disambiguation if needed
        ws_inst = self.workbook.create_sheet(sheet_name)

        ws_inst['A1'] = f'{inst.name} — Summary'
        ws_inst['A1'].font = Font(bold=True, size=12)
        ws_inst['A2'] = f'Subscription: {inst.get_subscription_status_display()}'
        ws_inst['A3'] = f'Slug: {inst.slug}'

        # Assessment summary table
        summary_headers = ['Category', 'Count']
        ws_inst.append([])
        ws_inst.append(summary_headers)
        self.style_header_row(ws_inst, row_num=ws_inst.max_row)

        patient_count  = Patient.objects.filter(Q(institution=inst) & date_filter).count()
        gma_count  = GMAssessment.objects.filter(Q(patient__institution=inst) & date_filter).count()
        hine_count = HINEAssessment.objects.filter(Q(patient__institution=inst) & date_filter).count()
        da_count   = DevelopmentalAssessment.objects.filter(Q(patient__institution=inst) & date_filter).count()
        cdic_count = CDICRecord.objects.filter(Q(patient__institution=inst) & date_filter).count()
        gpa_count  = GeneralPaediatricAssessment.objects.filter(Q(patient__institution=inst) & date_filter).count()

        for label, count in [
            ('Patients', patient_count),
            ('GMA Assessments', gma_count),
            ('HINE Assessments', hine_count),
            ('Developmental Assessments', da_count),
            ('CDIC Records', cdic_count),
            ('GPA Assessments', gpa_count),
            ('Total Assessments', gma_count + hine_count + da_count + cdic_count + gpa_count),
        ]:
            ws_inst.append([label, count])

        ws_inst.column_dimensions['A'].width = 28
        ws_inst.column_dimensions['B'].width = 12

    metadata = {
        'institutions_count': all_institutions.count(),
        'grand_totals': grand_totals,
        'start_date': start_date.strftime('%Y-%m-%d') if start_date else 'All',
        'end_date': end_date.strftime('%Y-%m-%d') if end_date else 'All',
    }

    self.workbook.save(output_path)
    return output_path, metadata
```

**New import needed in `excel_generator.py`:**
```python
from institution.models import Institution
```

**Sheet name truncation:** Excel limits sheet names to 31 characters. `inst.name[:28]` leaves
room. If two institutions have the same first 28 chars, sheet names will collide — add a
counter suffix if this becomes an issue.

**Zero-patient handling (AC #4):** When `patient_count == 0`, all assessment counts are also 0.
`ws_summary.append([..., 0, 0, 0, ...])` writes zeros correctly. No exception is raised.

---

### Task 4: `superadmin_reports` View — Full Code

Add to `institution/views.py`:

```python
from django.http import FileResponse


@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
@handle_view_errors(
    redirect_url='institution:institution-selector',
    error_message='Failed to generate report. Please try again.'
)
def superadmin_reports(request):
    """
    Cross-institution aggregate report export — three scopes (FR54):
    1. per_institution  — one institution's full data (Excel)
    2. cross_institution — all institutions aggregate (Excel)
    3. PDF per-patient  — PatientPDFGenerator with institution branding (not in this scope selector)

    SUPERADMIN only.

    GET:  Render scope selector form.
    POST: Generate and stream the export.
    """
    user_type = getattr(request.user, 'user_type', None)
    if user_type != UserType.SUPERADMIN:
        return redirect('manage-patients')

    institutions = Institution.objects.order_by('name')

    if request.method == 'POST':
        scope = request.POST.get('scope', '')
        institution_id = request.POST.get('institution_id', '')

        # ── Validate scope ─────────────────────────────────────────────
        valid_scopes = ('per_institution', 'cross_institution')
        if scope not in valid_scopes:
            from django.contrib import messages as django_messages
            django_messages.error(request, "Invalid report scope selected.")
            return render(request, 'institution/superadmin_reports.html', {
                'institutions': institutions,
            })

        if scope == 'per_institution' and not institution_id:
            from django.contrib import messages as django_messages
            django_messages.error(request, "Please select a target institution for per-institution export.")
            return render(request, 'institution/superadmin_reports.html', {
                'institutions': institutions,
            })

        from reports.utils.excel_generator import ExcelReportGenerator
        generator = ExcelReportGenerator()

        try:
            if scope == 'per_institution':
                target_institution = get_object_or_404(Institution, pk=institution_id)
                output_path, metadata = generator.per_institution_aggregate(
                    institution=target_institution,
                )
                filename = (
                    f"ndas_{target_institution.slug}_report_"
                    f"{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                )

            else:  # cross_institution
                output_path, metadata = generator.cross_institution_aggregate()
                filename = (
                    f"ndas_network_report_"
                    f"{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                )

            logger.info(
                "SUPERADMIN '%s' generated %s report → %s",
                request.user.username, scope, filename
            )

            response = FileResponse(
                open(output_path, 'rb'),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            logger.error(
                "Report generation failed for SUPERADMIN '%s', scope='%s': %s",
                request.user.username, scope, str(e)
            )
            from django.contrib import messages as django_messages
            django_messages.error(request, f"Report generation failed: {str(e)}")

    return render(request, 'institution/superadmin_reports.html', {
        'institutions': institutions,
    })
```

**New imports needed at top of `institution/views.py`:**
```python
from django.http import FileResponse
```
(All other imports — `UserType`, `Institution`, `logger`, `get_object_or_404`, `timezone`,
`require_http_methods`, `ratelimit`, `handle_view_errors` — already present from Stories 2.1–2.4.)

**PDF scope note:** AC #3 refers to PDF generation with institution branding.
The `BasePDFGenerator` change (Task 1) enables this. Existing views in `reports/views.py`
that call PDF generators should be updated to pass `institution=request.institution` when
context is available. This story's `superadmin_reports` view handles Excel exports;
the PDF branding flows through the existing `reports/` PDF views automatically once
Task 1 is complete and calling code passes `institution=request.institution`.

---

### Task 5: `institution/urls.py` — Exact Change

Add the reports URL after `superadmin-dashboard`:

```python
from django.urls import path
from institution import views

app_name = 'institution'

urlpatterns = [
    # Story 2.1 — Institution Selector Screen
    path('', views.institution_selector, name='institution-selector'),

    # Story 2.2 — Context Switching
    path('switch/<int:institution_id>/', views.institution_switch, name='institution-switch'),

    # Story 2.3 — Atomic Institution Onboarding
    path('add/', views.institution_add, name='institution-add'),

    # Story 2.4 — Superadmin Aggregate Analytics Dashboard
    path('superadmin/', views.superadmin_dashboard, name='superadmin-dashboard'),

    # Story 2.5 — Cross-Institution Aggregate Reports  ← ADD THIS LINE
    path('superadmin/reports/', views.superadmin_reports, name='superadmin-reports'),

    # Story 2.6 — Patient Move Between Institutions
    # path('patient-move/<int:patient_id>/', views.superadmin_patient_move, name='superadmin-patient-move'),

    # Story 3.1 — Institution Admin Dashboard
    # path('admin/', views.institution_admin_dashboard, name='institution-admin-dashboard'),
]
```

---

### Task 6: `templates/institution/superadmin_reports.html` — Full Template

```django
{% extends 'src/base.html' %}
{% load static %}
{% block title %}Superadmin Reports — NDAS{% endblock %}

{% block content_header %}
<div class="row mb-0">
  <div class="col-sm-6">
    <h1 class="m-0">Network Reports</h1>
    <small class="text-muted">Export cross-institution data</small>
  </div>
  <div class="col-sm-6">
    <ol class="breadcrumb float-sm-right">
      <li class="breadcrumb-item"><a href="{% url 'institution:institution-selector' %}">Network</a></li>
      <li class="breadcrumb-item"><a href="{% url 'institution:superadmin-dashboard' %}">Analytics</a></li>
      <li class="breadcrumb-item active">Reports</li>
    </ol>
  </div>
</div>
{% endblock content_header %}

{% block main_content %}
<div class="container-fluid">

  {# ── Action nav ────────────────────────────────────────────────────── #}
  <div class="row mb-3">
    <div class="col-12">
      <a href="{% url 'institution:superadmin-dashboard' %}" class="btn btn-secondary btn-sm mr-2">
        <i class="fas fa-arrow-left mr-1"></i>Back to Analytics
      </a>
      <a href="{% url 'institution:institution-selector' %}" class="btn btn-outline-secondary btn-sm">
        <i class="fas fa-th-large mr-1"></i>Network Selector
      </a>
    </div>
  </div>

  {# ── Report Scope Selector ──────────────────────────────────────────── #}
  <div class="row justify-content-center">
    <div class="col-lg-7 col-md-10 col-12">
      <div class="card card-primary card-outline">
        <div class="card-header">
          <h3 class="card-title">
            <i class="fas fa-file-download mr-2"></i>Generate Report
          </h3>
        </div>
        <div class="card-body">

          <form method="post" action="{% url 'institution:superadmin-reports' %}">
            {% csrf_token %}

            {# Non-field errors #}
            {% if messages %}
              {% for message in messages %}
                <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                  {{ message }}
                  <button type="button" class="close" data-dismiss="alert">
                    <span>&times;</span>
                  </button>
                </div>
              {% endfor %}
            {% endif %}

            {# ── Scope selection ──────────────────────────────────────── #}
            <div class="form-group">
              <label class="d-block font-weight-bold mb-2">Report Scope <span class="text-danger">*</span></label>

              <div class="custom-control custom-radio mb-2">
                <input type="radio" id="scope_per_institution" name="scope"
                       value="per_institution" class="custom-control-input"
                       onchange="toggleInstitutionSelector(this.value)"
                       nonce="{{ request.csp_nonce }}"
                       required>
                <label class="custom-control-label" for="scope_per_institution">
                  <strong>Per-Institution Aggregate</strong>
                  <small class="d-block text-muted">All patients and assessments for one specific institution (Excel)</small>
                </label>
              </div>

              <div class="custom-control custom-radio">
                <input type="radio" id="scope_cross_institution" name="scope"
                       value="cross_institution" class="custom-control-input"
                       onchange="toggleInstitutionSelector(this.value)">
                <label class="custom-control-label" for="scope_cross_institution">
                  <strong>Cross-Institution Aggregate</strong>
                  <small class="d-block text-muted">Summary of all institutions on the network (Excel)</small>
                </label>
              </div>
            </div>

            {# ── Institution selector (visible only for per_institution) ── #}
            <div class="form-group" id="institution-selector-row" style="display:none;">
              <label for="id_institution_id" class="font-weight-bold">
                Target Institution <span class="text-danger">*</span>
              </label>
              <select name="institution_id" id="id_institution_id" class="form-control">
                <option value="">— Select institution —</option>
                {% for inst in institutions %}
                  <option value="{{ inst.pk }}">
                    {{ inst.name }}
                    {% if inst.subscription_status != 'ACTIVE' %}({{ inst.get_subscription_status_display }}){% endif %}
                  </option>
                {% endfor %}
              </select>
            </div>

            <hr>

            {# ── Submit ──────────────────────────────────────────────── #}
            <div class="d-flex justify-content-end">
              <button type="submit" class="btn btn-primary">
                <i class="fas fa-download mr-1"></i>Download Report
              </button>
            </div>

          </form>

        </div>
      </div>

      {# ── Scope reference card ────────────────────────────────────────── #}
      <div class="card card-outline card-info mt-3">
        <div class="card-header">
          <h3 class="card-title"><i class="fas fa-info-circle mr-2"></i>Report Scopes</h3>
        </div>
        <div class="card-body p-0">
          <table class="table table-sm mb-0">
            <thead>
              <tr><th>Scope</th><th>Contents</th><th>Format</th></tr>
            </thead>
            <tbody>
              <tr>
                <td>Per-Patient</td>
                <td>Individual patient assessment history PDF</td>
                <td><span class="badge badge-danger">PDF</span> (via patient report)</td>
              </tr>
              <tr>
                <td>Per-Institution</td>
                <td>All patients + all assessment types for one institution</td>
                <td><span class="badge badge-success">Excel</span></td>
              </tr>
              <tr>
                <td>Cross-Institution</td>
                <td>Network summary + per-institution breakdown</td>
                <td><span class="badge badge-success">Excel</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

</div>

<script nonce="{{ request.csp_nonce }}">
function toggleInstitutionSelector(scope) {
  var row = document.getElementById('institution-selector-row');
  if (!row) return;
  row.style.display = (scope === 'per_institution') ? 'block' : 'none';
}
</script>
{% endblock %}
```

---

### Task 7: `institution/tests/test_superadmin_reports.py` — Full Code

```python
"""
institution/tests/test_superadmin_reports.py

Tests for Cross-Institution Aggregate Reports (Story 2.5).
AC: #1 (per_institution_aggregate), #2 (cross_institution_aggregate),
    #3 (PDF institution branding), #4 (zero patient handling)
"""

import logging
import os

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from institution.models import Institution
from ndas.custom_codes.choice import UserType, SubscriptionStatus

logger = logging.getLogger(__name__)
User = get_user_model()


class ReportsTestBase(TestCase):
    """Shared setup: SUPERADMIN + two institutions."""

    def setUp(self):
        self.superadmin = User.objects.create_user(
            username='sa_reports', password='Testpass1!',
            first_name='Super', last_name='Admin',
            position='Administrator', mobile_primary='0771991001',
            user_type=UserType.SUPERADMIN, is_superuser=True, institution=None,
        )
        self.inst_a = Institution.objects.create(
            name='Alpha Hospital', slug='alpha-hospital',
            subscription_status=SubscriptionStatus.ACTIVE, is_active=True,
            created_by=self.superadmin,
        )
        self.inst_b = Institution.objects.create(
            name='Beta Clinic', slug='beta-clinic',
            subscription_status=SubscriptionStatus.GRACE, is_active=True,
            created_by=self.superadmin,
        )
        self.admin_a = User.objects.create_user(
            username='admin_a_rep', password='Testpass1!',
            first_name='Alpha', last_name='Admin',
            position='Administrator', mobile_primary='0771992001',
            user_type=UserType.ADMIN, institution=self.inst_a,
        )
        self.reports_url = reverse('institution:superadmin-reports')


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class ReportsAccessTest(ReportsTestBase):
    """SUPERADMIN-only access."""

    def test_superadmin_can_access_reports_page(self):
        client = Client()
        client.force_login(self.superadmin)
        response = client.get(self.reports_url)
        self.assertEqual(response.status_code, 200)

    def test_admin_redirected_from_reports(self):
        client = Client()
        client.force_login(self.admin_a)
        response = client.get(self.reports_url)
        self.assertEqual(response.status_code, 302)

    def test_unauthenticated_redirected(self):
        response = Client().get(self.reports_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'].lower())


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class PerInstitutionExcelTest(ReportsTestBase):
    """AC #1: per_institution_aggregate() generates institution-scoped workbook."""

    def test_per_institution_export_returns_xlsx(self):
        """AC #1: POST with scope=per_institution returns Excel file."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.post(self.reports_url, {
            'scope': 'per_institution',
            'institution_id': str(self.inst_a.pk),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'spreadsheetml.sheet',
            response.get('Content-Type', ''),
            "Per-institution export must return Excel file"
        )
        self.assertIn(
            'attachment',
            response.get('Content-Disposition', ''),
            "Export must be a file download"
        )

    def test_per_institution_filename_contains_institution_slug(self):
        """AC #1: Filename includes institution slug for easy identification."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.post(self.reports_url, {
            'scope': 'per_institution',
            'institution_id': str(self.inst_a.pk),
        })
        disposition = response.get('Content-Disposition', '')
        self.assertIn('alpha-hospital', disposition,
            "Filename should contain institution slug")

    def test_per_institution_without_institution_id_shows_error(self):
        """AC #1: Missing institution_id re-renders form with error."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.post(self.reports_url, {
            'scope': 'per_institution',
            'institution_id': '',
        })
        self.assertEqual(response.status_code, 200,
            "Missing institution_id must re-render form, not download")

    def test_per_institution_aggregate_method_exists(self):
        """AC #1: ExcelReportGenerator has per_institution_aggregate() method."""
        from reports.utils.excel_generator import ExcelReportGenerator
        generator = ExcelReportGenerator()
        self.assertTrue(
            hasattr(generator, 'per_institution_aggregate'),
            "ExcelReportGenerator must have per_institution_aggregate() method"
        )


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class CrossInstitutionExcelTest(ReportsTestBase):
    """AC #2: cross_institution_aggregate() generates multi-institution workbook."""

    def test_cross_institution_export_returns_xlsx(self):
        """AC #2: POST with scope=cross_institution returns Excel file."""
        client = Client()
        client.force_login(self.superadmin)
        response = client.post(self.reports_url, {
            'scope': 'cross_institution',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'spreadsheetml.sheet',
            response.get('Content-Type', ''),
            "Cross-institution export must return Excel file"
        )

    def test_cross_institution_aggregate_method_exists(self):
        """AC #2: ExcelReportGenerator has cross_institution_aggregate() method."""
        from reports.utils.excel_generator import ExcelReportGenerator
        generator = ExcelReportGenerator()
        self.assertTrue(
            hasattr(generator, 'cross_institution_aggregate'),
            "ExcelReportGenerator must have cross_institution_aggregate() method"
        )

    def test_cross_institution_workbook_has_summary_sheet(self):
        """AC #2: cross_institution_aggregate() workbook contains 'Network Summary' sheet."""
        from reports.utils.excel_generator import ExcelReportGenerator
        generator = ExcelReportGenerator()
        output_path, metadata = generator.cross_institution_aggregate()
        try:
            from openpyxl import load_workbook
            wb = load_workbook(output_path)
            self.assertIn('Network Summary', wb.sheetnames,
                "AC #2: Workbook must contain 'Network Summary' sheet")
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_cross_institution_workbook_has_per_institution_sheets(self):
        """AC #2: cross_institution_aggregate() workbook has one sheet per institution."""
        from reports.utils.excel_generator import ExcelReportGenerator
        from openpyxl import load_workbook
        generator = ExcelReportGenerator()
        output_path, metadata = generator.cross_institution_aggregate()
        try:
            wb = load_workbook(output_path)
            # Should have Network Summary + one sheet per institution (2 institutions in test)
            self.assertGreaterEqual(len(wb.sheetnames), 2,
                "AC #2: Workbook must have Network Summary + per-institution breakdown sheets")
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class PDFInstitutionBrandingTest(ReportsTestBase):
    """AC #3: BasePDFGenerator accepts institution parameter for branding."""

    def test_base_pdf_generator_accepts_institution_param(self):
        """AC #3: BasePDFGenerator.__init__ accepts institution keyword argument."""
        from reports.utils.pdf_generator import BasePDFGenerator
        # Should not raise TypeError
        try:
            generator = BasePDFGenerator(institution=self.inst_a)
            self.assertEqual(generator.institution, self.inst_a,
                "BasePDFGenerator must store institution as self.institution")
        except TypeError as e:
            self.fail(f"AC #3: BasePDFGenerator must accept institution= parameter: {e}")

    def test_base_pdf_generator_default_institution_is_none(self):
        """AC #3: Default institution=None preserves backward compatibility."""
        from reports.utils.pdf_generator import BasePDFGenerator
        generator = BasePDFGenerator()
        self.assertIsNone(generator.institution,
            "Default institution must be None (backwards compatible)")

    def test_subclasses_inherit_institution_parameter(self):
        """AC #3: PatientPDFGenerator inherits institution parameter from BasePDFGenerator."""
        from reports.utils.pdf_generator import PatientPDFGenerator
        try:
            generator = PatientPDFGenerator(institution=self.inst_a)
            self.assertEqual(generator.institution, self.inst_a)
        except TypeError as e:
            self.fail(f"PatientPDFGenerator must accept institution= parameter: {e}")


@override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False)
class ZeroPatientInstitutionTest(ReportsTestBase):
    """AC #4: Institutions with zero patients handled gracefully in exports."""

    def test_per_institution_zero_patients_no_exception(self):
        """AC #4: per_institution_aggregate() with zero patients does not raise."""
        from reports.utils.excel_generator import ExcelReportGenerator
        # inst_b has no patients
        generator = ExcelReportGenerator()
        try:
            output_path, metadata = generator.per_institution_aggregate(institution=self.inst_b)
            self.assertIsNotNone(output_path,
                "AC #4: Should return output path even with zero patients")
        except Exception as e:
            self.fail(f"AC #4: per_institution_aggregate must not raise for zero-patient institution: {e}")
        finally:
            if output_path and os.path.exists(output_path):
                os.unlink(output_path)

    def test_cross_institution_zero_patients_no_exception(self):
        """AC #4: cross_institution_aggregate() with zero-patient institutions does not raise."""
        from reports.utils.excel_generator import ExcelReportGenerator
        generator = ExcelReportGenerator()
        try:
            output_path, metadata = generator.cross_institution_aggregate()
        except Exception as e:
            self.fail(f"AC #4: cross_institution_aggregate must not raise when institutions have zero patients: {e}")
        finally:
            if output_path and os.path.exists(output_path):
                os.unlink(output_path)

    def test_cross_institution_zero_patients_shown_as_zeros_in_summary(self):
        """AC #4: Zero-patient institutions appear in Network Summary sheet with 0 counts."""
        from reports.utils.excel_generator import ExcelReportGenerator
        from openpyxl import load_workbook
        generator = ExcelReportGenerator()
        output_path, metadata = generator.cross_institution_aggregate()
        try:
            wb = load_workbook(output_path)
            ws = wb['Network Summary']
            # Find Beta Clinic row (inst_b has 0 patients)
            found_beta = False
            for row in ws.iter_rows(min_row=6, values_only=True):
                if row[0] and 'Beta' in str(row[0]):
                    found_beta = True
                    # Patient count (col 5) should be 0
                    self.assertEqual(row[4], 0,
                        "AC #4: Beta Clinic (zero patients) must show 0 in patient count column")
                    break
            self.assertTrue(found_beta, "Beta Clinic row must appear in Network Summary")
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
```

---

### Project Structure Notes

**Files MODIFIED in this story:**
- `reports/utils/pdf_generator.py` — add `institution=None` to `BasePDFGenerator.__init__()` + modify `create_header_footer()`
- `reports/utils/excel_generator.py` — add `per_institution_aggregate()` + `cross_institution_aggregate()` + `from institution.models import Institution`
- `institution/views.py` — add `superadmin_reports` view + `from django.http import FileResponse`
- `institution/urls.py` — add `superadmin-reports` path

**Files CREATED in this story:**
- `templates/institution/superadmin_reports.html` — scope selector form
- `institution/tests/test_superadmin_reports.py` — 14 tests covering ACs #1–#4

**Files NOT touched:**
- `reports/views.py` — existing PDF download views are unchanged (they get institution branding automatically once BasePDFGenerator is updated, if callers pass `institution=request.institution`)
- Any migration files — no schema changes

---

### Backwards Compatibility

**`BasePDFGenerator(institution=None)` is 100% backwards compatible:**
- All existing callers use `BasePDFGenerator()` or `BasePDFGenerator(template=...)` — no institution kwarg
- `institution=None` means the existing `create_header_footer()` template-based path runs unchanged
- No existing test should break

**`ExcelReportGenerator.generate()` is unchanged:**
- `per_institution_aggregate()` and `cross_institution_aggregate()` are new methods only
- Existing `generate()` still works for single-institution exports from `reports/` app

---

### References

- Epics: Story 2.5 ACs — per_institution_aggregate, cross_institution_aggregate, PDF institution branding, zero handling [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.5`]
- Architecture: FR54 — three export scopes: per-patient, per-institution aggregate, cross-institution aggregate [Source: `_bmad-output/planning-artifacts/epics.md#FR54`]
- Architecture: "ExcelReportGenerator extended with per_institution_aggregate() and cross_institution_aggregate() scopes" [Source: `_bmad-output/planning-artifacts/epics.md#Reports`]
- Architecture: "BasePDFGenerator extended to inject active institution logo, name, header into all PDF output" [Source: `_bmad-output/planning-artifacts/epics.md#Reports`]
- ExcelReportGenerator API (confirmed): `create_workbook()`, `add_*_sheet()`, `add_summary_statistics_sheet()`, `style_header_row()`, `auto_adjust_column_widths()` — all reusable by new methods [Source: `reports/utils/excel_generator.py`]
- BasePDFGenerator API (confirmed): `create_header_footer()` uses `self.template.header_text` and `self.template.logo`; institution branding takes precedence over template [Source: `reports/utils/pdf_generator.py`]
- File serving pattern (confirmed): `FileResponse(open(path, 'rb'), content_type=...)` + `Content-Disposition` — FileResponse closes file automatically [Source: `reports/views.py:320`]
- ExcelReportGenerator existing imports: `Patient, GMAssessment, HINEAssessment, DevelopmentalAssessment, CDICRecord, GeneralPaediatricAssessment` already at top of file — no re-import needed [Source: `reports/utils/excel_generator.py:18-22`]
- Institution model fields: `name`, `slug`, `logo`, `subscription_status`, `get_subscription_status_display()` (from TextChoices) [Source: `institution/models.py`]
- Story 2.4: No `superadmin-reports` stub in urls.py — this story ADDS the path (not uncomments it) [Source: `_bmad-output/implementation-artifacts/2-4-cross-institution-aggregate-analytics-dashboard.md#Task 2`]
- Project context: Inline `<script>` with `nonce="{{ request.csp_nonce }}"` [Source: `_bmad-output/project-context.md#Security Gotchas`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
