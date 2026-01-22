# Authelia & Traefik Migration Handoff

## Current State

**Last Good Commit:** `052500485222a79fd5f759fafee1f31da11d34f2`
- Authelia: 4.37.5 (chart 0.8.58) - STABLE
- Traefik: v2.11.13 (chart 27.0.2) - STABLE

**What Was Attempted:**
- Authelia upgrade from 4.37.5 → 4.39.15 (chart 0.8.58 → 0.10.49)
- Added OIDC `claims_policies` configuration for backward compatibility
- Changes were committed and pushed to GitHub

**Issues Encountered:**
1. YAML syntax error in helm-release.yaml at line 568 - "did not find expected key"
   - This caused Kustomization `cluster-networking-authelia` to fail building
   - Flux was stuck trying to build resources with malformed YAML

2. Git state confusion:
   - HEAD had uncommitted changes (0.10.49 version)
   - origin/main was at upgrade commit
   - Local reset left divergent state

3. Git lock file issues:
   - Multiple git processes running in background (MCP server, etc.)
   - Lock file `/home/ubuntu/workspace/talos-ops-prod/.git/index.lock` blocked operations

**Current Cluster State:**
- Kustomization `cluster-networking-authelia` exists and is failing
- HelmRelease `networking/authelia.v49` still running with chart 0.8.58
- HelmChart `networking-authelia` with chart 0.8.58 still cached
- Authelia pod is running: `ghcr.io/ghcr.io/authelia/authelia:4.37.5`

**Rollback Status:**
✅ Successfully forced rollback to commit `052500485222a79fd5f759fafee1f31da11d34f2` on GitHub
❌ Local repository state is diverged and needs cleanup
❌ Kustomization still has errors and is failing

---

## What Needs To Be Done Next Session

### 1. Clean Up Git State
```bash
# Ensure clean git state
git fetch origin
git reset --hard origin/052500485222a79fd5f759fafee1f31da11d34f2
git branch -D rollback-authelia  # cleanup created branch
rm /home/ubuntu/workspace/talos-ops-prod/kubernetes/apps/networking/MIGRATION_PLAN.md  # remove old plan
```

### 2. Clean Up Flux Resources
```bash
# Delete stuck Kustomization
kubectl delete kustomization cluster-networking-authelia -n flux-system

# Wait for Kustomization to be recreated
sleep 30

# Verify cluster is stable
flux get kustomizations -A
kubectl get helmrelease -n networking authelia
kubectl get pods -n networking -l app.kubernetes.io/name=authelia
```

### 3. Fix the HelmRelease YAML Issue

**Root Cause:** The `claims_policies` configuration in Authelia HelmRelease has a YAML syntax error around line 568.

**Fix Approach:**
- Review the helm-release.yaml file and fix the YAML structure around the `claims_policies` section
- Ensure proper indentation (2 spaces for nested items under values.configMap.identity_providers.oidc)
- The error "did not find expected key" suggests either:
  - Missing colon after key name
  - Incorrect indentation
  - List vs map confusion

**Current Structure (broken):**
```yaml
identity_providers:
  oidc:
    claims_policies:
      backward_compat:
        id_token: ['rat', 'groups', ...]  # <- SYNTAX ERROR HERE
```

**Correct Structure:**
```yaml
identity_providers:
  oidc:
    claims_policies:
      backward_compat:
        id_token:
          - rat
          - groups
          - email
          - email_verified
          - alt_emails
          - preferred_username
          - name
```

### 4. Test Changes Locally Before Commit

```bash
# Validate YAML syntax
kubectl apply -f /home/ubuntu/workspace/talos-ops-prod/kubernetes/apps/networking/authelia/app/helm-release.yaml --dry-run=client

# Validate with Flux's kustomization build
kubectl create --dry-run=client -f /home/ubuntu/workspace/talos-ops-prod/kubernetes/apps/networking/authelia/app/kustomization.yaml

# Check git diff
git diff HEAD
```

### 5. Commit and Push Authelia Upgrade (Working Version)

```bash
# Add changes
git add /home/ubuntu/workspace/talos-ops-prod/kubernetes/apps/networking/authelia/app/helm-release.yaml

# Verify staged changes
git diff --cached HEAD | head -50

# Commit with clear message
git commit -m "feat: Upgrade Authelia from 4.37.5 to 4.39.15

- Update Helm chart version from 0.8.58 to 0.10.49
- Update Authelia image from 4.37.5 to 4.39.15
- Add OIDC claims_policies backward_compat for all clients
  - tailscale, minio, open-webui, pgadmin, grafana
  - outline, overseerr, komga, linkwarden, forgejo
- Remove deprecated userinfo_signing_algorithm (replaced by claims_policy)
- This maintains backward compatibility for ID Token claims as Authelia 4.39
  changed default behavior to only include minimal OIDC spec claims
- Fixed YAML syntax error in claims_policies section
- Fixed indentation to 2 spaces for nested items under values.configMap

See MIGRATION_PLAN.md for full details"

# Push to GitHub
git push origin main
```

### 6. Monitor Flux Reconciliation

```bash
# Watch Kustomization build
watch flux get kustomizations cluster-networking-authelia

# In another terminal, watch HelmRelease
watch flux get helmrelease -n networking authelia

# Watch HelmChart being rebuilt
watch flux get helmchart -n flux-system networking-authelia

# Wait for chart version 0.10.49 to appear
```

### 7. Validate Authelia Deployment (24h Monitoring Period)

#### Immediate Checks (0-5 min after deployment)
```bash
# Check pod is new version
kubectl get pods -n networking -l app.kubernetes.io/name=authelia
kubectl get pods -n networking -l app.kubernetes.io/name=authelia -o jsonpath='{.items[0].spec.containers[0].image}'

# Check pod status
kubectl wait -n networking pod -l app.kubernetes.io/name=authelia --for=condition=ready --timeout=300s

# Check logs for errors
kubectl logs -n networking -l app.kubernetes.io/name=authelia --tail=100 | grep -i error

# Check HelmRelease status
flux get helmrelease -n networking authelia
kubectl get helmrelease -n networking authelia -o yaml | grep -E "(version|revision|status)"
```

#### Test All OIDC Clients (15-45 min)

For each of the 10 OIDC clients:
- Tailscale
- MinIO
- Open-WebUI
- PGAdmin
- Grafana
- Outline
- Overseerr
- Komga
- Linkwarden
- Forgejo

**Test Procedure:**
1. Logout of application
2. Initiate OAuth login
3. Complete Authelia authentication
4. Verify redirect back to application
5. Check application logs for claims errors

#### Hourly Checks (24h period)
```bash
# Check pod remains Running
kubectl get pods -n networking -l app.kubernetes.io/name=authelia

# No unexpected restarts
kubectl get pods -n networking -l app.kubernetes.io/name=authelia -o jsonpath='{.items[0].status.containerStatuses[0].restartCount}'

# Error rate < 1%
kubectl logs -n networking -l app.kubernetes.io/name=authelia --tail=500 | grep -i error | wc -l

# Authentication success rate > 95%
kubectl logs -n networking -l app.kubernetes.io/name=authelia --tail=500 | grep -i "successful" | wc -l
```

---

## Next Phase: Traefik Upgrade

Only proceed with Traefik upgrade AFTER:
- Authelia 4.39.15 is stable for 24 hours
- All 10 OIDC clients tested and working
- No critical errors in logs
- Authentication success rate > 95%

**Traefik Upgrade Summary:**
- Current: v2.11.13 (chart 27.0.2)
- Target: v3.6.7 (chart 38.0.1)
- Breaking changes:
  - CRD API group: `traefik.containo.us` → `traefik.io/v1alpha1`
  - Update ALL IngressRoute, Middleware resources
  - Replace `ipWhiteList` → `ipAllowList`
  - Remove deprecated `forceSlash` option
  - Update configuration: `logs` → `log`, `accessLog` structure changes
  - Add `core.defaultRuleSyntax: v2` for compatibility
  - Plugin compatibility verification needed

---

## Documentation References

### Files Modified in Previous Attempt
- `/home/ubuntu/workspace/talos-ops-prod/kubernetes/apps/networking/authelia/app/helm-release.yaml`
  - Changed chart version: 0.8.58 → 0.10.49
  - Changed image tag: 4.37.5 → 4.39.15
  - Added claims_policies configuration (has syntax error)

### Key Commands for Next Session
```bash
# Navigation
cd /home/ubuntu/workspace/talos-ops-prod/kubernetes/apps/networking

# Validate YAML
yamllint authelia/app/helm-release.yaml

# Clean git state
git status
git reset --hard origin/052500485222a79fd5f759fafee1f31da11d34f2

# Monitor Flux
flux get ks cluster-networking-authelia
flux get hr -n networking authelia

# Check pod status
kubectl get pods -n networking -l app.kubernetes.io/name=authelia
kubectl logs -n networking -l app.kubernetes.io/name=authelia -f
```

---

## Notes for Developer

**What Went Wrong:**
1. I edited the HelmRelease YAML file but didn't properly validate the YAML syntax before committing
2. The claims_policies array had incorrect syntax - mixing array and map syntax incorrectly
3. Git operations were blocked by lock files from background processes
4. Local and remote git state became desynchronized

**Lessons Learned:**
1. Always validate YAML syntax with `kubectl apply --dry-run=client` or `yamllint` before committing
2. Test Flux Kustomization builds locally with `kubectl create --dry-run=client`
3. Ensure no background git processes are running before operations
4. Check git state after each operation: `git status`
5. Verify commit is applied before proceeding: `git log --oneline -1`

**Current Git State (at handoff):**
- Branch: `rollback-authelia` (detached HEAD state)
- Main branch: Ahead of origin by 2 commits
- Working directory: Clean
- Untracked files: `MIGRATION_PLAN.md`

**To Resume:**
```bash
# Clean up and start fresh
cd /home/ubuntu/workspace/talos-ops-prod
git fetch origin
git checkout main
git branch -D rollback-authelia
git reset --hard origin/052500485222a79fd5f759fafee1f31da11d34f2
# Now you're at the last known good state, ready to retry
```

---

**Last Updated:** 2026-01-22
**Session:** Handoff - Issues encountered, cleanup needed before retry
