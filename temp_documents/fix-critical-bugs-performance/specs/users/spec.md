# User Management - Validation, Performance, and Security

## MODIFIED Requirements

### Requirement: Object Retrieval Error Handling
User management views MUST use `get_object_or_404()` for object retrieval to provide proper HTTP responses.

#### Scenario: Missing user returns 404
- **WHEN** viewing user profile with non-existent ID
- **THEN** HTTP 404 response is returned
- **AND** NOT HTTP 500 Internal Server Error

#### Scenario: Invalid user session lookup
- **WHEN** accessing session with invalid ID
- **THEN** 404 page is displayed
- **AND** error is logged for monitoring

### Requirement: User Activity Tracking Performance
User activity log queries MUST use `select_related()` to prevent N+1 queries.

#### Scenario: Activity log displays efficiently
- **WHEN** viewing user activity log with 100 entries
- **THEN** user data is fetched with JOINs
- **AND** queries remain under 5 total
- **AND** NOT 100+ queries (one per log entry)

#### Scenario: Admin views all user activities
- **WHEN** displaying activity logs for all users
- **THEN** user information is prefetched
- **AND** page loads in under 1 second

### Requirement: Session Update Throttling
User session activity updates MUST be throttled to reduce database load.

#### Scenario: Session update cached
- **WHEN** authenticated user makes multiple requests
- **THEN** session last_activity is updated at most once per minute
- **AND** NOT on every single request

#### Scenario: Cache hit reduces database writes
- **WHEN** user makes 10 requests within 60 seconds
- **THEN** only 1 database UPDATE query occurs
- **AND** 9 requests hit cache and skip database

#### Scenario: Cache miss triggers update
- **WHEN** more than 60 seconds since last session update
- **THEN** database UPDATE executes
- **AND** new timestamp is cached for 2 minutes

## ADDED Requirements

### Requirement: Profile Picture Validation
Profile picture uploads MUST validate file size, format, dimensions, and content integrity.

#### Scenario: Valid profile picture accepted
- **WHEN** uploading JPG image 2MB, 800x800 pixels
- **THEN** validation passes
- **AND** image is stored successfully

#### Scenario: Oversized image rejected
- **WHEN** uploading image larger than 5MB
- **THEN** validation error is raised
- **AND** upload is rejected with clear message

#### Scenario: Invalid file format rejected
- **WHEN** uploading .gif or .bmp file
- **THEN** validation error indicates allowed formats (JPG, JPEG, PNG)
- **AND** file is not stored

#### Scenario: Corrupted image file rejected
- **WHEN** uploading file with .jpg extension but corrupted content
- **THEN** PIL image verification detects corruption
- **AND** validation error is raised

#### Scenario: Oversized dimensions rejected
- **WHEN** uploading 8000x8000 pixel image
- **THEN** validation error indicates maximum 4000x4000 pixels
- **AND** user is prompted to resize

#### Scenario: Executable disguised as image rejected
- **WHEN** attempting to upload .exe renamed to .jpg
- **THEN** content validation detects mismatch
- **AND** upload is rejected for security

### Requirement: Username Query Optimization
Views that list usernames MUST use `.only()` or `.values_list()` to avoid loading unnecessary fields.

#### Scenario: Username dropdown loads efficiently
- **WHEN** populating username dropdown with 500+ users
- **THEN** only id and username fields are fetched
- **AND** NOT all user fields (email, password hash, etc.)

#### Scenario: Memory usage remains low
- **WHEN** loading username list
- **THEN** memory usage is proportional to username count
- **AND** NOT proportional to full user object size

### Requirement: Database Index on Lookup Fields
User model fields used for lookups MUST have database indexes for performance.

#### Scenario: Mobile number lookup is fast
- **WHEN** searching user by mobile_primary field
- **THEN** database uses index for WHERE clause
- **AND** query completes in under 50ms for 10,000+ users

#### Scenario: Username search optimized
- **WHEN** filtering users by username
- **THEN** database unique index is used
- **AND** lookup time is O(log n)

### Requirement: Subscription Status Race Condition Prevention
Subscription status updates MUST use transactions and proper cache invalidation ordering.

#### Scenario: Concurrent status updates don't conflict
- **WHEN** two processes attempt to update subscription status simultaneously
- **THEN** database lock prevents race condition
- **AND** updates are serialized correctly

#### Scenario: Cache cleared after transaction commits
- **WHEN** subscription status is updated
- **THEN** database transaction commits first
- **AND** THEN cache is cleared
- **AND** no stale reads occur between cache clear and commit

#### Scenario: Cache unavailable falls back gracefully
- **WHEN** cache service is down during subscription update
- **THEN** update still succeeds using database
- **AND** next request rebuilds cache

## Technical Notes

### Profile Picture Validation Implementation

```python
def clean_profile_picture(self):
    """Validate profile picture upload"""
    picture = self.cleaned_data.get('profile_picture')

    if not picture:
        return picture

    # Check file size (5MB max)
    if picture.size > 5 * 1024 * 1024:
        raise ValidationError(_('Image file size cannot exceed 5MB.'))

    # Check file extension
    valid_extensions = ['.jpg', '.jpeg', '.png']
    ext = os.path.splitext(picture.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError(_('Unsupported file extension. Use JPG, JPEG, or PNG.'))

    # Validate actual image content
    try:
        from PIL import Image
        img = Image.open(picture)
        img.verify()

        # Reopen for dimension check (verify() closes file)
        picture.seek(0)
        img = Image.open(picture)

        # Check dimensions (max 4000x4000)
        if img.width > 4000 or img.height > 4000:
            raise ValidationError(_('Image dimensions too large. Maximum 4000x4000 pixels.'))

    except Exception as e:
        raise ValidationError(_('Invalid image file.'))

    # Reset file pointer after verification
    picture.seek(0)

    return picture
```

### Session Update Throttling

```python
# users/middleware.py
from django.core.cache import cache
from django.utils import timezone

def process_request(self, request):
    if request.user.is_authenticated:
        session_key = request.session.session_key

        cache_key = f"user_session_update_{request.user.id}_{session_key}"
        last_update = cache.get(cache_key)

        # Only update if last update was more than 60 seconds ago
        if last_update is None or (timezone.now() - last_update).seconds > 60:
            try:
                UserSession.objects.filter(
                    user=request.user,
                    session_key=session_key,
                    is_active=True
                ).update(last_activity=timezone.now())
                cache.set(cache_key, timezone.now(), 120)  # Cache for 2 minutes
            except Exception:
                pass  # Gracefully handle cache/database errors
```

### Username Query Optimization

```python
# Before (loads all fields)
username_list = CustomUser.objects.all()

# After Option 1 (if only usernames needed)
username_list = CustomUser.objects.values_list('username', flat=True)

# After Option 2 (if id and username needed for dropdown)
username_list = CustomUser.objects.only('id', 'username')
```

### Subscription Race Condition Fix

```python
def update_status(self):
    """Update subscription status based on current state"""
    # Calculate what the status should be
    new_status = None
    if self.is_expired:
        new_status = 'expired'
    elif self.is_expiring_soon:
        new_status = 'expiring_soon'
    elif self.status == 'trial' and not self.is_trial_expired:
        new_status = 'trial'
    elif self.status in ['active', 'trial']:
        new_status = 'active'

    if new_status and self.status != new_status:
        with transaction.atomic():
            # Lock row for update
            subscription = Subscription.objects.select_for_update().get(pk=self.pk)
            subscription.status = new_status
            subscription.save(update_fields=['status', 'updated_at'])

            # Clear cache AFTER transaction commits
            self._clear_cache()

    return new_status
```

### Affected Files

- `users/views.py` - Lines 215, 221, 443 (get_object_or_404)
- `users/views.py` - Lines 421, 818, 837 (select_related)
- `users/views.py` - Lines 657, 682, 690, 695, 829, 838, 848 (username optimization)
- `users/middleware.py` - Lines 35-39 (session throttling)
- `users/forms.py` - Line 245 (profile picture validation)
- `users/models.py` - Lines 32-36 (mobile index)
- `users/models.py` - Lines 748-780 (subscription race condition)

### Performance Targets

- **Activity log (100 entries):** < 5 queries
- **Username list (500 users):** < 100ms, < 10MB memory
- **Session updates:** 95% reduction in database writes
- **Profile validation:** < 50ms per file
- **Mobile lookup:** < 50ms for 10,000+ users
