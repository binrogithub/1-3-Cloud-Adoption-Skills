#!/usr/bin/env bash
# validate_e2e.sh — 12-step end-to-end validation for LiteLLM Huawei MaaS Proxy
# Usage: ./scripts/validate_e2e.sh
# Expects .env in the current directory or one directory up.

set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
PASS=0; FAIL=0; WARN=0

pass() { ((PASS++)); printf "${GREEN}✅ PASS${NC} — $1\n"; }
fail() { ((FAIL++)); printf "${RED}❌ FAIL${NC} — $1\n"; }
warn() { ((WARN++)); printf "${YELLOW}⚠️  WARN${NC} — $1\n"; }
step() { printf "\n${YELLOW}── Step $1 ──${NC}\n"; }

# ── Load environment ────────────────────────────────────────────
if [ -f .env ]; then
  set -a; source .env; set +a
elif [ -f ../.env ]; then
  set -a; source ../.env; set +a
else
  printf "${RED}ERROR: .env not found. Run from the project root.\n${NC}"; exit 1
fi

LITELLM_URL="${LITELLM_URL:-http://localhost:4000}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
MAAS_API_BASE="${HUAWEI_MAAS_API_BASE:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"

printf "${YELLOW}╔══════════════════════════════════════════════════════╗\n"
printf "║  LiteLLM Huawei MaaS Proxy — E2E Validation          ║\n"
printf "╚══════════════════════════════════════════════════════╝${NC}\n"

# ── Step 0: Preflight ──────────────────────────────────────────
step "0: Preflight"
if command -v docker &>/dev/null && docker --version &>/dev/null; then
  pass "Docker: $(docker --version | head -1)"
else
  fail "Docker not found"
fi
if docker compose version &>/dev/null; then
  pass "Docker Compose: $(docker compose version | head -1)"
else
  fail "Docker Compose V2 not found"
fi

# ── Step 1: .env check ─────────────────────────────────────────
step "1: .env completeness and permissions"
if [ -f .env ]; then
  pass ".env exists"
  PERMS=$(stat -c '%a' .env 2>/dev/null || stat -f '%Lp' .env 2>/dev/null)
  if [ "$PERMS" = "600" ]; then
    pass ".env permissions are 0600"
  else
    warn ".env permissions are $PERMS (expected 0600)"
  fi
  # Check required vars are not placeholders
  for VAR in LITELLM_MASTER_KEY LITELLM_SALT_KEY DB_PASSWORD HUAWEI_MAAS_API_KEY; do
    VAL="${!VAR:-}"
    if [ -z "$VAL" ] || echo "$VAL" | grep -qi 'change-me\|replace\|xxx'; then
      fail "$VAR is not set or still has a placeholder value"
    else
      pass "$VAR is set (len=${#VAL})"
    fi
  done
else
  fail ".env not found"
fi

# ── Step 2: Service health ─────────────────────────────────────
step "2: All services healthy"
if docker compose ps --format json 2>/dev/null | python3 -c "
import sys, json
services = [json.loads(l) for l in sys.stdin if l.strip()]
ok = all(s.get('Health','') == 'healthy' or s.get('Status','').startswith('Up') for s in services)
print('healthy' if ok and len(services) >= 4 else 'unhealthy', len(services))
" 2>/dev/null | read -r STATUS COUNT; then
  if [ "$STATUS" = "healthy" ]; then
    pass "All $COUNT services are healthy/running"
  else
    warn "$COUNT services found but not all healthy — check 'docker compose ps'"
  fi
else
  # Fallback for older docker compose
  RUNNING=$(docker compose ps --services --filter "status=running" 2>/dev/null | wc -l)
  if [ "$RUNNING" -ge 4 ]; then
    pass "$RUNNING services running"
  else
    fail "Only $RUNNING services running (expected 4)"
  fi
fi

# ── Step 3: Direct MaaS connectivity ───────────────────────────
step "3: Direct MaaS connectivity"
MAAS_RESP=$(curl -s --connect-timeout 10 -w '\n%{http_code}' "$MAAS_API_BASE/models" -H "Authorization: Bearer $HUAWEI_MAAS_API_KEY" 2>/dev/null)
MAAS_CODE=$(echo "$MAAS_RESP" | tail -1)
MAAS_BODY=$(echo "$MAAS_RESP" | sed '$d')
if [ "$MAAS_CODE" = "200" ]; then
  MODEL_COUNT=$(echo "$MAAS_BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('data',[])))" 2>/dev/null || echo "?")
  pass "MaaS API reachable — $MODEL_COUNT models listed"
else
  fail "MaaS API returned HTTP $MAAS_CODE (expected 200)"
fi

# ── Step 4: LiteLLM liveness ───────────────────────────────────
step "4: LiteLLM liveness"
LIVENESS=$(curl -s --connect-timeout 5 -w '%{http_code}' "$LITELLM_URL/health/liveliness" 2>/dev/null)
LIVENESS_CODE="${LIVENESS: -3}"
if [ "$LIVENESS_CODE" = "200" ]; then
  pass "LiteLLM liveness probe returned 200"
else
  fail "LiteLLM liveness probe returned $LIVENESS_CODE"
fi

# ── Step 5: Per-model health ───────────────────────────────────
step "5: Per-model health"
HEALTH_RESP=$(curl -s --connect-timeout 10 "$LITELLM_URL/health" -H "Authorization: Bearer $LITELLM_MASTER_KEY" 2>/dev/null)
HEALTH_OK=$(echo "$HEALTH_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('healthy_count',0))" 2>/dev/null || echo "?")
HEALTH_FAIL=$(echo "$HEALTH_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('unhealthy_count',0))" 2>/dev/null || echo "?")
if [ "$HEALTH_FAIL" = "0" ]; then
  pass "All models healthy ($HEALTH_OK healthy, $HEALTH_FAIL unhealthy)"
else
  warn "$HEALTH_OK healthy, $HEALTH_FAIL unhealthy — may be transient rate limits on health probes"
fi

# ── Step 6: Sync chat completion ───────────────────────────────
step "6: Sync chat completion"
CHAT_RESP=$(curl -s --connect-timeout 30 "$LITELLM_URL/v1/chat/completions" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"glm-5","messages":[{"role":"user","content":"Reply with OK only."}]}' 2>/dev/null)
CHAT_CONTENT=$(echo "$CHAT_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('choices',[{}])[0].get('message',{}).get('content',''))" 2>/dev/null || echo "")
if [ -n "$CHAT_CONTENT" ]; then
  pass "Chat completion returned: ${CHAT_CONTENT:0:50}"
else
  CHAT_ERR=$(echo "$CHAT_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); e=d.get('error',{}); print(e.get('message','unknown'))" 2>/dev/null || echo "parse error")
  fail "Chat completion failed: $CHAT_ERR"
fi

# ── Step 7: Streaming ──────────────────────────────────────────
step "7: Streaming chat completion"
STREAM_RESP=$(curl -s --connect-timeout 30 "$LITELLM_URL/v1/chat/completions" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v3.2","messages":[{"role":"user","content":"Count to 3."}],"stream":true}' 2>/dev/null | head -3)
if echo "$STREAM_RESP" | grep -q '^data:'; then
  pass "Streaming returned SSE chunks"
else
  fail "Streaming did not return SSE data"
fi

# ── Step 8: Prometheus metrics ─────────────────────────────────
step "8: Prometheus metrics from LiteLLM"
METRIC_COUNT=$(curl -sL --connect-timeout 5 "$LITELLM_URL/metrics" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" 2>/dev/null | grep -c 'litellm_' || echo "0")
if [ "$METRIC_COUNT" -gt 0 ] 2>/dev/null; then
  pass "LiteLLM metrics: $METRIC_COUNT litellm_ lines"
else
  fail "No litellm_ metrics found"
fi

# ── Step 9: Prometheus target ──────────────────────────────────
step "9: Prometheus target health"
PROM_HEALTH=$(curl -s --connect-timeout 5 "$PROMETHEUS_URL/api/v1/targets" 2>/dev/null | \
  python3 -c "import sys,json; d=json.load(sys.stdin); ts=d['data']['activeTargets']; print(ts[0]['health'] if ts else 'none')" 2>/dev/null || echo "error")
if [ "$PROM_HEALTH" = "up" ]; then
  pass "Prometheus target litellm is up"
else
  fail "Prometheus target health: $PROM_HEALTH (expected up)"
fi

# ── Step 10: Grafana ───────────────────────────────────────────
step "10: Grafana reachable"
GRAFANA_CODE=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 "$GRAFANA_URL" 2>/dev/null)
if [ "$GRAFANA_CODE" = "200" ] || [ "$GRAFANA_CODE" = "302" ]; then
  pass "Grafana returned HTTP $GRAFANA_CODE (reachable)"
else
  fail "Grafana returned HTTP $GRAFANA_CODE (expected 200 or 302)"
fi

# ── Step 11: Virtual key minting ───────────────────────────────
step "11: Virtual key generation"
KEY_RESP=$(curl -s --connect-timeout 10 -X POST "$LITELLM_URL/key/generate" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"models":["glm-5"],"max_budget":1.0,"duration":"1d"}' 2>/dev/null)
VK=$(echo "$KEY_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('key',''))" 2>/dev/null || echo "")
if [ -n "$VK" ] && echo "$VK" | grep -q '^sk-'; then
  pass "Virtual key minted: ${VK:0:10}...${VK: -4}"
else
  fail "Virtual key generation failed"
fi

# ── Summary ────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL + WARN))
printf "\n${YELLOW}══════════════════════════════════════════════════════${NC}\n"
printf "Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}, ${YELLOW}$WARN warnings${NC} out of $TOTAL checks\n"
if [ "$FAIL" -gt 0 ]; then
  printf "${RED}VALIDATION FAILED — $FAIL check(s) did not pass${NC}\n"
  exit 1
else
  printf "${GREEN}VALIDATION PASSED${NC}\n"
  exit 0
fi
