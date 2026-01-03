# Dependabot Security Alerts Remediation

This branch addresses 10 open Dependabot security vulnerabilities in the SurfSense project.

## Alert Summary

### High Severity (2 alerts)
- **#58**: Next Vulnerable to Denial of Service - surfsense_web/package-lock.json
  - Affected: next >= 15.5.1-canary.0, < 15.5.8
  - Fix: Update next to 15.5.8 or later

- **#57**: Next Vulnerable to Denial of Service - surfsense_web/pnpm-lock.yaml
  - Affected: next >= 15.5.1-canary.0, < 15.5.8  
  - Fix: Update next to 15.5.8 or later

### Moderate Severity (6 alerts)
- **#54**: Parcel Origin Validation Error - surfsense_browser_extension/pnpm-lock.yaml
- **#32**: jsondiffpatch XSS vulnerability - surfsense_web/package-lock.json
- **#56**: Next Server Actions Source Code Exposure - surfsense_web/package-lock.json
- **#55**: Next Server Actions Source Code Exposure - surfsense_web/pnpm-lock.yaml
- **#24**: esbuild Dev Server SSRF - surfsense_web/package-lock.json (PR #270)
- **#46**: PrismJS DOM Clobbering - surfsense_web/package-lock.json

### Low Severity (2 alerts)
- **#34**: Vercel AI SDK Filetype Bypass - surfsense_web/package-lock.json
- **#8**: tsup DOM Clobbering - surfsense_browser_extension/pnpm-lock.yaml

## Status

Dependabot is actively generating security updates. This branch consolidates the vulnerability fixes and tracks remediation progress.

## Related PRs
- PR #270: build(deps) - npm_and_yarn group updates (in progress)
