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

- **Python**: 3.10 or higher (3.11 recommended). `requirements.txt` pins `Django~=5.2.0` specifically because the demo.ndas.lk/ndas.lk cPanel accounts top out at Python 3.11.15 (no 3.12+ offered as of 2026-09-06) -- Django 6.0 needs Python >=3.12 and will refuse to install on this host. If the host later adds 3.12+, Django can be upgraded and this constraint revisited.
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

### 1.0 Two Domains, One Hosting Account (demo.ndas.lk + ndas.lk)

When both a demo and a live site share one cPanel account, give each domain
its own **application root** (its own code checkout, its own cPanel "Python
App", its own venv) rather than pointing both domains at one checkout:

```
/home/rasikakulasinghe/
  |-- ndas-demo/            # cPanel Python App root for demo.ndas.lk
  |   |-- .env               (from env files/.env.production.demo.example)
  |   |-- passenger_wsgi.py  (from passenger_wsgi.py.example)
  |   `-- db.sqlite3
  |-- ndas-live/            # cPanel Python App root for ndas.lk
  |   |-- .env               (from env files/.env.production.live.example)
  |   |-- passenger_wsgi.py  (from passenger_wsgi.py.example)
  |   `-- db.sqlite3
  `-- public_html/
      |-- demo.ndas.lk/{static,media}/
      `-- ndas.lk/{static,media}/
```

Each app root is a full copy of this repo. Inside each one:

```bash
python scripts/switch_env.py production-demo   # inside ndas-demo/
python scripts/switch_env.py production-live   # inside ndas-live/
```

This copies the matching template (`env files/.env.production.demo.example`
or `.env.production.live.example`) over that app root's own `.env`, backing
up whatever was there first. Because the two app roots are separate
directories, their `.env` and `db.sqlite3` files never collide on disk --
switching one never touches the other's data. Give each domain its own
`SECRET_KEY` and email account (the templates leave these as placeholders on
purpose; the script never fills them in).

> **⚠ `db.sqlite3` is currently committed to this git repository**, which
> undermines the "never collide" guarantee above: a `git pull` in either
> app root pulls whatever `db.sqlite3` is in the repo's history, which can
> conflict with or overwrite that domain's live patient data. This must be
> fixed at the repo level (`git rm --cached db.sqlite3` and add it to
> `.gitignore`, plus a history scrub since patient data is already
> committed) before either app root is safely kept in sync with `git pull`.
> `passenger_wsgi.py` has the same "tracked when it should be per-app-root
> local state" problem -- see the warning in [1.6](#16-create-passenger-wsgi).

### 1.1 Prepare Environment

```bash
# 1. Upload code to server
# Upload entire project directory to: /home/username/ndas/
# Keep it OUTSIDE public_html for security

# 2. Create virtual environment via cPanel Python App
# - Python Version: highest 3.10+ your cPanel account offers (3.11.x is
#   confirmed working for demo/live -- see 1.6). Django is pinned to
#   ~=5.2.0 to match; only move to Django 6.0 once the host offers 3.12+.
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
# Activate virtual environment (path/version come from cPanel's
# "Setup Python App" page for this app root -- 3.11 is confirmed working
# for demo/live on this host)
source /home/username/virtualenv/ndas/3.11/bin/activate

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

Running `python scripts/switch_env.py production-demo` (or
`production-live`) now also generates `passenger_wsgi.py` in this app root
from `passenger_wsgi.py.example`, with `INTERP` already filled in for that
domain's known cPanel venv -- you no longer need to hand-copy and edit the
`.example` file for these two domains.

> **Python version note (resolved 2026-09-06):** this cPanel account's
> "Setup Python App" selector tops out at **3.11.15** -- no 3.12+ is
> offered. `PASSENGER_WSGI_INTERP` in `scripts/switch_env.py` points both
> `production-demo` (`www.demo.ndas.lk`) and `production-live`
> (`www.ndas.lk`) at Python **3.11** venvs, and `requirements.txt` is
> pinned to `Django~=5.2.0` (not 6.0, which needs Python >=3.12) to match.
> The 3.11 venv for demo.ndas.lk is confirmed created; **confirm
> ndas.lk's "Setup Python App" was also recreated under 3.11 before
> deploying there.** If this host ever adds Python 3.12+, Django can move
> to 6.0 and `PASSENGER_WSGI_INTERP` updated accordingly.

If cPanel ever recreates the app under a different venv name or Python
version, update `PASSENGER_WSGI_INTERP` in `scripts/switch_env.py` to match
before re-running the switch.

For any other app root (a new domain, or a different Python version),
still copy `passenger_wsgi.py.example` to `passenger_wsgi.py` by hand and
set `INTERP` to the venv path cPanel's "Setup Python App" page shows for
that specific app. A missing `passenger_wsgi.py`, or one pointing at a venv
path that doesn't exist -- or, as happened on demo.ndas.lk, a hand-edit that
merges two statements onto one line -- is one of the most common causes of
a 500 error with no application-level log output on cPanel.

> **⚠ passenger_wsgi.py is git-tracked, not per-app-root local state.**
> Because the generated `passenger_wsgi.py` (unlike `.env`) is committed to
> this repository, whichever domain most recently ran `switch_env.py` is
> whatever gets pulled into the *other* app root on its next `git pull` --
> silently swapping in the wrong domain's `INTERP` and reintroducing the
> exact silent-500 failure this tooling exists to prevent. **Always re-run
> `python scripts/switch_env.py production-demo` / `production-live`
> immediately after every `git pull` in that app root, before restarting
> the app.**

### 1.7 Setup SSL Certificate

1. Go to cPanel → SSL/TLS Status
2. Run AutoSSL or install Let's Encrypt certificate
3. Verify HTTPS works before enabling redirects

### 1.8 Configure Cron Jobs

> **⚠ `python manage.py backup_database` does not exist in this codebase** --
> no such management command is defined anywhere in the project. A cron job
> that calls it will fail silently every run (cron does not surface errors
> unless mail is configured) and no backup is ever produced. Use a raw
> SQLite `.backup` copy instead, as below. `BACKUP_PATH` in each domain's
> `.env` is a convention for where these commands should write, not
> something the Django app itself reads.

Set this up **once per app root** (`ndas-demo/` and `ndas-live/` each need
their own cron entries -- they do not share cPanel Cron Jobs automatically):

```bash
# Database backup - Daily at 2 AM (adjust paths for this app root; BACKUP_PATH
# below should match this domain's own .env BACKUP_PATH, e.g. ndas-demo/ vs ndas-live/)
0 2 * * * sqlite3 /home/username/ndas-demo/db.sqlite3 ".backup '/home/username/backups/ndas-demo/db_$(date +\%Y\%m\%d).sqlite3'"

# Clean old backups - Weekly
0 3 * * 0 find /home/username/backups/ndas-demo/ -name "*.sqlite3" -mtime +30 -delete

# Clear expired sessions - Daily
0 4 * * * cd /home/username/ndas-demo && /home/username/virtualenv/www.demo.ndas.lk/3.11/bin/python manage.py clearsessions
```

Repeat with `ndas-live` / `www.ndas.lk` paths for the live site's own cron entries.

### 1.9 Caching, Sessions, and Rate Limiting Without Redis

Both `.env.production.demo.example` and `.env.production.live.example` leave
`REDIS_URL=` empty with a comment saying this gives a "file-based cache."
That comment is inaccurate: `ndas/settings.py` actually falls back to
Django's **`LocMemCache`** (an in-process memory cache, not file-based) when
`REDIS_URL` is unset. In production (`DEBUG=False`), NDAS puts both user
sessions (`SESSION_ENGINE = 'django.contrib.sessions.backends.cache'`) and
rate-limit counters (`RATELIMIT_USE_CACHE = 'default'`) in that same cache.

If cPanel's Passenger app for a domain ever runs more than one worker
process (common under load), `LocMemCache` is **not shared between them**:
- A user's session created in one worker is invisible to a request handled
  by another worker -- they get logged out at random.
- Rate limiting is enforced per-process instead of per-site, so the
  documented 10/min-create, 5/min-delete limits are effectively looser than
  configured.

If Redis is available on the hosting account, set `REDIS_URL` in each
domain's `.env` to use it. If it is not, be aware of this limitation rather
than relying on the (currently incorrect) "file-based cache" comment.

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

    # /media/ holds patient videos, clinical attachments, and profile
    # pictures. It MUST proxy to Django rather than being aliased straight
    # to disk — institution.views.protected_media_view is what enforces
    # that a clinician can only reach files belonging to their own
    # institution. Aliasing this path serves every patient's files to
    # anyone who can guess a URL, with no login and no isolation.
    location /media/ {
        proxy_pass http://ndas_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Unreachable directly (no external request can specify this prefix) —
    # only reachable via the X-Accel-Redirect header that
    # protected_media_view sets after it has authorized the request above.
    # This is what lets Nginx stream the actual bytes (including Range
    # requests for video seeking) once Django has approved access.
    location /x-accel-media/ {
        internal;
        alias /var/www/yourdomain.com/media/;
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

On cPanel Passenger hosting specifically, a 500 with nothing in
`logs/django.log` usually means the WSGI layer never reached Django at all.
Check, in order:
1. `passenger_wsgi.py` exists in this app root (see [1.6](#16-create-passenger-wsgi)) and its `INTERP` path is this app's actual venv, not another app's. If a `git pull` happened since the last `switch_env.py` run in this app root, re-run `switch_env.py <mode>` here first -- `passenger_wsgi.py` is git-tracked and a pull can silently overwrite it with the *other* domain's `INTERP`.
2. The venv `INTERP` points at is actually Python 3.10+ (3.11 confirmed working on this host). `requirements.txt` pins `Django~=5.2.0` for exactly this reason -- an older venv (e.g. leftover 3.8) fails to install or import Django, which on Passenger surfaces as exactly this kind of silent 500. Don't try to install Django 6.0 here: this cPanel account doesn't offer the Python 3.12+ it requires.
3. `.env` exists in this app root and was switched to the right profile (`python scripts/switch_env.py production-demo` or `production-live`) -- settings.py has no fallback for a missing `SECRET_KEY`.
4. `ALLOWED_HOSTS` in `.env` exactly matches the domain being requested (`demo.ndas.lk` vs `ndas.lk` -- a mismatch here is a 400, not always a 500, but check it anyway).
5. cPanel's "Setup Python App" page for this domain shows the app as running, and its "Application root" matches where `passenger_wsgi.py` actually lives.

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

**Last Updated**: 2026-09-05
**Version**: 1.2
**Rasika Kulasinghe**
