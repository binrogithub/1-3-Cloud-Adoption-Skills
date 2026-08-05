#!/usr/bin/env bash
set -euo pipefail

# Mode B: TP2/DP8 — 8 independent sglang instances for C4+ (multi-user) scenario.
# Each instance: TP2 on 2 die within the same NPU, ports 6688-6695.
# Deploy on the inference host. Set INFER_HOST to its address (placeholder below).
#
# Instance i -> die (2i, 2i+1), port (6688+i):
#   r0: die0,1   :6688    r1: die2,3   :6689    r2: die4,5   :6690    r3: die6,7   :6691
#   r4: die8,9   :6692    r5: die10,11 :6693    r6: die12,13 :6694    r7: die14,15 :6695

IMAGE="swr.sa-brazil-1.myhuaweicloud.com/llm-test-brazil/sglang:v0.5.14-cann9.0.0-a3-arm64"
MODEL_PATH="/data/models/Qwen3.6-35B-A3B"
BASE_PORT=6688
N=8
INFER_HOST="${INFER_HOST:-10.0.0.10}"   # placeholder — this host's own address, used for the health probes

declare -A ENV_VARS=(
  [ASCEND_USE_FIA]=1
  [HCCL_BUFFSIZE]=512
  [HCCL_OP_EXPANSION_MODE]=AIV
  [PYTORCH_NPU_ALLOC_CONF]=expandable_segments:True
  [SGLANG_ENABLE_OVERLAP_PLAN_STREAM]=1
  [SGLANG_SET_CPU_AFFINITY]=1
  [STREAMS_PER_DEVICE]=32
)

for i in $(seq 0 $((N-1))); do
  PORT=$((BASE_PORT + i)); DIE0=$((2*i)); DIE1=$((2*i+1)); NAME="sglang-bf16-r${i}"
  echo "Starting $NAME port $PORT die $DIE0,$DIE1"
  docker rm -f "$NAME" >/dev/null 2>&1
  ENV_ARGS=(); for k in "${!ENV_VARS[@]}"; do ENV_ARGS+=(-e "${k}=${ENV_VARS[$k]}"); done
  docker run -d --name "$NAME" --network host --shm-size 64g \
    --device /dev/davinci${DIE0} --device /dev/davinci${DIE1} \
    --device /dev/davinci_manager --device /dev/devmm_svm --device /dev/hisi_hdc \
    -v /mnt/sfs_turbo:/data \
    -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
    -v /usr/local/dcmi:/usr/local/dcmi:ro \
    -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi:ro \
    -v /etc/ascend_install.info:/etc/ascend_install.info:ro \
    -v /etc/hccn.conf:/etc/hccn.conf:ro \
    "${ENV_ARGS[@]}" "$IMAGE" \
    python3 -m sglang.launch_server \
      --model-path "$MODEL_PATH" \
      --host 0.0.0.0 --port "$PORT" --tp-size 2 --nnodes 1 \
      --attention-backend ascend --device npu \
      --chunked-prefill-size 2048 --max-total-tokens 262144 --max-prefill-tokens 32768 \
      --trust-remote-code --prefill-max-requests 16 --max-running-requests 64 \
      --max-mamba-cache-size 64 --mem-fraction-static 0.80 \
      --cuda-graph-bs 1 2 4 8 16 \
      --dtype bfloat16 --mamba-ssm-dtype bfloat16 \
      --speculative-algorithm NEXTN \
      --speculative-num-steps 3 --speculative-eagle-topk 1 --speculative-num-draft-tokens 4 \
      --reasoning-parser qwen3 --tool-call-parser qwen3_coder \
      > /tmp/${NAME}.log 2>&1 &
done
wait
echo "All launched. Waiting health..."
for i in $(seq 0 $((N-1))); do
  PORT=$((BASE_PORT + i))
  for j in $(seq 1 60); do
    if curl -s -m 3 http://${INFER_HOST}:${PORT}/health >/dev/null 2>&1; then echo "  r${i} ${PORT} READY"; break; fi
    sleep 5
  done
done
echo "DONE"
