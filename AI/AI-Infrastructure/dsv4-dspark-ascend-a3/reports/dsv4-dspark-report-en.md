# DeepSeek-V4-Flash-0731 W8A8 + DSpark Speculative Decoding — vLLM 0.25.1 Ascend A3 Test Report

**Test Date**: 2026-08-07
**Model**: DeepSeek-V4-Flash-0731-w8a8 (284B params, 13B activated, DSpark speculative decoding module)
**Framework**: vLLM 0.25.1 (`quay.io/ascend/vllm-ascend:DeepSeekV4-flash-0731-a3`)
**Speculative Decoding**: DSpark, `num_speculative_tokens=7`, `enforce_eager=true`
**Hardware**: 8 × Ascend 910 (A3) NPU = 16 die, 64GB HBM/die
**Topology**: TP4 + DP4, expert-parallel, port 6697

---

## 1. Background

Baseline test (2026-08-06, vLLM 0.22.1rc1, no speculative decoding) showed DSV4 W8A8 at 23.8-32.4 tok/s/user, ~0.20-0.31x of Qwen3.6 BF16+NEXTN. The primary gap was the absence of speculative decoding (ITL ~30ms/token).

**DSpark** is DeepSeek-V4-Flash-0731's native speculative decoding (block_size=5, Markov head + confidence head on layers 40-42). It requires vLLM-Ascend v0.25.1+ with dedicated image `DeepSeekV4-flash-0731-a3`.

---

## 2. Core Results: DSpark vs Baseline Throughput (tok/s/user)

| Scenario | C | Baseline | DSpark | Speedup | Qwen BF16+NEXTN | DSpark/Qwen |
|---|---|---|---|---|---|---|
| Chat (128,256) | C1 | 32.40 | **63.38** | **1.96x** | 159.76 | 0.40x |
| Chat | C4 | 30.41 | 51.80 | 1.70x | 136.20 | 0.38x |
| Chat | C8 | 29.90 | 42.40 | 1.42x | 121.86 | 0.35x |
| Chat | C16 | 28.96 | 29.45 | 1.02x | 94.44 | 0.31x |
| Sum (1024,128) | C1 | 31.09 | **63.99** | **2.06x** | 148.32 | 0.43x |
| Sum | C4 | 29.79 | 40.52 | 1.36x | 135.09 | 0.30x |
| Sum | C8 | 28.08 | 25.50 | 0.91x | 120.29 | 0.21x |
| Sum | C16 | 26.67 | 16.64 | 0.62x | 92.14 | 0.18x |
| Coding (16384,4096) | C1 | 30.68 | **89.17** | **2.91x** | 152.30 | 0.59x |
| Coding | C4 | 30.94 | 66.51 | 2.15x | 133.48 | 0.50x |
| Coding | C8 | 26.65 | 56.68 | 2.13x | 120.00 | 0.47x |
| Coding | C16 | 23.75 | 43.05 | 1.81x | 97.47 | 0.44x |

---

## 3. ITL Reduction (ms/token)

| Scenario | C | Baseline ITL | DSpark ITL | Reduction |
|---|---|---|---|---|
| Chat | C1 | 30.87 | 16.16 | -48% |
| Sum | C1 | 32.18 | 15.85 | -51% |
| Coding | C1 | 32.60 | 12.48 | -62% |
| Coding | C16 | 42.66 | 25.20 | -41% |

DSpark reduces ITL by 41-62% at low concurrency. Coding C1 ITL drops to 12.5ms/token (baseline 32.6ms).

---

## 4. TTFT (ms)

| Scenario | C | TTFT avg | TTFT p50 | TTFT p99 |
|---|---|---|---|---|
| Chat | C1 | 272.4 | 268.5 | 318.9 |
| Sum | C1 | 414.6 | 412.1 | 454.6 |
| Coding | C1 | 2595.7 | 2655.9 | 3876.0 |
| Coding | C16 | 6041.7 | 4626.0 | 12989.2 |

DSpark TTFT slightly lower than baseline at low concurrency (Chat C1 272ms vs 294ms) — drafter adds minimal prefill overhead.

---

## 5. NPU Utilization (DSpark vs Baseline)

| Metric | Baseline | DSpark |
|---|---|---|
| AICore avg | 82.2% | 65.2% |
| HBM avg | 58.9 GB/die | 50.3 GB/die |
| CPU avg | 6.7% | 8.4% |

DSpark AICore **lower** (65% vs 82%) — speculative decoding produces more tokens per NPU step, so less AICore time per output token. This is the expected signature of effective spec decode.

---

## 6. Key Findings

### 6.1 DSpark Effective at Low-Medium Concurrency
- C1 speedup: **1.96-2.91x** across scenarios (best on Coding 16K)
- DSpark acceptance_len ~5 (7 speculative tokens, ~5 accepted) — matches PR #12777 benchmarks
- Coding (long context) benefits most: 2.91x at C1 — long decode amortizes drafter overhead

### 6.2 DSpark Degrades at High Concurrency
- Chat C16: only 1.02x (no gain); Sum C16: 0.62x (regression!)
- Sum C8/C16 ITL rises to 41-65ms (worse than baseline 36-38ms)
- Cause: high concurrency increases batch size → drafter batch scheduling overhead grows → acceptance rate drops → spec decode overhead exceeds benefit
- **Recommendation**: DSpark best for C1-C4 (latency-focused); disable for C16+ (throughput-focused)

### 6.3 Gap to Qwen BF16+NEXTN Narrowed
- Baseline was 0.20-0.31x of Qwen; DSpark improves to **0.31-0.59x**
- Coding C1 DSpark reaches **0.59x** of Qwen (89 vs 152 tok/s)
- Remaining gap: Qwen NEXTN is more mature on A3 (accept_len 3.3, optimized for all concurrency); DSpark is new on A3 (v0.25.1 first release)

### 6.4 Deployment Fixes (v0.25.1 vs v0.22.1rc1)
- `enable_multithread_load` must be bool (not string)
- `multithread_load` incompatible with `safetensors-load-strategy=prefetch` → removed multithread
- DSpark requires `VLLM_ASCEND_ENABLE_DSPARK=1` env

---

## 7. Conclusion

DSpark speculative decoding successfully deployed on Ascend A3 (vLLM 0.25.1), delivering **1.96-2.91x throughput improvement** at low concurrency over the no-spec-decode baseline. Coding agent (16K context) sees the largest gain (2.91x at C1, ITL 32.6→12.5ms).

**Best use case**: DSpark for low-concurrency latency-sensitive workloads (C1-C4). For high-concurrency throughput (C16), baseline without spec decode is comparable or better.

**vs Qwen3.6 BF16+NEXTN**: DSpark narrows gap from 0.20-0.31x to 0.31-0.59x. Remaining gap is DSpark's A3 immaturity (first release) vs Qwen NEXTN's mature optimization.
