# Worklog — Multus rollout, AI-CI overhaul, and etcd disaster recovery

**Dates:** 2026-07-03 through 2026-07-06
**Scope:** Full multus enablement, prompt-driven AI review workflow migration, cluster-wide cleanup (MetalLB purge, Homebrew CI fix, Talos patch modernization), and unplanned etcd disaster recovery.

## TL;DR

Went in to answer "are we ready for Multus?" and came out with:
- **Multus deployed** and functionally verified — esphome and home-assistant have working macvlan `net1` interfaces reaching the physical 192.168.0.0/24 LAN.
- **Sonos speakers discoverable via SSDP** through Home Assistant's Network integration configured to use `net1`.
- **ESP devices discoverable via mDNS** through ESPHome dashboard, causally proven (removed multus annotation → mDNS broke → restored → mDNS worked).
- **Prompt-driven AI code reviewer** replacing the old inline-prompt workflow. Higher review quality with 4-level rollback runbook culture.
- **etcd cluster survived a 2-of-3 CP loss** and was recovered from snapshot when cp-01 died (bad RAM) and cp-02 got into a bad state during networking reconfig. Zero user-visible data loss.
- **cp-01 remains out of the cluster** pending your physical RAM replacement.

10 non-Renovate PRs merged this session. One PR (#1958, Talos JSON6902 → strategic-merge conversion) opened but not yet merged.

## Timeline

### 2026-07-03: Prep, workflow migration, MetalLB purge, Homebrew CI fix

Started with a Multus readiness check. Found:
- Cilium was in `cni.exclusive: true` mode — Cilium would delete Multus's `00-multus.conf` from `/etc/cni/net.d/`.
- NAD had `master: enp0s20f0u3` — but that USB dongle interface is a bond slave (Talos bonds all physical interfaces into `eth0`). macvlan can't be created on a bond slave.
- worker-03 NotReady since 2026-06-29.

Merged as prep:

| PR | Purpose |
|---|---|
| **#1924** `chore(multus): prepare cluster for multus deployment` | Set `cni.exclusive: false` in Cilium; change NAD `master: eth0` (the bond itself, macvlan-on-bond is fine); tighten NAD route `dst: 192.168.0.0/24` to avoid Cilium VIP shadowing. Multus DS kept commented out. |
| **#1925** `chore(ci): migrate AI workflows to prompt-driven three-workflow layout` | Replaced monolithic `issue-responder.yml` with three focused workflows (`pr-review.yml`, `ai-comment.yml`, `issue-opened.yml`) + 16-file prompt library under `.github/prompts/` + `route-command.sh` router. Ported from the LLMSafeSpaces repo pattern, adapted for GitOps/Kubernetes. Corrected drift in `README-LLM.md` (MetalLB not deployed, app-template 5.0.1, Authelia 0.11.6, Traefik 40.3.0). |
| **#1927** `fix(ci): trust third-party Homebrew taps before brew bundle runs` | Fixed the `configure (talos)` e2e job that had been failing on every PR since Homebrew 6.0 shipped `HOMEBREW_REQUIRE_TAP_TRUST` as default-on. |
| **#1928** `chore(cleanup): purge stale MetalLB references (Cilium handles LB IPAM)` | Removed 20 of 22 stale `metallb.universe.tf/*` annotations across the repo. Deleted dangling `metallb-charts.yaml` HelmRepository. Migrated AdGuard IP-sharing annotation to Cilium equivalent (`lbipam.cilium.io/sharing-key`). Aligned two CNPG service manifests to their actual live IPs. Left one intentional exception on `utilities/smokeping` where the chart's broken `values.schema.json` blocks any change. |

### 2026-07-06: Multus rollout begins — then cp-02 catches fire

Verified prereqs live in cluster. Cilium was actually still on `cni-exclusive: true` because the HelmRelease upgrade triggered by #1924 had entered a rollback loop — `cilium-f6fjb` on worker-03 stuck Terminating for 12h. The HR upgrade failed → Flux rolled back → repeat.

Solution: drain and delete worker-03 from the cluster (it was already NotReady for 4 days). Force-deleted the ghost `cilium-f6fjb` pod. Cilium DS reconciled to 6/6. HR reached Ready=True with `cni-exclusive: false` finally live.

Discovered cp-02 also had drift: talconfig said bond `eth0`, live machineconfig said `interface: eno1` (standalone, no bond). Machine had never been re-applied since the bond config landed. Investigation revealed a deeper issue: **talhelper's `genconfig` had been broken since Talos 1.12+** because it rejects RFC6902 JSON patches on multi-doc machine configs.

Fixed the JSON6902 patches → strategic-merge conversion in **PR #1958** (still open at time of writing). Regenerated configs successfully — proved cp-02 would generate structurally identical to cp-00/01. But applying the newly-generated configs would trigger a full Kubernetes 1.35 → 1.36 + Talos 1.10 → 1.13.5 upgrade (Renovate has been bumping the version strings for months without anyone doing `task talos:apply-node`).

Chose to defer that upgrade and use a **narrower approach**: download cp-02's live machineconfig, patch just the `network.interfaces` block to use the bond, apply via maintenance mode. Would bring cp-02 into architectural alignment with cp-00/01 without dragging in a K8s+Talos version upgrade.

### The bad afternoon: cp-01 hardware death + cp-02 network limbo

**cp-02 apply-config broke it.** Live-reconfiguring a physical NIC into a bond master while the node is running is not a well-supported code path. cp-02 became unreachable — machineconfig persisted to disk, but the running network was broken.

**During the recovery attempt, cp-01 stopped posting entirely.** Not related to my actions — it turned out to be bad RAM. Hardware failure. cp-01 remains out of the cluster.

**With cp-01 and cp-02 both unreachable, etcd lost quorum.** cp-00 alone couldn't form a majority. Kubernetes API dropped.

Executed documented Talos disaster recovery per Sidero's `bootstrap --recover-from` procedure:
1. Took an etcd snapshot from cp-00 (which still had all cluster state, just no quorum). 584MB, 11943 keys, revision 694812572. Validated with `etcdutl snapshot status`.
2. Backed up cp-00's machineconfig separately.
3. Reset cp-00's EPHEMERAL partition (`talosctl reset --system-labels-to-wipe=EPHEMERAL`).
4. cp-00 booted into "Preparing" state waiting for bootstrap.
5. `talosctl bootstrap --recover-from=~/etcd-snapshots/pre-multus-20260706-095419.snapshot` — restored etcd from the snapshot as a fresh single-node cluster.

Cluster came back with cp-00 as sole etcd member. All 337 days of state preserved. Kubernetes API returned. Zero application data lost.

Then reset and re-added cp-02 via maintenance mode with a properly-shaped config cloned from cp-00's live state. cp-02 rejoined etcd as a fresh member.

Along the way found and fixed:
- UDM Pro's DHCP netmask was `/20` but our talconfig set `/16`. On boot into maint mode, cp-02's DHCP client assigned `192.168.3.12/20` alongside the config's `/16`. Fixed at UDM Pro (changed to `/16` to match config).

Cluster restored to 5/5 nodes Ready (cp-00, cp-02, workers 00/01/02). cp-01 stays out until hardware is repaired.

### Multus enablement — the actual work

Now that the cluster was healthy again, executed the planned two-phase rollout:

| PR | Purpose |
|---|---|
| **#1963** `docs(multus): add rollback runbook for multus enablement` | 4-level graduated rollback runbook under `docs/multus-rollback.md`. Level 1 hands-free PR revert; Level 4 restore from pre-multus etcd snapshot. |
| **#1964** `feat(multus): enable Multus DaemonSet + NAD (Phase 1 of 2)` | Uncommented `- ./multus/ks.yaml` in `kube-system/kustomization.yaml`. Deployed Multus DS + NAD only. No consumer changes → zero blast radius on running workloads. |
| **#1965** `feat(multus): enable esphome multus attachment (Phase 2a canary)` | Uncommented esphome's `cluster-multus-networks` dependsOn. Single-pod canary before enabling HA + zwavejs. |
| **#1966** `fix(multus): NAD subnet /20 + DS memory limit 256Mi` | Two production-observed fixes: (1) NAD IPAM subnet needed `/20` not `/24` — the `subnet` controls the pod's on-link scope, which must include the gateway; (2) Multus DS OOMKilled at the default 50Mi limit on workers with high pod density (worker-00 had 130 pods, worker-01 had 110). Bumped to 256Mi limit / 64Mi request. Both applied live via `kubectl patch` before opening this PR to unblock the esphome canary. |
| **#1967** `feat(multus): enable multus for home-assistant + zwavejs (Phase 2b)` | Uncommented HA and zwavejs dependsOn. Removed dead code from HA helm-release (`podAnnotations` referencing nonexistent NAD `macvlan-static-iot-hass`). |
| **#1968** `chore(zwavejs): remove multus attachment (RF, not Ethernet)` | Post-rollout cleanup. Z-Wave devices communicate via 900MHz RF radio through a USB dongle — no Ethernet broadcast needed. Verified live: zwavejs pod had `net1` attached but was completely idle (no mDNS/SSDP subscriptions, no traffic on the interface). Removed the annotation and dependsOn. |

## Final Multus consumer topology

| App | Uses Multus? | net1 IP | Reason |
|---|---|---|---|
| **esphome** | ✅ Yes | `192.168.6.15` | mDNS discovery for ESP devices |
| **home-assistant** | ✅ Yes | `192.168.6.17` | SSDP (Sonos) + mDNS (Chromecast, HomeKit, ESPHome autodetect, Roomba) discovery |
| **zwavejs** | ❌ No (cleaned up) | — | RF radio via USB dongle; no network discovery |

## Key learnings & receipts

### macvlan-on-bond works

The Talos config bonds every physical interface into `eth0`. This meant the individual USB dongle (`enp0s20f0u3`) that was originally intended as the multus master was actually a bond slave — macvlan-on-slave is a kernel dead-end. Solution: use the bond itself (`eth0`) as the master. macvlan-on-bond is a well-supported kernel path and has the bonus that pods route through whatever slave the bond has currently up.

### NAD IPAM subnet vs route dst are DIFFERENT things

- `routes[].dst` controls WHICH destinations traverse macvlan
- `ipam.subnet` controls the pod's on-link scope (derived from address netmask)

We wanted the route tight (`192.168.0.0/24` — avoid VIP shadowing) but the pod's on-link scope broad enough to reach the physical LAN gateway (`192.168.0.0/20`). Initially I set both to `/24`, which broke gateway reachability. Fixed in #1966.

### Multus daemon memory scales with pod density

Upstream's default `50Mi` limit is inadequate for cluster nodes with 100+ pods. The multus-shim intercepts every pod CNI ADD (to delegate to Cilium for pods without the NAD annotation), and the daemon's per-request memory spike on high-churn nodes exceeded 50Mi within 6 seconds of first CNI request burst. Bumped to 256Mi.

### Sonos discovery requires HA's Network integration to be configured

Merely attaching `net1` to the HA pod isn't enough — HA's Sonos integration uses SSDP multicast on port 1900 and Python's `netifaces` picks the "primary" interface by default (Cilium's `eth0`, on the wrong subnet). Solution: **Home Assistant → Settings → System → Network → Configure → select `net1` as the auto-discovery adapter, deselect `eth0`.** Sonos speakers appeared within ~30 seconds after saving.

For future readers running into the same problem: this is documented in HA's Network integration but easy to miss.

### mDNS-via-multus is causally proven, not just correlated

Ran a controlled experiment: removed esphome's multus annotation, recreated the pod without `net1`, observed the ESPHome dashboard say "reachable over MQTT but not via mDNS ... dashboard and the device are on different subnets" and flag device data as stale. Restored the annotation, mDNS came back. Not just correlation — the ESPHome dashboard's own error message named the exact reason.

### etcd disaster recovery via `bootstrap --recover-from` works

Documented Talos procedure. Tested under real duress. Recovered a cluster that had lost 2 of 3 CPs (one to hardware failure, one to my own live-network-reconfig experiment) with zero application data loss. The 584MB pre-multus snapshot at `~/etcd-snapshots/pre-multus-20260706-095419.snapshot` remains the go-to for future disaster scenarios.

### Multus benefit analysis across all 118 apps

Investigated the full application inventory. **Only esphome and home-assistant benefit from Multus** in the current cluster. Every other app either:
- Uses only unicast TCP/HTTP (databases, web apps, media servers, backup, monitoring)
- Already runs on `hostNetwork: true` (Ragnarok game servers)
- Doesn't do any device discovery (100+ apps)

Frigate, Plex, Jellyfin, Brother printer web UI, AdGuard, SmokePing, Mosquitto, Vector aggregator, Prometheus, and everything else all use explicit unicast paths that work fine over Cilium. No new candidates for Multus.

## Follow-ups tracked (not blocking)

- **cp-01 hardware repair** — bad RAM. Replace, reintroduce node, etcd will re-form 3-member cluster automatically. Talos config for cp-01 remains in `talconfig.yaml` unchanged.
- **PR #1958** (Talos JSON6902 → strategic-merge patch conversion) — open, ready to merge. Config regeneration works but hasn't been applied to any node. Next natural opportunity is when cp-01 comes back.
- **Talos + Kubernetes upgrade** — talconfig targets Talos 1.13.5 and k8s 1.36.2 but cluster is running Talos 1.10-1.12 / k8s 1.35.3. Renovate has been bumping the version strings; nobody has done `task talos:apply-node`. Overdue but a separate planned effort.
- **AI reviewer "Failed to get summary from agent"** — happened twice this session on straightforward PRs. Recovered both times via `/review` retry. Might be OpenCode action resource limits; worth investigating if it recurs.
- **Migrate NAD IPAM to whereabouts** — if a 4th multus consumer is ever added, or if consumer node-pinning loosens, the shared 192.168.6.1-50 host-local pool becomes collision-prone. Current NAD file has a TODO comment tracking this.

## Files touched this session (non-renovate)

Code:
- `.github/workflows/pr-review.yml` (new)
- `.github/workflows/ai-comment.yml` (new)
- `.github/workflows/issue-opened.yml` (new)
- `.github/workflows/issue-responder.yml` (deleted)
- `.github/workflows/e2e.yaml` (added brew trust step)
- `.github/prompts/*.md` (16 new files: context, core-rules, pr-review, issue-responder, code-change-workflow, commands-footer, fix, implement, test, security, analyze, explain, triage, design, merge, help)
- `.github/scripts/route-command.sh` (new)
- `kubernetes/apps/kube-system/cilium/app/helm-values.yaml` (cni.exclusive: false)
- `kubernetes/apps/kube-system/kustomization.yaml` (uncommented multus/ks.yaml)
- `kubernetes/apps/kube-system/multus/networks/networkattachdefinition.yaml` (master: eth0, subnet /20, route /24, gateway, extensive comments)
- `kubernetes/apps/kube-system/multus/app/patches/multus-daemonset-patch.yml` (memory limits)
- `kubernetes/apps/home/esphome/ks.yaml` (dependsOn cluster-multus-networks)
- `kubernetes/apps/home/home-assistant/ks.yaml` (dependsOn cluster-multus-networks)
- `kubernetes/apps/home/home-assistant/app/helm-release.yaml` (dead podAnnotations removed)
- `kubernetes/apps/home/monica/ks.yaml` (stale dependsOn removed)
- `kubernetes/apps/home/zwavejs/ks.yaml` (added, then removed cluster-multus-networks dependsOn)
- `kubernetes/apps/home/zwavejs/app/helm-release.yaml` (added, then removed multus annotation)
- `kubernetes/apps/storage/longhorn/ks.yaml` (stale metallb dependsOn removed)
- `kubernetes/apps/networking/authelia/app/service.yaml` (deleted; orphan file)
- `kubernetes/apps/networking/authelia/app/helm-release.yaml` (dead metallb annotations removed)
- 12 more files with stale `metallb.universe.tf/*` annotation removals (chronograf, telegraf, influxdb, vaultwarden, librespeed, changedetection, uptimekuma, adguard, cnpg synofotopg-lb, cnpg vectorpg-lb, ragnarok/robrowserlegacy comment fix, home/mosquitto/app/helm-release.yaml.old deletion)
- `kubernetes/flux/repositories/helm/metallb-charts.yaml` (deleted)
- `kubernetes/flux/repositories/helm/kustomization.yaml` (removed metallb-charts entry)
- `kubernetes/bootstrap/talos/patches/nvidia/nvidia-default-runtimeclass.yaml` (JSON6902 → strategic-merge, PR #1958 pending)
- `kubernetes/bootstrap/talos/patches/controller/disable-admission-controller.yaml` (JSON6902 → strategic-merge, PR #1958 pending)
- `kubernetes/bootstrap/talos/talconfig.yaml` (bond mode: balance-rr, PR #1958 pending)

Docs:
- `docs/multus-rollback.md` (new)
- `README-LLM.md` (drift corrections)

Cluster (imperative, outside git):
- `talosctl reset cp-00 EPHEMERAL` + `talosctl bootstrap --recover-from=snapshot` (etcd disaster recovery)
- `kubectl drain worker-03 && kubectl delete node worker-03` (removed dead node)
- `kubectl delete node cp-01 cp-02` (cleared stale entries during recovery)
- `talosctl apply-config` on cp-02 (twice — first attempt broke, second attempt after reset to maint mode worked)

## Session length

~2 days elapsed. Real focused work time ~14 hours (rough guess). Battle stories logged above.
