# Security Policy

## Reporting a Vulnerability

We take the security of SurfSense seriously. If you discover a security vulnerability, please follow these steps:

### 🔒 Private Disclosure

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, please report security vulnerabilities by emailing the security team or creating a [private security advisory](https://github.com/okapteinis/SurfSense/security/advisories/new).

### 📧 What to Include

When reporting a vulnerability, please include:

1. **Description**: A clear description of the vulnerability
2. **Impact**: Assessment of the potential impact
3. **Steps to Reproduce**: Detailed steps to reproduce the vulnerability
4. **Proof of Concept**: If possible, include a PoC (code, screenshots, etc.)
5. **Suggested Fix**: If you have ideas for fixing the issue
6. **Your Contact Information**: So we can follow up with you

### ⏱️ Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity (see below)

### 🎯 Severity Levels

| Severity | Response Time | Examples |
|----------|---------------|----------|
| **Critical** | 24-48 hours | RCE, Authentication bypass, Data breach |
| **High** | 3-7 days | SQL injection, XSS, CSRF, Information disclosure |
| **Medium** | 7-14 days | Minor information leaks, DoS |
| **Low** | 14-30 days | Security best practices, hardening |

---

## Security Features

SurfSense implements multiple layers of security protection:

### 🛡️ Application Security

#### 1. CSRF Protection
- **Implementation**: `fastapi-csrf-protect`
- **Coverage**: All state-changing endpoints (POST, PUT, DELETE, PATCH)
- **Token Management**: Double-submit cookie pattern
- **Frontend Integration**: Automatic token injection via `csrfFetch()`

**Usage**:
```typescript
import { csrfFetch } from '@/lib/csrf';

// Automatic CSRF protection
const response = await csrfFetch('/api/documents', {
  method: 'POST',
  body: JSON.stringify(data),
});
```

#### 2. SSRF Protection
- **Implementation**: `app/utils/url_validator.py`
- **Protection Against**:
  - Private IP ranges (RFC 1918)
  - Localhost access
  - Cloud metadata services (AWS, GCP)
  - DNS rebinding attacks
  - URL encoding bypass

**Features**:
- Async DNS resolution with validation
- TOCTOU attack prevention
- IPv4 and IPv6 support

#### 3. Security Headers
All responses include comprehensive security headers:

| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | Force HTTPS |
| `Content-Security-Policy` | (see below) | XSS prevention |
| `X-Frame-Options` | `DENY` | Clickjacking prevention |
| `X-Content-Type-Options` | `nosniff` | MIME sniffing prevention |
| `X-XSS-Protection` | `1; mode=block` | XSS filter |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Privacy |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Permission control |

**Content-Security-Policy**:
```
default-src 'self';
script-src 'self' 'unsafe-inline' 'unsafe-eval';
style-src 'self' 'unsafe-inline';
img-src 'self' data: https:;
font-src 'self' data:;
connect-src 'self' https://www.googleapis.com;
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
```

#### 4. Rate Limiting
- **Library**: `slowapi` with Redis backend
- **File Uploads**: 10 uploads/minute per IP
- **JSONata Transformations**: 5 transformations/minute per IP
- **Global**: Configurable per-endpoint limits

#### 5. Authentication & Authorization
- **Library**: `fastapi-users`
- **Methods**: Local (JWT) + Google OAuth
- **Session Management**: HttpOnly cookies (recommended)
- **2FA Support**: TOTP-based two-factor authentication
- **Password**: Bcrypt hashing with salts

#### 6. Input Validation
- **Framework**: Pydantic models
- **SQL Injection**: SQLAlchemy ORM (parameterized queries)
- **Path Traversal**: File extension sanitization
- **File Uploads**:
  - Magic byte validation
  - Size limits
  - Streaming (DoS prevention)

#### 7. Information Exposure Prevention
- **Error Handling**: Generic user messages
- **Logging**: Sensitive data filtering
- **Stack Traces**: Never exposed to clients
- **Debugging**: Detailed logs server-side only

### 🔐 Infrastructure Security

#### 1. Secrets Management
- **Method**: SOPS (Secrets OPerationS) with age encryption
- **Storage**: `secrets.enc.yaml` (encrypted, safe for Git)
- **Access**: Private keys on servers only
- **Rotation**: Supported via SOPS MCP server

#### 2. Database Security
- **Connection**: SSL/TLS encryption
- **Access Control**: Role-based permissions
- **Backups**: Regular encrypted backups
- **Sensitive Data**: API keys encrypted in database

#### 3. Dependency Security
- **Scanning**: `safety` (Python), `npm audit` (JavaScript)
- **Automation**: GitHub Dependabot + Actions
- **Policy**: Dependencies updated within 7 days for security issues

---

## Secure Development Practices

### Code Review
- All changes require review before merge
- Security-focused reviews for authentication/authorization changes
- Automated security scanning in CI/CD

### Testing
- Unit tests for security-critical functions
- Integration tests for authentication flows
- Security test suite (`@pytest.mark.security`)

### Continuous Security
- **CodeQL**: Semantic code analysis
- **Bandit**: Python security linting  
- **Safety**: Dependency vulnerability scanning
- **Pre-commit Hooks**: Format and lint checks

---

## Security Best Practices for Users

### For Self-Hosted Deployments

1. **Environment Variables**:
   ```bash
   # Generate strong secrets (example command to run separately)
   # openssl rand -hex 32

   # Then set in your .env file:
   CSRF_SECRET_KEY=<generated-secret-here>
   SECRET=<generated-secret-here>

   # Enable HTTPS in production
   COOKIE_SECURE="TRUE"

   # Set trusted proxy IPs
   TRUSTED_HOSTS="your-proxy-ip"
   ```

2. **Database**:
   - Use strong PostgreSQL passwords
   - Enable SSL connections
   - Restrict network access
   - Regular backups

3. **Reverse Proxy**:
   - Use HTTPS (Let's Encrypt recommended)
   - Configure rate limiting
   - Set security headers (redundant protection)
   - Enable HTTP/2

4. **Secrets Management**:
   ```bash
   # Initialize SOPS
   age-keygen -o ~/.config/sops/age/keys.txt
   
   # Never commit secrets.yaml (unencrypted)
   # Only commit secrets.enc.yaml (encrypted)
   ```

5. **Updates**:
   - Subscribe to security advisories
   - Apply security updates within 7 days
   - Test updates in staging first

### For Developers

1. **Local Development**:
   - Use `.env.example` as template
   - Never commit `.env` files
   - Use development-specific secrets

2. **Pull Requests**:
   - Run security tests: `pytest -m security`
   - Check for new vulnerabilities: `safety check`
   - Review CodeQL alerts

3. **Authentication**:
   - Always use authenticated endpoints
   - Include CSRF tokens for state changes
   - Handle 401/403 errors properly

---

## Known Issues & Limitations

### Current Limitations

1. **CSP Unsafe Directives**:
   - `unsafe-inline` and `unsafe-eval` required for Next.js
   - **Mitigation**: Planning to add nonce-based CSP
   - **Risk**: Medium (XSS slightly easier)

2. **CSRF Protection**:
   - Currently implemented but needs frontend integration
   - **Status**: Backend ready, frontend utility created
   - **Timeline**: Full integration in next release

3. **Dependency Vulnerabilities**:
   - Some deep dependencies with known CVEs
   - **Mitigation**: Monitoring for updates
   - **Risk**: Low to Medium

### Planned Improvements

1. **Security Enhancements**:
   - [ ] Remove CSP `unsafe-*` directives with nonces
   - [ ] Implement Subresource Integrity (SRI)
   - [ ] Add API key rotation mechanism
   - [ ] Implement security.txt (RFC 9116)

2. **Monitoring**:
   - [ ] Security event logging
   - [ ] Intrusion detection system
   - [ ] Anomaly detection

3. **Compliance**:
   - [ ] OWASP ASVS Level 2 compliance
   - [ ] SOC 2 Type II preparation
   - [ ] GDPR compliance audit

---

## Security Audit History

| Date | Scope | Findings | Status |
|------|-------|----------|--------|
| 2025-12-30 | CodeQL + Manual Review | 17 alerts (9 fixed, 8 false positives) | ✅ Completed |
| 2025-12-01 | Full Security Audit | 12 improvements implemented | ✅ Completed |
| 2025-11-29 | Dependency Scan | 10 vulnerabilities (8 fixed) | 🔄 In Progress |

### Recent Security Improvements

**December 2025**:
- ✅ Comprehensive security headers (HSTS, CSP)
- ✅ CSRF protection implementation
- ✅ Information exposure fixes (generic error messages)
- ✅ SSRF protection enhancements
- ✅ Workflow permissions (GitHub Actions)

**November 2025**:
- ✅ SOPS secrets management
- ✅ File upload security hardening
- ✅ Rate limiting implementation
- ✅ Structured logging with sanitization
- ✅ 2FA support

---

## Security Compliance

### OWASP Top 10 (2021)

| Category | Status | Implementation |
|----------|--------|----------------|
| A01 - Broken Access Control | ✅ | Role-based permissions, CSRF protection |
| A02 - Cryptographic Failures | ✅ | HTTPS, HSTS, encrypted secrets |
| A03 - Injection | ✅ | ORM, input validation, CSP |
| A04 - Insecure Design | ✅ | Security by design, threat modeling |
| A05 - Security Misconfiguration | ✅ | Security headers, safe defaults |
| A06 - Vulnerable Components | 🔄 | Dependency scanning, updates |
| A07 - Authentication Failures | ✅ | fastapi-users, 2FA, secure sessions |
| A08 - Software Integrity Failures | ⏳ | Planned: SRI, signed releases |
| A09 - Security Logging Failures | ✅ | Structured logging, sanitization |
| A10 - Server-Side Request Forgery | ✅ | Comprehensive URL validation |

**Legend**: ✅ Implemented | 🔄 In Progress | ⏳ Planned

---

## Resources

- **Documentation**: [SECURITY_FIXES.md](./SECURITY_FIXES.md) - Implementation guide
- **CodeQL Tracking**: [CODEQL_FIXES.md](./CODEQL_FIXES.md) - Alert status
- **Dependencies**: [GitHub Dependabot](https://github.com/okapteinis/SurfSense/security/dependabot)
- **Security Workflow**: [.github/workflows/security.yml](.github/workflows/security.yml)

---

## Contact

For security-related questions or concerns:

- **Security Issues**: Create a [private security advisory](https://github.com/okapteinis/SurfSense/security/advisories/new)
- **General Questions**: Open a GitHub Discussion
- **Urgent**: Email the maintainers directly

---

**Last Updated**: December 30, 2025
**Version**: 1.0.0
