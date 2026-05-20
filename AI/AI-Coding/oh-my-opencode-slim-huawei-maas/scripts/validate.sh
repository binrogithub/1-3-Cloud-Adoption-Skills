#!/usr/bin/env bash
set -uo pipefail

# ─── Validate opencode + oh-my-opencode-slim + LiteLLM integration ───
#
# Run this after install.sh to verify everything works end-to-end.
#
# Usage:
#   ./validate.sh          # full validation including network checks
#   ./validate.sh --dry-run  # syntax and structure checks only (no network)

PASS=0
FAIL=0
DRY_RUN=false
LITELLM_URL="http://127.0.0.1:4000"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
  esac
done

check() {
  local desc="$1"
  shift
  if "$@" &>/dev/null; then
    echo "  ✓ $desc"
    PASS=$((PASS + 1))
  else
    echo "  ✗ $desc"
    FAIL=$((FAIL + 1))
  fi
}

skip_check() {
  local desc="$1"
  echo "  ○ $desc (skipped: --dry-run)"
}

# ── Helper: pipe JSON into jq as a single command (avoids top-level pipe in check) ──
jqc() {
  printf '%s' "$1" | jq -e "$2" 2>/dev/null
}

# ── Helper: strip JSONC comments for jq ──
strip_jsonc() {
  local file="$1"
  if command -v node &>/dev/null; then
    node -e "const fs=require('fs'); const s=fs.readFileSync('$file','utf8'); const r=s.replace(/\/\/.*$/gm,'').replace(/\/\*[\s\S]*?\*\//g,''); process.stdout.write(r);" 2>/dev/null
  elif command -v python3 &>/dev/null; then
    python3 -c "
import sys
def strip_jsonc(s):
    out = []; i = 0; n = len(s)
    while i < n:
        # inside string — emit verbatim (handle escapes)
        if s[i] == '\"':
            j = i + 1
            while j < n:
                if s[j] == '\\\\': j += 2; continue
                if s[j] == '\"': break
                j += 1
            out.append(s[i:j+1]); i = j + 1; continue
        # block comment
        if i+1 < n and s[i] == '/' and s[i+1] == '*':
            j = s.find('*/', i+2)
            if j == -1: j = n-2
            out.append(' '); i = j + 2; continue
        # line comment
        if i+1 < n and s[i] == '/' and s[i+1] == '/':
            j = s.find('\n', i+2)
            if j == -1: i = n
            else: i = j
            continue
        out.append(s[i]); i += 1
    return ''.join(out)
sys.stdout.write(strip_jsonc(sys.stdin.read()))
" < "$file"
  elif jq -e . "$file" &>/dev/null; then
    cat "$file"
  else
    echo "ERROR: Cannot parse JSONC file '$file' — install node.js or python3 for JSONC support" >&2
    return 1
  fi
}

if [ "$DRY_RUN" = true ]; then
  echo "=== Validation: opencode + Huawei MaaS via LiteLLM (DRY RUN) ==="
  echo "   (Network connectivity checks skipped)"
else
  echo "=== Validation: opencode + Huawei MaaS via LiteLLM ==="
fi
echo ""

# ── 1. LiteLLM proxy ──
echo "1. LiteLLM proxy"
if [ "$DRY_RUN" = true ]; then
  skip_check "LiteLLM health endpoint"
  skip_check "LiteLLM metrics endpoint"
  skip_check "LiteLLM Docker container running"
else
  check "LiteLLM health endpoint"   curl -sf -m 15 "$LITELLM_URL/health/liveliness"
  check "LiteLLM metrics endpoint"   curl -sf -m 15 "${LITELLM_URL%/}/metrics"
  check "LiteLLM Docker container running" test -n "$(docker ps --filter 'name=litellm_proxy' --filter 'status=running' --format '{{.Names}}' 2>/dev/null || true)"
fi
echo ""

# ── 2. opencode binary ──
echo "2. opencode binary"
check "opencode installed"         command -v opencode
echo ""

# ── 3. Config files ──
echo "3. Config files"
OPENCODE_DIR="$HOME/.config/opencode"
check "opencode.jsonc exists"       [ -f "$OPENCODE_DIR/opencode.jsonc" ] || [ -f "$OPENCODE_DIR/opencode.json" ]
check "oh-my-opencode-slim.json exists" [ -f "$OPENCODE_DIR/oh-my-opencode-slim.json" ] || [ -f "$OPENCODE_DIR/oh-my-opencode-slim.jsonc" ]
echo ""

# ── 4. Provider configuration ──
echo "4. Provider configuration"
CONFIG_FILE=""
if [ -f "$OPENCODE_DIR/opencode.jsonc" ]; then
  CONFIG_FILE="$OPENCODE_DIR/opencode.jsonc"
elif [ -f "$OPENCODE_DIR/opencode.json" ]; then
  CONFIG_FILE="$OPENCODE_DIR/opencode.json"
fi

if [ -n "$CONFIG_FILE" ]; then
  CLEAN_CONFIG=$(strip_jsonc "$CONFIG_FILE")
  check "LiteLLM provider defined"      jqc "$CLEAN_CONFIG" '.provider.LiteLLM'
  check "LiteLLM baseURL set"           jqc "$CLEAN_CONFIG" '.provider.LiteLLM.options.baseURL'
  check "LiteLLM baseURL is 0.0.0.0:4000" jqc "$CLEAN_CONFIG" '.provider.LiteLLM.options.baseURL == "http://0.0.0.0:4000"'
  check "LiteLLM apiKey set"            jqc "$CLEAN_CONFIG" '.provider.LiteLLM.options.apiKey'
  check "LiteLLM apiKey starts with sk-" test "$(printf '%s' "$CLEAN_CONFIG" | jq -r '.provider.LiteLLM.options.apiKey // ""' 2>/dev/null | cut -c1-3)" = "sk-"
  check "Huawei-MaaS provider defined"  jqc "$CLEAN_CONFIG" '.provider["Huawei-MaaS"]'
  check "Huawei-MaaS has all 5 models"  jqc "$CLEAN_CONFIG" '.provider["Huawei-MaaS"].models | keys | length >= 5'
  check "LiteLLM has all 5 models"      jqc "$CLEAN_CONFIG" '.provider.LiteLLM.models | keys | length >= 5'
  check "provider key is singular"       test "$(printf '%s' "$CLEAN_CONFIG" | jq -r 'if .provider then "ok" else "fail" end' 2>/dev/null)" = "ok"
  check "agent key is singular"          test "$(printf '%s' "$CLEAN_CONFIG" | jq -r 'if .agent then "ok" else "fail" end' 2>/dev/null)" = "ok"
  check "oh-my-opencode-slim plugin"    jqc "$CLEAN_CONFIG" '.plugin | index("oh-my-opencode-slim")'
  check "explore agent disabled"        jqc "$CLEAN_CONFIG" '.agent.explore.disable == true'
  check "general agent disabled"        jqc "$CLEAN_CONFIG" '.agent.general.disable == true'
  check "LSP enabled"                   jqc "$CLEAN_CONFIG" '.lsp == true'
  check "Config file permissions 600"   [ "$(stat -c '%a' "$CONFIG_FILE" 2>/dev/null || stat -f '%Lp' "$CONFIG_FILE" 2>/dev/null)" = "600" ]
else
  echo "  ✗ No opencode config file found"
  FAIL=$((FAIL + 14))
fi
echo ""

# ── 5. oh-my-opencode-slim preset ──
echo "5. oh-my-opencode-slim preset"
SLIM_CONFIG=""
if [ -f "$OPENCODE_DIR/oh-my-opencode-slim.json" ]; then
  SLIM_CONFIG="$OPENCODE_DIR/oh-my-opencode-slim.json"
elif [ -f "$OPENCODE_DIR/oh-my-opencode-slim.jsonc" ]; then
  SLIM_CONFIG="$OPENCODE_DIR/oh-my-opencode-slim.jsonc"
fi

if [ -n "$SLIM_CONFIG" ]; then
  CLEAN_SLIM=$(strip_jsonc "$SLIM_CONFIG")
  check "LiteLLM-Huawei-MaaS preset exists"      jqc "$CLEAN_SLIM" '.presets["LiteLLM-Huawei-MaaS"]'
  check "LiteLLM-Huawei-MaaS-Lite preset exists" jqc "$CLEAN_SLIM" '.presets["LiteLLM-Huawei-MaaS-Lite"]'
  check "Huawei-MaaS direct preset exists"        jqc "$CLEAN_SLIM" '.presets["Huawei-MaaS"]'
  check "Huawei-MaaS-Lite direct preset exists"   jqc "$CLEAN_SLIM" '.presets["Huawei-MaaS-Lite"]'
  check "Default preset is LiteLLM-Huawei-MaaS"   jqc "$CLEAN_SLIM" '.preset == "LiteLLM-Huawei-MaaS"'
  check "Orchestrator model set"         jqc "$CLEAN_SLIM" '.presets["LiteLLM-Huawei-MaaS"].orchestrator.model'
  check "Oracle model set"               jqc "$CLEAN_SLIM" '.presets["LiteLLM-Huawei-MaaS"].oracle.model'
  check "Council model set"              jqc "$CLEAN_SLIM" '.presets["LiteLLM-Huawei-MaaS"].council.model'
  check "Librarian model set"            jqc "$CLEAN_SLIM" '.presets["LiteLLM-Huawei-MaaS"].librarian.model'
  check "Explorer model set"             jqc "$CLEAN_SLIM" '.presets["LiteLLM-Huawei-MaaS"].explorer.model'
  check "Designer model set"             jqc "$CLEAN_SLIM" '.presets["LiteLLM-Huawei-MaaS"].designer.model'
  check "Fixer model set"                jqc "$CLEAN_SLIM" '.presets["LiteLLM-Huawei-MaaS"].fixer.model'
  check "Observer disabled"              jqc "$CLEAN_SLIM" '.disabled_agents | index("observer")'
  check "Orchestrator has skills"        jqc "$CLEAN_SLIM" '.presets["LiteLLM-Huawei-MaaS"].orchestrator.skills'
  check "Orchestrator has mcps"          jqc "$CLEAN_SLIM" '.presets["LiteLLM-Huawei-MaaS"].orchestrator.mcps'
  check "Librarian has mcps"             jqc "$CLEAN_SLIM" '.presets["LiteLLM-Huawei-MaaS"].librarian.mcps | length > 0'
  check "Config file permissions 600"    [ "$(stat -c '%a' "$SLIM_CONFIG" 2>/dev/null || stat -f '%Lp' "$SLIM_CONFIG" 2>/dev/null)" = "600" ]
else
  echo "  ✗ No oh-my-opencode-slim config file found"
  FAIL=$((FAIL + 16))
fi
echo ""

# ── 6. Fallback and council configuration ──
echo "6. Advanced configuration"
if [ -n "$SLIM_CONFIG" ]; then
  check "Fallback enabled"               jqc "$CLEAN_SLIM" '.fallback.enabled == true'
  check "Fallback chains defined"        jqc "$CLEAN_SLIM" '.fallback.chains | length > 0'
  check "Council presets defined"        jqc "$CLEAN_SLIM" '.council.presets'
  check "Council has alpha/beta/gamma"   jqc "$CLEAN_SLIM" '.council.presets.default | .alpha and .beta and .gamma'
  check "Todo continuation configured"   jqc "$CLEAN_SLIM" '.todoContinuation'
  check "Session manager configured"     jqc "$CLEAN_SLIM" '.sessionManager'
else
  echo "  ✗ No oh-my-opencode-slim config file found"
  FAIL=$((FAIL + 6))
fi
echo ""

# ── 7. LiteLLM model availability ──
echo "7. LiteLLM model availability (via proxy)"
if [ "$DRY_RUN" = true ]; then
  skip_check "Model catalog reachable"
  skip_check "All models available"
else
  VIRTUAL_KEY=""
  if [ -n "$CONFIG_FILE" ]; then
    VIRTUAL_KEY=$(printf '%s' "$CLEAN_CONFIG" | jq -r '.provider.LiteLLM.options.apiKey // empty' 2>/dev/null)
  fi

  if [ -z "$VIRTUAL_KEY" ]; then
    VIRTUAL_KEY="${LITELLM_MASTER_KEY:-}"
  fi

  if [ -z "$VIRTUAL_KEY" ]; then
    echo "  ✗ No API key available for model checks"
    FAIL=$((FAIL + 1))
  else
    # ── 7a. Discover models dynamically from /v1/models ──
    MODELS_JSON=$(curl -sf -m 10 "$LITELLM_URL/v1/models" \
      -H "Authorization: Bearer $VIRTUAL_KEY" 2>/dev/null)

    if [ -z "$MODELS_JSON" ] || ! printf '%s' "$MODELS_JSON" | jq -e '.data | length > 0' >/dev/null 2>&1; then
      echo "  ✗ Model catalog not reachable or empty"
      FAIL=$((FAIL + 1))
    else
      check "Model catalog reachable" true

      MODEL_COUNT=$(printf '%s' "$MODELS_JSON" | jq '.data | length' 2>/dev/null)
      MODEL_LIST=$(printf '%s' "$MODELS_JSON" | jq -r '.data[].id' 2>/dev/null)

      echo "  ℹ Discovered $MODEL_COUNT model(s): $(echo "$MODEL_LIST" | tr '\n' ' ' | sed 's/ $//')"

      # ── 7b. Minimal chat completion per model ──
      for model in $MODEL_LIST; do
        BODY=$(jq -nc --arg m "$model" '{model: $m, messages: [{role: "user", content: "ok"}]}')
        check "Model $model inference" curl -sf -m 15 "$LITELLM_URL/v1/chat/completions" \
          -H "Authorization: Bearer $VIRTUAL_KEY" \
          -H "Content-Type: application/json" \
          -d "$BODY"
      done
    fi
  fi
fi
echo ""

# ── Summary ──
TOTAL=$((PASS + FAIL))
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
