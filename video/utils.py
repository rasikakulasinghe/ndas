"""
Video processing utilities and helper functions.
"""
import os
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


logger = logging.getLogger(__name__)


class VideoProcessingError(Exception):
    """Custom exception for video processing errors."""
    pass


class FFmpegWrapper:
    """Wrapper class for FFmpeg operations."""
    
    def __init__(self, check_dependencies=True):
        self.ffmpeg_binary = getattr(settings, 'FFMPEG_BINARY', 'ffmpeg')
        self.ffprobe_binary = getattr(settings, 'FFPROBE_BINARY', 'ffprobe')
        self._dependencies_checked = False
        if check_dependencies:
            self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if FFmpeg and FFprobe are available."""
        if self._dependencies_checked:
            return
            
        try:
            subprocess.run([self.ffmpeg_binary, '-version'], 
                         capture_output=True, check=True)
            subprocess.run([self.ffprobe_binary, '-version'], 
                         capture_output=True, check=True)
            self._dependencies_checked = True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"FFmpeg/FFprobe not available: {e}")
            raise VideoProcessingError("FFmpeg/FFprobe not found in system PATH")
    
    def get_video_info(self, file_path: str) -> Dict[str, Any]:
        """Get comprehensive video information using ffprobe."""
        self._check_dependencies()
        try:
            cmd = [
                self.ffprobe_binary,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            data = json.loads(result.stdout)
            
            # Extract relevant information
            format_info = data.get('format', {})
            streams = data.get('streams', [])
            
            video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
            audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
            
            info = {
                'format': format_info.get('format_name', ''),
                'duration': float(format_info.get('duration', 0)),
                'size': int(format_info.get('size', 0)),
                'bitrate': int(format_info.get('bit_rate', 0)),
            }
            
            if video_stream:
                info.update({
                    'width': int(video_stream.get('width', 0)),
                    'height': int(video_stream.get('height', 0)),
                    'video_codec': video_stream.get('codec_name', ''),
                    'video_bitrate': int(video_stream.get('bit_rate', 0)) if video_stream.get('bit_rate') else None,
                    'fps': self._parse_frame_rate(video_stream.get('r_frame_rate', '0/1')),
                    'pixel_format': video_stream.get('pix_fmt', ''),
                })
            
            if audio_stream:
                info.update({
                    'audio_codec': audio_stream.get('codec_name', ''),
                    'audio_bitrate': int(audio_stream.get('bit_rate', 0)) if audio_stream.get('bit_rate') else None,
                    'sample_rate': int(audio_stream.get('sample_rate', 0)),
                    'channels': int(audio_stream.get('channels', 0)),
                })
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            raise VideoProcessingError(f"Failed to analyze video: {e}")
    
    def _parse_frame_rate(self, fps_string: str) -> float:
        """Parse frame rate from FFprobe format (e.g., '30/1')."""
        try:
            if '/' in fps_string:
                num, den = fps_string.split('/')
                return float(num) / float(den) if float(den) != 0 else 0
            return float(fps_string)
        except:
            return 0.0
    
    def generate_thumbnail(self, input_path: str, output_path: str, 
                          timestamp: float = 1.0, size: str = "320x240") -> bool:
        """Generate a thumbnail from video at specified timestamp."""
        self._check_dependencies()
        try:
            cmd = [
                self.ffmpeg_binary,
                '-i', input_path,
                '-ss', str(timestamp),
                '-vframes', '1',
                '-f', 'image2',
                '-vcodec', 'mjpeg',
                '-s', size,
                '-y',  # Overwrite output file
                output_path
            ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Thumbnail generation failed: {e}")
            return False
    
    def compress_video(self, input_path: str, output_path: str, 
                      quality_preset: Dict[str, Any], 
                      progress_callback=None) -> bool:
        """Compress video with specified quality settings."""
        self._check_dependencies()
        try:
            cmd = [self.ffmpeg_binary, '-i', input_path]
            
            # Video codec and quality settings
            cmd.extend(['-c:v', 'libx264'])
            cmd.extend(['-preset', 'medium'])
            
            # CRF (Constant Rate Factor) for quality
            if quality_preset.get('crf'):
                cmd.extend(['-crf', str(quality_preset['crf'])])
            
            # Resolution
            if quality_preset.get('width') and quality_preset.get('height'):
                cmd.extend(['-s', f"{quality_preset['width']}x{quality_preset['height']}"])
            
            # Video bitrate
            if quality_preset.get('video_bitrate'):
                cmd.extend(['-b:v', quality_preset['video_bitrate']])
            
            # Audio codec and bitrate
            cmd.extend(['-c:a', 'aac'])
            if quality_preset.get('audio_bitrate'):
                cmd.extend(['-b:a', quality_preset['audio_bitrate']])
            
            # Output format
            cmd.extend(['-f', 'mp4'])
            cmd.extend(['-movflags', '+faststart'])  # Web optimization
            cmd.extend(['-y', output_path])  # Overwrite output
            
            # Execute compression
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.returncode != 0:
                logger.error(f"FFmpeg error: {process.stderr}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Video compression failed: {e}")
            return False


class VideoProcessingManager:
    """High-level manager for video processing operations."""
    
    def __init__(self, check_dependencies=True):
        self.ffmpeg = None
        self._check_dependencies = check_dependencies
        self.supported_formats = getattr(settings, 'SUPPORTED_VIDEO_INPUTS', 
                                       ['.mp4', '.mov', '.avi', '.mkv', '.webm'])
        self.quality_presets = getattr(settings, 'VIDEO_QUALITY_PRESETS', {})
    
    def _ensure_ffmpeg(self):
        """Lazy initialization of FFmpeg wrapper."""
        if self.ffmpeg is None:
            self.ffmpeg = FFmpegWrapper(check_dependencies=self._check_dependencies)
    
    def validate_video_file(self, file_path: str) -> Tuple[bool, str]:
        """Validate video file format and constraints."""
        try:
            # Check file exists
            if not os.path.exists(file_path):
                return False, "File does not exist"
            
            # Check file extension
            file_ext = Path(file_path).suffix.lower()
            if file_ext not in self.supported_formats:
                return False, f"Unsupported format: {file_ext}"
            
            # Check file size
            file_size = os.path.getsize(file_path)
            max_size = getattr(settings, 'MAX_VIDEO_SIZE', 2 * 1024 * 1024 * 1024)
            if file_size > max_size:
                return False, f"File too large: {file_size} bytes (max: {max_size})"
            
            # Try to get video info to validate it's a proper video file
            try:
                self._ensure_ffmpeg()
                info = self.ffmpeg.get_video_info(file_path)
                if info.get('duration', 0) <= 0:
                    return False, "Invalid video file: no duration detected"
            except VideoProcessingError as e:
                return False, f"Invalid video file: {e}"
            
            return True, "Valid video file"
            
        except Exception as e:
            return False, f"Validation error: {e}"
    
    def get_processing_estimate(self, file_path: str, quality: str = 'medium') -> Dict[str, Any]:
        """Estimate processing time and output size."""
        try:
            self._ensure_ffmpeg()
            info = self.ffmpeg.get_video_info(file_path)
            duration = info.get('duration', 0)
            original_size = info.get('size', 0)
            
            # Rough estimates based on quality preset
            quality_preset = self.quality_presets.get(quality, {})
            target_bitrate = quality_preset.get('video_bitrate', '2500k')
            
            # Parse bitrate
            if isinstance(target_bitrate, str) and target_bitrate.endswith('k'):
                target_bitrate_kbps = int(target_bitrate[:-1])
            else:
                target_bitrate_kbps = 2500  # Default
            
            # Estimate output size (very rough)
            estimated_size = int(duration * target_bitrate_kbps * 1000 / 8)  # bytes
            
            # Estimate processing time (roughly 0.5x to 2x real-time depending on settings)
            processing_multiplier = {
                'mobile': 0.3,
                'low': 0.5,
                'medium': 1.0,
                'high': 1.5,
                'original': 0.1,  # Just copying
            }.get(quality, 1.0)
            
            estimated_time = duration * processing_multiplier
            
            return {
                'duration': duration,
                'original_size': original_size,
                'estimated_output_size': estimated_size,
                'estimated_processing_time': estimated_time,
                'compression_ratio': estimated_size / original_size if original_size > 0 else 1.0,
                'quality_preset': quality_preset,
            }
            
        except Exception as e:
            logger.error(f"Failed to estimate processing: {e}")
            return {}
    
    def get_system_resources(self) -> Dict[str, Any]:
        """Get current system resource usage."""
        try:
            import psutil
            
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0],
            }
        except ImportError:
            logger.warning("psutil not available for system monitoring")
            return {}
    
    def cleanup_temp_files(self, older_than_hours: int = 24) -> int:
        """Clean up temporary files older than specified hours."""
        import tempfile
        import time
        
        temp_dir = Path(tempfile.gettempdir())
        cutoff_time = time.time() - (older_than_hours * 3600)
        cleaned_count = 0
        
        try:
            for file_path in temp_dir.glob('*'):
                try:
                    if file_path.stat().st_mtime < cutoff_time:
                        if file_path.is_file():
                            file_path.unlink()
                            cleaned_count += 1
                except Exception:
                    pass  # Ignore files in use or permission errors
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        return cleaned_count


# Utility functions for common operations
def get_video_processing_status_display() -> Dict[str, str]:
    """Get human-readable status descriptions."""
    return {
        'pending': 'Waiting for processing',
        'uploading': 'File upload in progress',
        'processing': 'Currently being processed',
        'completed': 'Processing completed successfully',
        'failed': 'Processing failed',
    }


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining_seconds = int(seconds % 60)
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def format_file_size(bytes_size: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def get_quality_preset_description(quality: str) -> str:
    """Get description for quality preset."""
    descriptions = {
        'original': 'Original quality (no compression)',
        'high': 'High quality (1080p, 4Mbps)',
        'medium': 'Medium quality (720p, 2.5Mbps)',
        'low': 'Low quality (480p, 1Mbps)',
        'mobile': 'Mobile quality (360p, 500kbps)',
    }
    return descriptions.get(quality, 'Unknown quality setting')


# Global instance for easy access - use lazy initialization
_video_manager = None

def get_video_manager():
    """Get the global video manager instance with lazy initialization."""
    global _video_manager
    if _video_manager is None:
        _video_manager = VideoProcessingManager(check_dependencies=False)
    return _video_manager

# For backward compatibility
video_manager = get_video_manager()
