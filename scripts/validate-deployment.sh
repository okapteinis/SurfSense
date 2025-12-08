#!/bin/bash
# Pre-deployment validation script
# Run this BEFORE deploying to catch issues early

set -e

echo "=== Pre-Deployment Validation ==="

# Check 1: Build succeeds locally
echo "Checking if build succeeds..."
cd surfsense_web
pnpm build > /dev/null 2>&1
echo "✓ Build succeeds"

# Check 2: TypeScript compilation
echo "Checking TypeScript..."
pnpm tsc --noEmit
echo "✓ TypeScript OK"

# Check 3: Lint checks
echo "Running linter..."
pnpm lint || echo "⚠ Lint warnings found (non-fatal)"

# Check 4: Auth flow validation
echo "Validating auth code structure..."

# Check that localStorage is not used for auth tokens
if grep -r "localStorage.setItem.*AUTH_TOKEN_KEY" app lib --include="*.ts" --include="*.tsx" 2>/dev/null; then
    echo "✗ ERROR: Found localStorage.setItem(AUTH_TOKEN_KEY) - should use cookies only"
    exit 1
fi

if grep -r "Authorization.*Bearer.*localStorage" app lib --include="*.ts" --include="*.tsx" 2>/dev/null; then
    echo "✗ ERROR: Found Authorization header from localStorage - should use cookies"
    exit 1
fi

echo "✓ Auth code validation passed"

# Check 5: Environment variables
echo "Checking environment variables..."
if [ ! -f ".env" ] && [ ! -f ".env.local" ]; then
    echo "⚠ WARNING: No .env file found"
fi
echo "✓ Environment checks complete"

echo "=== All validation checks passed! ==="
