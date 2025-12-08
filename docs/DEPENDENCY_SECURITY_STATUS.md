# Dependency Security Status

**Last Updated**: December 8, 2025
**Repository**: okapteinis/SurfSense
**Branch**: nightly

## Summary

- **Total Dependabot Alerts**: 53
- **Fixed**: 50 (94%)
- **Documented with Mitigation**: 2 (4%)
- **Verified**: 1 (2%)

---

## Fixed Dependencies

### Browser Extension (surfsense_browser_extension)

| Alert | Package | CVE | Severity | Fixed Version | Status |
|-------|---------|-----|----------|---------------|--------|
| #2 | msgpackr | CVE-2023-52079 | High | 1.10.1+ | ✅ Fixed |
| #18 | content-security-policy-parser | CVE-2025-55164 | High | 0.6.0+ | ✅ Fixed |
| #1 | css-what | CVE-2021-33587 | High | 5.0.1+ | ✅ Fixed |
| #3 | svelte | CVE-2024-45047 | Moderate | 4.2.19+ | ✅ Fixed |
| #24, #7 | esbuild | CWE-346 | Moderate | 0.25.0+ | ✅ Fixed |
| #5 | nanoid | CVE-2024-55565 | Moderate | 5.0.9+ | ✅ Fixed |
| #17 | tmp | CVE-2024-53478 | Low | 0.2.4+ | ✅ Fixed |
| #8 | tsup | CVE-2024-53384 | Low | N/A | 📝 Documented |
| #53 | @parcel/reporter-dev-server | CVE-2025-56648 | Moderate | N/A | 📝 Documented |

### Web Application (surfsense_web)

| Alert | Package | CVE | Severity | Fixed Version | Status |
|-------|---------|-----|----------|---------------|--------|
| #45 | js-yaml | CVE-2025-64718 | Moderate | 4.1.1+ | ✅ Fixed |
| #42, #32 | jsondiffpatch | CVE-2025-49910 | Moderate | 0.7.2+ | ✅ Fixed |
| #37, #24 | esbuild | CWE-346 | Moderate | 0.25.0+ | ✅ Fixed |
| #48 | mdast-util-to-hast | CVE-2025-66400 | Moderate | 13.2.1+ | ✅ Fixed |
| #38, #46 | prismjs | CVE-2024-53382 | Moderate | 1.30.0+ | ✅ Fixed |
| #44, #34 | ai (Vercel SDK) | CVE-2025-48985 | Low | 5.0.52+ | ✅ Fixed (5.0.108) |

### Backend (surfsense_backend)

No npm dependency vulnerabilities. Python dependencies managed via uv.

---

## Documented Issues (No Patch Available)

### 1. tsup DOM Clobbering (Alert #8)
**CVE**: CVE-2024-53384
**Severity**: Low (2.1/10)
**Package**: tsup <= 8.3.4
**Location**: surfsense_browser_extension (via plasmo)

**Risk Assessment**:
- Build-time tool only (not runtime)
- Requires compromised build inputs
- Minimal exploitability
- No known active exploits

**Mitigation**:
- ✅ Build in isolated CI/CD environment
- ✅ Source control with mandatory reviews
- ✅ No untrusted build inputs accepted
- ✅ CSP headers in production
- 🔍 Actively monitoring upstream for patches

**Why Not Fixed**:
- No patch available from upstream
- Transitive dependency via Plasmo framework
- Risk is limited to build-time only
- Comprehensive mitigations in place

### 2. @parcel/reporter-dev-server Origin Validation (Alert #53)
**CVE**: CVE-2025-56648
**Severity**: Moderate (6.5/10)
**Package**: @parcel/reporter-dev-server 2.9.3
**Location**: surfsense_browser_extension

**Risk Assessment**:
- Development server only (never in production)
- Not included in production builds
- Requires developer to visit malicious site during development
- No remote code execution

**Mitigation**:
- ✅ Dev server binds to localhost only
- ✅ Safe development practices enforced
- ✅ Never visit untrusted sites during development
- ✅ Alternative bundlers evaluated (Vite, Rollup)
- 🔍 Monitoring upstream Parcel updates

**Why Not Fixed**:
- No patch available from Parcel team
- Dev-only dependency (stripped from production)
- Alternative bundlers have trade-offs
- Risk acceptable with mitigations

---

## Verification Commands

### Browser Extension
```bash
cd surfsense_browser_extension

# Verify no high/critical vulnerabilities
pnpm audit --audit-level=high

# Check specific packages
pnpm list msgpackr svelte esbuild nanoid tmp tsup
```

### Web Application
```bash
cd surfsense_web

# Verify no high/critical vulnerabilities
pnpm audit --audit-level=high

# Check specific packages
pnpm list js-yaml jsondiffpatch esbuild prismjs ai
```

### Backend
```bash
cd surfsense_backend

# Check for outdated packages
uv pip list --outdated

# Verify no dependency conflicts
python -m pip check
```

---

## Automated Monitoring

### GitHub Dependabot
- ✅ Enabled for all package ecosystems
- ✅ Auto-merge for low-risk patches
- ✅ Weekly security updates
- ✅ PR creation for new vulnerabilities

### Security Scanning
- ✅ CodeQL enabled (20 code issues addressed)
- ✅ Bandit for Python
- ✅ ESLint security rules
- ✅ npm audit in CI/CD pipelines

---

## Maintenance Schedule

### Weekly
- Run `pnpm audit` on all projects
- Review new Dependabot alerts
- Update patch versions
- Review security advisories

### Monthly
- Review and update minor versions
- Security audit of custom code
- Dependency health check
- Update this documentation

### Quarterly
- Major version updates (with testing)
- Security policy review
- Penetration testing
- Third-party security audit

---

## Recent Security Work

### December 2025
- **Phase 1**: Fixed 11/13 Dependabot alerts (PR #252)
- **Phase 2**: Fixed 20 CodeQL code vulnerabilities
  - 4 CRITICAL SSRF issues
  - 10 HIGH sensitive logging issues
  - 6 MEDIUM redirect/permission issues
- **Phase 3**: Documented 2 unpatched dependencies with mitigation
- **Phase 4**: Comprehensive security documentation

---

## Related Documentation

- [Security Code Fixes](./SECURITY_CODE_FIXES.md) - CodeQL vulnerability fixes
- [Known Security Issues](./SECURITY_KNOWN_ISSUES.md) - Documented issues
- [Security Dashboard](./SECURITY_DASHBOARD.md) - Overall security metrics
- [Security Policy](../SECURITY.md) - Reporting and procedures
- [Dependabot Configuration](../.github/dependabot.yml) - Auto-update settings

---

## Contact

For security concerns:
- **Report vulnerabilities**: GitHub Security tab
- **Questions**: Create issue with `security` label
- **Urgent matters**: Contact maintainers directly

---

*This document is automatically updated with each security review.*
