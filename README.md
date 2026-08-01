# talos-ops-prod

A production homelab Kubernetes cluster, managed entirely through GitOps.

This repository is the single source of truth for a cluster running on
[Talos Linux](https://www.talos.dev/) and reconciled by [Flux](https://fluxcd.io/).
Every workload, network policy, and secret originates from a file in this repo —
cluster state is never mutated by hand with `kubectl`.

> Looking for the LLM-facing reference? It lives in **[`README-LLM.md`](./README-LLM.md)** —
> critical rules, manifest patterns, networking, auth, storage, and the SOPS workflow.

---

## At a glance

| Area | Technology |
|---|---|
| Operating system | [Talos Linux](https://www.talos.dev/) |
| GitOps | [Flux](https://fluxcd.io/) (Kustomize + HelmReleases) |
| CNI + LoadBalancer | [Cilium](https://cilium.io/) — native LB IPAM and L2 announcements (no MetalLB) |
| Ingress | [Traefik](https://traefik.io/) with Authelia middleware chains |
| Authentication | [Authelia](https://www.authelia.com/) — forward-auth + OIDC SSO for ~15 apps |
| Secrets | [SOPS](https://github.com/getsops/sops) + [age](https://github.com/FiloSottile/age) |
| Storage | [OpenEBS](https://openebs.io/) LocalPV, [Longhorn](https://longhorn.io/), NFS, [MinIO](https://min.io/) |
| DNS | split-horizon via [external-dns](https://github.com/kubernetes-sigs/external-dns) + AdGuard Home |
| Policy | [Kyverno](https://kyverno.io/) |
| Dependency updates | [Renovate](https://www.mend.io/renovate/) |

## What runs here

Around 120 workloads across the cluster. A few highlights:

- **Media & photos** — Plex, Jellyfin, Sonarr, Radarr, Bazarr, Immich, Komga, Calibre, Transmission
- **Home automation** — Home Assistant, ESPHome, Z-Wave JS, Mosquitto (MQTT), Frigate
- **Self-hosted apps** — Forgejo, Vaultwarden, Outline, Paperless, Stirling-PDF, pgAdmin, Guacamole, IT-Tools, Uptime Kuma
- **Databases** — CloudNative-PG (Postgres), MariaDB (Galera), Redis, Valkey, InfluxDB
- **AI / ML** — vLLM, LocalAI, LiteLLM, Open-WebUI, Stable Diffusion, LibreChat
- **Ragnarok Online** — rAthena, Hercules, OpenKore, ROBrowser
- **Infrastructure** — cert-manager, external-dns, Cloudflare Tunnel, Reloader, Spegel
- **Observability** — Prometheus stack, Grafana, Loki, Vector

## Repository layout

```
kubernetes/
    apps/           per-namespace application manifests
    bootstrap/      initial cluster bootstrap (Talos + Flux)
    components/     shared kustomize components
    flux/           Flux config, sources, and cluster-wide variables
bootstrap/          talhelper configs and makejinja templates
.taskfiles/         task runner definitions
docs/               operational runbooks and worklogs
hack/               one-off admin manifests (restore jobs)
scripts/            helper scripts (validation, monitoring)
```

Each application follows a consistent Kustomize + Flux pattern:

```
kubernetes/apps/<namespace>/<app>/
    ks.yaml                  Flux Kustomization (sets path + dependsOn)
    app/
        helm-release.yaml    chart + values (mostly bjw-s app-template)
        secret.sops.yaml     SOPS-encrypted Secret
        ingress.yaml         Traefik Ingress (optional)
```

## Operating the cluster

Day-to-day operations are driven by [task](https://taskfile.dev/):

```sh
# Bootstrap
task bootstrap:talos          # install Talos and bootstrap the cluster
task bootstrap:flux           # install Flux and sync from this repo

# Validation
task kubernetes:kubeconform   # validate all manifests against schemas

# Maintenance
task talos:generate-config
task talos:apply-node HOSTNAME=<node> MODE=auto
task talos:upgrade-node HOSTNAME=<node>
task talos:upgrade-k8s
```

Secrets must be encrypted with SOPS before committing — never commit a decrypted
`secret.sops.yaml`. The full secret workflow is documented in `README-LLM.md`.

## Documentation

- [`README-LLM.md`](./README-LLM.md) — primary reference; start here for any work on this repo
- [`docs/kopia-restore-runbook.md`](./docs/kopia-restore-runbook.md) — restoring PVCs from Kopia backups
- [`docs/flux-sync-explanation.md`](./docs/flux-sync-explanation.md) — how Flux reconciliation and variable substitution work
- [`docs/shadow-testing-deployment-guide.md`](./docs/shadow-testing-deployment-guide.md) — canary/shadow deployment pattern
- [`docs/`](./docs) — full list of runbooks and historical worklogs

## Acknowledgements

Built on the foundation of [@onedr0p's cluster-template](https://github.com/onedr0p/cluster-template)
and informed by the wider [Home Operations](https://discord.gg/home-operations) community.
