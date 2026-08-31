# Firefly III SimpleFIN Sync — Runbook

Automated nightly import of SimpleFIN (BECU / Fidelity / Citi) transactions
into Firefly III, plus hourly post-import maintenance.

## Components

| Resource | File | Purpose |
|---|---|---|
| CronJob `firefly-importer-autoimport` | `kubernetes/apps/utilities/firefly-importer/app/autoimport.yaml` | Nightly 02:40 `${TIMEZONE}` CLI import (`php artisan importer:import`) with the preserved account mapping |
| CronJob `firefly-importer-fixer` | `.../cronjob.yaml` | Hourly: dedupe journals by `external_id` on all `(NNNN)` asset accounts; flip 401(k) contributions from withdrawals to deposits (SimpleFIN reports them institution-signed) |
| PrometheusRule `firefly-importer-sync` | `.../prometheus-rule.yaml` | `FireflyImportJobFailed` + `FireflyAutoImportStalled` (>26h without success) |
| Secret key `SIMPLEFIN_ACCESS_URL` | `.../secret.sops.yaml` | The exchanged SimpleFIN access URL (credential — sops-encrypted) |
| Firefly account "Unmapped Import" (id 201) | created via API | Catch-all for unmapped SimpleFIN accounts (`default_account` in the import config). If its balance is ever non-zero, a new bank account appeared — add a mapping. |

## Version-coupled behaviors — re-verify on data-importer upgrades

These are coupled to `fireflyiii/data-importer` behavior and must be re-tested
whenever Renovate bumps the image tag (in both CronJobs and the importer
HelmRelease):

1. `php artisan config:clear` before import — the image ships a baked config
   cache that otherwise ignores the runtime `IMPORT_DIR_ALLOWLIST` env.
2. Exit-code handling — the importer exits `GENERAL_ERROR` (1) when Firefly
   rejects re-imported duplicates, so job success is determined by
   `grep -q 'Done!' /tmp/import.log` instead of the process exit code.
3. `php artisan import:validate-json` — validates the rendered config against
   the importer's JSON config standard; fails the job loudly before importing
   if a version bump changed the config format.

## Routine maintenance

### SimpleFIN access URL expiry

SimpleFIN has rotated bridge infrastructure before (the `tsa.`/`data.`
subdomains went NXDOMAIN in Aug 2026; old claim keys started returning
`403 was it already claimed?`). Symptom: `FireflyImportJobFailed` alerts and
`403`/connection errors in job logs. Fix:

1. Generate a fresh Access Key at <https://bridge.simplefin.org>
2. Get the exchanged access URL: run the data-importer web UI once with the
   new key, then read `configuration.access_token` from the newest job file
   under `/var/www/html/storage/import-jobs/*.json` in the importer pod
   (never commit or paste this value anywhere).
3. Update the key:
   `sops kubernetes/apps/utilities/firefly-importer/app/secret.sops.yaml`
   → set `SIMPLEFIN_ACCESS_URL`, commit, push. Flux re-applies the Secret.

### Import window

`date_not_before` is rendered at runtime as **today − 90 days**
(`IMPORT_WINDOW_DAYS` env on the initContainer, default 90). The window is
bounded; no annual manual bump needed. History older than 90 days stays in
Firefly — it is never re-fetched, and duplicates are prevented by
external-id dedup.

### Balance re-anchoring (manual, occasional)

Nightly imports add transactions only — they do not reconcile levels. Drift
sources:

- **Investment accounts** (IRAs, 401k, RSU, INVESTMENT, HOLDING): market moves.
- Any SimpleFIN revision of pending transactions.

To re-anchor an account: set its opening balance so that
`opening + Σjournals = real-world balance`:
`opening = real_balance − current_firefly_balance + current_opening`.
Do this for the Fidelity accounts whenever the numbers start to look stale
(monthly is plenty). BECU/Citi accounts stay exact automatically.

### 401(k) sign quirk

The Fidelity feed reports 401(k) contributions institution-signed, so every
import lands them as withdrawals. The hourly fixer converts them to deposits
(keeping `external_id` so dedup still works). If the fixer is disabled, the
401(k) balance will drift negative again.

## Backups

Both `firefly-iii` (5Gi) and `firefly-importer` (2Gi) PVCs carry the
`snapshot.home.arpa/enabled: "true"` label; the Kyverno
`snapshot-cronjob-controller` policy generates daily Kopia snapshot CronJobs
for them (see `kubernetes/apps/kyverno/policies/snapshot-cronjob-controller.yaml`).

### Post-deploy verification (once, after first merge)

1. `kubectl -n utilities get pvc firefly-iii firefly-importer -o jsonpath='{.items[*].metadata.labels}'`
   — confirm `snapshot.home.arpa/enabled: "true"` propagated (app-template
   applies persistence `labels` on helm upgrade). If not, apply manually:
   `kubectl -n utilities label pvc firefly-iii firefly-importer snapshot.home.arpa/enabled=true`
2. Confirm Kyverno generated snapshot CronJobs:
   `kubectl -n utilities get cronjobs | grep snap` — expect
   `firefly-iii-firefly-iii-snap` and `firefly-importer-firefly-importer-snap`.
   If missing despite correct labels, re-trigger the generate rule by touching
   a PVC label (add + remove any annotation).

## Known incident history

- **2026-08-31**: Initial setup. Fixed inverted 401(k) contributions + a
  duplicate import; backfilled opening balances from BECU/Fidelity/Citi
  statements; re-anchored after the first full-window import brought missing
  historical transactions; created the "06 Kirkland" account (missing from
  Firefly); added `SIMPLEFIN_ACCESS_URL` after the bridge migration killed the
  old claim key.
