# App Template v4.3.0 Upgrade Status

## Current Situation

The app-template upgrade to v4.3.0 is **INCOMPLETE**. Only a subset of applications have been upgraded.

## Files Successfully Upgraded to v4.3.0 ✅

The following applications are already on v4.3.0:
- stirling-pdf
- fasten
- redlib
- stablediffusion
- monica
- frigate
- browserless
- esphome
- magicmirror
- linkwarden
- mosquitto
- minio
- brother-ql-web
- uptimekuma
- guacamole
- openldap
- vaultwarden-ldap
- changedetection
- pgadmin
- librespeed

## Files Still Needing Upgrade ❌

### Version 3.1.0 (Most Common)
- `kubernetes/apps/home/node-red/app/helm-release.yaml`
- `kubernetes/apps/home/langserver/app/helm-release.yaml`
- `kubernetes/apps/home/babybuddy-pandaria/app/helm-release.yaml`
- `kubernetes/apps/home/gamevault/app/helm-release.yaml`
- `kubernetes/apps/home/hercules/renewal/helm-release.yaml`
- `kubernetes/apps/home/hercules/classic/helm-release.yaml`
- `kubernetes/apps/home/babybuddy/app/helm-release.yaml`
- `kubernetes/apps/home/babybuddy/base/helm-release.yaml`
- `kubernetes/apps/home/localai/big-agi/helm-release.yaml`
- `kubernetes/apps/home/localai/jupyter/helm-release.yaml`
- `kubernetes/apps/home/localai/vllm/helm-release.yaml`
- `kubernetes/apps/home/localai/open-webui/helm-release.yaml`
- `kubernetes/apps/home/localai/litellm/helm-release.yaml`
- `kubernetes/apps/home/vscode/app/helm-release.yaml`
- `kubernetes/apps/home/zwavejs/app/helm-release.yaml`
- `kubernetes/apps/storage/kopia-web/app/helm-release.yaml`
- `kubernetes/apps/storage/paperless/app/helm-release.yaml`
- `kubernetes/apps/utilities/adguard/app/helm-release.yaml`
- `kubernetes/apps/utilities/it-tools/app/helm-release.yaml`

### Version 3.5.1
- `kubernetes/apps/home/home-assistant/app/helm-release.yaml`

### Version 2.6.0
- `kubernetes/apps/home/magicmirror/base/helm-release.yaml`
- `kubernetes/apps/home/localai/tabbyapi/helm-release.yaml`

## Why Flux Isn't Seeing the Changes

Even for files that ARE upgraded to v4.3.0, Flux may not have synced yet because:

1. **Flux operates on a schedule** - By default, GitRepository resources reconcile every 1-5 minutes
2. **Git commit not synced** - Flux is still pointing to an older commit
3. **Manual reconciliation needed** - You can force Flux to sync immediately

## Next Steps

### Option 1: Complete the Upgrade (Recommended)

Run the upgrade script on the remaining files:
```bash
python3 hack/app-template-upgrade-v4.py
```

### Option 2: Force Flux to Sync Current State

If you want Flux to pick up the files that ARE already upgraded:
```bash
# Force GitRepository to sync
kubectl annotate gitrepository flux-system -n flux-system \
  reconcile.fluxcd.io/requestedAt="$(date +%s)" --overwrite

# Wait and force Kustomizations to reconcile
sleep 15
kubectl get kustomization -A -o name | xargs -I {} kubectl annotate {} \
  reconcile.fluxcd.io/requestedAt="$(date +%s)" --overwrite
```

## Verification Commands

Check which files need upgrading:
```bash
find kubernetes/apps -name "helm-release.yaml" -exec grep -l "chart: app-template" {} \; | \
  xargs grep -H "version:" | grep -v "4.3.0"
```

Check Flux GitRepository status:
```bash
kubectl get gitrepository -n flux-system flux-system -o jsonpath='{.status.artifact.revision}'
```

Check current Git commit:
```bash
git rev-parse HEAD
```

Monitor HelmRelease status:
```bash
watch -n 5 'flux get hr -A | grep -v Succeeded'