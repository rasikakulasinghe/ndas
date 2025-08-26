"""
Celery tasks for video processing pipeline.
"""
import os
import time
import logging
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from celery import shared_task, current_task
from celery.exceptions import Retry
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
from django.utils import timezone

try:
    import ffmpeg
    import ffprobe
except ImportError:
    # Fallback if ffmpeg-python is not available
    ffmpeg = None
    ffprobe = None

# Configure logging
logger = logging.getLogger(__name__)

# Video processing configuration
VIDEO_PROCESSING_CONFIG = {
    'original': {
        'width': None,  # Keep original
        'height': None,  # Keep original
        'video_bitrate': None,  # Keep original
        'audio_bitrate': '128k',
    },
    'high': {
        'width': 1920,
        'height': 1080,
        'video_bitrate': '4000k',
        'audio_bitrate': '128k',
    },
    'medium': {
        'width': 1280,
        'height': 720,
        'video_bitrate': '2500k',
        'audio_bitrate': '128k',
    },
    'low': {
        'width': 854,
        'height': 480,
        'video_bitrate': '1000k',
        'audio_bitrate': '96k',
    },
    'mobile': {
        'width': 640,
        'height': 360,
        'video_bitrate': '500k',
        'audio_bitrate': '64k',
    },
}

SUPPORTED_INPUT_FORMATS = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v']
OUTPUT_FORMAT = 'mp4'
OUTPUT_CODEC = 'libx264'
AUDIO_CODEC = 'aac'

# Memory and CPU limits
MAX_MEMORY_MB = 1024  # 1GB
MAX_CPU_PERCENT = 80


def update_task_progress(video_id: int, percentage: int, metadata: Optional[Dict] = None):
    """Update task progress in the database."""
    try:
        from video.models import Video
        video = Video.objects.get(id=video_id)
        video.update_processing_progress(percentage, metadata)
        
        # Update Celery task state
        if current_task:
            current_task.update_state(
                state='PROGRESS',
                meta={'current': percentage, 'total': 100, 'metadata': metadata}
            )
    except Exception as e:
        logger.error(f"Failed to update progress for video {video_id}: {e}")


def extract_video_metadata(file_path: str) -> Dict[str, Any]:
    """Extract comprehensive video metadata using ffprobe."""
    if not ffprobe:
        logger.warning("ffprobe not available, using basic metadata extraction")
        return get_basic_metadata(file_path)
    
    try:
        # Use ffprobe to get detailed metadata
        probe = ffprobe.ffprobe(file_path)
        
        video_stream = None
        audio_stream = None
        
        # Find video and audio streams
        for stream in probe['streams']:
            if stream['codec_type'] == 'video' and not video_stream:
                video_stream = stream
            elif stream['codec_type'] == 'audio' and not audio_stream:
                audio_stream = stream
        
        metadata = {
            'format': probe['format']['format_name'],
            'duration': float(probe['format'].get('duration', 0)),
            'size': int(probe['format'].get('size', 0)),
            'bitrate': int(probe['format'].get('bit_rate', 0)),
        }
        
        if video_stream:
            metadata.update({
                'width': int(video_stream.get('width', 0)),
                'height': int(video_stream.get('height', 0)),
                'video_codec': video_stream.get('codec_name', ''),
                'video_bitrate': int(video_stream.get('bit_rate', 0)) if video_stream.get('bit_rate') else None,
                'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                'pixel_format': video_stream.get('pix_fmt', ''),
            })
        
        if audio_stream:
            metadata.update({
                'audio_codec': audio_stream.get('codec_name', ''),
                'audio_bitrate': int(audio_stream.get('bit_rate', 0)) if audio_stream.get('bit_rate') else None,
                'sample_rate': int(audio_stream.get('sample_rate', 0)),
                'channels': int(audio_stream.get('channels', 0)),
            })
        
        return metadata
        
    except Exception as e:
        logger.error(f"Failed to extract metadata with ffprobe: {e}")
        return get_basic_metadata(file_path)


def get_basic_metadata(file_path: str) -> Dict[str, Any]:
    """Get basic metadata without ffprobe."""
    try:
        stat = os.stat(file_path)
        return {
            'size': stat.st_size,
            'format': Path(file_path).suffix.lower().lstrip('.'),
            'duration': 0,  # Cannot determine without ffprobe
            'width': 0,
            'height': 0,
            'bitrate': 0,
        }
    except Exception as e:
        logger.error(f"Failed to get basic metadata: {e}")
        return {}


def validate_input_file(file_path: str) -> bool:
    """Validate input video file."""
    if not os.path.exists(file_path):
        raise ValueError(f"Input file does not exist: {file_path}")
    
    file_ext = Path(file_path).suffix.lower()
    if file_ext not in SUPPORTED_INPUT_FORMATS:
        raise ValueError(f"Unsupported input format: {file_ext}")
    
    file_size = os.path.getsize(file_path)
    max_size = getattr(settings, 'MAX_VIDEO_SIZE', 2 * 1024 * 1024 * 1024)  # 2GB default
    if file_size > max_size:
        raise ValueError(f"File too large: {file_size} bytes (max: {max_size} bytes)")
    
    return True


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def extract_video_metadata_task(self, video_id: int) -> Dict[str, Any]:
    """Extract video metadata as a separate task."""
    try:
        from video.models import Video
        video = Video.objects.get(id=video_id)
        
        update_task_progress(video_id, 10, {'stage': 'metadata_extraction'})
        
        # Get the file path
        file_path = video.original_video.path
        validate_input_file(file_path)
        
        # Extract metadata
        metadata = extract_video_metadata(file_path)
        
        # Update video model with metadata
        video.duration_seconds = metadata.get('duration', 0)
        video.original_resolution = f"{metadata.get('width', 0)}x{metadata.get('height', 0)}"
        video.original_codec = metadata.get('video_codec', '')
        video.original_bitrate = metadata.get('video_bitrate', 0)
        video.file_size = metadata.get('size', 0)
        
        # Store complete metadata
        current_metadata = video.processing_metadata or {}
        current_metadata['original_metadata'] = metadata
        video.processing_metadata = current_metadata
        
        video.save(update_fields=[
            'duration_seconds', 'original_resolution', 'original_codec',
            'original_bitrate', 'file_size', 'processing_metadata'
        ])
        
        update_task_progress(video_id, 20, {'stage': 'metadata_extraction_complete'})
        
        logger.info(f"Metadata extracted for video {video_id}: {metadata}")
        return metadata
        
    except Exception as e:
        logger.error(f"Metadata extraction failed for video {video_id}: {e}")
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def generate_thumbnail_task(self, video_id: int) -> str:
    """Generate video thumbnail as a separate task."""
    try:
        from video.models import Video
        video = Video.objects.get(id=video_id)
        
        update_task_progress(video_id, 30, {'stage': 'thumbnail_generation'})
        
        file_path = video.original_video.path
        
        if not ffmpeg:
            logger.warning("ffmpeg not available, skipping thumbnail generation")
            return ""
        
        # Create temporary file for thumbnail
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            thumbnail_path = tmp_file.name
        
        try:
            # Generate thumbnail at 1 second mark
            (
                ffmpeg
                .input(file_path, ss=1)
                .output(thumbnail_path, vframes=1, format='image2', vcodec='mjpeg')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True, check=True)
            )
            
            # Save thumbnail to model
            with open(thumbnail_path, 'rb') as thumb_file:
                thumbnail_name = f"thumb_{video.id}_{int(time.time())}.jpg"
                video.thumbnail.save(
                    thumbnail_name,
                    ContentFile(thumb_file.read()),
                    save=True
                )
            
            update_task_progress(video_id, 40, {'stage': 'thumbnail_complete'})
            
            logger.info(f"Thumbnail generated for video {video_id}")
            return video.thumbnail.url if video.thumbnail else ""
            
        finally:
            # Clean up temporary file
            if os.path.exists(thumbnail_path):
                os.unlink(thumbnail_path)
                
    except Exception as e:
        logger.error(f"Thumbnail generation failed for video {video_id}: {e}")
        # Don't fail the entire task for thumbnail issues
        return ""


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def compress_video_task(self, video_id: int, quality: str = 'medium') -> str:
    """Compress video with specified quality settings."""
    try:
        from video.models import Video
        video = Video.objects.get(id=video_id)
        
        update_task_progress(video_id, 50, {'stage': 'compression_start'})
        
        if not ffmpeg:
            raise ValueError("ffmpeg not available for video compression")
        
        input_path = video.original_video.path
        config = VIDEO_PROCESSING_CONFIG.get(quality, VIDEO_PROCESSING_CONFIG['medium'])
        
        # Create temporary output file
        with tempfile.NamedTemporaryFile(suffix=f'.{OUTPUT_FORMAT}', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            # Build ffmpeg command
            input_stream = ffmpeg.input(input_path)
            
            # Video processing arguments
            video_args = {
                'vcodec': OUTPUT_CODEC,
                'preset': 'medium',  # Balance between speed and compression
                'crf': 23,  # Constant Rate Factor for quality
            }
            
            # Add resolution if specified
            if config['width'] and config['height']:
                video_args['s'] = f"{config['width']}x{config['height']}"
            
            # Add bitrate if specified
            if config['video_bitrate']:
                video_args['b:v'] = config['video_bitrate']
            
            # Audio processing arguments
            audio_args = {
                'acodec': AUDIO_CODEC,
                'b:a': config['audio_bitrate'],
            }
            
            # Progress tracking
            def progress_callback(percentage):
                # Map compression progress to 50-90% of total progress
                total_progress = 50 + int(percentage * 0.4)
                update_task_progress(video_id, total_progress, {
                    'stage': 'compression',
                    'compression_progress': percentage
                })
            
            # Run ffmpeg with progress tracking
            start_time = time.time()
            
            (
                ffmpeg
                .output(input_stream, output_path, **video_args, **audio_args)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True, check=True)
            )
            
            processing_time = time.time() - start_time
            
            # Save compressed video to model
            with open(output_path, 'rb') as compressed_file:
                compressed_name = f"compressed_{video.id}_{int(time.time())}.{OUTPUT_FORMAT}"
                video.compressed_video.save(
                    compressed_name,
                    ContentFile(compressed_file.read()),
                    save=True
                )
            
            # Calculate compression metrics
            original_size = os.path.getsize(input_path)
            compressed_size = os.path.getsize(output_path)
            compression_ratio = compressed_size / original_size if original_size > 0 else 0
            
            # Update video with compression info
            video.compression_ratio = compression_ratio
            video.target_resolution = config.get('width') and config.get('height') and f"{config['width']}x{config['height']}" or video.original_resolution
            video.target_bitrate = config.get('video_bitrate') and int(config['video_bitrate'].rstrip('k')) or None
            
            # Update metadata
            current_metadata = video.processing_metadata or {}
            current_metadata['compression'] = {
                'quality': quality,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': compression_ratio,
                'processing_time': processing_time,
                'config_used': config,
            }
            video.processing_metadata = current_metadata
            
            video.save(update_fields=[
                'compression_ratio', 'target_resolution', 'target_bitrate', 'processing_metadata'
            ])
            
            update_task_progress(video_id, 90, {'stage': 'compression_complete'})
            
            logger.info(f"Video compression completed for video {video_id}. "
                       f"Compression ratio: {compression_ratio:.2f}, "
                       f"Processing time: {processing_time:.2f}s")
            
            return video.compressed_video.url if video.compressed_video else ""
            
        finally:
            # Clean up temporary file
            if os.path.exists(output_path):
                os.unlink(output_path)
                
    except Exception as e:
        logger.error(f"Video compression failed for video {video_id}: {e}")
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_video_task(self, video_id: int) -> Dict[str, Any]:
    """Main video processing pipeline task."""
    try:
        from video.models import Video
        video = Video.objects.get(id=video_id)
        
        logger.info(f"Starting video processing for video {video_id}")
        
        # Update video status
        video.processing_status = 'processing'
        video.save(update_fields=['processing_status'])
        
        start_time = time.time()
        results = {}
        
        # Step 1: Extract metadata
        try:
            metadata = extract_video_metadata_task.delay(video_id).get()
            results['metadata'] = metadata
        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")
            results['metadata_error'] = str(e)
        
        # Step 2: Generate thumbnail
        try:
            thumbnail_url = generate_thumbnail_task.delay(video_id).get()
            results['thumbnail_url'] = thumbnail_url
        except Exception as e:
            logger.error(f"Thumbnail generation failed: {e}")
            results['thumbnail_error'] = str(e)
        
        # Step 3: Compress video
        try:
            quality = video.target_quality or 'medium'
            compressed_url = compress_video_task.delay(video_id, quality).get()
            results['compressed_url'] = compressed_url
        except Exception as e:
            logger.error(f"Video compression failed: {e}")
            results['compression_error'] = str(e)
        
        # Calculate total processing time
        total_time = time.time() - start_time
        
        # Determine success
        success = 'metadata' in results and not any(k.endswith('_error') for k in results.keys())
        
        # Update video completion status
        video.set_processing_complete(
            success=success,
            error_message='; '.join([v for k, v in results.items() if k.endswith('_error')]) or None,
            processing_time=total_time
        )
        
        update_task_progress(video_id, 100, {'stage': 'complete', 'results': results})
        
        logger.info(f"Video processing completed for video {video_id}. "
                   f"Success: {success}, Total time: {total_time:.2f}s")
        
        return {
            'video_id': video_id,
            'success': success,
            'processing_time': total_time,
            'results': results,
        }
        
    except Exception as e:
        logger.error(f"Video processing pipeline failed for video {video_id}: {e}")
        
        # Mark as failed
        try:
            from video.models import Video
            video = Video.objects.get(id=video_id)
            video.set_processing_complete(success=False, error_message=str(e))
        except:
            pass
        
        raise


@shared_task(bind=True)
def batch_process_videos(self, video_ids: list, quality: str = 'medium') -> Dict[str, Any]:
    """Process multiple videos in batch."""
    logger.info(f"Starting batch processing for {len(video_ids)} videos")
    
    results = {
        'total': len(video_ids),
        'successful': 0,
        'failed': 0,
        'results': {},
    }
    
    for i, video_id in enumerate(video_ids):
        try:
            # Update batch progress
            batch_progress = int((i / len(video_ids)) * 100)
            self.update_state(
                state='PROGRESS',
                meta={'current': i, 'total': len(video_ids), 'batch_progress': batch_progress}
            )
            
            # Process individual video
            result = process_video_task.delay(video_id).get()
            
            if result['success']:
                results['successful'] += 1
            else:
                results['failed'] += 1
                
            results['results'][video_id] = result
            
        except Exception as e:
            logger.error(f"Batch processing failed for video {video_id}: {e}")
            results['failed'] += 1
            results['results'][video_id] = {
                'success': False,
                'error': str(e),
            }
    
    logger.info(f"Batch processing completed. "
               f"Successful: {results['successful']}, Failed: {results['failed']}")
    
    return results


@shared_task
def cleanup_temp_files():
    """Periodic task to clean up temporary files."""
    temp_dir = tempfile.gettempdir()
    cutoff_time = time.time() - (24 * 60 * 60)  # 24 hours ago
    
    cleaned_count = 0
    for file_path in Path(temp_dir).glob('*'):
        try:
            if file_path.stat().st_mtime < cutoff_time:
                if file_path.is_file():
                    file_path.unlink()
                    cleaned_count += 1
        except Exception:
            pass  # Ignore errors for files in use
    
    logger.info(f"Cleaned up {cleaned_count} temporary files")
    return cleaned_count


@shared_task
def health_check():
    """Health check task for monitoring."""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'worker_id': current_task.request.id if current_task else None,
    }
