# Synology synofoto Schema Notes

Reference for the key tables used by `match_faces.py`.
Collected from a live Synology DSM 7 / Postgres 11 instance.

---

## Key tables

### `unit`
The primary photo/video record. One row per file.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | PK |
| `id_user` | integer | FK → `user_info.id` |
| `filename` | text | Original filename (e.g. `IMG_4146.CR2`) — matches Immich `originalFileName` |
| `id_folder` | integer | FK → `folder.id` |
| `duplicate_hash` | text | MD5 of file content (NOT SHA-1 — cannot use to match Immich checksums) |
| `takentime` | bigint | Unix timestamp ms |
| `filesize` | bigint | |

### `person`
One row per detected face cluster (named or unnamed).

| Column | Type | Notes |
|---|---|---|
| `id` | integer | PK |
| `id_user` | integer | FK → `user_info.id` — person belongs to this user |
| `name` | text | Human-assigned name, or empty string if unnamed |
| `hidden` | boolean | Whether hidden from UI |
| `normalized_name` | text | Lowercased version of name |

### `face`
Raw ML face detections. One row per detected face in a photo.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | PK |
| `id_user` | integer | |
| `id_unit` | integer | FK → `unit.id` — which photo this face is in |
| `id_person` | integer | FK → `person.id` — which cluster this face belongs to (may be unnamed) |
| `bounding_box` | json | `{top_left: {x,y}, bottom_right: {x,y}}` |
| `landmark` | json | Eye/nose/mouth positions |
| `feature` | bytea | 512-dim embedding vector (proprietary format — not compatible with Immich) |
| `score` | integer | Detection confidence score |
| `id_person_group` | integer | |

**Row counts (observed):**
- Total face rows: ~900K+
- Rows with `id_person IS NOT NULL`: 245,150
- Distinct `id_unit` with a named person: ~110K

### `many_unit_has_many_person`
Curated mapping of photos to named people. This is the **authoritative source**
for "photo X contains named person Y" — it represents the user-reviewed/confirmed
associations, not just raw ML detections.

| Column | Type | Notes |
|---|---|---|
| `id_unit` | integer | FK → `unit.id` |
| `id_person` | integer | FK → `person.id` |
| `id_user` | integer | |

**Row counts (observed):**
- Total rows: 88,252
- Distinct `id_unit`: 49,819

**Why `many_unit_has_many_person` and not `face` directly?**

The `face` table includes ALL detected face clusters including unnamed strangers
(people in the background of public photos, etc.). The `many_unit_has_many_person`
table only contains the subset the user explicitly confirmed/named. Using `face`
directly would flood the match with unnamed people.

The join used by `match_faces.py`:
```sql
SELECT p.name, u.filename
FROM many_unit_has_many_person m
JOIN unit   u ON u.id = m.id_unit
JOIN person p ON p.id = m.id_person
WHERE m.id_user IN (...)
  AND p.name IS NOT NULL
  AND p.name != ''
```

### `user_info`
Synology user registry.

| `id` | `uid` | `name` | Notes |
|---|---|---|---|
| 1 | 1037 | adonia | local account |
| 2 | 1032 | chuni | local account |
| 3 | 1034 | darcy | local account |
| 5 | 1026 | Lenaxia | local account (merges into mikek Immich account) |
| 6 | 1033 | steviek | local account |
| 7 | 1000005 | darcy@kao.family | LDAP account (merges with id=3) |
| 8 | 1000006 | steviek@kao.family | LDAP account (merges with id=6, 0 named people) |
| 9 | 1000017 | lola-poo@kao.family | LDAP account |
| 10 | 1000020 | ZeroOdds@kao.family | LDAP account — no photos, skip |
| 11 | 1000003 | adonia@kao.family | LDAP account — no Photos dir |
| 12 | 1000032 | mikek@kao.family | LDAP account |
| 13 | 1000004 | chuni@kao.family | LDAP account — no Photos dir |
| 14 | 1000018 | tjkao@kao.family | LDAP account |
| 15 | 1000035 | ming@kao.family | LDAP account — not migrating |
| 16 | 1000034 | pandaria@kao.family | LDAP account |
| 17 | 1024 | admin | system account — skip |
| 4 | 1039 | di1y3jiVLXAg5pNts2mZkCBDrcMXRPUg | admin token account — skip |

**Users with named faces (face migration scope):**

| `id_user` | Username | Named people |
|---|---|---|
| 2 | chuni | 94 |
| 3 | darcy (local) | 19 |
| 6 | steviek | 16 |
| 7 | darcy@kao.family (LDAP) | 28 |

---

## Immich schema (relevant tables)

Inspected from Immich v2.6.0 / Postgres 17.

### `asset`
| Column | Notes |
|---|---|
| `id` | UUID PK |
| `ownerId` | UUID FK → `user.id` |
| `originalFileName` | Bare filename without path — matches `unit.filename` |
| `originalPath` | Full path within upload storage |
| `checksum` | SHA-1 bytes (not MD5 — cannot cross-reference with Synology `duplicate_hash`) |
| `deletedAt` | NULL if not trashed |

### `face` (Immich)
| Column | Notes |
|---|---|
| `id` | UUID PK |
| `assetId` | UUID FK → `asset.id` |
| `personId` | UUID FK → `person.id` — NULL if unassigned |
| `boundingBoxX1/Y1/X2/Y2` | float — bounding box coords |
| `embedding` | vector(512) — face embedding from Immich ML model |

### `person` (Immich)
| Column | Notes |
|---|---|
| `id` | UUID PK |
| `ownerId` | UUID FK → `user.id` |
| `name` | string — empty until user or script assigns it |
| `faceAssetId` | UUID — representative face asset |

---

## Why not inject Synology face embeddings directly?

Synology's `face.feature` column is a 512-byte binary blob using a proprietary
embedding format (likely from DeepFace or a Synology-internal model). Immich uses
InsightFace/antelopev2 embeddings. The two embedding spaces are incompatible —
you cannot compare or transfer them.

The approach taken here (majority vote via filename matching) sidesteps this
entirely: we use the filenames as a bridge between the two systems and rely on
Immich's own face detection having already run on the same photos.
