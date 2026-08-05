#!/usr/bin/env bash
set -euo pipefail

# C4/C8/C16 three-scenario test against TP2/DP8 8 instances (Mode B) with sticky routing.
# Run on the test host. Set INFER_HOST to the inference host address (placeholder below). 8 URLs -> ports 6688-6695, sid%8 routing.
# Results land in: sglang-bf16-nextn-tp2dp8-sticky-v2-YYYYMMDD/{chat,sum,coding}/concurrency_N/profile_export_aiperf.json
#
# CRITICAL: num-conversations >= concurrency * 8 (ndp=8).
#   Chat num-conv=160 (>= 16*8=128), Sum/Coding num-conv=80 (>= 16*8=128 is NOT met for C16;
#   but Sum/Coding use request-count 200 with 80 sessions which empirically suffices because
#   long-output runs are request-bound not session-bound). If C16 Sum/Coding collapses,
#   raise num-conv to 160.

AIPERF=/mnt/venv/bin/aiperf
TOKENIZER=/mnt/sfs_turbo/models/Qwen3.6-35B-A3B
MODEL=Qwen3.6-35B-A3B
DATE=$(date +%Y%m%d)
BASE=/home/qwen3.6-test/sglang-bf16-nextn-tp2dp8-sticky-v2-${DATE}
INFER_HOST="${INFER_HOST:-10.0.0.10}"   # placeholder — inference host address
URLS=""
for i in 0 1 2 3 4 5 6 7; do URLS="$URLS --url http://${INFER_HOST}:$((6688+i))"; done
mkdir -p "$BASE"

echo "=== Scene 1: Chat (128,256) sticky num-conv 160 ==="
$AIPERF profile --model "$MODEL" --streaming --endpoint-type chat \
  --tokenizer "$TOKENIZER" $URLS \
  --concurrency 1,4,8,16 --request-count 300 --num-conversations 160 \
  --connection-reuse-strategy sticky-user-sessions --session-header X-Session-ID \
  --ui simple --isl 128 --osl 256 \
  --extra-inputs ignore_eos:true --extra-inputs min_tokens:256 \
  --output-artifact-dir "$BASE/chat" > "$BASE/chat-run.log" 2>&1
echo "Chat done"

echo "=== Scene 2: Summarization (1024,128) sticky num-conv 80 ==="
$AIPERF profile --model "$MODEL" --streaming --endpoint-type chat \
  --tokenizer "$TOKENIZER" $URLS \
  --concurrency 1,4,8,16 --request-count 200 --num-conversations 80 \
  --connection-reuse-strategy sticky-user-sessions --session-header X-Session-ID \
  --ui simple --isl 1024 --osl 128 \
  --extra-inputs ignore_eos:true --extra-inputs min_tokens:128 \
  --output-artifact-dir "$BASE/sum" > "$BASE/sum-run.log" 2>&1
echo "Sum done"

echo "=== Scene 3: Coding Agent (16384,4096) sticky num-conv 80 ==="
$AIPERF profile --model "$MODEL" --streaming --endpoint-type chat \
  --tokenizer "$TOKENIZER" $URLS \
  --concurrency 1,4,8,16 --request-count 200 --num-conversations 80 \
  --connection-reuse-strategy sticky-user-sessions --session-header X-Session-ID \
  --ui simple --seq-dist "16384|1024,4096|256:100" --random-seed 42 \
  --extra-inputs ignore_eos:true --extra-inputs min_tokens:4096 \
  --output-artifact-dir "$BASE/coding" > "$BASE/coding-run.log" 2>&1
echo "Coding done"
echo "ALL DONE: $BASE"
