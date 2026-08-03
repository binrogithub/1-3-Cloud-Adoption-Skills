# Measured results

All rows: Qwen3.6-35B-A3B BF16, 64K input / 256 output, 90.35% shared prefix,
70/20/10 hot/warm/cold mix, USD 30,000 per 30-day month, 100% utilization.
Source files live on the load-generation host under
`/root/qwen8-throughput/w8a8-affinity-results/`.

## Headline progression

| Config | dies | topology | conc | reqs | output tok/s | USD/M out | p99 TTFT | KV peak | errors |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| Old baseline | 8 | TP2×DP4×EP8 | 128 | 160 | 467.3 | 24.77 | 87.2 s | 31.9% | 0 |
| 16-die, internal LB | 16 | TP2×DP8×EP16 | 256 | 320 | 739.8 | 15.65 | 102.5 s | 53.1% | 0 |
| **16-die + affinity** | **16** | **TP2×DP8×EP16** | **384** | **640** | **829.1** | **13.96** | **176.4 s** | **49.7%** | **0** |

Final run: `v6-c384-all.json`, run-id 90, `--pool-mult 4 --hot-unique 56`.
Mooncake eviction gate PASS (0 bytes evicted during the measured window).
Peak `running` = 384, matching nominal concurrency (instrument self-proof).

## Cache tier behaviour

| Run | local prefix-cache hit ratio | external (DRAM) hit ratio |
|---|---:|---:|
| DP4, C128 | 45.6 – 57.0% | 1.84 M tokens (exactly the designed 20% tier) |
| DP8, C256, no affinity | 11.9 – 16.0% | 3.7 – 8.7× the designed volume |
| **DP8, C384, affinity** | **65.8%** | 29.8% |

The DP8-without-affinity row lands at ~1/8 — the signature of round-robin session
scatter across 8 engines.

## Cost by billing convention (C384)

| Convention | USD / M input+output |
|---|---:|
| Face value (all prompt tokens billed) | **0.0545** |
| Cache-discounted (cached input at 10%) | ~0.25 |
| Strict (cached input unbilled) | ~0.48 |

Only the face-value figure derives purely from client-side token counts. The other
two depend on `prefix_cache_hits_total`, which counts per scheduler lookup rather
than per request — at C384 total lookups were ~1.88× the prompt tokens. Hit ratios
remain valid for cross-run comparison; absolute request-level conversions do not.

## Single-request path latency (64K, DP0 diagnostic)

| Path | TTFT |
|---|---:|
| Cold prefill | 11.453 s |
| HBM hit | 0.579 s |
| Mooncake DRAM hit | 0.584 s |

DRAM restore is 19.6× faster than cold prefill and within ~5 ms of an HBM hit at
this prefix length — the basis for keeping the DRAM tier for 64K prefixes and
dropping it for ~4K ones.

## Prefill capability reference

Cold-only phases (`warm_fill`, `hot_fill`, `eviction_pass`) sustain
**57,000 – 68,500 input tok/s**. During the measured window only ~19,000 tok/s of
genuine prefill compute is needed, so at the operating point the system is not
prefill-bound; the Mooncake DRAM restore path carries the larger share.

## Scheduler budget comparison (8-die era, C128)

| `max-num-batched-tokens` | output tok/s | USD/M out |
|---:|---:|---:|
| 8,192 | 467.3 | 24.77 |
| 16,384 | 337.7 | 34.28 |
| 32,768 | — | OOM on first 64K cold request |
