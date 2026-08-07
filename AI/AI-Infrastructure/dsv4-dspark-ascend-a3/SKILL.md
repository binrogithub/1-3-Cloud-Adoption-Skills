---
name: dsv4-dspark-ascend-a3
description: Deploy and benchmark DeepSeek-V4-Flash-0731 W8A8 with DSpark speculative decoding on Ascend A3 NPU using vLLM 0.25.1. Use when the user asks to deploy DSV4 with DSpark, benchmark DSV4 on Ascend, enable speculative decoding for DeepSeek V4, or reproduce the DSpark TPS optimization test.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
  - Edit
---

# DSV4-Flash-0731 W8A8 + DSpark on Ascend A3 — Deployment & Benchmark Skill

Deploys DeepSeek-V4-Flash-0731 W8A8 with DSpark speculative decoding on 16-die
Ascend A3 NPUs (vLLM 0.25.1), then benchmarks with aiperf (3 scenarios × 4
concurrency). DSpark delivers **1.96–2.91× throughput** over the no-spec-decode
baseline at low concurrency.

---

## What this skill produces

- A running vLLM 0.25.1 service (TP4+DP4, DSpark num_spec=7) on port 6697
- aiperf benchmark results: 12 data points (Chat/Sum/Coding × C1/C4/C8/C16)
- NPU/CPU/memory utilization logs
- An xlsx results workbook + bilingual report

---

## Prerequisites

| Item | Requirement |
|---|---|
| Inference host | 8 × Ascend 910 A3 NPU = 16 die, 64GB HBM/die, ≥400GB disk |
| Test host | aiperf 0.11.0 installed, network access to inference host |
| Model | `DeepSeek-V4-Flash-0731-w8a8` (294GB, modelslim W8A8) downloaded |
| Image | `quay.io/ascend/vllm-ascend:DeepSeekV4-flash-0731-a3` (vLLM 0.25.1, ~17GB) |
| SSH | key-based access to both hosts from the operator machine |

> **Critical**: DSpark requires vLLM-Ascend **v0.25.1+**. The older
> `v0.22.1rc1-a3` image does NOT support `method:dspark` and only supports
> `method:mtp`, which fails on 0731 weights (no `mtp.0.head.weight`).

---

## Phase 1 — Deploy the DSpark service

### 1.1 Pull the DSpark image

On the inference host:

```bash
docker pull quay.io/ascend/vllm-ascend:DeepSeekV4-flash-0731-a3
```

Verify it contains the DSpark proposer:

```bash
docker run --rm quay.io/ascend/vllm-ascend:DeepSeekV4-flash-0731-a3 \
  find / -name "dspark_proposer*" -o -name "deepseek_v4_mtp*"
# expect:
# /vllm-workspace/vllm-ascend/vllm_ascend/models/deepseek_v4_mtp.py
# /vllm-workspace/vllm-ascend/vllm_ascend/spec_decode/dspark_proposer.py
```

### 1.2 Write the serve script

Create `/root/dspark-serve.sh` on the inference host. **The JSON quoting matters
— use the exact escaped form below.** A mounted script avoids bash heredoc
quoting hell that breaks `--speculative-config` JSON.

```bash
cat > /root/dspark-serve.sh <<"SERVE"
#!/usr/bin/env bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
source /usr/local/Ascend/cann-9.0.0/share/info/ascendnpu-ir/bin/set_env.sh 2>/dev/null || true
source /usr/local/Ascend/nnal/atb/set_env.sh 2>/dev/null || true
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libjemalloc.so.2:${LD_PRELOAD:-}
exec vllm serve /data/models/DeepSeek-V4-Flash-0731-w8a8 \
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
  --speculative-config "{\"method\":\"dspark\",\"num_speculative_tokens\":7,\"enforce_eager\":true}" \
  --compilation-config "{\"cudagraph_mode\":\"FULL_DECODE_ONLY\"}" \
  --additional-config "{\"ascend_compilation_config\":{\"enable_npugraph_ex\":true,\"enable_static_kernel\":false},\"enable_cpu_binding\":true,\"multistream_overlap_shared_expert\":true}"
SERVE
chmod +x /root/dspark-serve.sh
```

### 1.3 Write the launch script

Create `/root/launch-dsv4-dspark-v2.sh` — mounts the serve script into the
container and runs a health-check loop. See `scripts/launch-dsv4-dspark-v2.sh`
in this skill for the full version. Key points:

- Mount `-v /root/dspark-serve.sh:/dspark-serve.sh:ro`, run `bash /dspark-serve.sh`
- All 16 die: `--device /dev/davinci0` … `--device /dev/davinci15`
- Env: `VLLM_ASCEND_ENABLE_DSPARK=1`, `VLLM_ASCEND_ENABLE_FLASHCOMM1=1`,
  `VLLM_ASCEND_APPLY_DSV4_PATCH=1`, `HCCL_BUFFSIZE=1024`, `TASK_QUEUE_ENABLE=1`,
  `HCCL_OP_EXPANSION_MODE=AIV`, `PYTORCH_NPU_ALLOC_CONF=expandable_segments:True`
- `--shm-size 512g --privileged --network host`

### 1.4 Launch and verify

```bash
nohup /root/launch-dsv4-dspark-v2.sh > /tmp/dspark-launch.log 2>&1 &
# wait ~10 min for model load + CUDA graph capture
curl http://<inference-ip>:6697/health   # expect 200
curl http://<inference-ip>:6697/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-V4-Flash-0731-w8a8","prompt":"The capital of France is","max_tokens":16,"temperature":0}'
# expect: " Paris. The capital of Italy is Rome. The capital of Spain is Madrid."
```

### 1.5 Deployment pitfalls (verified, do NOT repeat)

| Pitfall | Symptom | Fix |
|---|---|---|
| Wrong image version | `Unsupported connector` / `method:dspark cannot be converted` | Use `DeepSeekV4-flash-0731-a3` (v0.25.1), NOT `v0.22.1rc1-a3` |
| JSON quoting broken by heredoc | `Value method:dspark cannot be converted` / `Invalid JSON: key must be a string` | Mount the serve script as a file; do NOT inline JSON in `bash -c` |
| `enable_multithread_load` string | `ValueError: enable_multithread_load must be a bool, got str` | Use `true` (bool), not `"true"` (string) |
| multithread + prefetch conflict | `enable_multithread_load does not support safetensors_load_strategy='prefetch'` | Remove `--model-loader-extra-config` entirely; keep `--safetensors-load-strategy prefetch` |

---

## Phase 2 — Benchmark with aiperf

### 2.1 Start the NPU utilization sampler

On the inference host:

```bash
nohup /root/sample-util.sh dsv4-dspark 2 >/dev/null 2>&1 &
# writes /tmp/util-dsv4-dspark.log
# format: epoch ts ai0 hbm0 ai1 hbm1 ... ai15 hbm15 cpu_busy% mem_used_mb mem_total_mb
```

### 2.2 Write the aiperf test script

On the test host, create `run-dsv4-dspark-tp4dp4-all.sh` (see
`scripts/run-dsv4-dspark-tp4dp4-all.sh`). It runs 3 scenarios × 4 concurrency:

| Scenario | ISL/OSL | Requests | Concurrency |
|---|---|---|---|
| Chat | 128/256 | 300 | 1, 4, 8, 16 |
| Summarization | 1024/128 | 200 | 1, 4, 8, 16 |
| Coding Agent | 16384/4096 | 50 (seq-dist) | 1, 4, 8, 16 |

All hit the same port (DP4 handles parallelism internally).

### 2.3 Run the benchmark

```bash
nohup /home/qwen3.6-test/run-dsv4-dspark-tp4dp4-all.sh \
  > /home/qwen3.6-test/dsv4-dspark-master.log 2>&1 &
# ~3-4 hours total; Coding C1 is the long pole (~29 min)
```

### 2.4 Collect results

```bash
# stop sampler
ssh root@<inference-ip> 'pkill -f sample-util.sh'
# pull 12 JSON results + util log to the operator machine
scp root@<test-ip>:/home/qwen3.6-test/dsv4-w8a8-dspark-tp4dp4-*/*/profile_export_aiperf.json ./
scp root@<inference-ip>:/tmp/util-dsv4-dspark.log ./
```

---

## Phase 3 — Aggregate & report

Run `scripts/aggregate-dspark.py` (included) to build the xlsx with 5 sheets:
3-way throughput (DSpark vs baseline vs Qwen), ITL, TTFT, utilization, config.
Then write the report from `reports/dsv4-dspark-report-en.md` (included as a
template — substitute your measured numbers).

---

## Key results (our measurement, 2026-08-07)

### DSpark vs no-spec-decode baseline (tok/s/user)

| Scenario | C | Baseline | DSpark | Speedup |
|---|---|---|---|---|
| Chat (128,256) | C1 | 32.40 | 63.38 | **1.96×** |
| Sum (1024,128) | C1 | 31.09 | 63.99 | **2.06×** |
| Coding (16384,4096) | C1 | 30.68 | 89.17 | **2.91×** |
| Coding | C16 | 23.75 | 43.05 | 1.81× |

- DSpark best at **C1–C4** (latency-sensitive); degrades at C16 (Sum C16 0.62× regression)
- ITL reduced 41–62% at low concurrency (Coding C1: 32.6→12.5 ms/token)
- vs Qwen3.6 BF16+NEXTN: gap narrowed from 0.20–0.31× to **0.31–0.59×**
- NPU AICore **drops** (82%→65%) — signature of effective spec decode (more tokens per NPU step)

### Optimizations tested and rejected (control variable, single-factor)

| Optimization | Result | Reason |
|---|---|---|
| block-size 32 + prefix-cache | ❌ worse | fixed-ISL benchmark has no prefix reuse; block mgmt overhead exceeds cache gain |
| CPU KV offload (RecomputeCPUOffloadConnector) | ❌ worse | single-request fixed-ISL never triggers offload; connector has fixed overhead |
| Remove `enforce_eager` (drafter FULL ACLGraph) | ❌ worse | drafter graph unstable/slower on DSV4 |
| max-num-seqs 64 | ❌ -23% | larger batch lowers DSpark acceptance; spec overhead exceeds gain |
| enable_dsa_cp | ❌ worse + 19/50 errors | conflicts with DSpark; unstable |

**Conclusion**: DSpark with `enforce_eager:true`, `block-size 128`, `max-num-seqs 32`,
no prefix-cache, no CPU offload is the optimal config. Other optimizations target
multi-turn/prefix-reuse workloads or conflict with DSpark.

---

## Files in this skill

```
dsv4-dspark-ascend-a3/
├── README.md                                   ← human-readable overview
├── SKILL.md                                    ← this file
├── scripts/
│   ├── dspark-serve.sh                         ← vllm serve command (mount into container)
│   ├── launch-dsv4-dspark-v2.sh                ← docker run + health check loop
│   ├── run-dsv4-dspark-tp4dp4-all.sh           ← aiperf 3 scenarios × 4 concurrency
│   ├── sample-util.sh                          ← NPU/CPU/mem sampler
│   └── aggregate-dspark.py                     ← xlsx generator
├── reports/
│   └── dsv4-dspark-report-en.md                ← English report template
├── data/
│   └── dsv4-dspark-vs-baseline-result-20260807.xlsx  ← our measured results
└── references/
    ├── optimization-summary.md                 ← all TPS optimizations researched
    └── deployment-pitfalls.md                  ← verified pitfalls and fixes
```

---

## Reproducibility notes

- Hosts: one inference host (16 die) + one separate test host running aiperf.
  Addresses in all files are placeholders — the scripts read the inference host
  from `INFER_HOST` (default `10.0.0.10`), so export it before running them.
- Model path on inference: `/mnt/sfs_turbo/models/DeepSeek-V4-Flash-0731-w8a8`
- Image: `quay.io/ascend/vllm-ascend:DeepSeekV4-flash-0731-a3` (vLLM 0.25.1)
- DSpark acceptance_len ≈ 5 (7 speculative tokens, ~5 accepted) — matches PR #12777
- Image pull from quay.io can be unstable from the inference host; retry with a
  loop (`for i in 1 2 3 4 5; do docker pull ... && break || sleep 10; done`)
