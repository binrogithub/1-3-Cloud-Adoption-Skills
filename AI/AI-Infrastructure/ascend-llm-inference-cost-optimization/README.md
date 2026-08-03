# Ascend LLM Inference Cost Optimization

Field-tested playbook for cutting LLM inference token cost on Huawei Ascend 910 NPUs
with vLLM-Ascend and a Mooncake DRAM KV tier.

**Measured outcome: USD 24.77 → 13.96 per million output tokens** (−43.6%),
829 output tok/s at 640/640 requests with zero errors, on a 64K-context agent
workload with ~90% repeated prompt text. No new hardware, no model change, no
runtime upgrade.

## What this skill covers

| Area | Content |
|---|---|
| Deployment | 16-die TP2×DP8×EP16 topology, launch scripts for internal-LB and multi-port modes |
| Cache tiering | HBM prefix cache + Mooncake CPU-DRAM warm tier, with the prefix-length rule for when the DRAM tier pays |
| Session affinity | Multi-port external LB so a session's turns keep hitting the engine that holds its KV |
| Concurrency | How to find the knee, and the per-engine KV budget formula that bounds it |
| Cost accounting | Three billing conventions, and why the "strict" one is a perverse optimization target |
| Benchmarking | A 70/20/10 hot/warm/cold agent workload generator with cache-evidence gates |

## Files

- **`SKILL.md`** — operating checklist; start here.
- **`REPORT.md`** — full technical write-up: topology, workload, results, rejected
  approaches, and the three measurement defects that invalidated earlier conclusions.
- **`deploy/`** — vLLM launch scripts (`start-bf16-16die-dpm.sh` is the recommended
  configuration), Mooncake master and pool config, container helpers.
- **`scripts/`** — benchmark driver and cost-reporting tools.
- **`results/measured-results.md`** — all measured data.
- **`references/`** — investigation records behind each conclusion.

## The most transferable lesson

Most of the apparent optimization plateau in this work was **measurement error, not
a hardware limit**:

1. The load generator silently capped itself at 100 HTTP connections, so every run
   labelled above C100 actually ran at ~C100.
2. Data parallelism without session affinity drove the local cache hit rate to
   `1/N_engines`.
3. An unrelated restart shrank the KV pool, which then evicted the benchmark's own
   warm tier mid-measurement.

`SKILL.md` lists the fingerprint of each defect and the gate that catches it. Apply
those gates before trusting any throughput or cost number.

## Scope

Validated on Qwen3.6-35B-A3B (BF16, MoE) with vLLM 0.22.1 / vLLM-Ascend 0.22.1rc1 /
Mooncake 0.3.11.post1, CANN 8.5.2, on 16× Ascend 910 dies. Host addresses in all
files are placeholders; substitute your own. Cost figures assume a fixed monthly
server rental at 100% utilization — restate them against your own rate and duty
cycle before use.
