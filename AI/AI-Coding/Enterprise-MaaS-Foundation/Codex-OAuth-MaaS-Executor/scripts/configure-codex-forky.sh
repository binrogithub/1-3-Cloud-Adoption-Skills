#!/usr/bin/env bash
set -euo pipefail

CODEX_FORKY_BIN_DIR="${CODEX_FORKY_BIN_DIR:-$HOME/.local/bin}"
CODEX_FORKY_CONFIG_DIR="${CODEX_FORKY_CONFIG_DIR:-$HOME/.config/codex-forky}"
CODEX_FORKY_HOME="${CODEX_FORKY_HOME:-$HOME/.codex-forky}"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
CODEX_FORKY_BRIDGE_URL="${CODEX_FORKY_BRIDGE_URL:-http://127.0.0.1:3460}"
CODEX_FORKY_PORT="${CODEX_FORKY_PORT:-3460}"
CODEX_FORKY_HOST="${CODEX_FORKY_HOST:-127.0.0.1}"
CODEX_FORKY_ROUTER_KEY="${CODEX_FORKY_ROUTER_KEY:-codex-forky-local}"
CODEX_FORKY_MODEL="${CODEX_FORKY_MODEL:-claude-sonnet-4-6}"
CODEX_FORKY_OAUTH_MODEL="${CODEX_FORKY_OAUTH_MODEL:-gpt-5.5}"
CODEX_FORKY_CONTEXT_TOKENS="${CODEX_FORKY_CONTEXT_TOKENS:-180000}"
CODEX_FORKY_MAX_OUTPUT_TOKENS="${CODEX_FORKY_MAX_OUTPUT_TOKENS:-8192}"
FORKY_BASE_URL="${FORKY_BASE_URL:-http://127.0.0.1:3458}"
INSTALL_SYSTEMD_USER_SERVICE="${INSTALL_SYSTEMD_USER_SERVICE:-1}"
INSTALL_CODEX_SKILL="${INSTALL_CODEX_SKILL:-1}"
CODEX_FORKY_RESTART_BRIDGE="${CODEX_FORKY_RESTART_BRIDGE:-1}"
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

toml_escape() {
  node -e 'process.stdout.write(JSON.stringify(process.argv[1]))' "$1"
}

script_dir() {
  cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
}

probe_forky() {
  curl -fsS -m 2 "$FORKY_BASE_URL/health" >/dev/null 2>&1 ||
    curl -fsS -m 2 "$FORKY_BASE_URL/" >/dev/null 2>&1 ||
    die "forky is not reachable at $FORKY_BASE_URL. Install/start forky first."
}

write_bridge() {
  mkdir -p "$CODEX_FORKY_HOME"
  chmod 700 "$CODEX_FORKY_HOME"
  cp "$(script_dir)/codex-forky-responses-bridge.cjs" "$CODEX_FORKY_HOME/codex-forky-responses-bridge.cjs"
  chmod 700 "$CODEX_FORKY_HOME/codex-forky-responses-bridge.cjs"
}

install_codex_skill() {
  [[ "$INSTALL_CODEX_SKILL" == "1" ]] || return 0
  local skill_dir skill_dest skill_dest_parent
  skill_dir="$(cd "$(script_dir)/.." && pwd -P)"
  [[ -f "$skill_dir/SKILL.md" ]] || return 0
  skill_dest="$CODEX_HOME_DIR/skills/codex-oauth-maas-executor"
  skill_dest_parent="$(dirname "$skill_dest")"
  mkdir -p "$skill_dest_parent"
  chmod 700 "$CODEX_HOME_DIR" "$skill_dest_parent" 2>/dev/null || true

  if [[ -d "$skill_dest" ]] && [[ "$(cd "$skill_dest" && pwd -P)" == "$skill_dir" ]]; then
    return 0
  fi

  if command -v rsync >/dev/null 2>&1; then
    mkdir -p "$skill_dest"
    rsync -a --delete "$skill_dir/" "$skill_dest/"
  else
    rm -rf "$skill_dest.tmp"
    cp -a "$skill_dir" "$skill_dest.tmp"
    rm -rf "$skill_dest"
    mv "$skill_dest.tmp" "$skill_dest"
  fi
}

write_env_file() {
  mkdir -p "$CODEX_FORKY_CONFIG_DIR"
  chmod 700 "$CODEX_FORKY_CONFIG_DIR"
  cat > "$CODEX_FORKY_CONFIG_DIR/env" <<EOF
export CODEX_FORKY_BRIDGE_URL="$(json_escape "$CODEX_FORKY_BRIDGE_URL")"
export CODEX_FORKY_PORT="$(json_escape "$CODEX_FORKY_PORT")"
export CODEX_FORKY_HOST="$(json_escape "$CODEX_FORKY_HOST")"
export CODEX_FORKY_ROUTER_KEY="$(json_escape "$CODEX_FORKY_ROUTER_KEY")"
export CODEX_FORKY_MODEL="$(json_escape "$CODEX_FORKY_MODEL")"
export CODEX_FORKY_OAUTH_MODEL="$(json_escape "$CODEX_FORKY_OAUTH_MODEL")"
export CODEX_FORKY_CONTEXT_TOKENS="$(json_escape "$CODEX_FORKY_CONTEXT_TOKENS")"
export CODEX_FORKY_MAX_OUTPUT_TOKENS="$(json_escape "$CODEX_FORKY_MAX_OUTPUT_TOKENS")"
export CODEX_FORKY_HOME="$(json_escape "$CODEX_FORKY_HOME")"
export FORKY_BASE_URL="$(json_escape "$FORKY_BASE_URL")"
EOF
  chmod 600 "$CODEX_FORKY_CONFIG_DIR/env"
}

write_codex_profile() {
  mkdir -p "$CODEX_HOME_DIR"
  chmod 700 "$CODEX_HOME_DIR"
  local profile="$CODEX_HOME_DIR/forky.config.toml"
  cat > "$profile" <<EOF
model = $(toml_escape "$CODEX_FORKY_MODEL")
model_provider = "forky-responses-bridge"
model_context_window = $CODEX_FORKY_CONTEXT_TOKENS
model_reasoning_effort = "none"
model_catalog_json = "$CODEX_FORKY_HOME/model-catalog.json"

[model_providers.forky-responses-bridge]
name = "Forky Responses Bridge"
base_url = "$CODEX_FORKY_BRIDGE_URL/v1"
env_key = "CODEX_FORKY_ROUTER_KEY"
wire_api = "responses"
EOF
  chmod 600 "$profile"
}

write_model_catalog() {
  mkdir -p "$CODEX_FORKY_HOME"
  local catalog="$CODEX_FORKY_HOME/model-catalog.json"
  local model_json
  model_json="$(json_escape "$CODEX_FORKY_MODEL")"
  cat > "$catalog" <<EOF
{
  "models": [
    {
      "experimental_supported_tools": [],
      "available_in_plans": [],
      "supports_search_tool": false,
      "service_tiers": [],
      "additional_speed_tiers": [],
      "supports_reasoning_summaries": false,
      "prefer_websockets": false,
      "support_verbosity": false,
      "apply_patch_tool_type": "freeform",
      "web_search_tool_type": "text",
      "input_modalities": ["text", "image"],
      "supports_image_detail_original": true,
      "truncation_policy": {
        "mode": "tokens",
        "limit": 10000
      },
      "supports_parallel_tool_calls": true,
      "context_window": $CODEX_FORKY_CONTEXT_TOKENS,
      "max_context_window": $CODEX_FORKY_CONTEXT_TOKENS,
      "auto_compact_token_limit": null,
      "reasoning_summary_format": "none",
      "default_reasoning_summary": "auto",
      "slug": "$model_json",
      "display_name": "$model_json via forky",
      "description": "Codex split routing: tool/code-execution turns go through forky to the execution backend; non-tool and image turns go to Codex OAuth.",
      "default_reasoning_level": "none",
      "supported_reasoning_levels": [],
      "shell_type": "shell_command",
      "visibility": "list",
      "minimal_client_version": "0.0.1",
      "supported_in_api": true,
      "availability_nux": null,
      "upgrade": null,
      "priority": 10,
      "base_instructions": ""
    }
  ]
}
EOF
  chmod 600 "$catalog"
}

write_wrapper() {
  mkdir -p "$CODEX_FORKY_BIN_DIR"
  chmod 700 "$CODEX_FORKY_BIN_DIR"

  cat > "$CODEX_FORKY_BIN_DIR/codex-forky-bridge-run" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
if [[ -f "$HOME/.config/codex-forky/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.config/codex-forky/env"
fi
exec node "${CODEX_FORKY_HOME:-$HOME/.codex-forky}/codex-forky-responses-bridge.cjs"
EOF
  chmod 700 "$CODEX_FORKY_BIN_DIR/codex-forky-bridge-run"

  cat > "$CODEX_FORKY_BIN_DIR/codex-forky" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ -f "$HOME/.config/codex-forky/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.config/codex-forky/env"
fi

export CODEX_FORKY_ROUTER_KEY="${CODEX_FORKY_ROUTER_KEY:-codex-forky-local}"
export CODEX_FORKY_BRIDGE_URL="${CODEX_FORKY_BRIDGE_URL:-http://127.0.0.1:3460}"
export CODEX_FORKY_MODEL="${CODEX_FORKY_MODEL:-claude-sonnet-4-6}"
export CODEX_FORKY_OAUTH_MODEL="${CODEX_FORKY_OAUTH_MODEL:-gpt-5.5}"
export CODEX_FORKY_HOME="${CODEX_FORKY_HOME:-$HOME/.codex-forky}"
export FORKY_BASE_URL="${FORKY_BASE_URL:-http://127.0.0.1:3458}"

case ",${NO_PROXY:-}," in
  *,127.0.0.1,localhost,*) ;;
  *) export NO_PROXY="${NO_PROXY:+$NO_PROXY,}127.0.0.1,localhost" ;;
esac

bridge_healthy() {
  curl -fsS -m 2 -H "Authorization: Bearer $CODEX_FORKY_ROUTER_KEY" "$CODEX_FORKY_BRIDGE_URL/v1/responses" >/dev/null 2>&1
}

start_bridge() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl --user start codex-forky-bridge.service >/dev/null 2>&1 || true
  fi
  for _ in {1..20}; do
    bridge_healthy && return 0
    sleep 0.25
  done
  nohup "$HOME/.local/bin/codex-forky-bridge-run" > /tmp/codex-forky-bridge.log 2>&1 < /dev/null &
  for _ in {1..40}; do
    bridge_healthy && return 0
    sleep 0.25
  done
  echo "codex-forky: bridge is not reachable at $CODEX_FORKY_BRIDGE_URL" >&2
  echo "codex-forky: check /tmp/codex-forky-bridge.log and forky at $FORKY_BASE_URL" >&2
  exit 1
}

bridge_healthy || start_bridge
exec codex --profile forky --model "$CODEX_FORKY_MODEL" "$@"
EOF
  chmod 700 "$CODEX_FORKY_BIN_DIR/codex-forky"
  ln -sfn "$CODEX_FORKY_BIN_DIR/codex-forky" "$CODEX_FORKY_BIN_DIR/Codex-forky"
}

bridge_port_pids() {
  local port="$CODEX_FORKY_PORT"
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp "sport = :$port" 2>/dev/null |
      sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' |
      sort -u
  elif command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u
  fi
}

restart_bridge_if_running() {
  [[ "$CODEX_FORKY_RESTART_BRIDGE" == "1" ]] || return 0
  local pids pid args
  pids="$(bridge_port_pids || true)"
  [[ -n "$pids" ]] || return 0
  for pid in $pids; do
    args="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    if [[ "$args" == *"codex-forky"* || "$args" == *"codex-forky-responses-bridge.cjs"* ]]; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
}

install_systemd_user_service() {
  [[ "$INSTALL_SYSTEMD_USER_SERVICE" == "1" ]] || return 0
  command -v systemctl >/dev/null 2>&1 || return 0
  systemctl --user is-system-running >/dev/null 2>&1 || {
    echo "warning: systemd user manager unavailable; wrapper will start bridge on demand" >&2
    return 0
  }

  local systemd_dir="${SYSTEMD_USER_DIR:-$HOME/.config/systemd/user}"
  mkdir -p "$systemd_dir"
  cat > "$systemd_dir/codex-forky-bridge.service" <<EOF
[Unit]
Description=codex-forky Responses bridge
After=network-online.target forky.service

[Service]
Type=simple
ExecStart=$CODEX_FORKY_BIN_DIR/codex-forky-bridge-run
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

  systemctl --user daemon-reload
  systemctl --user enable --now codex-forky-bridge.service >/dev/null
  loginctl enable-linger "$USER" >/dev/null 2>&1 || true
}

main() {
  need_cmd node
  need_cmd curl
  need_cmd codex

  probe_forky
  write_bridge
  install_codex_skill
  write_env_file
  write_codex_profile
  write_model_catalog
  write_wrapper
  restart_bridge_if_running
  install_systemd_user_service

  if [[ "$VERIFY" == "1" ]]; then
    "$CODEX_FORKY_BIN_DIR/codex-forky" --version >/dev/null
    curl -fsS -H "Authorization: Bearer $CODEX_FORKY_ROUTER_KEY" "$CODEX_FORKY_BRIDGE_URL/v1/responses" >/dev/null
    echo "codex-forky installed. Run: codex-forky exec --skip-git-repo-check --ephemeral 'Reply with OK only'"
  fi
}

main "$@"
