#!/bin/bash
# CFW Finance Skill - Apply Finance-Specific ACL Rules
# Creates standard banking ACL rules on an existing CFW instance

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
    echo "Usage: bash cfw_finance_acl_rules.sh --region=<region> --fw-instance-id=<id> --object-id=<id>"
    exit 1
fi

echo "============================================"
echo "CFW Finance Skill - Apply Finance ACL Rules"
echo "============================================"
echo ""

# Common parameters
COMMON="--cli-region=$REGION --fw_instance_id=$FW_INSTANCE_ID --object_id=$OBJECT_ID --type=0"

# Rule 1: HTTPS Banking Access (Inbound)
echo "[1/5] Adding HTTPS Banking Access rule..."
R1=$(hcloud CFW AddAclRule $COMMON \
    --rules.1.name="Finance-Inbound-HTTPS-Allow" \
    --rules.1.address_type="0" \
    --rules.1.direction="0" \
    --rules.1.status="1" \
    --rules.1.action_type="0" \
    --rules.1.long_connect_enable="0" \
    --rules.1.source.type="0" \
    --rules.1.source.address="0.0.0.0/0" \
    --rules.1.destination.type="0" \
    --rules.1.destination.address="0.0.0.0/0" \
    --rules.1.service.type="0" \
    --rules.1.service.protocol="6" \
    --rules.1.service.source_port="1-65535" \
    --rules.1.service.dest_port="443" \
    --rules.1.sequence.top="1" 2>&1)

if echo "$R1" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('data',{}).get('rules',[])" 2>/dev/null; then
    echo "  ✅ Finance-Inbound-HTTPS-Allow created"
else
    echo "  ❌ Failed: $R1"
fi

# Rule 2: HTTP Redirect (Inbound)
echo "[2/5] Adding HTTP Redirect rule..."
R2=$(hcloud CFW AddAclRule $COMMON \
    --rules.1.name="Finance-Inbound-HTTP-Redirect-Allow" \
    --rules.1.address_type="0" \
    --rules.1.direction="0" \
    --rules.1.status="1" \
    --rules.1.action_type="0" \
    --rules.1.long_connect_enable="0" \
    --rules.1.source.type="0" \
    --rules.1.source.address="0.0.0.0/0" \
    --rules.1.destination.type="0" \
    --rules.1.destination.address="0.0.0.0/0" \
    --rules.1.service.type="0" \
    --rules.1.service.protocol="6" \
    --rules.1.service.source_port="1-65535" \
    --rules.1.service.dest_port="80" \
    --rules.1.sequence.top="1" 2>&1)

if echo "$R2" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('data',{}).get('rules',[])" 2>/dev/null; then
    echo "  ✅ Finance-Inbound-HTTP-Redirect-Allow created"
else
    echo "  ❌ Failed: $R2"
fi

# Rule 3: DNS Resolution (Outbound)
echo "[3/5] Adding DNS Resolution rule..."
R3=$(hcloud CFW AddAclRule $COMMON \
    --rules.1.name="Finance-Outbound-DNS-Allow" \
    --rules.1.address_type="0" \
    --rules.1.direction="1" \
    --rules.1.status="1" \
    --rules.1.action_type="0" \
    --rules.1.long_connect_enable="0" \
    --rules.1.source.type="0" \
    --rules.1.source.address="0.0.0.0/0" \
    --rules.1.destination.type="0" \
    --rules.1.destination.address="0.0.0.0/0" \
    --rules.1.service.type="0" \
    --rules.1.service.protocol="17" \
    --rules.1.service.source_port="1-65535" \
    --rules.1.service.dest_port="53" \
    --rules.1.sequence.top="1" 2>&1)

if echo "$R3" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('data',{}).get('rules',[])" 2>/dev/null; then
    echo "  ✅ Finance-Outbound-DNS-Allow created"
else
    echo "  ❌ Failed: $R3"
fi

# Rule 4: NTP Time Sync (Outbound)
echo "[4/5] Adding NTP Time Sync rule..."
R4=$(hcloud CFW AddAclRule $COMMON \
    --rules.1.name="Finance-Outbound-NTP-Allow" \
    --rules.1.address_type="0" \
    --rules.1.direction="1" \
    --rules.1.status="1" \
    --rules.1.action_type="0" \
    --rules.1.long_connect_enable="0" \
    --rules.1.source.type="0" \
    --rules.1.source.address="0.0.0.0/0" \
    --rules.1.destination.type="0" \
    --rules.1.destination.address="0.0.0.0/0" \
    --rules.1.service.type="0" \
    --rules.1.service.protocol="17" \
    --rules.1.service.source_port="1-65535" \
    --rules.1.service.dest_port="123" \
    --rules.1.sequence.top="1" 2>&1)

if echo "$R4" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('data',{}).get('rules',[])" 2>/dev/null; then
    echo "  ✅ Finance-Outbound-NTP-Allow created"
else
    echo "  ❌ Failed: $R4"
fi

# Rule 5: Block Telnet (Inbound)
echo "[5/5] Adding Telnet Deny rule..."
R5=$(hcloud CFW AddAclRule $COMMON \
    --rules.1.name="Finance-Inbound-Telnet-Deny" \
    --rules.1.address_type="0" \
    --rules.1.direction="0" \
    --rules.1.status="1" \
    --rules.1.action_type="1" \
    --rules.1.long_connect_enable="0" \
    --rules.1.source.type="0" \
    --rules.1.source.address="0.0.0.0/0" \
    --rules.1.destination.type="0" \
    --rules.1.destination.address="0.0.0.0/0" \
    --rules.1.service.type="0" \
    --rules.1.service.protocol="6" \
    --rules.1.service.source_port="1-65535" \
    --rules.1.service.dest_port="23" \
    --rules.1.sequence.top="1" 2>&1)

if echo "$R5" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('data',{}).get('rules',[])" 2>/dev/null; then
    echo "  ✅ Finance-Inbound-Telnet-Deny created"
else
    echo "  ❌ Failed: $R5"
fi

echo ""
echo "============================================"
echo "✅ Finance ACL rules applied"
echo "============================================"
