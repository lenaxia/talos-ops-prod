#!/usr/bin/env python3
"""
upload.py — Upload Synology photos to Immich via REST API

For each user with accounts on both sides:
1. Query synofotopg for all units (file path + metadata)
2. Hash each NFS file (SHA-1) to dedup locally
3. Skip files already in Immich (checksum index)
4. Upload remaining via POST /api/assets

Runs inside the syno-immich-upload Job pod. Idempotent: re-runs skip
already-uploaded files. See DESIGN.md §2.

Env vars (set by Job manifest):
  SYNO_DB_HOST, SYNO_DB_NAME, IMMICH_DB_HOST, IMMICH_DB_NAME
  PGUSER, PGPASSWORD
  IMMICH_URL          (http://immich-server.media.svc.cluster.local:2283)
  UPLOAD_USERS        (comma-separated: chuni,mike,serena,darcy,all)
  CONCURRENCY         (default: 4 parallel uploads)
  DRY_RUN             (default: false)
"""

import hashlib
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("upload")


# ---------------------------------------------------------------------------
# User mapping: syno_user_id → (immich_user_id, nfs_mount, home_dir, api_key_env)
# ---------------------------------------------------------------------------

SYNO_TO_IMMICH = {
    2: {
        "name": "chuni",
        "immich_id": "4bc1e174-e8e7-4f93-9a9f-20422a2383c8",
        "mount": "syno-local",
        "home": "chuni",
        "api_key_env": "CHUNI_API_KEY",
    },
    3: {
        "name": "darcy",
        "immich_id": "dfe560ec-b20a-46b1-8e72-bd745441b353",
        "mount": "syno-local",
        "home": "darcy",
        "api_key_env": "DARCY_API_KEY",
    },
    5: {
        "name": "mike-local",
        "immich_id": "3de3d105-f5f0-4156-bbca-91857f21dcc8",
        "mount": "syno-local",
        "home": "Lenaxia",
        "api_key_env": "MIKE_API_KEY",
    },
    7: {
        "name": "darcy-ldap",
        "immich_id": "dfe560ec-b20a-46b1-8e72-bd745441b353",
        "mount": "syno-ldap",
        "home": "darcy-1000005",
        "api_key_env": "DARCY_API_KEY",
    },
    9: {
        "name": "serena",
        "immich_id": "8609dd3f-e548-4d56-b474-b1431193dc35",
        "mount": "syno-ldap",
        "home": "lola-poo-1000017",
        "api_key_env": "SERENA_API_KEY",
    },
    12: {
        "name": "mike-ldap",
        "immich_id": "3de3d105-f5f0-4156-bbca-91857f21dcc8",
        "mount": "syno-ldap",
        "home": "mike-1000032",
        "api_key_env": "MIKE_API_KEY",
    },
}

NFS_ROOTS = {
    "syno-local": "/import/syno-local",
    "syno-ldap": "/import/syno-ldap",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def connect(host, dbname, user, password):
    dsn = f"host={host} dbname={dbname} user={user} password={password}"
    conn = psycopg2.connect(dsn)
    conn.set_session(autocommit=True)
    return conn


def nfs_path(id_user, folder_name, filename):
    info = SYNO_TO_IMMICH.get(id_user)
    if not info:
        return None
    root = NFS_ROOTS[info["mount"]]
    return f"{root}/{info['home']}/Photos{folder_name}/{filename}"


def compute_sha1(path):
    h = hashlib.sha1()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.digest()
    except (FileNotFoundError, PermissionError, IsADirectoryError, OSError) as e:
        log.debug("  skip %s: %s", path, e)
        return None


def epoch_to_iso(epoch):
    if not epoch or epoch <= 0:
        return datetime(2000, 1, 1, tzinfo=timezone.utc).isoformat()
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def get_syno_units(conn, syno_user_ids):
    """Get all units for the given syno users with NFS path info."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT u.id AS unit_id, u.id_user, u.filename, u.filesize,
                   u.createtime, u.mtime, u.takentime, f.name AS folder_name
            FROM unit u
            JOIN folder f ON f.id = u.id_folder
            WHERE u.id_user = ANY(%s)
            ORDER BY u.id_user, u.id
        """,
            (list(syno_user_ids),),
        )
        return cur.fetchall()


def load_immich_checksums(conn, owner_id):
    """Return set of SHA-1 bytes already in immich for this owner."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT checksum FROM asset
            WHERE "ownerId" = %s AND "deletedAt" IS NULL AND checksum IS NOT NULL
        """,
            (owner_id,),
        )
        return {bytes(row[0]) for row in cur.fetchall()}


def upload_file(
    api_key, immich_url, unit_id, path, filesize, takentime, mtime, id_user
):
    """Upload a single file via Immich REST API. Returns (status, detail)."""
    info = SYNO_TO_IMMICH[id_user]
    filename = os.path.basename(path)
    file_ext = os.path.splitext(filename)[1]

    try:
        with open(path, "rb") as f:
            files = {"assetData": (filename, f)}
            data = {
                "deviceAssetId": f"syno-{unit_id}",
                "deviceId": "synology-migration",
                "fileCreatedAt": epoch_to_iso(takentime),
                "fileModifiedAt": epoch_to_iso(mtime),
                "isFavorite": "false",
                "fileExtension": file_ext,
                "duration": "0",
            }
            resp = requests.post(
                f"{immich_url}/api/assets",
                headers={"x-api-key": api_key},
                files=files,
                data=data,
                timeout=300,
            )
    except requests.exceptions.RequestException as e:
        return ("error", str(e)[:200])

    if resp.status_code in (200, 201):
        body = resp.json()
        status = body.get("status", "unknown")
        return (status, body.get("id", ""))
    else:
        return (
            f"http_{resp.status_code}",
            resp.text[:200],
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
    concurrency = int(os.environ.get("CONCURRENCY", "4"))
    upload_users = os.environ.get("UPLOAD_USERS", "all").lower().split(",")
    user = os.environ["PGUSER"]
    password = os.environ["PGPASSWORD"]
    immich_url = os.environ["IMMICH_URL"].rstrip("/")

    if dry_run:
        log.info("*** DRY-RUN MODE — no uploads ***")

    # Determine which syno users to process
    if "all" in upload_users:
        target_syno_ids = sorted(SYNO_TO_IMMICH.keys())
    else:
        name_to_syno = {v["name"]: k for k, v in SYNO_TO_IMMICH.items()}
        target_syno_ids = []
        for u in upload_users:
            u = u.strip()
            if u in name_to_syno:
                target_syno_ids.append(name_to_syno[u])
            else:
                log.warning("Unknown user '%s', skipping", u)

    if not target_syno_ids:
        log.error("No users to process")
        sys.exit(1)

    log.info("Processing syno users: %s", target_syno_ids)

    # Connect to DBs
    syno_conn = connect(
        os.environ["SYNO_DB_HOST"], os.environ["SYNO_DB_NAME"], user, password
    )
    immich_conn = connect(
        os.environ["IMMICH_DB_HOST"], os.environ["IMMICH_DB_NAME"], user, password
    )

    # Group target syno users by immich owner (for checksum dedup)
    owner_to_synos = {}
    for sid in target_syno_ids:
        owner_id = SYNO_TO_IMMICH[sid]["immich_id"]
        owner_to_synos.setdefault(owner_id, []).append(sid)

    # Get API keys
    api_keys = {}
    for sid in target_syno_ids:
        info = SYNO_TO_IMMICH[sid]
        key_env = info["api_key_env"]
        key = os.environ.get(key_env)
        if not key:
            log.error("Missing API key env: %s for user %s", key_env, info["name"])
            sys.exit(1)
        api_keys[info["immich_id"]] = key

    grand_stats = {
        "uploaded": 0,
        "skipped_existing": 0,
        "skipped_dedup": 0,
        "file_error": 0,
        "upload_error": 0,
        "total_units": 0,
    }

    for owner_id, syno_ids in owner_to_synos.items():
        owner_name = SYNO_TO_IMMICH[syno_ids[0]]["name"]
        api_key = api_keys[owner_id]

        log.info("")
        log.info("=" * 60)
        log.info("Processing immich owner: %s (syno users: %s)", owner_name, syno_ids)
        log.info("=" * 60)

        # Load existing immich checksums for this owner
        existing = load_immich_checksums(immich_conn, owner_id)
        log.info("  %d existing assets in immich for this owner", len(existing))

        # Get all syno units
        units = get_syno_units(syno_conn, syno_ids)
        log.info("  %d syno units to process", len(units))
        grand_stats["total_units"] += len(units)

        # Phase 1: hash all files, dedup locally, skip existing
        log.info("  Phase 1: hashing + dedup...")
        to_upload = []
        seen_hashes = set()
        hash_errors = 0
        start = time.time()

        for i, u in enumerate(units):
            if (i + 1) % 2000 == 0:
                elapsed = time.time() - start
                rate = (i + 1) / elapsed
                log.info(
                    "    hashed %d/%d (%.0f%%) — to_upload=%d dup=%d exist=%d err=%d | rate=%.0f/s",
                    i + 1,
                    len(units),
                    100 * (i + 1) / len(units),
                    len(to_upload),
                    grand_stats["skipped_dedup"] - 0,
                    grand_stats["skipped_existing"],
                    hash_errors,
                    rate,
                )

            path = nfs_path(u["id_user"], u["folder_name"], u["filename"])
            if path is None:
                continue

            sha1 = compute_sha1(path)
            if sha1 is None:
                hash_errors += 1
                continue

            # Dedup locally (multiple units may be the same file)
            if sha1 in seen_hashes:
                grand_stats["skipped_dedup"] += 1
                continue
            seen_hashes.add(sha1)

            # Skip if already in immich
            if sha1 in existing:
                grand_stats["skipped_existing"] += 1
                continue

            to_upload.append(u)

        log.info(
            "  Phase 1 done: %d to upload, %d local dupes skipped, %d already in immich, %d hash errors",
            len(to_upload),
            grand_stats["skipped_dedup"],
            grand_stats["skipped_existing"],
            hash_errors,
        )

        if dry_run or not to_upload:
            if not to_upload:
                log.info("  Nothing to upload for %s", owner_name)
            continue

        # Phase 2: upload new files
        log.info(
            "  Phase 2: uploading %d files (concurrency=%d)...",
            len(to_upload),
            concurrency,
        )
        upload_start = time.time()

        import threading

        stats_lock = threading.Lock()

        def do_upload(u):
            """Upload one file, return (status, detail). Robust wrapper."""
            try:
                path = nfs_path(u["id_user"], u["folder_name"], u["filename"])
                if path is None:
                    return ("skip", "no_path")
                return upload_file(
                    api_key,
                    immich_url,
                    u["unit_id"],
                    path,
                    u["filesize"],
                    u["takentime"],
                    u["mtime"],
                    u["id_user"],
                )
            except Exception as e:
                return ("exception", f"{type(e).__name__}: {str(e)[:150]}")

        done_count = 0
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(do_upload, u): u for u in to_upload}
            for future in as_completed(futures):
                u = futures[future]
                try:
                    status, detail = future.result()
                except Exception as e:
                    status, detail = (
                        "exception",
                        f"future: {type(e).__name__}: {str(e)[:150]}",
                    )

                with stats_lock:
                    done_count += 1
                    if status in ("created", "replaced"):
                        grand_stats["uploaded"] += 1
                    elif status in ("duplicate", "skip"):
                        grand_stats["skipped_existing"] += 1
                    else:
                        grand_stats["upload_error"] += 1
                        if grand_stats["upload_error"] <= 20:
                            log.warning(
                                "    UPLOAD ERROR unit=%d status=%s detail=%s",
                                u["unit_id"],
                                status,
                                detail,
                            )

                    if done_count % 200 == 0:
                        elapsed = time.time() - upload_start
                        rate = done_count / elapsed if elapsed > 0 else 0
                        remaining = (
                            (len(to_upload) - done_count) / rate if rate > 0 else 0
                        )
                        log.info(
                            "    uploaded %d/%d (%.1f%%) | ok=%d err=%d | rate=%.1f/s ETA=%.0fmin",
                            done_count,
                            len(to_upload),
                            100 * done_count / len(to_upload),
                            grand_stats["uploaded"],
                            grand_stats["upload_error"],
                            rate,
                            remaining / 60,
                        )

        elapsed = time.time() - upload_start
        log.info(
            "  Phase 2 done for %s: %d uploaded in %.1f min",
            owner_name,
            grand_stats["uploaded"],
            elapsed / 60,
        )

    # Summary
    log.info("")
    log.info("=" * 60)
    log.info("=== Upload Summary ===")
    log.info("  Total units processed:  %d", grand_stats["total_units"])
    log.info("  Uploaded (new):         %d", grand_stats["uploaded"])
    log.info("  Skipped (in immich):    %d", grand_stats["skipped_existing"])
    log.info("  Skipped (local dedup):  %d", grand_stats["skipped_dedup"])
    log.info("  File read errors:       %d", grand_stats["file_error"])
    log.info("  Upload errors:          %d", grand_stats["upload_error"])
    log.info("=" * 60)

    syno_conn.close()
    immich_conn.close()


if __name__ == "__main__":
    main()
