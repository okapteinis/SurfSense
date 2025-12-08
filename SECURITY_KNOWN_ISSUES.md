# Known Security Issues

## Unpatched Vulnerabilities

### 1. @parcel/reporter-dev-server (CVE-2025-56648)

**Severity:** Moderate (6.5/10)
**Status:** No patch available
**Last Checked:** 2025-12-08

**Affected Component:** Development server only (not in production builds)
**Location:** `surfsense_browser_extension`

**Description:**
The Parcel development server is vulnerable to SSRF (Server-Side Request Forgery) when visiting malicious websites during development.

**Mitigation Strategy:**
1. ✅ Only use development server with trusted content
2. ✅ Do not browse untrusted websites while dev server is running
3. ✅ Consider using `--disable-dev-server` flag if needed
4. ✅ Production builds are not affected

**Tracking:**
- GitHub Advisory: https://github.com/advisories/GHSA-qm9p-f9j5-w83w
- Dependency Path: `plasmo > @plasmohq/parcel-config > @parcel/config-default > @parcel/reporter-dev-server`

**Next Review:** Check for patches quarterly

---

### 2. tsup (DOM Clobbering)

**Severity:** Low
**Status:** No patch available
**Last Checked:** 2025-12-08

**Affected Component:** Build tool (development only)
**Location:** `surfsense_browser_extension`

**Description:**
tsup has a DOM Clobbering vulnerability that could potentially be exploited during the build process.

**Mitigation Strategy:**
1. ✅ Only affects development/build process, not runtime
2. ✅ Use trusted dependencies and lock files
3. ✅ Regular security audits of build pipeline
4. ✅ Production bundles are not affected

**Tracking:**
- GitHub Advisory: https://github.com/advisories/GHSA-3mv9-4h5g-vhg3
- Dependency Path: `plasmo > @plasmohq/parcel-config > @plasmohq/parcel-resolver-post > tsup`

**Next Review:** Check for patches quarterly

---

## Fixed Vulnerabilities (2025-12-08)

### Browser Extension Fixes
1. ✅ **msgpackr** - Updated to >=1.10.1 (CVE-2023-52079)
2. ✅ **css-what** - Updated to >=5.0.1 (CVE-2021-33587)
3. ✅ **content-security-policy-parser** - Updated to >=0.6.0 (CVE-2025-55164)
4. ✅ **svelte** - Updated to >=4.2.19 (mXSS vulnerability)
5. ✅ **esbuild** - Updated to >=0.25.0 (SSRF vulnerability)
6. ✅ **nanoid** - Updated to >=5.0.9 (Predictable generation issue)

### Web Component Fixes
1. ✅ **esbuild** - Updated to >=0.25.0 (SSRF vulnerability)
2. ✅ **prismjs** - Updated to >=1.30.0 (DOM Clobbering)
3. ✅ **jsondiffpatch** - Updated to >=0.7.2 (XSS vulnerability)
4. ✅ **js-yaml** - Updated to >=4.1.1 (Prototype pollution)
5. ✅ **mdast-util-to-hast** - Updated to >=13.2.1 (Unsanitized attributes)
6. ✅ **ai (Vercel SDK)** - Updated to >=5.0.52 (Filetype whitelist bypass)

---

## Security Update Strategy

**Approach Used:**
- Direct dependency updates where possible
- PNPM overrides for transitive dependencies
- Comprehensive testing after updates

**Files Modified:**
- `surfsense_browser_extension/package.json` - Added pnpm overrides
- `surfsense_web/package.json` - Added pnpm overrides
- Both lock files regenerated

**Testing:**
- ✅ Build verification for both components
- ✅ Audit scans confirm fixes applied
- ✅ No breaking changes introduced

---

## Maintenance Schedule

- **Weekly:** Review new Dependabot alerts
- **Monthly:** Run `pnpm audit` on all components
- **Quarterly:** Review and attempt to patch known issues
- **Annually:** Full security audit

---

*Last Updated: 2025-12-08*
*Next Review Date: 2025-03-08*
