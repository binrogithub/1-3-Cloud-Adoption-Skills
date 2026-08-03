#!/usr/bin/env bash
# clean-vllm.sh — 彻底清理 166 上所有 vllm 进程 (含孤儿和端口监听者)
# 根因: pkill -9 vllm 主进程后, 子进程被 PID1(sleep infinity)接管,
#       继续监听 8002 (SO_REUSEPORT 静默共享) 或变 defunct。
#       必须杀整个进程树 + 查孤儿子进程 + 查端口监听者。
# 用法: bash clean-vllm.sh [--strict]  (--strict=清理后断言必须全0, 否则exit 1)
set -uo pipefail
STRICT="${1:-}"

# 1. 杀 vllm serve 主进程
pkill -9 -f "vllm serve" 2>/dev/null || true

# 2. 杀容器内孤儿子进程 (主进程死后被 PID1 接管的 ApiServer/EngineCore/Worker)
docker exec qwen3.6-8card bash -c '
  for p in $(ps -eo pid,cmd | grep -iE "VLLM::|EngineCore|Worker_DP|vllm serve" | grep -v grep | grep -v defunct | awk "{print \$1}"); do
    kill -9 $p 2>/dev/null || true
  done
' 2>/dev/null || true

# 3. 杀宿主机 8002 端口所有监听者 (含容器外孤儿 ApiServer)
for p in $(ss -tlnp 2>/dev/null | grep ":8002" | grep -oE "pid=[0-9]+" | grep -oE "[0-9]+"); do
  kill -9 $p 2>/dev/null || true
done

sleep 3

# 4. 确认
n_main=$(ps -eo args 2>/dev/null | grep -c "[v]llm serve")
n_child=$(docker exec qwen3.6-8card bash -c 'ps -eo cmd|grep -iE "VLLM::|EngineCore|Worker_DP"|grep -v grep|grep -v defunct|wc -l' 2>/dev/null || echo 0)
n_port=$(ss -tlnp 2>/dev/null | grep -c ":8002")
n_npu=$(npu-smi info 2>/dev/null | grep -c VLLMWorker)
n_mooncake=$(docker exec qwen3.6-8card bash -c 'ps -eo cmd|grep mooncake_master|grep -v grep|wc -l' 2>/dev/null || echo 0)

echo "清理结果: 主进程=$n_main 孤儿子=$n_child 端口=$n_port NPU=$n_npu mooncake=$n_mooncake"

if [ "$STRICT" = "--strict" ]; then
  if [ "$n_main" -ne 0 ] || [ "$n_child" -ne 0 ] || [ "$n_port" -ne 0 ] || [ "$n_npu" -ne 0 ]; then
    echo "FATAL: 清理不彻底" >&2
    exit 1
  fi
  echo "OK: 清理彻底, mooncake 保留"
fi
