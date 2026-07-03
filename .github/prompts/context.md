Repository: talos-ops-prod — a homelab Kubernetes cluster on Talos Linux, managed with Flux GitOps. Single maintainer: @lenaxia.

**Before doing anything else: read `README-LLM.md` at the repo root.** It is the authoritative source of truth for architecture, conventions, and hard rules. Every response must be consistent with it. Where this document and `README-LLM.md` disagree, `README-LLM.md` wins — but flag the drift so it can be reconciled.

---

## What the cluster runs

Production homelab serving:
- **Authentication** — Authelia + OIDC gateway for ~15 apps
- **Media** — Plex, Jellyfin, Sonarr, Radarr, Overseerr, Tautulli, Transmission
- **Home automation** — Home Assistant, ESPHome, Node-RED, Mosquitto MQTT, Z-Wave JS UI
- **Self-hosted services** — Forgejo, Vaultwarden, Nextcloud, Outline, Paperless-ngx
- **Ragnarok Online servers** — rAthena classic/renewal, Hercules classic/renewal, OpenKore bots
- **AI / ML** — vLLM, LocalAI, LiteLLM, Open-WebUI, LLMSafeSpaces
- **Infrastructure** — Traefik, cert-manager, Cilium, MetalLB-style L2 announcements, OpenEBS, Longhorn, CloudNative-PG, MariaDB, Redis, Prometheus stack, Loki, Vector

Domain: `${SECRET_DEV_DOMAIN}` — sourced from SOPS-encrypted cluster secrets.

---

## Cluster shape

- **Talos Linux** — 3 control-plane nodes (`cp-00/01/02` on 192.168.3.10–12) + workers (`worker-00/01/02/03` on 192.168.3.20–23; `worker-04` defined in talconfig but not currently joined).
- **VIP** — `192.168.3.30` for control-plane HA.
- **CNI + LoadBalancer** — Cilium in native routing mode. LoadBalancer IPAM and L2 announcements are handled entirely by Cilium via `CiliumLoadBalancerIPPool` + `CiliumL2AnnouncementPolicy` (config in `kubernetes/apps/kube-system/cilium/config/cilium-l2.yaml`). **MetalLB is NOT deployed.** Some services still carry stale `metallb.universe.tf/*` annotations from an earlier era — these are dead weight; the real IP allocation comes from Cilium and `spec.loadBalancerIP`. No BGP currently active.
- **Kubernetes** — v1.36.x on Talos v1.13.x per `kubernetes/bootstrap/talos/talconfig.yaml`. Older nodes may temporarily lag during rolling upgrades.
- **Flux** — reconciles the whole `kubernetes/` tree from GitHub. Root Kustomization is `kubernetes/flux/apps.yaml`.

Node names to remember:
- Control plane: `cp-00`, `cp-01`, `cp-02`
- Workers: `worker-00`, `worker-01`, `worker-02`, `worker-03`, `worker-04` (defined, not joined)

---

## Repository layout (canonical)

```
talos-ops-prod/
    kubernetes/
        apps/                          per-namespace app manifests
            actions-runner-system/     self-hosted GitHub runners
            cert-manager/
            databases/                 CloudNative-PG, MariaDB operator, Redis, InfluxDB, Telegraf
            default/                   canary/shadow test deployments
            fission/                   Fission serverless
            flux-system/               Flux monitoring + notifications
            home/                      home automation + AI + misc
            jobhunt/                   jobhunt tooling
            kube-system/               Cilium, CoreDNS, GPU plugins, Multus (disabled), Reloader, Spegel
            kyverno/                   policy engine
            llmsafespaces/             LLM safe-spaces platform
            media/                     Plex, Sonarr, Radarr, Jellyfin, etc.
            monitoring/                kube-prometheus-stack, Grafana, Loki, Vector
            networking/                Traefik, Authelia, external-dns, Cloudflared, webfinger, cloudflare-ddns
            openebs-system/            local hostpath provisioner
            ragnarok/                  rAthena, Hercules, OpenKore
            storage/                   MinIO, Longhorn, Volsync, Kopia, Paperless
            utilities/                 Forgejo, Vaultwarden, pgAdmin, AdGuard, Brother printer, etc.
        bootstrap/talos/               talconfig.yaml + patches (Talos machine config source of truth)
        components/                    shared Kustomize components (volsync, etc.)
        flux/
            apps.yaml                  root Kustomization → kubernetes/apps
            config/                    cluster-level Flux config
            repositories/              HelmRepository / GitRepository / OCIRepository sources
            vars/
                cluster-settings.yaml  non-sensitive cluster-wide variables (ConfigMap)
                secret.sops.yaml       sensitive variables (SOPS-encrypted Secret)

    bootstrap/                         talhelper configs + initial helmfile (used only at cluster bootstrap)
    .taskfiles/                        Task runner definitions
    docs/                              operational notes and upgrade logs
    hack/                              one-off admin manifests (restore jobs, migrations)
    scripts/                           shell/python helpers
    .sops.yaml                         SOPS encryption config
    Taskfile.yaml                      top-level Task runner entrypoint
    README-LLM.md                      **authoritative** LLM starting point
```

---

## Application manifest pattern

Every application follows this Kustomize + Flux pattern:

```
kubernetes/apps/<namespace>/<app>/
    ks.yaml                            Flux Kustomization (points to ./app, dependsOn, healthChecks)
    app/
        kustomization.yaml             Kustomize root (lists all resources)
        helm-release.yaml              HelmRelease
        secret.sops.yaml               SOPS-encrypted Secret with app credentials (if needed)
        ingress.yaml                   Traefik Ingress (optional)
        service.yaml                   extra Service, e.g. LoadBalancer (optional)
        pvc-*.yaml                     PersistentVolumeClaim (optional)
```

The overwhelming majority of apps use **`app-template` from bjw-s** as the Helm chart (current version in this cluster is `5.0.1`; some older apps are on `4.x`, one on `3.1.0`). See `README-LLM.md` for the full app-template values reference.

---

## Networking

Key IPs (from `kubernetes/flux/vars/cluster-settings.yaml` + LoadBalancer status):

| Address | Service |
|---|---|
| `192.168.5.11` | Authelia LoadBalancer |
| `192.168.5.12` | Traefik LoadBalancer (primary ingress) |
| `192.168.5.13` | Forgejo SSH |
| `192.168.5.0/25` | Cilium `l2-pool-reserved` (services opting in with `cilium.io/l2-ip-pool: reserved`) |
| `192.168.5.128/25` | Cilium `l2-pool` (default pool for all other LoadBalancer services) |
| `192.168.0.120` | Synology NAS (NFS + LDAP) |
| `192.168.0.5` | AdGuard Home (DNS) |
| `192.168.5.15` | MariaDB primary |
| `192.168.5.17` | Redis |

**Traefik middleware chains** (in `kubernetes/apps/networking/traefik/middlewares/`):

| Chain | Usage |
|---|---|
| `networking-chain-no-auth@kubernetescrd` | Public services, no auth |
| `networking-chain-no-auth-local@kubernetescrd` | LAN-only, rate limit only |
| `networking-chain-authelia@kubernetescrd` | Authelia-protected |
| `networking-chain-basic-auth@kubernetescrd` | Legacy HTTP basic auth |

Always include the `networking-` namespace prefix in ingress annotations.

---

## Authentication (Authelia)

- Chart version and image are pinned independently — see the HelmRelease in `kubernetes/apps/networking/authelia/`.
- LoadBalancer IP `192.168.5.11`.
- Backend: PostgreSQL (`defaultpg-rw.databases.svc.cluster.local:5432`).
- Session store: Redis (`redis-lb.databases.svc.cluster.local:6379`).
- User directory: LDAP on Synology NAS (`ldap://192.168.0.120`), base DN `dc=kao,dc=family`.
- 2FA: Duo Push.
- SMTP: AWS SES.

OIDC clients live under `identity_providers.oidc.clients` in the Authelia HelmRelease values. Client secrets are stored in SOPS-encrypted Secrets and referenced via Flux variable substitution (`SECRET_<APP>_OAUTH_CLIENT_SECRET`).

---

## Databases

| Service | Address | Notes |
|---|---|---|
| PostgreSQL (CloudNative-PG operator) | `defaultpg-rw.databases.svc.cluster.local:5432` | Primary relational DB. Per-app databases as `Cluster` or `Database` CRDs under `databases/cloudnative-pg/`. |
| MariaDB (MariaDB operator) | `192.168.5.15:3306` primary | Apps requiring MySQL |
| Redis | `redis-lb.databases.svc.cluster.local:6379` | Sessions, queues |
| InfluxDB v2 | in-cluster | Time-series metrics |

---

## Storage

| Type | Used for |
|---|---|
| OpenEBS local-hostpath | Default StorageClass — local node storage |
| Longhorn | Replicated block storage for stateful apps (default target for most PVCs) |
| NFS (NAS) | Media libraries, backups, Paperless data |
| MinIO | In-cluster S3-compatible object storage |
| Kopia | PVC backups |
| VolumeSnapshots + Volsync | PVC snapshots and replication |

NFS server addresses are `NFS_*` variables in `cluster-settings.yaml`.

---

## Variable substitution

Flux performs variable substitution across the entire `kubernetes/apps/` tree from two sources:
- `kubernetes/flux/vars/cluster-settings.yaml` — non-sensitive (ConfigMap)
- `kubernetes/flux/vars/secret.sops.yaml` — sensitive (SOPS-encrypted Secret)

Always reference values with `${VAR_NAME}`. **Never hardcode IPs or domain names.**

Common variables:
```
SECRET_DEV_DOMAIN          primary domain (e.g. example.com)
SVC_TRAEFIK_ADDR           192.168.5.12
SVC_AUTHELIA_ADDR          192.168.5.11
SVC_FORGEJO_SSH_ADDR       192.168.5.13
NAS_ADDR                   192.168.0.120
TIMEZONE                   e.g. America/Los_Angeles
APP_UID / APP_GID          conventional non-root pod UIDs (568)
```

---

## Commands

The following slash-commands are available on this issue/PR thread. Reply with one to trigger the assistant. Any text after a command tunes the request (e.g. `/review focus on the SOPS handling`).

- `/ai` — re-assess the current issue or PR in full
- `/ai <text>` — address a specific request
- `/review [text]` — explicit PR code review
- `/fix <description>` — fix a bug: branch, regression check, PR, iterate until approved, merge
- `/implement <description>` — implement a feature: branch, PR, iterate until approved, merge
- `/test <target>` — write or improve validation/tests: branch, PR, iterate until approved, merge
- `/analyze [text]` — read-only analysis, posts findings as a comment
- `/explain <topic>` — explain a manifest, controller, or data flow
- `/security [text]` — security-focused review (SOPS handling, RBAC, ingress exposure)
- `/triage [text]` — triage an issue: categorize, prioritize, suggest labels
- `/design [text]` — iterate on an operational design under `docs/` before implementing (**holds** for explicit `/merge`)
- `/merge` — explicitly merge an approved PR (squash + delete branch)
- `/help` — show the full command reference

Append `--no-merge` to `/fix`, `/implement`, `/test`, or `/security` to hold the merge until you post `/merge`. `/design` always holds.

The assistant is triggered automatically and reads `README-LLM.md` plus the full thread before responding.
