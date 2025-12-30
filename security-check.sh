#!/bin/bash
set -e

echo "🔍 SurfSense Security Check"
echo "=============================="

# 1. Check PRs
echo ""
echo "📋 Open Security PRs:"
gh pr list --label security --state open || echo "No security PRs or gh CLI not authenticated"

# 2. Check Dependabot
echo ""
echo "🔧 Dependabot Alerts:"
gh api /repos/okapteinis/SurfSense/dependabot/alerts 2>/dev/null | \
  jq -r '.[] | "\(.security_advisory.severity): \(.security_advisory.package.name)"' || \
  echo "Unable to fetch Dependabot alerts (check gh auth)"

# 3. Check CodeQL
echo ""
echo "🛡️ CodeQL Alerts:"
gh api /repos/okapteinis/SurfSense/code-scanning/alerts 2>/dev/null | \
  jq -r '.[] | select(.state=="open") | "\(.rule.severity): \(.rule.description)"' || \
  echo "Unable to fetch CodeQL alerts (check gh auth)"

# 4. Local Git Status
echo ""
echo "🔀 Git Status:"
git fetch origin --quiet
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"
git status --short

# 5. Check for uncommitted changes
echo ""
echo "📝 Security-Related Files Status:"
git status --short | grep -E "(security|test_.*security|SECURITY|csrf)" || echo "No pending security changes"

# 6. Run local security tests
echo ""
echo "🧪 Running Security Tests:"
cd surfsense_backend
if [ -f "pyproject.toml" ]; then
    echo "Running pytest security tests..."
    pytest -m security --tb=short -q 2>/dev/null || echo "Security tests not found or failed"
else
    echo "Backend not found at current path"
fi

# 7. Check dependencies
echo ""
echo "📦 Dependency Security Check:"
if command -v safety &> /dev/null; then
    safety check --short 2>/dev/null || echo "Safety check failed or no vulnerabilities"
else
    echo "safety not installed (pip install safety)"
fi

# 8. Summary
echo ""
echo "✅ Security check complete!"
echo ""
echo "Next steps:"
echo "  1. Review open PRs: gh pr list"
echo "  2. Check GitHub Security tab: open https://github.com/okapteinis/SurfSense/security"
echo "  3. Run full test suite: cd surfsense_backend && pytest -v"
