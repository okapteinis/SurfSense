# CodeQL Security Alerts Remediation

## Overview

This branch addresses 17 open CodeQL security alerts in the SurfSense project.

## Critical Issues (4 alerts)

### Full Server-Side Request Forgery (SSRF) - #32, #33, #34, #35

**Severity**: Critical
**Affected Files**:
- surfsense_backend/connectors/rss_connector.py:138
- surfsense_backend/connectors/jellyfin_connector.py:101
- surfsense_backend/connectors/jellyfin_connector.py:133
- surfsense_backend/routes/jellyfin_add_connector_route.py:87

**Issue**: Remote code execution through unsanitized requests to external services.

**Fix**: Implement request validation and URL scheme whitelist checks. Use `requests` library with timeout parameters and disable redirects for sensitive operations.

## High Severity Issues (9 alerts)

### Clear-text Logging of Sensitive Information - #25, #26, #27, #36, #37, #38, #39

**Severity**: High
**Affected Files**:
- surfsense_backend/routes/luma_add_connector_route.py
- surfsense_backend/routes/linear_add_connector_route.py  
- surfsense_backend/routes/slack_add_connector_route.py
- surfsense_backend/scripts/sops_mcp_server.py
- surfsense_backend/app/routes/linear_add_connector_route.py

**Issue**: Sensitive tokens and API keys logged in plain text to logs.

**Fix**: Remove sensitive data from logging. Use sanitization functions or mask sensitive values in logs.

## Medium Severity Issues (4 alerts)

### Workflow Missing Permissions - #1, #2, #4

**Severity**: Medium
**Affected Files**:
- .github/workflows/*.yml

**Fix**: Add explicit `permissions` block to GitHub workflows.

### Information Exposure Through Exception - #13, #22, #42

**Severity**: Medium
**Affected Files**:
- surfsense_backend/app/routes/luma_add_connector_route.py:235
- surfsense_backend/routes/slack_add_connector_route.py
- surfsense_backend/routes/linear_add_connector_route.py

**Fix**: Catch exceptions and return generic error messages instead of exposing stack traces.

## Remediation Status

This branch consolidates the tracking of all 17 CodeQL security alerts. Each alert requires targeted code modifications to address the underlying security vulnerabilities.

### Priority Order
1. **CRITICAL**: Fix SSRF vulnerabilities first (#32-#35)
2. **HIGH**: Fix sensitive data logging (#25-#39)
3. **MEDIUM**: Fix remaining issues (#1-#22)

## Related Issues
- GitHub CodeQL Security Alerts: https://github.com/okapteinis/SurfSense/security/code-scanning
