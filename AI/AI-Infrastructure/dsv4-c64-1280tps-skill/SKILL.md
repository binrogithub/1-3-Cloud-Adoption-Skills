---
name: dsv4-c64-1280tps-ascend-a3
description: Deploy and benchmark DeepSeek-V4-Flash-0731 W8A8 on Ascend A3 to achieve C64 aggregate output TPS >1280 (per-concurrency >20 tok/s). Use when the user asks to optimize DSV4 C64 throughput, enable Fused MC2, tune DSpark for high concurrency, or reproduce the 1523 tok/s result.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
  - Edit
---

# DSV4-Flash C64 >1280 TPS on Ascend A3 — Optimization Skill

Optimizes DeepSeek-V4-Flash-0731 W8A8 on 16-die Ascend A3 NPUs (vLLM 0.25.1)
to achieve **C64 aggregate output TPS >1280 tok/s** (per-concurrency >20 tok/s)
under fixed load: C64, ISL=128, OSL=256, streaming, ignore_eos=true.

**Final result: 1523 tok/s (23.8 tok/s/concurrency), CV=1.7%, 3 formal rounds all >1280.**

---

## What this skill produces

- A running vLLM 0.25.1 service with the optimized configuration (Fused MC2 + DSpark3 + MLAPO + DSA-CP)
- aiperf benchmark results proving C64 >1280 tok/s
- An xlsx results workbook with optimization path, profile data, and final config
- An English optimization report

---

## Prerequisites

| Item | Requirement |
|---|---|
| Inference host | 8 × Ascend 910 A3 NPU = 16 die, 64GB HBM/die |
| Test host | aiperf 0.11.0 installed, network access to inference host |
| Model | `DeepSeek-V4-Flash-0731-w8a8` (294GB, modelslim W8A8) |
| Image | `quay.io/ascend/vllm-ascend:DeepSeekV4-flash-0731-a3` (vLLM 0.25.1) |
| SSH | key-based access to both hosts from the operator machine |

---

## Optimization Method

### Profile-Driven Approach

The optimization follows a profile-driven methodology rather than random parameter
tuning:

1. **Freeze control group** — establish a stable baseline
2. **Operator-level profile** — identify the actual bottleneck
3. **Apply targeted optimization** — fix the dominant cost component
4. **Factorial combination** — test interactions, never add percentages

### Key Finding: MoE Communication is the Bottleneck

Operator-level profiling (10s steady-state decode, C64) revealed:

| Category | Time Share | Notes |
|---|---:|---|
| **MoeDistributeDispatchV2** | **59.0%** | Absolute dominant — MoE dispatch comm |
| MoeDistributeCombineV2 | 4.6% | MoE combine comm |
| DynamicQuant (W8A8) | 3.2% | Dequantization |
| GroupedMatmulSwigluQuant | 2.0% | GMM (MoE FFN) |
| **Total MoE communication** | **~66%** | Far exceeds 15% threshold |
| GMM/MatMul (all) | 6.1% | NOT the bottleneck |

Communication breakdown:
- hcom_allGather: 42.7%
- hcom_reduceScatter: 33.8%
- hcom_alltoallv: 21.7%

### Optimization Path (796 → 1523 tok/s, +91%)

| Step | Configuration | TPS | vs Baseline | Key Finding |
|---|---|---:|---:|---|
| Phase 0 | Control group (DSpark7, DSA-CP off) | 796 | — | Baseline |
| Phase 2 | +Fused MC2 (MoE comm fusion) | 979 | +23% | Main effect: fuses dispatch+FFN+combine |
| Phase 2 | DSpark7 → DSpark3 | 1221 | +53% | Less spec overhead at high concurrency |
| Phase 2 | +MLAPO | 1235 | +55% | MLA Pool optimization |
| **Phase 2** | **+DSA-CP on** | **1523** | **+91%** | **Strong synergy with Fused MC2+DSpark3** |

### Why Each Optimization Works

1. **Fused MC2** (`enable_fused_mc2=1`): Replaces the separate
   dispatch→FFN→combine sequence with a fused `dispatch_ffn_combine/mega_moe`
   operator, eliminating intermediate synchronization and reducing communication
   rounds. This is the single largest gain (+23%).

2. **DSpark3** (`num_speculative_tokens=3`): At C64 high concurrency, fewer
   speculative tokens reduce verification overhead and improve effective
   throughput. DSpark7 adds more draft tokens but the rejection rate increases
   under load, wasting compute. Note: `num_spec+1` must be divisible by
   `tensor_parallel_size` (4), so valid values are 3, 7, 11, 15...

3. **MLAPO** (`enable_mlapo=1`): Multi-head Latent Attention Pool optimization,
   reduces attention computation overhead.

4. **DSA-CP** (`enable_dsa_cp=true`): DSA Compressor Pipeline. Previously caused
   regression when used alone with DSpark7, but produces strong synergy (+36%)
   when combined with Fused MC2 + DSpark3. This is a classic interaction effect
   that single-factor A/B testing would miss.

---

## Phase 1 — Deploy the Optimized Service

### 1.1 Write the serve script

Create `/root/dspark-serve-final.sh` on the inference host. See
`scripts/dspark-serve-final.sh` for the exact content. Key parameters:

```bash
vllm serve /data/models/DeepSeek-V4-Flash-0731-w8a8 \
  --tensor-parallel-size 4 --data-parallel-size 4 \
  --enable-expert-parallel \
  --quantization ascend \
  --max-num-seqs 32 \
  --block-size 128 \
  --async-scheduling \
  --speculative-config '{"method":"dspark","num_speculative_tokens":3,"enforce_eager":true}' \
  --compilation-config '{"cudagraph_mode":"FULL_DECODE_ONLY"}' \
  --additional-config '{"enable_fused_mc2":1,"enable_mlapo":1,"enable_dsa_cp":true,"multistream_overlap_shared_expert":false}'
```

### 1.2 Launch and verify

Use `scripts/launch-dsv4-param.sh` with environment variables:

```bash
export NUM_SPEC=3 FUSED_MC2=1 MULTISTREAM=0 DSA_CP=1 ENABLE_MLAPO=1 MAX_SEQS=32
nohup /root/launch-dsv4-param.sh > /tmp/launch.log 2>&1 &
# wait ~7-8 min for model load + CUDA graph capture
curl http://<inference-ip>:6697/health   # expect 200
```

Verify optimizations are active in logs:

```bash
docker logs <container> 2>&1 | grep "enable_fused_mc2"
# expect: AscendConfig.enable_fused_mc2 is set from additional_config with value 1.
```

### 1.3 Deployment pitfalls (verified, do NOT repeat)

| Pitfall | Symptom | Fix |
|---|---|---|
| `enable_mc2_hierarchy_comm` + `enable_fused_mc2` | Startup crash: "fused mc2 op cannot be used with hierarchy communication" | Do NOT set `enable_mc2_hierarchy_comm` when `enable_fused_mc2=1` |
| DSpark5 (`num_spec=5`) | Startup crash: "Can't determine cudagraph shapes that are both a multiple of 6 and 4" | `num_spec+1` must be divisible by `tensor_parallel_size` (4). Use 3, 7, 11... |
| `multistream_overlap_shared_expert` + `enable_fused_mc2` | Auto-disabled with warning | Code handles this automatically; set `multistream_overlap_shared_expert=false` explicitly |
| seq64 / max-num-seqs=64 | -15% regression | Larger batch lowers DSpark acceptance rate; keep seq32 |

---

## Phase 2 — Benchmark with aiperf

### 2.1 Run the C64 benchmark

On the test host, use `scripts/run-c64-test.sh`:

```bash
bash run-c64-test.sh <label> <num_runs>
# Example: bash run-c64-test.sh final-acceptance 3
```

This runs warmup (30 req) + N formal rounds (300 req each) at C64, ISL=128,
OSL=256, streaming, ignore_eos=true.

### 2.2 Final acceptance test

Use `scripts/run-final-acceptance.sh` for the formal 3-round acceptance test
with 2 warmup rounds. All 3 formal rounds must exceed 1280 tok/s.

### 2.3 Expected results

| Round | TPS (tok/s) | >1280? |
|---|---:|---|
| formal-run1 | 1495.57 | ✅ |
| formal-run2 | 1524.63 | ✅ |
| formal-run3 | 1548.44 | ✅ |
| **Mean** | **1522.88** | ✅ |
| **CV** | **1.7%** | ✅ ≤3% |
| **Per-concurrency** | **23.8 tok/s** | ✅ >20 |

---

## Phase 3 — Aggregate & report

Run `scripts/aggregate-results.py` to build the xlsx workbook with 5 sheets:
optimization path, all results, profile operator statistics, profile communication,
and final config.

```bash
python3 scripts/aggregate-results.py dsv4-c64-1280tps-result.xlsx
```

---

## Final Configuration Summary

| Parameter | Value | Role |
|---|---|---|
| TP × DP | 4 × 4 | 16-die topology |
| EP | 16 | Expert parallelism |
| Quantization | ascend (W8A8) | 8-bit weight, 8-bit activation |
| max-num-seqs | 32 | Optimal batch size for DSpark |
| block-size | 128 | KV cache block size |
| **enable_fused_mc2** | **1** | **MoE comm fusion (MAIN EFFECT +23%)** |
| **num_speculative_tokens** | **3** | **DSpark3 (high-concurrency optimal)** |
| **enable_mlapo** | **1** | **MLA Pool optimization** |
| **enable_dsa_cp** | **true** | **DSA Compressor Pipeline (synergy +36%)** |
| multistream_overlap_shared_expert | false | Required by Fused MC2 (mutex) |
| enforce_eager | true | Drafter eager mode |
| cudagraph_mode | FULL_DECODE_ONLY | Graph capture for decode only |
| async-scheduling | true | Async scheduling |
| enable_prefix_caching | false | No prefix reuse in fixed-ISL benchmark |

---

## Excluded Optimizations (verified, do NOT retry)

| Optimization | Result | Reason |
|---|---|---|
| seq64 + batch16k | 838 tok/s (-15%) | Larger batch lowers DSpark acceptance |
| DSpark5 (num_spec=5) | Startup failure | 6 not divisible by TP4 |
| enable_mc2_hierarchy_comm | Startup failure | Mutually exclusive with fused_mc2 |
| DSA-CP alone (without Fused MC2) | 642-710 tok/s | Regression without Fused MC2 synergy |
| enforce_eager=false | Worse (historical) | Drafter graph unstable on DSV4 |
| CPU KV offload | Worse (historical) | Fixed-ISL never triggers offload |
| block32 + prefix-cache | Worse (historical) | No prefix reuse; block mgmt overhead |

---

## Files in this skill

```
dsv4-c64-1280tps-skill/
├── SKILL.md                                    ← this file
├── scripts/
│   ├── dspark-serve-final.sh                   ← final optimized vllm serve command
│   ├── dspark-serve-param.sh                   ← parameterized serve script
│   ├── launch-dsv4-param.sh                    ← docker run + health check
│   ├── run-c64-test.sh                         ← generic C64 benchmark
│   ├── run-c64-verify.sh                       ← extended verification (2 warmup + 5 rounds)
│   ├── run-final-acceptance.sh                 ← formal 3-round acceptance test
│   └── aggregate-results.py                    ← xlsx generator
├── reports/
│   └── dsv4-c64-1280tps-optimization-report-en.md  ← English optimization report
├── references/
│   ├── profile-analysis.md                     ← operator-level profile findings
│   └── optimization-decisions.md               ← why each optimization was chosen/excluded
└── data/
    └── dsv4-c64-1280tps-result.xlsx            ← measured results workbook
```

---

## Reproducibility notes

- Inference host: 115.120.85.166 (private 10.0.2.156), 16-die Ascend 910 A3
- Test host: 115.120.84.96, aiperf 0.11.0
- Model path: `/mnt/sfs_turbo/models/DeepSeek-V4-Flash-0731-w8a8` (on inference host)
- Model path: `/mnt/sfs_turbo/models/DeepSeek-V4-Flash-0731-w8a8` (on test host, shared FS)
- Image: `quay.io/ascend/vllm-ascend:DeepSeekV4-flash-0731-a3` (vLLM 0.25.1)
- Service port: 6697
- Benchmark: aiperf profile, C64, ISL=128, OSL=256, 300 requests, streaming, ignore_eos=true
- Date: 2026-08-09
