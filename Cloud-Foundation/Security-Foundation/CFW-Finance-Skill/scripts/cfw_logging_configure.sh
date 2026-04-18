#!/bin/bash
# CFW Finance Skill - Configure LTS Logging
# Enables LTS logging for CFW with finance-grade retention

set -euo pipefail

# Parse arguments
REGION=""
FW_INSTANCE_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --region=*) REGION="${1#*=}"; shift ;;
        --fw-instance-id=*) FW_INSTANCE_ID="${1#*=}"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
done

if [ -z "$REGION" ] || [ -z "$FW_INSTANCE_ID" ]; then
    echo "❌ Error: --region and --fw-instance-id are required"
    echo "Usage: bash cfw_logging_configure.sh --region=<region> --fw-instance-id=<id>"
    exit 1
fi

echo "============================================"
echo "CFW Finance Skill - Configure LTS Logging"
echo "============================================"
echo ""

# Step 1: Check current log status
echo "[1/2] Checking current log configuration..."
LOG_STATUS=$(hcloud CFW ListLogConfig \
    --cli-region="$REGION" \
    --fw_instance_id="$FW_INSTANCE_ID" 2>&1)

LTS_ENABLE=$(echo "$LOG_STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('lts_enable',0))" 2>/dev/null || echo "0")

echo "  LTS Status: $([ "$LTS_ENABLE" = "1" ] && echo "✅ Enabled" || echo "❌ Disabled")"

# Step 2: Enable LTS if not enabled
echo ""
echo "[2/2] Configuring LTS logging..."
if [ "$LTS_ENABLE" = "0" ]; then
    LTS_RESULT=$(hcloud CFW AddLogConfig \
        --cli-region="$REGION" \
        --fw_instance_id="$FW_INSTANCE_ID" \
        --lts_enable="1" 2>&1)
    
    if echo "$LTS_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('data',{})" 2>/dev/null; then
        echo "  ✅ LTS logging enabled"
    else
        echo "  ❌ Failed to enable LTS: $LTS_RESULT"
    fi
else
    echo "  ✅ LTS logging already enabled"
fi

echo ""
echo "============================================"
echo "✅ LTS logging configuration complete"
echo ""
echo "Finance retention requirements:"
echo "  - Attack Logs:  365 days (LTS + OBS)"
echo "  - IPS Logs:     365 days (LTS + OBS)"
echo "  - ACL Logs:     180 days (LTS)"
echo "  - Flow Logs:     90 days (LTS)"
echo "  - System Logs:   90 days (LTS)"
echo ""
echo "Note: Configure OBS archival for 365-day"
echo "retention of attack and IPS logs."
echo "============================================"
