# SurfSense Deployment Guide

## Quick Start

### Automatic Deployment (Recommended)
```bash
ssh root@46.62.230.195
cd /opt/SurfSense
./scripts/deploy.sh
```

The script automatically:
- Creates backup
- Pulls latest code
- Builds frontend
- Restarts services
- Runs health checks
- **Rolls back on any failure**

---

## Pre-Deployment Checklist

Before deploying to production:

- [ ] Run `scripts/validate-deployment.sh` locally
- [ ] All tests pass
- [ ] Changes reviewed in PR
- [ ] Backup database (if schema changes)
- [ ] Team notified of deployment

---

## Monitoring After Deployment

### Check Service Status
```bash
systemctl status surfsense-frontend
systemctl status surfsense
systemctl status surfsense-celery
systemctl status surfsense-celery-beat
```

### View Logs
```bash
# Deployment logs
tail -f /var/log/surfsense-deploy.log

# Frontend logs
journalctl -u surfsense-frontend -f

# Backend logs
journalctl -u surfsense -f
```

### Test Health
```bash
# Frontend
curl -I https://ai.kapteinis.lv

# Backend API
curl https://ai.kapteinis.lv/api/v1/

# Auth endpoints
curl -X POST https://ai.kapteinis.lv/api/v1/auth/2fa/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test&password=test"
```

---

## Rollback Procedure

### Automatic Rollback
The deployment script automatically rolls back on failure. No action needed.

### Manual Rollback
If you need to manually rollback:

```bash
# List available backups
ls -lt /opt/SurfSense-backups/

# Restore from backup
cd /opt/SurfSense
tar -xzf /opt/SurfSense-backups/surfsense-backup-YYYYMMDD-HHMMSS.tar.gz

# Restart services
systemctl restart surfsense-frontend
systemctl restart surfsense
```

---

## Troubleshooting

### Build Fails
1. Check disk space: `df -h`
2. Verify `scripts/build-production.sh` exists
3. Check for fumadocs errors in logs
4. Try manual build: `cd surfsense_web && pnpm build`

### Services Won't Start
1. Check logs: `journalctl -u surfsense-frontend -n 50`
2. Verify permissions: `ls -la /opt/SurfSense/surfsense_web/.next`
3. Check port conflicts: `lsof -i :3000`
4. Test manually: `cd surfsense_web && pnpm start`

### Authentication Issues
1. Clear browser cookies and localStorage
2. Verify backend is setting cookies (check Network tab)
3. Check CORS configuration in backend
4. Test auth endpoint directly (see Monitoring section)

### Database Migration Fails
1. Check database connection: `psql -U surfsense surfsense`
2. Review migration history: `alembic history`
3. Manually run migration: `cd surfsense_backend && pipenv run alembic upgrade head`

---

## Emergency Contacts

If deployment fails and automatic rollback doesn't work:

1. Check `/var/log/surfsense-deploy.log`
2. Restore from backup (see Rollback Procedure)
3. Contact team with exact error messages
