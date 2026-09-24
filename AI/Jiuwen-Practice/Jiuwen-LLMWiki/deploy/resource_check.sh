#!/usr/bin/env bash
# E9-S8 / NFR-4: LLMWiki footprint vs the 4 GiB budget and the neighbours'
# 3 GiB headroom. Exit 1 when the budget is blown.
set -uo pipefail
mb() { awk -v kb="$1" 'BEGIN{printf "%.0f", kb/1024}'; }
LLM=$(docker stats --no-stream --format '{{.MemUsage}}' llmwiki_pg llmwiki_embed 2>/dev/null \
      | grep -oE '^[0-9.]+' | paste -sd+ | bc); LLM=${LLM:-0}
JSW=$(ps -eo rss,args --no-headers | grep -F -- '--dotenv /root/HuaweiCloudLatam_LLMWiki/runtime/jiuwen' \
      | grep -v grep | awk '{s+=$1} END {print s+0}')
WEB=$(ps -eo rss,args --no-headers | grep -F 'llmwiki.cli serve' | grep -v grep | awk '{s+=$1} END {print s+0}')
TOTAL=$(awk -v c="${LLM:-0}" -v j="$(mb "${JSW:-0}")" -v w="$(mb "${WEB:-0}")" 'BEGIN{printf "%.0f", c+j+w}')
AVAIL=$(free -m | awk '/^Mem:/{print $7}')
echo "llmwiki containers: ${LLM:-0} MiB; jiuwen instance: $(mb "${JSW:-0}") MiB; web: $(mb "${WEB:-0}") MiB; total ~= $TOTAL MiB (budget 4096)"
echo "available for neighbours: $AVAIL MiB (must stay >= 3072)"
[ "$TOTAL" -le 4096 ] && [ "$AVAIL" -ge 3072 ]
