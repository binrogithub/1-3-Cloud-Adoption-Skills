#!/usr/bin/env bash
set -euo pipefail

# ─── Mint a scoped virtual key from LiteLLM ───
#
# Usage:
#   ./mint-virtual-key.sh                                    # key with alias, budget 100, duration 30d
#   ./mint-virtual-key.sh --models=glm-5.1,deepseek-v3.2    # model-scoped key
#   ./mint-virtual-key.sh --budget=50 --duration=7d          # custom budget + duration
#   ./mint-virtual-key.sh --models=glm-5.1 --budget=10       # model-scoped with budget
#   ./mint-virtual-key.sh --alias=my-key                     # custom alias
#   ./mint-virtual-key.sh --no-budget                        # unlimited budget (dangerous)

# ── Parse args ──
MODELS=""
BUDGET="100"
DURATION=""
ALIAS="opencode"
NO_BUDGET=false
for arg in "$@"; do
  case "$arg" in
    --models=*)     MODELS="${arg#--models=}" ;;
    --budget=*)     BUDGET="${arg#--budget=}" ;;
    --duration=*)   DURATION="${arg#--duration=}" ;;
    --alias=*)      ALIAS="${arg#--alias=}" ;;
    --no-budget)    NO_BUDGET=true ;;
  esac
done

if [ -z "${LITELLM_MASTER_KEY:-}" ]; then
  echo "ERROR: LITELLM_MASTER_KEY not set. Export it before running this script."
  exit 1
fi

# ── Build request body using jq for JSON safety ──
BODY_ARGS=()

# Always include key_alias
BODY_ARGS+=("--argjson" "alias" "\"$ALIAS\"")

# Add models if specified
if [ -n "$MODELS" ]; then
  MODELS_JSON=$(echo "$MODELS" | tr ',' '\n' | jq -R . | jq -s .)
  BODY_ARGS+=("--argjson" "models" "$MODELS_JSON")
fi

# Build the jq expression
JQ_EXPR='{key_alias: $alias'
if [ -n "$MODELS" ]; then
  JQ_EXPR="${JQ_EXPR}, models: \$models"
fi
if [ "$NO_BUDGET" = false ] && [ -n "$BUDGET" ]; then
  JQ_EXPR="${JQ_EXPR}, max_budget: ${BUDGET}"
fi
if [ -n "$DURATION" ]; then
  JQ_EXPR="${JQ_EXPR}, duration: \"${DURATION}\""
fi
JQ_EXPR="${JQ_EXPR}}"

# Generate the body
BODY=$(jq -n "${BODY_ARGS[@]}" "$JQ_EXPR")

# ── Mint the key ──
echo "Minting virtual key from LiteLLM..."
echo "  Alias:   $ALIAS"
echo "  Models:  ${MODELS:-all}"
if [ "$NO_BUDGET" = true ]; then
  echo "  Budget:  unlimited"
else
  echo "  Budget:  \$${BUDGET}"
fi
echo "  Duration: ${DURATION}"
echo ""

RESPONSE=$(curl -sf -X POST http://127.0.0.1:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d "$BODY")

KEY=$(echo "$RESPONSE" | jq -r '.key')
KEY_ID=$(echo "$RESPONSE" | jq -r '.key_id // empty')

if [ -z "$KEY" ] || [ "$KEY" = "null" ]; then
  echo "ERROR: Failed to mint virtual key."
  echo "Response: $RESPONSE"
  exit 1
fi

echo "Virtual key minted successfully:"
echo "  Key:    ${KEY:0:8}...${KEY: -4}"
[ -n "$KEY_ID" ] && echo "  Key ID: $KEY_ID"
echo ""
echo "To use this key, set it in opencode.jsonc:"
echo "  .provider.LiteLLM.options.apiKey = \"$KEY\""
echo ""
echo "Or re-run install.sh:"
echo "  ./install.sh --virtual-key=$KEY"
