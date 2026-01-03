# Rollback Procedures - SurfSense Deployment

**Purpose:** Emergency rollback procedures for failed deployments
**Target Environment:** Production VPS (root@46.62.230.195)
**Documentation Date:** January 3, 2026

---

## When to Rollback

### Immediate Rollback Required

**Critical failures that require immediate rollback:**

❌ **Service Failures:**
- Backend service fails to start after deployment
- Frontend build fails during deployment
- Celery workers crash repeatedly
- Database migrations fail

❌ **Data Integrity Issues:**
- Database corruption detected
- Migration creates data inconsistencies
- User data loss or corruption

❌ **Functionality Breaks:**
- Login system broken
- Core features non-functional (search, upload, chat)
- 500 errors on main user flows
- API endpoints returning errors

❌ **Resource Exhaustion:**
- Memory usage spikes to >95%
- Disk fills up during deployment
- CPU at 100% sustained
- Browser process leaks (>20 orphaned chromium processes)

❌ **Security Issues:**
- Security vulnerability introduced
- Authentication bypass discovered
- Data exposure risk identified

### Consider Rollback

**Warning signs that may require rollback:**

⚠️ **Performance Degradation:**
- Response times >5x slower than before
- High error rate in logs (>10 errors/minute)
- Database query timeouts

⚠️ **Resource Issues:**
- Memory usage >90% sustained
- Disk usage >95%
- Swap usage increasing rapidly

⚠️ **User Impact:**
- Multiple user reports of broken functionality
- Critical features intermittently failing
- Data sync issues

### Do NOT Rollback For

**Expected issues that do NOT require rollback:**

✅ **Known Limitations:**
- YouTube RequestBlocked on cloud VPS (Whisper fallback handles)
- Occasional Al Jazeera 404 errors (page removed by publisher)
- Individual extraction failures (retry logic handles)

✅ **Minor Issues:**
- Warning messages in logs
- Non-critical feature degradation
- Cosmetic UI issues
- Temporary network issues

---

## Rollback Decision Tree

```
Deployment Issue Detected
│
├─ Service won't start?
│  ├─ Yes → IMMEDIATE ROLLBACK
│  └─ No → Continue
│
├─ Critical errors in logs?
│  ├─ Yes → IMMEDIATE ROLLBACK
│  └─ No → Continue
│
├─ Core features broken?
│  ├─ Yes → IMMEDIATE ROLLBACK
│  └─ No → Continue
│
├─ High resource usage?
│  ├─ >95% → IMMEDIATE ROLLBACK
│  ├─ >90% → Monitor for 10 minutes, then rollback if not improving
│  └─ <90% → Continue monitoring
│
├─ Performance degradation?
│  ├─ >10x slower → IMMEDIATE ROLLBACK
│  ├─ 5-10x slower → Monitor for 30 minutes, consider rollback
│  └─ <5x slower → Continue monitoring
│
└─ Known limitations only?
   └─ Continue with deployment, no rollback needed
```

---

## Rollback Procedures

### Option 1: Git Revert (Clean Rollback)

**Best for:** Clean deployments where git history is intact

**Step 1: Identify previous working commit**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  cd /opt/SurfSense

  # Show recent commits
  git log --oneline -10

  # Identify last known-good commit (before deployment)
  # Example: If current is 66c5c76 and it's broken, use previous commit
"
```

**Step 2: Stop services**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  systemctl stop surfsense surfsense-celery surfsense-frontend

  echo '✅ All services stopped'
"
```

**Step 3: Revert to previous commit**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  cd /opt/SurfSense

  # Replace PREVIOUS_COMMIT with actual hash
  PREVIOUS_COMMIT='8600084'  # Example: commit before 66c5c76

  git checkout \$PREVIOUS_COMMIT

  echo '✅ Reverted to commit:' \$PREVIOUS_COMMIT
  git log --oneline -3
"
```

**Step 4: Rollback database migrations (if any)**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  cd /opt/SurfSense/surfsense_backend
  source venv/bin/activate

  # Check current migration
  alembic current

  # Rollback to previous version (if migrations were run)
  # alembic downgrade -1

  echo '✅ Database migrations checked/rolled back'
"
```

**Step 5: Rebuild frontend**
```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  cd /opt/SurfSense/surfsense_web

  # Clean build
  rm -rf .next node_modules/.cache

  # Reinstall and rebuild
  pnpm install --frozen-lockfile
  pnpm build

  if [ \$? -ne 0 ]; then
    echo '❌ Frontend build failed during rollback!'
    exit 1
  fi

  echo '✅ Frontend rebuilt successfully'
"
```

**Step 6: Restart services**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  systemctl start surfsense surfsense-celery surfsense-frontend

  sleep 10

  systemctl status surfsense surfsense-frontend --no-pager | grep Active

  echo '✅ Services restarted'
"
```

**Step 7: Verify rollback**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "
  # Check all services
  systemctl is-active surfsense surfsense-celery surfsense-frontend

  # Test health endpoint
  curl -s http://127.0.0.1:8000/api/health

  # Test frontend
  curl -I http://localhost:3000 | head -1

  echo '✅ Rollback verification complete'
"
```

---

### Option 2: Restore from Backup (Emergency)

**Best for:** Critical failures, corrupted git state, or when Option 1 fails

**Step 1: Identify backup file**
```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  cd /opt

  # List available backups
  ls -lth surfsense_code_*.tar.gz | head -5

  # Identify the backup from BEFORE deployment
  # Example: surfsense_code_20260103_010500.tar.gz (from before deployment)
"
```

**Step 2: Stop all services**
```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  systemctl stop surfsense surfsense-celery surfsense-frontend

  # Verify stopped
  systemctl is-active surfsense surfsense-celery surfsense-frontend

  echo '✅ All services stopped'
"
```

**Step 3: Backup current state (in case rollback fails)**
```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  cd /opt

  # Create emergency backup of broken state
  EMERGENCY_BACKUP=surfsense_broken_\$(date +%Y%m%d_%H%M%S).tar.gz

  tar -czf \$EMERGENCY_BACKUP \
    --exclude='SurfSense/surfsense_backend/venv' \
    --exclude='SurfSense/surfsense_web/node_modules' \
    SurfSense

  echo '✅ Emergency backup created:' \$EMERGENCY_BACKUP
"
```

**Step 4: Restore from backup**
```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  cd /opt

  # Set backup file (replace with actual filename)
  BACKUP_FILE='surfsense_code_20260103_010500.tar.gz'

  # Remove current installation
  rm -rf SurfSense

  # Restore from backup
  tar -xzf \$BACKUP_FILE

  echo '✅ Restored from backup:' \$BACKUP_FILE
"
```

**Step 5: Reinstall dependencies**
```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  # Backend dependencies
  cd /opt/SurfSense/surfsense_backend
  source venv/bin/activate
  pip install -e . --no-deps

  # Frontend dependencies and build
  cd /opt/SurfSense/surfsense_web
  rm -rf .next node_modules
  pnpm install --frozen-lockfile
  pnpm build

  echo '✅ Dependencies reinstalled and frontend rebuilt'
"
```

**Step 6: Rollback database (if needed)**
```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  cd /opt/SurfSense/surfsense_backend
  source venv/bin/activate

  # Check migration state
  alembic current

  # If migrations need rollback, do it manually
  # alembic downgrade <target_revision>

  echo '✅ Database state verified'
"
```

**Step 7: Restart services**
```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  systemctl start surfsense surfsense-celery surfsense-frontend

  sleep 15

  systemctl status surfsense surfsense-celery surfsense-frontend --no-pager | grep Active

  echo '✅ Services restarted after restore'
"
```

**Step 8: Comprehensive verification**
```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  echo '=== SERVICE STATUS ==='
  systemctl is-active surfsense surfsense-celery surfsense-frontend

  echo ''
  echo '=== HEALTH CHECKS ==='
  curl -s http://127.0.0.1:8000/api/health
  curl -I http://localhost:3000 | head -1

  echo ''
  echo '=== GIT STATUS ==='
  cd /opt/SurfSense && git log --oneline -3

  echo ''
  echo '=== DISK SPACE ==='
  df -h /opt | tail -1

  echo '✅ Rollback from backup complete'
"
```

---

### Option 3: Partial Rollback (Specific Components)

**Best for:** Issues isolated to specific components

#### 3A: Rollback Backend Only

```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  cd /opt/SurfSense

  # Stop backend services
  systemctl stop surfsense surfsense-celery

  # Revert backend code
  cd surfsense_backend
  git checkout <previous_commit> -- app/ scripts/ tests/

  # Reinstall dependencies
  source venv/bin/activate
  pip install -e . --no-deps

  # Rollback migrations if needed
  alembic downgrade -1

  # Restart
  systemctl start surfsense surfsense-celery

  echo '✅ Backend rolled back'
"
```

#### 3B: Rollback Frontend Only

```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  cd /opt/SurfSense

  # Stop frontend
  systemctl stop surfsense-frontend

  # Revert frontend code
  cd surfsense_web
  git checkout <previous_commit> -- .

  # Clean and rebuild
  rm -rf .next node_modules/.cache
  pnpm install --frozen-lockfile
  pnpm build

  # Restart
  systemctl start surfsense-frontend

  echo '✅ Frontend rolled back'
"
```

---

## Post-Rollback Verification

### Verification Checklist

**After rollback, verify ALL of the following:**

**1. Services Running:**
```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  systemctl status surfsense surfsense-celery surfsense-frontend --no-pager | grep -E 'Active:|Main PID'
"
```
Expected: All services `Active: active (running)`

**2. Health Endpoints:**
```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  curl -s http://127.0.0.1:8000/api/health
  curl -I http://localhost:3000 | head -1
"
```
Expected: Health endpoint returns OK, frontend returns 200

**3. No Critical Errors:**
```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  journalctl -u surfsense -n 100 | grep -i 'error\|exception' | head -20
"
```
Expected: No critical errors (warnings acceptable)

**4. Database Accessible:**
```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  cd /opt/SurfSense/surfsense_backend
  source venv/bin/activate
  python -c 'from app.database import get_db; next(get_db()); print(\"✅ Database accessible\")'
"
```
Expected: Database accessible message

**5. Core Functionality:**
- [ ] Can log in via web UI
- [ ] Can upload document
- [ ] Can search for content
- [ ] Can view documents
- [ ] Chat functionality works

**6. Resource Usage Normal:**
```bash
ssh -i ~/.ssh/id_ed25319_surfsense root@46.62.230.195 "
  free -h
  df -h /opt | tail -1
"
```
Expected: Memory <80%, disk <90%

---

## Database Rollback

### Understanding Alembic Migrations

**Check current migration:**
```bash
cd /opt/SurfSense/surfsense_backend
source venv/bin/activate
alembic current
```

**View migration history:**
```bash
alembic history --verbose
```

**Downgrade one version:**
```bash
alembic downgrade -1
```

**Downgrade to specific version:**
```bash
alembic downgrade <revision_id>
```

### Database Rollback Scenarios

**Scenario 1: Migration added new columns**
- Safe to rollback with `alembic downgrade -1`
- No data loss (assuming migration includes downgrade logic)

**Scenario 2: Migration modified existing data**
- ⚠️ Potential data loss
- Verify downgrade migration has data preservation logic
- Consider manual SQL rollback if needed

**Scenario 3: Migration deleted columns**
- ❌ Cannot safely rollback (data already lost)
- May need database restore from backup

**Scenario 4: No migrations in deployment**
- No database rollback needed
- Proceed with code rollback only

---

## Communication Templates

### Internal Team Notification

**Subject:** ROLLBACK: SurfSense Production Deployment

```
ALERT: Production deployment rolled back

Time: [TIMESTAMP]
Reason: [BRIEF DESCRIPTION OF ISSUE]
Rollback Method: [Git Revert / Backup Restore / Partial]
Current Status: [Services Status]

Actions Taken:
1. [Action 1]
2. [Action 2]
3. [Action 3]

Current State:
- Services: [Running/Stopped]
- Health: [OK/Degraded]
- Users Affected: [Yes/No/Unknown]

Next Steps:
1. [Next Step 1]
2. [Next Step 2]

Incident Owner: [Name]
```

### User Communication (if needed)

**For brief outages (<5 minutes):**
- Usually no communication needed
- Monitor for user reports

**For extended outages (>5 minutes):**

**Subject:** Brief Service Interruption - Resolved

```
Hi,

We experienced a brief service interruption while deploying updates.
The issue has been resolved and all services are now operating normally.

Duration: Approximately [X] minutes
Impact: [Description of what users may have experienced]
Resolution: [Brief non-technical explanation]

We apologize for any inconvenience.

If you continue to experience issues, please contact support.
```

---

## Rollback Testing (Optional but Recommended)

### Dry Run Procedure

**Test rollback on staging/development environment:**

1. Deploy same changes to staging
2. Verify functionality
3. Practice rollback procedure
4. Document any issues encountered
5. Update procedures based on findings

**Benefits:**
- Validates rollback procedures work
- Identifies potential issues before production
- Builds confidence in rollback process
- Documents actual rollback time

---

## Post-Rollback Analysis

### Root Cause Analysis

**After successful rollback, perform RCA:**

1. **What went wrong?**
   - Identify exact failure point
   - Collect error logs and stack traces
   - Document environmental factors

2. **Why did it happen?**
   - Missing test coverage?
   - Environmental difference (dev vs prod)?
   - Timing issue?
   - Resource constraint?

3. **How to prevent?**
   - Add tests
   - Update deployment checklist
   - Improve staging environment
   - Add monitoring/alerts

### Document Lessons Learned

**Update documentation:**
- Add discovered issue to DEPLOYMENT_CHECKLIST.md
- Update ROLLBACK_PROCEDURES.md with any new findings
- Create incident report (if significant)
- Share learnings with team

---

## Rollback Log Template

**Maintain a rollback log for tracking:**

```markdown
## Rollback Log Entry

**Date/Time:** YYYY-MM-DD HH:MM UTC
**Deployment:** [Deployment ID/PR numbers]
**Rollback Reason:** [Brief description]
**Rollback Method:** [Git Revert / Backup Restore / Partial]
**Duration:** [How long rollback took]
**Downtime:** [How long services were down]

**Issue Details:**
- **Trigger:** [What first indicated a problem]
- **Root Cause:** [What actually went wrong]
- **User Impact:** [How many users affected, what functionality broken]

**Rollback Steps:**
1. [Step 1 with timestamp]
2. [Step 2 with timestamp]
3. [Step 3 with timestamp]

**Verification Results:**
- Services: [Status]
- Health checks: [Results]
- Functionality: [Status]

**Lessons Learned:**
- [Lesson 1]
- [Lesson 2]

**Follow-up Actions:**
- [ ] [Action item 1]
- [ ] [Action item 2]

**Sign-off:** [Name]
```

---

## Quick Reference Card

### Emergency Rollback Commands

**Stop services:**
```bash
systemctl stop surfsense surfsense-celery surfsense-frontend
```

**Revert to previous commit:**
```bash
cd /opt/SurfSense && git checkout <PREVIOUS_COMMIT>
```

**Restore from backup:**
```bash
cd /opt && rm -rf SurfSense && tar -xzf <BACKUP_FILE>
```

**Rebuild frontend:**
```bash
cd /opt/SurfSense/surfsense_web && rm -rf .next && pnpm build
```

**Start services:**
```bash
systemctl start surfsense surfsense-celery surfsense-frontend
```

**Verify:**
```bash
systemctl status surfsense surfsense-frontend --no-pager
curl -s http://127.0.0.1:8000/api/health
curl -I http://localhost:3000
```

---

**Last Updated:** January 3, 2026
**Document Version:** 1.0
**Related Documents:**
- DEPLOYMENT_CHECKLIST.md
- VPS_TEST_RESULTS.md
- GEMINI_FINAL_REVIEW_SUMMARY.md
