# SeaweedFS - tiered S3 object storage (shadow deployment)

Replaces MinIO (upstream maintenance-mode). Apache-2.0, official Helm chart.

## Layout

| Piece | Replicas | Storage |
|---|---|---|
| master (coordinator) | 3 | Longhorn 2Gi each |
| filer (object catalog) | 2 | Longhorn 5Gi each, self-syncing |
| s3 gateway | 2 | none (stateless) |
| volume server | 1 | two NFS dataDirs + Longhorn 2Gi index |

- **SSD tier**: `/volume3/s3-ssd` on the Synology (static NFS PV `seaweedfs-ssd`)
- **HDD tier**: `/volume1/s3-hdd` on the Synology (static NFS PV `seaweedfs-hdd`)
- **Catalog backup #1**: PVC `seaweedfs-meta-backup-kopia` (labeled `snapshot.home.arpa/enabled: "true"` -> existing Kyverno/Kopia backups)
- **Catalog backup #2**: NFS dir `/volume1/backups/seaweedfs` (PV `seaweedfs-meta`)
- **Shadow endpoint**: `https://s3-shadow.<domain>` (MinIO keeps `s3.<domain>` until cutover)

Bucket tiers (set by `bucket-init-job.yaml`, changeable later with
`fs.configure -locationPrefix=/buckets/<name>/ -disk=<tier> -apply`):

- **ssd**: paperless, outline
- **hdd**: cnpg-5wxuej, restic, ragnarok, nemo-herc-ws, forgejo-k8s, ai-or-not, tftp, private, public, iceberg
- **not migrated** (dormant on old MinIO share): docbuddy-tpfs3, nextcloud-oh7iqq, loki-dev

## Before merging - fill the placeholder keys

`app/secret.sops.yaml` contains placeholder credentials. Fill them:

```sh
sops edit kubernetes/apps/storage/seaweedfs/app/secret.sops.yaml
```

1. **admin**: generate fresh - `openssl rand -hex 20` (access) and `openssl rand -base64 36` (secret). Fill both the standalone keys and the `admin` identity in the JSON.
2. **Per-app identities**: reuse each app's *existing* MinIO keys so consumers only need an endpoint change at cutover:
   - `cnpg` -> secret `postgres-minio` in `databases` ns (`MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`)
   - `forgejo` -> secret in `utilities` ns (`MINIO_ACCESS_KEY_ID` / `MINIO_SECRET_ACCESS_KEY`)
   - `outline` -> check outline chart values for its S3 secret
   - `paperless` -> check paperless app secret
   - `iceberg` -> `SECRET_ICEBERG_MINIO_ACCESS_KEY` / `..._SECRET_KEY` (flux vars secret)
   - `restic` -> wherever the restic bucket writer keeps its keys
3. Mirror the same values into both the standalone keys and the JSON identity fields.

## Acceptance tests (after deploy, before migration)

```sh
# 1. All pods healthy
kubectl get pods -n storage -l app.kubernetes.io/instance=seaweedfs

# 2. Both tier PVs bound to the volume server's claims
kubectl get pvc -n storage | grep -E 'ssd|hdd'

# 3. Bucket init job completed; note each bucket's disk type
kubectl logs -n storage job/seaweedfs-bucket-init

# 4. Write through S3 (shadow endpoint) and confirm placement
mc alias set sw https://s3-shadow.<domain> <ADMIN_ACCESS_KEY> <ADMIN_SECRET_KEY>
mc mb sw/placement-test-ssd  # then:
kubectl exec -n storage statefulset/seaweedfs-volume -- \
  sh -c 'echo "fs.configure -locationPrefix=/buckets/placement-test-ssd/ -disk=ssd -apply" | weed shell -master=seaweedfs-master:9333'
echo hello | mc pipe sw/placement-test-ssd/test.txt
# new 1GB-ish volume file must appear under /volume3/s3-ssd on the NAS,
# nothing under /volume1/s3-hdd:
ls -la /volume1/s3-hdd /volume3/s3-ssd   # on the Synology
# repeat with -disk=hdd for placement-test-hdd, expect the file on volume1
mc cat sw/placement-test-ssd/test.txt   # read back through S3

# 5. Catalog backups are streaming (both pods log progress)
kubectl logs -n storage deploy/seaweedfs-meta-backup-kopia --tail=20
kubectl logs -n storage deploy/seaweedfs-meta-backup-nfs --tail=20
# the NFS copy is visible on the NAS:
ls -la /volume1/backups/seaweedfs

# 6. Kopia enrollment (next Kyverno-generated backup should include the PVC)
kubectl get pvc -n storage seaweedfs-meta-backup-kopia --show-labels
```

## Migration

Edit `app/rclone-migrate-job.yaml` to `suspend: false` and commit - do NOT
`kubectl patch` it (Flux re-applies every 30m and would revert the patch,
killing an in-flight migration). Watch:

```sh
kubectl logs -n storage job/seaweedfs-rclone-migrate -f
```

Copies the 12 kept buckets and verifies checksums (`rclone check`). When done,
commit `suspend: true` again (or delete the Job object - Flux re-creates it
suspended). Aborted runs resume; `rclone copy` is idempotent.

## Cutover (separate PR)

Flip each consumer's endpoint `http://minio.storage.svc.cluster.local:9000`
-> `http://seaweedfs-s3.storage.svc.cluster.local:8333` (keys unchanged):

- `databases/cloudnative-pg/clusters/*.yaml` (endpointURL + barman S3)
- `monitoring/loki/app/helm-release.yaml` (if Loki returns)
- `utilities/forgejo/app/helm-release.yaml` (MINIO_ENDPOINT `s3.<domain>` - keep hostname, repoint DNS/ingress instead)
- `media/outline/...`, `jobhunt/trino/...`, `jobhunt/nessie/...`
- external `s3.<domain>` DNS -> point at the SeaweedFS ingress, then delete the
  shadow ingress (note: `networking/traefik/ingresses/minio.yaml` is a dormant
  file not registered in its kustomization - verify which DNS name actually
  serves `s3.<domain>` before flipping)

After consumers verified on SeaweedFS:

1. Suspend MinIO: `spec.suspend: true` in `storage/minio/ks.yaml` (keep the
   `/volume3/minio` NFS folder as dormant archive).
2. Remove the Authelia `minio` OAuth client (console is gone; nothing uses it).
3. Optional cleanup: stale `openebs-minio` StatefulSet leftovers in
   `openebs-system`.

## Restore procedures

- **One filer disk lost**: nothing to do; peer filer serves, sync restores it.
- **Both filer disks / cluster storage lost**: restore the Kopia PVC
  `seaweedfs-meta-backup-kopia` (or copy `/volume1/backups/seaweedfs` contents)
  into a filer data volume; restart filers. Object data was on NFS all along.
- **Synology volume lost**: catalog is safe (Longhorn + backups); data
  protected only by Synology RAID - same exposure the MinIO NFS share had.

## Aging (SSD -> HDD), when wanted

Unsuspend `seaweedfs-tier-move` and set `COLLECTION_PATTERN` (wildcards OK,
e.g. `paperless*`). Moves filled (>= FULL_PERCENT) volume files idle for
QUIET_FOR from the ssd dataDir to hdd. Free-version granularity: whole volume
files, not individual objects. Commit the change here after patching.
