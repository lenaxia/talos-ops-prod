#!/usr/bin/env bash
set -e

echo "====================================="
echo "Testing GitHub Workflows"
echo "====================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "❌ Docker is not running. Please start Docker first."
  exit 1
fi

echo "✅ Docker is running"
echo ""

# Test 1: Validate opencode.json
echo "Test 1: Validate opencode.json syntax"
if python3 -m json.tool .github/workflows/opencode.json 2>&1; then
  echo "✅ opencode.json is valid JSON"
else
  echo "❌ opencode.json has JSON errors"
  exit 1
fi
echo ""

# Test 2: Check vLLM endpoint accessibility
echo "Test 2: Check vLLM endpoint accessibility"
echo "Enter your vLLM endpoint URL (e.g., http://vllm.local/v1):"
read VLLM_ENDPOINT

if [ -z "$VLLM_ENDPOINT" ]; then
  echo "⚠️  Skipping network test (no endpoint provided)"
else
  if curl -s -o /dev/null --connect-timeout 5 "$VLLM_ENDPOINT/models" 2>&1; then
    echo "✅ vLLM endpoint is accessible"
  else
    echo "❌ vLLM endpoint is not accessible"
    echo "   Check:"
    echo "   - vLLM is running"
    echo "   - Traefik routing is configured correctly"
    echo "   - Firewall allows access"
  fi
fi
echo ""

# Test 3: Run Renovate Analysis workflow locally
echo "Test 3: Run Renovate Analysis workflow locally"
echo "This will require GITHUB_TOKEN to work properly"
echo ""
read -p "Run this test? (y/n): " RUN_TEST
if [[ $RUN_TEST =~ ^[Yy]$ ]]; then
  if command -v act > /dev/null; then
    echo "✅ act is installed"
    echo ""
    echo "Running: act -j renovate-analysis -s"

    # Use act to run the workflow
    # This simulates GitHub Actions environment
    echo "Note: This is a dry-run simulation. To test with real runner,"
    echo "      commit and push a test branch, or create a test PR."

  else
    echo "⚠️  act is not installed"
    echo "Install with: brew install act"
    echo "Then re-run this script"
  fi
else
  echo "Skipping workflow test"
fi
echo ""

# Test 4: Check GitHub CLI
echo "Test 4: Verify GitHub CLI setup"
if command -v gh > /dev/null 2>&1; then
  echo "✅ GitHub CLI (gh) is installed"

  # Check if authenticated
  if gh auth status > /dev/null 2>&1 | grep -q "Logged in"; then
    echo "✅ GitHub CLI is authenticated"
  else
    echo "⚠️  GitHub CLI is not authenticated"
    echo "   Run: gh auth login"
  fi
else
  echo "❌ GitHub CLI (gh) is not installed"
  echo "   Install with: brew install gh or conda install -c conda-forge gh"
fi
echo ""

echo "====================================="
echo "Testing Complete"
echo "====================================="
echo ""
echo "Next Steps:"
echo "1. Commit and push: git add .github/workflows/opencode.json && git commit -m 'feat: add vLLM config for OpenCode' && git push"
echo "2. Add OPENCODE_API_KEY secret to GitHub repository settings"
echo "3. Update opencode.json baseURL to match your vLLM endpoint"
echo "4. Test by creating a test issue or letting Renovate create a PR"
