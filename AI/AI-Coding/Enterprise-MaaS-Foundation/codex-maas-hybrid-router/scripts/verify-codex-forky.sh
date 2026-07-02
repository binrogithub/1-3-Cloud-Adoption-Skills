#!/usr/bin/env bash
set -uo pipefail

if [[ -f "$HOME/.config/codex-forky/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.config/codex-forky/env"
fi

CODEX_FORKY_BIN_DIR="${CODEX_FORKY_BIN_DIR:-$HOME/.local/bin}"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
CODEX_FORKY_HOME="${CODEX_FORKY_HOME:-$HOME/.codex-forky}"
CODEX_FORKY_BRIDGE_URL="${CODEX_FORKY_BRIDGE_URL:-http://127.0.0.1:3460}"
CODEX_FORKY_ROUTER_KEY="${CODEX_FORKY_ROUTER_KEY:-codex-forky-local}"
CODEX_FORKY_MODEL="${CODEX_FORKY_MODEL:-claude-sonnet-4-6}"
CODEX_FORKY_OAUTH_MODEL="${CODEX_FORKY_OAUTH_MODEL:-gpt-5.5}"
FORKY_BASE_URL="${FORKY_BASE_URL:-http://127.0.0.1:3458}"
FORKY_DIR="${FORKY_DIR:-$HOME/dev/forky}"
FORKY_LOG="${FORKY_LOG:-$HOME/.forky/forky.log}"
EXPECTED_EXEC_MODEL="${EXPECTED_EXEC_MODEL:-glm-5.2}"

failures=0

ok() {
  printf '[OK] %s\n' "$*"
}

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  failures=$((failures + 1))
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 is required"
}

bridge_healthy() {
  curl -fsS -m 2 -H "Authorization: Bearer $CODEX_FORKY_ROUTER_KEY" \
    "$CODEX_FORKY_BRIDGE_URL/v1/responses" >/dev/null 2>&1
}

check_runtime_config() {
  local profile="$CODEX_HOME_DIR/forky.config.toml"
  local env_file="$HOME/.config/codex-forky/env"
  local catalog="$CODEX_FORKY_HOME/model-catalog.json"
  local skill_file="$CODEX_HOME_DIR/skills/codex-maas-hybrid-router/SKILL.md"

  if [[ ! -f "$profile" ]]; then
    fail "Codex forky profile missing: $profile"
  elif grep -q "^model = \"$CODEX_FORKY_MODEL\"$" "$profile" &&
       grep -q '^model_reasoning_effort = "none"$' "$profile"; then
    ok "Codex profile uses $CODEX_FORKY_MODEL with reasoning disabled"
  else
    fail "Codex profile is stale; expected model=$CODEX_FORKY_MODEL and model_reasoning_effort=none in $profile"
  fi

  if [[ ! -f "$env_file" ]]; then
    fail "codex-forky env file missing: $env_file"
  elif grep -q "^export CODEX_FORKY_MODEL=\"$CODEX_FORKY_MODEL\"$" "$env_file"; then
    ok "codex-forky env uses $CODEX_FORKY_MODEL"
  else
    fail "codex-forky env is stale; expected CODEX_FORKY_MODEL=$CODEX_FORKY_MODEL in $env_file"
  fi

  CATALOG="$catalog" EXPECTED_MODEL="$CODEX_FORKY_MODEL" node <<'NODE'
const fs = require('fs');
const catalog = process.env.CATALOG;
const expected = process.env.EXPECTED_MODEL;
try {
  const body = JSON.parse(fs.readFileSync(catalog, 'utf8'));
  const model = body.models && body.models[0];
  if (!model) throw new Error('model catalog has no models[0]');
  if (model.slug !== expected) throw new Error(`catalog slug is ${model.slug}, expected ${expected}`);
  if (model.supports_search_tool !== false) throw new Error('catalog should not advertise search support');
  if (model.supports_reasoning_summaries !== false) throw new Error('catalog should not advertise reasoning summaries');
  process.exit(0);
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
NODE
  if [[ $? -eq 0 ]]; then
    ok "model catalog is lean for $CODEX_FORKY_MODEL"
  else
    fail "model catalog is stale; rerun scripts/configure-codex-forky.sh"
  fi

  if [[ -f "$skill_file" ]]; then
    ok "Codex skill is installed at $skill_file"
  else
    fail "Codex skill is not installed at $skill_file; rerun scripts/configure-codex-forky.sh"
  fi
}

start_bridge_if_needed() {
  if bridge_healthy; then
    ok "bridge reachable at $CODEX_FORKY_BRIDGE_URL"
    return 0
  fi

  if [[ -x "$CODEX_FORKY_BIN_DIR/codex-forky" ]]; then
    "$CODEX_FORKY_BIN_DIR/codex-forky" --version >/tmp/codex-forky-verify-start.out 2>/tmp/codex-forky-verify-start.err || true
  elif [[ -x "$CODEX_FORKY_BIN_DIR/codex-forky-bridge-run" ]]; then
    nohup "$CODEX_FORKY_BIN_DIR/codex-forky-bridge-run" >/tmp/codex-forky-bridge.log 2>&1 < /dev/null &
  else
    fail "codex-forky wrapper is missing; run scripts/configure-codex-forky.sh"
    return 1
  fi

  for _ in $(seq 1 40); do
    if bridge_healthy; then
      ok "bridge started and reachable at $CODEX_FORKY_BRIDGE_URL"
      return 0
    fi
    sleep 0.25
  done

  fail "bridge did not become reachable; check /tmp/codex-forky-bridge.log"
  return 1
}

check_codex_oauth() {
  local auth_file="${CODEX_FORKY_AUTH_FILE:-${CODEX_HOME:-$HOME/.codex}/auth.json}"
  AUTH_FILE="$auth_file" node <<'NODE'
const fs = require('fs');
const file = process.env.AUTH_FILE;
try {
  const auth = JSON.parse(fs.readFileSync(file, 'utf8'));
  const tokens = auth.tokens || {};
  if (!tokens.access_token && !auth.access_token) throw new Error('access token missing');
  if (!tokens.refresh_token && !auth.refresh_token) throw new Error('refresh token missing');
  const token = tokens.access_token || auth.access_token;
  const part = token.split('.')[1] || '';
  const padded = part.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (part.length % 4)) % 4);
  const payload = part ? JSON.parse(Buffer.from(padded, 'base64').toString('utf8')) : {};
  if (payload.exp && payload.exp * 1000 < Date.now()) throw new Error('access token expired');
  process.exit(0);
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
NODE
  if [[ $? -eq 0 ]]; then
    ok "Codex OAuth token present at $auth_file"
  else
    fail "Codex OAuth token check failed at $auth_file; run 'codex login'"
  fi
}

check_forky() {
  if curl -fsS -m 2 "$FORKY_BASE_URL/health" >/dev/null 2>&1 ||
     curl -fsS -m 2 "$FORKY_BASE_URL/" >/dev/null 2>&1; then
    ok "forky reachable at $FORKY_BASE_URL"
  else
    fail "forky is not reachable at $FORKY_BASE_URL"
  fi
}

check_exec_model() {
  local env_file="$FORKY_DIR/.env"
  if [[ ! -f "$env_file" ]]; then
    fail "forky env file not found: $env_file"
    return
  fi
  local exec_model
  exec_model="$(sed -n 's/^EXEC_MODEL=["'\'']\{0,1\}\([^"'\'']*\)["'\'']\{0,1\}$/\1/p' "$env_file" | tail -1)"
  if [[ "$exec_model" == "$EXPECTED_EXEC_MODEL" ]]; then
    ok "forky EXEC_MODEL is $exec_model"
  else
    fail "forky EXEC_MODEL is '${exec_model:-missing}', expected $EXPECTED_EXEC_MODEL"
  fi
}

check_oauth_route() {
  local out
  out="$(mktemp)"
  if curl -fsS -N -m 60 \
      -H "Authorization: Bearer $CODEX_FORKY_ROUTER_KEY" \
      -H 'Content-Type: application/json' \
      "$CODEX_FORKY_BRIDGE_URL/v1/responses" \
      -d '{"model":"'"$CODEX_FORKY_MODEL"'","input":[{"role":"user","content":[{"type":"input_text","text":"Reply with OK only."}]}],"stream":true}' \
      > "$out"; then
    if grep -q "\"model\":\"$CODEX_FORKY_OAUTH_MODEL\"" "$out"; then
      ok "no-tools request routed to Codex OAuth model $CODEX_FORKY_OAUTH_MODEL"
    else
      fail "no-tools request did not show model $CODEX_FORKY_OAUTH_MODEL"
    fi
  else
    fail "no-tools Codex OAuth request failed"
  fi
  rm -f "$out"
}

check_execution_route() {
  local before_lines out new_logs
  out="$(mktemp)"
  before_lines=0
  [[ -f "$FORKY_LOG" ]] && before_lines="$(wc -l < "$FORKY_LOG" | tr -d ' ')"

  if curl -fsS -N -m 90 \
      -H "Authorization: Bearer $CODEX_FORKY_ROUTER_KEY" \
      -H 'Content-Type: application/json' \
      "$CODEX_FORKY_BRIDGE_URL/v1/responses" \
      -d '{"model":"'"$CODEX_FORKY_MODEL"'","input":[{"role":"user","content":[{"type":"input_text","text":"Reply with OK only."}]}],"tools":[{"type":"function","name":"exec_command","description":"run shell","parameters":{"type":"object","properties":{"cmd":{"type":"string"}},"required":["cmd"]}}],"stream":true}' \
      > "$out"; then
    sleep 1
    if [[ -f "$FORKY_LOG" ]]; then
      new_logs="$(tail -n +"$((before_lines + 1))" "$FORKY_LOG" 2>/dev/null || true)"
      if printf '%s\n' "$new_logs" | grep -q '"routedVia":"execution"'; then
        ok "tool request entered forky execution route"
      else
        fail "tool request completed but no new forky execution log was found"
      fi
    else
      fail "forky log not found: $FORKY_LOG"
    fi
  else
    fail "tool execution route request failed"
  fi
  rm -f "$out"
}

main() {
  need_cmd node
  need_cmd curl
  need_cmd codex

  check_codex_oauth
  check_forky
  check_exec_model
  check_runtime_config
  start_bridge_if_needed
  check_oauth_route
  check_execution_route

  if [[ "$failures" -eq 0 ]]; then
    ok "codex-forky verification passed"
    exit 0
  fi

  printf '[FAIL] codex-forky verification failed with %s issue(s)\n' "$failures" >&2
  exit 1
}

main "$@"
