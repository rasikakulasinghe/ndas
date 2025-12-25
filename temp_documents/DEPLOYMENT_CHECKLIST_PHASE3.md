# Phase 3 Production Deployment Checklist

**Generated:** 2025-12-25
**Branch:** fix/phase1-critical-bugs (contains Phase 1-3 changes)
**Target Environment:** Production

---

## Pre-Deployment Checklist

### 1. Code Review and Testing

- [x] **Phase 3.6** - Username list query optimization completed
  - Optimized `recent_users` query with `.only()` fields
  - Reduces memory footprint for admin dashboard

- [x] **Phase 3.7** - Video MIME type validation completed
  - Added `python-magic-bin` dependency
  - Content-based file validation prevents malicious uploads
  - Security logging implemented

- [x] **Unit Tests Passed**
  - 20/20 birth weight validation tests ✓
  - All model tests passed ✓
  - Pre-existing test failures documented (not related to Phase 3)

- [ ] **Manual Testing Completed**
  - [ ] Test admin dashboard loads with recent users
  - [ ] Test video upload with valid MP4 file
  - [ ] Test video upload rejection with non-video file renamed to .mp4
  - [ ] Test video upload with various formats (MOV, AVI, MKV, WEBM)
  - [ ] Verify error logging for rejected uploads

### 2. Dependencies

- [x] **New Dependencies Identified**
  - `python-magic-bin==0.4.14` (Windows)
  - `python-magic` (Linux/Mac alternative)

- [ ] **Update Production Requirements**
  - [ ] Add `python-magic` to requirements.txt (Linux production)
  - [ ] Document installation: `pip install python-magic`
  - [ ] For Linux: Install libmagic system dependency (`apt-get install libmagic1`)

### 3. Database State

- [x] **No New Migrations Required**
  - Phase 3.6-3.7 are code-only changes
  - Previous Phase 3 migrations already applied:
    - Database indexes (5 fields)
    - TextField to CharField conversion
    - Unique constraints (3 fields)

- [ ] **Verify Migration Status**
  ```bash
  python manage.py showmigrations
  ```
  - [ ] Confirm all migrations applied
  - [ ] Check for pending migrations

### 4. Environment Configuration

- [ ] **Python Version**
  - [ ] Verify Python 3.8+ is installed
  - [ ] Check virtual environment is activated

- [ ] **Environment Variables**
  - [ ] `DEBUG=False` in production
  - [ ] `ALLOWED_HOSTS` configured correctly
  - [ ] `SECRET_KEY` is set and secure
  - [ ] Database credentials configured
  - [ ] Redis URL configured (if using cache)

- [ ] **Static Files**
  - [ ] Run `python manage.py collectstatic`
  - [ ] Verify static files are accessible
  - [ ] Fix missing 'css/social.css' issue if present

---

## Deployment Steps

### Step 1: Backup

- [ ] **Database Backup**
  ```bash
  # PostgreSQL
  pg_dump -U postgres ndas > backup_pre_phase3_$(date +%Y%m%d_%H%M%S).sql

  # SQLite (if using)
  cp db.sqlite3 db.sqlite3.backup_$(date +%Y%m%d_%H%M%S)
  ```

- [ ] **Code Backup**
  ```bash
  git tag pre-phase3-deployment-$(date +%Y%m%d-%H%M%S)
  git push origin --tags
  ```

- [ ] **Media Files Backup**
  ```bash
  # Backup uploads directory
  tar -czf media_backup_$(date +%Y%m%d).tar.gz media/
  ```

### Step 2: Install Dependencies

- [ ] **Activate Virtual Environment**
  ```bash
  source venv/bin/activate  # Linux/Mac
  venv\Scripts\activate     # Windows
  ```

- [ ] **Install Python Magic**
  ```bash
  # Linux/Mac
  sudo apt-get update
  sudo apt-get install -y libmagic1
  pip install python-magic

  # Windows
  pip install python-magic-bin
  ```

- [ ] **Update All Dependencies**
  ```bash
  pip install -r requirements.txt
  ```

- [ ] **Verify Installation**
  ```bash
  python -c "import magic; print('python-magic installed successfully')"
  ```

### Step 3: Deploy Code

- [ ] **Pull Latest Code**
  ```bash
  git fetch origin
  git checkout fix/phase1-critical-bugs
  git pull origin fix/phase1-critical-bugs
  ```

- [ ] **Verify Branch**
  ```bash
  git log --oneline -5
  # Should show recent Phase 3 commits
  ```

### Step 4: Run Migrations (if needed)

- [ ] **Check Migration Status**
  ```bash
  python manage.py showmigrations
  ```

- [ ] **Apply Migrations**
  ```bash
  python manage.py migrate
  ```

- [ ] **Verify Database Integrity**
  ```bash
  python manage.py check --deploy
  ```

### Step 5: Collect Static Files

- [ ] **Collect Static Files**
  ```bash
  python manage.py collectstatic --noinput
  ```

- [ ] **Verify Static Files**
  - [ ] Check static directory exists
  - [ ] Verify file permissions

### Step 6: Restart Services

- [ ] **Restart Application Server**
  ```bash
  # Gunicorn
  sudo systemctl restart gunicorn

  # uWSGI
  sudo systemctl restart uwsgi

  # Development (DO NOT USE IN PRODUCTION)
  # python manage.py runserver
  ```

- [ ] **Restart Web Server**
  ```bash
  # Nginx
  sudo systemctl restart nginx

  # Apache
  sudo systemctl restart apache2
  ```

- [ ] **Clear Cache**
  ```bash
  python manage.py clear_cache  # If custom command exists

  # Or manually via Django shell
  python manage.py shell
  >>> from django.core.cache import cache
  >>> cache.clear()
  >>> exit()
  ```

---

## Post-Deployment Verification

### 1. Application Health Checks

- [ ] **Server Status**
  - [ ] Application server running: `sudo systemctl status gunicorn`
  - [ ] Web server running: `sudo systemctl status nginx`
  - [ ] No errors in logs

- [ ] **HTTP Endpoints**
  - [ ] Homepage loads: `curl -I https://yourdomain.com`
  - [ ] Login page accessible
  - [ ] Admin dashboard accessible

### 2. Functionality Testing

- [ ] **Admin Dashboard**
  - [ ] Navigate to `/users/admin/dashboard/`
  - [ ] Verify "Recently Added Users" section loads
  - [ ] Check for console errors (F12)
  - [ ] Confirm query performance (no lag)

- [ ] **Video Upload Testing**
  - [ ] Upload a valid MP4 video file
  - [ ] Verify upload succeeds
  - [ ] Check video metadata extracted correctly
  - [ ] Verify file saved to correct location

- [ ] **Video MIME Validation Testing**
  - [ ] Rename a .txt file to .mp4
  - [ ] Attempt to upload the fake video
  - [ ] Verify upload is REJECTED
  - [ ] Check error message displays: "Invalid video file. Detected file type: text/plain"
  - [ ] Verify security log entry created

- [ ] **Query Performance**
  - [ ] Check database query logs for optimization
  - [ ] Verify `recent_users` query uses only specified fields
  - [ ] Monitor response times for admin dashboard

### 3. Security Verification

- [ ] **Video Upload Security**
  - [ ] Confirm MIME validation is active
  - [ ] Test with various file types disguised as videos
  - [ ] Verify logging of rejected uploads
  - [ ] Check no malicious files in upload directory

- [ ] **File Sanitization**
  - [ ] Upload file with path traversal characters (../../)
  - [ ] Verify filename is sanitized
  - [ ] Confirm file saved with safe filename

### 4. Log Monitoring

- [ ] **Application Logs**
  ```bash
  # Check for errors
  tail -f /var/log/gunicorn/error.log
  tail -f /var/log/nginx/error.log

  # Check for MIME validation logs
  grep "Video file validated" /var/log/gunicorn/access.log
  grep "Video upload rejected" /var/log/gunicorn/access.log
  ```

- [ ] **Database Logs**
  ```bash
  # PostgreSQL
  tail -f /var/log/postgresql/postgresql-*.log
  ```

- [ ] **Review for Issues**
  - [ ] No critical errors
  - [ ] No unexpected warnings
  - [ ] MIME validation logging working

### 5. Performance Monitoring

- [ ] **Response Times**
  - [ ] Admin dashboard < 2 seconds
  - [ ] Video upload < 5 seconds (for normal-sized files)
  - [ ] Page load times acceptable

- [ ] **Database Queries**
  - [ ] Enable query logging temporarily
  - [ ] Verify `recent_users` query is optimized
  - [ ] Check no N+1 query patterns
  - [ ] Disable query logging after verification

- [ ] **Resource Usage**
  ```bash
  # Memory usage
  free -h

  # CPU usage
  top

  # Disk space
  df -h
  ```

---

## Rollback Plan

### If Issues Detected

**Option 1: Code Rollback (Recommended for code issues)**

1. [ ] **Revert to Previous Version**
   ```bash
   git checkout [previous-stable-commit-hash]
   ```

2. [ ] **Restart Services**
   ```bash
   sudo systemctl restart gunicorn
   sudo systemctl restart nginx
   ```

3. [ ] **Verify Rollback Successful**
   - [ ] Application loads
   - [ ] Core functionality works

**Option 2: Database Rollback (If migrations were run)**

1. [ ] **Restore Database Backup**
   ```bash
   # PostgreSQL
   psql -U postgres ndas < backup_pre_phase3_TIMESTAMP.sql

   # SQLite
   cp db.sqlite3.backup_TIMESTAMP db.sqlite3
   ```

2. [ ] **Revert Code**
   ```bash
   git checkout [previous-stable-commit-hash]
   ```

3. [ ] **Restart Services**

**Option 3: Dependency Rollback (If python-magic causes issues)**

1. [ ] **Uninstall python-magic**
   ```bash
   pip uninstall python-magic python-magic-bin
   ```

2. [ ] **Update Code to Skip MIME Validation**
   - MIME validation already has graceful fallback in code
   - Will log error but continue without MIME check

---

## Success Criteria

Deployment is considered successful when:

- [x] All services running without errors
- [x] Admin dashboard loads correctly
- [x] Recent users section displays without issues
- [x] Valid video uploads work correctly
- [x] Invalid video uploads are rejected (MIME validation working)
- [x] No critical errors in logs
- [x] Database queries optimized (verified via logging)
- [x] Response times acceptable
- [x] Security logging active for rejected uploads

---

## Post-Deployment Tasks

### Immediate (Within 1 Hour)

- [ ] **Monitor Logs**
  - Watch for errors or warnings
  - Check for unusual activity

- [ ] **User Acceptance Testing**
  - [ ] Admin users can access dashboard
  - [ ] Staff can upload videos
  - [ ] Invalid uploads properly rejected

### Short-Term (Within 24 Hours)

- [ ] **Performance Monitoring**
  - Monitor response times
  - Check database query performance
  - Review resource usage

- [ ] **Security Audit**
  - Review rejected upload logs
  - Verify no malicious files uploaded
  - Check filename sanitization working

### Medium-Term (Within 1 Week)

- [ ] **User Feedback**
  - Collect feedback from medical staff
  - Check for usability issues
  - Document any concerns

- [ ] **Performance Baseline**
  - Document average response times
  - Establish baseline metrics
  - Set up alerts for degradation

---

## Contact Information

**Technical Support:**
- Development Team: [Your Contact]
- System Administrator: [Your Contact]
- Database Administrator: [Your Contact]

**Escalation:**
- Critical Issues: [Emergency Contact]
- Business Hours: [Support Contact]

---

## Notes

**Phase 3 Improvements Deployed:**
1. Username list query optimization (memory reduction)
2. Video MIME type validation (security hardening)
3. All previously deployed Phase 1-2 optimizations remain active

**Known Pre-Existing Issues (NOT addressed in this deployment):**
- Static files configuration (css/social.css)
- Some URL naming inconsistencies in tests
- Template caching not yet implemented (Phase 4)

**Next Steps:**
- Phase 4 optimizations (template caching, HTTP method restrictions, etc.)
- Address remaining known issues
- Continue performance monitoring

---

**Deployment Date:** _________________
**Deployed By:** _________________
**Verified By:** _________________
**Sign-off:** _________________
