# Session Management Documentation

## Overview

SurfSense implements a **sliding session** authentication system using JWT tokens stored in HTTP-only cookies. This provides a balance between security and user experience by keeping users logged in as long as they remain active.

## How Sliding Sessions Work

### Basic Concept

A sliding session extends the session expiration time with each user activity:

1. User logs in → receives a JWT token with 24-hour expiration
2. User makes a request → token is checked
3. If token has < 12 hours remaining → token is refreshed with new 24-hour expiration
4. If user is inactive for 24 hours → session expires and user must log in again

### Implementation Details

**Components:**
- `app/middleware/session_refresh.py` - SlidingSessionMiddleware that handles cookie refresh
- `app/users.py` - CustomCookieTransport for cookie configuration
- `app/app.py` - Middleware registration and configuration

**Token Lifecycle:**
```
Login:        Token issued (24h TTL)
12h later:    User makes request → Token refreshed (new 24h TTL)
              User continues to use app → Token keeps getting refreshed
24h idle:     Token expires → User must re-authenticate
```

## Configuration

### Environment Variables

```bash
# Cookie security settings
COOKIE_SECURE=TRUE                    # Require HTTPS for cookies (production: TRUE)
TRUSTED_HOSTS=127.0.0.1,nginx-ip     # Comma-separated trusted proxy IPs

# Session refresh threshold (0.0 - 1.0)
SESSION_REFRESH_THRESHOLD=0.5         # Refresh when 50% of token lifetime remains
```

### Refresh Threshold

The `SESSION_REFRESH_THRESHOLD` controls when cookies are refreshed:

- **0.5 (default)**: Refresh when < 12 hours remain (50% of 24h)
- **0.25**: Refresh when < 6 hours remain (less frequent refreshes)
- **0.75**: Refresh when < 18 hours remain (more frequent refreshes)

**Trade-offs:**
- **Lower threshold** (e.g., 0.25):
  - ✅ Lower server load - fewer cookie operations
  - ❌ Higher risk - user may become idle before next refresh

- **Higher threshold** (e.g., 0.75):
  - ✅ Better UX - lower risk of expiration during active use
  - ❌ Higher server load - more cookie operations

**Recommendation:** Keep at 0.5 for balanced performance and UX.

## Security Considerations

### Cookie Security Flags

The authentication cookie is configured with multiple security flags:

```python
cookie_httponly=True      # Prevents JavaScript access (XSS protection)
cookie_secure=True        # HTTPS-only in production
cookie_samesite="lax"     # CSRF protection
max_age=86400             # 24 hours
```

### Middleware Execution Order

**CRITICAL:** Middleware order matters for security!

```python
# 1. ProxyHeadersMiddleware - MUST be first!
#    Detects HTTPS from X-Forwarded-Proto header when behind reverse proxy
#    Without this, cookie_secure flag won't work correctly

# 2. CORSMiddleware
#    Validates origin and handles preflight requests

# 3. SecurityHeadersMiddleware
#    Adds HSTS, CSP, and other security headers

# 4. SlidingSessionMiddleware
#    Refreshes auth cookie after security checks pass
```

**Why ProxyHeaders must be first:**
- Behind a reverse proxy (nginx, Cloudflare), requests appear as HTTP to the app
- ProxyHeadersMiddleware reads `X-Forwarded-Proto: https` header
- This ensures `request.url.scheme == "https"` is true
- Without this, `cookie_secure=True` fails and cookies aren't set

### Token Validation

The middleware performs intelligent token validation:

1. **JWT Decode**: Extracts `exp` (expiration) claim from token
2. **Signature Skip**: Skips signature verification (already validated by fastapi-users)
3. **Expiration Check**: Calculates remaining lifetime
4. **Threshold Check**: Refreshes if remaining < threshold

**Error Handling:**
- Invalid/expired tokens → Skip refresh (let fastapi-users handle auth failure)
- Decode errors → Log warning and skip refresh
- Unexpected errors → Refresh to be safe

## Security Monitoring Recommendations

While sliding sessions provide good UX, they have security implications. Consider implementing:

### 1. Token Reuse Monitoring

**Risk:** Stolen token can be used until expiration (up to 24 hours)

**Mitigation:**
- Log token usage with client IP address
- Alert on token reuse from different geographic locations
- Detect suspicious patterns (same token from multiple IPs)

**Implementation:**
```python
# In SlidingSessionMiddleware.dispatch()
logger.info("token_usage",
    user_id=user_id,
    ip=request.client.host,
    location=geoip_lookup(request.client.host)
)
```

### 2. Token Revocation

**Risk:** No way to invalidate tokens before expiration

**Mitigation:**
- Implement token revocation list in Redis
- Add "Revoke All Sessions" button in user settings
- Check revocation list before refreshing cookie

**Implementation:**
```python
# Store in Redis: revoked:{user_id}:{token_jti} with 24h TTL
if await redis.exists(f"revoked:{user_id}:{token_jti}"):
    # Don't refresh, force re-authentication
    return response
```

### 3. Refresh Token Pattern

**Alternative Approach:**
- Short-lived access tokens (1 hour)
- Long-lived refresh tokens (24 hours)
- Reduces risk window if token is stolen

**Trade-offs:**
- ✅ Better security - stolen access token expires quickly
- ❌ More complex - requires separate token refresh endpoint
- ❌ More API calls - must refresh tokens more frequently

### 4. Session Lifetime Limits

**Risk:** Active users can extend sessions indefinitely

**Mitigation:**
- Implement absolute maximum session age (e.g., 7 days)
- Store session creation time in token (`iat` claim)
- Force re-authentication after absolute limit

**Implementation:**
```python
iat = payload.get("iat")
if iat and (time.time() - iat) > ABSOLUTE_MAX_AGE:
    # Exceeded absolute limit, don't refresh
    return response
```

### 5. Suspicious Pattern Detection

Monitor for:
- Many requests from different IPs with same token (credential stuffing)
- Token reuse after logout (session hijacking)
- Rapid session creation/destruction (bot activity)

## Performance Optimization

### Cookie Refresh Optimization

**Problem:** Refreshing cookies on every request adds overhead

**Solution:** Threshold-based refresh (current implementation)
- Only refresh when token lifetime drops below threshold
- For 24h tokens with 0.5 threshold: ~2 refreshes per day max
- Reduces cookie operations by ~95%

**Performance Monitoring:**
```python
# In SlidingSessionMiddleware
if duration > 0.05:  # 50ms threshold
    logger.warning(f"SlidingSessionMiddleware took {duration:.3f}s")
```

### Database Impact

**No database queries:**
- JWT tokens are stateless
- No DB lookup required for session validation
- All session data stored in token itself

**Advantages:**
- Scales horizontally without session storage
- No database load for authentication
- Fast validation (cryptographic verification only)

**Disadvantages:**
- Can't revoke tokens before expiration (without revocation list)
- Token payload visible to client (use encryption for sensitive data)

## Environment-Aware Logging

The middleware adjusts log verbosity based on environment:

**Production (`ENVIRONMENT=production`):**
- Cookie refresh: INFO level
- Threshold checks: DEBUG level (not logged)
- Errors: WARNING/ERROR level

**Development (`ENVIRONMENT=development`):**
- Cookie refresh: DEBUG level
- All threshold checks: DEBUG level
- Detailed token lifetime information

## Testing

### Manual Testing

```bash
# 1. Login and capture cookie
curl -X POST http://localhost:8000/auth/jwt/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test@example.com","password":"password"}' \
  -c cookies.txt

# 2. Make authenticated request
curl http://localhost:8000/verify-token \
  -b cookies.txt \
  -v  # Check if Set-Cookie header appears

# 3. Wait 12+ hours and test again to verify refresh
```

### Unit Testing

```python
import pytest
from app.middleware.session_refresh import SlidingSessionMiddleware

def test_should_refresh_cookie_when_expired():
    middleware = SlidingSessionMiddleware(app, secret_key="test")

    # Create token with 1 hour remaining (< 50% of 24h)
    token = create_jwt(exp=time.time() + 3600)

    assert middleware._should_refresh_cookie(token) is True

def test_should_not_refresh_cookie_when_fresh():
    middleware = SlidingSessionMiddleware(app, secret_key="test")

    # Create token with 20 hours remaining (> 50% of 24h)
    token = create_jwt(exp=time.time() + 72000)

    assert middleware._should_refresh_cookie(token) is False
```

## Troubleshooting

### Cookies Not Being Set

**Symptom:** Login returns 200 OK but no cookie in browser

**Causes:**
1. **HTTPS mismatch**: `COOKIE_SECURE=TRUE` but app served over HTTP
   - **Fix:** Set `COOKIE_SECURE=FALSE` for local development
   - **Production:** Ensure ProxyHeadersMiddleware detects HTTPS correctly

2. **Untrusted proxy**: ProxyHeadersMiddleware not trusting reverse proxy
   - **Fix:** Add proxy IP to `TRUSTED_HOSTS` environment variable

3. **Domain mismatch**: Frontend and backend on different domains without CORS
   - **Fix:** Configure CORS_ORIGINS to include frontend domain

### Cookies Not Refreshing

**Symptom:** Cookie expires after 24 hours despite user activity

**Debug steps:**
```python
# Check middleware logs
journalctl -u surfsense -n 100 | grep "refresh"

# Should see:
# "Cookie refresh needed: 10800s remaining (3.0h) < threshold 43200s"
# "Refreshed authentication cookie for sliding session"
```

**Causes:**
1. **Threshold too low**: User becomes idle before refresh happens
   - **Fix:** Increase `SESSION_REFRESH_THRESHOLD` (e.g., 0.75 for earlier refreshes)

2. **Middleware not registered**: Missing `app.add_middleware(SlidingSessionMiddleware)`
   - **Fix:** Check `app/app.py` middleware configuration

3. **JWT decode error**: Invalid secret key or token format
   - **Fix:** Check logs for `"Invalid or expired JWT token"` warnings

### Performance Issues

**Symptom:** Slow response times with middleware enabled

**Debug:**
```python
# Check performance warnings
journalctl -u surfsense | grep "SlidingSessionMiddleware took"

# If consistently > 50ms, investigate:
# - JWT decode performance (should be < 1ms)
# - Cookie operations (should be < 5ms)
```

**Solutions:**
- Ensure `python-jose[cryptography]` is installed (native crypto)
- Check if cryptography is using native OpenSSL bindings
- Profile with `cProfile` if still slow

## Migration Guide

### From Regular JWT to Sliding Session

1. **Install dependencies:**
   ```bash
   pip install python-jose[cryptography]
   ```

2. **Add middleware:**
   ```python
   from app.middleware.session_refresh import SlidingSessionMiddleware
   from app.users import SECRET

   app.add_middleware(SlidingSessionMiddleware, secret_key=SECRET)
   ```

3. **Configure environment:**
   ```bash
   COOKIE_SECURE=TRUE
   SESSION_REFRESH_THRESHOLD=0.5
   ```

4. **Test:**
   - Verify cookies are being set
   - Monitor logs for refresh messages
   - Check performance metrics

### Rollback Plan

If issues occur, sliding sessions can be disabled without data loss:

1. **Remove middleware:**
   ```python
   # Comment out in app/app.py
   # app.add_middleware(SlidingSessionMiddleware, secret_key=SECRET)
   ```

2. **Restart service:**
   ```bash
   systemctl restart surfsense
   ```

3. **Result:** Sessions still work but won't auto-refresh (24h hard limit)

## Future Enhancements

### Possible Improvements

1. **Configurable Token Lifetime**
   - Currently hardcoded to 24 hours
   - Could be made configurable per user tier

2. **Multi-Device Session Management**
   - Track active sessions per user
   - Allow users to revoke individual sessions
   - Show "Active Sessions" in user settings

3. **Biometric Re-authentication**
   - Require fingerprint/Face ID for sensitive actions
   - Even if session is valid

4. **Adaptive Session Duration**
   - Longer sessions for low-risk users
   - Shorter sessions after failed login attempts

5. **Session Activity Log**
   - Track all session refreshes
   - Show user login history
   - Alert on suspicious activity

## References

- [FastAPI Users Documentation](https://fastapi-users.github.io/fastapi-users/)
- [JWT Best Practices (RFC 8725)](https://datatracker.ietf.org/doc/html/rfc8725)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [python-jose Documentation](https://python-jose.readthedocs.io/)

---

*Last updated: December 30, 2024*
