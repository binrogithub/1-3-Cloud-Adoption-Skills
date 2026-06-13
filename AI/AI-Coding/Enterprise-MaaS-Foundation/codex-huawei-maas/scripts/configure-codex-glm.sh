#!/usr/bin/env bash
set -euo pipefail

MAAS_BASE_URL="${MAAS_BASE_URL:-https://api-ap-southeast-1.modelarts-maas.com/openai/v1}"
MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"
MAAS_CONTEXT_TOKENS="${MAAS_CONTEXT_TOKENS:-120000}"
MAAS_MAX_OUTPUT_TOKENS="${MAAS_MAX_OUTPUT_TOKENS:-8192}"
CODEX_GLM_BIN_DIR="${CODEX_GLM_BIN_DIR:-$HOME/.local/bin}"
CODEX_GLM_CONFIG_DIR="${CODEX_GLM_CONFIG_DIR:-$HOME/.config/codex-glm}"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
CODEX_GLM_CCR_HOME="${CODEX_GLM_CCR_HOME:-$HOME/.codex-glm/ccr-home}"
CODEX_GLM_MODEL_CATALOG_DIR="${CODEX_GLM_MODEL_CATALOG_DIR:-$HOME/.codex-glm}"
CCR_CONFIG_DIR="${CCR_CONFIG_DIR:-$CODEX_GLM_CCR_HOME/.claude-code-router}"
CCR_BASE_URL="${CCR_BASE_URL:-http://127.0.0.1:3457}"
CODEX_GLM_ROUTER_KEY="${CODEX_GLM_ROUTER_KEY:-codex-glm-local}"
CLAUDE_GLM_ROUTER_KEY="${CLAUDE_GLM_ROUTER_KEY:-$CODEX_GLM_ROUTER_KEY}"
CODEX_GLM_UPSTREAM_RPS="${CODEX_GLM_UPSTREAM_RPS:-0}"
CODEX_GLM_429_RETRIES="${CODEX_GLM_429_RETRIES:-3}"
CODEX_GLM_ENABLE_SEARCH="${CODEX_GLM_ENABLE_SEARCH:-0}"
CODEX_GLM_ENABLE_IMAGE="${CODEX_GLM_ENABLE_IMAGE:-0}"
CODEX_GLM_IMAGE_MODEL="${CODEX_GLM_IMAGE_MODEL:-vision-openrouter}"
LITELLM_BASE_URL="${LITELLM_BASE_URL:-http://127.0.0.1:4000}"
LITELLM_CCR_KEY="${LITELLM_CCR_KEY:-${LITELLM_API_KEY:-${MAAS_API_KEY:-${HUAWEI_MAAS_API_KEY:-}}}}"
INSTALL_SYSTEMD_USER_SERVICE="${INSTALL_SYSTEMD_USER_SERVICE:-1}"
VERIFY="${VERIFY:-1}"
RESTORE_CCR="${RESTORE_CCR:-0}"

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

url_port() {
  node -e 'const u=new URL(process.argv[1]); process.stdout.write(u.port || (u.protocol==="https:"?"443":"80"))' "$1"
}

script_dir() {
  cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
}

resolve_ccr_package_dir() {
  local npm_root
  npm_root="$(npm root -g)"
  local package_dir="$npm_root/@musistudio/claude-code-router"
  [[ -d "$package_dir" ]] || die "cannot find @musistudio/claude-code-router under $npm_root"
  printf '%s\n' "$package_dir"
}

restore_ccr() {
  local cli_js="$1"
  local backup
  backup="$(ls -1t "$cli_js".codex-glm-backup-* 2>/dev/null | head -n 1 || true)"
  [[ -n "$backup" ]] || die "no codex-glm CCR backup found for $cli_js"
  cp "$backup" "$cli_js"
  echo "restored $cli_js from $backup"
}

inject_ccr_shim() {
  local package_dir="$1"
  local cli_js="$package_dir/dist/cli.js"
  local shim_src="$(script_dir)/codex-glm-ccr-responses-shim.cjs"
  local shim_dst="$package_dir/dist/codex-glm-ccr-responses-shim.cjs"
  local marker='// codex-glm responses shim'

  [[ -f "$cli_js" ]] || die "CCR cli.js not found: $cli_js"
  [[ -f "$shim_src" ]] || die "shim source not found: $shim_src"

  if [[ "$RESTORE_CCR" == "1" ]]; then
    restore_ccr "$cli_js"
    rm -f "$shim_dst"
    return 0
  fi

  cp "$shim_src" "$shim_dst"

  if grep -qF "$marker" "$cli_js"; then
    echo "CCR responses shim already injected"
    return 0
  fi

  cp "$cli_js" "$cli_js.codex-glm-backup-$(date +%Y%m%d%H%M%S)"

  node - "$cli_js" <<'NODE'
const fs = require('fs');
const [file] = process.argv.slice(2);
let content = fs.readFileSync(file, 'utf8');
if (content.includes('// codex-glm responses shim')) process.exit(0);
const needle = 'e.get("/health",async()=>({status:"ok",timestamp:new Date().toISOString()}));let t=e.transformerService.getTransformersWithEndpoint();for(let{transformer:r}of t)r.endPoint&&e.post(r.endPoint,async(n,s)=>cN(n,s,e,r));';
const injection = 'e.get("/health",async()=>({status:"ok",timestamp:new Date().toISOString()}));try{require("./codex-glm-ccr-responses-shim.cjs").register(e)}catch(t){console.error("codex-glm responses shim failed:",t)}; // codex-glm responses shim\nlet t=e.transformerService.getTransformersWithEndpoint();for(let{transformer:r}of t)r.endPoint&&r.endPoint!=="/v1/responses"&&e.post(r.endPoint,async(n,s)=>cN(n,s,e,r));';
if (!content.includes(needle)) {
  console.error('Could not find CCR route registration anchor. Unsupported CCR dist/cli.js layout.');
  process.exit(2);
}
content = content.replace(needle, injection);
fs.writeFileSync(file, content);
NODE
  echo "injected CCR responses shim into $cli_js"
}

write_search_transformer() {
  [[ "$CODEX_GLM_ENABLE_SEARCH" == "1" ]] || return 0
  local plugin_dir="$CCR_CONFIG_DIR/plugins"
  local plugin="$plugin_dir/claude-websearch-to-responses.js"
  mkdir -p "$plugin_dir"
  cat > "$plugin" <<'PLUGIN'
class ClaudeWebSearchToResponses {
  name = "claude-websearch-to-responses";

  latestUserText(body) {
    const textParts = [];
    const addText = (text) => {
      if (!text || text.includes("<system-reminder>")) return;
      textParts.push(text);
    };
    const collect = (value) => {
      if (!value) return;
      if (typeof value === "string") return addText(value);
      if (Array.isArray(value)) return value.forEach(collect);
      if (typeof value === "object") {
        if (typeof value.text === "string") addText(value.text);
        if (typeof value.content === "string") addText(value.content);
        if (Array.isArray(value.content)) collect(value.content);
      }
    };
    const latestUserMessage = (messages) => {
      if (!Array.isArray(messages)) return undefined;
      for (let i = messages.length - 1; i >= 0; i -= 1) {
        if (messages[i] && messages[i].role === "user") return messages[i];
      }
      return undefined;
    };
    collect(latestUserMessage(body && body.messages));
    collect(latestUserMessage(body && body.input));
    return textParts.join("\n");
  }

  isSearchIntent(body) {
    return /搜索|新闻|最新|今天|今日|current|latest|today|news|search/i.test(this.latestUserText(body));
  }

  addSystemInstruction(body, content) {
    if (!body || !content) return;
    if (Array.isArray(body.input)) body.input.unshift({ role: "system", content });
    if (typeof body.system === "string") body.system = `${body.system}\n\n${content}`;
    else if (Array.isArray(body.system)) body.system.push({ type: "text", text: content });
    else if (Array.isArray(body.messages)) body.system = [{ type: "text", text: content }];
  }

  async transformRequestIn(body) {
    if (body && Array.isArray(body.input)) body.use_chat_completions_api = true;
    if (this.isSearchIntent(body)) {
      this.addSystemInstruction(
        body,
        "Live search, when configured, is handled before the model call by the LiteLLM proxy. Do not call WebSearch, WebFetch, Fetch, or shell tools for this search request."
      );
      if (Array.isArray(body.tools)) body.tools = [];
    }
    return body;
  }
}

module.exports = ClaudeWebSearchToResponses;
PLUGIN
  chmod 600 "$plugin"
}

write_ccr_config() {
  local config="$CCR_CONFIG_DIR/config.json"
  local ccr_port
  local base_no_slash="${MAAS_BASE_URL%/}"
  local chat_url="$base_no_slash/chat/completions"
  local model_json image_model_json url_json litellm_responses_url_json litellm_chat_url_json plugin_path_json
  local providers_json default_route image_route transformers_json
  ccr_port="$(url_port "$CCR_BASE_URL")"
  model_json="$(json_escape "$MAAS_MODEL")"
  image_model_json="$(json_escape "$CODEX_GLM_IMAGE_MODEL")"
  url_json="$(json_escape "$chat_url")"
  litellm_responses_url_json="$(json_escape "${LITELLM_BASE_URL%/}/v1/responses")"
  litellm_chat_url_json="$(json_escape "${LITELLM_BASE_URL%/}/v1/chat/completions")"
  plugin_path_json="$(json_escape "$CCR_CONFIG_DIR/plugins/claude-websearch-to-responses.js")"

  mkdir -p "$CCR_CONFIG_DIR"
  chmod 700 "$CCR_CONFIG_DIR"
  if [[ -f "$config" ]] && command -v lsattr >/dev/null 2>&1 && command -v chattr >/dev/null 2>&1; then
    if lsattr "$config" 2>/dev/null | grep -q -- '----i'; then
      chattr -i "$config" 2>/dev/null || die "cannot remove immutable attribute from $config"
    fi
  fi
  if [[ -f "$config" ]]; then
    cp "$config" "$config.backup.$(date +%Y%m%d%H%M%S)"
  fi

  providers_json='{
      "name": "huawei-maas",
      "api_base_url": "'"$url_json"'",
      "api_key": "$HUAWEI_MAAS_API_KEY",
      "models": ["'"$model_json"'"],
      "transformer": {
        "use": [
          ["maxtoken", { "max_tokens": '"$MAAS_MAX_OUTPUT_TOKENS"' }],
          "cleancache",
          "reasoning",
          "enhancetool"
        ]
      }
    }'
  default_route="huawei-maas,$model_json"
  transformers_json=""

  if [[ "$CODEX_GLM_ENABLE_SEARCH" == "1" ]]; then
    providers_json='{
      "name": "LiteLLM Provider",
      "api_base_url": "'"$litellm_responses_url_json"'",
      "api_key": "$LITELLM_CCR_KEY",
      "models": ["'"$model_json"'"],
      "transformer": {
        "use": [
          ["maxtoken", { "max_tokens": '"$MAAS_MAX_OUTPUT_TOKENS"' }],
          "cleancache",
          "claude-websearch-to-responses",
          "openai-responses",
          "claude-websearch-to-responses"
        ]
      }
    }'
    default_route="LiteLLM Provider,$model_json"
    transformers_json=',
  "transformers": [
    {
      "path": "'"$plugin_path_json"'"
    }
  ]'
  fi

  image_route=""
  if [[ "$CODEX_GLM_ENABLE_IMAGE" == "1" ]]; then
    providers_json="$providers_json"',{
      "name": "litellm-chat",
      "api_base_url": "'"$litellm_chat_url_json"'",
      "api_key": "$LITELLM_CCR_KEY",
      "models": ["'"$image_model_json"'"],
      "transformer": { "use": ["openrouter"] }
    }'
    image_route=',
    "image": "litellm-chat,'"$image_model_json"'"'
  fi

  cat > "$config" <<EOF
{
  "HOST": "127.0.0.1",
  "PORT": $ccr_port,
  "APIKEY": "\$CLAUDE_GLM_ROUTER_KEY",
  "LOG": true,
  "LOG_LEVEL": "info",
  "API_TIMEOUT_MS": 600000,
  "NON_INTERACTIVE_MODE": false,
  "Providers": [
    $providers_json
  ],
  "Router": {
    "default": "$default_route",
    "background": "$default_route",
    "longContext": "$default_route",
    "longContextThreshold": $MAAS_CONTEXT_TOKENS$image_route
  }$transformers_json
}
EOF
  chmod 600 "$config"
}

write_codex_profile() {
  mkdir -p "$CODEX_HOME_DIR"
  chmod 700 "$CODEX_HOME_DIR"
  local profile="$CODEX_HOME_DIR/glm.config.toml"
  cat > "$profile" <<EOF
model = $(toml_escape "$MAAS_MODEL")
model_provider = "huawei-maas-ccr"
model_context_window = $MAAS_CONTEXT_TOKENS
model_reasoning_effort = "none"
model_catalog_json = "$CODEX_GLM_MODEL_CATALOG_DIR/model-catalog.json"

[model_providers.huawei-maas-ccr]
name = "Huawei MaaS via CCR"
base_url = "$CCR_BASE_URL/v1"
env_key = "CODEX_GLM_ROUTER_KEY"
wire_api = "responses"
EOF
  chmod 600 "$profile"
}

write_model_catalog() {
  mkdir -p "$CODEX_GLM_MODEL_CATALOG_DIR"
  local catalog="$CODEX_GLM_MODEL_CATALOG_DIR/model-catalog.json"
  local model_json context_json supports_search experimental_tools input_modalities supports_image_detail
  model_json="$(json_escape "$MAAS_MODEL")"
  context_json="$MAAS_CONTEXT_TOKENS"
  supports_search="false"
  experimental_tools="[]"
  input_modalities='"text"'
  supports_image_detail="false"
  if [[ "$CODEX_GLM_ENABLE_SEARCH" == "1" ]]; then
    supports_search="true"
    experimental_tools='["web_search"]'
  fi
  if [[ "$CODEX_GLM_ENABLE_IMAGE" == "1" ]]; then
    input_modalities='"text", "image"'
    supports_image_detail="true"
  fi
  cat > "$catalog" <<CATALOG
{
  "models": [
    {
      "experimental_supported_tools": $experimental_tools,
      "available_in_plans": [],
      "supports_search_tool": $supports_search,
      "service_tiers": [],
      "additional_speed_tiers": [],
      "supports_reasoning_summaries": false,
      "prefer_websockets": false,
      "support_verbosity": false,
      "apply_patch_tool_type": "freeform",
      "web_search_tool_type": "text",
      "input_modalities": [$input_modalities],
      "supports_image_detail_original": $supports_image_detail,
      "truncation_policy": {
        "mode": "tokens",
        "limit": 10000
      },
      "supports_parallel_tool_calls": true,
      "context_window": $context_json,
      "max_context_window": $context_json,
      "auto_compact_token_limit": null,
      "reasoning_summary_format": "none",
      "default_reasoning_summary": "auto",
      "slug": "$model_json",
      "display_name": "$model_json",
      "description": "Huawei Cloud MaaS $model_json model.",
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
CATALOG
  chmod 600 "$catalog"
}

write_env_file() {
  local maas_api_key="$1"
  mkdir -p "$CODEX_GLM_CONFIG_DIR"
  chmod 700 "$CODEX_GLM_CONFIG_DIR"
  cat > "$CODEX_GLM_CONFIG_DIR/env" <<EOF
export HUAWEI_MAAS_API_KEY="$(json_escape "$maas_api_key")"
export MAAS_BASE_URL="$(json_escape "$MAAS_BASE_URL")"
export MAAS_MODEL="$(json_escape "$MAAS_MODEL")"
export MAAS_CONTEXT_TOKENS="$(json_escape "$MAAS_CONTEXT_TOKENS")"
export MAAS_MAX_OUTPUT_TOKENS="$(json_escape "$MAAS_MAX_OUTPUT_TOKENS")"
export CODEX_GLM_ROUTER_KEY="$(json_escape "$CODEX_GLM_ROUTER_KEY")"
export CLAUDE_GLM_ROUTER_KEY="$(json_escape "$CLAUDE_GLM_ROUTER_KEY")"
export CCR_BASE_URL="$(json_escape "$CCR_BASE_URL")"
export CODEX_GLM_CCR_HOME="$(json_escape "$CODEX_GLM_CCR_HOME")"
export CODEX_GLM_UPSTREAM_RPS="$(json_escape "$CODEX_GLM_UPSTREAM_RPS")"
export CODEX_GLM_429_RETRIES="$(json_escape "$CODEX_GLM_429_RETRIES")"
export CODEX_GLM_ENABLE_SEARCH="$(json_escape "$CODEX_GLM_ENABLE_SEARCH")"
export CODEX_GLM_ENABLE_IMAGE="$(json_escape "$CODEX_GLM_ENABLE_IMAGE")"
export CODEX_GLM_IMAGE_MODEL="$(json_escape "$CODEX_GLM_IMAGE_MODEL")"
export LITELLM_BASE_URL="$(json_escape "$LITELLM_BASE_URL")"
export LITELLM_CCR_KEY="$(json_escape "$LITELLM_CCR_KEY")"
EOF
  chmod 600 "$CODEX_GLM_CONFIG_DIR/env"
}

write_wrapper() {
  mkdir -p "$CODEX_GLM_BIN_DIR"
  chmod 700 "$CODEX_GLM_BIN_DIR"
  local wrapper="$CODEX_GLM_BIN_DIR/codex-glm"
  cat > "$wrapper" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ -f "$HOME/.config/codex-glm/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.config/codex-glm/env"
fi

export CODEX_GLM_ROUTER_KEY="${CODEX_GLM_ROUTER_KEY:-codex-glm-local}"
export CLAUDE_GLM_ROUTER_KEY="${CLAUDE_GLM_ROUTER_KEY:-$CODEX_GLM_ROUTER_KEY}"
export ANTHROPIC_AUTH_TOKEN="$CLAUDE_GLM_ROUTER_KEY"
export ANTHROPIC_BASE_URL="${CCR_BASE_URL:-http://127.0.0.1:3457}"
export CODEX_GLM_CCR_HOME="${CODEX_GLM_CCR_HOME:-$HOME/.codex-glm/ccr-home}"
CODEX_GLM_MODEL_CATALOG_DIR="${CODEX_GLM_MODEL_CATALOG_DIR:-$HOME/.codex-glm}"
export MAAS_MODEL="${MAAS_MODEL:-glm-5.1}"
export MAAS_MAX_OUTPUT_TOKENS="${MAAS_MAX_OUTPUT_TOKENS:-8192}"

case ",${NO_PROXY:-}," in
  *,127.0.0.1,localhost,*) ;;
  *) export NO_PROXY="${NO_PROXY:+$NO_PROXY,}127.0.0.1,localhost" ;;
esac

ccr_healthy() {
  curl -fss -m 2 -H "Authorization: Bearer $CLAUDE_GLM_ROUTER_KEY" "$ANTHROPIC_BASE_URL/" >/dev/null &&
    curl -fss -m 2 -H "Authorization: Bearer $CLAUDE_GLM_ROUTER_KEY" "$ANTHROPIC_BASE_URL/v1/responses" >/dev/null 2>&1
}

ccr_port() {
  node -e 'const u=new URL(process.argv[1]); process.stdout.write(u.port || (u.protocol==="https:"?"443":"80"))' "$ANTHROPIC_BASE_URL"
}

ccr_port_pids() {
  local port
  port="$(ccr_port)"
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp "sport = :$port" 2>/dev/null |
      sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' |
      sort -u
  elif command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u
  fi
}

clear_ccr_state() {
  rm -f "$CODEX_GLM_CCR_HOME/.claude-code-router/.claude-code-router.pid" \
    "$CODEX_GLM_CCR_HOME/.claude-code-router/.claude-code-router.lock" \
    "$CODEX_GLM_CCR_HOME/.claude-code-router/reference_count"
}

stop_ccr_forcefully() {
  HOME="$CODEX_GLM_CCR_HOME" ccr stop >/dev/null 2>&1 || true
  local pids
  pids="$(ccr_port_pids || true)"
  if [[ -n "$pids" ]]; then
    kill $pids >/dev/null 2>&1 || true
  fi
  for _ in {1..20}; do
    if [[ -z "$(ccr_port_pids || true)" ]]; then
      clear_ccr_state
      return 0
    fi
    sleep 0.25
  done
  pids="$(ccr_port_pids || true)"
  if [[ -n "$pids" ]]; then
    kill -9 $pids >/dev/null 2>&1 || true
  fi
  clear_ccr_state
}

start_ccr() {
  if [[ -z "${HUAWEI_MAAS_API_KEY:-}" ]]; then
    echo "codex-glm: HUAWEI_MAAS_API_KEY is not set" >&2
    exit 1
  fi
  local log_file="${CODEX_GLM_CCR_LOG:-/tmp/codex-glm-ccr.log}"
  clear_ccr_state
  if command -v setsid >/dev/null 2>&1; then
    setsid env HOME="$CODEX_GLM_CCR_HOME" ccr start > "$log_file" 2>&1 < /dev/null &
  else
    nohup env HOME="$CODEX_GLM_CCR_HOME" ccr start > "$log_file" 2>&1 < /dev/null &
  fi
  for _ in {1..60}; do
    if ccr_healthy; then
      return 0
    fi
    sleep 0.5
  done
  echo "codex-glm: ccr failed to start; see $log_file" >&2
  HOME="$CODEX_GLM_CCR_HOME" ccr status >&2 || true
  exit 1
}

if ! ccr_healthy; then
  stop_ccr_forcefully
  start_ccr
fi

exec codex --profile glm --model "$MAAS_MODEL" "$@"
EOF
  chmod 700 "$wrapper"
  ln -sfn "$wrapper" "$CODEX_GLM_BIN_DIR/Codex-glm"
}

install_systemd_user_service() {
  [[ "$INSTALL_SYSTEMD_USER_SERVICE" == "1" ]] || return 0
  command -v systemctl >/dev/null 2>&1 || return 0
  systemctl --user is-system-running >/dev/null 2>&1 || {
    echo "warning: systemd user manager unavailable; skipping user service" >&2
    return 0
  }

  local systemd_dir="${SYSTEMD_USER_DIR:-$HOME/.config/systemd/user}"
  mkdir -p "$systemd_dir"

cat > "$CODEX_GLM_BIN_DIR/codex-glm-ccr-run" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
if [[ -f "$HOME/.config/codex-glm/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.config/codex-glm/env"
fi
export ANTHROPIC_AUTH_TOKEN="${CLAUDE_GLM_ROUTER_KEY:-${CODEX_GLM_ROUTER_KEY:-codex-glm-local}}"
export CODEX_GLM_ROUTER_KEY="${CODEX_GLM_ROUTER_KEY:-codex-glm-local}"
export CLAUDE_GLM_ROUTER_KEY="${CLAUDE_GLM_ROUTER_KEY:-$CODEX_GLM_ROUTER_KEY}"
export CODEX_GLM_CCR_HOME="${CODEX_GLM_CCR_HOME:-$HOME/.codex-glm/ccr-home}"
CODEX_GLM_MODEL_CATALOG_DIR="${CODEX_GLM_MODEL_CATALOG_DIR:-$HOME/.codex-glm}"
exec env HOME="$CODEX_GLM_CCR_HOME" ccr start
EOF
  chmod 700 "$CODEX_GLM_BIN_DIR/codex-glm-ccr-run"

cat > "$CODEX_GLM_BIN_DIR/codex-glm-ccr-health" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
if [[ -f "$HOME/.config/codex-glm/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.config/codex-glm/env"
fi
base="${CCR_BASE_URL:-http://127.0.0.1:3457}"
key="${CODEX_GLM_ROUTER_KEY:-codex-glm-local}"
curl -fsS -m 2 -H "Authorization: Bearer $key" "$base/" >/dev/null
curl -fsS -m 2 -H "Authorization: Bearer $key" "$base/v1/responses" >/dev/null || {
  systemctl --user restart codex-glm-ccr.service
}
EOF
  chmod 700 "$CODEX_GLM_BIN_DIR/codex-glm-ccr-health"

  cat > "$systemd_dir/codex-glm-ccr.service" <<EOF
[Unit]
Description=codex-glm CCR service
After=network-online.target

[Service]
Type=simple
ExecStart=$CODEX_GLM_BIN_DIR/codex-glm-ccr-run
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

  cat > "$systemd_dir/codex-glm-ccr-health.service" <<EOF
[Unit]
Description=codex-glm CCR health check

[Service]
Type=oneshot
ExecStart=$CODEX_GLM_BIN_DIR/codex-glm-ccr-health
EOF

  cat > "$systemd_dir/codex-glm-ccr-health.timer" <<'EOF'
[Unit]
Description=Run codex-glm CCR health check

[Timer]
OnBootSec=30
OnUnitActiveSec=60
Unit=codex-glm-ccr-health.service

[Install]
WantedBy=timers.target
EOF

  systemctl --user daemon-reload
  systemctl --user enable --now codex-glm-ccr.service codex-glm-ccr-health.timer
  loginctl enable-linger "$USER" >/dev/null 2>&1 || true
}

main() {
  need_cmd node
  need_cmd npm
  need_cmd curl
  need_cmd codex

  if ! command -v ccr >/dev/null 2>&1; then
    npm install -g @musistudio/claude-code-router
  fi
  need_cmd ccr

  local package_dir
  package_dir="$(resolve_ccr_package_dir)"
  inject_ccr_shim "$package_dir"

  if [[ "$RESTORE_CCR" == "1" ]]; then
    echo "CCR restored. Restart ccr if it is running."
    exit 0
  fi

  local maas_api_key="${HUAWEI_MAAS_API_KEY:-${MAAS_API_KEY:-${API_KEY:-}}}"
  [[ -n "$maas_api_key" ]] || die "set HUAWEI_MAAS_API_KEY, MAAS_API_KEY, or API_KEY before running"

  export HUAWEI_MAAS_API_KEY="$maas_api_key"
  export CODEX_GLM_ROUTER_KEY
  export CLAUDE_GLM_ROUTER_KEY
  export MAAS_MAX_OUTPUT_TOKENS
  export MAAS_MODEL
  export LITELLM_CCR_KEY

  write_search_transformer
  write_ccr_config
  write_codex_profile
  write_model_catalog
  write_env_file "$maas_api_key"
  write_wrapper
  install_systemd_user_service

  HOME="$CODEX_GLM_CCR_HOME" ccr stop >/dev/null 2>&1 || true
  env HOME="$CODEX_GLM_CCR_HOME" ccr start >/tmp/codex-glm-ccr.log 2>&1 &

  if [[ "$VERIFY" == "1" ]]; then
    "$CODEX_GLM_BIN_DIR/codex-glm" --version >/dev/null
    echo "codex-glm installed. Run: codex-glm exec --skip-git-repo-check --ephemeral 'Reply with OK only'"
  fi
}

main "$@"
