# Qwen3.6 64K Inference Cost Optimization Report

## Executive summary

This report evaluates Qwen3.6-35B-A3B inference on eight Ascend NPUs for an
agent workload with 65,280 input tokens, 256 output tokens, and approximately
90% repeated prompt text. The target architecture keeps hot KV blocks in HBM
and uses a Mooncake-backed DRAM tier for evicted, reusable blocks. Results are
accepted only when the request error count is zero and cache-tier metrics prove
the intended HBM or DRAM path.

The lowest validated sample is the synchronous 8,192-token scheduler budget at
C128: 467.27 output tokens/s and USD 24.77 per million output tokens. An
independent first run produced USD 25.86/M; pooling both complete measurement
windows gives 457.18 output tokens/s and USD 25.32/M. This pooled figure is the
recommended capacity-planning estimate. The two costs differ by 4.23%, and both
runs passed the same zero-error and cache-tier evidence gates.

## Test environment

- Model: Qwen3.6-35B-A3B
- Runtime: vLLM 0.22.1 with vLLM-Ascend 0.22.1rc1
- Topology: tensor parallel 2, data parallel 4, expert parallel enabled
- Context limit: 65,536 tokens
- NPU server: eight Ascend NPUs, 64 GiB HBM per device
- Host memory: 2 TiB
- Load generator: separate AI Perf host on the same private network
- Cost assumption: USD 30,000 per 30-day month

## Implemented optimizations

- Automatic prefix caching for repeated agent history.
- TP2/DP4 with expert parallelism for the MoE model.
- Ascend fused operators, FlashComm, shared-expert overlap, CPU binding, and
  decode-only graph capture.
- Mooncake 0.3.11.post1 as the external KV backend.
- HBM as the hot tier and eight 176 GiB Mooncake DRAM segments (1.375 TiB
  aggregate) as the non-hot tier.
- `ASCEND_BUFFER_POOL=4:8` after Fabric Memory was rejected by the installed
  driver because cross-server communication is unsupported on this host.
- vLLM asynchronous scheduling disabled because it previously triggered a KV
  block reference-count assertion.
- The unrelated Llama service remained stopped throughout the measurements.

## 64K single-request break-even result

The proven synchronous 8,192 scheduler-token baseline produced:

| Path | TTFT |
|---|---:|
| Cold prefill | 11.453 s |
| Target fill | 10.112 s |
| HBM hit | 0.579 s |
| Mooncake DRAM hit | 0.584 s |

The DRAM request increased the external-prefix-hit counter by 63,488 tokens and
increased Mooncake Get activity while the local HBM-prefix counter did not
increase. DRAM TTFT was about 19.6 times faster than cold prefill and only about
5 ms slower than the measured HBM hit. This crosses the required 64K
single-request break-even gate.

The requested concurrency 1/4/8 path comparison also passed. Each row used
multiple one-output-token requests (8/16/32 respectively) to reduce sample
noise; all requests and all 224 eviction requests per row succeeded:

| Concurrency | Cold avg TTFT | HBM avg TTFT | DRAM avg TTFT | Cold / DRAM |
|---:|---:|---:|---:|---:|
| 1 | 5.782 s | 0.593 s | 0.575 s | 10.1x |
| 4 | 6.592 s | 0.804 s | 0.928 s | 7.1x |
| 8 | 11.026 s | 1.089 s | 1.382 s | 8.0x |

For C1/C4/C8, external-prefix-hit tokens exactly matched external-transfer
tokens (507,904 / 1,015,808 / 2,031,616), and Mooncake replica lookups were
16 / 32 / 64 respectively. Thus DRAM remained faster than cold prefill through
C8 and the result is not an accidental HBM hit.

## Scheduler-budget investigation

| KV load mode | Scheduler token budget | HBM utilization | Result |
|---|---:|---:|---|
| Synchronous | 8,192 | 0.918 | Stable; full cold/HBM/DRAM diagnostic passed |
| Asynchronous | 8,192 | 0.918 | External-hit request remained queued in a capacity loop |
| Asynchronous | 65,536 | 0.918 | OOM on 6.45 GiB MoE temporary allocation |
| Asynchronous | 65,536 | 0.880 | OOM on 6.46 GiB MoE temporary allocation |
| Asynchronous | 65,536 | 0.850 | OOM on 6.37 GiB MoE temporary allocation |
| Synchronous | 32,768 | 0.918 | OOM: 3.44 GiB requested with 1.01 GiB free |
| Synchronous | 16,384 | 0.918 | Passed: cold 14.019 s, HBM 0.547 s, DRAM 0.580 s |

The 16,384 run's DRAM request increased external-prefix hits by exactly 63,488
tokens and Mooncake batch replica-list requests by two; local-prefix hits were
unchanged. This confirms a real DRAM restore rather than an HBM hit.

Reducing `gpu_memory_utilization` is not automatically beneficial: it reserves
less HBM for hot KV blocks, while the 65,536-token execution shape still creates
a large temporary MoE allocation. The successful 8,192 and 16,384 diagnostics
therefore retain 0.918 rather than sacrificing the HBM tier. The mixed-workload
sweep selects 8,192 because it delivers lower measured cost than 16,384.

## Agent workload and concurrency methodology

The final workload contains 160 requests per run:

- 112 HBM-hit requests (70%)
- 32 Mooncake DRAM-hit requests (20%)
- 16 cold requests (10%)

Each request contains 65,280 input tokens, emits 256 output tokens, and shares
58,982 prompt tokens with the previous turn (90.35% text identity). Concurrency
is swept through 8, 16, 32, 64, and 128. Every run uses a unique run-level
session and eviction namespace to prevent cache state from a previous run from
converting cold traffic into cache hits.

An initial C8 run with 112 unique hot sessions was rejected even though all 160
requests succeeded: cache counters showed fewer local HBM hits and more
Mooncake lookups than the requested 70/20/10 mix. Its 124.34 output tokens/s
and USD 93.09/M output tokens are retained only as an invalid capacity-pressure
observation. The corrected workload uses 28 unique HBM-resident agent sessions
four times each, while retaining 32 unique DRAM sessions and 16 unique cold
sessions. This keeps the hot working set safely below effective HBM capacity.

## Cost calculation

Only successfully emitted output tokens are used:

```text
output_tokens_per_second = successful_completion_tokens / measurement_seconds
USD_per_million_output_tokens =
    30,000 / (output_tokens_per_second * 2,592,000) * 1,000,000
```

The reported value represents 100% server utilization and excludes failed or
warm-up requests. A production price should additionally include the expected
utilization factor, redundancy, operations, and margin.

This is deliberately an **output-token cost** because every measured request
generates the same 256 tokens. For reference, the first 8K-C128 run processed
10,485,760 prompt-plus-output tokens in 91.529 seconds, or about 114,562 total
tokens/s. Counting cached input tokens at face value would yield approximately
USD 0.101/M total processed tokens, but that number is not comparable to an
output-token selling price and should not be used without a defined cached-input
billing policy.

## Final benchmark results

### 16,384 scheduler-token budget

| Concurrency | Success | Output tok/s | p99 latency | USD/M output tokens | Cache validation |
|---:|---:|---:|---:|---:|---|
| 8 | 160/160 | 141.50 | 20.28 s | 81.80 | Valid: 64 Mooncake batch lookups = 32 DRAM requests |
| 16 | 160/160 | 229.00 | 24.25 s | 50.54 | Valid: 64 Mooncake batch lookups = 32 DRAM requests |
| 32 | 160/160 | 304.41 | 45.74 s | 38.02 | Valid: 64 Mooncake batch lookups = 32 DRAM requests |
| 64 | 160/160 | 323.06 | 96.88 s | 35.83 | Valid: 64 Mooncake batch lookups = 32 DRAM requests |
| 128 | 160/160 | 337.65 | 120.87 s | 34.28 | Valid: 64 Mooncake batch lookups = 32 DRAM requests |

At C8, external-prefix-hit and external-transfer deltas both equaled 1,572,864
tokens, local HBM-prefix hits increased by 6,905,856 tokens, and no request was
deferred. C16 preserved the exact same external-hit/transfer deltas, increased
local HBM-prefix hits by 7,131,136 tokens, and had no deferred waits. C32
lowers cost by 24.8%
relative to C16, at the expense of increasing p99 latency from 24.25 s to
45.74 s. C64 lowers cost only another 5.8% while p99 rises by 112% to 96.88 s;
capacity waiting peaks at 47 requests. This is the first clear latency/capacity
knee. C128 lowers cost only another 4.3% while p99 rises another 24.8% to
120.87 s. It is the absolute minimum-cost point for the 16,384 scheduler-token
configuration. The completed 8,192-budget comparison below supersedes it as
the global cost minimum.

### 8,192 scheduler-token budget

| Concurrency | Success | Output tok/s | p99 latency | USD/M output tokens | Cache validation |
|---:|---:|---:|---:|---:|---|
| 32 | 160/160 | 324.91 | 47.53 s | 35.62 | Valid: 64 Mooncake batch lookups = 32 DRAM requests |
| 64 | 160/160 | 370.29 | 81.03 s | 31.26 | Valid: external hit = transfer = 1,835,008 tokens; no deferred waits |
| 128 | 160/160 | 447.51 | 90.92 s | 25.86 | Valid: external hit = transfer = 1,835,008 tokens; no deferred waits |
| 128 repeat | 160/160 | 467.27 | 87.15 s | 24.77 | Valid: external hit = transfer = 1,835,008 tokens; no deferred waits |

Operational peaks for the same 8K runs were:

| Concurrency | KV usage | Approx. free blocks/engine* | Running | Capacity waiting | DRAM deferred waiting |
|---:|---:|---:|---:|---:|---:|
| 32 | 16.76% | 6,762 | 32 | 16 | 0 |
| 64 | 30.74% | 5,626 | 64 | 44 | 0 |
| 128 | 31.94% | 5,529 | 99 | 2 | 0 |
| 128 repeat | 31.87% | 5,534 | 94 | 5 | 0 |

\*Each DP engine reported 8,123 GPU KV blocks. Free blocks are derived from
`8,123 * (1 - peak KV usage)` because this runtime does not export a direct
free-block gauge. “Running” is the scheduler's peak active-request count; a
separate decode-batch-size metric was not exported. Likewise, zero deferred
waiting demonstrates no observed DRAM-load queue, but the runtime did not
export a direct per-request DRAM Get queue-time histogram.

At C32, the 8,192 budget is 6.7% faster and 6.3% cheaper than the 16,384
budget, with similar p99 latency. At C64 it is 14.6% faster and 12.8% cheaper,
while p99 improves from 96.88 s to 81.03 s. The larger prefill chunk therefore
does not improve this 90%-repeated, cache-dominated workload. At C128, the 8K
budget is 32.6% faster and 24.6% cheaper than the 16K result, while p99 is
29.95 s lower. Its peak observed running batch was 99 requests, so increasing
the nominal client concurrency above 128 would not increase useful parallelism
for this fixed 160-request workload. The independent repeat was 4.23% cheaper
than the first C128 sample. Pooling 81,920 emitted output tokens over 179.187
seconds yields 457.18 output tokens/s and USD 25.32/M output tokens.

## Recommendation

Use the synchronous 8,192-token scheduler budget at C128 for minimum steady-state
cost. The lowest individual sample is USD 24.77/M output tokens, while the
two-run pooled estimate is USD 25.32/M and the slower sample is USD 25.86/M.
Capacity plans should use the pooled or slower figure rather than selecting only
the fastest run. For a latency-balanced service, C32 remains the conservative
operating point (USD 35.62/M, p99 47.53 s); C64 is the intermediate choice (USD
31.26/M, p99 81.03 s).

The cost-minimum launch profile is:

| Setting | Value |
|---|---|
| Model context | 65,536 |
| Scheduler token budget | 8,192 |
| Maximum sequences | 128 |
| NPU memory utilization | 0.918 |
| Parallel topology | TP2 / DP4 / EP enabled |
| Prefix cache | Enabled |
| KV connector | AscendStoreConnector with Mooncake backend |
| External load mode | Synchronous (`load_async=false`) |
| DRAM tier | 8 x 176 GiB (1.375 TiB) |
| Ascend buffer pool | `ASCEND_BUFFER_POOL=4:8` |
| Graph capture | `FULL_DECODE_ONLY` |

## Scope boundaries and evidence limitations

- Direct H2D bandwidth was not captured by a hardware counter. The DRAM path is
  proven by exact external-hit/transfer token deltas, Mooncake replica lookups,
  unchanged local-hit counters in the single-request diagnostic, and measured
  TTFT; no unsupported bandwidth number is inferred.
- The asynchronous Mooncake path is excluded because it either entered a
  scheduler capacity loop or caused 64K-prefill OOM at the tested HBM fractions.
  All accepted cost rows use synchronous loading.
- Fabric Memory is not part of the accepted configuration because the installed
  driver reported that the required communication mode is unsupported. The
  fallback is ordinary Mooncake DRAM with `ASCEND_BUFFER_POOL=4:8`.
- PD separation, MA separation, and MTP were not independently deployed and
  validated in this benchmark, so no savings are attributed to them. The proven
  topology is TP2/DP4 with expert parallelism, APC, fused Ascend operators, HBM
  hot caching, and Mooncake DRAM for evicted reusable KV blocks.
- Setup traffic used to populate and evict cache entries is excluded from the
  steady-state measurement window. The result models a warmed agent service;
  cold startup and cache-maintenance overhead must be capacity-planned
  separately.
