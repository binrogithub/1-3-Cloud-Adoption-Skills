#!/usr/bin/env bash
set -euo pipefail
IMAGE="quay.io/ascend/vllm-ascend:DeepSeekV4-flash-0731-a3"
CONTAINER="dsv4-vllm-dspark-tp4dp4"
NET_IF="${NET_IF:-enp23s0f3}"
PORT=6697
# Address the inference host reaches itself on. Placeholder — export INFER_HOST.
INFER_HOST="${INFER_HOST:-10.0.0.10}"
# Any reachable address on the same subnet; used only to derive the local IP for HCCL.
HCCL_PROBE_HOST="${HCCL_PROBE_HOST:-10.0.0.1}"

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
  -v /root/dspark-serve.sh:/dspark-serve.sh:ro \
  -e OMP_PROC_BIND=false \
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
  -e HCCL_IF_IP="$(python3 -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('${HCCL_PROBE_HOST}',80));print(s.getsockname()[0])" 2>/dev/null || echo "$INFER_HOST")" \
  "$IMAGE" \
  bash /dspark-serve.sh

echo "[dspark-v2] container $CONTAINER launched on port $PORT"
echo "[dspark-v2] waiting for /health (max 30 min)..."
for i in $(seq 1 180); do
  sleep 10
  if ! docker ps --format "{{.Names}}" | grep -qx "$CONTAINER"; then
    echo "[dspark-v2] ERROR: container died. Last 50 log lines:"
    docker logs --tail 50 "$CONTAINER" 2>&1
    exit 1
  fi
  if curl -sf "http://$INFER_HOST:$PORT/health" >/dev/null 2>&1; then
    echo "[dspark-v2] READY after ${i}0s"
    resp=$(curl -s "http://$INFER_HOST:$PORT/v1/completions" -H "Content-Type: application/json" -d "{\"model\":\"DeepSeek-V4-Flash-0731-w8a8\",\"prompt\":\"The capital of France is\",\"max_tokens\":8,\"temperature\":0}")
    echo "OUTPUT: $(echo "$resp" | python3 -c "import sys,json; print(repr(json.load(sys.stdin)[\"choices\"][0][\"text\"]))" 2>&1)"
    exit 0
  fi
  [ $((i % 6)) -eq 0 ] && echo "[dspark-v2] ...${i}0s loading (last: $(docker logs --tail 1 "$CONTAINER" 2>&1 | head -c 100))"
done
echo "[dspark-v2] TIMEOUT"
docker logs --tail 50 "$CONTAINER" 2>&1
exit 1
