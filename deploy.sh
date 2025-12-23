#!/bin/bash

################################################################################
# NDAS Deployment Script
# Neurodevelopmental Assessment System
#
# This script automates common deployment tasks for NDAS
#
# Usage:
#   ./deploy.sh [command]
#
# Commands:
#   setup       - Initial deployment setup
#   update      - Update existing deployment
#   backup      - Create backup of database and media
#   restore     - Restore from backup
#   check       - Run deployment checks
#   restart     - Restart application services
#   logs        - Show application logs
#   help        - Show this help message
#
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Functions
print_header() {
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_env_file() {
    if [ ! -f ".env" ]; then
        print_error ".env file not found!"
        print_info "Please copy an example file and configure it:"
        echo "  Development: cp .env.development.example .env"
        echo "  Production:  cp .env.production.example .env"
        exit 1
    fi
    print_success ".env file found"
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    print_success "Python $(python3 --version) found"
}

activate_venv() {
    if [ -d "venv" ]; then
        print_info "Activating virtual environment..."
        source venv/bin/activate
        print_success "Virtual environment activated"
    else
        print_warning "Virtual environment not found. Creating one..."
        python3 -m venv venv
        source venv/bin/activate
        print_success "Virtual environment created and activated"
    fi
}

install_dependencies() {
    print_info "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    print_success "Dependencies installed"
}

create_directories() {
    print_info "Creating necessary directories..."
    mkdir -p logs
    mkdir -p media
    mkdir -p backups
    chmod 755 logs media backups
    print_success "Directories created"
}

run_migrations() {
    print_info "Running database migrations..."
    python manage.py migrate
    print_success "Migrations completed"
}

collect_static() {
    print_info "Collecting static files..."
    python manage.py collectstatic --noinput
    print_success "Static files collected"
}

create_superuser() {
    print_info "Creating superuser account..."
    python manage.py createsuperuser
}

deployment_check() {
    print_info "Running deployment checks..."
    python manage.py check --deploy
    print_success "Deployment checks completed"
}

backup_database() {
    BACKUP_DIR="backups"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)

    print_info "Creating database backup..."

    # Check if using PostgreSQL or SQLite
    if [ -f "db.sqlite3" ]; then
        cp db.sqlite3 "$BACKUP_DIR/db_${TIMESTAMP}.sqlite3"
        print_success "Database backed up to: $BACKUP_DIR/db_${TIMESTAMP}.sqlite3"
    else
        # PostgreSQL backup (requires .env configuration)
        print_info "PostgreSQL backup - please run manually:"
        echo "  pg_dump -U [DB_USER] [DB_NAME] > $BACKUP_DIR/db_${TIMESTAMP}.sql"
    fi
}

backup_media() {
    BACKUP_DIR="backups"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)

    print_info "Creating media files backup..."
    if [ -d "media" ] && [ "$(ls -A media)" ]; then
        tar -czf "$BACKUP_DIR/media_${TIMESTAMP}.tar.gz" media/
        print_success "Media backed up to: $BACKUP_DIR/media_${TIMESTAMP}.tar.gz"
    else
        print_warning "Media directory is empty, skipping backup"
    fi
}

show_logs() {
    if [ -f "logs/django.log" ]; then
        tail -f logs/django.log
    else
        print_warning "No log file found at logs/django.log"
    fi
}

restart_services() {
    print_info "Restarting services..."

    # Check if running on systemd
    if systemctl list-units --type=service | grep -q ndas; then
        sudo systemctl restart ndas
        sudo systemctl status ndas
        print_success "NDAS service restarted"
    else
        print_warning "No systemd service found. Please restart manually."
    fi

    # Restart nginx if available
    if systemctl list-units --type=service | grep -q nginx; then
        sudo systemctl reload nginx
        print_success "Nginx reloaded"
    fi
}

setup_deployment() {
    print_header "NDAS Initial Deployment Setup"

    check_python
    check_env_file
    activate_venv
    install_dependencies
    create_directories
    run_migrations
    collect_static

    print_info "\nWould you like to create a superuser account? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        create_superuser
    fi

    deployment_check

    print_header "Setup Complete!"
    print_success "NDAS has been successfully set up"
    print_info "\nNext steps:"
    echo "  1. Review the deployment checklist: python manage.py check --deploy"
    echo "  2. Test the application: python manage.py runserver"
    echo "  3. Configure your web server (Nginx/Apache)"
    echo "  4. Setup SSL certificate"
    echo "  5. Configure automated backups"
}

update_deployment() {
    print_header "NDAS Deployment Update"

    print_warning "This will update the deployment. Continue? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        print_info "Update cancelled"
        exit 0
    fi

    # Backup before update
    print_info "Creating backup before update..."
    backup_database
    backup_media

    check_python
    check_env_file
    activate_venv
    install_dependencies
    run_migrations
    collect_static
    deployment_check

    print_info "\nWould you like to restart services? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        restart_services
    fi

    print_header "Update Complete!"
    print_success "NDAS has been successfully updated"
}

full_backup() {
    print_header "Creating Full Backup"

    mkdir -p backups
    backup_database
    backup_media

    print_header "Backup Complete!"
    print_success "All backups created in: backups/"
}

show_help() {
    cat << EOF

NDAS Deployment Script

Usage: $0 [command]

Commands:
  setup       Initial deployment setup (first time)
  update      Update existing deployment
  backup      Create backup of database and media
  restore     Restore from backup (interactive)
  check       Run deployment checks
  restart     Restart application services
  logs        Show application logs (tail -f)
  help        Show this help message

Examples:
  $0 setup        # First time deployment
  $0 update       # Update after code changes
  $0 backup       # Create backup before changes
  $0 check        # Verify deployment configuration

For more information, see DEPLOYMENT.md

EOF
}

# Main script logic
case "$1" in
    setup)
        setup_deployment
        ;;
    update)
        update_deployment
        ;;
    backup)
        full_backup
        ;;
    check)
        print_header "Running Deployment Checks"
        check_env_file
        activate_venv
        deployment_check
        ;;
    restart)
        restart_services
        ;;
    logs)
        show_logs
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac

exit 0
