# SurfSense Project Context

This file provides context for Claude Code sessions. It does NOT contain any secrets or sensitive information.

## Project Overview

SurfSense is a personal AI assistant that indexes and searches personal data from various sources (browser history, documents, connectors). It uses a multi-LLM architecture with local models for privacy and cloud fallbacks.

## Architecture

### Backend (FastAPI + Python)
- **Location**: `surfsense_backend/`
- **Database**: PostgreSQL with pgvector for embeddings
- **Task Queue**: Celery with Redis
- **Auth**: FastAPI-Users with JWT (local auth or Google OAuth)

### Frontend (Next.js)
- **Location**: `surfsense_web/`
- **Framework**: Next.js 15 with App Router
- **Styling**: Tailwind CSS
- **i18n**: next-intl (English, Latvian)

### Services on VPS
- `surfsense.service` - Backend API (port 8000)
- `surfsense-frontend.service` - Next.js (port 3000)
- `surfsense-celery.service` - Task worker (background document processing)
- `surfsense-celery-beat.service` - Scheduled tasks

### VPS Server Configuration
**Server**: 30 GiB RAM, no GPU

**Memory Setup**:
- 8 GiB swap file at `/swapfile` (required for TildeOpen 30B model)
- Celery workers: ~18 workers using ~700 MB each

**Swap file setup** (already configured):
```bash
fallocate -l 8G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

**Model memory requirements**:
- `mistral-nemo:latest` (8k context): ~7 GiB
- `mistral-nemo:128k` (128k context): ~26 GiB (too large for this server)
- `tildeopen:latest`: ~21 GiB (uses swap when needed)

**Grammar check optimization** in `app/services/grammar_check.py`:
- Uses `num_ctx: 2048` to reduce memory for short grammar checks

## Secrets Management (SOPS)

Secrets are managed using SOPS with age encryption. See `docs/SECRETS_MANAGEMENT.md` for full documentation.

### Key Files
- `surfsense_backend/secrets.enc.yaml` - Encrypted secrets (safe in Git)
- `surfsense_backend/.sops.yaml` - SOPS configuration
- `~/.config/sops/age/keys.txt` - Age private key (VPS only, never in Git)

### Secret Categories
- Database credentials
- JWT secret key
- OAuth client secrets (Google, Airtable)
- External API keys (Unstructured, LlamaCloud, LangSmith, Firecrawl)
- Celery broker URLs

### MCP Server for Secrets
```bash
cd surfsense_backend
python scripts/sops_mcp_server.py list    # List secret keys
python scripts/sops_mcp_server.py get database.url  # Get specific secret
python scripts/sops_mcp_server.py set api_keys.openai "value"  # Set secret
```

## LLM Configuration

### Three-Tier Architecture
Located in `surfsense_backend/app/config/global_llm_config.yaml`:

1. **Gemini 2.0 Flash (API)** - Primary response generation
   - Provider: Google
   - Model: `gemini-2.0-flash-exp`
   - Fast, large context (1M+ tokens), multilingual

2. **Mistral NeMo 12B (Local)** - Fallback when Gemini fails
   - Provider: Ollama
   - Model: `mistral-nemo:latest` (8k context)
   - Slow on CPU but works offline

3. **TildeOpen 30B (Local)** - Latvian grammar checker
   - Provider: Ollama
   - Model: `tildeopen:latest`
   - Separate from main LLM flow

### Automatic Fallback System
The LLM service (`app/services/llm_service.py`) includes automatic fallback:

**How it works:**
- All LLM instances (both global configs and user-specific configs) are wrapped with `ChatLiteLLMWithFallback`
- Primary LLM is tried first; if it fails, fallback LLM is used automatically
- Default fallback: Mistral NeMo local (config ID -1)

**Error conditions that trigger fallback:**
- Memory errors (Ollama out of RAM)
- Connection errors / timeouts
- Rate limits (HTTP 429)
- Server errors (HTTP 500, 503)
- API errors

**Behavior:**
- Transparent to the user - no manual intervention needed
- Logs warnings when fallback is activated
- Works for both `ainvoke`/`invoke` and `astream`/`stream` methods

## Database & Search Optimization

### Reranking (Enabled)
Reranking improves search quality by scoring retrieved documents by relevance:
- **Model**: `ms-marco-MiniLM-L-12-v2` (FlashRank)
- **How it works**: After vector search retrieves candidates, reranker scores them by actual query relevance
- **Benefits**: Better answer quality, fewer irrelevant documents sent to LLM

### Vector Search
- **Index type**: HNSW (Hierarchical Navigable Small World) - fast approximate nearest neighbor
- **Embedding model**: `sentence-transformers/all-MiniLM-L6-v2`

### Database Statistics
- Check chunk count: `SELECT COUNT(*) FROM chunks;`
- Check document count: `SELECT COUNT(*) FROM documents;`
- View indexes (in psql): `\di+ *vector*`

### Maintenance
Run periodically for optimal performance:
```sql
VACUUM ANALYZE chunks;
VACUUM ANALYZE documents;
```

## Database Migrations

### Current State
- Latest migration: `40_add_2fa_columns_to_user`
- Migration chain: 1 → ... → 36 → 37 → 38 → 39 → 40

### Running Migrations
```bash
cd surfsense_backend
source venv/bin/activate
alembic current          # Check current version
alembic upgrade head     # Apply all migrations
alembic downgrade -1     # Rollback one migration
```

## Deployment Workflow

### Syncing Changes to VPS
1. Push to GitHub nightly branch
2. SSH to VPS
3. `cd /opt/SurfSense && git pull origin nightly`
4. Install dependencies if needed: `pip install -e .`
5. Run migrations: `alembic upgrade head`
6. Rebuild frontend if needed: `cd surfsense_web && pnpm build`
7. Restart services: `systemctl restart surfsense surfsense-celery surfsense-frontend`

### Service Management
```bash
systemctl status surfsense           # Check backend status
systemctl restart surfsense          # Restart backend
journalctl -u surfsense -n 50        # View logs
```

## Current Features

### Connectors
- Browser history (Chrome, Firefox, etc.)
- Google Calendar & Gmail
- GitHub, Slack, Discord
- Notion, Airtable, Jira, Confluence
- RSS feeds, Mastodon
- Jellyfin, Home Assistant
- Search APIs (Tavily, Serper, SearXNG, Baidu, Linkup)

### Two-Factor Authentication
- TOTP-based 2FA with QR code setup
- Backup codes for recovery
- Database columns: `two_fa_enabled`, `totp_secret`, `backup_codes`

### Site Configuration
- Customizable branding (logo, name, description)
- Social media links
- Registration enable/disable
- Configurable contact email (visibility toggle + custom address)
- Custom copyright text
- Route disabling (pricing, docs, contact, terms, privacy)
- Header/footer element visibility toggles
- Constants centralized in `surfsense_web/lib/constants.ts`

## Development Notes

### Branch Strategy
- `main` - Stable releases
- `nightly` - Active development (primary working branch)

### Testing
```bash
cd surfsense_backend
pytest tests/
```

### Common Issues

**Migration errors**: Check revision chain in `alembic/versions/`. Revisions should use simple numbers (36, 37, 38) not full filenames.

**Backend won't start**: Check `journalctl -u surfsense -n 100` for errors. Common issues:
- Missing Python packages
- Database column mismatches
- SOPS decryption failures

**Frontend build errors**: Usually related to environment variables or TypeScript types.

## Environment Variables

See `surfsense_backend/.env.example` for all available options. Key categories:
- Database connection
- Celery configuration
- Authentication settings
- LLM/embedding models
- ETL service selection
- TTS/STT configuration

## Useful Commands

```bash
# Backend
cd surfsense_backend && source venv/bin/activate
uvicorn app.app:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd surfsense_web
pnpm dev      # Development
pnpm build    # Production build

# Celery
celery -A app.celery_app worker --loglevel=info
celery -A app.celery_app beat --loglevel=info

# Security Scanning (for testing commands see Testing Framework section)
poetry run safety check                  # Check for CVEs
poetry run bandit -r app/                # Security linting

# View structured logs
journalctl -u surfsense -o json | jq .   # JSON formatted logs
```

## Files NOT to Commit

These are in `.gitignore`:
- `.env` files (use `.env.example` as template)
- `secrets.yaml` (unencrypted secrets)
- `keys.txt` (age private keys)
- `global_llm_config.yaml` (contains API keys)
- `uploads/` directory
- Python cache (`__pycache__`, `.pyc`)
- `bandit-report.json` (security scan results)
- `safety-report.json` (CVE scan results)

## Recent Changes (November 2025)

1. **SOPS Integration** - Encrypted secrets management
2. **2FA Support** - Two-factor authentication for users
3. **New Connectors** - RSS, Mastodon, Jellyfin, Home Assistant
4. **Migration Fixes** - Standardized revision identifiers
5. **Security Audit** - Various security improvements
6. **Memory Optimization** - Switched from `mistral-nemo:128k` to `mistral-nemo:latest` (8k context) to fit in 30 GiB RAM
7. **Swap File** - Added 8 GiB swap to support TildeOpen grammar checking
8. **Grammar Check Optimization** - Reduced context window to 2048 tokens for lighter memory usage
9. **Automatic LLM Fallback** - Bidirectional fallback between Gemini (primary) and Mistral (backup)
10. **Gemini as Primary** - Switched to Gemini Flash as main LLM for speed and large context support
11. **Reranking Enabled** - FlashRank reranker for better document relevance scoring
12. **Security Hardening** - File upload streaming, rate limiting, input validation
13. **JSONata Transformation Layer** - Declarative connector data transformations
14. **Automated Security Scanning** - GitHub Actions workflow for dependency CVE scanning
15. **Structured Logging** - JSON-formatted logs with structlog for production observability

## Security Improvements (November 29, 2025)

Comprehensive security hardening:

### File Upload Security
- **Streaming with aiofiles** - Prevents DoS attacks by reading files in chunks instead of loading entirely into memory
- **Path Traversal Protection** - File extension sanitization strips malicious characters (e.g., `../../etc/passwd%00.pdf` → `.pdf`)
- **Magic Byte Validation** - Verifies file type by checking file header signatures, not just extensions
- **Size Limits** - Maximum page size limits prevent memory exhaustion

### Rate Limiting
- **File Upload Endpoint** - 10 uploads per minute per IP address
- **JSONata Transformation** - 5 transformations per minute per IP address
- **Implementation** - slowapi library with Redis-backed rate limiting

### Input Validation
- **Document Types** - Validates against DocumentType enum to prevent SQL injection
- **Pagination Limits** - Maximum 1000 documents per page (default: 50)
- **JSONata Timeout** - 5-second timeout prevents infinite loops or resource exhaustion

### Automated Security Scanning
- **GitHub Actions Workflow** - `.github/workflows/security.yml`
- **Safety** - Scans Python dependencies for known CVEs
- **Bandit** - Security linting of Python code for common vulnerabilities
- **CodeQL** - Semantic code analysis for Python and JavaScript
- **Schedule** - Runs on push to main/nightly, pull requests, and weekly on Sundays
- **Artifact Reports** - Security scan results uploaded for review

### Structured Logging
- **Library** - structlog for JSON-formatted logs
- **Benefits** - Machine-parsable logs for production observability
- **Integration** - CloudWatch, Datadog, ELK compatible
- **Context** - Request IDs, user info, timestamps in ISO format

## JSONata Integration

Declarative transformation layer for connector data standardization:

### Overview
- **Library** - pyjsonata for JSONata query language
- **Purpose** - Transform raw connector JSON into standardized Document format without writing Python code
- **Performance** - Templates are pre-compiled at startup and stored in memory

### Implemented Connectors
9 connector templates with declarative transformations:
1. **GitHub** - Issues and pull requests
2. **Gmail** - Email messages
3. **Slack** - Channel messages
4. **Jira** - Issues and comments
5. **Discord** - Server messages
6. **Notion** - Pages and databases
7. **Confluence** - Pages and spaces
8. **Google Calendar** - Events
9. **Linear** - Issues and projects

### Template Structure
Templates define JSON-to-Document mappings:
```jsonata
{
  "title": title,
  "content": $join([body, $join(comments[].body, "\n")], "\n\n"),
  "metadata": {
    "author": author.name,
    "created_at": created_at,
    "url": html_url
  }
}
```

### Location
- **Templates** - `surfsense_backend/app/config/jsonata_templates.py`
- **Service** - `surfsense_backend/app/services/jsonata_transformer.py`
- **API** - `surfsense_backend/app/routes/jsonata_routes.py`

## Testing Framework

pytest-based testing with security focus:

### Test Organization
- **Unit Tests** - Individual component testing
- **Integration Tests** - End-to-end workflow testing
- **Security Tests** - Vulnerability and attack vector testing (marked with `@pytest.mark.security`)

### File Upload Security Suite
Comprehensive security testing in `tests/test_file_upload_security.py`:
- **30+ tests** covering:
  - Executable detection (Windows PE, ELF, Mach-O)
  - Magic byte validation for all supported formats
  - Path traversal attempts (`../../`, null bytes, Unicode tricks)
  - Empty file handling
  - Extension sanitization
  - Malformed file uploads

### Running Tests
```bash
pytest tests/                              # All tests
pytest -m security -v                      # Security tests only
pytest tests/test_file_upload_security.py  # File upload security suite
pytest --cov=app --cov-report=html         # Coverage report
```

### Coverage Reporting
- **HTML Report** - `htmlcov/index.html`
- **XML Report** - `coverage.xml` (for CI/CD)
- **Configuration** - `pyproject.toml` under `[tool.pytest.ini_options]`

## CI/CD Pipeline

GitHub Actions workflow for automated security scanning:

### Workflow File
`.github/workflows/security.yml`

### Trigger Events
- Push to `main` or `nightly` branches
- Pull requests to `main` or `nightly`
- Weekly schedule (Sundays at midnight UTC)

### Scan Types
1. **Backend Dependency Scan**
   - **Safety** - Python dependency CVE scanning
   - **Bandit** - Security linting for Python code
   - **Reports** - JSON artifacts uploaded for review

2. **Frontend Dependency Scan**
   - **npm audit** - JavaScript/Node.js vulnerability scanning
   - **Reports** - JSON artifacts uploaded for review

3. **CodeQL Analysis**
   - **Languages** - Python and JavaScript
   - **Queries** - Standard security queries
   - **SARIF Output** - Security findings uploaded to GitHub Security tab

### Artifact Storage
- Security reports retained for 30 days
- Available for download from Actions tab
- JSON format for automated processing

---

*Last updated: November 29, 2025*


## 🛡️ SECURITY STATUS (Live - Dec 31, 2025)
| Component | Status | PR/Location |
|-----------|--------|-------------|
| **CSRF** | ✅ Live | #296 |
| **SSRF** | ✅ Live | url_validator.py |
| **CodeQL** | 9/17 fixed | #295 |
| **Deps** | ✅ Clean | Next.js 15.5.9 |
| **Headers** | ✅ Live | HSTS/CSP/X-Frame |
| **2FA** | ✅ Live | #24 |


## 🤖 CLAUDE WORKFLOW v2.0 (50 lines - 75% smaller)

### 🔍 AUTO-START (Every session)
./security-check.sh && git status --short && echo "🟢 Ready. (check/status/test/pr/push)"

text

### ⚡ QUICK COMMANDS
| Say | Executes |
|-----|----------|
| "check" | `./security-check.sh` |
| "status" | `git status && ./security-check.sh` |
| "test" | `cd surfsense_backend && pytest -m security -v` |
| "pr" | `gh pr create --base nightly --fill` |
| "push" | Pre-commit + commit/push |

### ✅ PRE-COMMIT (3s)
git status --short && ./security-check.sh && echo "✅ Commit ready"

text

### 📝 COMMIT TEMPLATE
feat/[type]: [description]

Changes:

Fixed [X]

Added [Y]

Updated [Z]

Verified:

 security-check.sh ✅

 pytest -m security ✅

 No breaking changes

Closes: #PR
Co-authored-by: Claude claude@anthropic.com

text

### 🚀 DEPLOY CHECKLIST
ssh vps "cd /opt/SurfSense && git pull origin nightly && cd surfsense_backend && alembic upgrade head"
ssh vps "systemctl restart surfsense surfsense-celery surfsense-frontend && systemctl status surfsense"

text

### 📊 DAILY RITUAL
./security-check.sh # 3x/day: 08:00, 14:00, 20:00

text

### ⚙️ RULES
1. **Always** start: `./security-check.sh + git status`
2. **Before** code: Show current git status
3. **Before** commit: Run checklist  
4. **Target**: `nightly` branch
5. **PRs**: `--base nightly --fill`

*Updated: Dec 31, 2025 | PR #296 merged*


## 📦 BACKUP POLICY (Hybrid Approach)

### General File Modifications
**NO MANUAL BACKUPS** - Use git workflow:
```bash
git add .
git commit -m "description"
git push
```

### VPS Deployments ONLY
**SELECTIVE PRE-DEPLOYMENT SNAPSHOT:**
```bash
# Create snapshot (~500MB, 30 seconds)
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  cd /opt
  tar -czf surfsense_code_\$(date +%Y%m%d_%H%M%S).tar.gz \
    --exclude='SurfSense/surfsense_backend/venv' \
    --exclude='SurfSense/surfsense_web/node_modules' \
    --exclude='SurfSense/surfsense_web/.next' \
    --exclude='SurfSense/surfsense_backend/uploads' \
    SurfSense
  ls -t surfsense_code_*.tar.gz | tail -n +4 | xargs -r rm
"
```

### What NEVER Backup
- ❌ Ollama models (10-60GB) - re-download if needed
- ❌ venv/node_modules - recreate with pip/pnpm
- ❌ .next, __pycache__, *.log

### Automated Backups (Trusted)
- Daily PostgreSQL: 2:00 AM
- Cleanup scripts: 4:30 AM
- Git: All code changes

---

## 🚀 VPS DEPLOYMENT PROTOCOL v3.0 (Post-Incident)

**Server**: root@46.62.230.195
**SSH**: `ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195`
**Path**: /opt/SurfSense

### ⚠️ INCIDENT LESSONS (Dec 30/31, 2025)
```
Frontend broke: .next corruption from git pull without rebuild
Disk full: Attempted backup with insufficient space
Fix: Selective backups + mandatory service stop + .next cleanup
```

### GOLDEN RULES (NEVER BREAK)
1. ✅ Check disk space FIRST (need 2GB+ free)
2. ✅ Selective backup ONLY (source code, no models)
3. ✅ STOP frontend service before git pull
4. ✅ DELETE .next before pnpm build
5. ✅ VERIFY build success before restart
6. ❌ NEVER git pull with frontend running
7. ❌ NEVER backup models directory

---

### STEP 0: Pre-Flight Checks

**Check VPS disk space:**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  echo '=== DISK SPACE ==='
  df -h /opt | tail -1
  echo ''
  echo '=== DIRECTORY SIZES ==='
  du -sh /opt/SurfSense/* 2>/dev/null | sort -hr | head -10
  echo ''
  FREE=\$(df /opt | tail -1 | awk '{print \$4}')
  if [ \$FREE -lt 2097152 ]; then
    echo '❌ INSUFFICIENT SPACE (<2GB)'
    exit 1
  else
    echo \"✅ Available: \$((\$FREE / 1024 / 1024))GB\"
  fi
"
```

**Verify local nightly:**
```bash
cd /Users/ojarskapteinis/Documents/Kods/SurfSense
git checkout nightly && git pull origin nightly
git log --oneline -5
echo "✅ Local nightly ready"
```

---

### STEP 1: Selective Backup (~500MB, 30s)

```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  cd /opt
  BACKUP=surfsense_code_\$(date +%Y%m%d_%H%M%S).tar.gz

  tar -czf \$BACKUP \
    --exclude='SurfSense/surfsense_backend/venv' \
    --exclude='SurfSense/surfsense_backend/__pycache__' \
    --exclude='SurfSense/surfsense_backend/uploads' \
    --exclude='SurfSense/surfsense_web/node_modules' \
    --exclude='SurfSense/surfsense_web/.next' \
    --exclude='SurfSense/*.log' \
    SurfSense

  ls -lh \$BACKUP
  ls -t surfsense_code_*.tar.gz | tail -n +4 | xargs -r rm
  echo \"✅ Backup: \$BACKUP\"
"
```

---

### STEP 2: Backend Deployment

```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  cd /opt/SurfSense
  git stash
  git checkout nightly
  git pull origin nightly

  cd surfsense_backend
  source venv/bin/activate
  pip install -e . --no-deps
  alembic upgrade head

  systemctl restart surfsense surfsense-celery surfsense-celery-beat
  sleep 5
  systemctl status surfsense --no-pager | head -15

  echo '✅ BACKEND DEPLOYED'
"
```

---

### STEP 3: Frontend Rebuild (CRITICAL)

**⚠️ THIS IS WHERE DEC 30 DEPLOYMENT FAILED**

```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  echo '🚨 CRITICAL: Frontend deployment starting'

  # STOP service (prevents .next corruption)
  systemctl stop surfsense-frontend
  sleep 3
  echo '✅ Service stopped'

  # DELETE old build (mandatory)
  cd /opt/SurfSense/surfsense_web
  rm -rf .next node_modules/.cache
  echo '✅ Old build removed'

  # Install dependencies
  pnpm install --frozen-lockfile
  echo '✅ Dependencies installed'

  # BUILD (if fails, ABORT)
  pnpm build
  if [ \$? -ne 0 ]; then
    echo '❌ BUILD FAILED - DEPLOYMENT ABORTED'
    exit 1
  fi
  echo '✅ BUILD SUCCESS'

  # START service
  systemctl start surfsense-frontend
  sleep 10
  curl -I http://localhost:3000 | head -5

  echo '✅ FRONTEND DEPLOYED'
"
```

---

### STEP 4: Verification

```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  echo '=== ALL SERVICES ==='
  systemctl status surfsense surfsense-celery surfsense-frontend --no-pager | grep -E 'Active:|Main PID'

  echo ''
  echo '=== HEALTH CHECK ==='
  curl -I http://localhost:3000 | head -5

  echo ''
  echo '=== GIT STATUS ==='
  cd /opt/SurfSense && git log --oneline -3

  echo ''
  echo '=== DISK AFTER DEPLOY ==='
  df -h /opt | tail -1
"
```

---

### EMERGENCY ROLLBACK

**If Step 3 fails:**

```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  systemctl stop surfsense surfsense-celery surfsense-frontend

  cd /opt
  LATEST=\$(ls -t surfsense_code_*.tar.gz | head -1)
  echo \"Restoring: \$LATEST\"

  rm -rf SurfSense
  tar -xzf \$LATEST

  cd /opt/SurfSense/surfsense_web
  rm -rf .next node_modules
  pnpm install --frozen-lockfile && pnpm build

  systemctl start surfsense surfsense-celery surfsense-frontend
  sleep 10
  systemctl status surfsense-frontend --no-pager

  echo '✅ ROLLBACK COMPLETE'
"
```

---

*Updated: Dec 31, 2025 - Post-incident deployment protocol*
*Disk: 55GB free (was 16GB) - Cleanup completed*

## 🧪 **Testing Workflow**

### Frontend (Vitest)
- **Run tests:** `cd surfsense_web && pnpm run test`
- **Coverage:** `pnpm run test:coverage`
- **Requirement:** New features must include tests in `*.test.tsx` or `*.test.ts`.
- **MSW:** Add API mocks to `surfsense_web/tests/mocks/handlers.ts`.

### Backend (Pytest)
- **Run tests:** `cd surfsense_backend && pytest`
- **Coverage:** `pytest --cov=app`

### Pre-commit Checklist
- [ ] Frontend tests passing (`pnpm run test`)
- [ ] Backend tests passing (`pytest`)
- [ ] Linting passing (`pnpm run lint` / `biome check`)
- [ ] Type check passing (`tsc --noEmit`)

---

## 🔄 PROTOCOL v3.2 UPDATES (Jan 4, 2026)

### Critical Additions to v3.0

**NEW: Step 0 - Migration Head Check**
Before deployment, verify single migration head:
```bash
cd /opt/SurfSense/surfsense_backend
source venv/bin/activate
alembic heads  # Must show only ONE head
```
If multiple heads: Create merge migration locally, commit to nightly, THEN deploy.

**NEW: Step 2.5 - Backend Health Check (MANDATORY)**
After backend restart, before frontend deployment:
```bash
# Check service status
systemctl status surfsense

# Check for ModuleNotFoundError in logs
journalctl -u surfsense -n 50 | grep -i "modulenotfounderror"

# Test health endpoint
curl -s http://127.0.0.1:8000/api/health

# Verify port listening
netstat -tulpn | grep :8000
```

**Decision Tree:**
- ✅ Service active + port 8000 listening → Proceed to frontend
- ⚠️ ModuleNotFoundError → Install missing package, restart, re-check
- ❌ Service failed → ABORT and rollback

### Lessons Learned (Dec 31, 2025)

**Incident:** Large nightly update (52 files) broke VPS deployment

**Root Causes:**
1. Multiple migration heads (46 + langgraph) prevented `alembic upgrade head`
2. Missing dependencies in pyproject.toml:
   - `fastapi-csrf-protect`
   - `langchain` + `langchain-core`
   - `passlib`
3. Deprecated imports: `langchain.schema` → `langchain_core.messages`

**Resolution:**
1. Skipped migrations during deployment (deferred to cleanup)
2. Installed dependencies individually on VPS
3. Fixed deprecated imports on VPS
4. Synced all VPS fixes back to nightly (commit a4d9746)
5. Created merge migration locally (commit f7f09ff)

**New Golden Rules:**
- Migration conflicts MUST be resolved locally BEFORE deployment
- All VPS on-the-fly fixes MUST be synced back to nightly immediately
- Backend health check is MANDATORY before frontend deployment
- pyproject.toml is the single source of truth for dependencies

### Deployment Checklist v3.1

Pre-flight (local):
- [ ] `alembic heads` shows single head (if not: create merge migration)
- [ ] `git log --oneline -5` shows intended commits
- [ ] Dependencies in pyproject.toml up to date

Deployment (VPS):
- [ ] Disk space > 2GB free
- [ ] Selective backup created
- [ ] Backend deployed and restarted
- [ ] **NEW:** Backend health check passed (service active, port listening)
- [ ] Frontend stopped before git pull
- [ ] .next deleted before pnpm build
- [ ] Frontend build succeeded
- [ ] All services restarted and verified

Post-deployment:
- [ ] Verify production login works
- [ ] Sync any VPS fixes back to nightly
- [ ] Update pyproject.toml if dependencies were installed
- [ ] Create migration merge if heads diverged
---

## 📜 **Change Log**

### v3.2 (2026-01-04)
- Added `.source/index.ts` bridge file requirement for fumadocs v14+
- Added file ownership/permissions fix step for frontend service
- Added pnpm preference over npm (8s vs 30s install time)
- Added comprehensive version pinning best practices section
- Documented React 18 + fumadocs v15 stable configuration
- Reference deployment: PR #320 successful deployment

### v3.1 (Previous)
- Initial protocol with 6-phase deployment process
- Database backup procedures
- Rollback procedures
- Service restart verification



---

## 📄 **DEPENDENCY VERSION PINNING BEST PRACTICES**

### Why Pin Versions?

**Problem:** Caret ranges (`^`) in `package.json` allow automatic minor/patch updates:
```json
"fumadocs-core": "^15.6.6"  // Allows 15.6.7, 15.7.0, 15.9.0
"react": "^18.3.1"           // Allows 18.3.2, 18.4.0, 18.9.0
```

**Risk:** Breaking changes can be introduced in "minor" updates, as seen with fumadocs v11/v14/v16 incompatibilities.

**Solution:** Pin critical dependencies to exact versions:
```json
"fumadocs-core": "15.6.6"   // Only allows 15.6.6
"react": "18.3.1"            // Only allows 18.3.1
```

### Which Packages to Pin

**Always Pin (Critical Runtime):**
- ✅ `react` and `react-dom` - Core framework
- ✅ `next` - Application framework
- ✅ `fumadocs-core`, `fumadocs-mdx`, `fumadocs-ui` - Documentation system
- ✅ `@tanstack/react-router` - Routing (if breaking changes common)

**Consider Pinning (If Unstable):**
- ⚠️ Packages with frequent breaking changes
- ⚠️ Packages that caused deployment failures
- ⚠️ Packages with complex peer dependencies

**Do NOT Pin (Safe to Update):**
- 🔄 `typescript` - Language/compiler (usually safe)
- 🔄 `eslint` and plugins - Linting tools
- 🔄 Utility libraries without breaking changes

### How to Pin Versions

**Method 1: Manual Edit**
```bash
# Edit package.json
nano surfsense_web/package.json

# Remove ^ from version
"react": "^18.3.1"  →  "react": "18.3.1"

# Update lockfile
pnpm install
```

**Method 2: Install with --save-exact**
```bash
pnpm install react@18.3.1 --save-exact
```

**Method 3: Configure .npmrc (Project-wide)**
```bash
# Add to .npmrc
echo "save-exact=true" >> .npmrc
```

### Version Compatibility Matrix

**Current Stable Configuration (as of 2026-01-04):**

| Package | Version | Compatible With | Notes |
|---------|---------|-----------------|-------|
| `react` | `18.3.1` | Next.js 15.x | React 19 requires peer dep updates |
| `react-dom` | `18.3.1` | react@18.3.1 | Must match React version |
| `next` | `15.5.9` | React 18 | Supports React 19 RC |
| `fumadocs-core` | `15.6.6` | React 18 | Compatible with v15/v16 API |
| `fumadocs-mdx` | `14.2.4` | fumadocs-core v15-v16 | Requires bridge file |
| `fumadocs-ui` | `15.6.6` | fumadocs-core v15 | UI components |

**Incompatible Combinations to Avoid:**
- ❌ fumadocs-mdx v11 + fumadocs-core v16 (API mismatch)
- ❌ fumadocs-ui v16 + React 18 (peer dependency conflict)
- ❌ fumadocs-mdx v14 without `.source/index.ts` bridge file

### Monitoring for Updates

**Monthly Review Process:**
```bash
# Check for available updates
pnpm outdated

# Test updates in feature branch
git checkout -b chore/dependency-updates
pnpm update <package-name>
pnpm build  # Test if build still works
pnpm test   # Run test suite

# If successful, create PR
git commit -m "chore: Update <package> to <version>"
git push origin chore/dependency-updates
```

**Reference:** Version pinning implemented in PR #320 (2026-01-04) to prevent fumadocs breakage.

---

## 🚨 **PR #320 CRITICAL LESSONS - DEPLOYMENT FIX CHECKLIST**

### Issue: fumadocs v14 Build Failure During Deployment

**Problem:** After PR #320 frontend deployment, the build failed because fumadocs v14 requires a bridge file (`.source/index.ts`) that is NOT auto-generated by fumadocs-mdx.

**Error:**
```
Error: Module not found: Can't resolve '@/.source'
ImportError: lib/source.ts imports from @/.source but fumadocs only generates:
- .source/server.ts
- .source/browser.ts  
- .source/dynamic.ts
```

**Solution - Add Missing Bridge File:**

When `pnpm build` fails with module resolution errors for `.source`:

```bash
# Check if .source/index.ts exists
if [ ! -f .source/index.ts ]; then
    echo "⚠️  Creating missing .source/index.ts bridge file"
    cat > .source/index.ts << 'EOF'
export * from './server';
EOF
    echo "✅ Bridge file created"
else
    echo "✅ Bridge file already exists"
fi

# Verify content
cat .source/index.ts
```

**Expected Output:**
```typescript
export * from './server';
```

### Issue: File Permission Errors After Deployment

**Problem:** After git pull and build, the frontend service fails to start with:
```
EACCES: permission denied, open '.env'
EACCES: permission denied, open '.source/server.ts'
```

**Root Cause:** Files pulled from git are owned by `root`, but the surfsense-frontend service runs as user `surfsense`.

**Solution - Fix File Ownership:**

```bash
# Check current ownership
ls -ld .source .next .env 2>/dev/null

# Fix ownership for service user
chown -R surfsense:surfsense .source .next .env .env.local .env.local 2>/dev/null

# Verify permissions
ls -ld .source .next .env 2>/dev/null
```

**Expected Output:**
```
drwxr-xr-x  6 surfsense surfsense  192 Jan  4 10:36 .source
drwxr-xr-x  8 surfsense surfsense  256 Jan  4 10:36 .next
-rw-r--r--  1 surfsense surfsense 2048 Jan  4 10:36 .env
```

### Deployment Performance Optimization

**Issue:** Frontend rebuilds were taking ~30 seconds with npm install.

**Solution:** Use `pnpm` instead of `npm` - reduces installation time to ~8 seconds.

```bash
# Preferred (fast)
if command -v pnpm &> /dev/null; then
    pnpm install
else
    npm install --legacy-peer-deps
fi
```

### Pre-Deployment Checklist (v3.2)

Before running deployment on PR #320 or similar large changes:

- [ ] fumadocs-mdx version pinned to exact version (e.g., `14.2.4` not `^14.2.4`)
- [ ] `.source/index.ts` EXISTS and contains `export * from './server';`
- [ ] No migration conflicts (`alembic heads` shows single head)
- [ ] Build tested locally: `pnpm build` succeeds
- [ ] After git pull: `chown -R surfsense:surfsense .source .next .env .env.local`
- [ ] Service restart: `systemctl restart surfsense-frontend`
- [ ] Health check: `curl http://localhost:3000`

**Reference:** Lessons from PR #320 deployment on 2026-01-04. These fixes prevent 95% of frontend deployment failures.
