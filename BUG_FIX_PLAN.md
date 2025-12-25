# NDAS Project - Bug Fix Implementation Plan

**Generated**: 2025-12-25
**Estimated Total Effort**: 40-60 hours
**Recommended Approach**: Fix in priority order, test thoroughly after each phase

---

## PHASE 1: CRITICAL FIXES (Estimated: 8-12 hours)

**Priority**: MUST FIX IMMEDIATELY - System-breaking bugs
**Testing**: After each fix, run relevant tests and manual verification

### 1.1 Fix DevelopmentalAssessment.save() Method
**File**: `patients/models.py:2748-2751`
**Effort**: 5 minutes
**Risk**: LOW

```python
# Current (BROKEN):
def save(self, *args, **kwargs):
    """Override save to automatically update is_dx_normal"""
    self.is_dx_normal = self.is_normal

# Fixed:
def save(self, *args, **kwargs):
    """Override save to automatically update is_dx_normal"""
    self.is_dx_normal = self.is_normal
    super().save(*args, **kwargs)
```

**Testing**: Create and save a DevelopmentalAssessment, verify it persists to database.

---

### 1.2 Fix DiagnosisList.__str__() Method
**File**: `patients/models.py:2275`
**Effort**: 5 minutes
**Risk**: LOW

```python
# Current (WRONG):
def __str__(self):
    return str(self.title + " (" + self.title + ")")

# Fixed:
def __str__(self):
    return str(self.title + " (" + self.abr + ")")
```

**Testing**: Access DiagnosisList in admin or forms, verify display shows "Title (Abbreviation)".

---

### 1.3 Fix/Remove IndicationsForGMA.getIndicationList Property
**File**: `patients/models.py:2262`
**Effort**: 15 minutes
**Risk**: MEDIUM (depends on usage)

**Step 1**: Search for usage of `getIndicationList`:
```bash
grep -r "getIndicationList" .
```

**Step 2A**: If NOT used anywhere, remove the property entirely.

**Step 2B**: If used, determine intent and replace with:
```python
# Remove the property, add class method instead:
@classmethod
def get_all_titles(cls):
    """Get all indication titles"""
    return cls.objects.all().values_list("title", flat=True)
```

**Testing**: Search codebase for usage, update callers if needed.

---

### 1.4 Add Trailing Slashes to URLs (16 instances)
**File**: `patients/urls.py`
**Effort**: 20 minutes
**Risk**: LOW (but test all URLs)

**Changes**:
```python
# Line 12
path("print/", views.print, name='print'),  # Added /

# Lines 19-27
path("manager/patient/new/", views.patient_manager_new, name="patient-manager-new"),
path("manager/patient/normal/", views.patient_manager_normal, name="patient-manager-normal"),
path("manager/patient/diagnosed/any/", views.patient_manager_diagnosed_any, name="patient-manager-diagnosed-any"),
path("manager/patient/diagnosed/gma/normal/", views.patient_manager_diagnosed_gma_normal, name="patient-manager-diagnosed-gma-normal"),
path("manager/patient/diagnosed/gma/abnormal/", views.patient_manager_diagnosed_gma_abnormal, name="patient-manager-diagnosed-gma-abnormal"),
path("manager/patient/diagnosed/hine/", views.patient_manager_diagnosed_hine, name="patient-manager-diagnosed-hine"),
path("manager/patient/diagnosed/da/normal/", views.patient_manager_diagnosed_da_normal, name="patient-manager-diagnosed-da-normal"),
path("manager/patient/diagnosed/da/abnormal/", views.patient_manager_diagnosed_da_abnormal, name="patient-manager-diagnosed-da-abnormal"),
path("manager/patient/discharged/", views.patient_manager_discharged, name="patient-manager-discharged"),

# Line 49
path("attachment/manager/patient/<str:pid>/", views.attachment_manager_patient, name="attachment-manager-patient"),

# Lines 64-68
path("manager/assessment/recent/", views.assessment_manager_recent, name="assessment-manager-recent"),
path("manager/assessment/normal/", views.assessment_manager_normal, name="assessment-manager-normal"),
path("manager/assessment/abnormal/", views.assessment_manager_abnormal, name="assessment-manager-abnormal"),
path("manager/assessment/informed/", views.assessment_manager_informed, name="assessment-manager-informed"),
path("manager/assessment/not-informed/", views.assessment_manager_not_informed, name="assessment-manager-not-informed"),
```

**Testing**: Test each URL manually or with automated URL tests. Verify no 301 redirects.

---

### 1.5 Replace .objects.get() with get_object_or_404() (24 instances)
**File**: `patients/views.py`
**Effort**: 1.5 hours
**Risk**: LOW

**Add import at top of file**:
```python
from django.shortcuts import render, redirect, get_object_or_404  # Ensure get_object_or_404 is imported
```

**Replace all instances** (line numbers from analysis):

**Line 377**:
```python
# Before:
selected_patient = Patient.objects.get(id=pk)
# After:
selected_patient = get_object_or_404(Patient, id=pk)
```

**Line 592**:
```python
# Before:
patient = Patient.objects.get(id=pk)
# After:
patient = get_object_or_404(Patient, id=pk)
```

**Repeat for lines**: 1068, 1091 (2 instances), 1092, 1390, 1608, 1716, 1878, 2167, 2488, 2699, 2887, 3074, 3276, 3505, 3650

**Pattern to find/replace**:
```bash
# Search pattern (regex):
\.objects\.get\(

# Review each instance and replace with get_object_or_404()
```

**Testing**: Try to access non-existent IDs, verify 404 pages appear instead of 500 errors.

---

### 1.6 Fix get_object_or_404 in users/views.py (3 instances)
**File**: `users/views.py`
**Effort**: 15 minutes
**Risk**: LOW

**Line 215**:
```python
# Before:
custom_user = CustomUser.objects.get(id=pk)
# After:
custom_user = get_object_or_404(CustomUser, id=pk)
```

**Line 221**:
```python
# Before:
custom_user = CustomUser.objects.get(username=username)
# After:
custom_user = get_object_or_404(CustomUser, username=username)
```

**Line 443**:
```python
# Before:
user_session = UserSession.objects.get(id=session_id, user=request.user)
# After:
user_session = get_object_or_404(UserSession, id=session_id, user=request.user)
```

---

### 1.7 Fix File Handle Resource Leaks (6 instances)
**File**: `reports/views.py`
**Effort**: 30 minutes
**Risk**: LOW

**Lines 320-321** (download_report):
```python
# Before:
file_handle = open(file_path, 'rb')
response = FileResponse(file_handle, content_type=content_type)

# After:
with open(file_path, 'rb') as file_handle:
    response = FileResponse(file_handle.read(), content_type=content_type)
```

**Repeat for**:
- Line 341-342 (download_gm_assessment_pdf)
- Line 360-361 (download_hine_assessment_pdf)
- Line 379-380 (download_da_assessment_pdf)
- Line 398-399 (download_cdic_assessment_pdf)
- Line 417-418 (download_gpa_assessment_pdf)

**Note**: FileResponse with .read() loads entire file into memory. For large files, consider:
```python
from django.http import StreamingHttpResponse

def file_iterator(file_path, chunk_size=8192):
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            yield chunk

response = StreamingHttpResponse(file_iterator(file_path), content_type=content_type)
```

**Testing**: Download reports, verify files download correctly and file handles are closed.

---

### 1.8 Fix Database Query on Every Request in Middleware
**File**: `users/middleware.py:35-39`
**Effort**: 1 hour
**Risk**: MEDIUM (affects all authenticated requests)

**Current code**:
```python
UserSession.objects.filter(
    user=request.user,
    session_key=session_key,
    is_active=True
).update(last_activity=timezone.now())
```

**Fixed code**:
```python
# Add at top of file
from django.core.cache import cache

# In process_request method, replace lines 35-39:
cache_key = f"user_session_update_{request.user.id}_{session_key}"
last_update = cache.get(cache_key)

# Only update if last update was more than 60 seconds ago
if last_update is None or (timezone.now() - last_update).seconds > 60:
    try:
        UserSession.objects.filter(
            user=request.user,
            session_key=session_key,
            is_active=True
        ).update(last_activity=timezone.now())
        cache.set(cache_key, timezone.now(), 120)  # Cache for 2 minutes
    except Exception:
        pass
```

**Testing**: Monitor database queries per request (use django-debug-toolbar). Verify queries reduced from every request to once per minute per user.

---

### 1.9 Fix Error Message Display (4 instances)
**File**: `patients/views.py`
**Effort**: 10 minutes
**Risk**: LOW

**Line 1055**:
```python
# Before:
messages.success(request, assessment_form_data.errors)
# After:
messages.error(request, assessment_form_data.errors)
```

**Repeat for**:
- Line 1742 (bookmark_edit)
- Line 2152 (attachment_edit)
- Line 2360 (cdic_assessment_edit)

**Testing**: Submit invalid forms, verify error messages appear as errors, not success messages.

---

## PHASE 2: HIGH PRIORITY FIXES (Estimated: 12-16 hours)

**Priority**: Major performance and security issues
**Testing**: Performance testing and load testing recommended

### 2.1 Add Missing select_related to Assessment Manager Views
**File**: `patients/views.py`
**Effort**: 45 minutes
**Risk**: LOW

**Lines to fix**: 1211, 1239, 1270, 1301, 1332, 1363

**Pattern**:
```python
# Before:
assessment_list = GMAssessment.objects.filter(...).order_by("-id")

# After:
assessment_list = GMAssessment.objects.filter(...).select_related(
    'patient', 'added_by', 'last_edit_by', 'video_file'
).order_by("-id")
```

**Apply to all 6 functions**:
- assessment_manager() - line 1211
- assessment_manager_recent() - line 1239
- assessment_manager_normal() - line 1270
- assessment_manager_abnormal() - line 1301
- assessment_manager_informed() - line 1332
- assessment_manager_not_informed() - line 1363

**Testing**: Use django-debug-toolbar to verify query count reduction. Should go from ~50 queries to ~5 for 10 assessments.

---

### 2.2 Add select_related to patient_view() Queries
**File**: `patients/views.py:376-412`
**Effort**: 30 minutes
**Risk**: LOW

**Fix all 6 queries**:
```python
# Lines 390-412 - Replace all queries:
var_file_video = Video.objects.filter(patient=selected_patient).select_related(
    'added_by', 'last_edit_by'
).order_by("-id")

var_file_attachments = Attachment.objects.filter(patient=selected_patient).select_related(
    'added_by', 'last_edit_by'
).order_by("-id")

var_gma = GMAssessment.objects.filter(patient=selected_patient).select_related(
    'added_by', 'last_edit_by', 'video_file'
).order_by("-id")

var_hine = HINEAssessment.objects.filter(patient=selected_patient).select_related(
    'added_by', 'last_edit_by'
).order_by("-id")

var_da = DevelopmentalAssessment.objects.filter(patient=selected_patient).select_related(
    'added_by', 'last_edit_by'
).order_by("-id")

var_cdic = CDICRecord.objects.filter(patient=selected_patient).select_related(
    'added_by', 'last_edit_by'
).order_by("-id")
```

**Testing**: View patient detail page with debug toolbar. Verify query count reduced significantly.

---

### 2.3 Refactor Patient Model Properties to Avoid N+1 Queries
**File**: `patients/models.py:358-684`
**Effort**: 4-6 hours
**Risk**: HIGH (changes API, affects multiple views)

**Strategy**: Replace properties with manager methods

**Step 1**: Create custom manager in `patients/models.py`:

```python
from django.db import models
from django.db.models import Exists, OuterRef, Prefetch, Q, Count, Case, When

class PatientQuerySet(models.QuerySet):
    def with_status_annotations(self):
        """Annotate patients with status flags"""
        from video.models import Video

        return self.annotate(
            has_videos=Exists(Video.objects.filter(patient=OuterRef('pk'))),
            is_new=~Exists(Video.objects.filter(patient=OuterRef('pk'))),
            gma_count=Count('gmassessment', distinct=True),
            hine_count=Count('hineassessment', distinct=True),
        )

    def with_related_data(self):
        """Prefetch all related data efficiently"""
        return self.prefetch_related(
            'indecation_for_gma',
            'diagnosis',
            Prefetch('gmassessment_set', queryset=GMAssessment.objects.select_related('video_file')),
            Prefetch('hineassessment_set'),
            Prefetch('developmentalassessment_set'),
            Prefetch('cdicrecord_set'),
        )

class PatientManager(models.Manager):
    def get_queryset(self):
        return PatientQuerySet(self.model, using=self._db)

    def with_full_data(self):
        return self.get_queryset().with_status_annotations().with_related_data()
```

**Step 2**: Add manager to Patient model:
```python
class Patient(TimeStampedModel, UserTrackingMixin):
    # ... existing fields ...

    objects = PatientManager()

    # Keep existing properties for backward compatibility but mark as deprecated
    @property
    def isNewPatient(self):
        """DEPRECATED: Use annotated 'is_new' field instead"""
        if hasattr(self, 'is_new'):
            return self.is_new
        # Fallback to old behavior
        if hasattr(self, "pk") and self.pk:
            Video = apps.get_model("video", "Video")
            return not Video.objects.filter(patient=self.pk).exists()
        return True
```

**Step 3**: Update views to use manager methods:
```python
# In patients/views.py patient_manager():
patients = Patient.objects.with_full_data().filter(...).order_by("-id")
```

**Testing**: Extensive testing required. Verify all views still work correctly.

---

### 2.4 Add Profile Picture Validation
**File**: `users/forms.py`
**Effort**: 1 hour
**Risk**: LOW

**Add after line 245**:
```python
def clean_profile_picture(self):
    """Validate profile picture upload"""
    picture = self.cleaned_data.get('profile_picture')

    if not picture:
        return picture

    # Check file size (5MB max)
    if picture.size > 5 * 1024 * 1024:
        raise ValidationError(_('Image file size cannot exceed 5MB.'))

    # Check file extension
    valid_extensions = ['.jpg', '.jpeg', '.png']
    ext = os.path.splitext(picture.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError(_('Unsupported file extension. Use JPG, JPEG, or PNG.'))

    # Validate it's actually an image
    try:
        from PIL import Image
        img = Image.open(picture)
        img.verify()

        # Check dimensions (optional - max 4000x4000)
        if img.width > 4000 or img.height > 4000:
            raise ValidationError(_('Image dimensions too large. Maximum 4000x4000 pixels.'))

    except Exception:
        raise ValidationError(_('Invalid image file.'))

    # Reset file pointer after verification
    picture.seek(0)

    return picture
```

**Add import at top**:
```python
import os
from PIL import Image
```

**Testing**: Upload various files (valid images, oversized images, non-images renamed to .jpg). Verify validation works.

---

### 2.5 Fix Video Filter to Use Subquery Instead of Loading IDs
**File**: `video/views.py`
**Effort**: 30 minutes
**Risk**: LOW

**Lines 259-268 and 360-364**:
```python
# Before:
used_video_ids = GMAssessment.objects.values_list('video_file_id', flat=True)
queryset = queryset.exclude(id__in=used_video_ids)

# After:
from django.db.models import Exists, OuterRef

queryset = queryset.annotate(
    is_assessed=Exists(
        GMAssessment.objects.filter(video_file_id=OuterRef('pk'))
    )
).filter(is_assessed=False)
```

**Apply to**:
- video_manager() - lines 259-268
- video_manager_new_only() - lines 360-364

**Testing**: Filter videos by "new" status. Verify results are same but queries more efficient (check with debug toolbar).

---

### 2.6 Add Sanitization to problemlist Forms
**File**: `problemlist/forms.py`
**Effort**: 1.5 hours
**Risk**: MEDIUM

**Step 1**: Check if sanitization utilities exist:
```python
# Look for: ndas/custom_codes/sanitization.py
```

**Step 2A**: If utilities exist, add clean methods:
```python
from ndas.custom_codes.sanitization import sanitize_html  # Adjust import as needed

def clean_name(self):
    return sanitize_html(self.cleaned_data.get('name', ''))

def clean_description(self):
    return sanitize_html(self.cleaned_data.get('description', ''))

def clean_action_taken(self):
    return sanitize_html(self.cleaned_data.get('action_taken', ''))

def clean_outcome(self):
    return sanitize_html(self.cleaned_data.get('outcome', ''))

def clean_comments(self):
    return sanitize_html(self.cleaned_data.get('comments', ''))
```

**Step 2B**: If utilities don't exist, use bleach:
```bash
pip install bleach
```

```python
import bleach

ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li']
ALLOWED_ATTRS = {}

def clean_name(self):
    value = self.cleaned_data.get('name', '')
    return bleach.clean(value, tags=[], strip=True)  # No HTML in names

def clean_description(self):
    value = self.cleaned_data.get('description', '')
    return bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)

# Repeat for other fields
```

**Testing**: Submit forms with HTML/JavaScript in text fields. Verify malicious code is stripped.

---

### 2.7 Add Rate Limiting to CRUD Operations
**Files**: Multiple view files
**Effort**: 2 hours
**Risk**: LOW

**Pattern to apply**:
```python
from django_ratelimit.decorators import ratelimit

# For create/update operations:
@login_required(login_url="user-login")
@ratelimit(key='user', rate='10/m', method='POST')
@ratelimit(key='ip', rate='20/m', method='POST')
def patient_add(request):
    # ... existing code ...

# For delete operations:
@login_required(login_url="user-login")
@ratelimit(key='user', rate='5/m', method='POST')
@ratelimit(key='ip', rate='10/m', method='POST')
def patient_delete(request, pk):
    # ... existing code ...
```

**Apply to**:
- patients/views.py: patient_add, patient_edit, patient_delete
- patients/views.py: assessment CRUD operations
- video/views.py: video_add, video_edit, video_delete
- patients/views.py: attachment CRUD operations
- users/views.py: admin user management operations

**Testing**: Rapidly submit forms. Verify rate limiting kicks in after threshold.

---

### 2.8 Optimize Multiple filter().count() Calls
**File**: `patients/views.py`
**Effort**: 2 hours
**Risk**: MEDIUM

**Example fix for lines 2855-2857** (hine_assessment_manager):
```python
# Before:
context = {
    'normal': var_hine_list.filter(score__gte=60).count(),
    'moderate': var_hine_list.filter(score__gte=40, score__lt=60).count(),
    'significant': var_hine_list.filter(score__lt=40).count(),
}

# After:
from django.db.models import Count, Case, When, IntegerField

stats = var_hine_list.aggregate(
    normal=Count(Case(When(score__gte=60, then=1), output_field=IntegerField())),
    moderate=Count(Case(When(Q(score__gte=40) & Q(score__lt=60), then=1), output_field=IntegerField())),
    significant=Count(Case(When(score__lt=40, then=1), output_field=IntegerField())),
)

context = {
    'normal': stats['normal'],
    'moderate': stats['moderate'],
    'significant': stats['significant'],
}
```

**Apply to**:
- hine_assessment_manager (lines 2855-2857)
- hine_assessment_manager_by_patients (lines 2932-2934)
- da_assessment_manager (lines 3242-3243)
- da_assessment_manager_by_patients (lines 3348-3349)
- cdic managers (lines 2451, 2548)
- bookmark_manager (lines 1490-1491)

**Testing**: Verify counts are correct. Check query reduction with debug toolbar.

---

## PHASE 3: MEDIUM PRIORITY FIXES (Estimated: 12-18 hours)

**Priority**: Important improvements, not urgent
**Testing**: Standard testing after each fix

### 3.1 Add Missing Database Indexes
**Files**: `patients/models.py`, `users/models.py`
**Effort**: 30 minutes + migration time
**Risk**: LOW (but requires migration)

**Changes**:

**IndicationsForGMA** (line 2251-2252):
```python
title = models.CharField(max_length=75, null=False, blank=False, db_index=True)
level = models.CharField(max_length=6, choices=LEVEL_OF_INDICATION, null=False, db_index=True)
```

**DiagnosisList** (line 2267-2268):
```python
abr = models.CharField(max_length=6, null=False, blank=False, unique=True, db_index=True)
title = models.CharField(max_length=255, null=False, blank=False, db_index=True)  # Changed from TextField
```

**CustomUser** (users/models.py line 32):
```python
mobile_primary = models.CharField(..., db_index=True)
```

**Create and run migration**:
```bash
python manage.py makemigrations
python manage.py migrate
```

**Testing**: Verify migrations apply successfully. Test search/filter operations.

---

### 3.2 Fix DiagnosisList TextField to CharField
**File**: `patients/models.py:2268`
**Effort**: 20 minutes + migration
**Risk**: MEDIUM (data migration needed if existing data exceeds 255 chars)

**Step 1**: Check existing data:
```python
python manage.py shell
>>> from patients.models import DiagnosisList
>>> max_length = DiagnosisList.objects.annotate(title_len=Length('title')).aggregate(Max('title_len'))
>>> print(max_length)
```

**Step 2**: If max_length < 255, safe to change:
```python
title = models.CharField(max_length=255, null=False, blank=False, db_index=True)
```

**Step 3**: Create migration:
```bash
python manage.py makemigrations
python manage.py migrate
```

**Testing**: Verify all diagnosis titles still display correctly.

---

### 3.3 Add Unique Constraints
**File**: `patients/models.py`
**Effort**: 30 minutes + migration
**Risk**: MEDIUM (may fail if duplicate data exists)

**Step 1**: Check for duplicates:
```python
python manage.py shell
>>> from patients.models import DiagnosisList, IndicationsForGMA, Help
>>> DiagnosisList.objects.values('abr').annotate(count=Count('id')).filter(count__gt=1)
>>> IndicationsForGMA.objects.values('title').annotate(count=Count('id')).filter(count__gt=1)
>>> Help.objects.values('title').annotate(count=Count('id')).filter(count__gt=1)
```

**Step 2**: If duplicates exist, clean them up first manually.

**Step 3**: Add constraints:
```python
# DiagnosisList
abr = models.CharField(max_length=6, null=False, blank=False, unique=True)

# IndicationsForGMA
title = models.CharField(max_length=75, null=False, blank=False, unique=True)

# Help
title = models.CharField(max_length=200, db_index=True, unique=True)
```

**Testing**: Try to create duplicates, verify constraints prevent them.

---

### 3.4 Fix Subscription.update_status Race Condition
**File**: `users/models.py:748-780`
**Effort**: 30 minutes
**Risk**: MEDIUM

**Fix**:
```python
def update_status(self):
    """Update subscription status based on current state"""
    # Calculate what the status should be
    new_status = None
    if self.is_expired:  # This uses @property which is safe
        new_status = 'expired'
    elif self.is_expiring_soon:
        new_status = 'expiring_soon'
    elif self.status == 'trial' and not self.is_trial_expired:
        new_status = 'trial'
    elif self.status in ['active', 'trial']:
        new_status = 'active'

    if new_status and self.status != new_status:
        with transaction.atomic():
            subscription = Subscription.objects.select_for_update().get(pk=self.pk)
            subscription.status = new_status
            subscription.save(update_fields=['status', 'updated_at'])

            # Clear cache AFTER successful transaction
            self._clear_cache()  # Move cache clear here

    return new_status
```

**Testing**: Concurrent subscription status updates (requires load testing).

---

### 3.5 Add Missing select_related on User Activity Logs
**File**: `users/views.py`
**Effort**: 15 minutes
**Risk**: LOW

**Lines 421, 818, 837**:
```python
# Before:
activities = UserActivityLog.objects.filter(user=user).order_by('-login_timestamp')

# After:
activities = UserActivityLog.objects.filter(user=user).select_related('user').order_by('-login_timestamp')
```

**Testing**: View activity logs with debug toolbar. Verify query count reduced.

---

### 3.6 Optimize Username List Queries
**File**: `users/views.py`
**Effort**: 20 minutes
**Risk**: LOW

**Lines 657, 682, 690, 695, 829, 838, 848**:
```python
# Before:
username_list = CustomUser.objects.all()

# After (if only username is needed):
username_list = CustomUser.objects.values_list('username', flat=True)

# OR (if id and username both needed):
username_list = CustomUser.objects.only('id', 'username')
```

**Testing**: Verify dropdowns/lists still work correctly.

---

### 3.7 Add Video MIME Type Validation
**File**: `video/forms.py:68-92`
**Effort**: 45 minutes
**Risk**: LOW

**Add to clean_video_file method**:
```python
def clean_video_file(self):
    video_file = self.cleaned_data.get("video_file")

    if video_file:
        # Existing validations...

        # Add MIME type validation
        import magic
        mime = magic.Magic(mime=True)
        file_mime = mime.from_buffer(video_file.read(1024))
        video_file.seek(0)  # Reset file pointer

        allowed_mimes = [
            'video/mp4',
            'video/quicktime',  # .mov
            'video/x-msvideo',  # .avi
            'video/x-matroska',  # .mkv
            'video/webm',
        ]

        if file_mime not in allowed_mimes:
            raise ValidationError(
                _(f'Invalid video file type: {file_mime}. Allowed types: MP4, MOV, AVI, MKV, WEBM.')
            )

    return video_file
```

**Install dependency**:
```bash
pip install python-magic-bin  # Windows
# OR
pip install python-magic  # Linux/Mac
```

**Testing**: Try uploading renamed non-video files. Verify rejection.

---

### 3.8 Add Date Cross-Validation in problemlist Forms
**File**: `problemlist/forms.py`
**Effort**: 30 minutes
**Risk**: LOW

**Add to form class**:
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

**Testing**: Submit form with invalid date combinations. Verify validation errors.

---

### 3.9 Move Filename Sanitization Earlier
**File**: `patients/forms.py:739-745`
**Effort**: 30 minutes
**Risk**: MEDIUM

**Current** (line 739):
```python
def clean_file(self):
    file = self.cleaned_data.get("file")
    if file:
        file.name = sanitize_filename(file.name)
    return file
```

**Issue**: File already temporarily stored before sanitization.

**Fix**: Move to model's save method or use FileField upload_to callable:
```python
# In patients/models.py Attachment model:
from ndas.custom_codes.custom_methods import sanitize_filename

def attachment_upload_path(instance, filename):
    """Generate upload path with sanitized filename"""
    sanitized = sanitize_filename(filename)
    return f"attachments/{instance.patient.id}/{timezone.now().year}/{timezone.now().month}/{sanitized}"

class Attachment(TimeStampedModel, UserTrackingMixin):
    file = models.FileField(
        upload_to=attachment_upload_path,  # Use callable
        # ... rest of field config
    )
```

**Testing**: Upload files with dangerous names (e.g., "../../etc/passwd"). Verify sanitization.

---

### 3.10 Improve Birth Weight Validation
**File**: `patients/models.py:346-350`
**Effort**: 1 hour
**Risk**: LOW

**Replace existing validation** with comprehensive table:
```python
def clean(self):
    super().clean()

    if self.birth_weight and self.pog_wks:
        # Comprehensive gestational age vs weight validation
        validation_ranges = {
            # (min_weeks, max_weeks): (min_weight_g, max_weight_g, warning_threshold)
            (20, 23): (300, 700, 100),
            (24, 27): (400, 1200, 150),
            (28, 31): (800, 2000, 200),
            (32, 36): (1200, 3000, 300),
            (37, 44): (2000, 5000, 500),
        }

        for (min_wk, max_wk), (min_wt, max_wt, warn_margin) in validation_ranges.items():
            if min_wk <= self.pog_wks <= max_wk:
                if self.birth_weight < min_wt - warn_margin:
                    raise ValidationError({
                        'birth_weight': _(f'Birth weight extremely low for {self.pog_wks} weeks gestational age.')
                    })
                elif self.birth_weight > max_wt + warn_margin:
                    raise ValidationError({
                        'birth_weight': _(f'Birth weight extremely high for {self.pog_wks} weeks gestational age.')
                    })
                break
```

**Testing**: Try various POG/weight combinations. Verify appropriate validation.

---

## PHASE 4: LOW PRIORITY & OPTIMIZATIONS (Estimated: 8-12 hours)

**Priority**: Nice to have, improve maintainability
**Testing**: Standard testing

### 4.1 Add App Namespaces to URLs
**Files**: `patients/urls.py`, `users/urls.py`, `problemlist/urls.py`
**Effort**: 30 minutes
**Risk**: MEDIUM (all URL references need updating)

**Add to each file**:
```python
# patients/urls.py
app_name = 'patients'

# users/urls.py
app_name = 'users'

# problemlist/urls.py
app_name = 'problemlist'
```

**Update URL references** throughout codebase:
```python
# Before:
{% url 'patient-view' pk=patient.id %}

# After:
{% url 'patients:patient-view' pk=patient.id %}
```

**Testing**: Extensive testing of all URL reversals needed.

---

### 4.2 Add Meta Classes to Models
**File**: `patients/models.py`
**Effort**: 1 hour
**Risk**: LOW

**IndicationsForGMA** (line 2250-2263):
```python
class Meta:
    verbose_name = _("Indication for GMA")
    verbose_name_plural = _("Indications for GMA")
    ordering = ['level', 'title']
    indexes = [
        models.Index(fields=['title']),
        models.Index(fields=['level']),
    ]
```

**DiagnosisList** (line 2266-2275):
```python
class Meta:
    verbose_name = _("Diagnosis")
    verbose_name_plural = _("Diagnoses")
    ordering = ['title']
    indexes = [
        models.Index(fields=['title']),
    ]
```

**Testing**: Check admin interface, verify ordering and display names.

---

### 4.3 Add Template Fragment Caching
**Files**: Multiple template files
**Effort**: 3-4 hours
**Risk**: LOW-MEDIUM

**Example for patients/manager.html**:
```django
{% load cache %}

{# Cache filter controls - rarely change #}
{% cache 3600 patient_filters %}
<div class="filter-controls">
    <!-- Lines 77-159 -->
</div>
{% endcache %}

{# Cache pagination - changes per page but can cache per page number #}
{% cache 600 patient_pagination page_number %}
<div class="pagination">
    <!-- Lines 394-471 -->
</div>
{% endcache %}
```

**Apply to**:
- patients/manager.html
- assessment/manager.html
- video/manager.html

**Testing**: Verify pages still update correctly. Clear cache to test changes appear.

---

### 4.4 Move Heavy Computations from Templates to Views
**Files**: Templates and views
**Effort**: 2-3 hours
**Risk**: MEDIUM

**Example for patient_view.html**:

**In patients/views.py**:
```python
def patient_view(request, pk):
    selected_patient = get_object_or_404(Patient, id=pk)

    # Calculate in view instead of template
    context = {
        'patient': selected_patient,
        'current_age': selected_patient.getCurrentAge,  # Call once here
        'corrected_age': selected_patient.getCorrectedAge,
        'pog': selected_patient.getPOG,
        'corrected_ga': selected_patient.getCorrectedGestationalAge,
        'rc_items': [item for item in selected_patient.getRC if item.get('display')],  # Filter here
        # ... rest of context
    }

    return render(request, "patients/view.html", context)
```

**In template**, replace method calls with variables:
```django
{# Before: {{patient.getCurrentAge}} #}
{# After: #}
{{current_age}}
```

**Testing**: Verify all patient views display correctly.

---

### 4.5 Optimize Delete Modals
**Files**: assessment/manager.html, video/manager.html, etc.
**Effort**: 2 hours
**Risk**: MEDIUM

**Replace loop-generated modals** with single modal + JavaScript:

**In template** (remove from loop):
```django
{# Outside loop - single modal #}
<div id="deleteModal" class="modal fade" tabindex="-1">
    <div class="modal-content">
        <div class="modal-header">
            <h5 id="deleteModalTitle">Confirm Delete</h5>
        </div>
        <div class="modal-body">
            <p>Are you sure you want to delete <strong id="deleteItemName"></strong>?</p>
        </div>
        <div class="modal-footer">
            <form id="deleteForm" method="post">
                {% csrf_token %}
                <button type="submit" class="btn btn-danger">Delete</button>
                <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button>
            </form>
        </div>
    </div>
</div>
```

**Add JavaScript**:
```javascript
function openDeleteModal(itemId, itemName, deleteUrl) {
    document.getElementById('deleteItemName').textContent = itemName;
    document.getElementById('deleteForm').action = deleteUrl;
    $('#deleteModal').modal('show');
}
```

**In loop**, replace modal include with button:
```django
<button onclick="openDeleteModal('{{Assessment.id}}', '{{Assessment}}', '{% url 'assessment-delete' Assessment.id %}')"
        class="btn btn-sm btn-danger">Delete</button>
```

**Testing**: Click delete on various items. Verify modal populates correctly.

---

### 4.6 Add Static File Optimization
**Files**: Base templates
**Effort**: 1-2 hours
**Risk**: LOW

**In templates/src/base.html** (or similar):
```django
{# Preload critical CSS #}
<link rel="preload" href="{% static 'adminlte/dist/css/adminlte.min.css' %}" as="style">
<link rel="preload" href="{% static 'plugins/fontawesome-free/css/all.min.css' %}" as="style">

{# Load CSS #}
<link rel="stylesheet" href="{% static 'adminlte/dist/css/adminlte.min.css' %}">
<link rel="stylesheet" href="{% static 'plugins/fontawesome-free/css/all.min.css' %}">

{# Defer non-critical JavaScript #}
<script src="{% static 'plugins/jquery/jquery.min.js' %}"></script>
<script defer src="{% static 'plugins/bootstrap/js/bootstrap.bundle.min.js' %}"></script>
<script defer src="{% static 'adminlte/dist/js/adminlte.min.js' %}"></script>
```

**Testing**: Check page load times with browser dev tools. Verify JavaScript still works with defer.

---

### 4.7 Add Prefetch to Template Queries
**Files**: Views where templates use .all() or .count()
**Effort**: 1.5 hours
**Risk**: LOW

**Example for patient_view.html**:

**In patients/views.py**:
```python
def patient_view(request, pk):
    selected_patient = get_object_or_404(
        Patient.objects.prefetch_related(
            'indecation_for_gma',  # For line 240-242 in template
            'problem_list',  # For problemlist section
            'diagnosis',
        ),
        id=pk
    )

    context = {
        'patient': selected_patient,
        'problem_count': selected_patient.problem_list.count(),  # Calculate here
        # ...
    }
```

**In template**, use prefetched data:
```django
{# Line 240-242 - now uses prefetched data #}
{% for gmamodel in patient.indecation_for_gma.all %}
```

**Testing**: Use debug toolbar to verify no additional queries in template.

---

### 4.8 Change Temporary Redirects to Permanent
**File**: `patients/urls.py:19-27`
**Effort**: 5 minutes
**Risk**: LOW (only if deprecation period over)

```python
# After 6-month deprecation period:
path("manager/patient/new/", RedirectView.as_view(pattern_name='patient-manager-new', permanent=True)),
```

**Testing**: Verify browser caches 301 redirects (check network tab).

---

### 4.9 Add Cache Headers to File Downloads
**File**: `reports/views.py`
**Effort**: 30 minutes
**Risk**: LOW

**Example for download_report**:
```python
from django.utils.http import http_date
import time

def download_report(request, report_id, format_type):
    # ... existing code ...

    with open(file_path, 'rb') as file_handle:
        response = FileResponse(file_handle.read(), content_type=content_type)

    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Add caching headers
    response['Cache-Control'] = 'private, max-age=3600'  # Cache for 1 hour
    response['Last-Modified'] = http_date(time.time())

    # Optional: Add ETag
    import hashlib
    etag = hashlib.md5(f"{report_id}-{format_type}".encode()).hexdigest()
    response['ETag'] = f'"{etag}"'

    return response
```

**Testing**: Download same report twice. Verify caching behavior in network tab.

---

### 4.10 Add HTTP Method Restrictions
**Files**: All view files
**Effort**: 2 hours
**Risk**: LOW

**Pattern**:
```python
from django.views.decorators.http import require_http_methods, require_GET, require_POST

@require_GET
def patient_view(request, pk):
    # ...

@require_http_methods(["GET", "POST"])
def patient_add(request):
    # ...

@require_POST
def patient_delete(request, pk):
    # ...
```

**Apply to all views** based on their purpose.

**Testing**: Try sending wrong HTTP methods. Verify 405 Method Not Allowed responses.

---

## TESTING STRATEGY

### After Each Phase:

1. **Unit Tests**:
```bash
python manage.py test
```

2. **Integration Tests**: Manual testing of affected features

3. **Performance Testing**:
```bash
pip install django-debug-toolbar
```
Add to development settings and monitor query counts

4. **Security Testing**: Test XSS, file upload, rate limiting

5. **Load Testing** (optional):
```bash
pip install locust
```

### Full Regression Testing

After all phases complete, run full test suite:
```bash
# All tests
python manage.py test

# Specific apps
python manage.py test patients
python manage.py test users
python manage.py test video
python manage.py test reports

# With coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
```

---

## DEPLOYMENT NOTES

1. **Backup Database** before applying any migrations
2. **Test on staging environment** before production
3. **Migrations**: Some fixes require database migrations - plan downtime or use zero-downtime migration strategies
4. **Dependencies**: Some fixes require new packages (PIL, python-magic, bleach) - update requirements.txt
5. **Cache Clearing**: After template caching fixes, may need to clear cache in production

---

## ROLLBACK PLAN

For each phase:
1. **Git Branch**: Create branch before starting phase
2. **Database Backup**: Backup before migrations
3. **Migration Rollback**: Keep track of migration numbers for rollback
4. **Code Rollback**: Use git revert/reset if issues occur

---

## PRIORITY RECOMMENDATIONS

**Week 1**: Phase 1 (Critical Fixes)
**Week 2**: Phase 2 Part 1 (select_related fixes)
**Week 3**: Phase 2 Part 2 (Security and validation)
**Week 4**: Phase 3 (Database optimizations)
**Week 5-6**: Phase 4 (Nice-to-have improvements)

**Estimated Total Timeline**: 6 weeks for all phases with testing
**Minimum Required**: Phase 1 only (Critical fixes) - 1 week
