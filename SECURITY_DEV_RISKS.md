# Known Development Security Risks

## Dependency Vulnerabilities

The following vulnerabilities are present in development dependencies but are currently awaiting upstream patches. They affect the development environment only.

### 1. @parcel/reporter-dev-server (Alert 54)
- **Package:** `@parcel/reporter-dev-server`
- **Vulnerability:** CVE-2025-56648 (Origin Validation Error)
- **Severity:** Moderate
- **Impact:** Allows malicious websites to interact with the dev server if a developer visits them while the server is running.
- **Status:** Awaiting upstream fix.
- **Mitigation:** Do not visit untrusted websites while running the browser extension development server.

### 2. tsup (Alert 8)
- **Package:** `tsup`
- **Vulnerability:** CVE-2024-53384 (DOM Clobbering)
- **Severity:** Low
- **Impact:** Potential code execution via crafted scripts in bundled CommonJS modules.
- **Status:** Awaiting upstream fix.
- **Mitigation:** Monitor for `tsup` updates (fixed in >= 8.3.5, currently unavailable or requiring upgrade).

## Action Plan
Monitor GitHub Security Advisories for updates to these packages and update them in `surfsense_browser_extension` when available.
