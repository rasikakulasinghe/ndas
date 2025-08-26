# NDAS Video Processing - Celery Management (PowerShell)
# Windows-compatible script for managing Celery services

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "status", "logs", "process", "help")]
    [string]$Action = "help",
    
    [Parameter(Position=1)]
    [ValidateSet("worker", "beat", "flower", "all")]
    [string]$Service = "all",
    
    [switch]$Wait
)

# Configuration
$ProjectName = "ndas"
$VenvPath = "venv"
$LogDir = "logs"
$PidDir = "pids"

# Colors for output
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Blue = "Cyan"

# Create directories if they don't exist
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
if (-not (Test-Path $PidDir)) { New-Item -ItemType Directory -Path $PidDir | Out-Null }

# Function to check virtual environment
function Test-VirtualEnvironment {
    if (-not (Test-Path $VenvPath)) {
        Write-Host "Virtual environment not found at $VenvPath" -ForegroundColor $Red
        Write-Host "Please create a virtual environment first:"
        Write-Host "python -m venv $VenvPath"
        exit 1
    }
}

# Function to activate virtual environment
function Enable-VirtualEnvironment {
    Test-VirtualEnvironment
    $activateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        & $activateScript
    } else {
        Write-Host "Cannot find activation script at $activateScript" -ForegroundColor $Red
        exit 1
    }
}

# Function to check Redis
function Test-Redis {
    try {
        $redisCheck = redis-cli ping 2>$null
        if ($redisCheck -eq "PONG") {
            Write-Host "Redis is running" -ForegroundColor $Green
            return $true
        }
    } catch {
        Write-Host "Redis server is not running." -ForegroundColor $Red
        Write-Host "Please start Redis server first:"
        Write-Host "redis-server"
        return $false
    }
    return $false
}

# Function to get process by PID file
function Get-ProcessByPidFile {
    param([string]$PidFile)
    
    if (Test-Path $PidFile) {
        $processId = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($processId) {
            try {
                return Get-Process -Id $processId -ErrorAction Stop
            } catch {
                Remove-Item $PidFile -ErrorAction SilentlyContinue
            }
        }
    }
    return $null
}

# Function to start Celery worker
function Start-CeleryWorker {
    Write-Host "Starting Celery worker..." -ForegroundColor $Blue
    Enable-VirtualEnvironment
    
    if (-not (Test-Redis)) {
        exit 1
    }
    
    $pidFile = Join-Path $PidDir "celery_worker.pid"
    $process = Get-ProcessByPidFile $pidFile
    
    if ($process) {
        Write-Host "Celery worker is already running (PID: $($process.Id))" -ForegroundColor $Yellow
        return
    }
    
    $logFile = Join-Path $LogDir "celery_worker.log"
    
    # Start worker in background
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = "celery"
    $startInfo.Arguments = "-A $ProjectName worker --loglevel=info --concurrency=2 --queues=video_processing,default"
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    
    $process = [System.Diagnostics.Process]::Start($startInfo)
    
    if ($process) {
        $process.Id | Out-File -FilePath $pidFile -Encoding ascii
        Write-Host "Celery worker started successfully (PID: $($process.Id))" -ForegroundColor $Green
        Write-Host "Log file: $logFile"
        Write-Host "PID file: $pidFile"
    } else {
        Write-Host "Failed to start Celery worker" -ForegroundColor $Red
    }
}

# Function to start Celery beat
function Start-CeleryBeat {
    Write-Host "Starting Celery beat scheduler..." -ForegroundColor $Blue
    Enable-VirtualEnvironment
    
    if (-not (Test-Redis)) {
        exit 1
    }
    
    $pidFile = Join-Path $PidDir "celery_beat.pid"
    $process = Get-ProcessByPidFile $pidFile
    
    if ($process) {
        Write-Host "Celery beat is already running (PID: $($process.Id))" -ForegroundColor $Yellow
        return
    }
    
    $logFile = Join-Path $LogDir "celery_beat.log"
    
    # Start beat in background
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = "celery"
    $startInfo.Arguments = "-A $ProjectName beat --loglevel=info --scheduler=django_celery_beat.schedulers:DatabaseScheduler"
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    
    $process = [System.Diagnostics.Process]::Start($startInfo)
    
    if ($process) {
        $process.Id | Out-File -FilePath $pidFile -Encoding ascii
        Write-Host "Celery beat started successfully (PID: $($process.Id))" -ForegroundColor $Green
        Write-Host "Log file: $logFile"
        Write-Host "PID file: $pidFile"
    } else {
        Write-Host "Failed to start Celery beat" -ForegroundColor $Red
    }
}

# Function to start Flower
function Start-CeleryFlower {
    Write-Host "Starting Celery Flower monitoring..." -ForegroundColor $Blue
    Enable-VirtualEnvironment
    
    if (-not (Test-Redis)) {
        exit 1
    }
    
    $pidFile = Join-Path $PidDir "celery_flower.pid"
    $process = Get-ProcessByPidFile $pidFile
    
    if ($process) {
        Write-Host "Celery Flower is already running (PID: $($process.Id))" -ForegroundColor $Yellow
        return
    }
    
    $logFile = Join-Path $LogDir "celery_flower.log"
    
    # Start Flower in background
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = "celery"
    $startInfo.Arguments = "-A $ProjectName flower --port=5555"
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    
    $process = [System.Diagnostics.Process]::Start($startInfo)
    
    if ($process) {
        $process.Id | Out-File -FilePath $pidFile -Encoding ascii
        Write-Host "Celery Flower started successfully (PID: $($process.Id))" -ForegroundColor $Green
        Write-Host "Access monitoring at: http://localhost:5555"
        Write-Host "Log file: $logFile"
        Write-Host "PID file: $pidFile"
    } else {
        Write-Host "Failed to start Celery Flower" -ForegroundColor $Red
    }
}

# Function to stop service
function Stop-CeleryService {
    param([string]$ServiceName)
    
    $pidFile = Join-Path $PidDir "celery_$ServiceName.pid"
    $process = Get-ProcessByPidFile $pidFile
    
    if ($process) {
        Write-Host "Stopping Celery $ServiceName (PID: $($process.Id))..." -ForegroundColor $Blue
        try {
            $process.CloseMainWindow()
            if (-not $process.WaitForExit(5000)) {
                $process.Kill()
            }
            Write-Host "Celery $ServiceName stopped successfully" -ForegroundColor $Green
        } catch {
            Write-Host "Error stopping Celery $ServiceName : $_" -ForegroundColor $Red
        }
        Remove-Item $pidFile -ErrorAction SilentlyContinue
    } else {
        Write-Host "Celery $ServiceName is not running" -ForegroundColor $Yellow
    }
}

# Function to show status
function Show-Status {
    Write-Host "=== NDAS Video Processing Status ===" -ForegroundColor $Blue
    
    # Check Redis
    if (Test-Redis) {
        Write-Host "Redis: Running" -ForegroundColor $Green
    } else {
        Write-Host "Redis: Not Running" -ForegroundColor $Red
    }
    
    # Check services
    foreach ($svc in @("worker", "beat", "flower")) {
        $pidFile = Join-Path $PidDir "celery_$svc.pid"
        $process = Get-ProcessByPidFile $pidFile
        
        if ($process) {
            Write-Host "Celery $svc : Running (PID: $($process.Id))" -ForegroundColor $Green
        } else {
            Write-Host "Celery $svc : Not Running" -ForegroundColor $Red
        }
    }
    
    # Show queue status if worker is running
    $workerPidFile = Join-Path $PidDir "celery_worker.pid"
    $workerProcess = Get-ProcessByPidFile $workerPidFile
    
    if ($workerProcess) {
        Write-Host "`n=== Queue Status ===" -ForegroundColor $Blue
        Enable-VirtualEnvironment
        try {
            celery -A $ProjectName inspect active
        } catch {
            Write-Host "No active tasks"
        }
    }
}

# Function to show logs
function Show-Logs {
    param([string]$ServiceName = "worker")
    
    $logFile = Join-Path $LogDir "celery_$ServiceName.log"
    
    if (Test-Path $logFile) {
        Write-Host "=== Celery $ServiceName Logs ===" -ForegroundColor $Blue
        Get-Content $logFile -Wait -Tail 50
    } else {
        Write-Host "Log file not found: $logFile" -ForegroundColor $Red
    }
}

# Function to process videos
function Start-VideoProcessing {
    Write-Host "Processing videos using Django management command..." -ForegroundColor $Blue
    Enable-VirtualEnvironment
    
    Write-Host "Available options:"
    Write-Host "1. Process specific video by ID"
    Write-Host "2. Process all pending videos"
    Write-Host "3. Process failed videos (retry)"
    Write-Host "4. Show processing statistics"
    
    $option = Read-Host "Select option (1-4)"
    
    switch ($option) {
        "1" {
            $videoId = Read-Host "Enter video ID"
            python manage.py process_videos --video-id $videoId --wait
        }
        "2" {
            $maxVideos = Read-Host "Enter max videos to process (default 10)"
            if ([string]::IsNullOrEmpty($maxVideos)) { $maxVideos = "10" }
            python manage.py process_videos --batch --max-videos $maxVideos --wait
        }
        "3" {
            python manage.py process_videos --batch --status failed --max-videos 5 --wait
        }
        "4" {
            python manage.py monitor_video_processing --stats
        }
        default {
            Write-Host "Invalid option" -ForegroundColor $Red
        }
    }
}

# Function to show help
function Show-Help {
    Write-Host "NDAS Video Processing - Celery Management" -ForegroundColor $Blue
    Write-Host "Usage: .\celery_manager.ps1 [Action] [Service]" -ForegroundColor $Blue
    Write-Host ""
    Write-Host "Actions:" -ForegroundColor $Yellow
    Write-Host "  start    - Start Celery services"
    Write-Host "  stop     - Stop Celery services"
    Write-Host "  restart  - Restart Celery services"
    Write-Host "  status   - Show service status"
    Write-Host "  logs     - Show logs"
    Write-Host "  process  - Interactive video processing"
    Write-Host ""
    Write-Host "Services:" -ForegroundColor $Yellow
    Write-Host "  worker   - Celery worker"
    Write-Host "  beat     - Celery beat scheduler"
    Write-Host "  flower   - Flower monitoring"
    Write-Host "  all      - All services (default)"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor $Green
    Write-Host "  .\celery_manager.ps1 start all"
    Write-Host "  .\celery_manager.ps1 restart worker"
    Write-Host "  .\celery_manager.ps1 logs worker"
    Write-Host "  .\celery_manager.ps1 process"
}

# Main script logic
switch ($Action) {
    "start" {
        switch ($Service) {
            "worker" { Start-CeleryWorker }
            "beat" { Start-CeleryBeat }
            "flower" { Start-CeleryFlower }
            "all" {
                Start-CeleryWorker
                Start-CeleryBeat
                Start-CeleryFlower
            }
        }
    }
    "stop" {
        switch ($Service) {
            "worker" { Stop-CeleryService "worker" }
            "beat" { Stop-CeleryService "beat" }
            "flower" { Stop-CeleryService "flower" }
            "all" {
                Stop-CeleryService "worker"
                Stop-CeleryService "beat"
                Stop-CeleryService "flower"
            }
        }
    }
    "restart" {
        switch ($Service) {
            "worker" {
                Stop-CeleryService "worker"
                Start-Sleep 2
                Start-CeleryWorker
            }
            "beat" {
                Stop-CeleryService "beat"
                Start-Sleep 2
                Start-CeleryBeat
            }
            "flower" {
                Stop-CeleryService "flower"
                Start-Sleep 2
                Start-CeleryFlower
            }
            "all" {
                Stop-CeleryService "worker"
                Stop-CeleryService "beat"
                Stop-CeleryService "flower"
                Start-Sleep 2
                Start-CeleryWorker
                Start-CeleryBeat
                Start-CeleryFlower
            }
        }
    }
    "status" { Show-Status }
    "logs" { Show-Logs $Service }
    "process" { Start-VideoProcessing }
    "help" { Show-Help }
    default { Show-Help }
}
