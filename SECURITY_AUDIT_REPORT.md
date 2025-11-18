# Security Audit Report - SurfSense

**Date:** November 18, 2025
**Auditor:** Claude Code Security Audit
**Branch:** claude/security-audit-session-fix-01WNkTGGrYURxe9JATA3gX6y

---

## Executive Summary

This security audit identified and addressed critical security vulnerabilities in the SurfSense application, including plaintext password exposure in version control and session management issues causing unexpected logouts.

### Key Findings

| Severity | Issue | Status |
|----------|-------|--------|
| **CRITICAL** | Plaintext password committed to version control | FIXED |
| **HIGH** | Session loss when clicking logo (token sync issue) | FIXED |
| **MEDIUM** | Token stored in localStorage (XSS vulnerability) | DOCUMENTED |
| **MEDIUM** | No token refresh mechanism | DOCUMENTED |

---

## Critical Issues Found and Fixed

### 1. Plaintext Password in Version Control

**Location:** `surfsense_backend/scripts/update_admin_user.py` (line 39 in commit 28f2076)

**Exposed Data:**
- Admin Email: `ojars@kapteinis.lv`
- Plaintext Password: `^&U0yXLK1ypZOwLDGFeLT35kCrblITYyAVdVmF3!iJ%kkY1Nl^IS!P`

**Impact:** Anyone with access to the repository history can view these credentials and potentially gain unauthorized access to the production system.

**Fix Applied:**
- Created secure version of `update_admin_user.py` that reads credentials from environment variables
- Removed all hardcoded credentials from the script
- Added validation and security warnings

**IMMEDIATE ACTION REQUIRED:**
1. **Change the production admin password immediately** - the exposed password must be considered compromised
2. Rotate any services that may share this password
3. Review access logs for suspicious activity
4. Consider whether users need to be notified

**How to change the password safely:**
```bash
cd /path/to/SurfSense/surfsense_backend
source venv/bin/activate

# Set credentials via environment variables (not command line args)
export ADMIN_EMAIL="your-admin-email"
export ADMIN_NEW_PASSWORD="generate-a-new-secure-password"

python scripts/update_admin_user.py
```

---

### 2. Session Loss When Clicking Logo

**Root Cause:** The `baseApiService` singleton reads the authentication token only once at module initialization. When users log in, the token is stored in localStorage but the service continues using the stale (empty) initial token.

**Flow that caused session loss:**
1. User loads app -> `baseApiService` initializes with empty token
2. User logs in -> Token stored in localStorage
3. User navigates around dashboard -> Works (some components create new service instances)
4. User clicks logo -> Navigates to "/"
5. User returns to dashboard -> API calls fail with 401 (stale empty token)
6. Silent logout redirects user to home page

**Files Fixed:**
- `surfsense_web/components/TokenHandler.tsx` - Now syncs token with baseApiService
- `surfsense_web/app/dashboard/layout.tsx` - Syncs token on dashboard load
- `surfsense_web/components/UserDropdown.tsx` - Clears token from baseApiService on logout
- `surfsense_web/hooks/use-user.ts` - Properly clears token on 401
- `surfsense_web/hooks/use-chats.ts` - Properly clears token on 401
- `surfsense_web/hooks/use-search-space.ts` - Properly clears token on 401
- `surfsense_web/lib/auth-errors.ts` - Added session_expired error message

---

## Additional Security Concerns (Not Fixed - Require Discussion)

### 1. Token Storage in localStorage (XSS Vulnerability)

**Current State:** JWT tokens are stored in `localStorage` using key `"surfsense_bearer_token"`

**Risk:** Any XSS attack can steal the token since it's accessible to JavaScript.

**Recommendation:**
- Store tokens in HttpOnly cookies (set by backend)
- Implement CSRF protection
- Use short-lived access tokens with refresh token rotation

### 2. No Token Refresh Mechanism

**Current State:** Tokens have a fixed lifetime (24 hours) with no refresh capability

**Risk:** Users must re-authenticate frequently, leading to poor UX and potential security issues (users choosing weak passwords for convenience)

**Recommendation:**
- Implement token refresh flow
- Use short-lived access tokens (15 minutes)
- Implement refresh token rotation
- Add proactive token refresh before expiration

### 3. Inconsistent Authentication Checks

**Current State:** Only `/dashboard/layout.tsx` checks for authentication on route mount

**Risk:** Other routes may be accessible without proper authentication

**Recommendation:**
- Implement middleware-based authentication
- Create route guards for all protected routes
- Use Next.js middleware properly (currently disabled)

### 4. Silent Session Expiration

**Current State:** Users are silently redirected to home page when session expires

**Risk:** Users lose context and may not understand why they were logged out

**Recommendation:**
- Show clear notification when session expires
- Preserve user's location to redirect back after re-authentication
- Consider showing modal for re-authentication without full redirect

---

## Files Modified

| File | Change Type | Description |
|------|-------------|-------------|
| `surfsense_backend/scripts/update_admin_user.py` | Created | Secure admin script using env vars |
| `surfsense_web/components/TokenHandler.tsx` | Modified | Sync token with baseApiService |
| `surfsense_web/app/dashboard/layout.tsx` | Modified | Sync token on dashboard mount |
| `surfsense_web/components/UserDropdown.tsx` | Modified | Clear baseApiService token on logout |
| `surfsense_web/hooks/use-user.ts` | Modified | Proper 401 handling with token sync |
| `surfsense_web/hooks/use-chats.ts` | Modified | Proper 401 handling with token sync |
| `surfsense_web/hooks/use-search-space.ts` | Modified | Proper 401 handling with token sync |
| `surfsense_web/lib/auth-errors.ts` | Modified | Added session_expired error |

---

## Deployment Recommendations

### Before Deploying to Production

1. **Change the admin password** - Use the new secure script
2. **Review all environment variables** - Ensure no secrets in code
3. **Test session persistence** - Verify logo click doesn't cause logout
4. **Check git history** - Consider rewriting history to remove exposed password

### Post-Deployment

1. **Monitor access logs** - Look for unauthorized access attempts
2. **Set up alerts** - For failed login attempts and unusual activity
3. **Plan security improvements** - Address the documented concerns above

---

## Future Security Improvements

### Short-term (Next Sprint)
- [ ] Implement proper token refresh mechanism
- [ ] Add session expiration notifications
- [ ] Set up pre-commit hooks for secret detection (already configured in `.pre-commit-config.yaml`)

### Medium-term (Next Quarter)
- [ ] Migrate from localStorage to HttpOnly cookies
- [ ] Implement CSRF protection
- [ ] Add rate limiting for authentication endpoints
- [ ] Implement account lockout after failed attempts

### Long-term
- [ ] Add multi-factor authentication (MFA)
- [ ] Implement security audit logging
- [ ] Add intrusion detection systems
- [ ] Regular security penetration testing

---

## Git History Cleanup (Optional but Recommended)

The exposed password exists in git history. To fully remediate:

```bash
# WARNING: This rewrites git history and requires force push
# Coordinate with all team members before doing this

# Option 1: Use BFG Repo-Cleaner
bfg --delete-files update_admin_user.py --no-blob-protection

# Option 2: Use git filter-repo
git filter-repo --path surfsense_backend/scripts/update_admin_user.py --invert-paths

# After cleanup, force push to all remotes
git push --force --all
git push --force --tags
```

**Note:** Force pushing rewrites history and affects all collaborators. This should be done carefully and communicated to the team.

---

## Conclusion

The critical security issues have been addressed in this audit. The exposed password must be changed immediately on all production systems. The session loss bug has been fixed by properly syncing tokens with the baseApiService singleton.

Additional security improvements are recommended but not urgent - they should be prioritized based on risk assessment and available resources.

---

*This report was generated as part of a security audit. All findings should be reviewed by the security team before deployment.*
