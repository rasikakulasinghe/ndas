"""
Management command to migrate existing video data to new enhanced Video model structure
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from patients.models import Video
import os
import shutil
from pathlib import Path
from django.conf import settings


class Command(BaseCommand):
    help = 'Migrate existing video data to new enhanced Video model structure'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes',
        )
        parser.add_argument(
            '--reorganize-files',
            action='store_true',
            help='Also reorganize video files into new directory structure',
        )
        parser.add_argument(
            '--extract-metadata',
            action='store_true',
            help='Extract video metadata (requires ffmpeg-python)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        reorganize_files = options['reorganize_files']
        extract_metadata = options['extract_metadata']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )

        # Get all video records
        videos = Video.objects.all()
        
        if not videos.exists():
            self.stdout.write(
                self.style.SUCCESS('No videos found to migrate')
            )
            return

        self.stdout.write(f'Found {videos.count()} videos to process')

        migrated_count = 0
        error_count = 0

        with transaction.atomic():
            for video in videos:
                try:
                    changes_made = self.migrate_video_record(video, dry_run)
                    
                    if reorganize_files and not dry_run:
                        self.reorganize_video_file(video)
                    
                    if extract_metadata and not dry_run:
                        self.extract_video_metadata(video)
                    
                    if changes_made:
                        migrated_count += 1
                        
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'Error migrating video {video.pk}: {str(e)}'
                        )
                    )

        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(f'Migration Summary:')
        self.stdout.write(f'Total videos processed: {videos.count()}')
        self.stdout.write(f'Successfully migrated: {migrated_count}')
        self.stdout.write(f'Errors encountered: {error_count}')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    'This was a dry run - no actual changes were made'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Migration completed successfully!')
            )

    def migrate_video_record(self, video, dry_run=False):
        """Migrate a single video record to new structure"""
        changes_made = False
        
        # Map caption to title if title is empty
        if hasattr(video, 'caption') and video.caption and not video.title:
            self.stdout.write(f'Video {video.pk}: Mapping caption to title')
            if not dry_run:
                video.title = video.caption
                changes_made = True

        # Map video field to original_video if needed
        if hasattr(video, 'video') and video.video and not video.original_video:
            self.stdout.write(f'Video {video.pk}: Mapping video to original_video')
            if not dry_run:
                video.original_video = video.video
                changes_made = True

        # Set default processing status
        if not video.processing_status:
            self.stdout.write(f'Video {video.pk}: Setting default processing status')
            if not dry_run:
                video.processing_status = 'completed'
                changes_made = True

        # Set default access level
        if not video.access_level:
            self.stdout.write(f'Video {video.pk}: Setting default access level')
            if not dry_run:
                video.access_level = 'restricted'
                changes_made = True

        # Set default target quality
        if not video.target_quality:
            self.stdout.write(f'Video {video.pk}: Setting default target quality')
            if not dry_run:
                video.target_quality = 'medium'
                changes_made = True

        # Extract file size if not set
        if video.original_video and not video.file_size:
            try:
                file_size = video.original_video.size
                self.stdout.write(
                    f'Video {video.pk}: Setting file size ({file_size} bytes)'
                )
                if not dry_run:
                    video.file_size = file_size
                    changes_made = True
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(
                        f'Video {video.pk}: Could not determine file size: {e}'
                    )
                )

        # Extract format from filename
        if video.original_video and not video.format:
            try:
                ext = os.path.splitext(video.original_video.name)[1].lower().lstrip('.')
                if ext in ['mp4', 'mov', 'avi', 'mkv', 'webm']:
                    self.stdout.write(f'Video {video.pk}: Setting format ({ext})')
                    if not dry_run:
                        video.format = ext
                        changes_made = True
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(
                        f'Video {video.pk}: Could not determine format: {e}'
                    )
                )

        # Ensure recorded_on has timezone info if it's a date
        if video.recorded_on and hasattr(video.recorded_on, 'date'):
            # If it's a date field, convert to datetime
            if not hasattr(video.recorded_on, 'hour'):
                self.stdout.write(f'Video {video.pk}: Converting date to datetime')
                if not dry_run:
                    from datetime import datetime, time
                    video.recorded_on = timezone.make_aware(
                        datetime.combine(video.recorded_on, time(12, 0))
                    )
                    changes_made = True

        # Save changes
        if changes_made and not dry_run:
            video.save()

        return changes_made

    def reorganize_video_file(self, video):
        """Reorganize video file into new directory structure"""
        if not video.original_video:
            return

        old_path = video.original_video.path
        if not os.path.exists(old_path):
            self.stdout.write(
                self.style.WARNING(
                    f'Video {video.pk}: File not found at {old_path}'
                )
            )
            return

        # Generate new path
        patient_name = slugify(video.patient.baby_name) if video.patient else 'unknown'
        upload_date = video.uploaded_on or timezone.now()
        year = upload_date.strftime('%Y')
        month = upload_date.strftime('%m')

        new_dir = os.path.join(
            settings.MEDIA_ROOT, 'videos', year, month, patient_name
        )
        Path(new_dir).mkdir(parents=True, exist_ok=True)

        # Generate new filename
        timestamp = upload_date.strftime('%Y%m%d_%H%M%S')
        title = slugify(video.title) if video.title else 'video'
        ext = os.path.splitext(old_path)[1]
        new_filename = f"{patient_name}_{title}_original_{timestamp}{ext}"
        new_path = os.path.join(new_dir, new_filename)

        # Move file if paths are different
        if old_path != new_path:
            try:
                shutil.move(old_path, new_path)
                
                # Update database
                relative_path = os.path.relpath(new_path, settings.MEDIA_ROOT)
                video.original_video.name = relative_path
                video.save()
                
                self.stdout.write(
                    f'Video {video.pk}: Moved file to {relative_path}'
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Video {video.pk}: Failed to move file: {e}'
                    )
                )

    def extract_video_metadata(self, video):
        """Extract video metadata using ffmpeg (if available)"""
        if not video.original_video:
            return

        try:
            # Try to import ffmpeg
            import ffmpeg
            
            probe = ffmpeg.probe(video.original_video.path)
            video_stream = next(
                (s for s in probe['streams'] if s['codec_type'] == 'video'), 
                None
            )
            
            if video_stream:
                # Extract duration
                if 'duration' in video_stream and not video.duration:
                    duration_seconds = float(video_stream['duration'])
                    video.duration = timezone.timedelta(seconds=duration_seconds)
                
                # Extract resolution
                if 'width' in video_stream and 'height' in video_stream and not video.resolution:
                    video.resolution = f"{video_stream['width']}x{video_stream['height']}"
                
                # Extract frame rate
                if 'r_frame_rate' in video_stream and not video.frame_rate:
                    frame_rate_str = video_stream['r_frame_rate']
                    if '/' in frame_rate_str:
                        num, den = frame_rate_str.split('/')
                        video.frame_rate = float(num) / float(den)
                
                # Extract bitrate
                if 'bit_rate' in video_stream and not video.bitrate:
                    video.bitrate = int(video_stream['bit_rate']) // 1000  # Convert to kbps
                
                video.save()
                self.stdout.write(
                    f'Video {video.pk}: Extracted metadata'
                )
                
        except ImportError:
            self.stdout.write(
                self.style.WARNING(
                    'ffmpeg-python not installed. Skipping metadata extraction.'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(
                    f'Video {video.pk}: Failed to extract metadata: {e}'
                )
            )
