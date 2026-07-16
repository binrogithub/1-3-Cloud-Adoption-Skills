#!/usr/bin/env bash
# oauth-delegate-router verify — chains repo verification assets (PRD §12).
#  1. configure-claude-code.sh --verify   (litellm-maas-auto-plugin client probe + TOOL-CALL)
#  2. live_smoke.py text|tools            (litellm-maas-auto-plugin live smoke, if key shim present)
#  3. functional delegate smoke           (one tiny brief through claude-glm -> LiteLLM -> MaaS)
#  4. spend-log SQL                       (claude-code-maas-hybrid-router verify-forky pattern)
#  5. env-isolation asserts               (acceptance A/C invariants)
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GLM_DIR="${GLM_DIR:-$HOME/.claude-glm}"
BASE_URL="${LITELLM_BASE_URL:-http://127.0.0.1:4000}"
PG="${PG_CONTAINER:-litellm_pg_db}"
KEY=$(python3 -c "import json;print(json.load(open('$GLM_DIR/settings.json'))['env']['ANTHROPIC_API_KEY'])") || exit 1
CONFIGURE="${CONFIGURE_CC:-$ROOT/../litellm-maas-auto-plugin/client/configure-claude-code.sh}"
SMOKE="${LIVE_SMOKE:-$ROOT/../litellm-maas-auto-plugin/tests/live_smoke.py}"

echo "── 1. client probe (reused: configure-claude-code.sh --verify) ──"
CLAUDE_CONFIG_DIR="$GLM_DIR" bash "$CONFIGURE" "$KEY" --base-url "$BASE_URL" \
  --model claude-opus-4-6 --verify 2>&1 | grep -E "VERIFY|TOOL-CALL"

echo "── 2. live smoke (reused: live_smoke.py; needs LITELLM_ANTHROPIC_KEY in /root/LiteLLM/.env) ──"
if [ -f /root/LiteLLM/.env ] && grep -q LITELLM_ANTHROPIC_KEY /root/LiteLLM/.env 2>/dev/null; then
  for t in text tools; do python3 "$SMOKE" "$t" 2>&1 | tail -1; done
else
  echo "skipped (no key shim; see SKILL.md)"
fi

echo "── 3. functional delegate smoke ──"
TMP=$(mktemp -d)
"$ROOT/scripts/delegate" "{\"task_type\":\"code_generation\",\"goal\":\"Create hello.txt containing exactly: HYBRID-OK\",\"acceptance\":\"grep -q HYBRID-OK hello.txt\"}" --cwd "$TMP" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('delegate:', d['status'], '| attempts:', d['attempts'], '| verified:', d['verification']['passed'])"
rm -rf "$TMP"

echo "── 4. spend-log cross-check ──"
if command -v docker >/dev/null && docker ps --format '{{.Names}}' | grep -q "^$PG$"; then
  docker exec "$PG" psql -U llmproxy -d litellm -t -A -c \
    "select 'spendlog rows (10m): '||count(*) from \"LiteLLM_SpendLogs\" where \"startTime\" > now() - interval '10 minutes';"
else
  echo "skipped (no local $PG container)"
fi

echo "── 5. isolation invariants ──"
bash -lic 'env | grep -qE "^ANTHROPIC" && echo "FAIL: plain-shell ANTHROPIC_* leak" || echo "PASS: plain shell clean"' 2>/dev/null
python3 - <<PY
import json, os
p = os.path.expanduser("~/.claude/settings.json")
d = json.load(open(p)) if os.path.exists(p) else {}
print("PASS: plain claude transport untouched" if not d.get("env") else "FAIL: env block present in ~/.claude/settings.json")
PY
"$ROOT/scripts/route-stats.sh" || true
