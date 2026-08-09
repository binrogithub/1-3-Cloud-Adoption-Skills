# DeepSeek-V4-Flash C64 >1280 TPS Optimization Report

| Item | Value |
|---|---|
| Date | 2026-08-09 |
| Inference node | 115.120.85.166 (private 10.0.2.156), 16-die Ascend 910 A3 |
| Test node | 115.120.84.96, aiperf 0.11.0 |
| Model | DeepSeek-V4-Flash-0731 W8A8 (294GB) |
| Software | vLLM 0.25.1, vLLM-Ascend DeepSeekV4-flash-0731-a3, CANN 9.0.1 |
| Workload | C64, ISL=128, OSL=256, streaming, ignore_eos=true, 300 requests |
| Target | C64 aggregate output TPS >1280 (per-concurrency >20 tok/s) |
| **Result** | **1523 tok/s (23.8 tok/s/concurrency), CV=1.7%** |

## 1. Executive Summary

Starting from a control group baseline of 796 tok/s, we achieved 1523 tok/s
(+91.3%) through a profile-driven optimization approach. The key insight was
that MoE communication (dispatch + combine) occupied 66% of the critical path,
making it the dominant bottleneck — not GMM computation (6%).

The final configuration combines four optimizations with strong synergy:
**Fused MC2** (MoE communication fusion, +23% main effect) + **DSpark3**
(speculative decoding tuned for high concurrency, +53%) + **MLAPO** (MLA Pool
optimization, +55%) + **DSA-CP** (DSA Compressor Pipeline, +91% with synergy).

All 3 formal acceptance rounds exceeded 1280 tok/s with CV=1.7%.

## 2. Methodology

The optimization followed a strict profile-driven methodology:

1. **Phase 0 — Freeze control group**: Establish a stable baseline (DSpark7,
   DSA-CP off, seq32). Verified 3-round reproducibility (CV=1.1%).

2. **Phase 1 M0-1 — Client ceiling falsification**: Compared 1×C64 vs 2×C32
   clients. Result: +2% (below 5% threshold), client is not the bottleneck.

3. **Phase 1 M0-2 — Operator-level profile**: Collected 10s of steady-state
   decode profiling using torch_npu.profiler. Analyzed operator statistics,
   communication statistics, and API statistics.

4. **Phase 2 — Profile-driven optimization**: Applied targeted optimizations
   based on profile findings, testing each combination with proper controls.

## 3. Operator-Level Profile Findings

Profile collected on dp0/tp0/ep0 during 10s steady-state C64 decode.

### 3.1 Operator Time Distribution

| Operator | Total Time (us) | Count | Ratio (%) |
|---|---:|---:|---:|
| **MoeDistributeDispatchV2** | **11,947,400** | **1,333** | **59.0%** |
| MoeDistributeCombineV2 | 933,169 | 1,333 | 4.6% |
| DynamicQuant | 653,556 | 8,917 | 3.2% |
| GroupedMatmulSwigluQuant | 409,308 | 2,322 | 2.0% |
| allgatherAicpuKernel | 252,067 | 1,135 | 1.2% |
| MatMulV2 | 250,577 | 6,844 | 1.2% |
| QuantBatchMatmulV3 | 248,824 | 10,422 | 1.2% |
| SparseAttnSharedkv | 177,369 | 2,107 | 0.9% |

**Key insight**: MoE dispatch communication alone accounts for 59% of total
operator time. Combined with combine (4.6%) and other communication ops, total
MoE communication is ~66% of the critical path. GMM computation is only 6%.

### 3.2 Communication Statistics

| Communication Op | Total Time (us) | Count | Ratio (%) |
|---|---:|---:|---:|
| hcom_allGather | 1,700,840 | 5,633 | 42.7% |
| hcom_reduceScatter | 1,346,608 | 4,128 | 33.8% |
| hcom_alltoallv | 86873,740 | 903 | 21.7% |
| hcom_allReduce | 69,462 | 602 | 1.7% |

## 4. Optimization Path

| Step | Configuration | Mean TPS | vs Baseline | Key Finding |
|---|---|---:|---:|---|
| Phase 0 | Control group (DSpark7, DSA-CP off) | 796 | — | Stable baseline, CV=1.1% |
| Phase 2 | +Fused MC2 (DSpark7) | 979 | +23.0% | MoE comm fusion, main effect |
| Phase 2 | DSpark7 → DSpark3 | 1,221 | +53.4% | Less spec overhead at C64 |
| Phase 2 | +MLAPO | 1,235 | +55.2% | MLA Pool optimization |
| **Phase 2** | **+DSA-CP on** | **1,523** | **+91.3%** | **Strong synergy, breakthrough** |

### 4.1 Why Fused MC2 is the Main Effect (+23%)

Fused MC2 replaces the sequential dispatch → FFN → combine pipeline with a
fused `dispatch_ffn_combine/mega_moe` operator. Since MoE communication was 66%
of the critical path, reducing communication rounds directly attacks the
dominant cost. The fusion eliminates intermediate synchronization points and
reduces the number of all-to-all operations.

### 4.2 Why DSpark3 Beats DSpark7 at High Concurrency

At C64, each decode step processes 64 concurrent sequences. With DSpark7, each
step attempts 7 speculative tokens per sequence, creating 64×8=512 tokens for
verification. The rejection rate increases under high concurrency, wasting
compute on discarded tokens. DSpark3 reduces this to 64×4=256 tokens, improving
the effective acceptance rate and throughput.

**TP4 constraint**: `num_speculative_tokens + 1` must be divisible by
`tensor_parallel_size` (4). Valid values: 3, 7, 11, 15... DSpark5 (6 not
divisible by 4) causes startup failure.

### 4.3 DSA-CP Synergy (+36% Incremental)

DSA-CP (DSA Compressor Pipeline) alone previously caused regression (642-710
tok/s with DSpark7). However, when combined with Fused MC2 + DSpark3, it
produces a strong positive synergy (+36% incremental). This is a classic
interaction effect that single-factor A/B testing would miss — demonstrating
the value of the factorial combination approach.

## 5. Final Configuration

```bash
vllm serve /data/models/DeepSeek-V4-Flash-0731-w8a8 \
  --host 0.0.0.0 --port 6697 \
  --served-model-name DeepSeek-V4-Flash-0731-w8a8 \
  --tensor-parallel-size 4 --data-parallel-size 4 \
  --enable-expert-parallel \
  --quantization ascend \
  --tokenizer-mode deepseek_v4 \
  --tool-call-parser deepseek_v4 --enable-auto-tool-choice \
  --reasoning-parser deepseek_v4 \
  --trust-remote-code \
  --max-model-len 131072 \
  --max-num-batched-tokens 8192 \
  --max-num-seqs 32 \
  --gpu-memory-utilization 0.90 \
  --block-size 128 \
  --safetensors-load-strategy prefetch \
  --no-enable-prefix-caching \
  --async-scheduling \
  --speculative-config '{"method":"dspark","num_speculative_tokens":3,"enforce_eager":true}' \
  --compilation-config '{"cudagraph_mode":"FULL_DECODE_ONLY"}' \
  --additional-config '{"ascend_compilation_config":{"enable_npugraph_ex":true,"enable_static_kernel":false},"enable_cpu_binding":true,"multistream_overlap_shared_expert":false,"enable_dsa_cp":true,"enable_fused_mc2":1,"enable_mlapo":1}'
```

## 6. Final Acceptance Results

3 formal rounds (300 requests each, C64, ISL=128, OSL=256):

| Round | TPS (tok/s) | >1280? |
|---|---:|---|
| formal-run1 | 1,495.57 | ✅ |
| formal-run2 | 1,524.63 | ✅ |
| formal-run3 | 1,548.44 | ✅ |
| **Mean** | **1,522.88** | ✅ |
| **Median** | **1,524.63** | ✅ |
| **Min** | **1,495.57** | ✅ |
| **CV** | **1.7%** | ✅ ≤3% |
| **Per-concurrency** | **23.8 tok/s** | ✅ >20 |

Previous 5-round pre-verification: 1524, 1502, 1583, 1506, 1540
(mean=1531, CV=2.3%), also all >1280.

## 7. Excluded Optimizations

| Optimization | Result | Reason |
|---|---|---|
| seq64 + batch16k | 838 tok/s (-15%) | Larger batch lowers DSpark acceptance |
| DSpark5 (num_spec=5) | Startup failure | num_spec+1=6 not divisible by TP4 |
| enable_mc2_hierarchy_comm | Startup failure | Mutually exclusive with fused_mc2 |
| DSA-CP alone (no Fused MC2) | 642-710 tok/s | Regression without Fused MC2 synergy |
| enforce_eager=false | Worse (historical) | Drafter graph unstable on DSV4 |
| CPU KV offload | Worse (historical) | Fixed-ISL never triggers offload |
| block32 + prefix-cache | Worse (historical) | No prefix reuse; block mgmt overhead |

## 8. Correctness Verification

- temperature=0 golden prompt output matches control group:
  "The capital of France is" → "Paris. The capital of Spain is Madrid. The
  capital of Italy is Rome."
- 100% request success rate, no errors or truncation

## 9. Conclusion

Through profile-driven optimization, we identified MoE communication (66% of
critical path) as the dominant bottleneck and achieved 1523 tok/s (+91% over
baseline) by combining Fused MC2 communication fusion, DSpark3 speculative
decoding, MLAPO, and DSA-CP. All formal acceptance rounds exceeded the 1280
tok/s target with CV=1.7%.
