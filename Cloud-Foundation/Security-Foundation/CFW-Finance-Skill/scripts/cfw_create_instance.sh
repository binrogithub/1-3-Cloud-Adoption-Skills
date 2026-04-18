#!/bin/bash
# CFW Finance Skill - Create CFW Instance
# Creates a CFW instance with finance-appropriate defaults

set -euo pipefail

# Parse arguments
REGION=""
INSTANCE_NAME="cfw-finance-instance"
FLAVOR="Standard"

while [[ $# -gt 0 ]]; do
    case $1 in
        --region=*) REGION="${1#*=}"; shift ;;
        --name=*) INSTANCE_NAME="${1#*=}"; shift ;;
        --flavor=*) FLAVOR="${1#*=}"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
done

if [ -z "$REGION" ]; then
    echo "❌ Error: --region is required"
    echo "Usage: bash cfw_create_instance.sh --region=<region> [--name=<name>] [--flavor=<Standard|Professional>]"
    exit 1
fi

echo "============================================"
echo "CFW Finance Skill - Create CFW Instance"
echo "============================================"
echo "Region:        $REGION"
echo "Instance Name: $INSTANCE_NAME"
echo "Flavor:        $FLAVOR"
echo ""

# Create CFW instance
echo "[1/2] Creating CFW instance..."
RESPONSE=$(hcloud CFW CreateFirewall \
    --cli-region="$REGION" \
    --name="$INSTANCE_NAME" \
    --charge_info.charge_mode="postPaid" \
    --charge_info.is_auto_pay="false" \
    --charge_info.is_auto_renew="false" \
    --flavor.version="$FLAVOR" 2>&1)

echo "$RESPONSE"

# Extract job ID
JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('job_id',''))" 2>/dev/null || echo "")

if [ -n "$JOB_ID" ]; then
    echo ""
    echo "  ✅ Instance creation initiated. Job ID: $JOB_ID"
    echo ""
    echo "[2/2] Waiting for instance to become active..."
    sleep 10
    
    # Poll for instance status
    for i in {1..12}; do
        STATUS=$(hcloud CFW ListFirewallDetail \
            --cli-region="$REGION" \
            --limit="10" \
            --offset="0" \
            --service_type="0" 2>/dev/null | \
            python3 -c "import sys,json; d=json.load(sys.stdin); records=d.get('data',{}).get('records',[]); print(records[0].get('status','')) if records else print('')" 2>/dev/null || echo "")
        
        if [ "$STATUS" = "2" ]; then
            echo "  ✅ CFW instance is now running (status=2)"
            
            # Extract instance details
            hcloud CFW ListFirewallDetail \
                --cli-region="$REGION" \
                --limit="10" \
                --offset="0" \
                --service_type="0" 2>/dev/null | \
                python3 -c "
import sys, json
d = json.load(sys.stdin)
records = d.get('data',{}).get('records',[])
if records:
    r = records[0]
    print(f\"  Instance ID: {r.get('fw_instance_id','')}\")
    for po in r.get('protect_objects',[]):
        print(f\"  Object ID:   {po.get('object_id','')}\")
    print(f\"  Flavor:      {r.get('flavor',{}).get('version','')}\")
    print(f\"  IPv6:        {r.get('support_ipv6',False)}\")
    print(f\"  Time Zone:   {r.get('time_zone','')}\")
" 2>/dev/null || true
            break
        else
            echo "  ⏳ Waiting... (status=$STATUS, attempt $i/12)"
            sleep 10
        fi
    done
else
    echo "  ❌ Failed to create instance"
    exit 1
fi

echo ""
echo "============================================"
echo "✅ CFW instance creation complete"
echo "============================================"
