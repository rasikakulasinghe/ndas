# Spec: Authentication Rate Limiting

## REMOVED Requirements

None - rate limiting is a new security capability.

## ADDED Requirements

### Requirement: Authentication endpoints must enforce rate limiting

All authentication-related endpoints (login, password reset, registration, email verification) MUST implement rate limiting to prevent brute force attacks and abuse.

#### Scenario: Login endpoint rate limits by IP address

**Given** a malicious actor attempts brute force login
**When** making more than 5 POST requests to `/users/login/` within 1 minute from same IP
**Then** subsequent requests are blocked with HTTP 429 Too Many Requests
**And** error message displays "Too many login attempts. Please wait a few minutes and try again."
**And** the rate limit attempt is logged with IP address and username

#### Scenario: Login endpoint rate limits by username

**Given** an attacker targets a specific user account
**When** making more than 3 login attempts for the same username within 1 minute
**Then** subsequent requests for that username are blocked regardless of IP
**And** error message indicates rate limit
**And** the security event is logged

#### Scenario: Rate limit resets after time window expires

**Given** a user triggered rate limit by failed login attempts
**When** 1 minute passes since the last failed attempt (for IP-based limit)
**Or** 1 minute passes for username-based limit
**Then** the user can attempt login again
**And** the counter resets to zero

#### Scenario: Successful login does not trigger rate limit

**Given** a legitimate user enters correct credentials
**When** logging in successfully
**Then** no rate limit is applied
**And** the user is redirected to dashboard
**And** rate limit counter is not incremented for successful logins

### Requirement: Dual-key rate limiting strategy

Rate limiting MUST use both IP-based and username-based keys to prevent both distributed attacks and targeted account attacks.

#### Scenario: Dual key prevents distributed brute force

**Given** an attacker uses multiple IP addresses to brute force an account
**When** the attacker makes 3 attempts from each IP for username "admin"
**Then** after 3 total attempts for "admin" username, further attempts are blocked
**And** the username-based rate limit triggers even though IP limit not exceeded

#### Scenario: Dual key prevents IP-based attack on multiple accounts

**Given** an attacker from single IP tries many different usernames
**When** the attacker makes 5 login attempts total from the IP
**Then** further attempts are blocked regardless of username
**And** the IP-based rate limit protects against account enumeration

### Requirement: Password reset must be rate limited

Password reset functionality MUST enforce rate limiting to prevent email flooding and account enumeration.

#### Scenario: Password reset limited to 3 requests per hour per IP

**Given** a user requests password reset
**When** making more than 3 password reset requests within 1 hour from same IP
**Then** subsequent requests are blocked
**And** error message displays "Too many password reset requests. Please try again later."

#### Scenario: Password reset limited by email address

**Given** an attacker targets a specific email address
**When** making multiple password reset requests for the same email
**Then** requests are limited to 3 per hour per email address
**And** prevents email flooding to victim's inbox

### Requirement: Rate limit configuration must be environment-aware

Rate limiting MUST be configurable via environment variables and disabled in development mode for testing convenience.

#### Scenario: Rate limiting enabled in production

**Given** the application runs in production (DEBUG=False)
**When** the settings are loaded
**Then** RATELIMIT_ENABLE is set to True
**And** all rate limit decorators are active

#### Scenario: Rate limiting disabled in development

**Given** the application runs in development (DEBUG=True)
**And** developer sets RATELIMIT_ENABLE=False in .env
**When** making multiple rapid login attempts
**Then** no rate limiting is applied
**And** developers can test login flow without restrictions

#### Scenario: Rate limits use Redis cache in production

**Given** the application runs in production
**When** a rate limit decorator is triggered
**Then** the counter is stored in Redis cache
**And** RATELIMIT_USE_CACHE = 'default' setting is active
**And** rate limit state persists across application restarts

## MODIFIED Requirements

None - this is new functionality.

## Cross-References

- **Depends on**: Redis cache configuration in production
- **Depends on**: `django-ratelimit` package installation
- **Related to**: `csrf-protection` - Both enhance authentication security
- **Related to**: Input sanitization spec - Prevents timing attack username enumeration
- **Related to**: `security-testing` - Rate limiting validated by RateLimitingTestCase

## Implementation Notes

**Dependencies:**
```txt
django-ratelimit==4.1.0
```

**Settings Configuration** (ndas/settings.py):
```python
# Rate Limiting
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_ENABLE = config('RATELIMIT_ENABLE', default=True, cast=bool)
RATELIMIT_VIEW = 'ndas.views.rate_limited_error'
```

**View Decorators** (users/views.py):
```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='5/m', method='POST', block=True)
@ratelimit(key='post:username', rate='3/m', method='POST', block=True)
def loginPage(request):
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        messages.error(request, 'Too many login attempts. Please wait a few minutes and try again.')
        logger.warning(f"Rate limit triggered for IP {request.META.get('REMOTE_ADDR')}")
        return render(request, 'users/login.html', {'rate_limited': True})
    # ... existing login logic
```

**Password Reset Rate Limiting:**
```python
@ratelimit(key='ip', rate='3/h', method='POST', block=True)
@ratelimit(key='post:email', rate='3/h', method='POST', block=True)
def password_reset_request(request):
    # Password reset logic
```

**Custom Error Handler** (ndas/views.py):
```python
def rate_limited_error(request, exception):
    """Custom view for rate limit errors."""
    return render(request, 'errors/rate_limited.html', status=429)
```

**Rate Limit Configuration:**
- Login: 5/min per IP, 3/min per username
- Password reset: 3/hour per IP, 3/hour per email
- Registration: 3/hour per IP
- Email verification resend: 3/hour per email

**Testing Strategy:**
1. Unit test: Attempt 6 failed logins, verify 6th is blocked
2. Unit test: Attempt logins from different IPs for same username, verify username limit
3. Integration test: Verify rate limit resets after time window
4. Security test: Verify rate limit logging captures IP and username

**Logging:**
```python
logger.warning(
    f"Rate limit triggered for IP {request.META.get('REMOTE_ADDR')} "
    f"attempting username: {request.POST.get('username', 'N/A')}"
)
```

**Rollback Strategy:**
- Set RATELIMIT_ENABLE=False in .env to disable all rate limiting
- Remove @ratelimit decorators from views
- Keep django-ratelimit installed (no harm if unused)
