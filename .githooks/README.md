# Git Hooks for SurfSense

This directory contains Git hooks to prevent committing sensitive information.

## Setup

To enable these hooks, run:

```bash
git config core.hooksPath .githooks
```

The hook is already executable - no need to chmod.

## Pre-Commit Hook

The pre-commit hook performs comprehensive security checks:

### 1. Sensitive File Detection
Blocks commits containing:
- `.env` files (except `.env.example`)
- Private keys (`.pem`, `.key`, `id_rsa`, `id_ed25519`)
- SSL certificates (`.p12`, `.pfx`)
- Credentials files (`credentials.json`)

**Uses proper regex patterns** for accurate file matching.

### 2. Forbidden Plaintext Files
Prevents committing:
- `surfsense_backend/secrets.yaml` (use `secrets.enc.yaml`)
- Unencrypted `.env` files
- SOPS encryption keys

### 3. SOPS Encryption Verification
Verifies `secrets.enc.yaml` is actually encrypted (checks for `sops:` and `mac:` fields)

### 4. Hardcoded Secrets Detection
Scans for:
- API keys, passwords, tokens (>20 chars)
- AWS access keys (`AKIA...`)
- Private key headers
- GitHub tokens (`ghp_...`)

## Bypass (Emergency Only)

If absolutely necessary:

```bash
git commit --no-verify
```

**Warning:** Only use when certain no secrets are being committed.

---

**Last Updated:** January 2, 2026
**Migration Note:** This consolidated hook replaces the deprecated `.git-hooks/` directory.
