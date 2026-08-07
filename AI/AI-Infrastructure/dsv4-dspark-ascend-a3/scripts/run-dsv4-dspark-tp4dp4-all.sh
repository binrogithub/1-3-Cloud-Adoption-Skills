#!/usr/bin/env bash
set -euo pipefail
AIPERF=/mnt/venv/bin/aiperf
TOKENIZER=/mnt/sfs_turbo/models/DeepSeek-V4-Flash-0731-w8a8
MODEL=DeepSeek-V4-Flash-0731-w8a8
DATE=$(date +%Y%m%d)
BASE=/home/qwen3.6-test/dsv4-w8a8-dspark-tp4dp4-${DATE}
INFER_HOST="${INFER_HOST:-10.0.0.10}"   # placeholder — export INFER_HOST
URL="--url http://${INFER_HOST}:6697"
mkdir -p "$BASE"

run_chat() {
  local c=$1
  echo "=== Chat C${c} (DSpark TP4+DP4) $(date +%T) ==="
  $AIPERF profile --model "$MODEL" --streaming --endpoint-type chat \
    --tokenizer "$TOKENIZER" $URL \
    --concurrency "$c" --request-count 300 \
    --ui simple --isl 128 --osl 256 \
    --extra-inputs ignore_eos:true --extra-inputs min_tokens:256 \
    --output-artifact-dir "$BASE/chat-c${c}" > "$BASE/chat-c${c}-run.log" 2>&1
  echo "Chat C${c} done $(date +%T)"
}

run_sum() {
  local c=$1
  echo "=== Sum C${c} (DSpark TP4+DP4) $(date +%T) ==="
  $AIPERF profile --model "$MODEL" --streaming --endpoint-type chat \
    --tokenizer "$TOKENIZER" $URL \
    --concurrency "$c" --request-count 200 \
    --ui simple --isl 1024 --osl 128 \
    --extra-inputs ignore_eos:true --extra-inputs min_tokens:128 \
    --output-artifact-dir "$BASE/sum-c${c}" > "$BASE/sum-c${c}-run.log" 2>&1
  echo "Sum C${c} done $(date +%T)"
}

run_coding() {
  local c=$1
  echo "=== Coding C${c} (DSpark TP4+DP4) $(date +%T) ==="
  $AIPERF profile --model "$MODEL" --streaming --endpoint-type chat \
    --tokenizer "$TOKENIZER" $URL \
    --concurrency "$c" --request-count 50 \
    --ui simple --seq-dist "16384|1024,4096|256:100" --random-seed 42 \
    --extra-inputs ignore_eos:true --extra-inputs min_tokens:4096 \
    --output-artifact-dir "$BASE/coding-c${c}" > "$BASE/coding-c${c}-run.log" 2>&1
  echo "Coding C${c} done $(date +%T)"
}

for c in 1 4 8 16; do run_chat "$c"; done
for c in 1 4 8 16; do run_sum "$c"; done
for c in 1 4 8 16; do run_coding "$c"; done

echo "ALL DONE: $BASE"
