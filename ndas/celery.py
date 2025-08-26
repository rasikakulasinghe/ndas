"""
Celery configuration for NDAS video processing pipeline.
"""
import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ndas.settings')

app = Celery('ndas')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Celery configuration
app.conf.update(
    # Redis as broker and result backend
    broker_url=f"redis://{getattr(settings, 'REDIS_HOST', 'localhost')}:{getattr(settings, 'REDIS_PORT', 6379)}/0",
    result_backend=f"redis://{getattr(settings, 'REDIS_HOST', 'localhost')}:{getattr(settings, 'REDIS_PORT', 6379)}/0",
    
    # Task serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'video.tasks.process_video_task': {'queue': 'video_processing'},
        'video.tasks.extract_video_metadata': {'queue': 'video_processing'},
        'video.tasks.generate_thumbnail': {'queue': 'video_processing'},
        'video.tasks.compress_video': {'queue': 'video_processing'},
        'video.tasks.batch_process_videos': {'queue': 'video_processing'},
    },
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    
    # Task timeout and retry configuration
    task_soft_time_limit=1800,  # 30 minutes soft limit
    task_time_limit=3600,       # 1 hour hard limit
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    result_backend_transport_options={
        'master_name': 'mymaster',
        'retry_on_timeout': True,
    },
    
    # Memory and resource limits
    worker_max_memory_per_child=512000,  # 512MB per worker
    worker_concurrency=2,  # Number of concurrent workers
    
    # Beat scheduler (for periodic tasks)
    beat_scheduler='django_celery_beat.schedulers:DatabaseScheduler',
    
    # Task compression
    task_compression='gzip',
    result_compression='gzip',
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Custom queue definitions
    task_default_queue='default',
    task_queues={
        'default': {
            'exchange': 'default',
            'exchange_type': 'direct',
            'routing_key': 'default',
        },
        'video_processing': {
            'exchange': 'video_processing',
            'exchange_type': 'direct',
            'routing_key': 'video_processing',
        },
    },
)

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery configuration."""
    print(f'Request: {self.request!r}')
    return {'status': 'success', 'message': 'Celery is working!'}
