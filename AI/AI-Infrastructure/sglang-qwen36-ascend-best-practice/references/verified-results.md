# Verified Results

**Date**: 2026-08-05
**Setup**: Qwen3.6-35B-A3B, SGLang v0.5.14-cann9.0.0-a3-arm64, 8 × Ascend 910 (16 die), BF16 + NEXTN

## 1. Final Results (output tok/s per user)

Hybrid topology: **C1 from TP16 single engine**, **C4/C8/C16 from TP2/DP8 sticky**.

| Scenario | C1 (TP16) | C4 (TP2/DP8) | C8 (TP2/DP8) | C16 (TP2/DP8) |
|---|---|---|---|---|
| Chat (128, 256) | 160.33 | 137.61 | 122.49 | 94.10 |
| Coding Agent (16384, 4096) | 151.55 | 132.90 | 118.90 | 94.22 |
| Summarization (1024, 128) | 148.46 | 132.39 | 117.45 | 94.54 |

## 2. Comparison vs Historical Best (xlsx SGLang Exp2, TP16 single engine)

| Scenario | C | This work | Exp2 (historical best) | Delta |
|---|---|---|---|---|
| Chat | C1 | 160.33 | 147.20 | +9% ✅ |
| Chat | C4 | 137.61 | 109.27 | +26% ✅ |
| Chat | C8 | 122.49 | 90.76 | +35% ✅ |
| Chat | C16 | 94.10 | 82.05 | +15% ✅ |
| Coding | C1 | 151.55 | 145.53 | +4% ✅ |
| Coding | C4 | 132.90 | 86.20 | +54% ✅ |
| Coding | C8 | 118.90 | 73.73 | +61% ✅ |
| Coding | C16 | 94.22 | 60.06 | +57% ✅ |
| Sum | C1 | 148.46 | 135.62 | +9% ✅ |
| Sum | C4 | 132.39 | 76.71 | +73% ✅ |
| Sum | C8 | 117.45 | 46.44 | +153% ✅ |
| Sum | C16 | 94.54 | 49.16 | +92% ✅ |

**Result: 12/12 data points exceed the historical best (+4% to +153%).**

## 3. Root Causes of the Prior Gap (now fixed)

### 3.1 C1 collapse (fixed by Mode A: TP16)
- **Root cause**: sticky routing pinned the single C1 request to 1/8 TP2 instance (14 die idle). TP2 prefill=322 tok/s/user, TTFT=2729ms.
- **Fix**: C1 uses TP16 single engine — 1 request monopolizes 16 die, prefill ~10× faster.
- **Measured**: Chat C1 110.69 → 160.33, Coding C1 134.75 → 151.55, Sum C1 127.40 → 148.46.

### 3.2 Chat C16 collapse (fixed by raising num-conversations)
- **Root cause**: `--num-conversations 30` limited C16 to ~30 requests; cold-start + queuing dominated. TTFT=2111ms.
- **Fix**: `--num-conversations 160` (≥ C16 × 8 = 128). Each instance gets enough sessions to stay warm.
- **Measured**: Chat C16 43.81 → 94.10 (+115%).

## 4. Why BF16 + NEXTN (not w8a8)

- NEXTN speculative decoding: accept len ~3.33 → effective decode ~3.3× speedup. This is the primary accelerator.
- w8a8 (modelslim) + NEXTN is **incompatible** on sglang v0.5.14: MoE `scheme=None` crash (`AttributeError: 'NoneType' object has no attribute 'create_weights'`).
- w8a8 without NEXTN performs worse than BF16 + NEXTN. BF16 + NEXTN is the optimum.
