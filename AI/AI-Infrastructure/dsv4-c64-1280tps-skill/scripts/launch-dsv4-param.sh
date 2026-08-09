#!/usr/bin/env bash
set -euo pipefail
IMAGE="quay.io/ascend/vllm-ascend:DeepSeekV4-flash-0731-a3"
CONTAINER="dsv4-vllm-dspark-tp4dp4"
NET_IF="enp23s0f3"
PORT=6697
LABEL=${LABEL:-default}

docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

device_args=()
for id in $(seq 0 15); do
  device_args+=(--device "/dev/davinci${id}")
done

docker run -d \
  --name "$CONTAINER" --network host --shm-size 512g --privileged \
  "${device_args[@]}" \
  --device /dev/davinci_manager --device /dev/devmm_svm --device /dev/hisi_hdc \
  -v /mnt/sfs_turbo:/data \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/Ascend/driver/tools/hccn_tool:/usr/local/Ascend/driver/tools/hccn_tool \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /usr/local/Ascend/driver/lib64/:/usr/local/Ascend/driver/lib64/ \
  -v /usr/local/Ascend/driver/version.info:/usr/local/Ascend/driver/version.info \
  -v /etc/ascend_install.info:/etc/ascend_install.info \
  -v /etc/hccn.conf:/etc/hccn.conf \
  -v /root/dspark-serve-param.sh:/dspark-serve.sh:ro \
  -e TP=${TP:-4} -e DP=${DP:-4} \
  -e MAX_SEQS=${MAX_SEQS:-32} -e MAX_BATCH_TOKENS=${MAX_BATCH_TOKENS:-8192} \
  -e NUM_SPEC=${NUM_SPEC:-7} \
  -e FUSED_MC2=${FUSED_MC2:-0} -e DSA_CP=${DSA_CP:-0} \
  -e MULTISTREAM=${MULTISTREAM:-1} -e STATIC_KERNEL=${STATIC_KERNEL:-0} \
  -e GPU_MEM_UTIL=${GPU_MEM_UTIL:-0.90} \
  -e ENABLE_MLAPO=${ENABLE_MLAPO:-0} -e ENABLE_PREFILL_MC2=${ENABLE_PREFILL_MC2:-0} \
  -e OMP_PROC_BIND=false \
  -e VLLM_ENGINE_READY_TIMEOUT_S=1800 \
  -e OMP_NUM_THREADS=10 \
  -e PYTORCH_NPU_ALLOC_CONF=expandable_segments:True \
  -e HCCL_BUFFSIZE=1024 \
  -e TASK_QUEUE_ENABLE=1 \
  -e HCCL_OP_EXPANSION_MODE=AIV \
  -e VLLM_ASCEND_APPLY_DSV4_PATCH=1 \
  -e VLLM_ASCEND_ENABLE_FLASHCOMM1=1 \
  -e VLLM_ASCEND_ENABLE_DSPARK=1 \
  -e GLOO_SOCKET_IFNAME="$NET_IF" \
  -e HCCL_SOCKET_IFNAME="$NET_IF" \
  -e HCCL_IF_IP="$(python3 -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect((10.0.2.1,80));print(s.getsockname()[0])" 2>/dev/null || echo 10.0.2.156)" \
  "$IMAGE" \
  bash /dspark-serve.sh

echo "[${LABEL}] container launched on port $PORT"
for i in $(seq 1 180); do
  sleep 10
  if ! docker ps --format "{{.Names}}" | grep -qx "$CONTAINER"; then
    echo "[${LABEL}] ERROR: container died."
    docker logs --tail 30 "$CONTAINER" 2>&1
    exit 1
  fi
  if curl -sf "http://10.0.2.156:$PORT/health" >/dev/null 2>&1; then
    echo "[${LABEL}] READY after ${i}0s"
    exit 0
  fi
  [ $((i % 6)) -eq 0 ] && echo "[${LABEL}] ...${i}0s loading"
done
echo "[${LABEL}] TIMEOUT"
exit 1
