#!/usr/bin/env bash
set -euo pipefail
export VLLM_USE_MODELSCOPE=True
export PYTORCH_NPU_ALLOC_CONF=expandable_segments:True
export HCCL_OP_EXPANSION_MODE=AIV
export HCCL_BUFFSIZE=1024
export OMP_NUM_THREADS=1
export TASK_QUEUE_ENABLE=1
export PYTHONHASHSEED=0
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libjemalloc.so.2:${LD_PRELOAD:-}
export LD_LIBRARY_PATH=/usr/local/lib:/usr/local/lib64:${LD_LIBRARY_PATH:-}
export ASCEND_RT_VISIBLE_DEVICES=0,1,2,3,4,5,6,7
export ASCEND_BUFFER_POOL=4:8
export ASCEND_CONNECT_TIMEOUT=10000
export ASCEND_TRANSFER_TIMEOUT=10000
export MOONCAKE_CONFIG_PATH=/mnt/sfs_turbo/script/qwen3.6-8card/mooncake.json

exec vllm serve /mnt/sfs_turbo/models/Qwen3.6-35B-A3B \
  --host 0.0.0.0 \
  --port 8002 \
  --data-parallel-size 4 \
  --tensor-parallel-size 2 \
  --enable-expert-parallel \
  --seed 1024 \
  --enable-prefix-caching \
  --served-model-name Qwen3.6-35B-A3B \
  --max-num-seqs 128 \
  --max-model-len 65536 \
  --max-num-batched-tokens 8192 \
  --trust-remote-code \
  --gpu-memory-utilization 0.918 \
  --compilation-config '{"cudagraph_mode":"FULL_DECODE_ONLY"}' \
  --additional-config '{"enable_cpu_binding":true,"enable_flashcomm1":true,"multistream_overlap_shared_expert":true}' \
  --no-async-scheduling \
  --kv-transfer-config '{"kv_connector":"AscendStoreConnector","kv_role":"kv_both","kv_load_failure_policy":"fail","kv_connector_extra_config":{"lookup_rpc_port":"0","backend":"mooncake","load_async":false}}'
