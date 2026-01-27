# Testing Guide for vLLM Workflows

## Quick Start

Run the test script:
```bash
./.github/test/test-setup.sh
```

## Manual Testing Checklist

### 1. Verify opencode.json Configuration

```bash
# Check current configuration
cat opencode.json

# Update your vLLM endpoint
vim opencode.json
# Change: "baseURL": "http://vllm.local/v1"
```

### 2. Test vLLM Endpoint

```bash
# Test if vLLM is reachable
curl -v http://vllm.local/v1/models

# Test API with your model
curl -X POST http://vllm.local/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral-7b-instruct",
    "messages": [{"role": "user", "content": "Hello, vLLM!"}],
    "temperature": 0.7
  }'
```

### 3. Test with act (GitHub Actions Runner)

```bash
# Install act
brew install act

# Run workflow simulation
act -j renovate-analysis --env OPENAI_API_BASE=http://vllm.local/v1

# Or with environment variables
act -j renovate-analysis \
  --env OPENAI_API_BASE=http://vllm.local/v1 \
  --env OPENAI_API_KEY=test-key
```

### 4. Real Test via GitHub

**Option A: Test Issue Responder**
1. Create a test issue in your repo
2. Trigger the workflow by creating the issue
3. Check workflow logs in Actions tab

**Option B: Test Renovate Analysis**
1. Let Renovate create a PR
2. Check workflow logs for analysis output
3. Review the PR comment added by the workflow

## Troubleshooting

### Workflows Not Triggering

Check:
- [ ] `OPENCODE_API_KEY` secret is added to GitHub
- [ ] `opencode.json` is committed and pushed
- [ ] Workflow files are committed to the correct branch

### vLLM Connection Issues

If workflows fail with connection errors:

```bash
# Test vLLM from GitHub Actions runner
curl -v http://vllm.local/v1/models

# From your local machine
curl -v http://vllm.local/v1/models
```

Check:
- [ ] vLLM container is running
- [ ] Traefik routing is configured
- [ ] GitHub Actions runner can reach the endpoint
- [ ] CORS headers allow GitHub's domain

### OpenCode Configuration Errors

If you see "provider not found" errors:

1. Verify `opencode.json` is in the correct location (repo root)
2. Check JSON syntax:
   ```bash
   python3 -m json.tool opencode.json
   ```
3. Verify provider ID in workflow matches `opencode.json`:
   - Should both use `vllm-local`
   - Should use `@ai-sdk/openai-compatible` npm package

### Model Name Mismatch

If you see "model not found" errors:

1. Check model name in `opencode.json`:
   ```json
   "models": {
     "mistral-7b-instruct": {
       "name": "Mistral 7B Instruct"
     }
   }
   ```
2. Check model name in workflow:
   ```yaml
   opencode run -m vllm-local/mistral-7b-instruct "..."
   ```
3. Must match exactly: `vllm-local/mistral-7b-instruct`

## Workflow Debugging

### View Workflow Logs

1. Go to your repo → Actions tab
2. Click on the workflow run
3. Expand "Analyze Renovate PRs" step
4. Look for errors in the log output

### Common Errors

| Error | Cause | Fix |
|--------|--------|-----|
| `opencode: command not found` | OpenCode not installed in runner | Setup action doesn't install OpenCode |
| `Permission denied` | Wrong permission config | Fix `OPENCODE_PERMISSION` JSON |
| `GitHub API rate limit` | Too many requests | Wait and retry |
| `vLLM connection refused` | Network issue | Check Traefik routing |
| `Provider not configured` | opencode.json missing or wrong | Verify config file |

## Deployment Checklist

Before committing workflows:

- [ ] `opencode.json` is committed to repo
- [ ] Workflows reference correct model: `vllm-local/mistral-7b-instruct`
- [ ] `OPENCODE_API_KEY` secret is added to GitHub
- [ ] vLLM endpoint is accessible from GitHub Actions runner
- [ ] Tested workflows locally (optional but recommended)

## Success Indicators

When workflows are working correctly:

✅ Issue #XXX responds with AI analysis or PR creation
✅ Renovate PRs get detailed analysis comments
✅ No "permission denied" or "command not found" errors in logs
✅ OpenCode successfully connects to your vLLM
