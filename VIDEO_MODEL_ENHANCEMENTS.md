# Video Model Enhancements - Django Best Practices Implementation

## Overview

The Video model has been completely rewritten following Django best practices with comprehensive enhancements for video uploading, compression, validation, and performance optimization.

## Key Improvements

### 1. Model Architecture

#### Base Classes
- **TimeStampedModel**: Provides automatic `created_at` and `updated_at` fields
- **UserTrackingMixin**: Provides `added_by` and `last_edit_by` fields with proper relationships
- Follows Django's abstract base class pattern for reusable functionality

#### Field Enhancements
- **title**: Replaces `caption` with better validation and length (200 chars)
- **original_video**: Stores the original uploaded file with proper validation
- **compressed_video**: Stores compressed version for web playback
- **thumbnail**: Auto-generated video thumbnail for better UX
- **duration**: Auto-extracted video duration metadata
- **file_size**: Tracks original and compressed file sizes
- **resolution**: Stores video resolution (e.g., 1920x1080)
- **frame_rate**: Video frame rate information
- **bitrate**: Video bitrate in kbps

#### Processing & Compression
- **processing_status**: Tracks video processing state
- **target_quality**: User-selectable compression quality
- **processing_started_at/completed_at**: Processing timeline tracking
- **processing_error**: Error message storage for failed processing

#### Content & Access Control
- **tags**: Comma-separated tags for categorization
- **is_sensitive**: Flag for sensitive medical content
- **access_level**: Granular access control (restricted/team/department/public)
- **is_public**: Simple public access flag

### 2. Validation Enhancements

#### File Validation (`validate_video_file`)
- **Format validation**: Supports MP4, MOV, AVI, MKV, WebM
- **Size validation**: Configurable max size (default: 2GB)
- **Empty file protection**: Minimum 1KB size requirement
- **Comprehensive error messages**: User-friendly validation feedback

#### Recording Date Validation
- **Future date prevention**: Cannot record in future
- **Historical limit**: Max 10 years in the past
- **Cross-field validation**: Ensures logical date relationships

#### Content Validation
- **Title validation**: Alphanumeric, spaces, hyphens, underscores, dots only
- **Tag validation**: Max 20 tags, 50 chars each, special character filtering
- **Description length**: Max 2000 characters with proper truncation

### 3. File Organization

#### Structured Upload Paths
```
videos/
├── YYYY/
│   └── MM/
│       └── patient_name/
│           ├── original_video.mp4
│           ├── compressed/
│           │   └── compressed_video.mp4
│           └── thumbnails/
│               └── thumbnail.jpg
```

#### Naming Convention
- **Original**: `{patient}_{title}_original_{timestamp}.{ext}`
- **Compressed**: `{patient}_{title}_compressed_{timestamp}.mp4`
- **Thumbnail**: `{patient}_{title}_thumb_{timestamp}.jpg`

### 4. Performance Optimizations

#### Database Indexes
- **Composite indexes**: `(patient, -uploaded_on)` for patient video listings
- **Status indexes**: `processing_status` for background job queries
- **User indexes**: `(uploaded_by, -uploaded_on)` for user dashboards
- **Access indexes**: `(is_public, access_level)` for permission queries

#### Database Constraints
- **Check constraints**: Ensure positive file sizes
- **Foreign key optimization**: Proper CASCADE/SET_NULL behaviors
- **Index optimization**: Strategic index placement for common queries

#### Model Methods Optimization
- **Property caching**: Computed properties for expensive calculations
- **Lazy loading**: Metadata extraction only when needed
- **Bulk operations**: Support for bulk video processing

### 5. Enhanced Features

#### Video Processing Pipeline
- **Background processing**: Async video compression (ready for Celery)
- **Quality options**: Multiple compression levels (original/high/medium/low/mobile)
- **Thumbnail generation**: Auto-generated video previews
- **Metadata extraction**: Duration, resolution, frame rate, bitrate

#### User Experience
- **Progress tracking**: Processing status and timeline
- **Compression ratio**: Shows space savings from compression
- **Playback optimization**: Serves compressed version when available
- **Error handling**: Graceful failure recovery

#### Backward Compatibility
- **Legacy property mapping**: `caption` → `title`, `video` → `original_video`
- **Method aliases**: Maintains existing property names
- **Form compatibility**: Legacy form support during transition

### 6. Security Enhancements

#### File Security
- **MIME type validation**: Prevents malicious file uploads
- **Extension whitelist**: Only allowed video formats
- **Size limits**: Prevents resource exhaustion
- **Path traversal prevention**: Secure file naming

#### Access Control
- **User-based permissions**: Owner/team/department access levels
- **Sensitive content flagging**: Special handling for medical content
- **Audit trail**: Complete tracking of who uploaded/modified what

#### Content Security Policy
- **Video streaming**: Proper CSP headers for video playback
- **CORS handling**: Secure cross-origin video access
- **HTTPS enforcement**: Secure video transmission

### 7. Form Enhancements

#### VideoForm Features
- **Enhanced validation**: Client and server-side validation
- **File upload progress**: JavaScript progress tracking
- **Quality selection**: User-selectable compression options
- **Tag management**: Intuitive tag input with validation
- **Access control**: Easy permission setting

#### UX Improvements
- **Help text**: Comprehensive field explanations
- **Error messages**: User-friendly validation feedback
- **File format hints**: Clear format and size guidance
- **Preview functionality**: Thumbnail previews before upload

### 8. Configuration Settings

#### Django Settings
```python
# Video Upload and Processing Settings
VIDEO_MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
VIDEO_ALLOWED_FORMATS = ['mp4', 'mov', 'avi', 'mkv', 'webm']
VIDEO_COMPRESSION_ENABLED = True
VIDEO_THUMBNAIL_GENERATION = True
VIDEO_DEFAULT_QUALITY = 'medium'

# File Upload Security
DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100MB
```

## Migration Requirements

### Database Migration
1. **Create migration**: `python manage.py makemigrations patients`
2. **Review migration**: Check field additions and constraints
3. **Apply migration**: `python manage.py migrate`
4. **Data migration**: Custom migration for existing video records

### File System Updates
1. **Create directories**: New folder structure for organized storage
2. **Move existing files**: Migrate current videos to new structure
3. **Update permissions**: Ensure proper file system permissions

### Dependencies
1. **Optional**: `ffmpeg-python` for video metadata extraction
2. **Optional**: `Pillow` for thumbnail generation
3. **Recommended**: `celery` for background processing

## Usage Examples

### Creating a Video Record
```python
from patients.models import Video, Patient

patient = Patient.objects.get(id=1)
video = Video.objects.create(
    patient=patient,
    title="Assessment Video - Week 1",
    original_video=video_file,
    recorded_on=timezone.now(),
    description="Initial assessment video",
    tags="assessment, week1, movement",
    target_quality="medium",
    access_level="team"
)
```

### Querying Videos
```python
# Get all videos for a patient
patient_videos = Video.objects.filter(patient=patient).order_by('-uploaded_on')

# Get videos needing processing
pending_videos = Video.objects.filter(processing_status='pending')

# Get public videos
public_videos = Video.objects.filter(is_public=True)
```

### Using Properties
```python
video = Video.objects.get(id=1)
print(f"File size: {video.file_size_mb} MB")
print(f"Duration: {video.duration_display}")
print(f"Age at recording: {video.age_on_recording}")
print(f"Compression saved: {video.compression_ratio}%")
```

## Future Enhancements

### Planned Features
1. **AI Analysis**: Integration with video analysis services
2. **Streaming**: HLS/DASH streaming for large videos
3. **Cloud Storage**: S3/Azure blob storage integration
4. **Video Annotations**: Time-based annotations and markers
5. **Collaborative Features**: Shared viewing and commenting

### Technical Improvements
1. **CDN Integration**: Content delivery network support
2. **Progressive Upload**: Resumable upload functionality
3. **Real-time Processing**: Live processing status updates
4. **Multi-quality Streaming**: Adaptive bitrate streaming

## Best Practices Applied

1. **Django Model Design**: Proper use of abstract base classes, foreign keys, and constraints
2. **Validation**: Comprehensive validation at model, form, and database levels
3. **Security**: File upload security, access control, and audit trails
4. **Performance**: Strategic indexing, query optimization, and caching
5. **Maintainability**: Clear code structure, documentation, and error handling
6. **Scalability**: Designed for high volume video handling and processing
7. **User Experience**: Intuitive forms, progress tracking, and error feedback

This enhanced Video model provides a robust, scalable, and secure foundation for medical video management in the NDAS system.
