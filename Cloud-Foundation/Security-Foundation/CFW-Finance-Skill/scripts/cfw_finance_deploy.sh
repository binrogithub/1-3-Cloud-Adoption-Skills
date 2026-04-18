#!/bin/bash
# CFW Finance Skill - Full Deployment
# One-command deployment of CFW with finance-grade configuration

set -euo pipefail

# Parse arguments
REGION=""
FW_INSTANCE_ID=""
OBJECT_ID=""
SKIP_ACL=false
SKIP_IPS=false
SKIP_LOGGING=false
SKIP_ALARM=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --region=*) REGION="${1#*=}"; shift ;;
        --fw-instance-id=*) FW_INSTANCE_ID="${1#*=}"; shift ;;
        --object-id=*) OBJECT_ID="${1#*=}"; shift ;;
        --skip-acl) SKIP_ACL=true; shift ;;
        --skip-ips) SKIP_IPS=true; shift ;;
        --skip-logging) SKIP_LOGGING=true; shift ;;
        --skip-alarm) SKIP_ALARM=true; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
done

if [ -z "$REGION" ] || [ -z "$FW_INSTANCE_ID" ] || [ -z "$OBJECT_ID" ]; then
    echo "❌ Error: --region, --fw-instance-id, and --object-id are required"
    echo "Usage: bash cfw_finance_deploy.sh --region=<region> --fw-instance-id=<id> --object-id=<id>"
    echo "  [--skip-acl] [--skip-ips] [--skip-logging] [--skip-alarm]"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================"
echo "CFW Finance Skill - Full Deployment"
echo "============================================"
echo "Region:         $REGION"
echo "FW Instance ID: $FW_INSTANCE_ID"
echo "Object ID:      $OBJECT_ID"
echo ""

# Step 1: Preflight check
echo "=========================================="
echo "Step 1/6: Preflight Check"
echo "=========================================="
bash "$SCRIPT_DIR/cfw_preflight_check.sh" "$REGION" || true
echo ""

# Step 2: ACL Rules
if [ "$SKIP_ACL" = false ]; then
    echo "=========================================="
    echo "Step 2/6: Apply Finance ACL Rules"
    echo "=========================================="
    bash "$SCRIPT_DIR/cfw_finance_acl_rules.sh" \
        --region="$REGION" \
        --fw-instance-id="$FW_INSTANCE_ID" \
        --object-id="$OBJECT_ID"
    echo ""
else
    echo "⏭️  Step 2/6: ACL Rules (skipped)"
fi

# Step 3: IPS Configuration
if [ "$SKIP_IPS" = false ]; then
    echo "=========================================="
    echo "Step 3/6: Configure IPS for Finance"
    echo "=========================================="
    bash "$SCRIPT_DIR/cfw_ips_configure.sh" \
        --region="$REGION" \
        --object-id="$OBJECT_ID"
    echo ""
else
    echo "⏭️  Step 3/6: IPS Configuration (skipped)"
fi

# Step 4: Logging Configuration
if [ "$SKIP_LOGGING" = false ]; then
    echo "=========================================="
    echo "Step 4/6: Configure LTS Logging"
    echo "=========================================="
    bash "$SCRIPT_DIR/cfw_logging_configure.sh" \
        --region="$REGION" \
        --fw-instance-id="$FW_INSTANCE_ID"
    echo ""
else
    echo "⏭️  Step 4/6: Logging Configuration (skipped)"
fi

# Step 5: Alarm Configuration
if [ "$SKIP_ALARM" = false ]; then
    echo "=========================================="
    echo "Step 5/6: Configure Alarms"
    echo "=========================================="
    bash "$SCRIPT_DIR/cfw_alarm_configure.sh" \
        --region="$REGION" \
        --fw-instance-id="$FW_INSTANCE_ID"
    echo ""
else
    echo "⏭️  Step 5/6: Alarm Configuration (skipped)"
fi

# Step 6: Validation
echo "=========================================="
echo "Step 6/6: Validate Configuration"
echo "=========================================="
bash "$SCRIPT_DIR/cfw_validate_config.sh" \
    --region="$REGION" \
    --fw-instance-id="$FW_INSTANCE_ID" \
    --object-id="$OBJECT_ID"
echo ""

echo "============================================"
echo "✅ CFW Finance deployment complete"
echo "============================================"
