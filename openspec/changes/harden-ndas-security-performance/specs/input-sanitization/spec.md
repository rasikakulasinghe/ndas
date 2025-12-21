# Spec: Input Sanitization for XSS Prevention

## REMOVED Requirements

None - input sanitization is a new security layer.

## ADDED Requirements

### Requirement: All user input must be sanitized at form level

All Django forms that accept user input MUST sanitize data in `clean_<field>()` methods before saving to database.

#### Scenario: Plain text fields escape HTML entities

**Given** a patient form with `baby_name` field
**When** a user submits `<script>alert('XSS')</script>Baby Name`
**Then** the form's `clean_baby_name()` method sanitizes the input
**And** the saved value is `&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;Baby Name`
**And** HTML tags are escaped and cannot execute

Example:
```python
class PatientForm(forms.ModelForm):
    def clean_baby_name(self):
        baby_name = self.cleaned_data.get('baby_name')
        return sanitize_plain_text(baby_name)
```

#### Scenario: Rich text fields allow safe HTML only

**Given** a patient form with `problems` field (medical notes)
**When** a user submits `<p>Medical note</p><script>alert('XSS')</script>`
**Then** the form's `clean_problems()` method sanitizes with bleach
**And** the saved value is `<p>Medical note</p>` (script tag removed)
**And** allowed tags like `<p>`, `<strong>`, `<ul>` are preserved
**And** dangerous tags like `<script>`, `<iframe>` are stripped

Example:
```python
def clean_problems(self):
    problems = self.cleaned_data.get('problems')
    if problems:
        return sanitize_html(problems)
    return problems
```

#### Scenario: Filename sanitization prevents path traversal

**Given** a file upload form
**When** a user uploads file with name `../../etc/passwd`
**Then** the form's `clean_file()` method sanitizes the filename
**And** the saved filename is `etc_passwd` (path components removed)
**And** dangerous characters are replaced with underscores

Example:
```python
def clean_file(self):
    file = self.cleaned_data.get('file')
    if file:
        file.name = sanitize_filename(file.name)
    return file
```

### Requirement: Sanitization library must define allowed HTML tags and attributes

The sanitization configuration MUST whitelist only medically-necessary HTML tags and attributes.

#### Scenario: Allowed HTML tags for medical notes

**Given** the sanitization configuration
**When** defining allowed tags for rich text fields
**Then** the whitelist includes:
  - Text formatting: `p`, `br`, `strong`, `em`, `u`
  - Lists: `ul`, `ol`, `li`
  - Headers: `h1`, `h2`, `h3`, `h4`, `h5`, `h6`
  - Links: `a` (with href, title attributes only)
  - Other: `blockquote`, `code`, `pre`
**And** dangerous tags are NOT allowed:
  - Scripts: `script`, `noscript`
  - Iframes: `iframe`, `frame`, `frameset`
  - Objects: `object`, `embed`, `applet`
  - Forms: `form`, `input`, `button`, `select`
  - Events: No `on*` attributes (onclick, onload, etc.)

Configuration:
```python
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'a', 'blockquote', 'code', 'pre',
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
}

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']
```

#### Scenario: Sanitization removes event handlers from allowed tags

**Given** a rich text field with `<a href="#" onclick="alert('XSS')">link</a>`
**When** sanitizing with bleach.clean()
**Then** the output is `<a href="#">link</a>`
**And** the onclick event handler is removed
**And** only href attribute is preserved

### Requirement: Sanitization must apply to all form types

Input sanitization MUST be applied to patient forms, video forms, assessment forms, user profile forms, and attachment forms.

#### Scenario: Patient form sanitizes all text fields

**Given** the PatientForm
**When** validating submitted data
**Then** these fields are sanitized as plain text:
  - `baby_name`, `mother_name`, `bht`, `nnc_no`, `ptc_no`, `pc_no`, `pin`, `disk_no`
**And** these fields are sanitized as rich text (allow HTML):
  - `problems`, `resustn_note`, `examination_note`
**And** all other text fields are sanitized as plain text

#### Scenario: Video form sanitizes title and description

**Given** the VideoForm
**When** validating submitted data
**Then** `title` field is sanitized as plain text
**And** `description` field is sanitized as rich text (allow safe HTML)

#### Scenario: Attachment form sanitizes filename and metadata

**Given** the AttachmentForm
**When** validating uploaded file
**Then** filename is sanitized to remove path traversal
**And** `title` field is sanitized as plain text
**And** `description` field is sanitized as rich text

#### Scenario: User profile form sanitizes user-provided fields

**Given** a user profile update form
**When** validating submitted data
**Then** display name is sanitized as plain text
**And** bio/description is sanitized as rich text
**And** prevents XSS in user profile pages

### Requirement: Sanitization applies to new inputs only (no retroactive migration)

Sanitization MUST be applied to new form submissions but NOT retroactively to existing database records.

#### Scenario: New patient submissions are sanitized

**Given** a user creates a new patient record
**When** submitting the patient form
**Then** all fields are sanitized before database save
**And** sanitized data is stored in database

#### Scenario: Existing patient records remain unchanged

**Given** patient records already exist in the database
**When** the sanitization feature is deployed
**Then** existing database records are NOT modified
**And** no data migration is run
**And** existing data displays with Django's auto-escaping

#### Scenario: Edited records are sanitized on update

**Given** an existing patient record with unsanitized data
**When** a user edits and saves the record
**Then** the updated fields are sanitized
**And** only modified fields are affected (no full-record sanitization)

## MODIFIED Requirements

None - this is a new security layer.

## Cross-References

- **Depends on**: `bleach` library (pip install bleach==6.1.0)
- **Related to**: `csp-hardening` - Defense-in-depth XSS protection
- **Related to**: `security-testing` - Input sanitization validated by tests
- **Impact**: All Django forms in patients/, video/, users/ apps

## Implementation Notes

**Dependencies:**
```txt
bleach==6.1.0
```

**Sanitization Utilities** (ndas/custom_codes/sanitization.py):
```python
"""
Input sanitization utilities for NDAS.
"""
import bleach
from django.utils.html import escape

# Allowed HTML tags for rich text fields
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'a', 'blockquote', 'code', 'pre',
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
}

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


def sanitize_html(html_content, allowed_tags=None, allowed_attrs=None):
    """
    Sanitize HTML content to prevent XSS attacks.

    Args:
        html_content (str): Raw HTML content to sanitize
        allowed_tags (list, optional): Custom list of allowed tags
        allowed_attrs (dict, optional): Custom dict of allowed attributes

    Returns:
        str: Sanitized HTML safe for rendering
    """
    if not html_content:
        return ''

    tags = allowed_tags or ALLOWED_TAGS
    attrs = allowed_attrs or ALLOWED_ATTRIBUTES

    return bleach.clean(
        html_content,
        tags=tags,
        attributes=attrs,
        protocols=ALLOWED_PROTOCOLS,
        strip=True
    )


def sanitize_plain_text(text):
    """
    Sanitize plain text by escaping HTML entities.
    Use for fields that should not contain any HTML.

    Args:
        text (str): Text to sanitize

    Returns:
        str: Escaped text safe for rendering
    """
    if not text:
        return ''
    return escape(text)


def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal attacks.

    Args:
        filename (str): Original filename

    Returns:
        str: Sanitized filename
    """
    import os
    import re

    # Get basename (removes any path components)
    filename = os.path.basename(filename)

    # Remove any characters that aren't alphanumeric, dash, underscore, or dot
    filename = re.sub(r'[^\w\-\.]', '_', filename)

    # Prevent multiple dots (could hide extension)
    filename = re.sub(r'\.{2,}', '.', filename)

    # Ensure filename isn't empty
    if not filename or filename == '.':
        filename = 'unnamed_file'

    return filename
```

**Form Integration Examples:**

1. **PatientForm** (patients/forms.py):
```python
from ndas.custom_codes.sanitization import sanitize_html, sanitize_plain_text

class PatientForm(forms.ModelForm):
    def clean_baby_name(self):
        return sanitize_plain_text(self.cleaned_data.get('baby_name'))

    def clean_mother_name(self):
        return sanitize_plain_text(self.cleaned_data.get('mother_name'))

    def clean_problems(self):
        problems = self.cleaned_data.get('problems')
        if problems:
            return sanitize_html(problems)
        return problems

    def clean_resustn_note(self):
        note = self.cleaned_data.get('resustn_note')
        if note:
            return sanitize_html(note)
        return note
```

2. **AttachmentForm** (patients/forms.py):
```python
from ndas.custom_codes.sanitization import sanitize_filename

class AttachmentForm(forms.ModelForm):
    def clean_title(self):
        return sanitize_plain_text(self.cleaned_data.get('title'))

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            file.name = sanitize_filename(file.name)
        return file
```

**Testing Strategy:**
1. Unit test: Submit `<script>alert('XSS')</script>` in patient name, verify escaped
2. Unit test: Submit rich text with `<script>` in medical notes, verify script removed
3. Unit test: Submit `../../etc/passwd` filename, verify sanitized
4. Integration test: Create patient with XSS attempt, verify safe storage and display
5. Security test: Automated XSS payload testing

**Forms to Update:**
- `patients/forms.py`: PatientForm, AttachmentForm
- `video/forms.py`: VideoForm
- `users/forms.py`: UserProfileForm, RegistrationForm
- Any other forms accepting user input

**Validation:**
```python
# tests/test_security.py::InputSanitizationTestCase
def test_xss_in_patient_name(self):
    form_data = {
        'baby_name': '<script>alert("XSS")</script>Test Baby',
        # ... other required fields
    }
    form = PatientForm(data=form_data)
    if form.is_valid():
        patient = form.save(commit=False)
        self.assertNotIn('<script>', patient.baby_name)
        self.assertNotIn('alert', patient.baby_name)
```

**Rollback Strategy:**
- Remove `clean_<field>()` methods from forms
- Keep bleach library installed (no harm if unused)
- Sanitization only affects NEW inputs, so rollback doesn't affect existing data
