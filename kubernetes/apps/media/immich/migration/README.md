# Synology Photos → Immich Migration

Migration of all Synology Photos libraries into Immich, plus transfer of named facial
recognition data from the Synology `synofoto` PostgreSQL database.

## Overview

```
Phase 0  Prerequisites          Manual steps (NFS exports, Immich accounts)
Phase 1  Helm changes           Add NFS mounts to immich helm-release.yaml
Phase 2  Photo upload           Run immich-cli per user to bulk upload all photos
Phase 3  Face name migration    Match Synology named-person data to Immich people
```

---

## User Map

| Immich account | Synology source path(s) | Syno id_user(s) | Has named faces |
|---|---|---|---|
| mikek    | `/import/syno-local/Lenaxia/Photos`<br>`/import/syno-ldap/mikek-1000032/Photos` | 5, 12 | No |
| darcy    | `/import/syno-local/darcy/Photos`<br>`/import/syno-ldap/darcy-1000005/Photos` | 3, 7 | Yes (47 merged) |
| chuni    | `/import/syno-local/chuni/Photos` | 2 | Yes (94) |
| steviek  | `/import/syno-local/steviek/Photos`<br>`/import/syno-ldap/steviek-1000006/Photos` | 6, 8 | Yes (16) |
| adonia   | `/import/syno-local/adonia/Photos` | 1 | No |
| lola-poo | `/import/syno-ldap/lola-poo-1000017/Photos` | 9 | No |
| pandaria | `/import/syno-ldap/pandaria-1000034/Photos` | 16 | No |
| tjkao    | `/import/syno-ldap/tjkao-1000018/Photos` | 14 | No |

**NFS mount points inside the immich-server pod:**
- `/import/syno-local` → NAS `/volume1/homes` (local/non-LDAP users)
- `/import/syno-ldap`  → NAS `/volume1/homes/@LH-KAO.FAMILY/61` (LDAP users)

---

## Phase 0: Prerequisites

### 0.1 Add NFS exports on Synology DSM

See [01-nfs-setup.md](01-nfs-setup.md) for step-by-step instructions.

Two exports needed:
- `/volume1/homes`
- `/volume1/homes/@LH-KAO.FAMILY/61`

Verify from any cluster node:
```bash
showmount -e <NAS_ADDR>
```

### 0.2 Create Immich user accounts

In Immich Admin UI → Administration → Users, create accounts for:

| Username | Email | Notes |
|---|---|---|
| mikek | mikek@kao.family | You (admin can be this account) |
| darcy | darcy@kao.family | Merged local + LDAP Synology accounts |
| chuni | chuni@kao.family | Local Synology account only |
| steviek | steviek@kao.family | Merged local + LDAP Synology accounts |
| adonia | adonia@kao.family | Local Synology account only |
| lola-poo | lola-poo@kao.family | LDAP Synology account only |
| pandaria | pandaria@kao.family | LDAP Synology account only |
| tjkao | tjkao@kao.family | LDAP Synology account only |

### 0.3 Generate API keys

For each user: Immich UI → Account Settings → API Keys → New API key.

Copy each key into `02-upload/users.env` (see `02-upload/users.env.example`).

---

## Phase 1: Helm Changes

Add two NFS persistence entries to `app/helm-release.yaml` under `persistence:`:

```yaml
synology-local:
  type: nfs
  server: ${NAS_ADDR}
  path: /volume1/homes
  globalMounts:
    - path: /import/syno-local
      readOnly: true
synology-ldap:
  type: nfs
  server: ${NAS_ADDR}
  path: /volume1/homes/@LH-KAO.FAMILY/61
  globalMounts:
    - path: /import/syno-ldap
      readOnly: true
```

Push to main and reconcile:
```bash
flux reconcile kustomization cluster-media-immich --with-source
```

Verify the mounts are visible inside the server pod:
```bash
kubectl exec -n media deploy/immich-server -- ls /import/syno-local/
kubectl exec -n media deploy/immich-server -- ls /import/syno-ldap/
```

---

## Phase 2: Photo Upload

### 2.1 Configure users

```bash
cp 02-upload/users.env.example 02-upload/users.env
# Edit 02-upload/users.env — fill in IMMICH_URL and each user's API key
```

`users.env` is gitignored — never commit it with real keys.

### 2.2 Run uploads

```bash
cd 02-upload/
chmod +x upload.sh
./upload.sh
```

The script uploads each user's source paths sequentially using the official
`immich-cli` Docker image. It:
- Runs `immich upload --recursive --album --ignore '**/\@eaDir/**'`
- Creates albums mirroring Synology folder names
- Deduplicates by SHA-1 — safe to re-run if interrupted
- Logs output per user to `upload-<username>-<timestamp>.log`

For users with multiple source paths (mikek, darcy, steviek), both paths are
uploaded under the same API key so all photos land in one Immich account.
The SHA-1 dedup means any photos duplicated between the local and LDAP
Synology accounts are stored only once in Immich.

### 2.3 Trigger Immich jobs

After all uploads complete, in Immich Admin UI → Administration → Jobs:

1. **Extract Metadata** → Run (all)
2. **Generate Thumbnails** → Run (all)
3. **Detect Faces** → Run (all)

> **Important:** Face detection must complete fully before running Phase 3.
> Monitor progress in the Jobs tab. Face detection on a large library can
> take many hours. Wait until the queue shows 0 active jobs.

---

## Phase 3: Face Name Migration

### 3.1 Dump the Synology database

On the Synology NAS:
```bash
# SSH into the NAS, then:
pg_dump synofoto -U SynologyPhotos > /tmp/synofoto.dump

# Copy to your laptop or directly to a location accessible from the cluster
scp user@nas:/tmp/synofoto.dump ./03-face-migration/synofoto.dump
```

### 3.2 Restore the dump into cluster postgres

The dump is restored as a new `synofoto` database on the existing CloudNativePG
cluster. This is temporary — drop it after migration is complete.

```bash
# Port-forward to the cluster postgres
kubectl port-forward -n databases svc/postgres-rw 5432:5432 &

# Create the database (using superuser credentials from postgres-superuser secret)
PGPASSWORD=$(kubectl get secret -n databases postgres-superuser -o jsonpath='{.data.password}' | base64 -d)
createdb -h localhost -U postgres synofoto

# Restore the dump
pg_restore -h localhost -U postgres -d synofoto --no-owner --no-privileges \
  03-face-migration/synofoto.dump

# Verify tables are present
psql -h localhost -U postgres -d synofoto -c '\dt'
```

> Note: The dump is from Postgres 11 (Synology) being restored into Postgres 17
> (cluster). `--no-owner --no-privileges` avoids role-related errors. The `oid`
> type used in `face.picture` is handled transparently.

### 3.3 Configure the face migration script

```bash
cp 03-face-migration/config.example.yaml 03-face-migration/config.yaml
# Edit config.yaml — fill in DB connection strings, Immich URL, and per-user API keys
```

`config.yaml` is gitignored — never commit it with real credentials.

### 3.4 Install dependencies

```bash
cd 03-face-migration/
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3.5 Dry run first

```bash
python3 match_faces.py --config config.yaml --dry-run
```

This prints what names would be assigned without making any API calls.
Review the output — check that high-confidence matches look correct before
applying. Pay attention to:
- Confidence scores: aim for > 70% before trusting a match
- The `unmatched.csv` output: names that couldn't be matched automatically

### 3.6 Apply

```bash
python3 match_faces.py --config config.yaml
```

Outputs:
- `matched.csv` — successfully named people with confidence scores
- `unmatched.csv` — names that need manual assignment in Immich UI

### 3.7 Review unmatched

Open `unmatched.csv`. For each entry, go to Immich UI → Explore → People,
find the correct face cluster visually, and assign the name manually.

Common reasons for no match:
- Person appears in very few photos (below Immich's minimum cluster threshold)
- Filename collision between users
- Photos were in Synology but not successfully uploaded (check upload logs)
- Immich split the person into multiple clusters (merge them in UI first, then
  re-run the script for that person with `--person "Name"`)

### 3.8 Cleanup

```bash
# Drop the temporary synofoto DB
psql -h localhost -U postgres -c 'DROP DATABASE synofoto;'

# Kill the port-forward
kill %1

# Remove the dump file
rm 03-face-migration/synofoto.dump
rm 03-face-migration/config.yaml
```

---

## Troubleshooting

### Upload stalls or fails mid-way
The script logs per-user. Re-run `./upload.sh` — the CLI will skip already-uploaded
files (SHA-1 match). You can also run a single user manually:
```bash
source users.env
docker run --rm \
  -e IMMICH_INSTANCE_URL="$IMMICH_URL/api" \
  -e IMMICH_API_KEY="$MIKEK_API_KEY" \
  -v "/path/to/photos:/import:ro" \
  ghcr.io/immich-app/immich-cli:latest \
  upload --recursive --album --ignore '**/\@eaDir/**' /import
```

### Face script reports "0 assets matched"
- Confirm uploads completed for that user
- Check `originalFileName` in Immich matches Synology `unit.filename` exactly:
  ```bash
  psql -h localhost -U postgres -d immich \
    -c "SELECT \"originalFileName\" FROM asset WHERE \"ownerId\" = '<uuid>' LIMIT 10;"
  psql -h localhost -U postgres -d synofoto \
    -c "SELECT filename FROM unit WHERE id_user = 2 LIMIT 10;"
  ```

### Immich person clusters are fragmented
If Immich split one real person across multiple person records, merge them first
in Immich UI (People page → select both → Merge), then re-run the script.

### pg_restore fails with role errors
Use `--no-owner --no-privileges` flags (already in the command above).
If it fails on `CREATE EXTENSION`, the extensions (vector, etc.) may already
exist in the target DB — use `--if-exists` or ignore those errors.
