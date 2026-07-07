#!/usr/bin/env bash
set -euo pipefail

# configure-claude-code.sh
# Point a native Claude Code client at a LiteLLM gateway (Anthropic /v1/messages).
#
# The only required input is the LiteLLM virtual API key issued for this client.
# Writes the authoritative env block into ~/.claude/settings.json (read by
# Claude Code regardless of shell state) and, optionally, a managed export
# block into a shell profile.
#
# --restore undoes all of the above and returns Claude Code to Anthropic's
# API. Your claude.ai login (OAuth credentials) is stored separately and is
# never touched by this script, so it survives switching in both directions.
#
# No client-side proxy, router, or adapter is installed.

DEFAULT_BASE_URL="http://127.0.0.1:4000"
DEFAULT_MODEL="claude-opus-4-6"
MANAGED_BEGIN="# >>> claude-code-litellm managed block >>>"
MANAGED_END="# <<< claude-code-litellm managed block <<<"

API_KEY=""
BASE_URL="${LITELLM_BASE_URL:-$DEFAULT_BASE_URL}"
MODEL="${CLAUDE_CODE_MODEL:-$DEFAULT_MODEL}"
PROFILE=""
WRITE_SETTINGS=1
PRINT_ENV=0
VERIFY=0
PIN_AUTH_TOKEN=0
RESTORE=0

# Every env var this script may write; --restore removes exactly this set.
MANAGED_VARS=(
  ANTHROPIC_BASE_URL
  ANTHROPIC_API_KEY
  ANTHROPIC_AUTH_TOKEN
  ANTHROPIC_MODEL
  ANTHROPIC_DEFAULT_HAIKU_MODEL
  ANTHROPIC_SMALL_FAST_MODEL
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC
)

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  configure-claude-code.sh <api-key> [options]
  configure-claude-code.sh --api-key KEY [options]
  configure-claude-code.sh --restore [--profile FILE] [--no-settings]

Options:
  --api-key KEY   LiteLLM virtual key for this client (required).
  --base-url URL  LiteLLM gateway URL. Default: http://127.0.0.1:4000
                  (or env LITELLM_BASE_URL). Use http://<gateway-host>:4000
                  for remote clients.
  --model NAME    Model alias to request. Default: claude-opus-4-6.
  --profile FILE  Also write a managed export block into this shell profile
                  (e.g. ~/.bashrc). Idempotent; previous block is replaced.
  --no-settings   Do not write ~/.claude/settings.json (env exports only).
  --print-env     Print export commands to stdout and exit (writes nothing).
  --verify        After configuring, send a minimal /v1/messages request
                  and report PASS/FAIL.
  --pin-auth-token
                  Also pin ANTHROPIC_AUTH_TOKEN to the same key. Use on hosts
                  where legacy proxies/wrappers may have exported a stale
                  AUTH_TOKEN (it outranks ANTHROPIC_API_KEY inside Claude
                  Code). Side effect: Claude Code shows a harmless
                  "Both ANTHROPIC_AUTH_TOKEN and ANTHROPIC_API_KEY set"
                  notice.
  --restore       Switch back to Anthropic's API: remove the env vars this
                  script wrote from ~/.claude/settings.json and, with
                  --profile FILE, delete the managed export block from that
                  profile. No API key needed. Your claude.ai login is never
                  touched. Combine with --print-env to print the matching
                  `unset` commands for the current shell. Restart Claude
                  Code afterwards.
  -h, --help      Show this help.
EOF
}

mask() {
  local k="$1"; local n="${#k}"
  if [[ -z "$k" ]]; then printf '<missing>'
  elif (( n <= 8 )); then printf '****'
  else printf '%s****%s' "${k:0:4}" "${k:n-4:4}"; fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-key)   [[ $# -ge 2 ]] || die "--api-key requires a value"; API_KEY="$2"; shift 2 ;;
    --api-key=*) API_KEY="${1#*=}"; shift ;;
    --base-url)  [[ $# -ge 2 ]] || die "--base-url requires a value"; BASE_URL="$2"; shift 2 ;;
    --base-url=*) BASE_URL="${1#*=}"; shift ;;
    --model)     [[ $# -ge 2 ]] || die "--model requires a value"; MODEL="$2"; shift 2 ;;
    --model=*)   MODEL="${1#*=}"; shift ;;
    --profile)   [[ $# -ge 2 ]] || die "--profile requires a value"; PROFILE="$2"; shift 2 ;;
    --profile=*) PROFILE="${1#*=}"; shift ;;
    --no-settings) WRITE_SETTINGS=0; shift ;;
    --print-env) PRINT_ENV=1; shift ;;
    --verify)    VERIFY=1; shift ;;
    --pin-auth-token) PIN_AUTH_TOKEN=1; shift ;;
    --restore)   RESTORE=1; shift ;;
    -h|--help)   usage; exit 0 ;;
    -*)          die "unknown option: $1" ;;
    *)           [[ -z "$API_KEY" ]] || die "unexpected argument: $1"; API_KEY="$1"; shift ;;
  esac
done

# --- restore mode: undo everything this script writes, then exit
if [[ "$RESTORE" == "1" ]]; then
  [[ -z "$API_KEY" ]] || die "--restore takes no API key"
  [[ "$VERIFY" == "0" ]] || die "--restore cannot be combined with --verify"
  [[ "$PIN_AUTH_TOKEN" == "0" ]] || die "--restore cannot be combined with --pin-auth-token"

  if [[ "$PRINT_ENV" == "1" ]]; then
    printf 'unset %s\n' "${MANAGED_VARS[@]}"
    exit 0
  fi

  if [[ "$WRITE_SETTINGS" == "1" ]]; then
    command -v python3 >/dev/null 2>&1 || die "python3 is required to update ~/.claude/settings.json (use --no-settings to skip)"
    SETTINGS_FILE="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"
    if [[ -f "$SETTINGS_FILE" ]]; then
      ASG_VARS="${MANAGED_VARS[*]}" SETTINGS_FILE="$SETTINGS_FILE" python3 - <<'PY'
import json, os, time
path = os.environ["SETTINGS_FILE"]
with open(path) as f:
    data = json.load(f)
backup = f"{path}.bak.{time.strftime('%Y%m%d%H%M%S')}"
with open(backup, "w") as f:
    json.dump(data, f, indent=2)
print(f"Backup written: {backup}")
env = data.get("env", {})
removed = [v for v in os.environ["ASG_VARS"].split() if env.pop(v, None) is not None]
if not env:
    data.pop("env", None)
with open(path, "w") as f:
    json.dump(data, f, indent=2)
if removed:
    print(f"Updated: {path} (removed: {', '.join(removed)})")
else:
    print(f"No gateway settings found in {path}; nothing to remove.")
PY
    else
      echo "No $SETTINGS_FILE; nothing to remove."
    fi
  fi

  if [[ -n "$PROFILE" ]]; then
    case "$PROFILE" in "~") PROFILE="$HOME" ;; "~/"*) PROFILE="$HOME/${PROFILE#\~/}" ;; esac
    if [[ -f "$PROFILE" ]] && grep -qxF "$MANAGED_BEGIN" "$PROFILE"; then
      backup="$PROFILE.bak.$(date +%Y%m%d%H%M%S)"
      cp "$PROFILE" "$backup"
      echo "Backup written: $backup"
      tmp="$(mktemp)"
      awk -v b="$MANAGED_BEGIN" -v e="$MANAGED_END" '$0==b{s=1;next} $0==e{s=0;next} s!=1{print}' "$PROFILE" > "$tmp"
      install -m 600 "$tmp" "$PROFILE"
      rm -f "$tmp"
      echo "Updated: $PROFILE (managed block removed)"
    else
      echo "No managed block in ${PROFILE}; nothing to remove."
    fi
  fi

  echo
  echo "Claude Code restored to Anthropic's API (your claude.ai login was never touched)."
  echo "If a shell still exports the gateway variables, start a fresh login shell or run:"
  echo "  $(printf 'unset %s' "${MANAGED_VARS[*]}")"
  echo
  echo "Restart any open Claude Code session for the change to take effect."
  exit 0
fi

[[ -n "$API_KEY" ]] || { usage >&2; die "API key is required"; }
BASE_URL="${BASE_URL%/}"

print_exports() {
  printf 'export ANTHROPIC_BASE_URL=%q\n' "$BASE_URL"
  printf 'export ANTHROPIC_API_KEY=%q\n' "$API_KEY"
  [[ "$PIN_AUTH_TOKEN" == "1" ]] && printf 'export ANTHROPIC_AUTH_TOKEN=%q\n' "$API_KEY"
  printf 'export ANTHROPIC_MODEL=%q\n' "$MODEL"
  printf 'export ANTHROPIC_DEFAULT_HAIKU_MODEL=%q\n' "$MODEL"
  printf 'export ANTHROPIC_SMALL_FAST_MODEL=%q\n' "$MODEL"
  printf 'export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1\n'
}

if [[ "$PRINT_ENV" == "1" ]]; then
  print_exports
  exit 0
fi

# --- write ~/.claude/settings.json env block (authoritative for Claude Code)
if [[ "$WRITE_SETTINGS" == "1" ]]; then
  command -v python3 >/dev/null 2>&1 || die "python3 is required to update ~/.claude/settings.json (use --no-settings to skip)"
  SETTINGS_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
  mkdir -p "$SETTINGS_DIR"
  ASG_BASE_URL="$BASE_URL" ASG_API_KEY="$API_KEY" ASG_MODEL="$MODEL" \
  ASG_PIN_AUTH="$PIN_AUTH_TOKEN" \
  SETTINGS_FILE="$SETTINGS_DIR/settings.json" python3 - <<'PY'
import json, os, time
path = os.environ["SETTINGS_FILE"]
data = {}
if os.path.exists(path):
    with open(path) as f:
        data = json.load(f)
    backup = f"{path}.bak.{time.strftime('%Y%m%d%H%M%S')}"
    with open(backup, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Backup written: {backup}")
env = data.setdefault("env", {})
model = os.environ["ASG_MODEL"]
env.update({
    "ANTHROPIC_BASE_URL": os.environ["ASG_BASE_URL"],
    "ANTHROPIC_API_KEY": os.environ["ASG_API_KEY"],
    "ANTHROPIC_MODEL": model,
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,
    "ANTHROPIC_SMALL_FAST_MODEL": model,
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
})
if os.environ.get("ASG_PIN_AUTH") == "1":
    # AUTH_TOKEN outranks API_KEY inside Claude Code; pinning it defends
    # against stale tokens exported by legacy proxies/wrappers still living
    # in long-running shells. Claude Code will show a harmless
    # "Both ... set" notice when this is enabled.
    env["ANTHROPIC_AUTH_TOKEN"] = os.environ["ASG_API_KEY"]
else:
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
with open(path, "w") as f:
    json.dump(data, f, indent=2)
print(f"Updated: {path}")
PY
fi

# --- optional shell profile managed block
if [[ -n "$PROFILE" ]]; then
  case "$PROFILE" in "~") PROFILE="$HOME" ;; "~/"*) PROFILE="$HOME/${PROFILE#\~/}" ;; esac
  tmp="$(mktemp)"
  if [[ -f "$PROFILE" ]]; then
    backup="$PROFILE.bak.$(date +%Y%m%d%H%M%S)"
    cp "$PROFILE" "$backup"
    echo "Backup written: $backup"
    awk -v b="$MANAGED_BEGIN" -v e="$MANAGED_END" '$0==b{s=1;next} $0==e{s=0;next} s!=1{print}' "$PROFILE" > "$tmp"
  fi
  {
    echo "$MANAGED_BEGIN"
    echo "# Managed by configure-claude-code.sh. Re-run the script to update."
    print_exports
    echo "$MANAGED_END"
  } >> "$tmp"
  install -m 600 "$tmp" "$PROFILE"
  rm -f "$tmp"
  echo "Updated: $PROFILE"
fi

echo
echo "Claude Code -> LiteLLM configuration"
echo "  Base URL: $BASE_URL"
echo "  Model:    $MODEL"
echo "  API key:  $(mask "$API_KEY")"
echo "  Settings: $([[ $WRITE_SETTINGS == 1 ]] && echo "written" || echo "skipped")"
echo
echo "Restart any open Claude Code session for the change to take effect."

# --- optional end-to-end verification
if [[ "$VERIFY" == "1" ]]; then
  command -v curl >/dev/null 2>&1 || die "curl is required for --verify"
  echo
  echo "Verifying $BASE_URL/v1/messages ..."
  body=$(printf '{"model":"%s","max_tokens":16,"messages":[{"role":"user","content":"ping"}]}' "$MODEL")
  http_code=$(curl -sS -o /tmp/asg_verify.$$ -w "%{http_code}" -m 30 \
    -H "content-type: application/json" \
    -H "x-api-key: $API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -d "$body" "$BASE_URL/v1/messages" || echo "000")
  if [[ "$http_code" == "200" ]] && grep -q '"type"[[:space:]]*:[[:space:]]*"message"' /tmp/asg_verify.$$; then
    echo "VERIFY PASS (HTTP 200, message response)"
  else
    echo "VERIFY FAIL (HTTP $http_code)"
    head -c 300 /tmp/asg_verify.$$ 2>/dev/null; echo
    rm -f /tmp/asg_verify.$$
    exit 1
  fi
  rm -f /tmp/asg_verify.$$

  # Tool-call capability: Claude Code is unusable when the backend endpoint
  # does not parse tool calls - the model prints raw <tool_call> markup as
  # visible text and no tools ever execute (issue #111).
  echo "Verifying tool-call capability ..."
  tool_body=$(printf '{"model":"%s","max_tokens":300,"tools":[{"name":"echo_check","description":"Echo a short string back. Used to verify tool calling works.","input_schema":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}}],"messages":[{"role":"user","content":"Call the echo_check tool with text set to ok. Do not answer in plain text."}]}' "$MODEL")
  tool_code=$(curl -sS -o /tmp/asg_verify_tool.$$ -w "%{http_code}" -m 60 \
    -H "content-type: application/json" \
    -H "x-api-key: $API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -d "$tool_body" "$BASE_URL/v1/messages" || echo "000")
  if [[ "$tool_code" == "200" ]] && grep -q '"type"[[:space:]]*:[[:space:]]*"tool_use"' /tmp/asg_verify_tool.$$; then
    echo "TOOL-CALL PASS (structured tool_use block received)"
  elif grep -qE '<tool_call|<arg_key>|</[A-Za-z_]+_tool>' /tmp/asg_verify_tool.$$; then
    echo "TOOL-CALL FAIL: the backend returned raw tool-call MARKUP as text."
    echo "  Your model endpoint is not parsing tool calls into structured"
    echo "  tool_calls. In Claude Code every tool invocation will appear as"
    echo "  raw text (<tool_call>...) and no tools will execute."
    echo "  Fix on the SERVER side, not in this client:"
    echo "   - Huawei MaaS: use a model/endpoint version with function"
    echo "     calling (tools) enabled for OpenAI-compatible requests."
    echo "   - Self-hosted vLLM: start with --enable-auto-tool-choice and"
    echo "     the matching --tool-call-parser for your model."
    head -c 300 /tmp/asg_verify_tool.$$ 2>/dev/null; echo
    rm -f /tmp/asg_verify_tool.$$
    exit 1
  else
    echo "TOOL-CALL WARN (HTTP $tool_code, no tool_use block in response;"
    echo "  inconclusive - the model may simply not have called the tool):"
    head -c 300 /tmp/asg_verify_tool.$$ 2>/dev/null; echo
  fi
  rm -f /tmp/asg_verify_tool.$$
fi
