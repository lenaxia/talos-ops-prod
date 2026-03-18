# talos-ops-prod-authelia Documentation - LLM Starting Point

**This is the primary document for LLM-assisted development on this repository.**

All essential information is consolidated here.

---

## Project Overview

**talos-ops-prod-authelia** is a GitOps repository managing a production Kubernetes cluster running on [Talos Linux](https://github.com/siderolabs/talos). It uses [Flux](https://github.com/fluxcd/flux2) to continuously reconcile cluster state from this repository.

This is a homelab/personal cluster serving:
- Authentication (Authelia + OIDC for ~15 apps)
- Media stack (Plex, Jellyfin, Sonarr, Radarr, etc.)
- Home automation (Home Assistant, ESPHome, Node-RED, MQTT)
- Self-hosted services (Forgejo, Vaultwarden, Nextcloud, Outline, etc.)
- Ragnarok Online game servers (rAthena, Hercules, OpenKore)
- AI/ML services (vLLM, LocalAI, LiteLLM, Open-WebUI)
- Infrastructure (Traefik, cert-manager, Cilium, MetalLB, OpenEBS, monitoring)

**Domain:** `${SECRET_DEV_DOMAIN}` — resolved from SOPS-encrypted secrets. In cluster files this appears as a variable substitution.

---

## CRITICAL RULES

### 1. NEVER Commit Unencrypted Secrets

**All secrets MUST be encrypted with SOPS before committing. This rule has no exceptions.**

- Secret files are named `secret.sops.yaml` and encrypted with age.
- The age key file is `age.key` at the repo root (gitignored).
- SOPS config is at `.sops.yaml`.
- `.gitattributes` marks `*.sops.*` files for SOPS-aware diffs.

**Before staging any `*.sops.yaml` file, run this check:**

```bash
# Every value under data/stringData must be ENC[...] ciphertext.
# If this returns 0, the file is decrypted — DO NOT commit it.
grep -c "ENC\[" path/to/secret.sops.yaml

# The sops: block must be present at the bottom of the file.
grep "^sops:" path/to/secret.sops.yaml
```

**A file is safe to commit only when both commands return a match.**

If a `secret.sops.yaml` is decrypted, encrypt it before doing anything else:

```bash
sops --encrypt --in-place path/to/secret.sops.yaml
```

**If you are ever unsure whether a file is encrypted, do not commit it. Stop and verify first.**

### 2. NEVER Perform Destructive Git Operations

**Multiple agents or sessions may work in this repository.**

**FORBIDDEN:**
- `git checkout .` — discards uncommitted changes
- `git reset --hard` — destroys work
- `git clean -fd` — deletes untracked files

**REQUIRED:**
- Revert files one at a time with explicit user confirmation
- Always check `git status` before reverting anything

### 3. Variable Substitution — Use `${}` Syntax, Never Hardcode

Flux performs variable substitution from two sources:
- `kubernetes/flux/vars/cluster-settings.yaml` — non-sensitive cluster-wide variables (IPs, paths, etc.)
- `kubernetes/flux/vars/secret.sops.yaml` — sensitive variables (domain, passwords, API keys)

**Always use `${VAR_NAME}` in manifests.** Never hardcode IPs or domain names directly.

Key variables:
```
SECRET_DEV_DOMAIN      — primary domain (e.g. example.com)
SVC_TRAEFIK_ADDR       — 192.168.5.12
SVC_AUTHELIA_ADDR      — 192.168.5.11
SVC_FORGEJO_SSH_ADDR   — 192.168.5.13
NAS_ADDR               — 192.168.0.120
```

### 4. HelmRelease Versions Must Be Explicit

**Never use `latest` or floating tags.** Always pin:
- Helm chart version: `version: 1.2.3`
- Container image tag: `tag: v1.2.3`

Renovate manages automated version bumps via PRs.

### 5. Validate YAML Before Applying

```bash
task kubernetes:kubeconform    # validate all manifests against schemas
flux check --pre               # check Flux prerequisites
```

---

## Repository Structure

```
talos-ops-prod-authelia/
    kubernetes/
        apps/                  per-namespace application manifests
            cert-manager/
            databases/         postgres (cnpg), mariadb, redis, influxdb, telegraf
            default/           shadow/canary testing deployments
            flux-system/       flux monitoring + alerts
            home/              home automation + AI apps + misc
            kube-system/       cilium, coredns, multus, GPU plugins, reloader
            kyverno/           policy engine
            media/             plex, sonarr, radarr, jellyfin, etc.
            monitoring/        prometheus-stack, grafana, loki, vector
            networking/        traefik, authelia, external-dns, cloudflared
            openebs-system/    storage provisioner
            ragnarok/          rathena, hercules, openkore game servers
            storage/           minio, longhorn, volsync, kopia, paperless
            utilities/         forgejo, vaultwarden, pgadmin, adguard, etc.
        bootstrap/             initial cluster bootstrap (talos + flux)
        components/            shared kustomize components (volsync)
        flux/
            apps.yaml          root Flux Kustomization pointing to kubernetes/apps
            config/            cluster-level Flux config
            repositories/      HelmRepository + GitRepository sources
            vars/
                cluster-settings.yaml   non-sensitive cluster variables (ConfigMap)
                secret.sops.yaml        sensitive variables (SOPS-encrypted Secret)
                kustomization.yaml

    bootstrap/                 talhelper configs and initial helmfile
    .taskfiles/                task runner task definitions
    docs/                      operational notes and upgrade logs
    .sops.yaml                 SOPS encryption config
    Taskfile.yaml              top-level task runner
    config.sample.yaml         template bootstrap config (do not use directly)
```

---

## Application Manifest Pattern

Every application follows this Kustomize + Flux pattern:

```
kubernetes/apps/<namespace>/<app>/
    ks.yaml              Flux Kustomization (points to ./app, sets dependsOn)
    app/
        kustomization.yaml     Kustomize root (lists all resources)
        helm-release.yaml      HelmRelease with chart + values
        secret.sops.yaml       SOPS-encrypted k8s Secret with app credentials
        ingress.yaml           (optional) Traefik Ingress resource
        service.yaml           (optional) additional Service (e.g. LoadBalancer)
        pvc-*.yaml             (optional) PersistentVolumeClaim
```

### ks.yaml Example

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: &app myapp
  namespace: flux-system
spec:
  targetNamespace: home
  commonMetadata:
    labels:
      app.kubernetes.io/name: *app
  path: ./kubernetes/apps/home/myapp/app
  prune: true
  sourceRef:
    kind: GitRepository
    name: home-ops
  dependsOn:
    - name: cert-manager
      namespace: flux-system
```

### HelmRelease Example

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: &appname myapp
  namespace: home
spec:
  interval: 5m
  chart:
    spec:
      chart: myapp
      version: 1.2.3
      sourceRef:
        kind: HelmRepository
        name: my-charts
        namespace: flux-system
  values:
    image:
      tag: v1.2.3
```

### Ingress Example (with Authelia)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  namespace: home
  annotations:
    traefik.ingress.kubernetes.io/router.middlewares: networking-chain-authelia@kubernetescrd
spec:
  ingressClassName: traefik
  rules:
    - host: myapp.${SECRET_DEV_DOMAIN}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: myapp
                port:
                  number: 80
  tls:
    - hosts:
        - myapp.${SECRET_DEV_DOMAIN}
      secretName: myapp-tls
```

---

## Networking Architecture

### IP Address Layout

| Address | Service |
|---|---|
| `192.168.5.11` | Authelia (LoadBalancer) |
| `192.168.5.12` | Traefik (LoadBalancer, primary ingress) |
| `192.168.5.13` | Forgejo SSH |
| `192.168.5.1–5.67` | MetalLB devinfra pool |
| `192.168.5.68–5.255` | MetalLB default pool |
| `192.168.0.120` | NAS (Synology) |
| `192.168.0.5` | AdGuard Home (DNS) |
| `192.168.5.15` | MariaDB primary |
| `192.168.5.16` | MariaDB secondary |
| `192.168.5.17` | Redis |

### Ingress Flow

```
Internet / LAN
    → Cloudflare Tunnel (external apps only)
         OR
    → Traefik LoadBalancer (192.168.5.12)
        → Traefik middleware chains
            chain-no-auth          → rate-limit + secure-headers
            chain-authelia         → rate-limit + secure-headers + authelia forwardAuth
            chain-basic-auth       → rate-limit + secure-headers + basicAuth
        → Authelia forwardAuth (http://authelia.networking.svc.cluster.local/api/authz/forward-auth)
        → Backend service
```

### Traefik Middleware Chains

Defined in `kubernetes/apps/networking/traefik/middlewares/`:

| Chain | Usage |
|---|---|
| `chain-no-auth` | Public services, no authentication |
| `chain-no-auth-local` | LAN-only, rate limit only |
| `chain-authelia` | Protected services — requires Authelia auth |
| `chain-basic-auth` | HTTP basic auth (legacy) |

Reference in ingress annotations:
```yaml
traefik.ingress.kubernetes.io/router.middlewares: networking-chain-authelia@kubernetescrd
```

---

## Authentication (Authelia)

**Authelia** (`kubernetes/apps/networking/authelia/`) is the central authentication service.

- Version: `0.10.49` (chart), `4.39.13` (image)
- LoadBalancer IP: `192.168.5.11`
- Backend: PostgreSQL (`defaultpg-rw.databases.svc.cluster.local`)
- Session store: Redis (`redis-lb.databases.svc.cluster.local`)
- 2FA: Duo Push (`api-b68b8774.duosecurity.com`)
- User directory: LDAP at `ldap://192.168.0.120` (Synology NAS), base DN `dc=kao,dc=family`
- SMTP notifications: AWS SES

### Access Control Policy (summary)

- Default policy: **deny**
- Admin services (`traefik`, `grafana`, `code`, `sonarr`, `radarr`, etc.): `two_factor` — `group:administrators` only
- Public bypasses: `vault`, `s3`, `status`, `photos`, `drive`, `w`, `request`
- Local network bypasses: `hass`, `jelly`, `minio`, `ollama`, `ai`, `overseerr`
- Catchall: `*.${SECRET_DEV_DOMAIN}` → `two_factor`
- API paths on many apps: bypass for unauthenticated API access

### OIDC Clients

Authelia provides OIDC SSO for:
`tailscale`, `minio`, `open-webui`, `pgadmin`, `grafana`, `outline`, `overseerr`, `komga`, `linkwarden`, `forgejo`, `litellm`

OIDC client secrets are stored in `secret.sops.yaml` as `SECRET_<APP>_OAUTH_CLIENT_SECRET`.

To add a new OIDC client, add an entry to the `identity_providers.oidc.clients` list in `kubernetes/apps/networking/authelia/app/helm-release.yaml`.

---

## Database Services

| Service | Type | Address | Purpose |
|---|---|---|---|
| CloudNative-PG | PostgreSQL operator | `defaultpg-rw.databases.svc.cluster.local:5432` | Primary relational DB for most apps |
| MariaDB | MariaDB operator | `192.168.5.15:3306` (primary) | Apps requiring MySQL |
| Redis | Redis + sentinel | `redis-lb.databases.svc.cluster.local:6379` | Session cache, queues |
| InfluxDB | InfluxDB v2 | in-cluster | Time-series metrics |

PostgreSQL cluster is managed by CloudNative-PG (`kubernetes/apps/databases/cloudnative-pg/`). Per-app databases are provisioned as `Cluster` or `Database` CRDs inside `cloudnative-pg/clusters/`.

---

## Storage

| Type | Used For |
|---|---|
| OpenEBS local-hostpath | Default StorageClass, local node storage |
| Longhorn | Replicated block storage for stateful apps |
| NFS (NAS) | Large media, backups, paperless |
| MinIO (in-cluster) | S3-compatible object storage |
| Kopia | Backup tool for PVCs |
| VolumeSnapshots | Point-in-time PVC snapshots |
| Volsync | PVC replication/backup |

NFS paths are defined as `NFS_*` variables in `cluster-settings.yaml`.

---

## Key Infrastructure Components

| Component | Namespace | Version | Purpose |
|---|---|---|---|
| Traefik | networking | v3.6.10 (chart 39.0.5) | Ingress controller |
| Authelia | networking | 4.39.13 | Authentication gateway |
| Cilium | kube-system | — | CNI + L2 announcements (MetalLB-like) |
| cert-manager | cert-manager | — | TLS certificate management (Let's Encrypt) |
| external-dns | networking | — | DNS record management (split-horizon) |
| cloudflared | networking | — | Cloudflare Tunnel for external access |
| Kyverno | kyverno | — | Policy enforcement |
| Reloader | kube-system | — | Auto-restarts pods on ConfigMap/Secret changes |
| Prometheus stack | monitoring | — | Metrics (prometheus + alertmanager + grafana) |
| Loki | monitoring | — | Log aggregation |
| Vector | monitoring | — | Log forwarding |

---

## Ragnarok Online Servers

Located in `kubernetes/apps/ragnarok/`:

| App | Address | Purpose |
|---|---|---|
| rAthena classic | `192.168.5.102` | Classic pre-re server |
| rAthena renewal | `192.168.5.103` | Renewal mechanics server |
| Hercules classic | `192.168.5.100` | Hercules-based classic server |
| Hercules renewal | `192.168.5.101` | Hercules-based renewal server |
| OpenKore | — | Bot framework (deployed as k8s workload) |

Related external repos:
```
RATHENA_ROOT   = ~/personal/rathena
OPENKORE_ROOT  = ~/personal/openkore
GOKORE_ROOT    = ~/personal/goKore
```

---

## Common Operational Tasks

### Adding a New Application

1. Create directory structure:
   ```
   kubernetes/apps/<namespace>/<app>/
       ks.yaml
       app/
           kustomization.yaml
           helm-release.yaml
           secret.sops.yaml       (if needed)
   ```

2. Add the HelmRepository to `kubernetes/flux/repositories/` if not present.

3. Add the app's `ks.yaml` to the namespace `kustomization.yaml`.

4. Create and encrypt secrets:
   ```bash
   # Edit plain secret, then encrypt
   sops -e -i kubernetes/apps/<namespace>/<app>/app/secret.sops.yaml
   ```

5. Choose the correct Traefik middleware chain for the ingress annotation.

6. Set `dependsOn` in `ks.yaml` for required services (cert-manager, databases, etc.).

### Encrypting / Decrypting Secrets

```bash
# Encrypt a secret file in place
sops -e -i path/to/secret.sops.yaml

# Decrypt for editing (view only — do not save decrypted version)
sops -d path/to/secret.sops.yaml

# Edit a secret interactively
sops path/to/secret.sops.yaml
```

### Checking Flux Status

```bash
# Check all Kustomizations
flux get ks -A

# Check all HelmReleases
flux get hr -A

# Check sources
flux get sources git -A
flux get sources oci -A

# Force reconcile
flux reconcile ks <name> -n flux-system --with-source

# Force reconcile a HelmRelease
flux reconcile hr <name> -n <namespace>
```

### Debugging a Failing Pod

```bash
kubectl -n <namespace> get pods -o wide
kubectl -n <namespace> logs <pod> -f
kubectl -n <namespace> describe pod <pod>
kubectl -n <namespace> get events --sort-by='.metadata.creationTimestamp'
```

### Talos Maintenance

```bash
# Regenerate Talos config after talconfig.yaml change
task talos:generate-config

# Apply config to a node
task talos:apply-node HOSTNAME=<node> MODE=auto

# Upgrade Talos on a node
task talos:upgrade-node HOSTNAME=<node>

# Upgrade Kubernetes version
task talos:upgrade-k8s

# Reset cluster to maintenance mode
task talos:reset
```

### Bootstrap Commands

```bash
# Install Talos and bootstrap the cluster
task bootstrap:talos

# Install Flux
task bootstrap:flux

# Validate all manifests
task kubernetes:kubeconform
```

---

## Updating Application Versions

Most version updates come through Renovate PRs automatically. To update manually:

1. Edit `version:` in the `helm-release.yaml` chart spec (chart version).
2. Edit `tag:` in the `values.image` section (container image version).
3. Commit and push — Flux will reconcile within the `interval` period.

For Authelia specifically — the chart (`version`) and image (`tag`) are versioned independently. The chart version is `0.10.x` while image is `4.x.x`.

---

## SOPS / Secrets Reference

Secrets in `secret.sops.yaml` files are mounted into pods as Kubernetes Secrets. Flux decrypts them during reconciliation using the age key.

**Never add actual secret values to this document.** Variable names stored in cluster secrets include:

```
SECRET_DEV_DOMAIN                    primary cluster domain
SECRET_AWS_SMTP_HOST / PORT          SMTP server
SECRET_AWS_SMTP_USERNAME
SECRET_AWS_SMTP_FROM_ADDR
LDAP_PASSWORD                        Authelia LDAP bind password
SECRET_<APP>_OAUTH_CLIENT_SECRET     OIDC client secrets per app
STORAGE_ENCRYPTION_KEY               Authelia DB encryption key
SESSION_SECRET                       Authelia session key
OIDC_HMAC_SECRET                     Authelia OIDC HMAC
```

---

## Common Mistakes to Avoid

### 1. Using hardcoded IPs or domains

```yaml
# WRONG
host: 192.168.5.12
domain: example.com

# CORRECT
host: ${SVC_TRAEFIK_ADDR}
domain: ${SECRET_DEV_DOMAIN}
```

### 2. Referencing wrong middleware namespace

```yaml
# WRONG — namespace missing or wrong
middlewares: chain-authelia@kubernetescrd

# CORRECT — must include namespace prefix
middlewares: networking-chain-authelia@kubernetescrd
```

### 3. Forgetting dependsOn for database-backed apps

Apps that need PostgreSQL, Redis, or MariaDB must declare them in `ks.yaml`:
```yaml
dependsOn:
  - name: cloudnative-pg
    namespace: flux-system
  - name: redis
    namespace: flux-system
```

### 4. Not adding app to namespace kustomization.yaml

Every new app's `ks.yaml` must be listed in the parent `kustomization.yaml` for its namespace, or Flux will never see it.

### 5. Committing a decrypted secret.sops.yaml

SOPS-encrypted files contain `sops:` metadata at the bottom. A decrypted file has no `sops:` block. **Never commit decrypted secrets.**

### 6. Using `latest` image tags

Renovate cannot manage `latest` tags and Flux will not redeploy on image changes without a digest. Always use explicit versioned tags.

---

## Flux Sync Architecture

```
GitRepository (home-ops → this repo)
    ↓
Kustomization: flux-system (kubernetes/flux/)
    ↓ vars substitution from cluster-settings.yaml + secret.sops.yaml
Kustomization: apps (kubernetes/flux/apps.yaml → kubernetes/apps/)
    ↓
Per-namespace Kustomizations
    ↓
Per-app Kustomizations (ks.yaml files)
    ↓
HelmRelease resources
    ↓ HelmRepository sources
Deployed Helm charts
```

Variable substitution happens at the `apps` Kustomization level, injecting all `${VAR}` placeholders throughout the entire `kubernetes/apps/` tree.

---

## bjw-s app-template

**app-template is used for the majority (~60+) of all app deployments in this cluster.** It is the default chart whenever an upstream Helm chart does not exist or is not preferred.

### What it is

**app-template** is a Helm chart by [bjw-s](https://github.com/bjw-s-labs/helm-charts) that wraps a common library chart. Instead of bundling opinionated app-specific logic, it exposes a generic `values.yaml` schema that can deploy *any* containerized application by configuring controllers, containers, services, ingresses, and persistence in a uniform way.

### Version in this cluster

The cluster currently uses **app-template `4.3.0`** (some older apps may still be on `3.x`). The chart is fetched from the `bjw-s` HelmRepository (Helm repo at `https://bjw-s-labs.github.io/helm-charts`).

```yaml
# How to reference it in a HelmRelease
chart:
  spec:
    chart: app-template
    version: 4.3.0
    sourceRef:
      kind: HelmRepository
      name: bjw-s
      namespace: flux-system
```

### Documentation links

| Resource | URL |
|---|---|
| Official docs | https://bjw-s-labs.github.io/helm-charts/docs/app-template/ |
| Common library docs (storage, mounts, etc.) | https://bjw-s-labs.github.io/helm-charts/docs/common-library/ |
| Persistence global options | https://bjw-s-labs.github.io/helm-charts/docs/common-library/storage/globalOptions/ |
| Persistence types reference | https://bjw-s-labs.github.io/helm-charts/docs/common-library/storage/types/persistentVolumeClaim/ |
| Upgrade instructions | https://bjw-s-labs.github.io/helm-charts/docs/app-template/upgrade-instructions/ |
| Source values.yaml | https://github.com/bjw-s-labs/helm-charts/blob/main/charts/library/common/values.yaml |
| JSON schema (for IDE validation) | https://raw.githubusercontent.com/bjw-s-labs/helm-charts/app-template-4.6.2/charts/other/app-template/values.schema.json |
| Kubesearch (find real-world examples) | https://kubesearch.dev |

Add this header comment to any `helm-release.yaml` to get IDE schema validation:
```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/bjw-s-labs/helm-charts/app-template-4.6.2/charts/other/app-template/values.schema.json
```

---

### Top-level values.yaml structure

```yaml
# ── Pod-level defaults (applied to all pods/controllers) ──────────────────
defaultPodOptions:
  nodeSelector: {}
  securityContext: {}        # fsGroup, runAsUser, runAsGroup, etc.
  annotations: {}
  tolerations: []
  affinity: {}
  dnsPolicy: ""

# ── Controllers (one per workload, maps to a Deployment/StatefulSet/etc.) ──
controllers:
  <controller-name>:        # arbitrary name; "main" is conventional
    type: deployment        # deployment | statefulset | daemonset | cronjob | job
    replicas: 1
    strategy: RollingUpdate # RollingUpdate | Recreate (use Recreate for single-replica stateful apps)
    annotations: {}         # pod template annotations (e.g. reloader)

    initContainers:
      <name>:
        image: {}
        env: {}
        envFrom: []
        command: []
        args: []

    containers:
      <container-name>:     # "main" is conventional for the primary container
        image:
          repository: ""
          tag: ""
          pullPolicy: IfNotPresent
        env: {}             # key: value  OR  key: valueFrom: secretKeyRef: ...
        envFrom: []         # - secretRef: {name: ...}  OR  - configMapRef: {name: ...}
        args: []
        command: []
        resources:
          requests: {}
          limits: {}
        probes:
          liveness:
            enabled: false
          readiness:
            enabled: false
          startup:
            enabled: false
        securityContext: {}

    # StatefulSet-only: inline volumeClaimTemplates
    statefulset:
      volumeClaimTemplates:
        - name: config
          accessMode: ReadWriteOnce
          size: 5Gi
          storageClass: longhorn
          globalMounts:
            - path: /config

    # pod-level fields that apply within this controller
    pod:
      imagePullSecrets: []

# ── Services ──────────────────────────────────────────────────────────────
service:
  <service-name>:           # "main" is conventional
    controller: main        # which controller this service targets (default: same name)
    primary: true           # marks this as the default service for ingress refs
    type: ClusterIP         # ClusterIP | LoadBalancer | NodePort
    loadBalancerIP: ""
    externalTrafficPolicy: Cluster
    annotations: {}
    labels: {}
    ports:
      <port-name>:          # "http" is conventional
        port: 8080          # service port
        targetPort: 8080    # container port (defaults to port)
        protocol: TCP
        enabled: true

# ── Ingresses ─────────────────────────────────────────────────────────────
ingress:
  <ingress-name>:           # "main" is conventional
    enabled: true
    className: traefik
    annotations: {}
    hosts:
      - host: app.example.com
        paths:
          - path: /
            pathType: Prefix
            service:
              identifier: main   # references the service name above
              port: http         # references the port name above
    tls:
      - hosts:
          - app.example.com
        secretName: app.example.com

# ── Persistence (storage) ─────────────────────────────────────────────────
persistence:
  <volume-name>:
    enabled: true
    type: persistentVolumeClaim   # see persistence types below
    # ... type-specific fields
    globalMounts:
      - path: /config
    # OR
    advancedMounts: {}

# ── ConfigMaps (inline, chart-managed) ────────────────────────────────────
configMaps:
  <name>:
    enabled: true
    data:
      myfile.conf: |
        key=value

# ── Global name override ───────────────────────────────────────────────────
global:
  nameOverride: ""

# ── Pod-level fields (top-level, applied to all controllers) ──────────────
podAnnotations: {}
podLabels: {}
tolerations: []
priorityClassName: ""
```

---

### Persistence Types

All persistence entries go under the top-level `persistence:` key. Each entry is a named volume. The `type` field determines the storage backend.

#### Mount targeting: `globalMounts` vs `advancedMounts`

| Field | Behavior |
|---|---|
| `globalMounts` | Mounts the volume at the given path(s) in **all** containers across **all** controllers. Default mount path is `/<volume-name>` if omitted. |
| `advancedMounts` | Mounts only to specific controller + container combinations. Required when different containers need different paths for the same volume. |

```yaml
# globalMounts — mounts to every container
persistence:
  config:
    type: persistentVolumeClaim
    existingClaim: myapp-config
    globalMounts:
      - path: /config

# advancedMounts — mounts only to a specific controller+container
persistence:
  config-file:
    type: configMap
    name: myapp-config
    advancedMounts:
      main:           # controller name
        app:          # container name
          - path: /etc/myapp/config.yaml
            subPath: config.yaml
            readOnly: true
```

#### Type: `persistentVolumeClaim` (most common)

Use for persistent application data backed by a StorageClass.

**Sub-type A: existing pre-created PVC**
```yaml
persistence:
  config:
    type: persistentVolumeClaim
    existingClaim: myapp-config-volume   # name of pre-existing PVC
    globalMounts:
      - path: /config
```

**Sub-type B: dynamically provisioned PVC (chart creates it)**
```yaml
persistence:
  data:
    type: persistentVolumeClaim
    accessMode: ReadWriteOnce
    size: 20Gi
    storageClass: longhorn               # omit for default StorageClass (openebs-hostpath)
    retain: true                         # keep PVC on helm uninstall
    globalMounts:
      - path: /var/app/data
```

**Sub-type C: StatefulSet inline volumeClaimTemplates (preferred for StatefulSets)**

StatefulSets should use `statefulset.volumeClaimTemplates` instead of top-level `persistence` for the primary data volume. This creates a PVC per replica:

```yaml
controllers:
  main:
    type: statefulset
    statefulset:
      volumeClaimTemplates:
        - name: config
          accessMode: ReadWriteOnce
          size: 5Gi
          storageClass: longhorn
          labels:
            snapshot.home.arpa/enabled: 'true'   # opt into VolumeSnapshot backups
          globalMounts:
            - path: /config
```

**Which storage class to use:**

| StorageClass | Use case |
|---|---|
| *(omit / default)* | `openebs-hostpath` — local node storage, fast, no replication. Fine for single-node workloads. |
| `longhorn` | Replicated block storage. Use for stateful apps that need HA or remote backup. |

#### Type: `nfs`

Mount a NAS share directly. No PVC required. **Cannot specify mount options** — use a PVC-backed NFS PV if you need mount options.

```yaml
persistence:
  media:
    type: nfs
    server: ${NAS_ADDR}           # use the cluster variable
    path: /volume1/omoikane
    globalMounts:
      - path: /media
```

#### Type: `emptyDir`

Ephemeral scratch space — cleared when the pod is deleted. Use for caches, `/tmp`, transcoding scratch, shared memory.

```yaml
persistence:
  transcode:
    type: emptyDir
    globalMounts:
      - path: /transcode

  # In-memory emptyDir (tmpfs) with size limit:
  shm:
    type: emptyDir
    medium: Memory
    sizeLimit: 4Gi
    globalMounts:
      - path: /dev/shm
```

#### Type: `configMap`

Mount a Kubernetes ConfigMap as a volume. The ConfigMap must already exist (or be created by the chart's inline `configMaps:` block).

```yaml
persistence:
  config-file:
    type: configMap
    name: myapp-config            # name of the ConfigMap
    defaultMode: 0644             # file permissions (octal)
    globalMounts:
      - path: /etc/myapp/config.yaml
        subPath: config.yaml      # mount only this key as a file
```

#### Type: `secret`

Mount a Kubernetes Secret as a volume. The Secret must already exist.

```yaml
persistence:
  tunnel:
    type: secret
    name: cloudflared             # name of the Secret
    defaultMode: 0400
    globalMounts:
      - path: /etc/cloudflared/tunnel.json
        subPath: tunnel.json
```

#### Type: `hostPath`

Mount a path directly from the node. Use sparingly — requires node affinity to be useful. Common use case: USB/serial devices.

```yaml
persistence:
  usb:
    type: hostPath
    hostPath: /dev/serial/by-id/usb-Zooz_800_Z-Wave_Stick_533D004242-if00
    hostPathType: CharDevice
    globalMounts:
      - path: /dev/zwave
```

---

### Multiple subPaths from one volume

When you need to mount different directories of a single PVC to different paths, use multiple entries under `globalMounts`:

```yaml
persistence:
  data:
    type: persistentVolumeClaim
    existingClaim: myapp-data
    globalMounts:
      - path: /var/app/public
        subPath: public
      - path: /var/app/storage
        subPath: storage
      - path: /var/app/tmp/imports
        subPath: imports
```

---

### Environment Variables

```yaml
containers:
  main:
    # Inline key/value:
    env:
      TZ: America/Los_Angeles
      MY_VAR: "some-value"

    # Value from a Flux variable substitution:
    env:
      DOMAIN: ${SECRET_DEV_DOMAIN}

    # Value from a Secret key:
    env:
      DB_PASSWORD:
        valueFrom:
          secretKeyRef:
            name: myapp-secret
            key: password

    # Value from a field reference (downward API):
    env:
      - name: POD_NAME
        valueFrom:
          fieldRef:
            fieldPath: metadata.name
      - name: NAMESPACE
        valueFrom:
          fieldRef:
            fieldPath: metadata.namespace

    # Bulk-load all keys from a Secret:
    envFrom:
      - secretRef:
          name: myapp-secret

    # Bulk-load all keys from a ConfigMap:
    envFrom:
      - configMapRef:
          name: myapp-config
```

---

### Controller Types

| Type | Kubernetes resource | Use case |
|---|---|---|
| `deployment` | Deployment | Default. Stateless apps, multiple replicas. |
| `statefulset` | StatefulSet | Apps needing stable network identity or per-replica PVCs. |
| `daemonset` | DaemonSet | Run one pod per node (agents, log forwarders). |
| `cronjob` | CronJob | Scheduled tasks. |
| `job` | Job | One-off tasks. |

For single-replica stateful apps (most homelab services), `deployment` with `strategy: Recreate` is simpler than a StatefulSet:

```yaml
controllers:
  main:
    type: deployment
    strategy: Recreate     # stop old pod before starting new one (avoids PVC conflict)
```

---

### Reloader integration

When a ConfigMap or Secret changes, Kubernetes does not automatically restart pods. Use **Reloader** annotations so pods restart automatically:

```yaml
controllers:
  main:
    annotations:
      reloader.stakater.com/auto: "true"       # watch all mounted secrets/configmaps

# OR — watch specific resources:
podAnnotations:
  secret.reloader.stakater.com/reload: "myapp-secret"
  configmap.reloader.stakater.com/reload: "myapp-config"
```

---

### Security context

Applied at pod level via `defaultPodOptions.securityContext` (affects all containers) or at container level via `containers.<name>.securityContext`:

```yaml
defaultPodOptions:
  securityContext:
    runAsUser: 568          # APP_UID from cluster-settings.yaml
    runAsGroup: 568         # APP_GID from cluster-settings.yaml
    fsGroup: 568
    fsGroupChangePolicy: OnRootMismatch   # faster than Always for large volumes

controllers:
  main:
    containers:
      main:
        securityContext:
          readOnlyRootFilesystem: true
          allowPrivilegeEscalation: false
          capabilities:
            drop:
              - ALL
```

---

### Complete minimal example

A simple stateless app with ClusterIP service, Authelia-protected ingress, and a pre-existing PVC:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/bjw-s-labs/helm-charts/app-template-4.6.2/charts/other/app-template/values.schema.json
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: &app myapp
  namespace: home
spec:
  interval: 15m
  chart:
    spec:
      chart: app-template
      version: 4.3.0
      sourceRef:
        kind: HelmRepository
        name: bjw-s
        namespace: flux-system
  values:
    defaultPodOptions:
      nodeSelector:
        node-role.kubernetes.io/worker: "true"
      securityContext:
        runAsUser: 568
        runAsGroup: 568
        fsGroup: 568
        fsGroupChangePolicy: OnRootMismatch

    controllers:
      main:
        strategy: Recreate
        annotations:
          reloader.stakater.com/auto: "true"
        containers:
          main:
            image:
              repository: ghcr.io/someuser/myapp
              tag: 1.2.3
            env:
              TZ: ${TIMEZONE}
            envFrom:
              - secretRef:
                  name: *app
            resources:
              requests:
                cpu: 10m
                memory: 128Mi
              limits:
                memory: 512Mi

    service:
      main:
        primary: true
        ports:
          http:
            port: 8080

    ingress:
      main:
        enabled: true
        className: traefik
        annotations:
          cert-manager.io/cluster-issuer: letsencrypt-production
          traefik.ingress.kubernetes.io/router.entrypoints: websecure
          traefik.ingress.kubernetes.io/router.middlewares: networking-chain-authelia@kubernetescrd
          hajimari.io/enable: "true"
          hajimari.io/icon: application
          hajimari.io/group: Home
        hosts:
          - host: &uri myapp.${SECRET_DEV_DOMAIN}
            paths:
              - path: /
                pathType: Prefix
                service:
                  identifier: main
                  port: http
        tls:
          - hosts:
              - *uri
            secretName: *uri

    persistence:
      config:
        type: persistentVolumeClaim
        existingClaim: myapp-config-volume
        globalMounts:
          - path: /config
```

---

### Common app-template mistakes

**1. Wrong service reference in ingress paths (v4)**

In app-template v4, ingress path service references use `identifier` (the service name key), not `name`:

```yaml
# WRONG (v3 style)
service:
  port: http

# CORRECT (v4 style)
service:
  identifier: main    # the key under service:
  port: http          # the port name
```

**2. Controller and service name mismatch**

The service's `controller` field must match the controller key name. If omitted, it defaults to the service's own key name:

```yaml
service:
  app:                  # service named "app"
    controller: main    # explicitly targets controller named "main"
    ports:
      http:
        port: 3000
```

**3. Using `persistentVolumeClaim` type for a StatefulSet primary volume**

StatefulSets should use `statefulset.volumeClaimTemplates` for their primary storage. Using top-level `persistence` works but creates a single shared PVC — not per-replica templates.

**4. `globalMounts` mounts to ALL containers including sidecars**

If you have a sidecar container that should NOT get a volume, use `advancedMounts` instead of `globalMounts` to target only the main container.

**5. Forgetting `strategy: Recreate` for single-replica PVC mounts**

With `RollingUpdate` (default), Kubernetes tries to start the new pod before terminating the old one. If the PVC is `ReadWriteOnce`, the new pod can't mount it until the old pod releases it — causing the rollout to stall. Always use `Recreate` for single-replica apps with RWO PVCs.

**6. `defaultMode` needs to be decimal, not octal**

YAML does not natively support octal literals without the `0o` prefix. Write as integer:

```yaml
# CORRECT in YAML
defaultMode: 0644    # this is interpreted as decimal 644, NOT octal 0644
# To express octal 0644 (420 decimal):
defaultMode: 420
```

However, in practice the apps in this repo use `0644` notation and Kubernetes accepts it — because Helm/Kubernetes interpret the field as octal when it starts with 0. Be consistent with what is already used in the repo (the `0NNN` form).

**7. Missing `primary: true` on service**

If there are multiple services, exactly one must have `primary: true`. Ingresses use the primary service by default when no explicit `identifier` is given.

---

## Secrets and OPSEC

### CRITICAL: Never expose secret values to an LLM

**Treat this as an absolute rule with no exceptions.**

An LLM (including the one reading this document) must never see the plaintext content of any secret. This means:

- **Never paste decrypted secret contents into a chat or prompt.**
- **Never run `sops -d` and share the output with an LLM.**
- **Never ask an LLM to help you "fill in" a secret file with real values.**
- **Never show `kubectl get secret -o yaml` output to an LLM** — that base64 is trivially decodable.
- **Never commit a file without the `ENC[...]` markers** — if the `sops:` block at the bottom is missing, the file is decrypted.

The LLM's job is to help with structure, schema, and YAML shape — never with the values themselves. If you need to add a new secret key, you tell the LLM *what key name* is needed; you supply the value yourself in your terminal.

---

### How SOPS works in this repo

SOPS encrypts specific fields inside YAML files using an age key. The `.sops.yaml` config at the repo root controls which files are encrypted and which fields within them:

```yaml
# .sops.yaml
creation_rules:
  - path_regex: talos/.*\.sops\.ya?ml
    key_groups:
      - age:
          - "age1rr569v9jm7ck70q4wpnspfhdvt4y5m6s604tx0ygs0a65qkt7g4qdszk6k"
  - path_regex: kubernetes/.*\.sops\.ya?ml
    encrypted_regex: "^(data|stringData)$"   # only encrypts data/stringData fields
    key_groups:
      - age:
          - "age1rr569v9jm7ck70q4wpnspfhdvt4y5m6s604tx0ygs0a65qkt7g4qdszk6k"
```

Key points:
- Only fields matching `encrypted_regex` (`data` and `stringData`) are encrypted — `metadata`, `kind`, `apiVersion` remain plaintext.
- The age public key is safe to be in the repo. Only the private key (in `age.key`, gitignored) can decrypt.
- `age.key` is stored at the repo root and is **never committed** (see `.gitignore`).

An encrypted secret file looks like this — all values are `ENC[AES256_GCM,...]` ciphertext:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: myapp
  namespace: home
stringData:
  MY_PASSWORD: ENC[AES256_GCM,data:zsq0EI...,iv:UbcK...,tag:bQxK...,type:str]
sops:
  age:
    - recipient: age1rr569v9jm7ck70q4wpnspfhdvt4y5m6s604tx0ygs0a65qkt7g4qdszk6k
      enc: |
        -----BEGIN AGE ENCRYPTED FILE-----
        ...
        -----END AGE ENCRYPTED FILE-----
  encrypted_regex: ^(data|stringData)$
  version: 3.8.1
```

A file is safe to commit **if and only if** every value under `data`/`stringData` is `ENC[...]` ciphertext and the `sops:` block is present.

---

### Workflow: creating a new secret file

The LLM writes the skeleton (keys, metadata, structure). **You** supply the values in your terminal.

**Step 1 — LLM writes the skeleton with placeholder values:**

The LLM produces a file like:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: myapp
  namespace: home
stringData:
  DB_PASSWORD: PLACEHOLDER
  API_KEY: PLACEHOLDER
  SECRET_TOKEN: PLACEHOLDER
```

**Step 2 — You open the file in your terminal and replace placeholders with real values:**

```bash
# Open the file directly in your editor — never share this screen with an LLM
$EDITOR kubernetes/apps/home/myapp/app/secret.sops.yaml
```

Fill in real values, save, then close.

**Step 3 — Encrypt in place with `sops -e -i`:**

```bash
sops --encrypt --in-place kubernetes/apps/home/myapp/app/secret.sops.yaml
```

The `-i` / `--in-place` flag overwrites the file with its encrypted form. After this command, the file is safe to commit. All `stringData` values will be `ENC[...]` ciphertext.

**Step 4 — Verify the file is encrypted before committing:**

```bash
# Safe: should show ENC[...] values, not plaintext
grep -c "ENC\[" kubernetes/apps/home/myapp/app/secret.sops.yaml

# Safe: confirm the sops block is present
grep "^sops:" kubernetes/apps/home/myapp/app/secret.sops.yaml
```

If `grep -c "ENC["` returns 0, the file is NOT encrypted. Do not commit it.

---

### Workflow: editing an existing secret

**Option A — Edit interactively (recommended):**

```bash
sops kubernetes/apps/home/myapp/app/secret.sops.yaml
```

This decrypts into a temp file, opens your `$EDITOR`, and re-encrypts on save. The plaintext **never touches disk** in a permanent file. This is the safest method.

**Option B — Decrypt, edit, re-encrypt:**

```bash
# 1. Decrypt in place — FILE IS NOW PLAINTEXT, do not commit
sops --decrypt --in-place kubernetes/apps/home/myapp/app/secret.sops.yaml

# 2. Edit with your editor
$EDITOR kubernetes/apps/home/myapp/app/secret.sops.yaml

# 3. Re-encrypt in place IMMEDIATELY after editing
sops --encrypt --in-place kubernetes/apps/home/myapp/app/secret.sops.yaml

# 4. Verify
grep "^sops:" kubernetes/apps/home/myapp/app/secret.sops.yaml
```

**Never leave a decrypted file unattended.** If you walk away from your terminal mid-edit, run `sops --encrypt --in-place` before doing anything else.

**Option C — `sops -d` to stdout (read-only, non-destructive):**

```bash
# Prints decrypted content to stdout — useful for inspecting values yourself
# Never share this output with an LLM or paste it anywhere
sops --decrypt kubernetes/apps/home/myapp/app/secret.sops.yaml
```

---

### Workflow: adding a new key to an existing secret

```bash
# Open the encrypted file interactively — sops handles decrypt/re-encrypt
sops kubernetes/apps/home/myapp/app/secret.sops.yaml
```

Your editor opens the decrypted YAML. Add the new key with its real value, save, and close. SOPS re-encrypts automatically.

---

### Git safeguards

`.gitignore` excludes the age private key and decrypted temp files:

```
age.key          # private key — NEVER committed
*.agekey         # any age key files
.decrypted~*.yaml  # sops temp files
kubeconfig       # cluster credentials
talosconfig      # talos node credentials
```

`.gitattributes` marks SOPS files for diff display:

```
*.sops.* diff=sopsdiffer
```

This means `git diff` on a `.sops.yaml` shows the SOPS-aware diff (field names only, not plaintext values) rather than raw ciphertext churn.

**Before every commit involving secret files:**

```bash
# Check no file has plaintext data fields
git diff --staged | grep -E "^\+" | grep -v "ENC\[" | grep -E "(password|secret|key|token|api)" --ignore-case
```

If that returns matches, a secret file may have been staged while decrypted. Abort the commit and re-encrypt.

---

### What the LLM CAN safely do with secrets

| Safe | Not safe |
|---|---|
| Write the schema/structure of a `secret.sops.yaml` with placeholder values | Read, display, or process any decrypted secret file |
| Tell you which key names are needed | Suggest or generate actual secret values |
| Explain how to reference a secret key in a HelmRelease (`secretKeyRef`) | See the output of `sops -d` or `kubectl get secret -o yaml` |
| Show what an encrypted file looks like structurally | Have any file containing real credentials passed to it as context |
| Help add a new secret reference in a `helm-release.yaml` | Assist with any task that requires knowing the plaintext value |

**When working on a task involving secrets, the correct workflow is:**

1. LLM writes the HelmRelease and the secret skeleton (with `PLACEHOLDER` values).
2. You close the LLM session or scroll up past the skeleton.
3. You open the skeleton in your terminal, fill in real values, and run `sops --encrypt --in-place`.
4. You return to the LLM for any remaining non-secret work (ingress, persistence, etc.).

---

### SOPS command reference

```bash
# Interactive edit (safest — never writes plaintext to disk)
sops path/to/secret.sops.yaml

# Encrypt a plaintext file in place
sops --encrypt --in-place path/to/secret.sops.yaml

# Decrypt a file in place (DANGER — file becomes plaintext)
sops --decrypt --in-place path/to/secret.sops.yaml

# Decrypt to stdout only (no file written)
sops --decrypt path/to/secret.sops.yaml

# Create a new encrypted file from scratch
# Write plaintext first, then:
sops --encrypt --in-place path/to/new-secret.sops.yaml

# Rotate encryption key (re-encrypt with updated age keys)
sops --rotate --in-place path/to/secret.sops.yaml

# Check what SOPS would encrypt without doing it
sops --encrypt path/to/secret.sops.yaml   # prints to stdout, no file change
```

**Short flags:**
- `-e` = `--encrypt`
- `-d` = `--decrypt`
- `-i` = `--in-place`
- `-r` = `--rotate`

So `sops -e -i file.yaml` and `sops --encrypt --in-place file.yaml` are identical.

---

### Anatomy of a secret.sops.yaml file

Every app secret follows this exact structure:

```yaml
apiVersion: v1
kind: Secret
type: Opaque
metadata:
  name: myapp          # must match the name referenced in helm-release.yaml envFrom/secretRef
  namespace: home      # must match the app's namespace
stringData:            # ← this field is what SOPS encrypts (per encrypted_regex in .sops.yaml)
  KEY_ONE: ENC[AES256_GCM,data:...,iv:...,tag:...,type:str]
  KEY_TWO: ENC[AES256_GCM,data:...,iv:...,tag:...,type:str]
sops:
  age:
    - recipient: age1rr569v9jm7ck70q4wpnspfhdvt4y5m6s604tx0ygs0a65qkt7g4qdszk6k
      enc: |
        -----BEGIN AGE ENCRYPTED FILE-----
        ...
        -----END AGE ENCRYPTED FILE-----
  encrypted_regex: ^(data|stringData)$
  version: 3.8.1
```

**Use `stringData` not `data`.** SOPS encrypts the raw string values. If you use `data`, you'd need to base64-encode values first — unnecessary complexity.

**The Secret `name` must exactly match** what is referenced in the HelmRelease. For example, if the helm-release has:

```yaml
envFrom:
  - secretRef:
      name: myapp
```

Then `metadata.name` in the secret must be `myapp`.

---

### Cluster-wide secrets (flux/vars/secret.sops.yaml)

The file `kubernetes/flux/vars/secret.sops.yaml` is a special Secret named `cluster-secrets` in `flux-system`. Its keys become available as `${KEY_NAME}` variables everywhere in `kubernetes/apps/` via Flux variable substitution.

Adding a new cluster-wide variable:

```bash
# 1. Edit interactively
sops kubernetes/flux/vars/secret.sops.yaml

# 2. Add your new key under stringData:
#    NEW_SECRET_KEY: actual-value-here

# 3. Save and close — SOPS re-encrypts automatically

# 4. Reference it anywhere in kubernetes/apps/:
#    someField: ${NEW_SECRET_KEY}
```

Non-sensitive cluster-wide variables go in `kubernetes/flux/vars/cluster-settings.yaml` (unencrypted ConfigMap) — only put things in `secret.sops.yaml` that are genuinely secret.
