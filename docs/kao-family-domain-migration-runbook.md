# Runbook: Gradual thekao.cloud → kao.family Domain Migration

**Goal:** Move all cluster services to the `kao.family` domain gradually, app by
app, with instant rollback at every step. `thekao.cloud` remains fully served
until the final retirement phase.

**Why gradual:** Authelia sessions, OIDC issuers, TLS certs, client-side app
config (mobile apps, bookmarks, webhooks), and email are all bound to the
current domain. A big-bang flip breaks too many things at once to debug.

**Domain variables (established convention):**

- `${SECRET_DEV_DOMAIN}` = `thekao.cloud` (SOPS, `flux/vars/secret.sops.yaml`)
- `${SECRET_PROD_DOMAIN_KF}` = `kao.family` (SOPS — same secret; already used
  by `traefik/ingresses/synology-moments.yaml`)
- `${SECRET_PROD_DOMAIN_KFD}` = third domain (used by `minio` ingress s3 host)

---

## Current state (updated 2026-10-01, Phase 1 complete)

- ~127 manifests use `${SECRET_DEV_DOMAIN}`; the 26 hardcoded `thekao.cloud`
  refs in 13 files were converted to `${SECRET_DEV_DOMAIN}` (Phase 0)
- `external-dns` domainFilters includes both zones (Phase 0)
- ClusterIssuer `letsencrypt-production` dnsZones selector includes
  `${SECRET_PROD_DOMAIN_KF}` (Phase 1 — **this was a live blocker**, see below)
- **Reference dual-host example:** `traefik/ingresses/synology-moments.yaml`
  serves `moments.${SECRET_PROD_DOMAIN_KF}` + `moments.${SECRET_DEV_DOMAIN}`
  with one shared TLS secret

## Phase 1 — Validation results (2026-10-01, done live)

| Check | Result |
|---|---|
| external-dns CF token writes kao.family zone | ✅ created A + TXT records (zone `603cfc56…`) |
| cert-manager CF token DNS-01 in kao.family zone | ✅ TXT `_acme-challenge` created and cleaned |
| Let's Encrypt issuance for *.kao.family | ✅ test cert `phase1-test.kao.family` issued, then deleted |
| ClusterIssuer solver config | ❌→✅ dnsZones selector did NOT include kao.family → **every kao.family cert failed with "no configured challenge solvers"**. Fixed in `issuers/letsencrypt-production.yaml`. This had silently broken the `moments.kao.family` cert (deployed 2d19h earlier, stuck pending); the fix unblocked it and it issued. |

**Manual residue from the validation (delete in Cloudflare dashboard, kao.family zone):**
- `phase1-test` record (if listed — the `*.kao.family` wildcard makes dig
  checks ambiguous; authoritative NS showed a CNAME→apex answer)
- `k8s.a-phase1-test` TXT (external-dns marker)

external-dns will not garbage-collect these (its TXT-registry adoption fails
against the wildcard; documented quirk, harmless).

### Zone facts learned (important for Phase 2)

1. **`*.kao.family` wildcard CNAME → apex exists.** Every subdomain already
   resolves publicly to the home IP (97.113.186.130). Consequences:
   - New hostnames "work" at the DNS level instantly — but hit Traefik with a
     default cert until a real Certificate + ingress exist
   - You cannot use `dig` to prove a kao.family record is gone/deployed —
     always confirm via Cloudflare dashboard or authoritative NS
2. **kao.family email is LIVE on Hotmail/Outlook** (MX `pamx1.hotmail.com`,
   SPF `include:outlook.com`, DMARC `p=quarantine`). **Do NOT add SES SPF
   includes or send mail from kao.family** — that would interfere with the
   family's real email. Keep app notifications on `thekao.cloud` SES
   (Phase 3 question: pick a subdomain strategy or keep old-domain mail).
3. **No split-horizon LAN override** — and none should be added: the
   `thekao.cloud → 192.168.5.12` override was removed 2026-08-14 because
   LLMSafeSpaces pod egress NetworkPolicy blocks RFC1918 (see
   `ansible/roles/dns/defaults/main.yaml:39`). kao.family follows the same
   public-resolution model. Revisit only with a pod-compatible path.
4. external-dns creates **proxied** records; annotated ingresses
   (`external-dns.home.arpa/enabled: "true"`) get target
   `ipv4.${SECRET_PUBLIC_DOMAIN}` injected by the Kyverno policy
   `apply-ingress-external-dns-annotations`.

## Phase 2 — Per-app cutover (repeat per app, any order)

Follow the `synology-moments.yaml` pattern: add the new host as an ADDITIONAL
rule/tls host first, verify, then (optionally much later) drop the old host.

**Plain apps (forward-auth only — most of the cluster):**

1. Add second host: `app.${SECRET_PROD_DOMAIN_KF}` to `rules:` and `tls.hosts`
   (new `secretName` or extend existing — moments uses one shared secret)
2. Commit → Flux reconciles → cert-manager issues via DNS-01 → done
3. Rollback = revert the commit; the old host never stopped working

No Authelia change needed for forward-auth apps: cross-domain SSO bounce works
(browser hits `authelia.thekao.cloud` for login, returns to the new host).

**OIDC apps (tailscale, minio, open-webui, pgadmin, grafana, outline,
overseerr, komga, linkwarden, forgejo, litellm, llmsafespaces):**

1. FIRST add the new redirect URI to the app's Authelia client
   (`redirect_uris:` accepts multiple), e.g.
   `https://app.kao.family/oauth/callback` alongside the old one
2. Update the app's own configured redirect/callback URL to the new host
3. Add the new ingress host as above
4. Remove the old redirect URI after clients stop using it

**Suggested order:** leaf apps (echo-server, podinfo, librespeed) → media →
OIDC apps → `ai`/`s3` (many internal consumers; all var-based since Phase 0,
but check each consumer's host).

## Phase 3 — Authelia + identity cutover (single shot, schedule a window)

Authelia has exactly one public domain, session cookie domain, and OIDC
issuer — it cannot be dual-hosted. When everything else is on kao.family:

1. Flip authelia's host/domain/session/OIDC-issuer config to kao.family
2. Update EVERY remaining OIDC client redirect URI (remove `*.thekao.cloud`
   URIs, keep `*.kao.family`)
3. Webfinger app: move its ingress host
4. All users re-authenticate once (sessions invalidate) — expected
5. Check apps that persist their own URLs in databases (Immich, Outline,
   Nextcloud, Monica `APP_URL`, LiteLLM config) and grafana alert URLs
6. Decide mail strategy: keep SES on thekao.cloud, or a dedicated
   `notify.kao.family`-style subdomain with its own SPF (never touch the
   apex outlook.com SPF — see Phase 1 fact #2)

## Phase 4 — Retirement of thekao.cloud

1. Cloudflare bulk redirect rule: `*.thekao.cloud/*` → 301 equivalent on
   kao.family
2. Keep the zone + redirect for 3–6 months (mobile clients, old shares)
3. Then flip `SECRET_DEV_DOMAIN` → `kao.family` in SOPS (or replace all
   `${SECRET_DEV_DOMAIN}` with `${SECRET_PROD_DOMAIN_KF}` repo-wide and drop
   the old var), remove the CF zone and any remaining references

## Client-side checklist (not in GitOps)

- Mobile apps with stored server URLs: Immich, Bitwarden/Vaultwarden,
  Nextcloud, Home Assistant companion
- Browser bookmarks / hajimari entries (moments + drive already point at
  kao.family)
- ansible `cloudflare` role: uptime worker `ALERTMANAGER_URL`
- Forgejo: runner/webhook URLs, git remotes
- Tailscale/Headscale (planned): pick which domain MagicDNS + split-DNS
  advertises — decide during Phase 2
