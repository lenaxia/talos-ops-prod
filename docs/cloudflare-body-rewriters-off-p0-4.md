# P0-4 Runbook: Disable Cloudflare Body Rewriters on the LLMSafeSpaces Zone

**Date:** 2026-08-19
**Epic:** llmsafespaces epic-66 (dev preview) —
`design/stories/epic-66-workspace-dev-preview/redesign-2026-08-19/` (llmsafespaces repo)
**Why now:** P0-1 (edge `no-store`) and P0-2 (WS forwarding) are merged on
llmsafespaces main. **P0-4 must land before Phase 2 (CSP relaxation)** —
the sequencing constraint THREAT-MODEL T8: today the strict CSP
accidentally blocks Cloudflare-injected scripts; once it relaxes, any
still-active body rewriter's output would execute on preview origins.

## Evidence (field-verified 2026-08-19)

Responses from `api.safespaces.dev` (the zone fronting the workspace
dev-preview tunnel) arrive with an injected script tag that the origin
never sent:

```html
<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js/v4513..." ...>
```

This is Cloudflare's automatic RUM beacon (Browser Insights / Web Analytics
automatic instrumentation). Consequences through the dev-preview path:

1. **Previews are not byte-accurate** — the developer sees bytes their
   dev server never emitted.
2. **Under the planned relaxed CSP, the injected script would execute**
   on preview origins (T8 hazard).
3. It proves an intermediary mutates HTML bodies — the same class of
   actor that caused the original stale-cache debugging saga.

## Scope of change (zone: safespaces.dev)

Zone-level settings, **off for the whole zone**. There is no per-hostname
exception for these features; if RUM is wanted elsewhere, use the manual
Web Analytics snippet on chosen pages instead of automatic injection.

| Feature | Where it actually is (2026-08-20: dashboard paths UNVERIFIED — Cloudflare has reorganized; menu names below are historical and reported missing on the current UI. Use the API discovery below as the source of truth.) | API (zone_settings) |
|---|---|---|
| Web Analytics automatic beacon | **Likely ACCOUNT scope, not zone**: dash.cloudflare.com → account → Web Analytics → sites list → automatic instrumentation. (Zone-level search finds nothing — field-confirmed 2026-08-20.) | discover via `GET zones/:id/zone_settings` (see below) |
| Rocket Loader | Dashboard control reported missing (deprecated by CF) — verify via API whether the setting still exists | `rocket_loader` (may be absent = retired) |
| Email Address Obfuscation | Zone → Scrape Shield (search "Scrape Shield") | `email_obfuscation` = `off` |
| Auto Minify (JS/CSS/HTML) | **removed by Cloudflare Aug 2024** — verify absent via API | `minify` (may be absent = retired) |

**IMPORTANT (2026-08-20 correction):** the original version of this runbook
asserted dashboard paths were "current as of 2026-08" — that currency claim
was wrong (written from pre-2026 knowledge; Cloudflare removed/deprecated
several of these features and moved Web Analytics to account scope). The
canonical procedure is the API: enumerate `zone_settings`, act on what
actually exists, and verify by byte-diff (§ Verification) — which is
independent of which toggle did the injecting. Also: first confirm the
beacon still injects at all (browser view-source on any dev-preview HTML
page, search `beacon`) — if Cloudflare retired the feature, this runbook
reduces to recording the fact and re-verifying before Phase 2.

**Honest note on the beacon toggle:** the RUM beacon's exact zone-settings
key has moved across Cloudflare API revisions (Browser Insights →
Web Analytics automatic instrumentation). Rather than hard-coding a
possibly-stale key, discover it live:

```bash
CF_TOKEN=... ZONE_ID=...
curl -s -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/zone_settings" \
| python3 -c 'import json,sys; [print(s["id"], s["value"]) for s in json.load(sys.stdin)["result"] if s["id"] in ("rocket_loader","email_obfuscation","web_analytics","browser_insights","automatic_platform_optimization","minify")]'
```

Whatever key reports the beacon feature enabled — turn it off via
`PATCH zones/:ID/zone_settings` with `{"items":[{"id":"<key>","value":"off"}]}`
(value types vary; string toggles for the loader, "on"/"off").

Requires a token with **Zone → Zone Settings → Edit** on the zone.

## Why zone-wide is acceptable

- `api.safespaces.dev` is an API origin; RUM beacons on JSON endpoints are
  useless anyway.
- The frontend SPA (`app.safespaces.dev`, if separate) does not need
  automatic RUM; the manual snippet gives the same data with origin control.
- Byte-accuracy of the dev-preview path is a product feature (epic-66);
  silent mutation defeats it.

## Verification (definitive, toggle-independent)

The acceptance test from `ACCEPTANCE.md` §2.A4 — byte identity through the
tunnel vs. in-pod origin. Run from inside a workspace with a dev server on
:5173 and dev preview enabled:

```bash
# inside the pod
curl -s http://127.0.0.1:5173/stress.html -o /tmp/local.html
# through the tunnel (browser session cookie)
curl -s --compressed -H "Cookie: lsp_session=<VALUE>" \
  "https://api.safespaces.dev/api/v1/workspaces/<WS>/dev-preview/5173/stress.html" \
  -o /tmp/tunnel.html
diff /tmp/local.html /tmp/tunnel.html && echo BYTE-IDENTICAL
grep -c beacon.min.js /tmp/tunnel.html   # must be 0
```

**PASS:** `BYTE-IDENTICAL` and grep count 0. Headers may differ (the API
edge legitimately adds headers); bodies must not.

Also verify Rocket Loader / obfuscation did not leave rewrites on non-HTML
(dev servers serve JS/CSS): fetch one JS asset both ways and diff.

## Rollback

Re-enable the zone settings; re-run verification. No cluster state is
touched by this change.

## Status tracking — CLOSED 2026-08-20

- [x] Beacon: retired zone-wide by Cloudflare (no WA ruleset/setting; 0 refs
      in live HTML) — moot, recorded
- [x] Rocket Loader / Minify ×3 / APO / Polish / Mirage: already off (enumeration)
- [x] Email obfuscation off — PATCHed 2026-08-20, authoritative re-read `off`
- [x] Server-side excludes off — PATCHed 2026-08-20, authoritative re-read `off`
- [x] WebSockets: on (required) — untouched
- [x] A4 byte-identity PASS — browser verification (mobile-friendly page:
      `…/dev-preview/5173/verify-rewriters.html`): all three rewriter markers
      literal (email, no email-protection, sse markers) AND SHA-256 of the
      tunneled bytes == pod original (`310bf39f…d520e`). Dev-preview HTML is
      byte-identical from pod to browser.

**Epic-66 Phase 0 is fully closed**: P0-1/P0-2 shipped in v0.16.0 (deployed
2026-08-20T04:21Z, live-accepted A1 no-store + A2 WS echo RTT 31ms),
P0-3 dispositioned (docs merged), P0-4 closed above. The T8 sequencing
prerequisite for Phase 2 (CSP relaxation) is satisfied.

## Field enumeration results (2026-08-20, read-only API token)

Zone `safespaces.dev` (527902a0…), queried via `/zones/:id/settings/{id}`
(the collection endpoint no longer routes; settings are per-endpoint):

| Setting | Found value |
|---|---|
| rocket_loader | off |
| minify (css/html/js) | all off |
| automatic_platform_optimization | off |
| polish / mirage | off / off |
| websockets | **on** (required — keep) |
| email_obfuscation | **on — remaining action** |
| server_side_excludes | **on — remaining action** |
| browser_insights / web_analytics | **"Undefined zone setting"** — does not exist |

Rulesets on the zone: only sanitize / firewall-managed / ddos_l7 — **no
web_analytics injection ruleset**. Live HTML on apex/www/chat contains
zero beacon references. **Conclusion: the automatic beacon injection
observed 2026-08-19 no longer exists on this zone** (Cloudflare retired or
relocated the feature); P0-4's beacon leg is moot. Remaining work is the
two body rewriters above (`email_obfuscation`, `server_side_excludes`)
for dev-preview byte-accuracy.

Off-switch (needs a token with Zone Settings Edit; the enumeration token
is read-only):

```bash
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"value":"off"}' \
  "https://api.cloudflare.com/client/v4/zones/527902a031ba7d8ab430dd2bd8c71ccb/settings/email_obfuscation"
# repeat with .../settings/server_side_excludes
```

Byte-accuracy probe: `…/dev-preview/5173/rewriter-probe.html` (pod-local
md5 36e748b957fdd15101f5ae24880104c0) — contains a literal email and an
<!--sse--> block; view-source through the tunnel must match the pod bytes
exactly.
