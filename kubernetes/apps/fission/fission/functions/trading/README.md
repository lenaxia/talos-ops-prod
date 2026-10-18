# trading/ — Fission port of the ai-trading system (shadow mode)

Staged from `lenaxia/functions` `deploy/trading/` (tag `*-0.1.0` releases).
Full architecture + caveats: `README-TRADING.md` in that repo.

## What lands with this directory

- `packages.yaml` / `functions.yaml` — Package + Function CRs (debate,
  decide, execute, score, digest, morning-chain, afternoon-chain,
  trading-seed; env `python3-trading`, newdeploy MinScale 0)
- `triggers.yaml` (../httptriggers/trading/) — HTTP routes + TimeTriggers
  (13:45 / 22:30 UTC weekdays)
- `../../environments/python3-trading.yaml` — pinned env images (1.35.0)
- databases: CNPG cluster `tradingpg` + `tradingpg-db-init` Job (commented
  entry in `clusters/kustomization.yaml`)

## REQUIRED before merge (sops key holder)

1. Generate the DB role password: `openssl rand -base64 24`.
2. Fill + encrypt `secret-trading.yaml.template` into:
   - `kubernetes/apps/databases/cloudnative-pg/clusters/tradingpg-app.sops.yaml`
     (name `tradingpg-app`, ns `databases`, key `PASSWORD` only)
   - one `secret-<fn>.sops.yaml` per function right here (ns `fission`,
     name `trading-<fn>`; key matrix in the template header). SHADOW: "1"
     everywhere — shadow mode default.
3. Uncomment the secret entries in this directory's `kustomization.yaml`.

## After merge (Flux reconciles)

1. Uncomment `tradingpg-db-init.yaml` in `clusters/kustomization.yaml`
   (needs `tradingpg-app` + `postgres-superuser` secrets; idempotent),
   then comment it back out once the Job completes (Jobs are immutable).
2. Fire the seeder once via the router:
   `kubectl exec -n fission deploy/router -- curl -s -X POST http://localhost:8080/trading-seed`
3. Watch the next 13:45 / 22:30 UTC run:
   `fission function logs --name morning-chain --follow`, and
   `SELECT * FROM step_completions ORDER BY ts DESC LIMIT 10;` on db `trading`.

## Cutover (post comparison week)

Flip `SHADOW: "0"` in `secret-execute.sops.yaml`, add CNPG backups, and
disable the GHA schedules in `lenaxia/ai-trading` — see the cutover
checklist in the functions repo's `README-TRADING.md`.
