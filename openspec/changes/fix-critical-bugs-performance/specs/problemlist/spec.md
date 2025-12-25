# Problem List Management - Input Sanitization and Validation

## ADDED Requirements

### Requirement: HTML Input Sanitization
Problem list form fields MUST sanitize HTML input to prevent XSS vulnerabilities.

#### Scenario: Clean text in name field
- **WHEN** submitting problem name with HTML tags
- **THEN** all HTML tags are stripped
- **AND** only plain text is stored
- **AND** XSS attack is prevented

#### Scenario: Safe HTML in description field
- **WHEN** submitting problem description with formatting
- **THEN** only safe tags (p, br, strong, em, u, ul, ol, li) are allowed
- **AND** dangerous tags (script, iframe, object) are removed
- **AND** tag attributes are stripped

#### Scenario: Script injection attempt blocked
- **WHEN** attempting to submit `<script>alert('XSS')</script>` in text field
- **THEN** script tag is completely removed
- **AND** stored value contains no executable code

#### Scenario: Event handler attributes removed
- **WHEN** submitting `<img src=x onerror=alert(1)>`
- **THEN** onerror attribute is stripped
- **AND** only img tag with src remains (if images allowed)

#### Scenario: Multiple fields sanitized consistently
- **WHEN** form has name, description, action_taken, outcome, comments fields
- **THEN** each field is sanitized with appropriate rules
- **AND** name uses strictest sanitization (no HTML)
- **AND** description/comments allow limited formatting tags

### Requirement: Date Field Cross-Validation
Problem list date fields MUST be validated for logical consistency.

#### Scenario: Date identified after onset accepted
- **WHEN** date_identified is after date_of_onset
- **THEN** validation passes
- **AND** form submission succeeds

#### Scenario: Date identified before onset rejected
- **WHEN** date_identified is before date_of_onset
- **THEN** validation error is raised
- **AND** user sees message "Date identified cannot be before date of onset"

#### Scenario: Date resolved after onset accepted
- **WHEN** date_resolved is after date_of_onset
- **THEN** validation passes
- **AND** problem is marked as resolved

#### Scenario: Date resolved before onset rejected
- **WHEN** date_resolved is before date_of_onset
- **THEN** validation error is raised
- **AND** user sees message "Date resolved cannot be before date of onset"

#### Scenario: All three dates in logical order
- **WHEN** date_of_onset < date_identified < date_resolved
- **THEN** validation passes for timeline consistency
- **AND** problem record is created successfully

### Requirement: Filename Sanitization Timing
Uploaded filenames MUST be sanitized before temporary storage to prevent path traversal attacks.

#### Scenario: Safe filename accepted
- **WHEN** uploading file named "report_2024.pdf"
- **THEN** filename passes sanitization unchanged
- **AND** file is stored safely

#### Scenario: Path traversal attempt blocked
- **WHEN** attempting to upload file named "../../etc/passwd"
- **THEN** path separators are removed or escaped
- **AND** file is stored in intended directory only

#### Scenario: Special characters normalized
- **WHEN** uploading file with spaces, unicode, or special chars
- **THEN** filename is sanitized to safe ASCII characters
- **AND** file extension is preserved

## Technical Notes

### Input Sanitization Implementation

**Using bleach library:**
```python
import bleach

ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li']
ALLOWED_ATTRS = {}

class ProblemForm(forms.ModelForm):
    def clean_name(self):
        value = self.cleaned_data.get('name', '')
        return bleach.clean(value, tags=[], strip=True)  # No HTML in names

    def clean_description(self):
        value = self.cleaned_data.get('description', '')
        return bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)

    def clean_action_taken(self):
        value = self.cleaned_data.get('action_taken', '')
        return bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)

    def clean_outcome(self):
        value = self.cleaned_data.get('outcome', '')
        return bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)

    def clean_comments(self):
        value = self.cleaned_data.get('comments', '')
        return bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
```

**Dependency:** `pip install bleach`

### Date Cross-Validation

```python
def clean(self):
    cleaned_data = super().clean()
    date_of_onset = cleaned_data.get('date_of_onset')
    date_identified = cleaned_data.get('date_identified')
    date_resolved = cleaned_data.get('date_resolved')

    # Validate date_identified >= date_of_onset
    if date_of_onset and date_identified:
        if date_identified < date_of_onset:
            raise ValidationError({
                'date_identified': _('Date identified cannot be before date of onset.')
            })

    # Validate date_resolved >= date_of_onset
    if date_of_onset and date_resolved:
        if date_resolved < date_of_onset:
            raise ValidationError({
                'date_resolved': _('Date resolved cannot be before date of onset.')
            })

    return cleaned_data
```

### Filename Sanitization

**Move from form clean to model upload_to callable:**
```python
# In problemlist/models.py
from ndas.custom_codes.custom_methods import sanitize_filename
from django.utils import timezone

def problem_attachment_upload_path(instance, filename):
    """Generate upload path with sanitized filename"""
    sanitized = sanitize_filename(filename)
    return f"problemlist/{instance.patient.id}/{timezone.now().year}/{timezone.now().month}/{sanitized}"

class ProblemAttachment(TimeStampedModel, UserTrackingMixin):
    file = models.FileField(
        upload_to=problem_attachment_upload_path,  # Sanitizes before storage
        # ... rest of field config
    )
```

### Affected Files

- `problemlist/forms.py` - Lines 28-70 (sanitization methods)
- `problemlist/forms.py` - Lines 73-114 (date validation)
- `patients/forms.py` - Lines 739-745 (filename sanitization - related pattern)

### Security Test Cases

**XSS Prevention:**
```python
def test_xss_prevention(self):
    form = ProblemForm(data={
        'name': '<script>alert("XSS")</script>Test',
        'description': '<p>Normal text</p><script>alert(1)</script>'
    })
    self.assertTrue(form.is_valid())
    self.assertEqual(form.cleaned_data['name'], 'Test')
    self.assertEqual(form.cleaned_data['description'], '<p>Normal text</p>')
```

**Date Validation:**
```python
def test_date_validation(self):
    form = ProblemForm(data={
        'date_of_onset': '2024-01-15',
        'date_identified': '2024-01-10',  # Before onset - should fail
    })
    self.assertFalse(form.is_valid())
    self.assertIn('date_identified', form.errors)
```

### Performance Targets

- **Sanitization overhead:** < 10ms per field
- **Validation time:** < 50ms for all form validations
- **No XSS vulnerabilities:** 100% coverage on text inputs
