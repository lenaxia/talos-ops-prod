# Authelia Migration - Quick Reference

## 🎯 Current Status: READY TO EXECUTE

All configuration work is complete. The migration is now ready to be applied to the cluster.

---

## 📋 Quick Summary

**What:** Authelia helm chart upgrade from v0.8.58 to v0.10.49  
**Status:** Configuration complete, needs cluster application  
**Blocker:** Secret needs to be applied to cluster  
**Action Required:** Run the commands in `APPLY-MIGRATION-STEPS.md`

---

## ⚡ Quick Start Commands

### 1. Apply Secret (CRITICAL)
```bash
flux reconcile kustomization cluster-networking-authelia --with-source
kubectl get secret authelia -n networking -o jsonpath='{.data}' | jq 'keys'
```

### 2. Verify Secret Has 6 Keys
Required: `LDAP_PASSWORD`, `SESSION_SECRET`, `STORAGE_ENCRYPTION_KEY`, `SMTP_PASSWORD`, `DUO_SECRET_KEY`, `OIDC_HMAC_SECRET`

### 3. Trigger Helm Upgrade
```bash
flux reconcile helmrelease authelia -n networking
kubectl get pods -n networking -l app.kubernetes.io/name=authelia -w
```

### 4. Verify Success
```bash
kubectl get helmrelease authelia -n networking -o jsonpath='{.spec.chart.spec.version}'
# Should show: 0.10.49

kubectl get deployment authelia -n networking -o jsonpath='{.spec.template.spec.containers[0].image}'
# Should show: ghcr.io/authelia/authelia:4.39.13
```

---

## 📚 Documentation

| Document | Purpose | Length |
|----------|---------|--------|
| **APPLY-MIGRATION-STEPS.md** | Detailed execution steps with troubleshooting | 387 lines |
| **migration-session-log.md** | Complete session log of all work done | 864 lines |
| **CONTINUATION-PROMPT.md** | Context for continuing work in new session | 315 lines |
| **authelia-migration-tracking.md** | Comprehensive change tracking | 864 lines |
| **authelia-migration-summary.md** | Concise summary of changes | 275 lines |
| **authelia-secrets-configuration.md** | Secret configuration guide | 298 lines |
| **QUICK-REFERENCE.md** | This file | Quick access |

---

## ✅ What's Been Completed

- [x] Chart version updated: 0.8.58 → 0.10.49
- [x] Image tag override removed (uses chart appVersion 4.39.13)
- [x] Session schema migrated (added cookies array)
- [x] LDAP schema migrated (url → address, attributes restructured)
- [x] Storage/SMTP schemas migrated (address format)
- [x] OIDC completely restructured (10 clients, lifespans moved, fields renamed)
- [x] OIDC secrets updated to use hashed variants
- [x] Access control networks moved to definitions
- [x] Secret configuration migrated (per-component paths)
- [x] WebAuthn, TOTP schemas updated
- [x] Helm template validation passed
- [x] Changes committed and pushed to git
- [x] Comprehensive documentation created

---

## ⏭️ What's Next

1. **You need to run the commands** in `APPLY-MIGRATION-STEPS.md`
2. Start with Step 1 (Check Current State)
3. Follow through Step 7 (Test Functionality)
4. Use troubleshooting section if issues occur

---

## 🚨 Critical Information

### Why Migration Failed Previously
- Secret didn't have required keys (LDAP_PASSWORD, etc.)
- Pod couldn't mount secret volumes
- Helm automatically rolled back after 5 minute timeout

### Why It Will Work Now
- `secret.sops.yaml` contains all required keys
- Kustomization includes the secret file
- Flux just needs to reconcile to decrypt and apply it
- Once secret is in cluster, helm upgrade will succeed

### If You Need to Rollback
```bash
cd kubernetes/apps/networking/authelia/app
cp helm-release.yaml.backup helm-release.yaml
git add helm-release.yaml
git commit -m "Rollback: Revert authelia to v0.8.58"
git push
flux reconcile kustomization cluster-networking-authelia --with-source
```

---

## 🔧 Key Technical Details

### Chart Changes
- **Old:** v0.8.58 (Authelia 4.37.5)
- **New:** v0.10.49 (Authelia 4.39.13)
- **Breaking Changes:** 440+ across 27 sections

### OIDC Clients (10 total)
1. Tailscale
2. Minio
3. Open WebUI
4. PGAdmin
5. Grafana
6. Outline
7. Overseerr
8. Komga
9. Linkwarden
10. Forgejo

All migrated to new schema with hashed secrets.

### Secret Locations
Old: Centralized `secret.*` (deprecated)  
New: Per-component paths:
- `/secrets/authelia/LDAP_PASSWORD`
- `/secrets/authelia/SESSION_SECRET`
- `/secrets/authelia/STORAGE_ENCRYPTION_KEY`
- `/secrets/authelia/SMTP_PASSWORD`
- `/secrets/authelia/DUO_SECRET_KEY`
- `/secrets/authelia/OIDC_HMAC_SECRET`

---

## 📊 Expected Timeline

- **Apply Secret:** 1-2 minutes
- **Helm Upgrade:** 2-5 minutes
- **Verification:** 1 minute
- **Testing:** 5-10 minutes
- **Total:** 10-20 minutes

---

## 🎓 Files Reference

### Primary
- **helm-release.yaml** - Main configuration (updated ✓)
- **secret.sops.yaml** - Encrypted secrets (needs application)
- **kustomization.yaml** - Includes secret file (verified ✓)
- **ks.yaml** - Flux kustomization (verified ✓)

### Backup
- **helm-release.yaml.backup** - Original v0.8.58 config

### Documentation
- **docs/** directory - All migration documentation

---

## 💡 Pro Tips

1. **Watch logs during upgrade:** `kubectl logs -n networking -l app.kubernetes.io/name=authelia -f`
2. **Check events if pod fails:** `kubectl get events -n networking --sort-by='.lastTimestamp'`
3. **Verify ConfigMap secrets:** `kubectl get configmap authelia -n networking -o yaml | grep client_secret`
4. **Test incrementally:** Don't test all 10 OIDC clients at once, start with 1-2

---

## 📞 Getting Help

If stuck:
1. Check `APPLY-MIGRATION-STEPS.md` troubleshooting section
2. Review `migration-session-log.md` for full context
3. Check Authelia logs for specific errors
4. Verify secret has all 6 keys
5. Ensure Flux substitution is working

---

## ✨ Success Criteria

When complete, you should have:
- ✓ Helm release at v0.10.49
- ✓ Pod running Authelia 4.39.13
- ✓ All 10 OIDC clients with hashed secrets
- ✓ LDAP authentication working
- ✓ No errors in logs
- ✓ At least 2 OIDC clients tested successfully

---

**Last Updated:** 2026-01-22  
**Migration By:** OpenCode AI Assistant  
**Repository:** lenaxia/talos-ops-prod

---

## 🚀 Ready to Execute?

Start here: **docs/APPLY-MIGRATION-STEPS.md**

Good luck! 🎉
