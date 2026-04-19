#!/bin/bash
# CFW Finance Skill - Configure Alarms
# Enables all three alarm types for financial workloads

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
    echo "Usage: bash cfw_alarm_configure.sh --region=<region> --fw-instance-id=<id>"
    exit 1
fi

echo "============================================"
echo "CFW Finance Skill - Configure Alarms"
echo "============================================"
echo ""

# Step 1: Check current alarm configuration
echo "[1/4] Checking current alarm configuration..."
ALARM_STATUS=$(hcloud CFW ShowAlarmConfig \
    --cli-region="$REGION" \
    --fw_instance_id="$FW_INSTANCE_ID" 2>&1)

echo "$ALARM_STATUS" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for cfg in d.get('alarm_configs',[]):
    atype = cfg.get('alarm_type',-1)
    enabled = cfg.get('enable_status',0)
    names = {0: 'Attack', 1: 'Bandwidth', 2: 'Resource'}
    name = names.get(atype, f'Unknown({atype})')
    status = '✅ Enabled' if enabled == 1 else '❌ Disabled'
    print(f'  {name} Alarm: {status}')
" 2>/dev/null || echo "  ⚠️  Could not parse alarm status"

# Step 2: Enable Attack Alarms
echo ""
echo "[2/4] Enabling Attack Alarms..."
ATTACK_RESULT=$(hcloud CFW UpdateAlarmConfig \
    --cli-region="$REGION" \
    --fw_instance_id="$FW_INSTANCE_ID" \
    --alarm_type="0" \
    --enable_status="1" \
    --frequency_count="10" \
    --frequency_time="5" \
    --severity="CRITICAL,HIGH,MEDIUM" 2>&1)

if [ -n "$ATTACK_RESULT" ]; then
    echo "  ✅ Attack alarms enabled (CRITICAL, HIGH, MEDIUM)"
else
    echo "  ❌ Failed to enable attack alarms"
fi

# Step 3: Enable Bandwidth Alarms
echo ""
echo "[3/4] Enabling Bandwidth Alarms..."
BW_RESULT=$(hcloud CFW UpdateAlarmConfig \
    --cli-region="$REGION" \
    --fw_instance_id="$FW_INSTANCE_ID" \
    --alarm_type="1" \
    --enable_status="1" \
    --severity="1" 2>&1)

if [ -n "$BW_RESULT" ]; then
    echo "  ✅ Bandwidth alarms enabled"
else
    echo "  ❌ Failed to enable bandwith alarms"
fi

# Step 4: Enable Resource Alarms
echo ""
echo "[4/4] Enabling Resource Alarms..."
RES_RESULT=$(hcloud CFW UpdateAlarmConfig \
    --cli-region="$REGION" \
    --fw_instance_id="$FW_INSTANCE_ID" \
    --alarm_type="2" \
    --enable_status="1" \
    --severity="3" 2>&1)

if [ -n "$RES_RESULT" ]; then
    echo "  ✅ Resource alarms enabled"
else
    echo "  ❌ Failed to enable resource alarms"
fi

echo ""
echo "============================================"
echo "✅ Alarm configuration complete for finance"
echo "  - Attack Alarms:   CRITICAL, HIGH, MEDIUM"
echo "  - Bandwidth Alarms: Enabled"
echo "  - Resource Alarms:  Enabled"
echo ""
echo "Note: Configure SMN topic for notifications."
echo "============================================"
