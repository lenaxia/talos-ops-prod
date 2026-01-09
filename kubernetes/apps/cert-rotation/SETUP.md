# Setup Instructions for Certificate Rotation CronJob

This file contains instructions for setting up the admin credentials required by the certificate rotation CronJob.

## Step 1: Create Admin Talos Config Secret

The CronJob needs admin credentials to authenticate to Talos API and generate new client configs.

**Important:** Only rotate admin credentials, never share them publicly.

### Option A: Copy from existing encrypted talosconfig

If you already have an encrypted admin talosconfig at `kubernetes/bootstrap/talos/talsecret.sops.yaml`:

```bash
# 1. Decrypt your existing admin talosconfig
sops -d -i kubernetes/bootstrap/talos/talsecret.sops.yaml > /tmp/admin-talosconfig.yaml

# 2. Create new secret for CronJob
cat > kubernetes/bootstrap/cert-rotation/talos-admin-config.sops.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: talos-admin-config
  namespace: cert-rotation
type: Opaque
stringData:
  talosconfig: |-
$(cat /tmp/admin-talosconfig.yaml)
EOF

# 3. Encrypt with SOPS
sops -e -i kubernetes/bootstrap/cert-rotation/talos-admin-config.sops.yaml

# 4. Cleanup
rm /tmp/admin-talosconfig.yaml

# 5. Commit
git add kubernetes/bootstrap/cert-rotation/talos-admin-config.sops.yaml
git commit -m "feat: add admin talosconfig for cert rotation"
git push origin feature/cert-rotation
```

### Option B: Create new admin talosconfig manually

If you don't have an encrypted admin talosconfig or want to create a new one:

```bash
# 1. Generate new admin talosconfig
talosctl config new kubernetes/bootstrap/cert-rotation/talos-admin-config.yaml \
  --roles os:admin \
  --crt-ttl 8760h

# 2. Create Secret manifest
cat > kubernetes/bootstrap/cert-rotation/talos-admin-config.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: talos-admin-config
  namespace: cert-rotation
type: Opaque
stringData:
  talosconfig: |-
$(cat kubernetes/bootstrap/cert-rotation/talos-admin-config.yaml)
EOF

# 3. Encrypt with SOPS
sops -e -i kubernetes/bootstrap/cert-rotation/talos-admin-config.yaml

# 4. Cleanup
rm kubernetes/bootstrap/cert-rotation/talos-admin-config.yaml

# 5. Commit
git add kubernetes/bootstrap/cert-rotation/talos-admin-config.sops.yaml
git commit -m "feat: add admin talosconfig for cert rotation"
git push origin feature/cert-rotation
```

## Step 2: Remove Unused CronJob Volume Mounts

The CronJob currently has volume mounts for non-existent resources. Remove them:

```bash
# Edit kubernetes/bootstrap/cert-rotation/cronjob.yaml
# Remove these volume mounts from the CronJob spec:
# - name: talosconfig
# - name: kubeconfig
```

Then add the new admin config volume mount:

```yaml
volumes:
  - name: talos-admin-config
    secret:
      secretName: talos-admin-config
  - name: workspace
      emptyDir: {}
```

And update volumeMounts in the container spec:

```yaml
volumeMounts:
  - name: talos-admin-config
    mountPath: /talos
    readOnly: true
  - name: workspace
    mountPath: /workspace
```

## Step 3: Update CronJob Environment Variables

The CronJob needs to know where to find the admin config:

```yaml
env:
  - name: TALOSCONFIG
    value: /talos/talosconfig
```

## Step 4: Commit and Push

After making these changes:

```bash
git add -A
git commit -m "fix: update CronJob to use admin config secret"
git push origin feature/cert-rotation
```

## Step 5: Apply CronJob to Cluster

```bash
kubectl apply -k kubernetes/bootstrap/cert-rotation/
```

## Verification

After deployment, verify the CronJob can access the admin config:

```bash
# Check CronJob status
kubectl get cronjob -n cert-rotation

# Check secrets
kubectl get secret -n cert-rotation

# Manual test run (optional)
kubectl create job --from=cronjob/cert-rotator -n cert-rotation

# Check logs
kubectl logs -n cert-rotation job/cert-rotator-*
```

## Security Notes

- The admin talosconfig is encrypted with SOPS + age
- Only the CronJob ServiceAccount can access it in the cluster
- The CronJob uses admin config ONLY to generate new client configs
- New client configs are encrypted before committing to git
- No plaintext credentials ever leave the cluster
