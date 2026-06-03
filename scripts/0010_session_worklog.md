# Session 0010 Worklog: Photo Upload Pipeline + CLI Integration

**Date:** 2026-05-08
**Status:** Code complete, NOT yet production-run

## Summary

Built the complete photo upload pipeline (Phase 0 + Phase 2), wired it into the CLI,
and updated Phase 4 to source asset mappings from the upload tracking table instead of
broken filename matching. All 169 tests pass against live databases.

## Validation Performed

### Infrastructure (all validated, all OK)
- Synology DB: 192.168.5.149 via LB, user=`app` (was `postgres`, fixed)
- Immich DB: 192.168.5.150 (vectorpg-lb), user=`immich`
- NFS mount: `/mnt/homes/` accessible with all user dirs
- Immich API: via `kubectl port-forward` (in-cluster DNS doesn't resolve from dev host)
- All three Immich users confirmed: Mike, Serena, Chuni

### Timestamp format (V1 — validated against real data)
- `takentime` = epoch seconds → use for `fileCreatedAt`
- `createtime` = epoch milliseconds → discard (Synology index time, always Sept 2023)
- `mtime` = epoch seconds → use for `fileModifiedAt`
- Tested with 10 real records, all convert correctly to ISO 8601

### Upload throughput (V2 — measured with 10 real photos)
- Average: **0.15s/photo** (range 0.07–0.32s depending on file size)
- Serial estimate for 66,771 face-bearing units: **~2.8 hours**
- With 4x concurrency: **~0.7 hours**

### Scale confirmed
- Syno user 2 (chuni):    48,328 face-bearing units
- Syno user 5 (Lenaxia):    271 face-bearing units
- Syno user 9 (lola-poo): 5,903 face-bearing units
- Syno user 12 (mikek):   11,269 face-bearing units
- **Total: 66,771 units**

## TDD Cycles (all RED → GREEN)

| Cycle | Tests | Function | File |
|---|---|---|---|
| 1 | 9 | `convert_timestamps()` | migration_core.py |
| 2 | 9 | `build_file_path()` | migration_core.py |
| 3 | 4 | `upload_photo()` | migration_core.py |
| 4 | 3 | `ensure_photo_tracking_table()` + `syno_photo_migration` table | migration.py |
| 5 | 3 | `phase_photo_upload()` | migration.py |
| 6 | 2 | crash resume validation | migration.py |
| 7 | 8 | `phase_setup_api_keys()`, `load_api_keys()`, `cleanup_api_keys()` | migration.py |

**Test count: 148 → 169 passed, 0 failed, 27 skipped**

## Files Created
- `tests/unit/test_timestamp_conversion.py` (9 tests)
- `tests/unit/test_build_file_path.py` (9 tests)
- `tests/integration/test_upload_photo.py` (4 tests)
- `tests/integration/test_photo_tracking.py` (3 tests)
- `tests/integration/test_phase2_full.py` (3 tests)
- `tests/integration/test_crash_resume.py` (2 tests)
- `tests/integration/test_phase0_api_keys.py` (8 tests)

## Files Modified
- `migration_core.py` — added `convert_timestamps()`, `build_file_path()`, `upload_photo()`
- `migration.py` — Phase 0 + Phase 2 + CLI rewrite + Phase 4 tracking-table integration
- `SYNO_DSN.user` default: `postgres` → `app`

## Bug Fixes
- `SYNO_DB_USER` default was `postgres` (doesn't exist on CNPG), changed to `app`
- GRANT SELECT on Synology tables to `app` user (was missing, caused auth error)
- Old session 0009 API key plaintext secrets were lost; Phase 0 now regenerates them

## CLI Usage
```bash
# 1. Start port-forward
kubectl port-forward -n media svc/immich-server 22830:2283 &

# 2. Create per-user API keys
python3 migration.py --setup

# 3. Test with small batch
python3 migration.py --execute --limit 10

# 4. Full production run
python3 migration.py --execute

# 5. Photo upload only (skip face migration)
python3 migration.py --execute --upload-only

# 6. Cleanup
python3 migration.py --cleanup-keys
```

## NOT READY — Honest Assessment

The code is complete and tested, but there are **unvalidated risks** before a production run:

### HIGH risk — must test before full migration
1. **Multi-user upload not tested end-to-end** — All integration tests used Mike's API key
   for user 5 (Lenaxia→Mike). We have NOT tested uploading as Chuni or Serena. The
   `IMMICH_USER_NAMES` map says we create keys for all three, but we never verified that
   Chuni's key can upload a photo that lands in Chuni's library.

2. **No full-pipeline integration test** — We tested each phase in isolation but never
   ran: setup → upload 5 photos → face migration on those photos. Phase 4's
   `_build_unit_to_asset_from_tracking()` reads from `syno_photo_migration` and JOINs
   `asset`, but this join has never been tested with real uploaded data.

3. **Phase 4 face migration not re-tested with new asset source** — The existing
   `test_real_databases.py` integration tests still use the OLD `phase_asset_matching()`
   (filename matching). The new `_build_unit_to_asset_from_tracking()` path is only
   exercised by the CLI, which requires interactive `--execute` confirmation.

### MEDIUM risk — should validate
4. **HEIC/MOV files not tested** — Only JPG and TIF were uploaded during throughput test.
   Synology has HEIC files from iPhones. The Immich API should handle them, but untested.

5. **Port-forward is manual** — The script needs `kubectl port-forward` running. If it
   dies mid-migration, uploads will fail but the tracking table protects against data loss
   (resume is safe).

6. **No concurrency yet** — Serial at 0.15s/photo = ~2.8 hours. Acceptable but could be
   faster with `--concurrency` flag (planned but not implemented).

### LOW risk — cosmetic
7. **1 residual test row cleaned** from `syno_photo_migration` (syno_unit=55555, fake ID,
   would never collide with real data).

8. **`IMMICH_USER_NAMES` is hardcoded** — Should be derived from `MANUAL_USER_MAP` + DB
   query, but works for the 3 mapped users.

## Recommended Next Steps (Before Production Run)

1. **Write and run a full-pipeline integration test** — `--setup`, then `--execute --limit 5`,
   then verify: tracking rows created, assets visible in Immich UI, face migration succeeds.
2. **Test multi-user upload** — Upload 1 photo as Chuni, verify ownership in Immich.
3. **Test HEIC upload** — Upload 1 HEIC file, verify Immich accepts it.
4. **Dry run the full migration** — `python3 migration.py --dry-run` to see totals.
5. **Then and only then**: `python3 migration.py --execute`.
