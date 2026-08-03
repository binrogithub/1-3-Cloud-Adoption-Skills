# Qwen3.6-35B-A3B Ascend 8-NPU throughput result

Test date: 2026-08-02 (Asia/Shanghai)

## Deployment

- Model: `/mnt/sfs_turbo/models/Qwen3.6-35B-A3B` (BF16, MoE 256 experts, top-8)
- Runtime: `quay.io/ascend/vllm-ascend:v0.22.1rc1-a3`, vLLM 0.22.1
- NPU topology: devices 0-7, TP=2, DP=4, EP=8
- Optimization: paged KV cache, automatic prefix caching, expert parallel, MTP=3,
  full decode graph, FlashComm1, shared-expert multistream overlap, CPU binding
- Limit: `max-num-seqs=128` per DP rank, `max-num-batched-tokens=8192`,
  `max-model-len=65536`
- Endpoint: `http://vllm-host:8002`, served name `Qwen3.6-35B-A3B`

The startup files are `container.sh` and `start-mtp.sh` in this directory. Copies
are installed on the NPU host under `/mnt/sfs_turbo/script/qwen3.6-8card/`.

## Single-user gate

Workload: fixed ISL=128, OSL=32, streaming, 20 measured requests after warmup.

| Metric | Result |
|---|---:|
| Average TTFT | 248.00 ms |
| p99 TTFT | 291.05 ms |
| Average ITL | 10.22 ms |
| Per-user generation | 98.91 output token/s |
| Errors | 0 |

Acceptance gate was TTFT <= 300 ms and ITL <= 15.40 ms (the measured non-MTP
TP4 baseline). The deployment passes both.

## Concurrency search

Workload: fixed ISL=1024, OSL=256, streaming, `ignore_eos=true`.

| MTP | Concurrency | In-flight total tokens | Output token/s | Avg TTFT | Avg ITL | Errors |
|---:|---:|---:|---:|---:|---:|---:|
| off | 128 | 163,840 | 1,719.49 | 5,924.6 ms | 51.22 ms | 0 |
| off | 256 | 327,680 | 2,203.00 | 7,119.0 ms | 88.20 ms | 0 |
| off | 384 | 491,520 | 2,300.96 | 7,439.6 ms | 137.70 ms | 0 |
| off | 512 | 655,360 | 2,688.77 | 7,540.8 ms | 150.74 ms | 0 |
| 3 | 128 | 163,840 | 2,213.47 | 2,735.4 ms | 44.28 ms | 0 |
| 3 | 256 | 327,680 | 3,590.06 | 2,224.2 ms | 59.86 ms | 0 |
| 3 | 384 | 491,520 | 3,731.96 | 3,554.6 ms | 86.24 ms | 0 |
| 3 | 512 | 655,360 | 2,473.03 | 8,541.4 ms | 156.49 ms | 0 |

MTP's throughput knee is concurrency 384. Concurrency 512 overloads the useful
decode batch and drops throughput, so “more in-flight tokens” is not “lower cost.”

## Stability verification at the selected point

- Requests: 1,536/1,536 successful, 0 errors
- Duration: 98.31 s
- Fixed workload: ISL=1024, OSL=256, concurrency=384
- In-flight capacity represented by workload: 491,520 total tokens, of which
  98,304 are output-token budget
- Output throughput: **3,999.67 token/s**
- Input + output throughput: about **19,998.35 token/s**
- Request throughput: 15.62 request/s
- Average / p99 TTFT: 2,254.39 / 8,214.43 ms
- Average / p99 request latency: 24,084.13 / 33,627.90 ms
- Average ITL: 85.61 ms
- MTP accepted/draft tokens: 253,806 / 418,680 = **60.62%**

Artifact on AI Perf host:
`/home/qwen3.6-test/dp4-mtp-throughput-stable/c384-r1536/artifacts/`.

## Cost floor

Assumptions: USD 30,000 per 30-day month, 24x7, measured throughput remains
constant, and the amount excludes electricity, network/storage, operations,
redundancy, failures and idle capacity.

| Effective utilization | USD / 1M output tokens | USD / 1M input+output tokens |
|---:|---:|---:|
| 100% | **2.89** | **0.579** |
| 90% | 3.22 | 0.643 |
| 80% | 3.62 | 0.723 |
| 70% | 4.13 | 0.827 |

At 100% utilization the output-token unit cost is about
`$0.000002894/token`, with 10.367 billion output tokens per 30-day month.

## OmniInfer / PD boundary

The requested OmniInfer repository was cloned at commit `88e2bbc5`. This revision
states CloudMatrix384-only hardware support; its documented Qwen engine is Qwen2,
and its OmniAttention path explicitly does not support prefix caching. It is not
used to serve this Qwen3.6 A3-host result because that would be an unsupported
combination.

PD separation is primarily a latency-isolation mechanism. Upstream vLLM explicitly
notes that disaggregated prefill does not improve throughput. On one fixed 8-NPU
server it also duplicates model weights and partitions capacity, so it is not the
cost-minimizing topology for this throughput objective. A valid PD comparison
requires a supported connector/runtime plus a latency SLO workload, and should be
reported separately from this throughput floor.

## 90% prefix-cache-hit experiment

Test date: 2026-08-02. The workload uses one pre-warmed 4,096-token system
prefix plus about 455 unique input tokens and 256 output tokens. The exact
server-side cache counters measured 10,485,760 cache-hit tokens out of
11,702,362 queried prompt tokens: **89.604%**.

The cache-hit deployment differs from the random-prefix deployment in two ways:

- NPU KV allocation was increased from `gpu-memory-utilization=0.900` to
  `0.918`, increasing each DP engine's cache from 2,402,521 to 2,472,241 tokens.
- MTP was disabled and async scheduling enabled. On this runtime, MTP and APC
  together produced zero cache hits even for byte-identical sequential requests;
  disabling MTP made repeated-request latency fall from 3.257 seconds (cold) to
  about 0.26-0.31 seconds (hot), with cache-hit counters increasing normally.

CPU KV offload was attempted with `OffloadingConnector` and
`NPUOffloadingSpec`. It cannot start on the installed 0.22.1 image because the
Ascend plugin imports the absent core module `vllm.v1.kv_offload.abstract`.
Therefore the measured result uses NPU APC only. Disk offload remains disabled
because this host has no dedicated unmounted SSD (only a rotational root disk
and NFS storage).

### Concurrency search

| Concurrency | Output token/s | Avg TTFT | Avg ITL | Cache hit | Errors |
|---:|---:|---:|---:|---:|---:|
| 128 | 2,434.07 | 3,044.0 ms | 39.80 ms | 89.604% | 0 |
| 256 | 3,185.65 | 6,049.3 ms | 56.65 ms | 89.604% | 0 |
| 384 | 3,888.35 | 4,774.7 ms | 79.76 ms | 89.604% | 0 |
| 512 | 4,223.15 | 6,381.9 ms | 86.03 ms | 89.604% | 0 |
| 640 | 4,751.36 | 8,558.5 ms | 87.98 ms | 89.604% | 0 |

The final stability run used concurrency 640 and 2,560 requests (four waves):

- 2,560/2,560 requests successful, zero errors
- Duration: 119.78 seconds
- Stable output throughput: **5,470.54 token/s**
- Request throughput: 21.37 requests/s
- Average/p99 TTFT: 6,640.27/24,687.14 ms
- Average ITL: 81.68 ms
- Average request latency: 27,465.85 ms
- Cache-hit rate: **89.604%**

Artifact on the AI Perf host:
`/home/qwen3.6-test/cache90/stable-c640-r2560-v2/artifacts/`.

### Cost with 90% cache hits

The same USD 30,000 per 30-day month assumptions apply.

| Effective utilization | USD / 1M output tokens | USD / 1M billed input+output tokens |
|---:|---:|---:|
| 100% | **2.12** | **0.113** |
| 90% | 2.35 | 0.125 |
| 80% | 2.64 | 0.141 |
| 70% | 3.02 | 0.161 |

At 100% utilization this is about 14.180 billion output tokens per month. Output
throughput improves 36.77% over the random-prefix MTP stability result, lowering
output-token cost by 26.89% (from USD 2.89 to USD 2.12 per million). The billed
input+output figure counts cached prompt tokens as billable tokens; it is highly
workload-dependent and is not an apples-to-apples comparison with the earlier
1,024-input-token random workload.

## Mooncake DRAM offload experiment

Test date: 2026-08-02. `AscendStoreConnector` with the Mooncake backend was
validated first with 1 GiB per worker (8 GiB total). A 14,031-token prefix was
computed on DP0 in 2.649 seconds and then loaded by DP1 in 0.773 seconds.
Mooncake reported 2/2 successful Get batches (18/18 objects), proving that the
second request used the external DRAM pool rather than DP1's local HBM cache.

The pool was then increased to 176 GiB per worker, or 1,408 GiB total. All eight
segments registered successfully and the master reported 1.38 TiB capacity,
with about 439 GiB host memory still available after model startup.

The production-sized 90%-hit stability run at concurrency 640 was not stable.
All four DP engine cores eventually failed in vLLM's hybrid KV block allocator
at `block_pool.py:get_new_blocks`, on `assert block.ref_cnt == 0`. The benchmark
recorded 418 request errors before the server exited. There was no host OOM and
the failure occurred after only a tiny fraction of the DRAM pool was used, so
reducing the pool size does not address the root cause.

Because the Mooncake configuration failed the zero-error stability gate, no
lower token-price claim is made from this run. The server was restored to the
previous HBM APC configuration; its valid 90%-hit cost remains USD 2.12 per
million output tokens at the stated 100% utilization assumption.

## Mooncake synchronous-scheduler follow-up and Llama shutdown

The Llama P/D container on NPU 8-15 was stopped, including ports 8100, 8200,
and 8989. Qwen remained on NPU 0-7 so that this did not mix a topology change
with the resource-contention comparison.

Removing `--async-scheduling` fixed the Mooncake/AscendStore hybrid-block
lifecycle crash. With a 128 GiB pool, every tested tier completed without an
engine assertion or request error:

| Concurrency | Requests | Output token/s | Errors |
|---:|---:|---:|---:|
| 128 | 512 | about 2,541 | 0 |
| 256 | 1,024 | 3,808.77 | 0 |
| 384 | 1,536 | 4,019.15 | 0 |
| 512 | 2,048 | 3,953.74 | 0 |
| 640 | 2,560 | 4,355.43 | 0 |

The pool was then increased to 176 GiB per worker (1,408 GiB total). The
concurrency-640 stability run completed 2,560/2,560 requests with zero errors
at 4,294.56 output token/s. Average TTFT was 9,561.81 ms and average ITL was
101.27 ms. Mooncake stored only 141.41 MiB and served no DRAM Get requests in
this workload because its approximately 200 shared prefixes already fit in
HBM. At USD 30,000/month, 4,294.56 token/s would cost about USD 2.70 per million
output tokens, so this configuration was stable but not cost-optimal for the
tested working set.

The final production selection is therefore HBM APC with Mooncake Pool stopped
and the Llama container stopped. Repeating the identical concurrency-640,
2,560-request workload produced:

- 2,560/2,560 requests successful, zero errors
- 6,043.78 output token/s
- Average/p99 TTFT: 6,299.21/21,086.53 ms
- Average ITL: 69.47 ms
- Benchmark duration: 108.39 seconds

This is 10.48% more output throughput than the earlier 5,470.54 token/s result.
Under the same USD 30,000 per 30-day month assumption, the revised output-token
cost is USD 1.92 per million at 100% utilization (USD 2.13 at 90%, USD 2.39 at
80%, and USD 2.74 at 70%). The implied 100%-utilization monthly capacity is
15.665 billion output tokens.

Artifacts:
`/home/qwen3.6-test/cache90/mooncake-sync-1408g-c640-r2560/` and
`/home/qwen3.6-test/cache90/hbm-no-llama-c640-r2560/` on the AI Perf host.

## Verified HBM-hot / DRAM-warm tiered-cache comparison

A deterministic 2,560-request workload was used to distinguish true HBM hits
from DRAM hits. Each request had 4,098 prompt tokens and 256 output tokens. The
mix was 1,792 HBM-hot requests (70%), 512 DRAM-warm requests (20%), and 256
cold requests (10%). Before measurement, 512 warm and 64 hot prefixes were
inserted, followed by 3,000 unique churn prefixes; the hot prefixes were
periodically touched to keep them in HBM.

The Mooncake counters prove that this was a real multilevel-cache run rather
than a DRAM-for-HBM substitution. During measurement:

- vLLM local prefix-cache hits increased by 7,340,032 tokens, exactly
  1,792 x 4,096 (the 70% HBM-hot portion).
- vLLM external prefix-cache hits increased by 2,097,152 tokens, exactly
  512 x 4,096 (the 20% DRAM-warm portion).
- Mooncake Get increased by 1,024 batches / 5,120 objects, with no failed Get.
- The remaining 256 requests (10%) were cold and required normal prefill.
- Mooncake DRAM held 603.23 GB after the run, with a configured capacity of
  1.38 TB. All 2,560 requests completed without errors.

| Configuration | Output token/s | Duration | Avg latency | p99 latency | USD / 1M output tokens |
|---|---:|---:|---:|---:|---:|
| HBM hot + Mooncake DRAM warm, synchronous scheduler | 2,040.51 | 321.17 s | 71.85 s | 120.04 s | 5.67 |
| HBM-only APC control, identical request sequence | 2,457.87 | 266.64 s | 59.48 s | 85.42 s | 4.71 |

The cost calculation assumes USD 30,000 per 30-day month and 100% measured
utilization. At lower utilization, the tiered-cache cost is USD 6.30 at 90%,
USD 7.09 at 80%, and USD 8.10 at 70% per million output tokens. The identical
HBM-only control costs USD 5.23, USD 5.89, and USD 6.73 respectively.

Although Mooncake avoided recomputing all 512 warm prefixes, its synchronous
connector overhead reduced output throughput by 16.98% versus HBM-only and
increased cost per output token by 20.45%. Therefore this Mooncake build is not
the cost-optimal production choice for the tested 70/20/10 distribution. The
server was left on the stable HBM APC configuration, with Mooncake stopped and
the Llama container still stopped.

Artifacts on the AI Perf host:
`/home/qwen3.6-test/tiered-mooncake/` and
`/home/qwen3.6-test/tiered-hbm-control/`. The workload generator is
`/home/qwen3.6-test/tiered_kv_bench.py`.
