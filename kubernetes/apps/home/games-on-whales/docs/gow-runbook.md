# GOW / wolf runbook — known-good setup for worker-04 (2026-10-03)

Everything needed to rebuild streaming from scratch, in order. Derived from
the postmortem (`kubernetes/apps/home/games-on-whales/docs/gow-wolf-postmortem.md`); deviations from this recipe
are how every bug in that document happened.

## 1. Node: worker-04 image + sysctls

- Talos **v1.13.11**, schematic `8288fc88cb81d863b7bfaaa48dd4eec0172f65d9477a75b633c44f30c501bb03`
  (factory.talos.dev) — includes **uinput** and
  nvidia-open-gpu-kernel-modules-production (595.91.07).
  Upgrade command:
  `talosctl --talosconfig <cfg> -n 192.168.3.24 upgrade --image factory.talos.dev/metal-installer/8288fc88cb81d863b7bfaaa48dd4eec0172f65d9477a75b633c44f30c501bb03:v1.13.11`
  (If drain stalls on `ragpg-1`, delete that pod first and re-run.)
  NEVER roll this node from `clusterconfig/` — that schematic is stale
  (missing uinput → steam pods unschedulable on `squat.ai/uinput`).
- Sysctl `user.max_user_namespaces=15000` — machineconfig patch committed
  (`patches/nvidia/gpu-worker-patch.yaml`). Runtime quick-fix if Steam shows
  the user-namespace dialog:
  `kubectl -n home exec deploy/<any privileged pod> -- sh -c 'echo 15000 > /proc/sys/user/max_user_namespaces'`
- `nvidia_drm modeset=1` stays pinned (kernel args in the same patch dir).

## 2. GPU pinning (critical on this 4-GPU node)

Node map (verified 2026-10-03, re-assert at startup — indices reshuffle on
Talos upgrades):

| PCI | minor | render node | UUID prefix |
|---|---|---|---|
| 01:00.0 | 3 | renderD133? | GPU-6726851a (3090) |
| 46:00.0 | 2 | renderD130 | GPU-755d8528 (3090, **GOW spare**) |
| 81:00.0 | 1 | renderD129 | GPU-bec81ab7 (3090) |
| c1:00.0 | 0 | renderD128 | GPU-ec4bf65c (4090, **vLLM**) |

- **Wolf sidecar (User CR `mike` env)**:
  `NVIDIA_VISIBLE_DEVICES=GPU-6726851a…,GPU-755d8528…` (decoy 01:00.0 first so
  CUDA ordinal 1 = ours) + `CUDA_DEVICE_ORDER=PCI_BUS_ID`. Without both, wolf
  requests a CUDA ordinal that doesn't exist or lands on the wrong GPU →
  compositor panic → "no video".
- **App container**: masks `/dev/nvidia{0,1,3}` before `/entrypoint.sh` and
  fail-fast asserts renderD130 ↔ 0000:46:00.0 ↔ exactly 1 visible GPU.
  (Bundled in steam-sway.yaml's command; keep verbatim when cloning apps.)

## 3. The app: Steam under SWAY (not gamescope)

- Working app: `kubernetes/apps/home/games-on-whales/sessions/steam-sway.yaml`.
  Clone it for new apps (change only name/id/title). It is a byte-clone of the
  steam app (incl. volumeClaimTemplate — apps without it get a broken runner
  + malformed video producer) with `RUN_SWAY=true`.
- **gamescope is unusable on this node** until NVIDIA/gamescope fix the
  zero-modifier 8-bit ARGB issue (gamescope#1921): black screen, crash-loop,
  GPU-independent. Do not spend time on GAMESCOPE_MODE tweaks.
- No `video.source` overrides in wolfConfig (a synthetic source prevents the
  wayland socket → the "4-second kill" session abort).
- Session renderNode = `/dev/dri/renderD130` must match the User CR pinning.

## 4. Verify a session (from zero doubt to picture)

1. `kubectl -n home logs deploy/direwolf-operator` — no "not ready"/"deleting" spam.
2. Launch "Steam (Sway)" from Moonlight (host 192.168.5.20).
3. In the session pod, wolf log must show, in order:
   `Starting video producer: waylanddisplaysrc … ! video/x-raw(memory:CUDAMemory), width=…`
   (the caps segment MUST be present — if you see `! , width=` the producer is
   broken), `Created CUDA context`, `WAYLAND_DISPLAY = wayland-1`,
   `Wayland display ready`.
4. App log shows sway config load, then Steam Big Picture.
5. Black screen with all of the above → check `/tmp/rtp.pcap` decode
   (`scripts/moonlight-pcap-analyze.py`) — YAVG 16 = compositor empty (client
   problem), packets absent = network/encode problem.

## 5. Known limitations & ops

- **No resume** — operator deletes sessions ~1 min after disconnect; relaunch
  instead (Steam persists login on the PVC). Upstream: file/PR at
  **github.com/games-on-whales/fenrir** (open source, active — the operator
  AND proxy both live there; images publish under ghcr.io/timblakely/*).
- **App titles invisible** in Moonlight on the .20 host (proxy applist bug) —
  entries are in list order; fix pending.
- Port errors for UDP 47998/48000 in Moonlight are **expected noise** (legacy
  GFE ports; wolf only serves the modern set).
- vLLM (4090) was scaled to 0 during bring-up; restore with
  `kubectl -n home scale deploy vllm vllm-classifier-a vllm-classifier-b --replicas=1`
  once streaming on the 3090 is confirmed.
- Debug helpers that can be recreated if needed: `gow-kmsg-watcher`
  (kernel log tail), `gow-wolftest`/`gow-steamtest` (persistent wolf/steam
  image pods for standalone gst-launch/gamescope probes),
  `scripts/moonlight-pcap-analyze.py` (offline RTP/HEVC forensics).
- Evidence trail: `kubernetes/apps/home/games-on-whales/docs/gow-wolf-postmortem.md`, `kubernetes/apps/home/games-on-whales/docs/gow-wolf-debugging.md`.


## Resolution addendum (2026-10-04, final)

**Working configuration = everything above with the UPSTREAM proxy**
(`ghcr.io/timblakely/fenrir-moonlight-proxy@sha256:9c8576…`). Input, video,
pairing, Steam — all confirmed working end-to-end from the NVIDIA Shield.

### The fork lesson (do not repeat casually)
- The public `games-on-whales/fenrir` repo is BEHIND the deployed upstream
  image (missing the username pairing page). A fork built from it:
  - pairs clients WITHOUT user assignment → `user not found` 401s
  - broke the app list XML (`<AppID>` vs the client-parsed `<ID>`) → grey tiles
  - the resulting client-side chaos wedged the Shield Moonlight app so it
    stopped sending input entirely (fresh app install + upstream pairing fixed)
- Any future fork must be rebased on the ACTUAL deployed source. Fork images
  remain at `ghcr.io/lenaxia/fenrir-moonlight-proxy` (tags resume-fix digests)
  — treat as reference implementations only: resume=stop-then-relaunch,
  applist ID fix, LAUNCH_TIMEOUT_SECONDS.
- Client-side wedge symptom signature: video works, server receives ZERO input
  packets during deliberate presses (verified via wolf log + WAYLAND_DEBUG),
  mouse-from-another-client works. Fix: clear data + reinstall Moonlight on the
  client, re-pair via the upstream proxy's username PIN page
  (`http://192.168.5.20:47989/pin/#<hash-from-proxy-logs>`).

### Operator wedge (recurring; ~30s fix)
Symptom: launches fail with `client rate limiter Wait returned an error`, or
`failed to launch app` 500s; operator log shows hot `Reconciling session` /
`deployment not ready (0/1)` / `no route to host` loops.
```
kubectl -n home delete session <name-from-operator-logs>
kubectl -n home delete deploy <mike-steam-sway|...> --ignore-not-found
kubectl -n home rollout restart deploy direwolf-operator
```
Root: fenrir operator requeues without backoff when a session pod's deployment
status lags; the loop saturates client-go's rate limiter. Upstream bug worth
filing (bounded backoff).
IMPORTANT: before deleting a session/deployment, have the user EXIT MOONLIGHT
CLEANLY on the client first. An unclean stream kill (pod deleted mid-session)
wedges the Shield Moonlight app's input (video works, zero input packets sent;
verified twice). Fix: Force Stop Moonlight on the Shield, relaunch.

### Pairing runbook (upstream proxy)
1. Client: Add Host `192.168.5.20`
2. Grab the fresh hash: `kubectl -n home logs deploy/moonlight-proxy | grep "Insert pin"`
3. Open `http://192.168.5.20:47989/pin/#<hash>`, enter USERNAME + the client PIN
   (the username field is REQUIRED — it is what assigns userReference)
