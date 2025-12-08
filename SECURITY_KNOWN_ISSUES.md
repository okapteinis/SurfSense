# SurfSense - Security Known Issues and Fixes

**Last Updated**: December 8, 2025
**Repository**: okapteinis/SurfSense
**Branch**: nightly

## Executive Summary

- **Total Vulnerabilities Identified**: 15
- **Fixed**: 13
- **Documented with Mitigation**: 2
- **Remaining Risk**: Minimal (build-time and dev-only)

---

## ✅ Fixed Vulnerabilities

### Browser Extension (surfsense_browser_extension)

#### High Priority Fixes
1. **msgpackr < 1.10.1** (CVE-2023-52079)
   - Severity: High (8.6/10)
   - Issue: Infinite recursion DoS
   - Fixed: Updated to 1.10.1+
   - Status: ✅ Resolved

2. **content-security-policy-parser < 0.6.0** (CVE-2025-55164)
   - Severity: High (8.8/10)
   - Issue: Prototype pollution → RCE
   - Fixed: Updated to 0.6.0+
   - Status: ✅ Resolved

3. **css-what 4.0.0-5.0.0** (CVE-2021-33587)
   - Severity: High (7.5/10)
   - Issue: DoS via complexity attack
   - Fixed: Updated to 5.0.1+
   - Status: ✅ Resolved

#### Moderate Priority Fixes
4. **svelte < 4.2.19** (CVE-2024-45047 / Alert #3)
   - Severity: Moderate (5.1/10)
   - Issue: mXSS vulnerability
   - Fixed: Updated to 4.2.19+
   - Status: ✅ Resolved

5. **esbuild <= 0.24.2** (CWE-346 / Alert #7, #24)
   - Severity: Moderate (5.3/10)
   - Issue: CORS bypass (dev server)
   - Fixed: Updated to 0.25.0+
   - Status: ✅ Resolved

6. **nanoid < 5.0.9** (CVE-2024-55565 / Alert #5)
   - Severity: Moderate (4.3/10)
   - Issue: Predictable results with non-integer values
   - Fixed: Updated to 5.1.5
   - Status: ✅ Resolved

#### Low Priority Fixes
7. **tmp <= 0.2.3** (CVE-2024-53478 / Alert #17)
   - Severity: Low (2.1/10)
   - Issue: Arbitrary file write via symlink
   - Fixed: Updated to 0.2.4+
   - Status: ✅ Resolved (3 months ago)

### Web Application (surfsense_web)

#### High Priority Fixes
8. **js-yaml < 4.1.1** (CVE-2025-64718 / Alert #45)
   - Severity: Moderate (5.3/10)
   - Issue: Prototype pollution
   - Fixed: Updated to 4.1.1+
   - Status: ✅ Resolved

9. **jsondiffpatch < 0.7.2** (CVE-2025-49910 / Alert #42, #32)
   - Severity: Moderate (5.3/10)
   - Issue: XSS via HtmlFormatter
   - Fixed: Updated to 0.7.2+
   - Status: ✅ Resolved

#### Moderate Priority Fixes
10. **mdast-util-to-hast < 13.2.1** (CVE-2025-66400 / Alert #48)
    - Severity: Moderate (6.9/10)
    - Issue: Unsanitized class attribute
    - Fixed: Updated to 13.2.1+
    - Status: ✅ Resolved

11. **esbuild <= 0.24.2** (CWE-346 / Alert #37)
    - Severity: Moderate (5.3/10)
    - Issue: CORS bypass (dev server)
    - Fixed: Updated to 0.25.0+
    - Status: ✅ Resolved

12. **prismjs < 1.30.0** (CVE-2024-53382 / Alert #38, #46)
    - Severity: Moderate (4.9/10)
    - Issue: DOM Clobbering → XSS
    - Fixed: Updated to 1.30.0
    - Status: ✅ Resolved

#### Low Priority Fixes
13. **ai < 5.0.52** (CVE-2025-48985 / Alert #44, #34)
    - Severity: Low (3.7/10)
    - Issue: File type whitelist bypass
    - Fixed: Updated to 5.0.108
    - Status: ✅ Resolved

---

## ⚠️ Unpatched Vulnerabilities (With Mitigation)

### 1. tsup DOM Clobbering (CVE-2024-53384 / Alert #8)
**Location**: surfsense_browser_extension
**Severity**: Low (2.1/10)
**Status**: No patch available

**Vulnerability Details:**
A DOM Clobbering vulnerability in tsup v8.3.4 allows attackers to execute arbitrary code via a crafted script in the `import.meta.url` to `document.currentScript` in `cjs-shims.js` components.

**Risk Assessment:**
- **Runtime Impact**: None - tsup is a build-time tool only
- **Build-time Impact**: Minimal - requires compromised build inputs
- **Exploitability**: Low - requires attacker control over source files
- **Transitive Dependency**: Via plasmo 0.90.5

**Mitigation Strategy:**
1. ✅ **Code Review**: All build configurations reviewed for suspicious imports
2. ✅ **Source Control**: Strict branch protection and code review required
3. ✅ **CI/CD Security**: Build pipeline runs in isolated environments
4. ✅ **Input Validation**: No untrusted sources in build process
5. ✅ **Monitoring**: Watching for tsup security updates
6. ✅ **CSP Headers**: Content Security Policy implemented in production

**Recommended Actions:**
- Continue monitoring: https://github.com/egoist/tsup/security/advisories
- Consider alternative bundlers if patch not available within 3 months
- Regular security audits of build dependencies

**Workaround (if needed):**
```javascript
// In build configuration, disable problematic features
export default defineConfig({
  // Avoid using dynamic imports that rely on import.meta.url
  splitting: false,
  // Use alternative module resolution
  external: ['document']
});
```

**Risk Level**: **Minimal** (build-time only, controlled environment)

---

### 2. @parcel/reporter-dev-server (CVE-2025-56648 / Alert #53)
**Location**: surfsense_browser_extension
**Severity**: Moderate (6.5/10)
**Status**: No patch available

**Vulnerability Details:**
Parcel has an Origin Validation Error vulnerability where the development server allows any website to send requests and read responses due to default CORS settings. Malicious websites can steal source code.

**Risk Assessment:**
- **Production Impact**: None - only affects development server
- **Development Impact**: Moderate - source code exposure
- **Exploitability**: Moderate - requires visiting malicious site during dev

**Mitigation Strategy:**
1. ✅ **Localhost Binding**: Dev server binds to 127.0.0.1 only
2. ✅ **Safe Browsing**: Never visit untrusted websites during development
3. ✅ **Alternative Tools**: Evaluated alternative bundlers
4. ✅ **Production Safety**: Source maps disabled in production builds
5. ✅ **Monitoring**: Watching for upstream patches

**Safe Development Practices:**
```bash
# Always bind to localhost
pnpm dev  # Automatically binds to 127.0.0.1

# NEVER visit untrusted sites while dev server is running
# NEVER run dev server on public networks
```

**Risk Level**: **Low** (development-only, with safe practices)

---

## Development Best Practices

### Safe Development Commands

```bash
# Browser Extension - Safe dev mode
cd surfsense_browser_extension
pnpm dev  # Automatically binds to localhost

# Web Application - Safe dev mode
cd surfsense_web
pnpm dev --host 127.0.0.1

# Never run these commands while visiting untrusted sites:
# - pnpm dev
# - npm run watch
# - parcel serve
```

### Production Build Verification

```bash
# Run before deployment
pnpm audit
pnpm audit --fix

# Verify no high/critical vulnerabilities
pnpm audit --audit-level=high

# Check for outdated security patches
pnpm outdated
```

### Dependency Update Policy

1. **Security updates**: Apply immediately
2. **Major updates**: Test in staging first
3. **Weekly audit**: Run `pnpm audit` every Monday
4. **Automated alerts**: GitHub Dependabot enabled

---

## Testing Checklist

After applying all fixes:

### Browser Extension
- [x] No high/critical npm vulnerabilities
- [x] All builds complete successfully
- [x] Extension loads in Chrome/Firefox
- [x] Content scripts inject correctly
- [x] Background service worker functional
- [x] Settings page renders
- [x] Data syncing works

### Web Application
- [x] No high/critical npm vulnerabilities
- [x] Development server starts
- [x] Production build succeeds
- [x] All pages render correctly
- [x] API integrations functional
- [x] Authentication flows work
- [x] No console errors

### Security Verification
- [x] CSP headers configured
- [x] XSS protection enabled
- [x] CORS properly restricted
- [x] Secrets not in source code
- [x] Dependencies up to date
- [x] Security audit passing

---

## Implementation Timeline

**Batch 1 (Completed)**: Initial security fixes
- SSRF/TOCTOU protection
- Next.js updates
- Backend security hardening

**Batch 2 (Completed)**: Dependabot alerts #1-#11
- Browser extension: 5 high/moderate issues
- Web application: 6 moderate/low issues

**Batch 3 (Completed)**: Final vulnerability sweep
- prismjs, nanoid, tmp, ai updates
- Comprehensive documentation
- All fixable issues resolved

---

## References

### Vulnerability Databases
- [GitHub Advisory Database](https://github.com/advisories)
- [npm Security Advisories](https://www.npmjs.com/advisories)
- [CVE Database](https://cve.mitre.org/)

### Project Resources
- [SurfSense Security Policy](./SECURITY.md)
- [Contributing Guidelines](./CONTRIBUTING.md)
- [Dependabot Configuration](./.github/dependabot.yml)

---

## Contact

For security concerns:
- **Report vulnerabilities**: Use GitHub Security tab
- **Questions**: Create an issue with `security` label
- **Urgent matters**: Contact repository maintainers directly

---

**Note**: This document is maintained by the security team and reflects the current state of vulnerability management for the SurfSense project.

**Next Review Date**: March 8, 2026 (quarterly)
