#!/usr/bin/env bash
set -euo pipefail

MAAS_BASE_URL="${MAAS_BASE_URL:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"
MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"
MAAS_CONTEXT_TOKENS="${MAAS_CONTEXT_TOKENS:-190000}"
MAAS_MAX_OUTPUT_TOKENS="${MAAS_MAX_OUTPUT_TOKENS:-32768}"
CLAUDE_GLM_BIN_DIR="${CLAUDE_GLM_BIN_DIR:-$HOME/.local/bin}"
CLAUDE_GLM_CONFIG_DIR="${CLAUDE_GLM_CONFIG_DIR:-$HOME/.config/claude-glm}"
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude-code-router}"
CLAUDE_GLM_ROUTER_KEY="${CLAUDE_GLM_ROUTER_KEY:-claude-glm-local}"
CCR_BASE_URL="${CCR_BASE_URL:-http://127.0.0.1:3456}"
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

MAAS_API_KEY="${HUAWEI_MAAS_API_KEY:-${MAAS_API_KEY:-${API_KEY:-}}}"
if [ -z "$MAAS_API_KEY" ]; then
  die "HUAWEI_MAAS_API_KEY, MAAS_API_KEY, or API_KEY is not set. Export one before running this script."
fi
export HUAWEI_MAAS_API_KEY="$MAAS_API_KEY"
export CLAUDE_GLM_ROUTER_KEY

need_cmd node
need_cmd npm

if ! command -v ccr >/dev/null 2>&1; then
  npm install -g @musistudio/claude-code-router
fi
need_cmd ccr
need_cmd claude

mkdir -p "$CLAUDE_CONFIG_DIR" "$CLAUDE_GLM_CONFIG_DIR" "$CLAUDE_GLM_BIN_DIR"
chmod 700 "$CLAUDE_CONFIG_DIR" "$CLAUDE_GLM_CONFIG_DIR" "$CLAUDE_GLM_BIN_DIR"

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
  "HOST": "127.0.0.1",
  "PORT": 3456,
  "APIKEY": "\$CLAUDE_GLM_ROUTER_KEY",
  "LOG": true,
  "LOG_LEVEL": "info",
  "API_TIMEOUT_MS": 600000,
  "NON_INTERACTIVE_MODE": false,
  "Providers": [
    {
      "name": "huawei-maas",
      "api_base_url": "$URL_JSON",
      "api_key": "\$HUAWEI_MAAS_API_KEY",
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
          "enhancetool"
        ]
      }
    }
  ],
  "Router": {
    "default": "huawei-maas,$MODEL_JSON",
    "background": "huawei-maas,$MODEL_JSON",
    "think": "huawei-maas,$MODEL_JSON",
    "longContext": "huawei-maas,$MODEL_JSON",
    "longContextThreshold": $MAAS_CONTEXT_TOKENS
  }
}
EOF
chmod 600 "$CONFIG"

ENV_FILE="$CLAUDE_GLM_CONFIG_DIR/env"
cat > "$ENV_FILE" <<EOF
export HUAWEI_MAAS_API_KEY="$(json_escape "$MAAS_API_KEY")"
export CLAUDE_GLM_ROUTER_KEY="$(json_escape "$CLAUDE_GLM_ROUTER_KEY")"
EOF
chmod 600 "$ENV_FILE"

CLAUDE_GLM_BIN="$CLAUDE_GLM_BIN_DIR/claude-glm"
cat > "$CLAUDE_GLM_BIN" <<EOF
#!/usr/bin/env bash
# claude-glm side-by-side wrapper: keep claude on Anthropic, route only this command to Huawei MaaS.
set -euo pipefail

if [[ -f "\$HOME/.config/claude-glm/env" ]]; then
  # shellcheck disable=SC1091
  source "\$HOME/.config/claude-glm/env"
fi

export ANTHROPIC_AUTH_TOKEN="$CLAUDE_GLM_ROUTER_KEY"
export ANTHROPIC_BASE_URL="$CCR_BASE_URL"
export NO_PROXY="\${NO_PROXY:-127.0.0.1}"
export DISABLE_TELEMETRY="\${DISABLE_TELEMETRY:-true}"
export DISABLE_COST_WARNINGS="\${DISABLE_COST_WARNINGS:-true}"
export DISABLE_COMPACT="\${DISABLE_COMPACT:-true}"
export API_TIMEOUT_MS="\${API_TIMEOUT_MS:-600000}"
export CLAUDE_CODE_MAX_CONTEXT_TOKENS="\${CLAUDE_CODE_MAX_CONTEXT_TOKENS:-$MAAS_CONTEXT_TOKENS}"
export ANTHROPIC_MODEL="\${ANTHROPIC_MODEL:-$MAAS_MODEL}"
export ANTHROPIC_CUSTOM_MODEL_OPTION="\${ANTHROPIC_CUSTOM_MODEL_OPTION:-$MAAS_MODEL}"
export ANTHROPIC_CUSTOM_MODEL_OPTION_NAME="\${ANTHROPIC_CUSTOM_MODEL_OPTION_NAME:-$MAAS_MODEL}"
export ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION="\${ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION:-Huawei Cloud MaaS $MAAS_MODEL}"
unset CLAUDE_CODE_USE_BEDROCK

if ! command -v ccr >/dev/null 2>&1; then
  echo "claude-glm wrapper: ccr is not in PATH" >&2
  exit 127
fi

if ! ccr status >/dev/null 2>&1; then
  if [[ -z "\${HUAWEI_MAAS_API_KEY:-}" ]]; then
    echo "claude-glm wrapper: HUAWEI_MAAS_API_KEY is not set" >&2
    exit 1
  fi
  ccr start >/dev/null
fi

inject_model=1
case "\${1:-}" in
  --model|--model=*)
    inject_model=0
    ;;
  agents|auth|auto-mode|doctor|install|mcp|plugin|plugins|project|setup-token|ultrareview|update|upgrade)
    inject_model=0
    ;;
esac

for arg in "\$@"; do
  if [[ "\$arg" == "--model" || "\$arg" == --model=* ]]; then
    inject_model=0
    break
  fi
done

if [[ "\$inject_model" == "1" ]]; then
  exec claude --model "\$ANTHROPIC_MODEL" "\$@"
fi

exec claude "\$@"
EOF
chmod 700 "$CLAUDE_GLM_BIN"
ln -sfn "$CLAUDE_GLM_BIN" "$CLAUDE_GLM_BIN_DIR/Claude-glm"

ccr restart

if [ "$VERIFY" = "1" ]; then
  "$CLAUDE_GLM_BIN" --bare --print --output-format json 'Reply with OK only' | MAAS_MODEL="$MAAS_MODEL" node -e '
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
console.log(`verified: claude-glm uses ${model}`);
'
fi

echo "configured: claude-glm -> ccr -> Huawei Cloud MaaS ($MAAS_MODEL)"
echo "preserved: claude remains unchanged at $(command -v claude)"
echo "config: $CONFIG"
echo "env: $ENV_FILE"
echo "wrapper: $CLAUDE_GLM_BIN"
