#!/usr/bin/env bash
# Generic C64 test: $1=label, $2=runs (default 2)
set -euo pipefail
AIPERF=/mnt/venv/bin/aiperf
TOKENIZER=/mnt/sfs_turbo/models/DeepSeek-V4-Flash-0731-w8a8
MODEL=DeepSeek-V4-Flash-0731-w8a8
LABEL=${1:-test}
RUNS=${2:-2}
DATE=$(date +%Y%m%d-%H%M%S)
BASE=/home/qwen3.6-test/c64-${LABEL}-${DATE}
URL="--url http://10.0.2.156:6697"
mkdir -p "$BASE"

run_point() {
  local label=$1; local rc=$2; local outdir="$BASE/${label}"
  mkdir -p "$outdir"
  echo "=== C64 [${LABEL}/${label}] req=${rc} $(date +%T) ==="
  $AIPERF profile --model "$MODEL" --streaming --endpoint-type chat \
    --tokenizer "$TOKENIZER" $URL \
    --concurrency 64 --request-count "$rc" \
    --ui simple --isl 128 --osl 256 \
    --extra-inputs ignore_eos:true --extra-inputs min_tokens:256 \
    --output-artifact-dir "$outdir" > "$outdir/run.log" 2>&1
  local csv="$outdir/profile_export_aiperf.csv"
  if [ -f "$csv" ]; then
    tps=$(grep -i '^Output Token Throughput' "$csv" | tail -1 | cut -d, -f2)
    echo "  TPS=${tps}"
    echo "${tps}" >> "$BASE/results.txt"
  else
    echo "  NO CSV"
    echo "0" >> "$BASE/results.txt"
  fi
}

run_point warmup 30
for i in $(seq 1 "$RUNS"); do
  run_point "run${i}" 300
done

echo "=== ${LABEL} DONE: $BASE ==="
echo "Results: $(cat "$BASE/results.txt" | tail -n +2 | tr '\n' ' ')"
