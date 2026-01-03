# SurfSense Security Fixes - Implementation Guide

**Date:** December 1, 2025
**Audit Grade:** B+ (82/100) → Target: A (95+/100)

This document provides step-by-step instructions to fix all security issues identified in the comprehensive security audit.

---

## Table of Contents

1. [Critical Fixes (Week 1)](#critical-fixes-week-1)
2. [High Priority Fixes (Week 2)](#high-priority-fixes-week-2)
3. [Medium Priority Fixes (Week 3-4)](#medium-priority-fixes-week-3-4)
4. [Low Priority Fixes (Ongoing)](#low-priority-fixes-ongoing)
5. [Testing & Verification](#testing--verification)
6. [Deployment Checklist](#deployment-checklist)

---

## Critical Fixes (Week 1)

### 1. Update Vulnerable Dependencies

#### Backend Dependencies

**Issue:** urllib3 has 2 CVEs (CVE-2025-50181, CVE-2025-50182)
**Current Version:** 2.3.0
**Required Version:** ≥2.5.0

```bash
# Connect to VPS
ssh -i ~/.ssh/your_private_key user@your-vps-ip

# Navigate to backend
cd /opt/SurfSense/surfsense_backend

# Activate virtual environment
source venv/bin/activate

# Upgrade urllib3
pip install --upgrade "urllib3>=2.5.0"

# Verify upgrade
pip show urllib3

# Restart backend service
systemctl restart surfsense
systemctl restart surfsense-celery

# Check logs for errors
journalctl -u surfsense -n 50
```

#### Frontend Dependencies

**Issue:** 9 vulnerable packages identified
**Priority Order:** HIGH → MODERATE → LOW

```bash
# Connect to VPS
ssh -i ~/.ssh/your_private_key user@your-vps-ip

# Navigate to frontend
cd /opt/SurfSense/surfsense_web

# Update HIGH priority (tar-fs)
pnpm update tar-fs@^2.1.4

# Update MODERATE priority
pnpm update @babel/runtime@^7.28.4
pnpm update js-yaml@^4.1.1
pnpm update brace-expansion@^2.0.2

# Run audit to check remaining vulnerabilities
pnpm audit

# Rebuild frontend
pnpm build

# Restart frontend service
systemctl restart surfsense-frontend

# Verify frontend is running
curl http://127.0.0.1:3000/api/health
```

**Manual Review Required:**
- `esbuild` (0.18.20 → 0.25.0+): Deep dependency via `drizzle-kit`
- `prismjs` (1.27.0 → 1.30.0+): Via `react-syntax-highlighter`
- `jsondiffpatch` (0.6.0 → 0.7.2+): Via `ai` package

```bash
# Check if these can be updated
pnpm why esbuild
pnpm why prismjs
pnpm why jsondiffpatch

# Update parent packages if possible
pnpm update drizzle-kit@latest
pnpm update react-syntax-highlighter@latest
```

**For `ai` package (major version upgrade):**
```bash
# Review breaking changes first
# https://github.com/vercel/ai/releases

# Backup current code
git checkout -b backup/before-ai-upgrade

# Upgrade (4.3.19 → 5.0.52+)
pnpm update ai@^5.0.52

# Test chat functionality thoroughly
# Revert if breaking changes affect functionality
```

---

### 2. Add Security Headers

**Issue:** Missing CSP, HSTS, X-Frame-Options, X-Content-Type-Options
**Location:** `surfsense_web/next.config.mjs`

**Step 1: Edit next.config.mjs**

```bash
# On VPS or local machine
cd /opt/SurfSense/surfsense_web
nano next.config.mjs
```

**Step 2: Add security headers configuration**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // ... existing config ...

  async headers() {
    return [
      {
        // Apply security headers to all routes
        source: '/:path*',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block',
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=31536000; includeSubDomains',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval'", // Note: unsafe-eval needed for Next.js dev
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: https:",
              "font-src 'self' data:",
              "connect-src 'self' https://www.googleapis.com",
              "frame-ancestors 'none'",
            ].join('; '),
          },
        ],
      },
    ];
  },
};

export default nextConfig;
```

**Step 3: Build and deploy**

```bash
pnpm build
systemctl restart surfsense-frontend
```

**Step 4: Verify headers**

```bash
# Check headers are present
curl -I https://your-domain.com

# Should see:
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# Strict-Transport-Security: max-age=31536000; includeSubDomains
# Content-Security-Policy: ...
```

**Note:** If CSP breaks functionality:
1. Check browser console for CSP violations
2. Adjust CSP directives as needed
3. Add specific domains to `connect-src` for external APIs
4. Use `report-uri` directive to monitor violations without blocking

---

### 3. Migrate Auth Tokens to HttpOnly Cookies

**Issue:** Tokens in localStorage vulnerable to XSS attacks
**Current:** `localStorage.getItem('token')`
**Target:** HttpOnly cookies with Secure and SameSite flags

#### Backend Changes

**Step 1: Update auth routes to set cookies**

```bash
cd /opt/SurfSense/surfsense_backend
nano app/routes/auth_routes.py
```

**Add cookie setting after login:**

```python
from fastapi import Response
from fastapi.responses import JSONResponse

# In login endpoint (around line 85)
@router.post("/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    # ... existing authentication logic ...

    access_token = create_access_token(user_dict)

    # Create response with cookie
    response = JSONResponse(content={
        "user": user_dict,
        "message": "Login successful"
    })

    # Set HttpOnly cookie
    response.set_cookie(
        key="auth_token",
        value=access_token,
        httponly=True,
        secure=True,  # Only send over HTTPS
        samesite="strict",  # CSRF protection
        max_age=7 * 24 * 60 * 60,  # 7 days
        path="/",
    )

    return response

# Similar changes for OAuth login endpoint
@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    # ... existing OAuth logic ...

    access_token = create_access_token(user_dict)

    # Set cookie and redirect to dashboard
    response = RedirectResponse(url="/dashboard")
    response.set_cookie(
        key="auth_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )

    return response
```

**Step 2: Update auth dependency to read from cookie**

```bash
nano app/core/auth.py
```

```python
from fastapi import Cookie, HTTPException, status

async def get_current_user(
    auth_token: str = Cookie(None, alias="auth_token"),  # Read from cookie first
    authorization: str = Header(None),  # Fallback to header for API clients
    db: AsyncSession = Depends(get_db),
):
    # Try cookie first
    token = auth_token

    # Fallback to Authorization header
    if not token and authorization:
        if authorization.startswith("Bearer "):
            token = authorization.replace("Bearer ", "")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    # ... rest of token validation logic ...
```

**Step 3: Add logout endpoint to clear cookie**

```python
@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key="auth_token",
        path="/",
        httponly=True,
        secure=True,
        samesite="strict",
    )
    return {"message": "Logged out successfully"}
```

#### Frontend Changes

**Step 1: Remove localStorage token usage**

```bash
cd /opt/SurfSense/surfsense_web
nano lib/api.ts
```

**Update API client to use cookies:**

```typescript
// Remove this:
// const token = localStorage.getItem('token');

// Update fetch wrapper to rely on cookies:
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    credentials: 'include', // Important: send cookies with request
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
      // Remove Authorization header - cookie will be sent automatically
    },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }

  return response.json();
}
```

**Step 2: Update login page**

```bash
nano app/(auth)/login/page.tsx
```

```typescript
// Remove localStorage.setItem('token', response.token)

const handleLogin = async (values: LoginFormValues) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      credentials: 'include', // Important
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values),
    });

    if (response.ok) {
      const data = await response.json();
      // Cookie is automatically set by browser
      // No need to manually store token
      router.push('/dashboard');
    }
  } catch (error) {
    console.error('Login failed:', error);
  }
};
```

**Step 3: Update logout functionality**

```typescript
const handleLogout = async () => {
  await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  });

  // Cookie is automatically cleared by browser
  router.push('/login');
};
```

**Step 4: Remove all localStorage references**

```bash
# Search for localStorage usage
grep -r "localStorage" app/ lib/

# Remove or replace each instance:
# - Remove localStorage.setItem('token', ...)
# - Remove localStorage.getItem('token')
# - Remove localStorage.removeItem('token')
```

**Step 5: Update Next.js configuration for cookies**

```bash
nano next.config.mjs
```

```javascript
const nextConfig = {
  // ... existing config ...

  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*', // Proxy to backend
      },
    ];
  },
};
```

#### Deployment

```bash
# Backend
cd /opt/SurfSense/surfsense_backend
systemctl restart surfsense

# Frontend
cd /opt/SurfSense/surfsense_web
pnpm build
systemctl restart surfsense-frontend
```

#### Testing

1. **Test login:**
   - Open browser DevTools → Application → Cookies
   - Login and verify `auth_token` cookie is set
   - Verify cookie has `HttpOnly`, `Secure`, `SameSite=Strict` flags

2. **Test authenticated requests:**
   - Navigate to dashboard
   - Check Network tab - cookies should be sent automatically
   - Verify no `Authorization` header in requests

3. **Test logout:**
   - Logout and verify cookie is removed
   - Try accessing dashboard - should redirect to login

4. **Test security:**
   - Open browser console
   - Try `document.cookie` - should NOT show `auth_token` (HttpOnly protection)
   - Verify token cannot be accessed by JavaScript

---

## High Priority Fixes (Week 2)

### 4. Implement CSRF Protection

**Issue:** No CSRF tokens on state-changing requests
**Affected:** All POST, PUT, DELETE, PATCH requests

#### Backend Implementation

**Step 1: Install CSRF library**

```bash
cd /opt/SurfSense/surfsense_backend
source venv/bin/activate
pip install fastapi-csrf-protect
```

**Step 2: Configure CSRF protection**

```bash
nano app/app.py
```

```python
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from pydantic import BaseModel

# CSRF settings
class CsrfSettings(BaseModel):
    secret_key: str = os.getenv("CSRF_SECRET_KEY")  # REQUIRED: Set in environment or secrets
    cookie_name: str = "csrf_token"
    cookie_samesite: str = "strict"
    cookie_secure: bool = True
    cookie_httponly: bool = False  # Must be False so JS can read it
    header_name: str = "X-CSRF-Token"

@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()

app = FastAPI(title="SurfSense API")

# Add CSRF error handler
@app.exception_handler(CsrfProtectError)
def csrf_protect_exception_handler(request: Request, exc: CsrfProtectError):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": "CSRF token validation failed"}
    )
```

**Step 3: Add CSRF token endpoint**

```bash
nano app/routes/auth_routes.py
```

```python
from fastapi_csrf_protect import CsrfProtect

@router.get("/csrf-token")
async def get_csrf_token(csrf_protect: CsrfProtect = Depends()):
    """Get CSRF token for the current session"""
    response = JSONResponse(content={"message": "CSRF token set"})
    csrf_protect.set_csrf_cookie(response)
    return response
```

**Step 4: Protect state-changing endpoints**

```python
from fastapi_csrf_protect import CsrfProtect

# Add csrf_protect dependency to POST/PUT/DELETE endpoints
@router.post("/documents")
async def create_document(
    request: Request,
    document: DocumentCreate,
    csrf_protect: CsrfProtect = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate CSRF token
    await csrf_protect.validate_csrf(request)

    # ... rest of endpoint logic ...
```

**Bulk protect all routes in a file:**

```python
# At the top of route file
from fastapi import Depends
from fastapi_csrf_protect import CsrfProtect

def csrf_token_dependency(csrf_protect: CsrfProtect = Depends()):
    """Shared CSRF validation dependency"""
    return csrf_protect

# Use in router
router = APIRouter(
    dependencies=[Depends(csrf_token_dependency)]  # Protect all routes
)
```

#### Frontend Implementation

**Step 1: Fetch CSRF token on app load**

```bash
cd /opt/SurfSense/surfsense_web
nano app/layout.tsx
```

```typescript
'use client';

import { useEffect } from 'react';

export default function RootLayout({ children }) {
  useEffect(() => {
    // Fetch CSRF token when app loads
    fetch('/api/v1/auth/csrf-token', {
      credentials: 'include',
    });
  }, []);

  return (
    <html>
      <body>{children}</body>
    </html>
  );
}
```

**Step 2: Create CSRF helper function**

```bash
nano lib/csrf.ts
```

```typescript
/**
 * Get CSRF token from cookie
 */
export function getCsrfToken(): string | null {
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === 'csrf_token') {
      return decodeURIComponent(value);
    }
  }
  return null;
}

/**
 * Fetch with CSRF token
 */
export async function fetchWithCsrf(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const csrfToken = getCsrfToken();

  return fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      ...options.headers,
      'X-CSRF-Token': csrfToken || '',
    },
  });
}
```

**Step 3: Update API client to include CSRF token**

```bash
nano lib/api.ts
```

```typescript
import { getCsrfToken } from './csrf';

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const csrfToken = getCsrfToken();

  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken || '',
      ...options.headers,
    },
  });

  if (!response.ok) {
    if (response.status === 403) {
      // CSRF token expired or invalid
      // Refresh token and retry
      await fetch('/api/v1/auth/csrf-token', { credentials: 'include' });
      throw new Error('CSRF token invalid, please retry');
    }
    throw new Error(`API error: ${response.statusText}`);
  }

  return response.json();
}
```

**Step 4: Update all form submissions**

```typescript
// Example: Document upload form
const handleSubmit = async (formData: FormData) => {
  const csrfToken = getCsrfToken();

  await fetch('/api/v1/documents', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'X-CSRF-Token': csrfToken || '',
    },
    body: formData,
  });
};
```

#### Testing CSRF Protection

```bash
# Test 1: CSRF token is set
curl -I http://127.0.0.1:8000/api/v1/auth/csrf-token
# Should see Set-Cookie: csrf_token=...

# Test 2: Request without CSRF token fails
curl -X POST http://127.0.0.1:8000/api/v1/documents \
  -H "Cookie: auth_token=..." \
  -H "Content-Type: application/json" \
  -d '{}'
# Should return 403 Forbidden

# Test 3: Request with valid CSRF token succeeds
curl -X POST http://127.0.0.1:8000/api/v1/documents \
  -H "Cookie: auth_token=...; csrf_token=..." \
  -H "X-CSRF-Token: <csrf_token_value>" \
  -H "Content-Type: application/json" \
  -d '{}'
# Should succeed
```

---

### 5. Add OAuth CSRF Protection

**Issue:** Google OAuth callback doesn't validate state parameter
**Location:** `surfsense_backend/app/routes/auth_routes.py:178-200`

**Step 1: Generate and store state parameter**

```bash
nano app/routes/auth_routes.py
```

```python
import secrets
from fastapi import Response, Cookie

@router.get("/google/login")
async def google_login(response: Response):
    # Generate random state
    state = secrets.token_urlsafe(32)

    # Store state in cookie (will be verified on callback)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=True,
        samesite="lax",  # Lax allows cookie on redirect
        max_age=600,  # 10 minutes
        path="/",
    )

    # Build Google OAuth URL with state
    google_oauth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"state={state}"  # Include state in OAuth request
    )

    return RedirectResponse(url=google_oauth_url)
```

**Step 2: Validate state on callback**

```python
@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),  # State from OAuth provider
    oauth_state: str = Cookie(None),  # State from our cookie
    db: AsyncSession = Depends(get_db),
):
    # Validate state parameter
    if not oauth_state or state != oauth_state:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OAuth state parameter - possible CSRF attack"
        )

    # Clear the state cookie
    response = None  # Will create response later

    try:
        # ... existing OAuth token exchange logic ...

        # Create success response
        response = RedirectResponse(url="/dashboard")

        # Set auth cookie
        response.set_cookie(
            key="auth_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=7 * 24 * 60 * 60,
        )

        # Clear OAuth state cookie
        response.delete_cookie(
            key="oauth_state",
            path="/",
        )

        return response

    except Exception as e:
        # Clear state cookie even on error
        error_response = RedirectResponse(url="/login?error=oauth_failed")
        error_response.delete_cookie(key="oauth_state", path="/")
        return error_response
```

**Step 3: Test OAuth CSRF protection**

```bash
# Manual test:
# 1. Visit http://localhost:8000/api/v1/auth/google/login
# 2. Check cookie "oauth_state" is set
# 3. Complete OAuth flow
# 4. Verify callback validates state
# 5. Try replaying callback with different state - should fail
```

---

### 6. Encrypt API Keys in Database

**Issue:** API keys stored in plaintext in database
**Location:** `surfsense_backend/app/models/user.py:45`

**Step 1: Install cryptography library** (already installed)

```bash
cd /opt/SurfSense/surfsense_backend
source venv/bin/activate
pip show cryptography
```

**Step 2: Create encryption service**

```bash
nano app/services/encryption_service.py
```

```python
"""
Encryption service for sensitive data like API keys
"""
from cryptography.fernet import Fernet
from typing import Optional
import os
import base64
from app.core.config import settings

class EncryptionService:
    def __init__(self):
        # Get encryption key from environment or secrets
        encryption_key = os.getenv("ENCRYPTION_KEY")

        if not encryption_key:
            raise ValueError("ENCRYPTION_KEY not set in environment")

        # Ensure key is properly formatted
        if not encryption_key.endswith("="):
            encryption_key = base64.urlsafe_b64encode(encryption_key.encode()).decode()

        self.cipher = Fernet(encryption_key.encode())

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext and return base64 encoded ciphertext"""
        if not plaintext:
            return ""

        encrypted = self.cipher.encrypt(plaintext.encode())
        return encrypted.decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext and return plaintext"""
        if not ciphertext:
            return ""

        decrypted = self.cipher.decrypt(ciphertext.encode())
        return decrypted.decode()

    def encrypt_dict(self, data: dict) -> dict:
        """Encrypt all string values in a dictionary"""
        encrypted = {}
        for key, value in data.items():
            if isinstance(value, str):
                encrypted[key] = self.encrypt(value)
            else:
                encrypted[key] = value
        return encrypted

    def decrypt_dict(self, data: dict) -> dict:
        """Decrypt all string values in a dictionary"""
        decrypted = {}
        for key, value in data.items():
            if isinstance(value, str):
                try:
                    decrypted[key] = self.decrypt(value)
                except:
                    # If decryption fails, assume it's not encrypted
                    decrypted[key] = value
            else:
                decrypted[key] = value
        return decrypted

# Singleton instance
encryption_service = EncryptionService()
```

**Step 3: Generate encryption key**

```bash
# Generate a new Fernet key
python3 << 'EOF'
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(f"Add this to your secrets.enc.yaml:")
print(f"encryption_key: {key.decode()}")
EOF
```

**Step 4: Add encryption key to secrets**

```bash
cd /opt/SurfSense/surfsense_backend

# Edit secrets (will be encrypted by SOPS)
python scripts/sops_mcp_server.py set encryption.key "<generated_key_from_above>"
```

**Step 5: Update User model to use encryption**

```bash
nano app/models/user.py
```

```python
from sqlalchemy import Column, JSON
from sqlalchemy.ext.hybrid import hybrid_property
from app.services.encryption_service import encryption_service

class User(Base):
    # ... existing fields ...

    # Store encrypted API keys
    _api_keys = Column("api_keys", JSON, nullable=True)

    @hybrid_property
    def api_keys(self):
        """Decrypt API keys when accessed"""
        if not self._api_keys:
            return {}
        return encryption_service.decrypt_dict(self._api_keys)

    @api_keys.setter
    def api_keys(self, value: dict):
        """Encrypt API keys when set"""
        if not value:
            self._api_keys = {}
        else:
            self._api_keys = encryption_service.encrypt_dict(value)
```

**Step 6: Create migration to encrypt existing keys**

```bash
# Create new migration
alembic revision -m "encrypt_api_keys"

# Edit migration file
nano alembic/versions/41_encrypt_api_keys.py
```

```python
"""encrypt_api_keys

Revision ID: 41
Revises: 40
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.services.encryption_service import encryption_service

revision = '41'
down_revision = '40'

def upgrade():
    # Get database connection
    bind = op.get_bind()
    session = Session(bind=bind)

    # Get all users with API keys
    users = session.execute(
        sa.text("SELECT id, api_keys FROM users WHERE api_keys IS NOT NULL")
    ).fetchall()

    # Encrypt each user's API keys
    for user_id, api_keys in users:
        if api_keys:
            encrypted_keys = encryption_service.encrypt_dict(api_keys)
            session.execute(
                sa.text("UPDATE users SET api_keys = :keys WHERE id = :id"),
                {"keys": encrypted_keys, "id": user_id}
            )

    session.commit()

def downgrade():
    # Get database connection
    bind = op.get_bind()
    session = Session(bind=bind)

    # Get all users with API keys
    users = session.execute(
        sa.text("SELECT id, api_keys FROM users WHERE api_keys IS NOT NULL")
    ).fetchall()

    # Decrypt each user's API keys
    for user_id, api_keys in users:
        if api_keys:
            decrypted_keys = encryption_service.decrypt_dict(api_keys)
            session.execute(
                sa.text("UPDATE users SET api_keys = :keys WHERE id = :id"),
                {"keys": decrypted_keys, "id": user_id}
            )

    session.commit()
```

**Step 7: Run migration**

```bash
alembic upgrade head
```

**Step 8: Update connector service to use encrypted keys**

```bash
nano app/services/connector_service.py
```

```python
# API keys are automatically decrypted by the User model property
# No changes needed - just access user.api_keys as before

async def fetch_github_data(user: User, search_space_id: int):
    # API keys are automatically decrypted
    github_token = user.api_keys.get("github_token")

    # Use token as normal
    # ...
```

**Step 9: Test encryption**

```python
# Test script
import asyncio
import os

from app.services.encryption_service import encryption_service

async def test_encryption():
    # Test string encryption
    plaintext = "my-secret-api-key-12345"
    encrypted = encryption_service.encrypt(plaintext)
    decrypted = encryption_service.decrypt(encrypted)

    print(f"Original:  {plaintext}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")
    assert plaintext == decrypted

    # Test dict encryption (use real tokens from environment in production)
    api_keys = {
        "github_token": os.getenv("GITHUB_TOKEN", "your_github_token_here"),
        "google_api_key": os.getenv("GOOGLE_API_KEY", "your_google_api_key_here")
    }
    encrypted_dict = encryption_service.encrypt_dict(api_keys)
    decrypted_dict = encryption_service.decrypt_dict(encrypted_dict)

    print(f"\nOriginal dict:  {api_keys}")
    print(f"Encrypted dict: {encrypted_dict}")
    print(f"Decrypted dict: {decrypted_dict}")
    assert api_keys == decrypted_dict

asyncio.run(test_encryption())
```

---

## Medium Priority Fixes (Week 3-4)

### 7. Implement JWT Refresh Tokens

**Issue:** Long-lived access tokens increase security risk
**Current:** Single access token (7 days)
**Target:** Short-lived access token (15min) + refresh token (7 days)

**Step 1: Update auth service**

```bash
nano app/services/auth_service.py
```

```python
from datetime import datetime, timedelta
from typing import Tuple

# Token expiration times
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_token_pair(user_dict: dict) -> Tuple[str, str]:
    """Create both access and refresh tokens"""

    # Access token (short-lived)
    access_token_data = user_dict.copy()
    access_token_data.update({
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access"
    })
    access_token = jwt.encode(access_token_data, SECRET_KEY, algorithm=ALGORITHM)

    # Refresh token (long-lived, only contains user ID)
    refresh_token_data = {
        "sub": str(user_dict["id"]),
        "exp": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh"
    }
    refresh_token = jwt.encode(refresh_token_data, SECRET_KEY, algorithm=ALGORITHM)

    return access_token, refresh_token
```

**Step 2: Update login endpoint**

```python
@router.post("/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    # ... authentication logic ...

    # Create token pair
    access_token, refresh_token = create_token_pair(user_dict)

    response = JSONResponse(content={
        "user": user_dict,
        "message": "Login successful"
    })

    # Set both cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )

    return response
```

**Step 3: Add refresh endpoint**

```python
@router.post("/refresh")
async def refresh_token(
    refresh_token: str = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing"
        )

    try:
        # Decode refresh token
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])

        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        # Get user from database
        user_id = payload.get("sub")
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        # Create new token pair
        user_dict = {
            "id": user.id,
            "email": user.email,
            "is_superuser": user.is_superuser,
        }
        new_access_token, new_refresh_token = create_token_pair(user_dict)

        response = JSONResponse(content={"message": "Tokens refreshed"})

        # Set new cookies
        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        )

        return response

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
```

**Step 4: Update auth dependency**

```python
async def get_current_user(
    access_token: str = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])

        # Verify it's an access token
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        # ... rest of user validation ...

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expired",
            headers={"X-Token-Expired": "true"}  # Signal to frontend
        )
```

**Step 5: Frontend - Auto refresh on expiry**

```typescript
// lib/api.ts
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  let response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    credentials: 'include',
  });

  // If access token expired, try to refresh
  if (response.status === 401) {
    const tokenExpired = response.headers.get('X-Token-Expired');

    if (tokenExpired === 'true') {
      // Try to refresh token
      const refreshResponse = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      });

      if (refreshResponse.ok) {
        // Retry original request
        response = await fetch(`${API_BASE_URL}${endpoint}`, {
          ...options,
          credentials: 'include',
        });
      } else {
        // Refresh failed, redirect to login
        window.location.href = '/login';
        throw new Error('Session expired');
      }
    }
  }

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }

  return response.json();
}
```

---

### 8. Add Frontend Rate Limiting

**Issue:** No client-side rate limiting
**Target:** Prevent brute force attacks on login form

**Step 1: Create rate limiting middleware**

```bash
cd /opt/SurfSense/surfsense_web
nano middleware.ts
```

```typescript
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Simple in-memory rate limiter
// For production, use Redis
const rateLimitMap = new Map<string, { count: number; resetTime: number }>();

// Rate limit configuration
const RATE_LIMITS = {
  '/api/v1/auth/login': {
    maxRequests: 5,
    windowMs: 60 * 1000, // 1 minute
  },
  '/api/v1/auth/register': {
    maxRequests: 3,
    windowMs: 60 * 1000,
  },
};

function getRateLimitKey(ip: string, pathname: string): string {
  return `${ip}:${pathname}`;
}

function isRateLimited(key: string, config: { maxRequests: number; windowMs: number }): boolean {
  const now = Date.now();
  const record = rateLimitMap.get(key);

  if (!record || now > record.resetTime) {
    // New window
    rateLimitMap.set(key, {
      count: 1,
      resetTime: now + config.windowMs,
    });
    return false;
  }

  if (record.count >= config.maxRequests) {
    return true;
  }

  // Increment count
  record.count++;
  return false;
}

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  // Check if this route should be rate limited
  const rateLimitConfig = RATE_LIMITS[pathname];

  if (rateLimitConfig) {
    // Get client IP
    const ip = request.ip || request.headers.get('x-forwarded-for') || 'unknown';
    const key = getRateLimitKey(ip, pathname);

    if (isRateLimited(key, rateLimitConfig)) {
      return new NextResponse(
        JSON.stringify({ error: 'Too many requests. Please try again later.' }),
        {
          status: 429,
          headers: {
            'Content-Type': 'application/json',
            'Retry-After': String(Math.ceil(rateLimitConfig.windowMs / 1000)),
          },
        }
      );
    }
  }

  return NextResponse.next();
}

// Configure which paths the middleware runs on
export const config = {
  matcher: [
    '/api/v1/auth/login',
    '/api/v1/auth/register',
  ],
};
```

**Step 2: Add rate limit error handling to login form**

```typescript
// app/(auth)/login/page.tsx
const handleLogin = async (values: LoginFormValues) => {
  try {
    const response = await fetch('/api/v1/auth/login', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values),
    });

    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After');
      toast({
        title: 'Too many attempts',
        description: `Please try again in ${retryAfter} seconds`,
        variant: 'destructive',
      });
      return;
    }

    // ... rest of login handling ...
  } catch (error) {
    console.error('Login failed:', error);
  }
};
```

---

### 9. Test Coverage Improvements

**Issue:** Current coverage ~20-25%, target 75%+

#### Add Authentication Flow Tests

```bash
cd /opt/SurfSense/surfsense_backend
nano tests/test_auth_flows.py
```

```python
import os

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_2fa_login_flow(client: AsyncClient, db: AsyncSession):
    """Test complete 2FA login flow"""
    # 1. Register user
    response = await client.post("/api/v1/auth/register", json={
        "email": "test2fa@example.com",
        "password": os.getenv("TEST_PASSWORD", "changeme"),  # Use env var in production tests
    })
    assert response.status_code == 201

    # 2. Enable 2FA
    response = await client.post("/api/v1/auth/2fa/setup")
    assert response.status_code == 200
    totp_secret = response.json()["secret"]

    # 3. Verify 2FA code
    from pyotp import TOTP
    totp = TOTP(totp_secret)
    code = totp.now()

    response = await client.post("/api/v1/auth/2fa/verify", json={
        "code": code
    })
    assert response.status_code == 200

    # 4. Login with 2FA
    response = await client.post("/api/v1/auth/login", data={
        "username": "test2fa@example.com",
        "password": os.getenv("TEST_PASSWORD", "changeme"),  # Use env var in production tests
        "totp_code": totp.now(),
    })
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_oauth_callback_with_invalid_state(client: AsyncClient):
    """Test OAuth callback rejects invalid state"""
    # Attempt callback with mismatched state
    response = await client.get(
        "/api/v1/auth/google/callback",
        params={"code": "test_code", "state": "invalid_state"},
        cookies={"oauth_state": "valid_state"}
    )
    assert response.status_code == 401
    assert "Invalid OAuth state" in response.json()["detail"]

@pytest.mark.asyncio
async def test_refresh_token_flow(client: AsyncClient):
    """Test token refresh flow"""
    # Login
    response = await client.post("/api/v1/auth/login", data={
        "username": "test@example.com",
        "password": os.getenv("TEST_PASSWORD", "changeme"),  # Use env var in production tests
    })
    assert response.status_code == 200

    # Extract refresh token from cookie
    cookies = response.cookies

    # Wait for access token to expire (or mock expiration)
    # ...

    # Refresh token
    response = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": cookies["refresh_token"]}
    )
    assert response.status_code == 200
```

#### Add API Endpoint Tests

```bash
nano tests/test_api_endpoints.py
```

```python
@pytest.mark.asyncio
async def test_logs_routes(client: AsyncClient, auth_headers: dict):
    """Test logs API endpoints"""
    # Get logs
    response = await client.get(
        "/api/v1/logs",
        headers=auth_headers
    )
    assert response.status_code == 200

    # Retry task
    response = await client.post(
        "/api/v1/logs/1/retry",
        headers=auth_headers
    )
    assert response.status_code in [200, 404]  # 404 if log doesn't exist

    # Dismiss log
    response = await client.post(
        "/api/v1/logs/1/dismiss",
        headers=auth_headers
    )
    assert response.status_code in [200, 404]

@pytest.mark.asyncio
async def test_jsonata_routes(client: AsyncClient, auth_headers: dict):
    """Test JSONata transformation endpoints"""
    response = await client.post(
        "/api/v1/jsonata/transform",
        headers=auth_headers,
        json={
            "template": "{ \"title\": title }",
            "data": {"title": "Test", "body": "Content"}
        }
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Test"

@pytest.mark.asyncio
async def test_connectors_routes(client: AsyncClient, auth_headers: dict):
    """Test connector API endpoints"""
    # Get connectors
    response = await client.get(
        "/api/v1/connectors",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert "github" in response.json()
```

#### Run Tests with Coverage

```bash
# Install coverage tools
pip install pytest-cov

# Run tests with coverage report
pytest --cov=app --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html

# Aim for 75%+ coverage
```

---

## Low Priority Fixes (Ongoing)

### 10. Switch Celery Serialization to JSON

**Issue:** Celery uses pickle (deserialization risk)
**Location:** `surfsense_backend/app/celery_app.py`

```bash
nano app/celery_app.py
```

```python
from celery import Celery

celery_app = Celery(
    "surfsense",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Use JSON serialization instead of pickle
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    # ... other config ...
)
```

**Note:** Ensure all task parameters are JSON-serializable. Update tasks that pass complex objects to use primitive types instead.

---

### 11. Remove Sensitive Logging in Extension

**Issue:** console.log may expose sensitive data
**Location:** Throughout `surfsense_browser_extension/`

```bash
cd /opt/SurfSense/surfsense_browser_extension

# Search for console.log
grep -r "console.log" .

# Replace with conditional logging
nano background/messages/savedata.ts
```

```typescript
// Add debug flag
const DEBUG = process.env.NODE_ENV === 'development';

// Replace console.log with:
if (DEBUG) {
  console.log('Debug info:', data);
}

// Or create logger utility
// lib/logger.ts
export const logger = {
  debug: (...args: any[]) => {
    if (process.env.NODE_ENV === 'development') {
      console.log('[DEBUG]', ...args);
    }
  },
  info: (...args: any[]) => {
    console.info('[INFO]', ...args);
  },
  error: (...args: any[]) => {
    console.error('[ERROR]', ...args);
  },
};

// Usage
import { logger } from '~/lib/logger';
logger.debug('Sensitive data:', apiKey); // Only in dev
logger.error('Error occurred:', error); // Always logged
```

---

### 12. Improve TypeScript Type Safety

**Issue:** 206 instances of `any` type
**Target:** Replace with proper types

```bash
cd /opt/SurfSense/surfsense_web

# Find all 'any' usage
grep -r ": any" app/ lib/ components/

# Example fixes:
```

**Before:**
```typescript
const data: any = await response.json();
const items: any[] = data.items;
```

**After:**
```typescript
interface ApiResponse {
  items: Item[];
  total: number;
}

interface Item {
  id: number;
  title: string;
  content: string;
}

const data: ApiResponse = await response.json();
const items: Item[] = data.items;
```

**Create type definitions:**

```bash
nano types/api.ts
```

```typescript
// API response types
export interface User {
  id: number;
  email: string;
  is_superuser: boolean;
}

export interface Document {
  id: number;
  title: string;
  content: string;
  created_at: string;
  search_space_id: number;
}

export interface SearchSpace {
  id: number;
  name: string;
  description: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

// Use in components
import { Document, PaginatedResponse } from '~/types/api';

const fetchDocuments = async (): Promise<PaginatedResponse<Document>> => {
  const response = await fetch('/api/v1/documents');
  return response.json();
};
```

---

## Testing & Verification

### Security Testing Checklist

After implementing fixes, verify each item:

#### 1. Dependencies
```bash
# Backend
cd surfsense_backend
pip list | grep urllib3  # Should be 2.5.0+
safety check  # Should show 0 vulnerabilities

# Frontend
cd surfsense_web
pnpm audit  # Should show 0-3 low severity issues (acceptable)
```

#### 2. Security Headers
```bash
curl -I https://your-domain.com | grep -E "(X-Frame|X-Content|Strict-Transport|Content-Security)"

# Should see:
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# Strict-Transport-Security: max-age=31536000; includeSubDomains
# Content-Security-Policy: ...
```

#### 3. HttpOnly Cookies
```bash
# Login and check cookies
curl -v -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"$TEST_PASSWORD"}' \
  | grep -i "set-cookie"

# Should see: Set-Cookie: auth_token=...; HttpOnly; Secure; SameSite=Strict
```

#### 4. CSRF Protection
```bash
# Request without CSRF token should fail
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Cookie: auth_token=..." \
  -H "Content-Type: application/json" \
  -d '{}'

# Should return: 403 Forbidden
```

#### 5. OAuth CSRF
```bash
# Test OAuth flow manually:
# 1. Initiate OAuth login
# 2. Check oauth_state cookie is set
# 3. Complete OAuth flow
# 4. Verify callback validates state
# 5. Try replaying callback with different state - should fail with 401
```

#### 6. API Key Encryption
```bash
# Check database - API keys should be encrypted
psql surfsense -c "SELECT id, email, api_keys FROM users LIMIT 1;"

# api_keys should look like encrypted strings, not plaintext
```

#### 7. JWT Refresh Tokens
```bash
# Test token refresh
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Cookie: refresh_token=..." \
  --cookie-jar cookies.txt

# Should set new access_token and refresh_token cookies
```

#### 8. Rate Limiting
```bash
# Test login rate limit (should fail after 5 attempts)
for i in {1..6}; do
  curl -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"invalid_password"}' \
    -w "\nStatus: %{http_code}\n"
done

# First 5 should return 401, 6th should return 429
```

### Automated Security Scan

```bash
# Run full security scan
cd /opt/SurfSense

# Backend scan
cd surfsense_backend
safety check
bandit -r app/

# Frontend scan
cd ../surfsense_web
pnpm audit
npm audit fix  # Apply auto-fixes if safe

# Check for secrets in code
cd ..
git secrets --scan-history  # If git-secrets installed
```

---

## Deployment Checklist

Before deploying to production:

### Pre-Deployment

- [ ] All tests pass (`pytest` in backend, no TypeScript errors in frontend)
- [ ] Dependencies updated and verified
- [ ] Security headers configured
- [ ] HttpOnly cookies implemented
- [ ] CSRF protection enabled
- [ ] OAuth CSRF validation added
- [ ] API keys encrypted in database
- [ ] JWT refresh tokens implemented
- [ ] Rate limiting configured
- [ ] Logging audited (no sensitive data)
- [ ] Type safety improved (reduced `any` usage)

### Deployment Steps

1. **Backup Database**
```bash
ssh user@your-vps-ip
pg_dump surfsense > /backup/surfsense_$(date +%Y%m%d).sql
```

2. **Deploy Backend**
```bash
cd /opt/SurfSense
git pull origin nightly
cd surfsense_backend
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
systemctl restart surfsense
systemctl restart surfsense-celery
```

3. **Deploy Frontend**
```bash
cd /opt/SurfSense/surfsense_web
pnpm install
pnpm build
systemctl restart surfsense-frontend
```

4. **Verify Services**
```bash
systemctl status surfsense
systemctl status surfsense-celery
systemctl status surfsense-frontend
```

5. **Check Logs**
```bash
journalctl -u surfsense -n 50
journalctl -u surfsense-frontend -n 50
```

6. **Test Critical Paths**
- Login/logout
- Document upload
- Search functionality
- Connector syncing
- OAuth login

### Post-Deployment

- [ ] Security headers verified in production
- [ ] Cookies are HttpOnly and Secure
- [ ] CSRF protection working
- [ ] OAuth flow works with state validation
- [ ] API requests work with encrypted keys
- [ ] Token refresh works
- [ ] Rate limiting active
- [ ] No errors in logs
- [ ] Performance acceptable

### Monitoring

Set up alerts for:
- Failed authentication attempts (potential brute force)
- Rate limit violations
- CSRF token failures
- JWT expiration errors
- API key decryption failures

---

## Quick Reference

### Critical Commands

```bash
# Update dependencies
pip install --upgrade urllib3>=2.5.0
pnpm update tar-fs@^2.1.4 @babel/runtime@^7.28.4 js-yaml@^4.1.1

# Restart services
systemctl restart surfsense surfsense-celery surfsense-frontend

# Check security
safety check
pnpm audit
bandit -r app/

# Verify headers
curl -I https://your-domain.com

# Check logs
journalctl -u surfsense -n 50
```

### Key Files Modified

**Backend:**
- `app/app.py` - Security headers, CSRF config
- `app/routes/auth_routes.py` - OAuth CSRF, HttpOnly cookies, refresh tokens
- `app/core/auth.py` - Cookie-based auth
- `app/models/user.py` - Encrypted API keys
- `app/services/encryption_service.py` - New encryption service

**Frontend:**
- `next.config.mjs` - Security headers
- `lib/api.ts` - Cookie auth, CSRF tokens, auto-refresh
- `lib/csrf.ts` - New CSRF helper
- `middleware.ts` - New rate limiting
- All auth pages - Remove localStorage

---

## Support

If you encounter issues:

1. Check logs: `journalctl -u surfsense -n 100`
2. Verify configuration: Environment variables, secrets.enc.yaml
3. Test in development first before deploying to production
4. Rollback if needed: `git checkout <previous-commit>`

**Remember:** Security is an ongoing process. Schedule regular security audits and keep dependencies updated.

---

**Document Version:** 1.0
**Last Updated:** December 1, 2025
**Estimated Implementation Time:** 3-4 weeks
**Priority:** HIGH - Begin immediately with Critical Fixes
