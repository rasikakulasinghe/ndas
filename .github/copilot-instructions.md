# NDAS - GitHub Copilot Instructions

IDE-specific guidance for GitHub Copilot. For full project documentation, see `CLAUDE.md`.

**Last Updated:** 2025-12-25

## Project Context

**NDAS** - Django 4.2.16 medical system | AdminLTE 3.2 | Bootstrap 4.6

**Apps:** `patients/` (root), `users/`, `video/`, `reports/`, `problemlist/`

## Code Generation Rules

### Models - Always Include

```python
from ndas.custom_codes.Custom_abstract_class import TimeStampedModel, UserTrackingMixin

class MyModel(TimeStampedModel, UserTrackingMixin):
    # Provides: created_at, updated_at, added_by, last_edit_by
    field = models.CharField(max_length=100, db_index=True)  # Index searchable fields
```

- Choices go in `ndas/custom_codes/choice.py`
- Validators go in `ndas/custom_codes/validators.py`

### Views - Standard Pattern

```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

@login_required(login_url="user-login")
@require_http_methods(["GET", "POST"])
@ratelimit(key='user_or_ip', rate='10/m')
def my_view(request, pk):
    obj = get_object_or_404(MyModel, id=pk)
    related = Related.objects.filter(parent=obj).select_related('added_by')
    return render(request, "app/template.html", {"obj": obj})
```

### Forms - Bootstrap Styling

```python
class MyForm(forms.ModelForm):
    class Meta:
        model = MyModel
        fields = ["field1", "field2"]
        widgets = {
            "text": forms.TextInput(attrs={"class": "form-control"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "select": forms.Select(attrs={"class": "form-control"}),
        }
```

### Templates - Base Structure

```django
{% extends 'src/base.html' %}
{% load static %}
{% block title %}Section - Action{% endblock %}
{% block main_content %}
<div class="container-fluid">{% csrf_token %}<!-- Content --></div>
{% endblock %}
```

Naming: `manager.html` (list), `add.html` (create), `edit.html` (update), `view.html` (detail)

## Patient Model Fields

```python
# Correct field names (common mistakes to avoid)
patient.bht              # NOT bht_number
patient.nnc_no           # NOT nnc_number
patient.baby_name        # NOT patient_name
patient.dob_tob          # NOT date_of_birth
patient.pog_wks          # NOT gestational_age_weeks
patient.birth_weight     # NOT birth_weight_g
patient.hc               # NOT head_circumference
patient.apgar_1          # NOT apgar_1_min
```

## Custom Utilities

```python
# Import patterns
from ndas.custom_codes.custom_methods import getCountZeroIfNone, calculate_age_string
from ndas.custom_codes.validators import sanitize_text_input, sanitize_filename
from ndas.custom_codes.sanitization import sanitize_html, sanitize_plain_text
from ndas.custom_codes.ndas_enums import PtStatus
from ndas.custom_codes.delete_helpers import has_delete_permission, validate_can_delete
from ndas.custom_codes.error_handlers import handle_view_errors
```

## Do Not

- Add choices inline in models (use `choice.py`)
- Use `.objects.get()` without try/except (use `get_object_or_404()`)
- Change CSS framework (AdminLTE 3.2 + Bootstrap 4.6)
- Skip `select_related()`/`prefetch_related()` for related objects
- Forget CSRF tokens in forms
- Skip file upload validation
