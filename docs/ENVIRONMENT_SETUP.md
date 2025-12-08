# Environment Variables Setup

## Local Development

1. Copy the template:
   ```bash
   cp .env.example .env.local
   ```

2. Edit `.env.local` with your actual values

3. **Never commit `.env.local` to git!**

## Production Server

1. SSH to server:
   ```bash
   ssh root@46.62.230.195
   ```

2. Create environment file:
   ```bash
   cd /opt/SurfSense/surfsense_web
   nano .env.local
   ```

3. Add production values (ask team for secrets)

4. Verify it's not tracked:
   ```bash
   git status  # Should not show .env.local
   ```

## Security Best Practices

✅ DO:
- Use `.env.example` for templates
- Store secrets in password manager
- Use different secrets for dev/prod
- Rotate secrets regularly

❌ DON'T:
- Commit `.env` or `.env.local` files
- Share secrets in chat/email
- Use same secrets across environments
- Hardcode secrets in code
