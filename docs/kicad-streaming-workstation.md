# KiCad Streaming Workstation

Browser (Selkies-GStreamer WebRTC) and native-client (Sunshine + Moonlight)
access to a KiCad 9 desktop running on the cluster, with an LLM integration
path via MCP. Optimised for Intel iGPU (NUC8i5 / Iris Plus 655) using
VAAPI/Quick Sync hardware encoding.

This is the operator-facing runbook. For high-level architecture and how to
plug a new LLM client in, read this file in full before deploying.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│ Namespace: home                                                       │
│                                                                       │
│ Pod: kicad-0  (StatefulSet, replicas=1)                              │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Container: kicad-desktop (ghcr.io/lenaxia/kicad-desktop)        │  │
│  │  supervisord                                                   │  │
│  │   ├─ Xvfb              :20  (software X server)                │  │
│  │   ├─ Xfce4 + IceWM          (window managers)                  │  │
│  │   ├─ KiCad 9           (eeschema + pcbnew, auto-launched)      │  │
│  │   ├─ Selkies-GStreamer → NGINX :8080 (browser WebRTC, VAAPI)   │  │
│  │   ├─ Sunshine          :47984-48010 (Moonlight host, VAAPI)    │  │
│  │   ├─ pipewire + pulseaudio                                     │  │
│  │   └─ coturn          :3478 (TURN relay, optional for LAN)      │  │
│  │                                                                 │  │
│  │  /dev/dri via gpu.intel.com/i915 resource                      │  │
│  │  /config     5Gi  Longhorn RWO  (KiCad config + Sunshine state)│  │
│  │  /projects   50Gi Longhorn RWX  (KiCad designs, shared)        │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│ Pod: kicad-mcp-XXXX  (Deployment, replicas=1)                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Container: kicad-mcp (ghcr.io/lenaxia/kicad-mcp)                │  │
│  │  supergateway :8000 (HTTP/SSE)                                  │  │
│  │   └─ python3 -m kicad_mcp (stdio MCP server)                    │  │
│  │  Bundles: kicad-cli, kibot, pcbnew Python bindings              │  │
│  │  Mounts: /projects (same RWX PVC as kicad-0)                    │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│ Job: kicad-kibot-XXXX (template; triggered on demand)                │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Container: kicad9_auto_full (ghcr.io/inti-cmnb/kicad9_auto_full)│  │
│  │  Runs kibot -c config.kibot.yaml against /projects/$PROJECT     │  │
│  │  Outputs → /projects/$PROJECT/fab/                              │  │
│  │  ERC + DRC + Gerbers + Excellon + JLC BOM + JLC CPL + iBoM      │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│ Services:                                                             │
│   kicad-selkies   ClusterIP    :8080  → Traefik IngressRoute         │
│   kicad-sunshine  LoadBalancer 47984-48010 (TCP+UDP), pinned to      │
│                              192.168.5.18 (SVC_KICAD_SUNSHINE_ADDR)  │
│   kicad-metrics   ClusterIP    :9081  → ServiceMonitor → Prometheus  │
│   kicad-mcp       ClusterIP    :8000  (SSE)                          │
│                                                                       │
│ Ingress:                                                              │
│   https://kicad.${SECRET_DEV_DOMAIN}/   → Authelia → Selkies browser  │
└──────────────────────────────────────────────────────────────────────┘
                                  ▲
                                  │ in-cluster HTTP/SSE
                                  │
                       ┌──────────┴───────────┐
                       │ LiteLLM / Open-WebUI │
                       │   (existing pods)    │
                       └──────────────────────┘
```

### Why this shape

| Decision | Why |
|---|---|
| **Selkies + Sunshine in the SAME container** | Both attach to the same `$DISPLAY`. UNIX sockets can't cross pod boundaries, so the X server must be in the same pod as both encoders. Splitting them would require NFS-backed `/tmp/.X11-unix` which doesn't work. |
| **MCP as a separate Deployment** | The MCP server has no GUI / X server / GPU requirements. Splitting it lets the MCP pod live on any worker node and be restarted independently. It mounts the same `/projects` RWX PVC. |
| **kibot as a separate Job** | Kibot does heavy CPU work (DRC, gerber raster) that benefits from clean process lifecycle. Reusing the desktop pod would starve KiCad; reusing the MCP pod would block other MCP calls during a 10-minute kibot run. |
| **No KiCad IPC API in v1** | KiCad 9's IPC API is PCB-editor-only and **requires the GUI running** — there's no headless mode until KiCad 11 ships. The MCP server is intentionally file-based (uses `kicad-cli` + `kibot`) so it works in a headless pod today. When KiCad 11 lands, an `ipc_*` toolset will be added that connects to `/tmp/kicad/api.sock` (already mounted as an emptyDir). |

---

## Prerequisites (cluster-side)

All of these already exist in this cluster — listed here for completeness.

| Component | Where | Required because… |
|---|---|---|
| Intel GPU plugin | `kubernetes/apps/kube-system/intel-device-plugin/gpu/` | Exposes `gpu.intel.com/i915` resource → mounts `/dev/dri` into the pod. |
| NodeFeatureRule for Intel GPU | `kubernetes/apps/kube-system/node-feature-discovery/rules/` | Labels NUC8i5 nodes with `intel.feature.node.kubernetes.io/gpu=true`. |
| Longhorn | `kubernetes/apps/storage/longhorn/` | Provides the `longhorn` StorageClass used for `/config` and `/projects`. |
| Traefik | `kubernetes/apps/networking/traefik/` | Terminates TLS for the Selkies browser endpoint. |
| cert-manager | `kubernetes/apps/cert-manager/` | Issues the LE cert for `kicad.${SECRET_DEV_DOMAIN}`. |
| Authelia | `kubernetes/apps/networking/authelia/` | forward-auth on the Selkies IngressRoute. |
| Prometheus stack | `kubernetes/apps/monitoring/kube-prometheus-stack/` | Scrapes Selkies metrics via the ServiceMonitor. |
| Cilium L2 announcements | `kubernetes/apps/kube-system/cilium/config/cilium-l2.yaml` | Routes the Sunshine LoadBalancer VIP on the LAN. |

---

## Build the container images

The Dockerfiles live in [`lenaxia/containers`](https://github.com/lenaxia/containers)
under `apps/kicad-desktop/` and `apps/kicad-mcp/`. The GitHub Actions workflow
in that repo (`.github/workflows/release.yaml`) auto-builds apps whose
`apps/<name>/` directory changed on `main`. To build manually:

```bash
git clone https://github.com/lenaxia/containers.git
cd containers

# Local build (amd64 only — image is amd64-only by design)
docker buildx bake image-local

# Push a release (CI does this on merge to main)
git commit -am "release(kicad): v0.1.0" && git push origin main
```

The Job image (`ghcr.io/inti-cmnb/kicad9_auto_full:1.9.0`) is pulled directly
from upstream — no build needed.

Image digests are intentionally **not** pinned in the HelmReleases so Renovate
can manage them; pin via `tag: 0.1.0@sha256:...` once the first build is out.

---

## Deploy

### 1. Fill in the SOPS secrets

```bash
cd talos-ops-prod

# Edit each skeleton in your editor and replace PLACEHOLDER with real values.
# NEVER let an LLM see these values. NEVER commit a decrypted file.
$EDITOR kubernetes/apps/home/kicad/app/secret.sops.yaml
$EDITOR kubernetes/apps/home/kicad/mcp/app/secret.sops.yaml

# Encrypt in place.
sops -e -i kubernetes/apps/home/kicad/app/secret.sops.yaml
sops -e -i kubernetes/apps/home/kicad/mcp/app/secret.sops.yaml

# Verify BOTH files have ENC[...] values and a `sops:` block before staging.
grep -c 'ENC\[' kubernetes/apps/home/kicad/app/secret.sops.yaml    # must be > 0
grep '^sops:' kubernetes/apps/home/kicad/app/secret.sops.yaml      # must match
```

### 2. Commit and push

```bash
git add kubernetes/apps/home/kicad kubernetes/apps/home/kustomization.yaml \
        kubernetes/flux/vars/cluster-settings.yaml
git commit -m "feat(kicad): add KiCad 9 streaming workstation (Selkies + Sunshine + MCP)"
git push origin main
```

Flux reconciles within 30 minutes; force it with:

```bash
flux reconcile ks cluster-home-kicad      -n flux-system --with-source
flux reconcile ks cluster-home-kicad-mcp  -n flux-system --with-source
flux reconcile ks cluster-home-kicad-kibot -n flux-system --with-source
```

---

## First-run setup

After the pods are Running + Ready:

### Selkies (browser WebRTC)

1. Browse to `https://kicad.${SECRET_DEV_DOMAIN}/` (Authelia will challenge first).
2. Selkies' NGINX prompts for HTTP basic auth — use `ubuntu` + the
   `SELKIES_BASIC_AUTH_PASSWORD` you set in the Secret.
3. The KiCad project manager window appears. Open a project; the browser
   session shows the same X server the Moonlight client would see.

### Sunshine (Moonlight native client)

Sunshine does NOT read env vars for credentials. First-run setup is via
either the Web UI or the CLI subcommand `sunshine creds`.

**Web UI flow:**

1. Browse to `https://192.168.5.18:47990/` (self-signed cert — accept it).
2. First-run prompts you to create a username + password.
3. In Moonlight (any client), add the host `192.168.5.18` (auto-discovered
   via mDNS if the cluster's avahi/dbus is exposed; otherwise manual).
4. Moonlight shows a 4-digit PIN.
5. Back in the Web UI → "PIN" tab → enter the PIN.

**CLI flow (idempotent — safe to re-run):**

```bash
# Run inside the pod, using values from the SOPS Secret.
kubectl -n home exec -ti kicad-0 -c kicad-desktop -- \
    bash -c 'sunshine creds "$SUNSHINE_USER" "$SUNSHINE_PASS"'
```

The `SUNSHINE_USER` / `SUNSHINE_PASS` env vars come from the Secret
referenced via `envFrom` in the desktop HelmRelease. (Add this `envFrom`
block to the desktop HelmRelease if you want this one-liner to work
without manual editing — omitted in v1 because Sunshine is usually set up
once via the Web UI and never re-paired.)

### Pairing ports (reference)

| Port | Proto | Purpose |
|---|---|---|
| 47984 | TCP | HTTPS control plane (pairing handshake) |
| 47989 | TCP | HTTP control plane (plain) |
| 47990 | TCP | Web UI (HTTPS, self-signed) |
| 47998 | UDP | Video stream |
| 47999 | UDP | Control channel (input/feedback) |
| 48000 | UDP | Audio stream |
| 48010 | TCP | RTSP session setup |

All seven are exposed by the `kicad-sunshine` LoadBalancer Service.

---

## MCP integration

### Endpoint

```
http://kicad-mcp.home.svc.cluster.local:8000/sse
```

Add to LiteLLM's MCP config (or any MCP-aware client):

```yaml
mcp_servers:
  kicad:
    url: http://kicad-mcp.home.svc.cluster.local:8000/sse
    transport: sse
```

### Tools exposed

See [`apps/kicad-mcp/src/kicad_mcp/server.py`](https://github.com/lenaxia/containers/blob/main/apps/kicad-mcp/src/kicad_mcp/server.py)
for the canonical list. Summary:

- `list_kicad_projects` — discover projects under `/projects`
- `open_project` — resolve a project to its files
- `list_kibot_configs` — find `*.kibot.yaml` in a project
- `run_electrical_rules_check` — ERC via `kicad-cli sch erc`
- `run_design_rules_check` — DRC via `kicad-cli pcb drc`
- `export_gerber_files` — Gerbers via `kicad-cli pcb export gerbers`
- `export_drill_files` — Excellon / Gerber drill
- `export_step_model` — STEP 3D model
- `run_kibot_pipeline` — run a full kibot config (e.g. JLCPCB fab bundle)
- `health` — sanity probe

### Why file-based and not IPC

KiCad 9's IPC API (NNG over UNIX socket at `/tmp/kicad/api.sock`) is
**PCB-editor-only and requires the GUI running**. There is no headless
mode. KiCad 11 (not yet released as of 2026-07) adds headless IPC; the MCP
image already ships `kicad-python` (the official IPC client) and the
desktop pod already mounts `/tmp/kicad` as an emptyDir shared with the MCP
pod — so the upgrade path to native IPC is a no-op once KiCad 11 ships.

For v1 the MCP server uses `kicad-cli` + `kibot`, which work on plain
`.kicad_pcb` files without a running GUI. The trade-off is that live
in-process board edits (e.g. "place this footprint here") are not possible
via MCP yet — only file inspection + manufacturing outputs.

---

## Triggering fab jobs from the MCP layer

The kicad-kibot Job template lives in the cluster at all times (it's a
HelmRelease-managed Job with `restartPolicy: Never` and zero running pods
until triggered). Two ways to trigger it:

### Manual: `kubectl create job --from`

```bash
kubectl -n home create job --from=job/kicad-kibot \
    kicad-kibot-blinky-rev1-run1 \
    --env=PROJECT=blinky/rev1 \
    --env=KIBOT_CONFIG=config.kibot.yaml
```

### From the MCP pod: Kubernetes API

The MCP pod needs an RBAC grant to create Jobs in the `home` namespace.
v1 of the MCP image does NOT include a `trigger_fab_job` tool — the
operator triggers manually. To enable MCP-triggered jobs in v2, add:

```yaml
# In kicad/mcp/app/, add rbac.yaml:
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: kicad-mcp-job-trigger
  namespace: home
rules:
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["create", "get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: kicad-mcp-job-trigger
  namespace: home
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: kicad-mcp-job-trigger
subjects:
  - kind: ServiceAccount
    name: kicad-mcp
    namespace: home
```

Then a new MCP tool `trigger_kibot_job(project_path)` issues a
`batch/v1 Job` create against the in-cluster API. (Not included in v1 to
keep the RBAC surface minimal — opt in when ready.)

---

## Validation checklist

Run these after deployment to confirm everything works.

### Container build

```bash
# In lenaxia/containers:
docker buildx bake image-local
docker run --rm ghcr.io/lenaxia/kicad-desktop:0.1.0 kicad-cli version
docker run --rm ghcr.io/lenaxia/kicad-desktop:0.1.0 sunshine version
docker run --rm ghcr.io/lenaxia/kicad-desktop:0.1.0 vainfo
docker run --rm ghcr.io/lenaxia/kicad-desktop:0.1.0 gst-inspect-1.0 vah264enc
docker run --rm ghcr.io/lenaxia/kicad-mcp:0.1.0 kibot --version
```

### VAAPI in the pod

```bash
kubectl -n home exec -ti kicad-0 -c kicad-desktop -- vainfo
# Expect: "VAEntrypointEncSlice" for VAProfileH264High and friends.

kubectl -n home exec -ti kicad-0 -c kicad-desktop -- gst-inspect-1.0 vah264enc
# Expect: a non-empty description, no "no such element" error.
```

### Selkies browser session

```bash
# 1. Wait for the pod to be Ready.
kubectl -n home wait pod/kicad-0 --for=condition=Ready --timeout=600s

# 2. Browse to https://kicad.${SECRET_DEV_DOMAIN}/ — Authelia → Selkies
#    basic auth → KiCad project manager visible.
```

### Moonlight pairing

```bash
# 1. Web UI on https://192.168.5.18:47990/ — create admin user.
# 2. Moonlight client → add host 192.168.5.18 → PIN.
# 3. Enter PIN in Web UI. Pairing succeeds within seconds.
# 4. Stream at 1080p60 — confirm H.264/HEVC encoder in the Sunshine logs:
kubectl -n home logs kicad-0 -c kicad-desktop --tail=200 | grep -i encoder
```

### MCP server reachability

```bash
# Tool listing (curl-able from any in-cluster pod with curl):
kubectl -n home run curl-test --rm -ti --image=curlimages/curl -- \
    curl -sS http://kicad-mcp.home.svc.cluster.local:8000/healthz
# Expect: {"ok":true,"version":"0.1.0","projects_dir":"/projects","projects_found":N}

# From an LLM pod, hit the SSE endpoint with a JSON-RPC tools/list:
kubectl -n home exec -ti deploy/litellm -- \
    curl -sS -N http://kicad-mcp.home.svc.cluster.local:8000/sse
```

### KiBot Job end-to-end

```bash
# 1. Create a test project on the PVC (from the GUI or via kubectl cp):
kubectl -n home cp ./test-project kicad-0:/projects/test-project -c kicad-desktop

# 2. Copy the default kibot config in (or write your own):
kubectl -n home exec kicad-0 -c kicad-desktop -- \
    cp /etc/kibot-default/config.kibot.yaml /projects/test-project/

# 3. Trigger the Job:
kubectl -n home create job --from=job/kicad-kibot \
    kicad-kibot-test-1 --env=PROJECT=test-project

# 4. Wait for completion:
kubectl -n home wait job/kicad-kibot-test-1 --for=condition=Complete --timeout=600s

# 5. Inspect outputs:
kubectl -n home exec kicad-0 -c kicad-desktop -- ls /projects/test-project/fab/
# Expect: gerbers, excellon drill files, *_bom_jlc.csv, *_cpl_jlc.csv, *_ibom.html
```

### Manifests are app-template-based (no raw Deployments)

```bash
# Should return only HelmRelease, ConfigMap, Secret, ServiceMonitor, IngressRoute:
kubectl -n home get deployments,statefulsets,jobs,svc,ingress,ingressroute,servicemonitor \
    -l app.kubernetes.io/instance=kicad -o name
```

---

## Operational notes

### VAAPI encoder choice

| Encoder | `SELKIES_ENCODER` | Stability | Notes |
|---|---|---|---|
| Intel Quick Sync H.264 | `vah264enc` | stable | Default for NUC8i5. Best browser compatibility. |
| Intel Quick Sync HEVC | `vah265enc` | unstable | Lower bandwidth at same quality; Selkies flags as unstable. Test before relying on it. |
| Software H.264 | `x264enc` | stable | Fallback if `/dev/dri` is unavailable. High CPU. |

The `LIBVA_DRIVER_NAME=i965` env var on the desktop pod forces the i965
classic driver — correct for Iris Plus 655 (Kaby Lake R). For newer Intel
gens (Ice Lake+), switch to `iHD`.

### GPU contention

Selkies and Sunshine both encode from the same iGPU. If both are actively
streaming, expect encoder contention. Mitigations:

- Don't run both streams simultaneously (typical — pick one per session).
- If you must, drop one stream to 30 fps to halve its encoder demand.
- The NUC8i5's Iris Plus 655 has 48 execution units; it can sustain ~2
  simultaneous 1080p60 H.264 encodes before saturating.

### 3D viewer performance

Xvfb provides **software** OpenGL (llvmpipe). KiCad's 3D viewer renders on
CPU under this setup, which is fine for inspection but slow for complex
boards. Hardware-accelerated KiCad GL would require a real Intel Xorg
server or VirtualGL — neither is packaged as a turnkey Intel image
upstream. Track [selkies-project/selkies-glx-desktop#39](https://github.com/selkies-project/selkies-glx-desktop/issues)
for an Intel build.

### Backup

The `/config` and `/projects` PVCs are labelled
`snapshot.home.arpa/enabled: "true"` so they're picked up by the cluster's
VolumeSnapshot schedule. To take an ad-hoc snapshot:

```bash
kubectl -n home create volumesnapshot kicad-projects-manual \
    --class longhorn \
    --source persistentvolumeclaim/projects-kicad-0
```

---

## Troubleshooting

### Pod stuck in `ContainerCreating`

Check the intel GPU plugin is allocating:

```bash
kubectl -n home describe pod kicad-0 | grep -A5 "gpu.intel.com/i915"
kubectl get node -o json | jq '.items[].status.allocatable["gpu.intel.com/i915"]'
```

If allocatable is `0`, the Intel GPU plugin DaemonSet isn't running on the
target node, or NFD hasn't labelled it. See
`kubernetes/apps/kube-system/intel-device-plugin/gpu/` and
`kubernetes/apps/kube-system/node-feature-discovery/rules/`.

### `vainfo` errors with "libva not initialised"

The user can't open `/dev/dri/renderD128`. Check supplemental groups
(`109` for `render`, `44` for `video`) match the host node's group IDs:

```bash
# On a NUC8i5 node (via Talos `talosctl ls /dev/dri`):
stat -c '%g' /dev/dri/renderD128   # → 109 (render) on Ubuntu
```

If your node uses different GIDs, override the `supplementalGroups` list
in the desktop HelmRelease.

### Selkies session is black

`SELKIES_ENCODER=vah264enc` requires the GStreamer VA plugin. Verify:

```bash
kubectl -n home exec kicad-0 -c kicad-desktop -- gst-inspect-1.0 vah264enc
```

If empty, the image build skipped a VAAPI package. Rebuild
`ghcr.io/lenaxia/kicad-desktop` with `mesa-va-drivers` confirmed in the
final image.

### MCP `kicad-cli sch erc` hangs

`kicad-cli` (and kibot's KiAuto) need an X server even when invoked
headless. The MCP image sets `DISPLAY=:99` but doesn't actually run an
X server — `xvfb-run` is what manages it, and `kibot` invokes it
automatically via KiAuto. For direct `kicad-cli` calls that don't go
through KiAuto, wrap with `xvfb-run`:

```bash
xvfb-run -a kicad-cli pcb drc --exit-code-violations board.kicad_pcb
```

This is handled inside the `runner.py` module of the MCP image — but
worth knowing if you shell into the pod.

---

## Files added by this feature

```
talos-ops-prod/
└── kubernetes/
    ├── apps/
    │   └── home/
    │       ├── kustomization.yaml                 # +1 line: ./kicad/ks.yaml
    │       └── kicad/
    │           ├── ks.yaml                        # 3 Flux Kustomizations
    │           ├── app/                           # Desktop HelmRelease
    │           │   ├── helm-release.yaml
    │           │   ├── secret.sops.yaml           # ← ENCRYPT before commit
    │           │   ├── ingressroute.yaml          # Traefik CRD for Selkies
    │           │   ├── servicemonitor.yaml        # Selkies /metrics
    │           │   └── kustomization.yaml
    │           ├── mcp/app/                       # MCP sidecar HelmRelease
    │           │   ├── helm-release.yaml
    │           │   ├── secret.sops.yaml           # ← ENCRYPT before commit
    │           │   └── kustomization.yaml
    │           └── fab/app/                       # kibot Job template
    │               ├── helm-release.yaml
    │               ├── configmap.yaml             # Default config.kibot.yaml
    │               └── kustomization.yaml
    └── flux/
        └── vars/
            └── cluster-settings.yaml              # +SVC_KICAD_SUNSHINE_ADDR
docs/
└── kicad-streaming-workstation.md                 # This file.
```

Container images live in [`lenaxia/containers`](https://github.com/lenaxia/containers)
under `apps/kicad-desktop/` and `apps/kicad-mcp/`.
