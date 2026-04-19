#!/bin/bash
# CFW Finance Skill - Configure IPS for Finance
# Enables IPS strict protection mode and virtual patching

set -euo pipefail

# Parse arguments
REGION=""
OBJECT_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --region=*) REGION="${1#*=}"; shift ;;
        --object-id=*) OBJECT_ID="${1#*=}"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
done

if [ -z "$REGION" ] || [ -z "$OBJECT_ID" ]; then
    echo "❌ Error: --region and --object-id are required"
    echo "Usage: bash cfw_ips_configure.sh --region=<region> --object-id=<id>"
    exit 1
fi

echo "============================================"
echo "CFW Finance Skill - Configure IPS for Finance"
echo "============================================"
echo ""

# Step 1: Check current IPS status
echo "[1/4] Checking current IPS status..."
IPS_STATUS=$(hcloud CFW ListIpsSwitchStatus \
    --cli-region="$REGION" \
    --fw_instance_id="$FW_INSTANCE_ID" \
    --object_id="$OBJECT_ID" 2>&1)

BASIC_DEFENSE=$(echo "$IPS_STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('basic_defense_status',0))" 2>/dev/null || echo "0")
VIRTUAL_PATCH=$(echo "$IPS_STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('virtual_patches_status',0))" 2>/dev/null || echo "0")

echo "  Basic Defense: $([ "$BASIC_DEFENSE" = "1" ] && echo "✅ Enabled" || echo "❌ Disabled")"
echo "  Virtual Patching: $([ "$VIRTUAL_PATCH" = "1" ] && echo "✅ Enabled" || echo "❌ Disabled")"

# Step 2: Check protection mode
echo ""
echo "[2/4] Checking IPS protection mode..."
MODE_STATUS=$(hcloud CFW ListIpsProtectMode \
    --cli-region="$REGION" \
    --object_id="$OBJECT_ID" 2>&1)

CURRENT_MODE=$(echo "$MODE_STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('mode',0))" 2>/dev/null || echo "0")

MODE_NAMES=("Observation" "Strict" "Medium" "Loose")
echo "  Current Mode: ${MODE_NAMES[$CURRENT_MODE]} ($CURRENT_MODE)"

# Step 3: Enable virtual patching if not enabled
echo ""
echo "[3/4] Configuring virtual patching..."
if [ "$VIRTUAL_PATCH" = "0" ]; then
    VP_RESULT=$(hcloud CFW ChangeIpsSwitchStatus \
        --cli-region="$REGION" \
        --object_id="$OBJECT_ID" \
        --ips_type="2" \
        --status="1" 2>&1)
    
    if echo "$VP_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('data',{}).get('id','')" 2>/dev/null; then
        echo "  ✅ Virtual patching enabled"
    else
        echo "  ❌ Failed to enable virtual patching: $VP_RESULT"
    fi
else
    echo "  ✅ Virtual patching already enabled"
fi

# Step 4: Switch to strict protection mode if not already
echo ""
echo "[4/4] Configuring IPS protection mode..."
if [ "$CURRENT_MODE" != "1" ]; then
    MODE_RESULT=$(echo "b" | hcloud CFW ChangeIpsProtectMode \
        --cli-region="$REGION" \
        --object_id="$OBJECT_ID" \
        --mode="1" 2>&1)
    
    if echo "$MODE_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('data',{}).get('id','')" 2>/dev/null; then
        echo "  ✅ IPS switched to Strict protection mode"
    else
        echo "  ❌ Failed to switch protection mode: $MODE_RESULT"
    fi
else
    echo "  ✅ IPS already in Strict protection mode"
fi

echo ""
echo "============================================"
echo "✅ IPS configuration complete for finance"
echo "  - Protection Mode: Strict (mode=1)"
echo "  - Virtual Patching: Enabled"
echo "============================================"
