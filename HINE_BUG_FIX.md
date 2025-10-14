# HINE Assessment Bug Fix - October 14, 2025

## Error Encountered
```
RelatedObjectDoesNotExist at /hine/add/9/
HINEAssessment has no patient.
Request Method: POST
Exception Location: django\db\models\fields\related_descriptors.py, line 217
```

## Root Cause Analysis

The error occurred because the `HINEAssessment` model's `clean()` method was trying to access `self.patient` during form validation, but the patient relationship hadn't been established yet. The sequence was:

1. Form's `is_valid()` is called
2. Django's model validation calls `clean()` on the model instance
3. The `clean()` method tries to access `self.patient` to validate the assessment date
4. But `self.patient` is only set AFTER `save(commit=False)` in the view
5. This caused a `RelatedObjectDoesNotExist` exception

## Fixes Applied

### 1. Model Fix - `patients/models.py` (HINEAssessment.clean())

**Problem:** The `clean()` method unconditionally tried to access `self.patient`, which might not be set during form validation.

**Solution:** Added defensive checks to only validate patient-related fields if the patient relationship is already established:

```python
def clean(self):
    """Custom validation for HINE Assessment"""
    super().clean()

    # Validate assessment date is not in the future
    if self.date_of_assessment and self.date_of_assessment > timezone.now():
        raise ValidationError(
            {"date_of_assessment": _("Assessment date cannot be in the future.")}
        )

    # Validate assessment date is not before patient's birth
    # Only validate if patient is already set (skip during form validation)
    if self.patient_id:
        try:
            if (
                self.date_of_assessment
                and self.patient
                and self.patient.dob_tob
                and self.date_of_assessment < self.patient.dob_tob
            ):
                raise ValidationError(
                    {
                        "date_of_assessment": _(
                            "Assessment date cannot be before patient birth date."
                        )
                    }
                )
        except Patient.DoesNotExist:
            # Patient relationship not yet established, skip validation
            pass
```

### 2. Form Improvement - `patients/forms.py` (HINEAssessmentForm)

**Enhancement:** Modified form to accept patient instance and perform validation at the form level:

```python
class HINEAssessmentForm(forms.ModelForm):
    
    def __init__(self, *args, **kwargs):
        """Initialize form with optional patient instance for validation"""
        self.patient = kwargs.pop('patient', None)
        super().__init__(*args, **kwargs)
    
    def clean_date_of_assessment(self):
        """Validate and make timezone-aware the assessment date"""
        date_of_assessment = self.cleaned_data.get("date_of_assessment")
        if date_of_assessment and timezone.is_naive(date_of_assessment):
            date_of_assessment = timezone.make_aware(date_of_assessment)
        
        # Validate against patient's birth date if patient is provided
        if date_of_assessment and self.patient and self.patient.dob_tob:
            if date_of_assessment < self.patient.dob_tob:
                raise forms.ValidationError(
                    _("Assessment date cannot be before patient birth date.")
                )
        
        return date_of_assessment
```

### 3. View Updates - `patients/views.py`

#### hine_assessment_add()
- Pass `patient=sp` to form initialization
- Improved error handling and messages
- Better validation for form errors

```python
if request.method == "POST":
    hine_form = HINEAssessmentForm(request.POST, patient=sp)
    # ... rest of the logic
else:
    hine_form = HINEAssessmentForm(patient=sp)
```

#### hine_assessment_edit()
- Added try-except for record retrieval
- Pass `patient=sp` to form initialization
- Improved error messages
- Better error handling consistency

### 4. Template Fix - `templates/hine/add.html`

Fixed HTML structure issues:
- Corrected form closing tag placement (must close AFTER card-body)
- Added proper `container-fluid` wrapper with CSRF token per NDAS standards
- Proper nesting: `container-fluid` → `container-sm` → `card` → `form` → `card-body`

## Benefits

1. **Robust validation:** Form-level validation happens before model validation
2. **Better error messages:** User-friendly error formatting
3. **Defensive programming:** Model validation handles missing relationships gracefully
4. **Consistent patterns:** Follows NDAS architecture standards
5. **Type safety:** Proper null/existence checks prevent crashes

## Testing Recommendations

Test the following scenarios:
1. ✅ Create new HINE record with valid data
2. ✅ Create HINE record with assessment date before patient birth (should show error)
3. ✅ Create HINE record with future assessment date (should show error)
4. ✅ Create HINE record with invalid HINE score (< 0 or > 78)
5. ✅ Edit existing HINE record
6. ✅ View HINE record after creation

## Files Modified

1. `patients/models.py` - HINEAssessment.clean() method
2. `patients/forms.py` - HINEAssessmentForm class
3. `patients/views.py` - hine_assessment_add() and hine_assessment_edit()
4. `templates/hine/add.html` - HTML structure and container wrapper

## Migration Required

No database migration needed - only code logic changes.
