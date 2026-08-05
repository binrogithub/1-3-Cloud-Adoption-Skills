# SGLang + Qwen3.6-35B-A3B on Ascend NPU — Best-Practice Deployment

Field-tested playbook for serving Qwen3.6-35B-A3B (MoE) with SGLang on a 16-die
Huawei Ascend 910 (A3) host.

**Measured outcome: 12 of 12 data points beat the previous best configuration**,
by +4% to +153% output tok/s per user, across 3 workload scenarios × 4 concurrency
levels. No new hardware, no model change.

## The finding

No single parallelism topology wins at every concurrency level, so the best practice
is a **hybrid** one:

| Concurrency | Topology | Why |
|---|---|---|
| C1 (single user) | TP16 single engine, 16 die | One request monopolizes all 16 die → fastest prefill, lowest TTFT |
| C4+ (multi user) | TP2/DP8, 8 instances × 2 die, sticky routing | Load spreads across 8 engines, each keeps a batch deep enough for NEXTN to pay off |

Both modes run BF16 with NEXTN speculative decoding (accept length ~3.33 → decode
~3.3×), which is the dominant accelerator here — more so than w8a8 quantization,
which is in fact *incompatible* with NEXTN on SGLang v0.5.14 (MoE `scheme=None` crash).

## Verified results (output tok/s per user)

| Scenario | C1 | C4 | C8 | C16 |
|---|---|---|---|---|
| Chat (128 / 256) | 160.33 | 137.61 | 122.49 | 94.10 |
| Coding Agent (16384 / 4096) | 151.55 | 132.90 | 118.90 | 94.22 |
| Summarization (1024 / 128) | 148.46 | 132.39 | 117.45 | 94.54 |

Full per-point comparison against the prior best is in `references/verified-results.md`.

## Files

- **`SKILL.md`** — the reproduction guide; start here. Prerequisites, both launch
  modes, the must-follow rules and prohibitions, and a troubleshooting table.
- **`scripts/`** — the four scripts that produce the numbers above: two launchers
  for the inference host (TP16, TP2/DP8) and two aiperf drivers for the test host,
  plus `gen-final-xlsx.py` to aggregate results.
- **`config/env-and-params.md`** — full environment-variable and launch-flag tables
  for both modes.
- **`data/sglang-tp2dp8-final-result.xlsx`** — measured results workbook.
- **`references/verified-results.md`** — measured numbers and the delta against the
  historical best.
- **`references/gap-analysis-prd.md`** — root-cause investigation of the earlier
  performance gap (in Chinese).

## The most transferable lesson

Two of the three biggest apparent hardware limits were configuration errors in the
**load generator**, not the engine:

1. **Sticky routing starves C1.** Session-affinity routing pinned the single C1
   request to 1 of 8 engines, leaving 14 die idle — Chat C1 read 110.69 tok/s. The
   same hardware in TP16 single-engine mode reads 160.33. Affinity is a
   multi-user optimization; it is a pessimization at concurrency 1.

2. **`num-conversations` must be ≥ `concurrency × ndp`.** Sticky routes by
   `session_id % 8`, so with too few distinct sessions some engines never receive
   work and cold-start plus queuing dominates. Chat C16 read 43.81 tok/s at
   `num-conversations=30` and 94.10 at 160 — a +115% swing from one client-side flag.

Before attributing a plateau to the NPU, check that every engine is actually
receiving requests.

## Scope

Validated on Qwen3.6-35B-A3B (BF16, MoE — 256 experts, top-8, hybrid attention)
with SGLang `v0.5.14-cann9.0.0-a3-arm64` on 8 × Ascend 910 (A3), 16 die, using
aiperf as the load generator. Host addresses in all files are placeholders;
scripts read the inference host from `INFER_HOST`, so export it before running
them. The container image path points at a private SWR repository — substitute
your own registry.
