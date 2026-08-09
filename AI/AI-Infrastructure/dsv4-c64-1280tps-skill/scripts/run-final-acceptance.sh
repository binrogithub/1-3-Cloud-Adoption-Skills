#!/usr/bin/env bash
# Final acceptance v2 - no set -e
AIPERF=/mnt/venv/bin/aiperf
TOKENIZER=/mnt/sfs_turbo/models/DeepSeek-V4-Flash-0731-w8a8
MODEL=DeepSeek-V4-Flash-0731-w8a8
DATE=$(date +%Y%m%d-%H%M%S)
BASE=/home/qwen3.6-test/final-v2-${DATE}
URL="--url http://10.0.2.156:6697"
mkdir -p "$BASE"

run_point() {
  local label=$1; local rc=$2; local outdir="$BASE/${label}"
  mkdir -p "$outdir"
  echo "=== C64 [final/${label}] req=${rc} $(date +%T) ==="
  $AIPERF profile --model "$MODEL" --streaming --endpoint-type chat \
    --tokenizer "$TOKENIZER" $URL \
    --concurrency 64 --request-count "$rc" \
    --ui simple --isl 128 --osl 256 \
    --extra-inputs ignore_eos:true --extra-inputs min_tokens:256 \
    --output-artifact-dir "$outdir" > "$outdir/run.log" 2>&1
  local csv="$outdir/profile_export_aiperf.csv"
  if [ -f "$csv" ]; then
    tps=$(grep -i '^Output Token Throughput' "$csv" | tail -1 | cut -d, -f2)
    succ=$(grep -i '^Successful Request Count' "$csv" | tail -1 | cut -d, -f2)
    echo "  TPS=${tps} | success=${succ}"
    echo "${tps}" >> "$BASE/results.txt"
  else
    echo "  NO CSV"
    echo "0" >> "$BASE/results.txt"
  fi
}

run_point warmup1 30
run_point warmup2 64
run_point formal-run1 300
run_point formal-run2 300
run_point formal-run3 300

echo ""
echo "========================================"
echo "FINAL ACCEPTANCE RESULTS"
echo "========================================"
echo "Formal rounds: $(cat "$BASE/results.txt" 2>/dev/null | tail -n +3 | tr '\n' ' ')"
