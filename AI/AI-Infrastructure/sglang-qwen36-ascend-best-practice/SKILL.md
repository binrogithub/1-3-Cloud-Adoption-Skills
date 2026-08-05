---
name: sglang-qwen36-ascend-best-practice
description: Reproduce the verified best-practice SGLang deployment of Qwen3.6-35B-A3B (MoE) on Huawei Ascend 910 NPU (8 cards × 2 die = 16 die). Hybrid topology: C1 → TP16 single engine, C4+ → TP2/DP8 sticky. BF16 + NEXTN speculative decoding. All 12 data points (3 scenarios × 4 concurrency) exceed the historical best.
---

# Skill: SGLang + Qwen3.6-35B-A3B on Ascend NPU — Best-Practice Reproduction

**Version**: v1.0
**Date**: 2026-08-05
**Status**: Verified — 12/12 data points exceed historical best (xlsx SGLang Exp2)
**Model**: Qwen3.6-35B-A3B (MoE, 256 experts, top-8, hybrid attention: 10 full-attn + 30 GDN linear-attn)
**Framework**: SGLang v0.5.14-cann9.0.0-a3-arm64 on Ascend 910 (A3) NPU

---

## 1. What This Skill Does

Reproduces the optimal inference deployment for Qwen3.6-35B-A3B on a 16-die Ascend NPU host. The key finding from extensive A/B testing: **no single topology wins all concurrency levels**. The best practice is a **hybrid topology**:

| Concurrency | Topology | Why |
|---|---|---|
| **C1 (single user)** | **TP16 single engine** (1 process, 16 die) | 1 request monopolizes all 16 die → fastest prefill, lowest TTFT |
| **C4+ (multi user)** | **TP2/DP8 sticky** (8 processes, 2 die each) | 8 instances distribute load, sufficient batch per instance, NEXTN benefit fully realized |

### 1.1 Verified Results (output tok/s per user)

| Scenario | C1 | C4 | C8 | C16 |
|---|---|---|---|---|
| Chat (128, 256) | **160.33** | **137.61** | **122.49** | **94.10** |
| Coding Agent (16384, 4096) | **151.55** | **132.90** | **118.90** | **94.22** |
| Summarization (1024, 128) | **148.46** | **132.39** | **117.45** | **94.54** |

All 12 points exceed the historical best (xlsx SGLang Exp2, TP16 single engine) by +4% to +153%.

---

## 2. Prerequisites

### 2.1 Hardware

| Item | Value |
|---|---|
| NPU host | 8 × Ascend 910 (A3), 16 die (`/dev/davinci0` – `/dev/davinci15`) |
| HBM | 64 GiB per NPU, 512 GiB total |
| Network interface | `enp23s0f3` (used for HCCL/GLOO sockets in TP16 mode) |

### 2.2 Software (on inference host)

| Item | Value |
|---|---|
| SGLang image | `swr.sa-brazil-1.myhuaweicloud.com/llm-test-brazil/sglang:v0.5.14-cann9.0.0-a3-arm64` |
| Model path (BF16) | `/data/models/Qwen3.6-35B-A3B` (mounted from `/mnt/sfs_turbo/models/Qwen3.6-35B-A3B`) |
| Docker | with `--device /dev/davinci*` + `--device /dev/davinci_manager` + `--device /dev/devmm_svm` + `--device /dev/hisi_hdc` |
| Ascend driver mounts | `/usr/local/Ascend/driver`, `/usr/local/dcmi`, `/usr/local/bin/npu-smi`, `/etc/ascend_install.info`, `/etc/hccn.conf` (all `:ro`) |

### 2.3 Test host

| Item | Value |
|---|---|
| aiperf | `/mnt/venv/bin/aiperf` |
| Tokenizer path | `/mnt/sfs_turbo/models/Qwen3.6-35B-A3B` |

### 2.4 Hosts in this setup

Two hosts on the same private subnet. **All addresses below are placeholders — substitute your own.**

| Role | Private IP (placeholder) | Referred to below as |
|---|---|---|
| Inference (NPU) | `10.0.0.10` | inference host |
| Test (aiperf) | `10.0.0.20` | test host |

Every script reads the inference host address from `INFER_HOST` (defaulting to the
placeholder), so `export INFER_HOST=<your-inference-host>` before running them.

SSH keyless configured. If the network drops packets, use `ConnectTimeout=30 ServerAliveInterval=10`.

---

## 3. Reproduction Procedure

### Phase A: Deploy Mode A — TP16 single engine (for C1 scenario)

On the **inference host**:

```bash
# Clean any running sglang containers first
docker rm -f qwen-sglang-tp16 sglang-bf16-r0 sglang-bf16-r1 sglang-bf16-r2 sglang-bf16-r3 \
              sglang-bf16-r4 sglang-bf16-r5 sglang-bf16-r6 sglang-bf16-r7 2>/dev/null

# Launch TP16 single engine (port 6696, all 16 die)
bash /root/launch-sglang-bf16-tp16.sh
# Wait until it prints "READY"
curl -s http://10.0.0.10:6696/health  # must return 200
```

On the **test host**:

```bash
bash /home/qwen3.6-test/run-sglang-bf16-tp16-c1.sh
# Runs Chat / Sum / Coding at C1 only, results under:
#   /home/qwen3.6-test/sglang-bf16-tp16-c1-YYYYMMDD/{chat,sum,coding}/profile_export_aiperf.json
```

### Phase B: Deploy Mode B — TP2/DP8 8 instances (for C4+ scenario)

On the **inference host**:

```bash
# Clean TP16 first (frees all 16 die)
docker rm -f qwen-sglang-tp16 2>/dev/null

# Launch 8 TP2 instances (ports 6688-6695, 2 die each)
bash /root/launch-sglang-bf16-nextn-tp2dp8.sh
# Wait until it prints "DONE" with all 8 instances READY
for p in 6688 6689 6690 6691 6692 6693 6694 6695; do
  curl -s http://10.0.0.10:$p/health >/dev/null && echo "$p OK" || echo "$p FAIL"
done
```

On the **test host**:

```bash
bash /home/qwen3.6-test/run-sglang-bf16-nextn-tp2dp8-sticky-v2.sh
# Runs Chat / Sum / Coding at C1/C4/C8/C16 with sticky routing, results under:
#   /home/qwen3.6-test/sglang-bf16-nextn-tp2dp8-sticky-v2-YYYYMMDD/{chat,sum,coding}/concurrency_N/profile_export_aiperf.json
```

### Phase C: Aggregate results into xlsx

```bash
python3 /tmp/gen-final-xlsx.py
# Produces /home/qwen3.6-test/sglang-tp2dp8-final-result.xlsx
# 3 blocks: sglang-tp2dp8-sticky-v2 / sglang-tp16-c1 / sglang-BEST
# BEST = C1 from TP16, C4/C8/C16 from TP2/DP8
```

---

## 4. Key Rules (MUST follow)

### 4.1 ✅ Must Follow

1. **`num-conversations ≥ concurrency × ndp`**: Sticky routes by `session_id % 8`. If num-conv < C×8, some instances stay idle, cold-start + queuing dominates, throughput collapses.
   - Measured Chat C16: 43.81 tok/s at num-conv=30 → **94.10** at num-conv=160 (+115%).
   - Required minimums: Chat num-conv=160, Sum/Coding num-conv=80.

2. **C1 uses TP16, C4+ uses TP2/DP8**: C1 has only 1 concurrent request; sticky pins it to 1/8 instances (14 die idle). TP16 monopolizes 16 die, prefill ~10× faster.

3. **BF16 + NEXTN**: NEXTN speculative decoding is the primary accelerator (accept len ~3.33 → decode ~3.3×), 2-3× more impactful than w8a8 quantization bandwidth savings.

4. **Each TP2 spans only 2 die within the same NPU**: `davinci0-1, 2-3, ..., 14-15`. Never cross-NPU — minimizes HCCL communication overhead.

### 4.2 ❌ Prohibitions

1. **w8a8 + NEXTN incompatible**: sglang v0.5.14 + modelslim w8a8 + `--speculative-algorithm NEXTN` → MoE `scheme=None` crash (`AttributeError: 'NoneType' object has no attribute 'create_weights'`). w8a8 must drop NEXTN, degrading performance.

2. **`num-conversations < concurrency × ndp`**: Instances idle, cold-start dominates, high-concurrency throughput collapses.

3. **C1 with sticky multi-instance**: Single request lands on 1 instance only, 7/8 compute wasted.

4. **TP2 cross-NPU**: High HCCL overhead. Keep TP2 within same NPU's 2 die.

---

## 5. Deployment Parameters

### 5.1 Common Environment Variables

```bash
ASCEND_USE_FIA=1
HCCL_OP_EXPANSION_MODE=AIV
PYTORCH_NPU_ALLOC_CONF=expandable_segments:True
SGLANG_SET_CPU_AFFINITY=1
STREAMS_PER_DEVICE=32
```

### 5.2 Mode A: TP16 Single Engine (C1)

| Parameter | Value | Notes |
|---|---|---|
| `--tp-size` | 16 | All 16 die |
| `--port` | 6696 | |
| `--chunked-prefill-size` | 4096 | |
| `--max-running-requests` | 32 | |
| `--mem-fraction-static` | 0.80 | |
| `--disable-radix-cache` | | C1 doesn't need cache |
| `--speculative-algorithm` | NEXTN | Speculative decoding |
| `--speculative-num-steps` | 3 | |
| `--speculative-eagle-topk` | 1 | |
| `--speculative-num-draft-tokens` | 4 | |
| `HCCL_BUFFSIZE` | 1 | Single process, no cross-die |
| `SGLANG_ENABLE_OVERLAP_PLAN_STREAM` | 0 | |
| `GLOO_SOCKET_IFNAME` / `HCCL_SOCKET_IFNAME` | `enp23s0f3` | TP16 multi-die needs socket IF |

### 5.3 Mode B: TP2/DP8 8 Instances (C4+)

| Parameter | Value | Notes |
|---|---|---|
| `--tp-size` | 2 | 2 die per instance |
| `--port` | 6688-6695 | 8 ports |
| `--chunked-prefill-size` | 2048 | |
| `--max-running-requests` | 64 | |
| `--mem-fraction-static` | 0.80 | |
| radix cache | **enabled (default)** | Sticky + prompt reuse hits |
| `--speculative-algorithm` | NEXTN | Same as Mode A |
| `HCCL_BUFFSIZE` | 512 | TP2 cross-die comms |
| `SGLANG_ENABLE_OVERLAP_PLAN_STREAM` | 1 | Overlap plan |

### 5.4 Docker Device Mapping

```bash
# Mode A (TP16): map all 16 die
--device /dev/davinci0 ... --device /dev/davinci15

# Mode B (TP2/DP8 instance i): map die 2i, 2i+1
--device /dev/davinci${2i} --device /dev/davinci${2i+1}
```

Common devices for both: `--device /dev/davinci_manager --device /dev/devmm_svm --device /dev/hisi_hdc`

---

## 6. Test Parameters

### 6.1 Three Scenarios

| Scenario | ISL | OSL | request-count | num-conversations |
|---|---|---|---|---|
| Chat | 128 | 256 | 300 | **160** |
| Summarization | 1024 | 128 | 200 | **80** |
| Coding Agent | 16384 | 4096 | 200 (50 for C1 TP16) | **80** |

Coding uses `--seq-dist "16384|1024,4096|256:100" --random-seed 42`.

### 6.2 Key Test Parameters

| Parameter | Value | Notes |
|---|---|---|
| `--concurrency` | 1,4,8,16 | Four levels (TP16 test is C1-only) |
| `--connection-reuse-strategy` | sticky-user-sessions | Session affinity |
| `--session-header` | X-Session-ID | Route by `sid % 8` to 8 instances |
| `--num-conversations` | ≥ concurrency × 8 | **Critical!** See §4.1 |
| `--extra-inputs` | `ignore_eos:true min_tokens:OSL` | Force full-length output for stable measurement |

### 6.3 Routing Strategy

- **C1**: single URL → TP16 port 6696
- **C4/C8/C16**: 8 URLs + sticky-user-sessions → TP2/DP8 ports 6688-6695

---

## 7. Files in This Package

```
sglang-qwen36-ascend-best-practice/
├── SKILL.md                                    ← this file (full reproduction guide)
├── scripts/
│   ├── launch-sglang-bf16-tp16.sh              ← Mode A: TP16 single engine (deploy on 166)
│   ├── launch-sglang-bf16-nextn-tp2dp8.sh      ← Mode B: 8 TP2/DP8 instances (deploy on 166)
│   ├── run-sglang-bf16-tp16-c1.sh              ← C1 three-scenario test (run on 96)
│   ├── run-sglang-bf16-nextn-tp2dp8-sticky-v2.sh ← C4/C8/C16 three-scenario test (run on 96)
│   └── gen-final-xlsx.py                       ← aggregate results into xlsx
├── config/
│   └── env-and-params.md                       ← parameter reference tables
├── data/
│   └── sglang-tp2dp8-final-result.xlsx         ← verified result (3 blocks)
└── references/
    ├── gap-analysis-prd.md                     ← root-cause analysis of prior gap
    └── verified-results.md                     ← measured numbers + comparison vs Exp2
```

---

## 8. Operating Procedure (end-to-end)

1. **C1 scenario**: Clean all containers → launch TP16 (`launch-sglang-bf16-tp16.sh`) → run C1 three scenarios → record results.
2. **C4+ scenario**: Clean TP16 → launch TP2/DP8 8 instances (`launch-sglang-bf16-nextn-tp2dp8.sh`) → run C4/C8/C16 three scenarios → record results.
3. **Aggregate**: C1 from TP16, C4/C8/C16 from TP2/DP8, merge as BEST, output xlsx via `gen-final-xlsx.py`.
4. **Cleanup**: `docker rm -f` all sglang containers after testing, release die.

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| C1 per-user throughput low (~110) | sticky pinned 1 req to 1/8 instance | Use TP16 single engine for C1 (Mode A) |
| Chat C16 collapses (~43) | num-conversations too low | Set num-conv ≥ C×8 (Chat=160, Sum/Coding=80) |
| MoE `scheme=None` crash | w8a8 + NEXTN incompatible | Use BF16 (not w8a8), or drop NEXTN |
| SSH `Connection closed` | network packet loss | Retry with `ConnectTimeout=30 ServerAliveInterval=10` |
| Instance not READY | cold start ~3-5 min | Wait up to 120 × 5s = 10 min; check `/tmp/sglang-bf16-rN.log` |
| Port conflict | prior container still bound | `docker rm -f` all sglang containers first |
