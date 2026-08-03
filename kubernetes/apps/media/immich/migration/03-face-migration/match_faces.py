#!/usr/bin/env python3
"""
match_faces.py — Match Synology named persons to Immich people via IoU

For each Synology named person:
1. Get all units assigned to this person
2. For each unit bridged to an immich asset, get immich's detected faces
3. Match via bounding-box IoU (syno normalized → immich pixel space)
4. Majority vote → determine the winning immich personId
5. Auto-assign name if confident, otherwise flag for review

Idempotent: ON CONFLICT DO NOTHING on syno_face_id PK.
Re-runnable: skips already-matched faces.

Env vars:
  SYNO_DB_HOST, SYNO_DB_NAME, IMMICH_DB_HOST, IMMICH_DB_NAME
  PGUSER, PGPASSWORD
  IMMICH_URL          (http://immich-server.media.svc.cluster.local:2283)
  DRY_RUN             (default: false)
  IOU_THRESHOLD       (default: 0.3)
  MIN_VOTES           (default: 5)
  MARGIN_RATIO        (default: 2.0 — top must have >= ratio × runner-up)
  TARGET_PERSON       (optional: only process this syno person name)
"""

import json
import logging
import os
import sys
import time
from collections import Counter, defaultdict

import psycopg2
import psycopg2.extras
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("face-match")


SYNO_TO_IMMICH = {
    2: "4bc1e174-e8e7-4f93-9a9f-20422a2383c8",
    3: "dfe560ec-b20a-46b1-8e72-bd745441b353",
    5: "3de3d105-f5f0-4156-bbca-91857f21dcc8",
    7: "dfe560ec-b20a-46b1-8e72-bd745441b353",
    9: "8609dd3f-e548-4d56-b474-b1431193dc35",
    12: "3de3d105-f5f0-4156-bbca-91857f21dcc8",
}


def connect(host, dbname, user, password):
    dsn = f"host={host} dbname={dbname} user={user} password={password}"
    conn = psycopg2.connect(dsn)
    conn.set_session(autocommit=True)
    return conn


def parse_syno_bbox(bbox_json):
    if isinstance(bbox_json, str):
        bbox_json = json.loads(bbox_json)
    tl = bbox_json.get("top_left", {})
    br = bbox_json.get("bottom_right", {})
    return tl.get("x", 0), tl.get("y", 0), br.get("x", 0), br.get("y", 0)


def compute_iou(syno_bbox, imm_face):
    sx1n, sy1n, sx2n, sy2n = parse_syno_bbox(syno_bbox)
    w = imm_face["imageWidth"]
    h = imm_face["imageHeight"]
    if w <= 0 or h <= 0:
        return 0.0
    sx1, sy1, sx2, sy2 = sx1n * w, sy1n * h, sx2n * w, sy2n * h
    ix1, iy1 = imm_face["boundingBoxX1"], imm_face["boundingBoxY1"]
    ix2, iy2 = imm_face["boundingBoxX2"], imm_face["boundingBoxY2"]
    xi1, yi1 = max(sx1, ix1), max(sy1, iy1)
    xi2, yi2 = min(sx2, ix2), min(sy2, iy2)
    inter = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    area_s = (sx2 - sx1) * (sy2 - sy1)
    area_i = (ix2 - ix1) * (iy2 - iy1)
    union = area_s + area_i - inter
    return inter / union if union > 0 else 0.0


def get_named_persons(syno_conn, target_name=None):
    with syno_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if target_name:
            cur.execute(
                """
                SELECT p.id AS person_id, p.name, p.id_user, m.id_unit
                FROM person p
                JOIN many_unit_has_many_person m ON m.id_person = p.id
                WHERE p.name IS NOT NULL AND p.name <> ''
                  AND p.id_user = ANY(%s) AND p.name = %s
                ORDER BY p.id
            """,
                (list(SYNO_TO_IMMICH.keys()), target_name),
            )
        else:
            cur.execute(
                """
                SELECT p.id AS person_id, p.name, p.id_user, m.id_unit
                FROM person p
                JOIN many_unit_has_many_person m ON m.id_person = p.id
                WHERE p.name IS NOT NULL AND p.name <> ''
                  AND p.id_user = ANY(%s)
                ORDER BY p.id
            """,
                (list(SYNO_TO_IMMICH.keys()),),
            )
        person_units = defaultdict(
            lambda: {"name": "", "id_user": None, "units": set()}
        )
        for row in cur.fetchall():
            pid = row["person_id"]
            person_units[pid]["name"] = row["name"]
            person_units[pid]["id_user"] = row["id_user"]
            person_units[pid]["units"].add(row["id_unit"])
        return person_units


def get_syno_faces_for_units(syno_conn, unit_ids, person_id):
    if not unit_ids:
        return {}
    with syno_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id AS face_id, id_unit, bounding_box
            FROM face WHERE id_person = %s AND id_unit = ANY(%s)
        """,
            (person_id, list(unit_ids)),
        )
        return {row["face_id"]: row for row in cur.fetchall()}


def get_immich_faces_for_assets(immich_conn, asset_ids):
    if not asset_ids:
        return defaultdict(list)
    with immich_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, "assetId", "personId",
                   "boundingBoxX1", "boundingBoxY1",
                   "boundingBoxX2", "boundingBoxY2",
                   "imageWidth", "imageHeight"
            FROM asset_face
            WHERE "assetId" = ANY(%s) AND "deletedAt" IS NULL
        """,
            (list(asset_ids),),
        )
        faces_by_asset = defaultdict(list)
        for row in cur.fetchall():
            faces_by_asset[row["assetId"]].append(row)
        return faces_by_asset


def get_bridged_assets(immich_conn, unit_ids):
    if not unit_ids:
        return {}
    with immich_conn.cursor() as cur:
        cur.execute(
            """
            SELECT syno_unit_id, immich_asset_id
            FROM syno_photo_migration WHERE syno_unit_id = ANY(%s)
        """,
            (list(unit_ids),),
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def get_already_matched(immich_conn):
    with immich_conn.cursor() as cur:
        cur.execute("SELECT syno_face_id FROM syno_face_migration")
        return {row[0] for row in cur.fetchall()}


def insert_face_match(immich_conn, rows):
    if not rows:
        return 0
    with immich_conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO syno_face_migration
                (syno_face_id, immich_face_id, immich_asset_id,
                 immich_person_id, iou_score, syno_person_id)
            VALUES %s
            ON CONFLICT (syno_face_id) DO NOTHING
            """,
            rows,
            page_size=500,
        )
        return cur.rowcount


def assign_person_name(api_key, immich_url, person_id, name):
    try:
        resp = requests.get(
            f"{immich_url}/api/people/{person_id}",
            headers={"x-api-key": api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            return False, None
        old_name = resp.json().get("name", "")
        if old_name and old_name != name:
            return False, old_name
        resp = requests.put(
            f"{immich_url}/api/people/{person_id}",
            headers={"x-api-key": api_key},
            json={"name": name},
            timeout=10,
        )
        return resp.status_code == 200, old_name
    except requests.exceptions.RequestException as e:
        log.error("  API error: %s", str(e)[:200])
        return False, None


def main():
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
    iou_threshold = float(os.environ.get("IOU_THRESHOLD", "0.3"))
    min_votes = int(os.environ.get("MIN_VOTES", "5"))
    margin_ratio = float(os.environ.get("MARGIN_RATIO", "2.0"))
    target_person = os.environ.get("TARGET_PERSON")
    user = os.environ["PGUSER"]
    password = os.environ["PGPASSWORD"]
    immich_url = os.environ["IMMICH_URL"].rstrip("/")
    api_key = os.environ.get("ADMIN_API_KEY", "")

    if dry_run:
        log.info("*** DRY-RUN MODE — no DB writes, no name assignments ***")

    syno_conn = connect(
        os.environ["SYNO_DB_HOST"], os.environ["SYNO_DB_NAME"], user, password
    )
    immich_conn = connect(
        os.environ["IMMICH_DB_HOST"], os.environ["IMMICH_DB_NAME"], user, password
    )

    persons = get_named_persons(syno_conn, target_person)
    log.info("Loaded %d named Synology persons", len(persons))

    already_matched = get_already_matched(immich_conn)
    log.info("  %d faces already matched (will skip)", len(already_matched))

    stats = {
        "persons_total": len(persons),
        "auto_assigned": 0,
        "flagged": 0,
        "no_bridge": 0,
        "no_faces": 0,
        "faces_matched": 0,
        "faces_no_match": 0,
        "names_assigned": 0,
    }
    review_rows = []
    start = time.time()

    for pi, (person_id, info) in enumerate(sorted(persons.items())):
        name = info["name"]
        units = info["units"]
        if (pi + 1) % 10 == 0:
            log.info(
                "  Progress: %d/%d — auto=%d flagged=%d no_bridge=%d matched=%d",
                pi + 1,
                len(persons),
                stats["auto_assigned"],
                stats["flagged"],
                stats["no_bridge"],
                stats["faces_matched"],
            )

        bridged = get_bridged_assets(immich_conn, units)
        if not bridged:
            stats["no_bridge"] += 1
            continue

        syno_faces = get_syno_faces_for_units(
            syno_conn, list(bridged.keys()), person_id
        )
        if not syno_faces:
            stats["no_bridge"] += 1
            continue

        asset_ids = list(set(bridged.values()))
        immich_faces = get_immich_faces_for_assets(immich_conn, asset_ids)

        match_rows = []
        votes = Counter()

        for face_id, sface in syno_faces.items():
            if face_id in already_matched:
                continue
            unit_id = sface["id_unit"]
            asset_id = bridged.get(unit_id)
            if not asset_id:
                continue
            imm_faces = immich_faces.get(asset_id, [])
            if not imm_faces:
                continue
            best_iou = 0.0
            best_face = None
            for iface in imm_faces:
                iou = compute_iou(sface["bounding_box"], iface)
                if iou > best_iou:
                    best_iou = iou
                    best_face = iface
            if best_face and best_iou >= iou_threshold:
                match_rows.append(
                    (
                        face_id,
                        best_face["id"],
                        asset_id,
                        best_face["personId"],
                        best_iou,
                        person_id,
                    )
                )
                stats["faces_matched"] += 1
                if best_face["personId"]:
                    votes[best_face["personId"]] += 1
            else:
                stats["faces_no_match"] += 1

        if match_rows and not dry_run:
            insert_face_match(immich_conn, match_rows)

        if not votes:
            if match_rows:
                stats["flagged"] += 1
                review_rows.append(
                    {
                        "syno_person": name,
                        "reason": "matched but no personId in immich",
                        "matched": len(match_rows),
                    }
                )
            else:
                stats["no_faces"] += 1
            continue

        sorted_votes = votes.most_common()
        top_person, top_count = sorted_votes[0]
        runner_count = sorted_votes[1][1] if len(sorted_votes) > 1 else 0
        auto = top_count >= min_votes and top_count >= margin_ratio * runner_count

        if auto:
            stats["auto_assigned"] += 1
            log.info(
                "  AUTO-ASSIGN: '%s' → %s (votes=%d runner=%d faces=%d)",
                name,
                top_person,
                top_count,
                runner_count,
                len(match_rows),
            )
            if not dry_run and api_key:
                ok, old = assign_person_name(api_key, immich_url, top_person, name)
                if ok:
                    stats["names_assigned"] += 1
                elif old:
                    log.warning("    Person %s already named '%s'", top_person, old)
        else:
            stats["flagged"] += 1
            reason = (
                f"insufficient votes ({top_count}<{min_votes})"
                if top_count < min_votes
                else f"low margin ({top_count}<{margin_ratio:.1f}×{runner_count})"
            )
            review_rows.append(
                {
                    "syno_person": name,
                    "best_person": str(top_person),
                    "top_votes": top_count,
                    "runner_votes": runner_count,
                    "reason": reason,
                    "matched": len(match_rows),
                }
            )

    elapsed = time.time() - start
    log.info("")
    log.info("=" * 60)
    log.info("=== Face Match Summary ===")
    log.info("  Persons processed:        %d", stats["persons_total"])
    log.info("  Auto-assigned:            %d", stats["auto_assigned"])
    log.info("  Names assigned via API:   %d", stats["names_assigned"])
    log.info("  Flagged for review:       %d", stats["flagged"])
    log.info("  No bridge (not uploaded): %d", stats["no_bridge"])
    log.info("  No faces detected:        %d", stats["no_faces"])
    log.info("  Faces matched (IoU>=%.1f):%d", iou_threshold, stats["faces_matched"])
    log.info("  Faces no match:           %d", stats["faces_no_match"])
    log.info("  Elapsed:                  %.1f min", elapsed / 60)
    log.info("=" * 60)
    if review_rows:
        log.info("")
        log.info("=== Flagged for Review ===")
        for r in review_rows:
            log.info("  %s — %s", r["syno_person"], r["reason"])

    syno_conn.close()
    immich_conn.close()


if __name__ == "__main__":
    main()
