# Flux Diff Failure Analysis

## Failure Summary

**Workflow:** Flux Diff  
**Run ID:** 21772120319  
**Run URL:** https://github.com/lenaxia/talos-ops-prod/actions/runs/21772120319  
**Branch:** renovate/ghcr.io-esphome-esphome-2026.x  
**SHA:** 0f5cb79a57b5b7adca2f75e0d8e32ef11feb60dd

## Root Cause

**Category:** D. GitOps Repository Issues

The Flux Diff workflow fails when processing kustomizations that contain external git references. The specific error occurs in the flux-local Docker container:

```
flux-local error: Command 'flux build ks cluster-apps-node-feature-discovery --dry-run 
--kustomization-file /dev/stdin --path /github/workspace/pull/kubernetes/apps/kube-system/node-feature-discovery/app 
--namespace flux-system' failed with return code 1

✗ failed to generate kustomization.yaml: lstat /github/workspace/pull/kubernetes/apps/kube-system/node-feature-discovery/app/github.com/kubernetes-sigs/node-feature-discovery/deployment/base/nfd-crds?ref=v0.18.3: 
no such file or directory <nil> <nil>
```

### Detailed Explanation

1. The kustomization at `kubernetes/apps/kube-system/node-feature-discovery/app/kustomization.yaml:5` contains:
   ```yaml
   resources:
     - github.com/kubernetes-sigs/node-feature-discovery//deployment/base/nfd-crds?ref=v0.18.3
   ```

2. When flux-local runs `kustomize build` inside the Docker container, it encounters this external git reference

3. Git inside the container is not configured to fetch external repositories, so the reference is incorrectly interpreted as a local file path

4. The file lookup fails because the path doesn't exist locally

### Impact

This is a **systematic issue** affecting multiple PRs:
- 6+ recent failures in similar Renovate PRs (per recent-runs.json)
- Any kustomization with external git references will fail
- The bootstrap kustomization also has a similar pattern that could fail if checked

## Proposed Systematic Fix

### Approach: Configure Git for External Repository Access

Add a step before the flux-local diff to create a git configuration file that enables fetching external repositories:

```yaml
- name: Setup Git Configuration
  run: |
    cat > .gitconfig_ci << 'EOF'
    [url "https://github.com/"]
      insteadOf = git@github.com:
      insteadOf = ssh://git@github.com/
    [core]
      sshCommand = ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
    [credential]
      helper = /dev/null
    EOF

- name: Diff Resources
  uses: docker://ghcr.io/allenporter/flux-local:v8.1.0
  with:
    # ... existing args
  env:
    GIT_TERMINAL_PROMPT: '0'
    GIT_CONFIG: '/github/workspace/.gitconfig_ci'
```

### Why This Is a Systematic Fix

1. **Prevents entire class of errors** - Works for ALL external git references, not just node-feature-discovery
2. **Maintains existing structure** - No need to modify kustomization files or commit external resources
3. **Follows kustomize best practices** - Uses standard kustomize git reference syntax
4. **No additional dependencies** - Uses existing git/kustomize infrastructure
5. **Works offline for cached repos** - Once fetched, repos are cached locally

### Files to Modify

- `.github/workflows/flux-diff.yaml` - Add git configuration step and environment variables

### Testing Plan

1. Create PR with the workflow changes
2. Run Flux Diff workflow on the PR itself (testing esphome changes from #786)
3. Verify workflow succeeds and processes node-feature-discovery kustomization
4. Check that external git repository is fetched successfully
5. Verify no regressions in other PRs

### Risk Assessment

**Risk Level:** Low

- Configuration changes are isolated to CI workflow
- No changes to production kubernetes manifests
- Git configuration is temporary (only during workflow execution)
- Fallback behavior: if external fetch still fails, error will be the same as before
- Public repositories only (no secret/credential exposure)

### Prevention

This fix prevents future failures by:
- Enabling all kustomizations with external git references to work in CI
- Following standard kustomize patterns without modifications
- No additional manual steps required for new external references

## Additional Context

### Related Files with External Git References

1. `kubernetes/bootstrap/flux/kustomization.yaml:7`
   - References: `github.com/fluxcd/flux2/manifests/install?ref=v2.7.5`
   
2. `kubernetes/apps/kube-system/node-feature-discovery/app/kustomization.yaml:5`
   - References: `github.com/kubernetes-sigs/node-feature-discovery//deployment/base/nfd-crds?ref=v0.18.3`

### Why Bootstrap Doesn't Fail

The bootstrap kustomization isn't checked by the flux-diff workflow (it only checks `kubernetes/flux`), so it doesn't encounter the issue currently. However, if the workflow scope expands, it would also fail without this fix.

---

**Closes:** https://github.com/lenaxia/talos-ops-prod/actions/runs/21772120319  
**Related PR:** #786
