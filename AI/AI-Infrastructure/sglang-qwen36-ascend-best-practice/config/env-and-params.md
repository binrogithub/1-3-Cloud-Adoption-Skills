# Configuration Reference: SGLang + Qwen3.6-35B-A3B on Ascend NPU

## 1. Common Environment Variables (both modes)

| Variable | Value | Purpose |
|---|---|---|
| `ASCEND_USE_FIA` | 1 | Use FIA (Fast Internal Access) |
| `HCCL_OP_EXPANSION_MODE` | AIV | HCCL op expansion mode |
| `PYTORCH_NPU_ALLOC_CONF` | `expandable_segments:True` | NPU memory allocator config |
| `SGLANG_SET_CPU_AFFINITY` | 1 | Pin CPU affinity |
| `STREAMS_PER_DEVICE` | 32 | Streams per NPU device |

## 2. Mode A: TP16 Single Engine (C1 scenario)

### 2.1 Mode-A-specific env vars

| Variable | Value | Why |
|---|---|---|
| `HCCL_BUFFSIZE` | 1 | Single process, no cross-die HCCL |
| `SGLANG_ENABLE_OVERLAP_PLAN_STREAM` | 0 | |
| `GLOO_SOCKET_IFNAME` | `enp23s0f3` | TP16 multi-die needs socket interface |
| `HCCL_SOCKET_IFNAME` | `enp23s0f3` | Same |

### 2.2 Mode A sglang args

| Parameter | Value |
|---|---|
| `--tp-size` | 16 |
| `--port` | 6696 |
| `--chunked-prefill-size` | 4096 |
| `--max-running-requests` | 32 |
| `--max-total-tokens` | 262144 |
| `--max-prefill-tokens` | 32768 |
| `--mem-fraction-static` | 0.80 |
| `--disable-radix-cache` | (flag) |
| `--speculative-algorithm` | NEXTN |
| `--speculative-num-steps` | 3 |
| `--speculative-eagle-topk` | 1 |
| `--speculative-num-draft-tokens` | 4 |
| `--dtype` | bfloat16 |
| `--mamba-ssm-dtype` | bfloat16 |
| `--attention-backend` | ascend |
| `--device` | npu |
| `--cuda-graph-bs` | 1 2 4 8 16 |

## 3. Mode B: TP2/DP8 8 Instances (C4+ scenario)

### 3.1 Mode-B-specific env vars

| Variable | Value | Why |
|---|---|---|
| `HCCL_BUFFSIZE` | 512 | TP2 cross-die HCCL comms |
| `SGLANG_ENABLE_OVERLAP_PLAN_STREAM` | 1 | Overlap plan stream |

### 3.2 Mode B sglang args

| Parameter | Value |
|---|---|
| `--tp-size` | 2 |
| `--port` | 6688-6695 (8 ports) |
| `--chunked-prefill-size` | 2048 |
| `--max-running-requests` | 64 |
| `--max-total-tokens` | 262144 |
| `--max-prefill-tokens` | 32768 |
| `--mem-fraction-static` | 0.80 |
| radix cache | **enabled (default)** — do NOT pass `--disable-radix-cache` |
| `--speculative-algorithm` | NEXTN |
| `--speculative-num-steps` | 3 |
| `--speculative-eagle-topk` | 1 |
| `--speculative-num-draft-tokens` | 4 |
| `--dtype` | bfloat16 |
| `--mamba-ssm-dtype` | bfloat16 |
| `--attention-backend` | ascend |
| `--device` | npu |
| `--cuda-graph-bs` | 1 2 4 8 16 |

## 4. Docker Device Mapping

### Mode A (TP16): all 16 die
```
--device /dev/davinci0:/dev/davinci0 ... --device /dev/davinci15:/dev/davinci15
--device /dev/davinci_manager --device /dev/devmm_svm --device /dev/hisi_hdc
```

### Mode B (TP2/DP8 instance i): die 2i, 2i+1
```
--device /dev/davinci${2i} --device /dev/davinci${2i+1}
--device /dev/davinci_manager --device /dev/devmm_svm --device /dev/hisi_hdc
```

## 5. Volume Mounts (both modes)
```
-v /mnt/sfs_turbo:/data
-v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro
-v /usr/local/dcmi:/usr/local/dcmi:ro
-v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi:ro
-v /etc/ascend_install.info:/etc/ascend_install.info:ro
-v /etc/hccn.conf:/etc/hccn.conf:ro
```

## 6. Instance → Die → Port Mapping (Mode B)

| Instance | Die | Port | NPU |
|---|---|---|---|
| r0 | davinci0, 1 | 6688 | NPU0 |
| r1 | davinci2, 3 | 6689 | NPU1 |
| r2 | davinci4, 5 | 6690 | NPU2 |
| r3 | davinci6, 7 | 6691 | NPU3 |
| r4 | davinci8, 9 | 6692 | NPU4 |
| r5 | davinci10, 11 | 6693 | NPU5 |
| r6 | davinci12, 13 | 6694 | NPU6 |
| r7 | davinci14, 15 | 6695 | NPU7 |

Each TP2 spans only 2 die within the **same NPU** — never cross-NPU.
