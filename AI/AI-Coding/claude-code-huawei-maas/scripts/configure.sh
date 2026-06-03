#!/usr/bin/env bash
set -euo pipefail

MAAS_BASE_URL="${MAAS_BASE_URL:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"
MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"
MAAS_CONTEXT_TOKENS="${MAAS_CONTEXT_TOKENS:-120000}"
MAAS_MAX_OUTPUT_TOKENS="${MAAS_MAX_OUTPUT_TOKENS:-8192}"
CCR_AUTH_TOKEN="${CCR_AUTH_TOKEN:-test}"
CCR_BASE_URL="${CCR_BASE_URL:-http://127.0.0.1:3456}"
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude-code-router}"
VERIFY="${VERIFY:-1}"

die() {
  echo "error: $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required"
}

json_escape() {
  node -e 'process.stdout.write(JSON.stringify(process.argv[1]).slice(1,-1))' "$1"
}

if [ -z "${API_KEY:-}" ]; then
  die "API_KEY is not set. Export API_KEY before running this script."
fi

need_cmd node
need_cmd npm

if ! command -v ccr >/dev/null 2>&1; then
  npm install -g @musistudio/claude-code-router
fi
need_cmd ccr

CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude || true)}"
[ -n "$CLAUDE_BIN" ] || die "claude command not found in PATH"
[ -e "$CLAUDE_BIN" ] || die "claude path does not exist: $CLAUDE_BIN"

mkdir -p "$CLAUDE_CONFIG_DIR"
CONFIG="$CLAUDE_CONFIG_DIR/config.json"
if [ -f "$CONFIG" ]; then
  cp "$CONFIG" "$CONFIG.backup.$(date +%Y%m%d%H%M%S)"
fi

BASE_NO_SLASH="${MAAS_BASE_URL%/}"
CHAT_COMPLETIONS_URL="$BASE_NO_SLASH/chat/completions"
MODEL_JSON="$(json_escape "$MAAS_MODEL")"
URL_JSON="$(json_escape "$CHAT_COMPLETIONS_URL")"

cat > "$CONFIG" <<EOF
{
  "LOG": true,
  "LOG_LEVEL": "info",
  "API_TIMEOUT_MS": 600000,
  "NON_INTERACTIVE_MODE": false,
  "Providers": [
    {
      "name": "huawei-maas",
      "api_base_url": "$URL_JSON",
      "api_key": "\$API_KEY",
      "models": [
        "$MODEL_JSON"
      ],
      "transformer": {
        "use": [
          [
            "maxtoken",
            {
              "max_tokens": $MAAS_MAX_OUTPUT_TOKENS
            }
          ],
          "cleancache",
          "reasoning",
          "enhancetool"
        ]
      }
    }
  ],
  "Router": {
    "default": "huawei-maas,$MODEL_JSON",
    "background": "huawei-maas,$MODEL_JSON",
    "longContext": "huawei-maas,$MODEL_JSON",
    "longContextThreshold": $MAAS_CONTEXT_TOKENS
  }
}
EOF

REAL_CLAUDE="${CLAUDE_BIN}.real"
if [ -f "$CLAUDE_BIN" ] && grep -q "claude-huawei-maas wrapper" "$CLAUDE_BIN"; then
  :
elif [ -e "$REAL_CLAUDE" ]; then
  :
else
  mv "$CLAUDE_BIN" "$REAL_CLAUDE"
fi

[ -e "$REAL_CLAUDE" ] || die "real Claude binary not found: $REAL_CLAUDE"

cat > "$CLAUDE_BIN" <<EOF
#!/usr/bin/env bash
# claude-huawei-maas wrapper
set -euo pipefail

if ! command -v ccr >/dev/null 2>&1; then
  echo "claude wrapper: ccr is not in PATH" >&2
  exit 127
fi

if ! ccr status 2>/dev/null | grep -q "Status: Running"; then
  if [ -z "\${API_KEY:-}" ]; then
    echo "claude wrapper: API_KEY is not set; export API_KEY before starting Claude Code Router" >&2
    exit 1
  fi
  ccr_log="\${CLAUDE_HUAWEI_CCR_LOG:-/tmp/claude-huawei-maas-ccr.log}"
  if command -v setsid >/dev/null 2>&1; then
    setsid ccr start > "\$ccr_log" 2>&1 < /dev/null &
  else
    nohup ccr start > "\$ccr_log" 2>&1 < /dev/null &
  fi

  for _ in {1..30}; do
    ccr status 2>/dev/null | grep -q "Status: Running" && break
    sleep 0.2
  done

  if ! ccr status 2>/dev/null | grep -q "Status: Running"; then
    echo "claude wrapper: ccr failed to start; see \$ccr_log" >&2
    exit 1
  fi
fi

export ANTHROPIC_AUTH_TOKEN="\${ANTHROPIC_AUTH_TOKEN:-$CCR_AUTH_TOKEN}"
export ANTHROPIC_BASE_URL="\${ANTHROPIC_BASE_URL:-$CCR_BASE_URL}"
export NO_PROXY="\${NO_PROXY:-127.0.0.1}"
export DISABLE_TELEMETRY="\${DISABLE_TELEMETRY:-true}"
export DISABLE_COST_WARNINGS="\${DISABLE_COST_WARNINGS:-true}"
export API_TIMEOUT_MS="\${API_TIMEOUT_MS:-600000}"
export CLAUDE_CODE_MAX_CONTEXT_TOKENS="\${CLAUDE_CODE_MAX_CONTEXT_TOKENS:-$MAAS_CONTEXT_TOKENS}"
export ANTHROPIC_MODEL="\${ANTHROPIC_MODEL:-$MAAS_MODEL}"
export ANTHROPIC_CUSTOM_MODEL_OPTION="\${ANTHROPIC_CUSTOM_MODEL_OPTION:-$MAAS_MODEL}"
export ANTHROPIC_CUSTOM_MODEL_OPTION_NAME="\${ANTHROPIC_CUSTOM_MODEL_OPTION_NAME:-$MAAS_MODEL}"
export ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION="\${ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION:-Huawei Cloud MaaS $MAAS_MODEL}"
unset CLAUDE_CODE_USE_BEDROCK

exec "$REAL_CLAUDE" "\$@"
EOF
chmod 755 "$CLAUDE_BIN"

ccr restart

if [ "$VERIFY" = "1" ]; then
  "$CLAUDE_BIN" --bare --print --output-format json 'Reply with OK only' | MAAS_MODEL="$MAAS_MODEL" node -e '
const fs = require("fs");
const text = fs.readFileSync(0, "utf8");
let data;
try { data = JSON.parse(text); } catch (err) {
  console.error(text);
  throw err;
}
const usage = data.modelUsage || {};
const model = process.env.MAAS_MODEL || "glm-5.1";
if (!usage[model]) {
  console.error(JSON.stringify(data, null, 2));
  process.exitCode = 1;
  throw new Error(`modelUsage does not include ${model}`);
}
console.log(`verified: claude uses ${model}`);
'
fi

echo "configured: claude -> ccr -> Huawei Cloud MaaS ($MAAS_MODEL)"
echo "config: $CONFIG"
echo "wrapper: $CLAUDE_BIN"
