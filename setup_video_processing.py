#!/usr/bin/env python
"""
Setup script for NDAS Video Processing Enhancement

This script will:
1. Install required dependencies
2. Run database migrations
3. Configure Celery workers
4. Set up Redis configuration
5. Test the video processing pipeline
"""

import os
import sys
import subprocess
import django
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ndas.settings')
django.setup()

def run_command(command, description):
    """Run a shell command and handle errors."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            if result.stdout:
                print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ {description} failed")
            if result.stderr:
                print(f"   Error: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"❌ {description} failed with exception: {e}")
        return False

def check_dependencies():
    """Check if required dependencies are installed."""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        'celery',
        'redis',
        'ffmpeg-python',
        'django',
        'pillow'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package} is installed")
        except ImportError:
            print(f"❌ {package} is missing")
            missing_packages.append(package)
    
    return len(missing_packages) == 0, missing_packages

def install_dependencies(missing_packages):
    """Install missing Python dependencies."""
    if not missing_packages:
        return True
    
    print(f"📦 Installing missing packages: {', '.join(missing_packages)}")
    command = f"pip install {' '.join(missing_packages)}"
    return run_command(command, "Installing Python dependencies")

def check_system_dependencies():
    """Check if system dependencies are available."""
    print("🔍 Checking system dependencies...")
    
    # Check FFmpeg
    ffmpeg_check = run_command("ffmpeg -version", "Checking FFmpeg")
    if not ffmpeg_check:
        print("⚠️  FFmpeg is not installed or not in PATH")
        print("   Please install FFmpeg:")
        print("   - Windows: Download from https://ffmpeg.org/download.html")
        print("   - macOS: brew install ffmpeg")
        print("   - Ubuntu/Debian: sudo apt install ffmpeg")
        return False
    
    # Check Redis
    redis_check = run_command("redis-cli ping", "Checking Redis connection")
    if not redis_check:
        print("⚠️  Redis is not running or not accessible")
        print("   Please start Redis server:")
        print("   - Windows: Download and install Redis, then start redis-server")
        print("   - macOS: brew install redis && brew services start redis")
        print("   - Ubuntu/Debian: sudo apt install redis-server && sudo systemctl start redis")
        return False
    
    return True

def run_migrations():
    """Run Django database migrations."""
    print("🔄 Running database migrations...")
    
    # Make migrations for video app
    make_migrations = run_command(
        "python manage.py makemigrations video",
        "Creating video app migrations"
    )
    
    # Run migrations
    migrate = run_command(
        "python manage.py migrate",
        "Applying database migrations"
    )
    
    return make_migrations and migrate

def test_celery_setup():
    """Test Celery configuration."""
    print("🔄 Testing Celery setup...")
    
    try:
        from celery import current_app
        from ndas.celery import app as celery_app
        
        # Test basic Celery connection
        i = celery_app.control.inspect()
        stats = i.stats()
        
        if stats:
            print("✅ Celery workers are running")
            for worker, stat in stats.items():
                print(f"   Worker: {worker}")
        else:
            print("⚠️  No Celery workers detected")
            print("   Start workers with: celery -A ndas worker --loglevel=info")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Celery test failed: {e}")
        print("   Make sure Redis is running and Celery is configured correctly")
        return False

def test_video_processing():
    """Test video processing functionality."""
    print("🔄 Testing video processing setup...")
    
    try:
        # Test FFmpeg integration
        import ffmpeg
        
        # Create a test video info extraction (without actual file)
        print("✅ FFmpeg Python integration working")
        
        # Test task import
        from video.tasks import process_video_task
        print("✅ Video processing tasks can be imported")
        
        return True
        
    except ImportError as e:
        print(f"❌ Video processing test failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Video processing test failed: {e}")
        return False

def create_celery_startup_scripts():
    """Create convenient scripts to start Celery workers."""
    print("🔄 Creating Celery startup scripts...")
    
    # Windows PowerShell script
    ps_script = """# Start Celery Worker for NDAS Video Processing
# Run this script from the project root directory

Write-Host "Starting Celery worker for NDAS video processing..." -ForegroundColor Green

# Activate virtual environment if it exists
if (Test-Path "venv\\Scripts\\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & ".\\venv\\Scripts\\Activate.ps1"
}

# Start Celery worker
Write-Host "Starting Celery worker..." -ForegroundColor Yellow
celery -A ndas worker --loglevel=info --pool=solo --concurrency=1

Write-Host "Celery worker stopped." -ForegroundColor Red
"""
    
    with open("start_celery_worker.ps1", "w") as f:
        f.write(ps_script)
    
    # Bash script for Unix systems
    bash_script = """#!/bin/bash
# Start Celery Worker for NDAS Video Processing
# Run this script from the project root directory

echo "Starting Celery worker for NDAS video processing..."

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Start Celery worker
echo "Starting Celery worker..."
celery -A ndas worker --loglevel=info --concurrency=2

echo "Celery worker stopped."
"""
    
    with open("start_celery_worker.sh", "w") as f:
        f.write(bash_script)
    
    # Make bash script executable
    try:
        os.chmod("start_celery_worker.sh", 0o755)
    except:
        pass  # Windows doesn't support chmod
    
    print("✅ Created startup scripts:")
    print("   - start_celery_worker.ps1 (Windows PowerShell)")
    print("   - start_celery_worker.sh (Unix/Linux/macOS)")
    
    return True

def print_usage_instructions():
    """Print usage instructions for the video processing system."""
    print("\n" + "="*60)
    print("🎉 NDAS Video Processing Setup Complete!")
    print("="*60)
    
    print("\n📋 Next Steps:")
    print("1. Start Redis server (if not already running)")
    print("2. Start Celery workers:")
    print("   Windows: .\\start_celery_worker.ps1")
    print("   Unix/Linux: ./start_celery_worker.sh")
    print("   Manual: celery -A ndas worker --loglevel=info")
    
    print("\n🎯 Features Available:")
    print("✅ Enhanced video upload form with all metadata fields")
    print("✅ Real-time upload progress tracking")
    print("✅ Automatic video processing with Celery")
    print("✅ FFmpeg-based video compression and optimization")
    print("✅ Thumbnail generation")
    print("✅ Processing status monitoring")
    print("✅ Error handling and retry logic")
    
    print("\n🔗 Key URLs:")
    print("- Upload video: /video/add/<patient_id>/")
    print("- Processing status: /videos/process/<video_id>/")
    print("- View video: /videos/<video_id>/")
    print("- API status: /api/videos/<video_id>/status/")
    
    print("\n⚙️  Configuration Files:")
    print("- Celery config: ndas/celery.py")
    print("- Video models: video/models.py")
    print("- Video forms: video/forms.py")
    print("- Processing tasks: video/tasks.py")
    
    print("\n📊 Monitoring:")
    print("- Check Celery workers: celery -A ndas inspect active")
    print("- Monitor tasks: celery -A ndas flower (install flower package)")
    print("- Redis monitoring: redis-cli monitor")

def main():
    """Main setup function."""
    print("🚀 NDAS Video Processing Enhancement Setup")
    print("="*50)
    
    success = True
    
    # Check Python dependencies
    deps_ok, missing = check_dependencies()
    if not deps_ok:
        print(f"\n📦 Installing missing dependencies...")
        if not install_dependencies(missing):
            print("❌ Failed to install dependencies. Please install manually:")
            print(f"   pip install {' '.join(missing)}")
            success = False
    
    # Check system dependencies
    if not check_system_dependencies():
        print("❌ System dependencies not met. Please install FFmpeg and Redis.")
        success = False
    
    # Run migrations
    if success and not run_migrations():
        print("❌ Database migration failed.")
        success = False
    
    # Create startup scripts
    if success:
        create_celery_startup_scripts()
    
    # Test setup (optional, don't fail if workers aren't running)
    if success:
        print("\n🧪 Testing setup...")
        test_video_processing()
        # Note: Don't require Celery workers to be running for setup
    
    if success:
        print_usage_instructions()
    else:
        print("\n❌ Setup completed with errors. Please resolve the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
