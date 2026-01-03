# Stuck Documents Analysis and Recovery Plan

**Date**: 2026-01-03
**Status**: 🔴 CRITICAL - 75 Tasks Stuck, 191 Failed Tasks
**Impact**: Documents submitted by users never completed processing

---

## Executive Summary

Investigation revealed a **critical issue** with document processing:

### Key Findings

| Metric | Count | Status |
|--------|-------|--------|
| **Stuck Tasks (IN_PROGRESS)** | **75** | 🔴 Critical |
| **Failed Tasks** | **191** | ⚠️ Warning |
| **Successful Tasks** | **2,067** | ✅ Good |
| **Completion Rate** | **88.6%** | ⚠️ Below target |

### Root Cause

Tasks enter "IN_PROGRESS" status but **never complete** due to:
1. **Worker crashes/restarts** without status cleanup
2. **Timeout exceptions** not properly handled
3. **Event loop issues** in async task processing
4. **External service failures** (URL crawling, file parsing)

**Oldest stuck task**: December 4, 2025 (1 month ago!)

---

## Detailed Analysis

### Tasks by Status

```sql
 count |   status
-------+-------------
    75 | IN_PROGRESS  ← 🔴 STUCK TASKS
  2067 | SUCCESS
   191 | FAILED
     1 | DISMISSED
```

### Sample Stuck Tasks

From most recent query (50 non-success tasks):

**Common patterns:**
1. **URL Crawling stuck**:
   - lsm.lv URLs (Latvian news)
   - meduza.io URLs (Russian news)
   - aljazeera.com URLs

2. **Retry loops**:
   ```
   "Retrying task (retry #1)..."
   "Retrying task (retry #2)..."
   ```
   Tasks show retry attempts but remain stuck in IN_PROGRESS

3. **File processing stuck**:
   - PDF files from Britannica
   - Audio file transcription

### Tasks Distribution by Search Space

**Space 90** (user-reported issue):
- Documents: 2
- Logs: 4 (all SUCCESS)
- Status: ✅ No stuck tasks

**Other spaces with stuck tasks**:
- Space 2: Multiple stuck URL crawls
- Space 11: Multiple stuck URL crawls
- Space 15: Multiple stuck URL crawls
- Space 36, 61, 62, 79, 82: Retrying but stuck

---

## Impact Assessment

### User-Reported Issue (Space 90)

User statement: *"I for sure know that for this one I submitted more than there are visible"*

**Database evidence**:
```sql
search_space_id = 90
Documents: 2
Logs: 4 (all SUCCESS)
```

**Analysis**:
- All submitted tasks for Space 90 completed successfully
- No stuck or failed tasks found
- **Possible explanations**:
  1. User submitted via UI but tasks never reached Celery
  2. Tasks failed before logging (pre-database insertion)
  3. User submitted to different space by mistake
  4. Browser error prevented submission

**Recommendation**: Check browser DevTools Network tab when submitting to verify API calls succeed.

### System-Wide Impact

**75 stuck tasks** means:
- Users submitted URLs/files that never processed
- No error notification to users (tasks appear "processing" forever)
- Wasted resources (tasks holding database rows)
- Misleading UI state

**191 failed tasks** with FAILED status are actually better - at least users know they failed!

---

## Technical Root Causes

### 1. Worker Restarts Without Cleanup

**Evidence**: `systemctl status surfsense-celery` shows multiple PID changes

**Behavior**:
- Worker starts task → Sets status to "IN_PROGRESS"
- Worker crashes/restarts (e.g., OOM, timeout)
- Status never updates to FAILED or SUCCESS
- Task remains IN_PROGRESS forever

**Example from service status**:
```
Tasks: 6 (limit: 37532)
Memory: 1.5G (peak: 2G)  ← Near memory limit
CPU: 12min 46.472s
```

### 2. Timeout Handling Issues

**Code analysis** (`document_tasks.py`):
```python
CRAWL_URL_SOFT_TIMEOUT = 1200  # 20 minutes
CRAWL_URL_HARD_TIMEOUT = 1500  # 25 minutes

YOUTUBE_VIDEO_SOFT_TIMEOUT = 1800  # 30 minutes
YOUTUBE_VIDEO_HARD_TIMEOUT = 2100  # 35 minutes

FILE_UPLOAD_SOFT_TIMEOUT = 3600  # 60 minutes
FILE_UPLOAD_HARD_TIMEOUT = 4200  # 70 minutes
```

**Problem**:
- Hard timeout **kills the task** without cleanup
- Status remains IN_PROGRESS
- No error logged to `logs` table

### 3. External Service Failures

**Failed URL patterns**:
- aljazeera.com videos (likely blocking bots)
- meduza.io (Russian site, may have geoblocking)
- Wikipedia pages (rare, may be rate limiting)

**Failed file patterns**:
- Large PDFs from Britannica
- Audio files requiring transcription

### 4. Retry Logic Issues

**Evidence from logs**:
```
IN_PROGRESS | Retrying task (retry #1)...
IN_PROGRESS | Retrying task (retry #2)...
```

Tasks show retries but never resolve to SUCCESS or FAILED.

---

## Recovery Plan

### Phase 1: Immediate Cleanup (Clean stuck tasks)

**⚠️ WARNING**: This will mark stuck tasks as FAILED. Users will see "failed" status instead of indefinite "processing".

```bash
# Connect to VPS
ssh -i ~/.ssh/<SSH_KEY> <USER>@<VPS_IP>

# Mark all IN_PROGRESS tasks older than 1 hour as FAILED
sudo -u postgres psql surfsense <<'EOF'
UPDATE logs
SET
    status = 'FAILED',
    message = message || ' [Auto-failed: Task exceeded timeout and was stuck in IN_PROGRESS]',
    updated_at = NOW()
WHERE
    status = 'IN_PROGRESS'
    AND created_at < NOW() - INTERVAL '1 hour';

-- Show what was updated
SELECT COUNT(*) as cleaned_tasks FROM logs
WHERE status = 'FAILED'
  AND message LIKE '%Auto-failed: Task exceeded timeout%';
EOF
```

**Expected result**: ~75 tasks marked as FAILED

### Phase 2: Verify Celery Worker Health

```bash
# Check worker status
systemctl status surfsense-celery

# Check for duplicate workers (should only see one node)
cd /opt/SurfSense/surfsense_backend
source venv/bin/activate
celery -A app.celery_app inspect active

# If you see "DuplicateNodenameWarning", restart worker:
systemctl restart surfsense-celery
sleep 10
systemctl status surfsense-celery
```

### Phase 3: Monitor for New Stuck Tasks

```bash
# Run this every hour to catch new stuck tasks
sudo -u postgres psql surfsense <<'EOF'
SELECT
    id,
    search_space_id,
    source,
    message,
    created_at,
    NOW() - created_at as stuck_duration
FROM logs
WHERE status = 'IN_PROGRESS'
  AND created_at < NOW() - INTERVAL '1 hour'
ORDER BY created_at ASC;
EOF
```

**Set up cron job** (optional):
```bash
# Add to /etc/cron.hourly/cleanup_stuck_tasks.sh
#!/bin/bash
sudo -u postgres psql surfsense -c "
UPDATE logs
SET status = 'FAILED',
    message = message || ' [Auto-failed: Timeout cleanup]',
    updated_at = NOW()
WHERE status = 'IN_PROGRESS'
  AND created_at < NOW() - INTERVAL '2 hours';"

chmod +x /etc/cron.hourly/cleanup_stuck_tasks.sh
```

---

## Long-Term Fixes

### Fix 1: Add Timeout Signal Handlers

**File**: `surfsense_backend/app/tasks/celery_tasks/document_tasks.py`

**Problem**: Hard timeouts kill tasks without cleanup

**Solution**: Handle SoftTimeLimitExceeded exception

```python
from celery.exceptions import SoftTimeLimitExceeded

@celery_app.task(
    name="process_crawled_url",
    bind=True,
    soft_time_limit=CRAWL_URL_SOFT_TIMEOUT,
    time_limit=CRAWL_URL_HARD_TIMEOUT,
)
def process_crawled_url_task(self, url: str, search_space_id: int, user_id: str):
    """Process crawled URL with proper timeout handling."""
    import asyncio
    from app.services.task_logging_service import TaskLoggingService

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _process_crawled_url(url, search_space_id, user_id)
        )
    except SoftTimeLimitExceeded:
        # Log failure before hard timeout kills us
        async def log_timeout():
            async with get_celery_session_maker()() as session:
                task_logger = TaskLoggingService(session, search_space_id)
                await task_logger.log_task_failure(
                    task_name="process_crawled_url",
                    source="document_processor",
                    message=f"Task exceeded soft timeout ({CRAWL_URL_SOFT_TIMEOUT}s) for URL: {url}",
                    error=f"SoftTimeLimitExceeded after {CRAWL_URL_SOFT_TIMEOUT}s"
                )
                await session.commit()

        loop.run_until_complete(log_timeout())
        raise  # Re-raise to let Celery know task failed
    except Exception as e:
        # Handle other exceptions
        logger.error(f"Task failed with exception: {e}", exc_info=True)
        raise
    finally:
        loop.close()
```

Apply to all task functions:
- `process_extension_document_task`
- `process_crawled_url_task`
- `process_youtube_video_task`
- `process_file_upload_task`

### Fix 2: Add Task Heartbeat Mechanism

**New file**: `surfsense_backend/app/tasks/task_heartbeat.py`

```python
"""
Task heartbeat mechanism to detect and cleanup stuck tasks.
"""
from celery import shared_task
from sqlalchemy import select, and_
from datetime import datetime, timedelta
from app.db import get_async_session
from app.models import Log  # Assuming logs table model

@shared_task(name="cleanup_stuck_tasks")
async def cleanup_stuck_tasks():
    """
    Cleanup tasks stuck in IN_PROGRESS for more than 2 hours.
    Runs every hour via Celery Beat.
    """
    cutoff_time = datetime.now() - timedelta(hours=2)

    async with get_async_session() as session:
        # Find stuck tasks
        result = await session.execute(
            select(Log).where(
                and_(
                    Log.status == "IN_PROGRESS",
                    Log.created_at < cutoff_time
                )
            )
        )
        stuck_logs = result.scalars().all()

        # Mark as failed
        for log in stuck_logs:
            log.status = "FAILED"
            log.message += " [Auto-failed: Task exceeded maximum processing time]"
            log.updated_at = datetime.now()

        await session.commit()
        return f"Cleaned up {len(stuck_logs)} stuck tasks"
```

**Configure in Celery Beat** (`surfsense_backend/app/celery_app.py`):

```python
app.conf.beat_schedule = {
    # ... existing schedules ...
    'cleanup-stuck-tasks': {
        'task': 'cleanup_stuck_tasks',
        'schedule': 3600.0,  # Every hour
    },
}
```

### Fix 3: Improve Task Logging

**Current issue**: Tasks fail before creating log entry

**Solution**: Create log entry BEFORE processing starts

```python
async def _process_crawled_url(url: str, search_space_id: int, user_id: str):
    """Process crawled URL with immediate logging."""
    async with get_celery_session_maker()() as session:
        task_logger = TaskLoggingService(session, search_space_id)

        # Create log entry IMMEDIATELY (with IN_PROGRESS status)
        log_entry = await task_logger.log_task_start(
            task_name="process_crawled_url",
            source="document_processor",
            message=f"Starting URL crawling and processing for: {url}",
            metadata={"url": url}
        )
        await session.commit()  # Commit immediately so it's visible

        try:
            # ... actual processing ...

            # Update to SUCCESS
            await task_logger.log_task_success(
                log_id=log_entry.id,
                message=f"Successfully crawled and processed URL: {url}"
            )
            await session.commit()

        except Exception as e:
            # Update to FAILED
            await task_logger.log_task_failure(
                log_id=log_entry.id,
                message=f"Failed to crawl URL: {url}",
                error=str(e)
            )
            await session.commit()
            raise
```

### Fix 4: Add Retry Limits

**Current issue**: Tasks retry indefinitely

**Solution**: Set max retries in task decorator

```python
@celery_app.task(
    name="process_crawled_url",
    bind=True,
    max_retries=3,  # ← Add this
    default_retry_delay=60,  # Wait 1 minute between retries
    autoretry_for=(Exception,),  # Auto-retry on exceptions
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=600,  # Max 10 minutes backoff
    retry_jitter=True,  # Add randomness to avoid thundering herd
)
def process_crawled_url_task(self, url: str, search_space_id: int, user_id: str):
    # ... task code ...
```

---

## Prevention Measures

### 1. Resource Monitoring

**Set up alerts** for:
- Celery worker memory usage > 1.8GB (near 2GB limit)
- Number of IN_PROGRESS tasks > 10
- Task duration > soft timeout

**Tools**:
- Prometheus + Grafana
- Flower (Celery monitoring): `celery -A app.celery_app flower`
- Custom health check endpoint

### 2. Worker Configuration

**File**: `/etc/systemd/system/surfsense-celery.service`

**Add memory limits** and auto-restart:

```ini
[Service]
# ... existing config ...

# Memory limits
MemoryMax=2.5G
MemoryHigh=2G

# Auto-restart on failure
Restart=on-failure
RestartSec=10s

# Worker timeout (kill if unresponsive)
TimeoutStopSec=30s

# Log to journald with task IDs
StandardOutput=journal
StandardError=journal
```

Reload and restart:
```bash
systemctl daemon-reload
systemctl restart surfsense-celery
```

### 3. Task Timeout Configuration

**Reduce timeouts** to fail faster:

```python
# Old (too long)
CRAWL_URL_SOFT_TIMEOUT = 1200  # 20 minutes
CRAWL_URL_HARD_TIMEOUT = 1500  # 25 minutes

# New (recommended)
CRAWL_URL_SOFT_TIMEOUT = 300   # 5 minutes
CRAWL_URL_HARD_TIMEOUT = 420   # 7 minutes
```

Most URL crawls should complete in <5 minutes. If they don't, they're likely stuck.

### 4. User Notification

**Frontend improvement**: Show task status in real-time

**Add WebSocket notifications**:
```typescript
// In frontend
useEffect(() => {
  const ws = new WebSocket(`wss://ai.kapteinis.lv/ws/tasks/${searchSpaceId}`);

  ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    if (update.status === 'FAILED') {
      toast.error(`Document processing failed: ${update.message}`);
      // Refresh document list
      refreshDocuments();
    }
  };

  return () => ws.close();
}, [searchSpaceId]);
```

---

## Deployment Checklist

### Immediate Actions (Today)

- [ ] Run Phase 1 cleanup SQL (mark 75 stuck tasks as FAILED)
- [ ] Verify Celery worker health
- [ ] Set up hourly monitoring query
- [ ] Document process for user escalations

### Short-Term (This Week)

- [ ] Implement Fix 1: Add timeout signal handlers
- [ ] Implement Fix 2: Add task heartbeat mechanism
- [ ] Implement Fix 3: Improve task logging
- [ ] Test fixes in staging environment
- [ ] Deploy to production

### Medium-Term (This Month)

- [ ] Implement Fix 4: Add retry limits
- [ ] Set up Flower monitoring UI
- [ ] Configure memory limits in systemd
- [ ] Reduce task timeouts
- [ ] Add user notification system

### Long-Term (Next Quarter)

- [ ] Migrate to dedicated task queue server (separate from API server)
- [ ] Implement Prometheus + Grafana monitoring
- [ ] Add automated task cleanup cron job
- [ ] Create admin dashboard for task management

---

## Rollback Plan

If cleanup causes issues:

```bash
# Restore previous state (only if you have backup)
ssh -i ~/.ssh/<SSH_KEY> <USER>@<VPS_IP>

# Revert failed tasks back to IN_PROGRESS (NOT RECOMMENDED)
sudo -u postgres psql surfsense <<'EOF'
UPDATE logs
SET status = 'IN_PROGRESS',
    message = REPLACE(message, ' [Auto-failed: Task exceeded timeout and was stuck in IN_PROGRESS]', '')
WHERE message LIKE '%Auto-failed: Task exceeded timeout%';
EOF

# Better: Just restart Celery worker
systemctl restart surfsense-celery
```

---

## FAQ

### Q: Will cleanup delete any documents?

**A**: No. Cleanup only updates task log status. Documents already created will remain untouched.

### Q: What happens to tasks being processed right now?

**A**: The cleanup query only affects tasks older than 1 hour. Current tasks are safe.

### Q: How do I know if a URL failed due to timeout vs. actual error?

**A**: Check the `message` field in logs table:
- Timeout: "Task exceeded soft timeout"
- Actual error: Original error message from crawler

### Q: Can users resubmit failed URLs?

**A**: Yes. Users can resubmit any URL. The system will process it fresh.

### Q: Why not just delete failed log entries?

**A**: Failed logs provide audit trail and help identify problematic URLs/files for blocklisting.

---

## Commands Reference

### Query Stuck Tasks

```sql
-- All stuck tasks
SELECT * FROM logs WHERE status = 'IN_PROGRESS'
ORDER BY created_at ASC;

-- Stuck tasks by search space
SELECT search_space_id, COUNT(*) as stuck_count
FROM logs
WHERE status = 'IN_PROGRESS'
GROUP BY search_space_id
ORDER BY stuck_count DESC;

-- Stuck tasks older than 1 hour
SELECT id, search_space_id, source, message,
       NOW() - created_at as stuck_duration
FROM logs
WHERE status = 'IN_PROGRESS'
  AND created_at < NOW() - INTERVAL '1 hour';
```

### Cleanup Commands

```sql
-- Mark stuck tasks as failed (older than 1 hour)
UPDATE logs
SET status = 'FAILED',
    message = message || ' [Auto-failed: Timeout]',
    updated_at = NOW()
WHERE status = 'IN_PROGRESS'
  AND created_at < NOW() - INTERVAL '1 hour';

-- Mark specific task as failed
UPDATE logs
SET status = 'FAILED',
    message = 'Failed: Manually marked',
    updated_at = NOW()
WHERE id = 1234;
```

### Celery Commands

```bash
# Inspect active tasks
cd /opt/SurfSense/surfsense_backend
source venv/bin/activate
celery -A app.celery_app inspect active

# Check worker stats
celery -A app.celery_app inspect stats

# Purge all queued tasks (CAREFUL!)
celery -A app.celery_app purge

# Restart worker
systemctl restart surfsense-celery
```

---

## Contact & Escalation

**For stuck task issues:**
1. Check logs table first: `SELECT * FROM logs WHERE id = <task_id>;`
2. Check Celery worker logs: `journalctl -u surfsense-celery -n 100`
3. If task is truly stuck (>1 hour), run cleanup SQL
4. Notify user via email/UI that task failed and to resubmit

**For repeated failures of same URL:**
1. Check if URL is geoblocked or requires authentication
2. Add to blocklist if consistently failing
3. Update user with specific error reason

---

**Document Version**: 1.0
**Last Updated**: 2026-01-03
**Author**: Claude Code (Sonnet 4.5)
**Status**: Ready for implementation
