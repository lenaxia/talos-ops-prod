# Synology Photos → Immich Migration: Technical Design

**Status:** Ready for implementation
**Date:** 2026-08-02
**Supersedes:** `README.md` (which targets Immich v2.6 schema, now v3.x), `03-face-migration/match_faces.py` (targets v2.6 tables)

---

## 1. Verified State (pre-migration)

### 1.1 Source: synofotopg (CNPG cluster, PG 16.8)

**Backup status:** `ContinuousArchiving=Success`, `LastBackupSucceeded=Success` — daily 13:00 UTC to `s3://cnpg-5wxuej/synofotopg16`, 30d retention. Healthy.

| Metric | Count |
|---|---:|
| Total units | 445,660 |
| Distinct photos (by MD5) | 288,178 |
| Redundant units (duplicates) | 157,482 (35%) |
| Face detections | 246,241 |
| Faces with person assigned | 245,150 |
| Named persons (curated) | 157 |
| Normal albums (curated) | 95 |
| Album memberships | 19,724 |

### 1.2 Target: vectorpg (CNPG cluster, PG 16.8, pgvector 0.8.0)

**Backup status:** `ContinuousArchiving=Success`, `LastBackupSucceeded=Success` — daily 12:00 UTC to `s3://cnpg-5wxuej/vectorpg16`, 30d retention. Healthy. **Fixed 2026-08-02** — was broken for 136 days due to missing barman-cloud binaries in `-standard-bookworm` image variant. Commit `abaeade7`.

| Metric | Count |
|---|---:|
| Users | 4 |
| Assets | 21,818 |
| Asset faces | 20,964 |
| Faces with person | 17,544 |
| People | 379 |
| Named people | 37 |
| Albums | 53 |
| `syno_photo_migration` rows | 1 (single test) |
| `syno_face_migration` rows | 0 |

### 1.3 Other CNPG clusters (backup health)

| Cluster | Backups | Notes |
|---|---|---|
| synofotopg | ✅ working | Migration source |
| vectorpg | ✅ working (fixed) | Immich DB |
| defaultpg | ✅ working | Phase: degraded (2/3 ready), but backups succeed |
| llmsafespacespg | ✅ working | Phase: degraded (2/3 ready), but backups succeed |
| dawarich-postgis | ❌ **failing** | All backups fail. Separate issue — image `postgis:16`, different root cause. Not blocking migration but should be fixed. |

---

## 2. User Reconciliation

The README's user map is outdated. Reconciled against live Immich accounts:

| Immich account | Email | Immich user ID (prefix) | Synology id_user(s) | Synology username(s) | Assets in Immich | Named faces |
|---|---|---|---|---|---:|---:|
| Mike | mike@kao.family | 3de3d105 | 5, 12 | Lenaxia, mikek@kao.family | 7,928 | 0 |
| Serena (lola-poo) | serenaw.chai@gmail.com | 8609dd3f | 9 | lola-poo@kao.family | 11,862 | 0 |
| Darcy | Darcytanchang@gmail.com | dfe560ec | 3, 7 | darcy, darcy@kao.family | 2,025 | 47 |
| Chuni | chunikao@gmail.com | 4bc1e174 | 2 | chuni | 0 | 94 |

**Not yet in Immich (need accounts + uploads):**

| Synology username | id_user | Units | Distinct photos | Named faces |
|---|---|---:|---:|---:|
| steviek | 6 | 104,960 | 93,310 | 16 |
| pandaria@kao.family | 16 | 20,410 | 20,092 | 0 |
| adonia | 1 | 200 | 171 | 0 |
| tjkao@kao.family | 14 | 3 | 3 | 0 |

**Lenaxia (id_user=5)** = Mike's old local account. Consolidate into Mike's Immich account. 4,868 units, 32 intra-user dupes.

**Serena** = lola-poo. Same person, different identity provider names.

### NFS path construction

Synology `folder.name` stores the full relative path (e.g. `/Moments/Mobile/Donuts X/2019-03-06`). Combined with the user's home directory:

| Account type | NFS path pattern |
|---|---|
| Local user | `NAS_ADDR:/volume1/homes/{syno_username}/Photos{folder.name}/{filename}` |
| LDAP user | `NAS_ADDR:/volume1/homes/@LH-KAO.FAMILY/61/{syno_username}/Photos{folder.name}/{filename}` |

Top-level folder prefixes observed: `/Moments/` (370K photos), `/MobileBackup/` (66K), `/allison mobile/` (9K), `/PhotoLibrary/` (1.8K), plus shared event albums.

---

## 3. Architecture Decisions

### 3.1 Bridge key: SHA-1 content hash

**Decision:** Walk the NFS-mounted Synology photos, compute SHA-1 of each file, match against Immich's `asset.checksum` (already SHA-1, zero compute on the Immich side).

**Why not filename:** chuni has 41K filename-collision groups (156K extra rows). `IMG_0001.JPG` maps to 19 different photos across 19 folders. Filename-based voting is unreliable.

**Why not (filename, takentime):** Still has 49K collision groups for chuni. Not unique enough.

**Why not Synology's `duplicate_hash` (MD5):** Different algorithm from Immich's SHA-1. Cannot cross-reference. Useful for dedup analysis within Synology but not for the bridge.

**Optimization:** Walk only the 288,178 distinct photos (dedupe by MD5 first, walk one representative path per MD5). Cuts walk time ~35%.

**NFS walk location:** Run inside the immich-server pod (or a dedicated job pod) that has NFS mounted read-only. Expected throughput: ~2-3 hours for 288K files on NFS.

### 3.2 Cross-user dedup: per-owner upload + post-hoc stacking (A+D)

**Decision:** Upload per-owner independently. `immich-cli` auto-dedupes intra-user (SHA-1 at upload). Cross-user duplicates stored N× but handled cleanly in UI by running Immich's duplicate-detection job afterward.

**Rationale:**
- Intra-user dupes: 128K — auto-deduped by `immich-cli` on upload.
- Cross-user dupes: 32,323 distinct photos shared across users, 52K redundant copies. Top case: one family photo in 6 users' libraries.
- Immich stores per-owner (no cross-owner dedup), but the duplicate-detection job groups them into `stack` records for clean UX.
- Extra storage cost: ~52K redundant copies (~10-50GB depending on avg photo size). Acceptable for simplicity.

### 3.3 Face matching: IoU coordinate matching (Option B)

**Decision:** Let Immich re-detect faces with its own ML model (antelopev2), then match Synology's curated named-person data to Immich people via bounding-box coordinate overlap.

**Why not translate Synology embeddings (Option A):**
- Synology `face.feature` is a proprietary 512-d blob (DeepFace-derived).
- Immich uses InsightFace antelopev2 (also 512-d, different embedding space).
- Incompatible — cannot compare or project without thousands of paired samples for training.
- Bypassing Immich's pipeline to write directly to `asset_face` is fragile and breaks on upgrades.

**Matching algorithm (per named person):**
1. Query Synology `many_unit_has_many_person` → `unit` → bridge → Immich asset IDs.
2. For each matched asset, find the Immich `asset_face` row with highest IoU (intersection-over-union) against the Synology `face.bounding_box`.
3. Record the Immich `personId` from that best-IoU face.
4. Majority vote across all matched faces → winning `personId`.

**Ambiguity detection (relative margin, not absolute threshold):**
- **Auto-assign:** top `personId` votes ≥ 2× runner-up AND ≥ 5 absolute votes.
- **Flag for review:** otherwise. Emit CSV with deep links to `/people/{candidatePersonId}` + sample asset links.

**Why `many_unit_has_many_person` and not `face`:**
The `face` table includes all ML detections including unnamed strangers. `many_unit_has_many_person` only contains user-confirmed named-person associations — the authoritative source.

---

## 4. Implementation Phases

### Phase 0: Prerequisites

#### 0.1 NFS access via temporary migration Job (not permanent mount)

**Decision:** Do NOT modify immich-server's helm-release. NFS access is only needed for Phases 1 (SHA-1 walk) and 2 (upload). After that, everything is DB queries + Immich API. A permanent mount pollutes the production immich-server with I/O-heavy access it doesn't need long-term.

Instead, run migration scripts inside a **dedicated Job pod** (`migration/job/`) that:
- Mounts both NFS shares read-only at `/import/syno-local` and `/import/syno-ldap`
- Connects to both CNPG clusters via in-cluster services (no port-forward)
- Auto-terminates on completion — no leftover mounts

The Job is **not** managed by Flux (the `cluster-media-immich` kustomization only watches `./kubernetes/apps/media/immich/app`). Apply manually when ready:
```bash
kubectl apply -k kubernetes/apps/media/immich/migration/job/
```

Verify NFS access inside the Job pod before running scripts:
```bash
kubectl exec -n media job/syno-immich-migration -- ls /import/syno-local/
kubectl exec -n media job/syno-immich-migration -- ls /import/syno-ldap/
```

#### 0.2 Fix ML service (optional but recommended)

Immich machine-learning is currently failing (`Machine learning request failed for all URLs`). This blocks Immich's own face detection, which is a prerequisite for Phase 3 (IoU matching needs Immich face rows to exist).

Check `immich-machine-learning` pod logs and the OpenVINO/GPU device assignment.

#### 0.3 Pre-migration backup snapshot

Trigger a manual backup of both DBs before any migration writes:
```bash
kubectl create backup manual-pre-migration-vectorpg -n databases \
  --cluster vectorpg
kubectl create backup manual-pre-migration-synofotopg -n databases \
  --cluster synofotopg
```

---

### Phase 1: SHA-1 Bridge Script

**Script:** `migration/01-build-bridge.py`
**Output:** Populates `immich.syno_photo_migration(syno_unit_id, immich_asset_id, syno_user_id)`

#### 1.1 Algorithm

```
1. Query Synology: SELECT DISTINCT ON (duplicate_hash)
     id AS unit_id, id_user, filename, id_folder, duplicate_hash
   FROM unit WHERE duplicate_hash <> ''
   ORDER BY duplicate_hash, id
   → 288,178 distinct photos with their canonical unit_id

2. For each distinct photo:
   a. Construct NFS path from (id_user → username, folder.name, filename)
   b. Read file from NFS mount, compute SHA-1
   c. Query Immich: SELECT id, "ownerId" FROM asset
      WHERE checksum = %s AND "deletedAt" IS NULL
   d. For each Immich asset found (may be multiple — one per owner):
      INSERT INTO syno_photo_migration (syno_unit_id, immich_asset_id, syno_user_id)
      VALUES (%s, %s, %s) ON CONFLICT DO NOTHING

3. Also map all OTHER units sharing the same duplicate_hash
   to the same immich_asset_id(s):
   INSERT INTO syno_photo_migration
   SELECT u.id, %s, u.id_user FROM unit u WHERE u.duplicate_hash = %s
   ON CONFLICT DO NOTHING
```

#### 1.2 User → Immich ownerId mapping

The bridge must map Synology `id_user` to Immich `ownerId` so cross-user dupes (same SHA-1, different owners) each get their own bridge row:

```python
SYNO_TO_IMMICH = {
    # syno_user_id: (immich_user_id, nfs_mount, home_subpath)
    1:  (None,                  "syno-local", "adonia"),           # not in Immich yet
    2:  ("4bc1e174-...",        "syno-local", "chuni"),            # Chuni
    3:  ("dfe560ec-...",        "syno-local", "darcy"),            # Darcy (local)
    5:  ("3de3d105-...",        "syno-local", "Lenaxia"),          # → Mike
    6:  (None,                  "syno-local", "steviek"),          # not in Immich yet
    7:  ("dfe560ec-...",        "syno-ldap",  "darcy-1000005"),    # Darcy (LDAP)
    9:  ("8609dd3f-...",        "syno-ldap",  "lola-poo-1000017"), # Serena
    12: ("3de3d105-...",        "syno-ldap",  "mikek-1000032"),    # Mike (LDAP)
    14: (None,                  "syno-ldap",  "tjkao-1000018"),    # not in Immich yet
    16: (None,                  "syno-ldap",  "pandaria-1000034"), # not in Immich yet
}
```

#### 1.3 Path construction

```python
def nfs_path(syno_user_id, folder_name, filename):
    _, mount, home = SYNO_TO_IMMICH[syno_user_id]
    mount_root = f"/import/{mount}"
    return f"{mount_root}/{home}/Photos{folder_name}/{filename}"
    # e.g. /import/syno-local/chuni/Photos/Moments/Mobile/Donuts X/2019-03-06/IMG_6433.PNG
```

#### 1.4 Expected results

- Bridge rows created for the 21,818 already-uploaded assets.
- Remaining 266K distinct photos → logged to `bridge_unmatched.csv` (not yet uploaded).
- Stats: total distinct, matched, unmatched, by-user breakdown.

#### 1.5 Idempotency

- `syno_photo_migration` PK is `syno_unit_id` — `ON CONFLICT DO NOTHING` makes re-runs safe.
- Script is resumable: query `SELECT syno_unit_id FROM syno_photo_migration` at start, skip already-bridged units.

#### 1.6 Performance

- 288K SHA-1 computations on NFS: I/O-bound, ~2-3 hours.
- Batch Immich checksum lookups: `WHERE checksum = ANY(%s)` with batches of 500.
- Progress bar + checkpoint every 1000 files.
- Runs inside the migration Job pod (not immich-server) so heavy NFS I/O doesn't affect production.

---

### Phase 2: Upload Script (missing users)

**Script:** `migration/02-upload/upload.py` (replaces existing `upload.sh`)
**Purpose:** Upload photos for users not yet in Immich, pre-deduped by Synology MD5.

#### 2.1 Scope

| User | Distinct photos | Priority | Named faces |
|---|---:|---|---:|
| steviek | 93,310 | High | 16 |
| chuni (re-upload) | 125,413 | High | 94 |
| pandaria | 20,092 | Low | 0 |
| adonia | 171 | Low | 0 |
| tjkao | 3 | Low | 0 |

chuni has 0 assets in Immich despite having an account — likely upload failed or was never run.

#### 2.2 Approach

Use `immich-cli` in a Kubernetes Job (or exec into immich-server pod) with per-user API keys. Upload from the NFS-mounted Synology paths.

Pre-dedup: instead of uploading all 445K units, generate a file list of only the 288K distinct photos (by MD5) so `immich-cli` doesn't waste time hashing duplicates:

```bash
# Generate deduped file list per user from synofotopg
psql ... -c "SELECT DISTINCT ON (duplicate_hash) construct_path(...) AS path
            FROM unit WHERE id_user = 6 AND duplicate_hash <> ''
            ORDER BY duplicate_hash, id" > steviek-files.txt
```

Then:
```bash
immich upload --recursive --album --ignore '**/@eaDir/**' --from-file steviek-files.txt
```

#### 2.3 Post-upload

After each user's upload completes:
1. Trigger Immich jobs: Metadata Extraction → Thumbnail Generation → Face Detection.
2. Wait for Face Detection to complete (monitor via Immich admin → Jobs).
3. Re-run Phase 1 bridge script for the newly-uploaded assets.

---

### Phase 3: Face Name Matcher (v3 rewrite)

**Script:** `migration/03-face-migration/match_faces.py` (full rewrite)
**Depends on:** Phase 1 bridge populated, Immich face detection complete.

#### 3.1 Immich v3.x schema (corrected from v2.6)

| Old (v2.6) | New (v3.x) | Notes |
|---|---|---|
| `users` | `user` | Reserved keyword escape |
| `face` | `asset_face` | Renamed |
| `album.ownerId` | `album_user(role=owner)` | Owner moved to junction table |
| `asset.fileSizeByte` | `asset_file` table | Size moved to separate table |
| `face.boundingBoxX1` (float) | `asset_face.boundingBoxX1` (int) | Now integer pixels |

#### 3.2 Bounding box format comparison

**Synology** (`face.bounding_box` JSON): normalized 0.0–1.0
```json
{"top_left": {"x": 0.17, "y": 0.33}, "bottom_right": {"x": 0.29, "y": 0.46}}
```

**Immich** (`asset_face` columns): integer pixels
```
boundingBoxX1, boundingBoxY1, boundingBoxX2, boundingBoxY2
imageWidth, imageHeight
```

**IoU computation:** Convert Synology normalized coords to pixel space using Immich's `imageWidth/imageHeight`, then compute intersection-over-union:

```python
def iou(syno_box, immich_face):
    # Convert Synology normalized → pixel
    w, h = immich_face["imageWidth"], immich_face["imageHeight"]
    sx1 = syno_box["top_left"]["x"] * w
    sy1 = syno_box["top_left"]["y"] * h
    sx2 = syno_box["bottom_right"]["x"] * w
    sy2 = syno_box["bottom_right"]["y"] * h

    # Immich already in pixels
    ix1, iy1 = immich_face["x1"], immich_face["y1"]
    ix2, iy2 = immich_face["x2"], immich_face["y2"]

    # Intersection
    xi1, yi1 = max(sx1, ix1), max(sy1, iy1)
    xi2, yi2 = min(sx2, ix2), min(sy2, iy2)
    inter = max(0, xi2 - xi1) * max(0, yi2 - yi1)

    # Union
    area_s = (sx2 - sx1) * (sy2 - sy1)
    area_i = (ix2 - ix1) * (iy2 - iy1)
    union = area_s + area_i - inter

    return inter / union if union > 0 else 0.0
```

**Note:** Synology does not store image dimensions in `unit` or `metadata` tables. Immich's `asset_face.imageWidth/imageHeight` is the source of truth for the matching asset. Since the same photo produces the same face in both systems (just different embedding models), the pixel dimensions should match.

#### 3.3 Matching algorithm (per named person)

```
For each Synology named person (157 total):
  1. Get all Synology units for this person:
     SELECT u.id, f.id AS face_id, f.bounding_box
     FROM many_unit_has_many_person m
     JOIN unit u ON u.id = m.id_unit
     JOIN face f ON f.id_unit = u.id AND f.id_person = m.id_person
     WHERE m.id_person = %s

  2. For each (unit, face):
     a. Look up immich_asset_id from syno_photo_migration
     b. If not bridged → skip (log to unmatched: not_uploaded)
     c. Get all Immich asset_face rows for that asset:
        SELECT id, "personId", "boundingBoxX1", ..., "imageWidth", "imageHeight"
        FROM asset_face WHERE "assetId" = %s AND "deletedAt" IS NULL
     d. Compute IoU against each → pick best match (IoU > 0.3 threshold)
     e. Record (syno_face_id, immich_face_id, immich_asset_id, immich_personId)
        → INSERT INTO syno_face_migration
     f. Tally vote: immich_personId → vote_count

  3. Vote resolution:
     Sort personIds by vote_count descending.
     top = votes[0], second = votes[1] (if exists)

     AUTO_ASSIGN if:
       top.votes >= 5  AND  top.votes >= 2 * second.votes

     FLAG_FOR_REVIEW otherwise.

  4. If auto-assign:
     - Check if Immich person already has a name (GET /api/people/{id})
     - If empty → PUT /api/people/{id} {name: syno_person_name}
     - If non-empty and different → log conflict, skip
```

#### 3.4 Output files

**`matched.csv`** — auto-assigned names:
```
username, syno_person_name, immich_person_id, votes, runner_up_votes,
runner_up_person_id, total_faces_matched, iou_mean, iou_min, action
```

**`unmatched.csv`** — needs manual review:
```
username, syno_person_name, immich_person_id (best guess), votes,
runner_up_person_id, runner_up_votes, reason, review_url
```

`review_url` = `https://immich.${SECRET_DEV_DOMAIN}/people/{immich_person_id}` for quick eyeball verification.

#### 3.5 Scope

Only 3 Synology users have named faces:
- chuni (id=2): 94 named persons — **needs upload first** (0 assets in Immich)
- darcy (id=3,7): 47 named persons — partial (2,025 assets in Immich)
- steviek (id=6): 16 named persons — **needs upload + Immich account first**

Total: 157 named persons. Expected auto-match rate: ~80-90% (based on typical IoU > 0.3 hit rates when both systems detect the same face). Expected manual review: ~15-30 persons.

#### 3.6 Idempotency

- `syno_face_migration` PK is `syno_face_id` — `ON CONFLICT DO NOTHING` on re-runs.
- Skip Synology faces already in `syno_face_migration`.
- Person name assignment is checked before overwriting (skip if already named).
- `--person "Name"` flag to re-run a single person after merging clusters in Immich UI.

---

### Phase 4: Album Migration

**Script:** `migration/04-albums/migrate_albums.py`
**Depends on:** Phase 1 bridge populated.

#### 4.1 Scope

95 curated Synology `normal_album` entries with 19,724 item memberships. These are user-curated albums NOT tied to folder structure (e.g. "2005 Oct 昆明，重慶，北京" with 4,335 items, "2022 Morocco" with 3,033 items).

The existing 53 Immich albums are iPhone-derived (Mike's mobile app sync: Recents, Live Photos, Selfies, etc.) — **not** Synology albums. No collision concern.

#### 4.2 Schema mapping

| Synology | Immich | Notes |
|---|---|---|
| `normal_album.id` | `album.id` (new UUID) | No ID preservation |
| `normal_album.name` | `album.albumName` | Direct copy |
| `normal_album.id_user` | `album_user(userId, role=owner)` | Map via SYNO_TO_IMMICH |
| `many_item_has_many_normal_album.id_item` → `item.id_unit` | `album_asset(albumId, assetId)` | Via bridge |

Join chain: `many_item_has_many_normal_album` → `item` (on `id_item`) → `unit` (on `unit.id_item = item.id`) → `syno_photo_migration` (on `syno_unit_id`) → Immich `asset.id`.

#### 4.3 Algorithm

```
For each Synology normal_album:
  1. Determine Immich ownerId from normal_album.id_user via SYNO_TO_IMMICH
     If owner not in Immich yet → skip album (log to album_skipped.csv)

  2. Collect all member asset IDs:
     SELECT spm.immich_asset_id
     FROM many_item_has_many_normal_album m
     JOIN item i ON i.id = m.id_item
     JOIN unit u ON u.id_item = i.id
     JOIN syno_photo_migration spm ON spm.syno_unit_id = u.id
     WHERE m.id_normal_album = %s

  3. Create Immich album via REST API:
     POST /api/albums {albumName, ownerId, assetIds: [...]}
     → returns album UUID

  4. Log to album_migrated.csv:
     syno_album_id, syno_album_name, immich_album_id, asset_count, skipped_count
```

#### 4.4 REST API approach (not direct DB writes)

Albums should be created via Immich's REST API (`POST /api/albums`), not direct DB inserts. This ensures:
- Audit triggers fire correctly (`album_audit`, `album_asset_audit`).
- Thumbnail generation is triggered.
- Search indexing updates.
- Album updateId propagation works.

#### 4.5 Idempotency

- Before creating, check if album with same name + same owner already exists:
  `GET /api/albums?ownerId=...` → match by `albumName`.
- If exists, add missing assets via `PUT /api/albums/{id}/assets` (deduped by Immich).
- Log all actions to `album_migrated.csv`.

---

## 5. Execution Order

```
Phase 0.1  Mount NFS imports into immich-server           [prerequisite]
Phase 0.2  Fix ML service (face detection)                [prerequisite for Phase 3]
Phase 0.3  Manual pre-migration backups                   [safety net]
    │
    ├─ Phase 1   Build SHA-1 bridge (existing 21K assets) [2-3h NFS walk]
    │            → verify bridge coverage
    │
    ├─ Phase 2   Upload missing users (chuni, steviek…)   [hours-days depending on upload]
    │            → trigger face detection jobs
    │            → re-run Phase 1 for new assets
    │
    ├─ Phase 3   Face name matcher                        [minutes — DB queries + API calls]
    │            → dry-run → review → apply
    │
    ├─ Phase 4   Album migration                          [minutes — REST API]
    │
    └─ Phase 5   Post-migration
                 → Run Immich duplicate-detection job     [stacks cross-owner dupes]
                 → Verify albums, faces, people in UI
                 → Drop synofoto DB when satisfied
                 → Remove NFS import mounts
```

Phases 1 and 2 can partially overlap: upload chuni/steviek while the bridge walk runs for existing assets.

---

## 6. Configuration

All scripts read from a single gitignored config file (`migration/config.yaml`):

```yaml
# Database connections (read from CNPG secrets — populate manually)
syno_db: "host=192.168.5.149 port=5432 dbname=app user=app password=..."  # synofotopg-lb
immich_db: "host=vectorpg-rw.databases.svc.cluster.local port=5432 dbname=immich user=immich password=..."

# Immich API
immich_url: "https://immich.${SECRET_DEV_DOMAIN}"
# Per-user API keys (generate in Immich UI → Settings → API Keys)
users:
  - immich_username: mike
    immich_user_id: "3de3d105-f5f0-4156-bbca-91857f21dcc8"
    immich_api_key: "REPLACE_ME"
    syno_user_ids: [5, 12]
  - immich_username: serena
    immich_user_id: "8609dd3f-e548-4d56-b474-b1431193dc35"
    immich_api_key: "REPLACE_ME"
    syno_user_ids: [9]
  - immich_username: darcy
    immich_user_id: "dfe560ec-b20a-46b1-8e72-bd745441b353"
    immich_api_key: "REPLACE_ME"
    syno_user_ids: [3, 7]
  - immich_username: chuni
    immich_user_id: "4bc1e174-e8e7-4f93-9a9f-20422a2383c8"
    immich_api_key: "REPLACE_ME"
    syno_user_ids: [2]

# NFS mount roots (inside immich-server pod)
nfs:
  syno_local: "/import/syno-local"
  syno_ldap: "/import/syno-ldap"
```

**Never commit `config.yaml`.** It contains API keys and DB passwords. Add to `.gitignore`.

---

## 7. Risk Mitigation

| Risk | Mitigation |
|---|---|
| Bridge maps wrong asset (SHA-1 collision) | SHA-1 collision probability is negligible for 288K files. Immich already trusts SHA-1 for dedup. |
| IoU matching picks wrong face in group photos | Relative-margin threshold (2× runner-up) + minimum 5 votes. Ambiguous cases flagged, not auto-assigned. |
| Synology face coords don't align with Immich (different crop/scale) | Both systems detect on the original image. If re-encoded, SHA-1 won't match anyway (excluded from bridge). |
| Immich person clusters fragmented (one person split into 2+ clusters) | Merge clusters in Immich UI first, then re-run matcher with `--person "Name"`. |
| NFS walk takes too long | Dedup by MD5 first (288K not 445K). Batch SHA-1 computation. Resumable via bridge table checkpoint. |
| Migration writes corrupt Immich DB | Phase 0.3 manual backup. All writes go through Immich REST API (not direct DB writes) except bridge/face tracking tables which are append-only. |

---

## 8. Deprecated Files

The following files from the previous migration attempt are **superseded** by this design:

| File | Status | Reason |
|---|---|---|
| `README.md` | **Outdated** | Targets Immich v2.6 schema (`users`, `face`, `album.ownerId`). v3.x renamed all three. User list doesn't include Serena. |
| `03-face-migration/match_faces.py` | **Broken** | Queries `face`, `users` tables that don't exist in v3.x. Uses filename-only matching (unreliable). |
| `03-face-migration/schema_notes.md` | **Partially correct** | Synology schema notes still valid. Immich schema notes target v2.6 — use section 3.1 above instead. |
| `01-nfs-setup.md` | **Still valid** | NFS setup instructions are accurate. Phase 0.1 above is the condensed version. |
