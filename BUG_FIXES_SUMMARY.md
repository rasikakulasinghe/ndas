# Bug Fixes Summary - Django Server Startup

## Date: 2025-12-22

## Bugs Found and Fixed:

### 1. **CRITICAL: Missing django.contrib.staticfiles from INSTALLED_APPS**
   - **Error**: `InvalidStorageError: Could not find config for 'staticfiles' in settings.STORAGES`
   - **Location**: `ndas/settings.py` line 24
   - **Fix**: Added `'django.contrib.staticfiles'` to INSTALLED_APPS
   - **Status**: ✅ FIXED

### 2. **CRITICAL: Incorrect STORAGES key**
   - **Error**: Django looking for 'staticfiles' key but config had 'static'
   - **Location**: `ndas/settings.py` line 165
   - **Fix**: Changed `"static"` to `"staticfiles"` in STORAGES dict
   - **Status**: ✅ FIXED

### 3. **Missing Package: django-debug-toolbar**
   - **Error**: `ModuleNotFoundError: No module named 'debug_toolbar'`
   - **Fix**: Installed `django-debug-toolbar==4.2.0`
   - **Status**: ✅ FIXED

### 4. **Missing Package: bleach**
   - **Error**: `ModuleNotFoundError: No module named 'bleach'`
   - **Fix**: Installed `bleach==6.1.0`
   - **Status**: ✅ FIXED

### 5. **CRITICAL: Git Bash Path Translation Issue**
   - **Error**: STATIC_URL and MEDIA_URL being transformed to incorrect paths
   - **Example**: `/static/` → `/C:/Program Files/Git/static/`
   - **Root Cause**: Environment variables set in shell getting transformed by Git Bash
   - **Fix**:
     - Commented out STATIC_URL and MEDIA_URL in .env file
     - Fixed .bashrc encoding issues
     - Added warnings to .env.example
     - Documented to avoid exporting these as environment variables
   - **Status**: ✅ DOCUMENTED (user needs to restart shell/terminal)

### 6. **.bashrc Encoding Issue**
   - **Error**: `$'\377\376export': command not found` (UTF-16 BOM)
   - **Location**: `C:\Users\user\.bashrc`
   - **Fix**: Rewrote .bashrc with proper UTF-8 encoding
   - **Status**: ✅ FIXED

## Server Status:
✅ **SERVER NOW STARTS SUCCESSFULLY**

```
Django version 4.2.7, using settings 'ndas.settings'
Starting development server at http://127.0.0.1:8000/
```

## Remaining Warnings (Non-Critical):
- CKEditor 4.22.1 deprecation warning (not blocking server startup)
- Security warnings expected in development mode (DEBUG=True)

## Action Required by User:
1. **Restart your terminal/shell** to pick up the .bashrc changes
2. **Do NOT export** STATIC_URL, MEDIA_URL, STATIC_ROOT, or MEDIA_ROOT as shell environment variables
3. **If paths still incorrect**, check Windows environment variables and remove any Django-related paths

## Files Modified:
1. `ndas/settings.py` - Fixed INSTALLED_APPS and STORAGES
2. `.env` - Commented out STATIC_URL and MEDIA_URL
3. `.env.example` - Added warnings about environment variables
4. `C:\Users\user\.bashrc` - Fixed encoding and added warnings

## Verification Commands:
```bash
# Test server startup
python manage.py runserver

# Check configuration
python manage.py check

# Verify paths
python manage.py shell -c "from django.conf import settings; print(f'STATIC_URL: {settings.STATIC_URL}'); print(f'MEDIA_URL: {settings.MEDIA_URL}')"
```
