#!/usr/bin/env python3
"""
match_faces.py — Synology Photos → Immich face name migration

For each named person in the Synology synofoto database, this script:
  1. Finds all photo filenames associated with that person via
     many_unit_has_many_person → unit (the curated named-person mapping)
  2. Looks up the corresponding Immich asset IDs by originalFileName,
     scoped to the correct Immich user
  3. Counts which Immich person_id appears most across face records
     for those assets (majority vote)
  4. If confidence >= threshold: assigns the name via the Immich REST API
  5. Otherwise: writes to unmatched.csv for manual review

Darcy (Synology id_user 3 and 7) is merged into one Immich account.
Duplicate person names across the two accounts are combined before voting.

Usage:
    python3 match_faces.py --config config.yaml [--dry-run] [--user chuni]
                           [--confidence 0.5] [--person "Name"]

Requirements:
    pip install -r requirements.txt
"""

import argparse
import csv
import logging
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import psycopg2
import psycopg2.extras
import requests
import yaml

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config(path: str) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)

    required = ["syno_db", "immich_db", "immich_url", "users"]
    for key in required:
        if key not in cfg:
            raise ValueError(f"config.yaml missing required key: {key}")

    for i, u in enumerate(cfg["users"]):
        for key in [
            "immich_username",
            "immich_api_key",
            "immich_user_id",
            "syno_user_ids",
        ]:
            if key not in u:
                raise ValueError(f"users[{i}] missing required key: {key}")

    return cfg


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def syno_connect(dsn: str):
    conn = psycopg2.connect(dsn)
    conn.set_session(readonly=True, autocommit=True)
    return conn


def immich_connect(dsn: str):
    conn = psycopg2.connect(dsn)
    conn.set_session(readonly=True, autocommit=True)
    return conn


def fetch_named_persons(syno_conn, syno_user_ids: list[int]) -> dict:
    """
    Returns a dict: {person_name: [filename, ...]}

    Source: many_unit_has_many_person (curated named-person→photo mapping)
    joining unit (for filename) and person (for name).

    For merged users (e.g. darcy local + LDAP), filenames from both
    id_user values are combined under the same person name.
    """
    placeholders = ",".join(["%s"] * len(syno_user_ids))
    sql = f"""
        SELECT
            p.name        AS person_name,
            u.filename    AS filename,
            m.id_user     AS syno_user_id
        FROM many_unit_has_many_person m
        JOIN unit   u ON u.id   = m.id_unit
        JOIN person p ON p.id   = m.id_person
        WHERE m.id_user IN ({placeholders})
          AND p.name IS NOT NULL
          AND p.name != ''
        ORDER BY p.name, u.filename
    """
    with syno_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql, syno_user_ids)
        rows = cur.fetchall()

    # Group filenames by person name (merging across syno_user_ids)
    persons: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        persons[row["person_name"]].append(row["filename"])

    # Deduplicate filenames within each person (in case same file appears
    # under both local and LDAP accounts for merged users like darcy)
    return {name: list(dict.fromkeys(fnames)) for name, fnames in persons.items()}


def fetch_immich_asset_ids(
    immich_conn, immich_user_id: str, filenames: list[str]
) -> dict[str, str]:
    """
    Returns {filename: asset_id} for all filenames that exist in Immich
    for the given user. Scoped by ownerId to avoid cross-user matches.
    """
    if not filenames:
        return {}

    sql = """
        SELECT "originalFileName", id
        FROM asset
        WHERE "ownerId" = %s
          AND "originalFileName" = ANY(%s)
          AND "deletedAt" IS NULL
    """
    with immich_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql, (immich_user_id, filenames))
        rows = cur.fetchall()

    return {row["originalFileName"]: str(row["id"]) for row in rows}


def fetch_dominant_person(
    immich_conn, asset_ids: list[str]
) -> tuple[str | None, int, int]:
    """
    Among the Immich face records for the given asset IDs, find the
    person_id that appears most frequently (majority vote).

    Returns (person_id, vote_count, total_faces_with_person).
    person_id is None if no faces with a person assignment were found.
    """
    if not asset_ids:
        return None, 0, 0

    sql = """
        SELECT "personId", COUNT(*) AS cnt
        FROM face
        WHERE "assetId" = ANY(%s)
          AND "personId" IS NOT NULL
        GROUP BY "personId"
        ORDER BY cnt DESC
        LIMIT 1
    """
    with immich_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql, (asset_ids,))
        row = cur.fetchone()

    if not row:
        return None, 0, 0

    # Also get the total count of faces-with-person for confidence calculation
    sql_total = """
        SELECT COUNT(*) AS total
        FROM face
        WHERE "assetId" = ANY(%s)
          AND "personId" IS NOT NULL
    """
    with immich_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql_total, (asset_ids,))
        total_row = cur.fetchone()

    total = int(total_row["total"]) if total_row else 0
    return str(row["personId"]), int(row["cnt"]), total


# ---------------------------------------------------------------------------
# Immich API helpers
# ---------------------------------------------------------------------------


def immich_get_person(immich_url: str, api_key: str, person_id: str) -> dict | None:
    """Fetch a person record from the Immich API."""
    resp = requests.get(
        f"{immich_url}/api/people/{person_id}",
        headers={"x-api-key": api_key},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def immich_set_person_name(
    immich_url: str, api_key: str, person_id: str, name: str, dry_run: bool
) -> bool:
    """Assign a name to an Immich person record via the REST API."""
    if dry_run:
        log.info("  [DRY-RUN] Would PATCH /api/people/%s name=%r", person_id, name)
        return True

    resp = requests.put(
        f"{immich_url}/api/people/{person_id}",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json={"name": name},
        timeout=10,
    )
    resp.raise_for_status()
    return True


# ---------------------------------------------------------------------------
# Core migration logic
# ---------------------------------------------------------------------------


def migrate_user(
    syno_conn,
    immich_conn,
    user_cfg: dict,
    immich_url: str,
    confidence_threshold: float,
    dry_run: bool,
    filter_person: str | None,
    matched_writer,
    unmatched_writer,
) -> tuple[int, int]:
    """
    Migrate face names for one logical Immich user.
    Returns (matched_count, unmatched_count).
    """
    username = user_cfg["immich_username"]
    immich_user_id = user_cfg["immich_user_id"]
    api_key = user_cfg["immich_api_key"]
    syno_user_ids = user_cfg["syno_user_ids"]

    log.info("=== Processing user: %s (syno_ids=%s) ===", username, syno_user_ids)

    # Step 1: Get named persons from Synology
    persons = fetch_named_persons(syno_conn, syno_user_ids)
    if not persons:
        log.info("  No named persons found in Synology for this user — skipping.")
        return 0, 0

    log.info("  Found %d named persons in Synology.", len(persons))

    if filter_person:
        if filter_person not in persons:
            log.warning("  Person %r not found for user %s", filter_person, username)
            return 0, 0
        persons = {filter_person: persons[filter_person]}
        log.info("  Filtered to person: %r", filter_person)

    matched = 0
    unmatched = 0

    for person_name, filenames in sorted(persons.items()):
        log.info("  Person: %r  (%d photos in Synology)", person_name, len(filenames))

        # Step 2: Find Immich asset IDs by filename
        filename_to_asset = fetch_immich_asset_ids(
            immich_conn, immich_user_id, filenames
        )
        asset_ids = list(filename_to_asset.values())

        if not asset_ids:
            reason = "no_assets_in_immich"
            log.warning(
                "    -> UNMATCHED (%s): none of %d filenames found in Immich",
                reason,
                len(filenames),
            )
            unmatched_writer.writerow(
                {
                    "username": username,
                    "person_name": person_name,
                    "syno_photo_count": len(filenames),
                    "immich_assets_found": 0,
                    "immich_person_id": "",
                    "confidence": 0,
                    "reason": reason,
                }
            )
            unmatched += 1
            continue

        log.info(
            "    Matched %d/%d filenames to Immich assets.",
            len(asset_ids),
            len(filenames),
        )

        # Step 3: Vote on Immich person_id across those assets
        person_id, vote_count, total_faces = fetch_dominant_person(
            immich_conn, asset_ids
        )

        if not person_id:
            reason = "no_faces_detected_in_immich"
            log.warning(
                "    -> UNMATCHED (%s): Immich has no face records for these assets",
                reason,
            )
            unmatched_writer.writerow(
                {
                    "username": username,
                    "person_name": person_name,
                    "syno_photo_count": len(filenames),
                    "immich_assets_found": len(asset_ids),
                    "immich_person_id": "",
                    "confidence": 0,
                    "reason": reason,
                }
            )
            unmatched += 1
            continue

        confidence = vote_count / total_faces if total_faces > 0 else 0
        log.info(
            "    Top Immich person: %s  votes=%d/%d  confidence=%.1f%%",
            person_id,
            vote_count,
            total_faces,
            confidence * 100,
        )

        if confidence < confidence_threshold:
            reason = f"low_confidence_{confidence:.2f}"
            log.warning(
                "    -> UNMATCHED (%s): below threshold %.0f%%",
                reason,
                confidence_threshold * 100,
            )
            unmatched_writer.writerow(
                {
                    "username": username,
                    "person_name": person_name,
                    "syno_photo_count": len(filenames),
                    "immich_assets_found": len(asset_ids),
                    "immich_person_id": person_id,
                    "confidence": f"{confidence:.2f}",
                    "reason": reason,
                }
            )
            unmatched += 1
            continue

        # Step 4: Check if Immich person already has a name
        existing = immich_get_person(immich_url, api_key, person_id)
        if existing and existing.get("name") and existing["name"] != "":
            log.info(
                "    Immich person already named %r — skipping to avoid overwrite.",
                existing["name"],
            )
            matched_writer.writerow(
                {
                    "username": username,
                    "person_name": person_name,
                    "immich_person_id": person_id,
                    "confidence": f"{confidence:.2f}",
                    "vote_count": vote_count,
                    "total_faces": total_faces,
                    "action": "skipped_already_named",
                    "existing_name": existing["name"],
                }
            )
            matched += 1
            continue

        # Step 5: Assign the name
        try:
            immich_set_person_name(immich_url, api_key, person_id, person_name, dry_run)
            action = "dry_run" if dry_run else "named"
            log.info(
                "    -> MATCHED: assigned name %r to person %s", person_name, person_id
            )
        except requests.HTTPError as e:
            log.error("    -> API ERROR for person %s: %s", person_id, e)
            action = f"api_error:{e}"

        matched_writer.writerow(
            {
                "username": username,
                "person_name": person_name,
                "immich_person_id": person_id,
                "confidence": f"{confidence:.2f}",
                "vote_count": vote_count,
                "total_faces": total_faces,
                "action": action,
                "existing_name": "",
            }
        )
        matched += 1

    return matched, unmatched


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Migrate Synology Photos face names into Immich"
    )
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print actions without making API calls"
    )
    parser.add_argument(
        "--user", default=None, help="Process only this Immich username"
    )
    parser.add_argument(
        "--person",
        default=None,
        help="Process only this person name (within the filtered user)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.5,
        help="Minimum confidence threshold 0.0-1.0 (default: 0.5)",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.dry_run:
        log.info("*** DRY-RUN MODE — no changes will be made ***")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    matched_path = Path(f"matched-{ts}.csv")
    unmatched_path = Path(f"unmatched-{ts}.csv")

    matched_fields = [
        "username",
        "person_name",
        "immich_person_id",
        "confidence",
        "vote_count",
        "total_faces",
        "action",
        "existing_name",
    ]
    unmatched_fields = [
        "username",
        "person_name",
        "syno_photo_count",
        "immich_assets_found",
        "immich_person_id",
        "confidence",
        "reason",
    ]

    log.info("Output files: %s  %s", matched_path, unmatched_path)

    syno_conn = syno_connect(cfg["syno_db"])
    immich_conn = immich_connect(cfg["immich_db"])

    total_matched = 0
    total_unmatched = 0

    with (
        open(matched_path, "w", newline="") as mf,
        open(unmatched_path, "w", newline="") as uf,
    ):
        matched_writer = csv.DictWriter(mf, fieldnames=matched_fields)
        unmatched_writer = csv.DictWriter(uf, fieldnames=unmatched_fields)
        matched_writer.writeheader()
        unmatched_writer.writeheader()

        for user_cfg in cfg["users"]:
            if args.user and user_cfg["immich_username"] != args.user:
                continue

            m, u = migrate_user(
                syno_conn=syno_conn,
                immich_conn=immich_conn,
                user_cfg=user_cfg,
                immich_url=cfg["immich_url"].rstrip("/"),
                confidence_threshold=args.confidence,
                dry_run=args.dry_run,
                filter_person=args.person,
                matched_writer=matched_writer,
                unmatched_writer=unmatched_writer,
            )
            total_matched += m
            total_unmatched += u

    syno_conn.close()
    immich_conn.close()

    log.info("")
    log.info("=== Summary ===")
    log.info("  Matched (named or skipped):  %d", total_matched)
    log.info("  Unmatched (needs manual):    %d", total_unmatched)
    log.info("  matched.csv   → %s", matched_path)
    log.info("  unmatched.csv → %s", unmatched_path)

    if total_unmatched > 0:
        log.info("")
        log.info(
            "Review %s and assign remaining names manually in Immich UI.",
            unmatched_path,
        )

    if args.dry_run:
        log.info("")
        log.info("Dry-run complete. Re-run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
