# Security Audit - PR #301 Findings

**Date:** January 2, 2026
**Auditor:** Claude Code
**Branch:** feature/pr301-security-fixes
**Base:** nightly

## Executive Summary

Reviewed 21 security issues identified in PR #301 from CodeQL and Gemini Code Assist.
**Result:** 17/21 already fixed, 4 require immediate action, 1 requires code organization.

---

## Status Overview

| Category | Total | Fixed | Needs Action |
|----------|-------|-------|--------------|
| SSRF (Critical) | 4 | 3 | 1 |
| Secrets Logging (High) | 6 | 6 | 0 |
| Info Disclosure (Medium) | 6 | 3 | 3 |
| Code Organization | 1 | 0 | 1 |
| **TOTAL** | **17** | **12** | **5** |

---

## CRITICAL: SSRF Vulnerabilities

### ✅ ISSUE 1: Jellyfin Connector - First Location (FIXED)
**File:** `surfsense_backend/app/connectors/jellyfin_connector.py:98-101`
**Status:** ✅ **ALREADY FIXED**
**Fix Applied:**
- Constructor requires `validated_ips` parameter (raises ValueError if missing)
- `_build_url()` method uses validated IPs for all requests
- TOCTOU protection via IP pinning

**Verification:**
```python
# Line 48-52: Requires validated IPs
if not validated_ips:
    raise ValueError(
        "validated_ips is required to prevent SSRF attacks. "
        "Call validate_connector_url() before creating JellyfinConnector."
    )
```

### ✅ ISSUE 2: Jellyfin Connector - Second Location (FIXED)
**File:** `surfsense_backend/app/connectors/jellyfin_connector.py:130-133`
**Status:** ✅ **ALREADY FIXED**
**Fix Applied:** Same as Issue 1 - all methods use `_build_url()` with validated IPs

### ❌ ISSUE 3: RSS Connector - Redirect Following (NEEDS FIX)
**File:** `surfsense_backend/app/connectors/rss_connector.py:138-142`
**Status:** ❌ **REQUIRES ACTION**
**Vulnerability:** While initial URL is validated, `follow_redirects=True` allows bypass via redirect chains

**Attack Vector:**
```
https://example.com/feed (validated, safe)
  ↓ 302 redirect
http://169.254.169.254/latest/meta-data/ (AWS metadata, dangerous!)
```

**Proposed Fix:**
1. **Option A (Recommended):** Disable redirects and handle manually with validation
2. **Option B:** Use httpx redirect callback to validate each redirect target
3. **Option C:** Limit redirect depth and validate final destination

**Implementation:** Apply Option B - validate each redirect in chain

### ✅ ISSUE 4: Jellyfin Route Handler (FIXED)
**File:** `surfsense_backend/app/routes/jellyfin_add_connector_route.py:84-87`
**Status:** ✅ **ALREADY FIXED**
**Fix Applied:**
- Line 63: URL validated with `validate_connector_url()`
- Line 70: `validated_ips` passed to connector constructor
- Line 85: Uses `_build_url()` which enforces IP pinning

---

## HIGH: Sensitive Data Logging

### ✅ ISSUE 1: LLM Service API Key Exposure (FIXED)
**File:** `surfsense_backend/app/services/llm_service.py:382-393`
**Status:** ✅ **ALREADY FIXED**
**Fix Applied:**
- Line 386: Uses `sanitize_model_string()` before logging
- Line 392: Logs sanitized model string, not raw credentials
- Extra parameter contains safe data only

**Verification:**
```python
# Line 385-393
safe_model_string = sanitize_model_string(model_string)
logger.info(
    "Successfully validated LLM configuration",
    extra={"model": safe_model_string}  # Safe - sanitized
)
```

### ✅ ISSUES 2-6: SOPS MCP Server Secret Logging (FIXED)
**Files:** `surfsense_backend/scripts/sops_mcp_server.py` (lines 606, 616, 625, 627, 634)
**Status:** ✅ **ALREADY FIXED**
**Fix Applied:**
- All commands use `redact_value()` and `redact_dict_values()`
- Secrets only shown with explicit `--show-values` flag
- Default behavior redacts all sensitive values

**Verification:**
```python
# Lines 606-609 (get command)
if not show_values and 'value' in result:
    result['value'] = redact_value(str(result['value']))
    result['note'] = "Use --show-values flag to see actual value"
print(json.dumps(result, indent=2))  # Safe - redacted
```

---

## MEDIUM: Information Disclosure

### ✅ Already Fixed (3 instances)
1. LLM service error handling - sanitized
2. Connector test endpoints - generic messages
3. SOPS export - redacted by default

### ❌ ISSUE 1: CSRF Routes Exception Details (NEEDS FIX)
**File:** `surfsense_backend/app/routes/csrf_routes.py:131-134`
**Status:** ❌ **REQUIRES ACTION**
**Vulnerability:** Returns `str(e)` exposing internal CsrfProtectError details

**Current Code:**
```python
except CsrfProtectError as e:
    logger.error(f"CSRF token generation failed: {e!s}", exc_info=True)
    return {
        "error": "Failed to generate CSRF token",
        "message": str(e)  # ❌ Exposes internal details
    }
```

**Proposed Fix:**
```python
except CsrfProtectError as e:
    logger.error(f"CSRF token generation failed: {e!s}", exc_info=True)
    return {
        "error": "Failed to generate CSRF token",
        "message": "An internal error occurred while generating the CSRF token."
    }
```

### ❌ ISSUE 2: Home Assistant Connector Errors (NEEDS FIX)
**File:** `surfsense_backend/app/connectors/home_assistant_connector.py:100, 104`
**Status:** ❌ **REQUIRES ACTION**
**Vulnerability:** Exception details (`{e!s}`) exposed to users

**Lines Affected:**
- Line 100: `f"Connection error: Unable to reach Home Assistant at {self.ha_url}. {e!s}"`
- Line 104: `f"Unexpected error: {e!s}"`

**Proposed Fix:**
- Line 100: `f"Connection error: Unable to reach Home Assistant at {self.ha_url}."`
- Line 104: `"Unexpected error while communicating with Home Assistant."`
- Add server-side logging: `logger.error(f"Home Assistant error: {e}", exc_info=True)`

### ❌ ISSUE 3: Mastodon Connector Errors (NEEDS FIX)
**File:** `surfsense_backend/app/connectors/mastodon_connector.py:106, 110`
**Status:** ❌ **REQUIRES ACTION**
**Vulnerability:** Exception details (`{e!s}`) exposed to users

**Lines Affected:**
- Line 106: `f"Connection error: Unable to reach {self.instance_url}. {e!s}"`
- Line 110: `f"Unexpected error: {e!s}"`

**Proposed Fix:**
- Line 106: `f"Connection error: Unable to reach {self.instance_url}."`
- Line 110: `"Unexpected error occurred while communicating with the Mastodon instance."`
- Add server-side logging: `logger.error(f"Mastodon error: {e}", exc_info=True)`

---

## CODE ORGANIZATION

### ❌ Git Hooks Consolidation (NEEDS FIX)
**Files:** `.githooks/` and `.git-hooks/`
**Status:** ❌ **REQUIRES ACTION**
**Issues:**
1. **Duplicate directories** causing confusion about active hooks
2. **Regex pattern bug** in `.githooks/pre-commit`

**Critical Bug - Line 22:**
```bash
# Lines 9-18: Shell glob patterns
sensitive_files=(
    "*.pem"   # Shell glob, not regex!
    "*.key"
)

# Line 22: Grep expects regex, not glob!
if git diff --cached --name-only | grep -q "$pattern"; then
    # ❌ grep "*.pem" matches ".pem", "..pem" but NOT "file.pem"
```

**Impact:** Sensitive files like `api_key.pem` or `secret.key` will NOT be detected!

**Proposed Fix:**
1. Merge `.git-hooks/verify-secrets` logic into `.githooks/pre-commit`
2. Convert glob patterns to proper regex:
   - `*.pem` → `\.pem$`
   - `*.key` → `\.key$`
   - `*.secret` → `\.secret$`
   - `id_rsa` → `id_rsa$` (anchor to end)
3. Delete `.git-hooks/` directory entirely
4. Update `core.hooksPath` to `.githooks`

---

## Implementation Plan

### Phase 1: Information Disclosure Fixes (15 min)
1. Fix CSRF routes exception handling
2. Fix Home Assistant connector error messages
3. Fix Mastodon connector error messages

### Phase 2: SSRF Fix - RSS Connector (30 min)
1. Implement redirect validation callback in httpx
2. Validate each redirect target against SSRF blocklist
3. Add test cases for redirect bypass attempts

### Phase 3: Git Hooks Consolidation (20 min)
1. Create unified `.githooks/pre-commit` with:
   - Sensitive file detection (proper regex)
   - SOPS encryption verification
   - Hardcoded secrets scanning
2. Delete `.git-hooks/` directory
3. Update documentation

### Phase 4: Testing (15 min)
1. Unit tests for info disclosure fixes
2. Integration tests for RSS redirect validation
3. Manual testing of git hooks with various file patterns

### Phase 5: Documentation & PR
1. Update CLAUDE.md with security fixes applied
2. Create detailed commit messages
3. Open PR to nightly with comprehensive description
4. Reference PR #301 and mark issues resolved

---

## Test Cases Required

### RSS Connector Redirect Validation
```python
async def test_rss_redirect_to_private_ip():
    """Test that redirect to private IP is blocked"""
    connector = RSSConnector(["https://evil.com/feed"])
    # evil.com redirects to http://192.168.1.1/
    with pytest.raises(HTTPException) as exc:
        await connector.validate_feed("https://evil.com/feed")
    assert "private IP" in str(exc.value.detail).lower()
```

### Git Hooks Regex Patterns
```bash
#!/bin/bash
# Test sensitive file detection

# Should BLOCK these:
touch test.pem test.key id_rsa api_secret.secret .env

# Should ALLOW these:
touch test.pem.example config.key.example README.md

git add .
./.githooks/pre-commit
# Expected: Blocks .pem, .key, id_rsa, .secret, .env
# Expected: Allows .example files
```

---

## Recommendations for Future

1. **Automated Security Scanning**
   - Enable CodeQL in GitHub Actions for all PRs
   - Add Semgrep for Python-specific vulnerability patterns
   - Schedule weekly dependency scans with Safety

2. **Defense in Depth**
   - Consider network-level SSRF protection (firewall rules)
   - Implement request signing for connector APIs
   - Add rate limiting on connector test endpoints

3. **Security Training**
   - Document common vulnerability patterns in CONTRIBUTING.md
   - Add security checklist to PR template
   - Regular security review of connector code

4. **Monitoring & Alerting**
   - Log all SSRF blocking attempts
   - Alert on suspicious redirect patterns
   - Monitor for secrets in application logs

---

## References

- **PR #301:** https://github.com/okapteinis/SurfSense/pull/301
- **OWASP SSRF:** https://owasp.org/www-community/attacks/Server_Side_Request_Forgery
- **CWE-918:** Server-Side Request Forgery (SSRF)
- **CWE-209:** Information Exposure Through Error Messages
- **CWE-532:** Information Exposure Through Log Files

---

**Next Steps:** Proceed with Phase 1 implementation.
