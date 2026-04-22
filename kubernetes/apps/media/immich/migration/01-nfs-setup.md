# NFS Setup — Synology DSM

Two NFS exports must be added to the Synology NAS before the Helm changes
will work. These paths are mounted read-only into the immich-server pod.

---

## Exports needed

| Path on NAS | Mount point in pod | Users covered |
|---|---|---|
| `/volume1/homes` | `/import/syno-local` | chuni, darcy (local), steviek (local), adonia, Lenaxia (mikek) |
| `/volume1/homes/@LH-KAO.FAMILY/61` | `/import/syno-ldap` | mikek, darcy (LDAP), steviek (LDAP), lola-poo, pandaria, tjkao |

---

## Steps in DSM 7

1. Open **DSM Control Panel** → **File Services** → **NFS**
2. Enable NFS service if not already enabled (tick "Enable NFS service")
3. Click **NFS Permissions** tab (or go to **Shared Folder** → edit each folder)

For each path:

### `/volume1/homes`

This is the `homes` shared folder. In DSM:

1. Go to **Control Panel** → **Shared Folder**
2. Select `homes` → click **Edit** → **NFS Permissions** tab
3. Click **Create** and fill in:
   - **Hostname or IP**: enter your cluster node subnet (e.g. `10.0.0.0/24`)
     or each worker node IP individually
   - **Privilege**: `Read Only`
   - **Squash**: `No mapping` (or `Map all users to admin` if you hit
     permission errors — the pod runs as nobody/root)
   - **Security**: `sys`
   - Enable: **Allow connections from non-privileged ports** ✓
   - Enable: **Allow users to access mounted subfolders** ✓
4. Click **OK** → **Save**

### `/volume1/homes/@LH-KAO.FAMILY/61`

DSM does not let you export subdirectories of a shared folder directly through
the GUI. You have two options:

**Option A (recommended): Export the full `homes` share and use a subpath mount**

Since `/volume1/homes` is already exported above, you can mount a subpath of
it in the Helm config:

```yaml
synology-ldap:
  type: nfs
  server: ${NAS_ADDR}
  path: /volume1/homes/@LH-KAO.FAMILY/61   # subpath of the homes export
  globalMounts:
    - path: /import/syno-ldap
      readOnly: true
```

NFSv3/v4 clients support mounting subdirectories of an export directly.
This will work as long as `Allow users to access mounted subfolders` is
checked on the `homes` export (see step 3 above).

**Option B: Create a separate shared folder for the LDAP homes**

If Option A doesn't work (some NFS server versions restrict subpath mounts):

1. In DSM → **Control Panel** → **Shared Folder** → **Create**
2. Name: `lh-kao-homes` (or similar)
3. Path: manually set to `/volume1/homes/@LH-KAO.FAMILY/61`
   (this requires SSH — see below)
4. Add NFS permission as above

Via SSH on the NAS:
```bash
# Create a bind mount or symlink to expose the LDAP subdir as a shared folder
# DSM may need a restart of the NFS service after manual edits
```

---

## Verification

From any cluster node (or your laptop if it can reach the NAS):

```bash
# List all NFS exports from the NAS
showmount -e <NAS_ADDR>

# Expected output should include:
# /volume1/homes  <cluster-subnet>
# (and optionally the LDAP subpath)

# Test mount the local homes share
mkdir -p /tmp/test-nfs
mount -t nfs <NAS_ADDR>:/volume1/homes /tmp/test-nfs
ls /tmp/test-nfs
# Should show: adonia  chuni  darcy  Lenaxia  steviek  ...

# Test the LDAP subpath
mount -t nfs <NAS_ADDR>:/volume1/homes/@LH-KAO.FAMILY/61 /tmp/test-nfs
ls /tmp/test-nfs
# Should show: darcy-1000005  mikek-1000032  steviek-1000006  ...

umount /tmp/test-nfs
```

After applying the Helm changes and flux reconciling, verify inside the pod:

```bash
kubectl exec -n media deploy/immich-server -- ls /import/syno-local/
# Expected: adonia  chuni  darcy  di1y3...  @eaDir  Lenaxia  steviek  ...

kubectl exec -n media deploy/immich-server -- ls /import/syno-ldap/
# Expected: darcy-1000005  lola-poo-1000017  mikek-1000032  ...
```

---

## Firewall notes

If the Synology has a firewall enabled (Control Panel → Security → Firewall),
ensure port 2049 (NFS) is allowed from the cluster node subnet.
NFSv4 also uses port 2049 exclusively. NFSv3 additionally uses ports 111
(portmapper), 892, 20048 — if you see mount failures, check these are open.
