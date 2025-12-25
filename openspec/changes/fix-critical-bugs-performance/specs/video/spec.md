# Video Management - Query Optimization and Validation

## MODIFIED Requirements

### Requirement: Video Filtering Performance
Video filtering operations MUST use database subqueries instead of loading IDs into memory.

#### Scenario: New videos filtered efficiently
- **WHEN** filtering videos not yet used in assessments
- **THEN** Exists() subquery is used in database
- **AND** NOT loading all used video IDs into Python memory
- **AND** query performance scales with database size

#### Scenario: Large video library filters fast
- **WHEN** video library contains 10,000+ videos
- **THEN** filter query completes in under 200ms
- **AND** memory usage remains constant regardless of assessed video count

## ADDED Requirements

### Requirement: Video MIME Type Validation
Video file uploads MUST validate actual file content type, not just file extension.

#### Scenario: Valid video file accepted
- **WHEN** uploading MP4 video file
- **THEN** MIME type is verified as video/mp4
- **AND** file extension matches content type
- **AND** upload succeeds

#### Scenario: Renamed malicious file rejected
- **WHEN** attempting to upload executable renamed to .mp4
- **THEN** MIME type validation detects mismatch
- **AND** upload is rejected with validation error
- **AND** file is not stored

#### Scenario: Supported video formats validated
- **WHEN** uploading video file
- **THEN** MIME type must be one of: video/mp4, video/quicktime, video/x-msvideo, video/x-matroska, video/webm
- **AND** unsupported formats are rejected

### Requirement: Video Manager Query Optimization
Video manager views MUST use select_related() for related objects to prevent N+1 queries.

#### Scenario: Video list with patient data loads efficiently
- **WHEN** displaying video manager page
- **THEN** patient and user data is fetched with JOINs
- **AND** queries remain under 10 for 50 videos

#### Scenario: Video assessment status pre-computed
- **WHEN** checking if video is used in assessment
- **THEN** annotation with Exists() subquery is used
- **AND** status is available without additional queries

## Technical Notes

### Video Filter Optimization

**Before (loads IDs into memory):**
```python
used_video_ids = GMAssessment.objects.values_list('video_file_id', flat=True)
queryset = queryset.exclude(id__in=used_video_ids)
```

**After (database subquery):**
```python
from django.db.models import Exists, OuterRef

queryset = queryset.annotate(
    is_assessed=Exists(
        GMAssessment.objects.filter(video_file_id=OuterRef('pk'))
    )
).filter(is_assessed=False)
```

### MIME Type Validation

**Implementation:**
```python
def clean_video_file(self):
    video_file = self.cleaned_data.get("video_file")

    if video_file:
        # Existing size and extension checks...

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
                f'Invalid video file type: {file_mime}. Allowed types: MP4, MOV, AVI, MKV, WEBM.'
            )

    return video_file
```

**Dependency:** `pip install python-magic-bin` (Windows) or `python-magic` (Linux/Mac)

### Affected Files

- `video/views.py` - lines 259-268, 360-364 (filter optimization)
- `video/forms.py` - lines 68-92 (MIME validation)

### Performance Targets

- **Video list (50 items):** < 10 queries
- **Video filter operation:** < 200ms for 10,000+ videos
- **MIME validation:** < 50ms per file
