# msedge — Microsoft Edge via Selkies WebRTC

A browser-based Microsoft Edge desktop streamed over WebRTC via the
[LinuxServer.io msedge image](https://github.com/linuxserver/docker-msedge),
which is built on `docker-baseimage-selkies`. Accessible at
`https://edge.${SECRET_DEV_DOMAIN}/` behind Authelia.

## Files

| File | Purpose |
|---|---|
| `ks.yaml` | Flux Kustomization (parent pointer) |
| `app/helm-release.yaml` | HelmRelease (app-template) defining the container, service, ingress, and init-script mounts |
| `app/scrollfix-configmap.yaml` | Init script that patches Selkies JS at container start (see below) |
| `app/msedge-pvc.yaml` | 2Gi Longhorn PVC for `/config` (Edge profile, bookmarks, etc.) |

## Touchpad Scroll Fix

### The problem

Touchpad scrolling is wildly oversensitive — a small swipe jumps halfway down
the page. This is a known artifact of how Selkies handles input.

### Why it happens

Scrolling does **not** flow through the X server the way a normal desktop does.
The actual path is:

```
your touchpad → browser wheel events
    → Selkies web client JS (selkies-core.js) computes scroll magnitude
    → WebSocket message "m2,x,y,buttonMask,scrollMagnitude"
    → Selkies server (input_handler.py) → pynput → XTest Button4/5
    → Edge receives N scroll clicks
```

The number of scroll "clicks" is decided **entirely in the browser-side JS**,
before any X11 event is created. The relevant code in the served JS:

```js
// _mouseWheel(e) — runs on every wheel event in the browser
let l = Math.abs(Math.trunc(e.deltaY));                    // touchpad deltaY (1–100+)
l < this._smallestDeltaY && l !== 0 && (this._smallestDeltaY = l);  // adapts DOWN
const n = Math.max(1, Math.floor(l / this._smallestDeltaY));        // grows as divisor shrinks
const d = Math.min(n, this._scrollMagnitude);                       // capped at 10
this._triggerMouseWheel(t, d)                                        // sends d clicks
```

Defaults are hardcoded (not exposed as `SELKIES_*` env vars):

- `_scrollMagnitude = 10` — max lines per scroll event
- `_wheelThreshold = 100` — trackpad scroll throttle in ms
- `_smallestDeltaY` — starts at `1e4`, adapts down to the smallest deltaY the
  touchpad emits (often 1–4px)

Once `_smallestDeltaY` shrinks to a touchpad's tiny per-event delta, a normal
swipe with `deltaY` ~40 produces `n = 40/4 = 10` → capped at **10 lines per
event**. Inertial touchpad scrolling fires events every ~100ms for 1–2s →
10–20 events × up to 10 lines = **~150 lines per swipe**. That's the
"jump halfway down the page" symptom.

Real mouse wheels (consistent large deltaY) are detected by a threshold
heuristic (`_dropThreshold()`) and take a different code path that isn't
amplified — so the problem is touchpad-specific.

### Why imwheel was the wrong fix

A previous attempt used `imwheel` (via a docker-mod install + s6 service) to
"reduce scroll acceleration." This was a no-op because:

- imwheel operates on the **X11 side** — it grabs Button4/5 events from
  XTest and re-emits them. It cannot reduce the **count** of events that the
  browser-side JS already decided to send.
- The `REPS=1` setting in the old `.imwheelrc` is "emit 1 Button4 per Button4
  received" — a 1:1 passthrough, not a line-count control.
- The `-f` (force) flag adds grab/re-emit latency that can desync press/release
  pairs, potentially making things worse.

### The actual fix

The `scrollfix-configmap.yaml` init script runs at container start
(`/custom-cont-init.d/scrollfix.sh`) and patches the served Selkies JS files
in `/usr/share/selkies/`:

```
_scrollMagnitude:  10 → 3   (caps lines per touchpad swipe)
_wheelThreshold:  100 → 200  (throttles touchpad events further)
```

Both knobs only affect precision/touchpad input — real mouse wheels compute
`n=1` and bypass the throttle, so external mice are unaffected.

### Maintenance notes

- **The patch targets minified JS.** The asset filename is content-hashed
  (e.g. `index-23cDh2Vf.js`) and **will change on every Selkies base image
  bump**. The init script uses `grep -rl` to find files by content pattern, not
  by filename, so it survives filename changes — but if the upstream minifier
  reformats the tokens (`_scrollMagnitude=10`), the sed patterns will silently
  match nothing and the patch becomes inert.
- **To verify the patch is active** after a rebuild:

  ```bash
  kubectl -n home exec deploy/msedge -c main -- \
      grep -r "_scrollMagnitude=3" /usr/share/selkies/ ; echo "exit: $?"
  ```

  A non-zero exit (no matches) means the image changed and the patterns need
  updating.
- **The proper upstream fix** would be to expose `_scrollMagnitude` and
  `_wheelThreshold` as `SELKIES_*` environment variables in
  `selkies-project/selkies-gstreamer` (where the web client source lives),
  flowing downstream through `docker-baseimage-selkies` into this image. Not
  yet done.
