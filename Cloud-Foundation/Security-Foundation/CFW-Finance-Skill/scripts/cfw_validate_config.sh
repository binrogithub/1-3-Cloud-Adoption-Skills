#!/bin/bash
# CFW Finance Skill - Validate Configuration
# Validates all CFW configuration against financial compliance gates

set -euo pipefail

# Parse arguments
REGION=""
FW_INSTANCE_ID=""
OBJECT_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --region=*) REGION="${1#*=}"; shift ;;
        --fw-instance-id=*) FW_INSTANCE_ID="${1#*=}"; shift ;;
        --object-id=*) OBJECT_ID="${1#*=}"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
done

if [ -z "$REGION" ] || [ -z "$FW_INSTANCE_ID" ] || [ -z "$OBJECT_ID" ]; then
    echo "❌ Error: --region, --fw-instance-id, and --object-id are required"
    echo "Usage: bash cfw_validate_config.sh --region=<region> --fw-instance-id=<id> --object-id=<id>"
    exit 1
fi

echo "============================================"
echo "CFW Finance Skill - Configuration Validation"
echo "============================================"
echo ""

PASSED=0
FAILED=0

check_gate() {
    local gate_num="$1"
    local gate_name="$2"
    local result="$3"
    local expected="$4"
    
    if [ "$result" = "$expected" ]; then
        echo "  G${gate_num}: ✅ PASS - $gate_name ($result)"
        PASSED=$((PASSED + 1))
    else
        echo "  G${gate_num}: ❌ FAIL - $gate_name (got: $result, expected: $expected)"
        FAILED=$((FAILED + 1))
    fi
}

# G1: CFW instance running
echo "[Validation] Checking CFW instance status..."
FW_STATUS=$(hcloud CFW ListFirewallDetail \
    --cli-region="$REGION" \
    --limit="10" \
    --offset="0" \
    --service_type="0" 2>/dev/null | \
    python3 -c "import sys,json; d=json.load(sys.stdin); records=d.get('data',{}).get('records',[]); print(records[0].get('status','')) if records else print('')" 2>/dev/null || echo "0")
check_gate 1 "CFW instance running" "$FW_STATUS" "2"

# G2: ACL rules present
echo "[Validation] Checking ACL rules..."
ACL_COUNT=$(hcloud CFW ListAclRules \
    --cli-region="$REGION" \
    --fw_instance_id="$FW_INSTANCE_ID" \
    --object_id="$OBJECT_ID" \
    --limit="100" \
    --offset="0" 2>/dev/null | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('total',0))" 2>/dev/null || echo "0")
if [ "$ACL_COUNT" -ge 3 ]; then
    echo "  G2: ✅ PASS - ACL rules present ($ACL_COUNT rules)"
    PASSED=$((PASSED + 1))
else
    echo "  G2: ❌ FAIL - ACL rules insufficient (got: $ACL_COUNT, expected: >=3)"
    FAILED=$((FAILED + 1))
fi

# G3: IPS protection mode
echo "[Validation] Checking IPS protection mode..."
IPS_MODE=$(hcloud CFW ListIpsProtectMode \
    --cli-region="$REGION" \
    --object_id="$OBJECT_ID" 2>/dev/null | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('mode',0))" 2>/dev/null || echo "0")
check_gate 3 "IPS strict protection mode" "$IPS_MODE" "1"

# G4 & G5: IPS switch status
echo "[Validation] Checking IPS switch status..."
IPS_SWITCH=$(hcloud CFW ListIpsSwitchStatus \
    --cli-region="$REGION" \
    --fw_instance_id="$FW_INSTANCE_ID" \
    --object_id="$OBJECT_ID" 2>/dev/null)

BASIC_DEFENSE=$(echo "$IPS_SWITCH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('basic_defense_status',0))" 2>/dev/null || echo "0")
VIRTUAL_PATCH=$(echo "$IPS_SWITCH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('virtual_patches_status',0))" 2>/dev/null || echo "0")

check_gate 4 "Virtual patching enabled" "$VIRTUAL_PATCH" "1"
check_gate 5 "Basic defense enabled" "$BASIC_DEFENSE" "1"

# G6: LTS logging
echo "[Validation] Checking LTS logging..."
LTS_STATUS=$(hcloud CFW ListLogConfig \
    --cli-region="$REGION" \
    --fw_instance_id="$FW_INSTANCE_ID" 2>/dev/null | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('lts_enable',0))" 2>/dev/null || echo "0")
check_gate 6 "LTS logging enabled" "$LTS_STATUS" "1"

# G7, G8, G9: Alarm configuration
echo "[Validation] Checking alarm configuration..."
ALARM_CONFIG=$(hcloud CFW ShowAlarmConfig \
    --cli-region="$REGION" \
    --fw_instance_id="$FW_INSTANCE_ID" 2>/dev/null)

ATTACK_ALARM=$(echo "$ALARM_CONFIG" | python3 -c "import sys,json; configs=json.load(sys.stdin).get('alarm_configs',[]); print(next((c.get('enable_status',0) for c in configs if c.get('alarm_type')==0),0))" 2>/dev/null || echo "0")
BW_ALARM=$(echo "$ALARM_CONFIG" | python3 -c "import sys,json; configs=json.load(sys.stdin).get('alarm_configs',[]); print(next((c.get('enable_status',0) for c in configs if c.get('alarm_type')==1),0))" 2>/dev/null || echo "0")
RES_ALARM=$(echo "$ALARM_CONFIG" | python3 -c "import sys,json; configs=json.load(sys.stdin).get('alarm_configs',[]); print(next((c.get('enable_status',0) for c in configs if c.get('alarm_type')==2),0))" 2>/dev/null || echo "0")

check_gate 7 "Attack alarms enabled" "$ATTACK_ALARM" "1"
check_gate 8 "Bandwidth alarms enabled" "$BW_ALARM" "1"
check_gate 9 "Resource alarms enabled" "$RES_ALARM" "1"

# Summary
TOTAL=$((PASSED + FAILED))
echo ""
echo "============================================"
echo "Validation Summary: $PASSED/$TOTAL gates passed"
if [ "$FAILED" -eq 0 ]; then
    echo "✅ ALL GATES PASSED - CFW meets finance compliance"
else
    echo "❌ $FAILED gate(s) failed - remediation required"
fi
echo "============================================"

exit $FAILED
