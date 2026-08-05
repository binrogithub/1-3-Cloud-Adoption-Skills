#!/usr/bin/env bash
set -euo pipefail

# Mode A: TP16 single engine for C1 (single-user) scenario.
# Occupies all 16 die (davinci0-15), port 6696.
# Deploy on the inference host. Set INFER_HOST to its address (placeholder below).

IMAGE="swr.sa-brazil-1.myhuaweicloud.com/llm-test-brazil/sglang:v0.5.14-cann9.0.0-a3-arm64"
MODEL_PATH="/data/models/Qwen3.6-35B-A3B"
CONTAINER="qwen-sglang-tp16"
NET_IF="enp23s0f3"
INFER_HOST="${INFER_HOST:-10.0.0.10}"   # placeholder — this host's own address, used for the health probe

docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

device_args=()
for id in $(seq 0 15); do
  device_args+=(--device "/dev/davinci${id}:/dev/davinci${id}")
done

docker run -d \
  --name "$CONTAINER" \
  --network host \
  --ipc host \
  --shm-size 64g \
  "${device_args[@]}" \
  --device /dev/davinci_manager:/dev/davinci_manager \
  --device /dev/devmm_svm:/dev/devmm_svm \
  --device /dev/hisi_hdc:/dev/hisi_hdc \
  -v /mnt/sfs_turbo:/data \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
  -v /usr/local/dcmi:/usr/local/dcmi:ro \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi:ro \
  -v /etc/ascend_install.info:/etc/ascend_install.info:ro \
  -v /etc/hccn.conf:/etc/hccn.conf:ro \
  -e ASCEND_USE_FIA=1 \
  -e GLOO_SOCKET_IFNAME="$NET_IF" \
  -e HCCL_SOCKET_IFNAME="$NET_IF" \
  -e HCCL_BUFFSIZE=1 \
  -e HCCL_OP_EXPANSION_MODE=AIV \
  -e PYTORCH_NPU_ALLOC_CONF=expandable_segments:True \
  -e SGLANG_ENABLE_OVERLAP_PLAN_STREAM=0 \
  -e SGLANG_SET_CPU_AFFINITY=1 \
  -e STREAMS_PER_DEVICE=32 \
  "$IMAGE" \
  python3 -m sglang.launch_server \
    --model-path "$MODEL_PATH" \
    --host 0.0.0.0 \
    --port 6696 \
    --tp-size 16 \
    --nnodes 1 \
    --attention-backend ascend \
    --device npu \
    --chunked-prefill-size 4096 \
    --max-total-tokens 262144 \
    --max-prefill-tokens 32768 \
    --disable-radix-cache \
    --trust-remote-code \
    --prefill-max-requests 16 \
    --max-running-requests 32 \
    --max-mamba-cache-size 64 \
    --mem-fraction-static 0.80 \
    --cuda-graph-bs 1 2 4 8 16 \
    --enable-multimodal \
    --mm-attention-backend ascend_attn \
    --dtype bfloat16 \
    --mamba-ssm-dtype bfloat16 \
    --speculative-algorithm NEXTN \
    --speculative-num-steps 3 \
    --speculative-eagle-topk 1 \
    --speculative-num-draft-tokens 4 \
    --reasoning-parser qwen3 \
    --tool-call-parser qwen3_coder

echo "Launched $CONTAINER on port 6696. Waiting health..."
for j in $(seq 1 120); do
  if curl -s -m 3 http://${INFER_HOST}:6696/health >/dev/null 2>&1; then echo "READY"; exit 0; fi
  sleep 5
done
echo "TIMEOUT"
