# NDAS Video Processing Pipeline

## Overview

The NDAS (Neonatal Development Assessment System) video processing pipeline is a distributed, scalable solution for processing medical videos using Celery task queue and Redis message broker. This system provides:

- **Automated video processing** with configurable quality settings
- **Distributed task management** using Celery workers
- **Real-time progress tracking** and monitoring
- **Error handling** with automatic retry mechanisms
- **Batch processing** capabilities
- **Resource management** with memory and CPU limits
- **API endpoints** for integration and monitoring

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Django Web    │    │   Celery        │    │   Redis         │
│   Application   │◄──►│   Workers       │◄──►│   Message       │
│                 │    │                 │    │   Broker        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   File Storage  │    │   FFmpeg        │    │   Result        │
│   (Media Files) │    │   Processing    │    │   Backend       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Features

### Video Processing Capabilities

1. **Metadata Extraction**
   - Video duration, resolution, codec information
   - Bitrate and frame rate analysis
   - File format validation

2. **Video Compression**
   - Multiple quality presets (original, high, medium, low, mobile)
   - Configurable bitrate and resolution settings
   - H.264/MP4 output with web optimization

3. **Thumbnail Generation**
   - Automatic thumbnail creation at specified timestamp
   - Customizable thumbnail size and format

4. **Progress Tracking**
   - Real-time processing progress updates
   - Task status monitoring
   - Error reporting and retry mechanisms

### Quality Presets

| Preset   | Resolution | Video Bitrate | Audio Bitrate | Use Case          |
|----------|------------|---------------|---------------|-------------------|
| Original | Unchanged  | Unchanged     | 128k          | Archive/Reference |
| High     | 1920x1080  | 4000k         | 128k          | High Quality      |
| Medium   | 1280x720   | 2500k         | 128k          | Standard Web      |
| Low      | 854x480    | 1000k         | 96k           | Low Bandwidth     |
| Mobile   | 640x360    | 500k          | 64k           | Mobile Devices    |

## Installation

### Prerequisites

1. **Python 3.11+**
2. **Redis Server**
3. **FFmpeg** (for video processing)
4. **Django 4.2+**

### System Dependencies

#### Windows
```powershell
# Install Redis (using Chocolatey)
choco install redis-64

# Install FFmpeg
choco install ffmpeg

# Or download from official websites:
# Redis: https://redis.io/docs/getting-started/installation/install-redis-on-windows/
# FFmpeg: https://ffmpeg.org/download.html
```

#### Linux (Ubuntu/Debian)
```bash
# Install Redis
sudo apt update
sudo apt install redis-server

# Install FFmpeg
sudo apt install ffmpeg

# Install system dependencies
sudo apt install python3-dev libpq-dev libjpeg-dev libpng-dev
```

#### macOS
```bash
# Install using Homebrew
brew install redis ffmpeg
```

### Python Environment Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd ndas
```

2. **Create virtual environment**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

3. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
Create a `.env` file in the project root:
```env
# Django settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Redis configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Celery configuration
CELERY_WORKER_CONCURRENCY=2
CELERY_TASK_ALWAYS_EAGER=False

# Video processing
FFMPEG_BINARY=ffmpeg
FFPROBE_BINARY=ffprobe
MAX_VIDEO_SIZE=2147483648  # 2GB
```

5. **Run Django migrations**
```bash
python manage.py migrate
```

6. **Create superuser (optional)**
```bash
python manage.py createsuperuser
```

## Usage

### Starting Services

#### Option 1: Using Management Scripts

**Windows (PowerShell):**
```powershell
# Start all services
.\celery_manager.ps1 start all

# Start individual services
.\celery_manager.ps1 start worker
.\celery_manager.ps1 start beat
.\celery_manager.ps1 start flower

# Check status
.\celery_manager.ps1 status
```

**Linux/macOS (Bash):**
```bash
# Make script executable
chmod +x celery_manager.sh

# Start all services
./celery_manager.sh start all

# Start individual services
./celery_manager.sh start worker
./celery_manager.sh start beat
./celery_manager.sh start flower

# Check status
./celery_manager.sh status
```

#### Option 2: Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f celery_worker

# Stop services
docker-compose down
```

#### Option 3: Manual Commands

1. **Start Redis** (if not using Docker)
```bash
redis-server
```

2. **Start Celery Worker**
```bash
celery -A ndas worker --loglevel=info --concurrency=2 --queues=video_processing,default
```

3. **Start Celery Beat** (for periodic tasks)
```bash
celery -A ndas beat --loglevel=info --scheduler=django_celery_beat.schedulers:DatabaseScheduler
```

4. **Start Flower** (monitoring interface)
```bash
celery -A ndas flower --port=5555
```

5. **Start Django Development Server**
```bash
python manage.py runserver
```

### Processing Videos

#### Using Django Management Commands

1. **Process a specific video**
```bash
python manage.py process_videos --video-id 123 --wait
```

2. **Process all pending videos**
```bash
python manage.py process_videos --batch --max-videos 10 --wait
```

3. **Retry failed videos**
```bash
python manage.py process_videos --batch --status failed --max-videos 5
```

4. **Monitor processing**
```bash
python manage.py monitor_video_processing --stats
python manage.py monitor_video_processing --processing-videos --watch
```

#### Using API Endpoints

**Get video processing status:**
```bash
curl -X GET http://localhost:8000/video/api/status/123/
```

**Start video processing:**
```bash
curl -X POST http://localhost:8000/video/api/start/123/ \
  -H "Content-Type: application/json" \
  -d '{"quality": "medium"}'
```

**Get processing queue status:**
```bash
curl -X GET http://localhost:8000/video/api/queue/status/
```

**Start batch processing:**
```bash
curl -X POST http://localhost:8000/video/api/batch/process/ \
  -H "Content-Type: application/json" \
  -d '{"status": "pending", "quality": "medium", "max_videos": 10}'
```

### Monitoring

#### Flower Web Interface
Access the Flower monitoring interface at: http://localhost:5555

Features:
- Real-time task monitoring
- Worker status and statistics
- Task history and results
- Performance metrics

#### Django Admin Interface
Access video processing status through the Django admin at: http://localhost:8000/admin/

#### API Monitoring
Use the statistics endpoint for detailed metrics:
```bash
curl -X GET http://localhost:8000/video/api/statistics/?days=30
```

## Configuration

### Celery Settings (ndas/settings.py)

```python
# Celery Broker and Result Backend
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Task Configuration
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']

# Worker Configuration
CELERY_WORKER_CONCURRENCY = 2
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 512000  # 512MB

# Task Time Limits
CELERY_TASK_SOFT_TIME_LIMIT = 1800  # 30 minutes
CELERY_TASK_TIME_LIMIT = 3600       # 1 hour

# Task Routing
CELERY_TASK_ROUTES = {
    'video.tasks.*': {'queue': 'video_processing'},
}
```

### Video Processing Settings

```python
# File Size Limits
MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
MAX_VIDEO_DURATION = 3600  # 1 hour

# Supported Formats
SUPPORTED_VIDEO_INPUTS = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
VIDEO_OUTPUT_FORMAT = 'mp4'
VIDEO_OUTPUT_CODEC = 'libx264'

# Quality Presets
VIDEO_QUALITY_PRESETS = {
    'high': {
        'width': 1920,
        'height': 1080,
        'video_bitrate': '4000k',
        'audio_bitrate': '128k',
        'crf': 20,
    },
    # ... other presets
}
```

## Troubleshooting

### Common Issues

1. **Redis Connection Error**
   ```
   Error: Redis connection failed
   ```
   **Solution:** Ensure Redis server is running
   ```bash
   redis-server
   # Or check if Redis is running: redis-cli ping
   ```

2. **FFmpeg Not Found**
   ```
   Error: FFmpeg/FFprobe not found in system PATH
   ```
   **Solution:** Install FFmpeg and ensure it's in your system PATH
   ```bash
   # Check installation
   ffmpeg -version
   ffprobe -version
   ```

3. **Celery Worker Not Starting**
   ```
   Error: Worker failed to start
   ```
   **Solution:** Check virtual environment and dependencies
   ```bash
   # Activate virtual environment
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   
   # Install dependencies
   pip install -r requirements.txt
   ```

4. **Video Processing Fails**
   ```
   Error: Video processing failed
   ```
   **Solution:** Check video file format and size
   - Ensure video format is supported
   - Check file size limits
   - Verify FFmpeg can process the file: `ffprobe path/to/video.mp4`

5. **Out of Memory Errors**
   ```
   Error: Worker killed due to memory limit
   ```
   **Solution:** Reduce worker concurrency or increase memory limits
   ```python
   # In settings.py
   CELERY_WORKER_CONCURRENCY = 1  # Reduce from 2
   CELERY_WORKER_MAX_MEMORY_PER_CHILD = 1024000  # Increase to 1GB
   ```

### Debugging

1. **Enable Debug Logging**
   ```python
   # In settings.py
   LOGGING = {
       'version': 1,
       'handlers': {
           'file': {
               'level': 'DEBUG',
               'class': 'logging.FileHandler',
               'filename': 'debug.log',
           },
       },
       'loggers': {
           'video.tasks': {
               'handlers': ['file'],
               'level': 'DEBUG',
           },
       },
   }
   ```

2. **Monitor Celery Logs**
   ```bash
   # View worker logs
   ./celery_manager.sh logs worker
   
   # View beat logs
   ./celery_manager.sh logs beat
   ```

3. **Check Task Status**
   ```bash
   # Using management command
   python manage.py monitor_video_processing --all-active
   
   # Using Celery inspect
   celery -A ndas inspect active
   celery -A ndas inspect stats
   ```

### Performance Optimization

1. **Adjust Worker Concurrency**
   - For CPU-intensive tasks: Set concurrency to number of CPU cores
   - For memory-limited systems: Reduce concurrency

2. **Configure Redis Memory**
   ```bash
   # In redis.conf
   maxmemory 512mb
   maxmemory-policy allkeys-lru
   ```

3. **Optimize Video Processing**
   - Use appropriate quality presets
   - Consider file size vs. quality trade-offs
   - Monitor processing times and adjust settings

## API Reference

### Video Processing Endpoints

#### GET /video/api/status/{video_id}/
Get current processing status for a video.

**Response:**
```json
{
  "video_id": 123,
  "title": "Patient Video",
  "processing_status": "processing",
  "progress_percentage": 75,
  "processing_started_at": "2025-08-26T10:00:00Z",
  "processing_time_seconds": 120.5,
  "celery_task": {
    "status": "PROGRESS",
    "info": {"current": 75, "total": 100}
  }
}
```

#### POST /video/api/start/{video_id}/
Start processing a video.

**Request:**
```json
{
  "quality": "medium"
}
```

**Response:**
```json
{
  "success": true,
  "task_id": "abc123-def456-789",
  "message": "Video processing started"
}
```

#### GET /video/api/queue/status/
Get processing queue status and statistics.

**Response:**
```json
{
  "queue_stats": {
    "pending": 5,
    "processing": 2,
    "failed": 1,
    "completed_today": 15
  },
  "performance": {
    "average_processing_time": 180.5,
    "average_processing_time_formatted": "3m 0s"
  }
}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Add your license information here]

## Support

For issues and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review Celery and Django documentation
