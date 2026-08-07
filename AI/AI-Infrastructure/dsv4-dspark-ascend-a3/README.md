# DeepSeek-V4-Flash + DSpark on Ascend A3 — Deployment & Benchmark

Field-tested playbook for serving DeepSeek-V4-Flash-0731 W8A8 with **DSpark**
speculative decoding on a 16-die Huawei Ascend 910 (A3) host, using
vLLM-Ascend 0.25.1.

**Measured outcome: 1.96–2.91× output tok/s per user over the same model with no
speculative decoding**, at concurrency 1. No hardware change, no model change —
one `--speculative-config` flag plus the image that supports it.

## The finding

DSpark is DeepSeek-V4-Flash-0731's native speculative decoding (Markov + confidence
head on layers 40–42). It pays off at **low concurrency and long context**, and
stops paying off as batch size grows:

| Scenario | C1 | C4 | C8 | C16 |
|---|---|---|---|---|
| Chat (128 / 256) | **1.96×** | 1.70× | 1.42× | 1.02× |
| Summarization (1024 / 128) | **2.06×** | 1.36× | 0.91× | 0.62× |
| Coding Agent (16384 / 4096) | **2.91×** | 2.15× | 2.13× | 1.81× |

Speedup vs the no-spec-decode baseline on identical hardware. Summarization at C16
is a **0.62× regression** — larger batches lower the acceptance rate until drafter
overhead exceeds the gain. Enable DSpark for latency-sensitive traffic (C1–C4);
leave it off for high-concurrency throughput.

Inter-token latency drops 41–62% at low concurrency (Coding C1: 32.6 → 12.5 ms/token),
and NPU AICore utilization *falls* from 82% to 65% — the expected signature of
effective speculative decoding, since more tokens come out per NPU step.

## Optimizations tested and rejected

Each was tested single-factor against the adopted config. All five lost:

| Optimization | Result | Why |
|---|---|---|
| block-size 32 + prefix caching | worse | fixed-ISL benchmark has no prefix reuse; block-management overhead exceeds cache gain |
| CPU KV offload (RecomputeCPUOffloadConnector) | worse | never triggers on single-request fixed ISL; connector cost is fixed |
| Remove `enforce_eager` (drafter FULL ACLGraph) | worse | drafter graph is unstable/slower on DSV4 |
| `max-num-seqs 64` | −23% | larger batch lowers DSpark acceptance |
| `enable_dsa_cp` | worse, 19/50 errors | conflicts with DSpark |

## Files

- **`SKILL.md`** — the reproduction guide; start here. Prerequisites, the three
  phases (deploy / benchmark / aggregate), and a verified pitfalls table.
- **`scripts/`** — `dspark-serve.sh` (the vllm serve command, mounted into the
  container), `launch-dsv4-dspark-v2.sh` (docker run + health-check loop),
  `run-dsv4-dspark-tp4dp4-all.sh` (aiperf, 3 scenarios × 4 concurrency),
  `sample-util.sh` (NPU/CPU/memory sampler), `aggregate-dspark.py` (xlsx generator).
- **`data/dsv4-dspark-vs-baseline-result-20260807.xlsx`** — measured results workbook
  (throughput, ITL, TTFT, utilization, config).
- **`reports/dsv4-dspark-report-en.md`** — full English test report.
- **`references/optimization-summary.md`** — every optimization researched, adopted
  and rejected.
- **`references/deployment-pitfalls.md`** — verified failure modes and their fixes.

## The most transferable lesson

**The image version is the whole ballgame.** DSpark needs vLLM-Ascend **v0.25.1+**
(`quay.io/ascend/vllm-ascend:DeepSeekV4-flash-0731-a3`). On the older `v0.22.1rc1-a3`
image, `method:dspark` is rejected outright and the only speculative method offered
is `mtp` — which then fails on 0731 weights because there is no `mtp.0.head.weight`.
It is easy to read that chain of errors as "spec decode doesn't work on this model."

Second: **do not inline the `--speculative-config` JSON in `bash -c`.** Heredoc and
shell quoting mangle it into `Value method:dspark cannot be converted` or
`Invalid JSON: key must be a string`. Write the serve command to a file and mount
it into the container — that is why `dspark-serve.sh` exists as a separate script.

## Scope

Validated on DeepSeek-V4-Flash-0731-w8a8 (284B total / 13B activated, modelslim W8A8)
with vLLM-Ascend 0.25.1 on 8 × Ascend 910 (A3), 16 die, TP4 + DP4 with expert
parallelism, using aiperf 0.11.0 as the load generator. Comparison figures against
Qwen3.6 BF16+NEXTN come from the sibling
[sglang-qwen36-ascend-best-practice](../sglang-qwen36-ascend-best-practice/) run on
the same hardware. Host addresses in all files are placeholders; scripts read the
inference host from `INFER_HOST`, so export it before running them.
