#!/bin/bash
# NDAS Video Processing - Celery Management Scripts

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="ndas"
VENV_PATH="venv"
LOG_DIR="logs"
PID_DIR="pids"

# Create directories if they don't exist
mkdir -p $LOG_DIR $PID_DIR

# Function to check if virtual environment exists
check_venv() {
    if [ ! -d "$VENV_PATH" ]; then
        echo -e "${RED}Virtual environment not found at $VENV_PATH${NC}"
        echo "Please create a virtual environment first:"
        echo "python -m venv $VENV_PATH"
        exit 1
    fi
}

# Function to activate virtual environment
activate_venv() {
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        source "$VENV_PATH/Scripts/activate"
    else
        source "$VENV_PATH/bin/activate"
    fi
}

# Function to check if Redis is running
check_redis() {
    if ! command -v redis-cli &> /dev/null; then
        echo -e "${RED}Redis CLI not found. Please install Redis.${NC}"
        return 1
    fi
    
    if ! redis-cli ping &> /dev/null; then
        echo -e "${RED}Redis server is not running.${NC}"
        echo "Please start Redis server first:"
        echo "redis-server"
        return 1
    fi
    
    echo -e "${GREEN}Redis is running${NC}"
    return 0
}

# Function to start Celery worker
start_worker() {
    echo -e "${BLUE}Starting Celery worker...${NC}"
    check_venv
    activate_venv
    
    if ! check_redis; then
        exit 1
    fi
    
    # Check if worker is already running
    if [ -f "$PID_DIR/celery_worker.pid" ]; then
        PID=$(cat "$PID_DIR/celery_worker.pid")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${YELLOW}Celery worker is already running (PID: $PID)${NC}"
            return
        fi
    fi
    
    # Start worker with specific queues and concurrency
    celery -A $PROJECT_NAME worker \
        --loglevel=info \
        --concurrency=2 \
        --queues=video_processing,default \
        --pidfile="$PID_DIR/celery_worker.pid" \
        --logfile="$LOG_DIR/celery_worker.log" \
        --detach
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Celery worker started successfully${NC}"
        echo "Log file: $LOG_DIR/celery_worker.log"
        echo "PID file: $PID_DIR/celery_worker.pid"
    else
        echo -e "${RED}Failed to start Celery worker${NC}"
    fi
}

# Function to start Celery beat
start_beat() {
    echo -e "${BLUE}Starting Celery beat scheduler...${NC}"
    check_venv
    activate_venv
    
    if ! check_redis; then
        exit 1
    fi
    
    # Check if beat is already running
    if [ -f "$PID_DIR/celery_beat.pid" ]; then
        PID=$(cat "$PID_DIR/celery_beat.pid")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${YELLOW}Celery beat is already running (PID: $PID)${NC}"
            return
        fi
    fi
    
    # Start beat scheduler
    celery -A $PROJECT_NAME beat \
        --loglevel=info \
        --scheduler=django_celery_beat.schedulers:DatabaseScheduler \
        --pidfile="$PID_DIR/celery_beat.pid" \
        --logfile="$LOG_DIR/celery_beat.log" \
        --detach
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Celery beat started successfully${NC}"
        echo "Log file: $LOG_DIR/celery_beat.log"
        echo "PID file: $PID_DIR/celery_beat.pid"
    else
        echo -e "${RED}Failed to start Celery beat${NC}"
    fi
}

# Function to start Flower monitoring
start_flower() {
    echo -e "${BLUE}Starting Celery Flower monitoring...${NC}"
    check_venv
    activate_venv
    
    if ! check_redis; then
        exit 1
    fi
    
    # Check if flower is already running
    if [ -f "$PID_DIR/celery_flower.pid" ]; then
        PID=$(cat "$PID_DIR/celery_flower.pid")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${YELLOW}Celery Flower is already running (PID: $PID)${NC}"
            return
        fi
    fi
    
    # Start Flower
    celery -A $PROJECT_NAME flower \
        --port=5555 \
        --pidfile="$PID_DIR/celery_flower.pid" \
        --logfile="$LOG_DIR/celery_flower.log" \
        --detach
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Celery Flower started successfully${NC}"
        echo "Access monitoring at: http://localhost:5555"
        echo "Log file: $LOG_DIR/celery_flower.log"
        echo "PID file: $PID_DIR/celery_flower.pid"
    else
        echo -e "${RED}Failed to start Celery Flower${NC}"
    fi
}

# Function to stop services
stop_service() {
    SERVICE_NAME=$1
    PID_FILE="$PID_DIR/celery_${SERVICE_NAME}.pid"
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${BLUE}Stopping Celery $SERVICE_NAME (PID: $PID)...${NC}"
            kill $PID
            
            # Wait for process to stop
            for i in {1..10}; do
                if ! ps -p $PID > /dev/null 2>&1; then
                    echo -e "${GREEN}Celery $SERVICE_NAME stopped successfully${NC}"
                    rm -f "$PID_FILE"
                    return
                fi
                sleep 1
            done
            
            # Force kill if still running
            echo -e "${YELLOW}Force killing Celery $SERVICE_NAME...${NC}"
            kill -9 $PID 2>/dev/null
            rm -f "$PID_FILE"
        else
            echo -e "${YELLOW}Celery $SERVICE_NAME is not running${NC}"
            rm -f "$PID_FILE"
        fi
    else
        echo -e "${YELLOW}No PID file found for Celery $SERVICE_NAME${NC}"
    fi
}

# Function to show status
show_status() {
    echo -e "${BLUE}=== NDAS Video Processing Status ===${NC}"
    
    # Check Redis
    if check_redis &> /dev/null; then
        echo -e "Redis: ${GREEN}Running${NC}"
    else
        echo -e "Redis: ${RED}Not Running${NC}"
    fi
    
    # Check services
    for service in worker beat flower; do
        PID_FILE="$PID_DIR/celery_${service}.pid"
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p $PID > /dev/null 2>&1; then
                echo -e "Celery $service: ${GREEN}Running${NC} (PID: $PID)"
            else
                echo -e "Celery $service: ${RED}Not Running${NC} (stale PID file)"
            fi
        else
            echo -e "Celery $service: ${RED}Not Running${NC}"
        fi
    done
    
    # Show queue status if worker is running
    if [ -f "$PID_DIR/celery_worker.pid" ]; then
        PID=$(cat "$PID_DIR/celery_worker.pid")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "\n${BLUE}=== Queue Status ===${NC}"
            activate_venv
            celery -A $PROJECT_NAME inspect active 2>/dev/null || echo "No active tasks"
        fi
    fi
}

# Function to restart all services
restart_all() {
    echo -e "${BLUE}Restarting all Celery services...${NC}"
    stop_service worker
    stop_service beat
    stop_service flower
    sleep 2
    start_worker
    start_beat
    start_flower
}

# Function to show logs
show_logs() {
    SERVICE_NAME=${1:-worker}
    LOG_FILE="$LOG_DIR/celery_${SERVICE_NAME}.log"
    
    if [ -f "$LOG_FILE" ]; then
        echo -e "${BLUE}=== Celery $SERVICE_NAME Logs ===${NC}"
        tail -f "$LOG_FILE"
    else
        echo -e "${RED}Log file not found: $LOG_FILE${NC}"
    fi
}

# Function to process videos using management command
process_videos() {
    echo -e "${BLUE}Processing videos using Django management command...${NC}"
    check_venv
    activate_venv
    
    # Show available options
    echo "Available options:"
    echo "1. Process specific video by ID"
    echo "2. Process all pending videos"
    echo "3. Process failed videos (retry)"
    echo "4. Show processing statistics"
    
    read -p "Select option (1-4): " option
    
    case $option in
        1)
            read -p "Enter video ID: " video_id
            python manage.py process_videos --video-id $video_id --wait
            ;;
        2)
            read -p "Enter max videos to process (default 10): " max_videos
            max_videos=${max_videos:-10}
            python manage.py process_videos --batch --max-videos $max_videos --wait
            ;;
        3)
            python manage.py process_videos --batch --status failed --max-videos 5 --wait
            ;;
        4)
            python manage.py monitor_video_processing --stats
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            ;;
    esac
}

# Main script logic
case "$1" in
    start)
        case "$2" in
            worker) start_worker ;;
            beat) start_beat ;;
            flower) start_flower ;;
            all)
                start_worker
                start_beat
                start_flower
                ;;
            *) echo "Usage: $0 start {worker|beat|flower|all}" ;;
        esac
        ;;
    stop)
        case "$2" in
            worker) stop_service worker ;;
            beat) stop_service beat ;;
            flower) stop_service flower ;;
            all)
                stop_service worker
                stop_service beat
                stop_service flower
                ;;
            *) echo "Usage: $0 stop {worker|beat|flower|all}" ;;
        esac
        ;;
    restart)
        case "$2" in
            worker)
                stop_service worker
                sleep 1
                start_worker
                ;;
            beat)
                stop_service beat
                sleep 1
                start_beat
                ;;
            flower)
                stop_service flower
                sleep 1
                start_flower
                ;;
            all) restart_all ;;
            *) echo "Usage: $0 restart {worker|beat|flower|all}" ;;
        esac
        ;;
    status) show_status ;;
    logs) show_logs "$2" ;;
    process) process_videos ;;
    *)
        echo "NDAS Video Processing - Celery Management"
        echo "Usage: $0 {start|stop|restart|status|logs|process}"
        echo ""
        echo "Commands:"
        echo "  start {worker|beat|flower|all}  - Start Celery services"
        echo "  stop {worker|beat|flower|all}   - Stop Celery services"
        echo "  restart {worker|beat|flower|all} - Restart Celery services"
        echo "  status                          - Show service status"
        echo "  logs [worker|beat|flower]       - Show logs (default: worker)"
        echo "  process                         - Interactive video processing"
        echo ""
        echo "Examples:"
        echo "  $0 start all                    - Start all services"
        echo "  $0 restart worker               - Restart worker only"
        echo "  $0 logs worker                  - Show worker logs"
        echo "  $0 process                      - Process videos interactively"
        ;;
esac
