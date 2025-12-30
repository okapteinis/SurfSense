# SurfSense Deployment Guide
## Authentication & UI Enhancement Update - November 21, 2025

This guide covers deploying the authentication security fixes and UI enhancements to both local PC and production VPS.

---

## Pre-Deployment Checklist

- [ ] Backups completed (local + VPS)
- [ ] Pull request reviewed and merged to nightly
- [ ] Configuration files backed up
- [ ] Disk space verified
- [ ] Dependencies documented
- [ ] Rollback plan ready

---

## Part 1: Backup Current Installation

### Local PC Backup

```bash
# Navigate to project directory
cd /Users/ojarskapteinis/Documents/Kods

# Create backup with timestamp
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
cp -r SurfSense "SurfSense_backup_${BACKUP_DATE}"

# Verify backup
ls -lh "SurfSense_backup_${BACKUP_DATE}"

# Optional: Create archive
tar -czf "SurfSense_backup_${BACKUP_DATE}.tar.gz" "SurfSense_backup_${BACKUP_DATE}"
```

### VPS Backup

```bash
# SSH to VPS
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195

# Create backup
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
cd /opt
cp -r SurfSense "SurfSense_backup_${BACKUP_DATE}"

# Backup database (if applicable)
sudo -u postgres pg_dump surfsense > "/opt/surfsense_db_backup_${BACKUP_DATE}.sql"

# Backup configuration
cp /opt/SurfSense/surfsense_backend/.env "/opt/surfsense_backup_env_${BACKUP_DATE}"

# Verify backup
ls -lh "SurfSense_backup_${BACKUP_DATE}"
du -sh "SurfSense_backup_${BACKUP_DATE}"

# Optional: Create archive
tar -czf "SurfSense_backup_${BACKUP_DATE}.tar.gz" "SurfSense_backup_${BACKUP_DATE}"
```

---

## Part 2: Check Disk Space

### Local PC
```bash
df -h /Users/ojarskapteinis/Documents/Kods
```

### VPS
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 "df -h /opt && df -h /"
```

**Minimum Requirements:**
- Backend: ~500MB for dependencies
- Frontend: ~1GB for node_modules
- Total recommended: 5GB free space

---

## Part 3: Update Code from GitHub

### Local PC

```bash
cd /Users/ojarskapteinis/Documents/Kods/SurfSense

# Ensure you're on nightly branch
git checkout nightly

# Fetch latest changes
git fetch origin nightly

# Pull latest nightly (after PR is merged)
git pull origin nightly

# Verify the auth enhancement is included
git log --oneline -5
```

### VPS

```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195

cd /opt/SurfSense

# Ensure you're on nightly branch
git checkout nightly

# Fetch and pull latest
git fetch origin nightly
git pull origin nightly

# Verify update
git log --oneline -5
```

---

## Part 4: Install/Update Dependencies

### Backend (Python)

**Local PC:**
```bash
cd /Users/ojarskapteinis/Documents/Kods/SurfSense/surfsense_backend

# Activate virtual environment
source venv/bin/activate

# Install/update all dependencies from pyproject.toml
pip install -e .

# Verify critical packages
pip list | grep -E "(fastapi|litellm|langchain|uvicorn)"
```

**VPS:**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195

cd /opt/SurfSense/surfsense_backend

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install -e .

# Verify installation
pip list | head -20
```

### Frontend (Node.js)

**Local PC:**
```bash
cd /Users/ojarskapteinis/Documents/Kods/SurfSense/surfsense_web

# Install dependencies
npm install

# Or if using pnpm
pnpm install

# Build production bundle
pnpm build
```

**VPS:**
```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195

cd /opt/SurfSense/surfsense_web

# Install dependencies
pnpm install

# Build for production
pnpm build
```

---

## Part 5: Verify Configuration Files

### Backend Configuration

**Check and backup .env file:**

```bash
# Local
cat /Users/ojarskapteinis/Documents/Kods/SurfSense/surfsense_backend/.env | grep REGISTRATION

# VPS
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 \
  "cat /opt/SurfSense/surfsense_backend/.env | grep REGISTRATION"
```

**Critical Settings to Verify:**

```env
# Family/Private use settings
REGISTRATION_ENABLED=FALSE
DISABLE_REGISTRATION=true

# Database settings
DATABASE_URL=postgresql://...

# API Keys and secrets (should exist)
JWT_SECRET=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Backend URL
NEXT_PUBLIC_FASTAPI_BACKEND_URL=http://localhost:8000  # Local
NEXT_PUBLIC_FASTAPI_BACKEND_URL=https://yourdomain.com  # VPS
```

### Frontend Configuration

```bash
# Check frontend .env
cat /Users/ojarskapteinis/Documents/Kods/SurfSense/surfsense_web/.env

# VPS
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195 \
  "cat /opt/SurfSense/surfsense_web/.env"
```

---

## Part 6: Database Migrations

```bash
# Local
cd /Users/ojarskapteinis/Documents/Kods/SurfSense/surfsense_backend
source venv/bin/activate
alembic current
alembic upgrade head

# VPS
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195
cd /opt/SurfSense/surfsense_backend
source venv/bin/activate
alembic current
alembic upgrade head
```

---

## Part 7: Restart Services

### Local PC

**Backend:**
```bash
cd /Users/ojarskapteinis/Documents/Kods/SurfSense/surfsense_backend
source venv/bin/activate

# Stop existing process (if running)
pkill -f "uvicorn app.app:app"

# Start backend
uvicorn app.app:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd /Users/ojarskapteinis/Documents/Kods/SurfSense/surfsense_web

# Stop existing process
pkill -f "next dev"

# Start frontend
pnpm dev
```

### VPS (Production Services)

```bash
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195

# Restart backend
systemctl restart surfsense
systemctl status surfsense

# Restart frontend
systemctl restart surfsense-frontend
systemctl status surfsense-frontend

# Restart celery workers
systemctl restart surfsense-celery
systemctl status surfsense-celery

# Restart celery beat (scheduler)
systemctl restart surfsense-celery-beat
systemctl status surfsense-celery-beat
```

---

## Part 8: Verify Services

### Check Service Status (VPS)

```bash
# Check all services
systemctl status surfsense
systemctl status surfsense-frontend
systemctl status surfsense-celery
systemctl status surfsense-celery-beat

# Quick status check
systemctl is-active surfsense surfsense-frontend surfsense-celery surfsense-celery-beat
```

### Check Logs for Errors

**Backend logs:**
```bash
# VPS
journalctl -u surfsense -n 100 --no-pager

# Look for errors
journalctl -u surfsense -p err -n 50 --no-pager
```

**Frontend logs:**
```bash
# VPS
journalctl -u surfsense-frontend -n 100 --no-pager

# Look for errors
journalctl -u surfsense-frontend -p err -n 50 --no-pager
```

**Celery worker logs:**
```bash
# VPS
journalctl -u surfsense-celery -n 50 --no-pager
```

---

## Part 9: Test Critical Functionality

### 1. Test Authentication Flow

**Test /verify-token endpoint:**
```bash
# Get your token from browser localStorage
# Then test the endpoint

curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/verify-token

# VPS
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://yourdomain.com/verify-token
```

Expected response:
```json
{
  "user": {
    "id": "...",
    "email": "ojars@kapteinis.lv",
    "is_superuser": true,
    "is_active": true,
    ...
  }
}
```

### 2. Test Dashboard Access

1. **Local:** Open http://localhost:3000/dashboard
2. **VPS:** Open https://yourdomain.com/dashboard

**Verify:**
- [ ] Dashboard loads without flash of protected content
- [ ] Shows "Verifying authentication..." loading state
- [ ] Redirects to /login if not authenticated
- [ ] Loads dashboard after valid token verification

### 3. Test Admin Pages

**As Superuser (your account):**
1. Access http://localhost:3000/dashboard/security
2. Access http://localhost:3000/dashboard/rate-limiting
3. Access http://localhost:3000/dashboard/site-settings

**Verify:**
- [ ] All admin pages load successfully
- [ ] Shows "Checking administrator permissions..." loading state
- [ ] No error messages

**As Regular User (if you have a test account):**
1. Login with non-admin account
2. Try to access `/dashboard/security`

**Verify:**
- [ ] Redirects to /dashboard
- [ ] Shows "Access Denied" toast message
- [ ] Cannot access admin pages

### 4. Test Model Status Indicator

1. Open dashboard
2. Look at sidebar footer
3. Start a chat

**Verify:**
- [ ] Model status shows current model (e.g., "Gemini 2.0 Flash")
- [ ] Shows "Ready" when idle
- [ ] Shows "Responding" with animation during chat
- [ ] Updates in real-time

### 5. Test Performance Metrics

1. Open browser console (F12)
2. Start a new chat
3. Watch console logs

**Verify:**
- [ ] See "[Chat Performance] TTFB: XXXms" log
- [ ] See "[Chat Performance] Completed" log with metrics
- [ ] Metrics look reasonable (TTFB < 2000ms, tokens/s > 0)

---

## Part 10: Family User Access Configuration

### Verify Registration is Disabled

```bash
# Check backend config
grep -E "REGISTRATION|DISABLE_REGISTRATION" /opt/SurfSense/surfsense_backend/.env
```

Should show:
```
REGISTRATION_ENABLED=FALSE
DISABLE_REGISTRATION=true
```

### Create Family User Accounts (if needed)

```bash
# SSH to VPS
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195

cd /opt/SurfSense/surfsense_backend
source venv/bin/activate

# Create user via Python script
python -c "
from app.db.user_db import create_user
from app.db.database import SessionLocal

db = SessionLocal()
user = create_user(
    db=db,
    email='family_member@example.com',
    password=os.getenv('NEW_USER_PASSWORD', 'changeme'),  # Set NEW_USER_PASSWORD env var
    is_verified=True,
    is_superuser=False
)
print(f'Created user: {user.email}')
db.close()
"
```

### Test Family User Access

1. Login with family member account
2. Verify they can:
   - [ ] Access dashboard
   - [ ] View existing search spaces
   - [ ] Use chat functionality
   - [ ] View documents
3. Verify they cannot:
   - [ ] Access /dashboard/security
   - [ ] Access /dashboard/rate-limiting
   - [ ] Access /dashboard/site-settings
   - [ ] Register new accounts (registration disabled)

---

## Part 11: Optional HTTP Basic Auth (VPS)

If you want to add an extra layer of protection on VPS:

### Nginx Configuration

```bash
# Create password file
sudo apt-get install apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd surfsense_user

# Add to Nginx config
sudo nano /etc/nginx/sites-available/surfsense

# Add inside server block:
location / {
    auth_basic "SurfSense Family Access";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://localhost:3000;
    # ... other proxy settings
}

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

---

## Part 12: Monitoring & Validation

### Health Checks

```bash
# Backend health
curl http://localhost:8000/health  # Local
curl https://yourdomain.com/health  # VPS

# Frontend health
curl http://localhost:3000  # Local
curl https://yourdomain.com  # VPS
```

### Monitor Resource Usage

```bash
# VPS monitoring
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195

# Check memory
free -h

# Check CPU
top -bn1 | head -20

# Check disk
df -h

# Check swap usage
swapon --show
```

### Set Up Monitoring (Optional)

```bash
# Watch logs in real-time
journalctl -u surfsense -f

# Monitor services
watch -n 5 'systemctl is-active surfsense surfsense-frontend surfsense-celery'
```

---

## Troubleshooting

### Issue: Services won't start

```bash
# Check full logs
journalctl -u surfsense -n 200 --no-pager

# Check if port is in use
sudo lsof -i :8000  # Backend
sudo lsof -i :3000  # Frontend

# Verify Python environment
cd /opt/SurfSense/surfsense_backend
source venv/bin/activate
python --version
pip list | grep fastapi
```

### Issue: Authentication not working

```bash
# Verify /verify-token endpoint exists
curl -v http://localhost:8000/verify-token

# Check backend logs for auth errors
journalctl -u surfsense | grep -i "verify-token"

# Verify JWT secret is set
grep JWT_SECRET /opt/SurfSense/surfsense_backend/.env
```

### Issue: Admin pages not loading

1. Check browser console for errors
2. Verify token in localStorage: `localStorage.getItem('surfsense_bearer_token')`
3. Check network tab for /verify-token response
4. Verify user has `is_superuser: true`

### Issue: Out of disk space

```bash
# Check space
df -h

# Clean old backups
rm -rf /opt/SurfSense_backup_*

# Clean npm cache
pnpm store prune

# Clean Docker (if used)
docker system prune -a
```

---

## Rollback Procedure

If something goes wrong:

### Quick Rollback

```bash
# VPS
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195

# Stop services
systemctl stop surfsense surfsense-frontend surfsense-celery surfsense-celery-beat

# Restore backup (use your backup date)
cd /opt
rm -rf SurfSense
mv SurfSense_backup_YYYYMMDD_HHMMSS SurfSense

# Restore database
sudo -u postgres psql surfsense < /opt/surfsense_db_backup_YYYYMMDD_HHMMSS.sql

# Restore config
cp /opt/surfsense_backup_env_YYYYMMDD_HHMMSS /opt/SurfSense/surfsense_backend/.env

# Restart services
systemctl start surfsense surfsense-frontend surfsense-celery surfsense-celery-beat

# Verify
systemctl status surfsense
```

---

## Post-Deployment Checklist

- [ ] All services running on local PC
- [ ] All services running on VPS
- [ ] No errors in logs
- [ ] Authentication flow works
- [ ] Admin pages protected
- [ ] Family users can access their spaces
- [ ] Registration disabled
- [ ] Model status indicator visible
- [ ] Performance metrics logging
- [ ] Backups stored safely
- [ ] Documentation updated

---

## Security Verification

Run these checks after deployment:

1. **Public Access Test:**
   - [ ] Try accessing dashboard without login → redirects to /login
   - [ ] Try registering new account → shows disabled or 404

2. **Admin Protection Test:**
   - [ ] Non-admin user cannot access /dashboard/security
   - [ ] Non-admin user cannot access /dashboard/rate-limiting
   - [ ] Non-admin user cannot access /dashboard/site-settings

3. **Token Validation Test:**
   - [ ] Invalid token redirects to login
   - [ ] Expired token shows "Session Expired" message
   - [ ] Valid token loads dashboard

4. **Family User Test:**
   - [ ] Family members can login
   - [ ] Can view existing search spaces
   - [ ] Can use chat functionality
   - [ ] Cannot access admin features

---

## Support & Contacts

- **Repository:** https://github.com/okapteinis/SurfSense
- **Branch:** nightly
- **Documentation:** `/opt/SurfSense/CLAUDE.md`
- **Implementation Details:** `/opt/SurfSense/IMPLEMENTATION_SUMMARY.md`

---

**Deployment Guide Version:** 1.0
**Last Updated:** November 21, 2025
**Author:** Ojārs Kapteinis with Claude Code
