#!/usr/bin/env bash
# claude-glm side-by-side installer for the production LiteLLM-adapter chain:
#
#   claude-glm -> ccr (127.0.0.1:3456, custom router)
#              -> LiteLLM Anthropic adapter (127.0.0.1:4010)
#              -> LiteLLM (127.0.0.1:4000, docker) -> Huawei MaaS glm-5.1
#
# The plain `claude` command keeps using Anthropic; only `claude-glm` routes to
# MaaS via the `claude-opus-4-6` routing alias (the custom router maps it to the
# adapter, which carries streaming usage so auto-compact actually fires).
#
# Prerequisite: the LiteLLM stack (port 4000) must already be running; this
# script does not provision it (see the separate LiteLLM-Huawei-MaaS-Proxy
# project). It deploys the archived CCR config/custom-router/plugins, installs
# the local Anthropic adapter, and writes the claude-glm wrapper.
set -euo pipefail

# Backend model is informational; routing goes through the alias below.
MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"
ROUTING_MODEL="${ROUTING_MODEL:-claude-opus-4-6}"
# MaaS glm-5.1 hard input limit is 196608 tokens while Claude Code assumes a
# 200000 window; trigger auto-compact early enough to leave room for one full
# turn (max output + tool results).
MAAS_AUTO_COMPACT_WINDOW="${MAAS_AUTO_COMPACT_WINDOW:-180000}"
CLAUDE_GLM_BIN_DIR="${CLAUDE_GLM_BIN_DIR:-$HOME/.local/bin}"
CLAUDE_GLM_CONFIG_DIR="${CLAUDE_GLM_CONFIG_DIR:-$HOME/.config/claude-glm}"
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude-code-router}"
CLAUDE_GLM_ROUTER_KEY="${CLAUDE_GLM_ROUTER_KEY:-claude-glm-local}"
ADAPTER_DEST="${ADAPTER_DEST:-$HOME/litellm-anthropic-adapter}"
CCR_BASE_URL="${CCR_BASE_URL:-http://127.0.0.1:3456}"
LITELLM_ENV_FILE="${LITELLM_ENV_FILE:-/root/LiteLLM/.env}"
INSTALL_SYSTEMD_USER_SERVICE="${INSTALL_SYSTEMD_USER_SERVICE:-1}"
VERIFY="${VERIFY:-1}"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

# LiteLLM virtual keys the archived config.json expands. LITELLM_ANTHROPIC_KEY
# authenticates ccr -> adapter -> LiteLLM; LITELLM_CCR_KEY authenticates ccr's
# direct LiteLLM routes (image / responses). Both are optional here: if the
# LiteLLM stack runs without auth they can stay empty, otherwise they are read
# from $LITELLM_ENV_FILE when present.
LITELLM_ANTHROPIC_KEY="${LITELLM_ANTHROPIC_KEY:-}"
LITELLM_CCR_KEY="${LITELLM_CCR_KEY:-}"
if [ -f "$LITELLM_ENV_FILE" ]; then
  # shellcheck disable=SC1090
  . "$LITELLM_ENV_FILE"
fi

need_cmd node
need_cmd npm

if ! command -v ccr >/dev/null 2>&1; then
  npm install -g @musistudio/claude-code-router
fi
need_cmd ccr
need_cmd claude
need_cmd curl

[ -f "$REPO_DIR/assets/ccr/config.json" ] || die "archived CCR config not found: $REPO_DIR/assets/ccr/config.json"
[ -f "$REPO_DIR/assets/ccr/custom-router.js" ] || die "archived custom router not found: $REPO_DIR/assets/ccr/custom-router.js"

CCR_BIN_DIR="$(dirname "$(command -v ccr)")"
CLAUDE_BIN_DIR="$(dirname "$(command -v claude)")"
SYSTEMD_USER_DIR="${SYSTEMD_USER_DIR:-$HOME/.config/systemd/user}"

mkdir -p "$CLAUDE_CONFIG_DIR" "$CLAUDE_GLM_CONFIG_DIR" "$CLAUDE_GLM_BIN_DIR" "$CLAUDE_CONFIG_DIR/plugins"
chmod 700 "$CLAUDE_CONFIG_DIR" "$CLAUDE_GLM_CONFIG_DIR" "$CLAUDE_GLM_BIN_DIR"

# ---------------------------------------------------------------------------
# Deploy the verified 3-provider CCR config, custom router, and plugins from the
# repo archive. config.json carries $CLAUDE_GLM_ROUTER_KEY / $LITELLM_* APIKEY
# placeholders (expanded by ccr at runtime from its env) and absolute plugin /
# custom-router paths pinned to the default root deployment; rewrite those paths
# to $CLAUDE_CONFIG_DIR so non-default install dirs still work.
# ---------------------------------------------------------------------------
CONFIG="$CLAUDE_CONFIG_DIR/config.json"
if [ -f "$CONFIG" ]; then
  cp "$CONFIG" "$CONFIG.backup.$(date +%Y%m%d%H%M%S)"
fi
DIR_JSON="$(json_escape "$CLAUDE_CONFIG_DIR")"
sed "s#/root/.claude-code-router#$DIR_JSON#g" "$REPO_DIR/assets/ccr/config.json" > "$CONFIG"
chmod 600 "$CONFIG"

cp "$REPO_DIR/assets/ccr/custom-router.js" "$CLAUDE_CONFIG_DIR/custom-router.js"

for p in "$REPO_DIR"/assets/ccr/plugins/*.js; do
  [ -e "$p" ] || continue
  cp "$p" "$CLAUDE_CONFIG_DIR/plugins/$(basename "$p")"
done

# Local Anthropic adapter the wrapper's ensure_anthropic_adapter starts.
VERIFY=0 "$REPO_DIR/scripts/install-anthropic-adapter.sh"

ENV_FILE="$CLAUDE_GLM_CONFIG_DIR/env"
cat > "$ENV_FILE" <<EOF
export HUAWEI_MAAS_API_KEY="$(json_escape "$MAAS_API_KEY")"
export CLAUDE_GLM_ROUTER_KEY="$(json_escape "$CLAUDE_GLM_ROUTER_KEY")"
export LITELLM_ANTHROPIC_KEY="$(json_escape "$LITELLM_ANTHROPIC_KEY")"
export LITELLM_CCR_KEY="$(json_escape "$LITELLM_CCR_KEY")"
EOF
chmod 600 "$ENV_FILE"

# glm-5.1 cannot invoke Claude's native server-side WebSearch/WebFetch tools, so
# deny them by default in a claude-glm-only settings file. The wrapper injects
# this via --settings, keeping the plain `claude` command (and ~/.claude) clean.
SETTINGS_FILE="$CLAUDE_GLM_CONFIG_DIR/settings.json"
cat > "$SETTINGS_FILE" <<'EOF'
{
  "permissions": {
    "deny": ["WebSearch", "WebFetch"]
  }
}
EOF
chmod 600 "$SETTINGS_FILE"

CLAUDE_GLM_BIN="$CLAUDE_GLM_BIN_DIR/claude-glm"
RECOVER_SCRIPT_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/claude-glm-recover.sh"
# Keep the wrapper portable: reference the adapter via $HOME for the default
# install path, only pin an absolute path when ADAPTER_DEST was overridden.
if [ "$ADAPTER_DEST" = "$HOME/litellm-anthropic-adapter" ]; then
  ADAPTER_START_EXPR='$HOME/litellm-anthropic-adapter/start.sh'
else
  ADAPTER_START_EXPR="$ADAPTER_DEST/start.sh"
fi
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
# MaaS glm-5.1 hard input limit is 196608 tokens while Claude Code assumes a
# 200000 window; trigger auto-compact early enough to leave room for one
# full turn (max output 8192 + tool results).
export CLAUDE_CODE_AUTO_COMPACT_WINDOW="\${CLAUDE_GLM_AUTO_COMPACT_WINDOW:-$MAAS_AUTO_COMPACT_WINDOW}"
export ANTHROPIC_MODEL="\${ANTHROPIC_MODEL:-$ROUTING_MODEL}"
export ANTHROPIC_CUSTOM_MODEL_OPTION="\${ANTHROPIC_CUSTOM_MODEL_OPTION:-$ROUTING_MODEL}"
export ANTHROPIC_CUSTOM_MODEL_OPTION_NAME="\${ANTHROPIC_CUSTOM_MODEL_OPTION_NAME:-$ROUTING_MODEL}"
export ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION="\${ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION:-Claude Opus compatibility route to Huawei Cloud MaaS $MAAS_MODEL}"
unset CLAUDE_CODE_USE_BEDROCK

# glm-5.1 cannot invoke Claude's native server-side WebSearch/WebFetch tools;
# deny them by default via a claude-glm-only settings file so the model does
# not pretend to search or get routed through an unreliable bridge. Users can
# override by passing their own --settings.
CLAUDE_GLM_SETTINGS="\${CLAUDE_GLM_SETTINGS:-\$HOME/.config/claude-glm/settings.json}"

ensure_anthropic_adapter() {
  adapter_start="$ADAPTER_START_EXPR"
  if [[ -x "\$adapter_start" ]]; then
    "\$adapter_start" >/dev/null 2>&1 || {
      echo "claude-glm wrapper: LiteLLM Anthropic adapter failed to start" >&2
      exit 1
    }
  fi
}

if ! command -v ccr >/dev/null 2>&1; then
  echo "claude-glm wrapper: ccr is not in PATH" >&2
  exit 127
fi

ensure_anthropic_adapter

ccr_healthy() {
  curl -fsS -m 2 "\$ANTHROPIC_BASE_URL/" >/dev/null 2>&1
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

# GET / on ccr is unauthenticated, so ccr_healthy passes even with a wrong
# token and claude then retries 401s for 60s+ with no visible error. Probe
# the authenticated /v1/models endpoint — it returns 401/403 on bad auth and
# 404 on good auth (route doesn't exist but auth passed). This is ~6ms vs
# ~10s for a full /v1/messages inference call. Any non-401/403 status passes
# through so backend hiccups never block startup.
check_router_token() {
  token_status="\$(curl -sS -m 2 -o /dev/null -w '%{http_code}' \\
    -H "Authorization: Bearer \$ANTHROPIC_AUTH_TOKEN" \\
    "\$ANTHROPIC_BASE_URL/v1/models" 2>/dev/null)" || token_status="000"
  if [[ "\$token_status" == "401" || "\$token_status" == "403" ]]; then
    echo "claude-glm wrapper: router rejected the auth token (HTTP \$token_status)." >&2
    echo "claude-glm wrapper: check that ANTHROPIC_AUTH_TOKEN / CLAUDE_GLM_ROUTER_KEY matches APIKEY in ~/.claude-code-router/config.json, then run 'ccr restart'." >&2
    exit 1
  fi
}

check_router_token

# Management subcommands take no runtime flags; skip all injection for them.
is_mgmt=0
case "\${1:-}" in
  agents|auth|auto-mode|doctor|install|mcp|plugin|plugins|project|setup-token|ultrareview|update|upgrade)
    is_mgmt=1
    ;;
esac

user_model=0
user_settings=0
for arg in "\$@"; do
  case "\$arg" in
    --model|--model=*) user_model=1 ;;
    --settings|--settings=*) user_settings=1 ;;
  esac
done

extra_args=()
if [[ "\$is_mgmt" == "0" ]]; then
  if [[ "\$user_model" == "0" ]]; then
    extra_args+=(--model "\$ANTHROPIC_MODEL")
  fi
  if [[ "\$user_settings" == "0" && -f "\$CLAUDE_GLM_SETTINGS" ]]; then
    extra_args+=(--settings "\$CLAUDE_GLM_SETTINGS")
  fi
fi

exec claude \${extra_args[@]+"\${extra_args[@]}"} "\$@"
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
# LiteLLM virtual keys may also live in the LiteLLM stack env; load them so the
# resident router can expand \$LITELLM_ANTHROPIC_KEY / \$LITELLM_CCR_KEY.
if [[ -f "$LITELLM_ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$LITELLM_ENV_FILE"
  set +a
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

router_url="\${CLAUDE_GLM_ROUTER_URL:-$CCR_BASE_URL}"

healthy=1
ccr status 2>/dev/null | grep -q "Status: Running" || healthy=0
curl -fsS -m 3 "\$router_url/" >/dev/null 2>&1 || healthy=0

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
  "$CLAUDE_GLM_BIN" --bare --print --output-format json 'Reply with OK only' | node -e '
const fs = require("fs");
const text = fs.readFileSync(0, "utf8");
let data;
try { data = JSON.parse(text); } catch (err) {
  console.error(text);
  throw err;
}
const usage = data.modelUsage || {};
// Claude Code reports usage in camelCase (inputTokens/outputTokens).
const entry = Object.entries(usage).find(
  ([, u]) => u && (u.inputTokens || u.outputTokens)
);
if (!entry) {
  console.error(JSON.stringify(data, null, 2));
  process.exitCode = 1;
  throw new Error("modelUsage reports no token usage (routing/usage passthrough broken)");
}
console.log(`verified: claude-glm reported usage for ${entry[0]}`);
'
fi

echo "configured: claude-glm -> ccr -> LiteLLM Anthropic adapter -> LiteLLM -> Huawei Cloud MaaS ($MAAS_MODEL)"
echo "preserved: claude remains unchanged at $(command -v claude)"
echo "config: $CONFIG"
echo "router: $CLAUDE_CONFIG_DIR/custom-router.js (+ plugins/)"
echo "adapter: $ADAPTER_DEST"
echo "env: $ENV_FILE"
echo "wrapper: $CLAUDE_GLM_BIN"
echo "note: requires the LiteLLM stack on :4000 and the Anthropic adapter on :4010"
