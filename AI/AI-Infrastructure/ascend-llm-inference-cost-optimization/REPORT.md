# Qwen3.6-35B-A3B on Ascend 910: Inference Cost Optimization

**Final result: USD 13.96 per million output tokens** (829.1 output tok/s, 640/640
requests, zero errors) on a 16-die Ascend 910 host serving a 64K-context agent
workload with ~90% repeated prompt text.

That is **43.6% cheaper than the previously accepted USD 24.77/M baseline**, reached
without buying hardware, changing the model, or upgrading vLLM.

Date: 2026-08-03. Model: Qwen3.6-35B-A3B (BF16, MoE 256 experts, top-8).
Runtime: vLLM 0.22.1 / vLLM-Ascend 0.22.1rc1 / Mooncake 0.3.11.post1, CANN 8.5.2.

---

## 1. Two environments

| Role | Host | Internal IP | Contents |
|---|---|---|---|
| **Serving (NPU)** | `<npu-host>` | `vllm-host` | 16× Ascend 910 die, 2 TB host RAM. vLLM runs inside Docker container `qwen3.6-8card`. Serving ports 8002-8009, DP supervisor 8020, Mooncake master 9003/50088. Logs: `/mnt/sfs_turbo/script/qwen3.6-8card/*.log` (container clock = UTC). |
| **Load generation** | `<loadgen-host>` | `loadgen-host` | Benchmark driver. Scripts and results under `/root/qwen8-throughput/`. |
| *(jump host)* | `<jump-host>` | — | Reaches both of the above; holds the document/PRD history. |

`vllm-host` and `<npu-host>` are the same machine (internal vs. public
address). Earlier notes that treated them as an "old" and a "new" host were wrong.

---

## 2. Hardware: 16 independent dies, not 8

`npu-smi` prints 16 rows. These are **16 independently addressable 64 GiB devices**
(A3-class dual-die packaging), not 8 devices with shared memory. Proof:

- Two dies of the same NPU report different HBM usage (61,240 vs 60,051 MB).
- Each vLLM worker occupies ~57 GB; two 57 GB workers cannot share one 64 GB pool.
- Idle dies sit at ~3 GB / 0% AICore / ~170 W while busy dies are at ~60 GB /
  100% / 386-487 W.

The original deployment set `ASCEND_RT_VISIBLE_DEVICES=0..7` and therefore used
**half the machine**. Every cost figure produced before this was found describes a
half-idle host. Lighting up all 16 dies is the single largest lever in this report.

---

## 3. Workload: simulating a real agent

Chosen to mirror a production agent loop rather than a synthetic throughput test.

| Property | Value |
|---|---|
| Input length | 65,280 tokens |
| Output length | 256 tokens |
| Shared prefix between consecutive turns of a session | 58,982 tokens (**90.35%**) |
| Request mix | **70% HBM-hot / 20% DRAM-warm / 10% cold** |
| Unique hot sessions | 56 (each reused 8× in the measured window) |
| Cache-eviction churn | 56 unique 65,535-token prefixes |

The 70/20/10 mix is what makes this a *tiered-cache* benchmark: hot turns should be
served from HBM, warm turns from the Mooncake DRAM tier, and 10% must be computed
cold. Measurement phases run in order `warm_fill → eviction_pass → hot_fill →
measure`, and only the `measure` window is scored.

The **10% cold ratio is a business fact, not a tuning knob** — see §8 on why
lowering it makes the strict cost metric *worse*.

---

## 4. Deployment topology

```
16 dies → TP2 × DP8 × EP16
  8 DP engines, each = 2 dies (tensor-parallel pair)
  Experts sharded across all 16 dies
  Per-engine KV cache: 3,826,957 tokens (43.86 GiB)
```

Serving configuration (see `deploy/start-bf16-16die-dpm.sh`):

| Setting | Value | Why |
|---|---|---|
| `--max-num-batched-tokens` | 8192 | Beat 16384 by 24.6% on this cache-dominated workload; 32768 OOMs on MoE temp allocation |
| `--max-num-seqs` | 128 | Per engine; 1024 aggregate, never binding |
| `--gpu-memory-utilization` | 0.918 | Raising it only reserves idle KV blocks and squeezes MoE temp space |
| `--enable-prefix-caching` | on | Core of the workload |
| `--no-async-scheduling` | **required** | Async scheduling + Mooncake crashes the hybrid KV block allocator (`assert block.ref_cnt == 0`) |
| KV connector | `AscendStoreConnector` / Mooncake, `load_async=false` | Async load enters a scheduler capacity loop and OOMs at 64K |
| Graph capture | `FULL_DECODE_ONLY` | — |
| Extras | FlashComm v1, shared-expert multistream overlap, CPU binding | — |

### Mooncake CPU-DRAM KV tier

Host RAM serves as the warm KV tier below HBM.

| Parameter | Value |
|---|---|
| `global_segment_size` | 64 GB per worker |
| Aggregate capacity | 16 × 64 GiB = **1,099,511,627,776 B (1100 GB)** |
| Protocol | `ascend`, P2PHANDSHAKE, `prefer_alloc_in_same_node: true` |
| Load mode | **synchronous** |

Sizing rule: host has 2010 GB, non-Mooncake usage is ~770 GB, so ~1100 GB is the
safe ceiling. Do **not** use 16 × 88 GiB (1512 GB) — it exceeds host RAM.

Measured value of the DRAM tier depends entirely on prefix length:

- **64K prefixes — worth it.** DRAM hit 0.584 s vs cold prefill 11.453 s (19.6×).
- **~4K prefixes — not worth it.** Tiered run was 17.0% slower and 20.5% more
  expensive than HBM-only APC; the synchronous connector overhead exceeded the
  recompute it saved.

---

## 5. Session affinity (the largest software win)

With plain data-parallel load balancing, a session's turns land on a random engine.
Its KV lives on whichever engine served the previous turn, so the local-HBM hit
probability collapses to **1/N_engines**. Measured local hit rate fell from 45-57%
on DP4 to 11.9-16.0% on DP8 — exactly the predicted halving.

**Fix:** run vLLM in multi-port external-LB mode so each DP engine gets its own
port, and route each session deterministically.

```bash
--data-parallel-multi-port-external-lb
--data-parallel-supervisor-port 8020      # must NOT fall inside 8002-8009
```
Client side: `rank = session_id % n_engines`, request goes to port `8002 + rank`.

Two implementation traps, both of which silently disable affinity:

1. **Derive the rank from the session id, not the list index.** The original
   `items()` used the enumerate index, so the 8 repetitions of one session were
   spread across two different ranks.
2. **Aggregate `/metrics` across all 8 ports.** Each port exposes only its own
   engine; scraping one port shows 1/8 of the traffic and invalidates all cache
   evidence.

**Result: local prefix-cache hit ratio rose from 14.2% to 65.8% of lookups.**

### Why affinity also raises the concurrency ceiling

Per-engine KV budget:

```
cacheable space per engine ≈ 3,826,957 − (C / 8) × 65,280      [tokens]
```

Without affinity, the hot set must be replicated on *every* engine
(56 sessions × 57,344 = 3.21 M tokens). At C384 only 0.69 M tokens remain — 22% of
what is needed, so the cache is evicted by in-flight requests. With affinity each
engine holds only `U/8` sessions (0.40 M tokens), which fits with 1.7× headroom.

**Affinity is therefore a prerequisite for high concurrency, not an independent
optimization.** Running C384 without it produces a cache collapse, not a speedup.

---

## 6. Concurrency ladder

| Config | output tok/s | USD/M output | p99 TTFT | KV peak | Errors |
|---|---:|---:|---:|---:|---:|
| 8-die DP4, C128 (old baseline) | 467.3 | 24.77 | 87.2 s | 31.9% | 0 |
| 16-die DP8, C256, no affinity | 739.8 | 15.65 | 102.5 s | 53.1% | 0 |
| **16-die DP8, C384, affinity** | **829.1** | **13.96** | **176.4 s** | **49.7%** | **0** |

C384 used `--pool-mult 4 --hot-unique 56` (640 measured requests, mix held at
70/20/10). Gain over C256 was +12.1%, just above the 10% stop threshold, and p99
landed at 176.4 s against a 180 s budget — **C384 is at the knee**. Do not run C512:
in-flight KV alone (4.18 M tokens/engine) exceeds the 3.83 M capacity.

Note that measured KV peak at C384 (49.7%) came in far below the naive prediction
(81.9%) because concurrent requests sharing a prefix share physical blocks. The
budget formula above is therefore conservative.

---

## 7. Techniques evaluated and rejected

| Technique | Verdict | Evidence |
|---|---|---|
| **W8A8 quantization** (msModelSlim, `--quantization ascend`) | **Not adopted — inconclusive** | Measured USD 25.44/M vs BF16 24.77/M. That run was contaminated by the client-side concurrency cap and by multi-port partitioning, and **no accuracy gate was ever run**. Worth re-testing as a single variable on the current stack. |
| **MTP speculative decoding** | **Forbidden with prefix caching** | Locally produced zero cache hits. Upstream confirms: vllm#43559 (~20% accuracy drop with APC+MTP on this exact model), vllm#38182, vllm-ascend#9247. |
| **P/D disaggregation** | Not pursued | Upstream states disaggregated prefill does not raise throughput; on one host it duplicates weights and partitions capacity. With 90% of traffic skipping prefill, taking dies from the decode pool raises cost. Revisit only under a hard latency SLO. |
| **Async Mooncake load** (`load_async=true`) | Rejected | Scheduler capacity loop plus 64K prefill OOM (MoE temp 6.37-6.46 GiB), down to `gpu_memory_utilization=0.85`. |
| **vLLM async scheduling + Mooncake** | Rejected | Hybrid KV block allocator assertion `block.ref_cnt == 0`, 418 request errors. |
| **32,768 scheduler budget** | Rejected | OOM on first 64K cold request. |
| **16,384 scheduler budget** | Superseded | Stable, but 24.6% more expensive than 8,192. |
| **`use_layerwise`** | Unsupported | Qwen3.5/3.6 hybrid linear/full attention. |
| **Fabric Memory** | Unsupported | Driver reports cross-server mode unavailable. |
| **CPU offload via `OffloadingConnector`** | Blocked | Ascend plugin imports the absent `vllm.v1.kv_offload.abstract` on 0.22.1. |
| **Raising `gpu_memory_utilization`** | Not attempted at C384 | In-flight KV already high; compresses MoE temp space, which is the known OOM class. |

---

## 8. Cost accounting: the billing convention decides the answer

Three conventions applied to the same C384 measurement:

| Convention | Definition | Result |
|---|---|---|
| Face value | every prompt token billed | **USD 0.0545 / M** |
| Cache-discounted | cached input billed at 10% (industry norm) | ~USD 0.25 / M |
| Strict | cached input not billed at all | ~USD 0.48 / M |

**The strict convention is a perverse optimization target.** Cache hits are free to
the customer but still consume DRAM bandwidth, HBM and machine time — the rent is
unchanged. So the better the cache, the fewer billable tokens, and the higher the
strict price. Optimizing for it drives you toward *disabling* the cache.

Concretely: cutting cold requests from 10% to 5% improves output-token cost by ~9%
but degrades the strict metric by **76%** (0.587 → 1.036), because billable tokens
fall much faster than wall-clock does. This is why §3 treats the cold ratio as a
business fact rather than a knob.

**Recommendation: bill cached input at a discount (~10%), which is both the industry
norm and economically self-consistent.** Under that convention the USD 0.35/M target
was already met at C256 and is comfortably met at C384.

> **Caveat on cache counters.** `prefix_cache_hits_total` counts per scheduler
> lookup, and a chunked-prefill 64K request produces several lookups (measured
> queries ≈ 1.88× prompt tokens at C384). Hit *ratios* are therefore valid for
> comparison across runs, but converting them into "N requests served from HBM" is
> not. The discounted and strict figures above inherit that uncertainty; only the
> face-value figure is derived purely from client-side token counts.

---

## 9. Three defects that invalidated earlier conclusions

Most of the apparent "optimization plateau" in this project was measurement error.
These are the transferable lessons.

### F1 — The load generator capped itself at 100 connections

`aiohttp.ClientSession(timeout=...)` with no explicit connector defaults to
`TCPConnector(limit=100)`. Every run labelled above C100 actually ran at ~C100.
The fingerprint is unmistakable: measured `running` tracked nominal concurrency
exactly at C32 and C64, then froze at 86-99 for C128 *and* C256.

This single defect invalidated "C128 is the cost minimum", "more concurrency does
not help", "the p99 budget is exceeded" (TTFT was timed before the connection was
acquired, so it included client queueing), and the earlier verdict that session
affinity had failed.

**Fix:** `TCPConnector(limit=0, limit_per_host=0)`, start the TTFT clock after the
semaphore is acquired, and report client queue wait as its own field.
**Gate:** peak `running` must scale linearly with nominal concurrency.

### F2 — Data parallelism halved the cache hit rate

Covered in §5. Fingerprint: a local hit rate that lands near `1/N_engines`.

### F3 — A restart silently shrank the Mooncake pool

Clearing an unrelated stale process re-registered Mooncake segments under a newer
config, dropping capacity from 1512 GB to 825 GB. The pool then ran 83-89% full and
evicted **149-300 GB mid-measurement**, discarding the benchmark's own warm tier.
External hit rate fell 80% → 58.6%, tokens needing recomputation rose 5.1×, and
throughput dropped 32% — which was very nearly misattributed to the F1 fix.

**Gate:** `master_evicted_size_bytes` must not increase during the measured window;
if it does, discard the run. Reset the pool before every run — the churn phase
writes hundreds of GB and two runs will saturate it.

### Operational rule that came out of all three

vLLM binds with `SO_REUSEPORT`, so **a second server on the same port never fails to
bind** — two listeners simply split connections by 4-tuple hash. A dead-engine
leftover served part of the traffic and produced 320 spurious 500s. Always assert
`ps -eo args | grep -c "[v]llm serve"` is 0 before launch and 1 after, and smoke-test
with `/v1/completions` rather than `/health` (a zombie's `/health` can still return
200).

---

## 10. Reproduction

```bash
# 1. Pre-flight (on the NPU host)
pkill -f "vllm serve" || true; sleep 5
[ "$(ps -eo args | grep -c '[v]llm serve')" -eq 0 ] || exit 1
#    reset the Mooncake pool, confirm capacity 1,099,511,627,776 and evicted=0

# 2. Serve, 16 dies, session affinity
deploy/start-bf16-16die-dpm.sh          # ports 8002-8009, supervisor 8020

# 3. Smoke every port with a real completion
for p in 800{2..9}; do
  curl -s -m 90 http://127.0.0.1:$p/v1/completions -H 'Content-Type: application/json' \
    -d '{"model":"Qwen3.6-35B-A3B","prompt":"hello","max_tokens":4}' | grep -q '"text"' || exit 1
done

# 4. Benchmark (on the load-generation host)
python3 scripts/agent90_mix.py --run-id 90 --concurrency 384 \
  --pool-mult 4 --hot-unique 56 --dp-engines 8 \
  --url http://vllm-host:8002/v1/completions \
  --metrics-url "http://vllm-host:8002/metrics,...,http://vllm-host:8009/metrics" \
  --output results/c384.json
```

Acceptance gates for any run to count: zero errors; `mooncake_eviction_delta_bytes`
== 0; peak `running` ≈ nominal concurrency ±10%; all 8 engine labels present in the
aggregated metrics; per-port request spread ≤ 20%; and every cost claim reported
under all three billing conventions with the convention named.

---

## 11. What to try next

1. **W8A8 as a clean single variable** on the current 16-die + affinity stack, with
   an agent-task accuracy gate (tool-call JSON fidelity, not just perplexity).
   Decode is memory-bandwidth-bound, so this remains the largest untested lever.
2. **Idle-time backfill.** Every price here assumes 100% utilization of a fixed
   monthly rental. At 70% duty cycle the same configuration costs 43% more per
   token than the headline. A pre-emptible low-priority queue converts idle
   die-seconds into billable tokens and moves realized cost more than any engine
   tuning.
3. **Version bump on a separate snapshot** for FlashComm v2, MoE weight prefetch,
   `--inter-prefill-budget`, and the T-LRU / ARC eviction work — and re-check
   whether MTP and prefix caching can finally coexist.
