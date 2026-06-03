# Work Log 0009: Session Summary — Photo Upload Investigation and Plan

## Date: 2026-05-08
## Session Duration: Extended

---

## Context

This session picked up where 0007 left off. The face migration script was complete
and passing 156 tests, but the underlying asset matching (filename-based, 14-32%
match rate) was identified as fundamentally broken. The session pivoted to designing
a better approach: upload photos to Immich ourselves and use the returned asset ID
directly, eliminating the need for matching entirely.

---

## What Was Accomplished

### 1. Face Migration Script — Final Bug Fixes ✅

After the session 0007 adversarial review, a second round of adversarial
re-validation was performed. One **critical bug** was found that had survived
all prior reviews:

**B-1: Duplicate batch append (fatal in execute mode)**
`batch_search.append()` and `batch_tracking.append()` were called twice per face
in the migration loop — a copy/paste artifact from refactoring. In execute mode
this would cause a primary key violation on the first batch (two rows with the
same `faceId`), rolling back all inserts. The script appeared to work correctly
in dry-run mode because appends don't matter when there are no writes.

Fix: removed the duplicate append block (6 lines deleted).

**Additional fixes from final re-validation:**
- Audit log now written in both `--dry-run` AND `--execute` mode (was dry-run only)
- Stale docstring referencing `--resume` flag updated
- Dead code removed: unused `CHECKPOINT_PATH` constant, unused
  `get_assets_with_existing_faces()` function

**Test result after all fixes: 158/158 tests pass**

---

### 2. Medium Findings — Per-Face Transform Extraction ✅

The 100-line face loop in `migration.py` had no testable unit boundary.
Extracted the core transform logic into `migration_core.transform_face()` — a
pure function:

```python
def transform_face(feature_blob, bbox_text, res_text, syno_person_id, person_map) -> Optional[dict]
```

Returns `None` if the face should be skipped, or a dict with `embedding_512`,
`bbox`, `width`, `height`, `person_id` on success.

Added 23 unit tests in `tests/unit/test_transform_face.py` covering:
- NULL/missing embedding blob, resolution JSON, bbox JSON
- Resolution missing `width` or `height` keys
- Invalid JSON strings
- Zero-area and inverted bboxes
- NULL and unmapped `personId`
- Bbox clamping at image boundaries

---

### 3. Immich API Research and Validation ✅

A provided bash script claimed to use `POST /api/auth/login` to get per-user
Bearer tokens and then `POST /api/api-keys` to create per-user API keys.

**Validated against the real Immich v2.7.5 instance:**

| Claim | Result |
|---|---|
| `POST /api/auth/login` returns `accessToken` | **FALSE** — "Password login has been disabled". All users auth via OIDC (Authentik). |
| Admin can create API keys for other users via API | **FALSE** — `POST /api/api-keys` always creates under the authenticated user, `userId` in request body is ignored. |
| DB-inserted API keys work | **TRUE** — Insert `SHA-256(random_hex(32))` as `bytea` into `api_key` table; tested `GET /api/users/me` returns correct user profile. |
| `POST /api/assets` upload works | **TRUE** — Tested with real JPG and HEIC via port-forward, returns `{id, status:"created"}`. |
| `immich` CLI installed | **FALSE** — not installed; not needed since HTTP API works directly. |

**Current state of Immich DB:**
- 3 API keys created for testing:
  - `migration-admin-key` → Mike (admin)
  - `migration-serena` → Serena
  - `migration-chuni` → Chuni
- 17 test assets created (from API testing, not real migration)
- 0 tracking tables created yet

---

### 4. Asset Matching Investigation ✅

**Root cause of 14-32% filename match rate:**
- `originalFileName` is not unique: `IMG_0001.JPG` appears across thousands of photos
- Immich re-encodes photos on upload: content hashes (SHA-1) don't match originals
- Synology stores MD5 (`duplicate_hash`), Immich stores SHA-1 (`checksum`): incompatible
- Zero hash overlap confirmed across 10k sampled assets from both sides

**Conclusion:** Reliable matching between existing Immich assets and Synology
units is not possible. The only reliable link is: upload the photo yourself,
get the asset ID back.

---

### 5. Photo Directory Structure Discovery ✅

Synology homes are mounted at `/mnt/homes/`. Two user types:

**Local users** (already working):
```
/mnt/homes/chuni/Photos/
/mnt/homes/Lenaxia/Photos/
/mnt/homes/steviek/Photos/
/mnt/homes/darcy/Photos/
/mnt/homes/adonia/Photos/
```

**LDAP users** (discovered this session):
```
/mnt/homes/@LH-KAO.FAMILY/61/mike-1000032/Photos/
/mnt/homes/@LH-KAO.FAMILY/61/lola-poo-1000017/Photos/
/mnt/homes/@LH-KAO.FAMILY/61/pandaria-1000034/Photos/
```

Path reconstruction: `folder.name` in the Synology DB contains the full path
relative to the user's `Photos/` directory. Strip the leading `/`, join with
the base directory and `unit.filename`. Validated 10/10 for all 8 users.

---

### 6. Open Question Validation ✅

Prior plan had 6 unvalidated assumptions (U1–U6). Results:

| # | Question | Answer |
|---|---|---|
| U1 | `deviceAssetId` idempotency | **FALSE** — Same deviceAssetId + different file content = two separate assets. Must use tracking table for idempotency. |
| U2 | Immediate face INSERT after upload | **TRUE** — Tested: upload photo, INSERT face, read back, face persists. Asset not affected. |
| U3 | Atomicity gap (upload ok, tracking fails) | **Accept** — upload then track. Orphaned asset risk is low; manual cleanup if it occurs. |
| U4 | HEIC support | **TRUE** — Tested lola-poo `.HEIC` file, returns `{id, status:"created"}`. |
| U5 | Live Photos — face on photo or video? | **Answered**: All 111,142 face-bearing units are type=0 (image only). No face-bearing video units exist. Live Photo video component carries no face records. |
| U6 | Timestamp format | **Not yet tested** — need to verify `takentime` (seconds epoch) and `createtime` (milliseconds epoch) convert correctly to Immich `fileCreatedAt` ISO 8601 format. |

---

### 7. Photo + Face Migration Plan ✅

Documented in `0008_photo_migration_plan.md`. Plan status: **APPROVED**.

**Core change from old approach:**
- Old: match Synology faces to existing Immich assets by filename (broken)
- New: upload photos to Immich ourselves → get asset ID → use directly

**Four phases:**
0. Setup: create per-user API keys via DB insert
1. User mapping: manual overrides (mikek+Lenaxia→Mike, lola-poo→Serena, chuni→Chuni)
2. Photo upload: `POST /api/assets` per face-bearing unit, track in `syno_photo_migration`
3. Person mapping: name-based match to existing Immich persons
4. Face migration: same `transform_face()` logic, but `unit_to_asset` from tracking table

**Idempotency:**
- `syno_photo_migration` (PK: `syno_unit_id`) — photo upload tracker
- `syno_face_migration` (PK: `syno_face_id`) — face insert tracker
- Each phase independently resumable; crash-and-restart produces correct result

---

## Current State of All Files

```
scripts/
  migration_core.py          Core library: decode, bbox, user map, asset match,
                             transform_face(). All pure functions.
  migration.py               Production script: 4 phases, --dry-run/--execute,
                             --limit, --user, --batch-size, rollback docs.
  run_tests.py               Test runner CLI.
  tests/
    unit/
      test_embeddings.py     26 tests — embedding decode, quality, 256→512
      test_coordinates.py    19 tests — bbox conversion, clamping, validation
      test_user_mapping.py   14 tests — user mapping, email/name match
      test_recovery.py       13 tests — checkpoint load/save
      test_asset_matching.py 20 tests — ImmichAssetIndex, match_syno_to_immich
      test_transform_face.py 23 tests — transform_face() all edge cases
    integration/
      test_real_databases.py 33 tests — real Synology + Immich DBs
                                       includes TestLimitFlag (2 tests)
    performance/
      test_performance.py    10 benchmarks
  0006_session_worklog.md    Session 6: DB restore, test suite, schema analysis
  0007_adversarial_review_fixes.md  Session 7: critical bug fixes
  0008_photo_migration_plan.md      Session 8: photo migration plan (APPROVED)
  0009_session_worklog.md    This file
```

**Test count: 158/158 passing**

---

## Remaining Work

### IMMEDIATE: Validate before writing new code

| # | Task | Notes |
|---|---|---|
| V1 | Validate timestamp format for upload | `takentime` (epoch seconds), `createtime` (epoch ms), `mtime` (epoch seconds). Need to verify ISO 8601 conversion and that Immich stores/displays correct dates. |
| V2 | Measure upload throughput | Upload 10 photos serially, time it. Estimate total time for 11k (Mike) + 7k (Serena) + 48k (Chuni). |
| V3 | Clean up test assets | 17 test assets were created in Immich during API testing. Delete them before migration to avoid noise. |
| V4 | Decide on concurrency | Serial is safe but slow. Async or threading for Phase 2. Recommend: test at concurrency=1, then 4. |

### Phase 0 — Setup (new code needed)

- [ ] `phase_setup_api_keys()` in `migration.py`
  - Insert per-user API keys into Immich `api_key` table
  - Store secrets in a local `.migration_secrets.json` (gitignored)
  - Idempotent: check if key already exists before inserting
  - Cleanup flag: `--cleanup-keys` deletes all `migration-*` keys

### Phase 2 — Photo upload (new code needed)

- [ ] `ensure_photo_tracking_table()` in `migration.py`
- [ ] `get_already_uploaded()` — load `syno_photo_migration` set before upload loop
- [ ] `build_file_path(unit_id, folder_name, filename, syno_user_id)` in `migration_core.py`
  - Maps syno_user_id to base directory
  - Strips leading `/` from `folder.name`
  - Returns full path or `None` if file not found
- [ ] `upload_photo(file_path, api_key, metadata)` in `migration_core.py`
  - `POST /api/assets` via `requests` or `httpx`
  - Returns `asset_id` or raises on failure
  - Formats `fileCreatedAt` and `fileModifiedAt` correctly
- [ ] Phase 2 loop in `migration.py`
  - Query all face-bearing units for mapped users
  - Skip already-uploaded (tracking table check)
  - Upload + track in sequence; log orphaned asset IDs on tracking failure
  - Batch progress reporting (every 100 uploads)
- [ ] Update Phase 4 to source `unit_to_asset` from `syno_photo_migration` table
  instead of `ImmichAssetIndex` filename matching

### Tests needed (TDD order)

- [ ] `test_build_file_path()` — unit test: local user, LDAP user, missing user,
  missing file, special characters in path
- [ ] `test_upload_photo()` — integration test against real Immich (upload, verify
  asset exists, verify asset_id returned, clean up)
- [ ] `test_photo_tracking_idempotency()` — upload same unit twice, verify only
  one asset created and tracking table has one row
- [ ] `test_timestamp_conversion()` — unit test: takentime=0, takentime=epoch,
  createtime=ms-epoch, mtime=epoch
- [ ] `test_phase2_full()` — integration: run phase 2 for user 5 (Lenaxia, 266 units)
  with `--limit 5`, verify tracking table has 5 rows, verify 5 Immich assets exist
- [ ] `test_crash_resume_upload()` — integration: run phase 2 with limit=3, then
  run again with limit=10, verify no duplicates in tracking table

### Cleanup before production run

- [ ] Delete 17 test assets created during API validation
- [ ] Confirm `migration-admin-key`, `migration-serena`, `migration-chuni` API keys
  are still valid (they were created with correct SHA-256 hashes)
- [ ] Run `--dry-run` on all 4 mapped users to get final face count estimate
- [ ] Confirm `/mnt/homes/` mount is still accessible and read-only

### Production run sequence (once all tests pass)

```
# 1. Test run: 10 faces for Lenaxia (smallest user)
SYNO_DB_PASSWORD=... IMMICH_DB_PASSWORD=... python3 migration.py \
    --execute --user 5 --limit 10

# 2. Verify in Immich UI: do 10 photos appear? Do face boxes look correct?

# 3. If good, full Lenaxia run
python3 migration.py --execute --user 5

# 4. If good, full Serena run
python3 migration.py --execute --user 9

# 5. If good, Mike run (larger: users 12 + 5 already done)
python3 migration.py --execute --user 12

# 6. Chuni run (largest: 48k face-bearing units, ~117k faces)
# This may take hours. idempotency ensures safe resume.
python3 migration.py --execute --user 2

# 7. Post-migration: cleanup API keys
python3 migration.py --cleanup-keys

# 8. Trigger Immich ML re-processing to regenerate native 512-D embeddings
```

### Post-migration

- [ ] Trigger Immich face re-detection on migrated photos to replace
  zero-padded 256→512D embeddings with native Immich embeddings
- [ ] Evaluate whether Synology person labels transferred correctly
- [ ] Verify face clustering in Immich UI looks reasonable

---

## Key Constants and Credentials

**Database endpoints (env vars required):**
```
SYNO_DB_HOST=192.168.5.149  SYNO_DB_PASSWORD=...
IMMICH_DB_HOST=192.168.5.150  IMMICH_DB_PASSWORD=...
```

**Immich API endpoint:**
```
http://immich-server.media.svc.cluster.local:2283  (in-cluster)
kubectl port-forward -n media svc/immich-server 22830:2283  (local dev)
```

**Immich user IDs:**
```
Mike:   3de3d105-f5f0-4156-bbca-91857f21dcc8  (admin)
Serena: 8609dd3f-e548-4d56-b474-b1431193dc35
Chuni:  4bc1e174-e8e7-4f93-9a9f-20422a2383c8
```

**Synology user → photo directory:**
```
2  chuni      /mnt/homes/chuni/Photos/
5  Lenaxia    /mnt/homes/Lenaxia/Photos/
12 mikek      /mnt/homes/@LH-KAO.FAMILY/61/mike-1000032/Photos/
9  lola-poo   /mnt/homes/@LH-KAO.FAMILY/61/lola-poo-1000017/Photos/
6  steviek    /mnt/homes/steviek/Photos/      (unmapped to Immich)
16 pandaria   /mnt/homes/@LH-KAO.FAMILY/61/pandaria-1000034/Photos/  (unmapped)
3  darcy      /mnt/homes/darcy/Photos/        (unmapped)
1  adonia     /mnt/homes/adonia/Photos/       (unmapped)
```

**User mapping (Synology → Immich):**
```
12 mikek    → Mike    3de3d105...  (also: 5 Lenaxia → Mike)
9  lola-poo → Serena  8609dd3f...
2  chuni    → Chuni   4bc1e174...  (0 Immich assets today, will grow)
```

---

## Scale Estimates

| User | Face-bearing units | Faces | Est. upload time (2s/photo) |
|---|---|---|---|
| Lenaxia (5) | 271 | 989 | ~9 min |
| lola-poo (9) | 7,371 | 18,714 | ~4 hr |
| mikek (12) | 11,269 | 22,576 | ~6 hr |
| chuni (2) | 48,328 | 117,170 | ~27 hr |
| **Total** | **67,239** | **159,449** | **~37 hr serial** |

Concurrency=4 would reduce to ~9 hours total. Idempotency means this can be
run across multiple sessions.
