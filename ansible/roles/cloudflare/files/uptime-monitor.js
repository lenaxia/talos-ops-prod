/**
 * Uptime Monitor — Cloudflare Worker (ES module)
 *
 * Runs on Cloudflare's edge on a cron schedule and probes public endpoints
 * from OUTSIDE the LAN. This catches external-path failures that split-horizon
 * DNS hides from internal monitoring (WAN down, Cloudflare issues, broken
 * port-forwards, expired certs).
 *
 * State transitions are tracked in a KV namespace. On up->down a firing alert
 * is pushed to Prometheus Alertmanager (/api/v2/alerts); on down->up the same
 * alert (matched by labels) is pushed as resolved. Alertmanager routes to the
 * existing pushover receiver via severity=critical.
 *
 * Firing alerts carry endsAt = now + 10m and are re-posted every run, so if
 * this worker dies, the alerts auto-resolve instead of paging forever.
 *
 * Bindings (set by the ansible cloudflare role):
 *   - UPTIME_KV:            KV namespace (required) — per-endpoint state
 *   - UPTIME_ENDPOINTS:     plain_text — comma-separated URLs to probe
 *   - ALERTMANAGER_URL:     plain_text — e.g. https://alerts.thekao.cloud
 *   - ALERTMANAGER_ALERTNAME (optional, default ExternalEndpointDown)
 */

const DEFAULT_TIMEOUT_MS = 15000;
const FIRING_TTL_MS = 10 * 60 * 1000; // must exceed the cron interval
const USER_AGENT = "uptime-monitor-worker/1.0";

export default {
  async scheduled(event, env) {
    const endpoints = splitEndpoints(env.UPTIME_ENDPOINTS);
    const alertmanager = (env.ALERTMANAGER_URL || "").replace(/\/+$/, "");
    const alertname = env.ALERTMANAGER_ALERTNAME || "ExternalEndpointDown";

    if (endpoints.length === 0) {
      console.log("UPTIME_ENDPOINTS not set; nothing to probe");
      return;
    }

    const results = await Promise.all(endpoints.map((url) => probe(url)));
    const down = results.filter((r) => !r.ok);
    console.log(
      JSON.stringify({ total: results.length, up: results.length - down.length, down: down.length })
    );

    const alerts = [];

    for (const r of results) {
      const prev = await env.UPTIME_KV.get(stateKey(r.url));
      const wasDown = prev === "down";
      const isDown = !r.ok;

      if (isDown) {
        // new outage or still down: push/refresh a firing alert (endsAt keeps
        // it alive between runs; Alertmanager dedupes by label set)
        alerts.push({
          labels: {
            alertname,
            severity: "critical",
            instance: r.url,
            source: "cloudflare-worker",
          },
          annotations: {
            summary: `External endpoint down: ${r.url}`,
            description: `Probe from Cloudflare edge failed: ${
              r.error || `HTTP ${r.status}`
            }`,
          },
          startsAt: new Date().toISOString(),
          endsAt: new Date(Date.now() + FIRING_TTL_MS).toISOString(),
          generatorURL: r.url,
        });
      } else if (wasDown) {
        // recovered: same labels with endsAt in the past resolves the alert
        alerts.push({
          labels: {
            alertname,
            severity: "critical",
            instance: r.url,
            source: "cloudflare-worker",
          },
          annotations: {
            summary: `External endpoint recovered: ${r.url}`,
          },
          startsAt: new Date().toISOString(),
          endsAt: new Date().toISOString(), // resolved
          generatorURL: r.url,
        });
      }

      await env.UPTIME_KV.put(stateKey(r.url), isDown ? "down" : "up");
    }

    if (alerts.length > 0) {
      if (!alertmanager) {
        console.error("Transitions detected but ALERTMANAGER_URL not set");
      } else {
        const rc = await pushAlerts(alertmanager, alerts);
        console.log(`Alertmanager accepted ${alerts.length} alert(s): HTTP ${rc}`);
      }
    }
  },

  // Manual trigger for testing: curl the worker URL (workers.dev disabled by
  // default; enable temporarily or use `wrangler dev` / the dashboard)
  async fetch(request, env) {
    const endpoints = splitEndpoints(env.UPTIME_ENDPOINTS);
    const results = await Promise.all(endpoints.map((url) => probe(url)));
    return new Response(JSON.stringify(results, null, 2), {
      headers: { "content-type": "application/json" },
    });
  },
};

function splitEndpoints(raw) {
  return (raw || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function stateKey(url) {
  return `state:${url}`;
}

async function probe(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      method: "GET",
      redirect: "follow",
      headers: { "User-Agent": USER_AGENT },
      signal: controller.signal,
      cf: { cacheTtl: 0 }, // never serve probe responses from CF cache
    });
    // 2xx/3xx = healthy; 401/403 from forward-auth gates still proves the
    // external path (DNS + WAN + Traefik + cert) is alive
    return { url, ok: res.status < 500, status: res.status };
  } catch (err) {
    return { url, ok: false, status: null, error: err.message };
  } finally {
    clearTimeout(timer);
  }
}

async function pushAlerts(alertmanager, alerts) {
  try {
    const res = await fetch(`${alertmanager}/api/v2/alerts`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(alerts),
    });
    return res.status;
  } catch (err) {
    console.error(`Alertmanager push failed: ${err.message}`);
    return null;
  }
}
