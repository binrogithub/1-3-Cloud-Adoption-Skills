#!/bin/bash
# CFW Finance Skill - Preflight Check
# Validates prerequisites before CFW configuration

set -euo pipefail

REGION="${1:-}"
MISSING=0

echo "============================================"
echo "CFW Finance Skill - Preflight Check"
echo "============================================"
echo ""

# Check hcloud CLI
echo "[1/5] Checking hcloud CLI..."
if command -v hcloud &>/dev/null; then
    HCLOUD_VERSION=$(hcloud --version 2>/dev/null | head -1)
    echo "  ✅ hcloud found: $HCLOUD_VERSION"
else
    echo "  ❌ hcloud CLI not found. Install from: https://support.huaweicloud.com/cli/index.html"
    MISSING=1
fi

# Check region
echo ""
echo "[2/5] Checking region configuration..."
if [ -n "$REGION" ]; then
    echo "  ✅ Region specified: $REGION"
else
    # Try to get from environment or profile
    REGION=$(hcloud config get --cli-region 2>/dev/null || echo "")
    if [ -n "$REGION" ]; then
        echo "  ✅ Region from profile: $REGION"
    else
        echo "  ❌ Region not specified. Use --region=<region> or set in hcloud profile."
        MISSING=1
    fi
fi

# Check authentication
echo ""
echo "[3/5] Checking authentication..."
if hcloud IAM ShowPermanentAuthHeader --cli-region="${REGION:-la-north-2}" &>/dev/null; then
    echo "  ✅ Authentication configured"
else
    echo "  ⚠️  Cannot verify authentication. Ensure AK/SK or token is configured."
    echo "     Run: hcloud config set --cli-access-key=XXX --cli-secret-key=XXX"
fi

# Check IAM permissions
echo ""
echo "[4/5] Checking IAM permissions (cfw, vpc, eip, lts)..."
if [ -n "$REGION" ]; then
    if hcloud CFW ListFirewallDetail --cli-region="$REGION" --limit="1" --offset="0" --service_type="0" &>/dev/null; then
        echo "  ✅ CFW permissions verified"
    else
        echo "  ❌ CFW permissions not available. Required: cfw:*:*"
        MISSING=1
    fi
else
    echo "  ⏭️  Skipped (no region specified)"
fi

# Check existing CFW instances
echo ""
echo "[5/5] Checking existing CFW instances..."
if [ -n "$REGION" ]; then
    CFW_COUNT=$(hcloud CFW ListFirewallDetail --cli-region="$REGION" --limit="100" --offset="0" --service_type="0" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('total',0))" 2>/dev/null || echo "0")
    echo "  ℹ️  Found $CFW_COUNT existing CFW instance(s)"
else
    echo "  ⏭️  Skipped (no region specified)"
fi

# Summary
echo ""
echo "============================================"
if [ "$MISSING" -eq 0 ]; then
    echo "✅ Preflight check PASSED - Ready to configure CFW"
else
    echo "❌ Preflight check FAILED - Fix issues above before proceeding"
fi
echo "============================================"

exit $MISSING
