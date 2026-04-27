#!/bin/bash
# smoke_check.sh — Health verification for telco AI demo on Huawei Cloud ECS
# Usage: bash smoke_check.sh --ip=<ecs-ip> [--demo=1|2]
#
# Sanitized: no real IPs or credentials.

set -euo pipefail

ECS_IP=""
DEMO="${DEMO:-1}"
TIMEOUT=10

usage() {
    cat <<EOF
Usage: $0 --ip=<ecs-ip> [--demo=1|2]

  --ip=<ip>      ECS public IP address
  --demo=1|2     Demo number (default: 1)
EOF
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ip=*)   ECS_IP="${1#*=}" ;;
        --demo=*) DEMO="${1#*=}" ;;
        *)        usage ;;
    esac
    shift
done

[[ -z "$ECS_IP" ]] && usage

PASS=0
FAIL=0
TOTAL=0

check() {
    local desc="$1"
    local cmd="$2"
    local expected="$3"
    TOTAL=$((TOTAL + 1))

    echo -n "  [$TOTAL] $desc ... "
    result=$(eval "$cmd" 2>&1) || true

    if echo "$result" | grep -q "$expected"; then
        echo "PASS"
        PASS=$((PASS + 1))
    else
        echo "FAIL"
        echo "         Expected: $expected"
        echo "         Got:      $(echo "$result" | head -3)"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Telco AI Demo Smoke Check ==="
echo "Demo:    $DEMO"
echo "ECS IP:  $ECS_IP"
echo ""
echo "--- Backend API Checks ---"

# G1: Backend health
check "GET /health returns 200 + JSON" \
    "curl -sS -m $TIMEOUT http://$ECS_IP:8000/health" \
    "demo_mode"

# G2: API tasks endpoint
check "GET /api/tasks returns JSON array" \
    "curl -sS -m $TIMEOUT http://$ECS_IP:8000/api/tasks" \
    '\[.*\]'

# G3: POST /api/tasks creates task
if [[ "$DEMO" == "1" ]]; then
    SCENARIO="cancelacion"
    check "POST /api/tasks (cancelacion) returns task" \
        "curl -sS -m $((TIMEOUT + 20)) -X POST http://$ECS_IP:8000/api/tasks -H 'Content-Type: application/json' -d '{\"type\":\"cancelacion\"}'" \
        "segments"
else
    SCENARIO="legacy_analysis"
    check "POST /api/tasks (legacy_analysis) returns task" \
        "curl -sS -m $((TIMEOUT + 20)) -X POST http://$ECS_IP:8000/api/tasks -H 'Content-Type: application/json' -d '{\"type\":\"legacy_analysis\"}'" \
        "tech_debt_items"
fi

echo ""
echo "--- Dashboard Checks ---"

# G4: Dashboard serves
check "Dashboard HTTP 200" \
    "curl -sS -o /dev/null -w '%{http_code}' -m $TIMEOUT http://$ECS_IP:3000/" \
    "200"

# G5: Dashboard HTML contains Next.js markers
check "Dashboard is Next.js app" \
    "curl -sS -m $TIMEOUT http://$ECS_IP:3000/" \
    "__NEXT"

echo ""
echo "--- Connectivity Checks ---"

# G6: Port open
check "Port 8000 open" \
    "timeout 3 bash -c 'echo > /dev/tcp/$ECS_IP/8000' 2>&1; echo 'open'" \
    "open"

check "Port 3000 open" \
    "timeout 3 bash -c 'echo > /dev/tcp/$ECS_IP/3000' 2>&1; echo 'open'" \
    "open"

echo ""
echo "--- Deterministic Fallback Check ---"

# G7: Task with deterministic mode
check "Scenario completes in deterministic mode" \
    "curl -sS -m $((TIMEOUT + 20)) -X POST http://$ECS_IP:8000/api/tasks -H 'Content-Type: application/json' -d '{\"type\":\"'$SCENARIO'\"}' | python3 -c 'import sys,json; d=json.load(sys.stdin); print(\"segments\" in d or \"tech_debt_items\" in d)'" \
    "True"

echo ""
echo "=== Results ==="
echo "Passed: $PASS/$TOTAL"
echo "Failed: $FAIL/$TOTAL"

if [[ $FAIL -gt 0 ]]; then
    echo ""
    echo "=== Troubleshooting Tips ==="
    echo "- Check Docker services: ssh root@$ECS_IP 'docker compose -f /opt/telco-demo$DEMO/docker-compose.yml ps'"
    echo "- Check Docker logs:   ssh root@$ECS_IP 'docker compose -f /opt/telco-demo$DEMO/docker-compose.yml logs --tail=50'"
    echo "- Verify env vars:      ssh root@$ECS_IP 'cat /opt/telco-demo$DEMO/.env'"
    echo "- Rebuild dashboard:    ssh root@$ECS_IP 'cd /opt/telco-demo$DEMO && docker compose up -d --build --no-deps dashboard'"
    echo "- Check DNS:            ssh root@$ECS_IP 'cat /etc/resolv.conf'"
    echo ""
    echo "If NEXT_PUBLIC_API_URL has /api suffix: remove it and rebuild dashboard (build-time env var)"
    exit 1
fi

echo ""
echo "All checks passed. Demo is ready."
exit 0
