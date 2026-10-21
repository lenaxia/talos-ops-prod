# Breaking-Change PR Deep Dive — 7 PRs

Generated: 2026-10-21 · Read-only analysis, NO changes made.
Cluster context: Talos v1.12.4 (control-plane) / v1.13.6 (workers), live K8s server v1.35.3.
Config files declare `talosVersion: v1.13.11`, `kubernetesVersion: v1.36.4` (not yet live-applied).

Legend — Risk: LOW / MED / HIGH · Safe to merge as-is? YES / NO.

---

## 1. supergateway v4 — PR #2547

- **Version:** `3.4.3-uvx` → `4.2.0-uvx` (image is digest-pinned)
- **File / line:** `kubernetes/apps/home/hass-mcp/app/helm-release.yaml:71`
  - `3.4.3-uvx@sha256:2ffee900c18d8375096b392c8be15cd344535a05b753a5b182da227ab6306a15`
  - `4.2.0-uvx@sha256:f5289d1f4c8925f6a7c9666368af5bd3b19ecb3c50ab08325f991124166b8b62`
- **Breaking changes:** v4.0.0 requires Node 20+ and makes stateful stdio→Streamable HTTP sessions expire after 30 min idle (was: never). v4.1.0 gave each SSE/WebSocket connection its own server process.
- **Relevance to this deployment:** NONE of the breaking behavior applies. The image is used **only as a uv/uvx runtime** to run `hass-mcp --http` (`command: uvx`, `args: hass-mcp ...`), NOT as a supergateway gateway (see in-file NOTE at lines 66-69). supergateway itself is never started, so Node/session/SSE changes are inert.
- **Risk:** MED — purely because the only change that actually executes is the bundled `uvx`/`uv` runtime; a runtime swap can in principle break how `uvx hass-mcp` resolves/runs. The supergateway v4 breaking changes are irrelevant.
- **Safe to merge as-is?** YES. Only verify after merge that the `home/hass-mcp` pod (`hass-mcp-6d45c44b5b-h8qjr`, running 18d) stays `1/1 Running` and the MCP endpoint on `:8000` still answers. No config change required.

---

## 2. nzbhydra2 v9 — PR #2546

- **Version:** `8.9.0` → `9.1.1`
- **File / line:** `kubernetes/apps/media/nzbhydra2/app/helm-release.yaml:40`
  - `tag: '8.9.0'` → `tag: '9.1.1'`
- **Breaking changes (v9.0.x):**
  - DB migration — 9.0.5 notes the migration **fails** if the download history references indexers that were later deleted (auto-repairs on next start). A live install with such history should migrate but is the riskiest step.
  - Settings "Results fetched per request" and "Display all retrieved results" are **gone** (replaced by pagination + "Load N more").
  - Search UI now returns everything indexers returned instead of the first 100 (memory/latency behavior change).
  - Display/user preferences moved server-side (per user) instead of browser localStorage; existing choices are taken over on first page load.
  - v9.1.1 fixes the API GUID/download-link stability regression from 9.0.0 (matters for NZBGet RSS / Sonarr / Radarr dedup).
- **Relevance:** This is a real major-version app upgrade with a DB migration, served to Sonarr/Radarr/NZBGet via its API. Pod is a `statefulset` (`nzbhydra2-0`, 44d) with a config PVC + NFS mounts, so state persists across the bump.
- **Risk:** MED — v9.1.1 is the latest patch and specifically fixes the API GUID regression, so the *latest* target is the safe one. Main residual risk is the DB migration on existing history.
- **Safe to merge as-is?** YES, with one recommended pre-step: **back up `/config` (incl. the DB) before the upgrade** — the chart mounts a `backup` volume, so confirm a backup exists/is triggered first. No file change required; the app-template values are unchanged (env, ports, PVCs all compatible).

---

## 3. kubelet v1.37.1 — PR #2368  ⚠️

- **Version:** `v1.36.4` → `v1.37.1` (declared in config; **not** the live version)
- **File / line:**
  - `kubernetes/bootstrap/talos/talconfig.yaml:6`  `kubernetesVersion: v1.36.4` → `v1.37.1`
  - `bootstrap/templates/kubernetes/bootstrap/talos/talconfig.yaml.j2:6` (same change in the template)
- **Critical findings:**
  1. **This is NOT an application container bump — it changes the Kubernetes control-plane version.** Talos embeds kube-apiserver/controller-manager/scheduler/kube-proxy. Merging only edits GitOps files; the cluster changes only when you run `talosctl upgrade` per node. So merge-by-itself = no runtime effect.
  2. **Stale / out of sync with reality.** The file currently declares `v1.36.4`, but the **live cluster is v1.35.3** (server) and Talos is v1.12.4 (CP) / v1.13.6 (worker). The repo is also **2 minor versions ahead of the live cluster** and **ahead of Talos's own built-in stack** (Talos v1.13.11 ships `kube-apiserver v1.36.3` / `kubelet v1.36.3`).
  3. **Compatibility risk:** jumping declared kubelet to v1.37.1 while Talos is v1.13.11 (built against v1.36) is unsupported/mismatched. Talos `machine.kubelet.image` is intended to track the Talos build's K8s version. Forcing v1.37.1 requires the corresponding Talos 1.14-series (K8s 1.37) — not present here.
- **Breaking changes:** K8s 1.37 is a new minor release with its own deprecations/behavior changes on top of 1.36.5; combined with the Talos mismatch, an actual `talosctl upgrade` to 1.37 would need a supported Talos image and a controlled, node-by-node rollout.
- **Risk:** **HIGH** — not because of the diff (trivial 1-line x2), but because applying it (talosctl upgrade) to a v1.35 cluster via v1.37, on a Talos version that does not bundle 1.37, can destabilize the control plane.
- **Safe to merge as-is?** **NO.** Do NOT merge yet. Needs:
  1. Reconcile the version drift — decide the true target path (1.35.3 live → 1.36.x → 1.37) rather than jumping straight to 1.37.1 from a 1.36.4 declaration.
  2. Confirm a Talos release that bundles kubelet v1.37 before bumping `kubernetesVersion` (currently Talos is still v1.13.11 / K8s 1.36.3).
  3. When actually applied, do it as a planned `talosctl upgrade` with control-plane nodes first, workers after, and backups — never as a fire-and-forget Flux reconcile of the talconfig.
  Suggested action: close/hold #2368 and re-open as a coordinated Talos+K8s 1.37 upgrade with a matching Talos version.

---

## 4. gamevault-backend v17 — PR #2375

- **Version:** `16.3.0` → `17.0.1`
- **File / line:** `kubernetes/apps/home/gamevault/app/helm-release.yaml:28`
  - `tag: 16.3.0` → `tag: 17.0.1`
- **Critical finding — the app is NOT deployed.** No `gamevault` pods exist in any namespace, and the Flux reconciliation is **commented out**: `kubernetes/apps/home/kustomization.yaml:12`  `  #- ./gamevault/ks.yaml`. Renovate still tracks the image (registry tag present) and generated the PR, but nothing runs it.
- **Breaking changes:** v16→v17 is a major bump; Renovate body contains **no release notes** (dependency not resolvable), so the exact API/config/DB changes are unknown.
- **Risk:** LOW — no runtime effect because the app is disabled in the Flux tree (no pod, no traffic).
- **Safe to merge as-is?** YES (harmless, no-op for this cluster). Optionally, if you intend to re-enable GameVault later, first read the v17 breaking changes and verify the `gamevault` secret/env and the two PVCs (`gamevault-files-nfs`, `gamevault-images-nfs`) remain compatible.

---

## 5. ubuntu 26.04 — PR #2536

- **Version (GitHub Actions runner image):** `24.04` → `26.04`
- **File / line:** `.github/workflows/devcontainer.yaml:24`
  - `runs-on: ubuntu-24.04` → `runs-on: ubuntu-26.04`
- **Breaking changes / relevance:** This only changes the **CI runner** for the devcontainer publish workflow. It does not affect any deployed Kubernetes service. Risk is that the `ubuntu-26.04` runner image may not be available/enabled for this repo/plan, or that the devcontainer build (deps pinned to 24.04 tooling) breaks on the new base.
- **Risk:** LOW — CI-only, no production impact.
- **Safe to merge as-is?** YES, but verify by **checking that the workflow run succeeds** after merge (the build must complete on ubuntu-26.04). If the runner isn't available or the build fails, revert the tag. No additional file change needed.

---

## 6. http-https-echo v42 — PR #2534

- **Version:** `41` → `42`
- **File / line:** `bootstrap/templates/kubernetes/apps/network/echo-server/app/helmrelease.yaml.j2:31`
  - `tag: 41` → `tag: 42`
- **Breaking changes:** v42 adds **HTTP/2 support** and enforces max header size in code (Node HTTP/2 limit). No flag/port/env changes.
- **Relevance:** The echo server is a network diagnostic. There are two running instances (`default/echo-server-shadow` 44d, `utilities/echo-server` 3d6h) — both HTTP debug endpoints. v42 is backward compatible (HTTP/1.1 still served alongside HTTP/2); the only behavior change is a now-enforced max header size.
- **Risk:** LOW — diagnostic app, additive change, env/ports unchanged.
- **Safe to merge as-is?** YES. The generated manifests (shadow + utilities) pick up tag 42; no value/env change required. Confirm pods reach `1/1 Running` after rollout.

---

## 7. Forgejo v17 — PR #2761  ⚠️ BLOCKED

- **Version:** `16.0.6` → `17.0.0`
- **File / line:** `kubernetes/apps/utilities/forgejo/app/helm-release.yaml:31`
  - `tag: 16.0.6` → `tag: 17.0.0`
- **Upstream status (verified via codeberg API):**
  - Latest stable is **v17.0.0** (published 2026-10-15).
  - **v17.0.1 does NOT exist yet** (no `v17.0.1` tag, no release; only `v17.0.0` and `v17.0.0-dev`).
  - The v17.0.0 release notes carry an explicit warning: *"We currently advise against upgrading to Forgejo 17.0.0. An issue is currently being investigated that prevents pushing, merging, or other code operations in some cases."*
- **Additional deployment risk:** The chart uses `strategy: Recreate` (not RollingUpdate), so the single-instance Forgejo is taken down and restarted — a brief outage during upgrade, plus a **major DB migration (16→17)**. Combining that with the upstream push/merge regression makes this the highest-impact "real service" upgrade in the set.
- **Risk:** **HIGH** — upstream-confirmed push/merge regression on a major-version DB migration of a running, single-replica git server.
- **Safe to merge as-is?** **NO.** Confirmed blocked:
  1. Do **not** merge — the release notes explicitly advise against it and the fix patch (v17.0.1) has not shipped.
  2. Hold until **v17.0.1** (or later) is published and the push/merge issue is confirmed resolved.
  3. When unblocked: take a full DB + data backup first, then bump the tag and let the `Recreate` strategy roll it (plan for a short downtime).

---

# Summary Table

| # | PR | Component | Change | Real risk | Merge as-is? |
|---|-----|-----------|--------|-----------|--------------|
| 1 | #2547 | supergateway (uvx runtime) | 3.4.3-uvx → 4.2.0-uvx | MED | YES (verify hass-mcp pod) |
| 2 | #2546 | nzbhydra2 | 8.9.0 → 9.1.1 | MED | YES (backup /config first) |
| 3 | #2368 | kubelet / Talos K8s | 1.36.4 → 1.37.1 (declared; live=1.35.3) | **HIGH** | **NO** (Talos mismatch + version drift; needs coordinated upgrade) |
| 4 | #2375 | gamevault-backend | 16.3.0 → 17.0.1 | LOW | YES (app disabled, no-op) |
| 5 | #2536 | ubuntu (CI runner) | 24.04 → 26.04 | LOW | YES (verify CI run) |
| 6 | #2534 | http-https-echo | 41 → 42 | LOW | YES |
| 7 | #2761 | Forgejo | 16.0.6 → 17.0.0 | **HIGH** | **NO** (v17.0.1 not released; upstream push/merge regression) |

**Merge now (safe):** #2547, #2546, #2375, #2534, #2536 (with the noted post-merge verifications).
**Hold / do NOT merge:** #2368 (kubelet 1.37 — needs matching Talos + reconciled path), #2761 (Forgejo — wait for v17.0.1).
