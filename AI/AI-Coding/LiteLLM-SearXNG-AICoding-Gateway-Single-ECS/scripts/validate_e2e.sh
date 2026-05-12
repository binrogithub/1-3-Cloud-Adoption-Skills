#!/usr/bin/env bash
# End-to-end validation for the gateway.
# Runs from the laptop. Requires curl, jq, python3.
#
# Required env:
#   ECS_PUBLIC_IP
#   LITELLM_MASTER_KEY
#   HUAWEI_MAAS_API_BASE
#   HUAWEI_MAAS_API_KEY
#   MCP_TOKEN

set -euo pipefail

: "${ECS_PUBLIC_IP:?missing}"
: "${LITELLM_MASTER_KEY:?missing}"
: "${HUAWEI_MAAS_API_BASE:?missing}"
: "${HUAWEI_MAAS_API_KEY:?missing}"
: "${MCP_TOKEN:?missing}"

ok()   { printf "[ OK ] %s\n" "$*"; }
fail() { printf "[FAIL] %s\n" "$*"; exit 1; }

echo "== 1. Direct MaaS (baseline) =="
RESP=$(curl -fsS -H "Authorization: Bearer $HUAWEI_MAAS_API_KEY" \
    -H 'Content-Type: application/json' \
    -X POST "$HUAWEI_MAAS_API_BASE/chat/completions" \
    -d '{"model":"glm-5.1","messages":[{"role":"user","content":"reply: pong"}],"max_tokens":50}')
echo "$RESP" | python3 -c "import sys,json; print('reply:', json.load(sys.stdin)['choices'][0]['message']['content'])"
ok "direct MaaS"

echo
echo "== 2. LiteLLM /health/liveliness =="
curl -fsS "http://$ECS_PUBLIC_IP:4000/health/liveliness" >/dev/null
ok "liveliness"

echo
echo "== 3. LiteLLM /health upstream =="
H=$(curl -fsS -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
    "http://$ECS_PUBLIC_IP:4000/health")
HC=$(echo "$H" | python3 -c "import sys,json; print(json.load(sys.stdin)['healthy_count'])")
UC=$(echo "$H" | python3 -c "import sys,json; print(json.load(sys.stdin)['unhealthy_count'])")
[[ "$UC" == "0" ]] || fail "unhealthy_count=$UC"
ok "upstream healthy=$HC unhealthy=$UC"

echo
echo "== 4. LiteLLM proxied chat (master key) =="
curl -fsS -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
    -H 'Content-Type: application/json' \
    -X POST "http://$ECS_PUBLIC_IP:4000/v1/chat/completions" \
    -d '{"model":"huawei/glm-5.1","messages":[{"role":"user","content":"reply: pong"}],"max_tokens":50}' \
    | python3 -c "import sys,json; print('reply:', json.load(sys.stdin)['choices'][0]['message']['content'])"
ok "proxied chat"

echo
echo "== 5. LiteLLM /model/info costs =="
curl -fsS -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
    "http://$ECS_PUBLIC_IP:4000/v1/model/info" \
    | python3 -c "import sys,json; d=json.load(sys.stdin);
[print(m['model_name'],'in',m['model_info'].get('input_cost_per_token'),'out',m['model_info'].get('output_cost_per_token')) for m in d['data']]"
ok "model_info costs"

echo
echo "== 6. MCP no-auth probe =="
HC=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "http://$ECS_PUBLIC_IP:8788/mcp" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json,text/event-stream' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}')
[[ "$HC" == "401" ]] || fail "expected 401, got $HC"
ok "no-auth probe -> 401"

echo
echo "== 7. MCP initialize + tools/list + tools/call =="
TMP=$(mktemp)
curl -fsS -i -X POST "http://$ECS_PUBLIC_IP:8788/mcp" \
    -H "Authorization: Bearer $MCP_TOKEN" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json,text/event-stream' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' \
    > "$TMP"
SID=$(grep -i '^mcp-session-id' "$TMP" | awk '{print $2}' | tr -d '\r')
[[ -n "$SID" ]] || fail "no session id"

curl -fsS -X POST "http://$ECS_PUBLIC_IP:8788/mcp" \
    -H "Authorization: Bearer $MCP_TOKEN" -H "mcp-session-id: $SID" \
    -H 'Content-Type: application/json' -H 'Accept: application/json,text/event-stream' \
    -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null

curl -fsS -X POST "http://$ECS_PUBLIC_IP:8788/mcp" \
    -H "Authorization: Bearer $MCP_TOKEN" -H "mcp-session-id: $SID" \
    -H 'Content-Type: application/json' -H 'Accept: application/json,text/event-stream' \
    -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
    | sed -n '/^data:/p' | head -1 | grep -q web_search || fail "web_search missing"

curl -fsS -X POST "http://$ECS_PUBLIC_IP:8788/mcp" \
    -H "Authorization: Bearer $MCP_TOKEN" -H "mcp-session-id: $SID" \
    -H 'Content-Type: application/json' -H 'Accept: application/json,text/event-stream' \
    -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"web_search","arguments":{"query":"Anthropic Claude","num_results":3}}}' \
    | sed -n '/^data:/p' | head -1 | grep -q '"title"' || fail "no search results"
ok "MCP full handshake + web_search"

echo
echo "ALL CHECKS PASSED"
