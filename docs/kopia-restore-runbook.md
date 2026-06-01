# Kopia Snapshot Restore Runbook

This document describes how to restore data from Kopia snapshots written by the
cluster's snapshot-cronjob-controller (Kyverno-generated CronJobs).

## Background

Every PVC labelled by Kyverno's `snapshot-cronjob-controller` policy gets a
matching `*-snap` CronJob (schedule: daily at 12:00). The job:

1. Connects to the Kopia repository on NFS at `192.168.0.120:/volume1/backups/kopia`
2. Mounts the source PVC at `/data/<namespace>/<app>/<pvc-name>`
3. Runs `fsfreeze` on the PVC, calls `kopia snap create`, unfreezes
4. Retains: 17 latest, 0 hourly, 7 daily, 3 weekly, 2 monthly, 2 annual

Snapshots are accessible via:
- The **Kopia web UI** at <http://192.168.5.139> (`kopia` LoadBalancer service in `storage` namespace)
- A **CLI pod** in-cluster (procedure below)

## Web UI restore (preferred for small files)

1. Browse to <http://192.168.5.139>
2. Navigate **Snapshots** → find path `/data/<namespace>/<app>/<pvc-name>`
3. Open a snapshot timestamp → use **Mount as local filesystem** or **Restore Files**
4. Download specific files, or restore an entire directory tree

For full-PVC restores (DB volumes, large config trees) prefer the CLI procedure.

## CLI restore procedure

### 1. Identify the snapshot

```bash
# List snapshots for a given PVC path
kubectl -n storage exec deploy/kopia -- kopia snap list /data/<namespace>/<app>/<pvc-name>

# Example
kubectl -n storage exec deploy/kopia -- kopia snap list /data/home/babybuddy/babybuddy-volume
```

Note the snapshot ID (long hex hash) and timestamp of the snapshot you want.

### 2. Stop the workload

The target PVC must not be in use during restore. For most apps:

```bash
kubectl -n <namespace> scale deploy <app> --replicas=0
# or for StatefulSets
kubectl -n <namespace> scale statefulset <app> --replicas=0
```

For HelmRelease-managed apps, scaling will be reverted by Flux unless you
suspend the HelmRelease first:

```bash
flux -n <namespace> suspend helmrelease <app>
kubectl -n <namespace> scale deploy <app> --replicas=0
```

Wait for the pod to terminate and the PVC to detach (volume should show `detached`
in `kubectl -n longhorn-system get volumes.longhorn.io`).

### 3. Spawn a restore pod

Create a pod that mounts the target PVC and has access to the Kopia repo. The
simplest approach is to reuse the snapshot CronJob's pod template.

Save as `restore-pod.yaml`, edit `<NAMESPACE>`, `<PVC>`, `<SNAPSHOT_ID>`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: kopia-restore
  namespace: <NAMESPACE>
spec:
  restartPolicy: Never
  securityContext:
    runAsUser: 568
    runAsGroup: 568
    fsGroup: 568
  containers:
  - name: kopia
    image: kopia/kopia:latest
    command: ["/bin/bash", "-c"]
    args:
    - |
      kopia repo connect filesystem --path=/snapshots --override-hostname=cluster --override-username=root --no-persist-credentials --password=none
      echo "Listing target before restore:"
      ls -la /data/restore || true
      echo "Restoring snapshot <SNAPSHOT_ID>..."
      kopia snap restore <SNAPSHOT_ID> /data/restore
      echo "Done. Sleeping for inspection..."
      sleep 7200
    env:
    - name: KOPIA_PASSWORD
      value: none
    - name: KOPIA_CONFIG_PATH
      value: /tmp/repository.config
    - name: KOPIA_CACHE_DIRECTORY
      value: /tmp/kopia-cache
    volumeMounts:
    - name: data
      mountPath: /data/restore
    - name: snapshots
      mountPath: /snapshots
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: <PVC>
  - name: snapshots
    nfs:
      server: 192.168.0.120
      path: /volume1/backups/kopia
```

Apply and watch:

```bash
kubectl apply -f restore-pod.yaml
kubectl -n <NAMESPACE> logs -f pod/kopia-restore
```

### 4. Validate the restored data

```bash
kubectl -n <NAMESPACE> exec pod/kopia-restore -- ls -la /data/restore
# spot-check expected files exist
```

### 5. Tear down restore pod and bring workload back

```bash
kubectl -n <NAMESPACE> delete pod kopia-restore
flux -n <NAMESPACE> resume helmrelease <app>     # only if you suspended above
kubectl -n <NAMESPACE> scale deploy <app> --replicas=1
```

Verify the app comes back healthy and reads the restored data.

## Per-app exceptions

### Postgres (CNPG)

DO NOT restore postgres at the filesystem level from a Kopia snapshot of a
running cluster's data directory — corruption guaranteed. Instead:

- Use CNPG's native backup/restore via `Cluster.spec.bootstrap.recovery`
- Or `pg_restore` from a `pg_dump` taken before the loss
- Kopia snapshot is **only valid** if `fsfreeze` succeeded (check the source
  CronJob log for `[04/10] Freeze` step success)

### MariaDB (mariadb-operator)

Same caveat as postgres. Use mariadb-operator `Backup` resources or `mysqldump`
output rather than raw filesystem restore.

### SQLite (most home apps: babybuddy, *arr stack, home-assistant)

Filesystem restore is safe IF the original pod was stopped during the snapshot
window OR the kopia job successfully ran `fsfreeze` (check job log). Most home
apps in this cluster fall in this category and Kopia's filesystem restore works
fine.

### Plex / Media servers

Filesystem restore is safe but DBs inside (Plex's library SQLite) are large.
Restore can take 30+ min for large libraries. Watch I/O during restore.

## Troubleshooting

**"repository not found" / mount failure**
The NFS server `192.168.0.120` may be unreachable. Check NAS power/network.

**Kopia connect fails with auth error**
The cluster's Kopia repo uses `--password=none` (this is intentional — the NFS
server provides the security boundary). If a job fails auth, check the
`KOPIA_PASSWORD=none` env is set in the restore pod spec.

**Restored files have wrong owner/group**
The Kopia restore preserves the original UID/GID. If the target app uses a
different user, run `chown -R <uid>:<gid> /data/restore` after restore but
before bringing the app back online. Most app-template based apps use UID/GID
568 (the `apps` user).

**No snapshots listed for a PVC path**
- Check the snapshot CronJob exists: `kubectl get cronjob -A | grep <pvc-name>`
- Check it's running successfully: `kubectl get jobs -A | grep <pvc-name> | tail`
- The Kyverno policy only generates CronJobs for PVCs labelled appropriately;
  see `kubernetes/apps/kyverno/policies/snapshot-cronjob-controller.yaml`

## Related references

- Snapshot policy: `kubernetes/apps/kyverno/policies/snapshot-cronjob-controller.yaml`
- Kopia HelmRelease: `kubernetes/apps/storage/kopia-web/app/helm-release.yaml`
- VolSync (alternate backup mechanism, used by very few apps):
  `kubernetes/components/volsync/`
