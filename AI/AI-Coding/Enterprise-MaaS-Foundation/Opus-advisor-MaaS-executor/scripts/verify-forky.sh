#!/usr/bin/env bash
# verify-forky.sh — end-to-end checks: env, service, text→GLM, image→Opus,
# hook sentinel, LiteLLM DB confirmation.
set -euo pipefail

FORKY_PORT="${FORKY_PORT:-3458}"
FORKY_URL="http://127.0.0.1:$FORKY_PORT"
LITELLM_KEY="${LITELLM_KEY:-${LITELLM_CCR_KEY:-${EXEC_API_KEY:-}}}"
EXEC_MODEL="${FORKY_EXEC_MODEL:-glm-5.2}"

log()  { printf '\033[1;34m[verify-forky]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m  ✗\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[verify-forky] error:\033[0m %s\n' "$*" >&2; exit 1; }

pass=0; failc=0
check() { if "$@"; then ok "$2"; pass=$((pass+1)); else fail "$2"; failc=$((failc+1)); fi; }

# --- 1. wrapper + shell env ---------------------------------------------------
check_wrapper() {
  [[ -x "$HOME/.local/bin/claude-forky" ]] &&
    grep -q "ANTHROPIC_BASE_URL=\"http://127.0.0.1:$FORKY_PORT\"" "$HOME/.local/bin/claude-forky" &&
    grep -q "unset ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY" "$HOME/.local/bin/claude-forky"
}
check check_wrapper "claude-forky wrapper routes to forky without auth-token env"

check_no_global_auth() {
  ! bash -lic 'env | grep -E "^(ANTHROPIC_BASE_URL|ANTHROPIC_AUTH_TOKEN|ANTHROPIC_API_KEY)=" >/dev/null' 2>/dev/null
}
check check_no_global_auth "plain claude shell has no global ANTHROPIC auth/base-url"

check_mouse() {
  [[ "$(bash -lic 'echo "${CLAUDE_CODE_DISABLE_MOUSE_CLICKS:-}"' 2>/dev/null)" == "1" ]]
}
check check_mouse "CLAUDE_CODE_DISABLE_MOUSE_CLICKS=1 in new shell"

# --- 2. service ---------------------------------------------------------------
check_service() { systemctl --user is-active --quiet forky.service; }
check check_service "forky.service is active"

check_port() { ss -ltn "sport = :$FORKY_PORT" 2>/dev/null | grep -q ":$FORKY_PORT"; }
check check_port "port $FORKY_PORT is listening"

# --- 3. text + tools → execution (GLM) ---------------------------------------
text_resp="$(curl -fsS -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet-4-6",
    "max_tokens": 32,
    "tools": [{"name": "Bash", "description": "run a bash command", "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}],
    "messages": [{"role": "user", "content": "Reply with the single word: pong"}]
  }' \
  "$FORKY_URL/v1/messages" 2>&1)" || true

check_text() { echo "$text_resp" | grep -qi "pong" || echo "$text_resp" | grep -q '"content"'; }
check check_text "text+tools request returns a response"

# verify it actually routed to execution (not classifier/oauth)
check_text_route() {
  docker logs forky-systemd 2>&1 | tail -5 | grep '"event":"request"' | tail -1 | grep -q '"routedVia":"execution"' 2>/dev/null \
    || tail -80 "$HOME/.forky/forky.log" 2>/dev/null | grep '"event":"request"' | tail -1 | grep -q '"routedVia":"execution"' 2>/dev/null
}
check check_text_route "text+tools routed to execution (not classifier)"

# --- 3b. Claude Code 2.1.x system/developer-role normalization ----------------
norm_resp="$(curl -fsS -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet-4-6",
    "max_tokens": 32,
    "stream": false,
    "messages": [
      {"role": "user", "content": "context"},
      {"role": "system", "content": "reply with exactly: normalized"},
      {"role": "user", "content": "test"}
    ]
  }' \
  "$FORKY_URL/v1/messages" 2>&1)" || true

check_normalized() { echo "$norm_resp" | grep -qi "normalized\\|content"; }
check check_normalized "system role inside messages is normalized instead of 400"

# --- 4. image → vision (Opus) ------------------------------------------------
# generate a real 8×8 green PNG (1×1 is rejected by Anthropic)
PNG_FILE="$(mktemp /tmp/forky-verify-XXXXXX.png)"
python3 - "$PNG_FILE" <<'PY'
import sys, struct, zlib
def png(path):
    w = h = 8
    raw = b""
    for _ in range(h):
        raw += b"\x00" + b"\x00\xff\x00" * w
    def chunk(typ, data):
        return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", zlib.crc32(typ + data))
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(sig + ihdr + idat + iend)
png(sys.argv[1])
PY

img_b64="$(base64 -w0 "$PNG_FILE")"
img_resp="$(curl -fsS -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d "{
    \"model\": \"claude-sonnet-4-6\",
    \"max_tokens\": 32,
    \"messages\": [{\"role\": \"user\", \"content\": [{\"type\": \"image\", \"source\": {\"type\": \"base64\", \"media_type\": \"image/png\", \"data\": \"$img_b64\"}}, {\"type\": \"text\", \"text\": \"What color is this image? One word.\"}]}]
  }" \
  "$FORKY_URL/v1/messages" 2>&1)" || true

check_image() { echo "$img_resp" | grep -qi "green\|content"; }
check check_image "image request routes to vision (Opus) and returns a color answer"
rm -f "$PNG_FILE"

# --- 5. hook sentinel ---------------------------------------------------------
HOOK="$HOME/dev/forky/bin/forky-hook"
SENTINEL="$HOME/.forky/opus"
check_hook() {
  [[ -x "$HOOK" ]] || return 1
  # simulate UserPromptSubmit
  echo '{"hook_event_name":"UserPromptSubmit","prompt":"test"}' | "$HOOK" >/dev/null 2>&1 || true
  [[ -f "$SENTINEL" ]]
}
check check_hook "UserPromptSubmit hook creates plan-mode sentinel"

# --- 6. LiteLLM DB confirmation ----------------------------------------------
check_db() {
  if ! docker exec litellm_pg_db psql -U llmproxy -d litellm -t -A \
    -c "select 1 from \"LiteLLM_SpendLogs\" where model like '%glm-5.2%' and \"startTime\" > now() - interval '5 minutes' limit 1" 2>/dev/null | grep -q 1; then
    return 1
  fi
}
check check_db "LiteLLM Postgres shows glm-5.2 served a request in the last 5 min"

# --- summary ------------------------------------------------------------------
echo ""
log "results: $pass passed, $failc failed"
if [[ $failc -gt 0 ]]; then
  die "verification failed. Check ~/.forky/forky.log and journalctl --user -u forky -n 50 --no-pager"
fi
log "all checks passed — forky is routing correctly"
