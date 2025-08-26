"""
Management command to monitor Celery video processing tasks.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from video.models import Video
from celery import current_app
import time


class Command(BaseCommand):
    help = 'Monitor video processing tasks and their status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--task-id',
            type=str,
            help='Monitor a specific task by ID',
        )
        parser.add_argument(
            '--all-active',
            action='store_true',
            help='Show all active video processing tasks',
        )
        parser.add_argument(
            '--processing-videos',
            action='store_true',
            help='Show all videos currently being processed',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show processing statistics',
        )
        parser.add_argument(
            '--watch',
            action='store_true',
            help='Continuously monitor (refresh every 10 seconds)',
        )

    def handle(self, *args, **options):
        if options['task_id']:
            self.monitor_task(options['task_id'], options['watch'])
        elif options['all_active']:
            self.show_active_tasks(options['watch'])
        elif options['processing_videos']:
            self.show_processing_videos(options['watch'])
        elif options['stats']:
            self.show_statistics()
        else:
            self.show_overview()

    def monitor_task(self, task_id, watch=False):
        """Monitor a specific task."""
        self.stdout.write(f'Monitoring task: {task_id}')
        
        while True:
            result = current_app.AsyncResult(task_id)
            
            self.stdout.write(f'Status: {result.status}')
            
            if result.status == 'PROGRESS':
                info = result.info or {}
                self.stdout.write(f'Progress: {info}')
            elif result.status == 'SUCCESS':
                self.stdout.write(f'Result: {result.result}')
                break
            elif result.status == 'FAILURE':
                self.stdout.write(f'Error: {result.info}')
                break
            
            if not watch:
                break
                
            time.sleep(10)

    def show_active_tasks(self, watch=False):
        """Show all active video processing tasks."""
        while True:
            self.stdout.write('\n' + '='*50)
            self.stdout.write('ACTIVE VIDEO PROCESSING TASKS')
            self.stdout.write('='*50)
            
            # Get active tasks from Celery
            inspect = current_app.control.inspect()
            active_tasks = inspect.active()
            
            if not active_tasks:
                self.stdout.write('No active tasks found')
            else:
                for worker, tasks in active_tasks.items():
                    self.stdout.write(f'\nWorker: {worker}')
                    
                    video_tasks = [
                        task for task in tasks 
                        if task['name'].startswith('video.tasks.')
                    ]
                    
                    if not video_tasks:
                        self.stdout.write('  No video processing tasks')
                    else:
                        for task in video_tasks:
                            self.stdout.write(f'  Task: {task["name"]}')
                            self.stdout.write(f'    ID: {task["id"]}')
                            self.stdout.write(f'    Args: {task["args"]}')
            
            if not watch:
                break
                
            time.sleep(10)

    def show_processing_videos(self, watch=False):
        """Show all videos currently being processed."""
        while True:
            self.stdout.write('\n' + '='*50)
            self.stdout.write('VIDEOS CURRENTLY PROCESSING')
            self.stdout.write('='*50)
            
            processing_videos = Video.objects.filter(
                processing_status='processing'
            ).select_related('patient')
            
            if not processing_videos:
                self.stdout.write('No videos currently being processed')
            else:
                for video in processing_videos:
                    self.stdout.write(f'\nVideo: {video.title}')
                    self.stdout.write(f'  Patient: {video.patient.baby_name}')
                    self.stdout.write(f'  Progress: {video.progress_percentage}%')
                    self.stdout.write(f'  Started: {video.processing_started_at}')
                    
                    if video.task_id:
                        task_status = video.get_task_status()
                        if task_status:
                            self.stdout.write(f'  Task Status: {task_status["status"]}')
                            if task_status['info']:
                                self.stdout.write(f'  Task Info: {task_status["info"]}')
            
            if not watch:
                break
                
            time.sleep(10)

    def show_statistics(self):
        """Show processing statistics."""
        self.stdout.write('VIDEO PROCESSING STATISTICS')
        self.stdout.write('='*40)
        
        # Count videos by status
        status_counts = {}
        for status, _ in Video.objects.model._meta.get_field('processing_status').choices:
            count = Video.objects.filter(processing_status=status).count()
            status_counts[status] = count
        
        for status, count in status_counts.items():
            self.stdout.write(f'{status.title()}: {count}')
        
        # Average processing time
        completed_videos = Video.objects.filter(
            processing_status='completed',
            processing_time_seconds__isnull=False
        )
        
        if completed_videos.exists():
            avg_time = completed_videos.aggregate(
                avg_time=models.Avg('processing_time_seconds')
            )['avg_time']
            self.stdout.write(f'\nAverage Processing Time: {avg_time:.1f} seconds')
        
        # Recent activity
        recent_videos = Video.objects.filter(
            processing_completed_at__gte=timezone.now() - timezone.timedelta(hours=24)
        ).count()
        self.stdout.write(f'Videos Processed (Last 24h): {recent_videos}')

    def show_overview(self):
        """Show general overview."""
        self.stdout.write('NDAS VIDEO PROCESSING OVERVIEW')
        self.stdout.write('='*40)
        
        total_videos = Video.objects.count()
        processing_videos = Video.objects.filter(processing_status='processing').count()
        pending_videos = Video.objects.filter(processing_status='pending').count()
        failed_videos = Video.objects.filter(processing_status='failed').count()
        
        self.stdout.write(f'Total Videos: {total_videos}')
        self.stdout.write(f'Currently Processing: {processing_videos}')
        self.stdout.write(f'Pending Processing: {pending_videos}')
        self.stdout.write(f'Failed Processing: {failed_videos}')
        
        if processing_videos > 0 or pending_videos > 0:
            self.stdout.write('\nUse --processing-videos to see details of videos being processed')
            self.stdout.write('Use --all-active to see active Celery tasks')
        
        self.stdout.write('\nUse --help to see all available options')
