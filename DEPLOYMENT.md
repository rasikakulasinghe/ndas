# NDAS Deployment Guide

Complete deployment guide for the Neurodevelopmental Assessment System (NDAS).

## Table of Contents

- [Prerequisites](#prerequisites)
- [Deployment Options](#deployment-options)
- [Option 1: cPanel/Shared Hosting (SQLite)](#option-1-cpanelshared-hosting-sqlite)
- [Option 2: VPS with PostgreSQL](#option-2-vps-with-postgresql)
- [Post-Deployment](#post-deployment)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)

---

## Prerequisites

### System Requirements

- **Python**: 3.9 or higher
- **Database**: SQLite (default) or PostgreSQL 12+
- **Memory**: Minimum 512MB RAM (2GB+ recommended)
- **Storage**: 10GB+ (depending on video storage needs)
- **External Dependencies**:
  - FFmpeg (for video processing)
  - Redis (optional, for caching)

### Required Packages

See `requirements.txt` for all Python dependencies.

---

## Deployment Options

Choose the deployment option that best fits your infrastructure:

1. **cPanel/Shared Hosting** - Best for small to medium deployments with limited video storage
2. **VPS/Cloud Server** - Best for large deployments with PostgreSQL and high traffic

---

## Option 1: cPanel/Shared Hosting (SQLite)

### 1.1 Prepare Environment

```bash
# 1. Upload code to server
# Upload entire project directory to: /home/username/ndas/
# Keep it OUTSIDE public_html for security

# 2. Create virtual environment via cPanel Python App
# - Python Version: 3.9 or higher
# - Application Root: /home/username/ndas
# - Application URL: yourdomain.com
```

### 1.2 Configure Environment

```bash
# 1. Copy environment file
cp .env.production.example .env

# 2. Edit .env file
nano .env

# Update these critical settings:
# - SECRET_KEY (generate new one)
# - ALLOWED_HOSTS (your domain)
# - EMAIL settings
# - STATIC_ROOT and MEDIA_ROOT paths
```

**Example .env for cPanel:**

```env
SECRET_KEY=your-generated-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

STATIC_ROOT=/home/username/public_html/yourdomain.com/static/
MEDIA_ROOT=/home/username/public_html/yourdomain.com/media/

EMAIL_HOST=mail.yourdomain.com
EMAIL_HOST_USER=noreply@yourdomain.com
EMAIL_HOST_PASSWORD=your-password

SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### 1.3 Install Dependencies

```bash
# Activate virtual environment
source /home/username/virtualenv/ndas/3.9/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 1.4 Setup Database and Static Files

```bash
# Create necessary directories
mkdir -p /home/username/public_html/yourdomain.com/static
mkdir -p /home/username/public_html/yourdomain.com/media
mkdir -p logs

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser
```

### 1.5 Configure File Permissions

```bash
# Set proper permissions
chmod 755 /home/username/ndas
chmod 644 /home/username/ndas/*.py
chmod 600 /home/username/ndas/.env
chmod 644 /home/username/ndas/db.sqlite3
chmod -R 755 /home/username/public_html/yourdomain.com/static
chmod -R 755 /home/username/public_html/yourdomain.com/media
chmod -R 755 logs
```

### 1.6 Create Passenger WSGI

Create `passenger_wsgi.py` in your application root:

```python
import sys
import os

# Add application directory to path
INTERP = os.path.join(os.environ['HOME'], 'virtualenv', 'ndas', '3.9', 'bin', 'python3')
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

# Setup paths
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'ndas.settings'

# Import Django application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### 1.7 Setup SSL Certificate

1. Go to cPanel → SSL/TLS Status
2. Run AutoSSL or install Let's Encrypt certificate
3. Verify HTTPS works before enabling redirects

### 1.8 Configure Cron Jobs

Add to cPanel Cron Jobs:

```bash
# Database backup - Daily at 2 AM
0 2 * * * cd /home/username/ndas && /home/username/virtualenv/ndas/3.9/bin/python manage.py backup_database

# Clean old backups - Weekly
0 3 * * 0 find /home/username/backups/ndas/ -name "*.sql" -mtime +30 -delete

# Clear expired sessions - Daily
0 4 * * * cd /home/username/ndas && /home/username/virtualenv/ndas/3.9/bin/python manage.py clearsessions
```

---

## Option 2: VPS with PostgreSQL

### 2.1 Server Setup (Ubuntu/Debian)

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install required packages
sudo apt install -y python3-pip python3-venv postgresql nginx redis-server ffmpeg git

# 3. Configure firewall
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### 2.2 Setup PostgreSQL

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE ndas_production;
CREATE USER ndas_user WITH PASSWORD 'your-secure-password';
ALTER ROLE ndas_user SET client_encoding TO 'utf8';
ALTER ROLE ndas_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE ndas_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE ndas_production TO ndas_user;
\q

# Allow local connections (if needed)
sudo nano /etc/postgresql/*/main/pg_hba.conf
# Add: local   ndas_production   ndas_user   md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### 2.3 Setup Application

```bash
# 1. Create application directory
sudo mkdir -p /opt/ndas
sudo chown $USER:$USER /opt/ndas
cd /opt/ndas

# 2. Clone repository
git clone <your-repository-url> .

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
pip install gunicorn psycopg2-binary

# 5. Configure environment
cp .env.production.postgresql.example .env
nano .env
chmod 600 .env
```

**Example .env for VPS:**

```env
SECRET_KEY=your-generated-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

DB_ENGINE=django.db.backends.postgresql
DB_NAME=ndas_production
DB_USER=ndas_user
DB_PASSWORD=your-secure-password
DB_HOST=localhost
DB_PORT=5432

STATIC_ROOT=/var/www/yourdomain.com/static/
MEDIA_ROOT=/var/www/yourdomain.com/media/

REDIS_URL=redis://localhost:6379/0

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

SECURE_SSL_REDIRECT=True
SECURE_PROXY_SSL_HEADER=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### 2.4 Setup Database and Static Files

```bash
# Create directories
sudo mkdir -p /var/www/yourdomain.com/static
sudo mkdir -p /var/www/yourdomain.com/media
sudo mkdir -p /var/backups/ndas
mkdir -p logs

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser

# Set permissions
sudo chown -R www-data:www-data /var/www/yourdomain.com
sudo chown -R www-data:www-data /opt/ndas/logs
sudo chown -R www-data:www-data /opt/ndas/media
```

### 2.5 Configure Gunicorn Service

Create `/etc/systemd/system/ndas.service`:

```ini
[Unit]
Description=NDAS Gunicorn Daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/ndas
Environment="PATH=/opt/ndas/venv/bin"
ExecStart=/opt/ndas/venv/bin/gunicorn \
          --workers 3 \
          --bind unix:/opt/ndas/ndas.sock \
          --timeout 300 \
          --max-requests 1000 \
          --max-requests-jitter 50 \
          ndas.wsgi:application

[Install]
WantedBy=multi-user.target
```

Start and enable service:

```bash
sudo systemctl start ndas
sudo systemctl enable ndas
sudo systemctl status ndas
```

### 2.6 Configure Nginx

Create `/etc/nginx/sites-available/ndas`:

```nginx
upstream ndas_app {
    server unix:/opt/ndas/ndas.sock fail_timeout=0;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    client_max_body_size 2G;
    client_body_timeout 300s;

    location /static/ {
        alias /var/www/yourdomain.com/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /var/www/yourdomain.com/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://ndas_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/ndas /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 2.7 Setup SSL with Let's Encrypt

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Verify auto-renewal
sudo certbot renew --dry-run
```

### 2.8 Setup Automated Backups

Add to crontab (`sudo crontab -e`):

```bash
# Database backup - Daily at 2 AM
0 2 * * * pg_dump -U ndas_user ndas_production > /var/backups/ndas/db_$(date +\%Y\%m\%d).sql

# Media backup - Weekly on Sunday at 3 AM
0 3 * * 0 tar -czf /var/backups/ndas/media_$(date +\%Y\%m\%d).tar.gz /var/www/yourdomain.com/media/

# Clean old backups - Keep 30 days
0 4 * * * find /var/backups/ndas/ -name "db_*.sql" -mtime +30 -delete
0 4 * * * find /var/backups/ndas/ -name "media_*.tar.gz" -mtime +30 -delete

# Clear expired sessions - Daily at 5 AM
0 5 * * * /opt/ndas/venv/bin/python /opt/ndas/manage.py clearsessions
```

---

## Post-Deployment

### Security Checklist

```bash
# Run Django deployment check
python manage.py check --deploy

# Verify settings
python manage.py diffsettings

# Test email configuration
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Test message', 'from@example.com', ['to@example.com'])

# Check SSL rating (after SSL setup)
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=yourdomain.com
```

### Performance Optimization

1. **Enable Redis caching** (if available)
2. **Configure CDN** for static files (optional)
3. **Setup log rotation**:

```bash
# /etc/logrotate.d/ndas
/opt/ndas/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 www-data www-data
    sharedscripts
    postrotate
        systemctl reload ndas
    endscript
}
```

### Monitoring

```bash
# Monitor Gunicorn (VPS)
sudo journalctl -u ndas -f

# Monitor Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Monitor application logs
tail -f /opt/ndas/logs/django.log

# Check system resources
htop
```

---

## Troubleshooting

### Common Issues

**500 Internal Server Error**
```bash
# Check logs
tail -f logs/django.log
sudo journalctl -u ndas -n 50

# Check permissions
ls -la /opt/ndas
ls -la /var/www/yourdomain.com

# Restart service
sudo systemctl restart ndas
```

**Static files not loading**
```bash
# Recollect static files
python manage.py collectstatic --clear --noinput

# Check Nginx configuration
sudo nginx -t

# Verify paths in .env
echo $STATIC_ROOT
```

**Database connection errors**
```bash
# Test PostgreSQL connection
psql -U ndas_user -d ndas_production -h localhost

# Check PostgreSQL status
sudo systemctl status postgresql

# Review database settings in .env
```

**Email not sending**
```bash
# Test SMTP connection
telnet mail.yourdomain.com 587

# Check credentials in .env
# Review email logs
tail -f logs/django.log | grep email
```

---

## Maintenance

### Regular Tasks

**Daily:**
- Monitor logs for errors
- Check disk space
- Verify backups completed

**Weekly:**
- Review security logs
- Update dependencies (test environment first)
- Clean temporary files

**Monthly:**
- Test backup restoration
- Review user access
- Update SSL certificates (auto with Let's Encrypt)
- Security audit

### Update Procedure

```bash
# 1. Backup everything
sudo systemctl stop ndas
pg_dump -U ndas_user ndas_production > backup_pre_update.sql

# 2. Pull latest code
cd /opt/ndas
git pull origin main

# 3. Update dependencies
source venv/bin/activate
pip install -r requirements.txt --upgrade

# 4. Run migrations
python manage.py migrate

# 5. Collect static files
python manage.py collectstatic --noinput

# 6. Restart service
sudo systemctl start ndas
sudo systemctl status ndas

# 7. Verify deployment
python manage.py check --deploy
```

### Emergency Rollback

```bash
# 1. Stop service
sudo systemctl stop ndas

# 2. Restore code
git checkout <previous-commit-hash>

# 3. Restore database
psql -U ndas_user ndas_production < backup_pre_update.sql

# 4. Restart service
sudo systemctl start ndas
```

---

## Additional Resources

- **Django Deployment Checklist**: https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/
- **Security Best Practices**: Review CLAUDE.md in project root
- **Monitoring Tools**: Consider Sentry, New Relic, or Datadog
- **Support**: Check project documentation or contact system administrator

---

**Last Updated**: 2025-12-23
**Version**: 1.0
