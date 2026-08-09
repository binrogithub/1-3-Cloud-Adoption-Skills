# Profile Analysis — Operator-Level Findings

## Collection Method

- **Tool**: torch_npu.profiler via vLLM `--profiler-config`
- **Scope**: dp0/tp0/ep0 (one worker rank)
- **Duration**: 10 seconds steady-state decode
- **Load**: C64, ISL=128, OSL=256, 600 requests (profiling window at 25-35s)
- **Config**: Control group (DSpark7, DSA-CP off, seq32)

## Operator Statistics (Top 15 by Duration)

| Operator | Total Time (us) | Count | Ratio (%) |
|---|---:|---:|---:|
| MoeDistributeDispatchV2 | 11,947,400 | 1,333 | 59.0% |
| MoeDistributeCombineV2 | 933,169 | 1,333 | 4.6% |
| DynamicQuant | 653,556 | 8,917 | 3.2% |
| MoeDistributeDispatchV2 (kernel) | 460,715 | 2,322 | 2.3% |
| GroupedMatmulSwigluQuant | 409,308 | 2,322 | 2.0% |
| Neg | 363,432 | 1,806 | 1.8% |
| GroupedMatmulSwigluQuant (kernel) | 309,652 | 1,634 | 1.5% |
| allgatherAicpuKernel | 252,067 | 1,135 | 1.2% |
| MatMulV2 | 250,577 | 6,844 | 1.2% |
| QuantBatchMatmulV3 | 248,824 | 10,422 | 1.2% |
| QuantBatchMatmulV3 (variant) | 241,721 | 9,116 | 1.2% |
| MoeDistributeCombineV2 (kernel) | 214,170 | 2,322 | 1.1% |
| GroupedMatmul (kernel) | 198,974 | 2,322 | 1.0% |
| HcPre | 181,681 | 4,644 | 0.9% |
| SparseAttnSharedkv | 177,369 | 2,107 | 0.9% |

## Category Summary

| Category | Time (us) | Ratio | Count |
|---|---:|---:|---:|
| MoE Dispatch (MoeDistributeDispatchV2) | 12,408,115 | 61.3% | 3,655 |
| MoE Combine (MoeDistributeCombineV2) | 1,147,339 | 5.7% | 3,655 |
| GMM/MatMul | 1,244,960 | 6.1% | 42,505 |
| DynamicQuant (W8A8) | 802,649 | 4.0% | 22,107 |
| HCCL (HcPre/HcPost) | 446,947 | 2.2% | 15,824 |
| DSA Compressor | 419,941 | 2.1% | 12,028 |
| ScatterNdUpdate (MoE dispatch) | 317,283 | 1.6% | 12,738 |
| RmsNorm | 234,922 | 1.2% | 17,759 |
| Index (MoE routing) | 202,917 | 1.0% | 7,252 |
| RotaryEmbedding | 177,801 | 0.9% | 14,851 |
| Attention (SparseAttnSharedkv) | 177,369 | 0.9% | 2,107 |

## Communication Statistics

| Op | Total Time (us) | Count | Ratio (%) |
|---|---:|---:|---:|
| hcom_allGather | 1,700,840 | 5,633 | 42.7% |
| hcom_reduceScatter | 1,346,608 | 4,128 | 33.8% |
| hcom_alltoallv | 863,740 | 903 | 21.7% |
| hcom_allReduce | 69,462 | 602 | 1.7% |

## Key Conclusions

1. **MoE communication is the dominant bottleneck** (66% of critical path)
2. **GMM computation is NOT the bottleneck** (only 6%)
3. **Fused MC2 is the correct optimization** — it8 it fuses dispatch+FFN+combine
4. **Sampling is negligible** — Reduce Sample (包 S) not needed
5. **Graph fallback is not significant** — Static Kernel (包 K) low priority
6. **Drafter is not in top operators** — DSpark tuning (包 D) secondary

## Profile Thresholds (from PRD)

| Evidence | Priority Package | Triggered? |
|---|---|---|
| Client shard +5% | C (client) | No (+2%) |
| Graph fallback/Host gap ≥10% | K (static kernel) | No |
| Sampling/logits ≥8% | S (reduce sample) | No |
| **dispatch/combine/HCCL ≥15%** | **M (fused MC2)** | **Yes (66%)** |
| drafter+rejection ≥25% | D (DSpark tune) | Secondary |
