#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


def metric(text, name, labels=()):
    total = 0.0
    for line in text.splitlines():
        if not line.startswith(name) or any(label not in line for label in labels):
            continue
        try:
            total += float(line.rsplit(" ", 1)[1])
        except (ValueError, IndexError):
            pass
    return total


def delta(d, name, labels=(), source="vllm"):
    before = d["metrics"][f"{source}_before"]
    after = d["metrics"][f"{source}_after"]
    return metric(after, name, labels) - metric(before, name, labels)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("directory")
    p.add_argument("--output")
    args = p.parse_args()
    rows = []
    for path in sorted(Path(args.directory).glob("c*.json"),
                       key=lambda x: int(re.search(r"c(\d+)", x.stem).group(1))):
        d = json.loads(path.read_text())
        if "measure" not in d or "economics" not in d:
            continue
        m = d["measure"]
        rows.append({
            "concurrency": d["concurrency"],
            "requests": m["requests"],
            "success": m["success"],
            "errors": m["errors"],
            "duration_s": m["duration_s"],
            "avg_latency_s": m["avg_ttft_s"],
            "p99_latency_s": m["p99_ttft_s"],
            "output_tokens_per_second": d["economics"]["output_tokens_per_second"],
            "usd_per_million_output_tokens": d["economics"]["usd_per_million_output_tokens_at_100pct_utilization"],
            "local_prefix_hit_tokens": delta(d, "vllm:prefix_cache_hits_total"),
            "external_prefix_hit_tokens": delta(d, "vllm:external_prefix_cache_hits_total"),
            "external_transfer_tokens": delta(d, "vllm:prompt_tokens_by_source_total", ('source="external_kv_transfer"',)),
            "mooncake_batch_lookups": delta(d, "master_batch_get_replica_list_requests_total", source="master"),
            **d.get("runtime_max", {}),
        })
    result = {"runs": rows}
    if rows:
        valid = [r for r in rows if r["errors"] == 0 and r["success"] == r["requests"]]
        result["best_zero_error"] = min(valid, key=lambda r: r["usd_per_million_output_tokens"]) if valid else None
    payload = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
