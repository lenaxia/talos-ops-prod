# Multus Rollback Runbook

Emergency runbook for reversing a Multus enablement rollout when things go sideways. Written 2026-07-06 during the two-phase Multus deployment.

## When to use this runbook

Use this if any of the following happen after a Multus-related PR merges:

- A Flux Kustomization related to Multus (`cluster-multus`, `cluster-multus-networks`) never becomes Ready
- Multus-annotated pods (esphome, home-assistant, zwavejs) stuck `ContainerCreating` for >5 minutes
- New pods cluster-wide fail to schedule with CNI errors
- Cilium DaemonSet reports unhealthy on any node
- `kubectl get nodes` shows any worker `NotReady` (Multus-caused, not hardware)
- Talos node's kubelet logs show repeated CNI plugin errors

## Pre-flight

Every Multus rollout is preceded by an etcd snapshot. Latest snapshot lives at:

```
~/etcd-snapshots/pre-multus-<TIMESTAMP>.snapshot
```

If the snapshot doesn't exist, DO NOT PROCEED with the rollout — take one first:

```bash
talosctl -n 192.168.3.10 -e 192.168.3.10 etcd snapshot \
  ~/etcd-snapshots/pre-multus-$(date +%Y%m%d-%H%M%S).snapshot
```

## Rollback levels

### Level 1: Revert the PR (hands-free)

**Applies to:** Failures 1-3 (DS won't start, consumer pod stuck, single-app issue). Flux does the work.

1. Identify the offending PR (whichever Multus PR most recently merged).
2. On GitHub, click **Revert** on the merged PR to open a revert PR.
3. Merge the revert PR.
4. Wait for Flux to reconcile (typically 1-3 minutes):
   ```bash
   flux --context=admin@home-kubernetes -n flux-system reconcile source git flux-system
   ```
5. Verify:
   ```bash
   kubectl -n kube-system get ds kube-multus-ds 2>&1        # should be NotFound after DS revert
   kubectl get networkattachmentdefinitions -A 2>&1         # should be empty after NAD revert
   kubectl -n home get pods                                 # consumer pods should return to normal
   ```

**Success criteria:** all pods running, no CNI errors in kubelet logs. Move on.

**If Level 1 doesn't recover things in 10 minutes,** escalate to Level 2.

### Level 2: Manual CNI cleanup on affected nodes

**Applies to:** Failure 4 (`00-multus.conf` persists on nodes, Cilium can't take back exclusive control).

Cilium's `cni.exclusive` was already set to `false` before the rollout. This means Cilium won't automatically delete Multus's config file after the DaemonSet is removed. We do it manually.

For each affected node (start with the one whose workloads are broken):

```bash
# Verify what's in /etc/cni/net.d
talosctl -n <NODE-IP> -e 192.168.3.10 list /etc/cni/net.d

# If 00-multus.conf is present, remove it
talosctl -n <NODE-IP> -e 192.168.3.10 rm /etc/cni/net.d/00-multus.conf

# Restart the Cilium agent pod on that node so it re-reconciles CNI state
kubectl -n kube-system delete pod -l app.kubernetes.io/name=cilium-agent \
  --field-selector spec.nodeName=<NODE-NAME>

# Wait for the new Cilium pod to be Ready
kubectl -n kube-system wait --for=condition=Ready pod \
  -l app.kubernetes.io/name=cilium-agent \
  --field-selector spec.nodeName=<NODE-NAME> \
  --timeout=120s
```

**IP-to-name map:**
- 192.168.3.20 → worker-00
- 192.168.3.21 → worker-01
- 192.168.3.22 → worker-02

### Level 3: Force cni.exclusive back to true

**Applies to:** Failure 4 that Level 2 didn't resolve — Multus DS keeps re-creating the CNI file.

The two-phase rollout keeps `cni.exclusive: false` set in Cilium's HelmRelease. If the Multus DaemonSet is running as a DS and rewriting `00-multus.conf` faster than we can remove it, we need Cilium to take exclusive control.

1. Edit `kubernetes/apps/kube-system/cilium/app/helm-values.yaml`:
   - Change `cni.exclusive: false` back to `cni.exclusive: true`
2. Commit + push directly to `main` (skip PR — emergency).
3. Force Flux reconcile:
   ```bash
   flux --context=admin@home-kubernetes -n flux-system reconcile source git flux-system
   flux --context=admin@home-kubernetes -n kube-system reconcile hr cilium
   ```
4. Wait for Cilium DS rollout (~3-5 min). Cilium will delete `00-multus.conf` from every node as it reconciles.

### Level 4: Restore from etcd snapshot (worst case)

**Applies to:** Cluster is truly wedged. Multiple nodes NotReady, API server intermittent, workloads can't recover.

This is the "reset the world" option. See `docs/etcd-disaster-recovery.md` (if it exists) for details; otherwise follow the Sidero disaster-recovery procedure:

- <https://docs.siderolabs.com/talos/v1.13/build-and-extend-talos/cluster-operations-and-maintenance/disaster-recovery>

Key command:
```bash
# Reset EPHEMERAL on cp-00 (wipes etcd, keeps STATE / machine config)
talosctl -n 192.168.3.10 -e 192.168.3.10 reset \
  --graceful=false --reboot --system-labels-to-wipe=EPHEMERAL --wait=false

# Wait for cp-00 to reboot and reach "Preparing" state for etcd
# (see Sidero docs; typically 2-3 min after reboot)

# Bootstrap from pre-Multus snapshot
talosctl -n 192.168.3.10 -e 192.168.3.10 bootstrap \
  --recover-from=~/etcd-snapshots/pre-multus-<TIMESTAMP>.snapshot
```

Cluster restored to state immediately before the Multus rollout. Any changes made after the snapshot are lost.

## Post-rollback

After a successful rollback (Level 1-3):

1. Verify all workloads healthy:
   ```bash
   kubectl get pods -A | grep -v Running | grep -v Completed
   flux get ks -A | grep -v True
   ```
2. Post an incident write-up as a `docs/` note or GitHub issue with:
   - What failed
   - Which level of rollback was needed
   - Root cause if identified
   - What to change before retrying

## Known non-issues (don't panic)

- **Talos discovery shows "1 machine"** on the dashboard even though etcd/K8s have all nodes. This is a cosmetic Talos discovery-service issue unrelated to Multus. Don't roll back for this.
- **cp-01 NotReady / missing** — hardware failure (bad RAM), not Multus-related. Node has been out since 2026-06-29.
- **`cni.exclusive: false`** in `cilium-config` — this is intentional for Multus, not a rollback trigger.
