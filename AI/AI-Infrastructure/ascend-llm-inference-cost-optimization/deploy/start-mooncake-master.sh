#!/usr/bin/env bash
set -euo pipefail
export LD_LIBRARY_PATH=/usr/local/lib:/usr/local/lib64:/usr/local/Ascend/cann-9.0.0/aarch64-linux/lib64:/usr/local/Ascend/driver/lib64:${LD_LIBRARY_PATH:-}
exec mooncake_master \
  --port 50088 \
  --eviction_high_watermark_ratio 0.90 \
  --eviction_ratio 0.10 \
  --default_kv_lease_ttl 60000 \
  --logtostderr
