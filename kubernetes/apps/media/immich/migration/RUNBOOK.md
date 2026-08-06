# Bridge Build Runbook (Phase 1)

Operational procedures for the full bridge build run. Read this before kicking off
the Job. Pairs with `DESIGN.md` §5 (Execution Order).

---

## 1. Pre-flight checklist

Run these the day of, before launch:

```bash
# 1. Backups healthy (both clusters)
kubectl get cluster -n databases vectorpg     # phase=healthy, archiving=Success, backup=Success
kubectl get cluster -n databases synofotopg   # phase=healthy, archiving=Success, backup=Success

# 2. Trigger a fresh pre-migration backup (~2 min, gives clean restore point)
kubectl create backup manual-pre-bridge-vectorpg \
  -n databases --cluster vectorpg

# 3. Verify NFS exports still mounted correctly
cat <<'EOF' | kubectl apply -f -     # smoke-test pod, delete after
apiVersion: v1
kind: Pod
metadata: {name: nfs-check, namespace: databases}
spec:
  restartPolicy: Never
  containers:
    - name: c
      image: busybox
      command: ["sh", "-c", "ls /import/syno-local/chuni/Photos | head -1 && ls /import/syno-ldap/mike-1000032/Photos | head -1"]
      volumeMounts:
        - {name: l, mountPath: /import/syno-local, readOnly: true}
        - {name: r, mountPath: /import/syno-ldap,  readOnly: true}
  volumes:
    - {name: l, nfs: {server: 192.168.0.120, path: /volume1/homes, readOnly: true}}
    - {name: r, nfs: {server: 192.168.0.120, path: /volume1/homes/@LH-KAO.FAMILY/61, readOnly: true}}
EOF
kubectl logs -n databases nfs-check -f
kubectl delete pod -n databases nfs-check

# 4. No leftover test rows in bridge table
kubectl exec -n databases vectorpg-1 -- psql -U postgres -d immich -c \
  "SELECT COUNT(*) FROM syno_photo_migration;"
# Expected: 0 (or any prior known-good count). If unsure, TRUNCATE.

# 5. ConfigMap has latest script
kubectl delete configmap migration-scripts -n databases
kubectl create configmap migration-scripts -n databases \
  --from-file=build_bridge.py=kubernetes/apps/media/immich/migration/job/build_bridge.py
```

---

## 2. Launch

```bash
# From repo root
kubectl apply -k kubernetes/apps/media/immich/migration/job/

# Watch pod reach Running
kubectl get pods -n databases -l job-name=syno-immich-migration -w
```

The Job has `activeDeadlineSeconds: 43200` (12h hard kill) and resource limits
(memory 2Gi, cpu 2). It runs to completion and self-cleans after 24h.

---

## 3. Observability during the run

### What to watch

| Signal | Where to look | Healthy | Concerning |
|---|---|---|---|
| **Progress** | `kubectl logs -f job/syno-immich-migration` | Counter climbs steadily | Stuck at same count > 5 min |
| **Match rate** | Same logs (`matched=X (Y%)`) | 5–15% early, climbing as we hit uploaded files | 0% across > 5K photos |
| **File errors** | Same logs (`errors=N`) | < 100 total | Spiking, or > 1% of processed |
| **ETA** | Same logs (`ETA=Xmin`) | Decreases over time | Not decreasing, or increasing |
| **Bridge row count** | DB query (below) | Climbs with each batch commit | Flat for > 2 min |
| **Pod memory** | `kubectl top pod` | < 500Mi | Approaching 1Gi limit |
| **NFS mount health** | `kubectl describe pod` Events | No warnings | `Stale file handle`, `mount(2) failed` |
| **DB connection** | pod logs (psycopg2 errors) | None | `OperationalError`, `server closed connection` |

### Live monitoring one-liner

Run this in a second terminal while the Job runs:

```bash
# Watch logs + DB row count + pod resources, refresh every 30s
watch -n 30 '
  echo "=== Pod ==="
  kubectl get pod -n databases -l job-name=syno-immich-migration
  echo
  echo "=== Resources ==="
  kubectl top pod -n databases -l job-name=syno-immich-migration 2>/dev/null
  echo
  echo "=== Bridge rows ==="
  kubectl exec -n databases vectorpg-1 -- psql -U postgres -d immich -t -A -c \
    "SELECT COUNT(*) FROM syno_photo_migration"
  echo
  echo "=== Last log line ==="
  kubectl logs -n databases -l job-name=syno-immich-migration --tail=1
'
```

### When will we know something has gone wrong?

**Hard failures (Job exits non-zero):**
- NFS mount disappears → pod fails to read files, script crashes on OSError
- DB connection drops and doesn't recover → psycopg2 raises
- Pod hits memory limit → OOMKilled, Job retries (backoffLimit: 2)
- Job exceeds 12h → killed by `activeDeadlineSeconds`

**Soft failures (Job completes but with bad data):**
- Match rate is 0% → script ran but nothing matched (path bug, NFS stale)
- File errors > 1% of total → NFS permission regression or path drift
- Verification step reports accuracy < 99% → bridge rows are wrong
- Bridge row count doesn't match expected range → see §5

The post-run verification step is the **last line of defense** — it samples 3000
random rows and re-checks SHA-1 from NFS. If accuracy < 99% the Job logs a
WARNING, signaling manual review before proceeding to Phase 3.

---

## 4. Rollback

### Tier 1 — Stop the run (mid-flight)

If something looks wrong during execution:

```bash
# Stop the Job immediately (suspends further writes)
kubectl delete job -n databases syno-immich-migration

# Bridge rows inserted up to this point remain (they passed per-batch commit)
# but no further rows will be added.
```

### Tier 2 — Discard the bridge (recommended for soft failures)

The bridge table is a **disposable lookup table** — TRUNCATE has zero impact on
Immich assets, faces, people, albums, or anything users see.

```bash
kubectl exec -n databases vectorpg-1 -- psql -U postgres -d immich -c \
  "TRUNCATE syno_photo_migration;"

# Verify
kubectl exec -n databases vectorpg-1 -- psql -U postgres -d immich -c \
  "SELECT COUNT(*) FROM syno_photo_migration;"
# Expected: 0
```

After TRUNCATE, fix the script and re-run from scratch. No restore needed.

### Tier 3 — DB restore from backup (only for catastrophe)

Only if somehow Immich tables got corrupted (the script doesn't write to them,
but defense in depth):

```bash
# Find the pre-migration backup
kubectl get backups -n databases -l cnpg.io/cluster=vectorpg | grep manual-pre-bridge

# Restore via CNPG procedure (requires new cluster bootstrap, ~30 min)
# See: https://cloudnative-pg.io/documentation/1.25/recovery/
```

This is the nuclear option. Tier 2 covers all realistic failure modes.

---

## 5. Completion confidence criteria

The Job is "done" when all of these pass:

### 5.1 Job completes successfully
```bash
kubectl get job -n databases syno-immich-migration
# EXPECT: COMPLETIONS=1/1, no retries
```

### 5.2 Final log summary is sane
```
=== Bridge Build Summary ===
  Distinct photos processed:    ~197,000       # close to expected matchable count
  Matched to Immich assets:     ~14,000-18,000  # ~73-84% of 21K uploaded assets
  Not in Immich (not uploaded): ~179,000        # expected — only 21K of 288K uploaded
  File read errors:             < 500           # < 0.3% of processed
  Bridge rows inserted:         ~14,000-18,000  # may exceed assets due to dupes
  Elapsed:                      ~120-180 min
  User distribution:            {2: 0, 3: ~1k, 5: ~500, 7: ~200, 9: ~10k, 12: ~7k}
```

**Red flags in summary:**
- `Matched` is < 5,000 → most uploads weren't recognized (path or hash issue)
- `File errors` > 5,000 → NFS or path problems
- `User distribution` missing a user who has assets in Immich
- `Elapsed` < 30 min → script didn't actually walk files (probably early crash)

### 5.3 Post-run verification passes
```
=== Post-run Verification ===
  Total bridge rows: N, sampling 3000 (stratified per user)
  ...
  RESULTS: matched=2995 mismatched=0 missing=5 / 3000 checked
  ACCURACY: 99.83%
```

**Pass criteria:** accuracy ≥ 99.0% (hard threshold in script). The 3000-row
sample gives 99% confidence at ±0.5% margin for the full bridge population.

**Fail criteria:** accuracy < 99.0% → run §4 Tier 2 rollback, investigate
mismatches, fix script, re-run.

### 5.4 Cross-checks against Immich

```bash
# 1. Total Immich assets that got bridged (should be close to total Immich assets)
kubectl exec -n databases vectorpg-1 -- psql -U postgres -d immich -c "
SELECT
  (SELECT COUNT(DISTINCT id) FROM asset WHERE \"deletedAt\" IS NULL) AS total_immich_assets,
  (SELECT COUNT(DISTINCT immich_asset_id) FROM syno_photo_migration) AS bridged_assets,
  (SELECT COUNT(DISTINCT immich_asset_id) FROM syno_photo_migration)::float /
  (SELECT COUNT(DISTINCT id) FROM asset WHERE \"deletedAt\" IS NULL) AS coverage_pct;"
# EXPECT: coverage_pct between 60-90% (not 100% — some uploads aren't from Synology)

# 2. Per-user coverage (each user should have most of their assets bridged)
kubectl exec -n databases vectorpg-1 -- psql -U postgres -d immich -c "
SELECT u.email,
       COUNT(DISTINCT a.id) AS total_assets,
       COUNT(DISTINCT spm.immich_asset_id) AS bridged,
       ROUND(100.0 * COUNT(DISTINCT spm.immich_asset_id) / NULLIF(COUNT(DISTINCT a.id), 0), 1) AS pct
FROM \"user\" u
JOIN asset a ON a.\"ownerId\" = u.id AND a.\"deletedAt\" IS NULL
LEFT JOIN syno_photo_migration spm ON spm.immich_asset_id = a.id
GROUP BY u.email ORDER BY total_assets DESC;"
# EXPECT: Mike/Serena/Darcy each > 60% (Chuni=0 until uploaded)

# 3. No orphans: every bridge row must point to a real, non-deleted asset
kubectl exec -n databases vectorpg-1 -- psql -U postgres -d immich -c "
SELECT COUNT(*) AS orphan_bridge_rows
FROM syno_photo_migration spm
LEFT JOIN asset a ON a.id = spm.immich_asset_id AND a.\"deletedAt\" IS NULL
WHERE a.id IS NULL;"
# EXPECT: 0
```

### 5.5 Sign-off checklist

- [ ] Job COMPLETIONS=1/1
- [ ] Final summary stats in expected ranges
- [ ] Post-run verification accuracy ≥ 99.0%
- [ ] No orphan bridge rows
- [ ] Per-user coverage looks reasonable
- [ ] Unmatched CSV spot-checked for unexpected patterns

Once all six pass, Phase 1 is complete and Phase 3 (face matcher) can begin.

---

## 6. What success does NOT guarantee

Phase 1 builds the bridge — it does not:
- Upload any new photos (Phase 2)
- Assign any face names (Phase 3)
- Create any albums (Phase 4)

A successful bridge run only proves that the **lookup table** is correct. Each
subsequent phase has its own risk profile and should be runbooked separately
before execution.

Specifically: the bridge phase is **non-destructive and trivially reversible**.
Phases 3 and 4 modify Immich via API and need their own pre-flight backups
and rollback procedures (those will be written when we get there).
