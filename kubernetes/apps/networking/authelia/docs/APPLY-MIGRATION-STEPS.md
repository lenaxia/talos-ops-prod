# Authelia Migration - Execution Steps

## Current Status
All configuration changes are complete and committed. The migration is blocked on the Kubernetes secret not having the required keys.

## Prerequisites Check
The kustomization is properly configured:
- ✅ `app/kustomization.yaml` includes `secret.sops.yaml` 
- ✅ `ks.yaml` has substitution enabled: `substitution.flux.home.arpa/enabled: "true"`
- ✅ Path points to correct directory: `./kubernetes/apps/networking/authelia/app`
- ✅ All helm-release.yaml changes committed and pushed

## Step-by-Step Execution

### Step 1: Check Current State
```bash
# Check helm release version (should be 0.8.58 currently)
kubectl get helmrelease authelia -n networking -o jsonpath='{.spec.chart.spec.version}'
echo

# Check current pod image (should be 4.37.5 currently)
kubectl get deployment authelia -n networking -o jsonpath='{.spec.template.spec.containers[0].image}'
echo

# Check current secret keys
kubectl get secret authelia -n networking -o jsonpath='{.data}' | jq 'keys'

# Check pod status
kubectl get pods -n networking -l app.kubernetes.io/name=authelia
```

**Expected Current State:**
- Chart version: `0.8.58` (will be rolling back to this if upgrade fails)
- Image: `ghcr.io/authelia/authelia:4.37.5`
- Secret keys: May be missing LDAP_PASSWORD, SESSION_SECRET, etc.

---

### Step 2: Force Flux to Apply Secret
```bash
# Check if git changes are synced
flux get sources git home-kubernetes

# Reconcile the git source first
flux reconcile source git home-kubernetes --with-source

# Now reconcile the authelia kustomization (this will decrypt and apply secret.sops.yaml)
flux reconcile kustomization cluster-networking-authelia --with-source
```

**Watch for:**
- `✓ Kustomization reconciliation completed`
- `applied revision main/xxxxx`

**If errors occur:**
```bash
# Check kustomization logs
kubectl logs -n flux-system -l app=kustomize-controller --tail=50 | grep authelia

# Check for SOPS decryption issues
flux get kustomizations cluster-networking-authelia
```

---

### Step 3: Verify Secret Has Required Keys
```bash
# Check secret keys
kubectl get secret authelia -n networking -o jsonpath='{.data}' | jq 'keys'
```

**Required keys (must see all 6):**
```json
[
  "DUO_SECRET_KEY",
  "LDAP_PASSWORD",
  "OIDC_HMAC_SECRET",
  "SESSION_SECRET",
  "SMTP_PASSWORD",
  "STORAGE_ENCRYPTION_KEY"
]
```

**If keys are missing:**
```bash
# Check if secret.sops.yaml is included in kustomization
kubectl get kustomization cluster-networking-authelia -n flux-system -o yaml | grep -A 20 "inventory"

# Manually apply the secret as fallback
cd /home/mikekao/personal/talos-ops-prod/kubernetes/apps/networking/authelia/app
sops -d secret.sops.yaml | kubectl apply -f -

# Verify again
kubectl get secret authelia -n networking -o jsonpath='{.data}' | jq 'keys'
```

---

### Step 4: Trigger Helm Upgrade
```bash
# Force helm release reconciliation
flux reconcile helmrelease authelia -n networking

# Watch the helm release status
watch kubectl get helmrelease authelia -n networking
```

**Expected behavior:**
1. Helm will attempt upgrade to 0.10.49
2. Will create new ConfigMap with new schema
3. Will create new ReplicaSet with new pod
4. Pod will mount the secret successfully
5. Pod will start with image `ghcr.io/authelia/authelia:4.39.13`
6. After ~30s, pod should reach Ready state
7. Helm release status will show `Ready: True`

**Watch for these phases:**
- `HelmRelease/authelia progressing`
- `Helm upgrade succeeded`
- `Reconciliation finished`

---

### Step 5: Monitor Pod Startup
```bash
# Watch pods in real-time
kubectl get pods -n networking -l app.kubernetes.io/name=authelia -w
```

**In another terminal, watch logs:**
```bash
kubectl logs -n networking -l app.kubernetes.io/name=authelia -f
```

**Success indicators in logs:**
- `Configuration validated` or similar startup message
- LDAP connection successful
- OIDC provider initialized
- Server listening on port 9091

**If pod fails to start:**
```bash
# Check pod events
kubectl describe pod -n networking -l app.kubernetes.io/name=authelia

# Check for mount errors
kubectl get events -n networking --sort-by='.lastTimestamp' | grep authelia | tail -20
```

---

### Step 6: Verify Successful Migration
```bash
# Check final helm release version
kubectl get helmrelease authelia -n networking -o jsonpath='{.spec.chart.spec.version}'
# Should output: 0.10.49

# Check running image
kubectl get deployment authelia -n networking -o jsonpath='{.spec.template.spec.containers[0].image}'
# Should output: ghcr.io/authelia/authelia:4.39.13

# Check pod is ready
kubectl get pods -n networking -l app.kubernetes.io/name=authelia
# Should show: STATUS=Running, READY=1/1

# Check ConfigMap has proper OIDC secrets (not literal ${SECRET_*} strings)
kubectl get configmap authelia -n networking -o yaml | grep -A 5 "client_secret"
# Should see: value: $pbkdf2-sha512$... (NOT: value: ${SECRET_TAILSCALE...})
```

---

### Step 7: Test Functionality

#### Test 1: Access Authelia UI
```bash
curl -I https://authelia.thekao.cloud
# Should return: HTTP/2 200
```

#### Test 2: Test LDAP Authentication
1. Open https://authelia.thekao.cloud
2. Enter LDAP credentials
3. Verify successful login
4. Check 2FA flow (TOTP)

#### Test 3: Test OIDC Client (Pick One)
Example with Grafana:
1. Open Grafana
2. Click "Sign in with Authelia" or SSO button
3. Should redirect to Authelia
4. Should auto-approve (consent_mode: auto)
5. Should redirect back to Grafana authenticated

**Test these OIDC clients:**
- Tailscale: https://login.tailscale.com
- Grafana: https://grafana.thekao.cloud
- Outline: https://outline.thekao.cloud
- (Test at least 2-3 to verify)

---

## Troubleshooting

### Issue: Helm Keeps Rolling Back
**Symptom:** Version keeps reverting to 0.8.58

**Cause:** Pod not reaching Ready state within timeout

**Fix:**
1. Check pod logs for actual error
2. Fix the error
3. Delete failed pod: `kubectl delete pod -n networking -l app.kubernetes.io/name=authelia`
4. Retry: `flux reconcile helmrelease authelia -n networking`

### Issue: ConfigMap Shows Literal `${SECRET_*}` Strings
**Symptom:** ConfigMap contains `value: ${SECRET_TAILSCALE_OAUTH_CLIENT_SECRET_HASHED}` instead of actual hash

**Cause:** Flux variable substitution not working

**Fix:**
```bash
# Check if substitution is enabled
kubectl get kustomization cluster-networking-authelia -n flux-system -o yaml | grep substitution

# Check if secrets exist in flux-system
kubectl get secrets -n flux-system | grep cluster-secrets

# Check secret has the variables
kubectl get secret cluster-secrets -n flux-system -o yaml | grep TAILSCALE
```

### Issue: Pod CrashLoopBackOff
**Symptom:** Pod starts then crashes repeatedly

**Cause:** Configuration validation error in new schema

**Fix:**
```bash
# Get exact error from logs
kubectl logs -n networking -l app.kubernetes.io/name=authelia --tail=100

# Common errors:
# - "required field missing" → Schema issue in helm-release.yaml
# - "invalid address format" → Check storage/smtp address format
# - "invalid client secret" → OIDC secret hash format issue
```

### Issue: Secret Still Missing Keys After Reconcile
**Symptom:** Secret doesn't have LDAP_PASSWORD, SESSION_SECRET, etc.

**Possible causes:**
1. SOPS decryption failed (age key missing)
2. secret.sops.yaml not in git repository
3. Kustomization not picking up the file

**Fix:**
```bash
# Check SOPS configuration
kubectl get secret sops-age -n flux-system

# Verify file exists in git
cd /home/mikekao/personal/talos-ops-prod
git ls-files | grep "authelia/app/secret.sops.yaml"

# Manually decrypt and check
cd kubernetes/apps/networking/authelia/app
sops -d secret.sops.yaml
# Should show decrypted YAML with all keys

# If decryption works, manually apply
sops -d secret.sops.yaml | kubectl apply -f -
```

---

## Rollback Procedure

If migration completely fails and you need to rollback:

### Option 1: Git Revert (Recommended)
```bash
cd /home/mikekao/personal/talos-ops-prod/kubernetes/apps/networking/authelia/app

# Revert to previous commit
git log --oneline -5  # Find the commit before migration
git checkout <previous-commit-hash> helm-release.yaml

# Commit and push
git add helm-release.yaml
git commit -m "Rollback: Revert authelia to v0.8.58 due to migration issues"
git push

# Force flux to apply
flux reconcile source git home-kubernetes --with-source
flux reconcile kustomization cluster-networking-authelia --with-source
flux reconcile helmrelease authelia -n networking
```

### Option 2: Restore from Backup
```bash
cd /home/mikekao/personal/talos-ops-prod/kubernetes/apps/networking/authelia/app

# Restore backup
cp helm-release.yaml.backup helm-release.yaml

# Commit and push
git add helm-release.yaml
git commit -m "Rollback: Restore authelia from backup"
git push

# Force flux to apply
flux reconcile source git home-kubernetes --with-source
flux reconcile kustomization cluster-networking-authelia --with-source
flux reconcile helmrelease authelia -n networking
```

---

## Success Criteria Checklist

After completing all steps, verify:

- [ ] Secret `authelia` has all 6 required keys
- [ ] Helm release version is `0.10.49`
- [ ] Pod running with image `ghcr.io/authelia/authelia:4.39.13`
- [ ] Pod status is `Running` and `Ready 1/1`
- [ ] No errors in pod logs
- [ ] ConfigMap shows proper OIDC client secrets (hashed, not literals)
- [ ] Authelia UI accessible at https://authelia.thekao.cloud
- [ ] LDAP authentication works
- [ ] At least 2 OIDC clients tested and working
- [ ] No helm rollbacks occurring

---

## Post-Migration Cleanup

After successful migration and testing:

```bash
cd /home/mikekao/personal/talos-ops-prod/kubernetes/apps/networking/authelia/app

# Remove backup files (optional)
rm helm-release.yaml.backup
rm helm-release.yaml.before-path-change

# Update documentation with final status
# Edit docs/migration-session-log.md and mark all tasks complete

# Commit cleanup
git add .
git commit -m "Cleanup: Remove authelia migration backup files"
git push
```

---

## Timeline Expectations

- **Step 1-2 (Check & Apply Secret):** 1-2 minutes
- **Step 3 (Verify Secret):** 30 seconds
- **Step 4-5 (Helm Upgrade & Pod Start):** 2-5 minutes
- **Step 6 (Verification):** 1 minute
- **Step 7 (Testing):** 5-10 minutes

**Total expected time:** 10-20 minutes

---

## Key Files Reference

- Helm values: `/home/mikekao/personal/talos-ops-prod/kubernetes/apps/networking/authelia/app/helm-release.yaml`
- Secret: `/home/mikekao/personal/talos-ops-prod/kubernetes/apps/networking/authelia/app/secret.sops.yaml`
- Kustomization: `/home/mikekao/personal/talos-ops-prod/kubernetes/apps/networking/authelia/app/kustomization.yaml`
- Flux Kustomization: `/home/mikekao/personal/talos-ops-prod/kubernetes/apps/networking/authelia/ks.yaml`
- Backup: `/home/mikekao/personal/talos-ops-prod/kubernetes/apps/networking/authelia/app/helm-release.yaml.backup`

---

## Contact/Support

If issues persist:
1. Check all documentation in `docs/` directory
2. Review `docs/migration-session-log.md` for detailed context
3. Check Authelia v4.39 documentation: https://www.authelia.com/docs/
4. Check helm chart migration guide: https://github.com/authelia/chartrepo/blob/master/MIGRATION.md
