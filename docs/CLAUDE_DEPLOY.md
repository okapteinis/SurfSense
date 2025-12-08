# Deployment Instructions for Claude Code

## Quick Deploy

**Single command to deploy everything:**

```bash
ssh root@46.62.230.195
cd /opt/SurfSense
./scripts/deploy.sh
```

That's it! The script handles everything and rolls back automatically if anything fails.

---

## What the Script Does

1. ✅ Creates backup (for automatic rollback)
2. ✅ Pulls latest code from nightly
3. ✅ Installs dependencies
4. ✅ Builds frontend (handles fumadocs)
5. ✅ Fixes permissions
6. ✅ Runs migrations
7. ✅ Restarts all services
8. ✅ Tests health endpoints
9. ✅ **Auto-rollback on failure**

---

## If Something Goes Wrong

**Don't panic!** The script automatically rolls back.

View logs:
```bash
tail -f /var/log/surfsense-deploy.log
```

Check services:
```bash
systemctl status surfsense-frontend
```

---

## Important Rules

### ✅ DO:
- Use the deployment script
- Check logs if things fail
- Ask user for browser console errors
- Create git commits for fixes

### ❌ DON'T:
- Edit files directly on server (use git)
- Run `pnpm build` manually (use script)
- Move folders around manually
- Add localStorage auth code
- Try to "fix" things with sed/awk

---

## Debugging Checklist

If user reports issues after deployment:

1. **Check service status:**
   ```bash
   systemctl status surfsense-frontend
   ```

2. **Check logs:**
   ```bash
   journalctl -u surfsense-frontend -n 50
   ```

3. **Test health:**
   ```bash
   curl -I https://ai.kapteinis.lv
   ```

4. **Ask user to provide:**
   - Browser console errors (F12)
   - Network tab showing failed requests
   - Exact error messages they see

5. **If truly broken:**
   - Rollback is automatic
   - Manual rollback: see `docs/DEPLOYMENT.md`

---

## Common Issues & Solutions

### "Build failed"
- Script handles this automatically
- Check `/var/log/surfsense-deploy.log`
- Fumadocs routes are already handled by build script

### "Services won't start"
- Check logs: `journalctl -u surfsense-frontend -n 50`
- Verify permissions are set correctly (script does this)
- Test manually: `cd /opt/SurfSense/surfsense_web && pnpm start`

### "Authentication not working"
- Ask user to clear cookies and localStorage
- Verify cookies are being set (user checks Network tab)
- Don't add localStorage token code - it should use cookies only

---

## Remember

The deployment script is designed to be **idempotent** and **safe**. It's better to run it twice than to try manual fixes.

If you're unsure, ask the user to check the logs and provide exact error messages.
