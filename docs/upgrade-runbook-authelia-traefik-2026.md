# Upgrade Runbook: Authelia 0.8.58→0.10.49 + Traefik 27.0.2→39.0.5

**Date:** 2026-03-18  
**Cluster domain:** `thekao.cloud`  
**Traefik LB IP:** `192.168.5.12`  
**Authelia LB IP:** `192.168.5.11`  
**All required changes:** documented in `docs/upgrade-plan-authelia-traefik-2026.md` (fifth-pass validated)  
**Charts available locally:** `/tmp/authelia-0.10.49/` and `/tmp/traefik-v39/`

---

## Part 1 — Pre-Rollout Validation

Run every check below before making any edits. Every check must pass. A failing check means a prerequisite is broken and the upgrade should not proceed until it is resolved.

### 1.1 — Cluster health baseline

```bash
# All nodes Ready
kubectl get nodes

# No HelmRelease in failed state
kubectl get helmrelease -A | grep -v "True\|READY"

# Traefik pods running and healthy (expect 4 replicas)
kubectl get pod -n networking -l app.kubernetes.io/name=traefik

# Authelia pod running and healthy (expect 1 replica)
kubectl get pod -n networking -l app.kubernetes.io/name=authelia

# Flux kustomizations all reconciled
kubectl get kustomization -n flux-system | grep -v "True\|READY"
```

**Pass criteria:** All nodes Ready. No HelmRelease failures. All 4 Traefik pods Running. Authelia pod Running. No Flux kustomization failures.

### 1.2 — Authelia login smoke test (baseline)

```bash
# Login page returns HTTP 200
curl -sk https://authelia.thekao.cloud -o /dev/null -w "%{http_code}\n"
```

**Pass criteria:** `200`

### 1.3 — ForwardAuth protection smoke test (baseline)

```bash
# Protected route without auth cookie must redirect to Authelia (302)
curl -sk https://traefik.thekao.cloud -o /dev/null -w "%{http_code}\n"

# Bypass route must respond directly (200 or 301/302 to app, not to Authelia)
curl -sk https://vault.thekao.cloud -o /dev/null -w "%{http_code}\n"
```

**Pass criteria:** `traefik.thekao.cloud` returns `302` (redirect to Authelia). `vault.thekao.cloud` returns anything other than a redirect to `authelia.thekao.cloud` (it has bypass policy).

### 1.4 — Authelia API baseline

```bash
# Health endpoint
curl -sk https://authelia.thekao.cloud/api/health | python3 -m json.tool

# Old verify endpoint — must return 401 (exists, unauthenticated)
curl -sk https://authelia.thekao.cloud/api/verify -o /dev/null -w "%{http_code}\n"
```

**Pass criteria:** `/api/health` returns `{"status":"OK"}`. `/api/verify` returns `401` (not `404`). After upgrade `/api/verify` will return `404` — this baseline confirms the current state.

### 1.5 — SQLite backup (mandatory — the only non-reversible step)

```bash
AUTHELIA_POD=$(kubectl get pod -n networking \
  -l app.kubernetes.io/name=authelia \
  -o jsonpath='{.items[0].metadata.name}')

kubectl exec -n networking "$AUTHELIA_POD" -- \
  cat /config/db.sqlite3 > authelia-db-$(date +%Y%m%d-%H%M).sqlite3

# Verify backup is non-zero
ls -lh authelia-db-*.sqlite3
```

**Pass criteria:** Backup file exists and is > 0 bytes. Do not proceed until this is confirmed.

### 1.6 — Confirm chart tarballs available locally

```bash
ls /tmp/authelia-0.10.49/authelia/Chart.yaml
ls /tmp/traefik-v39/traefik/Chart.yaml
helm repo list | grep -E "authelia|traefik"
```

**Pass criteria:** Both Chart.yaml files exist. Both repos registered in helm.

---

## Part 2 — Pre-Push Validation (after all edits are made, before git push)

All file edits must be complete before running these checks. These gates must all pass before pushing.

### 2.1 — Helm schema dry-run: Traefik

```bash
helm template traefik /tmp/traefik-v39/traefik \
  -f kubernetes/apps/networking/traefik/app/helm-release.yaml \
  2>&1 | grep -Ei "error|not allowed|fail"
```

**Pass criteria:** No output. Any match is a blocking schema error that must be fixed before proceeding.

### 2.2 — Helm schema dry-run: Authelia

```bash
helm template authelia /tmp/authelia-0.10.49/authelia \
  -f kubernetes/apps/networking/authelia/app/helm-release.yaml \
  2>&1 | grep -Ei "error|not allowed|fail"
```

**Pass criteria:** No output. The Authelia chart's `{{ fail }}` calls (for `userinfo_signing_algorithm`, missing `client_secret` hash prefix, missing `session.cookies`) will appear here if triggered — any match is a blocking error.

### 2.3 — No old CRD API group remaining

```bash
# Must return zero active (non-commented) lines
grep -r "traefik.containo.us" kubernetes/ --include="*.yaml" | grep -v "#"
```

**Pass criteria:** No output.

### 2.4 — No forbidden keys remaining

```bash
grep -rE \
  "globalArguments:|pilot:|fallbackApiVersion:|forceSlash:|ipWhiteList:|redirectTo:|enabledSecret:|remember_me_duration:|userinfo_signing_algorithm:" \
  kubernetes/ --include="*.yaml" | grep -v "#"
```

**Pass criteria:** No output.

### 2.5 — Old API endpoint URLs gone

```bash
grep -r "api/verify" kubernetes/ --include="*.yaml"
```

**Pass criteria:** No output.

### 2.6 — New API endpoint URLs present

```bash
# ForwardAuth middleware must point to new endpoint
grep "api/authz/forward-auth" \
  kubernetes/apps/networking/traefik/middlewares/middlewares.yaml

# Kyverno policy must point to new auth-request endpoint
grep "api/authz/auth-request" \
  kubernetes/apps/kyverno/policies/apply-ingress-auth-annotations.yaml
```

**Pass criteria:** Both grep commands return a matching line.

### 2.7 — Dashboard port updated

```bash
grep "8080" kubernetes/apps/networking/traefik/ingresses/traefik.yaml
```

**Pass criteria:** Returns the line `number: 8080`.

### 2.8 — Checklist cross-check

Open `docs/upgrade-plan-authelia-traefik-2026.md`. Read through the pre-flight checklist for both Traefik and Authelia (lines 919–1005). For each item, physically confirm the change is present in the edited file. This is the only way to catch omissions that schema validation does not cover (e.g. forgetting `session.cookies`, which causes a runtime `{{ required }}` failure rather than a schema error).

---

## Part 3 — Rollout

### 3.1 — Commit and push (single atomic commit)

All changes go in one commit. Do not push partial changes.

```bash
git add \
  kubernetes/apps/networking/traefik/app/helm-release.yaml \
  kubernetes/apps/networking/traefik/middlewares/middlewares.yaml \
  kubernetes/apps/networking/traefik/middlewares/middlewares-chains.yaml \
  kubernetes/apps/networking/traefik/middlewares/cloudflare.yaml \
  kubernetes/apps/networking/traefik/middlewares/test.yaml \
  kubernetes/apps/networking/traefik/ingresses/guacamole.yaml \
  kubernetes/apps/networking/traefik/ingresses/plex.yaml \
  kubernetes/apps/networking/traefik/ingresses/synology-drive.yaml \
  kubernetes/apps/networking/traefik/ingresses/synology-file.yaml \
  kubernetes/apps/networking/traefik/ingresses/synology-moments.yaml \
  kubernetes/apps/networking/traefik/ingresses/synology-photos.yaml \
  kubernetes/apps/networking/traefik/ingresses/traefik.yaml \
  kubernetes/apps/storage/minio/app/middlewares.yaml \
  kubernetes/apps/networking/authelia/app/helm-release.yaml \
  kubernetes/apps/kyverno/policies/apply-ingress-auth-annotations.yaml

git commit -m "upgrade traefik v27→v39 (v2→v3) and authelia v0.8→v0.10"
git push
```

### 3.2 — What Flux does (automatic, no action required)

Flux reconciles on a 30m interval with 1m retryInterval. The Traefik ks.yaml has an explicit dependency chain:

1. `cluster-networking-traefik` reconciles first (helm-release.yaml)
2. `cluster-networking-traefik-middlewares` reconciles after (depends on traefik)
3. `cluster-networking-traefik-ingresses` reconciles after (depends on traefik + middlewares)
4. `cluster-networking-authelia` reconciles independently (no dependsOn in its ks.yaml)

The new `traefik.io/v1alpha1` CRD resources from middleware/ingress files will be applied. Kubernetes will hold them as pending if the new CRDs are not yet installed. The Traefik Helm upgrade installs the new CRDs as part of the chart. Once Traefik v3 is running, all `traefik.io/v1alpha1` resources become valid simultaneously.

The old `traefik.containo.us` CRDs remain installed (you have not deleted them) and are ignored by Traefik v3.

### 3.3 — Force immediate reconciliation (optional, skips the 30m wait)

```bash
flux reconcile source git home-kubernetes
flux reconcile kustomization cluster-networking-traefik --with-source
flux reconcile kustomization cluster-networking-authelia --with-source
```

### 3.4 — Watch rollout progress

```bash
# Watch HelmRelease status
watch kubectl get helmrelease -n networking

# Watch pod rollout
watch kubectl get pod -n networking

# Tail Traefik logs during upgrade
kubectl logs -n networking -l app.kubernetes.io/name=traefik -f --tail=50

# Tail Authelia logs during upgrade
kubectl logs -n networking -l app.kubernetes.io/name=authelia -f --tail=100
```

**Expected Authelia log on successful startup:**
```
level=info msg="Configuration parsed successfully without errors"
level=info msg="Authelia v4.39.13 is starting"
```

**Authelia log indicating config error (rollback trigger):**
```
level=fatal msg="..."
```
Any `fatal` log line on startup means Authelia refused to start. Proceed to rollback.

---

## Part 4 — Post-Rollout Validation

Run all checks below after Flux reconciliation shows both HelmReleases as `Ready=True`. A failing check requires either a targeted fix-forward or rollback per Part 5.

### 4.1 — Confirm deployed versions

```bash
# Traefik: must show v3.6.10
kubectl get pod -n networking -l app.kubernetes.io/name=traefik \
  -o jsonpath='{range .items[*]}{.spec.containers[0].image}{"\n"}{end}'

# Authelia: must show 4.39.13
kubectl get pod -n networking -l app.kubernetes.io/name=authelia \
  -o jsonpath='{range .items[*]}{.spec.containers[0].image}{"\n"}{end}'

# HelmRelease status: both must show True
kubectl get helmrelease -n networking traefik authelia
```

**Pass criteria:** Traefik image contains `v3.6.10`. Authelia image contains `4.39.13`. Both HelmReleases show `READY=True`.

### 4.2 — Authelia health

```bash
# Health endpoint
curl -sk https://authelia.thekao.cloud/api/health | python3 -m json.tool
```

**Pass criteria:** `{"status":"OK"}`. Any other response means Authelia is unhealthy.

### 4.3 — New authz endpoint present; old endpoint gone

```bash
# New forward-auth endpoint: must return 401 (exists, unauthenticated)
curl -sk https://authelia.thekao.cloud/api/authz/forward-auth \
  -o /dev/null -w "%{http_code}\n"

# New auth-request endpoint: must return 401
curl -sk https://authelia.thekao.cloud/api/authz/auth-request \
  -o /dev/null -w "%{http_code}\n"

# Old endpoint: must return 404 (no longer registered)
curl -sk https://authelia.thekao.cloud/api/verify \
  -o /dev/null -w "%{http_code}\n"
```

**Pass criteria:** `/api/authz/forward-auth` → `401`. `/api/authz/auth-request` → `401`. `/api/verify` → `404`. If `/api/verify` returns `401`, the legacy endpoint is still registered — check if `legacy` was accidentally added to `configMap.server.endpoints`.

### 4.4 — ForwardAuth protection working

```bash
# Auth-protected route must redirect to Authelia login (302)
curl -sk https://traefik.thekao.cloud -D - -o /dev/null 2>&1 | grep -E "^HTTP|^Location"
```

**Pass criteria:** `HTTP/2 302` with `Location: https://authelia.thekao.cloud/?rd=...`. If `502` — Traefik cannot reach Authelia. If `200` without authentication — forwardAuth middleware is not applied.

### 4.5 — Traefik dashboard accessible

```bash
# Must return 200 or 302 (dashboard loads through auth)
curl -sk https://traefik.thekao.cloud -o /dev/null -w "%{http_code}\n"

# Confirm Traefik is listening on port 8080 internally (not 9000)
kubectl exec -n networking \
  $(kubectl get pod -n networking -l app.kubernetes.io/name=traefik \
    -o jsonpath='{.items[0].metadata.name}') \
  -- wget -qO- http://localhost:8080/api/version 2>/dev/null | python3 -m json.tool
```

**Pass criteria:** Dashboard URL responds. `localhost:8080/api/version` returns JSON with `"Version":"3.6.10"`. If port 8080 returns nothing, check whether `ports.traefik.port` was accidentally set to 9000.

### 4.6 — HTTP→HTTPS redirect working

```bash
curl -sk http://authelia.thekao.cloud -D - -o /dev/null 2>&1 | grep "^Location"
```

**Pass criteria:** `Location: https://authelia.thekao.cloud/` — confirms `ports.web.http.redirections` is working correctly.

### 4.7 — TLS working

```bash
# Must negotiate TLS 1.2 or 1.3, with valid cert
curl -sv https://authelia.thekao.cloud -o /dev/null 2>&1 | grep -E "SSL|TLS|certificate|expire"
```

**Pass criteria:** TLS 1.2 or TLS 1.3 negotiated. Certificate valid (not expired, no SNI error). SNI strict is enabled — a missing SNI would cause a TLS handshake failure.

### 4.8 — Authelia login page functional (manual)

Open a browser and navigate to `https://authelia.thekao.cloud`. Verify:
- Login page renders without error
- Enter valid LDAP credentials
- 2FA prompt appears (Duo push)
- Authentication succeeds and redirects to `https://authelia.thekao.cloud`

**Pass criteria:** Full login flow completes without error.

### 4.9 — ForwardAuth end-to-end (manual)

1. Clear browser cookies for `thekao.cloud`
2. Navigate to `https://traefik.thekao.cloud` (two-factor, administrators group required)
3. Confirm redirect to Authelia login
4. Log in with valid credentials + 2FA
5. Confirm redirect back to `https://traefik.thekao.cloud` and dashboard loads

**Pass criteria:** Full forwardAuth cycle completes. Dashboard loads after authentication.

### 4.10 — OIDC: Grafana (priority test — simplest OIDC client)

1. Navigate to `https://grafana.thekao.cloud`
2. Click "Sign in with Authelia" (generic OAuth)
3. Complete login at Authelia
4. Confirm redirect back to Grafana and user is logged in

**Pass criteria:** OIDC flow completes. User is authenticated in Grafana. If this fails with `invalid_client`, check `token_endpoint_auth_method` — Grafana is a generic OAuth client and should accept the new default `client_secret_post`.

### 4.11 — OIDC: Tailscale (highest-risk client — token_endpoint_auth_method)

Tailscale OIDC is the highest-risk client because its auth method compatibility with the new `client_secret_post` default is unconfirmed.

In Tailscale admin console → Settings → SSO → check if the OIDC provider shows as connected/healthy.

If Tailscale shows an auth error, add `token_endpoint_auth_method: client_secret_basic` to the tailscale client entry in `helm-release.yaml` and push. This is a fix-forward, not a rollback.

**Pass criteria:** Tailscale SSO shows healthy in admin console.

### 4.12 — Bypass policies still working (no false auth blocks)

```bash
# vault.thekao.cloud has bypass policy — must not redirect to Authelia
curl -sk https://vault.thekao.cloud -D - -o /dev/null 2>&1 | \
  grep "^Location" | grep -v "authelia"

# s3.thekao.cloud has bypass policy
curl -sk https://s3.thekao.cloud -o /dev/null -w "%{http_code}\n"
```

**Pass criteria:** Neither URL redirects to `authelia.thekao.cloud`.

### 4.13 — Prometheus metrics scraping

```bash
# Traefik metrics endpoint
curl -sk http://192.168.5.12:8082/metrics | head -5

# Authelia metrics endpoint
curl -sk http://192.168.5.11:9959/metrics | head -5
```

**Pass criteria:** Both return Prometheus text format output starting with `# HELP` or `# TYPE`.

### 4.14 — Delete old CRDs (final cleanup — after all above pass)

Only after all checks above pass:

```bash
# Confirm old CRDs still present (expected — not yet deleted)
kubectl get crd | grep "containo.us"

# Delete them
kubectl delete crds \
  ingressroutes.traefik.containo.us \
  ingressroutetcps.traefik.containo.us \
  ingressrouteudps.traefik.containo.us \
  middlewares.traefik.containo.us \
  middlewaretcps.traefik.containo.us \
  serverstransports.traefik.containo.us \
  tlsoptions.traefik.containo.us \
  tlsstores.traefik.containo.us \
  traefikservices.traefik.containo.us

# Confirm deletion
kubectl get crd | grep "containo.us"
```

**Pass criteria:** `kubectl get crd | grep "containo.us"` returns nothing after deletion.

---

## Part 5 — Rollback

### 5.0 — Rollback decision criteria

Initiate rollback if any of the following occur:

| Condition | Severity | Response |
|-----------|----------|----------|
| Authelia pod in `CrashLoopBackOff` after > 3 restarts | Critical | Full rollback |
| Traefik pod in `CrashLoopBackOff` after > 3 restarts | Critical | Traefik-only rollback |
| `HelmRelease` stays `Ready=False` after 10 minutes | High | Check logs; rollback if no progress |
| All auth-protected routes return `502` | Critical | Likely Authelia failure; rollback |
| Authelia login page returns `500` or blank | Critical | Full rollback |
| `/api/health` returns non-`OK` | High | Check logs; rollback if not transient |
| OIDC broken for all clients | High | Fix-forward first; rollback if unresolvable |

Do not rollback for a single OIDC client failure — fix forward (see 5.4).

---

### 5.1 — Traefik-only rollback (Authelia not yet upgraded or Authelia still healthy)

**When:** Traefik pod crashloops or HelmRelease fails. Authelia is either still on v4.37 or successfully upgraded.

**If Authelia is still on v4.37 (upgrade not yet applied):**

```bash
# Revert Traefik helm-release only
git checkout HEAD -- kubernetes/apps/networking/traefik/app/helm-release.yaml
git commit -m "revert: traefik helm-release to v27.0.2"
git push

# Force immediate Flux reconcile
flux reconcile kustomization cluster-networking-traefik --with-source
```

The CRD files will still contain `traefik.io/v1alpha1` but Traefik v2 ignores unknown CRD groups entirely — it only watches `traefik.containo.us`. Routing recovers immediately. Revert the CRD files in a separate follow-up commit once stable.

**If you need recovery in under 60 seconds (don't wait for Flux):**

```bash
# Suspend Flux to prevent it fighting with manual changes
flux suspend kustomization cluster-networking-traefik

# Roll back the Helm release directly
helm rollback traefik -n networking

# Verify pod recovery
kubectl get pod -n networking -l app.kubernetes.io/name=traefik

# Once stable, resume Flux and push the revert commit
flux resume kustomization cluster-networking-traefik
```

---

### 5.2 — Authelia-only rollback (Traefik already upgraded to v3)

**When:** Traefik v3 is live and working. Authelia upgrade fails.

**The complication:** Traefik v3 is now calling `/api/authz/forward-auth` on an Authelia that is either crashing (v4.39 failed) or needs to be reverted to v4.37 (which doesn't have that endpoint). All forwardAuth-protected routes will return `502` until this is resolved.

**Step 1 — Patch the forwardAuth middleware immediately (takes effect in seconds, no Flux wait):**

```bash
# This re-points Traefik at /api/verify
# v4.37 has /api/verify; v4.39 in crash does not respond at all
# Either way this stops the 502 storm for routes while you work
kubectl patch middleware middlewares-authelia -n networking \
  --type=json \
  -p '[{"op":"replace","path":"/spec/forwardAuth/address",
       "value":"http://authelia.networking.svc.cluster.local/api/verify?rd=https://authelia.thekao.cloud"}]'
```

**Step 2 — Roll back Authelia Helm release:**

```bash
helm rollback authelia -n networking
kubectl get pod -n networking -l app.kubernetes.io/name=authelia
```

**Step 3 — Check if SQLite migration ran (the critical question):**

```bash
kubectl logs -n networking \
  $(kubectl get pod -n networking -l app.kubernetes.io/name=authelia \
    -o jsonpath='{.items[0].metadata.name}') | grep -i "migrat\|schema\|database"
```

If v4.37 starts successfully after rollback, the DB was either not migrated or the migration was backwards-compatible. Proceed to Step 5.

If v4.37 crashes with a DB schema error:

```bash
# Stop authelia
kubectl scale deployment authelia -n networking --replicas=0

# Restore SQLite backup
AUTHELIA_POD=$(kubectl get pod -n networking \
  -l app.kubernetes.io/name=authelia \
  -o jsonpath='{.items[0].metadata.name}')

kubectl cp authelia-db-YYYYMMDD-HHMM.sqlite3 \
  networking/$AUTHELIA_POD:/config/db.sqlite3

# Restart
kubectl scale deployment authelia -n networking --replicas=1
kubectl logs -n networking -l app.kubernetes.io/name=authelia -f --tail=50
```

**Step 4 — Confirm v4.37 is healthy:**

```bash
curl -sk https://authelia.thekao.cloud/api/health | python3 -m json.tool
curl -sk https://authelia.thekao.cloud/api/verify -o /dev/null -w "%{http_code}\n"
```

Pass criteria: `/api/health` → `{"status":"OK"}`. `/api/verify` → `401`.

**Step 5 — Restore forwardAuth middleware URL in git and push:**

```bash
# Revert both authelia helm-release and the middleware URL
git checkout HEAD -- \
  kubernetes/apps/networking/authelia/app/helm-release.yaml \
  kubernetes/apps/networking/traefik/middlewares/middlewares.yaml
git commit -m "revert: authelia to v0.8.58, restore /api/verify forwardAuth URL"
git push

flux reconcile kustomization cluster-networking-traefik --with-source
flux reconcile kustomization cluster-networking-authelia --with-source
```

**Note:** After this revert, Traefik is on v3 with `traefik.io/v1alpha1` CRDs and Authelia is on v4.37. This is a stable intermediate state — Traefik v3 works correctly with the reverted middleware URL pointing to `/api/verify` on v4.37.

---

### 5.3 — Full rollback (both failed, or Traefik failed before Authelia was attempted)

```bash
# Revert everything
git revert HEAD --no-edit
git push

# Force immediate Flux reconcile
flux reconcile source git home-kubernetes
flux reconcile kustomization cluster-networking-traefik --with-source
flux reconcile kustomization cluster-networking-authelia --with-source
```

If Authelia v4.37 refuses to start after `git revert` (DB migration issue), restore from backup:

```bash
kubectl scale deployment authelia -n networking --replicas=0
kubectl cp authelia-db-YYYYMMDD-HHMM.sqlite3 \
  networking/$(kubectl get pod -n networking \
    -l app.kubernetes.io/name=authelia \
    -o jsonpath='{.items[0].metadata.name}'):/config/db.sqlite3
kubectl scale deployment authelia -n networking --replicas=1
```

---

### 5.4 — Fix-forward: single OIDC client broken

Do not rollback for this. Edit only the affected client entry.

**Symptom:** One client (e.g. Tailscale) fails with `invalid_client`. Other OIDC clients work.

**Fix:** Add `token_endpoint_auth_method: client_secret_basic` to the failing client:

```yaml
- client_id: tailscale
  client_name: Tailscale
  client_secret: '$plaintext$${SECRET_TAILSCALE_OAUTH_CLIENT_SECRET}'
  token_endpoint_auth_method: client_secret_basic
  ...
```

```bash
git add kubernetes/apps/networking/authelia/app/helm-release.yaml
git commit -m "fix: tailscale token_endpoint_auth_method client_secret_basic"
git push
```

Authelia reconciles within 5 minutes. No downtime.

---

## Rollback Decision Tree

```
Push complete
     │
     ▼
Traefik pod healthy? ──No──► Helm rollback traefik → git revert traefik HR → push
     │
    Yes
     │
     ▼
Authelia pod healthy? ──No──► Patch middleware URL (kubectl, immediate)
     │                         → helm rollback authelia
     │                         → check DB (restore backup if needed)
    Yes                        → git revert authelia HR + middlewares.yaml → push
     │
     ▼
/api/health OK? ──No──► Same as Authelia pod unhealthy above
     │
    Yes
     │
     ▼
ForwardAuth working? ──No──► Check Authelia logs for forwardAuth errors
     │                        If middleware URL wrong: kubectl patch middleware
    Yes
     │
     ▼
OIDC clients working?
  All broken ──► Check hmac_secret path, jwks path in logs → fix-forward
  One broken ──► Add token_endpoint_auth_method to that client → fix-forward
     │
    Yes
     │
     ▼
All post-rollout checks pass → Delete old containo.us CRDs → Done
```

---

## Reference: Key Addresses

| Resource | Address |
|----------|---------|
| Traefik LB | `192.168.5.12` |
| Authelia LB | `192.168.5.11` |
| Traefik dashboard (internal) | `http://localhost:8080` (inside pod) |
| Authelia health | `https://authelia.thekao.cloud/api/health` |
| Authelia forward-auth | `http://authelia.networking.svc.cluster.local/api/authz/forward-auth` |
| Authelia auth-request | `http://authelia.networking.svc.cluster.local/api/authz/auth-request` |
| Traefik metrics | `http://192.168.5.12:8082/metrics` |
| Authelia metrics | `http://192.168.5.11:9959/metrics` |
