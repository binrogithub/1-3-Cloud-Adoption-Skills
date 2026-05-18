#!/usr/bin/env bash
set -euo pipefail

# ─── opencode + oh-my-opencode-slim installer for Huawei MaaS via LiteLLM ───
#
# Prerequisites:
#   - Docker + Docker Compose V2 installed (for LiteLLM proxy)
#   - LiteLLM proxy running on 127.0.0.1:4000 (from litellm-huawei-maas skill)
#   - bun installed (https://bun.sh)
#   - jq installed (https://stedolan.github.io/jq/)
#   - LITELLM_MASTER_KEY set in environment
#
# Usage:
#   ./install.sh                          # interactive — prompts for keys
#   ./install.sh --virtual-key=sk-...     # non-interactive — use existing virtual key
#   ./install.sh --dry-run                # preview changes without modifying anything

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OPENCODE_DIR="$HOME/.config/opencode"
OPENCODE_CONFIG="$OPENCODE_DIR/opencode.jsonc"

# ── Constants ──
SLIM_VERSION="1.1.1"
CURL_TIMEOUT=15

# ── Helper: retry curl with backoff ──
retry_curl() {
  local max_attempts=3 delay=2 attempt=1
  while [ $attempt -le $max_attempts ]; do
    if curl "$@" &>/dev/null; then
      return 0
    fi
    [ $attempt -lt $max_attempts ] && sleep $delay
    ((attempt++))
  done
  return 1
}

# ── Helper: retry curl with output ──
retry_curl_output() {
  local max_attempts=3 delay=2 attempt=1 response=""
  while [ $attempt -le $max_attempts ]; do
    response=$(curl "$@" 2>/dev/null) && [ -n "$response" ] && echo "$response" && return 0
    [ $attempt -lt $max_attempts ] && sleep $delay
    ((attempt++))
  done
  return 1
}

# ── Parse args ──
VIRTUAL_KEY=""
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --virtual-key=*) VIRTUAL_KEY="${arg#--virtual-key=}" ;;
    --dry-run)       DRY_RUN=true ;;
  esac
done

echo "=== opencode + oh-my-opencode-slim installer for Huawei MaaS ==="
if [ "$DRY_RUN" = true ]; then
  echo "   (DRY RUN — no changes will be made)"
fi
echo ""

# ── 1. Check prerequisites ──
echo "1. Checking prerequisites..."

if ! command -v bun &>/dev/null; then
  echo "ERROR: bun is not installed. Install from https://bun.sh"
  exit 1
fi
echo "   bun: $(bun --version)"

if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is not installed. Install from https://stedolan.github.io/jq/"
  exit 1
fi
echo "   jq: $(jq --version)"

if ! command -v docker &>/dev/null; then
  echo "WARNING: docker is not installed. Required for LiteLLM proxy (prerequisite)."
  echo "   Install: https://docs.docker.com/engine/install/"
else
  if docker compose version &>/dev/null; then
    echo "   docker compose: $(docker compose version --short 2>/dev/null)"
  else
    echo "WARNING: Docker Compose V2 not available. Install via 'apt install docker-compose-v2' or similar."
  fi
fi

if ! command -v opencode &>/dev/null; then
  echo "   opencode: not found — will install via bun"
else
  echo "   opencode: $(opencode --version 2>/dev/null || echo 'installed')"
fi

# Check LiteLLM is reachable
if curl -sf -m $CURL_TIMEOUT "http://127.0.0.1:4000/health/liveliness" &>/dev/null; then
  echo "   LiteLLM proxy: reachable at http://127.0.0.1:4000"
else
  echo "WARNING: LiteLLM proxy not reachable at http://127.0.0.1:4000. Start it first with the litellm-huawei-maas skill."
fi

echo ""

# ── 2. Install opencode ──
echo "2. Installing opencode..."
if ! command -v opencode &>/dev/null; then
  if [ "$DRY_RUN" = true ]; then
    echo "   Would run: bun install -g opencode"
  else
    bun install -g opencode
    echo "   Installed: $(opencode --version 2>/dev/null)"
  fi
else
  echo "   Already installed."
fi
echo ""

# ── 3. Install oh-my-opencode-slim plugin ──
echo "3. Installing oh-my-opencode-slim plugin (v${SLIM_VERSION})..."
if [ "$DRY_RUN" = true ]; then
  echo "   Would run: bunx oh-my-opencode-slim@${SLIM_VERSION} install"
else
  bunx "oh-my-opencode-slim@${SLIM_VERSION}" install
  echo "   Plugin installed."
fi
echo ""

# ── 4. Acquire virtual key (idempotent — reuse existing if valid) ──
echo "4. Configuring LiteLLM virtual key..."

# Try to reuse existing key from current opencode config
if [ -z "$VIRTUAL_KEY" ] && [ -f "$OPENCODE_CONFIG" ]; then
  EXISTING_KEY=$(jq -r '.provider.LiteLLM.options.apiKey // empty' "$OPENCODE_CONFIG" 2>/dev/null || true)
  if [ -n "$EXISTING_KEY" ] && [ "$EXISTING_KEY" != "null" ] && [[ "$EXISTING_KEY" == sk-* ]]; then
    if [ "$DRY_RUN" = true ]; then
      echo "   Would test existing key: ${EXISTING_KEY:0:8}...${EXISTING_KEY: -4}"
      VIRTUAL_KEY="$EXISTING_KEY"
    elif retry_curl -sf -m $CURL_TIMEOUT "http://127.0.0.1:4000/v1/chat/completions" \
         -H "Authorization: Bearer $EXISTING_KEY" \
         -H "Content-Type: application/json" \
         -d '{"model":"glm-5.1","messages":[{"role":"user","content":"ok"}],"max_tokens":1}'; then
      echo "   Existing virtual key is valid. Reusing: ${EXISTING_KEY:0:8}...${EXISTING_KEY: -4}"
      VIRTUAL_KEY="$EXISTING_KEY"
    else
      echo "   Existing virtual key is invalid or expired. Minting new key."
    fi
  fi
fi

# Mint new key if needed
if [ -z "$VIRTUAL_KEY" ]; then
  if [ -z "${LITELLM_MASTER_KEY:-}" ]; then
    echo "  LITELLM_MASTER_KEY not set. Enter it (or Ctrl+C to abort):"
    read -r LITELLM_MASTER_KEY
    if [ -z "$LITELLM_MASTER_KEY" ]; then
      echo "ERROR: LITELLM_MASTER_KEY is required to mint virtual keys."
      exit 1
    fi
    export LITELLM_MASTER_KEY
  fi
  if [ "$DRY_RUN" = true ]; then
    echo "   Would mint new virtual key with alias 'opencode', unlimited budget & duration, all models"
  else
    echo "   Minting virtual key from LiteLLM..."
    RESPONSE=$(retry_curl_output -sf -X POST "http://127.0.0.1:4000/key/generate" \
      -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
      -H "Content-Type: application/json" \
      -d '{"key_alias": "opencode", "duration": null}')
    if [ -z "$RESPONSE" ]; then
      echo "ERROR: Failed to mint virtual key after 3 attempts. Check LiteLLM health and master key."
      exit 1
    fi
    VIRTUAL_KEY=$(echo "$RESPONSE" | jq -r '.key')
    if [ -z "$VIRTUAL_KEY" ] || [ "$VIRTUAL_KEY" = "null" ]; then
      echo "ERROR: Failed to mint virtual key. Response: $RESPONSE"
      exit 1
    fi
    echo "   Virtual key minted: ${VIRTUAL_KEY:0:8}...${VIRTUAL_KEY: -4}"
  fi
fi
echo ""

# ── 5. Write opencode.jsonc ──
echo "5. Writing opencode config..."

if [ "$DRY_RUN" = true ]; then
  echo "   Would write: $OPENCODE_CONFIG (chmod 600)"
  echo "   Template: $PROJECT_DIR/assets/config/opencode.jsonc.example"
  echo "   Substitutions: <LITELLM_VIRTUAL_KEY> → ${VIRTUAL_KEY:0:8}..., <HUAWEI_MAAS_API_KEY> → from env"
  echo ""
  echo "6. Writing oh-my-opencode-slim config..."
  echo "   Would write: $OPENCODE_DIR/oh-my-opencode-slim.json (chmod 600)"
  echo ""
  echo "=== Dry run complete — no changes made ==="
  exit 0
fi

mkdir -p "$OPENCODE_DIR"

# Warn if existing config has non-LiteLLM providers
if [ -f "$OPENCODE_CONFIG" ]; then
  EXISTING_PROVIDERS=$(jq -r '.provider | keys[]' "$OPENCODE_CONFIG" 2>/dev/null | grep -v '^LiteLLM$' | grep -v '^Huawei-MaaS$' || true)
  if [ -n "$EXISTING_PROVIDERS" ]; then
    echo "   WARNING: Existing config has non-LiteLLM/Huawei-MaaS providers: $EXISTING_PROVIDERS"
    echo "   These will be overwritten. Backing up."
  fi
fi

if [ -f "$OPENCODE_CONFIG" ]; then
  echo "   Backing up existing config."
  cp "$OPENCODE_CONFIG" "$OPENCODE_CONFIG.bak.$(date +%Y%m%d%H%M%S)"
fi

# Get Huawei MaaS API key
HUAWEI_MAAS_API_KEY="${HUAWEI_MAAS_API_KEY:-}"
if [ -z "$HUAWEI_MAAS_API_KEY" ]; then
  echo "   Enter Huawei MaaS API key (or press Enter to skip direct provider):"
  read -r HUAWEI_MAAS_API_KEY
fi

# Build opencode.jsonc from template using jq for JSON-safe substitution
TEMPLATE="$PROJECT_DIR/assets/config/opencode.jsonc.example"
TARGET="$OPENCODE_CONFIG"

jq --arg vk "$VIRTUAL_KEY" --arg mk "${HUAWEI_MAAS_API_KEY:-<HUAWEI_MAAS_API_KEY>}" \
  '.provider.LiteLLM.options.apiKey = $vk |
   .provider["Huawei-MaaS"].options.apiKey = $mk' \
  "$TEMPLATE" > "$TARGET"

chmod 600 "$TARGET"
echo "   Written: $TARGET"
echo ""

# ── 6. Write oh-my-opencode-slim.json ──
echo "6. Writing oh-my-opencode-slim config..."
SLIM_CONFIG="$OPENCODE_DIR/oh-my-opencode-slim.json"

if [ -f "$SLIM_CONFIG" ]; then
  echo "   Backing up existing config."
  cp "$SLIM_CONFIG" "$SLIM_CONFIG.bak.$(date +%Y%m%d%H%M%S)"
fi

cp "$PROJECT_DIR/assets/config/oh-my-opencode-slim.json.example" "$SLIM_CONFIG"
chmod 600 "$SLIM_CONFIG"
echo "   Written: $SLIM_CONFIG"
echo ""

# ── 7. Summary ──
echo "=== Installation complete ==="
echo ""
echo "Config files:"
echo "  opencode:             $TARGET (chmod 600)"
echo "  oh-my-opencode-slim:  $SLIM_CONFIG (chmod 600)"
echo ""
echo "Versions:"
echo "  oh-my-opencode-slim:  v${SLIM_VERSION}"
command -v opencode &>/dev/null && echo "  opencode:             $(opencode --version 2>/dev/null || echo 'unknown')"
echo ""
echo "Preset: LiteLLM-Huawei-MaaS (default) — all 5 models via LiteLLM"
echo "Fallback: LiteLLM-Huawei-MaaS-Lite — glm-5.1, glm-5, deepseek-v3.2 only"
echo "Direct: Huawei-MaaS / Huawei-MaaS-Lite — bypass LiteLLM proxy"
echo "Switch preset at runtime: /preset LiteLLM-Huawei-MaaS-Lite"
echo ""
echo "LiteLLM proxy URL: http://127.0.0.1:4000"
echo ""
echo "Next steps:"
echo "  1. Validate: $SCRIPT_DIR/validate.sh"
echo "  2. Run: opencode"
