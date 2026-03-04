---
title: 'Bug Fixation — Data Isolation, Atomicity and Error Handling'
slug: 'bug-fix-isolation-atomicity-error-handling'
created: '2026-03-03'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Django 4.2', 'Python 3.x', 'SQLite/PostgreSQL', 'openpyxl 3.1.5']
files_to_modify:
  - 'ndas/custom_codes/custom_methods.py'
  - 'ndas/custom_codes/error_handlers.py'
  - 'ndas/custom_codes/delete_helpers.py'
  - 'patients/views.py'
  - 'patients/models.py'
  - 'video/views.py'
  - 'users/views.py'
  - 'reports/views.py'
  - 'reports/utils/excel_generator.py'
elicitation_applied: '2026-03-03'
elicitation_findings: [ELI-01, ELI-02, ELI-03, ELI-04, ELI-05]
code_patterns:
  - 'InstitutionScopedManager.for_institution(institution) — None returns all (Phase 1 safe)'
  - 'patient__in=_patients_qs — indirect institution scoping for models without their own manager'
  - 'transaction.atomic() — already used in institution/views.py and referral/views.py'
  - 'logger = logging.getLogger(__name__) at module level — project rule'
  - 'logger.exception() captures full stack; logger.warning() for handled edge cases'
test_patterns:
  - 'Django TestCase with Client/RequestFactory'
  - 'override_settings(MULTI_INSTITUTION_ENABLED=True, RATELIMIT_ENABLE=False) for isolation tests'
  - 'Reference: institution/tests/test_isolation.py for institution-scoping test patterns'
---

# Tech-Spec: Bug Fixation — Data Isolation, Atomicity and Error Handling

**Created:** 2026-03-03

## Overview

### Problem Statement

17 confirmed bugs across the NDAS backend. The most severe are institution data isolation leaks: four dashboard chart utility functions (`get_gma_diagnosis_data`, `get_all_diagnosis_data`, `get_admissions_data_barchart`, `get_userStats`) query across all institutions without filtering — every logged-in user sees system-wide aggregated charts. Secondary issues: cross-institution user lists in search and admin views; non-atomic GM assessment creation leaving orphaned records on M2M failure; missing video-patient ownership check in `assessment_add`; a recursive `ValidationError` handler that loops to Python's recursion limit; 7 bare `except:` clauses silently swallowing errors; duplicate Exists subquery evaluation on the dashboard; cross-institution GM count as a report quality denominator; a redundant double-query in `isLastGMANormal`; `ValidationError` logged at INFO instead of WARNING; `log_and_suppress` discarding stack traces; missing module-level loggers in three files.

### Solution

Add an `institution` parameter to all four chart functions and update their dashboard call-site. Scope search and admin user-list querysets to institution. Wrap GM assessment M2M save in `transaction.atomic()`. Add a `video_file.patient_id == patient.pk` guard before assessment creation. Fix `handle_view_errors` ValidationError branch to redirect instead of recurse, and raise its log level to WARNING. Replace all 7 bare `except:` with specific types and logging. Eliminate duplicate Exists subquery evaluation by deriving both count and list from one annotated queryset. Add institution scoping to `calculate_quality_metrics` and its call chain. Add missing module-level loggers.

### Scope

**In Scope:** All 17 items + 5 elicitation findings. 9 files modified (patients/views.py logger fix added via ELI-01; T-09 `_inst=None` guard added via ELI-04). No new packages, no migrations, no template changes.

**Out of Scope:** Caching `get_userStats()`, dev CSP changes, UI changes, new features.

---

## Context for Development

### Codebase Patterns

- **Institution isolation**: `Patient.objects.for_institution(institution)` via `InstitutionScopedManager` (only `Patient` has this manager). For models without it (Video, GMAssessment, etc.), scope via `patient__in=_patients_qs`. For CustomUser, scope via `.filter(institution=institution)`. `for_institution(None)` returns all records — Phase 1 backward compatible.
- **Chart utilities**: In `ndas/custom_codes/custom_methods.py`. Currently zero-argument. After fix: accept `institution` as first positional arg. Caller is exclusively `patients/views.py` dashboard, which already holds `_inst = getattr(request, 'institution', None)`.
- **Transactions**: `from django.db import transaction` + `with transaction.atomic():`. Pattern is in `institution/views.py:143` and `referral/views.py:58`.
- **Module-level logger rule**: `import logging` at top; `logger = logging.getLogger(__name__)` before first class/function. Three files are missing this: `patients/models.py`, `reports/views.py`, `reports/utils/excel_generator.py`.
- **`log.exception()`** captures full traceback (use for unexpected errors in `log_and_suppress`). **`logger.warning()`** for handled edge cases (bare `except:` replacements).
- **`admin_required`** decorator (`users/decorators.py`) allows both `is_staff` and `is_superuser`. A superuser must see all users; `is_staff` (institution admin) sees only their own institution's users.
- **`calculate_quality_metrics`** is a method on `ExcelReportGenerator`. It is called only from `generate()` on line 744. The `generate()` method is called only from `reports/views.py:154`. Institution must be threaded through: `reports/views.py` → `generate()` → `calculate_quality_metrics()`.

### Files to Reference

| File | Role in this fix |
| ---- | ---------------- |
| `ndas/custom_codes/custom_methods.py` | Add `institution` param to 4 chart functions |
| `ndas/custom_codes/error_handlers.py` | Fix ValidationError recursion + log level + `log_and_suppress` trace |
| `ndas/custom_codes/delete_helpers.py` | Fix bare `except:` in entity name helper |
| `patients/views.py` | Update chart call-sites; fix search user lists; atomic assessment save; ownership guard; fix duplicate Exists subqueries |
| `patients/models.py` | Fix 3 bare `except:`; collapse `isLastGMANormal` double query; add module-level logger |
| `video/views.py` | Fix bare `except:` in `video_detail` view |
| `users/views.py` | Scope `admin_user_list` to institution unless superuser |
| `reports/views.py` | Fix bare `except:`; pass `institution` to `generator.generate()`; add module-level logger |
| `reports/utils/excel_generator.py` | Fix `gm_total` isolation; fix bare `except:`; add `institution` param to `generate()` + `calculate_quality_metrics()`; add module-level logger |
| `institution/managers.py` | Reference for `for_institution()` signature |
| `institution/tests/test_isolation.py` | Reference for test patterns |

### Technical Decisions

- **Q1**: Chart functions receive `institution` as first positional arg. Pass `_inst` (already computed at dashboard top) at all four call-sites.
- **Q2**: No caching added to `get_userStats()`.
- **Q3**: `handle_view_errors` ValidationError branch mirrors IntegrityError — redirect to `redirect_url` if set, else render `render_template` if set, else `redirect('home')`. Recursive call removed entirely.
- **Q4**: Dev CSP unchanged.
- **Bookmark bare except**: Import `NoReverseMatch` locally alongside `reverse` — it is already imported locally in that method.
- **`isLastGMANormal`**: Remove both the `.exists()` pre-check and the `try/except` entirely. Single `.first()` + null-guard is equivalent and correct. Returns `True` (normal) when no assessments, same as `isLastHINENormal` and `isLastDANormal`.
- **`delete_helpers.py` bare except**: `except Exception: pass` (no logging) — this is a cosmetic string fallback, not a business operation.
- **`excel_generator.py` column-width bare except**: `except (TypeError, ValueError): pass` — cosmetic, cell value width calculation.
- **`admin_user_list` scoping**: Superuser (`request.user.is_superuser`) sees all users. `is_staff` non-superuser sees only `institution=_inst`.

---

## Implementation Plan

### Tasks

Tasks are ordered by dependency (lowest-risk / no-dependency changes first).

---

#### - [x] T-01 — Add module-level loggers to four files

**Files:** `patients/models.py`, `patients/views.py`, `reports/views.py`, `reports/utils/excel_generator.py`

Four files violate the project rule of defining `logger = logging.getLogger(__name__)` at module level. Several subsequent tasks in this spec depend on these loggers being present.

For each file, after the existing imports block, add:
```python
import logging
logger = logging.getLogger(__name__)
```

- `patients/models.py`: Add `import logging` after line 7 (`from datetime import timedelta`). Add `logger = logging.getLogger(__name__)` after line 47 (`from institution.managers import InstitutionScopedManager as _InstitutionScopedManager`), before the `Patient` class definition.
- `patients/views.py`: Line 71 currently reads `import os, logging` + `logger = logging.getLogger("django")`. Split the import and fix the logger name:
  ```python
  # BEFORE (lines 62, 71):
  import os, logging
  ...
  logger = logging.getLogger("django")

  # AFTER:
  import os
  import logging
  ...
  logger = logging.getLogger(__name__)
  ```
- `reports/views.py`: Add `import logging` after the existing stdlib imports (line 9). Add `logger = logging.getLogger(__name__)` after the last import block (after line 27). Remove the inline `import logging; logger = logging.getLogger('django')` inside the `report_history` function body (line 241–242).
- `reports/utils/excel_generator.py`: Add `import logging` after `import os` (line 8). Add `logger = logging.getLogger(__name__)` after the last import block (after line 21).

---

#### - [x] T-02 — Fix `log_and_suppress` to preserve stack traces

**File:** `ndas/custom_codes/error_handlers.py:158`

Change `log.error(...)` to `log.exception(...)`:

```python
# BEFORE (line 158):
log.error(f"Suppressed error in {func.__name__}: {e}")

# AFTER:
log.exception(f"Suppressed error in {func.__name__}: {e}")
```

---

#### - [x] T-03 — Fix `handle_view_errors` ValidationError branch

**File:** `ndas/custom_codes/error_handlers.py:66–87`

Two changes in the `ValidationError` handler:

**3a — Raise log level** (line 80): Change `logger.info(` to `logger.warning(`.

**3b — Remove recursive call** (line 84–87): Replace the tail of the except block:
```python
# BEFORE (lines 84–87):
                if redirect_url:
                    return redirect(redirect_url)
                # Let the view handle re-rendering the form with errors
                return view_func(request, *args, **kwargs)

# AFTER:
                if redirect_url:
                    return redirect(redirect_url)
                if render_template:
                    return render(request, render_template, {'error': error_msg})
                return redirect('home')
```

---

#### - [x] T-04 — Fix 7 bare `except:` clauses

**4a — `patients/models.py:451–460` — `isLastGMANormal` (also fixes T-11 double query)**

Replace the entire property body:
```python
# BEFORE (lines 445–460):
    @property
    def isLastGMANormal(self):
        """Check if last GMA assessment is normal"""
        if not hasattr(self, "pk") or not self.pk:
            return True

        if GMAssessment.objects.filter(patient=self).exists():
            try:
                latest = (
                    GMAssessment.objects.filter(patient=self).order_by("-id").first()
                )
                return latest.is_diagnosis_normal if latest else False
            except:
                return False
        else:
            return True

# AFTER:
    @property
    def isLastGMANormal(self):
        """Check if last GMA assessment is normal"""
        if not hasattr(self, "pk") or not self.pk:
            return True
        latest = GMAssessment.objects.filter(patient=self).order_by("-id").first()
        return latest.is_diagnosis_normal if latest else True
```

**4b — `patients/models.py:526` — `getDiagnosisList`**

```python
# BEFORE:
        except:
            var_gma_dx_list = "No GM assessments"

# AFTER:
        except Exception as e:
            logger.warning(f"Error getting GMA diagnosis list for patient {self.pk}: {e}")
            var_gma_dx_list = "No GM assessments"
```

**4c — `patients/models.py:2246–2251` — `Bookmark.get_bookmarked_object_url()`**

The local import on line 2232 already reads `from django.urls import reverse`. Extend it to include `NoReverseMatch`:

```python
# BEFORE (line 2232):
        from django.urls import reverse

# AFTER:
        from django.urls import reverse, NoReverseMatch
```

Then replace the bare except:
```python
# BEFORE (lines 2250–2251):
            except:
                pass

# AFTER:
            except NoReverseMatch as e:
                logger.warning(
                    f"URL reverse failed for bookmark {self.pk} "
                    f"(type={self.bookmark_type}): {e}"
                )
```

**4d — `video/views.py:127–130` — `video_detail` view**

```python
# BEFORE:
    try:
        is_new_file = video.is_new_file()
    except:
        is_new_file = True

# AFTER:
    try:
        is_new_file = video.is_new_file()
    except Exception as e:
        logger.warning(f"Could not determine new-file status for video {video.id}: {e}")
        is_new_file = True
```

**4e — `ndas/custom_codes/delete_helpers.py:128–133` — entity name helper**

```python
# BEFORE:
    try:
        str_repr = str(entity)
        if str_repr and str_repr != f"{entity.__class__.__name__} object":
            return str_repr
    except:
        pass

# AFTER:
    try:
        str_repr = str(entity)
        if str_repr and str_repr != f"{entity.__class__.__name__} object":
            return str_repr
    except Exception:
        pass
```

**4f — `reports/views.py:232–235` — expired file deletion**

```python
# BEFORE:
                        try:
                            os.remove(file_path)
                        except:
                            pass

# AFTER:
                        try:
                            os.remove(file_path)
                        except OSError as e:
                            logger.warning(f"Failed to delete expired report {file_path}: {e}")
```

**4g — `reports/utils/excel_generator.py:318–322` — column width loop**

```python
# BEFORE:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass

# AFTER:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except (TypeError, ValueError):
                    pass
```

---

#### - [x] T-05 — Fix duplicate Exists subquery evaluation in dashboard

**File:** `patients/views.py:134–165`

Replace lines 134–165 with:

```python
    # Get new patients (no videos) — build annotated queryset once, derive count + list
    has_videos = Video.objects.filter(patient=OuterRef('pk'))
    _patients_no_videos = _patients_qs.annotate(
        has_videos=Exists(has_videos)
    ).filter(has_videos=False)
    patients_new_count = _patients_no_videos.count()
    Patients_new_list_10 = _patients_no_videos.select_related(
        'added_by', 'last_edit_by'
    ).only(
        'id', 'baby_name', 'bht', 'created_at',
        'added_by__username', 'last_edit_by__username'
    )[:5]

    # Get new videos (no GM assessments) — same pattern
    has_gm_assessment = GMAssessment.objects.filter(video_file=OuterRef('pk'))
    _new_videos_qs = Video.objects.filter(patient__in=_patients_qs).annotate(
        has_assessment=Exists(has_gm_assessment)
    ).filter(has_assessment=False)
    new_videos_count = _new_videos_qs.count()
    new_videos = _new_videos_qs.select_related(
        'patient', 'added_by'
    ).only(
        'id', 'title', 'created_at',
        'patient__baby_name', 'added_by__username'
    )[:5]
```

---

#### - [x] T-06 — Add `institution` parameter to four chart functions

**File:** `ndas/custom_codes/custom_methods.py`

**6a — `get_gma_diagnosis_data`** (lines 15–28):
```python
# BEFORE:
def get_gma_diagnosis_data():
    from patients.models import GMAssessment
    data = GMAssessment.objects.values('diagnosis__abr').annotate(patient_count=Count('patient'))

# AFTER:
def get_gma_diagnosis_data(institution=None):
    from patients.models import GMAssessment, Patient
    _pts = Patient.objects.for_institution(institution)
    data = GMAssessment.objects.filter(patient__in=_pts).values('diagnosis__abr').annotate(patient_count=Count('patient'))
```
Rest of the function is unchanged.

**6b — `get_all_diagnosis_data`** (lines 30–42):
```python
# BEFORE:
def get_all_diagnosis_data():
    from patients.models import GMAssessment, HINEAssessment, DevelopmentalAssessment
    dx_gma_data = getCountZeroIfNone(GMAssessment.objects.filter(diagnosis_conclusion='ABNORMAL'))
    dx_hine_data = getCountZeroIfNone(HINEAssessment.objects.filter(score__lt = 73))
    dx_da_data = getCountZeroIfNone(DevelopmentalAssessment.objects.filter(is_dx_normal=False))

# AFTER:
def get_all_diagnosis_data(institution=None):
    from patients.models import GMAssessment, HINEAssessment, DevelopmentalAssessment, Patient
    _pts = Patient.objects.for_institution(institution)
    dx_gma_data = getCountZeroIfNone(GMAssessment.objects.filter(patient__in=_pts, diagnosis_conclusion='ABNORMAL'))
    dx_hine_data = getCountZeroIfNone(HINEAssessment.objects.filter(patient__in=_pts, score__lt=73))
    dx_da_data = getCountZeroIfNone(DevelopmentalAssessment.objects.filter(patient__in=_pts, is_dx_normal=False))
```
Rest of the function is unchanged.

**6c — `get_userStats`** (lines 44–74):
```python
# BEFORE:
def get_userStats():
    from patients.models import GMAssessment, HINEAssessment, DevelopmentalAssessment, Patient, CDICRecord, Attachment, Bookmark
    from video.models import Video
    from users.models import CustomUser

    def _counts(qs, field='added_by_id'):
        return {row[field]: row['count'] for row in qs.values(field).annotate(count=Count('id'))}

    pt_counts         = _counts(Patient.objects.all())
    video_counts      = _counts(Video.objects.all())
    gma_counts        = _counts(GMAssessment.objects.all())
    hine_counts       = _counts(HINEAssessment.objects.all())
    da_counts         = _counts(DevelopmentalAssessment.objects.all())
    cdic_counts       = _counts(CDICRecord.objects.all())
    attachment_counts = _counts(Attachment.objects.all())
    bookmark_counts   = _counts(Bookmark.objects.all(), field='owner_id')

    user_stats = {}
    for user in CustomUser.objects.only('id', 'username'):

# AFTER:
def get_userStats(institution=None):
    from patients.models import GMAssessment, HINEAssessment, DevelopmentalAssessment, Patient, CDICRecord, Attachment, Bookmark
    from video.models import Video
    from users.models import CustomUser

    def _counts(qs, field='added_by_id'):
        return {row[field]: row['count'] for row in qs.values(field).annotate(count=Count('id'))}

    _pts = Patient.objects.for_institution(institution)
    pt_counts         = _counts(_pts)
    video_counts      = _counts(Video.objects.filter(patient__in=_pts))
    gma_counts        = _counts(GMAssessment.objects.filter(patient__in=_pts))
    hine_counts       = _counts(HINEAssessment.objects.filter(patient__in=_pts))
    da_counts         = _counts(DevelopmentalAssessment.objects.filter(patient__in=_pts))
    cdic_counts       = _counts(CDICRecord.objects.filter(patient__in=_pts))
    attachment_counts = _counts(Attachment.objects.filter(patient__in=_pts))
    bookmark_counts   = _counts(
        Bookmark.objects.filter(owner__institution=institution) if institution else Bookmark.objects.all(),
        field='owner_id'
    )

    _users_qs = CustomUser.objects.filter(institution=institution).only('id', 'username') if institution else CustomUser.objects.only('id', 'username')
    user_stats = {}
    for user in _users_qs:
```
Rest of the function body (lines 63–74) is unchanged.

**6d — `get_admissions_data_barchart`** (lines 76–101):
```python
# BEFORE:
def get_admissions_data_barchart():
    from patients.models import Patient
    today = timezone.now().date()
    five_months_ago = today - timedelta(days=30*5)
    admissions = (
        Patient.objects
        .filter(dob_tob__gte=five_months_ago)

# AFTER:
def get_admissions_data_barchart(institution=None):
    from patients.models import Patient
    today = timezone.now().date()
    five_months_ago = today - timedelta(days=30*5)
    admissions = (
        Patient.objects.for_institution(institution)
        .filter(dob_tob__gte=five_months_ago)
```
Rest of the function is unchanged.

---

#### - [x] T-07 — Update dashboard call-sites for chart functions

**File:** `patients/views.py:168–171`

```python
# BEFORE:
    bar_chart_monthly_admissions = get_admissions_data_barchart()
    diagnosis_data_gma = get_gma_diagnosis_data()
    diagnosis_data_all = get_all_diagnosis_data()
    user_stat = get_userStats()

# AFTER:
    bar_chart_monthly_admissions = get_admissions_data_barchart(_inst)
    diagnosis_data_gma = get_gma_diagnosis_data(_inst)
    diagnosis_data_all = get_all_diagnosis_data(_inst)
    user_stat = get_userStats(_inst)
```

Note: `_inst = getattr(request, 'institution', None)` is already defined at line 103 of the dashboard view.

---

#### - [x] T-08 — Scope search view user lists to institution

**File:** `patients/views.py`

**8a — `search_start` view** (lines 674–677):
```python
# BEFORE:
@login_required(login_url="user-login")
def search_start(request):
    username_list = CustomUser.objects.all()
    return render(request, "patients/search.html", {"username_list": username_list})

# AFTER:
@login_required(login_url="user-login")
def search_start(request):
    _inst = getattr(request, 'institution', None)
    username_list = (
        CustomUser.objects.filter(institution=_inst).only('username')
        if _inst else CustomUser.objects.only('username')
    )
    return render(request, "patients/search.html", {"username_list": username_list})
```

**8b — `search_results` view** (line 696):
```python
# BEFORE:
    username_list = CustomUser.objects.all()

# AFTER:
    _inst = getattr(request, 'institution', None)
    username_list = (
        CustomUser.objects.filter(institution=_inst).only('username')
        if _inst else CustomUser.objects.only('username')
    )
```

---

#### - [x] T-09 — Scope `admin_user_list` to institution for non-superusers

**File:** `users/views.py:541`

```python
# BEFORE:
    users = CustomUser.objects.all().order_by('-date_joined')

# AFTER:
    _inst = getattr(request, 'institution', None)
    if request.user.is_superuser:
        users = CustomUser.objects.all().order_by('-date_joined')
    elif _inst is not None:
        users = CustomUser.objects.filter(institution=_inst).order_by('-date_joined')
    else:
        # Non-superuser with no institution assigned — return nothing rather than leak data
        users = CustomUser.objects.none()
```

---

#### - [x] T-10 — Add video-patient ownership guard in `assessment_add`

**File:** `patients/views.py:870–871`

After the two `get_object_or_404` calls, add the guard immediately:
```python
    patient = get_object_or_404(Patient.objects.for_institution(getattr(request, 'institution', None)), pk=ptid)
    video_file = get_object_or_404(Video, pk=fid)

    # Guard: video must belong to this patient
    if video_file.patient_id != patient.pk:
        messages.error(request, "This video does not belong to the selected patient.")
        return redirect("view-patient", pk=patient.pk)
```

---

#### - [x] T-11 — Wrap assessment M2M save in `transaction.atomic()`

**File:** `patients/views.py`

**11a — Add import**: Add `from django.db import transaction` to the imports at the top of `patients/views.py`. Insert after the existing `from django.urls import reverse` line.

**11b — Wrap the save block**: Locate the `try:` block at line 883 inside `assessment_add`. Wrap only the save and M2M operations:

```python
# BEFORE (lines 896–901):
                assessment.save()

                # Handle many-to-many relationship for diagnosis
                diagnosis_list = assessment_form.cleaned_data.get('diagnosis', [])
                if diagnosis_list:
                    assessment.diagnosis.set(diagnosis_list)

# AFTER:
                with transaction.atomic():
                    assessment.save()
                    diagnosis_list = assessment_form.cleaned_data.get('diagnosis', [])
                    if diagnosis_list:
                        assessment.diagnosis.set(diagnosis_list)
```

The outer `try: ... except ValidationError ... except Exception` block remains as-is for error handling.

---

#### - [x] T-12 — Add `institution` param to `ExcelReportGenerator.calculate_quality_metrics()`

**File:** `reports/utils/excel_generator.py`

**12a — Method signature** (line 206):
```python
# BEFORE:
    def calculate_quality_metrics(self, start_date=None, end_date=None):

# AFTER:
    def calculate_quality_metrics(self, start_date=None, end_date=None, institution=None):
```

**12b — Add institution-scoped patient base queryset** at the top of the method body (after `metrics = {}` on line 216):
```python
        # Scope all queries to institution (None = all institutions, Phase 1 safe)
        _pts = Patient.objects.for_institution(institution)
```

**12c — Replace all `Patient.objects.filter(patient_filter)` calls** in the method with `_pts.filter(patient_filter)`:
- Line 235: `total_patients = _pts.filter(patient_filter).count()`
- Line 238: `complete_birth_data = _pts.filter(patient_filter, pog_wks__isnull=False, ...).count()`
- Line 254: `patients_with_assessments = _pts.filter(patient_filter).filter(...).distinct().count()`

**12d — Fix `gm_total` cross-institution count** (lines 272–283):
```python
# BEFORE:
        gm_total = GMAssessment.objects.all().count()
        if gm_total > 0:
            gm_complete = GMAssessment.objects.filter(
                diagnosis_conclusion__isnull=False,
                date_of_assessment__isnull=False
            ).count()

# AFTER:
        gm_total = GMAssessment.objects.filter(patient__in=_pts).count()
        if gm_total > 0:
            gm_complete = GMAssessment.objects.filter(
                patient__in=_pts,
                diagnosis_conclusion__isnull=False,
                date_of_assessment__isnull=False
            ).count()
```

---

#### - [x] T-13 — Thread `institution` through `generate()` and its call-site

**File:** `reports/utils/excel_generator.py`

**13a — `generate()` signature** (line 701):
```python
# BEFORE:
    def generate(self, output_path=None, start_date=None, end_date=None, parameters=None):

# AFTER:
    def generate(self, output_path=None, start_date=None, end_date=None, parameters=None, institution=None):
```

**13b — Update internal call to `calculate_quality_metrics`** (line 744):
```python
# BEFORE:
        quality_metrics = self.calculate_quality_metrics(start_date, end_date)

# AFTER:
        quality_metrics = self.calculate_quality_metrics(start_date, end_date, institution=institution)
```

**File:** `reports/views.py`

**13c — Pass `institution` at `generator.generate()` call-site** (lines 154–158):
```python
# BEFORE:
            file_path, metadata = generator.generate(
                start_date=start_date,
                end_date=end_date,
                parameters=parameters
            )

# AFTER:
            file_path, metadata = generator.generate(
                start_date=start_date,
                end_date=end_date,
                parameters=parameters,
                institution=getattr(request, 'institution', None),
            )
```

---

### Acceptance Criteria

- [x] **AC-01 — Chart functions are institution-scoped**
  - Given Institution A has 3 patients with GMA assessments and Institution B has 5
  - When the dashboard view renders for an Institution A user
  - Then `get_gma_diagnosis_data(_inst)`, `get_all_diagnosis_data(_inst)`, `get_admissions_data_barchart(_inst)`, and `get_userStats(_inst)` each return data scoped only to Institution A's patients

- [x] **AC-02 — Chart functions with `institution=None` return all records**
  - Given `institution=None` is passed to any chart function
  - When the function executes
  - Then it returns unfiltered data (Phase 1 backward compatibility)

- [x] **AC-03 — Search dropdown shows only institution-scoped users**
  - Given Institution A has 2 users and Institution B has 3 users
  - When `search_start` or `search_results` is called by an Institution A user with `request.institution` set
  - Then `username_list` contains only Institution A's 2 users

- [x] **AC-04 — `admin_user_list` scopes correctly by role**
  - Given an `is_staff` non-superuser admin of Institution A calls `admin_user_list`
  - When the view builds its queryset
  - Then only users with `institution=_inst` are included
  - And given a superuser calls the same view
  - Then all users across all institutions are included

- [x] **AC-05 — Assessment creation is atomic**
  - Given `assessment.save()` succeeds but `assessment.diagnosis.set()` raises an `IntegrityError`
  - When the exception propagates out of the `transaction.atomic()` block
  - Then the database rolls back and no `GMAssessment` record exists — no orphan

- [x] **AC-06 — Video-patient ownership is enforced**
  - Given `ptid` resolves to Patient A and `fid` resolves to a video belonging to Patient B
  - When `assessment_add` is called with these mismatched IDs
  - Then the view redirects to Patient A's detail page with an error message and no assessment is created

- [x] **AC-07 — `handle_view_errors` ValidationError does not recurse**
  - Given a view decorated with `@handle_view_errors()` (no `redirect_url`, no `render_template`) raises `ValidationError`
  - When the decorator catches it
  - Then a redirect to `'home'` is returned and the wrapped view function is NOT invoked a second time
  - **Note:** AC-07 is source-verified — the recursive `view_func(request, *args, **kwargs)` call is removed entirely from the ValidationError branch. The absence of that call in the source is sufficient verification; no runtime mock test is required. Runtime smoke test: call the decorated view with a POST that triggers ValidationError and assert `response.status_code == 302` and `response['Location']` resolves to `'home'`.

- [x] **AC-08 — ValidationError is logged at WARNING level**
  - Given a view raises `ValidationError` that `handle_view_errors` catches
  - When the log output is inspected
  - Then a WARNING entry is present (not INFO)

- [x] **AC-09 — `log_and_suppress` preserves full stack traces**
  - Given a function decorated with `@log_and_suppress()` raises an exception
  - When the exception is caught
  - Then `log.exception()` is called and the full traceback appears in the log (not just the exception message string)

- [x] **AC-10 — No bare `except:` clauses remain in the 5 affected files**
  - Given a `grep -n "except:"` search of `patients/models.py`, `video/views.py`, `ndas/custom_codes/delete_helpers.py`, `reports/views.py`, `reports/utils/excel_generator.py`
  - When results are reviewed
  - Then zero matches appear in any of these files

- [x] **AC-11 — `isLastGMANormal` issues exactly one query**
  - Given a Patient with no GMA assessments
  - When `patient.isLastGMANormal` is accessed
  - Then exactly 1 DB query is issued and `True` is returned
  - And given a Patient whose latest GMA is abnormal
  - When `patient.isLastGMANormal` is accessed
  - Then exactly 1 DB query is issued and `False` is returned

- [x] **AC-12 — Dashboard Exists subqueries are not duplicated**
  - Given the dashboard view executes with query logging enabled
  - When the SQL log is inspected
  - Then the `has_videos` correlated subquery appears in exactly 1 SQL statement and the `has_gm_assessment` correlated subquery appears in exactly 1 SQL statement

- [x] **AC-13 — `calculate_quality_metrics` scopes GM count to institution**
  - Given Institution A has 2 GM assessments and Institution B has 8
  - When `calculate_quality_metrics(institution=institution_a)` is called
  - Then `gm_total` equals 2 and the `gm_quality` percentage is computed using only Institution A's assessments

- [x] **AC-14 — Module-level loggers present in all four files and use `__name__`**
  - Given `patients/models.py`, `patients/views.py`, `reports/views.py`, `reports/utils/excel_generator.py` are opened
  - When the import block is inspected
  - Then each file has `import logging` in the stdlib section and `logger = logging.getLogger(__name__)` at module level before the first class or function definition
  - And `reports/views.py` has no inline `import logging` inside any function body
  - And `patients/views.py` no longer uses `logging.getLogger("django")`

---

## Additional Context

### Dependencies

- No new packages required.
- No model migrations required.
- No template changes required.
- `from django.db import transaction` — already in Django stdlib, just needs to be imported in `patients/views.py`.

### Testing Strategy

Run existing isolation tests to confirm no regressions:
```bash
python manage.py test institution.tests.test_isolation
python manage.py test patients
python manage.py test reports
python manage.py test video
python manage.py test users
```

**Existing `get_userStats` tests** (`patients/tests/test_views.py:UserStatsQueryCountTest`) call `get_userStats()` without arguments. After T-06c, `institution=None` returns all records — these tests continue to pass unchanged.

**New test required for AC-01 — `get_userStats` institution isolation:** The existing tests only cover query count and return structure. A new test must assert that `get_userStats(institution=inst_a)` excludes records belonging to Institution B patients. Reference `institution/tests/test_isolation.py` for the two-institution fixture setup pattern:
```python
# Pattern: create two institutions, two patients (one per institution), call get_userStats(inst_a)
# Assert: only inst_a's patient/record counts appear in result; inst_b contributor not in dict
```

For manual verification of chart isolation: log in as a user of a specific institution with `MULTI_INSTITUTION_ENABLED=True` and confirm the dashboard bar chart, GMA diagnosis chart, all-diagnosis chart, and user stats table reflect only that institution's records.

For AC-05 (atomic assessment): temporarily inject a side-effect into `diagnosis.set()` or use `transaction.on_commit()` testing with `TestCase` (which wraps each test in a transaction) to verify rollback behavior.

### Notes

**Pre-mortem: High-risk items to watch during implementation**

1. ~~**T-10 redirect URL name**~~ — **RESOLVED.** `"view-patient"` confirmed in `patients/urls.py:29` ✓

2. **T-06c `get_userStats` — Bookmark scoping** — `Bookmark.objects.filter(owner__institution=institution)` traverses the `owner__institution` FK. `CustomUser.institution` is nullable (confirmed). Users with `institution=None` are excluded from the filter when `institution` is set — correct isolation behaviour. All institution-active users have `institution` set by deployment policy.

3. **T-12 `_pts` queryset reuse in `calculate_quality_metrics`** — `_pts` is a lazy queryset. When used as `_pts.filter(patient_filter)`, it creates a new queryset each time — no issue. However, `_pts` itself is never evaluated as a list; Django will fold the institution filter into each resulting SQL as a subquery or JOIN. This is correct but worth verifying performance doesn't regress on large datasets (the method is only called during report generation, not on every request).

4. ~~**T-03 ValidationError handler — existing callers**~~ — **RESOLVED.** Every real caller of `@handle_view_errors()` in the codebase sets `redirect_url`. The recursive branch at line 87 is currently unreachable. T-03 is proactive hardening against future callers, not a breaking change. No callers relied on the re-invocation.

5. **T-11 `transaction.atomic()` placement** — The `with transaction.atomic():` block must sit *inside* the existing `try:` block (not wrapping it), so the existing `except ValidationError` and `except Exception` handlers still catch errors that propagate out of the transaction. The spec's placement — wrapping only `assessment.save()` + `diagnosis.set()` — is correct. After the atomic block rolls back, Django has issued ROLLBACK, leaving the connection clean; subsequent ORM operations in the `except Exception:` handler (lines 920–923) work normally.

6. ~~**T-04a `isLastGMANormal` return value change**~~ — **RESOLVED.** Confirmed one downstream use: `patients/models.py:668` uses `self.isLastGMANormal == False`. Old code: no assessments → outer `else` → `True` (no PT indication). New code: no assessments → `.first()` returns `None` → `True` (same, no PT indication). Semantic change only applies to the impossible `exists()=True/.first()=None` case. Behaviour is correct and consistent with `isLastHINENormal` / `isLastDANormal`.

**Known limitation — ELI-02: `get_userStats` superuser contributions excluded from per-user breakdown**

When `get_userStats(institution=inst_a)` is called, `_users_qs` is filtered to Institution A users. Records added by superusers (who have `institution=None`) for Institution A's patients appear in `pt_counts`, `gma_counts`, etc. (scoped by `patient__in=_pts`), but superusers are not in `_users_qs`. Their contributions are silently omitted from the user breakdown widget. Dashboard total counts remain correct. This is accepted behaviour — superuser contributions to a specific institution's records are an edge case and displaying them in the institution-scoped widget would require cross-institution user lookup. Add an inline comment to the code:
```python
# Note: superuser contributions (institution=None) are excluded from this breakdown.
# Dashboard total counts above remain correct; only the per-user breakdown is affected.
```

**Backward-compatibility notes**

- All function signature changes use default `institution=None`, which preserves existing Phase 1 call-sites that pass no arguments.
- `generate()` and `calculate_quality_metrics()` new `institution` parameter is keyword-only with default `None` — existing callers in tests or scripts are unaffected.

**Out of scope — future work**

- Cache `get_userStats()` per institution with a 5-minute TTL once Phase 2 is live (deferred, Q2 decision).
- Remove `'unsafe-inline'` / `'unsafe-eval'` from dev `CSP_SCRIPT_SRC` (deferred, Q4 decision).
- Add `db_index=True` to `CDICRecord.is_discharged` — the dashboard filters on it but the model has no explicit index (flagged in the audit but out of scope for this spec).

## Review Notes

- Adversarial review completed (2026-03-04)
- Findings: 13 total, 5 fixed, 8 skipped
- Resolution approach: auto-fix
- Fixed: F1 (critical — Video cross-institution fetch), F3 (GMA count inconsistency), F4 (users_total_count for superusers), F6 (isLastGMANormal exception guard), F7 (user search institution validation)
- Skipped: F2 (spec-mandated), F5 (correct by analysis), F8/F13 (undecided/pre-existing), F9 (spec-mandated), F10/F11/F12 (pre-existing/out-of-scope)
