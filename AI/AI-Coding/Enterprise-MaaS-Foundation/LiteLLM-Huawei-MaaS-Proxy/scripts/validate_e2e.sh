#!/usr/bin/env bash
# validate_e2e.sh — End-to-end validation for LiteLLM Huawei MaaS Proxy
# Usage: ./scripts/validate_e2e.sh  (can be run from any directory)

set -euo pipefail

# ── Resolve project root (script is in scripts/ subdirectory) ─────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ── Colors ──────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
PASS=0; FAIL=0; WARN=0

pass() { PASS=$((PASS + 1)); printf "${GREEN}✅ PASS${NC} — $1\n"; }
fail() { FAIL=$((FAIL + 1)); printf "${RED}❌ FAIL${NC} — $1\n"; }
warn() { WARN=$((WARN + 1)); printf "${YELLOW}⚠️  WARN${NC} — $1\n"; }
step() { printf "\n${YELLOW}── Step $1 ──${NC}\n"; }

# ── Load environment ────────────────────────────────────────────
if [ -f .env ]; then
  set -a; source .env; set +a
else
  printf "${RED}ERROR: .env not found in $PROJECT_ROOT\n${NC}"; exit 1
fi

LITELLM_URL="${LITELLM_URL:-http://localhost:4000}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
MAAS_API_BASE="${HUAWEI_MAAS_API_BASE:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"
KEY_COUNT="${HUAWEI_MAAS_API_KEY_COUNT:-1}"

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
step "1: .env completeness, permissions, and multi-key"
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

  # Multi-key checks
  if [ -n "${HUAWEI_MAAS_API_KEY_COUNT:-}" ]; then
    pass "HUAWEI_MAAS_API_KEY_COUNT = $HUAWEI_MAAS_API_KEY_COUNT"
    if [ "$HUAWEI_MAAS_API_KEY_COUNT" -lt 1 ] 2>/dev/null; then
      fail "HUAWEI_MAAS_API_KEY_COUNT must be >= 1"
    fi
  else
    warn "HUAWEI_MAAS_API_KEY_COUNT not set (defaulting to 1)"
  fi

  # Check each individual key
  for i in $(seq 0 $((KEY_COUNT - 1))); do
    VAR="HUAWEI_MAAS_API_KEY_$i"
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
HEALTH_OUTPUT=$(docker compose ps --format json 2>/dev/null | python3 -c "
import sys, json
services = [json.loads(l) for l in sys.stdin if l.strip()]
ok = all(s.get('Health','') == 'healthy' or s.get('Status','').startswith('Up') for s in services)
print('healthy' if ok and len(services) >= 4 else 'unhealthy', len(services))
" 2>/dev/null) || HEALTH_OUTPUT=""
if [ -n "$HEALTH_OUTPUT" ]; then
  read -r STATUS COUNT <<< "$HEALTH_OUTPUT"
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

# ── Step 3: Direct MaaS connectivity (per key) ─────────────────
step "3: Direct MaaS connectivity (per key)"
KEYS_OK=0
KEYS_FAIL=0
for i in $(seq 0 $((KEY_COUNT - 1))); do
  VAR="HUAWEI_MAAS_API_KEY_$i"
  KEY_VAL="${!VAR:-}"
  if [ -z "$KEY_VAL" ]; then
    fail "MaaS API key $i ($VAR) is not set"
    KEYS_FAIL=$((KEYS_FAIL + 1))
    continue
  fi
  MAAS_RESP=$(curl -s --connect-timeout 10 -w '\n%{http_code}' "$MAAS_API_BASE/models" -H "Authorization: Bearer $KEY_VAL" 2>/dev/null)
  MAAS_CODE=$(echo "$MAAS_RESP" | tail -1)
  MAAS_BODY=$(echo "$MAAS_RESP" | sed '$d')
  if [ "$MAAS_CODE" = "200" ]; then
    MODEL_COUNT=$(echo "$MAAS_BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('data',[])))" 2>/dev/null || echo "?")
    pass "MaaS API key $i reachable — $MODEL_COUNT models listed"
    KEYS_OK=$((KEYS_OK + 1))
  else
    fail "MaaS API key $i returned HTTP $MAAS_CODE (expected 200)"
    KEYS_FAIL=$((KEYS_FAIL + 1))
  fi
done
if [ "$KEYS_OK" -eq 0 ]; then
  fail "No MaaS API keys are reachable"
elif [ "$KEYS_FAIL" -gt 0 ]; then
  warn "$KEYS_OK of $KEY_COUNT MaaS API keys reachable ($KEYS_FAIL failed)"
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

# ── Step 5: Per-model health (with deployment info) ────────────
step "5: Per-model health and deployments"
HEALTH_RESP=$(curl -s --connect-timeout 10 "$LITELLM_URL/health" -H "Authorization: Bearer $LITELLM_MASTER_KEY" 2>/dev/null)
HEALTH_OK=$(echo "$HEALTH_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('healthy_count',0))" 2>/dev/null || echo "?")
HEALTH_FAIL=$(echo "$HEALTH_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('unhealthy_count',0))" 2>/dev/null || echo "?")
if [ "$HEALTH_FAIL" = "0" ]; then
  pass "All deployments healthy ($HEALTH_OK healthy, $HEALTH_FAIL unhealthy)"
else
  warn "$HEALTH_OK healthy, $HEALTH_FAIL unhealthy — may be transient rate limits on health probes"
fi

# Report deployment count
if [ "$KEY_COUNT" -gt 1 ]; then
  printf "  ℹ️  $KEY_COUNT deployments per model ($((KEY_COUNT * 5)) total across 5 models)\n"
fi

# ── Step 5.5: Deployment count verification ─────────────────────
step "5.5: Config deployment count"
CONFIG_FILE="assets/config/litellm_config.yaml"
if [ -f "$CONFIG_FILE" ]; then
  pass "litellm_config.yaml exists (generated)"
  # Count model_list entries (lines starting with "  - model_name:")
  DEPLOYMENT_COUNT=$(grep -c '^\s*- model_name:' "$CONFIG_FILE" 2>/dev/null || echo "0")
  EXPECTED_DEPLOYMENTS=$((KEY_COUNT * 5))
  if [ "$DEPLOYMENT_COUNT" = "$EXPECTED_DEPLOYMENTS" ]; then
    pass "Deployment count: $DEPLOYMENT_COUNT (expected $EXPECTED_DEPLOYMENTS = 5 models × $KEY_COUNT keys)"
  else
    warn "Deployment count: $DEPLOYMENT_COUNT (expected $EXPECTED_DEPLOYMENTS = 5 models × $KEY_COUNT keys) — may need to re-run generate_config.sh"
  fi
else
  fail "litellm_config.yaml not found — run scripts/generate_config.sh"
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
# Ephemeral test key: validates key generation + DB storage.
# Auto-expires in 1h, $1 budget — not for production use.
step "11: Virtual key generation (ephemeral test key, 1h lifespan)"
KEY_RESP=$(curl -s --connect-timeout 10 -X POST "$LITELLM_URL/key/generate" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key_alias":"e2e-test-key-1h-ephemeral","models":["glm-5"],"max_budget":1.0,"duration":"1h"}' 2>/dev/null)
VK=$(echo "$KEY_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('key',''))" 2>/dev/null || echo "")
if [ -n "$VK" ] && echo "$VK" | grep -q '^sk-'; then
  pass "Virtual key minted: ${VK:0:10}...${VK: -4} (expires in 1h)"
else
  fail "Virtual key generation failed"
fi

# ── Summary ────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL + WARN))
printf "\n${YELLOW}══════════════════════════════════════════════════════${NC}\n"
printf "Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}, ${YELLOW}$WARN warnings${NC} out of $TOTAL checks\n"
if [ "$KEY_COUNT" -gt 1 ]; then
  printf "MaaS API keys: $KEY_COUNT ($((KEY_COUNT * 5)) deployments across 5 models)\n"
fi
if [ "$FAIL" -gt 0 ]; then
  printf "${RED}VALIDATION FAILED — $FAIL check(s) did not pass${NC}\n"
  exit 1
else
  printf "${GREEN}VALIDATION PASSED${NC}\n"
  exit 0
fi
