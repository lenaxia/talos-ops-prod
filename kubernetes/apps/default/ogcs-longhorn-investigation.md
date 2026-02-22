# Investigation: Orphaned ogcs HelmRelease causing Longhorn share-manager Service to have no endpoints

## Summary
This file documents the investigation of a Longhorn share-manager Service having no endpoints, caused by an orphaned ogcs HelmRelease.

## Finding Details
- **k8sgpt fingerprint:** `a0d16b08b77cdc1e92942984988b26379b176111d0eabc1d76798f279652baf4`
- **Service:** longhorn-system/pvc-5e07e911-8baf-4aff-b1f7-fd8f9a20d1b5
- **Namespace (as reported):** utilities (incorrect - actual namespace is longhorn-system)
- **Actual Namespace:** longhorn-system
- **Related Finding:** PR #1090 (fingerprint: `f37562b771ca9b546ed6152d1fd44dc7bb5bd2d7977d0a316b37e6a84776ad6d`)

## Investigation Results

### Evidence Gathered

1. **Service Status (longhorn-system/pvc-5e07e911-8baf-4aff-b1f7-fd8f9a20d1b5):**
   - Service exists in `longhorn-system` namespace (NOT `utilities` as incorrectly reported)
   - Has NO endpoints
   - Selector: `longhorn.io/managed-by=longhorn-manager,longhorn.io/share-manager=pvc-5e07e911-8baf-4aff-b1f7-fd8f9a20d1b5`
   - Type: ClusterIP
   - Port: 2049/TCP (NFS)
   - Age: 93 days

2. **Associated PVC:**
   - PVC: `ogcs-config` in `default` namespace
   - Volume: `pvc-5e07e911-8baf-4aff-b1f7-fd8f9a20d1b5`
   - Status: Bound
   - Capacity: 10Gi
   - AccessMode: RWX
   - Age: 93 days

3. **Longhorn Volume Status:**
   - Volume: `pvc-5e07e911-8baf-4aff-b1f7-fd8f9a20d1b5` in `longhorn-system`
   - State: `detached`
   - Robustness: `unknown`
   - Share State: `stopped`
   - All 3 replicas: `stopped`
   - Last pod reference: `ogcs-74b78b994b-pmw66` (status: Failed)

4. **Missing Resources:**
   - Deployment `ogcs` does NOT exist in `default` namespace
   - Zero pods exist with "ogcs" in name
   - Share-manager pod for this PVC does NOT exist

5. **Orphaned HelmRelease:**
   - HelmRelease `ogcs` exists in cluster (namespace: default)
   - Status: `True` (Ready) - but this is misleading
   - Revision: 1, Last Deployed: 2025-11-20
   - Has Flux finalizer: `finalizers.fluxcd.io`
   - NO Kustomization in GitOps manages it
   - Last reconcile: "release in-sync with desired state" (continuous syncs every 30m)

6. **GitOps Repository:**
   - No Kustomization manages the ogcs HelmRelease
   - No files in repo reference "ogcs" or "outlookgooglecalendarsync"
   - Only Kustomization for default namespace: `cluster-default-echo-server-shadow`

### Root Cause
The ogcs HelmRelease is orphaned. It exists in the cluster but has no corresponding Kustomization in the GitOps repository. The chain of events:

1. At some point, the ogcs application was removed from the GitOps repository
2. Flux stopped reconciling the HelmRelease (no source to compare against)
3. The ogcs Deployment was deleted (manually or by garbage collection)
4. With no pods using the `ogcs-config` PVC, Longhorn automatically detached the volume
5. When a Longhorn volume is detached, the share-manager pod is stopped to save resources
6. The share-manager Service (`pvc-5e07e911-8baf-4aff-b1f7-fd8f9a20d1b5`) now has no endpoints
7. k8sgpt detected this and flagged it as an issue

This is expected behavior for Longhorn share-manager services when volumes are not in use, but it indicates that the owning application (ogcs) is no longer running.

### Related Finding
This finding is directly related to PR #1090, which investigated the ogcs Service in the default namespace having no endpoints. Both findings are caused by the same root cause: the orphaned ogcs HelmRelease with a missing Deployment.

### Recommended Actions

**Option A: Clean up (recommended if app no longer needed)**
```bash
helm uninstall ogcs -n default
```
This will cleanly remove:
- HelmRelease `ogcs`
- Service `ogcs` (in default namespace)
- Ingress `ogcs.thekao.cloud`
- PVC `ogcs-config`
- Longhorn volume and all replicas
- Longhorn share-manager Service `pvc-5e07e911-8baf-4aff-b1f7-fd8f9a20d1b5`

**Option B: Re-add to GitOps (if app is still needed)**
1. Verify that the ogcs application is still needed
2. Create `kubernetes/apps/default/ogcs/` directory
3. Add `helm-release.yaml` with ogcs HelmRelease configuration
4. Add `ks.yaml` with Flux Kustomization
5. Add to `kubernetes/apps/default/kustomization.yaml`
6. This will cause Flux to recreate the Deployment

### Important Notes
- PVC `ogcs-config` contains 10Gi of data (actual usage: ~246MB) - verify before deletion
- The actual size is 246MB out of 10Gi allocated, so the volume is not heavily used
- Ingress `ogcs.thekao.cloud` has a TLS certificate
- This issue has existed for 93 days
- The k8sgpt finding incorrectly reported the namespace as `utilities` instead of `longhorn-system`
- No pods are currently using the `ogcs-config` PVC
- The Longhorn volume has 3 stopped replicas on worker-00, worker-01, and worker-02
- The application image was: `ghcr.io/lenaxia/outlookgooglecalendarsync:3.0.0@sha256:fa0e0f3ac5b4ce149f0a2f847d3b5ebcf5fd7e73a01f321f651d0f0c7da97e99`
- The application exposed port 3000 for HTTP
