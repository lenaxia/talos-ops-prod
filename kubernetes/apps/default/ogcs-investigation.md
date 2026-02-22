# Investigation: Orphaned ogcs HelmRelease

## Summary
This file documents the investigation of the orphaned ogcs HelmRelease causing Service to have no endpoints.

## Finding Details
- **k8sgpt fingerprint:** `f37562b771ca9b546ed6152d1fd44dc7bb5bd2d7977d0a316b37e6a84776ad6d`
- **Service:** default/ogcs
- **Namespace:** default (not `utilities` as incorrectly reported)

## Investigation Results

### Evidence Gathered
1. **Service Status:**
   - Service `ogcs` exists in `default` namespace
   - Has NO endpoints (Endpoints field is empty)
   - Selector: `app.kubernetes.io/controller=ogcs,app.kubernetes.io/instance=ogcs,app.kubernetes.io/name=ogcs`

2. **Missing Resources:**
   - Deployment `ogcs` does NOT exist
   - Zero pods exist with "ogcs" in name
   - Service selectors have no matching pods

3. **Orphaned HelmRelease:**
   - HelmRelease `ogcs` exists in cluster
   - Status: `True` (Ready) but Deployment is missing
   - Created: 2025-11-20
   - Has Flux finalizer: `finalizers.fluxcd.io`
   - NO Kustomization in GitOps manages it

4. **GitOps Repository:**
   - No Kustomization manages the ogcs HelmRelease
   - No files in repo reference "ogcs" or "outlookgooglecalendarsync"
   - Only Kustomization for default namespace: `cluster-default-echo-server-shadow`

### Root Cause
The ogcs HelmRelease is orphaned - it exists in the cluster but has no corresponding Kustomization in the GitOps repository. The HelmRelease was likely removed from GitOps at some point, causing Flux to stop reconciling it. The Deployment has been deleted (manually or by garbage collection), but the Service, Ingress, and PVC remain.

### Recommended Actions

**Option A: Clean up (if app no longer needed)**
```bash
helm uninstall ogcs -n default
```
This will remove all associated resources cleanly.

**Option B: Re-add to GitOps (if still needed)**
1. Create `kubernetes/apps/default/ogcs/` directory
2. Add `helm-release.yaml` with ogcs HelmRelease configuration
3. Add `ks.yaml` with Flux Kustomization
4. Add to `kubernetes/apps/default/kustomization.yaml`

### Important Notes
- PVC `ogcs-config` contains 10Gi of data - verify before deletion
- Ingress `ogcs.thekao.cloud` has TLS certificate
- This issue has existed for 93 days
- The k8sgpt finding incorrectly reported `utilities` namespace