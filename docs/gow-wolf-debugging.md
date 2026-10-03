# Games on Whales debugging — status, evidence, next steps (2026-10-03)

Two open bugs. What follows separates **proven** facts (verified in-cluster or
from captured bytes + upstream source) from **hypotheses**.

## Bug 1: wolf compositor EGL_BAD_ALLOC / nvkms_prime_dup (dmabuf import)

### Proven
- Pod-level GPU pinning works: in the mike-testball pod the only visible GPU is
  `/dev/nvidia2`, and the mapping chain is verified in-container:
  `0000:46:00.0` = device minor 2 = `/dev/nvidia2`; `renderD130` →
  `/sys/class/drm/renderD130/device` → `0000:46:00.0`. So wolf's compositor
  (renderD130) and CUDA are on the same physical GPU the kernel errors named.
- The steam App's rm-mask (`/dev/nvidia0,1,3` removed) is live in the applied
  spec, and is now backed by a fail-fast mapping assertion (steam.yaml).
- Prior art with the same kernel signature (`__nv_drm_gem_nvkms_prime_dup …
  Failed to import NVKMS memory to GEM object`): pop-os/cosmic-comp#2768 —
  2× RTX 3090 desktop, smithay compositor, smithay logs "import for wrong
  devices". **Open and unresolved**; no confirmed fix exists upstream.

### Hypothesis (unproven)
Cross-GPU allocation/import caused by the operator injecting
`NVIDIA_VISIBLE_DEVICES=all` into app pods. The working cogito-ops reference is
single-GPU, so "Blackwell works / Ampere-Ada fails" is confounded with
"1 GPU vs 4 GPUs". Do not treat silicon generation as the variable.

### The discriminating test (needs a human with a Moonlight client)
1. Apply the updated steam.yaml (Flux) and launch the Steam app from Moonlight.
2. On the node, watch the kernel log (however you normally run talosctl, the
   repo talosconfig has no contexts saved):
   `talosctl -n <worker-04-ip> dmesg -f | grep -iE 'nvkms|nvidia_drm'`
3. In the steam pod, confirm the assertion passed (log shows
   `visible GPUs: /dev/nvidia2 …` only).
- **PASS = hypothesis proven**: no nvkms_prime_dup errors AND gamescope
  connects (no EGL_BAD_ALLOC storm in wolf logs).
- **FAIL = hypothesis falsified**: errors persist with same-GPU verified →
  next bisects: (a) upstream `ghcr.io/games-on-whales/wolf` image, then
  (b) non-Talos host with a 3090 (splits Talos vs world; yields a clean
  upstream report).

## Bug 2: Moonlight kills session at ~5s ("no video received from host")

Analysis of the in-pod capture (`/tmp/rtp.pcap` inside the wolf container,
written by the tcpdump baked into the wolf-root-entrypoint ConfigMap).
Analyzer: `scripts/moonlight-pcap-analyze.py PCAP`.

### Proven (pcap + moonlight-common-c source)
- Transport is clean: RTP seq 0..890, zero loss/reorder; RTSP + ENET control
  fully established; AES keys N/A — **video is not encrypted** (plaintext
  AnnexB HEVC visible).
- Stream structure: 297 frames @ ~74fps, each = 1 data packet
  (SOF|EOF|PIC, 8-byte frame header `01 .. 02`=IDR where applicable, then
  HEVC VPS/SPS/PPS + slices) + 2 Reed-Solomon parity packets (fecInfo:
  dataPackets=1, fecPercentage=200). Data-packet streamPacketIndex monotonic.
- Fork payloader nonconformances vs moonlight-common-c:
  1. **frameIndex starts at 0** — the client initializes
     currentFrameNumber/nextFrameNumber = 1 and rejects frame 0 (the initial
     IDR) via `isBefore16/32` (src/RtpVideoQueue.c, src/VideoDepacketizer.c).
  2. All RTP timestamps are 0 (client synthesizes PTS — tolerated).
  3. Parity packets carry garbage spi/flags (client classifies parity by
     sequence position — ignored; benign).
  4. **No SS_PING payload echoes** (0/10 video, 0/11 audio). Sunshine echoes
     them; wolf's docs describe pings only as client-port discovery.
- IDR frames occur at frame 0 (dropped per #1) and frame 121 (~1.6s in),
  with param-set NALs on additional frames.

### Not proven / open
- The above does **not** fully explain a >5s total blackout: if packets reach
  the client, frame 121's IDR should decode. The in-pod pcap cannot see
  whether packets arrive or what the client does. Remaining suspects, in
  order: (a) network path (Cilium LBIPAM shared-VIP session Service — client
  connects to the VIP; egress-side source address after SNAT/DSR is
  unverifiable from inside the pod), (b) ping-echo absence gating some
  clients, (c) decoder-side rejection only visible client-side.

### Decisive next evidence (client side — needs the Moonlight machine)
1. Client capture during a session:
   `tcpdump -ni any 'host <VIP> and udp' -w client.pcap` — confirms arrival
   and the client-visible source IP/port of the RTP flow.
2. Verbose client logs: Moonlight Qt with debug logging, or
   `moonlight-embedded -verbose`. Grep for "Waiting for IDR frame",
   "Depacketizer detected corrupt frame", "Unrecognized frame type" — each
   maps to a specific fork bug above.
3. If packets arrive and none of those log lines appear, the failure is
  decoder-side; capture client.pcap and re-run the analyzer against it.

## Fork-bug candidates for an upstream report (when proven)
- moonlight packetizer: 0-based frameIndex (off-by-one vs every known host).
- ping responder: consider echoing SS_PING payloads (see SS_PING in
  moonlight-common-c src/Video.h; wolf docs/modules/protocols rtp-video.adoc
  only uses pings for port discovery).

## Files
- `scripts/moonlight-pcap-analyze.py` — offline pcap analyzer (SLL/SLL2,
  RTP/NV parse per moonlight-common-c struct, FEC/IDR/ping checks).
- `kubernetes/apps/home/games-on-whales/sessions/steam.yaml` — GPU mask +
  fail-fast mapping assertion.
- Raw evidence: `/tmp/rtp.pcap` (copied to operator workstation:
  kubectl cp mike-testball-<hash>:/tmp/rtp.pcap -c wolf).
