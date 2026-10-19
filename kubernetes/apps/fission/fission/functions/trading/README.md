# trading/ — Fission port of the ai-trading system (shadow mode)

Staged from `lenaxia/functions` `deploy/trading/` (release zips
`<fn>-<version>`, all currently 0.1.2 — matching the packages.yaml
pins in this PR).
Full architecture + caveats: `README-TRADING.md` in that repo.

## What lands with this directory

- `packages.yaml` / `functions.yaml` — Package + Function CRs (debate,
  decide, execute, score, digest, morning-chain, afternoon-chain,
  trading-seed; env `python3-trading`, newdeploy MinScale 0). All
  functions mount the ONE shared `trading` secret.
- `triggers.yaml` (../httptriggers/trading/) — HTTP routes + TimeTriggers
  (13:45 / 22:30 UTC weekdays)
- `../../environments/python3-trading.yaml` — pinned env images (1.35.0)
- databases: CNPG cluster `tradingpg` with `bootstrap.initdb.secret` —
  the `tradingpg-app` sops secret (username+password) makes CNPG create
  the `trading` role + database at first boot. **No db-init Job.**

## REQUIRED before first live use — AFTER merging this PR, BEFORE any cluster delete/recreate (sops key holder) — TWO files

This PR merges first and deliberately defers both sops files to the
follow-up (functions stay unspecialized; no cluster regression until
then). Do NOT start any `delete cluster tradingpg` before both files
below are encrypted, uncommented, and reconciled.

1. `openssl rand -base64 24` for the password.
2. Fill + encrypt `secret-trading.yaml.template` into:
   - `databases/cloudnative-pg/clusters/tradingpg-app.sops.yaml`
     (username+password) — uncomment it in `clusters/kustomization.yaml`
   - `functions/trading/secret-trading.sops.yaml` (shared, ns fission,
     full key set, `SHADOW: "1"`) — uncomment it in this directory's
     `kustomization.yaml`

Bootstrap runs only at cluster init. If `tradingpg` already came up
before `tradingpg-app` existed, delete the empty cluster (pre-seed =
zero data loss) and let Flux recreate it — **ordering matters**: land
both sops secrets FIRST (encrypt + uncomment their kustomization slots),
then `kubectl -n databases delete cluster tradingpg` (+ its PVC).
Recreating before `tradingpg-app` exists leaves initdb incomplete and
the cluster degraded (self-recovers once the secret lands, but red
until then). Same transient applies if the cluster is created at merge
time before the sops follow-up merges. Note: password rotation is now
manual (bootstrap consumes the secret once) — rotate via psql when
ever needed.

## After merge (Flux reconciles)

1. `POST /trading-seed` once via the router:
   `kubectl exec -n fission deploy/router -- curl -s -X POST http://localhost:8080/trading-seed`
2. Watch the next 13:45 / 22:30 UTC run:
   `fission function logs --name morning-chain --follow`, and
   `SELECT * FROM step_completions ORDER BY ts DESC LIMIT 10;` on db `trading`.

## Accepted risk: public router endpoints (documented deliberately)

The fission router is already exposed at `f.${SECRET_DEV_DOMAIN}`
(rate-limit only, no auth) and via a Cilium LoadBalancer. These triggers
add publicly-invokable trading endpoints on that surface:

- `/debate` burns a paid-LLM budget (40 min function timeout) per call
- `/trading-seed` (GET or POST) re-seeds the DB (idempotent upserts)
- `/execute` touches the Alpaca paper account — read-only under
  SHADOW=1, live orders only after the cutover flip

Until the sops secret exists every function fails closed (no creds), and
SHADOW=1 keeps broker access read-only. Longer term, restrict the
trading paths with a dedicated Traefik router +
`networking-chain-authelia@kubernetescrd` for the chain functions if the
public surface becomes a concern. **The SHADOW=0 cutover flip must not
ship before that restriction is in place.**

## Cutover (post comparison week)

Flip `SHADOW: "0"` in the shared `trading` secret (one key), add CNPG
backups, and disable the GHA schedules in `lenaxia/ai-trading` — see the
cutover checklist in the functions repo's `README-TRADING.md`.
