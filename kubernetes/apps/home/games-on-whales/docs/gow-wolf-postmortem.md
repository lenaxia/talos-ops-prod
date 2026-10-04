# GOW / wolf postmortem — from "black screen + 4-second kills" to working Steam (2026-10-03)

Complete chronicle. Every claim here is backed by captured evidence (pcaps,
WAYLAND_DEBUG traces, wolf/gamescope logs, kernel watcher) — see
`kubernetes/apps/home/games-on-whales/docs/gow-wolf-debugging.md` for the earlier mid-flight evidence detail and
`/tmp/opencode/gow/*` artifacts (session lifetime; re-capture from pods if
needed).

## Final working configuration

- **Host**: worker-04, Talos v1.13.11, schematic `8288fc88cb81d863b7bfaaa48dd4eec0172f65d9477a75b633c44f30c501bb03`
  (amd-ucode, i915, iscsi-tools, nvidia-container-toolkit-production,
  nvidia-open-gpu-kernel-modules-production = **595.91.07**, thunderbolt,
  util-linux-tools, **uinput**)
- **Host sysctl**: `user.max_user_namespaces=15000` (Steam requirement;
  Talos default is 0). Patch committed in
  `kubernetes/bootstrap/talos/patches/nvidia/gpu-worker-patch.yaml`.
- **App**: `steam-sway.yaml` — Steam running under **sway** (RUN_SWAY), NOT
  gamescope. GPU = spare 3090 (0000:46:00.0 = renderD130 = /dev/nvidia2).
- **Wolf env (User CR)**: `NVIDIA_VISIBLE_DEVICES=<01:00.0 UUID>,<46:00.0 UUID>`
  (two GPUs, ours at CUDA ordinal 1) + `CUDA_DEVICE_ORDER=PCI_BUS_ID`.
- **App container**: rm-masks /dev/nvidia{0,1,3} with fail-fast assertions
  (PCI↔render-node↔minor mapping verified 2026-10-03).

## The failure stack, bottom to top (what each "bug" really was)

1. **Kernel `nvkms_prime_dup` import errors + EGL_BAD_ALLOC** — looked like
   "Ampere/Ada broken, Blackwell works". Actually **cross-GPU allocation**:
   the fenrir operator injects `NVIDIA_VISIBLE_DEVICES=all` into app pods, so
   gamescope allocated on GPU0 while wolf composited on the spare GPU.
   Fix: per-container GPU masking + assertions. Zero kernel errors since.
2. **CUDA context failures ("Device with id 1 does not exist")** — wolf maps
   its render node to a CUDA ordinal by counting GPUs in **global procfs**
   (4 GPUs) while CUDA enumerates only container-visible GPUs, **fastest-first**
   (the 4090 would be device 0!). Fix: two-GPU NVD pin + PCI_BUS_ID ordering
   so ordinal 1 is deterministically ours.
3. **wolf compositor `waylanddisplaysrc` panics**
   (`Failed to create CUDA image from EGLImage: CUDA_ERROR_INVALID_DEVICE`) —
   same numbering mismatch at the compositor layer; reproduced standalone via
   `gst-launch waylanddisplaysrc ! video/x-raw(memory:CUDAMemory)`. Matches
   [wolf#301](https://github.com/games-on-whales/wolf/issues/301). Fixed by #2.
4. **"4-second kill" on Test Ball** — looked like a network/client bug (client
   killed with "no video received" while RTP flowed perfectly: seq 0-890 lossless,
   HEVC decodable, offline-verified). Actually the **synthetic
   `video.source: videotestsrc` override prevented the wayland display (and its
   socket) from ever starting**; the runner wait timed out at 5s and wolf
   aborted the session. Removing the override fixed it (session survived past
   the gate). The ball the user saw was the synthetic source streaming during
   the death window.
5. **Fork payloader quirks (real but non-fatal)**: frameIndex starts at 0
   (moonlight-common-c discards frame 0 = initial IDR; client then forced an
   IDR at ~2s — visible as "Forcing IDR" in wolf logs), all RTP timestamps 0,
   no SS_PING echoes. Clients tolerate them; video decodes.
6. **Black screen with gamescope (the last real blocker)**: NVIDIA **595.x
   returns ZERO dmabuf modifiers for 8-bit ARGB** (`vkGetPhysicalDeviceFormatProperties2`)
   → gamescope cannot allocate ANY presentable buffer → zero `wl_surface`
   attaches (proven via WAYLAND_DEBUG) → wolf streams a faithful 60fps of an
   empty compositor. Reproduced identically on **RTX 3090 and RTX 4090**, on
   **595.91.07 and 595.58.03** — it is driver×gamescope, NOT silicon (matches
   [gamescope#1921](https://github.com/ValveSoftware/gamescope/issues/1921),
   open). `--hdr-enabled` (10-bit path) lets gamescope composite standalone
   under sway, but wolf's compositor also demands the 8-bit client buffer →
   still dies in-session.
7. **The unlock: drop gamescope, use sway.** wlroots-based sway tolerates this
   driver (modifier-less allocation) and GOW images ship `RUN_SWAY`. Steam
   under sway worked on the first properly-rendered attempt. Gamescope on this
   driver stack is simply unavailable until NVIDIA/gamescope resolve #1921.

## Dead ends (documented so we never repeat them)

- Upstream `wolf:stable` image on this node: same compositor CUDA panic
  (image userspace can't allocate on this node's driver pairing) — not
  fixable by config; the fenrir/fork image is required.
- Driver downgrades: siderolabs only builds `-production` extensions for
  current Talos versions; 580.x/570.x don't exist for v1.13.x. We rolled the
  node to v1.13.0 (595.58.03) and back — 595.58.03 broke the producer caps,
  confirming both 595 builds are broken differently.
- **Never roll worker-04 from the stale clusterconfig schematic** — it lacks
  `uinput` (steam pods then fail scheduling on `squat.ai/uinput`). Correct
  schematic is `8288fc88…` (see runbook).

## Consequences of the fixes (what else changed)

- vLLM (vllm, vllm-classifier-a/b) was scaled to 0 for the 4090 test —
  **restore after confirming the 3090 stream**: `kubectl -n home scale deploy
  vllm vllm-classifier-a vllm-classifier-b --replicas=1`.
- Legacy A/B wolf stack (games-on-whales-legacy HelmRelease) was deleted.
- Debug pods (`gow-kmsg-watcher`, `gow-wolftest`, `gow-steamtest`,
  `gow-framecheck`, `moonlight-client`) may linger in namespace `home` —
  safe to delete individually.

## Final resolution (2026-10-04)

End state: ALL UPSTREAM proxy, RL-era configuration, full input restored.
The fork was withdrawn — see the runbook's "Resolution addendum" for the
fork lesson (public fenrir repo lags the deployed image; fork broke pairing
user-assignment and the applist, cascading into a client-side input wedge
cured by reinstalling Moonlight on the Shield).

Because we are on the UPSTREAM proxy, note these limitations are back:
- App tiles show icons WITHOUT titles (upstream applist XML)
- Launch timeout is 25s (premature 500s on cold starts — session usually
  completes behind it; just reconnect)
- Resume relaunches without the clean stop-first (occasional "failed to
  resume" — retry the launch)
All three have working reference fixes documented (rebase onto the deployed
upstream source before rebuilding any fork).

## Open items

- **Resume**: not supported by this fenrir operator build — on client
  disconnect the session is deleted within ~1 minute ("no wolf session ID"),
  so Moonlight "resume" fails. Workaround: relaunch (Steam state persists on
  the PVC). Fix requires an upstream feature (session grace period / linger).
- **App titles**: the direwolf proxy's applist shows icons without names in
  Moonlight (wolf's own applist showed names). Needs proxy-side fix.
- Upstream reports worth filing with our evidence: gamescope#1921 (add our
  two-GPU two-driver traces), wolf#301 (compositor CUDA panic), fenrir
  operator (NVD=all injection; session linger; applist titles).
- Gamepads: not addressed (needs uinput-based virtual pads — uinput extension
  now present, so wolf's pads may work; untested).


## Postscript: the recurring wedge chain (2026-10-04)

Final failure mode of the night, now fully mapped:
fenrir operator requeues deployment-not-ready WITHOUT backoff (status lag on
healthy pods) -> rate limiter saturates -> launches 500 -> cleanup kills a
LIVE session pod -> Shield Moonlight app wedges input on the unclean
disconnect (video fine, zero input packets — verified twice) -> Force Stop +
clean relaunch fixes.

Missing pieces (ranked):
- fenrir operator: bounded backoff (upstream bug to file)
- moonlight-android/Shield: input thread dies on unclean stream kill (file)
- cluster: no alerting on operator error rate (PrometheusRule TODO)
- operational rule (now in runbook): clean client exit before cleanup;
  never delete deployments whose pods are actually Running
