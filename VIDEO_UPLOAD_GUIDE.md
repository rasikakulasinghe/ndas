# Enhanced Video Upload System for NDAS

This document describes the enhanced video upload functionality implemented for the NDAS (Neonatal Development Assessment System).

## Overview

The enhanced video upload system provides:

1. **Modern AdminLTE UI**: Clean, responsive interface with progress indicators
2. **File Validation**: Comprehensive validation for video files
3. **Smart Compression**: Automatic compression for files larger than 25MB
4. **Progress Tracking**: Real-time upload progress and processing status
5. **Error Handling**: Robust error handling with user-friendly messages

## Features

### 🎯 Upload Interface

- **Patient Information Panel**: Display patient details during upload
- **Enhanced Form**: Modern form with validation and tooltips
- **File Size Detection**: Automatic detection of large files requiring compression
- **Advanced Options**: Collapsible panel for compression quality and access settings

### 📁 File Handling

- **Supported Formats**: MP4, MOV, AVI, MKV, WebM
- **Size Limits**: Up to 2GB per file
- **Compression Threshold**: Files > 25MB are automatically compressed
- **Quality Options**: Low, Medium, High compression settings

### 📊 Progress Tracking

- **Upload Progress**: Real-time progress bar during file upload
- **Processing Status**: Separate page for compression progress
- **Auto-refresh**: Automatic status updates during processing
- **Error Recovery**: Graceful handling of processing failures

### 🔒 Security & Validation

- **File Type Validation**: Server-side validation of video formats
- **Size Validation**: Configurable file size limits
- **Access Control**: Role-based access to uploaded videos
- **Sensitive Content**: Option to mark videos containing sensitive medical content

## Usage

### For End Users

1. **Navigate to Patient**: Go to the patient record
2. **Upload Video**: Click "Add Video" button
3. **Fill Form**: 
   - Enter descriptive title
   - Select video file
   - Set recording date/time
   - Add description and tags (optional)
4. **Configure Settings**: Expand "Advanced Options" if needed
5. **Upload**: Click "Upload Video" button
6. **Monitor Progress**: Watch upload progress and processing status

### File Size Handling

- **Small Files (< 25MB)**: Direct upload, immediate availability
- **Large Files (≥ 25MB)**: Upload + compression, redirected to processing page
- **Very Large Files (> 2GB)**: Rejected with error message

### Processing Status

After uploading large files, users are redirected to a processing page showing:

- **Queued**: File uploaded, waiting for processing
- **Processing**: Video being compressed (with estimated time)
- **Completed**: Processing finished, video ready
- **Failed**: Processing error (original file still available)

## Technical Implementation

### Backend Components

1. **Enhanced View Function** (`video_add`):
   - Proper Django form handling
   - File validation using custom validators
   - Size-based processing decisions
   - JSON response for AJAX requests

2. **Processing Handler** (`handle_video_upload`):
   - Form data extraction and validation
   - File size analysis
   - Video record creation
   - Compression queue management

3. **Compression Function** (`compress_video_sync`):
   - FFmpeg-based video compression
   - Quality settings management
   - Error handling and logging
   - Temporary file cleanup

4. **Progress View** (`video_processing_progress`):
   - Processing status display
   - Auto-refresh functionality
   - Error state handling

### Frontend Components

1. **AdminLTE Template** (`add.html`):
   - Responsive card-based layout
   - Progress indicators
   - File validation feedback
   - Success/error messaging

2. **JavaScript Enhancement**:
   - File size detection
   - Upload progress tracking
   - AJAX form submission
   - Automatic redirects

3. **Processing Page** (`conversion_progress.html`):
   - Status-specific displays
   - Auto-refresh for active processing
   - Action buttons based on status

### Database Schema

Enhanced `Video` model includes:

- **Processing Fields**: `processing_status`, `processing_started_at`, `processing_completed_at`
- **Quality Settings**: `target_quality`, `compressed_video`, `compressed_file_size`
- **Metadata**: `file_size`, `format`, `resolution`, `frame_rate`, `bitrate`
- **Security**: `is_sensitive`, `access_level`

## Configuration

### Settings

Add to `settings.py`:

```python
# Video upload settings
VIDEO_MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
VIDEO_COMPRESSION_THRESHOLD = 25 * 1024 * 1024  # 25MB
VIDEO_QUALITY_SETTINGS = {
    'low': {'crf': 28, 'preset': 'fast'},
    'medium': {'crf': 23, 'preset': 'medium'},
    'high': {'crf': 18, 'preset': 'slow'}
}
```

### FFmpeg Requirement

For video compression functionality:

```bash
# Install FFmpeg (Windows)
# Download from https://ffmpeg.org/download.html

# Install FFmpeg (Ubuntu/Debian)
sudo apt update
sudo apt install ffmpeg

# Install FFmpeg (macOS)
brew install ffmpeg
```

### URL Configuration

Add to your `urls.py`:

```python
path("video/add/<str:pk>/", views.video_add, name='file-add'),
path("video/processing/<str:f_id>/", views.video_processing_progress, name='video-processing'),
path("video/view/<str:f_id>/", views.video_view, name='video-view'),
path("video/edit/<str:f_id>/", views.video_edit, name='video-edit'),
```

## Testing

Run the test script to verify functionality:

```bash
python test_video_upload.py
```

Tests include:
- Small file upload (< 25MB)
- Large file upload (> 25MB)
- Invalid file type rejection
- Processing page access

## Performance Considerations

### Production Deployment

1. **Async Processing**: Use Celery for video compression in production
2. **Storage**: Consider cloud storage (AWS S3, Google Cloud) for large files
3. **CDN**: Use CDN for video delivery
4. **Monitoring**: Implement processing queue monitoring

### Optimization

1. **Compression Settings**: Adjust quality settings based on use case
2. **Batch Processing**: Process multiple videos in batches during off-peak hours
3. **Storage Cleanup**: Implement cleanup for failed processing attempts
4. **Caching**: Cache video metadata for faster access

## Troubleshooting

### Common Issues

1. **FFmpeg Not Found**:
   - Install FFmpeg system-wide
   - Ensure it's in system PATH
   - Videos will skip compression but upload successfully

2. **Large Upload Timeouts**:
   - Increase `DATA_UPLOAD_MAX_MEMORY_SIZE` in settings
   - Configure web server timeout settings
   - Consider chunked upload for very large files

3. **Processing Failures**:
   - Check FFmpeg installation
   - Verify disk space for temporary files
   - Review error logs for specific issues

4. **Permission Errors**:
   - Ensure media directory is writable
   - Check file system permissions
   - Verify user access levels

### Logging

Enable debug logging in `settings.py`:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'video_upload.log',
        },
    },
    'loggers': {
        'patients.views': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

## Future Enhancements

Potential improvements for future versions:

1. **Real-time Progress**: WebSocket-based real-time progress updates
2. **Thumbnails**: Automatic thumbnail generation from videos
3. **Multiple Quality**: Generate multiple quality versions automatically
4. **Resumable Uploads**: Support for resuming interrupted uploads
5. **Batch Upload**: Upload multiple videos simultaneously
6. **Advanced Analytics**: Video analytics and viewing statistics

## Support

For questions or issues:

1. Check this documentation
2. Review Django logs
3. Test with the provided test script
4. Contact the development team

---

**Version**: 1.0  
**Last Updated**: {{ current_date }}  
**Authors**: NDAS Development Team
