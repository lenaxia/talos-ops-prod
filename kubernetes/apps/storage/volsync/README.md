# VolSync Configuration - Awaiting K8s 1.34+

## Status: Prepared but Not Active

This VolSync configuration is **ready but disabled** pending Kubernetes 1.34+ upgrade when MutatingAdmissionPolicy (MAP) graduates from alpha to beta.

## Why Disabled

### Root Cause
The perfectra1n VolSync fork with Kopia support requires MutatingAdmissionPolicy to inject NFS repository mounts into backup job pods. Without MAP:
- `KOPIA_REPOSITORY: filesystem:///repository` in the secret has no mount target
- No native CRD field exists for repository mounting (`repositoryPVC`, `moverPodSpec` don't exist)
- Backup jobs fail because `/repository` path doesn't exist

### What We Tried (Dec 2024)

1. **MutatingAdmissionPolicy with K8s 1.33 (Alpha)** ❌
   - Enabled `MutatingAdmissionPolicy=true` feature gate
   - Result: API server overload, infinite error loops
   - Impact: Cluster-wide API requests failed ("not yet ready to handle request")
   - Reverted immediately

2. **moverPodSpec Field** ❌
   - Attempted to add NFS mounts via `spec.moverPodSpec`
   - Error: `.spec.moverPodSpec: field not declared in schema`
   - Field doesn't exist in perfectra1n CRD

3. **repositoryPVC Field** ❌
   - Attempted to use `spec.kopia.repositoryPVC`
   - Error: `.spec.kopia.repositoryPVC: field not declared in schema`
   - Field doesn't exist despite web search results claiming otherwise

### Current Backup Solution

**Using Kyverno + Kopia (Fully Functional)**
- `kubernetes/apps/kyverno/policies/snapshot-cronjob-controller.yaml`
- Watches PVCs labeled `snapshot.home.arpa/enabled: "true"`
- Auto-generates CronJobs with Kopia backups
- Retention: 17 latest, 7 daily, 3 weekly, 2 monthly, 2 annual
- Repository: NFS at `192.168.0.120:/volume1/backups/kopia`
- Works reliably without experimental features

## When to Enable VolSync

### Prerequisites
1. **Kubernetes 1.34+ installed**
   - MutatingAdmissionPolicy expected to graduate to beta
   - Check: `kubectl api-resources | grep MutatingAdmissionPolicy`
   - Should show `v1beta1` or `v1` (not `v1alpha1`)

2. **Enable Feature Gate (if still required)**
   ```yaml
   # kubernetes/bootstrap/talos/patches/controller/cluster.yaml
   apiServer:
     extraArgs:
       feature-gates: MutatingAdmissionPolicy=true
   ```

3. **Deploy MutatingAdmissionPolicy**
   - Create `kubernetes/apps/storage/volsync/app/mutatingadmissionpolicy-nfs.yaml`
   - Reference implementation in `.tmp/volsync` report
   - Injects NFS mount: `192.168.0.120:/volume1/backups/kopia` → `/repository`

4. **Test with Non-Critical App**
   ```yaml
   # In app's ks.yaml
   components:
     - ../../../../components/volsync
   postBuild:
     substitute:
       VOLSYNC_CAPACITY: 5Gi
   ```

### Activation Steps

1. Uncomment components in app kustomizations (e.g., `jellyfin/ks.yaml`)
2. Deploy MAP for NFS injection
3. Verify backup jobs run successfully
4. Gradually migrate apps from Kyverno to VolSync
5. Keep Kyverno policy as fallback/alternative

## What's Already Configured

### Operator
- **Image**: `ghcr.io/perfectra1n/volsync:v0.16.13`
- **Helm Chart**: `oci://ghcr.io/home-operations/charts-mirror/volsync-perfectra1n:0.17.15`
- **Movers**: kopia, rclone, restic, rsync, rsync-tls, syncthing
- **Status**: Running but idle (no ReplicationSources exist)

### Resources
- `volsync-kopia-secret.yaml`: Kopia password (none) and repo path
- `repository-pvc.yaml`: NFS-backed PV/PVC (500Gi, unused without MAP)
- `kopiamaintenance.yaml`: Automated cleanup every 8 hours
- `prometheusrule.yaml`: Alerts for backup health

### Component Templates
- `kubernetes/components/volsync/replicationsource.yaml`
- `kubernetes/components/volsync/replicationdestination.yaml`
- Ready to use with Kopia, requires MAP for NFS mounting

## Architecture Comparison

| Aspect | Current (Kyverno) | Future (VolSync) |
|--------|-------------------|------------------|
| Trigger | PVC label | ReplicationSource CRD |
| Snapshot | Longhorn CSI | Longhorn CSI |
| Backup Engine | Kopia | Kopia |
| Repository | NFS direct mount | NFS via MAP injection |
| Scheduling | CronJob | Built-in trigger |
| Retention | Policy-defined | Per-ReplicationSource |
| Restore | Manual Task workflow | ReplicationDestination |
| Maintenance | Manual | KopiaMaintenance CRD |

## Migration Strategy (When Ready)

1. **Phase 1**: Enable MAP, test on 1-2 non-critical apps
2. **Phase 2**: Migrate apps with complex backup needs (multiple PVCs, custom retention)
3. **Phase 3**: Keep Kyverno for simple apps or retire completely
4. **Phase 4**: Monitor, optimize, document

## Lessons Learned

1. **Alpha features are not production-ready** - MutatingAdmissionPolicy caused cluster issues
2. **Reference implementations may require bleeding-edge features** - Always verify K8s version requirements
3. **Test in dev first** - Experimental features should never touch production directly
4. **Document rollback procedures** - Having Talos config ready to revert saved us
5. **Trust simple over clever** - Kyverno approach is less elegant but completely reliable

## References

- Original Report: `.tmp/volsync` (from reference gitops repo)
- VolSync Docs: https://volsync.readthedocs.io/
- perfectra1n Fork: https://github.com/perfectra1n/volsync
- MAP KEP: https://github.com/kubernetes/enhancements/tree/master/keps/sig-api-machinery/3962-mutating-admission-policies

---
Last Updated: 2024-12-18
K8s Version: 1.33 (MAP v1alpha1 - unstable)
Status: Awaiting K8s 1.34+ for MAP beta graduation
