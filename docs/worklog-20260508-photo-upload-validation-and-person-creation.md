# Session 0011 Worklog: Full Pipeline Validation + Person Creation

**Date:** 2026-05-08
**Status:** All validation complete, 2 bugs found and fixed

## Summary

Validated all HIGH-risk items from session 0010's "NOT READY" assessment. Wrote 7 new
integration tests covering full pipeline, multi-user upload, and HEIC files. Found and
fixed two bugs: (1) person mapping was too strict on ownerId, (2) 87 named Synology
persons had no Immich person record. Added Phase 3B to auto-create missing person
records. All 203 tests pass. Dry-run confirms 94/94 persons covered.

## Validation Performed

### Infrastructure
- Syno DB: 192.168.5.149, user=`app` (password from k8s secret `synofotopg-app`)
- Immich DB: 192.168.5.150, user=`immich` (password from k8s secret `immich` in `media` ns)
- Immich API: `kubectl port-forward -n media svc/immich-server 22830:2283`
- NFS mounts: all user dirs accessible
- 12,047 Immich assets, 246,241 Synology faces, 3 Immich users confirmed

### Existing test suite baseline
- Ran 196 tests: **196 passed, 0 failed** (before new tests)

## New Tests Written (7 tests)

| Test File | Tests | What It Validates |
|---|---|---|
| `test_full_pipeline.py` | 1 | End-to-end: Phase 2 upload → tracking table → Phase 4 face migration → verify asset_face + face_search rows |
| `test_multi_user_upload.py` | 3 | Upload as Chuni → ownership=Chuni, Upload as Serena → ownership=Serena, Multi-user correct owners |
| `test_heic_upload.py` | 3 | HEIC direct upload, HEIC asset retrievable, HEIC upload via Phase 2 pipeline |

### Test count: 196 → 203 passed, 0 failed

## Bugs Found and Fixed

### BUG 1: Person mapping required ownerId match (Phase 3)

**Problem:** `phase_person_mapping()` only matched Synology persons to Immich persons
when the Immich person's `ownerId` matched the mapped Immich user. This was wrong because:
- Synology user 2 (Chuni) maps to Immich `CHUNI_ID`
- But "Stephanie Kao" in Immich has `ownerId = MIKE_ID` (Mike uploaded those photos)
- Result: **0 out of 94 Synology persons matched**

**Fix:** Changed matching logic to prefer owner match, but fall back to any name match
when no owner match is found. After fix: **7 out of 94 persons matched**.

**File changed:** `migration.py` lines 496-516

### BUG 2: 87 named Synology persons had no Immich person record

**Problem:** After fixing BUG 1, 87 Synology persons still had no match in Immich.
These are real named people (ChuNi Kao, Daniel Tan, Darcy Tan, etc.) with 38,678 total
faces. Without person records in Immich, these faces would be migrated as anonymous
(personId=NULL).

**Fix:** Added `phase_create_missing_persons()` (Phase 3B) that INSERTs new person
records into Immich's `person` table for each unmatched Synology person. The person
ownerId is set to the mapped Immich user.

After fix: **94/94 persons covered** (7 existing + 87 created).

**File changed:** `migration.py` — new function + integration in `_run_migration()`

## Dry Run Results (final)

```
Users mapped:             4  (mikek, Lenaxia → Mike; lola-poo → Serena; chuni → Chuni)
Persons matched:          7  (existing in Immich)
Persons created:         87  (new records in Immich)
Total persons covered:   94
```

Top created persons by face count:
- ChuNi Kao (但初霓): 13,542 faces
- Darcy Tan: 4,517 faces
- Daniel Tan: 4,065 faces
- Rowan Kao-Yau: 1,911 faces

## Test Fix: UUID Type Cast Issue

The full pipeline test had a secondary bug in `_cleanup_tracking_tables()`:
comparing `uuid` column against `text[]` array. Fixed with `::text` cast.

## Files Created
- `tests/integration/test_full_pipeline.py` (1 test)
- `tests/integration/test_multi_user_upload.py` (3 tests)
- `tests/integration/test_heic_upload.py` (3 tests)

## Files Modified
- `migration.py` — fixed person mapping + added Phase 3B person creation
- `tests/integration/test_full_pipeline.py` — UUID type cast fix in cleanup

## Remaining Risks (Before Production Run)

1. **No concurrency** — Serial at ~0.15s/photo = ~2.8 hours for 66,771 units. Acceptable
   but could be faster with `--concurrency` flag.

2. **`IMMICH_USER_NAMES` hardcoded** — Works for the 3 mapped users but not extensible.

3. **Created persons have no thumbnail** — `thumbnailPath=""`. Immich will need to
   generate face thumbnails from the migrated face data. This may require running
   Immich's face detection job afterward.

## Recommended Next Steps

1. **Run `python3 migration.py --setup`** to create API keys
2. **Test with `python3 migration.py --execute --limit 50`** for a small batch
3. **Verify in Immich UI** that uploaded photos and faces look correct
4. **Full run: `python3 migration.py --execute`**
