# Security Checklist for SurfSense

## Before Every Commit

- [ ] Run `git status` - ensure no `.env` files staged
- [ ] Check for hardcoded secrets: `git diff --cached | grep -i secret`
- [ ] Remove any test credentials or API keys
- [ ] Verify `.gitignore` is working

## Before Every Deploy

- [ ] Secrets are in `.env.local`, not in code
- [ ] `.env.local` is NOT committed to git
- [ ] Production secrets are different from dev
- [ ] No SSH keys in repository

## Regular Maintenance

- [ ] Rotate secrets every 90 days
- [ ] Review GitHub Actions secrets
- [ ] Check for leaked secrets: `git log -p | grep -i password`
- [ ] Update dependencies: `pnpm audit`

## If Secret is Leaked

1. **Immediately revoke/rotate the secret**
2. Remove from git history:
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch path/to/secret" \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. Force push (coordinate with team):
   ```bash
   git push origin --force --all
   ```
4. Notify team and rotate all secrets
5. Consider the secret permanently compromised

## Tools

- GitHub secret scanning (enabled by default)
- Pre-commit hooks (see `.githooks/`)
- Manual review: `git diff origin/nightly`
