# Git Hooks

## Setup

Enable pre-commit hook to prevent committing secrets:

```bash
# Configure git to use .githooks directory
git config core.hooksPath .githooks

# Make hooks executable
chmod +x .githooks/pre-commit
```

## What It Does

The pre-commit hook prevents:
- Committing `.env` files
- Committing SSH keys
- Committing files with secrets in the name
- Hardcoded API keys/passwords in code

## Bypass (Emergency Only)

If you absolutely need to bypass (not recommended):

```bash
git commit --no-verify
```

**Only use this if you're certain the files are safe!**
