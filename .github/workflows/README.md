# GitHub Actions Configuration

## Required Secrets

To enable automated deployments, configure these secrets in GitHub:

**Settings → Secrets and variables → Actions → New repository secret**

### Deployment Secrets
- `SERVER_HOST`: Production server IP (e.g., `46.62.230.195`)
- `SERVER_USER`: SSH user (e.g., `root`)
- `SSH_PRIVATE_KEY`: Private SSH key for deployment (entire key content)

### How to Generate SSH Key for Deployment

```bash
# Generate deployment key
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/surfsense_deploy

# Copy public key to server
ssh-copy-id -i ~/.ssh/surfsense_deploy.pub root@46.62.230.195

# Copy private key content to GitHub secret
cat ~/.ssh/surfsense_deploy
# Copy entire output to GitHub secret SSH_PRIVATE_KEY
```

## Environment Variables in GitHub Actions

Never hardcode these in workflow files. Use secrets:

```yaml
env:
  SERVER_HOST: ${{ secrets.SERVER_HOST }}
  API_KEY: ${{ secrets.API_KEY }}
```

## Security Notes

- Secrets are encrypted at rest
- Never log secret values (`echo ${{ secrets.API_KEY }}`)
- Rotate secrets regularly
- Use different keys for different environments
