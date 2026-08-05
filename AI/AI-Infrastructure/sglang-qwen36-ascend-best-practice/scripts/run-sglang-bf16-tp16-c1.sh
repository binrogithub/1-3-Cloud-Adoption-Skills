#!/usr/bin/env bash
set -euo pipefail

# C1 three-scenario test against TP16 single engine (Mode A).
# Run on the test host. Set INFER_HOST to the inference host address (placeholder below). Single URL -> TP16 port 6696.
# Results land in: sglang-bf16-tp16-c1-YYYYMMDD/{chat,sum,coding}/profile_export_aiperf.json

AIPERF=/mnt/venv/bin/aiperf
TOKENIZER=/mnt/sfs_turbo/models/Qwen3.6-35B-A3B
MODEL=Qwen3.6-35B-A3B
DATE=$(date +%Y%m%d)
BASE=/home/qwen3.6-test/sglang-bf16-tp16-c1-${DATE}
INFER_HOST="${INFER_HOST:-10.0.0.10}"   # placeholder — inference host address
URL="--url http://${INFER_HOST}:6696"
mkdir -p "$BASE"

echo "=== Chat C1 (TP16) ==="
$AIPERF profile --model "$MODEL" --streaming --endpoint-type chat \
  --tokenizer "$TOKENIZER" $URL \
  --concurrency 1 --request-count 300 \
  --ui simple --isl 128 --osl 256 \
  --extra-inputs ignore_eos:true --extra-inputs min_tokens:256 \
  --output-artifact-dir "$BASE/chat" > "$BASE/chat-run.log" 2>&1
echo "Chat C1 done"

echo "=== Sum C1 (TP16) ==="
$AIPERF profile --model "$MODEL" --streaming --endpoint-type chat \
  --tokenizer "$TOKENIZER" $URL \
  --concurrency 1 --request-count 200 \
  --ui simple --isl 1024 --osl 128 \
  --extra-inputs ignore_eos:true --extra-inputs min_tokens:128 \
  --output-artifact-dir "$BASE/sum" > "$BASE/sum-run.log" 2>&1
echo "Sum C1 done"

echo "=== Coding C1 (TP16) ==="
$AIPERF profile --model "$MODEL" --streaming --endpoint-type chat \
  --tokenizer "$TOKENIZER" $URL \
  --concurrency 1 --request-count 50 \
  --ui simple --seq-dist "16384|1024,4096|256:100" --random-seed 42 \
  --extra-inputs ignore_eos:true --extra-inputs min_tokens:4096 \
  --output-artifact-dir "$BASE/coding" > "$BASE/coding-run.log" 2>&1
echo "Coding C1 done"
echo "ALL DONE: $BASE"
