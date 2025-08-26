"""
Management command to process videos using Celery.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from video.models import Video
from video.tasks import process_video_task, batch_process_videos
import time


class Command(BaseCommand):
    help = 'Process videos using the Celery video processing pipeline'

    def add_arguments(self, parser):
        parser.add_argument(
            '--video-id',
            type=int,
            help='Process a specific video by ID',
        )
        parser.add_argument(
            '--batch',
            action='store_true',
            help='Process all pending videos in batch',
        )
        parser.add_argument(
            '--status',
            choices=['pending', 'failed'],
            default='pending',
            help='Process videos with specific status (default: pending)',
        )
        parser.add_argument(
            '--quality',
            choices=['original', 'high', 'medium', 'low', 'mobile'],
            default='medium',
            help='Target quality for video processing (default: medium)',
        )
        parser.add_argument(
            '--max-videos',
            type=int,
            default=10,
            help='Maximum number of videos to process in batch mode (default: 10)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually processing',
        )
        parser.add_argument(
            '--wait',
            action='store_true',
            help='Wait for tasks to complete and show results',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting NDAS Video Processing Pipeline')
        )

        if options['video_id']:
            self.process_single_video(options)
        elif options['batch']:
            self.process_batch(options)
        else:
            self.stdout.write(
                self.style.ERROR('Please specify either --video-id or --batch')
            )
            return

    def process_single_video(self, options):
        """Process a single video by ID."""
        video_id = options['video_id']
        dry_run = options['dry_run']
        wait = options['wait']

        try:
            video = Video.objects.get(id=video_id)
        except Video.DoesNotExist:
            raise CommandError(f'Video with ID {video_id} does not exist')

        self.stdout.write(f'Video: {video.title} (ID: {video_id})')
        self.stdout.write(f'Patient: {video.patient.baby_name}')
        self.stdout.write(f'Status: {video.processing_status}')
        self.stdout.write(f'Original file: {video.original_video.name}')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN: Would process this video')
            )
            return

        # Start processing
        self.stdout.write('Starting video processing task...')
        task = process_video_task.delay(video_id)
        
        self.stdout.write(f'Task ID: {task.id}')
        
        if wait:
            self.wait_for_task(task, video_id)
        else:
            self.stdout.write(
                'Task started. Use --wait to monitor progress or check the admin interface.'
            )

    def process_batch(self, options):
        """Process multiple videos in batch."""
        status = options['status']
        max_videos = options['max_videos']
        quality = options['quality']
        dry_run = options['dry_run']
        wait = options['wait']

        # Get videos to process
        queryset = Video.objects.filter(processing_status=status)
        
        if status == 'failed':
            # For failed videos, also check retry count
            queryset = queryset.filter(retry_count__lt=3)

        videos = list(queryset[:max_videos])
        
        if not videos:
            self.stdout.write(
                self.style.WARNING(f'No videos found with status: {status}')
            )
            return

        self.stdout.write(f'Found {len(videos)} videos to process:')
        
        for video in videos:
            self.stdout.write(f'  - {video.title} (ID: {video.id}) - {video.patient.baby_name}')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN: Would process these videos')
            )
            return

        # Start batch processing
        video_ids = [video.id for video in videos]
        self.stdout.write(f'Starting batch processing with quality: {quality}')
        
        task = batch_process_videos.delay(video_ids, quality)
        self.stdout.write(f'Batch Task ID: {task.id}')
        
        if wait:
            self.wait_for_batch_task(task, video_ids)
        else:
            self.stdout.write(
                'Batch task started. Use --wait to monitor progress.'
            )

    def wait_for_task(self, task, video_id):
        """Wait for a single video processing task to complete."""
        self.stdout.write('Monitoring task progress...')
        
        while not task.ready():
            # Get task status
            if task.state == 'PROGRESS':
                meta = task.info or {}
                percentage = meta.get('current', 0)
                stage = meta.get('metadata', {}).get('stage', 'processing')
                self.stdout.write(f'Progress: {percentage}% - {stage}')
            
            time.sleep(5)  # Wait 5 seconds before checking again

        # Task completed
        if task.successful():
            result = task.result
            self.stdout.write(
                self.style.SUCCESS(f'Video processing completed successfully!')
            )
            self.stdout.write(f'Processing time: {result.get("processing_time", 0):.2f} seconds')
            
            # Show results
            if 'results' in result:
                results = result['results']
                if 'metadata' in results:
                    metadata = results['metadata']
                    self.stdout.write(f'Duration: {metadata.get("duration", 0):.1f} seconds')
                    self.stdout.write(f'Resolution: {metadata.get("width", 0)}x{metadata.get("height", 0)}')
                
                if 'compressed_url' in results:
                    self.stdout.write(f'Compressed video available: {results["compressed_url"]}')
                
                if 'thumbnail_url' in results:
                    self.stdout.write(f'Thumbnail available: {results["thumbnail_url"]}')
        else:
            self.stdout.write(
                self.style.ERROR(f'Video processing failed: {task.result}')
            )

    def wait_for_batch_task(self, task, video_ids):
        """Wait for batch processing task to complete."""
        self.stdout.write('Monitoring batch processing...')
        
        while not task.ready():
            if task.state == 'PROGRESS':
                meta = task.info or {}
                current = meta.get('current', 0)
                total = meta.get('total', len(video_ids))
                batch_progress = meta.get('batch_progress', 0)
                self.stdout.write(f'Batch Progress: {current}/{total} videos ({batch_progress}%)')
            
            time.sleep(10)  # Wait 10 seconds for batch processing

        # Batch completed
        if task.successful():
            result = task.result
            self.stdout.write(
                self.style.SUCCESS('Batch processing completed!')
            )
            self.stdout.write(f'Total videos: {result["total"]}')
            self.stdout.write(f'Successful: {result["successful"]}')
            self.stdout.write(f'Failed: {result["failed"]}')
            
            # Show individual results
            if result['failed'] > 0:
                self.stdout.write('\nFailed videos:')
                for video_id, video_result in result['results'].items():
                    if not video_result.get('success', True):
                        error = video_result.get('error', 'Unknown error')
                        self.stdout.write(f'  Video {video_id}: {error}')
        else:
            self.stdout.write(
                self.style.ERROR(f'Batch processing failed: {task.result}')
            )
