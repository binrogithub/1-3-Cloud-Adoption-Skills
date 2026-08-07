# DSV4 TPS Optimizations Researched & Tested

Sources: vllm-ascend GitHub PRs/issues, LMSYS blog, vLLM blog, DeepSeek blog,
DeepEP DeepWiki, FlashInfer PRs, LeCompute — all 2026.

## Tested on Ascend A3 (16 die)

| # | Optimization | Config change | Result | Verdict |
|---|---|---|---|---|
| 1 | **DSpark speculative decoding** | `--speculative-config {"method":"dspark","num_speculative_tokens":7,"enforce_eager":true}` + `VLLM_ASCEND_ENABLE_DSPARK=1` | **1.96–2.91× throughput** at C1–C4; ITL -41–62% | ✅ ADOPT |
| 2 | block-size 32 + prefix-caching | `--block-size 32`, remove `--no-enable-prefix-caching` | worse than baseline (fixed-ISL, no prefix reuse) | ❌ reject for this workload |
| 3 | CPU KV offload | `--kv-transfer-config {"kv_connector":"RecomputeCPUOffloadConnector",...}` 200GB CPU | worse (single-request never triggers offload; connector overhead) | ❌ reject for this workload |
| 4 | Remove enforce_eager | drop `"enforce_eager":true` from spec config | worse (drafter FULL ACLGraph unstable on DSV4) | ❌ reject |
| 5 | max-num-seqs 64 | `--max-num-seqs 64` | -23% at C16 (larger batch lowers DSpark acceptance) | ❌ reject |
| 6 | enable_dsa_cp | `additional_config.enable_dsa_cp=true` | worse + 19/50 errors (conflicts with DSpark) | ❌ reject |

**Already enabled by default in v0.25.1** (no action needed):
- IndexCache (DSA topk_indices reuse across decode steps) — v0.20.2rc1 #9390
- DSA multistream overlap (compressor, indexer-select, CV parallel) — `multistream_overlap_shared_expert:true`
- FlashComm v1 (sequence parallelism) — `VLLM_ASCEND_ENABLE_FLASHCOMM1=1`
- Fused MC2 MoE comm (CANN MegaMoe) — default for DeepSeek on A3
- npugraph_ex compilation backend

## Researched but NOT testable on this setup

| Optimization | Source | Why not tested here |
|---|---|---|
| EPLB (Expert Parallel Load Balancing) | LMSYS Waterfill/LPLB blog, SGLang #25285 | A3 vllm-ascend `enable_eplb` path unverified; SGLang-native |
| DeepEP V2 (analytical resource alloc) | DeepSeek DeepEP DeepWiki | NVIDIA-only (NVLink/RDMA); A3 uses HCCL |
| MegaMoE CuTeDSL (combine_dtype=nvfp4) | FlashInfer #3980, 1.89× vs deep_gemm | NVIDIA Blackwell; A3 uses CANN MegaMoe (FusedMC2) |
| FP4 indexer cache | vLLM blog `--attention_config.use_fp4_indexer_cache=True` | A3 has no FP4 support |
| INT2 quantization | Infatoshi/dsv4-int2 (17 tok/s single 96GB GPU) | A3 only supports W8A8; INT2/FP4 unsupported |
| PD disaggregation (Mooncake KV transfer) | vllm-ascend kv_pool, DeepSeek-V3.1 tutorial | requires multi-node; 166 is single-node 16 die |
| Pipeline parallelism + chunked PP | vllm-ascend `profiling_chunk_config` | single-node TP4+DP4 is optimal; PP adds bubble |
| ShadowRadix prefix cache | SGLang Day-0 blog | SGLang-native; vllm-ascend uses its own prefix cache |
| HiSparse (hierarchical memory sparse attn) | SGLang Day-0 blog | SGLang-native; vllm-ascend uses DSA backend |
| Lightning TopK / fast topk kernel | vllm roadmap #40902 | likely already in v0.25.1 DSA path |

## When the rejected optimizations WOULD help

- **block-size 32 + prefix-cache**: multi-turn dialogue / agent workloads with
  repeated prefixes (PR #10354 shows 87% hit rate vs 45% at block-size 128)
- **CPU KV offload**: high-concurrency long-context with KV pressure (offload
  cold blocks to host RAM, keep hot blocks in HBM)
- **max-num-seqs 64**: throughput-focused high-concurrency WITHOUT speculative
  decoding (DSpark acceptance drops with batch size)
- **enable_dsa_cp**: long-context prefill WITHOUT DSpark (DSA context parallel
  splits prefill across die; conflicts with DSpark drafter)

## Key references

- DSpark PR: vllm-ascend #11196 (Add DeepSeek V4 DSpark support)
- DSpark bugfix: vllm-ascend #12777 (Fix sp in dspark, acceptance_len ~5.0)
- block-size 32: vllm-ascend #10354 (compressor block_size 32/64/128)
- block-size 128 prefix cache issue: vllm-ascend #12589
- CPU offload HMA: vllm-ascend #9162 (RecomputeCPUOffloadConnectorV1 SupportsHMA)
- DSA multistream: vllm-ascend v0.20.2rc1 release notes (#9450 #9441 #9433)
- DSV4 vLLM blog: vllm.ai/blog/2026-04-24-deepseek-v4
- SGLang DSV4 Day-0: lmsys.org/blog/2026-04-25-deepseek-v4
- Waterfill/LPLB: lmsys.org/blog/2026-06-26-waterfill-lplb
- DeepEP V2: deepwiki.com/deepseek-ai/DeepEP
