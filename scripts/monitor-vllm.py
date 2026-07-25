#!/usr/bin/env python3
"""Monitor vLLM server—poll /metrics and report TTFT, latency, prompt/gen stats."""

import argparse
import re
import sys
import time
import urllib.request
from collections import defaultdict

# ────────────────────────────────────────────────────────────────────────────
# Prometheus text-format helpers
# ────────────────────────────────────────────────────────────────────────────


def fetch_text(url: str, timeout: float = 5) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def parse_metrics(text: str) -> dict[str, list[dict]]:
    """Return {metric_name: [{labels: {}, value: float}, ...]}."""
    metrics: dict[str, list[dict]] = defaultdict(list)
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([\w:]+)\{(.+?)\}\s+([0-9eE.\+\-]+.*)$", line)
        if m:
            name = m.group(1)
            labels_str = m.group(2)
            val_str = m.group(3).split()[0]
            labels = dict(re.findall(r'(\w+)="([^"]*)"', labels_str))
            try:
                value = float(val_str)
            except ValueError:
                continue
            metrics[name].append({"labels": labels, "value": value})
        else:
            m2 = re.match(r"^([\w:]+)\s+([0-9eE.\+\-]+)$", line)
            if m2:
                name = m2.group(1)
                metrics[name].append({"labels": {}, "value": float(m2.group(2))})
    return metrics


def histogram_percentiles(
    buckets: list[dict],
    target_percentiles: tuple[float, ...] = (0.5, 0.9, 1.0),
) -> dict[float, float | None]:
    """Estimate percentiles from Prometheus histogram buckets (cumulative)."""
    sorted_buckets = sorted(buckets, key=lambda b: float(b["labels"].get("le", "inf")))

    total = 0
    parsed: list[tuple[float, float]] = []
    for b in sorted_buckets:
        le_str = b["labels"].get("le", "+Inf")
        le = float(le_str) if le_str != "+Inf" else float("inf")
        count = b["value"]
        total = max(total, count)
        parsed.append((le, count))

    if total == 0:
        return {p: None for p in target_percentiles}

    inf_est: float | None = None
    if parsed and parsed[-1][0] == float("inf") and len(parsed) >= 2:
        last_cnt = parsed[-1][1]
        prev_le = parsed[-2][0]
        prev_cnt = parsed[-2][1]
        if last_cnt > prev_cnt and prev_cnt > 0:
            avg_inc = prev_le / prev_cnt
            inf_est = prev_le + avg_inc * (last_cnt - prev_cnt)

    results: dict[float, float | None] = {}
    for p in target_percentiles:
        target_count = p * total
        lo_le, lo_cnt = 0.0, 0.0
        found = False
        for le, cnt in parsed:
            if cnt >= target_count:
                if le == float("inf"):
                    results[p] = inf_est if inf_est is not None else lo_le
                else:
                    if cnt == lo_cnt:
                        results[p] = le
                    else:
                        frac = (target_count - lo_cnt) / (cnt - lo_cnt)
                        results[p] = lo_le + frac * (le - lo_le)
                found = True
                break
            lo_le, lo_cnt = le, cnt
        if not found:
            results[p] = None

    return results


# ────────────────────────────────────────────────────────────────────────────
# Metrics extraction
# ────────────────────────────────────────────────────────────────────────────

PERCENTILES = (0.5, 0.9, 1.0)


def extract_histograms(metrics: dict[str, list[dict]]) -> dict:
    buckets: dict[str, list[dict]] = defaultdict(list)
    sum_count_sum: dict[str, float] = {}
    sum_count_count: dict[str, float] = {}
    gauges: dict[str, float] = {}

    for name, samples in metrics.items():
        for s in samples:
            lbl = s["labels"]
            val = s["value"]
            if "le" in lbl:
                base = name.removesuffix("_bucket")
                buckets[base].append(s)
            elif name.endswith("_sum") and not name.endswith("_sum_created"):
                sum_count_sum[name[:-4]] = val
            elif name.endswith("_count") and not name.endswith("_count_created"):
                sum_count_count[name[:-6]] = val
            elif name.endswith("_created"):
                pass
            else:
                gauges[name] = gauges.get(name, 0.0) + val

    sum_count: dict[str, tuple[float, float]] = {}
    all_keys = set(sum_count_sum.keys()) | set(sum_count_count.keys())
    for k in all_keys:
        sum_count[k] = (sum_count_sum.get(k, 0), sum_count_count.get(k, 0))

    return {
        "buckets": dict(buckets),
        "sum_count": sum_count,
        "gauges": gauges,
    }


def build_report(parsed: dict) -> dict:
    hist = parsed["buckets"]
    sumcnt = parsed["sum_count"]
    gauges = parsed["gauges"]

    report: dict[str, dict] = {}

    metric_map = {
        "ttft": "vllm:time_to_first_token_seconds",
        "e2e_latency": "vllm:e2e_request_latency_seconds",
        "tpot": "vllm:request_time_per_output_token_seconds",
        "prompt_tokens": "vllm:request_prompt_tokens",
        "gen_tokens": "vllm:request_generation_tokens",
        "queue_time": "vllm:request_queue_time_seconds",
    }

    for key, metric_name in metric_map.items():
        if metric_name in hist:
            percs = histogram_percentiles(hist[metric_name], PERCENTILES)
            report[key] = {f"p{int(p * 100)}": v for p, v in percs.items()}
            sc = sumcnt.get(metric_name)
            if sc:
                total, count = sc
                report[key]["avg"] = total / count if count else 0
                report[key]["count"] = int(count)
        elif metric_name in sumcnt:
            total, count = sumcnt[metric_name]
            report[key] = {"avg": total / count if count else 0, "count": int(count)}

    for gauge_name, display in [
        ("vllm:num_requests_running", "running"),
        ("vllm:num_requests_waiting", "waiting"),
        ("vllm:kv_cache_usage_perc", "kv_cache_usage_perc"),
    ]:
        if gauge_name in gauges:
            report[display] = gauges[gauge_name]

    for counter_name, display in [
        ("vllm:request_success_total", "success"),
        ("vllm:num_preemptions_total", "preemptions"),
    ]:
        if counter_name in gauges:
            report[display] = gauges[counter_name]

    return report


# ────────────────────────────────────────────────────────────────────────────
# Display / main loop
# ────────────────────────────────────────────────────────────────────────────


def format_value(v) -> str:
    if v is None:
        return "  N/A"
    if isinstance(v, float):
        if v >= 10:
            return f"{v:5.1f}"
        elif v >= 1:
            return f"{v:5.2f}"
        else:
            return f"{v:5.4f}"
    return f"{v!s:>5}"


def print_report(report: dict, clear: bool = True):
    if clear:
        print("\033[2J\033[H", end="")
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== vLLM Stats @ {ts} ===\n")

    def row(name, keys, unit=""):
        vals = "  ".join(
            f"{k.upper():>4}: {format_value(report.get(name, {}).get(k))}{unit}"
            for k in keys
        )
        print(f"  {name:<18} {vals}")

    def simple(name, unit=""):
        v = report.get(name)
        val = format_value(v) if v is not None else "  N/A"
        print(f"  {name:<18} {val}{unit}")

    print("  --- Response Latency ---")
    row("ttft", ["p50", "p90", "p100"], "s")
    row("e2e_latency", ["p50", "p90", "p100"], "s")
    row("tpot", ["avg", "p50", "p90"], "s")
    row("queue_time", ["avg", "p50", "p90"], "s")
    print()
    print("  --- Token Stats ---")
    row("prompt_tokens", ["avg", "p50", "p90", "p100"])
    row("gen_tokens", ["avg", "p50", "p90", "p100"])
    print()
    print("  --- Load ---")
    simple("running")
    simple("waiting")
    simple("success", " (total)")
    simple("preemptions", " (total)")
    simple("kv_cache_usage_perc", "%")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Poll vLLM /metrics endpoint and display request statistics"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="vLLM server base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=float,
        default=2.0,
        help="Poll interval in seconds (default: 2)",
    )
    parser.add_argument("--once", action="store_true", help="Fetch once and exit")
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not clear terminal between refreshes",
    )
    args = parser.parse_args()

    metrics_url = args.url.rstrip("/") + "/metrics"
    print(f"Polling {metrics_url} every {args.interval}s ...\n")
    if not args.once:
        print("Press Ctrl+C to stop.\n")
        time.sleep(0.5)

    try:
        while True:
            try:
                text = fetch_text(metrics_url)
                metrics = parse_metrics(text)
                parsed = extract_histograms(metrics)
                report = build_report(parsed)
                print_report(report, clear=not args.no_clear and not args.once)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
