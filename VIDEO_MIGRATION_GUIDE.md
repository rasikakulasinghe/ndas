# Video Model Migration Guide

## Overview
This guide provides step-by-step instructions for migrating from the old Video model to the enhanced version.

## Pre-Migration Checklist

### 1. Backup Current Data
```bash
# Backup database
python manage.py dumpdata patients.Video > video_backup.json

# Backup media files
cp -r media/videos/ media/videos_backup/
```

### 2. Install Dependencies (Optional)
```bash
# For video processing (optional)
pip install ffmpeg-python

# For thumbnail generation (optional)
pip install Pillow

# For background processing (recommended)
pip install celery redis
```

## Migration Steps

### Step 1: Create and Apply Migration
```bash
# Generate migration
python manage.py makemigrations patients

# Review the migration file
# Edit if necessary to handle data migration

# Apply migration
python manage.py migrate patients
```

### Step 2: Data Migration Script
Create a custom management command to migrate existing data:

```python
# patients/management/commands/migrate_video_data.py
from django.core.management.base import BaseCommand
from patients.models import Video
from django.utils import timezone

class Command(BaseCommand):
    help = 'Migrate existing video data to new model structure'

    def handle(self, *args, **options):
        videos = Video.objects.all()
        
        for video in videos:
            # Map old fields to new fields
            if hasattr(video, 'caption') and not video.title:
                video.title = video.caption
            
            if hasattr(video, 'video') and not video.original_video:
                video.original_video = video.video
            
            # Set default values for new fields
            if not video.processing_status:
                video.processing_status = 'completed'
            
            if not video.access_level:
                video.access_level = 'restricted'
            
            if not video.target_quality:
                video.target_quality = 'medium'
            
            # Extract file size if not set
            if video.original_video and not video.file_size:
                try:
                    video.file_size = video.original_video.size
                except:
                    pass
            
            video.save()
            
        self.stdout.write(
            self.style.SUCCESS(f'Successfully migrated {videos.count()} videos')
        )
```

Run the migration:
```bash
python manage.py migrate_video_data
```

### Step 3: Update Templates

#### Old Template Pattern
```html
<!-- Old template usage -->
<video controls>
    <source src="{{file.video.url}}" type="video/mp4">
</video>
<h3>{{file.caption}}</h3>
<p>{{file.getAgeOnRecord}}</p>
```

#### New Template Pattern
```html
<!-- New template usage -->
<video controls>
    <source src="{{file.playback_url}}" type="video/mp4">
</video>
<h3>{{file.title}}</h3>
<p>{{file.age_on_recording}}</p>

<!-- Enhanced features -->
<div class="video-metadata">
    <span class="badge">{{file.duration_display}}</span>
    <span class="badge">{{file.file_size_mb}} MB</span>
    <span class="badge">{{file.resolution}}</span>
</div>

<div class="video-tags">
    {% for tag in file.get_tags_list %}
        <span class="tag">{{tag}}</span>
    {% endfor %}
</div>
```

### Step 4: Update Views

#### Old View Pattern
```python
# Old view usage
def video_view(request, video_id):
    video = Video.objects.get(id=video_id)
    form = VideoForm(instance=video)
    return render(request, 'video/view.html', {
        'file': video,
        'video_form': form
    })
```

#### New View Pattern
```python
# New view usage
def video_view(request, video_id):
    video = Video.objects.select_related('patient', 'uploaded_by').get(id=video_id)
    
    # Check access permissions
    if not video.can_be_accessed_by(request.user):
        return HttpResponseForbidden()
    
    form = VideoForm(instance=video)
    return render(request, 'video/view.html', {
        'file': video,
        'video_form': form,
        'processing_status': video.processing_status,
        'compression_ratio': video.compression_ratio
    })
```

### Step 5: Update Forms

#### Template Form Updates
```html
<!-- Old form -->
<input type="file" name="video" accept="video/*">
<input type="text" name="caption" placeholder="Video title">

<!-- New enhanced form -->
{{video_form.original_video}}
{{video_form.title}}
{{video_form.tags}}
{{video_form.target_quality}}
{{video_form.access_level}}
{{video_form.is_sensitive}}

<!-- Add JavaScript for enhanced upload -->
<div id="upload-progress" style="display:none;">
    <div class="progress">
        <div class="progress-bar" role="progressbar"></div>
    </div>
    <p id="upload-status">Uploading...</p>
</div>
```

### Step 6: File Organization Migration

Create a script to reorganize existing video files:

```python
# reorganize_video_files.py
import os
import shutil
from pathlib import Path
from django.conf import settings
from patients.models import Video

def reorganize_video_files():
    media_root = settings.MEDIA_ROOT
    
    for video in Video.objects.all():
        if not video.original_video:
            continue
            
        old_path = video.original_video.path
        if not os.path.exists(old_path):
            continue
        
        # Generate new path
        patient_name = slugify(video.patient.baby_name) if video.patient else 'unknown'
        year = video.uploaded_on.strftime('%Y')
        month = video.uploaded_on.strftime('%m')
        
        new_dir = os.path.join(media_root, 'videos', year, month, patient_name)
        Path(new_dir).mkdir(parents=True, exist_ok=True)
        
        # Move file
        filename = os.path.basename(old_path)
        new_path = os.path.join(new_dir, filename)
        
        if old_path != new_path:
            shutil.move(old_path, new_path)
            
            # Update database
            relative_path = os.path.relpath(new_path, media_root)
            video.original_video.name = relative_path
            video.save()

if __name__ == '__main__':
    reorganize_video_files()
```

## Post-Migration Tasks

### 1. Verify Data Integrity
```python
# Check migration success
from patients.models import Video

# Verify all videos have required fields
videos_without_title = Video.objects.filter(title__isnull=True)
videos_without_status = Video.objects.filter(processing_status__isnull=True)

print(f"Videos without title: {videos_without_title.count()}")
print(f"Videos without status: {videos_without_status.count()}")
```

### 2. Update Admin Interface
```python
# patients/admin.py
@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'patient', 'uploaded_by', 'processing_status', 
        'file_size_mb', 'duration_display', 'uploaded_on'
    ]
    list_filter = [
        'processing_status', 'access_level', 'is_sensitive', 
        'target_quality', 'uploaded_on'
    ]
    search_fields = ['title', 'description', 'tags', 'patient__baby_name']
    readonly_fields = [
        'file_size', 'compressed_file_size', 'duration', 
        'resolution', 'frame_rate', 'bitrate', 'processing_started_at', 
        'processing_completed_at'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'patient', 'description', 'tags')
        }),
        ('Video Files', {
            'fields': ('original_video', 'compressed_video', 'thumbnail')
        }),
        ('Recording Information', {
            'fields': ('recorded_on', 'duration', 'resolution', 'frame_rate')
        }),
        ('Processing', {
            'fields': ('processing_status', 'target_quality', 'file_size', 'compressed_file_size')
        }),
        ('Access Control', {
            'fields': ('access_level', 'is_sensitive', 'is_public')
        }),
    )
```

### 3. Set Up Background Processing
```python
# tasks.py (for Celery)
from celery import shared_task
from patients.models import Video

@shared_task
def process_video(video_id):
    try:
        video = Video.objects.get(id=video_id)
        video.extract_video_metadata()
        # Add compression logic here
        video.mark_processing_completed()
    except Exception as e:
        video.mark_processing_failed(str(e))
```

## Testing Migration

### 1. Unit Tests
```python
# tests/test_video_migration.py
from django.test import TestCase
from patients.models import Video, Patient

class VideoMigrationTest(TestCase):
    def test_legacy_properties(self):
        video = Video.objects.create(
            title="Test Video",
            patient=Patient.objects.create(baby_name="Test Baby")
        )
        
        # Test backward compatibility
        self.assertEqual(video.caption, video.title)
        self.assertEqual(video.video, video.original_video)
        self.assertEqual(video.getAgeOnRecord, video.age_on_recording)
```

### 2. Integration Tests
```python
def test_video_upload_flow(self):
    # Test complete upload and processing flow
    response = self.client.post('/video/add/', {
        'title': 'Test Video',
        'original_video': uploaded_file,
        'recorded_on': timezone.now(),
        'target_quality': 'medium'
    })
    
    self.assertEqual(response.status_code, 200)
    video = Video.objects.latest('id')
    self.assertEqual(video.processing_status, 'pending')
```

## Rollback Plan

If issues occur, you can rollback:

### 1. Database Rollback
```bash
# Rollback migration
python manage.py migrate patients [previous_migration_number]

# Restore data
python manage.py loaddata video_backup.json
```

### 2. File System Rollback
```bash
# Restore files
rm -rf media/videos/
mv media/videos_backup/ media/videos/
```

## Common Issues and Solutions

### Issue: Migration Fails
**Solution**: Check for data inconsistencies, fix manually, then re-run migration

### Issue: File Paths Broken
**Solution**: Run file reorganization script again, check file permissions

### Issue: Forms Not Working
**Solution**: Clear browser cache, check form field mappings

### Issue: Performance Issues
**Solution**: Check database indexes, optimize queries

## Monitoring Post-Migration

1. **Monitor video uploads**: Check for upload failures
2. **Check processing status**: Ensure videos process correctly
3. **Verify file access**: Test video playback functionality
4. **Monitor storage usage**: Track file size and compression effectiveness

This migration guide ensures a smooth transition to the enhanced Video model while maintaining data integrity and system functionality.
