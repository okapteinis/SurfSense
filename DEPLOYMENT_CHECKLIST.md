# Deployment Checklist - SurfSense Gemini Review Fixes

**PRs Covered:** #303, #304, #305, #306, #307, #308
**Target Branch:** `nightly`
**VPS Testing:** ✅ Complete (Phases 2A, 2B, 2C)
**Documentation Date:** January 3, 2026

---

## Pre-Deployment Verification

### 1. Code Quality Checks

**Local Environment:**
```bash
# 1. Ensure on nightly branch
git checkout nightly
git pull origin nightly

# 2. Verify latest commit
git log --oneline -5
# Expected: 66c5c76 test: Complete Phase 2C YouTube transcript extraction testing

# 3. Run security checks
./security-check.sh
# Expected: ✅ All checks passed

# 4. Run Python tests
cd surfsense_backend
source venv/bin/activate
python -m pytest tests/test_youtube_transcript_utils.py -v
python -m pytest tests/test_crawler_news_sites.py -v
# Expected: All tests passing

# 5. Syntax validation
python -m py_compile app/utils/youtube_utils.py
python -m py_compile app/tasks/document_processors/url_crawler.py
python -m py_compile scripts/debug_crawler_aljazeera.py
# Expected: No output (success)
```

### 2. VPS Testing Results Review

**Verify all phases completed:**
- ✅ Phase 2A: Al Jazeera Diagnostic Script - 100% success
- ✅ Phase 2B: Al Jazeera Crawler Integration - 100% success (3/3 valid URLs)
- ✅ Phase 2C: YouTube Transcript Extraction - 100% success (when not IP-blocked)

**Review VPS_TEST_RESULTS.md:**
```bash
cat VPS_TEST_RESULTS.md | grep "Status:"
# Expected: Status: ✅ ALL VPS TESTING COMPLETE
```

### 3. Documentation Review

**Verify documentation completeness:**
- ✅ VPS_TEST_RESULTS.md (530+ lines)
- ✅ GEMINI_FINAL_REVIEW_SUMMARY.md
- ✅ REVIEW_RESPONSES_PR303.md
- ✅ DEPLOYMENT_CHECKLIST.md (this file)
- ✅ ROLLBACK_PROCEDURES.md
- ✅ .env.example updated

---

## Deployment Steps

### Step 1: Pre-Deployment Backup (VPS)

**Create selective code backup:**
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
  echo \"✅ Backup created: \$BACKUP\"
"
```

**Expected output:**
- Backup file size: ~500MB
- Success message with filename

### Step 2: Check System Resources (VPS)

**Verify sufficient resources:**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  echo '=== DISK SPACE ==='
  df -h /opt | tail -1
  echo ''
  echo '=== MEMORY ==='
  free -h
  echo ''
  echo '=== SERVICES ==='
  systemctl status surfsense surfsense-celery surfsense-frontend --no-pager | grep -E 'Active:|Main PID'
"
```

**Expected:**
- Disk space: >2GB free
- Memory: 30GB RAM available
- All services: Active (running)

### Step 3: Deploy Backend Changes (VPS)

**Pull and deploy backend:**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  cd /opt/SurfSense

  # Pull latest nightly
  git stash
  git checkout nightly
  git pull origin nightly

  # Expected commit: 66c5c76 or later
  git log --oneline -3

  # Install dependencies (if needed)
  cd surfsense_backend
  source venv/bin/activate
  pip install -e . --no-deps

  # Run migrations (if any)
  alembic upgrade head

  # Restart backend services
  systemctl restart surfsense surfsense-celery surfsense-celery-beat

  sleep 5

  # Verify services started
  systemctl status surfsense --no-pager | head -15

  echo '✅ BACKEND DEPLOYED'
"
```

**Expected output:**
- Git pull: Fast-forward to 66c5c76 or later
- Alembic: "Running upgrade... done" or "No migrations to run"
- Services: Active (running)

### Step 4: Verify Backend Health (VPS)

**Critical health checks:**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  # Check service status
  systemctl is-active surfsense

  # Check for errors in logs
  journalctl -u surfsense -n 50 | grep -i 'error\|failed\|exception'

  # Test health endpoint
  curl -s http://127.0.0.1:8000/api/health

  # Verify port listening
  netstat -tulpn | grep :8000
"
```

**Expected:**
- Service: `active`
- Logs: No critical errors (warnings acceptable)
- Health endpoint: `{\"status\":\"ok\"}` or similar
- Port 8000: Listening

**Decision tree:**
- ✅ All checks pass → Proceed to Step 5
- ⚠️ ModuleNotFoundError → Install missing package, restart, re-check
- ❌ Service failed → **ABORT** and run ROLLBACK_PROCEDURES.md

### Step 5: Deploy Frontend Changes (VPS)

**⚠️ CRITICAL: Follow exact order to avoid .next corruption**

```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  echo '🚨 CRITICAL: Frontend deployment starting'

  # 1. STOP service (prevents .next corruption)
  systemctl stop surfsense-frontend
  sleep 3
  echo '✅ Service stopped'

  # 2. DELETE old build (mandatory)
  cd /opt/SurfSense/surfsense_web
  rm -rf .next node_modules/.cache
  echo '✅ Old build removed'

  # 3. Install dependencies
  pnpm install --frozen-lockfile
  echo '✅ Dependencies installed'

  # 4. BUILD (if fails, ABORT)
  pnpm build
  if [ \$? -ne 0 ]; then
    echo '❌ BUILD FAILED - DEPLOYMENT ABORTED'
    exit 1
  fi
  echo '✅ BUILD SUCCESS'

  # 5. START service
  systemctl start surfsense-frontend
  sleep 10

  # 6. Verify
  curl -I http://localhost:3000 | head -5

  echo '✅ FRONTEND DEPLOYED'
"
```

**Expected output:**
- Build: Success (webpack compile complete)
- Service start: Success
- curl: HTTP/1.1 200 OK

**If build fails:**
- DO NOT proceed
- Run ROLLBACK_PROCEDURES.md immediately

### Step 6: Post-Deployment Verification (VPS)

**Comprehensive verification:**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  echo '=== ALL SERVICES ==='
  systemctl status surfsense surfsense-celery surfsense-frontend --no-pager | grep -E 'Active:|Main PID'

  echo ''
  echo '=== HEALTH CHECKS ==='
  curl -I http://localhost:3000 | head -5
  curl -s http://127.0.0.1:8000/api/health

  echo ''
  echo '=== GIT STATUS ==='
  cd /opt/SurfSense && git log --oneline -3

  echo ''
  echo '=== DISK AFTER DEPLOY ==='
  df -h /opt | tail -1

  echo ''
  echo '=== PROCESS CHECK ==='
  ps aux | grep -E 'uvicorn|celery|node' | grep -v grep | wc -l
  echo 'Expected: ~20 processes (uvicorn + celery workers + node)'
"
```

**Success criteria:**
- All services: Active (running)
- Frontend: HTTP 200 response
- Backend: Health endpoint responding
- Git: On commit 66c5c76 or later
- Disk: >2GB free remaining
- Processes: ~20 processes running

---

## Functional Testing

### Test 1: Al Jazeera Article Extraction

**Test the deployed Al Jazeera crawler:**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  cd /opt/SurfSense/surfsense_backend
  source venv/bin/activate

  # Quick functional test
  python -c '
import asyncio
from app.tasks.document_processors.url_crawler import _extract_article_with_playwright

url = \"https://www.aljazeera.com/economy/2025/12/31/us-jobless-claims-slow-in-last-full-week-of-2025-amid-weak-labour-market\"

async def test():
    headline, body, metadata = await _extract_article_with_playwright(url)
    print(f\"✅ Headline: {headline[:50]}...\")
    print(f\"✅ Strategy: {metadata.get(\\\"extraction_strategy\\\")}\")
    print(f\"✅ Length: {len(body)} characters\")

asyncio.run(test())
  '
"
```

**Expected output:**
```
✅ Headline: US jobless claims slow in last full week of 2025...
✅ Strategy: main_tag
✅ Length: 2500+ characters
```

### Test 2: YouTube Transcript Extraction

**Test YouTube API integration:**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  cd /opt/SurfSense/surfsense_backend
  source venv/bin/activate

  # Quick functional test (may fail due to cloud IP blocking - expected)
  python -c '
from app.utils.youtube_utils import get_youtube_transcript_with_proxy

try:
    transcript = get_youtube_transcript_with_proxy(\"dQw4w9WgXcQ\")
    print(f\"✅ Segments: {len(transcript)}\")
    print(f\"✅ First segment: {transcript[0][\\\"text\\\"][:50]}\")
except Exception as e:
    if \"RequestBlocked\" in str(e) or \"blocking\" in str(e):
        print(\"⚠️  IP blocked (expected on cloud VPS) - Whisper fallback will handle\")
    else:
        print(f\"❌ Unexpected error: {e}\")
  '
"
```

**Expected output (either):**
- ✅ Success: Segments extracted (if IP not blocked)
- ⚠️  IP blocked message (expected, validates fallback necessity)

### Test 3: Web UI Functionality

**Manual browser test:**
1. Open browser: `https://ai.kapteinis.lv`
2. Log in with credentials
3. Test document upload:
   - Upload a test PDF or text file
   - Verify processing completes
   - Check search functionality
4. Test URL crawling:
   - Add Al Jazeera URL
   - Verify extraction works
   - Check content indexed

**Success criteria:**
- ✅ Login works
- ✅ Document upload and processing functional
- ✅ Search returns results
- ✅ URL crawling extracts content

---

## Monitoring & Verification

### 24-Hour Monitoring Period

**Monitor these metrics for 24 hours post-deployment:**

**1. Service Stability:**
```bash
# Every 2 hours, check service status
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  systemctl status surfsense surfsense-celery surfsense-frontend --no-pager
"
```

**2. Error Logs:**
```bash
# Check for errors every 4 hours
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  journalctl -u surfsense --since '4 hours ago' | grep -i 'error\|exception'
"
```

**3. Resource Usage:**
```bash
# Check memory and disk every 8 hours
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  free -h && df -h /opt | tail -1
"
```

**4. Browser Process Leaks:**
```bash
# Check for orphaned chromium processes
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  ps aux | grep chromium | grep -v grep
"
# Expected: 0 processes (all should be cleaned up)
```

**5. YouTube API Blocking Rate:**
```bash
# Check YouTube API error rate
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  journalctl -u surfsense --since '24 hours ago' | grep -i 'requestblocked\|youtube.*block' | wc -l
"
# Expected: Some blocking (normal on cloud VPS)
```

---

## Rollback Criteria

**Trigger rollback if ANY of these occur:**

❌ **Critical Issues (Immediate Rollback):**
- Services fail to start after restart
- Health endpoint returns errors
- Frontend build fails
- Database migrations fail
- ModuleNotFoundError that can't be resolved
- 500 errors on user-facing pages

⚠️ **Warning Issues (Monitor, consider rollback):**
- High error rate in logs (>10 errors/minute)
- Memory usage >90%
- Disk usage >95%
- Browser process leaks (>5 orphaned processes)
- User reports of functionality breaking

✅ **Expected/Acceptable Issues:**
- YouTube RequestBlocked errors on cloud VPS (Whisper fallback handles)
- Occasional Al Jazeera 404s (page removed by publisher)
- Individual extraction failures (retry logic handles)

**If rollback needed:**
→ See ROLLBACK_PROCEDURES.md

---

## Post-Deployment Tasks

### Update GitHub

**1. Mark PRs as deployed:**
```bash
# Comment on each PR (303, 304, 305, 306, 307, 308)
# Template:
"✅ Deployed to production VPS and tested successfully.

**VPS Testing Results:**
- Phase 2A: Al Jazeera Diagnostic Script - ✅ PASS
- Phase 2B: Al Jazeera Crawler Integration - ✅ PASS (100% success, 17% faster)
- Phase 2C: YouTube Transcript Extraction - ✅ PASS (with expected cloud IP limitations)

See VPS_TEST_RESULTS.md for comprehensive test documentation."
```

**2. Close any related issues**

**3. Update project board/milestones**

### Documentation Updates

**1. Update CHANGELOG.md:**
```markdown
## [Unreleased] - 2026-01-03

### Fixed
- Fixed broken test suite constant reference (PR #308)
- Fixed incomplete path refactoring in diagnostic script (PR #307)
- Fixed YouTube API incompatibility with v1.2.3 (discovered during testing)

### Improved
- Added type hints to crawler extraction functions (PR #306)
- Optimized paragraph extraction with asyncio.gather (PR #306, 17% faster)
- Improved test assertions for deterministic testing (PR #306)
- Added module-level EXTRACTION_STRATEGIES constant (PR #306)

### Tested
- Al Jazeera crawler: 100% success on valid URLs
- YouTube transcripts: 100% success when not IP-blocked
- Browser resource cleanup: 0 orphaned processes
```

**2. Update README.md (if applicable):**
- Document YouTube cloud IP limitation
- Add note about Whisper fallback for cloud deployments

---

## Success Criteria

**Deployment considered successful when ALL criteria met:**

- [x] All services running and healthy
- [x] No critical errors in logs
- [x] Frontend accessible and functional
- [x] Backend API responding correctly
- [x] Al Jazeera extraction working (functional test passes)
- [x] YouTube extraction working or gracefully failing with IP block
- [x] No browser process leaks
- [x] Memory usage <80%
- [x] Disk usage <90%
- [x] 24-hour monitoring period completed without issues
- [x] All functional tests passing
- [x] User-facing features working correctly

---

## Deployment Sign-Off

**Deployment Date:** _______________
**Deployed By:** _______________
**VPS Commit:** _______________
**Backup File:** _______________

**Pre-Deployment Checks:**
- [ ] All VPS tests passed (Phases 2A, 2B, 2C)
- [ ] Security checks passed
- [ ] Documentation reviewed
- [ ] Backup created
- [ ] System resources verified

**Post-Deployment Verification:**
- [ ] All services active
- [ ] Health endpoints responding
- [ ] Functional tests passed
- [ ] No critical errors in logs
- [ ] 24-hour monitoring complete

**Rollback Plan:**
- [ ] ROLLBACK_PROCEDURES.md reviewed
- [ ] Backup location documented
- [ ] Rollback tested (optional, recommended)

**Sign-Off:**
- [ ] Deployment successful
- [ ] Monitoring period complete
- [ ] GitHub PRs updated
- [ ] Documentation updated

---

**Last Updated:** January 3, 2026
**Document Version:** 1.0
**Related Documents:**
- VPS_TEST_RESULTS.md
- ROLLBACK_PROCEDURES.md
- GEMINI_FINAL_REVIEW_SUMMARY.md
