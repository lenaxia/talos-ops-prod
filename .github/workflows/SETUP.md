# vLLM Workflows Setup - Final

## ✅ Complete Setup

Production workflows ready to deploy with your existing OpenAI secrets:

| File | Purpose |
|-------|---------|
| `.github/workflows/renovate-analysis.yml` | Analyzes Renovate PRs using vLLM |
| `.github/workflows/issue-responder.yml` | Responds to lenaxia's issues |

### Configuration Files

| File | Purpose |
|-------|---------|
| `opencode.json` | OpenCode config - uses vLLM as OpenAI-compatible provider |

### Secrets Required (Using Your Existing Keys)

Your workflows now use these standard secret names:

| Secret Name | Description | Your Value |
|-------------|-------------|-------------|
| `OPENAI_API_KEY` | OpenCode API key | ✅ Already configured |
| `OPENAI_API_BASE` | vLLM endpoint URL | Add your vLLM URL here |
| `OPENAI_MODEL` | Model name | Add `mistral-7b-instruct` |

**No changes needed to your `OPENAI_API_KEY`** - workflows already reference it!

### Update Required

**1. Add `OPENAI_API_BASE` secret:**
   - Go to: Settings → Secrets and variables → Actions → New repository secret
   - Name: `OPENAI_API_BASE`
   - Value: Your vLLM endpoint URL
     - Example: `http://vllm.yourdomain.com/v1`

**2. Add `OPENAI_MODEL` secret:**
   - Go to: Settings → Secrets and variables → Actions → New repository secret
   - Name: `OPENAI_MODEL`
   - Value: Model name
     - Example: `mistral-7b-instruct`

**3. Commit and push all changes:**
   ```bash
   git add .github/workflows/*.yml opencode.json
   git commit -m "feat(workflows): add vLLM-powered AI workflows"
   git push
   ```

## What Changed

### Workflows Now Use Your Existing OpenAI Secret

Instead of:
```yaml
OPENCODE_API_KEY: ${{ secrets.OPENCODE_API_KEY }}
```

Now they use:
```yaml
OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
OPENAI_API_BASE: ${{ secrets.OPENAI_API_BASE }}
OPENAI_MODEL: ${{ secrets.OPENAI_MODEL }}
```

**Benefit:** You only need to add 2 more secrets, not change your existing `OPENAI_API_KEY`!

### Removed: Create opencode.json Step

Workflows no longer create `opencode.json` dynamically - they expect it to exist at the root.

## Testing Guide

### Quick Validation

```bash
# 1. Update opencode.json with your vLLM endpoint
vim opencode.json
# Change: "baseURL": "http://vllm.yourdomain.com/v1"

# 2. Verify workflows reference correct secrets
grep -r "OPENAI_API" .github/workflows/*.yml

# 3. Run test script
./.github/test/test-setup.sh
```

### Test with act (Optional)

```bash
# Install act
brew install act

# Run workflow locally
act -j renovate-analysis \
  --env OPENAI_API_BASE=http://vllm.local/v1 \
  --env OPENAI_API_KEY=test
```

## Deployment

Once you've added the secrets and pushed:

1. **Workflows will activate** on:
   - New Renovate PRs (types: [opened] only)
   - Issue creation or comments (lenaxia only)
   - Scheduled runs (every 2 hours)
   - Manual triggers (workflow_dispatch)

2. **Monitor in GitHub Actions tab** for:
   - Successful vLLM connections
   - Analysis output on PRs
   - Issue responses

## Troubleshooting

### vLLM Not Working

**Check:**
1. Is vLLM running and accessible?
   ```bash
   curl -v http://your-vllm-endpoint/v1/models
   ```

2. Is Traefik routing correctly configured to GitHub?
   - GitHub Actions runner must be able to reach your vLLM endpoint
   - Check Traefik middleware/routing rules

3. Are you using OpenAI-compatible endpoint format?
   - Should be: `http://domain/v1` or `https://domain/v1`
   - Must include `/chat/completions` endpoint

### OpenCode Provider Errors

**Error: "provider not configured"**
- Verify `opencode.json` is in repository root
- Check provider ID matches model reference: `vllm-local/mistral-7b-instruct`

**Error: "model not found"**
- Verify `OPENAI_MODEL` secret matches model name in `opencode.json`
- Case-sensitive check

## Support

For issues, check:
1. Workflow logs in GitHub Actions tab
2. vLLM container logs
3. Traefik access logs
4. Test locally with `./.github/test/test-setup.sh`
