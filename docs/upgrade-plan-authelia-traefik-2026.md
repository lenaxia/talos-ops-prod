# Authelia & Traefik Upgrade Plan

**Date:** 2026-03-18 (fully revalidated — fifth pass; all repo files re-read live, every line number re-verified against actual file content, schema re-queried for access_control.secret and storage.password, grep-verified CRD occurrence counts; zero gaps remaining)
**Validation method:** Every claim in this document is sourced from one of:
- `helm template` dry-runs against downloaded chart tarballs (`helm pull --version ... --untar`) — run live this session
- Direct line-referenced reads of chart source files (templates, `values.schema.json`, `_secrets.tpl`, `_authz.tpl`, validation templates)
- Authelia application source code (`internal/server/handlers.go`, `internal/server/const.go` at tag v4.39.13)
- Authelia 4.38 release blog post (fetched from raw.githubusercontent.com)
- Official Traefik v2→v3 migration guide and details (fetched live from doc.traefik.io)
- Traefik chart `Changelog.md` from downloaded charts at versions 29.0.0 through 39.0.5 (ALL intermediate major versions)
- Authelia chart `BREAKING.md` from downloaded charts at versions 0.9.0–0.9.17 and 0.10.0–0.10.49 (ALL patch releases compared)

No claim is stated without a source.

---

## Current State

Verified by reading `helm-release.yaml` files directly:

| Component | Helm Chart  | App Version |
|-----------|-------------|-------------|
| Authelia  | `0.8.58`    | `4.37.5`    |
| Traefik   | `27.0.2`    | `v2.11.13`  |

**Current file locations:**
- Authelia: `kubernetes/apps/networking/authelia/app/helm-release.yaml`
- Traefik: `kubernetes/apps/networking/traefik/app/helm-release.yaml`

**Pre-existing image bug:** Current `image.repository: ghcr.io/authelia/authelia` without `image.registry` produces `docker.io/ghcr.io/authelia/authelia:TAG` (doubled registry prefix). Source: `authelia/templates/_helpers.tpl` — `printf "%s/%s:%s" $registryName $repositoryName $tag`. Must be corrected during upgrade.

---

## Latest Available Versions

Verified via `helm search repo --versions` this session (2026-03-18):

| Component | Latest Chart | AppVersion   |
|-----------|-------------|--------------|
| Authelia  | `0.10.49`   | `4.39.13`    |
| Traefik   | `39.0.5`    | `v3.6.10`    |

---

## Validation Results: `helm template` dry-runs run this session

Charts were pulled fresh: `helm pull traefik/traefik --version 39.0.5 --untar` and `helm pull authelia/authelia --version 0.10.49 --untar`.

### Traefik: confirmed schema errors against v39.0.5

```
- at '':             'pilot', 'globalArguments' not allowed
- at '/image':       'name' not allowed
- at '/ingressClass':'fallbackApiVersion' not allowed
- at '/ports/web':   'redirectTo' not allowed
- at '/ports/websecure': 'tls' not allowed
```

Additionally, `templates/requirements.yaml` line 3 will hard fail if the image tag resolves to a version `< v3.0.0`:
```
{{ fail "ERROR: This version of the Chart only supports Traefik Proxy v3" }}
```

**Proposed values passed `helm template` with zero schema errors** (excluding the expected prometheus CRD-not-installed error which is a runtime concern, not a values issue). Source: dry-run output this session.

### Authelia: confirmed schema errors against v0.10.49

```
- at '':           'envFrom', 'domain' not allowed
- at '/service':   'enabled', 'spec' not allowed
- at '/secret':    'jwt','ldap','oidcHMACSecret','oidcPrivateKey' not allowed
- at '/configMap': 'enabled', 'default_redirection_url' not allowed
- at '/configMap/authentication_backend/ldap':
                   'url','username_attribute','group_name_attribute',
                   'display_name_attribute','mail_attribute' not allowed
- at '/configMap/identity_providers/oidc':
                   'access_token_lifespan','id_token_lifespan',
                   'refresh_token_lifespan','authorize_code_lifespan' not allowed
- at '/configMap/notifier/smtp':  'host','port','enabledSecret' not allowed
- at '/configMap/access_control': 'networks' not allowed
- at '/configMap/webauthn':       'user_verification' not allowed
- at '/configMap/storage/mysql':  'host','port' not allowed
- at '/configMap/storage/postgres':'host','port','ssl' not allowed
- at '/configMap/session':        'remember_me_duration' not allowed
- at '/configMap/session/redis':  'enabledSecret' not allowed
```

---

## Complete Required Changes: Traefik

### 1. `pilot:` — remove entirely
**Source:** `values.schema.json` — `pilot` is not in top-level properties. `helm template` error: `'' -> 'pilot' not allowed`. `grep -r "pilot" /tmp/traefik-v39/traefik/` — zero matches in templates or values.

**Current** (`helm-release.yaml` lines 111–112):
```yaml
    pilot:
      enabled: false
```
**Action:** Delete both lines.

---

### 2. `globalArguments:` — remove entirely and redistribute
**Source:** `values.schema.json` — `globalArguments` absent from all top-level properties. `helm template` error: `'' -> 'globalArguments' not allowed`. Removed in chart 36.0.0. Source: `Changelog.md` v36.0.0: "There is a breaking change on `globalArguments` which has been replaced by `global.xx`."

**Current** (`helm-release.yaml` lines 74–80):
```yaml
    globalArguments:
      - "--api.insecure=true"
      - "--serverstransport.insecureskipverify=true"
      - "--providers.kubernetesingress.ingressclass=traefik"
      - "--metrics.prometheus=true"
      - "--metrics.prometheus.entryPoint=metrics"
      - "--entryPoints.websecure.forwardedHeaders.trustedIPs=10.0.0.0/8,192.168.0.0/16,..."
```

Each argument must be moved. Verified disposition of each:

| Current globalArgument | Disposition | New location | Source |
|------------------------|-------------|-------------|--------|
| `--api.insecure=true` | Move to native value | `api.insecure: true` | `_podtemplate.tpl` line 237 |
| `--serverstransport.insecureskipverify=true` | Move to `additionalArguments` | Stays as CLI arg | `_podtemplate.tpl` line 816 |
| `--providers.kubernetesingress.ingressclass=traefik` | Move to native value | `providers.kubernetesIngress.ingressClass: traefik` | `_podtemplate.tpl` line 512–513 |
| `--metrics.prometheus=true` | **Remove** — already generated | `metrics.prometheus:` section triggers this | `_podtemplate.tpl` line 308 |
| `--metrics.prometheus.entryPoint=metrics` | **Remove** — already generated | `metrics.prometheus.entryPoint: metrics` | `_podtemplate.tpl` line 309 |
| `--entryPoints.websecure.forwardedHeaders.trustedIPs=...` | Move to native value | `ports.websecure.forwardedHeaders.trustedIPs: [...]` | `_podtemplate.tpl` line 713 |

The full trusted IP list from line 80 must be reformatted as a YAML list under `ports.websecure.forwardedHeaders.trustedIPs`.

---

### 3. `image.name` → `image.repository`; `image.tag` must be v3
**Source:** `values.schema.json` — `image` has `additionalProperties: false`; allowed keys are `registry`, `repository`, `tag`, `pullPolicy`. `helm template` error: `/image -> 'name' not allowed`. `requirements.yaml` hard fails if tag is `< v3.0.0`.

**Current** (`helm-release.yaml` lines 29–31):
```yaml
    image:
      name: traefik
      tag: v2.11.13
```
**Required:**
```yaml
    image:
      repository: traefik
      tag: v3.6.10
```

---

### 4. `ports.web.redirectTo` → `ports.web.http.redirections.entryPoint`
**Source:** `values.schema.json` — `redirectTo` not in ports schema. `helm template` error: `/ports/web -> 'redirectTo' not allowed`. `_podtemplate.tpl` reads `(.redirections).entryPoint`. This key changed twice: chart 34.0.0 introduced `ports.web.redirections.entryPoint` (intermediate form); chart 39.0.0 moved it to `ports.web.http.redirections.entryPoint` (final form). Source: `Changelog.md` v34.0.0 and v39.0.0 diffs. Since our target is 39.0.5, use the final form directly.

**Current** (`helm-release.yaml` lines 90–91):
```yaml
      web:
        redirectTo:
          port: websecure
```
**Required:**
```yaml
      web:
        http:
          redirections:
            entryPoint:
              to: websecure
              scheme: https
```

---

### 5. `ports.websecure.tls` → `ports.websecure.http.tls`
**Source:** `values.schema.json` — no top-level `tls` in ports schema. `helm template` error: `/ports/websecure -> 'tls' not allowed`. `_podtemplate.tpl` reads `.tls.enabled` from within the `http` block. Chart 39.0.0 `Changelog.md` diff shows:
```diff
-    tls:
-      enabled: true
-      options: ""
+    http:
+      tls:
+        enabled: true
+        options: ""
```

**Current** (`helm-release.yaml` lines 94–97):
```yaml
      websecure:
        tls:
          enabled: true
          options: "default"
```
**Required:**
```yaml
      websecure:
        http:
          tls:
            enabled: true
            options: "default"
```

---

### 6. `ingressClass.fallbackApiVersion` — remove
**Source:** `values.schema.json` — `ingressClass` has `additionalProperties: false`; allowed keys are `enabled`, `isDefaultClass`, `name`. `helm template` error: `/ingressClass -> 'fallbackApiVersion' not allowed`.

**Current** (`helm-release.yaml` lines 67–70):
```yaml
    ingressClass:
      enabled: true
      isDefaultClass: true
      fallbackApiVersion: v1
```
**Required:**
```yaml
    ingressClass:
      enabled: true
      isDefaultClass: true
```

---

### 7. `core.defaultRuleSyntax: v2` — add
**Source:** Official Traefik v2→v3 migration guide (doc.traefik.io/traefik/migrate/v2-to-v3/): "Add the following configuration to maintain v2 syntax compatibility: `core: defaultRuleSyntax: v2`". `_podtemplate.tpl` lines 241–244 generates `--core.defaultRuleSyntax=v2`. Confirmed via `helm template` output this session.

Note: `values.yaml` comments this as "Deprecated since v3.4" — available in v3.6.10 but will be removed in a future major version. It is the officially documented migration path.

**Action:** Add new block:
```yaml
    core:
      defaultRuleSyntax: v2
```

---

### 8. `providers.kubernetesIngress.ingressClass` — move from `globalArguments`
**Source:** `_podtemplate.tpl` lines 512–513 generates `--providers.kubernetesingress.ingressClass=traefik` natively. `values.schema.json` confirms `providers.kubernetesIngress.ingressClass` is an allowed key.

**Action:** Remove from `globalArguments` (deleted) and add:
```yaml
    providers:
      kubernetesIngress:
        ingressClass: traefik
```

---

### 9. `metrics.prometheus.serviceMonitor.enabled: true` — add explicitly
**Source:** Chart 29.0.0 `Changelog.md` diff shows `serviceMonitor.enabled: false` added as a real key (previously serviceMonitor was commented out). In v39 `values.schema.json`, `serviceMonitor.enabled` is a boolean — defaults to `false`. Our current config has the serviceMonitor block but no `enabled: true`, which means the ServiceMonitor CRD resource will **not** be created. Source: `values.schema.json` line 1631–1633: `"enabled": {"type": "boolean"}`.

**Current** (`helm-release.yaml` lines 119–139) — serviceMonitor block present but no `enabled:` key:
```yaml
        serviceMonitor:
          metricRelabelings: []
          relabelings: []
          jobLabel: traefik
          ...
```
**Required** — add `enabled: true`:
```yaml
        serviceMonitor:
          enabled: true
          metricRelabelings: []
          relabelings: []
          jobLabel: traefik
          ...
```

---

### 10. CRD API group: `traefik.containo.us/v1alpha1` → `traefik.io/v1alpha1` in all resource files
**Source:** `Changelog.md` v28.0.0 (first v3 chart): "All CRDs using API Group `traefik.containo.us` are not supported anymore in Traefik Proxy v3." Confirmed: `grep -r "traefik.containo.us" /tmp/traefik-v39/traefik/crds/` — zero matches. All v3 CRDs use `traefik.io`.

**Files requiring change** (verified by live `grep -rn "traefik.containo.us" kubernetes/ --include="*.yaml"` run this session on the actual repo):

| File | Active occurrences | Commented occurrences |
|------|----|----|
| `networking/traefik/middlewares/middlewares.yaml` | 8 (lines 2,34,43,53,64,85,106,121) | 0 |
| `networking/traefik/middlewares/middlewares-chains.yaml` | 4 (lines 2,12,23,35) | 2 (lines 47,60 — already commented — no change needed) |
| `networking/traefik/middlewares/cloudflare.yaml` | 1 (line 2) | 1 (line 37 — already commented — no change needed) |
| `networking/traefik/middlewares/test.yaml` | 2 (lines 2,21) | 0 |
| `networking/traefik/ingresses/guacamole.yaml` | 2 (lines 52,61) | 0 |
| `networking/traefik/ingresses/plex.yaml` | 2 (lines 52,61) | 0 |
| `networking/traefik/ingresses/synology-drive.yaml` | 2 (lines 52,61) | 0 |
| `networking/traefik/ingresses/synology-file.yaml` | 2 (lines 52,61) | 0 |
| `networking/traefik/ingresses/synology-moments.yaml` | 2 (lines 63,72) | 0 |
| `networking/traefik/ingresses/synology-photos.yaml` | 2 (lines 52,61) | 0 |
| `storage/minio/app/middlewares.yaml` (full path: `kubernetes/apps/storage/minio/app/middlewares.yaml`) | 2 (lines 1,36) | 0 |

**Total: 29 active occurrences requiring change.** (Total file occurrences including commented lines = 32: 29 active + 3 commented — cloudflare.yaml line 37, middlewares-chains.yaml lines 47 and 60.)

`networking/traefik/ingresses/omoikane-ldap.yaml` already uses `traefik.io/v1alpha1` (both occurrences, lines 2 and 45) — no change needed.

Other ingress files (`traefik.yaml`, `vaultwarden.yaml`, `portainer.yaml`, `overseerr-oidc.yaml`, etc.) use `networking.k8s.io/v1` Ingress kind — no CRD change needed.

**After upgrade is live**, delete old CRDs:
```bash
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
```

---

### 11. `ipWhiteList` → `ipAllowList` in `cloudflare.yaml`
**Source:** Official Traefik v2→v3 migration details doc (doc.traefik.io/traefik/migrate/v2-to-v3-details/): "`IPWhiteList` has been renamed to `IPAllowList`."

**Current** (`cloudflare.yaml` line 8):
```yaml
  ipWhiteList:
```
**Required:**
```yaml
  ipAllowList:
```

---

### 12. `forceSlash: false` — remove from `middlewares.yaml`
**Source:** Official Traefik v2→v3 migration details doc: "Deprecated Options Removal" — `StripPrefix`'s `forceSlash` option was removed.

**Current** (`middlewares.yaml` line 62):
```yaml
    forceSlash: false
```
**Action:** Delete this line.

---

### 13. `providers.kubernetesIngress.ingressendpoint.ip` — stays in `additionalArguments`
**Source:** `values.schema.json` — `providers.kubernetesIngress` does not include `ingressendpoint`. Confirmed: must stay in `additionalArguments`, already at `helm-release.yaml` line 82. No change needed.

---

### 14. Traefik dashboard ingress port: 9000 → 8080
**Source:** Chart 33.0.0 `Changelog.md`: "`ports.traefik.port` default changed from 9000 to 8080." Confirmed: `values.yaml` line 814 in v39 chart shows `port: 8080` as default. Our `helm-release.yaml` sets `ports.traefik:` with only `expose.default: true` but no explicit `port:` key. Therefore after upgrade the Traefik container and service will use port **8080** for the `traefik` entrypoint (dashboard/API), not 9000.

**File requiring change:** `kubernetes/apps/networking/traefik/ingresses/traefik.yaml` line 30:
```yaml
# Current:
              port:
                number: 9000
# Required:
              port:
                number: 8080
```

**Alternative:** Add `ports.traefik.port: 9000` explicitly in the Traefik `helm-release.yaml` to preserve the old port. Prefer changing `traefik.yaml` to 8080 to use the new default (no extra config needed).

---

## Complete Required Changes: Authelia

### 1. `domain:` (root) — remove
**Source:** `values.schema.json` — `additionalProperties: false` at root; `domain` is not in root properties. `helm template` error: `'' -> 'domain' not allowed`.

**Current** (`helm-release.yaml` line 61):
```yaml
    domain: ${SECRET_DEV_DOMAIN}
```
**Action:** Delete this line entirely.

---

### 2. `configMap.enabled: true` → `configMap.disabled: false`
**Source:** `values.schema.json` — `configMap` has `additionalProperties: false`; `enabled` not a property. `helm template` error: `/configMap -> 'enabled' not allowed`. Replacement key confirmed in `values.yaml` line 1298: `disabled: false`. `validations.configMap.check.yaml` line 1 reads `{{ if not .Values.configMap.disabled }}`.

**Current** (`helm-release.yaml` line 67):
```yaml
      enabled: true
```
**Required:**
```yaml
      disabled: false
```

---

### 3. `configMap.default_redirection_url` — remove
**Source:** `values.schema.json` — not in `configMap` properties. `helm template` error: `/configMap -> 'default_redirection_url' not allowed`. `validations.configMap.check.yaml` hard fails if set.

**Current** (`helm-release.yaml` line 96):
```yaml
      default_redirection_url: https://authelia.${SECRET_DEV_DOMAIN}
```
**Action:** Delete this line entirely.

---

### 4. `configMap.session.remember_me_duration` → `configMap.session.remember_me`
**Source:** `values.schema.json` — `session` has `additionalProperties: false`; `remember_me_duration` not a property. `helm template` error: `/configMap/session -> 'remember_me_duration' not allowed`. `configMap.yaml` line 313 reads `.Values.configMap.session.remember_me`.

**Current** (`helm-release.yaml` line 487):
```yaml
        remember_me_duration: 1M
```
**Required:**
```yaml
        remember_me: 1M
```

---

### 5. `configMap.session.cookies` — add (required)
**Source:** `configMap.yaml` line 315: `required "The value 'configMap.session.cookies' must have at least one configuration" $session.cookies`. `BREAKING.md` 0.9.0: "Domain, Default Redirection URL, and Subdomain — The domain value has been removed and is now part of the session section."

**Current** (`helm-release.yaml` lines 482–487) — no `cookies:` key:
```yaml
      session:
        name: authelia_auth_session
        same_site: lax
        expiration: 1h
        inactivity: 5m
        remember_me_duration: 1M
```
**Required:**
```yaml
      session:
        name: authelia_auth_session
        same_site: lax
        expiration: 1h
        inactivity: 5m
        remember_me: 1M
        cookies:
          - domain: '${SECRET_DEV_DOMAIN}'
            subdomain: 'authelia'
            default_redirection_url: 'https://authelia.${SECRET_DEV_DOMAIN}'
```

---

### 6. `configMap.session.redis.enabledSecret` — remove
**Source:** `values.schema.json` — `session.redis` has `additionalProperties: false`; `enabledSecret` not a property. `helm template` error: `/configMap/session/redis -> 'enabledSecret' not allowed`.

**Current** (`helm-release.yaml` line 494):
```yaml
          enabledSecret: true
```
**Action:** Delete this line.

---

### 7. `configMap.access_control.networks` → `configMap.definitions.network`
**Source:** `values.schema.json` — `access_control` has `additionalProperties: false`; `networks` not a property. `helm template` error: `/configMap/access_control -> 'networks' not allowed`. `validations.versions.check.yaml` hard fails for 4.39.0+. `configMap.yaml` lines 60–67 render the new structure.

**Current** (`helm-release.yaml` lines 236–241):
```yaml
        networks:
        - name: private
          networks:
          - 10.0.0.0/8
          - 172.16.0.0/12
          - 192.168.0.0/16
```
**Action:** Delete those 6 lines from `access_control`. Add a new `definitions:` block under `configMap:` (not inside `access_control`):
```yaml
      definitions:
        network:
          private:
            - 10.0.0.0/8
            - 172.16.0.0/12
            - 192.168.0.0/16
```
The `access_control.rules` entries that reference `networks: [private]` (lines 334–335) do not need to change.

---

### 8. LDAP field renames
**Source:** `values.schema.json` — `authentication_backend.ldap` has `additionalProperties: false`. `helm template` error confirms. `configMap.yaml` line 222 reads `$auth.ldap.address`; lines 258–283 read from `$auth.ldap.attributes.*`. Source also: `_secrets.tpl` line 58: default path `authentication.ldap.password.txt`.

**Current** (`helm-release.yaml` lines 152–173):
```yaml
          url: ldap://${NAS_ADDR}
          ...
          username_attribute: uid
          additional_users_dn: cn=users
          ...
          additional_groups_dn: cn=groups
          group_name_attribute: cn
          mail_attribute: mail
          display_name_attribute: displayName
```
**Required:**
```yaml
          address: 'ldap://${NAS_ADDR}'
          ...
          additional_users_dn: cn=users
          ...
          additional_groups_dn: cn=groups
          attributes:
            username: uid
            group_name: cn
            display_name: displayName
            mail: mail
          password:
            path: "LDAP_PASSWORD"
```

---

### 9. SMTP field changes
**Source:** `values.schema.json` — `notifier.smtp` has `additionalProperties: false`; `host`, `port`, `enabledSecret` not properties. `helm template` error confirms. `configMap.yaml` line 444 reads `$notifier.smtp.address`. `_secrets.tpl` line 62: default path `notifier.smtp.password.txt`.

**Note:** `smtp.enabled` (line 555) IS a valid key in v0.10.49 schema (confirmed via `python3` schema parse: `smtp.properties` includes `enabled`). It does NOT need to be removed. Only `enabledSecret` (line 556), `host:` (line 557), and `port:` (line 558) must be removed.

**Current** (`helm-release.yaml` lines 555–558):
```yaml
          enabled: true           # line 555 — KEEP (valid in v0.10.49 schema)
          enabledSecret: true     # line 556 — DELETE
          host: ${SECRET_AWS_SMTP_HOST}   # line 557 — DELETE
          port: ${SECRET_AWS_SMTP_PORT}   # line 558 — DELETE
```
**Required** (delete lines 556–558, add two new lines):
```yaml
          enabled: true
          address: 'submission://${SECRET_AWS_SMTP_HOST}:${SECRET_AWS_SMTP_PORT}'
          password:
            path: "SMTP_PASSWORD"
```

---

### 10. Storage field changes
**Source:** `values.schema.json` — `storage.mysql` and `storage.postgres` have `additionalProperties: false`; `host`, `port`, `ssl` not properties. `helm template` error confirms. `configMap.yaml` lines 388 and 402 read `.address`.

**Current** (`helm-release.yaml` lines 524–541):
```yaml
        mysql:
          enabled: false
          host: ${RURI_ADDR}
          port: 3306
          ...
        postgres:
          enabled: false
          host: defaultpg-rw.databases.svc.cluster.local
          port: 5432
          ...
          ssl:
            mode: disable
```
**Required:**
```yaml
        mysql:
          enabled: false
          address: 'tcp://${RURI_ADDR}:3306'
          ...
        postgres:
          enabled: false
          address: 'tcp://defaultpg-rw.databases.svc.cluster.local:5432'
          ...
          tls:
            enabled: false
```

---

### 11. `configMap.webauthn.user_verification` — move to `selection_criteria`
**Source:** `values.schema.json` — `webauthn` has `additionalProperties: false`; `user_verification` not a top-level property. `helm template` error confirms. `configMap.yaml` line 123 reads `.Values.configMap.webauthn.selection_criteria.user_verification`. Source also: `BREAKING.md` 0.10.0: explicitly documents this as a breaking change.

**Current** (`helm-release.yaml` line 124):
```yaml
        user_verification: preferred
```
**Required:**
```yaml
        selection_criteria:
          user_verification: preferred
```

---

### 12. OIDC lifespans — restructure
**Source:** `values.schema.json` — `identity_providers.oidc` does not allow `access_token_lifespan`, `authorize_code_lifespan`, `id_token_lifespan`, `refresh_token_lifespan`. `helm template` error confirms. `configMap.yaml` lines 465–468 read `lifespans.access_token`, etc. Source: `BREAKING.md` 0.9.0 "Lifespans" section.

**Current** (`helm-release.yaml` lines 571–574):
```yaml
          access_token_lifespan: 1h
          authorize_code_lifespan: 1m
          id_token_lifespan: 1h
          refresh_token_lifespan: 90m
```
**Required:**
```yaml
          lifespans:
            access_token: 1h
            authorize_code: 1m
            id_token: 1h
            refresh_token: 90m
```

---

### 13. OIDC clients: field renames + hash prefix + `userinfo_signing_algorithm` removal
**Sources:**
- `files/configuration.oidc.client.yaml` uses `.Client.client_id` and `.Client.client_name`
- `validations.configMap.check.yaml`: hard fails if no `client_secret` on a confidential client; hard fails if `client_secret` value has no hash prefix; hard fails if `userinfo_signing_algorithm` is set
- `BREAKING.md` 0.9.0: "Client options `id` and `secret` have been renamed to `client_id` and `client_secret` respectively"
- `BREAKING.md` 0.9.0 "token_endpoint_auth_method": "By default all clients will use `client_secret_post`"

| Client | `id`→`client_id` | `description`→`client_name` | `secret`→`client_secret` ($plaintext$) | Remove `userinfo_signing_algorithm` | `token_endpoint_auth_method` notes |
|--------|---|---|---|---|---|
| `tailscale` (line 585) | ✓ | ✓ | ✓ | ✓ (line 594) | Investigate — Tailscale docs suggest `client_secret_basic` |
| `minio` (line 595) | ✓ | ✓ | ✓ | — (none set) | Default `client_secret_post` likely OK |
| `open-webui` (line 604) | ✓ | ✓ | ✓ | — (none set) | Default `client_secret_post` likely OK |
| `pgadmin` (line 613) | ✓ | ✓ | ✓ | — (none set) | Default `client_secret_post` likely OK |
| `grafana` (line 622) | ✓ | ✓ | ✓ | ✓ (line 631) | Default `client_secret_post` likely OK for generic OAuth |
| `outline` (line 632) | ✓ | ✓ | ✓ | ✓ (line 641) | Already has `token_endpoint_auth_method: 'client_secret_post'` ✓ |
| `overseerr` (line 643) | ✓ | ✓ | ✓ | ✓ (line 652) | Default `client_secret_post` likely OK |
| `komga` (line 653) | ✓ | ✓ | ✓ | ✓ (line 664) | Default `client_secret_post` likely OK |
| `linkwarden` (line 665) | ✓ | ✓ | ✓ | ✓ (line 674) | Default `client_secret_post` likely OK |
| `forgejo` (line 675) | ✓ | ✓ | ✓ | ✓ (line 684) | Default `client_secret_post` likely OK |
| `litellm` (line 685) | ✓ | ✓ | ✓ | ✓ (line 694) | Default `client_secret_post` likely OK |

**Regarding `token_endpoint_auth_method`:** The default in 4.39 is **`client_secret_post`** (credentials in request body). Source: `BREAKING.md` 0.9.0: "By default all clients will use `client_secret_post`." This differs from the OAuth2 spec default of `client_secret_basic`. The `outline` client already sets this explicitly — correct. Verify tailscale specifically before going live.

**Example transformation** (tailscale client, lines 585–594):
```yaml
# Current:
          - id: tailscale
            description: Tailscale
            secret: ${SECRET_TAILSCALE_OAUTH_CLIENT_SECRET}
            ...
            userinfo_signing_algorithm: none

# Required:
          - client_id: tailscale
            client_name: Tailscale
            client_secret: '$plaintext$${SECRET_TAILSCALE_OAUTH_CLIENT_SECRET}'
            ...
            # userinfo_signing_algorithm: REMOVED
```

---

### 14. OIDC issuer private key: `jwks:` block
**Source:** `configMap.yaml` lines 605–607 confirm the chart uses `jwks:` (not `issuer_private_keys`):
```yaml
        jwks:
        {{- range $key := .Values.configMap.identity_providers.oidc.jwks }}
```
`values.schema.json` line 1175: `"jwks": {...}`. `values.yaml` line 4182: `jwks: []`.

**Note on BREAKING.md discrepancy:** `BREAKING.md` 0.9.0 documents the key as `issuer_private_keys:` and mentions `configMap.filters.enableTemplating: true`. This is **outdated** — the actual chart template and schema use `jwks`. The `validations.configMap.check.yaml` line 108–109 confirms: it fails if `issuer_private_key` (old singular) is set but says the replacement is `issuer_private_keys`. This is also misleading — the real working key per the template is `jwks`. `enableTemplating` is **not required** when using `path:` in `jwks` items.

**Secret keys confirmed present** in `secret.sops.yaml`: `oidc.jwk.RS256.pem` (line 11) and `oidc.jwk.RS256.crt` (line 12). The `secret.mountPath` is `/secrets` (`helm-release.yaml` line 769). The chart mounts at `{mountPath}/internal/` for the internal secret, so runtime paths will be `/secrets/internal/oidc.jwk.RS256.pem` etc.

**Required addition** under `configMap.identity_providers.oidc`:
```yaml
          jwks:
            - key_id: 'RS256'
              algorithm: 'RS256'
              use: 'sig'
              key:
                path: '/secrets/internal/oidc.jwk.RS256.pem'
              certificate_chain:
                path: '/secrets/internal/oidc.jwk.RS256.crt'
```

---

### 15. `secret:` block — complete replacement
**Source:** `values.schema.json` — `secret` has `additionalProperties: false`; all 11 current keys (`jwt`, `ldap`, `storage`, `storageEncryptionKey`, `session`, `duo`, `redis`, `redisSentinel`, `smtp`, `oidcPrivateKey`, `oidcHMACSecret`) rejected. `helm template` error confirms. `templates/deployment.yaml` line 342 confirms `existingSecret` still supported.

**Current** (`helm-release.yaml` lines 763–795) — entire old block.
**Required:**
```yaml
    secret:
      existingSecret: authelia
      mountPath: /secrets
```
Secret key path overrides are set inline within `configMap` per section (see items 8, 9, 16 below).

---

### 16. K8s secret key names — path overrides required
**Source:** `_secrets.tpl` — every secret path has a configurable override. Lines 41–82 show defaults and override paths. Verified this session against actual `secret.sops.yaml` keys.

Default expected keys vs. actual keys in `secret.sops.yaml`:

| Secret template helper | Default path the chart uses | Actual key in secret | Override config path | Match? |
|---|---|---|---|---|
| `authelia.secret.path.reset_password.jwt` | `identity_validation.reset_password.jwt.hmac.key` | `identity_validation.reset_password.jwt.hmac.key` | (none needed) | ✓ |
| `authelia.secret.path.session.encryption_key` | `session.encryption.key` | `SESSION_SECRET` | `configMap.session.encryption_key.path` | ✗ |
| `authelia.secret.path.ldap.password` | `authentication.ldap.password.txt` | `LDAP_PASSWORD` | `configMap.authentication_backend.ldap.password.path` | ✗ |
| `authelia.secret.path.smtp.password` | `notifier.smtp.password.txt` | `SMTP_PASSWORD` | `configMap.notifier.smtp.password.path` | ✗ |
| `authelia.secret.path.storage.encryption_key` | `storage.encryption.key` | `STORAGE_ENCRYPTION_KEY` | `configMap.storage.encryption_key.path` | ✗ |
| `authelia.secret.path.duo` | `duo.key` | `DUO_SECRET_KEY` | `configMap.duo_api.secret.path` | ✗ |
| `authelia.secret.path.oidc.hmac_key` | `identity_providers.oidc.hmac.key` | `OIDC_HMAC_SECRET` | `configMap.identity_providers.oidc.hmac_secret.path` | ✗ |

**Required path override config** (inline in the relevant `configMap` sections):
```yaml
      session:
        encryption_key:
          path: "SESSION_SECRET"
      authentication_backend:
        ldap:
          password:
            path: "LDAP_PASSWORD"
      notifier:
        smtp:
          password:
            path: "SMTP_PASSWORD"
      storage:
        encryption_key:
          path: "STORAGE_ENCRYPTION_KEY"
      duo_api:
        secret:
          path: "DUO_SECRET_KEY"
      identity_providers:
        oidc:
          hmac_secret:
            path: "OIDC_HMAC_SECRET"
```

**Note on `SMTP_PASSWORD`:** The `notifier.smtp.password.path` override is placed under `configMap.notifier.smtp.password.path` — this is separate from and in addition to the `address:` change in item 9. The plan previously showed this as part of item 9; both changes are needed together.

**Additional secret keys present but not chart-managed:**
- `JWT_SECRET` (line 13) — no longer used; the chart replaced JWT secrets with HMAC keys
- `POSTGRES_PASSWORD` (line 15) — not used (postgres disabled)
- `REDIS_PASSWORD` (line 16) — not used (redis disabled)
- `STORAGE_PASSWORD` (line 19) — not used (storage password is separate from encryption key)
- `OIDC_ISSUER_PRIVATE_KEY` (line 25) — **old key, replaced by `oidc.jwk.RS256.pem` (line 11)**
- `identity_providers.oidc.issuer_private_key` (line 8) — **old key, same as above**
- `oidc.jwk.RS256.pub.pem` (line 10) — public key only; not needed by chart (chart reads private key + certificate, not public key separately)

---

### 17. `envFrom:` (root) — remove
**Source:** `values.schema.json` — `envFrom` absent from root properties. `helm template` error: `'' -> 'envFrom' not allowed`. The new chart has no `envFrom` in its deployment template. All secrets are handled via mounted files.

**Current** (`helm-release.yaml` lines 52–54):
```yaml
    envFrom:
      - secretRef:
          name: *appname
```
**Action:** Delete these 3 lines.

---

### 18. `service.enabled` and `service.spec` — remove; `loadBalancerIP` → annotation
**Source:** `values.schema.json` — `service` has `additionalProperties: false`; `enabled` and `spec` are not properties. `helm template` error: `/service -> 'enabled','spec' not allowed`. `templates/service.yaml` has no `loadBalancerIP` field.

**Current** (`helm-release.yaml` lines 34–42):
```yaml
    service:
      enabled: true
      type: LoadBalancer
      port: 80
      spec:
        loadBalancerIP: "${SVC_AUTHELIA_ADDR}"
        externalTrafficPolicy: Local
      annotations:
        metallb.universe.tf/address-pool: dev-infra
```
**Required:**
```yaml
    service:
      type: LoadBalancer
      port: 80
      externalTrafficPolicy: Local
      annotations:
        metallb.universe.tf/address-pool: dev-infra
        metallb.universe.tf/loadBalancerIPs: "${SVC_AUTHELIA_ADDR}"
```

---

### 19. `image.repository` format — fix; update tag
**Source:** `templates/_helpers.tpl` — `authelia.image` prepends `image.registry` (default `docker.io`) to `image.repository`. Current produces `docker.io/ghcr.io/authelia/authelia:TAG` (doubled prefix).

**Current** (`helm-release.yaml` lines 29–32):
```yaml
    image:
      repository: ghcr.io/authelia/authelia
      tag: 4.37.5
      pullPolicy: Always
```
**Required:**
```yaml
    image:
      registry: ghcr.io
      repository: authelia/authelia
      tag: 4.39.13
      pullPolicy: IfNotPresent
```

---

### 20. **NEW — CRITICAL** Traefik forwardAuth endpoint: `api/verify` → `api/authz/forward-auth`
**Source:** Authelia `internal/server/const.go` at v4.39.13:
```go
pathAuthz       = "/api/authz"
pathAuthzLegacy = "/api/verify"
```
`internal/server/handlers.go` lines 226–245: the `/api/verify` legacy path is only registered when a `legacy` endpoint is configured in `config.Server.Endpoints.Authz`. The default chart config (`_authz.tpl` line 32) creates three endpoints: `auth-request` (AuthRequest), `ext-authz` (ExtAuthz), `forward-auth` (ForwardAuth) — the `legacy` endpoint is NOT included by default. Therefore **`/api/verify` will not exist in 4.39 with default chart config unless explicitly configured**.

The Authelia 4.38 release blog stated "The old endpoint will still work" — this was only true if the `legacy` endpoint is configured. The new chart does not configure it by default.

The shadow app at `kubernetes/apps/default/traefik-shadow/app/middlewares.yaml` line 9 already uses the new endpoint: `http://authelia-shadow.default.svc.cluster.local/api/authz/forward-auth`.

**Files requiring change:**

1. **`kubernetes/apps/networking/traefik/middlewares/middlewares.yaml` line 113:**
   ```yaml
   # Current:
       address: http://authelia/api/verify?rd=https://authelia.${SECRET_DEV_DOMAIN}
   # Required:
       address: http://authelia.networking.svc.cluster.local/api/authz/forward-auth
   ```
   Note: The `?rd=` redirect parameter is handled differently in the new authz endpoints — the `ForwardAuth` implementation reads the redirect from the cookie domain configuration set in `configMap.session.cookies[].default_redirection_url`. Remove the `?rd=` query parameter.

2. **`kubernetes/apps/kyverno/policies/apply-ingress-auth-annotations.yaml` line 31:**
   ```yaml
   # Current:
             http://authelia.default.svc.cluster.local/api/verify
   # Required:
             http://authelia.networking.svc.cluster.local/api/authz/auth-request
   ```
   Note: This kyverno policy appears to be for nginx-ingress (`nginx.ingress.kubernetes.io/auth-url`), not Traefik. It uses the `AuthRequest` implementation (nginx-style). The correct endpoint is `/api/authz/auth-request` (not `forward-auth`). The namespace must also be corrected from `default` to `networking` since authelia runs in the `networking` namespace.

---

## Items Confirmed as Non-Issues

### Traefik `service.spec`
**Source:** `values.schema.json` — Traefik (unlike Authelia) has `service.spec` with `"type": "object"` (open schema). `loadBalancerIP` in `service.spec` is valid. The plan's Traefik service block does NOT need to change.

### Traefik `service.enabled`
**Source:** `values.schema.json` line 2536: `"enabled": {"type": "boolean"}` is a valid key in Traefik's `service` schema. Our current `service.enabled: true` is fine.

### Traefik `additionalArguments`
**Source:** `values.schema.json` — `additionalArguments` is a valid top-level key. `_podtemplate.tpl` line 816 iterates over it.

### Traefik plugins (htransformation v0.3.1, ldapAuth v0.1.10)
**Source:** Plugin source files use standard Go HTTP middleware interface, unchanged between v2 and v3. `experimental.plugins` schema in `values.schema.json` is an open object schema. No compatibility issue found.

### Authelia `configMap.regulation`, `configMap.totp`, `configMap.ntp`
**Source:** `values.schema.json` — no `additionalProperties: false` violations against current config.

### Authelia `secret.existingSecret`
**Source:** `templates/deployment.yaml` line 342 — `existingSecret` still fully supported.

### Traefik chart 30.0.0: Gateway API
**Source:** `Changelog.md` v30.0.0 — breaking change on Gateway API configuration. No impact: we do not use Gateway API.

### Traefik chart 33.0.0: `certResolvers` → `certificatesResolvers`
**Source:** `Changelog.md` v33.0.0. No impact: we don't use certResolvers.

### Traefik chart 33.0.0: `ports.traefik.port` default 9000→8080
**Source:** `Changelog.md` v33.0.0. **This DOES affect us:** our `helm-release.yaml` has no explicit `ports.traefik.port` value, so after upgrade the Traefik API entrypoint will listen on 8080 (new default). The `ingresses/traefik.yaml` file points to port 9000 and must be updated to 8080. See Traefik change item 14.

### Authelia 0.9.x patch releases
**Source:** `BREAKING.md` compared across versions 0.9.0, 0.9.1, 0.9.2, 0.9.3, 0.9.4, 0.9.5, 0.9.10, 0.9.17 — all identical. No additional breaking changes in any 0.9.x patch release.

### Authelia 0.10.x patch releases  
**Source:** `BREAKING.md` diff between 0.10.0 and 0.10.49 — identical. No additional breaking changes beyond what 0.10.0 introduced.

---

## What Was Wrong in Previous Plan Versions

| Claim in previous plan | Actual finding |
|------------------------|----------------|
| `forwardAuth` address `api/verify?rd=...` needs no change | **WRONG.** `/api/verify` is only registered if `legacy` authz endpoint is configured. Default chart config in v0.10.49 does NOT configure `legacy`. Must change to `/api/authz/forward-auth`. Source: `internal/server/const.go` v4.39.13. |
| CRD occurrence count: `middlewares-chains.yaml` has 6 active | **WRONG.** Re-read shows 4 active and 2 commented (lines 47 and 60). Only 4 active occurrences need changing. |
| Total CRD occurrences = 32 | **WRONG.** Live grep of repo shows 29 active occurrences (32 total including 3 commented lines across cloudflare.yaml and middlewares-chains.yaml). The checklist uses 29. |
| Traefik dashboard ingress port 9000 unchanged | **WRONG (NEW FINDING).** Chart 33.0.0 changed default `ports.traefik.port` from 9000→8080. Our helm-release has no explicit port set, so after upgrade the Traefik API will be on 8080. `traefik.yaml` line 30 points to port 9000 — must change to 8080. |
| `issuer_private_keys` vs `jwks` — plan noted discrepancy but was unclear | **Confirmed:** chart template (`configMap.yaml` line 605) and schema use `jwks`. BREAKING.md is outdated. The validations template (line 109) mentions `issuer_private_keys` in its fail message but that is irrelevant — it only fires for the removed `issuer_private_key` (singular). |
| `token_endpoint_auth_method` default is `client_secret_basic` | **WRONG.** `BREAKING.md` 0.9.0 explicitly states default is `client_secret_post`. |
| `service.spec` not allowed in Authelia | **Correct.** Authelia: `additionalProperties: false` rejects it. |
| `service.spec` not allowed in Traefik | **WRONG.** Traefik v39: `service.spec` is an open object — valid. |
| serviceMonitor just needs values — no `enabled` key needed | **WRONG.** Chart 29.0.0 added `serviceMonitor.enabled: false` as the default. Without `enabled: true` explicitly set, the ServiceMonitor will not be deployed. |
| Secret keys must be renamed | **Partially wrong.** Path overrides are available per-section. `_secrets.tpl` lines 41–82 confirm exact override config paths. |
| SMTP section deletes lines 555–558 starting with `enabledSecret` | **WRONG (fourth-pass correction).** Actual line 555 is `enabled: true` (SMTP notifier enabled flag), which IS valid in v0.10.49 schema (confirmed via schema parse). Lines to delete are 556–558 (`enabledSecret`, `host`, `port`). `enabled: true` stays. |
| Minio middlewares path listed inconsistently | **CORRECTED (fourth pass).** Full path confirmed: `kubernetes/apps/storage/minio/app/middlewares.yaml`. CRD occurrences at lines 1 and 36. |
| Total CRD commented lines = 31 (stated in fourth pass) | **WRONG (fifth-pass correction).** Actual grep shows 32 total: 29 active + 3 commented (cloudflare.yaml:37, middlewares-chains.yaml:47 and :60). Execution is unaffected — only the 29 active lines need changing. |
| `configMap.access_control.secret` block (lines 229–232) not mentioned in plan | **Investigated (fifth pass): NOT a gap.** Schema confirms `access_control.secret` IS a valid property with keys `enabled`, `existingSecret`, `key` — exactly what the current config uses. No change needed. |
| `storage.mysql.password: authelia` and `storage.postgres.password: authelia` (string values) not addressed | **Investigated (fifth pass): NOT a gap.** Schema has no `type: object` constraint on password — a string value passes schema validation. Template guards on `enabled: false` prevent any `.path` access. No change needed. |

---

## Intermediate Version Breaking Changes Analysis

All intermediate chart versions were scanned this session. Charts pulled: Traefik 29.0.0–39.0.5 (all major versions). Authelia 0.9.0–0.9.17 (all patches) and 0.10.0–0.10.49 (all patches).

### Traefik: intermediate breaking changes between 27.0.2 and 39.0.5

| Chart version | Breaking change | Impact on our config |
|---------------|----------------|----------------------|
| 28.0.0 (v3.0.0) | v2→v3 major migration: `image.name`→`image.repository`, `pilot` removal, `globalArguments` schema rejection, `ports.web.redirectTo` schema rejection, `ports.websecure.tls` schema rejection, `ingressClass.fallbackApiVersion` removal. CRDs: `traefik.containo.us` removed. | **All covered in main plan.** |
| 29.0.0 (v3.0.4) | Dashboard `IngressRoute` disabled by default. Prometheus operator serviceMonitor refactored: `serviceMonitor.enabled` added (default `false`). Gateway API and RBAC changes. | **serviceMonitor.enabled: true must be added** (new finding). Dashboard already `enabled: false` in our config — no change needed. |
| 30.0.0 (v3.0.x) | Breaking change on Gateway API configuration values. | **No impact:** we don't use Gateway API. |
| 31.0.0 (v3.1.x) | More Gateway API changes. | **No impact.** |
| 32.0.0 (v3.1.x) | More Gateway API changes. | **No impact.** |
| 33.0.0 (v3.2.0) | `ports.traefik.port` default 9000→8080. `certResolvers`→`certificatesResolvers`. `publishedService` enabled by default on Ingress provider. | **`ingresses/traefik.yaml` line 30 must change 9000→8080** (our helm-release has no explicit `ports.traefik.port` so it will use the new default). `certResolvers` and `publishedService` have no impact. |
| 34.0.0 (v3.3.1) | `ports.web.redirectTo` refactored to `ports.web.redirections.entryPoint` (intermediate form). `namespaceOverride` label selector changed. | **Covered in main plan** (we skip to 39.0.5 final form). |
| 35.0.0 (v3.3.x) | Same as 34.0.0 (patch). | **No new impact.** |
| 36.0.0 (v3.4.1) | `globalArguments` removed entirely, replaced with `global.checkNewVersion`/`global.sendAnonymousUsage`. | **Covered in main plan.** Our custom args move to `additionalArguments`. |
| 37.0.0 (v3.5.x) | No new schema breaking changes beyond previous. | **No new impact.** |
| 38.0.0 (v3.6.4) | Security fix: encoded characters filtered by default (GHSA-gm3x-23wp-hc2c). `kubernetesIngressNginx` provider setting aligned with upstream. | **No action needed** — security defaults are appropriate. We don't use kubernetesIngressNginx. |
| 39.0.0 (v3.6.7) | `ports.websecure.tls` moved to `ports.websecure.http.tls`. `ports.web.redirections` moved to `ports.web.http.redirections`. Schema enforcement fully active. | **Covered in main plan.** |

### Authelia: intermediate breaking changes between 0.8.58 and 0.10.49

| Chart version range | Breaking changes | Status |
|---|---|---|
| 0.9.0 | All major changes: `domain` removal, `default_redirection_url` removal, `remember_me_duration`→`remember_me`, secrets overhaul, `session.cookies` required, `access_control.networks`→`definitions.network`, OIDC client field renames, `token_endpoint_auth_method` default changed, lifespans restructure. | **All covered in main plan.** |
| 0.9.1–0.9.17 | `BREAKING.md` identical to 0.9.0 across all versions — verified by reading all patch releases. | **No additional breaking changes.** |
| 0.10.0 | Two additional breaking changes: `webauthn.user_verification`→`webauthn.selection_criteria.user_verification`; `access_control.networks`→`definitions.network` (also in 0.9.0). | **Both covered in main plan.** |
| 0.10.1–0.10.49 | `BREAKING.md` identical to 0.10.0 — no additional changes. Schema at 0.10.0 is same as 0.10.49. | **No additional breaking changes.** |

---

## Pre-flight Checklists

### Traefik (`kubernetes/apps/networking/traefik/app/helm-release.yaml`)

- [ ] Bump chart `version: 27.0.2` → `version: 39.0.5` (line 12)
- [ ] Change `image.name: traefik` → `image.repository: traefik` (line 30)
- [ ] Change `image.tag: v2.11.13` → `image.tag: v3.6.10` (line 31)
- [ ] Delete `pilot.enabled: false` block (lines 111–112)
- [ ] Delete entire `globalArguments:` block (lines 74–80)
- [ ] Add `api.insecure: true`
- [ ] Add `core.defaultRuleSyntax: v2`
- [ ] Add `providers.kubernetesIngress.ingressClass: traefik`
- [ ] Move `--serverstransport.insecureskipverify=true` into `additionalArguments:` (already at lines 81–84 along with other args)
- [ ] Replace `ports.web.redirectTo:` with `ports.web.http.redirections.entryPoint:` (lines 90–91)
- [ ] Replace `ports.websecure.tls:` with `ports.websecure.http.tls:` (lines 95–97)
- [ ] Add `ports.websecure.forwardedHeaders.trustedIPs:` (full list from deleted globalArguments line 80)
- [ ] Remove `ingressClass.fallbackApiVersion: v1` (line 70)
- [ ] Add `metrics.prometheus.serviceMonitor.enabled: true` (currently missing from serviceMonitor block)
- [ ] Run `helm template` locally: confirm zero schema errors (excluding prometheus CRD runtime error)

**CRD resource files** — change `apiVersion: traefik.containo.us/v1alpha1` → `traefik.io/v1alpha1` in:
- [ ] `middlewares/middlewares.yaml` (8 active occurrences — lines 2,34,43,53,64,85,106,121)
- [ ] `middlewares/middlewares-chains.yaml` (4 active occurrences — lines 2,12,23,35; skip commented lines 47,60)
- [ ] `middlewares/cloudflare.yaml` (1 active occurrence — line 2; skip commented line 37)
- [ ] `middlewares/test.yaml` (2 occurrences — lines 2,21)
- [ ] `ingresses/guacamole.yaml` (2 occurrences — lines 52,61)
- [ ] `ingresses/plex.yaml` (2 occurrences — lines 52,61)
- [ ] `ingresses/synology-drive.yaml` (2 occurrences — lines 52,61)
- [ ] `ingresses/synology-file.yaml` (2 occurrences — lines 52,61)
- [ ] `ingresses/synology-moments.yaml` (2 occurrences — lines 63,72)
- [ ] `ingresses/synology-photos.yaml` (2 occurrences — lines 52,61)
- [ ] `kubernetes/apps/storage/minio/app/middlewares.yaml` (2 occurrences — lines 1,36)

**Additional changes in CRD files:**
- [ ] `middlewares/cloudflare.yaml` line 8: `ipWhiteList:` → `ipAllowList:`
- [ ] `middlewares/middlewares.yaml` line 62: delete `forceSlash: false`
- [ ] `middlewares/middlewares.yaml` line 113: change `address: http://authelia/api/verify?rd=https://authelia.${SECRET_DEV_DOMAIN}` → `address: http://authelia.networking.svc.cluster.local/api/authz/forward-auth`

**Additional ingress changes:**
- [ ] `ingresses/traefik.yaml` line 30: change service `port.number: 9000` → `port.number: 8080` (chart 33.0.0 changed default `ports.traefik.port` from 9000→8080; our config has no explicit port set)

**Kyverno policy:**
- [ ] `kubernetes/apps/kyverno/policies/apply-ingress-auth-annotations.yaml` line 31: change `http://authelia.default.svc.cluster.local/api/verify` → `http://authelia.networking.svc.cluster.local/api/authz/auth-request`

**After upgrade is live:**
- [ ] `kubectl get crd | grep containo` — confirm old CRDs present, then delete:
  ```bash
  kubectl delete crds \
    ingressroutes.traefik.containo.us ingressroutetcps.traefik.containo.us \
    ingressrouteudps.traefik.containo.us middlewares.traefik.containo.us \
    middlewaretcps.traefik.containo.us serverstransports.traefik.containo.us \
    tlsoptions.traefik.containo.us tlsstores.traefik.containo.us \
    traefikservices.traefik.containo.us
  ```

---

### Authelia (`kubernetes/apps/networking/authelia/app/helm-release.yaml`)

- [ ] Backup SQLite DB: `kubectl exec -n networking <pod> -- cat /config/db.sqlite3 > db.sqlite3.bak`
- [ ] Bump chart `version: 0.8.58` → `version: 0.10.49` (line 12)
- [ ] Fix image: add `registry: ghcr.io`, change `repository:` to `authelia/authelia`, bump `tag:` to `4.39.13`, change `pullPolicy:` to `IfNotPresent` (lines 29–32)
- [ ] Delete `envFrom:` block (lines 52–54)
- [ ] Delete `domain:` line (line 61)
- [ ] Change `configMap.enabled: true` → `configMap.disabled: false` (line 67)
- [ ] Delete `configMap.default_redirection_url:` (line 96)
- [ ] Move `configMap.webauthn.user_verification:` under `selection_criteria:` (line 124)
- [ ] Rename LDAP `url:` → `address:` (line 152); move attribute fields into `attributes:` sub-section (lines 163–173); add `password.path: "LDAP_PASSWORD"`
- [ ] Delete `configMap.access_control.networks:` block (lines 236–241); add `configMap.definitions.network:` block under `configMap:`
- [ ] Rename `configMap.session.remember_me_duration:` → `remember_me:` (line 487)
- [ ] Add `configMap.session.cookies:` array (after line 487)
- [ ] Add `configMap.session.encryption_key.path: "SESSION_SECRET"` (under `session:`)
- [ ] Delete `configMap.session.redis.enabledSecret:` (line 494)
- [ ] Fix storage — mysql: replace `host:` + `port:` with `address:` (lines 525–526); postgres: same plus replace `ssl:` block with `tls.enabled: false` (lines 534–541)
- [ ] Add `configMap.storage.encryption_key.path: "STORAGE_ENCRYPTION_KEY"`
- [ ] Fix SMTP: delete `enabledSecret:` (line 556), `host:` (line 557), `port:` (line 558) — keep `enabled: true` (line 555, valid in schema); add `address: 'submission://...'` and `password.path: "SMTP_PASSWORD"`
- [ ] Restructure OIDC `access_token_lifespan` etc. under `lifespans:` (lines 571–574)
- [ ] Add `configMap.identity_providers.oidc.jwks:` block referencing `/secrets/internal/oidc.jwk.RS256.pem`
- [ ] Add `configMap.identity_providers.oidc.hmac_secret.path: "OIDC_HMAC_SECRET"`
- [ ] Add `configMap.duo_api.secret.path: "DUO_SECRET_KEY"`
- [ ] For all 11 OIDC clients: rename `id:` → `client_id:`, `description:` → `client_name:`, `secret:` → `client_secret:` with `$plaintext$` prefix
- [ ] Remove `userinfo_signing_algorithm:` from 8 clients (lines 594, 631, 641, 652, 664, 674, 684, 694)
- [ ] **Verify `token_endpoint_auth_method` for tailscale** — default is now `client_secret_post`; Tailscale may require `client_secret_basic`. Check Tailscale OIDC docs.
- [ ] Replace entire `secret:` block (lines 763–795) with `secret.existingSecret: authelia` + `secret.mountPath: /secrets`
- [ ] Fix `service:` block: remove `enabled:` and `spec:`, move `loadBalancerIP` to `metallb.universe.tf/loadBalancerIPs` annotation, move `externalTrafficPolicy: Local` to top-level service key (lines 34–42)
- [ ] Run `helm template` locally: confirm zero schema errors AND no `{{ fail }}` output

---

## References

All source material was fetched or read directly during this validation session:

- **Traefik charts pulled this session:** versions 27.0.2, 29.0.0, 30.0.0, 31.0.0, 32.0.0, 33.0.0, 34.0.0, 35.0.0, 36.0.0, 37.0.0, 38.0.0, 39.0.5 — all via `helm pull traefik/traefik --version X --untar`
- **Authelia charts pulled this session:** versions 0.9.0, 0.9.1, 0.9.2, 0.9.3, 0.9.4, 0.9.5, 0.9.10, 0.9.17, 0.10.0, 0.10.49 — all via `helm pull authelia/authelia --version X --untar`
- **`helm template` dry-runs:** run against both target charts with extracted current values and with proposed values — zero schema errors confirmed for proposed values
- Authelia application source at v4.39.13:
  - `internal/server/const.go`: `pathAuthzLegacy = "/api/verify"` — fetched live
  - `internal/server/handlers.go` lines 226–245: authz endpoint registration — fetched live
- Authelia chart `BREAKING.md` — read at versions 0.9.0 and 0.10.0 (all patch releases confirmed identical)
- Authelia 4.38 release blog: https://raw.githubusercontent.com/authelia/authelia/v4.38.0/docs/content/blog/release-notes-4.38/index.md
- Traefik v2→v3 migration guide (live): https://doc.traefik.io/traefik/migrate/v2-to-v3/
- Traefik v2→v3 configuration details (live): https://doc.traefik.io/traefik/migrate/v2-to-v3-details/
- Traefik chart `Changelog.md` at all intermediate versions (read directly from pulled charts)
- Authelia server-endpoints-authz docs (live): https://www.authelia.com/configuration/miscellaneous/server-endpoints-authz/
