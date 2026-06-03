#!/usr/bin/env bash
set -euo pipefail

MAAS_BASE_URL="${MAAS_BASE_URL:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"
MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"
MAAS_CONTEXT_TOKENS="${MAAS_CONTEXT_TOKENS:-120000}"
MAAS_MAX_OUTPUT_TOKENS="${MAAS_MAX_OUTPUT_TOKENS:-8192}"
CLAUDE_GLM_BIN_DIR="${CLAUDE_GLM_BIN_DIR:-$HOME/.local/bin}"
CLAUDE_GLM_CONFIG_DIR="${CLAUDE_GLM_CONFIG_DIR:-$HOME/.config/claude-glm}"
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude-code-router}"
CLAUDE_GLM_ROUTER_KEY="${CLAUDE_GLM_ROUTER_KEY:-claude-glm-local}"
CCR_BASE_URL="${CCR_BASE_URL:-http://127.0.0.1:3456}"
INSTALL_SYSTEMD_USER_SERVICE="${INSTALL_SYSTEMD_USER_SERVICE:-1}"
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
need_cmd curl

CCR_BIN_DIR="$(dirname "$(command -v ccr)")"
CLAUDE_BIN_DIR="$(dirname "$(command -v claude)")"
SYSTEMD_USER_DIR="${SYSTEMD_USER_DIR:-$HOME/.config/systemd/user}"

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
chmod 600 "$CONFIG"

ENV_FILE="$CLAUDE_GLM_CONFIG_DIR/env"
cat > "$ENV_FILE" <<EOF
export HUAWEI_MAAS_API_KEY="$(json_escape "$MAAS_API_KEY")"
export CLAUDE_GLM_ROUTER_KEY="$(json_escape "$CLAUDE_GLM_ROUTER_KEY")"
EOF
chmod 600 "$ENV_FILE"

CLAUDE_GLM_BIN="$CLAUDE_GLM_BIN_DIR/claude-glm"
RECOVER_SCRIPT_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/claude-glm-recover.sh"
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
case ",\${NO_PROXY:-}," in
  *,127.0.0.1,localhost,*) ;;
  *) export NO_PROXY="\${NO_PROXY:+\$NO_PROXY,}127.0.0.1,localhost" ;;
esac
export DISABLE_TELEMETRY="\${DISABLE_TELEMETRY:-true}"
export DISABLE_COST_WARNINGS="\${DISABLE_COST_WARNINGS:-true}"
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

ccr_healthy() {
  ccr status 2>/dev/null | grep -q "Status: Running" &&
    curl -fsS -m 2 \
      -H "Authorization: Bearer \$ANTHROPIC_AUTH_TOKEN" \
      "\$ANTHROPIC_BASE_URL/" >/dev/null 2>&1
}

wait_for_ccr_stop() {
  for _ in {1..20}; do
    if ! ccr status 2>/dev/null | grep -q "Status: Running"; then
      return 0
    fi
    sleep 0.25
  done
}

start_ccr() {
  if [[ -z "\${HUAWEI_MAAS_API_KEY:-}" ]]; then
    echo "claude-glm wrapper: HUAWEI_MAAS_API_KEY is not set" >&2
    exit 1
  fi
  ccr_log="\${CLAUDE_GLM_CCR_LOG:-/tmp/claude-glm-ccr.log}"
  if command -v setsid >/dev/null 2>&1; then
    setsid ccr start > "\$ccr_log" 2>&1 < /dev/null &
  else
    nohup ccr start > "\$ccr_log" 2>&1 < /dev/null &
  fi

  for _ in {1..60}; do
    ccr_healthy && break
    sleep 0.5
  done

  if ! ccr_healthy; then
    echo "claude-glm wrapper: ccr failed to start; see \$ccr_log" >&2
    ccr status >&2 || true
    exit 1
  fi
}

if ! ccr_healthy; then
  ccr stop >/dev/null 2>&1 || true
  wait_for_ccr_stop
  start_ccr
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

if [[ -f "$RECOVER_SCRIPT_SRC" ]]; then
  install -m 0755 "$RECOVER_SCRIPT_SRC" "$CLAUDE_GLM_BIN_DIR/claude-glm-recover"
fi

install_systemd_user_service() {
  if [[ "$INSTALL_SYSTEMD_USER_SERVICE" != "1" ]]; then
    return 1
  fi
  if ! command -v systemctl >/dev/null 2>&1 || ! systemctl --user is-system-running >/dev/null 2>&1; then
    echo "warning: systemd user manager is not available; skipping persistent ccr service" >&2
    return 1
  fi

  mkdir -p "$SYSTEMD_USER_DIR"

  cat > "$CLAUDE_GLM_BIN_DIR/claude-glm-ccr-run" <<EOF
#!/usr/bin/env bash
set -euo pipefail

export PATH="$CLAUDE_GLM_BIN_DIR:$CCR_BIN_DIR:$CLAUDE_BIN_DIR:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

if [[ -f "\$HOME/.config/claude-glm/env" ]]; then
  # shellcheck disable=SC1091
  source "\$HOME/.config/claude-glm/env"
fi

case ",\${NO_PROXY:-}," in
  *,127.0.0.1,localhost,*) ;;
  *) export NO_PROXY="\${NO_PROXY:+\$NO_PROXY,}127.0.0.1,localhost" ;;
esac

export API_TIMEOUT_MS="\${API_TIMEOUT_MS:-600000}"
export CLAUDE_GLM_ROUTER_KEY="\${CLAUDE_GLM_ROUTER_KEY:-$CLAUDE_GLM_ROUTER_KEY}"

command -v ccr >/dev/null || {
  echo "ccr is not in PATH" >&2
  exit 127
}

exec ccr start
EOF
  chmod 700 "$CLAUDE_GLM_BIN_DIR/claude-glm-ccr-run"

  cat > "$CLAUDE_GLM_BIN_DIR/claude-glm-ccr-health" <<EOF
#!/usr/bin/env bash
set -euo pipefail

export PATH="$CLAUDE_GLM_BIN_DIR:$CCR_BIN_DIR:$CLAUDE_BIN_DIR:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

if [[ -f "\$HOME/.config/claude-glm/env" ]]; then
  # shellcheck disable=SC1091
  source "\$HOME/.config/claude-glm/env"
fi

router_key="\${CLAUDE_GLM_ROUTER_KEY:-$CLAUDE_GLM_ROUTER_KEY}"
router_url="\${CLAUDE_GLM_ROUTER_URL:-$CCR_BASE_URL}"

healthy=1
ccr status 2>/dev/null | grep -q "Status: Running" || healthy=0
curl -fsS -m 3 -H "Authorization: Bearer \$router_key" "\$router_url/" >/dev/null 2>&1 || healthy=0

if [[ "\$healthy" != "1" ]]; then
  echo "claude-glm ccr health check failed; restarting user service" >&2
  systemctl --user restart claude-glm-ccr.service
fi
EOF
  chmod 700 "$CLAUDE_GLM_BIN_DIR/claude-glm-ccr-health"

  cat > "$SYSTEMD_USER_DIR/claude-glm-ccr.service" <<EOF
[Unit]
Description=Claude GLM Claude Code Router
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h
ExecStart=$CLAUDE_GLM_BIN_DIR/claude-glm-ccr-run
ExecStop=/bin/bash -lc 'export PATH="$CLAUDE_GLM_BIN_DIR:$CCR_BIN_DIR:$CLAUDE_BIN_DIR:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"; ccr stop >/dev/null 2>&1 || true'
Restart=always
RestartSec=5
KillMode=mixed
TimeoutStopSec=10

[Install]
WantedBy=default.target
EOF

  cat > "$SYSTEMD_USER_DIR/claude-glm-ccr-health.service" <<EOF
[Unit]
Description=Health check and auto-repair Claude GLM CCR

[Service]
Type=oneshot
ExecStart=$CLAUDE_GLM_BIN_DIR/claude-glm-ccr-health
EOF

  cat > "$SYSTEMD_USER_DIR/claude-glm-ccr-health.timer" <<EOF
[Unit]
Description=Run Claude GLM CCR health check periodically

[Timer]
OnBootSec=30s
OnUnitActiveSec=60s
AccuracySec=10s
Unit=claude-glm-ccr-health.service

[Install]
WantedBy=timers.target
EOF

  loginctl enable-linger "$USER" >/dev/null 2>&1 || true
  systemctl --user daemon-reload
  ccr stop >/dev/null 2>&1 || true
  systemctl --user enable --now claude-glm-ccr.service claude-glm-ccr-health.timer
  systemctl --user restart claude-glm-ccr.service
  echo "configured: systemd user service claude-glm-ccr.service"
  echo "configured: systemd health timer claude-glm-ccr-health.timer"
  return 0
}

if ! install_systemd_user_service; then
  ccr restart
fi

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
