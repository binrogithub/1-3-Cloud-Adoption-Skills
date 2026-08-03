---
name: ascend-llm-cost-optimization
description: Benchmark and reduce LLM inference token cost on Huawei Ascend 910 NPUs with vLLM-Ascend and a Mooncake DRAM KV tier. Use when working on Qwen3.6-35B-A3B serving, 64K-context agent workloads, prefix-cache tiering, data-parallel session affinity, concurrency tuning, or when a throughput/cost benchmark gives results that look wrong.
---

# Ascend LLM inference cost optimization

Field-tested playbook from taking Qwen3.6-35B-A3B on 16× Ascend 910 dies from
**USD 24.77 → 13.96 per million output tokens** (829 output tok/s, zero errors) on a
64K-context agent workload with ~90% repeated prompt text.

Read `REPORT.md` for the full write-up. This file is the operating checklist.

## Start here when a benchmark result looks wrong

Three measurement defects caused most of the apparent plateau in this project.
Check them **before** believing any throughput or cost number.

1. **Is the load generator actually driving the concurrency it claims?**
   `aiohttp.ClientSession(timeout=...)` without an explicit connector caps at
   **100 connections** (`TCPConnector(limit=100)`). Fingerprint: peak `running`
   tracks nominal concurrency at C32/C64, then freezes at ~95-99 for C128 and C256
   alike. Fix with `TCPConnector(limit=0, limit_per_host=0)`.
   *Gate: peak `running` must scale linearly with nominal concurrency.*

2. **Did the KV pool evict during the measured window?**
   Compare `master_evicted_size_bytes` before and after. Any increase means the
   warm tier was destroyed mid-run — discard the result. Reset the pool before
   every run; the churn phase writes hundreds of GB.

3. **Is a stale server sharing the port?**
   vLLM binds with `SO_REUSEPORT`, so a second instance on the same port **never
   fails to bind**; two listeners split traffic by 4-tuple hash and a dead-engine
   leftover returns `EngineDeadError` 500s. Assert
   `ps -eo args | grep -c "[v]llm serve"` is 0 before launch and 1 after.
   Smoke-test with `/v1/completions`, never `/health` — a zombie can still 200.

## Data-parallel deployments need session affinity

Without it a session's turns land on a random engine and the local-HBM hit rate
collapses to **1/N_engines** (measured: 45-57% at DP4 → 12-16% at DP8).

- Serve with `--data-parallel-multi-port-external-lb` plus
  `--data-parallel-supervisor-port` **outside** the engine port range.
- Route `rank = session_id % n_engines` → port `base + rank`.
- Derive the rank from the **session id, not the list index**, or repeated turns
  scatter across ranks and affinity silently does nothing.
- Scrape `/metrics` from **all** engine ports; each exposes only its own engine.

Affinity is a **prerequisite for high concurrency**, not an independent win:

```
cacheable space per engine ≈ total_kv_tokens − (C / n_engines) × input_len
```

Without affinity the hot set must be replicated on every engine; with it each
engine holds only `U/n_engines`. That 8× reduction is what makes C384 fit.

## Known-bad configurations — do not retry

`load_async=true` (capacity loop + 64K OOM) · vLLM async scheduling with Mooncake
(`assert block.ref_cnt == 0`) · 32768 scheduler budget (OOM) · MTP together with
prefix caching (zero hits locally; upstream vllm#43559 reports ~20% accuracy loss on
this model) · `use_layerwise` on Qwen3.5/3.6 · Mooncake DRAM tier for short (~4K)
prefixes (20.5% more expensive than HBM-only) · scaling the request pool by
inflating unique hot sessions (blows the KV budget).

## Cost accounting

Report every cost claim under **all three conventions**, and name the one you use:
face value, cache-discounted (cached input at ~10%, the industry norm), and strict
(cached input unbilled).

**Never optimize for the strict convention.** Cache hits are free to the customer
but still consume bandwidth, HBM and machine time, so a better cache means fewer
billable tokens and a *higher* strict price — its optimum is to disable caching.
Measured: cutting cold requests 10% → 5% improves output-token cost ~9% while
degrading the strict metric 76%.

Also note `prefix_cache_hits_total` counts per scheduler lookup, and a chunked
64K prefill produces several lookups per request. Hit *ratios* compare fine across
runs; converting them to "N requests served from HBM" does not.

## Files

- `REPORT.md` — full technical write-up: topology, workload, results, rejected paths.
- `deploy/start-bf16-16die-dpm.sh` — **recommended**: 16 dies, TP2×DP8×EP16,
  multi-port session affinity.
- `deploy/start-bf16-16die.sh` — same topology with internal load balancing.
- `deploy/start-w8a8-affinity.sh` — W8A8 quantized variant (tested, inconclusive,
  no accuracy gate yet).
- `deploy/mooncake.json` — DRAM KV tier, 64 GB/worker. Size to
  `host_ram − non_mooncake_usage`; 16 × 88 GiB exceeds a 2 TB host.
- `deploy/start-mooncake-master.sh`, `container.sh`, `clean-vllm.sh`.
- `scripts/agent90_mix.py` — the 70/20/10 agent benchmark (64K input, 90% shared
  prefix, 256 output). Phases: `warm_fill → eviction_pass → hot_fill → measure`.
- `scripts/kv64k_bench.py` — request driver and single-path cold/HBM/DRAM diagnostic.
- `scripts/three_cost_metrics.py`, `scripts/summarize_agent90.py` — cost reporting.
- `reference/` — PRDs v4-v6 and the earlier optimization reports, including the
  full defect investigations.

## Reproduce the best result

```bash
python3 scripts/agent90_mix.py --run-id 90 --concurrency 384 \
  --pool-mult 4 --hot-unique 56 --dp-engines 8 \
  --url http://<npu-host>:8002/v1/completions \
  --metrics-url "http://<npu-host>:8002/metrics,...,http://<npu-host>:8009/metrics" \
  --output results/c384.json
```

C384 sits at the knee: +12.1% over C256 with p99 TTFT 176.4 s against a 180 s
budget. **Do not run C512** — in-flight KV alone exceeds per-engine capacity.
