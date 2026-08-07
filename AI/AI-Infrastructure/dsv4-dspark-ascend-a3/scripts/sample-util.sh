#!/usr/bin/env bash
# NPU/CPU/mem utilization sampler. Run on the inference host in background.
# Usage: sample-util.sh <tag> <interval_sec>
# Output: /tmp/util-<tag>.log
# Row: epoch ts ai0 hbm0 ai1 hbm1 ... ai15 hbm15 cpu_busy% mem_used_mb mem_total_mb
TAG="${1:-default}"
INTERVAL="${2:-2}"
LOG="/tmp/util-${TAG}.log"

{
  echo "# sample-util start tag=$TAG interval=${INTERVAL}s host=$(hostname) date=$(date -Iseconds)"
  echo "# cols: epoch ts ai0 hbm0 ai1 hbm1 ... ai15 hbm15 cpu_busy% mem_used_mb mem_total_mb"
  while true; do
    EPOCH=$(date +%s)
    TS=$(date -Iseconds)
    NPU=$(npu-smi info 2>/dev/null | grep "0000:" | python3 -c '
import sys, re
out=[]
for line in sys.stdin:
    cols=line.split("|")
    if len(cols)<4: continue
    body=cols[3].strip()
    toks=body.split()
    ai=toks[0] if toks else "0"
    # hbm: match "X / 65536" or "X/ 65536" -> X is the used MB
    m=re.search(r"(\d+)\s*/\s*65536", body)
    hbm=m.group(1) if m else "0"
    out.append(ai); out.append(hbm)
print(" ".join(out))
')
    CPU_LINE=$(top -bn1 2>/dev/null | grep '^%Cpu')
    CPU_IDLE=$(echo "$CPU_LINE" | sed -n 's/.*,\s*\([0-9.]*\) id.*/\1/p')
    CPU_BUSY=$(awk "BEGIN{printf \"%.1f\", 100 - (${CPU_IDLE:-0})}")
    read MEM_TOTAL MEM_USED < <(awk '/MemTotal/{t=$2} /MemFree/{f=$2} END{print t, t-f}' /proc/meminfo)
    MEM_USED_MB=$((MEM_USED / 1024)); MEM_TOTAL_MB=$((MEM_TOTAL / 1024))
    echo "$EPOCH $TS ${NPU} ${CPU_BUSY} ${MEM_USED_MB} ${MEM_TOTAL_MB}"
    sleep "$INTERVAL"
  done
} >> "$LOG" 2>&1
